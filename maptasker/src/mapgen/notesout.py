"""notesout: the user's note and tags for an object, written into the Map under the object's own line."""

#! /usr/bin/env python3

#                                                                                        #
# notesout: put a note on the page.                                                       #
#                                                                                        #
# One call, made by the code that has just written a Project's, a Profile's or a Task's own line, and it writes the   #
# note and the tags under it -- or writes nothing, which is the usual case, and costs one dictionary lookup.          #
# The line is drawn in the object's own color and starts with a label, the way the Properties line under it is; the    #
# tags are written '#like-this' so that the Map's search, which is a text search, finds every object that carries one.  #
#                                                                                        #
# Nothing is written for an object without a note, or when the notes are switched off (the 'Show In Map And Diagram'    #
# setting of the Notes & Tags window, kept with the notes), which is how a Map is made ready to share.                  #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                                #
#
from __future__ import annotations

import html
from typing import TYPE_CHECKING

from maptasker.src.core import objnotes
from maptasker.src.core.mapjump import PROFILE, PROJECT, TASK
from maptasker.src.core.sysconst import FormatLine

if TYPE_CHECKING:
    from maptasker.src.core.primitem import RunState

# The color class each kind of line is drawn in: the object's own, as its Properties line is.
_COLORS = {PROJECT: "project_color", PROFILE: "profile_color", TASK: "task_color"}

# The labels, and the blanks that carry a second line of a note in under the first.
NOTE_LABEL = "Note:"
TAGS_LABEL = "Tags:"
_BLANK = "&nbsp;"


def note_html(note: objnotes.Note) -> str:
    """A note as the lines of the Map: the text, then the tags.  Escaped, since it is the user's own words."""
    parts: list[str] = []
    if note.text:
        indent = _BLANK * (len(NOTE_LABEL) + 1)
        body = html.escape(note.text, quote=False).replace("\r", "").replace("\n", f"<br>{indent}")
        parts.append(f"{NOTE_LABEL}{_BLANK}{body}")
    if note.tags:
        parts.append(f"{TAGS_LABEL}{_BLANK}{html.escape(note.hashtags, quote=False)}")
    return "<br>".join(parts)


def note_lines(kind: str, name: str, state: RunState) -> str:
    """The lines of the note on this object as html, or "" when it has none or notes are not being shown.

    Args:
        kind (str): mapjump.PROJECT, PROFILE or TASK.
        name (str): the object's name, as the Map lists it.  "" for one with no name, which cannot have a note.
        state (RunState): the run, which holds the notes read for this build.
    """
    if not name or kind not in _COLORS:
        return ""
    book = objnotes.book_for(state)
    if not book.show_in_map or (note := book.get(kind, name)) is None:
        return ""
    return note_html(note)


def output_notes(kind: str, name: str, state: RunState) -> None:
    """Write the note on this Project, Profile or Task under its line, if it has one and notes are being shown."""
    if lines := note_lines(kind, name, state):
        state.output_lines.add_line_to_output(2, f"{lines}<br>", ["", _COLORS[kind], FormatLine.add_end_span])
