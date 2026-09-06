"""MapTasker Task parsing (tasks) Unit Tests

tasks.py turns a <Task> element into the lines the map shows for it: the action list with
its nesting, the Entry/Exit role a Profile gave it, the icon and flags beside its name,
and -- for a Task that belongs to no Profile -- the Project it has to be listed under.

The action indentation is the part worth guarding hardest.  Tasker stores a Task's
control flow as a flat list of actions, and the If/End If nesting a reader depends on
exists ONLY as the indentation this module computes while walking that list.  Nothing
downstream re-derives it and nothing validates it, so an off-by-one in the indent
bookkeeping does not fail: it redraws the Task's logic as a different Task's logic.

Two tests here are marked xfail.  Both are pre-existing defects found while writing this
file, not new breakage, and both are described at the test.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from maptasker.src import taskerd, tasks
from maptasker.src.colrmode import set_color_mode
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.lineout import LineOut
from maptasker.src.primitem import PrimeItems, initial_found_named_items
from maptasker.src.proginit import load_arg_specs

_IF = '<Action sr="act{n}"><code>37</code><ConditionList sr="if"><Condition sr="c0"><lhs>%a</lhs><op>0</op><rhs>1</rhs></Condition></ConditionList></Action>'
_ELSE = '<Action sr="act{n}"><code>43</code></Action>'
_END_IF = '<Action sr="act{n}"><code>38</code></Action>'
_FOR = '<Action sr="act{n}"><code>39</code><Str sr="arg0">%item</Str><Str sr="arg1">%list</Str></Action>'
_END_FOR = '<Action sr="act{n}"><code>40</code></Action>'
_FLASH = '<Action sr="act{n}"><code>548</code><Str sr="arg0">hi</Str></Action>'

_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0"><name>Home</name><tids>10,11</tids></Project>
  <Project sr="proj1"><name>Away</name><tids>12</tids></Project>
  <Project sr="proj2"><name>Empty</name></Project>
  <Task sr="task10"><id>10</id><nme>Alpha</nme></Task>
  <Task sr="task11"><id>11</id><nme>Beta</nme></Task>
  <Task sr="task12"><id>12</id><nme>Gamma</nme></Task>
  <Task sr="task13"><id>13</id></Task>
</TaskerData>"""

ENTRY_ARROW = "&#11013;"
EXIT_ARROW = "&#11157;"
INDENT = "&nbsp;" * 4  # one nesting level at the default indent of 4


@pytest.fixture(autouse=True)
def _loaded() -> None:
    """A loaded configuration, plus the argument-type tables an action is mapped through."""
    load_arg_specs()

    PrimeItems.program_arguments = initialize_runtime_arguments()
    PrimeItems.colors_to_use = set_color_mode("dark")
    PrimeItems.output_lines = LineOut()
    PrimeItems.found_named_items = initial_found_named_items()
    PrimeItems.task_count_unnamed = 0
    PrimeItems.xml_root = ET.fromstring(_XML)  # noqa: S314  (fixture text, defined in this file)
    taskerd.build_tasker_tables()


def _task_of(*actions: str) -> ET.Element:
    """One <Task> whose actions are numbered in order, so map order is document order."""
    numbered = "".join(action.format(n=index) for index, action in enumerate(actions))
    return ET.fromstring(  # noqa: S314  (fixture text, built in this file)
        f'<Task sr="task99"><id>99</id><nme>Fixture</nme>{numbered}</Task>',
    )


def _indent_of(line: str) -> int:
    """How many nesting levels a rendered action line is drawn at."""
    inner = line.split(">", 1)[1] if ">" in line else line
    depth = 0
    while inner.startswith(INDENT):
        inner = inner[len(INDENT) :]
        depth += 1
    return depth


# ##################################################################################
# get_actions -- the action list, and the nesting that only exists here
# ##################################################################################
def test_actions_come_back_in_order() -> None:
    """One line per action, in the order they run."""
    lines = tasks.get_actions(_task_of(_FLASH, _FLASH, _FLASH))
    assert len(lines) == 3


def test_a_task_with_no_actions_produces_no_lines() -> None:
    """An empty Task is legal -- Tasker writes one for a Task the user created and never
    filled in -- and must not be an error or a blank line.
    """
    assert tasks.get_actions(ET.fromstring('<Task sr="task99"><id>99</id></Task>')) == []  # noqa: S314


def test_actions_inside_an_if_are_indented_under_it() -> None:
    """The If and its End If sit at the outer level and what they guard sits one level in.
    This indentation IS the Task's structure as the reader sees it -- see the module note.
    """
    lines = tasks.get_actions(_task_of(_FLASH, _IF, _FLASH, _END_IF, _FLASH))
    assert [_indent_of(line) for line in lines] == [0, 0, 1, 0, 0]


def test_nesting_goes_deeper_and_comes_back_out() -> None:
    """Two levels in and two levels back out.  A de-indent that trims the wrong amount
    leaves everything after the inner block permanently shifted.
    """
    lines = tasks.get_actions(_task_of(_IF, _FOR, _FLASH, _END_FOR, _FLASH, _END_IF, _FLASH))
    assert [_indent_of(line) for line in lines] == [0, 1, 2, 1, 1, 0, 0]


