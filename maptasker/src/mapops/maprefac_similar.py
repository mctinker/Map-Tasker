"""maprefac_similar: Tasks that are copies of each other with small differences -- the run of actions they share becomes one Task that they all call."""

#! /usr/bin/env python3

#                                                                                        #
# maprefac_similar: the near-duplicate finder.                                           #
#                                                                                        #
# A Task copied and pasted, then changed a little, is the commonest way a configuration  #
# grows: 'Morning' and 'Evening' and 'Weekend' each hold the same eight actions that     #
# set the volume and the brightness and post the same notification, and differ in the    #
# two or three actions around them.  The eight are one idea written three times, and     #
# the day somebody changes the volume it is changed in two of the three.                 #
#                                                                                        #
# Two halves.                                                                            #
#                                                                                        #
#   FINDING   find_shared_runs() looks at every Task's actions as a sequence and finds   #
#             the runs of consecutive actions that two or more Tasks have in common.     #
#   DOING     plan_shared_run() turns one such run into a Task of its own that the Tasks #
#             holding it each call -- which is Extract, done to every copy at once, and  #
#             built from the same parts (maprefac_extract's Perform Task, maprefac's     #
#             preview and apply).                                                        #
#                                                                                        #
# WHAT MAKES TWO ACTIONS THE SAME                                                        #
#                                                                                        #
# Everything the action says it does: its code, every argument, its condition, whether   #
# it is switched on and whether it carries on after an error.  Not its label and not     #
# whether it is shown collapsed, because those say nothing about what runs -- a label    #
# is a note the user wrote to themselves, and two copies written a week apart will have  #
# been annotated differently.  When the copies' labels differ the preview says so, since #
# turning the copies into one means keeping one set of them.                             #
#                                                                                        #
# WHAT IS NOT OFFERED                                                                    #
#                                                                                        #
#   * A run that begins or ends inside an If or a For.  The part that can be moved is    #
#     offered instead (maprefac_model.longest_balanced_run): the rest of the block has    #
#     to stay where it is, or the actions left behind would run under no condition.      #
#   * A Task that contains a Goto.  A Goto addresses an action by its NUMBER and moving  #
#     a run renumbers every action after it; the same reason Extract refuses.            #
#   * A run too short to be worth a Task of its own -- it has to save at least two       #
#     actions once the calls are counted, and be at least as long as the dialog's        #
#     "smallest shared run" says.                                                        #
#                                                                                        #
# THE SCAN AND THE PLAN ARE SEPARATE, AND THE PLAN DOES NOT TRUST THE SCAN               #
#                                                                                        #
# A scan can be on screen while the user edits a Task in another dialog.  So the plan    #
# takes only where ONE copy of the run sits (Task, first action, length) and works out   #
# again, from the Tasks as they are now, which Tasks hold it.  A Task edited since the   #
# scan drops out, or the whole run does, and the plan says so as a block rather than     #
# rewriting a Task from a list that is no longer true.                                   #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from maptasker.src.core import objnotes
from maptasker.src.core.editcommon import name_problem
from maptasker.src.core.mapjump import PROJECT, TASK, Target
from maptasker.src.core.sysconst import logger
from maptasker.src.edit import profedit, taskedit, taskedit_save
from maptasker.src.mapops.maprefac_extract import new_perform_task
from maptasker.src.mapops.maprefac_model import (
    PARAMETERS,
    SIMILAR,
    Block,
    Plan,
    Step,
    action_name,
    actions_of,
    blocked,
    control_flow_imbalance,
    describe_actions,
    goto_numbers,
    longest_balanced_run,
    object_table,
    projects_listing,
    renumber,
    shared_locals_warning,
    task_target,
    variable_names,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from xml.etree.ElementTree import Element

    from maptasker.src.core.primitem import RunState

# The shortest run the dialog offers by default, and the choices it gives for it.  Three actions in common is
# coincidence as often as it is copying (a Wait, a Flash and a Variable Set turn up everywhere); four is where a
# shared run starts to mean something, and a longer minimum is for a configuration with a great deal of it.
DEFAULT_MIN_RUN = 4
MIN_RUN_CHOICES = (3, 4, 5, 6, 8, 10)

# A run has to save at least this many actions, counting the call each copy keeps and the Task it is made into.
MIN_SAVED = 2

# The tag the shared Task is given in the user's notes (objnotes), so that every Task made this way can be listed at
# once -- and how many Task names its note spells out before it says "and N more", so that one line stays a line.
SHARED_TAG = "shared"
_NAMES_IN_NOTE = 12

# The most runs one scan hands back, best first, and the most it will explore to find them.  The second is a guard
# for a configuration made almost entirely of one pasted block, where the number of ways a run can be shared
# between Tasks grows faster than anyone could read.
MAX_RUNS = 300
_EXPLORE_LIMIT = 200_000

# What a copy can differ in without being a different action: see the header.
_COSMETIC_ATTRIBUTES = frozenset({"sr", "ve"})
_COSMETIC_CHILDREN = frozenset({"label", "coll"})

# A place in a Task: (the Task's id, the index of an action in it counting from 0).
_Spot = tuple[str, int]


# ##################################################################################
# What a scan hands back.
# ##################################################################################


@dataclass(frozen=True)
class Placement:
    """Where a shared run sits in one Task."""

    task_id: str
    name: str
    first: int  # the number the Map prints for the run's first action, counting from 1
    task_actions: int  # how many actions the whole Task has


@dataclass(frozen=True)
class SharedRun:
    """A run of actions that two or more Tasks have in common, and where each of them has it."""

    length: int
    placements: tuple[Placement, ...]
    actions: tuple[str, ...]  # the names of the run's actions, in order
    host: str  # the id of a Task that is made of nothing but this run, or "" when there is none

    @property
    def key(self) -> str:
        """What the dialog calls it: the first copy's Task, where it begins and how long it is."""
        first = self.placements[0]
        return f"{first.task_id}:{first.first}:{self.length}"

    @property
    def saved(self) -> int:
        """How many fewer actions the configuration holds afterwards.

        Every copy but one is dropped and each Task that held a copy gains a call; a Task that is already
        nothing but the run is the shared one, so it gains no call and no new Task is made.
        """
        copies = len(self.placements)
        if self.host:
            return copies * self.length - self.length - (copies - 1)
        return copies * self.length - self.length - copies


# ##################################################################################
# Reading the Tasks.
# ##################################################################################


def _canonical(element: Element, *, top: bool = False) -> tuple[Any, ...]:
    """An action as a value that is equal to another action's exactly when the two do the same thing."""
    attributes = tuple(
        sorted((name, value) for name, value in element.attrib.items() if not (top and name in _COSMETIC_ATTRIBUTES)),
    )
    children = tuple(_canonical(child) for child in element if not (top and child.tag in _COSMETIC_CHILDREN))
    return (element.tag, attributes, (element.text or "").strip(), children)


@dataclass(frozen=True)
class _Reading:
    """Every Task as its actions in run order and as a list of numbers, one per distinct action."""

    names: dict[str, str]
    actions: dict[str, list[Element]]
    sequences: dict[str, list[int]]


def _read_tasks(state: RunState, *, only: set[str] | None = None) -> _Reading:
    """Read the Tasks (all of them, or `only` these), numbering each distinct action once."""
    numbers: dict[tuple[Any, ...], int] = {}
    names: dict[str, str] = {}
    actions: dict[str, list[Element]] = {}
    sequences: dict[str, list[int]] = {}
    for task_id, entry in object_table("all_tasks", state=state).items():
        if only is not None and task_id not in only:
            continue
        task_actions = actions_of(entry["xml"])
        if not task_actions:
            continue
        names[task_id] = entry.get("name", "") or f"Task {task_id}"
        actions[task_id] = task_actions
        sequences[task_id] = [numbers.setdefault(_canonical(action, top=True), len(numbers)) for action in task_actions]
    return _Reading(names, actions, sequences)


# ##################################################################################
# Finding the runs.
#
# Every run of `shortest` actions that appears in two or more Tasks is a starting point.  It is grown, one action at
# a time at either end, for as long as every copy agrees -- and when the copies stop agreeing, the ones that still do
# between themselves are followed on their own, since two Tasks can share a run that a third only shares part of.
# ##################################################################################


def _grow(sequences: dict[str, list[int]], spots: list[_Spot], length: int) -> tuple[list[_Spot], int]:
    """The run, made longer at either end for as long as every copy has the same action next to it."""
    while all(start > 0 for _, start in spots) and len({sequences[task][start - 1] for task, start in spots}) == 1:
        spots = [(task, start - 1) for task, start in spots]
        length += 1
    while (
        all(start + length < len(sequences[task]) for task, start in spots)
        and len({sequences[task][start + length] for task, start in spots}) == 1
    ):
        length += 1
    return spots, length


def _by_next_action(
    sequences: dict[str, list[int]], spots: list[_Spot], length: int, *, before: bool
) -> list[list[_Spot]]:
    """The copies sorted by which action sits just before (or just after) them; copies at a Task's edge are dropped."""
    groups: dict[int, list[_Spot]] = {}
    for task, start in spots:
        at = start - 1 if before else start + length
        if 0 <= at < len(sequences[task]):
            groups.setdefault(sequences[task][at], []).append((task, start))
    return list(groups.values())


def _one_per_task(spots: list[_Spot]) -> list[_Spot]:
    """The leftmost copy in each Task: a run that repeats inside one Task is moved from the first place only."""
    first: dict[str, int] = {}
    for task, start in spots:
        if task not in first or start < first[task]:
            first[task] = start
    return list(first.items())


def _maximal_runs(sequences: dict[str, list[int]], shortest: int) -> list[tuple[list[_Spot], int]]:
    """Every run of at least `shortest` actions that two or more Tasks share, as far as it can be grown."""
    starting: dict[tuple[int, ...], list[_Spot]] = {}
    for task, numbers in sequences.items():
        for start in range(len(numbers) - shortest + 1):
            starting.setdefault(tuple(numbers[start : start + shortest]), []).append((task, start))
    pending = [(spots, shortest) for spots in starting.values() if len({task for task, _ in spots}) > 1]

    seen: set[tuple[frozenset[_Spot], int]] = set()
    found: list[tuple[list[_Spot], int]] = []
    explored = 0
    while pending and explored < _EXPLORE_LIMIT:
        explored += 1
        spots, length = pending.pop()
        spots, length = _grow(sequences, spots, length)
        if (key := (frozenset(spots), length)) in seen:
            continue
        seen.add(key)
        copies = _one_per_task(spots)
        if len(copies) > 1:
            found.append((copies, length))
        for before in (True, False):
            pending.extend(
                (group, length)
                for group in _by_next_action(sequences, spots, length, before=before)
                if len(group) < len(spots) and len({task for task, _ in group}) > 1
            )
    return found


def _movable(reading: _Reading, spots: list[_Spot], length: int, shortest: int) -> tuple[list[_Spot], int] | None:
    """The part of this run that can be moved without cutting an If or a For in two, or None if too little can."""
    task, start = spots[0]
    window = reading.actions[task][start : start + length]
    core = longest_balanced_run(window, shortest)
    if core is None:
        return None
    offset, kept = core
    return [(each, begin + offset) for each, begin in spots], kept


def _shared_run(reading: _Reading, spots: list[_Spot], length: int) -> SharedRun:
    """A run in the terms the dialog and the plan use: Tasks by name, actions counted from 1 as the Map counts them."""
    placements = tuple(
        Placement(task, reading.names[task], start + 1, len(reading.actions[task]))
        for task, start in sorted(spots, key=lambda spot: (reading.names[spot[0]].lower(), spot[0]))
    )
    first = placements[0]
    window = reading.actions[first.task_id][first.first - 1 : first.first - 1 + length]
    host = next((each.task_id for each in placements if each.task_actions == length), "")
    return SharedRun(length, placements, tuple(action_name(action) for action in window), host)


def _contained_in_another(runs: list[SharedRun]) -> set[int]:
    """The runs that say nothing a bigger one does not: the same Tasks (or fewer), inside a longer or wider run."""
    spans = [{each.task_id: (each.first, each.first + run.length) for each in run.placements} for run in runs]
    holding: dict[str, list[int]] = {}
    for index, span in enumerate(spans):
        for task in span:
            holding.setdefault(task, []).append(index)
    redundant: set[int] = set()
    for index, run in enumerate(runs):
        for other in holding[run.placements[0].task_id]:
            bigger = runs[other]
            if other == index or (bigger.length, len(bigger.placements)) <= (run.length, len(run.placements)):
                continue
            if len(bigger.placements) >= len(run.placements) and all(
                task in spans[other] and spans[other][task][0] <= begin and end <= spans[other][task][1]
                for task, (begin, end) in spans[index].items()
            ):
                redundant.add(index)
                break
    return redundant


def find_shared_runs(shortest: int, state: RunState) -> list[SharedRun]:
    """The runs of actions that two or more Tasks have in common, the most worth merging first.

    Tasks holding a Goto are left out altogether (see the header), and so is a Task of no actions.  What comes
    back are runs that can be made into a Task of their own as they stand: whole If and For blocks only, at least
    `shortest` actions long, saving at least MIN_SAVED actions.
    """
    reading = _read_tasks(state)
    candidates = {
        task: numbers
        for task, numbers in reading.sequences.items()
        if len(numbers) >= shortest and not goto_numbers(reading.actions[task])
    }
    runs: dict[str, SharedRun] = {}
    for spots, length in _maximal_runs(candidates, shortest):
        trimmed = _movable(reading, spots, length, shortest)
        if trimmed is None:
            continue
        run = _shared_run(reading, *trimmed)
        if run.saved >= MIN_SAVED:
            runs.setdefault(run.key, run)
    ordered = sorted(runs.values(), key=lambda run: (-run.saved, -run.length, run.key))
    redundant = _contained_in_another(ordered)
    return [run for index, run in enumerate(ordered) if index not in redundant][:MAX_RUNS]


def run_choices(runs: list[SharedRun]) -> list[tuple[str, str]]:
    """The runs as (key, label) for a pulldown: how long, how many Tasks, which, and what merging them saves."""
    choices: list[tuple[str, str]] = []
    for run in runs:
        names = [placement.name for placement in run.placements]
        listed = ", ".join(names[:3]) + (", ..." if len(names) > 3 else "")
        choices.append(
            (run.key, f"{run.length} actions in {len(names)} Tasks ({listed})  -- saves {run.saved}"),
        )
    return choices


def suggested_name(run: SharedRun, state: RunState) -> str:
    """A name for the shared Task that no Task has, built from the Task it will be taken from."""
    base = f"{run.placements[0].name} - shared part"
    name, number = base, 1
    while taskedit.task_name_exists(name, state=state):
        number += 1
        name = f"{base} {number}"
    return name


# ##################################################################################
# Doing it.
# ##################################################################################


@dataclass(frozen=True)
class _Holder:
    """One Task that holds the run, and what is in the way of changing it."""

    task_id: str
    name: str
    task: Element
    actions: list[Element]
    first: int  # counting from 1
    length: int

    @property
    def window(self) -> list[Element]:
        """The run's own actions in this Task."""
        return self.actions[self.first - 1 : self.first - 1 + self.length]

    @property
    def kept(self) -> list[Element]:
        """Every other action of the Task, in run order."""
        return [*self.actions[: self.first - 1], *self.actions[self.first - 1 + self.length :]]


def _holders(task_id: str, first: int, length: int, state: RunState) -> tuple[list[_Holder], list[str]] | None:
    """Every Task that holds the same run as this one, and the names of those that cannot be changed.

    None when the run is not there at all: the Task is gone, or has been edited so that the actions the scan saw at
    that place are no longer there.  The leftmost copy in each Task is the one used.
    """
    reading = _read_tasks(state)
    numbers = reading.sequences.get(task_id)
    if numbers is None or first < 1 or first - 1 + length > len(numbers):
        return None
    wanted = numbers[first - 1 : first - 1 + length]
    holders: list[_Holder] = []
    left_out: list[str] = []
    for each, each_numbers in reading.sequences.items():
        start = next(
            (at for at in range(len(each_numbers) - length + 1) if each_numbers[at : at + length] == wanted),
            None,
        )
        if start is None:
            continue
        if goto_numbers(reading.actions[each]):
            left_out.append(reading.names[each])
            continue
        task_element: Element = object_table("all_tasks", state=state)[each]["xml"]
        holders.append(_Holder(each, reading.names[each], task_element, reading.actions[each], start + 1, length))
    holders.sort(key=lambda holder: (holder.name.lower(), holder.task_id))
    return holders, left_out


def _name_block(new_name: str, where: Target, state: RunState) -> Block | None:
    """Why the new Task cannot be called this, or None."""
    if not new_name:
        return Block("NO-NAME", "The shared Task needs a name.", where)
    if problem := name_problem(new_name, "Task"):
        return Block("BAD-NAME", problem, where)
    if taskedit.task_name_exists(new_name, state=state):
        return Block(
            "NAME-TAKEN",
            f"A Task named '{new_name}' is already in this file.  Perform Task calls a Task by name, so "
            f"two Tasks sharing one would leave it ambiguous which of them each call runs.",
            where,
        )
    return None


def plan_shared_run(task_id: str, first: int, length: int, new_name: str, state: RunState) -> Plan:
    """Make the run that begins at this action of this Task into one Task that every Task holding it calls.

    `first` is the number the Map prints (counting from 1).  The Tasks that hold the run are found again here, as they
    are now: see the header on why a scan's answer is not trusted.

    The shared Task is a new one, made from the actions of the first copy -- unless some Task holding the run is
    made of nothing else, in which case that Task is the shared one already and `new_name` is not used: the others
    simply call it.  Either way every other copy is dropped and a Perform Task stands where it was, so what runs, and
    in what order, is unchanged.
    """
    what = f"Make the {length} shared actions of a Task one Task that the others call"
    where = task_target(task_id, state=state)
    found = _holders(task_id, first, length, state=state)
    if found is None:
        return blocked(
            SIMILAR,
            what,
            Block(
                "OUT-OF-RANGE",
                "The actions this was found in are no longer there.  The Task may have been edited since the search; "
                "search again.",
                where,
            ),
        )
    holders, left_out = found
    if len(holders) < 2:
        return blocked(
            SIMILAR,
            what,
            Block(
                "NOT-SHARED",
                "These actions are no longer in two Tasks that can be changed.  The Tasks may have been edited "
                "since the search; search again.",
                where,
            ),
        )

    source = holders[0]
    host = next((holder for holder in holders if len(holder.actions) == length), None)
    what = f"Make the {length} actions that {len(holders)} Tasks share " + (
        f"the Task '{host.name}', which the others call" if host else f"one new Task '{new_name}' that they call"
    )
    block = _block_for(source, new_name, host is not None, where, state=state)
    if block is not None:
        return blocked(SIMILAR, what, block)

    plan = Plan(
        kind=SIMILAR,
        what=what,
        elements=tuple(element for holder in holders for element in (holder.task, *holder.window)),
    )
    owners = projects_listing("tids", source.task_id, state=state)
    plan.steps = _steps(holders, host, new_name, owners, state=state)
    plan.warnings = _warnings(holders, host, left_out, owners, state=state)
    plan.run = _runner(holders, host, new_name, owners, state=state)
    return plan


def _block_for(source: _Holder, new_name: str, reuses: bool, where: Target, state: RunState) -> Block | None:
    """The one reason this will not be done, or None."""
    imbalance = control_flow_imbalance(list(enumerate(source.window, start=source.first)))
    if imbalance:
        return Block(
            "UNBALANCED-BLOCK",
            f"The shared actions are not self-contained: {imbalance}.  Moving them would leave the actions on the "
            f"other side running under a condition, or a loop, that is no longer there.",
            where,
        )
    return None if reuses else _name_block(new_name, where, state=state)


def _steps(
    holders: list[_Holder], host: _Holder | None, new_name: str, owners: list[str], state: RunState
) -> list[Step]:
    """What will be done, in order, one line each."""
    source = holders[0]
    names = ", ".join(action_name(action) for action in source.window[:4]) + (", ..." if source.length > 4 else "")
    steps: list[Step] = []
    if host is None:
        steps.append(Step(f"Create Task '{new_name}' holding {source.length} actions: {names}"))
    else:
        steps.append(Step(f"Task '{host.name}' stays as it is, and is the Task the others call"))
    for holder in holders:
        if holder is host:
            continue
        target = task_target(holder.task_id, state=state).at_action(holder.first)
        steps.append(
            Step(
                f"In Task '{holder.name}', take out {describe_actions(list(range(holder.first, holder.first + holder.length)))}"
                f" and put a Perform Task there, as action {holder.first}",
                target,
            ),
        )
    if host is None:
        steps.extend(
            Step(f"Add Task '{new_name}' to Project '{project}'", Target(kind=PROJECT, key=project))
            for project in owners
        )
    shared = host.name if host else new_name
    steps.append(
        Step(
            f"Put a note on Task '{shared}' saying it is shared and which Tasks call it, tagged #{SHARED_TAG} "
            f"(kept in the notes file, not in the backup)",
            task_target(host.task_id, state=state) if host else None,
        ),
    )
    return steps


def _warnings(
    holders: list[_Holder], host: _Holder | None, left_out: list[str], owners: list[str], state: RunState
) -> list[str]:
    """What is true of this change that the user should read before making it."""
    warnings: list[str] = []
    source = holders[0]
    if left_out:
        listed = ", ".join(f"'{name}'" for name in left_out[:6]) + (", ..." if len(left_out) > 6 else "")
        warnings.append(
            f"{listed} also {'holds' if len(left_out) == 1 else 'hold'} these actions but "
            f"{'contains' if len(left_out) == 1 else 'contain'} a Goto, which addresses an action by its number and "
            f"would land somewhere else once the actions around it moved.  "
            f"{'It is' if len(left_out) == 1 else 'They are'} left as {'it is' if len(left_out) == 1 else 'they are'}.",
        )

    warnings.extend(_locals_warnings(holders))

    parameters = sorted(name for name in variable_names(source.window) if name.lower() in PARAMETERS)
    if parameters:
        warnings.append(
            f"The shared actions use {', '.join(parameters)}.  Those are the parameters of whatever called each Task, "
            f"and once the actions are in a Task of their own they are the parameters of the Perform Task that calls "
            f"it -- which is written without passing anything in.",
        )

    changed = _labels_lost(holders, host)
    if changed:
        warnings.append(
            f"{changed} of the actions being dropped {'carries' if changed == 1 else 'carry'} a label that differs "
            f"from the one on the action being kept.  Only one set of labels survives: the kept one.",
        )

    bare = [holder.name for holder in holders if holder is not host and not holder.kept]
    if bare:
        listed = ", ".join(f"'{name}'" for name in bare[:6]) + (", ..." if len(bare) > 6 else "")
        warnings.append(
            f"{listed} {'is' if len(bare) == 1 else 'are'} made of nothing but these actions, so "
            f"{'it' if len(bare) == 1 else 'each'} will be left holding a single call.  That is valid; it is worth "
            f"being sure it is what you meant.",
        )

    if host is None:
        homes = {tuple(projects_listing("tids", holder.task_id, state=state)) for holder in holders}
        if len(homes) > 1:
            warnings.append(
                f"These Tasks are not all in the same Project.  The new Task is filed under "
                f"{', '.join(repr(project) for project in owners) or 'no Project'}, like Task '{source.name}' it is "
                f"taken from; Perform Task finds a Task by name from any Project.",
            )
    return warnings


def _locals_warnings(holders: list[_Holder]) -> list[str]:
    """Local variables a Task shares between the run and the rest of itself, which the move would separate."""
    found = [
        (holder.name, text)
        for holder in holders
        if (text := shared_locals_warning(holder.window, holder.kept, "in a Task of their own"))
    ]
    warnings = [f"Task '{name}': {text}" for name, text in found[:4]]
    if len(found) > 4:
        warnings.append(f"{len(found) - 4} more Tasks share local variables in the same way.")
    return warnings


def _labels_lost(holders: list[_Holder], host: _Holder | None) -> int:
    """How many of the actions that are dropped carry a label different from the action that is kept in their place."""
    keeper = host or holders[0]
    kept = [(action.findtext("label") or "").strip() for action in keeper.window]
    return sum(
        1
        for holder in holders
        if holder is not keeper
        for action, label in zip(holder.window, kept, strict=True)
        if (action.findtext("label") or "").strip() not in {"", label}
    )


def _runner(
    holders: list[_Holder], host: _Holder | None, new_name: str, owners: list[str], state: RunState
) -> Callable[[], list[str]]:
    """The change itself, for the plan to run later."""
    source = holders[0]

    def run() -> list[str]:
        """Make the shared Task (or take the one that is there), then put a call where each copy was."""
        shared_name = host.name if host else new_name
        if host is None:
            priority = source.task.findtext("pri", "") or "100"
            new_task = taskedit.create_new_task(new_name, priority, state=state)
            if isinstance(new_task, str):
                return [new_task]
            # The elements themselves move out of the first Task; they are not copied.  See maprefac_extract.
            for action in source.window:
                source.task.remove(action)
                new_task.task_element.append(action)
            renumber(source.window)
            _put_call_in(source, shared_name)
            taskedit_save.register_new_task(new_task, new_name, state=state)
            for project_name in owners:
                profedit.add_task_to_project(new_task.task_id, project_name, state=state)
        for holder in holders:
            if holder is host or (host is None and holder is source):
                continue
            for action in holder.window:
                holder.task.remove(action)
            _put_call_in(holder, shared_name)
        _note_the_sharing(shared_name, [holder.name for holder in holders if holder is not host], state=state)
        return []

    return run


def _put_call_in(holder: _Holder, shared_name: str) -> None:
    """Where the run was taken out of a Task, write the call to the shared one, and number the Task's actions again."""
    kept = holder.kept
    call = new_perform_task(type(holder.task), shared_name)
    holder.task.append(call)
    before = holder.first - 1
    renumber([*kept[:before], call, *kept[before:]])


def _sharing_sentence(callers: list[str]) -> str:
    """One sentence saying who calls the shared Task, naming up to _NAMES_IN_NOTE of them."""
    listed = ", ".join(callers[:_NAMES_IN_NOTE])
    if len(callers) > _NAMES_IN_NOTE:
        listed += f", and {len(callers) - _NAMES_IN_NOTE} more"
    return (
        f"Shared: this Task is called by {len(callers)} {'Task' if len(callers) == 1 else 'Tasks'} ({listed}), "
        f"so a change here changes what each of them does."
    )


def _note_the_sharing(shared_name: str, callers: list[str], state: RunState) -> None:
    """Note on the shared Task, in the user's own notes, that it is shared and by whom -- and tag it.

    Added to a note the Task already has rather than written over it: a Task that was the run already (or one whose
    name an earlier, undone merge left a note under) may carry something the person wrote.  The notes are in a file
    of their own, outside the backup and outside Undo, so a merge that is undone leaves the note on a Task that is
    not there; it comes back with the Task if the merge is redone.

    A note that cannot be saved is logged and not reported as a failure: the Tasks have been changed by now, and
    saying the merge failed would be saying the opposite of what happened.
    """
    sentence = _sharing_sentence(callers)
    book = objnotes.book_for(state)
    existing = book.get(TASK, shared_name)
    text = sentence
    tags = [SHARED_TAG]
    if existing is not None:
        text = existing.text if sentence in existing.text else f"{existing.text}  {sentence}".strip()
        tags = [*existing.tags, SHARED_TAG]
    try:
        book.put(objnotes.Note(TASK, shared_name, text, tags))
    except ValueError as error:
        logger.error(f"Shared Task '{shared_name}' could not be given a note: {error}")
        return
    if problem := objnotes.save(book):
        logger.error(f"The note on shared Task '{shared_name}' could not be saved: {problem}")
