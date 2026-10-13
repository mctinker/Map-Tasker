"""devicecheck: what Tasker already has, of what is about to be sent -- by name, and by ID against a fresh backup."""

from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import TYPE_CHECKING

import defusedxml.ElementTree as DefusedET

from maptasker.src.core.maputil2 import (
    auth_key_for,
    held_auth_key,
    http_delete_request,
    http_request,
    request_with_auth_key,
    tasker_name_matchable,
)
from maptasker.src.core.sysconst import logger
from maptasker.src.device.devicetask import (
    PROFILES_ENDPOINT,
    SCENES_ENDPOINT,
    build_reporting_task,
    fetch_tasker_object_names,
    install_task_on_android,
    poll_for_result,
    run_task_on_android,
)
from maptasker.src.device.deviceverify import task_names_on_device, verify_names_on_android

if TYPE_CHECKING:
    from collections.abc import Iterable
    from xml.etree.ElementTree import Element

    from maptasker.src.core.primitem import RunState

# ==========================================
# What Tasker already has, of what is about to be sent
# ==========================================
#
# Every Save To Android and Import Into Tasker button asks the device whether a FILE is already
# at the path it writes.  None of them used to ask Tasker whether it already has the OBJECTS in
# that file -- and that is what decides what an import does with them: a Task sent through
# api/import is added beside one of the same name rather than replacing it (see
# install_task_on_android), and Tasker's import screen offers to replace a Profile it has.
#
# BY NAME, because a name is all Tasker's HTTP API reports.  api/tasks, api/profiles and
# api/scenes answer objects with a "name" and no id, so an id the device has already given to a
# different object cannot be seen from here.  Unnamed Profiles and Tasks have nothing to ask
# about and are left out rather than guessed at.
#
# Tasks are asked about BY NAME too (task_names_on_device).  They used to be read as the whole
# list and matched here, but the handler looks up every Task in Tasker before answering that --
# seconds on a large configuration, and past the read timeout whenever the phone was busy, which
# failed the check with a connection error on a device that was fine.  Its 'name=' filter takes
# repeated names like the Profile and Scene ones do (checked against a real device), and answers
# at once.
#
# PROJECTS HAVE NO ENDPOINT.  Tasker's own 'Test Tasker' action does have a Projects type, so a
# helper Task asks it and writes the answer where the 'file' route can read it -- the exchange the
# file list uses (fetch_file_list_from_device).
#
# 'Test Tasker' answers every list type AS AN ARRAY: Store Result In %alpha gives %alpha1, %alpha2,
# ... one name each, for Projects, Profiles, Scenes and Tasks alike (confirmed by the user on a
# device, 2026-09-11).  It is also what the endpoints above are made of: the HTTP API's own GET
# Tasks, GET Profiles and GET Scenes handlers (task1064, task1070 and task1066 in this repo's
# sample backup) each begin with 'Test Tasker' of that Type into an array.  So the helper lists all
# four kinds in one run, each joined on the device with 'Variable Join' and PAYLOAD_JOINER -- the
# file list's own pattern, so a name with a comma in it arrives whole -- and a check that has to run
# it anyway, for a Project, takes every kind's answer from that one run.  A check with no Project in
# it asks the endpoints instead: the same arrays, one request each, and no Task run.
#

# The four kinds, in the order a prompt lists them, and the child each keeps its name in.
TASKER_OBJECT_KINDS = ("Project", "Profile", "Task", "Scene")
_NAME_TAGS = {"Project": "name", "Profile": "nme", "Task": "nme", "Scene": "nme"}
# How many names one prompt line spells out before it says 'and N more'.  A Project save sends
# every Task the Project owns, and a list of forty names is a list nobody reads.
_NAMES_SHOWN = 8


def names_in_export(xml: str | bytes) -> dict[str, list[str]]:
    """The named objects in a rendered export, by kind -- every kind present, in file order.

    Read off the document about to be sent rather than off the edit models, so what is asked
    about is exactly what the device will receive: a Project export's Tasks include the ones
    its Profiles and Scenes pull in from other Projects (see projedit.render_standalone_project_xml).
    A document that does not parse has nothing to ask about; the save itself reports that.
    """
    root = parse_tasker_xml(xml)
    return _names_by_kind(root) if root is not None else {kind: [] for kind in TASKER_OBJECT_KINDS}


