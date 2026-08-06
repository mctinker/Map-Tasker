"""sceneedit: build an editable model of a Scene and apply Add/Rename/Delete to it.

The Scene counterpart of projedit.py/profedit.py/taskedit.py, and deliberately
shaped like projedit.py rather than the other two, because a Scene is keyed the
same way a Project is: taskerd.get_the_xml_data builds all_scenes with
move_xml_to_table(..., get_id=False, "nme"), so the dict key IS the Scene's name.

A Scene's identity is its name, and unlike a Project it is its name in three
places at once, which is what makes Rename the interesting operation here:

  1. the all_scenes key,
  2. the <nme> child,
  3. the element's own sr attribute -- sr="sceneElectric Blanket", not the
     sr="scene0" positional index every other Tasker element uses (confirmed
     against this repo's own backup.xml and Electric_Blanket.scn.xml: every
     single Scene in both is sr="scene<name>"),

plus, outside the Scene itself, every owning Project's <scenes> element, which
is a comma-separated list of Scene *names* (not ids -- a Scene has no <id> at
all, again unlike Project/Profile/Task). scenes.process_project_scenes reads
exactly that list, so a rename that misses it leaves the Project pointing at a
Scene name that no longer exists and the Scene stops appearing in every view.
apply_edited_scene_to_live_tree updates all four together; nothing else should
touch any of them on its own.

TWO KINDS OF SCENE, and every function here has to know which it is holding:

  Legacy (https://tasker.joaoapps.com/userguide/en/scenes.html) -- the original
  kind. Its UI is a flat list of <TextElement>/<RectElement>/<ButtonElement>/...
  children, each with its own <geom> geometry, and the Scene's <widthPort>/
  <heightPort>/<widthLand>/<heightLand> are the real pixel canvas those are laid
  out on.

  Version 2 (https://tasker.joaoapps.com/userguide/en/scenes_v2.html -- Tasker's
  own "Screen Builder") -- one <lj> child and no element children at all. <lj> is
  a whole component tree serialized as JSON, gzipped, then Base64'd; see
  decode_v2_layout/encode_v2_layout, which are the only two functions that should
  ever touch it. The layout is declarative (Column/Row/Scaffold with modifiers
  and event handlers, not x/y geometry), so all four size children are -1 on
  every V2 Scene -- confirmed across all three in XML/backup.xml, which are the
  Scenes of the 'Test', 'Scene v2 Dialog' and 'Flashlight Slider' Projects.

  is_v2_scene() is the check; scene_version() gives the display name. The two
  are told apart purely by whether <lj> is there, which is also how
  scenes.get_scene_elements decides how to render one.

The V2 layout JSON carries its own copy of the Scene's name, as a top-level
"name" key alongside "root" -- so a V2 rename is not just an XML edit; the JSON
has to be decoded, renamed, and re-encoded or the two disagree. apply_edits_to_scene
does this; see _rename_v2_layout.

NOT YET HANDLED, and the reason config.EDIT_SCENE defaults to False: a Scene's
own contents -- a Legacy Scene's UI elements and the Tasks they fire (ClickTask
and friends, see scenes.get_scene_elements), or a V2 Scene's component tree --
are carried along verbatim by every function here but cannot be edited. Renaming
a Scene also does not rewrite Task actions that name it (Show Scene, Hide Scene,
Destroy Scene all take the Scene name as a string argument); those keep pointing
at the old name. Both are the "details to be provided later" this sketch leaves
room for -- see guiwins._build_scene_editor_body, the one place a dialog body
for them has to go.

Never touches PrimeItems.xml_tree -- edits happen on a deep copy (Add/Rename) or
directly on the live tasker_root_elements tables (Delete), mirroring projedit.py.
"""

from __future__ import annotations

import base64
import copy
import gzip
import io
import json
import os
import re
import time
import xml.etree.ElementTree as ETW  # stdlib "ET Write" -- used only to build/serialize
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import defusedxml.ElementTree

from maptasker.src.primitem import PrimeItems
from maptasker.src.projedit import touch_project_mdate

# Destination folder on the Android device for Save To Android -- the Scene sibling of
# projedit.ANDROID_PROJECT_LOCATION ("Tasker/projects"); see android_scene_path.
ANDROID_SCENE_LOCATION = "Tasker/scenes"
# A brand-new *Legacy* Scene's size, in the same units Tasker itself writes.  Portrait gets
# a real default so a new Scene is visible at all; landscape gets -1, which is what Tasker
# uses for "not laid out for this orientation" (every Scene in this repo's sample data that
# has never been opened in landscape carries -1 for both landscape dimensions).  A Version 2
# Scene gets -1 for all four instead -- it has no canvas to size; see create_new_scene.
NEW_SCENE_WIDTH_PORTRAIT = "600"
NEW_SCENE_HEIGHT_PORTRAIT = "800"
UNSET_DIMENSION = "-1"
# The Scene's four size children, paired with the label the dialog shows for each.
# The label lives here, next to the tag, rather than in guiwins, because three places
# have to agree on this list and would otherwise drift: guiwins._build_scene_editor_body
# builds one input per entry, userintr._apply_scene_field_values validates them and names
# them in its error messages, and set_scene_dimensions writes them back.  The labels are
# English source strings -- every consumer runs them through translate_string.
SCENE_DIMENSION_FIELDS = (
    ("widthPort", "Width (portrait)"),
    ("heightPort", "Height (portrait)"),
    ("widthLand", "Width (landscape)"),
    ("heightLand", "Height (landscape)"),
)

# The two kinds of Scene (see this module's docstring).  These strings are what the Add
# Scene version picker shows and what create_new_scene takes, so they are display names,
# not internal codes -- there is no third value and nothing parses them.
SCENE_VERSION_LEGACY = "Legacy"
SCENE_VERSION_V2 = "Version 2"
SCENE_VERSIONS = (SCENE_VERSION_LEGACY, SCENE_VERSION_V2)
# The child holding a V2 Scene's whole component tree -- gzipped, Base64'd JSON.  Its
# presence is the entire difference between the two kinds of Scene.
V2_LAYOUT_TAG = "lj"
# How Tasker itself encodes <lj>, matched byte-for-byte rather than guessed: compact JSON
# separators (no spaces), gzip at level 6 with the mtime header zeroed.  Re-encoding all
# three V2 Scenes in XML/backup.xml with exactly these settings reproduces Tasker's own
# Base64 string character for character, which is the only way to be sure a Scene this app
# rewrites is still the same file Tasker wrote.  (mtime especially: gzip stamps the current
# time into the header by default, so without mtime=0 an untouched Scene's <lj> would come
# out different on every single save.)
_V2_JSON_SEPARATORS = (",", ":")
_V2_GZIP_LEVEL = 6
# The layout JSON's top-level keys.  "root" is the component tree; "name" is the Scene's
# own name, duplicated here by Tasker and therefore something a rename has to keep in step.
_V2_ROOT_KEY = "root"
_V2_NAME_KEY = "name"


@dataclass
class EditableScene:
    """A deep-copied Scene element plus the name it was loaded under (the live
    all_scenes dict key -- may differ from the copy's own <nme> text once the
    user has typed a new one but not yet applied it).  Mirrors
    projedit.EditableProject, for the same reason: name-keyed table, so the
    key it came in under has to be remembered separately from the element.
    """

    scene_name: str
    scene_element: defusedxml.ElementTree.Element


def is_v2_scene(scene_element: defusedxml.ElementTree.Element) -> bool:
    """Whether this is a Version 2 (Screen Builder) Scene rather than a Legacy one.

    The <lj> child is the whole test, and it is a reliable one in both directions:
    every V2 Scene has exactly one and no element children, every Legacy Scene has
    element children and no <lj>.  scenes.get_scene_elements branches on the same
    tag to decide how to render a Scene, so the two agree by construction.
    """
    return scene_element.find(V2_LAYOUT_TAG) is not None


def scene_version(scene_element: defusedxml.ElementTree.Element) -> str:
    """SCENE_VERSION_V2 or SCENE_VERSION_LEGACY -- the display name of what
    is_v2_scene() decides.  Used for dialog titles and the pulldown-free "this is
    what you are editing" line in the editor body.
    """
    return SCENE_VERSION_V2 if is_v2_scene(scene_element) else SCENE_VERSION_LEGACY


def decode_v2_layout(scene_element: defusedxml.ElementTree.Element) -> dict | None:
    """The V2 Scene's component tree, decoded from <lj> into plain Python.

    Returns None for a Legacy Scene (no <lj>), and also for an <lj> that won't
    decode -- a corrupt or truncated one, or a future encoding this doesn't know.
    Callers treat None as "nothing to show/change here" and leave the element
    untouched, which is the safe answer either way: a layout that can't be read
    certainly shouldn't be re-encoded over the top of the original.

    Decoding itself is scenes.decompress_gzip_json, imported lazily -- that module
    pulls in the whole Map-output stack (tasks, proclist, dirout) which nothing on
    the editing path needs.  The encode half has no equivalent there and lives
    here, in encode_v2_layout.
    """
    layout_element = scene_element.find(V2_LAYOUT_TAG)
    if layout_element is None or not layout_element.text:
        return None

    from maptasker.src.scenes import decompress_gzip_json  # noqa: PLC0415

    decoded = decompress_gzip_json(layout_element.text)
    # decompress_gzip_json reports failure by returning its error message as a
    # string rather than raising, so anything that isn't a dict is a failure.
    return decoded if isinstance(decoded, dict) else None


