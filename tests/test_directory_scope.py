"""The directory is kept to the one object that was asked for.

Ask for a single Project and the Map shows that Project alone -- but the directory used to
be filtered by rules that never asked which Project anything belonged to.  A Profile was
listed whatever Project owned it, a Task likewise, and a Scene was looked for in EVERY
Project rather than the selected one, so another Project's Scene of the same name passed.
Which Project a single Profile belonged to was decided by comparing the Project's own
number against its list of Profile ids -- two different kinds of number, so the answer
was whatever the numbering happened to make it.

The filters now ask one question of each entry: does the selected object own it?  What is
checked here is the answer for each kind of selection, and the one deliberate exception --
an object no Project claims at all is kept, because Tasker leaves a Scene's Task that way
and the Map put it on the page.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from maptasker.src import taskerd
from maptasker.src.dirout import check_item
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.primitem import PrimeItems
from maptasker.src.runcfg import RunConfig

# Two Projects that own one of everything each, so that "belongs to the selected Project"
# has something to be wrong about.  OrphanSceneTask is in no Project's <tids> -- the shape
# Tasker leaves a Task that is only attached to a Scene.
_XML = """
<Project sr="proj0"><name>Base</name><pids>1</pids><tids>10,11</tids><scenes>BaseScene</scenes></Project>
<Project sr="proj1"><name>Other</name><pids>2</pids><tids>12</tids><scenes>OtherScene</scenes></Project>
<Profile sr="prof1"><id>1</id><nme>BaseProfile</nme><mid0>10</mid0>
  <Time sr="con0"><fh>8</fh><fm>0</fm></Time></Profile>
<Profile sr="prof2"><id>2</id><nme>OtherProfile</nme><mid0>12</mid0>
  <Time sr="con0"><fh>9</fh><fm>0</fm></Time></Profile>
<Task sr="task10"><id>10</id><nme>BaseEntry</nme></Task>
<Task sr="task11"><id>11</id><nme>BaseLoose</nme></Task>
<Task sr="task12"><id>12</id><nme>OtherEntry</nme></Task>
<Task sr="task13"><id>13</id><nme>OrphanSceneTask</nme></Task>
<Scene sr="BaseScene"><nme>BaseScene</nme></Scene>
<Scene sr="OtherScene"><nme>OtherScene</nme></Scene>
"""

# A directory holding every object in that configuration, which is what the filters are
# handed to trim.
_DIRECTORY = {
    "projects": [["Base", "Base"], ["Other", "Other"]],
    "profiles": [["BaseProfile", "BaseProfile"], ["OtherProfile", "OtherProfile"]],
    "tasks": [
        ["BaseEntry", "BaseEntry"],
        ["BaseLoose", "BaseLoose"],
        ["OtherEntry", "OtherEntry"],
        ["OrphanSceneTask_(Scene)", "OrphanSceneTask (Scene)"],
    ],
    "scenes": [["BaseScene", "BaseScene"], ["OtherScene", "OtherScene"]],
}


@pytest.fixture(autouse=True)
def tasker_data() -> None:
    """Load the fixture XML into PrimeItems' lookup tables, and put them back after."""
    saved_elements = PrimeItems.tasker_root_elements
    saved_arguments = PrimeItems.program_arguments
    PrimeItems.program_arguments = initialize_runtime_arguments()
    PrimeItems.xml_root = ET.fromstring(  # noqa: S314  (fixture text, defined in this file)
        f'<TaskerData sr="" dvi="1" tv="6.3.13">{_XML}</TaskerData>',
    )
    taskerd.build_tasker_tables()
    yield
    PrimeItems.tasker_root_elements = saved_elements
    PrimeItems.program_arguments = saved_arguments


def listed(kind: str, config: RunConfig) -> list[str]:
    """The names of the given kind the directory would list under these settings."""
    return [item[1] for item in _DIRECTORY[kind] if check_item(kind, item, config)]


# ##################################################################################
# Nothing selected
# ##################################################################################
def test_everything_is_listed_when_nothing_in_particular_was_asked_for() -> None:
    """The ordinary case: the directory is the whole configuration."""
    everything = RunConfig()

    for kind, items in _DIRECTORY.items():
        assert listed(kind, everything) == [item[1] for item in items]