def parse_tasker_xml(xml: str | bytes) -> Element | None:
    """A TaskerData document's root, or None if it does not parse."""
    try:
        return DefusedET.fromstring(xml)
    except DefusedET.ParseError:
        return None


def objects_in(root: Element) -> Iterable[tuple[str, str, str]]:
    """(kind, id, name) for every Project, Profile, Task and Scene directly under the root.

    id is "" for a Scene, which has none; name is "" for an unnamed Profile or Task.
    """
    for element in root:
        if element.tag in _NAME_TAGS:
            yield (
                element.tag,
                (element.findtext("id") or "").strip(),
                (element.findtext(_NAME_TAGS[element.tag]) or "").strip(),
            )


def _names_by_kind(root: Element) -> dict[str, list[str]]:
    """Every kind, each with its named objects in document order, once each."""
    names: dict[str, list[str]] = {kind: [] for kind in TASKER_OBJECT_KINDS}
    for kind, _object_id, name in objects_in(root):
        if name and name not in names[kind]:
            names[kind].append(name)
    return names


@dataclass(frozen=True)
class TaskerCheck:
    """What Tasker already has of an export.

    sent: the export's named objects, by kind.  present: of those, the ones Tasker reports.
    unchecked: the kinds that could not be asked about, with why -- kept apart from 'none of
    them are there', which is the opposite conclusion.
    """

    sent: dict[str, list[str]]
    present: dict[str, list[str]]
    unchecked: dict[str, str]

    @property
    def needs_prompt(self) -> bool:
        """Anything already there, or anything that could not be checked.  The second prompts
        for the reason an unreadable destination file does: 'might be there' is the user's call.
        """
        return any(self.present.values()) or bool(self.unchecked)


def check_tasker_for_existing(
    ip_address: str, ip_port: str, sent: dict[str, list[str]], state: RunState
) -> TaskerCheck:
    """Ask Tasker which of these objects it already has.  Blocking; see the section comment.

    With a Project among them, or a name the HTTP API's lookups cannot find, the helper has to run
    anyway, so that one run answers every kind -- and a run that fails leaves every kind unchecked, having been the only question asked.
    Without one, each kind is a single endpoint request, and a kind that cannot be asked is
    recorded as unchecked without stopping the others.
    """
    wanted = {kind: sent[kind] for kind in TASKER_OBJECT_KINDS if sent.get(kind)}
    if not wanted:
        return TaskerCheck(sent, {}, {})

    # The helper also answers for a name the HTTP API cannot find at all (see
    # maputil2.tasker_name_matchable) -- the endpoints would report '$New Task' missing when it is there.
    unmatchable = any(not tasker_name_matchable(name) for names in wanted.values() for name in names)
    if "Project" in wanted or unmatchable:
        return_code, message, listed = fetch_tasker_object_names(ip_address, ip_port, state=state)
        if return_code != 0:
            return TaskerCheck(sent, {}, dict.fromkeys(wanted, message))
        return TaskerCheck(sent, {kind: _found_in(names, listed[kind]) for kind, names in wanted.items()}, {})

    return_code, auth_key = auth_key_for(ip_address.strip(), ip_port.strip())
    if return_code != 0:
        return TaskerCheck(sent, {}, dict.fromkeys(wanted, str(auth_key)))

    present: dict[str, list[str]] = {}
    unchecked: dict[str, str] = {}
    endpoints = {"Profile": PROFILES_ENDPOINT, "Scene": SCENES_ENDPOINT}
    for kind, names in wanted.items():
        if kind in endpoints:
            found = verify_names_on_android(ip_address, ip_port, endpoints[kind], names, auth_key)
            if found is None:
                unchecked[kind] = f"Tasker did not answer the {kind} list request."
            else:
                present[kind] = _found_in(names, found)
            continue
        return_code, message, reported = task_names_on_device(ip_address, ip_port, names)
        if return_code != 0:
            unchecked[kind] = message
        else:
            present[kind] = _found_in(names, reported)

    return TaskerCheck(sent, present, unchecked)


