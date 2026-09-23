"""Ratchet the inline ``# noqa`` count so it can only go down.

The per-file ignores in pyproject.toml are a ratchet: each rule is switched off only for a
file that already broke it, and new code anywhere else is fully linted.  An inline
``# noqa`` has no such limit -- any line in any file can silence any rule -- so the
suppressions piled up unnoticed.  This script counts them, rule by rule, across the same
files ruff lints, and compares the counts with noqa_baseline.json beside it.

  * A rule whose count went up fails.  Fix the new violation rather than silencing it.
  * A rule whose count went down also fails, until the baseline is lowered to match.
    Otherwise the cleanup would leave room for the same number of new suppressions.
    ``--update`` lowers it.

    uv run python scripts/noqa_ratchet.py            check (what CI runs)
    uv run python scripts/noqa_ratchet.py --update   lower the baseline after a cleanup

``--update`` never raises a count.  If a new suppression really is the right call, raise
that rule's number in noqa_baseline.json by hand, so the increase shows up in review.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tokenize
import tomllib
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = Path(__file__).with_name("noqa_baseline.json")
UPDATE_HINT = "uv run python scripts/noqa_ratchet.py --update"

# Keys for suppressions that name no rule.  PGH004 already rejects a bare inline noqa, but
# ruff does not police the file-wide 'ruff: noqa' comment, which silences every rule at once.
# (The examples in these comments leave out the leading hash: with it, ruff would read them
# as real directives, and so would this script.)
BLANKET = "(blanket)"
FILE_WIDE = "(file-wide)"

# The comment forms ruff honours: 'ruff: noqa' (or flake8's spelling) on a line of its own
# exempts the whole file; 'noqa' or 'noqa: CODE, CODE' anywhere in a comment exempts that
# line.  Codes stop at the first word that is not one, so the prose people write after them
# ('noqa: BLE001  Any failure here means ...') is not miscounted.
_FILE_DIRECTIVE = re.compile(r"#\s*(?:ruff|flake8)\s*:\s*noqa\b", re.IGNORECASE)
_LINE_DIRECTIVE = re.compile(r"#\s*noqa\b(\s*:)?", re.IGNORECASE)
_CODE = re.compile(r"[\s,]*([A-Z]+[0-9]+)(?![A-Za-z0-9])")


def linted_files() -> list[Path]:
    """Return the Python files ruff lints, per the include list in pyproject.toml."""
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    patterns = config["tool"]["ruff"]["include"]
    return sorted({path for pattern in patterns for path in ROOT.glob(pattern) if path.suffix == ".py"})


def suppressions(path: Path) -> list[tuple[int, str]]:
    """Return (line, rule) for every rule a noqa comment in this file silences."""
    found = []
    with tokenize.open(path) as source:
        for token in tokenize.generate_tokens(source.readline):
            if token.type != tokenize.COMMENT:
                continue
            line, text = token.start[0], token.string
            if _FILE_DIRECTIVE.match(text):
                found.append((line, FILE_WIDE))
                continue
            directive = _LINE_DIRECTIVE.search(text)
            if not directive:
                continue
            codes = []
            position = directive.end()
            # Without the colon ruff reads the comment as a blanket noqa, whatever follows.
            while directive.group(1) and (code := _CODE.match(text, position)):
                codes.append(code.group(1))
                position = code.end()
            found.extend((line, code) for code in codes or [BLANKET])
    return found


def load_baseline() -> Counter[str]:
    """Return the committed per-rule allowance."""
    return Counter(json.loads(BASELINE.read_text(encoding="utf-8")))


def save_baseline(counts: Counter[str]) -> None:
    """Write the per-rule counts, sorted so a change diffs as one line per rule."""
    ordered = {rule: counts[rule] for rule in sorted(counts) if counts[rule]}
    BASELINE.write_text(json.dumps(ordered, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    """Compare the current noqa counts with the baseline; return the exit status."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--update", action="store_true", help="lower the baseline to the current counts")
    options = parser.parse_args()

    where: defaultdict[str, list[str]] = defaultdict(list)
    for path in linted_files():
        for line, rule in suppressions(path):
            where[rule].append(f"{path.relative_to(ROOT).as_posix()}:{line}")
    counts = Counter({rule: len(places) for rule, places in where.items()})
    baseline = load_baseline()

    risen = sorted(rule for rule in counts if counts[rule] > baseline[rule])
    fallen = sorted(rule for rule in baseline if counts[rule] < baseline[rule])

    for rule in risen:
        print(f"{rule}: {counts[rule]} suppressed, {baseline[rule]} allowed (+{counts[rule] - baseline[rule]}).")
        print("\n".join(f"  {place}" for place in where[rule]))
    if risen:
        print(
            "\nNew inline noqa comments. Fix what they silence instead; if one really is the right call, "
            f"raise its count in {BASELINE.name} by hand so the reviewer sees it.",
        )
        return 1

    if options.update:
        if fallen:
            save_baseline(counts)
        print(f"{BASELINE.name}: {counts.total()} inline suppressions ({baseline.total() - counts.total()} fewer).")
        return 0

    for rule in fallen:
        print(f"{rule}: {counts[rule]} suppressed, {baseline[rule]} in the baseline.")
    if fallen:
        print(f"\nFewer inline noqa comments than the baseline allows -- lock that in with:\n  {UPDATE_HINT}")
        return 1

    print(f"noqa ratchet: {counts.total()} inline suppressions, none new.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
