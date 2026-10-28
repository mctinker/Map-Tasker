"""The Legacy Scene designer (guiwins_designer_legacy): the list, the inspector, the toolbar and Undo.

What an edit does to a Scene's XML is test_sceneedit's, and what a canvas draws is sceneview's.  These mount the real
designer on a page of NiceGUI's in-process user simulation, over a three-element Scene, and use it as a person would:
pick rows, type into the geometry boxes, press Duplicate or Front or Delete, press Undo.  What is asserted is the designer's
own part -- that every edit lands in the one Scene copy the dialog will save, that every one can be undone by the one Undo,
that a refused edit says why and changes nothing, that a selection of several moves together while the property sheet
stays on one, and that the buttons which want exactly one element are off for any other number.
"""

from __future__ import annotations

import asyncio
import contextlib
import copy
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.core.sysconst import SCENE_TASK_TYPES
from maptasker.src.edit import sceneedit, sceneedit_legacy
from maptasker.src.gui import guiwins_designer_legacy, sceneview
from maptasker.src.gui.userintr import MyGui
from nicegui import core, events, ui
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

from tests.doubles import fake_window, required
from tests.nicegui_harness import all_elements
from tests.test_mapswap import _load

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from nicegui.testing.user import User

_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2"><name>Home</name><scenes>Panel</scenes></Project>
  <Task sr="task21"><id>21</id><nme>Helper</nme></Task>
  <Task sr="task22"><id>22</id><nme>Other</nme></Task>
  <Scene sr="scene0">
    <nme>Panel</nme>
    <widthPort>600</widthPort><heightPort>800</heightPort><widthLand>800</widthLand><heightLand>600</heightLand>
    <RectElement sr="elements0">
      <geom>0,0,600,800,0,0,800,600</geom><Str sr="arg0" ve="3">Back</Str>
    </RectElement>
    <ButtonElement sr="elements1">
      <geom>50,50,200,80,60,60,210,90</geom><Str sr="arg0" ve="3">Go</Str><Str sr="arg1" ve="3">Go!</Str>
      <clickTask>21</clickTask>
    </ButtonElement>
    <TextElement sr="elements2">
      <geom>50,200,300,60,70,70,300,60</geom><Str sr="arg0" ve="3">Label</Str><Str sr="arg1" ve="3">Hello</Str>
    </TextElement>
  </Scene>
</TaskerData>
"""

_built: dict = {}


@pytest.fixture(autouse=True)
def _configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Scene loaded for editing, and the designer captured when it is built."""
    _load(_XML)
    _built.clear()
    _built.update(edited=sceneedit.load_scene_for_edit("Panel", state=PrimeItems), designer=None, field_refs={})
    original = guiwins_designer_legacy._LegacyDesigner.__init__

    def capture(self: guiwins_designer_legacy._LegacyDesigner, *args: Any, **kwargs: Any) -> None:
        original(self, *args, **kwargs)
        _built["designer"] = self

    monkeypatch.setattr(guiwins_designer_legacy._LegacyDesigner, "__init__", capture)


def _gui() -> MyGui:
    return fake_window(state=PrimeItems, event_handlers=SimpleNamespace())


def _page() -> None:
    guiwins_designer_legacy._build_legacy_designer(_gui(), _built["edited"], _built["field_refs"])


@contextlib.asynccontextmanager
async def _open() -> AsyncIterator[User]:
    try:
        async with user_simulation(root=_page) as user:
            await user.open("/")
            yield user
    finally:
        if core.app.is_started:
            await core.app.stop()


def _click(user: User, element: ui.element) -> None:
    UserInteraction(user, {element}, None).click()


def _button(user: User, text: str) -> ui.button:
    found = [e for e in all_elements(user) if isinstance(e, ui.button) and e.text == text]
    assert found, f"no button {text!r}"
    return max(found, key=lambda e: e.id)


def _press(user: User, text: str) -> None:
    _click(user, _button(user, text))


def _texts(user: User) -> list[str]:
    return [e.text for e in all_elements(user) if isinstance(e, ui.label)]


def _scene() -> object:
    return _built["edited"].scene_element


def _order() -> list[str]:
    """The Scene's elements by name, bottom of the stack first."""
    return [sceneedit_legacy.legacy_element_label(e) for e in sceneview.paint_order(_scene())]


def _sr(label: str) -> str:
    return next(
        e.get("sr") for e in sceneview.paint_order(_scene()) if sceneedit_legacy.legacy_element_label(e) == label
    )


def _geom(label: str, *, landscape: bool = False) -> tuple:
    element = next(e for e in sceneview.paint_order(_scene()) if sceneedit_legacy.legacy_element_label(e) == label)
    return sceneview.element_geometry(element, landscape)


def _rows(user: User) -> list[ui.label]:
    """The element list's rows, top of the stack first (the order they are drawn)."""
    names = {sceneedit_legacy.legacy_element_label(e) for e in sceneview.paint_order(_scene())}
    found = [e for e in all_elements(user) if isinstance(e, ui.label) and e.text in names]
    return sorted((e for e in found if "cursor-pointer" in e.classes), key=lambda e: e.id)


