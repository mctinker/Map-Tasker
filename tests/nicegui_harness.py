"""A simulated NiceGUI window to put one dialog or drawing in, and the few ways tests look at what it holds.

A test hands `open_page` a function that builds some UI -- a dialog, a drawer, a canvas -- and gets back a user
looking at a page that ran it.  `found` is user.find without its assertion for "nothing there", and typed, which
the library's own is not; `button`, `click` and `labels` are the three things nearly every such test does.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any, TypeVar, cast

from nicegui import core, ui
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from nicegui.testing.user import User

T = TypeVar("T")


_build: dict[str, Callable[[], None]] = {}


def _page() -> None:
    _build["page"]()


@contextlib.asynccontextmanager
async def open_page(build: Callable[[], None]) -> AsyncIterator[User]:
    """Open a window whose page is whatever `build` puts up, and close the app afterwards."""
    _build["page"] = build
    try:
        async with user_simulation(root=_page) as user:
            await user.open("/")
            yield user
    finally:
        if core.app.is_started:
            await core.app.stop()


def found(user: User, kind: type[T]) -> list[T]:
    """Every visible element of this kind on the page, in the order they were built -- an empty list when none.

    NiceGUI hands back a set, whose order differs from one run (and one platform, and one Python) to the next, so
    a test that took the last of them was taking an arbitrary one.  An element's id counts up as the page is built.
    """
    try:
        elements = cast("set[T]", cast("Any", user).find(kind=kind).elements)
        return sorted(elements, key=lambda element: cast("ui.element", element).id)
    except AssertionError:
        return []


def button(user: User, text: str) -> ui.button:
    """The one button with exactly this text."""
    (element,) = [e for e in found(user, ui.button) if e.text == text]
    return element


async def press(user: User, element: ui.button) -> None:
    """Press this button, and give what it starts a moment to finish."""
    UserInteraction(user, {element}, None).click()
    await asyncio.sleep(0.1)


async def click(user: User, text: str) -> None:
    """Press the button with this text."""
    await press(user, button(user, text))


def label_texts(user: User) -> list[str]:
    """The text of every label on the page."""
    return [e.text for e in found(user, ui.label)]


def inputs(user: User) -> dict[str, ui.input]:
    """Every input on the page, by its label."""
    return {str(e.props.get("label")): e for e in found(user, ui.input)}


def dialogs(user: User) -> list[ui.dialog]:
    """Every dialog on the page."""
    return found(user, ui.dialog)


def all_elements(user: User) -> list[Any]:
    """Every element the page holds, visible or not -- for the ones user.find would not report."""
    assert user.client is not None
    return list(user.client.elements.values())
