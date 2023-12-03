#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# parsearg: MapTasker GUI                                                              #
#                                                                                      #
# Add the following statement (without quotes) to your Terminal Shell config file      #
#  (BASH, Fish, etc.) to eliminate the runtime msg:                                    #
#  DEPRECATION WARNING: The system version of Tk is deprecated ...                     #
#  "export TK_SILENCE_DEPRECATION = 1"                                                 #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# To add an argument, see Program_Guide as reference to necessary changes.             #
#                                                                                      #
# #################################################################################### #

import argparse
import textwrap
from argparse import ArgumentParser
from tkinter import Tk, font

from maptasker.src.config import GUI
from maptasker.src.sysconst import TYPES_OF_COLORS, logger


# ################################################################################
# Validate amount of indentation -i argument
# ################################################################################
def indentation_validation(x):
    x = int(x)
    if x > 10:
        raise argparse.ArgumentTypeError(f"Maximum indentation is 10.  You specified {x}.")
    return x


################################################################################
# Validate font entered
################################################################################
def font_validation(x):
    valid_fonts = ["Courier"]
    _ = Tk()
    # Get all monospace ("f"=fixed) fonts
    fonts = [font.Font(family=f) for f in font.families()]
    valid_fonts.extend(f.actual("family") for f in fonts if f.metrics("fixed"))
    if x != "help" and x not in valid_fonts:
        raise argparse.ArgumentTypeError(f"Invalid or non-monospace font name '{x}'.")
    return x