def _row(user: User, label: str) -> ui.label:
    return next(row for row in _rows(user) if row.text == label)


def _number(user: User, label: str) -> ui.number:
    found = [e for e in all_elements(user) if isinstance(e, ui.number) and e.props.get("label") == label]
    return max(found, key=lambda e: e.id)


async def _select(user: User, *labels: str) -> None:
    _built["designer"].select(*(_sr(label) for label in labels))
    await asyncio.sleep(0.02)


# ##################################################################################
# Opening
# ##################################################################################
@pytest.mark.asyncio
async def test_the_header_counts_the_elements_and_the_list_has_a_row_each_top_of_stack_first() -> None:
    async with _open() as user:
        assert "Scene Elements (3)" in _texts(user)
        assert [row.text for row in _rows(user)] == ["Text 'Label'", "Button 'Go'", "Rect 'Back'"]


@pytest.mark.asyncio
async def test_nothing_is_selected_at_first_and_the_inspector_says_to_pick_one() -> None:
    async with _open() as user:
        assert _built["designer"].selection == {"sr": "", "srs": ()}
        assert "Select an element on the canvas or in the list." in _texts(user)
        for label in ("Front", "Forward", "Backward", "Back", "Duplicate", "Delete"):
            assert not _button(user, label).enabled, label
        assert not _button(user, "Undo").enabled


@pytest.mark.asyncio
async def test_the_edit_registers_what_the_preview_needs_to_be_a_second_surface() -> None:
    async with _open():
        assert set(_built["field_refs"]["legacy_edit"]) == {"handlers", "selection", "snap", "orientation", "rerender"}


@pytest.mark.asyncio
async def test_the_status_line_explains_the_canvas_then_the_group() -> None:
    async with _open() as user:
        assert any(text.startswith("Click an element to select it") for text in _texts(user))
        await _select(user, "Rect 'Back'", "Button 'Go'")
        assert "2 elements selected — drag or nudge any of them and they all move together." in _texts(user)


# ##################################################################################
# Selecting
# ##################################################################################
@pytest.mark.asyncio
async def test_clicking_a_row_selects_it_and_shows_its_properties() -> None:
    async with _open() as user:
        _click(user, _row(user, "Button 'Go'"))
        await asyncio.sleep(0.02)
        assert _built["designer"].selection["srs"] == (_sr("Button 'Go'"),)
        assert "bg-blue-600" in _row(user, "Button 'Go'").classes
        assert "Geometry" in _texts(user)
        assert _button(user, "Duplicate").enabled


def _row_click(designer: object, label: str, **modifiers: bool) -> None:
    designer.click_row(SimpleNamespace(args=modifiers), _sr(label))


@pytest.mark.asyncio
async def test_ctrl_click_toggles_and_shift_click_takes_the_range_about_a_fixed_anchor() -> None:
    async with _open():
        designer = _built["designer"]
        _row_click(designer, "Rect 'Back'")
        _row_click(designer, "Text 'Label'", ctrlKey=True)
        assert designer.selection["srs"] == (_sr("Rect 'Back'"), _sr("Text 'Label'"))
        assert designer.selection["sr"] == _sr("Text 'Label'"), "the last picked is the anchor"
        _row_click(designer, "Text 'Label'", metaKey=True)
        assert designer.selection["srs"] == (_sr("Rect 'Back'"),)

        _row_click(designer, "Button 'Go'")
        _row_click(designer, "Text 'Label'", shiftKey=True)
        assert set(designer.selection["srs"]) == {_sr("Button 'Go'"), _sr("Text 'Label'")}
        assert designer.selection["sr"] == _sr("Button 'Go'"), "the anchor stays where the range started"
        _row_click(designer, "Rect 'Back'", shiftKey=True)
        assert set(designer.selection["srs"]) == {_sr("Button 'Go'"), _sr("Rect 'Back'")}


@pytest.mark.asyncio
async def test_shift_click_with_no_anchor_is_an_ordinary_click() -> None:
    async with _open():
        designer = _built["designer"]
        _row_click(designer, "Button 'Go'", shiftKey=True)
        assert designer.selection["srs"] == (_sr("Button 'Go'"),)


@pytest.mark.asyncio
async def test_a_selection_of_several_names_the_others_and_keeps_the_sheet_on_one() -> None:
    async with _open() as user:
        await _select(user, "Rect 'Back'", "Button 'Go'")
        assert "editing 1 of 2 selected" in _texts(user)
        assert "Also selected:" in _texts(user)
        also = next(
            e
            for e in all_elements(user)
            if isinstance(e, ui.label) and e.text == "Rect 'Back'" and "underline" in e.classes
        )
        _click(user, also)
        assert _built["designer"].selection["sr"] == _sr("Rect 'Back'")
        assert set(_built["designer"].selection["srs"]) == {_sr("Rect 'Back'"), _sr("Button 'Go'")}
        assert "Select a single element to duplicate, delete or restack it." in _texts(user)
        for label in ("Front", "Duplicate", "Delete"):
            assert not _button(user, label).enabled, label


