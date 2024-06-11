"""Read/write the settings file"""

#! /usr/bin/env python3

#                                                                                      #
# getputer: Save and restore program arguments                                         #
#                                                                                      #
from __future__ import annotations

import contextlib
import json
import os
from datetime import timedelta
from pathlib import Path

import tomli_w
import tomllib

from maptasker.src.colrmode import set_color_mode
from maptasker.src.error import error_handler
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.maputils import reset_named_objects
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import ARGUMENTS_FILE, NOW_TIME, OLD_ARGUMENTS_FILE, logger

twenty_four_hours_ago = NOW_TIME - timedelta(hours=25)


# Settings file is corrupt.  Let user know and reset colors to use and program arguments
def corrupted_file(program_arguments: dict, colors_to_use: dict) -> None:
    """
    Checks for corrupted settings file and handles error
    Args:
        program_arguments: Command line arguments
        colors_to_use: Color settings
    Returns:
        None: Returns None
    Processing Logic:
        1. Checks settings file for corruption
        2. Generates error message if corrupted
        3. Returns error message and settings as dictionaries for GUI display
        4. Does not restore corrupted settings, asks user to re-save"""
    error_handler(
        (
            f"The settings file,  {ARGUMENTS_FILE} is"
            " corrupt!  The old settings can not be restored.  A new settings file will be saved upon exit."
        ),
        0,
    )
    # Return the error as an entry in our dictionaries for display via te GUI,
    # if needed.
    program_arguments = colors_to_use = {
        "msg": (
            "The settings file is corrupt or not compatible with the new verison of \
            MapTasker!"
            "The old settings can not be restored.  A new default settings file has been saved.",
        ),
    }
    return program_arguments, colors_to_use


# Write out our runtime settings as a TOML file
def save_arguments(program_arguments: dict, colors_to_use: dict, new_file: str) -> None:
    """
    Save the program arguments, colors to use, and new file to a JSON file.

    Args:
        program_arguments (dict): The program arguments.
        colors_to_use (list): The colors to use.
        new_file (str): The new file to save the data to.

    Returns:
        None
    """
    # In the event we set the single Projeect name due to a single Task or Profile name,
    # then reset it before we do a save and exit.
    reset_named_objects()

    guidance = {
        "Guidance": "Modify this file as needed below the entries [program_arguments] and [colors_to_use].  Run 'maptasker -h' for details.",
    }

    # Make sure apikey is hidden
    program_arguments["ai_apikey"] = "Hidden"

    # Force file object into a dictionary for json encoding
    try:
        if not isinstance(program_arguments["file"], str):
            program_arguments["file"] = program_arguments["file"].name
    except AttributeError:
        program_arguments["file"] = ""

    # Save dictionaries
    settings = {"program_arguments": program_arguments, "colors_to_use": colors_to_use, "last_run": PrimeItems.last_run}

    # Write out the guidance for the file.
    with open(new_file, "wb") as settings_file:
        tomli_w.dump(guidance, settings_file)
        settings_file.close()

    # Write out the program arguments in TOML format.  Open in binary append format (ab).
    with open(new_file, "ab") as settings_file:
        settings["program_arguments"] = dict(sorted(program_arguments.items()))  # Sort the program args first.
        settings["colors_to_use"] = dict(sorted(colors_to_use.items()))  # Sort the colors first.
        try:
            tomli_w.dump(settings, settings_file)
        except TypeError as e:
            logger.debug(f"getputer tomli failure: {e}")
            print(f"getputer tomli failure: {e}...one or more settings is 'None'!")
        settings_file.close()


# User still has setting file in older unsupported format.  Convert the info and delete it.
def process_old_formatted_file(program_arguments: dict, colors_to_use: dict, old_file: str) -> tuple:
    """
    Process an old formatted file and restore the program arguments and colors to use.

    Args:
        program_arguments (dict): The program arguments to be restored.
        colors_to_use (dict): The colors to use to be restored.
        old_file (str): The path to the old formatted file.

    Returns:
        tuple: A tuple containing the restored program arguments and colors to use.

    Raises:
        OSError: If the old file is not found.
        json.decoder.JSONDecodeError: If the old file is not in the expected format.

    This function takes in a program arguments dictionary, a colors to use dictionary, and the path to an old formatted file.
    It attempts to open the file and load the contents into a list. It then extracts the colors to use and program arguments
    from the list and restores them. It also checks for corruption by testing the display_detail_level key in the program
    arguments dictionary. If the key is a string, it converts it to an integer. If the key is not found, it calls the
    corrupted_file function. If the file is not found, it calls the error_handler function with an appropriate error message.
    If the file is not in the expected format, it calls the corrupted_file function. If the program arguments contain a
    backup_file_http key, it extracts the android_ipaddr, android_port, and android_file keys from it and updates the settings.
    """
    try:
        with open(old_file) as f:
            list_to_restore = json.load(f)
            colors_to_use = list_to_restore[0]
            program_arguments = list_to_restore[1]
            f.close()
            # Check for corruption by testing display_detail_level
            try:
                if isinstance(program_arguments["display_detail_level"], str):
                    program_arguments["display_detail_level"] = int(program_arguments["display_detail_level"])
            except KeyError:
                corrupted_file(program_arguments, colors_to_use)

    # Handle file not found condition
    except OSError:
        error_handler("'-r' MapTasker Error: No settings file found to restore!", 0)
        program_arguments = colors_to_use = {"msg": "No settings file found to restore!"}
    # Handle file format error
    except json.decoder.JSONDecodeError:  # no saved file
        corrupted_file(program_arguments, colors_to_use)

    # Convert old android device settings to new settings.
    with contextlib.suppress(KeyError):
        if program_arguments["backup_file_http"]:
            temp_args = program_arguments["backup_file_http"].split(":")
            program_arguments["android_ipaddr"] = temp_args[1][2:]
            program_arguments["android_port"] = temp_args[2]
            program_arguments["android_file"] = program_arguments["backup_file_location"]
            del program_arguments["backup_file_http"]
            del program_arguments["backup_file_location"]

    # Finally, erase the old file since it is no longer needed.
    os.remove(old_file)

    return program_arguments, colors_to_use


