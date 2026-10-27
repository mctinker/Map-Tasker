"""Time the Map and the Diagram build, and fail when either gets slower than it was.

Speed was compared by hand -- a stopwatch around one change, then another -- each time something
touched the build.  This does it every time, the same way, against a baseline kept in
perf_baseline.json beside this script:

    uv run python scripts/perf_check.py                    check (what run-ci.sh runs)
    uv run python scripts/perf_check.py --update           record the timings as the new baseline
    uv run python scripts/perf_check.py -backup FILE       also time a backup of your own (see below)

WHAT IS TIMED

A command-line run's three steps, on one loaded configuration, in this order: LOAD (parse the backup
into the tables), MAP (the Map's HTML) and DIAGRAM (the outline the Diagram view is drawn from).

tests/data/synthetic_backup.xml is the input, but as it stands -- seven Tasks -- it builds in a few
milliseconds, which is noise.  So it is copied --scale times, every Project, Profile, Task and Scene
renamed and renumbered in each copy (ids are offset, names get a number), and written to a temporary
file.  The copy is the same on every machine and every run.  A real backup is much larger and its
Diagram is the slow step, so a regression in how the Diagram grows with the size of a configuration
shows here as it does there.

HOW A TIMING BECOMES A FAILURE

A baseline in seconds would only be right on the machine that made it.  So each run also times a fixed
piece of ordinary Python work (parse some XML, format text, fill and sort dictionaries: what the build
does), and every timing is kept in units of that, "the Diagram takes 9 of them".  That carries from one
machine to another well enough to catch a step that takes half as long again, which is what the
tolerance (--tolerance, default 0.25) is for.  Three things keep a slow run from being mistaken for a
regression:

  * every measurement is the best of --repeat runs (default 3), each in a process of its own so that
    nothing is cached from the one before;
  * the calibration is timed in the same process as the build, so a machine that is busy is busy for both;
  * only SLOWER fails.  Faster is noted, and --update records it, so the next regression has less room.

A phase that is not in the baseline (the first run, or a new --scale) fails too, with the command that
puts it there.

A BACKUP OF YOUR OWN

-backup FILE (repeatable) times that file as well, against scripts/perf_baseline_local.json, which is
not in the repository: a backup is personal.  --update with -backup records it there.  The timings are
the same ones, on the file as it is, which is the one place the real 17-second Diagram can be watched.

Exit status: 0 within the tolerance, 1 a phase got slower, 2 there is nothing to compare it with.
"""

from __future__ import annotations

import argparse
import copy
import gc
import json
import platform
import re
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING

from defusedxml import ElementTree as SafeET
from maptasker.src import clireports
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.mapgen import mapexport

if TYPE_CHECKING:
    from collections.abc import Callable

ROOT = Path(__file__).resolve().parent.parent
SYNTHETIC = ROOT / "tests" / "data" / "synthetic_backup.xml"
BASELINE = Path(__file__).with_name("perf_baseline.json")
LOCAL_BASELINE = Path(__file__).with_name("perf_baseline_local.json")

PHASES = ("load", "map", "diagram")
DEFAULT_SCALE = 200
DEFAULT_REPEAT = 3
DEFAULT_TOLERANCE = 0.25
# What a phase is allowed to be faster than the baseline before the check says so.  Only a note.
NOTEWORTHY_GAIN = 0.2

EXIT_OK, EXIT_SLOWER, EXIT_NO_BASELINE = 0, 1, 2

# The ids in the backup that each copy has to move, and how far: the highest in the file is 107.
ID_STEP = 1000
# Every this many copies, the first Task of a copy calls into the next copy.
CROSS_EVERY = 2


# ##################################################################################
# The input
# ##################################################################################
def _split_ids(text: str | None) -> list[str]:
    return [part for part in (text or "").split(",") if part]


def _renumber(text: str | None, step: int) -> str:
    return ",".join(str(int(part) + step) for part in _split_ids(text))


def _rename(text: str | None, copy_number: int) -> str:
    return f"{text} {copy_number}" if text else ""


def _rename_list(text: str | None, copy_number: int) -> str:
    return ",".join(_rename(part, copy_number) for part in _split_ids(text))


def _task_names(root: ET.Element) -> set[str]:
    return {name.text for task in root.findall("Task") if (name := task.find("nme")) is not None and name.text}


