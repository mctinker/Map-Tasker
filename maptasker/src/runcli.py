"""Process command line interface arguments for MapTasker"""

#! /usr/bin/env python3

#                                                                                      #
# runcli: process command line interface arguments for MapTasker                       #
#                                                                                      #
# Add the following statement (without quotes) to your Terminal Shell config file.     #
#  (BASH, Fish, etc.) to eliminate the runtime msg:                                    #
#  DEPRECATION WARNING: The system version of Tk is deprecated ...                     #
#  "export TK_SILENCE_DEPRECATION = 1"                                                 #
#                                                                                      #
import contextlib
import os
import sys
from collections import namedtuple

import darkdetect

from maptasker.src.clip import clip_figure
from maptasker.src.colors import get_and_set_the_color, validate_color
from maptasker.src.config import DEFAULT_DISPLAY_DETAIL_LEVEL
from maptasker.src.error import error_handler
from maptasker.src.getputer import save_restore_args
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.maputils import exit_program
from maptasker.src.parsearg import runtime_parser
from maptasker.src.primitem import PrimeItems
from maptasker.src.rungui import process_gui
from maptasker.src.sysconst import (
    ARGUMENTS_FILE,
    MY_LICENSE,
    MY_VERSION,
    TYPES_OF_COLORS,
    Colors,
    logger,
)


# ################################################################################
# Determine if the argument is a list or string, and return the value as appropriate
# ################################################################################
def get_arg_if_in_list(args: list, the_argument: str) -> int:
    """
    Determine if the argument is a list or string, and return the value as appropriate
        Args:
            args (Namespace): the args Namespace from either argparse or unit_test
            the_argument (str): the arguemnt to get

        Returns:
            tuple: boolean True if it is a list and the numeric value for the argument that was gotten
    """
    if the_value := getattr(args, the_argument):
        return int(the_value[0]) if isinstance(the_value, list) else int(the_value)

    return the_value


# We have a -name argument.  Get the name's attributes and save them
def get_name_attributes(value: str) -> None:
    """
    We have a -name argument.  Get the name's attributes and save them
        Args:
            value (str): The attributes to assign to names: (bold, highlight, underline, italicize)
    """
    # Get names (bold, highlight, underline and/or highlight)
    # If value is a list, convert it to a string first
    valid_attributes = ["bold", "highlight", "underline", "italicize"]

    name_attributes = " ".join(value) if isinstance(value, list) else value
    name_attributes = name_attributes.split()
    for attribute in name_attributes:
        if attribute in valid_attributes:
            PrimeItems.program_arguments[attribute] = True


# Go through all boolean settings, get each and if have it then set value to True
def get_and_set_booleans(args: list) -> None:
    """
    Go through all boolean settings, get each and if have it then set value to True
        Args:
            args (namedtuple): runtime arguments namespace
    """
    # Program runtime boolean arguments (long form and short form per argparse.py)
    boolean_arguments = {
        "conditions": "",
        "debug": "",
        "directory": "",
        "everything": "e",
        "outline": "o",
        "pretty": "",
        "preferences": "",
        "reset": "",
        "runtime": "",
        "taskernet": "",
        "twisty": "",
        "guiview": "",
    }

    # Loop through all possible boolean program arguments and get/set each
    # Check both the long name (key) and the short name (value)
    # NOTE: We can not use an either/or combination if statement to test both the
    #       key and the value since an exception on the first test will automatically
    #       skip doing the "or" second test.
    for key, value in boolean_arguments.items():
        try:
            if getattr(args, key):
                PrimeItems.program_arguments[key] = True
        except AttributeError:
            with contextlib.suppress(AttributeError):
                if value and getattr(args, value):
                    PrimeItems.program_arguments[key] = True


# Get the the other arguments
def get_the_other_arguments(args: list) -> None:
    """
    Get the remainder of the arguments
        Args:
            value (str): The attributes to assign to names: (bold, highlight, underline, italicize)
    """
    get_and_set_booleans(args)

    # Get display detail level, if provided.
    detail = getattr(args, "detail")
    if detail is not None:
        if isinstance(detail, int):
            PrimeItems.program_arguments["display_detail_level"] = detail
        elif isinstance(detail, list):
            PrimeItems.program_arguments["display_detail_level"] = detail[0]


def set_everything(program_arguments: dict) -> None:
    """
    Establish all of the settings that covers "everything" selection.
        program_arguments (dict): The program arguments.

    Returns:
        None
    """
    program_arguments["display_detail_level"] = DEFAULT_DISPLAY_DETAIL_LEVEL
    program_arguments["conditions"] = True
    program_arguments["preferences"] = True
    program_arguments["directory"] = True
    program_arguments["taskernet"] = True
    program_arguments["outline"] = True
    program_arguments["runtime"] = True
    program_arguments["pretty"] = True


