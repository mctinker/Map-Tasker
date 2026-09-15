"""The MapTasker window, built for real (GUI) Unit Tests

The rest of the suite tests the GUI's handlers against a MagicMock standing in for MyGui.
These build the real thing: MyGui() inside NiceGUI's in-process user simulation
(nicegui.testing.user_simulation), just as rungui's "/" page does, then open the page, look
at what is on it and press what a user would press.  No browser and no server.

Two things every test here relies on:

  * The page is built by _build_window, a function of this module.  user_simulation removes
    the module of every page function from sys.modules when it closes, unless that module's
    name starts with 'tests.' -- handing it MyGui itself would evict maptasker.src.userintr
    and its parent packages, and every later test would import a second copy of PrimeItems.
  * Each window starts in a directory of its own, with a fresh run's arguments and no loaded
    backup.  MyGui() reads the settings file, the changelog and the AI error files from the
    current directory, and writes the once-a-day version check's marker there.
"""

from __future__ import annotations

import asyncio
import contextlib
import copy
import logging
from collections.abc import AsyncIterator

import pytest
from nicegui import core, ui
from nicegui.testing.user import User
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

from maptasker.src import guiutils, guiwins, primitem
from maptasker.src.colrmode import set_color_mode
from maptasker.src.config import DEFAULT_DISPLAY_DETAIL_LEVEL
from maptasker.src.getputer import save_restore_args
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import ARGUMENTS_FILE

pytestmark = pytest.mark.asyncio

_built: dict = {}


def _build_window() -> None:
    """The "/" page: the real window, kept where the test can reach it."""
    from maptasker.src.userintr import MyGui  # noqa: PLC0415

    _built["gui"] = MyGui()


