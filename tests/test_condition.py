"""A Profile's conditions as the Map words them: Time, Day, State, Event, Application and Location."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from maptasker.src.core.actionc import load_arg_specs
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.mapgen import condition


def _element(text: str) -> ET.Element:
    return ET.fromstring(text)  # noqa: S314  (fixture text, defined in this file)


@pytest.fixture(autouse=True)
def _arg_specs() -> None:
    """A State or Event is worded from the argument-type table, which a run loads at start-up."""
    load_arg_specs()


# ##################################################################################
# Time
# ##################################################################################
def test_a_time_range_is_worded_from_and_to() -> None:
    item = _element("<Time><fh>9</fh><fm>5</fm><th>17</th><tm>0</tm></Time>")
    assert condition.condition_time(item, "") == "Time: from 9:05 to 17:00"


def test_a_time_with_no_end_has_no_to() -> None:
    assert condition.condition_time(_element("<Time><fh>9</fh><fm>0</fm></Time>"), "") == "Time: from 9:00"


def test_a_repeat_and_a_name_are_added() -> None:
    item = _element("<Time><fh>9</fh><fm>0</fm><rep>2</rep><repval>15</repval><cname>Work</cname></Time>")
    said = condition.condition_time(item, "")
    assert "repeat every 15 minutes" in said
    assert said.endswith(" Name=Work")


def test_a_repeat_counted_in_hours_says_hours() -> None:
    said = condition.condition_time(_element("<Time><fh>9</fh><fm>0</fm><rep>1</rep><repval>3</repval></Time>"), "")
    assert "repeat every 3 hours" in said


def test_times_held_in_variables_are_named_not_shown_as_midnight() -> None:
    """Tasker keeps "sunrise to sunset" as two variables.  The minutes used to be padded before
    anyone asked whether there were any, so the line read "from :00 to :00" and the variables,
    the only thing the condition says, were never reached.
    """
    item = _element("<Time><fromvar>%SunriseTime</fromvar><tovar>%SunsetTime</tovar></Time>")
    said = condition.condition_time(item, "")
    assert "%SunriseTime" in said
    assert "%SunsetTime" in said
    assert ":00" not in said


def test_a_time_part_nobody_mapped_is_said_so_in_words(monkeypatch: pytest.MonkeyPatch) -> None:
    """The result goes into the Profile's line as text, so it has to be text -- it was a pair, and a
    pair printed as "('...', None)" in the Map."""
    reported: list[tuple] = []
    monkeypatch.setattr(condition, "not_in_dictionary", lambda *args: reported.append(args))
    said = condition.condition_time(_element("<Time><zzz>q</zzz></Time>"), "")
    assert said == "q not yet mapped!"
    assert reported == [("Condition Time", "q")]


# ##################################################################################
# Day
# ##################################################################################
def test_days_of_the_week_month_and_months_are_listed() -> None:
    item = _element("<Day><wday>1</wday><wday>7</wday><mday>15</mday><mnth>0</mnth></Day>")
    said = condition.condition_day(item, "")
    assert "Days of Week: Sunday Saturday" in said
    assert "Days of Month: 15" in said
    assert "Months: January" in said


def test_a_day_condition_with_only_a_name_still_says_it() -> None:
    assert "Name=Holiday" in condition.condition_day(_element("<Day><cname>Holiday</cname></Day>"), "")


# ##################################################################################
# State and Event
# ##################################################################################
def test_a_state_is_named_with_its_settings() -> None:
    item = _element("<State><code>10</code><Int sr='arg0' val='1'/></State>")
    said = condition.condition_state(item, "", state=PrimeItems)
    assert said.startswith("State: Power")
    assert "inverted" not in said


def test_an_inverted_state_says_so() -> None:
    item = _element("<State><code>10</code><Int sr='arg0' val='1'/><pin>true</pin></State>")
    assert "<em>[inverted]</em>" in condition.condition_state(item, "", state=PrimeItems)


def test_debug_shows_a_states_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PrimeItems.program_arguments, "debug", True)
    item = _element("<State><code>10</code><Int sr='arg0' val='1'/></State>")
    assert "(code:10)" in condition.condition_state(item, "", state=PrimeItems)


def test_a_state_keeps_what_the_line_already_held() -> None:
    item = _element("<State><code>10</code><Int sr='arg0' val='1'/></State>")
    assert condition.condition_state(item, "Earlier, ", state=PrimeItems).startswith("Earlier, State: Power")


def test_an_event_is_named() -> None:
    said = condition.condition_event(_element("<Event><code>2087</code></Event>"), "", state=PrimeItems)
    assert said.startswith("Event: Fingerprint Gesture")


def test_an_event_with_no_code_is_not_one_tasker_wrote() -> None:
    assert condition.condition_event(_element("<Event/>"), "", state=PrimeItems) == "Event: (no code)"


def test_debug_shows_an_events_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PrimeItems.program_arguments, "debug", True)
    said = condition.condition_event(_element("<Event><code>2087</code></Event>"), "", state=PrimeItems)
    assert said.endswith("(code:2087)")


# ##################################################################################
# Application and Location
# ##################################################################################
def test_applications_are_listed_by_label() -> None:
    item = _element("<App><label>Chrome</label><label>Maps</label></App>")
    assert condition.condition_app(item, "") == "Application: Chrome Maps"


def test_an_application_matched_by_something_other_than_the_foreground_says_so() -> None:
    said = condition.condition_app(_element("<App><label>Chrome</label><flags>1</flags></App>"), "")
    assert "matching running services" in said


def test_a_location_is_worded_with_its_radius() -> None:
    item = _element("<Loc><lat>1.5</lat><long>2.5</long><rad>100</rad></Loc>")
    assert condition.condition_loc(item, "") == "Location with latitude 1.5 longitude 2.5 radius 100"


def test_a_location_without_a_latitude_says_nothing() -> None:
    assert condition.condition_loc(_element("<Loc/>"), "") == ""


# ##################################################################################
# Putting them together
# ##################################################################################
def test_a_profiles_conditions_are_joined_with_and() -> None:
    profile = _element(
        "<Profile><nme>x</nme><mid0>1</mid0><Time><fh>9</fh><fm>0</fm></Time>"
        "<State><code>10</code><Int sr='arg0' val='1'/></State><flags>1</flags></Profile>",
    )
    said = condition.parse_profile_condition(profile, PrimeItems)
    assert said.startswith("Time: from 9:00, <em>AND</em> State: Power")


def test_a_profile_with_no_conditions_has_none() -> None:
    assert condition.parse_profile_condition(_element("<Profile><nme>x</nme><id>1</id></Profile>"), PrimeItems) == ""
