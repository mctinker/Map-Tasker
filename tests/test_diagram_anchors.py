"""MapTasker Diagram object-anchor Unit Tests

The Diagram carries no ids -- it is plain text -- so a jump into it is addressed by the
LINE an object was drawn on, recorded while the diagram is built and carried through every
step that moves a line afterwards (see the note above flatten_with_quotes in diagram.py).

These tests exercise that recording in isolation: the buffered noting and flushing, the
remaps, and the resolution of a name to the exact span of the rendered line.  Standing up a
real diagram would exercise the drawing instead, which is not what is at risk here -- what
is at risk is a row that quietly stops meaning the line it used to mean.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET

import pytest
from maptasker.src import diagram, mapjump, taskerd
from maptasker.src.mapjump import PROFILE, PROJECT, TASK, Target, diagram_placement
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import DIAGRAM_FILE

_PROFILE = Target(kind=PROFILE, key="10", name="Wake Up")
_OTHER_PROFILE = Target(kind=PROFILE, key="11", name="Wind Down")
_TASK = Target(kind=TASK, key="20", name="Backup")
_TWIN = Target(kind=TASK, key="21", name="Backup")  # Same name, different Task.


@pytest.fixture(autouse=True)
def _clean_slate() -> None:
    """Each test starts with an empty diagram and nothing noted against it."""
    PrimeItems.netmap_output = []
    PrimeItems.diagram_object_seeds = {}
    PrimeItems.diagram_anchors = {}
    diagram._pending_boxes.clear()  # noqa: SLF001
    diagram._pending_tasks.clear()  # noqa: SLF001


# ##################################################################################
# Noting an object against a buffer, and fixing it when the buffer is flushed.
# ##################################################################################
def test_a_box_lands_on_the_middle_of_its_three_lines() -> None:
    """A box is drawn as a top, a name and a bottom; only the middle line names it."""
    diagram.add_output_line("header")
    diagram._note_box(_PROFILE, "║ Wake Up")  # noqa: SLF001
    diagram._flush_boxes(["top", "║ Wake Up ║", "bottom"])  # noqa: SLF001

    row, _snippet = PrimeItems.diagram_object_seeds[_PROFILE.anchor]
    assert row == 2
    assert PrimeItems.netmap_output[row] == "║ Wake Up ║"


def test_several_boxes_on_one_row_all_land_on_it() -> None:
    """Six Profiles side by side share the line, and each is recorded on it."""
    diagram._note_box(_PROFILE, "║ Wake Up")  # noqa: SLF001
    diagram._note_box(_OTHER_PROFILE, "║ Wind Down")  # noqa: SLF001
    diagram._flush_boxes(["top", "║ Wake Up ║ ║ Wind Down ║", "bottom"])  # noqa: SLF001

    assert PrimeItems.diagram_object_seeds[_PROFILE.anchor][0] == 1
    assert PrimeItems.diagram_object_seeds[_OTHER_PROFILE.anchor][0] == 1


def test_a_flush_clears_what_it_fixed() -> None:
    """Notes belong to the buffer being flushed, never to the next one."""
    diagram._note_box(_PROFILE, "║ Wake Up")  # noqa: SLF001
    diagram._flush_boxes(["top", "║ Wake Up ║", "bottom"])  # noqa: SLF001
    diagram._note_box(_OTHER_PROFILE, "║ Wind Down")  # noqa: SLF001
    diagram._flush_boxes(["top", "║ Wind Down ║", "bottom"])  # noqa: SLF001

    assert PrimeItems.diagram_object_seeds[_PROFILE.anchor][0] == 1
    assert PrimeItems.diagram_object_seeds[_OTHER_PROFILE.anchor][0] == 4


def test_task_lines_keep_their_place_within_the_buffer() -> None:
    """A Task's row is where its line sits in the run of Task lines, not where it was noted."""
    diagram.add_output_line("header")
    buffer = ["└─ Backup", "", "└─ Restore"]
    diagram._note_task(0, _TASK, "└─ Backup")  # noqa: SLF001
    diagram._note_task(2, _TWIN, "└─ Restore")  # noqa: SLF001
    diagram._flush_tasks(buffer)  # noqa: SLF001

    assert PrimeItems.diagram_object_seeds[_TASK.anchor][0] == 1
    assert PrimeItems.diagram_object_seeds[_TWIN.anchor][0] == 3


def test_two_tasks_of_one_name_are_recorded_separately() -> None:
    """The whole point of recording positions rather than matching text."""
    diagram._note_task(0, _TASK, "└─ Backup")  # noqa: SLF001
    diagram._note_task(1, _TWIN, "└─ Backup")  # noqa: SLF001
    diagram._flush_tasks(["└─ Backup", "└─ Backup"])  # noqa: SLF001

    assert PrimeItems.diagram_object_seeds[_TASK.anchor][0] == 0
    assert PrimeItems.diagram_object_seeds[_TWIN.anchor][0] == 1


