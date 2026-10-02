"""Run a Health Check, Compare, Changes Since, Export or folder watch from the command line."""

#! /usr/bin/env python3

#                                                                                      #
# clireports: the reports that do not need the window, run without one.                #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
#
#   maptasker -healthcheck -file backup.xml                 problems in one backup
#   maptasker -compare old.xml new.xml                      what differs between two
#   maptasker -changes_since week -file backup.xml          what changed over a period
#   maptasker -export map -format md -file backup.xml       the Map (or the diagram) as a file
#   maptasker -watch ~/TaskerBackups                        record each new backup in the history
#
# WHY THESE, AND WHY THEY CAN RUN WITHOUT THE WINDOW
#
# Each of these reads the configuration and writes text.  Health Check, Compare and Changes
# Since were built as pure functions over the loaded tables (healthck, xmldiff, timeline) and
# only the buttons that call them need a GUI.  Export needs a built Map, which is a build like
# any other, done here the way the GUI does it.  What was missing was a way to ask: someone who
# backs their phone up every night wants the nightly backup CHECKED, and nobody opens a window
# for that.
#
# WHAT A SCRIPT CAN RELY ON
#
#   * The report, and only the report, is on standard output.  Everything else -- what was
#     loaded, what was saved, a warning -- is on standard error, so `> report.txt` is a report.
#   * The exit code says what happened.  See the EXIT_* values below: 0 is "nothing to report",
#     10 is "the report found something", and the rest are failures, most of them the codes the
#     command line has always used (parsearg's epilog lists them).
#   * Nothing else changes.  No browser is opened, the settings file the GUI keeps is not
#     rewritten (PrimeItems.headless), and a load that fails leaves no error file behind for
#     the GUI to greet you with the next time you open it.
#
# This file is in the entry-point layer and nothing above NiceGUI is imported here, so a run
# starts without loading the GUI at all.
#
from __future__ import annotations

import argparse
import contextlib
import os
import platform
import re
import signal
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

from maptasker.src import (
    clock,
    console,
    diffload,
    folderwatch,
    healthck,
    mapexport,
    mapjump,
    timeline,
    xmldiff,
)
from maptasker.src.actionc import load_arg_specs
from maptasker.src.bildhtml import build_html
from maptasker.src.colrmode import set_color_mode
from maptasker.src.frontmtr import output_the_front_matter
from maptasker.src.getputer import save_restore_args
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.lineout import LineOut
from maptasker.src.mtexcept import MapTaskerError
from maptasker.src.outdir import normalize_output_directory
from maptasker.src.outline import outline_the_configuration
from maptasker.src.primitem import (
    MAP_OUTPUT_ATTRIBUTES,
    PrimeItems,
    PrimeItemsReset,
    clear_error,
    clear_single_items,
    initial_found_named_items,
    initial_tasker_root_elements,
    reset_attributes,
)
from maptasker.src.runcfg import current_config
from maptasker.src.sysconst import ERROR_FILE, TIMELINE_FILE, logger
from maptasker.src.taskerd import get_the_xml_data

if TYPE_CHECKING:
    from collections.abc import Iterator

# ##################################################################################
# The exit codes.  0-8 are the ones the command line already had (see parsearg's epilog);
# 10 and 11 are new, and are the two a scheduled job is written around.
# ##################################################################################
EXIT_OK = 0  # Done, and there was nothing to report.
EXIT_ERROR = 1  # A program error.
EXIT_OUTPUT_FAILED = 2  # A file that was asked for could not be written.
EXIT_NOT_A_BACKUP = 3  # A file is not a valid Tasker backup.
EXIT_NO_FILE = 6  # No file, or a file that is not there.
EXIT_BAD_OPTION = 7  # An option that does not make sense.
EXIT_FOUND = 10  # The report ran and found something: problems, or differences.
EXIT_NO_HISTORY = 11  # Changes Since had nothing earlier to compare against.

