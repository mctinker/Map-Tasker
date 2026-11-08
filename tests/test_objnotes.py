"""MapTasker notes and tags (objnotes) Unit Tests

What a tag is, what a note is and when it is not one, how the book is found, filtered and counted, and what is kept
in the file: written whole or not at all, read back as it was, and never lost to a file that could not be read.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import pytest
from maptasker.src.core import objnotes
from maptasker.src.core.mapjump import PROFILE, PROJECT, SCENE, TASK
from maptasker.src.core.objnotes import Note, NoteBook
from maptasker.src.core.sysconst import NOTES_FILE

from tests.doubles import fake_state

if TYPE_CHECKING:
    from pathlib import Path

    from maptasker.src.core.primitem import RunState


# conftest points every test's notes somewhere of their own; this is the function it replaces, taken before it does.
_REAL_BOOK_PATH = objnotes.book_path


def _book() -> NoteBook:
    book = NoteBook()
    book.put(Note(PROJECT, "Home", "Dad's phone only", ["family", "android-15"]))
    book.put(Note(PROFILE, "Wake Up", "", ["flaky"]))
    book.put(Note(TASK, "Backup", "Needs a rewrite", ["needs-rewrite", "flaky"]))
    book.put(Note(TASK, "Alarm", "Too loud", ["family"]))
    return book


# ##################################################################################
# Tags
# ##################################################################################
@pytest.mark.parametrize(
    ("raw", "kept"),
    [
        ("#Broken", "broken"),
        ("  Needs Rewrite  ", "needs-rewrite"),
        ("##double", "double"),
        ("android-15", "android-15"),
        ("#", ""),
        ("   ", ""),
        ("-edge-", "edge"),
    ],
)
def test_a_tag_is_kept_lower_case_without_its_hash_and_with_hyphens_for_blanks(raw: str, kept: str) -> None:
    assert objnotes.clean_tag(raw) == kept


def test_a_tag_is_cut_to_its_longest() -> None:
    assert len(objnotes.clean_tag("x" * 100)) == objnotes.MAX_TAG_LENGTH


def test_typed_tags_are_split_at_commas_semicolons_and_blanks() -> None:
    assert objnotes.parse_tags("#broken #android-15, flaky;needs-rewrite") == [
        "broken",
        "android-15",
        "flaky",
        "needs-rewrite",
    ]


def test_each_tag_is_kept_once_in_the_order_given() -> None:
    assert objnotes.parse_tags("b a B a #b c") == ["b", "a", "c"]
    assert objnotes.parse_tags(["Z", "y", "z"]) == ["z", "y"]


def test_no_more_than_the_most_tags_are_kept() -> None:
    assert len(objnotes.parse_tags([f"tag{number}" for number in range(100)])) == objnotes.MAX_TAGS


def test_a_note_writes_its_tags_with_hashes() -> None:
    assert Note(TASK, "A", tags=["x", "y-z"]).hashtags == "#x #y-z"
    assert Note(TASK, "A").hashtags == ""


# ##################################################################################
# A note, and when it is not one
# ##################################################################################
def test_a_note_is_put_on_an_object_and_found_again() -> None:
    book = NoteBook()

    kept = book.put(Note(TASK, "  Backup ", "  Slow  ", ["#Slow", "slow"]))

    note = book.get(TASK, "Backup")
    assert kept
    assert note is not None
    assert (note.text, note.tags, note.name) == ("Slow", ["slow"], "Backup")
    assert note.updated  # Stamped by the book, so every way in comes out alike.
    assert book.get(PROFILE, "Backup") is None  # Another kind of object of the same name is another object.


def test_putting_a_note_again_replaces_the_one_there() -> None:
    book = NoteBook()
    book.put(Note(TASK, "Backup", "first", ["a"]))

    book.put(Note(TASK, "Backup", "second", ["b"]))

    assert len(book.notes) == 1
    assert book.notes[(TASK, "Backup")].text == "second"
    assert book.notes[(TASK, "Backup")].tags == ["b"]


def test_a_note_with_neither_text_nor_tags_takes_the_note_off() -> None:
    book = _book()

    kept = book.put(Note(TASK, "Backup", "  ", ["#", " "]))

    assert not kept
    assert book.get(TASK, "Backup") is None
    assert book.get(TASK, "Alarm") is not None


def test_a_note_too_long_is_cut() -> None:
    book = NoteBook()

    book.put(Note(TASK, "A", "x" * (objnotes.MAX_NOTE_LENGTH + 500)))

    assert len(book.notes[(TASK, "A")].text) == objnotes.MAX_NOTE_LENGTH


@pytest.mark.parametrize("kind", [SCENE, "", "variable"])
def test_only_a_project_a_profile_or_a_task_can_carry_a_note(kind: str) -> None:
    with pytest.raises(ValueError, match="cannot carry a note"):
        NoteBook().put(Note(kind, "Name", "text"))


@pytest.mark.parametrize("name", ["", "   "])
def test_an_object_with_no_name_cannot_carry_a_note(name: str) -> None:
    with pytest.raises(ValueError, match="no name"):
        NoteBook().put(Note(TASK, name, "text"))


@pytest.mark.parametrize(
    ("name", "own"),
    [
        ("Backup", True),
        ("  Backup  ", True),
        ("Unnamed Stuff", True),  # Has the word, but is not the name MapTasker makes up.
        ("", False),
        ("   ", False),
        ("Variable Clear Name=%ChoresSno....107 (Unnamed)", False),
    ],
)
def test_a_name_is_its_own_unless_it_is_empty_or_the_one_made_up_for_an_unnamed_task(name: str, own: bool) -> None:
    assert objnotes.has_own_name(name) is own


def test_a_note_cannot_be_put_on_the_name_made_up_for_an_unnamed_task() -> None:
    """That name is the Task's first action, so a note kept under it would be lost when the action was edited."""
    with pytest.raises(ValueError, match="no name"):
        NoteBook().put(Note(TASK, "Flash Text=hi (Unnamed)", "text"))


