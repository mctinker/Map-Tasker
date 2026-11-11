"""compat: which of a configuration's actions and features break on which Tasker versions."""

#! /usr/bin/env python3

#                                                                                        #
# compat: the Compatibility Check.                                                       #
#                                                                                        #
# A backup records the Tasker that wrote it (the tv= on <TaskerData>), and Tasker is not   #
# kind about a backup from a newer one: an action it has never heard of is dropped or      #
# refused, and one that still exists may no longer do what it did.  Moving a Project to a   #
# friend, restoring last year's backup onto a new phone, or finally updating are all the    #
# same question: WHAT IN THIS FILE DOES NOT SURVIVE THE TRIP?                              #
#                                                                                        #
# The answer comes from a curated table, compat.json, built from Tasker's own release notes   #
# and the author's [dev] beta posts: for each action, event and state the version that         #
# introduced it and the Android it needs;                                                      #
# for each release the removals, renames and behaviour changes that can break a configuration #
# written before it.  This reads the loaded configuration for what it uses, and sets the       #
# table against two versions -- the one the file was written by and the one you are going to.  #
#                                                                                        #
# WHAT IT FINDS, by the tag each finding carries:                                           #
#                                                                                        #
#   NEWER-TASKER  uses something introduced after the target release: it will not work there.   #
#   NEWER-ANDROID uses something the target Android is too old for, or the target Tasker is.    #
#   REMOVED       something the target release no longer has (or has renamed).                 #
#   CHANGED       a behaviour that differs between the two versions, and so can change what     #
#                 the configuration does.  Both directions: moving to a newer Tasker, the       #
#                 changes since the file was written; moving to an older one, the changes the   #
#                 file may have been written to rely on.                                        #
#   GENERAL       changes that touch everything rather than an action, such as the Android API   #
#                 level Tasker targets.                                                         #
#                                                                                        #
# WHAT IT CANNOT DO, said plainly because "nothing found" gets trusted:                    #
#                                                                                        #
#   * It is a floor.  The table holds what the release notes and beta posts list as new,        #
#     removed or changed and that a backup can show; an option added to an action that already   #
#     existed is not there, since a backup cannot tell which Tasker an option needed.          #
#   * A version is the first the author announced the item in.  Where no beta post says so, it    #
#     is the release notes' first release, which may be later than a beta that had it.          #
#   * A plugin's own requirements are the plugin's business and are not in the file.            #
#   * It reads action codes.  An action MapTasker has no code for is in the table for reference  #
#     only, and cannot be found in a file.                                                   #
#                                                                                        #
# Read-only: nothing here changes the configuration.                                       #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import cache
from typing import TYPE_CHECKING, Any

from maptasker.src.core import clock
from maptasker.src.core.mapjump import SCENE, Row, Target, text_report
from maptasker.src.core.maputils import append_to_filename
from maptasker.src.core.outdir import output_path
from maptasker.src.core.sysconst import COMPAT_FILE, logger
from maptasker.src.mapops.maprefac_model import actions_of, object_table, profile_target, task_target
from maptasker.src.mapops.readiness import version_key

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from maptasker.src.core.primitem import RunState

TABLE_FILE = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "json", "compat.json"),
)

# The tags a finding carries.  Stable and un-translated, for the reason healthck's are.
NEWER_TASKER = "NEWER-TASKER"
NEWER_ANDROID = "NEWER-ANDROID"
REMOVED = "REMOVED"
CHANGED = "CHANGED"
GENERAL = "GENERAL"

# How many of the places something is used a line names before it says "and N more".
PLACES_SHOWN = 6

# What each Android API level is called.
ANDROID_NAMES = {
    19: "4.4",
    21: "5.0",
    22: "5.1",
    23: "6.0",
    24: "7.0",
    25: "7.1",
    26: "8.0",
    27: "8.1",
    28: "9",
    29: "10",
    30: "11",
    31: "12",
    32: "12L",
    33: "13",
    34: "14",
    35: "15",
    36: "16",
    37: "17",
}

# The suffix a Profile's condition tag gives the key.
_CONDITION_SUFFIX = {"Event": "e", "State": "s"}


# ##################################################################################
# The table.
# ##################################################################################


