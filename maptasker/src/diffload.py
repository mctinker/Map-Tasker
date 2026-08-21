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
from datetime import datetime
from typing import NamedTuple

from maptasker.src import sessundo
from maptasker.src.maputil2 import TIMESTAMP_SUFFIX_RE
from maptasker.src.maputils import append_to_filename
from maptasker.src.primitem import PrimeItems, initial_tasker_root_elements
from maptasker.src.sysconst import COMPARE_FILE, ERROR_FILE, logger
from maptasker.src.taskerd import get_the_xml_data
from maptasker.src.xmldiff import Configuration

# What get_the_xml_data returns, and what to tell the user about each.  Its own docstring
# documents these; a bare number in the GUI would tell nobody anything.
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
    root: object | None
    scratch: str

# program_arguments keys this forces for the duration of an isolated load.  See
# _parsed_in_isolation for why each one has to be forced rather than merely saved.
_FORCED_ARGUMENTS = {"gui": True, "directory": False}


def current_configuration() -> Configuration:
    """The configuration MapTasker has loaded, as one side of a comparison.

    Hands over PrimeItems.tasker_root_elements itself rather than a copy.  xmldiff only
    ever reads it, and copying a table holding every element of a large backup to satisfy
    a rule nothing is breaking would be a waste.
    """
    path = loaded_file_path()
    return Configuration(
        path=path or "(currently loaded)",
        tables=PrimeItems.tasker_root_elements,
        root=PrimeItems.xml_root,
        when=_modified_time(path),
    )


def loaded_file_path() -> str:
    """The path of the XML file currently loaded, or "" if there is none.

    PrimeItems.file_to_get is sometimes an open file object and sometimes the path as a
    plain string -- the same ambiguity healthck._current_xml_file and
    maputil2.write_full_backup_to_current_file handle, resolved the same way.
    """
    file_to_get = PrimeItems.file_to_get
    path = getattr(file_to_get, "name", file_to_get) if file_to_get else ""
    return path if isinstance(path, str) else ""


def load_for_comparison(file_path: str) -> tuple[Configuration | None, str]:
    """Parse another XML file into a Configuration, leaving the loaded one alone.

    Returns (Configuration, "") on success, or (None, message) on failure -- a message
    fit to put straight in front of the user.  Never raises for a bad file and never
    exits: a comparison against a file that would not load must leave the user with the
    configuration they already had open.
    """
    if not file_path:
        return None, "No file was chosen to compare against."

    with _parsed_in_isolation(file_path) as parsed:
        if parsed.return_code != 0:
            return None, _failure_message(parsed, file_path)

        return Configuration(
            path=file_path,
            tables=parsed.tables,
            root=parsed.root,
            when=_modified_time(file_path),
        ), ""


