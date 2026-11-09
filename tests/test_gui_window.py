"""The MapTasker window, built for real (GUI) Unit Tests

The rest of the suite tests the GUI's handlers against a MagicMock standing in for MyGui.
These build the real thing: MyGui() inside NiceGUI's in-process user simulation
(nicegui.testing.user_simulation), just as rungui's "/" page does, then open the page, look
at what is on it and press what a user would press.  No browser and no server.

Two things every test here relies on:

  * The page is built by _build_window, a function of this module.  user_simulation removes
    the module of every page function from sys.modules when it closes, unless that module's
    name starts with 'tests.' -- handing it MyGui itself would evict maptasker.src.gui.userintr
    and its parent packages, and every later test would import a second copy of PrimeItems.
  * Each window starts in a directory of its own, with a fresh run's arguments and no loaded
    backup.  MyGui() reads the settings file, the changelog and the AI error files from the
    current directory, and writes the once-a-day version check's marker there.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

import pytest
from maptasker.src.core.colrmode import set_color_mode
from maptasker.src.core.config import DEFAULT_DISPLAY_DETAIL_LEVEL
from maptasker.src.core.getputer import save_restore_args
from maptasker.src.core.initparg import initialize_runtime_arguments
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.core.sysconst import ARGUMENTS_FILE
from nicegui import core, ui
from nicegui.testing.user import User
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

from tests.doubles import required
from tests.shared_fixtures import _built

if TYPE_CHECKING:
    from maptasker.src.gui.userintr import MyGui

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("fresh_session")]


def _build_window() -> None:
    """The "/" page: the real window, kept where the test can reach it."""
    from maptasker.src.gui.userintr import MyGui

    _built["gui"] = MyGui(PrimeItems)


@contextlib.asynccontextmanager
async def _open_window() -> AsyncIterator[tuple[User, MyGui]]:
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


def _button(user: User, label: str) -> ui.button:
    """The one button labelled exactly `label` -- "Save" alone would match every Save button."""
    (button,) = [element for element in user.find(kind=ui.button).elements if element.text == label]
    return button


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
    errors = [
        f"{record.name}: {record.getMessage()}"
        for record in caplog.get_records("call")
        if record.levelno >= logging.ERROR
    ]
    assert not errors, errors


async def test_the_window_opens_with_its_tabs_and_main_buttons(caplog: pytest.LogCaptureFixture) -> None:
    """Everything the first screen offers is there, built by the real window."""
    async with _open_window() as (user, gui):
        for tab in ("Specific Name", "Colors", "Analyze", "Assistance"):
            await user.should_see(kind=ui.tab, content=tab)
        for button in (
            "Get Local XML File",
            "Get XML from Android Device",
            "Map",
            "Diagram",
            "Tree",
            "Reset Options",
            "Exit",
        ):
            await user.should_see(kind=ui.button, content=button)
        # The Application Settings pair, matched exactly: their labels are substrings of others.
        _button(user, "Save")
        _button(user, "Restore")
        await user.should_see("Display Options")
        assert PrimeItems.mygui is gui
    _no_errors_logged(caplog)


async def test_with_no_settings_file_the_window_opens_on_the_runs_starting_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No settings file is not an error: the window comes up on the arguments the run started with."""
    starting_level = PrimeItems.program_arguments.display_detail_level

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
    save_restore_args(saved, set_color_mode("Dark"), to_save=True, state=PrimeItems)

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


async def test_choosing_an_indentation_changes_it(caplog: pytest.LogCaptureFixture) -> None:
    """The pulldown hands its handler an event, not the text.  The handler took int() of the event,
    which raised, so choosing an indentation was logged as an error and changed nothing."""
    async with _open_window() as (_user, gui):
        assert gui.indent == 4

        gui.indent_option.set_value("7")
        for _ in range(40):
            if gui.indent == 7:
                break
            await asyncio.sleep(0.05)

        assert gui.indent == 7
    _no_errors_logged(caplog)


async def test_save_settings_writes_what_the_window_shows(tmp_path, caplog: pytest.LogCaptureFixture) -> None:
    """Pressing Save (Application Settings) puts the window's choices in the settings file, and says so."""
    async with _open_window() as (user, gui):
        _click(user, _checkbox(user, "Italicize"))
        assert gui.italicize is True

        _click(user, _button(user, "Save"))

        assert user.notify.contains("Settings saved."), user.notify.messages

    assert (tmp_path / ARGUMENTS_FILE).exists()
    restored, _colors = save_restore_args({}, {}, to_save=False, state=PrimeItems)
    assert restored["italicize"] is True
    assert restored["bold"] is False
    _no_errors_logged(caplog)


async def test_reset_options_puts_the_controls_back_to_their_defaults(caplog: pytest.LogCaptureFixture) -> None:
    """Reset rebuilds the window from defaulted settings, so every control shows its default again."""
    async with _open_window() as (user, gui):
        _click(user, _checkbox(user, "Bold"))
        with required(user.client):
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