def encode_v2_layout(scene_element: defusedxml.ElementTree.Element, layout: dict) -> None:
    """Writes a component tree back into the Scene's <lj>, encoded the way Tasker
    itself does (see _V2_GZIP_LEVEL and the note above it -- this reproduces
    Tasker's own output byte for byte, which is what makes an edit that changes
    nothing leave the file unchanged).  Creates the <lj> child if it isn't there,
    so this doubles as "make this a V2 Scene" for create_new_scene.
    """
    payload = json.dumps(layout, separators=_V2_JSON_SEPARATORS, ensure_ascii=False).encode("utf-8")
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", compresslevel=_V2_GZIP_LEVEL, mtime=0) as gzip_file:
        gzip_file.write(payload)
    _set_child_text(scene_element, V2_LAYOUT_TAG, base64.b64encode(buffer.getvalue()).decode("ascii"))


def _rename_v2_layout(scene_element: defusedxml.ElementTree.Element, new_name: str) -> None:
    """Keeps a V2 Scene's embedded layout name in step with its <nme>.

    Tasker stores the Scene's name twice -- once as the <nme> child, once as the
    layout JSON's top-level "name" (all three V2 Scenes in XML/backup.xml carry
    both, always agreeing).  Renaming only the XML leaves the two disagreeing
    inside a single file, so this decodes, sets, and re-encodes.

    No-op for a Legacy Scene, and for a V2 Scene whose <lj> won't decode -- see
    decode_v2_layout on why a layout that can't be read is left alone rather than
    overwritten.
    """
    layout = decode_v2_layout(scene_element)
    if layout is None:
        return
    layout[_V2_NAME_KEY] = new_name
    encode_v2_layout(scene_element, layout)


# --------------------------------------------------------------------------------------
# Version 2 designer, phase 1: address, describe and edit the nodes of a component tree.
#
# Everything below treats the decoded layout as the document.  Nothing here reconstructs a
# node: edits are applied in place, which is what keeps an untouched Scene re-encoding to
# the byte-identical <lj> it came from (json.dumps follows dict insertion order, so a node
# rebuilt "in schema order" would serialize differently even when nothing about it changed).
#
# Structural editing -- add, delete, reorder, reparent -- is deliberately NOT here yet.
# This phase can retitle a Button, resize a Text, repoint a WebView; it cannot change the
# shape of the tree.
# --------------------------------------------------------------------------------------

# Node keys that hold something other than child components, and so are never walked into
# when building the tree or offered as editable properties.
V2_STRUCTURAL_KEYS = ("type", "modifiers", "eventHandlers")


@dataclass(frozen=True)
class V2Prop:
    """One editable property of a component: which JSON key it is, what to call it in
    the inspector, and what kind of input to put up for it.

    kind is "text" (free string, including a %variable reference), "number" (digits, but
    still stored as a string -- see _coerce_like) or "choice" (one of `choices`, offered
    as a pulldown).
    """

    key: str
    label: str
    kind: str = "text"
    choices: tuple[str, ...] = ()


# Every component carries an id, so it is offered first for all of them rather than
# repeated in each entry below.  Phase 1 shows it read-only: renaming an id means finding
# every condition/showWhen/action that names it, which is phase 2's job (see the design
# sketch's round-trip rules).
V2_ID_PROP = V2Prop("id", "Component id")

_ARRANGEMENT = ("Start", "Center", "End", "SpaceBetween", "SpaceAround", "SpaceEvenly")
_ALIGNMENT = ("Start", "Center", "End")
_VERTICAL_ALIGNMENT = ("Top", "Center", "Bottom")

# What each component type offers the inspector.  Derived from what actually appears in
# XML/backup.xml -- the three Version 2 Scenes plus everything the 'Scene v2 Dialog'
# project's builder Task emits -- because Tasker publishes no schema for this format, so
# observed usage is the only schema there is.
#
# A type missing from here still opens and still edits: _v2_unschemad_props falls back to
# offering its scalar keys as plain text fields.  That matters for forward compatibility --
# a Scene from a newer Tasker will carry components this table has never seen, and the
# designer must not be the reason they can't be touched.
V2_COMPONENT_SCHEMA: dict[str, tuple[V2Prop, ...]] = {
    "Column": (
        V2Prop("horizontalAlignment", "Horizontal alignment", "choice", _ALIGNMENT),
        V2Prop("verticalArrangement", "Vertical arrangement", "choice", _ARRANGEMENT),
        V2Prop("spacing", "Spacing", "number"),
    ),
    "Row": (
        V2Prop("horizontalArrangement", "Horizontal arrangement", "choice", _ARRANGEMENT),
        V2Prop("verticalAlignment", "Vertical alignment", "choice", _VERTICAL_ALIGNMENT),
        V2Prop("spacing", "Spacing", "number"),
    ),
    "FlowRow": (
        V2Prop("horizontalArrangement", "Horizontal arrangement", "choice", _ARRANGEMENT),
        V2Prop("spacingHorizontal", "Spacing across", "number"),
        V2Prop("spacingVertical", "Spacing down", "number"),
    ),
    "Text": (
        V2Prop("text", "Text"),
        V2Prop("textSize", "Text size", "number"),
        V2Prop("textAlign", "Text alignment", "choice", _ALIGNMENT),
        V2Prop("color", "Colour"),
    ),
    "TextInput": (
        V2Prop("label", "Label"),
        V2Prop("textSize", "Text size", "number"),
        V2Prop("showWhen", "Show when"),
        V2Prop("showWhenMode", "Hidden as", "choice", ("Gone", "Invisible")),
    ),
    "Button": (
        V2Prop("text", "Text"),
        V2Prop("buttonColor", "Button colour"),
        V2Prop("textColor", "Text colour"),
        V2Prop("showWhen", "Show when"),
    ),
    "IconButton": (
        V2Prop("icon", "Icon"),
        V2Prop("contentScale", "Content scale"),
    ),
    "Image": (
        V2Prop("url", "Image URL"),
        V2Prop("icon", "Icon"),
        V2Prop("width", "Width", "number"),
        V2Prop("height", "Height", "number"),
        V2Prop("alignment", "Alignment", "choice", _ALIGNMENT),
    ),
    "WebView": (
        V2Prop("content", "Content"),
        V2Prop("allowFileAccess", "Allow file access", "choice", ("true", "false")),
        V2Prop("height", "Height", "number"),
    ),
    "Video": (
        V2Prop("source", "Source"),
        V2Prop("autoPlay", "Auto play", "choice", ("true", "false")),
        V2Prop("loop", "Loop", "choice", ("true", "false")),
        V2Prop("ratio", "Aspect ratio"),
    ),
    "Slider": (
        V2Prop("min", "Minimum", "number"),
        V2Prop("max", "Maximum", "number"),
        V2Prop("steps", "Steps", "number"),
        V2Prop("value", "Value"),
    ),
    "Dropdown": (
        V2Prop("isExpanded", "Expanded"),
        V2Prop("triggerShowsSelected", "Trigger shows selection", "choice", ("true", "false")),
        V2Prop("triggerMatchesContentWidth", "Trigger matches width", "choice", ("true", "false")),
    ),
    "Checkbox": (V2Prop("checked", "Checked"),),
    "Switch": (V2Prop("checked", "Checked"),),
    "NavigationItem": (
        V2Prop("icon", "Icon"),
        V2Prop("label", "Label"),
    ),
    "Variable": (V2Prop("key", "Variable"),),
    "Spacer": (V2Prop("height", "Height", "number"),),
    "Divider": (V2Prop("color", "Colour"),),
    "Scaffold": (),
    "TopAppBar": (),
    "NavigationBar": (),
    "FloatingActionButton": (),
}


@dataclass(frozen=True)
class V2TreeRow:
    """One line of the designer's component tree: the node itself, how deep it sits, the
    path that addresses it (see v2_node_at), and the container slot it hangs off -- the
    slot matters because a Scaffold's children are split across topBar/content/bottomBar/
    floatingActionButton rather than one "children" list.
    """

    path: tuple
    depth: int
    node: dict
    slot: str
    label: str


def v2_child_slots(node: dict) -> list[tuple[str, list]]:
    """The (slot key, child list) pairs hanging off this node.

    A container's children live under a type-specific key -- "children" for Column/Row,
    but "topBar"/"content"/"bottomBar"/"floatingActionButton" for Scaffold, "title"/
    "navigationIcon" for TopAppBar, and so on.  Rather than enumerate those keys (there is
    no fixed list, and a Tasker update would quietly add to it), this treats any list of
    component-shaped dicts as a slot -- the same rule v2_component_summary walks by.
    """
    slots = []
    for key, value in node.items():
        if key in V2_STRUCTURAL_KEYS or not isinstance(value, list):
            continue
        if any(isinstance(item, dict) and "type" in item for item in value):
            slots.append((key, value))
    return slots


def v2_node_label(node: dict) -> str:
    """"Text 'title_text'" -- how a node reads in the tree, matching what
    v2_component_summary already produces for the read-only outline.
    """
    node_type = node.get("type", "?")
    node_id = node.get("id", "")
    return f"{node_type} '{node_id}'" if node_id else node_type


