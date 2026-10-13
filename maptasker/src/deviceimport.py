"""deviceimport: importing a Profile into Tasker's live configuration, headlessly, through Import Data."""

from __future__ import annotations

from typing import TYPE_CHECKING

from maptasker.src import maputil2, taskedit, taskedit_apply
from maptasker.src.actiont import lookup_values
from maptasker.src.devicetask import (
    PAYLOAD_TERMINATOR,
    PROFILE_STAGE_LOCATION,
    STAGE_PATH_PARAMETER,
    WRITE_FILE_ACTION,
    install_task_on_android,
    poll_for_result,
    run_task_on_android,
    staged_paths,
)
from maptasker.src.deviceverify import verify_profile_on_android
from maptasker.src.maputil2 import (
    auth_key_for,
    device_address,
    held_auth_key,
    http_delete_request,
    request_with_auth_key,
)
from maptasker.src.sysconst import logger

if TYPE_CHECKING:
    from maptasker.src.primitem import RunState

# ==========================================
# Importing a Profile into Tasker's live configuration
# ==========================================
#
# PROTOTYPE.  The central question it exists to answer is not answered yet, and the wrong
# answer destroys a configuration.  Read this before pointing it at a device you care about.
#
# Tasker's HTTP API cannot import a Profile.  POST /api/import takes a Task and nothing
# else, POST /api/profiles only flips enabled/active on a Profile that already exists, and
# /upload drops a .prf.xml on storage that Tasker never reads (see
# profedit.save_profile_to_android, whose docstring is explicit about it).  That is where
# 'Save Profile To Android' has stopped.
#
# But /api/import is not a Tasker feature.  It is a Task in the HTTP Server Example
# project, and the step in it that does the importing is an ordinary action anyone can put
# in a Task of their own.  Taken apart from this repo's own sample backup, the Profile
# 'POST Import' (prof491) runs task473, whose act13 is:
#
#     code 153  'Import Data'   arg0 Type=0   arg1 Source=0   arg2 = %http_request_body
#
# Type is a dropdown, and its two options are ["Task", "Configuration"] --
# actiont.lookup_values["153"].  api/import hardcodes 0.  So the endpoint is Task-only
# because that Task was written that way, not because Tasker can only import Tasks.
#
# This does what api/import does with Type set to the other option: stage the .prf.xml on
# the device, then run a helper Task that reads it back and hands it to 'Import Data'.
#
# WHAT IS NOT KNOWN, AND WHY THE CALLER HAS TO SAY SO OUT LOUD
#
# What 'Configuration' means to Tasker when it is handed a standalone .prf.xml.  A merge --
# the Profile is added and everything else is left alone -- is what this is for.  A replace
# -- the configuration becomes that one file's contents, and the user's other several
# hundred Profiles stop existing -- is the other possibility, and nothing in Tasker's
# documentation rules it out.  It cannot be settled from here, only by running it against a
# device whose configuration is expendable.
#
# Hence acknowledged_risk.  There is no safe default for a question nobody has answered, so
# the caller states that it accepts the answer it might get.  Until it IS answered, nothing
# in the GUI should call this -- see import_profile_to_device's own note.
#
# Two smaller unknowns, both harmless beside that one:
#
#   * Source (arg1).  actiont.lookup_values["153a"] is a one-entry placeholder, ["Source"],
#     so this codebase does not know what that dropdown's options are called.  0 is what the
#     shipped api/import Task sends and is what this sends; _IMPORT_SOURCE_INDEX is there so
#     another value can be tried without editing the builder (see build_import_profile_task
#     on why that one argument does not go through apply_edits_to_task).
#   * Duplicates.  api/import ADDS a Task whose name is already taken rather than replacing
#     it -- see install_task_on_android, which is built around that.  If Configuration
#     behaves the same way, importing a Profile that is already on the device leaves two of
#     them.  Refused up front unless allow_existing says otherwise.
# v3 since 2026-08-30, when the staged file stopped being one fixed 'maptasker_import.prf.xml'
# and started carrying the Profile's own name.  THE VERSION IN THE NAME IS LOAD-BEARING: what
# this Task reads is part of its body, install_task_on_android installs only what is not
# already there, and a device still holding v1 or v2 would go on reading the old fixed path
# forever -- silently, since those Tasks run and write their answer file either way.  A new
# name is a new Task.
IMPORT_PROFILE_TASK_NAME = "MapTasker Import Profile v3"
_PROFILE_EXTENSION = "prf.xml"
# Where the helper says it got to, read back the same way every other helper's answer is.
_IMPORT_RESULT_WRITE_PATH = "Tasker/maptasker_import.txt"
_IMPORT_RESULT_READ_PATH = "/Tasker/maptasker_import.txt"
# Its own header, so reading one helper's answer as another's is an error rather than a
# silent misparse -- the reason _FILE_PAYLOAD_HEADER has one too.  The terminator is shared,
# because poll_for_result's completeness check is shared.
_IMPORT_PAYLOAD_HEADER = "MAPTASKER-IMPORT 1"
_IMPORT_PAYLOAD_STAGED = "STAGED"

