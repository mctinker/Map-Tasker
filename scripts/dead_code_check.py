"""Fail on dead code: anything vulture finds that nothing in maptasker/src refers to.

vulture reads the source for functions, methods, classes, attributes and constants nothing
refers to.  It is a guess -- a name used only by a framework, a string or a test looks as dead as
one nobody wants -- so a finding is dealt with one of two ways:

  * Dead:  deleted.
  * Called by something vulture cannot see (an HTMLParser's handle_starttag, a page registered by
    a decorator, a widget looked up by name from a table of strings), or kept on purpose: named in
    ``ignore_names`` or ``ignore_decorators`` under [tool.vulture] in pyproject.toml, with the reason
    beside it, so the reviewer sees it.

There is no list of allowed findings.  The one there used to be held what could not be sorted into
either, and a list like that only grows.

    uv run python scripts/dead_code_check.py     what CI runs
    uv run vulture                               the same findings, as vulture prints them
"""

from __future__ import annotations

import sys
from pathlib import Path

from vulture import Vulture
from vulture.config import make_config

ROOT = Path(__file__).resolve().parent.parent


def find_dead_code() -> list[tuple[str, int, str]]:
    """Return vulture's findings as (file, line, what was found), as configured in pyproject.toml."""
    with (ROOT / "pyproject.toml").open("rb") as pyproject:
        config = make_config([], pyproject)
    finder = Vulture(ignore_names=config["ignore_names"], ignore_decorators=config["ignore_decorators"])
    finder.scavenge([str(ROOT / path) for path in config["paths"]], exclude=config["exclude"])
    return sorted(
        (Path(item.filename).resolve().relative_to(ROOT).as_posix(), item.first_lineno, item.message)
        for item in finder.get_unused_code(min_confidence=config["min_confidence"])
    )


def main() -> int:
    """Print every finding; return the exit status."""
    found = find_dead_code()
    for path, line, message in found:
        print(f"{path}:{line}: {message}")
    if found:
        print(
            f"\n{len(found)} dead-code finding(s). Delete what is unused. If something calls it that vulture "
            "cannot see, or it is meant to stay, name it under ignore_names (or its decorator under "
            "ignore_decorators) in [tool.vulture] in pyproject.toml, with the reason.",
        )
        return 1
    print("dead code check: nothing unused.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
