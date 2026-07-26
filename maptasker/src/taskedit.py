"""taskedit: build an editable model of a Task and save it as a standalone .tsk.xml file.

Edit Task: edit an existing Task's name/priority and the values of arguments its
actions already have in the XML. Never touches PrimeItems.xml_tree -- all edits
happen on a deep copy, and the only output is a new standalone file.

Add Task: create a brand-new Task and populate it with newly-synthesized actions.
Only actions whose arguments are all plain numbers/text/checkboxes (or the purely
informational 'Output Variables' Bundle hint) can be synthesized from scratch --
see classify_action_addability() for the exact rule. Never touches the live tree
either; a new Task exists only in memory until saved.
"""

from __future__ import annotations

import copy
import json
import os
import re
import time
import xml.etree.ElementTree as ETW  # stdlib "ET Write" -- used only to build/serialize
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import defusedxml.ElementTree

from maptasker.src.actionc import action_codes
from maptasker.src.actiont import lookup_values
from maptasker.src.primitem import PrimeItems
from maptasker.src.shelsort import shell_sort

XML_DECLARATION = '<?xml version = "1.0" encoding = "UTF-8" standalone = "no" ?>\n'


@dataclass
class EditableArg:
    """One editable (or read-only) argument belonging to an Action."""

    arg_id: str
    arg_name: str
    widget_kind: str  # "checkbox" | "dropdown" | "text" | "raw_fallback" | "readonly"
    backing_tag: str  # "Int" | "Str" | ""
    is_var: bool
    element: defusedxml.ElementTree.Element | None
    current_value: str
    dropdown_options: list[str] | None = None
    readonly_note: str = ""


@dataclass
class EditableAction:
    """One Action element and its editable arguments, in execution order."""

    action_element: defusedxml.ElementTree.Element
    act_number: int
    code: str
    action_name: str
    args: list[EditableArg] = field(default_factory=list)


@dataclass
class EditableTask:
    """A deep-copied Task element plus its editable-action model."""

    task_id: str
    task_element: defusedxml.ElementTree.Element
    actions: list[EditableAction] = field(default_factory=list)


# The "If" action (code 37) has no Bundle/Int/Str args of its own -- its condition
# lives in a sibling <ConditionList sr="if"><Condition sr="c0" ve="3"><lhs/><op/>
# <rhs/></Condition></ConditionList>, e.g.:
#   <Action sr="act1" ve="7"><code>37</code>
#     <ConditionList sr="if"><Condition sr="c0" ve="3">
#       <lhs>%awcomm</lhs><op>2</op><rhs>&lt;aid_vol_down&gt;</rhs>
#     </Condition></ConditionList>
#   </Action>
# action.py's evaluate_condition already reads these same 12 op codes purely for
# display; this is the write-side (label <-> code) mapping for the Operator
# dropdown _build_if_condition_args/apply_arg_values build and write. Codes 8/9
# ("=(Numeric)"/"!=(Numeric)") are kept distinct from 0/1 -- both display as "="/
# "!=" in action.py's own read-only table, but they're written differently by real
# Tasker (all four appear in real backups), so collapsing them would silently
# change an edited action's meaning.
IF_ACTION_KEY = "37t"
ELSE_ACTION_KEY = "43t"
END_IF_ACTION_KEY = "38t"
IF_ACTION_CODE = IF_ACTION_KEY[:-1]
ELSE_ACTION_CODE = ELSE_ACTION_KEY[:-1]
END_IF_ACTION_CODE = END_IF_ACTION_KEY[:-1]

# The choices build_if_variant_dialog offers when the user picks the "If"
# action, mapped to the arg-less follower actions to insert right after it
# (both Else and End If have args=[] in actionc.py, so add_action_to_task can
# always synthesize them).
PERFORM_TASK_ACTION_CODE = "130"  # "Perform Task" (action_codes["130t"])
PERFORM_TASK_NAME_ARG_ID = "0"  # its "Name" arg

IF_BLOCK_VARIANTS: tuple[str, ...] = ("If", "If, End If", "If, Else, End If")
_IF_BLOCK_FOLLOWERS: dict[str, tuple[str, ...]] = {
    "If": (),
    "If, End If": (END_IF_ACTION_KEY,),
    "If, Else, End If": (ELSE_ACTION_KEY, END_IF_ACTION_KEY),
}
IF_CONDITION_OPERATORS: tuple[tuple[str, str], ...] = (
    ("0", "="),
    ("1", "!="),
    ("2", "~ (Matches)"),
    ("3", "!~ (Doesn't Match)"),
    ("4", "~R (Matches Regex)"),
    ("5", "!~R (Doesn't Match Regex)"),
    ("6", "<"),
    ("7", ">"),
    ("8", "= (Numeric)"),
    ("9", "!= (Numeric)"),
    ("12", "Is Set"),
    ("13", "Not Set"),
)
_IF_CONDITION_OPERATOR_LABELS = [label for _, label in IF_CONDITION_OPERATORS]
_IF_CONDITION_CODE_TO_INDEX = {code: i for i, (code, _label) in enumerate(IF_CONDITION_OPERATORS)}
_IF_CONDITION_LABEL_TO_CODE = {label: code for code, label in IF_CONDITION_OPERATORS}


def resolve_task_by_name(task_name: str) -> tuple[str, defusedxml.ElementTree.Element] | None:
    """Look up a Task's id and live XML element by its displayed name.

    Returns (task_id, live_element), or None if not found. Callers must not mutate
    the returned element directly -- go through load_task_for_edit() instead.
    """
    entry = PrimeItems.tasker_root_elements["all_tasks_by_name"].get(task_name)
    if entry is None:
        return None
    return entry["id"], entry["xml"]


def load_task_for_edit(task_name: str) -> EditableTask | None:
    """Resolve a Task by name, deep-copy it, and build its editable-action model.

    This is the one point of contact with the live tree -- everything downstream
    (including Save) operates on the copy, so the in-memory backup is never touched.
    """
    resolved = resolve_task_by_name(task_name)
    if resolved is None:
        return None
    task_id, live_element = resolved
    task_copy = copy.deepcopy(live_element)
    return EditableTask(
        task_id=task_id,
        task_element=task_copy,
        actions=_build_editable_actions(task_copy),
    )


def create_new_task(name: str, priority: str) -> EditableTask | str:
    """Build a brand-new Task element, not tied to any existing one, ready for
    actions to be added to it. Returns an error message string if no backup is
    loaded -- needed both to generate a collision-free id and to source the correct
    Element class (see write_standalone_task_xml's note on class mismatches).
    """
    if PrimeItems.xml_root is None:
        return "Load a Tasker backup file first (Add Task needs it to generate a unique Task ID)."

    existing_ids = [int(k) for k in PrimeItems.tasker_root_elements.get("all_tasks", {}) if k.isdigit()]
    new_id = max(existing_ids, default=0) + 1

    element_cls = type(PrimeItems.xml_root)
    task_element = element_cls("Task", {"sr": f"task{new_id}"})

    now_millis = str(int(time.time() * 1000))
    for tag, text in (
        ("cdate", now_millis),
        ("edate", now_millis),
        ("id", str(new_id)),
        ("nme", name.strip()),
        ("pri", priority.strip() or "100"),
    ):
        child = element_cls(tag)
        child.text = text
        task_element.append(child)

    return EditableTask(task_id=str(new_id), task_element=task_element, actions=[])


