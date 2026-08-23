"""Session-wide Undo/Redo for edits made to the loaded Tasker configuration."""

#! /usr/bin/env python3

#                                                                                      #
# sessundo: one Undo history covering every edit panel, for the whole session.          #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
#
# WHAT THIS IS FOR
#
# Editing became this program's flagship feature, and the worst thing it can do is let a
# user quietly wreck a configuration they cannot get back.  The Scene designers already had
# an Undo (guiwins.py's two `history` stacks), but it lives and dies inside one dialog and
# knows nothing about the four other panels.  Delete the wrong Task, rename the wrong
# Project, or attach a Profile to the wrong Project, and there was nothing to press.
#
# This is the missing half: one stack, above all the panels, holding the whole loaded
# configuration as it stood before each edit was committed to it.
#
# WHAT A CHECKPOINT IS
#
# The entire configuration, rendered exactly as "Save To Current File" would render it
# (maputil2.render_full_backup_xml), gzipped.  Not a per-operation inverse.
#
# The inverse-per-operation design is the one that looks efficient and is not worth
# building here -- sceneedit.legacy_snapshot says the same thing about the designers'
# own stacks, at a much smaller scale.  There are eighteen live-tree mutators across
# taskedit/profedit/projedit/sceneedit and several of them are one-to-many: deleting a
# Project unlinks its Profiles, deletes their Tasks, and restamps <mdate> on whatever is
# left.  Every one of those would need an exact inverse, and the first inverse that was
# subtly wrong would restore a configuration that looked right and was not -- which is
# precisely the failure this feature exists to prevent.
#
# A whole-configuration snapshot cannot be subtly wrong.  It is the same bytes the save
# path writes, which is why it is the same function that produces them: an Undo that
# restored a slightly different reconciliation than a Save writes would be its own bug.
#
# WHAT IT COSTS, AND WHY THAT IS AFFORDABLE
#
# Measured on the largest backup in this repo -- 8.3 MB, 83 Projects, 293 Profiles, 840
# Tasks, 62 Scenes:
#
#     render (no indent)   0.22 s        gzip   0.05 s        result   1.3 MB
#     restore (parse + rebuild the tables)      0.43 s
#
# So roughly a quarter of a second on the edit the user just committed, and under half a
# second on the Undo itself.  The render is only that cheap because it does not copy the
# tree for a checkpoint -- see render_full_backup_xml's own note on `indent`, which is what
# separates the two callers.  Smaller configurations, which is most of them, are far
# quicker again.
#
# MAX_CHECKPOINTS and MAX_TOTAL_BYTES between them bound what the history can grow to.
#
# WHAT IS AND IS NOT COVERED
#
# Covered: every change that has reached the loaded configuration -- everything the four
# Edit dialogs' Ok/Save buttons apply, Add and Delete of a Project/Profile/Task/Scene, and
# every Rename.  That is the set of changes "Changes Pending" stops warning about, and the
# set a Save would write.
#
# Not covered, deliberately: work still inside an open dialog.  A half-finished edit is
# Cancel's job, and the Scene designers' own Undo buttons remain the right tool inside a
# design session.  This one starts where those stop.
#

from __future__ import annotations

import contextlib
import gzip
import xml.etree.ElementTree as ETW  # noqa: ICN001, N814  (stdlib "ET Write" -- only to wrap a root)
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

import defusedxml.ElementTree as ET  # noqa: N817

from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import logger

if TYPE_CHECKING:
    from collections.abc import Iterator

# How many steps back the history goes.  Deep enough that a user who realises three or four
# edits later is still covered, shallow enough to stay a bounded amount of memory.
MAX_CHECKPOINTS = 20

# ...and the belt to that pair of braces.  A checkpoint is roughly a seventh of the backup's
# size once gzipped (1.3 MB for the 8.3 MB file above), so twenty of them is around 26 MB
# there -- fine.  A configuration several times larger would not be, and nobody would
# connect the memory to the Undo history.  Oldest checkpoints are dropped until the total
# fits, so the history shortens on a huge file rather than the program growing without
# bound.  512 MB of XML would have to be loaded before this bites on a normal one.
MAX_TOTAL_BYTES = 64 * 1024 * 1024

# gzip level 1.  Levels above it cost more time than they save memory at this size (level 6
# was measured taking twice as long for a third less space), and time is the axis that shows
# up as a pause on the user's click.
_COMPRESSION_LEVEL = 1


@dataclass(frozen=True)
class Checkpoint:
    """One entry in the history: what the configuration was, and what happened to it next.

    `label` describes the edit that was made AFTER this state was captured -- "Delete Task
    'Wake Up'" -- because that is what the user is choosing to undo.  It is what the Undo
    button's tooltip and the History dialog show, so it has to read as an action, not as a
    state.
    """

    label: str
    when: datetime
    payload: bytes

    @property
    def size(self) -> int:
        """Bytes this checkpoint occupies, for MAX_TOTAL_BYTES."""
        return len(self.payload)


