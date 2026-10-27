"""scripts/perf_check.py: the backup it times, and what it makes of the timings.

What is timed has to be a backup MapTasker loads cleanly and whose objects are all there however many copies
are asked for, since a timing of a half-loaded one means nothing.  What is made of the timings is the gate: slower than
the tolerance fails, faster is only noted, and no baseline is its own answer.
"""

from __future__ import annotations

import importlib.util
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from maptasker.src.core.primitem import PrimeItems

from tests.shared_fixtures import _load_local

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "perf_check.py"
_spec = importlib.util.spec_from_file_location("perf_check", _SCRIPT)
assert _spec is not None
assert _spec.loader is not None
pc = importlib.util.module_from_spec(_spec)
sys.modules["perf_check"] = pc
_spec.loader.exec_module(pc)

pytestmark = pytest.mark.usefixtures("_runtime")

_BASELINE = {"load": 1.0, "map": 10.0, "diagram": 20.0}


def _root(scale: int) -> ET.Element:
    return ET.fromstring(pc.scaled_backup(scale))


def test_each_copy_brings_every_object_of_the_test_backup() -> None:
    base = ET.parse(pc.SYNTHETIC).getroot()
    one, three = _root(1), _root(3)

    for tag in ("Project", "Profile", "Task", "Scene"):
        assert len(three.findall(tag)) == 3 * len(base.findall(tag)) == 3 * len(one.findall(tag))


def test_nothing_is_named_or_numbered_twice() -> None:
    root = _root(5)

    for tag, key in (("Task", "id"), ("Profile", "id"), ("Project", "name"), ("Scene", "nme")):
        values = [element.findtext(key) for element in root.findall(tag)]
        assert len(values) == len(set(values)), tag
    assert len({element.get("sr") for element in root.findall("Task")}) == len(root.findall("Task"))


def test_every_perform_task_names_a_task_that_is_there() -> None:
    root = _root(4)
    names = {task.findtext("nme") for task in root.findall("Task")}

    calls = [
        action.findtext("Str[@sr='arg0']")
        for element in root
        for action in element.iter("Action")
        if action.findtext("code") == "130"
    ]

    assert len(calls) > 4 * 6, "the Tasks call one another, which is what the Diagram draws"
    assert set(calls) <= names


def test_the_ids_a_project_and_a_profile_list_are_the_ids_of_tasks_there() -> None:
    root = _root(3)
    ids = {task.findtext("id") for task in root.findall("Task")}

    listed = {
        part
        for element in root
        for tag in ("tids", "mid0")
        if (text := element.findtext(tag))
        for part in text.split(",")
    }

    assert listed <= ids


def test_it_is_the_same_backup_every_time() -> None:
    assert pc.scaled_backup(3) == pc.scaled_backup(3)


def test_the_backup_loads_in_full(tmp_path: Path) -> None:
    _load_local(tmp_path, pc.scaled_backup(3))

    tables = PrimeItems.tasker_root_elements
    assert PrimeItems.error_code == 0
    assert len(tables["all_tasks"]) == 3 * 7
    assert len(tables["all_projects"]) == 3 * 2
    assert len(tables["all_scenes"]) == 3 * 3


def test_within_the_tolerance_is_ok() -> None:
    found = {"load": 1.1, "map": 12.0, "diagram": 20.0}

    status, lines = pc.compare("x", found, _BASELINE, 0.25)

    assert status == pc.EXIT_OK
    assert all("SLOWER" not in line for line in lines)


def test_a_phase_slower_than_the_tolerance_fails_and_the_others_do_not() -> None:
    found = {"load": 1.0, "map": 10.0, "diagram": 26.0}

    status, lines = pc.compare("x", found, _BASELINE, 0.25)

    assert status == pc.EXIT_SLOWER
    (slow,) = [line for line in lines if "SLOWER" in line]
    assert slow.strip().startswith("diagram")


def test_faster_is_noted_not_failed() -> None:
    found = {"load": 0.5, "map": 10.0, "diagram": 20.0}

    status, lines = pc.compare("x", found, _BASELINE, 0.25)

    assert status == pc.EXIT_OK
    assert any("faster than the baseline" in line for line in lines)


def test_no_baseline_is_its_own_answer() -> None:
    found = {"load": 1.0, "map": 10.0, "diagram": 20.0}

    assert pc.compare("x", found, None, 0.25)[0] == pc.EXIT_NO_BASELINE
    assert pc.compare("x", found, {"load": 1.0}, 0.25)[0] == pc.EXIT_NO_BASELINE


def test_recording_writes_only_this_input_and_keeps_the_others(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    pc._record(path, "synthetic x200", {"load": 1.0, "map": 2.0, "diagram": 3.0})
    pc._record(path, "other.xml", {"load": 4.0, "map": 5.0, "diagram": 6.0})

    inputs = pc._read(path)["inputs"]

    assert inputs["synthetic x200"] == {"load": 1.0, "map": 2.0, "diagram": 3.0}
    assert inputs["other.xml"] == {"load": 4.0, "map": 5.0, "diagram": 6.0}


def test_the_committed_baseline_has_every_phase_for_the_input_that_is_checked() -> None:
    baseline = pc._read(pc.BASELINE)["inputs"][f"synthetic x{pc.DEFAULT_SCALE}"]

    assert set(baseline) == set(pc.PHASES)
    assert all(value > 0 for value in baseline.values())
