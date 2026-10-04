"""Tasks and Projects that need special handling: the 'nothing in this Project' lists and the
named Tasks no Profile calls.

Run on a RunState of their own with a stand-in for the output, and with the Task printer
(proclist.output_task_list) replaced: what it prints is proclist's to test, and what matters
here is which Tasks are handed to it and what is written around them.
"""

from __future__ import annotations

import pytest
from maptasker.src import taskuniq
from maptasker.src.primitem import RunState
from maptasker.src.runcfg import current_config
from maptasker.src.sysconst import NO_PROJECT


class _Output:
    def __init__(self) -> None:
        self.lines: list[tuple[int, str]] = []
        self.output_lines: list[str] = ["a twisty is closed by rewriting the last line"]

    def add_line_to_output(self, level: int, text: str, _how: object) -> None:
        self.lines.append((level, text))

    def text(self) -> str:
        return "\n".join(text for _level, text in self.lines)


def _state(tasks: dict | None = None) -> RunState:
    state = RunState()
    state.output_lines = _Output()
    state.tasker_root_elements = {"all_tasks": tasks or {}, "all_projects": {}}
    state.found_named_items["single_task_found"] = False
    return state


# ##################################################################################
# Projects with nothing in them
# ##################################################################################
def test_projects_without_tasks_or_profiles_are_each_listed() -> None:
    """Two lists, each with its heading and one line per Project."""
    state = _state()
    taskuniq.process_missing_tasks_and_profiles(["Empty One"], ["Bare One", "Bare Two"], state=state)
    text = state.output_lines.text()
    assert "Project Empty One has no <em>Named</em> Tasks" in text
    assert "- Project 'Bare One' has no Profiles" in text
    assert "- Project 'Bare Two' has no Profiles" in text


def test_nothing_missing_writes_nothing() -> None:
    """A tidy configuration gets no headings at all."""
    state = _state()
    taskuniq.process_missing_tasks_and_profiles([], [], state=state)
    assert state.output_lines.lines == []


def test_projects_without_tasks_stay_quiet_when_one_Task_was_asked_for() -> None:  # noqa: N802
    """'No Tasks' is meaningless when the run was about a single Task."""
    state = _state()
    state.found_named_items["single_task_found"] = True
    taskuniq.process_missing_tasks_and_profiles(["Empty One"], [], state=state)
    assert state.output_lines.lines == []


# ##################################################################################
# The heading
# ##################################################################################
def test_the_heading_marks_the_run_as_listing_unattached_tasks() -> None:
    """Later output reads this flag to know where it is."""
    state = _state()
    assert taskuniq.add_heading(save_twisty=False, state=state) is True
    assert state.displaying_named_tasks_not_in_profile is True
    assert "Named Tasks that are not called by any Profile" in state.output_lines.text()
    assert "<details>" not in state.output_lines.text()


def test_the_heading_goes_under_a_twisty_when_details_are_hidden() -> None:
    """The hidden form folds the whole list behind the heading."""
    state = _state()
    taskuniq.add_heading(save_twisty=True, state=state)
    assert "<details><summary>" in state.output_lines.text()


# ##################################################################################
# One unattached Task
# ##################################################################################
@pytest.fixture
def printed(monkeypatch: pytest.MonkeyPatch) -> list:
    """What the Task printer was asked to print, and what it says it printed."""
    calls: list = []

    def fake(
        tasks: list, project: str, profile: str, details: list, found: list, extra: bool, config: object, state: object
    ) -> bool:
        calls.append({"tasks": tasks, "project": project, "details": details})
        return False

    monkeypatch.setattr(taskuniq, "output_task_list", fake)
    return calls


def _solo(state: RunState, project: str, **config_changes: object) -> tuple:
    config = current_config(state).with_changes(**config_changes)
    return taskuniq.process_solo_task_with_no_profile("7", [], 0, False, [], False, config, state=state)


def test_an_unattached_task_is_counted_and_printed_under_its_project(
    monkeypatch: pytest.MonkeyPatch,
    printed: list,
) -> None:
    """The Project it lives in is named, and the heading goes out once, ahead of the first."""
    state = _state({"7": {"name": "Lonely", "xml": None}})
    monkeypatch.setattr(taskuniq, "get_project_for_solo_task", lambda *_args, **_kwargs: ("Home", None))

    have_heading, specific, count = _solo(state, "Home", display_detail_level=3)

    assert (have_heading, specific, count) == (True, False, 1)
    [call] = printed
    assert call["project"] == "Home"
    assert "in Project 'Home'" in call["details"][0]
    assert "Task ID" not in call["details"][0]


