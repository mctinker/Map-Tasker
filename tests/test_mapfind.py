"""MapTasker faceted-search (mapfind) Unit Tests

mapfind reads the same lookup tables taskerd builds and nothing else, so these tests
build those tables from a small XML fixture rather than loading a backup or standing up
the GUI -- the same arrangement test_healthck.py uses, and for the same reason.

The fixture carries one object per facet and, alongside each, an object the facet must
NOT return.  Both halves matter: a search that answers with everything passes every
"does it find X" test ever written, and fails the only question a user actually has.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET

import pytest
from maptasker.src import mapfind, taskerd
from maptasker.src.mapjump import PROFILE, PROJECT, SCENE, TASK
from maptasker.src.primitem import PrimeItems

# Two Projects, and one object per facet with a near neighbour that must stay out of the
# answer.
#
#   Project 'Home'      Profiles 10,11,12; Tasks 20,21,22,23; Scene 'Menu'
#   Project 'Away'      Profile 13, Task 24 -- the "narrow to Project" control group
#   Profile 10 'Timed'  a Time context, entry Task 20 -> the trigger+action pair
#   Profile 11 'Watch'  State 160 (Wifi Connected), entry Task 21
#   Profile 12 'AppBar' an App context naming Spotify -> the app facet's Profile half
#   Profile 13 'Away P' a Time context in the other Project, entry Task 24
#   Task 20 'Fetcher'   HTTP Request (339) at act1, Perform Task (130) at act0.  Written
#                       act0, act10, act2 out of order so the action NUMBERS the results
#                       report have to come out in Map order, not document order.
#   Task 21 'Opener'    Launch App (20) naming Spotify -> the app facet's Task half
#   Task 22 'Shower'    Show Scene (47) naming 'Menu', and Destroy Scene (49) naming a
#                       Scene through a %variable -- the reference that cannot be resolved
#   Task 23 'Quiet'     one Flash (548); matches no facet but the free text 'quietly'
#   Task 24 'Far'       an HTTP Request, in Project 'Away'
#   Scene 'Menu'        listed by Project 'Home'
_FIXTURE_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2">
    <name>Home</name>
    <pids>10,11,12</pids>
    <tids>20,21,22,23</tids>
    <scenes>Menu</scenes>
  </Project>
  <Project sr="proj1" ve="2">
    <name>Away</name>
    <pids>13</pids>
    <tids>24</tids>
  </Project>
  <Profile sr="prof10" ve="2">
    <id>10</id>
    <nme>Timed</nme>
    <mid0>20</mid0>
    <Time sr="con0"><fh>7</fh><fm>0</fm><th>8</th><tm>0</tm></Time>
  </Profile>
  <Profile sr="prof11" ve="2">
    <id>11</id>
    <nme>Watch</nme>
    <mid0>21</mid0>
    <State sr="con0" ve="2"><code>160</code></State>
  </Profile>
  <Profile sr="prof12" ve="2">
    <id>12</id>
    <nme>AppBar</nme>
    <mid0>23</mid0>
    <App sr="con0" ve="2">
      <label0>Spotify</label0>
      <pkg0>com.spotify.music</pkg0>
    </App>
  </Profile>
  <Profile sr="prof13" ve="2">
    <id>13</id>
    <nme>Away P</nme>
    <mid0>24</mid0>
    <Time sr="con0"><fh>9</fh><fm>0</fm><th>10</th><tm>0</tm></Time>
  </Profile>
  <Task sr="task20" ve="2">
    <id>20</id>
    <nme>Fetcher</nme>
    <Action sr="act0" ve="7">
      <code>130</code>
      <Str sr="arg0" ve="3">Opener</Str>
    </Action>
    <Action sr="act10" ve="7">
      <code>548</code>
      <Str sr="arg0" ve="3">tenth</Str>
    </Action>
    <Action sr="act1" ve="7">
      <code>339</code>
      <Str sr="arg2" ve="3">https://example.com/feed</Str>
    </Action>
    <Action sr="act2" ve="7">
      <code>548</code>
      <Str sr="arg0" ve="3">done</Str>
    </Action>
  </Task>
  <Task sr="task21" ve="2">
    <id>21</id>
    <nme>Opener</nme>
    <Action sr="act0" ve="7">
      <code>20</code>
      <App sr="arg0"><appPkg>com.spotify.music</appPkg><label>Spotify</label></App>
    </Action>
  </Task>
  <Task sr="task22" ve="2">
    <id>22</id>
    <nme>Shower</nme>
    <Action sr="act0" ve="7">
      <code>47</code>
      <Str sr="arg0" ve="3">Menu</Str>
    </Action>
    <Action sr="act1" ve="7">
      <code>49</code>
      <Str sr="arg0" ve="3">%WhichScene</Str>
    </Action>
  </Task>
  <Task sr="task23" ve="2">
    <id>23</id>
    <nme>Quiet</nme>
    <Action sr="act0" ve="7">
      <code>548</code>
      <Str sr="arg0" ve="3">said quietly</Str>
    </Action>
  </Task>
  <Task sr="task24" ve="2">
    <id>24</id>
    <nme>Far</nme>
    <Action sr="act0" ve="7">
      <code>339</code>
      <Str sr="arg2" ve="3">https://example.com/other</Str>
    </Action>
  </Task>
  <Scene sr="scene0" ve="2">
    <nme>Menu</nme>
  </Scene>
</TaskerData>"""


