"""MapTasker Add-an-Action search unit tests

The Edit/Add Task dialogs' "Search actions" box filters Tasker's whole action catalogue by
substring.  Sorted by name, that buried the answer: typing "if" put 'ADB Wifi', 'Android
Notifier' and eleven 'AutoNotification ...' entries above 'If' and 'End If', because every
one of them contains the letters i-f somewhere.  search_addable_actions now ranks a whole
name, then a whole word, then a match anywhere, and sorts alphabetically inside each rank.

Two kinds of test here.  The ranking RULES are checked against a small made-up catalogue,
so they cannot be broken by Tasker adding an action in some later release; the behaviour
the change was actually asked for is checked against the real catalogue, because that is
the thing a user types "if" into.
"""

from __future__ import annotations

import pytest
from maptasker.src import taskedit

# A catalogue built to separate the three ranks on one query.  "set" is the whole of one
# name, a whole word in three others, and buried inside two more.
_FAKE_ACTIONS = [
    {"name": "Asset Manager", "category_name": "Files"},
    {"name": "Offset Time", "category_name": "Variables"},
    {"name": "Set", "category_name": "Variables"},
    {"name": "Set Clipboard", "category_name": "Misc"},
    {"name": "Set Widget Label", "category_name": "Misc"},
    {"name": "Variable Set", "category_name": "Variables"},
]


@pytest.fixture
def _fake_catalogue(monkeypatch: pytest.MonkeyPatch) -> None:
    """Search a small alphabetical catalogue instead of Tasker's real one.

    Alphabetical because that is the order list_addable_actions hands rows over in, and
    half of what these tests check is that the order SURVIVES inside each rank.
    """
    monkeypatch.setattr(taskedit, "list_addable_actions", lambda: list(_FAKE_ACTIONS))


def _names(query: str = "", category_name: str = "All") -> list[str]:
    """The search results as the list of names it puts on screen, in order."""
    return [row["name"] for row in taskedit.search_addable_actions(query, category_name)]


# ##################################################################################
# The ranking rules.
# ##################################################################################
@pytest.mark.usefixtures("_fake_catalogue")
def test_the_three_ranks_come_out_in_order() -> None:
    """Whole name first, then whole word, then a match anywhere -- alphabetical inside each."""
    assert _names("set") == [
        "Set",  # the whole name
        "Set Clipboard",  # a whole word, and these three are alphabetical
        "Set Widget Label",
        "Variable Set",
        "Asset Manager",  # buried inside a word, and these two are alphabetical
        "Offset Time",
    ]


@pytest.mark.usefixtures("_fake_catalogue")
def test_ranking_changes_the_order_and_not_the_matches() -> None:
    """Every name that matched before still matches -- this reorders, it does not filter.

    Worth its own test: a ranking written as a filter would quietly drop the substring
    matches, which are still the right answer when they are all there is.
    """
    assert sorted(_names("set")) == sorted(
        [row["name"] for row in _FAKE_ACTIONS if "set" in row["name"].lower()],
    )


@pytest.mark.usefixtures("_fake_catalogue")
def test_no_query_stays_alphabetical() -> None:
    """With nothing to rank against, the catalogue's own order is what browsing wants."""
    assert _names() == [row["name"] for row in _FAKE_ACTIONS]


@pytest.mark.usefixtures("_fake_catalogue")
def test_the_category_filter_still_applies() -> None:
    """Ranking and filtering compose: the rank orders what the category left."""
    assert _names("set", "Variables") == ["Set", "Variable Set", "Offset Time"]


@pytest.mark.usefixtures("_fake_catalogue")
def test_a_query_matching_nothing_finds_nothing() -> None:
    """The ranking has no opinion about an empty result."""
    assert _names("nothing here") == []


# ##################################################################################
# The real catalogue -- the case this was asked for.
# ##################################################################################
def test_if_and_end_if_come_first() -> None:
    """Typing "if" offers 'If' and 'End If' before the forty names that merely contain it.

    The example the change was requested with, checked against the catalogue the user is
    actually typing into rather than against a fixture.
    """
    names = _names("if")

    assert names[:2] == ["If", "End If"]
    # And the whole point: what used to be at the top is now below them.
    assert names.index("ADB Wifi") > 1


def test_a_query_holding_punctuation_still_matches() -> None:
    """'(hotspot)' finds 'WiFi Tether (Hotspot)'.

    The trap the word test avoids by not using \\b: \\b before "(" asks for a word
    character in front of it, which a name with a space there has not got, so the query
    would rank as no match at all -- or, with the regex written differently, raise.
    """
    assert _names("(hotspot)") == ["WiFi Tether (Hotspot)"]
