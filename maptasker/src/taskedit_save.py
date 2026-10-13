"""taskedit_save: getting an edited or new Task out -- as a standalone .tsk.xml, onto the Android device, or into the loaded tree -- and deleting one."""

from __future__ import annotations

import copy
import json
import xml.etree.ElementTree as ETW
from typing import TYPE_CHECKING

from maptasker.src import editcommon, piiscan, sessundo
from maptasker.src.editcommon import set_child_text as _set_child_text
from maptasker.src.editcommon import touch_project_mdate
from maptasker.src.maputil2 import (
    LIST_READ_TIMEOUT_SECONDS,
    http_post_request,
    http_request,
    request_with_auth_key,
    tasker_name_query,
)
from maptasker.src.presave import backup_local_file
from maptasker.src.taskedit import project_task_ids, resolve_task_by_name

if TYPE_CHECKING:
    from maptasker.src.primitem import RunState
    from maptasker.src.taskedit_model import EditableTask

# Destination folder on the Android device for Save To Android's file write -- the Task
# sibling of profedit.ANDROID_PROFILE_LOCATION ("Tasker/profiles") and
# sceneedit.ANDROID_SCENE_LOCATION ("Tasker/scenes"); see android_task_path.
ANDROID_TASK_LOCATION = "Tasker/tasks"
# What this editor's exports need that the other three's don't -- see editcommon.EditorKind.
EXPORT = editcommon.EditorKind(
    fallback="task",
    extension=".tsk.xml",
    android_location=ANDROID_TASK_LOCATION,
)


def sanitize_filename(name: str) -> str:
    """Strip characters illegal in filenames from a Task name, falling back to "task"."""
    return EXPORT.sanitize_filename(name)


def default_save_path(task_name: str, state: RunState) -> str:
    """Default standalone-export path: {output folder}/{sanitized name}.tsk.xml."""
    return EXPORT.default_save_path(task_name, state)


def android_task_path(task_name: str) -> str:
    """The absolute path a Save To Android of this Task writes to on the device.

    See EditorKind.android_path for the sanitized-name collision the overwrite prompt
    this feeds exists to catch (two Tasks named 'Wake: Up' and 'Wake_ Up' land on one
    path).
    """
    return EXPORT.android_path(task_name)


def save_path_exists(output_path: str) -> bool:
    """Whether a file already sits at this save path (would be silently overwritten)."""
    return editcommon.save_path_exists(output_path)


def render_standalone_task_xml(edited_task: EditableTask, state: RunState, *, redact: bool = False) -> str:
    """Render the edited Task as a standalone TaskerData/Task XML string, matching
    Tasker's own single-task export/import format. Shared by write_standalone_task_xml
    (local file) and save_task_to_android (posted to the Android device).

    `redact` runs the export through piiscan first, replacing the API keys, tokens,
    passwords, phone numbers, email addresses and coordinates in it with markers and
    writing a comment above the file saying what went -- what "Redact secrets" on the
    export button does.  Off by default, so nothing that already calls this changes.
    """
    tv = state.xml_root.attrib.get("tv", "") if state.xml_root is not None else ""
    task_copy = copy.deepcopy(edited_task.task_element)
    # The parsed tree's Element class isn't necessarily xml.etree.ElementTree's own
    # C-accelerated Element (defusedxml's hardened XMLParser forces the pure-Python
    # implementation) -- ET.Element()/.append() enforce an exact type match, so build
    # the wrapper using the same class the parsed elements actually are.
    root = type(task_copy)("TaskerData", {"sr": "", "dvi": "1", "tv": tv})
    root.append(task_copy)
    # Redacting happens HERE, on the tree that is about to be serialized, rather than at
    # the button that asked for it: this is the one line every export of this kind passes
    # through, so an export path added later cannot quietly skip it.  See piiscan.
    notice = piiscan.redact_rendered(root) if redact else ""

    ETW.indent(root, space="\t")

    # No <?xml ...?> declaration -- see profedit.render_standalone_profile_xml.
    return notice + ETW.tostring(root, encoding="unicode") + "\n"


