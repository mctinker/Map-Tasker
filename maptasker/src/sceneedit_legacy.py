"""sceneedit_legacy: the model the Legacy Scene designer edits.

Split out of sceneedit.py, which held both kinds of Scene and had grown past 5,000 lines.
A Legacy Scene is a pixel canvas: a flat list of <TextElement>/<RectElement>/... children,
each with its own <geom>, painted in sr order.  Everything here reads or changes one of
those -- its geometry and arguments, its place in the stack, the Tasks it fires, its
background, its item layout -- or the Scene's own <PropertiesElement>, and finds the Tasks
that address an element by name.

It knows nothing of Version 2 Scenes (sceneedit_v2.py) or of loading, saving and renaming a
Scene as a whole (sceneedit.py).  sceneedit imports it, never the other way round, which is
why UNSET_DIMENSION lives here: it is the value every size and geometry field below is
written with when an orientation has no layout, and sceneedit borrows it for a new Scene.
"""

from __future__ import annotations

import copy
import xml.etree.ElementTree as ETW  # stdlib "ET Write" -- used only to build/serialize
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from maptasker.src.primitem import RunState

from maptasker.src import appinv, sessundo
from maptasker.src.actionc import action_codes
from maptasker.src.sysconst import SCENE_TASK_TYPES
from maptasker.src.taskedit import (
    apply_arg_values,
    build_editable_args,
    build_synthesized_args,
    classify_action_addability,
    validate_arg_values,
)

# Tasker's own "not laid out for this orientation": what a Scene's size children and a
# <geom>'s half hold when an orientation has no layout.  Every V2 Scene carries it in all
# four size children too -- see sceneedit.NEW_SCENE_WIDTH_PORTRAIT and create_new_scene.
UNSET_DIMENSION = "-1"


# --------------------------------------------------------------------------------------
# Legacy designer, phase 1: select an element on the canvas, inspect it, move and resize it.
#
# The V2 designer's counterpart, and shaped by the one difference that matters: a V2 layout
# is a tree with no coordinates, so its editor is a tree; a Legacy Scene is a pixel canvas
# where every element carries its own <geom>, so its editor is that canvas.  What is here is
# therefore geometry and properties -- not structure.  Adding, deleting, restacking and
# renaming are phase 2 and 3 (see the design sketch), and nothing below can change how many
# elements a Scene has or what they are called.
#
# The property side costs almost nothing, because the schema already ships: an element's
# arguments are <Int sr="argN">/<Str sr="argN"> children, which is the *identical* structure
# a Task Action's arguments use, and taskedit.build_editable_args already turns that plus an
# actionc.action_codes entry into a list of typed, widget-classified fields.  It is documented
# as depending only on that structure rather than on being a Task Action -- profedit already
# reuses it for Profile conditions -- so a Scene element is the third caller, not a special
# case.  Reusing it also means dropdowns, checkboxes and the %variable fallback behave the
# same everywhere in this app, and that a new argument added to actionc.py appears in the
# Scene inspector without anything here changing.
#
# Same in-place discipline as the V2 half: mutate the elements a Scene already has, never
# rebuild them, so an untouched Scene serializes byte-identically.
# --------------------------------------------------------------------------------------

# <geom> is eight comma-separated numbers -- the portrait x,y,w,h then the landscape x,y,w,h
# (see sceneview.element_geometry, which is the read side of this and the one place that
# parses it for drawing).  -1 across a half means "not laid out for this orientation".
LEGACY_GEOM_VALUES = 8


def legacy_element_at(
    scene_element: Element,
    sr: str,
) -> Element | None:
    """The element with this sr ("elements3"), or None.

    Selection is held as an sr string rather than as a reference to the element, for the
    reason the V2 designer holds a path rather than a node: the panes are rebuilt on every
    change, and an sr survives that -- as it survives an Undo, which replaces the Scene's
    children wholesale with a restored copy.
    """
    if not sr:
        return None
    return next((child for child in scene_element if child.get("sr") == sr), None)


def legacy_element_label(element: Element) -> str:
    """ "Text 'Done!'" -- how an element reads in the designer's list.

    Its own name (arg0) if it has one, in the same quoted style v2_node_label uses, so the
    two designers name things the same way.  Falling back to the type alone is right rather
    than inventing a placeholder: an unnamed element genuinely has no name, and Tasker will
    show it that way too.
    """
    element_type = element.tag.replace("Element", "")
    name_element = element.find("Str[@sr='arg0']")
    name = (name_element.text or "").strip() if name_element is not None else ""
    return f"{element_type} '{name}'" if name else element_type


def legacy_element_args(element: Element, state: RunState) -> list:
    """The element's editable arguments, as taskedit.EditableArg records.

    Empty for an element type actionc.py has no entry for -- a type from a newer Tasker.
    That is deliberately not the same as "no fields": the designer says so, and the element
    is still selectable and still movable, because its geometry is in <geom> and needs no
    schema at all.  Losing the ability to reposition an element this app cannot describe
    would be a much worse answer than showing it with an empty property sheet.
    """
    action_code = action_codes.get(element.tag)
    if action_code is None:
        return []
    return build_editable_args(element, action_code.args, state=state)


# ---- Legacy colour arguments ---------------------------------------------------------
# A Legacy element writes its colours as #AARRGGBB -- alpha FIRST -- and CSS reads that same
# string as #RRGGBBAA, so the two orders are not a near miss: handing "#77333333" straight to
# a colour picker offers a grey at 20% where the Scene has one at 47%, and taking the picker's
# answer back unconverted would store a colour whose transparency came from its red channel.
# (sceneview.tasker_colour is the read-only half of this, and says the same thing at length.)
#
# The V2 half needs none of this: a V2 Scene writes ordinary CSS-ordered #RRGGBB.
_LEGACY_COLOUR_LENGTH = 9
_LEGACY_OPAQUE = "FF"
_LEGACY_COLOUR_NAMES = ("color", "colour")


def legacy_is_colour_arg(arg: object) -> bool:
    """Whether this element argument holds a colour, and can be typed into.

    Decided by the argument's name -- "Text Color", "Border XColor", "Background_Color" --
    because that is the only place actionc.py says so: its arg types are the storage kinds
    (Str, Int), and a colour is stored as a Str like any other string.

    A readonly argument stays readonly.  An element type this app has no table for has no
    arguments here at all, so it never reaches this.
    """
    name = str(getattr(arg, "arg_name", "")).lower()
    return getattr(arg, "widget_kind", "") == "text" and any(word in name for word in _LEGACY_COLOUR_NAMES)


def legacy_colour_to_css(value: str) -> str:
    """Tasker's #AARRGGBB as the CSS a colour picker understands: the same digits with the
    alpha moved from the front to the back.

    A fully opaque colour comes back as plain #RRGGBB rather than #RRGGBBFF, because that is
    the form the picker's swatch can preview -- and #FFFFFFFF and #FF000000 are between them
    most of the colours in a real backup.

    Anything that is not one of Tasker's nine characters -- a %variable, an empty argument, a
    colour some other Tasker wrote -- comes back untouched, to be shown as it is rather than
    reinterpreted.
    """
    text = value.strip()
    if len(text) != _LEGACY_COLOUR_LENGTH or not text.startswith("#"):
        return text
    try:
        int(text[1:], 16)
    except ValueError:
        return text
    alpha, rgb = text[1:3].upper(), text[3:].upper()
    return f"#{rgb}" if alpha == _LEGACY_OPAQUE else f"#{rgb}{alpha}"


def legacy_colour_from_css(value: str) -> str:
    """The way back: CSS's #RRGGBB or #RRGGBBAA as Tasker's #AARRGGBB, with a colour that
    states no alpha stored as fully opaque.

    Anything that is not a CSS hex colour is passed through unchanged rather than mangled into
    one -- a %variable in a colour argument is a perfectly ordinary thing for a Scene to hold,
    and it is not this function's business to decide it was a mistake.
    """
    text = value.strip()
    if not text.startswith("#"):
        return text
    body = text[1:]
    try:
        int(body, 16)
    except ValueError:
        return text
    if len(body) == 3:
        body = "".join(digit * 2 for digit in body)
    if len(body) == 6:
        return f"#{_LEGACY_OPAQUE}{body}".upper()
    if len(body) == 8:
        return f"#{body[6:]}{body[:6]}".upper()
    return text


def legacy_validate_arg(arg: object, value: str) -> list[str]:
    """Whether this value may be written to this argument -- taskedit's own rule, so the
    Scene inspector rejects exactly what the Task editor rejects and with the same words.
    """

    return validate_arg_values([arg], lambda _arg: "value", {"value": str(value)})


def legacy_set_arg(arg: object, value: str) -> None:
    """Write one inspector field back onto the XML element behind it.

    Goes through taskedit.apply_arg_values rather than setting the attribute here, so the
    per-widget write rules stay in exactly one place: a checkbox writes val="1"/"0", a
    dropdown writes the *index* of the chosen label and not the label, a variable-backed Int
    writes into its <var> child rather than its val attribute.  Reimplementing those four
    lines here is how the Scene inspector and the Task editor would start disagreeing about
    what a dropdown means.

    Caller validates first (legacy_validate_arg); this assumes a well-formed value, exactly
    as apply_arg_values does for its own callers.
    """

    apply_arg_values([arg], lambda _arg: "value", {"value": str(value)})


