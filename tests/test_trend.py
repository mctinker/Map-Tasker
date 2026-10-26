"""MapTasker trend (trend) Unit Tests

A trend is only worth showing if each number in it means what its label says, so the first half of this file measures
small configurations built to have exactly one thing to count -- a Task of a known length, a block nested to a known
depth, a chain of calls of a known height -- and the second half is about the history: that a snapshot is measured once,
that two snapshots with the same content are still two points in time, and that a verdict is only given when the
numbers support one.

The history is a real one, in a temporary folder, made with timeline.record; nothing here reads the user's.
"""

from __future__ import annotations

import gzip
from datetime import UTC, datetime
from pathlib import Path

import pytest
from maptasker.src.analysis import healthck, timecomp
from maptasker.src.core import timeline
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.mapops import trend

from tests.shared_fixtures import _load_local
from tests.test_taskstep import _act, _i, _s, disabled, end_for, end_if, flash, for_, if_, set_

pytestmark = pytest.mark.usefixtures("_runtime")


def perform(name: str) -> str:
    return _act("130", _s(0, name), _i(1, 5), _s(2, ""), _s(3, ""), _s(4, ""))


def config(**projects: dict[str, tuple[str, ...]]) -> str:
    """A configuration of Projects, each holding Tasks.  `config(Home={'Wake': (...actions...)})`."""
    body, number = "", 0
    for project, tasks in projects.items():
        ids = []
        for name, actions in tasks.items():
            number += 1
            ids.append(str(number))
            numbered = "".join(action.replace("act{}", f"act{index}") for index, action in enumerate(actions))
            body += (
                f'<Task sr="task{number}" ve="2"><id>{number}</id><nme>{name.replace("_", " ")}</nme>{numbered}</Task>'
            )
        body = f'<Project sr="proj{number}" ve="2"><name>{project}</name><tids>{",".join(ids)}</tids></Project>' + body
    return f'<TaskerData sr="" dvi="1" tv="6.3.13">{body}</TaskerData>'


def measure(tmp_path: Path, **projects: dict[str, tuple[str, ...]]) -> tuple[trend.Measures, dict[str, trend.Measures]]:
    _load_local(tmp_path, config(**projects))
    total, per_project, _ = trend.measure_state(PrimeItems)
    return total, per_project


@pytest.fixture(autouse=True)
def _history(tmp_path: Path, _runtime: None):
    """Keep the history in a folder of the test's own, and put the default back.

    After _runtime, which loads a configuration and so records it: that load belongs in the working directory's
    history, not in the one these tests count the snapshots of.
    """
    timeline.use_history_folder(tmp_path / "history")
    yield
    timeline.use_history_folder(None)


# ##################################################################################
# Size, length and depth.
# ##################################################################################


def test_a_task_of_a_known_length_is_the_longest_and_one_over_the_limit_is_long(tmp_path: Path) -> None:
    total, projects = measure(
        tmp_path,
        Home={
            "Short": (flash("a"), flash("b")),
            "Long": tuple(flash(str(n)) for n in range(trend.LONG_TASK_ACTIONS + 5)),
        },
    )

    assert (total.longest_task, total.longest_task_name) == (trend.LONG_TASK_ACTIONS + 5, "Long")
    assert total.long_tasks == 1
    assert total.tasks == 2
    assert total.actions == 2 + trend.LONG_TASK_ACTIONS + 5
    assert projects["Home"].longest_task == total.longest_task


def test_a_task_exactly_at_the_limit_is_not_long(tmp_path: Path) -> None:
    total, _ = measure(tmp_path, Home={"Edge": tuple(flash(str(n)) for n in range(trend.LONG_TASK_ACTIONS))})

    assert total.long_tasks == 0


