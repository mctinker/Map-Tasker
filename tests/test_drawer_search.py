"""The right drawer's 'Find a command' box and its sections (guiwins_drawer_search, guiwins_drawers)

What is tested: how a query is matched, that typing hides what does not match and opens the sections that still hold
something, that clearing the box gives the drawer back exactly as it was (the sections the user had open, and the
buttons other code hides on purpose), that the sections are an accordion, and -- on the real window -- that every
command is in the section it was proposed to be in, once.
"""

from __future__ import annotations

import contextlib
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from maptasker.src.gui import guiwins_drawers
from maptasker.src.gui.guiwins_drawer_search import DrawerSearch, matches
from nicegui import core, ui
from nicegui.testing.user_simulation import user_simulation

from tests.test_gui_window import _open_window

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from nicegui.testing.user import User


# ##################################################################################
# Matching.
# ##################################################################################
@pytest.mark.parametrize(
    ("query", "label", "description", "expected"),
    [
        ("", "Task Flow", "", True),
        ("flow", "Task Flow", "", True),
        ("FLOW", "Task Flow", "", True),
        ("task flow", "Task Flow", "", True),
        ("flow task", "Task Flow", "", True),
        ("xrf", "Variable Xref", "", True),
        ("cmpf", "Compare Files", "", True),
        ("password", "Outbound Inventory", "Flags an action carrying a key or password.", True),
        ("password", "Task Flow", "Reads control flow.", False),
        ("flow nothing", "Task Flow", "", False),
        ("ab", "Variable Manager", "", True),
        ("zq", "Variable Manager", "", False),
        ("tfl", "Task Flow", "", True),
        ("lft", "Task Flow", "", False),
    ],
)
def test_a_query_matches_the_label_or_the_description_and_every_word_must(
    query: str, label: str, description: str, expected: bool
) -> None:
    assert matches(query, label, description) is expected


def test_a_short_word_is_not_matched_by_running_through_the_label() -> None:
    assert matches("vm", "Variable Manager") is False


# ##################################################################################
# Filtering a drawer, on a small page.
# ##################################################################################
_window = SimpleNamespace()
_nothing: list[ui.label] = []
_buttons: dict[str, ui.button] = {}


def _page() -> None:
    _window.drawer_sections = {"structure": True}
    _window.drawer_expansions = {}
    _window.drawer_searching = False
    with ui.right_drawer() as drawer:
        _window.gui_right_drawer = drawer
        _buttons.clear()
        _buttons["Get Local XML File"] = ui.button("Get Local XML File")
        for key, title, buttons in (
            ("structure", "Structure & Style", ("Task Flow", "Variable Xref")),
            ("exposure", "Exposure & Cost", ("Inbound Inventory", "Outbound Inventory")),
        ):
            with guiwins_drawers._drawer_section(_window, key, title, "history"):  # type: ignore[arg-type]
                for label in buttons:
                    with ui.button(label) as button:
                        ui.tooltip(f"Tooltip about {label.lower()} and passwords" if "bound" in label else "")
                    _buttons[label] = button
        _nothing[:] = [ui.label("No command matches.")]
        _nothing[0].visible = False
    _window.search = DrawerSearch(_window, _nothing[0])  # type: ignore[arg-type]


@contextlib.asynccontextmanager
async def _open() -> AsyncIterator[User]:
    try:
        async with user_simulation(root=_page) as user:
            await user.open("/")
            yield user
    finally:
        if core.app.is_started:
            await core.app.stop()


def _button(user: User, label: str) -> ui.button:
    return _buttons[label]


def _section(user: User, title: str) -> ui.expansion:
    (section,) = [each for each in _window.drawer_expansions.values() if each.props["label"] == title]
    return section


@pytest.mark.asyncio
async def test_typing_hides_what_does_not_match_and_opens_the_section_that_holds_it() -> None:
    async with _open() as user:
        _window.search.filter("outbound")

        assert _button(user, "Outbound Inventory").visible
        assert not _button(user, "Inbound Inventory").visible
        assert not _button(user, "Task Flow").visible
        assert not _button(user, "Get Local XML File").visible
        assert _section(user, "Exposure & Cost").value is True
        assert not _section(user, "Structure & Style").visible


@pytest.mark.asyncio
async def test_a_word_in_a_tooltip_finds_the_command() -> None:
    async with _open() as user:
        _window.search.filter("passwords")

        assert _button(user, "Outbound Inventory").visible
        assert _button(user, "Inbound Inventory").visible
        assert not _button(user, "Task Flow").visible


@pytest.mark.asyncio
async def test_a_query_that_finds_nothing_says_so() -> None:
    async with _open() as user:
        _window.search.filter("zzzzzz")

        assert _nothing[0].visible
        assert not _button(user, "Task Flow").visible
        _window.search.filter("flow")
        assert not _nothing[0].visible