def _move_scene_tasks(properties: ET.Element, step: int) -> None:
    """The Tasks a Scene's Key and List events run, which are named by id."""
    for tag in ("keyTask", "iconclickTask", "itemselectedTask"):
        for element in properties.iter(tag):
            element.text = _renumber(element.text, step)


def _make_copy(base: ET.Element, copy_number: int) -> list[ET.Element]:
    """One renamed, renumbered copy of every object in the backup."""
    step = ID_STEP * copy_number
    tasks = _task_names(base)
    objects = [copy.deepcopy(element) for element in base if element.tag in {"Project", "Profile", "Task", "Scene"}]
    for index, element in enumerate(objects):
        if element.tag == "Task":
            element.set("sr", f"task{int(element.findtext('id', '0')) + step}")
            _set(element, "id", _renumber(element.findtext("id"), step))
            _set(element, "nme", _rename(element.findtext("nme"), copy_number), only_if_there=True)
        elif element.tag == "Profile":
            element.set("sr", f"prof{int(element.findtext('id', '0')) + step}")
            _set(element, "id", _renumber(element.findtext("id"), step))
            for tag in ("mid0", "mid1", "mid2", "mid3"):
                _set(element, tag, _renumber(element.findtext(tag), step), only_if_there=True)
            _set(element, "nme", _rename(element.findtext("nme"), copy_number), only_if_there=True)
        elif element.tag == "Project":
            element.set("sr", f"proj{copy_number * 10 + index}")
            _set(element, "name", _rename(element.findtext("name"), copy_number), only_if_there=True)
            _set(element, "pids", _renumber(element.findtext("pids"), step), only_if_there=True)
            _set(element, "tids", _renumber(element.findtext("tids"), step), only_if_there=True)
            _set(element, "scenes", _rename_list(element.findtext("scenes"), copy_number), only_if_there=True)
        else:
            _set(element, "nme", _rename(element.findtext("nme"), copy_number))
            element.set("sr", element.findtext("nme", ""))
            for properties in element.iter("PropertiesElement"):
                _move_scene_tasks(properties, step)
        # Perform Task (130) names the Task it calls, in a Task or in a Scene's list item.
        for action in element.iter("Action"):
            called = action.find("Str[@sr='arg0']")
            if action.findtext("code") == "130" and called is not None and called.text in tasks:
                called.text = _rename(called.text, copy_number)
    return objects


def _action(code: str, *arguments: str) -> str:
    return f'<Action sr="act{{}}" ve="7"><code>{code}</code>{"".join(arguments)}</Action>'


def _text(index: int, value: str) -> str:
    return f'<Str sr="arg{index}" ve="3">{value}</Str>'


def _number(index: int, value: int) -> str:
    return f'<Int sr="arg{index}" val="{value}"/>'


def _filler(called: list[str]) -> list[str]:
    """What a Task of a real configuration does besides what the test backup's Tasks do, and then calls each of `called`.

    A real backup has some eighteen actions to a Task, the commonest a Variable Set, an If with its End If,
    a Flash, and about one Perform Task: the calls are what the Diagram is drawn from.
    """
    condition = (
        '<ConditionList sr="if"><Condition sr="c0" ve="3"><lhs>%count</lhs><op>7</op><rhs>3</rhs></Condition>'
        "</ConditionList>"
    )
    variable = (_number(2, 0), _number(3, 0), _number(4, 0), _number(5, 3))
    return [
        *(_action("547", _text(0, f"%value{n}"), _text(1, f"{n} %count"), *variable) for n in range(4)),
        f'<Action sr="act{{}}" ve="7"><code>37</code>{condition}</Action>',
        _action("548", _text(0, "Counted %count")),
        _action("547", _text(0, "%count"), _text(1, "%count + 1"), *variable),
        _action("38"),
        _action("549", _text(0, "%value0")),
        *(
            _action(
                "130",
                _text(0, name),
                _number(1, 5),
                _text(2, ""),
                _text(3, ""),
                _text(4, ""),
                _number(5, 0),
                _number(6, 0),
                _text(7, ""),
                _number(8, 0),
                _number(9, 0),
            )
            for name in called
        ),
    ]


