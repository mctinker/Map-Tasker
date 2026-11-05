"""effects: what a Task leaves behind on the device -- the settings it switches, the levels it sets, the globals it writes."""

#! /usr/bin/env python3

#                                                                                       #
# effects: read off what a Task does to the things two Tasks can disagree about -- a    #
#          switch (Wi-Fi, Bluetooth), a level (a volume, the brightness) and a global   #
#          variable -- as {what: the value it is left with}.                           #
#                                                                                       #
# proflint answered this for the switches alone, and only for the actions a Task always #
# runs.  The Task Stepper already follows a Task through its If blocks and its Perform   #
# Tasks, with the variables it can know, and records every variable each step changed:  #
# so the same walk, read for what each step it RAN set, finds the levels and the globals #
# as well and sees through the Tasks a Task performs.  The two are put together:         #
#                                                                                       #
#   * what the walk RAN -- reached only along branches whose conditions it could settle  #
#     from what the Task itself sets, and stopped (never guessed past) at the first       #
#     decision that depends on something only the device knows;                          #
#   * what the Task always does, however its conditions turn out (proflint.settings_set), #
#     which catches the switches after an If block the walk had to stop in front of.     #
#                                                                                       #
# Both are certain: an effect this module reports is one the Task makes, not one it       #
# might.  What it cannot report is the cost of that -- a Task that decides by a variable   #
# on the device has effects after the decision that are not here, and a plugin's own      #
# settings are not read.                                                                  #
#                                                                                       #
# Same contract as firesim and taskstep: reads PrimeItems.tasker_root_elements and        #
# nothing else.  The dependency runs firesim -> effects -> taskstep, never back.          #
#                                                                                       #
# MIT License   Refer to https://opensource.org/license/mit                             #
from __future__ import annotations

from typing import TYPE_CHECKING, cast

from maptasker.src.analysis import proflint, taskstep
from maptasker.src.core.actionc import action_codes
from maptasker.src.core.mapjump import actions_in_map_order

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from maptasker.src.core.primitem import RunState

# What a setting is named by: proflint's own for a switch, and (LEVEL, code) or (VARIABLE, name) for the others.
Subject = proflint.Subject

# What kind of thing a subject is, the first member of the tuple that names it.  A switch's subject is
# proflint's own, (action code, the arguments that say which), so settings_set's and this module's agree.
LEVEL = "level"
VARIABLE = "variable"

# The actions that set a level, by code, and the argument the level is in: the volumes and the brightness.
_LEVEL_ARGUMENT = "0"
_LEVEL_CODES = frozenset({"303", "304", "305", "306", "307", "308", "309", "311", "387", "477", "810"})

_VARIABLE_MARKER = "%"

# The statuses of a step whose action the Task does on the path the walk took.
_REACHED = frozenset({taskstep.RAN, taskstep.NOT_SIMULATED})


def _level_of(action: Element) -> tuple[Subject, str] | None:
    """(the level this action sets, its value) for a volume or brightness action with a plain number, else None."""
    code = (action.findtext("code") or "").strip()
    if code not in _LEVEL_CODES:
        return None
    for child in action:
        if child.attrib.get("sr") != f"arg{_LEVEL_ARGUMENT}":
            continue
        variable = child.find("var")
        text = (variable.text or "" if variable is not None else child.attrib.get("val") or child.text or "").strip()
        if text.lstrip("-").isdigit():
            return (LEVEL, code), text
        return None
    return None


def is_global(name: str) -> bool:
    """Whether a variable name is a global: Tasker's rule is that a global has a capital letter in it."""
    return any(char.isupper() for char in name)


def describe(subject: Subject) -> str:
    """The thing as a finding names it: WiFi, Media Volume, %Mode."""
    kind = subject[0]
    if kind == LEVEL:
        entry = action_codes.get(f"{subject[1]}t")
        return entry.name if entry is not None and entry.name else f"code {subject[1]}"
    if kind == VARIABLE:
        return f"%{subject[1]}"
    return proflint.subject_label(subject)


def _setting_of(action: Element, switches: dict[str, str]) -> tuple[Subject, str] | None:
    """(what this one action sets, to what) for a switch, a volume or the brightness, else None."""
    return proflint.switch_setting(action, switches) or _level_of(action)


def _actions_of(
    step: taskstep.Step, own: list[Element], called: dict[str, list[Element]], state: RunState
) -> list[Element]:
    """The actions of the Task a step belongs to: the one being walked, or one it performed."""
    if not step.task:
        return own
    if step.task not in called:
        other = taskstep.find_task(step.task, state)
        called[step.task] = actions_in_map_order(other[1]) if other is not None else []
    return called[step.task]


def _walked(task_id: str, switches: dict[str, str], state: RunState) -> dict[Subject, str]:
    """What the Task Stepper's walk of this Task ran and set, with every unknown left as a stop."""
    trace = taskstep.step_task(task_id, state, taskstep.Options(policy=taskstep.POLICY_STOP))
    found = taskstep.find_task(task_id, state)
    if trace is None or found is None:
        return {}
    own = actions_in_map_order(found[1])
    called: dict[str, list[Element]] = {}

    settings: dict[Subject, str] = {}
    for step in trace.steps:
        # An action the walk reached was run -- or, for one it only shows (a volume, a switch), "not simulated".
        # Either way the Task does it on this path; a skipped, disabled or untaken one does not.
        if step.status not in _REACHED:
            continue
        actions = _actions_of(step, own, called, state)
        if 0 < step.number <= len(actions) and (setting := _setting_of(actions[step.number - 1], switches)):
            settings[setting[0]] = setting[1]
        for change in step.changes:
            if (
                is_global(change.name)
                and change.after != taskstep.UNKNOWN_TEXT
                and _VARIABLE_MARKER not in change.after
            ):
                settings[(VARIABLE, change.name)] = change.after
    return settings


def _always(task_element: Element, switches: dict[str, str]) -> dict[Subject, str]:
    """What the Task always sets, whatever its conditions turn out to be: proflint's unconditional switches and levels."""
    settings = proflint.settings_set(task_element, switches)
    depth = 0
    for action in actions_in_map_order(task_element):
        code = (action.findtext("code") or "").strip()
        if code == "37":
            depth += 1
        elif code == "38":
            depth = max(0, depth - 1)
        elif (
            not depth
            and action.find("on") is None
            and action.find("ConditionList") is None
            and (level := _level_of(action))
        ):
            settings[level[0]] = level[1]
    return settings


def entry_effects(task_id: str, state: RunState) -> dict[Subject, str]:
    """{what the Task sets: the value it leaves}, for the Task with this id.  Empty for a Task that is not there.

    The walk's effects first and the always-run ones over them: the second are literal and certain wherever they
    stand, and a walk that stopped at an unknown decision may not have reached them.
    """
    entry = state.tasker_root_elements["all_tasks"].get(task_id)
    if not isinstance(entry, dict):
        return {}
    switches = proflint.switch_actions()
    return {**_walked(task_id, switches, state), **_always(cast("Element", entry["xml"]), switches)}
