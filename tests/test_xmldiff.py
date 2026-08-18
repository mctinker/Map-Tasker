"""MapTasker XML Comparison Unit Tests

xmldiff.py is a pure function over two Configuration records, so these tests build both
sides from XML text rather than loading two backups or standing up the GUI.  Nothing
here touches PrimeItems, which is the point of the module under test: a comparison needs
two configurations in memory at once, and the global can only hold one.

The two fixtures (_OLDER_XML and _NEWER_XML) are the same configuration before and after
an editing session that makes one instance of every change the report can describe, with
untouched objects sitting alongside each one.  Both halves matter: every test asserts
that a change is reported AND that the untouched neighbour is not, which is what stops a
comparison that simply reports everything from passing.

The fixtures are two separate literals rather than one literal and a mutation of it.  A
mutation helper would mean the tests exercise the helper as much as the comparison; two
literals mean an accidental divergence shows up as a spurious finding, which the silence
assertions catch.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime

import pytest
from maptasker.src import taskerd
from maptasker.src.xmldiff import (
    ADDED,
    CHANGED,
    REMOVED,
    RENAMED,
    Configuration,
    compare,
)

# ##################################################################################
# The fixtures.
#
#   Project 'Home' (1)     keeps its Profiles but swaps one, gains a Task, and one of
#                          its own Project variables gains a value.
#   Project 'Away' (2)     renamed to 'Travel', nothing else touched -> PROJECT-RENAMED.
#   Project 'Gone' (3)     older only -> PROJECT-REMOVED.
#   Project 'Fresh' (4)    newer only -> PROJECT-ADDED.
#   Project 'Steady' (5)   byte-identical both sides -> reported nowhere.
#
#   Profile 10 'Wake'      identical -> silent.
#   Profile 11 'Evening'   renamed only -> PROFILE-RENAMED.
#   Profile 12 'Doorbell'  older only -> PROFILE-REMOVED.
#   Profile 13 'Car'       newer only -> PROFILE-ADDED.
#   Profile 14 'Toggle'    <limit> false -> true, i.e. disabled in Tasker.
#   Profile 15 'Swap'      entry Task 20 -> 21.
#   Profile 16 'Cond'      its Event condition edited in place.
#   Profile 17 'AddCond'   gains a State condition it did not have.
#
#   Task 20 'Runner'       identical -> silent.
#   Task 21 'Helper'       renamed only -> TASK-RENAMED.
#   Task 22 'Dead'         older only -> TASK-REMOVED.
#   Task 23 'Wake Up'      one action inserted, one argument edited, one removed.
#   Task 24 'Newcomer'     newer only -> TASK-ADDED.
#   Task 25 'Recode'       its one action's CODE changes, Flash -> Notify.
#   Task 26 'Relabel'      its one action's label changes, nothing else.
#
#   Scene 'Menu'           one element moved, one removed, one added, one's TAP Task
#                          repointed.
#   Scene 'Steady Scene'   identical -> silent.
#   Scene 'Old Scene'      older only -> SCENE-REMOVED.
#   Scene 'New Scene'      newer only -> SCENE-ADDED.
#
#   %keep unchanged, %edit changed, %gone removed, %fresh added.
#   Setting 'volume' changed.
# ##################################################################################
_OLDER_XML = """<TaskerData sr="" dvi="1" tv="6.5.6">
  <Project sr="proj0" ve="2">
    <cdate>1</cdate><mdate>2</mdate>
    <id>1</id><name>Home</name>
    <pids>10,11,12,14,15,16,17</pids>
    <tids>20,21,22,23,25,26</tids>
    <scenes>Menu,Steady Scene,Old Scene</scenes>
    <ProfileVariable sr="pv0"><pvn>%greeting</pvn><pvv></pvv><pvdn>Greeting</pvdn></ProfileVariable>
  </Project>
  <Project sr="proj1" ve="2">
    <cdate>1</cdate><id>2</id><name>Away</name><pids></pids><tids></tids>
  </Project>
  <Project sr="proj2" ve="2">
    <cdate>1</cdate><id>3</id><name>Gone</name><pids></pids><tids></tids>
  </Project>
  <Project sr="proj3" ve="2">
    <cdate>1</cdate><id>5</id><name>Steady</name><pids></pids><tids></tids>
  </Project>

  <Profile sr="prof10" ve="2"><cdate>1</cdate><id>10</id><nme>Wake</nme><mid0>20</mid0>
    <Time sr="if0"><fh>7</fh></Time></Profile>
  <Profile sr="prof11" ve="2"><cdate>1</cdate><id>11</id><nme>Evening</nme><mid0>21</mid0>
    <Time sr="if0"><fh>19</fh></Time></Profile>
  <Profile sr="prof12" ve="2"><cdate>1</cdate><id>12</id><nme>Doorbell</nme><mid0>22</mid0>
    <Event sr="if0"><code>2</code></Event></Profile>
  <Profile sr="prof14" ve="2"><cdate>1</cdate><id>14</id><nme>Toggle</nme><limit>false</limit>
    <mid0>20</mid0><Event sr="if0"><code>7</code></Event></Profile>
  <Profile sr="prof15" ve="2"><cdate>1</cdate><id>15</id><nme>Swap</nme><mid0>20</mid0>
    <Event sr="if0"><code>8</code></Event></Profile>
  <Profile sr="prof16" ve="2"><cdate>1</cdate><id>16</id><nme>Cond</nme><mid0>20</mid0>
    <Event sr="if0"><code>9</code><Str sr="arg0" ve="3">Original</Str></Event></Profile>
  <Profile sr="prof17" ve="2"><cdate>1</cdate><id>17</id><nme>AddCond</nme><mid0>20</mid0>
    <Event sr="if0"><code>10</code></Event></Profile>

  <Task sr="task20" ve="2"><cdate>1</cdate><id>20</id><nme>Runner</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">Running</Str></Action></Task>
  <Task sr="task21" ve="2"><cdate>1</cdate><id>21</id><nme>Helper</nme>
    <Action sr="act0" ve="7"><code>30</code><Int sr="arg1" val="5"/></Action></Task>
  <Task sr="task22" ve="2"><cdate>1</cdate><id>22</id><nme>Dead</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">Nobody</Str></Action></Task>
  <Task sr="task23" ve="2"><cdate>1</cdate><id>23</id><nme>Wake Up</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">Morning</Str></Action>
    <Action sr="act1" ve="7"><code>548</code><Str sr="arg0" ve="3">Awake</Str></Action>
    <Action sr="act2" ve="7"><code>30</code><Int sr="arg1" val="5"/></Action>
    <Action sr="act3" ve="7"><code>130</code><Str sr="arg0" ve="3">Helper</Str></Action></Task>
  <Task sr="task25" ve="2"><cdate>1</cdate><id>25</id><nme>Recode</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">Same text</Str></Action></Task>
  <Task sr="task26" ve="2"><cdate>1</cdate><id>26</id><nme>Relabel</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">Hi</Str><label>Before</label></Action></Task>

  <Scene sr="sceneMenu" ve="2"><cdate>1</cdate><nme>Menu</nme>
    <widthPort>400</widthPort><heightPort>600</heightPort>
    <TextElement sr="elements0" ve="3"><Str sr="arg0" ve="3">Ok</Str><geom>10,10,100,50,0,0,0,0</geom></TextElement>
    <TextElement sr="elements1" ve="3"><Str sr="arg0" ve="3">Cancel</Str><geom>10,80,100,50,0,0,0,0</geom></TextElement>
    <ButtonElement sr="elements2" ve="3"><Str sr="arg0" ve="3">Go</Str><geom>10,150,100,50,0,0,0,0</geom>
      <clickTask>20</clickTask></ButtonElement></Scene>
  <Scene sr="sceneSteady" ve="2"><cdate>1</cdate><nme>Steady Scene</nme>
    <widthPort>200</widthPort>
    <TextElement sr="elements0" ve="3"><Str sr="arg0" ve="3">Fixed</Str>
      <geom>1,1,1,1,0,0,0,0</geom></TextElement></Scene>
  <Scene sr="sceneOld" ve="2"><cdate>1</cdate><nme>Old Scene</nme>
    <TextElement sr="elements0" ve="3"><Str sr="arg0" ve="3">Bye</Str><geom>0,0,1,1,0,0,0,0</geom></TextElement></Scene>

  <Variable sr="vars0"><n>%keep</n><v>steady</v></Variable>
  <Variable sr="vars1"><n>%edit</n><v>before</v></Variable>
  <Variable sr="vars2"><n>%gone</n><v>vanishing</v></Variable>
  <Setting sr="prefs0"><n>volume</n><t>i</t><v>3</v></Setting>
  <Setting sr="prefs1"><n>theme</n><t>s</t><v>dark</v></Setting>
