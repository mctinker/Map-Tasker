"""MapTasker Map Cache Unit Tests

mapcache is what lets the Map view hand back the file it built a moment ago instead of
building the same one again, so what matters is not that it says yes -- it is that it
says no the instant anything the Map was built from has moved.  Every test here is
therefore a pair: something changes and the record is refused, and the same something put
back is accepted again.

The tables are built from a small XML fixture the way taskerd builds them from a file,
which is the arrangement test_healthck.py and test_impact.py use, and for the same
reason: no backup file and no GUI.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET

import pytest
from maptasker.src.initparg import ProgramArguments
from maptasker.src import mapcache, taskerd
from maptasker.src.primitem import PrimeItems, initial_tasker_root_elements

# One Project, one Profile, two Tasks and a Scene -- enough that a change can be made in
# any of the four tables, plus a global variable and a Tasker setting, which are the parts
# of the file that are not in any of them.
_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2">
    <name>Home</name>
    <pids>10</pids>
    <tids>20,21</tids>
    <scenes>Menu</scenes>
  </Project>
  <Profile sr="prof10" ve="2"><id>10</id><nme>Wake</nme><mid0>20</mid0></Profile>
  <Task sr="task20"><id>20</id><nme>Wake Up</nme>
    <Action sr="act0" ve="7"><code>547</code><Str sr="arg0" ve="3">%Handoff</Str></Action>
  </Task>
  <Task sr="task21"><id>21</id><nme>Helper</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">done</Str></Action>
  </Task>
  <Scene sr="scene0"><nme>Menu</nme></Scene>
  <Variable sr="var0"><n>%Handoff</n><v>ready</v></Variable>
  <Setting sr="set0"><n>beginnerMode</n><v>false</v></Setting>
</TaskerData>
"""


def _load(xml_text: str) -> None:
    """Build the PrimeItems lookup tables from XML text, the way taskerd does from a file."""
    root = ET.fromstring(xml_text)  # noqa: S314  (fixture text, defined in this file)
    PrimeItems.xml_root = root
    PrimeItems.tasker_root_elements = {
        "all_projects": taskerd.move_xml_to_table(root.findall("Project"), False, "name"),
        "all_profiles": taskerd.move_xml_to_table(root.findall("Profile"), True, "nme"),
        "all_tasks": taskerd.move_xml_to_table(root.findall("Task"), True, "nme"),
        "all_scenes": taskerd.move_xml_to_table(root.findall("Scene"), False, "nme"),
        "all_services": [],
    }


@pytest.fixture(autouse=True)
def _loaded(tmp_path, monkeypatch) -> None:
    """A loaded configuration, plain settings, and a Map file of our own to point at."""
    monkeypatch.chdir(tmp_path)
    _load(_XML)
    PrimeItems.program_arguments = ProgramArguments(display_detail_level=5, directory=True, font="Courier")
    PrimeItems.colors_to_use = {"project_color": "White"}
    mapcache.forget()
    yield
    mapcache.forget()


def _map_file(tmp_path, text: str = "<html>a Map</html>") -> str:
    """A stand-in for MapTasker.html, written where a build would have written it."""
    path = tmp_path / "MapTasker.html"
    path.write_text(text, encoding="utf-8")
    return str(path)


# ##################################################################################
# Nothing has changed: the Map that was built is the Map that would be built.
# ##################################################################################
def test_a_map_nothing_has_disturbed_is_current(tmp_path) -> None:
    """The whole point: same configuration, same settings, same file."""
    path = _map_file(tmp_path)
    mapcache.remember(path, 1234, mapcache.digests())

    assert mapcache.is_current(path, mapcache.digests())
    assert mapcache.output_lines() == 1234


def test_nothing_is_current_before_anything_has_been_remembered() -> None:
    """A session that has not built a Map yet has nothing to hand back."""
    assert not mapcache.is_current("/wherever/MapTasker.html", mapcache.digests())
    assert mapcache.output_lines() == 0


def test_forgetting_gives_up_the_record(tmp_path) -> None:
    """After forget() the next Map is built from scratch."""
    path = _map_file(tmp_path)
    mapcache.remember(path, 10, mapcache.digests())
    mapcache.forget()

    assert not mapcache.is_current(path, mapcache.digests())


# ##################################################################################
# The configuration moves.  Every one of these has to be refused.
# ##################################################################################
def test_renaming_a_task_is_not_the_same_configuration(tmp_path) -> None:
    """A name shows in the Map, so a Map built before the rename is the wrong Map."""
    path = _map_file(tmp_path)
    mapcache.remember(path, 10, mapcache.digests())

    task = PrimeItems.tasker_root_elements["all_tasks"]["20"]
    task["xml"].find("nme").text = "Wake Up Later"

    assert not mapcache.is_current(path, mapcache.digests())


