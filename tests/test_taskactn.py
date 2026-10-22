"""Writing a Task's Actions into the Map: their alignment, their numbering and finding the Task they belong to."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from types import SimpleNamespace

import pytest
from maptasker.src.mapgen import taskactn

B = "&nbsp;"


class _Output:
    """The Map's output, as a list of what was added to it."""

    def __init__(self) -> None:
        self.lines: list[tuple[int, str, list]] = []

    def add_line_to_output(self, level: int, text: str, format_spec: object) -> None:
        self.lines.append((level, text, format_spec))


def _state(tasks: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        output_lines=_Output(),
        tasker_root_elements={"all_tasks": tasks or {}},
        task_count_unnamed=0,
        task_action_warnings={},
        emitted_anchors=set(),
        program_arguments=SimpleNamespace(),
    )


def _config(**overrides: object) -> SimpleNamespace:
    values = {
        "pretty": False,
        "twisty": False,
        "display_detail_level": 3,
        "taskernet": False,
        "task_action_warning_limit": 100,
    }
    return SimpleNamespace(**(values | overrides))


# ##################################################################################
# Alignment
# ##################################################################################
def test_a_single_line_action_is_left_alone() -> None:
    assert taskactn.ensure_argument_alignment("Flash") == "Flash"


def test_every_argument_is_lined_up_under_the_first() -> None:
    """The first argument sets the indent and the rest are moved to it, whatever they carried."""
    ragged = f"Flash<br>{B * 4}Text=a<br>{B * 9}Long=1<br>{B * 2}Other=2"
    assert taskactn.ensure_argument_alignment(ragged) == f"Flash<br>{B * 4}Text=a<br>{B * 4}Long=1<br>{B * 4}Other=2"


def test_newlines_are_treated_as_line_breaks() -> None:
    assert taskactn.ensure_argument_alignment(f"Flash\n{B * 2}Text=a\n{B * 5}Long=1") == (
        f"Flash<br>{B * 2}Text=a<br>{B * 2}Long=1"
    )


def test_alignment_stops_at_an_html_label() -> None:
    """A label or TaskerNet description can carry markup of its own; indenting it would break it."""
    line = f"Flash<br>{B * 4}Text=a<br>{B * 9}Long=1<br>text-decoration x<br>after"
    assert taskactn.ensure_argument_alignment(line).endswith("<br>text-decoration x<br>after")


def test_the_disabled_marker_hangs_further_out() -> None:
    line = f"Flash<br>{B * 22}Text=a<br>[&#9940;DISABLED]</span>"
    assert taskactn.ensure_argument_alignment(line).endswith(f"<br>{B * 4}[&#9940;DISABLED]</span>")


# ##################################################################################
# Numbering and writing the Actions
# ##################################################################################
def _written(state: SimpleNamespace) -> list[str]:
    return [text for _level, text, _spec in state.output_lines.lines]


def test_actions_are_numbered_from_where_the_count_starts() -> None:
    state = _state()
    taskactn.output_list_of_actions(1, ["Flash", "Wait"], "Task", _config(), state=state)
    assert _written(state)[:2] == ["Action: 01</span> Flash", "Action: 02</span> Wait"]


def test_a_none_in_the_list_is_skipped() -> None:
    state = _state()
    taskactn.output_list_of_actions(1, [None, "Wait"], "Task", _config(), state=state)
    assert _written(state)[0] == "Action: 01</span> Wait"


def test_a_continued_line_is_written_without_a_number() -> None:
    state = _state()
    taskactn.output_list_of_actions(1, ["Flash", "...more of it"], "Task", _config(), state=state)
    assert _written(state)[:2] == ["Action: 01</span> Flash", "Action: ...more of it"]


def test_a_three_digit_action_gives_up_a_blank_to_stay_in_line() -> None:
    state = _state()
    taskactn.output_list_of_actions(100, [f"{B}Flash"], "Task", _config(), state=state)
    assert _written(state)[0] == "Action: 100</span> Flash"


def test_each_action_carries_an_anchor_when_the_task_is_known() -> None:
    state = _state()
    taskactn.output_list_of_actions(1, ["Flash"], "Task", _config(), task_id="12", state=state)
    anchor = state.output_lines.lines[0][2][0]
    assert anchor
    assert "12" in anchor


def test_pretty_mode_aligns_the_arguments() -> None:
    state = _state()
    line = f"Flash<br>{B * 4}Text=a<br>{B * 9}Long=1"
    taskactn.output_list_of_actions(1, [line], "Task", _config(pretty=True), state=state)
    assert f"<br>{B * 4}Long=1" in _written(state)[0]


def test_the_list_is_closed_unless_twisties_do_it() -> None:
    plain, twisty = _state(), _state()
    taskactn.output_list_of_actions(1, ["Flash"], "Task", _config(), state=plain)
    taskactn.output_list_of_actions(1, ["Flash"], "Task", _config(twisty=True), state=twisty)
    assert len(plain.output_lines.lines) == len(twisty.output_lines.lines) + 1


def test_a_known_task_at_the_lowest_detail_shows_only_its_first_action() -> None:
    state = _state()
    taskactn.output_list_of_actions(1, ["One", "Two", "Three"], "Wake Up", _config(display_detail_level=1), state=state)
    assert [text for text in _written(state) if text.startswith("Action:")] == ["Action: 01</span> One"]


