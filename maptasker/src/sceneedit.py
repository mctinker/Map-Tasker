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
import html
import io
import json
import os
import re
import time
import xml.etree.ElementTree as ETW  # stdlib "ET Write" -- used only to build/serialize
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import defusedxml.ElementTree

from maptasker.src.primitem import PrimeItems
from maptasker.src.projedit import touch_project_mdate
from maptasker.src.sysconst import SCENE_TASK_TYPES

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

    element_renames records (old name, new name) for every Legacy element the
    designer has renamed, in the order they were renamed, when the user asked for
    the Tasks that address them to be brought along.  It is deliberately a
    *pending* list rather than an edit already made: renaming an element inside
    this dialog changes a deep copy that Cancel throws away, but the Tasks it
    would rewrite are the live ones, so rewriting them as the rename is typed
    would leave a cancelled edit half-applied to the backup.  They are applied by
    apply_edited_scene_to_live_tree -- the single point at which this copy becomes
    the real Scene -- and by nothing else.
    """

    scene_name: str
    scene_element: defusedxml.ElementTree.Element
    element_renames: list[tuple[str, str]] = field(default_factory=list)


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
    as a pulldown).  "textvar", "numvar" and "colorvar" are those three plus a Select
    Variable picker, for the properties Tasker lets you point at a variable instead of
    filling in -- see V2_TEXT_CATEGORIES.

    `container` names the nested dict inside the node the property actually lives in, for the
    ones that are not a top-level key: a Text's font, spacing and decoration all sit inside
    its "textStyle" object rather than on the component itself.  Empty -- the ordinary case --
    means the node's own key.  v2_prop_dict is what turns this into something to read and
    write, and why it is a name here rather than a dict reference: the container is created
    only when something is first written into it, so an untouched Scene never grows one.
    """

    key: str
    label: str
    kind: str = "text"
    choices: tuple[str, ...] = ()
    container: str = ""


# Every component carries an id, so it is offered first for all of them rather than
# repeated in each entry below.  Phase 1 shows it read-only: renaming an id means finding
# every condition/showWhen/action that names it, which is phase 2's job (see the design
# sketch's round-trip rules).
V2_ID_PROP = V2Prop("id", "Component id")

# Properties every component can carry, whatever its type, appended after its own schema.
# They are here rather than repeated per type because the 'V2New' Scene shows them turning up
# on components of completely unrelated kinds -- treeLabel on a ProgressBar, a Camera, a Box
# and a Card; showWhen on a ProgressBar, a Camera and a RangeSlider as well as the TextInput
# and Button they were first seen on.
#
# treeLabel is Tasker's own name for the component in the Screen Builder's tree, which is why
# v2_node_label prefers it over the raw type when it is set: the designer's tree should read
# the way the Screen Builder's does.
V2_UNIVERSAL_PROPS: tuple[V2Prop, ...] = (
    V2Prop("showWhen", "Show when"),
    V2Prop("showWhenMode", "Hidden as", "choice", ("Gone", "Invisible")),
    V2Prop("treeLabel", "Tree label"),
)

# The two states that settle nothing themselves and instead carry a value: Dynamic, whose
# value is typed, and Select Variable, whose value is picked from the same categories the Show
# When picker offers.  Both write the one property -- they are two ways of filling it in, not
# two things to fill in -- which is why they are states of the same pulldown.
V2_DYNAMIC_STATE = "Dynamic"
V2_VARIABLE_STATE = "Select Variable"


@dataclass(frozen=True)
class V2StateField:
    """A property set from a short list of named states.

    Tasker's Screen Builder offers several of these and they all work the same way: two or
    three states that settle the property outright, plus the two open ones above, which settle
    nothing and instead carry a value to be evaluated when the Scene is shown.  That is why
    these are their own kind of input rather than a "choice": a choice stores what was picked,
    and this stores what was picked *or* what was written beside it.

    `fixed` pairs each settling state with what it stores, because the two are not always the
    same word: Enabled's On stores "true", while Content format's Plain stores "Plain".

    `types` is which components offer the field.  It is here rather than in
    V2_COMPONENT_SCHEMA because these fields have to sit directly below Show when -- Tasker
    groups them there, and they read as a set: whether the component is there, whether it
    responds, how it reads what it is given.  Everything in V2_COMPONENT_SCHEMA is offered
    *above* the universal properties, which is where Show when lives.

    `modifier` names the modifier type a field belongs to, for the ones that are a modifier's
    value rather than a component's property (Weight).  Those are offered by
    V2_MODIFIER_SCHEMA on the modifier itself and nowhere else, so a component that happens to
    carry a key of the same name is not handed a pulldown meant for something else.

    `grouped` says the same thing about a field that belongs to a category group rather than
    to the run below Show when -- everything a Text offers under Behaviour, Font, Decoration
    and Paragraph.  Without it _v2_universal_props would splice all fifteen of them in above
    the very categories that exist to organise them.

    `container` is V2Prop's, and means the same: the nested dict the property lives in.
    """

    key: str
    label: str
    fixed: tuple[tuple[str, str], ...]
    types: frozenset[str]
    modifier: str = ""
    grouped: bool = False
    container: str = ""

    @property
    def states(self) -> tuple[str, ...]:
        """What the pulldown offers: the settling states in order, then the two open ones."""
        return (*(state for state, _ in self.fixed), V2_DYNAMIC_STATE, V2_VARIABLE_STATE)

    @property
    def prop(self) -> V2Prop:
        """This field as the inspector's own kind of property."""
        return V2Prop(self.key, self.label, "state", container=self.container)


# What Enabled's On and Off actually store.  Strings, not JSON booleans, because that is what
# Tasker writes for a component property: every boolean-valued property in the V2 Scenes in
# XML/backup.xml -- autoPlay, loop, allowFileAccess, showStopIndicator, animateChanges -- is
# the *string* "true" or "false".  (The one real JSON bool anywhere in those layouts,
# stopPropagation, is on an event handler rather than a component.)
V2_ENABLED_ON = "true"
V2_ENABLED_OFF = "false"

# How heavy the text is drawn, lightest first -- Compose's own FontWeight scale, which is what
# the Screen Builder is offering.  Each stores the name it shows; v2_state_of matches them
# loosely enough that a Scene spelling one "ExtraLight" and this table spelling it
# "Extra Light" still read as the same weight.
V2_FONT_WEIGHTS: tuple[str, ...] = (
    "Thin",
    "Extra Light",
    "Light",
    "Normal",
    "Medium",
    "SemiBold",
    "Bold",
    "ExtraBold",
    "Black",
)

# --- A Text's own styling, which is where nearly all of it lives ----------------------------
#
# Everything about how a Text is *drawn* -- its font, its spacing, its decoration, how its
# paragraphs are laid out -- sits in one nested object rather than on the component, and this
# is that object's key.  The properties below name it through V2Prop.container, and the
# container is created only when one of them is first written (see v2_prop_dict): a Scene whose
# Text carries no textStyle must not grow an empty one just for being opened.
V2_TEXT_STYLE = "textStyle"

# The Screen Builder's font weights, spelled the way it spells them.  Separate from
# V2_FONT_WEIGHTS -- which is the Weight *modifier's* scale and spells the second one
# "Extra Light" -- because these are what a Scene's textStyle.fontWeight actually holds
# ("SemiBold", "ExtraBold" and "Bold" all appear in XML/backup.xml).  v2_state_of matches
# loosely enough that either spelling lands on the same weight whichever table reads it.
_TEXT_FONT_WEIGHTS: tuple[str, ...] = (
    "Thin",
    "ExtraLight",
    "Light",
    "Normal",
    "Medium",
    "SemiBold",
    "Bold",
    "ExtraBold",
    "Black",
)

# Compose's own named type scale, largest first, which is what the Screen Builder's Preset
# pulldown is offering.  TitleLarge, TitleMedium and BodySmall are the three that appear in
# XML/backup.xml; the rest of the scale is listed with them because a scale with three of its
# fifteen steps offered is not a scale.
_TYPOGRAPHY_PRESETS: tuple[str, ...] = (
    "DisplayLarge",
    "DisplayMedium",
    "DisplaySmall",
    "HeadlineLarge",
    "HeadlineMedium",
    "HeadlineSmall",
    "TitleLarge",
    "TitleMedium",
    "TitleSmall",
    "BodyLarge",
    "BodyMedium",
    "BodySmall",
    "LabelLarge",
    "LabelMedium",
    "LabelSmall",
)

# The font families Compose resolves by name on any device -- so, the ones that can be offered
# rather than typed.  Monospace and Cursive are both in XML/backup.xml; the other three are the
# rest of the same set.  A family outside it (an installed font, say) is still reachable
# through Dynamic, which is why this being a short list costs nothing.
_FONT_FAMILIES: tuple[str, ...] = ("Default", "SansSerif", "Serif", "Monospace", "Cursive")


def _switch(on: str = V2_ENABLED_ON, off: str = V2_ENABLED_OFF) -> tuple[tuple[str, str], ...]:
    """An On/Off pair as V2StateField.fixed wants it, for the several Text properties that are
    exactly a switch: On stores one string, Off the other.  Defaulted to Enabled's "true" and
    "false", which is what all but one of them store.
    """
    return (("On", on), ("Off", off))


def _states(*names: str) -> tuple[tuple[str, str], ...]:
    """States whose stored value is the name shown, which is all of Tasker's own enums."""
    return tuple((name, name) for name in names)


