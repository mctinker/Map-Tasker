"""The Trend Dashboard dialog: the verdict, the cards, the table, and the Projects that moved most.

What is measured is test_trend's.  What is tested here is the dialog around it: that it starts on the file that is open,
that it says which way things went and in the right colour, that a Project can be looked at on its own, that a Project
that was not always there is shown as such, and that an empty history gets a message and no dialog.  sparkline_svg is a
pure function and is tested as one.  The dialog is the real one, on a page of NiceGUI's in-process user simulation.
"""

from __future__ import annotations

import asyncio
import contextlib
import re
from typing import TYPE_CHECKING

import pytest
from maptasker.src.core import timeline
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.gui import guiwins_trend
from nicegui import core, ui
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

pytestmark = pytest.mark.usefixtures("_runtime")
from tests.test_trend import _at, _snapshot, config, flash, perform

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable
    from pathlib import Path

    from nicegui.testing.user import User

_built: dict = {}


@pytest.fixture(autouse=True)
def _history(tmp_path: Path, _runtime: None):
    """A history folder of the test's own, after _runtime's own load has been recorded elsewhere."""
    _built.clear()
    timeline.use_history_folder(tmp_path / "history")
    yield
    timeline.use_history_folder(None)


def _page() -> None:
    _built["dialog"] = guiwins_trend.build_trend_dialog(PrimeItems)
    if _built["dialog"] is not None:
        _built["dialog"].open()


@contextlib.asynccontextmanager
async def _open() -> AsyncIterator[User]:
    try:
        async with user_simulation(root=_page) as user:
            await user.open("/")
            yield user
    finally:
        if core.app.is_started:
            await core.app.stop()


async def _see(user: User, text: str) -> None:
    """Wait for `text` to be on the page.  The dialog measures on worker threads, which a slow machine takes a while over.

    should_see() gives up after three tenths of a second by default; this goes on for up to thirty, but returns the
    moment the text is there, so a fast machine waits no longer than before.
    """
    await user.should_see(text, retries=300)


def _labels(user: User) -> list[str]:
    return [element.text for element in user.find(kind=ui.label).elements]


def _select(user: User, label: str) -> ui.select:
    (element,) = [e for e in user.find(kind=ui.select).elements if e.props.get("label", "") == label]
    return element


async def _until(condition: Callable[[], object]) -> None:
    for _ in range(60):
        if condition():
            return
        await asyncio.sleep(0.05)
    msg = "it did not happen"
    raise AssertionError(msg)


def _keep(tmp_path: Path, *versions: tuple[int, str]) -> None:
    """Keep one snapshot per version: (day, configuration XML).  All of one family, 'backup.xml'."""
    for day, xml in versions:
        _snapshot(tmp_path, f"backup_2026090{day}_010101.xml", xml, _at(day))


_CLEAN = config(Home={"A": (flash("a"),)}, Work={"B": (flash("b"),)})
_MESSY = config(Home={"A": (perform("Gone"), perform("Gone2"))}, Work={"B": (flash("b"),)})


# ##################################################################################
# The sparkline.
# ##################################################################################


def test_a_sparkline_draws_a_line_through_the_values_and_marks_the_last() -> None:
    svg = guiwins_trend.sparkline_svg([1, 3, 2, 5], "#123456")

    assert svg.startswith("<svg")
    assert svg.count("<polyline") == 1
    assert svg.count("<circle") == 1
    assert 'stroke="#123456"' in svg
    points = re.search(r'points="([^"]+)"', svg)[1].split()
    assert len(points) == 4
    ys = [float(point.split(",")[1]) for point in points]
    assert ys[3] < ys[0], "a higher value is drawn higher up the picture, which is a smaller y"


def test_a_flat_series_is_a_flat_line_in_the_middle() -> None:
    svg = guiwins_trend.sparkline_svg([4, 4, 4])

    ys = {point.split(",")[1] for point in re.search(r'points="([^"]+)"', svg)[1].split()}
    assert len(ys) == 1


def test_a_gap_where_a_project_did_not_exist_splits_the_line() -> None:
    svg = guiwins_trend.sparkline_svg([1, 2, None, None, 3, 4])

    assert svg.count("<polyline") == 2


def test_a_single_value_is_a_dot_and_no_values_is_an_empty_picture() -> None:
    assert "<polyline" not in guiwins_trend.sparkline_svg([7])
    assert guiwins_trend.sparkline_svg([7]).count("<circle") == 1
    assert "<circle" not in guiwins_trend.sparkline_svg([None, None])


# ##################################################################################
# The dialog.
# ##################################################################################


