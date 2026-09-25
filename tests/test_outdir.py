"""Output folder (outdir) Unit Tests

Reports, exports and the Map/Diagram files go to one folder: the 'output_directory' setting,
or Documents/MapTasker when it is empty.  conftest points the default at the working
directory for every other test; the tests of the default itself put the real one back.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from maptasker.src import healthck, outdir
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.parsearg import runtime_parser
from maptasker.src.primitem import PrimeItems
from maptasker.src.runcli import process_extended_arguments
from maptasker.src.sysconst import ARGUMENT_NAMES


@pytest.fixture(autouse=True)
def _arguments(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Fresh arguments, run from a directory of this test's own."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(PrimeItems, "program_arguments", initialize_runtime_arguments())


# Taken at import, before conftest's autouse fixture stands the working directory in for it.
_REAL_DEFAULT = outdir.default_output_directory


@pytest.fixture
def documents(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """The real default, with platformdirs' Documents folder standing in a temporary one."""
    monkeypatch.setattr(outdir, "default_output_directory", _REAL_DEFAULT)
    fake_documents = tmp_path / "Documents"
    monkeypatch.setattr(outdir.platformdirs, "user_documents_path", lambda: fake_documents)
    return fake_documents


def test_default_is_a_maptasker_folder_in_documents(documents: Path) -> None:
    """With nothing chosen, output goes to Documents/MapTasker, which is made on first use."""
    assert not (documents / "MapTasker").exists()

    assert outdir.output_directory() == documents / "MapTasker"
    assert (documents / "MapTasker").is_dir()
    assert outdir.output_path("report.txt") == str(documents / "MapTasker" / "report.txt")


@pytest.mark.skipif(sys.platform != "win32", reason="asks Windows itself where Documents is")
def test_windows_documents_folder_is_found() -> None:
    """On Windows the default sits in the Documents folder Windows reports, wherever it has been moved.

    Checks the real lookup (SHGetKnownFolderPath, through platformdirs) rather than a stand-in,
    and only looks: nothing is created, so running this on a real machine leaves no folder behind.
    """
    documents = _REAL_DEFAULT().parent

    assert documents == outdir.platformdirs.user_documents_path()
    assert documents.is_absolute()
    assert documents.drive, documents  # a real Windows path, with a drive letter or UNC share
    assert documents.is_dir(), documents


def test_a_chosen_folder_is_used_and_made(tmp_path: Path) -> None:
    """The setting wins over the default, and a folder that is not there yet is created."""
    chosen = tmp_path / "reports" / "nested"
    PrimeItems.program_arguments.output_directory = str(chosen)

    assert outdir.output_directory() == chosen
    assert chosen.is_dir()


def test_an_unusable_folder_falls_back_to_the_working_directory(tmp_path: Path) -> None:
    """A report the user asked for is still written, to the working directory, if the folder cannot be made."""
    blocker = tmp_path / "a_file"
    blocker.write_text("", encoding="utf-8")
    PrimeItems.program_arguments.output_directory = str(blocker / "under_a_file")

    assert outdir.output_directory() == Path.cwd()


def test_reports_are_written_to_the_output_folder(tmp_path: Path) -> None:
    """A report lands in the chosen folder, not the working directory, and its full path comes back."""
    chosen = tmp_path / "out"
    PrimeItems.program_arguments.output_directory = str(chosen)

    written = healthck.write_health_check_report([])

    assert os.path.dirname(written) == str(chosen)
    assert os.path.basename(written).startswith("MapTasker_HealthCheck_")
    assert os.path.isfile(written)
    assert not list(tmp_path.glob("MapTasker_HealthCheck_*"))


def test_normalize_makes_the_folder_absolute(tmp_path: Path) -> None:
    """A folder typed in is stored absolute, so it means the same place from any start directory."""
    folder, problem = outdir.normalize_output_directory("  relative/out  ")

    assert problem == ""
    assert folder == str((tmp_path / "relative" / "out").resolve())
    assert Path(folder).is_dir()


def test_normalize_leaves_empty_as_the_default() -> None:
    """Empty (or blank) text means the default and is stored as ""."""
    assert outdir.normalize_output_directory("   ") == ("", "")


def test_normalize_refuses_a_folder_that_cannot_be_made(tmp_path: Path) -> None:
    """The problem is reported, and no setting is offered in its place."""
    blocker = tmp_path / "a_file"
    blocker.write_text("", encoding="utf-8")

    folder, problem = outdir.normalize_output_directory(str(blocker / "under_a_file"))

    assert folder == ""
    assert "cannot be used" in problem


def test_the_setting_is_saved() -> None:
    """It is a saved setting, so it survives to the next run."""
    assert "output_directory" in ARGUMENT_NAMES


def test_outdir_on_the_command_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """-outdir sets the folder, made absolute."""
    monkeypatch.setattr(sys, "argv", ["maptasker", "-outdir", "cli_out"])

    process_extended_arguments(runtime_parser())

    assert PrimeItems.program_arguments.output_directory == str((tmp_path / "cli_out").resolve())