_READ_FILE_ACTION = "417t"  # arg0 File, arg1 To Var, arg2 Structure Output
_IMPORT_DATA_ACTION = "153t"  # arg0 Type (dropdown), arg1 Source (dropdown), arg2 Variable
_IMPORT_DATA_TYPE_LOOKUP = "153"  # actiont.lookup_values key for that Type dropdown
# The Type option this is all for, by the label apply_arg_values matches on (it stores the
# option's index and finds it by label) -- the same contract _LIST_APPS_PACKAGE documents.
IMPORT_TYPE_CONFIGURATION = "Configuration"  # index 1
IMPORT_TYPE_TASK = "Task"  # index 0 -- what api/import itself sends; here to test against
_IMPORT_SOURCE_INDEX = "0"
# Where the .prf.xml lands on the device between being uploaded and being imported.  Named
# for MapTasker so it cannot collide with a variable of the user's own, as the Applications
# helper's are.
_IMPORT_XML_VARIABLE = "%mtimport_xml"
# One file read and one import: seconds, not the minutes an Applications fetch can take.
_IMPORT_POLL_ATTEMPTS = 15


def _import_task_name(import_type: str, source_index: str) -> str:
    """The name this helper is installed under, for a given pair of settings.

    It has to change whenever the Task's BODY changes, because install_task_on_android
    installs by name and skips a name that is already there -- the same contract
    HELPER_TASK_NAME documents with its version suffix.  Both of this Task's settings are
    baked into its actions at install time, so a run that changed one and kept the name
    would quietly re-run the Task built with the other, and the prototype would be
    measuring the previous experiment.

    The default pair keeps the plain name; anything else is spelled out, so a device that
    has been experimented on shows which Task is which in Tasker's own list.
    """
    if import_type == IMPORT_TYPE_CONFIGURATION and source_index == _IMPORT_SOURCE_INDEX:
        return IMPORT_PROFILE_TASK_NAME
    return f"{IMPORT_PROFILE_TASK_NAME} [{import_type}/{source_index}]"


