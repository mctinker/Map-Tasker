"""The Diagram's drawing helpers: boxes around names, icons that throw the columns out, and connectors that overlap."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from maptasker.src.mapgen import diagutil

ENGLISH = SimpleNamespace(language="English")


# ##################################################################################
# Connectors that share a column
# ##################################################################################
def _connector(caller: int, called: int, location: int) -> dict:
    return {"caller_line_num": caller, "called_line_num": called, "up_down_location": location}


def test_connectors_sharing_a_column_are_found_in_pairs() -> None:
    table = {"a": _connector(1, 5, 4), "b": _connector(3, 8, 4), "c": _connector(1, 2, 6), "d": {}}
    assert [key for key, _ in diagutil.find_duplicate_up_down_locations(table)] == ["a", "b"]


def test_no_shared_columns_means_none_found() -> None:
    assert diagutil.find_duplicate_up_down_locations({"a": _connector(1, 5, 4), "b": _connector(1, 5, 6)}) == []


def test_overlapping_connectors_are_moved_apart() -> None:
    """Two lines drawn down the same column over the same rows would read as one."""
    table = {"a": _connector(1, 5, 4), "b": _connector(3, 8, 4)}
    fixed = diagutil.fix_duplicate_up_down_locations(table)
    assert fixed["a"]["up_down_location"] == 4
    assert fixed["b"]["up_down_location"] == 6


def test_connectors_that_do_not_overlap_may_share_a_column() -> None:
    table = {"a": _connector(1, 3, 4), "b": _connector(10, 8, 4)}
    assert diagutil.fix_duplicate_up_down_locations(table) == table


def test_a_connector_drawn_upward_is_measured_from_its_top() -> None:
    """Caller below called: the span runs from the called line down to the caller."""
    table = {"a": _connector(9, 2, 4), "b": _connector(3, 4, 4)}
    fixed = diagutil.fix_duplicate_up_down_locations(table)
    assert fixed["b"]["up_down_location"] == 6


def test_three_connectors_end_up_in_three_columns() -> None:
    table = {"a": _connector(1, 9, 4), "b": _connector(2, 8, 4), "c": _connector(3, 7, 4)}
    fixed = diagutil.fix_duplicate_up_down_locations(table)
    assert len({entry["up_down_location"] for entry in fixed.values()}) == 3


# ##################################################################################
# Icons and wide characters
# ##################################################################################
def test_a_plain_name_has_no_extra_column() -> None:
    assert diagutil.icon_columns("hello") == 0
    assert diagutil.icon_columns("caf\u00e9") == 0


def test_a_double_width_icon_needs_the_column_it_occupies() -> None:
    assert diagutil.icon_columns("\U0001f604 hi") == 1
    assert diagutil.icon_columns("\U0001f304 a \U0001f304") == 2


def test_an_icon_that_is_already_two_characters_long_needs_nothing() -> None:
    assert diagutil.icon_columns("\u21a9\ufe0f hi") == 0


def test_each_chinese_japanese_or_korean_character_needs_the_column_it_occupies() -> None:
    assert diagutil.icon_columns("\u4e2d\u6587") == 2
    assert diagutil.icon_columns("\u6ed1\u52a8\u62fc\u56fev0.8") == 4
    assert diagutil.icon_columns("\u3072\u3089\u304c\u306a \ud55c\uae00") == 6


def test_icons_are_counted() -> None:
    assert diagutil.count_icons("a😀b🚀") == 2
    assert diagutil.count_icons("plain") == 0



def test_a_character_is_removed_by_position() -> None:
    assert diagutil.remove_char("abcd", 1) == "acd"


def test_a_closing_bracket_is_never_the_character_removed() -> None:
    assert diagutil.remove_char("ab]cd", 3) == "ab]cd"


def test_a_line_with_no_arrow_is_left_as_it_is() -> None:
    assert diagutil.remove_icon("plain text, no arrow") == "plain text, no arrow"


def test_a_line_with_an_arrow_and_no_icon_is_left_as_it_is() -> None:
    line = f"Task {diagutil.arrows[0]} other"
    assert diagutil.remove_icon(line) == line


def test_an_icon_before_a_connector_has_its_column_taken_back_from_the_blanks_in_front_of_it() -> None:
    line = f"x😀   {diagutil.bar} Task"
    assert diagutil.remove_icon(line) == f"x😀  {diagutil.bar} Task"


def test_no_text_is_ever_removed_to_make_room() -> None:
    line = f"x😀 {diagutil.bar} Task"
    assert diagutil.remove_icon(line) == f"x😀{diagutil.bar} Task"
    # With no blanks at all, the connector stays where it is rather than eating a word.
    tight = f"x😀 yz😀{diagutil.bar}"
    assert diagutil.remove_icon(tight) == tight


def _columns(line: str) -> dict[int, str]:
    """Each connector's column as it is drawn: an icon takes two."""
    columns, column = {}, 0
    for char in line:
        if char in diagutil._vertical_connectors:  # noqa: SLF001
            columns[column] = char
        column += 2 if diagutil.is_double_width(char) else 1
    return columns


