"""Scene Preview: draw a Scene as a picture rather than as a list of element names.

This is the drawing half of the "Preview" button on the Add/Edit Scene dialogs; the view
that hosts it (toolbar, scroll area, theming) is guiwins.NiceGuiSceneView, and the button
itself is in guiwins._build_scene_editor_body.

Both kinds of Scene are drawn, by two renderers that share nothing but their conventions,
because the two formats share nothing:

  * LEGACY is a pixel canvas -- <widthPort>x<heightPort>, every element carrying a <geom> of
    "x,y,w,h" into it.  That is enough to place things exactly, so draw_scene does: absolutely
    positioned divs at their real coordinates inside a fixed-size canvas, scaled as a whole by
    one CSS transform.  Nothing re-flows and nothing is guessed at.

  * VERSION 2 is a declarative component tree with no canvas and no coordinates -- Columns,
    Rows and modifiers that lay themselves out inside whatever screen they are given.  So
    draw_v2_layout walks the tree and maps it onto CSS flexbox, inside a device-sized frame.
    Compose's arrangements and alignments are flexbox's justify-content and align-items,
    which is why this is a translation rather than a re-implementation.

WHAT NEITHER OF THEM IS

Tasker's own renderer.  Four things stop that, and each is marked on screen rather than
papered over -- the whole point of a preview is that what it shows can be trusted:

  * %variables.  Real Scenes are full of them -- "%titlecolor" as a colour, "%remfont" as a
    font, "%svd_title" as a Text's whole content -- and nothing in a backup file says what
    they hold.  Picking a plausible value would be drawing a confident lie, so a
    variable-valued colour draws as a hatched swatch that names the variable, and variable
    text draws marked as variable text.  What the user sees is "this part is variable-driven",
    which is true.

  * The screen.  A Legacy Scene needs a density (geometry is in device pixels, text size is in
    Android's sp, and the number converting them belongs to the phone, not the Scene); a V2
    Scene needs a screen size (a declarative layout means nothing without a width to lay out
    in).  Neither is in the backup, so both are toolbar controls rather than constants
    pretending to be facts -- PreviewOptions.density and the frame size passed to
    draw_v2_layout.

  * Theme colours.  V2 names colours by Material 3 role -- "outline", "onSecondaryContainer"
    -- and Android resolves those against the device's own theme, which on Material You is
    generated from the user's wallpaper.  They are resolved here against the M3 baseline
    palette, which is a real answer but not the user's answer; see V2_MATERIAL_PALETTE.

  * Images, and web content this app would have to go and get.  A Legacy <Img> names a
    built-in Tasker icon or a file on the device; a V2 Image names a URL; a Web element in
    URL or File mode names a page in one of those two places.  None is fetched -- the
    device-side ones are unreachable, and the network ones are not a trip a preview should
    make on the user's behalf.  Markup the Scene carries itself is different: a Web element's
    inline page and a Text element's HTML are both here, so both ARE drawn, in a frame that
    renders markup without running it or letting it reach anything.  See _WEB_SANDBOX,
    _draw_web, _v2_draw_web_view and _text_content -- and note that a page which builds
    itself in JavaScript therefore previews as its markup alone.

WHERE THE PROPERTY NAMES COME FROM

Legacy: the tables MapTasker already ships -- actionc.action_codes for the argument roles,
actiont.lookup_values for the enumerations they index into (positions, shaders, corner sets).
Those tables are what the Map output has always used to describe Scene elements in words, so
a preview built on the same numbers cannot drift from what the rest of the app says about the
same Scene.  They are imported, not copied, for exactly that reason.

Version 2: sceneedit's V2_COMPONENT_SCHEMA, V2_CONTAINER_SLOTS and V2_MODIFIER_SCHEMA, which
were themselves read off real decoded <lj> layouts -- and, where the schema and the evidence
disagree, the evidence.  Two live examples: real layouts carry a Size modifier keyed "all"
where the editor's schema lists width/height, and a "Clickable" modifier the schema has never
heard of.  Both are handled here.  This renderer must not be the thing that decides a real
Scene is malformed.

Anything whose meaning is unknown is not drawn.  <flags> is the Legacy example: every element
has one, nothing in this app decodes it, and a guess would be a guess painted at full
confidence.  A V2 modifier or component type this app has never seen is listed in the
component's tooltip and drawn as a labelled box, so it is visible without being invented.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from nicegui import ui

from maptasker.src.actiont import lookup_values
from maptasker.src.maputil2 import is_html_colour, tasker_icon_name, translate_string
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import SCENE_TASK_TYPES

if TYPE_CHECKING:
    import defusedxml.ElementTree

# Tasker's "this orientation has no layout of its own" (sceneedit.UNSET_DIMENSION), which
# appears both as a Scene dimension and inside a <geom>.
UNSET = -1

# sp -> px.  See this module's docstring: not a fact about the Scene, a property of the
# device it would be shown on, so it is a default rather than a constant.
DEFAULT_DENSITY = 2.75
DENSITY_CHOICES = ("1.0", "1.5", "2.0", "2.625", "2.75", "3.0", "3.5")

# A colour this preview cannot know -- a %variable, or an argument the Scene left empty.
# Hatching rather than a flat grey so it reads as "unknown" at a glance instead of as a
# deliberate choice of grey.
VARIABLE_FILL = (
    "repeating-linear-gradient(45deg, rgba(148,163,184,0.45) 0 6px, rgba(148,163,184,0.12) 6px 12px)"
)
# What a placeholder (an image we can't load, a video, a map) is drawn on.
PLACEHOLDER_FILL = "rgba(148,163,184,0.16)"
PLACEHOLDER_EDGE = "1px dashed rgba(148,163,184,0.85)"

# actiont "TextElement1" -- the Position argument on Text/Button/EditText, in its own order:
# Center, Top, Bottom, Left, Right, Top Left, Top Right, Bottom Left, Bottom Right.  Indexed
# by that list rather than by a copy of it, so the two cannot drift.
_POSITION_FLEX: dict[int, tuple[str, str]] = {
    0: ("center", "center"),
    1: ("center", "flex-start"),
    2: ("center", "flex-end"),
    3: ("flex-start", "center"),
    4: ("flex-end", "center"),
    5: ("flex-start", "flex-start"),
    6: ("flex-end", "flex-start"),
    7: ("flex-start", "flex-end"),
    8: ("flex-end", "flex-end"),
}

# actiont "RectElement1" -- Shader: None, Horizontal, Vertical, Diagonal Top Left,
# Diagonal Bottom Left, Radial.  A shader blends the Color into the End Color.
_SHADER_GRADIENTS: dict[int, str] = {
    1: "linear-gradient(to right, {start}, {end})",
    2: "linear-gradient(to bottom, {start}, {end})",
    3: "linear-gradient(to bottom right, {start}, {end})",
    4: "linear-gradient(to top right, {start}, {end})",
    5: "radial-gradient(circle, {start}, {end})",
}

# actiont "RectElement2" -- which corners the Corner Radius applies to: All, Top, Bottom,
# Left, Right.  CSS order is top-left, top-right, bottom-right, bottom-left.
_ROUNDED_CORNERS: dict[int, tuple[bool, bool, bool, bool]] = {
    0: (True, True, True, True),
    1: (True, True, False, False),
    2: (False, False, True, True),
    3: (True, False, False, True),
    4: (False, True, True, False),
}

# actiont "TextElement2" -- Vertical Fit Mode: None, Reduce Text Size, Allow Scrolling.
_FIT_REDUCE = 1
_FIT_SCROLL = 2

# actiont "TextElement3" -- Text Format: Plain Text, Text With Links, HTML.
_FORMAT_HTML = 2
# For the HTML-format text that is NOT rendered -- a value with no real markup in it, or one
# that is wholly a %variable; see _text_content.  Deliberately a blunt "anything between
# angle brackets": this is not parsing the markup, it is removing it.
_HTML_TAG = re.compile(r"<[^>]*>")

# How deep to follow an item layout (a Spinner/List/Picker carries a whole nested <Scene>).
# One level is what makes those elements legible; more would be a Scene inside a Scene inside
# a Scene, drawn at a size nobody can read.
_MAX_ITEM_DEPTH = 1

# actiont "WebElement" -- Mode: URL, File, Direct.  Only "Direct" holds the page itself; the
# other two name something on the network or on the Android device, neither of which is here.
_WEB_MODE_DIRECT = 2

# Does this value carry markup?  Deliberately loose -- one tag, closing tag or doctype is
# enough to call it a page.  A Source without one keeps the placeholder, so a bare URL, a
# lone %variable or a plain sentence is not dressed up as a document it isn't.
_HTML_MARKUP = re.compile(r"<(?:!doctype\b|/?[a-z][a-z0-9]*)(?:\s[^>]*)?/?>", re.IGNORECASE)

# What the frame holding that markup may do: nothing that reaches out of itself.
#
# An empty sandbox is every restriction at once -- most of all no scripts and no
# same-origin -- which is what makes rendering the markup a different act from running it.
# The page draws; it cannot read this app's page, its session or its storage, cannot
# navigate the window it sits in, and cannot submit a form.  A shared Tasker project is
# exactly the sort of file that arrives from a stranger, so this is not negotiable: see
# _draw_web, which stopped at a placeholder for want of it.
_WEB_SANDBOX = ""

# ...and nothing that reaches out to the network.  Without this, an <img src="https://...">
# or an @font-face in a stranger's Scene would tell that host the user just opened the
# backup, which is the network trip this module's docstring declines to make on their behalf.
# Inline CSS is what makes the preview worth looking at, and data: URIs are self-contained,
# so those two are all that is allowed.
_WEB_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; media-src data:"

# Where that policy has to go: a Content-Security-Policy <meta> counts only inside <head>,
# and only before the content it governs.  Slipping it in after the document's own <head>
# (or after <html>, for markup that never opened one) leaves the rest of the document
# exactly as written -- which matters, because prepending a wrapper of our own would put
# the doctype in the body and drop the page into quirks mode, changing the very layout the
# preview exists to show.
_HTML_HEAD_OPEN = re.compile(r"<head(?:\s[^>]*)?>", re.IGNORECASE)
_HTML_OPEN = re.compile(r"<html(?:\s[^>]*)?>", re.IGNORECASE)


@dataclass
class PreviewOptions:
    """What the preview's toolbar controls.  Held together so the view can hand the whole
    lot to draw_scene and re-run it on any change -- every one of these repaints everything.
    """

    landscape: bool = False
    density: float = DEFAULT_DENSITY
    show_bounds: bool = True
    show_tasks: bool = True


@dataclass
class CanvasEditing:
    """Present when the canvas is the Legacy designer's editing surface rather than a
    picture; None when it is the read-only Preview.

    Deliberately holds no callbacks.  Everything about *reacting* to a drag lives in
    guiwins (the pointer handlers are browser-side, and what they report goes back through
    NiceGUI's global event bridge); all this module needs to know is which elements to draw
    the selection on and how far apart the grid is, because those are the only two things
    that change the drawing.  Keeping the split there is what lets the Preview keep calling
    draw_scene with nothing at all and get exactly what it got before.

    `selected` is every element picked out, by sr, in the order they were picked -- a drag
    moves all of them together, and the outlines are what tell the user what "all of them"
    is.  Unlike V2Editing this is a set rather than a run: a Legacy Scene is a pixel canvas
    where any elements at all can be moved by the same delta, so there is no adjacency for a
    selection to have to satisfy.

    `tooltips` is whether the elements keep the hover tooltip the read-only picture gives
    them.  It is the caller's answer rather than a rule here, because the honest answer
    depends on what else is on screen: the designer has an Inspector showing the same
    numbers a few inches away and drops them, while the Preview -- whose dialog, and
    therefore whose Inspector, is closed while it is up -- is the only place those numbers
    can be read at all and keeps them.
    """

    selected: tuple[str, ...] = ()
    snap: int = 1
    tooltips: bool = False


@dataclass
class V2Editing:
    """The Version 2 counterpart of CanvasEditing: present when the V2 canvas is a reorder
    surface rather than a picture, None when it is the read-only Preview.

    `selected` is the run of adjacent siblings currently picked out -- their paths, in the
    form sceneedit.v2_flatten hands out.  A run rather than a single path because a drag
    moves everything selected, and the highlight is what tells the user what that is.

    Like CanvasEditing this holds no callbacks: the gesture is browser-side and what comes
    back goes through NiceGUI's event bridge, so all this module needs to know is which
    components to outline and that paths are wanted on the DOM at all.
    """

    selected: tuple[tuple, ...] = ()


@dataclass(frozen=True)
class Colour:
    """A colour argument, resolved as far as it can be.

    `css` is always safe to put in a stylesheet.  `variable` is the %variable the value came
    from, if it did -- the caller draws those differently (see VARIABLE_FILL), which is the
    whole reason this is not just a string.  `known` is False when the argument was empty,
    a variable, or in a format this app does not recognise; a caller that has a sensible
    default of its own checks it before using `css`.
    """

    css: str
    variable: str = ""
    known: bool = True

    @property
    def is_variable(self) -> bool:
        return bool(self.variable)


def tasker_colour(raw: str | None, fallback: str = "transparent") -> Colour:
    """Turn a Scene's colour argument into something CSS will accept.

    Tasker writes #AARRGGBB -- alpha FIRST -- which CSS reads as #RRGGBBAA, so handing one
    straight to a stylesheet silently produces a different colour with a different
    transparency.  ("#CA33DD20" is a green at 79% opacity; CSS would render it as a blue-ish
    grey at 12%.)  That is the single most important line in this file.
    """
    value = (raw or "").strip()
    if not value:
        return Colour(fallback, known=False)
    if value.startswith("%"):
        return Colour(fallback, variable=value, known=False)
    if value.startswith("#") and len(value) == 9:
        try:
            alpha, red, green, blue = (int(value[i : i + 2], 16) for i in (1, 3, 5, 7))
        except ValueError:
            return Colour(fallback, known=False)
        return Colour(f"rgba({red},{green},{blue},{round(alpha / 255, 3)})")
    if value.startswith("#") and len(value) in (4, 7):
        return Colour(value)
    return Colour(fallback, known=False)


class ElementArgs:
    """The <Str sr="argN"> / <Int sr="argN" val="..."> / <Img sr="argN"> children of one
    Scene element, addressed by their argument number.

    Every element type stores its properties this way, so every drawer below takes one of
    these and reads the argument numbers actionc.py documents for that type.
    """

    def __init__(self, element: defusedxml.ElementTree.Element) -> None:
        self._element = element

    def text(self, index: int, default: str = "") -> str:
        """The <Str> at this argument, or default.  Never None -- an empty <Str sr="arg5"/>
        is extremely common (a font that was never set) and every caller wants "" for it.
        """
        found = self._element.find(f"Str[@sr='arg{index}']")
        if found is None or found.text is None:
            return default
        return found.text

    def number(self, index: int, default: int = 0) -> int:
        """The <Int val="..."> at this argument.  Falls back to the <Str> at the same index
        when there isn't one: Tasker writes some numeric arguments as strings (a Picker's
        Min/Max are <Str>, and can hold a %variable), and a variable there is not a number
        this can use, so it lands on the default like anything else unparseable.
        """
        found = self._element.find(f"Int[@sr='arg{index}']")
        if found is not None:
            try:
                return int(found.get("val", default))
            except (TypeError, ValueError):
                return default
        try:
            return int(self.text(index))
        except ValueError:
            return default

    def raw_number(self, index: int) -> str:
        """The numeric argument exactly as written -- for showing a Slider's "%MaxValue"
        rather than silently substituting the default number() would give back.
        """
        found = self._element.find(f"Int[@sr='arg{index}']")
        return found.get("val", "") if found is not None else self.text(index)

    def image(self, index: int) -> tuple[str, str]:
        """The <Img> at this argument as (kind, value): ("icon", built-in Tasker icon name),
        ("file", a path on the Android device), or ("", "") when the argument is an empty
        <Img/> -- which is how "no icon" is stored, and is common on Buttons.
        """
        found = self._element.find(f"Img[@sr='arg{index}']")
        if found is None:
            return ("", "")
        name = found.findtext("nme", "")
        if name:
            return ("icon", name)
        path = found.findtext("fle", "")
        return ("file", path) if path else ("", "")

    def colour(self, index: int, fallback: str = "transparent") -> Colour:
        return tasker_colour(self.text(index), fallback)


def scene_dimensions(
    scene_element: defusedxml.ElementTree.Element,
    landscape: bool,
) -> tuple[int, int] | None:
    """The canvas size for this orientation, or None when the Scene has no layout for it.

    None is a real answer, not a failure: -1 across a Scene's landscape pair is Tasker's own
    "this orientation has no layout of its own", and the great majority of real Scenes are
    portrait-only.  The caller says so rather than drawing a 0x0 canvas.
    """
    width_tag, height_tag = ("widthLand", "heightLand") if landscape else ("widthPort", "heightPort")
    try:
        width = int(scene_element.findtext(width_tag, "-1"))
        height = int(scene_element.findtext(height_tag, "-1"))
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return width, height


def has_landscape_layout(scene_element: defusedxml.ElementTree.Element) -> bool:
    """Whether the preview's Landscape toggle has anything to show."""
    return scene_dimensions(scene_element, landscape=True) is not None


