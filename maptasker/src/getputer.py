"""Read/write the settings file"""

#! /usr/bin/env python3

#                                                                                      #
# getputer: Save and restore program arguments                                         #
#                                                                                      #
from __future__ import annotations

import contextlib
import os
import pickle
import tempfile
import tomllib
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import tomli_w

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import BinaryIO

from maptasker.src.colrmode import set_color_mode
from maptasker.src.error import error_handler
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.maputil2 import log_startup_values, translate_string
from maptasker.src.maputils import reset_named_objects
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import (
    ARGUMENT_NAMES,
    ARGUMENTS_FILE,
    NOW_TIME,
    SYSTEM_ARGUMENTS,
    SYSTEM_SETTINGS_FILE,
    TRANSIENT_ARGUMENTS,
    logger,
)

twenty_four_hours_ago = NOW_TIME - timedelta(hours=25)


# Write a settings file in one indivisible step
def write_atomically(target_file: str, write_settings: Callable[[BinaryIO], None]) -> None:
    """Write a settings file via a temporary file, then swap it into place with os.replace().

    Writing straight to the settings file leaves a window -- two of them, in the case of the
    TOML file, which used to be truncated ('wb') and then reopened to be appended to ('ab') --
    in which what is on disk is empty or half-written.  Any read landing in that window
    (another MapTasker instance starting up, since every run saves settings) gets no
    'program_arguments' table and silently falls back to defaults, and a crash inside the
    window loses the user's settings for good.

    os.replace() is atomic on POSIX and Windows, so a reader sees either the complete old
    file or the complete new one -- never a partial one.  If write_settings raises, the
    temporary file is discarded and the previous settings file is left untouched.

    Args:
        target_file: path of the settings file to end up with.
        write_settings: called with the open binary temp file; does the actual writing.
    """
    target = Path(target_file)
    # The temp file must share a filesystem with the target for os.replace to be atomic,
    # so put it in the same directory rather than the system temp area.
    temp_fd, temp_name = tempfile.mkstemp(dir=target.parent or Path(), prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(temp_fd, "wb") as temp_file:
            write_settings(temp_file)
            # Flush all the way to disk before the swap: os.replace only orders the rename,
            # not the data behind it.
            temp_file.flush()
            os.fsync(temp_file.fileno())
        # Replacing the file replaces its permissions too, and mkstemp deliberately makes
        # owner-only (0600) files.  Carry the existing file's mode over so saving settings
        # doesn't quietly change who can read them.
        with contextlib.suppress(OSError):
            os.chmod(temp_name, target.stat().st_mode & 0o7777)
        os.replace(temp_name, target)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temp_name)
        raise


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
        "msg": "The settings file is corrupt or not compatible with the new version of MapTasker!  The old settings can not be restored.  A new default settings file has been saved.",
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
    # In the event we set the single Project name due to a single Task or Profile name,
    # then reset it before we do a save and exit.
    reset_named_objects()

    guidance = {
        "Guidance": "Modify this file as needed below the entries [program_arguments] and [colors_to_use].  Run 'maptasker -h' for details.",
    }

    # Make sure apikey is hidden
    program_arguments["ai_apikey"] = "Hidden"

    # Never persist what this particular run happens to be doing.  The AI analysis save
    # below happens while ai_analyze is still true (ai_analyze_event saves right before it
    # runs the analysis), so without this the flag would stay true in the settings file for
    # every session that follows.
    for argument, resting_value in TRANSIENT_ARGUMENTS.items():
        program_arguments[argument] = resting_value

    # Force file object into a dictionary for json encoding
    try:
        if not isinstance(program_arguments["file"], str):
            program_arguments["file"] = program_arguments["file"].name
    except AttributeError:
        program_arguments["file"] = ""

    # Separate user from system settings
    user_args = {}
    sys_args = {}
    project_translated = translate_string("Project:")
    profile_translated = translate_string("Profile:")
    task_translated = translate_string("Task:")
    for argument in ARGUMENT_NAMES:
        # TOML chokes on 'None" values.
        try:
            if program_arguments[argument] is None:
                logger.debug(f"{argument} is None.  Fix it!")
                program_arguments[argument] = ""
        except KeyError:
            program_arguments[argument] = ""

        # Make sure we don't save an item name of "None" in another language
        if PrimeItems.program_arguments["language"] != "English":
            if translate_string(program_arguments[argument] == "None"):
                program_arguments[argument] = ""
            # Make sure we don't save translated prefixes
            if isinstance(program_arguments[argument], str):
                if program_arguments[argument].startswith(project_translated):
                    program_arguments[argument] = program_arguments[argument].replace(f"{project_translated} ", "")
                elif program_arguments[argument].startswith(profile_translated):
                    program_arguments[argument] = program_arguments[argument].replace(f"{profile_translated}", "")
                elif program_arguments[argument].startswith(task_translated):
                    program_arguments[argument] = program_arguments[argument].replace(f"{task_translated} ", "")

        # Okay, now capture the argument.
        if argument in SYSTEM_ARGUMENTS:
            sys_args[argument] = program_arguments[argument]
        else:
            user_args[argument] = program_arguments[argument]

    # Save dictionaries.  The guidance goes in the same write as everything else: two
    # separate writes is exactly what used to leave a guidance-only file on disk for any
    # reader (or crash) that landed between them.
    settings = {
        **guidance,
        "program_arguments": dict(sorted(user_args.items())),  # Sort the program args first.
        "colors_to_use": dict(sorted(colors_to_use.items())),  # Sort the colors next.
        "last_run": PrimeItems.last_run,
    }

    # Write out the guidance, user program arguments and colors in TOML format.
    logger.info("Saving settings file with program args and colors...")
    try:
        write_atomically(new_file, lambda settings_file: tomli_w.dump(settings, settings_file))
    except TypeError as e:
        # The previous settings file is still intact -- write_atomically threw away the
        # partial one -- so the user loses this save, not everything saved before it.
        logger.debug(f"getputer tomli failure: {e}")
        print(f"getputer tomli failure: {e}...one or more settings is 'None'!")

    # Write out the system program arguments (e.g. window positions) in PICKLE format.
    logger.info("Saving system args file...")
    write_atomically(SYSTEM_SETTINGS_FILE, lambda settings_file: pickle.dump(sys_args, settings_file))


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
    program_arguments = ""
    colors_to_use = ""
    with open(new_file, "rb") as f:
        # Setup old date if date last used is not in TROML settings file.  Catch all possible errors with TOML file.
        try:
            # Colors to use
            settings = tomllib.load(f)
            try:
                colors_to_use = settings["colors_to_use"]  # Get the colors to use
            except KeyError:
                colors_to_use = set_color_mode(
                    "",
                )  # If this hadn't been previously saved, set it to blank

            # Get program arguments
            try:
                program_arguments = settings["program_arguments"]
                # Start log. file if debug is on.
                if program_arguments["debug"]:
                    log_startup_values()
            except KeyError:
                # A settings file with no [program_arguments] table at all.  Saves are
                # atomic now, so this is either a hand-edited file or one left half-written
                # by a version from before that -- worth saying so rather than quietly
                # coming up with defaults and then saving them back over the file.
                logger.error(f"No [program_arguments] found in {new_file}.  Falling back to default settings.")
                program_arguments = initialize_runtime_arguments()
            try:
                PrimeItems.last_run = settings["last_run"]  # Get the last run date
            except KeyError:
                # If this hadn't been previously saved, set it to yesterday (25 hours+).
                PrimeItems.last_run = twenty_four_hours_ago

            f.close()
        except tomllib.TOMLDecodeError:  # no saved file
            program_arguments, colors_to_use = corrupted_file(
                program_arguments,
                colors_to_use,
            )

    return program_arguments, colors_to_use