def v2_flatten(layout: dict) -> list[V2TreeRow]:
    """The layout's component tree as a flat, depth-tagged list, in display order --
    what the designer's tree pane renders one row per entry.

    The path in each row is what addresses that node later (v2_node_at): a tuple of
    alternating slot key and index, e.g. ("content", 0, "children", 2).  Paths are used
    rather than node references because the inspector is rebuilt on every selection, and a
    path stays meaningful across a rebuild in a way a stale widget reference does not.
    """
    rows: list[V2TreeRow] = []

    def walk(node: dict, depth: int, path: tuple, slot: str) -> None:
        rows.append(V2TreeRow(path=path, depth=depth, node=node, slot=slot, label=v2_node_label(node)))
        for slot_key, children in v2_child_slots(node):
            for index, child in enumerate(children):
                if isinstance(child, dict):
                    walk(child, depth + 1, (*path, slot_key, index), slot_key)

    root = layout.get(_V2_ROOT_KEY)
    if isinstance(root, dict):
        walk(root, 0, (), _V2_ROOT_KEY)
    return rows


def v2_node_at(layout: dict, path: tuple) -> dict | None:
    """The node a v2_flatten path points at, or None if the path no longer resolves
    (defence in depth -- phase 1 can't restructure the tree, so it always should).
    """
    node = layout.get(_V2_ROOT_KEY)
    if not isinstance(node, dict):
        return None
    for slot_key, index in zip(path[::2], path[1::2], strict=False):
        children = node.get(slot_key)
        if not isinstance(children, list) or not (0 <= index < len(children)):
            return None
        node = children[index]
        if not isinstance(node, dict):
            return None
    return node


def v2_editable_props(node: dict) -> list[V2Prop]:
    """What the inspector puts up for this node: its schema properties first, then any
    other scalar key it happens to carry.

    The second half is the forward-compatible bit.  V2_COMPONENT_SCHEMA is built from the
    Scenes in one backup, so a Scene written by a newer Tasker will have properties this
    app has never seen; showing them as plain text fields means they can still be read and
    edited rather than being invisible.  Anything non-scalar (a nested list or dict) is
    left out entirely -- it is either a child slot, a modifier list, or an event handler,
    none of which phase 1 edits, and all of which are carried through untouched.
    """
    schema = V2_COMPONENT_SCHEMA.get(node.get("type", ""), ())
    props = [V2_ID_PROP, *schema]
    known = {prop.key for prop in props}
    for key, value in node.items():
        if key in known or key in V2_STRUCTURAL_KEYS:
            continue
        if isinstance(value, (str, int, float, bool)):
            props.append(V2Prop(key, key))
    return props


def _coerce_like(existing: object, text: str) -> object:
    """Store an edited value in the same JSON type the node already used for that key.

    Tasker is inconsistent about this -- a Text's textSize is the string "22" while some
    numeric props are real JSON numbers -- and rewriting "22" as 22 would change the
    encoded bytes of a property the user never meant to retype.  So: match what was there.
    A key that did not exist before defaults to a string, which is what Tasker's own
    builder emits for nearly everything.
    """
    if isinstance(existing, bool):
        return text.strip().lower() in ("true", "1", "yes")
    if isinstance(existing, int):
        try:
            return int(text)
        except ValueError:
            return text
    if isinstance(existing, float):
        try:
            return float(text)
        except ValueError:
            return text
    return text


def v2_set_prop(node: dict, key: str, text: str) -> None:
    """Write one inspector field back onto its node, in place.

    In place is the whole point: assigning an existing key leaves it at its original
    position in the dict, so the re-encoded JSON differs from the original only where the
    user actually typed.  A key that was absent is appended (there is nowhere else to put
    it), and clearing a field back to empty removes the key rather than storing "" --
    an empty property and an absent one are not the same thing to Tasker.
    """
    if key in node:
        if text == "":
            del node[key]
        else:
            node[key] = _coerce_like(node[key], text)
    elif text != "":
        node[key] = text


# --------------------------------------------------------------------------------------
# Version 2 designer, phase 2: change the shape of the tree.
#
# Insert, delete, duplicate, reorder and re-nest components, and rename their ids.  Phase 1
# could only retype a property on a node that already existed; this is what makes Add Scene
# -> Version 2 produce something other than an empty Column.
#
# Every function here mutates the layout dict in place, for the same reason phase 1 does --
# an untouched branch keeps its original key order and so re-encodes to the same bytes.
# The caller is responsible for snapshotting before a structural edit if it wants undo
# (guiwins keeps a deepcopy stack; the trees are small enough that this costs nothing).
# --------------------------------------------------------------------------------------

# The child slots each container type declares, in the order the designer offers them.
# "children" is the ordinary case; Scaffold and friends split their children across named
# slots instead, which is why insertion has to know the slot and not just the parent.
# A type absent from here is a leaf -- but see v2_container_slots, which also honours any
# slot a node actually carries, so a component from a newer Tasker still nests correctly.
V2_CONTAINER_SLOTS: dict[str, tuple[str, ...]] = {
    "Column": ("children",),
    "Row": ("children",),
    "FlowRow": ("children",),
    "Scaffold": ("content", "topBar", "bottomBar", "floatingActionButton"),
    "TopAppBar": ("title", "navigationIcon"),
    "NavigationBar": ("content",),
    "FloatingActionButton": ("content",),
    "Dropdown": ("trigger", "content"),
}

# What the palette offers, grouped the way the inspector shows it.  Restricted to types
# seen in XML/backup.xml -- the three Version 2 Scenes plus everything the 'Scene v2 Dialog'
# builder emits -- because inventing entries for Tasker components nothing here has ever
# produced would mean inventing their property lists too, with nothing to check them against.
V2_PALETTE: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Layout", ("Column", "Row", "FlowRow", "Spacer", "Divider")),
    ("Display", ("Text", "Image", "WebView", "Video")),
    ("Input", ("TextInput", "Slider", "Switch", "Checkbox", "Dropdown", "Button", "IconButton")),
    ("Structure", ("Scaffold", "TopAppBar", "NavigationBar", "NavigationItem", "FloatingActionButton", "Variable")),
)

# The properties a newly-added component starts with, beyond its type and id.  Kept to what
# makes the component visible and sensible on screen -- a Text with no text renders as
# nothing, which reads as a bug rather than as an empty component.  Everything else is left
# absent rather than defaulted, so the encoded JSON stays as small as what Tasker writes.
V2_NEW_NODE_DEFAULTS: dict[str, dict] = {
    "Column": {"horizontalAlignment": "Center", "verticalArrangement": "Center", "children": []},
    "Row": {"horizontalArrangement": "Center", "verticalAlignment": "Center", "children": []},
    "FlowRow": {"children": []},
    "Text": {"text": "Text"},
    "Button": {"text": "Button"},
    "TextInput": {"label": "Input"},
    "Slider": {"min": "0", "max": "100", "steps": "1"},
    "Switch": {"checked": "false"},
    "Checkbox": {"checked": "false"},
    "Image": {"url": ""},
    "WebView": {"content": ""},
    "Video": {"source": ""},
    "Spacer": {"height": "16"},
    "Divider": {},
    "Variable": {"key": ""},
    "NavigationItem": {"label": "Item"},
    "Dropdown": {"trigger": [], "content": []},
    "Scaffold": {"content": []},
    "TopAppBar": {"title": []},
    "NavigationBar": {"content": []},
    "FloatingActionButton": {"content": []},
    "IconButton": {"icon": "icon:Star"},
}

# Task action codes that address a Version 2 Scene's component by its id: Update Scene v2,
# Get Scene v2 Values, Run Scene v2 Action.  Confirmed against this repo's own backup --
# 'Task16' runs code 485 with the Scene name in one Str argument and the component id
# ('Text1') in another.
#
# The legacy Element* codes (50/51/53/54/... 'Element Text', 'Element Web Control', ...)
# address a *Legacy* Scene's elements the same way but are not listed here: this sweep only
# runs for Version 2 Scenes, whose components those actions cannot reach.
V2_ELEMENT_ACTION_CODES = ("481", "483", "485")


def v2_container_slots(node: dict) -> tuple[str, ...]:
    """Which slots this node can take children in.

    The declared slots for its type (V2_CONTAINER_SLOTS), plus any slot the node actually
    carries that the table doesn't know about -- so a container from a newer Tasker is still
    a container here, and its children are still reachable, rather than the designer
    flattening it into a leaf.
    """
    declared = V2_CONTAINER_SLOTS.get(node.get("type", ""), ())
    present = tuple(key for key, _ in v2_child_slots(node) if key not in declared)
    return declared + present


def v2_all_ids(layout: dict) -> set[str]:
    """Every component id currently in the tree -- what uniqueness is checked against."""
    return {row.node["id"] for row in v2_flatten(layout) if isinstance(row.node.get("id"), str)}


def v2_next_id(layout: dict, node_type: str) -> str:
    """A free id for a new component of this type: "Text1", "Text2", ...

    Serial per type, matching how Tasker's own Screen Builder names them (the 'V2' Scene
    carries Scaffold1/TopAppBar1/Text1/Text2/NavItem1..3) and how the Scene v2 Dialog
    builder's nextId() does it.  Predictable, collision-free, and readable in a Task that
    addresses the component by id.
    """
    taken = v2_all_ids(layout)
    index = 1
    while f"{node_type}{index}" in taken:
        index += 1
    return f"{node_type}{index}"


def v2_new_node(layout: dict, node_type: str) -> dict:
    """Build a component ready to insert: type, a free id, and its starting properties.

    Key order matters (see this module's designer notes) -- type then id then the rest,
    which is the order every component in a real Tasker-written Scene uses.
    """
    node = {"type": node_type, "id": v2_next_id(layout, node_type)}
    node.update(copy.deepcopy(V2_NEW_NODE_DEFAULTS.get(node_type, {})))
    return node


def _v2_parent_and_slot(layout: dict, path: tuple) -> tuple[dict | None, str, int]:
    """The parent node, slot key and index a path's node sits at -- () for the root
    returns (None, "", -1), since the root has no parent and cannot be moved or deleted.
    """
    if not path:
        return None, "", -1
    parent = v2_node_at(layout, path[:-2])
    return parent, path[-2], path[-1]