def legacy_geometry_values(element: Element) -> list[str]:
    """The eight raw <geom> numbers, padded if the element carries fewer.

    Padded rather than rejected because the padding is only ever written back for an element
    that already had a <geom> -- and a short one is still describing a real portrait box that
    the user is entitled to move.
    """
    geom = element.find("geom")
    if geom is None:
        return []
    values = [value.strip() for value in (geom.text or "").split(",")]
    return values + [UNSET_DIMENSION] * (LEGACY_GEOM_VALUES - len(values)) if values else []


def legacy_set_geometry(
    element: Element,
    box: tuple[int, int, int, int],
    *,
    landscape: bool = False,
) -> None:
    """Write one orientation's x,y,w,h back into <geom>, leaving the other half alone.

    The other half matters: the two orientations share one element, so a drag in portrait
    must not disturb a landscape layout somebody laid out by hand -- and for the great
    majority of Scenes that other half is -1,-1,-1,-1, which has to survive as -1 rather
    than becoming a real number the Scene never had.

    Never creates a <geom>.  An element without one is not drawn on the canvas and cannot be
    selected (see sceneview.paint_order), so being asked to move one means something else is
    wrong; writing a geometry onto an element Tasker deliberately left without one would be
    inventing a layout.
    """
    geom = element.find("geom")
    if geom is None:
        return
    values = legacy_geometry_values(element)
    if not values:
        return
    offset = 4 if landscape else 0
    values[offset : offset + 4] = [str(int(number)) for number in box]
    geom.text = ",".join(values)


def legacy_snapshot(scene_element: Element) -> Element:
    """A deep copy of the whole Scene, for the designer's undo stack.

    The whole Scene rather than the one element being changed, and for the same reason the
    V2 designer snapshots its whole tree: it is affordable at this size (the largest Legacy
    Scene in this repo's sample data has 42 elements) and far simpler than modelling an
    inverse for every operation -- which is what phases 2 and 3, where an edit can touch
    several elements' sr attributes at once, would otherwise need.
    """
    return copy.deepcopy(scene_element)


def legacy_restore(
    scene_element: Element,
    snapshot: Element,
) -> None:
    """Put a snapshot back, in place.

    Replaces the live element's children and attributes rather than rebinding it, because
    EditableScene, the dialog's field_refs and the save path all hold *this* element object;
    swapping in the copy would leave every one of them editing something that is no longer
    going to be saved.  The V2 designer does the same thing to its layout dict, for the same
    reason.
    """
    scene_element[:] = list(snapshot)
    scene_element.attrib.clear()
    scene_element.attrib.update(snapshot.attrib)
    scene_element.text = snapshot.text


# --------------------------------------------------------------------------------------
# Legacy designer, phase 2: changing what a Scene contains -- add, delete, duplicate and
# restack its elements.
#
# Phase 1 could move and retype what was already there; nothing in it changed the element
# count. This does, and that brings in two constraints phase 1 never had to meet:
#
#   sr IS THE Z-ORDER AND IT MUST STAY CONTIGUOUS.  An element's sr="elementsN" is both its
#   key and its paint order -- elements0 is drawn first and therefore sits at the bottom --
#   and every one of the 350 Legacy Scenes in this repo's sample data numbers them 0..N-1
#   with no gaps.  So there is no such thing as adding or deleting one element: every
#   operation here renumbers the whole list and rewrites the XML in the new order, which is
#   also why each returns the sr the element ended up with rather than the one it started
#   with (see _legacy_reindex).
#
#   NAMES ARE UNIQUE, AND TASKS DEPEND ON THEM.  18 Task action codes reach into a Scene and
#   address an element by its name (LEGACY_ELEMENT_ACTION_CODES), and no Scene in the sample
#   data has two elements sharing one -- so a new or duplicated element has to be given a
#   name nobody else is using, and a deletion has to say which Tasks were relying on the one
#   going away (find_element_name_references).
#
# What a new element is made of is read off the sample data rather than invented: which types
# carry a ve attribute and which value (LEGACY_VE_BY_TYPE -- 100% consistent per type across
# 2,186 elements), what Tasker names a new one (LEGACY_DEFAULT_NAME), and that an Img-typed
# argument is always written even when it holds no image.  <flags> is deliberately NOT
# written: 75 real elements carry a <geom> and no <flags> at all, so its absence is a state
# Tasker itself produces -- and absence is not the same as 0, which would mark the new
# element invisible (objprops' SCENE_ELEMENT_VISIBLE_BIT, and sceneview.element_is_hidden on
# why the two cases are read differently).
# --------------------------------------------------------------------------------------

# The ve attribute a new element of each type carries.  Every type in the sample data is
# entirely consistent about this -- all 897 TextElements are ve="3", all 167 ImageElements
# are ve="2", all 265 RectElements have none -- so these are transcribed, not chosen.
# A type absent from here gets no ve attribute, which is what those types do.
LEGACY_VE_BY_TYPE: dict[str, str] = {
    "ButtonElement": "3",
    "EditTextElement": "3",
    "TextElement": "3",
    "ImageElement": "2",
    "SceneElement": "2",
    "WebElement": "2",
}

# What Tasker calls a new element of each type, before the user renames it -- taken from the
# names in the sample data that still match Tasker's own "<prefix><number>" pattern.  Two are
# worth noting because they are not the type name: an EditTextElement is a "TextEdit", and a
# SceneElement -- Tasker's Map element, despite the tag -- is a "Map".
LEGACY_DEFAULT_NAME: dict[str, str] = {
    "ButtonElement": "Button",
    "CheckBoxElement": "Checkbox",
    "DoodleElement": "Doodle",
    "EditTextElement": "TextEdit",
    "ImageElement": "Image",
    "ListElement": "Menu",
    "OvalElement": "Oval",
    "PickerElement": "Number Picker",
    "RectElement": "Rectangle",
    "SceneElement": "Map",
    "SliderElement": "Slider",
    "SpinnerElement": "Spinner",
    "SwitchElement": "Switch",
    "TextElement": "Text",
    "ToggleElement": "Toggle",
    "VideoElement": "Video",
    "WebElement": "WebView",
}


@dataclass(frozen=True)
class LegacyPaletteEntry:
    """One element the Add Element dialog offers."""

    element_type: str
    label: str
    group: str
    description: str


# The groups the Add Element dialog sorts the palette into.
#
# UNLIKE THE VERSION 2 PALETTE, THIS GROUPING IS THIS APP'S OWN.  V2_PALETTE_GROUPS was
# adopted from a screenshot of Tasker's own Add Element sheet, so it could be said to be the
# arrangement the user already knows; no such evidence exists for the Legacy editor's sheet,
# and claiming it would be dressing up a guess.  The labels and types below are real -- only
# the four headings they are filed under are a convenience.
LEGACY_PALETTE_GROUPS = ("Text", "Shapes", "Input", "Media")

LEGACY_PALETTE: tuple[LegacyPaletteEntry, ...] = (
    LegacyPaletteEntry("TextElement", "Text", "Text", "A run of text. Accepts %variables."),
    LegacyPaletteEntry("ButtonElement", "Button", "Text", "A labelled button, with an optional icon."),
    LegacyPaletteEntry("EditTextElement", "Text Edit", "Text", "A field the user types into."),
    LegacyPaletteEntry("ToggleElement", "Toggle", "Text", "A two-state button with its own on and off labels."),
    LegacyPaletteEntry(
        "RectElement",
        "Rectangle",
        "Shapes",
        "A filled or outlined rectangle, with optional rounded corners.",
    ),
    LegacyPaletteEntry("OvalElement", "Oval", "Shapes", "A filled or outlined ellipse."),
    LegacyPaletteEntry("CheckBoxElement", "Checkbox", "Input", "A tick box."),
    LegacyPaletteEntry("SwitchElement", "Switch", "Input", "An on/off switch."),
    LegacyPaletteEntry("SliderElement", "Slider", "Input", "A slider between a minimum and a maximum."),
    LegacyPaletteEntry("PickerElement", "Number Picker", "Input", "A number spinner between a minimum and a maximum."),
    LegacyPaletteEntry("SpinnerElement", "Spinner", "Input", "A drop-down list, filled from a Tasker variable."),
    LegacyPaletteEntry("ListElement", "Menu", "Input", "A scrolling list, filled from a Tasker variable."),
    LegacyPaletteEntry("ImageElement", "Image", "Media", "A built-in Tasker icon or an image file on the device."),
    LegacyPaletteEntry("DoodleElement", "Doodle", "Media", "A freehand drawing surface."),
    LegacyPaletteEntry("WebElement", "Web", "Media", "An embedded web page, a local file, or HTML written inline."),
    LegacyPaletteEntry("SceneElement", "Map", "Media", "A map, with optional traffic, satellite and road overlays."),
    LegacyPaletteEntry("VideoElement", "Video", "Media", "A video player."),
)

