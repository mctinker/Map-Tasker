"""maprefac: refactoring operations -- moves that rearrange the configuration rather than rewrite fields.

What is left here is what the four moves share at the end: the choices the dialog offers, the preview rows,
the saved report and apply().  The moves themselves are in their own modules:

    maprefac_extract     extract a run of actions into a Task, and inline a Perform Task
    maprefac_move        move a Task or a Profile to another Project
    maprefac_duplicate   copy a Project, Profile, Task or Scene under a new name

built on maprefac_model (Step, Block and Plan, and how the tree is read).
"""

#! /usr/bin/env python3

#                                                                                        #
# maprefac: the structural moves.  Four of them, one machinery.                          #
#                                                                                        #
#   EXTRACT    a run of a Task's actions becomes a Task of its own, and a Perform Task   #
#              takes their place.                                                        #
#   INLINE     the reverse: a Perform Task becomes the actions of the Task it calls.     #
#   MOVE       a Task or a Profile changes which Project owns it.                        #
#   DUPLICATE  a Project, Profile, Task or Scene is copied under a new name.             #
#                                                                                        #
# Same contract as healthck / varxref / mapfind / mapswap -- reads and writes            #
# PrimeItems.tasker_root_elements and nothing else, no GUI import, identity from         #
# mapjump -- and the same two rules every writer in this program follows:                #
#                                                                                        #
#   NOTHING IS APPLIED UNSEEN.  plan() and apply() are separate, apply() only ever takes #
#   a plan(), and every step of that plan is a clickable mapjump Row before it is a      #
#   change.                                                                              #
#                                                                                        #
#   ONE UNDO.  A refactor touches several objects at once -- extract writes a new Task,  #
#   edits an old one and edits a Project -- and all of it is one thing the user did, so  #
#   the whole of apply() runs inside a single re-entrant sessundo.undoable block.        #
#                                                                                        #
# WHERE THIS DIFFERS FROM mapswap, AND WHY THE DIFFERENCE IS THE POINT                   #
#                                                                                        #
# A bulk replace is a hundred independent changes, so mapswap's Plan carries a tick box  #
# per change and its apply() is a loop that can skip one and carry on.  A refactor is    #
# ONE change, made of steps that are meaningless apart: extracting six actions without   #
# writing the Perform Task that replaces them does not leave the user with a partly-done #
# refactor, it leaves them with six actions that no longer run.  So there are no ticks   #
# here, and a Plan is all-or-nothing.                                                    #
#                                                                                        #
# That is also why the refusals are BLOCKS rather than mapswap's per-site Skips.  A skip #
# reports one place a bulk operation could not reach and lets the rest proceed.  There   #
# is no "rest" here: a reason this refactor is unsafe is a reason not to do it at all,   #
# so a Plan carrying blocks describes what WOULD have happened and apply() refuses it.   #
#                                                                                        #
# WHAT A BLOCK IS FOR, AND WHY THERE ARE SO MANY                                         #
#                                                                                        #
# Every one of these moves is trivially correct on a Task of five Flashes and quietly    #
# wrong on a real one.  Pull six actions out of the middle of an If block and the three  #
# that are left run unconditionally.  Inline a Task holding a Goto and the Goto now      #
# addresses somebody else's action.  Split a Task in half and the local variables the    #
# two halves shared stop being the same variable, because a local belongs to the running #
# Task and a Perform Task starts a new one.                                              #
#                                                                                        #
# None of those show up as an error.  The configuration parses, loads, and runs -- doing #
# something other than what it did before, discovered days later on the device.  So the  #
# checks below are the feature, not paperwork around it, and each one names the specific #
# thing that would go wrong rather than refusing in the abstract.                        #
#                                                                                        #
# WHAT IS DELIBERATELY NOT ATTEMPTED                                                     #
#                                                                                        #
# Nothing here rewrites prose.  A Task label reading "flash the total" on an action that #
# has moved to another Task is stale, and a description mentioning six steps that are    #
# now one is stale, and this tool says so rather than editing English.                   #
#                                                                                        #
# Nothing here repoints references it cannot see.  A Task named in a home screen widget, #
# in a Tasker shortcut, or built at run time out of a variable is beyond the file, and   #
# the moves that could strand one say so in a warning instead of pretending otherwise.   #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

from typing import TYPE_CHECKING

from maptasker.src.core import clock, mapjump, maputil2
from maptasker.src.core.mapjump import TASK, Row, text_report
from maptasker.src.core.maputils import append_to_filename
from maptasker.src.core.outdir import output_path
from maptasker.src.core.sysconst import REFACTOR_FILE, logger
from maptasker.src.edit import sessundo, taskedit_model

if TYPE_CHECKING:
    from maptasker.src.core.primitem import RunState
from maptasker.src.mapops.maprefac_model import (
    Plan,
    action_code,
    action_name,
    actions_of,
    display_project,
    object_table,
    string_argument,
)

