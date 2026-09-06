"""MapTasker XML load (taskerd) Unit Tests

taskerd builds the five lookup tables -- all_projects/all_profiles/all_tasks/all_scenes,
plus the two by-name indexes -- that every other part of the program navigates a backup
through.  Nothing downstream re-derives them, so a table that is keyed wrongly, or that
is missing the Profiles and Tasks Tasker left unnamed, is not a visible error anywhere:
the object simply is not in the map, the diagram, or the Find results.

The derived names are most of what is asserted here.  Tasker writes no <nme> for a
Profile the user never named and no <nme> for a Task the user never named, and taskerd
invents one for each -- a Profile's from its run conditions, a Task's from its first
action.  Those invented names are what the user sees, what the directory links to, and
what all_profiles_by_name/all_tasks_by_name are keyed on, so a change in how they are
built silently renames objects across the whole product.
"""

from __future__ import annotations

import os
import tempfile
import xml.etree.ElementTree as ET

import pytest

from maptasker.src import taskerd
from maptasker.src.colrmode import set_color_mode
from maptasker.src.lineout import LineOut
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import UNNAMED_ITEM

# An action's <label> is rendered through format_label, which reads real colors out of
# colors_to_use -- an empty color table is a KeyError there, not a plain-text fallback.
FLASH = '<Action sr="act0"><code>548</code><Str sr="arg0">hello</Str></Action>'
ANCHOR = '<Action sr="act0"><code>300</code><label>Top of loop</label></Action>'


@pytest.fixture(autouse=True)
def _prime_items() -> None:
    """The globals taskerd writes into: the settings it reads, and somewhere to put lines."""
    PrimeItems.program_arguments = {
        "debug": False,
        "directory": False,
        "pretty": False,
        "gui": False,
        "display_detail_level": 3,
    }
    PrimeItems.colors_to_use = set_color_mode("dark")
    PrimeItems.output_lines = LineOut()
    PrimeItems.error_msg = ""


def _build(body: str) -> dict:
    """Build the lookup tables from the given <TaskerData> body, as a loaded file would."""
    PrimeItems.xml_root = ET.fromstring(  # noqa: S314  (fixture text, built in this file)
        f'<TaskerData sr="" dvi="1" tv="6.3.13">{body}</TaskerData>',
    )
    taskerd.build_tasker_tables()
    return PrimeItems.tasker_root_elements


# ##################################################################################
# move_xml_to_table -- what each table is keyed on
# ##################################################################################
def test_profiles_and_tasks_are_keyed_by_id() -> None:
    """A Profile or Task is referenced from everywhere else by its <id>, never by name:
    a Project lists <tids>10,11</tids>, and a Profile names its Tasks in <mid0>/<mid1>.
    Keying those two tables by name instead would break every one of those lookups.
    """
    tables = _build(
        '<Profile sr="prof5"><id>5</id><nme>Morning</nme></Profile>'
        '<Task sr="task10"><id>10</id><nme>Wake Up</nme></Task>',
    )
    assert set(tables["all_profiles"]) == {"5"}
    assert set(tables["all_tasks"]) == {"10"}
    assert tables["all_profiles"]["5"]["name"] == "Morning"
    assert tables["all_tasks"]["10"]["name"] == "Wake Up"


def test_projects_and_scenes_are_keyed_by_name() -> None:
    """Projects and Scenes carry no <id> -- they are referred to by name, and the two
    tables are keyed that way.  A Project's own name lives in <name>, a Scene's in <nme>.
    """
    tables = _build(
        '<Project sr="proj0"><name>Home</name></Project><Scene sr="scene0"><nme>Panel</nme></Scene>',
    )
    assert set(tables["all_projects"]) == {"Home"}
    assert set(tables["all_scenes"]) == {"Panel"}


def test_name_whitespace_is_stripped() -> None:
    """Tasker keeps whatever spacing the user typed.  The name is a dictionary key here
    and is matched against --project/--profile/--task arguments, so a stray space would
    make the object unreachable by the name shown for it.
    """
    tables = _build('<Project sr="proj0"><name>  Home  </name></Project>')
    assert set(tables["all_projects"]) == {"Home"}


def test_settings_are_carried_through_untouched() -> None:
    """all_services is the raw <Setting> list, not a name table -- it is the one entry
    that is a list, and the ones that read it index it positionally.
    """
    tables = _build("<Setting><n>k</n><v>1</v></Setting><Setting><n>j</n><v>2</v></Setting>")
    assert len(tables["all_services"]) == 2


