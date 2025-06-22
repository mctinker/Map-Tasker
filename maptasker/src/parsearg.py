"""MapTasker runtime argument parser"""

#! /usr/bin/env python3

#                                                                                      #
# parsearg: MapTasker runtime argument parser                                          #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #

import argparse
import textwrap
from argparse import ArgumentParser
from tkinter import font

from maptasker.src.error import error_handler
from maptasker.src.maputils import validate_ip_address, validate_port
from maptasker.src.nameattr import get_tk
from maptasker.src.sysconst import LLAMA_MODELS, OPENAI_MODELS, TYPES_OF_COLORS, logger


# Validate mutually inclusive variables
def validate_vars(var1: str, var2: int, var3: str) -> None:
    """Validate mutually inclusive arguments
    Args:
        var1: First argument to validate
        var2: Second argument to validate
        var3: Third argument to validate
    Returns:
        None: No value is returned
    Processing Logic:
        - Check if only var1 is True and var2 and var3 are False
        - Check if only var2 is True and var1 and var3 are False
        - Check if only var3 is True and var1 and var2 are False
        - If any of the above conditions are True, raise an error"""
    if (var1 and not var2 and not var3) or (not var1 and var2 and not var3) or (not var1 and not var2 and var3):
        msg = "The -android_ipaddr, -android_port and -xandroid_file options are mutually inclusive.  If one is specified, they each must have a value."
        error_handler(msg, 7)
        # raise argparse.ArgumentTypeError(msg)
        # raise MutuallyInclusiveArgumentError(
        #     "The -android_ipaddr, -android_port and -xandroid_file options are mutually inclusive.  If one is specified, they each must have a value."
        # )


# ################################################################################
# TCP IP Address validation
# ################################################################################
def ipaddr_validation(ip_address: str) -> str:
    """Validate IP address string
    Args:
        ip_address: IP address string to validate
    Returns:
        ip_address: Validated IP address string
    Validate IP address:
    - Check if IP address is valid using validate_ip_address function
    - If invalid, raise ArgumentTypeError with error message
    - If valid, simply return IP address string"""
    if ip_address != "" and not validate_ip_address(ip_address):
        msg = f"Invalid TCP IP address.  You specified {ip_address}."
        error_handler(msg, 7)
        # raise argparse.ArgumentTypeError(msg) from ValueError

    return ip_address


# ################################################################################
# TCP IP Address validation
# ################################################################################
def port_validation(port_number: str) -> str:
    """Validate IP address string
    Args:
        ip_address: IP address string to validate
    Returns:
        ip_address: Validated IP address string
    Validate IP address:
    - Check if IP address is valid using validate_ip_address function
    - If invalid, raise ArgumentTypeError with error message
    - If valid, simply return IP address string"""
    if port_number != "" and validate_port("", port_number) != 0:
        msg = f"Invalid port number.  You specified {port_number}."
        error_handler(msg, 7)
        # raise argparse.ArgumentTypeError(msg) from ValueError

    return port_number


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
        error_handler(msg, 7)
        # raise argparse.ArgumentTypeError(msg)
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
        error_handler(msg, 7)
        # raise argparse.ArgumentTypeError(msg)
    elif x == "help":
        print("Valid monospace fonts: ", ", ".join(valid_fonts))
    return x


################################################################################
# Validate file location entered
################################################################################
def file_validation(file: str) -> str:
    """
    Validate file extension for android backup file
    Args:
        file: File path to validate
    Returns:
        file: Validated file path
    - Check if file extension contains ".xml"
    - If not, raise error with message specifying missing ".xml" extension
    - Otherwise, return original file path
    """
    if file != "" and "xml" not in file:
        msg = f"Invalid android file location '{file}'.  Missing the backup '.xml' extension."
        error_handler(msg, 7)
        # raise argparse.ArgumentTypeError(msg)
    return file


