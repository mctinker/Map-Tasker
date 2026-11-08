"""The two places the user's notes and tags are reached from besides their own window: the drawer and the Diagram.

The drawer's button is the way in, and the Diagram's tag menu is how a tag is followed.  What each does when pressed is
the window's and the browser's, tested where they are written; what is tested here is that they are there, say so, and
do the one thing they are for.
"""

from __future__ import annotations

import contextlib
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from maptasker.src.gui import guiwins_diagram, guiwins_drawers
from nicegui import core, ui
from nicegui.elements.item import ItemSection
from nicegui.testing.user import User
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

_seen: dict[str, Any] = {}


@contextlib.asynccontextmanager
async def _open(page: Callable[[], None]) -> AsyncIterator[User]:
    try:
        async with user_simulation(root=page) as user:
            await user.open("/")
            yield user
    finally:
        if core.app.is_started:
            await core.app.stop()


def _button(user: User, label: str) -> ui.button:
    (found,) = [element for element in user.find(kind=ui.button).elements if element.text == label]
    return found


# ##################################################################################
# The drawer
# ##################################################################################
def _drawer_page() -> None:
    _seen["opened"] = 0

    def opened() -> None:
        _seen["opened"] += 1

    window = SimpleNamespace(event_handlers=SimpleNamespace(tools=SimpleNamespace(notes_event=opened)))
    guiwins_drawers._create_notes_button(window)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_the_analyze_section_has_a_button_that_opens_the_notes_window() -> None:
    async with _open(_drawer_page) as user:
        await user.should_see("Notes & Tags")
        UserInteraction(user, {_button(user, "Notes & Tags")}, None).click()

    assert _seen["opened"] == 1


@pytest.mark.asyncio
async def test_the_button_says_what_the_notes_are_and_that_they_are_not_in_the_backup() -> None:
    async with _open(_drawer_page) as user:
        await user.should_see("Notes & Tags")
        tooltip = next(element for element in user.find(kind=ui.tooltip).elements)

    assert "never in the backup" in tooltip.text


# ##################################################################################
# The Diagram's toolbar
# ##################################################################################
def _toolbar_page() -> None:
    _seen["commands"] = []
    view = SimpleNamespace(diagram_command=lambda name, argument=None: _seen["commands"].append((name, argument)))
    _seen["view"] = view
    with ui.row():
        guiwins_diagram.create_diagram_tools(view)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_the_toolbar_has_a_tag_button_that_is_hidden_until_the_diagram_has_tags() -> None:
    async with _open(_toolbar_page):
        view = _seen["view"]

        assert view.diagram_tag_button.visible is False

        guiwins_diagram.fill_tag_menu(view, {"flaky": 3, "family": 1})

        assert view.diagram_tag_button.visible is True


def _menu_items(view: Any) -> dict[str, ui.menu_item]:
    """The items of the tag menu by what they say."""
    return {
        next(section.text for section in item.descendants() if isinstance(section, ItemSection)): item
        for item in view.diagram_tag_menu.descendants()
        if isinstance(item, ui.menu_item)
    }


@pytest.mark.asyncio
async def test_each_tag_in_the_menu_follows_that_tag_and_the_last_item_lets_go() -> None:
    async with _open(_toolbar_page) as user:
        view = _seen["view"]
        with view.diagram_tag_button:
            guiwins_diagram.fill_tag_menu(view, {"flaky": 3, "family": 1})
        items = _menu_items(view)

        assert list(items) == ["#flaky  (3)", "#family  (1)", "Show All"]
        for label in items:
            UserInteraction(user, {items[label]}, None).click()

    assert _seen["commands"] == [("tag", "flaky"), ("tag", "family"), ("tag", "")]


@pytest.mark.asyncio
async def test_filling_the_menu_again_replaces_what_was_in_it() -> None:
    async with _open(_toolbar_page):
        view = _seen["view"]
        with view.diagram_tag_button:
            guiwins_diagram.fill_tag_menu(view, {"flaky": 3, "family": 1})
            guiwins_diagram.fill_tag_menu(view, {"only": 1})

        assert list(_menu_items(view)) == ["#only  (1)", "Show All"]


@pytest.mark.asyncio
async def test_a_diagram_with_no_tags_leaves_the_button_hidden_and_the_menu_empty() -> None:
    async with _open(_toolbar_page):
        view = _seen["view"]
        guiwins_diagram.fill_tag_menu(view, {"flaky": 1})
        guiwins_diagram.fill_tag_menu(view, {})

        assert view.diagram_tag_button.visible is False


def test_a_view_with_no_toolbar_is_left_alone() -> None:
    guiwins_diagram.fill_tag_menu(SimpleNamespace(), {"flaky": 1})  # type: ignore[arg-type]  # Must not raise.
