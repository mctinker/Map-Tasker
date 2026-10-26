"""MapTasker AI Task drafting (mapdraft) Unit Tests

A model proposes a Task; what these assert is mostly about what it is NOT allowed to do.
The model is shown only what the Add Task picker offers, and everything it sends back is
checked against that before any of it is built: an action the editor cannot build, an
argument an action does not have, a number that is not one, a choice that is not offered --
each is dropped and said, never passed on to quietly produce a different Task from the one
that was described.  What survives is built with taskedit's own functions into the editor's
working copy, so the tests also hold the line that a draft changes nothing that is loaded.

The model is a function standing in for it, as in test_mapask.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from maptasker.src.analysis import mapask
from maptasker.src.core import appinv, caches
from maptasker.src.core.actionc import action_codes
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import taskedit, taskedit_addable, taskedit_apply, taskedit_model, taskedit_save
from maptasker.src.mapops import mapcards, mapdraft

from tests.test_mapswap import _FIXTURE_XML, _load

if TYPE_CHECKING:
    from collections.abc import Collection

    from maptasker.src.core.primitem import RunState

# The actions used below, named so the tests read as prose.
IF, ELSE, END_IF = "37t", "43t", "38t"
FOR, END_FOR = "39t", "40t"
STOP = "137t"
FLASH = "548t"  # arg0 Text, arg1 Long (checkbox)
VARIABLE_SET = "547t"  # arg0 Name, arg1 To, arg2 Recurse Variables (checkbox)
WAIT = "30t"  # arg0 MS ... -- numbers
PERFORM_TASK = "130t"  # arg0 Name
ARRAY_PROCESS = "369t"  # arg1 Type -- a choice
SYSTEM_LOCK = "16t"  # no arguments at all

_SETTINGS = mapask.ModelSettings(mapask.ANTHROPIC, "claude-sonnet-5", "test-key")


@pytest.fixture
def backup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """test_mapswap's fixture backup, loaded: its Tasks are Noisy, Opener and Quiet.

    With a small, known list of fetched Applications, kept in a cache file of its own.  What is
    addable follows the Application and icon inventory (Notify, one of the common actions, has an
    icon argument), and the inventory includes whatever MapTasker_Apps.json sits in the current
    directory -- so without this, the catalog these tests read was the maintainer's phone locally
    and an empty one on a CI checkout, and the same test passed in one place and failed in the other.
    """
    cache = tmp_path / "MapTasker_Apps.json"
    cache.write_text(json.dumps({"devices": {"test:1821": {"apps": [{"pkg": "com.test.app", "label": "Test"}]}}}))
    monkeypatch.setattr(appinv, "cache_path", lambda: str(cache))
    caches.clear_all()
    _load(_FIXTURE_XML)


def _detail_prompt(
    description: str,
    plan: mapdraft.Plan,
    state: RunState,
    answered: Collection[int] = (),
    *,
    share_names: bool = False,
) -> tuple[str, str]:
    """The second prompt, for a test that expects there to be one to ask."""
    prompts = mapdraft.build_detail_prompt(description, plan, state, answered=answered, share_names=share_names)
    assert prompts is not None
    return prompts


def _plan(*steps: object, name: str = "", unexpressed: str = "") -> str:
    """A well-formed first reply.  A step is an action key, an (action, purpose) pair, or a dict of its fields."""
    listed = []
    for step in steps:
        if isinstance(step, dict):
            fields = {"purpose": "", "label": "", **step}
            fields["args"] = [{"id": key, "value": value} for key, value in step.get("args", {}).items()]
        elif isinstance(step, str):
            fields = {"action": step, "purpose": "", "label": "", "args": []}
        else:
            fields = {"action": step[0], "purpose": step[1], "label": "", "args": []}
        listed.append(fields)
    return json.dumps({"name": name, "steps": listed, "unexpressed": unexpressed})


def _detail(*steps: tuple[int, str, dict[str, object]]) -> str:
    """A well-formed second reply.  A step is (number from 1, label, {argument id: value})."""
    return json.dumps(
        {
            "steps": [
                {"step": number, "label": label, "args": [{"id": key, "value": value} for key, value in args.items()]}
                for number, label, args in steps
            ],
        },
    )


def _plan_of(*keys: str) -> mapdraft.Plan:
    return mapdraft.Plan("", tuple(mapdraft.PlanStep(key) for key in keys))


def _keys(plan: mapdraft.Plan) -> list[str]:
    return [step.action_key for step in plan.steps]


# ##################################################################################
# What the model is shown.
# ##################################################################################
def test_the_catalog_is_exactly_what_the_picker_lets_the_user_add(backup: None) -> None:
    catalog = {row["action_key"] for row in mapdraft.action_catalog(PrimeItems)}
    addable = {row["action_key"] for row in taskedit_addable.list_addable_actions(state=PrimeItems) if row["addable"]}
    refused = {
        row["action_key"] for row in taskedit_addable.list_addable_actions(state=PrimeItems) if not row["addable"]
    }

    assert catalog == addable
    assert FLASH in catalog
    assert refused
    assert not catalog & refused


def test_the_first_prompt_shows_the_catalog_and_not_the_configuration(backup: None) -> None:
    system, user = mapdraft.build_plan_prompt("flash hello", PrimeItems)

    assert f"{FLASH} Flash" in user
    assert "Description: flash hello" in user
    # What the user's Tasks hold is never sent: not their names, not an action's text.
    for private in ("Noisy", "Opener", "Quiet", "Done: %n", "flash the total", "com.spotify"):
        assert private not in system + user
    assert "unexpressed" in system


def test_the_first_prompt_teaches_how_tasks_work(backup: None) -> None:
    system, _ = mapdraft.build_plan_prompt("flash hello", PrimeItems)

    for fact in ("Variables are written %name", "End If", "Profile", "Perform Task", "Seconds"):
        assert fact in system
    # The braces of the JSON it describes were not left doubled by the template.
    assert "{{" not in system
    assert '{"id", "value"}' in system


def test_the_common_actions_are_listed_with_their_arguments(backup: None) -> None:
    _, user = mapdraft.build_plan_prompt("flash hello", PrimeItems)
    listed = {line.split(" ", 1)[0]: line for line in user.splitlines() if line[:1].isdigit()}

    assert "0 Text (text); 1 Long (checkbox)" in listed[FLASH]
    assert "if_op Operator (choice: " in listed[IF]
    assert "Is Set" in listed[IF]
    assert listed[ELSE] == f"{ELSE} Else"
    # The rest of the catalog is by name alone, and a common action is not listed twice.
    assert listed[ARRAY_PROCESS] == f"{ARRAY_PROCESS} Array Process"
    assert user.count(f"\n{FLASH} ") == 1


def test_every_common_action_is_in_the_catalog_and_its_arguments_exist(backup: None) -> None:
    """A key or argument id that drifts from the editor's is found here, not by a model leaving it out."""
    common = mapdraft.common_actions(PrimeItems)
    catalog = {row["action_key"] for row in mapdraft.action_catalog(PrimeItems)}

    assert set(mapdraft._COMMON_ACTIONS) <= catalog
    assert set(common) == set(mapdraft._COMMON_ACTIONS)
    for key, wanted in mapdraft._COMMON_ACTIONS.items():
        assert [arg.arg_id for arg in common[key]] == [
            arg_id for arg_id in wanted if arg_id in {a.arg_id for a in common[key]}
        ]
        assert len(common[key]) == len(wanted), f"{key}: an argument of the common list is not one the editor offers"


