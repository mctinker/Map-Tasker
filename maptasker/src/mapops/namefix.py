"""namefix: renaming what the naming rules found, with a preview -- Profiles, Tasks and variables, each only where it is safe."""

#! /usr/bin/env python3

#                                                                                        #
# namefix: the renames namerules offers, planned the way every other refactor is.        #
#                                                                                        #
# The result is a maprefac Plan, so the preview is maprefac.report_rows, applying it is   #
# maprefac.apply (ONE undo block, every element re-checked first) and the dialog draws    #
# it as it draws any other.  What this module adds is deciding, for each name the rules   #
# would change, whether the rename can be done WITHOUT BREAKING SOMETHING -- and saying    #
# so, for each one that cannot, rather than renaming the rest quietly.                    #
#                                                                                        #
#   Profile   Nothing refers to a Profile by name (a Project lists its Profiles by id),    #
#             so a rename is the name and the table entries and nothing else.              #
#   Task      Other Tasks call it BY NAME.  Every Perform Task that does is rewritten with   #
#             it.  A Task that something else names -- a Version 2 Scene's handler, a        #
#             home screen widget -- or that shares its name with another Task, is left         #
#             as it is and listed with the reason: those names are not ours to guess at.    #
#   Variable  maprefac_variable already knows every place a variable is set or read, so the  #
#             rename is its plan, one per variable.  One it refuses is left and listed.       #
#   Scene     Not renamed here.  A Scene is named by actions, by Version 2 handlers and by    #
#             its own layout, and the Scene editor is the one place that follows all three.   #
#                                                                                        #
# A new name that is empty, not a legal name, already in use, or proposed twice is skipped    #
# and listed.  Nothing is half-done: a skipped rename leaves its object exactly as it was.    #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
from __future__ import annotations

from typing import TYPE_CHECKING

from maptasker.src.analysis import healthck
from maptasker.src.core.editcommon import name_problem
from maptasker.src.core.mapjump import PROFILE, SCENE, TASK, actions_in_map_order
from maptasker.src.mapgen import varxref
from maptasker.src.mapops import maprefac_variable
from maptasker.src.mapops.maprefac_model import Plan, Step
from maptasker.src.mapops.namerules import GLOBAL_VARIABLE, LOCAL_VARIABLE, Breach

if TYPE_CHECKING:
    from collections.abc import Callable
    from xml.etree.ElementTree import Element

    from maptasker.src.core.primitem import RunState

NAMING = "naming"
_PERFORM_TASK_ARGUMENT = "arg0"
# What names a Task by name that this module does not know how to rewrite.
_NAMED_BY_SOMETHING_ELSE = frozenset({healthck.BY_SCENE_COMPONENT, healthck.BY_WIDGET})


def _perform_task_argument(caller: Element, number: int, old_name: str) -> Element | None:
    """The <Str> holding the called Task's name in the Perform Task that is action `number`, or None if it is not that."""
    actions = actions_in_map_order(caller)
    if not 1 <= number <= len(actions):
        return None
    for child in actions[number - 1].findall("Str"):
        if child.attrib.get("sr") == _PERFORM_TASK_ARGUMENT and (child.text or "").strip() == old_name:
            return child
    return None


def _plan_task(
    breach: Breach, taken: set[str], index: healthck.ReferenceIndex, state: RunState
) -> tuple[Step, Callable[[], None], Element] | str:
    """(the step, what does it, the element) for one Task rename -- or the reason it is not being done."""
    root = state.tasker_root_elements
    task_id = breach.where.key if breach.where else ""
    entry = root["all_tasks"].get(task_id)
    if entry is None:
        return "it is no longer in the configuration"
    old, new = entry["name"], breach.suggestion
    if len(index.task_ids_by_name.get(old, [])) > 1:
        return f"another Task is also called '{old}', so a call to it by name cannot be told apart"
    if new in root["all_tasks_by_name"] or new in taken:
        return f"a Task called '{new}' already exists"
    named_by = [
        referrer for referrer in index.task_referrers.get(task_id, []) if referrer.kind in _NAMED_BY_SOMETHING_ELSE
    ]
    if named_by:
        return f"it is also named by {named_by[0].label}, which this does not rewrite"
    calls: list[Element] = []
    for referrer in index.task_referrers.get(task_id, []):
        if referrer.kind != healthck.BY_PERFORM_TASK:
            continue
        caller = root["all_tasks"].get(referrer.where.key)
        argument = _perform_task_argument(caller["xml"], referrer.where.action, old) if caller else None
        if argument is None:
            return f"{referrer.label} calls it in a way this cannot rewrite"
        calls.append(argument)
    element: Element = entry["xml"]

    def run() -> None:
        name = element.find("nme")
        if name is not None:
            name.text = new
        entry["name"] = new
        by_name = root["all_tasks_by_name"]
        by_name.pop(old, None)
        by_name[new] = {"xml": element, "id": task_id}
        for argument in calls:
            argument.text = new

    called = f", and {len(calls)} Perform Task action{'' if len(calls) == 1 else 's'} that call it" if calls else ""
    return Step(f"Rename Task '{old}' to '{new}'{called}", breach.where), run, element