def get_single_name(program_arguments: dict, args: list) -> None:
    """
    A function that extracts single names from the provided arguments and updates the program arguments accordingly.
    Args:
        program_arguments (dict): Dictionary to store extracted names.
        args (list): List of arguments to extract names from.
    Returns:
        None
    """
    the_name = getattr(args, "project")  # Display single Project
    if the_name is not None:
        program_arguments["single_project_name"] = the_name[0]
    the_name = getattr(args, "profile")  # Display single Profile
    if the_name is not None:
        program_arguments["single_profile_name"] = the_name[0]
    the_name = getattr(args, "task")  # Display single task
    if the_name is not None:
        program_arguments["single_task_name"] = the_name[0]


def get_android_settings(program_arguments: dict, args: list) -> None:
    """
    A function to get Android settings based on the provided arguments.
    Args:
        program_arguments (dict): Dictionary to store the extracted Android settings.
        args (list): List of arguments to extract Android settings from.
    Returns:
        None
    """
    if value := getattr(args, "android_ipaddr"):
        if isinstance(value, list):
            program_arguments["android_ipaddr"] = value[0]
            program_arguments["android_port"] = getattr(args, "android_port")[0]
            program_arguments["android_file"] = getattr(args, "android_file")[0]
        else:
            program_arguments["android_ipaddr"] = value
            program_arguments["android_port"] = getattr(args, "android_port")
            program_arguments["android_file"] = getattr(args, "android_file")


def process_extended_arguments(args: list) -> None:
    """
    Process extended arguments from the command line.

    Args:
        args (list): A list of command line arguments.

    Returns:
        None: This function does not return anything.

    This function processes extended arguments from the command line and updates the program arguments accordingly.
    It handles special cases and non-binary settings.

    - If the 'e' argument is present, it sets the program arguments to display full detail and sets various display options to true.
    - If there is a single name (Project/Profile/Task) present in the command line arguments, it gets it.
    - If the 'v' argument is present, it displays version info.
    - If the 'names' argument is present, it gets the name attributes.
    - If the 'appearance' argument is present, it sets the appearance mode in the program arguments.
    - If the 'i' argument is present, it sets the indentation amount in the program arguments.
    - If the 'font' argument is present, it sets the font in the program arguments.
    - If the 'file' argument is present, it sets the file in the program arguments.

    Note:
        The function assumes that the 'program_arguments' attribute is present in the 'PrimeItems' class.
    """
    program_arguments = PrimeItems.program_arguments

    # The rest of this function is to handle special cases and non-binary settings.

    # Everything? Display full detail and set various display options to true.
    if getattr(args, "e"):
        set_everything(program_arguments)

    # If there is a single name (Project/Profile/Task), then get it.
    get_single_name(program_arguments, args)

    if getattr(args, "v"):  # Display version info
        display_version()

    # Get names (bold, highlight, underline and/or highlight)
    if value := getattr(args, "names"):
        get_name_attributes(value)

    # Get Android device info for fetching the backup xml file
    get_android_settings(program_arguments, args)

    # Appearance
    if appearance := getattr(args, "appearance"):
        program_arguments["appearance_mode"] = appearance

    # Indentation amount
    if indent := get_arg_if_in_list(args, "i"):
        program_arguments["indent"] = indent

    # Font
    if font := getattr(args, "font"):
        if isinstance(font, list):
            program_arguments["font"] = font[0]
        else:
            program_arguments["font"] = font

    # File
    if file := getattr(args, "file"):
        if isinstance(file, list):
            program_arguments["file"] = file[0]
        else:
            program_arguments["file"] = file

    # Map view limit
    if view_limit := get_arg_if_in_list(args, "view_limit"):
        program_arguments["view_limit"] = view_limit


# Get our parsed program arguments and save them to PrimeItems.program_args"]
def get_runtime_arguments(args: list) -> None:
    """
    Function to get runtime arguments from the command line.

    Parameters:
        args (list): A list of command line arguments.

    Returns:
        None: This function does not return anything.

    The code defines a function get_runtime_arguments to retrieve runtime arguments from the command line,
    process boolean values, display detail level, and non-binary arguments from a list of command line arguments.
    It does not return any value.
    """
    # Color help?
    if getattr(args, "ch"):
        validate_color("h")

    # Not GUI.  Get input from command line arguments or unit test defaults.

    # All booleans and display detail level.
    get_the_other_arguments(args)

    # Get non-binary arguments
    process_extended_arguments(args)


