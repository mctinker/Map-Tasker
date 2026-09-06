"""MapTasker Profile parsing (profiles) Unit Tests

A Profile is the part of a Tasker configuration with the least to show for itself: most
carry no name, and what distinguishes one from the next is the condition it runs on and
the one or two Tasks it fires.  profiles.py is what turns that into something readable,
and almost all of it is name derivation -- which is the part with no obvious right
answer and therefore the part that quietly drifts.

Two things here are worth stating up front because they look like test-fixture trivia
and are not:

*  Element order matters.  get_profile_tasks walks the Profile's children in document
   order and STOPS at <nme>, because Tasker writes <mid0>/<mid1> before the name.  A
   fixture that puts <nme> first finds no Tasks at all -- which is exactly the bug that
   ordering assumption would cause against a backup written by a future Tasker.
*  <mid0> is the Entry Task and <mid1> is the Exit Task.  Nothing in the names says so,
   and swapping them puts the wrong arrow on both lines.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from maptasker.src import profiles, taskerd
from maptasker.src.colrmode import set_color_mode
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.lineout import LineOut
from maptasker.src.primitem import PrimeItems, initial_found_named_items

# <mid0>/<mid1> before <nme>, the way Tasker writes a Profile -- see the module docstring.
_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Profile sr="prof5"><id>5</id><mid0>10</mid0><mid1>11</mid1><nme>Morning</nme></Profile>
  <Profile sr="prof6"><id>6</id><mid0>10</mid0><Time sr="con0"><fh>8</fh><fm>0</fm></Time></Profile>
  <Profile sr="prof7"><id>7</id><mid0>10</mid0><nme>Disabled One</nme><limit>true</limit></Profile>
  <Profile sr="prof8"><id>8</id><mid0>10</mid0><nme>Named At Eight</nme><Time sr="con0"><fh>8</fh><fm>0</fm></Time></Profile>
  <Task sr="task10"><id>10</id><nme>Entry Task</nme></Task>
  <Task sr="task11"><id>11</id><nme>Exit Task</nme></Task>
</TaskerData>"""

ENTRY_ARROW = "&#11013;"  # points left, at the Profile that fired the Task
EXIT_ARROW = "&#11157;"


@pytest.fixture(autouse=True)
def _loaded() -> None:
    """The fixture configuration, loaded into the tables the way taskerd does from a file."""
    # The real defaults rather than a hand-picked subset: the output path reads settings
    # the parsing code never mentions, and a missing key there is a KeyError, not a default.
    PrimeItems.program_arguments = initialize_runtime_arguments()
    PrimeItems.program_arguments["conditions"] = True  # off by default; most of this file needs it
    PrimeItems.found_named_items = initial_found_named_items()
    PrimeItems.colors_to_use = set_color_mode("dark")
    PrimeItems.output_lines = LineOut()
    PrimeItems.task_count_for_profile = 0
    PrimeItems.task_count_unnamed = 0
    PrimeItems.xml_root = ET.fromstring(_XML)  # noqa: S314  (fixture text, defined in this file)
    taskerd.build_tasker_tables()


def _profile(profile_id: str) -> ET.Element:
    """The Profile xml element for an id."""
    return PrimeItems.tasker_root_elements["all_profiles"][profile_id]["xml"]


# ##################################################################################
# get_profile_tasks -- which Tasks a Profile fires, and in which role
# ##################################################################################
def test_entry_and_exit_tasks_are_told_apart() -> None:
    """<mid0> is the Task that runs when the condition becomes true and <mid1> the one
    that runs when it stops being true.  They are drawn with opposite arrows and mean
    opposite things, and only the element name says which is which.
    """
    output_lines: list[str] = []
    found = profiles.get_profile_tasks(_profile("5"), [], output_lines)

    assert len(found) == 2
    assert ENTRY_ARROW in output_lines[0] and "Entry Task" in output_lines[0]
    assert EXIT_ARROW in output_lines[1] and "Exit Task" in output_lines[1]


