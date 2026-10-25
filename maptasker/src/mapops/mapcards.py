"""mapcards: what a model is told about an action, and which actions and examples a description is about."""

#! /usr/bin/env python3

#                                                                                        #
# mapcards: the knowledge mapdraft gives a model beyond the names of the actions.         #
#                                                                                        #
# A model that is shown "596t Variable Convert" and "598t Variable Search Replace" has no   #
# way to know that the first does Base64 and the second is what "remove the dashes" wants.  #
# action_cards.json says so, in a sentence and a few of the words a person would use, for   #
# the actions a description in plain words most often needs -- and, where there is one, the  #
# pitfall that a model gets wrong ("Level is 0 to 15").  What it holds is the same for every  #
# user and every backup, so nothing in it can leak what a user's Tasks contain.             #
#                                                                                        #
# The arguments are deliberately NOT in the cards.  They are read off the editor itself (see  #
# mapdraft.fillable_args), so they cannot drift from what the editor builds; a card is only   #
# the part a machine cannot read off the editor.                                          #
#                                                                                        #
# rank() picks which actions to show a model in full.  It scores the description against      #
# each action's name, card phrases and sentence with BM25, which is plain arithmetic on word   #
# counts: no model is asked, nothing is downloaded, and the same description always picks the  #
# same actions.  An action with no card is still found by its name.                         #
#                                                                                        #
# draft_recipes.json is the other half: worked examples, a description and the draft that    #
# answers it.  A rule ("close every If") is followed less reliably than an example is copied,  #
# so the few recipes nearest the user's description are shown beside it (similar_recipes,      #
# found the same way).  The same recipes are what the tests build through the whole pipeline,   #
# and what an optional live run scores a model against.                                      #
#                                                                                        #
# Same contract as mapdraft: no GUI import.                                                #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

import itertools
import json
import math
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import cache
from typing import TYPE_CHECKING, Any

from maptasker.src.core.actionc import action_codes
from maptasker.src.core.taskervars import tasker_global_variable_names

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

# A catalog row, as taskedit_addable lists them: action_key, name, category_name and so on.
Row = dict[str, Any]

CARDS_FILE = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "json", "action_cards.json"),
)

RECIPES_FILE = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "json", "draft_recipes.json"),
)

# How many recipes are shown with a question, and how near the best one another has to score to be
# shown too: a recipe a third as relevant as the best is noise, not a second example.
MAX_RECIPES = 3
RECIPE_CUTOFF = 0.4

# How much a word counts for, by where it was found: an action's name says most about it.
_NAME_WEIGHT = 3
_PHRASE_WEIGHT = 2
_SENTENCE_WEIGHT = 1
_CATEGORY_WEIGHT = 1

# BM25's usual constants.
_K1 = 1.2
_B = 0.75

# Words that say nothing about which action is wanted.
_STOP_WORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "do",
        "does",
        "for",
        "from",
        "has",
        "have",
        "how",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "me",
        "my",
        "of",
        "on",
        "one",
        "or",
        "so",
        "that",
        "the",
        "then",
        "there",
        "this",
        "to",
        "up",
        "was",
        "when",
        "where",
        "which",
        "will",
        "with",
        "you",
        "your",
        "please",
        "should",
        "would",
        "then",
        "after",
        "before",
        "again",
        "also",
        "just",
        "now",
    ],
)

_WORD = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class Card:
    """What is known about one action beyond its name."""

    does: str
    phrases: tuple[str, ...] = ()
    note: str = ""


@cache
def cards() -> dict[str, Card]:
    """action_cards.json, by action key, read the first time it is wanted."""
    with open(CARDS_FILE, encoding="utf-8") as file:
        raw = json.load(file)["cards"]
    return {key: Card(item["does"], tuple(item.get("phrases", ())), item.get("note", "")) for key, item in raw.items()}


def card_lines(action_key: str) -> list[str]:
    """The lines a prompt shows under an action, each already indented: what it does, and its pitfall."""
    card = cards().get(action_key)
    if card is None:
        return []
    lines = [f"    {card.does}"]
    if card.note:
        lines.append(f"    Note: {card.note}")
    return lines


# ##################################################################################
# Matching a description to actions.
# ##################################################################################
def _stem(word: str) -> str:
    """A word cut back to something its other forms share: 'vibrating', 'vibrates' and 'vibrate' all become 'vibrat'."""
    if len(word) > 5 and word.endswith("ing"):
        word = word[:-3]
        if len(word) > 2 and word[-1] == word[-2] and word[-1] not in "ls":
            word = word[:-1]
    elif len(word) > 4 and word.endswith("ies"):
        word = f"{word[:-3]}y"
    elif len(word) > 4 and word.endswith("ed"):
        word = word[:-2]
        if len(word) > 2 and word[-1] == word[-2] and word[-1] not in "ls":
            word = word[:-1]
    elif len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us")):
        word = word[:-1]
    if len(word) > 3 and word.endswith("e"):
        word = word[:-1]
    return word


