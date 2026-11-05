"""MapTasker Profile Conflict Detector Unit Tests (effects, firesim.active_together, profconflict)

Three layers, each tested on its own and then through the Health Check:

  effects          what a Task leaves set -- a switch, a volume, the brightness, a global -- read off the Task
                   Stepper's walk and off what the Task always does;
  active_together whether two Profiles can be active at once, one input at a time;
  profconflict    the pairs of Profiles that can meet and leave something set two ways, and which of them wins.

Each rule is here with the pair it must report and the pair that looks the same and must not be: two Profiles on
different Wi-Fi networks, a condition and its NOT, a Task that sets a local variable.  A rule about two Profiles
disagreeing fails by firing on Profiles that never meet, and only the negative half of each test can catch that.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from maptasker.src.analysis import effects, firesim, profconflict
from maptasker.src.analysis.healthck import run_health_check
from maptasker.src.core.mapjump import text_report
from maptasker.src.core.primitem import PrimeItems

from tests.shared_fixtures import _load_local

pytestmark = pytest.mark.usefixtures("_runtime")


# ##################################################################################
# Building the configuration.
# ##################################################################################
def _act(code: str, *arguments: str, extra: str = "") -> str:
    return f'<Action sr="act{{}}" ve="7"><code>{code}</code>{"".join(arguments)}{extra}</Action>'


def _s(index: int, value: str) -> str:
    return f'<Str sr="arg{index}" ve="3">{value}</Str>'


def _i(index: int, value: int | str) -> str:
    return f'<Int sr="arg{index}" val="{value}"/>'


def media_volume(level: int | str) -> str:
    return _act("307", _i(0, level), _i(1, 0), _i(2, 0))


def brightness(level: int) -> str:
    return _act("810", _i(0, level), _i(1, 0), _i(2, 0), _i(3, 0))


def wifi(value: int) -> str:
    return _act("425", _i(0, value))


def set_variable(name: str, value: str) -> str:
    return _act("547", _s(0, name), _s(1, value), _i(2, 0), _i(3, 0), _i(4, 0), _i(5, 3))


def perform(task: str) -> str:
    return _act("130", _s(0, task), _i(1, 5), _s(2, ""), _s(3, ""), _s(4, ""))


def if_unknown_local() -> str:
    condition = '<Condition sr="c0" ve="3"><lhs>%mood</lhs><op>2</op><rhs>happy</rhs></Condition>'
    return _act("37", extra=f'<ConditionList sr="if">{condition}</ConditionList>')


def end_if() -> str:
    return _act("38")


def _task(task_id: int, name: str, *actions: str) -> str:
    numbered = "".join(action.replace("act{}", f"act{index}") for index, action in enumerate(actions))
    return f'<Task sr="task{task_id}" ve="2"><id>{task_id}</id><nme>{name}</nme>{numbered}</Task>'


def _time(start: tuple[int, int], end: tuple[int, int]) -> str:
    return f'<Time sr="con0"><fh>{start[0]}</fh><fm>{start[1]}</fm><th>{end[0]}</th><tm>{end[1]}</tm></Time>'


def _wifi_state(ssid: str, *, invert: bool = False) -> str:
    pin = "<pin>true</pin>" if invert else ""
    return f'<State sr="con0"><code>160</code>{pin}<Str sr="arg0" ve="3">{ssid}</Str></State>'


def _plugged(*, invert: bool = False) -> str:
    pin = "<pin>true</pin>" if invert else ""
    return f'<State sr="con0"><code>6</code>{pin}</State>'


def _profile(
    profile_id: int, name: str, conditions: str, task_id: int, *, priority: int | None = None, off: bool = False
) -> str:
    extra = (f"<pri>{priority}</pri>" if priority is not None else "") + ("<limit>true</limit>" if off else "")
    return f'<Profile sr="prof{profile_id}" ve="2"><id>{profile_id}</id><nme>{name}</nme>{conditions}<mid0>{task_id}</mid0>{extra}</Profile>'


def _configuration(*parts: str, tids: str, pids: str) -> str:
    return (
        '<TaskerData sr="" dvi="1" tv="6.3.13">'
        f'<Project sr="proj0" ve="2"><name>Home</name><pids>{pids}</pids><tids>{tids}</tids></Project>'
        f"{''.join(parts)}</TaskerData>"
    )


def load(tmp_path: Path, *parts: str, tids: str, pids: str) -> None:
    _load_local(tmp_path, _configuration(*parts, tids=tids, pids=pids))


def effects_of(tmp_path: Path, *actions: str, **others: tuple[str, ...]) -> dict[tuple, str]:
    """What the Task 'T', made of these actions, leaves set -- with any other Tasks beside it for it to perform."""
    tasks = [_task(1, "T", *actions)] + [
        _task(number, name.replace("_", " "), *body) for number, (name, body) in enumerate(others.items(), start=2)
    ]
    load(tmp_path, *tasks, tids=",".join(str(number) for number in range(1, len(tasks) + 1)), pids="")
    return effects.entry_effects("1", state=PrimeItems)


# ##################################################################################
# What a Task leaves set.
# ##################################################################################
def test_a_volume_a_brightness_a_switch_and_a_global(tmp_path: Path) -> None:
    left = effects_of(tmp_path, media_volume(3), brightness(40), wifi(1), set_variable("%Mode", "night"))

    assert left[(effects.LEVEL, "307")] == "3"
    assert left[(effects.LEVEL, "810")] == "40"
    assert left[(effects.VARIABLE, "Mode")] == "night"
    assert "On" in left.values()


def test_the_things_are_named_as_tasker_names_them(tmp_path: Path) -> None:
    left = effects_of(tmp_path, media_volume(3), set_variable("%Mode", "night"), wifi(1))
    names = sorted(effects.describe(subject) for subject in left)

    assert names == ["%Mode", "Media Volume", "WiFi"]


def test_the_last_value_written_is_the_one_left(tmp_path: Path) -> None:
    assert effects_of(tmp_path, media_volume(3), media_volume(9))[(effects.LEVEL, "307")] == "9"


def test_a_local_variable_is_not_a_setting(tmp_path: Path) -> None:
    """%mode is the Task's own and gone when it ends; only a global (a capital in the name) is left behind."""
    assert effects_of(tmp_path, set_variable("%mode", "night")) == {}