# Task action codes that address a Legacy Scene's element by name: Element Text, Element
# Position, Element Size, Element Back Colour and the rest.  Bare digits, matching what a
# Task's <code> holds -- actionc.py keys the same actions "50t"/"612t".
#
# Confirmed by reading actionc.action_codes: each of these declares a "Scene Name" argument
# and an "Element" argument, which is what makes a rename or a delete here able to break a
# Task somewhere else in the backup.
LEGACY_ELEMENT_ACTION_CODES = (
    "50",
    "51",
    "53",
    "54",
    "55",
    "56",
    "57",
    "58",
    "60",
    "63",
    "64",
    "66",
    "67",
    "68",
    "71",
    "73",
    "195",
    "612",
)

# Element Visibility (code 65) is deliberately NOT in that list.  Its argument is an "Element
# Match" *pattern* rather than a name, so a Task that hides "Text*" depends on an element
# this app could rename or delete without its name ever appearing in that Task.  It is
# reported separately and never rewritten -- guessing at a glob is how a working Scene gets
# broken invisibly.
LEGACY_ELEMENT_MATCH_CODES = ("65",)


def find_element_name_references(scene_name: str, element_name: str, state: RunState) -> list[str]:
    """Tasks whose actions address this element by name, as readable descriptions.

    The Legacy sibling of find_component_id_references, and matched the same way and for the
    same reasons: an action naming *both* this Scene and this element in any of its string
    arguments, compared case-insensitively.  Position-independent because the two arguments
    do not sit at fixed indexes across all 18 codes, and case-insensitive because Tasker
    itself resolves a Scene named with different capitalisation (see the note on the V2
    version, which found a real instance of that in this repo's own backup).

    The cost is theoretical false positives -- a Task that names both strings coincidentally
    -- which is the right way round for a warning shown before a destructive edit.
    """
    if not scene_name or not element_name:
        return []

    wanted_scene = scene_name.strip().casefold()
    wanted_element = element_name.strip().casefold()

    references = []
    for entry in state.tasker_root_elements.get("all_tasks", {}).values():
        task_element = entry["xml"]
        task_name = task_element.findtext("nme") or f"Task {task_element.findtext('id', '?')}"
        for action in task_element.findall("Action"):
            if action.findtext("code") not in LEGACY_ELEMENT_ACTION_CODES:
                continue
            values = {(child.text or "").strip().casefold() for child in action.findall("Str")}
            if wanted_scene in values and wanted_element in values:
                references.append(task_name)
                break
    return sorted(set(references))


def find_element_match_references(scene_name: str, state: RunState) -> list[str]:
    """Tasks that address this Scene's elements by a match *pattern* (Element Visibility).

    Reported wholesale for the Scene rather than per element, because that is as precise as
    the truth allows: the pattern is evaluated by Tasker against whatever elements exist when
    it runs, so whether it currently matches the one being deleted is not something this app
    can answer without implementing Tasker's own globbing.  Naming the Tasks and leaving the
    judgement to the user is the honest form of that warning.
    """
    if not scene_name:
        return []

    wanted_scene = scene_name.strip().casefold()
    references = []
    for entry in state.tasker_root_elements.get("all_tasks", {}).values():
        task_element = entry["xml"]
        task_name = task_element.findtext("nme") or f"Task {task_element.findtext('id', '?')}"
        for action in task_element.findall("Action"):
            if action.findtext("code") not in LEGACY_ELEMENT_MATCH_CODES:
                continue
            if wanted_scene in {(child.text or "").strip().casefold() for child in action.findall("Str")}:
                references.append(task_name)
                break
    return sorted(set(references))


def legacy_can_add(element_type: str) -> str:
    """ "" if this element type can be created, otherwise the reason it cannot.

    The reason is always the same one, and it is a real limit rather than a placeholder:
    actionc.py has no argument table for the type, so this app does not know what arguments
    Tasker expects it to carry.  Writing an element with the arguments missing or invented is
    how a Scene stops opening in Tasker, so the palette offers the type, greys it out, and
    says why -- the same treatment v2_can_add gives a component that cannot go where it is
    being put.  VideoElement is the one type in this position today.
    """
    if element_type in action_codes:
        return ""
    return (
        "MapTasker has no argument table for this element type, so it cannot be created "
        "without inventing what Tasker expects it to contain."
    )


def _legacy_effective_args(element_type: str) -> list:
    """The argument definitions to build this element type from.

    An entry's `redirect` names another entry to borrow arguments from, and is followed when
    it resolves -- but SceneElement's says "Map", which is not a key in the table.  It also
    carries a full set of arguments of its own (Lat/Long, Zoom, Show Traffic, ...), so the
    redirect is a dangling label rather than a missing definition, and following it blindly
    is an exception where taking the entry at its word works.  Hence: use the target when it
    exists, the entry itself when it does not.
    """
    action_code = action_codes[element_type]
    target = action_codes.get(action_code.redirect) if action_code.redirect else None
    return target.args if target is not None else action_code.args


def legacy_element_names(scene_element: Element) -> set[str]:
    """Every element name currently in the Scene -- what uniqueness is checked against."""
    names = set()
    for child in scene_element:
        if not child.tag.endswith("Element") or child.tag == "PropertiesElement":
            continue
        name_element = child.find("Str[@sr='arg0']")
        if name_element is not None and name_element.text:
            names.add(name_element.text.strip())
    return names


def legacy_next_element_name(scene_element: Element, element_type: str) -> str:
    """A free name for a new element of this type: "Text1", "Text2", ...

    The stem is what Tasker itself names a new one (LEGACY_DEFAULT_NAME), so a Scene built
    here reads like a Scene built in Tasker.  Uniqueness is not cosmetic: 18 Task action
    codes address an element by name, and two elements sharing one makes every one of them
    ambiguous -- which is presumably why no Scene in the sample data has a duplicate.
    """
    stem = LEGACY_DEFAULT_NAME.get(element_type, element_type.replace("Element", "") or "Element")
    taken = legacy_element_names(scene_element)
    index = 1
    while f"{stem}{index}" in taken:
        index += 1
    return f"{stem}{index}"


