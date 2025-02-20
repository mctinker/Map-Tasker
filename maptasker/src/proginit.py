#! /usr/bin/env python3  # noqa: D100

#                                                                                      #
# proginit: perform program initialization functions                                   #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
import atexit
import contextlib
import json
import os
import platform
import re
import sys
from collections import namedtuple
from json import dumps, loads  # For write and read counter
from pathlib import Path
from tkinter import TkVersion, messagebox

# importing askopenfile (from class filedialog) and messagebox functions
from tkinter.filedialog import askopenfile

import requests

import maptasker.src.progargs as get_arguments
from maptasker.src.actionc import action_codes
from maptasker.src.colrmode import set_color_mode
from maptasker.src.config import DARK_MODE, GUI
from maptasker.src.error import error_handler

# from maptasker.src.fonts import get_fonts
from maptasker.src.frontmtr import output_the_front_matter
from maptasker.src.getbakup import get_backup_file
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import (
    COUNTER_FILE,
    MY_VERSION,
    NOW_TIME,
    TYPES_OF_COLOR_NAMES,
    logger,
    logging,
)
from maptasker.src.taskerd import get_the_xml_data

ActionCode = namedtuple(  # noqa: PYI024
    "ActionCode",
    ("redirect", "args", "display", "reqargs", "evalargs"),
)


# Use a counter to determine if this is the first time run.
#  If first time only, then provide a user prompt to locate the backup file
def read_counter() -> int:
    """
    Read the program counter
    Get the count of the number of times MapTasker has been called
        Parameters: none
        Returns: the count of the number of times the program has been called
    """
    try:
        with open(COUNTER_FILE) as f:
            return loads(f.read()) + 1 if Path.exists(Path(COUNTER_FILE).resolve()) else 0
    except FileNotFoundError:
        return 0


def write_counter() -> None:
    """
    Write the program counter
    Write out the number of times MapTasker has been called
        Parameters: none
        Returns: none
    """
    with open(COUNTER_FILE, "w") as f:
        f.write(dumps(run_counter))


run_counter = read_counter()
atexit.register(write_counter)


# Prompt user to select the backup xml file to use.
def prompt_for_backup_file(dir_path: str) -> None:
    """
    Prompt user to select a backup file
    Args:
        dir_path (str): Path to initial directory for file selection dialog
    Returns:
        None: No value is returned
    Processing Logic:
        - Try to open a file selection dialog to choose an XML backup file
        - Set a flag if any exception occurs or no file is selected
        - Check the flag and call an error handler if running without GUI
        - Set an error code if running with GUI
    """
    file_error = False
    # Tkinter prompt for file selection.
    try:
        PrimeItems.file_to_get = askopenfile(
            parent=PrimeItems.tkroot,
            mode="r",
            title="Select Tasker backup xml file",
            initialdir=dir_path,
            filetypes=[("XML Files", "*.xml")],
        )
        PrimeItems.error_code = 0  # No error.  Clear the code if there is one.
    except Exception:  # noqa: BLE001
        file_error = True
    if PrimeItems.file_to_get is None:
        file_error = True
    if file_error and not PrimeItems.program_arguments["gui"]:
        error_handler("Backup file selection canceled.  Program ended.", 6)
    elif file_error:
        PrimeItems.error_code = 6


# Open and read the Tasker backup XML file
# Return the file name for use for
def open_and_get_backup_xml_file() -> dict:
    """
    Open the Tasker backup file and return the file object
    """
    # Fetch backup xml directly from Android device?
    if (
        PrimeItems.program_arguments["android_ipaddr"]
        and PrimeItems.program_arguments["android_file"]
        and PrimeItems.program_arguments["android_port"]
    ):
        backup_file_name = get_backup_file()

        # If no backup file and we're coming from the GUI, then return to GUI.
        if backup_file_name is None and PrimeItems.program_arguments["gui"]:
            return None

        # Make sure we automatically use the file we just fetched
        PrimeItems.program_arguments["file"] = backup_file_name

    logger.info("entry")

    # Reset the file name
    PrimeItems.file_to_get = None

    # Get current directory
    dir_path = Path.cwd()
    logger.info(f"dir_path: {dir_path}")

    # If debug and we didn't fetch the backup file from Android device, default to
    # "backup.xml" file as backup to restore
    if (
        PrimeItems.program_arguments["debug"]
        and PrimeItems.program_arguments["fetched_backup_from_android"] is False
        and not PrimeItems.program_arguments["file"]
    ):
        PrimeItems.program_arguments["file"] = ""
        try:
            PrimeItems.file_to_get = open(f"{dir_path}{PrimeItems.slash}backup.xml")
        except OSError:
            error_handler(
                (f"Error: Debug is on and the backup.xml file was not found in {dir_path}."),
                3,
            )
            prompt_for_backup_file(dir_path)

    # See if we already have the file
    elif PrimeItems.program_arguments["file"]:
        filename = isinstance(PrimeItems.program_arguments["file"], str)
        filename = PrimeItems.program_arguments["file"].name if not filename else PrimeItems.program_arguments["file"]

        # We already have the file name...open it.
        try:
            PrimeItems.file_to_get = open(filename)
        except FileNotFoundError:
            file_not_found = filename
            error_handler(f"Backup file {file_not_found} not found.  Program ended.", 6)
    else:
        prompt_for_backup_file(dir_path)

    return