def write_standalone_task_xml(
    edited_task: EditableTask, output_path: str, state: RunState, *, redact: bool = False
) -> str:
    """Write the edited Task as a standalone TaskerData/Task XML file, matching
    Tasker's own single-task export/import format. Raises OSError on failure.

    A safety copy of anything already at `output_path` is taken first, into a
    MapTasker_Backups folder beside it -- see presave.backup_local_file.  Taken here
    rather than at the buttons that call this, so no export path can be added later that
    quietly skips it.  Returns the copy's path, or "" if there was nothing to copy or the
    copy failed (which does not stop the write -- see presave's module comment).

    `redact` is passed straight through to the render (see it for what goes).  Only the
    local exports offer it: "Save To Android" puts the configuration back on the user's own
    device, where the keys in it are the keys it needs to work, and a redacted upload would
    be an import that silently stopped functioning.
    """
    _, safety_copy = backup_local_file(output_path)
    with open(output_path, "w", encoding="utf-8") as out_file:
        out_file.write(render_standalone_task_xml(edited_task, redact=redact, state=state))
    return safety_copy


def save_task_to_android(
    edited_task: EditableTask, ip_address: str, ip_port: str, task_name: str, via_file: bool = True, *, state: RunState
) -> tuple[int, str]:
    """Import the edited Task into Tasker on the Android device, from a copy of it left in
    /Tasker/tasks.

    TWO STEPS, IN THIS ORDER, and the order is the point:

        1. the Task is written to /Tasker/tasks/<name>.tsk.xml and read back
           (_put_task_file_on_android -- the same write 'Save As File' does)
        2. what came back off the device is POSTed to api/import

    So the import sources from the file in that folder rather than from a render that only
    ever existed in this process, and an import always leaves the .tsk.xml behind -- the
    device keeps a copy of exactly what was imported, which is the artifact anyone would
    reach for to repeat it, inspect it or hand it to Tasker again by hand.

    It also means a write that cannot be confirmed stops the import: with no verified file
    in the folder there is nothing to import FROM, and importing the in-memory render at
    that point would be quietly importing something other than what this says it imports.

    via_file=False skips step 1 and posts the render straight to api/import.  It exists for
    ONE caller -- devicetask.install_task_on_android, putting MapTasker's own helper Tasks on
    the device.  Those are plumbing: the user did not ask for them, would not recognize them,
    and /Tasker/tasks is a folder they browse.  Filling it with 'MapTasker Send Profile
    v1.tsk.xml' would be leaving MapTasker's tools among the user's own work.

    api/import is the only documented way into Tasker's live configuration over HTTP and it
    is Task-only -- api/tasks runs a Task that already exists, and /api/file and /upload put
    bytes on the storage without Tasker ever reading them.  Every request to it must carry
    an 'Authorization: <key>' header; /upload, in step 1, needs none.

    The key is the one held for this device this session (maputil2.auth_key_for), so a device
    already asked -- by an earlier save, a fetch or an import -- is not prompted again.  If the
    device rejects it (401), a fresh key is fetched and the import tried once more; the held key
    may have expired or been revoked on the device.

    Returns (0, task_name) on success, or (return_code, error_message).
    """

    ip_address = ip_address.strip()
    ip_port = ip_port.strip()
    if not ip_address or not ip_port:
        return 8, "Android IP address and port are required."

    # Step 1, before the key: /upload needs no authorization, so a failed write costs the
    # user nothing and -- more to the point -- does not put an authorization prompt on their
    # phone for an import that was never going to happen.
    if via_file:
        return_code, result, xml_bytes = _put_task_file_on_android(
            edited_task, ip_address, ip_port, task_name, state=state
        )
        if return_code != 0:
            return return_code, result
    else:
        xml_bytes = render_standalone_task_xml(edited_task, state=state).encode("utf-8")

    # Step 2: the bytes that came off the device, not a fresh render of the same Task.  The key
    # is the one held for this device, asked for only if there is none, and a key the device
    # rejects is replaced and the import tried once more (maputil2.request_with_auth_key).
    return_code, response = request_with_auth_key(
        ip_address,
        ip_port,
        lambda auth_key: http_post_request(ip_address, ip_port, "", "api/import", "", xml_bytes, auth_key),
    )
    if return_code != 0:
        return return_code, str(response)
    return 0, task_name


