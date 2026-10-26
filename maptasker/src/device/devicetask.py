"""devicetask: putting one of MapTasker's helper Tasks on the Android device, running it, and reading back what it wrote.

Every feature that works on the device (the Application inventory, the file list, importing or offering a Profile,
checking what Tasker already has) does it the same way: build a small helper Task with taskedit's Add-Task machinery,
install it if the device lacks it, run it through Tasker's HTTP server, and poll for the file it writes.  That
common part is here; what each feature builds and what it does with the answer is in its own module (deviceinv,
devicefiles, deviceimport, deviceoffer, devicecheck, deviceverify).  The helper Tasks it leaves on the device
are versioned, and devicehelpers lists them.

Anything here that talks to the device blocks until the device answers, so a caller on the GUI's event loop
must hand it to run.io_bound."""

from __future__ import annotations

import functools
import json
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from maptasker.src.core.editcommon import sanitize_filename
from maptasker.src.core.maputil2 import (
    auth_key_for,
    held_auth_key,
    http_delete_request,
    http_post_request,
    http_request,
    request_with_auth_key,
    spaced_attempts,
    tasker_name_matchable,
)
from maptasker.src.core.sysconst import logger
from maptasker.src.edit import taskedit, taskedit_apply, taskedit_save

if TYPE_CHECKING:
    from collections.abc import Callable

    from maptasker.src.core.primitem import RunState
    from maptasker.src.edit.taskedit_model import EditableTask

PAYLOAD_TERMINATOR = "MAPTASKER-END"
PAYLOAD_JOINER = "|~|"

# actionc.py keys for the three actions the helper Task is built out of, and the arguments
# each one needs set.  All three are 'addable' by taskedit's own classifier (every argument
# is an Int, a Str or a checkbox), which is what lets the Task be synthesized rather than
# shipped as a blob of XML.
# The file a helper Task is told to work on, written the way Tasker reads it: %par1, filled
# in at run time by run_task_on_android (see it for where that arrives from).  Every helper
# that handles one object's file uses this in place of a literal path, which is what lets the
# staged file carry the object's own name instead of one baked-in filename shared by every
# import.
STAGE_PATH_PARAMETER = "%par1"
VARIABLE_JOIN_ACTION = "592t"  # arg0 Name, arg1 Joiner, arg2 Delete Parts
WRITE_FILE_ACTION = "410t"  # arg0 File, arg1 Text, arg2 Append, arg3 Add Newline

# How long to wait for the helper Task to finish and its file to appear.  Three bulk
# 'List Apps' calls are seconds rather than milliseconds on a real device, and 30 seconds
# leaves room for a slow one without leaving the user staring at a spinner over a device
# that is never going to answer.  Pairing labels adds an on-device iteration per installed
# app -- a few hundred of them -- so that budget is raised rather than the fetch timing out
# on a device that is working perfectly well, just slowly.
RESULT_POLL_SECONDS = 2.0


def split_payload_section(line: str, unset_prefix: str = "%mtapps_") -> list[str]:
    """One section's joined line, back into its parts.

    Args:
        unset_prefix: what an unset variable of this section's kind is spelled with --
            '%mtapps_' for the Applications payload, '%lfp_' for the file list.

    A section whose variable was never set comes back as the literal '%mtapps_pkg' -- that
    is what Tasker writes for a variable with no value -- so a line that is just one of
    those is an empty section, not an app called '%mtapps_pkg'.  Positions are otherwise
    kept exactly as they came, blanks included: the three sections are matched up by index,
    so dropping an empty one here would shift every label after it onto the wrong app.
    """
    line = line.strip()
    if not line or line.startswith(unset_prefix):
        return []
    parts = [part.strip() for part in line.split(PAYLOAD_JOINER)]
    # One trailing empty is the append loop's signature, not an app -- see
    # _add_paired_label_actions.  Dropped here rather than there because a bulk-joined line
    # never has one, so this costs the other path nothing and keeps the two formats
    # identical (which is what makes PAIR_LABELS_ON_DEVICE reversible without a parser
    # change).  Only ONE, and only at the end: any other blank is a real position, and
    # removing it would shift every entry after it onto the wrong package.
    if parts and not parts[-1]:
        parts.pop()
    return parts