def v2_insert_node(layout: dict, path: tuple, node: dict, slot: str = "") -> tuple | None:
    """Insert a component relative to the node at `path`, and return the new node's path.

    Placement is one rule, chosen so a single "Add" button behaves predictably:

      * if the target can hold children, the new node goes *inside* it, at the end of
        `slot` (or its first declared slot);
      * otherwise the new node goes in *after* it, as its next sibling.

    So adding to a Column nests, and adding to a Text appends alongside it -- which is what
    a tree editor's users expect from the two cases without having to pick a mode first.

    Returns None if the target path doesn't resolve, or if a leaf at the root somehow has
    no parent to be a sibling of (not reachable in practice -- the root is always a
    container in every Scene Tasker writes).
    """
    target = v2_node_at(layout, path)
    if target is None:
        return None

    slots = v2_container_slots(target)
    if slots:
        slot_key = slot or slots[0]
        children = target.setdefault(slot_key, [])
        if not isinstance(children, list):
            return None
        children.append(node)
        return (*path, slot_key, len(children) - 1)

    parent, parent_slot, index = _v2_parent_and_slot(layout, path)
    if parent is None:
        return None
    siblings = parent.get(parent_slot)
    if not isinstance(siblings, list):
        return None
    siblings.insert(index + 1, node)
    return (*path[:-1], index + 1)


def v2_delete_node(layout: dict, path: tuple) -> list[str]:
    """Delete a component and everything under it.  Returns [] on success, else errors
    (mirroring delete_scene's convention) and changes nothing.

    Refuses to delete the root: a Scene with no root component is not something Tasker can
    open, and "delete everything" is Delete Scene's job, not the designer's.
    """
    if not path:
        return ["The root component can't be deleted. Delete the Scene itself instead."]
    parent, slot, index = _v2_parent_and_slot(layout, path)
    if parent is None or not isinstance(parent.get(slot), list):
        return ["That component no longer exists."]
    del parent[slot][index]
    return []


def v2_move_node(layout: dict, path: tuple, offset: int) -> tuple | None:
    """Move a component up or down among its siblings; returns its new path, or None if
    it can't move that way (already first/last, or it's the root).  Reordering matters:
    a slot's list order is the order the components lay out on screen.
    """
    parent, slot, index = _v2_parent_and_slot(layout, path)
    if parent is None:
        return None
    siblings = parent.get(slot)
    if not isinstance(siblings, list):
        return None
    new_index = index + offset
    if not 0 <= new_index < len(siblings):
        return None
    siblings.insert(new_index, siblings.pop(index))
    return (*path[:-1], new_index)


def v2_outdent_node(layout: dict, path: tuple) -> tuple | None:
    """Move a component out of its parent, to sit just after it in the grandparent.
    Returns the new path, or None if there's no grandparent to move into.

    Paired with v2_indent_node, this is how re-nesting is done without drag and drop --
    the two operations a keyboard tree editor needs, and between them they can reach any
    arrangement.
    """
    parent, slot, index = _v2_parent_and_slot(layout, path)
    if parent is None or len(path) < 4:
        return None
    grandparent, grandparent_slot, parent_index = _v2_parent_and_slot(layout, path[:-2])
    if grandparent is None or not isinstance(grandparent.get(grandparent_slot), list):
        return None
    node = parent[slot].pop(index)
    grandparent[grandparent_slot].insert(parent_index + 1, node)
    return (*path[:-4], grandparent_slot, parent_index + 1)


def v2_indent_node(layout: dict, path: tuple) -> tuple | None:
    """Move a component into the container immediately above it among its siblings.
    Returns the new path, or None if there is no previous sibling or it can't take children.
    """
    parent, slot, index = _v2_parent_and_slot(layout, path)
    if parent is None or index <= 0:
        return None
    siblings = parent.get(slot)
    if not isinstance(siblings, list):
        return None
    new_parent = siblings[index - 1]
    slots = v2_container_slots(new_parent)
    if not slots:
        return None
    target_slot = slots[0]
    children = new_parent.setdefault(target_slot, [])
    if not isinstance(children, list):
        return None
    children.append(siblings.pop(index))
    return (*path[:-1], index - 1, target_slot, len(children) - 1)


def v2_duplicate_node(layout: dict, path: tuple) -> tuple | None:
    """Copy a component and everything under it in beside it, with fresh ids throughout.

    Every id in the copied subtree is renumbered, not just the top one -- two components
    sharing an id would make a Task's 'Run Scene v2 Action' ambiguous about which one it
    means. Returns the new node's path, or None for the root (nothing to duplicate it into).
    """
    parent, slot, index = _v2_parent_and_slot(layout, path)
    node = v2_node_at(layout, path)
    if node is None or parent is None or not isinstance(parent.get(slot), list):
        return None

    clone = copy.deepcopy(node)

    def renumber(current: dict) -> None:
        if isinstance(current.get("type"), str):
            current["id"] = v2_next_id(layout, current["type"])
        for _, children in v2_child_slots(current):
            for child in children:
                if isinstance(child, dict):
                    renumber(child)

    # Insert first, then renumber against the tree the clone is now part of, so the clone's
    # own new ids are counted and its nested components can't collide with each other.
    parent[slot].insert(index + 1, clone)
    renumber(clone)
    return (*path[:-1], index + 1)


def v2_rename_id(layout: dict, path: tuple, new_id: str) -> list[str]:
    """Rename a component's id, if the new one is free.  Returns [] on success, else errors.

    Does NOT rewrite anything that referred to the old id -- see
    find_component_id_references, which the dialog calls first so the user is told what
    they are about to detach before they do it. Nothing inside a Scene refers to a
    component id (confirmed across all three Version 2 Scenes in this repo's backup:
    condition/showWhen/applyWhen hold Tasker *variables*, never ids), so the references
    that matter are all in Task actions, and rewriting a Task's arguments from the Scene
    editor is a bigger step than this phase should take on its own.
    """
    node = v2_node_at(layout, path)
    if node is None:
        return ["That component no longer exists."]

    new_id = new_id.strip()
    if not new_id:
        return ["Component id cannot be empty."]
    if new_id != node.get("id") and new_id in v2_all_ids(layout):
        return [f"Another component is already called '{new_id}'. Choose a different id."]

    node["id"] = new_id
    return []


def find_component_id_references(scene_name: str, component_id: str) -> list[str]:
    """Tasks whose actions address this component by id, as readable descriptions.

    Tasker reaches into a Version 2 Scene from outside: 'Run Scene v2 Action' and friends
    take the Scene name and the component id as separate string arguments (see
    V2_ELEMENT_ACTION_CODES). So renaming or deleting a component can break a Task
    elsewhere in the backup, and that is the one consequence the designer cannot see from
    the layout alone.

    Matches an action that names *both* this Scene and this component id in any of its
    string arguments, rather than checking fixed argument positions -- code 485 puts the
    Scene in arg1 and the id in arg2, but 481/483's layouts vary with how they're
    configured, and a position-independent match stays correct for all of them.  The cost
    is theoretical false positives (a Task naming both strings for unrelated reasons),
    which is the right way round for a warning.

    Compared case-insensitively, for the same reason.  This is not hypothetical: in this
    repo's own backup, 'Task16' runs code 485 against the Scene it spells 'v2', while the
    Scene's actual <nme> is 'V2'.  Tasker evidently resolves that, so a case-sensitive
    sweep reports "nothing refers to this" about a component something demonstrably does
    refer to -- the one answer a warning like this must never give.
    """
    if not scene_name or not component_id:
        return []

    wanted_scene = scene_name.strip().casefold()
    wanted_id = component_id.strip().casefold()

    references = []
    for entry in PrimeItems.tasker_root_elements.get("all_tasks", {}).values():
        task_element = entry["xml"]
        task_name = task_element.findtext("nme") or f"Task {task_element.findtext('id', '?')}"
        for action in task_element.findall("Action"):
            if action.findtext("code") not in V2_ELEMENT_ACTION_CODES:
                continue
            values = {(child.text or "").strip().casefold() for child in action.findall("Str")}
            if wanted_scene in values and wanted_id in values:
                references.append(task_name)
                break
    return sorted(set(references))


# --------------------------------------------------------------------------------------
# Version 2 designer, phase 3: the three things hanging off a component that phases 1 and 2
# carried through untouched -- its modifiers, its event handlers, and its output bindings.
#
# Between them these are what make a Scene do something rather than just look like something:
# modifiers decide how a component sizes and sits (there is no geometry anywhere else),
# handlers decide what happens when it is touched, and bindings are how the values a user
# typed or dragged get back out to Tasker variables.
#
# Same in-place discipline as phases 1 and 2 -- lists are mutated, never rebuilt, so a
# component nobody touched still re-encodes to its original bytes.
# --------------------------------------------------------------------------------------

