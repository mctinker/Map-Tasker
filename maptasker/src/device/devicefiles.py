"""devicefiles: listing the XML files on the Android device, for the file picker."""

from __future__ import annotations

from typing import TYPE_CHECKING

from maptasker.src.core.maputil2 import auth_key_for, held_auth_key, http_delete_request, request_with_auth_key
from maptasker.src.core.sysconst import logger
from maptasker.src.device.devicetask import (
    PAYLOAD_JOINER,
    PAYLOAD_TERMINATOR,
    VARIABLE_JOIN_ACTION,
    WRITE_FILE_ACTION,
    install_task_on_android,
    poll_for_result,
    run_task_on_android,
    split_payload_section,
)
from maptasker.src.edit import taskedit, taskedit_apply

if TYPE_CHECKING:
    from maptasker.src.core.primitem import RunState

# ==========================================
# Listing the device's XML files
# ==========================================

# Listing the XML files on a device used to be a GET on the 'maplist' route, which is not
# part of the HTTP Server Example project at all: it is served by a separate 'MapTasker
# List' Profile the user had to find on TaskerNet, import by hand, and remember to leave
# enabled.  That was MapTasker's second manual setup step, it failed with a timeout that
# named no cause, and its Profile hardcodes port 1821 in its HTTP Request event -- so a
# device whose server runs anywhere else could not be made to work at all.
#
# The listing is done by a helper Task instead, installed, run and read back exactly the
# way the Applications fetch above does it (fetch_apps_from_device), over endpoints the
# HTTP Server Example itself provides.  Nothing has to be imported by hand, and there is
# no Profile to leave enabled.
#
# Why a Task and not a Profile: Tasker's HTTP API can import a *Task* (POST /api/import),
# and that is all it can import.  POST /api/profiles only sets the enabled/active status
# of a Profile that already exists, and the /upload route just drops a .prf.xml file on
# the device's storage without Tasker ever reading it (see profedit.save_profile_to_android,
# whose docstring is explicit about that).  So installing the old Profile automatically was
# never on the table; doing its job with a Task is.
FILE_LIST_TASK_NAME = "MapTasker List Files v1"
# The directory listed, and the one the Task is BUILT with -- Tasker's 'List Files' takes
# its path as an argument, so the path is baked into the Task at install time rather than
# passed per run (POST /api/tasks carries a task name, and nothing else).  The Task is
# installed once and left there, so changing this means bumping the version in
# FILE_LIST_TASK_NAME, the same contract HELPER_TASK_NAME documents.  Every caller asks for
# this one directory (see get_list_of_files).
FILE_LIST_DIRECTORY = "/storage/emulated/0/Tasker"
# Where the helper writes its answer and where this reads it back -- the same file spelled
# the two ways each end wants it, for the reason _DEVICE_RESULT_WRITE_PATH explains.
_FILE_LIST_WRITE_PATH = "Tasker/maptasker_files.txt"
_FILE_LIST_READ_PATH = "/Tasker/maptasker_files.txt"

# The payload, in the same shape as the Applications one -- header, section name, the
# section on one line, terminator -- so poll_for_result's terminator check and
# split_payload_section serve both.  Its own header, though: reading one as the other
# would be a silent misparse rather than an error.
_FILE_PAYLOAD_HEADER = "MAPTASKER-FILES 1"
_PAYLOAD_FILES = "FILES"

# 'List Files' (actionc '446t', "Get Files/Folders Properties") and the arguments it needs.
# arg0 is its Output Variables bundle, which the synthesizer fills in on its own.
_LIST_FILES_ACTION = "446t"  # arg1 Path, arg2 Type, arg3 Name/Path Filter, arg4 Other
#                              Filters, arg5 Recurse, arg6 Sort
_LIST_FILES_TYPE = "Files"  # Files, not folders.
_LIST_FILES_MATCH = "*xml"  # What MapTasker can actually open.
_LIST_FILES_OTHER = "NotEmpty"  # A zero-byte .xml is nothing anyone wants offered.
# Recurse, because the XML lives in Tasker's subdirectories (configs/user, tasks,
# profiles, scenes), not in the directory itself.
_LIST_FILES_RECURSE = "1"
# 'List Files' answers into a fixed set of %lfp_* array variables rather than into a
# 'Store Result In' of our choosing -- see the Output Variables the action declares.  The
# full paths are the only one of them this needs.
_FILE_PATHS_VARIABLE = "%lfp_full_path"
# What Tasker writes for that variable when the listing found nothing: an unset variable
# comes out as its own name.  Passed to split_payload_section so an empty listing reads
# as empty rather than as one file called '%lfp_full_path'.
_LIST_FILES_UNSET_PREFIX = "%lfp_"

