"""runcli: how the parsed command line becomes the settings a run uses.

The parser (see parsearg) hands back a namespace in which a value may be a one-item list
(nargs=1), a plain value, or None for "not given", and the GUI and the settings file feed the
same settings from the other side.  What matters here is the order things are applied in and
what is NOT done: a boolean option can only turn a setting on, so a saved one cannot be
switched off by leaving it out; a view limit not given on the command line leaves the one the
settings file restored; and a command line that is inconsistent is corrected with a warning
rather than run as asked.

The namespace is a plain object here, and the things that would end the process or open a
window (version banner, color help, the GUI) are replaced with functions that record the call.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest
from maptasker.src import runcli
from maptasker.src.core import console
from maptasker.src.core.config import DEFAULT_DISPLAY_DETAIL_LEVEL
from maptasker.src.core.initparg import initialize_runtime_arguments
from maptasker.src.core.primitem import RunState
from maptasker.src.core.sysconst import TYPES_OF_COLORS


class _Stop(Exception):  # noqa: N818
    """Stands in for exit_program, which ends the run."""


@pytest.fixture
def state() -> RunState:
    run = RunState()
    run.program_arguments = initialize_runtime_arguments()
    return run


def _args(**given: object) -> SimpleNamespace:
    """A parsed command line with nothing asked for, plus whatever the test says was."""
    values: dict[str, object] = {
        "e": False,
        "v": False,
        "ch": False,
        "g": False,
        "debug": False,
        "detail": None,
        "names": "",
        "appearance": None,
        "i": None,
        "font": None,
        "file": None,
        "outdir": None,
        "view_limit": None,
        "project": None,
        "profile": None,
        "task": None,
        "scene": None,
        "android_ipaddr": "",
        "android_port": "",
        "android_file": "",
        "conditions": False,
        "directory": False,
        "pretty": False,
        "preferences": False,
        "reset": False,
        "runtime": False,
        "taskernet": False,
        "twisty": False,
        "guiview": False,
    }
    values.update({f"c{key}": None for key in TYPES_OF_COLORS})
    values.update(given)
    return SimpleNamespace(**values)


@pytest.fixture
def no_exit(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """exit_program raises instead of ending the test run; the codes it was given are recorded."""
    codes: list[int] = []

    def stop(code: int = 0) -> None:
        codes.append(code)
        raise _Stop

    monkeypatch.setattr(runcli, "exit_program", stop)
    return codes


# ##################################################################################
# Values that may be a list.
# ##################################################################################
@pytest.mark.parametrize(
    ("given", "expected"),
    [([6], 6), (["6"], 6), (4, 4), ("5", 5), ([0], 0), (None, None), ([], []), ("", "")],
)
def test_a_number_may_come_as_a_list_a_value_or_nothing(given: object, expected: object) -> None:
    assert runcli.get_arg_if_in_list(SimpleNamespace(i=given), "i") == expected


def test_a_zero_in_a_list_is_taken_as_asked_for() -> None:
    """The list is truthy though its number is not: -i 0 means no indentation, not 'not given'."""
    assert runcli.get_arg_if_in_list(SimpleNamespace(i=[0]), "i") == 0


# ##################################################################################
# Booleans, names and detail.
# ##################################################################################
def test_a_boolean_option_turns_its_setting_on_and_cannot_turn_it_off(state: RunState) -> None:
    state.program_arguments.twisty = True
    state.program_arguments.debug = True

    runcli.get_and_set_booleans(_args(conditions=True, pretty=True, twisty=False), state=state)

    assert state.program_arguments.conditions is True
    assert state.program_arguments.pretty is True
    assert state.program_arguments.twisty is True  # Saved on; leaving it off the command line leaves it on.
    assert state.program_arguments.directory is False


def test_a_namespace_missing_an_option_is_not_an_error(state: RunState) -> None:
    runcli.get_and_set_booleans(SimpleNamespace(conditions=True), state=state)

    assert state.program_arguments.conditions is True
    assert state.program_arguments.pretty is False


@pytest.mark.parametrize(
    ("given", "attributes"),
    [
        ("bold underline", {"bold", "underline"}),
        (["italicize", "highlight"], {"italicize", "highlight"}),
        ("bold nonsense", {"bold"}),
        ("", set()),
    ],
)
def test_name_attributes_are_turned_on_one_by_one_and_junk_is_ignored(
    state: RunState, given: object, attributes: set[str]
) -> None:
    runcli.get_name_attributes(given, state=state)

    turned_on = {name for name in ("bold", "highlight", "underline", "italicize") if state.program_arguments[name]}
    assert turned_on == attributes


@pytest.mark.parametrize(("given", "expected"), [(2, 2), ([4], 4), (0, 0), ([0], 0), (None, 5)])
def test_the_detail_level_comes_as_a_number_or_a_list_or_not_at_all(
    state: RunState, given: object, expected: int
) -> None:
    state.program_arguments.display_detail_level = 5

    runcli.get_the_other_arguments(_args(detail=given), state=state)

    assert state.program_arguments.display_detail_level == expected


def test_everything_turns_on_what_it_stands_for(state: RunState) -> None:
    state.program_arguments.display_detail_level = 1

    runcli.set_everything(state.program_arguments)

    arguments = state.program_arguments
    assert arguments.display_detail_level == DEFAULT_DISPLAY_DETAIL_LEVEL
    assert all(
        getattr(arguments, name) is True
        for name in ("conditions", "preferences", "directory", "taskernet", "runtime", "pretty")
    )
    assert arguments.twisty is False  # -twisty is its own choice, and exclusive with -e.


def test_single_names_are_the_first_of_each_list(state: RunState) -> None:
    runcli.get_single_name(
        state.program_arguments, _args(project=["Home"], profile=["Morning"], task=["Noisy"], scene=["Dash"])
    )

    arguments = state.program_arguments
    assert (arguments.single_project_name, arguments.single_profile_name) == ("Home", "Morning")
    assert (arguments.single_task_name, arguments.single_scene_name) == ("Noisy", "Dash")


def test_names_not_given_leave_the_settings_alone(state: RunState) -> None:
    state.program_arguments.single_task_name = "Restored"

    runcli.get_single_name(state.program_arguments, _args())

    assert state.program_arguments.single_task_name == "Restored"


def test_android_settings_come_as_lists_or_plain_values(state: RunState) -> None:
    runcli.get_android_settings(
        state.program_arguments, _args(android_ipaddr=["1.2.3.4"], android_port=["1821"], android_file=["/b.xml"])
    )
    assert (
        state.program_arguments.android_ipaddr,
        state.program_arguments.android_port,
        state.program_arguments.android_file,
    ) == ("1.2.3.4", "1821", "/b.xml")

    runcli.get_android_settings(
        state.program_arguments, _args(android_ipaddr="5.6.7.8", android_port="1822", android_file="/c.xml")
    )
    assert (
        state.program_arguments.android_ipaddr,
        state.program_arguments.android_port,
        state.program_arguments.android_file,
    ) == ("5.6.7.8", "1822", "/c.xml")


def test_no_android_address_leaves_the_android_settings_alone(state: RunState) -> None:
    runcli.get_android_settings(state.program_arguments, _args(android_port=["1821"]))

    assert state.program_arguments.android_ipaddr == ""
    assert state.program_arguments.android_port == ""


# ##################################################################################
# The remaining arguments.
# ##################################################################################
def test_each_remaining_argument_is_read_where_it_was_given(state: RunState, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runcli, "normalize_output_directory", lambda folder: (f"/abs/{folder}", ""))

    runcli.process_extended_arguments(
        _args(
            names=["bold"], appearance=["dark"], i=[8], font=["Menlo"], file=["~/b.xml"], outdir=["out"], view_limit=300
        ),
        state=state,
    )

    arguments = state.program_arguments
    assert arguments.bold is True
    assert arguments.appearance_mode == ["dark"]
    assert (arguments.indent, arguments.font, arguments.file) == (8, "Menlo", "~/b.xml")
    assert arguments.output_directory == "/abs/out"
    assert arguments.view_limit == 300


def test_plain_values_are_taken_as_they_come(state: RunState, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runcli, "normalize_output_directory", lambda folder: (folder, ""))

    runcli.process_extended_arguments(_args(font="Menlo", file="b.xml", outdir="out", i=2), state=state)

    assert (state.program_arguments.font, state.program_arguments.file, state.program_arguments.output_directory) == (
        "Menlo",
        "b.xml",
        "out",
    )
    assert state.program_arguments.indent == 2


def test_nothing_given_changes_nothing(state: RunState) -> None:
    before = {
        name: state.program_arguments[name]
        for name in ("font", "indent", "file", "view_limit", "output_directory", "appearance_mode")
    }

    runcli.process_extended_arguments(_args(), state=state)

    assert {name: state.program_arguments[name] for name in before} == before


def test_a_view_limit_not_given_leaves_the_one_the_settings_restored(state: RunState) -> None:
    state.program_arguments.view_limit = 777

    runcli.process_extended_arguments(_args(view_limit=None), state=state)
    assert state.program_arguments.view_limit == 777

    runcli.process_extended_arguments(_args(view_limit=40), state=state)
    assert state.program_arguments.view_limit == 40


def test_an_unusable_output_folder_is_said_and_the_default_kept(
    state: RunState, monkeypatch: pytest.MonkeyPatch
) -> None:
    said = []
    monkeypatch.setattr(console, "say", said.append)
    monkeypatch.setattr(runcli, "normalize_output_directory", lambda folder: ("", "That folder cannot be written to."))
    state.program_arguments.output_directory = "/kept"

    runcli.process_extended_arguments(_args(outdir=["/nope"]), state=state)

    assert state.program_arguments.output_directory == "/kept"
    assert said == ["That folder cannot be written to.  Using the default output folder."]


def test_everything_is_applied_before_the_single_names_and_the_detail_it_sets_stands(state: RunState) -> None:
    runcli.process_extended_arguments(_args(e=True, task=["Noisy"]), state=state)

    assert state.program_arguments.display_detail_level == DEFAULT_DISPLAY_DETAIL_LEVEL
    assert state.program_arguments.single_task_name == "Noisy"


def test_the_version_is_shown_and_the_run_ends(
    state: RunState, no_exit: list[int], monkeypatch: pytest.MonkeyPatch
) -> None:
    said: list[str] = []
    monkeypatch.setattr(console, "say", said.append)
    monkeypatch.setattr(runcli, "clip_figure", lambda *_: said.append("figure"))

    with pytest.raises(_Stop):
        runcli.process_extended_arguments(_args(v=True), state=state)

    assert no_exit == [0]
    assert any(runcli.MY_VERSION in line and runcli.MY_LICENSE in line for line in said)
    assert "figure" in said


def test_color_help_is_shown_and_the_run_ends(state: RunState, monkeypatch: pytest.MonkeyPatch) -> None:
    asked = []

    def stop(color: str) -> None:
        asked.append(color)
        raise _Stop

    monkeypatch.setattr(runcli, "validate_color", stop)

    with pytest.raises(_Stop):
        runcli.get_runtime_arguments(_args(ch=True), state=state)

    assert asked == ["h"]


def test_runtime_arguments_are_booleans_then_detail_then_the_rest(state: RunState) -> None:
    runcli.get_runtime_arguments(_args(conditions=True, detail=[2], i=[6]), state=state)

    assert state.program_arguments.conditions is True
    assert state.program_arguments.display_detail_level == 2
    assert state.program_arguments.indent == 6


# ##################################################################################
# Colors.
# ##################################################################################
def test_a_color_asked_for_replaces_the_default_one(state: RunState) -> None:
    state.program_arguments.appearance_mode = "light"

    runcli.process_arguments(_args(cTask=["Navy"], cProject="Maroon"), state=state)

    assert state.colors_to_use["task_color"] == "Navy"
    assert state.colors_to_use["project_color"] == "Maroon"
    assert state.colors_to_use["profile_color"] not in ("Navy", "Maroon")


def test_a_color_that_is_not_a_color_is_refused(state: RunState, monkeypatch: pytest.MonkeyPatch) -> None:
    refused = []
    monkeypatch.setattr(runcli, "get_and_set_the_color", lambda arg, state: refused.append(arg))

    runcli.process_arguments(_args(cTask=["NotAColor"]), state=state)

    assert refused == ["-cTask=NotAColor"]


def test_the_default_colors_follow_the_appearance(state: RunState) -> None:
    state.program_arguments.appearance_mode = "dark"
    runcli.process_arguments(_args(), state=state)
    dark = dict(state.colors_to_use)

    state.program_arguments.appearance_mode = "light"
    runcli.process_arguments(_args(), state=state)

    assert state.colors_to_use["background_color"] != dark["background_color"]


# ##################################################################################
# Restoring the saved settings.
# ##################################################################################
def test_saved_settings_and_colors_are_put_back(state: RunState, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        runcli,
        "save_restore_args",
        lambda arguments, colors, to_save, state: (
            {"indent": 7, "display_detail_level": "2", "font": "Menlo"},
            {"task_color": "Navy"},
        ),
    )

    runcli.restore_arguments(state=state)

    assert (state.program_arguments.indent, state.program_arguments.font) == (7, "Menlo")
    assert state.program_arguments.display_detail_level == 2  # Saved as text, used as a number.
    assert state.colors_to_use["task_color"] == "Navy"


def test_a_setting_this_version_does_not_know_is_skipped(state: RunState, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        runcli,
        "save_restore_args",
        lambda arguments, colors, to_save, state: ({"from_the_future": 1, "indent": 3, "display_detail_level": 4}, {}),
    )

    runcli.restore_arguments(state=state)

    assert state.program_arguments.indent == 3
    assert (
        not hasattr(state.program_arguments, "from_the_future")
        or "from_the_future" not in state.program_arguments.__dict__
    )


def test_no_settings_file_is_not_an_error(state: RunState, monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(arguments: dict, colors: dict, to_save: bool, state: RunState) -> tuple[dict, dict]:
        raise KeyError("no file")

    monkeypatch.setattr(runcli, "save_restore_args", missing)

    # The KeyError is from the file's contents being read, and is the one that is expected.
    with pytest.raises(KeyError):
        runcli.restore_arguments(state=state)

    monkeypatch.setattr(runcli, "save_restore_args", lambda arguments, colors, to_save, state: ({}, {}))
    state.program_arguments.display_detail_level = 3
    runcli.restore_arguments(state=state)  # An empty restore: the KeyError inside is suppressed.
    assert state.program_arguments.display_detail_level == 3


def test_a_colors_entry_with_no_key_is_ignored(state: RunState, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        runcli,
        "save_restore_args",
        lambda arguments, colors, to_save, state: ({"display_detail_level": 3}, {None: "x", "task_color": "Navy"}),
    )

    runcli.restore_arguments(state=state)

    assert None not in state.colors_to_use
    assert state.colors_to_use["task_color"] == "Navy"


# ##################################################################################
# The test namespace.
# ##################################################################################
def _unit_test(monkeypatch: pytest.MonkeyPatch, *arguments: str) -> SimpleNamespace:
    monkeypatch.setattr(sys, "argv", ["maptasker", "-test=yes", *arguments])
    monkeypatch.setattr(console, "say", lambda *_: None)
    return runcli.unit_test()


def test_the_test_namespace_starts_from_the_defaults_a_test_run_wants(monkeypatch: pytest.MonkeyPatch) -> None:
    args = _unit_test(monkeypatch)

    assert (args.detail, args.i, args.view_limit, args.debug, args.font) == (3, 4, 5000, True, "Courier")
    assert args.project is None
    assert args.v is False


def test_a_test_argument_overrides_its_default(monkeypatch: pytest.MonkeyPatch) -> None:
    args = _unit_test(monkeypatch, "detail=2", "font=Menlo", "project=Home", "task=Noisy", "twisty", "conditions")

    assert args.detail == 2
    assert args.font == "Menlo"
    assert args.project == ["Home"]  # A single name is a one-item list, as the parser gives it.
    assert args.task == ["Noisy"]
    assert args.twisty is True
    assert args.conditions is True  # Not mistaken for a color argument, though it starts with c.


def test_a_color_in_a_test_run_is_a_name_and_a_value(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _unit_test(monkeypatch, "cTask Navy").cTask == "Navy"


# ##################################################################################
# Arguments that disagree.
# ##################################################################################
def test_twisty_below_detail_three_is_warned_about(state: RunState, monkeypatch: pytest.MonkeyPatch) -> None:
    warned = []
    monkeypatch.setattr(console, "warn", warned.append)
    state.program_arguments.display_detail_level = 2
    state.program_arguments.twisty = True

    runcli.validate_arguments(state=state)

    assert len(warned) == 1
    assert "Twisty disabled" in warned[0]


def test_a_single_scene_below_detail_three_is_raised_to_three(state: RunState, monkeypatch: pytest.MonkeyPatch) -> None:
    warned = []
    monkeypatch.setattr(console, "warn", warned.append)
    state.program_arguments.display_detail_level = 1
    state.program_arguments.single_scene_name = "Dash"

    runcli.validate_arguments(state=state)

    assert state.program_arguments.display_detail_level == 3
    assert "Display level set to 3" in warned[0]


def test_arguments_that_agree_say_nothing(state: RunState, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(console, "warn", lambda *_: pytest.fail("a warning was given"))
    state.program_arguments.display_detail_level = 3
    state.program_arguments.twisty = True

    runcli.validate_arguments(state=state)

    assert state.program_arguments.display_detail_level == 3


# ##################################################################################
# Deciding what the run is.
# ##################################################################################
@pytest.fixture
def cli(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """process_cli with its inputs and outputs replaced: the command line, the GUI, the settings file."""
    calls = SimpleNamespace(gui=0, arguments=0, validated=0, restored=0, parsed=_args())

    monkeypatch.setattr(runcli, "runtime_parser", lambda: calls.parsed)
    monkeypatch.setattr(runcli, "restore_arguments", lambda state: setattr(calls, "restored", calls.restored + 1))
    monkeypatch.setattr(
        runcli, "process_arguments", lambda args, state: setattr(calls, "arguments", calls.arguments + 1)
    )
    monkeypatch.setattr(runcli, "validate_arguments", lambda state: setattr(calls, "validated", calls.validated + 1))
    monkeypatch.setattr(runcli, "GUI", False)

    def process_gui(first: bool, state: RunState) -> tuple[object, dict]:
        calls.gui += 1
        return state.program_arguments, {"from_gui": True}

    monkeypatch.setattr(runcli, "process_gui", process_gui)
    monkeypatch.setattr(sys, "argv", ["maptasker"])
    return calls


def test_the_command_line_path_reads_the_arguments_and_checks_them(state: RunState, cli: SimpleNamespace) -> None:
    runcli.process_cli(state)

    assert (cli.gui, cli.arguments, cli.validated, cli.restored) == (0, 1, 1, 1)
    assert state.program_arguments.debug is False


def test_a_gui_flag_runs_the_gui_instead(state: RunState, cli: SimpleNamespace) -> None:
    cli.parsed = _args(g=True)

    runcli.process_cli(state)

    assert (cli.gui, cli.arguments) == (1, 0)
    assert state.colors_to_use == {"from_gui": True}
    assert state.program_arguments.gui is True


def test_a_build_can_force_the_gui_on(state: RunState, cli: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runcli, "GUI", True)

    runcli.process_cli(state)

    assert (cli.gui, cli.arguments) == (1, 0)


def test_the_version_flag_wins_over_the_gui(state: RunState, cli: SimpleNamespace) -> None:
    cli.parsed = _args(g=True, v=True)

    runcli.process_cli(state)

    assert (cli.gui, cli.arguments) == (0, 1)


def test_a_map_view_from_the_gui_does_not_process_the_command_line(state: RunState, cli: SimpleNamespace) -> None:
    state.program_arguments.guiview = True

    runcli.process_cli(state)

    assert (cli.gui, cli.arguments, cli.validated) == (0, 0, 1)
    assert state.program_arguments.guiview is True  # Kept across the re-initialization.


def test_the_diagram_flag_is_kept_across_the_re_initialization(state: RunState, cli: SimpleNamespace) -> None:
    state.program_arguments.doing_diagram = True

    runcli.process_cli(state)

    assert state.program_arguments.doing_diagram is True


def test_a_view_limit_on_the_command_line_is_remembered_before_the_settings_replace_the_arguments(
    state: RunState, cli: SimpleNamespace
) -> None:
    cli.parsed = _args(view_limit=250)

    runcli.process_cli(state)

    assert state.cli_view_limit == 250


def test_a_run_with_no_arguments_loaded_yet_starts_cleanly(cli: SimpleNamespace) -> None:
    run = RunState()  # Nothing to carry over from a GUI run.

    runcli.process_cli(run)

    assert run.program_arguments is not None
    assert run.program_arguments.guiview is False
    assert run.program_arguments.doing_diagram is False


def test_a_test_run_reads_its_arguments_from_the_command_line_text(
    state: RunState, cli: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["maptasker", "-test=yes", "detail=1"])
    monkeypatch.setattr(console, "say", lambda *_: None)
    monkeypatch.setattr(runcli, "runtime_parser", lambda: pytest.fail("the parser was used for a test run"))

    runcli.process_cli(state)

    assert state.cli_view_limit == 5000  # The test namespace's own default.
    assert state.program_arguments.debug is True