@dataclass(frozen=True)
class Release:
    """One Tasker release the notes cover."""

    version: str
    date: str  # "" where the notes give none
    min_android: int  # the lowest Android API level Tasker itself runs on from here; 0 = not stated
    beta: bool = False  # a version only a beta post announced, not one of the release notes' releases


@dataclass(frozen=True)
class Item:
    """An action, event or state, and the release that introduced it."""

    key: str  # Tasker code + t, e or s; "" when MapTasker has no code for it
    kind: str  # action, event or state
    name: str
    since: str  # the first version the author announced it in: a beta post, or else the release notes
    android: int  # lowest Android API level it works on; 0 = not stated
    note: str
    released: str = ""  # the release the notes put it in, when a beta had it earlier; "" otherwise
    post: str = ""  # the [dev] post that announced it, when one did


@dataclass(frozen=True)
class Change:
    """A release that removed, renamed or changed something."""

    release: str
    kind: str  # removed, renamed or changed
    text: str
    keys: tuple[str, ...]  # what it affects; () = everything
    named: tuple[str, ...]  # the same, by name, for the reader


@cache
def _table() -> dict[str, Any]:
    """compat.json, read the first time it is wanted."""
    with open(TABLE_FILE, encoding="utf-8") as file:
        return json.load(file)


def releases() -> list[Release]:
    """Every release in the table, oldest first."""
    return [
        Release(row["version"], row["date"], row["min_android"], row.get("beta", False)) for row in _table()["releases"]
    ]


def items() -> list[Item]:
    """Every action, event and state in the table, oldest first."""
    return [
        Item(
            row["key"],
            row["kind"],
            row["name"],
            row["since"],
            row["android"],
            row["note"],
            row.get("released", ""),
            row.get("post", ""),
        )
        for row in _table()["items"]
    ]


def changes() -> list[Change]:
    """Every removal, rename and change in the table, oldest first."""
    return [
        Change(row["release"], row["kind"], row["text"], tuple(row["keys"]), tuple(row["named"]))
        for row in _table()["changes"]
    ]


def target_api_bumps() -> list[tuple[str, int]]:
    """(release, Android API level) for each release that raised the level Tasker targets."""
    return [(row["release"], row["api"]) for row in _table()["target_api"]]


def android_name(api: int) -> str:
    """'Android 13' for 33; the level itself when it has no name here."""
    return f"Android {ANDROID_NAMES[api]}" if api in ANDROID_NAMES else f"Android API {api}"


# ##################################################################################
# What the configuration uses.
# ##################################################################################


def _scan(state: RunState) -> dict[str, list[Target]]:
    """{key: every place the loaded configuration uses it} for the keys the table knows."""
    wanted = {item.key for item in items() if item.key} | {key for change in changes() for key in change.keys}
    found: dict[str, list[Target]] = {}

    def note(element: Element, suffix: str, place: Target) -> None:
        key = f"{(element.findtext('code') or '').strip()}{suffix}"
        if key in wanted:
            found.setdefault(key, []).append(place)

    for task_id, entry in object_table("all_tasks", state=state).items():
        place = task_target(task_id, state=state)
        for number, action in enumerate(actions_of(entry["xml"]), start=1):
            note(action, "t", place.at_action(number))
    for profile_id, entry in object_table("all_profiles", state=state).items():
        place = profile_target(profile_id, state=state)
        for condition in entry["xml"]:
            if condition.tag in _CONDITION_SUFFIX:
                note(condition, _CONDITION_SUFFIX[condition.tag], place)
    for scene_name, entry in object_table("all_scenes", state=state).items():
        place = Target(SCENE, scene_name, scene_name)
        for action in entry["xml"].iter("Action"):
            note(action, "t", place)
    return found


# ##################################################################################
# The check.
# ##################################################################################


@dataclass(frozen=True)
class Finding:
    """One thing in the configuration that does not survive the trip, or may not."""

    tag: str
    release: str  # the release it is about; "" for none
    text: str
    places: tuple[Target, ...] = ()


