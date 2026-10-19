"""MapTasker Diagram "Calls" list Unit Tests

A Task's "[Calls ──▶ ...]" list names the Tasks it calls, and a called Task's own name can end in
a bracket of its own ("Disable State [Write/Refresh]").  The list has to be read to its own closing
bracket, or the Task named last is not found in it and its connector is drawn on the line above
the calling Task instead of below it.
"""

from __future__ import annotations

from types import SimpleNamespace

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


def test_a_connector_is_followed_through_a_row_whose_blanks_were_taken_out_for_an_icon() -> None:
    """Rows with an icon in them are a character short of the row above and below, to line up on screen.

    The connector's vertical run is at character 6 on every row but the one with the icon, where
    it is at character 5 -- and the whole of it has to be one connector, not a stub at each end.
    """
    lines = [
        "  \u256d\u25c4\u2500\u2500\u256e",
        "      \u2502",
        "  \U0001f504  \u2502",  # The icon takes two columns, so this bar is drawn in column 6 too.
        "      \u2502",
        "  \u2570\u25ba\u2500\u2500\u256f",
    ]
    state = SimpleNamespace()

    groups = diagram.compute_diagram_connector_groups(lines, [(4, 6, 0)], state=state)

    assert list(groups) == [0]
    covered = {row for row, _, _ in groups[0]}
    assert covered == {0, 1, 2, 3, 4}
    assert (2, 5, 6) in groups[0], "the bar on the icon's row is found where it is in the text, not where it is drawn"


def test_a_connector_is_not_joined_to_a_neighbour_that_only_looks_adjacent_in_the_text() -> None:
    """Without an icon, a bar one character over really is a different connector."""
    lines = ["  \u256d\u25c4\u2500\u2500\u256e", "      \u2502", "     \u2502", "      \u2502", "  \u2570\u25ba\u2500\u2500\u256f"]

    groups = diagram.compute_diagram_connector_groups(lines, [(4, 6, 0)], state=SimpleNamespace())

    assert all(row != 2 for gid in groups for row, _, _ in groups[gid])


def test_the_screen_columns_of_a_line_are_laid_out_for_wide_characters() -> None:
    display, cell_to_char, char_to_cell = diagram._display_geometry(["a\U0001f504b\u2502"])  # noqa: SLF001

    assert display == ["a\U0001f504\x00b\u2502"]
    assert cell_to_char == [[0, 1, 1, 2, 3]]
    assert char_to_cell == [[0, 1, 3, 4]]