def _set(element: ET.Element, tag: str, value: str, *, only_if_there: bool = False) -> None:
    child = element.find(tag)
    if child is None:
        if only_if_there:
            return
        child = ET.SubElement(element, tag)
    child.text = value


def scaled_backup(scale: int) -> str:
    """tests/data/synthetic_backup.xml, `scale` times over, as the text of a backup."""
    base = SafeET.fromstring(SYNTHETIC.read_text(encoding="utf-8"))
    scaled = ET.Element(base.tag, base.attrib)
    for copy_number in range(1, scale + 1):
        scaled.extend(_make_copy(base, copy_number))
    # Each Task calls the next of its copy that has a name, the last the first, and the first of every
    # copy also the first of the next: connectors of every length, as a configuration of Projects has.
    per_copy = [
        [t for t in scaled if t.tag == "Task" and t.findtext("nme", "").endswith(f" {n}")] for n in range(1, scale + 1)
    ]
    for copy_number, tasks in enumerate(per_copy):
        names = [task.findtext("nme", "") for task in tasks]
        for index, task in enumerate(tasks):
            called = [names[(index + 1) % len(names)], names[0]]  # The next one, and the copy's own hub.
            if index == 0 and copy_number % CROSS_EVERY == 0:
                called = [per_copy[(copy_number + 1) % scale][0].findtext("nme", "")]
            first = len(task.findall("Action"))
            for number, text in enumerate(_filler(called), start=first):
                task.append(SafeET.fromstring(text.replace("act{}", f"act{number}")))
    ET.indent(scaled, space="\t")
    return "<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>\n" + ET.tostring(scaled, encoding="unicode")


# ##################################################################################
# The measurement (in a process of its own)
# ##################################################################################
def _calibration_seconds() -> float:
    """A fixed piece of ordinary Python work -- XML in, text out, dictionaries filled and sorted.

    The same on every machine; how long it takes is the unit the build's timings are kept in.
    """
    started = time.perf_counter()
    rows = "".join(f"<r id='{n}'><n>{(n * 7919) % 1009} name</n><v>value {n}</v></r>" for n in range(200000))
    root = SafeET.fromstring(f"<d>{rows}</d>")
    table: dict[str, list[str]] = {}
    for row in root:
        key = (row.findtext("n") or "")[:3]
        table.setdefault(key, []).append(f"<b>{row.findtext('v')}</b>&nbsp;{row.get('id')}")
    text = "\n".join(f"{key}: {', '.join(sorted(values))}" for key, values in sorted(table.items()))
    return (time.perf_counter() - started) if re.search("value", text) else 0.0


def _ignore_saved_settings(state: object) -> None:
    """Stands in for clireports' reading of the settings file."""


def _timed(timings: dict[str, float], name: str, step: Callable[[], object]) -> None:
    gc.collect()
    started = time.perf_counter()
    step()
    timings[name] = time.perf_counter() - started


def _measure(path: Path, outdir: Path) -> dict[str, float]:
    """Load `path`, then build the Map and the Diagram from it, as the command line does; seconds each."""
    # The GUI's saved settings change what is built; a timing has to be of the defaults.
    clireports._apply_saved_settings = _ignore_saved_settings
    options = clireports.build_parser().parse_args(
        ["-export", mapexport.MAP, "-file", str(path), "-outdir", str(outdir), "-history_dir", str(outdir / "history")],
    )
    calibration = _calibration_seconds()
    timings: dict[str, float] = {}

    clireports._prepare(options, state=PrimeItems)
    _timed(timings, "load", lambda: clireports._load_backup(str(path), state=PrimeItems))
    _timed(timings, "map", lambda: clireports._build_the_view(mapexport.MAP, state=PrimeItems))
    _timed(timings, "diagram", lambda: clireports._build_the_view(mapexport.DIAGRAM, state=PrimeItems))
    # Calibrated again after, so that a machine that slowed down or sped up part-way shows in the unit.
    timings["calibration"] = min(calibration, _calibration_seconds())
    return timings


def _worker(path: Path) -> int:
    with tempfile.TemporaryDirectory(prefix="maptasker_perf_") as folder:
        print(json.dumps(_measure(path, Path(folder))))
    return 0


