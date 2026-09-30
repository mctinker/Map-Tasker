"""Keep the configuration history up to date from a folder of Tasker backups."""

#! /usr/bin/env python3

#                                                                                      #
# folderwatch: watch a folder for new Tasker backups and record each in the history    #
#              (timeline.py), so that "what changed since Tuesday" has an answer even  #
#              for the days MapTasker was not opened.                                  #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
#
# WHY THIS EXISTS
#
# The history (timeline.py) gets a snapshot only when a backup is LOADED.  Someone whose
# phone backs up every night into a synced folder, and who opens MapTasker once a week, has
# a history with one entry a week -- and the report meant to answer "what did I change on
# Wednesday" cannot, because Wednesday was never recorded.  Watching the folder records each
# backup as it arrives, whether or not MapTasker is running the GUI.
#
# THE THREE WAYS A FOLDER OF BACKUPS GOES WRONG
#
# 1. A file that is still being written.  A synced or copied backup appears in the folder
#    before it is whole.  A file modified within the last few seconds is left for the next
#    look, and one that is older is still parsed end to end before it is recorded: a
#    truncated XML file does not parse, and a history entry nobody can open is worse than a
#    gap.
# 2. A folder that already holds a year of backups.  Recording every one of them, each dated
#    by its file's modification time, would fill the history with configurations that were
#    never "loaded" and push out anything worth keeping (timeline caps it at MAX_SNAPSHOTS).
#    The first look records only the newest; what arrives after that is recorded as it does.
# 3. The same backup seen twice.  timeline.record never stores the same content twice in a
#    row, so looking again -- or a scheduled run that finds nothing new -- changes nothing.
#
# Polling, not the operating system's file notifications: those differ on each platform, are
# unreliable on the network and synced folders these backups usually land in, and would be a
# new dependency for something a look every minute does just as well.
#
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import ParseError

from maptasker.src import clock, timeline
from maptasker.src.sysconst import logger
from maptasker.src.xmldata import parse_tasker_xml

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

# How old a file has to be before it is taken to be finished being written.
SETTLE_SECONDS = 5

# How long to wait between looks at the folder.
DEFAULT_INTERVAL_SECONDS = 60

# What happened to a backup that was looked at.
RECORDED = "recorded"  # It is now the newest entry in the history.
UNCHANGED = "unchanged"  # It is the same configuration as the newest entry: nothing added.
INCOMPLETE = "incomplete"  # It is not a whole Tasker backup (yet): left out of the history.

# The root element every Tasker backup has.
_ROOT_TAG = "TaskerData"


@dataclass(frozen=True)
class Event:
    """One backup the watcher dealt with, and what came of it."""

    path: Path
    outcome: str
    snapshot: timeline.Snapshot | None = None


def backup_files(folder: Path) -> list[Path]:
    """The .xml files in `folder`, oldest first.  Not the ones in folders below it.

    Sorted by modification time and then by name, so two files written in the same instant
    come out in the same order every time.  A folder that cannot be listed is an empty one:
    the watcher is a background convenience and reports what it can, not a reason to stop.
    """
    try:
        candidates = [path for path in folder.iterdir() if path.suffix.lower() == ".xml" and path.is_file()]
    except OSError as error:
        logger.error(f"Folder {folder} could not be listed: {error}")
        return []

    def by_age(path: Path) -> tuple[int, str]:
        try:
            return path.stat().st_mtime_ns, path.name
        except OSError:
            return 0, path.name

    return sorted(candidates, key=by_age)


def newest_backup(folder: Path) -> Path | None:
    """The most recently modified .xml file in `folder`, or None if it holds none."""
    found = backup_files(folder)
    return found[-1] if found else None


def is_complete_backup(path: Path) -> bool:
    """Whether `path` is a whole Tasker backup: it parses end to end and is a <TaskerData>.

    A parse rather than a look at the first and last lines, because a half-copied file can
    have both and be missing the middle.  Never raises: a file that cannot be read is simply
    not a backup yet.
    """
    try:
        root = parse_tasker_xml(str(path)).getroot()
    except (ParseError, UnicodeDecodeError, OSError, DefusedXmlException) as error:
        logger.debug(f"{path} is not a complete Tasker backup: {error}")
        return False
    return root is not None and root.tag == _ROOT_TAG


@dataclass
class Watcher:
    """Looks at one folder, again and again, and records what is new in it.

    `settle` is how old a file must be to be trusted as finished.  `now` is the clock, given
    so a test can decide what time it is.  Nothing here sleeps: watch() does, and calls scan()
    between naps, so one look at a time can be tested.
    """

    folder: Path
    settle: float = SETTLE_SECONDS
    now: Callable[[], float] = time.time
    _seen: dict[Path, tuple[int, int]] = field(default_factory=dict, init=False)
    _looked: bool = field(default=False, init=False)

    def scan(self) -> list[Event]:
        """Look at the folder once and record every backup in it that is new or changed."""
        files = backup_files(self.folder)
        first_look = not self._looked
        self._looked = True
        # Forget files that have gone, so that one put back later is looked at afresh.
        self._seen = {path: signature for path, signature in self._seen.items() if path in files}

        waiting = []  # (path, signature, modification time), oldest first.
        for path in files:
            try:
                status = path.stat()
            except OSError:
                continue
            signature = (status.st_mtime_ns, status.st_size)
            if self._seen.get(path) == signature:
                continue
            # Modified within the last few seconds: perhaps still being written.  Not marked seen,
            # so the next look tries again.  A file dated in the FUTURE is not one of these --
            # it comes from a device whose clock is ahead of this one's, and waiting for this
            # clock to catch up would leave it out of the history altogether.  The parse in
            # is_complete_backup is what guards against a half-written one.
            if 0 <= self.now() - status.st_mtime < self.settle:
                continue
            waiting.append((path, signature, status.st_mtime))

        if first_look and waiting:
            # A folder that already holds old backups: start from the newest, not from all of them.
            for path, signature, _ in waiting[:-1]:
                self._seen[path] = signature
            waiting = waiting[-1:]

        events = []
        for path, signature, modified in waiting:
            self._seen[path] = signature
            if not is_complete_backup(path):
                events.append(Event(path, INCOMPLETE))
                continue
            # Dated by the file, but never later than now: a backup from a device with a fast
            # clock is not from the future, and a snapshot that was would sort after every real one.
            snapshot = timeline.record(str(path), when=clock.from_timestamp(min(modified, self.now())))
            events.append(Event(path, RECORDED if snapshot else UNCHANGED, snapshot))
        return events


def watch(
    folder: Path,
    *,
    interval: float = DEFAULT_INTERVAL_SECONDS,
    once: bool = False,
    on_event: Callable[[Event], None] = lambda _event: None,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Keep looking at `folder`, telling `on_event` about each backup dealt with.

    `once` looks a single time and returns -- what a scheduled job wants, since it is the
    schedule that does the repeating.  It trusts a file that is only just there, having
    nothing later to look again with; the parse in is_complete_backup is what stops a
    half-written one being recorded.  Otherwise this runs until interrupted (KeyboardInterrupt
    reaches the caller).
    """
    watcher = Watcher(folder, settle=0 if once else SETTLE_SECONDS)
    while True:
        for event in watcher.scan():
            on_event(event)
        if once:
            return
        sleep(interval)
