"""Keep a compressed history of every configuration loaded, so the diff can look backwards."""

#! /usr/bin/env python3

#                                                                                      #
# timeline: snapshot each backup as it is loaded, and answer "what changed in my        #
#           configuration since <date>" from that history.                             #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
#
# WHAT THIS ADDS TO THE COMPARISON THAT ALREADY EXISTS
#
# xmldiff compares two configurations and diffload gets the second one in hand.  Both
# already work; what they cannot do is answer the question people actually have, which is
# not "how do these two files differ" but "what did I change this week".  Answering that
# with the file picker means knowing which file on disk was the configuration as it stood
# last Tuesday -- and the whole reason the question gets asked is that nobody knows.
#
# So this keeps the older side itself.  Every load is written to a history folder, gzipped,
# and the comparison picks its own older side out of that by date.  Nothing else about the
# comparison changes: the report, the report writer and the ordering rules are xmldiff's
# and diffload's, unchanged.
#
# WHY A LOAD IS THE RIGHT MOMENT
#
# It is the only moment the whole configuration is known to be on disk, complete, and
# agreed with what the user is about to look at.  Snapshotting on save would miss every
# configuration edited on the device and merely loaded here, which is most of them.
#
# WHAT IS NOT SNAPSHOTTED, AND WHY IT MATTERS
#
# The comparison feature loads a file too -- diffload parses the file being compared
# against through the very same taskerd path this hooks into.  That load is not a
# configuration the user opened, it is one they pointed at for a moment, and recording it
# would put a file nobody is working on into the history of the file they are.  Worse, it
# would do so every time anyone ran a comparison.  suppressed() is what diffload wraps its
# isolation window in to prevent that; see recording_suppressed below for why this is a
# flag and not a "was it the loaded file" test.
#
# SIZE
#
# A real Tasker backup in this repo's samples is 8.4 MB and gzips to 951 KB -- 11%, in
# under a tenth of a second.  Thirty of them is under 30 MB, which is what MAX_SNAPSHOTS
# is set against.  Identical content is never stored twice (see record), so a history of
# thirty entries is thirty configurations that actually differ, not thirty loads.
#

from __future__ import annotations

import contextlib
import gzip
import hashlib
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from maptasker.src.editcommon import sanitize_filename
from maptasker.src.sysconst import logger

if TYPE_CHECKING:
    from maptasker.src.xmldiff import Configuration

# Where the history lives, in the current runtime directory -- the same place every other
# thing this program writes for the user goes (the map, the health check, the comparison
# report).  Named for what a user would look for, like presave.BACKUP_FOLDER.
HISTORY_FOLDER = "MapTasker_Timeline"

# How many configurations to keep.  Thirty differing configurations is a long way back for
# anyone who edits Tasker daily, and at the measured compression it is under 30 MB.  Same
# kind of cap, and the same reasoning, as presave.MAX_COPIES_PER_FILE.
MAX_SNAPSHOTS = 30

# <stamp>__<source name>__<hash>.xml.gz -- everything about a snapshot is in its name, so
# there is no index file to fall out of step with the folder, and deleting one by hand
# breaks nothing.  Date first and zero padded so a plain listing is in chronological order.
_STAMP_FORMAT = "%Y%m%d_%H%M%S"
_SUFFIX = ".xml.gz"
_NAME_RE = re.compile(r"^(?P<stamp>\d{8}_\d{6})__(?P<source>.*)__(?P<digest>[0-9a-f]{12})\.xml\.gz$")

# Enough of a SHA-256 to tell two configurations apart.  Not a security boundary -- it
# answers "is this the same file I already have", where the alternative being guarded
# against is an accidental duplicate, not a forged one.
_DIGEST_LENGTH = 12

# Read in chunks rather than whole: the files are megabytes and the digest is taken on
# every load, including the one at startup.
_CHUNK = 1 << 20

