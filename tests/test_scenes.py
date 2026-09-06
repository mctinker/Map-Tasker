"""MapTasker Scene parsing (scenes) Unit Tests

A Scene is a screen the user built: a size, a list of UI elements, and the Tasks those
elements fire when tapped.  scenes.py reads all three out of the <Scene> element.

The element list is stored two entirely different ways depending on which Scene editor
built it.  A Scene V1 element is a child element named for its type (<ButtonElement>,
<TextElement>); a Scene V2 element is a row of gzipped, Base64'd JSON in a single <lj>
child.  Both shapes reach the same output, and only one of them is exercised by any
backup a given developer happens to test against -- which is the argument for testing
the pair of them here rather than trusting whichever one the sample file has.

One test is marked xfail: a pre-existing defect found while writing this file, described
at the test.
"""

from __future__ import annotations

import base64
import gzip
import io
import json
import xml.etree.ElementTree as ET

import pytest

from maptasker.src import scenes, taskerd
from maptasker.src.colrmode import set_color_mode
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.lineout import LineOut
from maptasker.src.primitem import PrimeItems, initial_directory_items, initial_found_named_items

_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0"><name>Home</name><scenes>Panel,Dialog</scenes></Project>
  <Project sr="proj1"><name>Bare</name></Project>
  <Scene sr="scene0"><nme>Panel</nme><heightPort>800</heightPort><widthPort>480</widthPort></Scene>
  <Scene sr="scene1"><nme>Dialog</nme><heightPort>200</heightPort><widthPort>300</widthPort></Scene>
</TaskerData>"""


@pytest.fixture(autouse=True)
def _loaded() -> None:
    """A loaded configuration with two Scenes in one Project."""
    PrimeItems.program_arguments = initialize_runtime_arguments()
    PrimeItems.colors_to_use = set_color_mode("dark")
    PrimeItems.output_lines = LineOut()
    PrimeItems.found_named_items = initial_found_named_items()
    PrimeItems.named_task_count_total = 0
    PrimeItems.directory_items = initial_directory_items()
    PrimeItems.emitted_anchors = set()
    PrimeItems.xml_root = ET.fromstring(_XML)  # noqa: S314  (fixture text, defined in this file)
    taskerd.build_tasker_tables()


def _output() -> str:
    """Everything written to the output so far, as one string to search."""
    return "".join(PrimeItems.output_lines.output_lines)


def _gzipped_json(payload: object) -> str:
    """A Scene V2 <lj> payload: JSON, gzipped, Base64'd -- built the way Tasker writes it."""
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb") as handle:
        handle.write(json.dumps(payload).encode())
    return base64.b64encode(buffer.getvalue()).decode()


# ##################################################################################
# Geometry
# ##################################################################################
def test_geometry_is_read_width_first() -> None:
    """The return order is the whole contract of this function, and both values are bare
    numbers -- transposing them produces a plausible-looking wrong answer, not an error.
    """
    scene = PrimeItems.tasker_root_elements["all_scenes"]["Panel"]["xml"]
    assert scenes.get_geometry(scene) == ("480", "800")


def test_a_scene_without_geometry_is_not_an_error() -> None:
    """A Scene that has never been opened in the editor carries no size."""
    assert scenes.get_geometry(ET.fromstring("<Scene/>")) == (None, None)  # noqa: S314


@pytest.mark.xfail(
    reason="Pre-existing defect: process_scene unpacks 'height, width = get_geometry(scene)' "
    "but get_geometry returns (width, height), so the two are transposed and the reported "
    "'Width/Height' is the wrong way round for every Scene.",
    strict=False,
)
def test_a_scene_reports_its_size_the_way_it_is_labelled() -> None:
    """The Panel Scene is 480 wide and 800 tall.  A line labelled "Width/Height" that
    reads "800 X 480" is not ambiguous, it is wrong -- and a portrait Scene reported as
    landscape is the kind of thing a reader takes at face value.
    """
    scenes.process_scene("Panel", [], None, 0)
    assert "Width/Height: 480 X 800" in _output()


