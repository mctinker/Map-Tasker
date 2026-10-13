"""maprefac_extract: a run of a Task's actions becomes a Task of its own (extract), and a Perform Task becomes the actions of the Task it calls (inline)."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from maptasker.src.core.editcommon import set_child_text as _set_child_text
from maptasker.src.core.mapjump import PROJECT, TASK, Target
from maptasker.src.edit import profedit, taskedit, taskedit_model, taskedit_save
from maptasker.src.mapops.maprefac_model import (
    EXTRACT,
    INLINE,
    PARAMETERS,
    Block,
    Plan,
    Step,
    action_code,
    action_name,
    actions_of,
    blocked,
    control_flow_codes,
    control_flow_imbalance,
    describe_actions,
    extract_scope,
    goto_numbers,
    local_names,
    object_table,
    perform_task_callers,
    projects_listing,
    renumber,
    shared_locals_warning,
    string_argument,
    task_target,
    variable_names,
)

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from maptasker.src.core.primitem import RunState

# ##################################################################################
# Extract: a run of actions becomes a Task, and a Perform Task takes its place.
# ##################################################################################

# The shape Tasker writes for a Perform Task, measured rather than guessed.  Of the 9,901
# Perform Task actions in this repo's sample XML, 6,982 carry exactly these twelve children
# and no others (the rest add a <label>, an attached <ConditionList>, or both), and the
# value written below is the commonest for every single argument: <var>%priority</var> in
# 8,540 of them, arg10=1 in 7,773, and 0 for arg5/arg6/arg8/arg9 in between 8,485 and 9,299.
#
# %priority rather than a number is Tasker's own default and the only one that is right
# here: it means "run at the priority of the Task that called me", which is exactly what the
# extracted actions were doing a moment ago as part of that Task.
#
# The order is arg0, arg1, arg10, arg2 ... arg9, which looks like a mistake and is not:
# Tasker sorts an action's argument children by their 'sr' as TEXT.  Written in that order
# for the reason mapswap_model.order_action_children gives -- an action built in a different
# order than Tasker would have written it is a screenful of moved lines in any diff, all
# of it noise around the one line that is the actual change.
_PERFORM_TASK_TEMPLATE = (
    ("Int", "arg10", "1"),
    ("Str", "arg2", ""),
    ("Str", "arg3", ""),
    ("Str", "arg4", ""),
    ("Int", "arg5", "0"),
    ("Int", "arg6", "0"),
    ("Str", "arg7", ""),
    ("Int", "arg8", "0"),
    ("Int", "arg9", "0"),
)


def _new_perform_task(element_cls: type, task_name: str) -> Element:
    """A Perform Task action calling `task_name`, built from nothing.

    Built here rather than through taskedit.add_action_to_task because that route refuses:
    classify_action_addability blocks Perform Task, on the grounds that its 'Name' argument
    has no category it can generate a default for.  That is the right answer to the question
    the Add Action dialog asks -- offer the user an action with an unfillable argument and
    they can never finish it -- and the wrong answer here, where the name is not a default to
    be invented but the whole point of the call, known before the element exists.

    sr="act0" is a placeholder; the caller renumbers every action in the Task afterwards.
    """
    action = element_cls("Action", {"sr": "act0", "ve": "7"})

    code = element_cls("code")
    code.text = taskedit_model.PERFORM_TASK_ACTION_CODE
    action.append(code)

    name = element_cls("Str", {"sr": f"arg{taskedit_model.PERFORM_TASK_NAME_ARG_ID}", "ve": "3"})
    name.text = task_name
    action.append(name)

    priority = element_cls("Int", {"sr": "arg1"})
    variable = element_cls("var")
    variable.text = "%priority"
    priority.append(variable)
    action.append(priority)

    for tag, sr_value, value in _PERFORM_TASK_TEMPLATE:
        if tag == "Int":
            action.append(element_cls("Int", {"sr": sr_value, "val": value}))
        else:
            child = element_cls("Str", {"sr": sr_value, "ve": "3"})
            child.text = value
            action.append(child)

    return action


def plan_extract(task_id: str, action_numbers: list[int], new_task_name: str, state: RunState) -> Plan:
    """Move a run of a Task's actions into a new Task, leaving a Perform Task behind.

    `action_numbers` are the numbers the MAP PRINTS -- counting from 1, in run order, which
    is what every report in this program reports and what the pulldowns offer.  They are
    neither indices into findall("Action") (see actions_of) nor sr="actN" suffixes (see
    renumber, which is the only thing here that counts from zero).

    The run has to be CONTIGUOUS, and that is not a simplification to be lifted later.
    Extract actions 2 and 5 and there is one Perform Task to put back but two holes to put
    it in: whichever is chosen, actions 3 and 4 change places with action 5 relative to each
    other, which is a reordering the user did not ask for and would not see.  A refusal that
    says so is a better answer than a rule for guessing.

    The Perform Task is written at the position the run started, so what runs when is
    unchanged -- with the one exception the warnings are about, which is local variables.
    """
    entry = object_table("all_tasks", state=state).get(task_id)
    if entry is None:
        return blocked(EXTRACT, "Extract actions into a new Task", Block("NO-TASK", "That Task is not in this file."))

    task_element = entry["xml"]
    task_name = entry.get("name", "") or task_id
    where = task_target(task_id, state=state)
    all_actions = actions_of(task_element)

    wanted = sorted({int(number) for number in action_numbers})
    new_name = (new_task_name or "").strip()
    which = describe_actions(wanted) if wanted else "actions"
    what = f"Extract {which} of Task '{task_name}' into a new Task '{new_name}'"

    scope = extract_scope(state=state)
    if not scope.allows(TASK, task_id):
        # Belt to the filtered pulldown's braces.  The picker does not offer an
        # out-of-scope Task, but a dialog can sit open while the user changes what the Map
        # is showing, and a plan built before that must not be applied after it.
        return blocked(
            EXTRACT,
            what,
            Block(
                "OUT-OF-SCOPE",
                f"Task '{task_name}' is not among the Tasks {scope.phrase} covers.  Extract works on "
                f"the Task selected in the pulldowns, the same way the Edit buttons beside it do.  "
                f"Change or clear that selection to reach other Tasks.",
                where,
            ),
        )

    block = _extract_block(all_actions, wanted, new_name, where, state=state)
    if block is not None:
        return blocked(EXTRACT, what, block)

    moving = [all_actions[number - 1] for number in wanted]
    kept = [action for number, action in enumerate(all_actions, start=1) if number not in set(wanted)]
    owners = projects_listing("tids", task_id, state=state)

    plan = Plan(kind=EXTRACT, what=what, elements=(task_element, *all_actions))
    plan.steps = _extract_steps(moving, wanted, new_name, task_name, where, owners)
    plan.warnings = _extract_warnings(moving, kept, task_name, owners)

    def run() -> list[str]:
        """Move the elements, write the call, register the Task, file it under a Project."""
        priority = task_element.findtext("pri", "") or "100"
        new_task = taskedit.create_new_task(new_name, priority, state=state)
        if isinstance(new_task, str):
            return [new_task]

        # The elements themselves move; they are not copied.  A copy would be a second set
        # of elements holding the same plugin payloads, icons and conditions, and the first
        # set would then have to be deleted -- two operations that can disagree, where this
        # is one that cannot.
        for action in moving:
            task_element.remove(action)
            new_task.task_element.append(action)
        renumber(moving)

        call = _new_perform_task(type(task_element), new_name)
        task_element.append(call)
        # wanted[0] is a displayed number; the split in `kept` is an index.
        before = wanted[0] - 1
        renumber([*kept[:before], call, *kept[before:]])

        taskedit_save.register_new_task(new_task, new_name, state=state)
        for project_name in owners:
            profedit.add_task_to_project(new_task.task_id, project_name, state=state)
        return []

    plan.run = run
    return plan


def _extract_block(all_actions: list, wanted: list[int], new_name: str, where: Target, state: RunState) -> Block | None:
    """The one reason this extract will not be done, or None.

    One rather than all of them: the checks are ordered from the user's mistake outwards,
    and a run that is not contiguous has not got a meaningful If balance to report on.
    """
    if not wanted:
        return Block("NO-ACTIONS", "No actions were selected to extract.", where)
    if wanted[0] < 1 or wanted[-1] > len(all_actions):
        return Block(
            "OUT-OF-RANGE",
            f"This Task has {len(all_actions)} actions, numbered 1 to {len(all_actions)}, and the "
            f"selection reaches outside that.  It may have been edited since this preview was built.",
            where,
        )
    if wanted != list(range(wanted[0], wanted[-1] + 1)):
        missing = sorted(set(range(wanted[0], wanted[-1] + 1)) - set(wanted))
        return Block(
            "NOT-CONTIGUOUS",
            f"The selected actions have gaps in them ({', '.join(str(number) for number in missing[:6])} "
            f"{'is' if len(missing) == 1 else 'are'} in between and not selected).  One Perform Task can "
            f"only stand in one place, so extracting a run with holes would silently reorder the actions "
            f"left behind.  Select an unbroken run.",
            where,
        )
    if not new_name:
        return Block("NO-NAME", "The new Task needs a name.", where)
    if taskedit.task_name_exists(new_name, state=state):
        return Block(
            "NAME-TAKEN",
            f"A Task named '{new_name}' is already in this file.  Perform Task calls a Task by name, so "
            f"two Tasks sharing one would leave it ambiguous which of them this call runs.",
            where,
        )

    imbalance = control_flow_imbalance([(number, all_actions[number - 1]) for number in wanted])
    if imbalance:
        return Block(
            "UNBALANCED-BLOCK",
            f"The selection is not self-contained: {imbalance}.  Moving it would leave the actions on the "
            f"other side of the split running under a condition, or a loop, that is no longer there.  "
            f"Extend the selection to take in the whole block.",
            where,
        )

    gotos = goto_numbers(all_actions)
    if gotos:
        listed = ", ".join(str(number) for number in gotos[:6])
        return Block(
            "GOTO-PRESENT",
            f"This Task contains a Goto (action {listed}).  A Goto addresses an action by its NUMBER, and "
            f"extracting anything renumbers every action after it -- so the jump would still be valid and "
            f"would land somewhere else.  Nothing here can tell which action it was aiming at.",
            where,
        )
    return None


def _extract_steps(
    moving: list,
    wanted: list[int],
    new_name: str,
    task_name: str,
    where: Target,
    owners: list[str],
) -> list[Step]:
    """What an extract will do, in order, one line each."""
    first = wanted[0]
    steps = [
        Step(
            f"Create Task '{new_name}' holding {len(moving)} "
            f"{'action' if len(moving) == 1 else 'actions'}: "
            + ", ".join(action_name(action) for action in moving[:4])
            + (", ..." if len(moving) > 4 else ""),
        ),
        Step(
            f"Remove {describe_actions(wanted)} from Task '{task_name}'",
            where.at_action(first),
        ),
        Step(f"Put a Perform Task '{new_name}' in their place, as action {first}", where.at_action(first)),
    ]
    if owners:
        steps.extend(
            Step(f"Add Task '{new_name}' to Project '{project_name}'", Target(kind=PROJECT, key=project_name))
            for project_name in owners
        )
    else:
        steps.append(Step(f"Task '{new_name}' is filed under no Project, because Task '{task_name}' is not either"))
    return steps


def _extract_warnings(moving: list, kept: list, task_name: str, owners: list[str]) -> list[str]:
    """What is true of this extract that the user should read before doing it."""
    warnings = []

    shared = shared_locals_warning(moving, kept, "in a Task of their own")
    if shared:
        warnings.append(shared)

    parameters = sorted(name for name in variable_names(moving) if name.lower() in PARAMETERS)
    if parameters:
        warnings.append(
            f"The actions being moved use {', '.join(parameters)}.  Those are the parameters of whatever "
            f"called this Task, and after the move they will be the new Task's parameters instead -- which "
            f"the Perform Task being written does not pass anything into.",
        )

    if not kept:
        warnings.append(
            "Every action in this Task is being extracted, so what is left is a Task whose only action is a "
            "call to the new one.  That is a valid thing to want; it is worth being sure it is what you meant.",
        )

    labelled = [action for action in moving if action.find("label") is not None]
    if labelled:
        warnings.append(
            f"{len(labelled)} of the actions being moved {'carries' if len(labelled) == 1 else 'carry'} a "
            f"label.  Labels travel with their action and are not rewritten, so any that describe this Task "
            f"by name will now say so from inside another.",
        )

    if len(owners) > 1:
        warnings.append(
            f"Task '{task_name}' is listed by {len(owners)} Projects ({', '.join(owners)}), so the new Task "
            f"is added to all of them -- the same arrangement the original is in.",
        )
    return warnings


# ##################################################################################
# Inline: a Perform Task becomes the actions of the Task it calls.
#
# The mirror of extract, and the harder direction.  Extract splits one scope into two,
# which loses shared locals; inline MERGES two scopes into one, which is worse, because
# nothing is lost -- two variables that were separate quietly become the same variable.
# A %count the called Task uses as a loop counter and a %count the calling Task uses for
# something else have never met before and now overwrite each other.
#
# Both are warnings rather than blocks, for the same reason: they are frequently exactly
# what the user wants (that is often WHY somebody inlines a Task), and they are never
# something the tool can decide on its own.  What it can do is name the variables.
# ##################################################################################

_CONDITION_LIST = "ConditionList"


def plan_inline(task_id: str, action_number: int, state: RunState) -> Plan:
    """Replace one Perform Task with a copy of the actions of the Task it calls.

    A COPY, and the called Task is left exactly where it is.  Anything else would be two
    operations wearing one name: a Task called from six places, inlined at one of them and
    then deleted, breaks the other five.  Whether the called Task is now unused is a
    question this answers -- see the callers warning -- and deleting it stays the user's
    own click.
    """
    entry = object_table("all_tasks", state=state).get(task_id)
    if entry is None:
        return blocked(INLINE, "Inline a Perform Task", Block("NO-TASK", "That Task is not in this file."))

    task_element = entry["xml"]
    task_name = entry.get("name", "") or task_id
    where = task_target(task_id, state=state)
    all_actions = actions_of(task_element)

    if not 1 <= action_number <= len(all_actions):
        return blocked(
            INLINE,
            f"Inline action {action_number} of Task '{task_name}'",
            Block(
                "NO-ACTION",
                f"Task '{task_name}' has no action {action_number}.  It may have been edited since this "
                f"preview was built.",
                where,
            ),
        )

    call = all_actions[action_number - 1]
    called_name = string_argument(call, taskedit_model.PERFORM_TASK_NAME_ARG_ID)
    what = f"Inline Perform Task '{called_name}' at action {action_number} of Task '{task_name}'"

    called = object_table("all_tasks_by_name", state=state).get(called_name)
    block = _inline_block(call, called_name, called, task_id, where.at_action(action_number))
    if block is not None:
        return blocked(INLINE, what, block)

    if called is None:  # _inline_block has already blocked a missing Task; this is for the type checker.
        return blocked(
            INLINE,
            what,
            Block("NO-SUCH-TASK", f"'{called_name}' is not a Task in this file.", where.at_action(action_number)),
        )
    called_element = called["xml"]
    called_actions = actions_of(called_element)
    condition = call.find(_CONDITION_LIST)
    label = call.find("label")
    disabled = (call.findtext("on") or "") == "false"
    kept = [action for number, action in enumerate(all_actions, start=1) if number != action_number]

    plan = Plan(
        kind=INLINE,
        what=what,
        elements=(task_element, called_element, call, *all_actions, *called_actions),
    )
    plan.steps = _inline_steps(
        called_name, called_actions, task_name, action_number, where, condition, disabled, state=state
    )
    plan.warnings = _inline_warnings(call, called_name, called_actions, kept, state=state)

    def run() -> list[str]:
        """Copy the called Task's actions in, carrying over what the call itself said."""
        copies = [copy.deepcopy(action) for action in called_actions]

        for index, action in enumerate(copies):
            # The call's own condition and disabled flag are statements about WHETHER this
            # runs, and inlining must not quietly turn them off.  Distributed over every
            # copy, which is equivalent because the block above refused the two shapes where
            # it would not be -- flow control among the copies, and a copy with a condition
            # of its own.
            if condition is not None:
                action.append(copy.deepcopy(condition))
            if disabled:
                _set_child_text(action, "on", "false")
            # The call's label describes the call, so it belongs on the action that now
            # stands where the call did -- but only when that action has none of its own,
            # which is what the warning covers.
            if index == 0 and label is not None and action.find("label") is None:
                action.append(copy.deepcopy(label))

        task_element.remove(call)
        for action in copies:
            task_element.append(action)
        # action_number is a displayed number; the split in `kept` is an index.
        before = action_number - 1
        renumber([*kept[:before], *copies, *kept[before:]])
        return []

    plan.run = run
    return plan


