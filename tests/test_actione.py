"""An Action's line in the Map: its code looked up, its arguments laid out one to a line, its length held."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from types import SimpleNamespace

import pytest
from maptasker.src.core.primitem import PrimeItems, RunState
from maptasker.src.mapgen import actione

from tests.doubles import fake_state

BLANK = "&nbsp;"
NAME = '<span class="action_name_color">{}</span>'


def _state(*, pretty: bool) -> RunState:
    return fake_state(program_arguments=SimpleNamespace(pretty=pretty))


def _element(text: str) -> ET.Element:
    return ET.fromstring(text)


# ##################################################################################
# Looking up an action's code
# ##################################################################################
def test_a_code_nobody_has_mapped_is_said_so(monkeypatch: pytest.MonkeyPatch) -> None:
    """A new Tasker action must not break the Map: it is named by its code, and reported once for the author."""
    reported: list[tuple] = []
    monkeypatch.setattr(actione, "not_in_dictionary", lambda *args: reported.append(args))
    code = _element("<code>999999</code>")
    action = _element("<Action sr='act0'><code>999999</code></Action>")

    assert actione.get_action_code(code, action, True, "t", state=PrimeItems) == "Code 999999t not yet mapped"
    assert reported


def test_a_known_code_is_shown_by_name() -> None:
    code = _element("<code>1040969826</code>")  # a redirected entry: it borrows another action's arguments
    action = _element("<Action sr='act0'><code>1040969826</code><Str sr='arg0'>x</Str></Action>")
    shown = actione.get_action_code(code, action, True, "t", state=PrimeItems)
    assert shown.startswith('<span class="action_name_color">')
    assert "Muzei Wallpaper: Next Artwork" in shown


def test_a_deprecated_action_is_marked_where_the_name_is() -> None:
    code = _element("<code>2087</code>")
    action = _element("<Action sr='act0'><code>2087</code></Action>")
    assert "(Is Deprecated)" in actione.get_action_code(code, action, False, "e", state=PrimeItems)


def test_deprecation_is_decided_by_code_and_kind_together() -> None:
    """The Task action numbered 10 is deprecated; the State numbered 10 ('Power') is not."""
    assert actione.check_for_deprecation("2087e")
    assert actione.check_for_deprecation("10s") == ""
    assert actione.check_for_deprecation("0000x") == ""


# ##################################################################################
# JSON that the comma split took apart
# ##################################################################################
def test_a_structure_output_broken_at_its_comma_is_put_back() -> None:
    broken = "To=1, Structure Output (JSON<br>IND    etc), Next=2"
    assert actione.fix_json(broken, "Structure Output") == "To=1, Structure Output (JSON, etc), Next=2"


def test_a_line_without_one_is_left_alone() -> None:
    assert actione.fix_json("Text=a, b", "Structure Output") == "Text=a, b"


# ##################################################################################
# Pretty mode: one argument to a line, lined up under the first
# ##################################################################################
def test_each_argument_goes_on_a_line_of_its_own() -> None:
    line = f"{NAME.format('Flash')}{BLANK * 2}Text=Hello, Long=1, Other=2"

    pretty, hang = actione.make_action_pretty(line, "IND")

    assert pretty.count("<br>IND") == 2
    assert f"Text=Hello<br>IND{BLANK * hang}Long=1<br>IND{BLANK * hang}Other=2" in pretty


def test_variable_set_is_split_only_at_its_named_parts() -> None:
    """A Variable Set's value is free text full of commas; only the fixed parts are line starts."""
    line = f"{NAME.format('Variable Set')}{BLANK * 2}Name=%a, To=1, 2, 3, Max Rounding Digits=2, Structure Output (JSON, etc)"

    pretty, _ = actione.make_action_pretty(line, "IND")

    assert pretty.count("<br>IND") == 3
    assert "To=1, 2, 3" in pretty  # the commas inside the value survive
    assert "Structure Output (JSON, etc)" in pretty


def test_for_is_split_at_its_items() -> None:
    line = f"{NAME.format('For')}{BLANK * 2}Variable=%i, Items=1,2,3"
    pretty, _ = actione.make_action_pretty(line, "IND")
    assert pretty.count("<br>IND") == 1
    assert "Items=1,2,3" in pretty


def test_a_condition_label_and_flags_each_start_a_line() -> None:
    line = (
        f"{NAME.format('Flash')}{BLANK * 2}Text=a [DISABLED] (<em>IF %x</em>)"
        '<span class="action_label_color"> ...with label: Hi</span>'
    )

    pretty, _ = actione.make_action_pretty(line, "IND")

    assert pretty.count("<br>IND") == 3
    assert "<br>IND" + BLANK * 11 + "[DISABLED]" in pretty  # a disabled action is not pushed further in
    assert '<span class="action_label_color">...with label: Hi</span>' in pretty