def legacy_drawable_elements(scene_element: Element) -> list:
    """The Scene's elements in paint order, bottom first -- the same rule and the same order
    sceneview.paint_order draws them in, kept here so the model can reorder them without the
    editing half having to import the drawing half.
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


def _legacy_reindex(scene_element: Element, ordered: list) -> None:
    """Renumber this list of elements elements0..N-1, in place.

    Renumbering only.  The elements are deliberately NOT moved to match their new order in
    the file, and that is a correction to what this function first did: it reordered them
    physically, on the assumption that Tasker writes its elements in sr order.

    IT DOES NOT.  53 of the 350 Legacy Scenes in this repo's sample data have a document
    order that disagrees with their sr order -- so sr is authoritative and the position in
    the file carries no meaning, which is exactly what sceneview.paint_order already assumed
    when it sorted by sr rather than trusting the document.  Reordering them here would have
    rewritten a seventh of every backup this app touched, for a change nothing reads.

    The consequence worth stating: after a restack the file's element order and its z-order
    disagree, which looks wrong in a diff and is not.  It is the same state Tasker leaves
    those 53 Scenes in.
    """
    for offset, element in enumerate(ordered):
        element.set("sr", f"elements{offset}")


def _legacy_order_arg_children(element: Element) -> None:
    """Put an element's argument children back into argument order.

    Needed because the Img-typed arguments are written separately from the Int/Str ones (see
    legacy_new_element), which would otherwise leave an ImageElement carrying arg0, arg2,
    arg1.  Tasker addresses arguments by their sr and would not care, but a file this app
    writes should be indistinguishable from one Tasker wrote -- and a diff against a Scene
    that was only moved should not show its arguments shuffled.
    """
    args = [child for child in element if child.tag in ("Str", "Int", "Img")]

    def order(child: Element) -> int:
        sr = child.get("sr", "")
        digits = sr[len("arg") :] if sr.startswith("arg") else ""
        return int(digits) if digits.isdigit() else 1_000

    for child in args:
        element.remove(child)
    for child in sorted(args, key=order):
        element.append(child)


def legacy_new_element(
    scene_element: Element,
    element_type: str,
    box: tuple[int, int, int, int],
    state: RunState,
    *,
    landscape: bool = False,
) -> Element | str:
    """Build a new element of this type, sized and placed at `box`, ready to be inserted.

    Returns the element, or a reason string if the type cannot be created (legacy_can_add).

    Its arguments are synthesized from actionc.py's own table by taskedit.build_synthesized_args
    -- the same function that builds a brand-new Task Action's arguments and a brand-new
    Profile condition's, so a Scene element gets exactly the defaults those get.  The one
    thing it does not write is an Img-typed argument, which it classifies as uneditable and
    skips; those are added here as the empty <Img ve="2"/> that every Button, Image and
    Slider in the sample data carries, because "no icon" is stored as an empty Img and not as
    a missing one.

    `landscape` says whether the Scene has a landscape layout of its own.  When it does, the
    new element is given the same box in both orientations rather than -1,-1,-1,-1: an
    element that exists in portrait and is absent in landscape is a stranger thing to create
    on purpose than one that starts in the same place in both, and the landscape half can be
    dragged somewhere else the moment the designer is switched to it.
    """

    reason = legacy_can_add(element_type)
    if reason:
        return reason

    element_cls = type(scene_element)
    attributes = {"sr": "elements0"}  # replaced by _legacy_reindex on insert.
    version = LEGACY_VE_BY_TYPE.get(element_type)
    if version:
        attributes["ve"] = version
    element = element_cls(element_type, attributes)

    x, y, width, height = (int(value) for value in box)
    geometry = element_cls("geom")
    landscape_half = f"{x},{y},{width},{height}" if landscape else "-1,-1,-1,-1"
    geometry.text = f"{x},{y},{width},{height},{landscape_half}"
    element.append(geometry)

    effective_args = _legacy_effective_args(element_type)
    build_synthesized_args(element_cls, element, effective_args, state=state)

    for argument in effective_args:
        if argument.arg_type != "8":
            continue
        if element.find(f"Img[@sr='arg{argument.arg_id}']") is None:
            element.append(element_cls("Img", {"sr": f"arg{argument.arg_id}", "ve": "2"}))
    _legacy_order_arg_children(element)

    name_element = element.find("Str[@sr='arg0']")
    if name_element is not None:
        name_element.text = legacy_next_element_name(scene_element, element_type)
    return element


def legacy_insert_element(
    scene_element: Element,
    element: Element,
    at: int | None = None,
) -> str:
    """Put an element into the Scene and return the sr it ended up with.

    Appended at the top of the z-order by default, which is where a newly added element
    belongs: anything else would create it underneath something and look like it had not been
    created at all.

    Physically it goes in front of <PropertiesElement>, which is the only child whose
    position in the file is worth respecting -- every Scene in the sample data that has one
    keeps it last.  Where the element lands relative to its siblings does not matter, since
    sr is what carries the order (see _legacy_reindex).
    """
    ordered = legacy_drawable_elements(scene_element)
    position = len(ordered) if at is None else max(0, min(at, len(ordered)))

    properties = scene_element.find("PropertiesElement")
    if properties is None:
        scene_element.append(element)
    else:
        scene_element.insert(list(scene_element).index(properties), element)

    ordered.insert(position, element)
    _legacy_reindex(scene_element, ordered)
    return f"elements{position}"


def legacy_delete_element(scene_element: Element, sr: str) -> str:
    """Remove an element and renumber what is left.  Returns the sr to select next -- the
    element that took its place in the stack, or the new top one, or "" for an empty Scene.

    Selecting something afterwards rather than nothing is deliberate: a delete is usually one
    of several, and being dropped back to "select an element" between each would make a run
    of them needlessly slow.
    """
    ordered = legacy_drawable_elements(scene_element)
    element = next((candidate for candidate in ordered if candidate.get("sr") == sr), None)
    if element is None:
        return ""

    position = ordered.index(element)
    ordered.remove(element)
    scene_element.remove(element)
    _legacy_reindex(scene_element, ordered)
    if not ordered:
        return ""
    return f"elements{min(position, len(ordered) - 1)}"


def legacy_duplicate_element(scene_element: Element, sr: str) -> str:
    """Copy an element, name the copy, and put it directly above the original.  Returns the
    copy's sr, or "" if there was nothing at `sr`.

    Directly above rather than at the top of the stack, so the copy lands next to the thing
    it was copied from, and the two overlap exactly the way duplicating usually intends.

    The copy keeps whatever Tasks the original fires -- a duplicated button that does nothing
    would be a surprise -- but it does not keep its name: element names are how 18 Task action
    codes find an element, and two elements answering to one name makes every one of those
    actions ambiguous.
    """
    ordered = legacy_drawable_elements(scene_element)
    element = next((candidate for candidate in ordered if candidate.get("sr") == sr), None)
    if element is None:
        return ""

    copy_of_element = copy.deepcopy(element)
    name_element = copy_of_element.find("Str[@sr='arg0']")
    if name_element is not None:
        name_element.text = legacy_next_element_name(scene_element, element.tag)
    return legacy_insert_element(scene_element, copy_of_element, ordered.index(element) + 1)


def legacy_restack(scene_element: Element, sr: str, position: int) -> str:
    """Move an element to this position in the z-order -- 0 is the bottom -- and return the
    sr it ended up with, or "" if it did not move.

    One function for all four of Forward, Backward, To Front and To Back, because they differ
    only in the position they ask for; the caller works that out from where the element
    currently is, and this clamps it.  The returned sr is what the caller re-selects with,
    since renumbering has just changed it.
    """
    ordered = legacy_drawable_elements(scene_element)
    element = next((candidate for candidate in ordered if candidate.get("sr") == sr), None)
    if element is None:
        return ""

    current = ordered.index(element)
    target = max(0, min(position, len(ordered) - 1))
    if target == current:
        return ""

    ordered.remove(element)
    ordered.insert(target, element)
    _legacy_reindex(scene_element, ordered)
    return f"elements{target}"


# --------------------------------------------------------------------------------------
# Legacy designer, phase 3: the parts of an element that reach outside it.
#
# Phases 1 and 2 stayed inside the Scene -- geometry, properties, and which elements exist.
# Everything here crosses a boundary:
#
#   RENAMING reaches into other Tasks.  An element's name is how 18 Task action codes find
#   it, so a rename either brings them along or silently breaks them.  This offers to bring
#   them -- and defers the rewrite to the moment the Scene is actually saved, because the
#   Scene being edited is a deep copy that Cancel discards while the Tasks are the live ones
#   (see EditableScene.element_renames).
#
#   TASK BINDINGS are the Tasks.  <clickTask>213</clickTask> is a Task id, and 199 of the
#   1,472 bindings in this repo's sample data are *negative* -- Tasker's anonymous inline
#   Tasks, which exist nowhere else and have no name.  Those are shown and preserved and
#   never offered for rebinding: replacing one orphans a Task that cannot be recovered.
#
#   THE BACKGROUND is a whole RectElement living inside another element, and is where most
#   of a real Scene's colour is.  Only some types have one -- Button, Rect, Oval, Spinner,
#   Toggle, Doodle, Map and Video never do in any of the 2,186 sample elements -- so it is
#   offered only where Tasker itself puts one.
#
#   THE SCENE'S PROPERTIES describe the Scene rather than any element: how it is put on
#   screen, which way up, its background, its title.  66 of 366 sample Scenes have no
#   <PropertiesElement> at all, so its absence is ordinary and gets an offer to create one
#   rather than an error.
# --------------------------------------------------------------------------------------

# Which Task-binding tags each element type is offered, taken from what the sample data
# actually uses -- a Text can be tapped, long-tapped and stroked; a Checkbox only reports a
# change; a Web element reports link clicks and page loads.  sysconst.SCENE_TASK_TYPES names
# all fifteen tags Tasker has; these are the ones each type is observed to carry, so the
# editor offers a short real list rather than a long speculative one.
#
# A tag an element already carries is always offered for that element even if it is not
# listed here (see legacy_task_tags_for), so a Scene from a newer Tasker keeps whatever it
# came with.
LEGACY_TASK_TAGS_BY_TYPE: dict[str, tuple[str, ...]] = {
    # The Scene's own properties, not one of its elements.  Tasker's Scene Properties screen
    # calls these its Event tabs, and there are exactly three of them -- Key, Home Tap and
    # Tab Tap (see LEGACY_SCENE_EVENTS below, which is the table with the labels and the
    # rules on it).  All three are listed so the Scene Properties dialog can OFFER one to a
    # Scene that has none: without an entry here legacy_task_tags_for returns only what is
    # already present, which would make the tab read-only in exactly the case someone wants
    # it.
    #
    # <itemselectedTask> means something ELSE on a SpinnerElement below -- "Item Selected",
    # which is what sysconst.SCENE_TASK_TYPES calls it.  The tag is the same; what fires it
    # is not, which is why the Scene Properties dialog labels these from
    # LEGACY_SCENE_EVENTS rather than from that shared table.
    "PropertiesElement": ("keyTask", "iconclickTask", "itemselectedTask"),  # LEGACY_SCENE_EVENTS
    "ButtonElement": ("clickTask", "longclickTask"),
    "CheckBoxElement": ("checkchangeTask",),
    "EditTextElement": ("valueselectedTask",),
    "ImageElement": ("clickTask", "longclickTask"),
    "ListElement": ("itemclickTask", "itemlongclickTask"),
    "OvalElement": ("clickTask", "longclickTask"),
    "PickerElement": ("valueselectedTask",),
    "RectElement": ("clickTask", "longclickTask", "strokeTask"),
    "SliderElement": ("valueselectedTask",),
    "SpinnerElement": ("itemselectedTask",),
    "SwitchElement": ("checkchangeTask",),
    "TextElement": ("clickTask", "longclickTask", "strokeTask"),
    "ToggleElement": ("clickTask",),
    "WebElement": ("linkclickTask", "pageloadedTask"),
}

# Element types Tasker gives a <RectElement sr="background"> to.  Transcribed from the
# sample data: every CheckBox and every Switch has one, most Texts and EditTexts do, and the
# eight types absent from here have one in none of the 2,186 elements.
LEGACY_BACKGROUND_TYPES = frozenset(
    {
        "CheckBoxElement",
        "EditTextElement",
        "ImageElement",
        "ListElement",
        "PickerElement",
        "SliderElement",
        "SwitchElement",
        "TextElement",
        "WebElement",
    },
)

# An anonymous inline Task -- Tasker writes these with a negative id and stores them nowhere
# else.  scenes.process_tasks calls them "fake" and skips them for the same reason.
LEGACY_ANONYMOUS_TASK_PREFIX = "-"

# The three bindings a Scene's own <PropertiesElement> carries -- Tasker's Event tabs.
# Named here rather than spelled out at each use so the Scene Properties dialog,
# LEGACY_SCENE_EVENTS and LEGACY_TASK_TAGS_BY_TYPE above cannot drift apart over a string.
LEGACY_KEY_TASK_TAG = "keyTask"
LEGACY_HOME_TAP_TASK_TAG = "iconclickTask"
LEGACY_TAB_TAP_TASK_TAG = "itemselectedTask"


@dataclass(frozen=True)
class LegacyBinding:
    """One Task an element fires: which event, which Task, and whether it is one that can be
    changed.
    """

    tag: str
    label: str
    task_id: str
    task_name: str
    anonymous: bool


def legacy_task_tags_for(element: Element) -> list[str]:
    """The Task-binding tags to offer for this element: the ones its type is observed to
    use, plus any it already carries that the table has not heard of.

    The second half is the forward-compatible bit, and the same rule v2_container_slots
    follows: an element from a newer Tasker keeps whatever bindings it arrived with, and they
    stay editable, rather than the editor deciding they do not exist.
    """
    known = list(LEGACY_TASK_TAGS_BY_TYPE.get(element.tag, ()))
    present = [child.tag for child in element if child.tag in SCENE_TASK_TYPES and child.tag not in known]
    return known + present


def legacy_task_bindings(element: Element, state: RunState) -> list[LegacyBinding]:
    """Every Task this element currently fires, resolved to names where it can be.

    A binding whose id is not in the loaded backup is reported under its id rather than
    dropped -- it is still what the Scene will run, and hiding it would make the Tasks
    section disagree with the file.
    """
    all_tasks = state.tasker_root_elements.get("all_tasks", {})
    bindings = []
    for child in element:
        if child.tag not in SCENE_TASK_TYPES:
            continue
        task_id = (child.text or "").strip()
        anonymous = task_id.startswith(LEGACY_ANONYMOUS_TASK_PREFIX)
        entry = all_tasks.get(task_id)
        if anonymous:
            name = "(anonymous Task, stored in the Scene)"
        elif entry:
            name = entry["name"]
        else:
            name = f"Task {task_id}"
        bindings.append(
            LegacyBinding(
                tag=child.tag,
                label=SCENE_TASK_TYPES.get(child.tag, child.tag),
                task_id=task_id,
                task_name=name,
                anonymous=anonymous,
            ),
        )
    return bindings


def _legacy_insert_ordered_child(
    element: Element,
    child: Element,
) -> None:
    """Put a lowercase-tagged child (a Task binding, <geom>, <flags>) where Tasker puts it.

    Tasker writes an element's lowercase children in alphabetical order and its capitalised
    argument children (Str/Int/Img) after all of them -- "clickTask, flags, geom,
    longclickTask, Str arg0, ..." is the order every sample element is in.  Appending would
    put a new binding after the arguments, which no Tasker file does.
    """
    for index, existing in enumerate(element):
        if existing.tag[:1].isupper() or existing.tag > child.tag:
            element.insert(index, child)
            return
    element.append(child)


def legacy_set_task_binding(
    element: Element,
    tag: str,
    task_id: str,
) -> None:
    """Point one of this element's events at this Task, adding the child if it has none."""
    existing = element.find(tag)
    if existing is not None:
        existing.text = str(task_id)
        return
    child = type(element)(tag)
    child.text = str(task_id)
    _legacy_insert_ordered_child(element, child)