# Build color dictionary
def setup_colors() -> dict:
    """
    Determine and set colors to use in the output
        Args:
            None

        Returns:
            dict: dictionary of colors to use.
    """

    # Runtime argument "appearance" establishes the mode.
    # If it is not specified, then DARK_MODE from config.py sets mode.
    if PrimeItems.program_arguments["appearance_mode"] == "system":
        appearance = "dark" if DARK_MODE else "light"
    else:
        appearance = PrimeItems.program_arguments["appearance_mode"]
        return set_color_mode(appearance)

    colors_to_use = set_color_mode(appearance)

    # See if a color has already been assigned.  If so, keep it.  Otherwise,
    # use default from set_color_mode.
    with contextlib.suppress(Exception):
        if PrimeItems.colors_to_use:
            for color_argument_name in TYPES_OF_COLOR_NAMES.values():
                try:
                    if PrimeItems.colors_to_use[color_argument_name]:
                        colors_to_use[color_argument_name] = PrimeItems.colors_to_use[color_argument_name]
                except KeyError:
                    continue

    return colors_to_use


# Set up logging
def setup_logging() -> None:
    """
    Set up the logging: name the file and establish the log type and format
    """
    logging.basicConfig(
        filename="maptasker.log",
        filemode="w",
        format="%(asctime)s,%(msecs)d %(levelname)s %(name)s %(funcName)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.DEBUG,
    )
    logger.info(sys.version_info)


# Log the arguments
def log_startup_values() -> None:
    """
    Log the runtime arguments and color mappings
    """
    setup_logging()  # Get logging going
    logger.info(f"{MY_VERSION} {str(NOW_TIME)}")  # noqa: RUF010
    logger.info(f"sys.argv:{str(sys.argv)}")  # noqa: RUF010
    for key, value in PrimeItems.program_arguments.items():
        logger.info(f"{key}: {value}")
    for key, value in PrimeItems.colors_to_use.items():
        logger.info(f"colormap for {key} set to {value}")


# POpen and read xml and output the introduction/heading matter
def get_data_and_output_intro(do_front_matter: bool) -> int:
    """
    Gets data from Tasker backup file and outputs introductory information.

    Args:
        do_front_matter (bool): True = output the front matter, False = don't bother
    Returns:
        int: 0 if okay, non-zero if error (error code)

    Processing Logic:
    - Opens and reads the Tasker backup XML file
    - Extracts all the XML data from the file
    - Closes the file after reading
    - Outputs initial information like header and source to the user
    """
    # Only get the XML if we don't already have it.
    tasker_root_elements = PrimeItems.tasker_root_elements
    return_code = 0
    if (
        not tasker_root_elements["all_projects"]
        and not tasker_root_elements["all_profiles"]
        and not tasker_root_elements["all_tasks"]
        and not tasker_root_elements["all_scenes"]
    ):
        # We don't yet have the data.  Let's get it.
        if not PrimeItems.program_arguments["file"]:
            PrimeItems.program_arguments["file"] = (
                PrimeItems.file_to_get if PrimeItems.file_to_use == "" else PrimeItems.file_to_use
            )

        # Only display message box if we don't yet have the file name,
        # if this is not the first time ever that we have run (run_counter < 1),
        # and not running from the GUI.
        if not PrimeItems.file_to_get and run_counter < 1 and not GUI:
            msg = "Locate the Tasker XML file to use to map your Tasker environment"
            messagebox.showinfo("MapTasker", msg)

        # Open and read the file...
        open_and_get_backup_xml_file()
        if PrimeItems.error_code > 0:
            return PrimeItems.error_code

        # Go get all the xml data
        return_code = get_the_xml_data()

        # Close the file
        PrimeItems.file_to_get.close()

    # Output the inital info: head, source, etc. ...if it hasn't already been output.
    if return_code == 0 and do_front_matter and not PrimeItems.output_lines.output_lines:
        output_the_front_matter()
        return 0

    return return_code


