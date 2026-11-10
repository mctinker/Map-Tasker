"""The near-duplicate finder (maprefac_similar): finding the run of actions Tasks share, and making it one Task.

What these check is what SURVIVES and what is REFUSED, as in test_maprefac: that every copy is replaced by a call
standing where the copy was, that what is left of each Task keeps its order and its numbering, that one Undo puts all
of it back, and that nothing at all changes when the plan is blocked.  Finding has its own questions -- labels do not
make two actions different, a Task holding a Goto is left out, a run that cuts an If in two is trimmed to the part
that does not -- and the plan's answer to a Task that was edited after the search.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from maptasker.src.core import objnotes
from maptasker.src.core.mapjump import TASK, actions_in_map_order
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import sessundo
from maptasker.src.mapops import maprefac, maprefac_similar
from maptasker.src.mapops.maprefac_model import Plan
from maptasker.src.mapops.maprefac_similar import SharedRun

from tests.test_maprefac import _load

SET = "547"
FLASH = "548"
IF = "37"
END_IF = "38"
PERFORM_TASK = "130"
GOTO = "135"


def _action(code: str, *args: str, label: str = "") -> str:
    """One <Action>; its sr= is stamped by _task, in the order given."""
    strings = "".join(f'<Str sr="arg{number}" ve="3">{text}</Str>' for number, text in enumerate(args))
    tag = f"<label>{label}</label>" if label else ""
    return f'<Action sr="actX" ve="7"><code>{code}</code>{tag}{strings}</Action>'


def _task(task_id: str, name: str, *actions: str) -> str:
    """One <Task>, its actions numbered act0, act1, ... in the order given."""
    numbered = "".join(action.replace("actX", f"act{number}") for number, action in enumerate(actions))
    return f'<Task sr="task{task_id}" ve="2"><id>{task_id}</id><nme>{name}</nme><pri>50</pri>{numbered}</Task>'


def _flash(text: str, label: str = "") -> str:
    return _action(FLASH, text, label=label)


def _set(name: str, value: str) -> str:
    return _action(SET, name, value)


def _configuration(tasks: list[str], project_tids: str) -> str:
    return (
        '<TaskerData sr="" dvi="1" tv="6.3.13">'
        f'<Project sr="proj0" ve="2"><name>Home</name><pids></pids><tids>{project_tids}</tids></Project>'
        f"{''.join(tasks)}</TaskerData>"
    )


# The run the Tasks share: four actions that set the volume and the brightness and say so.  Written once and put
# into several Tasks, the way it would have been copied.
_VOLUME = _set("%volume", "5")
_SAID_VOLUME = _flash("volume is %volume")
_BRIGHTNESS = _set("%level", "80")
_SAID_BRIGHTNESS = _flash("brightness is %level")
_RUN = (_VOLUME, _SAID_VOLUME, _BRIGHTNESS, _SAID_BRIGHTNESS)

# 30 Morning   Flash, then the run (actions 2-5), then Flash.  Sets %volume itself, before the run, which the run
#              also uses -- a local that the move would separate from the Task.
# 31 Evening   Variable Set, then the run (2-5), then Flash.
# 32 Weekend   the run (1-4), then Flash; one action of the run carries a label here.  Evening sorts first, so its
#              copy is the one kept and this label is the one lost.
# 33 Errands   three Flashes nobody else has.
# 34 Looper    the run, then a Goto: left out, however much it shares.
# 35 Brief     two actions, shorter than any run it could share.
_FIXTURE_XML = _configuration(
    [
        _task("30", "Morning", _flash("good morning"), *_RUN, _flash("have a nice day")),
        _task(
            "31",
            "Evening",
            _set("%mood", "calm"),
            *_RUN,
            _flash("good night"),
        ),
        _task(
            "32",
            "Weekend",
            _VOLUME,
            _flash("volume is %volume", label="say the volume"),
            _BRIGHTNESS,
            _SAID_BRIGHTNESS,
            _flash("sleep in"),
        ),
        _task("33", "Errands", _flash("milk"), _flash("bread"), _flash("eggs")),
        _task("34", "Looper", *_RUN, _action(GOTO, "1")),
        _task("35", "Brief", _VOLUME, _SAID_VOLUME),
    ],
    "30,31,32,33,34,35",
)


@pytest.fixture(autouse=True)
def _no_notes_held_over() -> Iterator[None]:
    """Each test starts from the (empty, test-only) notes file, not from a book an earlier test left on the run."""
    objnotes.forget(PrimeItems)
    yield
    objnotes.forget(PrimeItems)


@pytest.fixture
def loaded() -> Iterator[None]:
    """The fixture configuration in the tables maprefac reads, with an empty undo history."""
    sessundo.clear(PrimeItems)
    _load(_FIXTURE_XML)
    yield
    sessundo.clear(PrimeItems)


def _codes(task_id: str) -> list[str]:
    """A Task's action codes in run order."""
    task = PrimeItems.tasker_root_elements["all_tasks"][task_id]["xml"]
    return [(action.findtext("code") or "") for action in actions_in_map_order(task)]