def legacy_clear_task_binding(element: Element, tag: str) -> None:
    """Stop this element firing anything on this event."""
    child = element.find(tag)
    if child is not None:
        element.remove(child)


def legacy_task_choices(state: RunState) -> list[str]:
    """Every Task name in the loaded backup, sorted -- what a binding can be pointed at.

    The same list the Task editor's own 'Perform Task' picker offers
    (taskedit.get_all_task_names), so the two never disagree about what exists.
    """
    return sorted(state.tasker_root_elements.get("all_tasks_by_name", {}))


def legacy_task_id_for_name(task_name: str, state: RunState) -> str:
    """The id of the Task with this name, or "" -- how a picked name becomes what the XML
    stores.
    """
    entry = state.tasker_root_elements.get("all_tasks_by_name", {}).get(task_name)
    return str(entry["id"]) if entry else ""


def legacy_background(element: Element) -> Element | None:
    """The element's <RectElement sr="background">, or None."""
    return element.find("RectElement[@sr='background']")


def legacy_can_have_background(element: Element) -> bool:
    """Whether Tasker gives this element type a background sub-element (see
    LEGACY_BACKGROUND_TYPES).  A Button, a Rect and an Oval draw their own fill through their
    own arguments and never carry one.
    """
    return element.tag in LEGACY_BACKGROUND_TYPES


def legacy_add_background(element: Element, state: RunState) -> Element | None:
    """Give this element a background sub-element, shaped the way Tasker writes one.

    Its <geom> is -1,-1,-1,-1,-1,-1,-1,-1 in every sample: a background has no geometry of
    its own, it fills its owner, and the field is there because it is a RectElement like any
    other.  Returns None for a type that never has one rather than creating something Tasker
    would not.
    """
    if not legacy_can_have_background(element):
        return None
    existing = legacy_background(element)
    if existing is not None:
        return existing

    element_cls = type(element)
    background = element_cls("RectElement", {"sr": "background"})
    geometry = element_cls("geom")
    geometry.text = ",".join([UNSET_DIMENSION] * LEGACY_GEOM_VALUES)
    background.append(geometry)
    build_synthesized_args(element_cls, background, _legacy_effective_args("RectElement"), state=state)
    _legacy_order_arg_children(background)
    element.append(background)
    return background


def legacy_remove_background(element: Element) -> None:
    """Take the background away again."""
    background = legacy_background(element)
    if background is not None:
        element.remove(background)


def legacy_scene_properties(
    scene_element: Element,
) -> Element | None:
    """The Scene's own <PropertiesElement>, or None -- 66 of 366 sample Scenes have none."""
    return scene_element.find("PropertiesElement")


def legacy_add_scene_properties(scene_element: Element, state: RunState) -> Element:
    """Give the Scene a <PropertiesElement>, at the end where Tasker keeps it."""
    existing = legacy_scene_properties(scene_element)
    if existing is not None:
        return existing

    element_cls = type(scene_element)
    properties = element_cls("PropertiesElement", {"sr": "props"})
    build_synthesized_args(element_cls, properties, _legacy_effective_args("PropertiesElement"), state=state)
    _legacy_order_arg_children(properties)
    scene_element.append(properties)
    return properties


def legacy_properties_snapshot(
    scene_element: Element,
) -> Element | None:
    """The Scene's <PropertiesElement> as the Properties dialog found it, kept so that
    dialog's Cancel has something to put back.  None when the Scene has none -- which is a
    state to restore like any other (see legacy_properties_restore), not a failure.

    THE PROPERTIES ALONE, not the whole Scene the way legacy_snapshot takes it, because that
    is all the Properties dialog writes to: its geometry boxes drive the Scene dialog's own
    inputs rather than the element (see guiwins._render_scene_geometry), and everything else
    it touches -- the eight arguments, the action bar items, the key filter, the three event
    bindings -- is inside this one child.  Snapshotting the whole Scene would make its Cancel
    throw away whatever the designer behind it had done before it was opened, which is the
    Scene dialog's own Cancel's business and not this one's.
    """
    properties = legacy_scene_properties(scene_element)
    return copy.deepcopy(properties) if properties is not None else None


def legacy_properties_restore(
    scene_element: Element,
    snapshot: Element | None,
) -> bool:
    """Put a legacy_properties_snapshot back, and say whether there was anything to put back.

    In place -- children, attributes and text replaced rather than the element rebound -- for
    the reason legacy_restore gives: the Scene copy holds this element object and so does
    anything rendered from it.

    Either end of the pair may be absent, and both are ordinary.  A snapshot of None means
    the Scene had no properties when the dialog opened, so "Add scene properties" is what
    made these and Cancel takes them away again; a current element of None cannot happen
    today (nothing in the dialog removes one) but is restored rather than ignored, because
    the alternative is a Cancel that silently keeps a deletion.

    The return value is what tells a caller whether to say anything: comparing the two is
    the only way to know, since every field here writes through as it is typed and none of
    them reports having done so.
    """
    current = legacy_scene_properties(scene_element)

    if snapshot is None:
        if current is None:
            return False
        scene_element.remove(current)
        return True

    if current is None:
        scene_element.append(copy.deepcopy(snapshot))
        return True

    if ETW.tostring(current) == ETW.tostring(snapshot):
        return False

    original = copy.deepcopy(snapshot)
    current[:] = list(original)
    current.attrib.clear()
    current.attrib.update(original.attrib)
    current.text = original.text
    return True


