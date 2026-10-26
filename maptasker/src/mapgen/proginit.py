#! /usr/bin/env python3
"""proginit: perform program initialization functions"""

#                                                                                      #
# proginit: perform program initialization functions                                   #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
import atexit
import sys
from json import dumps, loads
from pathlib import Path

from maptasker.src.core import console
from maptasker.src.core.colrmode import set_color_mode
from maptasker.src.core.config import DARK_MODE, GUI
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.core.mtexcept import MapTaskerError
from maptasker.src.core.primitem import RunState, clear_error
from maptasker.src.core.runcfg import current_config
from maptasker.src.core.sysconst import (
    COUNTER_FILE,
    TYPES_OF_COLOR_NAMES,
    logger,
)
from maptasker.src.mapgen.frontmtr import output_the_front_matter
from maptasker.src.mapgen.getbakup import get_backup_file
from maptasker.src.mapgen.taskerd import get_the_xml_data


# Use a counter to determine if this is the first time run.
#  If first time only, then provide a user prompt to locate the backup file
def read_counter() -> int:
    """
    Read the program counter
    Get the count of the number of times MapTasker has been called
        Parameters: none
        Returns: the count of the number of times the program has been called
    """
    try:
        with open(COUNTER_FILE, encoding="utf-8") as f:
            return loads(f.read()) + 1 if Path.exists(Path(COUNTER_FILE).resolve()) else 0
    except FileNotFoundError:
        return 0


def write_counter() -> None:
    """
    Write the program counter
    Write out the number of times MapTasker has been called
        Parameters: none
        Returns: none
    """
    with open(COUNTER_FILE, "w", encoding="utf-8") as f:
        f.write(dumps(run_counter))


run_counter = read_counter()
atexit.register(write_counter)


# Prompt user to select the backup xml file to use.
def prompt_for_backup_file(_dir_path: Path | str, state: RunState) -> None:
    """
    Prompt user to select a backup file
    Args:
        dir_path (str): Path to initial directory for file selection dialog
    Raises:
        MapTaskerError: code 6, when no file was chosen.
    """
    if state.file_to_get is None:
        message = "Backup file selection canceled.  Program ended."
        raise MapTaskerError(message, 6)


# Open and read the Tasker backup XML file
# Return the file name for use for
def open_and_get_backup_xml_file(state: RunState) -> None:
    """
    Open the Tasker backup file and return the file object
    """
    # Fetch backup xml directly from Android device?
    if (
        state.program_arguments.android_ipaddr
        and state.program_arguments.android_file
        and state.program_arguments.android_port
    ):
        backup_file_name = get_backup_file(state=state)

        # Make sure we automatically use the file we just fetched
        state.program_arguments.file = backup_file_name

    logger.info("entry")

    # Reset the file name
    state.file_to_get = None

    # Reset any error left over from an earlier, unrelated failed load attempt (e.g. a
    # missing file from a previous session): the window records the last one on the run state
    # (see error.record_error) and nothing else puts error_code back to 0, so build_html's own
    # check for a pending error would otherwise keep rejecting every subsequent load -- even a
    # brand new, valid file the user just picked via "Get Local XML File" -- with that stale
    # error, forever.
    clear_error(state)

    # Get current directory
    dir_path = Path.cwd()
    logger.info(f"dir_path: {dir_path}")

    # See if we already have the file
    if state.program_arguments.file:
        # The GUI keeps the open file itself here; a command line run keeps the path.
        given = state.program_arguments.file
        filename = given if isinstance(given, str) else getattr(given, "name", "")

        # We already have the file name...open it.
        try:
            state.file_to_get = open(filename, encoding="utf-8")
            # PrimeItems.file_to_get is now an open file object that can be read from.
        except FileNotFoundError as error:
            message = f"XML file {filename} not found."
            raise MapTaskerError(message, 6) from error
        except PermissionError as error:
            message = f"XML file {filename} not accessible."
            raise MapTaskerError(message, 6) from error
    else:
        prompt_for_backup_file(dir_path, state=state)


# Build color dictionary
def setup_colors(state: RunState) -> dict:
    """
    Determine and set colors to use in the output
        Args:
            None

        Returns:
            dict: dictionary of colors to use.
    """

    # Runtime argument "appearance" establishes the mode.
    # If it is not specified, then DARK_MODE from config.py sets mode.
    if state.program_arguments.appearance_mode == "system":
        appearance = "dark" if DARK_MODE else "light"
    else:
        appearance = state.program_arguments.appearance_mode
        return set_color_mode(appearance)

    colors_to_use = set_color_mode(appearance)

    # See if a color has already been assigned.  If so, keep it.  Otherwise,
    # use default from set_color_mode.
    for color_argument_name in TYPES_OF_COLOR_NAMES.values():
        if assigned := state.colors_to_use.get(color_argument_name):
            colors_to_use[color_argument_name] = assigned

    return colors_to_use


