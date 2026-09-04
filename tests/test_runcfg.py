"""RunConfig Unit Tests

runcfg.RunConfig is the read-only half of PrimeItems pulled out into a value: the colors
and the runtime arguments for one run, frozen.  These tests are written the way tests of
core logic are supposed to be able to be written once the settings stop being a global --
build the settings the test wants, hand them to the code, assert on the answer -- and the
ones that check the code converted so far (nameattr, caveats, dirout's single-item
filters) deliberately never touch PrimeItems.program_arguments at all.  That is the whole
claim being made, so it is the thing worth asserting.

Two of them are guards rather than tests of behavior:

  * test_fields_match_initparg -- RunConfig's fields mirror
    initparg.initialize_runtime_arguments() one for one, defaults included.  Add a
    runtime argument and forget the field and this fails, which is the only thing
    stopping the two from drifting apart.
  * test_config_is_frozen -- a RunConfig cannot be written to.  If that ever stops being
    true, everything below it is worthless.
"""

from __future__ import annotations

import dataclasses
import xml.etree.ElementTree as ET

import pytest
from maptasker.src.caveats import display_caveats
from maptasker.src.dirout import check_profile, check_project, check_scene, check_task
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.lineout import LineOut
from maptasker.src.nameattr import add_name_attribute
from maptasker.src.primitem import PrimeItems, get_single_item_not_found, get_single_item_requested
from maptasker.src.runcfg import RunConfig, current_config, overridden_config

# One Project owning one Profile, one Task and one Scene -- enough for the directory
# filters, which decide by asking "is this the single item that was requested, or does it
# belong to the Project that is?".
_XML = """<TaskerData>
  <Project sr="proj0"><name>Home</name><pids>10</pids><tids>20</tids><scenes>Panel</scenes></Project>
  <Project sr="proj1"><name>Away</name><pids>11</pids><tids>21</tids></Project>
</TaskerData>"""


@pytest.fixture
def tasker_data() -> None:
    """Load the fixture XML into PrimeItems' lookup tables, and put them back after.

    The lookup tables are the mutable accumulator half of PrimeItems, which has
    deliberately NOT moved into RunConfig -- so a test of the directory filters still has
    to stand these up.  That is the remaining global, and naming it here is the point.
    """
    saved = PrimeItems.tasker_root_elements
    root = ET.fromstring(_XML)  # noqa: S314  (fixture text, defined in this file)
    projects = {project.find("name").text: {"xml": project} for project in root.findall("Project")}
    PrimeItems.tasker_root_elements = {
        "all_projects": projects,
        "all_profiles": {"10": {"name": "Morning"}, "11": {"name": "Evening"}},
        "all_tasks": {"20": {"name": "Wake"}, "21": {"name": "Sleep"}},
        "all_tasks_by_name": {"Wake": {"id": "20"}, "Sleep": {"id": "21"}},
        "all_scenes": {},
    }
    yield
    PrimeItems.tasker_root_elements = saved


# ##################################################################################### #
# The value itself                                                                       #
# ##################################################################################### #
def test_fields_match_initparg() -> None:
    """Every runtime argument has a field of the same name and the same default."""
    defaults = initialize_runtime_arguments()

    assert set(RunConfig.ARGUMENT_NAMES) == set(defaults)

    config = RunConfig()
    mismatched = {
        name: (defaults[name], getattr(config, name)) for name in defaults if getattr(config, name) != defaults[name]
    }
    assert mismatched == {}


def test_config_is_frozen() -> None:
    """A RunConfig cannot be written to -- the point of the whole exercise."""
    config = RunConfig(display_detail_level=3)

    with pytest.raises(dataclasses.FrozenInstanceError):
        config.display_detail_level = 5

    assert config.display_detail_level == 3


def test_with_changes_leaves_the_original_alone() -> None:
    """Deriving a changed config hands back a new one; whoever held the old one still
    sees what they were given."""
    original = RunConfig(display_detail_level=3, bold=False)
    changed = original.with_changes(display_detail_level=5, bold=True)

    assert (original.display_detail_level, original.bold) == (3, False)
    assert (changed.display_detail_level, changed.bold) == (5, True)


def test_with_changes_rejects_an_unknown_setting() -> None:
    """A misspelled setting name fails here, where program_arguments["..."] = ... would
    have accepted it and left the value where nothing reads it."""
    with pytest.raises(TypeError):
        RunConfig().with_changes(dispaly_detail_level=5)


def test_two_configs_coexist() -> None:
    """Two runs' settings can be held at once -- which is what processing two maps in one
    process needs, and what a single global cannot do."""
    dark = RunConfig(appearance_mode="dark", colors={"project_color": "White"})
    light = RunConfig(appearance_mode="light", colors={"project_color": "Black"})

    assert (dark.appearance_mode, dark.color("project_color")) == ("dark", "White")
    assert (light.appearance_mode, light.color("project_color")) == ("light", "Black")


