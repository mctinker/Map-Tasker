"""diagrecord: noting where each object lands in the drawn Diagram.

A Profile or Scene box is not written when it is built, so a position cannot be read off the output as it grows.
Objects are noted against their buffer as they are drawn and resolved to rows when the buffer is flushed, then
remapped as lines are inserted or dropped.  This is what lets a report finding be jumped to in the Diagram."""

from __future__ import annotations

from typing import TYPE_CHECKING

from maptasker.src.mapgen.diagutil import print_3_lines, print_all

if TYPE_CHECKING:
    from maptasker.src.core.mapjump import Target
    from maptasker.src.core.primitem import RunState


# ##################################################################################
# Where each object ends up in the drawn diagram.
# ##################################################################################
# The Diagram used to be the one view a report finding could not be taken to.  The Map
# carries a mapjump anchor on every Project, Profile, Task and action (see
# mapjump.anchor_html), and an id is all a jump needs; the Diagram is plain text, so there
# is nothing to put an id on.  Matching the text an object is DRAWN as gets close, and is
# still the fallback, but it cannot tell two Tasks of the same name apart -- and naming a
# Task twice is ordinary in Tasker.
#
# So the position is recorded as the diagram is built, and travels with it: {anchor id:
# (line, column, length)} in PrimeItems.diagram_anchors, in the coordinates of the file the
# Diagram view renders.  Column and length are in UTF-16 code units, which is what a
# browser counts in -- a Task name holding an emoji is one character to Python and two to
# JavaScript, and a column that disagreed with the browser by one per emoji would highlight
# the wrong span of a line it had otherwise found perfectly.
#
# Recording a position is not as simple as noting len(netmap_output), because a box is not
# written when it is built.  Profile and Scene boxes accumulate across a three-line buffer
# -- six or eight of them side by side -- and Task lines accumulate in a list of their own;
# both are appended to the output later, and a box's row is only known then.  So an object
# is NOTED against its buffer as it is drawn, and the notes are resolved to rows when that
# buffer is flushed (see flush_boxes and flush_tasks).
#
# Everything after that is a remap.  Four steps move a row between being noted and being
# rendered, and each is applied here in the same breath as the connector seeds' own
# remapping, which goes through the last two of them:
#
#   add_blanks_above_called_tasks   inserts the blank lines the call arrows are drawn into
#   the view limit's cut            drops everything past the line the diagram stops at
#   build_network_map's bar sweep   drops the lines left holding nothing but '|'
#   network_map's file write        inserts the spacers written between Projects
#
# A missing anchor is ordinary rather than an error: a Diagram built for one Project has no
# line for anything outside it, and one built by a MapTasker older than this has no
# anchors at all.  Both fall back to the text match -- see mapjump.diagram_jump_js.
# ##################################################################################
# What a box is closed with, for extending a located name to the whole box it sits in.
BOX_WALL = "\u2551"


# The objects noted against the three-line box buffer, waiting for it to be flushed, are
# state.diagram_pending_boxes: [(target, snippet)], always the middle line of the three, which
# is the only one a name is written on.  Those noted against the Task-line buffer are
# state.diagram_pending_tasks: [(index in that buffer, target, snippet)].  Both live on the run
# state, and are emptied with the rest of the Diagram's records, so that two Diagrams being
# drawn cannot mix their notes.


def note_box(target: Target, snippet: str, state: RunState) -> None:
    """Record that this object has just been drawn into the box buffer's middle line."""
    state.diagram_pending_boxes.append((target, snippet))


def note_task(index: int, target: Target, snippet: str, state: RunState) -> None:
    """Record that this Task has just been drawn as line `index` of the Task buffer."""
    state.diagram_pending_tasks.append((index, target, snippet))


def record_at_row(row: int, target: Target, snippet: str, state: RunState) -> None:
    """Fix one noted object at a row of netmap_output.

    Two records, because two questions are being asked and they have different answers.

    WHERE A JUMP LANDS is diagram_object_seeds, and there first sighting wins, exactly as
    mapjump.anchor_html decides it for the Map: the Diagram draws a Task once per Profile
    that runs it and again under any Scene that fires it, and a jump should land on the
    Task's own line under its Profile rather than on whichever copy happened to be written
    last.

    WHAT IS CLICKABLE is diagram_object_placements, and there every drawing counts.  These
    used to be the same record, and the copies simply went unrecorded -- so the second and
    later drawings of a Task were drawn as plain text: not clickable, not lit up by a chain
    running through them, and invisible to the call edges that happened to point at one.
    The first one worked, which is what made it look like a rule rather than a gap.

    The Target is kept alongside, in a table of its own.  The position moves -- four
    separate passes remap it before the diagram is written -- and the identity does not, so
    the two are held apart: the positions are remapped over and over, while the identity is
    written once and only read at the end, when the interactive Diagram view's node model is
    assembled (see diagintr.build_model).
    """
    seeds = state.diagram_object_seeds
    if target.anchor not in seeds:
        seeds[target.anchor] = (row, snippet)
        state.diagram_object_targets[target.anchor] = target
    state.diagram_object_placements.append((target.anchor, row, snippet))


