"""MapTasker "What Fires When?" Simulator Unit Tests

firesim reads nothing but the lookup tables taskerd builds, so these tests build them
from a small XML fixture -- the same way tests/test_proflint.py does -- and ask it about
particular moments.  Each condition kind it can judge is here with a moment that makes it
true and one that makes it false, and each kind it cannot judge is here to prove it is
left open rather than guessed at: that is the half that stops a working Profile being
reported as one that will not fire.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime

import pytest
from maptasker.src import firesim, taskerd
from maptasker.src.initparg import ProgramArguments
from maptasker.src.primitem import PrimeItems

#   Profile 1 'Work Hours'  Time 09:00-17:00 AND Day Mon-Fri, priority 10.  Entry Task 50
#                           turns WiFi Off.
#   Profile 2 'Office'      Wifi Connected to Office/Office-5G.  Entry Task 51 turns WiFi On
#                           -> a SETTING collision with Profile 1 at 10:00 on a weekday.
#   Profile 3 'Low Battery' Battery Level 0-20.  Entry Task 52.
#   Profile 4 'Maps'        App Maps.  Entry Task 52 too -> SAME-TASK with Profile 3;
#                           Task 52 is 'Abort Existing Task'.
#   Profile 5 'Night'       Time 22:00-06:00, which wraps past midnight.
#   Profile 6 'Chime'       Time 08:00-12:00 repeating every 30 minutes.
#   Profile 7 'Notified'    an Event -> never more than possible.
#   Profile 8 'Switched Off' disabled.
#   Profile 9 'Away'        Wifi Connected to Home, inverted.
#   Profile 10 'Sunset'     Time from a variable -> unknown.
_SIM_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2">
    <name>Home</name>
    <pids>1,2,3,4,5,6,7,8,9,10</pids>
    <tids>50,51,52,53</tids>
  </Project>
  <Profile sr="prof1" ve="2">
    <id>1</id><nme>Work Hours</nme><mid0>50</mid0><pri>10</pri>
    <Time sr="con0"><fh>9</fh><fm>0</fm><th>17</th><tm>0</tm></Time>
    <Day sr="con1"><wday0>2</wday0><wday1>3</wday1><wday2>4</wday2><wday3>5</wday3><wday4>6</wday4></Day>
  </Profile>
  <Profile sr="prof2" ve="2">
    <id>2</id><nme>Office</nme><mid0>51</mid0>
    <State sr="con0" ve="2"><code>160</code><Str sr="arg0" ve="3">Office/Office-5G</Str>
      <Str sr="arg1" ve="3"/><Str sr="arg2" ve="3"/><Int sr="arg3" val="2"/></State>
  </Profile>
  <Profile sr="prof3" ve="2">
    <id>3</id><nme>Low Battery</nme><mid0>52</mid0>
    <State sr="con0" ve="2"><code>140</code><Int sr="arg0" val="0"/><Int sr="arg1" val="20"/></State>
  </Profile>
  <Profile sr="prof4" ve="2">
    <id>4</id><nme>Maps</nme><mid0>52</mid0>
    <App sr="con0" ve="2"><cls0>com.google.android.maps.MapsActivity</cls0><flags>2</flags>
      <label0>Maps</label0><pkg0>com.google.android.apps.maps</pkg0></App>
  </Profile>
  <Profile sr="prof5" ve="2">
    <id>5</id><nme>Night</nme><mid0>53</mid0>
    <Time sr="con0"><fh>22</fh><fm>0</fm><th>6</th><tm>0</tm></Time>
  </Profile>
  <Profile sr="prof6" ve="2">
    <id>6</id><nme>Chime</nme><mid0>53</mid0>
    <Time sr="con0"><fh>8</fh><fm>0</fm><rep>2</rep><repval>30</repval><th>12</th><tm>0</tm></Time>
  </Profile>
  <Profile sr="prof7" ve="2">
    <id>7</id><nme>Notified</nme><mid0>53</mid0>
    <Event sr="con0" ve="2"><code>461</code></Event>
  </Profile>
  <Profile sr="prof8" ve="2">
    <id>8</id><nme>Switched Off</nme><limit>true</limit><mid0>53</mid0>
    <Time sr="con0"><fh>0</fh><fm>0</fm><th>23</th><tm>59</tm></Time>
  </Profile>
  <Profile sr="prof9" ve="2">
    <id>9</id><nme>Away</nme><mid0>53</mid0>
    <State sr="con0" ve="2"><code>160</code><pin>true</pin><Str sr="arg0" ve="3">Home</Str>
      <Str sr="arg1" ve="3"/><Str sr="arg2" ve="3"/></State>
  </Profile>
  <Profile sr="prof10" ve="2">
    <id>10</id><nme>Sunset</nme><mid0>53</mid0>
    <Time sr="con0"><fromvar>%SunsetTime</fromvar><tovar>%SunriseTime</tovar></Time>
  </Profile>
  <Task sr="task50"><id>50</id><nme>Wifi Off</nme>
    <Action sr="act0" ve="7"><code>425</code><Int sr="arg0" val="0"/></Action>
  </Task>
  <Task sr="task51"><id>51</id><nme>Wifi On</nme>
    <Action sr="act0" ve="7"><code>425</code><Int sr="arg0" val="1"/></Action>
  </Task>
  <Task sr="task52"><id>52</id><nme>Shared</nme><rty>1</rty>
    <Action sr="act0" ve="7"><code>30</code><Int sr="arg1" val="5"/></Action>
  </Task>
  <Task sr="task53"><id>53</id><nme>Quiet</nme>
    <Action sr="act0" ve="7"><code>30</code><Int sr="arg1" val="1"/></Action>
  </Task>
</TaskerData>
"""