def element_geometry(
    element: defusedxml.ElementTree.Element,
    landscape: bool,
) -> tuple[int, int, int, int] | None:
    """One element's (x, y, width, height) for this orientation.

    <geom> is eight comma-separated numbers: the portrait x,y,w,h followed by the landscape
    x,y,w,h.  A landscape half of -1,-1,-1,-1 means the element is not placed in landscape,
    and returns None -- the same "nothing to draw" answer as a missing <geom> altogether,
    which is what the background sub-elements carry.
    """
    parts = (element.findtext("geom", "") or "").split(",")
    if len(parts) < 4:
        return None
    offset = 4 if landscape else 0
    if len(parts) < offset + 4:
        return None
    try:
        x, y, width, height = (int(value) for value in parts[offset : offset + 4])
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return x, y, width, height


def element_name(element: defusedxml.ElementTree.Element) -> str:
    """The name the user gave this element in Tasker's Scene editor -- arg0 on every type."""
    return ElementArgs(element).text(0)


def paint_order(scene_element: defusedxml.ElementTree.Element) -> list:
    """The Scene's drawable elements, bottom one first.

    Sorted by the number in the sr attribute ("elements0", "elements1", ... "elements10")
    rather than trusting document order, and numerically rather than as text so elements10
    lands after elements9.  That order is the z-order: the whole-canvas RectElement that
    real Scenes use as a background is elements0, and it has to be painted under everything
    rather than over it.

    Anything without a <geom> is skipped, which is what excludes <PropertiesElement> (the
    Scene's own settings, drawn by the canvas itself) and the <RectElement sr="background">
    sub-elements (drawn by their owner).  An element type this app has never seen is NOT
    skipped -- it gets the fallback drawer, so a Scene from a newer Tasker still previews.
    """
    drawable = [
        child
        for child in scene_element
        if child.tag.endswith("Element") and child.tag != "PropertiesElement" and child.find("geom") is not None
    ]

    def order(element: defusedxml.ElementTree.Element) -> tuple[int, str]:
        sr = element.get("sr", "")
        digits = sr[len("elements") :] if sr.startswith("elements") else ""
        return (int(digits), sr) if digits.isdigit() else (1_000_000, sr)

    return sorted(drawable, key=order)


def element_tasks(element: defusedxml.ElementTree.Element) -> list[tuple[str, str]]:
    """The Tasks this element fires, as (what fires it, Task name) -- "TAP", "LONG TAP",
    "ITEM TAP" and the rest, from sysconst.SCENE_TASK_TYPES.

    The child holds a Task *id*; the name comes out of the loaded backup.  A negative id is
    one of Tasker's anonymous inline Tasks (scenes.process_tasks calls these "fake"), which
    has no name to show, so it is reported as an unnamed Task rather than skipped -- the
    element does still do something when tapped, and that is the point of showing this.
    """
    all_tasks = PrimeItems.tasker_root_elements.get("all_tasks", {})
    found = []
    for child in element:
        label = SCENE_TASK_TYPES.get(child.tag)
        if label is None:
            continue
        task_id = (child.text or "").strip()
        if task_id.startswith("-"):
            found.append((label, translate_string("(unnamed Task)")))
            continue
        task = all_tasks.get(task_id)
        found.append((label, task["name"] if task else f"{translate_string('Task')} {task_id}"))
    return found


