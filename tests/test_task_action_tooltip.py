"""The 'Task:' tooltip in the Map lists the Task's actions, numbered and indented (proclist.get_task_action_lines)

Hovering over 'Task:' already showed the Profile and Project the Task belongs to.  Just below the Project it now lists
the Task's actions the way the Map does -- numbered from 01, in the Map's order, indented by If/Else/For nesting -- but
by title alone, and says how many more when there are too many to fit on a screen.  What is tested is the list, where it
falls in the tooltip, and what the tooltip looks like when the Task is not known.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET

import pytest
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.core.runcfg import RunConfig
from maptasker.src.mapgen import proclist

# Tasker's codes: the ones that open and close blocks, and some that do not.
IF, ELSE, END_IF, FOR, END_FOR = "37", "43", "38", "39", "40"
FLASH, VARIABLE_SET, PERFORM_TASK = "548", "547", "130"


def _task(*codes: str, numbers: list[int] | None = None) -> ET.Element:
    """A Task with one action per code, written the way Tasker writes them: act0, act1 ..."""
    marks = numbers or list(range(len(codes)))
    actions = "".join(
        f'<Action sr="act{number}" ve="7"><code>{code}</code></Action>'
        for number, code in zip(marks, codes, strict=True)
    )
    return ET.fromstring(f'<Task sr="task10"><id>10</id><nme>Morning</nme>{actions}</Task>')


def _tooltip_lines(output_line: str) -> list[str]:
    """The lines of the tooltip the 'Task:' label carries, as the browser would show them."""
    match = re.search(r'data-tooltip="([^"]*)"', output_line)
    assert match, output_line
    return html.unescape(match.group(1)).split("\n")


def _label(task: ET.Element | None, project: str = "Home", profile: str = "Dawn", indent: int = 4) -> list[str]:
    config = RunConfig(indent=indent)
    line, _color = proclist.format_task_or_scene(
        "Task:", "Morning&nbsp;", config, project, profile, task, state=PrimeItems
    )
    return _tooltip_lines(line)


# ==========================================
# The lines
# ==========================================
def test_each_action_is_listed_by_its_title_alone_and_numbered_from_01() -> None:
    task = _task(FLASH, VARIABLE_SET, PERFORM_TASK)

    assert proclist.get_task_action_lines(task, 4) == ["01: Flash", "02: Variable Set", "03: Perform Task"]


def test_the_numbers_are_two_digits_like_the_maps_and_grow_past_99() -> None:
    lines = proclist.get_task_action_lines(_task(*[FLASH] * 101), 4)

    assert lines[8] == "09: Flash"
    assert lines[9] == "10: Flash"
    assert lines[99] == "100: Flash"


def test_the_lines_are_in_the_order_the_map_numbers_the_actions() -> None:
    """Tasker writes act0, act1, act10, act2 as text: the Map's third action is not the third one in the file."""
    task = _task(FLASH, VARIABLE_SET, PERFORM_TASK, numbers=[0, 10, 2])

    assert proclist.get_task_action_lines(task, 4) == ["01: Flash", "02: Perform Task", "03: Variable Set"]


def test_a_plugin_action_is_named_by_its_own_entry_not_the_one_it_shares() -> None:
    assert proclist.get_task_action_lines(_task("107361459"), 4) == ["01: AutoInput Actions V2"]


def test_a_code_maptasker_does_not_know_is_still_a_line_of_the_list() -> None:
    assert proclist.get_task_action_lines(_task(FLASH, "99999999"), 4) == ["01: Flash", "02: code 99999999"]


def test_a_task_with_no_actions_has_no_lines() -> None:
    assert proclist.get_task_action_lines(_task(), 4) == []


# ==========================================
# The indentation
# ==========================================
def test_what_is_inside_an_if_is_indented_and_the_else_and_end_are_not() -> None:
    task = _task(IF, FLASH, ELSE, VARIABLE_SET, END_IF, PERFORM_TASK)

    assert proclist.get_task_action_lines(task, 4) == [
        "01: If",
        "02:     Flash",
        "03: Else",
        "04:     Variable Set",
        "05: End If",
        "06: Perform Task",
    ]


def test_a_for_loop_is_indented_the_same_way() -> None:
    assert proclist.get_task_action_lines(_task(FOR, FLASH, END_FOR), 4) == ["01: For", "02:     Flash", "03: End For"]


def test_nested_blocks_go_one_level_further_in_each() -> None:
    task = _task(FOR, IF, FLASH, END_IF, END_FOR)

    assert proclist.get_task_action_lines(task, 4) == [
        "01: For",
        "02:     If",
        "03:         Flash",
        "04:     End If",
        "05: End For",
    ]


def test_the_indent_is_the_maps_own_setting() -> None:
    task = _task(IF, FLASH, END_IF)

    assert proclist.get_task_action_lines(task, 2)[1] == "02:   Flash"
    assert proclist.get_task_action_lines(task, 0)[1] == "02: Flash"


