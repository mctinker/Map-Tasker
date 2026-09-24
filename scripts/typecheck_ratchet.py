"""Ratchet pyright's error count so it can only go down.

ruff's ANN rules make every function carry type annotations, but nothing checked that the
annotations are right.  pyright does, in basic mode ([tool.pyright] in pyproject.toml) --
and the code already had a couple of thousand errors when it was switched on, so it is
enforced the same way the noqa comments are: the errors that were there are counted, file
by file and rule by rule, in pyright_baseline.json beside this script, and only new ones fail.

  * A file whose count for a rule went up fails.  Fix the new error.
  * A count that went down also fails, until the baseline is lowered to match.  Otherwise
    the fix would leave room for a new error of the same kind in the same file.
    ``--update`` lowers it.

    uv run python scripts/typecheck_ratchet.py            check (what CI runs)
    uv run python scripts/typecheck_ratchet.py --update   lower the baseline after a fix

Counted per file and rule rather than per line, so an edit that moves code about does not
look like a new error.  The cost is that a file's new error cannot be told from its old
ones of the same rule: a rise lists all of them, and the new one is among them.

``--update`` never raises a count.  ``--reset`` rewrites the baseline to exactly what pyright
reports now, rises included -- for after pyright is upgraded or its settings change, when
the counts move for reasons that are not the code's.  The whole change then shows up in review.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import TypeAlias

import pyright

ROOT = Path(__file__).resolve().parent.parent
BASELINE = Path(__file__).with_name("pyright_baseline.json")
UPDATE_HINT = "uv run python scripts/typecheck_ratchet.py --update"

# pyright's own name for a diagnostic with no rule attached (a syntax error, say).
NO_RULE = "(no rule)"
COUNTED_SEVERITIES = {"error", "warning"}

Key: TypeAlias = tuple[str, str]  # (file, relative to the repository root; rule)


def run_pyright() -> list[dict]:
    """Run pyright over the files [tool.pyright] names and return its diagnostics."""
    result = pyright.run("--outputjson", cwd=ROOT, capture_output=True, text=True, check=False)
    # 0 is clean and 1 is "errors found"; anything else means pyright itself did not run.
    if result.returncode not in (0, 1):
        sys.exit(f"pyright failed (exit {result.returncode}):\n{result.stderr or result.stdout}")
    return json.loads(result.stdout)["generalDiagnostics"]


def tally(diagnostics: list[dict]) -> tuple[Counter[Key], defaultdict[Key, list[str]]]:
    """Count the diagnostics per (file, rule), and keep each one's line and message for reporting."""
    counts: Counter[Key] = Counter()
    where: defaultdict[Key, list[str]] = defaultdict(list)
    for diagnostic in diagnostics:
        if diagnostic["severity"] not in COUNTED_SEVERITIES:
            continue
        path = Path(diagnostic["file"]).resolve().relative_to(ROOT).as_posix()
        key = (path, diagnostic.get("rule", NO_RULE))
        counts[key] += 1
        message = diagnostic["message"].splitlines()[0]
        where[key].append(f"  {path}:{diagnostic['range']['start']['line'] + 1}  {message}")
    return counts, where


def load_baseline() -> Counter[Key]:
    """Return the committed allowance, per (file, rule)."""
    stored = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {}
    return Counter({(path, rule): count for path, rules in stored.items() for rule, count in rules.items()})


def save_baseline(counts: Counter[Key]) -> None:
    """Write the counts grouped by file, sorted so a change diffs as one line per file and rule."""
    by_file: defaultdict[str, dict[str, int]] = defaultdict(dict)
    for (path, rule), count in sorted(counts.items()):
        if count:
            by_file[path][rule] = count
    BASELINE.write_text(json.dumps(by_file, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    """Compare pyright's current counts with the baseline; return the exit status."""
    parser = argparse.ArgumentParser(description="Ratchet pyright's error count so it can only go down.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--update", action="store_true", help="lower the baseline to the current counts")
    mode.add_argument("--reset", action="store_true", help="rewrite the baseline to the current counts, rises included")
    options = parser.parse_args()

    counts, where = tally(run_pyright())
    baseline = load_baseline()

    if options.reset:
        save_baseline(counts)
        print(f"{BASELINE.name}: reset to {counts.total()} errors (was {baseline.total()}).")
        return 0

    risen = sorted(key for key in counts if counts[key] > baseline[key])
    fallen = sorted(key for key in baseline if counts[key] < baseline[key])

    for key in risen:
        path, rule = key
        print(f"{path}  {rule}: {counts[key]} errors, {baseline[key]} allowed (+{counts[key] - baseline[key]}).")
        print("\n".join(where[key]))
    if risen:
        print("\nNew type errors. The new ones are among those listed; fix them rather than raising the baseline.")
        return 1

    if options.update:
        if fallen:
            save_baseline(counts)
        print(f"{BASELINE.name}: {counts.total()} errors ({baseline.total() - counts.total()} fewer).")
        return 0

    for path, rule in fallen:
        print(f"{path}  {rule}: {counts[path, rule]} errors, {baseline[path, rule]} in the baseline.")
    if fallen:
        print(f"\nFewer type errors than the baseline allows -- lock that in with:\n  {UPDATE_HINT}")
        return 1

    print(f"typecheck ratchet: {counts.total()} errors, none new.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