@pytest.mark.asyncio
async def test_a_click_on_the_canvas_selects_shift_extends_and_the_background_clears() -> None:
    async with _open():
        designer = _built["designer"]
        designer.select_from_canvas({"sr": _sr("Button 'Go'")})
        assert designer.selection["srs"] == (_sr("Button 'Go'"),)
        designer.select_from_canvas({"sr": _sr("Text 'Label'"), "extend": True})
        assert len(designer.selection["srs"]) == 2
        designer.select_from_canvas({"sr": _sr("Text 'Label'"), "extend": True})
        assert designer.selection["srs"] == (_sr("Button 'Go'"),)
        designer.select_from_canvas({"sr": ""})
        assert designer.selection["srs"] == ()


@pytest.mark.asyncio
async def test_a_rubber_band_takes_what_it_caught_and_ignores_what_is_not_there() -> None:
    async with _open():
        designer = _built["designer"]
        designer.select_from_canvas({"srs": [_sr("Button 'Go'"), _sr("Text 'Label'"), "elements99"]})
        assert set(designer.selection["srs"]) == {_sr("Button 'Go'"), _sr("Text 'Label'")}
        designer.select_from_canvas({"srs": [_sr("Rect 'Back'")], "extend": True})
        assert len(designer.selection["srs"]) == 3
        designer.select_from_canvas({"srs": []})
        assert designer.selection["srs"] == ()


# ##################################################################################
# Structure, and the one Undo
# ##################################################################################
@pytest.mark.asyncio
async def test_duplicate_adds_a_copy_and_selects_it() -> None:
    async with _open() as user:
        await _select(user, "Button 'Go'")
        _press(user, "Duplicate")
        assert len(_order()) == 4
        assert _built["designer"].selection["sr"] == _built["designer"].selection["srs"][0]
        assert "Scene Elements (4)" in _texts(user)


@pytest.mark.asyncio
async def test_front_and_back_walk_an_element_through_the_stack() -> None:
    async with _open() as user:
        await _select(user, "Button 'Go'")
        _press(user, "Front")
        assert _order() == ["Rect 'Back'", "Text 'Label'", "Button 'Go'"]
        assert _built["designer"].selection["sr"] == _sr("Button 'Go'"), "re-selected by the renumbered sr"
        _press(user, "Back")
        assert _order() == ["Button 'Go'", "Rect 'Back'", "Text 'Label'"]
        _press(user, "Forward")
        assert _order()[1] == "Button 'Go'"
        _press(user, "Backward")
        assert _order()[0] == "Button 'Go'"


@pytest.mark.asyncio
async def test_restacking_past_the_end_says_so_and_changes_nothing() -> None:
    async with _open() as user:
        await _select(user, "Text 'Label'")
        before = copy.deepcopy(_order())
        _press(user, "Forward")
        assert user.notify.contains("Already at the front.")
        assert _order() == before
        assert not _built["designer"].history


@pytest.mark.asyncio
async def test_delete_removes_the_selection_and_undo_brings_it_back() -> None:
    async with _open() as user:
        before = _order()
        await _select(user, "Button 'Go'")
        _press(user, "Delete")
        assert _order() == ["Rect 'Back'", "Text 'Label'"]
        # The model hands back the element that closes the gap, and that is what ends up selected.
        (neighbour,) = _built["designer"].selection["srs"]
        assert (
            sceneedit_legacy.legacy_element_label(required(sceneedit_legacy.legacy_element_at(_scene(), neighbour)))
            != "Button 'Go'"
        )
        _press(user, "Undo")
        assert _order() == before


@pytest.mark.asyncio
async def test_delete_warns_about_the_tasks_that_address_the_element_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sceneedit_legacy, "find_element_name_references", lambda *_a, **_k: ["Helper"])
    monkeypatch.setattr(sceneedit_legacy, "find_element_match_references", lambda *_a, **_k: ["Other"])
    async with _open() as user:
        await _select(user, "Button 'Go'")
        _press(user, "Delete")
        assert user.notify.contains("Task(s) address 'Go' by name: Helper")
        assert user.notify.contains("match pattern")
        assert _order() == ["Rect 'Back'", "Text 'Label'"], "warned, not blocked"


@pytest.mark.asyncio
async def test_undo_works_back_through_several_edits_and_switches_off_at_the_start() -> None:
    async with _open() as user:
        original = _order()
        await _select(user, "Button 'Go'")
        _press(user, "Duplicate")
        _press(user, "Front")
        _press(user, "Undo")
        _press(user, "Undo")
        assert _order() == original
        assert not _button(user, "Undo").enabled


@pytest.mark.asyncio
async def test_undo_drops_a_selection_that_the_restore_removed() -> None:
    async with _open() as user:
        await _select(user, "Button 'Go'")
        _press(user, "Duplicate")
        assert _built["designer"].selection["srs"]
        _press(user, "Undo")
        assert all(
            sceneedit_legacy.legacy_element_at(_scene(), sr) is not None for sr in _built["designer"].selection["srs"]
        )