# ==========================================
# Drawing
# ==========================================
def draw_scene(
    scene_element: defusedxml.ElementTree.Element,
    width: int,
    height: int,
    options: PreviewOptions,
    editing: CanvasEditing | None = None,
) -> None:
    """Draw the whole canvas, into whatever NiceGUI container is currently open.

    width/height are passed in rather than read off the Scene because the preview shows what
    the *dialog* currently holds, including a size the user has typed but not yet saved (see
    guiwins.NiceGuiSceneView).

    The canvas is a fixed-size element at the Scene's true pixel dimensions with every child
    absolutely positioned at its real coordinates; fitting it on screen is one CSS transform
    applied to the whole thing by the view.  Doing it that way -- rather than scaling every
    coordinate as it is drawn -- means the numbers in the DOM are the numbers in the XML,
    so anything that looks wrong here is wrong in the Scene rather than in the arithmetic.
    """
    background = _canvas_background(scene_element)
    canvas = ui.element("div").classes("mt-scene-canvas").style(
        f"position: relative; width: {width}px; height: {height}px; overflow: hidden;"
        f"transform-origin: top left; background: {background.css};",
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
            _draw_element(element, options, editing=editing)
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
    with ui.element("div").classes("mt-selection").props(f'data-sr="{sr}"').style(
        f"position: absolute; left: {x}px; top: {y}px; width: {width}px; height: {height}px;"
        "box-sizing: border-box; z-index: 10; outline: 2px solid rgba(37,99,235,0.95);"
        "outline-offset: -1px; pointer-events: none;",
    ):
        if not handles:
            return
        for direction, placement, cursor in _HANDLE_POSITIONS:
            ui.element("div").classes("mt-handle").props(f'data-dir="{direction}"').style(
                f"position: absolute; {placement} width: 8px; height: 8px; box-sizing: border-box;"
                f"background: #fff; border: 1px solid rgba(37,99,235,0.95); border-radius: 1px;"
                f"cursor: {cursor}; pointer-events: auto;",
            )


def _canvas_background(scene_element: defusedxml.ElementTree.Element) -> Colour:
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


def scene_properties(scene_element: defusedxml.ElementTree.Element) -> list[tuple[str, str]]:
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
    element: defusedxml.ElementTree.Element,
    options: PreviewOptions,
    depth: int = 0,
    editing: CanvasEditing | None = None,
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

    frame = ui.element("div").style(
        f"position: absolute; left: {x}px; top: {y}px; width: {width}px; height: {height}px;"
        "box-sizing: border-box; overflow: hidden;" + ("cursor: move;" if editing else ""),
    )
    if editing:
        frame.classes("mt-el").props(
            f'data-sr="{element.get("sr", "")}" data-x="{x}" data-y="{y}" data-w="{width}" data-h="{height}"',
        )
    with frame:
        drawer = _DRAWERS.get(element.tag, _draw_unknown)
        drawer(element, args, width, height, options, depth)
        if options.show_bounds:
            _draw_bounds(element, width, height)
        if options.show_tasks:
            _draw_task_badges(element)

    # A tooltip on a frame the user is dragging gets in the way of the thing it describes,
    # so the designer does without: the Inspector is showing all of it anyway.  That reason
    # does not survive the trip to the Preview, where the dialog holding that Inspector is
    # closed -- so the surface says which it is rather than this inferring it from `editing`.
    if not editing or editing.tooltips:
        _attach_tooltip(frame, element, args, box)


def _draw_bounds(element: defusedxml.ElementTree.Element, width: int, height: int) -> None:
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


def _draw_task_badges(element: defusedxml.ElementTree.Element) -> None:
    """The Tasks this element fires, along its bottom edge.  A Scene's elements are mostly
    there to run Tasks, and which one is not visible in any amount of geometry.
    """
    tasks = element_tasks(element)
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
    element: defusedxml.ElementTree.Element,
    args: ElementArgs,
    box: tuple[int, int, int, int],
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
    lines.extend(f"{label} → {task_name}" for label, task_name in element_tasks(element))
    with frame:
        ui.tooltip("\n".join(lines)).style("white-space: pre-line")


# ------------------------------------------------------------------
# Shared pieces
# ------------------------------------------------------------------
def _background_style(element: defusedxml.ElementTree.Element) -> str:
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
    shader = _SHADER_GRADIENTS.get(args.number(1))

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
        top_left, top_right, bottom_right, bottom_left = _ROUNDED_CORNERS.get(
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
    if args.number(7) == _FIT_REDUCE:
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
    justify, align = _POSITION_FLEX.get(args.number(index), ("center", "center"))
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

    Markup is rendered, in the sandboxed frame described at _WEB_SANDBOX -- the same frame
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

    if html_format and _is_inline_html(raw):
        _html_frame(
            _text_document(raw, _text_style(args, height, options), _position_style(args)),
            "position: absolute; inset: 0; width: 100%; height: 100%;",
        )
        _corner_badge("HTML")
        return

    text = html.unescape(_HTML_TAG.sub("", raw)).strip() if html_format else raw
    if not text:
        return

    style = _text_style(args, height, options)
    if raw.startswith("%"):
        # Not resolvable here, and pretending otherwise would put a variable name on screen
        # where the user expects to judge what their Scene looks like.  Mark it instead.
        style += "font-style: italic; text-decoration: underline dotted; opacity: 0.85;"
    ui.label(text).style(f"{style} max-width: 100%; overflow: hidden; white-space: pre-wrap; text-align: center;")
    if html_format:
        _corner_badge("HTML")


def _corner_badge(text: str) -> None:
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


def _placeholder(icon: str, caption: str, detail: str = "") -> None:
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


def _is_inline_html(source: str) -> bool:
    """Whether this Source is a page the preview can draw rather than a reference to one.

    A Web element's Source is only markup in "Direct" mode, and even then only when there is
    markup in it -- Tasker is happy to hold a bare URL, a lone %variable or a plain sentence
    there.  A value that is wholly a %variable is a page nothing in a backup file can show,
    whatever it looks like, so it is excluded too.
    """
    stripped = source.strip()
    return bool(stripped) and not stripped.startswith("%") and bool(_HTML_MARKUP.search(stripped))


def _sandboxed_document(source: str) -> str:
    """`source` with _WEB_CSP inserted into it, ready to be a frame's srcdoc."""
    policy = f'<meta http-equiv="Content-Security-Policy" content="{_WEB_CSP}">'
    for pattern, insert in ((_HTML_HEAD_OPEN, policy), (_HTML_OPEN, f"<head>{policy}</head>")):
        match = pattern.search(source)
        if match:
            return source[: match.end()] + insert + source[match.end() :]
    # A fragment rather than a whole document (no <html>, no <head>): give it the head it
    # never had.  The doctype leads, so this still parses in standards mode.
    return f"<!DOCTYPE html><html><head>{policy}</head><body>{source}</body></html>"


def _html_frame(source: str, box_style: str, background: str = "transparent") -> None:
    """The frame a Scene's own HTML is drawn in -- see _WEB_SANDBOX for what it may do.

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
    frame.props["sandbox"] = _WEB_SANDBOX
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
    _html_frame(
        source,
        f"position: absolute; left: 0; top: 0; width: {viewport_width}px; height: {viewport_height}px;"
        f"transform: scale({options.density}); transform-origin: top left;",
        background="#fff",
    )


# ------------------------------------------------------------------
# One drawer per element type.  Argument numbers per actionc.action_codes.
# ------------------------------------------------------------------
def _draw_text(
    element: defusedxml.ElementTree.Element,
    args: ElementArgs,
    width: int,  # noqa: ARG001
    height: int,
    options: PreviewOptions,
    depth: int,  # noqa: ARG001
) -> None:
    """TextElement: 1 Text, 2 Text Size, 3 Width Scale %, 4 Colour, 5 Font, 6 Position,
    7 Vertical Fit Mode, 8 Text Format.

    Text Format is read here rather than inside _text_content because arg8 only means the
    format on this element type -- see _text_content.
    """
    overflow = "auto" if args.number(7) == _FIT_SCROLL else "hidden"
    with ui.element("div").style(
        f"position: absolute; inset: 0; box-sizing: border-box; overflow: {overflow};"
        f"{_background_style(element)}{_position_style(args)}",
    ):
        _text_content(args, 1, options, height, html_format=args.number(8) == _FORMAT_HTML)


def _draw_button(
    element: defusedxml.ElementTree.Element,
    args: ElementArgs,
    width: int,  # noqa: ARG001
    height: int,
    options: PreviewOptions,
    depth: int,  # noqa: ARG001
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
    element: defusedxml.ElementTree.Element,
    args: ElementArgs,
    width: int,  # noqa: ARG001
    height: int,
    options: PreviewOptions,
    depth: int,  # noqa: ARG001
) -> None:
    """EditTextElement: 1 Text, 2 Text Size, 3 Width Scale %, 4 Colour, 5 Font, 6 Position,
    7 Input Type, 8 Maximum Characters (1000 means unlimited).
    """
    background = _background_style(element)
    if not background:
        background = "border-bottom: 2px solid rgba(100,116,139,0.75);"
    with ui.element("div").style(
        f"position: absolute; inset: 0; box-sizing: border-box; overflow: hidden;"
        f"{background}{_position_style(args)}",
    ):
        _text_content(args, 1, options, height)
    input_type = _enum(lookup_values["EditTextElement"], args.number(7))
    if input_type:
        _corner_badge(input_type)


def _draw_rect(
    element: defusedxml.ElementTree.Element,  # noqa: ARG001
    args: ElementArgs,
    width: int,  # noqa: ARG001
    height: int,  # noqa: ARG001
    options: PreviewOptions,  # noqa: ARG001
    depth: int,  # noqa: ARG001
) -> None:
    """RectElement -- see _rect_style for the arguments."""
    ui.element("div").style(f"position: absolute; inset: 0; box-sizing: border-box; {_rect_style(args)}")


def _draw_oval(
    element: defusedxml.ElementTree.Element,  # noqa: ARG001
    args: ElementArgs,
    width: int,  # noqa: ARG001
    height: int,  # noqa: ARG001
    options: PreviewOptions,  # noqa: ARG001
    depth: int,  # noqa: ARG001
) -> None:
    """OvalElement: the same as a Rect minus the corner arguments -- 1 Shader, 2 Colour,
    3 End Colour, 4 Border Width, 5 Border Colour.  Its shape is the ellipse of its box.
    """
    ui.element("div").style(
        f"position: absolute; inset: 0; box-sizing: border-box; border-radius: 50%; {_rect_style(args)}",
    )


def _draw_image(
    element: defusedxml.ElementTree.Element,  # noqa: ARG001
    args: ElementArgs,
    width: int,  # noqa: ARG001
    height: int,  # noqa: ARG001
    options: PreviewOptions,  # noqa: ARG001
    depth: int,  # noqa: ARG001
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
            _placeholder("image", "Tasker icon", value)
        elif kind == "file":
            _placeholder("insert_photo", "Image on device", value.rsplit("/", 1)[-1])
        else:
            _placeholder("hide_image", "No image set")


def _draw_check_box(
    element: defusedxml.ElementTree.Element,
    args: ElementArgs,
    width: int,
    height: int,
    options: PreviewOptions,  # noqa: ARG001
    depth: int,  # noqa: ARG001
) -> None:
    """CheckBoxElement: 1 Checked."""
    _draw_toggle_glyph(element, args, width, height, "check_box", "check_box_outline_blank")


def _draw_switch(
    element: defusedxml.ElementTree.Element,
    args: ElementArgs,
    width: int,
    height: int,
    options: PreviewOptions,  # noqa: ARG001
    depth: int,  # noqa: ARG001
) -> None:
    """SwitchElement: 1 Checked."""
    _draw_toggle_glyph(element, args, width, height, "toggle_on", "toggle_off")


def _draw_toggle_glyph(
    element: defusedxml.ElementTree.Element,
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
    element: defusedxml.ElementTree.Element,  # noqa: ARG001
    args: ElementArgs,
    width: int,  # noqa: ARG001
    height: int,
    options: PreviewOptions,  # noqa: ARG001
    depth: int,  # noqa: ARG001
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
                f"position: absolute; {thumb} width: 14px; height: 14px;"
                "border-radius: 50%; background: #2563eb;",
            )
    if height >= 26:
        ui.label(f"{minimum} – {maximum}  ({args.raw_number(4) or default})").style(
            "position: absolute; left: 2px; bottom: 1px; font: 10px/1.2 monospace; color: rgba(71,85,105,0.95);",
        )


def _draw_toggle(
    element: defusedxml.ElementTree.Element,  # noqa: ARG001
    args: ElementArgs,
    width: int,  # noqa: ARG001
    height: int,
    options: PreviewOptions,
    depth: int,  # noqa: ARG001
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
    element: defusedxml.ElementTree.Element,  # noqa: ARG001
    args: ElementArgs,
    width: int,
    height: int,
    options: PreviewOptions,
    depth: int,  # noqa: ARG001
) -> None:
    """WebElement: 1 Mode (URL / File / Direct), 2 Source.

    In "Direct" mode the Source *is* the page, so it is drawn -- inside the frame described
    at _WEB_SANDBOX, which renders markup without running it.  That distinction is the whole
    reason this can be drawn at all: a shared Tasker project arrives from a stranger, and
    what it holds must not get at this app's page or the network.  It draws no script, so a
    page that builds itself in JavaScript previews as whatever its markup alone amounts to.

    "URL" and "File" name a page on the network or on the Android device.  Neither is here
    and neither is fetched, so those keep the panel reporting the mode and the source.
    """
    source = args.text(2)
    if args.number(1) == _WEB_MODE_DIRECT and _is_inline_html(source):
        _draw_inline_html(source, width, height, options)
        _corner_badge("HTML")
        return
    mode = _enum(lookup_values["WebElement"], args.number(1)) or "?"
    summary = source.splitlines()[0][:80] if source else translate_string("(empty)")
    _placeholder("public", f"Web ({mode})", summary)


def _draw_video(
    element: defusedxml.ElementTree.Element,  # noqa: ARG001
    args: ElementArgs,
    width: int,  # noqa: ARG001
    height: int,  # noqa: ARG001
    options: PreviewOptions,  # noqa: ARG001
    depth: int,  # noqa: ARG001
) -> None:
    """VideoElement.  MapTasker has no argument table for this one (it is absent from
    actionc.action_codes), so nothing beyond arg0's name is claimed about it -- see this
    module's docstring on not guessing.
    """
    _placeholder("movie", "Video", args.text(1))


def _draw_doodle(
    element: defusedxml.ElementTree.Element,  # noqa: ARG001
    args: ElementArgs,
    width: int,  # noqa: ARG001
    height: int,  # noqa: ARG001
    options: PreviewOptions,  # noqa: ARG001
    depth: int,  # noqa: ARG001
) -> None:
    """DoodleElement: 1 Doodle (a bitmap cached on the device), 2 Alpha."""
    _, path = args.image(1)
    _placeholder("draw", "Doodle", path.rsplit("/", 1)[-1] if path else "")


def _draw_map(
    element: defusedxml.ElementTree.Element,  # noqa: ARG001
    args: ElementArgs,
    width: int,  # noqa: ARG001
    height: int,  # noqa: ARG001
    options: PreviewOptions,  # noqa: ARG001
    depth: int,  # noqa: ARG001
) -> None:
    """SceneElement -- Tasker's Map element, despite the tag: 1 Lat/Long, 2 Zoom,
    3 Show Traffic, 4 Show Satellite, 5 Show Roads.
    """
    _placeholder("map", "Map", args.text(1))


def _draw_picker(
    element: defusedxml.ElementTree.Element,
    args: ElementArgs,
    width: int,  # noqa: ARG001
    height: int,
    options: PreviewOptions,  # noqa: ARG001
    depth: int,  # noqa: ARG001
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
    element: defusedxml.ElementTree.Element,
    args: ElementArgs,
    width: int,
    height: int,
    options: PreviewOptions,
    depth: int,
) -> None:
    """ListElement: 1 Source, 2/3 Selection Mode, 5 Horizontal Space, 6 Vertical Space --
    and, at arg4, a whole nested <Scene> that is the layout of one row.
    """
    _draw_item_layout(element, args, "arg4", width, height, options, depth, translate_string("List"))


def _draw_spinner(
    element: defusedxml.ElementTree.Element,
    args: ElementArgs,
    width: int,
    height: int,
    options: PreviewOptions,
    depth: int,
) -> None:
    """SpinnerElement: 1 Source, 2 Variable, and the item layout <Scene> at arg3."""
    _draw_item_layout(element, args, "arg3", width, height, options, depth, translate_string("Spinner"))


def _draw_item_layout(
    element: defusedxml.ElementTree.Element,
    args: ElementArgs,
    slot: str,
    width: int,
    height: int,
    options: PreviewOptions,
    depth: int,
    kind: str,
) -> None:
    """Draw a List's or Spinner's row template: the nested <Scene sr="val"> Tasker stores
    inside the element, laid out on its own little canvas and scaled to this element's width.

    One row, not a repeated list, because the rows come from a Tasker variable at runtime --
    there is no list here to draw.  What the preview can honestly show is the shape of a row,
    which is what the nested Scene is.  Recursion is capped at _MAX_ITEM_DEPTH; a template
    that itself holds a List draws that inner one as a labelled box.
    """
    nested = element.find(f"Scene[@sr='{slot}']/Scene[@sr='val']")
    source = _enum(lookup_values["ListElement1"], args.number(1))
    variable = args.text(2)
    caption = f"{kind}: {source}{f' — {variable}' if variable else ''}"

    if nested is None or depth >= _MAX_ITEM_DEPTH:
        _placeholder("list", caption)
        return

    item = scene_dimensions(nested, landscape=False)
    if item is None:
        _placeholder("list", caption)
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
                _draw_element(child, options, depth + 1)
        if height > item_height * scale + 20:
            ui.label("⋮").style(
                "position: absolute; left: 50%; bottom: 2px; transform: translateX(-50%);"
                "font: 14px/1 monospace; color: rgba(100,116,139,0.9);",
            )


def _draw_unknown(
    element: defusedxml.ElementTree.Element,
    args: ElementArgs,  # noqa: ARG001
    width: int,  # noqa: ARG001
    height: int,  # noqa: ARG001
    options: PreviewOptions,  # noqa: ARG001
    depth: int,  # noqa: ARG001
) -> None:
    """An element type this app has no argument table for -- a newer Tasker's, most likely.

    Drawn as a labelled box at its true geometry rather than skipped: where it is and how big
    it is are known from <geom> and are worth showing, and the alternative is a Scene that
    silently previews with a hole in it.
    """
    _placeholder("widgets", element.tag.replace("Element", ""), element_name(element))


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


# ======================================================================================
# VERSION 2
#
# A V2 layout is a tree of components that lay themselves out -- there are no coordinates to
# honour, so this half is a translation of Compose's layout model onto CSS flexbox rather
# than the placement exercise the Legacy half is.  The translation is close to exact for the
# things Scenes actually use: a Column is a flex column, its horizontalAlignment is
# align-items, its verticalArrangement is justify-content, and SpaceBetween/SpaceAround/
# SpaceEvenly are the CSS keywords of the same names.
#
# Sizes are in dp and drawn 1dp = 1px inside a frame of the chosen device size, then scaled
# to fit by the same transform the Legacy canvas uses.  There is no density control here and
# should not be: dp is already the density-independent unit, so 1:1 is the honest mapping and
# the only open question is how big a screen the layout is being laid out in -- which is what
# the frame size is for.
# ======================================================================================

# The screens the preview offers to lay a layout out in, in dp.  A V2 Scene has no size of
# its own, so this is the one thing the user has to be able to change to judge a layout:
# the same tree wraps differently at 360dp and at 800dp, and that difference is the whole
# reason FlowRow and showWhen (%sv2_render_width) exist.
V2_SCREENS: tuple[tuple[str, int, int], ...] = (
    ("Phone", 412, 892),
    ("Small phone", 360, 780),
    ("Large phone", 448, 998),
    ("Tablet", 800, 1280),
)
V2_DEFAULT_SCREEN = V2_SCREENS[0][0]

# Material 3's baseline light scheme -- what a colour named by role ("outline",
# "onSecondaryContainer") resolves to here.
#
# It is a real palette rather than an invented one, but it is NOT necessarily the user's:
# Android resolves these against the device's theme, and under Material You that theme is
# generated from the wallpaper, so the same Scene is a different set of colours on every
# phone.  Which is the argument for using the baseline: it is the documented default, it is
# stated in the caption, and no other choice available here would be any more correct.
V2_MATERIAL_PALETTE: dict[str, str] = {
    "primary": "#6750A4",
    "onPrimary": "#FFFFFF",
    "primaryContainer": "#EADDFF",
    "onPrimaryContainer": "#21005D",
    "secondary": "#625B71",
    "onSecondary": "#FFFFFF",
    "secondaryContainer": "#E8DEF8",
    "onSecondaryContainer": "#1D192B",
    "tertiary": "#7D5260",
    "onTertiary": "#FFFFFF",
    "tertiaryContainer": "#FFD8E4",
    "onTertiaryContainer": "#31111D",
    "error": "#B3261E",
    "onError": "#FFFFFF",
    "errorContainer": "#F9DEDC",
    "onErrorContainer": "#410E0B",
    "background": "#FFFBFE",
    "onBackground": "#1C1B1F",
    "surface": "#FFFBFE",
    "onSurface": "#1C1B1F",
    "surfaceVariant": "#E7E0EC",
    "onSurfaceVariant": "#49454F",
    "surfaceTint": "#6750A4",
    "inverseSurface": "#313033",
    "inverseOnSurface": "#F4EFF4",
    "inversePrimary": "#D0BCFF",
    "outline": "#79747E",
    "outlineVariant": "#CAC4D0",
    "scrim": "#000000",
    # The rest of Material 3's roles, at the same baseline.  The "fixed" family is the one
    # that keeps its colour when the rest of the scheme flips between light and dark -- which
    # is why onPrimaryFixed and onPrimaryContainer are the same swatch here and stop being the
    # same one on a dark device -- and the surfaceContainer family is the elevation ladder
    # that replaced Material 2's shadows.  Both are offered by Tasker's own colour picker, so
    # a Scene can name any of them.
    "primaryFixed": "#EADDFF",
    "onPrimaryFixed": "#21005D",
    "primaryFixedDim": "#D0BCFF",
    "onPrimaryFixedVariant": "#4F378B",
    "secondaryFixed": "#E8DEF8",
    "onSecondaryFixed": "#1D192B",
    "secondaryFixedDim": "#CCC2DC",
    "onSecondaryFixedVariant": "#4A4458",
    "tertiaryFixed": "#FFD8E4",
    "onTertiaryFixed": "#31111D",
    "tertiaryFixedDim": "#EFB8C8",
    "onTertiaryFixedVariant": "#633B48",
    "surfaceDim": "#DED8E1",
    "surfaceBright": "#FEF7FF",
    "surfaceContainerLowest": "#FFFFFF",
    "surfaceContainerLow": "#F7F2FA",
    "surfaceContainer": "#F3EDF7",
    "surfaceContainerHigh": "#ECE6F0",
    "surfaceContainerHighest": "#E6E0E9",
}

# Compose's arrangements and alignments, in the spellings sceneedit's schema offers, mapped
# onto the flexbox keywords that mean the same thing.
_V2_ARRANGEMENT: dict[str, str] = {
    "Start": "flex-start",
    "Center": "center",
    "End": "flex-end",
    "SpaceBetween": "space-between",
    "SpaceAround": "space-around",
    "SpaceEvenly": "space-evenly",
    "Top": "flex-start",
    "Bottom": "flex-end",
}
_V2_ALIGNMENT: dict[str, str] = {
    "Start": "flex-start",
    "Center": "center",
    "End": "flex-end",
    "Top": "flex-start",
    "Bottom": "flex-end",
}

# A component's default text size in dp when it does not say.  Material's body default.
_V2_DEFAULT_TEXT_SIZE = 16
# How deep to follow the tree.  Nothing in a real Scene comes close; this is a stop against a
# layout that somehow refers to itself, not a limit anyone should meet.
_V2_MAX_DEPTH = 40

# Icons arrive as "icon:Close" / "icon:ArrowBack" -- Material's own icon names, which is what
# the browser's Material font is keyed by once they are snake_cased.  So these draw as the
# real icon rather than as a placeholder, unlike a Legacy <Img>.
_V2_ICON_PREFIX = "icon:"
_V2_CAMEL_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")

# The second way a Scene names a glyph: Material Symbols, Google's newer set.  Quasar reaches
# it by prefixing the name -- sym_o_ for the Outlined face, which is the one Tasker's own
# picker shows -- and NiceGUI 3.15 ships all three Symbols faces with itself (see its
# static/fonts.css), so drawing one fetches nothing from the network.
#
# The names in this set are already snake_case, and the ";weight:600;opsz:24" tail on them
# says how to draw the glyph rather than which glyph it is (maputil2.tasker_icon_name).
_V2_SYMBOL_PREFIX = "symbol:"
_V2_QUASAR_SYMBOL_PREFIX = "sym_o_"

# The third way: an installed app's own icon, served by Tasker's icon provider on the device.
# "content://net.dinglisch.android.taskerm.iconprovider//app/com.android.vending" is a
# reference to something on the phone -- the icon belongs to the app, not to the backup -- so
# there is no glyph here to draw and the package name is what can honestly be shown for it.
_V2_APP_ICON_SCHEME = "content://"
_V2_APP_ICON_MARKER = "iconprovider"


def v2_colour(raw: object, fallback: str = "") -> Colour:
    """A V2 colour value: a Material role name, a plain hex colour, or a %variable.

    Not the same parse as the Legacy tasker_colour, and the difference is the point.  A V2
    layout writes ordinary #RRGGBB ("#64B5F6", "#f43356") and Material role names ("outline",
    "onSecondaryContainer"); a Legacy Scene writes #AARRGGBB with the alpha FIRST.  Handing a
    Legacy colour to this function would change both its hue and its transparency, so the two
    parsers are kept apart rather than merged into one clever one.

    THE EIGHT-DIGIT CASE IS AN INFERENCE, and is flagged as one because no V2 layout in any
    sample here carries a colour of that length -- there is no evidence to read.  It is
    treated as Tasker's own #AARRGGBB rather than as CSS's #RRGGBBAA, because AARRGGBB is the
    only colour convention this app has ever observed Tasker writing in a Scene of either
    kind, and the two orders are not a near miss: reading "#FF64B5F6" the CSS way turns a
    blue into a red.  If a real V2 Scene ever turns up carrying one, this is the line to check
    it against.
    """
    value = str(raw or "").strip()
    if not value:
        return Colour(fallback or "transparent", known=False)
    if value.startswith("%"):
        return Colour(fallback or "transparent", variable=value, known=False)
    if value in V2_MATERIAL_PALETTE:
        return Colour(V2_MATERIAL_PALETTE[value])
    if value.startswith("#") and len(value) == 9:
        return tasker_colour(value, fallback or "transparent")
    if value.startswith("#") and len(value) in (4, 7):
        return Colour(value)
    return Colour(fallback or "transparent", known=False)


def v2_swatch_colour(raw: object) -> str:
    """The CSS this V2 colour value actually draws as, for showing a swatch of it -- a
    Material role name resolved through the palette, a #hex as itself, an HTML colour name as
    itself.

    "" for anything that names no colour this app can resolve: an empty property, a
    %variable, a spelling from a newer Tasker.  The caller decides what to show for those --
    a blank swatch says "nothing to show you" where a made-up colour would be a claim.
    """
    value = str(raw or "").strip()
    if not value or value.startswith("%"):
        return ""
    colour = v2_colour(value, fallback="")
    if colour.known:
        return colour.css
    return value.lower() if is_html_colour(value) else ""


def v2_icon(raw: object) -> str:
    """The name Quasar draws this icon by: "icon:ArrowBack" -> "arrow_back",
    "symbol:cloud_upload;opsz:24" -> "sym_o_cloud_upload".

    Both sets are drawn from fonts NiceGUI ships, so neither goes to the network.  The two
    differ in how the name is spelled as well as which font it is in: Material Icons names are
    camel case in a Scene and snake case in the font, while Symbols names are snake case
    already -- which is why only the first is converted.

    "" for anything that is not a font glyph at all: an app icon from the device's own icon
    provider (see _v2_app_icon), a URL, a %variable, an empty property.
    """
    value = str(raw or "").strip()
    if value.startswith(_V2_SYMBOL_PREFIX):
        name = tasker_icon_name(value)
        return f"{_V2_QUASAR_SYMBOL_PREFIX}{name}" if name else ""
    if value.startswith(_V2_ICON_PREFIX):
        name = tasker_icon_name(value)
        return _V2_CAMEL_BOUNDARY.sub("_", name).lower() if name else ""
    return ""


def _v2_app_icon(raw: object) -> str:
    """The package whose own icon this reference names -- "com.android.vending" out of a
    "content://...iconprovider//app/com.android.vending".  "" for anything else.

    The icon itself is installed with the app on the phone and is not in the backup, so this
    is the most that can be said about it here.  The callers draw a stand-in glyph and name
    the package rather than leaving the component empty, which is what a preview that cannot
    show something owes the person reading it.
    """
    value = str(raw or "").strip()
    if not value.startswith(_V2_APP_ICON_SCHEME) or _V2_APP_ICON_MARKER not in value:
        return ""
    return tasker_icon_name(value)


def v2_layout_summary(layout: dict) -> list[tuple[str, str]]:
    """The layout's own settings, for the caption under the frame -- the V2 counterpart of
    scene_properties.  defaultDisplayMode is the one that changes what is drawn (see
    draw_v2_layout); the rest are reported because they describe the Scene and appear
    nowhere else in the picture.
    """
    rows = [
        ("Name", str(layout.get("name", ""))),
        ("Display mode", str(layout.get("defaultDisplayMode", ""))),
    ]
    handlers = _v2_handler_lines(layout)
    if handlers:
        rows.append(("Layout events", "; ".join(handlers)))
    return [(label, value) for label, value in rows if value]


# ------------------------------------------------------------------
# Component identity, for the drag that reorders them
# ------------------------------------------------------------------
# Where every node drawn in this pass sits in the tree: id(node) -> (path, siblings in its
# slot).  Built once per draw by _v2_index_paths and read by _v2_draw_node, which is the one
# funnel every component goes through.
#
# A LOOKUP RATHER THAN A PARAMETER, and deliberately.  The alternative is threading a path
# through _v2_draw_node into all thirty-odd drawers and back out of each of them to their
# children -- every drawer changed, every one of them able to compute the wrong path, to
# deliver something the drawers themselves have no use for.  The tree is walked once here
# instead, by the same rule _v2_slots walks by, so the paths mean to sceneedit exactly what
# its own v2_flatten would have meant.
#
# Keyed by id() because these dicts are the layout's own and stay alive throughout the draw;
# see _v2_alias for the two drawers that hand _v2_draw_node something else.
_V2_PATHS: dict[int, tuple[tuple, int]] = {}

# The two classes the hull is measured with: every component drawn carries the first, and the
# box drawn behind them carries the second.  Stated here rather than in guiwins because this
# is the module that puts them in the DOM; the script that reads them is
# guiwins._emit_v2_hull, and the two change together.
V2_COMPONENT_CLASS = "mt-v2-comp"
V2_HULL_CLASS = "mt-v2-hull"

# How far the hull is drawn outside the content it encloses, in canvas pixels.  Not
# decoration: the elements it encloses paint their own opaque backgrounds (a dialog's card,
# a filled Button), and a box drawn *behind* them and exactly the size of them would be a box
# nobody can see.  The rim is what is left visible, and it is still clamped to the screen.
V2_HULL_PADDING = 6
# The editing surface for this draw, or None when it is the read-only Preview.  Module-level
# for the same reason as _V2_PATHS: it is the drawer funnel that needs it, not the drawers.
_V2_EDITING: V2Editing | None = None


def v2_encode_path(path: tuple) -> str:
    """A path as one DOM-safe string -- ("content", 0, "children", 2) as
    "content|0|children|2", the empty tuple as "".

    The browser needs to compare paths (is this component a sibling of that one? is it inside
    it?) and a string it can take a prefix of is the whole of what that takes: siblings share
    everything up to the last separator, and a descendant's path starts with its ancestor's
    plus one.  See _emit_v2_dragging, which does exactly those two tests and nothing else.
    """
    return "|".join(str(part) for part in path)


def v2_decode_path(encoded: str) -> tuple:
    """The tuple a v2_encode_path string names.  Index segments come back as ints, slot keys
    as strings, which is what sceneedit.v2_node_at indexes with.

    Whatever the browser sends is a path *shape*, never a promise that it still resolves --
    the caller looks it up in the tree, which is what decides whether it means anything.
    """
    if not encoded:
        return ()
    return tuple(int(part) if part.lstrip("-").isdigit() else part for part in encoded.split("|"))


def _v2_index_paths(root: dict) -> None:
    """Record where every component in this layout sits, before a line of it is drawn."""
    _V2_PATHS.clear()

    def walk(node: dict, path: tuple, siblings: int) -> None:
        _V2_PATHS[id(node)] = (path, siblings)
        for slot, children in _v2_slots(node):
            for index, child in enumerate(children):
                if isinstance(child, dict):
                    walk(child, (*path, slot, index), len(children))

    walk(root, (), 0)


def _v2_alias(drawn: dict, original: dict) -> dict:
    """Give a stand-in dict the identity of the component it stands in for.

    Two drawers do not draw the component the tree holds: a NavigationBar and a
    SegmentedButtonRow decide which of their items is selected, and say so by drawing a copy
    with one key overridden rather than by writing into the Scene.  A copy is a different
    id(), so without this its items would be the only components on the canvas with no path
    -- unselectable and undraggable, for a reason invisible from the outside.
    """
    identity = _V2_PATHS.get(id(original))
    if identity is not None:
        _V2_PATHS[id(drawn)] = identity
    return drawn


def draw_v2_layout(
    layout: dict,
    width: int,
    height: int,
    options: PreviewOptions,
    editing: V2Editing | None = None,
) -> None:
    """Draw a Version 2 layout into a device-sized frame, into whatever container is open.

    The frame is the point.  A V2 layout has no size of its own -- it fills whatever it is
    given -- so previewing one means choosing a screen to lay it out in, and saying which.
    Everything inside is ordinary flexbox at 1dp = 1px; the frame as a whole is then scaled
    to fit by the caller, exactly as the Legacy canvas is.

    A Scene whose defaultDisplayMode is a Dialog is drawn as one: on a scrim, centred, sized
    to its content rather than to the screen.  That is not decoration -- it is the difference
    between a layout that fills a phone and one that floats in the middle of it, and a
    preview that showed the same picture for both would be wrong about the more important
    half of what the Scene is.

    `editing` makes the components the browser can pick up and drag -- see V2Editing.  The
    picture drawn is the same either way: what it adds is a path on each component and an
    outline round the selected run, never a different layout.

    Behind all of it goes the hull -- the box round everything the layout actually occupies
    within the screen.  It is drawn empty here and sized in the browser, for the reason
    _v2_hull gives.
    """
    global _V2_EDITING  # noqa: PLW0603 -- see _V2_PATHS on why this is not a parameter.
    root = layout.get("root")
    is_dialog = "dialog" in str(layout.get("defaultDisplayMode", "")).lower()
    _V2_EDITING = editing
    if editing is not None and isinstance(root, dict):
        _v2_index_paths(root)

    frame = ui.element("div").classes("mt-scene-canvas").style(
        f"position: relative; width: {width}px; height: {height}px; overflow: hidden;"
        f"transform-origin: top left; box-sizing: border-box;"
        f"background: {V2_MATERIAL_PALETTE['background']}; color: {V2_MATERIAL_PALETTE['onBackground']};"
        "font-family: Roboto, system-ui, sans-serif;",
    )
    if editing is not None:
        # The selected run, for the drag handlers to read off the canvas: where it starts and
        # how long it is.  The same two attributes the designer's tree pane carries, and put
        # here for the same reason -- see guiwins._v2_selection_props.
        frame.props(
            f'data-mt-v2-sel="{v2_encode_path(editing.selected[0] if editing.selected else ())}" '
            f'data-mt-v2-count="{max(1, len(editing.selected))}"',
        )
    with frame:
        if not isinstance(root, dict):
            _placeholder("layers_clear", "This layout has no root component")
            return
        _v2_hull()
        if is_dialog:
            with ui.element("div").style(
                "position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;"
                "background: rgba(0,0,0,0.32); padding: 24px; box-sizing: border-box;",
            ), ui.element("div").style(
                f"max-width: 100%; max-height: 100%; overflow: hidden; border-radius: 28px;"
                f"background: {V2_MATERIAL_PALETTE['surface']}; box-shadow: 0 8px 24px rgba(0,0,0,0.25);",
            ):
                # No fill: a dialog is the size of what is in it, which is the whole
                # difference between it and the full-screen case below.
                _v2_draw_node(root, options, 0)
        else:
            with ui.element("div").style(
                "position: absolute; inset: 0; display: flex; flex-direction: column; overflow: hidden;",
            ):
                _v2_draw_node(root, options, 0, fill=True)


def _v2_hull() -> None:
    """The box behind the layout: everything the Scene's components occupy within the screen,
    enclosed in one rectangle.

    A V2 layout has no coordinates of its own -- it is flexbox, and where a component lands
    is decided by the browser laying its siblings out -- so unlike the Legacy canvas, where
    every element's box is in the XML, there is no extent to compute here.  This element is
    therefore drawn empty and positioned by guiwins._emit_v2_hull once the layout has been
    laid out, which is the only place the numbers exist.

    Hidden until it has been measured, so a render whose script has not run yet shows no box
    rather than a box of the wrong size; drawn before the layout so it is painted underneath
    it, which is what makes it a background rather than an overlay.

    SOLID, where every other outline on this canvas is dashed.  A component's Bounds outline
    and a Show when's amber one are both dashed hairlines, and a fourth dashed blue rectangle
    would read as one more of those instead of as the thing they all sit inside.  The tint,
    the 2px edge and the glow beneath it are what carry the box at a glance -- it is behind
    opaque components, so the rim V2_HULL_PADDING leaves is most of what can be seen of it.
    """
    ui.element("div").classes(V2_HULL_CLASS).style(
        "position: absolute; display: none; z-index: 0; pointer-events: none;"
        "box-sizing: border-box; border-radius: 6px;"
        "background: rgba(37,99,235,0.13); border: 2px solid rgba(37,99,235,0.7);"
        "box-shadow: 0 2px 12px rgba(37,99,235,0.35);",
    )


def v2_component_count(layout: dict) -> int:
    """How many components the tree holds -- the V2 counterpart of len(paint_order)."""
    def count(node: object) -> int:
        if not isinstance(node, dict):
            return 0
        return 1 + sum(count(child) for _, children in _v2_slots(node) for child in children)

    return count(layout.get("root"))


def _v2_slots(node: dict) -> list[tuple[str, list]]:
    """The (slot name, children) pairs under this node.

    Deliberately the same rule sceneedit.v2_child_slots uses -- any list of component-shaped
    dicts is a slot -- rather than a table of slot names, so a container from a newer Tasker
    still nests here instead of being flattened into a leaf.  Imported rather than
    re-implemented would be better still, but sceneedit imports the whole GUI-editing stack;
    this is the one rule worth repeating to keep the preview importable on its own.
    """
    slots = []
    for key, value in node.items():
        if key in ("modifiers", "eventHandlers") or not isinstance(value, list):
            continue
        if any(isinstance(item, dict) and "type" in item for item in value):
            slots.append((key, value))
    return slots


def _v2_children(node: dict, *slots: str) -> list[dict]:
    """The child components in the named slots, in order.  Missing slots contribute
    nothing, which is what makes a Scaffold with no bottomBar draw without a gap.
    """
    found: list[dict] = []
    for slot in slots:
        value = node.get(slot)
        if isinstance(value, list):
            found.extend(child for child in value if isinstance(child, dict))
    return found


def _v2_all_children(node: dict) -> list[dict]:
    """Every child, whatever slot it is in -- for the generic containers and the fallback."""
    return [child for _, children in _v2_slots(node) for child in children if isinstance(child, dict)]


# ------------------------------------------------------------------
# Modifiers
# ------------------------------------------------------------------
def _v2_modifier_style(node: dict) -> str:
    """The CSS a component's modifier chain amounts to.

    Compose applies modifiers in order and each wraps the last, so strictly they are nested
    boxes; this merges them into one box's style instead, later modifiers overriding earlier
    ones for the same property.  The two agree for everything real Scenes do -- padding
    inside a border, a background behind both -- and disagree only for orders CSS has no box
    for (a padding outside a border, two paddings in a row).  That trade buys a component
    being one element rather than a stack of six, which is what keeps flex alignment,
    scrolling and the bounds outline all landing on the thing the user selected.

    Every modifier's keys are read defensively.  Size is the reason: sceneedit's schema lists
    width/height, and the Scenes in this repo carry "all".  Both work here.

    The transforming modifiers (Offset, Rotate, Scale) are gathered rather than concatenated,
    for the reason given at _V2_MODIFIER_TRANSFORM, and land after everything else -- a
    transform is applied to the box the rest of the chain has already decided on.
    """
    modifiers = node.get("modifiers")
    if not isinstance(modifiers, list):
        return ""

    style = ""
    transforms = []
    for modifier in modifiers:
        if not isinstance(modifier, dict):
            continue
        modifier_type = str(modifier.get("type", ""))
        style += _V2_MODIFIER_CSS.get(modifier_type, lambda _m: "")(modifier)
        transform = _V2_MODIFIER_TRANSFORM.get(modifier_type, lambda _m: "")(modifier)
        if transform:
            transforms.append(transform)
    if transforms:
        style += f"transform: {' '.join(transforms)};"
    return style


def _v2_number(source: dict, *keys: str) -> str:
    """The first of these keys the dict actually carries, as a CSS px length.  "" when none
    of them are there or the value is a %variable, which a length cannot be.

    Used for both modifiers and components -- a Padding's "all" and a Spacer's "height" are
    the same kind of value stored the same way (as a string, see sceneedit._coerce_like).
    """
    for key in keys:
        value = str(source.get(key, "")).strip()
        if value and not value.startswith("%"):
            try:
                return f"{float(value):g}px"
            except ValueError:
                continue
    return ""


def _v2_padding(modifier: dict) -> str:
    """Padding: all / horizontal / vertical / start / end / top / bottom, applied from the
    most general to the most specific so a {horizontal, bottom} pair composes the way Compose
    composes it.
    """
    style = ""
    for keys, css in (
        (("all",), "padding"),
        (("horizontal",), "padding-left"),
        (("horizontal",), "padding-right"),
        (("vertical",), "padding-top"),
        (("vertical",), "padding-bottom"),
        (("start",), "padding-left"),
        (("end",), "padding-right"),
        (("top",), "padding-top"),
        (("bottom",), "padding-bottom"),
    ):
        length = _v2_number(modifier, *keys)
        if length:
            style += f"{css}: {length};"
    return style


def _v2_shape(modifier: dict) -> str:
    """The corner rounding a Clip or a Border asks for: a Circle is a circle whatever its
    radius says, a Rounded is its radius, and a shape with neither is square.
    """
    if str(modifier.get("shape", "")) == "Circle":
        return "border-radius: 50%;"
    radius = _v2_number(modifier, "radius")
    return f"border-radius: {radius};" if radius else ""


def _v2_border(modifier: dict) -> str:
    colour = v2_colour(modifier.get("color"), fallback=V2_MATERIAL_PALETTE["outline"])
    width = _v2_number(modifier, "width") or "1px"
    return f"border: {width} solid {colour.css}; box-sizing: border-box;{_v2_shape(modifier)}"


def _v2_background(modifier: dict) -> str:
    colour = v2_colour(modifier.get("color"))
    if colour.is_variable:
        return f"background: {VARIABLE_FILL};"
    return f"background: {colour.css};" if colour.known else ""


def _v2_size(modifier: dict) -> str:
    """Size: an explicit width and height.  "all" is what the Scenes here carry and means
    both; width/height are what the editor's schema offers.  Either is accepted.
    """
    both = _v2_number(modifier, "all")
    if both:
        return f"width: {both}; height: {both}; flex: none;"
    style = ""
    width = _v2_number(modifier, "width")
    height = _v2_number(modifier, "height")
    if width:
        style += f"width: {width};"
    if height:
        style += f"height: {height};"
    return f"{style}flex: none;" if style else ""


def _v2_size_in(modifier: dict) -> str:
    style = ""
    max_width = _v2_number(modifier, "maxWidth")
    max_height = _v2_number(modifier, "maxHeight")
    if max_width:
        style += f"max-width: {max_width};"
    if max_height:
        style += f"max-height: {max_height};"
    return style


def _v2_alpha(modifier: dict) -> str:
    value = str(modifier.get("value", "")).strip()
    try:
        return f"opacity: {max(0.0, min(1.0, float(value)))};"
    except ValueError:
        return ""


# The weights a Weight modifier is set from (sceneedit.V2_FONT_WEIGHTS), as the numbers CSS
# knows them by.  Keyed without spaces or case so "ExtraLight", "Extra Light" and "extra
# light" all arrive at the same weight -- the same looseness sceneedit.v2_state_of reads them
# with, and for the same reason: which of the two spellings Tasker writes is not in evidence.
_V2_FONT_WEIGHT_CSS: dict[str, int] = {
    "thin": 100,
    "extralight": 200,
    "light": 300,
    "normal": 400,
    "medium": 500,
    "semibold": 600,
    "bold": 700,
    "extrabold": 800,
    "black": 900,
}

# What a Blur is drawn as when it says nothing about how much.  No Blur in any sample carries
# a radius and Tasker's name for one is not in evidence (see sceneedit's schema note), so this
# is a stand-in: enough to show that the component is blurred, not a claim about how much.
_V2_DEFAULT_BLUR = "4px"


def _v2_weight(modifier: dict) -> str:
    """Weight: how heavy the text is drawn.

    A named weight off Compose's scale, or a plain 100-900 that CSS would take as one.  A
    %variable, or a leftover number from when this modifier was read as a layout weight, is
    not a font weight and draws nothing -- the modifier is still named in the tooltip.
    """
    amount = str(modifier.get("amount", "")).strip()
    named = _V2_FONT_WEIGHT_CSS.get("".join(amount.split()).lower())
    if named:
        return f"font-weight: {named};"
    try:
        numeric = int(float(amount))
    except ValueError:
        return ""
    return f"font-weight: {numeric};" if 100 <= numeric <= 900 else ""  # noqa: PLR2004


def _v2_fraction(modifier: dict) -> str:
    """How much of the available space a Fill* modifier takes, as a CSS percentage.  Absent
    means all of it, which is how most of the samples' Fills are written.
    """
    value = str(modifier.get("fraction", "")).strip()
    try:
        return f"{max(0.0, min(1.0, float(value))) * 100:g}%"
    except ValueError:
        return "100%"


def _v2_shadow(modifier: dict) -> str:
    """Shadow: elevation as the distance the component is lifted off what is behind it.

    Compose states an elevation in dp and works the shadow out from it; CSS wants the offset
    and the blur, so the one number becomes both -- dropped half its elevation, blurred by the
    whole of it, which is the shape of Material's own elevation overlays.  The shape is
    carried too, so a shadow under a rounded card is rounded rather than square.
    """
    elevation = _v2_number(modifier, "elevation")
    if not elevation:
        return _v2_shape(modifier)
    depth = float(elevation.removesuffix("px"))
    return f"box-shadow: 0 {depth / 2:g}px {depth:g}px rgba(0,0,0,0.28);{_v2_shape(modifier)}"


def _v2_offset(modifier: dict) -> str:
    """Offset: x and y, either of which can be negative and either of which can be absent."""
    x = _v2_number(modifier, "x") or "0px"
    y = _v2_number(modifier, "y") or "0px"
    return "" if x == "0px" and y == "0px" else f"translate({x}, {y})"


def _v2_rotate(modifier: dict) -> str:
    degrees = str(modifier.get("degrees", "")).strip()
    try:
        return f"rotate({float(degrees):g}deg)"
    except ValueError:
        return ""


def _v2_scale(modifier: dict) -> str:
    amount = str(modifier.get("all", "")).strip()
    try:
        return f"scale({float(amount):g})"
    except ValueError:
        return ""


# type -> the CSS it contributes.  A modifier absent from here and from
# _V2_MODIFIER_TRANSFORM contributes nothing visually and is reported in the component's
# tooltip instead (see _v2_tooltip): WindowDrag is behaviour rather than appearance -- a
# picture cannot show that a window can be dragged -- and an unrecognised one is not going to
# be invented.
_V2_MODIFIER_CSS: dict[str, object] = {
    "FillWidth": lambda m: f"width: {_v2_fraction(m)};",
    "FillHeight": lambda m: f"height: {_v2_fraction(m)};",
    "FillSize": lambda m: f"width: {_v2_fraction(m)}; height: {_v2_fraction(m)};",
    "Size": _v2_size,
    "SizeIn": _v2_size_in,
    "Padding": _v2_padding,
    "Clip": lambda m: f"overflow: hidden;{_v2_shape(m)}",
    "Border": _v2_border,
    "Shadow": _v2_shadow,
    "Background": _v2_background,
    "Align": lambda m: f"align-self: {_V2_ALIGNMENT.get(str(m.get('alignment', '')), 'auto')};",
    "Weight": _v2_weight,
    "AspectRatio": lambda m: f"aspect-ratio: {m.get('ratio', '1')};",
    "Alpha": _v2_alpha,
    "Blur": lambda m: f"filter: blur({_v2_number(m, 'radius', 'all', 'value') or _V2_DEFAULT_BLUR});",
    "VerticalScroll": lambda _m: "overflow-y: auto;",
    "HorizontalScroll": lambda _m: "overflow-x: auto;",
    "Clickable": lambda _m: "cursor: pointer;",
}

# The three that are all the same CSS property.  Kept apart from the table above because
# `transform` takes a *list* of functions and the styles here are concatenated: written as
# ordinary declarations, a component carrying both a Rotate and a Scale would keep only
# whichever came last.  Gathered instead, and emitted as one transform in modifier order.
_V2_MODIFIER_TRANSFORM: dict[str, object] = {
    "Offset": _v2_offset,
    "Rotate": _v2_rotate,
    "Scale": _v2_scale,
}


def _v2_modifier_drawn(modifier_type: str) -> bool:
    """Whether the preview has anything to draw for this modifier -- what the tooltip's
    "(not drawn)" note is the answer to.
    """
    return modifier_type in _V2_MODIFIER_CSS or modifier_type in _V2_MODIFIER_TRANSFORM


# ------------------------------------------------------------------
# Event handlers and variable bindings
# ------------------------------------------------------------------
def _v2_handler_lines(node: dict) -> list[str]:
    """"click, hold -> SetVariable sd_button = Close; DismissLayout" for each handler.

    A V2 component's behaviour is entirely in here -- there is no clickTask child the way a
    Legacy element has -- so a preview that showed only the layout would be hiding the half
    of the Scene that does anything.
    """
    handlers = (node.get("eventHandlers") or {}).get("handlers")
    if not isinstance(handlers, list):
        return []

    lines = []
    for handler in handlers:
        if not isinstance(handler, dict):
            continue
        events = ", ".join(
            str(event.get("type", "?")) + (f" [{event['variableName']}]" if event.get("variableName") else "")
            for event in handler.get("events") or []
            if isinstance(event, dict)
        )
        actions = "; ".join(_v2_action_text(action) for action in handler.get("actions") or [] if isinstance(action, dict))
        if events or actions:
            lines.append(f"{events or '?'} → {actions or '(nothing)'}")
    return lines


def _v2_action_text(action: dict) -> str:
    """One action, in the shape sceneedit.V2_ACTION_SCHEMA says it has.  An action type this
    app has not seen is named anyway, with whatever scalar properties it carries -- better a
    slightly clumsy "DoSomething(x=1)" than silently dropping what the button does.
    """
    kind = str(action.get("type", "?"))
    if kind == "SetVariable":
        return f"SetVariable {action.get('variable', '?')} = {action.get('value', '')}"
    if kind == "ToggleVariable":
        return f"ToggleVariable {action.get('variable', '?')}"
    if kind == "RunTask":
        return f"RunTask '{action.get('task', '?')}'"
    if kind == "DismissLayout":
        result = action.get("result")
        return f"DismissLayout{f' → {result}' if result else ''}"
    if kind == "OutputToVariable":
        bindings = action.get("bindings")
        if isinstance(bindings, dict):
            pairs = ", ".join(f"{key}→{', '.join(str(v) for v in value)}" for key, value in bindings.items())
            return f"OutputToVariable {pairs}"
        return "OutputToVariable"
    extras = ", ".join(f"{key}={value}" for key, value in action.items() if key != "type" and not isinstance(value, (dict, list)))
    return f"{kind}({extras})" if extras else kind


def _v2_binding_lines(node: dict) -> list[str]:
    """The Tasker variables this component writes its value into.

    Held under a per-type state key -- textState for a TextInput, sliderValueState for a
    Slider (sceneedit.V2_STATE_BY_TYPE) -- but found here by shape rather than by type, so a
    component from a newer Tasker with its own state key still reports its bindings.
    """
    lines = []
    for key, value in node.items():
        if not key.endswith("State") or not isinstance(value, dict):
            continue
        bindings = value.get("outputVariableBindings")
        if not isinstance(bindings, dict):
            continue
        for slot, variables in bindings.items():
            names = ", ".join(str(variable) for variable in variables) if isinstance(variables, list) else str(variables)
            if names:
                lines.append(f"{slot} → {names}")
    return lines


# ------------------------------------------------------------------
# The recursive draw
# ------------------------------------------------------------------
def _v2_draw_node(node: dict, options: PreviewOptions, depth: int, *, fill: bool = False) -> None:
    """Draw one component and, through its drawer, everything under it.

    `fill` is for the components whose job is to occupy what they are given rather than to
    be the size of their contents -- the root of a full-screen layout, and whatever sits in a
    Scaffold's content slot.  Without it a Column asking for verticalArrangement: Center has
    nothing to centre within, because a flex item is only as tall as its children unless it
    is told to grow, and the layout would collapse to the top of the screen.
    """
    if depth > _V2_MAX_DEPTH:
        _placeholder("more_horiz", "Nested too deep to draw")
        return

    node_type = str(node.get("type", ""))
    drawer = _V2_DRAWERS.get(node_type, _v2_draw_unknown)
    hidden = str(node.get("showWhen", "")).strip()

    # position: relative so the bounds label, the condition marker and the event badges have
    # this component to hang off rather than the nearest positioned ancestor.
    #
    # min-width/min-height 0 because a flex item defaults to min-*: auto, which stops it ever
    # shrinking below its content -- the single most common reason a faithful-looking flex
    # translation overflows the frame it was given.
    style = "position: relative; box-sizing: border-box; min-width: 0; min-height: 0;"
    if fill:
        style += "flex: 1 1 auto; width: 100%; height: 100%;"
    # The modifier chain goes last so that a Scene that explicitly sizes a component beats
    # both of the defaults above -- the Scene's own instructions are the more specific ones.
    style += _v2_modifier_style(node)
    if hidden:
        # It may not be on screen at all when the Scene runs -- it is drawn anyway (this is a
        # preview of the layout, and a component nobody can see is still a component someone
        # has to find) but it is never drawn as though it were unconditional.
        style += "outline: 1px dashed rgba(217,119,6,0.9); outline-offset: -1px;"

    # The selection outline goes on last so it wins over a Show when's dashed one: which
    # components are about to be dragged is the more urgent of the two things to say, and the
    # amber outline is still there the moment the selection moves on.
    path, siblings = _V2_PATHS.get(id(node), ((), 0)) if _V2_EDITING is not None else ((), 0)
    if _V2_EDITING is not None and path in _V2_EDITING.selected:
        style += "outline: 2px solid #2563eb; outline-offset: -2px;"

    # The class is on every component, editing or not: it is what the hull is measured from,
    # and the hull is part of the picture rather than part of the editing surface.
    container = ui.element("div").classes(V2_COMPONENT_CLASS).style(style)
    if _V2_EDITING is not None and path:
        # The root is deliberately left out: it has no siblings, so there is nothing it could
        # be dragged among, and marking it draggable would be an offer that cannot be kept.
        #
        # data-sibs is how many components share its slot -- the count the drop gap is
        # measured against, known here and nowhere in the browser.
        container.classes("mt-v2-node").props(
            f'data-path="{v2_encode_path(path)}" data-sibs="{siblings}"',
        )
        if siblings > 1:
            container.style("cursor: grab;")
    with container:
        drawer(node, options, depth)
        if hidden:
            _v2_condition_badge(node)
        if options.show_bounds:
            _v2_bounds_label(node)
        if options.show_tasks:
            _v2_event_badge(node)
    _v2_tooltip(container, node)


# The components named by one of their own properties when they carry no treeLabel, and which
# property -- the same table sceneedit.V2_LABEL_FALLBACK holds for the designer's tree,
# written out again rather than imported to keep the renderer from depending on the editor.
# The two change together.
_V2_NAMED_BY_PROPERTY = {"Text": "text", "Button": "text", "IconButton": "icon"}


def _v2_bounds_label(node: dict) -> None:
    """The component's name, the way the designer's tree says it -- so a component picked out
    of the picture can be found in the tree, and the other way round.

    Which means the same order of preference sceneedit.v2_node_name uses, own property
    included: the two are written out separately rather than shared, to keep the renderer from
    importing the editor, and they have to be changed together.
    """
    own_key = _V2_NAMED_BY_PROPERTY.get(str(node.get("type", "")), "")
    own = str(node.get(own_key, "") or "") if own_key else ""
    if own and _v2_is_html(node):
        # Named by what it says rather than by its markup -- "Bold heading", not
        # "<b>Bold</b> heading".
        own = _v2_plain_text(own)
    if own and own_key == "icon":
        # "icon:Close" is called Close; a Symbol's ";weight:600;opsz:24" says how to draw it.
        own = tasker_icon_name(own)
    label = node.get("treeLabel") or own.strip() or node.get("id") or node.get("type", "?")
    ui.label(str(label)).style(
        "position: absolute; left: 0; top: 0; z-index: 5; pointer-events: none;"
        "font: 9px/1.2 monospace; color: rgba(37,99,235,0.95); background: rgba(255,255,255,0.75);"
        "padding: 0 2px; border-radius: 2px; max-width: 100%; overflow: hidden;"
        "text-overflow: ellipsis; white-space: nowrap;",
    )


def _v2_condition_badge(node: dict) -> None:
    """What decides whether this component is on screen, and what happens when it is not:
    "Gone" takes its space back, "Invisible" leaves the space behind.  Two different layouts,
    so the mode is shown and not just the condition.
    """
    mode = str(node.get("showWhenMode", "") or "Gone")
    ui.label(f"?{node.get('showWhen', '')} · {mode}").style(
        "position: absolute; right: 0; top: 0; z-index: 5; pointer-events: none;"
        "font: 9px/1.2 monospace; color: #fff; background: rgba(217,119,6,0.92);"
        "padding: 0 3px; border-radius: 2px; max-width: 100%; overflow: hidden;"
        "text-overflow: ellipsis; white-space: nowrap;",
    )


def _v2_event_badge(node: dict) -> None:
    """What this component does when it is used -- the V2 answer to the Legacy Task badge."""
    lines = _v2_handler_lines(node) + _v2_binding_lines(node)
    if not lines:
        return
    with ui.element("div").style(
        "position: absolute; left: 0; right: 0; bottom: 0; z-index: 4; pointer-events: none;"
        "display: flex; flex-wrap: wrap; gap: 2px; justify-content: flex-end;",
    ):
        for line in lines:
            ui.label(line).style(
                "font: 9px/1.3 monospace; color: #fff; background: rgba(37,99,235,0.9);"
                "padding: 0 3px; border-radius: 2px; max-width: 100%;"
                "overflow: hidden; text-overflow: ellipsis; white-space: nowrap;",
            )


def _v2_tooltip(container: ui.element, node: dict) -> None:
    """Everything about this component the drawing cannot carry: its id and type, its
    modifiers in the order they apply, the %variables it depends on, what it does, and where
    it writes to.

    The modifier list is the part that earns its keep.  A modifier this renderer has no CSS
    for -- WindowDrag, or one from a newer Tasker -- is still named here, so "the preview does
    not draw it" never quietly becomes "the Scene does not have it".
    """
    lines = [f"{node.get('type', '?')} '{node.get('id', '')}'".strip()]
    tree_label = node.get("treeLabel")
    if tree_label:
        lines.append(f"{translate_string('Tree label')}: {tree_label}")

    modifiers = [
        str(modifier.get("type", "?"))
        + ("" if _v2_modifier_drawn(str(modifier.get("type", ""))) else f" ({translate_string('not drawn')})")
        for modifier in node.get("modifiers") or []
        if isinstance(modifier, dict)
    ]
    if modifiers:
        lines.append(f"{translate_string('Modifiers')}: {' → '.join(modifiers)}")

    variables = sorted({
        value for value in node.values() if isinstance(value, str) and value.startswith("%")
    })
    if variables:
        lines.append(f"{translate_string('Variables')}: {', '.join(variables)}")
    if node.get("showWhen"):
        lines.append(f"{translate_string('Show when')}: {node['showWhen']} ({node.get('showWhenMode', 'Gone')})")
    lines.extend(_v2_handler_lines(node))
    lines.extend(_v2_binding_lines(node))

    with container:
        ui.tooltip("\n".join(lines)).style("white-space: pre-line")


def _v2_text_style(node: dict, default_colour: str = "") -> str:
    """Size and colour for anything that shows text."""
    size = str(node.get("textSize", "")).strip()
    try:
        size_px = float(size) if size and not size.startswith("%") else _V2_DEFAULT_TEXT_SIZE
    except ValueError:
        size_px = _V2_DEFAULT_TEXT_SIZE
    colour = v2_colour(node.get("color"), fallback=default_colour or V2_MATERIAL_PALETTE["onSurface"])
    align = _V2_ALIGNMENT.get(str(node.get("textAlign", "")), "")
    style = f"font-size: {size_px:g}px; line-height: 1.35;"
    style += f"color: {'rgba(100,116,139,0.95)' if colour.is_variable else colour.css};"
    if align:
        style += f"text-align: {'left' if align == 'flex-start' else 'right' if align == 'flex-end' else 'center'};"
    return style


def _v2_text(value: object, style: str) -> None:
    """Draw a run of text, marked when it is a %variable rather than a literal -- the same
    convention the Legacy half uses, so the two previews read the same way.
    """
    text = str(value or "")
    if not text:
        return
    if text.startswith("%"):
        style += "font-style: italic; text-decoration: underline dotted; opacity: 0.85;"
    ui.label(text).style(f"{style} max-width: 100%; overflow: hidden; white-space: pre-wrap;")


# One <a>...</a> and what it reads as on screen.  Nothing else about the markup is parsed:
# this is here to find the *links*, because they are the run drawn in the component's own
# link colour, and everything else is text.
_V2_ANCHOR = re.compile(r"<a\b[^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)

# A link nobody wrote a tag around.  Android linkifies these itself -- a bare https://..., a
# www. address or an email address in a text is tappable on the phone and drawn in the link
# colour -- so a preview that only coloured <a> runs would show a Scene whose one link is
# plainly a URL as having no links at all.
_V2_AUTOLINK = re.compile(
    r"(?:https?://|www\.)[^\s<>\"']+|[\w.+-]+@[\w-]+\.[\w.-]+",
    re.IGNORECASE,
)

# Punctuation that ends the sentence rather than the URL: "see https://x.com." links up to
# the "m".  Matches how Android's own Linkify treats a trailing stop.
_V2_AUTOLINK_TRAILING = ".,;:!?)\"'"

# What Tasker's contentFormat has to say for the text to be markup rather than a sentence.
_V2_HTML_FORMAT = "html"


def _v2_is_html(node: dict) -> bool:
    """Whether this component's text is to be read as markup: contentFormat says Html, and
    there is text to read it in.

    Deliberately NOT also "and there is a tag in it".  That extra test looks like the careful
    version and is the wrong one: an Html text whose only link is a bare URL has no tags at
    all, and gating on tags drew exactly that case -- the commonest one there is -- as a plain
    sentence with its link uncoloured.  Whether the text is markup is what contentFormat says;
    what is in it decides only what the drawing has to do.

    A text that is wholly a %variable is still excluded, as it is on the Legacy side (see
    _is_inline_html): its markup, and any link in it, arrive on the phone and not here, so it
    keeps the plain label and its variable marking.
    """
    if str(node.get("contentFormat", "")).strip().lower() != _V2_HTML_FORMAT:
        return False
    text = str(node.get("text", "") or "").strip()
    return bool(text) and not text.startswith("%")


def _v2_link_colour(node: dict) -> str:
    """The CSS colour this component's tappable links are drawn in.

    linkColor is an ordinary HTML colour -- a name or a #hex -- which is one more form than
    v2_colour parses (that one knows Material role names, Tasker's #AARRGGBB and CSS's
    shorter hexes), so a name is checked for separately and handed to CSS as itself.

    A %variable can't be resolved from a backup file, so it draws in the same muted grey
    _v2_text_style uses for a variable-driven text colour: the preview says "this is decided
    on the phone" rather than inventing a colour to show.  Nothing set at all means Material's
    primary, which is what an unstyled link lands on.
    """
    raw = str(node.get("linkColor", "") or "").strip()
    if raw.startswith("%"):
        return "rgba(100,116,139,0.95)"
    return v2_swatch_colour(raw) or V2_MATERIAL_PALETTE["primary"]


def _v2_html_text(node: dict, style: str) -> None:
    """Draw an Html-format text: its links in the component's link colour, the rest as text.

    The markup is taken apart rather than rendered.  A V2 component draws in the page's own
    flow -- it has no geometry to give a frame a size (which is how the Legacy half can afford
    to render markup properly, in the sandboxed iframe at _WEB_SANDBOX) -- and putting a
    stranger's markup loose in this page is the one thing that module is careful never to do.

    So what is drawn is the sentence with its tags taken off, the way the Legacy half draws an
    HTML text it isn't rendering, with the tappable runs kept apart and coloured.  That is the
    part of the markup this preview is actually being asked about: which words are tappable,
    and what colour they come out.  Each run goes in as *text* through ui.label, so nothing in
    the Scene can be markup here however it was written.

    Tappable means both kinds of link: the ones written as <a>, and the bare URLs and email
    addresses Android turns into links on its own (see _V2_AUTOLINK).
    """
    raw = str(node.get("text", "") or "")
    link_style = f"color: {_v2_link_colour(node)}; text-decoration: underline;"
    with ui.element("div").style(f"{style} max-width: 100%; overflow: hidden;"):
        position = 0
        for match in _V2_ANCHOR.finditer(raw):
            _v2_linkified_runs(raw[position : match.start()], link_style)
            _v2_run(_v2_plain_text(match.group(1)), link_style)
            position = match.end()
        _v2_linkified_runs(raw[position:], link_style)


def _v2_plain_text(fragment: str) -> str:
    """A run of markup as the words it shows: tags off, entities back (a &amp; is an "&" on
    the phone, not five characters).  What makes the drawn result a sentence rather than a
    listing of its source.
    """
    return html.unescape(_HTML_TAG.sub("", fragment))


def _v2_linkified_runs(fragment: str, link_style: str) -> None:
    """Draw a stretch of text that is outside any <a>, giving the link colour to the URLs and
    email addresses in it that Android would make tappable by itself.

    Tags come off first, so a URL that is only there as an href -- inside a tag rather than in
    the words -- is not mistaken for one the reader can see.
    """
    text = _v2_plain_text(fragment)
    position = 0
    for match in _V2_AUTOLINK.finditer(text):
        link = match.group(0).rstrip(_V2_AUTOLINK_TRAILING)
        _v2_run(text[position : match.start()], "")
        _v2_run(link, link_style)
        position = match.start() + len(link)
    _v2_run(text[position:], "")


def _v2_run(text: str, style: str) -> None:
    """One run of an Html-format text, drawn inline so the runs read as one sentence rather
    than as a stack of lines.
    """
    if text:
        ui.label(text).style(f"display: inline; {style}")


# ------------------------------------------------------------------
# One drawer per component type
# ------------------------------------------------------------------
def _v2_draw_column(node: dict, options: PreviewOptions, depth: int) -> None:
    """Column: children one above the other.  horizontalAlignment is align-items (across the
    column), verticalArrangement is justify-content (along it).
    """
    _v2_draw_stack(
        node,
        options,
        depth,
        direction="column",
        justify=_V2_ARRANGEMENT.get(str(node.get("verticalArrangement", "")), "flex-start"),
        align=_V2_ALIGNMENT.get(str(node.get("horizontalAlignment", "")), "stretch"),
    )


def _v2_draw_row(node: dict, options: PreviewOptions, depth: int) -> None:
    """Row: children side by side.  The two properties swap roles against a Column's."""
    _v2_draw_stack(
        node,
        options,
        depth,
        direction="row",
        justify=_V2_ARRANGEMENT.get(str(node.get("horizontalArrangement", "")), "flex-start"),
        align=_V2_ALIGNMENT.get(str(node.get("verticalAlignment", "")), "center"),
    )


def _v2_draw_flow_row(node: dict, options: PreviewOptions, depth: int) -> None:
    """FlowRow: a Row that wraps onto a new line when it runs out of width -- which is why
    the frame size on the toolbar changes what this draws, and is meant to.
    """
    # Named separately rather than as a single `gap`, because a FlowRow's two spacings are
    # different properties -- spacingHorizontal is the space between items along a line
    # (column-gap), spacingVertical the space between the lines (row-gap) -- and CSS's
    # shorthand takes them the other way round, row first.
    _v2_draw_stack(
        node,
        options,
        depth,
        direction="row",
        justify=_V2_ARRANGEMENT.get(str(node.get("horizontalArrangement", "")), "flex-start"),
        align="center",
        wrap=True,
        gap_css=_v2_axis_gap(column=_v2_number(node, "spacingHorizontal"), row=_v2_number(node, "spacingVertical")),
    )


def _v2_draw_flow_column(node: dict, options: PreviewOptions, depth: int) -> None:
    """FlowColumn: stacks downwards, wrapping into a new column when it runs out of height."""
    _v2_draw_stack(
        node,
        options,
        depth,
        direction="column",
        justify=_V2_ARRANGEMENT.get(str(node.get("horizontalArrangement", "")), "flex-start"),
        align=_V2_ALIGNMENT.get(str(node.get("itemHorizontalAlignment", "")), "stretch"),
        wrap=True,
    )


def _v2_draw_flex(node: dict, options: PreviewOptions, depth: int) -> None:
    """FlexBox -- Tasker marks it experimental itself.  It is the one component whose model
    is already CSS's, so its properties map across directly.
    """
    _v2_draw_stack(
        node,
        options,
        depth,
        direction="row",
        justify=_V2_ARRANGEMENT.get(str(node.get("alignContent", "")), "flex-start"),
        align=_V2_ALIGNMENT.get(str(node.get("alignItems", "")), "stretch"),
        wrap=str(node.get("wrap", "Wrap")) != "NoWrap",
        gap_css=_v2_axis_gap(column=_v2_number(node, "gap"), row=_v2_number(node, "gap")),
    )


def _v2_axis_gap(*, column: str, row: str) -> str:
    """Explicit row-gap/column-gap rather than the `gap` shorthand.

    The shorthand takes row before column and applies a lone value to both axes, so a
    container that sets only one of its two spacings would silently get that spacing on the
    axis it never asked about.  Naming them avoids both traps.
    """
    style = f"column-gap: {column};" if column else ""
    return style + (f"row-gap: {row};" if row else "")


def _v2_draw_stack(
    node: dict,
    options: PreviewOptions,
    depth: int,
    *,
    direction: str,
    justify: str,
    align: str,
    wrap: bool = False,
    gap_css: str = "",
) -> None:
    """The shared body of every flex container: one flex box, then each child in turn."""
    if not gap_css:
        # The plain single-spacing case -- a Column's or Row's `spacing`, which really does
        # mean the same thing on both axes because neither wraps.
        spacing = _v2_number(node, "spacing")
        gap_css = f"gap: {spacing};" if spacing else ""
    # height: 100% is deliberately unconditional and is not the same as "always full height":
    # a percentage height against a parent of automatic height computes to auto, so this fills
    # exactly when the component was given a definite height (by `fill`, or by a Size or
    # FillSize modifier) and is inert otherwise.  That is what makes verticalArrangement work
    # where it can and cost nothing where it cannot.
    style = (
        f"display: flex; flex-direction: {direction}; justify-content: {justify};"
        f"align-items: {align}; width: 100%; height: 100%; box-sizing: border-box;"
    )
    if wrap:
        style += "flex-wrap: wrap;"
    style += gap_css
    with ui.element("div").style(style):
        for child in _v2_all_children(node):
            _v2_draw_node(child, options, depth + 1)


def _v2_draw_box(node: dict, options: PreviewOptions, depth: int) -> None:
    """Box: a Z-stack -- children on top of one another rather than in a line.  A CSS grid
    with every child in the same cell is the flex-free way to say that.
    """
    with ui.element("div").style("display: grid; width: 100%; box-sizing: border-box;"):
        for child in _v2_all_children(node):
            with ui.element("div").style("grid-area: 1 / 1; min-width: 0; min-height: 0;"):
                _v2_draw_node(child, options, depth + 1)


def _v2_draw_card(node: dict, options: PreviewOptions, depth: int) -> None:
    """Card: a raised, rounded surface.  elevation is drawn as the shadow it is."""
    elevation = _v2_number(node, "elevation") or "1px"
    with ui.element("div").style(
        f"display: flex; flex-direction: column; width: 100%; box-sizing: border-box;"
        f"background: {V2_MATERIAL_PALETTE['surfaceVariant']}; border-radius: 12px; padding: 12px;"
        f"box-shadow: 0 {elevation} {elevation} rgba(0,0,0,0.22);",
    ):
        for child in _v2_all_children(node):
            _v2_draw_node(child, options, depth + 1)


def _v2_draw_scaffold(node: dict, options: PreviewOptions, depth: int) -> None:
    """Scaffold: the frame of a full-screen Scene -- topBar, content, bottomBar, and a
    floating action button over the content's bottom-right corner.

    Its slots are drawn in their real positions rather than in tree order, because that is
    what a Scaffold is: putting the bottomBar wherever it happened to appear in the JSON
    would make the one component whose whole job is placement the one this got wrong.
    """
    with ui.element("div").style(
        "display: flex; flex-direction: column; width: 100%; height: 100%; box-sizing: border-box;",
    ):
        for child in _v2_children(node, "topBar"):
            _v2_draw_node(child, options, depth + 1)
        with ui.element("div").style(
            "position: relative; flex: 1 1 auto; min-height: 0; display: flex; flex-direction: column;"
            "overflow: hidden;",
        ):
            for child in _v2_children(node, "content"):
                _v2_draw_node(child, options, depth + 1, fill=True)
            fab = _v2_children(node, "floatingActionButton")
            if fab:
                with ui.element("div").style("position: absolute; right: 16px; bottom: 16px; z-index: 3;"):
                    for child in fab:
                        _v2_draw_node(child, options, depth + 1)
        for child in _v2_children(node, "bottomBar"):
            _v2_draw_node(child, options, depth + 1)


def _v2_draw_top_app_bar(node: dict, options: PreviewOptions, depth: int) -> None:
    """TopAppBar: the navigationIcon slot, then the title slot, across the top."""
    with ui.element("div").style(
        f"display: flex; align-items: center; gap: 8px; width: 100%; height: 64px; padding: 0 8px;"
        f"box-sizing: border-box; background: {V2_MATERIAL_PALETTE['surfaceVariant']};"
        f"color: {V2_MATERIAL_PALETTE['onSurfaceVariant']}; flex: none;",
    ):
        for child in _v2_children(node, "navigationIcon"):
            _v2_draw_node(child, options, depth + 1)
        for child in _v2_children(node, "title"):
            _v2_draw_node(child, options, depth + 1)


def _v2_draw_bottom_app_bar(node: dict, options: PreviewOptions, depth: int) -> None:
    """BottomAppBar: the same bar, pinned to the bottom of a Scaffold."""
    with ui.element("div").style(
        f"display: flex; align-items: center; gap: 8px; width: 100%; height: 64px; padding: 0 8px;"
        f"box-sizing: border-box; background: {V2_MATERIAL_PALETTE['surfaceVariant']}; flex: none;",
    ):
        for child in _v2_all_children(node):
            _v2_draw_node(child, options, depth + 1)


def _v2_draw_navigation_bar(node: dict, options: PreviewOptions, depth: int) -> None:
    """NavigationBar: its Navigation Items spread evenly across the bottom.  selectedIndex
    picks the one drawn as current, which is a visible difference and worth honouring.
    """
    selected = _v2_int(node.get("selectedIndex"), -1)
    with ui.element("div").style(
        f"display: flex; justify-content: space-around; align-items: center; width: 100%; height: 72px;"
        f"box-sizing: border-box; background: {V2_MATERIAL_PALETTE['surfaceVariant']}; flex: none;",
    ):
        for index, child in enumerate(_v2_all_children(node)):
            # The bar's own selectedIndex wins over an item's "selected", because it is the
            # bar that decides which of its items is current.
            marked = _v2_alias(dict(child), child)
            if selected >= 0:
                marked["selected"] = "true" if index == selected else "false"
            _v2_draw_node(marked, options, depth + 1)


def _v2_draw_navigation_item(node: dict, options: PreviewOptions, depth: int) -> None:  # noqa: ARG001
    """NavigationItem: an icon over a label, tinted when it is the selected one."""
    is_selected = str(node.get("selected", "")).lower() == "true"
    colour = V2_MATERIAL_PALETTE["onSecondaryContainer" if is_selected else "onSurfaceVariant"]
    with ui.element("div").style(
        "display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px;"
        "padding: 4px 8px; box-sizing: border-box;"
        + (f"background: {V2_MATERIAL_PALETTE['secondaryContainer']}; border-radius: 16px;" if is_selected else ""),
    ):
        _v2_icon_or_placeholder(node.get("icon"), 24, colour)
        _v2_text(node.get("label"), f"font-size: 12px; line-height: 1.2; color: {colour};")


def _v2_draw_text(node: dict, options: PreviewOptions, depth: int) -> None:  # noqa: ARG001
    """Text: the component real Scenes are mostly made of."""
    if _v2_is_html(node):
        _v2_html_text(node, _v2_text_style(node))
        return
    _v2_text(node.get("text"), _v2_text_style(node))


def _v2_draw_button(node: dict, options: PreviewOptions, depth: int) -> None:  # noqa: ARG001
    """Button: text, buttonColor behind it, textColor on it -- Material's filled button when
    the Scene does not say otherwise.
    """
    background = v2_colour(node.get("buttonColor"), fallback=V2_MATERIAL_PALETTE["primary"])
    foreground = v2_colour(node.get("textColor"), fallback=V2_MATERIAL_PALETTE["onPrimary"])
    fill = VARIABLE_FILL if background.is_variable else background.css
    with ui.element("div").style(
        f"display: inline-flex; align-items: center; justify-content: center; gap: 8px;"
        f"padding: 10px 24px; border-radius: 20px; background: {fill}; box-sizing: border-box;",
    ):
        _v2_text(
            node.get("text"),
            f"font-size: 14px; line-height: 1.2; font-weight: 500;"
            f"color: {'rgba(255,255,255,0.85)' if foreground.is_variable else foreground.css};",
        )


def _v2_draw_icon_button(node: dict, options: PreviewOptions, depth: int) -> None:  # noqa: ARG001
    """IconButton: a 48dp target with the icon in the middle.  These draw as the real icon --
    "icon:Close" is Material's own name for it, so the browser has the same glyph Android does.
    """
    with ui.element("div").style(
        "display: inline-flex; align-items: center; justify-content: center;"
        "width: 48px; height: 48px; border-radius: 50%; flex: none; box-sizing: border-box;",
    ):
        _v2_icon_or_placeholder(node.get("icon"), 24, V2_MATERIAL_PALETTE["onSurfaceVariant"])


def _v2_draw_fab(node: dict, options: PreviewOptions, depth: int) -> None:
    """FloatingActionButton: the round raised button over a Scaffold's content."""
    with ui.element("div").style(
        f"display: flex; align-items: center; justify-content: center; width: 56px; height: 56px;"
        f"border-radius: 16px; background: {V2_MATERIAL_PALETTE['primaryContainer']};"
        f"color: {V2_MATERIAL_PALETTE['onPrimaryContainer']}; box-shadow: 0 3px 6px rgba(0,0,0,0.28);",
    ):
        children = _v2_all_children(node)
        if children:
            for child in children:
                _v2_draw_node(child, options, depth + 1)
        else:
            _v2_icon_or_placeholder(node.get("icon") or "icon:Add", 24, V2_MATERIAL_PALETTE["onPrimaryContainer"])


def _v2_draw_text_input(node: dict, options: PreviewOptions, depth: int) -> None:  # noqa: ARG001
    """TextInput: an outlined field showing its label.  What it writes into is on its badge
    (see _v2_binding_lines) -- for a text field that is the interesting half.
    """
    with ui.element("div").style(
        f"display: flex; align-items: center; width: 100%; min-height: 56px; padding: 8px 16px;"
        f"box-sizing: border-box; border: 1px solid {V2_MATERIAL_PALETTE['outline']}; border-radius: 4px;",
    ):
        _v2_text(
            node.get("label") or node.get("text"),
            _v2_text_style(node, default_colour=V2_MATERIAL_PALETTE["onSurfaceVariant"]),
        )


def _v2_draw_switch(node: dict, options: PreviewOptions, depth: int) -> None:  # noqa: ARG001
    """Switch: on or off, from `checked`."""
    _v2_draw_toggle(node, "toggle_on", "toggle_off")


def _v2_draw_checkbox(node: dict, options: PreviewOptions, depth: int) -> None:  # noqa: ARG001
    """Checkbox: ticked or not, from `checked`."""
    _v2_draw_toggle(node, "check_box", "check_box_outline_blank")


def _v2_draw_toggle(node: dict, on_icon: str, off_icon: str) -> None:
    """The shared body of Switch and Checkbox.  A `checked` holding a %variable is neither
    on nor off here, so it draws unchecked and says why on its own marker.
    """
    raw = str(node.get("checked", "")).strip()
    checked = raw.lower() == "true"
    with ui.element("div").style("display: inline-flex; align-items: center; gap: 4px;"):
        ui.icon(on_icon if checked else off_icon).style(
            f"font-size: 24px; color: {V2_MATERIAL_PALETTE['primary'] if checked else V2_MATERIAL_PALETTE['outline']};",
        )
        if raw.startswith("%"):
            _v2_text(raw, "font-size: 11px; line-height: 1.2;")


def _v2_draw_slider(node: dict, options: PreviewOptions, depth: int) -> None:  # noqa: ARG001
    """Slider: the thumb where `value` falls between min and max."""
    minimum = _v2_float(node.get("min"), 0.0)
    maximum = _v2_float(node.get("max"), 100.0)
    value = _v2_float(node.get("value"), minimum)
    span = maximum - minimum
    fraction = 0.0 if span <= 0 else max(0.0, min(1.0, (value - minimum) / span))
    _v2_draw_track([fraction])


def _v2_draw_range_slider(node: dict, options: PreviewOptions, depth: int) -> None:  # noqa: ARG001
    """RangeSlider: two thumbs, at `start` and `end`, on a 0-1 scale of its own."""
    _v2_draw_track([
        max(0.0, min(1.0, _v2_float(node.get("start"), 0.0))),
        max(0.0, min(1.0, _v2_float(node.get("end"), 1.0))),
    ])


def _v2_draw_track(fractions: list[float]) -> None:
    """A slider's track with a thumb at each of these positions, and the range between the
    first and last drawn as the active part -- which is what makes a RangeSlider read as a
    range rather than as two unrelated dots.
    """
    low, high = min(fractions), max(fractions)
    with ui.element("div").style("display: flex; align-items: center; width: 100%; height: 32px; padding: 0 8px;"):
        with ui.element("div").style(
            f"position: relative; width: 100%; height: 4px; border-radius: 999px;"
            f"background: {V2_MATERIAL_PALETTE['surfaceVariant']};",
        ):
            ui.element("div").style(
                f"position: absolute; left: {round(low * 100, 1)}%; right: {round((1 - high) * 100, 1)}%;"
                f"top: 0; bottom: 0; background: {V2_MATERIAL_PALETTE['primary']}; border-radius: 999px;",
            )
            for fraction in fractions:
                ui.element("div").style(
                    f"position: absolute; left: calc({round(fraction * 100, 1)}% - 8px); top: -6px;"
                    f"width: 16px; height: 16px; border-radius: 50%;"
                    f"background: {V2_MATERIAL_PALETTE['primary']};",
                )


def _v2_draw_progress(node: dict, options: PreviewOptions, depth: int) -> None:  # noqa: ARG001
    """ProgressBar: minProgress is where it starts, and its colour is its own property."""
    colour = v2_colour(node.get("color"), fallback=V2_MATERIAL_PALETTE["primary"])
    fraction = max(0.0, min(1.0, _v2_float(node.get("minProgress"), 0.0)))
    with ui.element("div").style(
        f"width: 100%; height: 4px; border-radius: 999px; background: {V2_MATERIAL_PALETTE['surfaceVariant']};",
    ):
        ui.element("div").style(
            f"width: {round(fraction * 100, 1)}%; height: 100%; border-radius: 999px;"
            f"background: {VARIABLE_FILL if colour.is_variable else colour.css};",
        )


def _v2_draw_segmented_row(node: dict, options: PreviewOptions, depth: int) -> None:
    """SegmentedButtonRow: its items joined into one control, with selectedIndices marking
    which of them are on -- a comma-separated list, because the row can allow several.
    """
    selected = {
        index.strip() for index in str(node.get("selectedIndices", "")).split(",") if index.strip().isdigit()
    }
    with ui.element("div").style(
        f"display: inline-flex; border: 1px solid {V2_MATERIAL_PALETTE['outline']}; border-radius: 20px;"
        f"overflow: hidden; box-sizing: border-box;",
    ):
        for index, child in enumerate(_v2_all_children(node)):
            marked = _v2_alias(dict(child), child)
            marked["selected"] = "true" if str(index) in selected else "false"
            _v2_draw_node(marked, options, depth + 1)


def _v2_draw_segmented_item(node: dict, options: PreviewOptions, depth: int) -> None:  # noqa: ARG001
    """SegmentedButtonItem: one segment of that control."""
    is_selected = str(node.get("selected", "")).lower() == "true"
    with ui.element("div").style(
        f"display: flex; align-items: center; justify-content: center; padding: 8px 16px; gap: 4px;"
        f"box-sizing: border-box;"
        + (f"background: {V2_MATERIAL_PALETTE['secondaryContainer']};" if is_selected else ""),
    ):
        if is_selected:
            ui.icon("check").style(f"font-size: 16px; color: {V2_MATERIAL_PALETTE['onSecondaryContainer']};")
        _v2_text(
            node.get("label"),
            f"font-size: 14px; line-height: 1.2;"
            f"color: {V2_MATERIAL_PALETTE['onSecondaryContainer' if is_selected else 'onSurface']};",
        )


def _v2_draw_dropdown(node: dict, options: PreviewOptions, depth: int) -> None:
    """Dropdown: the trigger, plus its menu drawn as the separate surface it becomes.

    The menu is shown rather than hidden -- a preview exists to show what is in the Scene,
    and a dropdown's content is the part nobody can see in the tree -- but it is drawn on its
    own dashed surface and labelled, so it is never mistaken for something on screen at rest.
    """
    with ui.element("div").style("display: flex; flex-direction: column; gap: 4px; box-sizing: border-box;"):
        for child in _v2_children(node, "trigger"):
            _v2_draw_node(child, options, depth + 1)
        content = _v2_children(node, "content")
        if content:
            ui.label(translate_string("Dropdown menu — shown when opened")).style(
                "font: 9px/1.2 monospace; color: rgba(71,85,105,0.95);",
            )
            with ui.element("div").style(
                f"display: flex; flex-direction: column; border: {PLACEHOLDER_EDGE}; border-radius: 4px;"
                f"background: {V2_MATERIAL_PALETTE['surface']}; padding: 4px; box-sizing: border-box;",
            ):
                for child in content:
                    _v2_draw_node(child, options, depth + 1)


def _v2_draw_arrays_template(node: dict, options: PreviewOptions, depth: int) -> None:
    """ArraysMergeTemplate: one block, repeated once per entry in a set of Tasker arrays.

    Drawn once, labelled.  How many times it really repeats is however many entries those
    arrays hold when the Scene runs, which is not in the backup -- so drawing three of them
    would be inventing a number.
    """
    with ui.element("div").style(
        f"display: flex; flex-direction: column; width: 100%; border: {PLACEHOLDER_EDGE};"
        f"border-radius: 4px; padding: 4px; box-sizing: border-box;",
    ):
        ui.label(translate_string("Repeats once per array entry")).style(
            "font: 9px/1.2 monospace; color: rgba(71,85,105,0.95);",
        )
        for child in _v2_all_children(node):
            _v2_draw_node(child, options, depth + 1)


def _v2_draw_variable(node: dict, options: PreviewOptions, depth: int) -> None:  # noqa: ARG001
    """Variable: declares a Scene variable and draws nothing at all in Tasker.

    Drawn here as a marker, because "nothing" and "not there" look identical on screen and
    the designer's tree shows it as a component.  A preview that silently dropped it would
    disagree with the tree about what the Scene contains.
    """
    with ui.element("div").style(
        f"display: inline-flex; align-items: center; gap: 4px; padding: 1px 6px; border-radius: 4px;"
        f"border: {PLACEHOLDER_EDGE}; background: {PLACEHOLDER_FILL}; box-sizing: border-box;",
    ):
        ui.icon("data_object").style("font-size: 12px; color: rgba(100,116,139,0.95);")
        ui.label(f"{translate_string('Variable')} {node.get('key', '')}").style(
            "font: 10px/1.2 monospace; color: rgba(71,85,105,0.95);",
        )


def _v2_draw_spacer(node: dict, options: PreviewOptions, depth: int) -> None:  # noqa: ARG001
    """Spacer: empty space of a fixed size."""
    height = _v2_number(node, "height") or "16px"
    width = _v2_number(node, "width")
    ui.element("div").style(f"height: {height};{f'width: {width};' if width else 'width: 100%;'} flex: none;")


def _v2_draw_divider(node: dict, options: PreviewOptions, depth: int) -> None:  # noqa: ARG001
    """Divider: a rule across its container."""
    colour = v2_colour(node.get("color"), fallback=V2_MATERIAL_PALETTE["outlineVariant"])
    ui.element("div").style(f"width: 100%; height: 1px; background: {colour.css}; flex: none;")


def _v2_draw_image(node: dict, options: PreviewOptions, depth: int) -> None:  # noqa: ARG001
    """Image: a named icon, or a URL that is deliberately not fetched.

    An icon: reference draws as the real icon.  A URL does not: previewing a Scene should not
    make this app go to the network on behalf of a file someone else wrote, and a URL that is
    a %variable could not be fetched anyway.  So it is named instead.
    """
    icon = v2_icon(node.get("icon"))
    width = _v2_number(node, "width")
    height = _v2_number(node, "height")
    box = f"{f'width: {width};' if width else ''}{f'height: {height};' if height else ''}"
    if icon:
        with ui.element("div").style(f"display: inline-flex; align-items: center; justify-content: center; {box}"):
            ui.icon(icon).style(f"font-size: {height or '32px'}; color: {V2_MATERIAL_PALETTE['onSurfaceVariant']};")
        return
    package = _v2_app_icon(node.get("icon"))
    if package:
        # Named rather than drawn, for the reason at _v2_app_icon -- and named as the app it
        # is, rather than falling through to the "Image" panel below, which would say only
        # that something unshowable goes here.
        with ui.element("div").style(f"{box or 'width: 100%; height: 96px;'} position: relative; flex: none;"):
            _placeholder("android", "App icon", package)
        return
    url = str(node.get("url", "") or node.get("icon", ""))
    with ui.element("div").style(f"{box or 'width: 100%; height: 96px;'} position: relative; flex: none;"):
        _placeholder("image", "Image", url.rsplit("/", 1)[-1] if url else "")


def _v2_draw_web_view(node: dict, options: PreviewOptions, depth: int) -> None:  # noqa: ARG001
    """WebView: an embedded page, or HTML held in a variable.

    Inline HTML is drawn, in the same sandboxed frame the Legacy WebElement uses -- see
    _draw_web and _WEB_SANDBOX.  A `content` that names a page instead of holding one, or
    that is a %variable, keeps the panel.

    No density here: a V2 layout is already laid out in dp, which this renderer maps to CSS
    pixels one-for-one, so the frame is simply the box it was given.
    """
    height = _v2_number(node, "height") or "120px"
    content = str(node.get("content", ""))
    with ui.element("div").style(f"position: relative; width: 100%; height: {height}; flex: none;"):
        if _is_inline_html(content):
            _html_frame(content, "position: absolute; inset: 0; width: 100%; height: 100%;", background="#fff")
            _corner_badge("HTML")
        else:
            _placeholder("public", "WebView", content.splitlines()[0][:60] if content else "")


def _v2_draw_video(node: dict, options: PreviewOptions, depth: int) -> None:  # noqa: ARG001
    """Video: source, and whether it starts itself and loops."""
    flags = [name for name in ("autoPlay", "loop") if str(node.get(name, "")).lower() == "true"]
    caption = f"Video ({', '.join(flags)})" if flags else "Video"
    detail = str(node.get("source", ""))
    with ui.element("div").style("position: relative; width: 100%; height: 140px; flex: none;"):
        _placeholder("movie", caption, detail.rsplit("/", 1)[-1])


def _v2_draw_camera(node: dict, options: PreviewOptions, depth: int) -> None:  # noqa: ARG001
    """Camera: a live preview from one of the device's lenses."""
    with ui.element("div").style("position: relative; width: 100%; height: 140px; flex: none;"):
        _placeholder("photo_camera", "Camera", str(node.get("lens", "")))


def _v2_draw_placeholder(node: dict, options: PreviewOptions, depth: int) -> None:  # noqa: ARG001
    """Placeholder: Tasker's own blank stand-in, for reserving space while building."""
    with ui.element("div").style("position: relative; width: 100%; height: 48px; flex: none;"):
        _placeholder("crop_free", "Placeholder")


def _v2_draw_unknown(node: dict, options: PreviewOptions, depth: int) -> None:
    """A component type this app has no drawer for -- from a newer Tasker, most likely.

    Drawn as a labelled box that still renders its children, so a container this app has
    never seen does not take the whole subtree under it off the screen.  Its properties are
    in the tooltip like any other component's.
    """
    with ui.element("div").style(
        f"display: flex; flex-direction: column; gap: 2px; width: 100%; padding: 4px; box-sizing: border-box;"
        f"border: {PLACEHOLDER_EDGE}; border-radius: 4px; background: {PLACEHOLDER_FILL};",
    ):
        ui.label(str(node.get("type", "?"))).style("font: 10px/1.2 monospace; color: rgba(71,85,105,0.95);")
        for child in _v2_all_children(node):
            _v2_draw_node(child, options, depth + 1)


def _v2_icon_or_placeholder(raw: object, size: int, colour: str) -> None:
    """A named icon as the real glyph, an app's icon as a stand-in that says which app, and
    anything else -- a URL, a %variable -- named instead.
    """
    icon = v2_icon(raw)
    if icon:
        ui.icon(icon).style(f"font-size: {size}px; color: {colour};")
        return
    package = _v2_app_icon(raw)
    if package:
        # The app's real icon is on the phone (see _v2_app_icon).  A generic glyph at the
        # right size and place says "an app icon goes here" without inventing which one; the
        # tooltip is where the package name goes, there being no room for it at 48px.
        with ui.icon("android").style(f"font-size: {size}px; color: {colour};"):
            ui.tooltip(f"{translate_string('App icon')}: {package}")
        return
    text = str(raw or "")
    if text:
        _v2_text(text, f"font-size: {max(9, size // 2)}px; line-height: 1.2; color: {colour};")


def _v2_int(value: object, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _v2_float(value: object, default: float) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


_V2_DRAWERS: dict[str, object] = {
    "Column": _v2_draw_column,
    "Row": _v2_draw_row,
    "FlowRow": _v2_draw_flow_row,
    "FlowColumn": _v2_draw_flow_column,
    "FlexBox": _v2_draw_flex,
    "Box": _v2_draw_box,
    "Card": _v2_draw_card,
    "Scaffold": _v2_draw_scaffold,
    "TopAppBar": _v2_draw_top_app_bar,
    "BottomAppBar": _v2_draw_bottom_app_bar,
    "NavigationBar": _v2_draw_navigation_bar,
    "NavigationItem": _v2_draw_navigation_item,
    "FloatingActionButton": _v2_draw_fab,
    "Text": _v2_draw_text,
    "Button": _v2_draw_button,
    "IconButton": _v2_draw_icon_button,
    "TextInput": _v2_draw_text_input,
    "Switch": _v2_draw_switch,
    "Checkbox": _v2_draw_checkbox,
    "Slider": _v2_draw_slider,
    "RangeSlider": _v2_draw_range_slider,
    "ProgressBar": _v2_draw_progress,
    "SegmentedButtonRow": _v2_draw_segmented_row,
    "SegmentedButtonItem": _v2_draw_segmented_item,
    "Dropdown": _v2_draw_dropdown,
    "ArraysMergeTemplate": _v2_draw_arrays_template,
    "Variable": _v2_draw_variable,
    "Spacer": _v2_draw_spacer,
    "Divider": _v2_draw_divider,
    "Image": _v2_draw_image,
    "WebView": _v2_draw_web_view,
    "Video": _v2_draw_video,
    "Camera": _v2_draw_camera,
    "Placeholder": _v2_draw_placeholder,
}