def test_changing_an_action_argument_is_not_the_same_configuration(tmp_path) -> None:
    """The change the Map is most likely to be asked to show: an edit inside an action."""
    path = _map_file(tmp_path)
    mapcache.remember(path, 10, mapcache.digests())

    action_argument = PrimeItems.tasker_root_elements["all_tasks"]["21"]["xml"].find("Action/Str")
    action_argument.text = "something else"

    assert not mapcache.is_current(path, mapcache.digests())


def test_changing_an_attribute_is_not_the_same_configuration(tmp_path) -> None:
    """Attributes carry meaning here -- an action's 'sr' is its position in the Task."""
    path = _map_file(tmp_path)
    mapcache.remember(path, 10, mapcache.digests())

    PrimeItems.tasker_root_elements["all_tasks"]["21"]["xml"].find("Action").set("sr", "act9")

    assert not mapcache.is_current(path, mapcache.digests())


def test_the_derived_name_of_an_object_counts_as_the_configuration(tmp_path) -> None:
    """An unnamed Profile is given a name to display; that name is part of what is drawn."""
    path = _map_file(tmp_path)
    mapcache.remember(path, 10, mapcache.digests())

    PrimeItems.tasker_root_elements["all_profiles"]["10"]["name"] = "Wake (renamed by the naming pass)"

    assert not mapcache.is_current(path, mapcache.digests())


def test_a_change_outside_the_four_tables_still_counts(tmp_path) -> None:
    """A global variable's value is listed in the Map, and it lives in none of the tables."""
    path = _map_file(tmp_path)
    mapcache.remember(path, 10, mapcache.digests())

    PrimeItems.xml_root.find("Variable/v").text = "not ready"

    assert not mapcache.is_current(path, mapcache.digests())


def test_deleting_an_object_is_not_the_same_configuration(tmp_path) -> None:
    """Fewer Tasks, fewer Tasks drawn."""
    path = _map_file(tmp_path)
    mapcache.remember(path, 10, mapcache.digests())

    del PrimeItems.tasker_root_elements["all_tasks"]["21"]

    assert not mapcache.is_current(path, mapcache.digests())


def test_putting_the_configuration_back_makes_the_map_current_again(tmp_path) -> None:
    """Undo included: the test that the digest reads content and not merely 'something happened'."""
    path = _map_file(tmp_path)
    mapcache.remember(path, 10, mapcache.digests())
    task_name = PrimeItems.tasker_root_elements["all_tasks"]["20"]["xml"].find("nme")

    task_name.text = "Wake Up Later"
    assert not mapcache.is_current(path, mapcache.digests())

    task_name.text = "Wake Up"
    assert mapcache.is_current(path, mapcache.digests())


# ##################################################################################
# The settings move.  The configuration is untouched, and it still has to be refused.
# ##################################################################################
def test_a_changed_setting_is_a_different_map(tmp_path) -> None:
    """Display detail level decides how much of each Task is drawn."""
    path = _map_file(tmp_path)
    mapcache.remember(path, 10, mapcache.digests())

    PrimeItems.program_arguments.display_detail_level = 3

    assert not mapcache.is_current(path, mapcache.digests())


def _something_else(value: object) -> object:
    """A value of the same kind as `value` that is not equal to it."""
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if isinstance(value, list):
        return [*value, "changed"]
    return f"{value}changed"


@pytest.mark.parametrize("name", ProgramArguments.NAMES)
def test_every_setting_is_part_of_what_was_built(tmp_path, name) -> None:
    """The settings are not a curated list: every one counts, including one added later,
    without being named here."""
    path = _map_file(tmp_path)
    mapcache.remember(path, 10, mapcache.digests())

    PrimeItems.program_arguments[name] = _something_else(PrimeItems.program_arguments[name])

    assert not mapcache.is_current(path, mapcache.digests())


def test_a_changed_colour_is_a_different_map(tmp_path) -> None:
    """Colours are written into the Map itself, so they are part of what was built."""
    path = _map_file(tmp_path)
    mapcache.remember(path, 10, mapcache.digests())

    PrimeItems.colors_to_use["project_color"] = "Red"

    assert not mapcache.is_current(path, mapcache.digests())


# ##################################################################################
# The file itself.  Nothing may be handed back that is not still there as it was.
# ##################################################################################
def test_a_map_file_that_has_been_written_to_since_is_refused(tmp_path) -> None:
    """Something else wrote to it, so what is on disk is no longer what was built."""
    path = _map_file(tmp_path)
    mapcache.remember(path, 10, mapcache.digests())

    _map_file(tmp_path, "<html>a Map, and then some</html>")

    assert not mapcache.is_current(path, mapcache.digests())