</TaskerData>
"""

_NEWER_XML = """<TaskerData sr="" dvi="1" tv="6.5.6">
  <Project sr="proj0" ve="2">
    <cdate>1</cdate><mdate>999</mdate>
    <id>1</id><name>Home</name>
    <pids>10,11,13,14,15,16,17</pids>
    <tids>20,21,23,24,25,26</tids>
    <scenes>Menu,Steady Scene,New Scene</scenes>
    <ProfileVariable sr="pv0"><pvn>%greeting</pvn><pvv>Hello</pvv><pvdn>Greeting</pvdn></ProfileVariable>
  </Project>
  <Project sr="proj1" ve="2">
    <cdate>1</cdate><id>2</id><name>Travel</name><pids></pids><tids></tids>
  </Project>
  <Project sr="proj2" ve="2">
    <cdate>1</cdate><id>4</id><name>Fresh</name><pids></pids><tids></tids>
  </Project>
  <Project sr="proj3" ve="2">
    <cdate>1</cdate><id>5</id><name>Steady</name><pids></pids><tids></tids>
  </Project>

  <Profile sr="prof10" ve="2"><cdate>1</cdate><id>10</id><nme>Wake</nme><mid0>20</mid0>
    <Time sr="if0"><fh>7</fh></Time></Profile>
  <Profile sr="prof11" ve="2"><cdate>1</cdate><id>11</id><nme>Evening Wind-down</nme><mid0>21</mid0>
    <Time sr="if0"><fh>19</fh></Time></Profile>
  <Profile sr="prof13" ve="2"><cdate>1</cdate><id>13</id><nme>Car</nme><mid0>24</mid0>
    <State sr="if0"><code>3</code></State></Profile>
  <Profile sr="prof14" ve="2"><cdate>1</cdate><id>14</id><nme>Toggle</nme><limit>true</limit>
    <mid0>20</mid0><Event sr="if0"><code>7</code></Event></Profile>
  <Profile sr="prof15" ve="2"><cdate>1</cdate><id>15</id><nme>Swap</nme><mid0>21</mid0>
    <Event sr="if0"><code>8</code></Event></Profile>
  <Profile sr="prof16" ve="2"><cdate>1</cdate><id>16</id><nme>Cond</nme><mid0>20</mid0>
    <Event sr="if0"><code>9</code><Str sr="arg0" ve="3">Edited</Str></Event></Profile>
  <Profile sr="prof17" ve="2"><cdate>1</cdate><id>17</id><nme>AddCond</nme><mid0>20</mid0>
    <Event sr="if0"><code>10</code></Event><State sr="if1"><code>11</code></State></Profile>

  <Task sr="task20" ve="2"><cdate>1</cdate><id>20</id><nme>Runner</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">Running</Str></Action></Task>
  <Task sr="task21" ve="2"><cdate>1</cdate><id>21</id><nme>Helper Renamed</nme>
    <Action sr="act0" ve="7"><code>30</code><Int sr="arg1" val="5"/></Action></Task>
  <Task sr="task23" ve="2"><cdate>1</cdate><id>23</id><nme>Wake Up</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">Morning</Str></Action>
    <Action sr="act1" ve="7"><code>559</code><Str sr="arg0" ve="3">Good morning</Str></Action>
    <Action sr="act2" ve="7"><code>548</code><Str sr="arg0" ve="3">Up and about</Str></Action>
    <Action sr="act3" ve="7"><code>30</code><Int sr="arg1" val="5"/></Action></Task>
  <Task sr="task24" ve="2"><cdate>1</cdate><id>24</id><nme>Newcomer</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">Brand new</Str></Action></Task>
  <Task sr="task25" ve="2"><cdate>1</cdate><id>25</id><nme>Recode</nme>
    <Action sr="act0" ve="7"><code>523</code><Str sr="arg0" ve="3">Same text</Str></Action></Task>
  <Task sr="task26" ve="2"><cdate>1</cdate><id>26</id><nme>Relabel</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">Hi</Str><label>After</label></Action></Task>

  <Scene sr="sceneMenu" ve="2"><cdate>1</cdate><nme>Menu</nme>
    <widthPort>480</widthPort><heightPort>600</heightPort>
    <TextElement sr="elements0" ve="3"><Str sr="arg0" ve="3">Ok</Str><geom>25,10,100,50,0,0,0,0</geom></TextElement>
    <TextElement sr="elements1" ve="3"><Str sr="arg0" ve="3">Retry</Str><geom>10,80,100,50,0,0,0,0</geom></TextElement>
    <ButtonElement sr="elements2" ve="3"><Str sr="arg0" ve="3">Go</Str><geom>10,150,100,50,0,0,0,0</geom>
      <clickTask>21</clickTask></ButtonElement></Scene>
  <Scene sr="sceneSteady" ve="2"><cdate>1</cdate><nme>Steady Scene</nme>
    <widthPort>200</widthPort>
    <TextElement sr="elements0" ve="3"><Str sr="arg0" ve="3">Fixed</Str>
      <geom>1,1,1,1,0,0,0,0</geom></TextElement></Scene>
  <Scene sr="sceneNew" ve="2"><cdate>1</cdate><nme>New Scene</nme>
    <TextElement sr="elements0" ve="3"><Str sr="arg0" ve="3">Hi</Str><geom>0,0,1,1,0,0,0,0</geom></TextElement></Scene>

  <Variable sr="vars0"><n>%keep</n><v>steady</v></Variable>
  <Variable sr="vars1"><n>%edit</n><v>after</v></Variable>
  <Variable sr="vars2"><n>%fresh</n><v>arrived</v></Variable>
  <Setting sr="prefs0"><n>volume</n><t>i</t><v>7</v></Setting>
  <Setting sr="prefs1"><n>theme</n><t>s</t><v>dark</v></Setting>