def test_the_name_made_up_for_an_unnamed_task_is_not_one_of_the_names_to_offer() -> None:
    state = fake_state(tasker_root_elements={"all_tasks_by_name": {"Backup": {}, "Flash Text=hi (Unnamed)": {}}})

    assert objnotes.known_names(TASK, state) == {"Backup"}


def test_removing_a_note_says_whether_there_was_one() -> None:
    book = _book()

    assert book.remove(TASK, "Backup")
    assert not book.remove(TASK, "Backup")
    assert book.get(TASK, "Backup") is None


# ##################################################################################
# Finding them
# ##################################################################################
def _names(notes: list[Note]) -> list[str]:
    return [note.name for note in notes]


def test_every_note_is_listed_projects_then_profiles_then_tasks_and_by_name() -> None:
    assert _names(_book().find()) == ["Home", "Wake Up", "Alarm", "Backup"]


def test_limiting_to_a_tag_lists_only_the_objects_that_carry_it() -> None:
    assert _names(_book().find(tags=["flaky"])) == ["Wake Up", "Backup"]
    assert _names(_book().find(tags=["#Family"])) == ["Home", "Alarm"]


def test_limiting_to_several_tags_lists_the_objects_that_carry_all_of_them() -> None:
    assert _names(_book().find(tags=["flaky", "needs-rewrite"])) == ["Backup"]
    assert _names(_book().find(tags=["flaky", "family"])) == []


def test_limiting_to_a_kind() -> None:
    assert _names(_book().find(kind=TASK)) == ["Alarm", "Backup"]
    assert _names(_book().find(kind=PROJECT)) == ["Home"]


def test_text_is_looked_for_in_the_name_the_note_and_the_tags_ignoring_case() -> None:
    book = _book()

    assert _names(book.find(text="REWRITE")) == ["Backup"]  # In the note and the tag.
    assert _names(book.find(text="wake")) == ["Wake Up"]  # In the name.
    assert _names(book.find(text="dad")) == ["Home"]  # In the note.
    assert _names(book.find(text="android-15")) == ["Home"]  # In a tag.
    assert _names(book.find(text="nothing like this")) == []


def test_the_filters_combine() -> None:
    assert _names(_book().find(tags=["family"], kind=TASK)) == ["Alarm"]
    assert _names(_book().find(tags=["flaky"], text="rewrite", kind=TASK)) == ["Backup"]


def test_the_tags_in_use_are_counted_most_used_first_and_then_by_name() -> None:
    assert _book().tag_counts() == {"family": 2, "flaky": 2, "android-15": 1, "needs-rewrite": 1}
    assert list(_book().tag_counts()) == ["family", "flaky", "android-15", "needs-rewrite"]


