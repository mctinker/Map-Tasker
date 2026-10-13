"""taskedit_args: building the editable form of a Task's actions and arguments from the XML they came from."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from maptasker.src.core import appinv, plugset
from maptasker.src.core.actionc import action_codes
from maptasker.src.core.actiont import lookup_values
from maptasker.src.core.shelsort import shell_sort
from maptasker.src.edit.taskedit_model import (
    ICON_CATEGORIES,
    IF_ACTION_KEY,
    IF_CONDITION_CODE_TO_INDEX,
    IF_CONDITION_OPERATOR_LABELS,
    NO_APPS_REASON,
    NO_ICONS_REASON,
    PERFORM_TASK_ACTION_CODE,
    PERFORM_TASK_NAME_ARG_ID,
    EditableAction,
    EditableArg,
)

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from maptasker.src.core.primitem import RunState


def build_editable_action(action_element: Element, act_number: int, state: RunState) -> EditableAction:
    """Build a single EditableAction bound to an already-in-the-tree Action element.

    Shared by build_editable_actions (initial load) and copy_action_in_task (a
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
        args=build_editable_args(action_element, effective_args, state=state),
    )


def build_editable_actions(task_copy: Element, state: RunState) -> list[EditableAction]:
    """Find the Task's Actions, sort them into execution order, and build their arg models.

    Execution order is driven by the numeric suffix of sr="actN", not document order
    (Tasker itself writes actions out-of-order in the file), so reuse the same sort
    tasks.get_actions() uses to keep this dialog's ordering identical to the rest of
    the app's views.
    """
    actions = task_copy.findall("Action")
    shell_sort(actions, True, False)

    return [
        build_editable_action(action_element, _action_number(action_element), state=state) for action_element in actions
    ]


def _action_number(action_element: Element) -> int:
    """Extract the numeric suffix of sr="actN" for display/sort purposes only."""
    sr = action_element.attrib.get("sr", "")
    match = re.search(r"\d+$", sr)
    return int(match.group()) if match else 0


def reclassify_action_args(action: EditableAction, state: RunState) -> None:
    """Rebuild one action's argument models against the inventory as it stands now.

    An argument's widget kind is decided when the model is built (see
    _classify_arg_widget): an App or an Icon argument with nothing to pick from is
    read-only, and carries NO_APPS_REASON/NO_ICONS_REASON to say why.  A fetch from the
    device makes that answer wrong, and nothing re-asks it -- so the field would go on
    being read-only, for a stated reason that had stopped being true, until the dialog was
    closed and reopened.  This re-asks it, so redrawing the row is enough (see
    guiwins_taskedit._render_readonly_note).

    Rebuilt from the same Action element, so nothing that has been edited in the XML is
    lost; what is discarded is the classification, which is the point.
    """
    action_code = action_codes.get(f"{action.code}t")
    if action_code is None:
        return
    if f"{action.code}t" == IF_ACTION_KEY:
        action.args = _build_if_action_args(action.action_element)
        return
    effective_args = action_codes[action_code.redirect].args if action_code.redirect else action_code.args
    action.args = build_editable_args(action.action_element, effective_args, state=state)


