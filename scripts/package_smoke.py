"""Smoke-test the built package: install the wheel in an empty environment and run it.

``twine check`` reads the wheel's metadata and nothing else.  It cannot tell that a data file the program opens at
start-up never made it into the wheel, that a module imports something the wheel does not depend on, or that the
console script is not wired to anything.  Those are found by what a user does first: install the wheel somewhere
that is not this checkout, and run it.  This does that, in a scratch directory, and checks:

  * the wheel holds every file the repository tracks under maptasker/, and nothing it does not (a stray local file
    in the package folder is shipped with it -- one was: a ``.claude`` settings file with the author's paths in it);
  * it installs, with its dependencies, into a fresh virtual environment;
  * every module in it imports there (a missing dependency, or a module that only works from the checkout);
  * ``maptasker -version`` runs, and says the wheel's own version;
  * ``maptasker -healthcheck`` and ``-export map|diagram`` read a sample backup and write a report, with the working
    directory and HOME somewhere that is not the checkout, so a file found only in the checkout is not found.

    uv run python scripts/package_smoke.py                 build the wheel, then test it (what CI runs)
    uv run python scripts/package_smoke.py --dist dist     test the wheel already in dist/

Needs uv and a network (the dependencies are installed from the index).  Nothing is left behind.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "tests" / "data" / "synthetic_backup.xml"
PACKAGE = "maptasker"
# A Project in the sample backup, which a Map of it has to name.
SAMPLE_PROJECT = "Reminders"


class SmokeError(Exception):
    """A check failed; the message says which and why."""


def run(
    command: list[str], *, cwd: Path, env: dict[str, str], what: str, expect: int = 0
) -> subprocess.CompletedProcess[str]:
    """Run a command; raise SmokeError with its output unless it exits with the status expected."""
    done = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, check=False)
    if done.returncode != expect:
        tail = "\n".join((done.stdout + done.stderr).strip().splitlines()[-15:])
        message = f"{what}: exit {done.returncode}, expected {expect}\n{tail}"
        raise SmokeError(message)
    return done


def build_wheel(into: Path) -> Path:
    """Build the wheel into this directory and return its path."""
    subprocess.run(["uv", "build", "--wheel", "--out-dir", str(into)], cwd=ROOT, check=True, capture_output=True)
    wheels = list(into.glob("*.whl"))
    if len(wheels) != 1:
        message = f"expected one wheel in {into}, found {len(wheels)}"
        raise SmokeError(message)
    return wheels[0]


def wheel_in(dist: Path) -> Path:
    """The newest wheel in this folder."""
    wheels = sorted(dist.glob("*.whl"))
    if not wheels:
        message = f"no wheel in {dist}"
        raise SmokeError(message)
    return wheels[-1]


def tracked_files() -> set[str]:
    """Every file git tracks under maptasker/."""
    listed = subprocess.run(["git", "ls-files", PACKAGE], cwd=ROOT, capture_output=True, text=True, check=True)
    return {line for line in listed.stdout.splitlines() if line}


def check_contents(wheel: Path) -> None:
    """The wheel holds what the repository tracks under maptasker/, and nothing else."""
    shipped = {name for name in zipfile.ZipFile(wheel).namelist() if name.startswith(f"{PACKAGE}/")}
    tracked = tracked_files()
    missing, extra = sorted(tracked - shipped), sorted(shipped - tracked)
    problems = []
    if missing:
        problems.append(f"{len(missing)} tracked file(s) are not in the wheel, e.g. {', '.join(missing[:5])}")
    if extra:
        problems.append(f"{len(extra)} file(s) in the wheel are not tracked, e.g. {', '.join(extra[:5])}")
    if problems:
        raise SmokeError("wheel contents: " + "; ".join(problems))
    print(f"  ok  the wheel holds all {len(tracked)} tracked files under {PACKAGE}/ and nothing else")


def venv_python(venv: Path) -> Path:
    """The interpreter of a virtual environment, on either kind of platform."""
    return venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def console_script(venv: Path) -> Path:
    """The maptasker command the wheel installed."""
    return venv / ("Scripts/maptasker.exe" if sys.platform == "win32" else "bin/maptasker")


IMPORT_EVERY_MODULE = """
import importlib, pkgutil, sys
import maptasker
failed = []
count = 0
for module in pkgutil.walk_packages(maptasker.__path__, "maptasker."):
    count += 1
    try:
        importlib.import_module(module.name)
    except Exception as error:
        failed.append(f"{module.name}: {type(error).__name__}: {error}")