def test_a_small_model_is_shown_a_short_prompt_with_what_looks_relevant(backup: None) -> None:
    description = "turn the flashlight on and vibrate"
    full_system, full_user = mapdraft.build_plan_prompt(description, PrimeItems)
    system, user = mapdraft.build_plan_prompt(description, PrimeItems, compact=True)

    assert len(system) + len(user) < (len(full_system) + len(full_user)) / 4
    assert len(system) + len(user) < 4000
    assert f"{FLASH} Flash" in user  # always shown
    assert "61t Vibrate" in user  # a word of the description
    assert "511t Torch" in user  # nothing in its name says flashlight; its card does
    assert "Common actions" not in user
    assert '"args" is always []' in system


def test_arguments_are_the_ones_the_editor_would_show(backup: None) -> None:
    flash = {arg.arg_id: arg for arg in mapdraft.fillable_args(FLASH, PrimeItems)}
    assert (flash["0"].name, flash["0"].kind) == ("Text", "text")
    assert flash["1"].kind == "checkbox"

    wait = {arg.arg_id: arg.kind for arg in mapdraft.fillable_args(WAIT, PrimeItems)}
    assert set(wait.values()) == {"number"}

    array = {arg.arg_id: arg for arg in mapdraft.fillable_args(ARRAY_PROCESS, PrimeItems)}
    assert array["1"].kind == "choice"
    assert "Reverse" in array["1"].options

    assert mapdraft.fillable_args(SYSTEM_LOCK, PrimeItems) == []


def test_an_if_is_offered_its_condition(backup: None) -> None:
    arguments = {arg.arg_id: arg for arg in mapdraft.fillable_args(IF, PrimeItems)}

    assert {"if_lhs", "if_op", "if_rhs"} <= arguments.keys()
    assert arguments["if_op"].kind == "choice"
    assert "Is Set" in arguments["if_op"].options


def test_the_second_prompt_shows_only_the_chosen_steps_arguments(backup: None) -> None:
    plan = mapdraft.Plan(
        "",
        (mapdraft.PlanStep(FLASH, "say hello"), mapdraft.PlanStep(SYSTEM_LOCK), mapdraft.PlanStep(WAIT, "wait 5s")),
    )
    system, user = _detail_prompt("say hello then wait", plan, PrimeItems)

    assert "say hello" in user
    assert '"step": 1' in user
    assert '"step": 3' in user
    # Unless the first question has already listed an action's arguments, in which case it is not asked again.
    _, partly = _detail_prompt("say hello then wait", plan, PrimeItems, answered={0})
    assert '"step": 1' not in partly
    assert '"step": 3' in partly
    assert mapdraft.build_detail_prompt("x", plan, PrimeItems, answered={0, 2}) is None
    # A step with nothing to set is not listed, and numbering follows the plan, not the list.
    assert '"step": 2' not in user
    assert "Description: say hello then wait" in user
    assert "Never invent" in system
    assert "Noisy" not in user


def test_a_perform_task_is_not_shown_the_names_of_the_users_tasks(backup: None) -> None:
    """A name in the description is checked here, afterwards; the configuration stays out of the prompt."""
    plan = mapdraft.Plan("", (mapdraft.PlanStep(PERFORM_TASK, "run the Noisy one"),))
    system, user = _detail_prompt("run Noisy", plan, PrimeItems)

    assert "Perform Task" in user
    assert "Opener" not in system + user
    assert "Quiet" not in system + user
    # Only what the user's own description said reaches the model.
    assert user.count("Noisy") == 2


def test_a_plan_of_actions_with_nothing_to_set_needs_no_second_question(backup: None) -> None:
    assert mapdraft.build_detail_prompt("lock", _plan_of(SYSTEM_LOCK, ELSE), PrimeItems) is None


# ##################################################################################
# What the model knows about an action (mapcards) and the actions that best match a description.
# ##################################################################################
def test_every_card_is_for_an_action_that_exists_under_the_name_it_gives() -> None:
    """A card that outlives a renamed or removed action would describe the wrong one to a model."""
    for key, card in mapcards.cards().items():
        raw = json.loads(Path(mapcards.CARDS_FILE).read_text(encoding="utf-8"))["cards"][key]
        assert key in action_codes, key
        assert raw["name"] == action_codes[key].name, key
        assert card.does.endswith("."), key
        assert card.phrases or len(card.does) > 20, key


