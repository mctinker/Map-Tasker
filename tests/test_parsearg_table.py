"""parsearg: the command-line options are a table (assets/json/cli_arguments.json).

What matters is that the parser the table builds is the one the program has always had, and
that the table cannot name something the code does not have.  The first is held by these
tests listing what must be there; the second is checked entry by entry.
"""

from __future__ import annotations

import argparse
import json
import sys

import pytest
from maptasker.src import parsearg
from maptasker.src.sysconst import TYPES_OF_COLORS


@pytest.fixture(scope="module")
def table() -> dict:
    with open(parsearg.CLI_ARGUMENTS_FILE, encoding="utf-8") as file:
        return json.load(file)


def _parse(*argv: str) -> argparse.Namespace:
    return parsearg.build_parser().parse_args(list(argv))


def test_every_type_group_and_choice_the_table_names_exists(table: dict) -> None:
    for entry in table["arguments"]:
        assert entry.get("type", "str") in parsearg._ARGUMENT_TYPES  # noqa: SLF001
        if "group" in entry:
            assert entry["group"] in table["groups"]
        if isinstance(entry.get("choices"), str):
            assert entry["choices"] in parsearg._ARGUMENT_CHOICES  # noqa: SLF001
        assert ("names" in entry) != ("expand" in entry)


def test_no_option_is_named_twice(table: dict) -> None:
    names = [name for entry in table["arguments"] for name in entry.get("names", [])]

    assert len(names) == len(set(names))


def test_the_options_the_program_has_always_had_are_all_there() -> None:
    parser = parsearg.build_parser()
    options = {name for action in parser._actions for name in action.option_strings}  # noqa: SLF001

    for name in (
        "-ai_model", "-android_ipaddr", "-android_port", "-android_file", "-appearance", "-conditions", "-debug",
        "-detail", "-directory", "-e", "-everything", "-file", "-font", "-g", "-gui", "-i", "-indent", "-guiview",
        "-view_limit", "-names", "-o", "-outline", "-outdir", "-preferences", "-pretty", "-project", "-profile",
        "-task", "-scene", "-reset", "-runtime", "-taskernet", "-twisty", "-v", "-version", "-ch", "-colorhelp",
    ):  # fmt: skip
        assert name in options, name
    # One color option for each kind of thing that can be colored.
    assert {f"-c{key}" for key in TYPES_OF_COLORS} <= options


def test_defaults_and_values_are_what_they_were() -> None:
    args = _parse()

    assert (args.detail, args.i, args.appearance, args.names) == (3, 4, "system", "")
    assert (args.view_limit, args.file, args.font) == (None, None, None)
    assert (args.debug, args.g, args.twisty, args.ch) == (False, False, False, False)
    assert args.android_ipaddr == ""

    args = _parse("-detail", "2", "-i", "6", "-names", "bold", "underline", "-view_limit", "50", "-cTask", "Blue")
    assert (args.detail, args.i, args.names, args.view_limit) == ([2], [6], ["bold", "underline"], 50)
    assert args.cTask == ["Blue"]


@pytest.mark.parametrize(
    "argv",
    [
        ["-detail", "9"],
        ["-appearance", "x"],
        ["-names", "bad"],
        ["-view_limit", "0"],
        ["-e", "-twisty"],
        ["-project", "A", "-task", "B"],
    ],
)
def test_what_the_table_forbids_is_refused(argv: list[str], capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit):
        _parse(*argv)
    assert capsys.readouterr().err


def test_the_ai_models_offered_are_the_ones_the_program_knows() -> None:
    parser = parsearg.build_parser()
    action = next(action for action in parser._actions if "-ai_model" in action.option_strings)  # noqa: SLF001

    assert list(action.choices) == parsearg._ARGUMENT_CHOICES["@ai_models"]()  # noqa: SLF001
    assert len(action.choices) > 10


def test_hidden_options_stay_out_of_the_help() -> None:
    help_text = parsearg.build_parser().format_help()

    assert "-view_limit" not in help_text
    assert "-guiview" not in help_text
    assert "Output Color Options" in help_text
    assert "mutually inclusive" in help_text


def test_runtime_parser_reads_the_command_line(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["maptasker", "-debug", "-detail", "4"])

    args = parsearg.runtime_parser()

    assert args.debug is True
    assert args.detail == [4]