# Monday 28 September 2026.
_MONDAY = datetime.fromisoformat("2026-09-28T10:00")  # naive: a Time condition reads local time


@pytest.fixture(autouse=True)
def _loaded() -> None:
    """Build the PrimeItems lookup tables from the fixture, the way taskerd does from a file."""
    root = ET.fromstring(_SIM_XML)  # noqa: S314  (fixture text, defined in this file)
    PrimeItems.file_to_get = "fixture.xml"
    PrimeItems.xml_root = root
    PrimeItems.program_arguments = ProgramArguments(task_action_warning_limit=100)
    PrimeItems.tasker_root_elements = {
        "all_projects": taskerd.move_xml_to_table(root.findall("Project"), False, "name"),
        "all_profiles": taskerd.move_xml_to_table(root.findall("Profile"), True, "nme"),
        "all_tasks": taskerd.move_xml_to_table(root.findall("Task"), True, "nme"),
        "all_scenes": taskerd.move_xml_to_table(root.findall("Scene"), False, "nme"),
        "all_services": [],
    }


def _states(scenario: firesim.Scenario) -> dict[str, str]:
    """{Profile name: active/possible/inactive} for one scenario."""
    result = firesim.simulate(scenario)
    return {profile.target.name: profile.state for profile in result.active + result.possible + result.inactive}


def _profile(scenario: firesim.Scenario, name: str) -> firesim.ProfileResult:
    result = firesim.simulate(scenario)
    return next(profile for profile in result.active + result.possible + result.inactive if profile.target.name == name)


# ##################################################################################
# Time and day.
# ##################################################################################
def test_time_window_and_weekday() -> None:
    """09:00-17:00 on weekdays: in at 10:00 Monday, out at 18:00, and out on a Sunday."""
    assert _states(firesim.Scenario(_MONDAY))["Work Hours"] == firesim.ACTIVE
    assert _states(firesim.Scenario(_MONDAY.replace(hour=18)))["Work Hours"] == firesim.INACTIVE
    sunday = _profile(firesim.Scenario(_MONDAY.replace(day=27)), "Work Hours")
    assert sunday.state == firesim.INACTIVE
    assert sunday.ruled_out_by.label == "Day"