def test_embedded_newlines_become_line_breaks_too() -> None:
    line = f"{NAME.format('Flash')}{BLANK * 2}Text=a\nb"
    pretty, _ = actione.make_action_pretty(line, "IND")
    assert "\n" not in pretty
    assert "a<br>IND" in pretty


def test_configuration_parameters_are_left_for_their_own_formatting() -> None:
    """They are laid out by tasks.reformat_html, so they only get the one split here and not
    the deeper, comma-and-newline one every other argument list gets after it."""
    line = f"{NAME.format('Perform Task')}{BLANK * 2}Configuration Parameter(s):a=1, b=2"
    pretty, hang = actione.make_action_pretty(line, "IND")
    assert pretty.count("<br>IND") == 1
    assert f"<br>IND{BLANK * hang}b=2" in pretty  # hung at the action name, not seven further in


# ##################################################################################
# Finishing the line and adding it to the list
# ##################################################################################
def test_a_long_line_with_no_newline_is_kept_whole() -> None:
    line = "x" * 90
    assert actione.finalize_action_details(line, [], 0, 0, state=_state(pretty=False)) == [line]


def test_pretty_mode_keeps_the_line_whole() -> None:
    line = "a\nb"
    assert actione.finalize_action_details(line, [], 0, 0, state=_state(pretty=True)) == [line]


def test_a_text_box_keeps_its_own_newlines() -> None:
    line = 'a\n<div class="text-box">b</div>'
    assert actione.finalize_action_details(line, [], 0, 0, state=_state(pretty=False)) == [line]


def test_continued_lines_are_marked_with_where_to_indent_them() -> None:
    result = actione.finalize_action_details("first\nsecond\nthird", [], 4, 3, state=_state(pretty=False))
    assert result == ["first", "...indent=7item=second", "...indent=7item=third"]


def test_continuation_stops_at_the_limit_and_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(actione, "CONTINUE_LIMIT", 2)

    result = actione.finalize_action_details("a\nb\nc\nd\ne", [], 0, 0, state=_state(pretty=False))

    assert len(result) == 3  # the first line and two continuations
    assert "continue limit of 2 reached" in result[-1]
    assert not any(item.endswith(("item=d", "item=e")) for item in result)


# ##################################################################################
# Building the line
# ##################################################################################
def test_an_action_nested_in_a_block_is_indented() -> None:
    line = f"{NAME.format('Flash')}{BLANK * 2}Text=a"
    result = actione.build_action([], line, ET.Element("code"), 2, "<>", state=_state(pretty=False))
    assert result == [f'<span class="action_name_color"><>Flash</span>{BLANK * 2}Text=a']


def test_a_top_level_action_is_not_indented() -> None:
    line = f"{NAME.format('Flash')}{BLANK * 2}Text=a"
    assert actione.build_action([], line, ET.Element("code"), 0, "<>", state=_state(pretty=False)) == [line]


def test_the_leading_comma_of_an_empty_first_argument_is_dropped() -> None:
    line = f"{NAME.format('Flash')}{BLANK * 2},Text=a"
    (result,) = actione.build_action([], line, ET.Element("code"), 0, "", state=_state(pretty=False))
    assert f"{BLANK * 2},Text=a" not in result
    assert f"{BLANK * 2}Text=a" in result


def test_pretty_mode_lays_the_arguments_out(monkeypatch: pytest.MonkeyPatch) -> None:
    line = f"{NAME.format('Flash')}{BLANK * 2}Text=a, Long=1"
    (result,) = actione.build_action([], line, ET.Element("code"), 0, "IND", state=_state(pretty=True))
    assert "<br>IND" in result


def test_pretty_mode_keeps_a_label_that_holds_html_out_of_the_layout() -> None:
    """A label may contain markup of its own ('<div ...>'), which must not be reflowed as arguments."""
    line = f'{NAME.format("Flash")}{BLANK * 2}Text=a, Long=1 ...with label: <div class="x">p, q</div>'
    (result,) = actione.build_action([], line, ET.Element("code"), 0, "IND", state=_state(pretty=True))
    assert "p, q</div>" in result  # the comma inside the label's markup is not turned into a line break


def test_pretty_mode_leaves_a_plain_label_unaligned() -> None:
    line = f"{NAME.format('Flash')}{BLANK * 2}Text=a ...with label: Hi"
    (result,) = actione.build_action([], line, ET.Element("code"), 0, "IND", state=_state(pretty=True))
    assert result == line


def test_an_action_with_nothing_to_show_is_reported_as_unmapped(monkeypatch: pytest.MonkeyPatch) -> None:
    reported: list[tuple] = []
    monkeypatch.setattr(actione, "not_in_dictionary", lambda *args: reported.append(args))
    code = ET.Element("code")
    code.text = "424242"

    (result,) = actione.build_action([], "", code, 0, "", state=_state(pretty=False))

    assert "Action 424242: not yet mapped" in result
    assert reported == [("Action", "424242")]