def test_an_empty_book_has_no_tags_and_no_notes() -> None:
    assert NoteBook().tag_counts() == {}
    assert NoteBook().find() == []


# ##################################################################################
# Which objects are in the file that is open
# ##################################################################################
def _loaded() -> RunState:
    return fake_state(
        tasker_root_elements={
            "all_projects": {"Home": {}},
            "all_profiles_by_name": {"Wake Up": {}},
            "all_tasks_by_name": {"Backup": {}, "": {}},
        },
    )


def test_the_names_in_the_loaded_file_are_those_of_its_own_kind() -> None:
    state = _loaded()

    assert objnotes.known_names(PROJECT, state) == {"Home"}
    assert objnotes.known_names(PROFILE, state) == {"Wake Up"}
    assert objnotes.known_names(TASK, state) == {"Backup"}  # A nameless one is no name.
    assert objnotes.known_names(SCENE, state) == set()


def test_nothing_loaded_has_no_names() -> None:
    assert objnotes.known_names(TASK, fake_state(tasker_root_elements={})) == set()


def test_a_note_is_in_the_file_when_its_object_is() -> None:
    state = fake_state(tasker_root_elements={"all_tasks_by_name": {"Backup": {}}})

    assert objnotes.in_file(Note(TASK, "Backup"), state)
    assert not objnotes.in_file(Note(TASK, "Gone"), state)
    assert not objnotes.in_file(Note(PROFILE, "Backup"), state)


# ##################################################################################
# The file
# ##################################################################################
def test_the_notes_are_kept_in_the_current_directory_beside_the_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    assert _REAL_BOOK_PATH() == os.path.join(os.getcwd(), NOTES_FILE)


def test_the_book_is_read_back_as_it_was_written(tmp_path: Path) -> None:
    where = str(tmp_path / "notes.json")
    book = _book()
    book.show_in_map = False

    assert objnotes.save(book, where) == ""
    again = objnotes.load(where)

    assert not again.show_in_map
    assert again.unreadable == ""
    assert [(note.kind, note.name, note.text, note.tags) for note in again.find()] == [
        (note.kind, note.name, note.text, note.tags) for note in book.find()
    ]


def test_the_file_is_plain_json_that_can_be_read() -> None:
    where = objnotes.book_path()
    objnotes.save(_book(), where)

    with open(where, encoding="utf-8") as handle:
        data = json.load(handle)

    assert data["version"] == objnotes.FORMAT_VERSION
    assert data["show_in_map"] is True
    assert {"kind": PROJECT, "name": "Home"} == {key: data["notes"][0][key] for key in ("kind", "name")}


def test_nothing_is_left_beside_the_file_once_it_is_written(tmp_path: Path) -> None:
    where = str(tmp_path / "notes.json")

    objnotes.save(_book(), where)

    assert sorted(path.name for path in tmp_path.iterdir()) == ["notes.json"]


def test_no_file_is_an_empty_book_that_shows_its_notes(tmp_path: Path) -> None:
    book = objnotes.load(str(tmp_path / "nothing.json"))

    assert book.notes == {}
    assert book.show_in_map
    assert book.unreadable == ""


def test_a_file_that_is_not_json_is_an_empty_book_that_says_why(tmp_path: Path) -> None:
    where = tmp_path / "notes.json"
    where.write_text("{ not json", encoding="utf-8")

    book = objnotes.load(str(where))

    assert book.notes == {}
    assert book.unreadable


def test_an_unreadable_file_is_put_aside_before_it_is_written_over(tmp_path: Path) -> None:
    where = tmp_path / "notes.json"
    where.write_text("{ not json", encoding="utf-8")
    book = objnotes.load(str(where))
    book.put(Note(TASK, "New", "after"))

    assert objnotes.save(book, str(where)) == ""

    assert (tmp_path / "notes.json.unreadable").read_text(encoding="utf-8") == "{ not json"
    assert objnotes.load(str(where)).get(TASK, "New") is not None
    assert book.unreadable == ""


