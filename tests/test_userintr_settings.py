"""The settings handlers: what each control does to the window's settings, and what it says.

SettingsEventHandlers is a mixin; here it is given a MagicMock for the window and a RunState of
its own, the way test_clireports and the other handler tests stand a window in.  The one thing
to know about a MagicMock window is that every attribute exists and is truthy -- so the lock the
handlers use against NiceGUI's change echoes, ``is_updating``, is set explicitly, and a
handler that reads an attribute the real window has not got would not fail here, which is what
test_gui_window's real-window tests are for.

What is asserted is the handlers' own logic: the value taken from an event or a label, the
fallback for something unrecognised, the lock being taken and always let go, and the message
the user is shown.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from maptasker.src import userintr_settings
from maptasker.src.config import DEFAULT_DISPLAY_DETAIL_LEVEL
from maptasker.src.primitem import RunState
from maptasker.src.sysconst import NOTIFY_TIMEOUT_DEFAULT, VIEW_LIMIT_DEFAULT
from maptasker.src.userintr_settings import SettingsEventHandlers


class _Handlers(SettingsEventHandlers):
    """The mixin on its own, holding the window and the run the way MapTaskerEventHandlers does."""

    def __init__(self, gui: MagicMock, state: RunState) -> None:
        self.gui = gui
        self.state = state


@pytest.fixture
def gui() -> MagicMock:
    """A window that is not in the middle of an update, whatever else it is asked."""
    window = MagicMock()
    window.is_updating = False
    return window


@pytest.fixture
def handlers(gui: MagicMock) -> _Handlers:
    """The handlers over that window and a RunState of their own."""
    handlers = _Handlers(gui, RunState())
    gui.event_handlers = handlers
    return handlers


def _said(gui: MagicMock) -> list[tuple[str, str]]:
    """(text, colour) of every message box the handler put up."""
    return [call.args for call in gui.display_message_box.call_args_list]


# ##################################################################################
# The tick boxes: read the box, say so, keep the answer
# ##################################################################################
_CHECKBOXES = [
    ("names_bold_event", "bold_checkbox", "Display Names in Bold", "bold", False),
    ("names_highlight_event", "highlight_checkbox", "Display Names Highlighted", "highlight", False),
    ("names_italicize_event", "italicize_checkbox", "Display Names Italicized", "italicize", False),
    ("names_underline_event", "underline_checkbox", "Display Names Underlined", "underline", False),
    ("taskernet_event", "taskernet_checkbox", "Display TaskerNet Information", "taskernet", False),
    ("pretty_event", "pretty_checkbox", "Display Pretty Output", "pretty", True),
    ("condition_event", "conditions_checkbox", "Display Profile and Task Action Conditions", "conditions", True),
    ("preferences_event", "preferences_checkbox", "Display Tasker Preferences", "preferences", True),
    ("directory_event", "directory_checkbox", "Display Directory", "directory", True),
]


@pytest.mark.parametrize(("handler", "checkbox", "message", "setting", "flags_event"), _CHECKBOXES)
@pytest.mark.parametrize("ticked", [True, False])
def test_a_tick_box_is_read_announced_and_kept(
    handlers: _Handlers,
    gui: MagicMock,
    handler: str,
    checkbox: str,
    message: str,
    setting: str,
    flags_event: bool,
    ticked: bool,
) -> None:
    """The setting follows the box, and the message names the option -- for every box on the panel."""
    gui.get_input_and_put_message.return_value = ticked
    gui.event = False

    getattr(handlers, handler)()

    gui.get_input_and_put_message.assert_called_once_with(getattr(gui, checkbox), message)
    assert getattr(gui, setting) is ticked
    assert gui.event is flags_event


# ##################################################################################
# Detail level
# ##################################################################################
@pytest.mark.parametrize("given", [4, "4", SimpleNamespace(value="4")])
def test_the_detail_level_is_always_an_int_whatever_it_arrives_as(
    handlers: _Handlers,
    gui: MagicMock,
    given: object,
) -> None:
    """A pulldown event, a restored string and an int all leave the same int -- the settings file reads it back."""
    handlers.detail_selected_event(given)
    assert gui.display_detail_level == 4
    assert gui.sidebar_detail_option.value == "4"
    assert gui.is_updating is False


def test_a_level_nobody_can_convert_leaves_the_current_one(handlers: _Handlers, gui: MagicMock) -> None:
    """An empty pulldown must not replace a number with something no comparison can take."""
    gui.display_detail_level = 3
    handlers.detail_selected_event(SimpleNamespace(value=""))
    assert gui.display_detail_level == 3


def test_a_detail_change_made_by_the_program_is_not_handled_twice(handlers: _Handlers, gui: MagicMock) -> None:
    """Setting the pulldown's value sends an event back; the lock is what stops the loop."""
    gui.is_updating = True
    gui.display_detail_level = 3
    handlers.detail_selected_event(5)
    assert gui.display_detail_level == 3