# ##################################################################################
# The two ways a Scene stores its elements
# ##################################################################################
def test_scene_v1_elements_are_listed_by_name_and_type() -> None:
    """A V1 element is a child named for its type, with its own name in the first <Str>."""
    scene = ET.fromstring(  # noqa: S314  (fixture text, built in this file)
        "<Scene><nme>Panel</nme>"
        "<ButtonElement><Str>OK</Str></ButtonElement>"
        "<TextElement><Str>Heading</Str></TextElement>"
        "</Scene>",
    )
    assert scenes.get_scene_element_names(scene) == ["'OK' (Button)", "'Heading' (Text)"]


def test_an_unnamed_element_is_listed_by_type_alone() -> None:
    """An element the user never named would otherwise be listed as "'' (Text)"."""
    scene = ET.fromstring("<Scene><TextElement><Str></Str></TextElement></Scene>")  # noqa: S314
    assert scenes.get_scene_element_names(scene) == ["Text"]


def test_the_scenes_own_settings_are_not_listed_as_elements() -> None:
    """<nme>, <heightPort> and <PropertiesElement> are the Scene's own properties, not
    things on it.  Listing them tells the reader the screen has controls it does not.
    """
    scene = ET.fromstring(  # noqa: S314  (fixture text, built in this file)
        "<Scene><nme>Panel</nme><heightPort>800</heightPort><widthPort>480</widthPort>"
        "<PropertiesElement><Str>props</Str></PropertiesElement>"
        "<ButtonElement><Str>OK</Str></ButtonElement>"
        "</Scene>",
    )
    assert scenes.get_scene_element_names(scene) == ["'OK' (Button)"]


def test_a_scene_v2_element_row_is_not_listed_as_an_element() -> None:
    """<lj> is the whole V2 element list compressed into one child.  Treated as an
    element it becomes a single meaningless row called "lj".
    """
    scene = ET.fromstring(f"<Scene><lj>{_gzipped_json([])}</lj></Scene>")  # noqa: S314
    assert scenes.get_scene_element_names(scene) == []


# ##################################################################################
# Scene V2: the compressed JSON element list
# ##################################################################################
def test_a_compressed_element_list_round_trips() -> None:
    """Base64 in, gzip out, JSON parsed -- the whole of a V2 Scene's contents arrive
    through this one function.
    """
    assert scenes.decompress_gzip_json(_gzipped_json({"type": "Button", "text": "OK"})) == {
        "type": "Button",
        "text": "OK",
    }


def test_an_undecodable_element_list_is_reported_not_raised() -> None:
    """A truncated or non-gzip <lj> must not stop the run: the rest of the configuration
    is still worth showing, and the caller prints this message beside the Scene.
    """
    result = scenes.decompress_gzip_json("this is not base64 @@@")
    assert isinstance(result, str)
    assert result.startswith("An error occurred")


def test_a_scene_v2_element_is_output_with_its_attributes() -> None:
    """The V2 element's type leads, and its remaining keys are indented under it so the
    attributes group with the element they belong to rather than running together.
    """
    scenes.process_recursive_json({"type": "Button", "text": "OK", "id": 3}, 0)
    output = _output()
    assert "type: Button" in output
    assert "text: OK" in output
    assert output.index("type: Button") < output.index("text: OK")


def test_nested_scene_v2_elements_are_indented_by_depth() -> None:
    """V2 JSON nests -- a container element holds its children -- and the nesting is only
    visible as indentation, the same as a Task's If blocks.
    """
    scenes.process_recursive_json({"type": "Box", "child": {"type": "Button", "text": "OK"}}, 0)
    lines = [line for line in PrimeItems.output_lines.output_lines if "type:" in line]
    assert len(lines) == 2
    assert lines[1].index("type:") > lines[0].index("type:")


def test_a_list_of_scene_v2_elements_is_output_one_per_item() -> None:
    """The top level of a V2 element list is a list, not an object."""
    scenes.process_recursive_json([{"type": "Button"}, {"type": "Text"}], 0)
    output = _output()
    assert "type: Button" in output
    assert "type: Text" in output


