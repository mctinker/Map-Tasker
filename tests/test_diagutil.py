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
    assert diagutil.fix_icon("hello") == ""


def test_a_double_width_icon_needs_the_column_it_occupies() -> None:
    assert diagutil.fix_icon("😀 hi") == diagutil.blank


def test_wide_cjk_characters_are_left_to_the_box_which_already_widens_for_them() -> None:
    assert diagutil.fix_icon("中文") == ""


def test_icons_are_counted() -> None:
    assert diagutil.count_icons("a😀b🚀") == 2
    assert diagutil.count_icons("plain") == 0


def test_cjk_characters_are_counted() -> None:
    assert diagutil.count_cjk_characters("中文名 abc") == 3
    assert diagutil.count_cjk_characters("abc") == 0


def test_a_character_is_removed_by_position() -> None:
    assert diagutil.remove_char("abcd", 1) == "acd"


def test_a_closing_bracket_is_never_the_character_removed() -> None:
    assert diagutil.remove_char("ab]cd", 3) == "ab]cd"


def test_a_line_with_no_arrow_is_left_as_it_is() -> None:
    assert diagutil.remove_icon("plain text, no arrow") == "plain text, no arrow"


def test_a_line_with_an_arrow_and_no_icon_is_left_as_it_is() -> None:
    line = f"Task {diagutil.arrows[0]} other"
    assert diagutil.remove_icon(line) == line


def test_an_icon_beside_an_arrow_has_its_column_taken_back() -> None:
    line = f"x😀{diagutil.bar} Task"
    assert len(diagutil.remove_icon(line)) < len(line)


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