# ##################################################################################
# Geometry
# ##################################################################################
@pytest.mark.asyncio
async def test_the_geometry_boxes_show_the_box_and_typing_moves_the_element() -> None:
    async with _open() as user:
        await _select(user, "Button 'Go'")
        assert [_number(user, name).value for name in ("X", "Y", "Width", "Height")] == [50, 50, 200, 80]
        _number(user, "Width").value = 240
        assert _geom("Button 'Go'") == (50, 50, 240, 80)
        assert _built["designer"].history, "a typed edit is one undo step"


@pytest.mark.asyncio
async def test_typing_the_value_the_box_already_has_changes_nothing() -> None:
    async with _open() as user:
        await _select(user, "Button 'Go'")
        _number(user, "X").value = 50
        assert not _built["designer"].history


@pytest.mark.asyncio
async def test_a_drag_reports_each_moved_box_once_and_selects_what_moved() -> None:
    async with _open():
        designer = _built["designer"]
        designer.set_geometry(
            {
                "moves": [
                    {"sr": _sr("Button 'Go'"), "x": 10, "y": 20, "w": 200, "h": 80},
                    {"sr": _sr("Text 'Label'"), "x": 15, "y": 25, "w": 300, "h": 60},
                ],
            },
        )
        assert _geom("Button 'Go'") == (10, 20, 200, 80)
        assert _geom("Text 'Label'") == (15, 25, 300, 60)
        assert len(designer.history) == 1, "one gesture, one undo step"
        assert set(designer.selection["srs"]) == {_sr("Button 'Go'"), _sr("Text 'Label'")}


@pytest.mark.asyncio
async def test_a_drag_naming_nothing_this_scene_has_leaves_no_trace() -> None:
    async with _open():
        designer = _built["designer"]
        designer.set_geometry({"moves": [{"sr": "elements99", "x": 1, "y": 1, "w": 5, "h": 5}, {"sr": "x", "x": "?"}]})
        designer.set_geometry({})
        assert not designer.history


@pytest.mark.asyncio
async def test_the_arrow_keys_nudge_everything_selected_by_the_same_amount() -> None:
    async with _open() as user:
        await _select(user, "Button 'Go'", "Text 'Label'")
        _built["designer"].nudge({"dx": 10, "dy": -5})
        assert _geom("Button 'Go'") == (60, 45, 200, 80)
        assert _geom("Text 'Label'") == (60, 195, 300, 60)
        assert len(_built["designer"].history) == 1

        _built["designer"].select()
        _built["designer"].nudge({"dx": 1})
        assert len(_built["designer"].history) == 1, "nothing selected, nothing moved"


@pytest.mark.asyncio
async def test_landscape_edits_the_other_half_of_the_geometry() -> None:
    async with _open() as user:
        await _select(user, "Button 'Go'")
        switch = next(e for e in all_elements(user) if isinstance(e, ui.switch))
        assert switch.enabled
        switch.value = True
        assert _built["designer"].orientation["landscape"] is True
        assert [_number(user, name).value for name in ("X", "Y", "Width", "Height")] == [60, 60, 210, 90]
        _number(user, "X").value = 99
        assert _geom("Button 'Go'", landscape=True) == (99, 60, 210, 90)
        assert _geom("Button 'Go'", landscape=False) == (50, 50, 200, 80), "the portrait half is untouched"


@pytest.mark.asyncio
async def test_a_scene_with_no_landscape_layout_cannot_be_switched_to_it() -> None:
    _scene_element = _built["edited"].scene_element
    _scene_element.find("widthLand").text = "-1"
    _scene_element.find("heightLand").text = "-1"
    async with _open() as user:
        switch = next(e for e in all_elements(user) if isinstance(e, ui.switch))
        assert not switch.enabled


@pytest.mark.asyncio
async def test_the_snap_grid_is_chosen_from_a_short_list_and_kept() -> None:
    async with _open() as user:
        snap = next(e for e in all_elements(user) if isinstance(e, ui.select) and e.props.get("label") == "Snap")
        snap.value = 10
        assert _built["designer"].snap["grid"] == 10
        snap = next(e for e in all_elements(user) if isinstance(e, ui.select) and e.props.get("label") == "Snap")
        assert snap.value == 10, "the rebuild keeps the choice"


@pytest.mark.asyncio
async def test_an_element_with_no_layout_in_this_orientation_says_so() -> None:
    element = next(
        e for e in sceneview.paint_order(_scene()) if sceneedit_legacy.legacy_element_label(e) == "Text 'Label'"
    )
    element.find("geom").text = "50,200,300,60,-1,-1,-1,-1"
    async with _open() as user:
        _built["designer"].orientation["landscape"] = True
        await _select(user, "Text 'Label'")
        assert "This element has no layout for this orientation." in _texts(user)


