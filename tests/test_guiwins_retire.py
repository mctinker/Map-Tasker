"""The Plugin Retirement Advisor window (guiwins_retire): the advice drawn for the file, the table, and Save Report.

What the advice says is test_retire's.  What is tested here is the window over it: that each plugin with a built-in is
drawn with its tag and its version, that every place is a link that jumps, that the table tab holds the whole list with
what the file uses, that it opens with no file loaded, and what Save Report says.  The window is the real one, on a
page of NiceGUI's in-process user simulation.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

import pytest
from maptasker.src.core import objnotes
from maptasker.src.core.mapjump import Target
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import sessundo
from maptasker.src.gui import guiwins_retire
from maptasker.src.mapops import retire
from nicegui import core, ui
from nicegui.testing.user import User
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

from tests.nicegui_harness import idle
from tests.test_maprefac import _load
from tests.test_retire import _xml

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

_built: dict[str, Any] = {}


@pytest.fixture(autouse=True)
def _configuration_loaded() -> Any:
    """The retirement fixture loaded, written by 6.7.8, with an empty undo history."""
    _built.clear()
    _built["jumps"] = []
    sessundo.clear(PrimeItems)
    objnotes.forget(PrimeItems)
    _load(_xml())
    yield
    sessundo.clear(PrimeItems)


def _page() -> None:
    def jump(target: Target) -> Callable[[], Any]:
        async def go() -> None:
            _built["jumps"].append(target)

        return go

    window = guiwins_retire.RetirementWindow(jump, PrimeItems)
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


def _shown(user: User) -> list[str]:
    return [element.text for element in user.find(kind=ui.label).elements]


def _press(user: User, label: str) -> None:
    UserInteraction(user, {b for b in user.find(kind=ui.button).elements if b.text == label}, None).click()


@pytest.mark.asyncio
async def test_each_plugin_with_a_built_in_is_drawn_with_its_tag_and_since_when() -> None:
    async with _open() as user:
        shown = _shown(user)

        assert "  REPLACED  AutoShortcut (com.joaomgcd.autoshortcut)" in shown
        assert "  PARTLY-REPLACED  Join (com.joaomgcd.join)" in shown
        assert "      Tasker's Action Shortcut, since Tasker 5.9.0 (a beta; released in 5.9.1)" in shown
        assert "TASKER NOW DOES THIS ITSELF (3)" in shown


@pytest.mark.asyncio
async def test_a_plugin_with_no_built_in_is_not_drawn() -> None:
    async with _open() as user:
        assert not any("com.joaomgcd.autoinput" in text for text in _shown(user))


@pytest.mark.asyncio
async def test_it_says_which_tasker_wrote_the_file() -> None:
    async with _open() as user:
        assert "Written by Tasker 6.7.8" in _shown(user)


@pytest.mark.asyncio
async def test_a_place_the_plugin_is_used_is_a_link_that_jumps_to_it() -> None:
    async with _open() as user:
        link = next(element for element in user.find(kind=ui.link).elements if "Evening" in element.text)

        UserInteraction(user, {link}, None).click()
        await idle()

        assert [target.key for target in _built["jumps"]] == ["11"]


@pytest.mark.asyncio
async def test_the_table_tab_holds_every_plugin_the_advisor_knows_with_what_the_file_uses() -> None:
    async with _open() as user:
        (table,) = user.find(kind=ui.table).elements
        rows = {row["plugin"]: row for row in table.rows}

        assert len(table.rows) == len(retire.entries())
        assert rows["Join"]["used"] == 3
        assert rows["Join"]["covers"] == "Partly replaced"
        assert rows["AutoShortcut"]["since"] == "5.9.0"
        assert rows["AutoShortcut"]["source"].startswith("https://")


@pytest.mark.asyncio
async def test_it_opens_with_no_file_loaded_and_says_so() -> None:
    PrimeItems.xml_root = None  # type: ignore[assignment]
    async with _open() as user:
        assert "No XML file has been loaded.  Get an XML file first." in _shown(user)
        (table,) = user.find(kind=ui.table).elements
        assert {row["used"] for row in table.rows} == {""}, "the table is still worth reading"


@pytest.mark.asyncio
async def test_save_report_says_where_the_report_went(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(retire, "write_report", lambda rows, state: "/out/MapTasker_PluginRetirement.txt")
    async with _open() as user:
        _press(user, "Save Report")

        assert user.notify.contains("Report saved as")


@pytest.mark.asyncio
async def test_save_report_says_when_it_could_not(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(retire, "write_report", lambda rows, state: "")
    async with _open() as user:
        _press(user, "Save Report")

        assert user.notify.contains("could not be saved")


@pytest.mark.asyncio
async def test_close_closes_the_window() -> None:
    async with _open() as user:
        dialog = _built["window"].dialog
        assert dialog.value

        _press(user, "Close")

        assert not dialog.value