def _srs(task_id: str) -> list[str]:
    """A Task's sr= attributes in run order: always act0, act1, ... with no gaps."""
    task = PrimeItems.tasker_root_elements["all_tasks"][task_id]["xml"]
    return [action.attrib.get("sr", "") for action in actions_in_map_order(task)]


def _called(task_id: str, number: int) -> str:
    """The name that action `number` (from 1) of a Task calls, which is its first argument."""
    task = PrimeItems.tasker_root_elements["all_tasks"][task_id]["xml"]
    return (actions_in_map_order(task)[number - 1].findtext("Str") or "").strip()


def _the_run() -> SharedRun:
    """The run the fixture was built around: four actions, in Morning, Evening and Weekend."""
    runs = maprefac_similar.find_shared_runs(4, state=PrimeItems)
    assert runs
    return runs[0]


def _plan(name: str = "Volume And Brightness") -> Plan:
    run = _the_run()
    where = run.placements[0]
    return maprefac_similar.plan_shared_run(where.task_id, where.first, run.length, name, state=PrimeItems)


def _everything() -> dict[str, list[str]]:
    """Every Task's codes and numbering, for 'nothing changed'."""
    tasks = PrimeItems.tasker_root_elements["all_tasks"]
    return {task_id: _codes(task_id) + _srs(task_id) for task_id in tasks}


# ##################################################################################
# Finding.
# ##################################################################################


def test_the_run_three_tasks_share_is_found_with_where_each_has_it(loaded: None) -> None:
    run = _the_run()

    assert run.length == 4
    assert {(each.name, each.first) for each in run.placements} == {("Morning", 2), ("Evening", 2), ("Weekend", 1)}
    assert run.actions == ("Variable Set", "Flash", "Variable Set", "Flash")
    assert run.host == ""


def test_a_label_does_not_make_two_actions_different(loaded: None) -> None:
    """Weekend's second action is labelled and Morning's is not; they are the same action."""
    assert "Weekend" in {each.name for each in _the_run().placements}


def test_a_task_with_a_goto_is_left_out_whatever_it_shares(loaded: None) -> None:
    assert "Looper" not in {
        each.name for run in maprefac_similar.find_shared_runs(4, PrimeItems) for each in run.placements
    }


def test_a_task_nobody_shares_with_is_in_no_run(loaded: None) -> None:
    named = {each.name for run in maprefac_similar.find_shared_runs(3, PrimeItems) for each in run.placements}

    assert "Errands" not in named
    assert "Brief" not in named, "two actions are shorter than the shortest run asked for"


def test_asking_for_a_longer_run_than_there_is_finds_nothing(loaded: None) -> None:
    assert maprefac_similar.find_shared_runs(5, state=PrimeItems) == []


def test_a_run_says_what_merging_it_saves(loaded: None) -> None:
    """Three copies of four actions become one of four and three calls: 12 - 4 - 3."""
    assert _the_run().saved == 5


def test_the_most_worth_merging_comes_first(loaded: None) -> None:
    runs = maprefac_similar.find_shared_runs(3, state=PrimeItems)

    assert [run.saved for run in runs] == sorted((run.saved for run in runs), reverse=True)


def test_a_run_is_offered_with_a_label_saying_what_it_is(loaded: None) -> None:
    key, label = maprefac_similar.run_choices([_the_run()])[0]

    assert key == _the_run().key
    assert "4 actions in 3 Tasks" in label
    assert "Evening" in label
    assert "saves 5" in label


def test_a_run_that_cuts_an_if_in_two_is_offered_only_for_the_part_that_does_not() -> None:
    """Both Tasks open the same If and share the first four actions inside it, but close it differently."""
    inside = (_flash("a"), _flash("b"), _flash("c"), _flash("d"))
    condition = _action(IF, "%x")
    sessundo.clear(PrimeItems)
    _load(
        _configuration(
            [
                _task("40", "Cut A", condition, *inside, _action(END_IF)),
                _task("41", "Cut B", condition, *inside, _flash("e"), _action(END_IF)),
            ],
            "40,41",
        ),
    )

    runs = maprefac_similar.find_shared_runs(4, state=PrimeItems)

    assert [run.length for run in runs] == [4]
    assert {each.first for each in runs[0].placements} == {2}, "the four Flashes, not the If before them"


