"""The Profile editor: the Edit/Add/Delete Profile dialogs and its Save To Android panel.

Split out of guiwins.py, which had grown to 14,500 lines.  _build_profile_editor_body is the
bulk of it -- a Profile's contexts (Application, Day, Time, State, Event, Location) each get
their own panel, and the ones that carry arguments render them through the Task editor's own
argument fields, which is why this module imports from guiwins_taskedit.

Its four calls back into guiwins -- editor_state, PendingChangesBanner, the Properties button
and the shared Save To Android fields -- are made inside the functions that need them, for
the same reason as guiwins_taskedit: guiwins imports the split-out modules at the top of its
own file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from maptasker.src import objprops, profedit
from maptasker.src.guiwins_impact import build_impact_panel
from maptasker.src.guiwins_taskedit import (
    _after_condition_fetch,
    _render_app_arg_field,
    _render_app_entry_pick_button,
    _render_icon_arg_field,
    _render_plugin_configuration_warning,
    _render_readonly_note,
)
from maptasker.src.mapjump import PROFILE
from maptasker.src.maputil2 import translate_string
from maptasker.src.primitem import PrimeItems

if TYPE_CHECKING:
    from nicegui.elements.select import Select

    from maptasker.src.userintr import MyGui


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


def _build_profile_editor_body(
    self: MyGui,
    edited_profile: profedit.EditableProfile,
    field_refs: dict,
    parent_dialog: ui.dialog,
) -> None:
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
    # Imported here rather than at the top of the file: guiwins imports this module, so a
    # module-level import would be a cycle.  See this module's docstring.
    from maptasker.src.guiwins import _build_properties_button  # noqa: PLC0415

    with ui.row().classes("w-full items-center gap-4"):
        enabled_switch = ui.switch(
            value=profedit.is_profile_enabled(edited_profile),
            on_change=lambda e: self.event_handlers.set_profile_enabled_event(edited_profile, e.value),
        )
        enabled_switch.bind_text_from(enabled_switch, "value", backward=lambda v: "Enabled" if v else "Disabled")

        # The working copy, and no on_applied: every Profile save path goes through it --
        # apply_edited_profile_to_live_tree swaps the whole element into all_profiles,
        # render_standalone_profile_xml takes the EditableProfile, and register_new_profile
        # stores this same object for a brand-new one -- so this is the Task situation, not
        # the Project one.  Being in the shared body, one call covers Add and Edit alike.
        #
        # parent_dialog is passed in rather than found: this body is built inside its
        # caller's `with ui.dialog()` block, and the Properties editor needs to know which
        # dialog it is opening over.  See build_edit_profile_dialog/build_add_profile_dialog.
        _build_properties_button(self, objprops.KIND_PROFILE, edited_profile.profile_element, parent_dialog)

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
                            translate_string("Unlink"),
                            on_click=lambda lt=link_type: (
                                self.event_handlers.unlink_task_from_profile_event(edited_profile, lt),
                                render_task_links(),
                            ),
                        ).props("flat color=red dense")
                    else:
                        picker = (
                            ui.select(task_names, label=translate_string("Choose a Task"), with_input=True)
                            .classes("flex-1")
                            .props("dense")
                        )
                        # Registered under a fixed key (not cleared/rebuilt like the cond*
                        # keys) so Save/Ok/Save To Android can link in whatever's currently
                        # picked here even if the user never clicked "Link" separately --
                        # see userintr._link_pending_task_pickers.
                        field_refs[f"{link_type.lower()}_task_picker"] = picker
                        ui.button(
                            translate_string("Link"),
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
                            translate_string("Add Task"),
                            on_click=lambda lt=link_type: self.event_handlers.open_add_task_for_profile_link_event(
                                edited_profile,
                                lt,
                                render_task_links,
                            ),
                        ).props("flat color=blue dense")

    render_task_links()

    ui.label(translate_string("Conditions")).classes("text-sm font-bold mt-4")
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
                ui.label(translate_string("No conditions on this Profile.")).classes("text-xs text-gray-500 italic")
            for condition in edited_profile.conditions:
                header = f"{condition.cond_index}: {profedit.get_condition_display_name(condition)}"
                with ui.expansion(header).classes("w-full"):
                    ui.button(
                        translate_string("Delete Condition"),
                        on_click=lambda ci=condition.cond_index: (
                            self.event_handlers.remove_condition_from_profile_event(edited_profile, ci),
                            render_conditions(),
                        ),
                    ).props("flat color=red dense").classes("mb-2")

                    if condition.cond_type in ("State", "Event"):
                        _render_plugin_configuration_warning(
                            condition.condition_element,
                            profedit.get_condition_display_name(condition),
                        )
                        if not condition.args:
                            ui.label(
                                translate_string(
                                    "No editable arguments (code not mapped, or this condition has none).",
                                ),
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
                                elif arg.widget_kind == "app_picker":
                                    _render_app_arg_field(
                                        self,
                                        arg,
                                        key,
                                        field_refs,
                                        text_initial(key, arg.current_value),
                                    )
                                elif arg.widget_kind == "icon_picker":
                                    _render_icon_arg_field(
                                        self,
                                        arg,
                                        key,
                                        field_refs,
                                        text_initial(key, arg.current_value),
                                    )
                                elif arg.widget_kind in ("text", "raw_fallback"):
                                    field_refs[key] = ui.input(
                                        arg.arg_name,
                                        value=text_initial(key, arg.current_value),
                                    ).classes("flex-1")
                                    if arg.readonly_note:
                                        _render_readonly_note(
                                            self,
                                            arg.readonly_note,
                                            _after_condition_fetch(render_conditions, condition),
                                        )
                                else:  # readonly
                                    ui.input(arg.arg_name, value=arg.current_value).props("readonly").classes(
                                        "flex-1",
                                    )
                                    if arg.readonly_note:
                                        _render_readonly_note(
                                            self,
                                            arg.readonly_note,
                                            _after_condition_fetch(render_conditions, condition),
                                        )

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
                                translate_string("Start Time"),
                                value=text_initial(start_key, values["start_time"]),
                                placeholder=translate_string("hh:mm AM/PM or %variable"),
                            ).classes("flex-1")
                            field_refs[end_key] = ui.input(
                                translate_string("End Time"),
                                value=text_initial(end_key, values["end_time"]),
                                placeholder=translate_string("hh:mm AM/PM or %variable"),
                            ).classes("flex-1")
                        with ui.row().classes("w-full gap-2 items-end mt-2"):
                            field_refs[rep_value_key] = ui.input(
                                translate_string("Every"),
                                value=text_initial(rep_value_key, values["rep_value"]),
                            ).classes("w-24")
                            field_refs[rep_unit_key] = (
                                ui.select(
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

                        ui.label(translate_string("Week-Day")).classes("text-xs font-bold text-gray-500")
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
                                translate_string("All"),
                                on_click=lambda boxes=weekday_checkboxes: set_weekday_checkboxes(
                                    boxes,
                                    set(range(1, 8)),
                                ),
                            ).props("flat dense")
                            ui.button(
                                translate_string("None"),
                                on_click=lambda boxes=weekday_checkboxes: set_weekday_checkboxes(boxes, set()),
                            ).props("flat dense")
                            ui.button(
                                translate_string("Odd"),
                                on_click=lambda boxes=weekday_checkboxes: set_weekday_checkboxes(
                                    boxes,
                                    {1, 3, 5, 7},
                                ),
                            ).props("flat dense")

                        ui.label(translate_string("Month")).classes("text-xs font-bold text-gray-500")
                        selected_months = set(profedit.get_day_selected_months(condition))
                        with ui.row().classes("w-full gap-2 flex-wrap mb-2"):
                            for month_number in range(12):
                                month_key = profedit.condition_field_key(condition.cond_index, f"mnth{month_number}")
                                field_refs[month_key] = ui.checkbox(
                                    profedit.MONTH_NAMES[month_number],
                                    value=checkbox_initial(month_key, month_number in selected_months),
                                )

                        ui.label(translate_string("Day of Month")).classes("text-xs font-bold text-gray-500")
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
                                translate_string("Last Day Of Month"),
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
                                    translate_string("Package"),
                                    value=text_initial(pkg_key, entry["pkg"]),
                                ).classes("flex-1")
                                field_refs[label_key] = ui.input(
                                    translate_string("Label"),
                                    value=text_initial(label_key, entry["label"]),
                                ).classes("flex-1")
                                field_refs[cls_key] = ui.input(
                                    translate_string("Class (optional)"),
                                    value=text_initial(cls_key, entry["cls"]),
                                ).classes("flex-1")
                                _render_app_entry_pick_button(self, field_refs, pkg_key, label_key, cls_key)
                                ui.button(
                                    translate_string("Remove"),
                                    on_click=lambda ci=condition.cond_index, ei=entry_index: (
                                        self.event_handlers.remove_app_entry_event(edited_profile, ci, ei),
                                        render_conditions(),
                                    ),
                                ).props("flat color=red dense")
                        ui.button(
                            translate_string("Add App Entry"),
                            on_click=lambda ci=condition.cond_index: (
                                self.event_handlers.add_app_entry_event(edited_profile, ci),
                                render_conditions(),
                            ),
                        ).props("flat color=blue dense")

            with ui.row().classes("w-full items-center gap-2 mt-2"):
                add_type_picker = (
                    ui.select(list(profedit.CONDITION_TYPES_ADDABLE), label=translate_string("Condition Type"))
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
                    ui.select(event_options, label=translate_string("Event Type"), with_input=True)
                    .classes("flex-1")
                    .props("dense")
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
                    ui.select(state_options, label=translate_string("State Type"), with_input=True)
                    .classes("flex-1")
                    .props("dense")
                )
                _mark_unsupported_options(
                    state_type_picker,
                    {row["condition_key"] for row in state_rows if not row["addable"]},
                )
                state_type_picker.bind_visibility_from(add_type_picker, "value", backward=lambda v: v == "State")

                def add_condition_clicked(
                    type_picker: Select = add_type_picker,
                    event_picker: Select = event_type_picker,
                    state_picker: Select = state_type_picker,
                ) -> None:
                    if type_picker.value == "Event":
                        self.event_handlers.add_event_condition_to_profile_event(edited_profile, event_picker.value)
                    elif type_picker.value == "State":
                        self.event_handlers.add_state_condition_to_profile_event(edited_profile, state_picker.value)
                    else:
                        self.event_handlers.add_condition_to_profile_event(edited_profile, type_picker.value)
                    render_conditions()

                ui.button(translate_string("Add Condition"), on_click=add_condition_clicked).props(
                    "flat color=blue dense",
                )

    render_conditions()


def build_edit_profile_dialog(self: MyGui, edited_profile: profedit.EditableProfile) -> None:
    """Builds and opens the Edit Profile dialog: Rename (the Name field is
    read-only -- Rename prompts for a new one and applies it on its own,
    immediately; see build_rename_dialog), Delete Profile, Enabled/Disabled
    toggle, Entry/Exit Task Link/Unlink, and per-condition Add/Edit/Delete
    (see _build_profile_editor_body for the shared body this and
    build_add_profile_dialog both render).

    Built fresh each call rather than reused, since its content is entirely different
    per Profile. Field widgets are kept in a plain dict (matching this file's existing
    ad-hoc widget-ref pattern) and read at Save time rather than using NiceGUI bindings.
    """
    # Imported here rather than at the top of the file: guiwins imports this module, so a
    # module-level import would be a cycle.  See this module's docstring.
    from maptasker.src.guiwins import PendingChangesBanner, build_redact_checkbox, editor_state  # noqa: PLC0415

    profile_name = edited_profile.profile_element.findtext("nme", "")
    field_refs: dict = {}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[500px] max-w-[900px] w-full p-6"):
        # Kept as a local (not in field_refs, which is scanned by key for widgets
        # to read .value off) so Rename can retitle the still-open dialog --
        # see guiwins_taskedit.build_edit_task_dialog's identical note and rename_profile_event.
        title_label = ui.label(f"Edit Profile: {profile_name}").classes("text-xl font-bold text-blue-600")

        # Read-only -- renamed only through the Rename button's prompt; see
        # guiwins_taskedit.build_edit_task_dialog's identical Name field for why.
        field_refs["name"] = (
            ui.input(translate_string("Profile Name"), value=profile_name).props("readonly").classes("w-full")
        )

        _build_profile_editor_body(self, edited_profile, field_refs, dialog)

        field_refs["save_path"] = ui.input(
            translate_string("Save as"),
            value=profedit.default_save_path(profile_name),
        ).classes("w-full mt-2")
        build_redact_checkbox(field_refs)

        # Add/Delete Condition, Link/Unlink Task, the Enabled toggle and a Rename all land on
        # the working copy's element as they happen; every condition's own fields wait in
        # field_refs until a save reads them, as does whatever is sitting picked but not yet
        # linked in an Entry/Exit Task picker (see userintr._link_pending_task_pickers) --
        # which is a pending change too, since a save would apply it.  See guiwins.editor_state.
        pending_changes = PendingChangesBanner()
        pending_changes.watch(dialog, lambda: editor_state(edited_profile.profile_element, field_refs))

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=dialog.close).props("outline")
            delete_profile_button = ui.button(
                translate_string("Delete Profile"),
                on_click=lambda: self.event_handlers.delete_profile_event(edited_profile, dialog),
            ).classes("bg-red-500 text-white")
            with delete_profile_button:
                ui.tooltip(
                    translate_string(
                        "Deletes only this Profile. Its Entry/Exit Tasks are kept -- a Task is owned by "
                        "the Project, not by the Profile, and the same Task can be used by other Profiles.",
                    ),
                )
            rename_profile_button = ui.button(
                translate_string("Rename"),
                on_click=lambda: self.event_handlers.rename_profile_event(edited_profile, field_refs, title_label),
            ).classes("bg-blue-600")
            with rename_profile_button:
                ui.tooltip(
                    translate_string(
                        "Prompts for a new name and applies just that to the loaded backup, right now. "
                        "Everything else in this dialog stays pending until Ok/Save, and the dialog stays "
                        "open so you can carry on editing.",
                    ),
                )
            ui.button(
                translate_string("Ok"),
                on_click=lambda: self.event_handlers.keep_edited_profile_event(edited_profile, field_refs, dialog),
            ).props("outline")
            profile_to_current_file = ui.button(
                translate_string("Save To Current File"),
                on_click=lambda: self.event_handlers.save_edited_profile_to_current_file_event(
                    edited_profile,
                    field_refs,
                    dialog,
                ),
            ).props("outline")
            with profile_to_current_file:
                ui.tooltip(
                    translate_string(
                        "Saves the entire backup -- every Project, Profile and Task in it, not just this Profile -- "
                        "with this dialog's edits applied, the same ones 'Ok' would keep.\n"
                        "It is written to a new, timestamped copy of the file currently loaded: "
                        "backup.xml becomes backup_20260728_143005.xml.\n"
                        "The file you loaded is never written to, so it is left exactly as it was.\n"
                        "The app then switches to the new copy, which becomes the current file for any further "
                        "editing and saving; saving again replaces the timestamp rather than adding a second one.\n"
                        "This writes to this computer only -- nothing is sent to your Android device.",
                    ),
                ).style("white-space: pre-wrap")
            profile_to_android = ui.button(
                translate_string("Save To Android"),
                on_click=lambda: self.event_handlers.open_save_profile_to_android_dialog_event(
                    edited_profile,
                    field_refs,
                    dialog,
                ),
            ).props("outline")
            with profile_to_android:
                ui.tooltip(
                    translate_string(
                        "This will write the Profile as a standalone file onto your Android device, "
                        "under /Tasker/profiles -- it does not import it into Tasker's live configuration.\n\n"
                        "The 'Http Server Example' Tasker Project must be installed and active on the Android "
                        "device, with the server running (see the README's Direct XML Retrieval notes).\n\n"
                        "The Android device must be on the same network, and the IP Address and Port must "
                        "match its Tasker server settings.\n\n"
                        "Watch the Android device while this runs: Tasker asks you to authorize the "
                        "connection several times for one save, and a prompt left untapped fails it.",
                    ),
                ).style("white-space: pre-wrap")
            export = ui.button(
                translate_string("Export Profile"),
                on_click=lambda: self.event_handlers.save_edited_profile_event(edited_profile, field_refs, dialog),
            ).classes("bg-blue-600")
            with export:
                ui.tooltip(
                    translate_string("Saves this Profile as a standalone .prf.xml file on this computer."),
                ).style("white-space: pre-wrap")

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
    # Imported here rather than at the top of the file: guiwins imports this module, so a
    # module-level import would be a cycle.  See this module's docstring.
    from maptasker.src.guiwins import _android_device_fields  # noqa: PLC0415

    with ui.dialog().props("persistent") as android_dialog, ui.card().classes("min-w-[350px] p-6"):
        ui.label(translate_string("Save Profile To Android Device")).classes("text-lg font-bold text-blue-600")
        android_field_refs = _android_device_fields(self)
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=android_dialog.close).props("outline")
            save_to_android = ui.button(
                translate_string("Save As File"),
                on_click=lambda: self.event_handlers.save_profile_to_android_event(
                    edited_profile,
                    field_refs,
                    android_field_refs,
                    android_dialog,
                    parent_dialog,
                ),
            ).props("outline")
            with save_to_android:
                ui.tooltip(
                    translate_string(
                        "This will write the Profile as a standalone file onto the Android device, "
                        "under /Tasker/profiles.\n\n"
                        "The IP Address and Port must match the Android device's Tasker server settings.\n\n"
                        "Watch the Android device while this runs: Tasker asks you to authorize the "
                        "connection several times for one save, and a prompt left untapped fails it.",
                    ),
                ).style("white-space: pre-wrap")
            # The other half of the same dialog, and a genuinely different outcome: 'Save'
            # leaves a file the user can do something with, this one puts the Profile in
            # front of Tasker to be imported.  Two buttons rather than a checkbox because
            # what they produce, what they can fail at and what the user has to do next all
            # differ -- a ticked box would hide all three.
            import_into_tasker = ui.button(
                translate_string("Import Into Tasker"),
                on_click=lambda: self.event_handlers.import_profile_into_tasker_event(
                    edited_profile,
                    field_refs,
                    android_field_refs,
                    android_dialog,
                    parent_dialog,
                ),
            ).classes("bg-blue-600")
            with import_into_tasker:
                ui.tooltip(
                    translate_string(
                        "This copies the Profile to the device and opens Android's 'Open with...' "
                        "chooser for it.  Pick Tasker, and its own import screen comes up; you then tap "
                        "Import to finish -- nothing is imported until you do.\n\n"
                        "The Profile is copied to /Tasker/profiles under its own name first and offered "
                        "from there, so it stays behind under a name you can find -- import it by hand "
                        "from Tasker if the import screen does not come up.  You will be asked before it "
                        "replaces a file already at that path.\n\n"
                        "The 'Http Server Example' Tasker Project must be installed and running, and "
                        "Tasker must be 6.2 or higher.\n\n"
                        "The device will ask you to authorize MapTasker the first time.",
                    ),
                ).style("white-space: pre-wrap")

    android_dialog.open()


def build_delete_profile_dialog(
    self: MyGui,
    edited_profile: profedit.EditableProfile,
    parent_dialog: ui.dialog,
) -> None:
    """Confirms deletion of a Profile. Unlike guiwins.build_delete_project_dialog there is
    no Keep/Delete Contents choice -- a Profile doesn't own its Entry/Exit Tasks
    (see profedit.delete_profile), so they are always kept, and the dialog says so
    explicitly rather than leaving the user to guess what "delete" reaches.

    Saying it is guiwins_impact.build_impact_panel's job, here as in the other three
    Delete dialogs, and it says more than the linked-Task count it replaces: a Task
    this Profile is the only thing that runs is about to be left with nothing running
    it, which is the consequence of deleting a Profile worth knowing before the fact.
    Read live, as that count was, so it cannot go stale while the editor sits open.
    """
    profile_name = edited_profile.profile_element.findtext("nme", "")

    with ui.dialog().props("persistent") as confirm_dialog, ui.card().classes("min-w-[400px] max-w-[600px] w-full p-6"):
        ui.label(f"{translate_string('Delete Profile')} '{profile_name}'").classes("text-lg font-bold text-red-600")
        build_impact_panel(self, PROFILE, profile_name)
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=confirm_dialog.close).props("outline")
            ui.button(
                translate_string("Delete Profile"),
                on_click=lambda: self.event_handlers.confirm_delete_profile_event(
                    profile_name,
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

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[500px] max-w-[900px] w-full p-6"):
        ui.label(translate_string("Add Profile")).classes("text-xl font-bold text-blue-600")

        last_auto_path = {"value": profedit.default_save_path("")}

        def sync_save_path(_e: object = None) -> None:
            # Keep "Save as" in sync with the Profile Name as the user types --
            # see guiwins_taskedit.build_add_task_dialog's identical sync_save_path for why this
            # only overwrites the path while it still holds what was last auto-computed.
            if field_refs["save_path"].value == last_auto_path["value"]:
                new_path = profedit.default_save_path(field_refs["name"].value)
                field_refs["save_path"].value = new_path
                last_auto_path["value"] = new_path

        if target_project_name:
            ui.label(f"{translate_string('Adding to Project:')} {target_project_name}").classes(
                "text-sm text-gray-500 italic",
            )

        field_refs["name"] = ui.input(translate_string("Profile Name"), value="", on_change=sync_save_path).classes(
            "w-full",
        )

        _build_profile_editor_body(self, edited_profile, field_refs, dialog)

        field_refs["save_path"] = ui.input(
            translate_string("Save as"),
            value=last_auto_path["value"],
        ).classes("w-full mt-2")

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=dialog.close).props("outline")
            ui.button(
                translate_string("Ok"),
                on_click=lambda: self.event_handlers.keep_new_profile_event(edited_profile, field_refs, dialog),
            ).props("outline")
            new_profile_to_current_file = ui.button(
                translate_string("Save To Current File"),
                on_click=lambda: self.event_handlers.save_new_profile_to_current_file_event(
                    edited_profile,
                    field_refs,
                    dialog,
                ),
            ).props("outline")
            with new_profile_to_current_file:
                ui.tooltip(
                    translate_string(
                        "Saves the entire backup -- every Project, Profile and Task in it, not just this one -- "
                        "with the new Profile added to its Project, the same way 'Ok' adds it.\n"
                        "It is written to a new, timestamped copy of the file currently loaded: "
                        "backup.xml becomes backup_20260728_143005.xml.\n"
                        "The file you loaded is never written to, so it is left exactly as it was.\n"
                        "The app then switches to the new copy, which becomes the current file for any further "
                        "editing and saving; saving again replaces the timestamp rather than adding a second one.\n"
                        "This writes to this computer only -- nothing is sent to your Android device.",
                    ),
                ).style("white-space: pre-wrap")
            profile_to_android = ui.button(
                translate_string("Save To Android"),
                on_click=lambda: self.event_handlers.open_save_profile_to_android_dialog_event(
                    edited_profile,
                    field_refs,
                    dialog,
                ),
            ).props("outline")
            with profile_to_android:
                ui.tooltip(
                    translate_string(
                        "This will write the Profile as a standalone file onto your Android device, "
                        "under /Tasker/profiles -- it does not import it into Tasker's live configuration.\n\n"
                        "The 'Http Server Example' Tasker Project (http://spoo.me/http_svr_example) must be installed and active on the Android "
                        "device, with the server running (see the README's Direct XML Retrieval notes).\n\n"
                        "The Android device must be on the same network, and the IP Address and Port must "
                        "match its Tasker server settings.\n\n"
                        "Watch the Android device while this runs: Tasker asks you to authorize the "
                        "connection several times for one save, and a prompt left untapped fails it.",
                    ),
                ).style("white-space: pre-wrap")
            export_prof = ui.button(
                translate_string("Export Profile"),
                on_click=lambda: self.event_handlers.save_new_profile_event(edited_profile, field_refs, dialog),
            ).classes("bg-blue-600")
            with export_prof:
                ui.tooltip(
                    translate_string(
                        "Saves this Profile, with all of its conditions and linked Tasks, as one standalone .prf.xml file -- the same format Tasker's own Profile export produces.\n\n"
                        "Tasks the Profile runs are not included; they belong to their own Project.",
                    ),
                ).style("white-space: pre-wrap")

    dialog.open()
