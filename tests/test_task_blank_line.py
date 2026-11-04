"""A blank line above each Task in the Map: format_item asks the writer for it, for a Task and for nothing else."""

from __future__ import annotations

import types
from typing import Any

import pytest
from maptasker.src.core.mapwriter import BLANK_LINE_BEFORE
from maptasker.src.mapgen import proclist


class RecordingOutput:
    """What state.output_lines is to format_item: it is told what to write, and in what order."""

    def __init__(self) -> None:
        self.written: list[str] = []

    def add_line_to_output(self, _level: int, line: str, _how: Any = None) -> None:
        self.written.append(line)


@pytest.fixture
def output(monkeypatch: pytest.MonkeyPatch) -> RecordingOutput:
    monkeypatch.setattr(proclist, "format_task_or_scene", lambda *_args, **_kwargs: ("<header>", "color"))
    monkeypatch.setattr(proclist, "add_dictionary_and_twisty", lambda *_args, **_kwargs: (None, None))
    monkeypatch.setattr(proclist, "item_anchor", lambda *_args, **_kwargs: "")
    return RecordingOutput()


def run_format_item(list_type: str, output: RecordingOutput) -> list[str]:
    state: Any = types.SimpleNamespace(output_lines=output)
    config: Any = types.SimpleNamespace(debug=False, display_detail_level=1)
    proclist.format_item(list_type, "Task: Name", [], None, config, state=state)
    return output.written


def test_a_task_asks_for_a_blank_line_before_its_heading(output: RecordingOutput) -> None:
    assert run_format_item("Task:", output) == [BLANK_LINE_BEFORE, "<header>"]


@pytest.mark.parametrize("list_type", ["Scene:", "--Task:"])
def test_a_scene_and_a_task_under_a_scene_do_not(output: RecordingOutput, list_type: str) -> None:
    assert BLANK_LINE_BEFORE not in run_format_item(list_type, output)