def _found_in(names: list[str], reported: Iterable[str]) -> list[str]:
    """The names, in their own order, that Tasker reported."""
    have = set(reported)
    return [name for name in names if name in have]


def _quoted_names(names: list[str]) -> str:
    """'A', 'B' and 3 more -- at most _NAMES_SHOWN spelled out."""
    shown = ", ".join(f"'{name}'" for name in names[:_NAMES_SHOWN])
    hidden = len(names) - _NAMES_SHOWN
    return f"{shown} and {hidden} more" if hidden > 0 else shown


def describe_tasker_check(check: TaskerCheck) -> list[str]:
    """The prompt's lines for a check, one per kind with something to say, in kind order.

    A kind of which only some are already there also names the rest: in a Project save those
    are the new objects, which is what the user most needs to see went with it.
    """
    lines: list[str] = []
    for kind in TASKER_OBJECT_KINDS:
        if kind in check.unchecked:
            lines.append(f"Could not check which {kind}s Tasker already has: {check.unchecked[kind]}")
            continue
        present = check.present.get(kind, [])
        if not present:
            continue
        sent = check.sent.get(kind, [])
        if len(sent) == 1:
            lines.append(f"Tasker already has the {kind} {_quoted_names(present)}.")
            continue
        line = f"Tasker already has {len(present)} of the {len(sent)} {kind}s: {_quoted_names(present)}."
        missing = [name for name in sent if name not in present]
        if missing:
            line += f"  Not in Tasker yet: {_quoted_names(missing)}."
        lines.append(line)
    return lines


# ==========================================
# IDs: a fresh backup from the device, compared with what is about to be sent
# ==========================================
#
# The name check above cannot see ids -- Tasker's HTTP API does not report them -- and an id is
# where an import can go wrong without a word.  Seen on 2026-09-11: a Project went back to the
# device carrying a new Task under id 1209, the edited Tasks around it arrived, and the new one
# did not.  1209 was the loaded backup's highest id + 1, and the device had moved past that
# backup (it held Profile 1210, made after the backup was taken).
#
# The only thing on a device that states every id is a backup, so this has the device make one:
# a helper Task runs Tasker's 'Data Backup' action into a file of MapTasker's own, and this reads
# it back, compares, and deletes it.  The shape is not invented -- the old Tasker HTTP API
# project's own 'Backup' Task (task472 in this repo's sample backup) runs 'Data Backup' with a
# Path relative to the storage root, 'Tasker/backup/<timestamp>.xml', exactly as this does.
# User variables and preferences are left out (arg2 off): ids and names are all that is wanted.
#
# HELD IN MEMORY ONLY.  It is the user's whole configuration, and nothing an id check does needs
# it written to this computer or left lying on the device.
ID_CHECK_TASK_NAME = "MapTasker Backup For ID Check v1"
_ID_CHECK_BACKUP_WRITE_PATH = "Tasker/maptasker_idcheck.xml"
_ID_CHECK_BACKUP_READ_PATH = "/Tasker/maptasker_idcheck.xml"
_ID_CHECK_RESULT_WRITE_PATH = "Tasker/maptasker_idcheck.txt"
_ID_CHECK_RESULT_READ_PATH = "/Tasker/maptasker_idcheck.txt"
_ID_CHECK_PAYLOAD_HEADER = "MAPTASKER-BACKUP 1"
_DATA_BACKUP_ACTION = "322t"  # arg0 Path, arg1 Google Drive Account, arg2 Include User Vars/Prefs
# A whole configuration written to storage takes longer than one 'Test Tasker' call.
_ID_CHECK_POLL_ATTEMPTS = 30
# Tasks and Profiles draw their ids from one counter (see taskedit.next_unique_task_or_profile_id),
# so they are one space; a Project's id is a UUID of its own.
_TASK_PROFILE_IDS = "Task/Profile"


