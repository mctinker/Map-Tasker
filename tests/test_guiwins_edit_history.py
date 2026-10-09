"""The Undo/Redo buttons and the Edit History dialog (guiwins): they show the history of the state they are given.

The history itself -- what a checkpoint holds, what Undo restores -- is test_sessundo's and the editors'.
These draw the real controls on a page of NiceGUI's in-process user simulation and check that each reads
the history of the run state of the window it belongs to, so that two windows over two states cannot show
each other's edits.
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from typing import TYPE_CHECKING

import pytest
from maptasker.src import guiwins
from maptasker.src.primitem import RunState
from maptasker.src.sessundo import Checkpoint
from nicegui import core, ui
from nicegui.testing.user_simulation import user_simulation

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
    return [element.text for element in user.find(kind=ui.label).elements]


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
            window = SimpleNamespace(state=state, event_handlers=MagicMock())
            guiwins._create_undo_section(window)  # noqa: SLF001
            built[name] = window

    async with _open(page) as user:
        assert user is not None

    assert built["edited"].undo_edit_button.enabled
    assert not built["edited"].redo_edit_button.enabled
    assert built["edited"].undo_next_label.text == "Undo: Add Task 'A'"
    assert not built["untouched"].undo_edit_button.enabled
    assert built["untouched"].undo_next_label.text == "No changes to undo."