def test_an_end_with_nothing_open_does_not_push_the_rest_out_past_the_edge() -> None:
    """A Task cut off mid-block, or edited by hand: the Map stops at zero, and so does this."""
    assert proclist.get_task_action_lines(_task(END_IF, FLASH), 4) == ["01: End If", "02: Flash"]


def test_the_codes_that_indent_are_the_ones_the_map_indents_by() -> None:
    """The same constants as tasks.get_actions, so the two cannot disagree about what a block is."""
    from maptasker.src.mapgen import tasks

    assert proclist.INDENT_IN_CODES is tasks.INDENT_IN_CODES
    assert proclist.INDENT_OUT_CODES is tasks.INDENT_OUT_CODES


# ==========================================
# The tooltip lines
# ==========================================
def test_the_actions_come_under_a_heading() -> None:
    assert proclist.task_action_tooltip_lines(_task(FLASH, VARIABLE_SET), 4) == [
        "Actions:",
        "01: Flash",
        "02: Variable Set",
    ]


def test_a_task_that_is_not_known_or_has_no_actions_adds_nothing() -> None:
    assert proclist.task_action_tooltip_lines(None, 4) == []
    assert proclist.task_action_tooltip_lines(_task(), 4) == []


def test_a_long_list_is_cut_and_says_how_many_more() -> None:
    total = proclist.MAX_TOOLTIP_ACTIONS + 7

    lines = proclist.task_action_tooltip_lines(_task(*[FLASH] * total), 4)

    assert lines[0] == "Actions:"
    assert len(lines[1:-1]) == proclist.MAX_TOOLTIP_ACTIONS
    assert lines[-2] == f"{proclist.MAX_TOOLTIP_ACTIONS}: Flash"
    assert lines[-1] == "... and 7 more"


def test_a_list_that_just_fits_is_not_cut() -> None:
    lines = proclist.task_action_tooltip_lines(_task(*[FLASH] * proclist.MAX_TOOLTIP_ACTIONS), 4)

    assert len(lines) == proclist.MAX_TOOLTIP_ACTIONS + 1
    assert not lines[-1].startswith("...")


# ==========================================
# In the Map
# ==========================================
def test_the_actions_are_just_below_the_project_in_the_tasks_tooltip() -> None:
    assert _label(_task(IF, FLASH, END_IF)) == [
        "Profile: Dawn",
        "Project: Home",
        "Actions:",
        "01: If",
        "02:     Flash",
        "03: End If",
    ]


def test_the_indent_in_the_tooltip_follows_the_runs_setting() -> None:
    assert _label(_task(IF, FLASH, END_IF), indent=2)[4] == "02:   Flash"


def test_a_task_that_belongs_to_no_profile_lists_its_actions_under_its_project() -> None:
    assert _label(_task(FLASH), profile="") == ["Project: Home", "Actions:", "01: Flash"]


def test_a_task_that_is_not_known_has_the_tooltip_it_always_had() -> None:
    assert _label(None) == ["Profile: Dawn", "Project: Home"]


def test_a_task_with_no_actions_has_the_tooltip_it_always_had() -> None:
    assert _label(_task()) == ["Profile: Dawn", "Project: Home"]


def test_a_title_with_markup_in_it_cannot_break_out_of_the_tooltip(monkeypatch: pytest.MonkeyPatch) -> None:
    """The lines go into an attribute: a quote or a tag in one must be escaped, as the Profile and Project already are."""
    monkeypatch.setattr(proclist, "get_task_action_lines", lambda _task, _indent: ['01: Say "hi" <b>& more'])
    config = RunConfig()
    line, _color = proclist.format_task_or_scene(
        "Task:", "Morning&nbsp;", config, "Home", "Dawn", _task(FLASH), state=PrimeItems
    )

    assert 'Say "hi"' not in line
    assert "&lt;b&gt;" in line
    assert _tooltip_lines(line)[-1] == '01: Say "hi" <b>& more'


def test_the_label_is_still_one_line_of_output() -> None:
    """The lines are joined with an entity, not a newline, so the Map's parser still reads one line."""
    config = RunConfig()
    line, _color = proclist.format_task_or_scene(
        "Task:", "Morning&nbsp;", config, "Home", "Dawn", _task(IF, FLASH, END_IF), state=PrimeItems
    )

    assert "\n" not in line
    assert "&#10;" in line


def test_a_task_a_scene_fires_gets_no_actions_in_its_tooltip() -> None:
    """'--Task:' is a handler on a Scene element and keeps the tooltip it had."""
    line, _color = proclist.format_task_or_scene(
        "&#45;&#45;Task:&nbsp;&nbsp;", "10", RunConfig(), "Home", "", _task(FLASH), state=PrimeItems
    )

    assert "Actions:" not in line