def terms(text: str) -> list[str]:
    """The words of a text that can say what is wanted, stemmed, and each pair of neighbours as one more term.

    The pairs are what lets "do not disturb" and "text message" count for more than "text" and "do"
    would apart.
    """
    words = [_stem(word) for word in _WORD.findall(text.casefold()) if word not in _STOP_WORDS and len(word) > 1]
    return words + [f"{first}_{second}" for first, second in itertools.pairwise(words)]


def _document(row: Row) -> Counter[str]:
    """The weighted terms of one action: its name, then what its card says, then its category."""
    document: Counter[str] = Counter()
    for term in terms(row["name"]):
        document[term] += _NAME_WEIGHT
    card = cards().get(row["action_key"])
    if card is not None:
        for phrase in card.phrases:
            for term in terms(phrase):
                document[term] += _PHRASE_WEIGHT
        for term in terms(card.does):
            document[term] += _SENTENCE_WEIGHT
    # A backup that has not named its categories calls them all this, which says nothing.
    category = row.get("category_name", "")
    if category and category != "Uncategorized":
        for term in terms(category):
            document[term] += _CATEGORY_WEIGHT
    return document


def _scores(wanted: Collection[str], documents: list[Counter[str]]) -> dict[int, float]:
    """BM25 of each document that shares a term with 'wanted', by the document's position."""
    totals: defaultdict[int, float] = defaultdict(float)
    if not documents:
        return totals
    lengths = [sum(document.values()) for document in documents]
    average = (sum(lengths) / len(lengths)) or 1.0
    count = len(documents)
    for term in wanted:
        holders = sum(term in document for document in documents)
        if not holders:
            continue
        idf = math.log(1 + (count - holders + 0.5) / (holders + 0.5))
        for number, document in enumerate(documents):
            frequency = document.get(term, 0)
            if frequency:
                norm = frequency * (_K1 + 1) / (frequency + _K1 * (1 - _B + _B * lengths[number] / average))
                totals[number] += idf * norm
    return totals


def rank(description: str, rows: list[Row], limit: int) -> list[Row]:
    """The rows (catalog rows, as taskedit_addable lists them) that best match a description, best first.

    Only rows that share at least one term with the description are returned, so a description
    with nothing in it that any action is about gets none rather than the first few alphabetically.
    Ties go to the shorter name and then the name, so the order is the same on every run.
    """
    wanted = set(terms(description))
    if not wanted or not rows:
        return []
    totals = _scores(wanted, [_document(row) for row in rows])
    best = sorted(totals, key=lambda number: (-totals[number], len(rows[number]["name"]), rows[number]["name"]))
    return [rows[number] for number in best[:limit]]


# ##################################################################################
# Names: Tasker's own variables, and the user's.
# ##################################################################################
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")

# The shortest name that is taken as mentioned just by appearing in the description.
_MENTION_MIN = 3


def name_terms(name: str) -> list[str]:
    """The terms of a name a person chose -- 'WakeUp', 'wake_up' and 'Wake up' all give the same ones."""
    return terms(_CAMEL.sub(" ", name.replace("%", " ").replace("_", " ")))


def rank_names(description: str, names: Collection[str], limit: int) -> list[str]:
    """The names a description seems to mean, best first: one it mentions outright, or shares a word with.

    A name nothing in the description points to is not returned however well it might fit, because
    what is returned is what gets shown to a model, and a user's names are not shown without cause.
    """
    mentioned = description.casefold()
    listed = sorted(set(names))
    named = [
        name
        for name in listed
        if len(name.strip("%")) >= _MENTION_MIN
        and re.search(rf"(?<![0-9a-z]){re.escape(name.casefold())}(?![0-9a-z])", mentioned)
    ]
    wanted = set(terms(description))
    documents = [Counter(name_terms(name)) for name in listed]
    totals = _scores(wanted, documents)
    shared = sorted(totals, key=lambda number: (-totals[number], listed[number]))
    ranked = named + [listed[number] for number in shared if listed[number] not in named]
    return ranked[:limit]


def builtin_variables(description: str, limit: int) -> list[tuple[str, str]]:
    """Tasker's own variables a description seems to be about, as (name, what it holds), best first."""
    entries = sorted(tasker_global_variable_names.items())
    wanted = set(terms(description))
    if not wanted:
        return []
    documents: list[Counter[str]] = []
    for name, label in entries:
        document: Counter[str] = Counter()
        for term in terms(label):
            document[term] += _NAME_WEIGHT
        for term in name_terms(name):
            document[term] += _PHRASE_WEIGHT
        documents.append(document)
    totals = _scores(wanted, documents)
    best = sorted(totals, key=lambda number: (-totals[number], entries[number][0]))
    return [entries[number] for number in best[:limit]]