# ##################################################################################
# Adding
# ##################################################################################
@pytest.mark.asyncio
async def test_add_offers_every_element_and_adding_one_puts_it_on_top_and_selects_it() -> None:
    async with _open() as user:
        _press(user, "Add")
        assert "Add Element" in _texts(user)
        _press(user, "Rectangle")
        await asyncio.sleep(0.05)
        assert len(_order()) == 4
        assert _order()[-1].startswith("Rect")
        assert _built["designer"].selection["sr"] == sceneview.paint_order(_scene())[-1].get("sr")
        # Centred, and no bigger than the canvas: 300 x 120 in a 600 x 800 portrait Scene.
        assert _geom(_order()[-1]) == (150, 340, 300, 120)


@pytest.mark.asyncio
async def test_a_blocked_element_says_why_instead_of_being_added(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sceneedit_legacy,
        "legacy_can_add",
        lambda element_type: "No argument table." if element_type == "OvalElement" else "",
    )
    async with _open() as user:
        _press(user, "Add")
        _press(user, "Oval")
        assert user.notify.contains("No argument table.")
        assert len(_order()) == 3


@pytest.mark.asyncio
async def test_the_add_sheet_filters_as_you_type_and_enter_picks_the_only_match() -> None:
    async with _open() as user:
        _press(user, "Add")
        search = next(
            e for e in all_elements(user) if isinstance(e, ui.input) and e.props.get("placeholder") == "Search elements"
        )
        search.value = "zzzzzz"
        assert "No element matches that." in _texts(user)
        search.value = "SceneElement"  # the XML tag still finds it
        chips = [e for e in all_elements(user) if isinstance(e, ui.button) and e.props.get("rounded") is not None]
        assert len(chips) == 1
        search.value = "oval"
        events_before = len(_order())
        for listener in list(search._event_listeners.values()):
            if listener.type == "keydown.enter":
                events.handle_event(
                    listener.handler, events.GenericEventArguments(sender=search, client=search.client, args=None)
                )
        await asyncio.sleep(0.05)
        assert len(_order()) == events_before + 1


@pytest.mark.asyncio
async def test_adding_to_an_orientation_with_no_layout_says_so() -> None:
    _scene().find("widthPort").text = "-1"
    async with _open() as user:
        _press(user, "Add")
        _press(user, "Rectangle")
        assert user.notify.contains("This Scene has no layout for this orientation.")
        assert len(_order()) == 3


# ##################################################################################
# The canvas
# ##################################################################################
@pytest.mark.asyncio
async def test_an_orientation_with_no_size_draws_a_note_instead_of_a_canvas() -> None:
    _scene().find("widthLand").text = "-1"
    _scene().find("heightLand").text = "-1"
    async with _open() as user:
        _built["designer"].set_orientation(True)
        assert any("has no landscape layout" in text for text in _texts(user))


@pytest.mark.asyncio
async def test_the_canvas_size_is_what_the_dialogs_fields_say_and_a_bad_one_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fields = {"widthPort": SimpleNamespace(value="300"), "heightPort": SimpleNamespace(value="500")}
    assert guiwins_designer_legacy._legacy_canvas_size(_built["edited"], fields, landscape=False) == (300, 500)
    assert guiwins_designer_legacy._legacy_canvas_size(_built["edited"], {}, landscape=False) == (600, 800)
    assert (
        guiwins_designer_legacy._legacy_canvas_size(
            _built["edited"],
            {"widthPort": SimpleNamespace(value="0"), "heightPort": SimpleNamespace(value="9")},
            landscape=False,
        )
        is None
    )

    async with _open() as user:
        bad = {"widthPort": SimpleNamespace(value="wide"), "heightPort": SimpleNamespace(value="500")}
        with required(user.client):
            assert guiwins_designer_legacy._legacy_canvas_size(_built["edited"], bad, landscape=False) == (600, 800)
        assert user.notify.contains("is not a whole number")


# ##################################################################################
# Renaming
# ##################################################################################
def _rename_button(user: User) -> ui.button:
    """The Rename beside the Name field: the first Rename drawn (the dialog's own comes later)."""
    found = [e for e in all_elements(user) if isinstance(e, ui.button) and e.text == "Rename"]
    return min(found, key=lambda e: e.id)


@pytest.mark.asyncio
async def test_rename_opens_a_dialog_that_says_nothing_addresses_the_element_by_name() -> None:
    async with _open() as user:
        await _select(user, "Button 'Go'")
        _click(user, _rename_button(user))
        assert "Rename Element: Go" in _texts(user)
        assert "No Task addresses this element by name." in _texts(user)


@pytest.mark.asyncio
async def test_renaming_changes_the_element_and_is_one_undo_step() -> None:
    async with _open() as user:
        await _select(user, "Button 'Go'")
        _click(user, _rename_button(user))
        name = next(e for e in all_elements(user) if isinstance(e, ui.input) and e.props.get("label") == "New name")
        name.value = "Launch"
        _click(user, _button(user, "Rename"))
        await asyncio.sleep(0.05)
        assert "Button 'Launch'" in _order()
        assert _built["edited"].element_renames == [], "no Task needed bringing along"
        _press(user, "Undo")
        assert "Button 'Go'" in _order()


