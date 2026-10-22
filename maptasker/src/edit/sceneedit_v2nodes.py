"""sceneedit_v2nodes: the structural edits of a Version 2 Scene -- add, delete, move, indent, duplicate.

The palette of components that can be added, where each may go, and every edit that changes the shape of the
tree.  Edits are applied in place, so an untouched Scene re-encodes to the layout it came from."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING

from maptasker.src.edit.sceneedit_v2tree import v2_child_slots, v2_flatten, v2_node_at

if TYPE_CHECKING:
    from maptasker.src.core.primitem import RunState


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
    # "content", not "children" -- the dialog-builder Project's compiler builds its rows as
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
# real -- a decoded <lj> in XML/*.xml, or the dialog-builder Project's compiler, which
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
    # Traced to the dialog-builder compiler's own buildButtonRow(), including the string
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
    carries Scaffold1/TopAppBar1/Text1/Text2/NavItem1..3) and how the dialog-builder
    Project's nextId() does it.  Predictable, collision-free, and readable in a Task that
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


def find_component_id_references(scene_name: str, component_id: str, state: RunState) -> list[str]:
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
    for entry in state.tasker_root_elements.get("all_tasks", {}).values():
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
