"""sceneview_legacy: drawing a Legacy Scene -- a pixel canvas with every element at its real coordinates.

draw_scene places an absolutely positioned div per element inside a fixed-size canvas; the element drawers (text,
button, image, slider, web, list...) and the selection, bounds and task-badge overlays are here."""

from __future__ import annotations

import html
from typing import TYPE_CHECKING

from nicegui import ui

from maptasker.src.core.actiont import lookup_values
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.gui.sceneview import (
    FIT_REDUCE,
    FIT_SCROLL,
    FORMAT_HTML,
    HTML_HEAD_OPEN,
    HTML_MARKUP,
    HTML_OPEN,
    HTML_TAG,
    MAX_ITEM_DEPTH,
    PLACEHOLDER_EDGE,
    PLACEHOLDER_FILL,
    POSITION_FLEX,
    ROUNDED_CORNERS,
    SHADER_GRADIENTS,
    VARIABLE_FILL,
    WEB_CSP,
    WEB_MODE_DIRECT,
    WEB_SANDBOX,
    CanvasEditing,
    Colour,
    ElementArgs,
    PreviewOptions,
    element_flag_names,
    element_geometry,
    element_is_hidden,
    element_name,
    element_tasks,
    paint_order,
    scene_dimensions,
)

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from maptasker.src.core.primitem import RunState


# ==========================================
# Drawing
# ==========================================
def draw_scene(
    scene_element: Element,
    width: int,
    height: int,
    options: PreviewOptions,
    editing: CanvasEditing | None = None,
    *,
    state: RunState,
) -> None:
    """Draw the whole canvas, into whatever NiceGUI container is currently open.

    width/height are passed in rather than read off the Scene because the preview shows what
    the *dialog* currently holds, including a size the user has typed but not yet saved (see
    guiwins_sceneview.NiceGuiSceneView).

    The canvas is a fixed-size element at the Scene's true pixel dimensions with every child
    absolutely positioned at its real coordinates; fitting it on screen is one CSS transform
    applied to the whole thing by the view.  Doing it that way -- rather than scaling every
    coordinate as it is drawn -- means the numbers in the DOM are the numbers in the XML,
    so anything that looks wrong here is wrong in the Scene rather than in the arithmetic.
    """
    background = _canvas_background(scene_element)
    canvas = (
        ui.element("div")
        .classes("mt-scene-canvas")
        .style(
            f"position: relative; width: {width}px; height: {height}px; overflow: hidden;"
            f"transform-origin: top left; background: {background.css};",
        )
    )
    if background.is_variable:
        canvas.style(f"background: {VARIABLE_FILL};")
    if editing:
        # tabindex so the canvas can hold focus and receive the arrow keys; the pointer
        # handlers are attached to this element by the designer, and it is rebuilt on every
        # render, which is what stops those handlers ever accumulating.
        #
        # The selection is written here, from Python, rather than poked in afterwards by
        # script: the handles belong to the overlay rather than to the element they resize,
        # so a handle-drag has to look up which element that is, and an attribute this
        # renderer states is one NiceGUI will re-state on every patch instead of dropping.
        #
        # Space-separated because it is a set: the drag script splits it to decide whether
        # the element under the pointer is one of the group, and an sr ("elements10") never
        # contains a space.
        canvas.props(f'tabindex="0" data-selected="{" ".join(editing.selected)}"').style("outline: none;")
    with canvas:
        selected_boxes = []
        for element in paint_order(scene_element):
            _draw_element(element, options, editing=editing, state=state)
            sr = element.get("sr", "")
            if editing and sr in editing.selected:
                # None for an element selected in one orientation and looked at in the
                # other, where it has no layout at all -- it is not drawn, so it gets no
                # outline either, rather than one round a box that isn't there.
                box = element_geometry(element, options.landscape)
                if box is not None:
                    selected_boxes.append((sr, box))
        # Drawn last, and outside every element's frame, so they sit above the whole canvas
        # and their handles are not clipped by the frame's own overflow: hidden.
        for sr, box in selected_boxes:
            _draw_selection(sr, box, handles=len(selected_boxes) == 1)


# Which way each handle stretches the box.  The names are compass points because that is
# what the pointer handler reasons in ("n" moves the top edge), and the CSS below places
# each one on the edge it is named after.
_HANDLE_POSITIONS: tuple[tuple[str, str, str], ...] = (
    ("nw", "left: -4px; top: -4px;", "nwse-resize"),
    ("n", "left: calc(50% - 4px); top: -4px;", "ns-resize"),
    ("ne", "right: -4px; top: -4px;", "nesw-resize"),
    ("e", "right: -4px; top: calc(50% - 4px);", "ew-resize"),
    ("se", "right: -4px; bottom: -4px;", "nwse-resize"),
    ("s", "left: calc(50% - 4px); bottom: -4px;", "ns-resize"),
    ("sw", "left: -4px; bottom: -4px;", "nesw-resize"),
    ("w", "left: -4px; top: calc(50% - 4px);", "ew-resize"),
)


