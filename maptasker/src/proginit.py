#! /usr/bin/env python3
"""proginit: perform program initialization functions"""

#                                                                                      #
# proginit: perform program initialization functions                                   #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
import atexit
import contextlib
import sys
from collections import namedtuple
from json import dumps, loads
from pathlib import Path

from maptasker.src import console
from maptasker.src.colrmode import set_color_mode
from maptasker.src.config import DARK_MODE, GUI
from maptasker.src.error import error_handler, exit_program
from maptasker.src.frontmtr import output_the_front_matter
from maptasker.src.getbakup import get_backup_file
from maptasker.src.maputil2 import translate_string
from maptasker.src.primitem import PrimeItems, clear_error
from maptasker.src.runcfg import current_config
from maptasker.src.sysconst import (
    COUNTER_FILE,
    TYPES_OF_COLOR_NAMES,
    logger,
)
from maptasker.src.taskerd import get_the_xml_data

# Define the action code fields and arguments.
ActionCode = namedtuple(  # noqa: PYI024
    "ActionCode",
    ("redirect", "args", "name", "category", "canfail"),
)
ArgumentCode = namedtuple(  # noqa: PYI024
    "ArgumentCode",
    ["arg_id", "arg_required", "arg_name", "arg_type", "arg_eval"],
)


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
        with open(COUNTER_FILE) as f:
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
    with open(COUNTER_FILE, "w") as f:
        f.write(dumps(run_counter))


run_counter = read_counter()
atexit.register(write_counter)


# Prompt user to select the backup xml file to use.
def prompt_for_backup_file(_dir_path: str) -> None:
    """
    Prompt user to select a backup file
    Args:
        dir_path (str): Path to initial directory for file selection dialog
    Returns:
        None: No value is returned
    Processing Logic:
        - Try to open a file selection dialog to choose an XML backup file
        - Set a flag if any exception occurs or no file is selected
        - Check the flag and call an error handler if running without GUI
        - Set an error code if running with GUI
    """
    file_error = False

    if PrimeItems.file_to_get is None:
        file_error = True
    if file_error and not PrimeItems.program_arguments["gui"]:
        error_handler("Backup file selection canceled.  Program ended.", 6)
    elif file_error:
        PrimeItems.error_code = 5


# Open and read the Tasker backup XML file
# Return the file name for use for
def open_and_get_backup_xml_file() -> dict:
    """
    Open the Tasker backup file and return the file object
    """
    # Fetch backup xml directly from Android device?
    if (
        PrimeItems.program_arguments["android_ipaddr"]
        and PrimeItems.program_arguments["android_file"]
        and PrimeItems.program_arguments["android_port"]
    ):
        backup_file_name = get_backup_file()

        # If no backup file and we're coming from the GUI, then return to GUI.
        if backup_file_name is None and PrimeItems.program_arguments["gui"]:
            return None

        # Make sure we automatically use the file we just fetched
        PrimeItems.program_arguments["file"] = backup_file_name

    logger.info("entry")

    # Reset the file name
    PrimeItems.file_to_get = None

    # Reset any error left over from an earlier, unrelated failed load attempt (e.g. a
    # missing file from a previous session) -- error_handler sets PrimeItems.error_code
    # but nothing ever clears it back to 0 on success, so get_data_and_output_intro's own
    # "if PrimeItems.error_code > 0: return PrimeItems.error_code" check would otherwise
    # keep rejecting every subsequent load (even a brand new, valid file the user just
    # picked via "Get Local XML File") with that stale error, forever.
    clear_error()

    # Get current directory
    dir_path = Path.cwd()
    logger.info(f"dir_path: {dir_path}")

    # See if we already have the file
    if PrimeItems.program_arguments["file"]:
        filename = isinstance(PrimeItems.program_arguments["file"], str)
        filename = PrimeItems.program_arguments["file"].name if not filename else PrimeItems.program_arguments["file"]

        # We already have the file name...open it.
        try:
            PrimeItems.file_to_get = open(filename)
            # PrimeItems.file_to_get is now an open file object that can be read from.
        except FileNotFoundError:
            file_not_found = filename
            error_handler(f"XML file {file_not_found} not found.", 6)
        except PermissionError:
            error_handler(f"XML file {filename} not accessible.", 100)
            prompt_for_backup_file(dir_path)
    else:
        prompt_for_backup_file(dir_path)

    return