def test_a_card_never_says_what_an_actions_arguments_are() -> None:
    """The arguments are read off the editor; a card that listed them would be a second, drifting, copy."""
    for key, card in mapcards.cards().items():
        assert set(json.loads(Path(mapcards.CARDS_FILE).read_text(encoding="utf-8"))["cards"][key]) <= {
            "name",
            "does",
            "phrases",
            "note",
        }, key
        assert "args" not in card.does.casefold().split(), key


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("replace the dashes in %text with spaces", "598t"),  # Variable Search Replace
        ("base64 encode the secret", "596t"),  # Variable Convert
        ("tell me when the sun goes down", None),
        ("what time is sunrise", "473t"),
        ("set do not disturb", "312t"),  # Interrupt Mode
        ("ask the user to type their name", "360t"),  # Input Dialog
        ("wait until 8pm", "35t"),  # Wait Until, not Wait
        ("check whether the file exists", "342t"),  # Test File
        ("turn the screen off", "248t"),
        ("sort the list", "369t"),  # Array Process
    ],
)
def test_the_action_a_description_is_about_is_among_the_best_matches(
    backup: None,
    description: str,
    expected: str | None,
) -> None:
    rows = [row for row in mapdraft.action_catalog(PrimeItems) if row["action_key"] not in mapdraft._COMMON_ACTIONS]
    best = [row["action_key"] for row in mapcards.rank(description, rows, mapdraft.MAX_RELATED)]

    if expected is not None:
        assert expected in best, best
        assert best.index(expected) < 5
    else:
        assert best  # nothing is claimed about it, but the words still find something


def test_the_best_matches_are_the_same_every_time_and_a_description_with_no_words_gets_none(backup: None) -> None:
    rows = mapdraft.action_catalog(PrimeItems)

    assert mapcards.rank("copy the file", rows, 10) == mapcards.rank("copy the file", rows, 10)
    assert mapcards.rank("", rows, 10) == []
    assert mapcards.rank("the and of to", rows, 10) == []
    assert mapcards.rank("zzzzqqq", rows, 10) == []
    assert len(mapcards.rank("file", rows, 3)) == 3


def test_words_are_matched_whatever_their_ending() -> None:
    assert mapcards.terms("vibrating")[0] == mapcards.terms("vibrates")[0] == mapcards.terms("vibrate")[0]
    assert mapcards.terms("shutting")[0] == mapcards.terms("shut")[0]
    assert "do_not" not in mapcards.terms("do not disturb")  # stop words are not terms ...
    assert "not_disturb" in mapcards.terms("do not disturb")  # ... and the neighbours that remain are a term


def test_the_actions_that_best_match_are_listed_with_their_arguments_and_what_they_are_for(backup: None) -> None:
    _, user = mapdraft.build_plan_prompt("replace the dashes in %text with spaces", PrimeItems)
    before, _, after = user.partition("## Best matches for this description")
    best, _, others = after.partition("## Other actions")
    others = others.partition("Examples of replies")[0]

    assert "598t Variable Search Replace: 0 Variable (text); 1 Search (text)" in best
    assert "Replace With (text)" in best
    assert "replace what matches" in best  # the card's sentence, under the action
    # Listed once: not again among the common ones, nor by name among the rest.
    assert "598t" not in before
    assert "598t" not in others
    assert user.count("\n598t ") == 1


def test_a_common_action_is_told_its_pitfall_and_is_not_listed_twice(backup: None) -> None:
    _, user = mapdraft.build_plan_prompt("lower the media volume", PrimeItems)

    assert user.count("\n307t ") == 1
    assert "Level is 0 to 15." in user
    best = user.partition("## Best matches for this description")[2].partition("## Other actions")[0]
    assert "307t" not in best


def test_nothing_of_the_users_is_added_to_the_prompt_by_the_best_matches(backup: None) -> None:
    system, user = mapdraft.build_plan_prompt("write the text to a file and run the Noisy task", PrimeItems)

    assert "## Best matches for this description" in user
    for private in ("Noisy", "Opener", "Quiet", "Done: %n", "flash the total", "com.spotify"):
        assert private not in system.replace("Noisy", "") + user.replace("run the Noisy task", "")


def test_an_action_with_too_many_arguments_is_named_not_listed(backup: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mapdraft, "MAX_RELATED_ARGS", 1)

    related = mapdraft.related_actions("replace the dashes in %text with spaces", PrimeItems)

    assert related["598t"] is None
    assert "598t" not in mapdraft.listed_with_arguments("replace the dashes in %text with spaces", PrimeItems)
    _, user = mapdraft.build_plan_prompt("replace the dashes in %text with spaces", PrimeItems)
    assert "\n598t Variable Search Replace\n" in user
    assert "replace what matches" in user


def test_the_second_prompt_repeats_a_cards_pitfall(backup: None) -> None:
    plan = mapdraft.Plan("", (mapdraft.PlanStep("307t", "quieter"), mapdraft.PlanStep(FLASH, "say hi")))
    _, user = _detail_prompt("quieter, say hi", plan, PrimeItems)
    lines = [json.loads(line) for line in user.splitlines() if line.startswith("{")]

    assert lines[0]["note"] == "Level is 0 to 15."
    assert "note" in lines[1]  # Flash has one too
    plan = mapdraft.Plan("", (mapdraft.PlanStep(WAIT, "pause"),))
    _, user = _detail_prompt("pause", plan, PrimeItems)
    assert "note" in json.loads(user.splitlines()[-1])


# ##################################################################################
# The first reply.
# ##################################################################################
def test_an_action_the_editor_cannot_build_is_dropped_and_said(backup: None) -> None:
    refused = next(
        row["action_key"] for row in taskedit_addable.list_addable_actions(state=PrimeItems) if not row["addable"]
    )
    plan = mapdraft.parse_plan(_plan(FLASH, "999999t", refused, "Teleport"), PrimeItems)

    assert _keys(plan) == [FLASH]
    assert plan.unknown == ("999999t", refused, "Teleport")


@pytest.mark.parametrize(
    "spelling",
    ["548t", "548", "Flash", "flash", " FLASH ", "548t Flash", "548t Flash: 0 Text (text)", "548 Flash", "548t: Flash"],
)
def test_an_action_may_be_named_by_key_or_by_its_one_name(backup: None, spelling: str) -> None:
    assert _keys(mapdraft.parse_plan(_plan(spelling), PrimeItems)) == [FLASH]