</TaskerData>
"""


def _configuration(xml_text: str, path: str) -> Configuration:
    """Build a Configuration from XML text, the way taskerd builds one from a file.

    Mirrors taskerd.get_the_xml_data's table construction but skips its derived-name
    passes (naming an unnamed Profile from its conditions, an unnamed Task from its first
    action).  Those reach into PrimeItems and need a fully initialised program_arguments;
    every object in these fixtures is named, so there is nothing for them to do anyway.
    """
    root = ET.fromstring(xml_text)  # noqa: S314  (fixture text, defined in this file)
    tables = {
        "all_projects": taskerd.move_xml_to_table(root.findall("Project"), False, "name"),
        "all_profiles": taskerd.move_xml_to_table(root.findall("Profile"), True, "nme"),
        "all_tasks": taskerd.move_xml_to_table(root.findall("Task"), True, "nme"),
        "all_scenes": taskerd.move_xml_to_table(root.findall("Scene"), False, "nme"),
        "all_services": [],
    }
    tables["all_profiles_by_name"] = {
        profile["name"]: {"xml": profile["xml"], "id": key} for key, profile in tables["all_profiles"].items()
    }
    tables["all_tasks_by_name"] = {
        task["name"]: {"xml": task["xml"], "id": key} for key, task in tables["all_tasks"].items() if task["name"]
    }
    return Configuration(path=path, tables=tables, root=root, when=datetime(2026, 8, 18, 9, 0, 0))  # noqa: DTZ001


def _entries_for(report: str, tag: str) -> list[str]:
    """The '[TAG]  where' lines of one tag, which is what the assertions match against."""
    return [line for line in report.splitlines() if line.startswith(f"[{tag}]")]


def _block_at(report: str, anchor: str) -> str:
    """One entry in full -- its '[TAG] where' line and the detail lines under it.

    Entries are separated by a blank line, so a block runs from the anchor to the first
    one.  Assertions about detail text need this rather than a plain 'in report': a
    neighbouring entry's detail would satisfy that just as happily.
    """
    return report[report.index(anchor) :].split("\n\n", maxsplit=1)[0]


def _section(report: str, heading: str) -> str:
    """One whole section of the report, from its heading to the next blank-line-separated one."""
    start = report.index(heading)
    remainder = report[start:]
    for later in ("ADDED -- ", "REMOVED -- ", "RENAMED -- ", "CHANGED\n", "WHAT THIS COMPARISON"):
        position = remainder.find(f"\n{later}", 1)
        if position > 0:
            remainder = remainder[:position]
    return remainder


@pytest.fixture
def report() -> str:
    """The comparison report for the two fixtures."""
    text, _ = compare(_configuration(_OLDER_XML, "older.xml"), _configuration(_NEWER_XML, "newer.xml"))
    return text


@pytest.fixture
def counts() -> dict:
    """The change counts for the two fixtures."""
    _, totals = compare(_configuration(_OLDER_XML, "older.xml"), _configuration(_NEWER_XML, "newer.xml"))
    return totals


# ##################################################################################
# The header, and the two cases with no changes in them at all.
# ##################################################################################
def test_header_names_both_files_and_their_totals(report: str) -> None:
    """The header says which file is which and how big each is."""
    assert "Older file:  older.xml" in report
    assert "Newer file:  newer.xml" in report
    assert "Older:       4 Projects, 7 Profiles, 6 Tasks, 3 Scenes" in report
    assert "Newer:       4 Projects, 7 Profiles, 6 Tasks, 3 Scenes" in report


def test_identical_configurations_report_nothing() -> None:
    """Comparing a file with itself says so, rather than producing an empty-looking report."""
    text, totals = compare(_configuration(_OLDER_XML, "a.xml"), _configuration(_OLDER_XML, "b.xml"))
    assert "hold the same configuration -- nothing differs" in text
    assert totals == {ADDED: 0, REMOVED: 0, RENAMED: 0, CHANGED: 0}


def test_timestamps_alone_are_never_a_change() -> None:
    """A re-save that only rewrites <cdate>/<mdate>/<edate> is not a change.

    The single most important thing this module gets right: Tasker rewrites these on
    every save, so counting them would report every object in the file as changed and
    make the whole feature useless.
    """
    restamped = _OLDER_XML.replace("<cdate>1</cdate>", "<cdate>424242</cdate>").replace(
        "<mdate>2</mdate>", "<mdate>424242</mdate>",
    )
    _, totals = compare(_configuration(_OLDER_XML, "a.xml"), _configuration(restamped, "b.xml"))
    assert totals == {ADDED: 0, REMOVED: 0, RENAMED: 0, CHANGED: 0}


def test_untouched_objects_are_reported_nowhere(report: str) -> None:
    """Every object the editing session did not touch stays out of the report entirely.

    The half of the fixture that catches a comparison reporting everything.  'Steady'
    and its neighbours differ in no way between the two files and must appear in no
    section -- not as added, not as removed, not as changed.
    """
    for untouched in ("Project 'Steady'", "Profile 'Wake'", "Task 'Runner'", "Scene 'Steady Scene'"):
        assert untouched not in report, f"{untouched} was not edited but appears in the report"
    assert "%keep" not in report
    assert "Setting theme" not in report


# ##################################################################################
# Projects.
# ##################################################################################
def test_added_and_removed_projects(report: str) -> None:
    """A Project present on only one side lands in that side's section."""
    assert _entries_for(report, "PROJECT-ADDED") == ["[PROJECT-ADDED]  Project 'Fresh'"]
    assert _entries_for(report, "PROJECT-REMOVED") == ["[PROJECT-REMOVED]  Project 'Gone'"]


