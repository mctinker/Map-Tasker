"""Read/write the settings file"""

#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# getputer: Save and restore program arguments                                         #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
from __future__ import annotations

import contextlib
import json
import os


from datetime import timedelta

from pathlib import Path

import tomli_w
import tomllib

from maptasker.src.error import error_handler

from maptasker.src.sysconst import ARGUMENTS_FILE, OLD_ARGUMENTS_FILE


from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import ARGUMENTS_FILE, NOW_TIME, OLD_ARGUMENTS_FILE

twenty_four_hours_ago = NOW_TIME - timedelta(hours=25)


# ##################################################################################
# Settings file is corrupt.  Let user know and reset colors to use and program arguments
# ##################################################################################


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


# ##################################################################################
# Write out our runtime settings as a TOML file
# ##################################################################################
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
    guidance = {
        "Guidance": "Modify this file as needed below the entries [program_arguments] and [colors_to_use].  Run 'maptasker -h' for details.",
    }
    # Force file object into a dictionary for json encoding
    try:
        if not isinstance(program_arguments["file"], str):
            program_arguments["file"] = program_arguments["file"].name
    except AttributeError:
        program_arguments["file"] = ""
    # Save dictionaries

    settings = {"program_arguments": program_arguments, "colors_to_use": colors_to_use}

    settings = {"program_arguments": program_arguments, "colors_to_use": colors_to_use, "last_run": PrimeItems.last_run}

    # Write out the guidance for the file.

    with open(new_file, "wb") as settings_file:
        tomli_w.dump(guidance, settings_file)
        settings_file.close()

    # Write out the program arguments in TOML format
    with open(new_file, "ab") as settings_file:
        tomli_w.dump(settings, settings_file)
        settings_file.close()


# ##################################################################################
# Read in the TOML runtime settings
# ##################################################################################
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

    # Read the TOML file
    elif os.path.isfile(new_file):

        with open(new_file, "rb") as f:

            # Setup old date if date last used is not in TROML settings file
            try:
                settings = tomllib.load(f)
                colors_to_use = settings["colors_to_use"]  # Get the colors to use
                program_arguments = settings["program_arguments"]  # Get the program arguments
                try:
                    PrimeItems.last_run = settings["last_run"]  # Get the last run date
                except KeyError:
                    # If this hadn't been previously saved, set it to yesterday (25 hours+).
                    PrimeItems.last_run = twenty_four_hours_ago

                f.close()
            except tomllib.TOMLDecodeError:  # no saved file
                corrupted_file(program_arguments, colors_to_use)

    return program_arguments, colors_to_use


# ##################################################################################
# Save and restore colors to use and program arguments
# ##################################################################################
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
    if to_save:
        save_arguments(program_arguments, colors_to_use, new_file)

    # Restore dictionaries
    else:
        program_arguments, colors_to_use = read_arguments(program_arguments, colors_to_use, old_file, new_file)

    return program_arguments, colors_to_use
