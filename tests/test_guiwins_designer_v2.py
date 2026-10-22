"""The Version 2 Scene designer (guiwins_designer_v2): the tree, the toolbar, Undo and the Add Element sheet.

What a structural edit does to a layout is test_sceneedit's.  These mount the real designer on a page of
NiceGUI's in-process user simulation, over the stock "Dialog with buttons" layout, and press what a person
would: pick a row, press Up or Duplicate or Delete, press Undo.  What is asserted is the designer's own part --
that every edit lands in the one layout dict the dialog will re-encode, that every one of them can be undone
by the one Undo, that a refused edit says why and leaves the layout exactly as it was, and that the buttons
which would act on more than the selection are switched off.
"""

from __future__ import annotations

import asyncio
import contextlib
import copy
import gc
import weakref
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from maptasker.src.core import scenelayout
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import sceneedit_v2, sceneedit_v2nodes, sceneedit_v2state, sceneedit_v2tree
from maptasker.src.gui import guiwins_canvas, guiwins_designer_v2, guiwins_sceneview, sceneview_v2
from nicegui import core, ui
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

from tests.test_mapfind import _FIXTURE_XML, _load

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from nicegui.testing.user import User

_built: dict = {}


# Where things are in the stock layout (see scenelayout.v2_template_layout): root -> header, content, button_row.
def _at(*indexes: int) -> tuple:
    """The path of the component reached by these child positions, from the root."""
    return tuple(part for index in indexes for part in ("children", index))


HEADER = _at(0)
TITLE = _at(0, 0)
CLOSE_BUTTON = _at(0, 1)
CONTENT = _at(1)
BODY_TEXT = _at(1, 0)
BUTTON_ROW = _at(2)


def _layout() -> dict:
    return scenelayout.v2_template_layout("Dialog", "Dialog with buttons")


@pytest.fixture(autouse=True)
def _configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fixture configuration loaded, and the designer captured when it is built."""
    _load(_FIXTURE_XML)
    _built.clear()
    _built.update(layout=_layout(), designer=None, field_refs={})
    original = guiwins_designer_v2._V2Designer.__init__

    def capture(self: guiwins_designer_v2._V2Designer, *args: object, **kwargs: object) -> None:
        original(self, *args, **kwargs)
        _built["designer"] = self

    monkeypatch.setattr(guiwins_designer_v2._V2Designer, "__init__", capture)


def _page() -> None:
    guiwins_designer_v2._build_v2_designer(
        SimpleNamespace(scene_name="Dialog"),
        _built["field_refs"],
        _built["layout"],
        PrimeItems,
    )


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
    """The toolbar or header button with this text; the one drawn last if a dialog has its own."""
    found = [e for e in user.client.elements.values() if isinstance(e, ui.button) and e.text == text]
    return max(found, key=lambda e: e.id)


def _press(user: User, text: str) -> None:
    _click(user, _button(user, text))


def _rows(user: User) -> list[ui.label]:
    """The tree's rows, in the order they are drawn."""
    found = [e for e in user.client.elements.values() if isinstance(e, ui.label) and "mt-v2-row" in e.classes]
    return sorted(found, key=lambda e: e.id)


def _row(user: User, path: tuple) -> ui.label:
    designer = _built["designer"]
    return designer.tree_rows[path][0]


def _paths() -> list[tuple]:
    return [row.path for row in sceneedit_v2tree.v2_flatten(_built["layout"])]


def _ids() -> list[str]:
    return [row.label for row in sceneedit_v2tree.v2_flatten(_built["layout"])]


def _node(path: tuple) -> dict | None:
    return sceneedit_v2tree.v2_node_at(_built["layout"], path)


async def _select(user: User, path: tuple) -> None:
    _click(user, _row(user, path))
    await asyncio.sleep(0.02)


# ##################################################################################
# Opening
# ##################################################################################
@pytest.mark.asyncio
async def test_the_layout_dict_is_registered_where_a_save_will_find_it() -> None:
    async with _open():
        assert _built["field_refs"]["v2_layout"] is _built["layout"]
        assert set(_built["field_refs"]["v2_edit"]) == {"handlers", "selection", "rerender"}


@pytest.mark.asyncio
async def test_a_designer_that_is_dropped_takes_its_canvas_entry_and_elements_with_it() -> None:
    async with _open() as user:
        designer = _built["designer"]
        root = designer.tree_root
        assert guiwins_canvas._ACTIVE_CANVASES[root] is designer.canvas_handlers
        gone = [weakref.ref(designer), *(weakref.ref(e) for e in user.client.elements.values())]
        user.client.delete()  # What the page going away does in the running app.
        del designer, user
    _built.clear()
    gc.collect()
    assert root not in guiwins_canvas._ACTIVE_CANVASES
    assert [ref for ref in gone if ref() is not None] == []


@pytest.mark.asyncio
async def test_opening_the_designer_again_does_not_grow_the_canvas_table() -> None:
    before = len(guiwins_canvas._ACTIVE_CANVASES)
    for _ in range(3):
        async with _open() as user:
            assert len(guiwins_canvas._ACTIVE_CANVASES) == before + 1
            user.client.delete()
            del user
        _built.update(designer=None, field_refs={})
        gc.collect()
    assert len(guiwins_canvas._ACTIVE_CANVASES) == before