def _draw_selection(sr: str, box: tuple[int, int, int, int], *, handles: bool = True) -> None:
    """One selection outline, and its eight resize handles, as an overlay at that element's
    box rather than as part of the element itself.

    Separate because every element frame carries overflow: hidden -- an element has to clip
    its own contents to its geometry, which is exactly what Tasker does -- and a handle
    hanging 4px outside the edge would be clipped away by it.  An overlay also means the
    selection can be moved during a drag without touching what is drawn inside the element,
    which is why it carries the sr: the drag script moves each outline with the element it
    belongs to.

    HANDLES ONLY WHEN ONE ELEMENT IS SELECTED.  Eight handles round each of six selected
    elements would be an offer this cannot keep: resizing a group is a question with two
    honest answers (scale them all about the group's box, or give each of them the same
    size) and no way to ask which was meant, so a multiple selection moves and does not
    resize.  Which is exactly what the drawing then says.
    """
    x, y, width, height = box
    with (
        ui.element("div")
        .classes("mt-selection")
        .props(f'data-sr="{sr}"')
        .style(
            f"position: absolute; left: {x}px; top: {y}px; width: {width}px; height: {height}px;"
            "box-sizing: border-box; z-index: 10; outline: 2px solid rgba(37,99,235,0.95);"
            "outline-offset: -1px; pointer-events: none;",
        )
    ):
        if not handles:
            return
        for direction, placement, cursor in _HANDLE_POSITIONS:
            ui.element("div").classes("mt-handle").props(f'data-dir="{direction}"').style(
                f"position: absolute; {placement} width: 8px; height: 8px; box-sizing: border-box;"
                f"background: #fff; border: 1px solid rgba(37,99,235,0.95); border-radius: 1px;"
                f"cursor: {cursor}; pointer-events: auto;",
            )


def _canvas_background(scene_element: Element) -> Colour:
    """The Scene's own background colour -- <PropertiesElement> arg2 (actionc.py
    "PropertiesElement": 0 Property Type, 1 Orientation, 2 Background_Color, 3 Theme,
    4 Title, 5 Subtitle, 6 Icon, 7 Tab Labels).

    White when the Scene never set one, because that is what an unset Scene looks like on a
    phone -- and because a canvas drawn on this app's own background would let the window's
    dark mode change what the Scene appears to be, which it does not.
    """
    properties = scene_element.find("PropertiesElement")
    if properties is None:
        return Colour("#ffffff")
    return ElementArgs(properties).colour(2, fallback="#ffffff")


def scene_properties(scene_element: Element) -> list[tuple[str, str]]:
    """The Scene's <PropertiesElement> settings, as (label, value) for the preview's caption.

    These describe the whole Scene rather than any element in it -- how it is put on screen,
    which way up, and what it is titled -- so they are reported next to the canvas instead of
    being drawn into it.  Display Type especially: an Overlay, a Dialog and an Activity are
    three visibly different things on a phone, and none of that is in the geometry.
    """
    properties = scene_element.find("PropertiesElement")
    if properties is None:
        return []
    args = ElementArgs(properties)
    rows = [
        ("Display Type", _enum(lookup_values["PropertyElement1"], args.number(0))),
        ("Orientation", _enum(lookup_values["PropertyElement2"], args.number(1))),
        ("Theme", _enum(lookup_values["PropertyElement3"], args.number(3))),
        ("Title", args.text(4)),
        ("Subtitle", args.text(5)),
    ]
    return [(label, value) for label, value in rows if value]


def _enum(values: list[str], index: int) -> str:
    """One of actiont.lookup_values' lists, by index -- "" for an index it doesn't have,
    which is how a value from a newer Tasker arrives and is better left blank than guessed.
    """
    return values[index] if 0 <= index < len(values) else ""


def _draw_element(
    element: Element, options: PreviewOptions, depth: int = 0, editing: CanvasEditing | None = None, *, state: RunState
) -> None:
    """Place one element on the canvas and hand it to the drawer for its type.

    `editing` turns the frame into something the browser can pick up and drag: it gains a
    class the pointer handlers look for and its geometry as data attributes.  The numbers
    are repeated there rather than read back out of the style because that is what the drag
    arithmetic starts from, and parsing "left: 388px" to get 388 back would be reconstructing
    a value this already has.
    """
    box = element_geometry(element, options.landscape)
    if box is None:
        return
    x, y, width, height = box
    args = ElementArgs(element)

    # An element Tasker hides is DIMMED, not left out.  It is part of the Scene and a Task can
    # make it visible at any time, so a preview that dropped it would be hiding the designer's
    # own work; drawn at full strength it would claim to be on screen when it is not.  The
    # tooltip names the bit, so the dimming has somewhere to be explained.
    hidden = element_is_hidden(element)

    frame = ui.element("div").style(
        f"position: absolute; left: {x}px; top: {y}px; width: {width}px; height: {height}px;"
        "box-sizing: border-box; overflow: hidden;"
        + ("opacity: 0.35;" if hidden else "")
        + ("cursor: move;" if editing else ""),
    )
    if editing:
        frame.classes("mt-el").props(
            f'data-sr="{element.get("sr", "")}" data-x="{x}" data-y="{y}" data-w="{width}" data-h="{height}"',
        )
    with frame:
        drawer = _DRAWERS.get(element.tag, _draw_unknown)
        if drawer in _STATEFUL_DRAWERS:
            drawer(element, args, width, height, options, depth, state=state)
        else:
            drawer(element, args, width, height, options, depth)
        if options.show_bounds:
            _draw_bounds(element, width, height)
        if options.show_tasks:
            _draw_task_badges(element, state=state)

    # A tooltip on a frame the user is dragging gets in the way of the thing it describes,
    # so the designer does without: the Inspector is showing all of it anyway.  That reason
    # does not survive the trip to the Preview, where the dialog holding that Inspector is
    # closed -- so the surface says which it is rather than this inferring it from `editing`.
    if not editing or editing.tooltips:
        _attach_tooltip(frame, element, args, box, state=state)