def test_the_first_drawing_of_a_task_is_the_one_kept() -> None:
    """A Task run by two Profiles is drawn twice; a jump goes to the first, as in the Map."""
    diagram._note_task(0, _TASK, "└─ Backup")  # noqa: SLF001
    diagram._flush_tasks(["└─ Backup"])  # noqa: SLF001
    diagram._note_task(0, _TASK, "└─ Backup")  # noqa: SLF001
    diagram._flush_tasks(["└─ Backup"])  # noqa: SLF001

    assert PrimeItems.diagram_object_seeds[_TASK.anchor][0] == 0


# ##################################################################################
# The remaps: every step that moves a line has to move what is on it.
# ##################################################################################
def test_a_remap_moves_every_object_with_its_line() -> None:
    """add_blanks_above_called_tasks and the bar sweep both shift rows under the objects."""
    PrimeItems.diagram_object_seeds = {"a": (5, "x"), "b": (9, "y")}
    diagram._remap_object_seeds({5: 12, 9: 20})  # noqa: SLF001

    assert PrimeItems.diagram_object_seeds == {"a": (12, "x"), "b": (20, "y")}


def test_a_remap_drops_an_object_whose_line_is_gone() -> None:
    """A row with no new home was swept away, and pointing at it would point at a stranger."""
    PrimeItems.diagram_object_seeds = {"a": (5, "x"), "b": (9, "y")}
    diagram._remap_object_seeds({5: 5})  # noqa: SLF001

    assert set(PrimeItems.diagram_object_seeds) == {"a"}


def test_the_view_limit_cut_drops_what_is_past_it() -> None:
    """A diagram cut short does not hold the objects it never got to."""
    PrimeItems.diagram_object_seeds = {"a": (5, "x"), "b": (40, "y")}
    diagram._keep_object_seeds_before(40)  # noqa: SLF001

    assert set(PrimeItems.diagram_object_seeds) == {"a"}


# ##################################################################################
# Resolving a name to the span of the line it was drawn on.
# ##################################################################################
def test_a_box_is_placed_as_the_whole_box() -> None:
    """A Profile is highlighted as the box the eye reads it as, walls included."""
    line = "     ║ Project: Home ║"
    column, length = diagram._place(line, "║ Project: Home", boxed=True)  # noqa: SLF001

    assert line[column : column + length] == "║ Project: Home ║"


def test_a_task_is_placed_as_its_drawn_name() -> None:
    """A Task line's name ends where the recorded text ends -- there is no box to close."""
    line = "        └─ Backup [Calls ──▶ Restore]"
    column, length = diagram._place(line, "└─ Backup", boxed=False)  # noqa: SLF001

    assert line[column : column + length] == "└─ Backup"


def test_a_column_is_counted_the_way_a_browser_counts_it() -> None:
    """An emoji is one character to Python and two to JavaScript.

    A column measured in code points would be one short per emoji to the left of it, and
    the highlight would sit one character off for every Task named with one -- which real
    configurations do.
    """
    line = "\U0001f3d8\U0001f3d8 └─ Backup"  # Two astral characters before the name.
    column, length = diagram._place(line, "└─ Backup", boxed=False)  # noqa: SLF001

    # Python would say 3; the browser, counting UTF-16 code units, says 5.
    assert column == 5
    assert length == 9  # The name itself is all BMP, so its length is the same either way.
    # And slicing the line the way the browser would gets the name back.
    units = line.encode("utf-16-le")
    assert units[column * 2 : (column + length) * 2].decode("utf-16-le") == "└─ Backup"


def test_a_name_that_cannot_be_placed_answers_with_the_whole_line() -> None:
    """remove_icon can rub out a blank inside a name to keep an arrowed line aligned.

    The line is still the right one to be taken to, so (0, 0) is returned and the Diagram
    view reads it as "highlight all of it" rather than as a failure.
    """
    assert diagram._place("nothing like it here", "└─ Backup", boxed=False) == (0, 0)  # noqa: SLF001


def test_an_unclosed_box_still_places_the_name() -> None:
    """A box the line is too short to close is placed as the name alone, not as the rest of the line."""
    column, length = diagram._place("  ║ Wake Up", "║ Wake Up", boxed=True)  # noqa: SLF001

    assert (column, length) == (2, 9)


# ##################################################################################
# What the Diagram view asks for.
# ##################################################################################
def test_a_placement_is_found_by_anchor() -> None:
    """The Diagram view looks the object up by the same anchor id the Map puts in the page."""
    PrimeItems.diagram_anchors = {_TASK.anchor: (12, 8, 9)}

    assert diagram_placement(_TASK) == (12, 8, 9)


