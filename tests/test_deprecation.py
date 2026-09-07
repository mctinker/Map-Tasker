#! /usr/bin/env python3
"""The deprecation notice -- what it marks, and more importantly what it must not.

Two faults met here, and both were invisible until the notice itself was repaired,
because before that it never appeared for anything.

The first was in the key.  deprecate.py was keyed by the bare code number, and a number
means different things per type, so one entry marked all of them: the entry for Task
action 10 also marked State 10, 'Power'.  Likewise 'HDMI Plugged' and the 'Device Boot'
event.  Keys now carry the type suffix, as action_codes does.

The second was in the contents.  'Test', 'HTTP Post', 'HTTP Head' and 'HTTP Get' were
listed on the assumption that 'HTTP Request' had superseded them.  It had not -- Tasker
still publishes all four in live categories.  That assumption is why the rule below is
tested against Tasker's own published table rather than against a list written here:
task_all_actions.json is exported from a running Tasker and does not carry actions it
has removed, so it can answer the question that guesswork got wrong four times.
"""

from __future__ import annotations

import json
import os

from maptasker.src.actionc import action_codes
from maptasker.src.actione import check_for_deprecation
from maptasker.src.deprecate import depricated

MARKER = "<em> (Is Deprecated)</em> "

TASK_ACTIONS_JSON = os.path.join(
    os.path.dirname(__file__), "..", "maptasker", "assets", "json", "task_all_actions.json"
)

# Real, current Tasker features that the type-blind lookup marked by accident.  Named
# individually because the point is the specific claim: these are not deprecated,
# whatever the table says about 10, 12 or 411 under some other type.  The json cannot
# settle these -- it covers Task actions only, and these are States and an Event.
NOT_DEPRECATED = {"10s": "Power", "12s": "HDMI Plugged", "411e": "Device Boot"}


def _published_task_actions() -> dict:
    """Tasker's own current action table, keyed as action_codes keys it."""
    with open(TASK_ACTIONS_JSON, encoding="utf-8") as file:
        return {f"{entry['code']}t": entry for entry in json.load(file)}


def test_no_action_tasker_still_publishes_is_marked() -> None:
    """The rule: if Tasker publishes an action, it is not deprecated.

    task_all_actions.json is exported from a running Tasker and lists what that release
    offers, so an action in it is one you can still add.  This is the check that four
    hand-written entries failed -- 'Test' and the three HTTP actions, all published, all
    in live categories, all wrongly marked.
    """
    published = _published_task_actions()
    wrong = [
        f"{key} ({published[key]['name']!r}, category {published[key]['categoryCode']})"
        for key in depricated
        if key in published
    ]
    assert not wrong, "Tasker still publishes these, so they are not deprecated: " + ", ".join(wrong)


def test_current_features_are_not_marked() -> None:
    """Power, HDMI Plugged and Device Boot carry no deprecation notice."""
    for key, name in NOT_DEPRECATED.items():
        assert action_codes[key].name == name, f"{key} is no longer {name}; this test needs rereading"
        assert check_for_deprecation(key) == "", f"{name} ({key}) must not be marked deprecated"


def test_every_key_carries_a_type_suffix() -> None:
    """No bare numbers.  A key without a type is the first of the two bugs.

    A bare number matches nothing now, so such an entry would fail silently rather than
    mark the wrong thing -- better, but still not what was meant.
    """
    bad = [key for key in depricated if not (key[:-1].isdigit() and key[-1] in "tes")]
    assert not bad, f"deprecation keys must be a code plus 't', 'e' or 's': {bad}"


def test_a_code_outside_the_table_is_never_marked() -> None:
    """Listing a code action_codes does not hold marks nothing.

    Most of the table is actions Tasker removed outright, kept for configurations old
    enough to still contain one.  Until such a code is in action_codes there is no name
    to append the notice to, and get_action_code reports it as unmapped instead.
    """
    absent = [key for key in depricated if key not in action_codes]
    assert absent, "expected the table to list codes Tasker no longer publishes"
    for key in absent:
        assert check_for_deprecation(key) == ""


def test_the_marked_set_is_exactly_what_is_intended() -> None:
    """Everything the notice actually shows for, in one place.

    Fingerprint Gesture is the only one: Tasker publishes the Event code but the feature
    is gone, and it was added deliberately.  A new entry landing on a live feature of
    another type -- the original bug -- fails here without anyone having to predict
    which feature it would hit.
    """
    marked = {key: action_codes[key].name for key in action_codes if check_for_deprecation(key) == MARKER}
    assert marked == {"2087e": "Fingerprint Gesture"}
