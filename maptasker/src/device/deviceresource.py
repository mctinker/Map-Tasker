"""deviceresource: asking the Android device whether the files, apps and Scenes a configuration names are there."""

#! /usr/bin/env python3

#                                                                                        #
# deviceresource: the phone's half of the Missing Resources check.                        #
#                                                                                        #
# resrefs reads the configuration for what it refers to; this asks the phone about each,   #
# over the connection every other device feature uses, and hands the answers to resstore.  #
# Three questions, three ways of asking:                                                  #
#                                                                                        #
#   PATHS    a helper Task, 'MapTasker Check Paths v1', reads a file of paths MapTasker      #
#            uploads, asks Tasker's own 'Test File' (Exists) about each, and writes the     #
#            answers back in the same order.  A helper Task is the way this program asks   #
#            the phone anything that is not an API endpoint (see deviceinv, devicefiles),   #
#            and 'Test File' is Tasker's own definition of "there" -- relative paths,       #
#            /sdcard and the rest are resolved exactly as the action that uses the path      #
#            would resolve them.                                                          #
#                                                                                        #
#            The paths travel in a FILE, not baked into the Task.  A helper Task is          #
#            installed once and left there (install_task_on_android does not replace one),   #
#            so a Task with this configuration's paths inside it would be the wrong Task      #
#            for the next configuration.  The Task is the same for everyone; the question    #
#            changes.                                                                       #
#                                                                                        #
#   APPS     the list of installed packages (deviceinv.fetch_apps_from_device), which is    #
#            also what the plugin check reads, so one fetch serves both.                     #
#                                                                                        #
#   SCENES   Tasker's own list of its Scenes (devicetask.fetch_tasker_object_names).         #
#                                                                                        #
# Each question is asked separately and a failure of one does not discard the others: a      #
# phone that answers about files and refuses the app fetch has still said which files are    #
# missing.  What it said is kept (resstore), and the failures come back as messages.        #
#                                                                                        #
# Blocking throughout -- the helper Task takes a moment and this waits for its file -- so    #
# a caller on the GUI thread must go through run.io_bound.                                 #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
from __future__ import annotations

import functools
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from maptasker.src.analysis import resrefs
from maptasker.src.core import appinv, resstore
from maptasker.src.core.maputil2 import (
    auth_key_for,
    device_address,
    held_auth_key,
    http_delete_request,
    http_upload_request,
    request_with_auth_key,
)
from maptasker.src.core.sysconst import logger
from maptasker.src.device import deviceinv
from maptasker.src.device.devicetask import (
    PAYLOAD_JOINER,
    PAYLOAD_TERMINATOR,
    WRITE_FILE_ACTION,
    fetch_tasker_object_names,
    install_task_on_android,
    poll_for_result,
    run_task_on_android,
    split_payload_section,
)
from maptasker.src.edit import taskedit, taskedit_apply

if TYPE_CHECKING:
    from maptasker.src.core.primitem import RunState
    from maptasker.src.edit.taskedit_model import EditableTask

# The helper Task.  Versioned because it is installed once and left on the device (see
# install_task_on_android): a different shape gets a different name.
CHECK_TASK_NAME = "MapTasker Check Paths v1"

# Where the question goes and where the answer comes from -- each spelled the way its end wants it (see
# deviceinv._DEVICE_RESULT_WRITE_PATH).  The upload takes a folder and a filename; Tasker's actions take a path
# from the storage root; the 'file' route wants a leading slash.
_UPLOAD_FOLDER = "Tasker"
_UPLOAD_FILE = "maptasker_check_in.txt"
_TASK_READ_PATH = f"{_UPLOAD_FOLDER}/{_UPLOAD_FILE}"
_RESULT_WRITE_PATH = "Tasker/maptasker_check_out.txt"
_RESULT_READ_PATH = "/Tasker/maptasker_check_out.txt"

_PAYLOAD_HEADER = "MAPTASKER-EXISTS 1"
_PAYLOAD_RESULTS = "RESULTS"