def _put_task_file_on_android(
    edited_task: EditableTask,
    ip_address: str,
    ip_port: str,
    task_name: str,
    state: RunState,
) -> tuple[int, str, bytes]:
    """Write the Task to /Tasker/tasks and hand back WHAT THE DEVICE NOW HOLDS.

    Returns (0, device_file_path, bytes_read_back_from_the_device) or
    (return_code, error_message, b"").

    The third value is the point of this being one step rather than two.  Both callers want
    it and they want it for different reasons: the file write compares it to what it sent
    (the only way to know the write landed -- /upload answers 200 even for a bogus location,
    creates missing folders silently and never reports failure at the HTTP layer), and the
    import posts it, so what reaches Tasker is provably the file in the folder rather than a
    second render of the same Task that nothing has checked.

    One read serves both.  Reading it twice would leave the verified bytes and the imported
    bytes as separate facts about the device, which is exactly the gap where they could
    differ.

    The write and the readback are EditorKind.upload_and_verify, shared with the other
    three editors -- this is the one caller that keeps the third value it hands back.
    """
    return EXPORT.upload_and_verify(
        ip_address,
        ip_port,
        task_name,
        lambda: render_standalone_task_xml(edited_task, state=state).encode("utf-8"),
    )


def save_task_to_android_file(
    edited_task: EditableTask,
    ip_address: str,
    ip_port: str,
    task_name: str,
    state: RunState,
) -> tuple[int, str]:
    """Writes the edited Task, rendered as standalone XML, onto the Android device's storage
    under /Tasker/tasks, via the Tasker HTTP Server Example's POST /upload endpoint (see
    maputil2.http_upload_request).  Mirrors profedit.save_profile_to_android exactly.

    THIS IS NOT AN IMPORT: nothing reaches Tasker's live configuration, Tasker does not watch
    this directory, and the file simply sits there for the user or their own device-side
    automation to pick up.  It also needs no authorization -- /upload takes no Authorization
    header, so unlike the api/import route there is no key to cache and no prompt on the
    device.  save_task_to_android does this write too, and then imports what it wrote.

    Returns (0, device_file_path) on success, or (return_code, error_message).
    """
    return_code, result, _bytes_on_device = _put_task_file_on_android(
        edited_task, ip_address, ip_port, task_name, state=state
    )
    return return_code, result


def verify_task_on_android(ip_address: str, ip_port: str, task_name: str, auth_key: str) -> bool:
    """Confirms the Task actually landed in Tasker after a save_task_to_android
    import, via the Tasker HTTP API's GET /api/tasks?name=<task_name> (Response:
    task objects -- a JSON array of {"name": ..., "running": ...}, filtered to
    Tasks matching the given name). api/import's own 200 response doesn't
    guarantee Tasker committed the Task, so this re-checks by name -- see
    save_task_to_android_directory for the fallback when this fails.

    Returns True if the GET succeeded and returned at least one Task named
    task_name, False otherwise.
    """
    # A name the filter cannot carry (see maputil2.tasker_name_query) is looked for in the
    # whole list, which the device takes seconds to produce.
    query = tasker_name_query([task_name])
    return_code, response = http_request(
        ip_address.strip(),
        ip_port.strip(),
        "",
        "api/tasks",
        query or "",
        auth_key,
        **({} if query else {"timeout": LIST_READ_TIMEOUT_SECONDS}),
    )
    if return_code != 0:
        return False

    try:
        tasks = json.loads(response)
        if not tasks:
            return False
    except (ValueError, TypeError):
        return False

    return any(task.get("name") == task_name for task in tasks)


