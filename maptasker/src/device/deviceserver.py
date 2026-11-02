"""deviceserver: putting the 'Http Server Example' Tasker project on a device that lacks it."""

from __future__ import annotations

from typing import TYPE_CHECKING

from maptasker.src.core.maputil2 import auth_key_for, device_address, held_auth_key, request_with_auth_key
from maptasker.src.device.devicetask import (
    PROFILES_ENDPOINT,
    finish_helper_task,
    install_task_on_android,
    new_helper_task,
    run_task_on_android,
)
from maptasker.src.device.deviceverify import MANUAL_IMPORT_POLL_ATTEMPTS, await_import, verify_names_on_android

if TYPE_CHECKING:
    from maptasker.src.core.primitem import RunState
    from maptasker.src.edit.taskedit_model import EditableTask

# ==========================================
# Installing the 'Http Server Example' project
# ==========================================
#
# MapTasker talks to the device through two Tasker projects.  'Tasker HTTP API' answers every
# 'api/...' route -- the key, the import, running and listing Tasks, Profiles and Scenes -- and
# 'Http Server Example' answers the plain ones: 'file' to read a file off the device and 'upload'
# to write one.  Reading a backup, Save To Android and every helper Task's answer file go
# through the second, so a device without it can be asked almost nothing.
#
# WHAT CAN INSTALL IT, which is narrower than it looks.  Not the second project, which is what
# is missing.  Tasker's HTTP API imports a Task and only a Task (POST /api/import), so a Project
# cannot be sent through it; and 'upload' only drops a file in storage, which Tasker never reads,
# so it is no way to stage one either -- and it is the very route that is absent.  What the HTTP
# API CAN do is run a Task, and a Task can open a link.  So the Task installed here opens the
# project's TaskerNet share, which brings up Tasker's own import screen on the device, and the
# user taps Import -- the same one tap every other import here ends in.
#
# NO ANSWER FILE, because reading one back is the 'file' route.  Success is asked of Tasker
# instead, the way an import of a Project is confirmed everywhere else: by whether the
# Profiles the project owns have turned up in GET api/profiles.
#
# REASONED, NOT MEASURED: that Android hands a taskernet.com/shares link to Tasker (or to a
# browser that offers it).  Nothing here can check it without a device, and if it does not land
# the message names the link, so the user can open it on the phone by hand.

SERVER_PROJECT_NAME = "Http Server Example"
# The project's TaskerNet share -- the page the README's short link leads to.
SERVER_SHARE_URL = (
    "https://taskernet.com/shares/?user=AS35m8ne7oO4s%2BaDx%2FwlzjdFTfVMWstg1ay5AkpiNdrLoSXEZdFfw1IpXiyJCVLNW0yn"
    "&id=Project%3AHttp+Server+Example"
)
# The two of its sixteen Profiles MapTasker uses: 'File System Host' serves GET /file/*, and
# 'Upload Files' serves PUT/POST /upload.  Whether the project is there is whether these are,
# since a user may well have deleted the rest.
SERVER_PROFILES = ("File System Host", "Upload Files")
# Versioned for the reason every helper Task is: install_task_on_android installs by name, so a
# changed link needs a new name or the old Task goes on opening the old one.
OPEN_SHARE_TASK_NAME = "MapTasker Open Share v1"

_SEND_INTENT_ACTION = "877t"  # arg0 Action, arg1 Cat, arg2 Mime Type, arg3 Data, arg9 Target
_VIEW_ACTION = "android.intent.action.VIEW"
_INTENT_CATEGORY_NONE = "None"
_INTENT_TARGET_ACTIVITY = "Activity"