def _plan_profile(breach: Breach, taken: set[str], state: RunState) -> tuple[Step, Callable[[], None], Element] | str:
    """(the step, what does it, the element) for one Profile rename -- or the reason it is not being done."""
    root = state.tasker_root_elements
    profile_id = breach.where.key if breach.where else ""
    entry = root["all_profiles"].get(profile_id)
    if entry is None:
        return "it is no longer in the configuration"
    old, new = entry["name"], breach.suggestion
    if new in root["all_profiles_by_name"] or new in taken:
        return f"a Profile called '{new}' already exists"
    element: Element = entry["xml"]

    def run() -> None:
        name = element.find("nme")
        if name is not None:
            name.text = new
        entry["name"] = new
        by_name = root["all_profiles_by_name"]
        by_name.pop(old, None)
        by_name[new] = {"xml": element, "id": profile_id}

    return Step(f"Rename Profile '{old}' to '{new}'", breach.where), run, element


class _Planner:
    """What the renames add up to so far: the steps, what does each, the elements touched, and what was left alone."""

    def __init__(self, state: RunState, wanted: list[Breach]) -> None:
        self.state = state
        self.reference_index = healthck.build_reference_index(state)
        needs_variables = any(breach.kind in (GLOBAL_VARIABLE, LOCAL_VARIABLE) for breach in wanted)
        self.variable_index = varxref.build_index(state=state) if needs_variables else None
        self.steps: list[Step] = []
        self.runs: list[Callable[[], list[str]]] = []
        self.elements: list[Element] = []
        self.skipped: list[str] = []
        self.warnings: list[str] = []
        self.taken: dict[str, set[str]] = {PROFILE: set(), TASK: set()}

    def add(self, breach: Breach) -> None:
        """Plan one rename, or note why it is being left alone."""
        label = f"{breach.kind} '{breach.name}'"
        if breach.kind in (PROFILE, TASK):
            self._add_object(breach, label)
        elif breach.kind in (GLOBAL_VARIABLE, LOCAL_VARIABLE):
            self._add_variable(breach, label)
        elif breach.kind == SCENE:
            self.skipped.append(
                f"{label}: not renamed here.  Rename a Scene in the Scene editor, which follows every place that names it.",
            )

    def _add_object(self, breach: Breach, label: str) -> None:
        problem = name_problem(breach.suggestion, breach.kind.capitalize())
        if problem:
            self.skipped.append(f"{label}: {problem}")
            return
        planned = (
            _plan_task(breach, self.taken[TASK], self.reference_index, self.state)
            if breach.kind == TASK
            else _plan_profile(breach, self.taken[PROFILE], self.state)
        )
        if isinstance(planned, str):
            self.skipped.append(f"{label}: not renamed, because {planned}.")
            return
        step, action, element = planned
        self.taken[breach.kind].add(breach.suggestion)
        self.steps.append(step)
        self.runs.append(_returning_nothing(action))
        self.elements.append(element)

    def _add_variable(self, breach: Breach, label: str) -> None:
        if self.variable_index is None:
            return
        plan = maprefac_variable.plan_variable(
            maprefac_variable.RENAME, breach.name, breach.owner, breach.suggestion, self.state, self.variable_index
        )
        if plan.blocks or plan.run is None:
            reason = plan.blocks[0].explanation if plan.blocks else "there is nothing to rewrite"
            self.skipped.append(f"{label}: not renamed, because {reason}")
            return
        self.steps.append(Step(f"Rename {breach.name} to {breach.suggestion}", breach.where))
        self.steps.extend(Step(f"    {step.text}", step.where) for step in plan.steps)
        self.warnings.extend(plan.warnings)
        self.runs.append(plan.run)
        self.elements.extend(plan.elements)

    def run_all(self) -> list[str]:
        """Every planned rename, in order; the errors any of them reports."""
        errors: list[str] = []
        for run in self.runs:
            errors.extend(run())
        return errors


def plan_renames(breaches: list[Breach], state: RunState) -> Plan:
    """The renames these breaches offer, as one Plan, with a note for each that could not be done.

    Only breaches that carry a new name count.  A Plan with nothing safe to do has no `run`, so the dialog shows an
    answer -- why not -- rather than an empty preview and a button that does nothing.
    """
    wanted = [breach for breach in breaches if breach.can_rename]
    count = f"{len(wanted)} object{'' if len(wanted) == 1 else 's'}"
    plan = Plan(kind=NAMING, what=f"Rename {count} to follow the naming rules")
    if not wanted:
        plan.warnings.append("None of the chosen breaches has a new name to give.")
        return plan
    planner = _Planner(state, wanted)
    for breach in wanted:
        planner.add(breach)
    plan.warnings = [*planner.warnings, *(f"Left alone -- {text}" for text in planner.skipped)]
    plan.steps = planner.steps
    plan.elements = tuple(planner.elements)
    if planner.steps:
        plan.run = planner.run_all
    else:
        plan.warnings.append("Nothing can be renamed safely, so nothing will be changed.")
    return plan


def _returning_nothing(action: Callable[[], None]) -> Callable[[], list[str]]:
    """A rename that cannot fail in the way a variable's can, as the list of errors every step reports."""

    def run() -> list[str]:
        action()
        return []

    return run
