"""scripts/package_smoke.py: the checks that do not need a network.

The install-and-run half is the CI gate itself (it needs the package index); what is tested here is the half that compares the
wheel with the repository, and the paths it builds, since those are what fail quietly when someone changes how the package is built.
"""

from __future__ import annotations

import importlib.util
import sys
import zipfile
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "package_smoke.py"
_spec = importlib.util.spec_from_file_location("package_smoke", _SCRIPT)
assert _spec is not None
assert _spec.loader is not None
ps = importlib.util.module_from_spec(_spec)
sys.modules["package_smoke"] = ps
_spec.loader.exec_module(ps)


def _wheel(tmp_path: Path, names: list[str]) -> Path:
    path = tmp_path / "maptasker-1.0.0-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as archive:
        for name in names:
            archive.writestr(name, "x")
    return path


def test_a_wheel_that_holds_what_is_tracked_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tracked = {"maptasker/main.py", "maptasker/assets/json/arg_specs.json"}
    monkeypatch.setattr(ps, "tracked_files", lambda: tracked)

    ps.check_contents(_wheel(tmp_path, [*tracked, "maptasker-1.0.0.dist-info/METADATA"]))


def test_a_data_file_missing_from_the_wheel_is_named(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ps, "tracked_files", lambda: {"maptasker/main.py", "maptasker/assets/json/arg_specs.json"})

    with pytest.raises(ps.SmokeError, match=r"not in the wheel, e\.g\. maptasker/assets/json/arg_specs\.json"):
        ps.check_contents(_wheel(tmp_path, ["maptasker/main.py"]))


def test_a_file_in_the_wheel_that_git_does_not_track_is_named(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A local file left in the package folder is shipped with it: a .claude settings file was."""
    monkeypatch.setattr(ps, "tracked_files", lambda: {"maptasker/main.py"})

    with pytest.raises(ps.SmokeError, match=r"not tracked, e\.g\. maptasker/src/\.claude/settings\.local\.json"):
        ps.check_contents(_wheel(tmp_path, ["maptasker/main.py", "maptasker/src/.claude/settings.local.json"]))


def test_the_environment_paths_are_the_ones_each_platform_uses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    assert ps.venv_python(tmp_path) == tmp_path / "bin" / "python"
    assert ps.console_script(tmp_path) == tmp_path / "bin" / "maptasker"

    monkeypatch.setattr(sys, "platform", "win32")
    assert ps.venv_python(tmp_path) == tmp_path / "Scripts" / "python.exe"
    assert ps.console_script(tmp_path) == tmp_path / "Scripts" / "maptasker.exe"


def test_the_sample_backup_the_smoke_test_reads_names_the_project_it_looks_for() -> None:
    assert ps.SAMPLE_PROJECT in ps.SAMPLE.read_text(encoding="utf-8")


def test_a_command_that_exits_wrongly_is_reported_with_the_end_of_its_output(tmp_path: Path) -> None:
    with pytest.raises(ps.SmokeError, match=r"checking: exit 3, expected 0\nboom"):
        ps.run(
            [sys.executable, "-c", "import sys; print('boom', file=sys.stderr); sys.exit(3)"],
            cwd=tmp_path,
            env={},
            what="checking",
        )


def test_the_wheel_in_this_checkout_holds_what_git_tracks() -> None:
    """The real check, against a real build -- the one that found the stray .claude file."""
    import shutil
    import tempfile

    if shutil.which("uv") is None:
        pytest.skip("uv is needed to build the wheel")
    with tempfile.TemporaryDirectory() as folder:
        wheel = ps.build_wheel(Path(folder))
        names = {name for name in zipfile.ZipFile(wheel).namelist() if name.startswith("maptasker/")}

    assert not [name for name in names if "/.claude/" in name]
    assert names >= ps.tracked_files()