@pytest.mark.asyncio
async def test_a_layout_with_no_root_says_there_is_nothing_to_design() -> None:
    _built["layout"] = {"name": "Empty"}
    async with _open() as user:
        texts = [e.text for e in user.client.elements.values() if isinstance(e, ui.label)]
        assert any("has no root component" in text for text in texts)
        assert _built["designer"] is None


@pytest.mark.asyncio
async def test_the_header_counts_the_components_and_the_tree_has_a_row_for_each() -> None:
    async with _open() as user:
        count = len(_paths())
        assert count > 5
        texts = [e.text for e in user.client.elements.values() if isinstance(e, ui.label)]
        assert f"Scene Components ({count})" in texts
        assert len(_rows(user)) == count


@pytest.mark.asyncio
async def test_the_root_starts_selected_and_its_toolbar_acts_on_nothing_but_the_root() -> None:
    async with _open() as user:
        assert _built["designer"].selection == {"path": (), "count": 1}
        for label in ("Up", "Down", "Out", "In", "Duplicate", "Delete"):
            assert not _button(user, label).enabled, label
        assert not _button(user, "Undo").enabled


@pytest.mark.asyncio
async def test_clicking_a_row_selects_it_highlights_it_and_enables_the_toolbar() -> None:
    async with _open() as user:
        await _select(user, CONTENT)
        assert _built["designer"].selection == {"path": CONTENT, "count": 1}
        assert "bg-blue-600" in _row(user, CONTENT).classes
        assert "bg-blue-600" not in _row(user, HEADER).classes
        for label in ("Up", "Down", "Out", "In", "Duplicate", "Delete"):
            assert _button(user, label).enabled, label


@pytest.mark.asyncio
async def test_the_inspector_is_headed_by_the_selected_components_label() -> None:
    async with _open() as user:
        await _select(user, CONTENT)
        heading = sceneedit_v2tree.v2_node_label(_node(CONTENT))
        assert heading in [e.text for e in user.client.elements.values() if isinstance(e, ui.label)]


@pytest.mark.asyncio
async def test_shift_extending_a_selection_takes_the_siblings_between_and_nothing_across_parents() -> None:
    async with _open():
        designer = _built["designer"]
        designer.select(HEADER)
        designer.select_from_surface({"path": sceneview_v2.v2_encode_path(BUTTON_ROW), "extend": True})
        assert designer.selection == {"path": HEADER, "count": 3}

        # Into another container: no run could reach there, so it is a fresh selection of that component.
        designer.select_from_surface({"path": sceneview_v2.v2_encode_path(TITLE), "extend": True})
        assert designer.selection == {"path": TITLE, "count": 1}


# ##################################################################################
# Structural edits, and the one Undo
# ##################################################################################
@pytest.mark.asyncio
async def test_duplicate_adds_a_copy_beside_it_and_keeps_the_copy_selected() -> None:
    async with _open() as user:
        before = len(_paths())
        await _select(user, CONTENT)
        _press(user, "Duplicate")
        assert len(_paths()) > before
        assert _built["designer"].selection["path"] == _at(2)


@pytest.mark.asyncio
async def test_down_then_up_walks_the_component_and_keeps_it_selected() -> None:
    async with _open() as user:
        original = copy.deepcopy(_built["layout"])
        await _select(user, HEADER)
        _press(user, "Down")
        assert _built["designer"].selection["path"] == _at(1)
        assert _node(_at(1))["id"] == "header"
        _press(user, "Up")
        assert _built["designer"].selection["path"] == _at(0)
        assert _built["layout"] == original


@pytest.mark.asyncio
async def test_moving_the_first_component_up_says_so_and_changes_nothing() -> None:
    async with _open() as user:
        original = copy.deepcopy(_built["layout"])
        await _select(user, HEADER)
        _press(user, "Up")
        assert user.notify.contains("Already first.")
        assert _built["layout"] == original
        assert not _built["designer"].history, "a refused edit leaves nothing on the undo stack"


@pytest.mark.asyncio
async def test_moving_the_last_component_down_says_so() -> None:
    async with _open() as user:
        await _select(user, BUTTON_ROW)
        _press(user, "Down")
        assert user.notify.contains("Already last.")


@pytest.mark.asyncio
async def test_in_puts_a_component_inside_the_one_above_and_out_takes_it_back() -> None:
    async with _open() as user:
        original = copy.deepcopy(_built["layout"])
        await _select(user, CONTENT)
        _press(user, "In")
        assert _built["designer"].selection["path"][:2] == _at(0), "it is now inside the header"
        _press(user, "Out")
        assert _built["layout"]["root"]["children"][1]["id"] == "content"
        assert len(_built["layout"]["root"]["children"]) == len(original["root"]["children"])