def test_an_action_is_answered_by_its_task() -> None:
    """The Diagram draws no actions, so 'action 5 of Task 20' lands on Task 20's own line."""
    PrimeItems.diagram_anchors = {_TASK.anchor: (12, 8, 9)}

    assert diagram_placement(_TASK.at_action(5)) == (12, 8, 9)


def test_an_object_the_diagram_never_drew_has_no_placement() -> None:
    """A Diagram narrowed to one Project holds nothing outside it -- the caller falls back."""
    PrimeItems.diagram_anchors = {_TASK.anchor: (12, 8, 9)}

    assert diagram_placement(_TWIN) is None


def test_no_diagram_at_all_has_no_placements() -> None:
    """Before any Diagram is built there is nothing to jump into, and nothing to raise about."""
    PrimeItems.diagram_anchors = {}

    assert diagram_placement(_TASK) is None


# ##################################################################################
# End to end: a real diagram, and where its objects actually ended up in it.
# ##################################################################################
# One Project, three Profiles and three Tasks, two of which share a name -- the case the
# recording exists for, and the one matching the drawn text can never answer.  The first
# 'Backup' calls 'Restore', so the diagram draws an arrow between them; drawing one inserts
# blank lines above the called Task, which moves every line under it and is the first of
# the four remaps an anchor has to survive.
_DIAGRAM_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2">
    <name>Home</name><pids>10,11,12</pids><tids>20,21,22</tids><scenes>Menu</scenes>
  </Project>
  <Profile sr="prof10" ve="2"><id>10</id><nme>Wake Up</nme><mid0>20</mid0></Profile>
  <Profile sr="prof11" ve="2"><id>11</id><nme>Wind Down</nme><mid0>21</mid0></Profile>
  <Profile sr="prof12" ve="2"><id>12</id><nme>Nightly</nme><mid0>22</mid0></Profile>
  <Task sr="task20" ve="2"><id>20</id><nme>Backup</nme><Action sr="act0"><code>548</code></Action></Task>
  <Task sr="task21" ve="2"><id>21</id><nme>Backup</nme><Action sr="act0"><code>548</code></Action></Task>
  <Task sr="task22" ve="2"><id>22</id><nme>Restore</nme><Action sr="act0"><code>548</code></Action></Task>
  <Scene sr="scene0" ve="2"><nme>Menu</nme></Scene>
