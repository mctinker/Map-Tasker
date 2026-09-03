"""The Version 2 Scene designer: the element tree, the property sheet and their pickers.

Split out of guiwins.py, which had grown to 14,500 lines.  Everything a Version 2 Scene is
edited through lives here -- _build_v2_designer itself, the Add Element sheet, the Show When
picker, and the colour/icon/state property fields the sheet is built out of.

The canvas underneath it is in guiwins_canvas, which the Legacy designer stands on as well;
nothing here is imported by guiwins_designer_legacy, and nothing here reaches back into
guiwins.
"""

from __future__ import annotations

import collections
import contextlib
import copy
from typing import TYPE_CHECKING

from nicegui import ui

from maptasker.src import sceneedit, sceneview
from maptasker.src.guiwins_canvas import (
    _ACTIVE_CANVASES,
    _DESIGNER_SEQUENCE,
    _emit_v2_dragging,
    _register_canvas_events,
    _v2_selection_props,
)
from maptasker.src.maputil2 import translate_string
from maptasker.src.primitem import PrimeItems

if TYPE_CHECKING:
    from collections.abc import Callable


def _build_add_element_dialog(layout: dict, path: tuple, on_pick: Callable[[str], None]) -> None:
    """Tasker's own "Add Element" sheet, as a dialog: a search box, then every element the
    palette offers as a chip, grouped and named the way the Screen Builder groups and names
    them (see sceneedit.V2_PALETTE -- "Vertical Column", not "Column").

    Replaces the cascading Add menu this used to be, because a menu can do only one of the
    three things this needs.  It can list types; it cannot describe them, and it cannot show
    an element that is *visible but not addable here* -- the old menu let you pick a
    Navigation Item anywhere and reported the mistake afterwards, as a notification, once
    the chance to explain had passed.

    Nothing here reasons about the tree.  Which elements exist, which are blocked, and why,
    all come from sceneedit.v2_palette_for; this renders the answer.

    Blocked chips stay clickable rather than being disabled.  A disabled Quasar button eats
    its own tooltip, so disabling would hide the very sentence that explains the block; a
    click on one notifies the reason instead of inserting.
    """
    relation, target_name = sceneedit.v2_insert_destination(layout, path)
    groups = sceneedit.v2_palette_for(layout, path)
    search = {"text": ""}

    def tooltip_for(entry: sceneedit.V2PaletteEntry, reason: str) -> str:
        lines = [translate_string(entry.description)]
        if reason:
            lines.append(reason)
        if not entry.verified:
            lines.append(
                translate_string(
                    "Tasker lists this element, but MapTasker has never seen one in a saved Scene -- "
                    "so it is added carrying nothing but its type and id, and even the type is inferred "
                    'from the name above (written as type: "{node_type}"). '
                    "If Tasker doesn't recognise it, press Undo.",
                ).format(node_type=entry.node_type),
            )
        return "\n\n".join(lines)

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[640px] max-w-[760px] p-6"):
        ui.label(translate_string("Add Element")).classes("text-lg font-bold text-blue-600")
        if target_name:
            # The destination stated up front rather than left to a tooltip -- this is
            # v2_insert_node's inside-vs-after rule, resolved against the current selection.
            ui.label(
                translate_string("Adds inside {name}" if relation == "inside" else "Adds after {name}").format(
                    name=target_name,
                ),
            ).classes("text-sm text-gray-500 italic")

        def pick(entry: sceneedit.V2PaletteEntry, reason: str) -> None:
            if reason:
                ui.notify(reason, type="warning")
                return
            dialog.close()
            on_pick(entry.node_type)

        def matches(entry: sceneedit.V2PaletteEntry) -> bool:
            """Substring, case-insensitive, over the label, its translation and the JSON
            type -- so "row" finds Horizontal Row, and someone who knows the format can
            still type "FlowRow" and get there.
            """
            text = search["text"].strip().lower()
            if not text:
                return True
            return any(
                text in candidate.lower() for candidate in (entry.label, translate_string(entry.label), entry.node_type)
            )

        def chip(entry: sceneedit.V2PaletteEntry, reason: str) -> None:
            # The icon and colour go on as Quasar props rather than as ui.button arguments:
            # ui.button takes `icon` but has no icon_right, and the colour is state-dependent
            # (grey = blocked, orange = unverified, default otherwise).
            props = ["outline", "rounded", "no-caps", "dense"]
            props.append("icon-right=help_outline" if not entry.verified else "icon-right=info_outline")
            if reason:
                props.append("color=grey")
            elif not entry.verified:
                props.append("color=orange")
            button = ui.button(
                translate_string(entry.label),
                on_click=lambda _e=None, x=entry, r=reason: pick(x, r),
            ).props(" ".join(props))
            if reason:
                button.classes("opacity-70")
            with button:
                ui.tooltip(tooltip_for(entry, reason)).style("white-space: pre-wrap").classes("max-w-sm")

        # Created before `results` because NiceGUI lays widgets out in creation order, and the
        # search box belongs above the chips it filters.  Its on_change closes over
        # search_changed, which is defined below -- resolved at call time, not at creation.
        search_input = (
            ui.input(placeholder=translate_string("Search elements"), on_change=lambda e: search_changed(e.value))
            .props("outlined dense clearable autofocus")
            .classes("w-full mt-2")
        )
        with search_input.add_slot("prepend"):
            ui.icon("search")

        results = ui.column().classes("w-full gap-0 mt-1 max-h-96 overflow-auto")

        def render() -> None:
            results.clear()
            shown = 0
            with results:
                for group, entries in groups:
                    visible = [(entry, reason) for entry, reason in entries if matches(entry)]
                    if not visible:
                        continue
                    shown += len(visible)
                    ui.label(translate_string(group)).classes("text-xs uppercase text-blue-400 mt-3 mb-1")
                    with ui.row().classes("w-full gap-2 flex-wrap"):
                        for entry, reason in visible:
                            chip(entry, reason)
                if not shown:
                    ui.label(translate_string("No element matches that.")).classes(
                        "text-sm italic text-gray-500 mt-3",
                    )

        def search_changed(value: str) -> None:
            search["text"] = value or ""
            render()

        def enter_pressed() -> None:
            """Enter picks the search's one remaining match -- the fast path for someone who
            knows what they want.  Deliberately silent when the search still matches several
            elements: guessing which of them was meant would insert the wrong component.
            """
            hits = [(entry, reason) for _group, entries in groups for entry, reason in entries if matches(entry)]
            if len(hits) == 1:
                pick(*hits[0])

        search_input.on("keydown.enter", lambda _e=None: enter_pressed())

        render()

        with ui.row().classes("w-full items-center justify-between mt-4 pt-3 border-t"):
            ui.label(
                translate_string(
                    "Amber: Tasker lists it, but MapTasker has no confirmed sample of it. "
                    "Grey: can't go where the selection would put it.",
                ),
            ).classes("text-xs text-gray-500 italic")
            ui.button(translate_string("Cancel"), on_click=dialog.close).props("flat")

    dialog.open()


