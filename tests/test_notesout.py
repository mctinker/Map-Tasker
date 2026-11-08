"""MapTasker notes in the Map (notesout) Unit Tests

The line a note is written as, when nothing is written, and -- through a real export -- that a Project's, a Profile's
and a Task's note each land under that object's own line, and nowhere else.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from maptasker.src import clireports
from maptasker.src.core import objnotes
from maptasker.src.core.mapjump import PROFILE, PROJECT, SCENE, TASK
from maptasker.src.core.objnotes import Note, NoteBook
from maptasker.src.mapgen import mapcache, notesout

from tests.doubles import fake_state

_SYNTHETIC_BACKUP = Path(__file__).parent / "data" / "synthetic_backup.xml"


class _Lines:
    """What the Map's output lines are to the writer: something that is told a line."""

    def __init__(self) -> None:
        self.added: list[tuple[int, str, Any]] = []

    def add_line_to_output(self, indent: int, text: str, style: Any) -> None:
        self.added.append((indent, text, style))


def _state() -> Any:
    return fake_state(object_notes=None, output_lines=_Lines())


def _save(*notes: Note, shown: bool = True) -> None:
    book = NoteBook(show_in_map=shown)
    for note in notes:
        book.put(note)
    objnotes.save(book)


# ##################################################################################
# The line
# ##################################################################################
def test_a_note_is_written_as_its_text_and_then_its_tags() -> None:
    line = notesout.note_html(Note(TASK, "A", "Needs a rewrite", ["flaky", "android-15"]))

    assert line == "Note:&nbsp;Needs a rewrite<br>Tags:&nbsp;#flaky #android-15"


def test_a_note_with_only_tags_or_only_text_writes_only_that() -> None:
    assert notesout.note_html(Note(TASK, "A", "", ["flaky"])) == "Tags:&nbsp;#flaky"
    assert notesout.note_html(Note(TASK, "A", "Just text", [])) == "Note:&nbsp;Just text"


def test_a_second_line_of_a_note_is_carried_in_under_the_first() -> None:
    line = notesout.note_html(Note(TASK, "A", "One\nTwo", []))

    assert line == "Note:&nbsp;One<br>" + "&nbsp;" * len("Note: ") + "Two"


def test_the_users_words_are_escaped_so_they_cannot_become_markup() -> None:
    line = notesout.note_html(Note(TASK, "A", '<script>alert("x")</script> & more', ["a<b"]))

    assert "<script>" not in line
    assert "&lt;script&gt;" in line
    assert "&amp; more" in line
    assert "#a&lt;b" in line


# ##################################################################################
# When one is written
# ##################################################################################
@pytest.mark.parametrize(
    ("kind", "color"),
    [(PROJECT, "project_color"), (PROFILE, "profile_color"), (TASK, "task_color")],
)
def test_a_note_is_written_in_the_color_of_the_object_it_is_on(kind: str, color: str) -> None:
    _save(Note(kind, "Thing", "Remember", ["x"]))
    state = _state()

    notesout.output_notes(kind, "Thing", state)

    ((indent, text, style),) = state.output_lines.added
    assert indent == 2
    assert text == f"{notesout.note_html(Note(kind, 'Thing', 'Remember', ['x']))}<br>"
    assert style[1] == color


def test_an_object_without_a_note_is_written_nothing() -> None:
    _save(Note(TASK, "Other", "Remember"))
    state = _state()

    notesout.output_notes(TASK, "Thing", state)
    notesout.output_notes(PROFILE, "Other", state)  # The same name, but another kind of object.

    assert state.output_lines.added == []


def test_an_object_with_no_name_or_a_kind_that_takes_no_note_is_written_nothing() -> None:
    _save(Note(TASK, "Thing", "Remember"))
    state = _state()

    notesout.output_notes(TASK, "", state)
    notesout.output_notes(SCENE, "Thing", state)

    assert state.output_lines.added == []


def test_notes_switched_off_write_nothing() -> None:
    _save(Note(TASK, "Thing", "Remember"), shown=False)
    state = _state()

    notesout.output_notes(TASK, "Thing", state)

    assert state.output_lines.added == []


def test_a_build_reads_the_notes_file_once() -> None:
    _save(Note(TASK, "Thing", "first"))
    state = _state()
    notesout.output_notes(TASK, "Thing", state)
    _save(Note(TASK, "Thing", "second"))  # Changed on disk part-way through a build.

    notesout.output_notes(TASK, "Thing", state)

    assert [line[1].count("first") for line in state.output_lines.added] == [1, 1]