def test_connectors_to_the_right_of_an_icon_stay_under_the_ones_above() -> None:
    line = "    └─ PT Tasks [Called by 🏘] [Calls ──▶ PT Log]  │▲  │"
    # Each connector is drawn one column further over than it would be without the icon.
    fixed = diagutil.remove_icon(line)

    assert sorted(_columns(fixed)) == [c - 1 for c in sorted(_columns(line))]
    assert list(_columns(fixed).values()) == list(_columns(line).values())
    # Only blanks went, and none from the text itself.
    assert fixed.replace(" ", "") == line.replace(" ", "")
    assert "[Calls ──▶ PT Log]" in fixed


def test_a_connector_to_the_left_of_an_icon_is_not_moved() -> None:
    line = "│   └─ Wake 🏘     │   │"
    fixed = diagutil.remove_icon(line)

    assert fixed.index(diagutil.bar) == 0
    assert _columns(fixed)[len("│   └─ Wake ") + 2 + 5 - 1] == diagutil.bar


def test_every_icon_gives_a_column_back_to_the_connectors_after_it() -> None:
    line = "│ 🏘 Task 💾     │      │"
    fixed = diagutil.remove_icon(line)

    assert [c - 2 for c in sorted(_columns(line))][1:] == sorted(_columns(fixed))[1:]
    assert min(_columns(fixed)) == 0


def test_an_icon_with_no_connector_after_it_is_left_alone() -> None:
    line = "│        └─ Wake 🏘    "

    assert diagutil.remove_icon(line) == line


def test_an_icon_in_a_box_leaves_the_box_as_drawn() -> None:
    line = "║ Wake 💾 ║ ║ No Profile ║     │"
    fixed = diagutil.remove_icon(line)

    assert fixed.startswith("║ Wake 💾 ║ ║ No Profile ║")
    assert list(_columns(fixed)) == [c - 1 for c in _columns(line)]


@pytest.mark.parametrize(
    "icon",
    ["\U0001f4be", "\u23f0", "\u2699\ufe0f", "\u21a9\ufe0f", "\U0001f3de\ufe0f", "\U0001f44d\U0001f3fd", "1\ufe0f\u20e3"],
)
def test_an_icon_is_found_whole_with_whatever_is_joined_onto_it(icon: str) -> None:
    assert diagutil.icon_spans(f"a {icon} b") == [(2, 2 + len(icon))]


def test_plain_text_and_connectors_hold_no_icons() -> None:
    assert diagutil.icon_spans("Task 1 \u2502\u25b2 \u2570\u25c4\u2500\u2500 abc") == []


def test_a_symbol_and_its_picture_selector_is_already_two_columns_long() -> None:
    # Three of them, as in 'Universal Error Display Sub \u21a9\ufe0f': each is two characters
    # and drawn two columns wide, so nothing is taken back and the connectors stay put.
    line = "\u2514\u2500 Sub \u21a9\ufe0f [Called by \u25c4\u2500\u2500 Sub \u21a9\ufe0f] [Calls \u2500\u2500\u25b6 Sub \u21a9\ufe0f]  \u25b2    \u2502 \u2502"

    assert diagutil.remove_icon(line) == line


