#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# runcli: process command line interface arguments for MapTasker                            #
#                                                                                            #
# Add the following statement (without quotes) to your Terminal Shell configuration file     #
#  (BASH, Fish, etc.) to eliminate the runtime msg:                                          #
#  DEPRECATION WARNING: The system version of Tk is deprecated ...                           #
#  "export TK_SILENCE_DEPRECATION = 1"                                                       #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #

from maptasker.src.colors import get_and_set_the_color
from maptasker.src.colors import validate_color
from maptasker.src.getputarg import save_restore_args
from maptasker.src.parsearg import user_interface
from maptasker.src.rungui import process_gui
from maptasker.src.sysconst import MY_LICENSE
from maptasker.src.sysconst import MY_VERSION
from maptasker.src.sysconst import TYPES_OF_COLORS
from maptasker.src.sysconst import logger


# #######################################################################################
# Get arguments from command line and put them to the proper settings
# #######################################################################################
def process_arguments(args: object,
                      display_detail_level: int,
                      display_profile_conditions: bool,
                      display_taskernet: bool,
                      single_project_name: str,
                      single_profile_name: str,
                      single_task_name: str,
                      debug: bool, colormap: dict) -> tuple:
    if getattr(args, "ch"):
        validate_color("h")
    # Not GUI.  Get input from command line arguments
    if getattr(args, "e"):
        display_detail_level = 3
        display_profile_conditions = True
        display_taskernet = True
    else:
        display_detail_level = getattr(args, "detail")
        display_profile_conditions = getattr(args, "conditions")
        display_taskernet = getattr(args, "taskernet")
    the_name = getattr(args, "project")
    if the_name is not None:
        single_project_name = the_name[0]
    the_name = getattr(args, "profile")
    if the_name is not None:
        single_profile_name = the_name[0]
    the_name = getattr(args, "task")
    if the_name is not None:
        single_task_name = the_name[0]
    if getattr(args, "d"):
        debug = True
    if getattr(args, "v"):
        print(f"{MY_VERSION}, under license {MY_LICENSE}")
        exit(0)

    # Process colors
    for item in TYPES_OF_COLORS:
        the_name = getattr(args, f"c{item}")
        if the_name is not None:
            get_and_set_the_color(f"-c{item}={the_name[0]}", colormap)

    # Save the arguments
    if getattr(args, "s"):
        temp_args = {
            "display_detail_level": display_detail_level,
            "single_task_name": single_task_name,
            "single_profile_name": single_profile_name,
            "single_project_name": single_project_name,
            "display_profile_conditions": display_profile_conditions,
            "display_taskernet": display_taskernet,
            "debug": debug,
        }
        save_restore_args(True, colormap, temp_args)

    return display_detail_level, \
        display_profile_conditions, \
        display_taskernet, \
        single_project_name, \
        single_profile_name, \
        single_task_name, \
        debug, colormap


# #######################################################################################
# Get arguments from saved file and restore them to the proper settings
# #######################################################################################
def restore_arguments(display_detail_level: int,
                      display_profile_conditions: bool,
                      display_taskernet: bool,
                      single_project_name: str,
                      single_profile_name: str,
                      single_task_name: str,
                      debug: bool, colormap: dict) -> tuple:
    temp_args = {}
    temp_args, temp_colormap = save_restore_args(False, colormap, temp_args)
    for key, value in temp_args.items():  # Map the progarg keys and values restored
        if key is not None:
            if key == "debug":
                debug = value
            elif key == "display_detail_level":
                display_detail_level = int(value)
            elif key == "display_profile_conditions":
                display_profile_conditions = value
            elif key == "display_taskernet":
                display_taskernet = value
            elif key == "single_profile_name":
                single_profile_name = value
            elif key == "single_project_name":
                single_project_name = value
            elif key == "single_task_name":
                single_task_name = value
    # Map the colormap keys and values restored
    for key, value in temp_colormap.items():
        if key is not None:
            colormap[key] = value

    return display_detail_level, \
            display_profile_conditions, \
            display_taskernet, \
            single_project_name, \
            single_profile_name, \
            single_task_name, \
            debug, colormap


# #######################################################################################
# Get the program arguments (e.g. python mapit.py -x)
# #######################################################################################
# Command line parameters
def process_cli(colormap: dict) -> tuple:
    display_detail_level, single_task_name, single_profile_name, single_project_name = (
        1,
        "",
        "",
        "",
    )
    display_profile_conditions, display_taskernet, debug = False, False, False

    # Get the arguments entered by user
    args = user_interface()
    logger.debug(f"Program arguments: {args}")

    # Grab the results
    if getattr(args, "g"):  # GUI for input?
        (
            display_detail_level,
            display_profile_conditions,
            display_taskernet,
            single_project_name,
            single_profile_name,
            single_task_name,
            debug,
            colormap,
        ) = process_gui(colormap, True)
    # Restore arguments from file?
    elif getattr(args, "r"):
        # Restore all changes that have been saved for progargs
        display_detail_level, display_profile_conditions, display_taskernet, single_project_name, \
            single_profile_name, single_task_name, debug, colormap = \
            restore_arguments(display_detail_level,
                              display_profile_conditions,
                              display_taskernet,
                              single_project_name,
                              single_profile_name,
                              single_task_name,
                              debug, colormap)

    # Process commands from command line
    else:
        display_detail_level, display_profile_conditions, display_taskernet, single_project_name, \
            single_profile_name, single_task_name, debug, colormap = \
            process_arguments(args, display_detail_level,
                              display_profile_conditions,
                              display_taskernet,
                              single_project_name,
                              single_profile_name,
                              single_task_name,
                              debug, colormap)

    # Return the results
    return (
        display_detail_level,
        display_profile_conditions,
        display_taskernet,
        single_project_name,
        single_profile_name,
        single_task_name,
        debug,
        colormap,
    )
