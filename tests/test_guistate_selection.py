"""What a rebuilt or second window carries into the settings that get saved."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from maptasker.src import guistate
from maptasker.src.guistate import live_selection
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import ARGUMENT_NAMES

SELECTION_NAMES = ("single_project_name", "single_profile_name", "single_task_name", "single_scene_name")


@pytest.fixture
def selection_arguments(monkeypatch: pytest.MonkeyPatch) -> dict:
    """program_arguments with no selection, restored after the test."""
    arguments = dict.fromkeys(SELECTION_NAMES, "")
    monkeypatch.setattr(PrimeItems, "program_arguments", arguments)
    return arguments


def test_task_wins_over_the_profile_and_project_mapping_it_filled_in(selection_arguments: dict) -> None:
    """Mapping a selected Task writes its owning Profile and Project into program_arguments too."""
    selection_arguments.update(
        single_task_name="Remind Me",
        single_profile_name="Morning Reminder",
        single_project_name="Base",
    )
    assert live_selection() == ("Task", "Remind Me")


def test_profile_wins_over_its_project(selection_arguments: dict) -> None:
    """A selected Profile is not replaced by the Project mapping it filled in."""
    selection_arguments.update(single_profile_name="Morning Reminder", single_project_name="Base")
    assert live_selection() == ("Profile", "Morning Reminder")


def test_nothing_selected(selection_arguments: dict) -> None:
    """No selection carries nothing forward."""
    assert live_selection() == ("", "")


def _stale_window(**overrides: object) -> SimpleNamespace:
    """A MyGui stand-in holding every setting, as a window built earlier in the session would."""
    settings = {**dict.fromkeys(ARGUMENT_NAMES, ""), **initialize_runtime_arguments(), **overrides}
    return SimpleNamespace(**settings, color_lookup={})


@pytest.fixture
def fresh_remembered(monkeypatch: pytest.MonkeyPatch) -> None:
    """program_arguments at their defaults, and nothing remembered yet."""
    monkeypatch.setattr(PrimeItems, "program_arguments", initialize_runtime_arguments())
    monkeypatch.setattr(guistate, "_remembered_settings", set())


@pytest.mark.usefixtures("fresh_remembered")
def test_address_set_in_one_window_survives_a_save_read_from_another() -> None:
    """Two browser tabs: the address is entered in one, the exit save reads the other."""
    used_window = _stale_window()
    other_window = _stale_window(android_last_ipaddr="192.168.0.77")

    guistate.remember_setting(used_window, "android_last_ipaddr", "10.1.2.3")

    assert guistate.gui_settings(other_window)["android_last_ipaddr"] == "10.1.2.3"
    guistate.capture_gui_state(other_window, {})
    assert PrimeItems.program_arguments["android_last_ipaddr"] == "10.1.2.3"
    assert other_window.android_last_ipaddr == "10.1.2.3"


@pytest.mark.usefixtures("fresh_remembered")
def test_settings_not_remembered_still_come_from_the_window() -> None:
    """Only remember_setting's values are put back; everything else is read off the window."""
    guistate.remember_setting(_stale_window(), "android_last_ipaddr", "10.1.2.3")
    assert guistate.gui_settings(_stale_window(bold=True))["bold"] is True
