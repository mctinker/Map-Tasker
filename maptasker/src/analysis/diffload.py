"""Load a second Tasker XML file for comparison, leaving the loaded one untouched."""

#! /usr/bin/env python3

#                                                                                      #
# diffload: parse another XML file into an xmldiff.Configuration without disturbing    #
#           the configuration MapTasker currently has loaded.                          #
#                                                                                      #
# This is the half of the comparison feature that has to touch PrimeItems, kept in its  #
# own module so that xmldiff.py can go on having no global state at all -- which is     #
# what makes the comparison itself testable from XML text and reusable from a CLI.      #
#                                                                                      #
# WHY THIS IS NOT JUST "CALL get_the_xml_data TWICE"                                    #
# taskerd.get_the_xml_data does not return its results; it writes them into             #
# PrimeItems.xml_tree/xml_root/tasker_root_elements.  Calling it a second time destroys  #
# the configuration the user has open.                                                  #
#                                                                                      #
# The obvious fix -- extract a pure build_tables(root) -> dict -- is NOT the mechanical  #
# refactor it looks like.  The unnamed-Profile naming pass writes back through the       #
# global on its own: profiles.conditions_to_name does                                    #
# PrimeItems.tasker_root_elements["all_profiles"][profile_id]["name"] = ... directly     #
# (profiles.py).  A build_tables that filled a local dict would have that pass writing   #
# the second file's derived names into the FIRST file's table.  Silently.                #
#                                                                                      #
# So instead of changing the load, this makes PrimeItems *be* the second file's storage  #
# for the duration and puts it all back afterwards.  That works precisely BECAUSE of the #
# write-back above: during the window, the global table is the scratch table.            #
#                                                                                      #
from __future__ import annotations

import contextlib
import copy
import os
import shutil
import tempfile
from typing import TYPE_CHECKING, Any, NamedTuple

from maptasker.src.analysis.xmldiff import Configuration
from maptasker.src.core import clock, timeline
from maptasker.src.core.maputil2 import TIMESTAMP_SUFFIX_RE
from maptasker.src.core.maputils import append_to_filename
from maptasker.src.core.mtexcept import MapTaskerError
from maptasker.src.core.outdir import output_path
from maptasker.src.core.primitem import (
    LOADED_CONFIGURATION_ATTRIBUTES,
    clear_error,
    initial_tasker_root_elements,
)
from maptasker.src.core.sysconst import COMPARE_FILE, logger
from maptasker.src.edit import sessundo
from maptasker.src.mapgen.taskerd import get_the_xml_data

if TYPE_CHECKING:
    from collections.abc import Iterator
    from datetime import datetime
    from xml.etree.ElementTree import Element

    from maptasker.src.core.primitem import RunState

# The code a MapTaskerError from get_the_xml_data carries, and what to tell the user about each.  Its own
# docstring documents these; a bare number in the GUI would tell nobody anything.
_RETURN_CODE_MESSAGES = {
    1: "could not be parsed -- it is not valid XML.",
    2: "is not a Tasker backup file.",
    3: "is not a valid Tasker backup file.",
}

# The load did not get as far as a verdict -- the file was missing, unreadable, or the
# parse threw.  Kept distinct from get_the_xml_data's own codes because those are
# judgements about the file's CONTENT: reporting a file that is not there as "not valid
# XML" sends the user off to inspect a file they have not got.
_LOAD_FAILED = -1


class _Parsed(NamedTuple):
    """What an isolated load produced.

    'scratch' is the temporary copy that was actually parsed.  Carried out of the window
    so a message can put the real file name back in place of it -- taskerd's own error
    text embeds the path it was handed, and a user shown a path under /var/folders has
    been told nothing and shown what looks like a bug.
    """

    return_code: int
    tables: dict
    root: Element | None
    scratch: str


# program_arguments keys this forces for the duration of an isolated load.  See
# _parsed_in_isolation for why each one has to be forced rather than merely saved.
_FORCED_ARGUMENTS = {"directory": False}


