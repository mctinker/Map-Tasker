"""objnotes: the user's own notes and tags on Projects, Profiles and Tasks, kept beside the backup and not in it."""

#! /usr/bin/env python3

#                                                                                        #
# objnotes: what a person wants to remember about an object that Tasker has no place for. #
#                                                                                        #
# "Broken on Android 15."  "Needs a rewrite."  "Dad's phone only."  A Project, Profile or Task has a name and a    #
# comment-less XML element, and nothing to hold a thought like that; a person ends up keeping it in a text file, or   #
# worse, in the name.  A note is that thought, attached to the object, with any number of tags to find it by.        #
#                                                                                        #
# WHERE THEY LIVE                                                                           #
#                                                                                        #
# In MapTasker_Notes.json in the current directory, beside the settings and the Task tests -- plain JSON that can be   #
# read, edited and put under version control.  NEVER IN THE BACKUP: Tasker has no field for one, and a backup MapTasker  #
# wrote with notes folded into it would carry them onto the phone and into anything shared from it.  Because they are    #
# outside the backup they are also outside Undo, which undoes edits to the configuration, and a Map built from a        #
# friend's backup shows no notes of yours except on an object of the same name.                                        #
#                                                                                        #
# HOW AN OBJECT IS FOUND AGAIN                                                              #
#                                                                                        #
# By kind and NAME, not by id: ids are renumbered whenever a backup passes through Tasker, and the name is what the      #
# object is called everywhere else (Task tests do the same).  Two objects of one kind and one name therefore share a      #
# note, and an object with no name cannot have one.  A note whose object is not in the file that is open is kept and       #
# listed as that -- it may be a Task since renamed, which is for the person to say, since the new name cannot be guessed.   #
#                                                                                        #
# No GUI and no output lines here: the Map's lines are written by mapgen.notesout, the Diagram's marks by diagintr, and the  #
# window is guiwins_notes.  This module is the book, its file and the rules for a tag.                                    #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                                #
#
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from maptasker.src.core import clock
from maptasker.src.core.mapjump import PROFILE, PROJECT, TASK
from maptasker.src.core.sysconst import NOTES_FILE, UNNAMED_ITEM, logger

if TYPE_CHECKING:
    from collections.abc import Iterable

    from maptasker.src.core.primitem import RunState

# The kinds of object that can carry a note, in the order a list of them is shown.
KINDS = (PROJECT, PROFILE, TASK)
_KIND_ORDER = {kind: position for position, kind in enumerate(KINDS)}

# The version of the file's layout, so a later release can tell what it is reading.
FORMAT_VERSION = 1

# How much a note and its tags may hold.  Generous for a thought and small enough that one Map line stays a line.
MAX_NOTE_LENGTH = 2000
MAX_TAG_LENGTH = 40
MAX_TAGS = 24

# What separates one tag from the next when they are typed: a comma, a semicolon, or any blanks.  A tag of two words
# is written with a hyphen -- "needs-rewrite" -- which is also how it is kept.
_TAG_SEPARATORS = re.compile(r"[,;\s]+")
_BLANKS = re.compile(r"\s+")

# How MapTasker spells the name it makes up for a Task that has none: its first action and then "(Unnamed)".  That name
# is not the Task's own -- it changes with the Task's first action -- so a note kept under it would be lost the first
# time the action was edited.
_MADE_UP_ENDING = f"({UNNAMED_ITEM})"

# The tables of the loaded configuration that are keyed by an object's NAME, per kind.  Profiles and Tasks have a second
# table keyed by id (all_profiles, all_tasks), which is not the one a name is looked up in.
_NAME_TABLES = {PROJECT: "all_projects", PROFILE: "all_profiles_by_name", TASK: "all_tasks_by_name"}


# ##################################################################################
# Tags.
# ##################################################################################
def clean_tag(raw: str) -> str:
    """One tag as it is kept: no leading '#', lower case, blanks inside it made hyphens, and not too long.

    Lower case so that "Broken" and "broken" are one tag when it comes to finding them; a tag is a word to look
    something up by and not a piece of prose, so nothing is lost.  "" when nothing is left.
    """
    tag = _BLANKS.sub("-", raw.strip().lstrip("#").strip().lower())
    return tag[:MAX_TAG_LENGTH].strip("-")


