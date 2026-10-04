"""What changed since <date>: the comparison that reads the configuration history."""

#! /usr/bin/env python3

#                                                                                      #
# timecomp: answer "what changed in my configuration since <date>" by comparing the     #
#           configuration loaded now with the one the history (timeline) held then.     #
#                                                                                      #
# Split out of timeline, which keeps the history itself -- snapshotting each load, and    #
# finding the snapshot nearest a date.  The comparison needs diffload to read a snapshot   #
# back in, and diffload loads through taskerd, which records every load in timeline: so   #
# with both in one module, timeline imported diffload from inside two functions to avoid   #
# importing itself.  Here the dependency simply points the one way -- timecomp imports     #
# timeline and diffload, and neither imports it.                                          #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
#
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from maptasker.src import clock, timeline
from maptasker.src.diffload import current_configuration, load_for_comparison
from maptasker.src.sysconst import logger
from maptasker.src.xmldiff import compare

if TYPE_CHECKING:
    from maptasker.src.primitem import RunState
    from maptasker.src.xmldiff import Configuration


def configuration_of(snapshot: timeline.Snapshot, state: RunState) -> tuple[Configuration | None, str]:
    """One snapshot as a comparison side.  Returns (Configuration, "") or (None, message).

    Goes through diffload.load_for_comparison, so a snapshot that will not parse produces
    the same message a picked file would, and the loaded configuration is left alone the
    same way.  The path on the returned side is the snapshot's label rather than the
    temporary file's name, which exists for a few milliseconds and would tell the reader
    of the report nothing.
    """
    try:
        with timeline.expanded(snapshot) as temporary:
            configuration, message = load_for_comparison(temporary, state=state)
    except OSError as error:
        logger.error(f"Timeline snapshot could not be expanded: {error}")
        return None, f"The snapshot from {snapshot.label()} could not be read.  ({error})"
    if configuration is None:
        return None, message
    return configuration._replace(path=snapshot.label(), when=snapshot.when), ""


@dataclass(frozen=True)
class Comparison:
    """The answer to "what changed since <date>", or why there isn't one.

    'problem' set means there is no report and it says why, in words fit to put in front
    of the user.  'note' is for a report that exists but comes with a caveat -- the usual
    one being that the history did not reach as far back as was asked for.
    """

    report: str = ""
    counts: dict = field(default_factory=dict)
    older: timeline.Snapshot | None = None
    note: str = ""
    problem: str = ""

    @property
    def nothing_changed(self) -> bool:
        """A report that ran and found no differences at all."""
        return bool(self.report) and not any(self.counts.values())


def changes_since(cutoff: datetime | None, newer: Configuration | None = None, *, state: RunState) -> Comparison:
    """Compare the configuration as it stood at `cutoff` against the one loaded now.

    A cutoff of None means the whole history -- the oldest configuration held.  That is
    "All" in the picker, and it is not the same as passing a very old date: asking for
    everything and being given everything is the answer, so it carries no note, whereas
    asking for a year ago and only having a fortnight is worth saying out loud.

    THE NEWER SIDE IS THE LIVE CONFIGURATION, not the newest snapshot.  Those are the same
    thing the moment a file is loaded, and they stop being the same as soon as anything is
    edited -- so using the live one means "what changed this week" includes what changed
    in the last five minutes, which is the answer the question wants.  Pass `newer`
    explicitly to compare two points in the past instead.

    Falls back to the oldest snapshot held when the history does not reach back to
    `cutoff`, and says so in 'note' rather than quietly answering a different question.
    """
    held = timeline.snapshots()
    if not held:
        return Comparison(problem="No configuration history has been recorded yet.")

    note = ""
    older_snapshot = held[0] if cutoff is None else timeline.since(cutoff)
    if older_snapshot is None:
        older_snapshot = held[0]
        note = (
            "The history does not reach back that far.  Comparing against the oldest "
            f"configuration held instead: {older_snapshot.described()}."
        )

    newer = newer if newer is not None else current_configuration(state=state)
    if not newer.tables.get("all_tasks"):
        return Comparison(problem="No XML file has been loaded.  Get an XML file first.")

    older_configuration, message = configuration_of(older_snapshot, state=state)
    if older_configuration is None:
        return Comparison(problem=message)

    report, counts = compare(older_configuration, newer)
    return Comparison(report=report, counts=counts, older=older_snapshot, note=note)


def changes_over_last(days: int, newer: Configuration | None = None, *, state: RunState) -> Comparison:
    """changes_since, counted back in whole days -- "this week" is days=7."""
    return changes_since(clock.now() - timedelta(days=days), newer, state=state)
