"""The rendered views: Map, Diagram and Misc (NiceGuiTextView), Tree, and Scene Preview.

Split out of guiwins.py, which after the dialog families left still held all three views
and everything they draw with.  What is here:

  * The three view classes.
  * What the text view streams its content through -- the HTML clean-up applied to the
    Map file (HTML_OPTIMIZE_PATTERN) and the splitter that cuts it into socket-sized
    chunks without leaving an element open across a cut (split_for_streaming).
  * The Diagram's own drawing: connector spans, line wrapping, and its toolbar.
  * The toolbar's scope badge, and the Scene editor session -- the hand-off that lets the
    Edit Scene dialog step aside for a Scene Preview and come back.

Search, Find and Replace are in guiwins_search.py, which NiceGuiTextView inherits them
from; the registry of open views and the jumps into them are in guiwins_nav.py.  Both sit
below this module, and guiwins.py above it.
"""

from __future__ import annotations

import asyncio
import contextlib
import re
from typing import TYPE_CHECKING

from nicegui import Event, run, ui

from maptasker.src import (
    diagintr,
    mapexport,
    mapfind,
    mapjump,
    sceneedit,
    sceneedit_v2,
    sceneview,
)
from maptasker.src.format import css_color
from maptasker.src.guiwins_canvas import (
    _ACTIVE_CANVASES,
    CANVAS_PREVIEW_ROOT,
    _emit_canvas_editing,
    _emit_canvas_fit,
    _emit_v2_dragging,
    _emit_v2_hull,
    _register_canvas_events,
)
from maptasker.src.guiwins_designer_legacy import (
    _legacy_canvas_size,
)
from maptasker.src.guiwins_nav import (
    _report_view_failure,
    enable_finding_clicks,
    live_views,
    register_finding_clicks,
    register_view,
)
from maptasker.src.guiwins_search import (
    SEARCH_JAVASCRIPT_TIMEOUT,
    TextViewSearch,
)
from maptasker.src.maputil2 import translate_string
from maptasker.src.outdir import output_path
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import (
    DIAGRAM_FILE,
    logger,
)

if TYPE_CHECKING:
    from maptasker.src.userintr import MyGui


# ==========================================
# THE SCENE EDITOR SESSION
# ==========================================
# How the Edit Scene dialog and a Scene Preview hand the screen back and forth: the dialog
# steps aside for the picture, and the picture's "Back to Editor" brings it back.
def repaint_scene_previews(gui: MyGui, dialog: ui.dialog) -> None:
    """Redraw every Scene preview this dialog put on screen.

    WHY A DIALOG CLOSING HAS TO REACH THE PICTURE BEHIND IT.  A preview draws from the
    dialog's live state -- for a Legacy Scene, edited_scene.scene_element itself -- and then
    never looks at it again; it repaints on its own toolbar, its own gestures and its own
    Refresh button, none of which is what just happened.  So the sequence Preview, Back to
    Editor, move something in the designer, Ok leaves the picture the user is returned to
    showing the geometry from before the move, with nothing on screen to say it is out of
    date.  Repainting is a few hundred divs and the state it reads is already in hand.

    Matched on the dialog the view was launched from rather than on the Scene's name,
    because that is the relationship that actually holds: a view holds the dialog it has to
    re-open, names can be changed by the Rename button mid-session, and two dialogs on the
    same Scene are a thing this app can produce (see _build_item_layout_dialog).

    Deliberately not called when Preview is what closed the dialog: that path is on its way
    to building a *new* view over a cleared content_container, and repainting the outgoing
    one into a container about to be emptied is work at best and a draw into a detached
    element at worst.  See preview_scene_event, which marks the session suspended first so
    that _scene_dialog_closed can tell the two apart.
    """
    for view in live_views(gui):
        if isinstance(view, NiceGuiSceneView) and getattr(view, "dialog", None) is dialog:
            view.render()


def _scene_dialog_closed(gui: MyGui, dialog: ui.dialog, field_refs: dict, event: Event) -> None:
    """One place every way of closing a Scene dialog goes through.

    Hung on the dialog's own value rather than on its buttons because there are eight of
    them across the two dialogs -- Cancel, Ok, Delete, Rename, three kinds of Save, Export --
    and they close it through six different event handlers in userintr_editors.  A ninth button
    added later would be one more that forgot to repaint; the value cannot be.

    THE PREVIEW STOPS BEING AN EDITING SURFACE HERE, which is half of drawing the right
    thing rather than merely a fresh thing.  A preview is editable only while the designer
    that opened it is alive to take the edit (see NiceGuiSceneView._legacy_editing), and
    these two keys are how it finds one -- but the handlers in them outlive the dialog,
    because NiceGUI hides a dialog rather than destroying it.  Left in place, the repainted
    picture would go on offering drags into an editor the user has just finished with: after
    Cancel they would land on a deep copy that was abandoned by definition, and after Ok on
    one whose contents have already been written to the live tree.  Both would move on
    screen, and neither would reach the Scene.  Dropping the keys turns the picture back
    into a picture, which is what it now is.
    """
    if event.value:
        return  # opening, not closing
    session = getattr(gui, "scene_editor_session", None)
    if session and session.get("dialog") is dialog and session.get("suspended"):
        return  # Preview is holding it hidden -- see repaint_scene_previews
    for key in ("v2_edit", "legacy_edit"):
        field_refs.pop(key, None)
    repaint_scene_previews(gui, dialog)


def suspend_scene_editor_session(gui: MyGui, dialog: ui.dialog) -> None:
    """Mark the Edit Scene dialog as hidden-but-alive, which is what Preview does to it.

    Only the Edit Scene dialog is tracked (build_edit_scene_dialog records it); previewing
    from Add Scene finds no match here and is left alone, so nothing can resume a half-built
    Scene that is not in the tree yet.
    """
    session = getattr(gui, "scene_editor_session", None)
    if session and session.get("dialog") is dialog:
        session["suspended"] = True


def _resume_scene_editor_session(gui: MyGui, dialog: ui.dialog) -> None:
    """Clear the suspended mark -- the dialog is being put back on screen."""
    session = getattr(gui, "scene_editor_session", None)
    if session and session.get("dialog") is dialog:
        session["suspended"] = False


def suspended_scene_editor(gui: MyGui, scene_name: str) -> ui.dialog | None:
    """The Edit Scene dialog for `scene_name` that a preview is currently holding hidden,
    or None if there isn't one.  Resuming is the caller's job; this marks it resumed.

    The mark exists only between Preview closing the dialog and something re-opening it, so
    a dialog closed for good by Cancel/Ok/Delete is never handed back: those all run while
    the dialog is on screen, which by definition is not suspended.
    """
    session = getattr(gui, "scene_editor_session", None)
    if not session or not session.get("suspended") or session.get("name") != scene_name:
        return None
    session["suspended"] = False
    return session["dialog"]


# ==========================================
# STREAMING THE MAP INTO THE TEXT VIEW
# ==========================================
# Pre-compile the regex pattern at the module level for maximum execution performance.
# This scans the HTML string and hits all target replacements in a single pass O(N).
#
# Most of what it does is about newlines, because this view shows the Map as preformatted
# text (see the wrap classes in build_ui) and a browser draws every newline in
# preformatted text as a line break.  A browser opening the saved file draws none of them:
# they are the file's own formatting, one after every <br> and one between the tags of
# each line, and there are tens of thousands.  Drawn, each one is an extra line -- and a
# blank line wherever the Map had already ended that line with a <br>, which is why a
# section heading in this view sat three and four blank lines below the section above it
# while the same file opened in a browser showed one.
#
# So a newline that touches a tag goes: it is the file's formatting, not the Map's.  A
# newline with text on both sides is the author's -- a Tasker value written over several
# lines -- and stays, as the one line break it asks for.  What this no longer does is
# throw <br>s away: it used to fold "<br><br>" down to one, from the days when the file
# arrived with gap after gap of blank lines in it.  bildhtml now writes that file through
# format.BlankLineLimiter, which keeps every gap to MAX_BLANK_LINES, so a second squeeze
# here only fought the first.
HTML_OPTIMIZE_PATTERN = re.compile(
    r"(?P<formatting>(?<=>)[ \t]*[\r\n]+|[\r\n]+[ \t]*(?=<))"
    r"|(?P<written>[\r\n]{2,})"
    r"|(?P<heading><h2>MapTasker</h2>|<h2><span class=\"normtab\"></span>Directory</h2>)",
)


# Map the targeted string matches directly to their optimized counterparts.
HTML_REPLACEMENT_MAP = {
    "<h2>MapTasker</h2>": '<a id="the_top"></a><h5>MapTasker</h5>',
    '<h2><span class="normtab"></span>Directory</h2>': '<h6><span class="normtab"></span>Directory</h6>',
}


def optimize_html(match: re.Match) -> str:
    """
    What one match of HTML_OPTIMIZE_PATTERN becomes -- see the note above it.

        :param match: the matched formatting, written newlines, or heading
        :return: what to put in its place
    """
    if match.lastgroup == "formatting":
        return ""  # The file's own line endings, which this view would otherwise draw.
    if match.lastgroup == "written":
        return "\n"  # The author's own, and one line break is all they asked for.
    return HTML_REPLACEMENT_MAP[match.group(0)]


# How the Map is cut up for the browser (see split_for_streaming).
#
# 256KB a piece, which on a large configuration is of the order of a hundred pieces: small
# enough that the browser can put the top of the Map on screen while the rest is still
# arriving, and few enough that the per-piece cost -- an element, a websocket message and
# the tags re-stated across the cut -- stays in the noise.
STREAM_CHUNK_BYTES = 262144


HTML_ELEMENT = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9-]*)[^>]*?(/?)>")


# Elements with no end tag of their own; nothing is left open by one.
VOID_ELEMENTS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"},
)


# The page's own frame, which the view never sees the end of and must not try to re-state.
FRAME_ELEMENTS = frozenset({"html", "head", "body"})


# Starting one of these closes an open <p>, which is a thing a browser does and the Map's
# html relies on: a TaskerNet description writes "<p>" and leaves it to the next block.
CLOSE_AN_OPEN_PARAGRAPH = frozenset(
    {
        "address",
        "article",
        "aside",
        "blockquote",
        "details",
        "div",
        "dl",
        "fieldset",
        "figure",
        "footer",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "ul",
    },
)


