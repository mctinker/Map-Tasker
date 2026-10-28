"""The Undo/Redo buttons and the Edit History dialog (guiwins): they show the history of the state they are given.

The history itself -- what a checkpoint holds, what Undo restores -- is test_sessundo's and the editors'.
These draw the real controls on a page of NiceGUI's in-process user simulation and check that each reads
the history of the run state of the window it belongs to, so that two windows over two states cannot show
each other's edits.
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from maptasker.src.core.primitem import RunState
from maptasker.src.edit.sessundo import Checkpoint
from maptasker.src.gui import guiwins
from nicegui import core, ui
from nicegui.testing.user_simulation import user_simulation

from tests.doubles import fake_window

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from nicegui.testing.user import User


def _state_with(*labels: str) -> RunState:
    """A run state whose Undo history holds one checkpoint per label, oldest first."""
    state = RunState()
    when = datetime(2026, 10, 9, 12, 0, 0, tzinfo=UTC)
    state.undo_history.undo.extend(Checkpoint(label=label, when=when, payload=b"") for label in labels)
    return state


@contextlib.asynccontextmanager
async def _open(page: Callable[[], None]) -> AsyncIterator[User]:
    try:
        async with user_simulation(root=page) as user:
            await user.open("/")
            yield user
    finally:
        if core.app.is_started:
            await core.app.stop()


def _label_texts(user: User) -> list[str]:
    """Every label's text, in the order the labels were created -- which is the order they are drawn in.

    find() hands back a set, so iterating it says nothing about order; element ids count up as the page
    is built.
    """
    return [element.text for element in sorted(user.find(kind=ui.label).elements, key=lambda element: element.id)]


@pytest.mark.asyncio
async def test_the_history_dialog_lists_the_edits_of_the_state_it_is_given() -> None:
    mine = _state_with("Add Task 'A'", "Delete Profile 'B'")
    other = _state_with("Rename Project to 'Elsewhere'")

    async with _open(lambda: guiwins.build_edit_history_dialog(mine)) as user:
        texts = _label_texts(user)

    assert "Delete Profile 'B'" in texts  # Most recent first.
    assert "Add Task 'A'" in texts
    assert "Rename Project to 'Elsewhere'" not in texts
    assert texts.index("Delete Profile 'B'") < texts.index("Add Task 'A'")
    assert other.undo_history.undo  # Untouched.


@pytest.mark.asyncio
async def test_the_history_dialog_says_so_when_its_state_has_no_edits() -> None:
    async with _open(lambda: guiwins.build_edit_history_dialog(RunState())) as user:
        assert "Nothing has been changed yet." in _label_texts(user)


@pytest.mark.asyncio
async def test_the_undo_buttons_follow_the_state_of_their_own_window() -> None:
    edited, untouched = _state_with("Add Task 'A'"), RunState()
    built: dict = {}

    def page() -> None:
        for name, state in (("edited", edited), ("untouched", untouched)):
            window = fake_window(state=state, event_handlers=MagicMock())
            guiwins.create_undo_section(window)
            built[name] = window

    async with _open(page) as user:
        assert user is not None

    assert built["edited"].undo_edit_button.enabled
    assert not built["edited"].redo_edit_button.enabled
    assert built["edited"].undo_next_label.text == "Undo: Add Task 'A'"
    assert not built["untouched"].undo_edit_button.enabled
    assert built["untouched"].undo_next_label.text == "No changes to undo."