def test_a_line_of_the_catalog_is_taken_for_its_key_only_if_the_key_is_real(backup: None) -> None:
    plan = mapdraft.parse_plan(_plan("999999t Flash", "37t If", "Teleport 548t"), PrimeItems)

    assert _keys(plan)[0] == IF
    assert plan.unknown == ("999999t Flash", "Teleport 548t")


def test_a_name_two_actions_share_is_not_guessed_at(backup: None) -> None:
    rows = mapdraft.action_catalog(PrimeItems)
    names = [row["name"].casefold() for row in rows]
    shared = next((name for name in names if names.count(name) > 1), None)
    if shared is None:
        pytest.skip("no two addable actions share a name in this build")
    assert mapdraft.parse_plan(_plan(shared), PrimeItems).steps == ()


def test_the_steps_keep_their_order_and_purposes(backup: None) -> None:
    plan = mapdraft.parse_plan(
        _plan((WAIT, "wait 5 seconds"), (FLASH, "say done"), name="  Wait  and\nsay  "), PrimeItems
    )

    assert [(step.action_key, step.purpose) for step in plan.steps] == [(WAIT, "wait 5 seconds"), (FLASH, "say done")]
    assert plan.name == "Wait and say"


def test_what_the_actions_cannot_do_is_passed_on(backup: None) -> None:
    plan = mapdraft.parse_plan(_plan(FLASH, unexpressed="'When I get home' is a Profile."), PrimeItems)
    assert plan.unexpressed == "'When I get home' is a Profile."
    assert mapdraft.parse_plan(_plan(FLASH, unexpressed="None."), PrimeItems).unexpressed == ""


def test_a_very_long_task_is_cut_and_said(backup: None) -> None:
    plan = mapdraft.parse_plan(_plan(*[FLASH] * (mapdraft.MAX_STEPS + 5)), PrimeItems)

    assert len(plan.steps) == mapdraft.MAX_STEPS
    assert any(str(mapdraft.MAX_STEPS) in note for note in plan.adjusted)


@pytest.mark.parametrize(
    "reply",
    ["", "no json at all", "[1, 2]", '{"steps": ', "{not json}"],
)
def test_a_reply_with_no_draft_in_it_is_an_error(backup: None, reply: str) -> None:
    with pytest.raises(mapask.AskError, match="draft"):
        mapdraft.parse_plan(reply, PrimeItems)


def test_a_reply_that_is_an_object_with_no_steps_is_an_empty_draft(backup: None) -> None:
    assert mapdraft.parse_plan("{}", PrimeItems).steps == ()


@pytest.mark.parametrize(
    "wrapped", ["```json\n{reply}\n```", "Here you go:\n{reply}\nEnjoy.", "<think>{{x}}</think>{reply}"]
)
def test_the_draft_is_found_however_the_reply_wraps_it(backup: None, wrapped: str) -> None:
    reply = wrapped.format(reply=_plan(FLASH))
    assert _keys(mapdraft.parse_plan(reply, PrimeItems)) == [FLASH]


# ##################################################################################
# Blocks stay balanced.
# ##################################################################################
def test_a_closed_block_is_left_alone(backup: None) -> None:
    plan = mapdraft.parse_plan(_plan(IF, FLASH, ELSE, WAIT, END_IF), PrimeItems)

    assert _keys(plan) == [IF, FLASH, ELSE, WAIT, END_IF]
    assert plan.adjusted == ()


def test_an_if_left_open_is_closed_and_said(backup: None) -> None:
    plan = mapdraft.parse_plan(_plan(IF, FLASH), PrimeItems)

    assert _keys(plan) == [IF, FLASH, END_IF]
    assert any("End If" in note for note in plan.adjusted)


def test_blocks_left_open_are_closed_innermost_first(backup: None) -> None:
    plan = mapdraft.parse_plan(_plan(IF, FOR, FLASH), PrimeItems)

    assert _keys(plan) == [IF, FOR, FLASH, END_FOR, END_IF]
    assert len(plan.adjusted) == 2


@pytest.mark.parametrize(
    ("steps", "kept"),
    [
        ([FLASH, ELSE], [FLASH]),  # an Else with no If
        ([FLASH, END_IF], [FLASH]),  # an End If that closes nothing
        ([IF, ELSE, ELSE, END_IF], [IF, ELSE, END_IF]),  # a second Else in one If
        ([FOR, END_IF, END_FOR], [FOR, END_FOR]),  # the wrong closer
        ([FOR, ELSE, END_FOR], [FOR, END_FOR]),  # an Else belongs to an If
        ([IF, END_FOR, END_IF], [IF, END_IF]),
    ],
)
def test_a_step_that_closes_the_wrong_thing_is_taken_out(backup: None, steps: list[str], kept: list[str]) -> None:
    plan = mapdraft.parse_plan(_plan(*steps), PrimeItems)

    assert _keys(plan) == kept
    assert plan.adjusted


# ##################################################################################
# The second reply.
# ##################################################################################
def _details(plan: mapdraft.Plan, reply: str) -> tuple[list[mapdraft.DraftStep], list[str]]:
    drafted = [mapdraft.DraftStep(step.action_key) for step in plan.steps]
    return mapdraft.parse_details(reply, plan, drafted, PrimeItems)


def test_values_that_pass_the_check_are_kept(backup: None) -> None:
    plan = _plan_of(FLASH, WAIT, ARRAY_PROCESS)
    steps, dropped = _details(
        plan,
        _detail(
            (1, "  say   hi ", {"0": "Hello %city", "1": "true"}),
            (2, "", {"0": "5000", "1": "-3"}),
            (3, "", {"1": "REVERSE"}),
        ),
    )

    assert dropped == []
    assert steps[0] == mapdraft.DraftStep(FLASH, "say hi", {"0": "Hello %city", "1": "1"})
    assert steps[1].values == {"0": "5000", "1": "-3"}
    # A choice is spelled the way the editor spells it.
    assert steps[2].values == {"1": "Reverse"}