# Make sure we have the appropriate version of Python and Tkinter
def check_versions() -> None:
    """
    Checks the Python and Tkinter versions
    Args:
        None: No arguments
    Returns:
        None: Does not return anything
    - It gets the Python version and splits it into major, minor, and patch numbers
    - It checks if the major version is less than 3 or the major is 3 and minor is less than 11
    - It gets the Tkinter version and splits it into major and minor
    - It checks if the major is less than 8 or the major is 8 and minor is less than 6
    - If either check fails, it logs and prints an error message and exits
    """
    msg = ""
    version = sys.version
    version = version.split(" ")
    major, minor, _ = (int(x, 10) for x in version[0].split("."))
    if major < 3 or (major == 3 and minor < 11):
        msg = f"Python version {sys.version} is not supported.  Please use Python 3.11 or greater."
    version = str(TkVersion)
    major, minor = version.split(".")
    if int(major) < 8 or (int(major) == 8 and int(minor) < 6):
        msg = (
            f"{msg}  Tcl/tk (Tkinter) version {TkVersion} is not supported.  Please use Tkinter version 8.6 or greater."
        )
        logger.error(msg)
    if msg:
        logger.error("MapTasker", msg)
        print(msg)
        exit(0)  # noqa: PLR1722


def java_constants_to_dict(url) -> dict:
    """
    Fetches a Java source file from the given URL and extracts public static final int constants.

    Args:
        url (str): The URL of the Java source file.

    Returns:
        dict: A dictionary where the keys are the constant names and the values are their corresponding integer values.

    Raises:
        requests.exceptions.RequestException: If there is an issue with the HTTP request.
    """
    constants = {}
    pattern = re.compile(r"public\s+static\s+final\s+int\s+(\w+)\s*=\s*(-?\d+);")

    response = requests.get(url, timeout=10)
    response.raise_for_status()

    for line in response.text.splitlines():
        match = pattern.search(line)
        if match:
            constants[match.group(1)] = int(match.group(2))

    return constants


class CustomJSONEncoder(json.JSONEncoder):
    """
    Custom JSON Encoder that capitalizes JSON boolean values.

    This encoder overrides the default JSONEncoder to replace lowercase
    boolean values ('true', 'false') with their capitalized counterparts
    ('True', 'False') in the resulting JSON string.
    """

    def iterencode(self, obj: object, _one_shot: bool = False) -> object:
        """
        Encodes the given object to a JSON formatted string, replacing lowercase
        JSON booleans with their capitalized counterparts.

        Args:
            obj: The object to encode.
            _one_shot (bool): Whether to use a single-pass encoding process.

        Yields:
            str: Chunks of the JSON encoded string with capitalized booleans.
        """
        for chunk in super().iterencode(obj, _one_shot):
            yield chunk.replace("true", "True").replace("false", "False")  # Capitalizing JSON booleans


def save_dict_to_json(dictionary: dict, filename: str) -> None:
    """
    Save a dictionary to a JSON file.

    Args:
        dictionary (dict): The dictionary to save.
        filename (str): The path to the file where the dictionary will be saved.

    Returns:
        None
    """
    with open(filename, "w") as file:
        json.dump(dictionary, file, indent=4, cls=CustomJSONEncoder)


def merge_type(arg_type: str) -> int:
    """
    Retrieve the integer value associated with a given argument type from PrimeItems.tasker_arg_specs.

    Args:
        arg_type (str): The type of argument to look up in PrimeItems.tasker_arg_specs.

    Returns:
        int: The integer value associated with the provided argument type.
    """
    for key, value in PrimeItems.tasker_arg_specs.items():
        if value == arg_type:
            return key
    return None