def build_import_profile_task(
    task_name: str = IMPORT_PROFILE_TASK_NAME,
    import_type: str = IMPORT_TYPE_CONFIGURATION,
    source_index: str = _IMPORT_SOURCE_INDEX,
    *,
    state: RunState,
):
    """Build the Profile-importing helper Task.  Returns an EditableTask, or an error message.

    Three kinds of action: 'Read File' to pull the staged .prf.xml into a variable, 'Import
    Data' to hand that variable to Tasker, and 'Write File' to record that it got that far.
    Synthesized out of taskedit's own Add-Task machinery for the reasons build_helper_task
    gives -- all three are addable (every argument is an Int, a Str or a checkbox), so this
    is the path an ordinary user's Add Task takes.

    The Write Files are the entire verification story, and they work only because 'Import
    Data' can fail (action_codes["153t"].canfail is True) and a failed action stops the
    Task: nothing after it runs, the terminator never lands, and poll_for_result reports a
    timeout rather than a success that did not happen.  POST /api/tasks answering 200 says
    only that the Task was started, which is why it is not evidence of anything on its own.
    """

    # Checked rather than trusted because the failure would be silent and would be the
    # wrong import: apply_arg_values resolves a dropdown by matching the label against its
    # options and falls back to index 0 for anything it does not recognize -- and index 0
    # of this particular dropdown is 'Task'.  A typo would quietly import the Profile XML
    # as a Task instead of saying so.
    type_options = lookup_values.get(_IMPORT_DATA_TYPE_LOOKUP, [])
    if import_type not in type_options:
        return f"'{import_type}' is not an 'Import Data' type.  Expected one of: {', '.join(type_options)}."

    edited_task = taskedit.create_new_task(task_name, "100", state=state)
    if isinstance(edited_task, str):
        return edited_task

    values: dict[str, str] = {}

    def add(action_key: str, args: dict[str, str]):  # noqa: ANN202
        """Append one action and stage its argument values.  Returns the action, or an
        error message -- unlike build_helper_task's `add`, which only ever needs the error,
        because one of the actions here has an argument that cannot be set through
        apply_edits_to_task (see below).
        """
        action = taskedit.add_action_to_task(edited_task, action_key, state=state)
        if isinstance(action, list):
            return action[0] if action else f"'{action_key}' could not be added."
        for arg_id, value in args.items():
            values[taskedit_apply.arg_key(action.act_number, arg_id)] = value
        return action

    # Structure Output off (arg2): the .prf.xml is wanted verbatim, as the bytes that were
    # uploaded.  Letting Tasker parse it into %mtimport_xml.<something> would hand 'Import
    # Data' a structure rather than the document.
    #
    # The file READ is %par1, handed over when the Task is run rather than baked in here, so
    # one installed Task serves every Profile and each one keeps its own name on the device
    # -- see run_task_on_android and staged_paths.
    read_action = add(_READ_FILE_ACTION, {"0": STAGE_PATH_PARAMETER, "1": _IMPORT_XML_VARIABLE, "2": "0"})
    if isinstance(read_action, str):
        return read_action

    import_action = add(_IMPORT_DATA_ACTION, {"0": import_type, "2": _IMPORT_XML_VARIABLE})
    if isinstance(import_action, str):
        return import_action

    # Only after the import, and only if it did not fail -- see this function's docstring.
    # %par1 again, so the answer file records the file this run was actually about rather
    # than a path that was true when the Task was installed.
    payload_lines = (_IMPORT_PAYLOAD_HEADER, _IMPORT_PAYLOAD_STAGED, STAGE_PATH_PARAMETER, PAYLOAD_TERMINATOR)
    for index, text in enumerate(payload_lines):
        written = add(
            WRITE_FILE_ACTION,
            {"0": _IMPORT_RESULT_WRITE_PATH, "1": text, "2": "0" if index == 0 else "1", "3": "1"},
        )
        if isinstance(written, str):
            return written

    errors = taskedit_apply.apply_edits_to_task(edited_task, task_name, "100", values, state)
    if errors:
        return errors[0]

    # Source (arg1) is set on the element directly, which no other argument in any helper
    # Task does.  apply_arg_values resolves a dropdown by matching the label against its
    # options, and lookup_values["153a"] is the one-entry placeholder ["Source"] -- so the
    # only value reachable through that path is 0.  0 is the right default (it is what the
    # shipped api/import Task sends), but a prototype whose whole job is to answer open
    # questions should not be the one making one of them unaskable.  Written after
    # apply_edits_to_task, not before, so it cannot be overwritten by it.
    source_element = import_action.action_element.find("Int[@sr='arg1']")
    if source_element is None:
        return "'Import Data' has no Source argument -- actionc.py's definition of '153t' has changed."
    source_element.set("val", source_index)

    return edited_task


# The return code both Profile routes use for "Tasker already has one of these".  Its own
# code rather than the generic 8 because it is the one failure a caller can do something
# about without the user retyping anything -- the GUI turns it into a confirm-and-retry (see
# userintr_android.import_profile_into_tasker_event) -- and matching on the message text to find it
# would break the first time the wording is improved.  6 and 9 are already spoken for
# (maputil2's 'not there' and 'key rejected'); 7 was free.
DUPLICATE_PROFILE_CODE = 7