def test_task_search_stops_at_the_profile_name() -> None:
    """The walk stops at <nme>: everything after it is the Profile's own detail, not
    more Tasks.  Asserted so that the stop condition is a decision and not an accident
    -- a Profile whose Tasks come after its name would silently lose them.
    """
    profile = ET.fromstring(  # noqa: S314  (fixture text, built in this file)
        '<Profile sr="prof9"><id>9</id><nme>Named First</nme><mid0>10</mid0></Profile>',
    )
    assert profiles.get_profile_tasks(profile, [], []) == []


def test_profile_task_count_skips_tasks_already_seen() -> None:
    """The per-Profile count feeds the run's totals.  A Task fired by two Profiles is one
    Task, so counting it once per sighting would inflate the configuration's size.
    """
    profiles.get_profile_tasks(_profile("5"), [], [])
    assert PrimeItems.task_count_for_profile == 2

    already_found = ["10", "11"]
    profiles.get_profile_tasks(_profile("5"), already_found, [])
    assert PrimeItems.task_count_for_profile == 2  # unchanged


def test_a_single_task_search_records_its_owning_profile() -> None:
    """--task asks for one Task by name.  The Profile that fires it has to be recorded
    on the way past, because the output is built Project > Profile > Task and the caller
    otherwise has no way back to the Profile heading the Task belongs under.
    """
    PrimeItems.program_arguments["single_task_name"] = "Exit Task"
    profiles.get_profile_tasks(_profile("5"), [], [])

    assert PrimeItems.found_named_items["single_task_found"] is True
    assert PrimeItems.program_arguments["single_profile_name"] == "Morning"


def test_bookkeeping_tags_are_not_mistaken_for_tasks() -> None:
    """<id>, <limit>, <flags>, <cdate>, <edate> sit among the Task references and are
    not Tasks.  <limit> in particular is the disabled flag, and reading it as a Task id
    would look up a Task called "true".
    """
    profile = ET.fromstring(  # noqa: S314  (fixture text, built in this file)
        '<Profile sr="prof9"><id>9</id><cdate>1</cdate><edate>2</edate>'
        "<flags>x</flags><limit>true</limit><mid0>10</mid0></Profile>",
    )
    found = profiles.get_profile_tasks(profile, [], [])
    assert len(found) == 1


# ##################################################################################
# get_profile_name
# ##################################################################################
def test_profile_name_is_labelled_and_coloured() -> None:
    """The name is returned twice: once dressed for the HTML output, and once bare for
    use as a key.  The bare one must stay bare -- it is what the tables are keyed on.
    """
    with_html, plain = profiles.get_profile_name(_profile("5"))
    assert plain == "Morning"
    assert 'class="profile_color"' in with_html
    assert "Profile:" in with_html


def test_unnamed_profile_name_is_italicised_but_its_id_is_not() -> None:
    """A derived name is not the user's name for the Profile and is shown in italics to
    say so.  The ".6 Unnamed" suffix is the program talking and stays outside the <em>,
    so the italics mark the condition text only.
    """
    with_html, plain = profiles.get_profile_name(_profile("6"))
    assert "<em>*from 800 to 00</em>" in with_html
    assert "<em>" not in plain


def test_profile_label_carries_a_tooltip_of_its_project_and_tasks() -> None:
    """A Profile line shows the condition, not the Tasks -- so the Tasks it fires, and
    the Project it belongs to, are on the label's hover tooltip instead.
    """
    with_html, _ = profiles.get_profile_name(_profile("5"), "Home", ["Entry Task", "Exit Task"])
    assert 'class="hover-tooltip"' in with_html
    assert "Project: Home" in with_html
    assert "Entry Task" in with_html


def test_profile_label_has_no_tooltip_when_there_is_nothing_to_say() -> None:
    """An empty tooltip is worse than none: it shows an empty box on hover."""
    with_html, _ = profiles.get_profile_name(_profile("5"))
    assert "hover-tooltip" not in with_html


def test_debug_mode_shows_the_profile_id() -> None:
    """The id is what the tables are keyed on and what <tids> references -- it is the
    thing you need when a Profile is not where it should be, and is otherwise invisible.
    """
    PrimeItems.program_arguments["debug"] = True
    with_html, _ = profiles.get_profile_name(_profile("5"))
    assert "ID:5" in with_html


