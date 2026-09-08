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
import re
import xml.etree.ElementTree as ET

import pytest
from maptasker.src import proginit, scenes, taskerd, varxref
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
# The same element with the arguments Tasker really writes, so its output line is the full
# one -- name, value and the rest -- rather than the stub a bare <Str> produces.
_TEXT_WITH_VARIABLE = (
    '<TextElement sr="txt1"><Str sr="arg0" ve="3">Notes</Str>'
    '<Str sr="arg1" ve="3">%NotesNobodySets</Str></TextElement>'
)


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


# ##################################################################################
# Jump anchors for a Scene's elements
#
# A health check finding about a variable a Scene reads is a finding about ONE element of
# that Scene -- "%Notes is read and nothing sets it" is about the Text element showing it,
# not about a Scene that may hold fifty others.  Clicking it used to land on the Scene's
# own line and leave the user to find the element among the rest of the Scene's output.
#
# Two halves have to agree for the click to land: varxref names the element it found the
# variable in, and the Map writes the id that name points at.  The last test here is the
# one that matters -- it holds the two halves against each other.
# ##################################################################################
def _anchors_written() -> list[str]:
    """Every jump anchor id the Scene output written so far carries."""
    return re.findall(r'<a id="([^"]+)" class="mt-anchor"', _output())


def _v2_scene_with(layout: dict) -> None:
    """The Panel Scene as a Version 2 one: its components in a gzipped <lj>, loaded."""
    PrimeItems.xml_root = ET.fromstring(  # noqa: S314  (fixture text, built in this file)
        '<TaskerData sr="" dvi="1" tv="6.3.13">'
        '<Project sr="proj0"><name>Home</name><scenes>Panel</scenes></Project>'
        '<Scene sr="scene0"><nme>Panel</nme><heightPort>800</heightPort><widthPort>480</widthPort>'
        f"<lj>{_gzipped_json(layout)}</lj></Scene>"
        "</TaskerData>",
    )
    taskerd.build_tasker_tables()


def _render_scene(elements: str) -> None:
    """Output the Panel Scene the way a Map run does, with its elements shown in full.

    The argument specs are loaded because a Scene's Properties are output whatever the
    detail level, and rendering an element's arguments needs them (actargs).
    """
    _scene_with(elements)
    proginit.load_arg_specs()
    PrimeItems.program_arguments["display_detail_level"] = 5
    scenes.process_scene("Panel", [], None, 0)


def test_each_scene_element_carries_its_own_jump_anchor() -> None:
    """Tasker's internal name for the element, which is already what the Map prints as
    "Internal Name=" -- and what tells two Text elements of one Scene apart.
    """
    _render_scene(_BUTTON + _TEXT)

    written = _anchors_written()
    assert "mt-scene-Panel-ebut1" in written
    assert "mt-scene-Panel-etxt1" in written


def test_a_nested_element_is_anchored_under_the_one_that_holds_it() -> None:
    """Tasker names every element's backing rectangle "background", so the name alone
    cannot say which element's it is -- and a jump would land on the first of them.
    """
    holder = (
        '<TextElement sr="txt1"><Str>Outer</Str>'
        '<RectElement sr="background"><Str>Behind</Str></RectElement>'
        "</TextElement>"
        '<TextElement sr="txt2"><Str>Other</Str>'
        '<RectElement sr="background"><Str>Behind</Str></RectElement>'
        "</TextElement>"
    )
    _render_scene(holder)

    written = _anchors_written()
    assert "mt-scene-Panel-etxt1%2Fbackground" in written
    assert "mt-scene-Panel-etxt2%2Fbackground" in written


def test_a_scene_element_finding_lands_on_that_element() -> None:
    """The whole point: the id varxref points a NEVER-SET finding at is an id the Map
    actually wrote, and it is the element's own, not the Scene's.
    """
    _render_scene(_TEXT_WITH_VARIABLE)

    finding = next(
        suspect for suspect in varxref.suspects(varxref.build_index()) if suspect.subject == "%NotesNobodySets"
    )
    place = finding.places[0]
    assert place.label.endswith("Scene 'Panel' element Text 'Notes'")
    assert place.anchor == "mt-scene-Panel-etxt1"

    # And it lands on the line that holds the variable, not merely somewhere in the Scene.
    output = _output()
    assert f'<a id="{place.anchor}" class="mt-anchor"' in output
    landed_on = output[output.index(f'<a id="{place.anchor}"') :][:400]
    assert "%NotesNobodySets" in landed_on


