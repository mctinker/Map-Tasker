"""The AI analysis is sent the object it was asked about.

Analyze used to go straight to the model with whatever was left in PrimeItems.output_lines
-- and a Map view empties those once the Map is on screen, so the query was the prompt and
nothing after it.  The model said as much: "the Tasker data didn't come through".
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator

import pytest
from maptasker.src.core.primitem import PrimeItems, initial_tasker_root_elements
from maptasker.src.gui import mapai, userintr_ai
from maptasker.src.mapgen import mapcache

from tests.doubles import fake_window

_SYNTHETIC_BACKUP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "synthetic_backup.xml")


@pytest.fixture
def _a_loaded_configuration(tmp_path, monkeypatch) -> Iterator[None]:
    """The synthetic backup loaded, with a GUI up, in a directory of our own."""
    from maptasker.src.core.actionc import load_arg_specs
    from maptasker.src.core.colrmode import set_color_mode
    from maptasker.src.core.initparg import initialize_runtime_arguments
    from maptasker.src.mapgen.lineout import LineOut
    from maptasker.src.mapgen.proginit import get_data_and_output_intro

    monkeypatch.chdir(tmp_path)
    PrimeItems.program_arguments = initialize_runtime_arguments()
    PrimeItems.program_arguments.update({"file": _SYNTHETIC_BACKUP, "display_detail_level": 5, "gui": True})
    # Anything other than None means "the GUI is up", which keeps the build from opening a browser.
    monkeypatch.setattr(PrimeItems, "mygui", object())
    PrimeItems.colors_to_use = set_color_mode("dark")
    PrimeItems.output_lines = LineOut(state=PrimeItems)
    PrimeItems.tasker_root_elements = initial_tasker_root_elements()
    PrimeItems.file_to_get = open(_SYNTHETIC_BACKUP, encoding="utf-8")
    load_arg_specs(state=PrimeItems)
    get_data_and_output_intro(True, state=PrimeItems)
    yield
    mapcache.forget()


@pytest.mark.usefixtures("_a_loaded_configuration")
def test_the_query_holds_the_selected_task(monkeypatch) -> None:
    """The selected Task and its actions are in what the model is sent."""
    # The window's settings, as capture_gui_state would copy them: one Task selected.
    monkeypatch.setattr(
        userintr_ai,
        "capture_gui_state",
        lambda _gui, _data, *, state, **_kw: PrimeItems.program_arguments.update({"single_task_name": "Remind Me"}),
    )
    PrimeItems.output_lines.output_lines.clear()  # As a Map view leaves it.
    assert mapai.cleanup_output(state=PrimeItems) == []

    gui = fake_window(view_limit=10000, display_message_box=lambda *_args: None, state=PrimeItems)
    assert asyncio.run(userintr_ai.build_analysis_lines(gui))

    query_lines = mapai.cleanup_output(state=PrimeItems)
    assert any("Task:" in line and "Remind Me" in line for line in query_lines)
    assert any("Time to check your reminders" in line for line in query_lines)


@pytest.mark.usefixtures("_a_loaded_configuration")
def test_the_query_is_text_without_blank_lines(monkeypatch) -> None:
    """The model is sent the Map's words: no markup, no entities, no empty lines."""
    monkeypatch.setattr(
        userintr_ai,
        "capture_gui_state",
        lambda _gui, _data, *, state, **_kw: PrimeItems.program_arguments.update({"single_task_name": "Remind Me"}),
    )
    gui = fake_window(view_limit=10000, display_message_box=lambda *_args: None, state=PrimeItems)
    assert asyncio.run(userintr_ai.build_analysis_lines(gui))

    for line in mapai.cleanup_output(state=PrimeItems):
        assert line.strip()
        assert "&#" not in line
        assert "&nbsp;" not in line