def test_renamed_project_is_a_rename_not_a_delete_and_an_add(report: str) -> None:
    """'Away' -> 'Travel' is one rename, not one removal plus one addition.

    The reason Projects are matched by <id> rather than by the name all_projects is keyed
    by.  A name match would put 'Away' under REMOVED and 'Travel' under ADDED, which is
    the one answer a user comparing two backups least wants.
    """
    assert _entries_for(report, "PROJECT-RENAMED") == ["[PROJECT-RENAMED]  Project 'Travel'"]
    assert "'Away' -> 'Travel'" in _block_at(report, "[PROJECT-RENAMED]  Project 'Travel'")
    assert "Away" not in _section(report, "REMOVED -- ")
    assert "Travel" not in _section(report, "ADDED -- ")


def test_project_membership_changes_are_named_not_numbered(report: str) -> None:
    """A Project's gained and lost Profiles/Tasks/Scenes are listed by name."""
    block = _block_at(report, "[PROJECT-CHANGED]  Project 'Home'")
    assert "Profiles added:   'Car'" in block
    assert "Profiles removed: 'Doorbell'" in block
    assert "Tasks added:   'Newcomer'" in block
    assert "Tasks removed: 'Dead'" in block
    assert "Scenes added:   'New Scene'" in block
    assert "Scenes removed: 'Old Scene'" in block


