"""GUI Window Classes and Definitions (NiceGUI Version)"""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import TYPE_CHECKING

from nicegui import app, context, ui

from maptasker.src import profedit, projedit, taskedit
from maptasker.src.colrmode import set_color_mode
from maptasker.src.guiutil2 import get_monospace_fonts, sort_languages_with_priority
from maptasker.src.maputil2 import translate_string
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import DIAGRAM_FILE, DIAGRAM_PROFILES_PER_LINE, logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from maptasker.src.userintr import MyGui


# ==========================================
# 2. DIALOGS & POPUPS
# ==========================================
def create_popup_window(title: str, message: str = "", close_button: bool = False) -> ui.dialog:
    """Creates a modal dialog. Replaces PopupWindow and CTkToplevel.

    Modified to expand width constraints allowing long text arrays
    and log data streams more horizontal breathing room.
    """
    # CHANGED: Increased max-w-[500px] to max-w-[800px] (or use w-[700px] / w-full)
    with ui.dialog() as dialog, ui.card().classes("min-w-[400px] max-w-[800px] w-full items-center p-6"):
        ui.label(title).classes("text-xl font-bold text-blue-600 text-center")
        if message:
            # The 'w-full' ensures the text block utilizes 100% of the wider card frame
            ui.label(message).classes("mt-2 text-left whitespace-pre-line break-words w-full text-base")
        if close_button:
            ui.button("Close", on_click=dialog.close).classes("mt-6 bg-red-500 text-white w-full")

    dialog.open()
    return dialog


def _refresh_position_options(
    edited_task: taskedit.EditableTask,
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


def _dropdown_current_label(arg: taskedit.EditableArg) -> str:
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
    self: MyGui,
    action: taskedit.EditableAction,
    arg: taskedit.EditableArg,
    key: str,
    field_refs: dict,
) -> None:
    """Renders the 'Perform Task' action's Name field: an ordinary text input
    the user can key any string into, plus a companion "Pick a Task" dropdown
    that -- when an option is chosen -- overwrites the text input with that
    Task's name. Either/or: whichever the user touches last is what's saved,
    since Save only ever reads the text input's own field_refs entry (this
    dropdown is deliberately never added to field_refs, so _task_arg_values
    can't see it).

    A plain ui.select with Quasar's "new-value-mode" was tried first so a
    single widget could both pick and free-type, but it only accepts a typed
    value when the user presses Enter -- clicking away (the far more likely
    action) silently reverts the field to its first option, which is exactly
    the "grabs the first task" bug this two-widget design avoids entirely.
    """
    field_refs[key] = ui.input(arg.arg_name, value=arg.current_value).classes("flex-1")

    task_names = taskedit.get_all_task_names()
    if not task_names:
        return

    def fill_in_picked_task(e) -> None:
        if e.value:
            field_refs[key].value = e.value

    ui.select(
        task_names,
        label="Pick a Task",
        with_input=True,
        on_change=fill_in_picked_task,
    ).classes("flex-1").props("dense")