# Modifier types and what each takes.  Order within a node's "modifiers" list is
# significant -- they compose in sequence, so Padding-then-Border draws a different thing
# from Border-then-Padding, which is why the editor offers move up/down rather than sorting.
V2_MODIFIER_SCHEMA: dict[str, tuple[V2Prop, ...]] = {
    "FillWidth": (),
    "FillSize": (),
    "WindowDrag": (),
    "Size": (V2Prop("width", "Width", "number"), V2Prop("height", "Height", "number")),
    "SizeIn": (V2Prop("maxWidth", "Max width", "number"), V2Prop("maxHeight", "Max height", "number")),
    "Padding": (
        V2Prop("all", "All", "number"),
        V2Prop("horizontal", "Horizontal", "number"),
        V2Prop("vertical", "Vertical", "number"),
        V2Prop("start", "Start", "number"),
        V2Prop("end", "End", "number"),
        V2Prop("top", "Top", "number"),
        V2Prop("bottom", "Bottom", "number"),
    ),
    "Clip": (V2Prop("shape", "Shape", "choice", ("Rounded", "Circle")), V2Prop("radius", "Radius", "number")),
    "Border": (
        V2Prop("color", "Colour"),
        V2Prop("shape", "Shape", "choice", ("Rounded", "Circle")),
        V2Prop("radius", "Radius", "number"),
        V2Prop("width", "Width", "number"),
    ),
    "Background": (V2Prop("color", "Colour"),),
    "Align": (V2Prop("alignment", "Alignment", "choice", ("Start", "Center", "End")),),
    "Weight": (V2Prop("amount", "Amount", "number"),),
    "AspectRatio": (V2Prop("ratio", "Ratio"),),
    "Alpha": (V2Prop("value", "Opacity", "number"),),
    "VerticalScroll": (V2Prop("applyWhen", "Apply when"),),
}

# Events a handler can fire on.  screen_variable_changed carries a variableName; the rest
# take no arguments of their own.
V2_EVENT_TYPES = ("click", "hold", "text_changed", "screen_variable_changed")
V2_EVENT_SCHEMA: dict[str, tuple[V2Prop, ...]] = {
    "screen_variable_changed": (V2Prop("variableName", "Variable"),),
}

# What a handler can do.  RunTask's "task" is a Task *name*, which is why the dialog offers
# a picker over the loaded backup's Tasks rather than a free text field.
V2_ACTION_SCHEMA: dict[str, tuple[V2Prop, ...]] = {
    "SetVariable": (V2Prop("variable", "Variable"), V2Prop("value", "Value")),
    "ToggleVariable": (V2Prop("variable", "Variable"),),
    "RunTask": (V2Prop("task", "Task", "task"),),
    "DismissLayout": (V2Prop("result", "Result"),),
    "OutputToVariable": (),
}
V2_ACTION_TYPES = tuple(V2_ACTION_SCHEMA)

# Which components write a value back out, and under what key.  The state object is always
# {"<state>": {"outputVariableBindings": {"<key>": [variable, ...]}}} -- confirmed in the
# 'Dialog' Scene (a TextInput carrying an empty textState) and in every build*() of the
# Scene v2 Dialog project's compiler.
#
# NOTE the compiler is inconsistent about the "%" prefix inside those lists: it writes
# textState as ["%" + var] but sliderValueState as [var]. Both evidently work, so the
# editor shows the stored string as-is and does not normalise either way -- guessing wrong
# would silently repoint a working Scene's output at a different variable.
V2_STATE_BY_TYPE: dict[str, tuple[str, str]] = {
    "TextInput": ("textState", "text"),
    "Slider": ("sliderValueState", "value"),
    "Dropdown": ("selectionState", "selected_indices"),
    "SegmentedButtonRow": ("selectionState", "selected_indices"),
    "Switch": ("selectionState", "selected_indices"),
    "Checkbox": ("selectionState", "selected_indices"),
}
_V2_BINDINGS_KEY = "outputVariableBindings"


def v2_schema_props(schema: dict[str, tuple[V2Prop, ...]], item: dict) -> list[V2Prop]:
    """The editable properties of a modifier / event / action, from its schema plus any
    other scalar key it carries.  The same forward-compatible shape v2_editable_props uses
    for components, and for the same reason: these tables are read off one backup, so
    anything newer must still be visible and editable rather than silently dropped.
    """
    props = list(schema.get(item.get("type", ""), ()))
    known = {prop.key for prop in props}
    for key, value in item.items():
        if key != "type" and key not in known and isinstance(value, (str, int, float, bool)):
            props.append(V2Prop(key, key))
    return props


def v2_modifiers(node: dict) -> list[dict]:
    """This component's modifier list -- always a real list, so callers can index it."""
    modifiers = node.get("modifiers")
    return modifiers if isinstance(modifiers, list) else []


def v2_add_modifier(node: dict, modifier_type: str) -> int:
    """Append a modifier and return its index.  Appends rather than inserts because a
    modifier's position is its place in the composition order, and the end is the only
    position that means "on top of what is already there".
    """
    modifiers = node.setdefault("modifiers", [])
    modifiers.append({"type": modifier_type})
    return len(modifiers) - 1


def v2_delete_modifier(node: dict, index: int) -> None:
    """Remove a modifier, and the whole "modifiers" key with it when the last one goes --
    Tasker writes no empty modifiers list on any component in this repo's backup, and an
    empty one is a difference from what it would have written.
    """
    modifiers = v2_modifiers(node)
    if 0 <= index < len(modifiers):
        del modifiers[index]
    if not modifiers and "modifiers" in node:
        del node["modifiers"]


def v2_move_modifier(node: dict, index: int, offset: int) -> int | None:
    """Reorder a modifier; returns its new index, or None if it can't move that way."""
    modifiers = v2_modifiers(node)
    new_index = index + offset
    if not (0 <= index < len(modifiers) and 0 <= new_index < len(modifiers)):
        return None
    modifiers.insert(new_index, modifiers.pop(index))
    return new_index


def v2_handlers(node: dict) -> list[dict]:
    """This component's event handlers -- always a real list."""
    handlers = (node.get("eventHandlers") or {}).get("handlers")
    return handlers if isinstance(handlers, list) else []


def v2_add_handler(node: dict, event_type: str) -> int:
    """Add an event handler firing on one event, with no actions yet, and return its index.

    A handler with no actions is legal and is the only sensible starting point -- the user
    picks the event first, then says what it should do.
    """
    event_handlers = node.setdefault("eventHandlers", {})
    handlers = event_handlers.setdefault("handlers", [])
    handlers.append({"events": [{"type": event_type}], "actions": []})
    return len(handlers) - 1


def v2_delete_handler(node: dict, index: int) -> None:
    """Remove an event handler, and the whole "eventHandlers" object with it when the last
    one goes -- same reasoning as v2_delete_modifier.  A stopPropagation flag set alongside
    the handlers goes with them, since it only means anything in their company.
    """
    handlers = v2_handlers(node)
    if 0 <= index < len(handlers):
        del handlers[index]
    if not handlers and "eventHandlers" in node:
        del node["eventHandlers"]


def v2_add_action(handler: dict, action_type: str) -> int:
    """Append an action to a handler and return its index.  Order matters: the actions of
    a handler run in sequence, which is how the 'Dialog' Scene's close button sets two
    variables *before* dismissing the layout.
    """
    actions = handler.setdefault("actions", [])
    actions.append({"type": action_type})
    return len(actions) - 1


def v2_delete_action(handler: dict, index: int) -> None:
    """Remove one action from a handler, leaving the handler in place even if empty."""
    actions = handler.get("actions")
    if isinstance(actions, list) and 0 <= index < len(actions):
        del actions[index]


def v2_move_action(handler: dict, index: int, offset: int) -> int | None:
    """Reorder an action within its handler; returns the new index or None."""
    actions = handler.get("actions")
    if not isinstance(actions, list):
        return None
    new_index = index + offset
    if not (0 <= index < len(actions) and 0 <= new_index < len(actions)):
        return None
    actions.insert(new_index, actions.pop(index))
    return new_index


def v2_binding_slot(node: dict) -> tuple[str, str] | None:
    """The (state key, binding key) this component writes its value out through, or None
    if it has no output.

    Falls back to whatever <x>State the node already carries when its type isn't in
    V2_STATE_BY_TYPE, so a binding written by a newer Tasker on a component this app
    doesn't know is still shown and editable rather than hidden.
    """
    known = V2_STATE_BY_TYPE.get(node.get("type", ""))
    if known:
        return known
    for key, value in node.items():
        if key.endswith("State") and isinstance(value, dict) and _V2_BINDINGS_KEY in value:
            bindings = value[_V2_BINDINGS_KEY]
            if isinstance(bindings, dict) and bindings:
                return key, next(iter(bindings))
    return None


def v2_get_binding(node: dict, slot: tuple[str, str]) -> str:
    """The variable this component currently writes to, as a comma-separated string.

    The stored form is a list -- Tasker allows more than one target -- but one is the
    normal case, so the editor is a single field and the list is joined for display.
    """
    state_key, binding_key = slot
    bindings = (node.get(state_key) or {}).get(_V2_BINDINGS_KEY, {})
    values = bindings.get(binding_key) if isinstance(bindings, dict) else None
    if isinstance(values, list):
        return ", ".join(str(value) for value in values)
    return "" if values is None else str(values)


def v2_set_binding(node: dict, slot: tuple[str, str], text: str) -> None:
    """Point this component's output at one or more variables, creating the state object
    if it isn't there.

    Clearing the field leaves an *empty list* rather than deleting the state object,
    because that is exactly what a real Scene contains: the 'Dialog' Scene's filter_bar
    carries "textState": {"outputVariableBindings": {"text": []}} -- the binding declared
    but unset.  Deleting the object instead would be a different document from the one
    Tasker wrote.
    """
    state_key, binding_key = slot
    state = node.setdefault(state_key, {})
    if not isinstance(state, dict):
        state = node[state_key] = {}
    bindings = state.setdefault(_V2_BINDINGS_KEY, {})
    if not isinstance(bindings, dict):
        bindings = state[_V2_BINDINGS_KEY] = {}
    bindings[binding_key] = [part.strip() for part in text.split(",") if part.strip()]


