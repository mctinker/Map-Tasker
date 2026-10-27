"""Scene Preview: draw a Scene as a picture rather than as a list of element names.

This is the drawing half of the "Preview" button on the Add/Edit Scene dialogs; the view
that hosts it (toolbar, scroll area, theming) is guiwins_sceneview.NiceGuiSceneView, and the button
itself is in guiwins_scene._build_scene_editor_body.

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
    renders markup without running it or letting it reach anything.  See WEB_SANDBOX,
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

Anything whose meaning is unknown is not drawn.  A V2 modifier or component type this app has
never seen is listed in the component's tooltip and drawn as a labelled box, so it is visible
without being invented.

A Legacy element's <flags> used to be in that category and no longer is: objprops holds
Tasker's own values for its four bits, so an element Tasker would not show (mask 4 clear) is
dimmed here rather than drawn as though it were on screen, and all four bits are named in the
tooltip.  What is still NOT inferred from them is the paint order, which comes from the sr
number and is left alone -- mask 2 marks a background element, but the z-order the sample
Scenes actually paint in is the one paint_order already uses.

The drawing is in these modules, which this one is the shared base of (options, colours, element arguments and
geometry):

    sceneview_legacy    the Legacy canvas and its element drawers
    sceneview_v2        the Version 2 component tree
    sceneview_v2base    its screens, colours and icons
    sceneview_v2style   its modifiers as CSS
    sceneview_v2text    its text, HTML and links
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from maptasker.src.core import objprops
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.core.sysconst import SCENE_TASK_TYPES

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from maptasker.src.core.primitem import RunState


# sp -> px.  See this module's docstring: not a fact about the Scene, a property of the
# device it would be shown on, so it is a default rather than a constant.
DEFAULT_DENSITY = 2.75


DENSITY_CHOICES = ("1.0", "1.5", "2.0", "2.625", "2.75", "3.0", "3.5")


# A colour this preview cannot know -- a %variable, or an argument the Scene left empty.
# Hatching rather than a flat grey so it reads as "unknown" at a glance instead of as a
# deliberate choice of grey.
VARIABLE_FILL = "repeating-linear-gradient(45deg, rgba(148,163,184,0.45) 0 6px, rgba(148,163,184,0.12) 6px 12px)"


# What a placeholder (an image we can't load, a video, a map) is drawn on.
PLACEHOLDER_FILL = "rgba(148,163,184,0.16)"


PLACEHOLDER_EDGE = "1px dashed rgba(148,163,184,0.85)"


# actiont "TextElement1" -- the Position argument on Text/Button/EditText, in its own order:
# Center, Top, Bottom, Left, Right, Top Left, Top Right, Bottom Left, Bottom Right.  Indexed
# by that list rather than by a copy of it, so the two cannot drift.
POSITION_FLEX: dict[int, tuple[str, str]] = {
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
SHADER_GRADIENTS: dict[int, str] = {
    1: "linear-gradient(to right, {start}, {end})",
    2: "linear-gradient(to bottom, {start}, {end})",
    3: "linear-gradient(to bottom right, {start}, {end})",
    4: "linear-gradient(to top right, {start}, {end})",
    5: "radial-gradient(circle, {start}, {end})",
}


# actiont "RectElement2" -- which corners the Corner Radius applies to: All, Top, Bottom,
# Left, Right.  CSS order is top-left, top-right, bottom-right, bottom-left.
ROUNDED_CORNERS: dict[int, tuple[bool, bool, bool, bool]] = {
    0: (True, True, True, True),
    1: (True, True, False, False),
    2: (False, False, True, True),
    3: (True, False, False, True),
    4: (False, True, True, False),
}


# actiont "TextElement2" -- Vertical Fit Mode: None, Reduce Text Size, Allow Scrolling.
FIT_REDUCE = 1


FIT_SCROLL = 2


# actiont "TextElement3" -- Text Format: Plain Text, Text With Links, HTML.
FORMAT_HTML = 2


# For the HTML-format text that is NOT rendered -- a value with no real markup in it, or one
# that is wholly a %variable; see _text_content.  Deliberately a blunt "anything between
# angle brackets": this is not parsing the markup, it is removing it.
HTML_TAG = re.compile(r"<[^>]*>")


# How deep to follow an item layout (a Spinner/List/Picker carries a whole nested <Scene>).
# One level is what makes those elements legible; more would be a Scene inside a Scene inside
# a Scene, drawn at a size nobody can read.
MAX_ITEM_DEPTH = 1


# actiont "WebElement" -- Mode: URL, File, Direct.  Only "Direct" holds the page itself; the
# other two name something on the network or on the Android device, neither of which is here.
WEB_MODE_DIRECT = 2


# Does this value carry markup?  Deliberately loose -- one tag, closing tag or doctype is
# enough to call it a page.  A Source without one keeps the placeholder, so a bare URL, a
# lone %variable or a plain sentence is not dressed up as a document it isn't.
HTML_MARKUP = re.compile(r"<(?:!doctype\b|/?[a-z][a-z0-9]*)(?:\s[^>]*)?/?>", re.IGNORECASE)


# What the frame holding that markup may do: nothing that reaches out of itself.
#
# An empty sandbox is every restriction at once -- most of all no scripts and no
# same-origin -- which is what makes rendering the markup a different act from running it.
# The page draws; it cannot read this app's page, its session or its storage, cannot
# navigate the window it sits in, and cannot submit a form.  A shared Tasker project is
# exactly the sort of file that arrives from a stranger, so this is not negotiable: see
# _draw_web, which stopped at a placeholder for want of it.
WEB_SANDBOX = ""


# ...and nothing that reaches out to the network.  Without this, an <img src="https://...">
# or an @font-face in a stranger's Scene would tell that host the user just opened the
# backup, which is the network trip this module's docstring declines to make on their behalf.
# Inline CSS is what makes the preview worth looking at, and data: URIs are self-contained,
# so those two are all that is allowed.
WEB_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; media-src data:"


# Where that policy has to go: a Content-Security-Policy <meta> counts only inside <head>,
# and only before the content it governs.  Slipping it in after the document's own <head>
# (or after <html>, for markup that never opened one) leaves the rest of the document
# exactly as written -- which matters, because prepending a wrapper of our own would put
# the doctype in the body and drop the page into quirks mode, changing the very layout the
# preview exists to show.
HTML_HEAD_OPEN = re.compile(r"<head(?:\s[^>]*)?>", re.IGNORECASE)


HTML_OPEN = re.compile(r"<html(?:\s[^>]*)?>", re.IGNORECASE)


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
    form sceneedit_v2tree.v2_flatten hands out.  A run rather than a single path because a drag
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
        """Whether the colour is a %variable, which has no colour to draw until Tasker runs."""
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

    def __init__(self, element: Element) -> None:
        """Hold the element whose arguments are to be read."""
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
        """The colour held at this argument."""
        return tasker_colour(self.text(index), fallback)


def scene_dimensions(
    scene_element: Element,
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


def has_landscape_layout(scene_element: Element) -> bool:
    """Whether the preview's Landscape toggle has anything to show."""
    return scene_dimensions(scene_element, landscape=True) is not None