def test_a_task_that_is_only_the_run_is_the_one_the_others_call() -> None:
    sessundo.clear(PrimeItems)
    _load(
        _configuration(
            [
                _task("50", "Core", *_RUN),
                _task("51", "Before", _flash("first"), *_RUN),
                _task("52", "After", *_RUN, _flash("last")),
            ],
            "50,51,52",
        ),
    )

    run = maprefac_similar.find_shared_runs(4, state=PrimeItems)[0]

    assert run.host == "50"
    assert run.saved == 3 * 4 - 4 - 2, "no new Task, and Core keeps no call"


def test_a_name_is_suggested_that_no_task_has(loaded: None) -> None:
    run = _the_run()
    first = maprefac_similar.suggested_name(run, state=PrimeItems)

    assert first == "Evening - shared part"
    assert maprefac_similar.suggested_name(run, state=PrimeItems) == first


# ##################################################################################
# Doing it.
# ##################################################################################


def test_every_copy_becomes_a_call_where_it_was(loaded: None) -> None:
    plan = _plan()
    assert plan.can_apply
    assert maprefac.apply(plan, state=PrimeItems) == (True, [])

    # What is left of each Task keeps its order, with the call standing where the run began.
    assert _codes("30") == [FLASH, PERFORM_TASK, FLASH]
    assert _codes("31") == [SET, PERFORM_TASK, FLASH]
    assert _codes("32") == [PERFORM_TASK, FLASH]
    for task_id in ("30", "31", "32"):
        assert _srs(task_id) == [f"act{number}" for number in range(len(_codes(task_id)))]

    assert _called("30", 2) == "Volume And Brightness"
    assert _called("31", 2) == "Volume And Brightness"
    assert _called("32", 1) == "Volume And Brightness"


def test_the_shared_task_holds_the_run_once_and_is_filed_under_the_project(loaded: None) -> None:
    maprefac.apply(_plan(), state=PrimeItems)

    shared_id = PrimeItems.tasker_root_elements["all_tasks_by_name"]["Volume And Brightness"]["id"]
    assert _codes(shared_id) == [SET, FLASH, SET, FLASH]
    assert _srs(shared_id) == ["act0", "act1", "act2", "act3"]
    home = PrimeItems.tasker_root_elements["all_projects"]["Home"]["xml"]
    assert shared_id in (home.findtext("tids") or "").split(",")


def test_a_task_that_was_not_part_of_it_is_untouched(loaded: None) -> None:
    before = {task_id: _codes(task_id) for task_id in ("33", "34", "35")}

    maprefac.apply(_plan(), state=PrimeItems)

    assert {task_id: _codes(task_id) for task_id in ("33", "34", "35")} == before


def test_one_undo_puts_every_task_back(loaded: None) -> None:
    before = _everything()
    maprefac.apply(_plan(), state=PrimeItems)
    assert _everything() != before

    assert sessundo.undo(PrimeItems)[0]

    assert _everything() == before
    assert "Volume And Brightness" not in PrimeItems.tasker_root_elements["all_tasks_by_name"]


def test_the_preview_names_every_task_it_changes_and_links_to_it(loaded: None) -> None:
    rows = maprefac.report_rows(_plan())
    text = "\n".join(row.text for row in rows)

    for name in ("Morning", "Evening", "Weekend"):
        assert f"In Task '{name}'" in text
    assert "Create Task 'Volume And Brightness'" in text
    assert sum(1 for row in rows if row.target is not None and row.target.action) == 3


def test_a_task_that_was_taken_out_for_a_goto_is_said_to_have_been_left(loaded: None) -> None:
    warnings = " ".join(_plan().warnings)

    assert "'Looper'" in warnings
    assert "Goto" in warnings


def test_labels_that_will_be_lost_are_counted(loaded: None) -> None:
    """Evening's action is kept and Weekend's carries a label: that label goes."""
    assert any("label" in warning for warning in _plan().warnings)


def test_a_local_variable_the_move_would_separate_is_named() -> None:
    sessundo.clear(PrimeItems)
    _load(
        _configuration(
            [
                _task("60", "Keeps A Local", _set("%volume", "3"), *_RUN),
                _task("61", "Does Not", *_RUN, _flash("done")),
            ],
            "60,61",
        ),
    )
    run = maprefac_similar.find_shared_runs(4, state=PrimeItems)[0]
    where = run.placements[0]

    plan = maprefac_similar.plan_shared_run(where.task_id, where.first, run.length, "Shared", state=PrimeItems)

    assert any("Task 'Keeps A Local'" in warning and "%volume" in warning for warning in plan.warnings)


