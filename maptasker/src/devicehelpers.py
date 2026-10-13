"""devicehelpers: the helper Tasks MapTasker leaves on the device -- which are current, which are stale, and all of them in one Project."""

from __future__ import annotations

import functools
import time
import uuid
import xml.etree.ElementTree as ETW
from dataclasses import dataclass
from typing import TYPE_CHECKING

from maptasker.src import maputil2, taskedit
from maptasker.src.devicecheck import ID_CHECK_TASK_NAME, build_id_check_task, objects_in, parse_tasker_xml
from maptasker.src.devicefiles import FILE_LIST_TASK_NAME, build_file_list_task
from maptasker.src.deviceimport import IMPORT_PROFILE_TASK_NAME, build_import_profile_task
from maptasker.src.deviceinv import HELPER_TASK_NAME, build_helper_task
from maptasker.src.deviceoffer import (
    ALL_OFFER_ROUTES,
    LAUNCH_TASKER_TASK_NAME,
    OPEN_PROJECT_ROUTE,
    build_launch_tasker_task,
    stage_xml,
)
from maptasker.src.devicetask import (
    OBJECT_LIST_TASK_NAME,
    RUN_TASK_HELPER_NAME,
    build_object_list_task,
    build_run_task_helper,
    fetch_tasker_object_names,
)
from maptasker.src.deviceverify import fetch_task_names_from_device, task_names_on_device
from maptasker.src.sysconst import logger

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from xml.etree.ElementTree import Element

    from maptasker.src.primitem import RunState

# ==========================================
# The helper Tasks this program leaves on the device
# ==========================================
#
# Every helper is installed by name and never replaced: Tasker's api/import ADDS a Task whose
# name is taken rather than replacing it, so install_task_on_android installs only what is
# not already there.  That is what makes the version suffixes load-bearing -- a changed body
# needs a changed name or the old Task goes on running -- and it is also what leaves the
# previous one behind forever.  A device that has been through several MapTasker releases
# accumulates 'MapTasker Open Profile v1', 'v2', 'v3' beside the one in use.
#
# NOTHING HERE DELETES THEM, because nothing can.  The Tasker HTTP Server Example has no
# route for it: its Task endpoints are GET /api/tasks (list) and POST /api/tasks (run), and
# its only DELETE is /api/file/*, which removes a file from storage -- a helper Task is in
# Tasker's configuration, not a file.  No Tasker action deletes a Tasker object either.  So
# the honest thing this CAN do is say exactly which ones are dead, by name, so the user can
# delete them in Tasker in one pass instead of guessing.

# What every one of this program's helper Tasks is called at the front, and the only thing
# separating them from the user's own Tasks in a list of several hundred.
HELPER_TASK_PREFIX = "MapTasker "


def current_helper_builders(state: RunState) -> dict[str, Callable[[], object]]:
    """Every helper Task THIS build installs, by name, with the builder that makes it.

    The one list of helpers: current_helper_task_names reads its names off it and the
    'MapTasker' Project is built from its builders, so a helper added here is both reported
    as in use and bundled into the Project, and one left out is neither.
    """
    builders: dict[str, Callable[[], object]] = {
        route.task_name: functools.partial(route.builder, state=state) for route in ALL_OFFER_ROUTES
    }
    builders.update(
        {
            name: functools.partial(builder, state=state)
            for name, builder in {
                IMPORT_PROFILE_TASK_NAME: build_import_profile_task,
                FILE_LIST_TASK_NAME: build_file_list_task,
                OBJECT_LIST_TASK_NAME: build_object_list_task,
                ID_CHECK_TASK_NAME: build_id_check_task,
                LAUNCH_TASKER_TASK_NAME: build_launch_tasker_task,
                HELPER_TASK_NAME: build_helper_task,
                RUN_TASK_HELPER_NAME: build_run_task_helper,
            }.items()
        },
    )
    return builders