def test_the_line_an_element_is_anchored_on_is_one_element_of_its_own() -> None:
    """The half of the jump that lives in the HTML, and the one that went wrong first.

    An arguments line opens two colour spans and used to close one, leaving the outer span
    open for the rest of the file -- so the element a click landed on ran to 306 lines, and
    the jump, which scrolls what it lands on to the middle of the window, arrived 150 lines
    past the line the finding named.  Nothing about the anchor said so: it was on the right
    line, pointing at an element that had swallowed everything after it.
    """
    _render_scene(_TEXT_WITH_VARIABLE)
    lines = PrimeItems.output_lines.output_lines
    position = next(index for index, line in enumerate(lines) if "UI for" in line)

    assert lines[position].count("<span") == lines[position].count("</span>")
    # And the colour it was leaking is put back, since the lines below it -- the names of
    # the Tasks a Scene's elements fire -- have always taken their colour from it.
    assert lines[position + 1].strip() == '<span class="scene_color">'


def test_an_element_is_still_anchored_where_its_arguments_are_not_shown() -> None:
    """Below the top detail level an element gets its heading line and nothing else, so
    that is the line to land on -- an element with no anchor at all could not be reached.
    """
    _scene_with(_TEXT)
    PrimeItems.program_arguments["display_detail_level"] = 3
    scenes.process_scene("Panel", [], None, 0)

    output = _output()
    assert '<a id="mt-scene-Panel-etxt1" class="mt-anchor"' in output
    assert "'Label' Element of type Text" in output[output.index("mt-scene-Panel-etxt1") :]


# A Version 2 Scene keeps its components in the gzipped JSON of <lj> instead of in child
# elements, and the Map writes each component out one property per line -- so unlike a
# Legacy element, there is an exact line for a finding to land on.
_V2_LAYOUT = {
    "root": {
        "type": "Column",
        "id": "root_column",
        "children": [
            {"type": "Text", "id": "title_text", "text": "%V2NobodySets", "textSize": "22"},
            {"type": "Text", "id": "other_text", "text": "%V2AlsoNobody"},
        ],
    },
}


def test_each_v2_component_property_holding_a_variable_carries_its_own_jump_anchor() -> None:
    """A component is addressed by its position in the tree -- it has no "sr" name to be
    keyed by -- and the property is part of that address, because the property is the line.
    """
    _v2_scene_with(_V2_LAYOUT)
    scenes.process_scene("Panel", [], None, 0)

    written = _anchors_written()
    assert "mt-scene-Panel-echildren%2F0%23text" in written  # the first child's text
    assert "mt-scene-Panel-echildren%2F1%23text" in written  # and the second's, told apart


def test_a_v2_property_with_no_variable_in_it_is_not_anchored() -> None:
    """Only a property a finding could name is worth an id.  A component is written out one
    property per line, so anchoring all of them put thousands of ids in the Map for the few
    hundred that are ever pointed at.

    The child slot is held out for a second reason: its value is the whole subtree below
    it, so a "%" anywhere in the Scene would otherwise anchor the "children:" line too.
    """
    _v2_scene_with(_V2_LAYOUT)
    scenes.process_scene("Panel", [], None, 0)

    written = _anchors_written()
    assert "mt-scene-Panel-echildren%2F0%23textSize" not in written  # plain "22"
    assert "mt-scene-Panel-eroot%23type" not in written  # plain "Column"
    assert "mt-scene-Panel-eroot%23children" not in written  # the slot holding both Texts
    assert len(written) == 2


def test_a_v2_component_finding_lands_on_the_property_that_holds_the_variable() -> None:
    """The Version 2 half of the contract: the id varxref points the finding at is an id
    the Map wrote, on the line that shows the variable.
    """
    _v2_scene_with(_V2_LAYOUT)
    scenes.process_scene("Panel", [], None, 0)

    finding = next(
        suspect for suspect in varxref.suspects(varxref.build_index()) if suspect.subject == "%V2NobodySets"
    )
    place = finding.places[0]
    assert place.label.endswith("Scene 'Panel' component Text '%V2NobodySets' text")
    assert place.anchor == "mt-scene-Panel-echildren%2F0%23text"

    output = _output()
    assert f'<a id="{place.anchor}" class="mt-anchor"' in output
    landed_on = output[output.index(f'<a id="{place.anchor}"') :][:300]
    assert "%V2NobodySets" in landed_on


def test_a_v2_layout_that_will_not_decode_writes_no_anchors() -> None:
    """A corrupt <lj> is reported and moved past.  Anchors for components nobody could
    read would be ids pointing at lines that were never written.
    """
    PrimeItems.xml_root = ET.fromstring(  # noqa: S314  (fixture text, built in this file)
        '<TaskerData sr="" dvi="1" tv="6.3.13">'
        '<Scene sr="scene0"><nme>Panel</nme><lj>not valid at all @@@</lj></Scene>'
        "</TaskerData>",
    )
    taskerd.build_tasker_tables()
    scenes.process_scene("Panel", [], None, 0)

    assert "could not be processed" in _output()
    assert not _anchors_written()
