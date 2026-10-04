"""Read in XML"""

#! /usr/bin/env python3

#                                                                                      #
# taskerd: get Tasker data from backup xml                                             #
#                                                                                      #
import defusedxml.ElementTree as ET

from maptasker.src import sessundo, timeline
from maptasker.src.error import error_handler
from maptasker.src.primitem import RunState
from maptasker.src.sysconst import FormatLine
from maptasker.src.taskertables import build_tasker_tables, get_first_action, move_xml_to_table
from maptasker.src.xmldata import parse_tasker_xml, rewrite_xml

# build_tasker_tables, get_first_action and move_xml_to_table lived here until they were split
# out (see taskertables); a good many callers and tests still reach them as taskerd.<name>.
__all__ = ["build_tasker_tables", "get_first_action", "get_the_xml_data", "move_xml_to_table"]


# Load all of the Projects, Profiles and Tasks into a format we can easily
# navigate through.
# Optimized
def get_the_xml_data(state: RunState) -> bool:
    # Put this code into a while loop in the event we have to re-call it again.
    """Gets the XML data from a Tasker backup file and returns it in a dictionary.
    Parameters:
        - None
    Returns:
        - int: 0 if successful, 1 if bad XML, 2 if not a Tasker backup file, 3 if not a valid Tasker backup file.
    Processing Logic:
        - Put code into a while loop in case it needs to be re-called.
        - Defines XML parser with ISO encoding.
        - If encoding error, rewrites XML with proper encoding and tries again.
        - If any other error, logs and exits.
        - Returns 1 if bad XML and not in GUI mode.
        - Returns 1 if bad XML and in GUI mode.
        - Gets XML root.
        - Checks for valid Tasker backup file.
        - Moves all data into dictionaries.
        - Returns all data in a dictionary."""
    file_to_parse = state.file_to_get.name
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
                error_handler(f"Error in {file_to_parse}: {e}", 1, state=state)
                return 1
            _rewrite_xml(file_to_parse)

    if state.xml_tree is None:
        return 1 if not state.program_arguments.gui else _handle_gui_error("Bad XML file", state=state)

    state.xml_root = state.xml_tree.getroot()
    if state.xml_root.tag != "TaskerData":
        return _handle_gui_error("Invalid Tasker backup XML file", code=3, state=state)

    # A different configuration is now the loaded one, so the session's undo history no
    # longer describes it -- see sessundo.clear() for what undoing into another file's
    # checkpoint would do.  Here rather than at the buttons that load a file (Get XML, the
    # Android fetch, the switch to the copy a "Save To Current File" just wrote) because
    # this is the one place all of them go through, and the one this must not be missed at.
    #
    # diffload puts the history back afterwards: it comes through here too, to parse the
    # file being compared against, and that load does not replace what the user has open.
    sessundo.clear()

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
    return 0


def _handle_gui_error(message: str, code: int = 1, *, state: RunState) -> int:
    state.output_lines.add_line_to_output(0, message, FormatLine.dont_format_line)
    if state.program_arguments.gui:
        state.error_msg = message
    return code