# ##################################################################################
# build_profile_line -- the Profile's one line of output
# ##################################################################################
# Profile 8 is NAMED and has a condition.  Profile 6 would not do for these two: it is
# unnamed, so its name is derived FROM the condition and mentions the time either way --
# a "condition is shown" test against it passes even when the condition is left out.
def test_profile_line_shows_its_run_condition() -> None:
    """The condition is the whole point of a Profile: without it the line says only that
    a Profile exists.
    """
    profiles.build_profile_line(_profile("8"))
    line = PrimeItems.output_lines.output_lines[-1]
    assert "Time: from 8:00" in line
    assert 'class="profile_condition_color"' in line


def test_conditions_can_be_turned_off() -> None:
    """--conditions is off by default because the condition text is long.  When it is
    off the Profile is still listed -- only its condition is left out.
    """
    PrimeItems.program_arguments["conditions"] = False
    profiles.build_profile_line(_profile("8"))
    line = PrimeItems.output_lines.output_lines[-1]
    assert "8:00" not in line
    assert "Named At Eight" in line


def test_a_disabled_profile_says_so() -> None:
    """<limit>true</limit> is a Profile the user switched off.  It is still in the
    configuration and still listed, and nothing else on the line distinguishes it from
    one that runs every day.
    """
    profiles.build_profile_line(_profile("7"))
    line = PrimeItems.output_lines.output_lines[-1]
    assert 'class="disabled_profile_color"' in line


def test_an_enabled_profile_is_not_marked_disabled() -> None:
    """The other half of the same check: <limit> absent, and a <limit> that is not
    "true", both mean the Profile runs.
    """
    profiles.build_profile_line(_profile("5"))
    assert "disabled_profile_color" not in PrimeItems.output_lines.output_lines[-1]


# ##################################################################################
# The string surgery the derived names are built out of
# ##################################################################################
def test_priority_is_removed_along_with_its_value() -> None:
    """remove_substring_and_next drops the substring AND the characters after it, which
    is how "Priority:5" is taken out of a condition -- removing only "Priority:" would
    leave a bare "5" sitting in the Profile's name.
    """
    assert profiles.remove_substring_and_next("Priority:5 rest", "Priority:") == " rest"
    assert profiles.remove_substring_and_next("aXbb", "X", 2) == "a"


def test_removing_a_substring_that_is_not_there_changes_nothing() -> None:
    """Most conditions carry no priority, so this is the common case, not the edge one."""
    assert profiles.remove_substring_and_next("no match here", "Priority:") == "no match here"


def test_removing_a_substring_at_the_very_end_does_not_overrun() -> None:
    """Nothing follows it to remove.  Slicing past the end of a string is silent in
    Python, so the risk here is a wrong result rather than an error.
    """
    assert profiles.remove_substring_and_next("abcPriority:", "Priority:") == "abc"


def test_the_field_name_before_an_equals_is_dropped() -> None:
    """A condition reads "Display State=on", and the name is built from the values, not
    the field names: the Profile is worth listing as "Display on".
    """
    assert profiles.delete_non_blank_before_equals("Foo=bar") == "bar"
    assert profiles.delete_non_blank_before_equals("a Foo=bar baz Qux=1") == "a bar baz 1"


def test_text_with_no_equals_is_left_alone() -> None:
    assert profiles.delete_non_blank_before_equals("nothing here") == "nothing here"


def test_a_condition_becomes_a_name() -> None:
    """The end of that chain: a run condition, turned into something short enough to be
    a name.  The leading '*' marks it as derived rather than given.
    """
    assert profiles.set_name_to_condition("State: Display State=on", "x") == "*Display on"


def test_a_profile_with_no_name_at_all_gets_no_derived_name() -> None:
    """set_name_to_condition returns the name it was handed when that name is empty --
    the guard that stops a Profile with neither name nor conditions being called "*".
    """
    assert profiles.set_name_to_condition("Event: Date Set", "") == ""


def test_a_derived_name_is_truncated() -> None:
    """A Profile can run on a page of conditions.  The name goes in a list and in the
    directory, so it is cut down -- with the markup removed first, so the cut cannot
    land in the middle of a tag and leave it unclosed.
    """
    long_condition = "State: " + ", ".join(f"Thing{n} Value{n}" for n in range(20))
    name = profiles.set_name_to_condition(long_condition, "x")
    assert len(name) <= 36  # 35 characters plus the leading '*'
    assert "<" not in name