def _refuse_duplicate_profile(
    ip_address: str,
    ip_port: str,
    profile_name: str,
    auth_key: str,
    allow_existing: bool,
) -> str:
    """The duplicate check the HEADLESS route makes before anything is uploaded or run.
    Returns a refusal to hand the user, or "" to go ahead.

    Not used by the routes that go through Tasker's import screen, and deliberately so:
    measured on a real device, Tasker asks the user itself whether to replace a Profile it
    already has.  Checking first there would be a second prompt in front of a better one --
    and a wrong one, since it would warn about a duplicate Tasker is about to offer to
    replace.

    'Import Data' shows nothing and asks nothing.  Tasker's api/import ADDS a Task whose
    name is taken rather than replacing it (see install_task_on_android) and there is no
    reason yet to think a headless Profile import differs -- so on that route a duplicate
    would appear silently, and both copies would be live at once.  Hence this survives, for
    the one route that has no screen to do the asking.
    """
    if allow_existing or not verify_profile_on_android(ip_address, ip_port, profile_name, auth_key):
        return ""
    return (
        f"Tasker already has a Profile named '{profile_name}'.  Importing may add a second one rather "
        "than replace it.  Rename this Profile, delete that one on the device, or pass allow_existing=True."
    )


def _stage_profile_xml(
    ip_address: str,
    ip_port: str,
    profile_xml: bytes,
    profile_name: str,
) -> tuple[int, str]:
    """Put the .prf.xml where a helper Task can reach it, under the Profile's OWN name.
    Returns (0, its absolute path on the device) or (code, message).

    Shared by both routes -- they differ only in what they do with the file once it is
    there, so a change to where or how it is staged has one place to happen.

    The path comes back rather than being a constant because it is per-Profile now and the
    caller has to hand it to the helper Task at run time -- see staged_paths and
    run_task_on_android.

    Read back and compared byte for byte, because /upload answers 200 whatever it wrote
    (see maputil2.http_upload_request): it does not validate the location, it creates
    missing folders silently, and it reports nothing at the HTTP layer.  A half-written
    .prf.xml would not fail loudly here -- it would be handed to Tasker.
    save_profile_to_android reads its own upload back for exactly this reason.
    """
    filename, read_path, task_path = staged_paths(
        PROFILE_STAGE_LOCATION,
        profile_name,
        _PROFILE_EXTENSION,
        "profile",
    )

    return_code, response = maputil2.http_upload_request(
        ip_address, ip_port, PROFILE_STAGE_LOCATION, filename, profile_xml
    )
    if return_code != 0:
        return return_code, str(response)

    # Retried rather than trusted -- the write and the read are two unrelated Tasker Tasks,
    # and a write still settling answers 404 to a read that arrives too soon.  A single
    # un-retried GET here used to fail an import whose file was on the device a moment
    # later; see maputil2.read_back_uploaded_file, which every other upload in this program
    # already goes through.
    verify_code, verify_content = maputil2.read_back_uploaded_file(ip_address, ip_port, read_path, profile_xml)
    if verify_code != 0:
        return 8, str(verify_content)
    return 0, task_path


def _validate_import_request(
    profile_xml: bytes,
    profile_name: str,
    ip_address: str,
    ip_port: str,
) -> str:
    """What both routes need before they are worth starting.  Returns "" or a message."""
    if not ip_address or not ip_port:
        return "An Android IP address and port are needed.  Set them under 'Get XML from Android Device'."
    if not profile_name:
        return "A Profile name is needed."
    if not profile_xml:
        return "There is no Profile XML to import."
    return ""