def _draw_bounds(element: Element, width: int, height: int) -> None:
    """A hairline round every element plus its name, so overlapping and zero-content
    elements (an empty Rect used as a spacer, a Web element that draws nothing here) are
    visible at all.  Off by default for anyone who wants to see the Scene rather than its
    construction.
    """
    ui.element("div").style(
        "position: absolute; inset: 0; pointer-events: none;"
        "outline: 1px dashed rgba(59,130,246,0.55); outline-offset: -1px;",
    )
    name = element_name(element) or element.tag.replace("Element", "")
    if width >= 60 and height >= 24:
        ui.label(name).style(
            "position: absolute; left: 2px; top: 1px; pointer-events: none;"
            "font: 11px/1.2 monospace; color: rgba(37,99,235,0.95);"
            "background: rgba(255,255,255,0.72); padding: 0 3px; border-radius: 2px;"
            "max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;",
        )


def _draw_task_badges(element: Element, state: RunState) -> None:
    """The Tasks this element fires, along its bottom edge.  A Scene's elements are mostly
    there to run Tasks, and which one is not visible in any amount of geometry.
    """
    tasks = element_tasks(element, state=state)
    if not tasks:
        return
    with ui.element("div").style(
        "position: absolute; left: 2px; right: 2px; bottom: 1px; pointer-events: none;"
        "display: flex; flex-wrap: wrap; gap: 2px; justify-content: flex-end;",
    ):
        for label, task_name in tasks:
            ui.label(f"{label} → {task_name}").style(
                "font: 10px/1.3 monospace; color: #fff; background: rgba(217,119,6,0.92);"
                "padding: 0 4px; border-radius: 3px; max-width: 100%;"
                "overflow: hidden; text-overflow: ellipsis; white-space: nowrap;",
            )


def _attach_tooltip(
    frame: ui.element,
    element: Element,
    args: ElementArgs,
    box: tuple[int, int, int, int],
    state: RunState,
) -> None:
    """Everything about this element that the drawing cannot carry: its type, its real
    geometry, the Tasks it fires, and -- the reason this exists -- every %variable it
    depends on, named.  A Scene whose colours are all variables draws as hatching, and
    without this there would be nowhere to find out what those variables are called.
    """
    x, y, width, height = box
    lines = [
        f"{element_name(element) or translate_string('(no name)')}  ({element.tag.replace('Element', '')})",
        f"{translate_string('Position')}: {x},{y}   {translate_string('Size')}: {width}x{height}",
    ]
    variables = sorted({value for index in range(9) for value in (args.text(index),) if value.startswith("%")})
    if variables:
        lines.append(f"{translate_string('Variables')}: {', '.join(variables)}")
    # <flags> says whether Tasker shows this element at all, whether it is fixed in place
    # rather than scrolling with the Scene, whether it sits behind the others and whether it
    # takes the initial focus -- none of which the drawing can carry, and the first of which
    # is the reason a dimmed element is dimmed (see _draw_element).
    if flag_names := element_flag_names(element):
        lines.append(f"{translate_string('Flags')}: {', '.join(flag_names)}")
        if element_is_hidden(element):
            lines.append(translate_string("Not visible until a Task shows it"))
    lines.extend(f"{label} → {task_name}" for label, task_name in element_tasks(element, state=state))
    with frame:
        ui.tooltip("\n".join(lines)).style("white-space: pre-wrap")


# ------------------------------------------------------------------
# Shared pieces
# ------------------------------------------------------------------
def _background_style(element: Element) -> str:
    """The CSS for an element's <RectElement sr="background"> sub-element, or "".

    Text, Button, EditText, CheckBox, Switch, Spinner and Picker elements all carry one, and
    it is where most of a real Scene's colour lives -- fill, border and corner radius.  It is
    a RectElement like any other, so it is drawn by the same code as one.
    """
    background = element.find("RectElement[@sr='background']")
    return "" if background is None else _rect_style(ElementArgs(background))


def _rect_style(args: ElementArgs) -> str:
    """The fill, border and corners of a RectElement, from its arguments (actionc.py
    "RectElement": 0 Name, 1 Shader, 2 Color, 3 End Color, 4 Border Width, 5 Border Color,
    6 Corner Radius, 7 Rounded Corners).
    """
    fill = args.colour(2)
    end_fill = args.colour(3)
    shader = SHADER_GRADIENTS.get(args.number(1))

    if fill.is_variable or end_fill.is_variable:
        style = f"background: {VARIABLE_FILL};"
    elif shader and end_fill.known:
        style = f"background: {shader.format(start=fill.css, end=end_fill.css)};"
    elif fill.known:
        style = f"background: {fill.css};"
    else:
        style = ""

    border_width = args.number(4)
    if border_width > 0:
        border_colour = args.colour(5, fallback="rgba(148,163,184,0.9)")
        style += f"border: {border_width}px solid {border_colour.css};"

    radius = args.number(6)
    if radius > 0:
        top_left, top_right, bottom_right, bottom_left = ROUNDED_CORNERS.get(
            args.number(7),
            (True, True, True, True),
        )
        corners = " ".join(f"{radius}px" if on else "0" for on in (top_left, top_right, bottom_right, bottom_left))
        style += f"border-radius: {corners};"
    return style


