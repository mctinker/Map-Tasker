"""guiwins_tndesc: the TaskerNet Description editor, shared by every Project, Profile and Task Add and Edit dialog.

One button in each of those dialogs opens it, beside the Properties button it is modelled on.  What a description is,
how it is written onto the object and what HTML it may carry live in core/tndesc.py; this is the form over it: a text
box, a row of buttons that write the tags, the checks, and a preview made by the code that draws the Map."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, cast

from nicegui import ui

from maptasker.src.core import tndesc
from maptasker.src.core.maputil2 import suppress_logged, translate_string
from maptasker.src.core.runcfg import current_config
from maptasker.src.core.share import description_html
from maptasker.src.gui.guiwins_editor import PendingChangesBanner, editor_state

if TYPE_CHECKING:
    from collections.abc import Callable
    from xml.etree.ElementTree import Element

    from maptasker.src.gui.userintr import MyGui

ADD_LABEL = "Add TaskerNet Description"
EDIT_LABEL = "Edit TaskerNet Description"

# Tasker's own wording, which is all there is to go on: there is no published list of tags.
INTRO = (
    "What anybody sees before importing this from TaskerNet.  Tasker says you can use HTML formatting in it, "
    "and some small images.  Plain text works too.  The buttons write the tags real TaskerNet descriptions use."
)

_ISSUE_COLORS = {tndesc.WARNING: "text-orange-600", tndesc.INFO: "text-gray-500"}
_ISSUE_ICONS = {tndesc.WARNING: "warning", tndesc.INFO: "info"}
_HEX_COLOR = re.compile(r"^[0-9A-Fa-f]{6}$")
# A selection is a start and an end.
_SELECTION_PARTS = 2
# flex-shrink:0 is load-bearing: the dialog's card is a flex column, and a child that scrolls is allowed to shrink
# to nothing in one, which left a preview one line high with the rest of it hanging out of the bottom.
_PREVIEW_STYLE = (
    "padding:8px; border-radius:4px; max-height:240px; min-height:3em; overflow:auto; width:100%; flex-shrink:0"
)


def _css_color(value: str) -> str:
    """A color as the Map's color table writes it -- 'Lavender', or the hex '222623' -- as CSS."""
    return f"#{value}" if _HEX_COLOR.match(value) else value


def _native_textarea_script(field_id: int) -> str:
    """The JavaScript that finds a ui.textarea's native <textarea>, as ``el`` (null if there is none).

    The same two-shape search guiwins_designer_v2 uses for a ui.input, for the same reason:
    getHtmlElement() may hand back the <textarea> itself or a wrapper around one.
    """
    return (
        f"const el = (() => {{ const r = getHtmlElement({field_id});"
        f" return r && r.matches('textarea') ? r : r && r.querySelector('textarea'); }})();"
    )


async def selection_in(field: ui.textarea) -> tuple[int, int]:
    """Where the selection is in the text box, asked of the browser -- or the end of the text if it will not say.

    Asked for rather than remembered, because the selection lives in the DOM and NiceGUI's value
    binding knows nothing about it.  The end of the text is the safe answer: a button pressed
    before the box was ever clicked into adds its tags after what is there.
    """
    length = len(str(field.value or ""))
    with suppress_logged("Reading the selection in the description"):
        found = cast(
            "object",
            await ui.run_javascript(
                f"(() => {{ {_native_textarea_script(field.id)} return el ? [el.selectionStart, el.selectionEnd] : null; }})()",
                timeout=3.0,
            ),
        )
        if isinstance(found, list) and len(cast("list[object]", found)) == _SELECTION_PARTS:
            start, end = cast("list[int]", found)
            return int(start), int(end)
    return length, length


def select_in(field: ui.textarea, start: int, end: int) -> None:
    """Put the selection back where a tool left it, once the new text has reached the browser."""
    ui.run_javascript(
        f"setTimeout(() => {{ {_native_textarea_script(field.id)}"
        f" if (el) {{ el.focus(); el.setSelectionRange({start}, {end}); }} }}, 60);",
    )


