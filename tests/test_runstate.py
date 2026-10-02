"""RunState: a run's own state, which a function can be handed instead of reading PrimeItems."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from maptasker.src.colrmode import set_color_mode
from maptasker.src import bildhtml, outline, proginit, runcli, taskerd, timeline
from maptasker.src.actionc import load_arg_specs
from maptasker.src import caveats, diagram, diagutil, dirout, frontmtr, mapjump, maputils, projects, share, tasks, twisty
from maptasker.src import property as prop
from maptasker.src.lineout import LineOut
from maptasker.src.mapjump import PROFILE, TASK, Target
from maptasker.src.sysconst import DIAGRAM_FILE as diagram_file
from maptasker.src.primitem import MAP_OUTPUT_ATTRIBUTES, PrimeItems, RunState, reset_attributes
from maptasker.src.runcfg import current_config

_PROFILE = Target(kind=PROFILE, key="10", name="Wake Up")


@pytest.fixture(autouse=True)
def _clean_slate() -> None:
    """Nothing noted against a diagram, on the global or in the module's own buffers."""
    PrimeItems.netmap_output = []
    PrimeItems.diagram_object_seeds = {}
    diagram._pending_boxes.clear()  # noqa: SLF001
    diagram._pending_tasks.clear()  # noqa: SLF001


def test_the_global_is_a_run_state() -> None:
    assert isinstance(PrimeItems, RunState)


def test_two_run_states_share_no_containers() -> None:
    """A dict, list or set filled in on one must never turn up in another."""
    first, second = RunState(), RunState()

    first.grand_totals["projects"] = 3
    first.netmap_output.append("line")
    first.emitted_anchors.add("a")

    assert second.grand_totals["projects"] == 0
    assert second.netmap_output == []
    assert second.emitted_anchors == set()
    assert PrimeItems.grand_totals is not first.grand_totals


def test_a_reset_touches_only_the_state_it_is_given() -> None:
    state = RunState()
    state.grand_totals["projects"] = 5
    PrimeItems.grand_totals["projects"] = 7

    reset_attributes(*MAP_OUTPUT_ATTRIBUTES, state=state)

    assert state.grand_totals["projects"] == 0
    assert PrimeItems.grand_totals["projects"] == 7
    PrimeItems.grand_totals["projects"] = 0


def test_the_project_counts_are_reset_on_the_state_handed_in() -> None:
    state = RunState()
    state.scene_count = 4
    PrimeItems.scene_count = 9

    assert projects.setup_summary_counts(state) == 0

    assert state.scene_count == 0
    assert PrimeItems.scene_count == 9
    PrimeItems.scene_count = 0


def test_a_diagram_line_goes_to_the_state_it_is_given() -> None:
    state = RunState()

    diagutil.add_output_line("║ Wake Up ║", state=state)

    assert state.netmap_output == ["║ Wake Up ║"]
    assert PrimeItems.netmap_output == []


def test_a_diagram_object_is_recorded_on_the_state_it_is_given() -> None:
    """The box is noted and then flushed to its rows, all without the global being set up."""
    state = RunState()
    diagutil.add_output_line("header", state=state)
    diagram._note_box(_PROFILE, "║ Wake Up")  # noqa: SLF001
    diagram._flush_boxes(["top", "║ Wake Up ║", "bottom"], state=state)  # noqa: SLF001

    assert state.diagram_object_seeds[_PROFILE.anchor][0] == 2
    assert PrimeItems.diagram_object_seeds == {}


def test_an_anchor_is_remembered_by_the_state_it_was_written_into() -> None:
    """An id may appear in a document once.  Two runs are two documents, so each gets its own."""
    first, second = RunState(), RunState()
    target = Target(TASK, "13", "Remind Me")

    assert mapjump.anchor_html(target, state=first) != ""
    assert mapjump.anchor_html(target, state=first) == ""
    assert mapjump.anchor_html(target, state=second) != ""
    assert target.anchor not in PrimeItems.emitted_anchors


def test_an_unnamed_task_is_counted_on_the_state_it_is_read_from() -> None:
    state = RunState()
    state.tasker_root_elements["all_tasks"] = {"13": {"xml": None, "name": ""}}
    before = PrimeItems.task_count_unnamed

    _, name = tasks.get_task_name("13", [], [], "Entry", current_config(), state=state)

    assert name.startswith("Unnamed")
    assert state.task_count_unnamed == 1
    assert PrimeItems.task_count_unnamed == before


def test_a_directory_item_is_added_to_the_state_it_is_given() -> None:
    state = RunState()

    dirout.add_directory_item("tasks", "Remind Me", current_config(), state=state)

    assert state.directory_items["tasks"] == [["Remind_Me", "Remind Me"]]
    assert PrimeItems.directory_items["tasks"] == []