</TaskerData>"""


class _Output:
    """The output collector network_map writes its ruler line into, and nothing else here reads."""

    output_lines: list = []  # noqa: RUF012

    def add_line_to_output(self, *_args: object, **_kwargs: object) -> None:
        """Swallow the line -- this test is about the diagram file, not the Map."""


def _drawn(tmp_path: object) -> list[str]:
    """Build a real diagram from the fixture and hand back the file it wrote, line by line."""
    root = ET.fromstring(_DIAGRAM_XML)  # noqa: S314  (fixture text, defined in this file)
    PrimeItems.xml_root = root
    PrimeItems.slash = "/"
    PrimeItems.output_lines = _Output()
    PrimeItems.program_arguments = {
        "language": "English",
        "profiles_per_line": 6,
        "debug": False,
        "pretty": False,
        "directory": False,
        "guiview": False,
        "gui": False,
        "view_limit": 10000,
        "display_detail_level": 3,
    }
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
    # setdefault, not assignment: this table keeps one entry per name, which is exactly why
    # the anchors take a Task's id from its own element instead of from here.
    tables["all_tasks_by_name"] = {}
    for key, task in tables["all_tasks"].items():
        tables["all_tasks_by_name"].setdefault(task["name"], {"xml": task["xml"], "id": key})
    PrimeItems.tasker_root_elements = tables

    # What outline.py's own pass fills in, and what makes the diagram draw a call arrow.
    tables["all_tasks_by_name"]["Backup"]["call_tasks"] = ["Restore"]
    tables["all_tasks_by_name"]["Restore"]["called_by"] = ["Backup"]

    network = {
        "Home": {
            "Wake Up": [{"xml": tables["all_tasks"]["20"]["xml"], "name": "Backup"}],
            "Wind Down": [{"xml": tables["all_tasks"]["21"]["xml"], "name": "Backup"}],
            "Nightly": [{"xml": tables["all_tasks"]["22"]["xml"], "name": "Restore"}],
            "Scenes": ["Menu"],
        },
    }

    here = os.getcwd()
    os.chdir(tmp_path)
    try:
        diagram.network_map(network)
        with open(DIAGRAM_FILE, encoding="utf-8") as written:
            return written.read().split("\n")
    finally:
        os.chdir(here)


def _span(lines: list[str], placement: tuple[int, int, int]) -> str:
    """The text a placement points at, sliced the way the browser slices it.

    Through UTF-16 deliberately: a placement that is only right when read as code points is
    a placement the Diagram view will get wrong, and slicing it in Python would hide that.
    """
    row, column, length = placement
    units = lines[row].encode("utf-16-le")
    return units[column * 2 : (column + length) * 2].decode("utf-16-le")


@pytest.fixture
def drawn(tmp_path: object) -> list[str]:
    """The diagram the fixture draws, as its rendered lines."""
    return _drawn(tmp_path)


def test_every_object_in_a_drawn_diagram_is_placed(drawn: list[str]) -> None:
    """Nothing is recorded that cannot be found again on the line it claims."""
    assert PrimeItems.diagram_anchors
    for anchor, placement in PrimeItems.diagram_anchors.items():
        assert placement[0] < len(drawn), f"{anchor} points past the end of the diagram"
        assert placement[2] > 0, f"{anchor} could not be placed on line {placement[0]}"


def test_the_project_profiles_and_scene_land_on_their_boxes(drawn: list[str]) -> None:
    """Each is highlighted as the whole box, walls included."""
    placements = PrimeItems.diagram_anchors
    assert _span(drawn, placements[Target(kind=PROJECT, key="Home", name="Home").anchor]) == "║ Project: Home ║"
    assert _span(drawn, placements[Target(kind=PROFILE, key="10", name="Wake Up").anchor]) == "║ Wake Up ║"
    assert _span(drawn, placements[Target(kind=PROFILE, key="12", name="Nightly").anchor]) == "║ Nightly ║"
    assert _span(drawn, placements["mt-scene-Menu"]) == "║ Menu ║"


def test_two_tasks_of_one_name_land_on_their_own_lines(drawn: list[str]) -> None:
    """The whole reason for recording positions instead of matching the drawn text.

    Both Tasks are called 'Backup' and both are drawn; a search for the text finds the
    first one twice, while the recorded lines tell them apart.
    """
    first = PrimeItems.diagram_anchors[Target(kind=TASK, key="20", name="Backup").anchor]
    second = PrimeItems.diagram_anchors[Target(kind=TASK, key="21", name="Backup").anchor]

    assert first[0] != second[0]
    assert _span(drawn, first) == "└─ Backup"
    assert _span(drawn, second) == "└─ Backup"


def test_a_task_below_the_call_arrows_survives_the_lines_they_inserted(drawn: list[str]) -> None:
    """'Restore' is drawn, then pushed down by the blanks the arrow to it needs.

    This is the remap that has no second chance: the row was recorded before
    add_blanks_above_called_tasks ran, and every step after it is measured from here.
    """
    placement = PrimeItems.diagram_anchors[Target(kind=TASK, key="22", name="Restore").anchor]

    assert _span(drawn, placement) == "└─ Restore"
    # And it really did move -- the fixture's arrow is what puts the blank lines in.
    assert placement[0] > drawn.index("     ║ Project: Home ║") + 6


def test_an_action_is_taken_to_its_tasks_line(drawn: list[str]) -> None:
    """The Diagram draws no actions, so an action's Target lands on the Task that holds it."""
    task = Target(kind=TASK, key="21", name="Backup")

    assert diagram_placement(task.at_action(4)) == PrimeItems.diagram_anchors[task.anchor]
    assert _span(drawn, diagram_placement(task.at_action(4))) == "└─ Backup"


# ##################################################################################
# The script the Diagram view is handed.
# ##################################################################################
def test_the_jump_script_escapes_its_newline() -> None:
    """The emitted JavaScript must ask for a newline, not contain one.

    The script is built by an f-string, so a single backslash-n in the source is a Python
    escape: it reaches the browser as a real line break inside a JavaScript string literal,
    which is a syntax error, and the whole jump dies in the console with nothing said on
    the Python side.  It shipped that way once.
    """
    script = mapjump.diagram_jump_js("c1", ["║ Wake Up ║"], (5, 2, 11))

    assert '"\\n"' in script
    # And the broken shape itself: a quote, a real line break, a quote.
    assert '"\n"' not in script


def test_the_jump_script_carries_the_placement_it_was_given() -> None:
    """The line, column and length reach the browser as the numbers they are."""
    script = mapjump.diagram_jump_js("c1", [], (12, 8, 9))

    assert "[12, 8, 9]" in script


def test_the_jump_script_says_so_when_there_is_no_placement() -> None:
    """Without one, the script falls back to matching the drawn text."""
    script = mapjump.diagram_jump_js("c1", ["║ Wake Up ║"])

    assert "const placement = null;" in script