# Build color dictionary
def setup_colors() -> dict:
    """
    Determine and set colors to use in the output
        Args:
            None

        Returns:
            dict: dictionary of colors to use.
    """

    # Runtime argument "appearance" establishes the mode.
    # If it is not specified, then DARK_MODE from config.py sets mode.
    if PrimeItems.program_arguments["appearance_mode"] == "system":
        appearance = "dark" if DARK_MODE else "light"
    else:
        appearance = PrimeItems.program_arguments["appearance_mode"]
        return set_color_mode(appearance)

    colors_to_use = set_color_mode(appearance)

    # See if a color has already been assigned.  If so, keep it.  Otherwise,
    # use default from set_color_mode.
    with contextlib.suppress(Exception):
        if PrimeItems.colors_to_use:
            for color_argument_name in TYPES_OF_COLOR_NAMES.values():
                try:
                    if PrimeItems.colors_to_use[color_argument_name]:
                        colors_to_use[color_argument_name] = PrimeItems.colors_to_use[color_argument_name]
                except KeyError:
                    continue

    return colors_to_use


# Open and read xml and output the introduction/heading matter
def get_data_and_output_intro(do_front_matter: bool) -> int:
    """
    Gets data from Tasker backup file and outputs introductory information.

    Args:
        do_front_matter (bool): True = output the front matter, False = don't bother
    Returns:
        int: 0 if okay, non-zero if error (error code)

    Processing Logic:
    - Opens and reads the Tasker backup XML file
    - Extracts all the XML data from the file
    - Closes the file after reading
    - Outputs initial information like header and source to the user
    """
    # Only get the XML if we don't already have it.
    tasker_root_elements = PrimeItems.tasker_root_elements
    return_code = 0
    if (
        not tasker_root_elements["all_projects"]
        and not tasker_root_elements["all_profiles"]
        and not tasker_root_elements["all_tasks"]
        and not tasker_root_elements["all_scenes"]
    ):
        # We don't yet have the data.  Let's get it.
        if not PrimeItems.program_arguments["file"]:
            PrimeItems.program_arguments["file"] = (
                PrimeItems.file_to_get if PrimeItems.file_to_use == "" else PrimeItems.file_to_use
            )

        # Only display message box if we don't yet have the file name,
        # if this is not the first time ever that we have run (run_counter < 1),
        # and not running from the GUI.
        if not PrimeItems.file_to_get and run_counter < 1 and not GUI:
            msg = translate_string("Locate the Tasker XML file to use to map your Tasker environment")
            console.say(f"MapTasker: {msg}")

        # Open and read the file...
        open_and_get_backup_xml_file()
        if PrimeItems.error_code > 0:
            return PrimeItems.error_code

        # Go get all the xml data
        return_code = get_the_xml_data()

        # Close the file
        PrimeItems.file_to_get.close()

    # Output the inital info: head, source, etc. ...if it hasn't already been output.
    if return_code == 0 and do_front_matter and not PrimeItems.output_lines.output_lines:
        output_the_front_matter(current_config())
        return 0

    return return_code


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
    - If the check fails, it logs and prints an error message and exits
    """
    msg = ""
    version = sys.version
    version = version.split(" ")
    major, minor, _ = (int(x, 10) for x in version[0].split("."))
    if major < 3 or (major == 3 and minor < 11):
        msg = f"Python version {sys.version} is not supported.  Please use Python 3.11 or greater."
    if msg:
        # Code 1, not 0: an unsupported interpreter is a failed run, and the exit status
        # is what a shell script wrapping MapTasker actually tests.  exit_program rather
        # than exit() so this is survivable when MapTasker is not the whole process.
        console.error(msg)
        exit_program(1)


# Where Tasker publishes the Event and State code constants.
EVENT_CODES_URL = "https://tasker.joaoapps.com/code/EventCodes.java"
STATE_CODES_URL = "https://tasker.joaoapps.com/code/StateCodes.java"


def rebuild_action_tables() -> None:
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
    from maptasker.src.bldargs import build_arguments  # noqa: PLC0415
    from maptasker.src.bldbndle import build_bundles  # noqa: PLC0415
    from maptasker.src.valcodes import validate_states_and_events  # noqa: PLC0415

    # Every finding these report goes through valcodes.debug_print, which says nothing
    # at all unless debug is on -- so without this the rebuild runs silently.
    PrimeItems.program_arguments["debug"] = True

    # Check the Event and State codes in the overlay against Tasker's own source.
    validate_states_and_events("e", EVENT_CODES_URL)
    validate_states_and_events("s", STATE_CODES_URL)
    # Build the <Bundle> dictionary ('bundle.py') from the backup xml.
    build_bundles()
    # Add any arguments the backup xml uses that neither action code table declares.
    build_arguments()