@pytest.mark.parametrize(
    ("value", "stored"),
    [("true", "1"), ("True", "1"), ("yes", "1"), (True, "1"), ("1", "1"), ("false", "0"), ("no", "0"), (False, "0")],
)
def test_a_checkbox_is_a_yes_or_a_no(backup: None, value: object, stored: str) -> None:
    steps, dropped = _details(_plan_of(FLASH), _detail((1, "", {"1": value})))

    assert dropped == []
    assert steps[0].values == {"1": stored}


@pytest.mark.parametrize(
    ("args", "why"),
    [
        ({"1": "maybe"}, "not true or false"),  # a checkbox
        ({"99": "x"}, "no argument '99'"),  # an argument the action does not have
    ],
)
def test_a_value_that_cannot_be_used_is_dropped_and_said(backup: None, args: dict, why: str) -> None:
    steps, dropped = _details(_plan_of(FLASH), _detail((1, "", {"0": "kept", **args})))

    assert steps[0].values == {"0": "kept"}
    assert len(dropped) == 1
    assert why in dropped[0]
    assert dropped[0].startswith("Step 1 (Flash)")


def test_a_number_has_to_be_a_whole_number(backup: None) -> None:
    steps, dropped = _details(_plan_of(WAIT), _detail((1, "", {"0": "soon", "1": "2.5", "2": "7"})))

    assert steps[0].values == {"2": "7"}
    assert len(dropped) == 2
    assert all("whole number" in note for note in dropped)


def test_a_choice_has_to_be_one_of_the_options(backup: None) -> None:
    steps, dropped = _details(_plan_of(ARRAY_PROCESS), _detail((1, "", {"1": "Shuffle everything"})))

    assert steps[0].values == {}
    assert "options" in dropped[0]


def test_an_if_condition_is_checked_like_any_other_choice(backup: None) -> None:
    steps, dropped = _details(
        _plan_of(IF),
        _detail((1, "", {"if_lhs": "%WIFI", "if_op": "= (numeric)", "if_rhs": "1"})),
    )

    assert dropped == []
    assert steps[0].values == {"if_lhs": "%WIFI", "if_op": "= (Numeric)", "if_rhs": "1"}


def test_a_perform_task_may_only_name_a_task_that_exists(backup: None) -> None:
    steps, dropped = _details(
        _plan_of(PERFORM_TASK, PERFORM_TASK), _detail((1, "", {"0": "noisy"}), (2, "", {"0": "Imaginary"}))
    )

    assert steps[0].values == {"0": "Noisy"}
    assert steps[1].values == {}
    assert "no Task named 'Imaginary'" in dropped[0]


def test_an_argument_may_be_named_the_way_the_xml_names_it(backup: None) -> None:
    steps, _ = _details(_plan_of(FLASH), _detail((1, "", {"arg0": "hi"})))
    assert steps[0].values == {"0": "hi"}


def test_an_argument_given_twice_keeps_the_first(backup: None) -> None:
    reply = json.dumps(
        {"steps": [{"step": 1, "label": "", "args": [{"id": "0", "value": "one"}, {"id": "0", "value": "two"}]}]}
    )
    steps, dropped = _details(_plan_of(FLASH), reply)

    assert steps[0].values == {"0": "one"}
    assert "twice" in dropped[0]


def test_an_empty_value_leaves_the_default(backup: None) -> None:
    steps, dropped = _details(_plan_of(FLASH), _detail((1, "", {"0": "", "3": "  "})))

    assert steps[0].values == {}
    assert dropped == []


def test_a_reply_about_a_step_that_does_not_exist_is_dropped(backup: None) -> None:
    steps, dropped = _details(_plan_of(FLASH), _detail((9, "", {"0": "x"}), (0, "", {"0": "y"})))

    assert steps == [mapdraft.DraftStep(FLASH)]
    assert len(dropped) == 2


def test_a_step_the_reply_does_not_mention_keeps_its_defaults(backup: None) -> None:
    steps, dropped = _details(_plan_of(FLASH, WAIT), _detail((2, "", {"0": "1000"})))

    assert steps[0] == mapdraft.DraftStep(FLASH)
    assert steps[1].values == {"0": "1000"}
    assert dropped == []


# ##################################################################################
# Asking.
# ##################################################################################
@pytest.mark.asyncio
async def test_a_description_of_common_actions_is_drafted_in_one_question(backup: None) -> None:
    asked = []

    async def model(settings: mapask.ModelSettings, system: str, user: str) -> str:
        asked.append((settings, user))
        return _plan(
            {"action": FLASH, "purpose": "say hello", "label": "  greet ", "args": {"0": "Hello", "1": "true"}},
            {"action": WAIT, "args": {"1": "5"}},
            name="Hello",
            unexpressed="'when I get home' is a Profile",
        )

    draft = await mapdraft.draft_task("say hello when I get home", _SETTINGS, PrimeItems, ask=model)

    assert len(asked) == 1
    settings, user = asked[0]
    assert (settings.schema, settings.max_tokens) == (mapdraft.PLAN_SCHEMA, mapdraft.PLAN_MAX_TOKENS)
    assert "say hello when I get home" in user
    assert draft.name == "Hello"
    assert draft.steps == (
        mapdraft.DraftStep(FLASH, "greet", {"0": "Hello", "1": "1"}),
        mapdraft.DraftStep(WAIT, "", {"1": "5"}),
    )
    assert draft.unknown == ()
    assert draft.unexpressed == "'when I get home' is a Profile"
    assert not draft.is_empty


@pytest.mark.asyncio
async def test_an_action_listed_among_the_best_matches_needs_no_second_question(backup: None) -> None:
    asked = []

    async def model(settings: mapask.ModelSettings, system: str, user: str) -> str:
        asked.append(user)
        return _plan({"action": "598t", "args": {"0": "%text", "1": "-", "6": "true", "7": "_"}})

    draft = await mapdraft.draft_task("replace the dashes in %text with spaces", _SETTINGS, PrimeItems, ask=model)

    assert len(asked) == 1
    assert draft.steps == (mapdraft.DraftStep("598t", "", {"0": "%text", "1": "-", "6": "1", "7": "_"}),)
    assert not draft.dropped


