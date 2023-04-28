#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# proginit: perform program initialization functions                                         #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #

import atexit
import datetime
import sys
from json import dumps, loads  # For write and read counter
from pathlib import Path

# importing tkinter and tkinter.ttk and all their functions and classes
from tkinter import Tk
from tkinter import messagebox

# importing askopenfile (from class filedialog) and messagebox functions
# from class filedialog
from tkinter.filedialog import askopenfile
from typing import Any

import maptasker.src.migrate as old_to_new
import maptasker.src.outputl as build_output
import maptasker.src.progargs as get_args
from maptasker.src.frmthtml import format_html
from maptasker.src.colrmode import set_color_mode
from maptasker.src.config import DARK_MODE
from maptasker.src.config import GUI
from maptasker.src.debug import debug1
from maptasker.src.sysconst import COUNTER_FILE
from maptasker.src.sysconst import MY_VERSION
from maptasker.src.sysconst import logger
from maptasker.src.sysconst import logging
from maptasker.src.taskerd import get_the_xml_data
from maptasker.src.error import error_handler


# #############################################################################################
# Use a counter to determine if this is the first time run.
#  If first time only, then provide a user prompt to locate the backup file
# #############################################################################################
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


# #######################################################################################
# Open and read the Tasker backup XML file
# Return the file name for use for
# #######################################################################################
def open_and_get_backup_xml_file(program_args: dict) -> object:
    """
    Open the Tasker backup file and return the file object
        :param program_args: runtime arguments
        :return: Tasker backup file object
    """
    logger.info("entry")
    file_error = False
    # Initialize tkinter
    tkroot = Tk()
    tkroot.geometry("200x100")
    tkroot.title("Select Tasker backup xml file")
    filename = None

    # dir_path = path.dirname(path.realpath(__file__))  # Get current directory
    dir_path = Path.cwd()
    logger.info(f"dir_path: {dir_path}")
    if program_args["debug"]:
        try:
            filename = open(f"{dir_path}/backup.xml", "r")
        except OSError:
            error_handler(
                (
                    f"Error: The backup.xml file was not found in {dir_path}.  Program"
                    " terminated!"
                ),
                3,
            )

    elif program_args["file"]:
        # We already have the file name...open it.
        filename = open(program_args["file"], "r")

    else:
        try:
            filename = askopenfile(
                parent=tkroot,
                mode="r",
                title="Select Tasker backup xml file",
                initialdir=dir_path,
                filetypes=[("XML Files", "*.xml")],
            )
        except Exception:
            file_error = True
        if filename is None:
            file_error = True
        if file_error:
            cancel_message = "Backup file selection cancelled.  Program ended."
            print(cancel_message)
            logger.debug(cancel_message)
            sys.exit(6)
    tkroot.destroy()
    del tkroot

    return filename


# #############################################################################################
# Build color dictionary
# #############################################################################################
def setup_colors() -> dict:
    """
    Set up the initial colors to use.
        :return: color map dictionary
    """
    colormap = {}

    appearance = 'Dark' if DARK_MODE else "Light"
    return set_color_mode(appearance, colormap)


# #############################################################################################
# Setup logging
# #############################################################################################
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


##############################################################################################
# Log the arguments
# ############################################################################################
def log_startup_values(program_args: dict, colormap: dict) -> None:
    """
    Log the runtime arguments
        :param program_args: runtrime arguments
        :param colormap: colors to use in the output
    """
    setup_logging()  # Get logging going
    logger.info(f"{MY_VERSION} {str(datetime.datetime.now())}")
    logger.info(f"sys.argv:{str(sys.argv)}")
    for key, value in program_args.items():
        logger.info(f"{key}: {value}")
    for key, value in colormap.items():
        logger.info(f"colormap for {key} set to {value}")


##############################################################################################
# Program setup: initialize key elements
# ############################################################################################
def setup(
    colormap: dict, program_args: dict, output_list: list, file_to_get: str
) -> tuple[Any, Any, object, Any, list, str]:
    """
    Perform basic setup
        :param colormap: colors to use for output
        :param program_args: runtime arguments
        :param output_list: lines of output generated thus far
        :param file_to_get: file object (if file already defined, don't prompt user), or None
        :return xml tree, xml root, all Tasker Projects/Profiles/Tasks/Scenes, output lines, the heading
    """

    program_args["file"] = file_to_get

    # Only display message box if we don't yet have the file name
    if not file_to_get and run_counter < 1 and not GUI:
        msg = "Locate the Tasker backup xml file to use to map your Tasker environment"
        messagebox.showinfo("MapTasker", msg)

    # Open and read the file...
    filename = open_and_get_backup_xml_file(program_args)

    # Go get all the xml data
    tree, root, all_tasker_items = get_the_xml_data(filename)

    # Check for valid Tasker backup.xml file
    if root.tag != "TaskerData":
        error_msg = "You did not select a Tasker backup XML file...exit 2"
        build_output.my_output(colormap, program_args, output_list, 0, error_msg)
        logger.debug(f"{error_msg}exit 3")
        sys.exit(3)
    else:
        # Format the output heading
        heading = (
            "<html>\n<head>\n<title>MapTasker</title>\n<body"
            f" style=\"background-color:{colormap['background_color']}\">\n"
            + format_html(
                colormap,
                "LawnGreen",
                "",
                (
                    "<b>Tasker Mapping................&nbsp;&nbsp;&nbsp;Tasker version:"
                    f" {root.attrib['tv']}&nbsp;&nbsp;&nbsp;&nbsp;Map-Tasker version:"
                    f" {MY_VERSION}</b>"
                ),
                True,
            )
        )
        # Start the output with heading
        build_output.my_output(colormap, program_args, output_list, 0, heading)

    # If we are debugging, output the runtime arguments and colors
    if program_args["debug"]:
        debug1(colormap, program_args, output_list)

    # Start a list (<ul>)
    build_output.my_output(colormap, program_args, output_list, 1, "")

    return tree, root, filename, all_tasker_items, output_list, heading


##############################################################################################
# Perform maptasker program initialization functions
# #############################################################################################
def start_up(output_list: list, file_to_get: str) -> tuple:
    """
    Perform maptasker program initialization functions
        :param output_list: list of output lines to add to.
        :param file_to_get: file name (fully qualified) if previously defined
        :return: see "return" statement
    """
    colormap = setup_colors()  # Get our map of colors

    # Get any arguments passed to program
    logger.info(f"sys.argv{str(sys.argv)}")

    # Rename/convert any old argument file to new name/format for clarity (one time only operation)
    old_to_new.migrate()

    # Get runtime arguments
    program_args, colormap = get_args.get_program_arguments(colormap)

    # Setup program key elements
    tree, root, filename, all_tasker_items, output_list, heading = setup(
        colormap, program_args, output_list, file_to_get
    )

    # If debug mode, log the arguments
    if program_args["debug"]:
        log_startup_values(program_args, colormap)

    # Force full detail if we are doing a single Task
    if program_args["single_task_name"]:
        logger.debug("Single Task=" + program_args["single_task_name"])
        program_args["display_detail_level"] = 3

    # Setup default for found Project / Profile / Task
    found_items = {
        "single_project_found": False,
        "single_profile_found": False,
        "single_task_found": False,
    }
    logger.info("exit")
    return (
        colormap,
        program_args,
        found_items,
        heading,
        output_list,
        tree,
        root,
        filename,
        all_tasker_items,
    )