# ##################################################################################
# Get the program arguments using via a GUI (Gooey)
# ##################################################################################
def runtime_parser():
    if GUI:
        return None
    # Setup for argument parsing
    # parser = argparse.ArgumentParser(
    parser = ArgumentParser(
        prog="MapTasker",
        description=(
            "This program reads a Tasker backup file (e.g. backup.xml) and displays the"
            " configuration of Profiles/Tasks/Scenes"
        ),
        epilog=textwrap.dedent(
            """\
                                Exit codes...
                                    exit 1- program error
                                    exit 2- output file failure
                                    exit 3- file selected is not a valid Tasker backup file
                                    exit 5- requested single Task not found
                                    exit 6- no or improper filename selected
                                    exit 7- invalid option
                                    exit 8- request to Android device running server failed.  See output for error code.

                                The output HTML file is saved in your current folder/directory
                                .
                                """
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    # Display Project/Profile/Task/Scene names in bold
    parser.add_argument(
        "-a",
        "-appearance",
        choices=["system", "light", "dark"],
        help=textwrap.dedent(
            """ \
                        Display appearance mode: system (default), light, dark
                            Example: appearance dark
                            """
        ),
        nargs=1,
        required=False,
        default="system",
    )
    # Get Backup (get backup xml) preferences
    parser.add_argument(
        "-b",
        "-backups",
        metavar="http+location",
        nargs=1,
        required=False,
        default="",
        type=str,
        help=textwrap.dedent(
            """ \
                        Get backup file directly from Android device running Tasker:
                            Tasker's HTTP Server Example must be installed on the Android device for this to work:
                            Specify the Tasker server port number and the location of the file. Enter both or none.
                            Default: -backup http://192.168.0.210:1821+/Tasker/configs/user/backup.xml
                            """
        ),
    )
    # Display Profile/Task conditions
    parser.add_argument(
        "-conditions",
        help="Display the condition(s) for Profiles and Tasks",
        action="store_true",
        default=False,
    )
    # Debug
    parser.add_argument(
        "-debug",
        help="Print and log debug information",
        action="store_true",
        default=False,
    )
    # Level of detail to display
    parser.add_argument(
        "-detail",
        help=textwrap.dedent(
            """ \
                        Level of detail to display:
                            0 = display simple Project/Profile/Task/Scene names only with no details
                            1 = display all Task action details for unknown Tasks only
                            2 = display full Task action name on every Task
                            3 = display full Task action details on every Task with action details (default)
                            4 = detail level 3 plus global variables
                            Example: '-detail 2' for Task action names only
                            """
        ),
        choices=[0, 1, 2, 3, 4],
        required=False,
        type=int,
        nargs=1,
        default=3,
    )
    # Display directory
    parser.add_argument(
        "-directory",
        help="Display a directory of hotlinks for all Projects/Profiles/Tasks/Scenes.",
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
                        TaskerNet information, directory, etc..
                            """
        ),
        action="store_true",
        default=False,
    )
    # Font to use in output
    parser.add_argument(
        "-f",
        "-font",
        help=textwrap.dedent(
            """ \
                        Name of monospaced font to use in output (default = 'Courier').  
                        Enter font name of 'help' for a list of valid fonts.
                            """
        ),
        required=False,
        type=font_validation,
        nargs=1,
        # default="Courier",
    )
    # Use the GUI
    parser.add_argument(
        "-g",
        "-gui",
        help=textwrap.dedent(
            """ \
                        Prompt for (these) settings via the graphical user interface (GUI):
                            This argument overrides all other arguments.
                            """
        ),
        action="store_true",
        default=False,
    )
    # Indentation amount (number of spaces)
    parser.add_argument(
        "-i",
        "-indent",
        help="Number of spaces to indent Task If/Then/Else Actions (default = 4)",
        required=False,
        type=indentation_validation,
        nargs=1,
        default=4,
    )
    # Display Project/Profile/Task/Scene names in bold
    parser.add_argument(
        "-names",
        choices=["bold", "highlight", "underline", "italicize"],
        help=textwrap.dedent(
            """ \
                        Display all Projects/Profiles/Tasks/Scenes in bold, underlined, italicized and/or highlighted text.
                            Example: names underline italicize
                            """
        ),
        nargs="+",
        required=False,
        default="",
    )
    # Display Configuration Outline
    parser.add_argument(
        "-o",
        "-outline",
        help=textwrap.dedent(
            """ \
                        Display configuration outline of Projects, Profiles, Tasks and Scenes, and
                        display the configuraion Map (MapTasker_map.txt) in the default text editor"
                            """
        ),
        action="store_true",
        default=False,
    )
    # Display Tasker preferences
    parser.add_argument(
        "-preferences",
        help="Display Tasker preferences",
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
        help="Display the details for a specific Project only.",
    )
    group.add_argument(
        "-profile",
        nargs=1,
        required=False,
        type=str,
        help="Display the details for a specific Profile only.",
    )
    # Save and Restore are mutually exclusive
    group1 = parser.add_mutually_exclusive_group()
    # Restore arguments
    group1.add_argument(
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
    # Display runtime arguments/settings
    parser.add_argument(
        "-runtime",
        help="Display all runtime arguments/settings at the top of the output.",
        action="store_true",
        default=False,
    )
    # Save arguments
    group1.add_argument(
        "-s",
        "-save",
        help="Save arguments for reuse",
        action="store_true",
        default=False,
    )
    # Display taskerNet info
    parser.add_argument(
        "-taskernet",
        help="Display any TaskerNet information for Projects/Profiles.",
        action="store_true",
        default=False,
    )

    group.add_argument(
        "-task",
        nargs=1,
        required=False,
        type=str,
        help='Display the details for a single Task only (forces option "-detail 3").',
    )

    # Display Task details under "hide/twisty"
    parser.add_argument(
        "-twisty",
        help=("Hide Task's details under 'twisty' ➤. Click on twisty to display details."),
        action="store_true",
        default=False,
    )

    # Version argument
    parser.add_argument(
        "-v",
        "-version",
        help="Display the program version and license information.",
        action="store_true",
        default=False,
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
        help="Display a list of valid color names.",
        required=False,
        action="store_true",
    )

    # parser.print_help()
    args = parser.parse_args()
    if args is None:
        # No arguments provide
        parser.print_help()
    else:
        output_results(args)
    return args


# ##################################################################################
# Get the program arguments using via a GUI (Gooey)
# ##################################################################################
def output_results(args):
    # Arguments have been provided
    message_out = f"Arguments: {args}"
    logger.info(message_out)