def build_action_condition_dialog(
    self: MyGui,
    edited_task: taskedit.EditableTask,
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

    prefill = condition_cache.get(act_number) or taskedit.get_action_condition_values(action)
    operator_labels = [label for _code, label in taskedit.IF_CONDITION_OPERATORS]

    with ui.dialog() as condition_dialog, ui.card().classes("min-w-[400px] p-6"):
        ui.label(f"If Condition -- {act_number}: {action.action_name}").classes("text-lg font-bold text-blue-600")
        target_input = ui.input("Target", value=prefill[0]).classes("w-full")
        operator_select = ui.select(
            operator_labels,
            value=prefill[1] if prefill[1] in operator_labels else operator_labels[0],
            label="Operator",
        ).classes("w-full")
        value_input = ui.input("Value", value=prefill[2]).classes("w-full")
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(
                "Cancel",
                on_click=lambda: (condition_dialog.close(), checkbox.set_value(False)),
            ).props("outline")
            ui.button(
                "Ok",
                on_click=lambda: self.event_handlers.set_action_condition_event(
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
    edited_task: taskedit.EditableTask,
    action: taskedit.EditableAction,
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
    condition_count = taskedit.action_condition_count(action)
    if condition_count > 1:
        ui.label(
            f"Has {condition_count} chained If conditions -- not editable here.",
        ).classes("text-xs text-gray-500 italic")
        return

    target, operator_label, value = taskedit.get_action_condition_values(action)
    text = f"If: {target} {operator_label} {value}".rstrip() if condition_count else "If"
    checkbox = ui.checkbox(text, value=condition_count == 1).props("dense")

    def on_toggle(e, act_number=action.act_number, cb=checkbox) -> None:
        if e.value:
            build_action_condition_dialog(self, edited_task, act_number, cb, condition_cache)
            return
        current = next((a for a in edited_task.actions if a.act_number == act_number), None)
        if current is not None and taskedit.action_has_condition(current):
            condition_cache[act_number] = taskedit.get_action_condition_values(current)
        self.event_handlers.remove_action_condition_event(edited_task, act_number)
        cb.set_text("If")

    checkbox.on_value_change(on_toggle)


def _render_continue_after_error_checkbox(
    self: MyGui,
    edited_task: taskedit.EditableTask,
    action: taskedit.EditableAction,
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
        "Continue Task After Error",
        value=taskedit.action_continues_after_error(action),
        on_change=lambda e, n=action.act_number: self.event_handlers.set_action_continue_after_error_event(
            edited_task,
            n,
            e.value,
        ),
    ).props("dense")


def build_if_variant_dialog(on_choice: Callable[[str], None]) -> None:
    """Prompts for how much of an If block to insert when the user picks the
    "If" action in an Add/Edit Task action picker: just the "If", "If" plus a
    matching "End If", or a full "If"/"Else"/"End If" skeleton -- see
    taskedit.IF_BLOCK_VARIANTS/add_if_block_to_task. Fires on_choice(variant)
    only when one is clicked; Cancel inserts nothing.
    """
    with ui.dialog() as variant_dialog, ui.card().classes("min-w-[300px] p-6"):
        ui.label("Add 'If' Action").classes("text-lg font-bold text-blue-600")
        ui.label("Insert just the 'If', or a complete block?").classes("text-sm mb-2")
        for variant in taskedit.IF_BLOCK_VARIANTS:
            ui.button(
                variant,
                on_click=lambda v=variant: (variant_dialog.close(), on_choice(v)),
            ).classes("w-full")
        with ui.row().classes("w-full justify-end mt-2"):
            ui.button("Cancel", on_click=variant_dialog.close).props("outline")

    variant_dialog.open()


def build_edit_task_dialog(self: MyGui, edited_task: taskedit.EditableTask) -> None:
    """Builds and opens the Edit Task dialog (Phase 1: name/priority; an "Add an
    action" search/filter picker -- the same one Add Task uses -- that can insert
    the new action before/after any existing one or at the end, not just append;
    per-action Copy/Move/Delete; and the values of an action's existing arguments
    -- see taskedit.py for what's editable and why).

    Built fresh each call rather than reused, since its content is entirely different
    per Task. Field widgets are kept in a plain dict (matching this file's existing
    ad-hoc widget-ref pattern) and read at Save time rather than using NiceGUI bindings.
    """
    task_name = edited_task.task_element.findtext("nme", "")
    field_refs: dict = {}
    # Last-known per-action If condition values, keyed by act_number -- lets an
    # uncheck/re-check of the "If" checkbox edit instead of starting over.
    condition_cache: dict[int, tuple[str, str, str]] = {}
    category_names = sorted({row["category_name"] for row in taskedit.list_addable_actions()})
    # Maps each "Position" dropdown label to the act_number to insert at (None
    # for "At the End") -- kept out-of-band rather than as the ui.select's own
    # value/options dict, since "Before N" and "After N-1" resolve to the exact
    # same act_number and a dict's keys (which NiceGUI's dict-options form uses
    # as the value) must be unique, but the two need to stay distinct, readable
    # menu entries.
    position_labels: dict[str, int | None] = {}

    with ui.dialog() as dialog, ui.card().classes("min-w-[500px] max-w-[900px] w-full p-6"):
        ui.label(f"Edit Task: {task_name}").classes("text-xl font-bold text-blue-600")

        with ui.row().classes("w-full gap-4"):
            field_refs["name"] = ui.input("Task Name", value=task_name).classes("flex-1")
            field_refs["priority"] = ui.input(
                "Priority",
                value=edited_task.task_element.findtext("pri", ""),
            ).classes("w-32")

        ui.label("Add an action").classes("text-sm font-bold mt-2")
        with ui.row().classes("w-full gap-4"):
            search_input = ui.input("Search actions").classes("flex-1")
            category_select = ui.select(["All", *category_names], value="All").classes("w-48")
        position_select = ui.select([], label="Position", with_input=True).classes("w-full").props("dense")

        picker_container = ui.column().classes("w-full")
        ui.label("Actions in this Task").classes("text-sm font-bold mt-2")
        actions_container = ui.column().classes("w-full")
        # act_number of the action most recently added in this dialog session --
        # render_actions highlights it so it's easy to spot in a long list.
        last_added_act_number: int | None = None

        def clear_last_added() -> None:
            # Copy/Move/Delete all renumber the list, so a stale act_number here
            # would risk highlighting the wrong action -- drop the highlight
            # instead of letting it follow whatever action inherits the number.
            nonlocal last_added_act_number
            last_added_act_number = None

        def refresh_position_options() -> None:
            _refresh_position_options(edited_task, position_select, position_labels)

        def add_picked_action(action_key: str) -> None:
            nonlocal last_added_act_number
            # "If" gets an extra prompt (just the If, or a whole If/Else/End If
            # block?) before anything is inserted; every other action goes in
            # directly. Position is resolved when the choice lands, not at
            # picker-click time -- same value, and the variant dialog is modal.
            if action_key == taskedit.IF_ACTION_KEY:

                def _add_if_block(variant: str) -> None:
                    nonlocal last_added_act_number
                    act_number = self.event_handlers.add_if_block_to_edit_task_event(
                        edited_task,
                        variant,
                        position_labels.get(position_select.value),
                    )
                    if act_number is not None:
                        last_added_act_number = act_number
                    render_actions()
                    refresh_position_options()

                build_if_variant_dialog(_add_if_block)
                return
            act_number = self.event_handlers.add_action_to_edit_task_event(
                edited_task,
                action_key,
                position_labels.get(position_select.value),
            )
            if act_number is not None:
                last_added_act_number = act_number
            render_actions()
            refresh_position_options()

        def refresh_picker(_e=None) -> None:
            picker_container.clear()
            rows = taskedit.search_addable_actions(search_input.value, category_select.value)
            with picker_container, ui.scroll_area().classes("w-full h-40 border rounded p-2"):
                for row in rows:
                    if row["addable"]:
                        ui.button(
                            f"{row['name']} ({row['category_name']})",
                            on_click=lambda r=row: add_picked_action(r["action_key"]),
                        ).props("flat align=left dense").classes("w-full justify-start")
                    else:
                        with ui.column().classes("w-full gap-0"):
                            ui.label(f"{row['name']} ({row['category_name']})").classes("text-gray-400")
                            ui.label(row["reason"]).classes("text-xs text-gray-500 italic")

        search_input.on_value_change(refresh_picker)
        category_select.on_value_change(refresh_picker)

        def render_actions() -> None:
            # Rebuild from scratch -- Copy/Move/Delete all renumber every action, so
            # stale act*_arg* keys must not survive into the next Save.
            for key in [k for k in field_refs if k.startswith("act")]:
                del field_refs[key]
            actions_container.clear()
            with actions_container, ui.scroll_area().classes("w-full h-96 border rounded p-2"):
                if not edited_task.actions:
                    ui.label("No actions in this Task.").classes("text-xs text-gray-500 italic")
                last_position = len(edited_task.actions) - 1
                indent_spaces = _action_indent_spaces(self)
                display_levels = taskedit.action_display_levels(edited_task.actions)
                for action, nest_level in zip(edited_task.actions, display_levels, strict=True):
                    # Indent with non-breaking spaces -- plain ones collapse in the rendered header.
                    indent_pad = "\u00a0" * (indent_spaces * nest_level)
                    is_last_added = action.act_number == last_added_act_number
                    header = f"{indent_pad}{action.act_number}: {action.action_name}"
                    if is_last_added:
                        header += "  \u2190 just added"
                    action_expansion = ui.expansion(header, value=is_last_added).classes("w-full")
                    if is_last_added:
                        action_expansion.classes("bg-amber-100 dark:bg-amber-900 border-2 border-amber-400 rounded")
                    with action_expansion:
                        with ui.row().classes("w-full items-center gap-2 mb-2"):
                            ui.button(
                                "Copy",
                                on_click=lambda n=action.act_number: (
                                    clear_last_added(),
                                    self.event_handlers.copy_action_in_edit_task_event(edited_task, n),
                                    render_actions(),
                                    refresh_position_options(),
                                ),
                            ).props("flat color=blue dense")
                            move_to_input = (
                                ui
                                .number(
                                    "Move to #",
                                    value=action.act_number,
                                    min=0,
                                    max=last_position,
                                )
                                .classes("w-24")
                                .props("dense")
                            )
                            ui.button(
                                "Move",
                                on_click=lambda n=action.act_number, target=move_to_input: (
                                    clear_last_added(),
                                    self.event_handlers.move_action_in_edit_task_event(
                                        edited_task,
                                        n,
                                        int(target.value) if target.value is not None else n,
                                    ),
                                    render_actions(),
                                    refresh_position_options(),
                                ),
                            ).props("flat color=orange dense")
                            ui.button(
                                "Delete",
                                on_click=lambda n=action.act_number: (
                                    clear_last_added(),
                                    self.event_handlers.delete_action_in_edit_task_event(edited_task, n),
                                    render_actions(),
                                    refresh_position_options(),
                                ),
                            ).props("flat color=red dense")

                        action_enabled_switch = ui.switch(
                            value=taskedit.is_action_enabled(action),
                            on_change=lambda e, n=action.act_number: self.event_handlers.set_action_enabled_event(
                                edited_task,
                                n,
                                e.value,
                            ),
                        ).classes("mb-2")
                        action_enabled_switch.bind_text_from(
                            action_enabled_switch,
                            "value",
                            backward=lambda v: "Enabled" if v else "Disabled",
                        )

                        field_refs[taskedit.label_key(action.act_number)] = ui.input(
                            "Label",
                            value=taskedit.get_action_label(action),
                        ).classes("w-full")

                        if action.code != taskedit.IF_ACTION_CODE:
                            _render_action_condition_checkbox(self, edited_task, action, condition_cache)
                        _render_continue_after_error_checkbox(self, edited_task, action)

                        if not action.args:
                            ui.label("No editable arguments.").classes("text-xs text-gray-500 italic")
                        for arg in action.args:
                            key = taskedit.arg_key(action.act_number, arg.arg_id)
                            with ui.row().classes("w-full items-center gap-2"):
                                if arg.widget_kind == "checkbox":
                                    field_refs[key] = ui.checkbox(arg.arg_name, value=arg.current_value == "1")
                                elif arg.widget_kind == "dropdown":
                                    options = arg.dropdown_options or []
                                    field_refs[key] = ui.select(
                                        options,
                                        value=_dropdown_current_label(arg),
                                        label=arg.arg_name,
                                    ).classes(
                                        "flex-1",
                                    )
                                elif taskedit.is_perform_task_name_arg(action.code, arg):
                                    _render_task_name_field(self, action, arg, key, field_refs)
                                elif arg.widget_kind in ("text", "raw_fallback"):
                                    field_refs[key] = ui.input(arg.arg_name, value=arg.current_value).classes("flex-1")
                                    if arg.readonly_note:
                                        ui.label(arg.readonly_note).classes("text-xs text-gray-500 italic")
                                else:  # readonly
                                    ui.input(arg.arg_name, value=arg.current_value).props("readonly").classes("flex-1")
                                    if arg.readonly_note:
                                        ui.label(arg.readonly_note).classes("text-xs text-gray-500 italic")

        refresh_picker()
        refresh_position_options()
        render_actions()

        field_refs["save_path"] = ui.input(
            "Save as",
            value=taskedit.default_save_path(task_name),
        ).classes("w-full mt-2")

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button("Cancel", on_click=dialog.close).props("outline")
            ui.button(
                "Ok",
                on_click=lambda: self.event_handlers.keep_edited_task_event(edited_task, field_refs, dialog),
            ).props("outline")
            ui.button(
                "Save To Current File",
                on_click=lambda: self.event_handlers.save_edited_task_to_current_file_event(
                    edited_task,
                    field_refs,
                    dialog,
                ),
            ).props("outline")
            task_to_android = ui.button(
                "Save To Android",
                on_click=lambda: self.event_handlers.open_save_to_android_dialog_event(
                    edited_task,
                    field_refs,
                    dialog,
                ),
            ).props("outline")
            with task_to_android:
                ui.tooltip(
                    "This will save the Task directly into the active Tasker session on your Android device.\n\n"
                    "Tasker version 6.2 or greater is required for this to work."
                    "The Android device must be on the same network, and the IP Address and Port\n"
                    "must match the Android device's Tasker server settings.\n\n"
                    "You will be prompted twice for authorization to write to Tasker on the Android device, and the Task "
                    "will be loaded directly into the active Tasker session.\n\n"
                    "You must exit and restart Tasker to see the new Task in the Tasker UI.",
                ).style("white-space: pre-line")
            task_save = ui.button(
                "Export Task",
                on_click=lambda: self.event_handlers.save_edited_task_event(edited_task, field_refs, dialog),
            ).classes("bg-blue-600")
            with task_save:
                ui.tooltip(
                    "This will save the Task directly to your current drive.\n\n",
                ).style("white-space: pre-line")

    dialog.open()


def build_save_to_android_dialog(
    self: MyGui,
    edited_task: taskedit.EditableTask,
    field_refs: dict,
    parent_dialog: ui.dialog,
    on_created: Callable[[str], None] | None = None,
) -> None:
    """Prompts for the Android device's IP address and port, then imports the
    current Task (name/priority/args as they stand in the parent dialog's fields)
    directly into Tasker on the device via its HTTP API's POST /api/import
    endpoint -- see taskedit.save_task_to_android. On success both this prompt and
    the parent (Edit/Add Task) dialog are closed.

    on_created is threaded through from build_add_task_dialog's own
    on_task_created -- see that parameter's docstring.
    """
    default_ip = getattr(self, "android_ipaddr", "") or "192.168.0.210"
    default_port = getattr(self, "android_port", "") or "1821"

    with ui.dialog() as android_dialog, ui.card().classes("min-w-[350px] p-6"):
        ui.label("Save Task To Android Device").classes("text-lg font-bold text-blue-600")
        android_field_refs = {
            "ip_address": ui.input("Android IP Address", value=default_ip).classes("w-full"),
            "ip_port": ui.input("Port", value=default_port).classes("w-full"),
        }
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button("Cancel", on_click=android_dialog.close).props("outline")
            save_to_android = ui.button(
                "Save",
                on_click=lambda: self.event_handlers.save_task_to_android_event(
                    edited_task,
                    field_refs,
                    android_field_refs,
                    android_dialog,
                    parent_dialog,
                    on_created=on_created,
                ),
            ).classes("bg-blue-600")
            with save_to_android:
                ui.tooltip(
                    "This will save the Task directly into Tasker running on the Android device running the Tasker server.\n\n"
                    "The IP Address and Port must match the Android device's Tasker server settings.\n\n"
                    "You will be prompted twice for authorization to write to Tasker on the Android device, and the Task."
                    "and its own actions will determine where it is saved on the device.",
                ).style("white-space: pre-line")

    android_dialog.open()


def set_weekday_checkboxes(boxes: dict[int, ui.checkbox], selected: set[int]) -> None:
    """Sets a Day condition's weekday checkboxes (1=Sunday..7=Saturday, keyed the
    same way as profedit.WEEKDAY_NAMES) to match `selected` -- backs the
    All/None/Odd quick-select buttons in build_edit_profile_dialog. Purely a
    client-side widget update; the actual condition isn't touched until Save
    reads these checkboxes' values like any other field.
    """
    for day_number, checkbox in boxes.items():
        checkbox.value = day_number in selected


def _mark_unsupported_options(select_widget: ui.select, unsupported_values: set) -> None:
    """Greys out and blocks selection of any option in select_widget whose
    underlying value is in unsupported_values -- e.g. an Event/State condition
    code this tool can't synthesize from scratch (see
    taskedit.classify_action_addability). NiceGUI's ui.select has no public
    Python API for disabling individual options, so this reaches into the
    Quasar QSelect props it builds internally: each option becomes
    {"value": index, "label": ...}, and adding a "disable": True key there
    (plus the "option-disable" prop telling QSelect which key to read) makes
    Quasar itself refuse the click -- the popup entry renders greyed out and
    unclickable, not just visually different.

    Must be called right after construction, before anything else touches the
    widget's options -- ui.select regenerates self._props["options"] from
    scratch on every .update()/.set_options() call (dropping any "disable" key
    added here), and this codebase's condition pickers are always freshly
    built per render rather than updated in place, so that's a non-issue here.

    Mutating a nested prop (each option dict, here) fires the *same*
    props-changed signal as a top-level one -- which normally triggers exactly
    that regeneration, self-defeating the mutation before it's ever read back.
    suspend_updates() defers that signal until the whole batch (every
    "disable" flag plus the "option-disable" prop) is in place.
    """
    with select_widget._props.suspend_updates():  # noqa: SLF001
        for option, value in zip(select_widget._props["options"], select_widget._values, strict=True):  # noqa: SLF001
            if value in unsupported_values:
                option["disable"] = True
        select_widget.props('option-disable="disable"')


def _build_profile_editor_body(self: MyGui, edited_profile: profedit.EditableProfile, field_refs: dict) -> None:
    """Renders a Profile's Enabled/Disabled toggle, Entry/Exit Task Link/Unlink
    controls, and its conditions section (per-condition Add/Edit/Delete for the
    flat condition types -- Time, Day, App, Loc; Event/State's own code
    pickers; and editing a State/Event condition's plugin/built-in arguments,
    reusing the same arg-widget rendering as Task Action editing) -- shared by
    build_edit_profile_dialog and build_add_profile_dialog, since a brand-new
    Profile being added from scratch needs the exact same Task-linking and
    condition-editing machinery as one already in the backup; only the dialog
    chrome around it (title, Name field, Save-path field, and button row)
    differs between the two. Must be called inside the caller's own
    `with ui.dialog(), ui.card():` block, after field_refs["name"] is set.
    """
    enabled_switch = ui.switch(
        value=profedit.is_profile_enabled(edited_profile),
        on_change=lambda e: self.event_handlers.set_profile_enabled_event(edited_profile, e.value),
    )
    enabled_switch.bind_text_from(enabled_switch, "value", backward=lambda v: "Enabled" if v else "Disabled")

    tasks_container = ui.column().classes("w-full")

    def render_task_links() -> None:
        # Rebuild from scratch so the Link/Unlink controls always reflect the
        # profile's current entry_task_id/exit_task_id after a Link or Unlink.
        tasks_container.clear()
        all_tasks_by_name = PrimeItems.tasker_root_elements.get("all_tasks_by_name", {})
        task_names = sorted(all_tasks_by_name)
        with tasks_container:
            for link_type, task_id in (
                ("Entry", edited_profile.entry_task_id),
                ("Exit", edited_profile.exit_task_id),
            ):
                with ui.row().classes("w-full items-center gap-2 mt-2"):
                    current_name = (
                        next(
                            (name for name, entry in all_tasks_by_name.items() if entry["id"] == task_id),
                            "",
                        )
                        if task_id
                        else ""
                    )
                    ui.label(f"{link_type} Task:").classes("font-bold w-24")
                    if current_name:
                        ui.label(current_name).classes("flex-1")
                        ui.button(
                            "Unlink",
                            on_click=lambda lt=link_type: (
                                self.event_handlers.unlink_task_from_profile_event(edited_profile, lt),
                                render_task_links(),
                            ),
                        ).props("flat color=red dense")
                    else:
                        picker = (
                            ui
                            .select(task_names, label="Choose a Task", with_input=True)
                            .classes("flex-1")
                            .props("dense")
                        )
                        # Registered under a fixed key (not cleared/rebuilt like the cond*
                        # keys) so Save/Ok/Save To Android can link in whatever's currently
                        # picked here even if the user never clicked "Link" separately --
                        # see userintr._link_pending_task_pickers.
                        field_refs[f"{link_type.lower()}_task_picker"] = picker
                        ui.button(
                            "Link",
                            on_click=lambda lt=link_type, p=picker: (
                                self.event_handlers.link_task_to_profile_event(edited_profile, lt, p.value),
                                render_task_links(),
                            ),
                        ).props("flat color=blue dense")
                        # Alternative to picking an existing Task: build a brand-new one
                        # inline (the same Add Task dialog the top-level "Add Task" button
                        # opens) and link it in as this Profile's Entry/Exit Task the
                        # moment it's created -- see open_add_task_for_profile_link_event.
                        ui.button(
                            "Add Task",
                            on_click=lambda lt=link_type: self.event_handlers.open_add_task_for_profile_link_event(
                                edited_profile,
                                lt,
                                render_task_links,
                            ),
                        ).props("flat color=blue dense")

    render_task_links()

    ui.label("Conditions").classes("text-sm font-bold mt-4")
    conditions_container = ui.column().classes("w-full")

    def render_conditions() -> None:
        # Rebuild from scratch -- Add/Delete Condition and an App condition's
        # Add/Remove App Entry all change what field_refs keys are valid, so
        # stale cond*_* keys must not survive into the next Save. But field
        # values (Time/Loc/Day/App/State/Event) are only ever written back
        # onto the XML at Save time -- they're not applied immediately like
        # Add/Delete Condition or Link/Unlink Task are -- so rebuilding from
        # the XML alone would silently discard whatever the user had already
        # entered elsewhere in this same dialog but hadn't saved yet (most
        # noticeable on Day, with its 51 checkboxes, but the same gap exists
        # for every field here). Snapshot the current widget values first
        # (same string coercion save_edited_profile_event uses) so each
        # widget below can prefer its own not-yet-saved value over the one
        # freshly read from the XML.
        unsaved = {
            key: ("1" if widget.value is True else "0" if widget.value is False else str(widget.value))
            for key, widget in field_refs.items()
            if key.startswith("cond")
        }

        def checkbox_initial(key: str, default: bool) -> bool:
            return unsaved[key] in ("1", "true", "True") if key in unsaved else default

        def text_initial(key: str, default: str) -> str:
            return unsaved.get(key, default)

        for key in [k for k in field_refs if k.startswith("cond")]:
            del field_refs[key]
        conditions_container.clear()
        with conditions_container:
            if not edited_profile.conditions:
                ui.label("No conditions on this Profile.").classes("text-xs text-gray-500 italic")
            for condition in edited_profile.conditions:
                header = f"{condition.cond_index}: {profedit.get_condition_display_name(condition)}"
                with ui.expansion(header).classes("w-full"):
                    ui.button(
                        "Delete Condition",
                        on_click=lambda ci=condition.cond_index: (
                            self.event_handlers.remove_condition_from_profile_event(edited_profile, ci),
                            render_conditions(),
                        ),
                    ).props("flat color=red dense").classes("mb-2")

                    if condition.cond_type in ("State", "Event"):
                        if not condition.args:
                            ui.label(
                                "No editable arguments (code not mapped, or this condition has none).",
                            ).classes("text-xs text-gray-500 italic")
                        for arg in condition.args:
                            key = profedit.condition_arg_key(condition.cond_index, arg.arg_id)
                            with ui.row().classes("w-full items-center gap-2"):
                                if arg.widget_kind == "checkbox":
                                    field_refs[key] = ui.checkbox(
                                        arg.arg_name,
                                        value=checkbox_initial(key, arg.current_value == "1"),
                                    )
                                elif arg.widget_kind == "dropdown":
                                    options = arg.dropdown_options or []
                                    try:
                                        current_label = options[int(arg.current_value)]
                                    except (ValueError, IndexError):
                                        current_label = options[0] if options else ""
                                    field_refs[key] = ui.select(
                                        options,
                                        value=text_initial(key, current_label),
                                        label=arg.arg_name,
                                    ).classes("flex-1")
                                elif arg.widget_kind in ("text", "raw_fallback"):
                                    field_refs[key] = ui.input(
                                        arg.arg_name,
                                        value=text_initial(key, arg.current_value),
                                    ).classes("flex-1")
                                    if arg.readonly_note:
                                        ui.label(arg.readonly_note).classes("text-xs text-gray-500 italic")
                                else:  # readonly
                                    ui.input(arg.arg_name, value=arg.current_value).props("readonly").classes(
                                        "flex-1",
                                    )
                                    if arg.readonly_note:
                                        ui.label(arg.readonly_note).classes("text-xs text-gray-500 italic")

                    elif condition.cond_type == "Time":
                        values = profedit.get_time_field_values(condition)
                        start_key = profedit.condition_field_key(condition.cond_index, "start_time")
                        end_key = profedit.condition_field_key(condition.cond_index, "end_time")
                        rep_value_key = profedit.condition_field_key(condition.cond_index, "rep_value")
                        rep_unit_key = profedit.condition_field_key(condition.cond_index, "rep_unit")
                        with ui.row().classes("w-full gap-2 items-end"):
                            # Plain text, not type=time: a native time input can't hold a
                            # %variable value (see profedit.get_time_field_values), only
                            # "hh:mm AM/PM", so this field needs to accept either form as free text.
                            field_refs[start_key] = ui.input(
                                "Start Time",
                                value=text_initial(start_key, values["start_time"]),
                                placeholder="hh:mm AM/PM or %variable",
                            ).classes("flex-1")
                            field_refs[end_key] = ui.input(
                                "End Time",
                                value=text_initial(end_key, values["end_time"]),
                                placeholder="hh:mm AM/PM or %variable",
                            ).classes("flex-1")
                        with ui.row().classes("w-full gap-2 items-end mt-2"):
                            field_refs[rep_value_key] = ui.input(
                                "Every",
                                value=text_initial(rep_value_key, values["rep_value"]),
                            ).classes("w-24")
                            field_refs[rep_unit_key] = (
                                ui
                                .select(
                                    ["Hours", "Minutes"],
                                    value=text_initial(rep_unit_key, values["rep_unit"]),
                                )
                                .classes("w-32")
                                .props("dense")
                            )

                    elif condition.cond_type == "Loc":
                        values = profedit.get_loc_field_values(condition)
                        with ui.row().classes("w-full gap-2"):
                            for key, label in (
                                ("lat", "Latitude"),
                                ("long", "Longitude"),
                                ("rad", "Radius (m)"),
                            ):
                                field_key = profedit.condition_field_key(condition.cond_index, key)
                                field_refs[field_key] = ui.input(
                                    label,
                                    value=text_initial(field_key, values[key]),
                                ).classes("flex-1")

                    elif condition.cond_type == "Day":
                        weekday_checkboxes: dict[int, ui.checkbox] = {}

                        ui.label("Week-Day").classes("text-xs font-bold text-gray-500")
                        selected_weekdays = set(profedit.get_day_selected_weekdays(condition))
                        with ui.row().classes("w-full gap-2 flex-wrap"):
                            for day_number in range(1, 8):
                                day_key = profedit.condition_field_key(condition.cond_index, f"wday{day_number}")
                                checkbox = ui.checkbox(
                                    profedit.WEEKDAY_NAMES[day_number],
                                    value=checkbox_initial(day_key, day_number in selected_weekdays),
                                )
                                weekday_checkboxes[day_number] = checkbox
                                field_refs[day_key] = checkbox
                        with ui.row().classes("w-full gap-2 mb-2"):
                            ui.button(
                                "All",
                                on_click=lambda boxes=weekday_checkboxes: set_weekday_checkboxes(
                                    boxes,
                                    set(range(1, 8)),
                                ),
                            ).props("flat dense")
                            ui.button(
                                "None",
                                on_click=lambda boxes=weekday_checkboxes: set_weekday_checkboxes(boxes, set()),
                            ).props("flat dense")
                            ui.button(
                                "Odd",
                                on_click=lambda boxes=weekday_checkboxes: set_weekday_checkboxes(
                                    boxes,
                                    {1, 3, 5, 7},
                                ),
                            ).props("flat dense")

                        ui.label("Month").classes("text-xs font-bold text-gray-500")
                        selected_months = set(profedit.get_day_selected_months(condition))
                        with ui.row().classes("w-full gap-2 flex-wrap mb-2"):
                            for month_number in range(12):
                                month_key = profedit.condition_field_key(condition.cond_index, f"mnth{month_number}")
                                field_refs[month_key] = ui.checkbox(
                                    profedit.MONTH_NAMES[month_number],
                                    value=checkbox_initial(month_key, month_number in selected_months),
                                )

                        ui.label("Day of Month").classes("text-xs font-bold text-gray-500")
                        selected_month_days = set(profedit.get_day_selected_month_days(condition))
                        with ui.row().classes("w-full gap-2 flex-wrap"):
                            for day_of_month in range(1, 32):
                                mday_key = profedit.condition_field_key(condition.cond_index, f"mday{day_of_month}")
                                field_refs[mday_key] = ui.checkbox(
                                    str(day_of_month),
                                    value=checkbox_initial(mday_key, day_of_month in selected_month_days),
                                )
                            last_day_key = profedit.condition_field_key(
                                condition.cond_index,
                                f"mday{profedit.DAY_OF_MONTH_LAST_DAY}",
                            )
                            field_refs[last_day_key] = ui.checkbox(
                                "Last Day Of Month",
                                value=checkbox_initial(
                                    last_day_key,
                                    profedit.DAY_OF_MONTH_LAST_DAY in selected_month_days,
                                ),
                            )

                    elif condition.cond_type == "App":
                        for entry_index, entry in enumerate(profedit.get_app_entries(condition)):
                            with ui.row().classes("w-full items-center gap-2"):
                                pkg_key = profedit.condition_field_key(condition.cond_index, f"app{entry_index}_pkg")
                                label_key = profedit.condition_field_key(
                                    condition.cond_index,
                                    f"app{entry_index}_label",
                                )
                                cls_key = profedit.condition_field_key(condition.cond_index, f"app{entry_index}_cls")
                                field_refs[pkg_key] = ui.input(
                                    "Package",
                                    value=text_initial(pkg_key, entry["pkg"]),
                                ).classes("flex-1")
                                field_refs[label_key] = ui.input(
                                    "Label",
                                    value=text_initial(label_key, entry["label"]),
                                ).classes("flex-1")
                                field_refs[cls_key] = ui.input(
                                    "Class (optional)",
                                    value=text_initial(cls_key, entry["cls"]),
                                ).classes("flex-1")
                                ui.button(
                                    "Remove",
                                    on_click=lambda ci=condition.cond_index, ei=entry_index: (
                                        self.event_handlers.remove_app_entry_event(edited_profile, ci, ei),
                                        render_conditions(),
                                    ),
                                ).props("flat color=red dense")
                        ui.button(
                            "Add App Entry",
                            on_click=lambda ci=condition.cond_index: (
                                self.event_handlers.add_app_entry_event(edited_profile, ci),
                                render_conditions(),
                            ),
                        ).props("flat color=blue dense")

            with ui.row().classes("w-full items-center gap-2 mt-2"):
                add_type_picker = (
                    ui
                    .select(list(profedit.CONDITION_TYPES_ADDABLE), label="Condition Type")
                    .classes("w-48")
                    .props("dense")
                )
                # Only shown once "Event"/"State" is picked above -- unlike Time/Day/App/
                # Loc, an Event/State condition's fields depend on which of the ~60-100+
                # codes was chosen (see profedit.list_addable_events/list_addable_states),
                # so each needs its own second, searchable picker (with_input=True) rather
                # than being addable from the type name alone. Every code is listed (not
                # just the addable ones) so the user can see what exists, but any not
                # addable (e.g. a third-party plugin needing a Bundle/App payload this
                # tool can't synthesize -- see taskedit.classify_action_addability) is
                # labeled "(Not Supported)" and greyed out/unselectable -- see
                # _mark_unsupported_options.
                event_rows = profedit.list_addable_events()
                event_options = {
                    row["condition_key"]: row["name"] if row["addable"] else f"{row['name']} (Not Supported)"
                    for row in event_rows
                }
                event_type_picker = (
                    ui.select(event_options, label="Event Type", with_input=True).classes("flex-1").props("dense")
                )
                _mark_unsupported_options(
                    event_type_picker,
                    {row["condition_key"] for row in event_rows if not row["addable"]},
                )
                event_type_picker.bind_visibility_from(add_type_picker, "value", backward=lambda v: v == "Event")

                state_rows = profedit.list_addable_states()
                state_options = {
                    row["condition_key"]: row["name"] if row["addable"] else f"{row['name']} (Not Supported)"
                    for row in state_rows
                }
                state_type_picker = (
                    ui.select(state_options, label="State Type", with_input=True).classes("flex-1").props("dense")
                )
                _mark_unsupported_options(
                    state_type_picker,
                    {row["condition_key"] for row in state_rows if not row["addable"]},
                )
                state_type_picker.bind_visibility_from(add_type_picker, "value", backward=lambda v: v == "State")

                def add_condition_clicked(
                    type_picker=add_type_picker,
                    event_picker=event_type_picker,
                    state_picker=state_type_picker,
                ) -> None:
                    if type_picker.value == "Event":
                        self.event_handlers.add_event_condition_to_profile_event(edited_profile, event_picker.value)
                    elif type_picker.value == "State":
                        self.event_handlers.add_state_condition_to_profile_event(edited_profile, state_picker.value)
                    else:
                        self.event_handlers.add_condition_to_profile_event(edited_profile, type_picker.value)
                    render_conditions()

                ui.button("Add Condition", on_click=add_condition_clicked).props("flat color=blue dense")

    render_conditions()


def build_edit_profile_dialog(self: MyGui, edited_profile: profedit.EditableProfile) -> None:
    """Builds and opens the Edit Profile dialog: Rename, Enabled/Disabled toggle,
    Entry/Exit Task Link/Unlink, and per-condition Add/Edit/Delete (see
    _build_profile_editor_body for the shared body this and build_add_profile_dialog
    both render).

    Built fresh each call rather than reused, since its content is entirely different
    per Profile. Field widgets are kept in a plain dict (matching this file's existing
    ad-hoc widget-ref pattern) and read at Save time rather than using NiceGUI bindings.
    """
    profile_name = edited_profile.profile_element.findtext("nme", "")
    field_refs: dict = {}

    with ui.dialog() as dialog, ui.card().classes("min-w-[500px] max-w-[900px] w-full p-6"):
        ui.label(f"Edit Profile: {profile_name}").classes("text-xl font-bold text-blue-600")

        field_refs["name"] = ui.input("Profile Name", value=profile_name).classes("w-full")

        _build_profile_editor_body(self, edited_profile, field_refs)

        field_refs["save_path"] = ui.input(
            "Save as",
            value=profedit.default_save_path(profile_name),
        ).classes("w-full mt-2")

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button("Cancel", on_click=dialog.close).props("outline")
            delete_profile_button = ui.button(
                "Delete Profile",
                on_click=lambda: self.event_handlers.delete_profile_event(edited_profile, dialog),
            ).classes("bg-red-500 text-white")
            with delete_profile_button:
                ui.tooltip(
                    "Deletes only this Profile. Its Entry/Exit Tasks are kept -- a Task is owned by "
                    "the Project, not by the Profile, and the same Task can be used by other Profiles.",
                )
            ui.button(
                "Ok",
                on_click=lambda: self.event_handlers.keep_edited_profile_event(edited_profile, field_refs, dialog),
            ).props("outline")
            ui.button(
                "Save To Current File",
                on_click=lambda: self.event_handlers.save_edited_profile_to_current_file_event(
                    edited_profile,
                    field_refs,
                    dialog,
                ),
            ).props("outline")
            profile_to_android = ui.button(
                "Save To Android",
                on_click=lambda: self.event_handlers.open_save_profile_to_android_dialog_event(
                    edited_profile,
                    field_refs,
                    dialog,
                ),
            ).props("outline")
            with profile_to_android:
                ui.tooltip(
                    "This will write the Profile as a standalone file onto your Android device, "
                    "under /Tasker/profiles -- it does not import it into Tasker's live configuration.\n\n"
                    "The 'Http Server Example' Tasker Project must be installed and active on the Android "
                    "device, with the server running (see the README's Direct XML Retrieval notes).\n\n"
                    "The Android device must be on the same network, and the IP Address and Port must "
                    "match its Tasker server settings. No authorization prompt is needed for this.",
                ).style("white-space: pre-line")
            ui.button(
                "Export Profile",
                on_click=lambda: self.event_handlers.save_edited_profile_event(edited_profile, field_refs, dialog),
            ).classes("bg-blue-600")

    dialog.open()


def build_save_profile_to_android_dialog(
    self: MyGui,
    edited_profile: profedit.EditableProfile,
    field_refs: dict,
    parent_dialog: ui.dialog,
) -> None:
    """Prompts for the Android device's IP address and port, then writes the
    current Profile (name as it stands in the parent dialog's fields) as a
    standalone .prf.xml file onto the device's storage under /Tasker/profiles,
    via the Tasker HTTP Server Example's /upload endpoint -- see
    profedit.save_profile_to_android. This does not import it into Tasker's
    live configuration. On success both this prompt and the parent (Edit/Add
    Profile) dialog are closed.
    """
    default_ip = getattr(self, "android_ipaddr", "") or "192.168.0.210"
    default_port = getattr(self, "android_port", "") or "1821"

    with ui.dialog() as android_dialog, ui.card().classes("min-w-[350px] p-6"):
        ui.label("Save Profile To Android Device").classes("text-lg font-bold text-blue-600")
        android_field_refs = {
            "ip_address": ui.input("Android IP Address", value=default_ip).classes("w-full"),
            "ip_port": ui.input("Port", value=default_port).classes("w-full"),
        }
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button("Cancel", on_click=android_dialog.close).props("outline")
            save_to_android = ui.button(
                "Save",
                on_click=lambda: self.event_handlers.save_profile_to_android_event(
                    edited_profile,
                    field_refs,
                    android_field_refs,
                    android_dialog,
                    parent_dialog,
                ),
            ).classes("bg-blue-600")
            with save_to_android:
                ui.tooltip(
                    "This will write the Profile as a standalone file onto the Android device, "
                    "under /Tasker/profiles.\n\n"
                    "The IP Address and Port must match the Android device's Tasker server settings.\n\n"
                    "No authorization prompt is needed for this.",
                ).style("white-space: pre-line")

    android_dialog.open()


def build_add_project_dialog(self: MyGui, edited_project: projedit.EditableProject) -> None:
    """Builds and opens the Add Project dialog: create a brand-new Project with
    just a name -- unlike Add Profile/Add Task, there's no parent to attach to
    (a Project is the top of the hierarchy) and no Save/Save To Android surface,
    since a brand-new Project has no Profiles/Tasks attached to it yet -- both
    Save actions export a Project's *existing* <pids>/<tids> contents (see
    projedit.py's module docstring), so there is nothing to export until it's
    been created and has something attached (see build_edit_project_dialog).
    """
    field_refs: dict = {}

    with ui.dialog() as dialog, ui.card().classes("min-w-[400px] max-w-[600px] w-full p-6"):
        ui.label("Add Project").classes("text-xl font-bold text-blue-600")

        field_refs["name"] = ui.input("Project Name", value="").classes("w-full")

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button("Cancel", on_click=dialog.close).props("outline")
            ui.button(
                "Ok",
                on_click=lambda: self.event_handlers.keep_new_project_event(edited_project, field_refs, dialog),
            ).classes("bg-blue-600")

    dialog.open()


def build_edit_project_dialog(self: MyGui, edited_project: projedit.EditableProject) -> None:
    """Builds and opens the Edit Project dialog: Rename the Project, delete it
    -- with a choice of what happens to the Profiles/Tasks it owns, see
    build_delete_project_dialog -- or save it, and everything it owns, as one
    standalone .prj.xml file, either locally (projedit.write_standalone_project_xml)
    or onto the Android device under /Tasker/projects (projedit.save_project_to_android,
    see build_save_project_to_android_dialog). Unlike Add Project, there IS content to
    save here -- an already-registered Project has whatever Profiles/Tasks are attached
    to it, which is exactly why Add Project has no equivalent button (see its docstring).
    """
    project_name = edited_project.project_name
    field_refs: dict = {}

    with ui.dialog() as dialog, ui.card().classes("min-w-[400px] max-w-[600px] w-full p-6"):
        ui.label(f"Edit Project: {project_name}").classes("text-xl font-bold text-blue-600")

        field_refs["name"] = ui.input("Project Name", value=project_name).classes("w-full")

        field_refs["project_save_path"] = ui.input(
            "Save as",
            value=projedit.default_project_save_path(project_name),
        ).classes("w-full mt-2")

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button("Cancel", on_click=dialog.close).props("outline")
            ui.button(
                "Delete Project",
                on_click=lambda: self.event_handlers.delete_project_event(edited_project, dialog),
            ).classes("bg-red-500 text-white")
            ui.button(
                "Rename",
                on_click=lambda: self.event_handlers.rename_project_event(edited_project, field_refs, dialog),
            ).classes("bg-blue-600")
            ui.button(
                "Save To Current File",
                on_click=lambda: self.event_handlers.save_project_to_current_file_event(
                    edited_project,
                    field_refs,
                    dialog,
                ),
            ).props("outline")
            project_to_android = ui.button(
                "Save To Android",
                on_click=lambda: self.event_handlers.open_save_project_to_android_dialog_event(
                    edited_project,
                    dialog,
                ),
            ).props("outline")
            with project_to_android:
                ui.tooltip(
                    "This will write the Project, and everything in it -- every Profile and Task -- as a "
                    "standalone file onto your Android device, under /Tasker/projects -- it does not import "
                    "it into Tasker's live configuration.\n\n"
                    "The 'Http Server Example' Tasker Project must be installed and active on the Android "
                    "device, with the server running.\n\n"
                    "The Android device must be on the same network, and the IP Address and Port must "
                    "match its Tasker server settings. No authorization prompt is needed for this.",
                ).style("white-space: pre-line")
            save_single_project = ui.button(
                "Export Project",
                on_click=lambda: self.event_handlers.save_project_event(edited_project, field_refs, dialog),
            ).classes("bg-blue-600")
            with save_single_project:
                ui.tooltip(
                    "Saves this Project, and everything in it -- every Profile and Task -- as one standalone file.",
                )

    dialog.open()


def build_save_project_to_android_dialog(
    self: MyGui,
    edited_project: projedit.EditableProject,
    parent_dialog: ui.dialog,
) -> None:
    """Prompts for the Android device's IP address and port, then writes the
    Project -- under its current, already-applied name (edited_project.project_name,
    same convention as save_project_event's local export; a not-yet-applied Rename
    edit doesn't carry through) -- as a standalone .prj.xml file onto the device's
    storage under /Tasker/projects, via the Tasker HTTP Server Example's /upload
    endpoint -- see projedit.save_project_to_android. This does not import it into
    Tasker's live configuration. On success both this prompt and the parent (Edit
    Project) dialog are closed.
    """
    default_ip = getattr(self, "android_ipaddr", "") or "192.168.0.210"
    default_port = getattr(self, "android_port", "") or "1821"

    with ui.dialog() as android_dialog, ui.card().classes("min-w-[350px] p-6"):
        ui.label("Save Project To Android Device").classes("text-lg font-bold text-blue-600")
        android_field_refs = {
            "ip_address": ui.input("Android IP Address", value=default_ip).classes("w-full"),
            "ip_port": ui.input("Port", value=default_port).classes("w-full"),
        }
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button("Cancel", on_click=android_dialog.close).props("outline")
            save_to_android = ui.button(
                "Save",
                on_click=lambda: self.event_handlers.save_project_to_android_event(
                    edited_project,
                    android_field_refs,
                    android_dialog,
                    parent_dialog,
                ),
            ).classes("bg-blue-600")
            with save_to_android:
                ui.tooltip(
                    "This will write the Project, and everything in it, as a standalone file onto the "
                    "Android device, under /Tasker/projects.\n\n"
                    "The IP Address and Port must match the Android device's Tasker server settings.\n\n"
                    "No authorization prompt is needed for this.",
                ).style("white-space: pre-line")

    android_dialog.open()


def build_overwrite_confirm_dialog(
    what_exists: str,
    on_confirm: Callable[[], None],
    *,
    unknown: bool = False,
) -> None:
    """Confirms overwriting something that is already there, before anything is
    written. Backs every Save/Export path that would otherwise clobber a file
    silently -- the local standalone exports and the Save To Android uploads
    (see userintr's save_* handlers).

    what_exists describes the thing in the user's terms (a full path); on_confirm
    performs the write and is called only if they choose "Overwrite". Cancel
    closes this dialog and leaves the parent Edit/Add dialog open, so nothing
    in progress is lost -- same convention as build_delete_project_dialog.

    unknown=True switches the wording for the case where existence could not be
    determined at all (maputil2.file_exists_on_android returning None -- device
    unreachable mid-check). That is deliberately still a prompt rather than a
    silent write: the honest statement is "this might overwrite something", and
    the user is the one who knows whether that matters.
    """
    title = "Could not check destination" if unknown else "Already exists"
    body = (
        f"Could not confirm whether {what_exists} already exists. Saving may overwrite it."
        if unknown
        else f"{what_exists} already exists and will be replaced."
    )

    with ui.dialog() as confirm_dialog, ui.card().classes("min-w-[400px] max-w-[600px] w-full p-6"):
        ui.label(title).classes("text-lg font-bold text-orange-600")
        ui.label(body).classes("mt-1 break-all")
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button("Cancel", on_click=confirm_dialog.close).props("outline")

            def _confirm() -> None:
                # Close first: on_confirm may open its own dialog (or close the
                # parent), and leaving this one stacked on top would hide it.
                confirm_dialog.close()
                on_confirm()

            ui.button("Overwrite", on_click=_confirm).classes("bg-orange-600 text-white")

    confirm_dialog.open()


def build_delete_profile_dialog(
    self: MyGui,
    edited_profile: profedit.EditableProfile,
    parent_dialog: ui.dialog,
) -> None:
    """Confirms deletion of a Profile. Unlike build_delete_project_dialog there is
    no Keep/Delete Contents choice -- a Profile doesn't own its Entry/Exit Tasks
    (see profedit.delete_profile), so they are always kept, and the dialog says so
    explicitly rather than leaving the user to guess what "delete" reaches.

    The linked-Task count is read live so it can't go stale between opening Edit
    Profile and clicking Delete, same as build_delete_project_dialog's counts.
    """
    profile_name = edited_profile.profile_element.findtext("nme", "")
    task_count = profedit.count_profile_tasks(profile_name)

    with ui.dialog() as confirm_dialog, ui.card().classes("min-w-[400px] max-w-[600px] w-full p-6"):
        ui.label(f"Delete Profile '{profile_name}'").classes("text-lg font-bold text-red-600")
        if task_count:
            ui.label(
                f"Its {task_count} linked Task(s) will be kept -- they belong to the Project, not to this Profile.",
            ).classes("mt-1")
        else:
            ui.label("It has no linked Tasks.").classes("mt-1")
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button("Cancel", on_click=confirm_dialog.close).props("outline")
            ui.button(
                "Delete Profile",
                on_click=lambda: self.event_handlers.confirm_delete_profile_event(
                    profile_name,
                    confirm_dialog,
                    parent_dialog,
                ),
            ).classes("bg-red-500 text-white")

    confirm_dialog.open()


def build_delete_project_dialog(
    self: MyGui,
    edited_project: projedit.EditableProject,
    parent_dialog: ui.dialog,
) -> None:
    """Confirms deletion of a Project, offering a choice for what happens to
    the Profiles/Tasks it owns: moved into "Base" (Keep Contents) or deleted
    along with it (Delete Contents) -- see projedit.delete_project. Shown
    before anything is mutated; the Profile/Task counts are read live so they
    can't go stale between opening Edit Project and clicking Delete.
    """
    project_name = edited_project.project_name
    profile_count, task_count = projedit.count_project_contents(project_name)

    with ui.dialog() as confirm_dialog, ui.card().classes("min-w-[400px] max-w-[600px] w-full p-6"):
        ui.label(f"Delete Project '{project_name}'").classes("text-lg font-bold text-red-600")
        ui.label(f"It owns {profile_count} Profile(s) and {task_count} Task(s).").classes("mt-1")
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button("Cancel", on_click=confirm_dialog.close).props("outline")
            ui.button(
                "Keep Contents",
                on_click=lambda: self.event_handlers.keep_contents_delete_project_event(
                    project_name,
                    confirm_dialog,
                    parent_dialog,
                ),
            ).props("outline")
            ui.button(
                "Delete Contents",
                on_click=lambda: self.event_handlers.delete_contents_delete_project_event(
                    project_name,
                    confirm_dialog,
                    parent_dialog,
                ),
            ).classes("bg-red-500 text-white")

    confirm_dialog.open()


def build_add_profile_dialog(
    self: MyGui,
    edited_profile: profedit.EditableProfile,
    target_project_name: str = "",
) -> None:
    """Builds and opens the Add Profile dialog: create a new Profile, then the
    exact same Enabled/Disabled toggle, Entry/Exit Task Link/Unlink, and
    per-condition Add/Edit/Delete as Edit Profile (see
    _build_profile_editor_body, shared by both), plus the same Cancel/Ok/Save
    To Android/Save button row -- mirrors build_add_task_dialog's relationship
    to build_edit_task_dialog.

    target_project_name is the single Project the top-level "Add Profile"
    button requires be selected before this dialog opens (see
    userintr.open_add_profile_dialog_event) -- stored in field_refs (not a
    widget; there's nothing here for the user to change) purely so
    _validate_and_apply_new_profile/save_profile_to_android_event can read it
    back and attach the new Profile to that Project (see
    profedit.add_profile_to_project) once it's registered. A Profile only
    shows up in the Project/Profile/Task pulldowns, Map, Diagram, or Tree
    views if some Project's <pids> element lists its id (see
    userintr.build_the_tree/projects.process_project_profiles, both driven by
    getids.get_ids -- not by the all_profiles lookup table register_new_profile
    populates), which is why a Project is required at all.
    """
    field_refs: dict = {"target_project_name": target_project_name}

    with ui.dialog() as dialog, ui.card().classes("min-w-[500px] max-w-[900px] w-full p-6"):
        ui.label("Add Profile").classes("text-xl font-bold text-blue-600")

        last_auto_path = {"value": profedit.default_save_path("")}

        def sync_save_path(_e: object = None) -> None:
            # Keep "Save as" in sync with the Profile Name as the user types --
            # see build_add_task_dialog's identical sync_save_path for why this
            # only overwrites the path while it still holds what was last auto-computed.
            if field_refs["save_path"].value == last_auto_path["value"]:
                new_path = profedit.default_save_path(field_refs["name"].value)
                field_refs["save_path"].value = new_path
                last_auto_path["value"] = new_path

        if target_project_name:
            ui.label(f"Adding to Project: {target_project_name}").classes("text-sm text-gray-500 italic")

        field_refs["name"] = ui.input("Profile Name", value="", on_change=sync_save_path).classes("w-full")

        _build_profile_editor_body(self, edited_profile, field_refs)

        field_refs["save_path"] = ui.input(
            "Save as",
            value=last_auto_path["value"],
        ).classes("w-full mt-2")

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button("Cancel", on_click=dialog.close).props("outline")
            ui.button(
                "Ok",
                on_click=lambda: self.event_handlers.keep_new_profile_event(edited_profile, field_refs, dialog),
            ).props("outline")
            ui.button(
                "Save To Current File",
                on_click=lambda: self.event_handlers.save_new_profile_to_current_file_event(
                    edited_profile,
                    field_refs,
                    dialog,
                ),
            ).props("outline")
            profile_to_android = ui.button(
                "Save To Android",
                on_click=lambda: self.event_handlers.open_save_profile_to_android_dialog_event(
                    edited_profile,
                    field_refs,
                    dialog,
                ),
            ).props("outline")
            with profile_to_android:
                ui.tooltip(
                    "This will write the Profile as a standalone file onto your Android device, "
                    "under /Tasker/profiles -- it does not import it into Tasker's live configuration.\n\n"
                    "The 'Http Server Example' Tasker Project must be installed and active on the Android "
                    "device, with the server running (see the README's Direct XML Retrieval notes).\n\n"
                    "The Android device must be on the same network, and the IP Address and Port must "
                    "match its Tasker server settings. No authorization prompt is needed for this.",
                ).style("white-space: pre-line")
            ui.button(
                "Export Profile",
                on_click=lambda: self.event_handlers.save_new_profile_event(edited_profile, field_refs, dialog),
            ).classes("bg-blue-600")

    dialog.open()


def build_add_task_dialog(
    self: MyGui,
    edited_task: taskedit.EditableTask,
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
    userintr.open_add_task_dialog_event) -- stored in field_refs (not a widget;
    there's nothing here for the user to change) purely so _finish_new_task can
    read it back and add the new Task's id to that Project's <tids> once it's
    registered. Left "" for open_add_task_for_profile_link_event's nested
    dialog, which doesn't attach to a Project at all.
    """
    field_refs: dict = {"target_project_name": target_project_name}
    category_names = sorted({row["category_name"] for row in taskedit.list_addable_actions()})
    # Same out-of-band Position-label -> act_number map as build_edit_task_dialog's.
    position_labels: dict[str, int | None] = {}
    # Same per-action If condition value cache as build_edit_task_dialog's.
    condition_cache: dict[int, tuple[str, str, str]] = {}

    with ui.dialog() as dialog, ui.card().classes("min-w-[500px] max-w-[900px] w-full p-6"):
        ui.label("Add Task").classes("text-xl font-bold text-blue-600")

        last_auto_path = {"value": taskedit.default_save_path("")}

        def sync_save_path(_e=None) -> None:
            # Keep "Save as" in sync with the Task Name as the user types, so the
            # file actually lands under the name they gave the task -- but only
            # while it still holds what we last auto-computed; if the user has
            # since edited it manually, leave their edit alone. (Can't tell "manual
            # edit" apart via save_path's own on_change: NiceGUI fires that for
            # programmatic value sets too, so it would trip on the very first sync.)
            if field_refs["save_path"].value == last_auto_path["value"]:
                new_path = taskedit.default_save_path(field_refs["name"].value)
                field_refs["save_path"].value = new_path
                last_auto_path["value"] = new_path

        if target_project_name:
            ui.label(f"Adding to Project: {target_project_name}").classes("text-sm text-gray-500 italic")

        with ui.row().classes("w-full gap-4"):
            field_refs["name"] = ui.input("Task Name", value="", on_change=sync_save_path).classes("flex-1")
            field_refs["priority"] = ui.input("Priority", value="100").classes("w-32")

        ui.label("Add an action").classes("text-sm font-bold mt-2")
        with ui.row().classes("w-full gap-4"):
            search_input = ui.input("Search actions").classes("flex-1")
            category_select = ui.select(["All", *category_names], value="All").classes("w-48")
        position_select = ui.select([], label="Position", with_input=True).classes("w-full").props("dense")

        picker_container = ui.column().classes("w-full")
        ui.label("Actions in this Task").classes("text-sm font-bold mt-2")
        added_container = ui.column().classes("w-full")
        # act_number of the action most recently added in this dialog session --
        # render_added_actions highlights it so it's easy to spot in a long list.
        last_added_act_number: int | None = None

        def clear_last_added() -> None:
            # Remove renumbers the list, so a stale act_number here would risk
            # highlighting the wrong action -- drop the highlight instead of
            # letting it follow whatever action inherits the number.
            nonlocal last_added_act_number
            last_added_act_number = None

        def refresh_position_options() -> None:
            _refresh_position_options(edited_task, position_select, position_labels)

        def render_added_actions() -> None:
            # Rebuild from scratch -- a Remove renumbers every action after it, so
            # stale act*_arg* keys must not survive into the next Save.
            for key in [k for k in field_refs if k.startswith("act")]:
                del field_refs[key]
            added_container.clear()
            with added_container:
                if not edited_task.actions:
                    ui.label("No actions added yet.").classes("text-xs text-gray-500 italic")
                indent_spaces = _action_indent_spaces(self)
                display_levels = taskedit.action_display_levels(edited_task.actions)
                for action, nest_level in zip(edited_task.actions, display_levels, strict=True):
                    # Indent with non-breaking spaces -- plain ones collapse in the rendered header.
                    indent_pad = "\u00a0" * (indent_spaces * nest_level)
                    is_last_added = action.act_number == last_added_act_number
                    header = f"{indent_pad}{action.act_number}: {action.action_name}"
                    if is_last_added:
                        header += "  \u2190 just added"
                    action_expansion = ui.expansion(header, value=is_last_added).classes("w-full")
                    if is_last_added:
                        action_expansion.classes("bg-amber-100 dark:bg-amber-900 border-2 border-amber-400 rounded")
                    with action_expansion:
                        field_refs[taskedit.label_key(action.act_number)] = ui.input(
                            "Label",
                            value=taskedit.get_action_label(action),
                        ).classes("w-full")
                        if action.code != taskedit.IF_ACTION_CODE:
                            _render_action_condition_checkbox(self, edited_task, action, condition_cache)
                        _render_continue_after_error_checkbox(self, edited_task, action)
                        for arg in action.args:
                            key = taskedit.arg_key(action.act_number, arg.arg_id)
                            with ui.row().classes("w-full items-center gap-2"):
                                if arg.widget_kind == "checkbox":
                                    field_refs[key] = ui.checkbox(arg.arg_name, value=arg.current_value == "1")
                                elif arg.widget_kind == "dropdown":
                                    options = arg.dropdown_options or []
                                    field_refs[key] = ui.select(
                                        options,
                                        value=_dropdown_current_label(arg),
                                        label=arg.arg_name,
                                    ).classes("flex-1")
                                elif taskedit.is_perform_task_name_arg(action.code, arg):
                                    _render_task_name_field(self, action, arg, key, field_refs)
                                else:  # "text" or "raw_fallback"
                                    field_refs[key] = ui.input(arg.arg_name, value=arg.current_value).classes("flex-1")
                        ui.button(
                            "Remove",
                            on_click=lambda n=action.act_number: (
                                clear_last_added(),
                                self.event_handlers.remove_action_from_new_task_event(edited_task, n),
                                render_added_actions(),
                                refresh_position_options(),
                            ),
                        ).props("flat color=red dense")

        def add_picked_action(action_key: str) -> None:
            nonlocal last_added_act_number
            # Same "If" block prompt and Position handling as
            # build_edit_task_dialog's picker.
            if action_key == taskedit.IF_ACTION_KEY:

                def _add_if_block(variant: str) -> None:
                    nonlocal last_added_act_number
                    act_number = self.event_handlers.add_if_block_to_new_task_event(
                        edited_task,
                        variant,
                        position_labels.get(position_select.value),
                    )
                    if act_number is not None:
                        last_added_act_number = act_number
                    render_added_actions()
                    refresh_position_options()

                build_if_variant_dialog(_add_if_block)
                return
            act_number = self.event_handlers.add_action_to_new_task_event(
                edited_task,
                action_key,
                position_labels.get(position_select.value),
            )
            if act_number is not None:
                last_added_act_number = act_number
            render_added_actions()
            refresh_position_options()

        def refresh_picker(_e=None) -> None:
            picker_container.clear()
            rows = taskedit.search_addable_actions(search_input.value, category_select.value)
            with picker_container, ui.scroll_area().classes("w-full h-40 border rounded p-2"):
                for row in rows:
                    if row["addable"]:
                        ui.button(
                            f"{row['name']} ({row['category_name']})",
                            on_click=lambda r=row: add_picked_action(r["action_key"]),
                        ).props("flat align=left dense").classes("w-full justify-start")
                    else:
                        with ui.column().classes("w-full gap-0"):
                            ui.label(f"{row['name']} ({row['category_name']})").classes("text-gray-400")
                            ui.label(row["reason"]).classes("text-xs text-gray-500 italic")

        search_input.on_value_change(refresh_picker)
        category_select.on_value_change(refresh_picker)
        refresh_picker()
        refresh_position_options()
        render_added_actions()

        field_refs["save_path"] = ui.input(
            "Save as",
            value=last_auto_path["value"],
        ).classes("w-full mt-2")

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button("Cancel", on_click=dialog.close).props("outline")
            ui.button(
                "Ok",
                on_click=lambda: self.event_handlers.keep_new_task_event(
                    edited_task,
                    field_refs,
                    dialog,
                    on_created=on_task_created,
                ),
            ).props("outline")
            ui.button(
                "Save To Current File",
                on_click=lambda: self.event_handlers.save_new_task_to_current_file_event(
                    edited_task,
                    field_refs,
                    dialog,
                    on_created=on_task_created,
                ),
            ).props("outline")
            ui.button(
                "Save To Android",
                on_click=lambda: self.event_handlers.open_save_to_android_dialog_event(
                    edited_task,
                    field_refs,
                    dialog,
                    on_created=on_task_created,
                ),
            ).props("outline")
            ui.button(
                "Export Task",
                on_click=lambda: self.event_handlers.save_new_task_event(
                    edited_task,
                    field_refs,
                    dialog,
                    on_created=on_task_created,
                ),
            ).classes("bg-blue-600")

    dialog.open()


# ==========================================
# 3. VIEWS (Tree and Text)
# ==========================================
# Pre-compile the regex pattern at the module level for maximum execution performance.
# This scans the HTML string and hits all target replacements in a single pass O(N).
HTML_OPTIMIZE_PATTERN = re.compile(
    r"(\n\n\n|\n\n|<br>\n<br><br>|\n<br><br>|<br>\n|<br><br>|<br></span>|\n<br>|<h2>MapTasker</h2>|<h2><span class=\"normtab\"></span>Directory</h2>)",
)

# Map the targeted string matches directly to their optimized counterparts.
HTML_REPLACEMENT_MAP = {
    "\n\n\n": "",
    "\n\n": "",
    "<br>\n<br><br>": "",
    "\n<br><br>": "<br>",
    "<br>\n": "<br>",
    "<br><br>": "<br>",
    "<br></span>": "</span>",
    "\n<br>": "<br>",
    "<h2>MapTasker</h2>": '<a id="the_top"></a><h5>MapTasker</h5>',
    '<h2><span class="normtab"></span>Directory</h2>': '<h6><span class="normtab"></span>Directory</h6>',
}


def _escape_html_text(text: str) -> str:
    """Escape plain text for safe embedding in HTML (the Diagram file has no markup of its own)."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _connectors_by_line() -> dict[int, list[tuple[int, int, int]]]:
    """Invert PrimeItems.diagram_connectors (id -> ranges) into line_num -> (start, end, id)."""
    by_line: dict[int, list[tuple[int, int, int]]] = {}
    for connector_id, ranges in getattr(PrimeItems, "diagram_connectors", {}).items():
        for line_num, col_start, col_end in ranges:
            by_line.setdefault(line_num, []).append((col_start, col_end, connector_id))
    return by_line


def _wrap_diagram_line(
    line_num: int,
    line: str,
    connectors_by_line: dict[int, list[tuple[int, int, int]]],
) -> str:
    """Escape a Diagram line for HTML, wrapping each connector's characters in a clickable span."""
    ranges = connectors_by_line.get(line_num)
    if not ranges:
        return _escape_html_text(line)

    pieces = []
    cursor = 0
    for col_start, col_end, connector_id in sorted(ranges):
        col_start = max(col_start, cursor)  # noqa: PLW2901
        if col_start >= col_end or col_start >= len(line):
            continue
        col_end = min(col_end, len(line))  # noqa: PLW2901
        if col_start > cursor:
            pieces.append(_escape_html_text(line[cursor:col_start]))
        pieces.append(
            f'<span class="connector" data-connector-id="{connector_id}">'
            f"{_escape_html_text(line[col_start:col_end])}</span>",
        )
        cursor = col_end
    if cursor < len(line):
        pieces.append(_escape_html_text(line[cursor:]))
    return "".join(pieces)


class NiceGuiTreeView:
    """Replaces CTkTreeview. Renders a hierarchical tree representation in the main view column."""

    def __init__(self, master_gui: MyGui, title: str, items: list) -> None:
        """Initialize the Tree view with a title and hierarchical items."""
        self.master_gui = master_gui
        self.title = title
        self.build_ui(items)

    def build_ui(self, items: list) -> None:
        """Build the base UI layout for the Tree view inside the main content container slot."""

        # 1. Target and clear the dedicated full-width main view column slot
        if hasattr(self.master_gui, "content_container") and self.master_gui.content_container:
            self.master_gui.content_container.clear()
            container_context = self.master_gui.content_container
        else:
            container_context = ui.column()  # Fallback context if called standalone

        # 2. Render the layout inside the main application body container
        with container_context:  # noqa: SIM117
            with ui.card().classes("w-full max-w-full mx-auto p-6 shadow-md border-2 border-gray-300"):
                # Header row with title and navigation hints
                with ui.row().classes("items-center justify-between w-full border-b pb-3 mb-4"):
                    ui.label(f"{self.title}").classes("text-orange-500 font-bold text-lg")
                    ui.label("Click arrows to expand/collapse details.").classes("text-xs text-gray-500 italic")

                # Convert MapTasker nested dictionary list nodes to NiceGUI tree notation
                tree_data = self._format_data(items)

                # 3. Create a scrollable window container for large tree structures
                with ui.scroll_area().classes("w-full h-[65vh] p-2"):
                    # Render the native responsive Tree component
                    # Injected custom fonts to preserve monospace formatting matches
                    self.tree = (
                        ui
                        .tree(tree_data, label_key="label", children_key="children", tick_strategy="none")
                        .classes("w-full text-base")
                        .style(f"font-family: '{self.master_gui.font}', monospace;")
                    )

    def _format_data(self, items: list, parent_id: str = "node") -> list:
        """Converts MapTasker lists/dicts into NiceGUI's strict dict format,

        replacing HTML non-breaking spaces (&nbsp;) with standard spaces
        and cleaning raw arrow entities (&#11013;) into clear symbols.
        """
        formatted_nodes = []
        for i, item in enumerate(items):
            current_id = f"{parent_id}_{i}"
            if isinstance(item, dict):
                # Extract the name and clean out the raw HTML markup fragments
                raw_name = item.get("name", "Unnamed")
                clean_name = (
                    raw_name
                    .replace("&nbsp;", " ")
                    .replace("&#9940;", "⛔")
                    .replace("&#11013;", "⬅️")
                    .replace("&#11157;", "➡️")
                    .ljust(50)
                )

                node = {"id": current_id, "label": clean_name}
                if item.get("children"):
                    node["children"] = self._format_data(item["children"], current_id)
                formatted_nodes.append(node)
            else:
                # Handle raw string line items (like nested Task Actions or standalone strings)
                clean_string = (
                    str(item)
                    .replace("&nbsp;", " ")
                    .replace("&#9940;", "⛔")
                    .replace("&#11013;", "⬅️")
                    .replace("&#11157;", "➡️")
                )
                formatted_nodes.append({"id": current_id, "label": clean_string})
        return formatted_nodes


class NiceGuiTextView:
    """Replaces CTkTextview. Handles rendering MapTasker data using HTML."""

    def __init__(
        self,
        master_gui: MyGui,
        title: str,
        the_data: list | dict,
        container: ui.column | None = None,
    ) -> None:
        """Initialize the NiceGuiTextView.

        If `container` is given, the view is built inside it directly instead of the
        master GUI's main content_container -- used to render into a separate popped-out
        browser window/tab without disturbing the main window's layout.
        """
        self.master_gui = master_gui
        self.title = title
        self.is_map = isinstance(the_data, dict)
        self.external_container = container
        self.build_ui()
        # Schedule the coroutine into the active event loop safely
        self._task = asyncio.create_task(self.process_data(the_data))

    def build_ui(self) -> None:
        """Builds the UI layout for the various text views, including toolbar and scrollable display area."""

        # A popped-out view (its own browser window/tab, see rungui.py's "/popout/{view_type}"
        # page) has the whole viewport to itself, so its scroll area flex-fills the remaining
        # height after the toolbar instead of the fixed 70vh used when embedded alongside the
        # rest of the main window's layout.
        is_popout = self.external_container is not None

        if is_popout:
            container_context = self.external_container
            container_context.classes("w-full h-screen flex flex-col p-0 m-0 gap-0")
        elif hasattr(self.master_gui, "content_container") and self.master_gui.content_container:
            self.master_gui.content_container.clear()
            container_context = self.master_gui.content_container
        else:
            container_context = ui.column()

        # "Diagram" view intentionally starts unwrapped so ASCII-art connectors stay aligned.
        is_diagram = self.title.startswith("Diagram")

        # Set the main container to a vertical layout with full width and height
        with container_context:
            # Toolbar
            with ui.row().classes("w-full items-center gap-2 p-2 mb-2 shrink-0") as self.gui_toolbar:
                ui.label(f"{self.title}").classes("text-orange-500 font-bold mr-4")
                self.search_input = ui.input(placeholder="Search...").classes("w-48")
                search_button = ui.button("Search", on_click=self.search_event).classes("bg-blue-600")
                with search_button:
                    ui.tooltip(
                        "The 'Search' button will search for and highlight every instance of the case-insensitive string entered in the search box, starting at the top of the data.\n\n"
                        "It will only show the first 200 instances of the search string.\n\n"
                        "Click on the line number to go to that line in the text view box.\n\n"
                        "The 'Clear' button will clear the search results.\n\n",
                    ).style("white-space: pre-line")
                ui.button("Clear", on_click=self.master_gui.event_handlers.clear_event).classes(
                    "bg-blue-600",
                )
                ui.separator().props("vertical")
                ui.button("Top", on_click=lambda: self.scroll("top")).classes("bg-blue-600")
                ui.button("Bottom", on_click=lambda: self.scroll("bottom")).classes("bg-blue-600")
                ui.button("Toggle Wrap", on_click=self.toggle_wrap).classes("bg-blue-600")
                if self.is_map:
                    self.map_message_label = ui.label(PrimeItems.view_limit_msg).classes("text-orange-400 italic ml-4")
                if is_diagram:
                    ui.separator().props("vertical")
                    ui.select(
                        options=[str(n) for n in range(11)],
                        value=str(self.master_gui.profiles_per_line),
                        label="Profiles Per Line",
                        on_change=self._profiles_per_line_selected,
                    ).classes("w-40").props("dense")
                    self.diagram_message_label = ui.label("").classes("text-orange-400 italic ml-4")

            self.wrap_enabled = "Diagram" not in self.title
            self.wrap_classes = "whitespace-pre-wrap break-words" if self.wrap_enabled else "whitespace-pre"

            # min-h-0 lets this flex item shrink below its content's intrinsic size -- without it
            # a flex column's default min-height:auto would keep growing the scroll area (and the
            # page) to fit all the streamed-in content instead of scrolling internally.
            scroll_height_classes = "flex-1 min-h-0" if is_popout else "h-[70vh]"

            # Tailwind's text-sm utility (below) pairs a 14px font with a 20px line-height --
            # comfortable for prose, but visibly loose for a dense box-drawn diagram. Tighten it
            # for the Diagram view only; keep process_data()'s approx_px_per_line chunk-height
            # estimate in sync with this so scrolling doesn't jump around as chunks pop in.
            line_height_style = " line-height: 1.2;" if is_diagram else ""

            self.scroll_area = (
                ui
                .scroll_area()
                # min-w-0 keeps this a flex child that can't be stretched wider than its container by
                # long unbreakable content; without it the default flex min-width:auto lets the box
                # (and the whole page) grow past the viewport once the full content has streamed in.
                .classes(
                    f"w-full max-w-full min-w-0 block {scroll_height_classes} "
                    f"border-2 border-gray-600 p-4 text-sm {self.wrap_classes}",
                )
                .style(
                    f"width: 100%; max-width: 100%; font-family: '{self.master_gui.font}', monospace;"
                    f"{line_height_style}",
                )
            )

    async def process_data(self, the_data: dict | list) -> None:
        """Converts data to HTML chunks, preventing single-packet WebSocket buffer overruns.

        All ui.html() calls below pass sanitize=False: the content is this program's own
        MapTasker.html/diagram output, not untrusted input. NiceGUI's default client-side
        sanitizer (the browser's Sanitizer API) strips "id", "class", and "data-*" attributes,
        which silently breaks in-page #fragment hyperlinks (e.g. the "Task ... has too many
        actions" links) and the Diagram view's click-to-highlight connectors -- their <a href>
        source tags survive sanitizing, but the <a id="..."> targets and .connector/
        data-connector-id spans they depend on do not.
        """
        is_diagram = self.title.startswith("Diagram")
        html_style = f"width: 100%; max-width: 100%; font-family: '{self.master_gui.font}', monospace;"
        if "Diagram" not in self.title:
            html_style += " word-break: break-word;"

        if self.title.startswith("Map"):
            file_to_read = os.path.join(os.getcwd(), "MapTasker.html")
        elif is_diagram:
            file_to_read = os.path.join(os.getcwd(), DIAGRAM_FILE)
        elif self.title.startswith("Misc"):
            with self.scroll_area:
                content_str = "\n".join(str(line) for line in the_data) if isinstance(the_data, list) else str(the_data)
                ui.html(f"<pre style='{html_style}'>{content_str}</pre>", sanitize=False)
            return

        try:
            with open(file_to_read, encoding="utf-8") as f:
                final_html = f.read()
                # The diagram file is plain text (no HTML markup), and its line numbers must line
                # up 1:1 with PrimeItems.diagram_connectors (recorded when the diagram was built) so
                # clicking a connector highlights the right one -- so skip the HTML-specific/blank-line
                # collapsing optimizations here; they aren't meaningful for plain text anyway.
                if not is_diagram:
                    final_html = HTML_OPTIMIZE_PATTERN.sub(
                        lambda match: HTML_REPLACEMENT_MAP[match.group(0)],
                        final_html,
                    )

            extracted_font = self.extract_first_font_name(final_html)
            if extracted_font not in ("Font name not found", self.master_gui.font):
                final_html = final_html.replace(f"font-family:{extracted_font}", f"font-family:{self.master_gui.font}")

            # --- STREAMING CHUNK ENGINE ---
            # Slice the giant HTML text by lines and push them in digestible blocks
            html_lines = final_html.splitlines()
            if html_lines and html_lines[0].strip() == '<span class="normtab"></span><!doctype html>':
                del html_lines[0]  # Remove the first line if it matches the unwanted header

            connectors_by_line = _connectors_by_line() if is_diagram else None

            # The Diagram view's click-to-highlight feature wraps every connector character in its
            # own <span> (tens of thousands of them on a large diagram, since a run only merges
            # with its neighbor when they're on the very same line -- see
            # compute_diagram_connector_groups() in diagram.py). That many extra inline elements
            # makes the browser's layout/paint work on scroll noticeably heavier, so the Diagram
            # view is chunked much more finely than other views. Every view's chunks are marked
            # content-visibility: auto though, which lets the browser skip layout and paint
            # entirely for chunks that are scrolled out of view instead of doing that work for the
            # whole document on every frame -- on a very large Map view that's the difference
            # between laying out the whole document up front and only what's on screen.
            # contain-intrinsic-size reserves roughly the right amount of scrollbar space for an
            # unrendered chunk so scrolling doesn't jump around as chunks pop in and out; it
            # doesn't need to be exact, just close. For the Map/Misc views this estimate is fuzzier
            # than for Diagram's plain monospace text, since long lines there can word-wrap
            # (word-break: break-word, set above) into more than one visual line -- a minor
            # scrollbar jitter, not a correctness issue.
            chunk_size = 150 if is_diagram else 2000
            # text-sm is 14px; at the Diagram view's tightened line-height (1.2, set in build_ui)
            # that's ~17px per line instead of Tailwind's default ~20px.
            approx_px_per_line = 17 if is_diagram else 20

            with self.scroll_area:
                for i in range(0, len(html_lines), chunk_size):
                    chunk_lines = html_lines[i : i + chunk_size]
                    if connectors_by_line is not None:
                        chunk_content = "\n".join(
                            _wrap_diagram_line(i + offset, line, connectors_by_line)
                            for offset, line in enumerate(chunk_lines)
                        )
                    else:
                        chunk_content = "\n".join(chunk_lines)
                    chunk_height = len(chunk_lines) * approx_px_per_line
                    chunk_style = (
                        html_style + f" content-visibility: auto; contain-intrinsic-size: auto {chunk_height}px;"
                    )
                    ui.html(chunk_content, sanitize=False).classes("w-full block max-w-full").style(chunk_style)
                    await asyncio.sleep(0.01)  # Yields loop to keep WebSocket alive

            if connectors_by_line:
                self._enable_connector_highlighting()
                if hasattr(self, "diagram_message_label"):
                    self.diagram_message_label.set_text("Click on connector to highlight")
            return  # noqa: TRY300

        except FileNotFoundError:
            pass

        # Apply the fallback generation if the file does not exist
        self._process_fallback_data(the_data)

    def _enable_connector_highlighting(self) -> None:
        """Wires up click-to-highlight for Diagram view connector spans.

        Clicking a connector span highlights every span sharing its data-connector-id and clears
        any previously-highlighted connector; clicking empty space clears the highlight too. If
        either end of the highlighted connector -- its topmost or bottommost cell, since a
        connector's spans are emitted top-to-bottom in document order -- is scrolled out of the
        visible area, a floating "Jump to Start"/"Jump to End" button appears so the user can
        bring it into view without hunting for it manually; the button hides itself again once
        the user scrolls that end into view (or clicks away).
        """
        # ui.run_javascript() needs an active NiceGUI "slot" to know which client to target.
        # This runs from a background asyncio task (self._task), after the `with self.scroll_area:`
        # block used to stream in the chunks has already closed, so the slot stack is empty here --
        # calling it unguarded raises RuntimeError (silently, since self._task is fire-and-forget)
        # and the click handler never reaches the browser. Re-entering the scroll_area as a context
        # manager restores the slot so the script actually gets sent.
        with self.scroll_area:
            ui.run_javascript(f"""
                const outerContainer = document.getElementById("c{self.scroll_area.id}");
                if (!outerContainer || outerContainer.dataset.connectorClickWired) return;
                outerContainer.dataset.connectorClickWired = "1";

                // Quasar's own q-scroll-area styling sets "contain: strict" on outerContainer,
                // which creates a new containing block for position:fixed descendants -- a button
                // appended inside it would be clipped to and positioned relative to the scroll
                // area's box instead of the viewport. Appending to document.body avoids that, at
                // the cost of needing to clean up by hand: remove any leftover buttons from a
                // previous Diagram view load first (clear()-ing the view's container doesn't touch
                // elements parented directly under body).
                document.querySelectorAll(".connector-jump-button").forEach((el) => el.remove());

                function makeJumpButton(label, bottomOffset) {{
                    const btn = document.createElement("button");
                    btn.textContent = label;
                    btn.className = "connector-jump-button";
                    btn.style.bottom = bottomOffset + "px";
                    btn.addEventListener("click", (event) => {{
                        event.stopPropagation();
                        const target = btn._jumpTarget;
                        if (target) {{
                            // A chunk currently skipped by content-visibility: auto (see
                            // process_data()'s chunking) never got laid out, so its descendants'
                            // getBoundingClientRect() is meaningless and scrollIntoView() would
                            // land in the wrong place. Force that chunk to lay out for real first
                            // -- it's the one we're about to scroll to anyway, so there's no
                            // wasted work, and leaving it visible afterward is harmless.
                            for (let a = target; a; a = a.parentElement) {{
                                if (getComputedStyle(a).contentVisibility === "auto") {{
                                    a.style.contentVisibility = "visible";
                                }}
                            }}
                            // Instant, not smooth: the jump can cover tens of thousands of pixels
                            // on a large diagram, where an animated scroll would be slow to land
                            // and distracting rather than helpful.
                            target.scrollIntoView({{block: "center", inline: "center", behavior: "auto"}});
                            // Don't wait for the resulting "scroll" event to re-check visibility --
                            // it fires asynchronously, and updateJumpButtons is hoisted so it's
                            // already safe to call here even though it's defined further down.
                            updateJumpButtons();
                        }}
                    }});
                    document.body.appendChild(btn);
                    return btn;
                }}
                const jumpEndBtn = makeJumpButton("Jump to End", 16);
                const jumpStartBtn = makeJumpButton("Jump to Start", 60);

                function isElementVisible(el, container) {{
                    // A connector's horizontal run can be wider than the whole viewport, in which
                    // case requiring it to fit entirely inside the container can never be
                    // satisfied even right after successfully jumping to it. Its midpoint landing
                    // inside the container is a better proxy for "the jump got you there".
                    const er = el.getBoundingClientRect();
                    const cr = container.getBoundingClientRect();
                    const midX = er.left + er.width / 2;
                    const midY = er.top + er.height / 2;
                    return midX >= cr.left && midX <= cr.right && midY >= cr.top && midY <= cr.bottom;
                }}

                function positionJumpButtons() {{
                    const rect = outerContainer.getBoundingClientRect();
                    const viewportWidth = document.documentElement.clientWidth;
                    const rightPx = Math.max(8, viewportWidth - rect.right + 16);
                    jumpEndBtn.style.right = rightPx + "px";
                    jumpStartBtn.style.right = rightPx + "px";
                }}
                positionJumpButtons();
                window.addEventListener("resize", positionJumpButtons);

                function updateJumpButtons() {{
                    if (jumpEndBtn._jumpTarget && document.body.contains(jumpEndBtn._jumpTarget)
                        && !isElementVisible(jumpEndBtn._jumpTarget, outerContainer)) {{
                        jumpEndBtn.style.display = "block";
                    }} else {{
                        jumpEndBtn.style.display = "none";
                    }}
                    if (jumpStartBtn._jumpTarget && document.body.contains(jumpStartBtn._jumpTarget)
                        && !isElementVisible(jumpStartBtn._jumpTarget, outerContainer)) {{
                        jumpStartBtn.style.display = "block";
                    }} else {{
                        jumpStartBtn.style.display = "none";
                    }}
                }}

                const scroller = outerContainer.querySelector(".q-scrollarea__container") || outerContainer;
                scroller.addEventListener("scroll", updateJumpButtons);

                outerContainer.addEventListener("click", (event) => {{
                    const target = event.target.closest(".connector");
                    outerContainer.querySelectorAll(".connector-highlight").forEach((el) => {{
                        el.classList.remove("connector-highlight");
                    }});
                    jumpEndBtn._jumpTarget = null;
                    jumpStartBtn._jumpTarget = null;
                    if (target) {{
                        const id = target.dataset.connectorId;
                        const matches = outerContainer.querySelectorAll(`.connector[data-connector-id="${{id}}"]`);
                        matches.forEach((el) => {{
                            el.classList.add("connector-highlight");
                        }});
                        if (matches.length > 0) {{
                            jumpStartBtn._jumpTarget = matches[0];
                            jumpEndBtn._jumpTarget = matches[matches.length - 1];
                        }}
                    }}
                    updateJumpButtons();
                }});
            """)

    def search_event(self) -> None:
        """Search for the input text inside the text views and display a clickable results popup."""
        query = self.search_input.value.strip()
        if not query:
            ui.notify("Please enter a search term.", type="warning")
            return

        # Upgraded JavaScript engine targeting Quasar content nodes and penetrating Shadow Roots
        js_code = f"""
            const outerContainer = document.getElementById("c{self.scroll_area.id}");
            if (!outerContainer) return [];

            const container = outerContainer.querySelector('.q-scrollarea__content') || outerContainer;

            // 1. Purge previous search highlights completely across Shadow boundaries
            function clearPreviousHighlights(root) {{
                const highlights = root.querySelectorAll ? root.querySelectorAll('.search-highlight') : [];
                highlights.forEach(el => {{
                    const textNode = document.createTextNode(el.textContent);
                    el.parentNode.replaceChild(textNode, el);
                }});
                const children = root.querySelectorAll ? root.querySelectorAll('*') : [];
                children.forEach(child => {{
                    if (child.shadowRoot) {{
                        clearPreviousHighlights(child.shadowRoot);
                    }}
                }});
            }}
            clearPreviousHighlights(container);

            const searchTerm = {json.dumps(query.lower())};
            const results = [];
            let uniqueIdCounter = 0;

            // 2. Recursive text node crawler that only COLLECTS matches (no DOM mutation).
            //    Mutating the DOM (e.g. via surroundContents) while iterating a live
            //    childNodes list causes the newly-inserted split nodes to be picked
            //    back up by the same in-progress loop. On large documents with a
            //    common search term this spirals into extremely expensive (sometimes
            //    effectively endless) work and hangs/crashes the browser tab before
            //    a response is ever sent back to Python. So: collect first, mutate later.
            //
            //    The Map/Diagram/Misc views stream many lines into one element per CHUNK
            //    (joined by literal "\\n", relying on white-space:pre to render them as
            //    separate visual lines -- see process_data() in guiwins.py), not one
            //    element per line. That means a match's immediate parentNode is a whole
            //    chunk (or, in the Diagram view, sometimes just a connector <span>
            //    covering a few characters), not a single line -- so parent.textContent
            //    can't be used to recover "the line the match is on". Instead, build a
            //    linear transcript of the whole container's text up front, recording
            //    each text node's starting offset within it, so each match's line number
            //    and line text can be derived from where its offset falls between
            //    newlines in that transcript.
            const textNodes = [];  // {{ node, start }}
            let fullText = '';

            function collectTextNodes(node) {{
                if (node.shadowRoot) {{
                    collectTextNodes(node.shadowRoot);
                }}

                if (node.nodeType === 3) {{
                    if (node.parentNode &&
                        node.parentNode.tagName !== 'SCRIPT' &&
                        node.parentNode.tagName !== 'STYLE') {{
                        textNodes.push({{ node, start: fullText.length }});
                        fullText += node.nodeValue;
                    }}
                }} else if (node.nodeType === 1 && node.tagName === 'BR') {{
                    // The Diagram view is plain text with literal "\\n" line breaks, but the
                    // Map/Misc/Tree views are real HTML that marks line breaks with <br>
                    // elements instead -- treat each one as a line break in the transcript
                    // too, so line numbers/text line up correctly there as well.
                    fullText += '\\n';
                }}

                // Snapshot into a static array so later DOM mutations (done in the
                // second pass below) can never feed back into this traversal.
                if (node.childNodes && node.childNodes.length) {{
                    for (const child of Array.from(node.childNodes)) {{
                        collectTextNodes(child);
                    }}
                }}
            }}

            collectTextNodes(container);

            // Map a global offset into fullText -> 0-based line number, via the offset of
            // every line start (binary search since a large diagram can have many lines).
            const lineStarts = [0];
            for (let i = 0; i < fullText.length; i++) {{
                if (fullText[i] === '\\n') lineStarts.push(i + 1);
            }}
            function lineNumberForOffset(offset) {{
                let lo = 0, hi = lineStarts.length - 1;
                while (lo < hi) {{
                    const mid = (lo + hi + 1) >> 1;
                    if (lineStarts[mid] <= offset) lo = mid; else hi = mid - 1;
                }}
                return lo;
            }}
            function lineTextForOffset(offset) {{
                const ln = lineNumberForOffset(offset);
                const start = lineStarts[ln];
                const end = ln + 1 < lineStarts.length ? lineStarts[ln + 1] - 1 : fullText.length;
                return fullText.substring(start, end);
            }}

            const matches = [];  // {{ node, index, globalOffset }}
            for (const {{ node, start }} of textNodes) {{
                const index = node.nodeValue.toLowerCase().indexOf(searchTerm);
                if (index !== -1) {{
                    matches.push({{ node, index, globalOffset: start + index }});
                }}
            }}

            // Cap the number of matches we actually highlight/report. A broad
            // search term (e.g. "Task") against a large rendered document could
            // otherwise still produce thousands of DOM mutations in the pass
            // below, which is slow and unnecessary for a human skimming results.
            const MAX_MATCHES = 200;
            const truncated = matches.length > MAX_MATCHES;
            const matchesToShow = truncated ? matches.slice(0, MAX_MATCHES) : matches;

            // 3. Second pass: now that traversal is fully finished, apply the
            //    highlight to each collected match. Each match's Text node is
            //    still valid because no mutation happened during collection.
            for (const {{ node, index, globalOffset }} of matchesToShow) {{
                const span = document.createElement('span');
                span.className = 'search-highlight';
                span.id = "search_target_" + (++uniqueIdCounter);
                span.style.backgroundColor = '#ffd941';
                span.style.color = '#000000';
                span.style.fontWeight = 'bold';
                span.style.display = 'inline';

                const range = document.createRange();
                range.setStart(node, index);
                range.setEnd(node, index + {len(query)});
                range.surroundContents(span);

                results.push({{
                    elementId: span.id,
                    text: lineTextForOffset(globalOffset).trim().substring(0, 100),
                    lineNumber: lineNumberForOffset(globalOffset) + 1,
                }});
            }}

            return {{ results: results, totalMatches: matches.length, truncated: truncated }};
        """

        client = context.client

        async def execute_search() -> None:
            with self.scroll_area:
                # Await the execution of our DOM analyzer script block
                search_result = await client.run_javascript(js_code)
                found_items = search_result.get("results", [])
                total_matches = search_result.get("totalMatches", len(found_items))
                was_truncated = search_result.get("truncated", False)

                if not found_items:
                    ui.notify(f"No matches found for: '{query}'", type="negative")
                    return  # Debugging output

                if was_truncated:
                    ui.notify(
                        f"Showing first {len(found_items)} of {total_matches} matches for: '{query}'",
                        type="warning",
                    )

                # 3. Create the interactive Search Results Modal Popup Window
                with ui.dialog() as results_dialog, ui.card().classes("w-[750px] max-w-full p-6"):
                    header_text = (
                        f"Search Results for '{query}' ({len(found_items)} of {total_matches} matches)"
                        if was_truncated
                        else f"Search Results for '{query}' ({len(found_items)} matches)"
                    )
                    ui.label(header_text).classes(
                        "text-lg font-bold text-blue-600 mb-2",
                    )
                    ui.label(
                        "Click on a row index line number to jump directly to that match block placement:",
                    ).classes("text-xs text-gray-500 italic mb-4")

                    # Create a clear scroll area container for the results rows list matching the active theme font
                    with ui.scroll_area().classes("w-full h-[45vh] border p-2 bg-gray-50 dark:bg-gray-900 rounded"):  # noqa: SIM117
                        with ui.column().classes("w-full gap-1"):
                            for item in found_items:
                                # Localized function referencing the cross-linked runtime element reference
                                def make_jump_callback(target_id: str = item["elementId"]) -> None:
                                    return lambda: (
                                        results_dialog.close(),
                                        client.run_javascript(f"""
                                            // Restore any previously-clicked match back to the standard
                                            // highlight color before marking the newly-clicked one, so
                                            // only the match the user just jumped to stands out.
                                            document.querySelectorAll('.search-highlight-active').forEach(el => {{
                                                el.classList.remove('search-highlight-active');
                                                el.style.backgroundColor = '#ffd941';
                                                el.style.color = '#000000';
                                            }});
                                            const el = document.getElementById("{target_id}");
                                            if (el) {{
                                                // As in the Diagram connector jump buttons: a chunk
                                                // skipped by content-visibility: auto was never laid
                                                // out, so scrollIntoView() on a descendant of it lands
                                                // in the wrong place until it's forced to render.
                                                for (let a = el; a; a = a.parentElement) {{
                                                    if (getComputedStyle(a).contentVisibility === "auto") {{
                                                        a.style.contentVisibility = "visible";
                                                    }}
                                                }}
                                                el.classList.add('search-highlight-active');
                                                el.style.backgroundColor = '#ff5722';
                                                el.style.color = '#ffffff';
                                                el.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
                                            }}
                                        """),
                                    )

                                with ui.row().classes(
                                    "w-full items-center py-1 border-b dark:border-gray-700 hover:bg-blue-50 dark:hover:bg-blue-950 px-2 rounded transition-colors",
                                ):
                                    # Active click hotlink index line label
                                    ui.link(f"Line #{item['lineNumber']}", "#").on(
                                        "click",
                                        make_jump_callback(),
                                    ).classes(
                                        "text-blue-600 dark:text-blue-400 font-bold font-mono text-sm mr-4 shrink-0 decoration-dotted hover:underline",
                                    )
                                    # Text context content preview box
                                    ui.label(item["text"]).classes(
                                        "text-sm font-mono truncate text-gray-800 dark:text-gray-200",
                                    )

                    # Footer window management close control
                    with ui.row().classes("w-full justify-end mt-4"):
                        ui.button("Close Results Window", on_click=results_dialog.close).classes(
                            "bg-red-500 text-white px-4",
                        )

                results_dialog.open()

        self._search = asyncio.create_task(execute_search())

    def extract_first_font_name(self: MyGui, text: str) -> str:
        """
        Scans the given text to identify and return the font name
        following the very first 'font-family:' rule declaration.
        """
        # Regex Breakdown:
        # font-family\s*:\s* -> Matches 'font-family', optional spaces, a colon, and optional spaces
        # ([a-zA-Z0-9\s\-_'\"]+) -> Capture Group 1: Matches valid font name characters (letters, numbers, spaces, quotes, hyphens)
        # (?=[;}]) -> Positive Lookahead: Stops capturing when it hits a closing semicolon or bracket
        pattern = re.compile(r"font-family\s*:\s*([a-zA-Z0-9\s\-_'\"]+)(?=[;}])")

        match = pattern.search(text)

        if match:
            # Return the captured font name, stripping off any outer quotes or accidental whitespace
            return match.group(1).strip().strip("'\"")

        return "Font name not found"

    def _process_fallback_data(self: MyGui, the_data: dict | list) -> None:
        """Fallback logic to assemble HTML content strings when the source file is missing."""
        html_builder = []
        in_style_block = False
        style_buffer = []

        def is_css_line(text: str) -> bool:
            """Helper function to determine if a stray line is actually a CSS rule."""
            clean = text.strip()
            if clean.startswith((".", "#", "}", "{")):
                return True
            return bool(":" in clean and (clean.endswith(";") or "/*" in clean or "*/" in clean))

        def escape_text_except_html(text: str) -> str:
            """Escapes < and > but preserves intended HTML tags like tables and links."""

            parts = re.split(r"(<[^>]+>)", text)

            allowed_tags = {
                "a",
                "table",
                "tr",
                "td",
                "th",
                "tbody",
                "thead",
                "div",
                "span",
                "br",
                "style",
                "b",
                "i",
                "u",
                "strong",
                "em",
                "hr",
                "!doctype",
                "html",
                "head",
                "meta",
                "title",
                "body",
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
                "p",
                "ul",
                "ol",
                "li",
            }

            for i in range(len(parts)):
                if i % 2 == 0:
                    parts[i] = parts[i].replace("<", "&lt;").replace(">", "&gt;")
                else:
                    tag_name_match = re.match(r"^</?([!a-zA-Z0-9]+)", parts[i])
                    if tag_name_match and tag_name_match.group(1).lower() in allowed_tags:
                        pass
                    else:
                        parts[i] = parts[i].replace("<", "&lt;").replace(">", "&gt;")
            return "".join(parts)

        # --- 2. FALLBACK DICTIONARY PROCESSING (Legacy Map View) ---
        if self.is_map:
            for _num, (_linenum, value) in enumerate(the_data.items()):
                text_list = value.get("text", [])
                color_list = value.get("color", [])
                full_line_text = "".join(str(t) for t in text_list)

                if "<style>" in full_line_text:
                    in_style_block = True

                if in_style_block:
                    clean_line = full_line_text.replace("<style>", "").replace("</style>", "").replace('"""', "")
                    style_buffer.append(clean_line)
                    if "</style>" in full_line_text:
                        in_style_block = False
                        html_builder.append(f"<style>{''.join(style_buffer)}</style>")
                        style_buffer = []
                elif is_css_line(full_line_text):
                    html_builder.append(f"<style>{full_line_text}</style>")
                else:
                    line_html = "<div>"
                    for t_idx, text_segment in enumerate(text_list):
                        if '"""' in str(text_segment):
                            text_segment = str(text_segment).replace('"""', "")  # noqa: PLW2901
                        safe_text = escape_text_except_html(str(text_segment))
                        color = color_list[t_idx] if t_idx < len(color_list) else "inherit"
                        line_html += f"<span style='color: {color};'>{safe_text}</span>"
                    line_html = line_html.rstrip("\r\n")
                    html_builder.append(line_html + "</div>")

        # --- 3. FALLBACK LIST DATA PROCESSING (Other Views) ---
        else:
            for line in the_data:
                if line.strip() == "":
                    html_builder.append("<div>&nbsp;</div>")
                    continue
                if "<br><br>" in line:
                    line = line.replace("<br><br>", "")  # noqa: PLW2901
                if '"""' in line:
                    if line in {"<div>  </tr>\n</div>", "<div>\n</div>"}:
                        continue
                    line = line.replace('"""', "")  # noqa: PLW2901

                if "<style>" in line:
                    in_style_block = True

                if in_style_block:
                    clean_line = line.replace("<style>", "").replace("</style>", "")
                    style_buffer.append(clean_line)
                    if "</style>" in line:
                        in_style_block = False
                        html_builder.append(f"<style>{''.join(style_buffer)}</style>")
                        style_buffer = []
                elif is_css_line(line):
                    html_builder.append(f"<style>{line}</style>")
                else:
                    clean_text_line = line.rstrip("\r\n")
                    safe_line = escape_text_except_html(clean_text_line)
                    html_builder.append(f"<div>{safe_line}</div>")

        # --- 4. COMPRESS MULTIPLE BLANK LINES FOR FALLBACK DATA ---
        final_html = "".join(html_builder)
        empty_div_pattern = r"(<div>(?:\s|&nbsp;|<span[^>]*>(?:\s|&nbsp;)*</span>)*</div>\s*){2,}"
        final_html = re.sub(empty_div_pattern, "", final_html)
        final_html = re.sub(r"\n{3,}", "\n", final_html)
        final_html = re.sub(r"(<br\s*/?>\s*){2,}", "<br>", final_html)

        self.html_display.content = final_html

    def scroll(self, direction: str) -> None:
        """Manages the scroll position of the view's content area based on the specified direction ('top' or 'bottom').

        Also resets horizontal scroll back to column 1, since the view may have been scrolled
        sideways (e.g. via the search feature or a wide diagram) before Top/Bottom is clicked.
        """
        # Reset horizontal scroll back to the leftmost column regardless of direction.
        self.scroll_area.scroll_to(percent=0.0, axis="horizontal")
        if direction == "top":
            # Native NiceGUI scroll to top (0% progress)
            self.scroll_area.scroll_to(percent=0.0)
        else:
            # Native NiceGUI scroll to bottom (100% progress)
            self.scroll_area.scroll_to(percent=1.0)

    def toggle_wrap(self) -> None:
        """Toggles word-wrap on/off for this view's content, replacing the exact prior classes."""
        self.wrap_enabled = not self.wrap_enabled
        new_classes = "whitespace-pre-wrap break-words" if self.wrap_enabled else "whitespace-pre"
        self.scroll_area.classes(remove=self.wrap_classes, add=new_classes)
        self.wrap_classes = new_classes
        ui.notify(f"Word wrap {'enabled' if self.wrap_enabled else 'disabled'} for {self.title}.", type="info")

    def _profiles_per_line_selected(self, event: object) -> None:
        """Fires when the Diagram view's 'Profiles Per Line' pulldown selection changes."""
        new_value = int(event.value if hasattr(event, "value") else event)
        if new_value != self.master_gui.profiles_per_line:
            asyncio.create_task(self.master_gui.event_handlers.profiles_per_line_event(new_value))

    def reload_diagram(self) -> None:
        """Clears and re-streams the Diagram view's content in place after it has been
        regenerated (e.g. after the 'Profiles Per Line' pulldown changes the diagram's layout).
        """
        self.scroll_area.clear()
        self._task = asyncio.create_task(self.process_data([]))


# ==========================================
# 4. INITIALIZATION & LAYOUT
# ==========================================
def initialize_gui(self: MyGui) -> None:
    """Initialize state variables. 'self' is the MyGui instance."""
    _initialize_gui_settings(self)
    _initialize_ai_settings(self)
    _initialize_android_settings(self)
    _initialize_display_settings(self)
    _initialize_feature_flags(self)
    _initialize_data_structures(self)
    _initialize_runtime_options(self)


def _initialize_gui_settings(self: MyGui) -> None:
    """Initializes GUI-related appearance and display settings."""
    PrimeItems.program_arguments["gui"] = True
    self.gui = True
    self.guiview = False
    self.appearance_mode = None
    self.default_font = ""
    self.font = None
    self.bold = None
    self.italicize = None
    self.underline = None
    self.highlight = None
    self.color_labels = None
    self.color_lookup = None
    self.twisty = None
    self.indent = None
    self.display_detail_level = None
    self.everything = None
    self.view_limit = 10000
    self.profiles_per_line = DIAGRAM_PROFILES_PER_LINE
    self.pretty = False
    self.task_action_warning_limit = 20
    self.language = "English"
    self.initialization = True
    self.textview = False


def _initialize_ai_settings(self: MyGui) -> None:
    """Initializes AI-related variables."""
    self.ai_analysis = None
    self.ai_analysis_window = None
    self.ai_apikey = None
    self.ai_apikey_window = None
    self.ai_model = ""
    self.ai_name = ""
    self.ai_model_extended_list = False
    self.displaying_extended_list = None
    self.ai_prompt = None


def _initialize_android_settings(self: MyGui) -> None:
    """Initializes Android device connection settings."""
    self.android_file = ""
    self.android_ipaddr = ""
    self.android_port = ""
    self.fetched_backup_from_android = False
    self.android_auth_key = ""  # Cached Tasker HTTP API key for Save To Android (see save_task_to_android_event).
    self.android_auth_key_ipaddr = ""
    self.android_auth_key_port = ""


def _initialize_display_settings(self: MyGui) -> None:
    """Initializes settings related to how data is displayed."""
    self.doing_diagram = False
    self.diagramview_window = None
    self.map_in_progress = False
    self.mapview_window = None
    self.miscview_window = None
    self.treeview_window = None
    self.video_window = None
    self.outline = False
    self.font_table = {}


def _initialize_feature_flags(self: MyGui) -> None:
    """Initializes boolean flags for various features and states."""
    self.extract_in_progress = False
    self.first_time = True
    self.list_files = False
    self.list_unnamed_items = False
    self.reset_debug_at_end = False
    self.restore = False
    self.runtime = False
    self.save = False
    self.checked_ffmpeg = False
    self.have_ffmpeg = False
    self.close_tabs_on_exit = False


def _initialize_data_structures(self: MyGui) -> None:
    """Initializes data structures used by the application."""
    self.all_messages = {}
    self.conditions = None  # Consider if this should be initialized to a dict or list
    self.named_item = None  # Consider if this should be initialized to a specific type
    self.single_profile_name = None
    self.single_project_name = None
    self.single_task_name = None
    self.tab_to_use = None  # Consider if this should be initialized to a default tab
    self.check_boxes = []


def _initialize_runtime_options(self: MyGui) -> None:
    """Initializes variables related to runtime actions and program flow."""
    self.debug = None
    self.exit = None
    self.file = None  # Consider if this should be initialized to an empty string or specific file object
    self.go_program = None
    self.preferences = None
    self.rerun = None
    self.reset = None
    self.taskernet = None


# =========================================================================
# Initialize the GUI screen layout using NiceGUI with split sidebars and main content area.
# =========================================================================
def inject_shared_head_styles() -> None:
    """Injects the CSS shared by every page of the app (scrollbar theming, light-mode overrides,
    Map/Diagram/Tree table layout, and the Diagram view's click-to-highlight connector styling).

    ui.add_head_html() only affects the page it's called from -- each NiceGUI @ui.page is its own
    independent document. Call this from every page function (the main window's initialize_screen()
    and the "/popout/{view_type}" route in rungui.py), or a popped-out window renders Diagram
    connectors that respond to clicks (the JS wiring is unaffected) but never visibly highlight,
    since the .connector-highlight rule defined here would simply be missing from that page.
    """
    ui.add_head_html("""
        <style>
            /* Force scrollbar tracks to be visible on our target components */
            .force-scrollbar,
            .force-scrollbar .q-drawer__content {
                overflow-y: scroll !important;
                overflow-x: auto !important;
            }

            /* =========================================================================
               NATIVE BROWSER SCROLLBARS (WebKit: Chrome, Safari, Edge) - LIGHT MODE CONTRAST
               ========================================================================= */
            .force-scrollbar::-webkit-scrollbar,
            .force-scrollbar .q-drawer__content::-webkit-scrollbar {
                display: block !important;
                width: 10px !important;
                height: 10px !important;
            }
            .force-scrollbar::-webkit-scrollbar-track,
            .force-scrollbar .q-drawer__content::-webkit-scrollbar-track {
                background: rgba(0, 0, 0, 0.08) !important;
                border-radius: 4px !important;
            }
            .force-scrollbar::-webkit-scrollbar-thumb,
            .force-scrollbar .q-drawer__content::-webkit-scrollbar-thumb {
                background: #475569 !important;
                border-radius: 4px !important;
                border: 1px solid #ffffff !important;
            }
            .force-scrollbar::-webkit-scrollbar-thumb:hover,
            .force-scrollbar .q-drawer__content::-webkit-scrollbar-thumb:hover {
                background: #1e293b !important;
            }

            /* =========================================================================
               QUASAR SCROLL AREA COMPONENT (NiceGUI ui.scroll_area) - LIGHT MODE CONTRAST
               ========================================================================= */
            .q-scrollarea__thumb--v,
            .q-scrollarea__thumb--h {
                background: #475569 !important;
                opacity: 0.95 !important;
                border: 1px solid #ffffff !important;
            }

            .q-scrollarea__thumb--v:hover,
            .q-scrollarea__thumb--h:hover {
                background: #1e293b !important;
                opacity: 1 !important;
            }

            /* =========================================================================
               DARK MODE HIGH-CONTRAST OVERRIDES (Crisp Silver/White on Dark Backgrounds)
               ========================================================================= */
            .dark .force-scrollbar::-webkit-scrollbar-track,
            .dark .force-scrollbar .q-drawer__content::-webkit-scrollbar-track {
                background: rgba(255, 255, 255, 0.1) !important;
            }
            .dark .force-scrollbar::-webkit-scrollbar-thumb,
            .dark .force-scrollbar .q-drawer__content::-webkit-scrollbar-thumb,
            .dark .q-scrollarea__thumb--v,
            .dark .q-scrollarea__thumb--h {
                background: #e2e8f0 !important;
                border: 1px solid #1e293b !important;
                opacity: 0.95 !important;
            }
            .dark .force-scrollbar::-webkit-scrollbar-thumb:hover,
            .dark .force-scrollbar .q-drawer__content::-webkit-scrollbar-thumb:hover,
            .dark .q-scrollarea__thumb--v:hover,
            .dark .q-scrollarea__thumb--h:hover {
                background: #ffffff !important;
                opacity: 1 !important;
            }

            /* Firefox Engine Fallback High-Contrast */
            .force-scrollbar,
            .force-scrollbar .q-drawer__content {
                scrollbar-width: auto !important;
                scrollbar-color: #475569 rgba(0, 0, 0, 0.08) !important;
            }
            .dark .force-scrollbar,
            .dark .force-scrollbar .q-drawer__content {
                scrollbar-color: #e2e8f0 rgba(255, 255, 255, 0.1) !important;
            }

            /* =========================================================================
               TARGETED LIGHT MODE OVERRIDES (Completely bypasses macOS System preferences)
               ========================================================================= */
            html:not(.dark) body,
            html:not(.dark) .q-layout,
            html:not(.dark) .q-page-container,
            html:not(.dark) main,
            html:not(.dark) .q-drawer,
            html:not(.dark) .q-tab-panels,
            html:not(.dark) .q-tab-panel,
            html:not(.dark) .q-card,
            html:not(.dark) .q-tabs,
            html:not(.dark) .q-scrollarea,
            html:not(.dark) .q-scroll-area,
            html:not(.dark) .q-textview,
            html:not(.dark) .q-content-container,
            html:not(.dark) .q-container-context,
            html:not(.dark) div.nicegui-content {
                background-color: #ffffff !important;
                color: #000000 !important;
            }

            /* =========================================================================
               CRITICAL FIX: FORCE TOOLBAR ROWS WHITE IN LIGHT MODE
               ========================================================================= */
            html:not(.dark) .bg-gray-200,
            html:not(.dark) .dark\\:bg-gray-800,
            html:not(.dark) .gap-4.mb-6 {
                background-color: #ffffff !important;
                color: #000000 !important;
            }

            /* =========================================================================
               GLOBAL TOOLTIP FONT SIZE ADJUSTMENT
               ========================================================================= */
            .q-tooltip {
                font-size: 14px !important;
                line-height: 1.4 !important;
            }

            /* =========================================================================
               MAP/DIAGRAM/TREE VIEW: KEEP THE GENERATED DIRECTORY TABLES WITHIN THE
               SCROLL AREA. The exported HTML sizes table columns to fit their widest
               unbroken cell (Task/Profile names are often one long unbroken word), which
               is fine in a full-width standalone browser tab but overflows this narrow
               embedded box. Force fixed column widths and let long names wrap instead.
               (Set here rather than injected per-render, since ui.html() sanitizes
               dynamic content client-side via DOMPurify and strips <style> tags.)
               ========================================================================= */
            .q-scrollarea table {
                table-layout: fixed !important;
                width: 100% !important;
            }
            .q-scrollarea table td,
            .q-scrollarea table th {
                overflow-wrap: anywhere !important;
                word-break: break-word !important;
                white-space: normal !important;
            }
            /* <pre> forces its own white-space:pre in the UA stylesheet, which wins over the
               inherited whitespace-pre-wrap Tailwind class on the scroll area itself (e.g. the
               AI-analysis prompt text embedded in the exported HTML). Force it to wrap too. */
            .q-scrollarea pre {
                white-space: pre-wrap !important;
                overflow-wrap: anywhere !important;
                word-break: break-word !important;
            }
            /* Quasar's own QScrollArea stylesheet gives its internal content wrapper
               (".q-scrollarea__content", not directly reachable via ui.scroll_area().classes())
               "min-width: 100%" but no max-width -- so any wide-enough descendant (a table
               whose fixed-width rule above is only 100% of THIS already-oversized box, a long
               line that slips past a narrower fix, etc.) is free to stretch it past the visible
               area. Quasar then just lets you scroll to it horizontally instead of clipping,
               which is indistinguishable from "wrap isn't working". Cap it at 100% -- but only
               while word wrap is on (the "whitespace-pre-wrap" Tailwind class toggled by Toggle
               Wrap lives on the very same .q-scrollarea element, so it doubles as the switch
               here): wrap-off views (Diagram's ASCII art by default) still need to grow past the
               viewport and rely on that same horizontal scrollbar on purpose. */
            .q-scrollarea.whitespace-pre-wrap .q-scrollarea__content {
                max-width: 100% !important;
            }

            /* =========================================================================
               DIAGRAM VIEW: CLICK-TO-HIGHLIGHT CONNECTOR LINES
               ========================================================================= */
            .connector {
                cursor: pointer;
            }
            .connector-highlight {
                background-color: #facc15 !important;
                color: #000000 !important;
                font-weight: bold;
            }
            .connector-jump-button {
                display: none;
                position: fixed;
                z-index: 1000;
                padding: 8px 14px;
                background-color: #2563eb;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-size: 0.875rem;
                font-weight: 600;
                cursor: pointer;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.35);
            }
            .connector-jump-button:hover {
                background-color: #1d4ed8;
            }
        </style>
    """)


def initialize_screen(self: MyGui) -> None:
    """Initializes the main GUI screen layout using NiceGUI with split sidebars."""
    logger.info("Building UI Layout...")

    inject_shared_head_styles()

    # =========================================================================
    # 1. HEADER
    # =========================================================================
    with ui.header().classes("bg-blue-900 text-white p-4 justify-between items-center"):
        ui.label("MapTasker").classes("text-2xl font-bold")

        dm_controller = ui.dark_mode()

        def toggle_dark_mode(e: ui.ValueChangeEventArguments) -> None:
            is_dark = e.value

            # --- 1. Activate NiceGUI's built-in dark mode controller ---
            dm_controller.enable() if is_dark else dm_controller.disable()

            # --- 2. Resolve theme colors from a single source of truth ---
            bg = "#1e293b" if is_dark else "#ffffff"
            drawer_bg = "#1f2937" if is_dark else "#ffffff"
            fg = "#ffffff" if is_dark else "#000000"

            # --- 3. Persist state on self ---
            self.appearance_mode = "dark" if is_dark else "light"
            self.dark_mode = is_dark
            self.saved_background_color = bg
            self.color_lookup = set_color_mode(self.appearance_mode)
            bg = self.color_lookup.get("background", bg)

            # --- 4. Push background color to the browser body ---
            ui.run_javascript(f"document.body.style.backgroundColor = '{bg}';")

            # --- 5. Apply styles to every named widget that exists ---
            for attr in ("gui_left_drawer", "gui_right_drawer"):
                widget = getattr(self, attr, None)
                if widget:
                    widget.style(f"background-color: {drawer_bg} !important; color: {fg} !important;")

            for attr in (
                "gui_main_column",
                "gui_tab_panel",
                "gui_tab_panels",
                "gui_main_tabs_container",
                "gui_color_panel",
                "gui_ai_panel",
                "gui_debug_panel",
                "gui_tasker_object_panel",
                "content_container",
            ):
                widget = getattr(self, attr, None)
                if widget:
                    widget.style(f"background-color: {bg} !important; color: {fg} !important;")

            # --- 6. CRITICAL FIX: Force the text view's gui_toolbar color update ---
            textview = getattr(self, "textview", None)
            if textview:
                scroll_area = getattr(textview, "scroll_area", None)
                if scroll_area:
                    scroll_area.style(f"background-color: {bg} !important;")

                # Map / Diagram / Tree View >  Search / Clear / Top / Bottom Toolbar
                tv_toolbar = getattr(textview, "gui_toolbar", None)
                if tv_toolbar:
                    if is_dark:
                        tv_toolbar.style("background-color: #1f2937 !important; color: #ffffff !important;")
                    else:
                        tv_toolbar.style("background-color: #00ffff !important; color: #000000 !important;")

            # --- 7. CRITICAL FIX: Force the main body gui_view_toolbar color update (Current File: backup.xml ...---
            view_toolbar = getattr(self, "gui_view_toolbar", None)
            if view_toolbar:
                if is_dark:
                    view_toolbar.style("background-color: #1e293b !important; color: #ffffff !important;")
                else:
                    view_toolbar.style("background-color: #00ffff !important; color: #000000 !important;")

        ui.switch("Dark Mode", value=True, on_change=toggle_dark_mode)

    # =========================================================================
    # 2. LEFT SIDEBAR: CONFIGURATIONS, DROPDOWNS & CHECKBOXES
    # =========================================================================
    with (
        ui
        .left_drawer(value=True, fixed=True)
        .props("breakpoint=0")
        .classes(
            "bg-gray-100 dark:bg-gray-800 p-4 w-96 force-scrollbar gap-y-0 m-0 p-0 leading-none",
        ) as self.gui_left_drawer
    ):
        from maptasker.src.guiutils import add_logo  # noqa: PLC0415  Avoid circular import

        add_logo(self, "maptasker")

        ui.label("Display Options").classes("text-lg font-bold mb-2 gap-y-0 m-0 p-0 leading-none")

        # Detail level pulldown
        self.sidebar_detail_option = (
            ui
            .select(
                options=["0", "1", "2", "3", "4", "5"],
                value=str(self.display_detail_level),
                label=translate_string("Detail Level"),
                on_change=self.event_handlers.detail_selected_event,
            )
            .tooltip(translate_string("0 = least detail, 5 = most detail."))
            .classes("w-full")
            .props("dense")
        )

        # Core Feature Checkboxes
        self.everything_checkbox = ui.checkbox(
            translate_string("Just Display Everything!"),
            on_change=self.event_handlers.everything_event,
        )

        self.conditions_checkbox = ui.checkbox(
            translate_string("Display Conditions"),
            on_change=self.event_handlers.condition_event,
        )

        self.taskernet_checkbox = ui.checkbox(
            translate_string("Display TaskerNet Info"),
            on_change=self.event_handlers.taskernet_event,
        )

        self.preferences_checkbox = ui.checkbox(
            translate_string("Display Tasker Preferences"),
            on_change=self.event_handlers.preferences_event,
        )

        self.twisty_checkbox = ui.checkbox(
            translate_string("Hide Task Details Under Twisty"),
            on_change=self.event_handlers.twisty_event,
        )

        self.directory_checkbox = ui.checkbox(
            translate_string("Display Directory"),
            on_change=self.event_handlers.directory_event,
        )

        self.pretty_checkbox = ui.checkbox(
            translate_string("Display Prettier Output"),
            on_change=self.event_handlers.pretty_event,
        )

        _create_name_display_options_section(self)
        _create_task_action_limit_section(self)
        _create_indentation_section(self)
        _create_language_selection_section(self)
        _create_font_section(self)
        _create_view_limit_section(self)

    # =========================================================================
    # 3. RIGHT SIDEBAR: ALL ACTION, HELP & SETTINGS BUTTONS
    # =========================================================================
    with (
        ui
        .right_drawer(value=True, fixed=True)
        .props("breakpoint=0")
        .classes(
            "bg-gray-100 dark:bg-gray-800 p-4 w-80 force-scrollbar flex flex-col items-center text-center",
        ) as self.gui_right_drawer
    ):
        ui.label("Actions & Control").classes("text-lg font-bold mb-2 self-center")

        ui.label("Execution").classes("text-xs font-bold uppercase text-gray-400 mt-2 self-center")
        get_file_color = "green" if PrimeItems.file_to_get else "red"
        blink_class = "" if PrimeItems.file_to_get else " animate-pulse"

        self.get_xml_button = ui.button(
            "Get Local XML File",
            color=get_file_color,
            on_click=self.event_handlers.getxml_event,
            icon="folder",
        ).classes(f"w-full justify-center {blink_class}")
        with self.get_xml_button:
            ui.tooltip(
                "Fetch XML from a local drive on this computer.\n\nThe XML fetched will become the current source for MapTasker commands.",
            ).style("white-space: pre-line")

        self.exit_button = ui.button(
            "Exit",
            color="orange",
            on_click=lambda: get_rid_of_windows_and_exit(self),
        ).classes(
            "w-full bg-red-600 text-white mt-2 justify-center",
        )

        self.close_tabs_on_exit_checkbox = (
            ui.checkbox("Close Tabs On Exit").bind_value(self, "close_tabs_on_exit").classes("text-xs mt-1")
        )
        with self.close_tabs_on_exit_checkbox:
            ui.tooltip(
                "When enabled, clicking 'Exit' also closes the main MapTasker window and any "
                "Map/Diagram windows/tabs it opened.\n\nWhen disabled, 'Exit' shuts down MapTasker "
                "but leaves those windows/tabs open.",
            ).style("white-space: pre-line")

        ui.label("File Operations").classes("text-xs font-bold uppercase text-gray-400 mt-4 self-center")
        _create_file_and_message_buttons_section(self)

        ui.label("Display Views").classes("text-xs font-bold uppercase text-gray-400 mt-4 self-center")
        with ui.row().classes("w-full justify-center gap-2 gap-y-0 mt-1"):
            ui.button("Map", on_click=lambda: self.event_handlers.view_event("map")).classes("bg-blue-500")
            ui.button("Diagram", on_click=lambda: self.event_handlers.view_event("diagram")).classes("bg-blue-500")
            ui.button("Tree", on_click=lambda: self.event_handlers.view_event("tree")).classes("bg-blue-500")
        ui.button("Clear", on_click=self.event_handlers.clear_view_event).classes("bg-blue-500")

        ui.label("Application Settings").classes("text-xs font-bold uppercase text-gray-400 mt-4 self-center")
        _create_settings_buttons_section(self)

        ui.label(translate_string("Help & Information")).classes(
            "text-xs font-bold uppercase text-gray-400 mt-4 gap-w-0 m-0 p-0 leading-none self-center",
        )
        _create_help_options_section(self)

    # =========================================================================
    # 4. MAIN BODY CONTENT AREA
    # =========================================================================
    with ui.column().classes("p-6 w-full max-w-full mx-auto") as self.gui_main_column:
        with ui.row().classes("gap-4 mb-6") as self.gui_view_toolbar:
            self.current_file = ui.label(translate_string("No file loaded")).classes("text-gray-500 italic")

        with ui.tabs().classes("w-full") as self.gui_main_tabs_container:
            self.tab_specific_name = ui.tab(translate_string("Specific Name"), icon="filter_list")
            self.tab_colors = ui.tab(translate_string("Colors"), icon="palette")
            self.tab_analyze = ui.tab(translate_string("Analyze"), icon="analytics")
            self.tab_debug = ui.tab(translate_string("Debug"), icon="bug_report")

        with ui.tab_panels(self.gui_main_tabs_container, value=self.tab_specific_name).classes(
            "w-full border rounded shadow-inner p-4 mt-1 gap-y-0 m-0 p-0 leading-none",
        ) as self.gui_tab_panels:
            # --- TAB 1: SPECIFIC NAME (MINIMIZED SPACING) ---
            with ui.tab_panel(self.tab_specific_name).classes("p-2 m-0") as self.gui_tasker_object_panel:
                ui.label(translate_string("Target specific Projects, Profiles, or Tasks.   (Select only one)")).classes(
                    "text-base mb-1",
                )
                self.currently_selected_label = ui.label("").classes("text-xs mb-2 text-gray-500 italic")

                # Wrap the pulldowns in a tight column with minimal vertical gap
                with ui.column().classes("gap-1 w-full m-0 p-0"):
                    self.specific_project_optionmenu = (
                        ui
                        .select(
                            ["None"],
                            on_change=lambda e: (
                                self.event_handlers.single_project_name_event(e.value) if e.value else None
                            ),
                            label=translate_string("Project"),
                            with_input=True,
                        )
                        .classes("w-64 mb-0")
                        .props("dense")
                    )

                    self.specific_profile_optionmenu = (
                        ui
                        .select(
                            ["None"],
                            on_change=lambda e: (
                                self.event_handlers.single_profile_name_event(e.value) if e.value else None
                            ),
                            label=translate_string("Profile"),
                            with_input=True,
                        )
                        .classes("w-64 mb-0")
                        .props("dense")
                    )

                    self.specific_task_optionmenu = (
                        ui
                        .select(
                            ["None"],
                            on_change=lambda e: (
                                self.event_handlers.single_task_name_event(e.value) if e.value else None
                            ),
                            label=translate_string("Task"),
                            with_input=True,
                        )
                        .classes("w-64 mb-0")
                        .props("dense")
                    )

                self.specific_name_msg_label = ui.label("").classes("text-xs ml-2 mt-1 text-left")
                self.list_unnamed_items_checkbox = ui.checkbox(
                    translate_string("List Unnamed Items"),
                    on_change=self.event_handlers.list_unnamed_items_event,
                ).classes("mt-1 text-xs")
                with ui.row().classes("gap-2 m-0 p-0"):
                    self.edit_project_button = ui.button(
                        translate_string("Edit Project"),
                        on_click=self.event_handlers.open_edit_project_dialog_event,
                    ).classes("w-64 mt-2 bg-blue-500")
                    self.add_project_button = ui.button(
                        translate_string("Add Project"),
                        on_click=self.event_handlers.open_add_project_dialog_event,
                    ).classes("w-64 mt-2 bg-blue-500")
                with ui.row().classes("gap-2 m-0 p-0"):
                    self.edit_profile_button = ui.button(
                        translate_string("Edit Profile"),
                        on_click=self.event_handlers.open_edit_profile_dialog_event,
                    ).classes("w-64 mt-2 bg-blue-500")
                    self.add_profile_button = ui.button(
                        translate_string("Add Profile"),
                        on_click=self.event_handlers.open_add_profile_dialog_event,
                    ).classes("w-64 mt-2 bg-blue-500")
                with ui.row().classes("gap-2 m-0 p-0"):
                    self.edit_task_button = ui.button(
                        translate_string("Edit Task"),
                        on_click=self.event_handlers.open_edit_task_dialog_event,
                    ).classes("w-64 mt-2 bg-blue-500")
                    self.add_task_button = ui.button(
                        translate_string("Add Task"),
                        on_click=self.event_handlers.open_add_task_dialog_event,
                    ).classes("w-64 mt-2 bg-blue-500")

            # --- TAB 2: COLORS (MINIMIZED SPACING) ---
            with ui.tab_panel(self.tab_colors).classes("p-2 m-0") as self.gui_color_panel:
                ui.label("Theme Configuration").classes("text-base mb-1")
                ui.button(
                    "Reset to Default Colors",
                    on_click=self.event_handlers.color_reset_event,
                ).classes("bg-blue-500 text-xs py-1")

                self.color_change = ui.label("Select a category to modify its color.").classes("text-xs mt-2")

                with ui.column().classes("gap-1 w-full mt-1"):
                    self.color_objects_options = (
                        ui
                        .select(
                            options=[
                                "Projects",
                                "Profiles",
                                "Disabled Profiles",
                                "Launcher Tasks",
                                "Profile Conditions",
                                "Tasks",
                                "Unnamed Tasks",
                                "(Task) Actions",
                                "Action Conditions",
                                "Action Labels",
                                "Action Names",
                                "Scenes",
                                "Background",
                                "TaskerNet Information",
                                "Tasker Preferences",
                                "Highlight",
                                "Heading",
                            ],
                            value="Projects",
                            label="Select Category to Colorize",
                        )
                        .classes("w-64 mb-0")
                        .props("dense")
                    )

                    self.color_picker_input = (
                        ui
                        .color_input(
                            label="Choose Hex Color",
                            value="#3f99ff",
                            on_change=lambda e: self.event_handlers.handle_color_pick_event(e.value),
                        )
                        .classes("w-64 mb-0")
                        .props("dense")
                    )

            # --- TAB 3: ANALYZE (MINIMIZED SPACING) ---
            with ui.tab_panel(self.tab_analyze).classes("p-2 m-0") as self.gui_ai_panel:
                ui.label("AI Analysis").classes("text-base mb-2")
                _create_analyze_tab_content(self, ui.tab_panel(self.tab_analyze))

            # --- TAB 4: DEBUG (MINIMIZED SPACING) ---
            with ui.tab_panel(self.tab_debug).classes("p-2 m-0") as self.gui_debug_panel:  # noqa: SIM117
                with ui.column().classes("gap-1"):
                    self.debug_checkbox = ui.checkbox("Debug Mode").bind_value(self, "debug").classes("text-xs")
                    self.runtime_checkbox = (
                        ui.checkbox("Display Runtime Settings").bind_value(self, "runtime").classes("text-xs")
                    )

            add_logo(self, "coffee")

        self.content_container = ui.column().classes("w-full max-w-full min-w-0 p-0 m-0 mt-6")

        with ui.dialog() as self.picker_dialog, ui.card().classes("p-4 items-center"):
            self.picker_title_label = ui.label("").classes("font-bold text-sm mb-2")
            self.picker_engine = ui.color_picker()
            ui.button("Cancel", on_click=self.picker_dialog.close).classes("mt-4 w-full bg-gray-500 text-white")

    if self.tab_to_use:
        self.gui_main_tabs_container.set_value(self.tab_to_use)


async def get_rid_of_windows_and_exit(self: MyGui, _delete_all: bool = True) -> None:
    """Shuts down the NiceGUI server and exits."""
    if getattr(self, "close_tabs_on_exit", False):
        # Close every Map/Diagram popout this window opened (tracked in window.mapTaskerPopouts,
        # see _open_popout_window() in userintr.py), then this window itself. Browsers only allow
        # script-driven window.close() on tabs/windows the script itself opened, so this window
        # may refuse to close if it wasn't launched via window.open() -- that's an unavoidable
        # browser security restriction, not a bug.
        # Must be awaited: run_javascript() only sends its payload once the event loop gets a
        # chance to run the background task it schedules -- and app.shutdown() below tears down
        # that same event loop. Without awaiting, shutdown can win the race and the browser never
        # receives the command, so the tabs are left open. window.close()-ing this tab itself may
        # tear down the connection before a response comes back, hence the timeout/suppress.
        try:
            await ui.run_javascript(
                "(window.mapTaskerPopouts || []).forEach(w => { try { if (w && !w.closed) w.close(); } "
                "catch (e) {} }); window.mapTaskerPopouts = []; window.close();",
                timeout=2.0,
            )
        except Exception:  # noqa: BLE001
            pass
    ui.notify("Shutting down MapTasker...", type="warning")
    app.shutdown()


def _create_analyze_tab_content(self: MyGui, tab: ui.tab_panel) -> None:
    """Populates the 'Analyze' (AI) tab using NiceGUI and colors the analysis button contextually."""
    from maptasker.src.guiutils import (  # noqa: PLC0415  Avoid circular import
        display_model_pulldown,
        update_analysis_button_color,
    )

    # Use the 'with' context manager to place elements inside the passed tab panel
    with tab:
        # 1. Action Buttons Row
        with ui.row().classes("items-center gap-4 mb-4"):
            self.show_apikeys_button = ui.button("Show/Edit API Key(s)", on_click=self.event_handlers.ai_apikey_event)
            self.change_prompt_button = ui.button("Change Prompt", on_click=self.event_handlers.ai_prompt_event)

            self.analysis_button = ui.button(
                "Run Analysis",
                on_click=self.event_handlers.ai_analyze_event,
            )
            update_analysis_button_color(self)
            self.analysis_query_button = ui.button(
                "?",
                on_click=lambda: self.event_handlers.query_event("ai"),
            ).classes("bg-blue-600 text-white min-w-[40px]")

        # 2. Model Selection Row
        with ui.row().classes("items-center gap-4"):
            self.model_to_use_label = ui.label("Model to Use:").classes("font-bold")

            # Display the default model list
            display_model_pulldown(self)

            # Extra model list checkbox with chained tooltip
            self.aimodel_extend_checkbox = (
                ui
                .checkbox("Extended", on_change=self.event_handlers.extended_models_event)
                .tooltip(
                    "Display an extended list of ALL available models.\n\n"
                    "Note: If the API key is not set for OpenAI or Gemini,\n"
                    "      then the default model list for the respective\n"
                    "      AI provider will be displayed.\n\n"
                    "Note: Not all models have been validated and\n"
                    "      one or more may return an error on analysis.\n\n"
                    "Note: Enabling this option for the first time will\n"
                    "      force the installation of the following modules\n"
                    "      and all of their dependencies:\n"
                    "      google-genai, anthropic, openai, ollama",
                )
                .style("white-space: pre-line")
            )  # Ensures the newline characters format correctly in HTML


def _create_name_display_options_section(self: MyGui) -> None:
    """
    Optimized creation of name display options using NiceGUI.
    Renders a section header and a condensed 2x2 grid of styling checkboxes.
    """
    handlers = self.event_handlers

    # 1. Create the Section Label with an inline native tooltip
    self.display_names_label = (
        ui
        .label("Project/Profile/Task/Scene Names:")
        .classes("text-sm font-semibold mt-4 mb-1 py-0 my-0 gap-y-0 leading-none")
        .tooltip("Add highlighting to Project, Profile and Task names in the output.")
    )

    # 2. Define Checkbox Configurations
    checkbox_configs = [
        (
            "bold_checkbox",
            handlers.names_bold_event,
            "Bold",
            "Bold and Italicize are mutually exclusive in the Map view.",
        ),
        (
            "italicize_checkbox",
            handlers.names_italicize_event,
            "Italicize",
            "Italicize and Bold are mutually exclusive in the Map view.",
        ),
        ("highlight_checkbox", handlers.names_highlight_event, "Highlight", None),
        ("underline_checkbox", handlers.names_underline_event, "Underline", None),
    ]

    # 3. Batch Creation inside a highly condensed 2-Column Grid Layout
    # Changed gap-y-1 to gap-y-0 to completely eliminate grid vertical row spacing
    with ui.grid(columns=2).classes("w-full gap-x-4 py-0 my-0 gap-y-0 pl-2"):
        for attr, event, label, tip in checkbox_configs:
            # Instantiate the checkbox and strip vertical padding/margins via py-0 my-0
            checkbox = ui.checkbox(label, on_change=event).classes("py-0 my-0")

            # Save the reference dynamically to the 'self' instance
            setattr(self, attr, checkbox)

            # Chain the tooltip natively if one is defined
            if tip:
                checkbox.tooltip(tip)


def _create_task_action_limit_section(self: MyGui) -> None:
    """Creates the task 'actions' limit slider in the NiceGUI sidebar."""
    text_to_insert = "Task 'actions' limit"
    text = PrimeItems._(text_to_insert) if hasattr(PrimeItems, "_") else text_to_insert

    # 1. Label tracking the live dynamic value
    self.task_action_label = ui.label(f"{text}: {self.task_action_warning_limit}").classes(
        "text-sm font-semibold mt-4 mb-1 py-0 my-0 gap-y-0",
    )

    # 2. NiceGUI Slider
    # CustomTkinter uses 'command=', NiceGUI uses 'on_change='
    # NiceGUI handles styling with Tailwind (e.g., track color tints via accent)
    self.task_action_limit = ui.slider(
        min=10,
        max=100,
        step=1,
        value=100,
        on_change=self.event_handlers.tasklimit_event,
    ).classes(
        "w-full px-2 accent-green-600 py-0 my-0 gap-y-0",
    )
    with self.task_action_limit:
        ui.tooltip(
            "Select how many actions in a Task before issuing a warning.\n"
            "The warning appears near the bottom of the configuration output,\n"
            "and is intended to help identify Tasks that are too complex\n"
            "and which should potentially be broken up into multiple Tasks.\n"
            "A setting of '100' means there is no limit.",
        ).style(
            "white-space: pre-line",
        )  # Ensures the tooltip text respects newlines for better readability


def _create_indentation_section(self: MyGui) -> None:
    """Creates the If/Then/Else indentation dropdown options in the NiceGUI sidebar."""
    self.indent_label = ui.label("If/Then/Else Indentation Amount:").classes(
        "text-sm font-semibold mt-4 mb-1 leading-none py-0 my-0 gap-y-0",
    )

    # CustomTkinter's option menu transforms into ui.select
    self.indent_option = ui.select(
        options=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
        value="4",  # Default initial value matching your original comments
        on_change=self.event_handlers.indent_selected_event,
    ).classes("w-full leading-none py-0 my-0 gap-y-0")
    with self.indent_option:
        ui.tooltip(
            "Set the indentation amount for If/Then/Else blocks.\n\n"
            "The default is '4'.\n\n"
            "This affects how the output is formatted in the Map and Diagram views.",
        ).style(
            "white-space: pre-line",
        )  # Ensures the tooltip text respects newlines for better readability


def _create_language_selection_section(self: MyGui) -> None:
    """Creates the language selection dropdown in the NiceGUI sidebar."""
    self.language_label = ui.label("Language:  ").classes(
        "text-sm font-semibold mt-4 mb-1 leading-none py-0 my-0 gap-y-0",
    )

    # This returns a list of English language keys, e.g., ["English", "German", "French"]
    languages = sort_languages_with_priority(PrimeItems.languages.keys())

    # ui.select's "value" (what on_change reports, and what must be assigned to select
    # a specific entry) is always the dict KEY, never the displayed label -- so map each
    # English key to its translated display label (e.g. "German" -> "Deutsch") here. That
    # keeps the value side in English (matching self.language / PrimeItems.languages) while
    # still showing the user their language's own name instead of always English.
    language_options = {language: translate_string(language) for language in languages}

    self.language_optionmenu = ui.select(
        options=language_options,
        value=self.language,
        on_change=self.event_handlers.language_selected_event,
    ).classes("w-full")


def _create_view_limit_section(self: MyGui) -> None:
    """Creates the view limit dropdown in the sidebar drawer."""
    self.viewlimit_label = ui.label("View Limit:").classes(
        "text-sm font-semibold mt-4 mb-1 leading-none py-0 my-0 gap-y-0",
    )

    with ui.row().classes("w-full items-center gap-2"):
        # CustomTkinter's option menu becomes a ui.select dropdown
        temp_view_limit = getattr(self, "view_limit", "10000")
        if temp_view_limit == 9999999:
            self.view_limit = "Unlimited"
        self.viewlimit_optionmenu = ui.select(
            options=["5000", "10000", "15000", "20000", "25000", "30000", "Unlimited"],
            value=str(getattr(self, "view_limit", "10000")),
            on_change=self.event_handlers.viewlimit_event,
        ).classes("flex-grow")
        with self.viewlimit_optionmenu:
            ui.tooltip(
                "Select the maximum number of items to display in the view to be allowed.\n\n"
                "Anything over this amount will stop the generation of the view as a means to throttle the program.\n\n"
                "Note: This is only for the 'Map' and 'Diagram' views, not the tree view.",
            ).style(
                "white-space: pre-line",
            )  # Ensures the tooltip text respects newlines for better readability
        self.view_limit = int(temp_view_limit) if temp_view_limit != "Unlimited" else 9999999

        # Query help button
        self.viewlimit_query_button = ui.button(
            "?",
            on_click=lambda: self.event_handlers.query_event("viewlimit"),
        ).classes("bg-blue-600 text-white min-w-[40px]")


def _create_settings_buttons_section(self: MyGui) -> None:
    """Creates settings buttons in their respective responsive layout containers."""
    handlers = self.event_handlers

    # 1. Sidebar Buttons (Master: self.gui_left_drawer)
    with self.gui_left_drawer:
        self.reset_button = ui.button("Reset Options", on_click=handlers.reset_settings_event).classes(
            "w-full bg-blue-600 text-white mt-2",
        )
        # Nest the tooltip explicitly inside the button context
        with self.reset_button:
            ui.tooltip(
                "Reset all of the options to their default values, including colors, font used, and other settings.\n\n"
                "The currently loaded XML will be cleared out.",
            ).style(
                "white-space: pre-line;",
            )  # Tells the web browser to render \n newlines!

    # 2. Main Window Buttons Layout Area
    with ui.row().classes("w-full gap-2 mt-0 justify-center"):
        self.save_settings_button = ui.button("Save Settings", on_click=handlers.save_settings_event).classes(
            "bg-indigo-600 text-white justify-center",
        )

        self.restore_settings_button = ui.button("Restore Settings", on_click=handlers.restore_settings_event).classes(
            "bg-indigo-600 text-white justify-center",
        )

        self.report_issue_button = ui.button("Report Issue", on_click=handlers.report_issue_event).classes(
            "bg-gray-600 text-white justify-center",
        )
        with self.report_issue_button:
            ui.tooltip(
                "Report any issues and/or suggestions to the developer.\n\n"
                "This will open a browser window to the GitHub Issues page, and you will need a GitHub account to submit an issue.",
            ).style("white-space: pre-line;")


def _create_font_section(self: MyGui) -> None:
    """Creates the monospaced font selection dropdown inside the content container."""
    self.font_label = ui.label("Font To Use In Output:").classes(
        "text-sm font-semibold mt-4 mb-1 py-0 my-0 gap-y-0 m-0 p-0 leading-none",
    )

    if not PrimeItems.mono_fonts:
        font_items = get_monospace_fonts()
        PrimeItems.mono_fonts = font_items
    else:
        font_items = PrimeItems.mono_fonts

    default_font = [value for value in font_items if "Courier" in value]
    self.default_font = default_font[0] if default_font else font_items[0]

    # ui.select manages choices natively
    self.font_optionmenu = ui.select(
        options=font_items,
        value=font_items[0] if font_items else self.default_font,
        on_change=self.event_handlers.font_event,
    ).classes("w-64")
    with self.font_optionmenu:
        ui.tooltip(
            "This is a list of all of the monospaced fonts available on your system.\n\n"
            "The font selected will be used in all output.\n\n"
            "'Courier' or 'Courier New' is highly recommended for Diagrams to ensure proper connector alignment.",
        ).style(
            "white-space: pre-line;",
        )  # Ensures newlines render properly in the tooltip


def _create_file_and_message_buttons_section(self: MyGui) -> None:
    """Creates file actions, message configuration button rows, and dynamic android panel containers."""
    with self.gui_right_drawer:
        # Stored on self so clear_android_buttons() (guiutils.py) can re-enter this exact row
        # when it deletes and recreates the button -- otherwise the recreated button attaches to
        # whatever the default page slot happens to be during that event callback and ends up
        # stranded at the bottom of the page instead of staying under "File Operations".
        with ui.row().classes("w-full flex-nowrap items-center justify-center gap-2 mt-0") as self.android_button_row:
            # self.get_backup_button = self.display_backup_button(
            #     "Get XML from Android Device",
            #     "#246FB6",
            #     "#6563ff",
            #     self.event_handlers.get_xml_from_android_event,
            # )
            self.get_backup_button = (
                ui
                .button("Get XML from Android Device", on_click=self.event_handlers.get_xml_from_android_event)
                .style("background-color: #246FB6; border-color: #6563ff; border-width: 2px; color: white;")
                .classes("mt-0 ml-0 font-bold flex-grow text-xs")
            )
            self.android_query_button = ui.button(
                "?",
                on_click=lambda: self.event_handlers.query_event("android"),
            ).classes("bg-blue-600 text-white min-w-[40px] shrink-0")
        with self.get_backup_button:
            ui.tooltip(
                "Fetch XML from an Android device.\n\nYou must be on the same network as the Android device, and the device must be running and connected.\n\n",
            ).style("white-space: pre-line")

        # The container panels stay bound right here under the button setup
        self.android_container = ui.column().classes(
            "w-full gap-y-2 mt-4 p-2 bg-gray-50 dark:bg-gray-700 rounded shadow-sm hidden",
        )
        self.upgrade_container = ui.column().classes("w-full gap-y-2 mt-2 items-center text-center hidden")


def _create_help_options_section(self: MyGui) -> None:
    """Creates browser execution panels, help routing shortcuts, and app termination controls."""
    handlers = self.event_handlers

    # 1. Specialized Help Buttons Row
    with ui.row().classes("w-full gap-2 mt-0 self_center justify-center"):
        self.display_help_button = ui.button("Display Help", on_click=lambda: handlers.query_event("help")).classes(
            "bg-blue-600 text-white",
        )

        self.get_android_help_button = ui.button(
            "Get Android Help",
            on_click=lambda: handlers.query_event("android"),
        ).classes("bg-blue-600 text-white")
