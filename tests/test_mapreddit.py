"""mapreddit: what the Map shows, written as Tasker's own text and indented as a Reddit code block.

The fixture is the post that asked for the feature, rebuilt as a backup: a Profile on a Logcat Entry Event whose Entry Task
searches a variable, branches on the result and performs another Task from each side.  What is checked is the layout
(the words, the nesting, the brackets), what is left out (an argument the file does not hold, a text argument that is
empty), and that the scope is the Map's: one Task, one Profile, one Project, or everything.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.core.sysconst import REDDIT_EXPORT_FILE
from maptasker.src.mapops import mapreddit

from tests.test_maprefac import _load

if TYPE_CHECKING:
    from pathlib import Path

SEARCH = "598"
PERFORM_TASK = "130"
IF = "37"
ELSE = "43"
END_IF = "38"
FLASH = "548"


def _string(number: int, text: str) -> str:
    return f'<Str sr="arg{number}" ve="3">{text}</Str>'


def _number(number: int, value: int) -> str:
    return f'<Int sr="arg{number}" val="{value}"/>'


def _action(code: str, *arguments: str, extra: str = "") -> str:
    return f'<Action sr="act0" ve="7"><code>{code}</code>{extra}{"".join(arguments)}</Action>'


def _if(left: str, operator: str, right: str) -> str:
    condition = f'<ConditionList sr="if"><Condition sr="c0" ve="3"><lhs>{left}</lhs><op>{operator}</op><rhs>{right}</rhs></Condition></ConditionList>'
    return _action(IF, extra=condition)


def _perform(name: str, spoken: str) -> str:
    return _action(
        PERFORM_TASK,
        _string(0, name),
        '<Int sr="arg1" val="0"><var>%priority</var></Int>',
        _string(2, spoken),
        _string(3, "media"),
        _number(10, 1),
    )


def _task(task_id: str, name: str, *actions: str) -> str:
    numbered = "".join(action.replace("act0", f"act{number}") for number, action in enumerate(actions))
    return f'<Task sr="task{task_id}" ve="2"><id>{task_id}</id><nme>{name}</nme>{numbered}</Task>'


_XML = (
    '<TaskerData sr="" dvi="1" tv="6.6.3">'
    '<Project sr="projNet" ve="2"><name>Net</name><pids>5</pids><tids>1,2,3</tids><scenes>Panel</scenes></Project>'
    '<Project sr="projOther" ve="2"><name>Other</name><pids></pids><tids>4</tids></Project>'
    '<Profile sr="prof5" ve="2"><id>5</id><nme>TetheredDevices</nme><mid0>1</mid0>'
    '<Event sr="con0" ve="2"><code>2085</code><pri>0</pri>'
    + _string(1, "SoftApManager")
    + _string(2, "The connected wifi stations have changed")
    + _number(3, 0)
    + "</Event></Profile>"
    + _task(
        "1",
        "Tethered Devices",
        _action(
            SEARCH,
            _string(0, "%lc_text"),
            _string(1, "([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})"),
            _string(5, "%mac"),
        ),
        _if("%lc_text", "4", "DisconnectReason"),
        _perform("Azure Talker", "A device has disconnected from your hotspot"),
        _action(ELSE),
        _perform("Azure Talker", "A new device has connected to your hotspot"),
        _action(END_IF),
    )
    + _task("2", "Azure Talker", _action(FLASH, _string(0, "%par1"), _number(1, 0)))
    + _task("3", "Loose", _action(FLASH, _string(0, "hi")))
    + _task("4", "Elsewhere", _action(FLASH, _string(0, "there")))
    + '<Scene sr="scenePanel"><nme>Panel</nme></Scene>'
    + "</TaskerData>"
)


@pytest.fixture(autouse=True)
def _configuration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The fixture loaded, no single object chosen, and an output folder of its own."""
    monkeypatch.chdir(tmp_path)
    _load(_XML)
    PrimeItems.program_arguments.output_directory = str(tmp_path)
    for name in ("single_project_name", "single_profile_name", "single_task_name", "single_scene_name"):
        setattr(PrimeItems.program_arguments, name, "")


def _text() -> list[str]:
    return mapreddit.build(PrimeItems).splitlines()


