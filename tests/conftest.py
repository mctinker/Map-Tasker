"""Fixtures every test gets."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from maptasker.src.core import outdir


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


@pytest.fixture(autouse=True)
def _no_designer_outlives_its_test() -> None:
    """Empty the table of live Scene canvases after every test.

    A designer unregisters itself when it is collected, but a test's NiceGUI client is kept by the user
    simulation long after the test, and with it every designer the test opened and its whole page of
    elements.  Fifty-eight designer tests left two million objects behind, and pytest collects garbage
    around every test: each of the thousands after them paid for the larger heap, which is why unrelated
    tests ran several times slower here than on their own.  Emptying the table here keeps one test's
    designer from being found by the next.
    """
    yield
    canvas = sys.modules.get("maptasker.src.gui.guiwins_canvas")  # Not imported, so nothing to empty.
    if canvas is not None:
        canvas._ACTIVE_CANVASES.clear()  # noqa: SLF001