# The state fields.  The component ones come in the order they are offered -- which is the
# order Tasker's own Screen Builder puts them in, directly below Show when.
#
# Everything marked grouped=True is offered through V2_TEXT_CATEGORIES instead and nowhere
# else; see V2StateField.grouped.
V2_STATE_FIELDS: tuple[V2StateField, ...] = (
    V2StateField("enabled", "Enabled", _switch(), frozenset({"Text"})),
    # Markdown as well as Plain and Html: a Text in XML/backup.xml carries "Markdown", and
    # without it here that Scene's Content format would open on Dynamic and read as a typed
    # expression rather than as the setting it is.
    V2StateField("contentFormat", "Content format", _states("Plain", "Html", "Markdown"), frozenset({"Text"})),
    # A modifier's value rather than a component's property, so it carries no component types
    # and is reached only through V2_MODIFIER_SCHEMA's "Weight" entry.
    V2StateField(
        "amount",
        "Weight",
        tuple((weight, weight) for weight in V2_FONT_WEIGHTS),
        frozenset(),
        modifier="Weight",
    ),
    # ---- Behaviour.  Top-level keys on the component, unlike everything below them.
    # "Ellipsis" is Compose's spelling and the one in XML/backup.xml.
    V2StateField("overflow", "Overflow", _states("Clip", "Ellipsis", "Visible"), frozenset({"Text"}), grouped=True),
    V2StateField("softWrap", "Soft wrap", _switch(), frozenset({"Text"}), grouped=True),
    V2StateField("selectable", "Selectable", _switch(), frozenset({"Text"}), grouped=True),
    V2StateField("autoSize", "Auto-size to fit", _switch(), frozenset({"Text"}), grouped=True),
    # ---- Font, and everything after it: inside textStyle.
    V2StateField(
        "typographyPreset",
        "Preset",
        _states(*_TYPOGRAPHY_PRESETS),
        frozenset({"Text"}),
        grouped=True,
        container=V2_TEXT_STYLE,
    ),
    V2StateField(
        "fontFamily",
        "Family",
        _states(*_FONT_FAMILIES),
        frozenset({"Text"}),
        grouped=True,
        container=V2_TEXT_STYLE,
    ),
    V2StateField(
        "fontWeight",
        "Weight",
        _states(*_TEXT_FONT_WEIGHTS),
        frozenset({"Text"}),
        grouped=True,
        container=V2_TEXT_STYLE,
    ),
    # Compose's FontStyle has exactly the two values, so the switch stores the words rather
    # than true/false -- "Italic" is what the samples hold.
    V2StateField(
        "fontStyle",
        "Italic",
        _switch("Italic", "Normal"),
        frozenset({"Text"}),
        grouped=True,
        container=V2_TEXT_STYLE,
    ),
    # ---- Decoration and effects.
    V2StateField(
        "textDecoration",
        "Decoration",
        _states("None", "Underline", "LineThrough", "UnderlineLineThrough"),
        frozenset({"Text"}),
        grouped=True,
        container=V2_TEXT_STYLE,
    ),
    V2StateField(
        "baselineShift",
        "Baseline",
        _states("None", "Superscript", "Subscript"),
        frozenset({"Text"}),
        grouped=True,
        container=V2_TEXT_STYLE,
    ),
    # ---- Paragraph.
    V2StateField(
        "lineBreak",
        "Line break",
        _states("Simple", "Heading", "Paragraph"),
        frozenset({"Text"}),
        grouped=True,
        container=V2_TEXT_STYLE,
    ),
    V2StateField(
        "hyphens",
        "Hyphens",
        _states("None", "Auto"),
        frozenset({"Text"}),
        grouped=True,
        container=V2_TEXT_STYLE,
    ),
    V2StateField(
        "textDirection",
        "Direction",
        _states("Content", "Ltr", "Rtl"),
        frozenset({"Text"}),
        grouped=True,
        container=V2_TEXT_STYLE,
    ),
    V2StateField(
        "lineHeightAlignment",
        "Line height alignment",
        _states("Top", "Center", "Proportional", "Bottom"),
        frozenset({"Text"}),
        grouped=True,
        container=V2_TEXT_STYLE,
    ),
    V2StateField(
        "lineHeightTrim",
        "Line height trim",
        _states("Both", "None", "FirstLineTop", "LastLineBottom"),
        frozenset({"Text"}),
        grouped=True,
        container=V2_TEXT_STYLE,
    ),
)

# Properties that hold an ordinary value but belong with the state fields below Show when
# rather than up in V2_COMPONENT_SCHEMA, as (property, the types offered it).
#
# Link colour is the colour a tappable link is drawn in, and it only means anything to a
# component whose Content format is Html -- which is what puts it directly below that field
# rather than beside the Text's own "color".
V2_BELOW_SHOW_WHEN_PROPS: tuple[tuple[V2Prop, frozenset[str]], ...] = (
    (V2Prop("linkColor", "Link color", "color"), frozenset({"Text"})),
)


def v2_is_colour(text: str) -> bool:
    """Whether this is something a Scene can hold as a colour -- and, just as much to the
    point, something the preview can draw.

    True for an HTML colour name or a #hex value (maputil2.is_html_colour), and for the
    Material role names Tasker writes into V2 colour properties ("primary", "onSurface").
    True as well for empty, which is a property that isn't set rather than one set wrongly,
    and for a %variable, whose value is only known on the phone.

    False, then, means a value that will not draw as a colour anywhere -- which is what the
    inspector marks, rather than refusing to store it: it is the user's Scene, and a colour
    this app fails to recognise is still theirs to keep.
    """
    from maptasker.src.maputil2 import is_html_colour  # noqa: PLC0415
    from maptasker.src.sceneview import V2_MATERIAL_PALETTE  # noqa: PLC0415

    value = text.strip()
    return not value or value.startswith("%") or value in V2_MATERIAL_PALETTE or is_html_colour(value)


@dataclass(frozen=True)
class V2ShowWhenChoice:
    """One variable the Show When picker offers: what it is called, and what it inserts.

    The two differ for the entries that have a documented name -- "Airplane Mode Status"
    inserts "%AIR" -- and are the same string for a user's own global, which has no name
    other than itself.

    Note what is deliberately NOT here: the variable's current value.  A Show When is
    evaluated when the Scene is shown, against whatever the variable holds *then*; whatever
    the backup happened to have stored when it was written is a different number and showing
    it would only invite someone to reason from it.
    """

    label: str
    value: str


# The Screen Builder's own environment variables -- read-only values Tasker sets while a
# Version 2 Scene is on screen.  "display" is the device's whole screen; "render" is the area
# this Scene is actually drawn into, which is smaller when the Scene is a dialog rather than
# full screen, so the two disagree exactly when it matters.
#
# The spellings are confirmed against real Scenes rather than transcribed: %sv2_render_is_
# landscape, %sv2_render_is_portrait, %sv2_display_is_portrait and %sv2_render_width all
# appear in the Version 2 Scenes in XML/backup.xml, every one of them with the "sv2" prefix
# (an "sv_" spelling appears nowhere, in any Scene, and would silently never match).
V2_SHOW_WHEN_ENVIRONMENT: tuple[V2ShowWhenChoice, ...] = (
    V2ShowWhenChoice("Display Width", "%sv2_display_width"),
    V2ShowWhenChoice("Display Height", "%sv2_display_height"),
    V2ShowWhenChoice("Display is Landscape", "%sv2_display_is_landscape"),
    V2ShowWhenChoice("Display is Portrait", "%sv2_display_is_portrait"),
    V2ShowWhenChoice("Render Width", "%sv2_render_width"),
    V2ShowWhenChoice("Render Height", "%sv2_render_height"),
    V2ShowWhenChoice("Render is Landscape", "%sv2_render_is_landscape"),
    V2ShowWhenChoice("Render is Portrait", "%sv2_render_is_portrait"),
)

# The comparisons a Show When can be built with.  Same shape as everything else the picker
# offers -- a name to choose by and the text it inserts -- because an operator is chosen the
# same way a variable is, and "ccontains" is no more memorable than "%AIR".
#
# Note "Contains (Case-Insensitive)": the parentheses are part of the *name*, not a spelling
# of the operator.  What goes into the field is the bare word, "contains".
V2_SHOW_WHEN_OPERATORS: tuple[V2ShowWhenChoice, ...] = (
    V2ShowWhenChoice("Equals", "=="),
    V2ShowWhenChoice("Not Equals", "!="),
    V2ShowWhenChoice("Greater Than", ">"),
    V2ShowWhenChoice("Less Than", "<"),
    V2ShowWhenChoice("Greater or Equal", ">="),
    V2ShowWhenChoice("Less or Equal", "<="),
    V2ShowWhenChoice("Contains (Case-Insensitive)", "contains"),
    V2ShowWhenChoice("Contains (Case-Sensitive)", "ccontains"),
    V2ShowWhenChoice("Matches Pattern", "matches"),
    V2ShowWhenChoice("Matches Regex", "matchesr"),
)

# What joins two comparisons into one condition, or negates one.  Kept as their own category
# rather than folded in with the comparisons above: these combine whole tests where those
# compare two values, so they are reached for at a different point in writing a condition.
V2_SHOW_WHEN_LOGICAL_OPERATORS: tuple[V2ShowWhenChoice, ...] = (
    V2ShowWhenChoice("And", "&"),
    V2ShowWhenChoice("Or", "|"),
    V2ShowWhenChoice("Not", "!"),
)

# The picker's categories, in the order it lists them.  The three short ones lead so they are
# all on screen without scrolling -- and because a condition is written left to right out of
# exactly these: a variable, a comparison, and whatever joins it to the next one.  The two
# long lists of globals follow.
V2_SHOW_WHEN_GROUPS = (
    "Environment",
    "Operators",
    "Logical Operators",
    "User Globals",
    "Built-in Globals",
)


def _v2_global_choices() -> tuple[list[V2ShowWhenChoice], list[V2ShowWhenChoice]]:
    """(user globals, built-in globals) out of the loaded backup's <Variable> elements.

    Read straight from the XML rather than from PrimeItems.variables, which looks like the
    obvious source and is the wrong one twice over: it is only ever filled by
    globalvr.get_variables() on the Map-output path, so in a GUI session that has not built a
    Map it is simply empty; and what it does hold has been through HTML escaping (spaces to
    &nbsp;, commas to <br>) for the benefit of the Map, which is not what a dialog should
    show.

    The two categories come from different places, and have to.

    User globals are the same set globalvr.print_the_variables treats as the user's: every
    <Variable> in the backup whose name Tasker does not own.  It is read here straight off
    the XML rather than out of PrimeItems.variables, which is the dict that function walks
    and would be the obvious thing to reuse, for two reasons: PrimeItems.variables is only
    ever filled by globalvr.get_variables() on the Map-output path, so in a GUI session that
    has not built a Map it is simply empty; and the values it holds have been HTML-escaped
    for the Map (spaces to &nbsp;, commas to <br>).  The names are identical either way,
    which is all this needs -- the name is both the label and what gets inserted.

    Built-ins are Tasker's own fixed set, and NOT the built-in-looking names found in the
    file: Tasker only writes a <Variable> for a value it has actually stored, so sourcing
    them from the backup yields an *empty* category on a real backup while %BATT and %WIFI
    are perfectly usable in a Show When.  Each is offered under its documented name --
    "Airplane Mode Status", not "%AIR", which is not something anyone browses a hundred-item
    list by -- from globalvr.tasker_global_variable_names, falling back to the variable
    itself for the handful that table has no name for.  Either way what gets inserted is the
    variable.  The set is the union of that table and globalvr's list, since each holds a few
    the other doesn't (see the note above tasker_global_variable_names).

    Both lists come back sorted by what the picker shows, ignoring case and any leading %,
    because Tasker's own ordering in the file is the order they were created in and means
    nothing to someone looking for one by name.
    """
    from maptasker.src.globalvr import tasker_global_variable_names, tasker_global_variables  # noqa: PLC0415

    builtin_names = set(tasker_global_variables) | set(tasker_global_variable_names)
    stored_names = (
        [variable.findtext("n") for variable in PrimeItems.xml_root.findall("Variable")]
        if PrimeItems.xml_root is not None
        else []
    )

    user = [V2ShowWhenChoice(name, name) for name in dict.fromkeys(stored_names) if name and name not in builtin_names]
    builtin = [V2ShowWhenChoice(tasker_global_variable_names.get(name, name), name) for name in builtin_names]

    def sort_key(choice: V2ShowWhenChoice) -> str:
        return choice.label.lstrip("%").lower()

    user.sort(key=sort_key)
    builtin.sort(key=sort_key)
    return user, builtin