def _inline_block(
    call: Element,
    called_name: str,
    called: dict | None,
    task_id: str,
    where: Target,
) -> Block | None:
    """The one reason this inline will not be done, or None."""
    if action_code(call) != taskedit_model.PERFORM_TASK_ACTION_CODE:
        return Block(
            "NOT-A-CALL",
            f"That action is a {action_name(call)}, not a Perform Task.  There is nothing to inline.",
            where,
        )
    if not called_name:
        return Block("NO-NAME", "This Perform Task names no Task to run.", where)
    if "%" in called_name:
        return Block(
            "INDIRECT-NAME",
            f"This call runs '{called_name}', which is decided by a variable when the Task runs.  Which "
            f"Task's actions to inline is not knowable from the file.",
            where,
        )
    if called is None:
        return Block(
            "NO-SUCH-TASK",
            f"'{called_name}' is not a Task in this file, so this call is already broken.  Point it at a "
            f"Task that exists, or delete it.",
            where,
        )
    if called["id"] == task_id:
        return Block(
            "SELF-CALL",
            f"'{called_name}' is this same Task.  Inlining it into itself would copy its actions into the "
            f"middle of themselves, and the copy would still hold the call.",
            where,
        )

    called_actions = actions_of(called["xml"])
    gotos = goto_numbers(called_actions)
    if gotos:
        listed = ", ".join(str(number) for number in gotos[:6])
        return Block(
            "GOTO-IN-CALLED-TASK",
            f"Task '{called_name}' contains a Goto (action {listed}).  A Goto addresses an action by its "
            f"NUMBER, and inlining shifts every one of these actions by however many come before them in "
            f"the calling Task -- so the jump would land on an unrelated action rather than fail.",
            where,
        )

    if call.find(_CONDITION_LIST) is not None:
        flow = control_flow_codes(called_actions)
        if flow:
            return Block(
                "CONDITIONAL-BLOCK",
                f"This call runs only if its own condition is met, and Task '{called_name}' contains "
                f"If/For actions.  The condition can be carried onto each inlined action one at a time, "
                f"but not onto a block -- an If whose condition was false would have its End If skipped "
                f"and the rest of the Task would run inside a block that never opened.",
                where,
            )
        conditioned = [
            number for number, action in enumerate(called_actions, start=1) if action.find(_CONDITION_LIST) is not None
        ]
        if conditioned:
            listed = ", ".join(str(number) for number in conditioned[:6])
            return Block(
                "CONDITION-ON-CONDITION",
                f"This call has a condition of its own, and so does action {listed} of Task "
                f"'{called_name}'.  Both would have to hold, and combining two conditions into one is a "
                f"decision about the user's intent that this tool will not make on its own.",
                where,
            )
    return None