def test_nesting_depth_is_how_deep_the_blocks_go(tmp_path: Path) -> None:
    flat = (set_("%a", "1"),)
    nested = (if_("%a", 0, "1"), for_("%i", "1:2"), if_("%b", 0, "1"), set_("%c", "x"), end_if(), end_for(), end_if())

    total, projects = measure(tmp_path, Home={"Flat": flat, "Deep": nested})

    assert (total.max_depth, total.deepest_task) == (3, "Deep")
    assert projects["Home"].max_depth == 3


def test_projects_are_measured_separately(tmp_path: Path) -> None:
    total, projects = measure(
        tmp_path,
        Small={"One": (flash("a"),)},
        Big={"Two": (flash("a"), flash("b"), flash("c"), if_("%a", 0, "1"), flash("d"), end_if())},
    )

    assert projects["Small"].longest_task == 1
    assert projects["Big"].longest_task == 6
    assert projects["Big"].max_depth == 1
    assert projects["Small"].max_depth == 0
    assert total.tasks == projects["Small"].tasks + projects["Big"].tasks


def test_a_configuration_with_nothing_in_it_measures_as_zeroes(tmp_path: Path) -> None:
    total, projects = measure(tmp_path)

    assert total == trend.Measures()
    assert projects == {}


# ##################################################################################
# Call depth.
# ##################################################################################


def test_call_depth_is_how_many_performs_deep_the_longest_chain_goes(tmp_path: Path) -> None:
    total, projects = measure(
        tmp_path,
        Home={"A": (perform("B"),), "B": (perform("C"),), "C": (flash("end"),), "Lonely": (flash("x"),)},
    )

    assert total.call_depth == 2
    assert total.call_chain == ["A", "B", "C"]
    assert projects["Home"].call_depth == 2


def test_the_longest_of_several_chains_is_the_one_reported(tmp_path: Path) -> None:
    total, _ = measure(
        tmp_path,
        Home={"A": (perform("B"), perform("C")), "B": (flash("x"),), "C": (perform("D"),), "D": (flash("y"),)},
    )

    assert total.call_chain == ["A", "C", "D"]


def test_a_call_whose_name_is_a_variable_or_a_switched_off_call_or_a_missing_task_is_not_followed(
    tmp_path: Path,
) -> None:
    total, _ = measure(
        tmp_path,
        Home={"A": (perform("%which"), disabled(perform("B")), perform("Nobody"), perform("B")), "B": (flash("x"),)},
    )

    assert total.call_depth == 1, "only the one real call to B counts"


def test_tasks_that_call_each_other_are_counted_as_recursive_and_do_not_hang(tmp_path: Path) -> None:
    total, _ = measure(tmp_path, Home={"A": (perform("B"),), "B": (perform("A"),), "Self": (perform("Self"),)})

    assert total.recursive >= 2
    assert total.call_depth >= 1


def test_a_chain_can_cross_projects(tmp_path: Path) -> None:
    _, projects = measure(tmp_path, First={"A": (perform("B"),)}, Second={"B": (perform("C"),), "C": (flash("x"),)})

    assert projects["First"].call_depth == 2, "A calls B, which calls C, in another Project"
    assert projects["Second"].call_depth == 1


# ##################################################################################
# Findings.
# ##################################################################################


def test_a_broken_call_is_an_error_in_the_project_that_made_it(tmp_path: Path) -> None:
    total, projects = measure(tmp_path, Good={"Fine": (flash("a"),)}, Bad={"Broken": (perform("Does Not Exist"),)})

    assert projects["Bad"].errors >= 1
    assert projects["Good"].errors == 0
    assert total.errors >= projects["Bad"].errors


def test_the_check_for_plugins_missing_from_the_device_is_left_out_because_it_asks_the_device_not_the_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[object] = []
    real = healthck.collect_findings

    def spy(skip: object = (), *, state: object) -> object:
        asked.append(skip)
        return real(skip, state=state)

    monkeypatch.setattr(trend.healthck, "collect_findings", spy)

    measure(tmp_path, Home={"A": (flash("a"),)})

    assert asked
    assert set(asked[0]) == set(trend.plugchk.TAGS | trend.resrefs.TAGS)


