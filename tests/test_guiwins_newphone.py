"""The New-Phone Checklist window (guiwins_newphone): the list drawn, the ticks saved as they are made, and the buttons.

What goes on the list is test_newphone's.  What is tested here is the window over it: that every group is drawn with
a count, that ticking a box is saved at once and is there when the window is opened again, that a plugin or app the
chosen phone lacks is flagged, that a Profile is a link into the Map, that Clear ticks and Only what is left do what
they say, and that it opens with no file loaded.  The window is the real one, on a page of NiceGUI's in-process user
simulation, in a directory of its own so the ticks file is not left in the project.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any

import pytest
from maptasker.src.core import appinv, objnotes
from maptasker.src.core.mapjump import Target
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import sessundo
from maptasker.src.gui import guiwins_newphone
from maptasker.src.mapops import newphone
from nicegui import core, ui
from nicegui.testing.user import User
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

from tests.test_maprefac import _load
from tests.test_newphone import PHONE, XML

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable
    from pathlib import Path

_built: dict[str, Any] = {}


@pytest.fixture(autouse=True)
def _configuration_loaded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """The checklist fixture loaded, in a directory of its own, with an empty undo history."""
    monkeypatch.chdir(tmp_path)
    _built.clear()
    _built["jumps"] = []
    sessundo.clear(PrimeItems)
    objnotes.forget(PrimeItems)
    _load(XML)
    yield
    sessundo.clear(PrimeItems)


def _page() -> None:
    def jump(target: Target) -> Callable[[], Any]:
        async def go() -> None:
            _built["jumps"].append(target)

        return go

    window = guiwins_newphone.NewPhoneWindow(jump, PrimeItems)
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


def _window() -> guiwins_newphone.NewPhoneWindow:
    return _built["window"]


def _shown(user: User) -> list[str]:
    return [element.text for element in user.find(kind=ui.label).elements]


def _box(user: User, text: str) -> ui.checkbox:
    return next(box for box in user.find(kind=ui.checkbox).elements if box.text.startswith(text))  # type: ignore[return-value]


def _press(user: User, label: str) -> None:
    UserInteraction(user, {b for b in user.find(kind=ui.button).elements if b.text == label}, None).click()


@pytest.mark.asyncio
async def test_every_group_is_drawn_with_how_many_of_it_are_done() -> None:
    async with _open() as user:
        shown = _shown(user)

        assert "Plugins to install (0/1)" in shown
        assert "Apps to install (0/1)" in shown
        assert "Special access to grant (0/1)" in shown
        assert "Global variables to enter (0/2)" in shown
        assert "Profiles to enable (0/1)" in shown
        assert "0/6 done" in shown


@pytest.mark.asyncio
async def test_ticking_a_box_counts_it_and_saves_it_at_once() -> None:
    async with _open() as user:
        _box(user, "Dawn").set_value(True)
        await asyncio.sleep(0)

        assert "Profiles to enable (1/1)" in _shown(user)
        assert "1/6 done" in _shown(user)
        assert newphone.load_ticks().keys == {"profile:Dawn"}


@pytest.mark.asyncio
async def test_a_tick_is_there_when_the_window_is_opened_again() -> None:
    newphone.save_ticks(newphone.TickBook(keys={"profile:Dawn"}))
    async with _open() as user:
        assert _box(user, "Dawn").value is True
        assert "1/6 done" in _shown(user)


@pytest.mark.asyncio
async def test_what_the_phone_lacks_is_flagged_in_red() -> None:
    appinv.store_fetched_apps(PHONE, [appinv.AppEntry(pkg="com.joaomgcd.autoinput", label="", cls="")])
    async with _open() as user:
        badges = {badge.text for badge in user.find(kind=ui.badge).elements}

        assert badges == {"On the phone", "Not on the phone"}
        assert _window().device == PHONE


@pytest.mark.asyncio
async def test_picking_no_phone_takes_the_flags_away() -> None:
    appinv.store_fetched_apps(PHONE, [appinv.AppEntry(pkg="com.example.music", label="", cls="")])
    async with _open() as user:
        _window().pick("")
        await asyncio.sleep(0)

        await user.should_not_see(kind=ui.badge)


@pytest.mark.asyncio
async def test_a_profile_is_a_link_that_jumps_to_it_in_the_map() -> None:
    async with _open() as user:
        link = next(element for element in user.find(kind=ui.link).elements if element.text == "Show in Map")

        UserInteraction(user, {link}, None).click()
        await asyncio.sleep(0.05)

        assert [target.name for target in _built["jumps"]] == ["Dawn"]


@pytest.mark.asyncio
async def test_the_commands_are_shown_to_copy() -> None:
    async with _open() as user:
        assert any(text.startswith("adb shell pm grant") for text in _shown(user))


@pytest.mark.asyncio
async def test_hiding_values_hides_them_on_screen() -> None:
    async with _open() as user:
        assert "Value: s3cret" in _shown(user)

        _window().set_show_values(False)
        await asyncio.sleep(0)

        assert "Value: s3cret" not in _shown(user)


@pytest.mark.asyncio
async def test_only_what_is_left_leaves_out_what_is_ticked() -> None:
    newphone.save_ticks(newphone.TickBook(keys={"profile:Dawn"}))
    async with _open() as user:
        _window().set_only_left(True)
        await asyncio.sleep(0)

        assert not [box for box in user.find(kind=ui.checkbox).elements if box.text.startswith("Dawn")]
        assert "Profiles to enable (1/1)" in _shown(user)


@pytest.mark.asyncio
async def test_clear_ticks_starts_again_and_saves_that() -> None:
    newphone.save_ticks(newphone.TickBook(keys={"profile:Dawn"}))
    async with _open() as user:
        _press(user, "Clear ticks")
        await asyncio.sleep(0)

        assert "0/6 done" in _shown(user)
        assert newphone.load_ticks().keys == set()


@pytest.mark.asyncio
async def test_copy_as_text_puts_the_checklist_on_the_clipboard(monkeypatch: pytest.MonkeyPatch) -> None:
    copied: list[str] = []
    monkeypatch.setattr(ui.clipboard, "write", copied.append)
    async with _open() as user:
        _press(user, "Copy as text")

        assert copied
        assert "[ ] Dawn" in copied[0]
        assert user.notify.contains("Copied.")


@pytest.mark.asyncio
async def test_save_report_says_where_the_report_went(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(newphone, "write_report", lambda *args, **kwargs: "/out/MapTasker_NewPhone_Checklist.txt")
    async with _open() as user:
        _press(user, "Save Report")

        assert user.notify.contains("Report saved as")


@pytest.mark.asyncio
async def test_save_report_says_when_it_could_not(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(newphone, "write_report", lambda *args, **kwargs: "")
    async with _open() as user:
        _press(user, "Save Report")

        assert user.notify.contains("could not be saved")


@pytest.mark.asyncio
async def test_with_no_file_loaded_it_still_opens_and_says_what_is_missing() -> None:
    PrimeItems.xml_root = None  # type: ignore[assignment]
    async with _open() as user:
        assert "No XML file has been loaded.  Get an XML file first." in _shown(user)
        assert "0/0 done" in _shown(user)


@pytest.mark.asyncio
async def test_the_copy_button_beside_a_command_copies_that_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """NiceGUI hands a click handler its event as the first argument, so the text must not be a bare default."""
    copied: list[str] = []
    monkeypatch.setattr(ui.clipboard, "write", copied.append)
    async with _open() as user:
        buttons = [
            button for button in user.find(kind=ui.button).elements if button.props.get("icon") == "content_copy"
        ]
        assert len(buttons) == 3  # one command, two values (a set, so in no particular order)

        for button in buttons:
            UserInteraction(user, {button}, None).click()

        command = newphone.build(PrimeItems).groups[2].items[0].commands[0]
        assert sorted(copied) == sorted([command, "Berlin", "s3cret"])