def _load(xml_text: str) -> None:
    """Build the PrimeItems lookup tables from XML text, the way taskerd does from a file."""
    root = ET.fromstring(xml_text)  # noqa: S314  (fixture text, defined in this file)
    PrimeItems.file_to_get = "fixture.xml"
    PrimeItems.xml_root = root
    PrimeItems.program_arguments = {"task_action_warning_limit": 100, "language": "English"}
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
    PrimeItems.tasker_root_elements = tables


@pytest.fixture
def index() -> mapfind.FindIndex:
    """The search index for the fixture."""
    _load(_FIXTURE_XML)
    return mapfind.build_index()


def _named(hits: list[mapfind.Hit]) -> set[tuple[str, str]]:
    """The (kind, name) of everything a query answered with -- what the assertions compare."""
    return {(hit.target.kind, hit.target.name) for hit in hits}


# ##################################################################################
# The facet catalogs: what the pulldowns offer.
# ##################################################################################
def test_catalogs_hold_only_what_the_file_uses(index: mapfind.FindIndex) -> None:
    """A pulldown offers the file's own actions and triggers, not Tasker's whole table."""
    actions = {choice.value: choice.count for choice in index.choices(mapfind.ACTION)}
    assert actions["HTTP Request"] == 2  # Task 'Fetcher' and Task 'Far'
    assert actions["Perform Task"] == 1
    assert actions["Flash"] == 3
    # Tasker has ~900 actions; the file uses five.
    assert set(actions) == {"HTTP Request", "Perform Task", "Flash", "Launch App", "Show Scene", "Destroy Scene"}

    triggers = {choice.value: choice.count for choice in index.choices(mapfind.TRIGGER)}
    assert triggers == {"Time": 2, "State: Wifi Connected": 1, "Application": 1}

    assert {choice.value for choice in index.choices(mapfind.APP)} == {"Spotify"}
    assert {choice.value for choice in index.choices(mapfind.SCENE_FACET)} == {"Menu"}


def test_catalog_is_ordered_commonest_first(index: mapfind.FindIndex) -> None:
    """The list opens on what the file uses most, which is what a search usually wants."""
    counts = [choice.count for choice in index.choices(mapfind.ACTION)]
    assert counts == sorted(counts, reverse=True)


def test_unresolvable_references_are_counted_not_guessed(index: mapfind.FindIndex) -> None:
    """A Scene named through a %variable is counted, not indexed as a Scene called '%WhichScene'."""
    assert index.variable_scenes == 1
    assert "%WhichScene" not in {choice.value for choice in index.choices(mapfind.SCENE_FACET)}