def test_an_unnamed_task_at_detail_zero_shows_only_its_first_action() -> None:
    state = _state()
    unnamed = "Flash.12 (Unnamed)"
    taskactn.output_list_of_actions(1, ["One", "Two"], unnamed, _config(display_detail_level=0), state=state)
    assert [text for text in _written(state) if text.startswith("Action:")] == ["Action: 01</span> One"]


# ##################################################################################
# Finding the Task an output line is about
# ##################################################################################
def _tasks() -> dict:
    return {
        "11": {"name": "Wake Up", "xml": ET.Element("Task", id="11")},
        "12": {"name": "Flash.12 (Unnamed)", "xml": ET.Element("Task", id="12")},
    }


def test_a_task_is_found_by_its_name() -> None:
    state = _state(_tasks())
    element, name, task_id = taskactn._find_task(f"Wake Up{B * 3}Task ID: 11", "Task:", state)
    assert (name, task_id) == ("Wake Up", "11")
    assert element is state.tasker_root_elements["all_tasks"]["11"]["xml"]


def test_arrows_added_for_calls_are_stripped_from_the_name() -> None:
    state = _state(_tasks())
    _, name, _ = taskactn._find_task("Wake Up &#11013;", "Task:", state)
    assert name == "Wake Up"
    _, name, _ = taskactn._find_task("Wake Up &#11157;", "Task:", state)
    assert name == "Wake Up"


def test_a_task_inside_a_scene_is_looked_up_by_its_id() -> None:
    state = _state(_tasks())
    element, name, task_id = taskactn._find_task("11", "&#45;&#45;Task:", state)
    assert (name, task_id) == ("Wake Up", "11")
    assert element is state.tasker_root_elements["all_tasks"]["11"]["xml"]


def test_an_unnamed_task_entry_or_exit_is_counted() -> None:
    state = _state(_tasks())
    taskactn._find_task("Flash.12 (Unnamed) Entry Task", "Task:", state)
    assert state.task_count_unnamed == 1


def test_an_unnamed_task_is_found_through_its_id_when_markup_hides_its_name() -> None:
    """'Pretty' mode puts a line break inside a long unnamed Task's name, so the name no longer matches."""
    state = _state(_tasks())
    element, name, task_id = taskactn._find_task("Flash<br>.12 (Unnamed)", "Task:", state)
    assert task_id == "12"
    assert name == "Flash.12 (Unnamed)"
    assert element is state.tasker_root_elements["all_tasks"]["12"]["xml"]


# ##################################################################################
# Writing a whole Task
# ##################################################################################
def test_a_task_not_found_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    reported: list[tuple] = []
    monkeypatch.setattr(taskactn, "error_handler", lambda *args, **kwargs: reported.append(args))
    state = _state(_tasks())

    taskactn.get_task_actions_and_output(None, "Task:", "Nobody", [], _config(), state)

    assert reported == [("No Task found!!!", 0)]


def test_a_found_task_is_remembered_and_its_actions_written(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(taskactn.tasks, "get_actions", lambda task, config, state: ["Flash", "Wait"])
    state = _state(_tasks())
    found: list[str] = []

    taskactn.get_task_actions_and_output(None, "Task:", f"Wake Up{B}Task ID: 11", found, _config(), state)

    assert found == ["11"]
    assert any(text.startswith("Action: 01") for text in _written(state))


def test_a_task_with_too_many_actions_is_flagged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(taskactn.tasks, "get_actions", lambda task, config, state: ["a", "b", "c", "d"])
    state = _state(_tasks())

    taskactn.get_task_actions_and_output(
        None, "Task:", f"Wake Up{B}Task ID: 11", [], _config(task_action_warning_limit=3), state
    )

    assert state.task_action_warnings == {"Wake Up": {"count": 4, "id": "11"}}


def test_a_scene_task_closes_the_list_it_was_nested_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Task shown inside a Scene sits in a list of its own, which needs closing as well as the
    Action list -- twice under twisties, which also have their own wrapper."""
    monkeypatch.setattr(taskactn.tasks, "get_actions", lambda task, config, state: ["Flash"])

    def closers(list_type: str, item: str, *, twisty: bool) -> int:
        state = _state(_tasks())
        taskactn.get_task_actions_and_output(None, list_type, item, [], _config(twisty=twisty), state)
        return sum(1 for level, _text, _spec in state.output_lines.lines if level == 3)

    by_name = f"Wake Up{B}Task ID: 11"
    assert closers("&#45;&#45;Task:", "11", twisty=False) == closers("Task:", by_name, twisty=False) + 1
    assert closers("&#45;&#45;Task:", "11", twisty=True) == closers("Task:", by_name, twisty=True) + 2


def test_the_taskernet_description_is_written_when_asked_for(monkeypatch: pytest.MonkeyPatch) -> None:
    shared: list[tuple] = []
    monkeypatch.setattr(taskactn.tasks, "get_actions", lambda task, config, state: ["Flash"])
    monkeypatch.setattr(taskactn, "share", lambda *args, **kwargs: shared.append(args))
    state = _state(_tasks())

    taskactn.get_task_actions_and_output(None, "Task:", f"Wake Up{B}Task ID: 11", [], _config(taskernet=True), state)

    assert len(shared) == 1