def test_a_level_from_a_variable_is_not_known(tmp_path: Path) -> None:
    assert effects_of(tmp_path, media_volume("%level")) == {}


def test_what_a_performed_task_sets_is_seen(tmp_path: Path) -> None:
    """The Task Stepper walks into Perform Task, so a Task that only calls another one still has the effects."""
    left = effects_of(tmp_path, perform("Quiet"), Quiet=(media_volume(1),))

    assert left[(effects.LEVEL, "307")] == "1"


def test_a_setting_after_a_decision_the_walk_cannot_make_is_still_found(tmp_path: Path) -> None:
    """The walk stops at an If on a variable only the device knows; what the Task always does is added to it."""
    left = effects_of(tmp_path, if_unknown_local(), media_volume(2), end_if(), wifi(0), media_volume(4))

    assert left[(effects.LEVEL, "307")] == "4"
    assert "Off" in left.values()


def test_a_setting_inside_an_if_the_walk_cannot_decide_is_not_claimed(tmp_path: Path) -> None:
    assert effects_of(tmp_path, if_unknown_local(), media_volume(2), end_if()) == {}


def test_a_disabled_action_sets_nothing(tmp_path: Path) -> None:
    disabled = media_volume(3).replace("</Action>", "<on>false</on></Action>")

    assert effects_of(tmp_path, disabled) == {}


def test_a_task_that_is_not_there_has_no_effects(tmp_path: Path) -> None:
    load(tmp_path, _task(1, "T", media_volume(3)), tids="1", pids="")

    assert effects.entry_effects("99", state=PrimeItems) == {}


# ##################################################################################
# Whether two Profiles can be active together.
# ##################################################################################
def _together(tmp_path: Path, first: str, second: str) -> firesim.Together | None:
    load(
        tmp_path,
        _profile(10, "A", first, 1),
        _profile(11, "B", second, 1),
        _task(1, "T", wifi(1)),
        tids="1",
        pids="10,11",
    )
    profiles = PrimeItems.tasker_root_elements["all_profiles"]
    return firesim.active_together(profiles["10"]["xml"], profiles["11"]["xml"])


def test_time_windows_that_overlap_can_be_active_together(tmp_path: Path) -> None:
    together = _together(tmp_path, _time((6, 0), (9, 0)), _time((8, 0), (12, 0)))

    assert together is not None
    assert together.shared
    assert together.example.startswith("at ")