# Read in the TOML runtime settings
def read_arguments(
    program_arguments: dict,
    colors_to_use: dict,
    new_file: str,
) -> None:
    """
    Reads the program arguments, colors to use, old file, and new file.

    Parameters:
        program_arguments (dict): A dictionary containing program arguments.
        colors_to_use (dict): A dictionary containing colors to use.
        new_file (str): The path to the new file.

    Returns:
        None: This function does not return anything.
    """
    sys_file = f"{Path.cwd()}{PrimeItems.slash}{SYSTEM_SETTINGS_FILE}"

    # Read the user settings TOML file
    if os.path.isfile(new_file):
        program_arguments, colors_to_use = read_toml_file(new_file)
    else:
        program_arguments = PrimeItems.program_arguments
        colors_to_use = set_color_mode(program_arguments["appearance_mode"])

    # Read the window positions from the PICKLE file
    if os.path.isfile(sys_file):
        try:
            with open(sys_file, "rb") as sys_settings_file:
                sys_args = pickle.load(sys_settings_file)  # noqa: S301
        except (pickle.UnpicklingError, EOFError, AttributeError, ImportError, IndexError) as e:
            # Only window positions and the like live here, so a damaged file is no reason
            # to refuse to start -- carry on with the defaults already in program_arguments.
            logger.error(f"Could not read {sys_file}: {e}.  Using default window positions.")
        else:
            for key, value in sys_args.items():
                program_arguments[key] = value

    # A run always starts out not doing any of the transient things, whatever a settings
    # file written by an older version (or edited by hand) claims.
    for argument, resting_value in TRANSIENT_ARGUMENTS.items():
        if isinstance(program_arguments, dict) and program_arguments.get(argument) != resting_value:
            logger.info(f"Ignoring saved '{argument}' and starting at {resting_value}.")
            program_arguments[argument] = resting_value

    return program_arguments, colors_to_use


# Save and restore colors to use and program arguments
def save_restore_args(
    program_arguments: dict,
    colors_to_use: dict,
    to_save: bool = True,
) -> tuple[dict, dict]:
    """
    Save and restore colors to use and program arguments
        :param program_arguments: program runtime arguments to save or restore into
        :param colors_to_use: color dictionary to save or restore into
        :param to_save: True if this is a save request, False is restore request
        :return: program runtime arguments saved/restored, colors to use saved/restored
    """
    our_path = os.getcwd()
    new_file = f"{our_path}{PrimeItems.slash}{ARGUMENTS_FILE}"

    # Saving?
    if to_save:
        save_arguments(program_arguments, colors_to_use, new_file)

    # Restore dictionaries
    else:
        program_arguments, colors_to_use = read_arguments(
            program_arguments,
            colors_to_use,
            new_file,
        )

    return program_arguments, colors_to_use