def _text_style(args: ElementArgs, height: int, options: PreviewOptions) -> str:
    """The font side of a text-bearing element: size, colour, font and the horizontal scale.

    Size is arg2 in sp, so it is multiplied by the toolbar's density (see this module's
    docstring).  "Reduce Text Size" (arg7, Vertical Fit Mode) is honoured by clamping to the
    element's height, because that is exactly what the setting is for -- Scenes really do
    carry text nominally taller than the box holding it, and Tasker shrinks it rather than
    clipping it.
    """
    size_px = max(1.0, args.number(2, 14) * options.density)
    if args.number(7) == FIT_REDUCE:
        size_px = min(size_px, height * 0.8)

    colour = args.colour(4, fallback="#000000")
    style = f"font-size: {round(size_px, 1)}px; line-height: 1.2;"
    style += f"color: {'rgba(100,116,139,0.95)' if colour.is_variable else colour.css};"

    font = args.text(5)
    if font and not font.startswith("%"):
        # A Tasker font name only resolves on the device; naming it here costs nothing when
        # it doesn't match anything installed, and matches when it is a common family.
        style += f"font-family: '{font}', sans-serif;"

    # Text Width Scale Percent (arg3): 100 is normal.  Anything else stretches or squeezes
    # the glyphs horizontally, which is a scaleX and not a font size.
    scale = args.number(3, 100)
    if scale > 0 and scale != 100:
        style += f"display: inline-block; transform: scaleX({round(scale / 100, 3)}); transform-origin: left center;"
    return style


def _position_style(args: ElementArgs, index: int = 6) -> str:
    """Where the text sits inside its box -- arg6 on Text/Button/EditText, indexing
    actiont's "TextElement1" list.
    """
    justify, align = POSITION_FLEX.get(args.number(index), ("center", "center"))
    return f"display: flex; justify-content: {justify}; align-items: {align};"


def _text_document(snippet: str, base_style: str, position_style: str) -> str:
    """A Text element's markup as a document, styled the way the Scene styles the element.

    The element's own font, colour, width scale and position are put on the document rather
    than left behind with the frame: a Text element's HTML is a styled *sentence*, and Tasker
    draws it over the size and colour set on the element, with the markup's own tags
    overriding those from the inside.  Handing the frame those same two rules -- the box's
    alignment on <body>, the element's text style on the sentence -- is what makes the drawn
    result the element rather than a bare snippet in a browser's default serif.

    Mirrors the DOM the plain-text branch builds (a flex box holding one styled label), with
    one deliberate difference: no white-space: pre-wrap.  Runs of spaces and newlines collapse
    in markup -- which is why the author wrote a <br> to break the line -- and honouring them
    literally turns a two-line label into three or four and clips what should have fitted.
    The plain-text branch keeps pre-wrap for the opposite reason: there, a newline in the
    value is the only line break there is.
    """
    return (
        "<!DOCTYPE html><html><head><style>"
        "html, body { margin: 0; padding: 0; height: 100%; background: transparent; }"
        f"body {{ {position_style} overflow: hidden; }}"
        f".t {{ {base_style} max-width: 100%; text-align: center; overflow-wrap: break-word; }}"
        f'</style></head><body><div class="t">{snippet}</div></body></html>'
    )


def _text_content(
    args: ElementArgs,
    index: int,
    options: PreviewOptions,
    height: int,
    *,
    html_format: bool = False,
) -> None:
    """Draw the element's text, marked as variable-driven when that is what it is.

    `html_format` says the value is markup, and only the caller can know that: it is arg8 on
    a TextElement, but arg8 on an EditTextElement is Maximum Characters, so reading it here
    would call an input that allows two characters an HTML one.

    Markup is rendered, in the sandboxed frame described at WEB_SANDBOX -- the same frame
    the Web element uses, for the same reason.  A frame rather than markup put straight into
    this page even for something as small as one <b>: the sentence can carry a <style> block,
    and a stylesheet loose in the preview restyles the whole of it (which is not theoretical
    -- see the Map view, where exactly that blanked out a Project).  Its own styling is
    handed to the frame, so what is drawn is still this element -- see _text_document.

    A value with no markup in it, or one that is wholly a %variable, has nothing to render:
    those keep the plain label, with any stray tags stripped rather than shown as source (an
    element whose text is one styled sentence would otherwise fill its box with angle
    brackets, and a preview of a Scene made of those says nothing about the Scene).
    """
    raw = args.text(index)
    if not raw:
        return

    if html_format and is_inline_html(raw):
        html_frame(
            _text_document(raw, _text_style(args, height, options), _position_style(args)),
            "position: absolute; inset: 0; width: 100%; height: 100%;",
        )
        corner_badge("HTML")
        return

    text = html.unescape(HTML_TAG.sub("", raw)).strip() if html_format else raw
    if not text:
        return

    style = _text_style(args, height, options)
    if raw.startswith("%"):
        # Not resolvable here, and pretending otherwise would put a variable name on screen
        # where the user expects to judge what their Scene looks like.  Mark it instead.
        style += "font-style: italic; text-decoration: underline dotted; opacity: 0.85;"
    ui.label(text).style(f"{style} max-width: 100%; overflow: hidden; white-space: pre-wrap; text-align: center;")
    if html_format:
        corner_badge("HTML")


def corner_badge(text: str) -> None:
    """A small marker in an element's top-right: that what is drawn there is the element's
    own markup ("HTML"), or something the drawing cannot show (an input type).  Positioned
    against the element's frame, so it is drawn from inside a drawer rather than by the
    caller.
    """
    ui.label(text).style(
        "position: absolute; right: 2px; top: 1px; font: 10px/1.2 monospace;"
        "color: rgba(71,85,105,0.9); background: rgba(226,232,240,0.85);"
        "padding: 0 3px; border-radius: 2px;",
    )


