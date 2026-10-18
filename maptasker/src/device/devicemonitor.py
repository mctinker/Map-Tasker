"""devicemonitor: sampling which Tasks are running and which Profiles are active on the Android device."""

#! /usr/bin/env python3

#                                                                                        #
# devicemonitor: the phone's half of the Live Run Monitor.                                 #
#                                                                                        #
# Tasker's HTTP API cannot push: there is no event to subscribe to.  What it can do is run a  #
# Task and hand back what that Task returned (devicetask.run_task_for_result), and a Task can #
# read Tasker's own %TRUN (the Tasks running now) and %PACTIVE (the Profiles active now).  So  #
# the monitor is a helper Task, 'MapTasker Monitor v1', that looks at those, waits a moment,   #
# looks again, and returns every look it took in one answer -- a WINDOW of samples.            #
#                                                                                        #
# Why a window and not one look per request: an HTTP round trip costs far more than a look   #
# at two variables, and a Task that runs for a moment is only seen if something is looking      #
# while it runs.  Sampling on the device, a few times a second, between requests that each      #
# bring back a few seconds of them, is what makes a short Task visible at all.               #
#                                                                                        #
# The Task is installed once and left (install_task_on_android does not replace one), so the    #
# number of samples is not baked in: it arrives as %par1, which the Task's For loop counts to.  #
# The wait between samples IS baked in; a different one means a different version of the name.   #
#                                                                                        #
# The Task itself is running while it looks, so its own name is always in %TRUN.  The monitor      #
# knows it and is told to leave it out (MONITOR_TASK_NAME).                                    #
#                                                                                        #
# Blocking: a window takes as long as its samples do, plus the round trip.  A caller on the    #
# GUI thread must go through run.io_bound.                                                   #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import TYPE_CHECKING

from maptasker.src.analysis.livemon import FIELD_SEPARATOR, SAMPLE_SEPARATOR
from maptasker.src.core.maputil2 import auth_key_for
from maptasker.src.device.devicetask import (
    TaskRunResult,
    finish_helper_task,
    install_task_on_android,
    new_helper_task,
    run_task_for_result,
)

if TYPE_CHECKING:
    from maptasker.src.core.primitem import RunState
    from maptasker.src.edit.taskedit_model import EditableTask

# The helper Task.  Versioned because it is installed once and left on the device.
MONITOR_TASK_NAME = "MapTasker Monitor v1"

# How long the Task waits between two looks, in milliseconds.  Baked in; see the header.
SAMPLE_WAIT_MS = 200
# How many looks a window takes by default, and the most one may be asked for.
DEFAULT_SAMPLES = 10
MAX_SAMPLES = 100

_VARIABLE_SET = "547t"  # arg0 Name, arg1 To, arg4 Append
_FOR = "39t"  # arg0 Variable, arg1 Items, arg2 Structure Output
_END_FOR = "40t"
_WAIT = "30t"  # arg0 MS, arg1 Seconds, arg2 Minutes, arg3 Hours, arg4 Days
_RETURN = "126t"  # arg0 Value

# Named for MapTasker so a helper Task running on someone's device cannot collide with a variable of their own.
_LOG = "%mtmon_log"
_COUNTER = "%mtmon_i"

# What one look records: the moment, then the Tasks running, the Profiles active and the battery, in that order.
# Tasker substitutes its own built-ins when the Task runs.
_LOOK = FIELD_SEPARATOR.join(("%TIMEMS", "%TRUN", "%PACTIVE", "%BATT")) + SAMPLE_SEPARATOR


def build_monitor_task(task_name: str = MONITOR_TASK_NAME, *, state: RunState) -> EditableTask | str:
    """Build the helper Task, out of taskedit's own Add-Task machinery.  An EditableTask, or an error message.

    Clear the log; then, %par1 times, append one look and wait; then return the log.  Each look is appended
    WITH its trailing separator, since Tasker has no append-with-separator, and the one after the last is simply an
    empty record that parse_window drops.
    """
    built = new_helper_task(task_name, state=state)
    if isinstance(built, str):
        return built
    edited_task, add, values = built

    error = (
        add(_VARIABLE_SET, {"0": _LOG, "1": "", "4": "0"})
        or add(_FOR, {"0": _COUNTER, "1": "1:%par1", "2": "0"})
        or add(_VARIABLE_SET, {"0": _LOG, "1": _LOOK, "4": "1"})
        or add(_WAIT, {"0": str(SAMPLE_WAIT_MS)})
        or add(_END_FOR, {})
        or add(_RETURN, {"0": _LOG, "1": "1"})
    )
    if error:
        return error
    return finish_helper_task(edited_task, task_name, values, state)


@dataclass
class Window:
    """What one request brought back: the text of the samples, or why there is none."""

    ok: bool
    text: str = ""
    error: str = ""
    seconds: float = 0.0


def install_monitor(ip_address: str, ip_port: str, *, state: RunState) -> tuple[int, str]:
    """Put the helper Task on the device if it is not there.  (0, "") or (return_code, message).

    Done once, before sampling starts, so that the first window is not also the slow one -- and so that a device
    that cannot be reached is found out before the monitor claims to be running.
    """
    ip_address, ip_port = ip_address.strip(), ip_port.strip()
    if not ip_address or not ip_port:
        return 8, "An Android IP address and port are needed."
    return_code, auth_key = auth_key_for(ip_address, ip_port)
    if return_code != 0:
        return return_code, auth_key
    return install_task_on_android(
        ip_address,
        ip_port,
        auth_key,
        MONITOR_TASK_NAME,
        functools.partial(build_monitor_task, state=state),
        state=state,
    )


def sample_window(ip_address: str, ip_port: str, samples: int = DEFAULT_SAMPLES, *, state: RunState) -> Window:
    """Run the helper Task once and return the samples it took.

    `samples` is how many looks, clamped to what the Task and the timeout can take.  The wait for the answer is
    the time the looks take plus a margin for the round trip, so a slow network is not mistaken for a hung Task.
    """
    count = max(1, min(int(samples), MAX_SAMPLES))
    timeout = count * SAMPLE_WAIT_MS / 1000 + 20
    result: TaskRunResult = run_task_for_result(
        ip_address, ip_port, MONITOR_TASK_NAME, par1=str(count), timeout=timeout, state=state
    )
    if not result.ok:
        return Window(ok=False, error=result.error, seconds=result.seconds)
    return Window(ok=True, text=result.output, seconds=result.seconds)