def current_configuration(state: RunState) -> Configuration:
    """The configuration MapTasker has loaded, as one side of a comparison.

    Hands over PrimeItems.tasker_root_elements itself rather than a copy.  xmldiff only
    ever reads it, and copying a table holding every element of a large backup to satisfy
    a rule nothing is breaking would be a waste.
    """
    path = loaded_file_path(state=state)
    return Configuration(
        path=path or "(currently loaded)",
        tables=state.tasker_root_elements,
        root=state.xml_root,
        when=_modified_time(path),
    )


# How many times another file has been parsed in isolation, since the program started.
_windows = [0]


def isolation_windows() -> int:
    """How many times another file has been read in so far -- each borrows the program's tables (see _parsed_in_isolation)."""
    return _windows[0]


def loaded_file_path(state: RunState) -> str:
    """The path of the XML file currently loaded, or "" if there is none.

    PrimeItems.file_to_get is sometimes an open file object and sometimes the path as a
    plain string -- the same ambiguity healthck._current_xml_file and
    maputil2.write_full_backup_to_current_file handle, resolved the same way.
    """
    file_to_get = state.file_to_get
    path = getattr(file_to_get, "name", file_to_get) if file_to_get else ""
    return path if isinstance(path, str) else ""


def load_for_comparison(file_path: str, state: RunState) -> tuple[Configuration | None, str]:
    """Parse another XML file into a Configuration, leaving the loaded one alone.

    Returns (Configuration, "") on success, or (None, message) on failure -- a message
    fit to put straight in front of the user.  Never raises for a bad file and never
    exits: a comparison against a file that would not load must leave the user with the
    configuration they already had open.
    """
    if not file_path:
        return None, "No file was chosen to compare against."

    # Counted, so that a build on another thread can tell it read the scratch tables meanwhile.
    _windows[0] += 1
    with _parsed_in_isolation(file_path, state=state) as parsed:
        if parsed.return_code != 0:
            return None, _failure_message(parsed, file_path, state=state)

        return (
            Configuration(
                path=file_path,
                tables=parsed.tables,
                root=parsed.root,
                when=_modified_time(file_path),
            ),
            "",
        )


def _failure_message(parsed: _Parsed, file_path: str, state: RunState) -> str:
    """Why the file did not load, in terms the user can act on.

    Read inside the isolation window, while PrimeItems.error_msg still belongs to this
    load -- the restore puts the loaded file's own error message back.
    """
    name = os.path.basename(file_path)
    # taskerd embeds the path it was handed, which was the temporary copy.  Put the name
    # the user chose back in its place, keeping any line/column detail after it.
    detail = state.error_msg or ""
    if parsed.scratch:
        detail = detail.replace(parsed.scratch, file_path)

    if parsed.return_code == _LOAD_FAILED:
        return f"{name} could not be read.  ({detail})" if detail else f"{name} could not be read."

    reason = _RETURN_CODE_MESSAGES.get(parsed.return_code, "could not be read.")
    return f"{name} {reason}" + (f"  ({detail})" if detail else "")


def original_of(file_path: str) -> str:
    """The file a "Save To Current File" copy was made from, if it is still there.

    "Save To Current File" never touches the original: it writes a timestamped copy
    alongside it -- backup.xml -> backup_20260721_143005.xml -- and switches the app over
    to the copy (caveats.md item 6, maputil2.write_full_backup_to_current_file).
    Both halves of that pair are therefore on disk, which makes "what did my own edit
    change?" answerable with no file picker at all.

    Returns "" when the loaded file is not one of those copies, or when the file it was
    made from has since been moved or deleted -- in either case there is nothing to offer
    and the caller falls back to asking.
    """
    if not file_path:
        return ""
    base_path, extension = os.path.splitext(file_path)
    stripped = TIMESTAMP_SUFFIX_RE.sub("", base_path)
    if stripped == base_path:
        return ""
    original = f"{stripped}{extension}"
    return original if os.path.isfile(original) else ""


