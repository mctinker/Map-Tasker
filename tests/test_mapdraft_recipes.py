"""MapTasker AI Task drafting: the worked examples (draft_recipes.json) Unit Tests

A recipe is a description and the draft that answers it.  The nearest few are shown to the model
beside the user's description (mapcards.similar_recipes), and the same recipes are the test set:

  * every recipe is run through the whole pipeline -- prompt, reply, checks, build -- with a model
    that answers with the recipe itself, so a recipe that names an action, argument or choice the
    editor no longer has fails here and not in front of a user;
  * every recipe's held-out wording, which the examples are never matched against, has to find the
    recipe, so the ranking is tested on descriptions it has not seen;
  * an opt-in run puts the same descriptions to a real model and scores what comes back, with the
    recipe taken out of the examples so that it is not simply copied.  Set MAPTASKER_DRAFT_EVAL to
    "<provider>:<model>" (Anthropic, OpenAI or Gemini) and the provider's usual API key variable
    (ANTHROPIC_API_KEY, OPENAI_API_KEY or GEMINI_API_KEY), and run this file with -s to see the table.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import pytest
from maptasker.src.analysis import mapask
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import taskedit, taskedit_args
from maptasker.src.mapops import mapcards, mapdraft

_SETTINGS = mapask.ModelSettings(mapask.ANTHROPIC, "claude-sonnet-5", "test-key")
_RECIPES = mapcards.recipes()
_IDS = [recipe.recipe_id for recipe in _RECIPES]

# The Tasks the recipes name, so that a Perform Task in one is checked against a Task that "exists".
_TASK_NAMES = ["Cleanup", "Noisy", "Opener", "Quiet"]


@pytest.fixture
def tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    """The loaded backup has Tasks of its own; the recipes' Perform Task names are added to them."""
    monkeypatch.setattr(taskedit_args, "get_all_task_names", lambda *_args, **_kwargs: list(_TASK_NAMES))


def _reply(recipe: mapcards.Recipe) -> str:
    """The first reply that answers a recipe: its draft, with every argument."""
    return json.dumps(
        {
            "name": recipe.name,
            "steps": [
                {
                    "action": step.action,
                    "purpose": step.purpose,
                    "label": step.label,
                    "args": [{"id": key, "value": value} for key, value in step.args.items()],
                }
                for step in recipe.steps
            ],
            "unexpressed": recipe.unexpressed,
        },
    )


def _oracle(recipe: mapcards.Recipe) -> mapask.Asker:
    """A model that knows the answer: the recipe's draft for the first question, its arguments for the second."""

    async def ask(settings: mapask.ModelSettings, system: str, user: str) -> str:
        if settings.schema is not mapdraft.DETAIL_SCHEMA:
            return _reply(recipe)
        asked = [json.loads(line) for line in user.splitlines() if line.startswith("{")]
        return json.dumps(
            {
                "steps": [
                    {
                        "step": item["step"],
                        "label": "",
                        "args": [{"id": k, "value": v} for k, v in recipe.steps[item["step"] - 1].args.items()],
                    }
                    for item in asked
                ],
            },
        )

    return ask


@dataclass(frozen=True)
class Score:
    """How near a draft came to a recipe's."""

    same_actions: bool
    arguments: int
    arguments_right: int
    dropped: int


def _normal(value: str) -> str:
    """A value as a draft stores it: a yes or no is 1 or 0."""
    return {"true": "1", "false": "0"}.get(value.strip().casefold(), value)


def _score(recipe: mapcards.Recipe, draft: mapdraft.Draft) -> Score:
    """Compare a draft with a recipe: the same actions in the same order, and how many of its arguments came out."""
    same = [step.action_key for step in draft.steps] == [step.action for step in recipe.steps]
    wanted = right = 0
    if same:
        for step, drafted in zip(recipe.steps, draft.steps, strict=True):
            for key, value in step.args.items():
                wanted += 1
                right += drafted.values.get(key, "").casefold() == _normal(value).casefold()
    return Score(same, wanted, right, len(draft.dropped) + len(draft.unknown) + len(draft.adjusted))


# ##################################################################################
# The file.
# ##################################################################################
def test_the_recipes_are_a_usable_set() -> None:
    assert len(_RECIPES) >= 30
    assert len(set(_IDS)) == len(_IDS)
    for recipe in _RECIPES:
        assert recipe.description.strip()
        assert recipe.steps, recipe.recipe_id
        assert recipe.held_out.strip(), recipe.recipe_id
        # The held-out wording is for testing, so it must not be one the recipe is matched against.
        assert recipe.held_out != recipe.description
        assert recipe.held_out not in recipe.also
    # No two recipes answer the same description.
    assert len({recipe.description.casefold() for recipe in _RECIPES}) == len(_RECIPES)