@pytest.mark.asyncio
async def test_in_under_a_component_that_cannot_hold_children_says_so() -> None:
    async with _open() as user:
        await _select(user, CLOSE_BUTTON)
        original = copy.deepcopy(_built["layout"])
        _press(user, "In")
        assert user.notify.contains("The component above it can't hold children.")
        assert _built["layout"] == original


@pytest.mark.asyncio
async def test_out_of_the_top_level_says_there_is_nowhere_to_go() -> None:
    async with _open() as user:
        await _select(user, CONTENT)
        _press(user, "Out")
        assert user.notify.contains("Nothing to move it out to.")


@pytest.mark.asyncio
async def test_undo_puts_back_every_edit_in_turn_and_switches_itself_off_at_the_start() -> None:
    async with _open() as user:
        original = copy.deepcopy(_built["layout"])
        await _select(user, CONTENT)
        _press(user, "Duplicate")
        _press(user, "Down")
        assert _button(user, "Undo").enabled
        _press(user, "Undo")
        _press(user, "Undo")
        assert _built["layout"] == original
        assert not _button(user, "Undo").enabled


@pytest.mark.asyncio
async def test_undo_restores_into_the_same_dict_the_save_holds() -> None:
    async with _open() as user:
        held = _built["field_refs"]["v2_layout"]
        await _select(user, CONTENT)
        _press(user, "Duplicate")
        _press(user, "Undo")
        assert _built["field_refs"]["v2_layout"] is held
        assert held is _built["layout"]


@pytest.mark.asyncio
async def test_undo_drops_a_selection_that_no_longer_exists_and_keeps_one_that_does() -> None:
    async with _open() as user:
        # The copy of the last Button is the only thing at that path, so undoing it leaves nothing there.
        await _select(user, _at(2, 1))
        _press(user, "Duplicate")
        assert _built["designer"].selection["path"] == _at(2, 2)
        _press(user, "Undo")
        assert _built["designer"].selection["path"] == ()

        # The copy of Content sits where the button row was, and the button row is at that path again once undone.
        await _select(user, CONTENT)
        _press(user, "Duplicate")
        _press(user, "Undo")
        assert _built["designer"].selection["path"] == _at(2)
        assert _node(_at(2))["id"] == "button_row"


# ##################################################################################
# Delete
# ##################################################################################
@pytest.mark.asyncio
async def test_delete_removes_the_component_selects_nothing_and_can_be_undone() -> None:
    async with _open() as user:
        original = copy.deepcopy(_built["layout"])
        await _select(user, BODY_TEXT)
        _press(user, "Delete")
        assert "body_text" not in str(_built["layout"])
        assert _built["designer"].selection["path"] == ()
        _press(user, "Undo")
        assert _built["layout"] == original


@pytest.mark.asyncio
async def test_delete_warns_when_a_task_addresses_the_component_by_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sceneedit_v2nodes, "find_component_id_references", lambda *_a, **_k: ["Fetcher", "Quiet"])
    async with _open() as user:
        await _select(user, BODY_TEXT)
        _press(user, "Delete")
        assert user.notify.contains("Fetcher, Quiet")
        assert user.notify.contains("Task(s) address it by id")


@pytest.mark.asyncio
async def test_a_delete_the_model_refuses_is_reported_and_leaves_the_layout_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sceneedit_v2nodes, "v2_delete_node", lambda *_a, **_k: ["The root can't be deleted."])
    async with _open() as user:
        original = copy.deepcopy(_built["layout"])
        await _select(user, BODY_TEXT)
        _press(user, "Delete")
        assert user.notify.contains("The root can't be deleted.")
        assert _built["layout"] == original
        assert not _built["designer"].history


# ##################################################################################
# Dragging, from either surface
# ##################################################################################
@pytest.mark.asyncio
async def test_a_drop_in_a_gap_reorders_and_a_drop_where_it_already_was_does_nothing() -> None:
    async with _open():
        designer = _built["designer"]
        original = copy.deepcopy(_built["layout"])
        designer.reorder_from_surface({"path": "children|0", "count": 1, "before": 3})
        assert [c["id"] for c in _built["layout"]["root"]["children"]] == ["content", "button_row", "header"]

        designer.restore()
        assert _built["layout"] == original

        designer.reorder_from_surface({"path": "children|0", "count": 1, "before": 0})
        assert _built["layout"] == original
        assert not designer.history


@pytest.mark.asyncio
async def test_a_click_on_a_path_that_does_not_exist_is_ignored() -> None:
    async with _open():
        designer = _built["designer"]
        designer.select_from_surface({"path": "children|9"})
        assert designer.selection == {"path": (), "count": 1}


# ##################################################################################
# The Add Element sheet
# ##################################################################################
@pytest.mark.asyncio
async def test_add_opens_the_sheet_and_says_where_the_element_will_go() -> None:
    async with _open() as user:
        await _select(user, CONTENT)
        _press(user, "Add")
        texts = [e.text for e in user.client.elements.values() if isinstance(e, ui.label)]
        assert "Add Element" in texts
        assert any(text.startswith(("Adds inside", "Adds after")) for text in texts)