def test_project_variable_change_is_spelled_out(report: str) -> None:
    """A Project variable gaining a value says which variable and what value.

    Named explicitly rather than swept into 'other properties changed', which is what it
    did when the module was first run against two real backups.
    """
    block = _block_at(report, "[PROJECT-CHANGED]  Project 'Home'")
    assert "Project variable %greeting: '' -> 'Hello'" in block


def test_reordered_membership_is_not_a_change() -> None:
    """<pids> compared as a set: Tasker reorders it freely and the order means nothing."""
    shuffled = _OLDER_XML.replace(
        "<pids>10,11,12,14,15,16,17</pids>", "<pids>17,16,15,14,12,11,10</pids>",
    )
    _, totals = compare(_configuration(_OLDER_XML, "a.xml"), _configuration(shuffled, "b.xml"))
    assert totals[CHANGED] == 0


# ##################################################################################
# Profiles.
# ##################################################################################
def test_added_and_removed_profiles_say_what_they_were(report: str) -> None:
    """An added or removed Profile carries its conditions and entry Task, so the entry
    means something without cross-referencing the file it came from."""
    added = _block_at(report, "[PROFILE-ADDED]")
    assert "Profile 'Car' (id 13)" in added
    assert "Conditions: State." in added
    assert "Entry Task: 'Newcomer'." in added

    removed = _block_at(report, "[PROFILE-REMOVED]")
    assert "Profile 'Doorbell' (id 12)" in removed
    assert "Conditions: Event." in removed