def placeholder_box(icon: str, caption: str, detail: str = "") -> None:
    """The panel drawn for anything whose real content is not reachable from here -- an
    Android-side image, a video, a map, a web page.  Says what it is and what it points at,
    rather than drawing an empty box that reads as a bug.
    """
    with ui.element("div").style(
        f"position: absolute; inset: 0; display: flex; flex-direction: column; gap: 2px;"
        f"align-items: center; justify-content: center; text-align: center; padding: 2px;"
        f"background: {PLACEHOLDER_FILL}; border: {PLACEHOLDER_EDGE}; box-sizing: border-box;",
    ):
        ui.icon(icon).style("font-size: 22px; color: rgba(100,116,139,0.95);")
        ui.label(translate_string(caption)).style("font: 11px/1.2 monospace; color: rgba(71,85,105,0.95);")
        if detail:
            ui.label(detail).style(
                "font: 10px/1.2 monospace; color: rgba(100,116,139,0.95); max-width: 96%;"
                "overflow: hidden; text-overflow: ellipsis; white-space: nowrap;",
            )


def is_inline_html(source: str) -> bool:
    """Whether this Source is a page the preview can draw rather than a reference to one.

    A Web element's Source is only markup in "Direct" mode, and even then only when there is
    markup in it -- Tasker is happy to hold a bare URL, a lone %variable or a plain sentence
    there.  A value that is wholly a %variable is a page nothing in a backup file can show,
    whatever it looks like, so it is excluded too.
    """
    stripped = source.strip()
    return bool(stripped) and not stripped.startswith("%") and bool(HTML_MARKUP.search(stripped))


def _sandboxed_document(source: str) -> str:
    """`source` with WEB_CSP inserted into it, ready to be a frame's srcdoc."""
    policy = f'<meta http-equiv="Content-Security-Policy" content="{WEB_CSP}">'
    for pattern, insert in ((HTML_HEAD_OPEN, policy), (HTML_OPEN, f"<head>{policy}</head>")):
        match = pattern.search(source)
        if match:
            return source[: match.end()] + insert + source[match.end() :]
    # A fragment rather than a whole document (no <html>, no <head>): give it the head it
    # never had.  The doctype leads, so this still parses in standards mode.
    return f"<!DOCTYPE html><html><head>{policy}</head><body>{source}</body></html>"


def html_frame(source: str, box_style: str, background: str = "transparent") -> None:
    """The frame a Scene's own HTML is drawn in -- see WEB_SANDBOX for what it may do.

    `background` is what shows through where the markup paints nothing.  It defaults to
    transparent because a frame is drawn *over* the element's own background -- the
    <RectElement sr="background"> that gives a Text element its fill and its rounded corners
    -- and an opaque frame would hide the very thing the text is meant to sit on.  A Web
    element passes white: a WebView's page starts on white on the phone, and every colour in
    a page written for one is chosen against that.

    pointer-events are off.  The preview is a picture, and the Legacy designer's drag has to
    reach the element frame underneath rather than stop at the page drawn on it.
    """
    frame = ui.element("iframe").style(f"border: 0; background: {background}; pointer-events: none;{box_style}")
    # Set through props rather than props()' string parsing: a whole HTML document holds every
    # character that syntax uses.  sandbox has to be present-but-empty, which is the one thing
    # "sandbox" alone as a boolean prop would not say.
    frame.props["srcdoc"] = _sandboxed_document(source)
    frame.props["sandbox"] = WEB_SANDBOX
    frame.props["referrerpolicy"] = "no-referrer"
    # Not loading="lazy": the document is inline, so there is nothing to defer, and a frame
    # inside a canvas the view scales with a CSS transform is exactly the case where the
    # browser's own "is this on screen yet" guess would leave it blank.
    frame.props["scrolling"] = "no"


def _draw_inline_html(source: str, width: int, height: int, options: PreviewOptions) -> None:
    """Draw a Legacy Web element's own HTML at its place on the canvas.

    The frame is laid out at the element's size in *CSS* pixels and then scaled back up by
    the density, rather than being handed the raw <geom> size: a WebView lays its page out in
    CSS pixels, so a 1440px-wide element on a 2.75 phone is a 524px-wide viewport, and giving
    the page 1440 would draw it at a third of the size it has on the phone.  Same sp->px
    conversion _text_style makes, for the same reason.
    """
    viewport_width = max(1, round(width / options.density))
    viewport_height = max(1, round(height / options.density))
    html_frame(
        source,
        f"position: absolute; left: 0; top: 0; width: {viewport_width}px; height: {viewport_height}px;"
        f"transform: scale({options.density}); transform-origin: top left;",
        background="#fff",
    )


# ------------------------------------------------------------------
# One drawer per element type.  Argument numbers per actionc.action_codes.
# ------------------------------------------------------------------
def _draw_text(
    element: Element,
    args: ElementArgs,
    _width: int,
    height: int,
    options: PreviewOptions,
    _depth: int,
) -> None:
    """TextElement: 1 Text, 2 Text Size, 3 Width Scale %, 4 Colour, 5 Font, 6 Position,
    7 Vertical Fit Mode, 8 Text Format.

    Text Format is read here rather than inside _text_content because arg8 only means the
    format on this element type -- see _text_content.
    """
    overflow = "auto" if args.number(7) == FIT_SCROLL else "hidden"
    with ui.element("div").style(
        f"position: absolute; inset: 0; box-sizing: border-box; overflow: {overflow};"
        f"{_background_style(element)}{_position_style(args)}",
    ):
        _text_content(args, 1, options, height, html_format=args.number(8) == FORMAT_HTML)


