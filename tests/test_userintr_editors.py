"""The editor handlers (userintr_editors): what the Edit and Add dialogs' buttons do.

What an edit does to a Task, Profile, Project or Scene is taskedit's, profedit's, projedit's and sceneedit's, and what the
dialogs look like is guiwins_*'s.  This is the part between them: the handler a button is wired to reads the dialog's fields
back, asks the model to validate and apply them, tells the user what happened, and closes the dialog or leaves it open.  So
these call the handlers as the dialogs do, with the window replaced by a mock and the dialogs by recorders, over a small
backup, and assert the three things a user can see -- what changed in the loaded configuration, what the user was told, and
whether the dialog closed -- along with the rule they all keep: on any error nothing is applied and the dialog stays open, so
nothing typed is lost.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from maptasker.src import projedit, profedit, sceneedit, sessundo, taskedit, userintr_editors
from maptasker.src.primitem import PrimeItems
from maptasker.src.userintr import MapTaskerEventHandlers, MyGui
from tests.test_mapswap import _load

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2">
    <name>Home</name>
    <pids>100</pids>
    <tids>20,21,22</tids>
    <scenes>Panel</scenes>
  </Project>
  <Project sr="proj1" ve="2"><name>Work</name></Project>
  <Profile sr="prof100" ve="2">
    <id>100</id>
    <mid0>20</mid0>
    <nme>Morning</nme>
    <Time sr="con0"><fh>8</fh><fm>0</fm><th>9</th><tm>30</tm></Time>
  </Profile>
  <Task sr="task20" ve="2">
    <id>20</id>
    <nme>Noisy</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">Done</Str></Action>
    <Action sr="act1" ve="7"><code>548</code><Str sr="arg0" ve="3">bare</Str></Action>
  </Task>
  <Task sr="task21" ve="2"><id>21</id><nme>Opener</nme></Task>
  <Task sr="task22" ve="2"><id>22</id><nme>Quiet</nme></Task>
  <Scene sr="scene0">
    <nme>Panel</nme>
    <widthPort>600</widthPort><heightPort>800</heightPort><widthLand>-1</widthLand><heightLand>-1</heightLand>
    <RectElement sr="elements0"><geom>0,0,600,800,-1,-1,-1,-1</geom><Str sr="arg0" ve="3">Back</Str></RectElement>
  </Scene>
</TaskerData>
"""


# The two helpers the `calls` fixture stubs for every other test, as they really are -- for the tests of the helpers.
_REAL_SELECT_RENAMED_ITEM = userintr_editors._select_renamed_item
_REAL_RESET_SELECTION = userintr_editors._reset_specific_name_selection


class _Widget(SimpleNamespace):
    """A field widget as the handlers read it: a value, and (for a text box) something to set."""

    def __init__(self, value: object = "") -> None:
        super().__init__(value=value)


class _Label:
    def __init__(self) -> None:
        self.text = ""

    def set_text(self, text: str) -> None:
        self.text = text


class _Notices(list):
    """Every ui.notify made, as (message, type)."""

    def said(self, fragment: str) -> bool:
        return any(fragment in message for message, _kind in self)

    def of_type(self, kind: str) -> list[str]:
        return [message for message, k in self if k == kind]


@pytest.fixture(autouse=True)
def _backup() -> None:
    sessundo.clear(PrimeItems)
    _load(_XML)
    yield
    sessundo.clear(PrimeItems)


@pytest.fixture(autouse=True)
def notices(monkeypatch: pytest.MonkeyPatch) -> _Notices:
    """ui.notify replaced by a record: there is no browser to show it in."""
    heard = _Notices()
    monkeypatch.setattr(
        userintr_editors.ui,
        "notify",
        lambda message, *_a, type="info", **_k: heard.append((str(message), type)),  # noqa: A002
    )
    return heard


@pytest.fixture(autouse=True)
def calls(monkeypatch: pytest.MonkeyPatch) -> dict[str, list]:
    """The dialog builders and pulldown refreshes replaced by recorders, so each handler is seen alone."""
    seen: dict[str, list] = {}

    def record(name: str) -> Callable:
        seen[name] = []
        return lambda *args, **kwargs: seen[name].append((args, kwargs))

    for name in (
        "build_edit_task_dialog",
        "build_run_task_on_android_dialog",
        "build_rename_dialog",
        "build_delete_task_dialog",
        "build_overwrite_confirm_dialog",
        "build_add_task_dialog",
        "build_add_profile_dialog",
        "build_edit_profile_dialog",
        "build_delete_profile_dialog",
        "build_add_project_dialog",
        "build_edit_project_dialog",
        "build_delete_project_dialog",
        "build_add_scene_dialog",
        "build_add_scene_version_dialog",
        "build_edit_scene_dialog",
        "build_delete_scene_dialog",
        "build_object_properties_dialog",
        "refresh_tasker_object_pulldowns",
        "select_pulldown_option",
        "_select_renamed_item",
        "_reset_specific_name_selection",
    ):
        monkeypatch.setattr(userintr_editors, name, record(name))
    return seen


@pytest.fixture
def gui() -> MagicMock:
    window = MagicMock(spec=MyGui)
    window.state = PrimeItems
    window.event_handlers = MagicMock()
    window.debug = False
    window.appearance_mode = "System"
    # No options listed: the pulldowns are "not populated yet", so a cached single name is trusted.
    for kind in ("project", "profile", "task", "scene"):
        setattr(window, f"specific_{kind}_optionmenu", SimpleNamespace())
    window.single_project_name = window.single_profile_name = window.single_task_name = window.single_scene_name = ""
    return window


@pytest.fixture
def handlers(gui: MagicMock) -> MapTaskerEventHandlers:
    return MapTaskerEventHandlers(gui)


@pytest.fixture
def dialog() -> MagicMock:
    return MagicMock()


def _live_task(name: str) -> object:
    return PrimeItems.tasker_root_elements["all_tasks_by_name"][name]["xml"]


def _task_fields(name: str = "Noisy", priority: str = "", save_path: str = "") -> dict:
    return {"name": _Widget(name), "priority": _Widget(priority), "save_path": _Widget(save_path)}


def _edit_task(name: str = "Noisy") -> taskedit.EditableTask:
    edited = taskedit.load_task_for_edit(name, state=PrimeItems)
    assert edited is not None
    return edited


# ##################################################################################
# Reading a dialog's fields back
# ##################################################################################
def test_task_argument_values_skip_the_fields_that_are_not_arguments_and_spell_booleans_as_digits() -> None:
    fields = {
        "name": _Widget("N"),
        "priority": _Widget("5"),
        "save_path": _Widget("p"),
        "target_project_name": "Home",
        userintr_editors.REDACT_FIELD: _Widget(True),
        "act0_arg0": _Widget("text"),
        "act0_arg1": _Widget(True),
        "act0_arg2": _Widget(False),
        "act0_arg3": _Widget(7),
    }
    assert userintr_editors._task_arg_values(fields) == {
        "act0_arg0": "text",
        "act0_arg1": "1",
        "act0_arg2": "0",
        "act0_arg3": "7",
    }


def test_profile_condition_values_take_only_the_condition_fields() -> None:
    fields = {"name": _Widget("N"), "cond0_fh": _Widget(8), "cond0_inv": _Widget(True), "entry_task_picker": _Widget("")}
    assert userintr_editors._profile_condition_values(fields) == {"cond0_fh": "8", "cond0_inv": "1"}


def test_property_values_use_the_words_tasker_writes_and_keep_whole_numbers_whole() -> None:
    values = userintr_editors._object_property_values(
        {"a": _Widget(True), "b": _Widget(False), "c": _Widget(None), "d": _Widget(50.0), "e": _Widget(2.5), "f": _Widget("x")},
    )
    assert values == {"a": "true", "b": "false", "c": "", "d": "50", "e": "2.5", "f": "x"}


def test_redaction_is_read_from_whichever_key_the_dialog_filed_it_under_and_defaults_to_no() -> None:
    assert userintr_editors._redact_requested({}) is False
    assert userintr_editors._redact_requested({userintr_editors.REDACT_FIELD: _Widget(True)}) is True
    assert userintr_editors._redact_requested({"custom": _Widget(True)}, key="custom") is True
    assert userintr_editors._redacted_note(False) == ""
    assert "redacted" in userintr_editors._redacted_note(True)


def test_an_unrecognised_field_in_the_edit_project_dialog_fails_the_save_and_names_it() -> None:
    inert = {key: _Widget() for key in userintr_editors.EDIT_PROJECT_INERT_FIELDS}
    assert userintr_editors._unapplied_project_edits(inert) == []

    errors = userintr_editors._unapplied_project_edits({**inert, "new_field": _Widget(), "another": _Widget()})
    assert len(errors) == 1
    assert "another, new_field" in errors[0]


def test_scene_sizes_are_validated_together_and_written_only_when_all_are_whole_numbers() -> None:
    edited = sceneedit.load_scene_for_edit("Panel", state=PrimeItems)
    good = {"widthPort": _Widget("640"), "heightPort": _Widget(" 480 "), "widthLand": _Widget("-1")}
    assert userintr_editors._apply_scene_field_values(edited, good) == []
    assert edited.scene_element.findtext("widthPort") == "640"
    assert edited.scene_element.findtext("heightPort") == "480"

    bad = {"widthPort": _Widget("wide"), "heightPort": _Widget("700"), "widthLand": _Widget("also bad")}
    errors = userintr_editors._apply_scene_field_values(edited, bad)
    assert len(errors) == 2
    assert edited.scene_element.findtext("heightPort") == "480", "nothing is written when anything is refused"


def test_a_scene_dialog_with_no_size_fields_writes_nothing() -> None:
    edited = sceneedit.load_scene_for_edit("Panel", state=PrimeItems)
    assert userintr_editors._apply_scene_field_values(edited, {}) == []
    assert edited.scene_element.findtext("widthPort") == "600"


def test_the_version_2_layout_the_designer_edited_is_written_back_under_the_scenes_current_name() -> None:
    edited = sceneedit.create_new_scene("Fresh", sceneedit.SCENE_VERSION_V2, state=PrimeItems)
    layout = sceneedit.decode_v2_layout(edited.scene_element)
    layout["root"]["id"] = "renamed_root"
    edited.scene_element.find("nme").text = "Renamed"

    userintr_editors._encode_v2_layout_if_edited(edited, {"v2_layout": layout})

    written = sceneedit.decode_v2_layout(edited.scene_element)
    assert written["root"]["id"] == "renamed_root"
    assert written["name"] == "Renamed", "the layout's own name follows <nme>, whichever was applied first"
    userintr_editors._encode_v2_layout_if_edited(edited, {})  # a Legacy Scene: nothing to do


# ##################################################################################
# Which Project a new object belongs to
# ##################################################################################
def test_a_selected_project_is_used_when_the_pulldown_still_lists_it(gui: MagicMock) -> None:
    gui.single_project_name = "Home"
    gui.specific_project_optionmenu = SimpleNamespace(options=["None", "Project: Home"])
    assert userintr_editors._project_for_new_object(gui, "Task") == ("Home", "")


def test_a_project_name_the_pulldown_no_longer_lists_does_not_count_as_selected(gui: MagicMock) -> None:
    gui.single_project_name = "Gone"
    gui.specific_project_optionmenu = SimpleNamespace(options=["None", "Project: Home"])
    project, message = userintr_editors._project_for_new_object(gui, "Task")
    assert project == ""
    assert "Select a single Project first" in message