def staged_paths(location: str, object_name: str, extension: str, fallback: str) -> tuple[str, str, str]:
    """Where one object's file goes on the device: (filename, read path, absolute path).

    Three spellings of one place, because the three ends want different ones: POST /upload
    takes a folder and a filename separately, the 'file' GET route wants a path from the
    storage root, and Tasker's own actions want an absolute one (see _DEVICE_RESULT_WRITE_PATH
    for the same split).

    The name is the OBJECT'S OWN -- 'My Profile.prf.xml', not 'maptasker_import.prf.xml'.
    That is the whole point: the staged file sits in the folder the user browses, so it has
    to be the file they are looking for.  A fixed name meant a Profile that reached the
    device and could not be found there, and -- since every import wrote the same path -- a
    second import silently replacing the first one's file.  It also means that when the
    handoff to Tasker fails, what is waiting in Tasker's own import browser is a file with
    the right name on it, which is exactly how the Scene route already works.

    fallback is what an object whose name is blank falls back to; the substitution itself
    is editcommon.sanitize_filename, the same one the editors use (see it for why a name
    of nothing but illegal characters keeps them, substituted, rather than falling back).  Two names can still sanitize onto one
    path ('Wake: Up' and 'Wake_ Up'), which is the collision the file-save buttons prompt
    about; here the caller takes a safety copy instead.
    """
    filename = f"{sanitize_filename(object_name, fallback)}.{extension}"
    return filename, f"/{location}/{filename}", f"/storage/emulated/0/{location}/{filename}"


def run_task_on_android(
    ip_address: str,
    ip_port: str,
    task_name: str,
    auth_key: str,
    par1: str = "",
    par2: str = "",
    timeout: float | None = None,
    variables: dict[str, str] | None = None,
) -> tuple[int, str]:
    """Run an existing Task on the device, via the Tasker HTTP API's POST /api/tasks
    (Params/Body: task object; Response: the Task's return value).

    Returns (0, return_value) or (return_code, error_message).  return_value is what the Task
    handed back with 'Return', or "" when it set none -- see task_return_value.  The helper
    Tasks return nothing and their callers ignore it; run_task_for_result is what reads it.  Return code 9 is passed through
    unchanged so a rejected key can be told apart from everything else and replaced -- see
    maputil2.request_with_auth_key, which every run goes through.

    par1 ARRIVES IN THE TASK AS %par1, and this is not a guess -- it is read off the HTTP
    Server Example's own handler in this repo's sample backup (XML/backup.xml), the same way
    the 'Import Data' route was derived.  Profile 'POST Task' (prof1079) runs task1077,
    whose act17 is:

        code 547  'Variable Set'  %par1 = %http_request_body.par1   IF %http_request_body.par1 is set

    -- act18 does the same for %par2, and act19 is a JavaScriptlet doing setLocal() for
    every key of a 'variables' object in the body.  The Perform Task that then runs the
    named Task (act22/act25, code 130) has Local Variable Passthrough on (arg6=1) limited to
    '!%http_request*/%return/%tasks' -- everything EXCEPT those -- so %par1 is passed
    straight through to the Task being run.

    That is what makes a per-object staged path possible.  The helper Tasks used to bake
    their file path in at install time because 'POST /api/tasks carries a Task name and
    nothing else', which was simply wrong: it carries whatever the body carries.  Sent only
    when non-empty, so a Task with no path to be told about is called exactly as before.
    par2 arrives as %par2 the same way (act18).

    timeout: seconds to wait for the answer, or None for http_post_request's own.  The handler
    answers only once the Task has finished, so a Task that does real work needs longer than a
    helper that only writes a file.

    variables: local variables for the Task, by name without the '%' -- act19's JavaScriptlet
    does setLocal() for each, and the passthrough hands them on.  run_task_for_result sends the
    name of the Task its helper is to run this way.
    """

    body: dict[str, object] = {"name": task_name}
    if par1:
        body["par1"] = par1
    if par2:
        body["par2"] = par2
    if variables:
        body["variables"] = variables

    return_code, response = http_post_request(
        ip_address,
        ip_port,
        "",
        "api/tasks",
        "",
        json.dumps(body).encode("utf-8"),
        auth_key,
        content_type="application/json",
        **({} if timeout is None else {"timeout": timeout}),
    )
    if return_code != 0:
        return return_code, str(response)
    return 0, task_return_value(response)


