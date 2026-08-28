"""Keep a copy of whatever a save is about to overwrite."""

#! /usr/bin/env python3

#                                                                                      #
# presave: automatic safety copies, taken immediately before a save overwrites          #
#          something -- on this computer or on the Android device.                      #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
#
# A NOTE ON THE WORD "BACKUP"
#
# Everywhere else in this program a "backup" is the Tasker backup XML -- the file the user
# loads and edits.  It is not what this module makes.  What this makes is a copy of a file
# that is about to stop existing, so the user can get it back; the folder it goes in is
# named MapTasker_Backups because that is the word a user will look for, but in the code
# they are called safety copies to keep the two apart.
#
# WHAT IS ACTUALLY AT RISK, AND WHAT IS NOT
#
# Worth being precise about, because the three save buttons are not equally dangerous:
#
#   "Save To Current File" is already safe by construction and always was.  It never opens
#   the loaded file for writing; it writes a new, timestamped one beside it
#   (maputil2.write_full_backup_to_current_file).  There is nothing to lose, so there is
#   normally nothing to copy -- the guard is still wired in for the one case that can
#   collide, two saves landing in the same second and so on the same generated name.
#
#   "Save"/"Export" writes a standalone .tsk/.prf/.prj/.scn.xml to a path the user typed,
#   which may well already hold something.  This is a real overwrite.
#
#   "Save To Android" writes to a fixed path on the device -- /Tasker/projects/<name>.prj.xml
#   and its three siblings -- so saving a Project twice overwrites the first one, and
#   saving a Project whose name matches one already exported from Tasker overwrites that.
#   Nothing on the device is versioned and the file is out of reach once it is gone.  This
#   is the one the user cannot recover from on their own, which is why the copy for it is
#   pulled back off the device and kept HERE, where they can find it.
#
# The two overwrite cases already ask before they clobber (build_overwrite_confirm_dialog).
# Saying yes to that prompt is still irreversible, though, and it is the answer people give
# by reflex.  A copy taken first turns the reflex into something recoverable.
#
# WHY A FAILED COPY DOES NOT STOP THE SAVE
#
# It reports the failure and lets the save go ahead.  A save that refused to run because a
# safety copy could not be written would turn a full disk, or a folder the user cannot
# write to, into "MapTasker will not save my work" -- a bigger problem than the one being
# guarded against, and one with no obvious cause from the outside.  The copy is a seat
# belt, not an ignition interlock.
#

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

from maptasker.src.sysconst import logger

# The folder safety copies go in, created next to whatever is being overwritten so a copy
# is found where its original was rather than somewhere central the user never looks.
BACKUP_FOLDER = "MapTasker_Backups"

# How many copies of any one file to keep.  Enough that a bad save is still recoverable
# several saves later; few enough that repeatedly exporting the same Project cannot quietly
# fill a disk with near-identical XML.
MAX_COPIES_PER_FILE = 10

# The stamp appended to a copy's base name: MyProject.prj_20260820_143005.xml.  Date then
# time, zero padded, so a listing sorts by when it was taken -- the same scheme and the
# same reasoning as healthck.write_health_check_report and
# maputil2.TIMESTAMP_SUFFIX_RE's naming.
_STAMP_FORMAT = "%Y%m%d_%H%M%S"

# Characters no filesystem this runs on will accept.  A device path becomes a local
# filename below, and those are full of slashes.  Mirrors the sanitize_filename the four
# edit modules each keep their own copy of.
_ILLEGAL_IN_FILENAME = re.compile(r'[\\/:*?"<>|]')


def _stamped_name(file_name: str) -> str:
    """`file_name` with a timestamp on its base, keeping the whole compound extension.

    os.path.splitext only takes the last one off, so "Wake Up.tsk.xml" would become
    "Wake Up.tsk_20260820_143005.xml" -- the ".tsk" left stranded mid-name.  These files
    are all <name>.<kind>.xml, and the kind is part of what the file IS, so the split is
    made at the FIRST dot instead: "Wake Up_20260820_143005.tsk.xml", which still opens in
    whatever the original opened in.
    """
    stamp = datetime.now().strftime(_STAMP_FORMAT)  # noqa: DTZ005
    base, dot, extensions = file_name.partition(".")
    return f"{base}_{stamp}{dot}{extensions}" if dot else f"{base}_{stamp}"


def _copy_pattern(file_name: str) -> re.Pattern:
    """Matches every safety copy previously made of `file_name` -- for pruning.

    Built from the same two halves _stamped_name joins, so the two cannot drift: anything
    this matches is something that named it.
    """
    base, dot, extensions = file_name.partition(".")
    return re.compile(rf"^{re.escape(base)}_\d{{8}}_\d{{6}}{re.escape(dot + extensions)}$")