# The KEY tab's other half, beside <keyTask>: Tasker keeps "swallow the key press" in a
# <LinkClickFilter sr="filter0"> child of the <PropertiesElement>, as a <stopEvent> beside
# the <urlMatch> naming which keys are being filtered ("back", "back/home").
#
# Transcribed from the sample data -- 87 LinkClickFilters, 84 of them on a
# PropertiesElement and 3 on a WebElement, every one of them sr="filter0".  <stopEvent> is
# written as the word "true" in all 75 that have one and is simply ABSENT in the other 12,
# so absent is how false is stored and how it is written back here; there is no
# <stopEvent>false</stopEvent> anywhere in the sample data.
#
# The filter is created on demand and removed again when nothing is left in it, so a Scene
# that never had one does not gain an empty element from a checkbox being ticked and
# unticked.  An empty <LinkClickFilter> is not invalid -- 6 samples have one -- it just is
# not something this editor should author.
LEGACY_LINK_CLICK_FILTER_TAG = "LinkClickFilter"
LEGACY_LINK_CLICK_FILTER_SR = "filter0"
LEGACY_STOP_EVENT_TAG = "stopEvent"
LEGACY_STOP_EVENT_TRUE = "true"


def legacy_link_click_filter(
    element: Element,
) -> Element | None:
    """The element's <LinkClickFilter>, or None.

    Matched by tag rather than by sr="filter0" so a file that numbers it differently is
    still read rather than silently treated as having no filter; the one this module
    CREATES is always filter0, which is what every sample carries.
    """
    return element.find(LEGACY_LINK_CLICK_FILTER_TAG)


def legacy_stop_event(element: Element) -> bool:
    """Whether this element swallows the key press instead of passing it on.

    Anything other than the word "true" reads as off, which covers both the absent
    <stopEvent> (how Tasker stores false) and a hand-edited "false".
    """
    link_filter = legacy_link_click_filter(element)
    if link_filter is None:
        return False
    return (link_filter.findtext(LEGACY_STOP_EVENT_TAG) or "").strip().lower() == LEGACY_STOP_EVENT_TRUE


def legacy_set_stop_event(element: Element, *, enabled: bool) -> None:
    """Turn Stop Event on or off, creating and disposing of the <LinkClickFilter> around it.

    Off removes the <stopEvent> child rather than writing "false", because that is the only
    way the sample data spells it -- and then removes the filter itself if THAT REMOVAL is
    what left it empty, so ticking and unticking the box gets back to the XML that was there
    before.  A filter still holding a <urlMatch> is kept: which keys are filtered is a
    separate setting this box does not own.

    A filter that was ALREADY EMPTY is left exactly where it is.  Tasker writes those -- 6
    of the 87 in the sample data, and one sample backup has one on a Scene whose Stop Event is off
    -- so turning off something already off would otherwise delete an element the user never
    touched, which is the one thing a no-op must not do.
    """
    link_filter = legacy_link_click_filter(element)

    if not enabled:
        if link_filter is None:
            return
        stop_event = link_filter.find(LEGACY_STOP_EVENT_TAG)
        if stop_event is None:
            return
        link_filter.remove(stop_event)
        if len(link_filter) == 0:
            element.remove(link_filter)
        return

    element_cls = type(element)
    if link_filter is None:
        link_filter = element_cls(
            LEGACY_LINK_CLICK_FILTER_TAG,
            {"sr": LEGACY_LINK_CLICK_FILTER_SR},
        )
        # Appended, not run through _legacy_insert_ordered_child: that one places the
        # lowercase Task-binding children ahead of the capitalised argument children, and
        # a LinkClickFilter goes after all of them -- last child, in all 87 samples.
        element.append(link_filter)
    stop_event = link_filter.find(LEGACY_STOP_EVENT_TAG)
    if stop_event is None:
        stop_event = element_cls(LEGACY_STOP_EVENT_TAG)
        link_filter.insert(0, stop_event)
    stop_event.text = LEGACY_STOP_EVENT_TRUE


# --------------------------------------------------------------------------------------
# TASKER'S SCENE PROPERTIES SCREEN, tab for tab.
#
# Its own user guide ("Scene Properties Edit") divides the screen into UI, Actions and
# Event, and Event into Key, Home Tap and Tab Tap.  Everything below is the XML each of
# those is stored as, worked out by lining the guide up against the 538 <PropertiesElement>s
# in XML/ -- Tasker's file format names none of it the way its screen does:
#
#   UI        <Int/Str/Img sr="arg0..arg7">  (action_overlay.json's "PropertiesElement")
#   Actions   <ListElementItem sr="itemN">   one action-bar item each: icon, label, action
#   Key       <keyTask> + <LinkClickFilter>'s <urlMatch> (the Keys filter) and <stopEvent>
#   Home Tap  <iconclickTask>
#   Tab Tap   <itemselectedTask>
#
# The two surprises, both confirmed against the data rather than guessed:
#
#   * <urlMatch> is the KEYS FILTER, not a URL.  Its values across the samples are "back"
#     (64), "back/home" (12), "Back;Home" and "Back" -- Tasker's slash-separated key list,
#     exactly as the guide describes it ("back/78/a").  The tag name is a leftover from the
#     Web element the same <LinkClickFilter> serves on 3 other samples.
#
#   * <itemselectedTask> is TAB TAP here.  All 15 that sit on a PropertiesElement are on an
#     Activity (arg0 == 2), and every sample whose Tab Labels are set has one.  The same tag
#     on a SpinnerElement is the unrelated "Item Selected"; see LEGACY_TASK_TAGS_BY_TYPE.
#
#   * <iconclickTask> is HOME TAP.  6 of its 7 samples are on an Activity, which is what the
#     guide says it is for ("the home icon in the top left of the action bar").
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class LegacySceneEvent:
    """One of the three Event tabs: what it is called, what it is stored as, when Tasker
    offers it at all, and which local variables its Task can read.

    `requires` is the Property Types the event exists for, as the arg0 index strings
    LEGACY_SCENE_TYPES uses.  `needs_arg` is the further UI-tab argument that has to be
    filled in first -- the guide gates Home Tap on an Icon and Tab Tap on Tab Labels -- or
    "" for an event that needs nothing beyond the right Property Type.
    """

    tag: str
    label: str
    requires: tuple[str, ...]
    needs_arg: str
    needs_arg_label: str
    description: str
    variables: tuple[tuple[str, str], ...]


# Indexes into actiont.lookup_values["PropertyElement1"] == ("Overlay", "Dialog", "Activity").
LEGACY_SCENE_TYPE_OVERLAY = "0"
LEGACY_SCENE_TYPE_DIALOG = "1"
LEGACY_SCENE_TYPE_ACTIVITY = "2"
LEGACY_SCENE_TYPES = (LEGACY_SCENE_TYPE_OVERLAY, LEGACY_SCENE_TYPE_DIALOG, LEGACY_SCENE_TYPE_ACTIVITY)

LEGACY_SCENE_TYPE_NAMES = {
    LEGACY_SCENE_TYPE_OVERLAY: "Overlay",
    LEGACY_SCENE_TYPE_DIALOG: "Dialog",
    LEGACY_SCENE_TYPE_ACTIVITY: "Activity",
}

# The UI-tab argument slots the Event tabs depend on (action_overlay.json's "PropertiesElement").
LEGACY_PROPERTY_TYPE_ARG = "0"
LEGACY_ICON_ARG = "6"
LEGACY_TAB_LABELS_ARG = "7"

# Set on the Task of EVERY Scene event, per the guide.
LEGACY_SCENE_EVENT_COMMON_VARIABLES = (
    ("%scene_name", "the name of the scene containing the element"),
    ("%event_type", "the name of the event (e.g. Tab Tap)"),
)

LEGACY_SCENE_EVENTS: tuple[LegacySceneEvent, ...] = (
    LegacySceneEvent(
        tag=LEGACY_KEY_TASK_TAG,
        label="Key",
        requires=(LEGACY_SCENE_TYPE_DIALOG, LEGACY_SCENE_TYPE_ACTIVITY),
        needs_arg="",
        needs_arg_label="",
        description=(
            "Occurs when a key has been pressed which has not been dealt with elsewhere. "
            "EditText elements with focus absorb key presses and generate no Key event."
        ),
        variables=(
            ("%key_code", "the unique numeric identifier"),
            ("%key_name", "the human name of the key"),
        ),
    ),
    LegacySceneEvent(
        tag=LEGACY_HOME_TAP_TASK_TAG,
        label="Home Tap",
        requires=(LEGACY_SCENE_TYPE_ACTIVITY,),
        needs_arg=LEGACY_ICON_ARG,
        needs_arg_label="Icon",
        description="Triggered when the user taps the home icon in the top left of the action bar.",
        variables=(),
    ),
    LegacySceneEvent(
        tag=LEGACY_TAB_TAP_TASK_TAG,
        label="Tab Tap",
        requires=(LEGACY_SCENE_TYPE_ACTIVITY,),
        needs_arg=LEGACY_TAB_LABELS_ARG,
        needs_arg_label="Tab Labels",
        description="Triggered when the user taps a tab in the action bar.",
        variables=(
            ("%tap_index", "the tab number, starting at 1"),
            ("%tap_label", "the tab label, as specified in the Tab Labels parameter of the UI tab"),
        ),
    ),
)