# The two halves of the history.  Undoing moves an entry from _undo to _redo and redoing
# moves it back, so between them they always describe one straight line through the
# session's edits with the current state sitting somewhere along it.
_undo: list[Checkpoint] = []
_redo: list[Checkpoint] = []

# Depth of the currently-open undoable() blocks.  Only the outermost takes a checkpoint --
# see undoable() for why that is not merely an optimisation.
_depth = 0


def _render() -> str | None:
    """The loaded configuration as one XML string.  None if there is nothing loaded or the
    render failed.

    Kept uncompressed because undoable() compares two of these to decide whether anything
    actually changed, and compressed bytes cannot be compared: gzip stamps the time into
    its header, so the same configuration rendered a second apart does not produce the same
    bytes.  Compression happens once, in _compress, when a checkpoint is really being kept.

    A failure here must never stop the edit that was about to happen: losing the ability to
    undo one change is a far smaller harm than refusing to make it, and the user asked for
    the edit, not for the checkpoint.  So it is logged and swallowed, and the edit proceeds
    with no history entry -- which is exactly the situation every edit was in before this
    module existed.
    """
    # Lazy import: maputil2 is imported by most of this package, and importing it at module
    # scope here puts sessundo in the middle of that graph for no benefit (mirrors
    # getbakup.get_backup_file()'s note on the same problem).
    from maptasker.src.maputil2 import render_full_backup_xml  # noqa: PLC0415

    if PrimeItems.xml_root is None:
        return None
    try:
        return render_full_backup_xml(indent=False)
    except (ValueError, TypeError, AttributeError) as error:
        logger.error(f"Undo checkpoint could not be taken: {error}")
        return None


def _compress(rendered: str) -> bytes:
    """A rendered configuration, ready to sit in the history."""
    return gzip.compress(rendered.encode("utf-8"), _COMPRESSION_LEVEL)


def _trim() -> None:
    """Drop the oldest checkpoints until the history is inside both of its limits."""
    del _undo[: max(0, len(_undo) - MAX_CHECKPOINTS)]
    while len(_undo) > 1 and sum(c.size for c in _undo) + sum(c.size for c in _redo) > MAX_TOTAL_BYTES:
        _undo.pop(0)


def _restore(payload: bytes) -> bool:
    """Make `payload` the loaded configuration again.  True if it took.

    The same two steps a file load takes (taskerd.get_the_xml_data), minus the file: parse,
    then rebuild every lookup table off the new root.  Rebuilding is not optional and not a
    refresh -- all_projects/all_profiles/all_tasks/all_scenes hold the tree's own elements,
    so a root swapped in underneath them would leave every table entry pointing into a tree
    nothing renders from any more.

    Parsed before anything is assigned, so a payload that somehow will not parse leaves the
    user's configuration exactly as it was rather than half-replaced.
    """
    # Lazy import for the same reason as _capture's -- taskerd sits low in the import graph.
    from maptasker.src.taskerd import build_tasker_tables  # noqa: PLC0415

    try:
        root = ET.fromstring(gzip.decompress(payload).decode("utf-8"))
    except (OSError, ET.ParseError, UnicodeDecodeError, ValueError) as error:
        logger.error(f"Undo could not restore the checkpoint: {error}")
        return False

    PrimeItems.xml_root = root
    # ETW's ElementTree, not defusedxml's -- defusedxml exposes the parsing entry points
    # and no ElementTree class of its own.  This is only a holder for the root (bildhtml
    # iterates it); the parse above is still the safe one.
    PrimeItems.xml_tree = ETW.ElementTree(root)
    build_tasker_tables()
    return True