# ##################################################################################
# A single Project
# ##################################################################################
def test_a_single_project_lists_itself_and_what_it_owns() -> None:
    """The Project asked for, its Profiles, its Tasks and its Scenes -- and no others."""
    base = RunConfig(single_project_name="Base")

    assert listed("projects", base) == ["Base"]
    assert listed("profiles", base) == ["BaseProfile"]
    assert listed("scenes", base) == ["BaseScene"]
    assert "BaseEntry" in listed("tasks", base)
    assert "BaseLoose" in listed("tasks", base)


def test_another_projects_objects_are_not_listed_for_a_single_project() -> None:
    """The point of the exercise: nothing from a Project that was not asked for."""
    base = RunConfig(single_project_name="Base")

    assert "Other" not in listed("projects", base)
    assert "OtherProfile" not in listed("profiles", base)
    assert "OtherEntry" not in listed("tasks", base)
    assert "OtherScene" not in listed("scenes", base)


def test_a_task_no_project_claims_is_kept() -> None:
    """Tasker does not always list a Scene's Task in its Project's <tids>.

    The directory only ever holds names the Map wrote, so an entry that cannot be shown to
    belong to another Project belongs to this one -- dropping it would lose a directory
    entry for a Task that is on the page.
    """
    assert "OrphanSceneTask (Scene)" in listed("tasks", RunConfig(single_project_name="Base"))


# ##################################################################################
# A single Profile
# ##################################################################################
def test_a_single_profile_lists_that_profile_alone() -> None:
    """One Profile was asked for, so one Profile is listed -- and no Project at all.

    output_directory leaves the Projects section out entirely for a single Profile, and
    check_project says the same thing entry by entry so that the two cannot disagree.
    """
    base_profile = RunConfig(single_profile_name="BaseProfile")

    assert listed("profiles", base_profile) == ["BaseProfile"]
    assert listed("projects", base_profile) == []


def test_a_single_profile_keeps_to_its_own_projects_tasks_and_scenes() -> None:
    """Its Project's, because those are what the Map displays along with it."""
    base_profile = RunConfig(single_profile_name="BaseProfile")

    assert listed("scenes", base_profile) == ["BaseScene"]
    assert "OtherEntry" not in listed("tasks", base_profile)


# ##################################################################################
# A single Task
# ##################################################################################
def test_a_single_task_lists_that_task_alone() -> None:
    """The Task is the whole of what was asked for."""
    base_entry = RunConfig(single_task_name="BaseEntry")

    assert listed("tasks", base_entry) == ["BaseEntry"]
    assert listed("projects", base_entry) == []
    assert listed("profiles", base_entry) == []


def test_a_single_task_keeps_to_the_scenes_of_its_own_project() -> None:
    """A Scene belonging to a Project that was not asked for is not in the directory."""
    assert listed("scenes", RunConfig(single_task_name="BaseEntry")) == ["BaseScene"]


def test_an_unnamed_task_is_still_let_through() -> None:
    """The name an unnamed Task is listed under is one MapTasker made up from its first
    action, so it cannot be matched against what the user asked for."""
    unnamed = [["Task_37_(Unnamed)", "Task 37 (Unnamed)"]]
    config = RunConfig(single_task_name="BaseEntry")

    assert [item[1] for item in unnamed if check_item("tasks", item, config)] == ["Task 37 (Unnamed)"]


# ##################################################################################
# A single Scene
# ##################################################################################
def test_a_single_scene_lists_that_scene_and_the_project_that_owns_it() -> None:
    """Only the owning Project is displayed, so only it gets a link."""
    base_scene = RunConfig(single_scene_name="BaseScene")

    assert listed("scenes", base_scene) == ["BaseScene"]
    assert listed("projects", base_scene) == ["Base"]
    assert listed("profiles", base_scene) == []


def test_a_single_scene_keeps_to_the_tasks_of_its_own_project() -> None:
    """Which are the Scene's own Tasks, since that is all the run displayed."""
    assert "OtherEntry" not in listed("tasks", RunConfig(single_scene_name="BaseScene"))