def add_action_to_task(
    edited_task: EditableTask,
    action_key: str,
    position: int | None = None,
) -> EditableAction | list[str]:
    """Synthesize a new Action element from scratch and add it to the task --
    appended at the end by default (position=None), or inserted at `position`
    (0-based, among the task's other actions -- clamped to a valid index) if
    given, so a caller can place it before or after a specific existing
    action instead of always at the end. See build_edit_task_dialog's own
    "Add an action" section, which offers exactly that choice; Add Task's
    picker always appends (position=None) since there's nothing to insert
    relative to until the user's already added something.

    Re-checks addability even though the UI shouldn't offer a non-addable action --
    defense in depth, matching apply_edits_to_task's list[str]-errors convention.
    """
    addable, reason = classify_action_addability(action_key)
    if not addable:
        return [reason or f"'{action_key}' is not addable."]

    code = action_key[:-1]
    action_code = action_codes[action_key]
    effective_args = action_codes[action_code.redirect].args if action_code.redirect else action_code.args

    act_number = len(edited_task.actions)
    element_cls = type(edited_task.task_element)

    action_element = element_cls("Action", {"sr": f"act{act_number}", "ve": "7"})
    code_element = element_cls("code")
    code_element.text = code
    action_element.append(code_element)

    if action_key == IF_ACTION_KEY:
        args = _synthesize_if_condition(element_cls, action_element)
    else:
        args = build_synthesized_args(element_cls, action_element, effective_args)

    edited_task.task_element.append(action_element)

    new_action = EditableAction(
        action_element=action_element,
        act_number=act_number,
        code=code,
        action_name=action_code.name,
        args=args,
    )
    if position is None:
        edited_task.actions.append(new_action)
    else:
        edited_task.actions.insert(max(0, min(position, len(edited_task.actions))), new_action)
        _renumber_actions(edited_task)
    return new_action


def add_if_block_to_task(
    edited_task: EditableTask,
    variant: str,
    position: int | None = None,
) -> EditableAction | list[str]:
    """Insert an "If" action plus whatever companions the chosen variant calls
    for (see IF_BLOCK_VARIANTS): nothing extra for "If", an "End If" after it
    for "If, End If", or an "Else" then an "End If" for "If, Else, End If" --
    all as consecutive actions starting at `position` (same semantics as
    add_action_to_task's: None appends at the end).

    Returns the "If" action itself on success (the companions need no further
    attention -- they're arg-less), or a list of error strings, matching
    add_action_to_task's convention.
    """
    if_action = add_action_to_task(edited_task, IF_ACTION_KEY, position)
    if isinstance(if_action, list):
        return if_action

    insert_at = edited_task.actions.index(if_action) + 1
    for follower_key in _IF_BLOCK_FOLLOWERS.get(variant, ()):
        follower = add_action_to_task(edited_task, follower_key, insert_at)
        if isinstance(follower, list):
            return follower
        insert_at += 1
    return if_action


def action_display_levels(actions: list[EditableAction]) -> list[int]:
    """Per-action If-nesting depth for indenting a Task's action list in the
    Add/Edit Task dialogs: every action after an "If" sits one level deeper;
    "Else" and "End If" render at their encapsulating "If"'s own level, with
    "End If" also popping back out so anything after it returns to the outer
    level. Nested "If"s stack a level each. An unbalanced "Else"/"End If"
    clamps at level 0 rather than going negative -- a Task's actions are free
    text as far as Tasker is concerned, so malformed nesting must still render.
    """
    levels = []
    depth = 0
    for action in actions:
        if action.code in (ELSE_ACTION_CODE, END_IF_ACTION_CODE):
            levels.append(max(depth - 1, 0))
        else:
            levels.append(depth)
        if action.code == IF_ACTION_CODE:
            depth += 1
        elif action.code == END_IF_ACTION_CODE:
            depth = max(depth - 1, 0)
    return levels


def _renumber_actions(edited_task: EditableTask) -> None:
    """Renumber every action's sr="actN" (and its act_number) to match its current
    position in edited_task.actions -- shared by remove/copy/move so the model and
    the XML always agree on order. XML child order is irrelevant to Tasker; it
    orders Actions by the numeric suffix of sr="actN", not document order (Tasker
    itself writes them out-of-order in the file -- see _build_editable_actions), so
    this is the only bookkeeping a reorder needs.
    """
    for new_number, action in enumerate(edited_task.actions):
        action.action_element.set("sr", f"act{new_number}")
        action.act_number = new_number


def remove_action_from_task(edited_task: EditableTask, act_number: int) -> None:
    """Remove an action (by its current act_number) from both the XML and the
    model, then renumber every remaining action's sr="actN" contiguously from 0 in
    their current order.
    """
    target = next((a for a in edited_task.actions if a.act_number == act_number), None)
    if target is None:
        return

    edited_task.task_element.remove(target.action_element)
    edited_task.actions = [a for a in edited_task.actions if a is not target]

    _renumber_actions(edited_task)


def copy_action_in_task(edited_task: EditableTask, act_number: int) -> EditableAction | None:
    """Duplicate the action currently numbered act_number, inserting the copy
    immediately after it in the model, then renumber every action's sr="actN" to
    match (XML child order doesn't matter -- see _renumber_actions).

    Returns the new (copied) action, or None if act_number wasn't found.
    """
    source_index = next((i for i, a in enumerate(edited_task.actions) if a.act_number == act_number), None)
    if source_index is None:
        return None

    source = edited_task.actions[source_index]
    new_element = copy.deepcopy(source.action_element)
    edited_task.task_element.append(new_element)

    new_action = _build_editable_action(new_element, source.act_number)
    edited_task.actions.insert(source_index + 1, new_action)

    _renumber_actions(edited_task)
    return new_action


def move_action_in_task(edited_task: EditableTask, act_number: int, new_position: int) -> bool:
    """Move the action currently numbered act_number to new_position (0-based,
    among the task's other actions), then renumber every action's sr="actN" to
    match (XML child order doesn't matter -- see _renumber_actions).

    new_position is clamped to a valid index. Returns True if the move was
    performed, False if act_number wasn't found.
    """
    source_index = next((i for i, a in enumerate(edited_task.actions) if a.act_number == act_number), None)
    if source_index is None:
        return False

    new_position = max(0, min(new_position, len(edited_task.actions) - 1))
    action = edited_task.actions.pop(source_index)
    edited_task.actions.insert(new_position, action)

    _renumber_actions(edited_task)
    return True


def is_action_enabled(action: EditableAction) -> bool:
    """Whether this Action is enabled -- mirrors action.py's own display logic,
    which treats an <on> child as "disabled" (Tasker always writes it as
    <on>false</on> when present) and its absence as "enabled". Same shape as
    profedit.is_profile_enabled for a Profile's <limit>.
    """
    on = action.action_element.find("on")
    return on is None or on.text != "false"


def set_action_enabled(edited_task: EditableTask, act_number: int, enabled: bool) -> None:
    """Enables or disables the action currently numbered act_number by removing/
    setting its <on> child -- applied immediately (not staged), same as
    profedit.set_profile_enabled. Takes act_number rather than an EditableAction
    (and looks it up itself), matching remove/copy/move_action_in_task's own
    calling convention -- the GUI's per-action buttons only close over act_number.
    """
    action = next((a for a in edited_task.actions if a.act_number == act_number), None)
    if action is None:
        return

    if enabled:
        on = action.action_element.find("on")
        if on is not None:
            action.action_element.remove(on)
    else:
        _set_child_text(action.action_element, "on", "false")


def action_can_fail(action: EditableAction) -> bool:
    """Whether Tasker considers this action able to fail (actionc.py's canfail
    flag) -- only such actions get the 'Continue Task After Error' checkbox;
    the flag is meaningless on ones that can't error.
    """
    action_code = action_codes.get(f"{action.code}t")
    return action_code is not None and action_code.canfail == "True"