@pytest.mark.asyncio
async def test_a_rename_that_tasks_depend_on_offers_to_bring_them_along_and_records_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sceneedit_legacy, "find_element_name_actions", lambda *_a, **_k: [("Helper", "arg0"), ("Other", "arg1")]
    )
    monkeypatch.setattr(
        sceneedit_legacy, "find_element_name_references", lambda *_a, **_k: ["Helper", "Other", "Loose"]
    )
    monkeypatch.setattr(sceneedit_legacy, "find_element_match_references", lambda *_a, **_k: ["Pattern"])
    async with _open() as user:
        await _select(user, "Button 'Go'")
        _click(user, _rename_button(user))
        texts = _texts(user)
        assert "Helper, Other" in texts
        assert any(text.startswith("Not updated") and "Loose" in text for text in texts)
        assert any(text.startswith("Never updated") and "Pattern" in text for text in texts)
        name = next(e for e in all_elements(user) if isinstance(e, ui.input) and e.props.get("label") == "New name")
        name.value = "Launch"
        _click(user, _button(user, "Rename"))
        await asyncio.sleep(0.05)
        assert _built["edited"].element_renames == [("Go", "Launch")]
        assert user.notify.contains("will be updated when this Scene is saved")


@pytest.mark.asyncio
async def test_unticking_the_task_update_renames_without_recording_a_sweep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sceneedit_legacy, "find_element_name_actions", lambda *_a, **_k: [("Helper", "arg0")])
    async with _open() as user:
        await _select(user, "Button 'Go'")
        _click(user, _rename_button(user))
        box = next(e for e in all_elements(user) if isinstance(e, ui.checkbox))
        box.value = False
        name = next(e for e in all_elements(user) if isinstance(e, ui.input) and e.props.get("label") == "New name")
        name.value = "Launch"
        _click(user, _button(user, "Rename"))
        await asyncio.sleep(0.05)
        assert "Button 'Launch'" in _order()
        assert _built["edited"].element_renames == []


@pytest.mark.asyncio
async def test_a_name_the_model_refuses_is_reported_and_leaves_the_element_alone() -> None:
    async with _open() as user:
        await _select(user, "Button 'Go'")
        _click(user, _rename_button(user))
        name = next(e for e in all_elements(user) if isinstance(e, ui.input) and e.props.get("label") == "New name")
        name.value = "Label"  # another element's name
        before = _order()
        _click(user, _button(user, "Rename"))
        await asyncio.sleep(0.05)
        assert _order() == before
        assert not _built["designer"].history


# ##################################################################################
# What an element does: Tasks
# ##################################################################################
def _task_expansion(user: User) -> ui.expansion:
    return next(
        e
        for e in all_elements(user)
        if isinstance(e, ui.expansion) and str(e.props.get("label", "")).startswith("Tasks")
    )


def _task_selects(user: User) -> list[ui.select]:
    return sorted(
        (e for e in all_elements(user) if isinstance(e, ui.select) and "Helper" in getattr(e, "options", {})),
        key=lambda e: e.id,
    )


@pytest.mark.asyncio
async def test_an_elements_tasks_are_listed_with_the_one_it_fires() -> None:
    async with _open() as user:
        await _select(user, "Button 'Go'")
        assert _task_expansion(user).props["label"] == "Tasks (1)"
        (picker,) = _task_selects(user)
        assert picker.value == "Helper"


@pytest.mark.asyncio
async def test_pointing_an_event_at_another_task_rewrites_the_binding_and_can_be_undone() -> None:
    async with _open() as user:
        await _select(user, "Button 'Go'")
        element = sceneedit_legacy.legacy_element_at(_scene(), _sr("Button 'Go'"))
        _task_selects(user)[0].value = "Other"
        assert required(element).findtext("clickTask") == "22"
        assert _built["designer"].expanded["tasks"] is True
        _press(user, "Undo")
        assert required(sceneedit_legacy.legacy_element_at(_scene(), _sr("Button 'Go'"))).findtext("clickTask") == "21"


@pytest.mark.asyncio
async def test_the_close_button_stops_the_event_firing_anything() -> None:
    async with _open() as user:
        await _select(user, "Button 'Go'")
        element = sceneedit_legacy.legacy_element_at(_scene(), _sr("Button 'Go'"))
        close = next(e for e in all_elements(user) if isinstance(e, ui.button) and e.props.get("icon") == "close")
        _click(user, close)
        assert required(element).find("clickTask") is None


@pytest.mark.asyncio
async def test_an_event_added_for_a_task_not_yet_chosen_writes_nothing_until_one_is() -> None:
    async with _open() as user:
        await _select(user, "Button 'Go'")
        designer = _built["designer"]
        element = sceneedit_legacy.legacy_element_at(_scene(), _sr("Button 'Go'"))
        designer.open_pending("longclickTask")
        assert required(element).find("longclickTask") is None, "a half-made binding is not something Tasker writes"
        assert "longclickTask" in designer.pending_events["tags"]
        pick = next(e for e in all_elements(user) if isinstance(e, ui.select) and e.props.get("label") == "Pick a Task")
        pick.value = "Other"
        assert required(element).findtext("longclickTask") == "22"
        assert "longclickTask" not in designer.pending_events["tags"]