def test_else_sits_at_the_level_of_its_if() -> None:
    """Else both closes and opens a block: it is drawn level with its If, and what
    follows it is indented again.
    """
    lines = tasks.get_actions(_task_of(_IF, _FLASH, _ELSE, _FLASH, _END_IF))
    assert [_indent_of(line) for line in lines] == [0, 1, 0, 1, 0]


def test_a_stray_end_if_cannot_indent_backwards() -> None:
    """A Task can be saved with unbalanced blocks, and an End If with no If would take
    the indent below zero.  Negative indentation is not a thing: the rest of the Task
    would be drawn wrongly, or the slicing that trims it would eat real text.
    """
    lines = tasks.get_actions(_task_of(_END_IF, _FLASH, _END_IF, _FLASH))
    assert [_indent_of(line) for line in lines] == [0, 0, 0, 0]


def test_actions_are_sorted_by_their_number_not_document_order() -> None:
    """Tasker does not promise to store actions in order -- sr="actN" is the order they
    run in.  Rendering them in file order shows the Task doing things in the wrong order.
    """
    task = ET.fromstring(  # noqa: S314  (fixture text, built in this file)
        '<Task sr="task99"><id>99</id>'
        '<Action sr="act1"><code>548</code><Str sr="arg0">second</Str></Action>'
        '<Action sr="act0"><code>548</code><Str sr="arg0">first</Str></Action>'
        "</Task>",
    )
    lines = tasks.get_actions(task)
    assert "first" in lines[0]
    assert "second" in lines[1]


# ##################################################################################
# Entry / Exit, and the names given to Tasks that have none
# ##################################################################################
def test_entry_and_exit_tasks_get_opposite_arrows() -> None:
    """The arrow is the only thing on the line that says whether the Task runs when the
    Profile's condition becomes true or when it stops being true.
    """
    output: list[str] = []
    tasks.get_task_name("10", [], output, "Entry")
    tasks.get_task_name("11", [], output, "Exit")
    assert ENTRY_ARROW in output[0]
    assert EXIT_ARROW in output[1]


def test_an_unknown_task_id_is_not_an_error() -> None:
    """A Profile can reference a Task that is not in the backup.  Returning empty lets
    the caller carry on and list the rest of the Profile, rather than stopping the run.
    """
    assert tasks.get_task_name("99999", [], [], "Entry") == (None, "")


def test_a_task_seen_twice_is_only_listed_once() -> None:
    """A Task run by two Profiles is one Task in the totals.  The found list is what
    distinguishes the second sighting from a second Task.
    """
    found: list[str] = []
    tasks.get_task_name("13", found, [], "Entry")
    tasks.get_task_name("13", found, [], "Entry")
    assert found == ["13"]


def test_only_the_first_sighting_of_an_unnamed_task_is_counted() -> None:
    """The unnamed-Task total counts Tasks, not appearances.  entry_or_exit_task is
    called with the name empty here because that is the only way into this branch --
    by the time a Task reaches it through get_task_name, taskerd has already given
    every Task a derived name.
    """
    tasks.entry_or_exit_task([], "", "Entry", "", False, "13")
    assert PrimeItems.task_count_unnamed == 1

    tasks.entry_or_exit_task([], "", "Entry", "", True, "13")  # a duplicate sighting
    assert PrimeItems.task_count_unnamed == 1


def test_an_unnamed_task_is_named_and_the_name_is_kept() -> None:
    """The invented name is written back into the lookup table, not just onto the line:
    everything that looks the Task up afterwards -- the directory, a jump, the totals --
    has to find the same name the user is looking at.
    """
    output: list[str] = []
    _, name = tasks.entry_or_exit_task(output, "", "Entry", "", False, "13")
    assert name == "Unnamed13"
    assert PrimeItems.tasker_root_elements["all_tasks"]["13"]["name"] == "Unnamed13"


def test_debug_mode_puts_the_task_id_on_the_line() -> None:
    """The id is what a Profile references and what the tables are keyed on, and it is
    otherwise nowhere in the output.
    """
    PrimeItems.program_arguments["debug"] = True
    output: list[str] = []
    tasks.get_task_name("10", [], output, "Entry")
    assert "Task ID: 10" in output[0]


# ##################################################################################
# Which Project a Profile-less Task belongs to
# ##################################################################################
def test_a_solo_task_is_traced_to_its_project() -> None:
    """A Task in no Profile is still in a Project, via that Project's <tids>.  It is
    listed under that Project, so this lookup decides where it appears.
    """
    assert tasks.get_project_for_solo_task("11", [])[0] == "Home"
    assert tasks.get_project_for_solo_task("12", [])[0] == "Away"


