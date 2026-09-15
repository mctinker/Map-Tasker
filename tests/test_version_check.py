"""New version check (guiutils) Unit Tests

Once a day MapTasker asks PyPI whether there is a newer version.  That request blocks until
PyPI answers or its timeout runs out, and the GUI runs on a single event loop -- so a request
made there freezes the whole window.  check_new_version hands it to a worker thread
(run.io_bound, stood in for here by asyncio.to_thread) and builds only the upgrade controls
back on the loop.  No network is involved: is_new_version is replaced in every test.
"""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from maptasker.src import guiutils


def _event_loop_running() -> bool:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


@pytest.fixture
def view(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """The first run today, with NiceGUI's widgets and worker threads stood in for."""
    monkeypatch.setattr(guiutils, "is_first_run_today", lambda: True)
    monkeypatch.setattr(guiutils, "ui", MagicMock())
    monkeypatch.setattr(guiutils, "translate_string", lambda text: text)

    async def io_bound(function, *args):  # noqa: ANN001, ANN002, ANN202
        return await asyncio.to_thread(function, *args)

    monkeypatch.setattr(guiutils.run, "io_bound", io_bound)
    return SimpleNamespace(upgrade_container=MagicMock(), event_handlers=MagicMock())


def _check(view: SimpleNamespace) -> None:
    """Start the check the way the GUI does -- from synchronous code on the loop -- and wait for it."""

    async def page_build() -> None:
        guiutils.check_new_version(view)
        await view._version_check

    asyncio.run(page_build())


def test_pypi_is_asked_on_a_worker_thread_not_the_event_loop(view: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    """The one call that blocks runs where there is no event loop for it to freeze."""
    asked_with_loop_running = []
    monkeypatch.setattr(guiutils, "is_new_version", lambda: asked_with_loop_running.append(_event_loop_running()) or True)

    _check(view)

    assert asked_with_loop_running == [False]


def test_starting_the_check_returns_before_pypi_is_asked(view: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    """check_new_version only schedules the check, so the page build carries straight on."""
    asked = []
    monkeypatch.setattr(guiutils, "is_new_version", lambda: asked.append(True) or False)

    async def page_build() -> None:
        guiutils.check_new_version(view)
        assert asked == []
        await view._version_check
        assert asked == [True]

    asyncio.run(page_build())


@pytest.mark.parametrize("newer", [True, False])
def test_the_upgrade_controls_appear_only_for_a_newer_version(
    view: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    newer: bool,
) -> None:
    """Built into the sidebar's upgrade slot when PyPI has something newer, and not otherwise."""
    monkeypatch.setattr(guiutils, "is_new_version", lambda: newer)

    _check(view)

    assert view.upgrade_container.clear.called is newer
    assert hasattr(view, "upgrade_button") is newer
    assert hasattr(view, "whats_new_button") is newer


def test_after_the_first_run_today_nothing_is_scheduled(view: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    """PyPI is asked once a day; later starts do not even schedule a check."""
    monkeypatch.setattr(guiutils, "is_first_run_today", lambda: False)
    monkeypatch.setattr(guiutils, "is_new_version", lambda: pytest.fail("PyPI was asked again the same day"))

    guiutils.check_new_version(view)

    assert not hasattr(view, "_version_check")


def test_a_check_that_raises_is_logged_not_lost(
    view: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A task nobody awaits would swallow the error; the done callback puts it in the log."""

    def broken() -> bool:
        raise ValueError("PyPI answered nonsense")

    monkeypatch.setattr(guiutils, "is_new_version", broken)
    caplog.set_level(logging.ERROR, logger="MapTasker")

    with pytest.raises(ValueError, match="nonsense"):
        _check(view)

    assert any("Checking for a new version failed" in record.getMessage() for record in caplog.records)