def test_what_is_found_is_the_same_each_time_it_is_measured(tmp_path: Path) -> None:
    first = measure(tmp_path, Home={"A": (perform("Gone"),)})
    second = measure(tmp_path, Home={"A": (perform("Gone"),)})

    assert first == second


# ##################################################################################
# Keeping what is measured.
# ##################################################################################


def _snapshot(tmp_path: Path, name: str, xml: str, when: datetime) -> timeline.Snapshot:
    """Write a configuration and keep it in the history as it stood at `when`."""
    path = tmp_path / name
    path.write_text(xml, encoding="utf-8")
    taken = timeline.record(str(path), when=when)
    assert taken is not None
    return taken


def _at(day: int, hour: int = 12) -> datetime:
    return datetime(2026, 9, day, hour, 0, 0, tzinfo=UTC).astimezone()


def test_a_snapshot_is_measured_once_and_then_read_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot = _snapshot(tmp_path, "backup.xml", config(Home={"A": (flash("a"), flash("b"))}), _at(1))
    first, problem = trend.measure_snapshot(snapshot, PrimeItems)
    assert problem == ""

    monkeypatch.setattr(timecomp, "configuration_of", lambda *_a, **_k: pytest.fail("read the snapshot again"))
    again, problem = trend.measure_snapshot(snapshot, PrimeItems)

    assert problem == ""
    assert again == first
    assert first is not None
    assert first.total.actions == 2


def test_metrics_survive_being_kept_and_read_back_as_text(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path, "backup.xml", config(Home={"A": (perform("B"),), "B": (flash("x"),)}), _at(1))
    metrics, _ = trend.measure_snapshot(snapshot, PrimeItems)

    assert metrics is not None
    assert trend.SnapshotMetrics.from_json(metrics.to_json()) == metrics


def test_metrics_from_an_older_release_are_measured_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot = _snapshot(tmp_path, "backup.xml", config(Home={"A": (flash("a"),)}), _at(1))
    trend.measure_snapshot(snapshot, PrimeItems)
    monkeypatch.setattr(trend, "METRICS_VERSION", trend.METRICS_VERSION + 1)

    reads: list[int] = []
    real = timecomp.configuration_of
    monkeypatch.setattr(timecomp, "configuration_of", lambda *a, **k: (reads.append(1), real(*a, **k))[1])
    trend.measure_snapshot(snapshot, PrimeItems)

    assert reads == [1]


def test_metrics_that_cannot_be_read_are_measured_again_not_trusted(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path, "backup.xml", config(Home={"A": (flash("a"),)}), _at(1))
    trend.measure_snapshot(snapshot, PrimeItems)
    for kept in (timeline.history_folder() / trend.METRICS_FOLDER).glob("*.json"):
        kept.write_text("{ not json", encoding="utf-8")

    metrics, problem = trend.measure_snapshot(snapshot, PrimeItems)

    assert problem == ""
    assert metrics is not None
    assert metrics.total.actions == 1


def test_the_same_content_loaded_twice_is_two_points_in_time(tmp_path: Path) -> None:
    """A backup restored from last month is the same content as then, loaded now."""
    older = config(Home={"A": (flash("a"),)})
    newer = config(Home={"A": (flash("a"), flash("b"))})
    _snapshot(tmp_path, "one.xml", older, _at(1))
    _snapshot(tmp_path, "two.xml", newer, _at(2))
    _snapshot(tmp_path, "three.xml", older, _at(3))

    series = trend.build_series(PrimeItems)

    assert [point.total.actions for point in series.points] == [1, 2, 1]
    assert [point.moment.day for point in series.points] == [1, 2, 3]


# ##################################################################################
# A run of snapshots.
# ##################################################################################