print(count)
if failed:
    print("\\n".join(failed), file=sys.stderr)
    sys.exit(1)
"""


def smoke(wheel: Path, scratch: Path) -> None:
    """Install the wheel in a fresh environment under `scratch` and try it."""
    venv = scratch / "venv"
    home = scratch / "home"
    work = scratch / "work"
    for folder in (home, work):
        folder.mkdir()
    # Nothing of this checkout reaches the run: not its working directory, not its PYTHONPATH, not its HOME.
    env = {key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "VIRTUAL_ENV", "PYTHONHOME"}}
    env.update(HOME=str(home), USERPROFILE=str(home), PYTHONNOUSERSITE="1", NO_COLOR="1", BROWSER="true")

    run(["uv", "venv", "--python", sys.executable, str(venv)], cwd=work, env=env, what="creating the environment")
    run(
        ["uv", "pip", "install", "--python", str(venv_python(venv)), str(wheel)],
        cwd=work,
        env=env,
        what="installing the wheel and its dependencies",
    )
    print(f"  ok  {wheel.name} installs with its dependencies into a fresh environment")

    counted = run([str(venv_python(venv)), "-c", IMPORT_EVERY_MODULE], cwd=work, env=env, what="importing every module")
    print(f"  ok  all {counted.stdout.strip()} modules import there")

    command = str(console_script(venv))
    version = run([command, "-version"], cwd=work, env=env, what="maptasker -version")
    wheel_version = wheel.name.split("-")[1]
    if wheel_version not in version.stdout:
        message = f"maptasker -version does not say {wheel_version}"
        raise SmokeError(message)
    print(f"  ok  maptasker -version runs and says {wheel_version}")

    backup = work / "backup.xml"
    shutil.copy(SAMPLE, backup)
    report = run([command, "-healthcheck", "-file", str(backup)], cwd=work, env=env, what="maptasker -healthcheck")
    if "MapTasker Health Check" not in report.stdout:
        message = "maptasker -healthcheck wrote no report"
        raise SmokeError(message)
    print("  ok  maptasker -healthcheck reads a backup and writes its report")

    for view, file_format in (("map", "md"), ("map", "pdf"), ("diagram", "md")):
        done = run(
            [command, "-export", view, "-format", file_format, "-file", str(backup)],
            cwd=work,
            env=env,
            what=f"maptasker -export {view} -format {file_format}",
        )
        written = Path(done.stdout.strip().splitlines()[-1]) if done.stdout.strip() else None
        if written is None or not written.is_file() or written.stat().st_size < 500:
            message = f"-export {view} -format {file_format} wrote no file (said: {done.stdout.strip()!r})"
            raise SmokeError(message)
        if file_format == "md" and view == "map" and SAMPLE_PROJECT not in written.read_text(encoding="utf-8"):
            message = f"the exported Map does not name the sample's Project, {SAMPLE_PROJECT!r}"
            raise SmokeError(message)
        print(f"  ok  maptasker -export {view} -format {file_format} builds it and writes {written.name}")


def main() -> int:
    """Test the wheel in --dist, or one built now; return the exit status."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--dist", type=Path, help="a folder holding the wheel to test (default: build one)")
    options = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="maptasker-smoke-") as folder:
        scratch = Path(folder)
        try:
            wheel = wheel_in(options.dist) if options.dist else build_wheel(scratch)
            check_contents(wheel)
            smoke(wheel, scratch)
        except SmokeError as error:
            print(f"\nFAILED -- {error}", file=sys.stderr)
            return 1
    print("package smoke test: the built package installs and runs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