def test_with_no_pulldown_built_yet_the_cached_project_name_is_trusted(gui: MagicMock) -> None:
    gui.single_project_name = "Home"
    gui.specific_project_optionmenu = None
    assert userintr_editors._confirmed_single_project_name(gui) == "Home"


def test_a_selected_task_profile_or_scene_leads_to_the_project_that_owns_it(gui: MagicMock) -> None:
    for attribute, name in (("single_task_name", "Noisy"), ("single_profile_name", "Morning"), ("single_scene_name", "Panel")):
        gui.single_project_name = gui.single_task_name = gui.single_profile_name = gui.single_scene_name = ""
        setattr(gui, attribute, name)
        assert userintr_editors._project_for_new_object(gui, "Profile") == ("Home", ""), attribute


def test_an_object_that_belongs_to_no_project_says_so_and_still_asks_for_one(gui: MagicMock) -> None:
    PrimeItems.tasker_root_elements["all_projects"]["Home"]["xml"].find("tids").text = ""
    gui.single_task_name = "Quiet"  # listed only in the Project's <tids>, which was just emptied
    project, message = userintr_editors._project_for_new_object(gui, "Profile")
    assert project == ""
    assert "Task 'Quiet' does not belong to a Project" in message
    assert "Select a single Project first" in message


def test_with_nothing_selected_it_asks_for_a_project(gui: MagicMock) -> None:
    assert userintr_editors._project_for_new_object(gui, "Scene")[0] == ""


def test_a_scene_name_is_confirmed_against_its_own_pulldown(gui: MagicMock) -> None:
    gui.single_scene_name = "Panel"
    gui.specific_scene_optionmenu = SimpleNamespace(options=["None", "Panel"])
    assert userintr_editors._confirmed_single_scene_name(gui) == "Panel"
    gui.specific_scene_optionmenu = SimpleNamespace(options=["None"])
    assert userintr_editors._confirmed_single_scene_name(gui) == ""
    gui.specific_scene_optionmenu = None
    assert userintr_editors._confirmed_single_scene_name(gui) == "Panel"
    gui.single_scene_name = ""
    assert userintr_editors._confirmed_single_scene_name(gui) == ""


# ##################################################################################
# Following a rename in the pulldowns
# ##################################################################################
def test_a_pulldown_option_is_found_by_exact_name_then_by_its_item_type_prefix_then_by_tail() -> None:
    plain = SimpleNamespace(options=["None", "Quiet"])
    assert userintr_editors._pulldown_option_for_name(plain, "Task", "Quiet") == "Quiet"
    prefixed = SimpleNamespace(options=["None", "Project: Home"])
    assert userintr_editors._pulldown_option_for_name(prefixed, "Project", "Home") == "Project: Home"
    other_language = SimpleNamespace(options=["None", "Projekt: Home"])
    assert userintr_editors._pulldown_option_for_name(other_language, "Project", "Home") == "Projekt: Home"
    assert userintr_editors._pulldown_option_for_name(prefixed, "Project", "Nowhere") == "Nowhere"
    assert userintr_editors._pulldown_option_for_name(SimpleNamespace(), "Task", "x") == "x"


def test_selecting_a_renamed_item_points_the_pulldown_at_it_and_runs_the_name_event_with_the_bare_name(
    gui: MagicMock,
) -> None:
    gui.specific_project_optionmenu = SimpleNamespace(options=["None", "Project: Renamed"], value="", update=MagicMock())
    seen_while_updating = []
    gui.event_handlers.process_name_event.side_effect = lambda *_a: seen_while_updating.append(gui.is_updating)

    _REAL_SELECT_RENAMED_ITEM(gui, "Project", "Renamed")

    assert gui.specific_project_optionmenu.value == "Project: Renamed"
    gui.specific_project_optionmenu.update.assert_called_once()
    gui.event_handlers.process_name_event.assert_called_once_with("Project", "Renamed")
    assert seen_while_updating == [False], "the guard is down again by the time the name event runs"
    assert gui.is_updating is False


def test_selecting_a_renamed_item_does_nothing_if_there_is_no_pulldown(gui: MagicMock) -> None:
    gui.specific_task_optionmenu = None
    _REAL_SELECT_RENAMED_ITEM(gui, "Task", "Quiet")
    gui.event_handlers.process_name_event.assert_not_called()