def action_continues_after_error(action: EditableAction) -> bool:
    """Whether this action carries <se>false</se> ('Continue Task After
    Error') -- the same child action.py's get_extra_stuff reads for display.
    No <se> (or any other text) means Tasker's default: stop the Task on error.
    """
    se = action.action_element.find("se")
    return se is not None and se.text == "false"


def set_action_continue_after_error(
    edited_task: EditableTask,
    act_number: int,
    continue_after_error: bool,
) -> None:
    """Sets or clears an action's <se>false</se> by writing/removing the <se>
    child -- applied immediately (not staged), same convention as
    set_action_enabled's <on> handling: Tasker omits the element entirely for
    the default (stop on error), so unchecking removes it rather than writing
    <se>true</se>.
    """
    action = next((a for a in edited_task.actions if a.act_number == act_number), None)
    if action is None:
        return

    if continue_after_error:
        _set_child_text(action.action_element, "se", "false")
    else:
        se = action.action_element.find("se")
        if se is not None:
            action.action_element.remove(se)


def _build_editable_action(action_element: defusedxml.ElementTree.Element, act_number: int) -> EditableAction:
    """Build a single EditableAction bound to an already-in-the-tree Action element.

    Shared by _build_editable_actions (initial load) and copy_action_in_task (a
    freshly-deep-copied element), so a copy's args are bound to its own Int/Str
    elements rather than the source action's.
    """
    code_element = action_element.find("code")
    code = code_element.text if code_element is not None else ""

    action_code = action_codes.get(f"{code}t")
    if action_code is None:
        return EditableAction(
            action_element=action_element,
            act_number=act_number,
            code=code,
            action_name=f"Code {code} not yet mapped",
            args=[],
        )

    if f"{code}t" == IF_ACTION_KEY:
        return EditableAction(
            action_element=action_element,
            act_number=act_number,
            code=code,
            action_name=action_code.name,
            args=_build_if_action_args(action_element),
        )

    effective_args = action_codes[action_code.redirect].args if action_code.redirect else action_code.args

    return EditableAction(
        action_element=action_element,
        act_number=act_number,
        code=code,
        action_name=action_code.name,
        args=build_editable_args(action_element, effective_args),
    )


def _build_editable_actions(task_copy: defusedxml.ElementTree.Element) -> list[EditableAction]:
    """Find the Task's Actions, sort them into execution order, and build their arg models.

    Execution order is driven by the numeric suffix of sr="actN", not document order
    (Tasker itself writes actions out-of-order in the file), so reuse the same sort
    tasks.get_actions() uses to keep this dialog's ordering identical to the rest of
    the app's views.
    """
    actions = task_copy.findall("Action")
    shell_sort(actions, True, False)

    return [_build_editable_action(action_element, _action_number(action_element)) for action_element in actions]


def _action_number(action_element: defusedxml.ElementTree.Element) -> int:
    """Extract the numeric suffix of sr="actN" for display/sort purposes only."""
    sr = action_element.attrib.get("sr", "")
    match = re.search(r"\d+$", sr)
    return int(match.group()) if match else 0


def build_editable_args(
    action_element: defusedxml.ElementTree.Element,
    effective_args: list,
) -> list[EditableArg]:
    """Classify each of an action's defined arguments into a widget kind, bound to
    whatever Int/Str element already exists in the XML for it (never synthesized).

    Public (not underscore-prefixed): this only depends on the Bundle/Int/Str
    argument structure, not specifically on being a Task Action -- Profile
    State/Event conditions use the exact same structure (see condition.py's
    condition_state/condition_event), so profedit.py reuses this directly rather
    than duplicating it.
    """
    editable_args = []
    for arg in effective_args:
        the_arg = f"arg{arg.arg_id}"
        category = PrimeItems.tasker_arg_specs.get(arg.arg_type, "")

        if category == "Boolean" or _is_checkbox_arg_eval(arg.arg_eval):
            editable_args.append(_build_boolean_arg(action_element, the_arg, arg))
        elif category == "Int":
            editable_args.append(_build_int_arg(action_element, the_arg, arg))
        elif category in ("String", "Str"):
            editable_args.append(_build_string_arg(action_element, the_arg, arg))
        else:
            editable_args.append(
                _readonly_arg(arg, f"'{category or arg.arg_type}' arguments are not editable in this version."),
            )

    return editable_args


def _find_int_element(
    action_element: defusedxml.ElementTree.Element,
    the_arg: str,
) -> defusedxml.ElementTree.Element | None:
    return action_element.find(f"./Int[@sr='{the_arg}']")


def _find_str_element(
    action_element: defusedxml.ElementTree.Element,
    the_arg: str,
) -> defusedxml.ElementTree.Element | None:
    return next(
        (child for child in action_element.findall("Str") if child.attrib.get("sr") == the_arg),
        None,
    )


def _readonly_arg(arg, note: str) -> EditableArg:
    return EditableArg(
        arg_id=arg.arg_id,
        arg_name=_display_arg_name(arg),
        widget_kind="readonly",
        backing_tag="",
        is_var=False,
        element=None,
        current_value="",
        readonly_note=note,
    )


def _readonly_note_arg(note: str) -> EditableArg:
    """Same shape as _readonly_arg, but for a synthetic note with no backing
    ArgumentCode (see _build_if_action_args' multi-condition case)."""
    return EditableArg(
        arg_id="if_note",
        arg_name="Condition",
        widget_kind="readonly",
        backing_tag="",
        is_var=False,
        element=None,
        current_value="",
        readonly_note=note,
    )


def _build_if_condition_args(condition_element: defusedxml.ElementTree.Element) -> list[EditableArg]:
    """Builds the three editable fields (Target, Operator, Value) for an 'If'
    action's single Condition test, bound directly to its existing <lhs>/<op>/
    <rhs> elements -- the write-side counterpart of action.py's evaluate_condition,
    which reads these same three elements for display. Shared by
    _synthesize_if_condition (a brand-new Condition, Add Task) and
    _build_if_action_args (an existing one, Edit Task).

    The Operator field is a "dropdown" widget_kind so it renders exactly like any
    other lookup-backed Int dropdown (see guiwins.py's generic arg rendering) --
    current_value is the *index* into IF_CONDITION_OPERATORS, matching that same
    convention -- but its backing_tag is the custom "IfOp" rather than "Int",
    since apply_arg_values has to write the selected op *code* as this element's
    text, not an index as a val attribute (see apply_arg_values' own IfOp branch).
    """
    lhs_element = condition_element.find("lhs")
    op_element = condition_element.find("op")
    rhs_element = condition_element.find("rhs")

    op_code = op_element.text if op_element is not None and op_element.text else "0"
    op_index = _IF_CONDITION_CODE_TO_INDEX.get(op_code, 0)

    return [
        EditableArg(
            arg_id="if_lhs",
            arg_name="Target",
            widget_kind="text",
            backing_tag="Str",
            is_var=False,
            element=lhs_element,
            current_value=lhs_element.text if lhs_element is not None and lhs_element.text else "",
        ),
        EditableArg(
            arg_id="if_op",
            arg_name="Operator",
            widget_kind="dropdown",
            backing_tag="IfOp",
            is_var=False,
            element=op_element,
            current_value=str(op_index),
            dropdown_options=list(_IF_CONDITION_OPERATOR_LABELS),
        ),
        EditableArg(
            arg_id="if_rhs",
            arg_name="Value",
            widget_kind="text",
            backing_tag="Str",
            is_var=False,
            element=rhs_element,
            current_value=rhs_element.text if rhs_element is not None and rhs_element.text else "",
        ),
    ]


