"""MapTasker Missing Resources (resrefs, resstore) Unit Tests

Two halves, tested separately because they fail separately.

*What is collected* -- the table of which arguments are inputs is the part that quietly goes wrong.  An output path
(Write File, Copy File's destination) reported as missing is wrong every time, and an input left out is a file
nobody is told is gone.  So the fixture carries both, and the tests name which is which.

*What is concluded* -- a thing is missing only when every device that was asked says no, and a thing nobody was
asked about is neither found nor missing.  The failure there is saying "everything is fine" about a question that
was never put, so the unchecked case is tested as carefully as the missing one.

No device is involved: the answers are written into resstore, which is where a check leaves them.
"""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

import pytest
from maptasker.src.analysis import healthck, resrefs
from maptasker.src.core import resstore
from maptasker.src.core.initparg import ProgramArguments
from maptasker.src.core.mapjump import text_report
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.mapgen import taskerd

if TYPE_CHECKING:
    from pathlib import Path

PHONE = "192.0.2.1:1821"
TABLET = "192.0.2.2:1821"

#   Task 20 'Files'    every shape a file reference takes, and the outputs that are not references:
#                        act0 Read File 'Tasker/data.txt'            a FILE the action reads
#                        act1 Read File '%where'                      not checkable: a variable
#                        act2 Open File 'content://media/x'           not checkable: a content address
#                        act3 Write File 'Tasker/out.txt'             an OUTPUT -- must never be collected
#                        act4 Music Play 'Music/a.mp3'                a SOUND
#                        act5 Notify: an <Img> file, a sound file     an IMAGE and a SOUND
#                        act6 Notify: a Tasker built-in icon          a name, not a path -- ignored, not listed
#                        act7 List Files 'Download'                   a FOLDER
#                        act8 Read File 'Tasker/data.txt' again       the same thing used a second time
#                        act9 List Files 'Download/*.txt'             not checkable: a wildcard
#   Task 21 'Scenes'   Show Scene 'Panel', Show Scene '%which', and a Popup whose Layout is 'Panel'.
#   Task 22 'Apps'     a Launch App naming two apps (comma-joined), a Flash whose icon is an app's own, and a
#                      Kill App whose package is a %variable.
#   Profile 100        an Application context.
_FIXTURE_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2">
    <name>Home</name>
    <pids>100</pids>
    <tids>20,21,22</tids>
    <scenes>Panel</scenes>
  </Project>
  <Profile sr="prof100" ve="2">
    <id>100</id>
    <mid0>20</mid0>
    <nme>Watching</nme>
    <App sr="con0" ve="2">
      <cls0>com.d.Main</cls0>
      <label0>D</label0>
      <pkg0>com.d.app</pkg0>
    </App>
  </Profile>
  <Task sr="task20">
    <id>20</id>
    <nme>Files</nme>
    <Action sr="act0" ve="7"><code>417</code><Str sr="arg0" ve="3">Tasker/data.txt</Str></Action>
    <Action sr="act1" ve="7"><code>417</code><Str sr="arg0" ve="3">%where</Str></Action>
    <Action sr="act2" ve="7"><code>102</code><Str sr="arg0" ve="3">content://media/x</Str></Action>
    <Action sr="act3" ve="7"><code>410</code><Str sr="arg0" ve="3">Tasker/out.txt</Str></Action>
    <Action sr="act4" ve="7"><code>445</code><Str sr="arg0" ve="3">Music/a.mp3</Str></Action>
    <Action sr="act5" ve="7">
      <code>523</code>
      <Img sr="arg2" ve="2"><nme>Pictures/i.png</nme></Img>
      <Str sr="arg9" ve="3">Notifications/ding.ogg</Str>
    </Action>
    <Action sr="act6" ve="7"><code>523</code><Img sr="arg2" ve="2"><nme>mw_action_language</nme></Img></Action>
    <Action sr="act7" ve="7"><code>412</code><Str sr="arg0" ve="3">Download</Str></Action>
    <Action sr="act8" ve="7"><code>417</code><Str sr="arg0" ve="3">Tasker/data.txt</Str></Action>
    <Action sr="act9" ve="7"><code>412</code><Str sr="arg0" ve="3">Download/*.txt</Str></Action>
  </Task>
  <Task sr="task21">
    <id>21</id>
    <nme>Scenes</nme>
    <Action sr="act0" ve="7"><code>47</code><Str sr="arg0" ve="3">Panel</Str></Action>
    <Action sr="act1" ve="7"><code>47</code><Str sr="arg0" ve="3">%which</Str></Action>
    <Action sr="act2" ve="7"><code>550</code><Str sr="arg3" ve="3">Gone Layout</Str></Action>
  </Task>
  <Task sr="task22">
    <id>22</id>
    <nme>Apps</nme>
    <Action sr="act0" ve="7">
      <code>20</code>
      <App sr="arg0">
        <appClass>a.Main, b.Main</appClass>
        <appPkg>com.a.app, com.b.app</appPkg>
        <label>A, B</label>
      </App>
    </Action>
    <Action sr="act1" ve="7"><code>548</code><Img sr="arg4" ve="2"><cls>c.Main</cls><pkg>com.c.app</pkg></Img></Action>
    <Action sr="act2" ve="7">
      <code>18</code>
      <App sr="arg0"><appPkg>%pkg</appPkg></App>
    </Action>
  </Task>
  <Scene sr="scenePanel"><nme>Panel</nme></Scene>
</TaskerData>
"""


def _load(xml_text: str) -> None:
    """Build the PrimeItems lookup tables from XML text, the way taskerd does from a file."""
    root = ET.fromstring(xml_text)
    PrimeItems.file_to_get = "fixture.xml"
    PrimeItems.xml_root = root
    PrimeItems.xml_tree = ET.ElementTree(root)
    PrimeItems.program_arguments = ProgramArguments(task_action_warning_limit=100, language="English")
    specs_file = os.path.join(os.path.dirname(__file__), "..", "maptasker", "assets", "json", "arg_specs.json")
    with open(specs_file, encoding="utf-8") as handle:
        specs = json.load(handle)
    specs[str(len(specs))] = "ConditionList"
    PrimeItems.tasker_arg_specs = specs
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


@pytest.fixture(autouse=True)
def _configuration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The fixture loaded, and a result store of the test's own -- never the MapTasker_Resources.json of whoever runs this."""
    monkeypatch.setattr(resstore, "cache_path", lambda: str(tmp_path / "MapTasker_Resources.json"))
    _load(_FIXTURE_XML)


def _found() -> dict[tuple[str, str], list[resrefs.Reference]]:
    return resrefs.collect(PrimeItems).questions()


def _answer(device: str, **present: bool) -> None:
    """Record what a device said.  Keyword names are the values asked about, with '/' and '.' spelled out."""
    spelled = {
        ("path", "Tasker/data.txt"): present.get("data"),
        ("path", "Music/a.mp3"): present.get("music"),
        ("path", "Download"): present.get("download"),
        ("path", "Pictures/i.png"): present.get("image"),
        ("path", "Notifications/ding.ogg"): present.get("ding"),
        ("scene", "Panel"): present.get("panel"),
        ("scene", "Gone Layout"): present.get("layout"),
        ("app", "com.a.app"): present.get("a"),
        ("app", "com.b.app"): present.get("b"),
        ("app", "com.c.app"): present.get("c"),
        ("app", "com.d.app"): present.get("d"),
    }
    resstore.store(device, {question: bool(value) for question, value in spelled.items() if value is not None})


# ##################################################################################
# What is collected.
# ##################################################################################


def test_what_an_action_reads_is_collected_and_what_it_writes_is_not() -> None:
    values = {value for _kind, value in _found()}

    assert "Tasker/data.txt" in values
    assert "Tasker/out.txt" not in values, "Write File's path is something about to be made"


def test_each_reference_says_what_it_is_and_which_argument_it_came_from() -> None:
    by_value = {reference.value: reference for refs in _found().values() for reference in refs}

    assert (by_value["Tasker/data.txt"].kind, by_value["Tasker/data.txt"].used_by) == (resrefs.FILE, "Read File")
    assert by_value["Tasker/data.txt"].argument == "File"
    assert by_value["Music/a.mp3"].kind == resrefs.SOUND
    assert by_value["Download"].kind == resrefs.FOLDER
    assert by_value["Pictures/i.png"].kind == resrefs.IMAGE
    assert by_value["Notifications/ding.ogg"].kind == resrefs.SOUND
    assert by_value["Panel"].kind == resrefs.SCENE


def test_the_same_thing_used_twice_is_one_question_with_two_places() -> None:
    uses = _found()[("path", "Tasker/data.txt")]

    assert [use.where.action for use in uses] == [1, 9]


def test_a_variable_a_content_address_and_a_wildcard_are_listed_as_not_checked_with_why() -> None:
    skipped = {item.value: item.reason for item in resrefs.collect(PrimeItems).skipped}

    assert "variable" in skipped["%where"]
    assert "content address" in skipped["content://media/x"]
    assert "wildcard" in skipped["Download/*.txt"]
    assert "%which" in skipped
    assert "%pkg" in skipped


def test_an_icon_that_is_a_name_and_not_a_path_is_neither_checked_nor_listed() -> None:
    """Tasker's own icons are not files; listing them as unchecked would be noise."""
    everything = {value for _kind, value in _found()} | {item.value for item in resrefs.collect(PrimeItems).skipped}

    assert "mw_action_language" not in everything


def test_apps_come_from_the_app_pickers_the_icon_and_the_profile_context() -> None:
    """A comma-joined picker is two apps; an icon that is an app's own is that app; a context names its apps."""
    apps = {value for kind, value in _found() if kind == "app"}

    assert apps == {"com.a.app", "com.b.app", "com.c.app", "com.d.app"}


def test_a_scene_is_collected_from_a_layout_argument_too() -> None:
    assert ("scene", "Gone Layout") in _found()


def test_every_place_is_a_link_to_its_own_action() -> None:
    reference = _found()[("scene", "Panel")][0]

    assert reference.where.label.startswith("Project 'Home' > Task 'Scenes'")
    assert reference.where.anchor.endswith("-a1")


def test_nothing_loaded_collects_nothing() -> None:
    PrimeItems.tasker_root_elements = {}

    assert resrefs.collect(PrimeItems).found == []


# ##################################################################################
# What the phone said.
# ##################################################################################


def test_a_thing_every_device_asked_says_is_not_there_is_missing_everywhere_it_is_used() -> None:
    _answer(PHONE, data=False, music=True)
    gone = resrefs.missing(resrefs.collect(PrimeItems))

    assert [item.question for item in gone] == [("path", "Tasker/data.txt")]
    assert len(gone[0].uses) == 2
    assert list(gone[0].said_by) == [PHONE]


def test_a_thing_present_on_any_device_asked_is_not_missing() -> None:
    """The backup does not say which phone it is for."""
    _answer(PHONE, data=False)
    _answer(TABLET, data=True)

    assert resrefs.missing(resrefs.collect(PrimeItems)) == []


def test_a_thing_no_device_was_asked_about_is_unchecked_and_not_missing() -> None:
    _answer(PHONE, data=True)
    references = resrefs.collect(PrimeItems)

    assert resrefs.missing(references) == []
    assert resrefs.unchecked(references) == len(references.questions()) - 1


def test_a_device_that_was_not_asked_about_a_thing_does_not_vote_on_it() -> None:
    """The tablet's answers cover only what it was asked; silence from it is not a yes."""
    _answer(PHONE, data=False)
    _answer(TABLET, music=True)

    assert [item.question for item in resrefs.missing(resrefs.collect(PrimeItems))] == [("path", "Tasker/data.txt")]


def test_missing_apps_and_scenes_are_found_the_same_way() -> None:
    _answer(PHONE, a=True, b=False, c=False, d=True, panel=True, layout=False)

    assert {item.question for item in resrefs.missing(resrefs.collect(PrimeItems))} == {
        ("app", "com.b.app"),
        ("app", "com.c.app"),
        ("scene", "Gone Layout"),
    }


# ##################################################################################
# The Health Check.
# ##################################################################################


def test_nothing_is_reported_before_a_device_has_been_checked_and_the_report_says_why() -> None:
    """Silence would read as everything being there."""
    assert resrefs.lint_problems(PrimeItems) == []
    rows, _ = healthck.run_health_check(state=PrimeItems)
    report = text_report(rows)

    assert "[RESOURCE-MISSING]" not in report
    assert "none of them was checked for being on the device" in report
    assert resrefs.resources_unchecked(PrimeItems) > 0


def test_a_missing_resource_is_one_warning_naming_the_device_and_every_place() -> None:
    _answer(PHONE, data=False)
    problem = resrefs.lint_problems(PrimeItems)[0]
    detail = "".join(text for text, _ in problem.detail)

    assert (problem.severity, problem.tag) == ("WARNING", resrefs.MISSING)
    assert problem.where == "File 'Tasker/data.txt'"
    assert f"Not on {PHONE} on " in detail
    assert "all 2 places that use it" in detail
    assert "Task 'Files' (id 20) action 1 (Read File)" in detail
    assert problem.target is not None
    assert problem.target.action == 1
    assert [target.action for target in problem.related] == [9]


def test_the_health_check_reports_it_with_a_note_and_leaves_the_unchecked_note_out() -> None:
    _answer(PHONE, data=False, music=True)
    rows, counts = healthck.run_health_check(state=PrimeItems)
    report = text_report(rows)

    assert "[RESOURCE-MISSING]  File 'Tasker/data.txt'" in report
    assert "NOTE ON MISSING RESOURCES" in report
    assert "none of them was checked" not in report
    assert counts[healthck.WARNING] >= 1


def test_unticking_it_skips_the_check_and_takes_its_note_with_it() -> None:
    _answer(PHONE, data=False)
    rows, _ = healthck.run_health_check(skip=[resrefs.MISSING], state=PrimeItems)
    report = text_report(rows)

    assert "[RESOURCE-MISSING]" not in report
    assert "NOTE ON MISSING RESOURCES" not in report


def test_the_check_is_offered_in_the_panel() -> None:
    assert resrefs.MISSING in {category.tag for category in healthck.all_categories()}


# ##################################################################################
# The report.
# ##################################################################################


def test_the_report_leads_with_what_is_missing_and_links_each_place() -> None:
    _answer(PHONE, data=False, music=True)
    rows = resrefs.report_rows(resrefs.collect(PrimeItems))
    text = [row.text for row in rows]

    assert text[0] == "Missing resources"
    assert f"Checked against {PHONE} on " in text[1]
    assert text.index(next(line for line in text if line.startswith("MISSING"))) < text.index(
        next(line for line in text if line.startswith("NOT CHECKED")),
    )
    assert any(row.target is not None and row.target.action == 9 for row in rows)


def test_the_report_says_what_could_not_be_checked_and_why() -> None:
    _answer(PHONE, data=True)
    report = text_report(resrefs.report_rows(resrefs.collect(PrimeItems)))

    assert "NOT CHECKED" in report
    assert "built from a variable" in report


def test_the_report_before_any_check_says_so() -> None:
    rows = resrefs.report_rows(resrefs.collect(PrimeItems))

    assert rows[1].text == "No device has been checked yet."


def test_a_problem_met_while_asking_is_in_the_report() -> None:
    rows = resrefs.report_rows(resrefs.collect(PrimeItems), errors=["Apps: the device said no."])

    assert any("Problem: Apps: the device said no." in row.text for row in rows)


def test_the_report_is_written_to_a_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(resrefs, "output_path", lambda name, state: str(tmp_path / name))
    _answer(PHONE, data=False)

    path = resrefs.write_report(resrefs.report_rows(resrefs.collect(PrimeItems)), PrimeItems)

    assert path.startswith(str(tmp_path))
    assert "Tasker/data.txt" in open(path, encoding="utf-8").read()


# ##################################################################################
# The store.
# ##################################################################################


def test_answers_survive_a_round_trip_and_are_kept_per_device() -> None:
    resstore.store(PHONE, {("path", "a"): True, ("app", "b"): False})
    resstore.store(TABLET, {("path", "a"): False})

    answers = resstore.answers()
    assert set(answers) == {PHONE, TABLET}
    assert answers[PHONE][1] == {("path", "a"): True, ("app", "b"): False}
    assert answers[TABLET][1] == {("path", "a"): False}
    assert answers[PHONE][0]


def test_a_new_check_replaces_that_devices_answers_and_leaves_the_others() -> None:
    """A file put back must not stay missing, and one deleted must not stay present."""
    resstore.store(PHONE, {("path", "old"): False})
    resstore.store(TABLET, {("path", "t"): True})
    resstore.store(PHONE, {("path", "new"): True})

    answers = resstore.answers()
    assert answers[PHONE][1] == {("path", "new"): True}
    assert answers[TABLET][1] == {("path", "t"): True}


def test_forgetting_a_device_drops_only_its_answers() -> None:
    resstore.store(PHONE, {("path", "a"): True})
    resstore.store(TABLET, {("path", "a"): True})

    assert resstore.forget(PHONE) == ""

    assert set(resstore.answers()) == {TABLET}


def test_a_damaged_store_means_nothing_has_been_checked(tmp_path: Path) -> None:
    (tmp_path / "MapTasker_Resources.json").write_text("{not json", encoding="utf-8")

    assert resstore.answers() == {}
    assert resrefs.lint_problems(PrimeItems) == []
