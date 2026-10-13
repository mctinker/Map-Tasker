"""The Scene preview and the Tree view (guiwins_views), and how the Edit Scene dialog hands the screen to a preview.

The drawing itself is sceneview's.  What is here is the frame round it, built on a page of NiceGUI's in-process user simulation:
the toolbar a Legacy Scene gets and the different one a Version 2 Scene gets, what each control changes, the caption that says
what the picture cannot be trusted for, the way a drag in the picture is handed to the designer behind it rather than made
here, and the way back to the dialog with everything still typed into it.  And the hand-off itself -- the Edit Scene dialog
steps aside for a preview and is only ever handed back to the one that stepped aside -- which is plain bookkeeping on the window.
"""

from __future__ import annotations

import contextlib
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from nicegui import core, events, ui
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

from maptasker.src.core import scenelayout
from maptasker.src.edit import sceneedit, scenemodel
from maptasker.src.gui import guiwins_views, sceneview
from maptasker.src.gui.guiwins_views import NiceGuiSceneView, NiceGuiTreeView
from maptasker.src.core.primitem import PrimeItems
from tests.test_mapswap import _load

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from nicegui.testing.user import User

_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2"><name>Home</name><scenes>Panel</scenes></Project>
  <Task sr="task21"><id>21</id><nme>Helper</nme></Task>
  <Scene sr="scene0">
    <nme>Panel</nme>
    <widthPort>600</widthPort><heightPort>800</heightPort><widthLand>800</widthLand><heightLand>600</heightLand>
    <RectElement sr="elements0"><geom>0,0,600,800,0,0,800,600</geom><Str sr="arg0" ve="3">Back</Str></RectElement>
    <ButtonElement sr="elements1">
      <geom>50,50,200,80,60,60,210,90</geom><Str sr="arg0" ve="3">Go</Str><Str sr="arg1" ve="3">Go!</Str>
      <clickTask>21</clickTask>
    </ButtonElement>
  </Scene>