##################################################################################
# Get the program arguments using via a GUI (Gooey)
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

    # Ai arguments
    models = OPENAI_MODELS + LLAMA_MODELS
    parser.add_argument(
        "-ai_model",
        help="The model to use for Profiles and Tasks Ai analysis.",
        choices=models,
        required=False,
        nargs=1,
    )

    # Android mutually inclusive group
    android_group = parser.add_argument_group("mutually inclusive")
    # Android device TCP IP Address
    android_group.add_argument(
        "-android_ipaddr",
        help=textwrap.dedent(
            """ \
                        TCP/IP Address of Android device running Tasker server
                            Example: -android_ipaddr 192.168.0.210
                            Also requires -android_port and -android_file arguments
                            """,
        ),
        type=ipaddr_validation,
        nargs=1,
        required=False,
        default="",
    )
    # Android Port Number
    android_group.add_argument(
        "-android_port",
        type=port_validation,
        help=textwrap.dedent(
            """ \
                        Port number of Android device running Tasker server
                            Example: -android_port 1821
                        Also requires -android_ipaddr and -android_file arguments
                            """,
        ),
        nargs=1,
        required=False,
        default="",
    )
    # Android device file location
    android_group.add_argument(
        "-android_file",
        type=file_validation,
        help=textwrap.dedent(
            """ \
                        File location of Tasker backup file on Android device
                            Example: -a-android_file /Tasker/configs/user/backup.xml
                        Also requires -android_ipaddr and -android_port arguments
                            """,
        ),
        nargs=1,
        required=False,
        default="",
    )

    # Display Background Appearnace: system, light or dark.
    parser.add_argument(
        "-appearance",
        choices=["system", "light", "dark"],
        help=textwrap.dedent(
            """ \
                        Display appearance mode: system (default), light, dark
                            Example: -appearance dark
                            """,
        ),
        nargs=1,
        required=False,
        default="system",
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
                            5 = detail level 4 plus Scene element UI details.
                            Example: '-detail 2' for Task action names only
                            """,
        ),
        choices=[0, 1, 2, 3, 4, 5],
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
    # Group everrything and twisty
    everything_group = parser.add_mutually_exclusive_group()
    # Display everything
    everything_group.add_argument(
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
    # File to use for the input (e.g. ~/Downloads/backup.xml)
    parser.add_argument(
        "-file",
        help=textwrap.dedent(
            """ \
                        Directory and file name of Tasker XML file to analyze.
                        Example: -file ~/Downloads/backup.xml
                            """,
        ),
        required=False,
        nargs=1,
    )
    # Font to use in output
    parser.add_argument(
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
    # Gui Map View feature
    parser.add_argument(
        "-guiview",
        help=argparse.SUPPRESS,  # Don't display this in the help
        action="store_true",
        default=False,
    )
    # view_limit
    parser.add_argument(
        "-view_limit",
        help=argparse.SUPPRESS,  # Don't display this in the help
        action="store_true",
        default=5000,
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

    # Make the output pretty
    parser.add_argument(
        "-pretty",
        help="Make output prettier (one argument/parameter per line)",
        action="store_true",
        default=False,
    )

    # Group project, profile and task = name ... together as exclusive arguments
    single_group = parser.add_mutually_exclusive_group()
    single_group.add_argument(
        "-project",
        nargs=1,
        required=False,
        type=str,
        help="Display the details for a specific Project only.",
    )
    single_group.add_argument(
        "-profile",
        nargs=1,
        required=False,
        type=str,
        help="Display the details for a specific Profile only.",
    )
    single_group.add_argument(
        "-task",
        nargs=1,
        required=False,
        type=str,
        help='Display the details for a single Task only (forces minimum of "-detail 3").',
    )

    # Reset arguments
    parser.add_argument(
        "-reset",
        action="store_true",
        default=False,
        help="Reset previously saved arguments...start fresh.",
    )
    # Rerun indicator (hidden)
    # parser.add_argument("-rerun", default=False, action="store_true", help=argparse.SUPPRESS)
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
    # Display Task details under "hide/twisty"
    everything_group.add_argument(
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

    # Make certain that if android args entered, they are inclusive.
    elif args.android_ipaddr or args.android_port or args.android_file:
        validate_vars(
            args.android_ipaddr[0],
            args.android_port[0],
            args.android_file[0],
        )
        output_results(args)
    return args


# Get the program arguments using via a GUI (Gooey)
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
