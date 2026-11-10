"""Undo and Redo restore the configuration exactly: not a configuration like it, the same file, byte for byte.

Every editor, and every bulk operation (Replace, Fix Findings), changes the loaded configuration and leaves a
checkpoint for Undo to go back to (sessundo).  A checkpoint is a whole rendered configuration rather than an
inverse of what was done, so it cannot be subtly wrong in the way an inverse can -- but only if every mutator takes
one, and only if restoring one gives back what rendering it gave out.  Nothing drew edits in an order nobody thought
of, undid them, and compared.  This does, with the editors the round-trip fuzz (test_fuzz_roundtrip) already drives:

  * a configuration that an edit changed has something to undo, and one it did not change has not;
  * undoing steps back to exactly the state the step before it left, whatever the edit was;
  * redoing steps forward to exactly the state the undone edit left;
  * undoing everything gives back the file that was loaded, and redoing everything the one that was left;
  * the flags the Undo and Redo buttons are drawn from (can_undo, can_redo) say what is true.

The edits are not wrapped in an undo block of their own here: a mutator that forgot to open one is the thing to find.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import event, given
from hypothesis import strategies as st
from maptasker.src.core import maputil2
from maptasker.src.core.actionc import action_codes
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import sessundo
from maptasker.src.mapops import mapfix, mapswap, mapswap_action

from tests.fuzzing import fuzz
from tests.test_fuzz_backup import _SYNTHETIC, backups
from tests.test_fuzz_roundtrip import EDITS, FLASH, NAMES, a_loaded_backup

if TYPE_CHECKING:
    from pathlib import Path

NOTIFY = next(key for key, entry in action_codes.items() if entry.name == "Notify")


def swap_flashes(_index: int, _name: str) -> None:
    """Replace: every Flash becomes a Notify, as ticked in the preview."""
    plan = mapswap_action.plan_action_swap(FLASH, NOTIFY, state=PrimeItems)
    mapswap.apply(plan, state=PrimeItems)


def fix_findings(_index: int, _name: str) -> None:
    """Fix Findings: every repair the Health Check offers."""
    mapfix.apply(mapfix.plan_fixes(state=PrimeItems), state=PrimeItems)


BULK = {function.__name__: function for function in (swap_flashes, fix_findings)}
EVERY_EDIT = {**EDITS, **BULK}


def the_file() -> str:
    """The configuration as Save To Current File writes it."""
    return maputil2.render_full_backup_xml(state=PrimeItems)


def the_checkpoint_form() -> str:
    """And as a checkpoint holds it: the same render, without the indentation."""
    return maputil2.render_full_backup_xml(indent=False, state=PrimeItems)


@st.composite
def sessions(draw: st.DrawFn) -> list[tuple[str, int, str]]:
    """A session: edits of any editor, with Undo and Redo pressed in between, in any order."""
    steps = st.one_of(
        st.tuples(st.sampled_from(sorted(EVERY_EDIT)), st.integers(min_value=0, max_value=50), NAMES),
        st.tuples(st.sampled_from(["undo", "redo"]), st.just(0), st.just("")),
    )
    return draw(st.lists(steps, min_size=1, max_size=14))


def _check_the_buttons() -> None:
    assert sessundo.can_undo(PrimeItems) == bool(PrimeItems.undo_history.undo)
    assert sessundo.can_redo(PrimeItems) == bool(PrimeItems.undo_history.redo)
    assert sessundo.can_undo(PrimeItems) == bool(sessundo.next_undo_label(PrimeItems))
    assert sessundo.can_redo(PrimeItems) == bool(sessundo.next_redo_label(PrimeItems))


def _play(session: list[tuple[str, int, str]]) -> None:
    """Run the session against the loaded backup, checking every step against what the steps before it left.

    `states` is the file at each depth of the undo stack along the line walked so far: depth 0 is what was loaded.
    An edit that makes several checkpoints leaves the depths between them unrecorded, and those are not checked.
    """
    states: dict[int, str] = {0: the_file()}
    depth = lambda: len(PrimeItems.undo_history.undo)
    assert not sessundo.can_undo(PrimeItems)

    for which, index, name in session:
        if which in {"undo", "redo"}:
            before = depth()
            done, message = (sessundo.undo if which == "undo" else sessundo.redo)(PrimeItems)
            moved = (before > 0) if which == "undo" else bool(PrimeItems.undo_history.redo) or done
            event(f"{which}: {'done' if done else 'nothing to do'}")
            assert done == moved, message
            if done:
                expected = states.get(depth())
                if expected is not None:
                    assert the_file() == expected, (
                        f"{which} did not give back the file that was there at depth {depth()}"
                    )
        else:
            had, was = depth(), the_checkpoint_form()
            EVERY_EDIT[which](index, name)
            changed = the_checkpoint_form() != was
            event(f"{which}: {'changed' if changed else 'no change'}")
            assert (depth() > had) == changed, (
                f"{which} {'changed the configuration and left nothing to undo' if changed else 'left a step to undo'}"
            )
            if changed:
                for deeper in [key for key in states if key > had]:
                    del states[deeper]  # a new edit ends the line that Redo was on
                states[depth()] = the_file()
        _check_the_buttons()

    # However the session went: undo to the start is the file that was loaded, and redo to the end is where it was.
    final, steps = the_file(), depth()
    while sessundo.can_undo(PrimeItems):
        sessundo.undo(PrimeItems)
    assert the_file() == states[0], "undoing everything did not give back the file that was loaded"
    if PrimeItems.undo_history.redo:
        redoable = len(PrimeItems.undo_history.redo)
        while sessundo.can_redo(PrimeItems):
            sessundo.redo(PrimeItems)
        assert depth() == redoable
        assert the_file() == states.get(depth(), the_file())
    del final, steps


@fuzz(120)
@given(session=sessions())
def test_undo_and_redo_give_back_exactly_the_file_that_was_there(session: list[tuple[str, int, str]]) -> None:
    with a_loaded_backup(_SYNTHETIC) as path:
        assert path
        _play(session)


@fuzz(60)
@given(data=backups(), session=sessions())
def test_undo_and_redo_hold_on_a_spoiled_backup_too(data: bytes, session: list[tuple[str, int, str]]) -> None:
    """The same, on a backup the loader accepts that is not the tidy one: odd ids, empty Projects, missing members."""
    with a_loaded_backup(data) as path:
        if path:
            _play(session)


@pytest.mark.parametrize("which", sorted(EVERY_EDIT))
def test_each_edit_alone_can_be_undone_and_redone_exactly(which: str) -> None:
    """The cases the draw has to hit, one at a time so a failure names the editor."""
    with a_loaded_backup(_SYNTHETIC) as path:
        assert path
        loaded = the_file()
        EVERY_EDIT[which](0, "Edited")
        edited = the_file()

        _play_back(loaded, edited, changed=loaded != edited)


def _play_back(loaded: str, edited: str, *, changed: bool) -> None:
    """Undo every step the edit left, to the loaded file; redo them all, to the edited one.

    More than one step when the edit is several mutators the dialog runs in a row (Add Task registers the Task and
    then attaches it to its Project); the dialog opens one block around both, which the driver does not.
    """
    steps = len(PrimeItems.undo_history.undo)
    assert (steps > 0) == changed
    for _ in range(steps):
        assert sessundo.undo(PrimeItems)[0]
    assert the_file() == loaded
    for _ in range(steps):
        assert sessundo.redo(PrimeItems)[0]
    assert the_file() == edited


def test_an_edit_made_after_an_undo_ends_the_line_redo_was_on(tmp_path: Path) -> None:
    with a_loaded_backup(_SYNTHETIC) as path:
        assert path
        EVERY_EDIT["add_project"](0, "First")
        sessundo.undo(PrimeItems)
        assert sessundo.can_redo(PrimeItems)

        EVERY_EDIT["add_project"](0, "Second")

        assert not sessundo.can_redo(PrimeItems)
        assert "Second" in the_file()
        assert "First" not in the_file()


# ##################################################################################
# What the property found, stated as an example
# ##################################################################################
def test_switching_a_project_off_is_a_step_undo_takes_back() -> None:
    """The Enabled switch in Edit Project writes to the live configuration at once, and used to leave nothing to undo."""
    from maptasker.src.edit import projedit

    with a_loaded_backup(_SYNTHETIC) as path:
        assert path
        name = sorted(entry["name"] for entry in PrimeItems.tasker_root_elements["all_projects"].values())[0]
        edited = projedit.load_project_for_edit(name, state=PrimeItems)
        assert edited
        loaded = the_file()

        projedit.set_project_enabled(edited, False, state=PrimeItems)

        assert sessundo.next_undo_label(PrimeItems) == f"Disable Project '{name}'"
        assert the_file() != loaded
        assert sessundo.undo(PrimeItems)[0]
        assert the_file() == loaded