# What the HTTP Server Example's 'POST Task' handler answers when the Task it ran set no
# return value.  Its HTTP Response body is '%return' plus a newline (task1077 act28), and it
# clears %return before the Perform Task (act20) -- so a Task that returns nothing leaves the
# variable unset, and Tasker sends an unset variable's name as its text.
_UNSET_RETURN = "%return"

# The helper that runs a Task the handler cannot find by name -- see run_task_for_result.  It
# does one 'Perform Task' of the name it is handed in %mt_run_task and hands back what that
# returned, so its own name is the only one the handler has to find.
RUN_TASK_HELPER_NAME = "MapTasker Run Task v1"
_PERFORM_TASK_ACTION = "130t"  # arg0 Name, arg1 Priority, arg4 Return Value Variable, arg6 Passthrough, arg7 Limit
_RETURN_ACTION = "126t"  # arg0 Value
_RUN_TASK_NAME_VARIABLE = "mt_run_task"  # set by the handler's JavaScriptlet, from the body's 'variables'
_RUN_TASK_RESULT_VARIABLE = "%mt_run_result"
# The helper's own variables stay behind; %par1, %par2 and the rest go on to the Task it runs.
_RUN_TASK_PASSTHROUGH_LIMIT = "!%mt_run*"

# How long a Task run for its result may take before MapTasker stops waiting.  The handler
# answers only when the Task finishes, so this is the Task's own running time plus the
# round trip -- generous, since a Task that asks the user something waits on them.
RUN_TASK_TIMEOUT_SECONDS = 60


def task_return_value(response: object) -> str:
    """The Task's return value out of a POST /api/tasks response body: "" when it set none.

    Only the one newline the handler adds is taken off, not all surrounding whitespace -- a
    Task that deliberately returns indented text or trailing spaces gets them shown.
    """
    text = response.decode("utf-8", errors="replace") if isinstance(response, bytes) else str(response or "")
    text = text.removesuffix("\n")
    # The helper's 'Return' of an unset result comes back as that variable's name, the same way.
    return "" if text.strip() in (_UNSET_RETURN, _RUN_TASK_RESULT_VARIABLE) else text


def build_run_task_helper(task_name: str = RUN_TASK_HELPER_NAME, *, state: RunState) -> EditableTask | str:
    """Build the Task that runs another Task by name and returns what it returned.

    Returns an EditableTask, or an error message string, like every other builder here.

    Its 'Perform Task' is the HTTP Server Example's own (task1077 act22), copied: priority
    %priority, a return value variable, and Local Variable Passthrough on -- which is how the
    Task it runs still gets %par1 and %par2.  A priority can only be written as a number
    through taskedit, so the %priority variable is put into the built action afterwards.
    """
    built = new_helper_task(task_name, state=state)
    if isinstance(built, str):
        return built
    edited_task, add, values = built

    error = add(
        _PERFORM_TASK_ACTION,
        {
            "0": f"%{_RUN_TASK_NAME_VARIABLE}",
            "4": _RUN_TASK_RESULT_VARIABLE,
            "6": "1",
            "7": _RUN_TASK_PASSTHROUGH_LIMIT,
        },
    ) or add(_RETURN_ACTION, {"0": _RUN_TASK_RESULT_VARIABLE})
    if error:
        return error
    finished = finish_helper_task(edited_task, task_name, values, state)
    if isinstance(finished, str):
        return finished

    priority = finished.task_element.find("Action[code='130']/Int[@sr='arg1']")
    if priority is None:
        return "The helper Task's 'Perform Task' has no Priority to set."
    priority.attrib.pop("val", None)
    var = priority.makeelement("var", {})
    var.text = "%priority"
    priority.append(var)
    return finished