def merge_add_arg(
    args: list,
    argid: str,
    manditory: bool,
    name: str,
    argtype: str,
    value: ActionCode,
    position: int,
    plugin: bool = False,
) -> list:
    """
    Adds a new argument to the list of arguments.

    Args:
        args (list): The list of arguments to which the new argument will be added.
        argid (str): The identifier for the argument.
        manditory (bool): Whether the argument is mandatory.
        name (str): The name of the argument.
        argtype (str): The type of the argument.
        value (ActionCode): The value from which to get the evaluation element.

    Returns:
        list: The updated list of arguments with the new argument added.
    """
    # Get the evaluation arguments
    if not plugin:  # Task/State/Event
        try:
            evaluate = value.evalargs[position] if position >= 0 else "undefined"
        except NameError:
            evaluate = ""
    else:  # Plugin
        try:
            evaluate = value.evalargs[position] if position >= 0 else "undefined"
        except NameError:
            evaluate = ""

    args.append((argid, manditory, name, argtype, evaluate))
    return args


def merge_codes(new_dict: dict, just_the_code: str, code: str, value: object) -> dict:
    """
    Merges tasker action codes into a new dictionary.

    Args:
        new_dict (dict): The dictionary to merge the codes into.
        just_the_code (str): The key to look up in the tasker action codes.
        code (str): The code to use as the key in the new dictionary.
        value (object): An object containing the required arguments and evaluation arguments.

    Returns:
        dict: The updated dictionary with the merged codes.

    Raises:
        KeyError: If the `just_the_code` is not found in `PrimeItems.tasker_action_codes`.
    """
    try:
        tasker_action_code = PrimeItems.tasker_action_codes[just_the_code]
        args = []
        for arg in tasker_action_code["args"]:
            try:
                arg_pos = value.reqargs.index(str(arg["id"]))
            except (ValueError, AttributeError):
                arg_pos = -1

            # Add the argument
            args = merge_add_arg(
                args,
                arg["id"],
                arg["isMandatory"],
                arg["name"],
                arg["type"],
                value,
                arg_pos,
                plugin=False,
            )

        # Get optional values
        category = tasker_action_code.get("category_code", "")
        canfail = tasker_action_code.get("canfail", "")
        # Build the dictionary
        new_dict[code] = ActionCode(
            "",
            args,
            tasker_action_code["name"],
            category,
            canfail,
        )

    # It's a plugin
    except KeyError:
        # Copy relevant data to new dictionary,
        args = []
        if value.reqargs:
            for num, arg in enumerate(value.reqargs):
                argtype = value.types[num]
                # Add the argument
                args = merge_add_arg(args, arg, True, "", merge_type(argtype), value, num, plugin=True)

        # Add it to our dictionary
        new_dict[code] = ActionCode(value.redirect, args, value.display, "", "")
    return new_dict


def merge_action_codes() -> None:
    """
    Merges action codes from the global `action_codes` dictionary and `PrimeItems.tasker_action_codes` dictionary
    into a new dictionary, and saves the result to a file.

    The function performs the following steps:
    1. Iterates through the old `action_codes` dictionary and processes each code based on its type.
       - If the code type is 't', 's', or 'e' and the code (excluding the last character) is numeric, it merges the code
       with the code table read from Tasker's development site (`PrimeItems.tasker_action_codes`).
       - Otherwise, it handles screen elements by creating a list of arguments and adding them to the new dictionary.
    2. Ensures that all codes from `PrimeItems.tasker_action_codes` are included in the new dictionary.
       - If a code is not present, it merges the code with a modified version of the code.
    3. Saves the new dictionary to a file named "newdict.txt" in Python syntax.

    The function does not return any value.
    """
    new_dict = {}
    for code, value in action_codes.items():
        just_the_code = code[:-1]
        code_type = code[-1]
        # Task?
        if code_type in ("t", "s", "e") and just_the_code.isdigit():
            # if code == "1040876951t":
            #    print("bingo")
            new_dict = merge_codes(new_dict, just_the_code, code, value)

        # Handle screen elements
        else:
            args = []
            for num, arg in enumerate(value.reqargs):
                evaluate = value.evalargs[num] if num else "undefined"
                args.append(("", arg, True, "", evaluate))
            new_dict[code] = ActionCode(value.redirect, args, value.display, "", "")

    # Check if all PrimeItems.tasker_action_codes are in action_codes, and if not, then add it.
    for just_the_code, value in PrimeItems.tasker_action_codes.items():
        modified_code = f"{just_the_code}t"
        if modified_code not in new_dict:
            tasker_action_code = PrimeItems.tasker_action_codes[just_the_code]
            # Format the arguments
            args = []
            for arg in tasker_action_code["args"]:
                args.append(("", arg["id"], arg["isMandatory"], arg["name"], arg["type"], ""))
            # Get optional values
            category = tasker_action_code.get("category_code", "")
            canfail = tasker_action_code.get("canfail", "")
            print("Adding Task action:", value["name"])
            new_dict[modified_code] = ActionCode("", args, value["name"], category, canfail)

    # Sort and save the new dictionary so we can import it.
    new_dict = dict(sorted(new_dict.items()))
    save_dict_to_json(new_dict, "newdict.py")

    print("New Action Codes dictionary saved.")