# How many entries of one category the Show When picker lists before it stops and asks for a
# search.  User Globals runs to several hundred on a real backup and Built-in Globals is a
# hundred on any backup; drawing all of them makes a dialog nobody can read and a page that
# takes a visible moment to build.  Forty is enough to browse a category and see what kind of
# thing is in it, which is what an unsearched list is for.
_SHOW_WHEN_PREVIEW_LIMIT = 40


def _build_show_when_dialog(
    field: ui.input,
    groups: list[tuple[str, list[sceneedit.V2ShowWhenChoice]]] | None = None,
    title: str = "Insert into Show When",
) -> None:
    """The Show When picker: choose variables to build the condition out of, from the three
    categories in sceneedit.v2_show_when_choices -- the Screen Builder's own environment
    values, the loaded backup's own global variables, and Tasker's built-in globals.

    Appends rather than replaces, and stays open after a pick, because a Show When is an
    expression and usually wants more than one: "%sv2_render_width > %sv2_display_width / 2"
    is two picks and some typing.  Writing through `field.value` rather than onto the node
    directly is what keeps the inspector's own on_change in charge of storing it, so this
    needs to know nothing about the component being edited.

    `groups` and `title` are what let a Dynamic state field reuse all of this: the same
    insert, search and caret handling over a shorter list (no operators -- see
    sceneedit.v2_dynamic_variable_choices), under its own heading.
    """
    groups = sceneedit.v2_show_when_choices() if groups is None else groups
    search = {"text": ""}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[620px] max-w-[740px] p-6"):
        ui.label(translate_string(title)).classes("text-lg font-bold text-blue-600")
        ui.label(
            translate_string("What you pick goes in at the cursor. Open this again to add the next piece."),
        ).classes("text-sm text-gray-500 italic")

        # Reaching the field's native <input>.  getHtmlElement() hands back whatever element
        # carries the NiceGUI id, and for ui.input that IS the <input> -- not a wrapper around
        # one -- so this has to cope with both rather than assuming a wrapper to search
        # inside.  (Assuming the wrapper is exactly the bug this replaced: querySelector found
        # nothing, every read came back null, and every pick silently fell back to the end.)
        _native_input = (
            f"const el = (() => {{ const r = getHtmlElement({field.id});"
            f" return r && r.matches('input, textarea') ? r : r && r.querySelector('input, textarea'); }})();"
        )

        async def caret_position() -> int | None:
            """Where the cursor is sitting in the Show When field, asked of the browser.

            It has to be asked for rather than remembered: the caret lives in the DOM, and
            NiceGUI's own value binding knows nothing about it.  Asking while this dialog has
            focus still works -- a blurred input keeps its selection.  None (a field never
            clicked into, or a browser that declines) means "the end", which is what
            v2_insert_show_when does with it.
            """
            with contextlib.suppress(Exception):
                return await ui.run_javascript(
                    f"(() => {{ {_native_input} return el ? el.selectionStart : null; }})()",
                    timeout=3.0,
                )
            return None

        async def pick(choice: sceneedit.V2ShowWhenChoice) -> None:
            text, caret = sceneedit.v2_insert_show_when(
                str(field.value or ""),
                choice.value,
                await caret_position(),
            )
            field.value = text
            # Put the caret back where the insert left it, so re-opening the picker adds the
            # next piece after this one rather than back at the same spot.
            with contextlib.suppress(Exception):
                ui.run_javascript(
                    f"(() => {{ {_native_input} if (el) {{ el.setSelectionRange({caret}, {caret}); }} }})()",
                )
            # Close on the pick.  A condition is built out of several of these, so staying
            # open to save a click is the obvious thing to do and the wrong one: the dialog
            # covers the very field it is filling in, so every pick landed unseen and there
            # was no way to check the expression without dismissing the picker anyway.
            # Closing shows the result, which is what makes the next pick an informed one.
            dialog.close()

        def matches(choice: sceneedit.V2ShowWhenChoice) -> bool:
            text = search["text"].strip().lower()
            return not text or text in choice.label.lower() or text in choice.value.lower()

        # Created before `results`: NiceGUI lays widgets out in creation order, and a search
        # box below the list it filters is a search box nobody finds.  Its on_change closes
        # over search_changed, defined below and resolved at call time.
        search_input = (
            ui.input(placeholder=translate_string("Search variables"), on_change=lambda e: search_changed(e.value))
            .props("outlined dense clearable autofocus")
            .classes("w-full mt-2")
        )
        with search_input.add_slot("prepend"):
            ui.icon("search")

        results = ui.column().classes("w-full gap-0 mt-1 max-h-96 overflow-auto")

        def render() -> None:
            results.clear()
            with results:
                for group, choices in groups:
                    visible = [choice for choice in choices if matches(choice)]
                    ui.label(f"{translate_string(group)} ({len(visible)})").classes(
                        "text-xs uppercase text-blue-400 mt-3 mb-1",
                    )
                    if not visible:
                        ui.label(translate_string("Nothing here.")).classes("text-sm italic text-gray-500")
                        continue
                    with ui.row().classes("w-full gap-2 flex-wrap"):
                        for choice in visible[:_SHOW_WHEN_PREVIEW_LIMIT]:
                            button = ui.button(
                                choice.label,
                                on_click=lambda _e=None, c=choice: pick(c),
                            ).props("outline rounded no-caps dense")
                            if choice.label != choice.value:
                                # Only the named entries need this -- a user global is
                                # already showing the exact text it inserts.
                                with button:
                                    ui.tooltip(choice.value)
                    if len(visible) > _SHOW_WHEN_PREVIEW_LIMIT:
                        ui.label(
                            translate_string("...and {count} more -- type above to narrow it down.").format(
                                count=len(visible) - _SHOW_WHEN_PREVIEW_LIMIT,
                            ),
                        ).classes("text-xs text-gray-500 italic mt-1")

        def search_changed(value: str) -> None:
            search["text"] = value or ""
            render()

        render()

        with ui.row().classes("w-full justify-end mt-4 pt-3 border-t"):
            ui.button(translate_string("Close"), on_click=dialog.close).props("flat")

    dialog.open()


# How big the swatch beside a Version 2 colour field is, and in the menu beside each Material
# role.  Small enough to sit inside a dense field, big enough to tell two greys apart.
_V2_SWATCH_STYLE = (
    "width: 18px; height: 18px; border-radius: 3px; flex: none;"
    "border: 1px solid rgba(120,120,120,0.55); box-sizing: border-box;"
)

# A glyph for each of sceneedit.V2_TEXT_CATEGORIES, so a closed section is recognisable at a
# glance rather than being one of eight identical grey bars.  Here rather than beside the
# categories themselves because what a section is called is the Scene's business and what it
# looks like is this pane's.  A category with no entry falls back to the Modifiers section's
# own "tune", which is what a group of settings looks like everywhere else in this designer.
_V2_CATEGORY_ICONS: dict[str, str] = {
    "General": "settings",
    "Content": "short_text",
    "Appearance": "palette",
    "Behavior": "rule",
    "Font": "text_fields",
    "Spacing": "format_line_spacing",
    "Decoration and effects": "auto_fix_high",
    "Paragraph": "notes",
    "Other": "more_horiz",
}