@pytest.mark.asyncio
async def test_picking_a_chip_inserts_that_element_and_selects_it() -> None:
    async with _open() as user:
        await _select(user, CONTENT)
        before = len(_paths())
        _press(user, "Add")
        entry = next(
            entry
            for _g, entries in sceneedit_v2nodes.v2_palette_for(_built["layout"], CONTENT)
            for entry, reason in entries
            if not reason and entry.node_type == "Text"
        )
        _click(user, _button(user, entry.label))
        await asyncio.sleep(0.05)
        assert len(_paths()) == before + 1
        assert _node(_built["designer"].selection["path"])["type"] == "Text"


@pytest.mark.asyncio
async def test_picking_a_blocked_chip_explains_instead_of_inserting() -> None:
    blocked = [
        (entry, reason)
        for _g, entries in sceneedit_v2nodes.v2_palette_for(_layout(), CLOSE_BUTTON)
        for entry, reason in entries
        if reason
    ]
    if not blocked:
        pytest.skip("nothing is blocked at the close button")
    async with _open() as user:
        await _select(user, CLOSE_BUTTON)
        original = copy.deepcopy(_built["layout"])
        _press(user, "Add")
        _click(user, _button(user, blocked[0][0].label))
        assert user.notify.contains(blocked[0][1])
        assert _built["layout"] == original


@pytest.mark.asyncio
async def test_the_sheet_filters_as_you_type_and_says_when_nothing_matches() -> None:
    async with _open() as user:
        await _select(user, CONTENT)
        _press(user, "Add")
        search = next(
            e
            for e in user.client.elements.values()
            if isinstance(e, ui.input) and e.props.get("placeholder") == "Search elements"
        )
        before = len([e for e in user.client.elements.values() if isinstance(e, ui.button)])
        search.value = "text"
        after = len([e for e in user.client.elements.values() if isinstance(e, ui.button)])
        assert after < before
        search.value = "zzzzzz"
        texts = [e.text for e in user.client.elements.values() if isinstance(e, ui.label)]
        assert "No element matches that." in texts


# ##################################################################################
# The property sheet
# ##################################################################################
def _widget(user: User, kind: type, label: str) -> ui.element:
    """The inspector's widget of this kind labelled so, hidden (in a closed section) or not."""
    found = [e for e in user.client.elements.values() if isinstance(e, kind) and e.props.get("label") == label]
    assert found, f"no {kind.__name__} labelled {label!r}"
    return max(found, key=lambda e: e.id)


def _after(user: User, kind: type, label: str, anchor: ui.element) -> ui.element:
    """The first widget of this kind labelled so that was drawn after `anchor` -- its own, among many alike."""
    found = [
        e
        for e in user.client.elements.values()
        if isinstance(e, kind) and e.props.get("label") == label and e.id > anchor.id
    ]
    return min(found, key=lambda e: e.id)


def _texts(user: User) -> list[str]:
    return [e.text for e in user.client.elements.values() if isinstance(e, ui.label)]


@pytest.mark.asyncio
async def test_typing_into_a_property_writes_through_to_the_layout() -> None:
    async with _open() as user:
        await _select(user, TITLE)
        _widget(user, ui.input, "Tree label").value = "Heading"
        assert _node(TITLE)["treeLabel"] == "Heading"


@pytest.mark.asyncio
async def test_a_components_tree_row_and_heading_follow_its_name_as_it_is_typed() -> None:
    async with _open() as user:
        await _select(user, TITLE)
        _widget(user, ui.input, "Text").value = "Welcome aboard"
        assert _node(TITLE)["text"] == "Welcome aboard"
        assert "Welcome aboard" in _row(user, TITLE).text
        assert "Text 'Welcome aboard'" in _texts(user), "the inspector's own heading follows too"


@pytest.mark.asyncio
async def test_typing_into_a_property_that_names_nothing_leaves_the_tree_rows_alone() -> None:
    async with _open() as user:
        await _select(user, TITLE)
        before = _row(user, TITLE).text
        _widget(user, ui.input, "Text size").value = "30"
        assert _node(TITLE)["textSize"] == "30"
        assert _row(user, TITLE).text == before


@pytest.mark.asyncio
async def test_a_choice_property_is_a_pulldown_that_writes_what_was_chosen() -> None:
    async with _open() as user:
        await _select(user, TITLE)
        picker = _widget(user, ui.select, "Alignment")
        choice = next(option for option in picker.options if option)
        picker.value = choice
        assert _node(TITLE)["textAlign"] == choice


@pytest.mark.asyncio
async def test_a_colour_names_itself_in_its_swatch_and_a_bad_one_is_marked_but_kept() -> None:
    async with _open() as user:
        await _select(user, TITLE)
        colour = _widget(user, ui.color_input, "Colour")
        colour.value = "red"
        assert _node(TITLE)["color"] == "red"
        assert "error" not in colour.props

        colour.value = "not-a-colour"
        assert _node(TITLE)["color"] == "not-a-colour", "stored anyway: the Scene is the user's"
        assert "error" in colour.props


