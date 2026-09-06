#! /usr/bin/env python3
"""Serialize actionc.action_codes to a golden snapshot, and diff a table against it.

This is the gate for the task_all_actions.json migration.  actionc.py is currently a
literal 743-entry table; it is to become a loader that rebuilds the same table from
task_all_actions.json (418 Task codes) plus an overlay carrying what Tasker does not
publish (113 Event, 61 State, 132 unpublished/plugin Task, 19 Scene element entries)
and the two fields the JSON has no equivalent for -- arg_eval and redirect.

The snapshot is taken from the literal table BEFORE that work starts.  Afterwards the
same comparison proves the loader reproduces it exactly, so no downstream module can
behave differently.  Nothing here knows about the migration: it compares whatever
actionc.action_codes currently is against the committed snapshot, which makes it a
drift guard before the migration and an equivalence proof after it.

Regenerate deliberately, never as a way to make a failing test pass:

    python tests/action_codes_snapshot.py --update

Every field is serialized verbatim, including values that look wrong.  actionc.py has
79 arg_eval strings that disagree with the JSON's own argument name (381t labels its
'Output Variables' argument 'Contact=', 464t has 'Action' and 'Calendar' swapped) and
one redirect -- SceneElement -> "Map" -- that names no key in the table.  Those are
pre-existing and load-bearing; correcting them is a separate decision from moving the
data, and a snapshot that quietly normalized them would hide the change.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

SNAPSHOT_PATH = os.path.join(os.path.dirname(__file__), "data", "action_codes_snapshot.json")

# Cap on how much a failing comparison prints.  A loader that goes wrong tends to go
# wrong for every entry at once, and 743 reported differences bury the useful first one.
MAX_REPORTED = 25

# Field order used when serializing, so a hand-edited snapshot and a generated one
# compare equal.  ArgumentCode is written as a positional list rather than an object:
# it has five fields, always in this order, and the flat form keeps one action code on
# one line of the snapshot so `git diff` shows precisely which codes moved.
_ARG_FIELDS = ("arg_id", "arg_required", "arg_name", "arg_type", "arg_eval")


def serialize_entry(entry: Any) -> dict:
    """One ActionCode as JSON-safe data.

    Args:
        entry (ActionCode): a value out of the action_codes table.
    Returns:
        dict: the entry's fields, with args as a list of five-element lists.
    """
    return {
        "redirect": entry.redirect,
        "name": entry.name,
        "category": entry.category,
        "canfail": entry.canfail,
        "args": [[getattr(arg, field) for field in _ARG_FIELDS] for arg in entry.args],
    }


def serialize_table(table: dict) -> list:
    """The whole action_codes table as an ordered list of [key, entry] pairs.

    A list rather than a dict so that key order is compared as data.  Several callers
    build user-facing pickers by iterating the table and sorting only on the action's
    display name -- 29 names are shared by more than one code -- so iteration order
    decides how those ties break, and a reordered table is a real change.

    Args:
        table (dict): action_codes, or anything shaped like it.
    Returns:
        list: [[key, {...}], ...] in the table's own iteration order.
    """
    return [[key, serialize_entry(entry)] for key, entry in table.items()]


def dumps(pairs: list) -> str:
    """Serialized table as text, one action code per line.

    json.dump's own indentation would spread a single action code over dozens of lines
    and make the diff of a one-field change unreadable.

    Args:
        pairs (list): output of serialize_table.
    Returns:
        str: the snapshot file's contents.
    """
    lines = [json.dumps(pair, ensure_ascii=False, sort_keys=True) for pair in pairs]
    return "[\n" + ",\n".join(lines) + "\n]\n"


def read_snapshot(path: str = SNAPSHOT_PATH) -> list:
    """The committed snapshot.

    Args:
        path (str): snapshot file to read.
    Returns:
        list: [[key, {...}], ...] as written by dumps.
    """
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def write_snapshot(pairs: list, path: str = SNAPSHOT_PATH) -> None:
    """Overwrite the snapshot.

    Args:
        pairs (list): output of serialize_table.
        path (str): snapshot file to write.
    Returns:
        None
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        file.write(dumps(pairs))