# An id belongs to the element where it opened.  Where a cut re-states that element in the
# next piece, the id is dropped, so that a Task action's anchor stays the one place in the
# document it names (see split_for_streaming).
ELEMENT_ID = re.compile(r'\s+id="[^"]*"')


def split_for_streaming(html: str, budget: int = STREAM_CHUNK_BYTES) -> list[str]:
    """Cut the Map into pieces the browser can render one at a time.

    WHY THIS IS NOT A SPLIT ON LINES.  It was, and the line it split on had already been
    taken out.  The view splits the file after HTML_OPTIMIZE_PATTERN has run over it, and
    what that pattern removes is precisely the newline between one tag and the next -- so
    a Map of twenty megabytes arrived here as a couple of hundred "lines" and left as a
    single piece.  One element holding the whole Map is the worst shape it could be in:
    the browser parses all of it before it shows any of it, lays out every one of its two
    hundred thousand elements because "content-visibility: auto" can only skip an element
    whole, and it all crosses the socket in one message.  That is the wait.

    WHAT A CUT COSTS.  The Map's colours are <span>s that are opened on one line and
    closed several lines later, so at most points in the document something is open.  A
    piece therefore ends by closing what is open and the next begins by opening it again,
    which is why this returns pieces that do not concatenate back into the original text
    -- they render as it, which is the thing that has to be true.  On a large Map the
    re-stated tags come to well under a tenth of its size.

    :param html: the whole Map, as the view has optimized it
    :param budget: how many bytes to aim for in a piece
    :return: the pieces, in order
    """
    open_elements: list[tuple[str, str]] = []  # (tag name, the markup that opened it)
    pieces: list[str] = []
    start = 0
    carried = ""  # the tags this piece has to re-state because a cut fell inside them

    for element in HTML_ELEMENT.finditer(html):
        closing, name, self_closing = element.group(1), element.group(2).lower(), element.group(3)
        if name in FRAME_ELEMENTS or name in VOID_ELEMENTS or self_closing:
            pass
        elif closing:
            # Everything opened inside the element being closed is closed with it, which
            # is what the browser does with markup that never closed it explicitly.
            for index in range(len(open_elements) - 1, -1, -1):
                if open_elements[index][0] == name:
                    del open_elements[index:]
                    break
        else:
            if open_elements and open_elements[-1][0] == "p" and name in CLOSE_AN_OPEN_PARAGRAPH:
                open_elements.pop()
            open_elements.append((name, element.group(0)))

        if element.end() - start >= budget:
            closers = "".join(f"</{tag}>" for tag, _ in reversed(open_elements))
            pieces.append(f"{carried}{html[start : element.end()]}{closers}")
            carried = "".join(ELEMENT_ID.sub("", markup, count=1) for _, markup in open_elements)
            start = element.end()

    if start < len(html):
        pieces.append(f"{carried}{html[start:]}")
    return pieces


# ==========================================
# THE DIAGRAM'S TOOLBAR AND DRAWING
# ==========================================
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
                f'<span class="{diagintr.NODE_CLASS}" data-anchor="{node["anchor"]}" '
                f'data-node="{node["index"]}" data-kind="{node["kind"]}" tabindex="0">',
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


def _create_export_menu(view: NiceGuiTextView) -> None:
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