# ##################################################################################
# Opening on a settings file nobody wrote by hand -- or did, wrongly
#
# The window reads MapTasker_Settings.toml as it comes up.  Everything else that reads an outside file is fuzzed;
# this is the file that is read on every start, and the one that, when it was wrong, kept the window from opening
# at all (an empty [colors_to_use] ended in make_hex_color(None)).  An empty colour table is not even wrong: the GUI
# saves only the colours the user changed, so none is "all the defaults", and the window says so.
# ##################################################################################
_SETTINGS = {
    "empty file": b"",
    "only the guidance": b'Guidance = "Modify this file as needed."\n',
    "no colours": b"[program_arguments]\nbold = true\ndebug = false\n",
    "an empty colour table": b"[program_arguments]\nbold = true\ndebug = false\n\n[colors_to_use]\n",
    "some of the colours": b'[program_arguments]\nbold = true\ndebug = false\n\n[colors_to_use]\nproject_color = "Red"\n',
    "no program arguments": b'[colors_to_use]\nbackground_color = "Black"\n',
    "no debug setting": b"[program_arguments]\nbold = true\n\n[colors_to_use]\n",
    "settings of an older version": (
        b"[program_arguments]\nbold = true\ndebug = false\nicon_alignement = true\nsome_future_setting = 3\n"
    ),
    "values of the wrong kind": (
        b'[program_arguments]\nbold = "yes"\ndebug = false\nindent = "wide"\ndisplay_detail_level = "all"\n'
        b'view_limit = "lots"\nnotify_timeout = -5\nprofiles_per_line = 0\n'
    ),
    "a colour that is not a colour": b"[program_arguments]\ndebug = false\n\n[colors_to_use]\nbackground_color = 7\n",
    "a language that is not offered": b'[program_arguments]\ndebug = false\nlanguage = "Klingon"\n',
    "an appearance that is not offered": b'[program_arguments]\ndebug = false\nappearance_mode = "sepia"\n',
    "a last run that is not a date": b'[program_arguments]\ndebug = false\n\nlast_run = "yesterday"\n',
    "text that is not TOML": b"this is not = = a settings file\n[\n",
    "bytes that are not text": b"[program_arguments]\nbold = \xff\xfe\n",
    "a byte-order mark": b"\xef\xbb\xbf[program_arguments]\nbold = true\ndebug = false\n",
}


# The files with no [program_arguments] table say so in the log, as an error, on purpose: the settings that would have
# been restored are not there, and a hand-edited file is the likeliest reason.
_SAID_SO = "No [program_arguments] found"
_SAYS_SO = {"empty file", "only the guidance", "no program arguments"}


@pytest.mark.parametrize("name", list(_SETTINGS))
async def test_the_window_opens_on_any_settings_file(name: str, tmp_path, caplog: pytest.LogCaptureFixture) -> None:
    """Whatever the file holds, the window comes up, with its controls, and nothing is logged as an error."""
    (tmp_path / ARGUMENTS_FILE).write_bytes(_SETTINGS[name])

    async with _open_window() as (user, gui):
        await user.should_see(kind=ui.button, content="Reset Options")
        assert PrimeItems.mygui is gui
        _checkbox(user, "Bold")
    errors = [r.getMessage() for r in caplog.get_records("call") if r.levelno >= logging.ERROR]
    assert len(errors) == (name in _SAYS_SO), errors
    if name in _SAYS_SO:
        assert _SAID_SO in errors[0]


async def test_a_settings_file_without_a_debug_setting_still_restores_the_rest(tmp_path) -> None:
    """The missing key was read as a missing table, so every other saved setting was thrown away with it."""
    (tmp_path / ARGUMENTS_FILE).write_bytes(_SETTINGS["no debug setting"])

    async with _open_window() as (user, gui):
        assert gui.bold is True
        assert _checkbox(user, "Bold").value is True


async def test_a_setting_of_the_wrong_kind_is_left_as_it_was_and_the_rest_is_restored(tmp_path) -> None:
    """'indent = "wide"' raised out of the restore, so the window never opened."""
    (tmp_path / ARGUMENTS_FILE).write_bytes(b'[program_arguments]\ndebug = false\nindent = "wide"\nunderline = true\n')

    async with _open_window() as (user, gui):
        assert gui.indent == 4
        assert gui.underline is True
        assert _checkbox(user, "Underline").value is True


async def test_a_file_with_one_changed_colour_leaves_every_other_colour_as_the_mode_has_it(tmp_path) -> None:
    """The GUI saves only the colours that were changed.  Restoring such a file used to find the rest "missing" and
    set every one of them to turquoise, with a message for each."""
    (tmp_path / ARGUMENTS_FILE).write_bytes(
        b'[program_arguments]\nappearance_mode = "light"\ndebug = false\n\n[colors_to_use]\nproject_color = "Red"\n'
    )

    async with _open_window() as (user, gui):
        light = set_color_mode("light")
        assert gui.color_lookup == {**light, "project_color": "Red"}
        assert not user.notify.contains("missing"), user.notify.messages
        assert "turquoise" not in gui.color_lookup.values()
        assert not user.notify.contains("Colors set to defaults.")


async def test_a_file_with_no_colours_restores_its_settings_and_says_the_colours_are_the_defaults(tmp_path) -> None:
    """The GUI saves only the colours that were changed, so an empty table is a file saved with none."""
    (tmp_path / ARGUMENTS_FILE).write_bytes(_SETTINGS["an empty colour table"])

    async with _open_window() as (user, gui):
        assert gui.bold is True
        assert user.notify.contains("Colors set to defaults."), user.notify.messages
        assert not user.notify.contains("No settings file found.")