def test_the_owning_profile_is_found_in_the_state_it_is_asked_of() -> None:
    """The tables are the state's own: the global holds none of this Task or Profile."""
    state = RunState()
    state.tasker_root_elements["all_tasks"] = {"13": {"xml": None, "name": "Remind Me"}}
    profile = ET.fromstring('<Profile sr="prof5"><id>5</id><mid0>13</mid0><nme>Morning</nme></Profile>')  # noqa: S314
    state.tasker_root_elements["all_profiles"] = {"5": {"xml": profile, "name": "Morning"}}

    assert maputils.find_owning_profile("Remind Me", state=state) == "Morning"
    assert maputils.find_owning_profile("Remind Me", state=PrimeItems) == ""


def _loaded_state() -> RunState:
    """A run state holding a (tiny) backup and an empty output, and nothing on the global."""
    state = RunState()
    state.xml_root = ET.fromstring('<TaskerData sr="" dvi="1" tv="6.3.13"/>')  # noqa: S314
    state.output_lines = LineOut(state=state)
    state.file_to_get = "backup.xml"
    return state


def test_the_front_matter_is_written_into_the_state_it_is_given() -> None:
    state = _loaded_state()
    before = len(PrimeItems.output_lines.output_lines) if PrimeItems.output_lines else 0

    frontmtr.output_the_front_matter(current_config(), state=state)

    assert "6.3.13" in state.heading
    assert any("backup.xml" in line for line in state.output_lines.output_lines)
    assert (len(PrimeItems.output_lines.output_lines) if PrimeItems.output_lines else 0) == before


def test_a_taskernet_description_is_written_into_the_state_it_is_given() -> None:
    state = _loaded_state()
    config = current_config().with_changes(colors=set_color_mode("dark"))
    root = ET.fromstring(  # noqa: S314
        "<Task><Share><d>Turns the lights on</d><g>lights</g></Share></Task>",
    )

    share.share(root, "tasktab", config=config, state=state)

    assert any("Turns the lights on" in line for line in state.output_lines.output_lines)


def test_a_twisty_is_opened_and_closed_on_the_state_it_is_given() -> None:
    state = _loaded_state()
    before = len(PrimeItems.output_lines.output_lines) if PrimeItems.output_lines else 0

    twisty.add_twisty("task_color", "Remind Me", state=state)
    assert any("Remind Me" in line for line in state.output_lines.output_lines)

    twisty.remove_twisty(state=state)
    assert state.output_lines.output_lines[-1] == "</details></span><br>\n"
    assert (len(PrimeItems.output_lines.output_lines) if PrimeItems.output_lines else 0) == before


def test_the_caveats_are_written_into_the_state_it_is_given() -> None:
    state = _loaded_state()
    before = len(PrimeItems.output_lines.output_lines) if PrimeItems.output_lines else 0

    caveats.display_caveats(current_config(), state=state)

    assert state.output_lines.output_lines
    assert (len(PrimeItems.output_lines.output_lines) if PrimeItems.output_lines else 0) == before


def test_a_profiles_properties_are_written_into_the_state_it_is_given() -> None:
    state = _loaded_state()
    profile = ET.fromstring('<Profile sr="prof5"><id>5</id><flags>12</flags><nme>Morning</nme></Profile>')  # noqa: S314
    before = len(PrimeItems.output_lines.output_lines) if PrimeItems.output_lines else 0

    prop.get_properties("Profile:", profile, config=current_config(), state=state)

    assert state.output_lines.output_lines
    assert (len(PrimeItems.output_lines.output_lines) if PrimeItems.output_lines else 0) == before


def test_starting_the_output_again_clears_the_state_the_lines_belong_to() -> None:
    """refresh_our_output throws the run's output away and writes the front matter again."""
    state = _loaded_state()
    state.grand_totals["projects"] = 5
    PrimeItems.grand_totals["projects"] = 7

    state.output_lines.refresh_our_output(False, "Home", "")

    assert state.grand_totals["projects"] == 0
    assert PrimeItems.grand_totals["projects"] == 7
    assert any("Project: Home" in line for line in state.output_lines.output_lines)
    assert "6.3.13" in state.heading
    PrimeItems.grand_totals["projects"] = 0


def test_a_line_is_formatted_by_the_state_its_output_belongs_to() -> None:
    """The directory switch and the hyperlink target are the owning state's, not the global's."""
    state = _loaded_state()
    state.program_arguments.directory = True
    state.directory_items["current_item"] = "tasks_Remind_Me"
    PrimeItems.directory_items["current_item"] = ""

    link = state.output_lines.add_directory_link("tasks", "Remind Me", "")

    assert "tasks_Remind_Me" in link


_OUTLINE_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0"><name>Home</name><pids>10</pids><tids>20,21</tids></Project>
  <Profile sr="prof10" ve="2"><id>10</id><mid0>20</mid0><nme>One</nme></Profile>
  <Task sr="task20" ve="2"><id>20</id><nme>Caller</nme>
    <Action sr="act0"><code>130</code><Str sr="arg0">Callee</Str></Action>
  </Task>
  <Task sr="task21" ve="2"><id>21</id><nme>Callee</nme><Action sr="act0"><code>548</code></Action></Task>