def parse_tags(tags: str | Iterable[str]) -> list[str]:
    """The tags in some text or a list, cleaned, each once, in the order given.

    Typed text is split at commas, semicolons and blanks, so "#broken #android-15" and "broken, android-15" are the
    same two tags.  Anything past MAX_TAGS is dropped.
    """
    pieces = _TAG_SEPARATORS.split(tags) if isinstance(tags, str) else list(tags)
    kept = dict.fromkeys(tag for tag in (clean_tag(piece) for piece in pieces) if tag)
    return list(kept)[:MAX_TAGS]


def has_own_name(name: str) -> bool:
    """Whether this is a name an object has of its own, and so one a note can be found by.

    Not an empty name, and not the one MapTasker makes up for a Task that has none.
    """
    stripped = name.strip()
    return bool(stripped) and not stripped.endswith(_MADE_UP_ENDING)


# ##################################################################################
# A note, and the book of them.
# ##################################################################################
@dataclass
class Note:
    """What is remembered about one object: some text, some tags, and when it was last changed."""

    kind: str
    name: str
    text: str = ""
    tags: list[str] = field(default_factory=list[str])
    updated: str = ""

    @property
    def key(self) -> tuple[str, str]:
        """What the object is, which is what the book is keyed by."""
        return (self.kind, self.name)

    @property
    def hashtags(self) -> str:
        """The tags as they are written in the Map and in a search: '#broken #android-15'."""
        return " ".join(f"#{tag}" for tag in self.tags)


@dataclass
class NoteBook:
    """Every note, and the one setting that goes with them."""

    notes: dict[tuple[str, str], Note] = field(default_factory=dict[tuple[str, str], Note])
    # Whether the Map and the Diagram show them.  Off for a Map that is about to be shared: the notes stay, unseen.
    show_in_map: bool = True
    # Why the file could not be read, or "" -- see load().  The book is empty then, and save() puts the unreadable file
    # aside rather than writing over it.
    unreadable: str = ""

    def get(self, kind: str, name: str) -> Note | None:
        """The note on this object, or None."""
        return self.notes.get((kind, name))

    def put(self, note: Note) -> bool:
        """Keep a note in the place of any the object already has.  True when it was kept.

        The text and tags are cleaned and the time stamped here, so every way in comes out alike.  A note with neither
        text nor tags is not a note: it is how an object has its note taken away, and so it removes the one there is.

        Raises:
            ValueError: for a kind that cannot carry a note, or an object with no name.
        """
        if note.kind not in KINDS:
            message = f"A {note.kind!r} cannot carry a note."
            raise ValueError(message)
        name = note.name.strip()
        if not has_own_name(name):
            message = "An object with no name cannot carry a note."
            raise ValueError(message)
        text = note.text.strip()[:MAX_NOTE_LENGTH]
        tags = parse_tags(note.tags)
        if not text and not tags:
            self.notes.pop((note.kind, name), None)
            return False
        self.notes[(note.kind, name)] = Note(note.kind, name, text, tags, clock.now().isoformat(timespec="seconds"))
        return True

    def remove(self, kind: str, name: str) -> bool:
        """Take the note off this object.  True when there was one."""
        return self.notes.pop((kind, name), None) is not None

    def tag_counts(self) -> dict[str, int]:
        """Each tag in use and how many objects carry it, the most used first and then alphabetically."""
        counts: dict[str, int] = {}
        for note in self.notes.values():
            for tag in note.tags:
                counts[tag] = counts.get(tag, 0) + 1
        return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))

    def find(self, tags: Iterable[str] = (), text: str = "", kind: str = "") -> list[Note]:
        """The notes that carry every one of `tags`, mention `text` and are on this `kind` -- each given only if wanted.

        `text` is looked for, ignoring case, in the object's name, the note and the tags.  Ordered Projects, then
        Profiles, then Tasks, and by name within each.
        """
        wanted = parse_tags(list(tags))
        needle = text.strip().lower()
        found = [
            note
            for note in self.notes.values()
            if (not kind or note.kind == kind)
            and all(tag in note.tags for tag in wanted)
            and (not needle or needle in " ".join([note.name, note.text, *note.tags]).lower())
        ]
        return sorted(found, key=lambda note: (_KIND_ORDER[note.kind], note.name.lower(), note.name))


# ##################################################################################
# Which objects are in the file that is open.
# ##################################################################################
def known_names(kind: str, state: RunState) -> set[str]:
    """The names of the objects of this kind in the loaded configuration; empty when nothing is loaded."""
    tables: dict[str, Any] = state.tasker_root_elements or {}
    table = tables.get(_NAME_TABLES.get(kind, ""))
    names = (str(name) for name in cast("dict[Any, Any]", table)) if isinstance(table, dict) else ()
    return {name for name in names if has_own_name(name)}


