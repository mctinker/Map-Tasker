"""The dialog that offers Save To Current File after a delete has closed the editor that held the button."""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

import pytest
from maptasker.src.gui import guiwins
from nicegui import core, ui
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from nicegui.testing.user import User

_saved: list[bool] = []
_answer = {"saved": True}


async def _save() -> bool:
    _saved.append(True)
    return _answer["saved"]


def _page() -> None:
    guiwins.build_unsaved_deletion_dialog("Deleted Task 'Quiet'.", _save)


@contextlib.asynccontextmanager
async def _open() -> AsyncIterator[User]:
    _saved.clear()
    _answer["saved"] = True
    try:
        async with user_simulation(root=_page) as user:
            await user.open("/")
            yield user
    finally:
        if core.app.is_started:
            await core.app.stop()


def _button(user: User, text: str) -> ui.button:
    (element,) = [e for e in user.find(kind=ui.button).elements if e.text == text]
    return element


def _dialog(user: User) -> ui.dialog:
    (element,) = user.find(kind=ui.dialog).elements
    return element


@pytest.mark.asyncio
async def test_it_says_what_was_deleted_and_that_it_is_not_saved() -> None:
    async with _open() as user:
        labels = [e.text for e in user.find(kind=ui.label).elements]
        assert "Deleted Task 'Quiet'." in labels
        assert "The deletion has not been saved to a file yet." in labels
        assert _dialog(user).value


@pytest.mark.asyncio
async def test_saving_closes_it() -> None:
    async with _open() as user:
        UserInteraction(user, {_button(user, "Save To Current File")}, None).click()
        await asyncio.sleep(0.1)
        assert _saved == [True]
        assert not _dialog(user).value


@pytest.mark.asyncio
async def test_a_save_that_did_not_happen_leaves_it_up_to_be_pressed_again() -> None:
    async with _open() as user:
        _answer["saved"] = False
        UserInteraction(user, {_button(user, "Save To Current File")}, None).click()
        await asyncio.sleep(0.1)
        assert _dialog(user).value
