"""Fixtures every test gets."""

from __future__ import annotations

from pathlib import Path

import pytest
from maptasker.src import outdir


@pytest.fixture(autouse=True)
def _output_folder_is_the_working_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    """Send reports, exports and view files to the working directory, not ~/Documents/MapTasker.

    The real default is a folder in the user's Documents, and a test suite has no business
    writing there.  The working directory is what tests have always isolated with
    monkeypatch.chdir(tmp_path), so pointing the default at it keeps every one of those tests
    meaning what it did.  Looked up at call time, so a chdir after this fixture still counts.
    Tests of outdir's own default undo this with monkeypatch.undo() or by patching platformdirs.
    """
    monkeypatch.setattr(outdir, "default_output_directory", Path.cwd)