def test_a_series_is_every_snapshot_in_order_with_its_progress_reported(tmp_path: Path) -> None:
    for day in (3, 1, 2):
        _snapshot(tmp_path, f"b{day}.xml", config(Home={"A": tuple(flash(str(n)) for n in range(day))}), _at(day))
    progress = trend.Progress()

    series = trend.build_series(PrimeItems, progress=progress)

    assert [point.total.actions for point in series.points] == [1, 2, 3]
    assert (progress.done, progress.total) == (3, 3)
    assert series.problems == []
    assert not series.stopped


def test_a_snapshot_that_cannot_be_read_is_reported_and_the_rest_are_still_measured(tmp_path: Path) -> None:
    _snapshot(tmp_path, "good.xml", config(Home={"A": (flash("a"),)}), _at(1))
    bad = _snapshot(tmp_path, "bad.xml", config(Home={"A": (flash("a"), flash("b"))}), _at(2))
    with gzip.open(bad.path, "wb") as damaged:
        damaged.write(b"this is not xml")

    series = trend.build_series(PrimeItems)

    assert len(series.points) == 1
    assert len(series.problems) == 1
    assert "bad.xml" in series.problems[0]


def test_stop_ends_the_series_between_snapshots_with_what_was_measured(tmp_path: Path) -> None:
    import threading

    for day in (1, 2, 3):
        _snapshot(tmp_path, f"b{day}.xml", config(Home={"A": tuple(flash(str(n)) for n in range(day))}), _at(day))
    stop = threading.Event()
    stop.set()

    series = trend.build_series(PrimeItems, stop=stop)

    assert series.stopped
    assert series.points == []


def test_a_family_is_the_file_name_without_a_timestamp() -> None:
    assert trend.family("backup_20261011_111635.xml") == "backup.xml"
    assert trend.family("backup-20261011-111635.xml") == "backup.xml"
    assert trend.family("backup.xml") == "backup.xml"
    assert trend.family("phone 2.xml") == "phone 2.xml"


def test_a_series_can_be_limited_to_one_family_of_file(tmp_path: Path) -> None:
    _snapshot(tmp_path, "backup_20260901_010101.xml", config(Home={"A": (flash("a"),)}), _at(1))
    _snapshot(tmp_path, "backup_20260902_010101.xml", config(Home={"A": (flash("a"), flash("b"))}), _at(2))
    _snapshot(tmp_path, "tablet.xml", config(Home={"A": (flash("a"),)}), _at(3))

    phone = trend.build_series(PrimeItems, "backup.xml")
    everything = trend.build_series(PrimeItems)

    assert len(phone.points) == 2
    assert len(everything.points) == 3
    assert trend.families() == ["backup.xml", "tablet.xml"]


def test_project_names_and_a_project_that_was_not_always_there(tmp_path: Path) -> None:
    _snapshot(tmp_path, "one.xml", config(Old={"A": (flash("a"),)}), _at(1))
    _snapshot(tmp_path, "two.xml", config(Old={"A": (flash("a"),)}, New={"B": (flash("b"),)}), _at(2))

    series = trend.build_series(PrimeItems)

    assert series.project_names() == ["New", "Old"]
    assert [measures is not None for _, measures in series.of_project("New")] == [False, True]


# ##################################################################################
# The verdict.
# ##################################################################################


def _m(**values: int) -> trend.Measures:
    return trend.Measures(**values)


def test_everything_that_fell_and_nothing_that_rose_is_healthier() -> None:
    verdict = trend.judge(_m(errors=5, warnings=10, longest_task=80), _m(errors=2, warnings=10, longest_task=60))

    assert verdict.label == trend.HEALTHIER
    assert {move.label for move in verdict.better} == {"Errors", "Longest Task (actions)"}


def test_everything_that_rose_and_nothing_that_fell_is_messier() -> None:
    assert trend.judge(_m(warnings=1), _m(warnings=4, max_depth=2)).label == trend.MESSIER


def test_some_up_and_some_down_is_about_the_same_not_netted_off() -> None:
    verdict = trend.judge(_m(errors=5, longest_task=10), _m(errors=1, longest_task=40))

    assert verdict.label == trend.STEADY
    assert verdict.better and verdict.worse