@pytest.mark.asyncio
async def test_a_state_property_writes_the_state_it_was_given() -> None:
    async with _open() as user:
        await _select(user, TITLE)
        picker = _widget(user, ui.select, "Enabled")
        state = next(option for option in picker.options if option and option != sceneedit_v2.V2_DYNAMIC_STATE)
        picker.value = state
        field = sceneedit_v2state.v2_state_field("enabled")
        assert sceneedit_v2state.v2_state_of(field, _node(TITLE).get("enabled", "")) == state


@pytest.mark.asyncio
async def test_a_dynamic_state_shows_its_value_box_and_keeps_what_was_typed_when_hidden() -> None:
    async with _open() as user:
        await _select(user, TITLE)
        picker = _widget(user, ui.select, "Enabled")
        dynamic = _after(user, ui.input, "Dynamic value", picker)
        picker.value = sceneedit_v2.V2_DYNAMIC_STATE
        await asyncio.sleep(0.3)  # NiceGUI refreshes bindings on a timer
        assert dynamic.visible
        dynamic.value = "%flag"
        picker.value = None
        await asyncio.sleep(0.3)
        assert not dynamic.visible
        assert dynamic.value == "%flag"


@pytest.mark.asyncio
async def test_a_category_remembers_whether_it_was_open_and_counts_what_is_filled_in() -> None:
    async with _open() as user:
        await _select(user, TITLE)
        designer = _built["designer"]
        content = next(
            e
            for e in user.client.elements.values()
            if isinstance(e, ui.expansion) and e.props.get("label") == "Content"
        )
        assert designer.expanded["category:Content"] is True or designer.expanded["category:Content"] is False
        content.value = not content.value
        assert designer.expanded["category:Content"] == content.value
        filled, total = content.props["caption"].split("/")
        assert 0 < int(filled) <= int(total)

        # Selecting another component keeps the section as it was left.
        await _select(user, _at(1, 0))
        reopened = next(
            e
            for e in user.client.elements.values()
            if isinstance(e, ui.expansion) and e.props.get("label") == "Content"
        )
        assert reopened.value == content.value


@pytest.mark.asyncio
async def test_the_component_id_is_renamed_on_blur_and_kept_unique() -> None:
    async with _open() as user:
        await _select(user, BODY_TEXT)
        field = _widget(user, ui.input, "Component id")
        field.value = "intro"
        _blur(field)
        assert _node(BODY_TEXT)["id"] == "intro"

        await _select(user, BODY_TEXT)
        field = _widget(user, ui.input, "Component id")
        field.value = "title_text"  # taken
        _blur(field)
        assert _node(BODY_TEXT)["id"] == "intro"
        assert field.value == "intro", "a refused id is put back in the box"
        assert _built["designer"].history, "only the accepted rename is on the undo stack"
        assert len(_built["designer"].history) == 1


@pytest.mark.asyncio
async def test_a_component_addressed_by_id_from_a_task_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sceneedit_v2nodes, "find_component_id_references", lambda *_a, **_k: ["Fetcher"])
    async with _open() as user:
        await _select(user, BODY_TEXT)
        assert "Addressed by id from: Fetcher" in _texts(user)


def _blur(widget: ui.input) -> None:
    """Fire the box's blur listeners, as leaving the field would."""
    from nicegui import events

    for listener in list(widget._event_listeners.values()):
        if listener.type == "blur":
            events.handle_event(
                listener.handler,
                events.GenericEventArguments(sender=widget, client=widget.client, args=None),
            )


# ##################################################################################
# Modifiers
# ##################################################################################
def _icon_buttons(user: User, icon: str) -> list[ui.button]:
    found = [e for e in user.client.elements.values() if isinstance(e, ui.button) and e.props.get("icon") == icon]
    return sorted(found, key=lambda e: e.id)


@pytest.mark.asyncio
async def test_modifiers_are_listed_in_order_with_their_count_in_the_heading() -> None:
    async with _open() as user:
        count = len(_node(())["modifiers"])
        assert f"Modifiers ({count})" in [
            e.props.get("label") for e in user.client.elements.values() if isinstance(e, ui.expansion)
        ]
        assert [
            e.text
            for e in user.client.elements.values()
            if isinstance(e, ui.label) and e.text in ("FillWidth", "Border")
        ]


@pytest.mark.asyncio
async def test_deleting_a_modifier_removes_it_and_undo_puts_it_back() -> None:
    async with _open() as user:
        original = copy.deepcopy(_built["layout"])
        _click(user, _icon_buttons(user, "close")[0])
        assert len(_node(())["modifiers"]) == len(original["root"]["modifiers"]) - 1
        _press(user, "Undo")
        assert _built["layout"] == original


@pytest.mark.asyncio
async def test_a_modifier_moves_down_and_back_up() -> None:
    async with _open() as user:
        original = [m["type"] for m in _node(())["modifiers"]]
        _click(user, _icon_buttons(user, "arrow_downward")[0])
        assert [m["type"] for m in _node(())["modifiers"]] == list(reversed(original))
        _click(user, _icon_buttons(user, "arrow_upward")[1])
        assert [m["type"] for m in _node(())["modifiers"]] == original


