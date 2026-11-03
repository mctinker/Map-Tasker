"""MapTasker Battery and Wake-up Audit (batteryaudit) Unit Tests

The audit finds what keeps the phone busy -- a Time condition that repeats, a Task that loops, Keep Device Awake, a repeating Profile
that goes online -- and scores each Project.  What is tested is, first, the arithmetic that is exact (how often a Profile repeats and
how many times that is in its window, the shortest Wait in a loop); then the rules that keep it from crying wolf, each of which
came from a real backup where it was wrong without it: a loop that can be left, or is paced by a dialog, or whose Wait is switched
off, is not a busy loop; and then the score, which is the worst finding plus a quarter of the rest.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from maptasker.src.analysis import batteryaudit, firesim, taskflow
from maptasker.src.core.actionc import action_codes
from maptasker.src.core.mapjump import text_report
from maptasker.src.core.primitem import PrimeItems

from tests.test_mapswap import _load
from tests.test_taskstep import _act, _cond, _i, _s, goto_block, goto_label, goto_number, labelled

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element


def wait(seconds: float = 0, *, ms: int = 0, minutes: int = 0) -> str:
    return _act("30", _i(0, ms), _i(1, f"{seconds:g}"), _i(2, minutes), _i(3, 0), _i(4, 0))


def wait_variable() -> str:
    return _act("30", _i(0, 0), '<Int sr="arg1"><var>%secs</var></Int>', _i(2, 0), _i(3, 0), _i(4, 0))


def flash(text: str = "x") -> str:
    return _act("548", _s(0, text), _i(1, 0), _i(2, 0))


def http() -> str:
    return _act("339", _s(2, "https://api.example.com/x"))


def perform(name: str) -> str:
    return _act("130", _s(0, name), _i(1, 5))


def stop(*, when: str = "") -> str:
    return _act("137", _i(0, 0), _s(1, ""), extra=_cond(when, 3, "1") if when else "")


def goto_if(number: int) -> str:
    """A Goto to an action number that carries a condition of its own."""
    return _act("135", _i(0, 0), _i(1, number), _s(2, ""), extra=_cond("%again", 3, "1"))


def disabled(action: str) -> str:
    return action.replace("</Action>", "<on>false</on></Action>")


def input_dialog() -> str:
    return _act("360", _s(1, "Say"), _s(2, "something"))


def time_condition(
    interval: int = 0, *, hours: bool = False, start: tuple[int, int] | None = None, end: tuple[int, int] | None = None
) -> str:
    parts = ["<Time sr='con0'>"]
    parts.append(f"<fh>{start[0] if start else -1}</fh><fm>{start[1] if start else -1}</fm>")
    parts.append(f"<th>{end[0] if end else -1}</th><tm>{end[1] if end else -1}</tm>")
    if interval:
        parts.append(f"<rep>{1 if hours else 2}</rep><repval>{interval}</repval>")
    parts.append("</Time>")
    return "".join(parts)


def profile(profile_id: int, name: str, condition: str, entry: int | None = None, *, off: bool = False) -> str:
    mid = f"<mid0>{entry}</mid0>" if entry is not None else ""
    limit = "<limit>true</limit>" if off else ""
    return (
        f'<Profile sr="prof{profile_id}" ve="2"><id>{profile_id}</id><nme>{name}</nme>{mid}{limit}{condition}</Profile>'
    )


def task(task_id: int, name: str, *actions: str, awake: bool = False) -> str:
    numbered = "".join(action.replace("act{}", f"act{n}") for n, action in enumerate(actions))
    extra = "<stayawake>true</stayawake>" if awake else ""
    return f'<Task sr="task{task_id}" ve="2"><id>{task_id}</id><nme>{name}</nme>{extra}{numbered}</Task>'


def project(name: str, profiles: str = "", tasks: str = "", *, off: bool = False) -> str:
    enbl = "<enbl>false</enbl>" if off else ""
    return f"<Project sr='p0' ve='2'><name>{name}</name>{enbl}<pids>{profiles}</pids><tids>{tasks}</tids></Project>"


def load(*parts: str) -> None:
    _load(f'<TaskerData sr="" dvi="1" tv="6.3.13">{"".join(parts)}</TaskerData>')


def scores() -> dict[str, batteryaudit.ProjectScore]:
    return {score.name: score for score in batteryaudit.audit(PrimeItems).projects}


def only() -> batteryaudit.Finding:
    (score,) = batteryaudit.audit(PrimeItems).projects
    (found,) = score.findings
    return found


# ##################################################################################
# How often a Time condition repeats -- and how many times a day that is
# ##################################################################################
def element(xml: str) -> Element:
    import xml.etree.ElementTree as ET

    return ET.fromstring(xml)


@pytest.mark.parametrize(
    ("condition", "minutes"),
    [
        (time_condition(12), 12),
        (time_condition(2, hours=True), 120),
        (time_condition(), 0),
        ("<Time><rep>2</rep><repval>0</repval></Time>", 0),
        ("<Time><fromvar>%t</fromvar><rep>2</rep><repval>5</repval></Time>", 0),
    ],
)
def test_how_often_a_time_condition_repeats_is_read_the_way_the_simulator_reads_it(
    condition: str, minutes: int
) -> None:
    assert firesim.repeat_minutes(element(condition)) == minutes


@pytest.mark.parametrize(
    ("condition", "interval", "ticks"),
    [
        (time_condition(1), 1, 1440),
        (time_condition(5, start=(8, 0), end=(20, 0)), 5, 145),
        (time_condition(60, start=(22, 0), end=(6, 0)), 60, 9),
        (time_condition(30, start=(18, 0)), 30, 12),
        ("<Time><fromvar>%t</fromvar><rep>2</rep><repval>10</repval></Time>", 10, 144),
        (time_condition(7, start=(9, 0), end=(9, 0)), 7, 1),
    ],
    ids=["all day", "a window", "past midnight", "start and no end", "set by a variable", "one moment"],
)
def test_how_many_times_a_day_a_repeating_condition_fires_comes_from_its_own_window(
    condition: str, interval: int, ticks: int
) -> None:
    assert batteryaudit.ticks_per_day(element(condition), interval) == ticks


# ##################################################################################
# Repeating Profiles
# ##################################################################################
@pytest.mark.parametrize(
    ("condition", "points"),
    [
        (time_condition(1), 40),
        (time_condition(5), 25),
        (time_condition(15), 12),
        (time_condition(1, hours=True), 5),
        (time_condition(3, hours=True), 1),
    ],
    ids=["every minute", "every 5", "every 15", "hourly", "every 3 hours"],
)
def test_a_repeating_profile_is_worth_more_the_oftener_it_repeats(condition: str, points: int) -> None:
    load(project("Home", "10", "1"), profile(10, "Poller", condition, 1), task(1, "Quiet", flash()))

    found = only()

    assert (found.kind, found.points) == (batteryaudit.REPEAT, points)
    assert found.where.label.startswith("Project 'Home' > Profile 'Poller'")


def test_the_wake_ups_a_day_are_in_the_finding_and_the_project() -> None:
    load(
        project("Home", "10", "1"),
        profile(10, "Poller", time_condition(5, start=(8, 0), end=(20, 0)), 1),
        task(1, "Q", flash()),
    )

    found = only()

    assert found.wakeups == 145
    assert "Repeats every 5 minutes: up to 145 wake-ups a day." in found.summary
    assert scores()["Home"].wakeups == 145


def test_a_time_condition_that_does_not_repeat_is_nothing() -> None:
    load(project("Home", "10", "1"), profile(10, "Once", time_condition(0, start=(8, 0)), 1), task(1, "Q", flash()))

    assert batteryaudit.audit(PrimeItems).projects == []


def test_a_profile_that_is_off_and_a_project_that_is_off_count_for_nothing() -> None:
    load(
        project("Off Project", "10", "1", off=True),
        project("On Project", "11", "2"),
        profile(10, "A", time_condition(1), 1),
        profile(11, "B", time_condition(1), 2, off=True),
        task(1, "T1", flash()),
        task(2, "T2", flash()),
    )

    assert batteryaudit.audit(PrimeItems).projects == []
    assert batteryaudit.audit(PrimeItems).profiles_checked == 0


# ##################################################################################
# Loops: what is a busy one and what is not
# ##################################################################################
def loop(*body: str, closing: str | None = None) -> str:
    """A Task made of `body` and then a Goto back to action 1 -- unconditional unless `closing` says otherwise."""
    load(project("Home", "", "1"), task(1, "Looper", *body, closing if closing is not None else goto_number(1)))
    return "ok"


@pytest.mark.parametrize(
    ("body", "points"),
    [
        ((flash(),), 40),
        ((flash(), wait(0.5)), 35),
        ((flash(), wait(ms=250)), 35),
        ((flash(), wait(5)), 30),
        ((flash(), wait(30)), 15),
        ((flash(), wait(minutes=10)), 5),
        ((flash(), wait(minutes=30)), 1),
        ((flash(), wait_variable()), 8),
    ],
    ids=["no Wait", "half a second", "250 ms", "5 seconds", "30 seconds", "10 minutes", "30 minutes", "a variable"],
)
def test_a_loop_that_cannot_end_is_worth_more_the_shorter_its_wait(body: tuple[str, ...], points: int) -> None:
    loop(*body)

    found = only()

    assert (found.kind, found.points) == (batteryaudit.LOOP, points)
    assert found.where.action == len(body) + 1, "the finding points at the Goto, by the number the Map prints"


def test_the_shortest_wait_in_a_loop_is_the_one_that_counts() -> None:
    loop(flash(), wait(60), wait(2), flash())

    assert "Loops every 2 seconds or so" in only().summary


def test_a_wait_that_is_switched_off_is_not_a_wait() -> None:
    loop(flash(), disabled(wait(5)))

    assert only().points == batteryaudit.LOOP_POINTS_NO_WAIT


def test_a_loop_that_a_condition_on_its_goto_can_end_is_a_job_that_finishes_not_a_busy_loop() -> None:
    loop(flash(), closing=goto_if(1))

    assert batteryaudit.audit(PrimeItems).projects == []


def test_a_loop_that_can_be_left_but_waits_is_scored_at_half() -> None:
    loop(flash(), wait(2), closing=goto_if(1))

    found = only()

    assert found.points == round(30 * batteryaudit.GUARDED_FRACTION), "a 2 second Wait is in the 'up to 5 seconds' row"
    assert found.summary.startswith("Can loop every 2 seconds")


@pytest.mark.parametrize(
    "leaving",
    [stop(when="%done"), stop(), _act("126", _s(0, ""), _i(1, 1))],
    ids=["conditional Stop", "Stop", "Return"],
)
def test_a_stop_or_return_in_the_loop_is_a_way_out(leaving: str) -> None:
    loop(flash(), leaving)

    assert batteryaudit.audit(PrimeItems).projects == []


def test_a_stop_that_names_another_task_is_not_a_way_out() -> None:
    other = _act("137", _i(0, 0), _s(1, "Other"))
    loop(flash(), other)

    assert only().points == batteryaudit.LOOP_POINTS_NO_WAIT


def test_a_loop_with_a_dialog_in_it_is_paced_by_the_person_answering_it() -> None:
    """The chat Task that asks, sends, and goes back round -- once per message, not once per tick."""
    loop(input_dialog(), flash())

    assert batteryaudit.audit(PrimeItems).projects == []


def test_a_dialog_that_is_switched_off_paces_nothing() -> None:
    loop(disabled(input_dialog()), flash())

    assert only().points == batteryaudit.LOOP_POINTS_NO_WAIT


def test_a_for_loop_and_its_own_gotos_are_not_loops() -> None:
    body = (
        _act("39", _s(0, "%i"), _s(1, "1:5"), _i(2, 0)),
        flash(),
        goto_block(2),
        _act("40"),
    )
    load(project("Home", "", "1"), task(1, "Counting", *body))

    assert batteryaudit.audit(PrimeItems).projects == []


def test_a_goto_that_goes_forward_is_not_a_loop() -> None:
    load(project("Home", "", "1"), task(1, "Skip", flash(), goto_number(4), flash(), flash()))

    assert batteryaudit.audit(PrimeItems).projects == []


def test_a_goto_by_label_that_lands_above_itself_is_a_loop() -> None:
    load(project("Home", "", "1"), task(1, "Looper", labelled(flash(), "again"), flash(), goto_label("again")))

    assert only().points == batteryaudit.LOOP_POINTS_NO_WAIT


def test_a_goto_that_is_switched_off_is_not_a_loop() -> None:
    load(project("Home", "", "1"), task(1, "Looper", flash(), disabled(goto_number(1))))

    assert batteryaudit.audit(PrimeItems).projects == []


def test_a_task_with_several_loops_is_one_finding_that_says_how_many_more() -> None:
    load(
        project("Home", "", "1"),
        task(1, "Many", flash(), goto_number(1), flash(), goto_number(3), flash(), goto_number(5)),
    )

    found = only()

    assert found.points == batteryaudit.LOOP_POINTS_NO_WAIT
    assert "2 other loops in this Task." in found.detail


# ##################################################################################
# Keep Device Awake
# ##################################################################################
def test_keep_device_awake_on_its_own_is_a_little() -> None:
    load(project("Home", "", "1"), task(1, "Awake", flash(), awake=True))

    found = only()

    assert (found.kind, found.points) == (batteryaudit.AWAKE, batteryaudit.AWAKE_POINTS)


def test_keep_device_awake_through_a_long_wait_is_more() -> None:
    load(project("Home", "", "1"), task(1, "Awake", flash(), wait(minutes=5), awake=True))

    found = only()

    assert found.points == batteryaudit.AWAKE_WAIT_POINTS
    assert "through a Wait of 5 minutes" in found.summary


def test_keep_device_awake_on_a_task_that_loops_is_what_taskers_own_text_warns_about() -> None:
    load(project("Home", "", "1"), task(1, "Awake", flash(), wait(10), goto_number(1), awake=True))

    kinds = {found.kind: found.points for found in scores()["Home"].findings}

    assert kinds[batteryaudit.AWAKE] == batteryaudit.AWAKE_LOOP_POINTS
    assert (
        "very quickly drain the battery"
        in next(f for f in scores()["Home"].findings if f.kind == batteryaudit.AWAKE).detail
    )


def test_keep_device_awake_counts_a_loop_that_finishes_too() -> None:
    """Tasker's warning is about a loop, not about a loop that never ends."""
    load(project("Home", "", "1"), task(1, "Awake", flash(), goto_if(1), awake=True))

    assert only().points == batteryaudit.AWAKE_LOOP_POINTS