def test_everything_ticks_every_option_and_resets_the_level(handlers: _Handlers, gui: MagicMock) -> None:
    """One box that turns the rest on: each is ticked, set, and the detail level goes to its default."""
    gui.everything_checkbox.value = True
    boxes = {
        name: MagicMock()
        for name in (
            "conditions_checkbox",
            "directory_checkbox",
            "outline_checkbox",
            "preferences_checkbox",
            "pretty_checkbox",
            "runtime_checkbox",
            "taskernet_checkbox",
            "list_unnamed_items_checkbox",
        )
    }
    for name, box in boxes.items():
        setattr(gui, name, box)

    handlers.everything_event()

    for name, box in boxes.items():
        box.set_value.assert_called_once_with(True)
        assert getattr(gui, name.replace("_checkbox", "")) is True
    assert gui.everything is True
    assert gui.display_detail_level == DEFAULT_DISPLAY_DETAIL_LEVEL
    assert gui.sidebar_detail_option.value == str(DEFAULT_DISPLAY_DETAIL_LEVEL)
    assert _said(gui)[-1] == ("Everything toggled on successfully", "Green")


def test_everything_off_says_so(handlers: _Handlers, gui: MagicMock) -> None:
    """The same box turns them off, and the message follows it."""
    gui.everything_checkbox.value = False
    handlers.everything_event()
    assert _said(gui)[-1] == ("Everything toggled off successfully", "Green")


# ##################################################################################
# The twisty
# ##################################################################################
def test_a_twisty_at_a_low_detail_level_raises_the_level_to_three(handlers: _Handlers, gui: MagicMock) -> None:
    """Hidden details need details: below 3 there is nothing under the twisty."""
    gui.get_input_and_put_message.return_value = True
    gui.display_detail_level = 1
    gui.everything = False

    handlers.twisty_event()

    assert gui.display_detail_level == 3
    assert handlers.state.program_arguments.display_detail_level == 3
    assert gui.sidebar_detail_option.value == "3"
    assert _said(gui)[0][1] == "Red"
    assert gui.twisty is True


def test_a_twisty_and_everything_cannot_both_be_on(handlers: _Handlers, gui: MagicMock) -> None:
    """The twisty gives way, and the box is unticked on screen as well as in the setting."""
    gui.get_input_and_put_message.return_value = True
    gui.display_detail_level = 5
    gui.everything = True

    handlers.twisty_event()

    assert gui.twisty is False
    gui.twisty_checkbox.set_value.assert_called_once_with(False)
    assert "mutually exclusive" in _said(gui)[-1][0]


def test_a_twisty_at_a_sensible_level_says_nothing_more(handlers: _Handlers, gui: MagicMock) -> None:
    """The ordinary case: ticked, kept, no warning."""
    gui.get_input_and_put_message.return_value = True
    gui.display_detail_level = 5
    gui.everything = False
    handlers.twisty_event()
    assert gui.twisty is True
    assert _said(gui) == []


# ##################################################################################
# Font, indent, limits
# ##################################################################################
def test_a_font_is_taken_from_an_event_kept_and_shown(handlers: _Handlers, gui: MagicMock) -> None:
    """The setting, the pulldown (without echoing back), the label on the toolbar, and the message."""
    gui.font_optionmenu.value = "Courier"
    handlers.font_event(SimpleNamespace(value="Monaco"))

    assert gui.font == "Monaco"
    assert gui.font_optionmenu.value == "Monaco"
    assert gui.is_updating is False
    assert gui.font_out_label.text == "Monospaced Font To Use: Monaco"
    assert _said(gui) == [("Font To Use set to Monaco", "Green")]


@pytest.mark.parametrize("given", ["", SimpleNamespace(value="")])
def test_an_empty_font_choice_changes_nothing(handlers: _Handlers, gui: MagicMock, given: object) -> None:
    """An empty selection is what a pulldown sends when it is cleared."""
    gui.font = "Monaco"
    handlers.font_event(given)
    assert gui.font == "Monaco"
    assert _said(gui) == []


