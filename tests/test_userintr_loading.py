"""Choosing the one Project, Profile, Task or Scene to show, and where the file picker opens."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from maptasker.src.core.sysconst import ALL_OBJECTS_MESSAGE
from maptasker.src.gui import userintr_loading
from maptasker.src.gui.userintr_loading import LoadingEventHandlers


# ##################################################################################
# Where the file picker opens
# ##################################################################################
def _remembering(directory: str = "", saved: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        local_xml_directory=directory,
        state=SimpleNamespace(program_arguments=SimpleNamespace(local_xml_directory=saved)),
    )


def test_the_picker_opens_where_the_last_file_came_from(tmp_path: Path) -> None:
    assert userintr_loading.local_xml_start_directory(_remembering(str(tmp_path))) == str(tmp_path)


def test_the_saved_setting_is_used_when_this_session_has_not_picked_yet(tmp_path: Path) -> None:
    assert userintr_loading.local_xml_start_directory(_remembering("", str(tmp_path))) == str(tmp_path)


def test_a_directory_that_is_gone_falls_back_to_home(tmp_path: Path) -> None:
    """Renamed, deleted, or on a drive that is not mounted any more."""
    assert userintr_loading.local_xml_start_directory(_remembering(str(tmp_path / "gone"))) == "~"


def test_nothing_remembered_means_home() -> None:
    assert userintr_loading.local_xml_start_directory(_remembering()) == "~"


def test_a_picked_file_makes_its_folder_the_next_starting_point(monkeypatch: pytest.MonkeyPatch) -> None:
    remembered: list[tuple] = []
    monkeypatch.setattr(userintr_loading, "remember_setting", lambda gui, name, value: remembered.append((name, value)))
    folder = Path("home", "me", "backups")  # Built, not typed, so it has this machine's separators.
    userintr_loading.remember_local_xml_directory(object(), str(folder / "backup.xml"))
    assert remembered == [("local_xml_directory", str(folder))]


def test_no_file_picked_remembers_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(userintr_loading, "remember_setting", lambda *_a: pytest.fail("nothing was picked"))
    userintr_loading.remember_local_xml_directory(object(), "")


# ##################################################################################
# The line saying what is on display
# ##################################################################################
@pytest.fixture(autouse=True)
def _untranslated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(userintr_loading, "translate_string", lambda text: text)


def test_a_selection_is_summarised_by_name() -> None:
    said = userintr_loading._single_item_selection_message(SimpleNamespace(), "Task", "Wake Up")
    assert said == "Display only Task 'Wake Up'."


def test_clearing_the_only_selection_says_everything_is_shown() -> None:
    gui = SimpleNamespace(single_project_name="", single_profile_name="", single_task_name="", single_scene_name="")
    assert userintr_loading._single_item_selection_message(gui, "Task", "None") == ALL_OBJECTS_MESSAGE


def test_clearing_one_selection_while_another_is_still_set_reports_the_other() -> None:
    """The four are meant to be exclusive; if one somehow is not, the line must not claim everything is shown."""
    gui = SimpleNamespace(single_project_name="Home", single_profile_name="", single_task_name="", single_scene_name="")
    assert userintr_loading._single_item_selection_message(gui, "Task", "None") == "Display only Project 'Home'."


# ##################################################################################
# Picking a name
# ##################################################################################
@pytest.fixture
def handlers(monkeypatch: pytest.MonkeyPatch) -> tuple[LoadingEventHandlers, MagicMock, dict]:
    """The handlers, with the window a mock and every helper they call replaced by a recorder."""
    gui = MagicMock()
    gui.is_updating = False
    gui.check_name.return_value = True
    state = SimpleNamespace(program_arguments={})
    handler = LoadingEventHandlers()
    handler.gui = gui
    handler.state = state
    calls: dict[str, list] = {
        name: []
        for name in (
            "clear",
            "reset",
            "menus",
            "button",
            "colour",
            "badges",
        )
    }
    monkeypatch.setattr(userintr_loading, "clear_single_item_names", lambda g: calls["clear"].append(g))
    monkeypatch.setattr(
        userintr_loading, "reset_single_item_pulldowns", lambda g, except_for: calls["reset"].append(except_for)
    )
    monkeypatch.setattr(userintr_loading, "update_tasker_object_menus", lambda g, **kw: calls["menus"].append(kw))
    monkeypatch.setattr(
        userintr_loading, "display_analyze_button", lambda g, row, first_time: calls["button"].append(row)
    )
    monkeypatch.setattr(userintr_loading, "update_analysis_button_color", lambda g: calls["colour"].append(g))
    monkeypatch.setattr(userintr_loading, "refresh_scope_badges", lambda g: calls["badges"].append(g))
    return handler, gui, calls


def test_a_valid_name_becomes_the_one_selection(handlers: tuple) -> None:
    handler, gui, calls = handlers

    handler.process_name_event("Project", "Project: Home")

    assert gui.single_project_name == "Home"
    assert handler.state.program_arguments["single_project_name"] == "Home"
    assert calls["reset"] == ["Project"]  # every other pulldown goes back to None
    assert calls["menus"] == [{"get_data": False, "reset_single_names": False}]
    assert "Home" in gui.specific_name_msg
    assert gui.is_updating is False  # set only while the pulldowns are being rewritten


def test_choosing_none_clears_the_selection(handlers: tuple) -> None:
    handler, gui, _calls = handlers
    handler.process_name_event("Project", "None")
    assert gui.single_project_name == ""
    assert handler.state.program_arguments["single_project_name"] == ""


def test_a_name_that_is_not_in_the_backup_changes_nothing_but_refreshes_the_menus(handlers: tuple) -> None:
    handler, gui, calls = handlers
    gui.check_name.return_value = False

    handler.process_name_event("Task", "Nonesuch")

    assert calls["clear"] == []
    assert calls["menus"]  # the menus are still brought up to date


@pytest.mark.parametrize("empty", ["No projects found", "No profiles found", "No tasks found", "No scenes found"])
def test_a_placeholder_entry_is_ignored(handlers: tuple, empty: str) -> None:
    handler, gui, calls = handlers
    handler.process_name_event("Project", empty)
    gui.display_message_box.assert_called_once()
    assert "Selection ignored" in gui.display_message_box.call_args.args[0]
    assert calls["clear"] == []


def test_a_name_arrives_with_or_without_its_kind_in_front(handlers: tuple) -> None:
    handler, gui, _calls = handlers
    handler.process_single_name_event("Project", "Project: Home")
    gui.event_handlers.process_name_event.assert_called_with("Project", "Home")
    handler.process_single_name_event("Project", {"label": "Project: Away"})
    gui.event_handlers.process_name_event.assert_called_with("Project", "Away")
    handler.process_single_name_event("Task", "Wake Up")
    gui.event_handlers.process_name_event.assert_called_with("Task", "Wake Up")


@pytest.mark.parametrize("kind", ["Project", "Profile", "Task", "Scene"])
def test_each_pulldown_routes_to_its_own_kind(handlers: tuple, kind: str) -> None:
    handler, gui, _calls = handlers
    getattr(handler, f"single_{kind.lower()}_name_event")("Name")
    gui.event_handlers.process_name_event.assert_called_once_with(kind, "Name")


@pytest.mark.parametrize("kind", ["Project", "Profile", "Task", "Scene"])
def test_a_pulldown_changed_by_the_program_is_not_treated_as_a_choice(handlers: tuple, kind: str) -> None:
    handler, gui, _calls = handlers
    gui.is_updating = True
    getattr(handler, f"single_{kind.lower()}_name_event")("Name")
    gui.event_handlers.process_name_event.assert_not_called()


# ##################################################################################
# A single-object export selects its own object
# ##################################################################################
def test_a_full_backup_selects_nothing(handlers: tuple, monkeypatch: pytest.MonkeyPatch) -> None:
    handler, gui, _calls = handlers
    monkeypatch.setattr(userintr_loading, "single_item_export_selection", lambda path, state: ("", ""))
    handler.select_single_item_export("backup.xml")
    gui.event_handlers.process_name_event.assert_not_called()


def test_a_single_object_export_selects_that_object_and_its_pulldown(
    handlers: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    handler, gui, _calls = handlers
    monkeypatch.setattr(userintr_loading, "single_item_export_selection", lambda path, state: ("Project", "Home"))
    picked: list[tuple] = []
    monkeypatch.setattr(userintr_loading, "select_pulldown_option", lambda menu, name: picked.append((menu, name)))

    handler.select_single_item_export("Home.prj.xml")

    gui.event_handlers.process_name_event.assert_called_once_with("Project", "Home")
    assert picked == [(gui.specific_project_optionmenu, "Home")]
    gui.specific_project_optionmenu.update.assert_called_once()
    assert gui.is_updating is False


def test_an_export_whose_pulldown_is_not_on_screen_is_still_selected(
    handlers: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    handler, gui, _calls = handlers
    monkeypatch.setattr(userintr_loading, "single_item_export_selection", lambda path, state: ("Scene", "Panel"))
    gui.specific_scene_optionmenu = None
    handler.select_single_item_export("Panel.scn.xml")
    gui.event_handlers.process_name_event.assert_called_once_with("Scene", "Panel")