def build_id_check_task(task_name: str = ID_CHECK_TASK_NAME, *, state: RunState):
    """Build the backup-taking helper Task.  Returns an EditableTask, or an error message.

    'Data Backup' can fail (canfail), and a failed action stops the Task -- so the payload's
    terminator is written only when the backup was, and a failure reads as a timeout rather than
    as a stale backup file believed.
    """
    return build_reporting_task(
        task_name,
        ((_DATA_BACKUP_ACTION, {"0": _ID_CHECK_BACKUP_WRITE_PATH, "2": "0"}),),
        _ID_CHECK_RESULT_WRITE_PATH,
        (_ID_CHECK_PAYLOAD_HEADER,),
        state=state,
    )


def fetch_device_backup(ip_address: str, ip_port: str, state: RunState) -> tuple[int, str, bytes]:
    """Have the device back its configuration up now, and read it.  (0, "", xml) or (code, why, b"").

    Key, install the helper if missing, clear the previous run's answer, run, wait, download the
    backup, delete it from the device.  The delete happens whether or not the download worked:
    a copy of the user's configuration left behind is not something to leave to a later run.

    Blocking; a caller on the GUI thread must use run.io_bound.
    """

    ip_address = ip_address.strip()
    ip_port = ip_port.strip()
    if not ip_address or not ip_port:
        return 8, "An Android IP address and port are needed.", b""

    return_code, auth_key = auth_key_for(ip_address, ip_port)
    if return_code != 0:
        return return_code, auth_key, b""

    return_code, message = install_task_on_android(
        ip_address,
        ip_port,
        auth_key,
        ID_CHECK_TASK_NAME,
        functools.partial(build_id_check_task, state=state),
        state=state,
    )
    if return_code != 0:
        return return_code, message, b""
    auth_key = held_auth_key(ip_address, ip_port) or auth_key

    # The previous run's answer, not its backup: a stale result file is what would let this read
    # a stale backup as a fresh one, and the new backup overwrites the old file anyway.
    delete_code, delete_error = http_delete_request(ip_address, ip_port, _ID_CHECK_RESULT_READ_PATH, auth_key)
    if delete_code != 0:
        logger.info(f"Could not clear {_ID_CHECK_RESULT_READ_PATH} before the backup: {delete_error}")

    return_code, message = request_with_auth_key(
        ip_address,
        ip_port,
        lambda auth_key: run_task_on_android(ip_address, ip_port, ID_CHECK_TASK_NAME, auth_key),
    )
    auth_key = held_auth_key(ip_address, ip_port) or auth_key
    if return_code != 0:
        return return_code, message, b""

    text, error = poll_for_result(ip_address, ip_port, _ID_CHECK_RESULT_READ_PATH, _ID_CHECK_POLL_ATTEMPTS, "backup")
    if error:
        return 8, error, b""
    if not text.lstrip().startswith(_ID_CHECK_PAYLOAD_HEADER):
        return 8, "The file the Android device wrote is not a MapTasker backup result.", b""

    return_code, content = http_request(ip_address, ip_port, _ID_CHECK_BACKUP_READ_PATH, "file", "?download=1")
    delete_code, delete_error = http_delete_request(ip_address, ip_port, _ID_CHECK_BACKUP_READ_PATH, auth_key)
    if delete_code != 0:
        logger.info(f"Could not delete {_ID_CHECK_BACKUP_READ_PATH} after reading it: {delete_error}")
    if return_code != 0:
        return return_code, str(content), b""
    return 0, "", content if isinstance(content, bytes) else str(content).encode("utf-8")


@dataclass(frozen=True)
class IdFinding:
    """One object being sent whose id does not line up with the device's.

    A CLASH (device_id == object_id): the device already has that id on a different object -- a
    different name, or a different kind, since Tasks and Profiles share one counter.  A MOVE
    (device_id != object_id): nothing on the device has this id, but an object of the same kind
    and name has another one.  Scenes have no id and never appear.
    """

    kind: str
    name: str
    object_id: str
    device_kind: str
    device_name: str
    device_id: str

    @property
    def is_clash(self) -> bool:
        """The device has this very id on something else, rather than this object under another id."""
        return self.device_id == self.object_id


