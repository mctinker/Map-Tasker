"""The Task editor: the Edit/Add/Delete Task dialogs and the action editor behind them.

Split out of guiwins.py, which had grown to 14,500 lines.  This is everything an Action is
edited through -- _build_task_action_editor and the field widgets it dispatches to, the
Application and Tasker-icon pickers those fields open, and the condition/If-variant dialogs
an Action's own logic is built with.

The Profile editor reuses the argument fields here (a Profile's state and event conditions
are built out of the same <Arg> shapes an Action is), so guiwins_profedit imports from this
module; nothing here imports from there.

The editor scaffolding it shares with the other Edit dialogs -- editor_state, PendingChangesBanner
and the Properties button -- comes from guiwins_editor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from maptasker.src.core import objprops
from maptasker.src.core.mapjump import TASK
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.edit import (
    taskedit,
    taskedit_addable,
    taskedit_apply,
    taskedit_args,
    taskedit_model,
    taskedit_save,
)
from maptasker.src.gui.guiwins_draft import DraftRow
from maptasker.src.gui.guiwins_editor import (
    PendingChangesBanner,
    build_properties_button,
    build_redact_checkbox,
    editor_state,
)
from maptasker.src.gui.guiwins_impact import build_impact_panel
from maptasker.src.gui.guiwins_taskpickers import (
    after_inventory_fetch,
    build_run_task_on_android_dialog,
    render_addability_reason,
    render_app_arg_field,
    render_icon_arg_field,
    render_readonly_note,
)
from maptasker.src.gui.guiwins_tndesc import build_taskernet_description_button

if TYPE_CHECKING:
    from collections.abc import Callable
    from xml.etree.ElementTree import Element

    from nicegui.events import ValueChangeEventArguments

    from maptasker.src.core.primitem import RunState
    from maptasker.src.gui.userintr import MyGui


def _refresh_position_options(
    edited_task: taskedit_model.EditableTask,
    position_select: ui.select,
    position_labels: dict[str, int | None],
) -> None:
    """Rebuilds an Add/Edit Task dialog's "Position" dropdown from the task's
    current actions -- called after every Add/Copy/Move/Delete/Remove, since
    act_numbers and names shift and stale labels would insert at the wrong
    spot. Keeps the user's current choice if it still exists, else falls back
    to "At the End". position_labels maps each label to the act_number to
    insert at (None for "At the End") -- see build_edit_task_dialog's note on
    why that map is kept out-of-band.
    """
    position_labels.clear()
    options = []
    for action in edited_task.actions:
        before_label = f"Before {action.act_number}: {action.action_name}"
        after_label = f"After {action.act_number}: {action.action_name}"
        position_labels[before_label] = action.act_number
        position_labels[after_label] = action.act_number + 1
        options.extend((before_label, after_label))
    options.append("At the End")
    position_labels["At the End"] = None
    previous = position_select.value
    position_select.set_options(options, value=previous if previous in options else "At the End")


def _action_indent_spaces(self: MyGui) -> int:
    """The user's "If/Then/Else Indentation Amount" setting as an int (default
    4) -- the same amount the Map view indents If blocks by. Restored settings
    can hold it as a string, hence the coercion.
    """
    try:
        return int(getattr(self, "indent", 4) or 4)
    except (TypeError, ValueError):
        return 4


def dropdown_current_label(arg: taskedit_model.EditableArg) -> str:
    """The option to preselect for a dropdown arg: current_value is the index
    into dropdown_options (If Operator, Int lookups -- every dropdown in this
    codebase).
    """
    options = arg.dropdown_options or []
    try:
        return options[int(arg.current_value)]
    except (ValueError, IndexError):
        return options[0] if options else ""


def _render_task_name_field(
    _self: MyGui,
    _action: taskedit_model.EditableAction,
    arg: taskedit_model.EditableArg,
    key: str,
    field_refs: dict,
    state: RunState,
) -> None:
    """Renders the 'Perform Task' action's Name field: an ordinary text input
    the user can key any string into, plus a companion "Pick a Task" dropdown
    that -- when an option is chosen -- overwrites the text input with that
    Task's name. Either/or: whichever the user touches last is what's saved,
    since Save only ever reads the text input's own field_refs entry (this
    dropdown is deliberately never added to field_refs, so task_arg_values
    can't see it).

    A plain ui.select with Quasar's "new-value-mode" was tried first so a
    single widget could both pick and free-type, but it only accepts a typed
    value when the user presses Enter -- clicking away (the far more likely
    action) silently reverts the field to its first option, which is exactly
    the "grabs the first task" bug this two-widget design avoids entirely.
    """
    field_refs[key] = ui.input(arg.arg_name, value=arg.current_value).classes("flex-1")

    task_names = taskedit_args.get_all_task_names(state=state)
    if not task_names:
        return

    def fill_in_picked_task(e: ValueChangeEventArguments) -> None:
        if e.value:
            field_refs[key].value = e.value

    ui.select(
        task_names,
        label=translate_string("Pick a Task"),
        with_input=True,
        on_change=fill_in_picked_task,
    ).classes("flex-1").props("dense").tooltip(translate_string("Pick a Task which will be called by this action."))


def build_action_condition_dialog(
    self: MyGui,
    edited_task: taskedit_model.EditableTask,
    act_number: int,
    checkbox: ui.checkbox,
    condition_cache: dict[int, tuple[str, str, str]],
) -> None:
    """Prompts for a per-action If condition (Target/Operator/Value) when the
    action's "If" checkbox is checked -- see _render_action_condition_checkbox.
    Prefills from the values cached by the last uncheck (so toggling off and
    on edits rather than starts over), else from the action's current XML. Ok
    validates and writes the <ConditionList> (dialog stays open on errors);
    Cancel unchecks the checkbox, adding nothing.
    """
    action = next((a for a in edited_task.actions if a.act_number == act_number), None)
    if action is None:
        return

    prefill = condition_cache.get(act_number) or taskedit_apply.get_action_condition_values(action)
    operator_labels = [label for _code, label in taskedit_model.IF_CONDITION_OPERATORS]

    with ui.dialog().props("persistent") as condition_dialog, ui.card().classes("min-w-[400px] p-6"):
        ui.label(f"If Condition -- {act_number}: {action.action_name}").classes("text-lg font-bold text-blue-600")
        target_input = ui.input(translate_string("Target"), value=prefill[0]).classes("w-full")
        operator_select = ui.select(
            operator_labels,
            value=prefill[1] if prefill[1] in operator_labels else operator_labels[0],
            label=translate_string("Operator"),
        ).classes("w-full")
        value_input = ui.input(translate_string("Value"), value=prefill[2]).classes("w-full")
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(
                translate_string("Cancel"),
                on_click=lambda: (condition_dialog.close(), checkbox.set_value(False)),
            ).props("outline")
            ui.button(
                translate_string("Ok"),
                on_click=lambda: self.event_handlers.editors.set_action_condition_event(
                    edited_task,
                    act_number,
                    target_input,
                    operator_select,
                    value_input,
                    condition_dialog,
                    checkbox,
                ),
            ).classes("bg-blue-600")

    condition_dialog.open()


def _render_action_condition_checkbox(
    self: MyGui,
    edited_task: taskedit_model.EditableTask,
    action: taskedit_model.EditableAction,
    condition_cache: dict[int, tuple[str, str, str]],
) -> None:
    """Renders an action's per-action "If" checkbox in the Add/Edit Task action
    lists (every action except the 'If' action itself -- callers skip that).
    Checked state mirrors whether the action currently has a <ConditionList>;
    checking prompts for the condition (build_action_condition_dialog),
    unchecking removes it (stashing its values in condition_cache so a
    re-check prefills them). An action with multiple chained conditions gets a
    read-only note instead -- replacing those from this single-condition
    prompt would silently drop the rest.
    """
    condition_count = taskedit_apply.action_condition_count(action)
    if condition_count > 1:
        ui.label(
            f"Has {condition_count} chained If conditions -- not editable here.",
        ).classes("text-xs text-gray-500 italic")
        return

    target, operator_label, value = taskedit_apply.get_action_condition_values(action)
    text = f"If: {target} {operator_label} {value}".rstrip() if condition_count else "If"
    checkbox = ui.checkbox(text, value=condition_count == 1).props("dense")

    def on_toggle(
        e: ValueChangeEventArguments, act_number: int = action.act_number, cb: ui.checkbox = checkbox
    ) -> None:
        if e.value:
            build_action_condition_dialog(self, edited_task, act_number, cb, condition_cache)
            return
        current = next((a for a in edited_task.actions if a.act_number == act_number), None)
        if current is not None and taskedit_apply.action_has_condition(current):
            condition_cache[act_number] = taskedit_apply.get_action_condition_values(current)
        self.event_handlers.editors.remove_action_condition_event(edited_task, act_number)
        cb.set_text(translate_string("If"))

    checkbox.on_value_change(on_toggle)


def _render_continue_after_error_checkbox(
    self: MyGui,
    edited_task: taskedit_model.EditableTask,
    action: taskedit_model.EditableAction,
) -> None:
    """Renders an action's 'Continue Task After Error' checkbox in the Add/Edit
    Task action lists -- only for actions Tasker considers able to fail
    (actionc.py's canfail flag, see taskedit.action_can_fail). Checked writes
    <se>false</se> on the action; unchecking removes the element (Tasker's
    stop-on-error default). Applied immediately, same as the Enabled switch.
    """
    if not taskedit.action_can_fail(action):
        return

    ui.checkbox(
        translate_string("Continue Task After Error"),
        value=taskedit.action_continues_after_error(action),
        on_change=lambda e, n=action.act_number: self.event_handlers.editors.set_action_continue_after_error_event(
            edited_task,
            n,
            bool(e.value),
        ),
    ).props("dense")


def _render_plugin_configuration_warning(element: Element, name: str) -> None:
    """Renders the standing "configure this in Tasker" warning on an action's or a
    condition's own panel, for a third-party plugin whose payload this tool can't
    edit -- nothing at all for anything else (see
    taskedit_addable.tasker_configuration_warning). Shown in all three action/condition
    lists (Edit Task, Add Task, Edit Profile's State/Event conditions), whether the
    item was just added from bundles.json or read from the loaded backup.
    """
    warning = taskedit_addable.tasker_configuration_warning(element, name)
    if not warning:
        return

    with ui.row().classes(
        "w-full items-center gap-2 p-2 mb-1 rounded bg-amber-100 dark:bg-amber-900 border border-amber-400",
    ):
        ui.icon("warning").classes("text-amber-700 dark:text-amber-300")
        ui.label(warning).classes("text-xs text-amber-900 dark:text-amber-100")


def build_if_variant_dialog(on_choice: Callable[[str], None]) -> None:
    """Prompts for how much of an If block to insert when the user picks the
    "If" action in an Add/Edit Task action picker: just the "If", "If" plus a
    matching "End If", or a full "If"/"Else"/"End If" skeleton -- see
    taskedit_model.IF_BLOCK_VARIANTS/add_if_block_to_task. Fires on_choice(variant)
    only when one is clicked; Cancel inserts nothing.
    """
    with ui.dialog().props("persistent") as variant_dialog, ui.card().classes("min-w-[300px] p-6"):
        ui.label(translate_string("Add 'If' Action")).classes("text-lg font-bold text-blue-600")
        ui.label(translate_string("Insert just the 'If', or a complete block?")).classes("text-sm mb-2")
        for variant in taskedit_model.IF_BLOCK_VARIANTS:
            ui.button(
                variant,
                on_click=lambda _e=None, v=variant: (variant_dialog.close(), on_choice(v)),
            ).classes("w-full")
        with ui.row().classes("w-full justify-end mt-2"):
            ui.button(translate_string("Cancel"), on_click=variant_dialog.close).props("outline")

    variant_dialog.open()


class _ActionPicker:
    """The "Add an action" half of the Add Task and Edit Task dialogs.

    A search box and category filter, a Position dropdown saying where the action goes, and the
    list of actions to pick from.  The two dialogs differ only in which event handlers do the
    adding, so those are passed in, and in what happens once something has been added, which
    on_added is told.
    """

    def __init__(
        self,
        gui: MyGui,
        edited_task: taskedit_model.EditableTask,
        add_action: Callable[[str, int | None], int | None],
        add_if_block: Callable[[str, int | None], int | None],
        on_added: Callable[[int | None], None],
    ) -> None:
        """
        Args:
            gui: The application window, which holds the run's state.
            edited_task: The working copy of the Task the action is added to.
            add_action: Adds the action with this key at this position, and returns its act_number
                (None if it could not be added).
            add_if_block: The same for an "If" block of the given variant.
            on_added: Called with what add_action/add_if_block returned.
        """
        self.gui = gui
        self.edited_task = edited_task
        self.add_action = add_action
        self.add_if_block = add_if_block
        self.on_added = on_added
        # Maps each "Position" dropdown label to the act_number to insert at (None
        # for "At the End") -- kept out-of-band rather than as the ui.select's own
        # value/options dict, since "Before N" and "After N-1" resolve to the exact
        # same act_number and a dict's keys (which NiceGUI's dict-options form uses
        # as the value) must be unique, but the two need to stay distinct, readable
        # menu entries.
        self.position_labels: dict[str, int | None] = {}
        self.search_input: ui.input
        self.category_select: ui.select
        self.position_select: ui.select
        self.picker_container: ui.column

    def build(self) -> None:
        """Draws the search row, the Position dropdown and the (still empty) list of actions."""
        category_names = sorted(
            {row["category_name"] for row in taskedit_addable.list_addable_actions(state=self.gui.state)}
        )
        ui.label(translate_string("Add an action")).classes("text-sm font-bold mt-2")
        with ui.row().classes("w-full gap-4"):
            self.search_input = ui.input(translate_string("Search actions")).classes("flex-1")
            self.category_select = ui.select(["All", *category_names], value="All").classes("w-48")
        self.position_select = (
            ui.select([], label=translate_string("Position"), with_input=True).classes("w-full").props("dense")
        )
        self.picker_container = ui.column().classes("w-full")
        self.search_input.on_value_change(self.refresh)
        self.category_select.on_value_change(self.refresh)

    def refresh(self, _e: object | None = None) -> None:
        """Redraws the list of actions to pick from, for the current search and category."""
        self.picker_container.clear()
        rows = taskedit_addable.search_addable_actions(
            self.search_input.value or "",
            self.category_select.value,
            state=self.gui.state,
        )
        with self.picker_container, ui.scroll_area().classes("w-full h-40 border rounded p-2"):
            for row in rows:
                if row["addable"]:
                    ui.button(
                        f"{row['name']} ({row['category_name']})",
                        on_click=lambda _e=None, r=row: self.pick(r["action_key"]),
                    ).props("flat align=left dense").classes("w-full justify-start")
                else:
                    with ui.column().classes("w-full gap-0"):
                        ui.label(f"{row['name']} ({row['category_name']})").classes("text-gray-400")
                        render_addability_reason(self.gui, row["reason"], self.refresh)

    def refresh_positions(self) -> None:
        """Redraws the Position dropdown -- see _refresh_position_options."""
        _refresh_position_options(self.edited_task, self.position_select, self.position_labels)

    def pick(self, action_key: str) -> None:
        """Adds the picked action.

        "If" gets an extra prompt (just the If, or a whole If/Else/End If
        block?) before anything is inserted; every other action goes in
        directly. Position is resolved when the choice lands, not at
        picker-click time -- same value, and the variant dialog is modal.
        """
        if action_key == taskedit_model.IF_ACTION_KEY:
            build_if_variant_dialog(
                lambda variant: self.on_added(
                    self.add_if_block(variant, self.position_labels.get(self.position_select.value)),
                ),
            )
            return
        self.on_added(self.add_action(action_key, self.position_labels.get(self.position_select.value)))


class _ActionList:
    """What the Add Task and Edit Task dialogs' lists of actions have in common.

    Both draw the actions added so far as expansions, highlight the one added last, and
    rebuild the whole list after any change -- which renumbers the actions, so the
    act*_arg* keys in field_refs would otherwise go stale.  Each subclass supplies its own
    render_actions, and what an action's panel holds.
    """

    def __init__(self, gui: MyGui, edited_task: taskedit_model.EditableTask, field_refs: dict) -> None:
        """
        Args:
            gui: The application window, which holds the event handlers and the run's state.
            edited_task: The working copy of the Task whose actions are listed.
            field_refs: The dialog's widgets by key, which Save reads the values back from.
        """
        self.gui = gui
        self.edited_task = edited_task
        self.field_refs = field_refs
        # Last-known per-action If condition values, keyed by act_number -- lets an
        # uncheck/re-check of the "If" checkbox edit instead of starting over.
        self.condition_cache: dict[int, tuple[str, str, str]] = {}
        # act_number of the action most recently added in this dialog session --
        # render_actions highlights it so it's easy to spot in a long list.
        self.last_added_act_number: int | None = None
        self.picker: _ActionPicker
        self.actions_container: ui.column

    def clear_last_added(self) -> None:
        """Forgets which action was added last.

        A change that renumbers the list leaves a stale act_number here, which would risk
        highlighting the wrong action -- drop the highlight instead of letting it follow
        whatever action inherits the number.
        """
        self.last_added_act_number = None

    def on_added(self, act_number: int | None) -> None:
        """Takes note of a newly added action (None if adding failed), and redraws."""
        if act_number is not None:
            self.last_added_act_number = act_number
        self.render_actions()
        self.picker.refresh_positions()

    def render_actions(self) -> None:
        """Rebuilds the list from scratch."""
        raise NotImplementedError

    def _forget_action_widgets(self) -> None:
        """Drops the act* keys of the widgets about to be rebuilt, so none survives into the next Save."""
        for key in [k for k in self.field_refs if k.startswith("act")]:
            del self.field_refs[key]

    def _render_action_header(
        self, action: taskedit_model.EditableAction, nest_level: int, indent_spaces: int
    ) -> ui.expansion:
        """The expansion an action's panel goes in, titled by its number and name, indented to its nesting."""
        # Indent with non-breaking spaces -- plain ones collapse in the rendered header.
        indent_pad = "\u00a0" * (indent_spaces * nest_level)
        is_last_added = action.act_number == self.last_added_act_number
        header = f"{indent_pad}{action.act_number}: {action.action_name}"
        if is_last_added:
            header += "  \u2190 just added"
        action_expansion = ui.expansion(header, value=is_last_added).classes("w-full")
        if is_last_added:
            action_expansion.classes("bg-amber-100 dark:bg-amber-900 border-2 border-amber-400 rounded")
        return action_expansion

    def _render_action_basics(self, action: taskedit_model.EditableAction) -> None:
        """An action's Label, its If and Continue-After-Error checkboxes, and any warning about its plugin."""
        self.field_refs[taskedit_apply.label_key(action.act_number)] = ui.input(
            translate_string("Label"),
            value=taskedit_apply.get_action_label(action),
        ).classes("w-full")
        if action.code != taskedit_model.IF_ACTION_CODE:
            _render_action_condition_checkbox(self.gui, self.edited_task, action, self.condition_cache)
        _render_continue_after_error_checkbox(self.gui, self.edited_task, action)
        _render_plugin_configuration_warning(action.action_element, action.action_name)

    def _render_shared_argument(
        self,
        action: taskedit_model.EditableAction,
        arg: taskedit_model.EditableArg,
        key: str,
    ) -> bool:
        """Draws an argument's widget if it is one of the kinds both dialogs draw alike.

        Returns:
            True if it was drawn, False if the kind is one the caller has to deal with.
        """
        field_refs = self.field_refs
        if arg.widget_kind == "checkbox":
            field_refs[key] = ui.checkbox(arg.arg_name, value=arg.current_value == "1")
        elif arg.widget_kind == "dropdown":
            options = arg.dropdown_options or []
            field_refs[key] = ui.select(
                options,
                value=dropdown_current_label(arg),
                label=arg.arg_name,
            ).classes("flex-1")
        elif taskedit_args.is_perform_task_name_arg(action.code, arg):
            _render_task_name_field(self.gui, action, arg, key, field_refs, state=self.gui.state)
        elif arg.widget_kind == "app_picker":
            render_app_arg_field(self.gui, arg, key, field_refs)
        elif arg.widget_kind == "icon_picker":
            render_icon_arg_field(self.gui, arg, key, field_refs)
        else:
            return False
        return True

    def _render_argument_note(self, action: taskedit_model.EditableAction, arg: taskedit_model.EditableArg) -> None:
        """The note under an argument that explains why it can't be edited here, if it has one."""
        if arg.readonly_note:
            render_readonly_note(
                self.gui,
                arg.readonly_note,
                after_inventory_fetch(self.render_actions, action, state=self.gui.state),
            )

    def _render_readonly_argument(self, action: taskedit_model.EditableAction, arg: taskedit_model.EditableArg) -> None:
        """An argument that can't be edited here: shown as it is, with the note saying why, if any."""
        ui.input(arg.arg_name, value=arg.current_value).props("readonly").classes("flex-1")
        self._render_argument_note(action, arg)


class _NewTaskActionList(_ActionList):
    """The "Actions in this Task" list of the Add Task dialog: every action added so far, each with Remove."""

    def build(self) -> None:
        """Draws the Add an action picker and the (empty) list below it, then fills in both."""
        gui = self.gui
        self.picker = _ActionPicker(
            gui,
            self.edited_task,
            lambda action_key, position: gui.event_handlers.editors.add_action_to_new_task_event(
                self.edited_task,
                action_key,
                position,
            ),
            lambda variant, position: gui.event_handlers.editors.add_if_block_to_new_task_event(
                self.edited_task,
                variant,
                position,
            ),
            self.on_added,
        )
        self.picker.build()
        ui.label(translate_string("Actions in this Task")).classes("text-sm font-bold mt-2")
        self.actions_container = ui.column().classes("w-full")
        self.picker.refresh()
        self.picker.refresh_positions()
        self.render_actions()

    def render_actions(self) -> None:
        """Rebuilds the list from scratch -- a Remove renumbers every action after it, so
        stale act*_arg* keys must not survive into the next Save.
        """
        self._forget_action_widgets()
        self.actions_container.clear()
        with self.actions_container:
            if not self.edited_task.actions:
                ui.label(translate_string("No actions added yet.")).classes("text-xs text-gray-500 italic")
            indent_spaces = _action_indent_spaces(self.gui)
            display_levels = taskedit.action_display_levels(self.edited_task.actions)
            for action, nest_level in zip(self.edited_task.actions, display_levels, strict=True):
                with self._render_action_header(action, nest_level, indent_spaces):
                    self._render_action_basics(action)
                    for arg in action.args:
                        key = taskedit_apply.arg_key(action.act_number, arg.arg_id)
                        with ui.row().classes("w-full items-center gap-2"):
                            self._render_argument(action, arg, key)
                    self._render_remove_button(action)

    def _render_argument(
        self, action: taskedit_model.EditableAction, arg: taskedit_model.EditableArg, key: str
    ) -> None:
        """The widget for one argument of an action in the list."""
        if self._render_shared_argument(action, arg, key):
            return
        if arg.widget_kind == "readonly":
            # A newly-added plugin action's payload (see
            # taskedit_addable._synthesize_bundle_arg): not editable here,
            # and apply_arg_values skips it, so never a field_ref.
            self._render_readonly_argument(action, arg)
        else:  # "text" or "raw_fallback"
            self.field_refs[key] = ui.input(arg.arg_name, value=arg.current_value).classes("flex-1")

    def _render_remove_button(self, action: taskedit_model.EditableAction) -> None:
        """The button that takes an action out of the new Task."""
        ui.button(
            translate_string("Remove"),
            on_click=lambda _e=None, n=action.act_number: (
                self.clear_last_added(),
                self.gui.event_handlers.editors.remove_action_from_new_task_event(self.edited_task, n),
                self.render_actions(),
                self.picker.refresh_positions(),
            ),
        ).props("flat color=red dense")


class _EditTaskActionList(_ActionList):
    """The "Actions in this Task" list of the Edit Task dialog, with Copy/Move/Delete and an Enabled switch."""

    def __init__(
        self,
        gui: MyGui,
        edited_task: taskedit_model.EditableTask,
        field_refs: dict,
        list_classes: str,
    ) -> None:
        """
        Args:
            gui: The application window, which holds the event handlers and the run's state.
            edited_task: The working copy of the Task whose actions are listed.
            field_refs: The dialog's widgets by key, which Save reads the values back from.
            list_classes: The classes of the scroll area the list sits in.
        """
        super().__init__(gui, edited_task, field_refs)
        self.list_classes = list_classes

    def build(self) -> None:
        """Draws the Add an action picker and the (empty) list below it, then fills in both."""
        gui = self.gui
        self.picker = _ActionPicker(
            gui,
            self.edited_task,
            lambda action_key, position: gui.event_handlers.editors.add_action_to_edit_task_event(
                self.edited_task,
                action_key,
                position,
            ),
            lambda variant, position: gui.event_handlers.editors.add_if_block_to_edit_task_event(
                self.edited_task,
                variant,
                position,
            ),
            self.on_added,
        )
        self.picker.build()
        ui.label(translate_string("Actions in this Task")).classes("text-sm font-bold mt-2")
        self.actions_container = ui.column().classes("w-full")
        self.picker.refresh()
        self.picker.refresh_positions()
        self.render_actions()

    def render_actions(self) -> None:
        """Rebuilds the list from scratch -- Copy/Move/Delete all renumber every action, so
        stale act*_arg* keys must not survive into the next Save.
        """
        self._forget_action_widgets()
        self.actions_container.clear()
        with self.actions_container, ui.scroll_area().classes(self.list_classes):
            if not self.edited_task.actions:
                ui.label(translate_string("No actions in this Task.")).classes("text-xs text-gray-500 italic")
            last_position = len(self.edited_task.actions) - 1
            indent_spaces = _action_indent_spaces(self.gui)
            display_levels = taskedit.action_display_levels(self.edited_task.actions)
            for action, nest_level in zip(self.edited_task.actions, display_levels, strict=True):
                with self._render_action_header(action, nest_level, indent_spaces):
                    self._render_action_controls(action, last_position)
                    self._render_enabled_switch(action)
                    self._render_action_basics(action)
                    if not action.args:
                        ui.label(translate_string("No editable arguments.")).classes("text-xs text-gray-500 italic")
                    for arg in action.args:
                        key = taskedit_apply.arg_key(action.act_number, arg.arg_id)
                        with ui.row().classes("w-full items-center gap-2"):
                            self._render_argument(action, arg, key)

    def _render_action_controls(self, action: taskedit_model.EditableAction, last_position: int) -> None:
        """The Copy button, the Move-to box with its button, and the Delete button."""
        handlers = self.gui.event_handlers
        edited_task = self.edited_task
        with ui.row().classes("w-full items-center gap-2 mb-2"):
            ui.button(
                translate_string("Copy"),
                on_click=lambda _e=None, n=action.act_number: (
                    self.clear_last_added(),
                    handlers.editors.copy_action_in_edit_task_event(edited_task, n),
                    self.render_actions(),
                    self.picker.refresh_positions(),
                ),
            ).props("flat color=blue dense")
            move_to_input = (
                ui.number(
                    translate_string("Move to #"),
                    value=action.act_number,
                    min=0,
                    max=last_position,
                )
                .classes("w-24")
                .props("dense")
            )
            ui.button(
                translate_string("Move"),
                on_click=lambda _e=None, n=action.act_number, target=move_to_input: (
                    self.clear_last_added(),
                    handlers.editors.move_action_in_edit_task_event(
                        edited_task,
                        n,
                        int(target.value) if target.value is not None else n,
                    ),
                    self.render_actions(),
                    self.picker.refresh_positions(),
                ),
            ).props("flat color=orange dense")
            ui.button(
                translate_string("Delete"),
                on_click=lambda _e=None, n=action.act_number: (
                    self.clear_last_added(),
                    handlers.editors.delete_action_in_edit_task_event(edited_task, n),
                    self.render_actions(),
                    self.picker.refresh_positions(),
                ),
            ).props("flat color=red dense")

    def _render_enabled_switch(self, action: taskedit_model.EditableAction) -> None:
        """The switch that enables or disables an action."""
        action_enabled_switch = ui.switch(
            value=taskedit.is_action_enabled(action),
            on_change=lambda e, n=action.act_number: self.gui.event_handlers.editors.set_action_enabled_event(
                self.edited_task,
                n,
                bool(e.value),
            ),
        ).classes("mb-2")
        action_enabled_switch.bind_text_from(
            action_enabled_switch,
            "value",
            backward=lambda v: "Enabled" if v else "Disabled",
        )

    def _render_argument(
        self, action: taskedit_model.EditableAction, arg: taskedit_model.EditableArg, key: str
    ) -> None:
        """The widget for one argument of an action in the list."""
        if self._render_shared_argument(action, arg, key):
            return
        if arg.widget_kind in ("text", "raw_fallback"):
            self.field_refs[key] = ui.input(arg.arg_name, value=arg.current_value).classes("flex-1")
            self._render_argument_note(action, arg)
        else:  # readonly
            self._render_readonly_argument(action, arg)


def _build_task_action_editor(
    self: MyGui,
    edited_task: taskedit_model.EditableTask,
    field_refs: dict,
    *,
    list_classes: str = "w-full h-96 border rounded p-2",
) -> Callable[[], None]:
    """The Task action editor: an "Add an action" search/filter picker that can insert the
    new action before/after any existing one or at the end, per-action Copy/Move/Delete, an
    Enabled switch, and the values of each action's existing arguments.

    LIFTED OUT OF build_edit_task_dialog, which is still its main caller and whose layout
    it reproduces exactly; the Scene Properties KEY tab renders the same editor over the
    Task a Legacy Scene fires on an event (see _render_scene_event_task_actions), and a copy
    of two hundred lines is not a thing to keep in step by hand.  Everything it builds goes
    into the container that is open when it is called, so a caller places it by calling it
    in the right place.

    WHAT LANDS WHEN.  Adding, copying, moving, deleting, enabling and the If condition are
    written straight onto edited_task -- the working copy -- as they are done.  Argument
    values and labels are NOT: they sit in the widgets recorded in field_refs until
    something reads them back (userintr_fields.task_arg_values) and applies them.  That split is
    the Edit Task dialog's, and every caller inherits it, so each needs its own Ok/Apply.

    field_refs gains one entry per editable argument and label, keyed by taskedit_apply.arg_key/
    label_key, and its "act*" keys are cleared and rebuilt on every re-render -- Copy, Move
    and Delete all renumber the actions, so a stale key would apply a value to the wrong one.

    Returns render_actions, so a caller that changes the Task underneath the editor can
    redraw the list.
    """
    action_list = _EditTaskActionList(self, edited_task, field_refs, list_classes)
    action_list.build()
    return action_list.render_actions


def _render_task_save_buttons(
    self: MyGui,
    edited_task: taskedit_model.EditableTask,
    field_refs: dict,
    dialog: ui.dialog,
) -> None:
    """The Edit Task dialog's two ways of keeping the edits beyond the session: Save To Current File and Save To Android."""
    task_to_current_file = ui.button(
        translate_string("Save To Current File"),
        on_click=lambda: self.event_handlers.editors.save_edited_task_to_current_file_event(
            edited_task,
            field_refs,
            dialog,
        ),
    ).props("outline")
    with task_to_current_file:
        ui.tooltip(
            translate_string(
                "Saves the entire backup -- every Project, Profile and Task in it, not just this Task -- "
                "with this dialog's edits applied, the same ones 'Ok' would keep.\n"
                "It is written to a new, timestamped copy of the file currently loaded: "
                "backup.xml becomes backup_20260728_143005.xml.\n"
                "The file you loaded is never written to, so it is left exactly as it was.\n"
                "The app then switches to the new copy, which becomes the current file for any further "
                "editing and saving; saving again replaces the timestamp rather than adding a second one.\n"
                "This writes to this computer only -- nothing is sent to your Android device.",
            ),
        ).style("white-space: pre-wrap")
    task_to_android = ui.button(
        translate_string("Save To Android"),
        on_click=lambda: self.event_handlers.android.open_save_to_android_dialog_event(
            edited_task,
            field_refs,
            dialog,
        ),
    ).props("outline")
    with task_to_android:
        ui.tooltip(
            translate_string(
                "This opens a choice of two: write the Task as a standalone file onto your Android "
                "device under /Tasker/tasks, or import it straight into Tasker's live "
                "configuration.\n\n"
                "The 'Http Server Example' and 'Tasker HTTP API' Tasker Projects must both be installed and active on the Android "
                "device, with the server running (see the README's Direct XML Retrieval notes), and "
                "Tasker must be 6.2 or higher.\n\n"
                "The Android device must be on the same network, and the IP Address and Port must "
                "match its Tasker server settings.\n\n"
                "Watch the Android device while either one runs: Tasker asks you to authorize "
                "the connection several times for one save, and a prompt left untapped fails it.\n\n"
                "You must exit and restart Tasker to see an imported Task in the Tasker UI.",
            ),
        ).style("white-space: pre-wrap")


def _render_edit_task_buttons(
    self: MyGui,
    edited_task: taskedit_model.EditableTask,
    field_refs: dict,
    dialog: ui.dialog,
    title_label: ui.label,
    pending_changes: PendingChangesBanner,
) -> None:
    """The Edit Task dialog's row of buttons: Cancel, Delete, Rename, Ok and the several Saves."""
    with ui.row().classes("w-full justify-end gap-2 mt-4"):
        ui.button(translate_string("Cancel"), on_click=dialog.close).props("outline")
        delete_task_button = ui.button(
            translate_string("Delete Task"),
            on_click=lambda: self.event_handlers.editors.delete_task_event(edited_task, dialog),
        ).classes("bg-red-500 text-white")
        with delete_task_button:
            ui.tooltip(
                translate_string(
                    "Deletes this Task and every reference to it: it is removed from the Tasks of every "
                    "Project that owns it, and from any Profile that runs it as its Entry/Exit Task. "
                    "The Profiles themselves are kept.",
                ),
            )
        rename_task_button = ui.button(
            translate_string("Rename"),
            on_click=lambda: self.event_handlers.editors.rename_task_event(edited_task, field_refs, title_label),
        ).classes("bg-blue-600")
        with rename_task_button:
            ui.tooltip(
                translate_string(
                    "Prompts for a new name and applies just that to the loaded backup, right now. "
                    "Everything else in this dialog stays pending until Ok/Save, and the dialog stays "
                    "open so you can carry on editing.",
                ),
            )
        edit_task_ok = ui.button(
            translate_string("Ok"),
            on_click=lambda: self.event_handlers.editors.keep_edited_task_event(edited_task, field_refs, dialog),
        ).props("outline")
        with edit_task_ok:
            ui.tooltip(
                translate_string(
                    "Applies the changes made in this dialog to the loaded backup, right now, and closes the "
                    "dialog.\n\n"
                    "They are kept for this session only: no file is written and nothing is sent to your Android "
                    "device. Use 'Save To Current File' or 'Save To Android' to keep them. One press of Undo takes "
                    "the change back.\n\n"
                    "If something cannot be applied, such as a name another Task already has, the dialog stays "
                    "open and says why, so your edits are not lost.",
                ),
            ).style("white-space: pre-wrap")
        _render_task_save_buttons(self, edited_task, field_refs, dialog)
        run_on_android = ui.button(
            translate_string("Run On Android"),
            on_click=lambda: build_run_task_on_android_dialog(
                self,
                field_refs["name"].value.strip(),
                lambda: bool(pending_changes.row.visible),
            ),
        ).props("outline")
        with run_on_android:
            ui.tooltip(
                translate_string(
                    "Runs this Task on your Android device and shows what it returned, or the error.\n\n"
                    "The device runs the Task as Tasker already has it: use 'Save To Android' first to "
                    "run your edits.",
                ),
            ).style("white-space: pre-wrap")
        task_save = ui.button(
            translate_string("Export Task"),
            on_click=lambda: self.event_handlers.editors.save_edited_task_event(edited_task, field_refs, dialog),
        ).classes("bg-blue-600")
        with task_save:
            ui.tooltip(
                translate_string("This will save the Task directly to your current drive.\n\n"),
            ).style("white-space: pre-wrap")


def build_edit_task_dialog(self: MyGui, edited_task: taskedit_model.EditableTask) -> None:
    """Builds and opens the Edit Task dialog (Phase 1: name/priority; an "Add an
    action" search/filter picker -- the same one Add Task uses -- that can insert
    the new action before/after any existing one or at the end, not just append;
    per-action Copy/Move/Delete; and the values of an action's existing arguments
    -- see taskedit.py for what's editable and why). The Task Name field itself is
    read-only: Rename prompts for a new one and applies it on its own, immediately
    (see build_rename_dialog); Delete Task removes the Task and every reference to
    it (see build_delete_task_dialog).

    Built fresh each call rather than reused, since its content is entirely different
    per Task. Field widgets are kept in a plain dict (matching this file's existing
    ad-hoc widget-ref pattern) and read at Save time rather than using NiceGUI bindings.
    """
    task_name = edited_task.task_element.findtext("nme", "")
    field_refs: dict = {}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[500px] max-w-[900px] w-full p-6"):
        # Kept as a local (not in field_refs -- task_arg_values reads .value off
        # every entry there, which a ui.label doesn't have) so Rename can retitle
        # the still-open dialog: see rename_task_event.
        title_label = ui.label(f"{translate_string('Edit Task')}: {task_name}").classes(
            "text-xl font-bold text-blue-600",
        )

        with ui.row().classes("w-full gap-4"):
            # Read-only: an existing Task is renamed only through the Rename
            # button's prompt (guiwins_dialogs.build_rename_dialog), which is the one path that
            # rejects a name another Task already has. Rename writes the new
            # name back into this field so Ok/Save, which still read it, don't
            # apply the pre-rename name over the top.
            field_refs["name"] = (
                ui.input(translate_string("Task Name"), value=task_name).props("readonly").classes("flex-1")
            )
            field_refs["priority"] = ui.input(
                translate_string("Priority"),
                value=edited_task.task_element.findtext("pri", ""),
            ).classes("w-32")
            # The working copy, not the live element: every Task save path goes through
            # it (apply_edited_task_to_live_tree swaps the whole element into all_tasks,
            # render_standalone_task_xml deep-copies it), so a property written here
            # reaches the live tree, the export and the upload alike -- and Cancel here
            # still discards it.  See objprops.py's module docstring.
            build_properties_button(self, objprops.KIND_TASK, edited_task.task_element, dialog)
            # Beside it, on the same working copy: see the note above.
            build_taskernet_description_button(self, objprops.KIND_TASK, edited_task.task_element, task_name)

        # The picker and the action list -- see _build_task_action_editor, which this
        # dialog is where they came from.  Nothing here needs its render_actions back:
        # the editor redraws itself on everything that changes the list.
        _build_task_action_editor(self, edited_task, field_refs)

        field_refs["save_path"] = ui.input(
            translate_string("Save as"),
            value=taskedit_save.default_save_path(task_name, self.state),
        ).classes("w-full mt-2")
        build_redact_checkbox(field_refs)

        # Everything a change to this Task can be in is either the working copy's element --
        # every Add/Copy/Move/Delete Action, an action's Enabled switch, its If condition,
        # a Rename -- or a widget in field_refs, which is where the Priority, labels and
        # argument values sit until a save reads them.  See guiwins.editor_state.
        pending_changes = PendingChangesBanner()
        pending_changes.watch(dialog, lambda: editor_state(edited_task.task_element, field_refs))

        _render_edit_task_buttons(self, edited_task, field_refs, dialog, title_label, pending_changes)

    dialog.open()


def build_delete_task_dialog(
    self: MyGui,
    edited_task: taskedit_model.EditableTask,
    parent_dialog: ui.dialog,
) -> None:
    """Confirms deletion of a Task. Like guiwins_profedit.build_delete_profile_dialog there is no
    Keep/Delete Contents choice -- a Task owns nothing below it -- but unlike a
    Profile, other things point *at* a Task, so the dialog spells out exactly
    which references go away with it (see taskedit_save.delete_task): the owning
    Project(s)' Task list, and the Entry/Exit link of any Profile that runs it.

    Which of those references the delete repairs and which it leaves dangling is
    guiwins_impact.build_impact_panel's to say, and the four Delete dialogs all say
    it the same way.  It replaces the two counts this dialog used to work out for
    itself, and is read live for the same reason those were: the editor may have
    been open a while, and an answer worked out when it opened would describe a
    configuration that has since changed underneath it.
    """
    task_name = edited_task.task_element.findtext("nme", "")

    with ui.dialog().props("persistent") as confirm_dialog, ui.card().classes("min-w-[400px] max-w-[600px] w-full p-6"):
        ui.label(f"{translate_string('Delete Task')} '{task_name}'").classes("text-lg font-bold text-red-600")
        build_impact_panel(self, TASK, task_name)
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=confirm_dialog.close).props("outline")
            ui.button(
                translate_string("Delete Task"),
                on_click=lambda: self.event_handlers.editors.confirm_delete_task_event(
                    task_name,
                    confirm_dialog,
                    parent_dialog,
                ),
            ).classes("bg-red-500 text-white")

    confirm_dialog.open()


def _make_save_path_sync(field_refs: dict, last_auto_path: dict, state: RunState) -> Callable[..., None]:
    """The Task Name field's change handler for the Add Task dialog: keeps "Save as" in step with it.

    Args:
        field_refs: The dialog's widgets by key; "name" and "save_path" are read from it.
        last_auto_path: Holds, under "value", the path last worked out from the name.
        state: The run state whose output folder the path is worked out in.
    """

    def sync_save_path(_e: object | None = None) -> None:
        # Keep "Save as" in sync with the Task Name as the user types, so the
        # file actually lands under the name they gave the task -- but only
        # while it still holds what we last auto-computed; if the user has
        # since edited it manually, leave their edit alone. (Can't tell "manual
        # edit" apart via save_path's own on_change: NiceGUI fires that for
        # programmatic value sets too, so it would trip on the very first sync.)
        if field_refs["save_path"].value == last_auto_path["value"]:
            new_path = taskedit_save.default_save_path(field_refs["name"].value, state)
            field_refs["save_path"].value = new_path
            last_auto_path["value"] = new_path

    return sync_save_path


def _render_new_task_name_row(
    self: MyGui,
    edited_task: taskedit_model.EditableTask,
    field_refs: dict,
    dialog: ui.dialog,
    sync_save_path: Callable[..., None],
) -> None:
    """The Add Task dialog's Name and Priority fields and its Properties button."""
    with ui.row().classes("w-full gap-4"):
        field_refs["name"] = ui.input(translate_string("Task Name"), value="", on_change=sync_save_path).classes(
            "flex-1",
        )
        field_refs["priority"] = ui.input(translate_string("Priority"), value="100").classes("w-32")
        # Safe on a not-yet-registered Task, unlike Add Project's equivalent:
        # register_new_task stores THIS element object in all_tasks rather than a
        # copy of it, and every save path deep-copies it at write time, so properties
        # set before the Task exists are still on it once it does.
        build_properties_button(self, objprops.KIND_TASK, edited_task.task_element, dialog)
        build_taskernet_description_button(self, objprops.KIND_TASK, edited_task.task_element)


def _render_new_task_buttons(
    self: MyGui,
    edited_task: taskedit_model.EditableTask,
    field_refs: dict,
    dialog: ui.dialog,
    on_task_created: Callable[[str], None] | None,
) -> None:
    """The Add Task dialog's row of buttons: Cancel, Ok and the several Saves."""
    with ui.row().classes("w-full justify-end gap-2 mt-4"):
        ui.button(translate_string("Cancel"), on_click=dialog.close).props("outline")
        add_task_ok = ui.button(
            translate_string("Ok"),
            on_click=lambda: self.event_handlers.editors.keep_new_task_event(
                edited_task,
                field_refs,
                dialog,
                on_created=on_task_created,
            ),
        ).props("outline")
        with add_task_ok:
            ui.tooltip(
                translate_string(
                    "Adds the new Task to the loaded backup and closes this dialog. When you opened this from "
                    "the Add Task button, it is listed under the Project you had selected.\n\n"
                    "It is kept for this session only: no file is written and nothing is sent to your Android "
                    "device. Use 'Save To Current File' or 'Save To Android' to keep it. One press of Undo takes it "
                    "back.\n\n"
                    "If the name is already used by another Task, the dialog stays open and says why, so your "
                    "work is not lost.",
                ),
            ).style("white-space: pre-wrap")
        new_task_to_current_file = ui.button(
            translate_string("Save To Current File"),
            on_click=lambda: self.event_handlers.editors.save_new_task_to_current_file_event(
                edited_task,
                field_refs,
                dialog,
                on_created=on_task_created,
            ),
        ).props("outline")
        with new_task_to_current_file:
            ui.tooltip(
                translate_string(
                    "Saves the entire backup -- every Project, Profile and Task in it, not just this one -- "
                    "with the new Task added to it, the same way 'Ok' adds it.\n"
                    "It is written to a new, timestamped copy of the file currently loaded: "
                    "backup.xml becomes backup_20260728_143005.xml.\n"
                    "The file you loaded is never written to, so it is left exactly as it was.\n"
                    "The app then switches to the new copy, which becomes the current file for any further "
                    "editing and saving; saving again replaces the timestamp rather than adding a second one.\n"
                    "This writes to this computer only -- nothing is sent to your Android device.",
                ),
            ).style("white-space: pre-wrap")
        ui.button(
            translate_string("Save To Android"),
            on_click=lambda: self.event_handlers.android.open_save_to_android_dialog_event(
                edited_task,
                field_refs,
                dialog,
                on_created=on_task_created,
            ),
        ).props("outline")
        export_task = ui.button(
            translate_string("Export Task"),
            on_click=lambda: self.event_handlers.editors.save_new_task_event(
                edited_task,
                field_refs,
                dialog,
                on_created=on_task_created,
            ),
        ).classes("bg-blue-600")
        with export_task:
            ui.tooltip(
                translate_string(
                    "Exports the Task as XML to a file on your computer.",
                ),
            ).style("white-space: pre-wrap")


def build_add_task_dialog(
    self: MyGui,
    edited_task: taskedit_model.EditableTask,
    on_task_created: Callable[[str], None] | None = None,
    target_project_name: str = "",
) -> None:
    """Builds and opens the Add Task dialog: create a new Task, search/filter actions
    by name or category to add to it, edit their synthesized default argument values,
    remove any if needed, then save as a standalone .tsk.xml -- see taskedit.py for
    what's addable and why (roughly 3 in 4 action types; the rest need an App/Icon
    picker or are third-party plugin configs with no generic default, and show up
    greyed out with a reason instead of being clickable).

    Both the action picker and the "added so far" list are rebuilt (not just
    appended to) after every Add/Remove, since removing an action renumbers every
    action after it -- their field_refs keys (which embed act_number) would
    otherwise go stale.

    on_task_created, if given, is called with the new Task's id once Ok/Save/
    Save To Android actually registers it into the live tree -- the hook
    open_add_task_for_profile_link_event uses to link this brand-new Task in
    as a Profile's Entry/Exit Task the moment it exists, without this dialog
    (or its Save/Ok/Save To Android handlers) needing to know anything about
    Profiles itself.

    target_project_name is the single Project the top-level "Add Task" button
    requires be selected before this dialog opens (see
    userintr_editors.open_add_task_dialog_event) -- stored in field_refs (not a widget;
    there's nothing here for the user to change) purely so finish_new_task can
    read it back and add the new Task's id to that Project's <tids> once it's
    registered. Left "" for open_add_task_for_profile_link_event's nested
    dialog, which doesn't attach to a Project at all.
    """
    field_refs: dict = {"target_project_name": target_project_name}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[500px] max-w-[900px] w-full p-6"):
        ui.label(translate_string("Add Task")).classes("text-xl font-bold text-blue-600")

        last_auto_path = {"value": taskedit_save.default_save_path("", self.state)}
        sync_save_path = _make_save_path_sync(field_refs, last_auto_path, self.state)

        if target_project_name:
            ui.label(f"{translate_string('Adding to Project:')} {target_project_name}").classes(
                "text-sm text-gray-500 italic",
            )

        _render_new_task_name_row(self, edited_task, field_refs, dialog, sync_save_path)
        actions = _NewTaskActionList(self, edited_task, field_refs)
        DraftRow(self, edited_task, field_refs, dialog, actions.on_added).build()
        actions.build()

        field_refs["save_path"] = ui.input(
            translate_string("Save as"),
            value=last_auto_path["value"],
        ).classes("w-full mt-2")

        _render_new_task_buttons(self, edited_task, field_refs, dialog, on_task_created)

    dialog.open()