# Add some pazaazz to the version identiifer
def display_version() -> None:
    """
    Display the version of the program.

    This function prints the program version and license information to the console.
    It also displays an ASCII art header with the program name.

    Parameters:
        None

    Returns:
        None
    """
    header = f"""

    {Colors.Purple}


███╗   ███╗ █████╗ ██████╗     ████████╗ █████╗ ███████╗██╗  ██╗███████╗██████╗
████╗ ████║██╔══██╗██╔══██╗    ╚══██╔══╝██╔══██╗██╔════╝██║ ██╔╝██╔════╝██╔══██╗
██╔████╔██║███████║██████╔╝       ██║   ███████║███████╗█████╔╝ █████╗  ██████╔╝
██║╚██╔╝██║██╔══██║██╔═══╝        ██║   ██╔══██║╚════██║██╔═██╗ ██╔══╝  ██╔══██╗
██║ ╚═╝ ██║██║  ██║██║            ██║   ██║  ██║███████║██║  ██╗███████╗██║  ██║
╚═╝     ╚═╝╚═╝  ╚═╝╚═╝            ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝

"""
    color_to_use = Colors.Yellow if darkdetect.isDark() else Colors.Blue
    print(header)
    print(f"{color_to_use}{MY_VERSION}, under license {MY_LICENSE}\033[0m")
    print("")
    clip_figure("castles", False)
    exit_program(0)


# Get arguments from command line and put them to the proper settings
def process_arguments(args: object) -> dict:
    """
    Get arguments from command line and put them to the proper settings
        Args:
            args (object): program arguments passed from command line

        Returns:
            None
    """
    # Get our runtime arguments that go into PrimeItems.program_arguments
    get_runtime_arguments(args)

    # Process color arguments.
    for item in TYPES_OF_COLORS:
        the_name = getattr(args, f"c{item}")
        if the_name is not None:
            if isinstance(the_name, list):
                get_and_set_the_color(f"-c{item}={the_name[0]}")
            else:
                get_and_set_the_color(f"-c{item}={the_name}")

    return


# Get arguments from saved file and restore them to the proper settings
def restore_arguments() -> dict:
    """
    Get arguments from saved file and restore them to the proper settings
    """
    temp_arguments = temp_colors = {}
    # Get the arguments from our saved settings file.
    temp_arguments, temp_colors = save_restore_args(temp_arguments, temp_colors, False)

    # We will get a Keyerror if the restore file does not exist
    with contextlib.suppress(KeyError):
        for (
            key,
            value,
        ) in temp_arguments.items():  # Map the prog_arg keys and values restored
            if key is not None:
                try:
                    PrimeItems.program_arguments[key] = value
                except KeyError:
                    error_handler("Error...runcli invalid argument restored: {key}!", 0)
                if key == "display_detail_level":
                    PrimeItems.program_arguments["display_detail_level"] = int(value)

        # Map the colormap keys and values restored
        for key, value in temp_colors.items():
            if key is not None:
                PrimeItems.colors_to_use[key] = value

    return


# Unit tests...
# We're running a unit test. Get the unit test arguments and create the arg namespace.
# We do this so that 1) we can run a unit test without command line arguments, and
# 2) we can rerun over and over as many times as needed.
def unit_test() -> namedtuple:  # noqa: PYI024
    """
    We're running a unit test. Get the unit test arguments and create the arg namespace
            :return: args Namespace with arguments from run_test.py
    """
    single_names = ["project", "profile", "task"]

    class Namespace:
        def __init__(self: object, **kwargs: tuple) -> None:
            self.__dict__.update(kwargs)

    # Setup default argument Namespace based on parsearg.py add_argument
    # Update this if adding a new program argument !!!

    # Each PrimeItems.program_arguments must have an entry in here.

    # single letter if the first name is a single letter, otherwise full name
    # Example: parser.add_argument( "-g","-gui",... then -g is the short name
    args = Namespace(
        appearance=None,
        android_ipaddr="",
        android_file="",
        android_port="",
        cAction=None,
        cActionCondition=None,
        cActionLabel=None,
        cActionName=None,
        cBackground=None,
        cDisabledAction=None,
        cDisabledProfile=None,
        ch=False,
        cHeading=None,
        cHighlight=None,
        cLauncherTask=None,
        conditions=False,
        cPreferences=None,
        cProfile=None,
        cProfileCondition=None,
        cProject=None,
        cScene=None,
        cTask=None,
        cTaskerNetInfo=None,
        cTrailingComments=None,
        cUnknownTask=None,
        debug=True,
        detail=3,
        directory=False,
        e=False,
        file="",
        font="Courier",
        g=False,
        guiview=False,
        i=4,
        view_limit=5000,
        names=False,
        o=False,
        p=False,
        pretty=False,
        profile=None,
        project=None,
        reset=False,
        runtime=False,
        task=None,
        taskernet=False,
        twisty=False,
        v=False,
    )
    # Go through each argument from runtest
    print("Running Unit Test.")
    for the_argument in sys.argv:
        if the_argument == "-test=yes":  # Remove unit test trigger
            continue
        new_arg = the_argument.split("=")

        # Handle boolean (True) values and colors
        if len(new_arg) == 1:
            # Handle color
            if new_arg[0][0] == "c" and new_arg[0] != "conditions":
                color_arg = new_arg[0].split()
                setattr(args, color_arg[0], color_arg[1])
            else:
                # Boolean argument.  Set as True.
                setattr(args, new_arg[0], True)

        # Handle display_detail_level, which requires an int
        elif new_arg[0] == "detail":
            new_arg[1] = int(new_arg[1])
            setattr(args, new_arg[0], new_arg[1])

        # For everything else, replace the default Namespace value with unit test value.
        elif new_arg[0] in single_names:
            setattr(args, new_arg[0], [new_arg[1]])
        else:
            setattr(args, new_arg[0], new_arg[1])

    return args