def _run_timed_out(timeout: float) -> str:
    """What a run that outlasted its timeout is reported as: it may not have failed at all."""
    return (
        f"The Android device did not answer within {timeout:g} seconds.  The Task may still be running, "
        "may be waiting on something on the device, or may have stopped on an error without "
        "finishing -- check Tasker's Run Log on the device."
    )


@dataclass(frozen=True)
class TaskRunResult:
    """What running a Task on the device came to: its return value, or why there is none.

    ok is True when the device ran the Task and answered; output is then its return value
    ("" when it set none).  error says what went wrong otherwise, in words for the user.
    seconds is how long the run took, answer or not.
    """

    ok: bool
    output: str = ""
    error: str = ""
    seconds: float = 0.0


def run_task_for_result(
    ip_address: str,
    ip_port: str,
    task_name: str,
    par1: str = "",
    par2: str = "",
    timeout: float = RUN_TASK_TIMEOUT_SECONDS,
    *,
    state: RunState,
) -> TaskRunResult:
    """Run a Task that is already on the device, wait for it to finish, and report what it returned.

    The Task runs as Tasker has it, not as the loaded configuration or an open editor has it --
    edits reach the device only through Save To Android.  par1 and par2 arrive as %par1 and
    %par2 (see run_task_on_android).

    A failure is explained rather than passed on raw where the reason can be known: a run that
    outlasts the timeout may still be going on the device, and a Task the device does not have
    is answered by the handler with a bare 400 -- told apart from any other refusal by asking
    the device whether it has a Task of that name.

    A name the handler cannot find at all -- '$Taskaroo', or anything else holding a character
    it reads as a regular expression (see maputil2.tasker_name_matchable) -- is run through
    RUN_TASK_HELPER_NAME instead, whose own name it can.
    """
    ip_address, ip_port, task_name = ip_address.strip(), ip_port.strip(), task_name.strip()
    if not task_name:
        return TaskRunResult(ok=False, error="There is no Task name to run.")

    started = time.monotonic()
    if not tasker_name_matchable(task_name):
        return _run_task_through_helper(ip_address, ip_port, task_name, par1, par2, timeout, started, state=state)

    return_code, response = request_with_auth_key(
        ip_address,
        ip_port,
        lambda auth_key: run_task_on_android(ip_address, ip_port, task_name, auth_key, par1, par2, timeout),
    )
    if return_code == 0:
        return TaskRunResult(ok=True, output=str(response), seconds=time.monotonic() - started)

    message = str(response)
    if "Timeout error" in message:
        message = _run_timed_out(timeout)
    elif return_code != 9 and "Connection error" not in message:
        # The device answered, and refused.  The likeliest reason by far is that it has no such Task.
        auth_key = held_auth_key(ip_address, ip_port)
        if auth_key and not taskedit_save.verify_task_on_android(ip_address, ip_port, task_name, auth_key):
            message = (
                f"Tasker on the Android device has no Task named '{task_name}'.  "
                "Use 'Save To Android' to put it there first."
            )
    return TaskRunResult(ok=False, error=message, seconds=time.monotonic() - started)


