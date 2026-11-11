"""The Project Dependencies window (guiwins_projdeps): the table, the graph, the detail of a chosen Project and the report.

What is decided is test_projdeps's.  What is tested here is the window over it: that every Project is a row with the
right counts, that choosing one -- in the table or by clicking its node in the graph -- shows its detail with lines that
jump into the Map, that a configuration with nothing crossing says so instead of drawing an empty graph, and that Save
Report says where the report went.  The window is the real one, on a page of NiceGUI's in-process user simulation.
"""

from __future__ import annotations

import contextlib
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from maptasker.src.core.mapjump import Target
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import sessundo
from maptasker.src.gui import guiwins_projdeps
from maptasker.src.mapops import projdeps
from nicegui import core, ui
from nicegui.testing.user import User
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

from tests.nicegui_harness import idle
from tests.test_maprefac import _load
from tests.test_projdeps import _XML, _action, _project, _task

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

_built: dict[str, Any] = {}


@pytest.fixture(autouse=True)
def _configuration() -> Any:
    """The dependency fixture loaded, with an empty undo history and nothing remembered from a test before."""
    _built.clear()
    _built["jumps"] = []
    sessundo.clear(PrimeItems)
    _load(_XML)
    yield
    sessundo.clear(PrimeItems)


def _page() -> None:
    def jump(target: Target) -> Callable[[], Any]:
        async def go() -> None:
            _built["jumps"].append(target)

        return go

    window = guiwins_projdeps.ProjectDependenciesWindow(jump, PrimeItems)
    _built["window"] = window
    window.build().open()


@contextlib.asynccontextmanager
async def _open() -> AsyncIterator[User]:
    try:
        async with user_simulation(root=_page) as user:
            await user.open("/")
            yield user
    finally:
        if core.app.is_started:
            await core.app.stop()


def _event(**fields: Any) -> Any:
    """A stand-in for the event NiceGUI hands a handler: only the fields the window reads."""
    return SimpleNamespace(**fields)


def _window() -> guiwins_projdeps.ProjectDependenciesWindow:
    return _built["window"]


def _shown(user: User) -> list[str]:
    return [element.text for element in user.find(kind=ui.label).elements]


def _rows() -> dict[str, dict[str, Any]]:
    return {row["project"]: row for row in _window().shown_rows}


@pytest.mark.asyncio
async def test_every_project_is_a_row_with_how_many_it_needs_and_is_needed_by() -> None:
    async with _open():
        rows = _rows()

        assert sorted(rows) == ["Home", "Lonely", "Media", "Utilities"]
        assert (rows["Home"]["needs"], rows["Home"]["needed_by"]) == (2, 0)
        assert (rows["Utilities"]["needs"], rows["Utilities"]["needed_by"]) == (1, 2)
        assert (rows["Lonely"]["needs"], rows["Lonely"]["needed_by"]) == (0, 0)


@pytest.mark.asyncio
async def test_the_table_says_which_projects_stand_alone_and_which_are_in_a_loop() -> None:
    async with _open():
        rows = _rows()

        assert rows["Lonely"]["status"] == "Self-contained"
        assert rows["Home"]["status"] == "Needs others"
        assert rows["Media"]["status"] == "In a loop"
        assert rows["Utilities"]["status"] == "In a loop"


@pytest.mark.asyncio
async def test_the_summary_counts_the_projects() -> None:
    async with _open() as user:
        assert "Projects: 4" in _shown(user)


@pytest.mark.asyncio
async def test_nothing_is_chosen_at_first_and_the_window_says_what_to_do() -> None:
    async with _open() as user:
        assert "Choose a Project to see what it needs and what needs it." in _shown(user)


@pytest.mark.asyncio
async def test_choosing_a_project_shows_what_it_needs_and_what_deleting_it_would_leave() -> None:
    async with _open() as user:
        _window().chose(_event(selection=[_rows()["Utilities"]]))
        shown = " ".join(_shown(user))

        assert "Used by 2 other Projects" in shown
        assert "would be left with nothing" in shown


@pytest.mark.asyncio
async def test_clicking_a_node_of_the_graph_chooses_that_project() -> None:
    async with _open() as user:
        window = _window()
        node = next(node for node, name in window.node_names.items() if name == "Home")

        window.node_clicked(_event(node_id=node))

        assert window.table.selected == [_rows()["Home"]]
        assert "Needs 2 other Projects" in " ".join(_shown(user))


@pytest.mark.asyncio
async def test_a_node_the_window_does_not_know_is_ignored() -> None:
    async with _open():
        window = _window()

        window.node_clicked(_event(node_id="nonsense"))

        assert window.table.selected == []


@pytest.mark.asyncio
async def test_a_line_of_the_detail_is_a_link_that_jumps_to_where_it_is() -> None:
    async with _open() as user:
        _window().show("Utilities")
        links = [element for element in user.find(kind=ui.link).elements if "Task 'Morning'" in element.text]

        assert links, "the user of Setup is a click"
        UserInteraction(user, set(links[:1]), None).click()
        await idle()
        assert [target.key for target in _built["jumps"]] == ["10"]


@pytest.mark.asyncio
async def test_save_report_says_where_the_report_went(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(projdeps, "write_report", lambda rows, state: "/out/MapTasker_ProjectDependencies.txt")
    async with _open() as user:
        UserInteraction(user, {b for b in user.find(kind=ui.button).elements if b.text == "Save Report"}, None).click()

        assert user.notify.contains("Report saved as")


@pytest.mark.asyncio
async def test_save_report_says_when_it_could_not(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(projdeps, "write_report", lambda rows, state: "")
    async with _open() as user:
        UserInteraction(user, {b for b in user.find(kind=ui.button).elements if b.text == "Save Report"}, None).click()

        assert user.notify.contains("could not be saved")


@pytest.mark.asyncio
async def test_a_configuration_where_nothing_crosses_says_so_and_draws_no_graph() -> None:
    _load(
        '<TaskerData sr="" dvi="1" tv="6.3.13">'
        + _project("Solo", "", "1")
        + _task("1", "Alone", _action("548", "x"))
        + "</TaskerData>",
    )
    async with _open() as user:
        assert "No Project uses anything that is in another Project." in _shown(user)
        await user.should_not_see(kind=ui.mermaid)


def _page_with_nothing_loaded() -> None:
    _built["window"] = guiwins_projdeps.build_project_dependencies_window(lambda _target: _no_jump, PrimeItems)


async def _no_jump() -> None:
    """The click a jump would be; nothing here is clicked."""


@pytest.mark.asyncio
async def test_with_nothing_loaded_there_is_no_window() -> None:
    _load('<TaskerData sr="" dvi="1" tv="6.3.13"></TaskerData>')
    try:
        async with user_simulation(root=_page_with_nothing_loaded) as user:
            await user.open("/")

            assert _built["window"] is None
            assert user.notify.contains("No XML file has been loaded")
    finally:
        if core.app.is_started:
            await core.app.stop()