def _build_if_action_args(action_element: defusedxml.ElementTree.Element) -> list[EditableArg]:
    """Builds an existing 'If' action's editable Target/Operator/Value fields from
    its <ConditionList>/<Condition>. Falls back to a single read-only note if there
    isn't exactly one Condition (no ConditionList at all, or more than one chained
    with AND/OR) -- editing a multi-condition If isn't supported yet, and silently
    editing just the first Condition would drop the rest on save.
    """
    condition_list = action_element.find("ConditionList")
    if condition_list is None:
        return [_readonly_note_arg("This 'If' action has no condition to edit.")]

    conditions = condition_list.findall("Condition")
    if len(conditions) != 1:
        return [
            _readonly_note_arg(
                f"This 'If' action has {len(conditions)} chained conditions -- editing "
                "multi-condition If actions isn't supported by this tool yet.",
            ),
        ]

    return _build_if_condition_args(conditions[0])


def _synthesize_if_condition(
    element_cls: type,
    action_element: defusedxml.ElementTree.Element,
) -> list[EditableArg]:
    """Builds a brand-new, single-Condition <ConditionList sr="if"> for an 'If'
    action (code 37) and appends it to action_element -- the Add Task counterpart
    of _build_if_action_args, mirroring the real XML shape documented at
    IF_CONDITION_OPERATORS. Defaults to an empty comparison (lhs="", op="0" i.e.
    "=", rhs="") for the user to fill in.
    """
    condition_list = element_cls("ConditionList", {"sr": "if"})
    condition = element_cls("Condition", {"sr": "c0", "ve": "3"})
    for tag in ("lhs", "op", "rhs"):
        child = element_cls(tag)
        child.text = "0" if tag == "op" else ""
        condition.append(child)
    condition_list.append(condition)
    action_element.append(condition_list)

    return _build_if_condition_args(condition)


def _lookup_key(arg) -> str | None:
    """If this arg's eval is ['prefix', 'l', lookupkey], return the lookup key."""
    if isinstance(arg.arg_eval, list) and len(arg.arg_eval) > 2 and arg.arg_eval[1] == "l":
        return arg.arg_eval[2]
    return None


def _is_checkbox_arg_eval(arg_eval) -> bool:
    """True when arg_eval marks a boolean 'selected' arg via actionc.py's "e"
    evaluation marker (["e", "name"] or ["", "e", "name"] -- see the evalargs
    legend at the top of actionc.py). This overrides the arg's declared
    arg_type/category: these are always backed by an <Int> element and edited
    as a checkbox, regardless of whether the action table lists the arg as
    Int, String, or Boolean.
    """
    if not isinstance(arg_eval, list):
        return False
    if len(arg_eval) > 2 and arg_eval[1] == "e":
        return True
    return len(arg_eval) > 1 and arg_eval[0] == "e"


def _display_arg_name(arg) -> str:
    """The label to show for this arg in the GUI: arg.arg_name if it's set,
    else derived from arg.arg_eval's first entry (arg_eval[0] for a list --
    e.g. ["Priority=", "l", "4s"] -- or arg_eval itself for a plain string --
    e.g. "Level=") with a leading ", " and trailing "=" stripped, e.g.
    "Priority=" -> "Priority", ", To=" -> "To". Falls back to "" (unlabeled,
    same as before) if arg_name is blank and arg_eval is empty/absent too.

    Special case: when arg_name is blank and arg_eval is a list marking an
    'event' arg (["", "e", "Name"] or ["e", "Name"]), the name sits right
    after the "e" marker rather than in the first entry.
    """
    if arg.arg_name:
        return arg.arg_name

    if _is_checkbox_arg_eval(arg.arg_eval):
        name_index = 2 if len(arg.arg_eval) > 2 and arg.arg_eval[1] == "e" else 1
        return arg.arg_eval[name_index].removeprefix(", ").removesuffix("=")

    first_entry = arg.arg_eval[0] if isinstance(arg.arg_eval, list) else arg.arg_eval
    if not first_entry:
        return ""

    first_entry = first_entry.removeprefix(", ")
    return first_entry.removesuffix("=")


def _classify_arg_widget(arg) -> tuple[str, str, list[str] | None]:
    """Pure schema classification of an ArgumentCode -- no XML/value involved.

    Returns (widget_kind, backing_tag, dropdown_options). Shared between reading an
    existing arg's value (Edit Task) and seeding a default for a brand-new one (Add
    Task); value-sourcing details that only make sense for an *existing* element
    (e.g. a var-backed Int downgrading a dropdown to raw_fallback) stay in the
    individual _build_*_arg functions rather than here.
    """
    if _is_checkbox_arg_eval(arg.arg_eval):
        return "checkbox", "Int", None

    category = PrimeItems.tasker_arg_specs.get(arg.arg_type, "")

    if category == "Boolean":
        return "checkbox", "Int", None
    if category == "Int":
        lookup_key = _lookup_key(arg)
        if lookup_key is not None and lookup_key in lookup_values:
            return "dropdown", "Int", lookup_values[lookup_key]
        return "text", "Int", None
    if category in ("String", "Str"):
        widget_kind = "text" if isinstance(arg.arg_eval, str) else "raw_fallback"
        return widget_kind, "Str", None
    return "readonly", "", None


def _build_boolean_arg(action_element: defusedxml.ElementTree.Element, the_arg: str, arg) -> EditableArg:
    int_element = _find_int_element(action_element, the_arg)
    if int_element is None:
        return _readonly_arg(arg, "Not present in this action's XML.")
    widget_kind, backing_tag, _ = _classify_arg_widget(arg)
    return EditableArg(
        arg_id=arg.arg_id,
        arg_name=_display_arg_name(arg),
        widget_kind=widget_kind,
        backing_tag=backing_tag,
        is_var=False,
        element=int_element,
        current_value=int_element.attrib.get("val", "0"),
    )


def _build_int_arg(action_element: defusedxml.ElementTree.Element, the_arg: str, arg) -> EditableArg:
    int_element = _find_int_element(action_element, the_arg)
    if int_element is None:
        return _readonly_arg(arg, "Not present in this action's XML.")

    var_element = int_element.find("var")
    is_var = var_element is not None
    raw_value = var_element.text or "" if is_var else int_element.attrib.get("val", "")

    widget_kind, backing_tag, dropdown_options = _classify_arg_widget(arg)

    if widget_kind == "dropdown":
        if is_var:
            # A formula, not an index -- can't safely represent it as a dropdown.
            return EditableArg(
                arg_id=arg.arg_id,
                arg_name=_display_arg_name(arg),
                widget_kind="raw_fallback",
                backing_tag="Int",
                is_var=True,
                element=int_element,
                current_value=raw_value,
                readonly_note="Variable expression -- edited as raw text.",
            )
        return EditableArg(
            arg_id=arg.arg_id,
            arg_name=_display_arg_name(arg),
            widget_kind="dropdown",
            backing_tag="Int",
            is_var=False,
            element=int_element,
            current_value=raw_value or "0",
            dropdown_options=dropdown_options,
        )

    return EditableArg(
        arg_id=arg.arg_id,
        arg_name=_display_arg_name(arg),
        widget_kind="text",
        backing_tag=backing_tag,
        is_var=is_var,
        element=int_element,
        current_value=raw_value,
    )


