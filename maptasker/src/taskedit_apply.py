"""taskedit_apply: validating the values a user typed into an editable Task, and applying them -- arguments, labels and If conditions."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from maptasker.src import appinv
from maptasker.src.editcommon import set_child_text as _set_child_text
from maptasker.src.taskedit_model import (
    IF_ACTION_CODE,
    IF_CONDITION_CODE_TO_INDEX,
    IF_CONDITION_LABEL_TO_CODE,
    IF_CONDITION_OPERATOR_LABELS,
    IF_CONDITION_OPERATORS,
    EditableAction,
    EditableArg,
    EditableTask,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from maptasker.src.primitem import RunState


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


def set_action_label(action: EditableAction, label_text: str) -> None:
    """Give the action a label of its own, or clear it with empty text -- for a caller that is
    not the editor's own Save, which applies labels with the rest of its fields (see
    apply_action_edits_to_task).
    """
    _apply_action_label(action, label_text)


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
       Value must be set, to either of those same two forms.
    3. A %variable Target or Value must name a valid Tasker variable: 3 or
       more letters/digits/underscores after the '%', not starting or ending
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
            operator_label = IF_CONDITION_OPERATOR_LABELS[0]

    return validate_condition_fields(target, operator_label, value)


def _validate_condition_field(field_name: str, field_value: str) -> list[str]:
    """The rule both an If condition's Target and its Value obey: plain
    alphanumeric text, or a %variable naming a valid Tasker variable (3+
    letters/digits/underscores after the '%', not starting or ending with
    '_'). field_name ('Target'/'Value') names the offending field in the
    message. Assumes an already-stripped, non-empty field_value.
    """
    if field_value.startswith("%"):
        if not _IF_VARIABLE_NAME_RE.match(field_value[1:]):
            message = (
                f"The If condition's {field_name} '{field_value}' is not a valid variable: the name after '%' "
                "must be 3 or more letters, digits, or underscores, and cannot start or end with '_'."
            )
            return [message]
    elif not field_value.isalnum():
        return [f"The If condition's {field_name} '{field_value}' must be alphanumeric, or a %variable."]
    return []


def validate_condition_fields(target: str, operator_label: str, value: str) -> list[str]:
    """The If-condition field rules, shared by the 'If' action's own condition
    (validate_if_condition_values) and a per-action If condition
    (set_action_condition):

    1. Target must be set: plain alphanumeric text, or a %variable naming a
       valid Tasker variable (3+ letters/digits/underscores after the '%',
       not starting or ending with '_').
    2. Unless the Operator tests existence alone ('Is Set'/'Not Set'), Value
       must be set, to either of those same two forms -- comparing a variable
       against another variable (e.g. %DATE) is legitimate in Tasker.
    """
    target = target.strip()
    value = value.strip()

    errors = []
    if not target:
        errors.append("The If condition's Target must be set.")
    else:
        errors.extend(_validate_condition_field("Target", target))

    if operator_label not in _IF_NO_VALUE_OPERATORS:
        if not value:
            errors.append(f"The If condition's Value must be set when the Operator is '{operator_label}'.")
        else:
            errors.extend(_validate_condition_field("Value", value))

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
    op_label = IF_CONDITION_OPERATORS[IF_CONDITION_CODE_TO_INDEX.get(op_code, 0)][1]
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
        ("op", IF_CONDITION_LABEL_TO_CODE.get(operator_label, "0")),
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
    state: RunState,
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
            # An "If" action's Operator (see build_if_condition_args): unlike a
            # lookup-backed Int dropdown, the element this writes to (<op>) holds
            # Tasker's own op *code* as its text, not this dropdown's own option
            # index as a val attribute.
            arg.element.text = IF_CONDITION_LABEL_TO_CODE.get(value, "0")
        elif arg.widget_kind == "dropdown":
            index = arg.dropdown_options.index(value) if value in arg.dropdown_options else 0
            arg.element.set("val", str(index))
        elif arg.backing_tag == "App":
            appinv.write_app_element(arg.element, appinv.parse_app_value(value, state=state))
        elif arg.backing_tag == "Img":
            appinv.write_icon_element(arg.element, appinv.parse_icon_value(value))
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
    state: RunState,
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

    errors.extend(validate_action_edits(edited_task, arg_values))

    if errors:
        return errors

    _set_child_text(edited_task.task_element, "nme", name_value)
    if priority_value:
        _set_child_text(edited_task.task_element, "pri", priority_value)

    _apply_action_edits(edited_task, arg_values, state)

    return []


def validate_action_edits(edited_task: EditableTask, arg_values: dict[str, str]) -> list[str]:
    """Every complaint the action half of a Task edit has -- argument values, and an If's
    own condition -- each tagged with the action it came from.  Mutates nothing.
    """
    errors = []
    for action in edited_task.actions:
        key_for_arg = lambda arg, act_number=action.act_number: arg_key(act_number, arg.arg_id)
        action_errors = validate_arg_values(action.args, key_for_arg, arg_values)
        if action.code == IF_ACTION_CODE:
            action_errors.extend(validate_if_condition_values(action, key_for_arg, arg_values))
        errors.extend(f"{error} (Action {action.act_number})" for error in action_errors)
    return errors


def _apply_action_edits(edited_task: EditableTask, arg_values: dict[str, str], state: RunState) -> None:
    """Write the validated action argument values and labels onto the Task copy."""
    for action in edited_task.actions:
        apply_arg_values(
            action.args,
            lambda arg, act_number=action.act_number: arg_key(act_number, arg.arg_id),
            arg_values,
            state=state,
        )
        if (pending_label := arg_values.get(label_key(action.act_number))) is not None:
            _apply_action_label(action, pending_label)


def apply_action_edits_to_task(edited_task: EditableTask, arg_values: dict[str, str], state: RunState) -> list[str]:
    """apply_edits_to_task without the Name/Priority half, for an editor that shows neither.

    The Scene Properties KEY tab edits the actions of the Task the Scene fires on a key
    press, and never its name -- which it must not touch: a Task bound by id can be an
    unnamed one, whose displayed name is invented by taskerd from its first action and
    would become a real <nme> the moment apply_edits_to_task validated it.

    All-or-nothing like apply_edits_to_task: on any error nothing is mutated.
    """
    errors = validate_action_edits(edited_task, arg_values)
    if errors:
        return errors
    _apply_action_edits(edited_task, arg_values, state)
    return []
