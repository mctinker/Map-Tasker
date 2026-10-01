"""RunState: a run's own state, which a function can be handed instead of reading PrimeItems."""

from __future__ import annotations

import pytest
from maptasker.src import diagram, diagutil, projects
from maptasker.src.mapjump import PROFILE, Target
from maptasker.src.primitem import MAP_OUTPUT_ATTRIBUTES, PrimeItems, RunState, reset_attributes

_PROFILE = Target(kind=PROFILE, key="10", name="Wake Up")


@pytest.fixture(autouse=True)
def _clean_slate() -> None:
    """Nothing noted against a diagram, on the global or in the module's own buffers."""
    PrimeItems.netmap_output = []
    PrimeItems.diagram_object_seeds = {}
    diagram._pending_boxes.clear()  # noqa: SLF001
    diagram._pending_tasks.clear()  # noqa: SLF001


def test_the_global_is_a_run_state() -> None:
    assert isinstance(PrimeItems, RunState)


def test_two_run_states_share_no_containers() -> None:
    """A dict, list or set filled in on one must never turn up in another."""
    first, second = RunState(), RunState()

    first.grand_totals["projects"] = 3
    first.netmap_output.append("line")
    first.emitted_anchors.add("a")

    assert second.grand_totals["projects"] == 0
    assert second.netmap_output == []
    assert second.emitted_anchors == set()
    assert PrimeItems.grand_totals is not first.grand_totals


def test_a_reset_touches_only_the_state_it_is_given() -> None:
    state = RunState()
    state.grand_totals["projects"] = 5
    PrimeItems.grand_totals["projects"] = 7

    reset_attributes(*MAP_OUTPUT_ATTRIBUTES, state=state)

    assert state.grand_totals["projects"] == 0
    assert PrimeItems.grand_totals["projects"] == 7
    PrimeItems.grand_totals["projects"] = 0


def test_the_project_counts_are_reset_on_the_state_handed_in() -> None:
    state = RunState()
    state.scene_count = 4
    PrimeItems.scene_count = 9

    assert projects.setup_summary_counts(state) == 0

    assert state.scene_count == 0
    assert PrimeItems.scene_count == 9
    PrimeItems.scene_count = 0


def test_a_diagram_line_goes_to_the_state_it_is_given() -> None:
    state = RunState()

    diagutil.add_output_line("║ Wake Up ║", state=state)

    assert state.netmap_output == ["║ Wake Up ║"]
    assert PrimeItems.netmap_output == []


def test_a_diagram_object_is_recorded_on_the_state_it_is_given() -> None:
    """The box is noted and then flushed to its rows, all without the global being set up."""
    state = RunState()
    diagutil.add_output_line("header", state=state)
    diagram._note_box(_PROFILE, "║ Wake Up")  # noqa: SLF001
    diagram._flush_boxes(["top", "║ Wake Up ║", "bottom"], state=state)  # noqa: SLF001

    assert state.diagram_object_seeds[_PROFILE.anchor][0] == 2
    assert PrimeItems.diagram_object_seeds == {}