def current_helper_task_names(state: RunState) -> set[str]:
    """Every helper Task name THIS build installs -- the ones that must not be deleted.

    Derived from the routes and the standalone helpers rather than written out, because a
    hand-kept list is exactly the thing that goes stale: a version bump that updated the
    constant and not the list would report the Task now in use as dead, and the user would
    delete the working one.
    """
    return set(current_helper_builders(state=state))


def classify_helper_tasks(task_names: Iterable[str], state: RunState) -> tuple[list[str], list[str]]:
    """Split every name on the device into (this program's current helpers, its leftovers).

    Anything not starting with HELPER_TASK_PREFIX is the user's own and is not this
    program's business to have an opinion about, so it appears in neither list.

    The prototype's experiment variants ('MapTasker Import Profile v3 [Task/0]' -- see
    _import_task_name) count as current when they carry the current version, since they are
    that build's Task with one setting changed rather than an older build's.  Sorted, because
    this is read by a person working down a list in Tasker.
    """
    current = current_helper_task_names(state=state)
    ours = {name.strip() for name in task_names if name and name.strip().startswith(HELPER_TASK_PREFIX)}
    live = {name for name in ours if name in current or any(name.startswith(f"{one} [") for one in current)}
    return sorted(live), sorted(ours - live)


def stale_helper_tasks_on_device(
    ip_address: str, ip_port: str, state: RunState
) -> tuple[int, str, list[str], list[str]]:
    """(0, "", stale, current) for one device, or (return_code, message, [], []).

    The two lists together are the whole answer a user needs: which of this program's Tasks
    to delete in Tasker, and which to leave alone.  Reported rather than acted on -- see the
    section comment for why deleting them from here is not possible.
    """
    return_code, message, names = fetch_task_names_from_device(ip_address, ip_port)
    if return_code != 0:
        return return_code, message, [], []
    current, stale = classify_helper_tasks(names, state=state)
    return 0, "", stale, current


# --- Every helper in one Project, so one delete in Tasker removes them all ------------------
#
# The helpers cannot be deleted from here (see the section comment above), and api/import puts
# each one wherever Tasker puts an imported Task -- among the user's own.  What CAN be done is
# to give Tasker all of them at once as a Project named 'MapTasker'.  Once they are in it,
# deleting that one Project in Tasker removes every helper, and install_task_on_android finds
# each by name and installs nothing loose beside it.
#
# TASKER REFUSES THE WHOLE PROJECT IF IT ALREADY HAS ANY TASK IN IT.  Measured on a real device
# (2026-09-17), importing by hand from Tasker's Projects tab: a Project holding one new Task
# imported, one holding every helper the device lacked imported, and one holding a single helper
# the device already had loose -- same name, same id -- failed with 'Import failed.'  So did the
# full Project, whether its ids came from the loaded backup or from the device's own.  Two
# consequences:
#
#   - Nothing may be installed on the way.  Offering the file through the "Open with..." route
#     installs that route's helper first, and a fresh backup for the ids installs another, and
#     each is then a Task the Project carries that Tasker already has.  So the file is only
#     uploaded to /Tasker/projects, and the user imports it by hand -- which is how the working
#     imports above were done.
#   - Helpers already on the device have to go first.  They are named, and nothing is offered
#     until the device has none of them.
#
# The ids cannot come from a fresh backup (that needs a helper), so they come from the backup
# Tasker writes on its own, /Tasker/configs/user/backup.xml, and the loaded one, with the usual
# headroom past both for whatever the device has made since.
HELPER_PROJECT_NAME = "MapTasker"
# Tasker's own automatic backup: read with the plain 'file' route, which runs no Task.
_TASKER_AUTO_BACKUP_PATH = "/Tasker/configs/user/backup.xml"


def _highest_object_id(root: Element | None) -> int:
    """The highest Task or Profile id in a TaskerData document, or 0."""
    ids = [
        int(object_id)
        for kind, object_id, _name in (objects_in(root) if root is not None else ())
        if kind != "Project" and object_id.isdigit()
    ]
    return max(ids, default=0)