class _DescriptionEditor:
    """The dialog's widgets, and what each button does to them."""

    def __init__(
        self,
        gui: MyGui,
        kind: str,
        element: Element,
        name: str,
        on_kept: Callable[[], None],
        on_applied: Callable[[], None] | None,
    ) -> None:
        self.gui = gui
        self.kind = kind
        self.element = element
        self.name = name
        self.on_kept = on_kept
        self.on_applied = on_applied
        self.dialog: ui.dialog
        self.text: ui.textarea
        self.address: ui.input
        self.color: ui.select
        self.heading: ui.select
        self.issues: ui.column
        self.preview: ui.html

    # ---------------------------------------------------------------- the pieces
    def build(self) -> None:
        """The whole dialog, opened."""
        title = f"{translate_string(self.kind)} {translate_string('TaskerNet Description')}"
        with (
            ui.dialog().props("persistent") as self.dialog,
            ui.card().classes("min-w-[560px] max-w-[900px] w-full p-6"),
        ):
            ui.label(f"{title}: {self.name}" if self.name else title).classes("text-xl font-bold text-blue-600")
            ui.label(translate_string(INTRO)).classes("text-xs text-gray-500 italic")
            self._build_toolbar()
            self.text = (
                ui.textarea(
                    translate_string("Description"),
                    value=tndesc.description_of(self.element),
                    on_change=lambda _event: self.refresh(),
                )
                .props("outlined rows=12 debounce=250 input-style='font-family: monospace'")
                .classes("w-full")
            )
            self._build_helpers()
            self.issues = ui.column().classes("w-full gap-0")
            ui.label(translate_string("Preview, as the Map shows it")).classes("text-sm font-bold mt-2")
            background = _css_color(current_config(self.gui.state).colors.get("background_color", "white"))
            self.preview = ui.html("", sanitize=False).style(f"{_PREVIEW_STYLE}; background:{background}")
            PendingChangesBanner().watch(self.dialog, lambda: editor_state(self.element, {"description": self.text}))
            self._build_buttons()
        self.refresh()
        self.dialog.open()

    def _tool_button(self, tool: tndesc.Tool) -> None:
        button = ui.button(
            icon=tool.icon,
            on_click=lambda _event=None, t=tool: self.use(t),
        ).props("flat dense round")
        with button:
            ui.tooltip(f"{translate_string(tool.label)}.  {translate_string(tool.tooltip)}")

    def _build_toolbar(self) -> None:
        """One button per tool, and the two choices a tool may need: a heading level and a color."""
        with ui.row().classes("w-full items-center gap-0 flex-wrap"):
            for tool in tndesc.TOOLS:
                self._tool_button(tool)
                if tool.key == "color":
                    self.color = (
                        ui.select(list(tndesc.COLORS), value=tndesc.COLORS[0]).props("dense borderless").classes("w-24")
                    )
            self.heading = (
                ui.select(list(tndesc.HEADINGS), value=tndesc.DEFAULT_HEADING).props("dense borderless").classes("w-20")
            )
            with ui.button(
                icon="title",
                on_click=lambda _event=None: self.use(tndesc.heading_tool(str(self.heading.value))),
            ).props("flat dense round"):
                ui.tooltip(translate_string("Heading, at the level chosen beside it.  H1 is the largest."))

    def _build_helpers(self) -> None:
        """The address the Link and Image buttons use, and the two whole-text conveniences."""
        with ui.row().classes("w-full items-center gap-2"):
            self.address = ui.input(
                translate_string("Address for Link and Image"),
                placeholder=tndesc.DEFAULT_ADDRESS,
            ).classes("flex-1")
            with ui.button(
                translate_string("Add Line Breaks"),
                on_click=lambda: self.text.set_value(tndesc.add_line_breaks(str(self.text.value or ""))),
            ).props("outline dense no-caps"):
                ui.tooltip(
                    translate_string(
                        "In HTML a line end is only a space, so text that reads as a list here runs together on "
                        "a web page.  This puts a <br/> on the end of every line that does not already end a tag.",
                    ),
                ).style("white-space: pre-wrap")

    def _build_buttons(self) -> None:
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=self.dialog.close).props("outline")
            with ui.button(translate_string("Clear"), on_click=lambda: self.text.set_value("")).props("outline"):
                ui.tooltip(
                    translate_string("Empties the box.  The description is taken off the object when you press Ok."),
                )
            ok = ui.button(translate_string("Ok"), on_click=self.keep).classes("bg-blue-600")
            with ok:
                ui.tooltip(translate_string(self._ok_tooltip())).style("white-space: pre-wrap")

    def _ok_tooltip(self) -> str:
        if self.on_applied is not None:
            return (
                "Puts the description on the Project in the loaded backup, right now, for this session only: no "
                "file is written and nothing is sent to your Android device.  One press of Undo takes it back."
            )
        return (
            "Keeps the description on this object.  It is saved with everything else when you save, and Cancel "
            "in the window behind this one still discards it."
        )

    # ---------------------------------------------------------------- what the buttons do
    async def use(self, tool: tndesc.Tool) -> None:
        """Write one tool's tags into the box, around the selection."""
        text = str(self.text.value or "")
        start, end = await selection_in(self.text)
        edit = tndesc.apply_tool(
            text,
            start,
            end,
            tool,
            address=str(self.address.value or ""),
            color=str(self.color.value or ""),
        )
        self.text.set_value(edit.text)
        select_in(self.text, edit.start, edit.end)

    def refresh(self) -> None:
        """Redo the checks and the preview for what is in the box."""
        text = str(self.text.value or "")
        self.issues.clear()
        with self.issues:
            self._show_issues(text)
        self.preview.set_content(self._preview_html(text))

    def _show_issues(self, text: str) -> None:
        if not text.strip():
            ui.label(translate_string("Nothing written yet.")).classes("text-xs text-gray-500 italic")
            return
        found = tndesc.check(text)
        if not found:
            ui.label(translate_string("No problems found in the HTML.")).classes("text-xs text-green-600")
        for issue in found:
            with ui.row().classes(f"items-center gap-1 {_ISSUE_COLORS[issue.severity]}"):
                ui.icon(_ISSUE_ICONS[issue.severity]).classes("text-sm")
                ui.label(issue.message).classes("text-xs")

    def _preview_html(self, text: str) -> str:
        if not text.strip():
            return f"<i>{translate_string('Nothing to show.')}</i>"
        with suppress_logged("Drawing the TaskerNet description preview"):
            return description_html(text, current_config(self.gui.state).colors)
        return f"<i>{translate_string('The preview could not be drawn.')}</i>"

    def keep(self) -> None:
        """Ok."""
        self.gui.event_handlers.editors.keep_taskernet_description_event(
            self.element,
            str(self.text.value or ""),
            self.dialog,
            self.on_applied,
            self.on_kept,
        )