def _draw_button(
    element: Element,
    args: ElementArgs,
    _width: int,
    height: int,
    options: PreviewOptions,
    _depth: int,
) -> None:
    """ButtonElement: 1 Label, 2 Label Size, 3 Width Scale %, 4 Label Colour, 5 Font,
    6 Position, 7 Icon.

    A Button with no background sub-element still looks like a button on a phone, so it gets
    a neutral raised fill here -- the one place this file draws something the XML does not
    state, and it is Tasker's default rather than an invention.
    """
    background = _background_style(element)
    if not background:
        background = "background: #e2e8f0; border: 1px solid rgba(100,116,139,0.55); border-radius: 6px;"
    with ui.element("div").style(
        f"position: absolute; inset: 0; box-sizing: border-box; gap: 4px; overflow: hidden;"
        f"{background}{_position_style(args)}",
    ):
        kind, value = args.image(7)
        if kind:
            ui.icon("image" if kind == "file" else "star").style("font-size: 16px; opacity: 0.75;").tooltip(value)
        _text_content(args, 1, options, height)


def _draw_edit_text(
    element: Element,
    args: ElementArgs,
    _width: int,
    height: int,
    options: PreviewOptions,
    _depth: int,
) -> None:
    """EditTextElement: 1 Text, 2 Text Size, 3 Width Scale %, 4 Colour, 5 Font, 6 Position,
    7 Input Type, 8 Maximum Characters (1000 means unlimited).
    """
    background = _background_style(element)
    if not background:
        background = "border-bottom: 2px solid rgba(100,116,139,0.75);"
    with ui.element("div").style(
        f"position: absolute; inset: 0; box-sizing: border-box; overflow: hidden;{background}{_position_style(args)}",
    ):
        _text_content(args, 1, options, height)
    input_type = _enum(lookup_values["EditTextElement"], args.number(7))
    if input_type:
        corner_badge(input_type)


def _draw_rect(
    _element: Element,
    args: ElementArgs,
    _width: int,
    _height: int,
    _options: PreviewOptions,
    _depth: int,
) -> None:
    """RectElement -- see _rect_style for the arguments."""
    ui.element("div").style(f"position: absolute; inset: 0; box-sizing: border-box; {_rect_style(args)}")


def _draw_oval(
    _element: Element,
    args: ElementArgs,
    _width: int,
    _height: int,
    _options: PreviewOptions,
    _depth: int,
) -> None:
    """OvalElement: the same as a Rect minus the corner arguments -- 1 Shader, 2 Colour,
    3 End Colour, 4 Border Width, 5 Border Colour.  Its shape is the ellipse of its box.
    """
    ui.element("div").style(
        f"position: absolute; inset: 0; box-sizing: border-box; border-radius: 50%; {_rect_style(args)}",
    )


def _draw_image(
    _element: Element,
    args: ElementArgs,
    _width: int,
    _height: int,
    _options: PreviewOptions,
    _depth: int,
) -> None:
    """ImageElement: 1 Image, 2 Alpha (0-255).

    Neither kind of image is reachable: a built-in icon name ("mw_action_info_outline") is
    Tasker's own resource, and a file path is on the Android device.  The alpha is applied to
    the placeholder anyway -- an image at alpha 40 is nearly invisible on the phone, and a
    preview that draws it at full strength would be showing a layout the user does not have.
    """
    kind, value = args.image(1)
    alpha = args.number(2, 255)
    with ui.element("div").style(f"position: absolute; inset: 0; opacity: {round(max(0, min(alpha, 255)) / 255, 3)};"):
        if kind == "icon":
            placeholder_box("image", "Tasker icon", value)
        elif kind == "file":
            placeholder_box("insert_photo", "Image on device", value.rsplit("/", 1)[-1])
        else:
            placeholder_box("hide_image", "No image set")


def _draw_check_box(
    element: Element,
    args: ElementArgs,
    width: int,
    height: int,
    _options: PreviewOptions,
    _depth: int,
) -> None:
    """CheckBoxElement: 1 Checked."""
    _draw_toggle_glyph(element, args, width, height, "check_box", "check_box_outline_blank")


def _draw_switch(
    element: Element,
    args: ElementArgs,
    width: int,
    height: int,
    _options: PreviewOptions,
    _depth: int,
) -> None:
    """SwitchElement: 1 Checked."""
    _draw_toggle_glyph(element, args, width, height, "toggle_on", "toggle_off")


def _draw_toggle_glyph(
    element: Element,
    args: ElementArgs,
    width: int,
    height: int,
    on_icon: str,
    off_icon: str,
) -> None:
    """The shared body of Checkbox and Switch: a background sub-element, and a glyph sized
    to the box showing the state arg1 holds.
    """
    checked = args.number(1) == 1
    with ui.element("div").style(
        f"position: absolute; inset: 0; box-sizing: border-box; display: flex;"
        f"align-items: center; justify-content: center; {_background_style(element)}",
    ):
        ui.icon(on_icon if checked else off_icon).style(
            f"font-size: {round(max(12.0, min(width, height) * 0.7), 1)}px;"
            f"color: {'#2563eb' if checked else 'rgba(100,116,139,0.9)'};",
        )