def v2_component_summary(layout: dict) -> list[str]:
    """A flat, indented outline of a V2 layout's component tree -- "Column",
    "  Text 'title_text'", "  IconButton 'close_button'" -- for the read-only
    panel the editor body shows in place of the Legacy element list (see
    guiwins._build_scene_editor_body).  The Legacy counterpart is
    scenes.get_scene_element_names.

    Children hang off more than one key: "children" for a Column/Row, but a
    Scaffold puts them under "topBar", a TopAppBar its title under "title", and
    so on.  Rather than enumerate the container keys -- there is no fixed list,
    and a Tasker update would silently add to it -- this walks into any list
    whose entries are themselves components (dicts with a "type"), which is what
    every one of those keys holds.  "modifiers" and "eventHandlers" are skipped
    by name: they are lists of dicts with a "type" too, but they describe a
    component rather than being one, so including them would bury the structure.
    """
    lines: list[str] = []

    def walk(component: dict, depth: int) -> None:
        component_type = component.get("type", "?")
        component_id = component.get("id", "")
        lines.append(f"{'  ' * depth}{component_type}" + (f" '{component_id}'" if component_id else ""))
        for key, value in component.items():
            if key in ("modifiers", "eventHandlers") or not isinstance(value, list):
                continue
            for item in value:
                if isinstance(item, dict) and "type" in item:
                    walk(item, depth + 1)

    root = layout.get(_V2_ROOT_KEY)
    if isinstance(root, dict):
        walk(root, 0)
    return lines


def resolve_scene_by_name(scene_name: str) -> defusedxml.ElementTree.Element | None:
    """Look up a Scene's live XML element by its name (also its all_scenes key).

    Callers must not mutate the returned element directly -- go through
    load_scene_for_edit() instead.
    """
    entry = PrimeItems.tasker_root_elements.get("all_scenes", {}).get(scene_name)
    return None if entry is None else entry["xml"]


def load_scene_for_edit(scene_name: str) -> EditableScene | None:
    """Resolve a Scene by name and deep-copy it -- the one point of contact with
    the live tree, so the in-memory backup is never touched until Rename is
    applied.  Mirrors projedit.load_project_for_edit.
    """
    live_element = resolve_scene_by_name(scene_name)
    if live_element is None:
        return None
    return EditableScene(scene_name=scene_name, scene_element=copy.deepcopy(live_element))


def new_v2_layout(name: str) -> dict:
    """The component tree a brand-new Version 2 Scene starts with: a single
    centred Column holding nothing, plus the Scene's name.

    Modelled on the smallest real V2 Scene in XML/backup.xml ('Torch Slider v2',
    the 'Flashlight Slider' Project's) with its one child removed -- same root
    type, same keys, same order -- rather than invented, so what Tasker's Screen
    Builder opens is a shape it already writes itself.  Deliberately no
    "defaultDisplayMode": only one of the three real V2 Scenes sets it, so it is
    optional and Tasker's own default is the right thing for a new Scene.
    """
    return {
        _V2_ROOT_KEY: {
            "type": "Column",
            "id": "Column1",
            "horizontalAlignment": "Center",
            "verticalArrangement": "Center",
            "children": [],
        },
        _V2_NAME_KEY: name,
    }


def _v2_dismiss_actions(label: str) -> list[dict]:
    """The action list a dialog button runs: record which button was pressed, then close.

    Copied from the 'Dialog' Scene's own close button rather than invented -- it writes
    sd_button_index and sd_button before DismissLayout, and those two names are what the
    'Scene v2 Dialog' project's Task reads back afterwards. A template that used different
    variable names would look right and return nothing.
    """
    return [
        {"type": "SetVariable", "variable": "sd_button", "value": label},
        {"type": "DismissLayout"},
    ]


def _v2_template_dialog(name: str, *, with_buttons: bool) -> dict:
    """A titled dialog: header row with a title and a close button, then a content column.

    This is the 'Dialog' Scene of the 'Scene v2 Dialog' project, reduced to its frame --
    same root Column with the rounded border, same SpaceBetween header, same close button
    behaviour -- with its runtime-injected body replaced by an ordinary Text the user can
    edit or delete.
    """
    children: list[dict] = [
        {
            "type": "Row",
            "id": "header",
            "horizontalArrangement": "SpaceBetween",
            "verticalAlignment": "Center",
            "modifiers": [{"type": "FillWidth"}, {"type": "Padding", "all": "8"}],
            "children": [
                {"type": "Text", "id": "title_text", "text": "Title", "textSize": "22"},
                {
                    "type": "IconButton",
                    "id": "close_button",
                    "icon": "icon:Close",
                    "contentScale": "FillBounds",
                    "eventHandlers": {
                        "handlers": [{"events": [{"type": "click"}], "actions": _v2_dismiss_actions("Close")}],
                    },
                },
            ],
        },
        {
            "type": "Column",
            "id": "content",
            "horizontalAlignment": "Center",
            "verticalArrangement": "Center",
            "spacing": "8",
            "modifiers": [{"type": "FillWidth"}, {"type": "Padding", "horizontal": "16", "bottom": "8"}],
            "children": [{"type": "Text", "id": "body_text", "text": "Body text"}],
        },
    ]

    if with_buttons:
        children.append(
            {
                "type": "Row",
                "id": "button_row",
                "horizontalArrangement": "End",
                "verticalAlignment": "Center",
                "spacing": "8",
                "modifiers": [{"type": "FillWidth"}, {"type": "Padding", "all": "8"}],
                "children": [
                    {
                        "type": "Button",
                        "id": f"button_{index}",
                        "text": label,
                        "eventHandlers": {
                            "handlers": [{"events": [{"type": "click"}], "actions": _v2_dismiss_actions(label)}],
                        },
                    }
                    for index, label in enumerate(("Cancel", "OK"), start=1)
                ],
            },
        )

    return {
        _V2_ROOT_KEY: {
            "type": "Column",
            "id": "root_column",
            "horizontalAlignment": "Center",
            "verticalArrangement": "Center",
            "modifiers": [
                {"type": "FillWidth"},
                {"type": "Border", "color": "outline", "shape": "Rounded", "radius": "16"},
            ],
            "children": children,
        },
        _V2_NAME_KEY: name,
    }


def _v2_template_full_screen(name: str) -> dict:
    """A full-screen app frame: top bar, bottom navigation, and a content column.

    Modelled on the 'V2' Scene of the 'Test' project -- the only real example of a Scaffold
    in this repo's backup -- so the slot names (topBar / bottomBar / content) and the
    NavigationItem shape match something Tasker demonstrably opens.
    """
    return {
        _V2_ROOT_KEY: {
            "type": "Scaffold",
            "id": "Scaffold1",
            "topBar": [
                {
                    "type": "TopAppBar",
                    "id": "TopAppBar1",
                    "title": [{"type": "Text", "id": "Text1", "text": "Title", "textSize": "22"}],
                },
            ],
            "bottomBar": [
                {
                    "type": "NavigationBar",
                    "id": "NavBar1",
                    "content": [
                        {"type": "NavigationItem", "id": f"NavItem{index}", "icon": icon, "label": label}
                        for index, (icon, label) in enumerate(
                            (("icon:Home", "Home"), ("icon:Search", "Search"), ("icon:Settings", "Settings")),
                            start=1,
                        )
                    ],
                },
            ],
            "content": [
                {
                    "type": "Column",
                    "id": "Column1",
                    "horizontalAlignment": "Center",
                    "verticalArrangement": "Center",
                    "children": [{"type": "Text", "id": "Text2", "text": "Content"}],
                },
            ],
        },
        _V2_NAME_KEY: name,
    }


# The starting points Add Scene offers for a Version 2 Scene, in the order it lists them.
# Each entry is (label, description, builder).  Every one of these is traced to a Scene in
# XML/backup.xml rather than composed from the schema, because the schema says what is
# *possible* and these Scenes are evidence of what Tasker actually opens.
V2_TEMPLATES: tuple[tuple[str, str, object], ...] = (
    ("Empty", "A single centred Column to build in.", new_v2_layout),
    (
        "Titled dialog",
        "Header with a title and close button, and a content area.",
        lambda name: _v2_template_dialog(name, with_buttons=False),
    ),
    (
        "Dialog with buttons",
        "A titled dialog plus a Cancel / OK row that reports which was pressed.",
        lambda name: _v2_template_dialog(name, with_buttons=True),
    ),
    ("Full screen", "Scaffold with a top bar, bottom navigation and content.", _v2_template_full_screen),
)
V2_DEFAULT_TEMPLATE = V2_TEMPLATES[0][0]


def v2_template_layout(name: str, template: str) -> dict:
    """Build the named template's component tree.  Falls back to the empty one for a name
    that isn't offered, so a stale caller degrades to "blank Scene" rather than failing.
    """
    for label, _description, builder in V2_TEMPLATES:
        if label == template:
            return builder(name)
    return new_v2_layout(name)