def _inline_steps(
    called_name: str,
    called_actions: list,
    task_name: str,
    action_number: int,
    where: Target,
    condition: object,
    disabled: bool,
    state: RunState,
) -> list[Step]:
    """What an inline will do, in order, one line each."""
    count = len(called_actions)
    called_entry = object_table("all_tasks_by_name", state=state).get(called_name)
    called_where = task_target(called_entry["id"], state=state) if called_entry else None
    steps = [
        Step(
            f"Remove the Perform Task at action {action_number} of Task '{task_name}'",
            where.at_action(action_number),
        ),
        Step(
            f"Put {count} {'action' if count == 1 else 'actions'} copied from Task '{called_name}' in its "
            "place: "
            + ", ".join(action_name(action) for action in called_actions[:4])
            + (", ..." if count > 4 else ""),
            called_where,
        ),
    ]
    if condition is not None:
        steps.append(Step(f"Carry the call's condition onto each of the {count} copied actions"))
    if disabled:
        steps.append(Step(f"Carry the call's disabled state onto each of the {count} copied actions"))
    steps.append(Step(f"Leave Task '{called_name}' itself exactly as it is"))
    return steps


def _inline_warnings(
    call: Element,
    called_name: str,
    called_actions: list,
    kept: list,
    state: RunState,
) -> list[str]:
    """What is true of this inline that the user should read before doing it."""
    warnings = []

    if not called_actions:
        warnings.append(
            f"Task '{called_name}' has no actions, so this inline removes the call and puts nothing in its place.",
        )

    collisions = sorted(local_names(called_actions) & local_names(kept))
    if collisions:
        listed = ", ".join(collisions[:8]) + (", ..." if len(collisions) > 8 else "")
        warnings.append(
            f"{listed} {'is' if len(collisions) == 1 else 'are'} used by both Tasks.  They are separate "
            f"variables today, because Tasker scopes a lower case name to the Task that is running; after "
            f"this they are one, and each Task's values will overwrite the other's.",
        )

    parameters = sorted(name for name in variable_names(called_actions) if name.lower() in PARAMETERS)
    passed = [value for value in (string_argument(call, "2"), string_argument(call, "3")) if value]
    if parameters:
        detail = f" This call passes {', '.join(passed)}." if passed else " This call passes nothing."
        warnings.append(
            f"Task '{called_name}' reads {', '.join(parameters)} -- the parameters of whatever called it."
            f"{detail}  Inlined, those actions will read the CALLING Task's parameters instead, which are "
            f"a different thing entirely.",
        )

    returned = string_argument(call, "4")
    if returned:
        warnings.append(
            f"This call puts the called Task's return value into {returned}.  Inlined actions do not return "
            f"anything, so nothing will set {returned} any more.",
        )

    if call.find("label") is not None and called_actions and called_actions[0].find("label") is not None:
        warnings.append(
            f"The call carries a label and so does the first action of '{called_name}'.  The action keeps "
            f"its own, and the call's label is not preserved.",
        )

    remaining = len(perform_task_callers(called_name, state=state)) - 1
    if remaining > 0:
        warnings.append(
            f"{remaining} other {'call' if remaining == 1 else 'calls'} to '{called_name}' "
            f"{'remains' if remaining == 1 else 'remain'} elsewhere in this file, so the Task is still "
            f"needed and is left in place.",
        )
    elif remaining == 0:
        warnings.append(
            f"Nothing else calls '{called_name}'.  It is left in place either way -- deleting a Task is its "
            f"own decision, and Perform Task is not the only way a Task can be reached (a home screen "
            f"widget or a Tasker shortcut leaves no trace in this file).",
        )
    return warnings