# ##################################################################################
# In a real Map
# ##################################################################################
def _export(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> str:
    code = clireports.run(
        ["-export", "map", "-format", "md", "-file", str(_SYNTHETIC_BACKUP), "-outdir", str(tmp_path)]
    )
    assert code == clireports.EXIT_OK
    return Path(capsys.readouterr().out.strip()).read_text(encoding="utf-8")


def test_each_object_has_its_note_under_its_own_line(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _save(
        Note(PROJECT, "Reminders", "Dad's phone only", ["family"]),
        Note(PROFILE, "Morning Reminder", "", ["flaky"]),
        Note(TASK, "Remind Me", "Needs a rewrite", ["needs-rewrite"]),
    )

    text = _export(tmp_path, capsys)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    project = lines.index("Project: Reminders")
    profile = lines.index("Profile: Morning Reminder")
    task = next(at for at, line in enumerate(lines) if line.startswith("Task: Remind Me"))
    assert lines[project + 1 : project + 3] == ["Note: Dad's phone only", "Tags: \\#family"]
    # Under the Profile's own line, which the export may follow with the conditions it shows.
    assert "Tags: \\#flaky" in lines[profile + 1 : profile + 4]
    # A Task's own text sits in its block, above its actions, as its Properties do.
    assert "Note: Needs a rewrite" in lines[task : task + 6]
    assert text.count("Note:") == 2
    assert text.count("Tags:") == 3


def test_no_notes_file_is_a_map_as_it_always_was(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    text = _export(tmp_path, capsys)

    assert "Note:" not in text
    assert "Tags:" not in text


def test_notes_switched_off_are_not_in_the_map(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _save(Note(TASK, "Remind Me", "Needs a rewrite", ["x"]), shown=False)

    text = _export(tmp_path, capsys)

    assert "Needs a rewrite" not in text


def test_a_note_on_an_object_not_in_the_file_is_not_in_the_map(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _save(Note(TASK, "Not In This Backup", "Elsewhere", ["x"]))

    text = _export(tmp_path, capsys)

    assert "Elsewhere" not in text


def test_a_task_no_profile_runs_is_noted_where_the_map_lists_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Under 'not in any Profile' a Task is listed on its own, and its note is with it."""
    _save(Note(TASK, "Open Reminder List", "Opens the list", ["ui"]))

    text = _export(tmp_path, capsys)

    assert text.count("Opens the list") == 1


# ##################################################################################
# What the cache makes of them
# ##################################################################################
def test_a_note_added_since_the_map_was_built_is_a_map_that_must_be_built_again() -> None:
    state = fake_state(program_arguments={}, colors_to_use={})
    before = mapcache.settings_digest(state)

    _save(Note(TASK, "Remind Me", "Added later"))

    assert mapcache.settings_digest(state) != before


def test_the_same_notes_are_the_same_map() -> None:
    state = fake_state(program_arguments={}, colors_to_use={})
    _save(Note(TASK, "Remind Me", "Same"))
    first = mapcache.settings_digest(state)

    _save(Note(TASK, "Remind Me", "Same"))

    assert mapcache.settings_digest(state) == first


# ##################################################################################
# Where a Task's note goes: under its line, or -- under a twisty -- in the line that stays
# ##################################################################################
class _TaskOutput:
    """What state.output_lines is to format_item: it is told what to write, and in what order."""

    def __init__(self) -> None:
        self.written: list[str] = []

    def add_line_to_output(self, _level: int, line: str, _how: Any = None) -> None:
        self.written.append(line)


def _format_task(
    monkeypatch: pytest.MonkeyPatch, *, twisty: bool, list_type: str = "Task:"
) -> tuple[list[str], list[str]]:
    """Format one Task the way the Map does; returns what was written and what the twisty was given as its summary."""
    import xml.etree.ElementTree as ET

    from maptasker.src.mapgen import proclist

    summaries: list[str] = []

    def add_dictionary_and_twisty(
        _type: str, _item: str, _task: object, line: str, *_rest: object, **_kw: object
    ) -> tuple[str, str]:
        summaries.append(line)
        return "", ""

    monkeypatch.setattr(proclist, "format_task_or_scene", lambda *_args, **_kwargs: ("<header>", "color"))
    monkeypatch.setattr(proclist, "add_dictionary_and_twisty", add_dictionary_and_twisty)
    monkeypatch.setattr(proclist, "item_anchor", lambda *_args, **_kwargs: "")
    output = _TaskOutput()
    state: Any = fake_state(
        object_notes=None,
        output_lines=output,
        tasker_root_elements={"all_tasks": {"101": {"name": "Remind Me"}}},
    )
    config: Any = SimpleNamespace(debug=False, display_detail_level=1, twisty=twisty)
    task = ET.fromstring('<Task sr="task101"><id>101</id><nme>Remind Me</nme></Task>')
    proclist.format_item(list_type, "Task: Name", [], task, config, state=state)
    return output.written, summaries


def test_a_tasks_note_is_written_under_its_line(monkeypatch: pytest.MonkeyPatch) -> None:
    _save(Note(TASK, "Remind Me", "Needs a rewrite", ["x"]))

    written, summaries = _format_task(monkeypatch, twisty=False)

    assert written[-2:] == ["<header>", "Note:&nbsp;Needs a rewrite<br>Tags:&nbsp;#x<br>"]
    assert summaries == ["<header>"]


def test_under_a_twisty_the_note_is_in_the_line_that_stays_and_is_not_written_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _save(Note(TASK, "Remind Me", "Needs a rewrite", ["x"]))

    written, summaries = _format_task(monkeypatch, twisty=True)

    assert summaries == ["<header><br>Note:&nbsp;Needs a rewrite<br>Tags:&nbsp;#x"]
    assert written[-1] == "<header>"
    assert not any("Needs a rewrite" in line for line in written)


def test_a_task_with_no_note_is_formatted_as_before_with_or_without_a_twisty(monkeypatch: pytest.MonkeyPatch) -> None:
    for twisty in (False, True):
        written, summaries = _format_task(monkeypatch, twisty=twisty)

        assert written[-1] == "<header>"
        assert summaries == ["<header>"]


def test_a_task_fired_from_a_scene_takes_no_note(monkeypatch: pytest.MonkeyPatch) -> None:
    _save(Note(TASK, "Remind Me", "Needs a rewrite", ["x"]))

    written, summaries = _format_task(monkeypatch, twisty=True, list_type="--Task:")

    assert summaries == ["<header>"]
    assert not any("Needs a rewrite" in line for line in written)