def compare_ids(
    export: Element,
    device: Element,
) -> list[IdFinding]:
    """Every id in the export that the device's backup disagrees with, in export order.

    The same id on an object of the same kind and name is the same object, which is the normal
    case for anything edited rather than created.  Two UNNAMED objects of one kind sharing an id
    are taken to be the same object too: there is nothing else here to tell them apart by, and
    calling every unnamed Profile a clash would bury the real ones.
    """
    holders: dict[tuple[str, str], list[tuple[str, str]]] = {}
    ids_by_name: dict[tuple[str, str], list[str]] = {}
    for kind, object_id, name in objects_in(device):
        if not object_id:
            continue
        space = kind if kind == "Project" else _TASK_PROFILE_IDS
        holders.setdefault((space, object_id), []).append((kind, name))
        if name:
            ids_by_name.setdefault((kind, name), []).append(object_id)

    findings: list[IdFinding] = []
    for kind, object_id, name in objects_in(export):
        if not object_id:
            continue
        space = kind if kind == "Project" else _TASK_PROFILE_IDS
        on_device = holders.get((space, object_id), [])
        if on_device:
            if not any(held == (kind, name) for held in on_device):
                device_kind, device_name = on_device[0]
                findings.append(IdFinding(kind, name, object_id, device_kind, device_name, object_id))
            continue
        other_ids = ids_by_name.get((kind, name), []) if name else []
        if other_ids:
            findings.append(IdFinding(kind, name, object_id, kind, name, other_ids[0]))
    return findings


def check_against_device_backup(
    ip_address: str,
    ip_port: str,
    xml: str | bytes,
    state: RunState,
) -> tuple[TaskerCheck | None, list[IdFinding], str]:
    """Both questions -- which objects Tasker has, and which ids disagree -- from one fresh backup.

    Returns (names check, id findings, "") or (None, [], why it could not be had).  The names come
    from the backup too, which answers for Projects directly, with no 'Test Tasker' helper run as
    well.  Blocking.
    """
    export = parse_tasker_xml(xml)
    if export is None:
        return TaskerCheck({kind: [] for kind in TASKER_OBJECT_KINDS}, {}, {}), [], ""

    return_code, message, device_xml = fetch_device_backup(ip_address, ip_port, state=state)
    if return_code != 0:
        return None, [], message
    device = parse_tasker_xml(device_xml)
    if device is None or device.tag != "TaskerData":
        return None, [], "The backup the Android device made could not be read."

    sent = _names_by_kind(export)
    have = {kind: set(names) for kind, names in _names_by_kind(device).items()}
    present = {kind: [name for name in names if name in have[kind]] for kind, names in sent.items() if names}
    return TaskerCheck(sent, present, {}), compare_ids(export, device), ""


def _object_label(kind: str, name: str) -> str:
    return f"{kind} '{name}'" if name else f"unnamed {kind}"


def _capped(lines: list[str], what: str) -> list[str]:
    """At most _NAMES_SHOWN lines, the rest counted rather than listed."""
    if len(lines) <= _NAMES_SHOWN:
        return lines
    return [*lines[:_NAMES_SHOWN], f"...and {len(lines) - _NAMES_SHOWN} more {what}."]


def describe_id_findings(findings: list[IdFinding]) -> list[str]:
    """The prompt's lines for an id check: clashes first, since they are the ones that lose objects,
    each group followed by one line saying what it risks.  [] when every id lines up.
    """
    clashes = [finding for finding in findings if finding.is_clash]
    moves = [finding for finding in findings if not finding.is_clash]

    lines = _capped(
        [
            f"ID {finding.object_id} of the {_object_label(finding.kind, finding.name)} being sent already belongs "
            f"to the device's {_object_label(finding.device_kind, finding.device_name)}."
            for finding in clashes
        ],
        "ID clashes",
    )
    if clashes:
        lines.append(
            "Tasker may leave out or overwrite an object sent under an ID it has already given to something else.",
        )

    lines += _capped(
        [
            f"The device has the {_object_label(finding.kind, finding.name)} under ID {finding.device_id}; "
            f"the one being sent has ID {finding.object_id}."
            for finding in moves
        ],
        "ID differences",
    )
    if moves:
        lines.append("Tasker may not treat an object sent under a different ID as the one it already has.")
    return lines
