#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# runcli: process command line interface arguments for MapTasker                       #
#                                                                                      #
# Add the following statement (without quotes) to your Terminal Shell config file.     #
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
# #################################################################################### #
import contextlib
import sys
from collections import namedtuple

import darkdetect

from maptasker.src.clip import clip_figure
from maptasker.src.colors import get_and_set_the_color, validate_color
from maptasker.src.error import error_handler
from maptasker.src.getputarg import save_restore_args
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.parsearg import runtime_parser
from maptasker.src.rungui import process_gui
from maptasker.src.sysconst import (
    MY_LICENSE,
    MY_VERSION,
    TYPES_OF_COLORS,
    Colors,
    logger,
)


# ################################################################################
# Determine if the argument is a list or string, and return the value as appropriate
# ################################################################################
def get_arg_if_in_list(
    args: namedtuple("ArgNamespace", ["some_arg", "another_arg"]), the_argument: str
) -> int:
    """_summary_
    Determine if the argument is a list or string, and return the value as appropriate
        Args:
            args (Namespace): the args Namespace from either argparse or unit_test
            the_argument (str): the arguemnt to get

        Returns:
            int: the numeric value for the argument that was gotten
    """
    if the_value := getattr(args, the_argument):
        return int(the_value[0]) if isinstance(the_value, list) else int(the_value)
    else:
        return the_value


# ##################################################################################
# We have the "backup" argument.  Validate and save it.
# ##################################################################################
def process_backup(primary_items: dict, backup_file_info: list) -> None:
    """_summary_
    We have the "backup" argument.  Validate info and save it.
        Args:
            primary_items (dict): Common items used throughout.  See primitem.py for details.
            backup_file_info (list): A list of the values for the backup to use
    """
    if isinstance(backup_file_info, list):
        backup_details = backup_file_info[0].split("+")
    else:
        backup_details = backup_file_info.split("+")

    # Break up the command into http portion and file-location portion
    if backup_details[0].isdigit and backup_details[1]:
        primary_items["program_arguments"]["backup_file_http"] = backup_details[0]
        primary_items["program_arguments"]["backup_file_location"] = backup_details[1]


# ##################################################################################
# We have a -name argument.  Get the name's attributes and save them
# ##################################################################################
def get_name_attributes(primary_items: dict, value: str) -> None:
    """_summary_
    We have a -name argument.  Get the name's attributes and save them
        Args:
            primary_items (dict): Common items used throughout.  See primitem.py for details.
            value (str): The attributes to assign to names: (bold, highlight, underline, italicize)
    """
    # Get names (bold, highlight, underline and/or highlight)
    # If value is a list, convert it to a string first
    valid_attributes = ["bold", "highlight", "underline", "italicize"]

    name_attributes = " ".join(value) if isinstance(value, list) else value
    name_attributes = name_attributes.split()
    for attribute in name_attributes:
        if attribute in valid_attributes:
            primary_items["program_arguments"][attribute] = True


# ##################################################################################
# Go through all boolean settings, get each and if have it then set value to True
# ##################################################################################
def get_and_set_booleans(
    primary_items: dict, args: namedtuple("ArgNamespace", ["some_arg", "another_arg"])
) -> None:
    """_summary_
    Go through all boolean settings, get each and if have it then set value to True
        Args:
            primary_items (dict): Common items used throughout.  See primitem.py for details.
            args (namedtuple): runtime arguments namespace
    """
    # Program runtime boolean arguments (long form and short form per argparse.py)
    boolean_arguments = {
        "conditions": "",
        "debug": "",
        "directory": "",
        "everything": "e",
        "outline": "o",
        "preferences": "",
        "restore": "",
        "runtime": "",
        "save": "s",
        "taskernet": "",
        "twisty": "",
    }

    # Loop through all possible boolean program arguments and get/set each
    # Check both the long name (key) and the short name (value)
    # NOTE: We can not use an either/or combination if statement to test both the
    #       key and the value since an exception on the first test will automatically
    #       skip doing the "or" second test.
    for key, value in boolean_arguments.items():
        try:
            if getattr(args, key):
                primary_items["program_arguments"][key] = True
        except AttributeError:
            with contextlib.suppress(AttributeError):
                if value and getattr(args, value):
                    primary_items["program_arguments"][key] = True


