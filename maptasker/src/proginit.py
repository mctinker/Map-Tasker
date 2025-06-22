#! /usr/bin/env python3  # noqa: D100

#                                                                                      #
# proginit: perform program initialization functions                                   #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
import atexit
import contextlib
import json
import os
import platform
import sys
from collections import namedtuple
from json import dumps, loads
from pathlib import Path
from tkinter import TkVersion, messagebox

# importing askopenfile (from class filedialog) and messagebox functionsy
from tkinter.filedialog import askopenfile

import maptasker.src.progargs as get_arguments
from maptasker.src.colrmode import set_color_mode
from maptasker.src.config import DARK_MODE, GUI
from maptasker.src.error import error_handler

# from maptasker.src.fonts import get_fonts
from maptasker.src.frontmtr import output_the_front_matter
from maptasker.src.getbakup import get_backup_file
from maptasker.src.maputils import exit_program
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import (
    COUNTER_FILE,
    MY_VERSION,
    NOW_TIME,
    TYPES_OF_COLOR_NAMES,
    logger,
    logging,
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
            return (
                loads(f.read()) + 1 if Path.exists(Path(COUNTER_FILE).resolve()) else 0
            )
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
def prompt_for_backup_file(dir_path: str) -> None:
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
    # Tkinter prompt for file selection.
    try:
        PrimeItems.file_to_get = askopenfile(
            parent=PrimeItems.tkroot,
            mode="r",
            title="Select Tasker backup xml file",
            initialdir=dir_path,
            filetypes=[("XML Files", "*.xml")],
        )
        PrimeItems.error_code = 0  # No error.  Clear the code if there is one.
    except Exception:  # noqa: BLE001
        file_error = True
    if PrimeItems.file_to_get is None:
        file_error = True
    if file_error and not PrimeItems.program_arguments["gui"]:
        error_handler("Backup file selection canceled.  Program ended.", 6)
    elif file_error:
        PrimeItems.error_code = 6


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

    # Get current directory
    dir_path = Path.cwd()
    logger.info(f"dir_path: {dir_path}")

    # See if we already have the file
    if PrimeItems.program_arguments["file"]:
        filename = isinstance(PrimeItems.program_arguments["file"], str)
        filename = (
            PrimeItems.program_arguments["file"].name
            if not filename
            else PrimeItems.program_arguments["file"]
        )

        # We already have the file name...open it.
        try:
            PrimeItems.file_to_get = open(filename)
        except FileNotFoundError:
            file_not_found = filename
            error_handler(f"XML file {file_not_found} not found.", 5)
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
                        colors_to_use[color_argument_name] = PrimeItems.colors_to_use[
                            color_argument_name
                        ]
                except KeyError:
                    continue

    return colors_to_use


# Set up logging
def setup_logging() -> None:
    """
    Set up the logging: name the file and establish the log type and format
    """
    # Add the date and time to the log filename.
    file_name = f"maptasker_{NOW_TIME.month}-{NOW_TIME.day}-{NOW_TIME.year}_{NOW_TIME.hour}-{NOW_TIME.minute}-{NOW_TIME.second}.log"
    logging.basicConfig(
        filename=file_name,
        filemode="w",
        format="%(asctime)s,%(msecs)d %(levelname)s %(name)s %(funcName)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.DEBUG,
    )
    logger.info(sys.version_info)


# Log the arguments
def log_startup_values() -> None:
    """
    Log the runtime arguments and color mappings
    """
    setup_logging()  # Get logging going
    logger.info(f"{MY_VERSION} {str(NOW_TIME)}")  # noqa: RUF010
    logger.info(f"sys.argv:{str(sys.argv)}")  # noqa: RUF010
    for key, value in PrimeItems.program_arguments.items():
        logger.info(f"{key}: {value}")
    for key, value in PrimeItems.colors_to_use.items():
        logger.info(f"colormap for {key} set to {value}")


# POpen and read xml and output the introduction/heading matter
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
                PrimeItems.file_to_get
                if PrimeItems.file_to_use == ""
                else PrimeItems.file_to_use
            )

        # Only display message box if we don't yet have the file name,
        # if this is not the first time ever that we have run (run_counter < 1),
        # and not running from the GUI.
        if not PrimeItems.file_to_get and run_counter < 1 and not GUI:
            msg = "Locate the Tasker XML file to use to map your Tasker environment"
            messagebox.showinfo("MapTasker", msg)

        # Open and read the file...
        open_and_get_backup_xml_file()
        if PrimeItems.error_code > 0:
            return PrimeItems.error_code

        # Go get all the xml data
        return_code = get_the_xml_data()

        # Close the file
        PrimeItems.file_to_get.close()

    # Output the inital info: head, source, etc. ...if it hasn't already been output.
    if (
        return_code == 0
        and do_front_matter
        and not PrimeItems.output_lines.output_lines
    ):
        output_the_front_matter()
        return 0

    return return_code


# Make sure we have the appropriate version of Python and Tkinter
def check_versions() -> None:
    """
    Checks the Python and Tkinter versions
    Args:
        None: No arguments
    Returns:
        None: Does not return anything
    - It gets the Python version and splits it into major, minor, and patch numbers
    - It checks if the major version is less than 3 or the major is 3 and minor is less than 11
    - It gets the Tkinter version and splits it into major and minor
    - It checks if the major is less than 8 or the major is 8 and minor is less than 6
    - If either check fails, it logs and prints an error message and exits
    """
    msg = ""
    version = sys.version
    version = version.split(" ")
    major, minor, _ = (int(x, 10) for x in version[0].split("."))
    if major < 3 or (major == 3 and minor < 11):
        msg = f"Python version {sys.version} is not supported.  Please use Python 3.11 or greater."
    version = str(TkVersion)
    major, minor = version.split(".")
    if int(major) < 8 or (int(major) == 8 and int(minor) < 6):
        msg = f"{msg}  Tcl/tk (Tkinter) version {TkVersion} is not supported.  Please use Tkinter version 8.6 or greater."
        logger.error(msg)
    if msg:
        logger.error("MapTasker", msg)
        print(msg)
        exit(0)  # noqa: PLR1722