# Open and read xml and output the introduction/heading matter
def get_data_and_output_intro(do_front_matter: bool, state: RunState) -> None:
    """
    Gets data from Tasker backup file and outputs introductory information.

    Args:
        do_front_matter (bool): True = output the front matter, False = don't bother
    Raises:
        MapTaskerError: when there is no file to read or it is not a Tasker backup.  The window and the
            command line decide what that means; see error.report_error.

    Processing Logic:
    - Opens and reads the Tasker backup XML file
    - Extracts all the XML data from the file
    - Closes the file after reading
    - Outputs initial information like header and source to the user
    """
    # Only get the XML if we don't already have it.
    tasker_root_elements = state.tasker_root_elements
    if (
        not tasker_root_elements["all_projects"]
        and not tasker_root_elements["all_profiles"]
        and not tasker_root_elements["all_tasks"]
        and not tasker_root_elements["all_scenes"]
    ):
        # We don't yet have the data.  Let's get it.
        if not state.program_arguments.file:
            chosen = state.file_to_get if state.file_to_use == "" else state.file_to_use
            # By name: what is reopened (see open_and_get_backup_xml_file) is the file the name points at.
            state.program_arguments.file = chosen if isinstance(chosen, str) else str(getattr(chosen, "name", ""))

        # Only display message box if we don't yet have the file name,
        # if this is not the first time ever that we have run (run_counter < 1),
        # and not running from the GUI.
        if not state.file_to_get and run_counter < 1 and not GUI:
            msg = translate_string("Locate the Tasker XML file to use to map your Tasker environment")
            console.say(f"MapTasker: {msg}")

        # Open and read the file...
        open_and_get_backup_xml_file(state=state)

        # Go get all the xml data, and close the file whether or not it could be read.  By now it is the
        # open file, but a failed open leaves a path or nothing.
        try:
            get_the_xml_data(state=state)
        finally:
            if (close := getattr(state.file_to_get, "close", None)) is not None:
                close()

    # Output the inital info: head, source, etc. ...if it hasn't already been output.
    if do_front_matter and not state.output_lines.output_lines:
        output_the_front_matter(current_config(state), state=state)


# Make sure we have the appropriate version of Python
def check_versions() -> None:
    """
    Checks the Python version
    Args:
        None: No arguments
    Returns:
        None: Does not return anything
    - It gets the Python version and splits it into major, minor, and patch numbers
    - It checks if the major version is less than 3 or the major is 3 and minor is less than 11
    - If the check fails, it raises MapTaskerError
    """
    msg = ""
    version = sys.version
    version = version.split(" ")
    major, minor, _ = (int(x, 10) for x in version[0].split("."))
    if major < 3 or (major == 3 and minor < 11):
        msg = f"Python version {sys.version} is not supported.  Please use Python 3.11 or greater."
    if msg:
        # Code 1, not 0: an unsupported interpreter is a failed run, and the exit status
        # is what a shell script wrapping MapTasker actually tests.  Raised rather than exit()ed
        # so this is survivable when MapTasker is not the whole process; mapit_all says why.
        raise MapTaskerError(msg, 1)


# Where Tasker publishes the Event and State code constants.
EVENT_CODES_URL = "https://tasker.joaoapps.com/code/EventCodes.java"
STATE_CODES_URL = "https://tasker.joaoapps.com/code/StateCodes.java"


def rebuild_action_tables(state: RunState) -> None:
    """
    Refresh the half of the action code tables that Tasker does not publish as json.

    FOR DEVELOPMENT ONLY -- reaches the network and rewrites files in the source tree.
    Dropping Tasker's new task_all_actions.json into assets/json is the whole of the
    other half: actionc.py reads that file directly.  What is left is what it does not
    describe, which is what this checks and rebuilds.  See valcodes.py.

    Args:
        None
    Returns:
        None
    """
    # Only done here, because these reach the network and the backup xml.
    from maptasker.src.core.bldargs import build_arguments  # noqa: PLC0415
    from maptasker.src.core.bldbndle import build_bundles  # noqa: PLC0415
    from maptasker.src.core.valcodes import validate_states_and_events  # noqa: PLC0415

    # Every finding these report goes through valcodes.debug_print, which says nothing
    # at all unless debug is on -- so without this the rebuild runs silently.
    state.program_arguments.debug = True

    # Check the Event and State codes in the overlay against Tasker's own source.
    validate_states_and_events("e", EVENT_CODES_URL, state=state)
    validate_states_and_events("s", STATE_CODES_URL, state=state)
    # Build the <Bundle> dictionary ('bundles.json') from the backup xml.
    build_bundles()
    # Add any arguments the backup xml uses that neither action code table declares.
    build_arguments()
