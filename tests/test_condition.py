"""A Profile's conditions as the Map words them: Time, Day, State, Event, Application and Location."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest
from maptasker.src.core.actionc import load_arg_specs
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.mapgen import condition, profiles


def _element(text: str) -> ET.Element:
    return ET.fromstring(text)


@pytest.fixture(autouse=True)
def _arg_specs() -> None:
    """A State or Event is worded from the argument-type table, which a run loads at start-up."""
    load_arg_specs(state=PrimeItems)


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
# A plugin State or Event, with "display prettier output" on
# ##################################################################################
# A trimmed AutoNotification "Intercept" State, in the shape Tasker writes it: the plugin's settings in a Bundle (its
# blurb first), then the plugin's package, its activity and "Structure Output" as the last arguments.
_PLUGIN_STATE = """<State sr="con0" ve="2"><code>40830242</code>
<Bundle sr="arg0"><Vals sr="val">
<AllFields>false</AllFields><App>System UI</App><BigTextNames>&lt;null&gt;</BigTextNames>
<ExactApp>false</ExactApp><Title>Do not disturb turned on</Title>
<com.twofortyfouram.locale.intent.extra.BLURB>Notification App: System UI
Notification Title: Do not disturb turned on</com.twofortyfouram.locale.intent.extra.BLURB>
<plugininstanceid>75b73d68</plugininstanceid>
<plugintypeid>com.joaomgcd.autonotification.intent.IntentInterceptNotification</plugintypeid>
</Vals></Bundle>
<Str sr="arg1" ve="3">com.joaomgcd.autonotification</Str>
<Str sr="arg2" ve="3">com.joaomgcd.autonotification.activity.ActivityConfigNotificationInterceptTasker</Str>
<Int sr="arg3" val="1"/></State>"""


@pytest.fixture
def pretty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PrimeItems.program_arguments, "pretty", True)


def _lines_of(said: str) -> list[str]:
    """The text a State is worded as, one entry for each line the browser will show."""
    return [line.strip() for line in said.split("<br>")]


def _real_text_in(line: str) -> str:
    return line.replace("&nbsp;", "").strip()


@pytest.mark.usefixtures("pretty")
def test_a_plugin_states_parameters_each_get_a_line_of_their_own() -> None:
    said = condition.condition_state(_element(_PLUGIN_STATE), "", state=PrimeItems)
    lines = [_real_text_in(line) for line in _lines_of(said)]

    assert lines[0].endswith("Configuration Parameter(s):")
    for parameter in (
        "Notification App: System UI",
        "AllFields=false",
        "App=System UI",
        "Title=Do not disturb turned on",
    ):
        assert parameter in lines, f"{parameter!r} should be a line of its own: {lines}"
    # Not run together on one line, which is how an unbroken run of blanks looks to a browser.
    assert not [line for line in lines if line.count("=") > 1 or line.count(": ") > 1], lines


@pytest.mark.usefixtures("pretty")
def test_a_plugin_states_parameters_are_indented_under_the_first_and_with_blanks_that_hold() -> None:
    """The indentation is &nbsp;, which a browser keeps.  Plain spaces were collapsed, and the lines ran together."""
    said = condition.condition_state(_element(_PLUGIN_STATE), "", state=PrimeItems)

    for line in _lines_of(said)[1:]:
        if _real_text_in(line):
            assert line.startswith("&nbsp;"), f"{line!r} is not indented with blanks that hold"
    assert not re.search(r" {3,}", said), "a run of plain spaces collapses in a browser"


@pytest.mark.usefixtures("pretty")
def test_a_plugin_states_name_does_not_run_into_the_word_after_it() -> None:
    """The Profile line is aligned afterwards, and that strips every &nbsp; from the text after a line break."""
    said = condition.condition_state(_element(_PLUGIN_STATE), "", state=PrimeItems)

    assert "AutoNotification Intercept  Configuration Parameter(s):" in said
    aligned = profiles.align_html_text(f'<span class="profile_condition_color"><br>(State: {said}')
    assert "InterceptConfiguration" not in aligned
    assert "Intercept Configuration Parameter(s):" in re.sub(r"\s+", " ", aligned.replace("&nbsp;", " "))


@pytest.mark.usefixtures("pretty")
def test_a_plugin_states_parameters_leave_no_blank_line_before_the_next_argument() -> None:
    """The parameters end with a newline and the next argument begins with a comma: a blank line was left between."""
    said = condition.condition_state(_element(_PLUGIN_STATE), "", state=PrimeItems)

    assert not [line for line in _lines_of(said)[1:] if not _real_text_in(line)], _lines_of(said)


# The same plugin's Event: its parameters are worded and laid out by the same code as a State's.
_PLUGIN_EVENT = (
    _PLUGIN_STATE.replace("<State", "<Event")
    .replace("</State>", "</Event>")
    .replace("<code>40830242</code>", "<code>1520257414</code>")
)


@pytest.mark.usefixtures("pretty")
def test_a_plugin_events_name_does_not_run_into_the_word_after_it_either() -> None:
    """It did: "AutoNotification InterceptConfiguration Parameter(s):" -- the Event had the same fault as the State."""
    said = condition.condition_event(_element(_PLUGIN_EVENT), "", state=PrimeItems)

    aligned = profiles.align_html_text(f'<span class="profile_condition_color"><br>(Event: {said}')
    assert "InterceptConfiguration" not in aligned
    assert "Intercept Configuration Parameter(s):" in re.sub(r"\s+", " ", aligned.replace("&nbsp;", " "))
    assert [_real_text_in(line) for line in _lines_of(said)].count("AllFields=false") == 1


def test_a_plugin_states_parameters_are_on_one_line_when_the_output_is_not_pretty() -> None:
    """Unchanged: without "display prettier output" the parameters are a comma-separated list."""
    said = condition.condition_state(_element(_PLUGIN_STATE), "", state=PrimeItems)

    assert "<br>" not in said
    assert "Notification App: System UI, Notification Title: Do not disturb turned on" in said


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


@pytest.mark.parametrize(
    "bad", ["<wday/>", "<wday>0</wday>", "<wday>8</wday>", "<wday>x</wday>", "<mnth/>", "<mnth>12</mnth>", "<mday/>"]
)
def test_a_day_condition_with_an_empty_or_impossible_value_is_still_worded(bad: str) -> None:
    """Tasker writes what it writes; one odd value must not end the whole Map with an error."""
    said = condition.condition_day(_element(f"<Day><wday>2</wday>{bad}<cname>n</cname></Day>"), "")
    assert "Monday" in said
    assert "Name=n" in said