# ##################################################################################
# The names taskerd invents for objects Tasker left unnamed
# ##################################################################################
def test_unnamed_profile_is_named_for_its_conditions() -> None:
    """A Profile the user never named has no <nme> at all, and would otherwise be listed
    as a nameless row.  Its run conditions are what actually distinguishes it, so those
    become its name -- with the Profile id appended, since two Profiles may well run on
    the same condition and the name is a key in all_profiles_by_name.
    """
    tables = _build('<Profile sr="prof6"><id>6</id><Time sr="con0"><fh>8</fh><fm>0</fm></Time></Profile>')
    name = tables["all_profiles"]["6"]["name"]
    assert name.endswith(f".6 {UNNAMED_ITEM}")
    assert "800" in name  # the 8:00 time condition it was named after


def test_unnamed_profile_name_carries_no_markup() -> None:
    """The condition text arrives with <em> in it, and this name is used as a dictionary
    key and written into the directory -- both of which want the text, not the markup.
    """
    tables = _build(
        '<Profile sr="prof7"><id>7</id>'
        '<Time sr="con0"><fh>8</fh><fm>0</fm></Time><Time sr="con1"><fh>9</fh><fm>0</fm></Time>'
        "</Profile>",
    )
    assert "<em>" not in tables["all_profiles"]["7"]["name"]


def test_unnamed_task_is_named_for_its_first_action() -> None:
    """The same problem for Tasks, solved from the other end: what a Task does is its
    first action, so an unnamed Task is listed under that action plus its own id.
    """
    tables = _build(f'<Task sr="task11"><id>11</id>{FLASH}</Task>')
    assert tables["all_tasks"]["11"]["name"] == "Flash Text=hello.11 (Unnamed)"


def test_unnamed_anchor_task_is_named_for_its_label() -> None:
    """An Anchor action does nothing except carry a label, so naming the Task after the
    action alone ("Anchor ...with label:") tells the user nothing and reads as a broken
    line.  The label is what the Anchor is FOR, so it becomes the name.
    """
    tables = _build(f'<Task sr="task20"><id>20</id>{ANCHOR}</Task>')
    name = tables["all_tasks"]["20"]["name"]
    assert name.startswith('Anchor "Top of l')
    assert "...with label:" not in name


def test_task_with_no_first_action_still_gets_a_name() -> None:
    """An empty Task, and one whose actions do not start at act0, both have no first
    action to be named after.  They still need a name: it is the key of the by-name
    table, and a second nameless Task would otherwise overwrite the first.
    """
    tables = _build('<Task sr="task21"><id>21</id></Task><Task sr="task22"><id>22</id></Task>')
    assert tables["all_tasks"]["21"]["name"] == ".21 (Unnamed)"
    assert tables["all_tasks"]["22"]["name"] == ".22 (Unnamed)"
    assert len(tables["all_tasks_by_name"]) == 2


def test_named_objects_are_left_alone() -> None:
    """The derived-name passes must not touch an object that already has a name."""
    tables = _build(
        f'<Task sr="task10"><id>10</id><nme>Wake Up</nme>{FLASH}</Task>'
        '<Profile sr="prof5"><id>5</id><nme>Morning</nme>'
        "<Time sr=\"con0\"><fh>8</fh><fm>0</fm></Time></Profile>",
    )
    assert tables["all_tasks"]["10"]["name"] == "Wake Up"
    assert tables["all_profiles"]["5"]["name"] == "Morning"


# ##################################################################################
# The by-name indexes
# ##################################################################################
def test_by_name_tables_map_names_back_to_ids() -> None:
    """Everything the user types or clicks is a name -- Edit Profile, Find, the single
    item arguments -- and every lookup that follows needs the id.  These two tables are
    that translation, and they index the DERIVED name, so an unnamed object is reachable
    by the name it is actually displayed under.
    """
    tables = _build(
        '<Profile sr="prof5"><id>5</id><nme>Morning</nme></Profile>'
        f'<Task sr="task11"><id>11</id>{FLASH}</Task>',
    )
    assert tables["all_profiles_by_name"]["Morning"]["id"] == "5"
    assert tables["all_tasks_by_name"]["Flash Text=hello.11 (Unnamed)"]["id"] == "11"
    assert tables["all_tasks_by_name"]["Flash Text=hello.11 (Unnamed)"]["xml"] is tables["all_tasks"]["11"]["xml"]