def legacy_scene_type(properties: Element) -> str:
    """The Scene's Property Type as its arg0 index -- "0" Overlay, "1" Dialog, "2" Activity.

    Defaults to Overlay, which is what arg0 holds when Tasker writes a Scene that has never
    been given a type, and is the most restrictive of the three to assume.
    """
    element = properties.find(f"Int[@sr='arg{LEGACY_PROPERTY_TYPE_ARG}']")
    if element is None:
        return LEGACY_SCENE_TYPE_OVERLAY
    value = (element.attrib.get("val") or "").strip()
    return value if value in LEGACY_SCENE_TYPES else LEGACY_SCENE_TYPE_OVERLAY


def _legacy_arg_is_set(properties: Element, arg_id: str) -> bool:
    """Whether a UI-tab argument slot has anything in it.

    Tasker writes every one of the eight slots whether or not it is used, so presence proves
    nothing -- an empty <Str sr="arg7" ve="3" /> is what "no Tab Labels" looks like.  An
    <Img> is judged by its <nme> for the same reason.
    """
    image = properties.find(f"Img[@sr='arg{arg_id}']")
    if image is not None:
        return bool((image.findtext("nme") or "").strip())
    element = properties.find(f"Str[@sr='arg{arg_id}']")
    if element is not None:
        return bool((element.text or "").strip())
    element = properties.find(f"Int[@sr='arg{arg_id}']")
    return element is not None and bool((element.attrib.get("val") or "").strip())


def legacy_scene_event_availability(
    properties: Element,
    event: LegacySceneEvent,
) -> str:
    """ "" if Tasker offers this event for this Scene, otherwise why it does not.

    NOT A GATE ON READING IT.  An event whose conditions no longer hold can still be bound
    -- a Scene switched from Activity to Dialog keeps its <iconclickTask> -- and the editor
    shows what is there either way, with this sentence beside it.  Hiding a binding the file
    holds is how an editor comes to disagree with the file.
    """
    scene_type = legacy_scene_type(properties)
    if scene_type not in event.requires:
        wanted = " and ".join(LEGACY_SCENE_TYPE_NAMES[kind] for kind in event.requires)
        return f"Available only for {wanted} scenes."
    if event.needs_arg and not _legacy_arg_is_set(properties, event.needs_arg):
        return f"Available only when {event.needs_arg_label} has been set in the UI tab."
    return ""


# ---- The Key event's Keys filter -----------------------------------------------------
LEGACY_KEY_FILTER_TAG = "urlMatch"


def legacy_key_filter(properties: Element) -> str:
    """The Keys filter -- the slash-separated list of keys the Scene handles, "" for all.

    Stored in the same <LinkClickFilter> Stop Event lives in; see legacy_set_stop_event.
    """
    link_filter = legacy_link_click_filter(properties)
    if link_filter is None:
        return ""
    return (link_filter.findtext(LEGACY_KEY_FILTER_TAG) or "").strip()


def legacy_set_key_filter(properties: Element, keys: str) -> None:
    """Set which keys the Scene handles; "" (or blank) means all of them.

    Disposes of an emptied <LinkClickFilter> on the same terms legacy_set_stop_event does,
    and for the same reason -- with the same refusal to touch one that was already empty.
    """
    keys = keys.strip()
    link_filter = legacy_link_click_filter(properties)

    if not keys:
        if link_filter is None:
            return
        existing = link_filter.find(LEGACY_KEY_FILTER_TAG)
        if existing is None:
            return
        link_filter.remove(existing)
        if len(link_filter) == 0:
            properties.remove(link_filter)
        return

    element_cls = type(properties)
    if link_filter is None:
        link_filter = element_cls(LEGACY_LINK_CLICK_FILTER_TAG, {"sr": LEGACY_LINK_CLICK_FILTER_SR})
        properties.append(link_filter)
    existing = link_filter.find(LEGACY_KEY_FILTER_TAG)
    if existing is None:
        # After <stopEvent>, which is the order all 72 samples carrying both are in.
        existing = element_cls(LEGACY_KEY_FILTER_TAG)
        link_filter.append(existing)
    existing.text = keys


# ---- The Actions tab: an Activity's action-bar items ----------------------------------
# One <ListElementItem sr="itemN"> per row of Tasker's Actions tab.  42 in the sample data,
# on 16 <PropertiesElement>s, every one of them on an Activity.  Children, in the order
# Tasker writes them: <label>, <Action sr="action">, and an optional <Img sr="icon"> -- the
# guide's "label text", "action button" and "icon button".  5 of the 42 carry the icon.
LEGACY_ACTION_ITEM_TAG = "ListElementItem"
LEGACY_ACTION_ITEM_SR_PREFIX = "item"
LEGACY_ACTION_ITEM_LABEL_TAG = "label"
LEGACY_ACTION_ITEM_ACTION_SR = "action"
LEGACY_ACTION_ITEM_ICON_SR = "icon"

# Where the guide says an item ends up, from what it has been given.  Tasker decides this at
# display time and stores nothing about it, so this is the editor telling the user what will
# happen rather than a setting anyone can change.
LEGACY_ACTION_ITEM_PLACEMENTS = {
    (True, False): "always in the main bar",
    (True, True): "in the main bar if there is room",
    (False, True): "always in the overflow menu",
    (False, False): "nowhere -- give it an icon or a label",
}


@dataclass(frozen=True)
class LegacyActionItem:
    """One action-bar item: its element, and the three things the guide says it is made of."""

    element: object
    sr: str
    index: int
    label: str
    icon: str
    action_element: object
    action_name: str

    @property
    def placement(self) -> str:
        """Which of Tasker's three overflow rules this item falls under."""
        return LEGACY_ACTION_ITEM_PLACEMENTS[(bool(self.icon), bool(self.label))]


def legacy_action_items(properties: Element) -> list[LegacyActionItem]:
    """The Scene's action-bar items, in the order Tasker shows them.

    Document order, not sr order: Tasker writes item0..itemN in order and renumbers them on
    every reorder (which is what legacy_move_action_item does here), so document order is
    the display order and the sr is only an identity to hold a selection by.
    """
    items = []
    for index, element in enumerate(properties.findall(LEGACY_ACTION_ITEM_TAG)):
        action_element = element.find(f"Action[@sr='{LEGACY_ACTION_ITEM_ACTION_SR}']")
        if action_element is None:
            action_element = element.find("Action")
        code = (action_element.findtext("code") or "").strip() if action_element is not None else ""
        action_code = action_codes.get(f"{code}t")
        icon_element = element.find(f"Img[@sr='{LEGACY_ACTION_ITEM_ICON_SR}']")
        items.append(
            LegacyActionItem(
                element=element,
                sr=element.get("sr", f"{LEGACY_ACTION_ITEM_SR_PREFIX}{index}"),
                index=index,
                label=(element.findtext(LEGACY_ACTION_ITEM_LABEL_TAG) or "").strip(),
                icon=(icon_element.findtext("nme") or "").strip() if icon_element is not None else "",
                action_element=action_element,
                action_name=action_code.name if action_code is not None else (f"Code {code}" if code else ""),
            ),
        )
    return items


def legacy_action_item_args(item: LegacyActionItem, state: RunState) -> list:
    """The item's action's editable arguments, as taskedit.EditableArg records.

    Its <Action> is an ordinary Task action -- same <code> and <Int/Str sr="argN"> shape --
    so it goes through the same model the Task editor and the element inspector use, and an
    argument added to actionc.py shows up here without anything changing.
    """
    if item.action_element is None:
        return []
    code = (item.action_element.findtext("code") or "").strip()
    action_code = action_codes.get(f"{code}t")
    if action_code is None:
        return []
    effective = action_codes[action_code.redirect].args if action_code.redirect else action_code.args
    return build_editable_args(item.action_element, effective, state=state)


def legacy_set_action_item_label(item: LegacyActionItem, text: str) -> None:
    """Set the item's label, adding the <label> child if it has none.

    The <label> is kept even when blank: every one of the 42 samples has one, and an item
    with an icon and no label is a real configuration (the guide's "always shown in the main
    bar" case) rather than an item with nothing in it.
    """
    element = item.element
    label = element.find(LEGACY_ACTION_ITEM_LABEL_TAG)
    if label is None:
        label = type(element)(LEGACY_ACTION_ITEM_LABEL_TAG)
        element.insert(0, label)
    label.text = text


def legacy_action_item_icon(item: LegacyActionItem) -> str:
    """The item's icon as one field's worth of text -- deviceinv's spelling, the same one
    every Icon argument in this app is typed into.
    """

    image = item.element.find(f"Img[@sr='{LEGACY_ACTION_ITEM_ICON_SR}']")
    if image is None:
        return ""
    return appinv.format_icon_value(appinv.read_icon_element(image))


