"""MapTasker "What Fires When?" Simulator Unit Tests

firesim reads nothing but the lookup tables taskerd builds, so these tests build them
from a small XML fixture -- the same way tests/test_proflint.py does -- and ask it about
particular moments.  Each condition kind it can judge is here with a moment that makes it
true and one that makes it false, and each kind it cannot judge is here to prove it is
left open rather than guessed at: that is the half that stops a working Profile being
reported as one that will not fire.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from maptasker.src.analysis import firesim
from maptasker.src.core.primitem import PrimeItems

# Monday 28 September 2026.
pytestmark = pytest.mark.usefixtures("_loaded")

_MONDAY = datetime.fromisoformat("2026-09-28T10:00")  # naive: a Time condition reads local time


def _states(scenario: firesim.Scenario) -> dict[str, str]:
    """{Profile name: active/possible/inactive} for one scenario."""
    result = firesim.simulate(scenario, state=PrimeItems)
    return {profile.target.name: profile.state for profile in result.active + result.possible + result.inactive}


def _profile(scenario: firesim.Scenario, name: str) -> firesim.ProfileResult:
    result = firesim.simulate(scenario, state=PrimeItems)
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
    result = firesim.simulate(firesim.Scenario(_MONDAY), state=PrimeItems)
    assert result.disabled == 1
    assert "Switched Off" not in _states(firesim.Scenario(_MONDAY))


# ##################################################################################
# The queue and its collisions.
# ##################################################################################
def test_queue_runs_higher_priority_first_and_marks_ties() -> None:
    """Work Hours (priority 10) starts first; the rest share the default and are tied."""
    result = firesim.simulate(firesim.Scenario(_MONDAY, wifi="Office", app="", battery=50), state=PrimeItems)
    names = [run.profile.target.name for run in result.queue]
    assert names[0] == "Work Hours"
    assert not result.queue[0].tied
    assert all(run.tied for run in result.queue[1:])
    assert result.queue[0].profile.priority == 10
    assert result.queue[1].profile.priority == firesim.DEFAULT_PRIORITY


def test_profiles_on_different_triggers_that_disagree() -> None:
    """Work Hours and Office watch different things, are true together, and set WiFi both ways."""
    result = firesim.simulate(firesim.Scenario(_MONDAY, wifi="Office", app="", battery=50), state=PrimeItems)
    settings = [collision for collision in result.collisions if collision.kind == firesim.SETTING]
    assert len(settings) == 1
    assert settings[0].certain
    assert "Work Hours" in settings[0].where.label
    assert "runs later, so the device is left On" in settings[0].detail

    # Off the office network the pair is not active together, and there is nothing to report.
    quiet = firesim.simulate(firesim.Scenario(_MONDAY, wifi="Cafe", app="", battery=50), state=PrimeItems)
    assert not [collision for collision in quiet.collisions if collision.kind == firesim.SETTING]


def test_one_task_started_by_two_profiles() -> None:
    """Low Battery and Maps both start Task 'Shared', whose handling is Abort Existing Task."""
    result = firesim.simulate(firesim.Scenario(_MONDAY, app="Maps", battery=10), state=PrimeItems)
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
    result = firesim.simulate(firesim.Scenario(_MONDAY, battery=10), state=PrimeItems)
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
    result = firesim.simulate(firesim.Scenario(_MONDAY), state=PrimeItems)
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
    assert firesim.wifi_networks(state=PrimeItems) == ["Home", "Office", "Office-5G"]
    assert firesim.condition_apps(state=PrimeItems) == {"com.google.android.apps.maps": "Maps"}
