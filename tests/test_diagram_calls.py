"""MapTasker Diagram "Calls" list Unit Tests

A Task's "[Calls ──▶ ...]" list names the Tasks it calls, and a called Task's own name can end in
a bracket of its own ("Disable State [Write/Refresh]").  The list has to be read to its own closing
bracket, or the Task named last is not found in it and its connector is drawn on the line above
the calling Task instead of below it.
"""

from __future__ import annotations

import pytest
from maptasker.src.mapgen import diagram
from maptasker.src.mapgen.diagcnst import task_delimeter

PLAIN = "Freeze - Long Press Dialog"
BRACKETED = "Freeze - 🔄 Disable State [Write/Refresh]"


def _caller_line(*names: str, delimited: bool) -> str:
    """The caller Task's Diagram line, as it stands when the connectors are about to be drawn."""
    calls = ", ".join(f"{task_delimeter}{name}{task_delimeter}" if delimited else name for name in names)
    return f"    └─ Freeze - 🔑 Inbuilt Task [Calls ──▶ {calls}]"


def _middle_of(line: str, name: str) -> int:
    """The column of the middle of the called Task's name in the line, once delimiters are gone."""
    plain = line.replace(task_delimeter, "")
    return plain.find(name, plain.find("Calls")) + len(name) // 2


@pytest.mark.parametrize("delimited", [True, False])
def test_a_called_task_with_a_bracket_in_its_name_is_found_in_the_list(delimited: bool) -> None:
    line = _caller_line(PLAIN, BRACKETED, delimited=delimited)

    assert diagram.get_index_by_middle_char_position(line, _middle_of(line, PLAIN), PLAIN) == 1
    assert diagram.get_index_by_middle_char_position(line, _middle_of(line, BRACKETED), BRACKETED) == 2


def test_the_list_ends_at_its_own_closing_bracket() -> None:
    line = _caller_line(PLAIN, BRACKETED, delimited=False)

    substrings, _ = diagram.get_index_setup(line, BRACKETED)

    assert substrings == [PLAIN, BRACKETED]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("a, b]", 4),
        ("a, b [x]]", 8),
        ("a [x], b [y]] and more]", 12),
        ("a, b", -1),
    ],
)
def test_list_end(text: str, expected: int) -> None:
    assert diagram._list_end(text) == expected  # noqa: SLF001


def test_padding_for_removed_delimiters_goes_after_the_whole_list() -> None:
    line = _caller_line(PLAIN, BRACKETED, delimited=True)
    output_lines = [line]

    diagram.cleanup_task_names(output_lines, 0, line)

    assert output_lines[0] == _caller_line(PLAIN, BRACKETED, delimited=False) + " " * 4
