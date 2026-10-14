"""The per-layer coverage ratchet: how files are grouped, how a figure becomes a floor, and when it fails.

scripts/coverage_ratchet.py reads coverage.py's JSON report, so these tests hand it small reports of their own
rather than running a coverage measurement.  The committed floors are checked against the layers that exist.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location("coverage_ratchet", _ROOT / "scripts" / "coverage_ratchet.py")
ratchet = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ratchet)


def _report(**files: tuple[int, int, int, int]) -> dict:
    """A coverage report: path -> (covered lines, statements, covered branches, branches)."""
    return {
        "files": {
            path: {
                "summary": {
                    "covered_lines": lines,
                    "num_statements": statements,
                    "covered_branches": covered_branches,
                    "num_branches": branches,
                },
            }
            for path, (lines, statements, covered_branches, branches) in files.items()
        },
    }


# ##################################################################################
# Which layer a file is in
# ##################################################################################
@pytest.mark.parametrize(
    ("path", "layer"),
    [
        ("maptasker/src/gui/guiwins.py", "gui"),
        ("maptasker/src/core/maputil2.py", "core"),
        ("maptasker/src/mapit.py", "entry"),
        ("maptasker/src/gui/__init__.py", "gui"),
        ("maptasker/main.py", None),
        ("maptasker/src/__init__.py", "entry"),
        ("tests/test_x.py", None),
        ("maptasker\\src\\edit\\taskedit.py", "edit"),  # the separator on Windows
    ],
)
def test_a_file_belongs_to_the_package_it_sits_in(path: str, layer: str | None) -> None:
    assert ratchet.layer_of(path) == layer


# ##################################################################################
# Measuring
# ##################################################################################
def test_a_layer_counts_lines_and_branches_together() -> None:
    report = _report(
        **{
            "maptasker/src/core/a.py": (8, 10, 1, 2),
            "maptasker/src/core/b.py": (2, 10, 0, 2),
        },
    )
    assert ratchet.measure(report) == {"core": 100 * 11 / 24}


def test_each_layer_is_measured_on_its_own() -> None:
    report = _report(**{"maptasker/src/core/a.py": (10, 10, 0, 0), "maptasker/src/gui/b.py": (5, 10, 0, 0)})
    assert ratchet.measure(report) == {"core": 100.0, "gui": 50.0}


def test_files_outside_the_layers_are_not_counted() -> None:
    report = _report(**{"maptasker/main.py": (0, 4, 0, 0), "maptasker/src/core/a.py": (10, 10, 0, 0)})
    assert ratchet.measure(report) == {"core": 100.0}


def test_a_package_of_nothing_but_empty_files_is_left_out_rather_than_divided_by_zero() -> None:
    assert ratchet.measure(_report(**{"maptasker/src/core/__init__.py": (0, 0, 0, 0)})) == {}


@pytest.mark.parametrize(("measured", "floor"), [(72.4, 71), (80.0, 79), (0.5, 0), (100.0, 99)])
def test_a_floor_is_a_point_under_the_figure_rounded_down(measured: float, floor: int) -> None:
    assert ratchet.floor_for(measured) == floor


# ##################################################################################
# The check itself
# ##################################################################################
@pytest.fixture
def run(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    """Run main() against a report and a baseline of the test's choosing; return (exit status, output, baseline)."""
    baseline = tmp_path / "coverage_baseline.json"
    monkeypatch.setattr(ratchet, "BASELINE", baseline)

    def go(report: dict, floors: dict, *flags: str) -> tuple[int, str, dict]:
        baseline.write_text(json.dumps(floors), encoding="utf-8")
        report_file = tmp_path / "report.json"
        report_file.write_text(json.dumps(report), encoding="utf-8")
        monkeypatch.setattr("sys.argv", ["coverage_ratchet.py", "--json", str(report_file), *flags])
        status = ratchet.main()
        return status, capsys.readouterr().out, json.loads(baseline.read_text(encoding="utf-8"))

    return go


_GOOD = _report(**{"maptasker/src/core/a.py": (90, 100, 0, 0), "maptasker/src/gui/b.py": (70, 100, 0, 0)})


def test_every_layer_at_or_above_its_floor_passes(run) -> None:
    status, out, _ = run(_GOOD, {"core": 89, "gui": 70})
    assert status == 0
    assert "every layer is at or above its floor" in out


def test_a_layer_under_its_floor_fails_and_names_it(run) -> None:
    status, out, _ = run(_GOOD, {"core": 95, "gui": 70})
    assert status == 1
    assert "core: 90.0% is under its floor of 95%" in out
    assert "gui: 70.0% is under" not in out


def test_a_layer_far_above_its_floor_is_mentioned_but_does_not_fail(run) -> None:
    status, out, _ = run(_GOOD, {"core": 50, "gui": 70})
    assert status == 0
    assert "room to raise it" in out


def test_a_layer_with_a_floor_but_nothing_measured_fails(run) -> None:
    """A package that vanished from the report must not pass by not being there."""
    status, out, _ = run(_GOOD, {"core": 89, "gui": 70, "device": 80})
    assert status == 1
    assert "device: has a floor but nothing was measured" in out


def test_a_new_layer_has_to_be_given_a_floor(run) -> None:
    status, out, _ = run(_GOOD, {"core": 89})
    assert status == 1
    assert "gui: is new and has no floor" in out


# ##################################################################################
# Updating
# ##################################################################################
def test_update_raises_the_floors_to_a_point_under_the_figures(run) -> None:
    status, _, floors = run(_GOOD, {"core": 50, "gui": 50}, "--update")
    assert status == 0
    assert floors == {"core": 89, "gui": 69}


def test_update_never_lowers_a_floor(run) -> None:
    _, _, floors = run(_GOOD, {"core": 95, "gui": 10}, "--update")
    assert floors["core"] == 95  # measured 90.0 -- the floor stays where it was set
    assert floors["gui"] == 69


def test_update_gives_a_new_layer_its_first_floor(run) -> None:
    _, _, floors = run(_GOOD, {"core": 89}, "--update")
    assert floors == {"core": 89, "gui": 69}


# ##################################################################################
# The committed baseline
# ##################################################################################
def test_the_committed_floors_are_for_layers_that_exist() -> None:
    """A floor for a package that was renamed or removed would otherwise fail the build with no
    way to meet it."""
    floors = json.loads((_ROOT / "scripts" / "coverage_baseline.json").read_text(encoding="utf-8"))
    packages = {path.name for path in (_ROOT / "maptasker" / "src").iterdir() if path.is_dir() and path.name != "__pycache__"}
    assert set(floors) <= packages | {ratchet.ENTRY}
    assert all(isinstance(value, int) and 0 <= value <= 100 for value in floors.values())
