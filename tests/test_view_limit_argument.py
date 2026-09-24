"""The view limit asked for on the command line is the one the Map build uses.

Two things were wrong with -view_limit.  The parser declared it as a flag
(action="store_true") carrying a number as its default, so a value could not be given at
all and the option on its own set the limit to 1 line.  And the value, wherever it came
from, was only ever written into the runtime arguments -- while the Map build reads
PrimeItems.view_limit, which only the GUI ever set.  A command-line run therefore always
built to the default limit.

What is checked here is that a limit given on the command line is accepted as a number,
that a bad one is refused rather than quietly turned into something else, that saying
nothing leaves a limit restored from the settings file alone, and that the value ends up
where the build reads it.
"""

from __future__ import annotations

import argparse
import sys

import pytest
from maptasker.src.initparg import ProgramArguments, initialize_runtime_arguments
from maptasker.src.parsearg import runtime_parser, validate_view_limit
from maptasker.src.primitem import PrimeItems
from maptasker.src.progargs import VIEW_LIMIT_UNLIMITED, resolve_view_limit
from maptasker.src.runcli import process_extended_arguments
from maptasker.src.sysconst import VIEW_LIMIT_DEFAULT


@pytest.fixture
def program_arguments() -> ProgramArguments:
    """A fresh set of runtime arguments for the command line to be applied to."""
    saved = PrimeItems.program_arguments
    PrimeItems.program_arguments = initialize_runtime_arguments()
    yield PrimeItems.program_arguments
    PrimeItems.program_arguments = saved


def run_with(*command_line: str) -> None:
    """Parse this command line and apply it, the way a run of MapTasker would."""
    saved_argv = sys.argv
    sys.argv = ["maptasker", *command_line]
    try:
        process_extended_arguments(runtime_parser())
    finally:
        sys.argv = saved_argv


# ##################################################################################
# What the parser accepts
# ##################################################################################
def test_a_number_of_lines_is_accepted() -> None:
    """-view_limit takes a value now, rather than being a flag."""
    assert validate_view_limit("250") == 250


def test_something_that_is_not_a_number_is_refused() -> None:
    """Better an error than a limit the user did not ask for."""
    with pytest.raises(argparse.ArgumentTypeError):
        validate_view_limit("lots")


@pytest.mark.parametrize("limit", ["0", "-1"])
def test_a_limit_that_would_leave_nothing_to_read_is_refused(limit: str) -> None:
    """A limit below one line cuts the Map off before it starts."""
    with pytest.raises(argparse.ArgumentTypeError):
        validate_view_limit(limit)


# ##################################################################################
# What the command line does with it
# ##################################################################################
def test_a_limit_given_on_the_command_line_is_taken(program_arguments: ProgramArguments) -> None:
    """The value asked for reaches the runtime arguments."""
    run_with("-view_limit", "250")

    assert program_arguments.view_limit == 250


def test_saying_nothing_leaves_the_restored_limit_alone(program_arguments: ProgramArguments) -> None:
    """A run that does not mention the limit must not overwrite the saved one."""
    program_arguments.view_limit = 3000  # As restored from the settings file.

    run_with()

    assert program_arguments.view_limit == 3000


def test_a_limit_given_beats_the_restored_one(program_arguments: ProgramArguments) -> None:
    """Asking for a limit is the whole point of asking for it."""
    program_arguments.view_limit = 3000

    run_with("-view_limit", "250")

    assert program_arguments.view_limit == 250


def test_a_bad_limit_stops_the_run(program_arguments: ProgramArguments) -> None:
    """argparse's own refusal: the run ends rather than building to some other limit."""
    with pytest.raises(SystemExit):
        run_with("-view_limit", "none at all")


# ##################################################################################
# Getting it to where the build reads it
# ##################################################################################
def test_the_limit_is_handed_over_as_a_number() -> None:
    """bildhtml.write_out_the_file compares line numbers against it."""
    assert resolve_view_limit(250) == 250
    assert resolve_view_limit("250") == 250


def test_the_guis_unlimited_is_understood() -> None:
    """The View Limit dropdown's largest setting can reach here as its own word."""
    assert resolve_view_limit("Unlimited") == VIEW_LIMIT_UNLIMITED


@pytest.mark.parametrize("value", [None, "", "lots"])
def test_a_value_that_is_no_use_falls_back_to_the_default(value: object) -> None:
    """An empty or hand-edited settings file must not stop the Map being built."""
    assert resolve_view_limit(value) == VIEW_LIMIT_DEFAULT
