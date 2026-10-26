"""MapTasker Live Run Monitor model (livemon) Unit Tests

A monitor is trusted to say what ran, so what is tested is that it says no more than it saw.  A sample is read back
exactly, a name with a comma in it is put back together from the backup and not guessed, a Task seen once is called
brief and its length is not invented, and the prediction comparison judges only what What Fires When was sure of.

No device is involved: the samples are written the way the helper Task writes them.
"""

from __future__ import annotations

from datetime import datetime

from maptasker.src.analysis import firesim, livemon
from maptasker.src.core.primitem import PrimeItems

from tests.test_resrefs import _load

#   Profile 100 'Dawn'   06:00-07:00, runs Task 20          Profile 101 'Dusk'  18:00-19:00, runs Task 22
#   Profile 102 'Twin'   twice, with 'Twin' in Project 'Away': two Profiles of one name
#   Profile 104 'Wired'  an Event (a Profile that fires and is gone)
#   Task 20 'Morning'    Task 21 'Quiet, Please' (a name holding a comma)    Task 22 'Evening'
_FIXTURE_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2"><name>Home</name><pids>100,101,104</pids><tids>20,21,22</tids></Project>
  <Project sr="proj1" ve="2"><name>Away</name><pids>102,103</pids><tids>23</tids></Project>
  <Profile sr="prof100" ve="2"><id>100</id><nme>Dawn</nme><mid0>20</mid0>
    <Time sr="con0"><fh>6</fh><fm>0</fm><th>7</th><tm>0</tm></Time></Profile>
  <Profile sr="prof101" ve="2"><id>101</id><nme>Dusk</nme><mid0>22</mid0>
    <Time sr="con0"><fh>18</fh><fm>0</fm><th>19</th><tm>0</tm></Time></Profile>
  <Profile sr="prof102" ve="2"><id>102</id><nme>Twin</nme><mid0>23</mid0>
    <Time sr="con0"><fh>6</fh><fm>0</fm><th>7</th><tm>0</tm></Time></Profile>
  <Profile sr="prof103" ve="2"><id>103</id><nme>Twin</nme><mid0>23</mid0>
    <Time sr="con0"><fh>6</fh><fm>0</fm><th>7</th><tm>0</tm></Time></Profile>
  <Profile sr="prof104" ve="2"><id>104</id><nme>Wired</nme><mid0>21</mid0>
    <Event sr="con0" ve="2"><code>2000</code></Event></Profile>
  <Task sr="task20" ve="2"><id>20</id><nme>Morning</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">hi</Str></Action></Task>
  <Task sr="task21" ve="2"><id>21</id><nme>Quiet, Please</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">shh</Str></Action></Task>
  <Task sr="task22" ve="2"><id>22</id><nme>Evening</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">bye</Str></Action></Task>
  <Task sr="task23" ve="2"><id>23</id><nme>Away Task</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">x</Str></Action></Task>