def test_a_font_change_made_by_the_program_is_ignored(handlers: _Handlers, gui: MagicMock) -> None:
    """The lock again."""
    gui.is_updating = True
    gui.font = "Monaco"
    handlers.font_event("Courier")
    assert gui.font == "Monaco"


def test_the_font_label_is_not_built_when_there_is_nowhere_to_put_it(handlers: _Handlers) -> None:
    """A window with no toolbar yet is not an error."""
    bare = SimpleNamespace(font_out_label=None, gui_view_toolbar=None)
    handlers._update_font_labels(bare, "Monaco")  # noqa: SLF001
    assert bare.font_out_label is None


def test_the_indent_is_kept_as_a_number_and_shown_as_text(handlers: _Handlers, gui: MagicMock) -> None:
    """The setting is compared as a number; the pulldown's options are strings."""
    handlers.indent_selected_event("6")
    assert gui.indent == 6
    assert gui.indent_option.value == "6"
    assert _said(gui) == [("Indentation Amount set to 6", "green")]
    assert gui.is_updating is False


def test_the_task_action_limit_follows_the_slider_and_labels_itself(handlers: _Handlers, gui: MagicMock) -> None:
    """From an event or a bare number, to the setting, the label and the knob."""
    handlers.tasklimit_event(SimpleNamespace(value=45))
    assert gui.task_action_warning_limit == 45
    assert gui.task_action_label.text == "Task Action Limit: 45"
    assert gui.task_action_limit.value == 45
    assert gui.is_updating is False

    handlers.tasklimit_event(60)
    assert gui.task_action_warning_limit == 60