def test_nothing_changing_is_about_the_same() -> None:
    verdict = trend.judge(_m(errors=3), _m(errors=3))

    assert verdict.label == trend.STEADY
    assert "none of the numbers changed" in verdict.summary()


def test_growing_bigger_is_not_messier() -> None:
    assert (
        trend.judge(_m(tasks=10, actions=100, profiles=3), _m(tasks=50, actions=900, profiles=20)).label == trend.STEADY
    )


def test_a_project_that_was_not_there_has_no_verdict() -> None:
    assert trend.judge(None, _m()).label == trend.TOO_FEW
    assert trend.judge(_m(), None).label == trend.TOO_FEW


def test_the_summary_names_what_moved_most() -> None:
    summary = trend.judge(_m(errors=1, warnings=1), _m(errors=2, warnings=11)).summary()

    assert summary.startswith("Messier: warnings +10, errors +1")


def test_a_series_needs_two_points_for_a_verdict(tmp_path: Path) -> None:
    _snapshot(tmp_path, "one.xml", config(Home={"A": (flash("a"),)}), _at(1))

    whole, last = trend.overall(trend.build_series(PrimeItems))

    assert whole.label == last.label == trend.TOO_FEW


def test_the_whole_history_and_the_last_step_are_judged_separately(tmp_path: Path) -> None:
    _snapshot(tmp_path, "a.xml", config(Home={"A": (perform("Gone"),)}), _at(1))  # one error
    _snapshot(tmp_path, "b.xml", config(Home={"A": (flash("fine"),)}), _at(2))  # none
    _snapshot(tmp_path, "c.xml", config(Home={"A": (perform("Gone"), perform("Gone2"))}), _at(3))  # two

    whole, last = trend.overall(trend.build_series(PrimeItems))

    assert whole.label == trend.MESSIER, "from one error to two"
    assert last.label == trend.MESSIER
    assert [move.delta for move in whole.moves if move.label == "Errors"] == [1]
    assert [move.delta for move in last.moves if move.label == "Errors"] == [2]


def test_the_projects_that_moved_most_in_each_direction(tmp_path: Path) -> None:
    before = config(
        Worse={"A": (flash("a"),)}, Better={"B": (perform("Gone"), perform("Gone2"))}, Same={"C": (flash("c"),)}
    )
    after = config(
        Worse={"A": (perform("Gone"), perform("Gone2"), perform("Gone3"))},
        Better={"B": (flash("b"),)},
        Same={"C": (flash("c"),)},
    )
    _snapshot(tmp_path, "one.xml", before, _at(1))
    _snapshot(tmp_path, "two.xml", after, _at(2))

    worse, better = trend.movers(trend.build_series(PrimeItems))

    assert [mover.name for mover in worse] == ["Worse"]
    assert [mover.name for mover in better] == ["Better"]
    assert worse[0].problem_delta > 0 > better[0].problem_delta


def test_a_messier_project_names_the_problems_that_are_new(tmp_path: Path) -> None:
    _snapshot(tmp_path, "one.xml", config(Home={"A": (perform("Gone"),)}), _at(1))
    _snapshot(tmp_path, "two.xml", config(Home={"A": (perform("Gone"), flash("x"), perform("Missing"))}), _at(2))

    worse, _ = trend.movers(trend.build_series(PrimeItems))

    assert worse[0].problem_delta == 1
    assert len(worse[0].new_problems) == 1, "the first broken call was already there"
    assert worse[0].new_problems[0].is_error


def test_a_problem_that_moved_to_another_task_is_one_fixed_and_one_new(tmp_path: Path) -> None:
    _snapshot(tmp_path, "one.xml", config(Home={"A": (perform("Gone"),), "B": (flash("b"),)}), _at(1))
    _snapshot(tmp_path, "two.xml", config(Home={"A": (flash("a"),), "B": (perform("Gone"),)}), _at(2))

    series = trend.build_series(PrimeItems)
    new = trend.new_problems(series.points[0], series.points[1], "Home")

    assert len(new) == 1
    assert "B" in new[0].where