def _diff_entry(key: str, expected: dict, actual: dict) -> list[str]:
    """Field-level differences for one action code.

    Args:
        key (str): the action_codes key being compared.
        expected (dict): the snapshot's entry.
        actual (dict): the current table's entry.
    Returns:
        list[str]: one line per differing field, empty when the entries match.
    """
    report = [
        f"  {key}.{field}: expected {expected[field]!r}, got {actual[field]!r}"
        for field in ("redirect", "name", "category", "canfail")
        if expected[field] != actual[field]
    ]

    old_args, new_args = expected["args"], actual["args"]
    if len(old_args) != len(new_args):
        report.append(f"  {key}.args: expected {len(old_args)} argument(s), got {len(new_args)}")
        return report

    for old_arg, new_arg in zip(old_args, new_args, strict=True):
        for field, old_value, new_value in zip(_ARG_FIELDS, old_arg, new_arg, strict=True):
            if old_value != new_value:
                report.append(
                    f"  {key} arg {old_arg[0]}.{field}: expected {old_value!r}, got {new_value!r}",
                )
    return report


def diff_tables(expected: list, actual: list) -> list[str]:
    """Everything that differs between a snapshot and a current table, worst first.

    Ordered so the first lines answer the question that matters most in this migration:
    did any action code go missing.  Only once the key sets agree does ordering, and
    then field content, get reported -- a lost code makes those meaningless anyway.

    Args:
        expected (list): the committed snapshot.
        actual (list): serialize_table of the current action_codes.
    Returns:
        list[str]: human-readable differences, empty when the tables are identical.
    """
    expected_keys = [pair[0] for pair in expected]
    actual_keys = [pair[0] for pair in actual]
    lost = [key for key in expected_keys if key not in set(actual_keys)]
    gained = [key for key in actual_keys if key not in set(expected_keys)]

    report = []
    if lost:
        report.append(f"{len(lost)} action code(s) LOST: {', '.join(lost[:MAX_REPORTED])}")
    if gained:
        report.append(f"{len(gained)} action code(s) ADDED: {', '.join(gained[:MAX_REPORTED])}")
    if lost or gained:
        return report

    if expected_keys != actual_keys:
        # The key sets already agree, so this is either a reordering or a duplicated key.
        moved = [i for i, (old, new) in enumerate(zip(expected_keys, actual_keys, strict=False)) if old != new]
        if moved:
            first = moved[0]
            report.append(
                f"key ORDER differs from position {first}: expected {expected_keys[first]!r}, "
                f"got {actual_keys[first]!r}.  Sort the merged table -- sorted(json keys + overlay keys) "
                f"reproduces the literal table's order exactly.",
            )
        else:
            report.append(
                f"table has {len(actual_keys)} keys against the snapshot's {len(expected_keys)} "
                f"with the same key set -- a key is duplicated.",
            )

    actual_by_key = dict(actual)
    for key, old_entry in expected:
        report.extend(_diff_entry(key, old_entry, actual_by_key[key]))
        if len(report) > MAX_REPORTED:
            report.append(f"... and more (output capped at {MAX_REPORTED} differences)")
            break
    return report


def _main() -> int:
    """Regenerate the snapshot, reporting what it changes first.

    Args:
        None
    Returns:
        int: process exit status.
    """
    if "--update" not in sys.argv:
        print(__doc__)
        print("Nothing done.  Pass --update to rewrite the snapshot.")
        return 1

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from maptasker.src.actionc import action_codes  # noqa: PLC0415

    current = serialize_table(action_codes)
    if os.path.exists(SNAPSHOT_PATH):
        changes = diff_tables(read_snapshot(), current)
        if not changes:
            print(f"Snapshot already matches the current table ({len(current)} action codes).")
            return 0
        print("This rewrite changes:")
        for line in changes:
            print(f"  {line}")
        print("")

    write_snapshot(current)
    total_args = sum(len(entry["args"]) for _, entry in current)
    print(f"Wrote {SNAPSHOT_PATH}: {len(current)} action codes, {total_args} arguments.")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
