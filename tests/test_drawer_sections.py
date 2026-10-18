"""The collapsible sections of the right drawer: closed to start with, and open again when the drawer is redrawn.

The buttons inside them are the main window's and are not built here.  What is tested is the one thing the sections add: that
each starts folded (the point of them is a short drawer), that opening one is remembered on the window, and that a
drawer drawn again -- a change of language or appearance rebuilds the page -- shows the sections as the user left them.
"""

from __future__ import annotations

import contextlib
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from maptasker.src.gui import guiwins
from nicegui import core, ui
from nicegui.testing.user_simulation import user_simulation

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from nicegui.testing.user import User

_window = SimpleNamespace(drawer_sections={})


def _page() -> None:
    for key, title in (("history", "Compare & History"), ("analyze", "Analyze")):
        with guiwins._drawer_section(_window, key, title, "history"):  # type: ignore[arg-type]  # noqa: SLF001
            ui.button(f"{title} button")


@contextlib.asynccontextmanager
async def _open() -> AsyncIterator[User]:
    try:
        async with user_simulation(root=_page) as user:
            await user.open("/")
            yield user
    finally:
        if core.app.is_started:
            await core.app.stop()


def _sections(user: User) -> dict[str, ui.expansion]:
    return {element.props["label"]: element for element in user.find(kind=ui.expansion).elements}


@pytest.fixture(autouse=True)
def _fresh_window() -> None:
    _window.drawer_sections = {}


@pytest.mark.asyncio
async def test_every_section_starts_folded() -> None:
    async with _open() as user:
        sections = _sections(user)

        assert set(sections) == {"Compare & History", "Analyze"}
        assert not any(section.value for section in sections.values())


@pytest.mark.asyncio
async def test_opening_a_section_is_remembered_on_the_window() -> None:
    async with _open() as user:
        _sections(user)["Analyze"].set_value(True)

        assert _window.drawer_sections == {"analyze": True}


@pytest.mark.asyncio
async def test_a_drawer_drawn_again_shows_the_sections_as_they_were_left() -> None:
    _window.drawer_sections = {"history": True}
    async with _open() as user:
        sections = _sections(user)

        assert sections["Compare & History"].value is True
        assert sections["Analyze"].value is False


@pytest.mark.asyncio
async def test_folding_a_section_again_is_remembered_too() -> None:
    _window.drawer_sections = {"history": True}
    async with _open() as user:
        _sections(user)["Compare & History"].set_value(False)

        assert _window.drawer_sections == {"history": False}