</TaskerData>
"""

HELPER = "MapTasker Monitor v1"


def _text(*samples: tuple[int, str, str, str]) -> str:
    """A window as the helper Task writes it: (time, running, active, battery) per look."""
    return "".join(livemon.FIELD_SEPARATOR.join(map(str, sample)) + livemon.SAMPLE_SEPARATOR for sample in samples)


def _load_fixture() -> livemon.NameIndex:
    _load(_FIXTURE_XML)
    return livemon.build_index(PrimeItems, ignore=[HELPER])


def _tracker() -> livemon.Tracker:
    return livemon.Tracker(_load_fixture())


def _sample(when: int, running: str = "", active: str = "", battery: int | None = 80) -> livemon.Sample:
    index = livemon.build_index(PrimeItems)
    return livemon.Sample(
        when,
        frozenset(livemon.split_names(running, index.tasks)),
        frozenset(livemon.split_names(active, index.profiles)),
        battery,
    )


# ##################################################################################
# Reading what the device wrote.
# ##################################################################################


def test_a_window_is_read_back_sample_by_sample() -> None:
    text = _text((1000, "Morning,Evening", "Dawn", "88"), (1200, "", "Dawn,Dusk", "87"))

    samples = livemon.parse_window(text)

    assert [s.when_ms for s in samples] == [1000, 1200]
    assert samples[0].running == {"Morning", "Evening"}
    assert samples[1].active == {"Dawn", "Dusk"}
    assert [s.battery for s in samples] == [88, 87]


def test_a_name_with_a_comma_is_put_back_together_from_the_names_in_the_backup() -> None:
    assert livemon.split_names("Quiet, Please,Morning", ["Quiet, Please", "Morning"]) == {"Quiet, Please", "Morning"}


def test_a_name_that_is_not_in_the_backup_is_taken_as_written() -> None:
    assert livemon.split_names("Stranger,Morning", ["Morning"]) == {"Stranger", "Morning"}


def test_the_longest_gluing_wins() -> None:
    """'A, B' could be one name or two; when the backup has the one, that is what it is."""
    assert livemon.split_names("A, B", ["A", "B", "A, B"]) == {"A, B"}


def test_a_list_tasker_left_unset_is_empty() -> None:
    samples = livemon.parse_window(_text((1000, "%TRUN", "%PACTIVE", "%BATT")))

    assert samples[0].running == frozenset()
    assert samples[0].active == frozenset()
    assert samples[0].battery is None


def test_a_record_that_is_cut_off_or_has_no_time_is_dropped_not_guessed() -> None:
    text = "garbage" + livemon.SAMPLE_SEPARATOR + _text((1000, "A", "B", "5")) + "12" + livemon.FIELD_SEPARATOR + "A"

    assert [s.when_ms for s in livemon.parse_window(text)] == [1000]


def test_a_sample_says_when_it_was_in_local_time() -> None:
    sample = livemon.Sample(0, frozenset(), frozenset())

    assert isinstance(sample.when, datetime)
    assert sample.when.tzinfo is None


# ##################################################################################
# The stream of events.
# ##################################################################################


def test_what_is_already_going_on_when_the_monitor_starts_is_said_to_be() -> None:
    tracker = _tracker()

    events = tracker.feed([_sample(1000, "Morning", "Dawn")])

    assert [(e.kind, e.name) for e in events] == [
        (livemon.PROFILE_ACTIVE, "Dawn"),
        (livemon.TASK_STARTED, "Morning"),
    ]
    assert all("already" in e.note for e in events)


def test_a_profile_that_becomes_active_and_then_inactive_is_two_events() -> None:
    tracker = _tracker()
    tracker.feed([_sample(1000)])

    events = tracker.feed([_sample(1200, active="Dawn"), _sample(1400, active="Dawn"), _sample(1600)])

    assert [(e.kind, e.name, e.when_ms) for e in events] == [
        (livemon.PROFILE_ACTIVE, "Dawn", 1200),
        (livemon.PROFILE_INACTIVE, "Dawn", 1600),
    ]


def test_a_task_that_runs_for_a_while_says_about_how_long() -> None:
    tracker = _tracker()
    tracker.feed([_sample(0)])

    events = tracker.feed([_sample(1000, "Morning"), _sample(2000, "Morning"), _sample(3500, "Morning"), _sample(4000)])

    finished = events[-1]
    assert (finished.kind, finished.name) == (livemon.TASK_FINISHED, "Morning")
    assert "about 3.0 s" in finished.note


def test_a_task_seen_once_is_called_brief_and_its_length_is_not_made_up() -> None:
    tracker = _tracker()
    tracker.feed([_sample(0)])

    events = tracker.feed([_sample(1000, "Morning"), _sample(1200)])

    assert "one sample only" in events[-1].note
    assert "length is not known" in events[-1].note


def test_the_monitors_own_task_is_never_reported() -> None:
    tracker = _tracker()

    events = tracker.feed([livemon.Sample(1000, frozenset({HELPER, "Morning"}), frozenset())])

    assert [e.name for e in events] == ["Morning"]


def test_a_name_the_backup_does_not_have_is_logged_and_says_so() -> None:
    tracker = _tracker()
    tracker.feed([_sample(0)])

    events = tracker.feed([_sample(1000, "Stranger")])

    assert events[0].targets == ()
    assert "(not in this backup)" in events[0].line()


def test_an_event_names_every_object_of_that_name() -> None:
    tracker = _tracker()
    tracker.feed([_sample(0)])

    events = tracker.feed([_sample(1000, active="Twin")])

    assert len(events[0].targets) == 2
    assert {t.key for t in events[0].targets} == {"102", "103"}


def test_an_event_is_a_line_of_a_log_with_the_time_in_milliseconds() -> None:
    tracker = _tracker()
    tracker.feed([_sample(0)])

    line = tracker.feed([_sample(1_700_000_000_123, "Morning")])[0].line()

    assert line.endswith("Task started: Morning")
    assert ".123" in line


def test_the_whole_log_is_kept_in_order_and_can_be_written_out() -> None:
    tracker = _tracker()
    tracker.feed([_sample(0)])
    tracker.feed([_sample(1000, "Morning")])
    tracker.feed([_sample(2000)])

    assert [e.kind for e in tracker.events] == [livemon.TASK_STARTED, livemon.TASK_FINISHED]
    assert tracker.as_text().count("\n") == 1


def test_what_is_on_now_is_listed_with_its_objects() -> None:
    tracker = _tracker()
    tracker.feed([_sample(1000, "Morning,Quiet, Please", "Dawn,Twin")])

    active, running = tracker.targets_now()

    assert [name for name, _ in active] == ["Dawn", "Twin"]
    assert [name for name, _ in running] == ["Morning", "Quiet, Please"]
    assert len(active[1][1]) == 2


# ##################################################################################
# What is lit.
# ##################################################################################


def test_what_is_on_is_lit_on_and_everything_of_that_name_with_it() -> None:
    tracker = _tracker()
    tracker.feed([_sample(1000, "Morning", "Twin")])

    lit = tracker.lit()

    assert lit == {"mt-task-20": livemon.LIT_ON, "mt-profile-102": livemon.LIT_ON, "mt-profile-103": livemon.LIT_ON}


def test_what_has_just_stopped_is_marked_recent_and_then_goes_out() -> None:
    tracker = _tracker()
    tracker.feed([_sample(0, "Morning")])
    tracker.feed([_sample(1000)])

    assert tracker.lit(recent_seconds=5) == {"mt-task-20": livemon.LIT_RECENT}

    tracker.feed([_sample(9000)])

    assert tracker.lit(recent_seconds=5) == {}


def test_something_still_on_is_never_marked_recent_because_of_a_namesake() -> None:
    tracker = _tracker()
    tracker.feed([_sample(0, "Morning")])

    assert tracker.lit() == {"mt-task-20": livemon.LIT_ON}


def test_the_lights_script_carries_the_anchors_and_the_container() -> None:
    script = livemon.lights_js({"mt-task-20": livemon.LIT_ON}, "c42")

    assert '"c42"' in script
    assert '"mt-task-20"' in script
    assert "mt-live-on" in script
    assert "__" not in script, "every placeholder was filled"


def test_without_a_container_the_script_works_on_the_whole_page() -> None:
    """The monitor sends it to every window, so the window's own Diagram is found without knowing its element."""
    script = livemon.lights_js({"mt-task-20": livemon.LIT_ON})

    assert 'const containerId = "";' in script
    assert "containerId ? document.getElementById(containerId) : document" in script


