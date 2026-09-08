#! /usr/bin/env python3
"""actionc.action_codes equivalence gate for the task_all_actions.json migration.

actionc.py is a literal 743-entry table today and is to become a loader that rebuilds
that table from maptasker/assets/json/task_all_actions.json plus a small overlay.  The
JSON supplies 418 Task codes; the overlay has to supply the 325 entries Tasker does not
publish (113 Event, 61 State, 132 unpublished/plugin Task, 19 Scene element) together
with the two fields the JSON has no equivalent for at all -- arg_eval and redirect.

These tests compare the live table against tests/data/action_codes_snapshot.json.  The
snapshot was first taken from the literal table, which is how the loader was proved to
reproduce it exactly; it was regenerated once since, for the Phase B deletion below, and
otherwise a difference means something drifted.

The last test is a different kind of check.  Rather than comparing the table to itself,
it verifies the claim the migration rests on: that task_all_actions.json really does
carry, exactly, the structure of the 418 codes it covers.  It is the test that fails
when a new Tasker release renames an argument -- which is when the overlay needs an
entry, and the one failure mode a self-comparison cannot see.

Regenerate the snapshot only on purpose, and never to make a failure go away:

    python tests/action_codes_snapshot.py --update
"""

from __future__ import annotations

import json
import os

import pytest
from maptasker.src.actionc import action_codes

from tests.action_codes_snapshot import (
    diff_tables,
    read_snapshot,
    serialize_table,
)

# Measured from the literal table.  Hard-coded rather than derived so that a snapshot
# regenerated against a damaged table is caught here instead of silently becoming the
# new baseline.
EXPECTED_CODES = 757
EXPECTED_ARGS = 1704

# The 339 entries that task_all_actions.json cannot supply, by kind.  Tasker publishes
# no plugin, so every plugin action is here: the nine AM* and four HA* ones were added
# from backups, and like the other 128 they carry no arguments of their own and borrow
# the canonical plugin argument list by redirect.  2087e was added by hand as well --
# Tasker publishes that Event code but nothing uses it, so it has no arguments either.
EXPECTED_OVERLAY = {"event": 114, "state": 61, "task": 145, "scene": 19}

TASK_ACTIONS_JSON = os.path.join(
    os.path.dirname(__file__),
    "..",
    "maptasker",
    "assets",
    "json",
    "task_all_actions.json",
)


@pytest.fixture(scope="module")
def snapshot() -> list:
    """The committed golden table."""
    return read_snapshot()


@pytest.fixture(scope="module")
def current() -> list:
    """The live action_codes table, serialized the same way."""
    return serialize_table(action_codes)


def _kind(key: str) -> str:
    """Which of the four groups an action_codes key belongs to."""
    if not (key[:-1].isdigit() and key[-1] in "tes"):
        return "scene"
    return {"e": "event", "s": "state", "t": "task"}[key[-1]]


def test_no_action_codes_are_lost(snapshot: list, current: list) -> None:
    """Every key in the snapshot is still in the table, and none appeared.

    The migration's cardinal failure: the JSON covers 418 of 743 entries, so anything
    the overlay forgets simply stops existing, and most consumers treat a missing key
    as 'not yet mapped' rather than raising.
    """
    before = {pair[0] for pair in snapshot}
    after = {pair[0] for pair in current}
    lost = sorted(before - after)
    gained = sorted(after - before)
    assert not lost, f"{len(lost)} action code(s) lost: {', '.join(lost[:25])}"
    assert not gained, f"{len(gained)} unexpected action code(s) added: {', '.join(gained[:25])}"


def test_overlay_population_is_unchanged(current: list) -> None:
    """The 325 entries task_all_actions.json cannot supply are all present.

    Stated per kind so a loader that drops, say, every State code fails with the reason
    rather than with a count that has to be worked back to a cause.
    """
    with open(TASK_ACTIONS_JSON, encoding="utf-8") as file:
        published = {f"{entry['code']}t" for entry in json.load(file)}
    counts = {"event": 0, "state": 0, "task": 0, "scene": 0}
    for key, _ in current:
        if key not in published:
            counts[_kind(key)] += 1
    assert counts == EXPECTED_OVERLAY


def test_key_order_is_preserved(snapshot: list, current: list) -> None:
    """The table iterates in the same order it always did.

    profedit and mapswap build their pickers by walking action_codes and sorting only
    on the action's display name, and 29 names are shared by more than one code, so
    iteration order decides how those ties break and reaches the screen.  A loader that
    appends the overlay after the JSON codes reorders the table; sorting the merged
    keys reproduces the literal order exactly.
    """
    assert [pair[0] for pair in snapshot] == [pair[0] for pair in current]


def test_every_entry_is_identical(snapshot: list, current: list) -> None:
    """Field-for-field equality across all 743 entries and 1704 arguments."""
    report = diff_tables(snapshot, current)
    assert not report, "action_codes differs from the snapshot:\n" + "\n".join(report)


def test_snapshot_is_whole(snapshot: list) -> None:
    """The snapshot itself is the size it should be.

    Guards the case where the gate passes because both sides are equally truncated.
    """
    assert len(snapshot) == EXPECTED_CODES
    assert sum(len(entry["args"]) for _, entry in snapshot) == EXPECTED_ARGS