def create_new_scene(
    name: str,
    version: str = SCENE_VERSION_LEGACY,
    template: str = V2_DEFAULT_TEMPLATE,
) -> EditableScene | str:
    """Build a brand-new, empty Scene element of either kind, not tied to any
    existing one.  Returns an error message string if no backup is loaded (needed
    to source the correct Element class -- see projedit.create_new_project's
    identical note).

    version is SCENE_VERSION_LEGACY or SCENE_VERSION_V2 -- the choice the Add
    Scene button prompts for before this is ever called (see
    guiwins.build_add_scene_version_dialog).  It decides two things, and they go
    together:

      * V2 gets an <lj> child holding new_v2_layout(); Legacy gets none.
      * V2's size children are all -1, Legacy's get a real portrait canvas.
        A V2 layout is declarative -- Column/Row/modifiers, not x/y geometry --
        so there is no canvas to size, and every real V2 Scene carries -1 across
        all four (see this module's docstring).  Handing a V2 Scene 600x800 would
        be inventing a constraint Tasker doesn't use.

    No <id> child, and no id counter to consult: unlike Task/Profile (a shared
    integer counter, see taskedit.next_unique_task_or_profile_id) and unlike
    Project (a UUID), a Scene has no <id> element at all in any Tasker backup --
    its name is its identity.  That is also why sr is "scene<name>" rather than
    a "sceneN" index; see this module's docstring.

    Children are emitted in the alphabetical order real Tasker Scenes use
    (cdate, edate, heightLand, heightPort, [lj,] nme, widthLand, widthPort) --
    note <lj> falls between heightPort and nme, exactly where all three real V2
    Scenes carry it -- so a round-trip through render_standalone_scene_xml
    matches what Tasker writes.  The Scene starts empty either way: adding
    elements/components is the part still to come (see this module's docstring).
    """
    if PrimeItems.xml_root is None:
        return "Load a Tasker backup file first (Add Scene needs it to build the Scene)."
    if version not in SCENE_VERSIONS:
        return f"'{version}' is not a kind of Scene. Choose {' or '.join(SCENE_VERSIONS)}."

    element_cls = type(PrimeItems.xml_root)
    clean_name = name.strip()
    is_v2 = version == SCENE_VERSION_V2
    scene_element = element_cls("Scene", {"sr": f"scene{clean_name}"})

    now_millis = str(int(time.time() * 1000))
    portrait_width = UNSET_DIMENSION if is_v2 else NEW_SCENE_WIDTH_PORTRAIT
    portrait_height = UNSET_DIMENSION if is_v2 else NEW_SCENE_HEIGHT_PORTRAIT
    for tag, text in (
        ("cdate", now_millis),
        ("edate", now_millis),
        ("heightLand", UNSET_DIMENSION),
        ("heightPort", portrait_height),
        ("nme", clean_name),
        ("widthLand", UNSET_DIMENSION),
        ("widthPort", portrait_width),
    ):
        child = element_cls(tag)
        child.text = text
        scene_element.append(child)

    if is_v2:
        # encode_v2_layout appends <lj> at the end; move it into alphabetical
        # position (after heightPort) so the child order matches a real V2 Scene's.
        encode_v2_layout(scene_element, v2_template_layout(clean_name, template))
        layout_element = scene_element.find(V2_LAYOUT_TAG)
        scene_element.remove(layout_element)
        scene_element.insert(list(scene_element).index(scene_element.find("nme")), layout_element)

    return EditableScene(scene_name=clean_name, scene_element=scene_element)


def scene_name_exists(name: str) -> bool:
    """Whether a Scene with this name already exists in the currently loaded backup."""
    return name.strip() in PrimeItems.tasker_root_elements.get("all_scenes", {})


def apply_edits_to_scene(edited_scene: EditableScene, new_name: str) -> list[str]:
    """Validate the new name, and only if valid, write it into the Scene copy's
    <nme> child AND its sr attribute (both carry the name -- see this module's
    docstring).  All-or-nothing, mirrors projedit.apply_edits_to_project.

    A no-op rename (new_name == edited_scene.scene_name) is allowed through --
    it's not a conflict with itself.

    A comma in the name is rejected, which no other object type has to care
    about: a Project lists the Scenes it owns as one comma-separated <scenes>
    string, so a Scene called "Big,Red" would read back as two Scenes named
    "Big" and "Red" and neither would resolve.

    For a Version 2 Scene there is a third place the name lives -- inside the
    <lj> layout JSON -- and _rename_v2_layout keeps it in step.  Nothing else in
    this module has to know: for a Legacy Scene that call does nothing.
    """
    errors = []

    new_name = new_name.strip()
    if not new_name:
        errors.append("Scene name cannot be empty.")
    elif "," in new_name:
        errors.append(
            "Scene name cannot contain a comma -- a Project lists its Scenes as one comma-separated name list.",
        )
    elif new_name != edited_scene.scene_name and scene_name_exists(new_name):
        errors.append(f"A Scene named '{new_name}' already exists in this backup. Choose a different name.")

    if errors:
        return errors

    _set_child_text(edited_scene.scene_element, "nme", new_name)
    edited_scene.scene_element.set("sr", f"scene{new_name}")
    _rename_v2_layout(edited_scene.scene_element, new_name)
    touch_scene_edate(edited_scene.scene_element)
    # Keep scene_name in sync with the applied <nme> -- register_new_scene keys
    # all_scenes by it, so a brand-new Scene (created with name "") would
    # otherwise be registered under "" and show up nameless in the Scene pulldown.
    edited_scene.scene_name = new_name
    return []


def _set_child_text(parent: defusedxml.ElementTree.Element, tag: str, text: str) -> None:
    child = parent.find(tag)
    if child is None:
        # Match parent's actual Element class (see projedit._set_child_text's
        # identical note) -- ETW.SubElement() would build a stdlib-class child.
        child = type(parent)(tag)
        parent.append(child)
    child.text = text


def touch_scene_edate(scene_element: defusedxml.ElementTree.Element) -> None:
    """Stamps a Scene's <edate> with the current time.  A Scene uses <edate> for
    "last modified", the way Task/Profile do -- not <mdate>, which is the
    Project-only spelling (see projedit.touch_project_mdate).  Confirmed against
    this repo's own backup.xml: every Scene has <cdate>+<edate>, none has <mdate>.
    """
    _set_child_text(scene_element, "edate", str(int(time.time() * 1000)))


def set_scene_dimensions(edited_scene: EditableScene, dimensions: dict[str, str]) -> None:
    """Writes the Scene copy's size children (see SCENE_DIMENSION_FIELDS) and
    stamps <edate>.  Separate from apply_edits_to_scene because the two answer to
    different buttons -- the name is applied by Rename/Ok, the size by every save
    path -- and because unlike the name, a size can't collide with anything, so
    there is nothing here to validate against the rest of the backup.  Whether
    the values are well-formed is the caller's business (see
    userintr._apply_scene_field_values, which checks them before calling this).
    """
    for tag, value in dimensions.items():
        _set_child_text(edited_scene.scene_element, tag, value)
    touch_scene_edate(edited_scene.scene_element)


def register_new_scene(edited_scene: EditableScene) -> None:
    """Adds a new Scene to the in-memory backup's all_scenes table so it behaves
    like any other Scene loaded from the backup -- so it shows up in the Scene
    pulldown, and so a second Add Scene with the same name is caught by
    scene_name_exists().  Call once, right after a successful Add Scene, and
    follow it with add_scene_to_project: registration alone leaves the Scene in
    a table nothing walks (see that function).
    """
    PrimeItems.tasker_root_elements.setdefault("all_scenes", {})[edited_scene.scene_name] = {
        "xml": edited_scene.scene_element,
        "name": edited_scene.scene_name,
    }


def add_scene_to_project(scene_name: str, project_name: str) -> None:
    """Attaches a newly-registered Scene to a Project by appending its *name* to
    that Project's <scenes> element -- the mechanism Tasker, and every view this
    app generates, uses to know which Scenes belong to which Project:
    scenes.process_project_scenes splits exactly this element, and
    projects.process_project_scenes' caller walks it for the Map/Diagram/Tree
    output.  Names, not ids -- a Scene has no <id>; see this module's docstring.

    Without this, register_new_scene alone leaves a Scene sitting only in the
    all_scenes lookup table, which only the Scene pulldown reads -- so it exists
    and can be selected, but appears in no generated view at all.  This is the
    exact Scene analogue of profedit.add_profile_to_project's <pids> append.

    Mutates the Project's XML element in place (not a copy) -- the live Project
    table is already in PrimeItems.tasker_root_elements, so this takes effect
    immediately for every other view in the same session.  No-op if project_name
    isn't a known Project (defense in depth; the GUI only offers real names).
    """
    project_entry = PrimeItems.tasker_root_elements.get("all_projects", {}).get(project_name)
    if project_entry is None:
        return

    project_element = project_entry["xml"]
    existing_names = _project_scene_names(project_element)
    if scene_name not in existing_names:
        existing_names.append(scene_name)
    _set_child_text(project_element, "scenes", ",".join(existing_names))
    touch_project_mdate(project_element)


def _project_scene_names(project_element: defusedxml.ElementTree.Element) -> list[str]:
    """Reads a Project's <scenes> as a list of Scene names, empty-safe.  The
    element is one comma-separated string; an empty or absent one is no Scenes.
    """
    child = project_element.find("scenes")
    if child is None or not child.text:
        return []
    return [name for name in child.text.split(",") if name]


def _set_project_scene_names(
    project_element: defusedxml.ElementTree.Element,
    scene_names: list[str],
) -> None:
    """Writes a Project's <scenes> back, removing the element entirely when the
    last Scene is gone rather than leaving an empty one behind -- an empty
    <scenes/> is not something Tasker itself ever writes, and
    scenes.process_project_scenes' own `if scene_list[0]` guard exists precisely
    because an empty string splits to [""] and would otherwise be processed as a
    Scene with no name.
    """
    child = project_element.find("scenes")
    if not scene_names:
        if child is not None:
            project_element.remove(child)
        return
    _set_child_text(project_element, "scenes", ",".join(scene_names))