def test_colors_cannot_be_written_through() -> None:
    """The colors table is read-only too, so a config handed to a function cannot have
    its colors edited out from under the caller."""
    config = RunConfig(colors={"project_color": "White"})

    with pytest.raises(TypeError):
        config.colors["project_color"] = "Red"

    # ...and the source dictionary is copied, not aliased.
    source = {"task_color": "Yellow"}
    config = RunConfig.from_dicts({}, source)
    source["task_color"] = "Green"
    assert config.color("task_color") == "Yellow"


def test_color_falls_back_to_the_default() -> None:
    """A color that is missing or empty gives the default rather than a KeyError."""
    config = RunConfig(colors={"task_color": ""})

    assert config.color("task_color", "Black") == "Black"
    assert config.color("no_such_color", "Black") == "Black"
    assert config.color("no_such_color") == ""


def test_from_dicts_ignores_settings_it_does_not_know() -> None:
    """A settings file written by an older MapTasker carries arguments that no longer
    exist; the program has always been expected to start anyway."""
    config = RunConfig.from_dicts({"bold": True, "an_argument_from_2021": "gone"})

    assert config.bold is True
    assert config.get("an_argument_from_2021", "absent") == "absent"
    assert "an_argument_from_2021" not in config.as_arguments()


def test_as_arguments_round_trips() -> None:
    """A config converted to the dictionary shape and back is the same config."""
    config = RunConfig(display_detail_level=2, single_task_name="Wake", colors={"task_color": "Yellow"})

    assert RunConfig.from_dicts(config.as_arguments(), config.as_colors()) == config


def test_as_arguments_is_a_fresh_copy() -> None:
    """Handing the arguments out as a dictionary does not hand out a way back in."""
    config = RunConfig(bold=True)
    arguments = config.as_arguments()
    arguments["bold"] = False

    assert config.bold is True


# ##################################################################################### #
# Snapshotting and overriding the settings that are still on PrimeItems                  #
# ##################################################################################### #
def test_current_config_is_a_snapshot() -> None:
    """A config handed out is not a live view: writing to the global afterwards does not
    reach back into it."""
    saved_arguments, saved_colors = PrimeItems.program_arguments, PrimeItems.colors_to_use
    try:
        PrimeItems.program_arguments = initialize_runtime_arguments()
        PrimeItems.program_arguments["display_detail_level"] = 2
        PrimeItems.colors_to_use = {"task_color": "Yellow"}

        config = current_config()
        PrimeItems.program_arguments["display_detail_level"] = 5
        PrimeItems.colors_to_use["task_color"] = "Green"

        assert config.display_detail_level == 2
        assert config.color("task_color") == "Yellow"
    finally:
        PrimeItems.program_arguments, PrimeItems.colors_to_use = saved_arguments, saved_colors


def test_overridden_config_restores_on_the_way_out() -> None:
    """The save-overwrite-restore dance, done once and correctly."""
    saved = PrimeItems.program_arguments
    try:
        PrimeItems.program_arguments = initialize_runtime_arguments()
        PrimeItems.program_arguments["directory"] = True

        with overridden_config(directory=False) as config:
            assert config.directory is False
            assert PrimeItems.program_arguments["directory"] is False

        assert PrimeItems.program_arguments["directory"] is True
    finally:
        PrimeItems.program_arguments = saved


def test_overridden_config_restores_when_the_block_raises() -> None:
    """Which the hand-written version of this dance did not manage."""
    saved = PrimeItems.program_arguments
    try:
        PrimeItems.program_arguments = initialize_runtime_arguments()
        PrimeItems.program_arguments["twisty"] = True

        blew_up = ValueError("boom")
        with pytest.raises(ValueError, match="boom"), overridden_config(twisty=False):
            raise blew_up

        assert PrimeItems.program_arguments["twisty"] is True
    finally:
        PrimeItems.program_arguments = saved


def test_overridden_config_keeps_other_changes_made_inside_it() -> None:
    """Only the overridden settings are put back.  The work these blocks wrap fills in
    single_project_name as it goes, and that has to survive the block."""
    saved = PrimeItems.program_arguments
    try:
        PrimeItems.program_arguments = initialize_runtime_arguments()
        PrimeItems.program_arguments["directory"] = True

        with overridden_config(directory=False):
            PrimeItems.program_arguments["single_project_name"] = "Home"

        assert PrimeItems.program_arguments["directory"] is True
        assert PrimeItems.program_arguments["single_project_name"] == "Home"
    finally:
        PrimeItems.program_arguments = saved


def test_overridden_config_does_not_invent_settings() -> None:
    """A partial program_arguments -- what most tests set up -- comes out of an override
    with exactly the keys it went in with."""
    saved = PrimeItems.program_arguments
    try:
        PrimeItems.program_arguments = {"language": "English"}

        with overridden_config(twisty=False):
            assert PrimeItems.program_arguments["twisty"] is False

        assert PrimeItems.program_arguments == {"language": "English"}
    finally:
        PrimeItems.program_arguments = saved