def test_an_entry_that_is_not_a_note_is_skipped_and_the_rest_are_kept(tmp_path: Path) -> None:
    where = tmp_path / "notes.json"
    where.write_text(
        json.dumps(
            {
                "notes": [
                    {"kind": "task", "name": "Good", "text": "ok"},
                    {"kind": "scene", "name": "Menu", "text": "a Scene cannot carry one"},
                    {"kind": "task", "name": "", "text": "no name"},
                    {"kind": "task", "name": "Empty", "text": "", "tags": []},
                    "not even an object",
                    {"kind": "profile", "name": "Tagged", "tags": ["#A", "a", "b"]},
                ],
            },
        ),
        encoding="utf-8",
    )

    book = objnotes.load(str(where))

    assert [(note.kind, note.name) for note in book.find()] == [(PROFILE, "Tagged"), (TASK, "Good")]
    assert book.get(PROFILE, "Tagged").tags == ["a", "b"]  # type: ignore[union-attr]


def test_a_note_in_the_file_on_a_made_up_name_is_skipped(tmp_path: Path) -> None:
    where = tmp_path / "notes.json"
    where.write_text(
        json.dumps({"notes": [{"kind": "task", "name": "Flash Text=hi (Unnamed)", "text": "lost on an edit"}]}),
        encoding="utf-8",
    )

    assert objnotes.load(str(where)).notes == {}


@pytest.mark.parametrize("content", ["[]", "3", '"text"', "null", '{"notes": 5}', '{"notes": {"a": 1}}'])
def test_a_file_of_the_wrong_shape_is_an_empty_book(tmp_path: Path, content: str) -> None:
    where = tmp_path / "notes.json"
    where.write_text(content, encoding="utf-8")

    book = objnotes.load(str(where))

    assert book.notes == {}


def test_a_file_that_cannot_be_written_says_why(tmp_path: Path) -> None:
    missing_folder = str(tmp_path / "no" / "such" / "folder" / "notes.json")

    assert objnotes.save(_book(), missing_folder)


def test_text_in_any_language_survives_the_file(tmp_path: Path) -> None:
    where = str(tmp_path / "notes.json")
    book = NoteBook()
    book.put(Note(TASK, "Réveil ⏰", "你好 — «note»", ["éclair"]))

    objnotes.save(book, where)

    again = objnotes.load(where).get(TASK, "Réveil ⏰")
    assert again is not None
    assert (again.text, again.tags) == ("你好 — «note»", ["éclair"])


# ##################################################################################
# What a run holds
# ##################################################################################
def test_a_run_reads_the_file_once_and_holds_the_book() -> None:
    state = fake_state(object_notes=None)
    objnotes.save(_book())

    first = objnotes.book_for(state)
    objnotes.save(NoteBook())  # A change on disk, which this run has not been told of.

    assert objnotes.book_for(state) is first
    assert len(first.notes) == 4


def test_a_run_that_lets_go_of_the_book_reads_the_file_again() -> None:
    state = fake_state(object_notes=None)
    objnotes.save(_book())
    objnotes.book_for(state)
    objnotes.save(NoteBook())

    objnotes.forget(state)

    assert objnotes.book_for(state).notes == {}


# ##################################################################################
# What a Map built from them depends on
# ##################################################################################
def test_the_fingerprint_changes_when_a_note_does() -> None:
    book = _book()
    objnotes.save(book)
    before = objnotes.fingerprint()

    book.put(Note(TASK, "Backup", "Rewritten", ["done"]))
    objnotes.save(book)

    assert objnotes.fingerprint() != before


def test_the_same_notes_have_the_same_fingerprint() -> None:
    objnotes.save(_book())
    first = objnotes.fingerprint()
    objnotes.save(_book())  # Written again, with new time stamps: not a change a Map shows.

    assert objnotes.fingerprint() == first


def test_no_notes_and_notes_switched_off_are_the_same_to_a_map() -> None:
    nothing = objnotes.fingerprint()
    book = _book()
    book.show_in_map = False
    objnotes.save(book)

    assert nothing == "off"
    assert objnotes.fingerprint() == "off"


def test_switching_notes_off_and_on_again_is_what_costs_a_rebuild() -> None:
    book = _book()
    objnotes.save(book)
    shown = objnotes.fingerprint()

    book.show_in_map = False
    objnotes.save(book)
    hidden = objnotes.fingerprint()
    book.show_in_map = True
    objnotes.save(book)

    assert shown != hidden
    assert objnotes.fingerprint() == shown