# ##################################################################################
# Get the the other arguments
# ##################################################################################
def get_the_other_arguments(
    primary_items: dict, args: namedtuple("ArgNamespace", ["some_arg", "another_arg"])
) -> None:
    """_summary_
    Get the remainder of the arguments
        Args:
            primary_items (dict): Common items used throughout.  See primitem.py for details.
            value (str): The attributes to assign to names: (bold, highlight, underline, italicize)
    """
    get_and_set_booleans(primary_items, args)

    # Get display detail level, if provided.
    detail = getattr(args, "detail")
    if detail is not None and isinstance(detail, int):
        primary_items["program_arguments"]["display_detail_level"] = detail

    elif (detail := get_arg_if_in_list(args, "detail")) is not None:
        primary_items["program_arguments"]["display_detail_level"] = detail


# ##################################################################################
# Get our parsed program arguments and save them to primary_items["program_args"]
# ##################################################################################
def get_runtime_arguments(
    primary_items: dict, args: namedtuple("ArgNamespace", ["some_arg", "another_arg"])
) -> None:
    """_summary_
    Get our parsed program arguments and save them to primary_items["program_args"]
        Args:
            primary_items (dict): Common items used throughout.  See primitem.py for details.
            args (list): runtime arguments namespace
    """

    # Color help?
    if getattr(args, "ch"):
        validate_color("h")

    # Not GUI.  Get input from command line arguments

    # Everything? Display full detail and set various display optionsm to true.
    if getattr(args, "e"):
        primary_items["program_arguments"]["display_detail_level"] = 4
        primary_items["program_arguments"]["conditions"] = primary_items[
            "program_arguments"
        ]["preferences"] = primary_items["program_arguments"][
            "directory"
        ] = primary_items[
            "program_arguments"
        ][
            "taskernet"
        ] = primary_items[
            "program_arguments"
        ][
            "outline"
        ] = primary_items[
            "program_arguments"
        ][
            "runtime"
        ] = True

    # Get input from command line arguments
    get_the_other_arguments(primary_items, args)

    the_name = getattr(args, "project")  # Display single Project
    if the_name is not None:
        primary_items["program_arguments"]["single_project_name"] = the_name[0]
    the_name = getattr(args, "profile")  # Display single Profile
    if the_name is not None:
        primary_items["program_arguments"]["single_profile_name"] = the_name[0]
    the_name = getattr(args, "task")  # Display single task
    if the_name is not None:
        primary_items["program_arguments"]["single_task_name"] = the_name[0]
    if getattr(args, "v"):  # Display version info
        display_version()

    # Get names (bold, highlight, underline and/or highlight)
    if value := getattr(args, "names"):
        get_name_attributes(primary_items, value)
    # Get backup file directly from Android device
    # It is a list if coming from program arguments.
    # Otherwise, just a string if coming from run_test (unit test)
    if backup_file_info := getattr(args, "b"):
        process_backup(primary_items, backup_file_info)

    # Appearance
    if appearance := getattr(args, "a"):
        primary_items["program_arguments"]["appearance_mode"] = appearance

    # Indentation amount
    if indent := get_arg_if_in_list(args, "i"):
        primary_items["program_arguments"]["indent"] = indent

    # Font
    if font := getattr(args, "f"):
        if isinstance(font, list):
            primary_items["program_arguments"]["font"] = font[0]
        else:
            primary_items["program_arguments"]["font"] = font


# ##################################################################################
# Add some pazaazz to the version identiifer
# ##################################################################################
def display_version():
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
    exit(0)


# ##################################################################################
# Get arguments from command line and put them to the proper settings
# ##################################################################################
def process_arguments(primary_items: dict, args: object) -> dict:
    """_summary_
    Get arguments from command line and put them to the proper settings
        Args:
            primary_items (dict): dictionary of the primary items used throughout the
            module.  See primitem.py for details
            args (object): program arguments passed from command line

        Returns:
            dict: modfgied primary_items based on program arguments
    """
    # Get our runtime arguments that go into primary_items["program_arguments"]
    get_runtime_arguments(primary_items, args)

    # Process colors
    for item in TYPES_OF_COLORS:
        the_name = getattr(args, f"c{item}")
        if the_name is not None:
            if isinstance(the_name, list):
                get_and_set_the_color(primary_items, f"-c{item}={the_name[0]}")
            else:
                get_and_set_the_color(primary_items, f"-c{item}={the_name}")

    # Save the arguments
    if getattr(args, "s"):
        (
            primary_items["program_arguments"],
            primary_items["colors_to_use"],
        ) = save_restore_args(
            primary_items["program_arguments"], primary_items["colors_to_use"], True
        )

    return primary_items