# ##################################################################################### #
# The converted code, exercised without the global                                       #
# ##################################################################################### #
@pytest.mark.parametrize(
    ("settings", "expected"),
    [
        ({}, "Wake"),
        ({"bold": True}, "<b>Wake</b>"),
        ({"italicize": True}, "<em>Wake</em>"),
        ({"highlight": True}, "<mark>Wake</mark>"),
        ({"underline": True}, "<u>Wake</u>"),
        (
            {"bold": True, "italicize": True, "highlight": True, "underline": True},
            "<u><mark><b><em>Wake</em></b></mark></u>",
        ),
    ],
)
def test_add_name_attribute_reads_only_its_config(settings: dict, expected: str) -> None:
    """Every styling combination, with no global set up and none torn down."""
    assert add_name_attribute("Wake", RunConfig(**settings)) == expected


def test_add_name_attribute_ignores_the_global() -> None:
    """The converted function answers from the config it was handed, even when the global
    says the opposite."""
    saved = PrimeItems.program_arguments
    try:
        PrimeItems.program_arguments = initialize_runtime_arguments()
        PrimeItems.program_arguments["bold"] = True

        assert add_name_attribute("Wake", RunConfig(bold=False)) == "Wake"
    finally:
        PrimeItems.program_arguments = saved


@pytest.mark.parametrize(
    ("detail_level", "preferences", "expected_caveats"),
    [
        (0, False, ["-d0"]),  # the unnamed-Task caveat only
        (1, False, ["mapped"]),  # the "not all actions are mapped" caveat
        (4, False, ["mapped", "Inactive variables"]),
        (4, True, ["mapped", "Inactive variables", "Google API key"]),
    ],
)
def test_display_caveats_follows_its_config(
    detail_level: int,
    preferences: bool,
    expected_caveats: list[str],
) -> None:
    """Which conditional caveats appear is decided by the config passed in."""
    saved_output = PrimeItems.output_lines
    saved_arguments = PrimeItems.program_arguments
    try:
        # translate_string and format_html still read the global; the caveat *selection*
        # under test does not, which is what these assertions are about.
        PrimeItems.program_arguments = initialize_runtime_arguments()
        PrimeItems.output_lines = LineOut()

        display_caveats(RunConfig(display_detail_level=detail_level, preferences=preferences))
        written = "".join(PrimeItems.output_lines.output_lines)

        for caveat in expected_caveats:
            assert caveat in written
        if "-d0" not in expected_caveats:
            assert "-d0" not in written
        if "Google API key" not in expected_caveats:
            assert "Google API key" not in written
    finally:
        PrimeItems.output_lines = saved_output
        PrimeItems.program_arguments = saved_arguments


def test_directory_filters_follow_their_config(tasker_data: None) -> None:
    """The single-item directory filters decide from the config they are handed."""
    everything = RunConfig()
    assert check_project(("Home", "Home"), everything) is True
    assert check_profile(("Morning", "Morning"), everything) is True
    assert check_task(("Wake", "Wake"), everything) is True

    # Asking for one Project links that Project and no other.
    one_project = RunConfig(single_project_name="Home")
    assert check_project(("Home", "Home"), one_project) is True
    assert check_project(("Away", "Away"), one_project) is False

    # Asking for one Task links that Task, and no Projects or Profiles at all.
    one_task = RunConfig(single_task_name="Wake")
    assert check_task(("Wake", "Wake"), one_task) is True
    assert check_task(("Sleep", "Sleep"), one_task) is False
    assert check_project(("Home", "Home"), one_task) is False
    assert check_profile(("Morning", "Morning"), one_task) is False

    # Asking for one Scene links only the Project that owns it.
    one_scene = RunConfig(single_scene_name="Panel")
    assert check_project(("Home", "Home"), one_scene) is True
    assert check_project(("Away", "Away"), one_scene) is False
    assert check_scene(("Panel", "Panel"), one_scene) is True
    assert check_scene(("Other", "Other"), one_scene) is False


def test_directory_filters_ignore_the_global(tasker_data: None) -> None:
    """Same filters, with the global asking for something else entirely."""
    saved = PrimeItems.program_arguments
    try:
        PrimeItems.program_arguments = initialize_runtime_arguments()
        PrimeItems.program_arguments["single_project_name"] = "Away"

        assert check_project(("Home", "Home"), RunConfig(single_project_name="Home")) is True
        assert check_project(("Away", "Away"), RunConfig(single_project_name="Home")) is False
    finally:
        PrimeItems.program_arguments = saved


# ##################################################################################### #
# The single-item helpers, answered from a config                                        #
# ##################################################################################### #
def test_single_item_helpers_read_the_given_config() -> None:
    """get_single_item_requested and friends answer from a config when given one."""
    saved_arguments = PrimeItems.program_arguments
    saved_found = PrimeItems.found_named_items
    try:
        PrimeItems.program_arguments = initialize_runtime_arguments()
        PrimeItems.found_named_items = {"single_task_found": False}

        config = RunConfig(single_task_name="Wake")
        assert get_single_item_requested(config) == ("Task", "Wake")
        assert get_single_item_not_found(config) == ("Task", "Wake")

        PrimeItems.found_named_items["single_task_found"] = True
        assert get_single_item_not_found(config) == ("", "")

        # Left out, they still read the global -- which asked for nothing.
        assert get_single_item_requested() == ("", "")
    finally:
        PrimeItems.program_arguments = saved_arguments
        PrimeItems.found_named_items = saved_found