def test_task_tables_come_out_sorted() -> None:
    """Both Task tables are sorted, which is what puts the Task list in a predictable
    order rather than in whatever order the backup file happened to store them.
    """
    tables = _build(
        '<Task sr="task3"><id>3</id><nme>Charlie</nme></Task>'
        '<Task sr="task1"><id>1</id><nme>Alpha</nme></Task>'
        '<Task sr="task2"><id>2</id><nme>Bravo</nme></Task>',
    )
    assert list(tables["all_tasks"]) == ["1", "2", "3"]
    assert list(tables["all_tasks_by_name"]) == ["Alpha", "Bravo", "Charlie"]


def test_empty_configuration_builds_empty_tables() -> None:
    """A backup with nothing in it is a valid backup.  Every table must still exist:
    the callers index into them without checking, so a missing key is a crash on load.
    """
    tables = _build("")
    for key in (
        "all_projects",
        "all_profiles",
        "all_profiles_by_name",
        "all_tasks",
        "all_tasks_by_name",
        "all_scenes",
    ):
        assert tables[key] == {}
    assert tables["all_services"] == []


# ##################################################################################
# get_first_action
# ##################################################################################
def test_get_first_action_reads_act0_not_document_order() -> None:
    """Tasker stores actions in whatever order it likes and numbers them in sr=; act0 is
    the one that runs first.  Taking the first <Action> in the file instead would name a
    Task after an action from the middle of it.
    """
    task = ET.fromstring(  # noqa: S314  (fixture text, built in this file)
        '<Task sr="task1"><id>1</id>'
        '<Action sr="act1"><code>548</code><Str sr="arg0">second</Str></Action>'
        '<Action sr="act0"><code>548</code><Str sr="arg0">first</Str></Action>'
        "</Task>",
    )
    assert taskerd.get_first_action(task) == "Flash Text=first"


def test_get_first_action_of_a_task_without_one_is_empty() -> None:
    """No act0 is not an error -- the caller turns the empty string into ".<id> (Unnamed)"."""
    task = ET.fromstring(  # noqa: S314  (fixture text, built in this file)
        '<Task sr="task1"><id>1</id><Action sr="act1"><code>548</code><Str sr="arg0">x</Str></Action></Task>',
    )
    assert taskerd.get_first_action(task) == ""


def test_get_first_action_is_truncated() -> None:
    """This is a name in a list, not the action's own line: an action with a long
    argument would otherwise push the whole column open.
    """
    task = ET.fromstring(  # noqa: S314  (fixture text, built in this file)
        f'<Task sr="task1"><id>1</id><Action sr="act0"><code>548</code><Str sr="arg0">{"x" * 200}</Str></Action></Task>',
    )
    result = taskerd.get_first_action(task)
    assert len(result) < 40
    assert result.endswith("...")


# ##################################################################################
# get_the_xml_data -- the file, and what happens when it is not a backup
# ##################################################################################
def _load_file(text: str) -> int:
    """Write the text to a temporary file and load it the way the program does."""
    handle = tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False)  # noqa: SIM115
    try:
        handle.write(text)
        handle.close()
        with open(handle.name) as opened:
            PrimeItems.file_to_get = opened
            return taskerd.get_the_xml_data()
    finally:
        os.unlink(handle.name)


def test_a_backup_file_loads_and_builds_the_tables() -> None:
    """The whole path, from a file on disk to the tables -- 0 means loaded."""
    assert _load_file('<TaskerData sr="" dvi="1" tv="6.3.13"><Task sr="task1"><id>1</id><nme>T</nme></Task></TaskerData>') == 0
    assert PrimeItems.tasker_root_elements["all_tasks"]["1"]["name"] == "T"


def test_a_file_that_is_not_a_tasker_backup_is_refused() -> None:
    """Well-formed XML that is not a backup -- any other XML file the user picks by
    mistake.  Parsing it as one would build empty tables and show an empty map, which
    looks like a backup with nothing in it rather than like the wrong file.
    """
    assert _load_file("<NotTasker><something/></NotTasker>") == 3


def test_the_gui_is_told_why_a_file_was_refused() -> None:
    """The GUI has no console to print to: it shows error_msg, so the reason has to be
    put there or the file simply fails to load with nothing said.
    """
    PrimeItems.program_arguments["gui"] = True
    assert _load_file("<NotTasker><something/></NotTasker>") == 3
    assert PrimeItems.error_msg == "Invalid Tasker backup XML file"


def test_a_corrupt_file_stops_the_run() -> None:
    """XML that does not parse cannot be recovered from -- continuing would run the rest
    of the program against whatever configuration was loaded before it.
    """
    with pytest.raises(SystemExit):
        _load_file("<TaskerData><unclosed>")