def _project_id(root: Element | None, project_name: str) -> str:
    """The id a Project of this name has in a TaskerData document, or ""."""
    for kind, object_id, name in objects_in(root) if root is not None else ():
        if kind == "Project" and name == project_name and object_id:
            return object_id
    return ""


def build_helper_project_xml(
    project_name: str = HELPER_PROJECT_NAME, device_xml: str | bytes = b"", *, state: RunState
) -> str:
    """Every current helper Task, inside one Project, as a standalone .prj.xml string.

    device_xml is a backup of the device the Project is for -- Tasker's automatic one -- and its
    ids are kept clear of, as the loaded configuration's are, with taskedit.NEW_OBJECT_ID_HEADROOM
    past the higher of the two.  Without one the ids come from the loaded configuration alone.

    Raises ValueError with the builder's message if any helper cannot be built -- a Project
    missing one would leave that one to be installed loose later, which is what this is for
    avoiding -- or if device_xml is not a backup that can be read.
    """
    if state.xml_root is None:
        msg = "Load a Tasker backup file first (building the helper Tasks needs it)."
        raise ValueError(msg)

    device = None
    if device_xml:
        device = parse_tasker_xml(device_xml)
        if device is None or device.tag != "TaskerData":
            msg = "The backup the Android device made could not be read."
            raise ValueError(msg)

    # Past every id loaded here and every id the device's backup holds, with the headroom
    # next_unique_task_or_profile_id leaves for objects the device made after that backup.
    next_id = max(
        taskedit.next_unique_task_or_profile_id(state=state),
        _highest_object_id(device) + taskedit.NEW_OBJECT_ID_HEADROOM + 1 if device is not None else 0,
    )

    task_elements = []
    task_ids: list[str] = []
    for name, builder in sorted(current_helper_builders(state=state).items()):
        built = builder()
        if isinstance(built, str):
            msg = f"Could not build '{name}': {built}"
            raise ValueError(msg)  # noqa: TRY004  (a builder's refusal, not a caller's wrong type)
        task_id, next_id = str(next_id), next_id + 1
        task_ids.append(task_id)
        element = built.task_element
        element.set("sr", f"task{task_id}")
        element.find("id").text = task_id
        task_elements.append(element)

    element_cls = type(state.xml_root)
    root = element_cls("TaskerData", {"sr": "", "dvi": "1", "tv": state.xml_root.attrib.get("tv", "")})
    project = element_cls("Project", {"sr": "proj0", "ve": "2"})
    now_millis = str(int(time.time() * 1000))
    for tag, text in (
        ("cdate", now_millis),
        ("id", _project_id(device, project_name) or str(uuid.uuid4())),
        ("mdate", now_millis),
        ("name", project_name),
        ("tids", ",".join(task_ids)),
    ):
        child = element_cls(tag)
        child.text = text
        project.append(child)
    # Project first, then its Tasks: the order Tasker's own single-Project export uses (see
    # projedit.render_standalone_project_xml).  There are no Profiles to go before it.
    root.append(project)
    root.extend(task_elements)

    ETW.indent(root, space="\t")
    return ETW.tostring(root, encoding="unicode") + "\n"


@dataclass(frozen=True)
class HelperProjectResult:
    """What stage_helper_project did.

    ok with a device_path: the file is on the device to be imported by hand.  already_in_project:
    every helper is in the 'MapTasker' Project already and there is nothing to do.  Not ok with
    helpers_present: the device has these helpers where the Project cannot carry them, and they
    must be deleted first -- with project_exists saying whether deleting the Project is what does
    it (None when it could not be asked).  Not ok without either: error says why.
    """

    ok: bool
    error: str = ""
    helpers_present: tuple[str, ...] = ()
    device_path: str = ""
    already_in_project: bool = False
    project_exists: bool | None = None


