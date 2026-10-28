"""Fixtures every test gets."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from maptasker.src.core import outdir
from maptasker.src.core.primitem import PrimeItems

if TYPE_CHECKING:
    from collections.abc import Iterator

# Fixtures several modules share; see the module.
pytest_plugins = ["tests.shared_fixtures"]


_PRIME_ITEMS_BEFORE = pytest.StashKey[dict[str, object]]()


@pytest.hookimpl(wrapper=True)
def pytest_runtest_setup(item: pytest.Item) -> Iterator[None]:
    """Take a copy of PrimeItems before the first fixture of a test touches it; see pytest_runtest_teardown."""
    # A copy, since a test fills the tables in place as well as replacing them.
    item.stash[_PRIME_ITEMS_BEFORE] = copy.deepcopy(vars(PrimeItems))
    return (yield)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_teardown(item: pytest.Item, nextitem: pytest.Item | None) -> Iterator[None]:
    """Put PrimeItems back the way it was before the test, so no test depends on the one that ran before.

    PrimeItems is one object for the whole process, and most tests set some of it up and leave it.  Run in
    file order that mostly goes unnoticed; the same tests in another order -- which is what pytest-xdist makes
    of them -- find whatever an earlier one left.  Done here rather than in a fixture because it has to come
    after every fixture is undone, a test's monkeypatch included: that puts back the very objects the test
    had been filling, and no fixture can be sure of being undone last.  The rest of what a test touches is
    its own: the working directory, the environment and module attributes are monkeypatched, and a Scene
    canvas is emptied below.
    """
    result = yield
    before = item.stash.get(_PRIME_ITEMS_BEFORE, None)
    if before is not None:
        state = vars(PrimeItems)
        state.clear()
        state.update(before)
    return result


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
def _no_designer_outlives_its_test() -> Iterator[None]:
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
        canvas._ACTIVE_CANVASES.clear()
