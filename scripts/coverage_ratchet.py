"""Ratchet test coverage per layer so each can only go up.

pyproject.toml's ``fail_under`` is one number for the whole program, and one number lets a
well-tested layer hide a neglected one: the core could lose ten points and the total would
still pass on the strength of the GUI, or the reverse.  This script measures each layer on
its own -- the packages under maptasker/src, plus the entry modules that sit beside them --
and compares it with the floor for that layer in coverage_baseline.json.

  * A layer below its floor fails.  Add the tests, rather than lowering the floor.
  * A layer well above its floor is reported, but does not fail: coverage differs by a point
    or so between Python versions and operating systems, so a floor set to the exact figure
    would fail a build for nothing.  ``--update`` raises each floor to one point under what
    was just measured.

    uv run python scripts/coverage_ratchet.py            check (what CI runs, after the tests)
    uv run python scripts/coverage_ratchet.py --update   raise the floors after adding tests

The coverage data comes from a test run made with ``--cov=maptasker`` (the .coverage file).
``--json`` reads a report made by ``coverage json`` instead.  ``--update`` never lowers a
floor.  If one really has to come down, lower it in coverage_baseline.json by hand, so the
reduction shows up in review.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = Path(__file__).with_name("coverage_baseline.json")
UPDATE_HINT = "uv run python scripts/coverage_ratchet.py --update"

# The entry modules (mapit, progargs, runcli, rungui, clireports) sit directly in src rather
# than in a package, and are measured together as one layer.
ENTRY = "entry"

# How far under the measured figure a floor is set, in points.  See the note on versions above.
MARGIN = 1.0

# A layer this far over its floor is worth mentioning.
SLACK = 3.0


def layer_of(path: str) -> str | None:
    """Return the layer a measured file belongs to, or None for a file that is not in one.

    ``maptasker/src/gui/guiwins.py`` is "gui"; ``maptasker/src/mapit.py`` is "entry".
    """
    parts = path.replace("\\", "/").split("/")
    if len(parts) < 3 or parts[:2] != ["maptasker", "src"]:
        return None
    return parts[2] if len(parts) > 3 else ENTRY


def measure(report: dict) -> dict[str, float]:
    """Return each layer's coverage, lines and branches together as coverage.py reckons it."""
    covered: defaultdict[str, int] = defaultdict(int)
    possible: defaultdict[str, int] = defaultdict(int)
    for path, entry in report["files"].items():
        layer = layer_of(path)
        if layer is None:
            continue
        summary = entry["summary"]
        covered[layer] += summary["covered_lines"] + summary.get("covered_branches", 0)
        possible[layer] += summary["num_statements"] + summary.get("num_branches", 0)
    return {layer: 100 * covered[layer] / possible[layer] for layer in possible if possible[layer]}


def floor_for(measured: float) -> int:
    """Return the floor to set for a layer measured at this figure."""
    return max(0, math.floor(measured - MARGIN))


def load_baseline() -> dict[str, int]:
    """Return the committed floor for each layer."""
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def save_baseline(floors: dict[str, int]) -> None:
    """Write the floors, sorted so a change diffs as one line per layer."""
    BASELINE.write_text(json.dumps(dict(sorted(floors.items())), indent=2) + "\n", encoding="utf-8")


def read_report(json_path: Path | None, data_file: Path | None) -> dict:
    """Return coverage.py's JSON report, from a file or made now from the coverage data."""
    if json_path is not None:
        return json.loads(json_path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder) / "coverage.json"
        command = [sys.executable, "-m", "coverage", "json", "-q", "-o", str(out)]
        if data_file is not None:
            command += ["--data-file", str(data_file)]
        done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        if done.returncode != 0:
            sys.exit(f"coverage json failed -- was the test run made with --cov=maptasker?\n{done.stderr}{done.stdout}")
        return json.loads(out.read_text(encoding="utf-8"))


def main() -> int:
    """Compare each layer's coverage with its floor; return the exit status."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--update", action="store_true", help="raise the floors to the current figures")
    parser.add_argument("--json", type=Path, help="a report made by 'coverage json', instead of the .coverage data")
    parser.add_argument("--data-file", type=Path, help="the coverage data file, if not ./.coverage")
    options = parser.parse_args()

    measured = measure(read_report(options.json, options.data_file))
    floors = load_baseline()

    # A layer with a floor has to be measured: a package that vanished from the report would
    # otherwise pass by not being there.
    missing = sorted(set(floors) - set(measured))
    below = sorted(layer for layer in measured if measured[layer] < floors.get(layer, 0))
    unlisted = sorted(set(measured) - set(floors))

    width = max((len(layer) for layer in measured), default=0)
    for layer in sorted(measured):
        floor = floors.get(layer)
        note = "" if floor is None else f"  floor {floor}"
        if floor is not None and measured[layer] >= floor + SLACK:
            note += f"  (room to raise it: {UPDATE_HINT})"
        print(f"{layer:<{width}}  {measured[layer]:5.1f}%{note}")

    if options.update:
        raised = {layer: max(floors.get(layer, 0), floor_for(figure)) for layer, figure in measured.items()}
        save_baseline(raised)
        print(f"\n{BASELINE.name} updated.")
        return 0

    for layer in below:
        print(f"\n{layer}: {measured[layer]:.1f}% is under its floor of {floors[layer]}%.")
    for layer in missing:
        print(f"\n{layer}: has a floor but nothing was measured for it.")
    for layer in unlisted:
        print(f"\n{layer}: is new and has no floor -- run {UPDATE_HINT} to give it one.")
    if below or missing or unlisted:
        print("\nAdd tests for what was left uncovered; do not lower a floor to make this pass.")
        return 1

    print("\ncoverage ratchet: every layer is at or above its floor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
