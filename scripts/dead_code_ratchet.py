"""Ratchet the dead code vulture finds so it can only go down.

vulture reads the source for functions, methods, classes, attributes and constants nothing
refers to.  It is a guess -- a name used only by a framework, a string or a test looks as dead as
one nobody wants -- so the findings are sorted three ways:

  * Dead:  deleted.
  * Called by something vulture cannot see (an HTMLParser's handle_starttag, a page registered by
    a decorator, a method looked up by name from a string): named in ``ignore_names`` or
    ``ignore_decorators`` under [tool.vulture] in pyproject.toml, with the reason beside it.
  * The rest -- widget references kept on the window and never read back, fields only a test reads,
    a sketch of a feature not yet wired in: listed in dead_code_baseline.json beside this script.

This script compares what vulture finds now with that list.

  * A finding that is not in the list fails.  Delete the dead code; if something calls it that
    vulture cannot see, add its name to ``ignore_names``; if it really is meant to stay, add it to
    the baseline by hand so the reviewer sees it.
  * A finding that is in the list but is gone also fails, until the baseline is lowered to match.
    Otherwise the cleanup would leave room for the same amount of new dead code.  ``--update``
    lowers it.

The baseline is keyed by file and by what was found, never by line number, so editing a file
does not disturb it.

    uv run python scripts/dead_code_ratchet.py            check (what CI runs)
    uv run python scripts/dead_code_ratchet.py --update   lower the baseline after a cleanup
    uv run vulture                                        the raw findings, with line numbers

``--update`` never adds an entry: it only removes the ones that are gone.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from vulture import Vulture
from vulture.config import make_config

ROOT = Path(__file__).resolve().parent.parent
BASELINE = Path(__file__).with_name("dead_code_baseline.json")
UPDATE_HINT = "uv run python scripts/dead_code_ratchet.py --update"

# {file: {what was found: how many times}}
Findings = dict[str, Counter[str]]


def find_dead_code() -> tuple[Findings, dict[tuple[str, str], list[int]]]:
    """Return vulture's findings by file, and the lines each was found on, as configured in pyproject.toml."""
    with (ROOT / "pyproject.toml").open("rb") as pyproject:
        config = make_config([], pyproject)
    finder = Vulture(ignore_names=config["ignore_names"], ignore_decorators=config["ignore_decorators"])
    finder.scavenge([str(ROOT / path) for path in config["paths"]], exclude=config["exclude"])

    found: Findings = {}
    lines: dict[tuple[str, str], list[int]] = {}
    for item in finder.get_unused_code(min_confidence=config["min_confidence"]):
        path = Path(item.filename).resolve().relative_to(ROOT).as_posix()
        # message is e.g. "unused function 'popout_view'": the kind of thing and its name.
        found.setdefault(path, Counter())[item.message] += 1
        lines.setdefault((path, item.message), []).append(item.first_lineno)
    return found, lines


def load_baseline() -> Findings:
    """Return the committed allowance."""
    raw = json.loads(BASELINE.read_text(encoding="utf-8"))
    return {path: Counter(entries) for path, entries in raw.items()}


def save_baseline(allowed: Findings) -> None:
    """Write the allowance sorted, so a change diffs as one line per finding."""
    ordered = {
        path: {message: allowed[path][message] for message in sorted(allowed[path])}
        for path in sorted(allowed)
        if allowed[path]
    }
    BASELINE.write_text(json.dumps(ordered, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def compare(found: Findings, allowed: Findings) -> tuple[list[tuple[str, str, int]], list[tuple[str, str, int]]]:
    """Return (new, gone): findings above the allowance, and allowance above the findings, each with its excess."""
    new, gone = [], []
    for path in sorted(found.keys() | allowed.keys()):
        here, expected = found.get(path, Counter()), allowed.get(path, Counter())
        for message in sorted(here.keys() | expected.keys()):
            if here[message] > expected[message]:
                new.append((path, message, here[message] - expected[message]))
            elif here[message] < expected[message]:
                gone.append((path, message, expected[message] - here[message]))
    return new, gone


def lowered(found: Findings, allowed: Findings) -> Findings:
    """The allowance with everything that is gone taken out; nothing is ever added."""
    still_there = {
        path: {message: min(count, found.get(path, Counter())[message]) for message, count in entries.items()}
        for path, entries in allowed.items()
    }
    return {
        path: Counter({message: count for message, count in entries.items() if count})
        for path, entries in still_there.items()
    }


def main() -> int:
    """Compare the current findings with the baseline; return the exit status."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--update", action="store_true", help="lower the baseline to the current findings")
    options = parser.parse_args()

    found, lines = find_dead_code()
    allowed = load_baseline()
    new, gone = compare(found, allowed)
    total = sum(sum(entries.values()) for entries in found.values())
    allowance = sum(sum(entries.values()) for entries in allowed.values())

    for path, message, extra in new:
        where = ", ".join(str(line) for line in sorted(lines[path, message]))
        print(f"{path}:{where}: {message}" + (f" (+{extra})" if extra > 1 else ""))
    if new:
        print(
            f"\n{sum(extra for _, _, extra in new)} new dead-code finding(s). Delete what is unused. If something "
            "calls it that vulture cannot see, name it under ignore_names (or its decorator under "
            "ignore_decorators) in [tool.vulture], with the reason. If it really is meant to stay, add it to "
            f"{BASELINE.name} by hand so the reviewer sees it.",
        )
        return 1

    if options.update:
        if gone:
            save_baseline(lowered(found, allowed))
        print(f"{BASELINE.name}: {total} findings ({allowance - total} fewer).")
        return 0

    for path, message, missing in gone:
        print(f"{path}: {message} is gone" + (f" (x{missing})" if missing > 1 else ""))
    if gone:
        print(f"\nLess dead code than the baseline allows -- lock that in with:\n  {UPDATE_HINT}")
        return 1

    print(f"dead code ratchet: {total} known findings, none new.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