@pytest.mark.asyncio
async def test_the_open_state_of_the_modifiers_section_survives_the_rebuild_an_edit_causes() -> None:
    async with _open() as user:
        modifiers = next(
            e
            for e in user.client.elements.values()
            if isinstance(e, ui.expansion) and str(e.props.get("label", "")).startswith("Modifiers")
        )
        modifiers.value = True
        _click(user, _icon_buttons(user, "close")[0])
        rebuilt = next(
            e
            for e in user.client.elements.values()
            if isinstance(e, ui.expansion) and str(e.props.get("label", "")).startswith("Modifiers")
        )
        assert rebuilt.value is True


@pytest.mark.asyncio
async def test_adding_a_modifier_from_the_menu_appends_one_of_that_type() -> None:
    async with _open() as user:
        count = len(_node(())["modifiers"])
        _fire_click(_menu_entry(user, "FillHeight"))
        assert len(_node(())["modifiers"]) == count + 1
        assert _node(())["modifiers"][-1]["type"] == "FillHeight"


def _menu_entry(user: User, text: str) -> ui.menu_item:
    """The menu entry with this text -- kept in the item's one section -- in a menu that is not open."""
    found = [
        e
        for e in user.client.elements.values()
        if isinstance(e, ui.menu_item) and e.default_slot.children and e.default_slot.children[0].text == text
    ]
    assert found, f"no menu entry {text!r}"
    return max(found, key=lambda e: e.id)


def _fire_click(element: ui.element) -> None:
    """Fire an element's click listeners directly, for the entries of a menu that is not open."""
    from nicegui import events

    for listener in list(element._event_listeners.values()):
        if listener.type == "click":
            events.handle_event(
                listener.handler,
                events.ClickEventArguments(sender=element, client=element.client),
            )


# ##################################################################################
# Event handlers
# ##################################################################################
@pytest.mark.asyncio
async def test_a_component_with_a_handler_shows_its_event_and_its_actions() -> None:
    async with _open() as user:
        await _select(user, CLOSE_BUTTON)
        texts = _texts(user)
        assert "On click" in texts
        assert "Actions (2)" in texts
        assert "SetVariable" in texts
        assert "DismissLayout" in texts


@pytest.mark.asyncio
async def test_an_actions_fields_write_through_and_its_order_can_be_changed() -> None:
    async with _open() as user:
        await _select(user, CLOSE_BUTTON)
        handler = _node(CLOSE_BUTTON)["eventHandlers"]["handlers"][0]
        _click(user, _icon_buttons(user, "arrow_downward")[0])
        handler = _node(CLOSE_BUTTON)["eventHandlers"]["handlers"][0]
        assert [a["type"] for a in handler["actions"]] == ["DismissLayout", "SetVariable"]
        # SetVariable is second now, so its Up is the second Up button the sheet draws.
        _click(user, _icon_buttons(user, "arrow_upward")[1])
        handler = _node(CLOSE_BUTTON)["eventHandlers"]["handlers"][0]
        assert [a["type"] for a in handler["actions"]] == ["SetVariable", "DismissLayout"]


@pytest.mark.asyncio
async def test_deleting_an_action_and_then_the_handler_leaves_undo_to_restore_both() -> None:
    async with _open() as user:
        await _select(user, CLOSE_BUTTON)
        original = copy.deepcopy(_built["layout"])
        closes = _icon_buttons(user, "close")
        # Hand-picked: the last close is the second action's, the one before it the first action's.
        _click(user, closes[-1])
        assert len(_node(CLOSE_BUTTON)["eventHandlers"]["handlers"][0]["actions"]) == 1
        _press(user, "Undo")
        assert _built["layout"] == original


@pytest.mark.asyncio
async def test_the_only_when_box_sets_the_handlers_condition() -> None:
    async with _open() as user:
        await _select(user, CLOSE_BUTTON)
        _widget(user, ui.input, "Only when").value = "%portrait"
        assert _node(CLOSE_BUTTON)["eventHandlers"]["handlers"][0]["condition"] == "%portrait"


@pytest.mark.asyncio
async def test_adding_a_handler_and_an_action_from_their_menus() -> None:
    async with _open() as user:
        await _select(user, CLOSE_BUTTON)
        handlers = len(_node(CLOSE_BUTTON)["eventHandlers"]["handlers"])
        _fire_click(_menu_entry(user, "hold"))
        assert len(_node(CLOSE_BUTTON)["eventHandlers"]["handlers"]) == handlers + 1

        # The last menu drawn is the new handler's own Add action, so that is where this lands.
        _fire_click(_menu_entry(user, "RunTask"))
        actions = _node(CLOSE_BUTTON)["eventHandlers"]["handlers"][-1]["actions"]
        assert [action["type"] for action in actions] == ["RunTask"]


@pytest.mark.asyncio
async def test_a_runtask_action_offers_the_loaded_tasks_by_name() -> None:
    async with _open() as user:
        await _select(user, CLOSE_BUTTON)
        _fire_click(_menu_entry(user, "RunTask"))
        picker = max(
            (e for e in user.client.elements.values() if isinstance(e, ui.select) and "Fetcher" in e.options),
            key=lambda e: e.id,
        )
        picker.value = "Fetcher"
        action = _node(CLOSE_BUTTON)["eventHandlers"]["handlers"][0]["actions"][-1]
        assert "Fetcher" in action.values()


