"""mapswap: bulk replace over the loaded configuration -- one action, argument, context or variable for another.

What is left here is what the four operations share at the end: the preview rows, the saved report and
apply(), which carries a Plan out inside one undo.  The operations themselves are in their own modules:

    mapswap_action      Task action for Task action
    mapswap_condition   Profile context for Profile context
    mapswap_argument    set or edit one argument of every action of a code
    mapswap_rename      rename or fold a variable

built on mapswap_model (Site, Change, Skip and Plan, and the argument carry-over every swap uses) and
mapswap_sites (reading and writing the one place a Change points at).
"""

#! /usr/bin/env python3

#                                                                                        #
# mapswap: bulk replace over the loaded configuration, rather than over rendered text.   #
#                                                                                        #
# Four operations, one machinery.  Swap every Task action of one code for another; set  #
# or edit one argument of every action of a code; swap every Profile context of one kind #
# for another; rename every use of a variable, or fold it into another variable.  They   #
# share the dialog, the preview, the report and the apply path, and nothing below that.  #
# Three of them are STRUCTURAL (a different element, holding a different set of children #
# that mean different things) and one -- the variable rename -- is TEXTUAL (one string   #
# rewritten in place, every field keeping its meaning).                                  #
#                                                                                        #
# Same contract as healthck / varxref / mapfind -- reads PrimeItems.tasker_root_elements #
# and nothing else, no GUI import, identity from mapjump.  What differs is that this one #
# WRITES, and four rules follow from that:                                               #
#                                                                                        #
#   NOTHING IS APPLIED UNSEEN.  A report that is 90% right is useful; a replace that is  #
#   90% right is a corrupted configuration the user cannot spot by looking.  plan() and  #
#   apply() are separate, apply() only ever takes a plan(), and every planned change is  #
#   a clickable mapjump Row before it is a change.                                       #
#                                                                                        #
#   ONE SCANNER.  Finding the places and rewriting them must be one pass, or the two     #
#   drift and the preview says 14 places while 12 get changed -- silently.  So there is  #
#   no scanner here: mapfind and varxref are asked where things are, and each carries    #
#   the element handle its own reports never needed.                                     #
#                                                                                        #
#   ONE UNDO.  A hundred-site rename is one thing the user did, so the whole of apply()  #
#   runs inside a single re-entrant sessundo.undoable block.                             #
#                                                                                        #
#   ONLY WHAT IS ON SCREEN.  With a single Project/Profile/Task/Scene selected, both     #
#   operations reach that object and no further (mapjump.current_scope), and say so --   #
#   in the plan, in the saved report, and in the Undo label.                             #
#                                                                                        #
# What cannot be reached is reported rather than dropped: a variable a plugin produces   #
# without naming it, a target built at run time ('Variable Set %(%which)'), a plugin     #
# payload bundles.json has no definition for.  A silent skip is the worst thing this module #
# could do -- the user reads "23 changed", believes the job done, and the two it could   #
# not touch are the two that now disagree with the other twenty-one.                     #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

from typing import TYPE_CHECKING

from maptasker.src.core import clock, maputil2
from maptasker.src.core.mapjump import Row, text_report
from maptasker.src.core.maputils import append_to_filename
from maptasker.src.core.outdir import output_path
from maptasker.src.core.sysconst import SWAP_FILE, logger
from maptasker.src.edit import sessundo

if TYPE_CHECKING:
    from maptasker.src.core.primitem import RunState
from maptasker.src.mapops.mapswap_action import swap_one_action
from maptasker.src.mapops.mapswap_condition import swap_one_condition
from maptasker.src.mapops.mapswap_model import ACTION_ELEMENT, DECLARATION, PROFILE_CONDITION, Change, Plan
from maptasker.src.mapops.mapswap_sites import write_site