def build_taskernet_description_dialog(
    self: MyGui,
    kind: str,
    element: Element,
    name: str = "",
    on_kept: Callable[[], None] | None = None,
    on_applied: Callable[[], None] | None = None,
) -> None:
    """Open the TaskerNet Description editor over whichever Add/Edit dialog asked for it.

    Opens OVER the parent, which stays open behind it: the parent still owns the save, and
    closing it out from under the user would lose whatever else they had typed into it.
    `on_applied` is for a caller whose element is not the whole story -- Edit Project, whose
    saves render from the live tree -- exactly as it is for the Properties editor.
    """
    _DescriptionEditor(self, kind, element, name, on_kept or (lambda: None), on_applied).build()


def build_taskernet_description_button(
    self: MyGui,
    kind: str,
    element: Element,
    name: str = "",
    on_applied: Callable[[], None] | None = None,
) -> ui.button:
    """The one button an Add/Edit dialog grows.  Reads "Add TaskerNet Description" for an object
    that has none and "Edit TaskerNet Description" for one that has, and changes to match when
    the editor's Ok is pressed.

    Deliberately NOT registered in the caller's field_refs, for the reason the Properties
    button is not: the Task dialog reads .value off every entry there, the Project dialog
    fails a save on a field it does not know, and nothing needs it -- the editor writes onto
    the element itself, which is what both the save and editor_state() already read.
    """
    button: ui.button

    def label() -> str:
        return translate_string(EDIT_LABEL if tndesc.has_description(element) else ADD_LABEL)

    def kept() -> None:
        button.set_text(label())

    button = ui.button(
        label(),
        icon="public",
        on_click=lambda: build_taskernet_description_dialog(self, kind, element, name, kept, on_applied),
    ).props("outline")
    with button:
        ui.tooltip(
            translate_string(
                f"The description anybody sees before importing this {kind} from TaskerNet.  It can be plain text "
                "or HTML, with buttons to write the tags.\n"
                + (
                    "Changes here are applied to the loaded backup as soon as you press Ok in the description "
                    "window -- like Rename and the Enabled switch, Cancel does not undo them."
                    if on_applied is not None
                    else "Changes here are kept when you press Ok in this window, and are saved along with "
                    "everything else when you save."
                ),
            ),
        ).style("white-space: pre-wrap")
    return button