def _draw_slider(
    _element: Element,
    args: ElementArgs,
    _width: int,
    height: int,
    _options: PreviewOptions,
    _depth: int,
) -> None:
    """SliderElement: 1 Orientation, 2 Min, 3 Max, 4 Default, 5 Show Indicators, 6 Icon.

    The thumb sits where the Default value falls between Min and Max, so the preview shows
    the position the Scene actually opens at rather than a generic half-way slider.
    """
    minimum, maximum, default = args.number(2), args.number(3, 100), args.number(4)
    span = maximum - minimum
    fraction = 0.0 if span <= 0 else max(0.0, min(1.0, (default - minimum) / span))
    vertical = args.number(1) != 0
    with ui.element("div").style(
        "position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; padding: 4px;",
    ):
        track = ui.element("div").style(
            "position: relative; background: rgba(100,116,139,0.45); border-radius: 999px;"
            + ("width: 6px; height: 100%;" if vertical else "height: 6px; width: 100%;"),
        )
        with track:
            along = f"calc({round(fraction * 100, 1)}% - 7px)"
            thumb = f"bottom: {along}; left: -4px;" if vertical else f"left: {along}; top: -4px;"
            ui.element("div").style(
                f"position: absolute; {thumb} width: 14px; height: 14px;border-radius: 50%; background: #2563eb;",
            )
    if height >= 26:
        ui.label(f"{minimum} \u2013 {maximum}  ({args.raw_number(4) or default})").style(
            "position: absolute; left: 2px; bottom: 1px; font: 10px/1.2 monospace; color: rgba(71,85,105,0.95);",
        )


def _draw_toggle(
    _element: Element,
    args: ElementArgs,
    _width: int,
    height: int,
    options: PreviewOptions,
    _depth: int,
) -> None:
    """ToggleElement: 1 On, 2 Off Label, 3 On Label, 4 Label Size, 5 Width Scale %,
    6 Label Colour.

    Its argument numbering is its own -- the label size/colour are at 4 and 6 rather than at
    2 and 4 -- so it cannot share the text helpers, which read the common layout.
    """
    is_on = args.number(1) == 1
    label = args.text(3) if is_on else args.text(2)
    colour = args.colour(6, fallback="#000000")
    size_px = max(1.0, args.number(4, 14) * options.density)
    with ui.element("div").style(
        "position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; gap: 6px;"
        "background: #e2e8f0; border: 1px solid rgba(100,116,139,0.55); border-radius: 6px; box-sizing: border-box;",
    ):
        ui.icon("toggle_on" if is_on else "toggle_off").style(
            f"font-size: {max(14, min(height * 0.6, 28))}px; color: {'#2563eb' if is_on else 'rgba(100,116,139,0.9)'};",
        )
        if label:
            ui.label(label).style(
                f"font-size: {round(size_px, 1)}px; line-height: 1.2;"
                f"color: {'rgba(100,116,139,0.95)' if colour.is_variable else colour.css};"
                "overflow: hidden; white-space: nowrap; text-overflow: ellipsis;",
            )


def _draw_web(
    _element: Element,
    args: ElementArgs,
    width: int,
    height: int,
    options: PreviewOptions,
    _depth: int,
) -> None:
    """WebElement: 1 Mode (URL / File / Direct), 2 Source.

    In "Direct" mode the Source *is* the page, so it is drawn -- inside the frame described
    at WEB_SANDBOX, which renders markup without running it.  That distinction is the whole
    reason this can be drawn at all: a shared Tasker project arrives from a stranger, and
    what it holds must not get at this app's page or the network.  It draws no script, so a
    page that builds itself in JavaScript previews as whatever its markup alone amounts to.

    "URL" and "File" name a page on the network or on the Android device.  Neither is here
    and neither is fetched, so those keep the panel reporting the mode and the source.
    """
    source = args.text(2)
    if args.number(1) == WEB_MODE_DIRECT and is_inline_html(source):
        _draw_inline_html(source, width, height, options)
        corner_badge("HTML")
        return
    mode = _enum(lookup_values["WebElement"], args.number(1)) or "?"
    summary = source.splitlines()[0][:80] if source else translate_string("(empty)")
    placeholder_box("public", f"Web ({mode})", summary)


def _draw_video(
    _element: Element,
    args: ElementArgs,
    _width: int,
    _height: int,
    _options: PreviewOptions,
    _depth: int,
) -> None:
    """VideoElement.  MapTasker has no argument table for this one (it is absent from
    actionc.action_codes), so nothing beyond arg0's name is claimed about it -- see this
    module's docstring on not guessing.
    """
    placeholder_box("movie", "Video", args.text(1))


def _draw_doodle(
    _element: Element,
    args: ElementArgs,
    _width: int,
    _height: int,
    _options: PreviewOptions,
    _depth: int,
) -> None:
    """DoodleElement: 1 Doodle (a bitmap cached on the device), 2 Alpha."""
    _, path = args.image(1)
    placeholder_box("draw", "Doodle", path.rsplit("/", 1)[-1] if path else "")


def _draw_map(
    _element: Element,
    args: ElementArgs,
    _width: int,
    _height: int,
    _options: PreviewOptions,
    _depth: int,
) -> None:
    """SceneElement -- Tasker's Map element, despite the tag: 1 Lat/Long, 2 Zoom,
    3 Show Traffic, 4 Show Satellite, 5 Show Roads.
    """
    placeholder_box("map", "Map", args.text(1))


