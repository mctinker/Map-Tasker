"""sceneview_v2: drawing a Version 2 Scene -- a component tree mapped onto CSS flexbox.

draw_v2_layout walks the tree inside a device-sized frame; each component type has a drawer here, and the
path and editing state the designer's canvas reads back live with them."""

from __future__ import annotations

from nicegui import ui

from maptasker.src.core.maputil2 import translate_string
from maptasker.src.core.sysconst import V2_MATERIAL_PALETTE
from maptasker.src.gui.sceneview import PLACEHOLDER_EDGE, PLACEHOLDER_FILL, VARIABLE_FILL, PreviewOptions, V2Editing
from maptasker.src.gui.sceneview_legacy import corner_badge, html_frame, is_inline_html, placeholder_box
from maptasker.src.gui.sceneview_v2base import (
    V2_ALIGNMENT,
    V2_ARRANGEMENT,
    V2_MAX_DEPTH,
    v2_app_icon,
    v2_colour,
    v2_icon,
)
from maptasker.src.gui.sceneview_v2style import v2_handler_lines, v2_modifier_style, v2_number
from maptasker.src.gui.sceneview_v2text import (
    v2_bounds_label,
    v2_condition_badge,
    v2_event_badge,
    v2_html_text,
    v2_is_html,
    v2_text,
    v2_text_style,
    v2_tooltip,
)


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
    handlers = v2_handler_lines(layout)
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
# guiwins_canvas._emit_v2_hull, and the two change together.
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
    as strings, which is what sceneedit_v2tree.v2_node_at indexes with.

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

    frame = (
        ui.element("div")
        .classes("mt-scene-canvas")
        .style(
            f"position: relative; width: {width}px; height: {height}px; overflow: hidden;"
            f"transform-origin: top left; box-sizing: border-box;"
            f"background: {V2_MATERIAL_PALETTE['background']}; color: {V2_MATERIAL_PALETTE['onBackground']};"
            "font-family: Roboto, system-ui, sans-serif;",
        )
    )
    if editing is not None:
        # The selected run, for the drag handlers to read off the canvas: where it starts and
        # how long it is.  The same two attributes the designer's tree pane carries, and put
        # here for the same reason -- see guiwins_canvas._v2_selection_props.
        frame.props(
            f'data-mt-v2-sel="{v2_encode_path(editing.selected[0] if editing.selected else ())}" '
            f'data-mt-v2-count="{max(1, len(editing.selected))}"',
        )
    with frame:
        if not isinstance(root, dict):
            placeholder_box("layers_clear", "This layout has no root component")
            return
        _v2_hull()
        if is_dialog:
            with (
                ui.element("div").style(
                    "position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;"
                    "background: rgba(0,0,0,0.32); padding: 24px; box-sizing: border-box;",
                ),
                ui.element("div").style(
                    f"max-width: 100%; max-height: 100%; overflow: hidden; border-radius: 28px;"
                    f"background: {V2_MATERIAL_PALETTE['surface']}; box-shadow: 0 8px 24px rgba(0,0,0,0.25);",
                ),
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
    therefore drawn empty and positioned by guiwins_canvas._emit_v2_hull once the layout has been
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

    Deliberately the same rule sceneedit_v2tree.v2_child_slots uses -- any list of component-shaped
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
    if depth > V2_MAX_DEPTH:
        placeholder_box("more_horiz", "Nested too deep to draw")
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
    style += v2_modifier_style(node)
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
            v2_condition_badge(node)
        if options.show_bounds:
            v2_bounds_label(node)
        if options.show_tasks:
            v2_event_badge(node)
    v2_tooltip(container, node)


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
        justify=V2_ARRANGEMENT.get(str(node.get("verticalArrangement", "")), "flex-start"),
        align=V2_ALIGNMENT.get(str(node.get("horizontalAlignment", "")), "stretch"),
    )


