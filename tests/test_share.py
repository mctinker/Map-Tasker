"""TaskerNet <Share> text in the Map: the clean-up of doubled line breaks after it."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from types import SimpleNamespace

from maptasker.src.core.share import share


def _output(*lines: str) -> SimpleNamespace:
    """The Map's output so far, and the one method share() adds to it with."""
    collected = list(lines)
    return SimpleNamespace(
        output_lines=collected,
        add_line_to_output=lambda _level, text, _format: collected.append(text),
    )


def test_a_doubled_line_break_at_the_end_is_taken_out_by_position() -> None:
    """The clean-up removed it with list.remove(index), which looks for a VALUE equal to the index
    and so raised ValueError whenever there was a doubled break to remove."""
    state = SimpleNamespace(output_lines=_output("heading", "<br>", "<br>"))

    share(ET.fromstring("<Task><Share/></Task>"), "tasktab", config=None, state=state)  # noqa: S314

    lines = state.output_lines.output_lines
    assert lines.count("<br>") == 1  # one of the pair is gone
    assert lines[0] == "heading"


def test_a_single_line_break_is_left_alone() -> None:
    state = SimpleNamespace(output_lines=_output("heading", "<br>"))

    share(ET.fromstring("<Task><Share/></Task>"), "tasktab", config=None, state=state)  # noqa: S314

    assert state.output_lines.output_lines.count("<br>") == 1


def test_a_task_without_a_share_element_writes_nothing() -> None:
    state = SimpleNamespace(output_lines=_output("heading"))

    share(ET.fromstring("<Task/>"), "tasktab", config=None, state=state)  # noqa: S314

    assert state.output_lines.output_lines == ["heading"]