def _prune(folder: Path, file_name: str) -> None:
    """Delete the oldest safety copies of `file_name` beyond MAX_COPIES_PER_FILE.

    Sorted by name, not by modification time: the name carries the timestamp this module
    put there, and it cannot be changed by a file being copied, synced or restored the way
    an mtime can.  Only files this module's own naming produced are ever considered, so
    nothing the user put in the folder themselves can be caught by it.
    """
    pattern = _copy_pattern(file_name)
    try:
        copies = sorted(entry.name for entry in folder.iterdir() if pattern.match(entry.name))
    except OSError as error:
        logger.error(f"Safety copies in {folder} could not be listed: {error}")
        return

    for stale in copies[: max(0, len(copies) - MAX_COPIES_PER_FILE)]:
        try:
            (folder / stale).unlink()
        except OSError as error:
            logger.error(f"Old safety copy {stale} could not be removed: {error}")


def _backup_folder(beside: Path) -> Path | None:
    """The MapTasker_Backups folder next to `beside`, made if it isn't there yet."""
    folder = beside / BACKUP_FOLDER
    try:
        folder.mkdir(exist_ok=True)
    except OSError as error:
        logger.error(f"Safety copy folder {folder} could not be created: {error}")
        return None
    return folder


def backup_local_file(output_path: str) -> tuple[bool, str]:
    """Copy whatever is at `output_path` into MapTasker_Backups beside it, before a save
    overwrites it.

    Returns:
        (True, path of the copy) -- a copy was made.
        (True, "")               -- nothing was there to copy, which is the ordinary case
                                    for a save to a new name.  Not a failure.
        (False, error message)   -- there was something there and it could not be copied.
                                    The caller should say so and save anyway; see the
                                    module comment on why this never blocks a save.
    """
    if not output_path:
        return True, ""

    original = Path(output_path)
    try:
        if not original.is_file():
            return True, ""
    except OSError as error:  # An unreadable path, a broken mount -- unknowable, not absent.
        return False, str(error)

    folder = _backup_folder(original.parent)
    if folder is None:
        return False, f"could not create the {BACKUP_FOLDER} folder"

    destination = folder / _stamped_name(original.name)
    try:
        # copy2 rather than copy: it keeps the original's modification time, which is what
        # tells the user which of several copies is the one they are looking for.
        shutil.copy2(original, destination)
    except OSError as error:
        logger.error(f"Safety copy of {output_path} failed: {error}")
        return False, str(error)

    _prune(folder, original.name)
    return True, str(destination)


def save_android_safety_copy(device_path: str, content: bytes) -> tuple[bool, str]:
    """Keep the bytes that were at `device_path` on the Android device, before a Save To
    Android overwrites them, in MapTasker_Backups in the current directory.

    The copy is kept on this computer rather than beside the original on the device.  That
    is the whole point: the device has no versioning, no undo and no file manager the user
    is likely to go hunting in, and a second file left next to the first would be one more
    thing for Tasker to import by accident.  Here it sits alongside every other MapTasker
    output, and the device is left with exactly the one file the save intended.

    The name records where it came from -- Tasker_projects_MyProject_20260820_143005.prj.xml
    -- because a device path cannot be a filename and "which device folder was this?" is
    otherwise unanswerable.

    TAKES THE BYTES RATHER THAN FETCHING THEM.  Every caller has just read that path to ask
    whether anything is there to clobber (maputil2.read_android_file answers both questions
    from one GET), and reading it a second time here would mean a second round trip, a second
    chance for the two answers to disagree, and -- on the Tasker HTTP Server Example, whose
    /file handler runs Test File and flashes 'File doesn't exist' on every miss -- a second
    flash on the user's phone for a single save.

    Returns the same three outcomes backup_local_file does, with (True, "") covering the
    ordinary case of nothing having been at that path.
    """
    if not device_path or not content:
        return True, ""

    folder = _backup_folder(Path.cwd())
    if folder is None:
        return False, f"could not create the {BACKUP_FOLDER} folder"

    # "/Tasker/projects/My Project.prj.xml" -> "Tasker_projects_My Project.prj.xml", so the
    # copy says which folder on the device it was taken from.
    flattened = _ILLEGAL_IN_FILENAME.sub("_", device_path.strip("/"))
    destination = folder / _stamped_name(flattened)
    try:
        destination.write_bytes(content)
    except OSError as error:
        logger.error(f"Safety copy of {device_path} failed: {error}")
        return False, str(error)

    _prune(folder, flattened)
    return True, str(destination)