# Validate arguments by looking for inconsistancies.
def validate_arguments() -> None:
    """
    Validate arguments by looking for inconsistancies.
        Args: None

        Returns:
            Nothing"""
    program_arguments = PrimeItems.program_arguments
    # It doesn't make sense to do twisties if notr displaying full detail.
    if program_arguments["display_detail_level"] < 3 and program_arguments["twisty"]:
        message = "Twisty disabled since the display level is not 3 or above."
        print(f"{Colors.Yellow}{message}")
        logger.info(message)


# Get the program arguments from command line or via unit test (e.g. python mapit.py -x)
# Command line parameters
def process_cli() -> None:
    """
    Get the program arguments from command line or via unit test (e.g. python mapit.py -x)
        Args:
            pi (PrimeItems): Primary Items class object

        Returns:
            None
    """
    gui_flag = "g"
    reset_flag = "reset"
    version_flag = "v"
    debug_flag = "debug"

    # Intialize runtime arguments.
    try:  # Save map and diagram view flags in case we are coming from the GUI.
        save_guiview = PrimeItems.program_arguments["guiview"]
    except (TypeError, KeyError):
        save_guiview = False
    try:
        save_diagram = PrimeItems.program_arguments["doing_diagram"]
    except (KeyError, TypeError):
        save_diagram = False
    PrimeItems.program_arguments = initialize_runtime_arguments()
    PrimeItems.program_arguments["guiview"] = save_guiview
    PrimeItems.program_arguments["doing_diagram"] = save_diagram

    # Process unit tests if "-test" in arguments, else get normal runtime arguments via Parsearg.
    args = unit_test() if "-test=yes" in sys.argv else runtime_parser()

    # Get the debug argument and startup log file if in debug mode.
    PrimeItems.program_arguments["debug"] = getattr(args, debug_flag)

    logger.debug(f"Program arguments: {args}")

    # Restore runtime arguments if we are not doing a reset and not doing the GUI and there is a settings file to restore.
    # If doing thew GUI and poswsibly a map view, then the arguments are restored by userintr.py
    PrimeItems.program_arguments["reset"] = getattr(args, reset_flag)
    PrimeItems.program_arguments["gui"] = getattr(args, gui_flag)
    save_gui = PrimeItems.program_arguments["gui"]
    save_map = PrimeItems.program_arguments["guiview"]
    if (
        not PrimeItems.program_arguments["reset"]
        and not PrimeItems.program_arguments["gui"]
        and os.path.isfile(ARGUMENTS_FILE)
    ) or PrimeItems.program_arguments["guiview"]:
        restore_arguments()

        # Restore the GUI and Map View flags.
        PrimeItems.program_arguments["gui"] = save_gui  # Restore GUI flag from runtime options,
        PrimeItems.program_arguments["guiview"] = save_map  # Restore GUI Map View flag from runtime options,

        PrimeItems.program_arguments["rerun"] = False  # Make sure this is off!  Loops otherwise.

    # If using the GUI and not doing a map view or version, them process the GUI.
    do_version = getattr(args, version_flag)  # See if doing version (-v)
    if PrimeItems.program_arguments["gui"] and not PrimeItems.program_arguments["guiview"] and not do_version:
        (
            PrimeItems.program_arguments,
            PrimeItems.colors_to_use,
        ) = process_gui(True)

    # Not doing the GUI or Map View.  Process commands from command line.
    elif not PrimeItems.program_arguments["guiview"]:
        process_arguments(args)

    # Validate arguments against each other (e.g. look for combo problems).
    validate_arguments()
