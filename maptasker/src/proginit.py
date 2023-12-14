#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# proginit: perform program initialization functions                                   #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #

import atexit
import contextlib
import sys
from datetime import datetime
from json import dumps, loads  # For write and read counter
from pathlib import Path

# importing tkinter and tkinter.ttk and all their functions and classes
from tkinter import Tk, messagebox

# importing askopenfile (from class filedialog) and messagebox functions
from tkinter.filedialog import askopenfile

import maptasker.src.migrate as old_to_new
import maptasker.src.progargs as get_arguments
from maptasker.src.colrmode import set_color_mode
from maptasker.src.config import DARK_MODE, GUI
from maptasker.src.error import error_handler
from maptasker.src.fonts import get_fonts
from maptasker.src.frontmtr import output_the_front_matter
from maptasker.src.getbakup import get_backup_file
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import (
    COUNTER_FILE,
    MY_VERSION,
    TYPES_OF_COLOR_NAMES,
    logger,
    logging,
)
from maptasker.src.taskerd import get_the_xml_data


# ##################################################################################
# Use a counter to determine if this is the first time run.
#  If first time only, then provide a user prompt to locate the backup file
# ##################################################################################
def read_counter():
    """
    Read the program counter
    Get the count of the number of times MapTasker has been called
        Parameters: none
        Returns: the count of the number of times the program has been called
    """
    return loads(open(COUNTER_FILE, "r").read()) + 1 if Path.exists(Path(COUNTER_FILE).resolve()) else 0


def write_counter():
    """
    Write the program counter
    Write out the number of times MapTasker has been called
        Parameters: none
        Returns: none
    """
    with open(COUNTER_FILE, "w") as f:
        f.write(dumps(run_counter))
    return


run_counter = read_counter()
atexit.register(write_counter)


# ##################################################################################
# Open and read the Tasker backup XML file
# Return the file name for use for
# ##################################################################################
def open_and_get_backup_xml_file() -> dict:
    """
    Open the Tasker backup file and return the file object
    """
    # Fetch backup xml directly from Android device?
    if PrimeItems.program_arguments["backup_file_http"] and PrimeItems.program_arguments["backup_file_location"]:
        backup_file_name = get_backup_file()
        # Make sure we automatically use the file we just fetched
        PrimeItems.program_arguments["file"] = backup_file_name

    logger.info("entry")
    file_error = False
    # Initialize tkinter
    tkroot = Tk()
    tkroot.geometry("200x100")
    tkroot.title("Select Tasker backup xml file")
    PrimeItems.file_to_get = None

    # dir_path = path.dirname(path.realpath(__file__))  # Get current directory
    dir_path = Path.cwd()
    logger.info(f"dir_path: {dir_path}")

    # If debug and we didn't fetch the backup file from Android device, default to
    # "backup.xml" file as backup to restore

    if PrimeItems.program_arguments["debug"] and PrimeItems.program_arguments["fetched_backup_from_android"] is False:
        PrimeItems.program_arguments["file"] = ""
        try:
            PrimeItems.file_to_get = open(f"{dir_path}/backup.xml", "r")
        except OSError:
            error_handler(
                (f"Error: The backup.xml file was not found in {dir_path}.  Program" " terminated!"),
                3,
            )

    # See if we already have the file
    elif PrimeItems.program_arguments["file"]:
        filename = isinstance(PrimeItems.program_arguments["file"], str)
        if not filename:
            filename = PrimeItems.program_arguments["file"].name
        else:
            filename = PrimeItems.program_arguments["file"]

        # We already have the file name...open it.
        try:
            PrimeItems.file_to_get = open(filename, "r")
        except FileNotFoundError:
            file_not_found = filename
            error_handler(f"Backup file {file_not_found} not found.  Program ended.", 6)
    else:
        try:
            PrimeItems.file_to_get = askopenfile(
                parent=tkroot,
                mode="r",
                title="Select Tasker backup xml file",
                initialdir=dir_path,
                filetypes=[("XML Files", "*.xml")],
            )
        except Exception:
            file_error = True
        if PrimeItems.file_to_get is None:
            file_error = True
        if file_error and not PrimeItems.program_arguments["gui"]:
            error_handler("Backup file selection cancelled.  Program ended.", 6)
        elif file_error:
            PrimeItems.error_code = 6
            return
    tkroot.destroy()
    del tkroot

    return


# ##################################################################################
# Build color dictionary
# ##################################################################################
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


# ##################################################################################
# Set up logging
# ##################################################################################
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


# ##################################################################################
# Log the arguments
# ##################################################################################
def log_startup_values() -> None:
    """
    Log the runtime arguments and color mappings
    """
    setup_logging()  # Get logging going
    logger.info(f"{MY_VERSION} {str(datetime.now())}")
    logger.info(f"sys.argv:{str(sys.argv)}")
    for key, value in PrimeItems.program_arguments.items():
        logger.info(f"{key}: {value}")
    for key, value in PrimeItems.colors_to_use.items():
        logger.info(f"colormap for {key} set to {value}")


# ##################################################################################
# POpen and read xml and output the introduction/heading matter
# ##################################################################################
def get_data_and_output_intro() -> int:
    """
    Gets data from Tasker backup file and outputs introductory information.

    Args:
        None: None
    Returns:
        int: 0 if okay, non-zero if error (error code)

    Processing Logic:
    - Opens and reads the Tasker backup XML file
    - Extracts all the XML data from the file
    - Closes the file after reading
    - Outputs initial information like header and source to the user
    """
    PrimeItems.program_arguments["file"] = PrimeItems.file_to_get

    # Only display message box if we don't yet have the file name
    if not PrimeItems.file_to_get and run_counter < 1 and not GUI:
        msg = "Locate the Tasker backup xml file to use to map your Tasker environment"
        messagebox.showinfo("MapTasker", msg)

    # Open and read the file...
    open_and_get_backup_xml_file()
    if PrimeItems.error_code > 0:
        return PrimeItems.error_code

    # Go get all the xml data
    get_the_xml_data()

    # Close the file
    PrimeItems.file_to_get.close()

    # Output the inital info: head, source, etc.
    output_the_front_matter()

    return 0


# ##################################################################################
# Perform maptasker program initialization functions
# ##################################################################################
def start_up() -> dict:
    # Get any arguments passed to program
    logger.info(f"sys.argv{str(sys.argv)}")

    # Rename/convert any old argument file to new name/format for clarity
    # (one time only operation)
    old_to_new.migrate()

    # Get runtime arguments (from CLI or GUI)
    get_arguments.get_program_arguments()

    # Get our list of fonts
    _ = get_fonts(True)

    # Get our map of colors
    PrimeItems.colors_to_use = setup_colors()

    # get_data_and_output_intro program key elements
    PrimeItems.program_arguments["gui"] = False  # Turn off...we don't want this on anymore.
    _ = get_data_and_output_intro()

    # If debug mode, log the arguments
    if PrimeItems.program_arguments["debug"]:
        log_startup_values()

    return