def v2_show_when_choices() -> list[tuple[str, list[V2ShowWhenChoice]]]:
    """The whole Show When picker, as (category, choices) in V2_SHOW_WHEN_GROUPS order.

    A category with nothing in it is still returned, empty -- a backup with no variables of
    its own should say "User Globals: none" rather than silently offering two categories
    where the user was told there are three.
    """
    user, builtin = _v2_global_choices()
    return [
        ("Environment", list(V2_SHOW_WHEN_ENVIRONMENT)),
        ("Operators", list(V2_SHOW_WHEN_OPERATORS)),
        ("Logical Operators", list(V2_SHOW_WHEN_LOGICAL_OPERATORS)),
        ("User Globals", user),
        ("Built-in Globals", builtin),
    ]


def v2_insert_show_when(current: str, value: str, caret: int | None = None) -> tuple[str, int]:
    """Put one variable or operator into a Show When expression at `caret`, and hand back
    (new text, where the caret should now be).

    Inserts rather than replaces, because a Show When is an expression built a piece at a
    time -- "%sv2_render_is_portrait" is a complete condition on its own, but
    "%BATT < 20" is a variable, an operator and something typed, in that order.

    caret is where the user last had the cursor in the field; None, or a position that no
    longer fits the text, means the end.  The end is also the right answer for the common
    case of never having clicked into the field at all, where the caret sits at 0 and
    inserting there would build the expression backwards.

    Single spaces are added around the inserted text where its neighbours don't already
    provide them, so picking a variable and then an operator gives "%BATT <" rather than
    "%BATT<" -- and the returned caret sits *after* that trailing space, ready for whatever
    comes next.
    """
    position = len(current) if caret is None or not 0 <= caret <= len(current) else caret
    before, after = current[:position], current[position:]
    lead = "" if not before or before[-1].isspace() else " "
    trail = "" if not after or after[0].isspace() else " "
    inserted = f"{lead}{value}{trail}"
    return f"{before}{inserted}{after}", position + len(inserted)


def v2_dynamic_variable_choices() -> list[tuple[str, list[V2ShowWhenChoice]]]:
    """The variables offered for a Dynamic state field, as (category, choices).

    The same three categories of variable the Show When picker lists -- Environment, User
    Globals, Built-in Globals -- because these fields can be driven by a variable in exactly
    the way a Show When can.  What they do not borrow from that picker are its Operators and
    Logical Operators: those build a comparison out of two values, and these fields hold one.

    Empty categories are returned empty, for the reason v2_show_when_choices gives.
    """
    user, builtin = _v2_global_choices()
    return [
        ("Environment", list(V2_SHOW_WHEN_ENVIRONMENT)),
        ("User Globals", user),
        ("Built-in Globals", builtin),
    ]


def v2_state_field(key: str) -> V2StateField | None:
    """The state field this property key belongs to, or None for a key that isn't one."""
    return next((field for field in V2_STATE_FIELDS if field.key == key), None)


def v2_is_variable(text: str) -> bool:
    """Whether this is one variable and nothing else -- "%BATT", not "%BATT > 20" and not
    "<b>%name</b>".

    The whole test is a leading % and no whitespace, which is what tells a value the Select
    Variable state produced from one someone typed under Dynamic.  It is deliberately a shape
    test rather than a lookup in the picker's own lists: a Scene can perfectly well be driven
    by a local variable, or one a Task creates at run time, and neither appears in any list
    this app can build.
    """
    stripped = text.strip()
    return stripped.startswith("%") and len(stripped) > 1 and not any(c.isspace() for c in stripped)


def v2_state_of(field: V2StateField, value: object) -> str:
    """Which state a stored value reads as -- or "" for a component that carries no such
    property at all, which is not the same as one set to its "off" state.

    A settling state is matched ignoring case *and* spaces, and a real JSON boolean is read as
    the "true"/"false" it prints as.  So a Scene from a newer Tasker spelling Enabled as true
    rather than "true" still lands on On, and one spelling a weight "ExtraLight" where this
    app spells it "Extra Light" still lands on that weight rather than falling through to
    Dynamic.  Nothing is lost by being that loose: no two states in any of these tables differ
    only by case or a space.

    What is left is one of the two open states, told apart by v2_is_variable: a bare %variable
    reads as Select Variable, anything else as Dynamic.  The point of the distinction is that
    the field reopens on the control that could have produced what is stored -- a picked
    variable in the variable box, typed text in the text box.
    """
    text = str(value).strip()
    if not text:
        return ""

    def loose(word: str) -> str:
        return "".join(word.split()).lower()

    settled = next((state for state, stored in field.fixed if loose(text) == loose(stored)), "")
    if settled:
        return settled
    return V2_VARIABLE_STATE if v2_is_variable(text) else V2_DYNAMIC_STATE


def v2_state_value(field: V2StateField, value: object, state: str = "") -> str:
    """What an open state is carrying -- the typed text, or the picked variable -- and "" for
    any settling state, so that the box starts empty rather than showing "true" for a
    component the user has only just switched over.

    `state` asks for the value of one particular open state, which is how the two boxes are
    filled from the one stored property: the one that state produced gets it, the other starts
    empty rather than both opening with the same text.
    """
    current = v2_state_of(field, value)
    if current not in (V2_DYNAMIC_STATE, V2_VARIABLE_STATE):
        return ""
    return str(value).strip() if state in ("", current) else ""


def v2_set_state(field: V2StateField, node: dict, state: str, value: str = "") -> None:
    """Write a state field from the state chosen and, for the two open states, whatever is in
    that state's box.

    A settling state goes through v2_set_prop, so that a Scene which already spelled the key
    as a JSON boolean keeps its own spelling (see _coerce_like); anything else stores the
    string Tasker writes.  An open state can't go that way -- a %variable coerced onto a
    boolean key would store false and silently lose what was chosen -- so it is written as the
    string it is.

    No state, or an open state with nothing in it yet, removes the key rather than storing an
    empty one: absent is how Tasker writes a component that has never been given the property,
    and it is the honest way to hold a setting that isn't finished being written.
    """
    stored = dict(field.fixed).get(state)
    if stored is not None:
        v2_set_prop(node, field.key, stored)
    elif state in (V2_DYNAMIC_STATE, V2_VARIABLE_STATE) and value.strip():
        node[field.key] = value
    else:
        node.pop(field.key, None)


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
        V2Prop("color", "Colour", "color"),
    ),
    "TextInput": (
        V2Prop("label", "Label"),
        V2Prop("textSize", "Text size", "number"),
    ),
    "Button": (
        V2Prop("text", "Text"),
        V2Prop("buttonColor", "Button colour", "color"),
        V2Prop("textColor", "Text colour", "color"),
    ),
    "IconButton": (
        V2Prop("icon", "Icon", "icon"),
        V2Prop("contentScale", "Content scale"),
    ),
    "Image": (
        V2Prop("url", "Image URL"),
        V2Prop("icon", "Icon", "icon"),
        V2Prop("width", "Width", "number"),
        V2Prop("height", "Height", "number"),
        V2Prop("alignment", "Alignment", "choice", _ALIGNMENT),
        V2Prop("contentScale", "Content scale"),
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
    "SegmentedButtonRow": (
        V2Prop("allowDeselect", "Allow deselect", "choice", ("true", "false")),
        V2Prop("selectedIndices", "Selected indices"),
    ),
    "SegmentedButtonItem": (V2Prop("label", "Label"),),
    "NavigationItem": (
        V2Prop("icon", "Icon", "icon"),
        V2Prop("label", "Label"),
        V2Prop("selected", "Selected", "choice", ("true", "false")),
    ),
    "Variable": (V2Prop("key", "Variable"),),
    "Spacer": (V2Prop("height", "Height", "number"),),
    "Divider": (V2Prop("color", "Colour", "color"),),
    "Scaffold": (),
    "TopAppBar": (),
    "NavigationBar": (V2Prop("selectedIndex", "Selected index", "number"),),
    "FloatingActionButton": (),
    # ---- Read off the 'V2New' Scene, which was built in Tasker's Screen Builder with one of
    # each of the elements this app had never seen a sample of.  Every key below appears in
    # that Scene; the ones Tasker left absent are absent here too rather than guessed at, so
    # these entries stay as short as the evidence is.
    "ProgressBar": (
        V2Prop("minProgress", "Minimum progress", "number"),
        V2Prop("color", "Colour", "color"),
        V2Prop("showStopIndicator", "Show stop indicator", "choice", ("true", "false")),
        V2Prop("animateChanges", "Animate changes", "choice", ("true", "false")),
    ),
    # "front" is what the sample carries; the opposite value is Tasker's to name, so this is a
    # free text field rather than a two-item pulldown that might offer the wrong other half.
    "Camera": (V2Prop("lens", "Lens"),),
    "RangeSlider": (
        V2Prop("start", "Range start"),
        V2Prop("end", "Range end"),
    ),
    "Card": (V2Prop("elevation", "Elevation", "number"),),
    "FlexBox": (
        V2Prop("wrap", "Wrap", "choice", ("Wrap", "NoWrap")),
        V2Prop("alignItems", "Align items"),
        V2Prop("alignContent", "Align content", "choice", _ARRANGEMENT),
        V2Prop("gap", "Gap", "number"),
    ),
    "FlowColumn": (
        V2Prop("horizontalArrangement", "Horizontal arrangement", "choice", _ARRANGEMENT),
        V2Prop("itemHorizontalAlignment", "Item alignment", "choice", _ALIGNMENT),
        V2Prop("maxItemsPerLine", "Max items per line", "number"),
        V2Prop("maxLines", "Max lines", "number"),
        V2Prop("overflow", "Overflow"),
    ),
    # Four the sample carries with no properties of their own beyond the universal ones --
    # they were added and left empty.  Listed anyway, so the inspector shows a deliberate
    # "nothing to set here" rather than falling through to the unschema'd path.
    "Box": (),
    "BottomAppBar": (),
    "ArraysMergeTemplate": (),
    "Placeholder": (),
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


# Components that name themselves by one of their own properties when they carry no
# treeLabel, and which property that is.  A Text or a Button says what it says and an
# IconButton is the icon on it: "Text 'Empty Scene'", "Button 'Save'" and "IconButton 'Close'"
# identify them on sight, where "Text 'Text2'" is a number the user never chose and has to
# click each one to tell apart.
V2_LABEL_FALLBACK: dict[str, str] = {"Text": "text", "Button": "text", "IconButton": "icon"}

# The properties above that hold an icon reference rather than words, and so are read for
# their name by maputil2.tasker_icon_name -- "icon:Close" is called Close.
_V2_ICON_KEYS = ("icon",)

# How Tasker spells a Material icon: the prefix, then the name in Pascal case ("icon:AcUnit")
# where the font's own ligature is snake ("ac_unit").  The designer's picker offers the
# ligature names -- they are what the glyphs are drawn by -- and converts on the way in.
V2_ICON_PREFIX = "icon:"

# Where the names come from.  Alongside the app's other tables rather than written into this
# module, because it is a list of 550 strings and it is data: see the file's own _comment for
# what was verified about it, and _build_icon_field for what the designer does with it.
_V2_ICON_NAMES_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets",
    "json",
    "material_icons.json",
)
_v2_icon_names_cache: list[str] = []