def test_a_task_that_is_only_the_run_is_called_not_copied() -> None:
    sessundo.clear(PrimeItems)
    _load(
        _configuration(
            [
                _task("50", "Core", *_RUN),
                _task("51", "Before", _flash("first"), *_RUN),
                _task("52", "After", *_RUN, _flash("last")),
            ],
            "50,51,52",
        ),
    )
    run = maprefac_similar.find_shared_runs(4, state=PrimeItems)[0]
    where = run.placements[0]

    plan = maprefac_similar.plan_shared_run(where.task_id, where.first, run.length, "", state=PrimeItems)
    assert plan.can_apply, "no name is needed: the Task that is already there is the shared one"
    assert maprefac.apply(plan, state=PrimeItems) == (True, [])

    assert _codes("50") == [SET, FLASH, SET, FLASH], "Core is as it was"
    assert _codes("51") == [FLASH, PERFORM_TASK]
    assert _codes("52") == [PERFORM_TASK, FLASH]
    assert _called("51", 2) == "Core"
    assert "" not in PrimeItems.tasker_root_elements["all_tasks_by_name"]


def test_a_task_holding_the_run_twice_is_changed_at_the_first_copy_only() -> None:
    sessundo.clear(PrimeItems)
    _load(
        _configuration(
            [
                _task("70", "Twice", *_RUN, _flash("between"), *_RUN),
                _task("71", "Once", _flash("x"), *_RUN),
            ],
            "70,71",
        ),
    )
    run = maprefac_similar.find_shared_runs(4, state=PrimeItems)[0]
    where = run.placements[0]
    plan = maprefac_similar.plan_shared_run(where.task_id, where.first, run.length, "Shared", state=PrimeItems)

    assert maprefac.apply(plan, state=PrimeItems) == (True, [])

    assert _codes("70") == [PERFORM_TASK, FLASH, SET, FLASH, SET, FLASH]
    assert _srs("70") == [f"act{number}" for number in range(6)]
    assert maprefac_similar.find_shared_runs(4, state=PrimeItems), "the second copy can be merged in turn"


def test_a_task_that_repeats_one_action_does_not_make_the_search_hang_or_overlap() -> None:
    sessundo.clear(PrimeItems)
    ticks = [_flash("tick")] * 12
    _load(_configuration([_task("80", "A", *ticks), _task("81", "B", *ticks)], "80,81"))

    runs = maprefac_similar.find_shared_runs(4, state=PrimeItems)

    assert runs
    assert runs[0].length == 12


def _note_on(name: str) -> objnotes.Note | None:
    """The note on a Task, as the notes file holds it -- read afresh, since that is what the Map will build from."""
    return objnotes.load().get(TASK, name)


def test_the_shared_task_is_noted_as_shared_and_names_the_tasks_that_call_it(loaded: None) -> None:
    maprefac.apply(_plan(), state=PrimeItems)

    note = _note_on("Volume And Brightness")
    assert note is not None
    assert note.tags == ["shared"]
    assert note.hashtags == "#shared"
    assert note.text.startswith("Shared: this Task is called by 3 Tasks (Evening, Morning, Weekend)")


def test_the_preview_says_the_note_will_be_made_and_where_it_is_kept(loaded: None) -> None:
    text = "\n".join(row.text for row in maprefac.report_rows(_plan()))

    assert "Put a note on Task 'Volume And Brightness'" in text
    assert "#shared" in text
    assert "not in the backup" in text


def test_nothing_is_noted_when_the_plan_is_blocked(loaded: None) -> None:
    maprefac.apply(_plan(""), state=PrimeItems)

    assert objnotes.load().notes == {}