def element_geometry(
    element: Element,
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


def element_name(element: Element) -> str:
    """The name the user gave this element in Tasker's Scene editor -- arg0 on every type."""
    return ElementArgs(element).text(0)


def element_flag_names(element: Element) -> list[str]:
    """This element's <flags> bits, named -- Fixed position, Background element, Visible,
    Initial focus -- and [] for an element with no <flags> at all.

    The names are objprops', which is where Tasker's own values for the bitmask live.  They
    go in the tooltip rather than into the drawing: three of the four say something about how
    Tasker treats the element that no amount of geometry shows, and the fourth (Visible) is
    the one this module does draw -- see element_is_hidden.
    """
    if element.find(objprops.SCENE_ELEMENT_FLAGS_TAG) is None:
        return []
    return objprops.describe_flags(objprops.flag_bits(element), objprops.SCENE_ELEMENT_FLAG_NAMES)


def element_is_hidden(element: Element) -> bool:
    """Would Tasker draw this element when the Scene is shown?

    Mask 4 is Visible, so an element whose <flags> has it CLEAR is one Tasker hides until a
    Task makes it visible -- 172 of the sample data's elements, mostly Images and Texts.

    AN ELEMENT WITH NO <flags> AT ALL IS NOT HIDDEN.  1,507 have none, a state Tasker itself
    produces, so absence means "nothing said" and such an element is drawn as normal.  Taking
    it as 0 would hide a fifth of every Scene in the preview, including every
    <PropertiesElement>.  A value that will not parse is the same answer for the same reason:
    the tag is Tasker's, and "I cannot read this" is not grounds for leaving the element out
    of the picture.
    """
    value = (element.findtext(objprops.SCENE_ELEMENT_FLAGS_TAG) or "").strip()
    return value.isdigit() and not (int(value) & (1 << objprops.SCENE_ELEMENT_VISIBLE_BIT))


def paint_order(scene_element: Element) -> list:
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

    def order(element: Element) -> tuple[int, str]:
        sr = element.get("sr", "")
        digits = sr[len("elements") :] if sr.startswith("elements") else ""
        return (int(digits), sr) if digits.isdigit() else (1_000_000, sr)

    return sorted(drawable, key=order)


def element_tasks(element: Element, state: RunState) -> list[tuple[str, str]]:
    """The Tasks this element fires, as (what fires it, Task name) -- "TAP", "LONG TAP",
    "ITEM TAP" and the rest, from sysconst.SCENE_TASK_TYPES.

    The child holds a Task *id*; the name comes out of the loaded backup.  A negative id is
    one of Tasker's anonymous inline Tasks (scenes.process_tasks calls these "fake"), which
    has no name to show, so it is reported as an unnamed Task rather than skipped -- the
    element does still do something when tapped, and that is the point of showing this.
    """
    all_tasks = state.tasker_root_elements.get("all_tasks", {})
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