def build_action_codes() -> None:
    """
    Builds the action codes dictionary from the Tasker JSON files.
    Args:
        None
    Returns:
        None
    """
    # Get the JSON directory
    asset_dir = (
        f"{os.getcwd()}{PrimeItems.slash}maptasker{PrimeItems.slash}assets{PrimeItems.slash}json{PrimeItems.slash}"
    )
    # Get the map of all Tasker task action codes and their arguments
    with open(f"{asset_dir}task_all_actions.json", encoding="utf-8") as file:
        tasker_codes = json.load(file)
        # Go thru the list of dictionaries and build our own dictionary.
        for value in tasker_codes:
            PrimeItems.tasker_action_codes[str(value["code"])] = {
                "args": value["args"],
                "canfail": value.get("canFail", False),
                "category_code": value["categoryCode"],
                "name": value["name"],
            }
        # Sort the dictionary
        PrimeItems.tasker_action_codes = dict(sorted(PrimeItems.tasker_action_codes.items()))

    # Get the map of all Tasker task action argument types
    with open(f"{asset_dir}arg_specs.json", encoding="utf-8") as file:
        PrimeItems.tasker_arg_specs = json.load(file)
        spec_number = len(PrimeItems.tasker_arg_specs)
        PrimeItems.tasker_arg_specs[str(spec_number)] = "ConditionList"
        for key, value in PrimeItems.tasker_arg_specs.items():
            if value == "String":
                PrimeItems.tasker_arg_specs[key] = "Str"
                break

    # Get the action category description
    with open(f"{asset_dir}category_descriptions.json", encoding="utf-8") as file:
        category_descriptions = json.load(file)
        for description in category_descriptions:
            PrimeItems.tasker_category_descriptions[description["code"]] = description["name"]

    # Get the event codes
    url = "https://tasker.joaoapps.com/code/EventCodes.java"
    PrimeItems.tasker_event_codes = java_constants_to_dict(url)

    # Get the state codes
    url = "https://tasker.joaoapps.com/code/StateCodes.java"
    PrimeItems.tasker_state_codes = java_constants_to_dict(url)

    # Merge actionc with this new data to create a new dictionary
    merge_action_codes()


# Perform maptasker program initialization functions
def start_up() -> dict:
    # Get any arguments passed to program
    """
    Initializes the program startup.
    Args:
        None
    Returns:
        None
    Processing Logic:
        - Gets any arguments passed to the program
        - Migrates any old argument files to a new format
        - Gets runtime arguments from the command line or GUI
        - Gets the list of available fonts
        - Gets a map of colors to use
        - Gets key program elements and outputs intro text
        - Logs startup values if debug mode is enabled
    """
    logger.info(f"sys.argv{sys.argv!s}")

    # Get the OS so we know which directory slash to use (/ or \)
    our_platform = platform.system()
    if our_platform == "Windows":
        PrimeItems.slash = "\\"
    else:
        PrimeItems.slash = "/"

    # Validate runtime versions for python and tkinter
    check_versions()

    # Get runtime arguments (from CLI or GUI)
    get_arguments.get_program_arguments()

    # Get our list of fonts
    # _ = get_fonts(True)

    # If debug mode, log the arguments
    if PrimeItems.program_arguments["debug"]:
        log_startup_values()

    # Get our map of colors
    PrimeItems.colors_to_use = setup_colors()

    # Build the action codes
    # NOTE: FOR DEVELOPMENT ONLY!!! THIS ROUTINE SHOULD ONLY BE RUN WITH A NEW UPDATE OF TASKER!
    # build_action_codes()

    # Display a popup window telling user we are analyzing
    if PrimeItems.program_arguments["doing_diagram"]:
        PrimeItems.program_arguments["doing_diagram"] = False

    # Get the XML data and output the front matter
    _ = get_data_and_output_intro(True)

    return
