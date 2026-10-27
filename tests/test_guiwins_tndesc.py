"""The TaskerNet Description editor: the button in each Add and Edit dialog, and the form it opens.

What a description is and how it is written onto an object is tndesc's, and is tested there.  Here it is the form: a
button in all six dialogs that reads Add or Edit by what the object holds, the text box with its checks and its preview,
each toolbar button writing its tags around the selection the browser reports, and Ok and Cancel -- Ok writing onto the
element, running the caller's follow-up and changing the button's label, Edit Project's reaching the live Project.

The dialogs are the real ones, over the fixture backup, on a page of NiceGUI's in-process user simulation.  The browser
is the one thing it does not have, so the selection a button is pressed over is supplied by the test.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from maptasker.src.core import tndesc
from maptasker.src.core.colrmode import set_color_mode
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import profedit, projedit, sessundo, taskedit
from maptasker.src.edit.taskedit_model import EditableTask
from maptasker.src.gui import guiwins_profedit, guiwins_project, guiwins_taskedit, guiwins_tndesc
from maptasker.src.gui.userintr import MapTaskerEventHandlers
from nicegui import ui

from tests.nicegui_harness import button, click, found, open_page, press
from tests.test_mapswap import _load
from tests.test_profedit import _XML

if TYPE_CHECKING:
    from collections.abc import Callable

    from nicegui.testing.user import User


def tool_for(key: str) -> tndesc.Tool:
    """The toolbar tool with this key."""
    return next(tool for tool in tndesc.TOOLS if tool.key == key)


ADD = "Add TaskerNet Description"
EDIT = "Edit TaskerNet Description"


@pytest.fixture(autouse=True)
def _configuration() -> None:
    """The fixture backup loaded: Projects Home and Work, Profile Triggers, Tasks Entry, Exit and Other."""
    _load(_XML)
    PrimeItems.colors_to_use = set_color_mode("light")


@pytest.fixture
def selection(monkeypatch: pytest.MonkeyPatch) -> dict[str, tuple[int, int]]:
    """The selection the 'browser' reports, and a record of where the editor asked for it to be put back."""
    state = {"asked": (0, 0), "put": (-1, -1)}

    async def selection_in(_field: ui.textarea) -> tuple[int, int]:
        return state["asked"]

    def select_in(_field: ui.textarea, start: int, end: int) -> None:
        state["put"] = (start, end)

    monkeypatch.setattr(guiwins_tndesc, "selection_in", selection_in)
    monkeypatch.setattr(guiwins_tndesc, "select_in", select_in)
    return state


def _gui() -> MagicMock:
    """The window, with the real handlers behind it: Ok goes through them, which is what is being tested."""
    window = MagicMock()
    window.state = PrimeItems
    window.indent = 4
    window.event_handlers = MapTaskerEventHandlers(window)
    return window


def _box(user: User) -> ui.textarea:
    (box,) = found(user, ui.textarea)
    return box


def _tool(user: User, key: str) -> ui.button:
    tool = tool_for(key)
    (element,) = [b for b in found(user, ui.button) if b.props.get("icon") == tool.icon]
    return element


async def _ok(user: User) -> None:
    """Press the editor's Ok: the last one on the page, since a parent dialog may have an Ok of its own."""
    await press(user, sorted((b for b in found(user, ui.button) if b.text == "Ok"), key=lambda b: b.id)[-1])


def _labels(user: User) -> list[str]:
    return [label.text for label in found(user, ui.label)]


def _preview(user: User) -> str:
    (html,) = found(user, ui.html)
    return html.content


def _open_editor(element: ET.Element, *, on_applied: Callable[[], None] | None = None) -> Callable[[], None]:
    def page() -> None:
        guiwins_tndesc.build_taskernet_description_dialog(_gui(), "Task", element, "Entry", None, on_applied)

    return page


def _task() -> ET.Element:
    return ET.fromstring("<Task><id>9</id><nme>Entry</nme><Action sr='act0'><code>1</code></Action></Task>")


# ##################################################################################
# The button each dialog grows
# ##################################################################################
def _add_project() -> Callable[[], None]:
    def page() -> None:
        created = projedit.create_new_project("", state=PrimeItems)
        assert not isinstance(created, str)
        guiwins_project.build_add_project_dialog(_gui(), created)

    return page


def _edit_project() -> Callable[[], None]:
    def page() -> None:
        edited = projedit.load_project_for_edit("Home", state=PrimeItems)
        assert edited is not None
        guiwins_project.build_edit_project_dialog(_gui(), edited)

    return page


def _edit_profile() -> Callable[[], None]:
    def page() -> None:
        edited = profedit.load_profile_for_edit("Triggers", state=PrimeItems)
        assert edited is not None
        guiwins_profedit.build_edit_profile_dialog(_gui(), edited)

    return page


def _add_profile() -> Callable[[], None]:
    def page() -> None:
        created = profedit.create_new_profile("", state=PrimeItems)
        assert not isinstance(created, str)
        guiwins_profedit.build_add_profile_dialog(_gui(), created, "Home")

    return page


