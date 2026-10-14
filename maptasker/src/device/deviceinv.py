#! /usr/bin/env python3
"""deviceinv: fetching the installed Applications from the Android device, through Tasker's HTTP server.

Build a small helper Task with taskedit's own Add-Task machinery, install it, run it, and read
back the file it writes: the Applications' package names, labels and launcher activities, which
are cached for the App and Icon pickers.  That is all that is left here, and it was this module's
whole purpose once; the rest of what MapTasker does on the device grew up around it and is now in
its own modules, built on the same install-run-read exchange (devicetask):

    devicetask      install, run and read back a helper Task; the object list it is built on
    deviceverify    asking Tasker what it has, and waiting for an import to land
    devicefiles     the device's XML files, for the file picker
    deviceimport    importing a Profile into Tasker's live configuration
    deviceoffer     offering a Profile, Project, Scene or Task to Tasker's import screen
    devicecheck     what Tasker already has of what is about to be sent, by name and by ID
    devicehelpers   the helper Tasks left on the device: current, stale, and all in one Project

Anything here that talks to the device blocks until the device answers, so a caller on the GUI's
event loop must hand it to run.io_bound.

The inventory the fetched Applications feed, which the App and Icon pickers offer and which is
harvested from the loaded configuration as well, is appinv.
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from maptasker.src.core.primitem import RunState
    from maptasker.src.edit.taskedit_model import EditableTask


from maptasker.src.core.appinv import AppEntry, _store_fetched_apps
from maptasker.src.core.maputil2 import (
    auth_key_for,
    device_address,
    held_auth_key,
    http_delete_request,
    request_with_auth_key,
)
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

# ==========================================
# Fetching the list from the Android device
# ==========================================

# The helper Task MapTasker installs on the device to do the enumerating, and the file it
# writes.  The name carries a version because the Task is installed once and left there: a
# later MapTasker that needs a different Task installs it under a different name rather
# than trying to decide whether the one already on the device is the one it meant.  An
# orphaned older one is harmless and can be deleted in Tasker.
#
# ---------------------------------------------------------------------------------------
# THE ONE SWITCH.  Set this to False and every difference below reverts together: the helper
# Task goes back to its v1 name and its v1 shape (three bulk 'List Apps' calls), the poll
# budget goes back to 30 seconds, and nothing else in this module or above it changes.  The
# payload format is deliberately identical either way, so parse_device_payload, the cache,
# the pickers and the tests are all untouched by the choice.  It is read at import, not per
# call: flip it and restart.
#
# Why it exists: 'List Apps' answers Package, App and Activity as three independent lists,
# and measured against a real device they do NOT line up -- the first fetch came back
# '(package names only)', which is parse_device_payload discarding a label list of the wrong
# length rather than mislabelling every app with its neighbour's name.  Pairing each label
# to its own package with 'Test App' costs one on-device iteration per installed app, which
# is the part that might prove too cumbersome in practice; hence a switch rather than a
# rewrite.  Activities are NOT paired: 'Test App' has no activity type to ask for (see
# actiont.lookup_values["344"]), so those stay on the bulk call and stay length-checked.
# ---------------------------------------------------------------------------------------
PAIR_LABELS_ON_DEVICE = True

_HELPER_TASK_BULK = "MapTasker Get Apps v1"
_HELPER_TASK_PAIRED = "MapTasker Get Apps v2"
# Versioned because the Task is installed once and left on the device: a different shape gets
# a different name rather than this having to decide whether the one already there is the one
# it meant (see _install_helper_task).  Backing the switch out therefore goes back to using
# v1, which is still sitting on the device from before; v2 is left behind and can be deleted
# in Tasker.
HELPER_TASK_NAME = _HELPER_TASK_PAIRED if PAIR_LABELS_ON_DEVICE else _HELPER_TASK_BULK
# Where the helper writes its answer, and where this reads it back from.  Tasker's Write
# File resolves a relative path against the device's storage root, and the HTTP server's
# 'file' route is rooted at the same place (see get_list_of_files, which strips
# '/storage/emulated/0' off the paths it lists for exactly this reason), so these two are
# the same file spelled the two ways each end wants it.
_DEVICE_RESULT_WRITE_PATH = "Tasker/maptasker_apps.txt"
_DEVICE_RESULT_READ_PATH = "/Tasker/maptasker_apps.txt"

# The payload the helper writes.  A header line, then one 'section name' line followed by
# one line holding that whole section joined together, then a terminator.
#
# One line per section rather than one line per app so that nothing depends on a newline
# surviving a trip through Tasker's Str argument and back -- and PAYLOAD_JOINER rather
# than a comma because app labels contain commas ('Bonza, Jigsaw') and package names do
# not contain this.
_PAYLOAD_HEADER = "MAPTASKER-APPS 1"
_PAYLOAD_PACKAGES = "PACKAGES"
_PAYLOAD_LABELS = "LABELS"
_PAYLOAD_ACTIVITIES = "ACTIVITIES"
_PAYLOAD_SECTIONS = (_PAYLOAD_PACKAGES, _PAYLOAD_LABELS, _PAYLOAD_ACTIVITIES)
_LIST_APPS_ACTION = "815t"  # arg0 Type (dropdown), arg1 Match, arg2 Store Result In
# Used only when PAIR_LABELS_ON_DEVICE is on.
_FOR_ACTION = "39t"  # arg0 Variable, arg1 Items, arg2 Structure Output
_END_FOR_ACTION = "40t"  # no arguments
_TEST_APP_ACTION = "344t"  # arg0 Type (dropdown), arg1 Data, arg2 Store Result In
_VARIABLE_SET_ACTION = "547t"  # arg0 Name, arg1 To, ... arg4 Append
# 'Test App' asks one question about one package.  'App Name' is the only one of its twelve
# types that is any use here -- there is no 'launcher activity' among them, which is why the
# activity list cannot be paired the same way.  See actiont.lookup_values["344"].
_TEST_APP_NAME_TYPE = "App Name"
# The 'Type' dropdown's options, by the label apply_arg_values writes back (it stores the
# option's index, and finds it by matching the label) -- see actiont.lookup_values["815"].
_LIST_APPS_PACKAGE = "Package"
_LIST_APPS_LABEL = "App"
_LIST_APPS_ACTIVITY = "Activity"
# Where each 'List Apps' run puts its answer.  Named for MapTasker so a helper Task running
# on someone's device cannot collide with a variable of their own.
_PACKAGES_VARIABLE = "%mtapps_pkg"
_LABELS_VARIABLE = "%mtapps_lbl"
_ACTIVITIES_VARIABLE = "%mtapps_cls"
# The loop's own two locals, when pairing.  Lowercase, so Tasker scopes them to one run of
# the Task and no state can survive into the next fetch.
_LOOP_PACKAGE_VARIABLE = "%mtapp"
_LOOP_LABEL_VARIABLE = "%mtapp_name"
_RESULT_POLL_ATTEMPTS = 60 if PAIR_LABELS_ON_DEVICE else 15


def parse_device_payload(text: str) -> tuple[list[AppEntry], str]:
    """Read the helper Task's file back into Applications.

    Returns (entries, error_message); a non-empty error means the payload was not one this
    understands and nothing should be cached from it.

    **The alignment question this is built around** (app_icon_fetch_design.md §3): it is not
    established that 'List Apps' returns Package, App and Activity in the same order, and it
    cannot be established without a real device.  So the package list is authoritative -- it
    is the identity, and it is the field Tasker matches on -- and a label or activity list
    is used ONLY if it has exactly as many entries.  A list of a different length is
    discarded rather than zipped: mislabelling every app is far worse than labelling none,
    because a wrong label looks right.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != _PAYLOAD_HEADER:
        return [], "The file the Android device wrote is not a MapTasker application list."
    if not any(line.strip() == PAYLOAD_TERMINATOR for line in lines):
        return [], "The Android device's application list is incomplete -- the Task may still be running."

    sections: dict[str, list[str]] = {}
    for index, line in enumerate(lines):
        name = line.strip()
        if name in _PAYLOAD_SECTIONS and index + 1 < len(lines):
            sections[name] = split_payload_section(lines[index + 1])

    packages = sections.get(_PAYLOAD_PACKAGES, [])
    if not any(packages):
        return [], "The Android device reported no applications."

    labels = sections.get(_PAYLOAD_LABELS, [])
    activities = sections.get(_PAYLOAD_ACTIVITIES, [])
    if len(labels) != len(packages):
        logger.info(f"Android app labels ({len(labels)}) do not line up with packages ({len(packages)}); ignoring.")
        labels = []
    if len(activities) != len(packages):
        logger.info(f"Android app activities ({len(activities)}) do not line up with packages; ignoring.")
        activities = []

    entries = []
    for index, package in enumerate(packages):
        if not package:
            continue
        entries.append(
            AppEntry(
                pkg=package,
                label=labels[index] if labels else "",
                cls=activities[index] if activities else "",
            ),
        )
    return entries, ""