def test_the_recipes_cover_the_shapes_a_model_gets_wrong() -> None:
    used = {step.action for recipe in _RECIPES for step in recipe.steps}

    assert {"37t", "43t", "38t"} <= used  # If, Else, End If
    assert {"39t", "40t"} <= used  # a loop
    assert "130t" in used  # Perform Task
    assert any(recipe.unexpressed for recipe in _RECIPES)  # a trigger the Task cannot hold
    assert any(sum(step.action == "37t" for step in recipe.steps) > 1 for recipe in _RECIPES)  # nested Ifs


# ##################################################################################
# A recipe is a draft the pipeline accepts.
# ##################################################################################
@pytest.mark.asyncio
@pytest.mark.parametrize("recipe", _RECIPES, ids=_IDS)
async def test_a_recipe_is_drafted_exactly_as_written_with_nothing_dropped(
    backup: None,
    tasks: None,
    recipe: mapcards.Recipe,
) -> None:
    draft = await mapdraft.draft_task(recipe.description, _SETTINGS, PrimeItems, ask=_oracle(recipe))

    score = _score(recipe, draft)
    assert draft.dropped == (), draft.dropped
    assert draft.unknown == ()
    assert draft.adjusted == ()
    assert score.same_actions
    assert score.arguments_right == score.arguments, [(s.action_key, s.values) for s in draft.steps]
    assert draft.name == recipe.name
    assert draft.unexpressed == recipe.unexpressed


@pytest.mark.parametrize("recipe", _RECIPES, ids=_IDS)
def test_a_recipe_builds_into_the_editor_without_a_note(
    backup: None,
    tasks: None,
    recipe: mapcards.Recipe,
) -> None:
    draft = mapdraft.Draft(
        recipe.name,
        tuple(
            mapdraft.DraftStep(step.action, step.label, {k: _normal(v) for k, v in step.args.items()})
            for step in recipe.steps
        ),
    )
    edited = taskedit.create_new_task("recipe", "100", state=PrimeItems)
    assert not isinstance(edited, str)

    applied = mapdraft.apply_draft(edited, draft, PrimeItems)

    assert applied.added == len(recipe.steps)
    assert applied.notes == ()


# ##################################################################################
# The examples a question carries.
# ##################################################################################
@pytest.mark.parametrize("recipe", _RECIPES, ids=_IDS)
def test_a_recipe_asked_about_finds_itself_with_every_argument_shown(
    backup: None,
    recipe: mapcards.Recipe,
) -> None:
    """The example for its own description loses no argument: each is one the question listed for its action."""
    _, user = mapdraft.build_plan_prompt(recipe.description, PrimeItems)

    assert f"Description: {recipe.description}\nReply: " in user
    reply = user.split(f"Description: {recipe.description}\nReply: ", 1)[1].splitlines()[0]
    shown = json.loads(reply)
    assert [step["action"] for step in shown["steps"]] == [step.action for step in recipe.steps]
    for step, original in zip(shown["steps"], recipe.steps, strict=True):
        assert {item["id"]: item["value"] for item in step["args"]} == dict(original.args), original.action


@pytest.mark.parametrize("recipe", _RECIPES, ids=_IDS)
def test_a_description_in_other_words_finds_its_recipe(recipe: mapcards.Recipe) -> None:
    found = [near.recipe_id for near in mapcards.similar_recipes(recipe.held_out)]

    assert recipe.recipe_id in found, found


def test_a_recipe_found_by_its_own_description_comes_first() -> None:
    for recipe in _RECIPES:
        assert mapcards.similar_recipes(recipe.description)[0].recipe_id == recipe.recipe_id


def test_a_description_that_nothing_resembles_gets_no_examples(backup: None) -> None:
    assert mapcards.similar_recipes("zzzz qqqq") == []
    _, user = mapdraft.build_plan_prompt("zzzz qqqq", PrimeItems)

    assert "Examples of replies" not in user


def test_the_examples_are_the_nearest_few_and_come_before_the_description(backup: None) -> None:
    description = "wait 10 seconds then say 'Hi'"
    _, user = mapdraft.build_plan_prompt(description, PrimeItems)

    assert 1 <= user.count("\nReply: ") <= mapcards.MAX_RECIPES
    assert user.index("Examples of replies to similar descriptions:") < user.rindex(f"Description: {description}")
    assert user.endswith(f"Description: {description}")


def test_a_small_model_is_shown_no_examples(backup: None) -> None:
    _, user = mapdraft.build_plan_prompt("wait 10 seconds then say 'Hi'", PrimeItems, compact=True)

    assert "Examples of replies" not in user
    assert "Reply:" not in user


def test_an_example_never_does_what_the_questions_rules_forbid(backup: None) -> None:
    """An action listed without arguments is given [] -- so the example gives it none either."""
    recipe = next(recipe for recipe in _RECIPES if recipe.recipe_id == "ask-name")

    text = mapcards.example_text(recipe, {"559t": {"0"}})
    steps = json.loads(text.split("Reply: ", 1)[1])["steps"]

    assert steps[0]["args"] == []  # Input Dialog was not listed with its arguments
    assert steps[1]["args"] == [{"id": "0", "value": "Hello %name"}]
    narrower = json.loads(mapcards.example_text(recipe, {"559t": set()}).split("Reply: ", 1)[1])["steps"]
    assert narrower[1]["args"] == []  # an argument that was not listed is left out too