def test_time_window_wrapping_midnight() -> None:
    """22:00-06:00 holds at 23:30 and at 02:00, and not at noon."""
    assert _states(firesim.Scenario(_MONDAY.replace(hour=23, minute=30)))["Night"] == firesim.ACTIVE
    assert _states(firesim.Scenario(_MONDAY.replace(hour=2)))["Night"] == firesim.ACTIVE
    assert _states(firesim.Scenario(_MONDAY.replace(hour=12)))["Night"] == firesim.INACTIVE


def test_repeating_time_fires_only_on_its_ticks() -> None:
    """Every 30 minutes from 08:00: 10:00 is a tick, 10:10 is not and names the next one."""
    on_tick = _profile(firesim.Scenario(_MONDAY), "Chime")
    assert on_tick.state == firesim.ACTIVE
    assert on_tick.instant
    off_tick = _profile(firesim.Scenario(_MONDAY.replace(minute=10)), "Chime")
    assert off_tick.state == firesim.INACTIVE
    assert "next at 10:30" in off_tick.ruled_out_by.reason


def test_time_from_a_variable_is_left_open() -> None:
    """A window set by %SunsetTime is not something the scenario can settle."""
    assert _states(firesim.Scenario(_MONDAY))["Sunset"] == firesim.POSSIBLE


# ##################################################################################
# Wi-Fi, battery, app.
# ##################################################################################
def test_wifi_alternatives_and_not_connected() -> None:
    """'Office/Office-5G' takes either network, case-insensitively, and nothing else."""
    assert _states(firesim.Scenario(_MONDAY, wifi="office-5g"))["Office"] == firesim.ACTIVE
    assert _states(firesim.Scenario(_MONDAY, wifi="Cafe"))["Office"] == firesim.INACTIVE
    assert _states(firesim.Scenario(_MONDAY, wifi=""))["Office"] == firesim.INACTIVE


def test_inverted_wifi_condition() -> None:
    """'NOT connected to Home' holds on another network and when not connected at all."""
    assert _states(firesim.Scenario(_MONDAY, wifi="Office"))["Away"] == firesim.ACTIVE
    assert _states(firesim.Scenario(_MONDAY, wifi=""))["Away"] == firesim.ACTIVE
    assert _states(firesim.Scenario(_MONDAY, wifi="home"))["Away"] == firesim.INACTIVE


def test_unsimulated_inputs_are_left_open() -> None:
    """With no Wi-Fi, app or battery given, Profiles on them are possible, never ruled out."""
    states = _states(firesim.Scenario(_MONDAY))
    assert states["Office"] == states["Away"] == states["Maps"] == states["Low Battery"] == firesim.POSSIBLE


def test_battery_range_is_inclusive() -> None:
    """0-20%: 20 is in, 21 is out."""
    assert _states(firesim.Scenario(_MONDAY, battery=20))["Low Battery"] == firesim.ACTIVE
    assert _states(firesim.Scenario(_MONDAY, battery=21))["Low Battery"] == firesim.INACTIVE


def test_app_by_package_or_label() -> None:
    """The app in front matches by package, or by the label a user would type."""
    assert _states(firesim.Scenario(_MONDAY, app="com.google.android.apps.maps"))["Maps"] == firesim.ACTIVE
    assert _states(firesim.Scenario(_MONDAY, app="maps"))["Maps"] == firesim.ACTIVE
    assert _states(firesim.Scenario(_MONDAY, app="Chrome"))["Maps"] == firesim.INACTIVE
    assert _states(firesim.Scenario(_MONDAY, app=""))["Maps"] == firesim.INACTIVE


def test_event_is_only_ever_possible() -> None:
    """Whether an Event happens is not part of a scenario."""
    profile = _profile(firesim.Scenario(_MONDAY), "Notified")
    assert profile.state == firesim.POSSIBLE
    assert profile.instant
    assert [verdict.outcome for verdict in profile.waiting_on] == [firesim.UNKNOWN]