def _variable_picker_button(field: ui.input, label: str) -> None:
    """The Select Variable half of a property that can either be filled in or pointed at a
    variable -- a Text's own text, a max lines of %line_budget, a shadow the theme decides.

    Only the button.  Which slot it goes in is the caller's, because ui.color_input arrives
    with an append slot already holding its wheel: adding one there takes the wheel away (see
    _build_colour_field), so a colour field has to put this *into* that slot instead.

    Writes through `field.value`, so the field's own on_change is still what stores it and this
    knows nothing about the component being edited -- the same division the Show When picker
    and the state fields' own variable box keep to.
    """
    picker = ui.button(
        icon="playlist_add",
        on_click=lambda _e=None: _build_show_when_dialog(
            field,
            sceneedit.v2_dynamic_variable_choices(),
            f"Select a variable for {label}",
        ),
    ).props("flat dense round size=sm")
    with picker:
        ui.tooltip(translate_string("Pick from the Scene's environment and global variables."))


def _build_colour_field(item: dict, prop: sceneedit.V2Prop) -> None:
    """A Version 2 colour property: type a name or a #hex value, pick one off the wheel, or
    take one of Material's own roles from the menu.  A "colorvar" property adds a fourth way --
    point it at a variable and let the phone decide.

    The three ways matter because a V2 Scene's colours are of two kinds.  Most are ordinary
    values -- "#64B5F6", "red" -- and those want the wheel.  But Tasker also writes *role*
    names ("onPrimaryFixed", "surfaceContainerHigh"), which are not colours at all until the
    phone resolves them against its own theme, and which no colour wheel can offer because
    picking the swatch they happen to look like here would store the wrong thing entirely.
    Picking one from the menu stores the name, which is the whole point of naming it.

    The swatch is drawn here rather than through ui.color_input's own `preview`, which knows
    only hex: this one shows what a role name and an HTML colour name look like too, and goes
    blank -- rather than misleading -- for a %variable or a spelling this app cannot resolve.

    What the field does NOT do is refuse a value it doesn't recognise.  It marks it (Quasar's
    own error state, so it reads as a warning rather than a rejection) and stores it anyway:
    the Scene belongs to the user, the property may well be one a newer Tasker understands,
    and silently dropping what they typed would be worse than showing it in red.
    """
    field = (
        ui.color_input(
            label=translate_string(prop.label),
            value=str(item.get(prop.key, "")),
            on_change=lambda e, k=prop.key, d=item: colour_changed(d, k, str(e.value or "")),
        )
        .props("dense")
        .classes("w-full")
    )
    with field.add_slot("prepend"):
        swatch = ui.element("div").style(_V2_SWATCH_STYLE)
    # Into the append slot ui.color_input already made, NOT a fresh one: add_slot REPLACES a
    # slot of the same name, and the slot this field arrives with is the one holding its
    # colour wheel.  Making a new one here takes the wheel away, which is the opposite of
    # what this button is for -- the roles are offered *as well as* the wheel, not instead.
    with field.slots["append"]:
        palette_button = ui.button(icon="palette").props("flat dense round size=sm")
        with palette_button:
            ui.tooltip(translate_string("Pick one of Material's own colour roles."))
            _build_material_colour_menu(field)
        if prop.kind == "colorvar":
            _variable_picker_button(field, prop.label)

    def colour_changed(node: dict, key: str, text: str) -> None:
        sceneedit.v2_set_prop(node, key, text)
        resolved = sceneview.v2_swatch_colour(text)
        swatch.style(f"background: {resolved or 'transparent'};")
        if sceneedit.v2_is_colour(text):
            field.props(remove="error")
        else:
            message = translate_string("Not an HTML colour name or #hex value.")
            field.props(f'error error-message="{message}"')

    colour_changed(item, prop.key, str(item.get(prop.key, "")))


# How many icons the picker draws before it stops and asks for a search.  Same bargain the
# Show When picker strikes at _SHOW_WHEN_PREVIEW_LIMIT, at a size that suits a grid of glyphs:
# enough to browse and see what kind of thing is in there, not so many that opening the dialog
# builds several hundred widgets nobody scrolled to.
_ICON_PREVIEW_LIMIT = 120


def _build_icon_field(item: dict, prop: sceneedit.V2Prop) -> None:
    """A Version 2 icon property: type a reference, or pick a Material icon by its picture.

    Typed into as well as picked from, because an icon reference is not only ever a Material
    name -- a Scene can point at a Material Symbol ("symbol:cloud_upload;opsz:24") or at an
    installed app's own icon, and neither is something this picker can offer.  What is typed
    is stored exactly as typed.

    The glyph on the left is the field showing its own value back: it resolves all three forms
    through the same sceneview.v2_icon the preview draws by, so what is in the field and what
    the component will show are the same answer.
    """
    field = (
        ui.input(
            translate_string(prop.label),
            value=str(item.get(prop.key, "")),
            on_change=lambda e, k=prop.key, d=item: icon_changed(d, k, str(e.value or "")),
        )
        .props("dense")
        .classes("w-full")
    )
    with field.add_slot("prepend"):
        glyph = ui.icon("").style("font-size: 22px;")
    with field.add_slot("append"):
        pick_button = ui.button(
            icon="apps",
            on_click=lambda _e=None, w=field: _build_icon_dialog(w),
        ).props("flat dense round size=sm")
        with pick_button:
            ui.tooltip(translate_string("Pick a Material icon."))

    def icon_changed(node: dict, key: str, text: str) -> None:
        sceneedit.v2_set_prop(node, key, text)
        glyph.name = sceneview.v2_icon(text)

    icon_changed(item, prop.key, str(item.get(prop.key, "")))