# ##################################################################################
# Worked examples.
# ##################################################################################
@dataclass(frozen=True)
class RecipeStep:
    """One action of a recipe: which, what for, and the arguments it sets by the id the editor gives each."""

    action: str
    purpose: str = ""
    label: str = ""
    args: Mapping[str, str] = field(default_factory=lambda: {})  # noqa: PIE807


@dataclass(frozen=True)
class Recipe:
    """A description and the draft that answers it."""

    recipe_id: str
    description: str
    steps: tuple[RecipeStep, ...]
    name: str = ""
    unexpressed: str = ""
    # Other ways of saying it, matched against like the description.
    also: tuple[str, ...] = ()
    # One more way of saying it, never matched against: what a test asks to see whether a description
    # the recipe has not seen still finds it.
    held_out: str = ""

    @property
    def action_keys(self) -> list[str]:
        """The actions the recipe uses, in order, each once."""
        return list(dict.fromkeys(step.action for step in self.steps))


def _recipe_step(raw: dict[str, Any]) -> RecipeStep:
    """One step as draft_recipes.json writes it."""
    given: dict[str, Any] = raw.get("args", {})
    args = {str(key): str(value) for key, value in given.items()}
    return RecipeStep(raw["action"], raw.get("purpose", ""), raw.get("label", ""), args)


@cache
def recipes() -> tuple[Recipe, ...]:
    """draft_recipes.json, in the order it is written, read the first time it is wanted."""
    with open(RECIPES_FILE, encoding="utf-8") as file:
        raw = json.load(file)["recipes"]
    return tuple(
        Recipe(
            recipe_id=item["id"],
            description=item["description"],
            steps=tuple(_recipe_step(step) for step in item["steps"]),
            name=item.get("name", ""),
            unexpressed=item.get("unexpressed", ""),
            also=tuple(item.get("also", ())),
            held_out=item.get("held_out", ""),
        )
        for item in raw
    )


def _recipe_document(recipe: Recipe) -> Counter[str]:
    """The weighted terms of one recipe: what it answers, other ways of saying it, then what it uses."""
    document: Counter[str] = Counter()
    for term in terms(recipe.description):
        document[term] += _NAME_WEIGHT
    for phrase in recipe.also:
        for term in terms(phrase):
            document[term] += _PHRASE_WEIGHT
    for step in recipe.steps:
        code = action_codes.get(step.action)
        for term in terms(f"{code.name if code else ''} {step.purpose}"):
            document[term] += _SENTENCE_WEIGHT
    return document


def similar_recipes(
    description: str, limit: int = MAX_RECIPES, available: Collection[str] | None = None
) -> list[Recipe]:
    """The recipes whose descriptions are nearest to this one, nearest first.

    'available' are the action keys the editor can build; a recipe that uses one that is not among
    them is left out, since an example may not teach an action the model cannot use.  Only recipes at
    least RECIPE_CUTOFF as relevant as the best are returned, and none if nothing is shared.
    """
    wanted = set(terms(description))
    pool = [recipe for recipe in recipes() if available is None or set(recipe.action_keys) <= set(available)]
    if not wanted or not pool:
        return []
    totals = _scores(wanted, [_recipe_document(recipe) for recipe in pool])
    if not totals:
        return []
    best = sorted(totals, key=lambda number: (-totals[number], pool[number].recipe_id))
    top = totals[best[0]]
    return [pool[number] for number in best[:limit] if totals[number] >= top * RECIPE_CUTOFF]


def example_text(recipe: Recipe, shown: Mapping[str, Collection[str]]) -> str:
    """A recipe as the model reads it: its description, then the reply that answers it, as JSON.

    'shown' maps an action key to the ids of the arguments the question lists for it.  An argument
    that was not listed is left out of the example, as is every argument of an action that was not
    listed at all, so that the example never does what the question's own rules say not to.
    """
    steps: list[dict[str, object]] = []
    for step in recipe.steps:
        listed = set(shown.get(step.action, ()))
        steps.append(
            {
                "action": step.action,
                "purpose": step.purpose,
                "label": step.label,
                "args": [{"id": key, "value": value} for key, value in step.args.items() if key in listed],
            },
        )
    reply: dict[str, object] = {"name": recipe.name, "steps": steps, "unexpressed": recipe.unexpressed}
    return f"Description: {recipe.description}\nReply: {json.dumps(reply, ensure_ascii=False)}"