def import_profile_to_device(  # noqa: PLR0911
    profile_xml: bytes,
    profile_name: str,
    ip_address: str,
    ip_port: str,
    acknowledged_risk: bool = False,
    allow_existing: bool = False,
    import_type: str = IMPORT_TYPE_CONFIGURATION,
    source_index: str = _IMPORT_SOURCE_INDEX,
    *,
    state: RunState,
) -> tuple[int, str]:
    """Put a Profile into Tasker's live configuration on the device.  PROTOTYPE -- read the
    section comment above before calling this, and do not call it from the GUI until the
    merge-or-replace question it describes has been answered against an expendable device.

    Args:
        profile_xml: the standalone .prf.xml, as bytes -- profedit.render_standalone_profile_xml
            encoded UTF-8, i.e. exactly what save_profile_to_android uploads today.
        acknowledged_risk: the caller stating it accepts an import whose effect on the rest
            of the configuration is not established.  False refuses without touching the
            device.
        allow_existing: proceed even though Tasker already reports a Profile of this name.
            False refuses, because a Configuration import may well add a second one rather
            than replace the first.
        import_type, source_index: the two open questions, as arguments.  Changing either
            installs a differently-NAMED helper Task -- see _import_task_name -- so one
            experiment cannot be run with the Task another one left behind.

    The exchange, in order: get an API key, refuse if the Profile is already there, install
    the helper Task if it isn't, clear the last answer, upload the .prf.xml and read it back
    to confirm it landed whole, run the Task, wait for its answer, then ask Tasker whether
    the Profile exists.  Returns (0, a sentence saying what happened) or (return_code, an
    error message fit to show the user).

    Requires the Tasker HTTP Server Example project running on the device and Tasker 6.2 or
    higher -- 'Save to Android' already requires both.

    Blocking, deliberately, exactly as fetch_apps_from_device is: it sleeps between polls.
    A caller on the GUI thread must hand it to run.io_bound.
    """

    if not acknowledged_risk:
        return 8, (
            "Refusing to import: what Tasker does to the rest of the configuration when it is handed a "
            "Profile as a 'Configuration' import has not been established.  Test it against a device whose "
            "configuration is expendable, and pass acknowledged_risk=True once you know."
        )

    ip_address = ip_address.strip()
    ip_port = ip_port.strip()
    profile_name = profile_name.strip()
    if refusal := _validate_import_request(profile_xml, profile_name, ip_address, ip_port):
        return 8, refusal

    key = device_address(ip_address, ip_port)
    return_code, auth_key = auth_key_for(ip_address, ip_port)
    if return_code != 0:
        return return_code, auth_key

    # Before anything is uploaded or run: a name Tasker already knows.  Checked here rather
    # than left to the import because the import may not object -- see the duplicates note
    # in the section comment above.
    if refusal := _refuse_duplicate_profile(ip_address, ip_port, profile_name, auth_key, allow_existing):
        return DUPLICATE_PROFILE_CODE, refusal

    # Named for the settings it is built with, not just for the job it does -- see
    # _import_task_name for why a shared name would make the prototype lie.
    task_name = _import_task_name(import_type, source_index)
    return_code, message = install_task_on_android(
        ip_address,
        ip_port,
        auth_key,
        task_name,
        lambda: build_import_profile_task(task_name, import_type, source_index, state=state),
        state=state,
    )
    if return_code != 0:
        return return_code, message
    auth_key = held_auth_key(ip_address, ip_port) or auth_key

    # Clear the last answer first, for the reason fetch_apps_from_device gives: a stale one
    # left in place would be read as this run's.  Its own failure is not fatal.
    delete_code, delete_error = http_delete_request(ip_address, ip_port, _IMPORT_RESULT_READ_PATH, auth_key)
    if delete_code != 0:
        logger.info(f"Could not clear {_IMPORT_RESULT_READ_PATH} before importing: {delete_error}")

    return_code, message = _stage_profile_xml(ip_address, ip_port, profile_xml, profile_name)
    if return_code != 0:
        return return_code, message
    stage_task_path = message

    # The staged path goes over WITH the run, as %par1 -- one installed helper, a different
    # file each time.  See run_task_on_android.
    return_code, message = request_with_auth_key(
        ip_address,
        ip_port,
        lambda auth_key: run_task_on_android(ip_address, ip_port, task_name, auth_key, stage_task_path),
    )
    auth_key = held_auth_key(ip_address, ip_port) or auth_key
    if return_code != 0:
        return return_code, message

    text, error = poll_for_result(
        ip_address,
        ip_port,
        _IMPORT_RESULT_READ_PATH,
        _IMPORT_POLL_ATTEMPTS,
        "import result",
    )
    if error:
        # No answer means 'Import Data' failed and stopped the Task, or the Task never ran.
        # Either way nothing was imported, which is the one thing worth saying plainly.
        return 8, f"{error}  Tasker's 'Import Data' most likely refused the Profile XML."
    if not text.splitlines() or text.splitlines()[0].strip() != _IMPORT_PAYLOAD_HEADER:
        return 8, "The file the Android device wrote is not a MapTasker import result."

    # The helper got past 'Import Data' without failing.  That is not the same as Tasker
    # having committed a Profile, which is what this asks.
    if not verify_profile_on_android(ip_address, ip_port, profile_name, auth_key):
        return 8, (
            f"'{profile_name}' was imported without error, but Tasker does not report a Profile of that name "
            "afterwards.  Check Tasker on the device before importing it again."
        )

    return 0, f"'{profile_name}' was imported into Tasker on {key}."
