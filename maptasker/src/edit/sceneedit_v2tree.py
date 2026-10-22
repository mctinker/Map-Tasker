"""sceneedit_v2tree: addressing and describing the nodes of a Version 2 Scene's component tree.

A node's name and label, the flattened rows the tree view shows, finding a node by path, and the properties
an editor lists for it.  Read-only: the edits themselves are sceneedit_v2nodes and sceneedit_v2props."""

from __future__ import annotations

import html
from dataclasses import dataclass

from maptasker.src.core.maputil2 import strip_html_tags, tasker_icon_name
from maptasker.src.core.scenelayout import V2_ROOT_KEY
from maptasker.src.edit.sceneedit_v2 import (
    V2_BELOW_SHOW_WHEN_PROPS,
    V2_COMPONENT_SCHEMA,
    V2_ID_PROP,
    V2_STATE_FIELDS,
    V2_STRUCTURAL_KEYS,
    V2_UNIVERSAL_PROPS,
    V2Prop,
)
from maptasker.src.edit.sceneedit_v2state import v2_state_field, v2_state_of

# The layout JSON's top-level key holding the component tree is scenelayout.V2_ROOT_KEY: the one thing
# the Version 2 model takes from the XML side.  (Its sibling, the Scene's name, is scenelayout.V2_NAME_KEY:
# only a rename, which is scenelayout's, ever touches it.)


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
        own_value = html.unescape(strip_html_tags(own_value))
    if own_value and own_key in _V2_ICON_KEYS:
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

    root = layout.get(V2_ROOT_KEY)
    if isinstance(root, dict):
        walk(root, 0, (), V2_ROOT_KEY)
    return rows


def v2_node_at(layout: dict, path: tuple) -> dict | None:
    """The node a v2_flatten path points at, or None if the path no longer resolves
    (defence in depth -- phase 1 can't restructure the tree, so it always should).
    """
    node = layout.get(V2_ROOT_KEY)
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