# 'Read File' (417), 'Variable Split' (590), 'Variable Set' (547), 'For' (39), 'End For' (40) and 'Test File'
# (342), and the arguments each is given.
_READ_FILE_ACTION = "417t"  # arg0 File, arg1 To Var
_SPLIT_ACTION = "590t"  # arg0 Name, arg1 Splitter, arg2 Delete Base
_SET_ACTION = "547t"  # arg0 Name, arg1 To, arg4 Append
_FOR_ACTION = "39t"  # arg0 Variable, arg1 Items, arg2 Structure Output
_END_FOR_ACTION = "40t"
_TEST_FILE_ACTION = "342t"  # arg0 Type, arg1 Data, arg2 Store Result In
# The option of Test File's Type dropdown that asks whether the path exists (actiont.lookup_values["342"]).
_TEST_FILE_EXISTS = "Exists"

# Named for MapTasker so a helper Task running on someone's device cannot collide with a variable of their own.
# Lower case, so Tasker scopes them to one run of the Task and nothing survives into the next.
_IN_VARIABLE = "%mtres_in"
_OUT_VARIABLE = "%mtres_out"
_PATH_VARIABLE = "%mtres_path"
_ANSWER_VARIABLE = "%mtres_ok"
_UNSET_PREFIX = "%mtres_"
# What _ANSWER_VARIABLE holds if Test File never gets to set it, so a failed test reads as "unknown" and not as
# the variable's own name.
_UNKNOWN = "unknown"

# A path takes a moment to test; a thousand take a few seconds.  The poll budget is generous so a busy phone is
# waited for rather than blamed.
_POLL_ATTEMPTS = 30


def build_check_task(task_name: str = CHECK_TASK_NAME, *, state: RunState) -> EditableTask | str:
    """Build the helper Task, out of taskedit's own Add-Task machinery.  An EditableTask, or an error message.

    Read the paths, split them into an array, and for each one ask 'Test File' whether it exists and append the
    answer, joined with PAYLOAD_JOINER, to one line; then write that line out under a header and a terminator
    the way every other helper Task writes its answer, so poll_for_result serves it.

    The answer for each path is appended WITH a trailing joiner (Tasker has no append-with-separator), which
    leaves one empty part at the end that split_payload_section drops.
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

    steps = [
        lambda: add(_READ_FILE_ACTION, {"0": _TASK_READ_PATH, "1": _IN_VARIABLE}),
        lambda: add(_SPLIT_ACTION, {"0": _IN_VARIABLE, "1": PAYLOAD_JOINER, "2": "0", "3": "0"}),
        lambda: add(_SET_ACTION, {"0": _OUT_VARIABLE, "1": "", "4": "0"}),
        lambda: add(_FOR_ACTION, {"0": _PATH_VARIABLE, "1": f"{_IN_VARIABLE}()", "2": "0"}),
        lambda: add(_SET_ACTION, {"0": _ANSWER_VARIABLE, "1": _UNKNOWN, "4": "0"}),
        lambda: add(
            _TEST_FILE_ACTION,
            # Use Global Namespace on, as the Test File actions in real backups have it: the path is then looked
            # up in the phone's shared storage, which is where the actions that use it look.
            {"0": _TEST_FILE_EXISTS, "1": _PATH_VARIABLE, "2": _ANSWER_VARIABLE, "4": "1"},
        ),
        lambda: add(_SET_ACTION, {"0": _OUT_VARIABLE, "1": f"{_ANSWER_VARIABLE}{PAYLOAD_JOINER}", "4": "1"}),
        lambda: add(_END_FOR_ACTION, {}),
    ]
    payload_lines = (_PAYLOAD_HEADER, _PAYLOAD_RESULTS, _OUT_VARIABLE, PAYLOAD_TERMINATOR)
    steps.extend(
        lambda index=index, text=text: add(
            WRITE_FILE_ACTION,
            {"0": _RESULT_WRITE_PATH, "1": text, "2": "0" if index == 0 else "1", "3": "1"},
        )
        for index, text in enumerate(payload_lines)
    )

    for step in steps:
        error = step()
        if error:
            return error

    errors: list[str] = taskedit_apply.apply_edits_to_task(edited_task, task_name, "100", values, state)
    if errors:
        return errors[0]
    return edited_task


def parse_check_payload(text: str, paths: list[str]) -> tuple[dict[str, bool | None], str]:
    """Read the helper Task's answer back: {path: whether it exists, or None if Tasker could not say}.

    Returns (answers, error_message); a non-empty error means the file was not one this understands and nothing
    should be believed from it.  The answers are matched to the paths BY POSITION, so a list of a different
    length is refused rather than zipped -- an answer attached to the wrong path looks exactly like a right one.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != _PAYLOAD_HEADER:
        return {}, "The file the Android device wrote is not a MapTasker path check."
    if not any(line.strip() == PAYLOAD_TERMINATOR for line in lines):
        return {}, "The Android device's path check is incomplete -- the Task may still be running."

    answers: list[str] = []
    for index, line in enumerate(lines):
        if line.strip() == _PAYLOAD_RESULTS and index + 1 < len(lines):
            answers = split_payload_section(lines[index + 1], _UNSET_PREFIX)
            break
    if len(answers) != len(paths):
        return {}, (
            f"The Android device answered {len(answers)} of the {len(paths)} paths it was asked about, so none "
            f"of its answers can be matched to a path."
        )
    meaning = {"true": True, "false": False}
    return {path: meaning.get(answer.strip().lower()) for path, answer in zip(paths, answers, strict=True)}, ""


