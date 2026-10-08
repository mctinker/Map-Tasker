"""Shared by the Find/Replace dialog's tests: a stand-in view, a page to open the dialog on, and finders.

Not a test module (no test_ prefix), so pytest does not collect it.  The autouse fixture each test module
needs -- loading the configuration and recording jumps -- stays in the module, since what a module loads is its own.
"""

from __future__ import annotations

import contextlib
from types import SimpleNamespace
from typing import TYPE_CHECKING

from nicegui import core, ui
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

from maptasker.src import guiwins_search
from maptasker.src.primitem import PrimeItems

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from nicegui.testing.user import User

built: dict = {}


class View(guiwins_search.TextViewSearch):
    """The little of a Map view the Find/Replace dialog reaches for."""

    def __init__(self, title: str = "Map") -> None:
        async def view_event(view_type: str) -> None:
            built.setdefault("rebuilt", []).append(view_type)

        self.master_gui = SimpleNamespace(
            state=PrimeItems,
            ai_name="",
            ai_model="",
            event_handlers=SimpleNamespace(view_event=view_event),
        )
        self.title = title
        self.scroll_area = ui.scroll_area()
        self.search_input = ui.input(label="Search")
        self._content_token = 0
        self._last_search = None
        self._find_query = None
        self._find_ask = None
        self._find_dialog = None
        self._replace_inputs = None
        self._replace_ticks = None


def page() -> None:
    view = View(built["title"])
    built["view"] = view
    ui.button("Find", on_click=view.find_event)
    ui.button("Search", on_click=view.search_event)


@contextlib.asynccontextmanager
async def open_page(title: str = "Map") -> AsyncIterator[User]:
    """The page with a view on it, its Find and Search buttons, and nothing open."""
    built["title"] = title
    try:
        async with user_simulation(root=page) as user:
            await user.open("/")
            yield user
    finally:
        if core.app.is_started:
            await core.app.stop()


@contextlib.asynccontextmanager
async def open_dialog(title: str = "Map") -> AsyncIterator[User]:
    """The page with a view on it and the Find dialog open."""
    async with open_page(title) as user:
        click(user, by_text(user, "Find")[0])
        yield user


def by_text(user: User, text: str) -> list[ui.button]:
    return sorted((e for e in user.find(kind=ui.button).elements if e.text == text), key=lambda e: e.id)


def click(user: User, element: ui.element) -> None:
    UserInteraction(user, {element}, None).click()


def select(user: User, label: str) -> ui.select:
    """The Find tab's select with this label, shown or not -- user.find only sees what is on screen.

    The Replace tab labels some of its pulldowns the same way, so this takes the first drawn: the Find tab's.
    """
    found = (e for e in user.client.elements.values() if isinstance(e, ui.select) and e.props.get("label") == label)
    return min(found, key=lambda e: e.id)


def field(user: User, label: str) -> ui.input:
    found = (e for e in user.client.elements.values() if isinstance(e, ui.input) and e.props.get("label") == label)
    return min(found, key=lambda e: e.id)


def labels(user: User) -> list[str]:
    return [element.text for element in user.find(kind=ui.label).elements]


def links(user: User) -> list[ui.link]:
    try:
        return sorted(user.find(kind=ui.link).elements, key=lambda e: e.id)
    except AssertionError:  # user.find insists on at least one: a list with no rows has none
        return []


def press_find(user: User) -> None:
    """Press the dialog's own Find button (the second 'Find': the first is the page's, the third the tab's)."""
    click(user, by_text(user, "Find")[-1])