def test_the_actions_an_example_uses_are_listed_with_their_arguments(backup: None) -> None:
    description = "ask me my name and say hello to them"
    related = mapdraft.related_actions(description, PrimeItems)
    listed = mapdraft.listed_with_arguments(description, PrimeItems)

    assert "360t" in related  # Input Dialog, which the matching example uses
    assert "360t" in listed
    assert {"8", "2"} <= {arg.arg_id for arg in listed["360t"]}


def test_an_example_is_left_out_if_the_editor_cannot_build_what_it_uses(backup: None) -> None:
    everything = mapcards.similar_recipes("ask me my name and say hello to them")
    without_input_dialog = mapcards.similar_recipes(
        "ask me my name and say hello to them",
        available={row["action_key"] for row in mapdraft.action_catalog(PrimeItems)} - {"360t"},
    )

    assert any("360t" in recipe.action_keys for recipe in everything)
    assert all("360t" not in recipe.action_keys for recipe in without_input_dialog)


def test_the_examples_carry_nothing_of_the_users(backup: None) -> None:
    system, user = mapdraft.build_plan_prompt("flash the total", PrimeItems)

    for private in ("Noisy", "Opener", "Quiet", "Done: %n", "flash the total's", "com.spotify"):
        assert private not in system + user


@pytest.mark.asyncio
async def test_a_description_with_examples_is_still_drafted_in_one_question(backup: None) -> None:
    asked = []
    recipe = next(recipe for recipe in _RECIPES if recipe.recipe_id == "wait-say")

    async def model(settings: mapask.ModelSettings, system: str, user: str) -> str:
        asked.append(user)
        return _reply(recipe)

    draft = await mapdraft.draft_task("wait 45 seconds then say 'Dinner'", _SETTINGS, PrimeItems, ask=model)

    assert len(asked) == 1
    assert "Examples of replies" in asked[0]
    assert _score(recipe, draft).same_actions


# ##################################################################################
# The scoring, and an opt-in run against a real model.
# ##################################################################################
@pytest.mark.asyncio
async def test_a_model_that_gets_it_wrong_scores_low(backup: None, tasks: None) -> None:
    recipe = _RECIPES[0]
    other = _RECIPES[1]

    draft = await mapdraft.draft_task(recipe.description, _SETTINGS, PrimeItems, ask=_oracle(other))

    assert not _score(recipe, draft).same_actions


_LIVE = os.environ.get("MAPTASKER_DRAFT_EVAL", "")
_KEYS = {
    mapask.ANTHROPIC: "ANTHROPIC_API_KEY",
    mapask.OPENAI: "OPENAI_API_KEY",
    mapask.GEMINI: "GEMINI_API_KEY",
}


@pytest.mark.asyncio
@pytest.mark.skipif(not _LIVE, reason="set MAPTASKER_DRAFT_EVAL=<provider>:<model> to score a real model")
async def test_a_real_model_drafts_the_recipes_from_their_held_out_wording(
    backup: None,
    tasks: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider, _, model = _LIVE.partition(":")
    provider = next((name for name in _KEYS if name.casefold() == provider.strip().casefold()), "")
    assert provider, f"MAPTASKER_DRAFT_EVAL must start with one of {', '.join(_KEYS)}"
    key = os.environ.get(_KEYS[provider], "")
    assert key, f"{_KEYS[provider]} is not set"
    settings = mapask.ModelSettings(provider, model.strip(), key)

    rows = []
    for recipe in _RECIPES:
        # The recipe being asked about is taken out of the examples, or the model would only copy it.
        others = tuple(other for other in _RECIPES if other is not recipe)
        with monkeypatch.context() as patch:
            patch.setattr(mapcards, "recipes", lambda others=others: others)
            try:
                draft = await mapdraft.draft_task(recipe.held_out, settings, PrimeItems)
            except mapask.AskError as error:
                rows.append((recipe.recipe_id, None, str(error)))
                continue
        rows.append((recipe.recipe_id, _score(recipe, draft), ""))

    scored = [(name, score) for name, score, _ in rows if score is not None]
    for name, score, error in rows:
        if score is None:
            print(f"{name:24} ERROR {error}")
        else:
            print(
                f"{name:24} actions {'ok ' if score.same_actions else 'NO '}"
                f" args {score.arguments_right}/{score.arguments}  left out {score.dropped}",
            )
    actions_ok = sum(score.same_actions for _, score in scored) / len(_RECIPES)
    arguments = sum(score.arguments for _, score in scored if score.same_actions)
    arguments_ok = sum(score.arguments_right for _, score in scored if score.same_actions) / (arguments or 1)
    print(f"\n{provider}:{model}  same actions {actions_ok:.0%}  arguments right {arguments_ok:.0%}")

    floor = float(os.environ.get("MAPTASKER_DRAFT_EVAL_MIN", "0.6"))
    assert actions_ok >= floor, f"only {actions_ok:.0%} of the recipes were drafted with the right actions"
