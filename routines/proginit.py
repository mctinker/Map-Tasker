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

import sys
import datetime
from pathlib import Path

# importing tkinter and tkinter.ttk and all their functions and classes
from tkinter import *

# importing askopenfile (from class filedialog) and messagebox functions
# from class filedialog
from tkinter.filedialog import askopenfile

from config import *  # Configuration info
from routines import progargs as get_args
from routines.sysconst import *


# #######################################################################################
# Open and read the Tasker backup XML file
# Return the file name for use for
# #######################################################################################
def open_and_get_backup_xml_file(program_args: dict) -> object:
    logger.info("entry")
    file_error = False
    # Initialize tkinter
    tkroot = Tk()
    tkroot.geometry("200x100")
    tkroot.title("Select Tasker backup xml file")

    # dir_path = path.dirname(path.realpath(__file__))  # Get current directory
    dir_path = Path.cwd()
    logger.info(f"dir_path: {dir_path}")
    if program_args["debug"]:
        try:
            filename = open(f"{dir_path}/backup.xml", "r")
        except Exception:
            error_msg = f"Error: The backup.xml file was not found in {dir_path}.  Program terminated!"
            logger.debug(error_msg)
            print(error_msg)
            exit(3)
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
    logger.info("exit")
    return filename


# #############################################################################################
# Build color dictionary
# #############################################################################################
def setup_colors() -> dict:
    return {
        "project_color": project_color,
        "profile_color": profile_color,
        "task_color": task_color,
        "scene_color": scene_color,
        "action_color": action_color,
        "disabled_profile_color": disabled_profile_color,
        "unknown_task_color": unknown_task_color,
        "disabled_action_color": disabled_action_color,
        "action_condition_color": action_condition_color,
        "action_label_color": action_label_color,
        "action_name_color": action_name_color,
        "profile_condition_color": profile_condition_color,
        "launcher_task_color": launcher_task_color,
        "background_color": background_color,
        "bullet_color": bullet_color,
        "taskernet_color": taskernet_color,
    }


# #############################################################################################
# Setup logging if in debug mode
# #############################################################################################
def setup_logging():
    logging.basicConfig(
        filename="./maptasker.log",
        filemode="a",
        format="%(asctime)s,%(msecs)d %(levelname)s %(name)s %(funcName)s %(message)s",
        datefmt="%H:%M:%S",
        level=logging.DEBUG,
    )
    logger.info(sys.version_info)


##############################################################################################
# Log the arguments
# #############################################################################################
def log_startup_values(program_args: dict, colormap: dict) -> None:
    setup_logging()  # Get logging going
    logger.info(f"{MY_VERSION} {str(datetime.datetime.now())}")
    logger.info(f"display_detail_level: {program_args['display_detail_level']}")
    logger.info(f"display_taskernet: {program_args['display_taskernet']}")
    logger.info(f"single_project_name: {program_args['single_project_name']}")
    logger.info(f"single_profile_name: {program_args['single_profile_name']}")
    logger.info(f"single_task_name: {program_args['single_task_name']}")
    logger.info(
        f"display_profile_conditions: {program_args['display_profile_conditions']}"
    )
    logger.info(f"debug: {program_args['debug']}")
    for key, value in colormap.items():
        logger.info(f"colormap for {key} set to {value}")


##############################################################################################
# Perform main program initialization functions
# #############################################################################################
def start_up() -> tuple:
    colormap = setup_colors()  # Get our map of colors

    # Get any arguments passed to program
    logger.info(f"sys.argv{str(sys.argv)}")
    program_args, colormap = get_args.get_program_arguments(colormap)
    # If debug mode, log the arguments
    if program_args["debug"]:
        log_startup_values(program_args, colormap)
    heading = (
        '<html>\n<head>\n<title>MapTasker</title>\n<body style="background-color:'
        + colormap["background_color"]
        + '">'
        + FONT_TO_USE
        + "Tasker Mapping................"
    )

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
    return colormap, program_args, found_items, heading
