"""guiwins_diagram: the Diagram view's own drawing -- connector spans, line wrapping, and its toolbar.

The Diagram is plain text, so the arrows are drawn as spans over its lines; the export menu and the tools that
step through the connectors live here with them."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from maptasker.src.core.maputil2 import translate_string
from maptasker.src.mapgen import diagintr, mapexport
from maptasker.src.mapgen.diagutil import icon_spans

if TYPE_CHECKING:
    from maptasker.src.core.primitem import RunState
    from maptasker.src.gui.guiwins_textview import NiceGuiTextView


# ==========================================
# THE DIAGRAM'S TOOLBAR AND DRAWING
# ==========================================
def _escape_html_text(text: str) -> str:
    """Escape plain text for safe embedding in HTML (the Diagram file has no markup of its own)."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# The class that holds an icon to exactly two columns (see .mt-w in maptasker.css).
ICON_CLASS = "mt-w"


def _escape_diagram_text(text: str) -> str:
    """Escape a stretch of a Diagram line, with each icon in it fixed at two columns wide.

    The diagram is laid out in Python on the basis that an icon takes two columns, but the
    browser draws it at whatever width its picture font gives it -- in Menlo, about one and
    two thirds -- so everything after an icon on the line would drift out of line with the
    connectors above and below.  An element of the width the layout assumed puts it right.
    """
    pieces = []
    cursor = 0
    for start, end in icon_spans(text):
        pieces.append(_escape_html_text(text[cursor:start]))
        pieces.append(f'<span class="{ICON_CLASS}">{_escape_html_text(text[start:end])}</span>')
        cursor = end
    pieces.append(_escape_html_text(text[cursor:]))
    return "".join(pieces)


def diagram_connectors_by_line(state: RunState) -> dict[int, list[tuple[int, int, int]]]:
    """Invert PrimeItems.diagram_connectors (id -> ranges) into line_num -> (start, end, id)."""
    by_line: dict[int, list[tuple[int, int, int]]] = {}
    for connector_id, ranges in getattr(state, "diagram_connectors", {}).items():
        for line_num, col_start, col_end in ranges:
            by_line.setdefault(line_num, []).append((col_start, col_end, connector_id))
    return by_line


def _diagram_spans(
    line_num: int,
    line: str,
    connectors_by_line: dict[int, list[tuple[int, int, int]]],
    nodes_by_line: dict[int, list[dict]],
) -> list[tuple[int, int, str]]:
    """Every span to wrap on this line, in column order and never overlapping.

    Two kinds of span want the same characters now: a connector's run of box-drawing
    characters, and an object's name.  A Task is drawn as "└─ Backup", and the "─" in that
    prefix is a connector character -- so a horizontal run passing close by can, rarely,
    grow into it.  An element cannot be in two spans at once, so the object name wins and
    the connector is clipped around it: losing a character off the end of a connector costs
    a click target that the rest of the same connector still offers, while losing one off a
    name costs the name its click target outright.
    """
    claimed = []
    for node in nodes_by_line.get(line_num, []):
        start, end = node["col"], node["col"] + node["len"]
        if start >= len(line) or end <= start:
            continue
        claimed.append(
            (
                start,
                min(end, len(line)),
                (
                    f'<span class="{diagintr.NODE_CLASS}" data-anchor="{node["anchor"]}" '
                    f'data-node="{node["index"]}" data-kind="{node["kind"]}" tabindex="0">'
                ),
            ),
        )
    claimed.sort()

    spans = list(claimed)
    for col_start, col_end, connector_id in sorted(connectors_by_line.get(line_num, [])):
        start, end = max(col_start, 0), min(col_end, len(line))
        opening = f'<span class="connector" data-connector-id="{connector_id}">'
        # Split around every name this run touches, keeping the pieces that are still the
        # connector's own.  Almost always one piece, unchanged.
        for name_start, name_end, _ in claimed:
            if name_start >= end or name_end <= start:
                continue
            if start < name_start:
                spans.append((start, name_start, opening))
            start = max(start, name_end)
        if start < end:
            spans.append((start, end, opening))
    spans.sort()
    return spans


def create_export_menu(view: NiceGuiTextView) -> None:
    """The Map and Diagram views' 'Export' button, and the menu of formats under it.

    One button with a menu rather than a button per format: the Diagram's toolbar is full
    already, and the three are one decision.  What is exported is read from the file the
    view was drawn from (see mapexport), so what is saved is what is on screen.
    """
    what = mapexport.DIAGRAM if view.title.startswith("Diagram") else mapexport.MAP
    with ui.button(translate_string("Export"), icon="file_download").classes("bg-blue-600"):
        ui.tooltip(
            translate_string(
                "'Export' saves what this view shows to a file in the Output Folder:\n\n"
                "Markdown, for a wiki page, an issue or a note.\n"
                "JSON, for a script to read.\n"
                "PDF, for printing or sending, with searchable text and bookmarks.\n\n",
            ),
            # Beside the button, not under it, where it would sit on top of the open menu.
        ).props('anchor="center right" self="center left"').style("white-space: pre-wrap")
        with ui.menu():
            for fmt, label in mapexport.FORMATS.items():
                ui.menu_item(label, on_click=lambda _e=None, chosen=fmt: view.export_event(what, chosen))


