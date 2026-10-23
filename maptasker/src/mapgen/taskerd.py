"""Read in XML"""

#! /usr/bin/env python3

#                                                                                      #
# taskerd: get Tasker data from backup xml                                             #
#                                                                                      #
import defusedxml.ElementTree as ET

from maptasker.src.core import timeline
from maptasker.src.core.mtexcept import MapTaskerError
from maptasker.src.core.primitem import RunState
from maptasker.src.core.xmldata import parse_tasker_xml, rewrite_xml
from maptasker.src.edit import sessundo
from maptasker.src.mapgen.taskertables import build_tasker_tables, get_first_action, move_xml_to_table

# build_tasker_tables, get_first_action and move_xml_to_table lived here until they were split
# out (see taskertables); a good many callers and tests still reach them as taskerd.<name>.
__all__ = ["build_tasker_tables", "get_first_action", "get_the_xml_data", "move_xml_to_table"]


# Load all of the Projects, Profiles and Tasks into a format we can easily
# navigate through.
# Optimized
def get_the_xml_data(state: RunState) -> None:
    # Put this code into a while loop in the event we have to re-call it again.
    """Read the Tasker backup file into the run state's tables.

    Parameters:
        - state: the run state, whose file_to_get names the backup and which receives the tables.
    Raises:
        - MapTaskerError: code 1 when there is no file to read or it is not well-formed XML, code 3
          when it is XML but not a Tasker backup.  The caller decides what a failed load means --
          a message in the window, or the end of a command-line run.
    Processing Logic:
        - If encoding error, rewrites XML with proper encoding and tries again.
        - Gets XML root.
        - Checks for valid Tasker backup file.
        - Moves all data into dictionaries.
    """
    # The open file, whose .name is its path -- or, where something stored the path itself, that.
    file_to_parse = getattr(state.file_to_get, "name", state.file_to_get)
    if not isinstance(file_to_parse, str) or not file_to_parse:
        message = "There is no Tasker backup file to read."
        raise MapTaskerError(message, 1)
    counter = 0

    # # Count the lines to see if we should issue a status.
    # with open(file_to_parse, "rb") as f:
    #     count = sum(1 for _ in f)
    # if count > 15000:
    #     print("Parsing XML file...")

    _rewrite_xml = rewrite_xml
    # Validate the XML file by parsing it twice if necessary.
    while True:
        try:
            state.xml_tree = parse_tasker_xml(file_to_parse)
            break
        # If error, rewrite thqat file with correct encoding.  Try this twice and then call it quits if still fails.
        except (ET.ParseError, UnicodeDecodeError) as e:
            counter += 1
            if counter > 2 or isinstance(e, ET.ParseError):
                message = f"Error in {file_to_parse}: {e}"
                raise MapTaskerError(message, 1) from e
            _rewrite_xml(file_to_parse)

    if state.xml_tree is None:
        message = "Bad XML file"
        raise MapTaskerError(message, 1)

    state.xml_root = state.xml_tree.getroot()
    if state.xml_root.tag != "TaskerData":
        message = "Invalid Tasker backup XML file"
        raise MapTaskerError(message, 3)

    # A different configuration is now the loaded one, so the session's undo history no
    # longer describes it -- see sessundo.clear() for what undoing into another file's
    # checkpoint would do.  Here rather than at the buttons that load a file (Get XML, the
    # Android fetch, the switch to the copy a "Save To Current File" just wrote) because
    # this is the one place all of them go through, and the one this must not be missed at.
    #
    # diffload puts the history back afterwards: it comes through here too, to parse the
    # file being compared against, and that load does not replace what the user has open.
    sessundo.clear(state)

    # And this configuration goes into the history, for the same reason and in the same
    # place: every way of loading a file arrives here.  timeline.record decides whether
    # there is anything to store -- reloading an unchanged file adds nothing -- and never
    # raises, so a history that cannot be written cannot cost the user the load.  The
    # comparison's own load comes through here too and must NOT be recorded; diffload
    # wraps its window in timeline.suppressed().
    timeline.record(file_to_parse)

    build_tasker_tables(state=state)
    # The highest Task/Profile id as the file has it, before this session adds anything -- the
    # floor taskedit.next_unique_task_or_profile_id keeps new ids clear of (see
    # NEW_OBJECT_ID_HEADROOM).  Here rather than in build_tasker_tables, which an undo also
    # runs: the tables it rebuilds then hold this session's own new objects, and re-basing on
    # those would push the next id up again.
    state.loaded_highest_object_id = max(
        (
            int(key)
            for table_name in ("all_tasks", "all_profiles")
            for key in state.tasker_root_elements[table_name]
            if key.isdigit()
        ),
        default=0,
    )