# ##################################################################################
# Get arguments from saved file and restore them to the proper settings
# ##################################################################################
def restore_arguments(primary_items: dict) -> dict:
    """
    Get arguments from saved file and restore them to the proper settings
        :param primary_items:  Program registry.  See primitem.py for details.
        :return: primary items
    """
    temp_arguments = temp_colors = {}
    temp_arguments, temp_colors = save_restore_args(temp_arguments, temp_colors, False)

    # We will get a Keyerror if the restore file does not exist
    with contextlib.suppress(KeyError):
        for (
            key,
            value,
        ) in temp_arguments.items():  # Map the prog_arg keys and values restored
            if key is not None:
                try:
                    primary_items["program_arguments"][key] = value
                except KeyError:
                    error_handler("Error...runcli invalid argument restored: {key}!", 0)
                if key == "display_detail_level":
                    primary_items["program_arguments"]["display_detail_level"] = int(
                        value
                    )

        # Map the colormap keys and values restored
        for key, value in temp_colors.items():
            if key is not None:
                primary_items["colors_to_use"][key] = value

    return primary_items


# ##################################################################################
# We're running a unit test. Get the unit test arguments and create the arg namespace
# ##################################################################################
def unit_test() -> namedtuple("ArgNamespace", ["some_arg", "another_arg"]):
    """
    We're running a unit test. Get the unit test arguments and create the arg namespace
            :return: args Namespace with arguments from run_test.py
    """
    single_names = ["project", "profile", "task"]

    class Namespace:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    # Setup default argument Namespace based on parsearg.py add_argument
    # Update this if adding a new program argument !!!

    # Each primary_items["program_arguments"] must have an entry in here.

    # single letter if the first name is a single letter, otherwise full name
    # Example: parser.add_argument( "-g","-gui",... then -g is the short name
    args = Namespace(
        a=None,
        b=False,
        cAction=None,
        cActionCondition=None,
        cActionLabel=None,
        cActionName=None,
        cBackground=None,
        cBullet=None,
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
        f="Courier",
        g=False,
        i=4,
        names=False,
        o=False,
        p=False,
        profile=None,
        project=None,
        restore=False,
        runtime=False,
        s=False,
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


# ##################################################################################
# Validate arguments by looking for inconsistancies.
# ##################################################################################
def validate_arguments(primary_items: dict) -> None:
    """_summary_
    Validate arguments by looking for inconsistancies.
        Args:
            primary_items (dict): Program registry.  See primitem.py for details.

        Returns:
            Nothing
    """
    program_arguments = primary_items["program_arguments"]
    # It doesn't make sense to do twisties if notr displaying full detail.
    if program_arguments["display_detail_level"] < 3 and program_arguments["twisty"]:
        message = "Twisty disabled since the display level is not 3 or above."
        print(f"{Colors.Yellow}{message}")
        logger.info(message)


# ##################################################################################
# Get the program arguments from command line or via unit test (e.g. python mapit.py -x)
# ##################################################################################
# Command line parameters
def process_cli(primary_items: dict) -> dict:
    """_summary_
    Get the program arguments from command line or via unit test (e.g. python mapit.py -x)
        Args:
            primary_items (dict): Program registry.  See primitem.py for details.

        Returns:
            dict: Program registry.  See primitem.py for details.
    """

    # Convert runtime argument default values to a dictionary
    primary_items["program_arguments"] = initialize_runtime_arguments()

    # Process unit tests if "-test" in arguments, else get normal runtime arguments
    # args = unit_test() if "-test=yes" in sys.argv else runtime_parser()
    args = unit_test() if "-test=yes" in sys.argv else runtime_parser()
    logger.debug(f"Program arguments: {args}")

    # Grab the results
    if getattr(args, "g"):  # GUI for input?
        (
            primary_items["program_arguments"],
            colormap,
        ) = process_gui(primary_items, True)

    # Restore arguments from file?
    elif getattr(args, "restore"):
        # Restore all changes that have been saved for progargs
        primary_items = restore_arguments(primary_items)
        primary_items["program_arguments"]["restore"] = True

    # Process commands from command line
    else:
        primary_items = process_arguments(primary_items, args)

    # Validate arguements against each other.
    validate_arguments(primary_items)

    # Return the results
    return primary_items