def v2_icon_names() -> list[str]:
    """Every Material icon the picker offers, by the ligature name its glyph is drawn by.

    Read once and kept: the file is small, but the picker rebuilds its list on every keystroke
    of its search box, and re-reading a file per keystroke is the kind of thing that makes a
    dialog feel slow for no reason.

    An empty list if the file is missing or unreadable -- the designer then offers no picker
    and the icon field is typed into, which is exactly what it was before there was one.
    """
    if not _v2_icon_names_cache:
        try:
            with open(_V2_ICON_NAMES_FILE, encoding="utf-8") as file:
                _v2_icon_names_cache.extend(json.load(file).get("icons", []))
        except (OSError, ValueError):
            return []
    return _v2_icon_names_cache


def v2_icon_reference(name: str) -> str:
    """A ligature name as the reference a Scene stores: "ac_unit" -> "icon:AcUnit"."""
    return f"{V2_ICON_PREFIX}{''.join(part.capitalize() for part in name.split('_'))}"

# How much of that property the tree shows.  The ids and treeLabels this used to display are
# a few characters; a Text's content runs to 66 in this repo's own Scenes, and a tree row is
# one unwrapped line, so a whole paragraph would widen the pane rather than name the row.
_V2_LABEL_MAX = 40


def _v2_label_text(value: str) -> str:
    """One line, short enough for a tree row.  Runs of whitespace become single spaces --
    a Text's value can carry newlines, and a row is drawn with white-space: pre, so an
    unflattened one would break the row apart rather than label it.
    """
    single_line = " ".join(value.split())
    return single_line if len(single_line) <= _V2_LABEL_MAX else f"{single_line[:_V2_LABEL_MAX]}..."


def v2_reads_as_html(node: dict) -> bool:
    """Whether this component's text is markup rather than the words themselves -- its
    Content format settles on Html.

    A format left to a %variable or to Dynamic answers False: what it will be is decided on
    the phone, and treating an unknown as markup would strip angle brackets out of a value
    that may well be showing them.
    """
    field = v2_state_field("contentFormat")
    return field is not None and v2_state_of(field, node.get(field.key, "")) == "Html"


def v2_node_name(node: dict) -> str:
    """What a component is called in the designer: its treeLabel, else the property named for
    its type in V2_LABEL_FALLBACK, else its id.

    treeLabel leads because that is exactly what the property is for -- it is the name
    Tasker's own Screen Builder tree displays, and a component the user has bothered to name
    should read by that name here too.  The id is last because it is the only one of the three
    the user did not write.

    A property that holds markup is named by what it *says*: the tags come off and the
    entities come back, so an Html Text reads "Bold heading" rather than "<b>Bold</b>
    heading".  Only when the Content format actually says Html, though -- in a Plain text the
    angle brackets are the content, and a component showing "<b>" on the phone should say so
    here.  An icon reference is read for its name for the same reason -- "icon:Close" is
    called Close, and the ";weight:600;opsz:24" on a Symbol says how to draw it, not which one
    it is (see maputil2.tasker_icon_name).

    A value that cleans up to nothing -- markup with no words in it, a bare "icon:" -- falls
    through to the id, the same as a value that was empty to begin with.
    """
    tree_label = str(node.get("treeLabel") or "").strip()
    if tree_label:
        return _v2_label_text(tree_label)

    own_key = V2_LABEL_FALLBACK.get(str(node.get("type", "")), "")
    own_value = str(node.get(own_key, "") or "") if own_key else ""
    if own_value and v2_reads_as_html(node):
        from maptasker.src.maputil2 import strip_html_tags  # noqa: PLC0415

        own_value = html.unescape(strip_html_tags(own_value))
    if own_value and own_key in _V2_ICON_KEYS:
        from maptasker.src.maputil2 import tasker_icon_name  # noqa: PLC0415

        own_value = tasker_icon_name(own_value)
    return _v2_label_text(own_value) or str(node.get("id", ""))


def v2_node_label(node: dict) -> str:
    """ "Text 'Empty Scene'" -- how a node reads in the designer's tree and at the head of its
    inspector.  See v2_node_name for which of the component's names is used.
    """
    node_type = node.get("type", "?")
    name = v2_node_name(node)
    return f"{node_type} '{name}'" if name else node_type


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


def _v2_universal_props(node: dict) -> list[V2Prop]:
    """The properties every component can carry, with the state fields and then
    V2_BELOW_SHOW_WHEN_PROPS spliced in directly below Show when, for the types that have
    them.

    A node that already carries one of those keys gets the field whatever its type, so that a
    component this app doesn't yet know has one is still edited with its own widget rather
    than falling through to the raw text box an unrecognised key gets.

    Grouped fields are left out on both counts -- see V2StateField.grouped.  They have a place
    of their own in V2_TEXT_CATEGORIES, and a component that carries one without being the type
    that groups them (a "selectable" on something other than a Text, say) is better served by
    the plain fallback field than by a widget lifted out of another type's category.
    """
    node_type = node.get("type")
    extras = [
        field.prop
        for field in V2_STATE_FIELDS
        if not field.modifier and not field.grouped and (node_type in field.types or field.key in node)
    ]
    extras += [prop for prop, types in V2_BELOW_SHOW_WHEN_PROPS if node_type in types or prop.key in node]

    props = list(V2_UNIVERSAL_PROPS)
    below_show_when = next(index for index, prop in enumerate(props) if prop.key == "showWhen") + 1
    for offset, prop in enumerate(extras):
        props.insert(below_show_when + offset, prop)
    return props


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
    props = [V2_ID_PROP, *schema, *_v2_universal_props(node)]
    known = {prop.key for prop in props}
    for key, value in node.items():
        if key in known or key in V2_STRUCTURAL_KEYS:
            continue
        if isinstance(value, (str, int, float, bool)):
            props.append(V2Prop(key, key))
    return props


# --------------------------------------------------------------------------------------
# Property categories.
#
# A Text carries more settings than any other component by a wide margin -- fifty-odd, once
# its textStyle is counted -- and a flat list of fifty fields is not a property sheet, it is a
# haystack.  So they are grouped the way Tasker's own Screen Builder groups them, and the
# inspector puts each group up as a section that can be opened and closed.
#
# Only Text has a table here.  Every other component still gets the flat list from
# v2_editable_props, because none of them has enough properties for the grouping to be worth
# the click it costs -- see v2_property_groups, which is what both paths go through.
#
# Every key below appears on a real Text in XML/backup.xml, at the spelling written here.
# --------------------------------------------------------------------------------------


def _state_prop(key: str) -> V2Prop:
    """One of the state fields above as a property, by key -- so the table reads as a list of
    fields rather than as a list of lookups.
    """
    field = v2_state_field(key)
    if field is None:  # pragma: no cover -- the keys below are literals from V2_STATE_FIELDS
        message = f"No V2 state field named {key!r}"
        raise KeyError(message)
    return field.prop


def _style_prop(key: str, label: str, kind: str = "numvar") -> V2Prop:
    """One plain textStyle property.  Defaulted to "numvar" because most of them are a
    measurement that can equally be pointed at a variable -- a line height of 17, or of
    whatever %spacing turns out to hold when the Scene is shown.
    """
    return V2Prop(key, label, kind, container=V2_TEXT_STYLE)


