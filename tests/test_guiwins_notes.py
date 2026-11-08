"""MapTasker Notes & Tags window (guiwins_notes) Unit Tests

objnotes is tested on its own; what is tested here is the window over it: that the table shows the notes and says which
are not in the open file, that a tag limits it, that adding, changing, moving and deleting a note keep the file
right, that the switch is kept, and that Show In Map is given the right place to go.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any, cast

import pytest
from maptasker.src.core import objnotes
from maptasker.src.core.mapjump import PROFILE, PROJECT, TASK, Target
from maptasker.src.core.objnotes import Note, NoteBook
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.gui import guiwins_notes
from nicegui import core, ui
from nicegui.testing.user import User
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

pytestmark = pytest.mark.usefixtures("_runtime")

# The configuration the runtime loads has Projects Pack and Other, Profiles Dawn and Dusk, and Tasks Morning, Helper and
# Elsewhere -- see shared_fixtures.
_built: dict[str, Any] = {}


def _save_notes() -> None:
    book = NoteBook()
    book.put(Note(PROJECT, "Pack", "Dad's phone only", ["family", "android-15"]))
    book.put(Note(PROFILE, "Dawn", "", ["flaky"]))
    book.put(Note(TASK, "Morning", "Needs a rewrite", ["needs-rewrite", "flaky"]))
    book.put(Note(TASK, "Gone Since", "Was renamed", ["family"]))
    objnotes.save(book)


@pytest.fixture(autouse=True)
def _notes() -> None:
    _save_notes()
    _built.clear()
    _built["jumps"] = []


def _page() -> None:
    def jump(target: Target) -> Callable[[], Any]:
        async def go() -> None:
            _built["jumps"].append(target)

        return go

    window = guiwins_notes.NotesWindow(jump, PrimeItems)
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


def _window() -> guiwins_notes.NotesWindow:
    window = _built["window"]
    assert isinstance(window, guiwins_notes.NotesWindow)
    return window


def _buttons(user: User, label: str) -> list[ui.button]:
    return [element for element in user.find(kind=ui.button).elements if element.text == label]


def _newest(user: User, label: str) -> ui.button:
    """The enabled button of this name made last: a dialog's, not the window's own of the same name."""
    return max((b for b in _buttons(user, label) if b.enabled), key=lambda button: button.id)


def _press(user: User, button: ui.button) -> None:
    UserInteraction(user, {button}, None).click()


def _tags_field(user: User) -> ui.input:
    """The dialog's tags field: the newest input that is not the note's text area, which is an input of a kind."""
    inputs = [element for element in user.find(kind=ui.input).elements if not isinstance(element, ui.textarea)]
    return max(inputs, key=lambda element: element.id)


def _labels(user: User) -> list[str]:
    return [element.text for element in user.find(kind=ui.label).elements]


def _rows() -> dict[str, dict[str, Any]]:
    return {row["name"]: row for row in _window().shown_rows}


class _Closable:
    """What the dialog is to the code that saves: something that can be closed."""

    def close(self) -> None:
        pass


def _keep(existing: Note | None, kind: str, name: str, tags: str, text: str) -> None:
    """Save as the dialog's Save button does, from inside the window's own page as a click would be."""
    window = _window()
    with window.dialog:
        window._keep(cast("ui.dialog", _Closable()), existing, kind, name, tags, text)


def _file_notes() -> dict[tuple[str, str], Note]:
    return objnotes.load().notes


async def _until(condition: Callable[[], object]) -> None:
    for _ in range(60):
        if condition():
            return
        await asyncio.sleep(0.05)
    msg = "it did not happen"
    raise AssertionError(msg)


# ##################################################################################
# The window
# ##################################################################################
@pytest.mark.asyncio
async def test_the_window_lists_every_note_with_its_object_and_tags() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        rows = _rows()

    assert set(rows) == {"Pack", "Dawn", "Morning", "Gone Since"}
    assert rows["Pack"]["kind"] == "Project"
    assert rows["Pack"]["tags"] == "#family #android-15"
    assert rows["Pack"]["note"] == "Dad's phone only"
    assert (rows["Dawn"]["kind"], rows["Dawn"]["note"]) == ("Profile", "")
    assert rows["Morning"]["kind"] == "Task"


@pytest.mark.asyncio
async def test_the_summary_counts_the_notes_and_the_tags() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        summary = next(text for text in _labels(user) if text.startswith("Note:"))

    assert summary == "Note: 4    Tags: 4"


@pytest.mark.asyncio
async def test_a_note_on_an_object_that_is_not_in_the_open_file_says_so() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        rows = _rows()

    assert rows["Gone Since"]["status"] == "Not in this file"
    assert rows["Morning"]["status"] == ""
    assert rows["Pack"]["status"] == ""
    assert rows["Dawn"]["status"] == ""


@pytest.mark.asyncio
async def test_with_no_file_open_no_note_is_said_to_be_missing_from_it() -> None:
    PrimeItems.tasker_root_elements = {}

    async with _open() as user:
        await user.should_see("Notes & Tags")
        rows = _rows()

    assert set(rows) == {"Pack", "Dawn", "Morning", "Gone Since"}
    assert {row["status"] for row in rows.values()} == {""}


@pytest.mark.asyncio
async def test_with_no_notes_the_window_is_empty_and_still_opens(tmp_path: object) -> None:
    objnotes.save(NoteBook())

    async with _open() as user:
        await user.should_see("Notes & Tags")

    assert _window().shown_rows == []
    assert _window().tag_row.default_slot.children == []


@pytest.mark.asyncio
async def test_a_file_that_cannot_be_read_is_said_to_be_and_the_window_still_opens() -> None:
    with open(objnotes.book_path(), "w", encoding="utf-8") as handle:
        handle.write("{ not json")

    async with _open() as user:
        await user.should_see("The notes file could not be read.")

    assert _window().shown_rows == []


# ##################################################################################
# The filter
# ##################################################################################
@pytest.mark.asyncio
async def test_a_tag_limits_the_table_to_the_objects_that_carry_it() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        _window().limit_to("flaky")
        shown = set(_rows())

    assert shown == {"Dawn", "Morning"}


@pytest.mark.asyncio
async def test_two_tags_limit_it_to_the_objects_that_carry_both() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        _window().limit_to("flaky")
        _window().limit_to("needs-rewrite")
        shown = set(_rows())

    assert shown == {"Morning"}


@pytest.mark.asyncio
async def test_pressing_a_tag_in_force_takes_it_off_and_show_all_takes_them_all_off() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        _window().limit_to("flaky")
        _window().limit_to("flaky")
        after_toggle = set(_rows())
        _window().limit_to("family")
        _window().limit_to("android-15")
        limited = set(_rows())
        _window().limit_to(None)
        after_show_all = set(_rows())

    assert after_toggle == {"Pack", "Dawn", "Morning", "Gone Since"}
    assert limited == {"Pack"}
    assert after_show_all == {"Pack", "Dawn", "Morning", "Gone Since"}
    assert _window().limit == set()


@pytest.mark.asyncio
async def test_each_tag_in_use_has_a_button_with_its_count() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        labels = [button.text for button in user.find(kind=ui.button).elements]

    assert "#family  (2)" in labels
    assert "#flaky  (2)" in labels
    assert "#android-15  (1)" in labels
    assert "#needs-rewrite  (1)" in labels
    assert "Show All" in labels


@pytest.mark.asyncio
async def test_a_tag_that_no_note_carries_any_more_stops_limiting_the_table() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        _window().limit_to("android-15")
        _window().book.remove(PROJECT, "Pack")
        _window().refresh()
        shown = set(_rows())

    assert _window().limit == set()
    assert shown == {"Dawn", "Morning", "Gone Since"}


# ##################################################################################
# The buttons follow what is ticked
# ##################################################################################
def _tick(*names: str) -> None:
    window = _window()
    window.choose_many([note for note in window.book.notes.values() if note.name in names])


@pytest.mark.asyncio
async def test_with_nothing_ticked_only_add_is_available() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        _tick()
        enabled = {key: button.enabled for key, button in _window().buttons.items()}

    assert enabled == {"add": True, "edit": False, "delete": False, "show": False}


@pytest.mark.asyncio
async def test_one_note_ticked_can_be_edited_deleted_and_shown() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        _tick("Morning")
        enabled = {key: button.enabled for key, button in _window().buttons.items()}

    assert enabled == {"add": True, "edit": True, "delete": True, "show": True}


@pytest.mark.asyncio
async def test_several_ticked_can_only_be_deleted() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        _tick("Morning", "Dawn")
        enabled = {key: button.enabled for key, button in _window().buttons.items()}

    assert enabled == {"add": True, "edit": False, "delete": True, "show": False}


@pytest.mark.asyncio
async def test_a_note_on_an_object_not_in_the_file_cannot_be_shown_in_the_map() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        _tick("Gone Since")
        enabled = {key: button.enabled for key, button in _window().buttons.items()}

    assert enabled["show"] is False
    assert enabled["edit"] is True  # It can still be moved to the object it was renamed to.


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Pack", Target(PROJECT, "Pack", "Pack")),
        ("Dawn", Target(PROFILE, "100", "Dawn")),
        ("Morning", Target(TASK, "20", "Morning")),
    ],
)
async def test_show_in_map_goes_to_the_object_by_its_id(name: str, expected: Target) -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        _tick(name)
        await _window().show()

    assert _built["jumps"] == [expected]


@pytest.mark.asyncio
async def test_show_in_map_with_nothing_or_several_ticked_goes_nowhere() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        _tick()
        await _window().show()
        _tick("Pack", "Dawn")
        await _window().show()

    assert _built["jumps"] == []


# ##################################################################################
# Adding, changing, moving and deleting
# ##################################################################################
@pytest.mark.asyncio
async def test_a_new_note_is_kept_in_the_file_and_shown_in_the_table() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        _keep(None, TASK, "Helper", "#Slow, slow  retry", "Runs for ages")
        await user.should_see("Saved.")

    assert _file_notes()[(TASK, "Helper")].text == "Runs for ages"
    assert _file_notes()[(TASK, "Helper")].tags == ["slow", "retry"]
    assert "Helper" in _rows()
    assert len(_file_notes()) == 5


@pytest.mark.asyncio
async def test_a_note_needs_an_object() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        _keep(None, TASK, "   ", "x", "text")
        await user.should_see("Choose the object this note is on.")

    assert len(_file_notes()) == 4


@pytest.mark.asyncio
async def test_a_note_cannot_be_put_on_the_name_made_up_for_an_unnamed_task() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        _keep(None, TASK, "Flash Text=hi (Unnamed)", "x", "text")
        await user.should_see("An object with no name cannot carry a note.")

    assert len(_file_notes()) == 4


@pytest.mark.asyncio
async def test_a_note_that_cannot_be_kept_leaves_the_one_it_was_moving_from_where_it_was() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        existing = _window().book.get(TASK, "Gone Since")
        _keep(existing, TASK, "Flash Text=hi (Unnamed)", "family", "Was renamed")
        await user.should_see("An object with no name cannot carry a note.")

    assert _file_notes()[(TASK, "Gone Since")].text == "Was renamed"


@pytest.mark.asyncio
async def test_a_note_cannot_be_put_on_an_object_that_already_has_one() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        _keep(None, TASK, "Morning", "other", "A second note")
        await user.should_see("That object already has a note.  Edit that one instead.")

    assert _file_notes()[(TASK, "Morning")].text == "Needs a rewrite"


@pytest.mark.asyncio
async def test_changing_a_note_keeps_it_on_the_same_object() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        existing = _window().book.get(TASK, "Morning")
        _keep(existing, TASK, "Morning", "rewritten", "Rewritten at last")
        await user.should_see("Saved.")

    note = _file_notes()[(TASK, "Morning")]
    assert (note.text, note.tags) == ("Rewritten at last", ["rewritten"])
    assert len(_file_notes()) == 4


@pytest.mark.asyncio
async def test_a_note_is_moved_to_the_object_it_was_renamed_to() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        existing = _window().book.get(TASK, "Gone Since")
        _keep(existing, TASK, "Helper", "family", "Was renamed")
        await user.should_see("Saved.")
        rows = _rows()

    assert (TASK, "Gone Since") not in _file_notes()
    assert _file_notes()[(TASK, "Helper")].text == "Was renamed"
    assert rows["Helper"]["status"] == ""  # And Helper is in the file.


@pytest.mark.asyncio
async def test_a_note_can_be_moved_to_another_kind_of_object() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        existing = _window().book.get(TASK, "Gone Since")
        _keep(existing, PROFILE, "Dusk", "family", "Was renamed")
        await user.should_see("Saved.")

    assert (TASK, "Gone Since") not in _file_notes()
    assert _file_notes()[(PROFILE, "Dusk")].text == "Was renamed"


@pytest.mark.asyncio
async def test_saving_a_note_with_nothing_in_it_takes_the_note_away() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        existing = _window().book.get(TASK, "Morning")
        _keep(existing, TASK, "Morning", "", "")
        await user.should_see("Saved.")

    assert (TASK, "Morning") not in _file_notes()


@pytest.mark.asyncio
async def test_the_add_dialog_offers_the_names_of_the_open_file_by_kind() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        _press(user, _newest(user, "Add"))
        await user.should_see("Separate tags with spaces or commas.")
        selects = user.find(kind=ui.select).elements
        kind, name = sorted(selects, key=lambda element: element.id)[-2:]
        offered_tasks = set(name.options)
        kind.set_value(PROFILE)
        await _until(lambda: set(name.options) == {"Dawn", "Dusk"})
        offered_profiles = set(name.options)
        kind.set_value(PROJECT)
        await _until(lambda: set(name.options) == {"Pack", "Other"})

    assert offered_tasks >= {"Morning", "Helper", "Elsewhere"}
    assert offered_profiles == {"Dawn", "Dusk"}


@pytest.mark.asyncio
async def test_the_add_dialog_saves_what_was_typed() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        _press(user, _newest(user, "Add"))
        await user.should_see("Separate tags with spaces or commas.")
        ordered = sorted(user.find(kind=ui.select).elements, key=lambda element: element.id)
        kind, name = ordered[-2:]
        kind.set_value(TASK)
        name.set_value("Helper")
        tags = _tags_field(user)
        tags.set_value("#slow retry")
        text = max(user.find(kind=ui.textarea).elements, key=lambda element: element.id)
        text.set_value("Runs for ages")
        _press(user, _newest(user, "Save"))
        await user.should_see("Saved.")

    assert _file_notes()[(TASK, "Helper")].tags == ["slow", "retry"]
    assert _file_notes()[(TASK, "Helper")].text == "Runs for ages"


@pytest.mark.asyncio
async def test_editing_a_note_opens_the_dialog_with_it_filled_in() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        _tick("Morning")
        _press(user, _window().buttons["edit"])
        await user.should_see("Separate tags with spaces or commas.")
        text = max(user.find(kind=ui.textarea).elements, key=lambda element: element.id)
        tags = _tags_field(user)

        assert text.value == "Needs a rewrite"
        assert tags.value == "needs-rewrite flaky"


@pytest.mark.asyncio
async def test_a_tag_button_in_the_dialog_adds_that_tag_once() -> None:
    assert guiwins_notes.NotesWindow._with_tag("a b", "c") == "a b c"
    assert guiwins_notes.NotesWindow._with_tag("a, #b", "b") == "a b"
    assert guiwins_notes.NotesWindow._with_tag("", "x") == "x"


@pytest.mark.asyncio
async def test_deleting_asks_first_and_then_takes_the_chosen_notes_away() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        _tick("Morning", "Dawn")
        _press(user, _window().buttons["delete"])
        await user.should_see("Delete the chosen notes?")
        assert len(_file_notes()) == 4  # Nothing yet.
        _press(user, _newest(user, "Delete"))
        await _until(lambda: len(_file_notes()) == 2)

    assert set(_rows()) == {"Pack", "Gone Since"}


@pytest.mark.asyncio
async def test_cancelling_the_delete_keeps_every_note() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        _tick("Morning")
        _press(user, _window().buttons["delete"])
        await user.should_see("Delete the chosen notes?")
        _press(user, _newest(user, "Cancel"))
        await asyncio.sleep(0.2)

    assert len(_file_notes()) == 4


@pytest.mark.asyncio
async def test_nothing_ticked_deletes_nothing() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        _tick()
        _press(user, _window().buttons["delete"])
        await asyncio.sleep(0.1)

    assert len(_file_notes()) == 4


# ##################################################################################
# The switch
# ##################################################################################
@pytest.mark.asyncio
async def test_the_switch_is_on_when_the_notes_are_shown_and_is_kept_when_it_is_turned_off() -> None:
    async with _open() as user:
        await user.should_see("Notes & Tags")
        switch = user.find(kind=ui.switch).elements.pop()
        was_on = switch.value
        switch.set_value(False)
        await _until(lambda: not objnotes.load().show_in_map)

    assert was_on is True
    assert len(_file_notes()) == 4  # Hidden, not deleted.


@pytest.mark.asyncio
async def test_a_switch_that_was_left_off_comes_back_off() -> None:
    book = objnotes.load()
    book.show_in_map = False
    objnotes.save(book)

    async with _open() as user:
        await user.should_see("Notes & Tags")
        switch = user.find(kind=ui.switch).elements.pop()

    assert switch.value is False


@pytest.mark.asyncio
async def test_what_the_window_changes_is_read_again_by_the_next_build() -> None:
    PrimeItems.object_notes = NoteBook()  # What an earlier build held.

    async with _open() as user:
        await user.should_see("Notes & Tags")
        _keep(None, TASK, "Helper", "x", "y")
        await user.should_see("Saved.")

    assert PrimeItems.object_notes is None