def test_arg_eval_is_carried_for_every_argument(snapshot: list, current: list) -> None:
    """arg_eval matches the snapshot on every argument, list-form values included.

    task_all_actions.json has no arg_eval equivalent, so every surviving value comes
    from the overlay.  The 419 list-form ones are the load-bearing kind: they are
    lookups into actiont.lookup_values, and losing one turns a named setting back into
    a bare integer.  Of the string ones, only two kinds are read at all -- see
    test_no_unread_arg_eval_values, which is what keeps the rest from creeping back.
    """
    expected = {(key, arg[0]): arg[4] for key, entry in snapshot for arg in entry["args"]}
    actual = {(key, arg[0]): arg[4] for key, entry in current for arg in entry["args"]}
    assert actual == expected


def test_redirects_are_carried(snapshot: list, current: list) -> None:
    """All 133 redirects survive, targets included.

    Redirect is the other field task_all_actions.json has no equivalent for.  Every one
    of the 133 lives wholly inside the overlay -- none points into JSON-covered
    territory -- so they stand or fall with the overlay alone.
    """
    expected = {key: entry["redirect"] for key, entry in snapshot if entry["redirect"]}
    actual = {key: entry["redirect"] for key, entry in current if entry["redirect"]}
    assert actual == expected


def test_scene_element_dangling_redirect_is_left_alone() -> None:
    """SceneElement still redirects to 'Map', which is not a key in the table.

    This is the one redirect that does not resolve, and it is deliberate: 'Map' is a
    display label for Tasker's Map element, whose xml tag is SceneElement, and the
    entry carries a full set of arguments of its own.  sceneedit._legacy_effective_args
    documents this and takes the entry at its word when the target is missing.

    Called out by name because a loader that validates redirects, or drops the ones it
    cannot resolve, will 'fix' this and break the Map scene element.
    """
    assert action_codes["SceneElement"].redirect == "Map"
    assert "Map" not in action_codes
    assert action_codes["SceneElement"].args, "SceneElement must keep its own arguments"


def test_task_all_actions_json_still_matches_the_table(snapshot: list) -> None:
    """task_all_actions.json agrees exactly with the 418 codes it covers.

    The premise of the migration, checked against the source rather than against the
    table: name, category and canfail per action, and id, name, type and mandatory-ness
    per argument.  All four agreed exactly when the snapshot was taken.

    A failure here does not mean the loader is broken -- it means a newer Tasker release
    changed something under a code the overlay is keyed to, and the overlay's arg_eval
    entries for that code are now attached to an argument that may have moved.
    """
    with open(TASK_ACTIONS_JSON, encoding="utf-8") as file:
        published = {f"{entry['code']}t": entry for entry in json.load(file)}

    by_key = dict(snapshot)
    report = []
    for key, source in published.items():
        entry = by_key.get(key)
        if entry is None:
            report.append(f"{key} ({source['name']}) is in the JSON but not in the table")
            continue
        if entry["name"] != source["name"]:
            report.append(f"{key}.name: table {entry['name']!r}, JSON {source['name']!r}")
        if entry["category"] != str(source["categoryCode"]):
            report.append(f"{key}.category: table {entry['category']!r}, JSON {source['categoryCode']!r}")
        if entry["canfail"] != str(source.get("canFail", False)):
            report.append(f"{key}.canfail: table {entry['canfail']!r}, JSON {source.get('canFail', False)!r}")

        source_args = {str(arg["id"]): arg for arg in source["args"]}
        if len(entry["args"]) != len(source_args):
            report.append(f"{key}.args: table has {len(entry['args'])}, JSON has {len(source_args)}")
            continue
        for arg_id, _required, arg_name, arg_type, _eval in entry["args"]:
            source_arg = source_args.get(arg_id)
            if source_arg is None:
                report.append(f"{key} arg {arg_id} is not in the JSON")
                continue
            if arg_name != (source_arg.get("name") or ""):
                report.append(f"{key} arg {arg_id}.name: table {arg_name!r}, JSON {source_arg.get('name')!r}")
            if arg_type != str(source_arg["type"]):
                report.append(f"{key} arg {arg_id}.type: table {arg_type!r}, JSON {source_arg['type']!r}")
            if _required != bool(source_arg["isMandatory"]):
                report.append(f"{key} arg {arg_id}.required: table {_required!r}, JSON {source_arg['isMandatory']!r}")

    assert not report, (
        f"task_all_actions.json no longer matches the table for {len(report)} field(s) "
        "-- the overlay needs an entry for these:\n" + "\n".join(report[:25])
    )


def test_no_unread_arg_eval_values() -> None:
    """No argument stores a string arg_eval that its arg_name shadows.

    actargs.action_args picks arg_name over a string arg_eval whenever arg_name is set,
    and taskedit._display_arg_name does the same, so such a string cannot reach any
    output -- it is data nothing can read.  Phase B deleted 957 of them, which changed
    not one line across the 380,954 rendered from the backups in XML/.

    Two kinds are genuinely read and must stay:

      - a Boolean argument (arg_type "3"), because actargs' Boolean case re-reads the
        raw arg[4] and so overrides the arg_name preference for exactly these;
      - an argument with no arg_name at all, where arg_eval carries the label itself.

    A failure here means unread values have come back.  They cost nothing at runtime but
    are actively misleading to read: 77 of the deleted ones disagreed with the argument's
    real name, which made them look like display bugs that could never actually fire.
    """
    unread = [
        f"{key} arg {arg.arg_id} ({arg.arg_name!r} shadows {arg.arg_eval!r})"
        for key, entry in action_codes.items()
        for arg in entry.args
        if isinstance(arg.arg_eval, str) and arg.arg_eval and arg.arg_name and arg.arg_type != "3"
    ]
    assert not unread, (
        f"{len(unread)} argument(s) carry a string arg_eval that arg_name shadows, so nothing "
        "reads them:\n" + "\n".join(unread[:25])
    )