# See suppressed().  A plain module flag rather than a parameter because the caller that
# has to suppress it (diffload) and the caller that does the recording (taskerd, from
# inside get_the_xml_data) do not speak to each other -- there is no argument to thread
# from one to the other, which is the same reason sessundo's history is saved and restored
# around that window rather than passed through it.
recording_suppressed = False


@dataclass(frozen=True)
class Snapshot:
    """One configuration as it stood at one moment, sitting in the history folder."""

    path: Path
    when: datetime
    source: str
    digest: str

    def label(self) -> str:
        """How this snapshot names itself in a report header.

        The date is deliberately NOT in here.  xmldiff's header prints the side's own
        'when' in brackets after this, so spelling it here too would print it twice --
        what this has to add is that the older side is a kept copy rather than a file
        sitting on disk under that name today.
        """
        return f"{self.source} (from the configuration history)"

    def described(self) -> str:
        """This snapshot in one phrase, date included -- for a message with no header."""
        return f"{self.source}, {self.when:%d-%b-%Y %H:%M:%S}"


@contextlib.contextmanager
def suppressed() -> None:
    """Do not record loads that happen inside this block.

    For diffload's isolation window.  The file being compared against goes through
    taskerd.get_the_xml_data like any other load, and without this every comparison would
    file the other file into the history of the one the user has open.

    Restores the previous value rather than clearing the flag, so a nested use -- which
    nothing does today -- could not switch recording back on for its outer caller.
    """
    global recording_suppressed  # noqa: PLW0603
    previous = recording_suppressed
    recording_suppressed = True
    try:
        yield
    finally:
        recording_suppressed = previous


def _history_folder(*, create: bool) -> Path | None:
    """The history folder, made if asked for and if it can be.  None when it cannot.

    Never raises: a history that cannot be written is a feature that is not available,
    not a load that fails.  The same reasoning as presave's -- see its module header on
    why a failed safety copy does not stop the save.
    """
    folder = Path.cwd() / HISTORY_FOLDER
    if create:
        try:
            folder.mkdir(exist_ok=True)
        except OSError as error:
            logger.error(f"Timeline history folder could not be created: {error}")
            return None
    return folder if folder.is_dir() else None


def _digest_of(file_path: str) -> str:
    """The first _DIGEST_LENGTH hex characters of the file's SHA-256, or "" if unreadable."""
    hasher = hashlib.sha256()
    try:
        with Path(file_path).open("rb") as source_file:
            while chunk := source_file.read(_CHUNK):
                hasher.update(chunk)
    except OSError as error:
        logger.error(f"Timeline could not read {file_path}: {error}")
        return ""
    return hasher.hexdigest()[:_DIGEST_LENGTH]


def _snapshot_from(path: Path) -> Snapshot | None:
    """Read a snapshot's facts back out of its file name, or None if it is not one of ours."""
    match = _NAME_RE.match(path.name)
    if match is None:
        return None
    try:
        when = datetime.strptime(match["stamp"], _STAMP_FORMAT)  # noqa: DTZ007
    except ValueError:
        return None
    return Snapshot(path=path, when=when, source=match["source"], digest=match["digest"])


def snapshots() -> list[Snapshot]:
    """Every snapshot in the history, oldest first.

    Anything in the folder that is not one of ours is ignored rather than reported: the
    folder is in the user's own working directory and they are entitled to put things in
    it.  Sorted by the timestamp in the name, not by the file's own mtime, which a copy
    or a sync would rewrite.
    """
    folder = _history_folder(create=False)
    if folder is None:
        return []
    try:
        names = list(folder.iterdir())
    except OSError as error:
        logger.error(f"Timeline history could not be listed: {error}")
        return []
    found = [snapshot for snapshot in (_snapshot_from(path) for path in names) if snapshot is not None]
    return sorted(found, key=lambda snapshot: (snapshot.when, snapshot.path.name))