# ##################################################################################
# One facet at a time.
# ##################################################################################
def test_action_facet_answers_with_tasks(index: mapfind.FindIndex) -> None:
    """'Which Tasks perform an HTTP Request' -- and no Profile riding along with them."""
    hits, total = mapfind.run_query(index, mapfind.Query(action="HTTP Request"))
    assert total == 2
    assert _named(hits) == {(TASK, "Fetcher"), (TASK, "Far")}


def test_action_hit_points_at_the_action_in_map_order(index: mapfind.FindIndex) -> None:
    """The jump lands on the action, numbered the way the Map numbers it.

    Task 'Fetcher' is written act0, act10, act1, act2.  The Map sorts those numerically
    before printing, so the HTTP Request at act1 is action 2 on screen -- not the third
    element in the file, and not action 10's neighbour.
    """
    hits, _ = mapfind.run_query(index, mapfind.Query(action="HTTP Request", project="Home"))
    (hit,) = hits
    assert hit.target.action == 2
    assert "action 2" in hit.detail


def test_trigger_facet_answers_with_profiles_only(index: mapfind.FindIndex) -> None:
    """A Task has no trigger, so naming one takes every Task out of the answer."""
    hits, _ = mapfind.run_query(index, mapfind.Query(trigger="State: Wifi Connected"))
    assert _named(hits) == {(PROFILE, "Watch")}


def test_app_facet_answers_with_everything_that_names_it(index: mapfind.FindIndex) -> None:
    """'Everything referencing Spotify' is both halves: the Profile waiting on it and the
    Task launching it."""
    hits, _ = mapfind.run_query(index, mapfind.Query(app="Spotify"))
    assert _named(hits) == {(PROFILE, "AppBar"), (TASK, "Opener")}


def test_scene_facet_answers_with_the_scene_its_users_and_its_owner(index: mapfind.FindIndex) -> None:
    """A Scene search returns the Scene, the Task that shows it and the Project listing it."""
    hits, _ = mapfind.run_query(index, mapfind.Query(scene="Menu"))
    assert _named(hits) == {(SCENE, "Menu"), (TASK, "Shower"), (PROJECT, "Home")}


def test_text_facet_reaches_argument_text(index: mapfind.FindIndex) -> None:
    """The free-text facet searches what an action holds, not just what it is called."""
    hits, _ = mapfind.run_query(index, mapfind.Query(text="quietly"))
    assert _named(hits) == {(TASK, "Quiet")}


# ##################################################################################
# Facets in combination -- the whole reason for the feature.
# ##################################################################################
def test_trigger_and_action_climb_from_profile_to_its_tasks(index: mapfind.FindIndex) -> None:
    """'Profiles on a Time that run a Task doing an HTTP Request'.

    Neither facet can be satisfied by one object on its own, which is exactly the query
    that used to be unaskable.  The answer is the Profiles -- the object that has the
    trigger -- and the detail names the Task that supplied the action.
    """
    hits, _ = mapfind.run_query(index, mapfind.Query(trigger="Time", action="HTTP Request"))
    assert _named(hits) == {(PROFILE, "Timed"), (PROFILE, "Away P")}
    assert "Fetcher" in next(hit.detail for hit in hits if hit.target.name == "Timed")


def test_a_profile_is_not_listed_for_its_tasks_alone(index: mapfind.FindIndex) -> None:
    """The rule that keeps one match from being reported twice.

    Profile 'Timed' runs the Task that performs the HTTP Request, but answering the action
    query with both the Task and every Profile that runs it doubles the list without
    adding an object to it.
    """
    hits, _ = mapfind.run_query(index, mapfind.Query(action="HTTP Request"))
    assert not [hit for hit in hits if hit.target.kind == PROFILE]