@pytest.mark.asyncio
async def test_an_action_only_named_among_the_best_matches_is_asked_about_next(
    backup: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mapdraft, "MAX_RELATED_ARGS", 1)
    asked = []

    async def model(settings: mapask.ModelSettings, system: str, user: str) -> str:
        asked.append(user)
        return _plan("598t") if len(asked) == 1 else _detail((1, "", {"0": "%text", "1": "-"}))

    draft = await mapdraft.draft_task("replace the dashes in %text with spaces", _SETTINGS, PrimeItems, ask=model)

    assert len(asked) == 2
    assert draft.steps == (mapdraft.DraftStep("598t", "", {"0": "%text", "1": "-"}),)


@pytest.mark.asyncio
async def test_the_second_question_is_asked_only_about_the_actions_that_were_not_listed(backup: None) -> None:
    asked = []

    async def model(settings: mapask.ModelSettings, system: str, user: str) -> str:
        asked.append((settings.schema, user))
        if len(asked) == 1:
            return _plan({"action": FLASH, "args": {"0": "Hello"}}, (ARRAY_PROCESS, "reverse %list"))
        return _detail((2, "flip", {"1": "reverse"}))

    draft = await mapdraft.draft_task("say hello and reverse my list", _SETTINGS, PrimeItems, ask=model)

    assert [schema for schema, _ in asked] == [mapdraft.PLAN_SCHEMA, mapdraft.DETAIL_SCHEMA]
    # By the plan's own numbering, and the common action is not asked about again.
    assert '"step": 2' in asked[1][1]
    assert '"step": 1' not in asked[1][1]
    assert draft.steps == (
        mapdraft.DraftStep(FLASH, "", {"0": "Hello"}),
        mapdraft.DraftStep(ARRAY_PROCESS, "flip", {"1": "Reverse"}),
    )


@pytest.mark.asyncio
async def test_a_common_action_given_no_arguments_is_asked_about_again(backup: None) -> None:
    """A Flash that comes back with its text only in the purpose must not become a Flash that says nothing."""
    asked = []

    async def model(_settings: mapask.ModelSettings, _system: str, user: str) -> str:
        asked.append(user)
        if len(asked) == 1:
            return _plan((IF, "if %WIFI is on"), (FLASH, "show 'All is Well'"), END_IF, STOP)
        return _detail((2, "", {"0": "All is Well"}))

    draft = await mapdraft.draft_task("flash 'All is Well' if %WIFI is on", _SETTINGS, PrimeItems, ask=model)

    assert len(asked) == 2
    # The If and the Flash had arguments listed and were given none; an End If and a Stop have nothing to give.
    assert '"step": 1' in asked[1]
    assert '"step": 2' in asked[1]
    assert '"step": 3' not in asked[1]
    assert '"step": 4' not in asked[1]
    assert [step.values for step in draft.steps] == [{}, {"0": "All is Well"}, {}, {}]


@pytest.mark.parametrize("spelling", ["0", "arg0", "Text", "text", " TEXT "])
def test_an_argument_may_be_named_by_the_name_it_was_listed_under(backup: None, spelling: str) -> None:
    steps, dropped = _details(_plan_of(FLASH), _detail((1, "", {spelling: "hi"})))

    assert dropped == []
    assert steps[0].values == {"0": "hi"}


@pytest.mark.asyncio
async def test_the_second_question_is_not_asked_when_there_is_nothing_to_set(backup: None) -> None:
    asked = []

    async def model(_settings: mapask.ModelSettings, _system: str, _user: str) -> str:
        asked.append(1)
        return _plan(SYSTEM_LOCK)

    draft = await mapdraft.draft_task("lock the screen", _SETTINGS, PrimeItems, ask=model)

    assert len(asked) == 1
    assert draft.steps == (mapdraft.DraftStep(SYSTEM_LOCK),)


@pytest.mark.asyncio
async def test_the_values_in_the_first_reply_are_checked_like_any_others(backup: None) -> None:
    async def model(*_: object) -> str:
        return _plan(
            {"action": WAIT, "args": {"1": "soon", "2": "7"}},
            {"action": FLASH, "args": {"0": "ok", "99": "x"}},
        )

    draft = await mapdraft.draft_task("wait then flash", _SETTINGS, PrimeItems, ask=model)

    assert [step.values for step in draft.steps] == [{"2": "7"}, {"0": "ok"}]
    assert len(draft.dropped) == 2
    assert draft.dropped[0].startswith("Step 1 (Wait)")
    assert "whole number" in draft.dropped[0]
    assert draft.dropped[1].startswith("Step 2 (Flash)")


@pytest.mark.asyncio
async def test_a_note_names_the_step_as_it_is_numbered_in_the_draft(backup: None) -> None:
    """A step taken out, or one added to close a block, must not shift what a note says."""

    async def model(*_: object) -> str:
        return _plan("Teleport", ELSE, IF, {"action": FLASH, "args": {"1": "maybe"}})

    draft = await mapdraft.draft_task("flash", _SETTINGS, PrimeItems, ask=model)

    assert [step.action_key for step in draft.steps] == [IF, FLASH, END_IF]
    assert draft.dropped[0].startswith("Step 2 (Flash)")


@pytest.mark.asyncio
async def test_the_model_is_asked_not_to_deliberate_and_not_to_take_forever(backup: None) -> None:
    seen = []

    async def model(settings: mapask.ModelSettings, *_: object) -> str:
        seen.append(settings)
        return _plan(ARRAY_PROCESS) if len(seen) == 1 else _detail()

    await mapdraft.draft_task("reverse it", _SETTINGS, PrimeItems, ask=model)

    assert len(seen) == 2
    assert all(settings.effort == "low" for settings in seen)
    assert all(settings.timeout == mapdraft.ASK_TIMEOUT for settings in seen)