def test_the_script_says_how_many_named_objects_the_page_has_and_how_many_it_lit() -> None:
    """So 'no Diagram is open' can be told from 'a Diagram without these'."""
    script = livemon.lights_js({})

    assert "{nodes:" in script
    assert "lit: lit_count" in script


def test_putting_the_lights_out_is_the_same_script_with_nothing_lit() -> None:
    assert "const lit = {};" in livemon.lights_js({}, "c1")


# ##################################################################################
# The prediction.
# ##################################################################################


def _predict(hour: int, minute: int = 30) -> firesim.Simulation:
    return firesim.simulate(firesim.Scenario(datetime(2026, 10, 19, hour, minute)), PrimeItems)


def test_a_device_that_does_as_predicted_agrees() -> None:
    index = _load_fixture()

    comparison = livemon.compare(_predict(6), frozenset({"Dawn"}), index)

    assert comparison.differences == []
    assert comparison.agreed >= 2, "Dawn active as predicted, and Dusk inactive as predicted"


def test_a_profile_predicted_active_that_is_not_is_reported_missing() -> None:
    index = _load_fixture()

    comparison = livemon.compare(_predict(6), frozenset(), index)

    assert [(d.kind, d.name) for d in comparison.differences] == [(livemon.MISSING, "Dawn")]
    assert "does not list it as active" in comparison.differences[0].why


