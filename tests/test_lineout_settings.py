"""LineOut reads the settings it is given, and the live ones only when it is given none."""

from __future__ import annotations

import pytest
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.lineout import LineOut
from maptasker.src.primitem import PrimeItems
from maptasker.src.runcfg import current_config
from maptasker.src.sysconst import FormatLine

_LINE = "Remind Me&nbsp;&nbsp;Task ID: 12"


@pytest.fixture(autouse=True)
def _settings() -> None:
    """A clean set of settings, with debug off."""
    PrimeItems.program_arguments = initialize_runtime_arguments()
    PrimeItems.program_arguments.debug = False


def _written(output: LineOut) -> str:
    output.add_line_to_output(2, _LINE, FormatLine.dont_format_line)
    return "".join(output.output_lines)


def test_without_a_config_the_live_settings_are_read_as_they_change() -> None:
    """The GUI makes one LineOut at start-up and changes settings after: it has to see them."""
    output = LineOut()
    assert "Task ID" not in _written(output)

    PrimeItems.program_arguments.debug = True
    assert "Task ID" in _written(output)


def test_a_config_is_read_instead_of_the_global() -> None:
    """Debug is off in the global and on in the config, so the Task ID is kept."""
    output = LineOut(current_config().with_changes(debug=True))

    assert "Task ID" in _written(output)


def test_a_config_does_not_change_when_the_global_does() -> None:
    """A frozen config cannot move under the LineOut that holds it."""
    output = LineOut(current_config())
    PrimeItems.program_arguments.debug = True

    assert "Task ID" not in _written(output)