def _helper_project_on_device(ip_address: str, ip_port: str, state: RunState) -> bool | None:
    """Whether Tasker has a Project called 'MapTasker'.  None if it could not be asked.

    The object-listing helper answers it ('Test Tasker' with Type Projects into an array -- see
    build_object_list_task), because Tasker's HTTP API has no /api/projects.  ONLY CALLED WITH
    THAT HELPER ALREADY ON THE DEVICE, so this installs nothing: a helper installed here would
    be a Task the Project carries that Tasker already has, which is the one thing that makes the
    import fail (see the section comment).
    """
    return_code, message, listed = fetch_tasker_object_names(ip_address, ip_port, state=state)
    if return_code != 0:
        logger.info(f"Could not list the device's Projects: {message}")
        return None
    return HELPER_PROJECT_NAME in listed.get("Project", [])


def stage_helper_project(ip_address: str, ip_port: str, state: RunState) -> HelperProjectResult:
    """Put the 'MapTasker' Project in /Tasker/projects for the user to import, installing nothing.

    The exchange: ask which helpers Tasker already has (and stop if any -- see the section
    comment), ask whether the 'MapTasker' Project is there when that can be done without
    installing anything, read Tasker's automatic backup for ids to keep clear of, build the
    Project, upload it and read it back.  No helper Task is installed or run at any step, because every one
    installed would be a Task the Project carries that Tasker already has.

    Blocking; a caller on the GUI thread must use run.io_bound.
    """
    ip_address, ip_port = ip_address.strip(), ip_port.strip()
    if not ip_address or not ip_port:
        return HelperProjectResult(
            ok=False,
            error="An Android IP address and port are needed.  Set them under 'Get XML from Android Device'.",
        )

    return_code, message, present = task_names_on_device(
        ip_address, ip_port, sorted(current_helper_task_names(state=state))
    )
    if return_code != 0:
        return HelperProjectResult(ok=False, error=f"Could not read the device's Task list: {message}")
    if present:
        # Asked only when the helper that answers it is one of the ones already there, so that
        # asking cannot install anything.  It decides what the user is told to delete: the
        # Project, or the Tasks.
        project_exists = None
        if OBJECT_LIST_TASK_NAME in present:
            project_exists = _helper_project_on_device(ip_address, ip_port, state=state)
        if project_exists and set(present) == current_helper_task_names(state=state):
            return HelperProjectResult(ok=False, already_in_project=True, project_exists=True)
        return HelperProjectResult(
            ok=False,
            helpers_present=tuple(sorted(set(present))),
            project_exists=project_exists,
        )

    # Only a help: a device with no automatic backup, or one that cannot be read, still gets a
    # Project numbered past the loaded configuration.

    exists, device_xml = maputil2.read_android_file(ip_address, ip_port, _TASKER_AUTO_BACKUP_PATH)
    try:
        project_xml = build_helper_project_xml(HELPER_PROJECT_NAME, device_xml if exists else b"", state=state)
    except ValueError as error:
        if not exists:
            return HelperProjectResult(ok=False, error=str(error))
        logger.info(f"Ignoring {_TASKER_AUTO_BACKUP_PATH} for the helper Project's ids: {error}")
        try:
            project_xml = build_helper_project_xml(HELPER_PROJECT_NAME, state=state)
        except ValueError as retry_error:
            return HelperProjectResult(ok=False, error=str(retry_error))

    # OPEN_PROJECT_ROUTE for where a Project is staged and what it is called, and nothing else:
    # its helper Task is never installed or run from here.
    return_code, message = stage_xml(
        ip_address,
        ip_port,
        project_xml.encode("utf-8"),
        HELPER_PROJECT_NAME,
        OPEN_PROJECT_ROUTE,
    )
    if return_code != 0:
        return HelperProjectResult(ok=False, error=message)
    return HelperProjectResult(ok=True, device_path=message)
