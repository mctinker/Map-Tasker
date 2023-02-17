#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# parsearg: MapTasker GUI                                                                    #
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

import argparse
import textwrap
from argparse import ArgumentParser

from maptasker.src.config import GUI
from maptasker.src.sysconst import TYPES_OF_COLORS
from maptasker.src.sysconst import logger


# #######################################################################################
# Get the program arguments using via a GUI (Gooey)
# #######################################################################################
def user_interface():
    if GUI:
        return None
    # Setup for argument parsing
    # parser = argparse.ArgumentParser(
    parser = ArgumentParser(
        prog="MapTasker",
        description="This program reads a Tasker backup file (e.g. backup.xml) and displays the configuration of Profiles/Tasks/Scenes",
        epilog=textwrap.dedent(
            """\
                                Exit codes...
                                    exit 1- program error
                                    exit 2- output file failure
                                    exit 3- file selected is not a valid Tasker backup file
                                    exit 5- requested single Task not found
                                    exit 6- no or improper filename selected
                                    exit 7- invalid option

                                The output HTML file is saved in your current folder/directory
                                .
                                """
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    # Level of detail to display
    parser.add_argument(
        "-detail",
        help=textwrap.dedent(
            """ \
                        Level of detail to display:
                            0 = display first Task action only, for unnamed Tasks only (silent)
                            1 = display all Task action details for unknown Tasks only (default)
                            2 = display full Task action name on every Task
                            3 = display full Task action details on every Task with action details
                            Example: '-detail 2' for Task action names only
                            """
        ),
        choices=[0, 1, 2, 3],
        required=False,
        type=int,
        default=1,
    )
    # Display Profile/Task conditions
    parser.add_argument(
        "-conditions",
        help="Display the condition(s) for Profiles and Tasks",
        action="store_true",
        default=False,
    )
    # Display everything
    parser.add_argument(
        "-e",
        "-everything",
        help=textwrap.dedent(
            """ \
                        Display everything: full detail, Profile/Task conditions,
                        and TaskerNet information
                            """
        ),
        action="store_true",
        default=False,
    )
    # Use the GUI
    parser.add_argument(
        "-g",
        "-gui",
        help=textwrap.dedent(
            """ \
                        Prompt for settings via the graphical user interface (GUI):
                            This argument overrides all other arguments
                            """
        ),
        action="store_true",
        default=False,
    )
    # Display taskerNet info
    parser.add_argument(
        "-taskernet",
        help="Display any TaskerNet information for Projects/Profiles",
        action="store_true",
        default=False,
    )
    # Group project, profile and task = name ... together as exclusive arguments
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-project",
        nargs=1,
        required=False,
        type=str,
        help="Display the details for a specific Project only",
    )
    group.add_argument(
        "-profile",
        nargs=1,
        required=False,
        type=str,
        help="Display the details for a specific Profile only",
    )
    group.add_argument(
        "-task",
        nargs=1,
        required=False,
        type=str,
        help='Display the details for a single Task only (forces option "-d 2")',
    )

    # define a color group for the various color settings
    color_group = parser.add_argument_group("Output Color Options")
    # For each type of color option, create the appropriate argument
    for key, value in TYPES_OF_COLORS.items():
        color_group.add_argument(
            f"-c{key}",
            help=f"Provide a valid color for {value}.  Example: -c{key} Blue",
            required=False,
            type=str,
            nargs=1,
        )
    # Color help
    color_group.add_argument(
        "-ch",
        "-colorhelp",
        help="Display a list of valid color names",
        required=False,
        action="store_true",
    )
    # Debug
    parser.add_argument(
        "-d",
        "-debug",
        help="Print and log debug information",
        action="store_true",
        default=False,
    )
    # Save and Restore are mutually exclusive
    group1 = parser.add_mutually_exclusive_group()
    # Save arguments
    group1.add_argument(
        "-s",
        "-save",
        help="Save arguments for reuse",
        action="store_true",
        default=False,
    )
    # Restore arguments
    group1.add_argument(
        "-r",
        "-restore",
        action="store_true",
        default=False,
        help=textwrap.dedent(
            """ \
                        Restore previously saved arguments for reuse:
                            This argument overrides all other arguments except '-g'
                            """
        ),
    )
    # Save arguments
    parser.add_argument(
        "-v",
        "-version",
        help="Display the program version and license information",
        action="store_true",
        default=False,
    )

    # parser.print_help()
    args = parser.parse_args()
    if args is None:
        # No arguments provide
        parser.print_help()
    else:
        output_results(args)
    return args


# #######################################################################################
# Get the program arguments using via a GUI (Gooey)
# #######################################################################################
def output_results(args):
    # Arguments have been provided
    message_out = f"Arguments: {args}"
    # print(message_out)
    # print(args)
    logger.info(message_out)