@dataclass
class Compatibility:
    """What the check found for one pair of versions."""

    written_by: str  # the Tasker the file says wrote it, or ""
    target: str
    target_android: int  # 0 = not asked
    findings: list[Finding] = field(default_factory=list[Finding])
    # Changes that touch everything rather than anything the file uses: worth knowing, and not something the file did.
    notes: list[Finding] = field(default_factory=list[Finding])
    # The newest release among the items the table knows the release of, and what they are: how new a Tasker the file needs.
    minimum: str = ""
    minimum_names: tuple[str, ...] = ()
    items_used: int = 0

    @property
    def is_clean(self) -> bool:
        """Whether nothing in the file was found.  The notes are not about the file, so they do not count."""
        return not self.findings


def written_by(state: RunState) -> str:
    """The Tasker that wrote the loaded backup, or "" when it does not say or nothing is loaded."""
    if not state.backup_loaded:
        return ""
    return str(state.xml_root.attrib.get("tv", "")).strip()


def _label(item: Item) -> str:
    """'Action Set Device Effects' -- an item as a sentence names it."""
    return f"{item.kind.capitalize()} {item.name}"


def _new_in(item: Item) -> str:
    """'Action Java Code is new in Tasker 6.6.4 (a beta; released in 6.6.18).' -- when it came in, and when it was released."""
    earlier = f" (a beta; released in {item.released})" if item.released else ""
    return f"{_label(item)} is new in Tasker {item.since}{earlier}."


def _newer_tasker(used: dict[str, list[Target]], target: str) -> tuple[list[Finding], str, tuple[str, ...], int]:
    """What the file uses that the target release does not have, and how new a Tasker the file needs overall."""
    findings: list[Finding] = []
    newest = ""
    names: list[str] = []
    count = 0
    for item in items():
        if not item.key or item.key not in used:
            continue
        count += 1
        if not newest or version_key(item.since) > version_key(newest):
            newest, names = item.since, []
        if item.since == newest:
            names.append(_label(item))
        if version_key(item.since) > version_key(target):
            findings.append(
                Finding(NEWER_TASKER, item.since, _new_in(item), tuple(used[item.key])),
            )
    findings.sort(key=lambda each: version_key(each.release), reverse=True)
    return findings, newest, tuple(names), count


def _android(used: dict[str, list[Target]], target: str, target_android: int) -> list[Finding]:
    """What the target Android is too old for: Tasker itself, then the items."""
    if not target_android:
        return []
    findings = [
        Finding(
            NEWER_ANDROID,
            release.version,
            f"Tasker {release.version} needs {android_name(release.min_android)} or later.",
        )
        for release in releases()
        if release.version == target and release.min_android > target_android
    ]
    findings.extend(
        Finding(
            NEWER_ANDROID,
            item.since,
            f"{_label(item)} needs {android_name(item.android)} or later.",
            tuple(used[item.key]),
        )
        for item in items()
        if item.key in used and item.android > target_android
    )
    return findings


def _changed(used: dict[str, list[Target]], source: str, target: str) -> list[Finding]:
    """What changed between the two versions that this file uses, and what changed for everything."""
    if not source or version_key(source) == version_key(target):
        return []
    upgrading = version_key(target) > version_key(source)
    low, high = sorted((version_key(source), version_key(target)))
    findings: list[Finding] = []
    for change in changes():
        if not low < version_key(change.release) <= high:
            continue
        if not upgrading and change.kind != "changed":
            continue  # An older Tasker still has what a newer one removed or renamed.
        places = tuple(place for key in change.keys for place in used.get(key, ()))
        if change.keys and not places:
            continue
        tag = GENERAL if not change.keys else (CHANGED if change.kind == "changed" else REMOVED)
        prefix = "" if upgrading else "Written for the newer behaviour: "
        findings.append(Finding(tag, change.release, f"{prefix}{change.text}", places))
    if upgrading:
        findings.extend(
            Finding(GENERAL, release, f"Tasker now targets {android_name(api)}, so background behaviour may differ.")
            for release, api in target_api_bumps()
            if low < version_key(release) <= high
        )
    findings.sort(key=lambda each: version_key(each.release))
    return findings


def check(state: RunState, target: str, target_android: int = 0) -> Compatibility:
    """Set the loaded configuration against a target Tasker release (and, if asked, a target Android).

    Safe with nothing loaded: there is nothing used, so there is nothing found.
    """
    source = written_by(state)
    used = _scan(state) if state.backup_loaded else {}
    result = Compatibility(written_by=source, target=target, target_android=target_android)
    newer, result.minimum, result.minimum_names, result.items_used = _newer_tasker(used, target)
    everything = [*newer, *_android(used, target, target_android), *_changed(used, source, target)]
    result.findings = [finding for finding in everything if finding.tag != GENERAL]
    result.notes = [finding for finding in everything if finding.tag == GENERAL]
    return result