def _run_task_through_helper(
    ip_address: str,
    ip_port: str,
    task_name: str,
    par1: str,
    par2: str,
    timeout: float,
    started: float,
    state: RunState,
) -> TaskRunResult:
    """run_task_for_result for a name the handler cannot find: check, install the helper, run it.

    Checked first, because a helper asked to run a Task that is not there stops on 'Perform Task'
    without returning anything, which would read as a run that worked.  And checked with the
    object-list helper (fetch_tasker_object_names), not the HTTP API: GET api/tasks cannot answer
    for these names even unfiltered -- its handler builds the whole list by testing each name
    against %tasks(#?~R<name>) and silently leaves out every one that fails, which these all do.
    'Test Tasker' lists names as they are.
    """

    def failed(message: str) -> TaskRunResult:
        return TaskRunResult(ok=False, error=message, seconds=time.monotonic() - started)

    return_code, message, listed = fetch_tasker_object_names(ip_address, ip_port, state=state)
    if return_code != 0:
        return failed(f"Could not check that Tasker has '{task_name}': {message}")
    if task_name not in listed.get("Task", []):
        return failed(
            f"Tasker on the Android device has no Task named '{task_name}'.  "
            "Use 'Save To Android' to put it there first."
        )

    return_code, auth_key = auth_key_for(ip_address, ip_port)
    if return_code != 0:
        return failed(auth_key)
    return_code, message = install_task_on_android(
        ip_address,
        ip_port,
        auth_key,
        RUN_TASK_HELPER_NAME,
        functools.partial(build_run_task_helper, state=state),
        state=state,
    )
    if return_code != 0:
        return failed(f"Could not install '{RUN_TASK_HELPER_NAME}', which runs this Task: {message}")

    return_code, response = request_with_auth_key(
        ip_address,
        ip_port,
        lambda key: run_task_on_android(
            ip_address,
            ip_port,
            RUN_TASK_HELPER_NAME,
            key,
            par1,
            par2,
            timeout,
            variables={_RUN_TASK_NAME_VARIABLE: task_name},
        ),
    )
    if return_code == 0:
        return TaskRunResult(ok=True, output=str(response), seconds=time.monotonic() - started)
    message = str(response)
    if "Timeout error" in message:
        message = _run_timed_out(timeout)
    return failed(message)


def confirm_task_on_android(ip_address: str, ip_port: str, task_name: str, auth_key: str, state: RunState) -> bool:
    """Whether Tasker has a Task of this name -- taskedit_save.verify_task_on_android, for any name.

    That asks GET api/tasks, whose handler reads the name as a regular expression, so a name
    maputil2.tasker_name_matchable refuses ('$Taskaroo', '... [Task/0]') is never in its answer,
    filtered or not.  Those are checked with the object-list helper Task instead: seconds rather
    than a fraction of one, but the only way Tasker reports them.  Answering False for a Task that
    is there is not harmless -- a caller that retries the import on False gets a second Task of the
    same name, because api/import adds rather than replaces (see install_task_on_android).

    Here rather than in taskedit, which deviceinv imports.  Blocking.
    """
    if tasker_name_matchable(task_name):
        return taskedit_save.verify_task_on_android(ip_address, ip_port, task_name, auth_key)

    return_code, message, listed = fetch_tasker_object_names(ip_address, ip_port, state=state)
    if return_code != 0:
        logger.info(f"Could not list Tasker's objects to confirm '{task_name}': {message}")
        return False
    return task_name in listed["Task"]


def install_task_on_android(
    ip_address: str,
    ip_port: str,
    auth_key: str,
    task_name: str,
    builder: Callable[[], EditableTask | str],
    state: RunState,
) -> tuple[int, str]:
    """Put one of MapTasker's helper Tasks on the device, if it isn't there already.

    Args:
        task_name: what the Task is called on the device, version and all.
        builder: builds it -- build_helper_task or build_file_list_task -- returning an
            EditableTask, or a string if it could not be built.

    Checked before importing rather than importing every time: Tasker's api/import does not
    replace a Task of the same name, it adds another one, so a fetch that re-imported
    unconditionally would leave a growing pile of identical Tasks in the user's
    configuration.  That is also why every helper Task name carries a version.
    """

    if confirm_task_on_android(ip_address, ip_port, task_name, auth_key, state=state):
        return 0, ""

    built = builder()
    if isinstance(built, str):
        return 8, built

    # via_file=False: a helper Task is MapTasker's own plumbing, and an ordinary import
    # leaves a .tsk.xml behind in /Tasker/tasks -- a folder the user browses for their own
    # Tasks.  'MapTasker Send Profile v1.tsk.xml' sitting in it is litter they did not ask
    # for and would have to recognize before deleting.
    return_code, result = taskedit_save.save_task_to_android(
        built, ip_address, ip_port, task_name, via_file=False, state=state
    )
    if return_code != 0:
        return return_code, str(result)

    # api/import answering 200 is not evidence Tasker committed the Task -- the same
    # reservation save_task_to_android_directory exists for.  Checked with the key the import
    # used, which is a fresh one if the device had rejected the one held.
    if not confirm_task_on_android(
        ip_address, ip_port, task_name, held_auth_key(ip_address, ip_port) or auth_key, state=state
    ):
        return 8, (
            f"'{task_name}' was sent to the device but Tasker did not report it afterwards.  "
            "Tasker 6.2 or higher is required, and Tasker must be running."
        )
    return 0, ""