@pytest.mark.asyncio
async def test_clearing_the_box_gives_the_drawer_back_as_it_was() -> None:
    async with _open() as user:
        hidden_on_purpose = _button(user, "Variable Xref")
        hidden_on_purpose.visible = False

        _window.search.filter("outbound")
        _window.search.filter("")

        assert _button(user, "Task Flow").visible
        assert _button(user, "Get Local XML File").visible
        assert not hidden_on_purpose.visible, "a button something else hides stays hidden"
        assert _section(user, "Structure & Style").value is True, "the section the user had open is open again"
        assert _section(user, "Exposure & Cost").value is False
        assert _section(user, "Exposure & Cost").visible
        assert _window.drawer_sections == {"structure": True}
        assert _window.drawer_searching is False


@pytest.mark.asyncio
async def test_a_second_query_narrows_from_what_the_drawer_was_before_not_from_the_first_query() -> None:
    async with _open() as user:
        _window.search.filter("outbound")
        _window.search.filter("flow")

        assert _button(user, "Task Flow").visible
        assert not _button(user, "Outbound Inventory").visible
        assert _section(user, "Structure & Style").value is True
        assert not _section(user, "Exposure & Cost").visible


@pytest.mark.asyncio
async def test_sections_found_by_a_search_are_all_open_at_once() -> None:
    async with _open() as user:
        _window.search.filter("inv xref")  # 'inv' is in two buttons, 'xref' in a third

        assert _window.drawer_searching is True
        _window.search.filter("o")  # a short word matches as text: every button with an 'o'
        assert _section(user, "Exposure & Cost").value is True
        assert _section(user, "Structure & Style").value is True


# ##################################################################################
# The accordion.
# ##################################################################################
@pytest.mark.asyncio
async def test_opening_a_section_folds_the_others() -> None:
    async with _open() as user:
        assert _section(user, "Structure & Style").value is True

        _section(user, "Exposure & Cost").set_value(value=True)

        assert _section(user, "Structure & Style").value is False
        assert _window.drawer_sections == {"structure": False, "exposure": True}


# ##################################################################################
# The real window.
# ##################################################################################
_PROPOSED: dict[str, tuple[str, ...]] = {
    "Structure & Style": (
        "Task Flow",
        "Variable Xref",
        "Xref Live",
        "Variable Manager",
        "Project Dependencies",
        "Naming Rules",
        "Notes & Tags",
    ),
    "Exposure & Cost": ("Inbound Inventory", "Outbound Inventory", "Battery Audit"),
    "Tasker & Phone": ("Compatibility Check", "Plugin Retirement Advisor", "New-Phone Checklist", "Missing Resources"),
    "Simulate & Test": ("What Fires When?", "Task Stepper", "Task Tests", "Live Run Monitor"),
    "Compare & History": (
        "Compare Files",
        "Changes Since...",
        "Restore From History",
        "TaskerNet Updates",
        "Trend Dashboard",
    ),
}


@pytest.mark.asyncio
@pytest.mark.usefixtures("fresh_session")
async def test_every_command_is_in_the_section_it_was_proposed_to_be_in_and_only_there() -> None:
    async with _open_window() as (user, gui):
        titles = {element.props["label"]: key for key, element in gui.drawer_expansions.items()}
        assert set(titles) == set(_PROPOSED)
        for title, labels in _PROPOSED.items():
            section = gui.drawer_expansions[titles[title]]
            inside = {element.text for element in section.descendants() if isinstance(element, ui.button)}
            assert set(labels) <= inside, (title, set(labels) - inside)
        everywhere = [
            element.text
            for section in gui.drawer_expansions.values()
            for element in section.descendants()
            if isinstance(element, ui.button)
        ]
        assert len(everywhere) == len(set(everywhere)), "a command is in two sections"
        for outside in ("Get Local XML File", "Import With Dependencies", "Map", "Clear", "Health Check"):
            assert outside not in everywhere
        await user.should_see(kind=ui.button, content="Import With Dependencies")


@pytest.mark.asyncio
@pytest.mark.usefixtures("fresh_session")
async def test_the_window_has_a_search_box_that_finds_a_command_in_a_folded_section() -> None:
    async with _open_window() as (user, gui):
        box = next(element for element in user.find(kind=ui.input).elements if "Find a command" in str(element.props))
        box.set_value("naming")

        sections = gui.drawer_expansions
        assert sections["structure"].value is True
        assert sections["exposure"].visible is False
        box.set_value("")
        assert all(section.visible for section in sections.values())
        assert not any(section.value for section in sections.values())