def _add_paired_label_actions(add: Callable[[str, dict[str, str]], str]) -> str:
    """The loop that gives every package its own label.  Returns "" or an error message.

    Built because 'List Apps' does not answer Package and App in the same order -- measured,
    not assumed: the first real fetch came back '(package names only)', which is
    parse_device_payload refusing to zip two lists of different lengths.  Asking 'Test App'
    for one package's name at a time pairs them by construction, so no order has to be
    trusted.

    The cost is one on-device iteration per installed app, which is why the whole thing is
    behind PAIR_LABELS_ON_DEVICE.

    Three details that are not obvious:

      * The label variable is seeded with the package before 'Test App' overwrites it, so a
        lookup that fails leaves the package name as the label rather than the literal text
        '%mtapp_name'.  Tasker writes an unset variable out as its own name.
      * Each label is appended WITH a trailing joiner, because Tasker has no 'join with a
        separator between' in an append.  That leaves one empty part at the end of the line,
        which split_payload_section drops -- and a bulk-joined line has no trailing joiner,
        so that drop is a no-op on the other path.
      * It iterates '%mtapps_pkg()', the array, which is why build_helper_task runs this
        before joining the packages into a string.
    """
    return (
        # Start from empty: the appends below build this line up one label at a time.
        add(_VARIABLE_SET_ACTION, {"0": _LABELS_VARIABLE, "1": "", "4": "0"})
        or add(_FOR_ACTION, {"0": _LOOP_PACKAGE_VARIABLE, "1": f"{_PACKAGES_VARIABLE}()", "2": "0"})
        or add(_VARIABLE_SET_ACTION, {"0": _LOOP_LABEL_VARIABLE, "1": _LOOP_PACKAGE_VARIABLE, "4": "0"})
        or add(
            _TEST_APP_ACTION,
            {"0": _TEST_APP_NAME_TYPE, "1": _LOOP_PACKAGE_VARIABLE, "2": _LOOP_LABEL_VARIABLE},
        )
        or add(
            _VARIABLE_SET_ACTION,
            {"0": _LABELS_VARIABLE, "1": f"{_LOOP_LABEL_VARIABLE}{PAYLOAD_JOINER}", "4": "1"},
        )
        or add(_END_FOR_ACTION, {})
    )