def _draw_picker(
    element: Element,
    args: ElementArgs,
    _width: int,
    height: int,
    _options: PreviewOptions,
    _depth: int,
) -> None:
    """PickerElement: 1 Min, 2 Max, 3 Default, 4 Wrap Around, 5 Format.  Drawn as the
    number spinner it is -- chevrons above and below the default value.
    """
    with ui.element("div").style(
        f"position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center;"
        f"justify-content: center; box-sizing: border-box; {_background_style(element)}",
    ):
        compact = height < 60
        if not compact:
            ui.icon("expand_less").style("font-size: 16px; color: rgba(100,116,139,0.9);")
        ui.label(args.text(3) or str(args.number(3))).style(
            "font: 14px/1.2 monospace; color: #0f172a;",
        )
        if not compact:
            ui.icon("expand_more").style("font-size: 16px; color: rgba(100,116,139,0.9);")


def _draw_list(
    element: Element,
    args: ElementArgs,
    width: int,
    height: int,
    options: PreviewOptions,
    depth: int,
    state: RunState,
) -> None:
    """ListElement: 1 Source, 2/3 Selection Mode, 5 Horizontal Space, 6 Vertical Space --
    and, at arg4, a whole nested <Scene> that is the layout of one row.
    """
    _draw_item_layout(element, args, "arg4", width, height, options, depth, translate_string("List"), state=state)


def _draw_spinner(
    element: Element,
    args: ElementArgs,
    width: int,
    height: int,
    options: PreviewOptions,
    depth: int,
    state: RunState,
) -> None:
    """SpinnerElement: 1 Source, 2 Variable, and the item layout <Scene> at arg3."""
    _draw_item_layout(element, args, "arg3", width, height, options, depth, translate_string("Spinner"), state=state)


def _draw_item_layout(
    element: Element,
    args: ElementArgs,
    slot: str,
    width: int,
    height: int,
    options: PreviewOptions,
    depth: int,
    kind: str,
    state: RunState,
) -> None:
    """Draw a List's or Spinner's row template: the nested <Scene sr="val"> Tasker stores
    inside the element, laid out on its own little canvas and scaled to this element's width.

    One row, not a repeated list, because the rows come from a Tasker variable at runtime --
    there is no list here to draw.  What the preview can honestly show is the shape of a row,
    which is what the nested Scene is.  Recursion is capped at MAX_ITEM_DEPTH; a template
    that itself holds a List draws that inner one as a labelled box.
    """
    nested = element.find(f"Scene[@sr='{slot}']/Scene[@sr='val']")
    source = _enum(lookup_values["ListElement1"], args.number(1))
    variable = args.text(2)
    caption = f"{kind}: {source}{f' — {variable}' if variable else ''}"

    if nested is None or depth >= MAX_ITEM_DEPTH:
        placeholder_box("list", caption)
        return

    item = scene_dimensions(nested, landscape=False)
    if item is None:
        placeholder_box("list", caption)
        return
    item_width, item_height = item
    scale = min(1.0, width / item_width) if item_width else 1.0

    with ui.element("div").style(
        f"position: absolute; inset: 0; box-sizing: border-box; overflow: hidden;"
        f"background: rgba(148,163,184,0.10); border: {PLACEHOLDER_EDGE};",
    ):
        ui.label(caption).style(
            "position: absolute; left: 2px; top: 1px; z-index: 2; font: 10px/1.2 monospace;"
            "color: rgba(71,85,105,0.95); background: rgba(255,255,255,0.75); padding: 0 3px; border-radius: 2px;",
        )
        with ui.element("div").style(
            f"position: absolute; left: 0; top: 14px; width: {item_width}px; height: {item_height}px;"
            f"transform: scale({round(scale, 4)}); transform-origin: top left;"
            f"background: {_canvas_background(nested).css}; overflow: hidden;",
        ):
            for child in paint_order(nested):
                _draw_element(child, options, depth + 1, state=state)
        if height > item_height * scale + 20:
            ui.label("⋮").style(
                "position: absolute; left: 50%; bottom: 2px; transform: translateX(-50%);"
                "font: 14px/1 monospace; color: rgba(100,116,139,0.9);",
            )


def _draw_unknown(
    element: Element,
    _args: ElementArgs,
    _width: int,
    _height: int,
    _options: PreviewOptions,
    _depth: int,
) -> None:
    """An element type this app has no argument table for -- a newer Tasker's, most likely.

    Drawn as a labelled box at its true geometry rather than skipped: where it is and how big
    it is are known from <geom> and are worth showing, and the alternative is a Scene that
    silently previews with a hole in it.
    """
    placeholder_box("widgets", element.tag.replace("Element", ""), element_name(element))


_DRAWERS = {
    "TextElement": _draw_text,
    "ButtonElement": _draw_button,
    "EditTextElement": _draw_edit_text,
    "RectElement": _draw_rect,
    "OvalElement": _draw_oval,
    "ImageElement": _draw_image,
    "CheckBoxElement": _draw_check_box,
    "SwitchElement": _draw_switch,
    "SliderElement": _draw_slider,
    "ToggleElement": _draw_toggle,
    "WebElement": _draw_web,
    "VideoElement": _draw_video,
    "DoodleElement": _draw_doodle,
    "SceneElement": _draw_map,
    "PickerElement": _draw_picker,
    "ListElement": _draw_list,
    "SpinnerElement": _draw_spinner,
}


# The drawers that draw a whole Scene inside the element (a row's layout), and so need the run's
# state to draw it with; _draw_element hands them the state and every other drawer none.
_STATEFUL_DRAWERS = frozenset({_draw_list, _draw_spinner})