def test_time_windows_that_do_not_touch_cannot(tmp_path: Path) -> None:
    assert _together(tmp_path, _time((6, 0), (9, 0)), _time((13, 0), (17, 0))) is None


def test_a_window_wrapping_midnight_meets_one_in_the_small_hours(tmp_path: Path) -> None:
    assert _together(tmp_path, _time((22, 0), (7, 0)), _time((6, 0), (9, 0))) is not None


def test_different_wifi_networks_cannot_both_be_connected(tmp_path: Path) -> None:
    assert _together(tmp_path, _wifi_state("Home"), _wifi_state("Office")) is None


def test_the_same_wifi_network_can(tmp_path: Path) -> None:
    together = _together(tmp_path, _wifi_state("Home"), _wifi_state("Home"))

    assert together is not None
    assert "'Home'" in together.example


def test_wifi_and_a_time_window_are_independent(tmp_path: Path) -> None:
    together = _together(tmp_path, _wifi_state("Home"), _time((22, 0), (7, 0)))

    assert together is not None
    assert not together.shared, "they watch different things"


def test_a_condition_and_its_not_cannot(tmp_path: Path) -> None:
    assert _together(tmp_path, _plugged(), _plugged(invert=True)) is None


def test_weekdays_that_do_not_meet(tmp_path: Path) -> None:
    mondays = '<Day sr="con0"><wday0>2</wday0></Day>'
    tuesdays = '<Day sr="con0"><wday0>3</wday0></Day>'

    assert _together(tmp_path, mondays, tuesdays) is None
    assert _together(tmp_path, mondays, mondays) is not None


def test_a_condition_that_cannot_be_judged_is_not_a_reason_to_rule_a_pair_out(tmp_path: Path) -> None:
    near = '<State sr="con0"><code>110</code></State>'

    assert _together(tmp_path, near, _wifi_state("Home")) is not None


def test_battery_ranges_that_do_not_overlap(tmp_path: Path) -> None:
    low = '<State sr="con0"><code>140</code><Int sr="arg0" val="0"/><Int sr="arg1" val="20"/></State>'
    high = '<State sr="con0"><code>140</code><Int sr="arg0" val="50"/><Int sr="arg1" val="100"/></State>'

    assert _together(tmp_path, low, high) is None


def test_an_instant_profile_is_recognised(tmp_path: Path) -> None:
    event = '<Event sr="con0"><code>208</code></Event>'
    load(tmp_path, _profile(10, "A", event, 1), _task(1, "T", wifi(1)), tids="1", pids="10")

    assert firesim.fires_at_a_moment(PrimeItems.tasker_root_elements["all_profiles"]["10"]["xml"])
    assert not firesim.fires_at_a_moment(_profile_element(tmp_path, _time((6, 0), (9, 0))))


def _profile_element(tmp_path: Path, conditions: str):
    load(tmp_path, _profile(10, "A", conditions, 1), _task(1, "T", wifi(1)), tids="1", pids="10")
    return PrimeItems.tasker_root_elements["all_profiles"]["10"]["xml"]


# ##################################################################################
# The pairs that conflict, and which of them wins.
# ##################################################################################
def _problems(tmp_path: Path, *parts: str, tids: str, pids: str) -> list[profconflict.Problem]:
    load(tmp_path, *parts, tids=tids, pids=pids)
    return profconflict.lint_problems(state=PrimeItems)


def _names(problems: list[profconflict.Problem]) -> set[frozenset[str]]:
    return {frozenset({problem.where.name, problem.related[0].name}) for problem in problems}


def _volumes(
    tmp_path: Path, first: str, second: str, *, home_priority: int | None = None, night_priority: int | None = None
) -> list[profconflict.Problem]:
    return _problems(
        tmp_path,
        _profile(10, "Home", first, 1, priority=home_priority),
        _profile(11, "Night", second, 2, priority=night_priority),
        _task(1, "Quiet", media_volume(3)),
        _task(2, "Loud", media_volume(7)),
        tids="1,2",
        pids="10,11",
    )


def test_different_triggers_that_meet_and_disagree_about_the_volume(tmp_path: Path) -> None:
    problems = _volumes(tmp_path, _wifi_state("Home"), _time((22, 0), (7, 0)))

    assert _names(problems) == {frozenset({"Home", "Night"})}
    assert problems[0].tag == profconflict.OVERLAP
    assert "Media Volume: 3 here, 7 there" in problems[0].detail