def test_a_note_that_cannot_be_saved_does_not_make_the_merge_fail(
    loaded: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(objnotes, "save", lambda *_args, **_kwargs: "disk full")

    assert maprefac.apply(_plan(), state=PrimeItems) == (True, [])

    assert _codes("32") == [PERFORM_TASK, FLASH]


def test_a_task_that_was_already_the_run_keeps_its_note_and_gains_the_new_one() -> None:
    sessundo.clear(PrimeItems)
    _load(
        _configuration(
            [
                _task("50", "Core", *_RUN),
                _task("51", "Before", _flash("first"), *_RUN),
                _task("52", "After", *_RUN, _flash("last")),
            ],
            "50,51,52",
        ),
    )
    book = objnotes.book_for(PrimeItems)
    book.put(objnotes.Note(TASK, "Core", "Written by me.", ["mine"]))
    objnotes.save(book)
    run = maprefac_similar.find_shared_runs(4, state=PrimeItems)[0]
    where = run.placements[0]

    plan = maprefac_similar.plan_shared_run(where.task_id, where.first, run.length, "", state=PrimeItems)
    assert maprefac.apply(plan, state=PrimeItems) == (True, [])

    note = _note_on("Core")
    assert note is not None
    assert note.tags == ["mine", "shared"]
    assert note.text.startswith("Written by me.")
    assert "called by 2 Tasks (After, Before)" in note.text, "the Task that is the run is not one of its own callers"


def test_merging_again_under_the_same_name_does_not_say_it_twice(loaded: None) -> None:
    maprefac.apply(_plan(), state=PrimeItems)
    sessundo.undo(PrimeItems)  # the merge goes; the note, which Undo does not reach, stays
    first = _note_on("Volume And Brightness")
    assert first is not None

    maprefac.apply(_plan(), state=PrimeItems)

    again = _note_on("Volume And Brightness")
    assert again is not None
    assert again.text == first.text


def test_a_note_with_a_great_many_callers_names_some_and_counts_the_rest() -> None:
    sentence = maprefac_similar._sharing_sentence([f"Task {number}" for number in range(20)])

    assert "called by 20 Tasks (Task 0," in sentence
    assert "Task 11, and 8 more)" in sentence
    assert "Task 12" not in sentence


# ##################################################################################
# Refusing.
# ##################################################################################


@pytest.mark.parametrize(("name", "reason"), [("", "NO-NAME"), ("Morning", "NAME-TAKEN"), ("Bad\x01Name", "BAD-NAME")])
def test_a_name_that_cannot_be_used_blocks_the_plan_and_changes_nothing(loaded: None, name: str, reason: str) -> None:
    before = _everything()
    plan = _plan(name)

    assert [block.reason for block in plan.blocks] == [reason]
    assert not plan.can_apply
    assert maprefac.apply(plan, state=PrimeItems)[0] is False
    assert _everything() == before


def test_a_run_that_is_no_longer_where_it_was_found_is_refused(loaded: None) -> None:
    run = _the_run()
    where = run.placements[0]
    PrimeItems.tasker_root_elements["all_tasks"][where.task_id]["xml"].remove(
        actions_in_map_order(PrimeItems.tasker_root_elements["all_tasks"][where.task_id]["xml"])[where.first - 1],
    )

    plan = maprefac_similar.plan_shared_run(where.task_id, where.first, run.length, "Shared", state=PrimeItems)

    assert plan.blocks
    assert plan.blocks[0].reason in {"OUT-OF-RANGE", "NOT-SHARED"}


def _change_the_run_in(task_id: str, first: int) -> None:
    """Edit the first action of the run in one Task, so that the Task no longer holds the run."""
    task = PrimeItems.tasker_root_elements["all_tasks"][task_id]["xml"]
    argument = actions_in_map_order(task)[first - 1].find("Str")
    assert argument is not None
    argument.text = "something else entirely"


def test_a_task_edited_since_the_search_drops_out_of_the_plan_instead_of_being_rewritten(loaded: None) -> None:
    run = _the_run()
    where = run.placements[0]
    _change_the_run_in("30", 2)  # Morning
    morning = _codes("30") + _srs("30")

    plan = maprefac_similar.plan_shared_run(where.task_id, where.first, run.length, "Shared", state=PrimeItems)

    assert maprefac.apply(plan, state=PrimeItems) == (True, [])
    assert _codes("30") + _srs("30") == morning
    assert _codes("31") == [SET, PERFORM_TASK, FLASH]
    assert _codes("32") == [PERFORM_TASK, FLASH]


def test_a_run_only_one_task_still_holds_is_not_shared(loaded: None) -> None:
    run = _the_run()
    where = run.placements[0]
    _change_the_run_in("30", 2)  # Morning
    _change_the_run_in("32", 1)  # Weekend

    plan = maprefac_similar.plan_shared_run(where.task_id, where.first, run.length, "Shared", state=PrimeItems)

    assert [block.reason for block in plan.blocks] == ["NOT-SHARED"]


def test_a_plan_is_refused_if_its_tasks_are_gone_by_the_time_it_is_applied(loaded: None) -> None:
    plan = _plan()
    PrimeItems.tasker_root_elements["all_tasks"].pop("32")
    PrimeItems.xml_root.remove(PrimeItems.xml_root.findall("Task")[2])

    done, errors = maprefac.apply(plan, state=PrimeItems)

    assert done is False
    assert errors