# ##################################################################################
# A repeating Profile whose Task goes online
# ##################################################################################
def test_a_repeating_profile_whose_task_goes_online_is_a_poll() -> None:
    load(project("Home", "10", "1"), profile(10, "Poller", time_condition(5), 1), task(1, "Fetch", http()))

    found = {finding.kind: finding for finding in scores()["Home"].findings}

    assert found[batteryaudit.REPEAT].points == 25
    assert found[batteryaudit.POLL].points == 12
    assert "Goes online every 5 minutes: Task 'Fetch' uses HTTP Request." in found[batteryaudit.POLL].summary


def test_a_task_the_task_performs_counts_too() -> None:
    load(
        project("Home", "10", "1,2"),
        profile(10, "Poller", time_condition(5), 1),
        task(1, "Outer", perform("Inner")),
        task(2, "Inner", http()),
    )

    assert batteryaudit.POLL in {finding.kind for finding in scores()["Home"].findings}


def test_a_repeat_slower_than_an_hour_is_not_a_poll() -> None:
    load(project("Home", "10", "1"), profile(10, "Slow", time_condition(2, hours=True), 1), task(1, "Fetch", http()))

    assert {finding.kind for finding in scores()["Home"].findings} == {batteryaudit.REPEAT}


def test_a_repeating_profile_whose_task_stays_on_the_phone_is_not_a_poll() -> None:
    load(project("Home", "10", "1"), profile(10, "Poller", time_condition(5), 1), task(1, "Local", flash()))

    assert {finding.kind for finding in scores()["Home"].findings} == {batteryaudit.REPEAT}