def test_a_map_file_that_has_gone_is_refused(tmp_path) -> None:
    """Deleted from under us between one Map and the next."""
    path = _map_file(tmp_path)
    mapcache.remember(path, 10, mapcache.digests())

    (tmp_path / "MapTasker.html").unlink()

    assert not mapcache.is_current(path, mapcache.digests())


def test_a_different_path_is_refused(tmp_path) -> None:
    """The record is about one file, not about any Map anywhere."""
    path = _map_file(tmp_path)
    mapcache.remember(path, 10, mapcache.digests())

    assert not mapcache.is_current(str(tmp_path / "Somewhere Else.html"), mapcache.digests())


def test_remembering_a_file_that_was_never_written_records_nothing(tmp_path) -> None:
    """A build that failed before writing leaves nothing to hand back."""
    mapcache.remember(str(tmp_path / "never written.html"), 10, mapcache.digests())

    assert not mapcache.is_current(str(tmp_path / "never written.html"), mapcache.digests())


# ##################################################################################
# The Map build itself: what all of the above is in aid of.
# ##################################################################################
_SYNTHETIC_BACKUP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "synthetic_backup.xml")


def _build_a_map(tmp_path) -> tuple[float, int]:
    """Build the Map the way the GUI does, and report (the file's mtime, its line count)."""
    from maptasker.src.bildhtml import build_html  # noqa: PLC0415
    from maptasker.src.frontmtr import output_the_front_matter  # noqa: PLC0415
    from maptasker.src.runcfg import current_config  # noqa: PLC0415

    PrimeItems.output_lines.output_lines.clear()
    output_the_front_matter(current_config(), state=PrimeItems)
    build_html("")
    written = tmp_path / "MapTasker.html"
    return (written.stat().st_mtime_ns, PrimeItems.map_output_line_count)


@pytest.fixture
def _a_real_configuration(tmp_path, monkeypatch) -> None:
    """A whole loaded configuration and a GUI to build a Map for, in a directory of our own."""
    from maptasker.src.actionc import load_arg_specs  # noqa: PLC0415
    from maptasker.src.colrmode import set_color_mode  # noqa: PLC0415
    from maptasker.src.initparg import initialize_runtime_arguments  # noqa: PLC0415
    from maptasker.src.lineout import LineOut  # noqa: PLC0415
    from maptasker.src.proginit import get_data_and_output_intro  # noqa: PLC0415

    monkeypatch.chdir(tmp_path)
    PrimeItems.program_arguments = initialize_runtime_arguments()
    PrimeItems.program_arguments.update({"file": _SYNTHETIC_BACKUP, "display_detail_level": 5, "gui": True})
    # Anything other than None means "the GUI is up", which is what keeps the build from
    # opening the finished Map in a web browser (see bildhtml.display_output).
    monkeypatch.setattr(PrimeItems, "mygui", object())
    PrimeItems.colors_to_use = set_color_mode("dark")
    PrimeItems.output_lines = LineOut()
    PrimeItems.tasker_root_elements = initial_tasker_root_elements()
    PrimeItems.file_to_get = open(_SYNTHETIC_BACKUP)
    load_arg_specs()
    get_data_and_output_intro(True)
    yield
    mapcache.forget()


@pytest.mark.usefixtures("_a_real_configuration")
def test_an_unchanged_map_is_not_built_a_second_time(tmp_path) -> None:
    """The whole feature, end to end: the third build leaves the file exactly where it was.

    The third and not the second, because the first build of a session settles the
    configuration as it goes -- see mapcache.digests() -- so the second one really does
    have something new to say.
    """
    _build_a_map(tmp_path)
    _, second_lines = _build_a_map(tmp_path)
    second_mtime, _ = _build_a_map(tmp_path)  # the one that should be answered from the record

    third_mtime, third_lines = _build_a_map(tmp_path)

    assert third_mtime == second_mtime, "the Map was written again when nothing had changed"
    assert third_lines == second_lines, "the size of the Map was lost along with the build"


@pytest.mark.usefixtures("_a_real_configuration")
def test_an_edited_configuration_is_built_again(tmp_path) -> None:
    """The other half: a Map that is no longer right is not handed back."""
    _build_a_map(tmp_path)
    _build_a_map(tmp_path)
    settled_mtime, _ = _build_a_map(tmp_path)

    task = next(iter(PrimeItems.tasker_root_elements["all_tasks"].values()))
    task["name"] = f"{task['name']} (edited)"
    rebuilt_mtime, _ = _build_a_map(tmp_path)

    assert rebuilt_mtime != settled_mtime, "an edited configuration was shown the old Map"