# ##################################################################################
# What there is to choose from.
#
# Here rather than in the dialog for the reason mapswap's own choice builders are: the
# labels have to say what the object IS -- which Project a Task is in, which of a Task's
# actions are calls -- and every one of those facts is read off the tables this module
# already walks.  A dialog building them itself would be a second reader of the same
# structures, drifting from this one.
# ##################################################################################


def task_choices(scope: mapjump.Scope | None = None, *, state: RunState) -> list[tuple[str, str]]:
    """Every Task as (id, label), Project named, sorted the way a user looks for one.

    The Project is in the label because Task names are not unique across a configuration
    and routinely repeat -- 'Setup' in four Projects is ordinary -- so an id-keyed pulldown
    showing bare names would offer four identical entries.

    `scope` narrows the list to what the app is currently displaying -- see extract_scope,
    which is the only caller that passes one and explains why.  None, or an empty Scope,
    offers every Task in the file.
    """
    entries = [
        (task_id, entry.get("name", "") or f"Task {task_id}", display_project("tids", task_id, state=state))
        for task_id, entry in object_table("all_tasks", state=state).items()
        if scope is None or scope.allows(TASK, task_id)
    ]
    entries.sort(key=lambda item: (item[2].lower(), item[1].lower()))
    return [
        (task_id, f"{name}  ({project})" if project else f"{name}  (no Project)") for task_id, name, project in entries
    ]


def profile_choices(state: RunState) -> list[tuple[str, str]]:
    """Every Profile as (id, label), Project named.  Same reasoning as task_choices."""
    entries = [
        (
            profile_id,
            entry.get("name", "") or f"Profile {profile_id}",
            display_project("pids", profile_id, state=state),
        )
        for profile_id, entry in object_table("all_profiles", state=state).items()
    ]
    entries.sort(key=lambda item: (item[2].lower(), item[1].lower()))
    return [
        (profile_id, f"{name}  ({project})" if project else f"{name}  (no Project)")
        for profile_id, name, project in entries
    ]


def project_choices(state: RunState) -> list[str]:
    """Every Project name, sorted."""
    return sorted(object_table("all_projects", state=state), key=str.lower)


def scene_choices(state: RunState) -> list[str]:
    """Every Scene name, sorted."""
    return sorted(object_table("all_scenes", state=state), key=str.lower)


def action_choices(task_id: str, state: RunState) -> list[tuple[int, str]]:
    """A Task's actions as (number, label), counted from 1.

    Numbered as the Map prints them -- 1, 2, 3 -- because that is the number the user is
    looking at when they decide which actions to extract, and because every other report in
    this program counts them that way (healthck, varxref and taskflow each enumerate
    actions_in_map_order with start=1).  Counting from 0 here made every jump land one
    action early, and made action 0 lose its anchor outright: Target.anchor appends the
    action only `if self.action`, and 0 is falsy.  A label the user gave an
    action is shown alongside its name: on a Task of forty Flashes it is the only thing
    telling one from another.
    """
    entry = object_table("all_tasks", state=state).get(task_id)
    if entry is None:
        return []
    choices = []
    for number, action in enumerate(actions_of(entry["xml"]), start=1):
        label = (action.findtext("label") or "").strip().splitlines()
        suffix = f"  -- {label[0][:40]}" if label and label[0] else ""
        choices.append((number, f"{number}: {action_name(action)}{suffix}"))
    return choices


def call_choices(task_id: str, state: RunState) -> list[tuple[int, str]]:
    """Only the Perform Task actions of a Task -- the ones an inline can be asked about.

    Filtered here rather than offering every action and refusing the rest in the preview.
    A pulldown of forty actions where thirty-eight produce "that is not a Perform Task" is
    a worse answer than a pulldown of two, and the refusal still exists for the case where
    the Task was edited while the dialog was open.
    """
    entry = object_table("all_tasks", state=state).get(task_id)
    if entry is None:
        return []
    choices = []
    for number, action in enumerate(actions_of(entry["xml"]), start=1):
        if action_code(action) != taskedit_model.PERFORM_TASK_ACTION_CODE:
            continue
        called = string_argument(action, taskedit_model.PERFORM_TASK_NAME_ARG_ID) or "(no Task named)"
        choices.append((number, f"{number}: Perform Task '{called}'"))
    return choices


# ##################################################################################
# The preview, and the one thing it is for.
# ##################################################################################