def test_a_joined_picture_is_longer_than_it_is_wide_so_the_connectors_are_given_columns() -> None:
    family = "\U0001f468\u200d\U0001f469\u200d\U0001f467"
    line = f"Task {family}  \u2502"

    fixed = diagutil.remove_icon(line)

    assert list(_columns(line))[0] + 3 == list(_columns(fixed))[0]


# ##################################################################################
# A box around a name
# ##################################################################################
def test_a_name_is_boxed_on_three_lines() -> None:
    lines, anchor = diagutil.build_box("Wake Up", ["", "", ""], ENGLISH)
    assert lines == [" ╔═════════╗", " ║ Wake Up ║", " ╚═════════╝"]
    assert anchor == 5


def test_trailing_blanks_are_not_boxed() -> None:
    lines, _ = diagutil.build_box("Wake Up   ", ["", "", ""], ENGLISH)
    assert lines[1] == " ║ Wake Up ║"


def test_a_box_is_added_after_whatever_is_already_on_the_line() -> None:
    lines, _ = diagutil.build_box("B", ["A", "A", "A"], ENGLISH)
    assert [line.startswith("A") for line in lines] == [True, True, True]
    assert lines[1].endswith("║ B ║")


def test_a_box_holding_an_icon_still_lines_up() -> None:
    top, middle, bottom = diagutil.build_box("😀 Wake", ["", "", ""], ENGLISH)[0]
    assert len(top) == len(bottom)
    assert middle.endswith("║")


def _drawn_width(line: str) -> int:
    return sum(2 if diagutil.is_double_width(char) else 1 for char in line)


@pytest.mark.parametrize("name", ["\U0001f304", "Wake \U0001f304 Up", "\U0001f304 a \U0001f4be", "caf\u00e9", "\u21a9\ufe0f x", "\u6ed1\u52a8\u62fc\u56fev0.8", "\u76d1\u63a7\u5fae\u535a \U0001f9e9"])
def test_the_walls_of_a_box_holding_an_icon_are_under_its_borders(name: str) -> None:
    top, middle, bottom = diagutil.build_box(name, ["", "", ""], ENGLISH)[0]

    assert _drawn_width(top) == _drawn_width(middle) == _drawn_width(bottom)


def test_the_boxes_after_one_holding_an_icon_stay_in_line_with_it() -> None:
    lines = ["", "", ""]
    for name in ("Wake", "\U0001f304", "\u76d1\u63a7\u5fae\u535a", "Nightly"):
        lines = diagutil.build_box(name, lines, ENGLISH)[0]

    assert {_drawn_width(line) for line in lines} == {_drawn_width(lines[0])}
    def columns(line: str, characters: str) -> list[int]:
        found, column = [], 0
        for char in line:
            if char in characters:
                found.append(column)
            column += 2 if diagutil.is_double_width(char) else 1
        return found

    assert columns(lines[0], "\u2554\u2557") == columns(lines[1], "\u2551") == columns(lines[2], "\u255a\u255d")


def test_a_box_holding_cjk_text_is_widened_for_it() -> None:
    plain = diagutil.build_box("abc", ["", "", ""], ENGLISH)[0]
    cjk = diagutil.build_box("中文名", ["", "", ""], ENGLISH)[0]
    assert len(cjk[0]) >= len(plain[0])


def test_the_no_profile_box_is_translated_for_other_languages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diagutil, "translate_string", lambda text: "Kein Profil")
    lines, _ = diagutil.build_box("No Profile", ["", "", ""], SimpleNamespace(language="German"))
    assert "Kein Profil" in lines[1]


@pytest.mark.parametrize("language", ["English", "Arabic"])
def test_the_no_profile_box_is_left_alone_in_english_and_arabic(
    monkeypatch: pytest.MonkeyPatch, language: str
) -> None:
    monkeypatch.setattr(diagutil, "translate_string", lambda text: pytest.fail("not translated"))
    lines, _ = diagutil.build_box("No Profile", ["", "", ""], SimpleNamespace(language=language))
    assert "No Profile" in lines[1]
