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
import datetime
import sys
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
from maptasker.src.debug import display_debug_info
from maptasker.src.error import error_handler
from maptasker.src.fonts import get_fonts
from maptasker.src.frmthtml import format_html
from maptasker.src.getbakup import get_backup_file
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
    """Read the program counter
    Get the count of the number of times MapTasker has been called
        Parameters: none
        Returns: the count of the number of times the program has been called

    """
    return (
        loads(open(COUNTER_FILE, "r").read()) + 1
        if Path.exists(Path(COUNTER_FILE).resolve())
        else 0
    )


def write_counter():
    """Write the program counter
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
def open_and_get_backup_xml_file(primary_items: dict) -> dict:
    """
    Open the Tasker backup file and return the file object
        :param primary_items:  program registry.  See primitem.py for details.
        :return: primary_items
    """
    # Fetch backup xml directly from Android device?
    if (
        primary_items["program_arguments"]["backup_file_http"]
        and primary_items["program_arguments"]["backup_file_location"]
    ):
        backup_file_name = get_backup_file(primary_items)
        # Make sure we automatically use the file we just fetched
        primary_items["program_arguments"]["file"] = backup_file_name
        print(backup_file_name)

    logger.info("entry")
    file_error = False
    # Initialize tkinter
    tkroot = Tk()
    tkroot.geometry("200x100")
    tkroot.title("Select Tasker backup xml file")
    primary_items["file_to_get"] = None

    # dir_path = path.dirname(path.realpath(__file__))  # Get current directory
    dir_path = Path.cwd()
    logger.info(f"dir_path: {dir_path}")

    # If debug and we didn't fetch the backup file from Android device, default to
    # "backup.xml" file as backup to restore

    if (
        primary_items["program_arguments"]["debug"]
        and primary_items["program_arguments"]["fetched_backup_from_android"] is False
    ):
        primary_items["program_arguments"]["file"] = ""
        try:
            primary_items["file_to_get"] = open(f"{dir_path}/backup.xml", "r")
        except OSError:
            error_handler(
                (
                    f"Error: The backup.xml file was not found in {dir_path}.  Program"
                    " terminated!"
                ),
                3,
            )

    # See if we already have the file
    elif primary_items["program_arguments"]["file"]:
        # We already have the file name...open it.
        try:
            primary_items["file_to_get"] = open(
                primary_items["program_arguments"]["file"], "r"
            )
        except FileNotFoundError:
            file_not_found = primary_items["program_arguments"]["file"]
            error_handler(f"Backup file {file_not_found} not found.  Program ended.", 6)
    else:
        try:
            primary_items["file_to_get"] = askopenfile(
                parent=tkroot,
                mode="r",
                title="Select Tasker backup xml file",
                initialdir=dir_path,
                filetypes=[("XML Files", "*.xml")],
            )
        except Exception:
            file_error = True
        if primary_items["file_to_get"] is None:
            file_error = True
        if file_error:
            error_handler("Backup file selection cancelled.  Program ended.", 6)
    tkroot.destroy()
    del tkroot

    return primary_items


# ##################################################################################
# Build color dictionary
# ##################################################################################
def setup_colors(primary_items: dict) -> dict:
    """_summary_
    Determine and set colors to use in the output
        Args:
            primary_items (dict): program registry.  See primitem.py for details.

        Returns:
            dict: dictionary of colors to use.
    """

    # Runtime argument "appearance" establishes the mode.
    # If it is not specified, then DARK_MODE from config.py sets mode.
    appearance = primary_items["program_arguments"]["appearance_mode"] or (
        "dark" if DARK_MODE else "light"
    )

    colors_to_use = set_color_mode(appearance)

    # See if a color has already been assigned.  If so, keep it.  Otherwise,
    # use default from set_color_mode.
    if primary_items["colors_to_use"]:
        for color_argument_name in TYPES_OF_COLOR_NAMES.values():
            try:
                if primary_items["colors_to_use"][color_argument_name]:
                    colors_to_use[color_argument_name] = primary_items["colors_to_use"][
                        color_argument_name
                    ]
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
def log_startup_values(primary_items: dict) -> None:
    """
    Log the runtime arguments
        :param primary_items:  program registry.  See primitem.py for details.
    """
    setup_logging()  # Get logging going
    logger.info(f"{MY_VERSION} {str(datetime.datetime.now())}")
    logger.info(f"sys.argv:{str(sys.argv)}")
    for key, value in primary_items["program_arguments"].items():
        logger.info(f"{key}: {value}")
    for key, value in primary_items["colors_to_use"].items():
        logger.info(f"colormap for {key} set to {value}")


# ##################################################################################
# POpen and read xml and output the introduction/heading matter
# ##################################################################################
def get_data_and_output_intro(
    primary_items: dict,
) -> dict:
    """
    Open and read xml and output the introduction/heading matter
        :param primary_items:  program registry.  See primitem.py for details.
        :return xml tree, xml root, all Tasker Projects/Profiles/Tasks/Scenes,
            output lines, the heading
    """

    primary_items["program_arguments"]["file"] = primary_items["file_to_get"]

    # Only display message box if we don't yet have the file name
    if not primary_items["file_to_get"] and run_counter < 1 and not GUI:
        msg = "Locate the Tasker backup xml file to use to map your Tasker environment"
        messagebox.showinfo("MapTasker", msg)

    # Open and read the file...
    primary_items = open_and_get_backup_xml_file(primary_items)

    # Go get all the xml data
    primary_items = get_the_xml_data(primary_items)

    # Close the file
    primary_items["file_to_get"].close()

    # Output the inital info: head, source, etc.
    display_starting_info(primary_items)

    # If we are debugging, output the runtime arguments and colors
    if (
        primary_items["program_arguments"]["debug"]
        or primary_items["program_arguments"]["runtime"]
    ):
        display_debug_info(primary_items)

    # Start a list (<ul>) to force everything to tab over
    # primary_items["unordered_list_count"] = 0
    primary_items["output_lines"].add_line_to_output(primary_items, 1, "")

    return primary_items


# ##################################################################################
# Display/output the start up information
# ##################################################################################
def display_starting_info(primary_items: dict) -> None:
    """
    Display the heading and source file details
        :param primary_items:  program registry.  See primitem.py for details.
    """
    # Get the screen dimensions from <dmetric> xml
    screen_element = primary_items["xml_root"].find("dmetric")
    screen_size = (
        f'&nbsp;&nbsp;Device screen size: {screen_element.text.replace(",", " X ")}'
        if screen_element is not None
        else ""
    )

    # Set up highlight background color if needed
    if primary_items["program_arguments"]["highlight"]:
        background_color_html = (
            "<style>\nmark { \nbackground-color: "
            + primary_items["colors_to_use"]["highlight_color"]
            + ";\n}\n</style>\n"
        )
    else:
        background_color_html = ""

    # Format the output heading
    heading_color = primary_items["colors_to_use"]["heading_color"]
    primary_items["heading"] = (
        f"<!doctype html>\n<html lang=”en”>\n<head>\n{background_color_html}<title>MapTasker</title>\n<body"
        f" style=\"background-color:{primary_items['colors_to_use']['background_color']}\">\n"
        + format_html(
            primary_items,
            heading_color,
            "",
            (
                "<h2>MapTasker</h2><br> Tasker Mapping................&nbsp;&nbsp;&nbsp;Tasker"
                " version:"
                f" {primary_items['xml_root'].attrib['tv']}&nbsp;&nbsp;&nbsp;&nbsp;Map-Tasker"
                f" version: {MY_VERSION}{screen_size}"
            ),
            True,
        )
    )
    # Start the output with heading
    primary_items["output_lines"].add_line_to_output(
        primary_items, 0, primary_items["heading"]
    )

    # Display where the source file came from
    # Did we restore the backup from Android?
    if primary_items["program_arguments"]["fetched_backup_from_android"]:
        source_file = (
            "From Android device"
            f' {primary_items["program_arguments"]["backup_file_http"]} at'
            f' {primary_items["program_arguments"]["backup_file_location"]}'
        )
    elif (
        primary_items["program_arguments"]["debug"]
        or not primary_items["program_arguments"]["file"]
    ):
        source_file = primary_items["file_to_get"].name
    else:
        source_file = primary_items["program_arguments"]["file"]
    # Add source to output
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        0,
        format_html(
            primary_items,
            heading_color,
            "",
            f"<br><br>Source backup file: {source_file}",
            True,
        ),
    )


# ##################################################################################
# Perform maptasker program initialization functions
# ##################################################################################
def start_up(primary_items: dict) -> dict:
    """
    Perform maptasker program initialization functions
        :param primary_items:  program registry.  See primitem.py for details.
        :return: primary_items...See primitem.py for details
    """

    # Get any arguments passed to program
    logger.info(f"sys.argv{str(sys.argv)}")

    # Rename/convert any old argument file to new name/format for clarity
    # (one time only operation)
    primary_items = old_to_new.migrate(primary_items)

    # Get runtime arguments (from CLI or GUI)
    primary_items = get_arguments.get_program_arguments(primary_items)

    # Get our list of fonts
    _ = get_fonts(primary_items, True)

    # Get our map of colors
    primary_items["colors_to_use"] = setup_colors(primary_items)

    # get_data_and_output_intro program key elements
    primary_items = get_data_and_output_intro(primary_items)

    # If debug mode, log the arguments
    if primary_items["program_arguments"]["debug"]:
        log_startup_values(primary_items)

    # Force full detail if we are doing a single Task
    if primary_items["program_arguments"]["single_task_name"]:
        logger.debug(
            "Single Task=" + primary_items["program_arguments"]["single_task_name"]
        )
        primary_items["program_arguments"]["display_detail_level"] = 3

    logger.info("exit")
    return primary_items