</TaskerData>"""


def _outline_state(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> RunState:
    """A run state that has loaded the outline fixture from a file, the way a user's load does.

    Nothing of it is on the global: taskerd parses into the state it is handed.  (The history a
    load would record on disk is switched off; it is not what is being looked at.)
    """
    monkeypatch.setattr(timeline, "record", lambda _path: None)
    backup = tmp_path / "backup.xml"
    backup.write_text(_OUTLINE_XML, encoding="utf-8")
    state = RunState()
    state.colors_to_use = set_color_mode("dark")
    state.output_lines = LineOut(state=state)
    with backup.open(encoding="utf-8") as opened:
        state.file_to_get = opened
        assert taskerd.get_the_xml_data(state=state) == 0
    state.file_to_get = str(backup)
    return state


def test_a_whole_outline_is_built_on_a_state_of_its_own(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    """The Outline and the Diagram built from it, start to finish, against a RunState that
    is not PrimeItems: its tables, its output, its call links -- and nothing on the global.
    """
    monkeypatch.chdir(tmp_path)
    state = _outline_state(tmp_path, monkeypatch)
    PrimeItems.output_lines = LineOut()
    on_the_global = len(PrimeItems.output_lines.output_lines)
    netmap_before, model_before = list(PrimeItems.netmap_output), dict(PrimeItems.diagram_model)

    outline.outline_the_configuration(state=state)

    assert state.tasker_root_elements["all_tasks_by_name"]["Caller"]["call_tasks"] == ["Callee"]
    assert any("Caller" in line for line in state.output_lines.output_lines)
    assert state.diagram_model
    assert (tmp_path / diagram_file).read_text(encoding="utf-8")
    assert len(PrimeItems.output_lines.output_lines) == on_the_global
    assert PrimeItems.netmap_output == netmap_before
    assert PrimeItems.diagram_model == model_before


def test_a_whole_map_is_built_on_a_state_of_its_own(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    """The Map, from the Projects down to the file it is written to, against a RunState that is
    not PrimeItems.  Only the output folder is still read from the global (outdir.py).
    """
    load_arg_specs()
    monkeypatch.chdir(tmp_path)
    state = _outline_state(tmp_path, monkeypatch)
    state.headless = True  # Nobody is watching: do not open a browser.
    state.tasker_arg_specs = PrimeItems.tasker_arg_specs
    state.tasker_category_descriptions = PrimeItems.tasker_category_descriptions
    PrimeItems.output_lines = LineOut()
    monkeypatch.setattr(PrimeItems.program_arguments, "output_directory", str(tmp_path))
    on_the_global = len(PrimeItems.output_lines.output_lines)
    projects_before = PrimeItems.grand_totals["projects"]

    bildhtml.build_html("", state=state)

    assert state.grand_totals["projects"] == 1
    assert state.grand_totals["named_tasks"] == 2
    assert "Caller" in (tmp_path / "MapTasker.html").read_text(encoding="utf-8")
    assert len(PrimeItems.output_lines.output_lines) == on_the_global
    assert PrimeItems.grand_totals["projects"] == projects_before


def test_a_backup_is_loaded_into_the_state_it_is_given(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    tables_before = dict(PrimeItems.tasker_root_elements)
    root_before = PrimeItems.xml_root

    state = _outline_state(tmp_path, monkeypatch)

    assert set(state.tasker_root_elements["all_tasks"]) == {"20", "21"}
    assert state.loaded_highest_object_id == 21
    assert state.xml_root is not root_before
    assert PrimeItems.tasker_root_elements == tables_before
    assert PrimeItems.xml_root is root_before


def test_a_run_is_started_and_its_file_read_on_a_state_of_its_own(
    tmp_path: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The start of a run, as proginit does it: open the named backup, parse it, write the front
    matter -- all of it on the state that was handed in.
    """
    monkeypatch.setattr(timeline, "record", lambda _path: None)
    monkeypatch.chdir(tmp_path)
    backup = tmp_path / "backup.xml"
    backup.write_text(_OUTLINE_XML, encoding="utf-8")
    state = RunState()
    state.colors_to_use = set_color_mode("dark")
    state.output_lines = LineOut(state=state)
    state.program_arguments.file = str(backup)
    root_before, lines_before = PrimeItems.xml_root, len(PrimeItems.output_lines.output_lines)

    assert proginit.get_data_and_output_intro(True, state=state) == 0

    assert set(state.tasker_root_elements["all_tasks"]) == {"20", "21"}
    assert "6.3.13" in state.heading
    assert state.output_lines.output_lines
    assert PrimeItems.xml_root is root_before
    assert len(PrimeItems.output_lines.output_lines) == lines_before


def test_a_runtime_option_is_set_on_the_state_it_is_given() -> None:
    """The command line's options are read into the state's own settings, not the global's."""
    state = RunState()
    bold_before = PrimeItems.program_arguments.bold
    PrimeItems.program_arguments.bold = False

    runcli.get_name_attributes("bold underline", state=state)

    assert state.program_arguments.bold is True
    assert state.program_arguments.underline is True
    assert PrimeItems.program_arguments.bold is False
    PrimeItems.program_arguments.bold = bold_before