def is_perform_task_name_arg(action_code: str, arg) -> bool:
    """Whether this arg is the 'Perform Task' action's Name field (code 130,
    arg_id 0) -- the one field guiwins.py's Add/Edit Task dialogs offer an
    extra Task-picker dropdown alongside (see get_all_task_names), as a
    fill-in convenience for its ordinary text field. Public (not
    underscore-prefixed): guiwins.py calls this directly to decide when to
    render that picker.

    Safe to gate purely on the numeric code text: no Profile State/Event
    condition defines code 130 (checked against actionc.py), so this can't
    misfire on the same machinery profedit.py reuses (build_editable_args/
    build_synthesized_args) for those.
    """
    return action_code == PERFORM_TASK_ACTION_CODE and arg.arg_id == PERFORM_TASK_NAME_ARG_ID


def get_all_task_names() -> list[str]:
    """Every Task name in the currently loaded backup, sorted -- the options
    offered by the 'Perform Task' action's Name picker (see
    is_perform_task_name_arg). Same source task_name_exists reads.
    """
    return sorted(PrimeItems.tasker_root_elements.get("all_tasks_by_name", {}))


def _build_string_arg(action_element: defusedxml.ElementTree.Element, the_arg: str, arg) -> EditableArg:
    str_element = _find_str_element(action_element, the_arg)
    if str_element is None:
        return _readonly_arg(arg, "Not present in this action's XML.")

    widget_kind, backing_tag, _ = _classify_arg_widget(arg)
    return EditableArg(
        arg_id=arg.arg_id,
        arg_name=_display_arg_name(arg),
        widget_kind=widget_kind,
        backing_tag=backing_tag,
        is_var=False,
        element=str_element,
        current_value=str_element.text or "",
    )


def _build_default_arg(arg) -> EditableArg | None:
    """Seed a default EditableArg for a brand-new action being synthesized (Add Task).

    Returns None for any Bundle-category arg -- on an addable action (see
    classify_action_addability) the only Bundle that can appear is the informational
    'Output Variables' hint, which is safe to omit entirely (no row, no element
    written) -- and for any other unsupported category (defense in depth; the action
    shouldn't have been offered as addable if this is reached). The returned arg's
    `element` is left None -- add_action_to_task() builds and attaches the real XML
    element afterward, keeping this function pure/schema-only.
    """
    category = PrimeItems.tasker_arg_specs.get(arg.arg_type, "")
    if category == "Bundle":
        return None

    widget_kind, backing_tag, dropdown_options = _classify_arg_widget(arg)
    if widget_kind == "readonly":
        return None

    if widget_kind in ("checkbox", "dropdown"):
        current_value = "0"
    else:  # "text" or "raw_fallback"
        current_value = "0" if backing_tag == "Int" else ""

    return EditableArg(
        arg_id=arg.arg_id,
        arg_name=_display_arg_name(arg),
        widget_kind=widget_kind,
        backing_tag=backing_tag,
        is_var=False,
        element=None,
        current_value=current_value,
        dropdown_options=dropdown_options,
    )


def build_synthesized_args(
    element_cls: type,
    container_element: defusedxml.ElementTree.Element,
    effective_args: list,
) -> list[EditableArg]:
    """Synthesizes default Int/Str XML elements for a set of ArgumentCode
    definitions, appends them to container_element, and returns their bound
    EditableArgs.

    Public (not underscore-prefixed): shared by add_action_to_task (a new Task
    Action) and profedit.add_event_condition_to_profile (a new Profile Event
    condition) -- both build brand-new elements from the exact same Bundle/
    Int/Str argument shape (see build_editable_args' own docstring on why
    Profile conditions reuse this machinery). Skips any arg _build_default_arg
    returns None for (the informational 'Output Variables' Bundle hint, or an
    unsupported category -- shouldn't occur on an addable action/event; see
    classify_action_addability).
    """
    args = []
    for arg in effective_args:
        editable_arg = _build_default_arg(arg)
        if editable_arg is None:
            continue

        if editable_arg.backing_tag == "Int":
            element = element_cls("Int", {"sr": f"arg{arg.arg_id}", "val": editable_arg.current_value or "0"})
        else:  # "Str"
            element = element_cls("Str", {"sr": f"arg{arg.arg_id}", "ve": "3"})
            element.text = ""
        container_element.append(element)
        editable_arg.element = element
        args.append(editable_arg)
    return args


_SAFE_CATEGORIES = ("Int", "Str", "String", "Boolean")


def classify_action_addability(action_key: str) -> tuple[bool, str]:
    """Whether a real numeric Task-action key (e.g. '104t') can be synthesized from
    scratch, and why not if not.

    Only args that are plain numbers/text/checkboxes, or the informational 'Output
    Variables' Bundle hint, can be safely synthesized; anything else (App/Icon/Image
    pickers, or a Bundle that's actually an opaque third-party plugin payload) has no
    generic default. Code '37' (If) has no args at all (action_codes["37t"].args ==
    []) and would otherwise fall through the "not effective_args" case below as
    addable -- it gets its own synthesizer instead (see add_action_to_task's
    IF_ACTION_KEY branch and _synthesize_if_condition), building its
    <ConditionList>/<Condition> from IF_CONDITION_OPERATORS rather than the generic
    Bundle/Int/Str model, so it's left to fall through here too.
    """
    action_code = action_codes[action_key]
    if action_code.redirect:
        target = action_codes.get(action_code.redirect)
        if target is None:
            return False, "Unresolvable action definition."
        effective_args = target.args
    else:
        effective_args = action_code.args

    if not effective_args:
        return True, ""

    for arg in effective_args:
        category = PrimeItems.tasker_arg_specs.get(arg.arg_type, "")
        if category in _SAFE_CATEGORIES:
            continue
        if category == "Bundle" and arg.arg_name == "Output Variables":
            continue
        reason = (
            f"Requires a '{category or arg.arg_type}' value for "
            f"'{arg.arg_name or 'plugin payload'}' that this tool can't generate yet."
        )
        return False, reason

    return True, ""


_ADDABLE_ACTIONS_CACHE: list[dict] | None = None


def list_addable_actions() -> list[dict]:
    """All real numeric Task-action entries with their addability, memoized -- the
    underlying data (actionc.py, arg_specs.json, category_descriptions.json) is
    static for the process lifetime.
    """
    global _ADDABLE_ACTIONS_CACHE  # noqa: PLW0603
    if _ADDABLE_ACTIONS_CACHE is not None:
        return _ADDABLE_ACTIONS_CACHE

    rows = []
    for key, action_code in action_codes.items():
        if not (key.endswith("t") and key[:-1].isdigit()):
            continue  # Not a real numeric Task-action code (e.g. Scene-widget entries).
        addable, reason = classify_action_addability(key)
        category_code = action_code.category
        category_name = "Uncategorized"
        if category_code and category_code.isdigit():
            category_name = PrimeItems.tasker_category_descriptions.get(int(category_code), "Uncategorized")
        rows.append(
            {
                "action_key": key,
                "code": key[:-1],
                "name": action_code.name,
                "category_name": category_name,
                "addable": addable,
                "reason": reason,
            },
        )
    rows.sort(key=lambda row: row["name"])
    _ADDABLE_ACTIONS_CACHE = rows
    return rows


def search_addable_actions(query: str = "", category_name: str = "All") -> list[dict]:
    """Filter the memoized action list by name substring and/or exact category name."""
    query = query.strip().lower()
    rows = list_addable_actions()
    if query:
        rows = [r for r in rows if query in r["name"].lower()]
    if category_name and category_name != "All":
        rows = [r for r in rows if r["category_name"] == category_name]
    return rows


def arg_key(act_number: int, arg_id: str) -> str:
    """Key format shared with the dialog builder for arg_values dict lookups."""
    return f"act{act_number}_arg{arg_id}"