def _prune() -> None:
    """Drop the oldest snapshots beyond MAX_SNAPSHOTS."""
    existing = snapshots()
    for snapshot in existing[: max(0, len(existing) - MAX_SNAPSHOTS)]:
        try:
            snapshot.path.unlink()
        except OSError as error:
            logger.error(f"Timeline snapshot could not be pruned: {error}")


def record(file_path: str, *, when: datetime | None = None) -> Snapshot | None:
    """Add this configuration to the history, unless it is already the latest entry.

    Returns the Snapshot written, or None when nothing was written -- which is the
    ordinary case for reloading a file that has not changed, and is also what every
    failure returns.  Callers are not expected to check: this is a side effect of loading
    a file, and a history that could not be written must not disturb the load that was.

    THE SAME CONFIGURATION IS NEVER STORED TWICE IN A ROW.  Loading a file, closing the
    program and loading it again is two loads of one configuration, and a history with
    both in it would report an hour in which nothing changed as an entry worth having.
    Compared by content, so this also covers loading the same configuration by two
    different paths -- a backup and the timestamped copy "Save To Current File" made of
    it are the same configuration under two names.
    """
    if recording_suppressed or not file_path:
        return None

    digest = _digest_of(file_path)
    if not digest:
        return None

    existing = snapshots()
    if existing and existing[-1].digest == digest:
        return None

    folder = _history_folder(create=True)
    if folder is None:
        return None

    when = when or datetime.now()  # noqa: DTZ005
    source = sanitize_filename(Path(file_path).name, "configuration")
    target = folder / f"{when.strftime(_STAMP_FORMAT)}__{source}__{digest}{_SUFFIX}"
    try:
        with Path(file_path).open("rb") as source_file, gzip.open(target, "wb") as compressed:
            shutil.copyfileobj(source_file, compressed, _CHUNK)
    except OSError as error:
        logger.error(f"Timeline snapshot could not be written: {error}")
        with contextlib.suppress(OSError):
            target.unlink()
        return None

    _prune()
    return _snapshot_from(target)


def since(cutoff: datetime) -> Snapshot | None:
    """The configuration as it stood at `cutoff` -- the newest snapshot taken no later.

    None when the history does not reach back that far.  Deliberately not "the oldest
    snapshot instead": a report headed "since last week" that quietly compared against
    three months ago would be answering a question nobody asked.  The caller says so and
    offers what there is -- see earliest().
    """
    reachable = [snapshot for snapshot in snapshots() if snapshot.when <= cutoff]
    return reachable[-1] if reachable else None


def earliest() -> Snapshot | None:
    """The oldest snapshot held, or None when the history is empty."""
    held = snapshots()
    return held[0] if held else None


@contextlib.contextmanager
def _expanded(snapshot: Snapshot) -> str:
    """The snapshot decompressed to a temporary .xml file, removed on the way out.

    A file on disk because that is what the loader takes: diffload hands taskerd a path
    and taskerd parses it (and may rewrite it -- see diffload._scratch_copy, which is why
    handing it anything but a throwaway would be a mistake).  A decompressed snapshot is
    exactly that throwaway.
    """
    handle, temporary = tempfile.mkstemp(prefix="maptasker_timeline_", suffix=".xml")
    os.close(handle)
    try:
        with gzip.open(snapshot.path, "rb") as compressed, Path(temporary).open("wb") as expanded:
            shutil.copyfileobj(compressed, expanded, _CHUNK)
        yield temporary
    finally:
        with contextlib.suppress(OSError):
            Path(temporary).unlink()


def configuration_of(snapshot: Snapshot) -> tuple[Configuration | None, str]:
    """One snapshot as a comparison side.  Returns (Configuration, "") or (None, message).

    Goes through diffload.load_for_comparison, so a snapshot that will not parse produces
    the same message a picked file would, and the loaded configuration is left alone the
    same way.  The path on the returned side is the snapshot's label rather than the
    temporary file's name, which exists for a few milliseconds and would tell the reader
    of the report nothing.
    """
    # Lazy import to avoid a circular-import error: taskerd calls record() above, and
    # diffload imports taskerd (mirrors getbakup.get_backup_file()).
    from maptasker.src.diffload import load_for_comparison  # noqa: PLC0415

    try:
        with _expanded(snapshot) as temporary:
            configuration, message = load_for_comparison(temporary)
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
    older: Snapshot | None = None
    note: str = ""
    problem: str = ""

    @property
    def nothing_changed(self) -> bool:
        """A report that ran and found no differences at all."""
        return bool(self.report) and not any(self.counts.values())