def test_projects_without_tasks_are_collected_on_the_way_past() -> None:
    """The caller reports Projects that contain nothing, and this walk is where they are
    noticed -- it is already visiting every Project.
    """
    # Task 13 is in no Project's <tids>, so the walk visits every Project rather than
    # returning at the first match -- which is what it takes to reach the empty one.
    empty: list[str] = []
    tasks.get_project_for_solo_task("13", empty)
    assert "Empty" in empty


@pytest.mark.xfail(
    reason="Pre-existing defect: the search falls out of its loop returning the LAST Project "
    "it looked at rather than the NO_PROJECT default, so a Task belonging to no Project is "
    "attributed to whichever Project happens to be last in the table.",
    strict=False,
)
def test_a_task_in_no_project_is_not_attributed_to_one() -> None:
    """Task 13 is in no Project's <tids>.  Naming a Project for it puts the Task under a
    heading it does not belong to, which reads as a fact about the configuration.
    """
    assert tasks.get_project_for_solo_task("13", [])[0] == "No Project"


# ##################################################################################
# The icon shown beside a Task's name
# ##################################################################################
def test_a_task_icon_is_summarised() -> None:
    """An icon is stored as a package, a class and a name, each fully qualified.  Only
    the last segment of each is worth showing beside a Task name.
    """
    task = ET.fromstring(  # noqa: S314  (fixture text, built in this file)
        "<Task><Img><nme>com.foo.bar</nme><pkg>net.dinglisch.android.taskerm</pkg></Img></Task>",
    )
    assert tasks.get_icon_info(task) == "[Icon Info(pkg=taskerm name=bar)]"


def test_a_task_without_an_icon_shows_nothing() -> None:
    """Most Tasks have no icon, so this is the common path -- an empty "[Icon Info()]"
    on every Task line would be noise on every line.
    """
    assert tasks.get_icon_info(ET.fromstring("<Task/>")) == ""  # noqa: S314
    assert tasks.get_icon_info(None) == ""


def test_an_icon_field_that_is_absent_is_skipped() -> None:
    """get_image is called once per field and most icons set only some of them."""
    image = ET.fromstring("<Img><pkg>a.b.c</pkg></Img>")  # noqa: S314
    assert tasks.get_image(image, "pkg", "pkg") == "pkg=c "
    assert tasks.get_image(image, "class", "cls") == ""


def test_an_unqualified_icon_field_is_shown_whole() -> None:
    """Only the segment after the last '.' is shown, and a value with no '.' in it is
    already that segment -- taking the split unconditionally would drop it entirely.
    """
    image = ET.fromstring("<Img><nme>flashlight</nme></Img>")  # noqa: S314
    assert tasks.get_image(image, "name", "nme") == "name=flashlight "


@pytest.mark.xfail(
    reason="Pre-existing defect: an empty element (<nme/>) has text None, and get_image does "
    "'.' in text on it -- a TypeError rather than the empty string its own docstring promises. "
    "Reached from get_icon_info for any Task whose <Img> carries an empty field.",
    strict=False,
)
def test_an_empty_icon_field_is_skipped() -> None:
    """Tasker writes an empty element for a field that was cleared rather than dropping
    it, so this is a shape that reaches the parser from a real backup.
    """
    image = ET.fromstring("<Img><nme></nme><pkg>a.b.c</pkg></Img>")  # noqa: S314
    assert tasks.get_image(image, "name", "nme") == ""


# ##################################################################################
# The pretty-mode reformatting of an action's configuration parameters
# ##################################################################################
def test_configuration_parameters_are_split_onto_their_own_lines() -> None:
    """A Perform Task action carries its parameters as one ';'-separated run.  In pretty
    mode each gets its own line, indented to hang under the label.
    """
    result = tasks.reformat_html(
        "Perform Task&nbsp;&nbsp;Name=Sub;Configuration Parameter(s):alpha=1;beta=2<span>tail</span>",
    )
    assert "alpha=1" in result
    assert "beta=2" in result
    assert result.count("\n") >= 2
    assert "&nbsp;" * 9 in result  # the hanging indent the parameters are aligned to


def test_text_without_configuration_parameters_is_left_alone() -> None:
    """Most actions have none, and the pattern must not match half of an ordinary line."""
    assert tasks.reformat_html("Flash&nbsp;&nbsp;Text=hi") == "Flash&nbsp;&nbsp;Text=hi"


@pytest.mark.xfail(
    reason="Pre-existing defect: replace_except_last DELETES the final occurrence instead of "
    "leaving it in place -- str.join over a one-element list puts no separator back. The last "
    "line of a reformatted parameter block loses its line break as a result.",
    strict=False,
)
def test_the_last_occurrence_is_kept_not_dropped() -> None:
    """The function's whole contract: replace every occurrence except the last, and leave
    that last one alone.
    """
    assert tasks.replace_except_last("a,b,c", ",", ";") == "a;b,c"
    assert tasks.replace_except_last("a,b", ",", ";") == "a,b"


def test_text_without_the_target_is_unchanged() -> None:
    """Nothing to replace and nothing to keep -- the path taken by every action line that
    has no parameter block at all.
    """
    assert tasks.replace_except_last("abc", ",", ";") == "abc"