def label_key(act_number: int) -> str:
    """Key format shared with the dialog builder for an action's Label field --
    lives in the same arg_values dict as arg_key's entries (can't collide:
    arg keys always continue "arg{id}" after the underscore).
    """
    return f"act{act_number}_label"


def get_action_label(action: EditableAction) -> str:
    """The action's current <label> text, "" if it has none -- the same child
    action.py's get_label_disabled_condition reads for display.
    """
    return action.action_element.findtext("label") or ""


def _apply_action_label(action: EditableAction, label_text: str) -> None:
    """Sets the action's <label> child, or removes it when the pending text is
    empty/whitespace -- clearing the field in the dialog un-labels the action
    rather than leaving an empty <label/> behind (Tasker omits the element
    entirely for unlabeled actions).
    """
    label_text = label_text.strip()
    if label_text:
        _set_child_text(action.action_element, "label", label_text)
        return
    label_element = action.action_element.find("label")
    if label_element is not None:
        action.action_element.remove(label_element)


def validate_arg_values(
    args: list[EditableArg],
    key_for_arg: Callable[[EditableArg], str],
    arg_values: dict[str, str],
) -> list[str]:
    """Validates a set of args' pending values (only plain-number "text"+"Int"
    non-variable args need it -- checkboxes/dropdowns/Str can't fail this way).

    Public (not underscore-prefixed) and parameterized by key_for_arg rather
    than hardcoding arg_key's act{N}_arg{id} format: Profile State/Event
    conditions share this exact same arg model (see build_editable_args) but key
    their pending values as cond{N}_arg{id} instead -- see
    profedit.condition_arg_key.
    """
    errors = []
    for arg in args:
        if arg.widget_kind != "text" or arg.backing_tag != "Int" or arg.is_var:
            continue
        value = arg_values.get(key_for_arg(arg), "")
        if value and not value.lstrip("-").isdigit():
            errors.append(f"'{arg.arg_name}' must be a whole number.")
    return errors


# A Tasker variable name (the part after '%'): 3+ letters/digits/underscores,
# not starting or ending with an underscore.
_IF_VARIABLE_NAME_RE = re.compile(r"^(?!_)[A-Za-z0-9_]{3,}(?<!_)$")

# Operator labels (see IF_CONDITION_OPERATORS) that test mere existence, so the
# Value field is legitimately empty.
_IF_NO_VALUE_OPERATORS = ("Is Set", "Not Set")


def validate_if_condition_values(
    action: EditableAction,
    key_for_arg: Callable[[EditableArg], str],
    arg_values: dict[str, str],
) -> list[str]:
    """Validates an 'If' action's pending Target/Operator/Value field values:

    1. Target must be set: plain alphanumeric text, or a %variable.
    2. Unless the Operator is 'Is Set'/'Not Set' (which test existence alone),
       Value must be set to alphanumeric text.
    3. A %variable Target must name a valid Tasker variable: 3 or more
       letters/digits/underscores after the '%', not starting or ending
       with '_'.

    No-op for an If whose condition isn't editable (no/multiple Conditions --
    see _build_if_action_args' read-only fallback). Falls back to an arg's
    current value when its key isn't in arg_values, matching apply_arg_values'
    leave-untouched convention.
    """
    args_by_id = {arg.arg_id: arg for arg in action.args}
    if not {"if_lhs", "if_op", "if_rhs"} <= args_by_id.keys():
        return []

    lhs_arg, op_arg, rhs_arg = args_by_id["if_lhs"], args_by_id["if_op"], args_by_id["if_rhs"]
    target = arg_values.get(key_for_arg(lhs_arg), lhs_arg.current_value).strip()
    value = arg_values.get(key_for_arg(rhs_arg), rhs_arg.current_value).strip()

    # The dialog's dropdown delivers the operator as its label; the fallback
    # current_value is an index into the same label list.
    operator_label = arg_values.get(key_for_arg(op_arg))
    if operator_label is None:
        try:
            operator_label = op_arg.dropdown_options[int(op_arg.current_value)]
        except (TypeError, ValueError, IndexError):
            operator_label = _IF_CONDITION_OPERATOR_LABELS[0]

    return validate_condition_fields(target, operator_label, value)


def validate_condition_fields(target: str, operator_label: str, value: str) -> list[str]:
    """The If-condition field rules, shared by the 'If' action's own condition
    (validate_if_condition_values) and a per-action If condition
    (set_action_condition):

    1. Target must be set: plain alphanumeric text, or a %variable naming a
       valid Tasker variable (3+ letters/digits/underscores after the '%',
       not starting or ending with '_').
    2. Unless the Operator tests existence alone ('Is Set'/'Not Set'), Value
       must be set to alphanumeric text.
    """
    target = target.strip()
    value = value.strip()

    errors = []
    if not target:
        errors.append("The If condition's Target must be set.")
    elif target.startswith("%"):
        if not _IF_VARIABLE_NAME_RE.match(target[1:]):
            errors.append(
                f"The If condition's Target '{target}' is not a valid variable: the name after '%' "
                "must be 3 or more letters, digits, or underscores, and cannot start or end with '_'.",
            )
    elif not target.isalnum():
        errors.append(f"The If condition's Target '{target}' must be alphanumeric, or a %variable.")

    if operator_label not in _IF_NO_VALUE_OPERATORS:
        if not value:
            errors.append(f"The If condition's Value must be set when the Operator is '{operator_label}'.")
        elif not value.isalnum():
            errors.append(f"The If condition's Value '{value}' must be alphanumeric.")

    return errors


def action_condition_count(action: EditableAction) -> int:
    """How many <Condition>s this action's <ConditionList> holds (0 if none) --
    1 is the editable case for the per-action "If" checkbox; more means a
    chained AND/OR condition this tool won't clobber (same stance as
    _build_if_action_args' multi-condition fallback).
    """
    condition_list = action.action_element.find("ConditionList")
    return 0 if condition_list is None else len(condition_list.findall("Condition"))


def action_has_condition(action: EditableAction) -> bool:
    """Whether this action carries a per-action If condition."""
    return action_condition_count(action) > 0


def get_action_condition_values(action: EditableAction) -> tuple[str, str, str]:
    """(Target, Operator label, Value) of the action's first If condition, or
    ("", "=", "") when it has none -- prefill for the per-action If prompt.
    """
    condition_list = action.action_element.find("ConditionList")
    condition = condition_list.find("Condition") if condition_list is not None else None
    if condition is None:
        return "", IF_CONDITION_OPERATORS[0][1], ""

    op_code = condition.findtext("op") or "0"
    op_label = IF_CONDITION_OPERATORS[_IF_CONDITION_CODE_TO_INDEX.get(op_code, 0)][1]
    return condition.findtext("lhs") or "", op_label, condition.findtext("rhs") or ""