@pytest.fixture(autouse=True)
def fresh_session(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """A working directory of its own, a fresh run, nothing loaded -- and everything the window
    changes on the way up put back afterwards, so no other test inherits it."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(PrimeItems, "program_arguments", initialize_runtime_arguments())
    for name in primitem.LOADED_CONFIGURATION_ATTRIBUTES:
        monkeypatch.setattr(PrimeItems, name, copy.deepcopy(primitem._RUN_DEFAULTS[name]))  # noqa: SLF001
    monkeypatch.setattr(PrimeItems, "slash", "/")
    monkeypatch.setattr(PrimeItems, "mygui", None)
    monkeypatch.setattr(PrimeItems, "colors_to_use", {})
    monkeypatch.setattr(PrimeItems, "language_set", False)
    monkeypatch.setattr(PrimeItems, "languages_translated", dict(PrimeItems.languages_translated))
    monkeypatch.setitem(guiwins._NOTIFY_TIMEOUT, "ms", guiwins._NOTIFY_TIMEOUT["ms"])  # noqa: SLF001
    # The daily PyPI check is scheduled only on the day's first run; this is never it.
    monkeypatch.setattr(guiutils, "is_first_run_today", lambda *_args, **_kwargs: False)
    had_translator, translator = hasattr(PrimeItems, "_"), getattr(PrimeItems, "_", None)
    _built.clear()
    yield tmp_path
    if had_translator:
        PrimeItems._ = translator
    elif hasattr(PrimeItems, "_"):
        del PrimeItems._


@contextlib.asynccontextmanager
async def _open_window() -> AsyncIterator[tuple[User, object]]:
    """The window, opened by a simulated user: (user, the MyGui behind the page).

    A test that fails inside the window -- or is expected to, like the xfail below -- leaves
    user_simulation's lifespan without its shutdown, so NiceGUI still counts itself started.
    Any later test that builds NiceGUI elements outside a running app (test_scene_properties
    does) is then refused a startup handler, and fails for a reason that has nothing to do
    with it.  So the app is stopped here whatever happened inside.
    """
    try:
        async with user_simulation(root=_build_window) as user:
            await user.open("/")
            yield user, _built["gui"]
    finally:
        if core.app.is_started:
            await core.app.stop()


def _checkbox(user: User, label: str) -> ui.checkbox:
    """The one checkbox labelled exactly `label` -- find() alone matches on a substring."""
    (checkbox,) = [element for element in user.find(kind=ui.checkbox).elements if element.text == label]
    return checkbox


def _click(user: User, element: ui.element) -> None:
    """Press this element, as the user would."""
    UserInteraction(user, {element}, None).click()


async def _wait_for_notification(user: User, message: str) -> None:
    """Wait for a message a short ui.timer puts up -- Reset Options rebuilds the window from one."""
    for _ in range(40):
        if user.notify.contains(message):
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"no {message!r} among {user.notify.messages}")


def _no_errors_logged(caplog: pytest.LogCaptureFixture) -> None:
    errors = [f"{record.name}: {record.getMessage()}" for record in caplog.get_records("call") if record.levelno >= logging.ERROR]
    assert not errors, errors


async def test_the_window_opens_with_its_tabs_and_main_buttons(caplog: pytest.LogCaptureFixture) -> None:
    """Everything the first screen offers is there, built by the real window."""
    async with _open_window() as (user, gui):
        for tab in ("Specific Name", "Colors", "Analyze", "Debug"):
            await user.should_see(kind=ui.tab, content=tab)
        for button in ("Get Local XML File", "Get XML from Android Device", "Map", "Diagram", "Tree", "Save Settings", "Reset Options", "Exit"):
            await user.should_see(kind=ui.button, content=button)
        await user.should_see("Display Options")
        assert PrimeItems.mygui is gui
    _no_errors_logged(caplog)


async def test_with_no_settings_file_the_window_opens_on_the_runs_starting_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No settings file is not an error: the window comes up on the arguments the run started with."""
    starting_level = PrimeItems.program_arguments["display_detail_level"]

    async with _open_window() as (user, gui):
        assert gui.bold is False
        assert _checkbox(user, "Bold").value is False
        assert gui.display_detail_level == starting_level
        assert gui.sidebar_detail_option.value == str(starting_level)
    _no_errors_logged(caplog)


async def test_saved_settings_are_on_screen_when_the_window_opens(caplog: pytest.LogCaptureFixture) -> None:
    """What was saved last time is what the controls show, not just what the program holds."""
    saved = initialize_runtime_arguments()
    saved["bold"] = True
    saved["display_detail_level"] = 5
    save_restore_args(saved, set_color_mode("Dark"), to_save=True)

    async with _open_window() as (user, gui):
        assert gui.bold is True
        assert _checkbox(user, "Bold").value is True
        assert gui.display_detail_level == 5
        assert gui.sidebar_detail_option.value == "5"
        assert not user.notify.contains("No settings file found.")
    _no_errors_logged(caplog)


async def test_ticking_an_option_changes_the_setting(caplog: pytest.LogCaptureFixture) -> None:
    """The checkbox and the setting it stands for move together."""
    async with _open_window() as (user, gui):
        bold = _checkbox(user, "Bold")
        assert bold.value is False
        assert gui.bold is False

        _click(user, bold)

        assert bold.value is True
        assert gui.bold is True
    _no_errors_logged(caplog)


async def test_save_settings_writes_what_the_window_shows(tmp_path, caplog: pytest.LogCaptureFixture) -> None:
    """Pressing Save Settings puts the window's choices in the settings file, and says so."""
    async with _open_window() as (user, gui):
        _click(user, _checkbox(user, "Italicize"))
        assert gui.italicize is True

        user.find(kind=ui.button, content="Save Settings").click()

        assert user.notify.contains("Settings saved."), user.notify.messages

    assert (tmp_path / ARGUMENTS_FILE).exists()
    restored, _colors = save_restore_args({}, {}, to_save=False)
    assert restored["italicize"] is True
    assert restored["bold"] is False
    _no_errors_logged(caplog)


async def test_reset_options_puts_the_controls_back_to_their_defaults(caplog: pytest.LogCaptureFixture) -> None:
    """Reset rebuilds the window from defaulted settings, so every control shows its default again."""
    async with _open_window() as (user, gui):
        _click(user, _checkbox(user, "Bold"))
        with user.client:
            gui.sidebar_detail_option.value = "0"
        assert gui.bold is True
        assert gui.display_detail_level == 0

        user.find(kind=ui.button, content="Reset Options").click()
        await _wait_for_notification(user, "Settings Reset!")

        assert gui.bold is False
        assert _checkbox(user, "Bold").value is False
        assert gui.display_detail_level == DEFAULT_DISPLAY_DETAIL_LEVEL
        assert gui.sidebar_detail_option.value == str(DEFAULT_DISPLAY_DETAIL_LEVEL)
    _no_errors_logged(caplog)


async def test_a_fresh_window_and_reset_options_agree_on_the_detail_level() -> None:
    """'Reset Options' promises the default values; a window that has never been changed is showing them."""
    async with _open_window() as (user, gui):
        opened_at = gui.sidebar_detail_option.value
        assert opened_at == str(DEFAULT_DISPLAY_DETAIL_LEVEL)

        user.find(kind=ui.button, content="Reset Options").click()
        await _wait_for_notification(user, "Settings Reset!")

        assert gui.sidebar_detail_option.value == opened_at