def test_independent_triggers_are_info_and_overlapping_ones_a_warning(tmp_path: Path) -> None:
    independent = _volumes(tmp_path, _wifi_state("Home"), _time((22, 0), (7, 0)))
    overlapping = _volumes(tmp_path, _time((6, 0), (9, 0)), _time((8, 0), (12, 0)))

    assert [problem.severity for problem in independent] == [profconflict.INFO]
    assert [problem.severity for problem in overlapping] == [profconflict.WARNING]


def test_profiles_that_cannot_be_active_together_are_not_reported(tmp_path: Path) -> None:
    assert _volumes(tmp_path, _wifi_state("Home"), _wifi_state("Office")) == []
    assert _volumes(tmp_path, _time((6, 0), (9, 0)), _time((13, 0), (17, 0))) == []
    assert _volumes(tmp_path, _plugged(), _plugged(invert=True)) == []


def test_profiles_that_agree_are_not_reported(tmp_path: Path) -> None:
    problems = _problems(
        tmp_path,
        _profile(10, "Home", _wifi_state("Home"), 1),
        _profile(11, "Night", _time((22, 0), (7, 0)), 2),
        _task(1, "Quiet", media_volume(3)),
        _task(2, "Quiet Too", media_volume(3)),
        tids="1,2",
        pids="10,11",
    )

    assert problems == []


def test_a_pair_on_the_very_same_trigger_is_left_to_the_health_checks_other_finding(tmp_path: Path) -> None:
    """PROFILE-CONFLICT already says so, and one pair should not be reported twice."""
    assert _volumes(tmp_path, _wifi_state("Home"), _wifi_state("Home")) == []


def test_one_task_started_by_two_profiles_cannot_disagree_with_itself(tmp_path: Path) -> None:
    problems = _problems(
        tmp_path,
        _profile(10, "Home", _wifi_state("Home"), 1),
        _profile(11, "Night", _time((22, 0), (7, 0)), 1),
        _task(1, "Quiet", media_volume(3)),
        tids="1",
        pids="10,11",
    )

    assert problems == []


def test_a_disabled_profile_is_left_out(tmp_path: Path) -> None:
    problems = _problems(
        tmp_path,
        _profile(10, "Home", _wifi_state("Home"), 1, off=True),
        _profile(11, "Night", _time((22, 0), (7, 0)), 2),
        _task(1, "Quiet", media_volume(3)),
        _task(2, "Loud", media_volume(7)),
        tids="1,2",
        pids="10,11",
    )

    assert problems == []


def test_a_profile_that_fires_at_an_instant_is_left_out(tmp_path: Path) -> None:
    event = '<Event sr="con0"><code>208</code></Event>'

    assert _volumes(tmp_path, event, _time((22, 0), (7, 0))) == []


def test_two_globals_set_differently_by_profiles_that_meet(tmp_path: Path) -> None:
    problems = _problems(
        tmp_path,
        _profile(10, "Work", _time((9, 0), (17, 0)), 1),
        _profile(11, "Focus", _time((10, 0), (12, 0)), 2),
        _task(1, "Work Mode", set_variable("%Mode", "work")),
        _task(2, "Focus Mode", set_variable("%Mode", "focus")),
        tids="1,2",
        pids="10,11",
    )

    assert len(problems) == 1
    assert "%Mode: work here, focus there" in problems[0].detail
    assert problems[0].severity == profconflict.WARNING


def test_a_brightness_set_through_a_performed_task_is_found(tmp_path: Path) -> None:
    problems = _problems(
        tmp_path,
        _profile(10, "Bright", _time((6, 0), (12, 0)), 1),
        _profile(11, "Dim", _time((11, 0), (23, 0)), 2),
        _task(1, "Go Bright", perform("Full")),
        _task(2, "Go Dim", brightness(10)),
        _task(3, "Full", brightness(100)),
        tids="1,2,3",
        pids="10,11",
    )

    assert "Display Brightness: 100 here, 10 there" in problems[0].detail