def report_rows(plan: Plan) -> list[Row]:
    """The plan as mapjump Rows: what it is, what stops it, what to read, what it will do.

    Blocks first and steps last, which is the reverse of how the plan was built and the
    order the user reads in.  A refusal is the whole answer when there is one -- printing
    the steps above it would show a user a list of things that are not going to happen and
    make them scroll for the reason.

    Rows rather than a string so the preview is clickable in the Map the way a health-check
    finding is.  For this feature that is not decoration: "actions 3-6 of Task 'Morning'"
    is not enough to decide by, and going to look at them is the only way to be sure.
    """
    rows: list[Row] = [Row(plan.what), Row("")]

    if plan.blocks:
        rows.append(Row(f"CANNOT BE DONE ({len(plan.blocks)})"))
        for block in plan.blocks:
            rows.append(Row(f"  {block.where.label}" if block.where else f"  {block.reason}", block.where))
            rows.extend(Row(f"      {line}") for line in _wrapped(block.explanation))
        return rows

    if plan.warnings:
        rows.extend((Row(f"BEFORE YOU DO THIS ({len(plan.warnings)})"), Row("")))
        for warning in plan.warnings:
            rows.extend(Row(f"  {line}") for line in _wrapped(warning))
            rows.append(Row(""))

    rows.append(Row(f"WHAT WILL HAPPEN ({len(plan.steps)} {'step' if len(plan.steps) == 1 else 'steps'})"))
    for number, step in enumerate(plan.steps, start=1):
        # A step whose text is already indented is a continuation of the one above it (the
        # renamings under a Project duplication), and numbering those would imply they are
        # separate things that happen in turn.
        prefix = "     " if step.text.startswith("    ") else f"  {number:>2}. "
        rows.append(Row(f"{prefix}{step.text.strip()}", step.where))

    if not plan.steps:
        rows.append(Row("  Nothing."))
    return rows


_REPORT_WIDTH = 88


def _wrapped(text: str) -> list[str]:
    """A paragraph broken to the report's width, on spaces.

    The explanations here are prose -- several sentences of it -- where healthck's and
    mapswap's are one line, so they are the first thing in this program that has to wrap.
    Done on the Row rather than left to the widget because the same text is written to a
    text file, where nothing is going to wrap it at all.
    """
    words, lines, current = text.split(), [], ""
    for word in words:
        if current and len(current) + 1 + len(word) > _REPORT_WIDTH:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}" if current else word
    if current:
        lines.append(current)
    return lines or [""]


def write_refactor_report(rows: list[Row], state: RunState) -> str:
    """Save the preview as text, the way mapfind, varxref and mapswap save theirs.

    Worth having for the refactor the user decided NOT to do as much as the one they did:
    a block's explanation names the actions that would have to be selected differently, and
    that is a work list which does not survive closing the dialog otherwise.
    """
    stamp = clock.now().strftime("_%m-%d-%Y_%H-%M-%S")
    file_name = append_to_filename(REFACTOR_FILE, stamp)
    if not file_name:
        return ""
    file_path = output_path(file_name, state=state)
    try:
        with open(file_path, "w", encoding="utf-8") as output_file:
            output_file.write(text_report(rows))
    except OSError as error:
        logger.error(f"Refactor report could not be written: {error}")
        return ""
    return file_path


def apply(plan: Plan, state: RunState) -> tuple[bool, list[str]]:
    """Do the refactor.  Returns (whether it was done, anything that went wrong).

    Three gates, in this order, and each is a different question:

      IS IT ALLOWED.  A Plan carrying blocks is a preview of something that was refused,
      and apply() refuses it again rather than trusting the dialog to have disabled its
      own button.  The blocks are returned as the errors, so a caller that reached here
      wrongly still shows the user the real reason instead of a bare failure.

      IS IT STILL THE SAME FILE.  Every element the plan closed over is re-checked against
      the loaded configuration.  A preview can sit on screen while the user deletes the
      Task it describes in another dialog, and a refactor that ran against a detached
      element would rewrite a tree nothing renders from -- silently doing nothing, or
      worse, resurrecting a deleted Task by registering a copy of it.

      DID IT WORK.  Anything the operation itself could not do comes back as an error, and
      a raise from inside it is caught rather than escaping into the GUI -- a half-applied
      refactor is exactly what the undo checkpoint below exists for, and the user needs to
      be told, not shown a traceback.

    ONE undo block around the whole thing, and the outermost one.  Extract writes a new
    Task, edits an old one and edits a Project; those are one thing the user did and cost
    one press of Undo, which is what sessundo's re-entrancy is for (see its note on
    deleting a Project, which runs ten mutators for one undoable action).
    """
    if plan.blocks:
        return False, [block.explanation for block in plan.blocks]
    if plan.run is None:
        return False, ["There is nothing to apply."]

    attached = maputil2.attached_elements(state=state)
    if any(id(element) not in attached for element in plan.elements):
        return False, [
            (
                "Something this refactor was going to change is no longer in the configuration -- it was "
                "deleted, or another file was loaded, while this preview was open.  Nothing was changed.  "
                "Build the preview again."
            ),
        ]

    with sessundo.undoable(plan.what, state=state):
        try:
            errors = plan.run()
        except (AttributeError, KeyError, TypeError, ValueError) as failure:
            logger.error(f"Refactor '{plan.what}' failed: {failure}")
            return False, [f"{plan.what} could not be completed: {failure}"]

    return not errors, errors