def build_helper_task(task_name: str = HELPER_TASK_NAME, *, state: RunState) -> EditableTask | str:
    """Build the helper Task, out of taskedit's own Add-Task machinery.

    Returns an EditableTask, or an error message string if it could not be built (the same
    either/or taskedit.create_new_task itself uses).

    Synthesized rather than shipped as a blob of XML on purpose.  Every action it needs --
    'List Apps', 'Variable Join', 'Write File' -- is one taskedit already classifies as
    addable, so this is the same code path an ordinary user's Add Task takes, and the Task
    stays correct if an argument definition in actionc.py is ever corrected.  It also means
    there is no second copy of Tasker's XML shape to keep in step with the first.
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

    # 'Store Result In' produces an array (%v1, %v2, ...); 'Variable Join' collapses it into
    # the one variable a 'Write File' can write.  The two are kept apart here because the
    # order matters when pairing: the loop iterates the packages ARRAY, so it has to run
    # before that array is collapsed into a single string.
    def list_apps(list_type: str, variable: str) -> str:
        return add(_LIST_APPS_ACTION, {"0": list_type, "1": "", "2": variable})

    def join(variable: str) -> str:
        return add(VARIABLE_JOIN_ACTION, {"0": variable, "1": PAYLOAD_JOINER, "2": "0"})

    # Each step answers with the error that stopped it, or "" -- and the first error ends the build.
    steps = [lambda: list_apps(_LIST_APPS_PACKAGE, _PACKAGES_VARIABLE)]

    if PAIR_LABELS_ON_DEVICE:
        steps.append(lambda: _add_paired_label_actions(add))

    steps.append(lambda: join(_PACKAGES_VARIABLE))

    if not PAIR_LABELS_ON_DEVICE:
        steps.append(lambda: list_apps(_LIST_APPS_LABEL, _LABELS_VARIABLE) or join(_LABELS_VARIABLE))

    # Activities are asked for in bulk whether or not labels are paired -- 'Test App' has no
    # activity type to ask for, so there is nothing to pair them with.  They stay subject to
    # parse_device_payload's length check, and are dropped when they fail it.
    steps.append(lambda: list_apps(_LIST_APPS_ACTIVITY, _ACTIVITIES_VARIABLE) or join(_ACTIVITIES_VARIABLE))

    # Then the file, a line at a time.  The first write truncates and every later one
    # appends, so a re-run replaces the previous answer rather than growing it.
    payload_lines = (
        _PAYLOAD_HEADER,
        _PAYLOAD_PACKAGES,
        _PACKAGES_VARIABLE,
        _PAYLOAD_LABELS,
        _LABELS_VARIABLE,
        _PAYLOAD_ACTIVITIES,
        _ACTIVITIES_VARIABLE,
        PAYLOAD_TERMINATOR,
    )
    steps.extend(
        lambda index=index, text=text: add(
            WRITE_FILE_ACTION,
            {"0": _DEVICE_RESULT_WRITE_PATH, "1": text, "2": "0" if index == 0 else "1", "3": "1"},
        )
        for index, text in enumerate(payload_lines)
    )

    for step in steps:
        error = step()
        if error:
            return error

    errors = taskedit_apply.apply_edits_to_task(edited_task, task_name, "100", values, state)
    if errors:
        return errors[0]
    return edited_task


def fetch_apps_from_device(ip_address: str, ip_port: str, state: RunState) -> tuple[int, str]:
    """Fetch the full list of installed Applications from an Android device and cache it.

    The whole exchange, in order: get an API key, put the helper Task on the device if it
    isn't there, delete any previous answer, run the Task, wait for the file, read it,
    parse it, cache it.  Returns (0, a sentence saying what was fetched) or
    (return_code, an error message fit to show the user).

    Requires the Tasker HTTP Server Example project running on the device and Tasker 6.2 or
    higher -- the same requirements 'Save to Android' already has.

    Blocking, deliberately: it sleeps between polls, and the file it is waiting for takes
    seconds to appear.  Callers on the GUI thread must hand it to run.io_bound, the way
    guiutils.ping_android_device does with its own probe.
    """

    ip_address = ip_address.strip()
    ip_port = ip_port.strip()
    if not ip_address or not ip_port:
        return 8, "An Android IP address and port are needed.  Set them under 'Get XML from Android Device'."

    key = device_address(ip_address, ip_port)
    return_code, auth_key = auth_key_for(ip_address, ip_port)
    if return_code != 0:
        return return_code, auth_key

    return_code, message = install_task_on_android(
        ip_address, ip_port, auth_key, HELPER_TASK_NAME, functools.partial(build_helper_task, state=state), state=state
    )
    if return_code != 0:
        return return_code, message
    auth_key = held_auth_key(ip_address, ip_port) or auth_key

    # Clear the previous answer out of the way BEFORE running anything -- see
    # maputil2.http_delete_request for why this is not optional.  Its own failure is not
    # fatal: the terminator check in poll_for_result is a second line of defence, and a
    # device that refuses the delete may still run the Task perfectly well.
    delete_code, delete_error = http_delete_request(ip_address, ip_port, _DEVICE_RESULT_READ_PATH, auth_key)
    if delete_code != 0:
        logger.info(f"Could not clear {_DEVICE_RESULT_READ_PATH} before fetching: {delete_error}")

    # A rejected key is replaced and the run tried once more -- see
    # maputil2.request_with_auth_key, which is where that dance now lives.
    return_code, message = request_with_auth_key(
        ip_address,
        ip_port,
        lambda auth_key: run_task_on_android(ip_address, ip_port, HELPER_TASK_NAME, auth_key),
    )
    if return_code != 0:
        return return_code, message

    text, error = poll_for_result(
        ip_address, ip_port, _DEVICE_RESULT_READ_PATH, _RESULT_POLL_ATTEMPTS, "application list"
    )
    if error:
        return 8, error

    entries, error = parse_device_payload(text)
    if error:
        return 8, error

    cache_error = _store_fetched_apps(key, entries)
    labelled = sum(1 for entry in entries if entry.label)
    summary = f"{len(entries)} applications fetched from {key}"
    summary += f" ({labelled} with names)." if labelled else " (package names only)."
    if cache_error:
        summary += f"  They could not be saved for next time: {cache_error}"
    return 0, summary