# One 'List Files' call over a directory of XML is quick -- nothing like the per-app
# iteration the Applications fetch can do -- so the shorter of the two budgets is plenty.
_FILE_LIST_POLL_ATTEMPTS = 15


def build_file_list_task(
    task_name: str = FILE_LIST_TASK_NAME, directory: str = FILE_LIST_DIRECTORY, *, state: RunState
):
    """Build the file-listing helper Task.  Returns an EditableTask, or an error message.

    Three actions: 'List Files' over `directory`, 'Variable Join' to collapse the array of
    paths it produces into one string, and 'Write File' to put that where the 'file' route
    can read it.  Synthesized out of taskedit's own Add-Task machinery for the reasons
    build_helper_task gives -- all three are actions taskedit already classifies as
    addable, so this is the path an ordinary user's Add Task takes.

    The old 'MapTasker List' Profile merged the paths with a per-file count and joined
    them with commas, which left get_list_of_files chopping three characters off
    the end of every entry and splitting on a character that can legitimately appear in a
    file name.  This writes the paths and nothing else, joined with PAYLOAD_JOINER.
    """

    edited_task = taskedit.create_new_task(task_name, "100", state=state)
    if isinstance(edited_task, str):
        return edited_task

    values: dict[str, str] = {}

    def add(action_key: str, args: dict[str, str]) -> str:
        action = taskedit.add_action_to_task(edited_task, action_key, state=state)
        if isinstance(action, list):
            return action[0] if action else f"'{action_key}' could not be added."
        for arg_id, value in args.items():
            values[taskedit_apply.arg_key(action.act_number, arg_id)] = value
        return ""

    error = add(
        _LIST_FILES_ACTION,
        {
            "1": directory,
            "2": _LIST_FILES_TYPE,
            "3": _LIST_FILES_MATCH,
            "4": _LIST_FILES_OTHER,
            "5": _LIST_FILES_RECURSE,
        },
    )
    if error:
        return error

    error = add(VARIABLE_JOIN_ACTION, {"0": _FILE_PATHS_VARIABLE, "1": PAYLOAD_JOINER, "2": "0"})
    if error:
        return error

    # The first write truncates and the rest append, so a re-run replaces the previous
    # answer rather than growing it -- and the terminator only lands once the paths are
    # already on disk, which is what makes poll_for_result's check mean something.
    payload_lines = (_FILE_PAYLOAD_HEADER, _PAYLOAD_FILES, _FILE_PATHS_VARIABLE, PAYLOAD_TERMINATOR)
    for index, text in enumerate(payload_lines):
        error = add(
            WRITE_FILE_ACTION,
            {"0": _FILE_LIST_WRITE_PATH, "1": text, "2": "0" if index == 0 else "1", "3": "1"},
        )
        if error:
            return error

    errors = taskedit_apply.apply_edits_to_task(edited_task, task_name, "100", values, state)
    if errors:
        return errors[0]
    return edited_task


