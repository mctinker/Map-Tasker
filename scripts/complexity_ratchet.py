"""Ratchet function size and complexity so it can only go down.

ruff's limits in pyproject.toml ([tool.ruff.lint.pylint] and [tool.ruff.lint.mccabe]) are the
ceiling nothing may pass.  They are as low as the code allows, which is not as low as new code
should be: a function that is 50 statements long is hard to read and a 100-line one harder, but
rewriting every such function at once is not something a change can safely do.  So there are
two numbers per measure.  The ceiling is ruff's, and fails the build outright.  The target is
[tool.complexity-ratchet] in the same file, and is what every function is held to unless it is
listed in complexity_baseline.json beside this script.

The baseline is a list of the functions that were over a target when this was introduced, with
how far over each was, measure by measure -- as the noqa and type-check ratchets do for their
suppressions and errors:

  * A function that is over a target and not in the baseline fails.  Split it up.
  * A function whose measure went UP from its baseline fails, even though the target was
    already missed: the point is that nothing gets bigger.
  * A function whose measure went DOWN, or that is gone or back under the target, also fails,
    until the baseline is lowered to match.  Otherwise the cleanup would leave room for the
    same function to grow back.  ``--update`` lowers it.

    uv run python scripts/complexity_ratchet.py            check (what CI runs)
    uv run python scripts/complexity_ratchet.py --update   lower the baseline after a cleanup

Functions are identified by file and qualified name, not by line, so an edit that moves code
about does not look like a new offender.  Renaming or moving an offender does: the check names
both the new function and the baseline entry that went missing, and the baseline entry is
renamed by hand so the change is visible in review.

``--update`` never adds a function or raises a number.

The measures, and where they come from:

    PLR0915  statements     ruff's count, which is what [tool.ruff.lint.pylint] max-statements limits
    PLR0912  branches       ruff's count (max-branches)
    C901     complexity     McCabe, as ruff computes it (mccabe max-complexity)
    PLR0913  arguments      ruff's count (max-args)
    LINES    lines          first line to last of the definition, which ruff has no rule for
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import tomllib
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = Path(__file__).with_name("complexity_baseline.json")
UPDATE_HINT = "uv run python scripts/complexity_ratchet.py --update"

# pyproject.toml's [tool.complexity-ratchet] key, the ruff rule that measures it, and ruff's setting
# for it.  LINES is measured here, from the syntax tree, since ruff has no rule for it.
LINES = "LINES"
RUFF_MEASURES = {
    "statements": ("PLR0915", "lint.pylint.max-statements"),
    "branches": ("PLR0912", "lint.pylint.max-branches"),
    "complexity": ("C901", "lint.mccabe.max-complexity"),
    "arguments": ("PLR0913", "lint.pylint.max-args"),
}
# "(62 > 50)": ruff's message for every one of those rules.
_MEASURED = re.compile(r"\((\d+) > \d+\)")

Measures = dict[str, int]  # rule (or LINES) -> how far over the target, as a measured value


def targets() -> dict[str, int]:
    """The per-measure targets, from [tool.complexity-ratchet] in pyproject.toml."""
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    table = config["tool"]["complexity-ratchet"]
    wanted = {*RUFF_MEASURES, "lines"}
    if set(table) != wanted:
        sys.exit(f"[tool.complexity-ratchet] must set exactly {sorted(wanted)}, not {sorted(table)}.")
    return table


def linted_files() -> list[Path]:
    """The Python files ruff lints, per the include list in pyproject.toml."""
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    patterns = config["tool"]["ruff"]["include"]
    return sorted({path for pattern in patterns for path in ROOT.glob(pattern) if path.suffix == ".py"})


def ruff_findings(limits: dict[str, int]) -> list[dict]:
    """Every function ruff finds over the targets, as its JSON diagnostics.

    The project's own per-file ignores and every inline noqa are switched off: what matters here is
    what a function measures, not whether something has been excused from saying so.
    """
    settings = {
        "lint.select": json.dumps([rule for rule, _ in RUFF_MEASURES.values()]),
        "lint.per-file-ignores": "{}",
        **{setting: str(limits[name]) for name, (_rule, setting) in RUFF_MEASURES.items()},
    }
    command = [
        sys.executable,
        "-m",
        "ruff",
        "check",
        "--no-cache",
        "--ignore-noqa",
        "--output-format",
        "json",
        "--exit-zero",
    ]
    for key, value in settings.items():
        command += ["--config", f"{key} = {value}"]
    command += [str(path) for path in linted_files()]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.exit(f"ruff failed (exit {result.returncode}):\n{result.stderr or result.stdout}")
    return json.loads(result.stdout)


def functions_in(tree: ast.AST) -> dict[int, tuple[str, int]]:
    """Every function in a file: its first line -> (qualified name, length in lines).

    Methods are qualified by their class, and a function defined inside another by
    "outer.<locals>.inner", the way Python itself names them.  Two functions of one name in one
    scope (a handler written twice in a branch, say) are told apart by their order, which is
    stable under any edit that does not reorder them.
    """
    found: dict[int, tuple[str, int]] = {}
    seen: defaultdict[str, int] = defaultdict(int)

    def walk(node: ast.AST, scope: list[str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                name = ".".join([*scope, child.name])
                seen[name] += 1
                if seen[name] > 1:
                    name = f"{name}#{seen[name]}"
                found[child.lineno] = (name, (child.end_lineno or child.lineno) - child.lineno + 1)
                walk(child, [*scope, child.name, "<locals>"])
            elif isinstance(child, ast.ClassDef):
                walk(child, [*scope, child.name])
            else:
                walk(child, scope)

    walk(tree, [])
    return found


def measure(limits: dict[str, int]) -> dict[str, Measures]:
    """Every function over a target, as {"file::qualified name": {measure: value}}."""
    findings = ruff_findings(limits)
    by_file: defaultdict[str, list[dict]] = defaultdict(list)
    for finding in findings:
        by_file[Path(finding["filename"]).relative_to(ROOT).as_posix()].append(finding)

    over: dict[str, Measures] = defaultdict(dict)
    for path in linted_files():
        relative = path.relative_to(ROOT).as_posix()
        functions = functions_in(ast.parse(path.read_text(encoding="utf-8")))
        for finding in by_file.get(relative, []):
            line = finding["location"]["row"]
            if line not in functions:
                sys.exit(f"{relative}:{line}: ruff reported {finding['code']} on something that is not a function.")
            measured = _MEASURED.search(finding["message"])
            if measured is None:
                sys.exit(f"{relative}:{line}: cannot read the measure in ruff's message: {finding['message']}")
            value = int(measured.group(1))
            over[f"{relative}::{functions[line][0]}"][finding["code"]] = value
        for name, lines in functions.values():
            if lines > limits["lines"]:
                over[f"{relative}::{name}"][LINES] = lines
    return dict(over)


def load_baseline() -> dict[str, Measures]:
    """Return the committed list of what is over a target, and by how much."""
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def save_baseline(baseline: dict[str, Measures]) -> None:
    """Write the baseline, sorted so a change diffs as one line per measure."""
    ordered = {key: dict(sorted(baseline[key].items())) for key in sorted(baseline)}
    BASELINE.write_text(json.dumps(ordered, indent=2) + "\n", encoding="utf-8")


def compare(current: dict[str, Measures], baseline: dict[str, Measures]) -> tuple[list[str], list[str]]:
    """Return (problems that must be fixed, improvements that must be locked in)."""
    problems: list[str] = []
    improved: list[str] = []
    for key in sorted(current):
        for rule, value in sorted(current[key].items()):
            allowed = baseline.get(key, {}).get(rule)
            if allowed is None:
                problems.append(f"{key}: {rule} {value}, over the target and not in the baseline.")
            elif value > allowed:
                problems.append(f"{key}: {rule} {value}, up from {allowed}.")
            elif value < allowed:
                improved.append(f"{key}: {rule} {value}, down from {allowed}.")
    for key in sorted(baseline):
        for rule, allowed in sorted(baseline[key].items()):
            if rule not in current.get(key, {}):
                improved.append(f"{key}: {rule} was {allowed}, now within the target or gone.")
    return problems, improved


def lowered(current: dict[str, Measures], baseline: dict[str, Measures]) -> dict[str, Measures]:
    """The baseline with every improvement taken, and nothing added or raised."""
    result: dict[str, Measures] = {}
    for key, measures in baseline.items():
        kept = {
            rule: min(allowed, current[key][rule]) for rule, allowed in measures.items() if rule in current.get(key, {})
        }
        if kept:
            result[key] = kept
    return result


def total(baseline: dict[str, Measures]) -> int:
    """How many (function, measure) pairs the baseline holds."""
    return sum(len(measures) for measures in baseline.values())


def main() -> int:
    """Compare what the code measures with the baseline; return the exit status."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--update", action="store_true", help="lower the baseline to what the code measures now")
    options = parser.parse_args()

    limits = targets()
    current = measure(limits)
    baseline = load_baseline()
    problems, improved = compare(current, baseline)

    if problems:
        print("\n".join(problems))
        print(
            "\nOver a target (see [tool.complexity-ratchet] in pyproject.toml).  Split the function up instead; "
            "a baseline entry that has to move because the function was renamed is edited by hand.",
        )
        return 1

    if options.update:
        if improved:
            save_baseline(lowered(current, baseline))
        print(f"{BASELINE.name}: {total(lowered(current, baseline))} measures over a target ({len(improved)} fewer).")
        return 0

    if improved:
        print("\n".join(improved))
        print(f"\nFewer or smaller offenders than the baseline allows -- lock that in with:\n  {UPDATE_HINT}")
        return 1

    print(f"complexity ratchet: {total(baseline)} measures over a target, none worse, none new.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
