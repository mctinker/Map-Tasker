"""sceneedit_v2: the model the Version 2 Scene designer edits.

Split out of sceneedit.py, which held both kinds of Scene and had grown past 5,000 lines.
A Version 2 Scene is a component tree -- Columns, Rows, Texts, Buttons -- decoded from the
Scene's <lj> child (scenelayout.decode_v2_layout).  Everything is done on that decoded tree as a
plain dict.  This module is the schema of what each component type can hold and set; the work on it is in:

    sceneedit_v2tree     addressing, naming and flattening the tree
    sceneedit_v2state    state fields and the Show-When condition
    sceneedit_v2props    properties: grouping them and writing them back
    sceneedit_v2nodes    the structural edits: add, delete, move, indent, duplicate
    sceneedit_v2events   modifiers, event handlers, actions and variable bindings

It never touches XML, which is scenelayout's (decoding and re-encoding <lj>) and sceneedit's
(creating, renaming, saving and deleting a Scene as a whole).  Nothing in either imports it
directly: scenemodel is what the rest of the program asks about a Scene of either kind.
"""

from __future__ import annotations

from dataclasses import dataclass

from maptasker.src.core.maputil2 import is_html_colour
from maptasker.src.core.sysconst import V2_MATERIAL_PALETTE

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


_ARRANGEMENT = ("Start", "Center", "End", "SpaceBetween", "SpaceAround", "SpaceEvenly")


ALIGNMENT = ("Start", "Center", "End")


VERTICAL_ALIGNMENT = ("Top", "Center", "Bottom")


# What each component type offers the inspector.  Derived from what actually appears in
# XML/backup.xml -- the three Version 2 Scenes plus everything the dialog-builder
# Project's builder Task emits -- because Tasker publishes no schema for this format, so
# observed usage is the only schema there is.
#
# A type missing from here still opens and still edits: _v2_unschemad_props falls back to
# offering its scalar keys as plain text fields.  That matters for forward compatibility --
# a Scene from a newer Tasker will carry components this table has never seen, and the
# designer must not be the reason they can't be touched.
V2_COMPONENT_SCHEMA: dict[str, tuple[V2Prop, ...]] = {
    "Column": (
        V2Prop("horizontalAlignment", "Horizontal alignment", "choice", ALIGNMENT),
        V2Prop("verticalArrangement", "Vertical arrangement", "choice", _ARRANGEMENT),
        V2Prop("spacing", "Spacing", "number"),
    ),
    "Row": (
        V2Prop("horizontalArrangement", "Horizontal arrangement", "choice", _ARRANGEMENT),
        V2Prop("verticalAlignment", "Vertical alignment", "choice", VERTICAL_ALIGNMENT),
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
        V2Prop("textAlign", "Text alignment", "choice", ALIGNMENT),
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
        V2Prop("alignment", "Alignment", "choice", ALIGNMENT),
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
        V2Prop("itemHorizontalAlignment", "Item alignment", "choice", ALIGNMENT),
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