def test_profile_entries_name_their_owning_project(report: str) -> None:
    """A location reads 'Project X > Profile Y', the same convention healthck uses."""
    assert "[PROFILE-ADDED]  Project 'Home' > Profile 'Car' (id 13)" in report


def test_renamed_profile_keeps_its_id_match(report: str) -> None:
    """A renamed Profile is one rename, and does not appear as an add or a remove."""
    assert _entries_for(report, "PROFILE-RENAMED") == [
        "[PROFILE-RENAMED]  Project 'Home' > Profile 'Evening Wind-down' (id 11)",
    ]
    assert "Evening" not in _section(report, "REMOVED -- ")


def test_disabled_profile_is_reported(report: str) -> None:
    """<limit>true</limit> is how Tasker records a disabled Profile, and it matters."""
    block = _block_at(report, "[PROFILE-CHANGED]  Project 'Home' > Profile 'Toggle' (id 14)")
    assert "disabled (was enabled)" in block


def test_changed_entry_task_names_both_tasks(report: str) -> None:
    """An entry Task change resolves both ids to names -- one per side, since the name
    for an id can differ between the two files."""
    block = _block_at(report, "[PROFILE-CHANGED]  Project 'Home' > Profile 'Swap' (id 15)")
    assert "entry Task: 'Runner' -> 'Helper Renamed'" in block


def test_condition_changes_are_reported_by_type(report: str) -> None:
    """An edited condition and an added one read differently, and both are reported."""
    edited = _block_at(report, "[PROFILE-CHANGED]  Project 'Home' > Profile 'Cond' (id 16)")
    assert "Event condition edited." in edited

    gained = _block_at(report, "[PROFILE-CHANGED]  Project 'Home' > Profile 'AddCond' (id 17)")
    assert "State condition added (1)." in gained
    assert "Event" not in gained.split("State condition added", 1)[1]


# ##################################################################################
# Tasks and their action lists.
# ##################################################################################
def test_added_and_removed_tasks_carry_an_action_count(report: str) -> None:
    """An added or removed Task says how big it was."""
    assert "[TASK-ADDED]  Project 'Home' > Task 'Newcomer' (id 24)" in report
    assert "1 actions." in _block_at(report, "[TASK-ADDED]")
    assert "[TASK-REMOVED]  Project 'Home' > Task 'Dead' (id 22)" in report


def test_inserted_action_does_not_renumber_everything_below_it(report: str) -> None:
    """The whole reason the action lists are matched with difflib rather than by sr="actN".

    Task 'Wake Up' gains a Say at position 2 and loses its trailing Perform Task, and one
    Flash's text is edited.  Position matching would report all four actions as changed;
    the sequence match reports the one insertion, the one edit and the one removal.
    """
    block = _block_at(report, "[TASK-CHANGED]  Project 'Home' > Task 'Wake Up' (id 23)")
    assert "+ inserted at 2:  2. Say" in block
    assert "- removed from 4:  4. Perform Task" in block
    assert "Text: 'Awake' -> 'Up and about'" in block
    # The unedited Flash at position 1 and the Wait are untouched and must not be listed.
    assert "'Morning'" not in block


def test_action_argument_change_names_the_argument(report: str) -> None:
    """An edited argument is named ('Text'), not numbered ('arg0').

    Read from actionc.action_codes, which is a static table -- the richer renderer in
    actione.py needs a live program_arguments and would make this module untestable.
    """
    block = _block_at(report, "[TASK-CHANGED]  Project 'Home' > Task 'Wake Up' (id 23)")
    assert "Text: 'Awake' -> 'Up and about'" in block
    assert "arg0:" not in block


def test_changed_action_code_stops_at_the_code(report: str) -> None:
    """Flash -> Notify reports the code change and NOT an argument comparison.

    Flash's arg0 is its text and Notify's arg0 is its title: the same argument id means
    something different either side, so comparing the two values would report a change
    of meaning as a change of value.  The fixture keeps arg0 identical precisely so that
    a wrongly-reported argument change would be visible here.
    """
    block = _block_at(report, "[TASK-CHANGED]  Project 'Home' > Task 'Recode' (id 25)")
    assert "Flash  ->  Notify" in block
    assert "Same text" not in block


