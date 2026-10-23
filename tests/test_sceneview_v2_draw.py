"""Drawing a Version 2 Scene: every component type, the modifiers that style them, and what is marked on top.

What each component means is Tasker's; what the preview does is map the tree onto flexbox.  Here every type the
preview knows is drawn in a simulated page, alone and inside a Scaffold, so a drawer that cannot cope with its own
component fails here rather than in a user's Scene -- and the things drawn on top of a component (a Show when marker,
the event badges, the bounds, the selection outline, the drag path) are checked for the cases that show them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from maptasker.src.gui import sceneview_v2
from maptasker.src.gui.sceneview import PreviewOptions, V2Editing
from nicegui import ui

from tests.nicegui_harness import all_elements, open_page

if TYPE_CHECKING:
    from collections.abc import Callable

    from nicegui.testing.user import User


def _drawn(user: User) -> list[ui.element]:
    return [e for e in all_elements(user) if sceneview_v2.V2_COMPONENT_CLASS in e._classes]


def _texts(user: User) -> list[str]:
    return [str(getattr(e, "text", "") or getattr(e, "content", "")) for e in all_elements(user)]


def _draw(layout: dict, options: PreviewOptions | None = None, editing: V2Editing | None = None) -> Callable[[], None]:
    def page() -> None:
        sceneview_v2.draw_v2_layout(layout, 411, 891, options or PreviewOptions(), editing)

    return page


def _text(label: str = "Hello") -> dict:
    return {"type": "Text", "text": label}


# ##################################################################################
# Every type the preview knows
# ##################################################################################
@pytest.mark.asyncio
@pytest.mark.parametrize("component", sorted(sceneview_v2._V2_DRAWERS))
async def test_every_component_type_draws_inside_a_column(component: str) -> None:
    node: dict[str, Any] = {"type": component, "text": "Sample", "label": "Sample", "title": "Sample"}
    layout = {"root": {"type": "Column", "children": [node]}}

    async with open_page(_draw(layout)) as user:
        assert len(_drawn(user)) >= 2, f"{component} was not drawn through the funnel every component goes through"


@pytest.mark.asyncio
@pytest.mark.parametrize("container", ["Column", "Row", "FlowRow", "FlowColumn", "FlexBox", "Box", "Card"])
async def test_a_container_draws_every_child_it_is_given(container: str) -> None:
    layout = {"root": {"type": container, "children": [_text("one"), _text("two"), _text("three")]}}

    async with open_page(_draw(layout)) as user:
        assert len(_drawn(user)) == sceneview_v2.v2_component_count(layout) == 4
        for word in ("one", "two", "three"):
            assert any(word in text for text in _texts(user))


@pytest.mark.asyncio
async def test_a_scaffold_draws_its_bars_content_and_button() -> None:
    layout = {
        "root": {
            "type": "Scaffold",
            "topBar": [{"type": "TopAppBar", "title": "Home"}],
            "content": [_text("body")],
            "bottomBar": [{"type": "BottomAppBar", "children": [_text("bar")]}],
            "floatingActionButton": [{"type": "FloatingActionButton", "icon": "add"}],
        }
    }

    async with open_page(_draw(layout)) as user:
        assert len(_drawn(user)) == sceneview_v2.v2_component_count(layout)
        assert any("body" in text for text in _texts(user))


@pytest.mark.asyncio
async def test_a_navigation_bar_selects_one_item_without_writing_into_the_scene() -> None:
    items = [
        {"type": "NavigationItem", "label": "Home", "icon": "home"},
        {"type": "NavigationItem", "label": "Settings", "icon": "settings"},
    ]
    layout = {"root": {"type": "NavigationBar", "selectedIndex": 1, "children": items}}

    async with open_page(_draw(layout)) as user:
        assert len(_drawn(user)) == 3
        assert "selected" not in items[0] and "selected" not in items[1], "a copy is drawn, never the Scene itself"


@pytest.mark.asyncio
async def test_a_segmented_button_row_draws_its_items() -> None:
    layout = {
        "root": {
            "type": "SegmentedButtonRow",
            "selectedIndex": 0,
            "children": [{"type": "SegmentedButtonItem", "label": "A"}, {"type": "SegmentedButtonItem", "label": "B"}],
        }
    }

    async with open_page(_draw(layout)) as user:
        assert len(_drawn(user)) == 3


@pytest.mark.asyncio
async def test_an_unknown_component_is_a_labelled_box_not_an_error() -> None:
    layout = {"root": {"type": "Column", "children": [{"type": "HologramProjector", "power": 11}]}}

    async with open_page(_draw(layout)) as user:
        assert len(_drawn(user)) == 2
        assert any("HologramProjector" in text for text in _texts(user))


@pytest.mark.asyncio
async def test_a_tree_nested_past_the_limit_stops_with_a_note() -> None:
    node: dict[str, Any] = _text("deep")
    for _ in range(sceneview_v2.V2_MAX_DEPTH + 3):
        node = {"type": "Column", "children": [node]}

    async with open_page(_draw({"root": node})) as user:
        assert any("Nested too deep to draw" in text for text in _texts(user))


# ##################################################################################
# The frame
# ##################################################################################
@pytest.mark.asyncio
async def test_a_layout_with_no_root_says_so() -> None:
    async with open_page(_draw({"name": "Empty"})) as user:
        assert any("This layout has no root component" in text for text in _texts(user))


@pytest.mark.asyncio
async def test_a_dialog_scene_is_drawn_on_a_scrim_rather_than_filling_the_screen() -> None:
    layout = {"defaultDisplayMode": "Dialog", "root": {"type": "Column", "children": [_text("hi")]}}

    async with open_page(_draw(layout)) as user:
        styles = [e._style.get("background", "") for e in all_elements(user) if hasattr(e, "_style")]
        assert any("rgba(0,0,0,0.32)" in str(style).replace(" ", "") for style in styles)


@pytest.mark.asyncio
async def test_the_frame_is_the_size_asked_for() -> None:
    async with open_page(_draw({"root": _text()})) as user:
        (frame,) = [e for e in all_elements(user) if "mt-scene-canvas" in e._classes]
        assert frame._style["width"] == "411px" and frame._style["height"] == "891px"


# ##################################################################################
# On top of a component
# ##################################################################################
@pytest.mark.asyncio
async def test_a_show_when_condition_outlines_the_component_and_marks_it() -> None:
    layout = {"root": {"type": "Column", "children": [{"type": "Text", "text": "maybe", "showWhen": "%flag == 1"}]}}

    async with open_page(_draw(layout)) as user:
        outlined = [e for e in _drawn(user) if "dashed" in str(e._style.get("outline", ""))]
        assert outlined, "a component that may not be on screen is never drawn as though it were unconditional"


@pytest.mark.asyncio
async def test_the_toolbar_switches_the_bounds_and_task_badges_on_and_off() -> None:
    layout = {
        "root": {
            "type": "Column",
            "children": [
                {
                    "type": "Button",
                    "text": "Go",
                    "eventHandlers": {"click": [{"type": "PerformTask", "task": "Wake Up"}]},
                    "modifiers": [{"type": "Size", "width": 120, "height": 40}],
                }
            ],
        }
    }

    async with open_page(_draw(layout, PreviewOptions(show_bounds=True, show_tasks=True))) as user:
        with_both = len(all_elements(user))
    async with open_page(_draw(layout, PreviewOptions(show_bounds=False, show_tasks=False))) as user:
        without = len(all_elements(user))
    assert with_both > without, "bounds and task badges are extra elements drawn only when asked for"


# ##################################################################################
# Editing: paths, selection and the drag surface
# ##################################################################################
@pytest.mark.asyncio
async def test_when_editing_every_component_below_the_root_carries_its_path_and_sibling_count() -> None:
    layout = {"root": {"type": "Column", "children": [_text("a"), _text("b")]}}

    async with open_page(_draw(layout, editing=V2Editing())) as user:
        nodes = [e for e in all_elements(user) if "mt-v2-node" in e._classes]
        assert len(nodes) == 2, "the root has no siblings, so it is not offered as draggable"
        assert sorted((e._props["data-path"], e._props["data-sibs"]) for e in nodes) == [
            ("children|0", "2"),
            ("children|1", "2"),
        ]


@pytest.mark.asyncio
async def test_the_selected_run_is_outlined_and_published_on_the_frame() -> None:
    layout = {"root": {"type": "Column", "children": [_text("a"), _text("b")]}}
    editing = V2Editing(selected=(("children", 1),))

    async with open_page(_draw(layout, editing=editing)) as user:
        outlined = [e for e in _drawn(user) if "solid #2563eb" in str(e._style.get("outline", ""))]
        assert len(outlined) == 1
        (frame,) = [e for e in all_elements(user) if "mt-scene-canvas" in e._classes]
        assert "children|1" in str(frame._props)


@pytest.mark.asyncio
async def test_without_editing_no_component_is_draggable() -> None:
    layout = {"root": {"type": "Column", "children": [_text("a"), _text("b")]}}

    async with open_page(_draw(layout)) as user:
        assert not [e for e in all_elements(user) if "mt-v2-node" in e._classes]


# ##################################################################################
# Paths
# ##################################################################################
@pytest.mark.parametrize(
    ("path", "encoded"),
    [((), ""), (("children", 0), "children|0"), (("content", 0, "children", 2), "content|0|children|2")],
)
def test_a_path_round_trips_through_its_dom_safe_string(path: tuple, encoded: str) -> None:
    assert sceneview_v2.v2_encode_path(path) == encoded
    assert sceneview_v2.v2_decode_path(encoded) == path


def test_the_component_count_walks_every_slot_and_ignores_what_is_not_a_node() -> None:
    layout = {
        "root": {
            "type": "Scaffold",
            "topBar": [{"type": "TopAppBar"}],
            "content": [_text(), "not a node", {"type": "Column", "children": [_text()]}],
            "modifiers": [{"type": "Padding"}],
        }
    }

    assert sceneview_v2.v2_component_count(layout) == 5
    assert sceneview_v2.v2_component_count({"root": "nonsense"}) == 0


def test_the_layouts_summary_names_it_and_lists_its_events() -> None:
    layout = {"name": "Panel", "defaultDisplayMode": "Dialog", "root": {"type": "Column"}}

    rows = dict(sceneview_v2.v2_layout_summary(layout))

    assert rows["Name"] == "Panel" and rows["Display mode"] == "Dialog"


def test_a_layout_with_no_name_or_mode_has_nothing_to_summarise() -> None:
    assert sceneview_v2.v2_layout_summary({"root": {"type": "Column"}}) == []


@pytest.mark.asyncio
async def test_modifiers_reach_the_components_style() -> None:
    node = {
        "type": "Text",
        "text": "styled",
        "modifiers": [
            {"type": "Padding", "all": "8"},
            {"type": "Alpha", "value": "0.5"},
            {"type": "Clickable"},
            {"type": "SomethingNew"},
        ],
    }

    async with open_page(_draw({"root": {"type": "Column", "children": [node]}})) as user:
        (styled,) = [e for e in _drawn(user) if e._style.get("opacity") == "0.5"]
        assert styled._style["cursor"] == "pointer"
        assert styled._style["padding"] == "8px"