def test_combining_narrows_rather_than_widens(index: mapfind.FindIndex) -> None:
    """Adding a facet can only ever remove objects from the answer."""
    broad, _ = mapfind.run_query(index, mapfind.Query(trigger="Time"))
    narrow, _ = mapfind.run_query(index, mapfind.Query(trigger="Time", action="Perform Task"))
    assert _named(narrow) < _named(broad)
    assert _named(narrow) == {(PROFILE, "Timed")}


def test_project_narrowing_leaves_the_other_project_out(index: mapfind.FindIndex) -> None:
    """The Project control is a filter over the whole query, whatever the facets found."""
    hits, _ = mapfind.run_query(index, mapfind.Query(action="HTTP Request", project="Away"))
    assert _named(hits) == {(TASK, "Far")}


def test_an_empty_query_answers_nothing(index: mapfind.FindIndex) -> None:
    """A dialog pressed with nothing chosen is a slip, not a request for the whole file."""
    hits, total = mapfind.run_query(index, mapfind.Query())
    assert (hits, total) == ([], 0)
    # A Project on its own is a filter, not a question.
    assert mapfind.run_query(index, mapfind.Query(project="Home")) == ([], 0)


def test_results_are_grouped_by_project(index: mapfind.FindIndex) -> None:
    """Sorted so the list reads the way the configuration is organised."""
    hits, _ = mapfind.run_query(index, mapfind.Query(trigger="Time", action="HTTP Request"))
    assert [hit.project for hit in hits] == ["Away", "Home"]


def test_the_limit_caps_the_list_but_not_the_count(index: mapfind.FindIndex) -> None:
    """A truncated answer still says how much was left out."""
    hits, total = mapfind.run_query(index, mapfind.Query(action="HTTP Request"), limit=1)
    assert len(hits) == 1
    assert total == 2


# ##################################################################################
# The report.
# ##################################################################################
def test_report_says_what_was_asked_and_keeps_the_targets(index: mapfind.FindIndex) -> None:
    """Every location row carries the Target that makes it clickable."""
    query = mapfind.Query(app="Spotify")
    hits, total = mapfind.run_query(index, query)
    rows = mapfind.report_rows(query, hits, total, index)
    text = "\n".join(row.text for row in rows)
    assert "App 'Spotify'" in text
    assert "Found: 2 object(s)" in text
    assert {row.target.name for row in rows if row.target} == {"AppBar", "Opener"}


def test_report_states_what_the_scan_cannot_reach(index: mapfind.FindIndex) -> None:
    """The unresolvable references are said out loud, so a zero is never read as 'none'."""
    query = mapfind.Query(scene="Menu")
    rows = mapfind.report_rows(query, *mapfind.run_query(index, query), index)
    text = "\n".join(row.text for row in rows)
    assert "anonymous Tasks that live inside a Scene are not scanned" in text
    assert "1 action(s) name a Scene through a %variable" in text


def test_report_is_written_to_a_timestamped_file(index: mapfind.FindIndex, tmp_path: object) -> None:
    """The saved file holds the same report the results list shows."""
    query = mapfind.Query(action="HTTP Request")
    rows = mapfind.report_rows(query, *mapfind.run_query(index, query), index)
    here = os.getcwd()
    os.chdir(tmp_path)
    try:
        file_name = mapfind.write_find_report(rows)
        assert file_name.startswith("MapTasker_Find_")
        with open(file_name, encoding="utf-8") as written:
            assert "HTTP Request" in written.read()
    finally:
        os.chdir(here)


# ##################################################################################
# Nothing loaded.
# ##################################################################################
def test_an_empty_configuration_is_answered_not_raised() -> None:
    """Safe to build an index over nothing -- the GUI checks first, but this must not raise."""
    _load('<TaskerData sr="" dvi="1" tv="6.3.13"></TaskerData>')
    empty = mapfind.build_index()
    assert empty.objects == []
    assert empty.choices(mapfind.ACTION) == []
    assert mapfind.run_query(empty, mapfind.Query(action="Flash")) == ([], 0)