def _v2_draw_row(node: dict, options: PreviewOptions, depth: int) -> None:
    """Row: children side by side.  The two properties swap roles against a Column's."""
    _v2_draw_stack(
        node,
        options,
        depth,
        direction="row",
        justify=V2_ARRANGEMENT.get(str(node.get("horizontalArrangement", "")), "flex-start"),
        align=V2_ALIGNMENT.get(str(node.get("verticalAlignment", "")), "center"),
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
        justify=V2_ARRANGEMENT.get(str(node.get("horizontalArrangement", "")), "flex-start"),
        align="center",
        wrap=True,
        gap_css=_v2_axis_gap(column=v2_number(node, "spacingHorizontal"), row=v2_number(node, "spacingVertical")),
    )


def _v2_draw_flow_column(node: dict, options: PreviewOptions, depth: int) -> None:
    """FlowColumn: stacks downwards, wrapping into a new column when it runs out of height."""
    _v2_draw_stack(
        node,
        options,
        depth,
        direction="column",
        justify=V2_ARRANGEMENT.get(str(node.get("horizontalArrangement", "")), "flex-start"),
        align=V2_ALIGNMENT.get(str(node.get("itemHorizontalAlignment", "")), "stretch"),
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
        justify=V2_ARRANGEMENT.get(str(node.get("alignContent", "")), "flex-start"),
        align=V2_ALIGNMENT.get(str(node.get("alignItems", "")), "stretch"),
        wrap=str(node.get("wrap", "Wrap")) != "NoWrap",
        gap_css=_v2_axis_gap(column=v2_number(node, "gap"), row=v2_number(node, "gap")),
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
        spacing = v2_number(node, "spacing")
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
    elevation = v2_number(node, "elevation") or "1px"
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


def _v2_draw_navigation_item(node: dict, _options: PreviewOptions, _depth: int) -> None:
    """NavigationItem: an icon over a label, tinted when it is the selected one."""
    is_selected = str(node.get("selected", "")).lower() == "true"
    colour = V2_MATERIAL_PALETTE["onSecondaryContainer" if is_selected else "onSurfaceVariant"]
    with ui.element("div").style(
        "display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px;"
        "padding: 4px 8px; box-sizing: border-box;"
        + (f"background: {V2_MATERIAL_PALETTE['secondaryContainer']}; border-radius: 16px;" if is_selected else ""),
    ):
        _v2_icon_or_placeholder(node.get("icon"), 24, colour)
        v2_text(node.get("label"), f"font-size: 12px; line-height: 1.2; color: {colour};")


def _v2_draw_text(node: dict, _options: PreviewOptions, _depth: int) -> None:
    """Text: the component real Scenes are mostly made of."""
    if v2_is_html(node):
        v2_html_text(node, v2_text_style(node))
        return
    v2_text(node.get("text"), v2_text_style(node))


def _v2_draw_button(node: dict, _options: PreviewOptions, _depth: int) -> None:
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
        v2_text(
            node.get("text"),
            f"font-size: 14px; line-height: 1.2; font-weight: 500;"
            f"color: {'rgba(255,255,255,0.85)' if foreground.is_variable else foreground.css};",
        )


def _v2_draw_icon_button(node: dict, _options: PreviewOptions, _depth: int) -> None:
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


def _v2_draw_text_input(node: dict, _options: PreviewOptions, _depth: int) -> None:
    """TextInput: an outlined field showing its label.  What it writes into is on its badge
    (see v2_binding_lines) -- for a text field that is the interesting half.
    """
    with ui.element("div").style(
        f"display: flex; align-items: center; width: 100%; min-height: 56px; padding: 8px 16px;"
        f"box-sizing: border-box; border: 1px solid {V2_MATERIAL_PALETTE['outline']}; border-radius: 4px;",
    ):
        v2_text(
            node.get("label") or node.get("text"),
            v2_text_style(node, default_colour=V2_MATERIAL_PALETTE["onSurfaceVariant"]),
        )


def _v2_draw_switch(node: dict, _options: PreviewOptions, _depth: int) -> None:
    """Switch: on or off, from `checked`."""
    _v2_draw_toggle(node, "toggle_on", "toggle_off")


def _v2_draw_checkbox(node: dict, _options: PreviewOptions, _depth: int) -> None:
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
            v2_text(raw, "font-size: 11px; line-height: 1.2;")


def _v2_draw_slider(node: dict, _options: PreviewOptions, _depth: int) -> None:
    """Slider: the thumb where `value` falls between min and max."""
    minimum = _v2_float(node.get("min"), 0.0)
    maximum = _v2_float(node.get("max"), 100.0)
    value = _v2_float(node.get("value"), minimum)
    span = maximum - minimum
    fraction = 0.0 if span <= 0 else max(0.0, min(1.0, (value - minimum) / span))
    _v2_draw_track([fraction])


def _v2_draw_range_slider(node: dict, _options: PreviewOptions, _depth: int) -> None:
    """RangeSlider: two thumbs, at `start` and `end`, on a 0-1 scale of its own."""
    _v2_draw_track(
        [
            max(0.0, min(1.0, _v2_float(node.get("start"), 0.0))),
            max(0.0, min(1.0, _v2_float(node.get("end"), 1.0))),
        ],
    )


def _v2_draw_track(fractions: list[float]) -> None:
    """A slider's track with a thumb at each of these positions, and the range between the
    first and last drawn as the active part -- which is what makes a RangeSlider read as a
    range rather than as two unrelated dots.
    """
    low, high = min(fractions), max(fractions)
    with (
        ui.element("div").style("display: flex; align-items: center; width: 100%; height: 32px; padding: 0 8px;"),
        ui.element("div").style(
            "position: relative; width: 100%; height: 4px; border-radius: 999px;"
            f"background: {V2_MATERIAL_PALETTE['surfaceVariant']};",
        ),
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


def _v2_draw_progress(node: dict, _options: PreviewOptions, _depth: int) -> None:
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
    selected = {index.strip() for index in str(node.get("selectedIndices", "")).split(",") if index.strip().isdigit()}
    with ui.element("div").style(
        f"display: inline-flex; border: 1px solid {V2_MATERIAL_PALETTE['outline']}; border-radius: 20px;"
        f"overflow: hidden; box-sizing: border-box;",
    ):
        for index, child in enumerate(_v2_all_children(node)):
            marked = _v2_alias(dict(child), child)
            marked["selected"] = "true" if str(index) in selected else "false"
            _v2_draw_node(marked, options, depth + 1)


def _v2_draw_segmented_item(node: dict, _options: PreviewOptions, _depth: int) -> None:
    """SegmentedButtonItem: one segment of that control."""
    is_selected = str(node.get("selected", "")).lower() == "true"
    with ui.element("div").style(
        "display: flex; align-items: center; justify-content: center; padding: 8px 16px; gap: 4px;"
        "box-sizing: border-box;"
        + (f"background: {V2_MATERIAL_PALETTE['secondaryContainer']};" if is_selected else ""),
    ):
        if is_selected:
            ui.icon("check").style(f"font-size: 16px; color: {V2_MATERIAL_PALETTE['onSecondaryContainer']};")
        v2_text(
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


def _v2_draw_variable(node: dict, _options: PreviewOptions, _depth: int) -> None:
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


def _v2_draw_spacer(node: dict, _options: PreviewOptions, _depth: int) -> None:
    """Spacer: empty space of a fixed size."""
    height = v2_number(node, "height") or "16px"
    width = v2_number(node, "width")
    ui.element("div").style(f"height: {height};{f'width: {width};' if width else 'width: 100%;'} flex: none;")


def _v2_draw_divider(node: dict, _options: PreviewOptions, _depth: int) -> None:
    """Divider: a rule across its container."""
    colour = v2_colour(node.get("color"), fallback=V2_MATERIAL_PALETTE["outlineVariant"])
    ui.element("div").style(f"width: 100%; height: 1px; background: {colour.css}; flex: none;")


def _v2_draw_image(node: dict, _options: PreviewOptions, _depth: int) -> None:
    """Image: a named icon, or a URL that is deliberately not fetched.

    An icon: reference draws as the real icon.  A URL does not: previewing a Scene should not
    make this app go to the network on behalf of a file someone else wrote, and a URL that is
    a %variable could not be fetched anyway.  So it is named instead.
    """
    icon = v2_icon(node.get("icon"))
    width = v2_number(node, "width")
    height = v2_number(node, "height")
    box = f"{f'width: {width};' if width else ''}{f'height: {height};' if height else ''}"
    if icon:
        with ui.element("div").style(f"display: inline-flex; align-items: center; justify-content: center; {box}"):
            ui.icon(icon).style(f"font-size: {height or '32px'}; color: {V2_MATERIAL_PALETTE['onSurfaceVariant']};")
        return
    package = v2_app_icon(node.get("icon"))
    if package:
        # Named rather than drawn, for the reason at v2_app_icon -- and named as the app it
        # is, rather than falling through to the "Image" panel below, which would say only
        # that something unshowable goes here.
        with ui.element("div").style(f"{box or 'width: 100%; height: 96px;'} position: relative; flex: none;"):
            placeholder_box("android", "App icon", package)
        return
    url = str(node.get("url", "") or node.get("icon", ""))
    with ui.element("div").style(f"{box or 'width: 100%; height: 96px;'} position: relative; flex: none;"):
        placeholder_box("image", "Image", url.rsplit("/", 1)[-1] if url else "")


def _v2_draw_web_view(node: dict, _options: PreviewOptions, _depth: int) -> None:
    """WebView: an embedded page, or HTML held in a variable.

    Inline HTML is drawn, in the same sandboxed frame the Legacy WebElement uses -- see
    _draw_web and WEB_SANDBOX.  A `content` that names a page instead of holding one, or
    that is a %variable, keeps the panel.

    No density here: a V2 layout is already laid out in dp, which this renderer maps to CSS
    pixels one-for-one, so the frame is simply the box it was given.
    """
    height = v2_number(node, "height") or "120px"
    content = str(node.get("content", ""))
    with ui.element("div").style(f"position: relative; width: 100%; height: {height}; flex: none;"):
        if is_inline_html(content):
            html_frame(content, "position: absolute; inset: 0; width: 100%; height: 100%;", background="#fff")
            corner_badge("HTML")
        else:
            placeholder_box("public", "WebView", content.splitlines()[0][:60] if content else "")


def _v2_draw_video(node: dict, _options: PreviewOptions, _depth: int) -> None:
    """Video: source, and whether it starts itself and loops."""
    flags = [name for name in ("autoPlay", "loop") if str(node.get(name, "")).lower() == "true"]
    caption = f"Video ({', '.join(flags)})" if flags else "Video"
    detail = str(node.get("source", ""))
    with ui.element("div").style("position: relative; width: 100%; height: 140px; flex: none;"):
        placeholder_box("movie", caption, detail.rsplit("/", 1)[-1])


def _v2_draw_camera(node: dict, _options: PreviewOptions, _depth: int) -> None:
    """Camera: a live preview from one of the device's lenses."""
    with ui.element("div").style("position: relative; width: 100%; height: 140px; flex: none;"):
        placeholder_box("photo_camera", "Camera", str(node.get("lens", "")))


def _v2_draw_placeholder(_node: dict, _options: PreviewOptions, _depth: int) -> None:
    """Placeholder: Tasker's own blank stand-in, for reserving space while building."""
    with ui.element("div").style("position: relative; width: 100%; height: 48px; flex: none;"):
        placeholder_box("crop_free", "Placeholder")


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
    package = v2_app_icon(raw)
    if package:
        # The app's real icon is on the phone (see v2_app_icon).  A generic glyph at the
        # right size and place says "an app icon goes here" without inventing which one; the
        # tooltip is where the package name goes, there being no room for it at 48px.
        with ui.icon("android").style(f"font-size: {size}px; color: {colour};"):
            ui.tooltip(f"{translate_string('App icon')}: {package}")
        return
    text = str(raw or "")
    if text:
        v2_text(text, f"font-size: {max(9, size // 2)}px; line-height: 1.2; color: {colour};")


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