def check_paths_on_device(
    ip_address: str,
    ip_port: str,
    paths: list[str],
    *,
    state: RunState,
) -> tuple[int, dict[str, bool | None] | str]:
    """Ask the device which of these paths exist.  (0, {path: answer}) or (return_code, error_message).

    The exchange the Applications fetch runs, for a different Task: get an API key, install the Task if it is not
    there, upload the paths, clear the previous answer, run, wait, read, parse.  Nothing is cached -- the answer
    is wanted now.  Each path is asked once, however many places use it.
    """
    wanted = list(dict.fromkeys(paths))
    if not wanted:
        return 0, {}

    return_code, auth_key = auth_key_for(ip_address, ip_port)
    if return_code != 0:
        return return_code, auth_key

    return_code, message = install_task_on_android(
        ip_address,
        ip_port,
        auth_key,
        CHECK_TASK_NAME,
        functools.partial(build_check_task, state=state),
        state=state,
    )
    if return_code != 0:
        return return_code, message
    auth_key = held_auth_key(ip_address, ip_port) or auth_key

    # Uploaded before the answer is cleared and the Task run: the Task reads this file the moment it starts.
    return_code, message = http_upload_request(
        ip_address, ip_port, _UPLOAD_FOLDER, _UPLOAD_FILE, PAYLOAD_JOINER.join(wanted).encode("utf-8")
    )
    if return_code != 0:
        return return_code, message

    # Clear the previous answer first, for the reason fetch_apps_from_device gives: a stale file would be read
    # back and believed.  Its own failure is not fatal -- the terminator check is the second line of defence.
    delete_code, delete_error = http_delete_request(ip_address, ip_port, _RESULT_READ_PATH, auth_key)
    if delete_code != 0:
        logger.info(f"Could not clear {_RESULT_READ_PATH} before checking: {delete_error}")

    return_code, message = request_with_auth_key(
        ip_address,
        ip_port,
        lambda key: run_task_on_android(ip_address, ip_port, CHECK_TASK_NAME, key),
    )
    if return_code != 0:
        return return_code, str(message)

    text, error = poll_for_result(ip_address, ip_port, _RESULT_READ_PATH, _POLL_ATTEMPTS, "path check")
    if error:
        return 8, error
    answers, error = parse_check_payload(text, wanted)
    if error:
        return 8, error
    return 0, answers


