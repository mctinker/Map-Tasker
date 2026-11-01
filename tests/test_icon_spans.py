"""icon_spans finds the icons in a Diagram line, and finds the same ones the one-character-at-a-time search did.

The search was rewritten to step over everything that cannot start an icon, because it was the hottest function in a
large Diagram.  The old search is kept here as the definition, and the new one must agree with it on any line.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from maptasker.src.core.mapfonts import is_double_width
from maptasker.src.mapgen import diagutil

from tests.fuzzing import fuzz


def one_character_at_a_time(text: str) -> list[tuple[int, int]]:
    """The search as it was written first: look at every character in turn."""
    spans = []
    position = 0
    while position < len(text):
        char = text[position]
        following = text[position + 1 : position + 2]
        if char not in diagutil._icon_modifiers and ((char.strip() and is_double_width(char)) or following == "️"):
            end = position + 1
            while end < len(text) and (text[end] in diagutil._icon_modifiers or text[end] == "‍"):
                end += 2 if text[end] == "‍" else 1
            end = min(end, len(text))
            spans.append((position, end))
            position = end
        else:
            position += 1
    return spans


# Every kind of character a line holds: text, blanks, the connectors, narrow symbols, wide ones, and the characters
# that join an icon to the next one or change how it is drawn.
PIECES = st.sampled_from(
    [
        "a",
        "Z",
        " ",
        "\t",
        "1",
        "#",
        "│",  # bar
        "─",  # straight line
        "╔",  # box corner
        "◄",
        "⚙",  # gear, narrow, wants its picture
        "➡",  # arrow, narrow, wants its picture
        "️",
        "‍",
        "⃣",
        "\U0001f3fb",
        "\U0001f3ff",
        "日",  # CJK
        "本",
        "Ａ",  # fullwidth
        "あ",  # kana
        "한",  # Hangul
        "\U0001f642",  # emoji
        "\U0001f468",
        "\U0001f4bb",
        "⌚",  # wide, below the emoji planes
        "é",
        "\x00",
    ]
)


@fuzz(500)
@given(pieces=st.lists(PIECES, max_size=40))
def test_the_faster_search_finds_exactly_the_icons_the_first_one_did(pieces: list[str]) -> None:
    text = "".join(pieces)

    assert diagutil.icon_spans(text) == one_character_at_a_time(text)


@fuzz(200)
@given(text=st.text(max_size=60))
def test_it_agrees_on_any_text_at_all(text: str) -> None:
    assert diagutil.icon_spans(text) == one_character_at_a_time(text)


@pytest.mark.parametrize(
    ("text", "spans"),
    [
        ("", []),
        ("plain text and │ bars", []),
        ("a日b", [(1, 2)]),
        ("⚙️ gear", [(0, 2)]),
        ("\U0001f468‍\U0001f4bb at work", [(0, 3)]),
        ("\U0001f44d\U0001f3fb", [(0, 2)]),
        ("\ufe0f", []),
        ("x\ufe0f", [(0, 2)]),
    ],
)
def test_the_icons_in_a_line(text: str, spans: list[tuple[int, int]]) -> None:
    assert diagutil.icon_spans(text) == spans == one_character_at_a_time(text)


def test_nothing_in_the_range_the_search_steps_over_is_wide() -> None:
    """The connectors and boxes are drawn in U+2500 to U+25FC, which the search does not stop at."""
    wide = [hex(code) for code in range(0x2500, 0x25FD) if is_double_width(chr(code))]

    assert wide == []
    assert is_double_width("\u25fd"), "and the first one after the range is wide, which is why it ends there"


# ##################################################################################
# The index of Task lines
# ##################################################################################
def lines_holding(lines: list[str], name: str) -> list[int]:
    """The lines with "└─ <name>" in them, found the way they were before there was an index: by reading each."""
    wanted = f"{diagutil.angle}{name}"
    return [number for number, line in enumerate(lines) if wanted in line]


LINE_PIECES = st.sampled_from(["└─ ", "└─ ", "a", "b", "ab", " ", "[", "]", "Calls", "│", "日", "(entry) ", ", "])


@fuzz(400)
@given(
    lines=st.lists(st.lists(LINE_PIECES, max_size=14).map("".join), max_size=12),
    name=st.lists(LINE_PIECES, max_size=5).map("".join),
)
def test_the_index_finds_the_lines_that_reading_each_one_finds(lines: list[str], name: str) -> None:
    assert diagutil.TaskLineIndex(lines).lines_with(name) == lines_holding(lines, name)


def test_a_name_longer_than_the_index_keeps_is_still_found() -> None:
    long_name = "n" * (diagutil.TaskLineIndex.KEPT + 40)
    lines = ["nothing here", f"{diagutil.angle}{long_name} [Calls", f"{diagutil.angle}{long_name[:-1]}x"]

    assert diagutil.TaskLineIndex(lines).lines_with(long_name) == [1] == lines_holding(lines, long_name)


def test_a_name_that_is_the_start_of_longer_ones_finds_them_all() -> None:
    lines = [f"{diagutil.angle}Wake Up [Calls", f"{diagutil.angle}Wake Up Early [Calls", f"x {diagutil.angle}Wake Up"]

    assert diagutil.TaskLineIndex(lines).lines_with("Wake Up") == [0, 1, 2]
    assert diagutil.TaskLineIndex(lines).lines_with("Wake Up E") == [1]
