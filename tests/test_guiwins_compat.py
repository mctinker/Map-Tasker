"""The Compatibility Check window (guiwins_compat): the versions asked about, the findings drawn, and the table.

What is decided is test_compat's.  What is tested here is the window over it: that picking a version redraws the
findings at once, that a line of them is a link that jumps to where the thing is used, that the table tab holds the
whole curated table with what the file uses, that it opens with no file loaded (the table is worth reading alone), and
that Save Report says where the report went.  The window is the real one, on a page of NiceGUI's in-process user simulation.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any

import pytest
from maptasker.src.core import objnotes
from maptasker.src.core.mapjump import Target
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import sessundo
from maptasker.src.gui import guiwins_compat
from maptasker.src.mapops import compat
from nicegui import core, ui
from nicegui.testing.user import User
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

from tests.nicegui_harness import idle
from tests.test_compat import _configuration
from tests.test_maprefac import _load

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

_built: dict[str, Any] = {}


@pytest.fixture(autouse=True)
def _configuration_loaded() -> Any:
    """The compatibility fixture loaded, written by 6.3.13, with an empty undo history."""
    _built.clear()
    _built["jumps"] = []
    sessundo.clear(PrimeItems)
    objnotes.forget(PrimeItems)
    _load(_configuration("6.3.13"))
    yield
    sessundo.clear(PrimeItems)


def _page() -> None:
    def jump(target: Target) -> Callable[[], Any]:
        async def go() -> None:
            _built["jumps"].append(target)

        return go

    window = guiwins_compat.CompatibilityWindow(jump, PrimeItems)
    _built["window"] = window
    window.build().open()


@contextlib.asynccontextmanager
async def _open() -> AsyncIterator[User]:
    try:
        async with user_simulation(root=_page) as user:
            await user.open("/")
            yield user
    finally:
        if core.app.is_started:
            await core.app.stop()


def _window() -> guiwins_compat.CompatibilityWindow:
    return _built["window"]


def _shown(user: User) -> list[str]:
    return [element.text for element in user.find(kind=ui.label).elements]


@pytest.mark.asyncio
async def test_it_says_which_tasker_wrote_the_file() -> None:
    async with _open() as user:
        assert "Written by Tasker 6.3.13" in _shown(user)


@pytest.mark.asyncio
async def test_asked_about_the_newest_release_it_finds_nothing_newer_than_it() -> None:
    async with _open() as user:
        shown = " ".join(_shown(user))

        assert "NEWER-TASKER" not in shown
        assert _window().target == "6.7.8"


@pytest.mark.asyncio
async def test_picking_an_older_tasker_redraws_the_findings_at_once() -> None:
    async with _open() as user:
        _window().pick(target="6.0.9")
        await asyncio.sleep(0)
        shown = " ".join(_shown(user))

        assert "NEWER-TASKER  [6.6.4] Action Java Code is new in Tasker 6.6.4 (a beta; released in 6.6.18)." in shown
        assert "Checked against Tasker 6.0.9" in shown


@pytest.mark.asyncio
async def test_picking_an_android_adds_what_that_android_is_too_old_for() -> None:
    async with _open() as user:
        _window().pick(android=33)
        await asyncio.sleep(0)

        assert any("Set Device Effects needs Android 15 or later." in text for text in _shown(user))


@pytest.mark.asyncio
async def test_a_place_a_finding_names_is_a_link_that_jumps_to_it() -> None:
    async with _open() as user:
        _window().pick(target="6.0.9")
        await asyncio.sleep(0)
        link = next(element for element in user.find(kind=ui.link).elements if "Morning" in element.text)

        UserInteraction(user, {link}, None).click()
        await idle()

        assert [target.key for target in _built["jumps"]] == ["10"]


@pytest.mark.asyncio
async def test_the_table_tab_holds_the_whole_table_with_what_the_file_uses() -> None:
    async with _open() as user:
        (table,) = user.find(kind=ui.table).elements
        rows = {row["name"]: row for row in table.rows}

        assert len(table.rows) == len(compat.table(PrimeItems))
        assert rows["Action Java Code"]["release"] == "6.6.4"
        assert rows["Action Java Code"]["post"].startswith("https://www.reddit.com/r/tasker/comments/")
        assert rows["Action Google Drive Sign In"]["post"] == "", "dated from the release notes, so there is no post"
        assert rows["Action Java Code"]["used"] == 1
        assert rows["Action Google Drive List"]["used"] == ""


@pytest.mark.asyncio
async def test_save_report_says_where_the_report_went(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(compat, "write_report", lambda rows, state: "/out/MapTasker_Compatibility.txt")
    async with _open() as user:
        UserInteraction(user, {b for b in user.find(kind=ui.button).elements if b.text == "Save Report"}, None).click()

        assert user.notify.contains("Report saved as")


@pytest.mark.asyncio
async def test_save_report_says_when_it_could_not(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(compat, "write_report", lambda rows, state: "")
    async with _open() as user:
        UserInteraction(user, {b for b in user.find(kind=ui.button).elements if b.text == "Save Report"}, None).click()

        assert user.notify.contains("could not be saved")


@pytest.mark.asyncio
async def test_with_no_file_loaded_it_still_opens_and_says_what_is_missing() -> None:
    PrimeItems.xml_root = None  # type: ignore[assignment]
    async with _open() as user:
        assert "No XML file has been loaded.  Get an XML file first." in _shown(user)
        (table,) = user.find(kind=ui.table).elements
        assert table.rows
        assert all(row["used"] == "" for row in table.rows)