@pytest.mark.asyncio
async def test_a_model_on_this_computer_gets_the_short_prompt_and_the_second_question(backup: None) -> None:
    asked = []

    async def model(settings: mapask.ModelSettings, system: str, user: str) -> str:
        asked.append((settings, system, user))
        return _plan(FLASH) if len(asked) == 1 else _detail((1, "", {"0": "Hello"}))

    local = mapask.ModelSettings(mapask.LLAMA, "tinyllama")
    draft = await mapdraft.draft_task("flash hello", local, PrimeItems, ask=model)

    # No arguments were listed for it to fill in, so the second question is how they are asked for.
    assert len(asked) == 2
    assert "Common actions" not in asked[0][2]
    assert asked[0][0].timeout == mapdraft.LOCAL_ASK_TIMEOUT
    assert draft.steps == (mapdraft.DraftStep(FLASH, "", {"0": "Hello"}),)


@pytest.mark.asyncio
async def test_a_plan_with_nothing_usable_in_it_is_an_empty_draft_not_an_error(backup: None) -> None:
    async def model(*_: object) -> str:
        return _plan("Teleport", unexpressed="nothing here does that")

    draft = await mapdraft.draft_task("teleport me", _SETTINGS, PrimeItems, ask=model)

    assert draft.is_empty
    assert draft.unknown == ("Teleport",)
    assert draft.unexpressed == "nothing here does that"


@pytest.mark.asyncio
async def test_an_empty_description_is_not_sent(backup: None) -> None:
    async def model(*_: object) -> str:
        message = "the model should not have been asked"
        raise AssertionError(message)

    with pytest.raises(mapask.AskError, match="Describe"):
        await mapdraft.draft_task("   ", _SETTINGS, PrimeItems, ask=model)


@pytest.mark.asyncio
async def test_nothing_is_drafted_with_no_backup_loaded(backup: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PrimeItems, "xml_root", None)

    async def model(*_: object) -> str:
        message = "the model should not have been asked"
        raise AssertionError(message)

    with pytest.raises(mapask.AskError, match="backup"):
        await mapdraft.draft_task("flash hello", _SETTINGS, PrimeItems, ask=model)


@pytest.mark.asyncio
async def test_a_description_is_cut_to_a_paragraph(backup: None) -> None:
    seen = []

    async def model(_settings: mapask.ModelSettings, _system: str, user: str) -> str:
        seen.append(user)
        return _plan(SYSTEM_LOCK)

    await mapdraft.draft_task("x" * (mapdraft.MAX_DESCRIPTION * 3), _SETTINGS, PrimeItems, ask=model)

    assert "x" * mapdraft.MAX_DESCRIPTION in seen[0]
    assert "x" * (mapdraft.MAX_DESCRIPTION + 1) not in seen[0]


@pytest.mark.asyncio
async def test_cancelling_the_draft_cancels_the_request(backup: None) -> None:
    """Closing the dialog reaches the model's call itself, as it does for the Find's question."""
    started = asyncio.Event()
    outcome = {}

    async def waiting(*_: object) -> str:
        started.set()
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            outcome["cancelled"] = True
            raise
        return _plan(FLASH)

    task = asyncio.create_task(mapdraft.draft_task("flash hello", _SETTINGS, PrimeItems, ask=waiting))
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert outcome == {"cancelled": True}


@pytest.mark.asyncio
async def test_the_requested_reply_shape_reaches_the_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """A draft's schema and token limit go to the model, not the Find's."""
    sent = {}

    class Messages:
        async def create(self, **kwargs: object) -> object:
            sent.update(kwargs)
            return type("Reply", (), {"content": [type("Block", (), {"text": "{}"})()]})()

    class AsyncAnthropic:
        def __init__(self, api_key: str) -> None:
            self.messages = Messages()

        async def __aenter__(self) -> AsyncAnthropic:
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

    monkeypatch.setattr(mapask, "_library", lambda *_: type("Lib", (), {"AsyncAnthropic": AsyncAnthropic}))
    await mapask.ask_model(replace(_SETTINGS, schema=mapdraft.PLAN_SCHEMA), "system", "user")

    assert sent["output_config"]["format"]["schema"] == mapdraft.PLAN_SCHEMA

    sent.clear()
    await mapask.ask_model(_SETTINGS, "system", "user")
    assert sent["output_config"]["format"]["schema"] == mapask.REPLY_SCHEMA


# ##################################################################################
# Putting the draft in the editor.
# ##################################################################################
def _new_task() -> taskedit_model.EditableTask:
    task = taskedit.create_new_task("", "100", state=PrimeItems)
    assert not isinstance(task, str)
    return task


def _draft(*steps: mapdraft.DraftStep) -> mapdraft.Draft:
    return mapdraft.Draft("", tuple(steps))


def test_a_draft_is_built_the_way_a_hand_added_action_is(backup: None) -> None:
    task = _new_task()
    draft = _draft(
        mapdraft.DraftStep(FLASH, "greet", {"0": "Hello %city", "1": "1"}),
        mapdraft.DraftStep(WAIT, "", {"1": "5"}),
        mapdraft.DraftStep(ARRAY_PROCESS, "", {"1": "Reverse"}),
    )
    applied = mapdraft.apply_draft(task, draft, PrimeItems)

    assert (applied.first_act_number, applied.added, applied.notes) == (0, 3, ())
    assert [action.action_name for action in task.actions] == ["Flash", "Wait", "Array Process"]

    flash = task.actions[0]
    assert taskedit_apply.get_action_label(flash) == "greet"
    # In the XML, where a save reads it from...
    assert flash.action_element.find("Str[@sr='arg0']").text == "Hello %city"
    assert flash.action_element.find("Int[@sr='arg1']").get("val") == "1"
    # ...and in what the editor shows, which is what the user reviews.
    shown = {arg.arg_id: arg.current_value for arg in flash.args}
    assert (shown["0"], shown["1"]) == ("Hello %city", "1")
    wait = {arg.arg_id: arg.current_value for arg in task.actions[1].args}
    assert wait["1"] == "5"
    array = next(arg for arg in task.actions[2].args if arg.arg_id == "1")
    assert array.dropdown_options[int(array.current_value)] == "Reverse"