def parse_file_list_payload(text: str) -> tuple[list[str], str]:
    """Read the file-listing Task's file back into a list of paths.

    Returns (paths, error_message); a non-empty error means the payload was not one this
    understands and nothing should be believed from it.  The paths come back exactly as
    Tasker reported them -- absolute, storage root and all -- since it is the caller that
    knows how it wants them spelled (see get_list_of_files).
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FILE_PAYLOAD_HEADER:
        return [], "The file the Android device wrote is not a MapTasker file list."
    if not any(line.strip() == PAYLOAD_TERMINATOR for line in lines):
        return [], "The Android device's file list is incomplete -- the Task may still be running."

    paths: list[str] = []
    for index, line in enumerate(lines):
        if line.strip() == _PAYLOAD_FILES and index + 1 < len(lines):
            paths = split_payload_section(lines[index + 1], _LIST_FILES_UNSET_PREFIX)
            break

    paths = [path for path in paths if path]
    if not paths:
        return [], f"No XML files were found on the Android device under {FILE_LIST_DIRECTORY}."
    return paths, ""


def fetch_file_list_from_device(
    ip_address: str, ip_port: str, directory: str = FILE_LIST_DIRECTORY, *, state: RunState
) -> tuple[int, list[str] | str]:
    """Fetch the list of XML files on an Android device.

    The same exchange fetch_apps_from_device runs, for a different Task: get an API key,
    install the Task if it isn't there, delete any previous answer, run it, wait for the
    file, read it, parse it.  Nothing is cached -- a file list goes stale the moment the
    user saves a backup, and it costs one Task run to ask again.

    Returns (0, paths) or (return_code, error_message) -- the same two-shaped answer
    get_list_of_files has always handed its own callers.

    Requires the Tasker HTTP Server Example project running on the device and Tasker 6.2
    or higher.  It does NOT require the 'MapTasker List' Profile, which is the point.

    Blocking, deliberately: it sleeps between polls.  Callers on the GUI thread must hand
    it to run.io_bound, as userintr_android.validate_or_filelist_xml's own caller does.
    """

    ip_address = ip_address.strip()
    ip_port = ip_port.strip()
    if not ip_address or not ip_port:
        return 8, "An Android IP address and port are needed.  Set them under 'Get XML from Android Device'."

    return_code, auth_key = auth_key_for(ip_address, ip_port)
    if return_code != 0:
        return return_code, auth_key

    return_code, message = install_task_on_android(
        ip_address,
        ip_port,
        auth_key,
        FILE_LIST_TASK_NAME,
        lambda: build_file_list_task(FILE_LIST_TASK_NAME, directory, state=state),
        state=state,
    )
    if return_code != 0:
        return return_code, message
    auth_key = held_auth_key(ip_address, ip_port) or auth_key

    # Clear the previous answer BEFORE running anything: a listing is asked for repeatedly
    # within one session, so a stale file here is the normal case rather than the rare one,
    # and reading one would report the files as they were several backups ago.  A failed
    # delete is not fatal -- poll_for_result's terminator check is the second line of
    # defence -- for the reasons the Applications fetch gives.
    delete_code, delete_error = http_delete_request(ip_address, ip_port, _FILE_LIST_READ_PATH, auth_key)
    if delete_code != 0:
        logger.info(f"Could not clear {_FILE_LIST_READ_PATH} before listing: {delete_error}")

    return_code, message = request_with_auth_key(
        ip_address,
        ip_port,
        lambda auth_key: run_task_on_android(ip_address, ip_port, FILE_LIST_TASK_NAME, auth_key),
    )
    if return_code != 0:
        return return_code, message

    text, error = poll_for_result(
        ip_address,
        ip_port,
        _FILE_LIST_READ_PATH,
        _FILE_LIST_POLL_ATTEMPTS,
        "file list",
    )
    if error:
        return 8, error

    paths, error = parse_file_list_payload(text)
    if error:
        return 8, error
    return 0, paths


# List the XML files on the Android device
def get_list_of_files(ip_address: str, ip_port: str, file_location: str, state: RunState) -> tuple:
    """Get the list of XML files on an Android device.

    Args:
        ip_address: the device's TCP/IP address.
        ip_port: the port its Tasker HTTP server is listening on.
        file_location: the directory to list.

    Returns:
        tuple: (0, list of file paths) or (return_code, error message).

    The listing is done by a helper Task MapTasker installs on the device itself -- see
    fetch_file_list_from_device.  It used to be a GET on the 'maplist' route,
    which is served by the separate 'MapTasker List' TaskerNet Profile that the user had
    to import by hand and keep enabled; that Profile is no longer needed for anything.

    The old route answered with each path glued to that path's file count and the whole
    lot joined by commas, which is why this used to chop three characters off the end of
    every entry and split on a character that can appear in a file name.  The helper Task
    writes the paths and nothing else, so neither is necessary any more.

    Blocking -- the helper Task takes a moment to run and this waits for its answer -- so
    callers on the GUI thread must go through run.io_bound (userintr_android.validate_or_filelist_xml does).
    """
    return_code, result = fetch_file_list_from_device(ip_address, ip_port, file_location, state=state)
    if return_code != 0:
        return return_code, result

    # Paths come back absolute, as Tasker reported them.  The 'file' route is rooted at the
    # storage root, so that prefix has to come off before any of these can be fetched --
    # and Tasker's own trash is full of XML nobody wants offered.
    final_list = [path.replace("/storage/emulated/0", "") for path in result if ".Trash" not in path]
    if not final_list:
        return 8, f"Only trashed XML files were found on the Android device under {file_location}."
    return 0, final_list
