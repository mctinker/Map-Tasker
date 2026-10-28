"""The window's decisions that need no window: version checks, which model goes with which key, and name checks."""

from __future__ import annotations

import asyncio
import datetime
from types import SimpleNamespace
from typing import Any

import pytest
from maptasker.src.gui import guiutils
from maptasker.src.gui.userintr import MyGui

from tests.doubles import fake_state, fake_window


# ##################################################################################
# Versions
# ##################################################################################
@pytest.mark.parametrize(
    ("installed", "published", "newer"),
    [
        ("14.1.2", "14.1.3", True),
        ("14.1.2", "14.2.0", True),
        ("14.1.2", "15.0.0", True),
        ("14.1.2", "14.1.2", False),
        ("14.1.2", "14.1.1", False),
        ("14.1.2", "13.9.9", False),
        ("14.1", "14.1.1", True),  # the same numbers with more after them are later
        ("14.1.1", "14.1", False),
        ("14.1.2", "14.2.0b1", False),  # a beta is never offered as an upgrade
        ("14.2.0b1", "14.2.0", False),  # ...nor does a beta install get upgrade prompts
    ],
)
def test_a_published_version_is_newer_only_if_it_really_is(installed: str, published: str, newer: bool) -> None:
    assert guiutils.is_version_greater(installed, published) is newer


def test_a_newer_version_on_pypi_is_reported_and_the_check_is_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    state = fake_state(last_run=None)
    monkeypatch.setattr(guiutils, "get_pypi_version", lambda: "maptasker==99.0.0")
    monkeypatch.setattr(guiutils, "NOW_TIME", "now")
    assert guiutils.is_new_version(state) is True
    assert state.last_run == "now"


def test_pypi_not_answering_means_no_new_version(monkeypatch: pytest.MonkeyPatch) -> None:
    state = fake_state(last_run=None)
    monkeypatch.setattr(guiutils, "get_pypi_version", lambda: "")
    assert guiutils.is_new_version(state) is False
    assert state.last_run is None  # nothing was checked, so nothing is recorded