def write_comparison_report(report: str, base_name: str = COMPARE_FILE, *, state: RunState) -> str:
    """Write the report to a timestamped file in the output folder (see outdir).

    Returns the path written, or "" if the write failed -- a comparison whose
    findings displayed fine is still worth showing when only the save went wrong.

    Named and stamped exactly as healthck.write_health_check_report does
    (MapTasker_Compare_08-18-2026_14-52-07.txt), zero padded so successive reports from
    one day sort by when they were run, and clock.now() rather than maputils'
    get_current_local_time_auto_timezone -- that one geolocates by IP with a five second
    timeout, which is a strange thing to make a local button click wait for.

    base_name is what to stamp.  It defaults to the two-file comparison's own name; the
    timeline passes TIMELINE_FILE so that "what changed since Tuesday" does not land in
    the same pile as "how do these two files differ", which is a different question with
    a different answer.
    """
    stamp = clock.now().strftime("_%m-%d-%Y_%H-%M-%S")
    file_name = append_to_filename(base_name, stamp)
    if not file_name:
        return ""
    report_path = output_path(file_name, state=state)
    try:
        with open(report_path, "w", encoding="utf-8") as output_file:
            output_file.write(report)
    except OSError as error:
        logger.error(f"Comparison report could not be written: {error}")
        return ""
    return report_path


def order_by_age(first: Configuration, second: Configuration) -> tuple[Configuration, Configuration]:
    """The two sides as (older, newer), by file modification time.

    Falls back to the order given when either side has no usable timestamp -- a file
    fetched from an Android device, or one whose path is gone.  A wrong guess is visible
    rather than misleading: the report header always names which file is which, and
    xmldiff.compare is symmetric.
    """
    if first.when and second.when and second.when < first.when:
        return second, first
    return first, second


def _modified_time(file_path: str) -> datetime | None:
    """A file's modification time, or None if it cannot be read.

    What the caller orders the two sides by, so the report can say which is the older.
    None rather than a guess when the file is gone: an invented timestamp would put the
    two files in an order nobody can check.
    """
    try:
        # Aware local time, like the timeline snapshot times these are ordered against.
        return clock.from_timestamp(os.path.getmtime(file_path))
    except OSError:
        return None