def _edit_task() -> Callable[[], None]:
    def page() -> None:
        edited = taskedit.load_task_for_edit("Entry", state=PrimeItems)
        assert edited is not None
        guiwins_taskedit.build_edit_task_dialog(_gui(), edited)

    return page


def _add_task() -> Callable[[], None]:
    def page() -> None:
        created = taskedit.create_new_task("", "5", state=PrimeItems)
        assert not isinstance(created, str)
        guiwins_taskedit.build_add_task_dialog(_gui(), created, None, "Home")

    return page


_PANELS = {
    "Add Project": _add_project,
    "Edit Project": _edit_project,
    "Add Profile": _add_profile,
    "Edit Profile": _edit_profile,
    "Add Task": _add_task,
    "Edit Task": _edit_task,
}


@pytest.mark.asyncio
@pytest.mark.parametrize("panel", list(_PANELS))
async def test_every_add_and_edit_dialog_has_the_button_beside_its_properties(panel: str) -> None:
    async with open_page(_PANELS[panel]()) as user:
        names = [b.text for b in found(user, ui.button)]

    assert any(name in names for name in (ADD, EDIT)), f"{panel} has no TaskerNet Description button"
    assert any(name.endswith("Properties") for name in names)


@pytest.mark.asyncio
async def test_the_button_says_edit_for_an_object_that_already_has_a_description() -> None:
    element = _task()
    tndesc.set_description(element, "hello")

    def page() -> None:
        guiwins_tndesc.build_taskernet_description_button(_gui(), "Task", element)

    async with open_page(page) as user:
        assert [b.text for b in found(user, ui.button)] == [EDIT]


@pytest.mark.asyncio
async def test_the_button_hover_text_says_where_a_change_lands() -> None:
    def tooltip(element: ui.element) -> str:
        return " ".join(child.text for child in element.default_slot.children if isinstance(child, ui.tooltip))

    def page() -> None:
        guiwins_tndesc.build_taskernet_description_button(_gui(), "Task", _task())
        guiwins_tndesc.build_taskernet_description_button(_gui(), "Project", _task(), on_applied=lambda: None)

    async with open_page(page) as user:
        task_button, project_button = sorted(found(user, ui.button), key=lambda b: b.id)

        assert "kept when you press Ok in this window" in tooltip(task_button)
        assert "applied to the loaded backup as soon as you press Ok" in tooltip(project_button)


# ##################################################################################
# The form
# ##################################################################################
@pytest.mark.asyncio
async def test_the_box_holds_what_the_object_has_and_the_preview_shows_it_as_the_map_does() -> None:
    element = _task()
    tndesc.set_description(element, "Hello <b>there</b>")

    async with open_page(_open_editor(element)) as user:
        assert _box(user).value == "Hello <b>there</b>"
        assert "TaskerNet description:" in _preview(user)
        assert "there" in _preview(user)
        assert "No problems found in the HTML." in _labels(user)


@pytest.mark.asyncio
async def test_an_empty_box_says_nothing_has_been_written() -> None:
    async with open_page(_open_editor(_task())) as user:
        assert "Nothing written yet." in _labels(user)
        assert "Nothing to show." in _preview(user)


@pytest.mark.asyncio
async def test_typing_a_broken_tag_says_so_as_it_is_typed() -> None:
    async with open_page(_open_editor(_task())) as user:
        _box(user).set_value("<b>never closed <script>x</script>")

        text = _labels(user)
        assert "<b> is never closed." in text
        assert any(label.startswith("<script> is removed") for label in text)


@pytest.mark.asyncio
async def test_a_toolbar_button_wraps_the_selection_and_puts_the_selection_back(selection: dict) -> None:
    selection["asked"] = (5, 9)
    element = _task()
    tndesc.set_description(element, "make this loud")

    async with open_page(_open_editor(element)) as user:
        await press(user, _tool(user, "bold"))

        assert _box(user).value == "make <b>this</b> loud"
        assert selection["put"] == (8, 12)


@pytest.mark.asyncio
async def test_with_nothing_selected_the_placeholder_goes_in(selection: dict) -> None:
    async with open_page(_open_editor(_task())) as user:
        await press(user, _tool(user, "italic"))

        assert _box(user).value == "<i>italic text</i>"
        assert selection["put"] == (3, 14)


@pytest.mark.asyncio
async def test_the_heading_button_uses_the_level_chosen_beside_it(selection: dict) -> None:
    selection["asked"] = (0, 5)
    element = _task()
    tndesc.set_description(element, "Title and more")

    async with open_page(_open_editor(element)) as user:
        (levels,) = [s for s in found(user, ui.select) if "h1" in list(s.options)]
        levels.set_value("h2")
        (heading,) = [b for b in found(user, ui.button) if b.props.get("icon") == "title"]
        await press(user, heading)

        assert _box(user).value == "<h2>Title</h2> and more"