# ##################################################################################
# Preview, and then -- separately -- apply.
# ##################################################################################
def report_rows(plan: Plan) -> list[Row]:
    """The plan as mapjump Rows: skips first, then changes grouped by Project and Task.

    Skips first because they are the part the user must read and the part they will not
    scroll back up for.  Rows rather than a string so the preview is clickable in the Map
    the same way a health-check finding is -- which for this feature is not a nicety: the
    only way to judge 'should this one be changed' is to go and look at it.
    """
    rows: list[Row] = [Row(plan.what), Row("")]

    rows.extend(Row(f"  {warning}") for warning in plan.warnings)

    if plan.skips:
        rows.extend((Row(""), Row(f"CANNOT BE CHANGED ({len(plan.skips)})")))
        for skip in plan.skips:
            rows.append(Row(f"  {skip.where.label}", skip.where))
            rows.append(Row(f"      {skip.explanation}"))

    if not plan.changes:
        rows.extend((Row(""), Row("Nothing to change.")))
        return rows

    rows.extend((Row(""), Row(f"WOULD CHANGE ({len(plan.selected)} of {len(plan.changes)} ticked)")))

    # Grouped by Project, in the order the objects came out of the index, so the list reads
    # in the same order as the Map the user is about to click into.
    current_project = None
    for position, change in enumerate(plan.changes):
        project = change.site.where.project
        if project != current_project:
            current_project = project
            rows.append(Row(f"  Project '{project}'" if project else "  No Project"))
        tick = "[x]" if position in plan.selected else "[ ]"
        rows.append(Row(f"    {tick} {change.site.where.label}", change.site.where))
        rows.append(Row(f"        {change.before}  ->  {change.after}"))
        if change.note:
            rows.append(Row(f"        {change.note}"))

    return rows


def write_swap_report(rows: list[Row], state: RunState) -> str:
    """Save the preview as text, the way varxref and mapfind save theirs.

    Worth having for the plan the user did NOT apply as much as the one they did: a
    hundred-row preview is a work list, and 'which ones did I decide to leave' does not
    survive closing the dialog otherwise.
    """
    stamp = clock.now().strftime("_%m-%d-%Y_%H-%M-%S")
    file_name = append_to_filename(SWAP_FILE, stamp)
    if not file_name:
        return ""
    file_path = output_path(file_name, state=state)
    try:
        with open(file_path, "w", encoding="utf-8") as output_file:
            output_file.write(text_report(rows))
    except OSError as error:
        logger.error(f"Replace report could not be written: {error}")
        return ""
    return file_path


def apply(plan: Plan, state: RunState) -> tuple[int, list[str]]:
    """Make the selected changes.  Returns (how many were made, errors).

    ONE undo block around the whole thing, and the outermost one:

        with sessundo.undoable(plan.what):
            ...

    A rename touching 60 sites is one thing the user did.  sessundo is re-entrant
    precisely so that a bulk operation calling per-item mutators still costs one press of
    Undo -- the same reason delete-a-Project does not cost ten -- and its render-and-
    compare means a plan whose every change was unticked leaves no entry behind.

    Re-checks each site is still attached to the tree before writing (apply skips what it finds detached):
    the preview can sit on screen while the user edits a Task in another dialog, and an
    element deleted underneath a plan must not be resurrected by writing to it.

    Order within the block matters in one case only: a variable rename must rewrite the
    <Variable> declaration LAST.  If it goes first and something later raises, the file
    holds a declaration for a name nothing uses and no declaration for the name
    everything uses -- the one intermediate state that survives as a plausible-looking
    configuration.
    """
    changes = [change for position, change in enumerate(plan.changes) if position in plan.selected]
    if not changes:
        return 0, []

    errors: list[str] = []
    changed = 0

    # The declaration goes last.  Ordering by kind rather than by leaving the caller to
    # order the list, so that a plan assembled in any order still applies in a safe one.
    changes.sort(key=lambda change: change.site.kind == DECLARATION)

    attached = maputil2.attached_elements(state=state)

    with sessundo.undoable(plan.what, state=state):
        for change in changes:
            if id(change.site.element) not in attached:
                errors.append(
                    f"{change.site.where.label}: no longer in the configuration -- it was deleted or "
                    f"reloaded while this preview was open.  Skipped.",
                )
                continue
            try:
                _apply_one(change, state=state)
            except (AttributeError, KeyError, ValueError) as failure:
                errors.append(f"{change.site.where.label}: {failure}")
                continue
            changed += 1

    return changed, errors


def _apply_one(change: Change, state: RunState) -> None:
    """Perform one planned change.  Raises rather than reporting; apply() catches."""
    if change.site.kind == ACTION_ELEMENT:
        swap_one_action(change.site.element, change.site.new_key, change.site.carry, state=state)
        return
    if change.site.kind == PROFILE_CONDITION:
        swap_one_condition(change.site.element, change.site.new_key, change.site.carry, state=state)
        return
    write_site(change.site, state=state)