def create_diagram_tools(view: NiceGuiTextView) -> None:
    """The Diagram view's own controls: zoom, folding, and a way back to a plain diagram.

    Everything here is a shortcut for something the diagram itself already offers -- a
    Project folds by clicking its top border, a chain lights up by shift-clicking a Task --
    with the exception of zoom, which has nowhere else to live.  They are on the toolbar
    because a diagram of forty Projects is a lot of borders to click, and because a control
    on screen is how anyone finds out that the diagram does this at all.

    The state label is the one thing here that is not a button: it is written to from the
    browser (see diagintr.report) rather than from Python, since every one of these actions
    happens in the page and never comes back.
    """
    ui.separator().props("vertical")
    with ui.row().classes("items-center gap-1"):
        zoom_out = ui.button(
            icon="zoom_out",
            on_click=lambda: view.diagram_command("zoom", 1 / 1.15),
        ).props(
            "flat dense",
        )
        with zoom_out:
            ui.tooltip(translate_string("Zoom out.  Ctrl/⌘ and the scroll wheel does the same."))
        zoom_in = ui.button(icon="zoom_in", on_click=lambda: view.diagram_command("zoom", 1.15)).props(
            "flat dense",
        )
        with zoom_in:
            ui.tooltip(translate_string("Zoom in.  Ctrl/⌘ and the scroll wheel does the same."))
        collapse = ui.button(
            icon="unfold_less",
            on_click=lambda: view.diagram_command("collapse-all"),
        ).props(
            "flat dense",
        )
        with collapse:
            ui.tooltip(
                translate_string(
                    "Collapse every Project down to its title bar.\n\n"
                    "One Project on its own collapses by clicking the top edge of its box.",
                ),
            ).style("white-space: pre-wrap")
        expand = ui.button(icon="unfold_more", on_click=lambda: view.diagram_command("expand-all")).props(
            "flat dense",
        )
        with expand:
            ui.tooltip(translate_string("Expand every collapsed Project."))
        reset = ui.button(icon="restart_alt", on_click=lambda: view.diagram_command("reset")).props(
            "flat dense",
        )
        with reset:
            ui.tooltip(translate_string("Back to the whole diagram: no zoom, nothing folded, nothing filtered."))
        # The one place the gestures are written down.  Everything the diagram does on a
        # click is discoverable by trying it, but only if you already suspect it is there.
        help_button = ui.button(icon="help_outline").props("flat dense")
        with help_button:
            ui.tooltip(
                translate_string(
                    "The diagram is clickable:\n\n"
                    "Click a Project, Profile, Task or Scene name to be taken to it in the Map.\n\n"
                    "Shift-click a Task to light up the whole chain of calls it takes part in -- "
                    "everything it calls, everything that calls it, and the arrows between them.\n\n"
                    "Right-click any name for the rest: collapse its Project, show only that "
                    "Project, follow its chain.\n\n"
                    "Click the ▾ beside a Project to collapse it, and the ▸ to bring it back.\n\n"
                    "Ctrl (or ⌘) and the scroll wheel zooms.  Esc clears a chain.",
                ),
            ).style("white-space: pre-wrap")
    view.diagram_state_label = ui.label("").classes("text-xs text-gray-400 italic ml-1")


def wrap_diagram_line(
    line_num: int,
    line: str,
    connectors_by_line: dict[int, list[tuple[int, int, int]]],
    nodes_by_line: dict[int, list[dict]],
    folds_by_line: dict[int, str],
) -> str:
    """One Diagram line as its own element, with its connectors and its names inside it.

    A line is an element rather than a run of text between two newlines because the
    interactive view has to be able to take one away -- folding a Project hides its lines,
    and there is no way to hide a stretch of text that is not an element.

    The newline is inside the element and hidden with it, in a span of its own that is
    never displayed: the line elements are blocks, so the browser breaks between them
    anyway, and a newline that rendered as well would double-space the whole diagram.  It
    is still in the text, though, and that is deliberate -- the view's search index and the
    jump into the Diagram both count lines by counting newlines through the text nodes, and
    a document with none would leave both of them measuring one enormous line.  An
    otherwise empty line carries a zero-width space for the same kind of reason: an empty
    block has no height, and the blank lines in a diagram are the ones the connectors are
    drawn down.
    """
    pieces = []
    cursor = 0
    for start, end, opening in _diagram_spans(line_num, line, connectors_by_line, nodes_by_line):
        begin = max(start, cursor)
        if begin >= end:
            continue
        if begin > cursor:
            pieces.append(_escape_diagram_text(line[cursor:begin]))
        pieces.append(f"{opening}{_escape_diagram_text(line[begin:end])}</span>")
        cursor = end
    if cursor < len(line):
        pieces.append(_escape_diagram_text(line[cursor:]))
    if not pieces:
        pieces.append("&#8203;")

    fold = folds_by_line.get(line_num)
    fold_attribute = f' data-fold="{fold}" data-fold-state="open"' if fold else ""
    return (
        f'<span class="{diagintr.LINE_CLASS}" data-line="{line_num}"{fold_attribute}>'
        f'{"".join(pieces)}<span class="mt-dnl">\n</span></span>'
    )