def save_task_to_android_directory(
    edited_task: EditableTask,
    ip_address: str,
    ip_port: str,
    task_name: str,
    auth_key: str = "",
) -> tuple[int, str]:
    """Fallback for save_task_to_android when verify_task_on_android can't confirm
    the import landed in Tasker: retries the POST /api/import once more, rather
    than falling back to a different endpoint. api/import is the only documented
    way to actually get a Task into Tasker over HTTP -- /api/file and /upload put
    bytes on the storage that Tasker never reads -- so a second attempt at the
    real thing is the only fallback that can plausibly help, e.g. if the first
    POST/GET-verify pair hit a transient network blip.

    The name is finally accurate: this re-reads /Tasker/tasks/<name>.tsk.xml, which
    save_task_to_android has already written and verified by this point, and posts THAT.
    Nothing is uploaded again -- the file is known good, and re-rendering the Task here
    would make the retry a different request from the one being retried.

    Returns (0, task_name) on success, or (return_code, error_message).
    """

    ip_address = ip_address.strip()
    ip_port = ip_port.strip()
    device_path = android_task_path(task_name)

    read_code, xml_bytes = http_request(ip_address, ip_port, device_path, "file", "")
    if read_code != 0 or not isinstance(xml_bytes, bytes) or not xml_bytes:
        return 8, f"Could not read {device_path} back from the device to retry the import."

    # file_location is "" so this reproduces save_task_to_android's request byte for byte
    # -- a retry that posted to a different URL would not be testing the same thing.
    # It used to pass "/Tasker/tasks/<name>.tsk.xml" here, left over from when this
    # function tried to write a file; http_post_request appends that to the endpoint, so
    # the "retry" actually POSTed to /api/import/Tasker/tasks/<name>.tsk.xml, which Tasker
    # has no route for -- meaning this fallback could never have succeeded.
    return_code, response = http_post_request(
        ip_address,
        ip_port,
        "",
        "api/import",
        "",
        xml_bytes,
        auth_key,
    )
    if return_code != 0:
        return return_code, str(response)
    return 0, task_name


def register_new_task(edited_task: EditableTask, task_name: str, state: RunState) -> None:
    """Adds a new Task to the in-memory backup's Task tables (all_tasks,
    all_tasks_by_name) so it behaves like any other Task loaded from the backup --
    e.g. so it shows up in the Edit Task picker (guiutils.py reads
    all_tasks_by_name for that list) and so a second Add Task with the same name
    is caught by task_name_exists(). Call once: right after the standalone
    .tsk.xml write succeeds (see userintr_editors.save_new_task_event), for a
    keep-without-saving-to-disk Ok without one (see userintr_editors.keep_new_task_event),
    or after a successful Save To Android import (see
    userintr_android.save_task_to_android_event's is_new_task branch).
    """
    with sessundo.undoable(f"Add Task '{task_name}'", state=state):
        state.tasker_root_elements["all_tasks"][edited_task.task_id] = {
            "xml": edited_task.task_element,
            "name": task_name,
        }
        state.tasker_root_elements["all_tasks_by_name"][task_name] = {
            "xml": edited_task.task_element,
            "id": edited_task.task_id,
        }