def test_an_argument_the_draft_leaves_out_keeps_the_editors_default(backup: None) -> None:
    drafted = _new_task()
    mapdraft.apply_draft(drafted, _draft(mapdraft.DraftStep(FLASH, "", {"0": "hi"})), PrimeItems)
    by_hand = _new_task()
    taskedit.add_action_to_task(by_hand, FLASH, state=PrimeItems)

    flash = {arg.arg_id: arg.current_value for arg in drafted.actions[0].args}
    plain = {arg.arg_id: arg.current_value for arg in by_hand.actions[0].args}
    assert flash.pop("0") == "hi"
    plain.pop("0")
    assert flash == plain


def test_a_draft_is_added_after_what_the_editor_already_holds(backup: None) -> None:
    task = _new_task()
    taskedit.add_action_to_task(task, WAIT, state=PrimeItems)
    taskedit.add_action_to_task(task, FLASH, state=PrimeItems)

    applied = mapdraft.apply_draft(
        task, _draft(mapdraft.DraftStep(VARIABLE_SET, "", {"0": "%a", "1": "1"})), PrimeItems
    )

    assert applied.first_act_number == 2
    assert [action.action_name for action in task.actions] == ["Wait", "Flash", "Variable Set"]
    assert [action.act_number for action in task.actions] == [0, 1, 2]


def test_a_draft_changes_nothing_that_is_loaded(backup: None) -> None:
    before = {
        table: {key: entry["xml"] for key, entry in PrimeItems.tasker_root_elements[table].items()}
        for table in ("all_tasks", "all_profiles", "all_projects")
    }
    task = _new_task()
    mapdraft.apply_draft(
        task,
        _draft(mapdraft.DraftStep(IF, "", {"if_lhs": "%a", "if_rhs": "b"}), mapdraft.DraftStep(END_IF)),
        PrimeItems,
    )

    for table, elements in before.items():
        assert {key: entry["xml"] for key, entry in PrimeItems.tasker_root_elements[table].items()} == elements
    assert task.task_element.attrib["sr"] not in {
        str(entry["xml"].attrib.get("sr")) for entry in PrimeItems.tasker_root_elements["all_tasks"].values()
    }
    assert all(entry["xml"].findtext("nme") != "" for entry in PrimeItems.tasker_root_elements["all_tasks"].values())


def test_an_if_condition_is_written_where_the_editor_reads_it(backup: None) -> None:
    task = _new_task()
    mapdraft.apply_draft(
        task,
        _draft(mapdraft.DraftStep(IF, "", {"if_lhs": "%WIFI", "if_op": "Is Set"}), mapdraft.DraftStep(END_IF)),
        PrimeItems,
    )

    shown = {arg.arg_id: arg.current_value for arg in task.actions[0].args}
    assert shown["if_lhs"] == "%WIFI"
    assert task.actions[0].args[1].dropdown_options[int(shown["if_op"])] == "Is Set"


def test_an_if_condition_that_fails_the_editors_check_is_left_empty_and_said(backup: None) -> None:
    task = _new_task()
    applied = mapdraft.apply_draft(
        task,
        _draft(
            mapdraft.DraftStep(IF, "check", {"if_lhs": "%a b c!", "if_op": "=", "if_rhs": "x"}),
            mapdraft.DraftStep(END_IF),
        ),
        PrimeItems,
    )

    assert applied.added == 2
    assert any("Step 1 (If)" in note and "defaults" in note for note in applied.notes)
    assert {arg.arg_id: arg.current_value for arg in task.actions[0].args}["if_lhs"] == ""
    # What did pass is still there.
    assert taskedit_apply.get_action_label(task.actions[0]) == "check"


def test_a_plugin_action_is_said_to_need_configuring(backup: None) -> None:
    plugin = next(
        row["action_key"]
        for row in mapdraft.action_catalog(PrimeItems)
        if (action := taskedit.add_action_to_task(_new_task(), row["action_key"], state=PrimeItems))
        and not isinstance(action, list)
        and taskedit_addable.needs_tasker_configuration(action.action_element)
    )
    task = _new_task()
    applied = mapdraft.apply_draft(task, _draft(mapdraft.DraftStep(plugin)), PrimeItems)

    assert applied.added == 1
    assert any("configured within Tasker" in note for note in applied.notes)


def test_an_action_that_can_no_longer_be_added_is_said(backup: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """What is addable follows the loaded inventory, which can change between asking and applying."""
    real = taskedit.add_action_to_task

    def refusing(task: taskedit_model.EditableTask, key: str, position: int | None = None, *, state: object) -> object:
        return ["Requires something that is gone."] if key == WAIT else real(task, key, position, state=state)

    monkeypatch.setattr(taskedit, "add_action_to_task", refusing)
    task = _new_task()
    applied = mapdraft.apply_draft(task, _draft(mapdraft.DraftStep(WAIT), mapdraft.DraftStep(FLASH)), PrimeItems)

    assert (applied.first_act_number, applied.added) == (0, 1)
    assert [action.action_name for action in task.actions] == ["Flash"]
    assert "Step 1 (Wait)" in applied.notes[0]


def test_an_empty_draft_adds_nothing(backup: None) -> None:
    task = _new_task()
    applied = mapdraft.apply_draft(task, _draft(), PrimeItems)

    assert (applied.first_act_number, applied.added) == (None, 0)
    assert task.actions == []


def test_a_drafted_task_saves_like_any_other(backup: None) -> None:
    """The draft is a Task the editor can validate and write: nothing about it is special."""
    task = _new_task()
    mapdraft.apply_draft(
        task,
        _draft(
            mapdraft.DraftStep(IF, "", {"if_lhs": "%WIFI", "if_op": "Is Set"}),
            mapdraft.DraftStep(FLASH, "hi", {"0": "Hello"}),
            mapdraft.DraftStep(END_IF),
        ),
        PrimeItems,
    )

    assert taskedit_apply.apply_edits_to_task(task, "Drafted", "100", {}, PrimeItems) == []
    xml = taskedit_save.render_standalone_task_xml(task, state=PrimeItems)
    assert "<nme>Drafted</nme>" in xml
    assert "<label>hi</label>" in xml
    assert "Hello" in xml