def test_nothing_is_new_when_the_problems_are_the_same(tmp_path: Path) -> None:
    _snapshot(tmp_path, "one.xml", config(Home={"A": (perform("Gone"),)}), _at(1))
    _snapshot(tmp_path, "two.xml", config(Home={"A": (perform("Gone"), flash("x"))}), _at(2))

    series = trend.build_series(PrimeItems)

    assert trend.new_problems(series.points[0], series.points[1], "Home") == []


def test_the_problems_are_kept_with_the_measurements(tmp_path: Path) -> None:
    _snapshot(tmp_path, "one.xml", config(Home={"A": (perform("Gone"),)}), _at(1))
    first = trend.build_series(PrimeItems).points[0]

    again = trend.SnapshotMetrics.from_json(first.to_json())

    assert again.problems == first.problems
    assert again.problems["Home"], "the broken call is kept"


def test_measurements_kept_before_problems_were_kept_still_read() -> None:
    text = trend.SnapshotMetrics("d", _at(1).isoformat(), "x.xml").to_json()
    old = text.replace(',"problems":{}', "")

    assert trend.SnapshotMetrics.from_json(old).problems == {}


def test_the_text_report_lists_the_new_problems_under_the_messier_project(tmp_path: Path) -> None:
    _snapshot(tmp_path, "one.xml", config(Home={"A": (flash("a"),)}), _at(1))
    _snapshot(tmp_path, "two.xml", config(Home={"A": (perform("Gone"), perform("Gone2"))}), _at(2))

    text = trend.as_text(trend.build_series(PrimeItems))

    assert "Messier:   Home" in text
    assert text.count("new: ERROR") == 2


def test_only_the_first_few_new_problems_are_spelled_out_and_the_rest_counted(tmp_path: Path) -> None:
    calls = tuple(perform(f"Gone{number}") for number in range(trend.NEW_PROBLEMS_SHOWN + 3))
    _snapshot(tmp_path, "one.xml", config(Home={"A": (flash("a"),)}), _at(1))
    _snapshot(tmp_path, "two.xml", config(Home={"A": calls}), _at(2))

    lines = trend.new_problem_lines(trend.movers(trend.build_series(PrimeItems))[0][0])

    assert len(lines) == trend.NEW_PROBLEMS_SHOWN + 1
    assert lines[-1] == "... and 3 more"


# ##################################################################################
# As text.
# ##################################################################################


def test_the_text_report_has_the_verdict_and_a_row_per_snapshot(tmp_path: Path) -> None:
    _snapshot(tmp_path, "a.xml", config(Home={"A": (flash("a"),)}), _at(1))
    _snapshot(tmp_path, "b.xml", config(Home={"A": (flash("a"), flash("b"), flash("c"))}), _at(2))

    text = trend.as_text(trend.build_series(PrimeItems))

    assert text.startswith("MapTasker trend: The whole configuration")
    assert "Since the first kept:" in text
    assert "01-Sep-2026" in text
    assert "02-Sep-2026" in text


def test_the_text_report_for_one_project_says_where_it_did_not_exist(tmp_path: Path) -> None:
    _snapshot(tmp_path, "a.xml", config(Old={"A": (flash("a"),)}), _at(1))
    _snapshot(tmp_path, "b.xml", config(Old={"A": (flash("a"),)}, New={"B": (flash("b"),)}), _at(2))

    text = trend.as_text(trend.build_series(PrimeItems), "New")

    assert "Project 'New'" in text
    assert "(not in this configuration)" in text


def test_with_one_snapshot_the_text_says_a_trend_needs_two(tmp_path: Path) -> None:
    _snapshot(tmp_path, "a.xml", config(Home={"A": (flash("a"),)}), _at(1))

    assert "Not enough history" in trend.as_text(trend.build_series(PrimeItems))