def test_a_profile_predicted_inactive_that_is_active_is_reported_with_the_condition_that_ruled_it_out() -> None:
    index = _load_fixture()

    comparison = livemon.compare(_predict(6), frozenset({"Dawn", "Dusk"}), index)

    (difference,) = comparison.differences
    assert (difference.kind, difference.name) == (livemon.UNEXPECTED, "Dusk")
    assert "ruled it out" in difference.why
    assert difference.target is not None


def test_a_profile_that_fires_at_a_moment_is_not_judged_on_whether_it_is_active() -> None:
    index = _load_fixture()

    comparison = livemon.compare(_predict(6), frozenset({"Dawn"}), index)

    assert all(d.name != "Wired" for d in comparison.differences)


def test_a_profile_that_fires_at_a_single_time_is_not_judged_even_when_predicted_active() -> None:
    """'At 08:30' is a moment, not a state: the device is never going to list it as active to be checked."""
    index = _load_fixture()
    dawn = index.profiles["Dawn"][0]
    prediction = firesim.Simulation(
        firesim.Scenario(datetime(2026, 10, 19, 6, 30)),
        active=[firesim.ProfileResult(dawn, firesim.ACTIVE, [], 5, True, None, None)],
    )

    assert livemon.compare(prediction, frozenset(), index).differences == []


def test_two_profiles_with_one_name_are_not_judged_since_the_name_says_nothing_about_which() -> None:
    index = _load_fixture()

    comparison = livemon.compare(_predict(6), frozenset(), index)

    assert all(d.name != "Twin" for d in comparison.differences)


def test_what_is_active_on_the_device_and_unknown_to_the_prediction_is_listed_not_judged() -> None:
    index = _load_fixture()

    comparison = livemon.compare(_predict(6), frozenset({"Dawn", "Mystery"}), index)

    assert comparison.unjudged == ["Mystery"]


def test_the_comparison_reads_as_rows_with_the_moment_and_a_link_for_each_difference() -> None:
    index = _load_fixture()
    comparison = livemon.compare(_predict(6), frozenset({"Dusk"}), index, battery=77)

    rows = comparison.rows()

    assert "battery 77%" in rows[0].text
    assert any(row.target is not None and row.text.startswith("ACTIVE, PREDICTED INACTIVE: Dusk") for row in rows)
    assert any(row.target is not None and row.text.startswith("INACTIVE, PREDICTED ACTIVE: Dawn") for row in rows)


# ##################################################################################
# Which Diagram, and where in it.
# ##################################################################################


def test_what_has_just_started_is_what_a_diagram_scrolls_to() -> None:
    tracker = _tracker()
    tracker.feed([_sample(0)])

    events = tracker.feed([_sample(1000, "Morning", "Dawn"), _sample(1200, "Morning", "Dawn")])

    assert livemon.started_anchors(events) == ["mt-profile-100", "mt-task-20"]


def test_what_finished_or_has_no_object_in_the_backup_is_not_scrolled_to() -> None:
    tracker = _tracker()
    tracker.feed([_sample(0, "Morning")])

    events = tracker.feed([_sample(1000, "Stranger")])

    assert livemon.started_anchors(events) == []


def test_the_follow_anchors_are_in_the_lights_script() -> None:
    script = livemon.lights_js({}, follow=["mt-task-20", "mt-task-21"])

    assert 'for (const anchor of ["mt-task-20", "mt-task-21"])' in script


def test_everything_seen_in_one_project_is_a_diagram_of_that_project() -> None:
    tracker = _tracker()
    tracker.feed([_sample(0, "Morning", "Dawn")])

    assert tracker.seen_projects() == {"Home"}
    assert livemon.diagram_scope(tracker.seen_projects()) == "Home"


def test_what_is_seen_in_several_projects_needs_the_whole_configuration() -> None:
    tracker = _tracker()
    tracker.feed([_sample(0, "Morning,Away Task", "Dawn")])

    assert tracker.seen_projects() == {"Home", "Away"}
    assert livemon.diagram_scope(tracker.seen_projects()) == ""


def test_nothing_seen_yet_needs_the_whole_configuration() -> None:
    assert livemon.diagram_scope(_tracker().seen_projects()) == ""


def test_something_that_belongs_to_no_project_needs_the_whole_configuration() -> None:
    assert livemon.diagram_scope({"Home", ""}) == ""
    assert livemon.diagram_scope({""}) == ""
