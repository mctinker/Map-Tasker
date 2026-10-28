"""A Profile's conditions as text: naming an unnamed Profile after them and lining them up in pretty mode."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from maptasker.src.core.primitem import RunState
from maptasker.src.mapgen import profiles

from tests.doubles import fake_config, fake_state

B = "&nbsp;"


def _element(text: str) -> ET.Element:
    return ET.fromstring(text)


# ##################################################################################
# Naming a Profile after its conditions
# ##################################################################################
def test_the_priority_is_taken_out_before_the_conditions_are_broken_up() -> None:
    parts = profiles._split_conditions(f"Time: from 9:00 Priority:5{B}{B}State: Power")
    assert not any("Priority" in part for part in parts)


def test_a_conditions_equals_colon_equals_is_not_split() -> None:
    parts = profiles._split_conditions("Variable: %a =:= 5")
    assert any("-+-" in part for part in parts)  # held aside while splitting, restored in the name
    assert profiles._name_from_conditions(["", "%a-+-5"]) == ":%a=:=5"


def test_the_name_drops_the_class_a_condition_names_and_one_letter_leftovers() -> None:
    assert profiles._name_from_conditions(["Application", "com.example.MainClass", "x", "Chrome"]) == "Chrome"


def test_an_application_regains_the_colon_the_split_took() -> None:
    assert profiles._name_from_conditions(["", "Application"]) == "Application:"


def test_a_long_name_is_cut_to_the_length_a_name_may_be() -> None:
    tidied = profiles._tidy_condition_name("<em>x</em>" * 20)
    assert len(tidied) <= 35
    assert "<em>" not in tidied  # the markup goes when the name has to be cut


def test_a_short_name_is_left_whole() -> None:
    assert profiles._tidy_condition_name("short name") == "short name"


def test_a_name_loses_what_stood_in_front_of_an_equals_sign() -> None:
    assert "Priority" not in profiles._tidy_condition_name("abc=def Priority 5")


def test_a_profile_with_no_name_to_set_gets_none() -> None:
    assert profiles.set_name_to_condition("Time: from 9:00", "") == ""


def test_a_name_from_conditions_starts_with_a_star() -> None:
    assert profiles.set_name_to_condition("Time: from 9:00", "x").startswith("*")


def _state() -> RunState:
    return fake_state(tasker_root_elements={"all_profiles": {"12": {"name": ""}}})


def test_an_unnamed_profile_is_recorded_under_its_id() -> None:
    state = _state()
    profile = _element("<Profile sr='prof12'/>")
    config = fake_config(directory=False, pretty=False)

    html_name, name, conditions = profiles.conditions_to_name(
        profile, "Time: from 9:00", "x", "<b>x</b>", config, state
    )

    assert html_name == "<b>x</b>"
    assert name.endswith(".12 Unnamed")
    assert state.tasker_root_elements["all_profiles"]["12"]["name"] == name
    assert conditions == "Time: from 9:00"


def test_pretty_mode_breaks_the_conditions_at_their_commas() -> None:
    state = _state()
    profile = _element("<Profile sr='prof12'/>")
    config = fake_config(directory=False, pretty=True)

    _, _, conditions = profiles.conditions_to_name(profile, "Time: 9:00, State: Power", "x", "x", config, state)

    assert conditions == "Time: 9:00<br> State: Power"


def test_a_directory_entry_is_added_for_the_new_name(monkeypatch: pytest.MonkeyPatch) -> None:
    added: list[tuple] = []
    monkeypatch.setattr(profiles, "add_directory_item", lambda *args, **kwargs: added.append(args))
    state = _state()
    config = fake_config(directory=True, pretty=False)

    _, name, _ = profiles.conditions_to_name(_element("<Profile sr='prof12'/>"), "Time: 9:00", "x", "x", config, state)

    assert added == [("profiles", name)]


# ##################################################################################
# Debug mode and pretty mode extras
# ##################################################################################
def test_flags_are_decoded_in_debug_mode() -> None:
    said = profiles._profile_flags_html(_element("<Profile><flags>43</flags></Profile>"))
    assert "flags: 43" in said
    assert "Hide In Notification" in said
    assert "Collapsed" in said


def test_no_flags_say_nothing() -> None:
    assert profiles._profile_flags_html(_element("<Profile/>")) == ""


def test_flags_with_nothing_set_are_just_the_number() -> None:
    said = profiles._profile_flags_html(_element("<Profile><flags>0</flags></Profile>"))
    assert "flags: 0" in said
    assert "(" not in said


def test_extras_each_start_a_line_indented_one_space() -> None:
    assert profiles._prettify_profile_extras("a, b (c) [d]") == f"a<br>{B}b<br>{B}  (c)<br>{B}  [d]"


# ##################################################################################
# Lining the conditions up
# ##################################################################################
_OPEN = '<span class="profile_condition_color">'


def test_text_with_no_condition_in_it_is_returned_as_it_was() -> None:
    assert profiles.align_html_text("nothing to align here") == "nothing to align here"


def test_continuation_lines_hang_under_the_first_condition() -> None:
    aligned = profiles.align_html_text(f"{_OPEN}(Time: from 9:00<br>more")
    first, rest = aligned.split("<br>")
    assert first == f"{_OPEN}(Time: from 9:00"
    assert rest.endswith("more")
    assert rest.startswith(B * 20)  # the lead-in of the Profile line plus the label


def test_an_and_starts_its_own_line_and_the_next_condition_follows_it() -> None:
    aligned = profiles.align_html_text(f"{_OPEN}(Time: from 9:00<br>x<em>AND</em> State: Power")
    assert "<em>AND</em><br>" in aligned
    assert aligned.endswith("State: Power")


def test_the_disabled_marker_and_the_priority_each_start_a_line() -> None:
    aligned = profiles.align_html_text(f"{_OPEN}(Time: from 9:00 [&#9940;&nbsp;DISABLED] Priority:5")
    assert "<br>" + B in aligned  # indented
    assert aligned.count("<br>") == 2
    assert "[&#9940;&nbsp;DISABLED]" in aligned
    assert "Priority:5" in aligned


def test_a_disabled_line_is_indented_less_and_so_is_everything_after_it() -> None:
    parts: list[str] = []
    after = profiles._align_condition_text("[&#9940;DISABLED]", 30, parts)
    assert after == 22
    assert parts == [B * 30 + "[&#9940;&nbsp;DISABLED]"]  # not a condition label, so 8 further in than the others


def test_a_line_that_names_a_condition_lines_up_with_the_first() -> None:
    parts: list[str] = []
    profiles._align_condition_text("State: Power", 30, parts)
    assert parts == [B * 30 + "State: Power"]


def test_a_continuation_of_a_condition_is_pushed_in_further() -> None:
    parts: list[str] = []
    profiles._align_condition_text("Set=AC", 30, parts)
    assert parts == [B * 38 + "Set=AC"]


# A time's colon is part of the time.  The conditions are broken at their colons to get at the pieces,
# and the name is made of the pieces put back together -- so a split at the time's colon lost it, and a
# Profile named after its conditions read "from 900 to 1700".
def test_a_time_is_not_broken_at_its_colon() -> None:
    parts = profiles._split_conditions("Time: from 9:00 to 17:00")
    assert parts == ["Time", " from 9:00 to 17:00"]


def test_a_name_made_of_a_time_keeps_the_colons_of_it() -> None:
    assert profiles.set_name_to_condition("Time: from 9:00 to 17:00", "x") == "*from 9:00 to 17:00"


def test_every_time_in_the_conditions_keeps_its_colons() -> None:
    name = profiles.set_name_to_condition(f"Day: Mon{B}Time: from 22:30 until 6:15", "x")
    assert "from 22:30 until 6:15" in name


def test_a_label_followed_by_a_number_is_still_broken_at_its_colon() -> None:
    """Only a colon with a digit on each side is a time."""
    assert profiles._split_conditions("Net: 5G") == ["Net", " 5G"]