def flush_boxes(output_lines: list, state: RunState) -> None:
    """Append a finished row of boxes, and fix every box noted into it at its line.

    print_3_lines by another name.  The row is taken before the append rather than after,
    since it is the append that makes it a row at all.
    """
    row = len(state.netmap_output) + 1  # The middle of the three lines.
    print_3_lines(output_lines, state=state)
    for target, snippet in state.diagram_pending_boxes:
        record_at_row(row, target, snippet, state=state)
    state.diagram_pending_boxes.clear()


def flush_tasks(output_lines: list, state: RunState) -> None:
    """Append a finished run of Task lines, and fix every Task noted into it at its line."""
    base = len(state.netmap_output)
    print_all(output_lines, state=state)
    for index, target, snippet in state.diagram_pending_tasks:
        record_at_row(base + index, target, snippet, state=state)
    state.diagram_pending_tasks.clear()


def remap_object_seeds(old_to_new: dict[int, int], state: RunState) -> None:
    """Move every recorded object to where its line has just moved to.

    A row with no entry in the map is a row that no longer exists -- cut off at the view
    limit, or swept away as a bar-only line -- and the object on it is dropped rather than
    left pointing at whatever ended up there instead.
    """
    state.diagram_object_seeds = {
        anchor: (old_to_new[row], snippet)
        for anchor, (row, snippet) in state.diagram_object_seeds.items()
        if row in old_to_new
    }
    state.diagram_object_placements = [
        (anchor, old_to_new[row], snippet)
        for anchor, row, snippet in state.diagram_object_placements
        if row in old_to_new
    ]


def remap_call_edges(old_to_new: dict[int, int], state: RunState) -> None:
    """Move every recorded call to where the two Task lines it joins have just moved to.

    The same journey the object seeds make, and made in the same breath as theirs so the
    two cannot drift apart -- an edge whose rows no longer agree with the anchors on them
    is an edge that would highlight the wrong Tasks.  An edge losing either end (cut off at
    the view limit, or swept away with a bar-only line) is dropped whole: half a call is
    not a link in a chain.
    """
    state.diagram_call_edges = {
        index: {**edge, "caller_row": old_to_new[edge["caller_row"]], "called_row": old_to_new[edge["called_row"]]}
        for index, edge in state.diagram_call_edges.items()
        if edge["caller_row"] in old_to_new and edge["called_row"] in old_to_new
    }


def keep_object_seeds_before(cut: int, state: RunState) -> None:
    """Drop every object drawn past the line the view limit cut the diagram at.

    Those lines are about to be deleted outright, and an object still pointing into them
    would be a jump into whatever the file ends with.
    """
    state.diagram_object_seeds = {
        anchor: placement for anchor, placement in state.diagram_object_seeds.items() if placement[0] < cut
    }
    state.diagram_object_placements = [placement for placement in state.diagram_object_placements if placement[1] < cut]


def _utf16_length(text: str) -> int:
    """How many UTF-16 code units this text is -- how the browser counts a string index.

    Python indexes by code point, JavaScript by UTF-16 code unit, and the two differ by one
    for every astral character: an emoji in a Task name (Tasker allows them, and real
    configurations use them) is one to Python and two to the browser.  Converting here is
    what lets the browser take the column as given rather than searching for the name again.
    """
    return len(text.encode("utf-16-le")) // 2


def place_in_line(line: str, snippet: str, boxed: bool, start: int = 0) -> tuple[int, int]:
    """Where in this rendered line the object's name sits: (column, length), browser-counted.

    (0, 0) when the name cannot be found on the line after all, which the Diagram view
    reads as "the whole line" -- the line is still the right one to be taken to, and
    highlighting all of it says so more honestly than highlighting nothing.  Reachable
    because remove_icon rubs out a blank next to an arrow to keep a line with an icon in it
    aligned, which can fall inside a name.

    A box's name is extended to the wall that closes it, so a Profile jumped to is
    highlighted as the box the eye reads it as rather than as bare text inside one.

    'start' is where to begin looking, in code points, and is how a line holding the same
    name twice gives up both of them.  Two Profiles drawn side by side can run the very same
    Task, which puts "└─ Wear Location Menu" on the line twice; searching from the front
    each time would answer with the first one for both, and the two would be handed to the
    view as one span drawn over itself.
    """
    at = line.find(snippet, start)
    if at < 0:
        return (0, 0)
    end = at + len(snippet)
    if boxed:
        closing = line.find(BOX_WALL, end)
        if closing != -1:
            end = closing + 1
    return (_utf16_length(line[:at]), _utf16_length(line[at:end]))