def test_debug_adds_the_task_id(monkeypatch: pytest.MonkeyPatch, printed: list) -> None:
    """The id is how a developer finds the Task in the XML."""
    state = _state({"7": {"name": "Lonely", "xml": None}})
    monkeypatch.setattr(taskuniq, "get_project_for_solo_task", lambda *_args, **_kwargs: ("Home", None))
    _solo(state, "Home", display_detail_level=3, debug=True)
    assert "with Task ID: 7" in printed[0]["details"][0]


def test_a_task_in_no_project_gets_no_project_phrase(monkeypatch: pytest.MonkeyPatch, printed: list) -> None:
    """There is nothing true to say about where it lives."""
    state = _state({"7": {"name": "Lonely", "xml": None}})
    monkeypatch.setattr(taskuniq, "get_project_for_solo_task", lambda *_args, **_kwargs: (NO_PROJECT, None))
    _solo(state, NO_PROJECT, display_detail_level=3)
    assert printed[0]["details"] == [""]


def test_a_low_detail_level_counts_the_task_without_printing_it(
    monkeypatch: pytest.MonkeyPatch,
    printed: list,
) -> None:
    """Detail 2 or less wants the count, not the list."""
    state = _state({"7": {"name": "Lonely", "xml": None}})
    monkeypatch.setattr(taskuniq, "get_project_for_solo_task", lambda *_args, **_kwargs: ("Home", None))
    have_heading, _specific, count = _solo(state, "Home", display_detail_level=2)
    assert (have_heading, count) == (False, 1)
    assert printed == []


# ##################################################################################
# Walking every Task
# ##################################################################################
def _walk(state: RunState, found: list, **settings: object) -> None:
    """Walk with these settings.  They go on the state: the walk takes its own from there."""
    for name, value in {"display_detail_level": 3, **settings}.items():
        setattr(state.program_arguments, name, value)
    taskuniq.process_tasks_not_called_by_profile([], found, current_config(state), state=state)


@pytest.fixture
def walked(monkeypatch: pytest.MonkeyPatch) -> list:
    """The ids of the Tasks the walk handed over; each one 'prints' and reports no match."""
    seen: list = []

    def fake(task_id: str, _found: list, count: int, have_heading: bool, *_args: object, **_kwargs: object) -> tuple:
        seen.append(task_id)
        return have_heading, False, count + 1

    monkeypatch.setattr(taskuniq, "process_solo_task_with_no_profile", fake)
    return seen


def test_only_tasks_no_profile_called_are_walked(walked: list) -> None:
    """The ones already shown under a Profile are skipped."""
    state = _state({"1": {"name": "A"}, "2": {"name": "B"}, "3": {"name": "C"}})
    _walk(state, found=["2"])
    assert walked == ["1", "3"]


def test_the_list_is_closed_after_the_tasks(walked: list) -> None:
    """A blank line, then the list is closed -- three times when anything was printed."""
    state = _state({"1": {"name": "A"}})
    _walk(state, found=[])
    assert [level for level, _text in state.output_lines.lines] == [0, 3, 3]


def test_nothing_to_print_still_closes_the_list(walked: list) -> None:
    """The enclosing list was opened by the caller, so it is closed here regardless."""
    state = _state({"1": {"name": "A"}})
    _walk(state, found=["1"])
    assert [level for level, _text in state.output_lines.lines] == [3]


def test_a_single_task_run_stops_the_walk_at_once(walked: list) -> None:
    """If the one Task asked for was already found, there is nothing left to look for."""
    state = _state({"1": {"name": "A"}, "2": {"name": "B"}})
    state.found_named_items["single_task_found"] = True
    _walk(state, found=[])
    assert walked == []


def test_finding_the_named_task_ends_the_walk_and_says_so(walked: list) -> None:
    """A run for one Task is done the moment it has it."""
    state = _state({"1": {"name": "A"}, "2": {"name": "B"}})
    _walk(state, found=[], single_task_name="A")
    assert walked == ["1"]
    assert state.found_named_items["single_task_found"] is True


def test_the_twisty_setting_is_off_during_the_walk_and_back_after(monkeypatch: pytest.MonkeyPatch) -> None:
    """The walk turns twisties off for the nested lists and must not leave them off."""
    state = _state({"1": {"name": "A"}})
    during = []

    def fake(
        _task_id: str,
        _found: list,
        count: int,
        have_heading: bool,
        _no_tasks: list,
        save_twisty: bool,
        config: object,
        state: RunState,
    ) -> tuple:
        during.append((config.twisty, save_twisty))
        return have_heading, False, count + 1

    monkeypatch.setattr(taskuniq, "process_solo_task_with_no_profile", fake)
    _walk(state, found=[], twisty=True)

    assert during == [(False, True)]
    assert state.program_arguments.twisty is True
    assert state.output_lines.output_lines[-1] == "</details></span><br>\n"