def test_a_web_request_that_is_switched_off_does_not_make_a_poll() -> None:
    load(project("Home", "10", "1"), profile(10, "Poller", time_condition(5), 1), task(1, "Fetch", disabled(http())))

    assert {finding.kind for finding in scores()["Home"].findings} == {batteryaudit.REPEAT}


# ##################################################################################
# The score
# ##################################################################################
def test_a_project_scores_its_worst_finding_plus_a_quarter_of_the_rest() -> None:
    score = batteryaudit.ProjectScore(
        "P",
        [batteryaudit.Finding("P", batteryaudit.LOOP, _where(), points, "x") for points in (40, 20, 12, 4)],
    )

    assert score.points == 40 + round(0.25 * (20 + 12 + 4))


def test_a_score_is_held_to_one_hundred() -> None:
    score = batteryaudit.ProjectScore(
        "P", [batteryaudit.Finding("P", batteryaudit.LOOP, _where(), 40, "x") for _ in range(30)]
    )

    assert score.points == 100


@pytest.mark.parametrize(
    ("points", "band"),
    [
        (0, "None"),
        (1, "Light"),
        (14, "Light"),
        (15, "Moderate"),
        (39, "Moderate"),
        (40, "Heavy"),
        (69, "Heavy"),
        (70, "Severe"),
        (100, "Severe"),
    ],
)
def test_the_bands_begin_where_the_report_says(points: int, band: str) -> None:
    assert batteryaudit.band_of(points) == band