V2_TEXT_CATEGORIES: tuple[tuple[str, tuple[V2Prop, ...]], ...] = (
    (
        "General",
        (
            V2_ID_PROP,
            V2Prop("treeLabel", "Tree label"),
            V2Prop("showWhen", "Show when"),
            # Kept with Show when rather than dropped: it says what "hidden" means for this
            # component, and it is meaningless anywhere else.
            V2Prop("showWhenMode", "Hidden as", "choice", ("Gone", "Invisible")),
            _state_prop("enabled"),
        ),
    ),
    (
        "Content",
        (
            # The one property a Text cannot do without, and the reason "textvar" exists: what
            # it says is as often %some_variable as it is words.
            V2Prop("text", "Text", "textvar"),
            _state_prop("contentFormat"),
            # Only means anything when the Content format above it is Html or Markdown, which
            # is why it sits with them rather than beside Appearance's own colour.
            V2Prop("linkColor", "Link color", "color"),
        ),
    ),
    (
        "Appearance",
        (
            V2Prop("textSize", "Text size", "number"),
            V2Prop("color", "Colour", "color"),
            V2Prop("textAlign", "Alignment", "choice", _ALIGNMENT),
            V2Prop("verticalAlignment", "Vertical alignment", "choice", _VERTICAL_ALIGNMENT),
        ),
    ),
    (
        "Behavior",
        (
            _state_prop("overflow"),
            V2Prop("maxLines", "Max lines", "numvar"),
            V2Prop("minLines", "Min lines", "numvar"),
            _state_prop("softWrap"),
            _state_prop("selectable"),
            _state_prop("autoSize"),
            V2Prop("autoSizeMinSp", "Auto-size min (sp)", "numvar"),
            # Offered beside its own minimum.  Not in the brief this table was written from,
            # but it is in the Scenes -- five Texts in XML/backup.xml carry it -- and a minimum
            # whose maximum could only be edited as a raw key would be the odd one of the pair.
            V2Prop("autoSizeMaxSp", "Auto-size max (sp)", "numvar"),
        ),
    ),
    (
        "Font",
        (
            _state_prop("typographyPreset"),
            _state_prop("fontFamily"),
            _state_prop("fontWeight"),
            _state_prop("fontStyle"),
        ),
    ),
    (
        "Spacing",
        (
            _style_prop("lineHeight", "Line height"),
            _style_prop("letterSpacing", "Letter spacing"),
            _style_prop("textIndentFirstLine", "Indent (first line)"),
            _style_prop("textIndentRestLine", "Indent (other lines)"),
        ),
    ),
    (
        "Decoration and effects",
        (
            _state_prop("textDecoration"),
            _state_prop("baselineShift"),
            _style_prop("shadowColor", "Shadow color", "colorvar"),
            _style_prop("shadowOffsetX", "Shadow offset X"),
            _style_prop("shadowOffsetY", "Shadow offset Y"),
            _style_prop("shadowBlur", "Shadow blur"),
            _style_prop("gradientStartColor", "Gradient start", "colorvar"),
            _style_prop("gradientEndColor", "Gradient end", "colorvar"),
            _style_prop("gradientAngleDegrees", "Gradient angle"),
            _style_prop("strokeWidth", "Stroke"),
            # Tasker's key for it is spanBackground; the Screen Builder calls it Highlight, and
            # that is the name the user is looking for.
            _style_prop("spanBackground", "Highlight", "colorvar"),
        ),
    ),
    (
        "Paragraph",
        (
            _state_prop("lineBreak"),
            _state_prop("hyphens"),
            _state_prop("textDirection"),
            _state_prop("lineHeightAlignment"),
            _state_prop("lineHeightTrim"),
        ),
    ),
)

# Which categories the inspector opens on.  The two that answer "which component is this and
# what does it say" -- the rest are refinements, and eight open sections is the flat list this
# grouping replaced, only taller.
V2_OPEN_CATEGORIES = frozenset({"General", "Content"})

# Where the leftovers go: any key a Scene carries that no category above claims.  Named rather
# than hidden, for the reason v2_editable_props gives -- a Scene from a newer Tasker will carry
# properties this app has never seen, and the designer must not be the reason they can't be
# touched.
V2_OTHER_CATEGORY = "Other"


class V2NestedProps:
    """One node's nested property object -- a Text's textStyle -- presented as the dict the
    inspector edits.

    It exists so that v2_set_prop and v2_set_state, which know only how to read and write keys
    on a dict, can edit a property that lives one level down without either of them learning
    about nesting.  Every operation those two use is forwarded to the real object.

    What it adds is when that object exists.  It is created on the first write and removed
    again when its last key is cleared, so a Text that has never been styled does not grow an
    empty "textStyle": {} for having been selected in the tree, and one styled back to nothing
    re-encodes to the bytes it arrived as.

    A container the Scene holds as something other than an object is read as empty and never
    written over.  That is not a shape Tasker writes, and guessing at it would cost the user
    whatever is actually in there.
    """

    __slots__ = ("_container", "_node")

    def __init__(self, node: dict, container: str) -> None:
        self._node = node
        self._container = container

    @property
    def _held(self) -> dict:
        held = self._node.get(self._container)
        return held if isinstance(held, dict) else {}

    def _writable(self) -> dict | None:
        """The object to write into, created if this node has never had one."""
        held = self._node.get(self._container)
        if isinstance(held, dict):
            return held
        if held is not None:
            return None
        created: dict = {}
        self._node[self._container] = created
        return created

    def _prune(self) -> None:
        held = self._node.get(self._container)
        if isinstance(held, dict) and not held:
            del self._node[self._container]

    def get(self, key: str, default: object = None) -> object:
        return self._held.get(key, default)

    def items(self) -> object:
        return self._held.items()

    def __contains__(self, key: str) -> bool:
        return key in self._held

    def __getitem__(self, key: str) -> object:
        return self._held[key]

    def __setitem__(self, key: str, value: object) -> None:
        held = self._writable()
        if held is not None:
            held[key] = value

    def __delitem__(self, key: str) -> None:
        self._held.pop(key, None)
        self._prune()

    def pop(self, key: str, default: object = None) -> object:
        value = self._held.pop(key, default)
        self._prune()
        return value


def v2_prop_dict(node: dict, prop: V2Prop) -> dict | V2NestedProps:
    """What to read and write this property on: the node itself, or the nested object it
    lives in.  The one call the inspector needs to make to stop caring where a property sits.
    """
    return V2NestedProps(node, prop.container) if prop.container else node


def _v2_other_props(node: dict, claimed: tuple[tuple[str, tuple[V2Prop, ...]], ...]) -> list[V2Prop]:
    """Scalar keys the categories don't account for -- on the node and inside the containers
    they name -- as plain fields, so nothing a Scene holds is invisible.
    """
    spoken_for = {(prop.container, prop.key) for _, props in claimed for prop in props}
    containers = {prop.container for _, props in claimed for prop in props if prop.container}

    others: list[V2Prop] = []
    for key, value in node.items():
        if key in V2_STRUCTURAL_KEYS or key in containers or ("", key) in spoken_for:
            continue
        if isinstance(value, (str, int, float, bool)):
            others.append(V2Prop(key, key))
    for container in sorted(containers):
        held = node.get(container)
        if not isinstance(held, dict):
            continue
        others += [
            V2Prop(key, f"{container}.{key}", container=container)
            for key, value in held.items()
            if (container, key) not in spoken_for and isinstance(value, (str, int, float, bool))
        ]
    return others


def v2_property_groups(node: dict) -> list[tuple[str, list[V2Prop]]]:
    """This component's editable properties, as the named sections the inspector draws.

    A type with a category table (Text, and so far only Text) gets its sections in the table's
    order, with anything left over gathered into a final one.  Every other type gets a single
    section with no name, which is the flat list the inspector has always drawn -- so the
    grouping is something a type opts into rather than something every type now pays for.
    """
    categories = V2_TEXT_CATEGORIES if node.get("type") == "Text" else ()
    if not categories:
        return [("", v2_editable_props(node))]

    groups = [(name, list(props)) for name, props in categories]
    others = _v2_other_props(node, categories)
    if others:
        groups.append((V2_OTHER_CATEGORY, others))
    return groups


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
    # "content", not "children" -- the Scene v2 Dialog compiler builds its rows as
    # {type: "SegmentedButtonRow", ..., content: [SegmentedButtonItem, ...]}.
    "SegmentedButtonRow": ("content",),
    # Confirmed: the 'V2New' Scene's Card holds a Text under "children".
    "Card": ("children",),
    # Containers by their own properties -- FlowColumn carries maxItemsPerLine and
    # itemHorizontalAlignment, FlexBox carries alignItems and gap, and a Z-stack, an app bar
    # and a repeating template exist to hold things -- but each was left empty in 'V2New', so
    # the slot *name* is still the one inference left here.  "children" is the guess, being
    # what every confirmed general-purpose container uses.  If Tasker turns out to name it
    # otherwise, v2_container_slots' present-slot fallback still finds the real one when a
    # populated Scene arrives.
    "Box": ("children",),
    "FlowColumn": ("children",),
    "FlexBox": ("children",),
    "BottomAppBar": ("children",),
    "ArraysMergeTemplate": ("children",),
    # Placeholder is deliberately NOT here.  Nothing shows it holding anything, and a leaf
    # wrongly declared a container swallows the next component added; a container wrongly
    # left a leaf only puts it alongside instead, which is the recoverable way to be wrong.
}


@dataclass(frozen=True)
class V2PaletteEntry:
    """One element the Add Element dialog offers.

    label is deliberately *not* the type: Tasker's own Add Element sheet says "Vertical
    Column" and "Horizontal Row" where the JSON says Column and Row, and someone who
    learned the Screen Builder should find the element under the name it showed them.
    The type is what gets written; the label is what gets read.

    verified is the honest bit -- see V2_PALETTE below.
    """

    node_type: str
    label: str
    group: str
    description: str
    verified: bool = True


# The groups, in the order Tasker's own Add Element sheet lists them.  Its grouping is
# adopted wholesale rather than kept as this app's earlier Layout/Display/Input/Structure
# split, for the same reason the labels are: it is the arrangement the user already knows.
V2_PALETTE_GROUPS = ("Display", "Input", "Layout", "Media")

