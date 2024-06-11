#! /usr/bin/env python3  # noqa: D100

#                                                                                      #
# proginit: perform program initialization functions                                   #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
import atexit
import contextlib
import platform
import sys
from json import dumps, loads  # For write and read counter
from pathlib import Path
from tkinter import TkVersion, messagebox

# importing askopenfile (from class filedialog) and messagebox functions
from tkinter.filedialog import askopenfile

import maptasker.src.progargs as get_arguments
from maptasker.src.colrmode import set_color_mode
from maptasker.src.config import DARK_MODE, GUI
from maptasker.src.error import error_handler

# from maptasker.src.fonts import get_fonts
from maptasker.src.frontmtr import output_the_front_matter
from maptasker.src.getbakup import get_backup_file
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

    # If debug and we didn't fetch the backup file from Android device, default to
    # "backup.xml" file as backup to restore
    if (
        PrimeItems.program_arguments["debug"]
        and PrimeItems.program_arguments["fetched_backup_from_android"] is False
        and not PrimeItems.program_arguments["file"]
    ):
        PrimeItems.program_arguments["file"] = ""
        try:
            PrimeItems.file_to_get = open(f"{dir_path}{PrimeItems.slash}backup.xml")
        except OSError:
            error_handler(
                (f"Error: Debug is on and the backup.xml file was not found in {dir_path}."),
                3,
            )
            prompt_for_backup_file(dir_path)

    # See if we already have the file
    elif PrimeItems.program_arguments["file"]:
        filename = isinstance(PrimeItems.program_arguments["file"], str)
        filename = PrimeItems.program_arguments["file"].name if not filename else PrimeItems.program_arguments["file"]

        # We already have the file name...open it.
        try:
            PrimeItems.file_to_get = open(filename)
        except FileNotFoundError:
            file_not_found = filename
            error_handler(f"Backup file {file_not_found} not found.  Program ended.", 6)
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
                except KeyError:  # noqa: PERF203
                    continue

    return colors_to_use


# Set up logging
def setup_logging() -> None:
    """
    Set up the logging: name the file and establish the log type and format
    """
    logging.basicConfig(
        filename="maptasker.log",
        filemode="w",
        format="%(asctime)s,%(msecs)d %(levelname)s %(name)s %(funcName)s %(message)s",
        datefmt="%H:%M:%S",
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
                PrimeItems.file_to_get if PrimeItems.file_to_use == "" else PrimeItems.file_to_use
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
    if return_code == 0 and do_front_matter and not PrimeItems.output_lines.output_lines:
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
    major, minor, patch = (int(x, 10) for x in version[0].split("."))
    if major < 3 or (major == 3 and minor < 11):
        msg = f"Python version {sys.version} is not supported.  Please use Python 3.11 or greater."
    version = str(TkVersion)
    major, minor = version.split(".")
    if int(major) < 8 or (int(major) == 8 and int(minor) < 6):
        msg = (
            f"{msg}  Tcl/tk (Tkinter) version {TkVersion} is not supported.  Please use Tkinter version 8.6 or greater."
        )
        logger.error(msg)
    if msg:
        logger.error("MapTasker", msg)
        print(msg)
        exit(0)  # noqa: PLR1722


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
    logger.info(f"sys.argv{sys.argv!s}")

    # Get the OS so we know which directory slash to use (/ or \)
    our_platform = platform.system()
    if our_platform == "Windows":
        PrimeItems.slash = "\\"
    else:
        PrimeItems.slash = "/"

    # Validate runtime versions
    check_versions()

    # Get runtime arguments (from CLI or GUI)
    get_arguments.get_program_arguments()

    # Get our list of fonts
    # _ = get_fonts(True)

    # Get our map of colors
    PrimeItems.colors_to_use = setup_colors()

    # Get the XML data and output the front matter
    _ = get_data_and_output_intro(True)

    # If debug mode, log the arguments
    if PrimeItems.program_arguments["debug"]:
        log_startup_values()

    return