@pytest.mark.asyncio
async def test_link_and_color_use_the_address_and_color_given(selection: dict) -> None:
    selection["asked"] = (0, 4)
    element = _task()
    tndesc.set_description(element, "docs and more")

    async with open_page(_open_editor(element)) as user:
        (address,) = [i for i in found(user, ui.input) if str(i.props.get("label")).startswith("Address")]
        address.set_value("https://example.com/docs")
        await press(user, _tool(user, "link"))
        assert _box(user).value == '<a href="https://example.com/docs">docs</a> and more'

        (colors,) = [s for s in found(user, ui.select) if "red" in list(s.options)]
        colors.set_value("blue")
        selection["asked"] = (0, 0)
        await press(user, _tool(user, "color"))
        assert str(_box(user).value).startswith('<font color="blue">colored text</font>')


@pytest.mark.asyncio
async def test_add_line_breaks_turns_plain_lines_into_html_lines(selection: dict) -> None:
    element = _task()
    tndesc.set_description(element, "one\ntwo")

    async with open_page(_open_editor(element)) as user:
        await click(user, "Add Line Breaks")

        assert _box(user).value == "one<br/>\ntwo"


# ##################################################################################
# Ok, Cancel and Clear
# ##################################################################################
@pytest.mark.asyncio
async def test_ok_writes_the_description_onto_the_element_and_runs_the_callers_follow_up() -> None:
    element = _task()
    applied: list[str] = []

    async with open_page(
        _open_editor(element, on_applied=lambda: applied.append(tndesc.description_of(element)))
    ) as user:
        _box(user).set_value("Does <b>a thing</b>")
        await click(user, "Ok")

        assert tndesc.description_of(element) == "Does <b>a thing</b>"
        assert applied == ["Does <b>a thing</b>"], "the follow-up runs after the element has been written"
        assert user.notify.contains("TaskerNet description kept.")


@pytest.mark.asyncio
async def test_ok_with_html_that_does_not_check_still_keeps_it_and_says_what_is_wrong() -> None:
    element = _task()

    async with open_page(_open_editor(element)) as user:
        _box(user).set_value("<b>never closed")
        await click(user, "Ok")

        assert tndesc.description_of(element) == "<b>never closed"
        assert user.notify.contains("kept, but check its HTML")
        assert user.notify.contains("<b> is never closed.")


@pytest.mark.asyncio
async def test_cancel_writes_nothing() -> None:
    element = _task()
    before = ET.tostring(element)

    async with open_page(_open_editor(element)) as user:
        _box(user).set_value("typed and abandoned")
        await click(user, "Cancel")

    assert ET.tostring(element) == before


@pytest.mark.asyncio
async def test_clear_then_ok_takes_the_description_off_the_object() -> None:
    element = _task()
    before = ET.tostring(element)
    tndesc.set_description(element, "to be removed")

    async with open_page(_open_editor(element)) as user:
        await click(user, "Clear")
        assert _box(user).value == ""
        await click(user, "Ok")

    assert ET.tostring(element) == before


@pytest.mark.asyncio
async def test_clear_alone_changes_nothing_until_ok() -> None:
    element = _task()
    tndesc.set_description(element, "still here")

    async with open_page(_open_editor(element)) as user:
        await click(user, "Clear")

    assert tndesc.description_of(element) == "still here"


@pytest.mark.asyncio
async def test_the_dialogs_own_button_changes_its_label_once_a_description_is_kept() -> None:
    element = _task()

    def page() -> None:
        guiwins_tndesc.build_taskernet_description_button(_gui(), "Task", element, "Entry")

    async with open_page(page) as user:
        await click(user, ADD)
        _box(user).set_value("hello")
        await click(user, "Ok")

        assert button(user, EDIT)
        assert not [b for b in found(user, ui.button) if b.text == ADD]


# ##################################################################################
# Through the real dialogs
# ##################################################################################
@pytest.mark.asyncio
async def test_a_description_added_in_add_task_is_on_the_new_task() -> None:
    holder: dict[str, EditableTask] = {}

    def page() -> None:
        created = taskedit.create_new_task("", "5", state=PrimeItems)
        assert not isinstance(created, str)
        holder["task"] = created
        guiwins_taskedit.build_add_task_dialog(_gui(), created, None, "Home")

    async with open_page(page) as user:
        await click(user, ADD)
        _box(user).set_value("Made in Add Task")
        await _ok(user)

    assert tndesc.description_of(holder["task"].task_element) == "Made in Add Task"


@pytest.mark.asyncio
async def test_edit_project_carries_the_description_to_the_live_project_and_undo_takes_it_back() -> None:
    async with open_page(_edit_project()) as user:
        await click(user, ADD)
        _box(user).set_value("About Home")
        await click(user, "Ok")

    live = projedit.resolve_project_by_name("Home", state=PrimeItems)
    assert live is not None
    assert tndesc.description_of(live) == "About Home"

    sessundo.undo(state=PrimeItems)
    live = projedit.resolve_project_by_name("Home", state=PrimeItems)
    assert live is not None
    assert tndesc.description_of(live) == ""


@pytest.mark.asyncio
async def test_the_properties_button_is_still_there_and_still_says_properties() -> None:
    def page() -> None:
        created = taskedit.create_new_task("", "5", state=PrimeItems)
        assert not isinstance(created, str)
        guiwins_taskedit.build_add_task_dialog(_gui(), created, None, "Home")

    async with open_page(page) as user:
        assert button(user, "Add Properties")