# ##################################################################################
# Notification duration
# ##################################################################################
@pytest.fixture
def timeout_set(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """The notification durations the window was told to use."""
    seen: list[int] = []
    monkeypatch.setattr(userintr_settings, "set_notification_timeout", seen.append)
    return seen


def test_a_duration_chosen_by_its_label_becomes_milliseconds(
    handlers: _Handlers,
    gui: MagicMock,
    timeout_set: list[int],
) -> None:
    """The pulldown sends its label."""
    label, milliseconds = userintr_settings.NOTIFY_TIMEOUT_CHOICES[-1]
    said = handlers.notify_timeout_event(SimpleNamespace(value=label))
    assert gui.notify_timeout == milliseconds
    assert timeout_set == [milliseconds]
    assert said.startswith("Notification Duration set to")


def test_a_saved_duration_restores_in_milliseconds(
    handlers: _Handlers,
    gui: MagicMock,
    timeout_set: list[int],
) -> None:
    """The settings file holds the number."""
    milliseconds = userintr_settings.NOTIFY_TIMEOUT_CHOICES[0][1]
    handlers.notify_timeout_event(milliseconds)
    assert gui.notify_timeout == milliseconds


@pytest.mark.parametrize("garbage", ["whenever", None, 123456789, "-1"])
def test_an_unrecognised_duration_falls_back_to_the_default_not_to_never(
    handlers: _Handlers,
    gui: MagicMock,
    timeout_set: list[int],
    garbage: object,
) -> None:
    """A bad value must not silently make every message in the app one that never goes away."""
    handlers.notify_timeout_event(garbage)
    assert gui.notify_timeout == NOTIFY_TIMEOUT_DEFAULT
    assert timeout_set == [NOTIFY_TIMEOUT_DEFAULT]


def test_a_duration_change_made_by_the_program_is_ignored(
    handlers: _Handlers,
    gui: MagicMock,
    timeout_set: list[int],
) -> None:
    """The lock; and it answers nothing, since there is nothing to announce."""
    gui.is_updating = True
    assert handlers.notify_timeout_event(10000) is None
    assert timeout_set == []


# ##################################################################################
# View limit
# ##################################################################################
@pytest.fixture(autouse=True)
def _no_page_update(monkeypatch: pytest.MonkeyPatch) -> None:
    """ui.update() needs a page; the handlers call it after a change and there is none here."""
    monkeypatch.setattr(userintr_settings.ui, "update", lambda *_args: None)


@pytest.mark.parametrize("given", ["9999999", "Unlimited"])
def test_unlimited_is_a_very_large_number_and_shown_as_a_word(
    handlers: _Handlers,
    gui: MagicMock,
    given: str,
) -> None:
    """Both spellings of it, the number the settings hold and the word the pulldown shows."""
    handlers.viewlimit_event(given)
    assert gui.view_limit == 9999999
    assert gui.viewlimit_optionmenu.value == "Unlimited"
    assert _said(gui) == [("View Limit set to Unlimited.", "Green")]


def test_a_numeric_limit_is_kept_as_a_number(handlers: _Handlers, gui: MagicMock) -> None:
    """The pulldown's strings, the setting's int."""
    handlers.viewlimit_event(SimpleNamespace(value="250"))
    assert gui.view_limit == 250
    assert gui.viewlimit_optionmenu.value == "250"
    assert gui.is_updating is False


def test_a_limit_that_is_not_a_number_falls_back_to_the_default(handlers: _Handlers, gui: MagicMock) -> None:
    """Nothing is left half-set."""
    handlers.viewlimit_event("lots")
    assert gui.view_limit == VIEW_LIMIT_DEFAULT


# ##################################################################################
# Language
# ##################################################################################
def test_choosing_the_language_already_in_use_does_nothing_more(handlers: _Handlers, gui: MagicMock) -> None:
    """No rebuild of the window for a choice that changes nothing."""
    gui.language = "English"
    handlers.language_set_event = MagicMock()
    handlers.language_selected_event("English")
    handlers.language_set_event.assert_not_called()
    assert handlers.state.language_set is True


def test_choosing_another_language_switches_it_and_schedules_a_rebuild(
    handlers: _Handlers,
    gui: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The switch first, then the window rebuilt from outside the drawer this event fired in."""
    gui.language = "English"
    timers: list = []
    monkeypatch.setattr(userintr_settings.ui, "timer", lambda *args, **kwargs: timers.append((args, kwargs)))
    handlers.language_set_event = MagicMock()

    handlers.language_selected_event(SimpleNamespace(value=" French "))

    handlers.language_set_event.assert_called_once_with("French")
    assert gui.displaying_extended_list is None
    assert gui.aimodel_extend_checkbox.value is False
    assert gui.is_updating is False
    [(args, kwargs)] = timers
    assert args[0] == 0.01
    assert kwargs == {"once": True}


# ##################################################################################
# Output folder
# ##################################################################################
@pytest.fixture
def folder_saved(monkeypatch: pytest.MonkeyPatch) -> list:
    """Settings the handler remembered and wrote, without touching a real settings file."""
    saved: list = []
    monkeypatch.setattr(userintr_settings, "remember_setting", lambda gui, name, value: saved.append((name, value)))
    monkeypatch.setattr(userintr_settings, "save_restore_args", lambda *_args, **_kwargs: saved.append("written"))
    return saved


def test_a_new_output_folder_is_made_remembered_saved_and_announced(
    handlers: _Handlers,
    gui: MagicMock,
    folder_saved: list,
    tmp_path: object,
) -> None:
    """A folder that does not exist yet is made, stored absolute, and written to the settings at once."""
    gui.output_directory = ""
    target = tmp_path / "reports"

    handlers.output_directory_event(str(target))

    assert target.is_dir()
    assert folder_saved == [("output_directory", str(target.resolve())), "written"]
    assert _said(gui)[0][1] == "Green"
    assert "Output Folder set to" in _said(gui)[0][0]


def test_the_same_folder_again_changes_nothing(handlers: _Handlers, gui: MagicMock, folder_saved: list) -> None:
    """Leaving the box without editing it is not a change to announce."""
    gui.output_directory = ""
    handlers.output_directory_event("")
    assert folder_saved == []
    assert _said(gui) == []


def test_a_folder_that_cannot_be_used_is_refused_with_the_reason(
    handlers: _Handlers,
    gui: MagicMock,
    folder_saved: list,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A typo is caught now, not by the next report landing somewhere else."""
    monkeypatch.setattr(
        userintr_settings, "normalize_output_directory", lambda _text: ("", "Output folder 'x' cannot be used.")
    )
    handlers.output_directory_event("x")
    assert _said(gui) == [("Output folder 'x' cannot be used.", "Red")]
    assert folder_saved == []


def test_a_restored_output_folder_goes_into_its_box(handlers: _Handlers, gui: MagicMock) -> None:
    """And the answer says where output will go."""
    said = handlers.output_directory_restored("/somewhere")
    assert gui.output_directory == "/somewhere"
    assert said.startswith("Output Folder set to")


# ##################################################################################
# Colours
# ##################################################################################
def test_a_colour_is_recorded_for_the_item_and_for_the_run(handlers: _Handlers, gui: MagicMock) -> None:
    """The window's lookup and the run's colours both learn it, under the item's CSS class name."""
    gui.color_lookup = {}
    handlers.state.colors_to_use = {}

    handlers.extract_color_from_event("#ff0000", "Projects")

    key = userintr_settings.TYPES_OF_COLOR_NAMES["Projects"]
    assert gui.color_lookup == {key: "#ff0000"}
    assert handlers.state.colors_to_use == {key: "#ff0000"}


def test_resetting_colours_puts_back_the_modes_own_and_forgets_the_picks(handlers: _Handlers, gui: MagicMock) -> None:
    """Defaults for the appearance mode, the lookup emptied, and the user told."""
    gui.appearance_mode = "dark"
    gui.color_lookup = {"x": "#fff"}
    handlers.color_reset_event()
    assert gui.color_lookup == {}
    assert handlers.state.colors_to_use
    assert _said(gui) == [("Tasker items set back to their default colors.", "Green")]


def test_a_colour_picked_with_no_category_chosen_is_ignored(handlers: _Handlers, gui: MagicMock) -> None:
    """Nothing to colour."""
    gui.color_objects_options = None
    gui.event_handlers.extract_color_from_event = MagicMock()

    handlers.handle_color_pick_event("#ff0000")

    gui.event_handlers.extract_color_from_event.assert_not_called()


# ##################################################################################
# Save and restore
# ##################################################################################
def test_save_writes_the_windows_settings_and_says_so(
    handlers: _Handlers,
    gui: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """What the window shows is what goes to the file, and the colours it hands back are kept."""
    calls: list = []

    def save(settings: object, colors: object, to_save: bool, state: object) -> tuple:
        calls.append((settings, colors, to_save))
        return {}, {"background_color": "#000"}

    monkeypatch.setattr(userintr_settings, "gui_settings", lambda _gui: {"bold": True})
    monkeypatch.setattr(userintr_settings, "save_restore_args", save)
    gui.color_lookup = {}

    handlers.save_settings_event()

    assert calls == [({"bold": True}, {}, True)]
    assert gui.color_lookup == {"background_color": "#000"}
    assert _said(gui) == [("Settings saved.", "Green")]


def _restoring(monkeypatch: pytest.MonkeyPatch, settings: dict, colors: dict) -> None:
    monkeypatch.setattr(
        userintr_settings, "save_restore_args", lambda *_args, **_kwargs: (dict(settings), dict(colors))
    )
    monkeypatch.setattr(userintr_settings, "make_hex_color", lambda color: color)


def test_restoring_with_no_settings_file_says_so(
    handlers: _Handlers,
    gui: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Defaults stay, and the user is told there was nothing to restore."""
    _restoring(monkeypatch, {}, {})
    handlers.restore_settings_event()
    assert ("No settings file found.", "Orange") in _said(gui)
    gui.extract_settings.assert_not_called()


def test_restoring_settings_with_no_colours_says_colours_are_defaults(
    handlers: _Handlers,
    gui: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The settings are applied; the colours were not in the file, and that is said."""
    _restoring(monkeypatch, {"bold": True}, {})
    handlers.restore_settings_event()
    gui.extract_settings.assert_called_once_with({"bold": True})
    assert gui.restore is True
    assert ("Colors set to defaults.", "Green") in _said(gui)


def test_a_settings_file_that_reports_an_error_resets_the_colours_and_stops(
    handlers: _Handlers,
    gui: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The file's own message is shown in red, and nothing half-read is applied."""
    _restoring(monkeypatch, {"msg": "The settings file is damaged."}, {})
    handlers.color_reset_event = MagicMock()

    handlers.restore_settings_event()

    assert _said(gui) == [("The settings file is damaged.", "Red")]
    handlers.color_reset_event.assert_called_once_with()
    gui.extract_settings.assert_not_called()


def test_the_saved_notification_duration_is_in_force_before_the_restore_reports_itself(
    handlers: _Handlers,
    gui: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Otherwise every message in the restore would sit on screen for the default duration."""
    _restoring(monkeypatch, {"notify_timeout": 10000, "bold": True}, {"background_color": "#000"})
    handlers.notify_timeout_event = MagicMock()
    handlers.restore_settings_event()
    handlers.notify_timeout_event.assert_called_once_with(10000)