@dataclass
class Outcome:
    """What a check asked, what it was told, and what went wrong on the way."""

    device: str
    asked: int = 0
    answered: int = 0
    missing: int = 0
    errors: list[str] = field(default_factory=list[str])
    could_not_save: str = ""


def _ask_paths(
    ip_address: str,
    ip_port: str,
    questions: list[resstore.Question],
    known: dict[resstore.Question, bool],
    outcome: Outcome,
    *,
    state: RunState,
) -> None:
    """Fold the device's answer about the paths into `known`, or its failure into the outcome."""
    paths = [value for kind, value in questions if kind == resrefs.ASK_PATH]
    if not paths:
        return
    return_code, result = check_paths_on_device(ip_address, ip_port, paths, state=state)
    if return_code != 0 or isinstance(result, str):
        outcome.errors.append(f"Files and folders: {result}")
        return
    for path, present in result.items():
        if present is not None:
            known[(resrefs.ASK_PATH, path)] = present


def _ask_apps(
    ip_address: str,
    ip_port: str,
    questions: list[resstore.Question],
    known: dict[resstore.Question, bool],
    outcome: Outcome,
    *,
    refresh: bool,
    state: RunState,
) -> None:
    """Answer the app questions from the device's installed packages, fetching them first if asked to."""
    wanted = [value for kind, value in questions if kind == resrefs.ASK_APP]
    if not wanted:
        return
    if refresh:
        return_code, message = deviceinv.fetch_apps_from_device(ip_address, ip_port, state=state)
        if return_code != 0:
            outcome.errors.append(f"Apps: {message}")
            return
    fetched = appinv.fetched_packages().get(device_address(ip_address, ip_port))
    if fetched is None:
        outcome.errors.append("Apps: no list of this device's apps has been fetched yet.")
        return
    for package in wanted:
        known[(resrefs.ASK_APP, package)] = package in fetched[1]


def _ask_scenes(
    ip_address: str,
    ip_port: str,
    questions: list[resstore.Question],
    known: dict[resstore.Question, bool],
    outcome: Outcome,
    *,
    state: RunState,
) -> None:
    """Answer the Scene questions from the Scenes Tasker reports having."""
    wanted = [value for kind, value in questions if kind == resrefs.ASK_SCENE]
    if not wanted:
        return
    return_code, message, listed = fetch_tasker_object_names(ip_address, ip_port, state=state)
    if return_code != 0:
        outcome.errors.append(f"Scenes: {message}")
        return
    on_device = set(listed.get("Scene", []))
    for name in wanted:
        known[(resrefs.ASK_SCENE, name)] = name in on_device


def check_device(
    ip_address: str,
    ip_port: str,
    references: resrefs.References,
    *,
    refresh_apps: bool = True,
    state: RunState,
) -> Outcome:
    """Ask the device about everything the configuration refers to, and keep what it says.

    Each kind of question is asked separately, and what is answered is kept even if another kind failed.
    Nothing is kept when nothing was answered, so a phone that could not be reached does not replace the last
    good answers with an empty set.  `refresh_apps` fetches the installed apps first; without it the list
    fetched earlier is used, which is quicker and as old as that fetch.
    """
    ip_address, ip_port = ip_address.strip(), ip_port.strip()
    outcome = Outcome(device=device_address(ip_address, ip_port))
    questions = list(references.questions())
    outcome.asked = len(questions)
    if not ip_address or not ip_port:
        outcome.errors.append("An Android IP address and port are needed.")
        return outcome

    known: dict[resstore.Question, bool] = {}
    _ask_paths(ip_address, ip_port, questions, known, outcome, state=state)
    _ask_apps(ip_address, ip_port, questions, known, outcome, refresh=refresh_apps, state=state)
    _ask_scenes(ip_address, ip_port, questions, known, outcome, state=state)

    outcome.answered = len(known)
    outcome.missing = sum(1 for present in known.values() if not present)
    if known:
        outcome.could_not_save = resstore.store(outcome.device, known)
    return outcome