def test_a_scene_v2_row_that_will_not_decode_says_so_in_the_output() -> None:
    """The reader has to be told the Scene's contents could not be read -- a Scene
    silently listed with no elements looks like an empty Scene.
    """
    scenes.get_scene_elements(ET.fromstring("<lj>not valid at all @@@</lj>"), 0)  # noqa: S314
    assert "could not be processed" in _output()


# ##################################################################################
# Which Scenes belong to a Project
# ##################################################################################
def test_a_projects_scenes_are_found_by_name() -> None:
    """A Project lists its Scenes as a comma-separated <scenes> string, and that is the
    only link between the two -- a Scene element says nothing about its Project.
    """
    assert scenes.process_project_scenes(
        PrimeItems.tasker_root_elements["all_projects"]["Home"]["xml"],
        None,
        [],
    )
    assert PrimeItems.scene_count == 2


def test_a_project_with_no_scenes_reports_none() -> None:
    """Most Projects have no Scenes at all, so this is the common path."""
    assert not scenes.process_project_scenes(
        PrimeItems.tasker_root_elements["all_projects"]["Bare"]["xml"],
        None,
        [],
    )


def test_asking_for_one_scene_narrows_the_project_to_it() -> None:
    """--scene asks for a single Scene by name.  Its Project is still walked, so the
    other Scenes have to be filtered out here or they are all output anyway.
    """
    PrimeItems.program_arguments["single_scene_name"] = "Dialog"
    assert scenes.process_project_scenes(
        PrimeItems.tasker_root_elements["all_projects"]["Home"]["xml"],
        None,
        [],
    )
    assert PrimeItems.scene_count == 1
    assert PrimeItems.found_named_items["single_scene_found"] is True


# ##################################################################################
# Walking a Scene's elements
# ##################################################################################
#
# A Scene element stores the Task it fires BEFORE its <Str> name, and process_tasks
# stops looking at the first <Str> or <Int> -- everything after that is the element's
# arguments, not more Tasks.  A fixture written the other way round finds no Tasks at
# all, silently, which is the same bug this ordering assumption would cause against a
# backup written by a future Tasker.  The same trap as get_profile_tasks; see
# test_profiles.py.
_BUTTON = (
    '<ButtonElement sr="but1"><clickTask>10</clickTask><Str>OK</Str><geom>0,0,100,50</geom></ButtonElement>'
)
_TEXT = '<TextElement sr="txt1"><Str>Label</Str><geom>0,60,100,20</geom></TextElement>'


def _scene_with(elements: str) -> ET.Element:
    """A Scene carrying the given elements, loaded so its Tasks resolve."""
    PrimeItems.xml_root = ET.fromstring(  # noqa: S314  (fixture text, built in this file)
        '<TaskerData sr="" dvi="1" tv="6.3.13">'
        f'<Scene sr="scene0"><nme>Panel</nme><heightPort>800</heightPort><widthPort>480</widthPort>{elements}</Scene>'
        '<Task sr="task10"><id>10</id><nme>Clicked</nme></Task>'
        "</TaskerData>",
    )
    taskerd.build_tasker_tables()
    return PrimeItems.tasker_root_elements["all_scenes"]["Panel"]["xml"]


def test_each_scene_element_is_listed_with_its_geometry() -> None:
    """Where a control sits and how big it is, which is what makes a list of elements a
    description of a screen rather than a list of names.
    """
    scenes.get_details(_scene_with(_BUTTON + _TEXT), [], 0)
    output = _output()
    assert "'OK' Element of type Button ...with geometry 0x0 100x50" in output
    assert "'Label' Element of type Text ...with geometry 0x60 100x20" in output


def test_an_element_without_geometry_is_still_listed() -> None:
    """An element that has never been positioned has no <geom>, and must not be dropped."""
    scenes.get_details(_scene_with('<TextElement sr="t"><Str>Bare</Str></TextElement>'), [], 0)
    assert "'Bare' Element of type Text" in _output()


def test_the_task_an_element_fires_is_listed_under_it() -> None:
    """A Scene's buttons are how a Task gets run by hand.  Without them the Task looks
    unreachable -- in no Profile and called by nothing.
    """
    scenes.get_details(_scene_with(_BUTTON), [], 0)
    output = _output()
    assert "Clicked" in output
    assert "TAP" in output  # the kind of interaction that fires it