def test_many_mild_findings_do_not_outscore_one_bad_one() -> None:
    mild = "".join(task(n, f"T{n}", flash(), wait(minutes=30), goto_number(1)) for n in range(1, 31))
    load(
        project("Mild", "", ",".join(str(n) for n in range(1, 31))),
        mild,
        project("Bad", "", "99"),
        task(99, "Hot", flash(), goto_number(1)),
    )

    ranked = scores()

    assert ranked["Bad"].points > ranked["Mild"].points
    assert list(ranked)[0] == "Bad"


def test_projects_are_listed_worst_first_and_a_clean_one_is_left_out() -> None:
    load(
        project("Clean", "", "1"),
        project("Awake", "", "2"),
        project("Hot", "", "3"),
        task(1, "T1", flash()),
        task(2, "T2", flash(), awake=True),
        task(3, "T3", flash(), goto_number(1)),
    )

    assert [score.name for score in batteryaudit.audit(PrimeItems).projects] == ["Hot", "Awake"]


def test_a_task_in_no_project_is_scored_apart_and_named_as_such() -> None:
    load(task(1, "Loose", flash(), goto_number(1)))

    (score,) = batteryaudit.audit(PrimeItems).projects

    assert score.name == ""
    rows, _ = batteryaudit.run_battery_audit(PrimeItems)
    assert "Not in any Project" in text_report(rows)


