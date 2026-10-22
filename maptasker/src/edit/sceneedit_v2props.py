"""sceneedit_v2props: a component's properties, grouped for the inspector and written back.

The Text component's property categories, the nested and 'other' groups, and v2_set_prop and v2_set_state,
which coerce what was typed to the type the property already holds."""

from __future__ import annotations

from maptasker.src.edit.sceneedit_v2 import (
    ALIGNMENT,
    V2_DYNAMIC_STATE,
    V2_ID_PROP,
    V2_STRUCTURAL_KEYS,
    V2_TEXT_STYLE,
    V2_VARIABLE_STATE,
    VERTICAL_ALIGNMENT,
    V2Prop,
    V2StateField,
)
from maptasker.src.edit.sceneedit_v2state import v2_state_field
from maptasker.src.edit.sceneedit_v2tree import v2_editable_props


def v2_set_state(field: V2StateField, node: V2Props, state: str, value: str = "") -> None:
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
            V2Prop("textAlign", "Alignment", "choice", ALIGNMENT),
            V2Prop("verticalAlignment", "Vertical alignment", "choice", VERTICAL_ALIGNMENT),
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
        """Hold the node and the name of the container on it that this view reads and writes."""
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
        """The value under this key, or the default."""
        return self._held.get(key, default)

    def items(self) -> object:
        """The container's key/value pairs."""
        return self._held.items()

    def __contains__(self, key: str) -> bool:
        """Whether the container holds this key."""
        return key in self._held

    def __getitem__(self, key: str) -> object:
        """The value under this key; KeyError if it is not there."""
        return self._held[key]

    def __setitem__(self, key: str, value: object) -> None:
        """Set the key, creating the container if the node never had one."""
        held = self._writable()
        if held is not None:
            held[key] = value

    def __delitem__(self, key: str) -> None:
        """Remove the key if present, and the container itself once it is empty."""
        self._held.pop(key, None)
        self._prune()

    def pop(self, key: str, default: object = None) -> object:
        """Remove the key and return what it held, or the default."""
        value = self._held.pop(key, default)
        self._prune()
        return value


# What a property is read from and written to: the node itself, or the nested object it lives in.
V2Props = dict | V2NestedProps


def v2_prop_dict(node: dict, prop: V2Prop) -> V2Props:
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


def v2_set_prop(node: V2Props, key: str, text: str) -> None:
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
