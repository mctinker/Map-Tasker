"""The widgets that edit one argument of a Legacy Scene element: text, number, choice and colour fields."""

#! /usr/bin/env python3

#                                                                                        #
# guiwins_legacyarg: render one <Arg> of a Legacy Scene element as the field that edits it.        #
#                                                                                        #
# Both the Legacy designer (an element's own arguments) and the Scene Properties dialog (the        #
# Scene's) draw their fields with this, and the designer also opens that dialog -- so while it      #
# lived in the designer, each of them had to reach the other from inside a function.  Here it       #
# stands below both, and neither is imported by it.                                                  #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                              #
#
from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import Event, ui

from maptasker.src import sceneedit_legacy, taskedit
from maptasker.src.guiwins_canvas import FIELD_COMMIT_DEBOUNCE_MS
from maptasker.src.guiwins_taskedit import _dropdown_current_label
from maptasker.src.maputil2 import translate_string
from maptasker.src.primitem import PrimeItems

if TYPE_CHECKING:
    from collections.abc import Callable


def _render_legacy_colour_arg(arg: taskedit.EditableArg, commit: Callable[[Event], None]) -> None:
    """A Legacy element's colour: the same picker the V2 designer's colours use, over a value
    written the other way round.

    Tasker stores #AARRGGBB and every colour picker there is speaks #RRGGBBAA, so the field
    shows the converted value and converts back before committing (see
    sceneedit_legacy.legacy_colour_to_css, which is where that ordering is explained).  The picker
    itself is put into "hexa" so it returns the alpha rather than dropping it -- a Scene's
    "#77333333" is a deliberately half-transparent grey, and a picker that answered in plain
    #RRGGBB would quietly make it opaque.

    The committed value is re-shown afterwards.  A pick of an opaque colour comes back as
    eight digits, which stores as #FFRRGGBB and reads back out as six -- so writing that form
    into the field is what lets the swatch preview it.  That write is its own change event,
    which `settling` swallows: it would otherwise commit the identical colour a second time
    and repaint the canvas for it.
    """
    settling = {"busy": False}

    def commit_colour(event: Event) -> None:
        if settling["busy"]:
            return
        stored = sceneedit_legacy.legacy_colour_from_css(str(event.value or ""))
        event.value = stored
        commit(event)
        settling["busy"] = True
        try:
            field.value = sceneedit_legacy.legacy_colour_to_css(stored)
        finally:
            settling["busy"] = False

    field = (
        ui.color_input(
            label=translate_string(arg.arg_name),
            value=sceneedit_legacy.legacy_colour_to_css(arg.current_value),
            preview=True,
            on_change=commit_colour,
        )
        .props(f"dense debounce={FIELD_COMMIT_DEBOUNCE_MS}")
        .classes("flex-1")
    )
    field.picker.q_color.props('format-model="hexa"')


def _render_legacy_arg(
    arg: taskedit.EditableArg,
    on_applied: Callable[[], None],
    on_rename: Callable[[], None] | None = None,
    *,
    name_editable: bool = False,
) -> None:
    """One property field, rendered from the same EditableArg model the Task editor uses --
    so a dropdown, a checkbox and a variable-backed field look and behave identically
    wherever they appear in this app.

    Written through on change rather than collected at save time, matching the V2 designer:
    the inspector's widgets are destroyed on every selection change, so there would be
    nothing left to collect from.  Cancel still discards everything, because all of this is
    happening to the dialog's own deep copy of the Scene.

    `on_applied` RUNS WHILE THE FIELD STILL HAS FOCUS, and must therefore not rebuild the
    container these widgets are in -- it would destroy the one being typed into mid-word.  The
    designer passes its repaint(), which redraws the canvas and leaves the forms alone; see
    that function, which is where this used to go wrong.

    THE NAME FIELD IS THE EXCEPTION, and which exception depends on whose name it is:

      * A top-level element's name is what 18 Task action codes look it up by, so it is not
        typed into.  It gets a Rename button (`on_rename`) that opens a dialog naming what
        depends on the current name first -- see _build_rename_legacy_element_dialog.

      * A sub-element's name -- a background RectElement's, a PropertiesElement's -- is
        addressed by nothing at all: Tasker reaches those through their owner and their sr,
        never by name.  Those pass `name_editable` and are typed into like any other field.
    """
    is_name = arg.arg_id == "0" and arg.backing_tag == "Str" and not name_editable

    def commit(event: Event) -> None:
        value = event.value
        if arg.widget_kind == "checkbox":
            value = "1" if value else "0"
        errors = sceneedit_legacy.legacy_validate_arg(arg, str(value))
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return
        sceneedit_legacy.legacy_set_arg(arg, str(value), state=PrimeItems)
        on_applied()

    with ui.row().classes("w-full items-center gap-2"):
        if is_name:
            ui.input(translate_string(arg.arg_name), value=arg.current_value).props("readonly dense").classes("flex-1")
            rename_button = ui.button(
                translate_string("Rename"),
                icon="drive_file_rename_outline",
                on_click=lambda: on_rename() if on_rename else None,
            ).props("dense flat size=sm")
            rename_button.set_enabled(on_rename is not None)
            with rename_button:
                ui.tooltip(
                    translate_string(
                        "Tasks address this element by name (Element Text, Element Position, ... 18 "
                        "action codes in all), so renaming it is not a field edit. The Rename dialog "
                        "lists what depends on the current name and offers to bring those Tasks along.",
                    ),
                ).style("white-space: pre-wrap")
        elif arg.widget_kind == "checkbox":
            ui.checkbox(translate_string(arg.arg_name), value=arg.current_value == "1", on_change=commit)
        elif arg.widget_kind == "dropdown":
            ui.select(
                arg.dropdown_options or [],
                value=_dropdown_current_label(arg),
                label=translate_string(arg.arg_name),
                on_change=commit,
            ).props("dense").classes("flex-1")
        elif arg.widget_kind == "readonly":
            ui.input(translate_string(arg.arg_name), value=arg.current_value).props("readonly dense").classes("flex-1")
            if arg.readonly_note:
                ui.label(translate_string(arg.readonly_note)).classes("text-xs text-gray-500 italic")
        elif sceneedit_legacy.legacy_is_colour_arg(arg):
            _render_legacy_colour_arg(arg, commit)
        else:  # "text" and "raw_fallback"
            # Debounced, unlike the checkbox and the dropdown above: those commit one whole
            # value per click, while this one is typed a character at a time.  See
            # FIELD_COMMIT_DEBOUNCE_MS, and repaint() for why the commit no longer takes the
            # caret with it either way.
            ui.input(translate_string(arg.arg_name), value=arg.current_value, on_change=commit).props(
                f"dense debounce={FIELD_COMMIT_DEBOUNCE_MS}",
            ).classes("flex-1")