def test_action_label_change_is_reported(report: str) -> None:
    """An action's label is content, and a change to it is worth a line."""
    block = _block_at(report, "[TASK-CHANGED]  Project 'Home' > Task 'Relabel' (id 26)")
    assert "label: 'Before' -> 'After'" in block


def test_renamed_task_is_a_rename(report: str) -> None:
    """A Task renamed and otherwise untouched goes under RENAMED, not CHANGED."""
    assert _entries_for(report, "TASK-RENAMED") == [
        "[TASK-RENAMED]  Project 'Home' > Task 'Helper Renamed' (id 21)",
    ]


def test_unchanged_action_count_is_reported(report: str) -> None:
    """A changed Task says how much of it stayed put, which is what makes a long entry
    readable at a glance."""
    block = _block_at(report, "[TASK-CHANGED]  Project 'Home' > Task 'Wake Up' (id 23)")
    assert "of 4 actions unchanged." in block


# ##################################################################################
# Scenes.
# ##################################################################################
def test_added_and_removed_scenes(report: str) -> None:
    """A Scene on one side only, with its element count."""
    assert "[SCENE-ADDED]  Project 'Home' > Scene 'New Scene'" in report
    assert "[SCENE-REMOVED]  Project 'Home' > Scene 'Old Scene'" in report


def test_scene_element_changes(report: str) -> None:
    """Elements added, removed, moved, and their Task bindings repointed."""
    block = _block_at(report, "[SCENE-CHANGED]  Project 'Home' > Scene 'Menu'")
    assert "- removed: Text 'Cancel'" in block
    assert "+ added:   Text 'Retry'" in block
    assert "Text 'Ok' moved." in block
    assert "Button 'Go' TAP: 'Runner' -> 'Helper Renamed'." in block


def test_scene_dimension_change_is_reported(report: str) -> None:
    """A resized Scene says so."""
    block = _block_at(report, "[SCENE-CHANGED]  Project 'Home' > Scene 'Menu'")
    assert "portrait width: '400' -> '480'" in block


def test_version_2_scene_change_is_reported_without_detail() -> None:
    """A V2 Scene's layout is one compressed blob, so a change to it is reported as one.

    Honest rather than silent: the report says it changed and says it did not look
    inside, and the closing limitations section explains why.
    """
    older = _OLDER_XML.replace("<nme>Steady Scene</nme>", "<nme>Steady Scene</nme><lj>AAAA</lj>")
    newer = _NEWER_XML.replace("<nme>Steady Scene</nme>", "<nme>Steady Scene</nme><lj>BBBB</lj>")
    text, _ = compare(_configuration(older, "a.xml"), _configuration(newer, "b.xml"))
    assert "Version 2 layout changed (not compared in detail)." in text
    assert "hold a Version 2 layout" in text


# ##################################################################################
# Variables and Settings.
# ##################################################################################
def test_variable_changes(report: str) -> None:
    """Global variables added, removed and edited -- the answer an object-level
    comparison would miss entirely."""
    assert "[VARIABLE-CHANGED]  Variable %edit" in report
    assert "'before'  ->  'after'" in _block_at(report, "[VARIABLE-CHANGED]  Variable %edit")
    assert "[VARIABLE-ADDED]  Variable %fresh" in report
    assert "[VARIABLE-REMOVED]  Variable %gone" in report


def test_setting_change(report: str) -> None:
    """A changed Tasker preference is reported; an unchanged one is not."""
    assert "[SETTING-CHANGED]  Setting volume" in report
    assert "theme" not in report


# ##################################################################################
# The guards: id reuse, capped detail, and the closing limitations.
# ##################################################################################
def test_id_reuse_is_reported_as_a_removal_and_an_addition() -> None:
    """Two files that merely share ids are not treated as two versions of one file.

    An id is unique within a file, not across two.  When an id-matched pair has a
    different name AND nothing in common, calling it one heavily-changed object produces
    nonsense; a removal plus an addition is truer.
    """
    unrelated = """<TaskerData sr="" dvi="1" tv="6.5.6">
      <Task sr="t" ve="2"><id>20</id><nme>Something Else</nme>
        <Action sr="act0" ve="7"><code>523</code><Str sr="arg0" ve="3">Unrelated</Str></Action></Task>
    </TaskerData>
    """
    original = """<TaskerData sr="" dvi="1" tv="6.5.6">
      <Task sr="t" ve="2"><id>20</id><nme>Runner</nme>
        <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">Running</Str></Action></Task>
    </TaskerData>
    """
    text, totals = compare(_configuration(original, "a.xml"), _configuration(unrelated, "b.xml"))
    assert totals[ADDED] == 1
    assert totals[REMOVED] == 1
    assert totals[CHANGED] == 0
    assert "[TASK-ADDED]  Task 'Something Else' (id 20)" in text
    assert "[TASK-REMOVED]  Task 'Runner' (id 20)" in text


