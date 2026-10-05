"""The Restore From History dialog: pick a configuration, preview one restore, apply it.

What a restore does is test_maprestore's, and reading the history is test_timeline's.  What is
tested here is the dialog around them: that nothing is applied unseen, that Apply is there only
while a preview is, that the list is read again after a restore and shows what was restored, and
that a history it cannot read says so instead of showing an empty list.

The history is replaced with snapshots built by hand and the older configuration is the one
test_maprestore builds; the dialog is the real one, on a page of NiceGUI's in-process user
simulation.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from maptasker.src import guiwins_restore, sessundo, timecomp, timeline
from maptasker.src.primitem import PrimeItems
from nicegui import core, ui
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

from tests.test_maprestore import _older, loaded  # noqa: F401  (loaded is the fixture the tests below ask for)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from nicegui.testing.user import User

_built: dict = {}


def _snapshot(source: str, day: int) -> timeline.Snapshot:
    return timeline.Snapshot(
        Path(f"/history/{source}"), datetime(2026, 9, day, 14, 29, 18, tzinfo=UTC), source, f"digest{day}"
    )


@pytest.fixture(autouse=True)
def _history(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Two snapshots (oldest first, as the timeline keeps them), and the older side from test_maprestore."""
    monkeypatch.chdir(tmp_path)
    _built.clear()
    _built.update(
        rebuilt=0,
        saved=0,
        save_answer=False,
        read=[],
        problem="",
        snapshots=[_snapshot("older.xml", 10), _snapshot("newer.xml", 15)],
    )
    monkeypatch.setattr(guiwins_restore.timeline, "snapshots", lambda: list(_built["snapshots"]))

    def configuration_of(snapshot: timeline.Snapshot, state: object) -> tuple:
        _built["read"].append(snapshot.source)
        return (None, _built["problem"]) if _built["problem"] else (_older(), "")

    monkeypatch.setattr(guiwins_restore.timecomp, "configuration_of", configuration_of)


def _page() -> None:
    async def rebuild() -> None:
        _built["rebuilt"] += 1

    async def save() -> bool:
        _built["saved"] += 1
        return _built["save_answer"]

    def jump(target: object) -> Callable:
        return lambda *_args: None

    _built["dialog"] = guiwins_restore.build_restore_dialog(jump, rebuild, save, PrimeItems)
    if _built["dialog"] is not None:
        _built["dialog"].open()


@contextlib.asynccontextmanager
async def _open() -> AsyncIterator[User]:
    try:
        async with user_simulation(root=_page) as user:
            await user.open("/")
            yield user
    finally:
        if core.app.is_started:
            await core.app.stop()


def _buttons(user: User, label: str) -> list[ui.button]:
    return [element for element in user.find(kind=ui.button).elements if element.text == label]


def _press(user: User, button: ui.button) -> None:
    UserInteraction(user, {button}, None).click()


def _only(user: User, label: str) -> ui.button:
    (button,) = _buttons(user, label)
    return button


def _labels(user: User) -> list[str]:
    return [element.text for element in user.find(kind=ui.label).elements]


async def _until(condition: Callable[[], object]) -> None:
    """Wait, up to two seconds, for something the dialog does on a timer or off the event loop."""
    for _ in range(40):
        if condition():
            return
        await asyncio.sleep(0.05)
    msg = "it did not happen"
    raise AssertionError(msg)


async def _listed(user: User) -> None:
    """Wait for the first read of the history to finish and the list to be drawn."""
    await user.should_see("to bring back")


async def _preview_one_that_can_be_applied(user: User) -> None:
    """Press 'Restore this' down the list until a preview comes up that Apply can make."""
    apply_button = _only(user, "Apply")
    for button in _buttons(user, "Restore this"):
        _press(user, button)
        if apply_button.enabled:
            return
    msg = "no row in the fixture could be applied"
    raise AssertionError(msg)


# ##################################################################################
# Opening
# ##################################################################################
@pytest.mark.asyncio
async def test_with_nothing_loaded_there_is_no_dialog_and_a_message() -> None:
    """There is nothing to restore INTO."""
    PrimeItems.tasker_root_elements = {"all_tasks": {}}
    async with _open() as user:
        assert _built["dialog"] is None
        assert user.notify.contains("No XML file has been loaded.  Get an XML file first.")


@pytest.mark.asyncio
async def test_with_no_history_there_is_no_dialog_and_a_message(loaded: None) -> None:  # noqa: F811
    """A configuration no file has ever been loaded from has nothing behind it to restore from."""
    _built["snapshots"] = []
    async with _open() as user:
        assert _built["dialog"] is None
        assert user.notify.contains("No configuration history has been recorded yet")