def measure(path: Path, repeat: int) -> dict[str, float]:
    """The best of `repeat` runs of each phase (and of the calibration), in units of the calibration."""
    runs = []
    for number in range(repeat):
        done = subprocess.run(
            [sys.executable, str(Path(__file__)), "--worker", str(path)],
            capture_output=True,
            text=True,
            check=False,
            cwd=ROOT,
        )
        if done.returncode:
            sys.stderr.write(done.stderr[-2000:])
            msg = f"The timing run {number + 1} for {path.name} failed."
            raise SystemExit(msg)
        runs.append(json.loads(done.stdout.strip().splitlines()[-1]))
    best = {name: min(run[name] for run in runs) for name in (*PHASES, "calibration")}
    unit = best["calibration"]
    return {**{name: best[name] / unit for name in PHASES}, "seconds": best["load"] + best["map"] + best["diagram"]}


# ##################################################################################
# The comparison
# ##################################################################################
def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def compare(
    name: str, found: dict[str, float], baseline: dict[str, float] | None, tolerance: float
) -> tuple[int, list[str]]:
    """The lines to print for one input, and whether it is within `tolerance` of its baseline."""
    lines = [f"{name}"]
    status = EXIT_OK
    for phase in PHASES:
        units = found[phase]
        if baseline is None or phase not in baseline:
            lines.append(f"  {phase:<8}{units:>8.2f}   no baseline")
            status = max(status, EXIT_NO_BASELINE)
            continue
        ratio = units / baseline[phase]
        verdict = "ok"
        if ratio > 1 + tolerance:
            verdict, status = f"SLOWER than the {1 + tolerance:.2f}x allowed", max(status, EXIT_SLOWER)
        elif ratio < 1 - NOTEWORTHY_GAIN:
            verdict = "faster than the baseline; --update records it"
        lines.append(f"  {phase:<8}{units:>8.2f}   baseline {baseline[phase]:>7.2f}   {ratio:>5.2f}x   {verdict}")
    return status, lines


def _record(path: Path, name: str, found: dict[str, float]) -> None:
    data = _read(path)
    data.setdefault("note", "Timings in units of a fixed piece of Python work; see scripts/perf_check.py.")
    data["python"] = platform.python_version()
    data.setdefault("inputs", {})[name] = {phase: round(found[phase], 3) for phase in PHASES}
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    """Time the inputs, then compare or record them."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--update", action="store_true", help="record these timings as the baseline")
    parser.add_argument("--scale", type=int, default=DEFAULT_SCALE, help="copies of the synthetic backup")
    parser.add_argument("--repeat", type=int, default=DEFAULT_REPEAT, help="runs per input; the best counts")
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE, help="how much slower is too slow")
    parser.add_argument(
        "-backup", action="append", type=Path, default=[], help="also time this backup (local baseline)"
    )
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    options = parser.parse_args()
    if options.worker:
        return _worker(options.worker)

    status = EXIT_OK
    jobs: list[tuple[str, Path, Path]] = []
    with tempfile.TemporaryDirectory(prefix="maptasker_perf_input_") as folder:
        synthetic = Path(folder) / "synthetic.xml"
        synthetic.write_text(scaled_backup(options.scale), encoding="utf-8")
        name = f"synthetic x{options.scale}"
        jobs.append((name, synthetic, BASELINE))
        jobs += [(path.name, path, LOCAL_BASELINE) for path in options.backup]
        for name, path, baseline_file in jobs:
            found = measure(path, options.repeat)
            print(f"{name}: {path.stat().st_size / 1e6:.1f} MB, {found['seconds']:.1f} s here")
            if options.update:
                _record(baseline_file, name, found)
                print(f"  recorded in {baseline_file.name}: " + ", ".join(f"{p} {found[p]:.2f}" for p in PHASES))
                continue
            baseline = _read(baseline_file).get("inputs", {}).get(name)
            result, lines = compare(name, found, baseline, options.tolerance)
            print("\n".join(lines[1:]))
            status = max(status, result)
    if status == EXIT_NO_BASELINE:
        print(
            "\nNothing to compare with.  Record it with --update (add -backup FILE for a backup of your own: its baseline "
            "stays on this machine; the synthetic one is committed)."
        )
    elif status == EXIT_SLOWER:
        print("\nSlower than the baseline allows.  If it is meant (more work done), --update; if not, find the cause.")
    return status


if __name__ == "__main__":
    sys.exit(main())