# The flags that make a run a command-line report, in the single-dash style the rest of the
# command line uses.  Each is also accepted with two dashes.
REPORT_FLAGS = ("healthcheck", "compare", "changes_since", "export", "watch")

# Health Check: which findings make the run "find something" (EXIT_FOUND).
FAIL_ON_ERROR = "error"
FAIL_ON_WARNING = "warning"
FAIL_ON_NEVER = "never"

# The Map is built without the view limit: that is a limit on what a window is asked to show.
_UNLIMITED = 9_999_999

# "3d": three days back.  The other periods are named (see _cutoff).
_DAYS_BACK = re.compile(r"^(\d+)d$", re.IGNORECASE)


class _ReportError(Exception):
    """A run that cannot go on, and the exit code and message that say why."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class _Parser(argparse.ArgumentParser):
    """An argument parser that reports to the caller instead of ending the process.

    argparse ends the process on a bad option (with status 2) and on -h.  This is called from
    mapit_all, which turns a return value into an exit status, and from tests, which must not
    be ended -- and a bad option here is EXIT_BAD_OPTION, the code the command line already
    uses for one, rather than argparse's own.
    """

    def error(self, message: str) -> NoReturn:
        """Show the usage and the problem on standard error, and stop with EXIT_BAD_OPTION."""
        self.print_usage(sys.stderr)
        sys.stderr.write(f"{self.prog}: error: {message}\n")
        raise MapTaskerError(exit_code=EXIT_BAD_OPTION)

    def exit(self, status: int = 0, message: str | None = None) -> NoReturn:
        """Stop without ending the process."""
        if message:
            sys.stderr.write(message)
        raise MapTaskerError(exit_code=status)


def wants_report(argv: list[str]) -> bool:
    """Whether the command line asks for one of these reports rather than for the GUI.

    Args:
        argv (list[str]): the command line, without the program's own name.

    Returns:
        bool: True if any argument is one of the REPORT_FLAGS (with one or two dashes, and
            with or without an "=value").
    """
    flags = {f"-{name}" for name in REPORT_FLAGS} | {f"--{name}" for name in REPORT_FLAGS}
    return any(argument.split("=", 1)[0] in flags for argument in argv)


def build_parser() -> argparse.ArgumentParser:
    """The command line for the reports.

    Returns:
        argparse.ArgumentParser: the parser.  Built fresh each time, so a test can parse
            more than once.
    """
    parser = _Parser(
        prog="maptasker",
        allow_abbrev=False,
        description="Run a MapTasker report from the command line, with no window.",
        epilog=(
            "The report is written to standard output; everything else goes to standard error.\n"
            "Exit codes: 0 done, nothing to report; 10 the report found something (problems, or\n"
            "differences); 11 Changes Since had no earlier configuration to compare against;\n"
            "1 program error; 2 a file could not be written; 3 not a valid Tasker backup;\n"
            "6 no such file; 7 invalid option."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    chosen = parser.add_mutually_exclusive_group(required=True)
    chosen.add_argument("-healthcheck", action="store_true", help="scan a backup for problems")
    chosen.add_argument(
        "-compare",
        nargs=2,
        metavar=("OLDER", "NEWER"),
        help="show what differs between two backups (which is older is settled by the files' dates)",
    )
    chosen.add_argument(
        "-changes_since",
        metavar="PERIOD",
        help="show what changed since PERIOD: today, week, month, all, a date (YYYY-MM-DD) or Nd (e.g. 3d)",
    )
    chosen.add_argument(
        "-export",
        choices=(mapexport.MAP, mapexport.DIAGRAM),
        help="write the Map or the Diagram as a file (see -format), and print its path",
    )
    chosen.add_argument(
        "-watch",
        metavar="FOLDER",
        help="record each new backup that appears in FOLDER in the history, until stopped",
    )

    parser.add_argument("-file", help="the Tasker backup to use: a file, or a folder to use the newest .xml in")
    parser.add_argument("-outdir", help="the folder to write files into (see -save and -export)")
    parser.add_argument("-history_dir", help="the folder holding the history, if not MapTasker_Timeline here")
    parser.add_argument("-save", action="store_true", help="also save the report as a file, as the window does")
    parser.add_argument(
        "-fail_on",
        choices=(FAIL_ON_ERROR, FAIL_ON_WARNING, FAIL_ON_NEVER),
        default=FAIL_ON_ERROR,
        help="-healthcheck: which findings exit with 10 (default: error)",
    )
    parser.add_argument(
        "-format",
        choices=tuple(mapexport.FORMATS),
        default=mapexport.MARKDOWN,
        help="-export: the format to write (default: md)",
    )
    parser.add_argument("-detail", type=int, choices=range(6), help="-export: the level of detail to build the Map at")
    parser.add_argument(
        "-interval",
        type=float,
        default=folderwatch.DEFAULT_INTERVAL_SECONDS,
        help="-watch: seconds between looks at the folder",
    )
    parser.add_argument("-once", action="store_true", help="-watch: look once and stop (for a scheduled job)")
    return parser


# ##################################################################################
# Getting ready.  A command-line run starts from nothing, so this does what the start of
# the GUI's run does -- and no more.
# ##################################################################################
def _prepare(options: argparse.Namespace) -> None:
    """Set PrimeItems up for a run with nobody watching."""
    # A terminal that cannot show a Tasker name (a Windows console in its legacy code page,
    # a pipe that has no encoding of its own) must not turn a report into a traceback.
    for stream in (sys.stdout, sys.stderr):
        if callable(reconfigure := getattr(stream, "reconfigure", None)):  # A captured stream has none.
            reconfigure(encoding="utf-8", errors="replace")

    PrimeItemsReset()
    PrimeItems.headless = True
    PrimeItems.slash = "\\" if platform.system() == "Windows" else "/"
    PrimeItems.windows_system = platform.system() == "Windows"
    load_arg_specs()

    PrimeItems.program_arguments = initialize_runtime_arguments()
    _apply_saved_settings()
    # Whatever the GUI last left behind about what it was doing is not what this run is for.
    PrimeItems.program_arguments.update(
        {"gui": False, "guiview": False, "doing_diagram": False, "rerun": False, "ai_analyze": False},
    )
    clear_single_items()
    PrimeItems.colors_to_use = set_color_mode(PrimeItems.program_arguments.appearance_mode)
    _put_on_primeitems(output_lines=LineOut(), tasker_root_elements=initial_tasker_root_elements())

    if options.outdir:
        folder, problem = normalize_output_directory(options.outdir)
        if problem:
            raise _ReportError(EXIT_OUTPUT_FAILED, problem)
        PrimeItems.program_arguments.output_directory = folder
    if options.detail is not None:
        PrimeItems.program_arguments.display_detail_level = options.detail
    if options.history_dir:
        timeline.use_history_folder(options.history_dir)


def _put_on_primeitems(**attributes: object) -> None:
    """Set attributes on PrimeItems by name.

    PrimeItems declares a few of these (output_lines, file_to_get) with a type too narrow for
    what they really hold, so assigning the real thing is a type error wherever it is done --
    and the type-check baseline already counts those.  By name it is not one more of them.
    """
    for name, value in attributes.items():
        setattr(PrimeItems, name, value)


def _apply_saved_settings() -> None:
    """Take what the GUI last saved -- the output folder, the colours, the detail level.

    So that a report is saved where the window would have saved it and an export looks as the
    Map does.  Read, never written: a missing or unreadable settings file leaves the defaults.
    """
    with contextlib.suppress(Exception):
        saved_arguments, saved_colors = save_restore_args({}, {}, to_save=False)
        PrimeItems.program_arguments.restore(
            saved_arguments if isinstance(saved_arguments, dict) else saved_arguments.as_dict(),
        )
        PrimeItems.program_arguments.display_detail_level = int(PrimeItems.program_arguments.display_detail_level)
        PrimeItems.colors_to_use.update({key: value for key, value in saved_colors.items() if key is not None})


@contextlib.contextmanager
def _error_file_left_alone() -> Iterator[None]:
    """Leave the error file as it was.

    With the GUI's error handling on (see _load_backup) a failed load writes the reason to a
    file in the current directory, which the GUI reads at start-up and shows as an error from
    a previous session.  A scheduled report that found a bad backup must not be the reason
    someone is greeted with an error when they next open the window.
    """
    path = Path(ERROR_FILE)
    try:
        before = path.read_bytes() if path.exists() else None
    except OSError:
        before = None
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            if before is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(before)


def _resolve_backup(text: str | None) -> Path:
    """The backup file to use: the file named, or the newest .xml in the folder named."""
    if not text:
        message = "No backup was given.  Use -file <backup.xml>, or -file <folder> for the newest backup in it."
        raise _ReportError(EXIT_NO_FILE, message)
    path = Path(text).expanduser()
    if path.is_dir():
        newest = folderwatch.newest_backup(path)
        if newest is None:
            raise _ReportError(EXIT_NO_FILE, f"There is no .xml backup in {path}.")
        return newest
    if not path.is_file():
        raise _ReportError(EXIT_NO_FILE, f"{path} was not found.")
    return path


def _load_backup(text: str | None) -> Path:
    """Load a backup as the configuration this run works on, and return the file it was.

    The load is taskerd's own, so it records the backup in the history exactly as opening it
    in the window does -- a scheduled report is also a way of keeping the history up to date.

    The GUI's error handling is on for the load and off again after: with it, a bad file is
    RECORDED (PrimeItems.error_msg) and the load returns, where without it the error handler
    ends the run with a bare exit code and no reason to give.
    """
    path = _resolve_backup(text)
    arguments = PrimeItems.program_arguments
    arguments.file = str(path)
    with _error_file_left_alone(), console.muted():
        arguments.gui = True
        with path.open(encoding="utf-8") as opened:
            try:
                _put_on_primeitems(file_to_get=opened, tasker_root_elements=initial_tasker_root_elements())
                clear_error()
                return_code = get_the_xml_data()
            finally:
                arguments.gui = False
    if return_code != 0:
        raise _ReportError(EXIT_NOT_A_BACKUP, PrimeItems.error_msg or f"{path} is not a valid Tasker backup file.")
    sys.stderr.write(f"MapTasker: loaded {path}\n")
    return path


# ##################################################################################
# Output
# ##################################################################################
def _report(text: str) -> None:
    """The report, on standard output."""
    sys.stdout.write(text if text.endswith("\n") else f"{text}\n")
    sys.stdout.flush()


def _note(message: str) -> None:
    """Something to say that is not the report, on standard error."""
    sys.stderr.write(f"MapTasker: {message}\n")


def _saved(path: str, what: str) -> None:
    """Say where a saved report went, or fail with EXIT_OUTPUT_FAILED if it went nowhere."""
    if not path:
        raise _ReportError(EXIT_OUTPUT_FAILED, f"The {what} could not be saved.")
    _note(f"{what} saved as {path}")


# ##################################################################################
# The reports
# ##################################################################################
def _health_check(options: argparse.Namespace) -> int:
    """Scan the backup for problems.  EXIT_FOUND if there are any at or above -fail_on."""
    _load_backup(options.file)
    rows, counts = healthck.run_health_check()
    _report(mapjump.text_report(rows))
    _note(
        f"Health Check: {counts[healthck.ERROR]} errors, {counts[healthck.WARNING]} warnings, "
        f"{counts[healthck.INFO]} notes.",
    )
    if options.save:
        _saved(healthck.write_health_check_report(rows), "Health Check")

    if options.fail_on == FAIL_ON_NEVER:
        return EXIT_OK
    failing = counts[healthck.ERROR] + (counts[healthck.WARNING] if options.fail_on == FAIL_ON_WARNING else 0)
    return EXIT_FOUND if failing else EXIT_OK


def _compare(options: argparse.Namespace) -> int:
    """Show what differs between two backups.  EXIT_FOUND if anything does."""
    first, second = options.compare
    for path in (first, second):
        if not Path(path).expanduser().is_file():
            raise _ReportError(EXIT_NO_FILE, f"{path} was not found.")
    if os.path.realpath(first) == os.path.realpath(second):
        raise _ReportError(EXIT_BAD_OPTION, "Both files are the same file.  Give two different backups to compare.")

    sides = []
    for path in (first, second):
        configuration, message = diffload.load_for_comparison(str(Path(path).expanduser()))
        if configuration is None:
            raise _ReportError(EXIT_NOT_A_BACKUP, message)
        sides.append(configuration)

    # Ordered by file date so "added" means added in the newer file, whichever way round they
    # were given -- the same as the window.  The header names both files either way.
    older, newer = diffload.order_by_age(*sides)
    report, counts = xmldiff.compare(older, newer)
    _report(report)
    if options.save:
        _saved(diffload.write_comparison_report(report), "Comparison")
    return EXIT_FOUND if any(counts.values()) else EXIT_OK


def _cutoff(period: str) -> datetime | None:
    """The moment a -changes_since period starts.  None means the whole history.

    Raises:
        _ReportError: with EXIT_BAD_OPTION if the period is not one of the ones understood.
    """
    text = period.strip().lower()
    if text in {timeline.TODAY, timeline.THIS_WEEK, timeline.THIS_MONTH, timeline.ALL}:
        return timeline.cutoff_for(text)
    if days := _DAYS_BACK.match(text):
        return clock.now() - timedelta(days=int(days[1]))
    try:
        return timeline.cutoff_for(timeline.ON_DATE, on_date=date.fromisoformat(text))
    except ValueError:
        message = (
            f"'{period}' is not a period.  Use today, week, month, all, a date (YYYY-MM-DD) or a number of days (3d)."
        )
        raise _ReportError(EXIT_BAD_OPTION, message) from None


def _changes_since(options: argparse.Namespace) -> int:
    """Show what changed in the configuration since a period.  EXIT_FOUND if anything did."""
    cutoff = _cutoff(options.changes_since)
    # Asked before the load, which is itself recorded in the history: with nothing there
    # already this backup would be the whole of it, and the answer is "nothing before it".
    had_history = bool(timeline.snapshots())
    _load_backup(options.file)
    if not had_history:
        _note("There was no history yet, so this backup is now its first entry.  Run this again after the next backup.")
        return EXIT_NO_HISTORY

    result = timeline.changes_since(cutoff)
    if result.problem:
        _note(result.problem)
        return EXIT_NO_HISTORY
    if result.note:
        _note(result.note)
    _report(result.report)
    if options.save:
        _saved(diffload.write_comparison_report(result.report, TIMELINE_FILE), "Timeline")
    return EXIT_OK if result.nothing_changed else EXIT_FOUND


def _build_the_view(view: str) -> None:
    """Build the Map or the Diagram, as the window does, so that there is something to export."""
    arguments = PrimeItems.program_arguments
    PrimeItems.view_limit = _UNLIMITED
    arguments.view_limit = _UNLIMITED
    reset_attributes(*MAP_OUTPUT_ATTRIBUTES)
    PrimeItems.found_named_items = initial_found_named_items()
    clear_error()
    _put_on_primeitems(output_lines=LineOut())

    with console.muted():
        if view == mapexport.MAP:
            output_the_front_matter(current_config(), state=PrimeItems)
            build_html("", state=PrimeItems)
        else:
            outline_the_configuration(state=PrimeItems)
    if PrimeItems.error_code > 0:
        raise _ReportError(EXIT_ERROR, PrimeItems.error_msg or f"The {view} could not be built.")


def _export(options: argparse.Namespace) -> int:
    """Build the Map or the Diagram and write it as a file, then print where it went."""
    _load_backup(options.file)
    _build_the_view(options.export)
    try:
        path = mapexport.export_view(options.export, options.format)
    except mapexport.ExportError as error:
        raise _ReportError(EXIT_ERROR, str(error)) from error
    except OSError as error:
        raise _ReportError(EXIT_OUTPUT_FAILED, f"The export could not be saved: {error}") from error
    _report(path)
    return EXIT_OK


@contextlib.contextmanager
def _stop_on_terminate() -> Iterator[None]:
    """Make SIGTERM stop a watch the way Ctrl-C does.

    SIGTERM is how a service manager (launchd, systemd, a container) asks a program to stop,
    and left alone it ends the process on the spot.  A watch has nothing half-done to lose --
    a snapshot is written whole or not at all -- but ending on a request rather than a kill
    lets it say so, and lets it exit with 0.  Only the main thread can set a handler, so
    anywhere else this does nothing.
    """

    def stop(_signal_number: int, _frame: object) -> None:
        raise KeyboardInterrupt

    try:
        previous = signal.signal(signal.SIGTERM, stop)
    except ValueError:  # Not the main thread.
        yield
        return
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


def _watch(options: argparse.Namespace) -> int:
    """Record each backup that appears in a folder in the history."""
    folder = Path(options.watch).expanduser()
    if not folder.is_dir():
        raise _ReportError(EXIT_NO_FILE, f"{folder} is not a folder.")

    def announce(event: folderwatch.Event) -> None:
        if event.outcome == folderwatch.RECORDED:
            _report(f"recorded {event.path.name}")
        elif event.outcome == folderwatch.INCOMPLETE:
            _note(f"{event.path.name} is not a complete Tasker backup; it was left out of the history.")
        else:
            _note(f"{event.path.name} is the same configuration as the latest in the history; nothing added.")

    if not options.once:
        _note(f"Watching {folder} every {options.interval:g} seconds.  Press Ctrl-C to stop.")
    try:
        with _stop_on_terminate():
            folderwatch.watch(folder, interval=options.interval, once=options.once, on_event=announce)
    except KeyboardInterrupt:
        _note("Stopped.")
    return EXIT_OK


_COMMANDS = (
    ("healthcheck", _health_check),
    ("compare", _compare),
    ("changes_since", _changes_since),
    ("export", _export),
    ("watch", _watch),
)


def run(argv: list[str]) -> int:
    """Run the report the command line asks for, and return the exit code.

    Args:
        argv (list[str]): the command line, without the program's own name.

    Returns:
        int: the exit code.  Nothing here ends the process: mapit_all returns this as the
            status, and a test can call it as often as it likes.
    """
    try:
        options = build_parser().parse_args(argv)
    except MapTaskerError as stopped:  # -h, or an option that makes no sense: already answered.
        return stopped.exit_code

    try:
        _prepare(options)
        for name, command in _COMMANDS:
            # Given, not merely truthy: "-changes_since ''" is a period that is wrong, which
            # _cutoff says so about, and not a report that was never asked for.
            if getattr(options, name) not in (None, False):
                return command(options)
    except _ReportError as failure:
        console.error(f"MapTasker: {failure.message}")
        return failure.code
    except MapTaskerError as error:
        # exit_program's own message is usually empty (the reason went to the log or the
        # window, and there is no window): say what can be said, and where the rest is.
        console.error(f"MapTasker: {error.message or 'The run could not be completed.  See the MapTasker log.'}")
        return error.exit_code or EXIT_ERROR
    except OSError as error:
        logger.exception("Command-line report failed")
        console.error(f"MapTasker: {error}")
        return EXIT_ERROR
    finally:
        timeline.use_history_folder(None)
        PrimeItems.headless = False
    return EXIT_ERROR