def build_editable_args(
    action_element: Element,
    effective_args: list,
    state: RunState,
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
        category = state.tasker_arg_specs.get(arg.arg_type, "")

        if category == "Boolean" or _is_checkbox_arg_eval(arg.arg_eval):
            editable_args.append(_build_boolean_arg(action_element, the_arg, arg, state=state))
        elif category == "Int":
            editable_args.append(_build_int_arg(action_element, the_arg, arg, state=state))
        elif category in ("String", "Str"):
            editable_args.append(_build_string_arg(action_element, the_arg, arg, state=state))
        elif category == "App":
            editable_args.append(_build_app_arg(action_element, the_arg, arg, state=state))
        elif category in ICON_CATEGORIES:
            editable_args.append(_build_icon_arg(action_element, the_arg, arg, state=state))
        elif category == "Bundle" and plugset.is_plugin(action_element):
            editable_args.append(_plugin_settings_arg(action_element, arg))
        else:
            editable_args.append(
                _readonly_arg(arg, f"'{category or arg.arg_type}' arguments are not editable in this version."),
            )

    return editable_args


def _plugin_settings_arg(action_element: Element, arg) -> EditableArg:
    """A plugin's settings, shown read-only as one line (see plugset.settings_summary).

    Still not editable -- the plugin checks its own settings when Tasker hands them over --
    but no longer a blank box: what the plugin was set up to do is the first thing anyone
    opening the action wants to know, and the standing warning above it already says where
    to change it (see tasker_configuration_warning).
    """
    return EditableArg(
        arg_id=arg.arg_id,
        arg_name=display_arg_name(arg) or "Plugin Settings",
        widget_kind="readonly",
        backing_tag="",
        is_var=False,
        element=None,
        current_value=plugset.settings_summary(action_element),
    )


def _find_int_element(
    action_element: Element,
    the_arg: str,
) -> Element | None:
    return action_element.find(f"./Int[@sr='{the_arg}']")


def _find_str_element(
    action_element: Element,
    the_arg: str,
) -> Element | None:
    return next(
        (child for child in action_element.findall("Str") if child.attrib.get("sr") == the_arg),
        None,
    )


def _readonly_arg(arg, note: str) -> EditableArg:
    return EditableArg(
        arg_id=arg.arg_id,
        arg_name=display_arg_name(arg),
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


def build_if_condition_args(condition_element: Element) -> list[EditableArg]:
    """Builds the three editable fields (Target, Operator, Value) for an 'If'
    action's single Condition test, bound directly to its existing <lhs>/<op>/
    <rhs> elements -- the write-side counterpart of action.py's evaluate_condition,
    which reads these same three elements for display. Shared by
    synthesize_if_condition (a brand-new Condition, Add Task) and
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
    op_index = IF_CONDITION_CODE_TO_INDEX.get(op_code, 0)

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
            dropdown_options=list(IF_CONDITION_OPERATOR_LABELS),
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


def _build_if_action_args(action_element: Element) -> list[EditableArg]:
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

    return build_if_condition_args(conditions[0])


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


def display_arg_name(arg) -> str:
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


def _classify_arg_widget(arg, state: RunState) -> tuple[str, str, list[str] | None]:
    """Pure schema classification of an ArgumentCode -- no XML/value involved.

    Returns (widget_kind, backing_tag, dropdown_options). Shared between reading an
    existing arg's value (Edit Task) and seeding a default for a brand-new one (Add
    Task); value-sourcing details that only make sense for an *existing* element
    (e.g. a var-backed Int downgrading a dropdown to raw_fallback) stay in the
    individual _build_*_arg functions rather than here.
    """
    if _is_checkbox_arg_eval(arg.arg_eval):
        return "checkbox", "Int", None

    category = state.tasker_arg_specs.get(arg.arg_type, "")

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
    # An Application or an icon is editable only while there is an inventory to offer:
    # both fields are typed into as well as picked from (see guiwins_taskedit._render_app_arg_field),
    # but a picker with nothing in it is a field the user has no way to fill correctly, so
    # with an empty inventory these stay exactly as read-only as they were before
    # appinv.py existed.  See classify_action_addability, which gates on the same thing.
    if category == "App" and appinv.have_apps(state=state):
        return "app_picker", "App", None
    if category in ICON_CATEGORIES and appinv.have_icons(state=state):
        return "icon_picker", "Img", None
    return "readonly", "", None


def _build_boolean_arg(action_element: Element, the_arg: str, arg, state: RunState) -> EditableArg:
    int_element = _find_int_element(action_element, the_arg)
    if int_element is None:
        return _readonly_arg(arg, "Not present in this action's XML.")
    widget_kind, backing_tag, _ = _classify_arg_widget(arg, state=state)
    return EditableArg(
        arg_id=arg.arg_id,
        arg_name=display_arg_name(arg),
        widget_kind=widget_kind,
        backing_tag=backing_tag,
        is_var=False,
        element=int_element,
        current_value=int_element.attrib.get("val", "0"),
    )


def _build_int_arg(action_element: Element, the_arg: str, arg, state: RunState) -> EditableArg:
    int_element = _find_int_element(action_element, the_arg)
    if int_element is None:
        return _readonly_arg(arg, "Not present in this action's XML.")

    var_element = int_element.find("var")
    is_var = var_element is not None
    raw_value = var_element.text or "" if is_var else int_element.attrib.get("val", "")

    widget_kind, backing_tag, dropdown_options = _classify_arg_widget(arg, state=state)

    if widget_kind == "dropdown":
        if is_var:
            # A formula, not an index -- can't safely represent it as a dropdown.
            return EditableArg(
                arg_id=arg.arg_id,
                arg_name=display_arg_name(arg),
                widget_kind="raw_fallback",
                backing_tag="Int",
                is_var=True,
                element=int_element,
                current_value=raw_value,
                readonly_note="Variable expression -- edited as raw text.",
            )
        return EditableArg(
            arg_id=arg.arg_id,
            arg_name=display_arg_name(arg),
            widget_kind="dropdown",
            backing_tag="Int",
            is_var=False,
            element=int_element,
            current_value=raw_value or "0",
            dropdown_options=dropdown_options,
        )

    return EditableArg(
        arg_id=arg.arg_id,
        arg_name=display_arg_name(arg),
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


def get_all_task_names(state: RunState) -> list[str]:
    """Every Task name in the currently loaded backup, sorted -- the options
    offered by the 'Perform Task' action's Name picker (see
    is_perform_task_name_arg). Same source task_name_exists reads.
    """
    return sorted(state.tasker_root_elements.get("all_tasks_by_name", {}))


def _build_string_arg(action_element: Element, the_arg: str, arg, state: RunState) -> EditableArg:
    str_element = _find_str_element(action_element, the_arg)
    if str_element is None:
        return _readonly_arg(arg, "Not present in this action's XML.")

    widget_kind, backing_tag, _ = _classify_arg_widget(arg, state=state)
    return EditableArg(
        arg_id=arg.arg_id,
        arg_name=display_arg_name(arg),
        widget_kind=widget_kind,
        backing_tag=backing_tag,
        is_var=False,
        element=str_element,
        current_value=str_element.text or "",
    )


def _build_app_arg(action_element: Element, the_arg: str, arg, state: RunState) -> EditableArg:
    """An <App sr="argN"> argument, as a field holding its package names.

    Read-only in two cases, both of which are what this argument did before it was
    editable at all: no inventory to pick from (see _classify_arg_widget), or no <App>
    element in this action's XML to bind to.  The second is the same treatment
    _build_string_arg gives a missing <Str>: this builds a model of what is there, and
    synthesizing a missing element belongs to Add Task (build_synthesized_args).
    """
    widget_kind, backing_tag, _ = _classify_arg_widget(arg, state=state)
    if widget_kind != "app_picker":
        return _readonly_arg(arg, NO_APPS_REASON)

    app_element = action_element.find(f"./App[@sr='{the_arg}']")
    if app_element is None:
        return _readonly_arg(arg, "Not present in this action's XML.")

    return EditableArg(
        arg_id=arg.arg_id,
        arg_name=display_arg_name(arg) or "App",
        widget_kind=widget_kind,
        backing_tag=backing_tag,
        is_var=False,
        element=app_element,
        current_value=appinv.format_app_value(appinv.read_app_element(app_element)),
    )


def _build_icon_arg(action_element: Element, the_arg: str, arg, state: RunState) -> EditableArg:
    """An <Img sr="argN"> argument, as a field holding one icon reference -- see
    appinv.format_icon_value for how the four forms of one are spelled.  Falls back to
    read-only on the same two conditions as _build_app_arg, for the same reasons.
    """
    widget_kind, backing_tag, _ = _classify_arg_widget(arg, state=state)
    if widget_kind != "icon_picker":
        return _readonly_arg(arg, NO_ICONS_REASON)

    img_element = action_element.find(f"./Img[@sr='{the_arg}']")
    if img_element is None:
        return _readonly_arg(arg, "Not present in this action's XML.")

    return EditableArg(
        arg_id=arg.arg_id,
        arg_name=display_arg_name(arg) or "Icon",
        widget_kind=widget_kind,
        backing_tag=backing_tag,
        is_var=False,
        element=img_element,
        current_value=appinv.format_icon_value(appinv.read_icon_element(img_element)),
    )


def build_default_arg(arg, state: RunState) -> EditableArg | None:
    """Seed a default EditableArg for a brand-new action being synthesized (Add Task).

    Returns None for any Bundle-category arg -- on an addable action (see
    classify_action_addability) the only Bundle that can appear is the informational
    'Output Variables' hint, which is safe to omit entirely (no row, no element
    written) -- and for any other unsupported category (defense in depth; the action
    shouldn't have been offered as addable if this is reached). The returned arg's
    `element` is left None -- add_action_to_task() builds and attaches the real XML
    element afterward, keeping this function pure/schema-only.
    """
    category = state.tasker_arg_specs.get(arg.arg_type, "")
    if category == "Bundle":
        return None

    widget_kind, backing_tag, dropdown_options = _classify_arg_widget(arg, state=state)
    if widget_kind == "readonly":
        return None

    if widget_kind in ("checkbox", "dropdown"):
        current_value = "0"
    else:  # "text" or "raw_fallback"
        current_value = "0" if backing_tag == "Int" else ""

    return EditableArg(
        arg_id=arg.arg_id,
        arg_name=display_arg_name(arg),
        widget_kind=widget_kind,
        backing_tag=backing_tag,
        is_var=False,
        element=None,
        current_value=current_value,
        dropdown_options=dropdown_options,
    )