def set_action_condition(
    edited_task: EditableTask,
    act_number: int,
    target: str,
    operator_label: str,
    value: str,
) -> list[str]:
    """Validates and writes a per-action If condition (the <ConditionList
    sr="if"> Tasker allows on any action), replacing whatever single-condition
    list the action already had. Returns [] on success, else the validation
    errors (see validate_condition_fields) with nothing mutated -- same
    convention as apply_edits_to_task.

    Refuses the 'If' action itself: its ConditionList IS the action (edited
    via its own Target/Operator/Value arg fields, which are bound to those
    same elements -- replacing them here would orphan the args).
    """
    action = next((a for a in edited_task.actions if a.act_number == act_number), None)
    if action is None:
        return [f"Action {act_number} no longer exists."]
    if action.code == IF_ACTION_CODE:
        return ["Use the If action's own Target/Operator/Value fields instead."]

    errors = validate_condition_fields(target, operator_label, value)
    if errors:
        return errors

    existing = action.action_element.find("ConditionList")
    if existing is not None:
        action.action_element.remove(existing)

    element_cls = type(action.action_element)
    condition_list = element_cls("ConditionList", {"sr": "if"})
    condition = element_cls("Condition", {"sr": "c0", "ve": "3"})
    for tag, text in (
        ("lhs", target.strip()),
        ("op", _IF_CONDITION_LABEL_TO_CODE.get(operator_label, "0")),
        ("rhs", value.strip()),
    ):
        child = element_cls(tag)
        child.text = text
        condition.append(child)
    condition_list.append(condition)
    action.action_element.append(condition_list)
    return []


def remove_action_condition(edited_task: EditableTask, act_number: int) -> None:
    """Removes an action's per-action If condition, if any -- backs unchecking
    the "If" checkbox. Same 'If'-action guard as set_action_condition.
    """
    action = next((a for a in edited_task.actions if a.act_number == act_number), None)
    if action is None or action.code == IF_ACTION_CODE:
        return

    condition_list = action.action_element.find("ConditionList")
    if condition_list is not None:
        action.action_element.remove(condition_list)


def apply_arg_values(
    args: list[EditableArg],
    key_for_arg: Callable[[EditableArg], str],
    arg_values: dict[str, str],
) -> None:
    """Applies a set of args' pending values onto their backing XML elements.
    Caller must have already validated via validate_arg_values -- this assumes
    every numeric value present is well-formed.
    """
    for arg in args:
        if arg.widget_kind == "readonly" or arg.element is None:
            continue
        key = key_for_arg(arg)
        if key not in arg_values:
            continue
        value = arg_values[key]

        if arg.widget_kind == "checkbox":
            arg.element.set("val", "1" if value in ("1", "true", "True") else "0")
        elif arg.widget_kind == "dropdown" and arg.backing_tag == "IfOp":
            # An "If" action's Operator (see _build_if_condition_args): unlike a
            # lookup-backed Int dropdown, the element this writes to (<op>) holds
            # Tasker's own op *code* as its text, not this dropdown's own option
            # index as a val attribute.
            arg.element.text = _IF_CONDITION_LABEL_TO_CODE.get(value, "0")
        elif arg.widget_kind == "dropdown":
            index = arg.dropdown_options.index(value) if value in arg.dropdown_options else 0
            arg.element.set("val", str(index))
        elif arg.backing_tag == "Int" and arg.is_var:
            var_element = arg.element.find("var")
            var_element.text = value
        elif arg.backing_tag == "Int":
            arg.element.set("val", value)
        elif arg.backing_tag == "Str":
            arg.element.text = value


def apply_edits_to_task(
    edited_task: EditableTask,
    name_value: str,
    priority_value: str,
    arg_values: dict[str, str],
) -> list[str]:
    """Validate all fields, and only if everything's valid, mutate the task copy.

    All-or-nothing: on any validation error, nothing is mutated and the list of
    error messages is returned.
    """
    errors = []

    name_value = name_value.strip()
    if not name_value:
        errors.append("Task name cannot be empty.")

    priority_value = priority_value.strip()
    if priority_value and not priority_value.isdigit():
        errors.append("Priority must be a non-negative whole number.")

    for action in edited_task.actions:
        key_for_arg = lambda arg, act_number=action.act_number: arg_key(act_number, arg.arg_id)
        action_errors = validate_arg_values(action.args, key_for_arg, arg_values)
        if action.code == IF_ACTION_CODE:
            action_errors.extend(validate_if_condition_values(action, key_for_arg, arg_values))
        errors.extend(f"{error} (Action {action.act_number})" for error in action_errors)

    if errors:
        return errors

    _set_child_text(edited_task.task_element, "nme", name_value)
    if priority_value:
        _set_child_text(edited_task.task_element, "pri", priority_value)

    for action in edited_task.actions:
        apply_arg_values(
            action.args,
            lambda arg, act_number=action.act_number: arg_key(act_number, arg.arg_id),
            arg_values,
        )
        if (pending_label := arg_values.get(label_key(action.act_number))) is not None:
            _apply_action_label(action, pending_label)

    return []


def _set_child_text(parent: defusedxml.ElementTree.Element, tag: str, text: str) -> None:
    child = parent.find(tag)
    if child is None:
        # Match parent's actual Element class (see write_standalone_task_xml) --
        # ETW.SubElement() would build a stdlib-class child and fail parent.append().
        child = type(parent)(tag)
        parent.append(child)
    child.text = text


def sanitize_filename(name: str) -> str:
    """Strip characters illegal in filenames from a Task name (minimal, not a full slugify)."""
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip() or "task"


def default_save_path(task_name: str) -> str:
    """Default standalone-export path: {current runtime directory}/{sanitized name}.tsk.xml.

    Uses os.getcwd() (the directory the app is running from) rather than the
    loaded backup file's directory -- the backup is typically picked from the
    user's home directory (see Local_File_Picker("~", ...) in userintr.py), which
    isn't necessarily where a Task should land.
    """
    return os.path.join(os.getcwd(), f"{sanitize_filename(task_name)}.tsk.xml")


def task_name_exists(name: str) -> bool:
    """Whether a Task with this name already exists in the currently loaded backup."""
    return name.strip() in PrimeItems.tasker_root_elements.get("all_tasks_by_name", {})


def save_path_exists(output_path: str) -> bool:
    """Whether a file already sits at this save path (would be silently overwritten)."""
    return bool(output_path) and os.path.exists(output_path)


def render_standalone_task_xml(edited_task: EditableTask) -> str:
    """Render the edited Task as a standalone TaskerData/Task XML string, matching
    Tasker's own single-task export/import format. Shared by write_standalone_task_xml
    (local file) and save_task_to_android (posted to the Android device).
    """
    tv = PrimeItems.xml_root.attrib.get("tv", "") if PrimeItems.xml_root is not None else ""
    task_copy = copy.deepcopy(edited_task.task_element)
    # The parsed tree's Element class isn't necessarily xml.etree.ElementTree's own
    # C-accelerated Element (defusedxml's hardened XMLParser forces the pure-Python
    # implementation) -- ET.Element()/.append() enforce an exact type match, so build
    # the wrapper using the same class the parsed elements actually are.
    root = type(task_copy)("TaskerData", {"sr": "", "dvi": "1", "tv": tv})
    root.append(task_copy)
    ETW.indent(root, space="\t")

    return XML_DECLARATION + ETW.tostring(root, encoding="unicode") + "\n"


def write_standalone_task_xml(edited_task: EditableTask, output_path: str) -> None:
    """Write the edited Task as a standalone TaskerData/Task XML file, matching
    Tasker's own single-task export/import format. Raises OSError on failure.
    """
    with open(output_path, "w", encoding="utf-8") as out_file:
        out_file.write(render_standalone_task_xml(edited_task))