# What the palette offers -- every element Tasker's Add Element sheet lists, plus the three
# slot-scoped ones it only offers in context (see V2_PARENT_ONLY).
#
# `verified` says whether this entry's type string and property keys were read off something
# real -- a decoded <lj> in XML/*.xml, or the 'Scene v2 Dialog' project's compiler, which
# emits component JSON as string literals.  Every entry currently is: the 'V2New' Scene in
# XML/backup.xml was built in Tasker's Screen Builder expressly to carry one of each element
# this app had never seen a sample of, and it confirmed all ten type strings (PascalCase of
# the label, as guessed) along with their real properties.
#
# The flag stays because the situation it describes will recur: Tasker adds elements, and the
# next one named in its UI but absent from every Scene here starts life unverified.  Such an
# entry deliberately carries NO schema and NO invented properties -- inventing property keys
# would be inventing a format, and the failure mode is a Scene Tasker can no longer render.
# The dialog marks it, and its tooltip says so in words.
#
# To retire one: build it in Tasker's Screen Builder, export the Scene into XML/, decode its
# <lj>, and write down what is actually there -- the real type string, the real property
# keys, the real child-slot name.  Then flip the flag and fill in V2_COMPONENT_SCHEMA /
# V2_CONTAINER_SLOTS from the sample.  Note what Tasker *omits* as much as what it writes:
# it gives a brand-new component nothing but a type and an id, which is why
# V2_NEW_NODE_DEFAULTS stays empty for all ten.
#
# Alphabetical within each group, matching the sheet.  Every label and description is an
# English source string -- guiwins runs them through translate_string.
V2_PALETTE: tuple[V2PaletteEntry, ...] = (
    # ---- Display ----
    V2PaletteEntry("Divider", "Divider", "Display", "A horizontal rule across the width of its container."),
    V2PaletteEntry("Image", "Image", "Display", "A picture from a URL, a file path, or a named icon."),
    V2PaletteEntry("ProgressBar", "Progress Bar", "Display", "A progress indicator."),
    V2PaletteEntry("Text", "Text", "Display", "A run of text. Accepts %variables."),
    V2PaletteEntry("WebView", "WebView", "Display", "An embedded web page, or HTML held in a variable."),
    # ---- Input ----
    V2PaletteEntry("Button", "Button", "Input", "A labelled button. Add a click handler to make it do something."),
    V2PaletteEntry("Camera", "Camera", "Input", "A live camera preview."),
    V2PaletteEntry("Checkbox", "Checkbox", "Input", "A tick box that writes its state into a variable."),
    V2PaletteEntry("IconButton", "Icon Button", "Input", "A button showing an icon instead of a label."),
    V2PaletteEntry(
        "RangeSlider",
        "Range Slider",
        "Input",
        "A slider with a low and a high handle, selecting a range.",
    ),
    V2PaletteEntry(
        "SegmentedButtonRow",
        "Segmented Button Row",
        "Input",
        "A row of joined buttons of which one stays selected. Holds Segmented Button Items.",
    ),
    V2PaletteEntry(
        "SegmentedButtonItem",
        "Segmented Button Item",
        "Input",
        "One button within a Segmented Button Row.",
    ),
    V2PaletteEntry("Slider", "Slider", "Input", "A slider between a minimum and a maximum."),
    V2PaletteEntry("Switch", "Switch", "Input", "An on/off switch that writes its state into a variable."),
    V2PaletteEntry("TextInput", "Text Input", "Input", "A text field that writes what is typed into a variable."),
    # ---- Layout ----
    V2PaletteEntry(
        "ArraysMergeTemplate",
        "Arrays Merge Template",
        "Layout",
        "Repeats a block of components once per entry in a set of Tasker arrays.",
    ),
    V2PaletteEntry(
        "BottomAppBar",
        "Bottom App Bar",
        "Layout",
        "A bar pinned to the bottom of a Scaffold.",
    ),
    V2PaletteEntry(
        "Box",
        "Box (Z-Stack)",
        "Layout",
        "Stacks its children on top of one another rather than in a line.",
    ),
    V2PaletteEntry("Card", "Card", "Layout", "A raised, rounded panel to group components in."),
    V2PaletteEntry("Dropdown", "Dropdown", "Layout", "A trigger that opens a list to pick from."),
    V2PaletteEntry(
        "FlexBox",
        "FlexBox (Experimental)",
        "Layout",
        "Experimental flexible layout. Tasker marks it experimental itself.",
    ),
    V2PaletteEntry(
        "FlowColumn",
        "Flow Column",
        "Layout",
        "Stacks children downwards, wrapping into a new column when full.",
    ),
    V2PaletteEntry("FlowRow", "Flow Row", "Layout", "Lays children across, wrapping onto a new line when full."),
    V2PaletteEntry("Row", "Horizontal Row", "Layout", "Lays its children out side by side."),
    V2PaletteEntry("NavigationBar", "Navigation Bar", "Layout", "A bottom navigation bar holding Navigation Items."),
    V2PaletteEntry("NavigationItem", "Navigation Item", "Layout", "One destination within a Navigation Bar."),
    V2PaletteEntry(
        "FloatingActionButton",
        "Floating Action Button",
        "Layout",
        "The round button that floats over a Scaffold's content.",
    ),
    V2PaletteEntry(
        "Placeholder",
        "Placeholder",
        "Layout",
        "A blank stand-in, to reserve space while building.",
    ),
    V2PaletteEntry(
        "Scaffold",
        "Scaffold",
        "Layout",
        "The frame of a full-screen Scene: top bar, content, bottom bar and floating button.",
    ),
    V2PaletteEntry("Spacer", "Spacer", "Layout", "Empty space of a fixed size, to push components apart."),
    V2PaletteEntry("TopAppBar", "Top App Bar", "Layout", "A title bar across the top of a Scaffold."),
    V2PaletteEntry("Variable", "Variable", "Layout", "Declares a Scene variable. Renders nothing itself."),
    V2PaletteEntry("Column", "Vertical Column", "Layout", "Lays its children out one above the other."),
    # ---- Media ----
    V2PaletteEntry("Video", "Video", "Media", "A video player."),
)

# Elements that only make sense inside one kind of parent, and the parents that will take
# them.  Tasker's own sheet offers these contextually rather than listing them at the root,
# which is why none of the three appear in a screenshot of it taken with the root selected.
# The designer greys them out with a reason instead of hiding them, so the element is still
# discoverable -- and so "why can't I add this?" has an answer on screen.
V2_PARENT_ONLY: dict[str, tuple[str, ...]] = {
    "NavigationItem": ("NavigationBar",),
    "SegmentedButtonItem": ("SegmentedButtonRow",),
    "FloatingActionButton": ("Scaffold",),
}

# Type -> the name the palette shows for it, for messages that have to name a component the
# user did not necessarily add themselves (v2_can_add's reasons).  A type absent from the
# palette -- a component from a newer Tasker -- falls back to its own type string.
V2_PALETTE_LABELS: dict[str, str] = {entry.node_type: entry.label for entry in V2_PALETTE}

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
    # Traced to the Scene v2 Dialog compiler's own buildButtonRow(), including the string
    # "true" rather than a JSON boolean -- see _coerce_like on why that distinction is kept.
    "SegmentedButtonRow": {"allowDeselect": "true", "selectedIndices": "", "content": []},
    "SegmentedButtonItem": {"label": "Item"},
    # The ten from 'V2New' get no defaults at all -- deliberately, and not for lack of a
    # schema.  Tasker wrote every one of them carrying nothing but its type and id: an
    # untouched Box is {"type": "Box", "id": "Box1"}, with no empty children list, no colour,
    # no size.  Matching that exactly is the point (see this module's note on re-encoding),
    # and the missing child slot costs nothing -- v2_insert_node setdefaults it into place the
    # moment something is actually added, which is also when Tasker itself would write it.
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


def v2_insert_destination(layout: dict, path: tuple) -> tuple[str, str]:
    """Where v2_insert_node would put a new component right now, as ("inside"/"after", id).

    The same two-case rule v2_insert_node implements, answered *before* the click rather
    than described in a tooltip -- the Add Element dialog puts it in its header so the
    destination is a fact on screen ("inside Column1") instead of a caveat.  ("", "") for a
    path that doesn't resolve.

    "inside" and "after" are English source strings; the caller translates them.
    """
    target = v2_node_at(layout, path)
    if target is None:
        return "", ""
    name = str(target.get("id") or target.get("type", ""))
    return ("inside" if v2_container_slots(target) else "after"), name


def _v2_insert_parent_type(layout: dict, path: tuple) -> str:
    """The type of the component a new node added at `path` would end up *in* -- the target
    itself when it can hold children, otherwise the target's own parent.  Mirrors
    v2_insert_node's two cases, which is what makes v2_can_add agree with what a click does.
    """
    target = v2_node_at(layout, path)
    if target is None:
        return ""
    if v2_container_slots(target):
        return str(target.get("type", ""))
    parent, _slot, _index = _v2_parent_and_slot(layout, path)
    return str((parent or {}).get("type", ""))


def v2_can_add(layout: dict, path: tuple, node_type: str) -> str:
    """ "" if this element can be added at this selection, otherwise the reason it can't.

    Only V2_PARENT_ONLY is consulted: everything else goes anywhere a container will take
    it, and being stricter than that would mean ruling on nestings Tasker allows and this
    app has simply never seen.  The reason is an English source string for the caller to
    translate, and names the parent by its palette label ("a Navigation Bar", not
    "a NavigationBar").
    """
    allowed = V2_PARENT_ONLY.get(node_type)
    if allowed is None:
        return ""
    if _v2_insert_parent_type(layout, path) in allowed:
        return ""
    labels = " or ".join(V2_PALETTE_LABELS.get(parent_type, parent_type) for parent_type in allowed)
    return f"Only goes inside a {labels}. Select one first."


def v2_palette_for(layout: dict, path: tuple) -> list[tuple[str, list[tuple[V2PaletteEntry, str]]]]:
    """The whole palette as the Add Element dialog needs it: groups in V2_PALETTE_GROUPS
    order, each holding its entries paired with "" or the reason that entry can't be added
    at this selection.

    Deciding here rather than in guiwins keeps the dialog presentation-only -- it renders
    what it is handed and never reasons about the tree.  Nothing is filtered out: an element
    that can't go here is still shown, greyed, with its reason, because a palette that hides
    things teaches nothing about why.
    """
    return [
        (
            group,
            [(entry, v2_can_add(layout, path, entry.node_type)) for entry in V2_PALETTE if entry.group == group],
        )
        for group in V2_PALETTE_GROUPS
    ]


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
    return v2_move_run(layout, path, 1, offset)


def _v2_splice_run(layout: dict, path: tuple, count: int, insert_at: int) -> tuple | None:
    """Lift `count` consecutive siblings starting at `path` out of their slot and put them
    back at `insert_at`, and return the run's new first path.

    THE ONE PLACE THE INDEX ARITHMETIC HAPPENS.  Every way of moving a run -- the toolbar's
    Up/Down, a drag dropped in a gap -- is the same splice under a different way of naming
    where it lands, and each of those names has its own off-by-one against the other.  So
    they convert to this one, which takes the only unambiguous answer: an index into the
    sibling list *as it stands with the run already lifted out*.  Callers do their own
    conversion (see v2_move_run and v2_drop_run) and this does none.

    Returns None -- changing nothing -- for the root, a run that doesn't sit whole inside one
    slot, a destination outside the list, and a move that would put the run back exactly
    where it was.  That last one is not a failure the caller need report; see v2_drop_run.
    """
    parent, slot, start = _v2_parent_and_slot(layout, path)
    if parent is None or count < 1:
        return None
    siblings = parent.get(slot)
    if not isinstance(siblings, list) or start < 0 or start + count > len(siblings):
        return None
    if insert_at == start or not 0 <= insert_at <= len(siblings) - count:
        return None
    run = siblings[start : start + count]
    del siblings[start : start + count]
    siblings[insert_at:insert_at] = run
    return (*path[:-1], insert_at)


def v2_move_run(layout: dict, path: tuple, count: int, offset: int) -> tuple | None:
    """Move a run of `count` adjacent siblings `offset` places up (negative) or down.

    The run-sized Up/Down: offset is in sibling positions, so +1 steps the whole run past
    the one component below it however many components the run holds.  Returns the run's new
    first path, or None if it can't move that way.
    """
    return _v2_splice_run(layout, path, count, _v2_parent_and_slot(layout, path)[2] + offset)