def build_action_codes(build_it_all: bool = False) -> None:
    """
    Builds the action codes dictionary from the Tasker JSON files.
    Args:
        build_it_all(bool): True = build all action codes, False = build only new action spec codes
    Returns:
        None
    """
    # Point to the JSON directory
    current_dir = os.getcwd()
    abspath = os.path.abspath(__file__)
    json_dir = os.path.dirname(abspath).replace(
        "src",
        f"assets{PrimeItems.slash}json{PrimeItems.slash}",
    )
    # Switch to our temp directory (assets)
    os.chdir(json_dir)

    # Get the map of all Tasker task action argument types
    try:
        with open(f"{json_dir}arg_specs.json", encoding="utf-8") as file:
            PrimeItems.tasker_arg_specs = json.load(file)
            spec_number = len(PrimeItems.tasker_arg_specs)
            # Add extras for new action specs
            PrimeItems.tasker_arg_specs[str(spec_number)] = "ConditionList"
            PrimeItems.tasker_arg_specs[str(spec_number + 1)] = "Img"
            for key, value in PrimeItems.tasker_arg_specs.items():
                if value == "String":
                    PrimeItems.tasker_arg_specs[key] = "Str"
                    break
    except FileNotFoundError:
        logger.error("arg_specs missing!")

    # If building it all, then get the map of all Tasker task action codes and their arguments, states, and events.
    if build_it_all:
        from maptasker.src.acmerge import merge_action_codes, validate_states_and_events

        # Make sure we see the output
        PrimeItems.program_arguments["debug"] = True

        # Get the map of all Tasker task action codes and their arguments
        with open(f"{json_dir}task_all_actions.json", encoding="utf-8") as file:
            # NOTE: 'spec' defines the argument value:
            # t:n:? = text where 'n' is number of input lines; ? means optional.
            # n:nn = range of numbers; nn is the maximum number.
            # h:m:s = time
            # plus more...
            tasker_codes = json.load(file)

        # Go thru the list of dictionaries and build our own dictionary from task_all_actions.json contents.
        for value in tasker_codes:
            PrimeItems.tasker_action_codes[str(value["code"])] = {
                "args": value["args"],
                "canfail": value.get("canFail", False),
                "category_code": value["categoryCode"],
                "name": value["name"],
            }
        # Sort the dictionary
        PrimeItems.tasker_action_codes = dict(
            sorted(PrimeItems.tasker_action_codes.items()),
        )

        # Get the action category description
        with open(f"{json_dir}category_descriptions.json", encoding="utf-8") as file:
            category_descriptions = json.load(file)
            for description in category_descriptions:
                PrimeItems.tasker_category_descriptions[description["code"]] = (
                    description["name"]
                )

        # Merge actionc with this new data to create a new dictionary
        merge_action_codes()

        # Validate event codes
        url = "https://tasker.joaoapps.com/code/EventCodes.java"
        validate_states_and_events("e", url)

        # Validate the state codes
        url = "https://tasker.joaoapps.com/code/StateCodes.java"
        validate_states_and_events("s", url)

        PrimeItems.tasker_action_codes.clear()

    # Put the directory back to where it should be.
    os.chdir(current_dir)


# Perform maptasker program initialization functions
def start_up() -> dict:
    # Get any arguments passed to program
    """
    Initializes the program startup.
    Args:
        None
    Returns:
        None
    Processing Logic:
        - Gets any arguments passed to the program
        - Migrates any old argument files to a new format
        - Gets runtime arguments from the command line or GUI
        - Gets the list of available fonts
        - Gets a map of colors to use
        - Gets key program elements and outputs intro text
        - Logs startup values if debug mode is enabled
    """
    # If debug mode, fire-up the log.
    if "-d" in sys.argv or "-debug" in sys.argv:
        log_startup_values()
    logger.info(f"sys.argv{sys.argv!s}")

    # Get the OS so we know which directory slash to use (/ or \)
    our_platform = platform.system()
    if our_platform == "Windows":
        PrimeItems.slash = "\\"
    else:
        PrimeItems.slash = "/"

    # Validate runtime versions for python and tkinter
    check_versions()

    # Build the action codes
    # NOTE: FOR DEVELOPMENT ONLY!!! 'BUILD_ALL = TRUE' ONLY WITH NEW UPDATE OF TASKER!  See acmerge.py
    build_all = False
    build_action_codes(build_it_all=build_all)
    if build_all:
        exit_program(0)
    # END OF DEVELOPMENT CODE

    # Get runtime arguments (from CLI or GUI)
    get_arguments.get_program_arguments()

    # Get our map of colors if we don't have them.
    if not PrimeItems.colors_to_use:
        PrimeItems.colors_to_use = setup_colors()

    # Display a popup window telling user we are analyzing
    if PrimeItems.program_arguments["doing_diagram"]:
        PrimeItems.program_arguments["doing_diagram"] = False

    # Get the XML data and output the front matter
    _ = get_data_and_output_intro(True)

    return
