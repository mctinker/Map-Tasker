"""MapTasker Project parsing (projects) Unit Tests

projects.py is the top of the walk: it decides what a backup actually contains and
therefore which way the whole run goes.  A Tasker backup is not always a set of
Projects -- the user can export a single Profile, a single Task, or a single Scene, and
each of those arrives as a <TaskerData> file with most of the tree simply absent.

That routing is what most of this file tests.  It matters more than it looks: choosing
the wrong branch does not fail, it produces an empty or near-empty map for a file that
plainly had something in it, and the user's conclusion is that their backup is broken.

The other half is the per-Project counts.  They are accumulated across Projects into the
run's grand totals and printed as fact ("a total of N Profiles, M Tasks"), with nothing
anywhere to check them against.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET

import pytest

from maptasker.src import projects, taskerd
from maptasker.src.colrmode import set_color_mode
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.lineout import LineOut
from maptasker.src.primitem import (
    PrimeItems,
    initial_directory_items,
    initial_found_named_items,
    initial_grand_totals,
)
from maptasker.src.proginit import build_action_codes_from_json


@pytest.fixture(autouse=True)
def _clean_globals() -> None:
    """A fresh set of the counters and tables a run accumulates into."""
    cwd = os.getcwd()
    build_action_codes_from_json(False)  # chdir's into assets and does not come back
    os.chdir(cwd)

    PrimeItems.program_arguments = initialize_runtime_arguments()
    PrimeItems.colors_to_use = set_color_mode("dark")
    PrimeItems.output_lines = LineOut()
    PrimeItems.found_named_items = initial_found_named_items()
    PrimeItems.grand_totals = initial_grand_totals()
    PrimeItems.directory_items = initial_directory_items()
    PrimeItems.emitted_anchors = set()
    projects.setup_summary_counts()


def _load(body: str) -> None:
    """Load a <TaskerData> body into the lookup tables, the way taskerd does from a file."""
    PrimeItems.xml_root = ET.fromstring(  # noqa: S314  (fixture text, built in this file)
        f'<TaskerData sr="" dvi="1" tv="6.3.13">{body}</TaskerData>',
    )
    taskerd.build_tasker_tables()


def _project(name: str) -> ET.Element:
    return PrimeItems.tasker_root_elements["all_projects"][name]["xml"]


def _output() -> str:
    return "".join(PrimeItems.output_lines.output_lines)


# ##################################################################################
# The launcher Task
# ##################################################################################
def test_a_launcher_task_is_named_on_the_project_line() -> None:
    """A launcher Task is what runs when the user taps the Project's home-screen icon --
    it is the Project's entry point and is not referenced from anywhere else in the tree.
    """
    _load('<Project sr="proj0"><name>Home</name><Share><t>Launch Me</t></Share></Project>')
    result = projects.get_launcher_task(_project("Home"), "Home")
    assert "[Launcher Task: Launch Me]" in result
    assert 'class="launcher_task_color"' in result


def test_a_project_without_a_launcher_task_says_nothing() -> None:
    """Most Projects have none.  <Share> is also where the TaskerNet description lives,
    so a Project can have the element without a launcher Task in it -- both shapes have
    to come back empty rather than printing an empty "[Launcher Task: ]".
    """
    _load('<Project sr="proj0"><name>Home</name></Project>')
    assert projects.get_launcher_task(_project("Home"), "Home") == ""

    _load('<Project sr="proj1"><name>Shared</name><Share><d>a description</d></Share></Project>')
    assert projects.get_launcher_task(_project("Shared"), "Shared") == ""


# ##################################################################################
# Which Profiles a Project owns
# ##################################################################################
def test_a_projects_profiles_are_read_from_its_pids() -> None:
    """<pids> is the only link from a Project to its Profiles -- a Profile element says
    nothing about which Project it belongs to.
    """
    _load('<Project sr="proj0"><name>Home</name><pids>1,2</pids></Project>')
    assert projects.get_profile_ids(_project("Home"), "Home", []) == ["1", "2"]


def test_a_project_with_no_profiles_is_recorded_as_such() -> None:
    """The run reports Projects that contain nothing, and this walk is where an empty one
    is noticed.
    """
    _load('<Project sr="proj0"><name>Home</name></Project>')
    without_profiles: list[str] = []
    assert projects.get_profile_ids(_project("Home"), "Home", without_profiles) == []
    assert "Home" in without_profiles


# ##################################################################################
# The counts printed for each Project, and rolled up into the run's totals
# ##################################################################################
def test_the_project_summary_reports_what_was_counted() -> None:
    """These numbers are printed as fact and there is nothing to check them against."""
    PrimeItems.task_count_for_profile = 7
    PrimeItems.named_task_count_total = 5
    PrimeItems.task_count_unnamed = 2
    PrimeItems.task_count_no_profile = 1
    PrimeItems.scene_count = 3

    projects.summary_counts("Home", 4)
    line = _output()
    assert "Project Home has a total of 4 Profiles" in line
    assert "7  Tasks called by Profiles" in line
    assert "2 unnamed Tasks" in line
    assert "1 Tasks not in any Profile" in line
    assert "5 named Tasks out of 7 total Tasks" in line
    assert "3 Scenes" in line


def test_project_counts_accumulate_into_the_run_total() -> None:
    """The grand totals are the sum over Projects -- summary_counts is the only place
    they are added to, so a Project that does not pass through here is missing from the
    figure the run finishes with.
    """
    PrimeItems.named_task_count_total = 5
    PrimeItems.task_count_unnamed = 2
    PrimeItems.scene_count = 3
    projects.summary_counts("Home", 4)

    projects.setup_summary_counts()
    PrimeItems.named_task_count_total = 1
    PrimeItems.scene_count = 1
    projects.summary_counts("Away", 2)

    assert PrimeItems.grand_totals == {
        "projects": 2,
        "profiles": 6,
        "unnamed_tasks": 2,
        "named_tasks": 6,
        "scenes": 4,
    }


def test_counters_are_reset_between_projects() -> None:
    """Without the reset each Project's line would show a running total rather than its
    own contents, and the grand totals would count earlier Projects again.
    """
    PrimeItems.task_count_for_profile = 9
    PrimeItems.named_task_count_total = 9
    PrimeItems.task_count_unnamed = 9
    PrimeItems.task_count_no_profile = 9
    PrimeItems.scene_count = 9

    assert projects.setup_summary_counts() == 0
    assert PrimeItems.task_count_for_profile == 0
    assert PrimeItems.named_task_count_total == 0
    assert PrimeItems.task_count_unnamed == 0
    assert PrimeItems.task_count_no_profile == 0
    assert PrimeItems.scene_count == 0


# ##################################################################################
# Working out what kind of backup this is
# ##################################################################################
def test_a_backup_with_projects_is_walked_from_the_projects() -> None:
    """The ordinary case: a full backup, walked Project > Profile > Task."""
    _load(
        '<Project sr="proj0"><name>Home</name><pids>5</pids></Project>'
        '<Profile sr="prof5"><id>5</id><mid0>10</mid0><nme>Morning</nme></Profile>'
        '<Task sr="task10"><id>10</id><nme>Alpha</nme></Task>',
    )
    projects.process_projects_and_their_profiles([], [])
    output = _output()
    assert "Home" in output
    assert "Morning" in output


def test_a_profile_export_is_walked_from_the_profiles() -> None:
    """Exporting one Profile produces a backup with no Project at all.  Falling through
    to the Project branch would output nothing and report an empty configuration.
    """
    _load(
        '<Profile sr="prof5"><id>5</id><mid0>10</mid0><nme>Morning</nme></Profile>'
        '<Task sr="task10"><id>10</id><nme>Alpha</nme></Task>',
    )
    projects.process_projects_and_their_profiles([], [])
    assert "Morning" in _output()


def test_a_task_export_is_walked_from_the_tasks() -> None:
    """A single exported Task: no Project, no Profile, and no Scene either -- the last
    condition matters, because a Scene export also carries the Tasks its buttons fire.
    """
    _load('<Task sr="task10"><id>10</id><nme>Alpha</nme></Task><Task sr="task11"><id>11</id><nme>Beta</nme></Task>')
    projects.process_projects_and_their_profiles([], [])
    output = _output()
    assert "Alpha" in output
    assert "Beta" in output


def test_a_scene_export_is_walked_from_the_scenes() -> None:
    """A Scene export carries the Scene and the Tasks its elements fire.  It is the
    Scene that has to lead -- listing the loose Tasks instead shows the parts without
    the screen they belong to.
    """
    _load('<Scene sr="scene0"><nme>Panel</nme></Scene><Task sr="task10"><id>10</id><nme>Alpha</nme></Task>')
    projects.process_projects_and_their_profiles([], [])
    assert "Panel" in _output()
    assert PrimeItems.grand_totals["scenes"] == 1


def test_an_unclaimed_scene_is_output_rather_than_reported_missing() -> None:
    """A Scene in the backup that no Project's <scenes> lists is reachable no other way:
    every path to a Scene goes through its Project.  Reporting "not found" for a Scene
    that is in the file, by the name the user gave, is a wrong answer -- it exists, it
    is just unclaimed.
    """
    _load('<Project sr="proj0"><name>Home</name></Project><Scene sr="scene0"><nme>Orphan</nme></Scene>')
    PrimeItems.program_arguments["single_scene_name"] = "Orphan"

    projects.output_orphan_single_scene()
    assert PrimeItems.found_named_items["single_scene_found"] is True
    assert PrimeItems.grand_totals["scenes"] == 1


def test_a_scene_already_found_is_not_output_twice() -> None:
    """The orphan path runs after the normal walk, so a Scene its Project already
    output would otherwise be listed a second time and counted twice.
    """
    _load('<Project sr="proj0"><name>Home</name></Project><Scene sr="scene0"><nme>Panel</nme></Scene>')
    PrimeItems.program_arguments["single_scene_name"] = "Panel"
    PrimeItems.found_named_items["single_scene_found"] = True

    projects.output_orphan_single_scene()
    assert PrimeItems.grand_totals["scenes"] == 0


def test_a_scene_name_that_is_not_in_the_backup_is_left_alone() -> None:
    """A genuine miss must stay a miss: the caller reports the requested Scene as not
    found, and marking it found here would silently swallow the user's typo.
    """
    _load('<Project sr="proj0"><name>Home</name></Project><Scene sr="scene0"><nme>Panel</nme></Scene>')
    PrimeItems.program_arguments["single_scene_name"] = "Nonexistent"

    projects.output_orphan_single_scene()
    assert PrimeItems.found_named_items["single_scene_found"] is False
    assert PrimeItems.grand_totals["scenes"] == 0


def test_the_orphan_path_does_nothing_on_an_ordinary_run() -> None:
    """No single Scene was asked for, so there is nothing to rescue."""
    _load('<Scene sr="scene0"><nme>Panel</nme></Scene>')
    projects.output_orphan_single_scene()
    assert PrimeItems.found_named_items["single_scene_found"] is False


def test_the_single_project_name_survives_the_walk() -> None:
    """process_profiles overwrites single_project_name as it goes.  The caller still
    needs the name the user asked for afterwards -- to report it as not found, if
    nothing matched.
    """
    _load(
        '<Project sr="proj0"><name>Home</name><pids>5</pids></Project>'
        '<Profile sr="prof5"><id>5</id><mid0>10</mid0><nme>Morning</nme></Profile>'
        '<Task sr="task10"><id>10</id><nme>Alpha</nme></Task>',
    )
    PrimeItems.program_arguments["single_project_name"] = "Home"
    projects.process_projects_and_their_profiles([], [])
    assert PrimeItems.program_arguments["single_project_name"] == "Home"


def test_found_tasks_come_back_deduplicated() -> None:
    """A Task fired by two Profiles is found twice.  The caller uses this list to work
    out which Tasks were in no Profile at all, so duplicates in it skew that answer.
    """
    _load(
        '<Project sr="proj0"><name>Home</name><pids>5,6</pids></Project>'
        '<Profile sr="prof5"><id>5</id><mid0>10</mid0><nme>One</nme></Profile>'
        '<Profile sr="prof6"><id>6</id><mid0>10</mid0><nme>Two</nme></Profile>'
        '<Task sr="task10"><id>10</id><nme>Shared</nme></Task>',
    )
    found = projects.process_projects_and_their_profiles([], [])
    assert sorted(found) == list(dict.fromkeys(found))