@pytest.mark.asyncio
async def test_a_pending_event_can_be_discarded_and_belongs_only_to_the_element_it_was_opened_on() -> None:
    async with _open() as user:
        await _select(user, "Button 'Go'")
        designer = _built["designer"]
        designer.open_pending("longclickTask")
        designer.discard_pending("longclickTask")
        assert designer.pending_events["tags"] == set()
        designer.open_pending("longclickTask")
        await _select(user, "Text 'Label'")
        assert designer.pending_events["tags"] == set()


@pytest.mark.asyncio
async def test_the_add_event_menu_lists_only_the_events_not_yet_used() -> None:
    async with _open() as user:
        await _select(user, "Button 'Go'")
        entries = [
            e.default_slot.children[0].text
            for e in all_elements(user)
            if isinstance(e, ui.menu_item) and e.default_slot.children
        ]
        assert SCENE_TASK_TYPES["longclickTask"] in entries
        assert SCENE_TASK_TYPES["clickTask"] not in entries, "that event already fires a Task"


@pytest.mark.asyncio
async def test_a_task_that_is_not_in_the_backup_is_refused() -> None:
    async with _open() as user:
        await _select(user, "Button 'Go'")
        with required(user.client):
            _built["designer"].set_binding("clickTask", "No Such Task")
        assert user.notify.contains("No Task named 'No Such Task' in this backup.")


@pytest.mark.asyncio
async def test_an_anonymous_task_is_shown_and_cannot_be_repointed() -> None:
    element = sceneedit_legacy.legacy_element_at(_scene(), _sr("Button 'Go'"))
    required(required(element).find("clickTask")).text = "-3"
    async with _open() as user:
        await _select(user, "Button 'Go'")
        readonly = [e for e in all_elements(user) if isinstance(e, ui.input) and "readonly" in e.props]
        assert readonly


# ##################################################################################
# Background, and the Scene's own properties
# ##################################################################################
@pytest.mark.asyncio
async def test_an_element_that_can_have_a_background_offers_one_to_add_and_to_remove() -> None:
    async with _open() as user:
        await _select(user, "Text 'Label'")
        element = sceneedit_legacy.legacy_element_at(_scene(), _sr("Text 'Label'"))
        assert sceneedit_legacy.legacy_background(required(element)) is None
        assert any(
            str(e.props.get("label", "")) == "Background (none)"
            for e in all_elements(user)
            if isinstance(e, ui.expansion)
        )

        _press(user, "Add a background")
        assert sceneedit_legacy.legacy_background(required(element)) is not None
        assert _built["designer"].expanded["background"] is True

        _press(user, "Remove background")
        assert sceneedit_legacy.legacy_background(required(element)) is None
        _press(user, "Undo")
        # Undo restores the Scene from its snapshot, so the element is looked up afresh.
        restored = sceneedit_legacy.legacy_element_at(_scene(), _sr("Text 'Label'"))
        assert sceneedit_legacy.legacy_background(required(restored)) is not None


@pytest.mark.asyncio
async def test_an_element_that_draws_its_own_fill_is_offered_no_background() -> None:
    async with _open() as user:
        await _select(user, "Button 'Go'")
        assert not any(
            str(e.props.get("label", "")).startswith("Background")
            for e in all_elements(user)
            if isinstance(e, ui.expansion)
        )


@pytest.mark.asyncio
async def test_the_scene_properties_panel_points_at_the_form_it_does_not_repeat() -> None:
    async with _open() as user:
        assert any(
            str(e.props.get("label", "")) == "Scene Properties (none)"
            for e in all_elements(user)
            if isinstance(e, ui.expansion)
        )
        assert any(text.startswith("This Scene has no properties element.") for text in _texts(user))
        assert _button(user, "Add scene properties")


@pytest.mark.asyncio
async def test_opening_the_scene_properties_form_rebuilds_the_panel_when_it_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list = []
    monkeypatch.setattr(
        guiwins_designer_legacy,
        "_build_scene_properties_dialog",
        lambda gui, edited, refs, on_closed=None: opened.append(on_closed),
    )
    async with _open() as user:
        _press(user, "Add scene properties")
        assert opened == [_built["designer"].render]


# ##################################################################################
# Mounting it in a Scene dialog
# ##################################################################################
def _mount_page() -> None:
    guiwins_designer_legacy.LegacyDesigner().build_body(
        _gui(), _built["edited"], _built["field_refs"], None, PrimeItems
    )


@contextlib.asynccontextmanager
async def _open_mounted() -> AsyncIterator[User]:
    try:
        async with user_simulation(root=_mount_page) as user:
            await user.open("/")
            yield user
    finally:
        if core.app.is_started:
            await core.app.stop()