def test_several_disagreements_are_one_finding_for_the_pair(tmp_path: Path) -> None:
    problems = _problems(
        tmp_path,
        _profile(10, "Home", _wifi_state("Home"), 1),
        _profile(11, "Night", _time((22, 0), (7, 0)), 2),
        _task(1, "Quiet", media_volume(3), brightness(10), wifi(0)),
        _task(2, "Loud", media_volume(7), brightness(90), wifi(1)),
        tids="1,2",
        pids="10,11",
    )

    assert len(problems) == 1
    for setting in ("Media Volume", "Display Brightness", "WiFi"):
        assert setting in problems[0].detail


def test_the_lower_priority_profile_runs_last_and_wins(tmp_path: Path) -> None:
    """A higher priority starts first, so the lower one's Task runs last and the device keeps its value."""
    problems = _volumes(tmp_path, _time((6, 0), (9, 0)), _time((8, 0), (12, 0)), home_priority=7, night_priority=3)
    detail = problems[0].detail

    assert "Night" in detail
    assert "(priority 7) runs first" in detail
    assert "(priority 3) runs last" in detail
    assert "Media Volume 7" in detail, "the one that runs last leaves its own value, which is Night's 7"


def test_equal_priorities_have_no_fixed_winner(tmp_path: Path) -> None:
    detail = _volumes(tmp_path, _time((6, 0), (9, 0)), _time((8, 0), (12, 0)))[0].detail

    assert "same priority" in detail
    assert "not fixed" in detail


def test_the_finding_says_what_starting_at_different_times_does(tmp_path: Path) -> None:
    detail = _volumes(tmp_path, _time((6, 0), (9, 0)), _time((8, 0), (12, 0)))[0].detail

    assert "becomes active after the other" in detail


def test_each_profile_of_the_pair_is_one_jump_away(tmp_path: Path) -> None:
    problem = _volumes(tmp_path, _wifi_state("Home"), _time((22, 0), (7, 0)))[0]

    assert problem.where.name == "Home"
    assert [target.name for target in problem.related] == ["Night"]


def test_nothing_loaded_is_nothing_found() -> None:
    PrimeItems.tasker_root_elements = {"all_tasks": {}, "all_projects": {}, "all_profiles": {}}

    assert profconflict.lint_problems(state=PrimeItems) == []


# ##################################################################################
# In What Fires When, and in the Health Check
# ##################################################################################
def test_what_fires_when_now_sees_a_volume_collision(tmp_path: Path) -> None:
    load(
        tmp_path,
        _profile(10, "Work Hours", _time((9, 0), (17, 0)), 1, priority=10),
        _profile(11, "Office", _wifi_state("Office"), 2),
        _task(1, "Quiet", media_volume(3)),
        _task(2, "Loud", media_volume(7)),
        tids="1,2",
        pids="10,11",
    )

    result = firesim.simulate(firesim.Scenario(datetime.fromisoformat("2026-09-28T10:00"), wifi="Office"), PrimeItems)
    settings = [collision for collision in result.collisions if collision.kind == firesim.SETTING]

    assert len(settings) == 1
    assert "sets Media Volume 3" in settings[0].detail
    assert "Media Volume is left 7" in settings[0].detail


def test_the_health_check_reports_it_with_its_note(tmp_path: Path) -> None:
    load(
        tmp_path,
        _profile(10, "Home", _wifi_state("Home"), 1),
        _profile(11, "Night", _time((22, 0), (7, 0)), 2),
        _task(1, "Quiet", media_volume(3)),
        _task(2, "Loud", media_volume(7)),
        tids="1,2",
        pids="10,11",
    )

    rows, _counts = run_health_check(state=PrimeItems)
    report = text_report(rows)

    assert [line for line in report.splitlines() if line.startswith("[PROFILE-OVERLAP]")]
    assert "NOTE ON OVERLAPPING PROFILES" in report


def test_the_category_can_be_unticked(tmp_path: Path) -> None:
    load(
        tmp_path,
        _profile(10, "Home", _wifi_state("Home"), 1),
        _profile(11, "Night", _time((22, 0), (7, 0)), 2),
        _task(1, "Quiet", media_volume(3)),
        _task(2, "Loud", media_volume(7)),
        tids="1,2",
        pids="10,11",
    )

    rows, _counts = run_health_check(state=PrimeItems, skip=profconflict.TAGS)
    report = text_report(rows)

    assert not [line for line in report.splitlines() if line.startswith("[PROFILE-OVERLAP]")]
    assert "NOTE ON OVERLAPPING PROFILES" not in report