# ##################################################################################
# The table as a reference, and the check as a report.
# ##################################################################################


@dataclass(frozen=True)
class TableRow:
    """One line of the reference table."""

    release: str
    what: str  # New, Removed, Renamed or Changed
    name: str
    note: str
    used: int | None  # how many places the loaded file uses it; None when it cannot be told
    source: str = ""  # the [dev] post that announced it, when one did


def table(state: RunState) -> list[TableRow]:
    """Every item and change in the table, newest release first, with how much of it the loaded file uses."""
    used = _scan(state) if state.backup_loaded else {}
    loaded = state.backup_loaded
    rows: list[TableRow] = []
    for item in items():
        android = f"  (needs {android_name(item.android)})" if item.android else ""
        earlier = f"  (first in a beta; released in {item.released})" if item.released else ""
        count = len(used.get(item.key, ())) if loaded and item.key else None
        rows.append(TableRow(item.since, "New", _label(item), f"{item.note}{android}{earlier}", count, item.post))
    for change in changes():
        count = sum(len(used.get(key, ())) for key in change.keys) if loaded and change.keys else None
        named = ", ".join(change.named) if change.named else "Everything"
        rows.append(TableRow(change.release, change.kind.capitalize(), named, change.text, count))
    return sorted(rows, key=lambda row: version_key(row.release), reverse=True)


def _places_row(places: tuple[Target, ...]) -> list[Row]:
    """The places a finding is about, each a click into the Map, up to PLACES_SHOWN of them."""
    rows = [Row(f"      {place.label}", place) for place in places[:PLACES_SHOWN]]
    if len(places) > PLACES_SHOWN:
        rows.append(Row(f"      ... and {len(places) - PLACES_SHOWN} more"))
    return rows


def _finding_rows(heading: str, findings: list[Finding]) -> list[Row]:
    """A heading with a count, then each finding with its release and the places it is."""
    rows = [Row(f"{heading} ({len(findings)})")]
    for finding in findings:
        release = f"[{finding.release}] " if finding.release else ""
        rows.append(Row(f"  {finding.tag}  {release}{finding.text}"))
        rows.extend(_places_row(finding.places))
    return rows


def report_rows(result: Compatibility) -> list[Row]:
    """The result as a report: what the file is, what was asked, then each finding with where it is."""
    android = f", {android_name(result.target_android)}" if result.target_android else ""
    rows = [
        Row("COMPATIBILITY CHECK"),
        Row(
            f"Written by Tasker {result.written_by}"
            if result.written_by
            else "The file does not say which Tasker wrote it."
        ),
        Row(f"Checked against Tasker {result.target}{android}"),
    ]
    rows.append(
        Row(
            f"It uses {result.items_used} of the {sum(1 for item in items() if item.key)} actions, events and states the table can find."
        )
    )
    if result.minimum:
        rows.append(
            Row(f"It uses things that need at least Tasker {result.minimum}: {', '.join(result.minimum_names[:4])}.")
        )
    rows.append(Row(""))
    if result.is_clean:
        rows.append(Row("Nothing in this file is known to break on that version."))
    else:
        rows.extend(_finding_rows("FOUND", result.findings))
    if result.notes:
        rows.append(Row(""))
        rows.extend(_finding_rows("TRUE OF EVERYTHING, WHATEVER THE FILE USES", result.notes))
    return rows


def write_report(rows: list[Row], state: RunState) -> str:
    """Save the report as text, the way the other reports are saved.  Returns the file's path, or "" if it could not be."""
    stamp = clock.now().strftime("_%m-%d-%Y_%H-%M-%S")
    file_name = append_to_filename(COMPAT_FILE, stamp)
    if not file_name:
        return ""
    file_path = output_path(file_name, state=state)
    try:
        with open(file_path, "w", encoding="utf-8") as output_file:
            output_file.write(text_report(rows))
    except OSError as error:
        logger.error(f"The compatibility report could not be written: {error}")
        return ""
    return file_path