def v2_drop_run(layout: dict, path: tuple, count: int, before: int) -> tuple | None:
    """Move a run of `count` adjacent siblings so it sits before sibling `before`.

    What a drag drops: `before` is a *gap* in the slot as the user sees it right now -- 0 is
    above the first component, len(siblings) is below the last -- counted with the dragged
    run still in place, because that is the list the gap was aimed at.  Lifting the run out
    shifts every gap below it up by count, which is the correction made here and nowhere
    else.

    Returns the run's new first path, or None if the drop changes nothing (the two gaps
    either side of a run are both where it already is) or can't be made.
    """
    _parent, _slot, start = _v2_parent_and_slot(layout, path)
    return _v2_splice_run(layout, path, count, before - count if before > start else before)


def v2_selection_run(layout: dict, anchor: tuple, other: tuple) -> tuple[tuple, int] | None:
    """The run of adjacent siblings spanned by two selected paths, as (first path, count).

    What a shift-click means, and the one place the "adjacent" in "one or more adjacent
    components" is enforced: two paths span a run only when they address siblings -- the same
    parent and the same slot, which is exactly `path[:-1]` being equal.  Everything between
    two siblings is a sibling, so the span needs no further checking.

    None when they are not siblings, which the caller reads as "start a new selection here"
    rather than as an error.  A tree selection that reached across parents could not be moved
    by any single splice, so it is never allowed to exist.
    """
    if not anchor or not other or anchor[:-1] != other[:-1]:
        return None
    if v2_node_at(layout, anchor) is None or v2_node_at(layout, other) is None:
        return None
    first, last = sorted((anchor[-1], other[-1]))
    return (*anchor[:-1], first), last - first + 1


def v2_run_paths(path: tuple, count: int) -> tuple[tuple, ...]:
    """Every path in a run -- what the tree and the picture both highlight.  The run's own
    invariant is what makes this arithmetic rather than a search: adjacent siblings differ
    only in the last element of their path.
    """
    if not path:
        return ((),)
    return tuple((*path[:-1], path[-1] + step) for step in range(max(1, count)))


def v2_run_is_valid(layout: dict, path: tuple, count: int) -> bool:
    """Does this run still address `count` whole siblings?  Checked before every use of a
    remembered selection, because the tree it was taken from can have been re-rendered,
    undone or edited from the other view since.
    """
    parent, slot, start = _v2_parent_and_slot(layout, path)
    if parent is None or count < 1 or start < 0:
        return False
    siblings = parent.get(slot)
    return isinstance(siblings, list) and start + count <= len(siblings)


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

# What any modifier can carry, whatever its type: the condition deciding whether it applies at
# all.  Universal rather than declared per type because the Scenes in XML/ carry it on six
# unrelated modifiers -- Size, Padding, Alpha, Background, Rotate and VerticalScroll -- which
# says it belongs to modifiers in general rather than to any of them in particular.
#
# An expression in the same language a component's showWhen is written in ("%floatbutton ==
# \"Add\"", "%description_toggle"), which is why it is offered as a plain field rather than a
# pulldown of anything.
V2_MODIFIER_UNIVERSAL_PROPS: tuple[V2Prop, ...] = (V2Prop("applyWhen", "Apply when"),)

# Modifier types and what each takes.  Order within a node's "modifiers" list is
# significant -- they compose in sequence, so Padding-then-Border draws a different thing
# from Border-then-Padding, which is why the editor offers move up/down rather than sorting.
#
# Read off the Version 2 Scenes in XML/ rather than from any published schema (there is none):
# every key below appears in a real Scene, at the spelling written here.  A type or key that
# does not appear is not invented -- see the "no properties observed" group at the end, and
# _v2_unschemad's fallback, which still shows anything a newer Tasker writes.
V2_MODIFIER_SCHEMA: dict[str, tuple[V2Prop, ...]] = {
    # "fraction" is how much of the available space to fill: 0.83, 0.9, 1.  Absent means all
    # of it, which is why most of the 58 FillWidths in the samples carry nothing at all.
    "FillWidth": (V2Prop("fraction", "Fraction", "number"),),
    "FillSize": (V2Prop("fraction", "Fraction", "number"),),
    # INFERRED, and the only inferred entry here: no FillHeight in any sample carries a
    # fraction, but its two siblings above both do, and a "fill the height" that could not be
    # told to fill half of it would be the odd one of the three.
    "FillHeight": (V2Prop("fraction", "Fraction", "number"),),
    "WindowDrag": (),
    # "all" -- one number for both sides -- is the commonest form of this modifier by some way
    # (47 of the samples' Sizes), and was missing here while width/height were not.
    "Size": (
        V2Prop("all", "All", "number"),
        V2Prop("width", "Width", "number"),
        V2Prop("height", "Height", "number"),
    ),
    "SizeIn": (
        V2Prop("minWidth", "Min width", "number"),
        V2Prop("minHeight", "Min height", "number"),
        V2Prop("maxWidth", "Max width", "number"),
        V2Prop("maxHeight", "Max height", "number"),
    ),
    "Padding": (
        V2Prop("all", "All", "number"),
        V2Prop("horizontal", "Horizontal", "number"),
        V2Prop("vertical", "Vertical", "number"),
        V2Prop("start", "Start", "number"),
        V2Prop("end", "End", "number"),
        V2Prop("top", "Top", "number"),
        V2Prop("bottom", "Bottom", "number"),
    ),
    "Offset": (V2Prop("x", "X", "number"), V2Prop("y", "Y", "number")),
    "Clip": (V2Prop("shape", "Shape", "choice", ("Rounded", "Circle")), V2Prop("radius", "Radius", "number")),
    "Border": (
        V2Prop("color", "Colour", "color"),
        V2Prop("shape", "Shape", "choice", ("Rounded", "Circle")),
        V2Prop("radius", "Radius", "number"),
        V2Prop("width", "Width", "number"),
    ),
    "Shadow": (
        V2Prop("elevation", "Elevation", "number"),
        V2Prop("shape", "Shape", "choice", ("Rounded", "Circle")),
        V2Prop("radius", "Radius", "number"),
    ),
    "Background": (V2Prop("color", "Colour", "color"),),
    "Align": (V2Prop("alignment", "Alignment", "choice", ("Start", "Center", "End")),),
    # The one modifier whose value is a state field rather than a plain property: a weight is
    # picked off Compose's scale (V2_FONT_WEIGHTS), or worked out when the Scene is shown.
    "Weight": (v2_state_field("amount").prop,),
    "AspectRatio": (V2Prop("ratio", "Ratio"),),
    "Alpha": (V2Prop("value", "Opacity", "number"),),
    # A fraction rather than a size: the samples' Scales are 0.7, 0.8, 0.9.  Only "all" is
    # ever written in them, so only "all" is offered -- Compose scales each axis separately
    # and Tasker may well too, but under a spelling that is not in evidence here.
    "Scale": (V2Prop("all", "All", "number"),),
    "Rotate": (V2Prop("degrees", "Degrees", "number"),),
    "VerticalScroll": (),
    "HorizontalScroll": (),
    # Listed so they can be added and are named as themselves, with no properties because none
    # of them carries one in any sample.  Blur especially will have something to set (a radius,
    # if it follows Compose) -- but what Tasker calls it is not in evidence here, and a guessed
    # key writes a property Tasker would ignore.  Anything they do carry still shows through
    # the unschema'd fallback in v2_schema_props.
    "Blur": (),
    # Clickable's one key, "actions", is a nested {"click:2": {"task": ...}} rather than a
    # scalar, so it is not offered as a field at all -- it is carried through untouched, and
    # the Task it names is edited where Tasks are edited.
    "Clickable": (),
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


def v2_schema_props(
    schema: dict[str, tuple[V2Prop, ...]],
    item: dict,
    universal: tuple[V2Prop, ...] = (),
) -> list[V2Prop]:
    """The editable properties of a modifier / event / action, from its schema, then any
    `universal` property its kind carries whatever its type, then any other scalar key it
    happens to hold.  The same forward-compatible shape v2_editable_props uses for components,
    and for the same reason: these tables are read off one backup, so anything newer must
    still be visible and editable rather than silently dropped.

    A universal property already named by the type's own schema is not offered twice.
    """
    props = list(schema.get(item.get("type", ""), ()))
    declared = {prop.key for prop in props}
    props += [prop for prop in universal if prop.key not in declared]
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

    # Element renames the designer deferred, applied here because here is where this copy
    # stops being a copy.  Matched against old_name: a Task that addresses this Scene names
    # it as it was, and renaming a Scene has never rewritten those (see this module's
    # docstring), so the Scene name in a Task action is still the one it came in under.
    if edited_scene.element_renames:
        apply_element_renames_to_tasks(old_name, edited_scene.element_renames)
        edited_scene.element_renames.clear()

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
    scene_element: defusedxml.ElementTree.Element,
    sr: str,
) -> defusedxml.ElementTree.Element | None:
    """The element with this sr ("elements3"), or None.

    Selection is held as an sr string rather than as a reference to the element, for the
    reason the V2 designer holds a path rather than a node: the panes are rebuilt on every
    change, and an sr survives that -- as it survives an Undo, which replaces the Scene's
    children wholesale with a restored copy.
    """
    if not sr:
        return None
    return next((child for child in scene_element if child.get("sr") == sr), None)


def legacy_element_label(element: defusedxml.ElementTree.Element) -> str:
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


def legacy_element_args(element: defusedxml.ElementTree.Element) -> list:
    """The element's editable arguments, as taskedit.EditableArg records.

    Empty for an element type actionc.py has no entry for -- a type from a newer Tasker.
    That is deliberately not the same as "no fields": the designer says so, and the element
    is still selectable and still movable, because its geometry is in <geom> and needs no
    schema at all.  Losing the ability to reposition an element this app cannot describe
    would be a much worse answer than showing it with an empty property sheet.
    """
    from maptasker.src.actionc import action_codes  # noqa: PLC0415  (kept off the import path)
    from maptasker.src.taskedit import build_editable_args  # noqa: PLC0415

    action_code = action_codes.get(element.tag)
    if action_code is None:
        return []
    return build_editable_args(element, action_code.args)


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
    from maptasker.src.taskedit import validate_arg_values  # noqa: PLC0415

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
    from maptasker.src.taskedit import apply_arg_values  # noqa: PLC0415

    apply_arg_values([arg], lambda _arg: "value", {"value": str(value)})


def legacy_geometry_values(element: defusedxml.ElementTree.Element) -> list[str]:
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
    element: defusedxml.ElementTree.Element,
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