@contextlib.contextmanager
def undoable(label: str) -> Iterator[None]:
    """Wrap a change to the loaded configuration so the user can take it back.

    Put it around the mutation itself, in the module that performs it, rather than around
    the button that asked for it -- there are far more buttons than mutators, and a button
    added later that forgot to wrap itself would be a silent hole in the history.  The
    mutators are the choke points; that is where this belongs.

    RE-ENTRANT, AND THAT IS THE POINT.  Nested blocks take no checkpoint of their own and
    keep the outermost one's label, so one thing the user did stays one thing they can
    undo.  Deleting a Project runs delete_profiles_and_tasks_of_project, which runs
    delete_profile and delete_task once per item it owns; without this, deleting a Project
    with nine Profiles would need ten presses of Undo to get back, each one restoring a
    configuration that was mid-delete and internally inconsistent.  A handler that makes
    several top-level changes at once (Add Profile registers the Profile and then attaches
    it to its Project) opens its own outer block for the same reason.

    NOTHING CHANGED MEANS NOTHING TO UNDO.  The configuration is rendered on the way in and
    again on the way out, and the checkpoint is only kept if the two differ.  Without that,
    every one of these would leave an entry behind whether or not it did anything -- and
    several routinely do nothing: the deletes all validate first and return an error
    without touching anything, the rename and apply mutators are documented no-ops when the
    item is not registered, and pressing Ok on a dialog nobody edited applies an identical
    element over the top of itself.  A history full of steps that undo to the state they
    already undid to is worse than no history: the user presses Undo, sees nothing move,
    and stops trusting the button.

    It costs a second render, which is the cheap half of a checkpoint (see the timings at
    the top of this module) and is only paid once per user action however many mutators
    that action ran.

    A failure inside the block keeps the checkpoint rather than discarding it, and the
    comparison is what makes that work: an exception part-way through a mutation leaves a
    configuration that differs from the one on the way in, so it is kept -- which is
    exactly the case where the user most needs the state from before it.
    """
    global _depth  # noqa: PLW0603

    if _depth > 0:
        _depth += 1
        try:
            yield
        finally:
            _depth -= 1
        return

    before = _render()
    _depth = 1
    try:
        yield
    finally:
        _depth = 0
        after = _render()
        # `after is None` means the render failed on the way out, so whether anything
        # changed is unknown -- and unknown is kept, because the alternative is throwing
        # away the only copy of a state that may well have just been mutated.
        if before is not None and (after is None or after != before):
            _undo.append(Checkpoint(label=label, when=datetime.now(), payload=_compress(before)))  # noqa: DTZ005
            # Redoing only makes sense along the line the user walked back down.  Making a
            # fresh change from here is a new line, and the old one can no longer be reached.
            _redo.clear()
            _trim()


def can_undo() -> bool:
    """Whether there is an edit to take back."""
    return bool(_undo)


def can_redo() -> bool:
    """Whether an undone edit can be put back."""
    return bool(_redo)


def next_undo_label() -> str:
    """What Undo would take back, or "" if there is nothing."""
    return _undo[-1].label if _undo else ""


def next_redo_label() -> str:
    """What Redo would put back, or "" if there is nothing."""
    return _redo[-1].label if _redo else ""


def history() -> list[tuple[str, datetime]]:
    """The whole undo history, most recent edit first -- for the History dialog.

    Only the undo half: what the user can still take back.  The redo half is the same
    edits seen from the other side and listing both would show each one twice.
    """
    return [(checkpoint.label, checkpoint.when) for checkpoint in reversed(_undo)]


def undo() -> tuple[bool, str]:
    """Take back the most recent edit.

    Returns (True, label of the edit undone) or (False, why not).  The current state goes
    onto the redo stack first, under that same label, so Redo puts back exactly the edit
    Undo just removed.
    """
    if not _undo:
        return False, "There is nothing to undo."

    current = _render()
    checkpoint = _undo.pop()
    if not _restore(checkpoint.payload):
        # _restore left the configuration untouched, so put the checkpoint back rather
        # than losing a step of history to a failure that changed nothing.
        _undo.append(checkpoint)
        return False, "That undo step could not be restored -- nothing was changed."

    if current is not None:
        _redo.append(
            Checkpoint(label=checkpoint.label, when=datetime.now(), payload=_compress(current))
        )  # noqa: DTZ005
    return True, checkpoint.label


def redo() -> tuple[bool, str]:
    """Put back the most recently undone edit.  The mirror of undo(), in every respect."""
    if not _redo:
        return False, "There is nothing to redo."

    current = _render()
    checkpoint = _redo.pop()
    if not _restore(checkpoint.payload):
        _redo.append(checkpoint)
        return False, "That redo step could not be restored -- nothing was changed."

    if current is not None:
        _undo.append(
            Checkpoint(label=checkpoint.label, when=datetime.now(), payload=_compress(current))
        )  # noqa: DTZ005
        _trim()
    return True, checkpoint.label


def clear() -> None:
    """Throw the history away.

    Call it whenever a different configuration becomes the loaded one -- a Get XML, a fetch
    from Android, the switch to the new copy a "Save To Current File" just wrote.  A
    checkpoint is a whole configuration, so undoing into one taken from a different file
    would not restore an edit; it would silently replace everything the user has open with
    the contents of another file.
    """
    _undo.clear()
    _redo.clear()


def save_history() -> tuple[list[Checkpoint], list[Checkpoint]]:
    """The history as it stands, to be handed back to restore_history() later.

    For diffload, and only for diffload.  Loading the file the user picked to compare
    against goes through taskerd.get_the_xml_data, which clears this history because a load
    normally means a different configuration is now open -- see clear().  A comparison is
    the one load where that is wrong: it borrows PrimeItems for the second file and puts
    everything back afterwards, and the user's own configuration, edits and all, is still
    open the whole time.  Without this pair, clicking "Compare Files" would silently throw
    away every undo step of the session.
    """
    return list(_undo), list(_redo)


def restore_history(state: tuple[list[Checkpoint], list[Checkpoint]]) -> None:
    """Put back what save_history() returned."""
    undo_side, redo_side = state
    _undo[:] = undo_side
    _redo[:] = redo_side