def apply_edited_scene_to_live_tree(old_name: str, edited_scene: EditableScene) -> None:
    """Writes an edited (pre-existing) Scene back into the in-memory backup: its
    contents onto the live element, its all_scenes entry under whatever name it
    now carries, and -- if that name changed -- the <scenes> list of every
    Project that referenced the old one.

    The first of those three is the part that has to be a transplant, and is the
    one place this deliberately diverges from
    profedit.apply_edited_profile_to_live_tree/projedit.rename_project_in_live_tree,
    both of which simply swap the edited deep copy into the table in place of the
    old object.  Those get away with it because maputil2.write_full_backup_to_
    current_file reconciles by <id>, which survives a rename.  A Scene has no
    <id>, so that same function has to match it by <nme> -- and an object swap
    plus a rename means the tree's element still says the old name while the
    table's says the new one, so nothing matches: the old element is orphaned
    into the saved file and the renamed one is appended alongside it, leaving two
    Scenes where there was one.  (Observed, not theorized -- 50 Scenes in, 52
    out.)  Copying the edit *onto* the live element instead keeps one object
    carrying one name, so the deep copy the save takes of the tree and the entry
    in the table are the same Scene under the same name, whatever it was renamed
    to.

    The <scenes> sweep is the part with no Project/Profile/Task equivalent at
    all: those are referenced by id, which a rename doesn't change, whereas every
    reference to a Scene is by name and so goes stale the moment the name does.

    Safe to call when nothing was renamed -- that is the ordinary "Ok" path,
    which lands the size edits and leaves the name where it was.

    No-op if old_name isn't registered (defense in depth; the GUI should only
    ever pass a name that was just loaded via load_scene_for_edit).
    """
    all_scenes = PrimeItems.tasker_root_elements.get("all_scenes", {})
    entry = all_scenes.get(old_name)
    if entry is None:
        return

    live_element = entry["xml"]
    edited_element = edited_scene.scene_element
    if live_element is not edited_element:
        live_element.attrib.clear()
        live_element.attrib.update(edited_element.attrib)
        for child in list(live_element):
            live_element.remove(child)
        for child in list(edited_element):
            live_element.append(child)
    # From here on the model and the tree are the same element, so a second save
    # from the still-open dialog transplants onto itself and is a no-op.
    edited_scene.scene_element = live_element

    new_name = live_element.findtext("nme", "") or old_name
    if new_name != old_name:
        del all_scenes[old_name]
        for project_entry in PrimeItems.tasker_root_elements.get("all_projects", {}).values():
            project_element = project_entry["xml"]
            scene_names = _project_scene_names(project_element)
            if old_name not in scene_names:
                continue
            # Positional replace, not remove-then-append: a Project's <scenes>
            # order is the order its Scenes are listed in every view, and a
            # rename is not a reordering.
            scene_names[scene_names.index(old_name)] = new_name
            _set_project_scene_names(project_element, scene_names)
            touch_project_mdate(project_element)

    all_scenes[new_name] = {"xml": live_element, "name": new_name}
    edited_scene.scene_name = new_name


def count_scene_references(scene_name: str) -> int:
    """How many Projects currently list this Scene in their <scenes> -- for the
    Delete confirmation dialog's "it will be removed from N Project(s)" message,
    read live off the Project table before anything is mutated.  Mirrors
    projedit.count_project_contents/taskedit.count_task_references.

    Counts Projects only.  Task actions that name the Scene (Show Scene, Hide
    Scene, Destroy Scene) are NOT counted, because delete_scene does not touch
    them -- see this module's docstring.
    """
    return sum(
        1
        for project_entry in PrimeItems.tasker_root_elements.get("all_projects", {}).values()
        if scene_name in _project_scene_names(project_entry["xml"])
    )


def delete_scene(scene_name: str) -> list[str]:
    """Deletes a Scene from the in-memory backup and removes it from every
    Project's <scenes> list.  Returns [] on success, else a list of error
    strings (mirrors projedit.delete_project's convention), and mutates nothing
    on error.

    Nothing is deleted below it: a Scene's elements live inside the Scene
    element itself and go with it, and any Task those elements fire is a
    top-level Task owned by a Project, which is left exactly where it is (the
    same call the Delete Task dialog spells out in reverse).
    """
    all_scenes = PrimeItems.tasker_root_elements.get("all_scenes", {})
    if scene_name not in all_scenes:
        return [f"Scene '{scene_name}' no longer exists."]

    for project_entry in PrimeItems.tasker_root_elements.get("all_projects", {}).values():
        project_element = project_entry["xml"]
        scene_names = _project_scene_names(project_element)
        if scene_name not in scene_names:
            continue
        scene_names.remove(scene_name)
        _set_project_scene_names(project_element, scene_names)
        touch_project_mdate(project_element)

    del all_scenes[scene_name]
    return []


def sanitize_filename(name: str) -> str:
    """Strip characters illegal in filenames from a Scene name (minimal, not a
    full slugify).  Mirrors projedit/profedit/taskedit's own copies exactly,
    with the type-appropriate fallback.
    """
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip() or "scene"


def default_scene_save_path(scene_name: str) -> str:
    """Default standalone-export path: {current runtime directory}/{sanitized name}.scn.xml."""
    return os.path.join(os.getcwd(), f"{sanitize_filename(scene_name)}.scn.xml")


def save_path_exists(output_path: str) -> bool:
    """Whether a file already sits at this save path (would be silently overwritten).
    Mirrors projedit.save_path_exists.
    """
    return bool(output_path) and os.path.exists(output_path)


def android_scene_path(scene_name: str) -> str:
    """The absolute path a Save To Android of this Scene would write to on the
    device.  Single source of truth for that path -- save_scene_to_android
    writes here and the GUI's overwrite check reads it back through
    maputil2.file_exists_on_android, so the two must never drift apart.  See
    projedit.android_project_path for the sanitized-name collision this shares.
    """
    return f"/{ANDROID_SCENE_LOCATION}/{sanitize_filename(scene_name)}.scn.xml"


def render_standalone_scene_xml(scene_name: str) -> str:
    """Render a Scene as a standalone TaskerData/Scene XML string, matching the
    shape Tasker's own Scene export produces (verified against this repo's
    Electric_Blanket.scn.xml: a TaskerData root holding one <Scene>, which keeps
    its sr="scene<name>" and all of its UI elements).

    Simpler than projedit.render_standalone_project_xml in the one way that
    matters: there is nothing to bundle.  A Project export has to gather the
    Profiles and Tasks its ids point at; a Scene's UI elements are children of
    the Scene element itself, so a deep copy of that one element is the whole
    export.  Nothing is stripped either -- a Scene has no <id>/<clr>/<mdate> to
    omit, and its sr carries the name rather than a document position, so unlike
    a Project's sr="proj0" there is nothing to renumber.

    Task actions the Scene's elements fire (ClickTask and friends) are NOT
    bundled -- the same deliberate non-recursion as the Project export.

    Raises ValueError if scene_name isn't a currently-loaded Scene.
    """
    scene_entry = PrimeItems.tasker_root_elements.get("all_scenes", {}).get(scene_name)
    if scene_entry is None:
        msg = f"Scene '{scene_name}' no longer exists in this backup."
        raise ValueError(msg)

    scene_copy = copy.deepcopy(scene_entry["xml"])
    tv = PrimeItems.xml_root.attrib.get("tv", "") if PrimeItems.xml_root is not None else ""

    # Match the parsed tree's actual Element class (see projedit's identical note).
    element_cls = type(scene_copy)
    root = element_cls("TaskerData", {"sr": "", "dvi": "1", "tv": tv})
    root.append(scene_copy)

    ETW.indent(root, space="\t")
    # No <?xml ...?> declaration -- see profedit.render_standalone_profile_xml.
    return ETW.tostring(root, encoding="unicode") + "\n"


def write_standalone_scene_xml(scene_name: str, output_path: str) -> None:
    """Write a Scene as a standalone .scn.xml file.  Raises OSError on failure,
    ValueError if the Scene no longer exists.
    """
    rendered = render_standalone_scene_xml(scene_name)
    with open(output_path, "w", encoding="utf-8") as out_file:
        out_file.write(rendered)


def save_scene_to_android(scene_name: str, ip_address: str, ip_port: str) -> tuple[int, str]:
    """Writes the Scene onto the Android device's storage under /Tasker/scenes,
    via the same POST /upload mechanism as projedit.save_project_to_android (see
    that function's docstring for why a readback-verify is required, and why
    this does not touch Tasker's live configuration).

    Returns (0, device_file_path) on success, or (return_code, error_message).
    """
    # Lazy import to avoid a circular-import error (mirrors getbakup.get_backup_file()).
    from maptasker.src.maputil2 import http_request, http_upload_request  # noqa: PLC0415

    ip_address = ip_address.strip()
    ip_port = ip_port.strip()
    if not ip_address or not ip_port:
        return 8, "Android IP address and port are required."

    try:
        xml_bytes = render_standalone_scene_xml(scene_name).encode("utf-8")
    except ValueError as e:
        return 8, str(e)

    device_path = android_scene_path(scene_name)
    filename = device_path.rsplit("/", 1)[-1]

    return_code, response = http_upload_request(ip_address, ip_port, ANDROID_SCENE_LOCATION, filename, xml_bytes)
    if return_code != 0:
        return return_code, str(response)

    verify_code, verify_content = http_request(ip_address, ip_port, device_path, "file", "")
    if verify_code != 0 or verify_content != xml_bytes:
        return 8, f"Uploaded to {device_path}, but could not confirm it landed correctly."

    return 0, device_path