def _failure_message(parsed: _Parsed, file_path: str) -> str:
    """Why the file did not load, in terms the user can act on.

    Read inside the isolation window, while PrimeItems.error_msg still belongs to this
    load -- the restore puts the loaded file's own error message back.
    """
    name = os.path.basename(file_path)
    # taskerd embeds the path it was handed, which was the temporary copy.  Put the name
    # the user chose back in its place, keeping any line/column detail after it.
    detail = PrimeItems.error_msg or ""
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
    to the copy (edit_caveats.txt item 6, maputil2.write_full_backup_to_current_file).
    Both halves of that pair are therefore on disk, which makes "what did my own edit
    change?" answerable with no file picker at all.

    Returns "" when the loaded file is not one of those copies, or when the file it was
    made from has since been moved or deleted -- in either case there is nothing to offer
    and the caller falls back to asking.
    """
    if not file_path:
        return ""
    base_path, extension = os.path.splitext(file_path)  # noqa: PTH122
    stripped = TIMESTAMP_SUFFIX_RE.sub("", base_path)
    if stripped == base_path:
        return ""
    original = f"{stripped}{extension}"
    return original if os.path.isfile(original) else ""  # noqa: PTH113


def write_comparison_report(report: str) -> str:
    """Write the report to a timestamped file in the current runtime directory.

    Returns the file name written, or "" if the write failed -- a comparison whose
    findings displayed fine is still worth showing when only the save went wrong.

    Named and stamped exactly as healthck.write_health_check_report does
    (MapTasker_Compare_08-18-2026_14-52-07.txt), zero padded so successive reports from
    one day sort by when they were run, and datetime.now() rather than maputils'
    get_current_local_time_auto_timezone -- that one geolocates by IP with a five second
    timeout, which is a strange thing to make a local button click wait for.
    """
    stamp = datetime.now().strftime("_%m-%d-%Y_%H-%M-%S")  # noqa: DTZ005
    file_name = append_to_filename(COMPARE_FILE, stamp)
    if not file_name:
        return ""
    try:
        report_path = os.path.join(os.getcwd(), file_name)  # noqa: PTH109, PTH118
        with open(report_path, "w", encoding="utf-8") as output_file:  # noqa: PTH123
            output_file.write(report)
    except OSError as error:
        logger.error(f"Comparison report could not be written: {error}")
        return ""
    return file_name


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
        return datetime.fromtimestamp(os.path.getmtime(file_path))  # noqa: DTZ006
    except OSError:
        return None


@contextlib.contextmanager
def _parsed_in_isolation(file_path: str) -> _Parsed:
    """Run get_the_xml_data against another file with PrimeItems as its scratch storage.

    Yields a _Parsed.  Everything saved here is restored on the way out, including when
    the parse fails and including when it raises.

    THE FILE IS COPIED FIRST, AND THE COPY IS WHAT GETS PARSED.  Not paranoia:
    get_the_xml_data calls xmldata.rewrite_xml on a UnicodeDecodeError, and rewrite_xml
    does os.remove(file_to_parse) followed by os.rename -- it replaces the file on disk.
    A comparison that rewrote one of the two backups it was asked to compare would be
    destroying the very thing the user opened it to check, and "Save to Current File"
    never touches the original (edit_caveats.txt item 6) precisely so that pair stays
    comparable.  Parsing a copy makes that impossible by construction rather than by
    hoping the encoding is fine.

    "gui" is forced True for the duration, and this is load-bearing rather than tidy: on
    a parse error taskerd calls error_handler, which outside GUI mode ends in
    exit_program -> sys.exit.  A corrupt file picked for comparison would take the whole
    program down, unsaved edits and all.  In GUI mode it records the error and returns,
    which is the only acceptable outcome here.

    "directory" is forced False because conditions_to_name calls add_directory_item when
    it is on, which would append the other file's Profiles to the live directory list.
    PrimeItems.directory_items is deep-copied and restored anyway, as a backstop.

    Not re-entrant and not thread safe.  It does not need to be: one button, one click.
    """
    saved = {
        "file_to_get": PrimeItems.file_to_get,
        "file_to_use": PrimeItems.file_to_use,
        "xml_tree": PrimeItems.xml_tree,
        "xml_root": PrimeItems.xml_root,
        "tasker_root_elements": PrimeItems.tasker_root_elements,
        "error_code": PrimeItems.error_code,
        "error_msg": PrimeItems.error_msg,
    }
    # Restored by content into the SAME dict and the same lists inside it, rather than by
    # replacing it with the copy: anything already holding a reference to
    # PrimeItems.directory_items (or to one of its lists) would otherwise be left writing
    # into an object nothing reads any more.
    saved_directory = PrimeItems.directory_items
    saved_directory_contents = copy.deepcopy(PrimeItems.directory_items)
    saved_arguments = {key: PrimeItems.program_arguments.get(key) for key in _FORCED_ARGUMENTS}
    # get_the_xml_data clears the session's undo history, because a load normally means a
    # different configuration is open now.  This load does not -- see sessundo.save_history.
    saved_undo_history = sessundo.save_history()
    # _handle_gui_error appends the failure to the running output, which belongs to the
    # map being built for the file the user actually has open.
    saved_output = list(PrimeItems.output_lines.output_lines) if PrimeItems.output_lines is not None else None
    saved_error_file = _read_error_file()

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
            opened = open(scratch)  # noqa: SIM115, PTH123  (closed in the finally below)
            PrimeItems.file_to_get = opened
            PrimeItems.tasker_root_elements = initial_tasker_root_elements()
            PrimeItems.error_code = 0
            PrimeItems.error_msg = ""
            PrimeItems.program_arguments.update(_FORCED_ARGUMENTS)

            parsed = _Parsed(get_the_xml_data(), PrimeItems.tasker_root_elements, PrimeItems.xml_root, scratch)
        except Exception as error:  # noqa: BLE001
            # Deliberately every exception, not just OSError.  The contract this module
            # owes its caller is that picking a bad file to compare against produces a
            # message and leaves the loaded configuration alone -- so anything the parse
            # can throw has to become that message.
            #
            # Not hypothetical: taskerd's own error path calls
            # PrimeItems.output_lines.add_line_to_output, and output_lines is None until
            # a map has been built (guiutils/mapit construct the LineOut).  A malformed
            # file picked before the user has rendered anything therefore comes back as
            # an AttributeError from inside the error handler rather than as a return
            # code.  A missing file, an unreadable one and a failed copy arrive here too.
            logger.error(f"Comparison file could not be read: {error}")
            PrimeItems.error_msg = str(error)
            parsed = _Parsed(_LOAD_FAILED, initial_tasker_root_elements(), None, scratch or "")

        yield parsed
    finally:
        if opened is not None:
            opened.close()
        if scratch is not None:
            # missing_ok: the parse may have replaced it (see rewrite_xml above), which
            # is exactly what the copy is here to absorb.
            with contextlib.suppress(OSError):
                os.unlink(scratch)  # noqa: PTH108

        for name, value in saved.items():
            setattr(PrimeItems, name, value)
        sessundo.restore_history(saved_undo_history)
        PrimeItems.directory_items = saved_directory
        for key, value in saved_directory_contents.items():
            if isinstance(saved_directory.get(key), list):
                saved_directory[key][:] = value
            else:
                saved_directory[key] = value
        for key, value in saved_arguments.items():
            if value is None:
                PrimeItems.program_arguments.pop(key, None)
            else:
                PrimeItems.program_arguments[key] = value
        if saved_output is not None:
            PrimeItems.output_lines.output_lines = saved_output
        _restore_error_file(saved_error_file)


def _scratch_copy(file_path: str) -> str:
    """A throwaway copy of the file to parse, in the system temp directory.

    Named after the original so anything that surfaces the path -- a log line, an
    error_handler message -- still says which file went wrong.
    """
    handle, scratch = tempfile.mkstemp(prefix="MapTasker_compare_", suffix=f"_{os.path.basename(file_path)}")
    os.close(handle)
    shutil.copyfile(file_path, scratch)
    return scratch


def _read_error_file() -> bytes | None:
    """The current contents of the error file, or None if there is not one.

    With "gui" forced True, a failed parse makes error_handler write ERROR_FILE, which
    userintr reads on entry to show an error from a previous session.  Left there, a
    comparison file that would not load would greet the user at next startup as though
    their own configuration had failed.
    """
    try:
        with open(ERROR_FILE, "rb") as error_file:  # noqa: PTH123
            return error_file.read()
    except OSError:
        return None


def _restore_error_file(contents: bytes | None) -> None:
    """Put the error file back as it was -- rewritten, or removed if there was none."""
    try:
        if contents is None:
            if os.path.exists(ERROR_FILE):  # noqa: PTH110
                os.unlink(ERROR_FILE)  # noqa: PTH108
        else:
            with open(ERROR_FILE, "wb") as error_file:  # noqa: PTH123
                error_file.write(contents)
    except OSError as error:
        logger.error(f"Error file could not be restored after a comparison: {error}")
