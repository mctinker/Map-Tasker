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
def process_arguments(primary_items: dict, args: object) -> dict:

    # Color help?
    if getattr(args, "ch"):
        validate_color("h")
    # Not GUI.  Get input from command line arguments
    if getattr(args, "e"):  # Everything?
        primary_items["program_arguments"]["display_detail_level"] = 3
        primary_items["program_arguments"]["display_profile_conditions"] = \
        primary_items["program_arguments"]["display_preferences"] = \
            primary_items["program_arguments"]["directory"] = \
        primary_items["program_arguments"]["display_taskernet"] = True
    else:
        primary_items["program_arguments"]["display_detail_level"] = getattr(
            args, "detail"  # Display detail level
        )
        primary_items["program_arguments"]["display_profile_conditions"] = getattr(
            args, "conditions"  # Display conditions
        )
        primary_items["program_arguments"]["display_preferences"] = getattr(
            args, "p"
        )  # Display Tasker preferences
        primary_items["program_arguments"]["display_taskernet"] = getattr(
            args, "taskernet"  # Display TaskerNet info
        )
    the_name = getattr(args, "project")  # Display single Project
    if the_name is not None:
        primary_items["program_arguments"]["single_project_name"] = the_name[0]
    the_name = getattr(args, "profile")  # Display single Profile
    if the_name is not None:
        primary_items["program_arguments"]["single_profile_name"] = the_name[0]
    the_name = getattr(args, "task")  # Display single task
    if the_name is not None:
        primary_items["program_arguments"]["single_task_name"] = the_name[0]
    if getattr(args, "d"):  # Debug mode
        primary_items["program_arguments"]["debug"] = True
    if getattr(args, "v"):  # Display version info
        print(f"{MY_VERSION}, under license {MY_LICENSE}")
        exit(0)
    if getattr(args, "twisty"):  # Twisty
        primary_items["program_arguments"]["twisty"] = True
    if getattr(args, "directory"):  # Directory
        primary_items["program_arguments"]["directory"] = True
    if backup_file_info := getattr(
        args, "b"
    ):  # Get backup file directly from Android device
        # It is a list if coming from program arguments.  Otherwise, just a string if coming from run_test (unit test)
        if type(backup_file_info) == list:
            backup_details = backup_file_info[0].split("+")
        else:
            backup_details = backup_file_info.split("+")

        # Break up the command into http portion and file-location portion
        if backup_details[0].isdigit and backup_details[1]:
            primary_items["program_arguments"]["backup_file_http"] = backup_details[0]
            primary_items["program_arguments"]["backup_file_location"] = backup_details[
                1
            ]

    # Process colors
    for item in TYPES_OF_COLORS:
        the_name = getattr(args, f"c{item}")
        if the_name is not None:
            if type(the_name) is list:
                get_and_set_the_color(primary_items, f"-c{item}={the_name[0]}")
            else:
                get_and_set_the_color(primary_items, f"-c{item}={the_name}")

    # Save the arguments
    if getattr(args, "s"):
        primary_items["program_arguments"], primary_items["colors_to_use"] = (
            save_restore_args(
                primary_items["program_arguments"], primary_items["colors_to_use"], True
            )
        )

    return primary_items


# #######################################################################################
# Get arguments from saved file and restore them to the proper settings
# #######################################################################################
def restore_arguments(primary_items: dict) -> dict:
    """
    Get arguments from saved file and restore them to the proper settings
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :return: primary items
    """
    temp_arguments = temp_colors = {}
    temp_arguments, temp_colors = save_restore_args(temp_arguments, temp_colors, False)
    for key, value in temp_arguments[
        "program_arguments"
    ].items():  # Map the prog_arg keys and values restored
        if key is not None:
            match key:
                case "debug":
                    primary_items["program_arguments"]["debug"] = value
                case "display_detail_level":
                    primary_items["program_arguments"]["display_detail_level"] = int(
                        value
                    )
                case "display_profile_conditions":
                    primary_items["program_arguments"][
                        "display_profile_conditions"
                    ] = value
                case "display_preferences":
                    primary_items["program_arguments"]["display_preferences"] = value
                case "display_taskernet":
                    primary_items["program_arguments"]["display_taskernet"] = value
                case "single_profile_name":
                    primary_items["program_arguments"]["single_profile_name"] = value
                case "single_project_name":
                    primary_items["program_arguments"]["single_project_name"] = value
                case "single_task_name":
                    primary_items["program_arguments"]["single_task_name"] = value
                case _:
                    error_handler("Invalid argument restored: {key}!", 0)

    # Map the colormap keys and values restored
    for key, value in temp_colors.items():
        if key is not None:
            primary_items["colors_to_use"][key] = value

    return primary_items


# #######################################################################################
# We're running a unit test. Get the unit test arguments
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
        detail=3,
        conditions=False,
        e=False,
        g=False,
        p=False,
        b=False,
        taskernet=False,
        twisty=False,
        directory=False,
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
def process_cli(primary_items: dict) -> dict:
    # Convert runtime argument default values to a dictionary
    primary_items["program_arguments"] = initialize_runtime_arguments()

    # Process unit tests if "-test" in arguments, else get normal runtime arguments
    args = unit_test() if "-test=yes" in sys.argv else runtime_parser()
    logger.debug(f"Program arguments: {args}")

    # Grab the results
    if getattr(args, "g"):  # GUI for input?
        (
            primary_items["program_arguments"],
            colormap,
        ) = process_gui(primary_items, True)

    # Restore arguments from file?
    elif getattr(args, "r"):
        # Restore all changes that have been saved for progargs
        primary_items = restore_arguments(primary_items)

    # Process commands from command line
    else:
        primary_items = process_arguments(primary_items, args)

    # Return the results
    return primary_items