def test_disabled_profile_is_counted_not_simulated() -> None:
    """A switched-off Profile is active on nothing."""
    result = firesim.simulate(firesim.Scenario(_MONDAY))
    assert result.disabled == 1
    assert "Switched Off" not in _states(firesim.Scenario(_MONDAY))


# ##################################################################################
# The queue and its collisions.
# ##################################################################################
def test_queue_runs_higher_priority_first_and_marks_ties() -> None:
    """Work Hours (priority 10) starts first; the rest share the default and are tied."""
    result = firesim.simulate(firesim.Scenario(_MONDAY, wifi="Office", app="", battery=50))
    names = [run.profile.target.name for run in result.queue]
    assert names[0] == "Work Hours"
    assert not result.queue[0].tied
    assert all(run.tied for run in result.queue[1:])
    assert result.queue[0].profile.priority == 10
    assert result.queue[1].profile.priority == firesim.DEFAULT_PRIORITY


def test_profiles_on_different_triggers_that_disagree() -> None:
    """Work Hours and Office watch different things, are true together, and set WiFi both ways."""
    result = firesim.simulate(firesim.Scenario(_MONDAY, wifi="Office", app="", battery=50))
    settings = [collision for collision in result.collisions if collision.kind == firesim.SETTING]
    assert len(settings) == 1
    assert settings[0].certain
    assert "Work Hours" in settings[0].where.label
    assert "runs later, so the device is left On" in settings[0].detail

    # Off the office network the pair is not active together, and there is nothing to report.
    quiet = firesim.simulate(firesim.Scenario(_MONDAY, wifi="Cafe", app="", battery=50))
    assert not [collision for collision in quiet.collisions if collision.kind == firesim.SETTING]


def test_one_task_started_by_two_profiles() -> None:
    """Low Battery and Maps both start Task 'Shared', whose handling is Abort Existing Task."""
    result = firesim.simulate(firesim.Scenario(_MONDAY, app="Maps", battery=10))
    same = [
        collision
        for collision in result.collisions
        if collision.kind == firesim.SAME_TASK and collision.where.name == "Shared"
    ]
    assert len(same) == 1
    assert same[0].certain
    assert "Abort Existing Task" in same[0].detail


def test_collision_with_a_possible_profile_is_not_certain() -> None:
    """With the app unknown, Maps may or may not be active, and the collision says so."""
    result = firesim.simulate(firesim.Scenario(_MONDAY, battery=10))
    same = [
        collision
        for collision in result.collisions
        if collision.kind == firesim.SAME_TASK and collision.where.name == "Shared"
    ]
    assert len(same) == 1
    assert not same[0].certain
    assert "only if" in same[0].detail


def test_nothing_loaded() -> None:
    """With empty tables the answer is empty, not an error."""
    PrimeItems.tasker_root_elements = {"all_projects": {}, "all_profiles": {}, "all_tasks": {}}
    result = firesim.simulate(firesim.Scenario(_MONDAY))
    assert not result.active
    assert not result.possible
    assert not result.inactive
    assert not result.queue
    assert not result.collisions


# ##################################################################################
# Helpers the dialog uses.
# ##################################################################################
@pytest.mark.parametrize(
    ("pattern", "value", "expected"),
    [
        ("Home", "home", True),
        ("Home/Work", "Work", True),
        ("Home*", "Home-5G", True),
        ("Home+", "Home", False),
        ("!Home", "Work", True),
        ("!Home", "Home", False),
        ("Home.Net", "HomeXNet", False),
    ],
)
def test_tasker_pattern_matching(pattern: str, value: str, expected: bool) -> None:
    """Tasker's simple matching: alternatives, wildcards, negation, everything else literal."""
    assert firesim.tasker_matches(pattern, value) is expected


def test_pickers_are_filled_from_the_configuration() -> None:
    """Every network a condition names, split on '/', and every app a condition names."""
    assert firesim.wifi_networks() == ["Home", "Office", "Office-5G"]
    assert firesim.condition_apps() == {"com.google.android.apps.maps": "Maps"}
