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
import sys

from maptasker.src.colors import get_and_set_the_color
from maptasker.src.colors import validate_color
from maptasker.src.getputarg import save_restore_args
from maptasker.src.parsearg import runtime_parser
from maptasker.src.rungui import process_gui
from maptasker.src.initparg import initialize_runtime_arguments

from maptasker.src.sysconst import MY_LICENSE
from maptasker.src.sysconst import MY_VERSION
from maptasker.src.sysconst import TYPES_OF_COLORS
from maptasker.src.sysconst import logger
from maptasker.src.error import error_handler


# #######################################################################################
# Get arguments from command line and put them to the proper settings
# #######################################################################################
def process_arguments(args: object, prog_args: dict, colormap: dict) -> tuple:
    # Color help?
    if getattr(args, "ch"):
        validate_color("h")
    # Not GUI.  Get input from command line arguments
    if getattr(args, "e"):
        prog_args["display_detail_level"] = 3
        prog_args["display_profile_conditions"] = True
        prog_args["display_preferences"] = True
        prog_args["display_taskernet"] = True
    else:
        prog_args["display_detail_level"] = getattr(args, "detail")
        prog_args["display_profile_conditions"] = getattr(args, "conditions")
        prog_args["display_preferences"] = getattr(args, "p")
        prog_args["display_taskernet"] = getattr(args, "taskernet")
    the_name = getattr(args, "project")
    if the_name is not None:
        prog_args["single_project_name"] = the_name[0]
    the_name = getattr(args, "profile")
    if the_name is not None:
        prog_args["single_profile_name"] = the_name[0]
    the_name = getattr(args, "task")
    if the_name is not None:
        prog_args["single_task_name"] = the_name[0]
    if getattr(args, "d"):
        prog_args["debug"] = True
    if getattr(args, "v"):
        print(f"{MY_VERSION}, under license {MY_LICENSE}")
        exit(0)

    # Process colors
    for item in TYPES_OF_COLORS:
        the_name = getattr(args, f"c{item}")
        if the_name is not None:
            if type(the_name) is list:
                get_and_set_the_color(f"-c{item}={the_name[0]}", colormap)
            else:
                get_and_set_the_color(f"-c{item}={the_name}", colormap)

    # Save the arguments
    if getattr(args, "s"):
        save_restore_args(True, colormap, prog_args)

    return prog_args, colormap


# #######################################################################################
# Get arguments from saved file and restore them to the proper settings
# #######################################################################################
def restore_arguments(prog_args: dict, colormap: dict) -> tuple:
    temp_args = {}
    temp_args, temp_colormap = save_restore_args(False, colormap, temp_args)
    for key, value in temp_args.items():  # Map the prog_arg keys and values restored
        if key is not None:
            match key:
                case "debug":
                    prog_args["debug"] = value
                case "display_detail_level":
                    prog_args["display_detail_level"] = int(value)
                case "display_profile_conditions":
                    prog_args["display_profile_conditions"] = value
                case "display_preferences":
                    prog_args["display_preferences"] = value
                case "display_taskernet":
                    prog_args["display_taskernet"] = value
                case "single_profile_name":
                    prog_args["single_profile_name"] = value
                case "single_project_name":
                    prog_args["single_project_name"] = value
                case "single_task_name":
                    prog_args["single_task_name"] = value
                case _:
                    error_handler("Invalid argument restored!", 0)

    # Map the colormap keys and values restored
    for key, value in temp_colormap.items():
        if key is not None:
            colormap[key] = value

    return prog_args, colormap


# #######################################################################################
# We're running a unit test- get the unit test arguments
# #######################################################################################
def unit_test() -> object:
    """
    # Get arguments from run_test.py and process them for unit testing
        :return: Namespace with arguments
    """
    single_names = ["project", "profile", "task"]

    class Namespace:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    # Setup default argument Namespace
    args = Namespace(
        detail=1,
        conditions=False,
        e=False,
        g=False,
        p=False,
        taskernet=False,
        project=None,
        profile=None,
        task=None,
        cProject=None,
        cProfile=None,
        cTask=None,
        cAction=None,
        cDisabledProfile=None,
        cUnknownTask=None,
        cDisabledAction=None,
        cActionCondition=None,
        cProfileCondition=None,
        cLauncherTask=None,
        cBackground=None,
        cScene=None,
        cBullet=None,
        cActionLabel=None,
        cActionName=None,
        cTaskerNetInfo=None,
        cPreferences=None,
        cTrailingComments=None,
        ch=False,
        d=True,
        s=False,
        r=False,
        v=False,
    )
    # Go through each argument from runtest
    for the_argument in sys.argv:
        if the_argument == "-test=yes":  # Remove unit test trigger
            continue
        new_arg = the_argument.split("=")
        # Handle boolean (True) values
        if len(new_arg) == 1:
            new_arg.append("1")
        # Handle display_detail_level, which requires an int
        if new_arg[0] == "detail":
            new_arg[1] = int(new_arg[1])
        # replace the default Namespace value with unit test value
        if new_arg[0] in single_names:
            setattr(args, new_arg[0], [new_arg[1]])
        else:
            setattr(args, new_arg[0], new_arg[1])

    return args


# #######################################################################################
# Get the program arguments (e.g. python mapit.py -x)
# #######################################################################################
# Command line parameters
def process_cli(colormap: dict) -> tuple:
    # Convert runtime argument default values to a dictionary
    prog_args = initialize_runtime_arguments()

    # Process unit tests if "-test" in arguments, else get normal runtime arguments
    args = unit_test() if "-test=yes" in sys.argv else runtime_parser()
    logger.debug(f"Program arguments: {args}")

    # Grab the results
    if getattr(args, "g"):  # GUI for input?
        (
            prog_args,
            colormap,
        ) = process_gui(colormap, True)
    # Restore arguments from file?
    elif getattr(args, "r"):
        # Restore all changes that have been saved for progargs
        prog_args, colormap = restore_arguments(prog_args, colormap)

    # Process commands from command line
    else:
        prog_args, colormap = process_arguments(args, prog_args, colormap)

    # Return the results
    return (
        prog_args,
        colormap,
    )
