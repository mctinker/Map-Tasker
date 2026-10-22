"""guiwins_props: the Object Properties form.

The property widgets, the variable panel with its checkboxes, and build_object_properties_dialog, which puts them
together for a Project, Profile, Task or Scene."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from maptasker.src.core import objprops
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.gui.guiwins_editor import PendingChangesBanner, editor_state

if TYPE_CHECKING:
    from collections.abc import Callable
    from xml.etree.ElementTree import Element

    from maptasker.src.gui.userintr import MyGui


def _build_property_widget(spec: objprops.PropField, value: str) -> object:
    """One scalar property's widget, per objprops.PropField.kind.

    Every one of them carries Tasker's own wording as its tooltip -- these are settings
    whose names give nothing away ("Collision Handling", "Cooldown Time"), and the
    sentence explaining each is the same one Tasker shows.
    """
    if spec.kind == "checkbox":
        widget = ui.checkbox(translate_string(spec.label), value=value == "true")
    elif spec.kind == "choice":
        widget = ui.select(
            list(spec.choices),
            value=value or spec.choices[0],
            label=translate_string(spec.label),
        ).classes("w-full")
    elif spec.kind == "slider":
        # Number rather than a bare slider: the value has to be readable and typeable,
        # and a 0-50 slider alone gives no way to land on an exact one.
        widget = ui.number(
            translate_string(spec.label),
            value=int(value) if value.isdigit() else None,
            min=0,
            max=spec.maximum,
            format="%.0f",
        ).classes("w-full")
    elif spec.kind == "number":
        # The slider's widget without the ceiling: a repeat count has no maximum Tasker
        # documents, and 0-50 is Launch Task Priority's range rather than a shared one.
        # Empty means "no value", which is what removes the tag -- see PropField.default.
        widget = ui.number(
            translate_string(spec.label),
            value=int(value) if value.isdigit() else None,
            min=0,
            format="%.0f",
        ).classes("w-full")
    elif spec.kind == "duration":
        widget = ui.input(
            f"{translate_string(spec.label)} ({objprops.COOLDOWN_FORMAT})",
            value=objprops.format_cooldown(value),
        ).classes("w-full")
    else:
        widget = ui.input(translate_string(spec.label), value=value).props("autogrow").classes("w-full")

    if spec.tooltip:
        with widget:
            ui.tooltip(translate_string(spec.tooltip)).style("white-space: pre-wrap; max-width: 32rem")
    return widget


# The three checkboxes on a variable, with the explanations Tasker itself gives for them
# -- transcribed from the Project Variables help screens (Properties1.png/Properties2.png).
# Kept together because all three are the same shape and the wording is the point.
_VARIABLE_CHECKBOXES: tuple[tuple[str, str, str], ...] = (
    (
        "pvci",
        "Configure On Import",
        (
            "If you enable the option to configure on import you need to fill in a question that the "
            "user will be asked when importing this into Tasker.  The value of this variable will "
            "also be cleared when you export it so that private data is not mistakenly sent to other "
            "users."
        ),
    ),
    (
        "strout",
        "Structured Variables (JSON, etc)",
        (
            "Enable the 'Structured Variable' option if the variable is either JSON, HTML or XML so "
            "that you can easily read its contents via the dot or square brackets notations.\n"
            "For example if there's a %json variable and its contents are in the JSON format you "
            "could use '%json.info' or '%json[info]' to get the value for the 'info' field."
        ),
    ),
    (
        "immutable",
        "Immutable",
        (
            "If you enable the 'Immutable' option, the variable can be changed in Tasks, but will "
            "reset to the value here when the Task ends."
        ),
    ),
)


def _build_variable_panel(
    props: objprops.EditableProperties,
    index: int,
    variable: Element,
    field_refs: dict,
    rerender: Callable[[], None],
) -> None:
    """One <ProfileVariable>, as an expansion titled by its name.

    Field order follows Tasker's own, which is the order property.py already prints them
    in on the read side: Type, Name, the three checkboxes, then Value / Display Name /
    Prompt, then Exported Value with "Same as Value" beside it.
    """
    values = objprops.variable_values(variable)
    key = lambda field: f"var{index}_{field}"

    title = objprops.variable_display_name(variable) or translate_string("(new variable)")
    with ui.expansion(title, icon="data_object", value=not values["pvn"]).classes("w-full"):
        # Codes are what the XML holds, labels are what a person can pick -- so a
        # {code: label} select, sorted by label.  A code this build does not know about
        # (a newer Tasker type) is added to the options as itself rather than dropped,
        # so opening and closing this panel cannot silently retype the variable.
        options = dict(sorted(objprops.VARIABLE_TYPES.items(), key=lambda pair: pair[1]))
        if values["pvt"] and values["pvt"] not in options:
            options[values["pvt"]] = values["pvt"]
        field_refs[key("pvt")] = ui.select(
            options,
            value=values["pvt"] or objprops.DEFAULT_VARIABLE_TYPE,
            label=translate_string("Type"),
        ).classes("w-full")

        field_refs[key("pvn")] = ui.input(translate_string("Name"), value=values["pvn"]).classes("w-full")

        for tag, label, tooltip in _VARIABLE_CHECKBOXES:
            field_refs[key(tag)] = ui.checkbox(translate_string(label), value=values[tag] == "true")
            with field_refs[key(tag)]:
                ui.tooltip(translate_string(tooltip)).style("white-space: pre-wrap; max-width: 32rem")

        field_refs[key("pvv")] = ui.input(translate_string("Value"), value=values["pvv"]).classes("w-full")
        field_refs[key("pvdn")] = ui.input(translate_string("Display Name"), value=values["pvdn"]).classes("w-full")
        field_refs[key("pvd")] = ui.input(translate_string("Prompt"), value=values["pvd"]).classes("w-full")

        with ui.row().classes("w-full items-center gap-2"):
            exported = ui.input(translate_string("Exported Value"), value=values["exportval"]).classes("flex-1")
            same_as_value = ui.checkbox(
                translate_string("Same as Value"),
                value=values["same_as_value"] == "true",
            )
            field_refs[key("exportval")] = exported
            field_refs[key("same_as_value")] = same_as_value
            with same_as_value:
                ui.tooltip(
                    translate_string(
                        "Under 'Exported Value' if you disable the 'Same as Value' option, you can "
                        "customize what value gets exported when you share the variable with other "
                        "users.\n"
                        "You can keep the 'Exported Value' field blank if you want the export to not "
                        "have a value at all, or you can set the value you wish to always use for "
                        "exports.\n"
                        "If you enable the 'Same as Value' option, the current variable value will be "
                        "used when exporting.",
                    ),
                ).style("white-space: pre-wrap; max-width: 32rem")

            # "Same as Value" is derived rather than stored -- Tasker just writes
            # <exportval> equal to <pvv> (see objprops.variable_values).  Mirroring here,
            # and disabling the field while it is on, is what keeps the two from being
            # made to disagree on screen and then disagreeing again in the XML.
            def mirror() -> None:
                exported.set_enabled(not same_as_value.value)
                if same_as_value.value:
                    exported.value = field_refs[key("pvv")].value

            same_as_value.on_value_change(mirror)
            field_refs[key("pvv")].on_value_change(mirror)
            mirror()

        ui.button(
            translate_string("Remove Variable"),
            icon="delete",
            on_click=lambda: (objprops.remove_variable(props, index), rerender()),
        ).props("flat dense color=negative")


def build_object_properties_dialog(
    self: MyGui,
    kind: str,
    element: Element,
    _parent_dialog: ui.dialog | None,
    on_applied: Callable[[], None] | None = None,
) -> None:
    """The Properties editor, shared by every Add/Edit dialog -- see the section comment.

    Opens OVER the parent, which stays open behind it: the parent still owns the save,
    and closing it out from under the user would lose whatever else they had typed into
    it.  Ok applies onto `element` and closes; Cancel closes, writes nothing, and drops
    any variable that was added but never named (objprops.discard_unnamed_variables --
    Add Variable puts a real element on straight away, the way every other structural
    edit in this app does).
    """
    props = objprops.load_properties(kind, element)
    field_refs: dict = {}
    values = objprops.scalar_values(props)

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[560px] max-w-[860px] w-full p-6"):
        ui.label(f"{translate_string(kind)} {translate_string('Properties')}").classes(
            "text-xl font-bold text-blue-600",
        )

        for spec in objprops.OBJECT_PROPERTIES.get(kind, ()):
            field_refs[spec.key] = _build_property_widget(spec, values[spec.key])

        ui.label(translate_string(f"{kind} Variables")).classes("text-sm font-bold mt-4")
        ui.label(
            translate_string(
                "The variables you add here will be available in all the profiles and tasks in this "
                "project but will not be available in other projects."
                if kind == objprops.KIND_PROJECT
                else "If there are multiple project/profile/task variables with the same name available "
                "in the same task, the inner-most variable will take precedence.  The order of "
                "precedence is Task > Profile > Project.",
            ),
        ).classes("text-xs text-gray-500 italic")

        variables_container = ui.column().classes("w-full")

        def render_variables() -> None:
            # Rebuilt from scratch after every Add/Remove, not appended to: removing a
            # variable renumbers every one after it, so its field_refs keys (which embed
            # the index) would otherwise go stale and a save would read the wrong panel's
            # values into it.  Same reason guiwins_taskedit.build_edit_task_dialog rebuilds its actions.
            variables_container.clear()
            for stale in [name for name in field_refs if name.startswith("var")]:
                del field_refs[stale]
            with variables_container:
                if not props.variables:
                    ui.label(translate_string("No variables.")).classes("text-xs text-gray-500 italic")
                for index, variable in enumerate(props.variables):
                    _build_variable_panel(props, index, variable, field_refs, render_variables)

        render_variables()

        ui.button(
            translate_string("Add Variable"),
            icon="add",
            on_click=lambda: (objprops.add_variable(props), render_variables()),
        ).props("flat dense")

        # Everything a change here can be in is either the element -- which Add/Remove
        # Variable write to as they happen -- or a widget in field_refs, where the scalars
        # and every variable field wait until Ok reads them.  See editor_state.
        pending_changes = PendingChangesBanner()
        pending_changes.watch(dialog, lambda: editor_state(props.element, field_refs))

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(
                translate_string("Cancel"),
                on_click=lambda: self.event_handlers.cancel_object_properties_event(props, dialog),
            ).props("outline")
            ui.button(
                translate_string("Ok"),
                on_click=lambda: self.event_handlers.keep_object_properties_event(
                    props,
                    field_refs,
                    dialog,
                    on_applied,
                ),
            ).classes("bg-blue-600")

    dialog.open()