def test_a_profile_is_written_the_way_tasker_posts_it() -> None:
    lines = _text()
    start = lines.index("Profile: TetheredDevices")

    assert lines[start + 1].startswith("\tEvent: Logcat Entry")
    assert lines[start + 2] == ""
    assert lines[start + 3] == "Enter Task: Tethered Devices"


def test_an_actions_arguments_hang_under_it_in_brackets_with_taskers_own_labels() -> None:
    lines = _text()
    start = lines.index("A1: Variable Search Replace [")

    assert lines[start : start + 4] == [
        "A1: Variable Search Replace [",
        "     Variable: %lc_text",
        "     Search: ([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})",
        "     Store Matches In Array: %mac ]",
    ]


def test_an_if_is_one_line_and_what_is_inside_it_is_nested_to_the_end_if() -> None:
    lines = _text()

    assert "A2: If [ %lc_text ~R DisconnectReason ]" in lines
    assert "    A3: Perform Task [" in lines
    assert "A4: Else" in lines
    assert "    A5: Perform Task [" in lines
    assert "A6: End If" in lines


def test_a_perform_task_writes_what_the_file_holds_and_leaves_the_rest_out() -> None:
    lines = _text()
    start = lines.index("    A3: Perform Task [")

    assert lines[start : start + 6] == [
        "    A3: Perform Task [",
        "         Name: Azure Talker",
        "         Priority: %priority",
        "         Parameter 1 (%par1): A device has disconnected from your hotspot",
        "         Parameter 2 (%par2): media",
        "         Structure Output (JSON, etc): On ]",
    ]


def test_an_off_switch_the_file_holds_is_written_and_an_empty_text_is_not() -> None:
    lines = _text()
    start = lines.index("A1: Flash [", lines.index("Task: Azure Talker"))

    assert lines[start : start + 3] == ["A1: Flash [", "     Text: %par1", "     Long: Off ]"]


def test_a_task_no_profile_runs_is_a_task_and_a_scene_is_a_scene() -> None:
    lines = _text()

    assert "Task: Loose" in lines
    assert "Scene: Panel" in lines
    assert "Project: Net" in lines
    assert lines.index("Project: Net") < lines.index("Profile: TetheredDevices") < lines.index("Project: Other")


def test_a_task_that_two_profiles_run_is_written_once() -> None:
    second = '<Profile sr="prof6" ve="2"><id>6</id><nme>Second</nme><mid0>1</mid0></Profile>'
    _load(
        _XML.replace("<pids>5</pids>", "<pids>5,6</pids>").replace("</Event></Profile>", "</Event></Profile>" + second)
    )
    text = "\n".join(_text())

    assert text.count("A1: Variable Search Replace") == 1
    assert "Enter Task: Tethered Devices\n\n    (written above)" in text


def test_the_scope_is_the_one_object_the_map_is_showing() -> None:
    PrimeItems.program_arguments.single_task_name = "Loose"
    assert _text() == ["Task: Loose", "", "A1: Flash [ Text: hi ]"]
    assert "Project: Net" not in _text()
    assert "Profile: TetheredDevices" not in _text()

    PrimeItems.program_arguments.single_task_name = ""
    PrimeItems.program_arguments.single_profile_name = "TetheredDevices"
    lines = _text()
    assert lines[0] == "Profile: TetheredDevices"
    assert "Task: Loose" not in lines

    PrimeItems.program_arguments.single_profile_name = ""
    PrimeItems.program_arguments.single_project_name = "Other"
    assert "Task: Elsewhere" in _text()
    assert "Profile: TetheredDevices" not in _text()


def test_nothing_in_the_map_is_said_rather_than_an_empty_post() -> None:
    PrimeItems.program_arguments.single_task_name = "No Such Task"

    with pytest.raises(mapreddit.RedditError):
        mapreddit.build(PrimeItems)


def test_the_code_block_indents_every_line_four_spaces_blank_ones_too() -> None:
    block = mapreddit.as_code_block("Profile: A\n\nEnter Task: B\n")

    assert block == "    Profile: A\n    \n    Enter Task: B\n"


def test_export_saves_the_code_block_and_answers_what_to_paste(tmp_path: Path) -> None:
    path, post = mapreddit.export(PrimeItems)

    assert path == str(tmp_path / REDDIT_EXPORT_FILE)
    assert (tmp_path / REDDIT_EXPORT_FILE).read_text(encoding="utf-8") == post
    assert all(line.startswith("    ") for line in post.splitlines())