# ##################################################################################
# The pickers
# ##################################################################################
@pytest.fixture
def caret(monkeypatch: pytest.MonkeyPatch) -> list:
    """The browser's answer about where the cursor is, and a record of what the page was told to run."""
    told: list = []

    class Response:
        def __await__(self) -> object:
            yield from ()
            return None

    monkeypatch.setattr(ui, "run_javascript", lambda code, **_k: told.append(code) or Response())
    return told


def _dialog_buttons(user: User) -> list[ui.button]:
    return sorted((e for e in user.client.elements.values() if isinstance(e, ui.button)), key=lambda e: e.id)


@pytest.mark.asyncio
async def test_the_show_when_picker_inserts_a_variable_into_the_field_and_closes(caret: list) -> None:
    async with _open() as user:
        await _select(user, TITLE)
        field = _widget(user, ui.input, "Show when")
        field.value = "a b"
        before = {e.id for e in user.client.elements.values()}
        # The append-slot button beside Show when opens the picker.
        opener = next(
            e
            for e in user.client.elements.values()
            if isinstance(e, ui.button) and e.props.get("icon") == "playlist_add" and e.parent_slot.parent is field
        )
        _click(user, opener)
        choice = sceneedit_v2state.v2_show_when_choices(state=PrimeItems)[0][1][0]
        button = next(
            e
            for e in user.client.elements.values()
            if isinstance(e, ui.button) and e.id not in before and e.text == choice.label
        )
        _click(user, button)
        await asyncio.sleep(0.1)
        assert field.value == sceneedit_v2state.v2_insert_show_when("a b", choice.value, None)[0]
        assert _node(TITLE)["showWhen"] == field.value
        dialog = next(e for e in user.client.elements.values() if isinstance(e, ui.dialog) and e.id > field.id)
        assert dialog.value is False, "closed on the pick so the result is visible"
        assert any("setSelectionRange" in code for code in caret), "the cursor is put back after the insert"


@pytest.mark.asyncio
async def test_the_show_when_picker_filters_by_what_is_typed_and_says_when_a_category_is_empty(caret: list) -> None:
    async with _open() as user:
        await _select(user, TITLE)
        field = _widget(user, ui.input, "Show when")
        opener = next(
            e
            for e in user.client.elements.values()
            if isinstance(e, ui.button) and e.props.get("icon") == "playlist_add" and e.parent_slot.parent is field
        )
        _click(user, opener)
        search = next(
            e
            for e in user.client.elements.values()
            if isinstance(e, ui.input) and e.props.get("placeholder") == "Search variables"
        )
        search.value = "zzzz-no-such-variable"
        assert "Nothing here." in _texts(user)


@pytest.mark.asyncio
async def test_a_numeric_or_text_variable_property_has_a_select_variable_button(caret: list) -> None:
    async with _open() as user:
        await _select(user, TITLE)
        field = _widget(user, ui.input, "Max lines")
        opener = next(
            e
            for e in user.client.elements.values()
            if isinstance(e, ui.button) and e.props.get("icon") == "playlist_add" and e.parent_slot.parent is field
        )
        _click(user, opener)
        assert "Select a variable for Max lines" in _texts(user)


@pytest.mark.asyncio
async def test_choosing_select_variable_on_a_state_opens_the_picker_at_once(caret: list) -> None:
    async with _open() as user:
        await _select(user, TITLE)
        picker = _widget(user, ui.select, "Enabled")
        picker.value = sceneedit_v2.V2_VARIABLE_STATE
        assert "Select a variable for Enabled" in _texts(user)


@pytest.mark.asyncio
async def test_the_icon_picker_replaces_the_field_with_the_icon_chosen() -> None:
    async with _open() as user:
        await _select(user, CLOSE_BUTTON)
        field = _widget(user, ui.input, "Icon")
        assert field.value == "icon:Close"
        opener = next(
            e
            for e in user.client.elements.values()
            if isinstance(e, ui.button) and e.props.get("icon") == "apps" and e.parent_slot.parent is field
        )
        _click(user, opener)
        assert "Pick an icon" in _texts(user)
        tiles = [
            e for e in user.client.elements.values() if isinstance(e, ui.button) and e.props.get("stack") is not None
        ]
        assert 0 < len(tiles) <= guiwins_designer_v2._ICON_PREVIEW_LIMIT
        name = tiles[0].default_slot.children[1].text
        _click(user, tiles[0])
        assert field.value == sceneedit_v2tree.v2_icon_reference(name)
        assert _node(CLOSE_BUTTON)["icon"] == field.value