def poll_for_result(
    ip_address: str,
    ip_port: str,
    read_path: str,
    attempts: int,
    subject: str,
) -> tuple[str, str]:
    """Wait for a helper Task's file to appear, whole.  Returns (text, error_message).

    Args:
        read_path: the file to wait for, spelled the way the 'file' route wants it.
        attempts: how many polls before giving up -- each one RESULT_POLL_SECONDS apart.
        subject: what the file holds, for the error messages ("application list").

    'Whole' is the reason this polls on content rather than on existence: the Task writes
    the file a line at a time, so it exists and is readable long before it is finished, and
    a read that lands in the middle of that would report a truncated list as a complete
    one.  The terminator line is what says it is done -- and it is the same terminator for
    every helper Task, which is what lets one poller serve them all.
    """

    last_error = f"The Android device did not produce {'an' if subject[0] in 'aeiou' else 'a'} {subject}."
    for _ in spaced_attempts(attempts, RESULT_POLL_SECONDS):
        return_code, response = http_request(ip_address, ip_port, read_path, "file", "?download=1")
        if return_code == 0:
            text = response.decode("utf-8", errors="replace") if isinstance(response, bytes) else str(response)
            if any(line.strip() == PAYLOAD_TERMINATOR for line in text.splitlines()):
                return text, ""
            last_error = f"The Android device's {subject} never finished being written."
        elif return_code != 6:  # 6 is 'not there yet', which is the normal case while waiting.
            last_error = str(response)

    return "", last_error


# Where the .prf.xml is staged for the helper to read.  Tasker's own Profile folder, the same
# one the offer routes stage into and the same one profedit.ANDROID_PROFILE_LOCATION writes
# to -- see PROFILE_STAGE_LOCATION's comment in the offer-routes section for the report
# behind that, which applies here exactly as it does there: a file staged in /Tasker is one
# the user cannot find in the folder they browse.  Defined at this point in the file rather
# than beside its siblings because this is the first of the two sections to need it.
PROFILE_STAGE_LOCATION = "Tasker/profiles"
# The two endpoints an import can be confirmed against.  Tasker's HTTP API reports Profiles,
# Tasks, Scenes and Globals by name; a Project has no endpoint of its own, which is why a
# Project import is confirmed through the Profiles it brings (see offer_to_tasker).
PROFILES_ENDPOINT = "api/profiles"
SCENES_ENDPOINT = "api/scenes"
# The same shape -- a JSON array of objects with a "name" -- so verify_names_on_android
# serves it too (it answers {"name":..., "running":...}; see taskedit_save.verify_task_on_android,
# which asks it the same question one name at a time).
TASKS_ENDPOINT = "api/tasks"


