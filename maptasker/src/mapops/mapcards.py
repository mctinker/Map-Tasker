"""mapcards: what a model is told about an action, and which actions a description is about."""

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
from dataclasses import dataclass
from functools import cache
from typing import Any

# A catalog row, as taskedit_addable lists them: action_key, name, category_name and so on.
Row = dict[str, Any]

CARDS_FILE = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "json", "action_cards.json"),
)

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


def rank(description: str, rows: list[Row], limit: int) -> list[Row]:
    """The rows (catalog rows, as taskedit_addable lists them) that best match a description, best first.

    Only rows that share at least one term with the description are returned, so a description
    with nothing in it that any action is about gets none rather than the first few alphabetically.
    Ties go to the shorter name and then the name, so the order is the same on every run.
    """
    wanted = set(terms(description))
    if not wanted or not rows:
        return []
    documents = [_document(row) for row in rows]
    lengths = [sum(document.values()) for document in documents]
    average = (sum(lengths) / len(lengths)) or 1.0
    count = len(rows)
    totals: defaultdict[int, float] = defaultdict(float)
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
    best = sorted(totals, key=lambda number: (-totals[number], len(rows[number]["name"]), rows[number]["name"]))
    return [rows[number] for number in best[:limit]]