@pytest.mark.asyncio
async def test_the_newest_snapshot_is_chosen_first_and_its_rows_are_listed(loaded: None) -> None:  # noqa: F811
    """Newest first, because it is the one most often wanted; its differences are the rows."""
    async with _open() as user:
        await _listed(user)
        assert _built["read"] == ["newer.xml"]
        labels = _labels(user)
        assert "5 deleted since, to bring back -- 2 changed since, to put back" in labels
        assert len(_buttons(user, "Restore this")) == 7
        # What is deliberately not offered is counted, so a short list does not read as a short comparison.
        assert any("not offered" in label for label in labels)


@pytest.mark.asyncio
async def test_choosing_another_snapshot_reads_that_one(loaded: None) -> None:  # noqa: F811
    """The pulldown is the way back to something that was gone before this file was loaded."""
    async with _open() as user:
        await _listed(user)
        (choice,) = user.find(kind=ui.select).elements

        choice.value = 1
        await _until(lambda: len(_built["read"]) == 2)

        assert _built["read"] == ["newer.xml", "older.xml"]


@pytest.mark.asyncio
async def test_a_snapshot_that_cannot_be_read_says_why_instead_of_listing_nothing(loaded: None) -> None:  # noqa: F811
    """An empty list would read as 'nothing was lost'."""
    _built["problem"] = "That snapshot is damaged."
    async with _open() as user:
        await _until(lambda: user.notify.contains("That snapshot is damaged."))
        assert not _buttons(user, "Restore this")


# ##################################################################################
# Previewing: nothing is applied unseen
# ##################################################################################
@pytest.mark.asyncio
async def test_apply_is_greyed_out_until_a_preview_is_up(loaded: None) -> None:  # noqa: F811
    """Apply makes the plan on screen and no other, so with none on screen it is not there to press."""
    async with _open() as user:
        await _listed(user)
        assert not _only(user, "Apply").enabled


@pytest.mark.asyncio
async def test_restore_this_draws_a_preview_and_changes_nothing(loaded: None) -> None:  # noqa: F811
    """Pressing a row only plans.  The configuration is exactly as it was."""
    tasks_before = dict(PrimeItems.tasker_root_elements["all_tasks"])
    async with _open() as user:
        await _listed(user)
        await _preview_one_that_can_be_applied(user)

        assert "Preview -- nothing has changed yet" in _labels(user)
        assert _only(user, "Apply").enabled
    assert PrimeItems.tasker_root_elements["all_tasks"] == tasks_before
    assert _built["rebuilt"] == 0


@pytest.mark.asyncio
async def test_cancel_preview_takes_the_preview_and_apply_away(loaded: None) -> None:  # noqa: F811
    """The preview goes, and with it the only plan Apply could have made."""
    async with _open() as user:
        await _listed(user)
        await _preview_one_that_can_be_applied(user)

        _press(user, _only(user, "Cancel Preview"))

        assert "Preview -- nothing has changed yet" not in _labels(user)
        assert not _only(user, "Apply").enabled


# ##################################################################################
# Applying
# ##################################################################################
@pytest.mark.asyncio
async def test_apply_restores_one_object_rebuilds_the_window_and_lists_again(loaded: None) -> None:  # noqa: F811
    """One object, undoable, the window refreshed -- and the row restored stays, with a green button."""
    async with _open() as user:
        await _listed(user)
        before = next(label for label in _labels(user) if "to bring back" in label)
        await _preview_one_that_can_be_applied(user)

        _press(user, _only(user, "Apply"))
        await _until(lambda: _built["rebuilt"])
        await user.should_see("to bring back")

        assert _built["rebuilt"] == 1
        assert any("Undo is available." in message for message in user.notify.messages)
        assert next(label for label in _labels(user) if "to bring back" in label) != before
        assert not _only(user, "Apply").enabled
        # A restored object has nothing left to restore, so its row is kept but cannot be pressed again.
        assert [button.enabled for button in _buttons(user, "Restore this")].count(False) == 1
    assert sessundo.can_undo()


# ##################################################################################
# Saving
# ##################################################################################
@pytest.mark.asyncio
async def test_save_to_current_file_asks_the_view_to_save(loaded: None) -> None:  # noqa: F811
    """Written by the view, which reports its own outcome; the dialog only asks."""
    async with _open() as user:
        await _listed(user)
        _press(user, _only(user, "Save To Current File"))
        await _until(lambda: _built["saved"])
        assert _built["saved"] == 1


@pytest.mark.asyncio
async def test_close_closes_the_dialog(loaded: None) -> None:  # noqa: F811
    """Closing leaves the configuration alone."""
    async with _open() as user:
        await _listed(user)
        _press(user, _only(user, "Close"))
        assert _built["dialog"].value is False