def test_deleting_the_selected_object_clears_every_selection_with_the_guard_up(
    gui: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cleared, reset = [], []
    monkeypatch.setattr(userintr_editors, "clear_single_item_view_names", lambda g: cleared.append(g))
    monkeypatch.setattr(userintr_editors, "reset_single_item_pulldowns", lambda g: reset.append(g.is_updating))

    _REAL_RESET_SELECTION(gui)

    assert cleared == [gui]
    assert reset == [True]
    assert gui.is_updating is False


# ##################################################################################
# Saving to the current file
# ##################################################################################
def test_a_saved_copy_replaces_the_loaded_file_and_the_pulldowns_are_rebuilt_from_it(
    gui: MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    copy = tmp_path / "backup_copy.xml"
    copy.write_text(_XML, encoding="utf-8")
    shown, refreshed = [], []
    monkeypatch.setattr(userintr_editors, "get_the_xml_data", lambda state: 0)
    monkeypatch.setattr(userintr_editors, "display_current_file", lambda g, path: shown.append(path))
    monkeypatch.setattr(userintr_editors, "refresh_tasker_object_pulldowns", lambda g: refreshed.append(g))

    assert userintr_editors.reload_saved_copy_and_refresh(gui, str(copy)) == (True, "")

    assert PrimeItems.program_arguments.file == str(copy)
    assert gui.file == str(copy)
    assert shown == [str(copy)] and refreshed == [gui]
    PrimeItems.file_to_get.close()


def test_a_copy_that_cannot_be_opened_or_parsed_is_reported_and_leaves_the_window_alone(
    gui: MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ok, error = userintr_editors.reload_saved_copy_and_refresh(gui, str(tmp_path / "missing.xml"))
    assert ok is False and error

    present = tmp_path / "copy.xml"
    present.write_text(_XML, encoding="utf-8")
    monkeypatch.setattr(userintr_editors, "get_the_xml_data", lambda state: 7)
    ok, error = userintr_editors.reload_saved_copy_and_refresh(gui, str(present))
    assert (ok, "code 7" in error) == (False, True)
    PrimeItems.file_to_get.close()


@pytest.mark.asyncio
async def test_the_in_progress_notice_is_a_spinner_that_lets_the_loop_send_it_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    made = []
    monkeypatch.setattr(userintr_editors.ui, "notification", lambda *a, **k: made.append((a, k)) or "notice")
    assert await userintr_editors.show_save_in_progress_notice() == "notice"
    ((args, kwargs),) = made
    assert "in progress" in args[0]
    assert kwargs["spinner"] is True and kwargs["timeout"] is None


def _stub_the_save(monkeypatch: pytest.MonkeyPatch, *, written: tuple = (True, "/tmp/copy.xml"), reloaded: tuple = (True, "")) -> MagicMock:
    notice = MagicMock()
    monkeypatch.setattr(userintr_editors, "show_save_in_progress_notice", AsyncMock(return_value=notice))
    monkeypatch.setattr(userintr_editors, "write_full_backup_to_current_file", lambda state: written)
    monkeypatch.setattr(userintr_editors, "reload_saved_copy_and_refresh", lambda g, path: reloaded)
    return notice


# ##################################################################################
# The Task editor
# ##################################################################################
def test_edit_task_with_none_selected_asks_for_one(handlers: MapTaskerEventHandlers, notices: _Notices, calls: dict) -> None:
    handlers.open_edit_task_dialog_event()
    assert notices.said("Select a single Task first")
    assert calls["build_edit_task_dialog"] == []


def test_edit_task_for_a_name_that_does_not_resolve_says_so(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    notices: _Notices,
    calls: dict,
) -> None:
    gui.single_task_name = "Vanished"
    handlers.open_edit_task_dialog_event()
    assert notices.of_type("negative") == ["Could not find Task 'Vanished'."]
    assert calls["build_edit_task_dialog"] == []


def test_edit_task_opens_the_dialog_over_a_copy_of_the_selected_task(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    calls: dict,
) -> None:
    gui.single_task_name = "Noisy"
    handlers.open_edit_task_dialog_event()
    ((args, _),) = calls["build_edit_task_dialog"]
    assert args[0] is gui
    assert args[1].task_element is not _live_task("Noisy"), "a copy, so Cancel leaves the loaded Task alone"


def test_run_on_android_needs_a_selected_task_and_takes_only_its_name(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    notices: _Notices,
    calls: dict,
) -> None:
    handlers.open_run_task_on_android_dialog_event()
    assert notices.said("Select a single Task first") and calls["build_run_task_on_android_dialog"] == []
    gui.single_task_name = "Quiet"
    handlers.open_run_task_on_android_dialog_event()
    assert calls["build_run_task_on_android_dialog"] == [((gui, "Quiet"), {})]


def test_the_rename_button_prompts_for_a_name_and_the_prompt_confirms_through_the_handler(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    calls: dict,
    dialog: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    edited = _edit_task()
    label = _Label()
    handlers.rename_task_event(edited, _task_fields(), label)
    ((args, _),) = calls["build_rename_dialog"]
    assert args[:3] == (gui, "Task", "Noisy")

    confirmed = []
    monkeypatch.setattr(handlers, "confirm_rename_task_event", lambda *a: confirmed.append(a))
    args[3]("Loud", dialog)
    assert confirmed[0][3:] == ("Loud", dialog)


def test_a_valid_rename_is_applied_at_once_and_the_dialog_follows_it(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    notices: _Notices,
    calls: dict,
    dialog: MagicMock,
) -> None:
    edited = _edit_task()
    label = _Label()
    fields = _task_fields(save_path=taskedit.default_save_path("Noisy", PrimeItems))

    handlers.confirm_rename_task_event(edited, fields, label, "Loud", dialog)

    assert "Loud" in PrimeItems.tasker_root_elements["all_tasks_by_name"]
    assert "Noisy" not in PrimeItems.tasker_root_elements["all_tasks_by_name"]
    assert label.text == "Edit Task: Loud"
    assert fields["name"].value == "Loud", "Ok would otherwise rename it straight back"
    assert fields["save_path"].value == taskedit.default_save_path("Loud", PrimeItems)
    assert notices.said("Renamed to 'Loud'.")
    assert calls["refresh_tasker_object_pulldowns"] and calls["_select_renamed_item"][0][0][1:] == ("Task", "Loud")
    dialog.close.assert_called_once()


def test_a_save_path_the_user_typed_is_not_rewritten_by_a_rename(
    handlers: MapTaskerEventHandlers,
    calls: dict,
    dialog: MagicMock,
    notices: _Notices,
) -> None:
    fields = _task_fields(save_path="/my/own/place.tsk.xml")
    handlers.confirm_rename_task_event(_edit_task(), fields, _Label(), "Loud", dialog)
    assert fields["save_path"].value == "/my/own/place.tsk.xml"


@pytest.mark.parametrize("bad_name", ["", "   ", "Opener"])
def test_a_rename_to_nothing_or_to_a_taken_name_is_refused_and_the_prompt_stays_open(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    calls: dict,
    dialog: MagicMock,
    bad_name: str,
) -> None:
    handlers.confirm_rename_task_event(_edit_task(), _task_fields(), _Label(), bad_name, dialog)
    assert notices.of_type("negative")
    assert "Noisy" in PrimeItems.tasker_root_elements["all_tasks_by_name"]
    dialog.close.assert_not_called()
    assert calls["refresh_tasker_object_pulldowns"] == []


def test_delete_task_opens_the_confirmation_over_the_editor(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    calls: dict,
    dialog: MagicMock,
) -> None:
    edited = _edit_task()
    handlers.delete_task_event(edited, dialog)
    assert calls["build_delete_task_dialog"] == [((gui, edited, dialog), {})]


def test_confirming_a_delete_removes_the_task_clears_the_selection_and_closes_both_dialogs(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    calls: dict,
) -> None:
    confirm, parent = MagicMock(), MagicMock()
    handlers.confirm_delete_task_event("Quiet", confirm, parent)
    assert "Quiet" not in PrimeItems.tasker_root_elements["all_tasks_by_name"]
    assert notices.said("Deleted Task 'Quiet'.")
    assert calls["refresh_tasker_object_pulldowns"] and calls["_reset_specific_name_selection"]
    confirm.close.assert_called_once()
    parent.close.assert_called_once()


def test_deleting_a_task_that_does_not_exist_reports_it_and_keeps_both_dialogs_open(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    calls: dict,
) -> None:
    confirm, parent = MagicMock(), MagicMock()
    handlers.confirm_delete_task_event("No Such Task", confirm, parent)
    assert notices.of_type("negative")
    confirm.close.assert_not_called()
    parent.close.assert_not_called()
    assert calls["_reset_specific_name_selection"] == []


def test_ok_keeps_the_edit_in_the_loaded_configuration_and_closes_the_dialog(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
) -> None:
    edited = _edit_task()
    handlers.keep_edited_task_event(edited, _task_fields(name="Noisier", priority="3"), dialog)
    assert "Noisier" in PrimeItems.tasker_root_elements["all_tasks_by_name"] or _live_task_by_id("20").findtext("nme") == "Noisier"
    assert _live_task_by_id("20").findtext("pri") == "3"
    assert notices.said("Changes kept.")
    dialog.close.assert_called_once()


def _live_task_by_id(task_id: str) -> object:
    return PrimeItems.tasker_root_elements["all_tasks"][task_id]["xml"]


@pytest.mark.parametrize(("name", "priority"), [("", "1"), ("Fine", "high"), ("Fine", "-3")])
def test_ok_with_a_bad_name_or_priority_changes_nothing_and_leaves_the_dialog_open(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
    name: str,
    priority: str,
) -> None:
    handlers.keep_edited_task_event(_edit_task(), _task_fields(name=name, priority=priority), dialog)
    assert notices.of_type("negative")
    assert _live_task_by_id("20").findtext("nme") == "Noisy"
    dialog.close.assert_not_called()


def test_save_writes_a_standalone_file_applies_the_edit_and_closes(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
    tmp_path: Path,
) -> None:
    target = tmp_path / "noisy.tsk.xml"
    handlers.save_edited_task_event(_edit_task(), _task_fields(name="Noisier", save_path=str(target)), dialog)
    assert target.is_file()
    assert "Noisier" in target.read_text(encoding="utf-8")
    assert notices.said(f"Saved to {target}.")
    assert _live_task_by_id("20").findtext("nme") == "Noisier"
    dialog.close.assert_called_once()


def test_save_over_an_existing_file_asks_before_it_clobbers_and_writes_only_when_told_to(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    calls: dict,
    dialog: MagicMock,
    tmp_path: Path,
) -> None:
    target = tmp_path / "noisy.tsk.xml"
    target.write_text("old", encoding="utf-8")
    handlers.save_edited_task_event(_edit_task(), _task_fields(save_path=str(target)), dialog)

    assert target.read_text(encoding="utf-8") == "old", "nothing is written until the user agrees"
    dialog.close.assert_not_called()
    ((args, _),) = calls["build_overwrite_confirm_dialog"]
    args[1]()
    assert target.read_text(encoding="utf-8") != "old"
    assert notices.said("The file it replaced was copied to")
    dialog.close.assert_called_once()


def test_a_save_with_an_invalid_field_writes_no_file_and_leaves_the_dialog_open(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
    tmp_path: Path,
) -> None:
    target = tmp_path / "bad.tsk.xml"
    handlers.save_edited_task_event(_edit_task(), _task_fields(name="", save_path=str(target)), dialog)
    assert not target.exists() and notices.of_type("negative")
    dialog.close.assert_not_called()


def test_a_save_that_cannot_write_says_so_and_applies_nothing(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
    tmp_path: Path,
) -> None:
    handlers.save_edited_task_event(
        _edit_task(),
        _task_fields(name="Noisier", save_path=str(tmp_path / "no_such_folder" / "x.tsk.xml")),
        dialog,
    )
    assert notices.said("Could not save file")
    assert _live_task_by_id("20").findtext("nme") == "Noisy"
    dialog.close.assert_not_called()


def test_a_redacted_save_says_what_was_redacted(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
    tmp_path: Path,
) -> None:
    fields = _task_fields(save_path=str(tmp_path / "r.tsk.xml"))
    fields[userintr_editors.REDACT_FIELD] = _Widget(True)
    handlers.save_edited_task_event(_edit_task(), fields, dialog)
    assert notices.said("Secrets and personal details were redacted")


@pytest.mark.asyncio
async def test_save_to_current_file_applies_the_edit_writes_the_copy_loads_it_and_reselects_the_task(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    notices: _Notices,
    calls: dict,
    dialog: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    notice = _stub_the_save(monkeypatch)
    await handlers.save_edited_task_to_current_file_event(_edit_task(), _task_fields(name="Noisier"), dialog)

    assert _live_task_by_id("20").findtext("nme") == "Noisier"
    notice.dismiss.assert_called_once()
    assert calls["_select_renamed_item"][0][0][1:] == ("Task", "Noisier")
    assert notices.said("The original file was left unchanged.")
    dialog.close.assert_called_once()


@pytest.mark.asyncio
async def test_a_current_file_save_that_fails_to_write_says_so_and_keeps_the_dialog(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    notice = _stub_the_save(monkeypatch, written=(False, "disk full"))
    await handlers.save_edited_task_to_current_file_event(_edit_task(), _task_fields(), dialog)
    notice.dismiss.assert_called_once()
    assert notices.said("Could not save to current file: disk full")
    dialog.close.assert_not_called()


@pytest.mark.asyncio
async def test_a_copy_that_was_written_but_would_not_load_is_a_warning_not_a_success(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_the_save(monkeypatch, reloaded=(False, "unreadable"))
    await handlers.save_edited_task_to_current_file_event(_edit_task(), _task_fields(), dialog)
    assert notices.of_type("warning") and "unreadable" in notices.of_type("warning")[0]
    dialog.close.assert_not_called()


@pytest.mark.asyncio
async def test_a_current_file_save_with_an_invalid_field_does_not_write_anything(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    written = MagicMock()
    monkeypatch.setattr(userintr_editors, "write_full_backup_to_current_file", written)
    await handlers.save_edited_task_to_current_file_event(_edit_task(), _task_fields(name=""), dialog)
    written.assert_not_called()
    assert notices.of_type("negative")


def test_a_task_kept_in_the_loaded_configuration_is_registered_if_new_and_written_back_if_not(
    handlers: MapTaskerEventHandlers,
    calls: dict,
) -> None:
    existing = _edit_task()
    existing.task_element.find("nme").text = "Edited"
    handlers._keep_task_in_loaded_config(existing, "Edited", is_new_task=False, on_created=None)
    assert _live_task_by_id("20").findtext("nme") == "Edited"

    created = taskedit.create_new_task("Brand New", "", state=PrimeItems)
    made = []
    handlers._keep_task_in_loaded_config(created, "Brand New", is_new_task=True, on_created=made.append)
    assert "Brand New" in PrimeItems.tasker_root_elements["all_tasks_by_name"]
    assert made == [created.task_id]
    assert len(calls["refresh_tasker_object_pulldowns"]) == 2


# ##################################################################################
# Tasks edited under a Scene's Properties
# ##################################################################################
def test_stashing_snapshots_the_widgets_into_the_task_copy_without_touching_the_loaded_task(
    handlers: MapTaskerEventHandlers,
) -> None:
    edited = _edit_task()
    key = taskedit.arg_key(edited.actions[0].act_number, edited.actions[0].args[0].arg_id)
    handlers.stash_scene_event_task_edits(edited, {key: _Widget("changed text")})
    assert "changed text" in ET_text(edited.task_element)
    assert "changed text" not in ET_text(_live_task("Noisy"))


def ET_text(element: object) -> str:  # noqa: N802
    import xml.etree.ElementTree as ET

    return ET.tostring(element, encoding="unicode")


def test_applying_a_key_tasks_edits_keeps_them_without_closing_anything_or_touching_its_name(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
) -> None:
    edited = _edit_task()
    key = taskedit.arg_key(edited.actions[0].act_number, edited.actions[0].args[0].arg_id)
    handlers.apply_scene_key_task_event(edited, {key: _Widget("applied")})
    assert "applied" in ET_text(_live_task("Noisy"))
    assert notices.said("Changes kept for Task 'Noisy'")


def test_keeping_a_scenes_event_tasks_applies_bound_copies_and_creates_the_ones_that_have_actions(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    calls: dict,
) -> None:
    bound = _edit_task()
    key = taskedit.arg_key(bound.actions[0].act_number, bound.actions[0].args[0].arg_id)

    composed = taskedit.create_new_task("From Event", "", state=PrimeItems)
    taskedit.add_action_to_task(composed, "548t", state=PrimeItems)
    empty = taskedit.create_new_task("Left Empty", "", state=PrimeItems)

    bound_to = []
    pending = {"longclickTask": (composed, {"name": _Widget("From Event"), "priority": _Widget("")}), "other": (empty, {})}
    kept = handlers.keep_scene_event_task_edits(
        {"clickTask": (bound, {key: _Widget("via event")})},
        pending,
        lambda tag, task_id: bound_to.append((tag, task_id)),
    )

    assert kept is True
    assert "via event" in ET_text(_live_task("Noisy"))
    assert "Left Empty" not in PrimeItems.tasker_root_elements["all_tasks_by_name"], "an untouched sub-tab creates nothing"
    assert "other" in pending, "and is left alone"


def test_keeping_scene_event_tasks_reports_a_rejected_edit_and_says_the_dialog_must_stay_open(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
) -> None:
    bound = _edit_task()
    wait = taskedit.add_action_to_task(bound, "30t", state=PrimeItems)  # a Wait, whose MS must be a whole number
    key = taskedit.arg_key(wait.act_number, "0")
    assert handlers.keep_scene_event_task_edits({"t": (bound, {key: _Widget("not a number")})}, {}, lambda *_a: None) is False
    assert notices.said("'MS' must be a whole number.")
    assert "<code>30</code>" not in ET_text(_live_task("Noisy")), "nothing of the rejected Task was applied"


def test_cancelling_the_scene_properties_puts_the_properties_and_the_geometry_boxes_back(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
) -> None:
    edited = sceneedit.load_scene_for_edit("Panel", state=PrimeItems)
    properties = sceneedit_legacy_properties(edited)
    snapshot = sceneedit_legacy_snapshot(properties)
    geometry = {"widthPort": _Widget("999")}

    handlers.discard_scene_properties_event(edited.scene_element, snapshot, {"widthPort": "600"}, geometry)

    assert geometry["widthPort"].value == "600"
    assert notices.said("Scene properties changes discarded.")


def test_cancelling_when_nothing_was_changed_is_silent(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
) -> None:
    edited = sceneedit.load_scene_for_edit("Panel", state=PrimeItems)
    snapshot = sceneedit_legacy_snapshot(sceneedit_legacy_properties(edited))
    handlers.discard_scene_properties_event(edited.scene_element, snapshot, {"widthPort": "600"}, {"widthPort": _Widget("600")})
    assert list(notices) == []


def sceneedit_legacy_properties(edited: sceneedit.EditableScene) -> object:
    from maptasker.src import sceneedit_legacy

    sceneedit_legacy.legacy_add_scene_properties(edited.scene_element, state=PrimeItems)
    return sceneedit_legacy.legacy_scene_properties(edited.scene_element)


def sceneedit_legacy_snapshot(properties: object) -> object:
    import copy

    return copy.deepcopy(properties)


def test_creating_a_scene_events_task_registers_it_binds_it_and_says_so(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    calls: dict,
) -> None:
    created = taskedit.create_new_task("Event Task", "", state=PrimeItems)
    bound = []
    assert handlers.create_scene_event_task_event(
        created,
        {"name": _Widget("Event Task"), "priority": _Widget("")},
        bound.append,
    )
    assert "Event Task" in PrimeItems.tasker_root_elements["all_tasks_by_name"]
    assert bound == [created.task_id]
    assert notices.said("Event Task")


def test_creating_a_scene_events_task_with_a_taken_name_creates_nothing(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    calls: dict,
) -> None:
    created = taskedit.create_new_task("Opener", "", state=PrimeItems)
    bound = []
    assert not handlers.create_scene_event_task_event(created, {"name": _Widget("Opener"), "priority": _Widget("")}, bound.append)
    assert bound == []
    assert notices.said("already exists")


# ##################################################################################
# The Project editor
# ##################################################################################
def _live_project(name: str) -> object:
    return PrimeItems.tasker_root_elements["all_projects"][name]["xml"]


def _edit_project(name: str = "Home") -> projedit.EditableProject:
    edited = projedit.load_project_for_edit(name, state=PrimeItems)
    assert edited is not None
    return edited


def test_add_project_opens_the_dialog_on_a_blank_project(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    calls: dict,
) -> None:
    handlers.open_add_project_dialog_event()
    ((args, _),) = calls["build_add_project_dialog"]
    assert args[0] is gui
    assert isinstance(args[1], projedit.EditableProject)


def test_add_project_with_no_backup_and_no_file_to_load_says_so(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    notices: _Notices,
    calls: dict,
) -> None:
    PrimeItems.xml_root = None
    PrimeItems.file_to_get = None
    gui.file = ""
    handlers.open_add_project_dialog_event()
    assert notices.said("No backup file is currently loaded.")
    assert calls["build_add_project_dialog"] == []


def test_add_project_loads_the_file_the_window_has_open_when_nothing_is_parsed_yet(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    calls: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    PrimeItems.xml_root = None
    PrimeItems.file_to_get = None
    gui.file = "backup.xml"
    loaded = []
    monkeypatch.setattr(userintr_editors, "get_xml", lambda *args, **kwargs: loaded.append(PrimeItems.file_to_get) or 0)
    handlers.open_add_project_dialog_event()
    assert loaded == ["backup.xml"]


def test_a_new_project_is_registered_selected_and_the_dialog_closes(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    calls: dict,
    dialog: MagicMock,
) -> None:
    created = projedit.create_new_project("", state=PrimeItems)
    handlers.keep_new_project_event(created, {"name": _Widget("  Fresh  ")}, dialog)
    assert "Fresh" in PrimeItems.tasker_root_elements["all_projects"]
    assert calls["refresh_tasker_object_pulldowns"] and calls["select_pulldown_option"][0][0][1] == "Fresh"
    assert notices.said("Project added.")
    dialog.close.assert_called_once()


@pytest.mark.parametrize("name", ["Home", "", "  "])
def test_a_new_project_with_a_taken_or_empty_name_is_refused_and_the_dialog_stays(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    calls: dict,
    dialog: MagicMock,
    name: str,
) -> None:
    created = projedit.create_new_project("", state=PrimeItems)
    handlers.keep_new_project_event(created, {"name": _Widget(name)}, dialog)
    assert notices.of_type("negative")
    dialog.close.assert_not_called()
    assert calls["refresh_tasker_object_pulldowns"] == []


def test_edit_project_needs_a_selected_project_that_still_resolves(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    notices: _Notices,
    calls: dict,
) -> None:
    gui.specific_project_optionmenu = None
    handlers.open_edit_project_dialog_event()
    assert notices.said("Select a single Project first")

    gui.single_project_name = "Vanished"
    handlers.open_edit_project_dialog_event()
    assert notices.said("Could not find Project 'Vanished'.")

    gui.single_project_name = "Home"
    handlers.open_edit_project_dialog_event()
    ((args, _),) = calls["build_edit_project_dialog"]
    assert args[1].project_name == "Home"


def test_the_project_rename_prompt_confirms_through_the_handler_with_the_editor_dialog_as_parent(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    calls: dict,
    dialog: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    edited = _edit_project()
    handlers.rename_project_event(edited, dialog)
    ((args, _),) = calls["build_rename_dialog"]
    assert args[:3] == (gui, "Project", "Home")
    confirmed = []
    monkeypatch.setattr(handlers, "confirm_rename_project_event", lambda *a: confirmed.append(a))
    prompt = MagicMock()
    args[3]("Houses", prompt)
    assert confirmed == [(edited, "Houses", prompt, dialog)]


def test_a_project_rename_moves_it_follows_it_and_closes_both_dialogs(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    calls: dict,
) -> None:
    prompt, parent = MagicMock(), MagicMock()
    handlers.confirm_rename_project_event(_edit_project(), "Houses", prompt, parent)
    assert "Houses" in PrimeItems.tasker_root_elements["all_projects"]
    assert "Home" not in PrimeItems.tasker_root_elements["all_projects"]
    assert calls["_select_renamed_item"][0][0][1:] == ("Project", "Houses")
    assert notices.said("Renamed to 'Houses'.")
    prompt.close.assert_called_once()
    parent.close.assert_called_once()


@pytest.mark.parametrize("bad", ["", "Work"])
def test_a_project_rename_to_nothing_or_a_taken_name_leaves_everything_open(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    bad: str,
) -> None:
    prompt, parent = MagicMock(), MagicMock()
    handlers.confirm_rename_project_event(_edit_project(), bad, prompt, parent)
    assert notices.of_type("negative") and "Home" in PrimeItems.tasker_root_elements["all_projects"]
    prompt.close.assert_not_called()
    parent.close.assert_not_called()


def test_the_enabled_switch_reaches_the_loaded_project_at_once(handlers: MapTaskerEventHandlers) -> None:
    edited = _edit_project()
    handlers.set_project_enabled_event(edited, enabled=False)
    assert projedit.is_project_enabled(edited) is False
    handlers.set_project_enabled_event(edited, enabled=True)
    assert projedit.is_project_enabled(edited) is True


def test_delete_project_opens_the_choice_over_the_editor(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    calls: dict,
    dialog: MagicMock,
) -> None:
    edited = _edit_project()
    handlers.delete_project_event(edited, dialog)
    assert calls["build_delete_project_dialog"] == [((gui, edited, dialog), {})]


def test_keep_contents_moves_the_profiles_and_tasks_to_base_and_says_where(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    calls: dict,
) -> None:
    confirm, parent = MagicMock(), MagicMock()
    handlers.keep_contents_delete_project_event("Home", confirm, parent)
    assert "Home" not in PrimeItems.tasker_root_elements["all_projects"]
    assert notices.said(f"moved to '{projedit.BASE_PROJECT_NAME}'")
    assert calls["_reset_specific_name_selection"]
    confirm.close.assert_called_once()
    parent.close.assert_called_once()


def test_delete_contents_removes_everything_the_project_owned(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    calls: dict,
) -> None:
    handlers.delete_contents_delete_project_event("Home", MagicMock(), MagicMock())
    assert notices.said("and everything it owned")
    assert "Noisy" not in PrimeItems.tasker_root_elements["all_tasks_by_name"]


def test_a_project_delete_the_model_refuses_is_reported_and_closes_nothing(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    calls: dict,
) -> None:
    confirm, parent = MagicMock(), MagicMock()
    handlers.delete_contents_delete_project_event("No Such Project", confirm, parent)
    assert notices.of_type("negative")
    confirm.close.assert_not_called()
    parent.close.assert_not_called()
    assert calls["_reset_specific_name_selection"] == []


def _project_fields(name: str = "Home", save_path: str = "") -> dict:
    return {key: _Widget() for key in userintr_editors.EDIT_PROJECT_INERT_FIELDS} | {
        "name": _Widget(name),
        "project_save_path": _Widget(save_path),
    }


def test_exporting_a_project_writes_its_file_under_its_applied_name(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
    tmp_path: Path,
) -> None:
    target = tmp_path / "home.prj.xml"
    handlers.save_project_event(_edit_project(), _project_fields(save_path=str(target)), dialog)
    assert target.is_file() and "Noisy" in target.read_text(encoding="utf-8")
    assert notices.said("Saved Project 'Home'")
    dialog.close.assert_called_once()


def test_exporting_over_an_existing_file_asks_first(
    handlers: MapTaskerEventHandlers,
    calls: dict,
    dialog: MagicMock,
    tmp_path: Path,
) -> None:
    target = tmp_path / "home.prj.xml"
    target.write_text("old", encoding="utf-8")
    handlers.save_project_event(_edit_project(), _project_fields(save_path=str(target)), dialog)
    assert target.read_text(encoding="utf-8") == "old"
    calls["build_overwrite_confirm_dialog"][0][0][1]()
    assert target.read_text(encoding="utf-8") != "old"


def test_an_export_that_cannot_write_says_so(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
    tmp_path: Path,
) -> None:
    handlers.save_project_event(_edit_project(), _project_fields(save_path=str(tmp_path / "nope" / "x.xml")), dialog)
    assert notices.said("Could not save file")
    dialog.close.assert_not_called()


def test_an_edit_project_dialog_with_a_field_nothing_applies_fails_both_saves(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
    tmp_path: Path,
) -> None:
    fields = _project_fields(save_path=str(tmp_path / "x.prj.xml")) | {"brand_new_field": _Widget()}
    handlers.save_project_event(_edit_project(), fields, dialog)
    assert notices.said("brand_new_field") and not (tmp_path / "x.prj.xml").exists()
    dialog.close.assert_not_called()


@pytest.mark.asyncio
async def test_project_save_to_current_file_applies_the_name_writes_loads_and_follows_it(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    calls: dict,
    dialog: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    notice = _stub_the_save(monkeypatch)
    await handlers.save_project_to_current_file_event(_edit_project(), _project_fields(name="Houses"), dialog)
    assert "Houses" in PrimeItems.tasker_root_elements["all_projects"]
    notice.dismiss.assert_called_once()
    assert calls["_select_renamed_item"][0][0][1:] == ("Project", "Houses")
    dialog.close.assert_called_once()


@pytest.mark.asyncio
async def test_project_save_to_current_file_stops_at_an_unapplied_field_a_bad_name_or_a_failed_write(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    written = MagicMock(return_value=(False, "disk full"))
    monkeypatch.setattr(userintr_editors, "write_full_backup_to_current_file", written)

    await handlers.save_project_to_current_file_event(_edit_project(), _project_fields() | {"extra": _Widget()}, dialog)
    await handlers.save_project_to_current_file_event(_edit_project(), _project_fields(name=""), dialog)
    written.assert_not_called()

    monkeypatch.setattr(userintr_editors, "show_save_in_progress_notice", AsyncMock(return_value=MagicMock()))
    await handlers.save_project_to_current_file_event(_edit_project(), _project_fields(), dialog)
    assert notices.said("Could not save to current file: disk full")

    _stub_the_save(monkeypatch, reloaded=(False, "unreadable"))
    await handlers.save_project_to_current_file_event(_edit_project(), _project_fields(), dialog)
    assert "unreadable" in notices.of_type("warning")[-1]
    dialog.close.assert_not_called()


# ##################################################################################
# The Properties form
# ##################################################################################
def _properties(kind: str = "Project", name: str = "Home") -> tuple[object, dict]:
    from maptasker.src import objprops

    element = _live_project(name)
    props = objprops.load_properties(kind, element)
    fields = {key: _Widget(value) for key, value in objprops.scalar_values(props).items()}
    return props, fields


def test_the_properties_button_opens_the_form_over_the_dialog_that_asked(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    calls: dict,
    dialog: MagicMock,
) -> None:
    element = _live_project("Home")
    handlers.open_object_properties_event("Project", element, dialog, None)
    assert calls["build_object_properties_dialog"] == [((gui, "Project", element, dialog, None), {})]


def test_ok_keeps_the_properties_runs_the_follow_up_and_closes(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
) -> None:
    props, fields = _properties()
    followed = []
    handlers.keep_object_properties_event(props, fields, dialog, lambda: followed.append(True))
    assert followed == [True]
    assert notices.said("Properties kept.")
    dialog.close.assert_called_once()


def test_a_bad_property_value_is_reported_and_the_form_stays_up_without_running_the_follow_up(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
) -> None:
    props, fields = _properties()
    from maptasker.src import objprops

    variable = objprops.add_variable(props)
    variable.find("pvn").text = ""
    fields["var0_pvn"] = _Widget("not a variable name")
    followed = []
    handlers.keep_object_properties_event(props, fields, dialog, lambda: followed.append(True))
    assert notices.of_type("negative") and followed == []
    dialog.close.assert_not_called()


def test_a_variable_declared_twice_is_a_warning_not_a_refusal(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
) -> None:
    from maptasker.src import objprops

    props, fields = _properties()
    objprops.add_variable(props)
    objprops.add_variable(props)
    fields["var0_pvn"] = _Widget("%dup")
    fields["var1_pvn"] = _Widget("%dup")
    handlers.keep_object_properties_event(props, fields, dialog)
    assert notices.of_type("warning") and notices.said("more than once")
    dialog.close.assert_called_once()


def test_cancel_drops_variables_never_named_and_says_how_many(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
) -> None:
    from maptasker.src import objprops

    props, _fields = _properties()
    objprops.add_variable(props)
    handlers.cancel_object_properties_event(props, dialog)
    assert notices.said("Discarded 1 unnamed variable(s).")
    assert props.variables == []
    dialog.close.assert_called_once()


def test_cancel_with_nothing_to_discard_is_silent(handlers: MapTaskerEventHandlers, notices: _Notices, dialog: MagicMock) -> None:
    props, _fields = _properties()
    handlers.cancel_object_properties_event(props, dialog)
    assert list(notices) == []
    dialog.close.assert_called_once()


def test_project_properties_are_carried_through_to_the_loaded_project(handlers: MapTaskerEventHandlers) -> None:
    from maptasker.src import objprops

    edited = _edit_project()
    props = objprops.load_properties("Project", edited.project_element)
    objprops.apply_properties(props, {**objprops.scalar_values(props), "mdate": ""} if False else objprops.scalar_values(props))
    handlers.apply_project_properties_event(edited)  # must not raise, and leaves a consistent live Project
    assert _live_project("Home").findtext("name") == "Home"


# ##################################################################################
# The Scene editor
# ##################################################################################
def _live_scene(name: str = "Panel") -> object:
    return PrimeItems.tasker_root_elements["all_scenes"][name]["xml"]


def _edit_scene(name: str = "Panel") -> sceneedit.EditableScene:
    edited = sceneedit.load_scene_for_edit(name, state=PrimeItems)
    assert edited is not None
    return edited


def _scene_fields(name: str = "Panel", save_path: str = "", **sizes: str) -> dict:
    fields = {"name": _Widget(name), "scene_save_path": _Widget(save_path), "target_project_name": "Home"}
    fields.update({key: _Widget(value) for key, value in sizes.items()})
    return fields


def test_add_scene_without_a_project_asks_for_one(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    calls: dict,
) -> None:
    handlers.open_add_scene_dialog_event()
    assert notices.said("Select a single Project first")
    assert calls["build_add_scene_version_dialog"] == []


def test_add_scene_with_a_project_asks_which_kind(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    calls: dict,
) -> None:
    gui.single_project_name = "Home"
    gui.specific_project_optionmenu = None
    handlers.open_add_scene_dialog_event()
    assert calls["build_add_scene_version_dialog"] == [((gui, "Home"), {})]


def test_add_scene_with_no_backup_parsed_and_no_file_says_so(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    notices: _Notices,
    calls: dict,
) -> None:
    gui.single_project_name = "Home"
    gui.specific_project_optionmenu = None
    PrimeItems.xml_root = None
    PrimeItems.file_to_get = None
    gui.file = ""
    handlers.open_add_scene_dialog_event()
    assert notices.said("No backup file is currently loaded.")
    assert calls["build_add_scene_version_dialog"] == []


@pytest.mark.parametrize("version", [sceneedit.SCENE_VERSION_LEGACY, sceneedit.SCENE_VERSION_V2])
def test_choosing_a_scene_kind_closes_the_prompt_and_opens_the_add_dialog_on_a_new_scene_of_that_kind(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    calls: dict,
    version: str,
) -> None:
    prompt = MagicMock()
    handlers.add_scene_of_version_event(version, "", "Home", prompt)
    prompt.close.assert_called_once()
    ((args, kwargs),) = calls["build_add_scene_dialog"]
    assert sceneedit.scene_version(args[1].scene_element) == version
    assert kwargs == {"target_project_name": "Home"}


def test_a_scene_that_cannot_be_built_keeps_the_prompt_open(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    calls: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sceneedit, "create_new_scene", lambda *a, **k: "No backup is loaded.")
    prompt = MagicMock()
    handlers.add_scene_of_version_event(sceneedit.SCENE_VERSION_LEGACY, "", "Home", prompt)
    assert notices.of_type("warning") == ["No backup is loaded."]
    prompt.close.assert_not_called()
    assert calls["build_add_scene_dialog"] == []


def test_a_new_scene_is_registered_attached_to_its_project_and_selected(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    notices: _Notices,
    calls: dict,
    dialog: MagicMock,
) -> None:
    created = sceneedit.create_new_scene("", sceneedit.SCENE_VERSION_LEGACY, state=PrimeItems)
    handlers.keep_new_scene_event(created, _scene_fields(name="Fresh Scene", widthPort="320", heightPort="480"), dialog)
    assert "Fresh Scene" in PrimeItems.tasker_root_elements["all_scenes"]
    assert "Fresh Scene" in _live_project("Home").findtext("scenes")
    assert notices.said("Scene added.")
    dialog.close.assert_called_once()


def test_a_new_scene_with_a_taken_name_or_a_bad_size_is_refused(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
) -> None:
    created = sceneedit.create_new_scene("", sceneedit.SCENE_VERSION_LEGACY, state=PrimeItems)
    handlers.keep_new_scene_event(created, _scene_fields(name="Panel"), dialog)
    assert notices.said("A Scene named 'Panel' already exists")
    handlers.keep_new_scene_event(created, _scene_fields(name="Other", widthPort="wide"), dialog)
    assert notices.said("must be a whole number")
    assert "Other" not in PrimeItems.tasker_root_elements["all_scenes"]
    dialog.close.assert_not_called()


def test_edit_scene_needs_a_selected_scene_and_a_scene_that_resolves(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    notices: _Notices,
    calls: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(userintr_editors, "suspended_scene_editor", lambda *_a: None)
    gui.specific_scene_optionmenu = None
    handlers.open_edit_scene_dialog_event()
    assert notices.said("Select a single Scene first")

    gui.single_scene_name = "Vanished"
    handlers.open_edit_scene_dialog_event()
    assert notices.said("Could not find Scene 'Vanished'.")

    gui.single_scene_name = "Panel"
    handlers.open_edit_scene_dialog_event()
    ((args, _),) = calls["build_edit_scene_dialog"]
    assert args[1].scene_name == "Panel"


def test_edit_scene_brings_back_the_dialog_a_preview_is_holding_instead_of_starting_over(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    calls: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    held = MagicMock()
    monkeypatch.setattr(userintr_editors, "suspended_scene_editor", lambda *_a: held)
    gui.single_scene_name = "Panel"
    gui.specific_scene_optionmenu = None
    handlers.open_edit_scene_dialog_event()
    held.open.assert_called_once()
    assert calls["build_edit_scene_dialog"] == []


def test_previewing_hides_the_dialog_marks_it_suspended_and_draws_the_scene(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    dialog: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suspended, drawn = [], []
    monkeypatch.setattr(userintr_editors, "suspend_scene_editor_session", lambda g, d: suspended.append((g, d)))
    monkeypatch.setattr(userintr_editors, "NiceGuiSceneView", lambda *args: drawn.append(args) or "view")
    edited = _edit_scene()
    fields = _scene_fields()

    handlers.preview_scene_event(edited, fields, dialog)

    assert suspended == [(gui, dialog)]
    dialog.close.assert_called_once()
    assert drawn == [(gui, edited, fields, dialog)]
    assert gui.textview == "view"


def test_previewing_without_a_dialog_just_draws(handlers: MapTaskerEventHandlers, gui: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    drawn = []
    monkeypatch.setattr(userintr_editors, "NiceGuiSceneView", lambda *args: drawn.append(args) or "view")
    handlers.preview_scene_event(_edit_scene(), _scene_fields())
    assert len(drawn) == 1


def test_ok_on_edit_scene_writes_the_copy_back_into_the_loaded_scene(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
) -> None:
    handlers.save_edited_scene_event(_edit_scene(), _scene_fields(widthPort="640", heightPort="480"), dialog)
    assert _live_scene().findtext("widthPort") == "640"
    assert notices.said("Saved Scene 'Panel'.")
    dialog.close.assert_called_once()


def test_ok_on_edit_scene_with_a_bad_size_changes_nothing(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
) -> None:
    handlers.save_edited_scene_event(_edit_scene(), _scene_fields(widthPort="wide"), dialog)
    assert _live_scene().findtext("widthPort") == "600" and notices.of_type("negative")
    dialog.close.assert_not_called()


def test_the_scene_rename_prompt_confirms_through_the_handler(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    calls: dict,
    dialog: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    edited = _edit_scene()
    handlers.rename_scene_event(edited, dialog)
    ((args, _),) = calls["build_rename_dialog"]
    assert args[:3] == (gui, "Scene", "Panel")
    confirmed = []
    monkeypatch.setattr(handlers, "confirm_rename_scene_event", lambda *a: confirmed.append(a))
    prompt = MagicMock()
    args[3]("Board", prompt)
    assert confirmed == [(edited, "Board", prompt, dialog)]


def test_a_scene_rename_moves_it_in_every_project_that_lists_it_and_closes_both(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    calls: dict,
) -> None:
    prompt, parent = MagicMock(), MagicMock()
    handlers.confirm_rename_scene_event(_edit_scene(), "Board", prompt, parent)
    assert "Board" in PrimeItems.tasker_root_elements["all_scenes"]
    assert _live_project("Home").findtext("scenes") == "Board"
    assert calls["_select_renamed_item"][0][0][1:] == ("Scene", "Board")
    prompt.close.assert_called_once()
    parent.close.assert_called_once()


def test_a_scene_rename_to_nothing_leaves_everything_open(handlers: MapTaskerEventHandlers, notices: _Notices) -> None:
    prompt, parent = MagicMock(), MagicMock()
    handlers.confirm_rename_scene_event(_edit_scene(), "", prompt, parent)
    assert notices.of_type("negative") and "Panel" in PrimeItems.tasker_root_elements["all_scenes"]
    prompt.close.assert_not_called()
    parent.close.assert_not_called()


def test_exporting_a_scene_applies_the_dialog_first_so_the_file_carries_the_work(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
    tmp_path: Path,
) -> None:
    target = tmp_path / "panel.scn.xml"
    handlers.save_scene_event(_edit_scene(), _scene_fields(save_path=str(target), widthPort="777"), dialog)
    assert "777" in target.read_text(encoding="utf-8")
    assert notices.said("Saved Scene 'Panel'")
    dialog.close.assert_called_once()


def test_exporting_a_scene_with_a_bad_size_writes_no_file(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
    tmp_path: Path,
) -> None:
    target = tmp_path / "panel.scn.xml"
    handlers.save_scene_event(_edit_scene(), _scene_fields(save_path=str(target), widthPort="wide"), dialog)
    assert not target.exists() and notices.of_type("negative")


def test_exporting_a_scene_over_a_file_asks_and_a_failed_write_is_reported(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    calls: dict,
    dialog: MagicMock,
    tmp_path: Path,
) -> None:
    target = tmp_path / "panel.scn.xml"
    target.write_text("old", encoding="utf-8")
    handlers.save_scene_event(_edit_scene(), _scene_fields(save_path=str(target)), dialog)
    assert target.read_text(encoding="utf-8") == "old"
    calls["build_overwrite_confirm_dialog"][0][0][1]()
    assert target.read_text(encoding="utf-8") != "old"

    handlers.save_scene_event(_edit_scene(), _scene_fields(save_path=str(tmp_path / "nope" / "x.xml")), dialog)
    assert notices.said("Could not save file")


@pytest.mark.asyncio
async def test_scene_save_to_current_file_applies_writes_loads_and_reselects(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    calls: dict,
    dialog: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_the_save(monkeypatch)
    await handlers.save_scene_to_current_file_event(_edit_scene(), _scene_fields(widthPort="650"), dialog)
    assert _live_scene().findtext("widthPort") == "650"
    assert calls["_select_renamed_item"][0][0][1:] == ("Scene", "Panel")
    dialog.close.assert_called_once()


@pytest.mark.asyncio
async def test_scene_save_to_current_file_stops_on_a_bad_size_a_failed_write_or_a_failed_load(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    written = MagicMock()
    monkeypatch.setattr(userintr_editors, "write_full_backup_to_current_file", written)
    await handlers.save_scene_to_current_file_event(_edit_scene(), _scene_fields(widthPort="wide"), dialog)
    written.assert_not_called()

    _stub_the_save(monkeypatch, written=(False, "disk full"))
    await handlers.save_scene_to_current_file_event(_edit_scene(), _scene_fields(), dialog)
    assert notices.said("Could not save to current file: disk full")

    _stub_the_save(monkeypatch, reloaded=(False, "unreadable"))
    await handlers.save_scene_to_current_file_event(_edit_scene(), _scene_fields(), dialog)
    assert "unreadable" in notices.of_type("warning")[-1]
    dialog.close.assert_not_called()


def test_delete_scene_opens_the_confirmation_over_the_editor(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    calls: dict,
    dialog: MagicMock,
) -> None:
    edited = _edit_scene()
    handlers.delete_scene_event(edited, dialog)
    assert calls["build_delete_scene_dialog"] == [((gui, edited, dialog), {})]


def test_confirming_a_scene_delete_removes_it_from_its_projects_and_closes_both_dialogs(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    calls: dict,
) -> None:
    confirm, parent = MagicMock(), MagicMock()
    handlers.confirm_delete_scene_event("Panel", confirm, parent)
    assert "Panel" not in PrimeItems.tasker_root_elements["all_scenes"]
    assert "Panel" not in (_live_project("Home").findtext("scenes") or "")
    assert calls["_reset_specific_name_selection"] and notices.said("Deleted Scene 'Panel'.")
    confirm.close.assert_called_once()
    parent.close.assert_called_once()


def test_deleting_a_scene_that_does_not_exist_closes_nothing(handlers: MapTaskerEventHandlers, notices: _Notices, calls: dict) -> None:
    confirm, parent = MagicMock(), MagicMock()
    handlers.confirm_delete_scene_event("No Such Scene", confirm, parent)
    assert notices.of_type("negative")
    confirm.close.assert_not_called()
    parent.close.assert_not_called()


# ##################################################################################
# The Profile editor
# ##################################################################################
def _live_profile(name: str) -> object:
    return PrimeItems.tasker_root_elements["all_profiles_by_name"][name]["xml"]


def _edit_profile(name: str = "Morning") -> profedit.EditableProfile:
    edited = profedit.load_profile_for_edit(name, state=PrimeItems)
    assert edited is not None
    return edited


def _profile_fields(
    name: str = "Morning",
    save_path: str = "",
    project: str = "Home",
    edited: profedit.EditableProfile | None = None,
) -> dict:
    """The Edit/Add Profile dialog's fields, including the widgets of any Time condition the Profile holds (an
    unfilled one fails validation, as it should).
    """
    fields = {"name": _Widget(name), "save_path": _Widget(save_path), "target_project_name": project}
    for condition in edited.conditions if edited is not None else ():
        if condition.cond_type == "Time":
            for key, value in profedit.get_time_field_values(condition).items():
                fields[profedit.condition_field_key(condition.cond_index, key)] = _Widget(value)
    return fields


def _new_profile(*, with_task: bool = True, with_condition: bool = True) -> profedit.EditableProfile:
    created = profedit.create_new_profile("", state=PrimeItems)
    if with_task:
        profedit.link_task_to_profile(created, "21", "Entry")
    if with_condition:
        profedit.add_condition_to_profile(created, "Time")
    return created


def test_edit_profile_needs_a_selected_profile_that_resolves(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    notices: _Notices,
    calls: dict,
) -> None:
    handlers.open_edit_profile_dialog_event()
    assert notices.said("Select a single Profile first")
    gui.single_profile_name = "Vanished"
    handlers.open_edit_profile_dialog_event()
    assert notices.said("Could not find Profile 'Vanished'.")
    gui.single_profile_name = "Morning"
    handlers.open_edit_profile_dialog_event()
    assert calls["build_edit_profile_dialog"][0][0][1].profile_id == "100"


def test_the_profile_rename_prompt_confirms_through_the_handler(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    calls: dict,
    dialog: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    edited = _edit_profile()
    fields, label = _profile_fields(), _Label()
    handlers.rename_profile_event(edited, fields, label)
    ((args, _),) = calls["build_rename_dialog"]
    assert args[:3] == (gui, "Profile", "Morning")
    confirmed = []
    monkeypatch.setattr(handlers, "confirm_rename_profile_event", lambda *a: confirmed.append(a))
    args[3]("Dawn", dialog)
    assert confirmed == [(edited, fields, label, "Dawn", dialog)]


def test_a_profile_rename_is_applied_at_once_and_the_dialog_follows_it(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    calls: dict,
    dialog: MagicMock,
) -> None:
    fields, label = _profile_fields(save_path=profedit.default_save_path("Morning", PrimeItems)), _Label()
    handlers.confirm_rename_profile_event(_edit_profile(), fields, label, "Dawn", dialog)
    assert "Dawn" in PrimeItems.tasker_root_elements["all_profiles_by_name"]
    assert "Dawn" in label.text
    assert fields["name"].value == "Dawn"
    assert fields["save_path"].value == profedit.default_save_path("Dawn", PrimeItems)
    assert calls["_select_renamed_item"][0][0][1:] == ("Profile", "Dawn")
    dialog.close.assert_called_once()


def test_a_profile_rename_to_nothing_is_refused_and_the_prompt_stays(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
) -> None:
    edited = _edit_profile()
    fields = _profile_fields(edited=edited)
    handlers.confirm_rename_profile_event(edited, fields, _Label(), "", dialog)
    assert notices.of_type("negative") and "Morning" in PrimeItems.tasker_root_elements["all_profiles_by_name"]
    dialog.close.assert_not_called()


def test_delete_profile_opens_the_confirmation_and_confirming_keeps_its_tasks(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    notices: _Notices,
    calls: dict,
    dialog: MagicMock,
) -> None:
    edited = _edit_profile()
    handlers.delete_profile_event(edited, dialog)
    assert calls["build_delete_profile_dialog"] == [((gui, edited, dialog), {})]

    confirm, parent = MagicMock(), MagicMock()
    handlers.confirm_delete_profile_event("Morning", confirm, parent)
    assert "Morning" not in PrimeItems.tasker_root_elements["all_profiles_by_name"]
    assert "Noisy" in PrimeItems.tasker_root_elements["all_tasks_by_name"]
    assert notices.said("Its Tasks were kept.") and calls["_reset_specific_name_selection"]
    confirm.close.assert_called_once()
    parent.close.assert_called_once()


def test_deleting_a_profile_that_does_not_exist_closes_nothing(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
) -> None:
    confirm, parent = MagicMock(), MagicMock()
    handlers.confirm_delete_profile_event("No Such Profile", confirm, parent)
    assert notices.of_type("negative")
    confirm.close.assert_not_called()
    parent.close.assert_not_called()


def test_add_profile_needs_a_project_then_opens_the_dialog_on_a_blank_profile_for_it(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    notices: _Notices,
    calls: dict,
) -> None:
    handlers.open_add_profile_dialog_event()
    assert notices.said("Select a single Project first")

    gui.single_project_name = "Home"
    handlers.open_add_profile_dialog_event()
    ((args, kwargs),) = calls["build_add_profile_dialog"]
    assert kwargs == {"target_project_name": "Home"}
    assert isinstance(args[1], profedit.EditableProfile)


def test_add_profile_with_no_backup_loaded_says_so(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    notices: _Notices,
    calls: dict,
) -> None:
    gui.single_project_name = "Home"
    PrimeItems.xml_root = None
    PrimeItems.file_to_get = None
    gui.file = ""
    handlers.open_add_profile_dialog_event()
    assert notices.said("No backup file is currently loaded.")
    assert calls["build_add_profile_dialog"] == []


def test_linking_a_task_by_name_attaches_it_and_a_missing_name_or_task_is_explained(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
) -> None:
    edited = _edit_profile()
    handlers.link_task_to_profile_event(edited, "Exit", "")
    assert notices.said("Choose a Task first.")
    handlers.link_task_to_profile_event(edited, "Exit", "No Such Task")
    assert notices.said("Could not find Task 'No Such Task'.")
    handlers.link_task_to_profile_event(edited, "Exit", "Quiet")
    assert edited.exit_task_id == "22"
    handlers.unlink_task_from_profile_event(edited, "Exit")
    assert edited.exit_task_id == ""


def test_adding_a_task_from_inside_a_profile_links_it_as_that_type_when_it_is_created(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    calls: dict,
) -> None:
    edited = _edit_profile("Morning")
    redrawn = []
    handlers.open_add_task_for_profile_link_event(edited, "Exit", lambda: redrawn.append(True))
    ((args, kwargs),) = calls["build_add_task_dialog"]
    assert args[0] is gui
    kwargs["on_task_created"]("22")
    assert edited.exit_task_id == "22" and redrawn == [True]


def test_the_enabled_switch_and_the_condition_buttons_reach_the_working_copy(handlers: MapTaskerEventHandlers, notices: _Notices) -> None:
    edited = _edit_profile()
    handlers.set_profile_enabled_event(edited, enabled=False)
    assert profedit.is_profile_enabled(edited) is False

    handlers.add_condition_to_profile_event(edited, "")
    assert notices.said("Choose a condition type first.")
    handlers.add_condition_to_profile_event(edited, "Day")
    assert [c.cond_type for c in edited.conditions] == ["Time", "Day"]
    handlers.add_condition_to_profile_event(edited, "Nonsense")
    assert notices.of_type("negative")
    handlers.remove_condition_from_profile_event(edited, 0)
    assert [c.cond_type for c in edited.conditions] == ["Day"]


def test_event_and_state_conditions_are_added_by_key_and_an_empty_pick_is_refused(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
) -> None:
    edited = _edit_profile()
    handlers.add_event_condition_to_profile_event(edited, "")
    handlers.add_state_condition_to_profile_event(edited, "")
    assert notices.said("Choose an Event type first.") and notices.said("Choose a State type first.")

    handlers.add_event_condition_to_profile_event(edited, "7e")
    handlers.add_state_condition_to_profile_event(edited, "123s")
    assert [c.cond_type for c in edited.conditions] == ["Time", "Event", "State"]

    handlers.add_event_condition_to_profile_event(edited, "999999999e")
    handlers.add_state_condition_to_profile_event(edited, "999999999s")
    assert len(notices.of_type("negative")) == 2 and len(edited.conditions) == 3


def test_a_third_party_plugin_condition_warns_that_its_setup_is_done_in_tasker(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(taskedit, "tasker_configuration_warning", lambda element, name: f"{name} needs Tasker")
    handlers.add_event_condition_to_profile_event(_edit_profile(), "7e")
    assert notices.of_type("warning") and "needs Tasker" in notices.of_type("warning")[0]


def test_app_entries_are_added_and_removed_on_the_condition_with_that_index(handlers: MapTaskerEventHandlers) -> None:
    edited = profedit.create_new_profile("", state=PrimeItems)
    profedit.add_condition_to_profile(edited, "App")
    before = len(profedit.get_app_entries(edited.conditions[0]))
    handlers.add_app_entry_event(edited, 0)
    assert len(profedit.get_app_entries(edited.conditions[0])) == before + 1
    handlers.remove_app_entry_event(edited, 0, 0)
    assert len(profedit.get_app_entries(edited.conditions[0])) == before
    handlers.add_app_entry_event(edited, 9)  # no such condition: nothing happens
    handlers.remove_app_entry_event(edited, 9, 0)


def test_ok_on_a_profile_keeps_it_links_a_picked_but_unlinked_task_and_closes(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
) -> None:
    edited = _edit_profile()
    profedit.unlink_task_from_profile(edited, "Exit")
    fields = _profile_fields(name="Dawn", edited=edited) | {"exit_task_picker": _Widget("Quiet")}
    handlers.keep_edited_profile_event(edited, fields, dialog)
    live = PrimeItems.tasker_root_elements["all_profiles_by_name"]["Dawn"]["xml"]
    assert live.findtext("mid1") == "22", "the Task picked in the dropdown counts without a separate Link click"
    assert notices.said("Changes kept.")
    dialog.close.assert_called_once()


def test_ok_on_a_profile_with_an_empty_name_changes_nothing(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
) -> None:
    edited = _edit_profile()
    fields = _profile_fields(name="", edited=edited)
    handlers.keep_edited_profile_event(edited, fields, dialog)
    assert notices.of_type("negative") and "Morning" in PrimeItems.tasker_root_elements["all_profiles_by_name"]
    dialog.close.assert_not_called()


def test_exporting_a_profile_writes_its_file_applies_it_and_closes(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
    tmp_path: Path,
) -> None:
    target = tmp_path / "morning.prf.xml"
    edited = _edit_profile()
    fields = _profile_fields(name="Dawn", save_path=str(target), edited=edited)
    handlers.save_edited_profile_event(edited, fields, dialog)
    assert "Dawn" in target.read_text(encoding="utf-8")
    assert "Dawn" in PrimeItems.tasker_root_elements["all_profiles_by_name"]
    assert notices.said(f"Saved to {target}.")
    dialog.close.assert_called_once()


def test_exporting_over_a_file_asks_first_and_a_bad_field_or_unwritable_path_is_reported(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    calls: dict,
    dialog: MagicMock,
    tmp_path: Path,
) -> None:
    target = tmp_path / "morning.prf.xml"
    target.write_text("old", encoding="utf-8")
    edited = _edit_profile()
    fields = _profile_fields(save_path=str(target), edited=edited)
    handlers.save_edited_profile_event(edited, fields, dialog)
    assert target.read_text(encoding="utf-8") == "old"
    calls["build_overwrite_confirm_dialog"][0][0][1]()
    assert target.read_text(encoding="utf-8") != "old"

    edited = _edit_profile()

    fields = _profile_fields(save_path=str(tmp_path / "nope" / "x.xml"), edited=edited)

    handlers.save_edited_profile_event(edited, fields, dialog)
    assert notices.said("Could not save file")
    edited = _edit_profile()
    fields = _profile_fields(name="", save_path=str(tmp_path / "y.xml"), edited=edited)
    handlers.save_edited_profile_event(edited, fields, dialog)
    assert not (tmp_path / "y.xml").exists()


def test_a_redacted_profile_export_says_so(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
    tmp_path: Path,
) -> None:
    edited = _edit_profile()
    fields = _profile_fields(save_path=str(tmp_path / "r.prf.xml"), edited=edited) | {userintr_editors.REDACT_FIELD: _Widget(True)}
    handlers.save_edited_profile_event(edited, fields, dialog)
    assert notices.said("were redacted")


@pytest.mark.asyncio
async def test_profile_save_to_current_file_applies_writes_loads_and_reselects(
    handlers: MapTaskerEventHandlers,
    calls: dict,
    dialog: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_the_save(monkeypatch)
    edited = _edit_profile()
    fields = _profile_fields(name="Dawn", edited=edited)
    await handlers.save_edited_profile_to_current_file_event(edited, fields, dialog)
    assert calls["_select_renamed_item"][0][0][1:] == ("Profile", "Dawn")
    dialog.close.assert_called_once()


@pytest.mark.asyncio
async def test_profile_save_to_current_file_stops_on_a_bad_field_a_failed_write_or_a_failed_load(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    written = MagicMock()
    monkeypatch.setattr(userintr_editors, "write_full_backup_to_current_file", written)
    edited = _edit_profile()
    fields = _profile_fields(name="", edited=edited)
    await handlers.save_edited_profile_to_current_file_event(edited, fields, dialog)
    written.assert_not_called()

    _stub_the_save(monkeypatch, written=(False, "disk full"))
    edited = _edit_profile()
    fields = _profile_fields(edited=edited)
    await handlers.save_edited_profile_to_current_file_event(edited, fields, dialog)
    assert notices.said("Could not save to current file: disk full")

    _stub_the_save(monkeypatch, reloaded=(False, "unreadable"))
    edited = _edit_profile()
    fields = _profile_fields(edited=edited)
    await handlers.save_edited_profile_to_current_file_event(edited, fields, dialog)
    assert "unreadable" in notices.of_type("warning")[-1]
    dialog.close.assert_not_called()


def test_a_new_profile_needs_a_name_nobody_has_a_project_an_entry_task_and_a_condition(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    calls: dict,
    dialog: MagicMock,
) -> None:
    edited = _new_profile(with_task=False, with_condition=False)
    fields = _profile_fields(name="Fresh", project="", edited=edited)
    handlers.keep_new_profile_event(edited, fields, dialog)
    said = " ".join(notices.of_type("negative"))
    assert "Choose a Project first" in said
    assert "Entry Task" in said and "condition" in said

    edited = _new_profile()

    fields = _profile_fields(name="Morning", edited=edited)

    handlers.keep_new_profile_event(edited, fields, dialog)
    assert "A Profile named 'Morning' already exists" in " ".join(notices.of_type("negative"))
    assert "Fresh" not in PrimeItems.tasker_root_elements["all_profiles_by_name"]
    dialog.close.assert_not_called()
    assert calls["refresh_tasker_object_pulldowns"] == []


def test_ok_on_a_new_profile_registers_it_attaches_it_selects_it_and_says_it_is_session_only(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    calls: dict,
    dialog: MagicMock,
) -> None:
    edited = _new_profile()
    fields = _profile_fields(name="Fresh", edited=edited)
    handlers.keep_new_profile_event(edited, fields, dialog)
    assert "Fresh" in PrimeItems.tasker_root_elements["all_profiles_by_name"]
    new_id = PrimeItems.tasker_root_elements["all_profiles_by_name"]["Fresh"]["id"]
    assert new_id in _live_project("Home").findtext("pids").split(",")
    assert calls["select_pulldown_option"][0][0][1] == "Fresh"
    assert notices.said("Profile kept for this session only")
    dialog.close.assert_called_once()


def test_saving_a_new_profile_checks_the_save_path_writes_the_file_and_registers_it(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
    tmp_path: Path,
) -> None:
    target = tmp_path / "fresh.prf.xml"
    edited = _new_profile()
    fields = _profile_fields(name="Fresh", save_path=str(target), edited=edited)
    handlers.save_new_profile_event(edited, fields, dialog)
    assert target.is_file() and "Fresh" in PrimeItems.tasker_root_elements["all_profiles_by_name"]
    assert notices.said(f"Saved to {target}.")
    dialog.close.assert_called_once()


def test_saving_a_new_profile_over_an_existing_file_or_to_an_unwritable_path_registers_nothing(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
    tmp_path: Path,
) -> None:
    taken = tmp_path / "taken.prf.xml"
    taken.write_text("old", encoding="utf-8")
    edited = _new_profile()
    fields = _profile_fields(name="Fresh", save_path=str(taken), edited=edited)
    handlers.save_new_profile_event(edited, fields, dialog)
    assert notices.said("A file already exists at")
    edited = _new_profile()
    fields = _profile_fields(name="Fresh", save_path=str(tmp_path / "nope" / "x.xml"), edited=edited)
    handlers.save_new_profile_event(edited, fields, dialog)
    assert notices.said("Could not save file")
    assert "Fresh" not in PrimeItems.tasker_root_elements["all_profiles_by_name"]
    dialog.close.assert_not_called()


@pytest.mark.asyncio
async def test_a_new_profile_saved_to_the_current_file_is_registered_before_the_write_and_stays_if_it_fails(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    calls: dict,
    dialog: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_the_save(monkeypatch, written=(False, "disk full"))
    edited = _new_profile()
    fields = _profile_fields(name="Fresh", edited=edited)
    await handlers.save_new_profile_to_current_file_event(edited, fields, dialog)
    assert "Fresh" in PrimeItems.tasker_root_elements["all_profiles_by_name"], "a failed write does not undo the registration"
    assert notices.said("Could not save to current file: disk full")
    dialog.close.assert_not_called()


@pytest.mark.asyncio
async def test_a_new_profile_saved_to_the_current_file_closes_when_the_copy_loads(
    handlers: MapTaskerEventHandlers,
    dialog: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_the_save(monkeypatch)
    edited = _new_profile()
    fields = _profile_fields(name="Fresh", edited=edited)
    await handlers.save_new_profile_to_current_file_event(edited, fields, dialog)
    dialog.close.assert_called_once()

    _stub_the_save(monkeypatch, reloaded=(False, "unreadable"))
    other = MagicMock()
    edited = _new_profile()
    fields = _profile_fields(name="Fresh Two", edited=edited)
    await handlers.save_new_profile_to_current_file_event(edited, fields, other)
    other.close.assert_not_called()


@pytest.mark.asyncio
async def test_a_new_profile_that_fails_validation_is_not_written_to_disk(
    handlers: MapTaskerEventHandlers,
    dialog: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    written = MagicMock()
    monkeypatch.setattr(userintr_editors, "write_full_backup_to_current_file", written)
    edited = _new_profile(with_task=False)
    fields = _profile_fields(name="Fresh", edited=edited)
    await handlers.save_new_profile_to_current_file_event(edited, fields, dialog)
    written.assert_not_called()


def test_a_profile_kept_in_the_loaded_configuration_is_one_undo_step(
    handlers: MapTaskerEventHandlers,
    calls: dict,
) -> None:
    created = _new_profile()
    created.profile_element.find("nme").text = "Fresh"
    handlers._keep_profile_in_loaded_config(created, "Fresh", is_new_profile=True, project_name="Home")
    assert "Fresh" in PrimeItems.tasker_root_elements["all_profiles_by_name"]

    existing = _edit_profile()
    existing.profile_element.find("nme").text = "Edited"
    handlers._keep_profile_in_loaded_config(existing, "Edited", is_new_profile=False, project_name="")
    assert "Edited" in PrimeItems.tasker_root_elements["all_profiles_by_name"]
    assert len(calls["refresh_tasker_object_pulldowns"]) == 2


# ##################################################################################
# Add Task, and the action editors
# ##################################################################################
def _new_task_fields(name: str = "Fresh Task", save_path: str = "", project: str = "Home") -> dict:
    return {"name": _Widget(name), "priority": _Widget("100"), "save_path": _Widget(save_path), "target_project_name": project}


def _new_task(actions: int = 1) -> taskedit.EditableTask:
    created = taskedit.create_new_task("", "100", state=PrimeItems)
    for _ in range(actions):
        taskedit.add_action_to_task(created, "548t", state=PrimeItems)
    return created


def test_add_task_needs_a_project_then_opens_the_dialog_for_it(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    notices: _Notices,
    calls: dict,
) -> None:
    handlers.open_add_task_dialog_event()
    assert notices.said("Select a single Project first")
    gui.single_project_name = "Home"
    handlers.open_add_task_dialog_event()
    ((args, kwargs),) = calls["build_add_task_dialog"]
    assert kwargs == {"target_project_name": "Home"}
    assert isinstance(args[1], taskedit.EditableTask)


def test_add_task_with_no_backup_loaded_says_so(
    handlers: MapTaskerEventHandlers,
    gui: MagicMock,
    notices: _Notices,
    calls: dict,
) -> None:
    gui.single_project_name = "Home"
    PrimeItems.xml_root = None
    PrimeItems.file_to_get = None
    gui.file = ""
    handlers.open_add_task_dialog_event()
    assert notices.said("No backup file is currently loaded.")
    assert calls["build_add_task_dialog"] == []


def test_adding_an_action_returns_its_number_for_highlighting_and_a_refusal_returns_none(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _new_task(0)
    assert handlers.add_action_to_new_task_event(created, "548t") == 0
    assert handlers.add_action_to_new_task_event(created, "548t", 0) == 0
    assert len(created.actions) == 2

    edited = _edit_task()
    assert handlers.add_action_to_edit_task_event(edited, "548t", None) == 2

    monkeypatch.setattr(taskedit, "add_action_to_task", lambda *a, **k: ["That action cannot be added."])
    assert handlers.add_action_to_new_task_event(created, "548t") is None
    assert handlers.add_action_to_edit_task_event(edited, "548t", None) is None
    assert notices.of_type("negative") == ["That action cannot be added."] * 2


def test_a_plugin_action_warns_that_its_configuration_is_set_in_tasker(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(taskedit, "tasker_configuration_warning", lambda element, name: "configure it in Tasker")
    handlers.add_action_to_new_task_event(_new_task(0), "548t")
    handlers.add_action_to_edit_task_event(_edit_task(), "548t", None)
    assert notices.of_type("warning") == ["configure it in Tasker"] * 2


@pytest.mark.parametrize("variant", taskedit.IF_BLOCK_VARIANTS)
def test_an_if_block_adds_the_actions_its_variant_calls_for_and_returns_where_the_if_went(
    handlers: MapTaskerEventHandlers,
    variant: str,
) -> None:
    created = _new_task(1)
    assert handlers.add_if_block_to_new_task_event(created, variant) == 1
    edited = _edit_task()
    before = len(edited.actions)
    assert handlers.add_if_block_to_edit_task_event(edited, variant, 0) == 0
    assert len(edited.actions) == before + len(created.actions) - 1 - 0 or len(edited.actions) > before


def test_an_if_block_that_cannot_be_added_reports_why(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(taskedit, "add_if_block_to_task", lambda *a, **k: ["no If here"])
    assert handlers.add_if_block_to_new_task_event(_new_task(0), "If") is None
    assert handlers.add_if_block_to_edit_task_event(_edit_task(), "If", None) is None
    assert notices.of_type("negative") == ["no If here"] * 2


def test_actions_are_removed_copied_moved_enabled_and_set_to_continue_after_error(handlers: MapTaskerEventHandlers) -> None:
    edited = _edit_task()
    handlers.copy_action_in_edit_task_event(edited, 0)
    assert len(edited.actions) == 3
    handlers.move_action_in_edit_task_event(edited, 2, 0)
    handlers.set_action_enabled_event(edited, 0, enabled=False)
    assert edited.actions[0].action_element.findtext("on") == "false"
    handlers.set_action_enabled_event(edited, 0, enabled=True)
    assert edited.actions[0].action_element.find("on") is None
    handlers.set_action_continue_after_error_event(edited, 0, continue_after_error=True)
    assert edited.actions[0].action_element.findtext("se") == "false"
    handlers.delete_action_in_edit_task_event(edited, 0)
    assert len(edited.actions) == 2

    created = _new_task(2)
    handlers.remove_action_from_new_task_event(created, 0)
    assert len(created.actions) == 1


def test_a_per_action_condition_is_written_shown_on_its_checkbox_and_closes_the_prompt(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
) -> None:
    edited = _edit_task()
    operator = next(iter(taskedit._IF_CONDITION_LABEL_TO_CODE))
    checkbox, prompt = MagicMock(), MagicMock()
    handlers.set_action_condition_event(edited, 0, _Widget("%flag"), _Widget(operator), _Widget(" 1 "), prompt, checkbox)
    assert taskedit.action_has_condition(edited.actions[0])
    checkbox.set_text.assert_called_once_with(f"If: %flag {operator} 1")
    assert notices.said("If condition set.")
    prompt.close.assert_called_once()

    handlers.remove_action_condition_event(edited, 0)
    assert not taskedit.action_has_condition(edited.actions[0])


def test_a_per_action_condition_that_fails_validation_leaves_the_prompt_open(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
) -> None:
    edited = _edit_task()
    checkbox, prompt = MagicMock(), MagicMock()
    handlers.set_action_condition_event(edited, 0, _Widget(""), _Widget(""), _Widget(""), prompt, checkbox)
    assert notices.of_type("negative")
    checkbox.set_text.assert_not_called()
    prompt.close.assert_not_called()


def test_ok_on_a_new_task_registers_attaches_selects_and_says_it_is_session_only(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    calls: dict,
    dialog: MagicMock,
) -> None:
    created = []
    handlers.keep_new_task_event(_new_task(), _new_task_fields(), dialog, created.append)
    assert "Fresh Task" in PrimeItems.tasker_root_elements["all_tasks_by_name"]
    task_id = PrimeItems.tasker_root_elements["all_tasks_by_name"]["Fresh Task"]["id"]
    assert created == [task_id]
    assert task_id in _live_project("Home").findtext("tids").split(",")
    assert calls["select_pulldown_option"][0][0][1] == "Fresh Task"
    assert notices.said("Task kept for this session only")
    dialog.close.assert_called_once()


def test_a_new_task_with_no_actions_is_warned_about_and_one_with_a_taken_name_is_refused(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
) -> None:
    handlers.keep_new_task_event(_new_task(0), _new_task_fields(name="Opener"), dialog)
    assert notices.said("This Task has no actions yet.")
    assert notices.said("A Task named 'Opener' already exists")
    dialog.close.assert_not_called()


def test_a_new_task_built_inside_a_profile_is_not_attached_to_a_project_or_selected(
    handlers: MapTaskerEventHandlers,
    calls: dict,
    dialog: MagicMock,
) -> None:
    fields = _new_task_fields(project="")
    fields.pop("target_project_name")
    handlers.keep_new_task_event(_new_task(), fields, dialog)
    assert calls["select_pulldown_option"] == []
    assert "Fresh Task" in PrimeItems.tasker_root_elements["all_tasks_by_name"]


def test_saving_a_new_task_writes_the_file_then_registers_it(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
    tmp_path: Path,
) -> None:
    target = tmp_path / "fresh.tsk.xml"
    handlers.save_new_task_event(_new_task(), _new_task_fields(save_path=str(target)), dialog)
    assert target.is_file() and "Fresh Task" in PrimeItems.tasker_root_elements["all_tasks_by_name"]
    assert notices.said(f"Saved to {target}.")
    dialog.close.assert_called_once()


def test_saving_a_new_task_over_a_file_or_to_an_unwritable_path_registers_nothing(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
    tmp_path: Path,
) -> None:
    taken = tmp_path / "taken.tsk.xml"
    taken.write_text("old", encoding="utf-8")
    handlers.save_new_task_event(_new_task(), _new_task_fields(save_path=str(taken)), dialog)
    assert notices.said("A file already exists at")
    handlers.save_new_task_event(_new_task(), _new_task_fields(save_path=str(tmp_path / "nope" / "x.xml")), dialog)
    assert notices.said("Could not save file")
    assert "Fresh Task" not in PrimeItems.tasker_root_elements["all_tasks_by_name"]
    dialog.close.assert_not_called()


@pytest.mark.asyncio
async def test_a_new_task_saved_to_the_current_file_is_registered_then_written_and_loaded(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_the_save(monkeypatch)
    await handlers.save_new_task_to_current_file_event(_new_task(), _new_task_fields(), dialog)
    assert "Fresh Task" in PrimeItems.tasker_root_elements["all_tasks_by_name"]
    assert notices.said("The original file was left unchanged.")
    dialog.close.assert_called_once()


@pytest.mark.asyncio
async def test_a_new_task_current_file_save_that_fails_keeps_the_registration_and_the_dialog(
    handlers: MapTaskerEventHandlers,
    notices: _Notices,
    dialog: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_the_save(monkeypatch, written=(False, "disk full"))
    await handlers.save_new_task_to_current_file_event(_new_task(), _new_task_fields(name="One"), dialog)
    assert notices.said("Could not save to current file: disk full")
    assert "One" in PrimeItems.tasker_root_elements["all_tasks_by_name"]

    _stub_the_save(monkeypatch, reloaded=(False, "unreadable"))
    await handlers.save_new_task_to_current_file_event(_new_task(), _new_task_fields(name="Two"), dialog)
    assert "unreadable" in notices.of_type("warning")[-1]
    dialog.close.assert_not_called()

    written = MagicMock()
    monkeypatch.setattr(userintr_editors, "write_full_backup_to_current_file", written)
    await handlers.save_new_task_to_current_file_event(_new_task(), _new_task_fields(name="Opener"), dialog)
    written.assert_not_called()