# Read the TOML file and return the settings.
def read_toml_file(new_file: str) -> tuple[dict, dict]:
    """
    Reads a TOML file and returns the program arguments and colors to use.

    Args:
        new_file (str): The path to the TOML file.

    Returns:
        tuple[dict, dict]: A tuple containing the program arguments (a dictionary) and the colors to use (a dictionary).

    Raises:
        tomllib.TOMLDecodeError: If the TOML file is corrupted or does not exist.

    Side Effects:
        - If the TOML file does not contain a "last_run" key, the last run date is set to yesterday (25 hours+).
        - If the TOML file does not contain a "colors_to_use" key, the colors to use are set to blank.
        - If the TOML file does not contain a "program_arguments" key, the program arguments are initialized.
        - If the TOML file is corrupted or does not exist, the function calls the "corrupted_file" function.

    """
    with open(new_file, "rb") as f:
        # Setup old date if date last used is not in TROML settings file.  Catch all possible errors with TOML file.
        try:
            # Colors to use
            settings = tomllib.load(f)
            try:
                colors_to_use = settings["colors_to_use"]  # Get the colors to use
            except KeyError:
                colors_to_use = set_color_mode("")  # If this hadn't been previously saved, set it to blank

            # Program arguments
            try:
                program_arguments = settings["program_arguments"]  # Get the program arguments
            except KeyError:
                program_arguments = initialize_runtime_arguments()
            try:
                PrimeItems.last_run = settings["last_run"]  # Get the last run date
            except KeyError:
                # If this hadn't been previously saved, set it to yesterday (25 hours+).
                PrimeItems.last_run = twenty_four_hours_ago

            f.close()
        except tomllib.TOMLDecodeError:  # no saved file
            corrupted_file(program_arguments, colors_to_use)

    return program_arguments, colors_to_use


# Read in the TOML runtime settings
def read_arguments(program_arguments: dict, colors_to_use: dict, old_file: str, new_file: str) -> None:
    """
    Reads the program arguments, colors to use, old file, and new file.

    Parameters:
        program_arguments (dict): A dictionary containing program arguments.
        colors_to_use (dict): A dictionary containing colors to use.
        old_file (str): The path to the old file.
        new_file (str): The path to the new file.

    Returns:
        None: This function does not return anything.
    """
    # First see if there is an old formatted file to restore.
    if os.path.isfile(old_file):
        program_arguments, colors_to_use = process_old_formatted_file(program_arguments, colors_to_use, old_file)

    # Read the TOML file
    elif os.path.isfile(new_file):
        program_arguments, colors_to_use = read_toml_file(new_file)

    return program_arguments, colors_to_use


# Save and restore colors to use and program arguments
def save_restore_args(
    program_arguments: dict,
    colors_to_use: dict,
    to_save: bool,
) -> tuple[dict, dict]:
    """
    Save and restore colors to use and program arguments
        :param program_arguments: program runtime arguments to save or restore into
        :param colors_to_use: color dictionary to save or restore into
        :param to_save: True if this is a save request, False is restore request
        :return: program runtime arguments saved/restored, colors to use saved/restored
    """
    new_file = f"{Path.cwd()}{PrimeItems.slash}{ARGUMENTS_FILE}"
    old_file = f"{Path.cwd()}{PrimeItems.slash}{OLD_ARGUMENTS_FILE}"

    # Saving?
    if to_save:
        save_arguments(program_arguments, colors_to_use, new_file)

    # Restore dictionaries
    else:
        program_arguments, colors_to_use = read_arguments(program_arguments, colors_to_use, old_file, new_file)

    return program_arguments, colors_to_use