def build_open_share_task(
    task_name: str = OPEN_SHARE_TASK_NAME, url: str = SERVER_SHARE_URL, *, state: RunState
) -> EditableTask | str:
    """Build the Task that opens a link on the device.  An EditableTask, or an error message string.

    'Send Intent' with ACTION_VIEW and the link as its data, and no package or class: an
    implicit intent for a web link, which Android gives to whatever handles taskernet.com --
    Tasker, if it has claimed the link, or the browser, whose TaskerNet page has an Import
    button.  'Browse URL' would do the same but takes an App argument, which taskedit refuses
    to add while the application inventory is empty (see deviceoffer's note on it).

    The link is baked in rather than handed over as %par1: there is one link, and a Task that
    can be sent anywhere is more than this is for.
    """
    built = new_helper_task(task_name, state=state)
    if isinstance(built, str):
        return built
    edited_task, add, values = built

    error = add(
        _SEND_INTENT_ACTION,
        {"0": _VIEW_ACTION, "1": _INTENT_CATEGORY_NONE, "3": url, "9": _INTENT_TARGET_ACTIVITY},
    )
    if error:
        return error
    return finish_helper_task(edited_task, task_name, values, state)


def server_is_installed(ip_address: str, ip_port: str, auth_key: str) -> bool | None:
    """Whether the device has the Profiles of the Http Server Example MapTasker needs.  None if it could not be asked.

    Asked of the Tasker HTTP API, because the project itself is what may be missing: probing its
    'file' route would answer the same way for 'not installed' and 'not running'.
    """
    present = verify_names_on_android(ip_address, ip_port, PROFILES_ENDPOINT, list(SERVER_PROFILES), auth_key)
    if present is None:
        return None
    return present == set(SERVER_PROFILES)


def install_server_example(
    ip_address: str,
    ip_port: str,
    wait_for_confirmation: bool = True,
    attempts: int = MANUAL_IMPORT_POLL_ATTEMPTS,
    *,
    state: RunState,
) -> tuple[int, str]:
    """Open the Http Server Example's TaskerNet share on the device, unless it is already there.

    Returns (0, a sentence saying what happened and what is left to do) or (return_code, an error
    message).  Needs only the Tasker HTTP API project, which is the point; its message says so
    when that is what is missing.

    The exchange: get a key, ask what Tasker has, install the helper Task if it is absent, run
    it, and then -- if asked -- wait for the project's Profiles to appear, for as long as it
    takes someone to pick up the phone (await_import: `attempts` polls, five minutes by default,
    since a share is a page to read and a button to tap before it is Tasker's own import screen).
    With wait_for_confirmation False it returns as soon as the link has been opened, and the
    message says the import is pending.

    Blocking; a caller on the GUI thread must use run.io_bound.
    """
    ip_address = ip_address.strip()
    ip_port = ip_port.strip()
    if not ip_address or not ip_port:
        return 8, "An Android IP address and port are needed.  Set them under 'Get XML from Android Device'."

    key = device_address(ip_address, ip_port)
    return_code, auth_key = auth_key_for(ip_address, ip_port)
    if return_code != 0:
        return return_code, (
            f"{auth_key}  Installing '{SERVER_PROJECT_NAME}' goes through the 'Tasker HTTP API' project, which "
            "has to be installed and running on the device; without it there is no way in."
        )

    installed = server_is_installed(ip_address, ip_port, auth_key)
    if installed:
        return 0, f"'{SERVER_PROJECT_NAME}' is already in Tasker on {key}."

    return_code, message = install_task_on_android(
        ip_address,
        ip_port,
        auth_key,
        OPEN_SHARE_TASK_NAME,
        lambda: build_open_share_task(state=state),
        state=state,
    )
    if return_code != 0:
        return return_code, message
    auth_key = held_auth_key(ip_address, ip_port) or auth_key

    return_code, message = request_with_auth_key(
        ip_address,
        ip_port,
        lambda fresh_key: run_task_on_android(ip_address, ip_port, OPEN_SHARE_TASK_NAME, fresh_key),
    )
    if return_code != 0:
        return return_code, str(message)
    auth_key = held_auth_key(ip_address, ip_port) or auth_key

    opened = (
        f"The '{SERVER_PROJECT_NAME}' share was opened on {key}.  Tap Import on the device to finish; "
        f"if nothing came up, open {SERVER_SHARE_URL} on the phone."
    )
    if not wait_for_confirmation:
        return 0, opened

    return_code, message = await_import(
        ip_address,
        ip_port,
        list(SERVER_PROFILES),
        f"Project '{SERVER_PROJECT_NAME}'",
        PROFILES_ENDPOINT,
        auth_key,
        attempts,
    )
    return (0, message) if return_code == 0 else (return_code, f"{message}  {opened}")