def in_file(note: Note, state: RunState) -> bool:
    """Whether the object this note is on is in the loaded configuration."""
    return note.name in known_names(note.kind, state)


# ##################################################################################
# Keeping them.
# ##################################################################################
def book_path() -> str:
    """Where the notes are kept -- in the current directory, beside the settings."""
    return os.path.join(os.getcwd(), NOTES_FILE)


def _note_from(data: object) -> Note | None:
    """One note from its JSON, or None when it is not one: a kind that can carry a note, a name, and something to say."""
    if not isinstance(data, dict):
        return None
    raw = cast("dict[str, Any]", data)
    kind, name = str(raw.get("kind") or ""), str(raw.get("name") or "").strip()
    raw_tags = raw.get("tags")
    tags = parse_tags([str(tag) for tag in cast("list[Any]", raw_tags)] if isinstance(raw_tags, list) else "")
    text = str(raw.get("text") or "").strip()[:MAX_NOTE_LENGTH]
    if kind not in KINDS or not has_own_name(name) or not (text or tags):
        return None
    return Note(kind, name, text, tags, str(raw.get("updated") or ""))


def load(file_path: str | None = None) -> NoteBook:
    """The saved notes.  An empty book when there is no file; an empty one that says why when it cannot be read.

    An entry that is not a note is skipped and the rest are kept, so one hand-edited mistake does not cost the others.
    """
    where = file_path or book_path()
    try:
        with open(where, encoding="utf-8") as handle:
            data: object = json.load(handle)
    except FileNotFoundError:
        return NoteBook()
    except (OSError, ValueError) as error:
        logger.error(f"Notes could not be read from {where}: {error}")
        return NoteBook(unreadable=str(error))
    raw = cast("dict[str, Any]", data) if isinstance(data, dict) else {}
    entries = raw.get("notes")
    book = NoteBook(show_in_map=bool(raw.get("show_in_map", True)))
    for entry in cast("list[Any]", entries) if isinstance(entries, list) else []:
        if (note := _note_from(entry)) is not None:
            book.notes[note.key] = note
    return book


def save(book: NoteBook, file_path: str | None = None) -> str:
    """Write the notes.  Returns "" or why they could not be saved.

    Written to a file beside the real one and moved into place, so a crash part-way through leaves the notes as they
    were rather than half of them.  A file that could not be read is copied to '<name>.unreadable' first: the book in
    hand is empty because of it, and writing over the file would lose whatever a person could still have fixed.
    """
    where = file_path or book_path()
    data = {
        "version": FORMAT_VERSION,
        "show_in_map": book.show_in_map,
        "notes": [
            {"kind": note.kind, "name": note.name, "text": note.text, "tags": note.tags, "updated": note.updated}
            for note in book.find()
        ],
    }
    temporary = f"{where}.tmp"
    try:
        if book.unreadable and os.path.exists(where):
            shutil.copyfile(where, f"{where}.unreadable")
            book.unreadable = ""
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
        os.replace(temporary, where)
    except OSError as error:
        logger.error(f"Notes could not be written to {where}: {error}")
        with contextlib.suppress(OSError):
            os.remove(temporary)
        return str(error)
    return ""


def book_for(state: RunState) -> NoteBook:
    """The notes this build uses: read from the file the first time they are asked for, then held (see RunState.object_notes)."""
    held: object = state.object_notes
    if isinstance(held, NoteBook):
        return held
    book = load()
    state.object_notes = book
    return book


def forget(state: RunState) -> None:
    """Let go of the notes held for this run, so the next thing to ask reads the file again."""
    state.object_notes = None


def fingerprint() -> str:
    """What the notes in the file say, as far as a Map is concerned, in a few characters.

    For the Map cache (mapcache): a Map built before a note was added is not the Map to show after it.  Read from the
    FILE, not from the run's held copy, because that is what a build will read.  "off" when they are not shown, so
    that switching them off and on again is the only thing that costs a rebuild.
    """
    book = load()
    if not book.show_in_map or not book.notes:
        return "off"
    digest = hashlib.blake2b(digest_size=16)
    for note in book.find():
        digest.update(json.dumps([note.kind, note.name, note.text, note.tags]).encode())
    return digest.hexdigest()