@contextlib.contextmanager
def _parsed_in_isolation(file_path: str, state: RunState) -> Iterator[_Parsed]:
    """Run get_the_xml_data against another file with PrimeItems as its scratch storage.

    Yields a _Parsed.  Everything saved here is restored on the way out, including when
    the parse fails and including when it raises.

    THE FILE IS COPIED FIRST, AND THE COPY IS WHAT GETS PARSED.  Not paranoia:
    get_the_xml_data calls xmldata.rewrite_xml on a UnicodeDecodeError, and rewrite_xml
    does os.remove(file_to_parse) followed by os.rename -- it replaces the file on disk.
    A comparison that rewrote one of the two backups it was asked to compare would be
    destroying the very thing the user opened it to check, and "Save to Current File"
    never touches the original (caveats.md item 6) precisely so that pair stays
    comparable.  Parsing a copy makes that impossible by construction rather than by
    hoping the encoding is fine.

    A file that will not parse makes get_the_xml_data raise MapTaskerError, and the except
    below turns it into the verdict this function hands back -- the code the error carries,
    and its message for the user -- without recording anything on the run: a corrupt file
    picked for comparison must not leave an error behind for the next startup to show as
    though the user's own configuration had failed.

    "directory" is forced False because conditions_to_name calls add_directory_item when
    it is on, which would append the other file's Profiles to the live directory list.
    PrimeItems.directory_items is deep-copied and restored anyway, as a backstop.

    Not re-entrant and not thread safe.  It does not need to be: one button, one click.
    """
    # Everything loading a backup sets, and the file and the error that go with it -- see
    # primitem.LOADED_CONFIGURATION_ATTRIBUTES, which a test keeps in step with taskerd.
    saved = {name: getattr(state, name) for name in LOADED_CONFIGURATION_ATTRIBUTES}
    # Restored by content into the SAME dict and the same lists inside it, rather than by
    # replacing it with the copy: anything already holding a reference to
    # PrimeItems.directory_items (or to one of its lists) would otherwise be left writing
    # into an object nothing reads any more.
    saved_directory = state.directory_items
    saved_directory_contents = copy.deepcopy(state.directory_items)
    saved_arguments = {key: state.program_arguments[key] for key in _FORCED_ARGUMENTS}
    # get_the_xml_data clears the session's undo history, because a load normally means a
    # different configuration is open now.  This load does not -- see sessundo.save_history.
    saved_undo_history = sessundo.save_history(state)
    # The load can add to the running output, which belongs to the map being built for the file
    # the user actually has open.
    saved_output = list(state.output_lines.output_lines) if state.output_lines is not None else None

    scratch = None
    opened = None
    try:
        # The inner try wraps the setup and the parse ONLY -- never the yield.  A
        # generator-based context manager gets the caller's own exceptions thrown back in
        # at the yield, so an except around the yield would try to yield a second time
        # and raise "generator didn't stop after throw()" on top of whatever actually
        # went wrong.
        try:
            scratch = _scratch_copy(file_path)
            opened = open(scratch, encoding="utf-8")  # Closed in the finally below.
            state.file_to_get = opened
            state.tasker_root_elements = initial_tasker_root_elements()
            clear_error(state)
            state.program_arguments.update(_FORCED_ARGUMENTS)

            # The file being compared against is not a configuration the user opened, so
            # it does not belong in the timeline history -- without this, every comparison
            # anyone ran would file the other file into the history of the one they are
            # working on.  Only this call can record: it is the load.
            with timeline.suppressed():
                get_the_xml_data(state=state)
            parsed = _Parsed(0, state.tasker_root_elements, state.xml_root, scratch)
        except MapTaskerError as error:
            # A verdict on the file's content: its code says which, and its message says where.
            state.error_msg = error.message
            parsed = _Parsed(error.exit_code, initial_tasker_root_elements(), None, scratch or "")
        except Exception as error:
            # Deliberately every exception, not just OSError.  The contract this module
            # owes its caller is that picking a bad file to compare against produces a
            # message and leaves the loaded configuration alone -- so anything the parse
            # can throw has to become that message.
            #
            # A missing file, an unreadable one and a failed copy arrive here.
            logger.exception("Comparison file could not be read")
            state.error_msg = str(error)
            parsed = _Parsed(_LOAD_FAILED, initial_tasker_root_elements(), None, scratch or "")

        yield parsed
    finally:
        if opened is not None:
            opened.close()
        if scratch is not None:
            # missing_ok: the parse may have replaced it (see rewrite_xml above), which
            # is exactly what the copy is here to absorb.
            with contextlib.suppress(OSError):
                os.unlink(scratch)

        for name, value in saved.items():
            setattr(state, name, value)
        sessundo.restore_history(saved_undo_history, state)
        state.directory_items = saved_directory
        _restore_directory(saved_directory, saved_directory_contents)
        state.program_arguments.update(saved_arguments)
        if saved_output is not None:
            state.output_lines.output_lines = saved_output


def _restore_directory(directory: dict[str, Any], contents: dict[str, Any]) -> None:
    """Put what the directory held back into it, in place -- the same dict, and the same lists in it."""
    for key, value in contents.items():
        if isinstance(directory.get(key), list):
            directory[key][:] = value
        else:
            directory[key] = value


def _scratch_copy(file_path: str) -> str:
    """A throwaway copy of the file to parse, in the system temp directory.

    Named after the original so anything that surfaces the path -- a log line, an
    error message -- still says which file went wrong.
    """
    handle, scratch = tempfile.mkstemp(prefix="MapTasker_compare_", suffix=f"_{os.path.basename(file_path)}")
    os.close(handle)
    shutil.copyfile(file_path, scratch)
    return scratch
