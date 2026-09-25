"""The one folder every report, export and view file is written to."""

#! /usr/bin/env python3

#                                                                                      #
# outdir: where MapTasker writes the files it produces for the user to read.           #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
#
# Health Check, Fix, Replace, Refactor, Find, Variable Cross-Reference, Task Flow,
# Compare and Timeline reports, the AI analysis, the Map (MapTasker.html) and Diagram
# (MapTasker_Map.txt) files the views are drawn from, their exports, and the default
# location of a standalone Project/Profile/Task/Scene export all used to go to the current
# directory -- wherever MapTasker happened to be started from.  That scattered them across
# whatever folder a terminal was sitting in, and filled a development checkout's root with
# timestamped reports.
#
# They go to one folder now: the 'output_directory' setting, or, when that is empty, a
# MapTasker folder in the user's Documents (platformdirs finds it on each system).  A
# relative setting is taken relative to the current directory, so "." puts everything back
# where it used to go.
#
# What is NOT moved: the settings file, the Applications cache, the Timeline history and the
# MapTasker_Backups safety copies.  Those are the program's own remembered state rather than
# output, and moving them would lose what earlier runs had saved.
from __future__ import annotations

from pathlib import Path

import platformdirs

from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import logger

# The folder made inside the user's Documents when no output folder has been chosen.
OUTPUT_FOLDER_NAME = "MapTasker"


def default_output_directory() -> Path:
    """The folder used when no output folder has been chosen: Documents/MapTasker."""
    return platformdirs.user_documents_path() / OUTPUT_FOLDER_NAME


def output_directory() -> Path:
    """The folder to write output to, made if it is not there yet.

    Falls back to the current directory, with a warning in the log, when the chosen folder
    cannot be made -- a drive that is no longer mounted, a path that names a file, a folder
    without write permission.  A report the user asked for is worth more in an unexpected
    place than not written at all.
    """
    chosen = PrimeItems.program_arguments.output_directory
    folder = Path(chosen).expanduser() if chosen else default_output_directory()
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        logger.warning(f"Output folder '{folder}' cannot be used ({error}).  Writing to the current directory.")
        return Path.cwd()
    return folder


def output_path(file_name: str) -> str:
    """The full path file_name is written to (and read back from) in the output folder."""
    return str(output_directory() / file_name)


def normalize_output_directory(text: str) -> tuple[str, str]:
    """Check a folder the user typed in, and answer (the setting to store, an error message).

    Empty text is the default folder and is stored as "".  Anything else is expanded ("~")
    and made absolute, so the stored setting does not quietly change meaning when MapTasker
    is next started from somewhere else.  The folder is made if it does not exist, which is
    also how an unusable one is caught here rather than at the first report.

    On success the error message is "".  On failure the setting is "" and should be ignored.
    """
    text = text.strip()
    if not text:
        return "", ""
    folder = Path(text).expanduser().resolve()
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        return "", f"Output folder '{folder}' cannot be used: {error.strerror or error}"
    return str(folder), ""