</TaskerData>
"""

_built: dict = {}


@pytest.fixture(autouse=True)
def _configuration() -> None:
    _load(_XML)
    _built.clear()
    _built.update(view=None, gui=None, dialog=None, field_refs={}, scene="Panel", version="legacy")


def _edited() -> sceneedit.EditableScene:
    if _built["version"] == "v2":
        return sceneedit.create_new_scene("Fresh", scenemodel.SCENE_VERSION_V2, state=PrimeItems)
    return sceneedit.load_scene_for_edit(_built["scene"], state=PrimeItems)


def _page() -> None:
    gui = SimpleNamespace(font="Courier New", dark_mode=False, state=PrimeItems)
    gui.content_container = ui.column()
    _built["gui"] = gui
    with gui.content_container:
        _built["dialog"] = ui.dialog()
    _built["edited"] = _edited()
    if _built["version"] == "v2" and "v2_layout" not in _built["field_refs"]:
        _built["field_refs"]["v2_layout"] = scenelayout.decode_v2_layout(_built["edited"].scene_element)
    _built["view"] = NiceGuiSceneView(gui, _built["edited"], _built["field_refs"], _built["dialog"])


@contextlib.asynccontextmanager
async def _open(page: Callable[[], None] = _page) -> AsyncIterator[User]:
    try:
        async with user_simulation(root=page) as user:
            await user.open("/")
            yield user
    finally:
        if core.app.is_started:
            await core.app.stop()


def _click(user: User, element: ui.element) -> None:
    UserInteraction(user, {element}, None).click()


def _all(user: User, kind: type) -> list:
    return sorted((e for e in user.client.elements.values() if isinstance(e, kind)), key=lambda e: e.id)


def _button(user: User, text: str) -> ui.button:
    found = [e for e in _all(user, ui.button) if e.text == text]
    assert found, f"no button {text!r}"
    return found[0]


def _select(user: User, label: str) -> ui.select:
    found = [e for e in _all(user, ui.select) if e.props.get("label") == label]
    assert found, f"no select {label!r}"
    return found[0]


def _switch(user: User, text: str) -> ui.switch:
    found = [e for e in _all(user, ui.switch) if e.text == text]
    assert found, f"no switch {text!r}"
    return found[0]


def _texts(user: User) -> list[str]:
    return [e.text for e in _all(user, ui.label)]


def _editor_for_legacy(calls: list) -> dict:
    return {
        "handlers": {name: (lambda payload, n=name: calls.append((n, payload))) for name in ("select", "geometry", "nudge")},
        "selection": {"sr": "elements1", "srs": ("elements1",)},
        "snap": {"grid": 5},
        "orientation": {"landscape": False},
        "rerender": lambda: calls.append(("rerender", None)),
    }


# ##################################################################################
# The Edit Scene dialog handing the screen to a preview
# ##################################################################################
def _window() -> SimpleNamespace:
    return SimpleNamespace(scene_editor_session={"dialog": "D", "name": "Panel", "suspended": False})


def test_previewing_marks_the_session_suspended_but_only_for_the_dialog_that_stepped_aside() -> None:
    gui = _window()
    guiwins_views.suspend_scene_editor_session(gui, "OTHER")
    assert gui.scene_editor_session["suspended"] is False
    guiwins_views.suspend_scene_editor_session(gui, "D")
    assert gui.scene_editor_session["suspended"] is True
    guiwins_views.suspend_scene_editor_session(SimpleNamespace(), "D")  # a window with no session: nothing to mark


def test_a_suspended_editor_is_handed_back_once_and_only_for_its_own_scene() -> None:
    gui = _window()
    assert guiwins_views.suspended_scene_editor(gui, "Panel") is None, "nothing is suspended yet"
    guiwins_views.suspend_scene_editor_session(gui, "D")
    assert guiwins_views.suspended_scene_editor(gui, "Other") is None
    assert guiwins_views.suspended_scene_editor(gui, "Panel") == "D"
    assert guiwins_views.suspended_scene_editor(gui, "Panel") is None, "marked resumed, so not handed back twice"
    assert guiwins_views.suspended_scene_editor(SimpleNamespace(), "Panel") is None


def test_going_back_to_the_editor_clears_the_mark() -> None:
    gui = _window()
    guiwins_views.suspend_scene_editor_session(gui, "D")
    guiwins_views._resume_scene_editor_session(gui, "D")
    assert gui.scene_editor_session["suspended"] is False
    guiwins_views._resume_scene_editor_session(gui, "OTHER")  # someone else's dialog: left alone


@pytest.mark.asyncio
async def test_closing_the_dialog_repaints_only_the_previews_it_launched_and_stops_them_being_surfaces() -> None:
    async with _open():
        view, dialog, gui = _built["view"], _built["dialog"], _built["gui"]
        field_refs = {"legacy_edit": {"x": 1}, "v2_edit": {"y": 2}, "other": 3}
        other = MagicMock(spec=NiceGuiSceneView)
        other.dialog = "SOMEONE ELSE'S"
        gui.textviews = [view, other]
        repainted = []
        view.render = lambda: repainted.append(True)

        guiwins_views._scene_dialog_closed(gui, dialog, field_refs, SimpleNamespace(value=False))

        assert field_refs == {"other": 3}, "its handlers outlive the dialog and would take drags into a finished editor"
        assert repainted == [True]
        other.render.assert_not_called()


@pytest.mark.asyncio
async def test_opening_the_dialog_or_hiding_it_for_a_preview_repaints_nothing() -> None:
    async with _open():
        view, dialog, gui = _built["view"], _built["dialog"], _built["gui"]
        repainted = []
        view.render = lambda: repainted.append(True)
        field_refs = {"legacy_edit": {}}
        guiwins_views._scene_dialog_closed(gui, dialog, field_refs, SimpleNamespace(value=True))
        assert repainted == [] and "legacy_edit" in field_refs, "opening is not closing"

        gui.scene_editor_session = {"dialog": dialog, "name": "Panel", "suspended": True}
        guiwins_views._scene_dialog_closed(gui, dialog, field_refs, SimpleNamespace(value=False))
        assert repainted == [] and "legacy_edit" in field_refs, "a preview is holding it hidden: that is not the end"


# ##################################################################################
# A Legacy Scene's preview
# ##################################################################################
@pytest.mark.asyncio
async def test_a_legacy_preview_is_titled_with_the_scene_and_offers_its_own_controls() -> None:
    async with _open() as user:
        assert "Scene Preview: Panel" in _texts(user)
        assert {"Back to Editor", "Refresh"} <= {b.text for b in _all(user, ui.button)}
        assert {"Zoom", "Text density"} <= {s.props.get("label") for s in _all(user, ui.select)}
        assert {"Landscape", "Bounds", "Tasks"} <= {s.text for s in _all(user, ui.switch)}
        assert "Screen" not in {s.props.get("label") for s in _all(user, ui.select)}, "that is the Version 2 control"
        assert "Snap" not in {s.props.get("label") for s in _all(user, ui.select)}, "no designer behind it, nothing to drag"


@pytest.mark.asyncio
async def test_the_caption_says_the_size_the_element_count_and_what_the_picture_cannot_tell() -> None:
    async with _open() as user:
        texts = _texts(user)
        assert any(text.startswith("600 x 800 pixels · 2 element(s)") for text in texts)
        assert any(text.startswith("Hatched fills and italic underlined text are %variables") for text in texts)
        assert not any(text.startswith("Click an element to select it") for text in texts), "not an editing surface"


@pytest.mark.asyncio
async def test_a_preview_opened_from_nowhere_has_no_way_back() -> None:
    def page() -> None:
        gui = SimpleNamespace(font="x", dark_mode=False, state=PrimeItems, content_container=ui.column())
        _built["view"] = NiceGuiSceneView(gui, sceneedit.load_scene_for_edit("Panel", state=PrimeItems), {}, None)
        _built["gui"] = gui

    async with _open(page) as user:
        assert "Back to Editor" not in {b.text for b in _all(user, ui.button)}
        _built["view"]._back_to_editor()  # nothing to go back to: must not raise


@pytest.mark.asyncio
async def test_the_view_is_registered_as_the_current_one() -> None:
    async with _open():
        assert _built["gui"].textview is _built["view"]
        assert _built["view"] in _built["gui"].textviews


@pytest.mark.asyncio
async def test_a_scene_with_no_landscape_layout_has_its_landscape_switch_off() -> None:
    _load(_XML.replace("<widthLand>800</widthLand><heightLand>600</heightLand>", "<widthLand>-1</widthLand><heightLand>-1</heightLand>"))
    async with _open() as user:
        assert not _switch(user, "Landscape").enabled


@pytest.mark.asyncio
async def test_landscape_redraws_at_the_landscape_size_and_a_missing_size_says_so() -> None:
    async with _open() as user:
        _switch(user, "Landscape").value = True
        assert _built["view"].options.landscape is True
        assert any(text.startswith("800 x 600 pixels") for text in _texts(user))

    _load(_XML.replace("<widthLand>800</widthLand><heightLand>600</heightLand>", "<widthLand>-1</widthLand><heightLand>-1</heightLand>"))
    async with _open() as user:
        _built["view"]._set_option("landscape", True)
        assert any("has no landscape layout" in text for text in _texts(user))


@pytest.mark.asyncio
async def test_the_toggles_and_the_picklists_change_the_options_and_redraw() -> None:
    async with _open() as user:
        view = _built["view"]
        _switch(user, "Bounds").value = True
        _switch(user, "Tasks").value = True
        assert view.options.show_bounds is True and view.options.show_tasks is True

        _select(user, "Zoom").value = "50%"
        assert view.zoom == "50%"

        _select(user, "Text density").value = sceneview.DENSITY_CHOICES[0]
        assert view.options.density == float(sceneview.DENSITY_CHOICES[0])


@pytest.mark.asyncio
async def test_an_unreadable_density_falls_back_to_the_default() -> None:
    async with _open() as user:
        view = _built["view"]
        with user.client:
            view._density_selected(SimpleNamespace(value="lots"))
        assert view.options.density == sceneview.DEFAULT_DENSITY


@pytest.mark.asyncio
async def test_a_percentage_zoom_is_passed_to_the_fit_and_an_unreadable_one_means_fit(monkeypatch: pytest.MonkeyPatch) -> None:
    fits = []
    monkeypatch.setattr(guiwins_views, "_emit_canvas_fit", lambda root, width, height, fixed=None: fits.append(fixed))
    async with _open():
        view = _built["view"]
        view.zoom = "150%"
        view._apply_scale(600, 800)
        view.zoom = "wide%"
        view._apply_scale(600, 800)
        view.zoom = "Fit"
        view._apply_scale(600, 800)
        assert fits[-3:] == [1.5, None, None]


@pytest.mark.asyncio
async def test_the_size_boxes_in_the_dialog_decide_the_size_it_is_drawn_at() -> None:
    _built["field_refs"] = {"widthPort": SimpleNamespace(value="300"), "heightPort": SimpleNamespace(value="400")}
    async with _open() as user:
        assert any(text.startswith("300 x 400 pixels") for text in _texts(user))


@pytest.mark.asyncio
async def test_back_to_editor_reopens_the_dialog_and_asks_the_designer_to_rebuild() -> None:
    calls: list = []
    _built["field_refs"] = {"legacy_edit": _editor_for_legacy(calls)}
    async with _open() as user:
        dialog = _built["dialog"]
        gui = _built["gui"]
        gui.scene_editor_session = {"dialog": dialog, "name": "Panel", "suspended": True}
        _click(user, _button(user, "Back to Editor"))
        assert dialog.value is True
        assert ("rerender", None) in calls
        assert gui.scene_editor_session["suspended"] is False


# ----- the picture as an editing surface ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_with_a_designer_behind_it_the_picture_says_how_to_edit_it_and_offers_a_snap_grid() -> None:
    _built["field_refs"] = {"legacy_edit": _editor_for_legacy([])}
    async with _open() as user:
        assert any(text.startswith("Click an element to select it") for text in _texts(user))
        assert _select(user, "Snap").value == 5


@pytest.mark.asyncio
async def test_choosing_a_snap_writes_the_designers_own_grid_so_the_two_canvases_agree() -> None:
    editor = _editor_for_legacy([])
    _built["field_refs"] = {"legacy_edit": editor}
    async with _open() as user:
        _select(user, "Snap").value = 10
        assert editor["snap"]["grid"] == 10


@pytest.mark.asyncio
async def test_a_gesture_on_the_picture_goes_to_the_designers_handler_and_then_the_picture_is_redrawn() -> None:
    calls: list = []
    _built["field_refs"] = {"legacy_edit": _editor_for_legacy(calls)}
    async with _open():
        view = _built["view"]
        redrawn = []
        view.render = lambda: redrawn.append(True)
        view._legacy_from_canvas("geometry", {"moves": []})
        assert ("geometry", {"moves": []}) in calls and redrawn == [True]

        view._legacy_from_canvas("no such gesture", {})
        assert redrawn == [True], "an unknown gesture is ignored"


@pytest.mark.asyncio
async def test_a_gesture_with_no_designer_behind_the_picture_does_nothing() -> None:
    async with _open():
        view = _built["view"]
        redrawn = []
        view.render = lambda: redrawn.append(True)
        view._legacy_from_canvas("select", {})
        assert redrawn == []


@pytest.mark.asyncio
async def test_landscape_in_the_picture_turns_the_designers_own_orientation_too() -> None:
    editor = _editor_for_legacy([])
    _built["field_refs"] = {"legacy_edit": editor}
    async with _open() as user:
        _switch(user, "Landscape").value = True
        assert editor["orientation"]["landscape"] is True


# ##################################################################################
# A Version 2 Scene's preview
# ##################################################################################
@pytest.mark.asyncio
async def test_a_version_2_preview_offers_a_screen_not_a_density() -> None:
    _built["version"] = "v2"
    async with _open() as user:
        labels = {s.props.get("label") for s in _all(user, ui.select)}
        assert {"Screen", "Zoom"} <= labels
        assert not {"Text density", "Snap"} & labels
        assert _switch(user, "Landscape").enabled, "always means something for a V2 layout"
        assert {"Bounds", "Actions"} <= {s.text for s in _all(user, ui.switch)}


@pytest.mark.asyncio
async def test_the_caption_names_the_screen_the_layout_was_laid_out_in() -> None:
    _built["version"] = "v2"
    async with _open() as user:
        name, width, height = sceneview.V2_SCREENS[0]
        assert any(text.startswith(f"Drawn in {name} {width} x {height} dp") for text in _texts(user))
        assert any(text.startswith("The screen size is this preview's") for text in _texts(user))


@pytest.mark.asyncio
async def test_choosing_another_screen_or_landscape_changes_the_frame() -> None:
    _built["version"] = "v2"
    async with _open() as user:
        view = _built["view"]
        tablet = next(screen for screen in sceneview.V2_SCREENS if screen[0] == "Tablet")
        _select(user, "Screen").value = "Tablet"
        assert view._screen_size() == (tablet[1], tablet[2])
        _switch(user, "Landscape").value = True
        assert view._screen_size() == (tablet[2], tablet[1]), "on its side"
        assert any(text.startswith(f"Drawn in Tablet {tablet[2]} x {tablet[1]} dp") for text in _texts(user))


@pytest.mark.asyncio
async def test_an_unknown_screen_name_falls_back_to_the_first() -> None:
    _built["version"] = "v2"
    async with _open():
        view = _built["view"]
        view.screen = "Mystery"
        _name, width, height = sceneview.V2_SCREENS[0]
        assert view._screen_size() == (width, height)


@pytest.mark.asyncio
async def test_a_version_2_preview_draws_the_layout_the_dialog_holds_not_the_one_last_saved() -> None:
    _built["version"] = "v2"
    layout = scenelayout.v2_template_layout("Typed", "Dialog with buttons")
    _built["field_refs"] = {"v2_layout": layout}
    async with _open() as user:
        assert any(f"{sceneview.v2_component_count(layout)} component(s)" in text for text in _texts(user))


@pytest.mark.asyncio
async def test_a_layout_that_cannot_be_read_says_so_instead_of_drawing_nothing() -> None:
    _built["version"] = "v2"
    _built["field_refs"] = {"v2_layout": "not a dict"}

    def page() -> None:
        _built["gui"] = SimpleNamespace(font="x", dark_mode=False, state=PrimeItems, content_container=ui.column())
        edited = sceneedit.create_new_scene("Broken", scenemodel.SCENE_VERSION_V2, state=PrimeItems)
        edited.scene_element.find("lj").text = "garbage"
        _built["view"] = NiceGuiSceneView(_built["gui"], edited, _built["field_refs"], None)

    async with _open(page) as user:
        assert any("could not be read, so there is nothing to draw" in text for text in _texts(user))


@pytest.mark.asyncio
async def test_with_a_designer_behind_it_a_version_2_picture_is_a_reorder_surface() -> None:
    _built["version"] = "v2"
    seen: list = []
    _built["field_refs"] = {
        "v2_layout": scenelayout.v2_template_layout("Typed", "Dialog with buttons"),
        "v2_edit": {
            "handlers": {"v2select": lambda payload: seen.append(("select", payload))},
            "selection": {"path": (), "count": 1},
            "rerender": lambda: None,
        },
    }
    async with _open() as user:
        assert any(text.startswith("Click a component to select it") for text in _texts(user))
        view = _built["view"]
        redrawn = []
        view.render = lambda: redrawn.append(True)
        view._v2_from_canvas("v2select", {"path": ""})
        assert seen == [("select", {"path": ""})] and redrawn == [True]
        view._v2_from_canvas("nonsense", {})
        assert redrawn == [True]


@pytest.mark.asyncio
async def test_without_a_live_layout_a_version_2_picture_is_read_only() -> None:
    _built["version"] = "v2"
    async with _open():
        # The page decoded a layout for this view alone and there is no designer: a drag would be lost.
        _built["view"].field_refs.pop("v2_edit", None)
        assert _built["view"]._v2_editing() is None
        _built["view"]._v2_from_canvas("v2select", {})  # and a gesture finds no editor: nothing happens


# ##################################################################################
# The Tree view
# ##################################################################################
def _tree_page() -> None:
    gui = SimpleNamespace(font="Courier New", dark_mode=False, state=PrimeItems, content_container=ui.column())
    _built["gui"] = gui
    _built["view"] = NiceGuiTreeView(gui, "Tree of Home", _built["items"])


_ITEMS = [
    {"name": "Project: Home", "children": [{"name": "Profile:&nbsp;Morning", "children": ["Task: Wake&nbsp;Up", "Action &#9940; off"]}]},
    "plain string &#11013; left &#11157; right",
]


@pytest.mark.asyncio
async def test_the_tree_view_draws_its_title_and_the_hierarchy_it_was_given() -> None:
    _built["items"] = _ITEMS
    async with _open(_tree_page) as user:
        assert "Tree of Home" in _texts(user)
        assert "Click arrows to expand/collapse details." in _texts(user)
        (tree,) = _all(user, ui.tree)
        top = tree.props["nodes"]
        assert [node["id"] for node in top] == ["node_0", "node_1"]
        assert top[0]["children"][0]["children"][0]["id"] == "node_0_0_0"


@pytest.mark.asyncio
async def test_html_entities_in_names_become_the_characters_they_stand_for() -> None:
    _built["items"] = _ITEMS
    async with _open(_tree_page) as user:
        (tree,) = _all(user, ui.tree)
        top = tree.props["nodes"]
        profile = top[0]["children"][0]
        assert profile["label"].startswith("Profile: Morning"), "&nbsp; is a space"
        assert len(top[0]["label"]) >= 50, "names are padded so the arrows line up"
        assert [child["label"] for child in profile["children"]] == ["Task: Wake Up", "Action ⛔ off"]
        assert top[1]["label"] == "plain string ⬅️ left ➡️ right"


@pytest.mark.asyncio
async def test_the_tree_view_is_the_current_view_and_paints_itself_for_the_mode_the_window_is_in() -> None:
    _built["items"] = _ITEMS
    async with _open(_tree_page):
        view, gui = _built["view"], _built["gui"]
        assert gui.textview is view
        view.apply_theme("#1e293b", "#ffffff")
        assert view.card._style["background-color"] == "#1e293b !important"
        assert view.card._style["color"] == "#ffffff !important"
        assert view.scroll_area._style["background-color"] == "#1e293b !important"


@pytest.mark.asyncio
async def test_a_tree_view_with_nothing_in_it_still_draws() -> None:
    _built["items"] = []
    async with _open(_tree_page) as user:
        (tree,) = _all(user, ui.tree)
        assert tree.props["nodes"] == []


@pytest.mark.asyncio
async def test_a_tree_view_standing_alone_draws_into_a_column_of_its_own() -> None:
    def page() -> None:
        _built["view"] = NiceGuiTreeView(SimpleNamespace(font="x", dark_mode=False, state=PrimeItems), "Alone", ["a"])

    async with _open(page) as user:
        assert "Alone" in _texts(user)
