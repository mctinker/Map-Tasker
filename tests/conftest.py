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

    guiwins_canvas._ACTIVE_CANVASES maps each designer to its handlers and is never emptied, and a
    handler is a bound method -- so every designer a test opened, with its whole page of elements, stayed
    alive for the rest of the run.  Fifty-eight designer tests left two million objects behind, and
    pytest collects garbage around every test: each of the thousands after them paid for the larger
    heap, which is why unrelated tests ran several times slower here than on their own.
    """
    yield
    canvas = sys.modules.get("maptasker.src.gui.guiwins_canvas")  # Not imported, so nothing to empty.
    if canvas is not None:
        canvas._ACTIVE_CANVASES.clear()  # noqa: SLF001