def apply_edited_task_to_live_tree(edited_task: EditableTask, state: RunState) -> None:
    """Writes an edited (pre-existing) Task's changes back into the in-memory
    backup's Task tables (all_tasks, all_tasks_by_name) so views generated from
    them -- Map, Diagram, Tree -- reflect the edit right away instead of the
    Task's original, unedited content. load_task_for_edit/apply_edits_to_task
    only ever mutate a deep copy (never PrimeItems.xml_root or these tables
    directly -- see load_task_for_edit), so without this, Save only ever produces
    a standalone file and the rest of the app keeps showing the old version.

    Same all_tasks[id]["xml"]-swap approach as register_new_task, so it's
    consistent with however that Task already got into the tables; the actual
    XML tree's document structure (e.g. which Project/Profile a live Task
    element sits under) doesn't need touching since every view reads Task
    content through these tables, not by re-walking the tree for it.

    No-op if the Task's id isn't registered yet (e.g. a brand-new Task from Add
    Task, saved via Save To Android before ever reaching register_new_task) --
    call once, right after a successful Save (local or to Android).
    """
    with sessundo.undoable(
        f"Edit Task '{edited_task.task_element.findtext('nme', '') or edited_task.task_id}'", state=state
    ):
        all_tasks = state.tasker_root_elements["all_tasks"]
        entry = all_tasks.get(edited_task.task_id)
        if entry is None:
            return

        old_name = entry["name"]
        new_name = edited_task.task_element.findtext("nme", "") or old_name

        all_tasks[edited_task.task_id] = {"xml": edited_task.task_element, "name": new_name}

        all_tasks_by_name = state.tasker_root_elements["all_tasks_by_name"]
        if old_name in all_tasks_by_name and old_name != new_name:
            del all_tasks_by_name[old_name]
        all_tasks_by_name[new_name] = {"xml": edited_task.task_element, "id": edited_task.task_id}


def delete_task(task_name: str, state: RunState) -> list[str]:
    """Deletes a Task and every reference to it. Returns [] on success, else a
    list of error strings (mirrors profedit.delete_profile/projedit.delete_project's
    convention), mutating nothing on error.

    Three things have to happen together, or the backup is left inconsistent:
    drop the Task from both lookup tables (all_tasks is keyed by id,
    all_tasks_by_name by name -- see register_new_task, which populates both),
    unlink it from every Project's <tids>, and unlink it from any Profile that
    names it as its Entry/Exit Task.

    The <tids> half is what actually removes it from the Map/Diagram/Tree views
    and the "Tasks not in any Profile" listing, none of which read the lookup
    tables to find a Project's Tasks -- they walk <tids> (see
    profedit.add_task_to_project, the mirror image of this, and
    projects.do_tasks_in_project). Every Project is scanned rather than assuming
    a single owner: nothing in the format prevents two Projects from listing the
    same Task id, and a leftover id would make the Task appear to still exist in
    whichever view walked that Project.

    The <mid0>/<mid1> half matters for the same reason unlink_task_from_profile
    exists, plus one of its own: ids are handed out as max-in-use + 1 (see
    next_unique_task_or_profile_id), so deleting the highest-numbered Task frees
    its id for the next Add Task -- a Profile still holding the old id would then
    silently point at a completely unrelated new Task. Only the reference is
    removed; the Profile itself is kept (deleting Profiles is Edit Profile's job).

    Tasks referenced by *name* from another Task's "Perform Task" action are
    deliberately not rewritten -- that's a plain string argument the user may
    well want to repoint at a replacement Task, and silently editing other Tasks'
    actions here would be a much wider mutation than "delete this Task".
    """
    with sessundo.undoable(f"Delete Task '{task_name}'", state=state):
        resolved = resolve_task_by_name(task_name, state=state)
        if resolved is None:
            return [f"Task '{task_name}' no longer exists."]
        task_id, _ = resolved

        for project_entry in state.tasker_root_elements.get("all_projects", {}).values():
            project_element = project_entry["xml"]
            existing_ids = project_task_ids(project_element)
            if task_id not in existing_ids:
                continue
            _set_child_text(project_element, "tids", ",".join(i for i in existing_ids if i != task_id))
            touch_project_mdate(project_element)

        for profile_entry in state.tasker_root_elements.get("all_profiles", {}).values():
            profile_element = profile_entry["xml"]
            for child in [c for c in profile_element if "mid" in c.tag and c.text == task_id]:
                profile_element.remove(child)

        state.tasker_root_elements.get("all_tasks", {}).pop(task_id, None)
        state.tasker_root_elements.get("all_tasks_by_name", {}).pop(task_name, None)
        return []