def legacy_snapshot(scene_element: defusedxml.ElementTree.Element) -> defusedxml.ElementTree.Element:
    """A deep copy of the whole Scene, for the designer's undo stack.

    The whole Scene rather than the one element being changed, and for the same reason the
    V2 designer snapshots its whole tree: it is affordable at this size (the largest Legacy
    Scene in this repo's sample data has 42 elements) and far simpler than modelling an
    inverse for every operation -- which is what phases 2 and 3, where an edit can touch
    several elements' sr attributes at once, would otherwise need.
    """
    return copy.deepcopy(scene_element)


def legacy_restore(
    scene_element: defusedxml.ElementTree.Element,
    snapshot: defusedxml.ElementTree.Element,
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
# Tasker itself produces, and this app does not know what its bits mean (see sceneview).
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


def find_element_name_references(scene_name: str, element_name: str) -> list[str]:
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
    for entry in PrimeItems.tasker_root_elements.get("all_tasks", {}).values():
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


def find_element_match_references(scene_name: str) -> list[str]:
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
    for entry in PrimeItems.tasker_root_elements.get("all_tasks", {}).values():
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
    from maptasker.src.actionc import action_codes  # noqa: PLC0415

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
    from maptasker.src.actionc import action_codes  # noqa: PLC0415

    action_code = action_codes[element_type]
    target = action_codes.get(action_code.redirect) if action_code.redirect else None
    return target.args if target is not None else action_code.args


def legacy_element_names(scene_element: defusedxml.ElementTree.Element) -> set[str]:
    """Every element name currently in the Scene -- what uniqueness is checked against."""
    names = set()
    for child in scene_element:
        if not child.tag.endswith("Element") or child.tag == "PropertiesElement":
            continue
        name_element = child.find("Str[@sr='arg0']")
        if name_element is not None and name_element.text:
            names.add(name_element.text.strip())
    return names


def legacy_next_element_name(scene_element: defusedxml.ElementTree.Element, element_type: str) -> str:
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


def legacy_drawable_elements(scene_element: defusedxml.ElementTree.Element) -> list:
    """The Scene's elements in paint order, bottom first -- the same rule and the same order
    sceneview.paint_order draws them in, kept here so the model can reorder them without the
    editing half having to import the drawing half.
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


def _legacy_reindex(scene_element: defusedxml.ElementTree.Element, ordered: list) -> None:
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


def _legacy_order_arg_children(element: defusedxml.ElementTree.Element) -> None:
    """Put an element's argument children back into argument order.

    Needed because the Img-typed arguments are written separately from the Int/Str ones (see
    legacy_new_element), which would otherwise leave an ImageElement carrying arg0, arg2,
    arg1.  Tasker addresses arguments by their sr and would not care, but a file this app
    writes should be indistinguishable from one Tasker wrote -- and a diff against a Scene
    that was only moved should not show its arguments shuffled.
    """
    args = [child for child in element if child.tag in ("Str", "Int", "Img")]

    def order(child: defusedxml.ElementTree.Element) -> int:
        sr = child.get("sr", "")
        digits = sr[len("arg") :] if sr.startswith("arg") else ""
        return int(digits) if digits.isdigit() else 1_000

    for child in args:
        element.remove(child)
    for child in sorted(args, key=order):
        element.append(child)


def legacy_new_element(
    scene_element: defusedxml.ElementTree.Element,
    element_type: str,
    box: tuple[int, int, int, int],
    *,
    landscape: bool = False,
) -> defusedxml.ElementTree.Element | str:
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
    from maptasker.src.taskedit import build_synthesized_args  # noqa: PLC0415

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
    build_synthesized_args(element_cls, element, effective_args)

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
    scene_element: defusedxml.ElementTree.Element,
    element: defusedxml.ElementTree.Element,
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


def legacy_delete_element(scene_element: defusedxml.ElementTree.Element, sr: str) -> str:
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


def legacy_duplicate_element(scene_element: defusedxml.ElementTree.Element, sr: str) -> str:
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


def legacy_restack(scene_element: defusedxml.ElementTree.Element, sr: str, position: int) -> str:
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
LEGACY_BACKGROUND_TYPES = frozenset({
    "CheckBoxElement",
    "EditTextElement",
    "ImageElement",
    "ListElement",
    "PickerElement",
    "SliderElement",
    "SwitchElement",
    "TextElement",
    "WebElement",
})

# An anonymous inline Task -- Tasker writes these with a negative id and stores them nowhere
# else.  scenes.process_tasks calls them "fake" and skips them for the same reason.
LEGACY_ANONYMOUS_TASK_PREFIX = "-"


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


def legacy_task_tags_for(element: defusedxml.ElementTree.Element) -> list[str]:
    """The Task-binding tags to offer for this element: the ones its type is observed to
    use, plus any it already carries that the table has not heard of.

    The second half is the forward-compatible bit, and the same rule v2_container_slots
    follows: an element from a newer Tasker keeps whatever bindings it arrived with, and they
    stay editable, rather than the editor deciding they do not exist.
    """
    known = list(LEGACY_TASK_TAGS_BY_TYPE.get(element.tag, ()))
    present = [child.tag for child in element if child.tag in SCENE_TASK_TYPES and child.tag not in known]
    return known + present


def legacy_task_bindings(element: defusedxml.ElementTree.Element) -> list[LegacyBinding]:
    """Every Task this element currently fires, resolved to names where it can be.

    A binding whose id is not in the loaded backup is reported under its id rather than
    dropped -- it is still what the Scene will run, and hiding it would make the Tasks
    section disagree with the file.
    """
    all_tasks = PrimeItems.tasker_root_elements.get("all_tasks", {})
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
    element: defusedxml.ElementTree.Element,
    child: defusedxml.ElementTree.Element,
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
    element: defusedxml.ElementTree.Element,
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


def legacy_clear_task_binding(element: defusedxml.ElementTree.Element, tag: str) -> None:
    """Stop this element firing anything on this event."""
    child = element.find(tag)
    if child is not None:
        element.remove(child)


def legacy_task_choices() -> list[str]:
    """Every Task name in the loaded backup, sorted -- what a binding can be pointed at.

    The same list the Task editor's own 'Perform Task' picker offers
    (taskedit.get_all_task_names), so the two never disagree about what exists.
    """
    return sorted(PrimeItems.tasker_root_elements.get("all_tasks_by_name", {}))


def legacy_task_id_for_name(task_name: str) -> str:
    """The id of the Task with this name, or "" -- how a picked name becomes what the XML
    stores.
    """
    entry = PrimeItems.tasker_root_elements.get("all_tasks_by_name", {}).get(task_name)
    return str(entry["id"]) if entry else ""


def legacy_background(element: defusedxml.ElementTree.Element) -> defusedxml.ElementTree.Element | None:
    """The element's <RectElement sr="background">, or None."""
    return element.find("RectElement[@sr='background']")


def legacy_can_have_background(element: defusedxml.ElementTree.Element) -> bool:
    """Whether Tasker gives this element type a background sub-element (see
    LEGACY_BACKGROUND_TYPES).  A Button, a Rect and an Oval draw their own fill through their
    own arguments and never carry one.
    """
    return element.tag in LEGACY_BACKGROUND_TYPES


def legacy_add_background(element: defusedxml.ElementTree.Element) -> defusedxml.ElementTree.Element | None:
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

    from maptasker.src.taskedit import build_synthesized_args  # noqa: PLC0415

    element_cls = type(element)
    background = element_cls("RectElement", {"sr": "background"})
    geometry = element_cls("geom")
    geometry.text = ",".join([UNSET_DIMENSION] * LEGACY_GEOM_VALUES)
    background.append(geometry)
    build_synthesized_args(element_cls, background, _legacy_effective_args("RectElement"))
    _legacy_order_arg_children(background)
    element.append(background)
    return background


def legacy_remove_background(element: defusedxml.ElementTree.Element) -> None:
    """Take the background away again."""
    background = legacy_background(element)
    if background is not None:
        element.remove(background)


def legacy_scene_properties(
    scene_element: defusedxml.ElementTree.Element,
) -> defusedxml.ElementTree.Element | None:
    """The Scene's own <PropertiesElement>, or None -- 66 of 366 sample Scenes have none."""
    return scene_element.find("PropertiesElement")


def legacy_add_scene_properties(
    scene_element: defusedxml.ElementTree.Element,
) -> defusedxml.ElementTree.Element:
    """Give the Scene a <PropertiesElement>, at the end where Tasker keeps it."""
    existing = legacy_scene_properties(scene_element)
    if existing is not None:
        return existing

    from maptasker.src.taskedit import build_synthesized_args  # noqa: PLC0415

    element_cls = type(scene_element)
    properties = element_cls("PropertiesElement", {"sr": "props"})
    build_synthesized_args(element_cls, properties, _legacy_effective_args("PropertiesElement"))
    _legacy_order_arg_children(properties)
    scene_element.append(properties)
    return properties


def find_element_name_actions(scene_name: str, element_name: str) -> list[tuple[str, object]]:
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
    for entry in PrimeItems.tasker_root_elements.get("all_tasks", {}).values():
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


def apply_element_renames_to_tasks(scene_name: str, renames: list[tuple[str, str]]) -> int:
    """Rewrite the Task actions that address these elements by name.  Returns how many
    argument values were changed.

    Applied in the order the renames were made, so an element renamed twice (A to B, then B
    to C) ends up addressed as C rather than being missed by the second pass.

    Called from apply_edited_scene_to_live_tree and nowhere else -- see
    EditableScene.element_renames on why this cannot happen while the dialog is still open.
    """
    changed = 0
    for old_name, new_name in renames:
        for _task_name, argument in find_element_name_actions(scene_name, old_name):
            argument.text = new_name
            changed += 1
    return changed


def legacy_rename_element(
    scene_element: defusedxml.ElementTree.Element,
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
    element: defusedxml.ElementTree.Element,
) -> defusedxml.ElementTree.Element | None:
    """The nested <Scene sr="val"> holding this element's row layout, or None.

    None covers both "this type never has one" and "this one has not been given one", and
    the caller does not need to tell those apart: neither can be edited.
    """
    slot = LEGACY_ITEM_LAYOUT_SLOT.get(element.tag)
    if slot is None:
        return None
    return element.find(f"Scene[@sr='{slot}']/Scene[@sr='val']")


def legacy_item_layout_name(element: defusedxml.ElementTree.Element) -> str:
    """What the item layout calls itself -- "Builtin Item Layout" for a List, "spinner" for
    a Spinner, in every sample.  For the nested dialog's title, so it says which layout is
    being edited rather than just "Scene".
    """
    layout = legacy_item_layout(element)
    return (layout.findtext("nme") or "").strip() if layout is not None else ""
