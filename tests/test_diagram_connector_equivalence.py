"""The connector search was made faster; these hold it to finding exactly what the first version found.

compute_diagram_connector_groups grows each connector out from a seed, cell by cell, and was rewritten to stop
looking cells up in a set of directions, to keep one dictionary of which group a cell belongs to rather than a
set and a second dictionary, and to give a line with no icon in it a range for its layout rather than two lists.
None of that may change a result -- including the ORDER the cells of a connector are found in, because the order
of a group's rows in the answer is the order its cells were met.  The first version is kept here, as written, and
the two are run over lines drawn at random from the characters a Diagram is made of.
"""

from __future__ import annotations

import random
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from maptasker.src.mapgen import diagarrows
from maptasker.src.mapgen.diagcnst import CONNECTOR_DIRECTIONS
from maptasker.src.mapgen.diagutil import icon_spans

from tests.doubles import fake_state
from tests.fuzzing import fuzz

_MAX_BRIDGE = 4


# ##################################################################################
# The first version
# ##################################################################################
def first_reachable_neighbors(lines: list[str], r: int, c: int, max_bridge: int = _MAX_BRIDGE) -> list[tuple[int, int]]:
    found = []
    for dr, dc in CONNECTOR_DIRECTIONS[lines[r][c]]:
        nr, nc = r + dr, c + dc
        blanks = 0
        while 0 <= nr < len(lines) and 0 <= nc < len(lines[nr]):
            nchar = lines[nr][nc]
            if nchar in CONNECTOR_DIRECTIONS and (-dr, -dc) in CONNECTOR_DIRECTIONS[nchar]:
                found.append((nr, nc))
                break
            if nchar == " ":
                blanks += 1
                if blanks > max_bridge:
                    break
            elif nchar not in CONNECTOR_DIRECTIONS:
                break
            nr, nc = nr + dr, nc + dc
    return found


def first_grow_connector(lines: list[str], seed_cell: tuple[int, int], visited: set) -> list[tuple[int, int]]:
    cells = []
    stack = [seed_cell]
    visited.add(seed_cell)
    while stack:
        r, c = stack.pop()
        cells.append((r, c))
        for nr, nc in first_reachable_neighbors(lines, r, c):
            if (nr, nc) in visited:
                continue
            visited.add((nr, nc))
            stack.append((nr, nc))
    return cells


def first_display_geometry(lines: list[str]) -> tuple[list[str], list[list[int]], list[list[int]]]:
    display_lines, cell_to_char, char_to_cell = [], [], []
    for line in lines:
        spans = dict(icon_spans(line))
        cells, chars, starts = [], [], []
        position = 0
        while position < len(line):
            end = spans.get(position)
            if end is None:
                starts.append(len(cells))
                cells.append(line[position])
                chars.append(position)
                position += 1
                continue
            starts.extend([len(cells)] * (end - position))
            cells.extend([line[position], "\x00"])
            chars.extend([position, position])
            position = end
        display_lines.append("".join(cells))
        cell_to_char.append(chars)
        char_to_cell.append(starts)
    return display_lines, cell_to_char, char_to_cell


def first_compute(lines: list[str], seeds: list[tuple[int, int, int]]) -> tuple[dict, dict]:
    visited: set = set()
    groups: dict = {}
    group_of_cell: dict = {}
    calls_by_group: dict = {}
    group_id = 0
    cells_by_line, cell_to_char, char_to_cell = first_display_geometry(lines)
    for row, col, call_index in seeds:
        seed_cell = diagarrows.find_diagram_connector_seed_cell(lines, row, col)
        if seed_cell is None:
            continue
        seed_cell = (row, char_to_cell[row][seed_cell[1]])
        if seed_cell in visited:
            existing = group_of_cell.get(seed_cell)
            if existing is not None and call_index not in calls_by_group[existing]:
                calls_by_group[existing].append(call_index)
            continue
        cells = first_grow_connector(cells_by_line, seed_cell, visited)
        groups[group_id] = cells
        calls_by_group[group_id] = [call_index]
        for cell in cells:
            group_of_cell[cell] = group_id
        group_id += 1
    ranges = {
        gid: diagarrows._cells_to_ranges([(row, cell_to_char[row][cell]) for row, cell in cells])
        for gid, cells in groups.items()
    }
    return ranges, calls_by_group


# ##################################################################################
# Lines drawn at random from what a Diagram is made of
# ##################################################################################
CHARACTERS = [*CONNECTOR_DIRECTIONS, " ", " ", " ", "x", "[", "║", "\U0001f504", "日"]


@st.composite
def diagrams(draw: st.DrawFn) -> tuple[list[str], list[tuple[int, int, int]]]:
    rows = draw(st.integers(min_value=1, max_value=14))
    width = draw(st.integers(min_value=1, max_value=24))
    lines = ["".join(draw(st.lists(st.sampled_from(CHARACTERS), min_size=0, max_size=width))) for _ in range(rows)]
    seeds = [
        (draw(st.integers(min_value=0, max_value=rows)), draw(st.integers(min_value=0, max_value=width + 2)), call)
        for call in range(draw(st.integers(min_value=0, max_value=6)))
    ]
    return lines, seeds


@fuzz(1500)
@given(diagram=diagrams())
def test_the_connectors_found_are_the_ones_the_first_version_found(
    diagram: tuple[list[str], list[tuple[int, int, int]]],
) -> None:
    lines, seeds = diagram
    state: Any = fake_state()

    ranges = diagarrows.compute_diagram_connector_groups(lines, seeds, state=state)
    expected_ranges, expected_calls = first_compute(lines, seeds)

    assert ranges == expected_ranges
    assert state.diagram_connector_calls == expected_calls
    assert list(ranges) == list(expected_ranges)


@fuzz(500)
@given(diagram=diagrams())
def test_the_layout_by_screen_column_is_the_first_versions(
    diagram: tuple[list[str], list[tuple[int, int, int]]],
) -> None:
    lines, _ = diagram

    display, cell_to_char, char_to_cell = diagarrows._display_geometry(lines)
    first_display, first_cell_to_char, first_char_to_cell = first_display_geometry(lines)

    assert display == first_display
    assert [list(row) for row in cell_to_char] == first_cell_to_char
    assert [list(row) for row in char_to_cell] == first_char_to_cell


def test_a_long_straight_bar_with_a_bundle_across_it_is_one_connector() -> None:
    """Dozens of other connectors' bars standing side by side must not cut the run in two (see the bridging note)."""
    column = "│"
    lines = ["╭◄───╮"] + ["     " + column] * 40 + ["╰►───╯"]
    seeds = [(0, 0, 0), (41, 5, 0)]
    state: Any = fake_state()

    ranges = diagarrows.compute_diagram_connector_groups(lines, seeds, state=state)

    assert len(ranges) == 1
    assert state.diagram_connector_calls == {0: [0]}


@pytest.mark.parametrize("seed", range(3))
def test_a_large_random_diagram_agrees_too(seed: int) -> None:
    rng = random.Random(seed)
    lines = ["".join(rng.choice(CHARACTERS) for _ in range(rng.randint(40, 90))) for _ in range(120)]
    seeds = [(rng.randrange(120), rng.randrange(90), index) for index in range(60)]
    state: Any = fake_state()

    assert diagarrows.compute_diagram_connector_groups(lines, seeds, state=state) == first_compute(lines, seeds)[0]