def test_a_rewritten_task_keeping_its_name_is_still_a_change() -> None:
    """The id-reuse guard only applies when the name changed too.

    A Task rewritten from scratch under the same name is a change, not a different Task,
    and reporting it as a removal plus an addition would be actively wrong.
    """
    original = """<TaskerData sr="" dvi="1" tv="6.5.6">
      <Task sr="t" ve="2"><id>20</id><nme>Runner</nme>
        <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">Old</Str></Action></Task>
    </TaskerData>
    """
    rewritten = """<TaskerData sr="" dvi="1" tv="6.5.6">
      <Task sr="t" ve="2"><id>20</id><nme>Runner</nme>
        <Action sr="act0" ve="7"><code>523</code><Str sr="arg0" ve="3">Brand new</Str></Action></Task>
    </TaskerData>
    """
    _, totals = compare(_configuration(original, "a.xml"), _configuration(rewritten, "b.xml"))
    assert totals == {ADDED: 0, REMOVED: 0, RENAMED: 0, CHANGED: 1}


def test_many_id_collisions_warn_at_the_top() -> None:
    """Enough collisions and the report says the two files may be unrelated, up front.

    Left to infer it from the entries, a reader would work through a hundred nonsense
    findings before reaching the same conclusion.
    """
    def one_side(prefix: str, code: str) -> str:
        tasks = "".join(
            f'<Task sr="t{index}" ve="2"><id>{index}</id><nme>{prefix}{index}</nme>'
            f'<Action sr="act0" ve="7"><code>{code}</code>'
            f'<Str sr="arg0" ve="3">{prefix}</Str></Action></Task>'
            for index in range(1, 8)
        )
        return f'<TaskerData sr="" dvi="1" tv="6.5.6">{tasks}</TaskerData>'

    text, _ = compare(
        _configuration(one_side("Mine", "548"), "a.xml"),
        _configuration(one_side("Theirs", "523"), "b.xml"),
    )
    assert "WARNING" in text
    assert "7 objects share an id between these two files" in text


def test_detail_lines_are_capped() -> None:
    """One wholly-rewritten Task must not bury every other entry in the report."""
    def one_side(text: str) -> str:
        actions = "".join(
            f'<Action sr="act{index}" ve="7"><code>548</code>'
            f'<Str sr="arg0" ve="3">{text}{index}</Str></Action>'
            for index in range(40)
        )
        return (
            '<TaskerData sr="" dvi="1" tv="6.5.6">'
            f'<Task sr="t" ve="2"><id>20</id><nme>Huge</nme>{actions}</Task>'
            "</TaskerData>"
        )

    text, _ = compare(_configuration(one_side("before"), "a.xml"), _configuration(one_side("after"), "b.xml"))
    block = _block_at(text, "[TASK-CHANGED]  Task 'Huge' (id 20)")
    assert "more differences." in block
    assert len(block.splitlines()) < 20


def test_limitations_are_always_stated(report: str) -> None:
    """The closing section is not optional.

    A renamed Scene genuinely does come out as one removal and one addition -- a Scene
    has no id, so a rename and a replace are indistinguishable in the file.  Unsaid,
    that reads as a bug in the comparison rather than a limit of the format.
    """
    assert "WHAT THIS COMPARISON CANNOT SEE" in report
    assert "A renamed Scene appears above as one removed Scene and one added Scene." in report
    assert "Creation and modification dates are ignored throughout." in report


def test_counts_match_the_entries(report: str, counts: dict) -> None:
    """The header's counts are the number of entries the report actually holds.

    A count that drifts from the body is worse than no count: it is the one line most
    likely to be read on its own.
    """
    for kind, prefix in ((ADDED, "-ADDED"), (REMOVED, "-REMOVED"), (RENAMED, "-RENAMED"), (CHANGED, "-CHANGED")):
        entries = [line for line in report.splitlines() if line.startswith("[") and prefix in line.split("]")[0]]
        assert len(entries) == counts[kind], f"{kind}: header says {counts[kind]}, body has {len(entries)}"