def _create_diagram_tools(view: NiceGuiTextView) -> None:
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
            on_click=lambda: view._diagram_command("zoom", 1 / 1.15),
        ).props(
            "flat dense",
        )
        with zoom_out:
            ui.tooltip(translate_string("Zoom out.  Ctrl/⌘ and the scroll wheel does the same."))
        zoom_in = ui.button(icon="zoom_in", on_click=lambda: view._diagram_command("zoom", 1.15)).props(
            "flat dense",
        )
        with zoom_in:
            ui.tooltip(translate_string("Zoom in.  Ctrl/⌘ and the scroll wheel does the same."))
        collapse = ui.button(
            icon="unfold_less",
            on_click=lambda: view._diagram_command("collapse-all"),
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
        expand = ui.button(icon="unfold_more", on_click=lambda: view._diagram_command("expand-all")).props(
            "flat dense",
        )
        with expand:
            ui.tooltip(translate_string("Expand every collapsed Project."))
        reset = ui.button(icon="restart_alt", on_click=lambda: view._diagram_command("reset")).props(
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


def _wrap_diagram_line(
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
        start = max(start, cursor)  # noqa: PLW2901
        if start >= end:
            continue
        if start > cursor:
            pieces.append(_escape_html_text(line[cursor:start]))
        pieces.append(f"{opening}{_escape_html_text(line[start:end])}</span>")
        cursor = end
    if cursor < len(line):
        pieces.append(_escape_html_text(line[cursor:]))
    if not pieces:
        pieces.append("&#8203;")

    fold = folds_by_line.get(line_num)
    fold_attribute = f' data-fold="{fold}" data-fold-state="open"' if fold else ""
    return (
        f'<span class="{diagintr.LINE_CLASS}" data-line="{line_num}"{fold_attribute}>'
        f'{"".join(pieces)}<span class="mt-dnl">\n</span></span>'
    )


# ==========================================
# THE VIEWS
# ==========================================
def scope_badge_text(built_for: str, now: str) -> tuple[str, str]:
    """What the toolbar badge says: (what this view was drawn for, what has changed since).

    The second half is "" when the two agree, which is what the view shows and hides the
    stale line and the Rebuild button by.  Both halves name the selection in the words the
    pulldowns use ("Project 'Home'", "Task 'Wake Up'"), and the whole configuration is said
    rather than left as a blank, because a badge reading "Drawn for" and then nothing looks
    like something failed to load.
    """
    everything = translate_string("the whole configuration")
    drawn = f"{translate_string('Drawn for')} {built_for or everything}"
    if (built_for or "") == (now or ""):
        return drawn, ""
    return drawn, f"-- {translate_string('now showing')} {now or everything}"


def refresh_scope_badges(master_gui: MyGui) -> None:
    """Tell every open view that the single-item selection has changed.

    Called from the one funnel a changed selection goes through (userintr_loading.process_name_event),
    so a Diagram drawn for the old selection says so the moment the user picks a new one
    rather than the next time they happen to look at its toolbar.

    Touches text and visibility on elements that already exist, which is what makes it safe
    from a pulldown's handler in the MAIN window: those elements belong to the popout's
    client, and NiceGUI sends a property change to whichever client owns the element.
    Creating one there would be the problem -- see register_finding_clicks on what building
    into a live page costs.
    """
    for view in live_views(master_gui):
        try:
            view.refresh_scope_badge()
        except (AttributeError, RuntimeError):
            continue  # A view without a badge, or one whose page went away mid-update.


def view_theme_colors(master_gui: MyGui) -> tuple[str, str]:
    """The (background, foreground) a view should paint itself with right now.

    Same pair the dark-mode toggle hands to the drawers, panels and text views, so a view
    that has to colour itself at build time -- the toggle's on_change only fires when the
    switch is actually clicked -- lands on exactly what the rest of the window is using.
    Defaults to light when the switch has never been touched, which is the state the page
    starts in (ui.dark_mode() mounts disabled regardless of the switch's initial value).
    """
    is_dark = bool(getattr(master_gui, "dark_mode", False))
    bg = "#1e293b" if is_dark else "#ffffff"
    fg = "#ffffff" if is_dark else "#000000"
    return (getattr(master_gui, "color_lookup", None) or {}).get("background", bg), fg


class NiceGuiTreeView:
    """Replaces CTkTreeview. Renders a hierarchical tree representation in the main view column."""

    def __init__(self, master_gui: MyGui, title: str, items: list) -> None:
        """Initialize the Tree view with a title and hierarchical items."""
        self.master_gui = master_gui
        self.title = title
        self.build_ui(items)
        register_view(master_gui, self)

    def build_ui(self, items: list) -> None:
        """Build the base UI layout for the Tree view inside the main content container slot."""

        # 1. Target and clear the dedicated full-width main view column slot
        if hasattr(self.master_gui, "content_container") and self.master_gui.content_container:
            self.master_gui.content_container.clear()
            container_context = self.master_gui.content_container
        else:
            container_context = ui.column()  # Fallback context if called standalone

        # 2. Render the layout inside the main application body container
        with container_context:
            self.card = ui.card().classes(
                "maptasker-tree-card w-full max-w-full mx-auto p-6 shadow-md border-2 border-gray-300",
            )
            with self.card:
                # Header row with title and navigation hints
                with ui.row().classes("items-center justify-between w-full border-b pb-3 mb-4"):
                    ui.label(f"{self.title}").classes("text-orange-500 font-bold text-lg")
                    ui.label(translate_string("Click arrows to expand/collapse details.")).classes(
                        "text-xs text-gray-500 italic",
                    )

                # Convert MapTasker nested dictionary list nodes to NiceGUI tree notation
                tree_data = self._format_data(items)

                # 3. Create a scrollable window container for large tree structures
                self.scroll_area = ui.scroll_area().classes("w-full h-[65vh] p-2")
                with self.scroll_area:
                    # Render the native responsive Tree component
                    # Injected custom fonts to preserve monospace formatting matches
                    self.tree = (
                        ui.tree(tree_data, label_key="label", children_key="children", tick_strategy="none")
                        .classes("w-full text-base")
                        .style(f"font-family: '{self.master_gui.font}', monospace;")
                    )

        self.apply_theme(*view_theme_colors(self.master_gui))

    def apply_theme(self, bg: str, fg: str) -> None:
        """Paint this view's card and scroll area for the mode the window is currently in.

        Unlike the Map/Diagram views -- whose scroll area the dark-mode toggle restyles by
        hand -- the Tree view's container used to carry no colours of its own, leaving it to
        whichever stylesheet rule won the cascade for .q-card / .q-scrollarea. That is a
        fragile thing to depend on across browsers and NiceGUI/Quasar releases (it is what
        left this one container white in dark mode), so state the colours outright instead.
        "!important" for the same reason the Map view's background needs it: it has to beat
        the equally-important light/dark overrides injected by inject_shared_head_styles().
        The node labels follow along through the .maptasker-tree-card rule in that same
        stylesheet, which hands them this card's colour instead of Quasar's theme colour.
        """
        style = f"background-color: {bg} !important; color: {fg} !important;"
        self.card.style(style)
        self.scroll_area.style(style)

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
                    raw_name.replace("&nbsp;", " ")
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


class NiceGuiSceneView:
    """Draws a Scene as a picture in the main content column -- what the Preview button on
    the Add/Edit Scene dialogs opens.  The drawing itself is sceneview.py; this is the frame
    round it: the toolbar, the scaling, and the way back to the dialog.

    THE DIALOG HAS TO GET OUT OF THE WAY.  content_container sits behind a modal overlay, so
    a preview drawn while the Scene dialog is up would be invisible underneath it.  The
    dialog is therefore closed before this is built and re-opened by this view's own "Back to
    Editor" button.  Closing a NiceGUI dialog only hides it -- its widgets are not destroyed
    -- so every field the user has typed into and not yet saved is still there when they go
    back, which is the entire reason it is closed rather than cancelled.

    That is also why this takes field_refs rather than reading the Scene: the preview shows
    what is currently *typed into* the dialog, not what was last saved.  For a Legacy Scene
    that is the four size fields, so previewing is a way to try a canvas size out; for a
    Version 2 Scene it is the live layout dict the designer edits in place (field_refs
    ["v2_layout"]), so previewing shows components added, moved and retyped a moment ago.
    A Legacy size that isn't a whole number is reported and the saved one used, matching what
    userintr_editors._apply_scene_field_values would say about it at save time rather than inventing a
    second opinion.

    THE PICTURE IS ALSO AN EDITING SURFACE, for both kinds of Scene, whenever the designer
    that opened it is still alive: components are dragged into a new order here (V2) and
    elements are selected, moved and resized here (Legacy).  It edits nothing itself.  Every
    gesture is handed straight to that designer's own handlers -- see _v2_from_canvas and
    _legacy_from_canvas -- so an edit made in the picture goes on the same undo stack, and
    through the same code, as the identical edit made in the dialog.  A second implementation
    of "move an element" living here is exactly what this arrangement exists to avoid.

    THE TWO KINDS OF SCENE NEED DIFFERENT CONTROLS, so the toolbar is built per kind rather
    than shown-and-disabled.  A Legacy Scene needs a text density (its canvas size is its own)
    and a Landscape toggle that is meaningless unless it has a second layout; a V2 Scene needs
    a screen size (it has no size at all) and a Landscape toggle that always means something,
    and has no use for a density because dp is already density-independent.  Offering all four
    to both would mean two controls that do nothing on whichever Scene is open.

    Registered with register_view like the Map/Diagram/Tree views, so Clear View disposes of
    it and the dark-mode toggle repaints it.  The canvas itself deliberately does NOT follow
    dark mode: it is painted with the Scene's own background colour (Legacy) or the Material
    palette (V2), and letting this app's appearance change what the Scene appears to look like
    would defeat the point of it.
    """

    # The zoom pulldown.  "Fit" is not a number because the width it has to fit is the
    # browser's, which only the browser knows -- see _apply_scale.
    ZOOM_CHOICES = ("Fit", "25%", "50%", "75%", "100%", "150%", "200%")

    def __init__(
        self,
        master_gui: MyGui,
        edited_scene: sceneedit.EditableScene,
        field_refs: dict,
        dialog: ui.dialog | None = None,
    ) -> None:
        """Build the preview and draw it."""
        self.master_gui = master_gui
        self.edited_scene = edited_scene
        self.field_refs = field_refs
        self.dialog = dialog
        self.title = f"{translate_string('Scene Preview')}: {edited_scene.scene_name}"
        self.is_v2 = sceneedit.is_v2_scene(edited_scene.scene_element)
        self.options = sceneview.PreviewOptions()
        self.zoom = "Fit"
        self.screen = sceneview.V2_DEFAULT_SCREEN
        _register_canvas_events()
        self.build_ui()
        self.render()
        register_view(master_gui, self)

    # ---------- layout ----------
    def build_ui(self) -> None:
        """Toolbar, then the scroll area the canvas is drawn into."""
        if hasattr(self.master_gui, "content_container") and self.master_gui.content_container:
            self.master_gui.content_container.clear()
            container_context = self.master_gui.content_container
        else:
            container_context = ui.column()

        with container_context:
            self.card = ui.card().classes("w-full max-w-full mx-auto p-4 shadow-md border-2 border-gray-300")
            with self.card:
                with ui.row().classes("w-full items-center gap-2 flex-wrap") as self.gui_toolbar:
                    ui.label(self.title).classes("text-orange-500 font-bold mr-2")
                    if self.dialog is not None:
                        ui.button(
                            translate_string("Back to Editor"),
                            icon="arrow_back",
                            on_click=self._back_to_editor,
                        ).classes("bg-blue-600")
                    ui.button(translate_string("Refresh"), icon="refresh", on_click=self.render).classes("bg-blue-600")
                    ui.separator().props("vertical")

                    self._build_orientation_control()

                    ui.select(
                        list(self.ZOOM_CHOICES),
                        value=self.zoom,
                        label=translate_string("Zoom"),
                        on_change=self._zoom_selected,
                    ).props("dense").classes("w-28")

                    if self.is_v2:
                        self._build_screen_control()
                    else:
                        self._build_density_control()
                        self._build_snap_control()

                    ui.switch(
                        translate_string("Bounds"),
                        value=self.options.show_bounds,
                        on_change=lambda event: self._set_option("show_bounds", bool(event.value)),
                    ).props("dense").tooltip(
                        (
                            translate_string(
                                "Outline every component and name it, the way the designer's tree names it.",
                            )
                            if self.is_v2
                            else translate_string("Outline every element and name it.")
                        ),
                    )
                    ui.switch(
                        translate_string("Actions") if self.is_v2 else translate_string("Tasks"),
                        value=self.options.show_tasks,
                        on_change=lambda event: self._set_option("show_tasks", bool(event.value)),
                    ).props("dense").tooltip(
                        (
                            translate_string("Show what each component does when tapped, and what it writes to.")
                            if self.is_v2
                            else translate_string("Show the Task each element runs.")
                        ),
                    )

                self.scroll_area = ui.scroll_area().classes("w-full h-[70vh] p-2")
                with self.scroll_area:
                    # Two nested elements on purpose: the outer one is what the fit
                    # calculation measures and what reserves the scaled height in the page's
                    # flow, the inner one is the true-size canvas that gets transformed. A
                    # transform does not affect layout, so without the outer element the page
                    # would reserve room for the canvas at full size however far it is
                    # scaled down.
                    self.canvas_wrap = (
                        ui.element("div")
                        .classes(f"mt-scene-wrap {CANVAS_PREVIEW_ROOT}")
                        .style(
                            "position: relative; width: 100%; overflow: hidden;",
                        )
                    )
                self.caption = ui.column().classes("w-full gap-0 mt-2")

        self.apply_theme(*view_theme_colors(self.master_gui))

    def _build_orientation_control(self) -> None:
        """The Landscape toggle, which means two different things.

        For a Legacy Scene it selects the Scene's *second stored layout* -- the landscape half
        of every <geom> -- and most Scenes do not have one, so it is disabled and says why.
        For a V2 Scene there is no second layout to select: it turns the frame on its side and
        lets the tree re-flow into it, which is exactly what the Scene would do on a phone, so
        it is always available.
        """
        if self.is_v2:
            ui.switch(
                translate_string("Landscape"),
                value=False,
                on_change=lambda event: self._set_option("landscape", bool(event.value)),
            ).props("dense").tooltip(
                translate_string("Turn the screen on its side and let the layout re-flow into it."),
            )
            return

        has_landscape = sceneview.has_landscape_layout(self.edited_scene.scene_element)
        landscape_switch = ui.switch(
            translate_string("Landscape"),
            value=False,
            on_change=lambda event: self._set_option("landscape", bool(event.value)),
        ).props("dense")
        landscape_switch.set_enabled(has_landscape)
        if not has_landscape:
            with landscape_switch:
                ui.tooltip(translate_string("This Scene has no landscape layout of its own (its size is -1)."))

    def _build_density_control(self) -> None:
        """Legacy only: the sp-to-pixel number that is not in the backup file."""
        density_select = (
            ui.select(
                list(sceneview.DENSITY_CHOICES),
                value=str(sceneview.DEFAULT_DENSITY),
                label=translate_string("Text density"),
                on_change=self._density_selected,
            )
            .props("dense")
            .classes("w-32")
        )
        with density_select:
            ui.tooltip(
                translate_string(
                    "A Scene's element positions are stored in device pixels, but its text sizes "
                    "are stored in Android's sp units. The number that converts between the two is "
                    "a property of the phone the Scene is shown on, and is not in the backup file.\n\n"
                    "So it is set here. Raise it if the text looks too small for its elements, "
                    "lower it if the text overflows them.",
                ),
            ).style("white-space: pre-wrap")

    def _build_snap_control(self) -> None:
        """Legacy, and only when this Preview is an editing surface: the grid a dragged
        element's position rounds to.

        Built at all only when there is a designer behind this picture, because without one
        there is nothing to drag and a Snap control would be a setting for a gesture the
        Preview does not offer.  It writes the designer's own dict rather than keeping a
        number of its own, so the two canvases cannot end up snapping to different grids --
        the same sharing that puts one selection on both of them.
        """
        editor = self.field_refs.get("legacy_edit")
        if not isinstance(editor, dict):
            return
        ui.select(
            [1, 2, 5, 10],
            value=int(editor["snap"]["grid"]),
            label=translate_string("Snap"),
            on_change=self._snap_selected,
        ).props("dense").classes("w-24").tooltip(
            translate_string("Round dragged positions and sizes to this many pixels."),
        )

    def _snap_selected(self, event: Event) -> None:
        editor = self.field_refs.get("legacy_edit")
        if isinstance(editor, dict):
            editor["snap"]["grid"] = int(event.value or 1)
        self.render()

    def _build_screen_control(self) -> None:
        """Version 2 only: which screen to lay the component tree out in.

        The nearest thing V2 has to the Legacy canvas size, except that it is not a property
        of the Scene at all -- it is the question the Scene answers differently on every
        device, which is why it is a control and not a number in the file.
        """
        screen_select = (
            ui.select(
                [name for name, _width, _height in sceneview.V2_SCREENS],
                value=self.screen,
                label=translate_string("Screen"),
                on_change=self._screen_selected,
            )
            .props("dense")
            .classes("w-36")
        )
        with screen_select:
            ui.tooltip(
                translate_string(
                    "A Version 2 Scene has no size of its own -- it lays itself out inside whatever "
                    "screen it is shown on, so there is nothing in the backup file to draw it at.\n\n"
                    "Change this to see the layout re-flow. A Flow Row wraps differently, and any "
                    "'Show when' written against %sv2_render_width is asking about exactly this.",
                ),
            ).style("white-space: pre-wrap")

    def apply_theme(self, bg: str, fg: str) -> None:
        """Paint the card and scroll area for the window's current mode.  The canvas inside
        keeps the Scene's own colours -- see this class's docstring.
        """
        style = f"background-color: {bg} !important; color: {fg} !important;"
        self.card.style(style)
        self.scroll_area.style(style)

    # ---------- toolbar handlers ----------
    def _back_to_editor(self) -> None:
        """Re-open the Scene dialog this preview was launched from, with everything still
        typed into it (see this class's docstring).
        """
        if self.dialog is None:
            return
        _resume_scene_editor_session(self.master_gui, self.dialog)
        self.dialog.open()
        # Re-render whichever designer is behind this preview, which re-installs the pointer
        # handlers on its surface -- the V2 designer's tree, the Legacy designer's canvas.
        #
        # A hidden Quasar dialog does not merely hide its contents, it takes them out of the
        # document, and re-opening it puts back new elements rather than the same ones -- so
        # the handlers installed on the old pane went with it.  Everything else about the
        # designer survives, which is exactly what makes this worth doing here instead of
        # leaving the pane to look right and answer nothing until whatever the user clicked
        # next happened to re-render it.
        #
        # A Scene is one kind or the other, so only one of these two is ever present.
        for key in ("v2_edit", "legacy_edit"):
            editor = self.field_refs.get(key)
            if isinstance(editor, dict):
                editor["rerender"]()

    def _set_option(self, name: str, value: object) -> None:
        setattr(self.options, name, value)
        if name == "landscape" and not self.is_v2:
            # ONE ORIENTATION, TWO SURFACES.  A drag in this picture is applied by the
            # designer's handlers, and they write whichever half of <geom> the designer's own
            # orientation names -- so a Preview showing landscape while the designer sat in
            # portrait would take a landscape drag and rewrite the portrait layout with it,
            # silently, with the evidence on the other toggle.  Moving them together is also
            # the better behaviour on its own terms: going Back to Editor lands on the
            # orientation the user was just looking at.
            editor = self.field_refs.get("legacy_edit")
            if isinstance(editor, dict):
                editor["orientation"]["landscape"] = bool(value)
        self.render()

    def _zoom_selected(self, event: Event) -> None:
        self.zoom = str(event.value or "Fit")
        self.render()

    def _density_selected(self, event: Event) -> None:
        try:
            self.options.density = float(event.value)
        except (TypeError, ValueError):
            self.options.density = sceneview.DEFAULT_DENSITY
        self.render()

    def _screen_selected(self, event: Event) -> None:
        self.screen = str(event.value or sceneview.V2_DEFAULT_SCREEN)
        self.render()

    # ---------- drawing ----------
    def render(self) -> None:
        """Draw (or re-draw) from the dialog's current state.  Every toolbar control lands
        here rather than trying to patch the drawing in place: it is a few hundred divs,
        rebuilding is cheap, and a partial update would be a second code path that could
        disagree with the first.
        """
        self.canvas_wrap.clear()
        self.caption.clear()
        self._render_v2() if self.is_v2 else self._render_legacy()

    def _render_legacy(self) -> None:
        """A Legacy Scene: its own pixel canvas, at the size the dialog currently holds."""
        scene_element = self.edited_scene.scene_element
        dimensions = self._dimensions()
        if dimensions is None:
            orientation = "landscape" if self.options.landscape else "portrait"
            self._say(
                f"This Scene has no {orientation} layout: its size is -1, which is Tasker's "
                "'this orientation has no layout of its own'.",
                "text-orange-600",
            )
            return

        width, height = dimensions
        editing = self._legacy_editing()
        with self.canvas_wrap:
            sceneview.draw_scene(scene_element, width, height, self.options, editing=editing)
        self._apply_scale(width, height)
        if editing is not None:
            _ACTIVE_CANVASES[CANVAS_PREVIEW_ROOT] = {
                name: (lambda payload, which=name: self._legacy_from_canvas(which, payload))
                for name in ("select", "geometry", "nudge")
            }
            _emit_canvas_editing(CANVAS_PREVIEW_ROOT, editing.snap)
        self._draw_legacy_caption(scene_element, width, height)

    def _legacy_editing(self) -> sceneview.CanvasEditing | None:
        """The Preview as the Legacy designer's second canvas, or None for the picture it has
        always been.

        Editing needs the designer to still be there -- and for a different reason than the
        Version 2 half of this class needs it.  There, a Preview opened where no designer was
        built draws a layout dict decoded for this view alone, so a drag on it would look like
        it worked and quietly lose the change.  Here the Preview draws
        edited_scene.scene_element, the very element the dialog saves, so a drag WOULD stick.
        It would stick with no snapshot taken and no designer panes to agree with it: a move
        that really did change the Scene and that Undo cannot take back, which is the worse of
        the two failures rather than the milder one.
        """
        editor = self.field_refs.get("legacy_edit")
        if not isinstance(editor, dict):
            return None
        return sceneview.CanvasEditing(
            selected=tuple(editor["selection"]["srs"]),
            snap=int(editor["snap"]["grid"]),
            # Kept here, unlike on the designer's canvas: the dialog holding the Inspector
            # that made them redundant there is closed while this is up, so the tooltip is
            # the only place an element's variables and Tasks can be read.  The caption below
            # promises exactly that, and this is what keeps the promise.
            tooltips=True,
        )

    def _legacy_from_canvas(self, name: str, payload: object) -> None:
        """A click, a drag or a nudge on the picture: hand it to the designer, then redraw.

        The designer's own handlers do the work -- see the note on field_refs["legacy_edit"]
        -- so an element moved in the Preview is snapshotted, written, selected and re-listed
        by exactly the code the designer's own canvas goes through.  All that is left here is
        the half the designer cannot do, which is repainting this picture.
        """
        editor = self.field_refs.get("legacy_edit")
        if not isinstance(editor, dict):
            return
        handler = editor["handlers"].get(name)
        if handler is None:
            return
        handler(payload)
        self.render()

    def _render_v2(self) -> None:
        """A Version 2 Scene: the component tree, laid out in the chosen screen.

        The layout comes from field_refs first -- that is the dict the designer edits in
        place, so a component added or retyped in the dialog a moment ago is in the picture
        without having been saved.  Decoding the Scene is the fallback for a preview opened
        from somewhere that never built a designer.
        """
        layout = self.field_refs.get("v2_layout")
        if not isinstance(layout, dict):
            layout = sceneedit.decode_v2_layout(self.edited_scene.scene_element)
        if not isinstance(layout, dict):
            self._say(
                "This Scene's Version 2 layout could not be read, so there is nothing to draw.",
                "text-orange-600",
            )
            return

        editing = self._v2_editing()
        width, height = self._screen_size()
        with self.canvas_wrap:
            sceneview.draw_v2_layout(layout, width, height, self.options, editing=editing)
        self._apply_scale(width, height)
        # After the scale, never before: the hull is measured in screen pixels and divided
        # back by the factor _apply_scale leaves on the wrapper, and a hull measured before
        # that factor existed would be sized by whatever the last render happened to set.
        _emit_v2_hull(CANVAS_PREVIEW_ROOT, width, height)
        if editing is not None:
            _ACTIVE_CANVASES[CANVAS_PREVIEW_ROOT] = {
                "v2select": lambda payload: self._v2_from_canvas("v2select", payload),
                "v2reorder": lambda payload: self._v2_from_canvas("v2reorder", payload),
            }
            _emit_v2_dragging(
                CANVAS_PREVIEW_ROOT,
                f".{CANVAS_PREVIEW_ROOT} .mt-scene-canvas",
                "mt-v2-node",
            )
        self._draw_v2_caption(layout, width, height)

    def _v2_editing(self) -> sceneview.V2Editing | None:
        """The Preview as a reorder surface, or None for the picture it has always been.

        Editing needs two things at once, and the absence of either is what makes this a
        read-only preview: the layout being drawn has to be the *live* one the designer edits
        in place, and the designer has to still be there to take the edit -- it owns the undo
        stack a drag has to land on, and the tree that has to agree with the picture
        afterwards.  A Preview opened where no designer was built draws a dict decoded for
        this view alone, which nothing would ever save; a drag on that would look like it
        worked and quietly lose the change.
        """
        editor = self.field_refs.get("v2_edit")
        if not isinstance(editor, dict) or self.field_refs.get("v2_layout") is None:
            return None
        selection = editor["selection"]
        return sceneview.V2Editing(selected=sceneedit_v2.v2_run_paths(selection["path"], selection["count"]))

    def _v2_from_canvas(self, name: str, payload: object) -> None:
        """A click or a drop on the picture: hand it to the designer, then redraw.

        The designer's own handlers do the work -- see the note on field_refs["v2_edit"] --
        so a component dragged in the Preview is snapshotted, moved, selected and re-rendered
        in the tree by exactly the code the tree's own drag goes through.  All that is left
        here is the half the designer cannot do, which is repainting this picture.
        """
        editor = self.field_refs.get("v2_edit")
        if not isinstance(editor, dict):
            return
        handler = editor["handlers"].get(name)
        if handler is None:
            return
        handler(payload)
        self.render()

    def _screen_size(self) -> tuple[int, int]:
        """The frame a V2 layout is drawn in: the chosen screen, on its side when Landscape
        is on -- which for V2 is the whole of what the toggle does, there being no second
        stored layout to switch to.
        """
        for name, width, height in sceneview.V2_SCREENS:
            if name == self.screen:
                return (height, width) if self.options.landscape else (width, height)
        _name, width, height = sceneview.V2_SCREENS[0]
        return (height, width) if self.options.landscape else (width, height)

    def _dimensions(self) -> tuple[int, int] | None:
        """The canvas size to draw at -- the same answer the designer draws at, from the same
        function, so a Scene never previews at one size and edits at another.
        """
        return _legacy_canvas_size(self.edited_scene, self.field_refs, self.options.landscape)

    def _apply_scale(self, width: int, height: int) -> None:
        """Fit the true-size canvas into the space available.

        One transform on the whole canvas, rather than scaling each element's coordinates as
        it is drawn: the DOM then holds the same numbers the XML does, so a misplaced element
        here is a misplaced element in the Scene.  Scoped to this view's own wrapper class,
        because the Legacy designer has a canvas of its own on the same page.
        """
        fixed = None
        if self.zoom != "Fit":
            try:
                fixed = int(self.zoom.rstrip("%")) / 100
            except ValueError:
                fixed = None
        _emit_canvas_fit(CANVAS_PREVIEW_ROOT, width, height, fixed)

    def _draw_legacy_caption(self, scene_element: object, width: int, height: int) -> None:
        """Under the canvas: the Scene's own settings, the element count, and -- the part
        that matters -- what the drawing above is not able to tell the truth about.
        """
        elements = sceneview.paint_order(scene_element)
        with self.caption:
            summary = (
                f"{width} x {height} {translate_string('pixels')} · {len(elements)} {translate_string('element(s)')}"
            )
            properties = sceneview.scene_properties(scene_element)
            if properties:
                summary += " · " + " · ".join(f"{translate_string(label)}: {value}" for label, value in properties)
            ui.label(summary).classes("text-xs text-gray-500")
            if self._legacy_editing() is not None:
                ui.label(
                    translate_string(
                        "Click an element to select it, Shift-click or drag a box on the background to "
                        "take several, and drag any of them to move them all -- arrow keys nudge, Shift "
                        "for 10px. Drag a handle to resize a single element. Undo, and everything else "
                        "about an element, is back in the editor.",
                    ),
                ).classes("text-xs text-blue-600")
            ui.label(
                translate_string(
                    "Hatched fills and italic underlined text are %variables -- their values live on the "
                    "device, not in the backup, so they are named rather than guessed at. Images, video, "
                    "maps and web content are shown as placeholders. Hover any element for its geometry, "
                    "its variables and the Tasks it runs.",
                ),
            ).classes("text-xs text-gray-500 italic")

    def _draw_v2_caption(self, layout: dict, width: int, height: int) -> None:
        """The V2 counterpart.  Says the screen the layout was drawn in, because unlike a
        Legacy canvas that number is this preview's choice rather than the Scene's -- and
        says where the colours came from, for the same reason.
        """
        with self.caption:
            summary = (
                f"{translate_string('Drawn in')} {self.screen} {width} x {height} dp · "
                f"{sceneview.v2_component_count(layout)} {translate_string('component(s)')}"
            )
            properties = sceneview.v2_layout_summary(layout)
            if properties:
                summary += " · " + " · ".join(f"{translate_string(label)}: {value}" for label, value in properties)
            ui.label(summary).classes("text-xs text-gray-500")
            if self._v2_editing() is not None:
                ui.label(
                    translate_string(
                        "Click a component to select it, shift-click another in the same container to take "
                        "several, and drag to reorder them among their own siblings. Moving a component into "
                        "or out of a container is the editor's In and Out buttons; Undo is there too.",
                    ),
                ).classes("text-xs text-blue-600")
            ui.label(
                translate_string(
                    "The screen size is this preview's, not the Scene's -- a Version 2 layout has no size "
                    "of its own, so change 'Screen' to see it re-flow. Colours named by Material role are "
                    "drawn from the Material 3 baseline palette; the device resolves them against its own "
                    "theme, which under Material You comes from the wallpaper. Hatched fills and italic "
                    "underlined text are %variables. Amber outlines mark components with a 'Show when'. "
                    "Hover any component for its modifiers, variables and actions.",
                ),
            ).classes("text-xs text-gray-500 italic")

    def _say(self, message: str, colour_classes: str) -> None:
        """The stand-in for a canvas that cannot be drawn -- said in the caption area so the
        toolbar stays put and the user can change orientation and try again.
        """
        with self.caption:
            ui.label(translate_string(message)).classes(f"text-sm {colour_classes}")


class NiceGuiTextView(TextViewSearch):
    """Replaces CTkTextview. Handles rendering MapTasker data using HTML."""

    def __init__(
        self,
        master_gui: MyGui,
        title: str,
        the_data: list | dict,
        container: ui.column | None = None,
        jump_to: str = "",
        map_scope: str = "",
        built_for: str = "",
    ) -> None:
        """Initialize the NiceGuiTextView.

        If `container` is given, the view is built inside it directly instead of the
        master GUI's main content_container -- used to render into a separate popped-out
        browser window/tab without disturbing the main window's layout.

        `jump_to` is a mapjump token this view scrolls to and highlights the moment its
        content has finished streaming in -- how a clicked report finding reaches a Map
        that had to be built for it.  Acted on there and not before, because a chunk that
        has not arrived cannot be scrolled to.

        `map_scope` is the Project a Map view was built for ("" for the whole file).  It is
        what lets a later clicked finding tell a Map that can show what it points at from
        one that merely contains it -- see jump_map_view.

        `built_for` is what the app was displaying when this view was drawn, as the phrase a
        person reads -- "Project 'Home'", "" for the whole configuration.  Only the toolbar
        badge uses it (see _build_scope_badge); nothing decides anything by it.
        """
        self.master_gui = master_gui
        self.title = title
        self.is_map = isinstance(the_data, dict)
        self.external_container = container
        self.jump_to = jump_to
        self.map_scope = map_scope
        self.built_for = built_for
        # The toolbar's "built for" line and the "the selection has moved on" line beside it.
        # Held on the view so refresh_scope_badges can update them later without a slot: an
        # element's text can be changed from anywhere, while CREATING one cannot.
        self.scope_label = None
        self.scope_stale_label = None
        self.scope_rebuild_button = None
        # Search caching (see search_event). The token identifies the content currently in
        # this view: 0 means "not searchable as a stable document yet" -- process_data streams
        # the content in chunk by chunk, so anything cached about the DOM mid-stream would be
        # a snapshot of a partial document. _mark_content_ready() bumps it once streaming ends,
        # and reload_diagram() drops it back to 0 while the content is replaced.
        self._content_token = 0
        self._content_generation = 0
        self._last_search: tuple[str, list, int, bool] | None = None
        # The last structured question asked of this view (see find_event).  Held so that
        # re-opening Find comes back to the query whose result row the user just followed,
        # rather than to an empty dialog they have to fill in again.
        self._find_query: mapfind.Query | None = None
        # The Find dialog's question out with an AI model, while it is out -- held on the view
        # rather than the dialog so that _dismiss_find_dialog, which deletes a dialog without
        # its "hide" firing, can still cancel it (see _cancel_find_ask).
        self._find_ask: asyncio.Task | None = None
        # The last Replace the user set up on this view -- ("action", old key, new key,
        # project) or ("variable", name, owner, new name).  The INPUTS, not the Plan: a
        # Plan holds live elements, and holding those across a dialog that may have been
        # reopened after another edit is the stale-handle bug apply()'s own attachment
        # check exists to catch.  Reopening rebuilds the plan from these instead.
        self._replace_inputs: tuple | None = None
        # The Find/Replace dialog this view currently has up, or None.  Held because that
        # dialog no longer always takes itself down: following one of its own rows docks it
        # to the right edge and leaves it there (see _FindDialog.dock), so a second press
        # of Find/Replace has to dispose of the one already on screen rather than build a
        # second one over it.
        self._find_dialog: ui.dialog | None = None
        # The "still working on it" banner this view shows itself while its content is
        # being read and streamed in (see _show_loading).  Created by build_ui below, so
        # it is part of the very first paint of the window rather than something that has
        # to arrive over the socket afterwards.
        self._loading_row: ui.element | None = None
        self._loading_label: ui.label | None = None
        self.build_ui()
        register_view(master_gui, self)
        # Schedule the coroutine into the active event loop safely
        self._task = asyncio.create_task(self.process_data(the_data))
        # A bare create_task drops whatever the coroutine raises on the floor: the view is
        # left half-built and the app says nothing, which is a long way to debug from.  Every
        # failure in here shows up as "the view did not finish", so it is worth a line in the
        # log saying which one it was.
        self._task.add_done_callback(_report_view_failure)

    def _show_loading(self) -> None:
        """Put a spinner and a progress line at the top of this view's scroll area.

        A popped-out view opens as an empty window and stays that way for as long as it
        takes process_data to read its generated file and stream the whole of it in --
        seconds, on a large configuration, during which the window said nothing at all and
        looked like it had simply come up blank.  This is what it says instead, and
        _hide_loading takes it away the moment the content is all there.

        Built here rather than pushed over the socket later so that it is part of the
        window's first paint: it has to be on screen before the work that delays
        everything else, not after it.
        """
        if self._loading_row is not None or not hasattr(self, "scroll_area"):
            return
        with self.scroll_area:
            self._loading_row = ui.row().classes("w-full items-center gap-3 p-2")
            with self._loading_row:
                ui.spinner(size="1.5em", color="orange")
                self._loading_label = ui.label(
                    translate_string("Building the view.  Please stand by ..."),
                ).classes("text-orange-500 italic")

    def _set_loading_text(self, message: str) -> None:
        """Say how far along the streaming is, if the banner is still up."""
        if self._loading_label is not None:
            self._loading_label.set_text(message)

    def _hide_loading(self) -> None:
        """Take the progress banner down.  Safe to call when there isn't one."""
        row, self._loading_row, self._loading_label = self._loading_row, None, None
        if row is not None:
            with contextlib.suppress(Exception):
                row.delete()

    def _mark_content_ready(self) -> None:
        """Marks this view's content as fully streamed in, under a fresh content token.

        The token is what lets the browser-side search index (and the results cache below)
        be trusted: it changes whenever the content does, so an index built against the
        previous content can never be mistaken for one built against this one.
        """
        self._content_generation += 1
        self._content_token = self._content_generation
        self._last_search = None
        # Every path through process_data ends here, which makes this the one place the
        # progress banner can be taken down without having to remember each of them.
        self._hide_loading()

    async def _enable_in_page_links(self) -> None:
        """Make the Map's own hyperlinks land on what they name.

        The directory at the top of the Map, the "Go to top" links and every Task name that
        points at its own entry are plain '<a href="#...">' links, which the browser follows
        by itself.  That works only while the browser knows where the target is -- and the
        Map arrives as pieces marked "content-visibility: auto", which is what lets it skip
        the layout of everything off screen (see split_for_streaming).  A piece it has
        skipped has never been laid out, so a link into one lands at that piece's ESTIMATED
        position rather than its real one, which on a large Map is thousands of lines out.

        So the click is taken over here: the piece holding the target is asked to lay itself
        out for real, and only then is the target scrolled to.  Exactly what a clicked report
        finding and a search result already do (mapjump.REVEAL_ANCESTORS_JS), now that an
        ordinary hyperlink needs it too.

        Inside the view's own slot, as _deliver_jump runs its jump: ui.run_javascript needs
        a client to send to, and it raises rather than guesses when it is called from a
        background task with no slot in context -- which the rest of this method's work
        then never happens inside.
        """
        with self.scroll_area:
            try:
                await self._wire_in_page_links()
            except (TimeoutError, RuntimeError):
                # The page went away, or never finished connecting, while the content was
                # still arriving.  The links then fall back to what the browser does with
                # them, which is right for everything it has already laid out.
                logger.debug("Map view: the in-page link handler was not installed.")

    async def _wire_in_page_links(self) -> None:
        """Install the click handler described by _enable_in_page_links."""
        await ui.run_javascript(
            f"""
            (() => {{
                const container = document.getElementById("c{self.scroll_area.id}");
                if (!container || container.dataset.mtLinksWired) return;
                container.dataset.mtLinksWired = "1";
{mapjump.REVEAL_ANCESTORS_JS}
{mapjump.RESOLVE_TARGET_JS}
                container.addEventListener("click", (event) => {{
                    const link = event.target.closest('a[href^="#"]');
                    if (!link || !container.contains(link)) return;
                    const name = decodeURIComponent(link.getAttribute("href").slice(1));
                    const anchor = name ? document.getElementById(name) : null;
                    if (!anchor) return;   // Nothing of that name here: leave the browser to it.
                    // The anchor is often an empty marker with no box of its own, so what
                    // gets scrolled to is the line it stands in front of (see mtJumpTarget).
                    mtRevealAncestors(anchor);
                    const target = mtJumpTarget(anchor);
                    if (!target) return;
                    event.preventDefault();
                    mtRevealAncestors(target);
                    // With the "twisty" option on, the target can be inside a collapsed
                    // <details>, and scrolling to something not being displayed does nothing.
                    for (let box = target.closest("details"); box; box = box.parentElement?.closest("details")) {{
                        box.open = true;
                    }}
                    target.scrollIntoView({{ behavior: "auto", block: "start" }});
                }});
            }})()
            """,
            timeout=SEARCH_JAVASCRIPT_TIMEOUT,
        )

    async def _deliver_jump(self) -> None:
        """Take this freshly built Map to the object a clicked report finding asked for.

        Runs once and then forgets the token: this is the delivery of one click, not a
        property of the view, and a later reload of the same page should not silently jump
        somewhere the user has since scrolled away from.

        Says so when the object turns out not to be there after all.  The rebuild that led
        here already went to the whole configuration at a detail level chosen for this
        object, so the remaining explanations are narrow -- the view limit cut the Map short
        before reaching it, or it is one of the things the Map has no line for (a variable
        the Map's own variable table does not list, for one) -- and either way the useful
        thing to say is that it is not there, not to guess which.
        """
        token, self.jump_to = self.jump_to, ""
        target = mapjump.Target.from_token(token) if token else None
        if target is None:
            return

        with self.scroll_area:
            try:
                landed = await ui.run_javascript(mapjump.jump_js(target.anchor), timeout=5)
            except (TimeoutError, RuntimeError):
                # The page went away, or never finished connecting, between the content
                # arriving and this asking it to scroll.  There is nobody left to tell.
                return
            if not landed:
                ui.notify(
                    f"{translate_string('Built the Map, but it has no line for')} {target.label}",
                    type="warning",
                    position="top",
                )

    def _build_scope_badge(self) -> None:
        """The toolbar line saying what this view was drawn for, and whether that is still
        what the app is showing.

        A Diagram is a SNAPSHOT.  Nothing rebuilds it when the user picks a different single
        Project, Profile, Task or Scene, so it goes on drawing the selection it was built
        for -- and its hotlinks go on pointing at those objects, which is fine until the user
        moves on and then reads the two views as though they agree.  Clicking one of those
        hotlinks then answers with a Map of the object clicked (see rebuild_map_for_jump),
        replacing the Map the user had just built for their new selection, which is a
        surprise precisely because nothing on screen said the Diagram was from another time.

        So it says so, in the one place the clicking happens.  Nothing is disabled and no
        behaviour changes: the hotlinks still work, and the Rebuild button is offered rather
        than done, because a Diagram of a large configuration is slow to draw and the user
        may well want the old one a moment longer.

        Both labels are created here whatever the state, and only their text and visibility
        change afterwards -- see refresh_scope_badges for why that distinction matters.
        """
        self.scope_label = ui.label("").classes("text-xs text-gray-500 italic ml-4")
        self.scope_stale_label = ui.label("").classes("text-xs text-orange-500 font-bold")

        async def rebuild() -> None:
            """Draw this view again for whatever is selected now.

            Through view_event, the same call the Diagram button makes, so the rebuild is
            the view the user would get by pressing it -- this is a shortcut to that button,
            not a second way of building a Diagram.
            """
            handlers = getattr(self.master_gui, "event_handlers", None)
            if handlers is None:
                ui.notify(translate_string("Press Diagram View to rebuild it."), type="info", position="top")
                return
            await handlers.view_event("diagram")

        self.scope_rebuild_button = (
            ui.button(translate_string("Rebuild"), on_click=rebuild).props("dense flat").classes("text-orange-500")
        )
        self.refresh_scope_badge()

    def refresh_scope_badge(self) -> None:
        """Put the current answer into the badge built above.

        Text and visibility only.  Called at build time and again whenever the selection
        changes, from a context that has no NiceGUI slot -- which is exactly why nothing here
        creates an element.
        """
        if self.scope_label is None:
            return
        drawn, changed = scope_badge_text(self.built_for, mapjump.current_scope().phrase)
        self.scope_label.set_text(drawn)
        self.scope_stale_label.set_text(changed)
        self.scope_stale_label.set_visibility(bool(changed))
        self.scope_rebuild_button.set_visibility(bool(changed))

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
        # The Task Flow view is a drawing too -- one Task's control flow, box-drawn by
        # taskflow.py -- so it inherits the Diagram's unwrapped, tightly-led layout without
        # inheriting the Diagram's toolbar, none of which (Profiles Per Line, folding, the
        # call chain) means anything for a single Task.
        is_flow = self.title.startswith("Task Flow")

        # Set the main container to a vertical layout with full width and height
        with container_context:
            # Toolbar
            with ui.row().classes("w-full items-center gap-2 p-2 mb-2 shrink-0") as self.gui_toolbar:
                ui.label(f"{self.title}").classes("text-orange-500 font-bold mr-4")
                self.search_input = ui.input(placeholder=translate_string("Search...")).classes("w-48")
                search_button = ui.button(translate_string("Search"), on_click=self.search_event).classes("bg-blue-600")
                with search_button:
                    ui.tooltip(
                        translate_string(
                            "The 'Search' button will search for and highlight every instance of the case-insensitive string entered in the search box, starting at the top of the data.\n\n"
                            "It will only show the first 200 instances of the search string.\n\n"
                            "Click on the line number to go to that line in the text view box.\n\n"
                            "The 'Clear' button will clear the search results.\n\n",
                        ),
                    ).style("white-space: pre-wrap")
                ui.button(translate_string("Clear"), on_click=self.master_gui.event_handlers.clear_event).classes(
                    "bg-blue-600",
                )
                # Structured search, alongside the text one rather than replacing it: the
                # two answer different questions (see find_event).  Offered on the Map and
                # the Diagram and nowhere else -- it answers with objects in the loaded
                # configuration, which is what those two views draw; the Misc view shows
                # reports, which have their own clickable rows already.
                if self.is_map or is_diagram:
                    find_button = ui.button(translate_string("Find/Replace"), on_click=self.find_event).classes(
                        "bg-blue-600",
                    )
                    with find_button:
                        ui.tooltip(
                            translate_string(
                                "'Find/Replace' asks the loaded configuration a question rather than searching the "
                                "text on screen: every Task performing a given action, every Profile a given "
                                "trigger fires, everything that names a given app or Scene.\n\n"
                                "The boxes combine -- pick a trigger and an action to find the Profiles that "
                                "trigger that way and run a Task that does that.\n\n"
                                "Results come back as a list of objects; click one to be taken to it.\n\n",
                            ),
                        ).style("white-space: pre-wrap")
                    # On the same two views as Find/Replace, and for the same reason: they draw
                    # the configuration, which is what an export is of (see mapexport).
                    _create_export_menu(self)
                ui.separator().props("vertical")
                ui.button(translate_string("Top"), on_click=lambda: self.scroll("top")).classes("bg-blue-600")
                ui.button(translate_string("Bottom"), on_click=lambda: self.scroll("bottom")).classes("bg-blue-600")
                ui.button(translate_string("Toggle Wrap"), on_click=self.toggle_wrap).classes("bg-blue-600")
                if self.is_map:
                    self.map_message_label = ui.label(PrimeItems.view_limit_msg).classes("text-orange-400 italic ml-4")
                if is_diagram:
                    ui.separator().props("vertical")
                    # Held on the view, not left anonymous, so "Reset Options" can move it:
                    # this pulldown lives on the Diagram view's own toolbar rather than in the
                    # settings drawer, and a reset that changed the value without moving the
                    # control would leave the two disagreeing on screen.
                    self.profiles_per_line_select = (
                        ui.select(
                            options=[str(n) for n in range(11)],
                            value=str(self.master_gui.profiles_per_line),
                            label=translate_string("Profiles Per Line"),
                            on_change=self._profiles_per_line_selected,
                        )
                        .classes("w-40")
                        .props("dense")
                    )
                    _create_diagram_tools(self)
                    self.diagram_message_label = ui.label("").classes("text-orange-400 italic ml-4")
                    self._build_scope_badge()

            self.wrap_enabled = not (is_diagram or is_flow)
            self.wrap_classes = "whitespace-pre-wrap break-words" if self.wrap_enabled else "whitespace-pre"

            # min-h-0 lets this flex item shrink below its content's intrinsic size -- without it
            # a flex column's default min-height:auto would keep growing the scroll area (and the
            # page) to fit all the streamed-in content instead of scrolling internally.
            scroll_height_classes = "flex-1 min-h-0" if is_popout else "h-[70vh]"

            # Tailwind's text-sm utility (below) pairs a 14px font with a 20px line-height --
            # comfortable for prose, but visibly loose for a dense box-drawn diagram. Tighten it
            # for the Diagram view only; keep process_data()'s approx_px_per_line chunk-height
            # estimate in sync with this so scrolling doesn't jump around as chunks pop in.
            line_height_style = " line-height: 1.2;" if is_diagram or is_flow else ""

            # The Map view renders MapTasker.html, every color in which was picked against the
            # configured output background -- the same one frontmtr writes onto that file's
            # <body>. The app's own page background is set from the dark-mode toggle instead,
            # so the two disagreed: open the file and the output sits on Lavender, show the
            # same output here and it sat on white. Anything the output colors near-matches
            # (a TaskerNet description's white headings, say) then disappears. Use the
            # configured background here too, so the view shows what the file shows.
            # "!important" is needed, not decorative: the light-mode overrides injected by
            # inject_shared_head_styles() force "background-color: #ffffff !important" onto
            # every .q-scrollarea to keep macOS's system appearance from bleeding through, and
            # a plain inline style loses to that. An important declaration in the style
            # attribute is the one thing that outranks an important rule in a stylesheet, and
            # it applies to this one scroll area rather than weakening the override for the
            # drawers, cards and tab panels that rely on it.
            background_style = ""
            if self.title.startswith("Map"):
                background = css_color(PrimeItems.colors_to_use.get("background_color", ""))
                if background:
                    background_style = f" background-color: {background} !important;"

            self.scroll_area = (
                ui.scroll_area()
                # min-w-0 keeps this a flex child that can't be stretched wider than its container by
                # long unbreakable content; without it the default flex min-width:auto lets the box
                # (and the whole page) grow past the viewport once the full content has streamed in.
                .classes(
                    f"w-full max-w-full min-w-0 block {scroll_height_classes} "
                    f"border-2 border-gray-600 p-4 text-sm {self.wrap_classes}",
                )
                .style(
                    # The font the output was generated with, which process_data() then
                    # reconciles against the file it actually reads. Deliberately not
                    # master_gui.font -- see the note there on why that can be stale.
                    f"width: 100%; max-width: 100%; "
                    f"font-family: '{PrimeItems.program_arguments.font}', monospace;"
                    f"{line_height_style}{background_style}",
                )
            )

            # The window is about to be handed to the browser with nothing in it yet.  Say
            # what it is waiting for, right here in the first paint -- see _show_loading.
            self._show_loading()

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
        is_flow = self.title.startswith("Task Flow")
        # Starting point, used as-is by the Misc and Task Flow views (neither of which has a
        # generated file behind it).  The file-backed views replace this below with the font
        # their file actually carries.
        html_style = f"width: 100%; max-width: 100%; font-family: '{PrimeItems.program_arguments.font}', monospace;"
        if not (is_diagram or is_flow):
            html_style += " word-break: break-word;"

        if self.title.startswith("Map"):
            file_to_read = output_path("MapTasker.html")
        elif is_diagram:
            file_to_read = output_path(DIAGRAM_FILE)
        elif self.title.startswith("Misc") or is_flow:
            # The Task Flow view is this renderer with the Diagram's habits: rows mapjump has
            # already made clickable, but a drawing rather than prose, so nothing may wrap
            # (see build_ui).  Its content comes off PrimeItems rather than through the_data
            # because a popped-out window builds itself from a URL and is handed nothing --
            # the same reason the Diagram popout re-reads its own file (rungui.popout_view).
            with self.scroll_area:
                content_str = (
                    mapjump.html_report(PrimeItems.taskflow_rows)
                    if is_flow
                    else ("\n".join(str(line) for line in the_data) if isinstance(the_data, list) else str(the_data))
                )
                ui.html(f"<pre style='{html_style}'>{content_str}</pre>", sanitize=False)
            # A report rendered by mapjump.html_report marks the rows that point at
            # something in the Map (see its FINDING_CLASS).  Tested for rather than assumed,
            # since this branch also shows reports that carry no such rows at all -- the
            # file comparison, and any report from a build before those rows existed.
            if mapjump.FINDING_CLASS in content_str:
                enable_finding_clicks(self)
            self._mark_content_ready()
            return

        try:
            with open(file_to_read, encoding="utf-8") as f:
                final_html = f.read()
                # The diagram file is plain text (no HTML markup), and its line numbers must line
                # up 1:1 with PrimeItems.diagram_connectors (recorded when the diagram was built) so
                # clicking a connector highlights the right one -- so skip the HTML-specific/blank-line
                # collapsing optimizations here; they aren't meaningful for plain text anyway.
                if not is_diagram:
                    final_html = HTML_OPTIMIZE_PATTERN.sub(optimize_html, final_html)

            # Render in whatever font the file we just read was actually generated with,
            # rather than overriding it with the GUI's current selection.
            #
            # This used to rewrite the file's font-family to self.master_gui.font. That is
            # only right while the two agree -- and the popout page resolves its gui through
            # PrimeItems.mygui, which is simply the most recently constructed MyGui, so a
            # main window that got rebuilt (a reload, a reconnect, a second window) leaves a
            # .font behind that never generated anything. Rewriting to it then replaced a
            # correct font with a stale one, which is why the saved MapTasker.html could show
            # the selected font while the Map view of that very same file did not.
            #
            # Reading the font back out of the file removes the disagreement outright: the
            # view can only ever show what the output it is displaying was built with. The
            # Diagram file is plain text with no CSS of its own, hence the fallback to the
            # font that generated this run.
            extracted_font = self.extract_first_font_name(final_html)
            view_font = extracted_font if extracted_font != "Font name not found" else PrimeItems.program_arguments.font
            html_style = f"width: 100%; max-width: 100%; font-family: '{view_font}', monospace;"
            if not is_diagram:
                html_style += " word-break: break-word;"
            # build_ui() styled the scroll area before this file had been read, so bring it
            # into step now that the font it is actually holding is known.
            self.scroll_area.style(f"font-family: '{view_font}', monospace;")

            # --- STREAMING CHUNK ENGINE ---
            # Slice the giant HTML text by lines and push them in digestible blocks
            html_lines = final_html.splitlines()
            if html_lines and html_lines[0].strip() == '<span class="normtab"></span><!doctype html>':
                del html_lines[0]  # Remove the first line if it matches the unwanted header

            connectors_by_line = _connectors_by_line() if is_diagram else None
            # What makes the Diagram clickable rather than merely drawn -- see diagintr.
            # Empty for a Diagram file left on disk by an older run, in which case the
            # lines below are wrapped exactly as they always were.
            diagram_model = diagintr.model() if is_diagram else {}
            nodes_by_line = diagintr.nodes_by_line(diagram_model)
            folds_by_line = diagintr.folds_by_line(diagram_model)

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
            # text-sm is 14px; at the Diagram view's tightened line-height (1.2, set in build_ui)
            # that's ~17px per line instead of Tailwind's default ~20px.
            approx_px_per_line = 17 if is_diagram else 20

            # The Diagram is a drawing made of lines, and every one of them has to keep its
            # own number for a connector click to land on it, so it is still cut into pieces
            # of 150 lines.  The Map is not: by the time it reaches here the newlines
            # between its tags have been optimized away, so cutting it by lines left the
            # whole Map in one piece however big it was (see split_for_streaming).
            if is_diagram:
                chunks = [
                    (
                        "".join(
                            _wrap_diagram_line(
                                start + offset,
                                line,
                                connectors_by_line or {},
                                nodes_by_line,
                                folds_by_line,
                            )
                            for offset, line in enumerate(html_lines[start : start + 150])
                        ),
                        len(html_lines[start : start + 150]),
                    )
                    for start in range(0, len(html_lines), 150)
                ]
            else:
                # Joined back exactly as the chunks used to be written, so that what the
                # browser is given is the same text it was given before -- only cut up
                # differently.  How tall a piece is, near enough to reserve scrollbar space
                # for: every line of the Map ends in a <br>, so counting those counts lines.
                chunks = [(piece, piece.count("<br>") or 1) for piece in split_for_streaming("\n".join(html_lines))]

            delivered = 0
            total_size = sum(len(content) for content, _ in chunks) or 1
            with self.scroll_area:
                for number, (chunk_content, chunk_lines) in enumerate(chunks):
                    chunk_height = chunk_lines * approx_px_per_line
                    chunk_style = (
                        html_style + f" content-visibility: auto; contain-intrinsic-size: auto {chunk_height}px;"
                    )
                    chunk = ui.html(chunk_content, sanitize=False).classes("w-full block max-w-full").style(chunk_style)
                    # How many lines this chunk holds, so that zooming can re-reserve the
                    # right amount of scrollbar space for it while it is still unrendered --
                    # the height above was worked out against the unzoomed line height.
                    if is_diagram:
                        chunk.props(f"data-lines={chunk_lines}")
                    # How far along, on the banner _show_loading put up.  Content arrives
                    # top-down so there is something to look at almost at once, but on a
                    # large configuration it goes on arriving for a while after that, and
                    # a percentage is the difference between "still working" and "stuck".
                    delivered += len(chunk_content)
                    self._set_loading_text(
                        f"{translate_string('Building the view')} ... {min(100, round(100 * delivered / total_size))}%",
                    )
                    # Yields the loop to keep the WebSocket alive.  Not after every piece:
                    # the Map is now cut into far more of them, and a hundredth of a second
                    # each would put a wait of its own in front of the user.
                    if number % 4 == 0:
                        await asyncio.sleep(0.01)

            if connectors_by_line:
                self._enable_connector_highlighting()
                if hasattr(self, "diagram_message_label"):
                    self.diagram_message_label.set_text(translate_string("Click on connector to highlight"))
            if diagram_model.get("nodes"):
                self._enable_diagram_interaction(diagram_model)
                # Replaces the connector hint rather than joining it: both are about
                # clicking the diagram, and this one covers the connectors too.
                if hasattr(self, "diagram_message_label"):
                    self.diagram_message_label.set_text(
                        translate_string("Click a name for its Map entry \u00b7 shift-click a Task for its call chain"),
                    )
            # A diagram cut short at the view limit (diagram.check_limit) says so here, in place
            # of the connector hint: that the diagram stops early is the more important of the
            # two things to tell the user, and this is the Map view's view_limit_msg field by
            # another name (see NiceGuiTextView.build_ui).
            if PrimeItems.diagram_limit_msg and hasattr(self, "diagram_message_label"):
                self.diagram_message_label.set_text(PrimeItems.diagram_limit_msg)
            await self._enable_in_page_links()
            self._mark_content_ready()
            # Everything is on the page now, so a report finding that asked for this Map can
            # finally be taken to.  Last, deliberately: the anchor it wants may be in the
            # chunk that only just arrived.
            await self._deliver_jump()
            return  # noqa: TRY300

        except FileNotFoundError:
            pass

        # Apply the fallback generation if the file does not exist
        self._process_fallback_data(the_data)
        self._mark_content_ready()

    def _enable_diagram_interaction(self, diagram_model: dict) -> None:
        """Wire up the Diagram view's clickable nodes, folds, chains and zoom.

        The DOM half of it.  The Python half is one subscription -- the same "mt_jump" a
        clicked report finding raises -- so that a node click and a report row are answered
        by the very same code (see go_to_target): the Diagram is one more thing that points
        at the Map, not a second way of getting there.

        Needs an active NiceGUI slot for both, and this runs from process_data's background
        task where the slot stack is empty, hence the scroll area re-entry -- the same
        reason, spelled out at greater length, as in _enable_connector_highlighting.
        """
        with self.scroll_area:
            register_finding_clicks(self.master_gui)
            status_id = f"c{self.diagram_state_label.id}" if hasattr(self, "diagram_state_label") else ""
            ui.run_javascript(diagintr.interaction_js(f"c{self.scroll_area.id}", status_id, diagram_model))

    def _diagram_command(self, name: str, argument: float | None = None) -> None:
        """Carry one of the Diagram toolbar's buttons to the view it belongs to."""
        with self.scroll_area:
            ui.run_javascript(diagintr.command_js(f"c{self.scroll_area.id}", name, argument))

    def _enable_connector_highlighting(self) -> None:
        """Wires up click-to-highlight for Diagram view connector spans.

        Clicking a connector span highlights every span sharing its data-connector-id and clears
        any previously-highlighted connector; clicking empty space clears the highlight too. If
        either end of the highlighted connector -- its topmost or bottommost cell, since a
        connector's spans are emitted top-to-bottom in document order -- is scrolled out of the
        visible area, a floating "Jump to Start"/"Jump to End" button appears so the user can
        bring it into view without hunting for it manually; the button hides itself again once
        the user scrolls that end into view (or clicks away). A jump scrolls vertically to that
        end's line and horizontally back to column 1, so the line is read from its beginning
        rather than from wherever the connector happens to sit across a wide diagram.
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
{mapjump.REVEAL_ANCESTORS_JS}

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
                            mtRevealAncestors(target);
                            // Instant, not smooth: the jump can cover tens of thousands of pixels
                            // on a large diagram, where an animated scroll would be slow to land
                            // and distracting rather than helpful.
                            //
                            // Vertical placement only. Centering horizontally on the connector
                            // (inline: "center") parked a wide diagram mid-line, so the user
                            // landed on the right line but somewhere out in the middle of it;
                            // "nearest" keeps scrollIntoView from moving sideways on its own and
                            // the loop below then pins every scrollable ancestor back to column 1.
                            target.scrollIntoView({{block: "center", inline: "nearest", behavior: "auto"}});
                            for (let a = target.parentElement; a; a = a.parentElement) {{
                                if (a.scrollWidth > a.clientWidth) {{
                                    a.scrollLeft = 0;
                                }}
                            }}
                            if (document.scrollingElement) {{
                                document.scrollingElement.scrollLeft = 0;
                            }}
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
                    // Vertical only, matching what the jump actually does: it scrolls to the
                    // connector's line and then resets to column 1, so a target sitting off to
                    // the right is not something the button can help with -- testing for it
                    // would leave the button showing forever on a wide diagram. A connector's
                    // run can also be taller than the container, in which case requiring it to
                    // fit entirely inside can never be satisfied even right after a successful
                    // jump; its midpoint landing inside is a better proxy for "you're there".
                    const er = el.getBoundingClientRect();
                    const cr = container.getBoundingClientRect();
                    const midY = er.top + er.height / 2;
                    return midY >= cr.top && midY <= cr.bottom;
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

    async def export_event(self, what: str, fmt: str) -> None:
        """Save the Map or the Diagram as Markdown, JSON or PDF, and say where it went.

        Run off the event loop: a PDF of a large Map takes a moment, most of it spent the
        first time on looking through the system's fonts for one to embed (see
        mapfonts.embeddable_font), and the window should not stop answering meanwhile.
        """
        try:
            path = await run.io_bound(mapexport.export_view, what, fmt)
        except mapexport.ExportError as error:
            ui.notify(str(error), type="warning", position="top")
            return
        except OSError as error:
            ui.notify(f"{translate_string('The export could not be saved:')} {error}", type="negative", position="top")
            return
        # None is not a path: nicegui answers it when the wait is cancelled or the app is
        # stopping (see nicegui.run._run).  The file is written either way; what is gone is the
        # page that would have been told where.
        if path is None:
            return
        ui.notify(f"{translate_string('Exported to')} {path}", type="positive", position="top")

    def extract_first_font_name(self: MyGui, text: str) -> str:
        """
        Scans the given text to identify and return the font name
        following the very first 'font-family:' rule declaration.
        """
        # Regex Breakdown:
        # font-family\s*:\s* -> Matches 'font-family', optional spaces, a colon, and optional spaces
        # ([^,;{}]+)         -> Capture Group 1: the first family in the list, i.e. everything
        #                       up to the comma that starts the fallback stack, or to the end
        #                       of the declaration when there is no fallback
        #
        # The comma has to end the capture rather than be excluded from it.  Every
        # font-family MapTasker writes carries a fallback -- addcss.py emits
        # "font-family:<font>, monospace;" and the view styles below build the same shape --
        # so a pattern that had to reach a ';' or '}' without crossing a comma matched none
        # of them.  This returned "Font name not found" for all real output, and the caller
        # fell back to program_arguments.font every single time: exactly the stale-font
        # behaviour that reading the font back out of the file is meant to avoid.
        pattern = re.compile(r"font-family\s*:\s*([^,;{}]+)")

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
                # Everything format.py can put in a TaskerNet description or Task label needs
                # to be in this list, or it is escaped and shown as its own markup instead of
                # being rendered.  "img" is the one that shows: a description's picture came
                # out as the literal text of its <img> tag and no image at all.
                "img",
                "figure",
                "figcaption",
                "big",
                "small",
                "code",
                "pre",
                "blockquote",
                "font",
                "mark",
                "sub",
                "sup",
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
            self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        """Scroll the view all the way down, with the last line actually on screen.

        scroll_to(percent=1.0) hands Quasar a percentage of the scroll size it currently knows
        about -- and while the chunks process_data() streamed in are still being skipped by
        "content-visibility: auto", that size is the sum of their *estimated* heights
        (contain-intrinsic-size), not their real ones. The estimate runs short on the last chunk,
        so "100%" stopped a line or so above the true end of the content.

        Setting scrollTop past the end instead lets the browser clamp it to the real maximum,
        and doing that again over the next few frames picks up the correction as the chunks
        being scrolled into view get laid out for real and the scroll height grows.
        """
        ui.run_javascript(f"""
            const outerContainer = document.getElementById("c{self.scroll_area.id}");
            if (!outerContainer) return;
            const scroller = outerContainer.querySelector(".q-scrollarea__container") || outerContainer;
            let attempts = 0;
            const toBottom = () => {{
                // Deliberately past the end: the browser clamps this to scrollHeight minus the
                // visible height, which is exactly the bottom, without having to measure either.
                scroller.scrollTop = scroller.scrollHeight;
                // Eight frames is ~130ms at 60fps -- long enough for the last chunks to render
                // and settle, short enough to still read as an instant jump.
                if (++attempts < 8) {{
                    requestAnimationFrame(toBottom);
                }}
            }};
            toBottom();
        """)

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
            asyncio.create_task(self.master_gui.event_handlers.profiles_per_line_event(new_value))  # noqa: RUF006

    def reload_diagram(self) -> None:
        """Clears and re-streams the Diagram view's content in place after it has been
        regenerated (e.g. after the 'Profiles Per Line' pulldown changes the diagram's layout).
        """
        # The content this view's cached search index and results were built against is about
        # to be thrown away; process_data() issues a new token once the replacement is fully
        # streamed in. Until then nothing about the old content may be reused.
        self._content_token = 0
        self._last_search = None
        self.scroll_area.clear()
        # clear() took the previous banner's element with it, so forget the handle before
        # asking for a fresh one -- the re-stream is another wait, and says so too.
        self._loading_row = self._loading_label = None
        self._show_loading()
        self._task = asyncio.create_task(self.process_data([]))