@pytest.mark.asyncio
async def test_a_scene_dialog_mounts_the_size_fields_the_properties_button_and_the_designer() -> None:
    async with _open_mounted() as user:
        fields = _built["field_refs"]
        assert {key for key, _label in sceneedit.SCENE_DIMENSION_FIELDS} <= set(fields)
        assert fields["widthPort"].value == "600"
        assert "-1 means this orientation has no layout of its own." in _texts(user)
        assert any(isinstance(e, ui.button) and e.text.endswith("Properties") for e in all_elements(user))
        assert "Scene Elements (3)" in _texts(user)


@pytest.mark.asyncio
async def test_the_dialogs_size_fields_decide_how_big_the_designer_draws() -> None:
    async with _open_mounted():
        _built["field_refs"]["widthPort"].value = "300"
        _built["field_refs"]["heightPort"].value = "400"
        assert guiwins_designer_legacy._legacy_canvas_size(_built["edited"], _built["field_refs"], landscape=False) == (
            300,
            400,
        )


# ##################################################################################
# A List's row layout
# ##################################################################################
_LIST = """<ListElement sr="elements3">
  <geom>10,300,300,200,-1,-1,-1,-1</geom><Str sr="arg0" ve="3">Items</Str>
  <Scene sr="arg4"><Scene sr="val"><nme>row</nme>
    <widthPort>300</widthPort><heightPort>50</heightPort><widthLand>-1</widthLand><heightLand>-1</heightLand>
    <TextElement sr="elements0"><geom>0,0,100,40,-1,-1,-1,-1</geom><Str sr="arg0" ve="3">Cell</Str></TextElement>
  </Scene></Scene>
</ListElement>"""


def _with_list() -> None:
    import xml.etree.ElementTree as ET

    _scene().append(ET.fromstring(_LIST))


@pytest.mark.asyncio
async def test_a_list_names_its_row_layout_and_how_many_elements_it_has() -> None:
    _with_list()
    async with _open() as user:
        await _select(user, "List 'Items'")
        assert any(text.startswith("Item layout:") and "(1 element(s))" in text for text in _texts(user))


@pytest.mark.asyncio
async def test_edit_item_layout_opens_a_designer_of_its_own_over_the_same_copy() -> None:
    _with_list()
    async with _open() as user:
        await _select(user, "List 'Items'")
        _press(user, "Edit item layout")
        assert any(text.startswith("Item layout:") for text in _texts(user))
        assert "Done" in {e.text for e in all_elements(user) if isinstance(e, ui.button)}
        # Two designers are mounted at once: the outer one and the row's.
        assert (
            len([e for e in all_elements(user) if isinstance(e, ui.label) and e.text.startswith("Scene Elements")]) == 2
        )


@pytest.mark.asyncio
async def test_the_item_layouts_size_is_written_through_when_valid_and_refused_when_not() -> None:
    _with_list()
    async with _open() as user:
        await _select(user, "List 'Items'")
        _press(user, "Edit item layout")
        holder = sceneedit_legacy.legacy_element_at(_scene(), _sr("List 'Items'"))
        layout = sceneedit_legacy.legacy_item_layout(required(holder))
        fields = {
            e.props.get("label"): e
            for e in all_elements(user)
            if isinstance(e, ui.input) and e.props.get("label") in ("Width (portrait)", "Height (portrait)")
        }
        assert fields, "the row's own size boxes"
        width = fields["Width (portrait)"]
        width.value = "320"
        _blur(width)
        assert required(layout).findtext("widthPort") == "320"

        width.value = "wide"
        _blur(width)
        assert user.notify.contains("Size must be a whole number")
        assert width.value == "320"


def _blur(widget: ui.input) -> None:
    for listener in list(widget._event_listeners.values()):
        if listener.type == "blur":
            events.handle_event(
                listener.handler, events.GenericEventArguments(sender=widget, client=widget.client, args=None)
            )


@pytest.mark.asyncio
async def test_a_holder_without_a_row_layout_opens_nothing() -> None:
    async with _open() as user:
        element = sceneedit_legacy.legacy_element_at(_scene(), _sr("Button 'Go'"))
        with required(user.client):
            guiwins_designer_legacy._build_item_layout_dialog(_gui(), required(element), lambda: None)
        assert not any(e.text == "Done" for e in all_elements(user) if isinstance(e, ui.button))


@pytest.mark.asyncio
async def test_a_list_and_a_spinner_are_drawn_on_the_canvas_not_dropped_with_an_error() -> None:
    """Both draw a whole Scene inside themselves, which needs the run's state -- once not passed to them."""
    import xml.etree.ElementTree as ET

    _with_list()
    spinner = (
        _LIST.replace("ListElement", "SpinnerElement")
        .replace('sr="elements3"', 'sr="elements4"')
        .replace('sr="arg4"', 'sr="arg3"')
    )
    _scene().append(ET.fromstring(spinner))
    async with _open() as user:
        assert "Scene Elements (5)" in _texts(user)
        assert not any("Traceback" in text for text in _texts(user))