def _build_icon_dialog(field: ui.input) -> None:
    """The Material icon picker: a grid of the glyphs themselves, because an icon is chosen by
    looking at it -- "AcUnit" is a snowflake, and nobody browses a list of names for that.

    The name goes under each glyph anyway.  It is what gets stored (sceneedit
    .v2_icon_reference turns "ac_unit" into "icon:AcUnit"), and two icons that look alike at
    22px are told apart by it.

    Replaces the field rather than inserting into it, unlike the Show When picker: a component
    has one icon, so a second pick is a correction and not an addition.
    """
    names = sceneedit.v2_icon_names()
    search = {"text": ""}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[640px] max-w-[760px] p-6"):
        ui.label(translate_string("Pick an icon")).classes("text-lg font-bold text-blue-600")
        ui.label(
            translate_string("What you pick replaces what the field holds. Type to narrow the list down."),
        ).classes("text-sm text-gray-500 italic")

        def pick(name: str) -> None:
            field.set_value(sceneedit.v2_icon_reference(name))
            dialog.close()

        search_input = (
            ui.input(placeholder=translate_string("Search icons"), on_change=lambda e: search_changed(e.value))
            .props("outlined dense clearable autofocus")
            .classes("w-full mt-2")
        )
        with search_input.add_slot("prepend"):
            ui.icon("search")

        results = ui.column().classes("w-full gap-1 mt-2 max-h-96 overflow-auto")

        def render() -> None:
            results.clear()
            text = search["text"].strip().lower().replace(" ", "_")
            visible = [name for name in names if text in name] if text else names
            with results:
                if not names:
                    ui.label(
                        translate_string("The Material icon list could not be read, so type the name instead."),
                    ).classes("text-sm italic text-orange-600")
                    return
                if not visible:
                    ui.label(translate_string("Nothing here.")).classes("text-sm italic text-gray-500")
                    return
                with ui.row().classes("w-full gap-1 flex-wrap"):
                    for name in visible[:_ICON_PREVIEW_LIMIT]:
                        # "stack" is Quasar's own glyph-above-label layout.  Doing it with flex
                        # classes on the button does not work: they land on the button, while
                        # the row that needs turning is the .q-btn__content inside it, so the
                        # tiles come out half stacked and half side by side.
                        tile = (
                            ui.button(on_click=lambda _e=None, n=name: pick(n))
                            .props(
                                "flat dense no-caps stack",
                            )
                            .classes("w-24 h-20")
                        )
                        with tile:
                            ui.icon(name).style("font-size: 24px;")
                            ui.label(name).style(
                                "font: 9px/1.1 monospace; max-width: 84px; overflow: hidden;"
                                "text-overflow: ellipsis; white-space: nowrap;",
                            )
                            ui.tooltip(sceneedit.v2_icon_reference(name))
                if len(visible) > _ICON_PREVIEW_LIMIT:
                    ui.label(
                        translate_string("...and {count} more -- type above to narrow it down.").format(
                            count=len(visible) - _ICON_PREVIEW_LIMIT,
                        ),
                    ).classes("text-xs text-gray-500 italic mt-1")

        def search_changed(value: str) -> None:
            search["text"] = value or ""
            render()

        render()

        with ui.row().classes("w-full justify-end mt-4 pt-3 border-t"):
            ui.button(translate_string("Cancel"), on_click=dialog.close).props("flat")

    dialog.open()


def _build_material_colour_menu(field: ui.color_input) -> None:
    """The menu of Material role names, each beside a swatch of what it resolves to.

    Both halves are needed to choose one: the name is what gets stored and the colour is what
    it will look like, and neither on its own tells you whether onSecondaryContainer is the
    dark one.  The colours are Material 3's baseline (sceneview.V2_MATERIAL_PALETTE) -- what a
    device without Material You shows, and an indication rather than a promise on one with it.

    Writing through `field.value` leaves the field's own on_change to store it, so this needs
    to know nothing about the component being edited -- the same division the Show When picker
    keeps to.
    """
    with ui.menu().props("auto-close").classes("max-h-96"), ui.column().classes("gap-0 p-1"):
        for name, css in sceneview.V2_MATERIAL_PALETTE.items():
            with ui.item(on_click=lambda _e=None, n=name: field.set_value(n)).props("dense clickable"):
                with ui.row().classes("items-center gap-2 no-wrap"):
                    ui.element("div").style(f"{_V2_SWATCH_STYLE} background: {css};")
                    ui.label(name).classes("text-sm font-mono")
                    ui.space()
                    ui.label(css).classes("text-xs text-gray-500 font-mono")


def _build_state_field(item: dict, field: sceneedit.V2StateField) -> None:
    """One of the Screen Builder's state properties -- Enabled, Content format: a pulldown of
    its states, and, for Dynamic only, the text or %variable to be evaluated when the Scene is
    shown.

    Two widgets rather than one list of everything, because the settling states and the value
    behind Dynamic are not alternatives to each other: On *is* the answer, Dynamic says where
    the answer will come from.  The value box is shown and hidden rather than created and
    destroyed, so that switching to Off to try something and back to Dynamic doesn't lose what
    was typed.

    Each box writes the whole property on every change (sceneedit.v2_set_state takes the state
    and the value together), since neither the state nor the box alone says what to store.
    """
    stored = item.get(field.key, "")
    state = sceneedit.v2_state_of(field, stored)
    # Guards the prompt below against firing while this field is still being built.  Nothing
    # in NiceGUI 3.15 raises on_change from a constructor, so this is belt and braces -- but
    # the cost of being wrong is a picker dialog opening by itself every time a component that
    # happens to hold a variable is selected in the tree.
    ready = {"user": False}

    def value_of(state_name: str) -> str:
        return str((dynamic_input if state_name == sceneedit.V2_DYNAMIC_STATE else variable_input).value or "")

    def write() -> None:
        chosen = str(state_select.value or "")
        sceneedit.v2_set_state(field, item, chosen, value_of(chosen))

    def state_changed() -> None:
        """Write the new state, and -- this being what Select Variable *is* -- put the picker
        up as soon as it is chosen, rather than making the user find a button afterwards.
        """
        write()
        if ready["user"] and state_select.value == sceneedit.V2_VARIABLE_STATE:
            pick_variable()

    def pick_variable() -> None:
        _build_show_when_dialog(
            variable_input,
            sceneedit.v2_dynamic_variable_choices(),
            f"Select a variable for {field.label}",
        )

    state_select = (
        ui.select(
            list(field.states),
            value=state or None,
            label=translate_string(field.label),
            clearable=True,
            on_change=lambda _e=None: state_changed(),
        )
        .props("dense")
        .classes("w-full")
    )
    with state_select:
        ui.tooltip(
            translate_string("Dynamic and Select Variable are worked out when the Scene is shown."),
        )

    dynamic_input = (
        ui.input(
            translate_string("Dynamic value"),
            value=sceneedit.v2_state_value(field, stored, sceneedit.V2_DYNAMIC_STATE),
            on_change=lambda _e=None: write(),
        )
        .props("dense")
        .classes("w-full")
    )
    dynamic_input.bind_visibility_from(
        state_select,
        "value",
        backward=lambda value: value == sceneedit.V2_DYNAMIC_STATE,
    )

    variable_input = (
        ui.input(
            translate_string("Variable"),
            value=sceneedit.v2_state_value(field, stored, sceneedit.V2_VARIABLE_STATE),
            on_change=lambda _e=None: write(),
        )
        .props("dense")
        .classes("w-full")
    )
    variable_input.bind_visibility_from(
        state_select,
        "value",
        backward=lambda value: value == sceneedit.V2_VARIABLE_STATE,
    )
    # Shows what was picked, and re-opens the picker: the prompt on choosing the state is the
    # way in, but a variable chosen by mistake needs a way back that isn't "select a different
    # state and select this one again".
    with variable_input.add_slot("append"):
        variable_button = ui.button(icon="playlist_add", on_click=lambda _e=None: pick_variable()).props(
            "flat dense round size=sm",
        )
        with variable_button:
            ui.tooltip(translate_string("Pick from the Scene's environment and global variables."))

    ready["user"] = True