@pytest.mark.asyncio
async def test_with_no_history_there_is_no_dialog_and_a_message() -> None:
    async with _open() as user:
        assert _built["dialog"] is None
        assert user.notify.contains("No configuration history has been recorded yet")


@pytest.mark.asyncio
async def test_it_follows_the_file_that_is_open_and_says_which_way_things_went(tmp_path: Path) -> None:
    _keep(tmp_path, (1, _CLEAN), (2, _MESSY))
    PrimeItems.file_to_get = str(tmp_path / "backup_20260902_010101.xml")
    async with _open() as user:
        await _see(user, "2 configurations measured.")

        assert _select(user, "Follow this file").value == "backup.xml"
        await _see(user, "Messier")
        assert any("errors +" in label for label in _labels(user))


@pytest.mark.asyncio
async def test_getting_better_is_said_to_be_healthier(tmp_path: Path) -> None:
    _keep(tmp_path, (1, _MESSY), (2, _CLEAN))
    async with _open() as user:
        await _see(user, "2 configurations measured.")

        await _see(user, "Healthier")


@pytest.mark.asyncio
async def test_with_one_snapshot_it_says_a_trend_needs_two(tmp_path: Path) -> None:
    _keep(tmp_path, (1, _CLEAN))
    async with _open() as user:
        await _see(user, "Not enough history")


@pytest.mark.asyncio
async def test_the_table_has_a_row_for_each_snapshot_newest_first(tmp_path: Path) -> None:
    _keep(tmp_path, (1, _CLEAN), (2, _MESSY), (3, _CLEAN))
    async with _open() as user:
        await _see(user, "3 configurations measured.")

        # In the order they are drawn down the page, which is the tree's order -- not the order widgets were made in.
        (area,) = [e for e in user.find(kind=ui.scroll_area).elements if "h-[210px]" in e.classes]
        dates = [
            e.text
            for e in area.descendants()
            if isinstance(e, ui.label) and re.match(r"\d{2}-Sep-2026 \d{2}:\d{2}$", e.text)
        ]
        # The snapshots are made at 12:00 UTC, which is a different clock time in each machine's own time zone.
        assert dates == [f"{_at(day):%d-%b-%Y %H:%M}" for day in (3, 2, 1)]


@pytest.mark.asyncio
async def test_a_project_can_be_looked_at_on_its_own(tmp_path: Path) -> None:
    _keep(tmp_path, (1, _CLEAN), (2, _MESSY))
    async with _open() as user:
        await _see(user, "2 configurations measured.")
        scope = _select(user, "Look at")
        assert set(scope.options) >= {"Home", "Work"}

        scope.set_value("Work")

        await _see(user, "Since it first appeared")
        await _see(user, "none of the numbers changed")


@pytest.mark.asyncio
async def test_a_project_that_was_not_always_there_says_so(tmp_path: Path) -> None:
    _keep(
        tmp_path, (1, config(Old={"A": (flash("a"),)})), (2, config(Old={"A": (flash("a"),)}, New={"B": (flash("b"),)}))
    )
    async with _open() as user:
        await _see(user, "2 configurations measured.")

        _select(user, "Look at").set_value("New")

        await _see(user, "(not in this configuration)")


@pytest.mark.asyncio
async def test_the_projects_that_moved_most_are_listed_and_one_click_looks_at_it(tmp_path: Path) -> None:
    _keep(tmp_path, (1, _CLEAN), (2, _MESSY))
    async with _open() as user:
        await _see(user, "2 configurations measured.")
        await _see(user, "Messier")

        link = next(element for element in user.find(kind=ui.link).elements if element.text == "Home")
        UserInteraction(user, {link}, None).click()

        assert _select(user, "Look at").value == "Home"


@pytest.mark.asyncio
async def test_a_second_look_reads_the_kept_figures_and_does_not_measure_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _keep(tmp_path, (1, _CLEAN), (2, _MESSY))
    async with _open() as user:
        await _see(user, "2 configurations measured.")

    from maptasker.src.analysis import timecomp

    monkeypatch.setattr(timecomp, "configuration_of", lambda *_a, **_k: pytest.fail("measured again"))
    async with _open() as user:
        await _see(user, "2 configurations measured.")


@pytest.mark.asyncio
async def test_copy_puts_the_text_report_on_the_clipboard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _keep(tmp_path, (1, _CLEAN), (2, _MESSY))
    copied: list[str] = []
    async with _open() as user:
        await _see(user, "2 configurations measured.")
        monkeypatch.setattr(guiwins_trend.ui.clipboard, "write", copied.append)
        button = next(b for b in user.find(kind=ui.button).elements if b.text == "Copy As Text")

        UserInteraction(user, {button}, None).click()

        assert copied
        assert copied[0].startswith("MapTasker trend: The whole configuration")