def test_the_current_version_is_not_new(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(guiutils, "get_pypi_version", lambda: f"maptasker=={guiutils.VERSION}")
    assert guiutils.is_new_version(fake_state(last_run=None)) is False


class _Day:
    """A clock that says it is a given day."""

    def __init__(self, day: str) -> None:
        self.day = datetime.date.fromisoformat(day)

    def now(self) -> datetime.datetime:
        return datetime.datetime.combine(self.day, datetime.time(12))


def test_the_first_check_of_the_day_is_the_first(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    marker = str(tmp_path / "last_run.txt")
    monkeypatch.setattr(guiutils, "clock", _Day("2026-10-14"))
    assert guiutils.is_first_run_today(marker) is True
    assert (tmp_path / "last_run.txt").read_text(encoding="utf-8") == "2026-10-14"


def test_a_second_check_the_same_day_is_not(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    marker = str(tmp_path / "last_run.txt")
    monkeypatch.setattr(guiutils, "clock", _Day("2026-10-14"))
    guiutils.is_first_run_today(marker)
    assert guiutils.is_first_run_today(marker) is False


def test_the_next_day_is_a_first_again(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    marker = str(tmp_path / "last_run.txt")
    monkeypatch.setattr(guiutils, "clock", _Day("2026-10-14"))
    guiutils.is_first_run_today(marker)
    monkeypatch.setattr(guiutils, "clock", _Day("2026-10-15"))
    assert guiutils.is_first_run_today(marker) is True


def test_a_version_check_that_failed_is_logged_not_lost(monkeypatch: pytest.MonkeyPatch) -> None:
    logged: list[str] = []
    monkeypatch.setattr(guiutils.logger, "exception", lambda message, **_kw: logged.append(message))

    async def fail() -> None:
        raise RuntimeError("pypi unreachable")

    async def run() -> None:
        task = asyncio.create_task(fail())
        await asyncio.wait([task])
        guiutils._report_version_check_failure(task)

    asyncio.run(run())
    assert logged == ["Checking for a new version failed"]


def test_a_version_check_that_was_cancelled_says_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    logged: list[str] = []
    monkeypatch.setattr(guiutils.logger, "exception", lambda message, **_kw: logged.append(message))

    async def run() -> None:
        task = asyncio.create_task(asyncio.sleep(10))
        task.cancel()
        await asyncio.wait([task])
        guiutils._report_version_check_failure(task)

    asyncio.run(run())
    assert logged == []


# ##################################################################################
# The model pulldown
# ##################################################################################
def test_models_are_prefixed_with_their_provider_and_sorted() -> None:
    assert guiutils.prefix_and_sort(["b", "a"], "OpenAI") == ["OpenAI: a", "OpenAI: b"]


def test_switching_lists_keeps_the_chosen_model_selected() -> None:
    """The extended list marks an installed Ollama model, and a pulldown whose value is not among its
    options goes blank -- which looked as though switching lists had thrown the choice away."""
    gui = fake_window(ai_model="phi4", ai_model_option=SimpleNamespace(value=None), is_updating=False)
    guiutils.keep_selected_model(gui, ["Llama: tinyllama", "Llama: phi4 (installed)"])
    assert gui.ai_model_option.value == "Llama: phi4 (installed)"
    assert gui.is_updating is False  # set only while the value is being put back


def test_a_chosen_model_not_in_the_new_list_leaves_the_pulldown_alone() -> None:
    gui = fake_window(ai_model="phi4", ai_model_option=SimpleNamespace(value="before"), is_updating=False)
    guiutils.keep_selected_model(gui, ["Llama: tinyllama"])
    assert gui.ai_model_option.value == "before"


def test_the_flag_is_cleared_even_if_the_pulldown_refuses() -> None:
    class Refuses:
        @property
        def value(self) -> str:
            return ""

        @value.setter
        def value(self, _new: str) -> None:
            raise RuntimeError("the page went away")

    gui = fake_window(ai_model="phi4", ai_model_option=Refuses(), is_updating=False)
    with pytest.raises(RuntimeError):
        guiutils.keep_selected_model(gui, ["Llama: phi4"])
    assert gui.is_updating is False


# ##################################################################################
# Which key goes with which model
# ##################################################################################
def _gui(**overrides: Any) -> MyGui:
    ai = {
        "openai_models": ["gpt-5"],
        "anthropic_models": ["claude-opus"],
        "gemini_models": ["gemini-pro"],
        "llama_models": ["phi4 (installed)"],
        "openai_key": "sk-openai",
        "anthropic_key": "sk-claude",
        "gemini_key": "",
    }
    values = {
        "ai_model": "",
        "ai_apikey": "",
        "ai_model_extended_list": False,
        "state": SimpleNamespace(ai=ai),
    }
    return fake_window(**(values | overrides))


def test_a_model_with_no_name_is_not_a_configuration() -> None:
    assert guiutils.is_valid_ai_config(_gui(ai_model="")) is False


def test_a_cloud_model_with_its_key_is_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(guiutils, "get_api_key", lambda state: "unused")
    gui = _gui(ai_model="gpt-5", ai_apikey="sk-openai")
    assert guiutils.is_valid_ai_config(gui) is True
    assert gui.ai_apikey == "sk-openai"


def test_a_cloud_model_whose_provider_has_no_key_is_not(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(guiutils, "get_api_key", lambda state: "unused")
    assert guiutils.is_valid_ai_config(_gui(ai_model="gemini-pro", ai_apikey="x")) is False


def test_a_local_model_needs_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(guiutils, "get_api_key", lambda state: "unused")
    assert guiutils.is_valid_ai_config(_gui(ai_model="phi4", ai_apikey="x")) is True


def test_a_model_nobody_lists_is_not_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(guiutils, "get_api_key", lambda state: "unused")
    assert guiutils.is_valid_ai_config(_gui(ai_model="mystery", ai_apikey="x")) is False


def test_a_hidden_key_is_read_back_from_the_store(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[object] = []
    monkeypatch.setattr(guiutils, "get_api_key", lambda state: asked.append(state) or "sk-openai")
    gui = _gui(ai_model="gpt-5", ai_apikey="Hidden")
    assert guiutils.is_valid_ai_config(gui) is True
    assert asked == [gui.state]


def test_the_key_for_a_cloud_model_is_found_by_the_models_provider() -> None:
    gui = _gui()
    assert guiutils.set_ai_key(gui, "claude-opus") is True
    assert gui.ai_apikey == "sk-claude"


def test_a_local_or_unknown_model_has_no_key_to_set() -> None:
    gui = _gui()
    assert guiutils.set_ai_key(gui, "phi4") is False
    assert guiutils.set_ai_key(gui, "mystery") is False


def test_a_provider_with_no_saved_key_is_reported_as_having_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(guiutils, "get_api_key", lambda state: "")
    assert guiutils.set_ai_key(_gui(), "gemini-pro") is False


def test_the_extended_list_reads_the_keys_in_before_giving_up(monkeypatch: pytest.MonkeyPatch) -> None:
    gui = _gui(ai_model_extended_list=True)

    def load(state: SimpleNamespace) -> str:
        state.ai["gemini_key"] = "now-here"
        return "now-here"

    monkeypatch.setattr(guiutils, "get_api_key", load)
    assert guiutils.set_ai_key(gui, "gemini-pro") is True
    assert gui.ai_apikey == "now-here"


# ##################################################################################
# Is this a name in the backup?
# ##################################################################################
def _loaded() -> SimpleNamespace:
    return SimpleNamespace(
        android_file="",
        file="backup.xml",
        directory=False,
        list_unnamed_items=False,
        debug=False,
        appearance_mode="dark",
        state=SimpleNamespace(
            slash="/",
            error_msg="",
            error_code=0,
            program_arguments=SimpleNamespace(file=""),
            tasker_root_elements={
                "all_projects": {"1": {"name": "Home"}},
                "all_profiles": {"2": {"name": "Morning"}},
                "all_tasks": {"3": {"name": "Wake Up"}, "4": {"name": "Flash.4 (Unnamed)"}},
                "all_scenes": {"5": {"name": "Panel"}},
            },
        ),
    )


@pytest.mark.parametrize("none", ["None"])
def test_none_is_always_a_valid_choice(none: str) -> None:
    assert guiutils.valid_item(_loaded(), none, "Project", False, "dark") is True


@pytest.mark.parametrize(
    ("name", "kind", "valid"),
    [
        ("Home", "Project", True),
        ("Project: Home", "Project", True),  # the label the pulldown puts in front is ignored
        ("Nowhere", "Project", False),
        ("Morning", "Profile", True),
        ("Wake Up", "Task", True),
        ("Panel", "Scene", True),
        ("Home", "Scene", False),  # the right name in the wrong kind
        ("Flash.4 (Unnamed)", "Task", True),  # an unnamed Task is matched by its id
        ("Flash.9 (Unnamed)", "Task", False),
    ],
)
def test_a_name_is_valid_if_the_backup_has_one_of_that_kind(name: str, kind: str, valid: bool) -> None:
    assert guiutils.valid_item(_loaded(), name, kind, False, "dark") is valid


def test_the_local_file_is_used_when_the_backup_came_from_the_device() -> None:
    gui = _loaded()
    gui.android_file = "/Tasker/backup.xml"
    guiutils.valid_item(gui, "Home", "Project", False, "dark")
    assert gui.state.program_arguments.file == "backup.xml"


def test_the_file_the_user_picked_is_used_otherwise() -> None:
    gui = _loaded()
    gui.file = "picked.xml"
    guiutils.valid_item(gui, "Home", "Project", False, "dark")
    assert gui.state.program_arguments.file == "picked.xml"


def test_with_no_file_the_user_is_asked_for_one() -> None:
    gui = _loaded()
    gui.file = ""
    asked: list[tuple] = []
    gui.prompt_and_get_file = lambda *args: asked.append(args)
    guiutils.valid_item(gui, "Home", "Project", False, "dark")
    assert asked == [(False, "dark")]


def test_a_backup_not_yet_read_is_read_before_the_name_is_checked(monkeypatch: pytest.MonkeyPatch) -> None:
    gui = _loaded()
    loaded = gui.state.tasker_root_elements
    gui.state.tasker_root_elements = {"all_projects": {}, "all_profiles": {}, "all_tasks": {}, "all_scenes": {}}

    def read(debug: bool, mode: str, state: SimpleNamespace) -> int:
        state.tasker_root_elements = loaded
        return 0

    monkeypatch.setattr(guiutils, "get_xml", read)
    assert guiutils.valid_item(gui, "Home", "Project", False, "dark") is True


@pytest.mark.parametrize(("code", "message"), [(6, "Cancel button pressed."), (3, "")])
def test_a_backup_that_cannot_be_read_makes_every_name_invalid(
    monkeypatch: pytest.MonkeyPatch, code: int, message: str
) -> None:
    gui = _loaded()
    gui.state.tasker_root_elements = {"all_projects": {}, "all_profiles": {}, "all_tasks": {}, "all_scenes": {}}
    monkeypatch.setattr(guiutils, "get_xml", lambda debug, mode, state: code)

    assert guiutils.valid_item(gui, "Home", "Project", False, "dark") is False
    assert gui.state.error_msg == message
    assert gui.state.error_code == 0