def legacy_set_action_item_icon(item: LegacyActionItem, value: str) -> None:
    """Point the item at an icon, creating its <Img sr="icon"> or taking it away again.

    Blank removes the <Img> outright rather than leaving an empty one: an item with no icon
    is one of the guide's three placements ("just a label" -> always in the overflow menu),
    and 37 of the 42 sample items have no <Img> at all, so absence is how Tasker stores it.

    The value goes through deviceinv, so a built-in name, an icon pack's "name:package", an
    app's "app:package/class" and a %variable are all understood -- the same four forms the
    Task editor's Icon fields accept.
    """

    element = item.element
    image = element.find(f"Img[@sr='{LEGACY_ACTION_ITEM_ICON_SR}']")
    icon = appinv.parse_icon_value(value)

    if icon is None:
        if image is not None:
            element.remove(image)
        return

    if image is None:
        # Last child, which is where all 5 samples that have one keep it -- after <Action>.
        image = type(element)("Img", {"sr": LEGACY_ACTION_ITEM_ICON_SR, "ve": "2"})
        element.append(image)
    appinv.write_icon_element(image, icon)


def legacy_renumber_action_items(properties: Element) -> None:
    """Put the items' sr back in document order -- item0, item1, ... -- after one has been
    added, removed or moved.  Tasker's own files are always numbered that way.
    """
    for index, element in enumerate(properties.findall(LEGACY_ACTION_ITEM_TAG)):
        element.set("sr", f"{LEGACY_ACTION_ITEM_SR_PREFIX}{index}")


def legacy_add_action_item(
    properties: Element,
    action_key: str,
    state: RunState,
) -> LegacyActionItem | list[str]:
    """Add an action-bar item running a brand-new action of this type, or return why not.

    The action is synthesized exactly as Add Task synthesizes one (taskedit's
    classify_action_addability then build_synthesized_args), so what can be put on an action
    bar is precisely what can be added to a Task -- one rule, one reason shown when it
    cannot, and no second opinion about what a default argument should be.

    No icon: the guide has the icon as a separate control on the row, and an item with a
    label alone is valid (it lands in the overflow menu).  Appended after any existing item,
    which is where Tasker adds one -- its plus button is at the bottom of the list.
    """
    addable, reason = classify_action_addability(action_key, state=state)
    if not addable:
        return [reason or f"'{action_key}' cannot be added."]

    element_cls = type(properties)
    action_code = action_codes[action_key]
    effective = action_codes[action_code.redirect].args if action_code.redirect else action_code.args

    item = element_cls(LEGACY_ACTION_ITEM_TAG, {"sr": LEGACY_ACTION_ITEM_SR_PREFIX})
    label = element_cls(LEGACY_ACTION_ITEM_LABEL_TAG)
    label.text = action_code.name
    item.append(label)

    action = element_cls("Action", {"sr": LEGACY_ACTION_ITEM_ACTION_SR, "ve": "7"})
    code = element_cls("code")
    code.text = action_key[:-1]
    action.append(code)
    build_synthesized_args(element_cls, action, effective, action_key, state=state)
    _legacy_order_arg_children(action)
    item.append(action)

    # After the last existing item, or -- for the first one -- at the end, where every
    # sample keeps its items: after the arguments and after the <LinkClickFilter>.
    existing = properties.findall(LEGACY_ACTION_ITEM_TAG)
    if existing:
        properties.insert(list(properties).index(existing[-1]) + 1, item)
    else:
        properties.append(item)
    legacy_renumber_action_items(properties)
    return legacy_action_items(properties)[-1]


def legacy_remove_action_item(properties: Element, sr: str) -> None:
    """Take one action-bar item away, and renumber what is left."""
    element = next(
        (child for child in properties.findall(LEGACY_ACTION_ITEM_TAG) if child.get("sr") == sr),
        None,
    )
    if element is None:
        return
    properties.remove(element)
    legacy_renumber_action_items(properties)


def legacy_move_action_item(properties: Element, sr: str, offset: int) -> None:
    """Move an item up (-1) or down (+1) the action bar, and renumber.

    A no-op at either end rather than an error: the buttons that drive it are disabled
    there, and a silent clamp is the right answer for the keyboard path that is not.
    """
    items = properties.findall(LEGACY_ACTION_ITEM_TAG)
    positions = {element.get("sr"): index for index, element in enumerate(items)}
    if sr not in positions:
        return
    target = positions[sr] + offset
    if not 0 <= target < len(items):
        return

    element = items[positions[sr]]
    anchor = list(properties).index(items[0])
    properties.remove(element)
    properties.insert(anchor + target, element)
    legacy_renumber_action_items(properties)


def find_element_name_actions(scene_name: str, element_name: str, state: RunState) -> list[tuple[str, object]]:
    """The exact <Str> elements a rename would rewrite, as (Task name, Str element).

    STRICTER THAN find_element_name_references ON PURPOSE.  That one matches an action naming
    both strings in any argument, which is the right way round for a *warning* -- a false
    positive costs a needless sentence.  This one drives an edit, where a false positive
    costs a Task silently repointed at something else, so it insists on the shape all 18
    codes actually declare: arg0 is the Scene Name and arg1 is the Element.

    The two can therefore disagree, and the caller is expected to say so rather than quietly
    rewrite fewer Tasks than it warned about.
    """
    if not scene_name or not element_name:
        return []

    wanted_scene = scene_name.strip().casefold()
    wanted_element = element_name.strip().casefold()

    found = []
    for entry in state.tasker_root_elements.get("all_tasks", {}).values():
        task_element = entry["xml"]
        task_name = task_element.findtext("nme") or f"Task {task_element.findtext('id', '?')}"
        for action in task_element.findall("Action"):
            if action.findtext("code") not in LEGACY_ELEMENT_ACTION_CODES:
                continue
            scene_argument = action.find("Str[@sr='arg0']")
            element_argument = action.find("Str[@sr='arg1']")
            if scene_argument is None or element_argument is None:
                continue
            if (scene_argument.text or "").strip().casefold() != wanted_scene:
                continue
            if (element_argument.text or "").strip().casefold() != wanted_element:
                continue
            found.append((task_name, element_argument))
    return found


def apply_element_renames_to_tasks(scene_name: str, renames: list[tuple[str, str]], state: RunState) -> int:
    """Rewrite the Task actions that address these elements by name.  Returns how many
    argument values were changed.

    Applied in the order the renames were made, so an element renamed twice (A to B, then B
    to C) ends up addressed as C rather than being missed by the second pass.

    Called from apply_edited_scene_to_live_tree and nowhere else -- see
    EditableScene.element_renames on why this cannot happen while the dialog is still open.
    """
    with sessundo.undoable(f"Rename Scene '{scene_name}' elements in the Tasks that use them"):
        changed = 0
        for old_name, new_name in renames:
            for _task_name, argument in find_element_name_actions(scene_name, old_name, state=state):
                argument.text = new_name
                changed += 1
        return changed


def legacy_rename_element(
    scene_element: Element,
    sr: str,
    new_name: str,
) -> list[str]:
    """Rename an element within the Scene copy.  Returns errors; renames nothing when it
    returns any.

    Uniqueness is enforced rather than warned about: an element's name is what 18 Task action
    codes look it up by, and no Scene in the sample data has two elements sharing one -- so a
    duplicate would make every one of those actions ambiguous, with no way for Tasker to say
    which was meant.
    """
    element = legacy_element_at(scene_element, sr)
    if element is None:
        return ["That element is no longer in this Scene."]

    wanted = new_name.strip()
    if not wanted:
        return ["An element name cannot be empty."]

    name_element = element.find("Str[@sr='arg0']")
    if name_element is None:
        return ["This element has no name field to rename."]

    current = (name_element.text or "").strip()
    if wanted == current:
        return []

    taken = legacy_element_names(scene_element) - {current}
    if wanted in taken:
        return [f"This Scene already has an element named '{wanted}'."]

    name_element.text = wanted
    return []


# --------------------------------------------------------------------------------------
# Item layouts: the Scene inside an element.
#
# A ListElement and a SpinnerElement each carry a whole nested <Scene> that is the layout of
# one row -- Tasker stamps it out once per entry of whatever variable fills the list.  It is
# a Scene in every sense: its own <nme>, its own widthPort/heightPort, its own elements
# numbered from elements0, its own PropertiesElement.  So it is edited by the same designer,
# opened on the nested element instead of the outer one.
#
# 58 of them across this repo's sample data, always in the same slot per holder type, and
# never nested more than one deep.
# --------------------------------------------------------------------------------------

# Which argument slot each holder keeps its item layout in.  Transcribed: all 38 Lists use
# arg4 and all 20 Spinners use arg3.  A PickerElement has no item layout at all -- it holds
# numbers, not rows.
LEGACY_ITEM_LAYOUT_SLOT: dict[str, str] = {
    "ListElement": "arg4",
    "SpinnerElement": "arg3",
}


def legacy_item_layout(
    element: Element,
) -> Element | None:
    """The nested <Scene sr="val"> holding this element's row layout, or None.

    None covers both "this type never has one" and "this one has not been given one", and
    the caller does not need to tell those apart: neither can be edited.
    """
    slot = LEGACY_ITEM_LAYOUT_SLOT.get(element.tag)
    if slot is None:
        return None
    return element.find(f"Scene[@sr='{slot}']/Scene[@sr='val']")


def legacy_item_layout_name(element: Element) -> str:
    """What the item layout calls itself -- "Builtin Item Layout" for a List, "spinner" for
    a Spinner, in every sample.  For the nested dialog's title, so it says which layout is
    being edited rather than just "Scene".
    """
    layout = legacy_item_layout(element)
    return (layout.findtext("nme") or "").strip() if layout is not None else ""