def test_a_scene_task_counts_toward_the_totals() -> None:
    """A Task reached only from a Scene is still a Task in this configuration."""
    scenes.get_details(_scene_with(_BUTTON), [], 0)
    assert PrimeItems.named_task_count_total == 1


def test_a_placeholder_task_reference_is_not_a_task() -> None:
    """Tasker writes a negative id for an element whose Task slot is empty.  Looking it
    up finds nothing, and listing it invents a Task the configuration does not have.
    """
    element = '<ButtonElement sr="but1"><clickTask>-1</clickTask><Str>OK</Str></ButtonElement>'
    scenes.get_details(_scene_with(element), [], 0)
    assert PrimeItems.named_task_count_total == 0


def test_element_details_are_left_out_below_detail_level_three() -> None:
    """The element list is the bulk of a Scene's output, and the lower detail levels
    exist to leave that kind of bulk out.
    """
    PrimeItems.program_arguments["display_detail_level"] = 2
    scenes.get_details(_scene_with(_BUTTON + _TEXT), [], 0)
    assert "Element of type" not in _output()


def test_a_layout_scene_inside_an_element_is_reported_with_its_size() -> None:
    """An element can hold a whole Scene as its layout.  It is a second screen inside the
    first, and its contents are otherwise never shown.
    """
    element = (
        '<ButtonElement sr="but1"><Str>Holder</Str><Scene>'
        "<Sub><nme>Inner</nme><heightPort>100</heightPort><widthPort>200</widthPort></Sub>"
        "</Scene></ButtonElement>"
    )
    scenes.get_details(_scene_with(element), [], 0)
    assert "Element has an item 'Layout' (Scene) with width/height 200 X 100" in _output()


# ##################################################################################
# Naming an unnamed Task reached from a Scene
# ##################################################################################
def test_a_long_scene_task_name_is_shortened_for_the_directory() -> None:
    """The directory appends "(Scene)" to the name, so a name already at the limit would
    push the entry past it.  The id has to survive the trim -- it is what makes the
    shortened name unique.
    """
    _scene_with(_BUTTON)
    long_name = "A very long derived task name indeed.10 (Unnamed)"
    PrimeItems.tasker_root_elements["all_tasks"]["10"]["name"] = long_name
    PrimeItems.tasker_root_elements["all_tasks_by_name"] = {"other": {"xml": None, "id": "99"}}

    result = scenes.adjust_name_and_add_to_directory(long_name, "10", 35)
    assert result.endswith(".10 (Unnamed)")
    assert len(result) < len(long_name)
    assert PrimeItems.tasker_root_elements["all_tasks"]["10"]["name"] == result


def test_a_short_scene_task_name_is_left_alone() -> None:
    """Most names already fit, and trimming one that does would lose real text."""
    _scene_with(_BUTTON)
    assert scenes.adjust_name_and_add_to_directory("Clicked", "10", 35) == "Clicked"


def test_a_scene_task_is_marked_as_such_in_the_directory() -> None:
    """The directory lists Tasks from everywhere.  "(Scene)" is what says this one is
    reached by tapping something rather than by a Profile firing.
    """
    _scene_with(_BUTTON)
    PrimeItems.program_arguments["directory"] = True
    scenes.adjust_name_and_add_to_directory("Clicked", "10", 35)
    assert any("Clicked (Scene)" in entry for entry in PrimeItems.directory_items["tasks"])


def test_asking_for_a_scene_this_project_does_not_have_finds_nothing() -> None:
    """The miss must not be recorded as a find: the caller uses that flag to decide
    whether to report the requested Scene as missing from the configuration.
    """
    PrimeItems.program_arguments["single_scene_name"] = "Nonexistent"
    assert not scenes.process_project_scenes(
        PrimeItems.tasker_root_elements["all_projects"]["Home"]["xml"],
        None,
        [],
    )
    assert PrimeItems.found_named_items["single_scene_found"] is False