# ##################################################################################
# The report
# ##################################################################################
def test_the_report_has_a_score_table_the_findings_and_the_weights_and_what_it_cannot_tell() -> None:
    load(
        project("Home", "10", "1"),
        profile(10, "Poller", time_condition(5), 1),
        task(1, "Fetch", http(), awake=True),
    )

    rows, counts = batteryaudit.run_battery_audit(PrimeItems)
    text = text_report(rows)

    assert counts["projects"] == 1 and counts["findings"] == 3 and counts["profiles"] == 1 and counts["tasks"] == 1
    for heading in ("SCORE BY PROJECT", "FINDINGS", "HOW THE SCORE IS WORKED OUT", "NOTE ON WHAT THIS CANNOT TELL"):
        assert heading in text, heading
    assert "Project 'Home'" in text
    assert "up to 1 minutes: 40" in text, "the weights are printed, so nobody has to take the score on trust"
    assert "not a measurement of any battery" in text


def test_every_row_that_names_a_place_points_at_it() -> None:
    load(
        project("Home", "10", "1"),
        profile(10, "Poller", time_condition(5), 1),
        task(1, "Loop", flash(), goto_number(1)),
    )

    rows, _ = batteryaudit.run_battery_audit(PrimeItems)
    targets = [row.target for row in rows if row.target is not None]

    assert {target.kind for target in targets} >= {"project", "profile", "task"}
    assert any(target.action == 2 for target in targets), "the loop's Goto, by its Map number"


def test_a_configuration_with_nothing_in_it_says_so_and_still_says_what_it_cannot_tell() -> None:
    load(project("Quiet", "", "1"), task(1, "Q", flash()))

    rows, counts = batteryaudit.run_battery_audit(PrimeItems)
    text = text_report(rows)

    assert counts["findings"] == 0 and counts["projects"] == 0
    assert "Nothing to report" in text and "NOTE ON WHAT THIS CANNOT TELL" in text


def test_the_report_is_written_as_the_text_that_is_shown(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    load(project("Home", "", "1"), task(1, "Loop", flash(), goto_number(1)))
    rows, _ = batteryaudit.run_battery_audit(PrimeItems)

    path = batteryaudit.write_battery_report(rows, PrimeItems)

    assert os.path.basename(path).startswith("MapTasker_Battery")
    with open(path, encoding="utf-8") as written:
        assert written.read() == text_report(rows)


# ##################################################################################
# What it stands on
# ##################################################################################
def test_every_pacing_action_is_an_action_tasker_still_has_by_that_name() -> None:
    """A rename in Tasker would quietly turn a paced loop back into a busy one."""
    names = {entry.name for key, entry in action_codes.items() if key.endswith("t")}

    assert batteryaudit.PACING_ACTIONS <= names


def test_the_wait_action_is_still_code_30_with_its_five_arguments_in_this_order() -> None:
    entry = action_codes["30t"]

    assert entry.name == "Wait"
    assert [argument.arg_name for argument in entry.args] == ["MS", "Seconds", "Minutes", "Hours", "Days"]


def test_a_stop_is_the_end_of_the_flow_the_graph_says_so() -> None:
    load(project("Home", "", "1"), task(1, "T", flash(), stop(), flash()))

    flow = taskflow.analyze_task_flow("1", "Home", state=PrimeItems)
    assert flow is not None

    assert taskflow.successors(flow)[1] == set()


def _where():
    from maptasker.src.core.mapjump import TASK, Target

    return Target(TASK, "1", "T")