@pytest.mark.asyncio
async def test_the_icon_picker_narrows_by_name_and_says_when_nothing_is_left() -> None:
    async with _open() as user:
        await _select(user, CLOSE_BUTTON)
        field = _widget(user, ui.input, "Icon")
        opener = next(
            e
            for e in user.client.elements.values()
            if isinstance(e, ui.button) and e.props.get("icon") == "apps" and e.parent_slot.parent is field
        )
        _click(user, opener)
        search = next(
            e
            for e in user.client.elements.values()
            if isinstance(e, ui.input) and e.props.get("placeholder") == "Search icons"
        )
        search.value = "zzzz_no_such_icon"
        assert "Nothing here." in _texts(user)
        search.value = "close"
        tiles = [
            e for e in user.client.elements.values() if isinstance(e, ui.button) and e.props.get("stack") is not None
        ]
        assert tiles
        assert all("close" in t.default_slot.children[1].text for t in tiles)


@pytest.mark.asyncio
async def test_typing_an_icon_reference_is_kept_exactly_and_drives_the_glyph() -> None:
    async with _open() as user:
        await _select(user, CLOSE_BUTTON)
        field = _widget(user, ui.input, "Icon")
        field.value = "symbol:cloud_upload;opsz:24"
        assert _node(CLOSE_BUTTON)["icon"] == "symbol:cloud_upload;opsz:24"


@pytest.mark.asyncio
async def test_the_material_colour_menu_sets_a_role_by_name() -> None:
    async with _open() as user:
        await _select(user, TITLE)
        colour = _widget(user, ui.color_input, "Colour")
        role = next(iter(guiwins_designer_v2.V2_MATERIAL_PALETTE))
        entries = [
            e
            for e in user.client.elements.values()
            if isinstance(e, ui.item)
            and colour in e.ancestors()
            and any(getattr(c, "text", None) == role for c in e.descendants())
        ]
        assert len(entries) == 1
        _fire_click(entries[0])
        assert colour.value == role
        assert _node(TITLE)["color"] == role
        assert "error" not in colour.props, "a role is a colour name"


# ##################################################################################
# Mounting it in a Scene dialog
# ##################################################################################
def _scene(layout: dict | None) -> SimpleNamespace:
    import xml.etree.ElementTree as ET

    element = ET.fromstring('<Scene sr="sceneNew"><nme>Dialog</nme></Scene>')
    if layout is None:
        ET.SubElement(element, "lj").text = "not a layout"
    else:
        scenelayout.encode_v2_layout(element, layout)
    return SimpleNamespace(scene_element=element, scene_name="Dialog")


def _mount_page() -> None:
    guiwins_designer_v2.V2Designer().build_body(
        SimpleNamespace(),
        _built["scene"],
        _built["field_refs"],
        None,
        PrimeItems,
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
async def test_a_scene_dialog_mounts_the_designer_over_the_scenes_own_layout() -> None:
    _built["scene"] = _scene(_layout())
    async with _open_mounted() as user:
        assert f"Scene Components ({len(sceneedit_v2tree.v2_flatten(_layout()))})" in _texts(user)
        assert _built["field_refs"]["v2_layout"]["root"]["id"] == "root_column"


@pytest.mark.asyncio
async def test_a_layout_that_cannot_be_read_is_said_to_be_left_exactly_as_it_is() -> None:
    _built["scene"] = _scene(None)
    async with _open_mounted() as user:
        assert any("could not be read, and will be left exactly as it is" in text for text in _texts(user))
        assert "v2_layout" not in _built["field_refs"]


def test_the_preview_says_a_version_2_layout_has_no_size_of_its_own() -> None:
    assert "no size of its own" in guiwins_designer_v2.V2Designer.preview_tooltip


def _dialog_page() -> None:
    _built["column"] = ui.column()


@pytest.mark.asyncio
async def test_a_scene_dialog_closed_for_good_leaves_nothing_of_its_designer_behind() -> None:
    """Open, close and re-open Edit Scene the way the running app does, and count what is left."""
    _built["scene"] = _scene(_layout())
    gui = SimpleNamespace(scene_editor_session=None, textviews=[])
    async with _open_dialog_page() as user:
        elements, table = len(user.client.elements), len(guiwins_canvas._ACTIVE_CANVASES)
        for opened in range(1, 4):
            field_refs: dict = {}
            with _built["column"], ui.dialog() as dialog, ui.card():
                guiwins_designer_v2.V2Designer().build_body(
                    SimpleNamespace(), _built["scene"], field_refs, dialog, PrimeItems
                )
            dialog.on_value_change(
                lambda e, d=dialog, f=field_refs: guiwins_sceneview._scene_dialog_closed(gui, d, f, e)
            )
            dialog.open()
            assert len(guiwins_canvas._ACTIVE_CANVASES) == table + 1
            dialog.close()
            await asyncio.sleep(0.05)
            del dialog, field_refs
            _built["designer"] = None  # The fixture's own capture of it.
            gc.collect()
            # NiceGUI leaves one empty placeholder div where a dialog was declared; the designer's page is gone.
            assert len(user.client.elements) == elements + opened
            assert len(guiwins_canvas._ACTIVE_CANVASES) == table


@contextlib.asynccontextmanager
async def _open_dialog_page() -> AsyncIterator[User]:
    try:
        async with user_simulation(root=_dialog_page) as user:
            await user.open("/")
            yield user
    finally:
        if core.app.is_started:
            await core.app.stop()