def new_helper_task(
    task_name: str, state: RunState
) -> tuple[EditableTask, Callable[[str, dict[str, str]], str], dict[str, str]] | str:
    """An empty Task plus the `add` helper both offer builders use.

    Returns (edited_task, add, values) or an error message string.  Synthesized out of
    taskedit's own Add-Task machinery for the reasons build_helper_task gives -- every
    action involved is one taskedit already classifies as addable, so this is the path an
    ordinary user's Add Task takes.
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

    return edited_task, add, values


def finish_helper_task(
    edited_task: EditableTask, task_name: str, values: dict[str, str], state: RunState
) -> EditableTask | str:
    """Apply the staged argument values.  Returns the EditableTask or an error message."""

    errors = taskedit_apply.apply_edits_to_task(edited_task, task_name, "100", values, state)
    return errors[0] if errors else edited_task


# The version is in the name because install_task_on_android installs by name.  This replaced
# 'MapTasker List Projects' v1 and v2, which the stale-helper report therefore lists for deletion.
OBJECT_LIST_TASK_NAME = "MapTasker List Tasker Objects v1"
_OBJECT_LIST_WRITE_PATH = "Tasker/maptasker_objects.txt"
_OBJECT_LIST_READ_PATH = "/Tasker/maptasker_objects.txt"
_OBJECT_PAYLOAD_HEADER = "MAPTASKER-OBJECTS 1"
_TEST_TASKER_ACTION = "347t"  # arg0 Type (dropdown), arg1 Data, arg2 Store Result In
# Per kind: its 'Test Tasker' Type, by the label actiont.lookup_values["347"] holds (indexes 11, 5,
# 6 and 7), the variable its array goes into, and the payload section it is written under.
_OBJECT_LISTS = (
    ("Project", "Projects", "%mtprojects", "PROJECTS"),
    ("Profile", "Profiles", "%mtprofiles", "PROFILES"),
    ("Scene", "Scenes", "%mtscenes", "SCENES"),
    ("Task", "Tasks", "%mttasks", "TASKS"),
)
# Four 'Test Tasker' calls and four joins: still quick, so the file list's short budget.
_OBJECT_LIST_POLL_ATTEMPTS = 15


def build_object_list_task(task_name: str = OBJECT_LIST_TASK_NAME, *, state: RunState) -> EditableTask | str:
    """Build the Tasker-object-listing helper Task.  Returns an EditableTask, or an error message.

    Per kind in _OBJECT_LISTS, 'Test Tasker' into that kind's array and 'Variable Join' to make it
    one line joined with PAYLOAD_JOINER; then the payload, one section per kind.  Neither action
    can fail (both are canfail False), so a device with no Scenes -- an array never set -- still
    reaches the terminator, that section holding the variable's own unexpanded name.
    """
    steps: list[tuple[str, dict[str, str]]] = []
    payload = [_OBJECT_PAYLOAD_HEADER]
    for _kind, test_type, variable, section in _OBJECT_LISTS:
        # Data (arg1) means nothing to the list types; this repo's own uses leave it blank.
        steps.append((_TEST_TASKER_ACTION, {"0": test_type, "1": "", "2": variable}))
        steps.append((VARIABLE_JOIN_ACTION, {"0": variable, "1": PAYLOAD_JOINER, "2": "0"}))
        payload += [section, variable]
    return build_reporting_task(task_name, tuple(steps), _OBJECT_LIST_WRITE_PATH, tuple(payload), state=state)


def build_reporting_task(
    task_name: str,
    steps: tuple[tuple[str, dict[str, str]], ...],
    result_write_path: str,
    payload_lines: tuple[str, ...],
    state: RunState,
) -> EditableTask | str:
    """A helper Task of its working actions followed by their payload, written a line at a time.

    Returns an EditableTask, or an error message.  The shape the Project list and the ID check
    share: each step is (action key, {arg id: value}); the payload is written after them, first
    line truncating and the rest appending, with PAYLOAD_TERMINATOR added last -- so the
    terminator lands only once the steps have finished, and a step that fails stops the Task
    before it does.  Built with taskedit's own Add-Task machinery, as build_file_list_task is.
    """

    edited_task = taskedit.create_new_task(task_name, "100", state=state)
    if isinstance(edited_task, str):
        return edited_task

    values: dict[str, str] = {}
    lines = (*payload_lines, PAYLOAD_TERMINATOR)
    writes = [
        (WRITE_FILE_ACTION, {"0": result_write_path, "1": text, "2": "0" if index == 0 else "1", "3": "1"})
        for index, text in enumerate(lines)
    ]
    for action_key, args in (*steps, *writes):
        action = taskedit.add_action_to_task(edited_task, action_key, state=state)
        if isinstance(action, list):
            return action[0] if action else f"'{action_key}' could not be added."
        for arg_id, value in args.items():
            values[taskedit_apply.arg_key(action.act_number, arg_id)] = value

    errors = taskedit_apply.apply_edits_to_task(edited_task, task_name, "100", values, state)
    if errors:
        return errors[0]
    return edited_task


def parse_object_list_payload(text: str) -> tuple[dict[str, list[str]], str]:
    """Read the object-listing Task's file back into names, by kind.

    Returns (names by kind, error_message); a non-empty error means nothing in it should be
    believed.  A kind whose array was never set reads as empty -- a device with no Scenes is
    ordinary.  But every device has at least one Project, and at least one Task (this helper is
    one), so an answer with none of either is refused as unreadable rather than read as 'Tasker
    has none', which would make every one being saved look new.

    Sections are looked for in order, each after the last, so a Project that happens to be named
    'SCENES' cannot be taken for the heading.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != _OBJECT_PAYLOAD_HEADER:
        return {}, "The file the Android device wrote is not a MapTasker object list."
    if not any(line.strip() == PAYLOAD_TERMINATOR for line in lines):
        return {}, "The Android device's object list is incomplete -- the Task may still be running."

    names: dict[str, list[str]] = {}
    start = 1
    for kind, _test_type, variable, section in _OBJECT_LISTS:
        index = next((i for i in range(start, len(lines)) if lines[i].strip() == section), None)
        if index is None or index + 1 >= len(lines):
            return {}, f"The Android device's object list has no {kind}s section."
        names[kind] = [name for name in split_payload_section(lines[index + 1], variable) if name]
        start = index + 2

    for kind in ("Project", "Task"):
        if not names[kind]:
            return {}, f"The Android device did not report any {kind}s."
    return names, ""


