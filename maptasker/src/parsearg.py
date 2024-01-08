"""MapTasker runtime argument parser"""
#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# parsearg: MapTasker runtime argument parser                                          #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #

import argparse
import textwrap
from argparse import ArgumentParser
from tkinter import font

from maptasker.src.nameattr import get_tk
from maptasker.src.sysconst import TYPES_OF_COLORS, logger


# ################################################################################
# Validate amount of indentation -i argument
# ################################################################################
def indentation_validation(x: int) -> int:
    """
    Validate indentation level
    Args:
        x: Indentation level to validate
    Returns:
        x: Validated indentation level
    - Convert input to integer
    - Check if indentation level is greater than 10
    - Raise error if indentation is greater than 10
    - Return indentation level if valid"""
    x = int(x)
    if x > 10:
        msg = f"Maximum indentation is 10.  You specified {x}."
        raise argparse.ArgumentTypeError(msg)
    return x


################################################################################
# Validate font entered
################################################################################
def font_validation(x: str) -> str:
    """
    Validate font name and return valid font
    Args:
        x: Font name to validate
    Returns:
        x: Validated font name
    - Check if input font name is 'help'
    - Check if input font name is in list of valid monospace fonts
    - If not valid, raise error
    - Otherwise return input font name"""
    valid_fonts = ["Courier"]
    # Get our Tkinter window
    get_tk()
    # Get all monospace ("f"=fixed) fonts
    fonts = [font.Font(family=f) for f in font.families()]
    valid_fonts.extend(f.actual("family") for f in fonts if f.metrics("fixed"))
    if x != "help" and x not in valid_fonts:
        msg = f"Invalid or non-monospace font name '{x}'."
        raise argparse.ArgumentTypeError(msg)
    return x


# ##################################################################################
# Get the program arguments using via a GUI (Gooey)
# ##################################################################################
def runtime_parser() -> None:
    """
    Get the program arguments using via a GUI (Gooey)
    Args:
        function: {Function description in one line}
    Returns:
        None: {Return description in one line}
    {Processing Logic}:
        - Setup argument parser
        - Add arguments for runtime settings
        - Parse arguments and call output function
    """
    # Setup for argument parsing
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
                                """,
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
                            """,
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
                            """,
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
                            """,
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
                            """,
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
                            """,
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
                            """,
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
                            """,
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
                            """,
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
    # Reset arguments
    parser.add_argument(
        "-reset",
        action="store_true",
        default=False,
        help="Reset previously saved arguments...start fresh.",
    )
    # Display runtime arguments/settings
    parser.add_argument(
        "-runtime",
        help="Display all runtime arguments/settings at the top of the output.",
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
def output_results(args: object) -> None:
    # Arguments have been provided
    """Outputs logging information about function arguments
    Args:
        args: The arguments passed to the function
    Returns:
        None: This function does not return anything
    - Format the arguments into a message string
    - Call the logger to output an info log message with the arguments"""
    message_out = f"Arguments: {args}"
    logger.info(message_out)