def _build_v2_designer(
    edited_scene: sceneedit.EditableScene,
    field_refs: dict,
    layout: dict,
) -> None:
    """The Version 2 Scene designer -- phase 1: pick a component out of the tree on the
    left, edit its properties on the right.

    Two panes rather than the read-only outline this replaces, because a component tree is
    navigated and a property sheet is filled in, and those want different shapes.  Both are
    rebuilt wholesale on every selection (`.clear()` then repopulate): the tree because the
    highlight moves, the inspector because a different component has entirely different
    fields.  Rebuilding is why selection is held as a *path* (see sceneedit.v2_flatten) and
    not as a widget reference -- the widgets do not survive, the path does.

    Edits write straight through to the layout dict as they are typed
    (sceneedit.v2_set_prop), rather than being collected from widgets at save time.  The
    inspector's widgets are destroyed on every selection change, so there would be nothing
    left to collect from; and the dict being edited belongs to the dialog's own deep copy of
    the Scene, so nothing reaches the loaded backup until a save button re-encodes it (see
    userintr._apply_scene_field_values).  Cancel discards it by simply not encoding.

    NOT in this phase: adding, deleting, reordering or reparenting components, and editing
    modifiers or event handlers.  Those are carried through untouched -- see sceneedit.py's
    designer section on why in-place editing is what keeps an unchanged Scene re-encoding
    byte-identically.
    """
    # The dict every edit lands in, and the one _apply_scene_field_values re-encodes.
    field_refs["v2_layout"] = layout
    # What is selected: a *run* of adjacent siblings, as the path of its first component and
    # how many of them there are.  One component is the run of one, so nothing here has a
    # single-selection case to special-case.
    #
    # The invariant, which sceneedit.v2_selection_run is what enforces: every component in a
    # run shares a parent and a slot, and their indices are consecutive.  That is what makes
    # a run something a single splice can move, and a selection reaching across two parents
    # something no drag could carry out -- so one is never allowed to exist.
    selection: dict = {"path": (), "count": 1}
    # Snapshots taken before each structural edit. Deep copies of the whole tree, which is
    # affordable at this size (the largest Scene in this repo's backup is 13 components)
    # and far simpler than modelling an inverse for every operation.
    history: list[dict] = []
    scene_name = edited_scene.scene_name
    # Whether the Modifiers / Event handlers sections are open, kept out here because the
    # inspector is rebuilt on every edit -- without this, adding a modifier would collapse
    # the very section you are working in, and adding two in a row would mean re-opening it
    # each time.
    expanded = {"modifiers": False, "handlers": False}
    # The tree's rendered rows, path -> (label widget, depth), rebuilt by render_tree.  Held
    # so retitle_node_labels can reach the selected row's label without a full re-render.
    tree_rows: dict[tuple, tuple] = {}
    # The inspector's own heading for the selected component, held for the same reason.
    inspector_heading: dict = {"label": None}

    if not sceneedit.v2_flatten(layout):
        # No root component at all -- not something Tasker writes, and there is nothing for
        # the tree to hang off, so say so rather than showing an empty designer.
        ui.label(
            translate_string("This Scene's Version 2 layout has no root component, so there is nothing to design."),
        ).classes("text-sm text-orange-600 mt-2")
        return

    _register_canvas_events()
    # This designer's own reorder surface -- unique for the reason _ACTIVE_CANVASES gives:
    # ui.on subscribes app-wide, and the Preview is a second surface over this same layout.
    tree_root = f"mt-v2-tree-{next(_DESIGNER_SEQUENCE)}"

    header = ui.row().classes("w-full items-center gap-2 mt-2")
    with ui.row().classes("w-full gap-3 items-start no-wrap mt-1"):
        tree_pane = ui.column().classes(f"{tree_root} w-2/5 gap-0 p-2 border rounded max-h-80 overflow-auto")
        inspector_pane = ui.column().classes("w-3/5 gap-2 p-2 border rounded max-h-80 overflow-auto")
    toolbar = ui.row().classes("w-full gap-1 items-center mt-1 flex-wrap")

    def snapshot() -> None:
        history.append(copy.deepcopy(layout))

    def restore() -> None:
        if not history:
            return
        previous = history.pop()
        # Replace the contents rather than rebinding: field_refs and the save path hold
        # *this* dict object, so swapping in a new one would leave them on the old tree.
        layout.clear()
        layout.update(previous)
        if not sceneedit.v2_run_is_valid(layout, selection["path"], selection["count"]):
            select_only(())
        render()

    def select_only(path: tuple, count: int = 1) -> None:
        """Set the selection without re-rendering -- for the callers that render anyway."""
        selection["path"] = path
        selection["count"] = max(1, count)

    def select(path: tuple, count: int = 1) -> None:
        select_only(path, count)
        render()

    def select_from_surface(payload: dict) -> None:
        """A click on a tree row or on a component in the Preview.

        Shift extends the selection into a run, but only where a run is a thing that could
        exist: shift-clicking into another container starts a fresh selection there instead
        of refusing the click, because the user is plainly pointing at that component and
        selecting it is the reading that gives them something.
        """
        path = sceneview.v2_decode_path(str(payload.get("path", "")))
        if sceneedit.v2_node_at(layout, path) is None:
            return
        if payload.get("extend"):
            run = sceneedit.v2_selection_run(layout, selection["path"], path)
            if run is not None:
                select(*run)
                return
        select(path)

    def reorder_from_surface(payload: dict) -> None:
        """A run dropped in one of the gaps between its siblings, from either surface."""
        path = sceneview.v2_decode_path(str(payload.get("path", "")))
        count = max(1, int(payload.get("count", 1) or 1))
        if not sceneedit.v2_run_is_valid(layout, path, count):
            return
        snapshot()
        new_path = sceneedit.v2_drop_run(layout, path, count, int(payload.get("before", 0) or 0))
        if new_path is None:
            # The drop landed where the run already was.  Nothing was changed and nothing is
            # said about it -- putting something back where it came from is a thing users do
            # on purpose, not a failed operation.
            history.pop()
            select(path, count)
            return
        select(new_path, count)

    def add_component(node_type: str) -> None:
        snapshot()
        new_path = sceneedit.v2_insert_node(layout, selection["path"], sceneedit.v2_new_node(layout, node_type))
        if new_path is None:
            history.pop()
            ui.notify(translate_string("That component can't go there."), type="warning")
            return
        select(new_path)

    def structural(operation: Callable[[], tuple | None], failure: str, count: int = 1) -> None:
        """Run a move/duplicate that returns a new path, keeping the moved component
        selected -- so a run of Move Up clicks walks one component up the tree instead of
        losing it after the first.

        `count` is what to re-select: the whole run for the operations that move one (Up and
        Down), one component for those that do not.
        """
        snapshot()
        new_path = operation()
        if new_path is None:
            history.pop()
            ui.notify(translate_string(failure), type="warning")
            return
        select(new_path, count)

    def delete_selected() -> None:
        node = sceneedit.v2_node_at(layout, selection["path"])
        node_id = (node or {}).get("id", "")
        references = sceneedit.find_component_id_references(scene_name, node_id)
        snapshot()
        errors = sceneedit.v2_delete_node(layout, selection["path"])
        if errors:
            history.pop()
            for error in errors:
                ui.notify(error, type="negative")
            return
        if references:
            # Warn rather than block: the Task may be obsolete, and the user can undo.
            ui.notify(
                f"Deleted '{node_id}'. {len(references)} Task(s) address it by id: "
                f"{', '.join(references)}. They will no longer find it.",
                type="warning",
                multi_line=True,
                timeout=10000,
            )
        select_only(())
        render()

    def render_tree() -> None:
        tree_rows.clear()
        rows = sceneedit.v2_flatten(layout)
        # How many components share each slot, which is the number of gaps a drop can aim at.
        # Counted off the flattened tree rather than looked up per row: every sibling is a row
        # here, and rows that are siblings are exactly the rows whose paths agree but for
        # their last element.
        siblings = collections.Counter(row.path[:-1] for row in rows if row.path)
        selected = sceneedit.v2_run_paths(selection["path"], selection["count"])
        for row in rows:
            classes = "mt-v2-row text-sm font-mono whitespace-pre cursor-pointer rounded px-1 py-0.5 w-full"
            classes += (
                " bg-blue-600 text-white" if row.path in selected else " hover:bg-blue-100 dark:hover:bg-blue-900"
            )
            # The indent is drawn rather than nested so every row stays one flat, clickable
            # strip -- nested containers would make the click target of a deep node a sliver.
            label = (
                ui.label(f"{'  ' * row.depth}{row.label}")
                .classes(classes)
                .on("click", lambda _e=None, path=row.path: select(path))
            )
            # The same two attributes the Preview's components carry, so one script drags
            # both -- where this row sits, and how many gaps its slot has to drop into.
            label.props(
                f'data-path="{sceneview.v2_encode_path(row.path)}" data-sibs="{siblings.get(row.path[:-1], 0)}"',
            )
            tree_rows[row.path] = (label, row.depth)
        tree_pane.props(_v2_selection_props(selection))
        _emit_v2_dragging(
            tree_root,
            f".{tree_root}",
            "mt-v2-row",
            # The rows select themselves through NiceGUI; see guiwins_canvas._emit_v2_dragging.
            select_on_click=False,
        )

    def retitle_node_labels(node: dict) -> None:
        """Keep both places a component is named by -- its tree row and the inspector's own
        heading -- reading correctly as its Tree label is typed.  Both, because they show the
        same v2_node_label and would otherwise disagree with each other until the next
        re-render.

        A no-op for any other dict prop_input is editing: a modifier or an action can carry a
        treeLabel key of its own and names nothing in the tree.
        """
        if node is not sceneedit.v2_node_at(layout, selection["path"]):
            return
        text = sceneedit.v2_node_label(node)
        row = tree_rows.get(selection["path"])
        if row is not None:
            label, depth = row
            label.set_text(f"{'  ' * depth}{text}")
        if inspector_heading.get("label") is not None:
            inspector_heading["label"].set_text(text)

    def prop_input(item: dict, prop: sceneedit.V2Prop) -> None:
        """One editable field for any dict the designer edits -- a component, a modifier,
        an event or an action.  They all store scalars under named keys, so they all get
        the same handful of widget kinds and the same write-through to sceneedit.v2_set_prop.

        `item` is the thing being edited; `target` is where this particular property is kept,
        which for most of them is the same object and for a Text's styling is the nested one
        it names (sceneedit.v2_prop_dict).  Everything that reads or writes the value goes
        through `target`; the two things that need the component itself -- what type it is, and
        retitling its tree row -- keep using `item`.
        """
        target = sceneedit.v2_prop_dict(item, prop)
        value = target.get(prop.key, "")
        if prop.kind == "task":
            # RunTask names a Task in the loaded backup, so offer the real list rather than
            # a free field -- with_input still allows a name that isn't loaded yet.
            task_names = sorted(PrimeItems.tasker_root_elements.get("all_tasks_by_name", {}))
            ui.select(
                task_names,
                value=str(value) if value != "" else None,
                label=translate_string(prop.label),
                with_input=True,
                on_change=lambda e, k=prop.key, d=target: sceneedit.v2_set_prop(d, k, str(e.value or "")),
            ).props("dense").classes("w-full")
        elif prop.kind == "choice":
            ui.select(
                list(prop.choices),
                value=str(value) if value != "" else None,
                label=translate_string(prop.label),
                with_input=True,
                on_change=lambda e, k=prop.key, d=target: sceneedit.v2_set_prop(d, k, str(e.value or "")),
            ).props("dense").classes("w-full")
        elif prop.kind == "state" and (state_field := sceneedit.v2_state_field(prop.key)) is not None:
            _build_state_field(target, state_field)
        elif prop.kind in ("color", "colorvar"):
            _build_colour_field(target, prop)
        elif prop.kind == "icon":
            _build_icon_field(target, prop)
        else:
            text_input = (
                ui.input(
                    translate_string(prop.label),
                    value=str(value),
                    on_change=lambda e, k=prop.key, d=target: sceneedit.v2_set_prop(d, k, str(e.value or "")),
                )
                .props("dense")
                .classes("w-full")
            )
            if prop.key == "showWhen":
                # A Show When is built out of variables nobody remembers the spelling of --
                # %sv2_render_is_landscape is not something to type from memory, and a
                # misspelling doesn't fail, it just silently never matches.  So the field
                # carries a picker for all three categories of them.
                with text_input.add_slot("append"):
                    show_when_button = ui.button(
                        icon="playlist_add",
                        on_click=lambda _e=None, w=text_input: _build_show_when_dialog(w),
                    ).props("flat dense round size=sm")
                    with show_when_button:
                        ui.tooltip(translate_string("Pick from the Scene's environment and global variables."))
            elif prop.kind in ("textvar", "numvar"):
                # Fill it in, or point it at a variable.  One field for both, rather than the
                # state fields' pulldown-and-box, because there is nothing to choose between:
                # a max lines of "2" and a max lines of "%line_budget" are the same property
                # written two ways, and neither is a state the other isn't.
                with text_input.add_slot("append"):
                    _variable_picker_button(text_input, prop.label)
            # Either of the two properties a component can be named by: its treeLabel, or --
            # for a Text, which is named by what it says -- its own text (see
            # sceneedit.v2_node_name).  A change to whichever names *this* node has to reach
            # the tree row.  The row is retitled in place rather than the panes being
            # re-rendered, for two reasons: a rebuild on every keystroke would destroy the
            # field being typed into and take the caret with it, and deferring the rebuild to
            # the field's blur doesn't work -- Quasar's blur does not reach a NiceGUI
            # .on("blur") handler here, so the row would simply sit stale until the next click.
            names_node = prop.key in ("treeLabel", sceneedit.V2_LABEL_FALLBACK.get(str(item.get("type", "")), ""))
            if names_node:
                text_input.on_value_change(lambda _e=None, d=item: retitle_node_labels(d))

    def structural_edit(mutate: Callable[[], object]) -> None:
        """Snapshot, mutate, re-render -- the wrapper every add/remove/reorder inside the
        inspector goes through, so all of them land on the same undo stack as the tree's.
        """
        snapshot()
        mutate()
        render()

    def render_binding(node: dict) -> None:
        slot = sceneedit.v2_binding_slot(node)
        if slot is None:
            return
        state_key, binding_key = slot
        ui.label(f"{translate_string('Writes to variable')} ({state_key}.{binding_key})").classes(
            "text-xs uppercase text-gray-500 mt-2",
        )
        ui.input(
            translate_string("Tasker variable(s)"),
            value=sceneedit.v2_get_binding(node, slot),
            on_change=lambda e, n=node, s=slot: sceneedit.v2_set_binding(n, s, str(e.value or "")),
        ).props("dense").classes("w-full").tooltip(
            translate_string(
                "The Tasker variable this component writes its value into. "
                "Separate several with commas. Leave empty to declare the binding without setting it.",
            ),
        )

    def render_modifiers(node: dict) -> None:
        modifiers = sceneedit.v2_modifiers(node)
        with ui.expansion(
            f"{translate_string('Modifiers')} ({len(modifiers)})",
            icon="tune",
            value=expanded["modifiers"],
            on_value_change=lambda e: expanded.__setitem__("modifiers", bool(e.value)),
        ).classes("w-full mt-2"):
            ui.label(
                translate_string("Applied in order — the one at the bottom sits on top."),
            ).classes("text-xs text-gray-500 italic")
            for index, modifier in enumerate(modifiers):
                with ui.card().classes("w-full p-2 gap-1"):
                    with ui.row().classes("w-full items-center gap-1"):
                        ui.label(modifier.get("type", "?")).classes("text-sm font-mono font-semibold")
                        ui.space()
                        ui.button(
                            icon="arrow_upward",
                            on_click=lambda _e=None, i=index: structural_edit(
                                lambda: sceneedit.v2_move_modifier(node, i, -1),
                            ),
                        ).props("dense flat size=sm")
                        ui.button(
                            icon="arrow_downward",
                            on_click=lambda _e=None, i=index: structural_edit(
                                lambda: sceneedit.v2_move_modifier(node, i, 1),
                            ),
                        ).props("dense flat size=sm")
                        ui.button(
                            icon="close",
                            on_click=lambda _e=None, i=index: structural_edit(
                                lambda: sceneedit.v2_delete_modifier(node, i),
                            ),
                        ).props("dense flat size=sm color=negative")
                    for prop in sceneedit.v2_schema_props(
                        sceneedit.V2_MODIFIER_SCHEMA,
                        modifier,
                        sceneedit.V2_MODIFIER_UNIVERSAL_PROPS,
                    ):
                        prop_input(modifier, prop)
            add_modifier = ui.button(translate_string("Add modifier"), icon="add").props("dense flat")
            with add_modifier, ui.menu():
                for modifier_type in sceneedit.V2_MODIFIER_SCHEMA:
                    ui.menu_item(
                        modifier_type,
                        on_click=lambda _e=None, t=modifier_type: structural_edit(
                            lambda: sceneedit.v2_add_modifier(node, t),
                        ),
                    ).props("dense")

    def render_handlers(node: dict) -> None:
        handlers = sceneedit.v2_handlers(node)
        with ui.expansion(
            f"{translate_string('Event handlers')} ({len(handlers)})",
            icon="bolt",
            value=expanded["handlers"],
            on_value_change=lambda e: expanded.__setitem__("handlers", bool(e.value)),
        ).classes("w-full mt-1"):
            for index, handler in enumerate(handlers):
                events = handler.get("events") or []
                with ui.card().classes("w-full p-2 gap-1"):
                    with ui.row().classes("w-full items-center gap-1"):
                        ui.label(
                            translate_string("On") + " " + ", ".join(e.get("type", "?") for e in events),
                        ).classes("text-sm font-mono font-semibold")
                        ui.space()
                        ui.button(
                            icon="close",
                            on_click=lambda _e=None, i=index: structural_edit(
                                lambda: sceneedit.v2_delete_handler(node, i),
                            ),
                        ).props("dense flat size=sm color=negative")
                    for event in events:
                        for prop in sceneedit.v2_schema_props(sceneedit.V2_EVENT_SCHEMA, event):
                            prop_input(event, prop)
                    # A handler-level condition gates the whole thing; the 'V2' Scene uses
                    # one to run only in portrait.
                    ui.input(
                        translate_string("Only when"),
                        value=str(handler.get("condition", "")),
                        on_change=lambda e, h=handler: sceneedit.v2_set_prop(h, "condition", str(e.value or "")),
                    ).props("dense").classes("w-full")

                    actions = handler.get("actions") or []
                    ui.label(f"{translate_string('Actions')} ({len(actions)})").classes(
                        "text-xs uppercase text-gray-500 mt-1",
                    )
                    for action_index, action in enumerate(actions):
                        with ui.row().classes("w-full items-center gap-1"):
                            ui.label(action.get("type", "?")).classes("text-xs font-mono")
                            ui.space()
                            ui.button(
                                icon="arrow_upward",
                                on_click=lambda _e=None, h=handler, a=action_index: structural_edit(
                                    lambda: sceneedit.v2_move_action(h, a, -1),
                                ),
                            ).props("dense flat size=sm")
                            ui.button(
                                icon="arrow_downward",
                                on_click=lambda _e=None, h=handler, a=action_index: structural_edit(
                                    lambda: sceneedit.v2_move_action(h, a, 1),
                                ),
                            ).props("dense flat size=sm")
                            ui.button(
                                icon="close",
                                on_click=lambda _e=None, h=handler, a=action_index: structural_edit(
                                    lambda: sceneedit.v2_delete_action(h, a),
                                ),
                            ).props("dense flat size=sm color=negative")
                        for prop in sceneedit.v2_schema_props(sceneedit.V2_ACTION_SCHEMA, action):
                            prop_input(action, prop)

                    add_action = ui.button(translate_string("Add action"), icon="add").props("dense flat size=sm")
                    with add_action, ui.menu():
                        for action_type in sceneedit.V2_ACTION_TYPES:
                            ui.menu_item(
                                action_type,
                                on_click=lambda _e=None, h=handler, t=action_type: structural_edit(
                                    lambda: sceneedit.v2_add_action(h, t),
                                ),
                            ).props("dense")

            add_handler = ui.button(translate_string("Add handler"), icon="add").props("dense flat")
            with add_handler, ui.menu():
                for event_type in sceneedit.V2_EVENT_TYPES:
                    ui.menu_item(
                        event_type,
                        on_click=lambda _e=None, t=event_type: structural_edit(
                            lambda: sceneedit.v2_add_handler(node, t),
                        ),
                    ).props("dense")

    def render_prop(node: dict, prop: sceneedit.V2Prop) -> None:
        """One property of the selected component.

        Everything goes through prop_input except the component's own id, which is applied by
        v2_rename_id rather than v2_set_prop: an id has to stay unique, and Tasks address
        components by it (see rename_id below).  `prop.container` is what tells that id apart
        from a nested key that merely happens to be called "id".
        """
        if prop.key != "id" or prop.container:
            prop_input(node, prop)
            return

        value = node.get(prop.key, "")
        id_input = ui.input(translate_string(prop.label), value=str(value)).props("dense").classes("w-full")
        id_input.on("blur", lambda _e=None, w=id_input, p=selection["path"]: rename_id(p, w))
        references = sceneedit.find_component_id_references(scene_name, str(value))
        if references:
            ui.label(
                f"{translate_string('Addressed by id from')}: {', '.join(references)}",
            ).classes("text-xs text-orange-600 italic")

    def render_category(node: dict, name: str, props: list) -> None:
        """One named section of the property sheet, for the types that have them.

        Open/closed is remembered in `expanded` for the same reason the Modifiers section's is:
        the inspector is rebuilt on every edit, so a section that didn't remember would shut
        itself the moment you typed in it.  It is keyed by category name rather than by
        component, so walking down a column of Texts keeps the section you are working in open
        instead of making you reopen it at every stop.

        The caption counts what is actually set.  With eight sections and fifty-odd fields
        behind them, "which of these has anything in it" is the question the closed sheet has
        to answer -- otherwise finding the one shadow colour a Scene sets means opening all
        eight.

        It is recounted when the section is toggled rather than on every keystroke, because
        the inspector is not rebuilt as you type (see the treeLabel note in prop_input) and a
        count that never recounted would still read 2/11 after you had filled in a third.
        Toggling is when the number is actually read: an open section shows its own fields, so
        the only caption anyone looks at is one that has just been -- or is about to be --
        closed.
        """
        key = f"category:{name}"
        expanded.setdefault(key, name in sceneedit.V2_OPEN_CATEGORIES)

        def caption() -> str:
            filled = sum(1 for prop in props if str(sceneedit.v2_prop_dict(node, prop).get(prop.key, "")) != "")
            return f"{filled}/{len(props)}"

        def toggled(value: object) -> None:
            expanded[key] = bool(value)
            section.props(f'caption="{caption()}"')

        section = (
            ui.expansion(
                translate_string(name),
                icon=_V2_CATEGORY_ICONS.get(name, "tune"),
                caption=caption(),
                value=expanded[key],
                on_value_change=lambda e: toggled(e.value),
            )
            .props("dense")
            .classes("w-full")
        )
        with section, ui.column().classes("w-full gap-2 pb-2"):
            for prop in props:
                render_prop(node, prop)

    def render_inspector() -> None:
        node = sceneedit.v2_node_at(layout, selection["path"])
        if node is None:
            ui.label(translate_string("Select a component on the left.")).classes("text-sm italic text-gray-500")
            return

        inspector_heading["label"] = ui.label(sceneedit.v2_node_label(node)).classes(
            "text-sm font-semibold font-mono",
        )
        for name, props in sceneedit.v2_property_groups(node):
            if not name:
                # The flat list every type but Text still gets -- see v2_property_groups.
                for prop in props:
                    render_prop(node, prop)
                continue
            render_category(node, name, props)

        render_binding(node)
        render_modifiers(node)
        render_handlers(node)

    def rename_id(path: tuple, widget: ui.input) -> None:
        """Applies the id field on blur rather than on every keystroke -- a partially-typed
        id would otherwise be checked for uniqueness mid-word and rejected for colliding
        with itself.
        """
        node = sceneedit.v2_node_at(layout, path)
        if node is None or str(widget.value).strip() == node.get("id", ""):
            return
        snapshot()
        errors = sceneedit.v2_rename_id(layout, path, str(widget.value))
        if errors:
            history.pop()
            for error in errors:
                ui.notify(error, type="negative")
            widget.value = node.get("id", "")
            return
        render()

    def render_header() -> None:
        rows = sceneedit.v2_flatten(layout)
        ui.label(f"{translate_string('Scene Components')} ({len(rows)})").classes("text-sm font-semibold")
        ui.space()
        add_button = ui.button(
            translate_string("Add"),
            icon="add",
            on_click=lambda: _build_add_element_dialog(layout, selection["path"], add_component),
        ).props("dense flat")
        with add_button:
            ui.tooltip(
                translate_string(
                    "Adds inside the selected component if it can hold children, otherwise directly after it.",
                ),
            )
        ui.button(translate_string("Undo"), icon="undo", on_click=restore).props("dense flat").set_enabled(
            bool(history),
        )

    def render_toolbar() -> None:
        """The structural operations.

        Up and Down move the whole selected run; everything else is a one-component
        operation and is switched off while a run is selected, rather than quietly acting on
        the first of them.  Deleting three highlighted components and keeping two is the kind
        of surprise an Undo does not really undo.
        """
        node = sceneedit.v2_node_at(layout, selection["path"])
        is_root = not selection["path"]
        run = selection["count"]
        for label, icon, handler, failure in (
            (
                "Up",
                "arrow_upward",
                lambda: sceneedit.v2_move_run(layout, selection["path"], selection["count"], -1),
                "Already first.",
            ),
            (
                "Down",
                "arrow_downward",
                lambda: sceneedit.v2_move_run(layout, selection["path"], selection["count"], 1),
                "Already last.",
            ),
            (
                "Out",
                "format_indent_decrease",
                lambda: sceneedit.v2_outdent_node(layout, selection["path"]),
                "Nothing to move it out to.",
            ),
            (
                "In",
                "format_indent_increase",
                lambda: sceneedit.v2_indent_node(layout, selection["path"]),
                "The component above it can't hold children.",
            ),
            (
                "Duplicate",
                "content_copy",
                lambda: sceneedit.v2_duplicate_node(layout, selection["path"]),
                "The root component can't be duplicated.",
            ),
        ):
            moves_run = label in ("Up", "Down")
            ui.button(
                translate_string(label),
                icon=icon,
                on_click=lambda _e=None, op=handler, f=failure, c=(run if moves_run else 1): structural(op, f, c),
            ).props("dense flat").set_enabled(node is not None and not is_root and (moves_run or run == 1))
        ui.button(translate_string("Delete"), icon="delete", on_click=delete_selected).props(
            "dense flat color=negative",
        ).set_enabled(node is not None and not is_root and run == 1)
        ui.space()
        ui.label(
            translate_string(
                (
                    "Drag to reorder. Shift-click a component in the same container to take several at once."
                    if run == 1
                    else f"{run} components selected — they move together."
                ),
            ),
        ).classes("text-xs text-gray-500 italic")

    def render() -> None:
        # Re-registered on every render because the handlers close over nothing that changes,
        # but the table is what a re-opened dialog's surface has to be found in again.
        _ACTIVE_CANVASES[tree_root] = {"v2select": select_from_surface, "v2reorder": reorder_from_surface}
        # What the Preview needs to be the second surface over this same layout, and why it
        # is handed these three rather than a copy of them:
        #
        #   handlers  -- the Preview's drags run *these* closures, so a reorder made in the
        #                picture lands on this designer's undo stack instead of a second one
        #                that its Undo button knows nothing about.
        #   selection -- the same dict object, so the run outlined in the picture and the run
        #                highlighted in the tree cannot disagree.
        #
        #   rerender  -- called when the dialog comes back, because re-opening it rebuilds the
        #                tree pane's DOM and the drag handlers have to be put back on the new
        #                one.  See NiceGuiSceneView._back_to_editor.
        #
        # Running this designer's handlers is also what keeps the tree from going stale while
        # it is hidden: they end in render(), so the pane the Preview is covering is rebuilt
        # as the drag lands rather than coming back showing the order from before it.
        field_refs["v2_edit"] = {
            "handlers": _ACTIVE_CANVASES[tree_root],
            "selection": selection,
            "rerender": render,
        }
        header.clear()
        tree_pane.clear()
        inspector_pane.clear()
        toolbar.clear()
        with header:
            render_header()
        with tree_pane:
            render_tree()
        with inspector_pane:
            render_inspector()
        with toolbar:
            render_toolbar()

    render()