def changes_since(cutoff: datetime | None, newer: Configuration | None = None) -> Comparison:
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
    # Lazy imports for the same reason as configuration_of's -- taskerd calls record().
    from maptasker.src.diffload import current_configuration  # noqa: PLC0415
    from maptasker.src.xmldiff import compare  # noqa: PLC0415

    held = snapshots()
    if not held:
        return Comparison(problem="No configuration history has been recorded yet.")

    note = ""
    older_snapshot = held[0] if cutoff is None else since(cutoff)
    if older_snapshot is None:
        older_snapshot = held[0]
        note = (
            "The history does not reach back that far.  Comparing against the oldest "
            f"configuration held instead: {older_snapshot.described()}."
        )

    newer = newer if newer is not None else current_configuration()
    if not newer.tables.get("all_tasks"):
        return Comparison(problem="No XML file has been loaded.  Get an XML file first.")

    older_configuration, message = configuration_of(older_snapshot)
    if older_configuration is None:
        return Comparison(problem=message)

    report, counts = compare(older_configuration, newer)
    return Comparison(report=report, counts=counts, older=older_snapshot, note=note)


def changes_over_last(days: int, newer: Configuration | None = None) -> Comparison:
    """changes_since, counted back in whole days -- "this week" is days=7."""
    return changes_since(datetime.now() - timedelta(days=days), newer)  # noqa: DTZ005


# ##################################################################################
# The periods the "Changes Since..." picker offers.
#
# Here rather than in the GUI because what "this month" MEANS is a decision about the
# data, not about the widget -- and because the label and the date it resolves to have to
# be decided in one place or they will disagree.
#
# TODAY is calendar, the rest are rolling.  That is deliberate and it is the way people
# actually ask: "what changed today" means since this morning, not since 24 hours ago,
# while "this week" on a Monday morning must not mean "since a few hours ago" -- which is
# what a calendar week would give, and it would look broken.  Each label says which it is,
# so nobody has to infer it.
# ##################################################################################
TODAY = "today"
THIS_WEEK = "week"
THIS_MONTH = "month"
ALL = "all"
ON_DATE = "date"

# In the order the picker offers them.  Untranslated here -- the GUI runs each through
# translate_string, the same as every other label it shows.
PERIOD_LABELS = {
    TODAY: "Today",
    THIS_WEEK: "This Week (last 7 days)",
    THIS_MONTH: "This Month (last 30 days)",
    ALL: "All (everything kept)",
    ON_DATE: "Since a specific date...",
}

_ROLLING_DAYS = {THIS_WEEK: 7, THIS_MONTH: 30}


def cutoff_for(period: str, *, on_date: date | None = None, now: datetime | None = None) -> datetime | None:
    """The moment a period starts, for changes_since.  None means the whole history.

    `on_date` is required for ON_DATE and ignored otherwise; a specific date starts at
    midnight on that day, so picking today's date and picking "Today" agree.

    An unknown period is treated as ALL rather than raising.  This is reached from a
    pulldown whose options this module supplies, so the only way to get here with
    something else is a bug -- and answering with more history than was asked for is a
    visibly odd report, where an exception is a dead button.
    """
    now = now or datetime.now()  # noqa: DTZ005
    if period == TODAY:
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period in _ROLLING_DAYS:
        return now - timedelta(days=_ROLLING_DAYS[period])
    if period == ON_DATE and on_date is not None:
        return datetime.combine(on_date, time.min)
    return None