def save_task_to_android(
    edited_task: EditableTask,
    ip_address: str,
    ip_port: str,
    task_name: str,
    auth_key: str = "",
) -> tuple[int, str, str]:
    """Import the edited Task, rendered as standalone XML, onto the Android device
    via the Tasker HTTP API's POST /api/import endpoint (Params/Body: Task XML;
    Response: task object). Every request to this API must carry an
    'Authorization: <key>' header.

    Pass a previously-cached auth_key (see maputil2.get_android_auth_key) to skip
    that device's GET /api/auth confirmation prompt. If the device rejects a
    cached key (401), this falls back to fetching a fresh one and retries once --
    the cached key may have expired or been revoked on the device.

    Returns (0, task_name, auth_key_used) on success, so the caller can cache
    auth_key_used for next time, or (return_code, error_message, "") on failure.
    """
    # Lazy import to avoid a circular-import error (mirrors getbakup.get_backup_file()).
    from maptasker.src.maputil2 import get_android_auth_key, http_post_request  # noqa: PLC0415

    ip_address = ip_address.strip()
    ip_port = ip_port.strip()
    if not ip_address or not ip_port:
        return 8, "Android IP address and port are required.", ""

    had_cached_key = bool(auth_key)
    if not auth_key:
        return_code, auth_key = get_android_auth_key(ip_address, ip_port)
        if return_code != 0:
            return return_code, auth_key, ""

    xml_text = render_standalone_task_xml(edited_task)

    # api/import imports directly into Tasker
    # api/tasks runs an existing task by name, but doesn't import a new one
    # /api/file reads/writes files on the device, but doesn't import into Tasker
    # Try just a file write to /api/file and then a /api/import of that file, instead of sending the whole XML in the POST body.
    return_code, response = http_post_request(
        ip_address,
        ip_port,
        "",
        "api/import",
        "",
        xml_text.encode("utf-8"),
        auth_key,
    )

    if return_code == 9 and had_cached_key:
        # Cached key was rejected -- get a fresh one (device prompts once more) and retry.
        return_code, auth_key = get_android_auth_key(ip_address, ip_port)
        if return_code != 0:
            return return_code, auth_key, ""
        return_code, response = http_post_request(
            ip_address,
            ip_port,
            "",
            "api/import",
            "",
            xml_text.encode("utf-8"),
            auth_key,
        )
        if return_code != 0:
            return return_code, str(response), ""

    if return_code != 0:
        return return_code, str(response), ""
    return 0, task_name, auth_key


def verify_task_on_android(ip_address: str, ip_port: str, task_name: str, auth_key: str) -> bool:
    """Confirms the Task actually landed in Tasker after a save_task_to_android
    import, via the Tasker HTTP API's GET /api/tasks?name=<task_name> (Response:
    task objects -- a JSON array of {"name": ..., "running": ...}, filtered to
    Tasks matching the given name). api/import's own 200 response doesn't
    guarantee Tasker committed the Task, so this re-checks by name -- see
    save_task_to_android_directory for the fallback when this fails.

    Returns True if the GET succeeded and returned at least one Task named
    task_name, False otherwise.
    """
    # Lazy import to avoid a circular-import error (mirrors getbakup.get_backup_file()).
    from urllib.parse import quote  # noqa: PLC0415

    from maptasker.src.maputil2 import http_request  # noqa: PLC0415

    return_code, response = http_request(
        ip_address.strip(),
        ip_port.strip(),
        "",
        "api/tasks",
        f"?name={quote(task_name)}",
        auth_key,
    )
    if return_code != 0:
        return False

    try:
        tasks = json.loads(response)
        if not tasks:
            return False
    except (ValueError, TypeError):
        return False

    return any(task.get("name") == task_name for task in tasks)


def save_task_to_android_directory(
    edited_task: EditableTask,
    ip_address: str,
    ip_port: str,
    task_name: str,
    auth_key: str = "",
) -> tuple[int, str]:
    """Fallback for save_task_to_android when verify_task_on_android can't confirm
    the import landed in Tasker: retries the same POST /api/import once more,
    rather than falling back to a different endpoint. api/import is the only
    documented way to actually get a Task into Tasker over HTTP -- /api/file
    only supports GET/DELETE (no way to write a file with it), and even if it
    did, Tasker doesn't watch that directory for files to auto-import -- so a
    second attempt at the real thing is the only fallback that can plausibly
    help, e.g. if the first POST/GET-verify pair hit a transient network blip.

    Returns (0, task_name) on success, or (return_code, error_message) on failure.
    """
    # Lazy import to avoid a circular-import error (mirrors getbakup.get_backup_file()).
    from maptasker.src.maputil2 import http_post_request  # noqa: PLC0415

    xml_text = render_standalone_task_xml(edited_task)

    # file_location is "" so this reproduces save_task_to_android's request byte for byte
    # -- a retry that posted to a different URL would not be testing the same thing.
    # It used to pass "/Tasker/tasks/<name>.tsk.xml" here, left over from when this
    # function tried to write a file; http_post_request appends that to the endpoint, so
    # the "retry" actually POSTed to /api/import/Tasker/tasks/<name>.tsk.xml, which Tasker
    # has no route for -- meaning this fallback could never have succeeded.
    return_code, response = http_post_request(
        ip_address.strip(),
        ip_port.strip(),
        "",
        "api/import",
        "",
        xml_text.encode("utf-8"),
        auth_key,
    )
    if return_code != 0:
        return return_code, str(response)
    return 0, task_name


def register_new_task(edited_task: EditableTask, task_name: str) -> None:
    """Adds a new Task to the in-memory backup's Task tables (all_tasks,
    all_tasks_by_name) so it behaves like any other Task loaded from the backup --
    e.g. so it shows up in the Edit Task picker (guiutils.py reads
    all_tasks_by_name for that list) and so a second Add Task with the same name
    is caught by task_name_exists(). Call once: right after the standalone
    .tsk.xml write succeeds (see userintr.save_new_task_event), for a
    keep-without-saving-to-disk Ok without one (see userintr.keep_new_task_event),
    or after a successful Save To Android import (see
    userintr.save_task_to_android_event's is_new_task branch).
    """
    PrimeItems.tasker_root_elements["all_tasks"][edited_task.task_id] = {
        "xml": edited_task.task_element,
        "name": task_name,
    }
    PrimeItems.tasker_root_elements["all_tasks_by_name"][task_name] = {
        "xml": edited_task.task_element,
        "id": edited_task.task_id,
    }


def apply_edited_task_to_live_tree(edited_task: EditableTask) -> None:
    """Writes an edited (pre-existing) Task's changes back into the in-memory
    backup's Task tables (all_tasks, all_tasks_by_name) so views generated from
    them -- Map, Diagram, Tree -- reflect the edit right away instead of the
    Task's original, unedited content. load_task_for_edit/apply_edits_to_task
    only ever mutate a deep copy (never PrimeItems.xml_root or these tables
    directly -- see load_task_for_edit), so without this, Save only ever produces
    a standalone file and the rest of the app keeps showing the old version.

    Same all_tasks[id]["xml"]-swap approach as register_new_task, so it's
    consistent with however that Task already got into the tables; the actual
    XML tree's document structure (e.g. which Project/Profile a live Task
    element sits under) doesn't need touching since every view reads Task
    content through these tables, not by re-walking the tree for it.

    No-op if the Task's id isn't registered yet (e.g. a brand-new Task from Add
    Task, saved via Save To Android before ever reaching register_new_task) --
    call once, right after a successful Save (local or to Android).
    """
    all_tasks = PrimeItems.tasker_root_elements["all_tasks"]
    entry = all_tasks.get(edited_task.task_id)
    if entry is None:
        return

    old_name = entry["name"]
    new_name = edited_task.task_element.findtext("nme", "") or old_name

    all_tasks[edited_task.task_id] = {"xml": edited_task.task_element, "name": new_name}

    all_tasks_by_name = PrimeItems.tasker_root_elements["all_tasks_by_name"]
    if old_name in all_tasks_by_name and old_name != new_name:
        del all_tasks_by_name[old_name]
    all_tasks_by_name[new_name] = {"xml": edited_task.task_element, "id": edited_task.task_id}