def fetch_tasker_object_names(ip_address: str, ip_port: str, state: RunState) -> tuple[int, str, dict[str, list[str]]]:
    """Every Project, Profile, Scene and Task Tasker has, by name.  (0, "", by kind) or (code, why, {}).

    The exchange fetch_file_list_from_device runs, for the object-listing Task: key, install if
    missing, clear the previous answer, run, wait, parse.  Nothing cached -- the answer is wanted
    right before a save, which is exactly when an old one is most likely to be wrong.

    Blocking; a caller on the GUI thread must use run.io_bound.
    """

    ip_address = ip_address.strip()
    ip_port = ip_port.strip()
    if not ip_address or not ip_port:
        return 8, "An Android IP address and port are needed.", {}

    return_code, auth_key = auth_key_for(ip_address, ip_port)
    if return_code != 0:
        return return_code, auth_key, {}

    return_code, message = install_task_on_android(
        ip_address,
        ip_port,
        auth_key,
        OBJECT_LIST_TASK_NAME,
        functools.partial(build_object_list_task, state=state),
        state=state,
    )
    if return_code != 0:
        return return_code, message, {}
    auth_key = held_auth_key(ip_address, ip_port) or auth_key

    delete_code, delete_error = http_delete_request(ip_address, ip_port, _OBJECT_LIST_READ_PATH, auth_key)
    if delete_code != 0:
        logger.info(f"Could not clear {_OBJECT_LIST_READ_PATH} before listing: {delete_error}")

    return_code, message = request_with_auth_key(
        ip_address,
        ip_port,
        lambda auth_key: run_task_on_android(ip_address, ip_port, OBJECT_LIST_TASK_NAME, auth_key),
    )
    if return_code != 0:
        return return_code, message, {}

    text, error = poll_for_result(
        ip_address,
        ip_port,
        _OBJECT_LIST_READ_PATH,
        _OBJECT_LIST_POLL_ATTEMPTS,
        "object list",
    )
    if error:
        return 8, error, {}

    names, error = parse_object_list_payload(text)
    if error:
        return 8, error, {}
    return 0, "", names
