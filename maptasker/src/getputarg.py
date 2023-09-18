#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# getputarg: Save and restore program arguments                                        #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
import json
from pathlib import Path

from maptasker.src.error import error_handler
from maptasker.src.sysconst import ARGUMENTS_FILE


def corrupted_file(program_arguments, colors_to_use):
    error_handler(
        (
            f"'-restore' option... The settings file,  {ARGUMENTS_FILE} is"
            " corrupt!  The old settings can not be restored.  Re-save your"
            " settings."
        ),
        0,
    )
    # Return the error as an entry in our dictionaries for display via te GUI,
    # if needed.
    program_arguments = colors_to_use = {
        "msg": (
            "The settings file is corrupt or not compatible with the new verison of \
            MapTasker!"
            "The old settings can not be restored.  Re-save your settings."
        )
    }
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
        :param to_save: True if this is a save reques6t, False is restore request
        :return: program runtime arguments saved/restored, colors to use saved/restored
    """
    the_file = f"{Path.cwd()}/{ARGUMENTS_FILE}"
    if to_save:
        # Force file object into a dictionary for json encoding
        try:
            if not isinstance(program_arguments["file"], str):
                program_arguments["file"] = program_arguments["file"].name
        except AttributeError:
            program_arguments["file"] = ""
        # Save dictionaries
        list_to_save = [
            colors_to_use,
            program_arguments,
        ]
        with open(the_file, "w") as json_file:
            json.dump(list_to_save, json_file)
            json_file.close()

    # Restore dictionaries
    else:
        try:
            with open(the_file, "r") as f:
                list_to_restore = json.load(f)
                colors_to_use = list_to_restore[0]
                program_arguments = list_to_restore[1]
                f.close()
                # Check for corruption by testing display_detail_level
                try:
                    if isinstance(program_arguments["display_detail_level"], str):
                        program_arguments["display_detail_level"] = int(
                            program_arguments["display_detail_level"]
                        )
                except KeyError:
                    corrupted_file(program_arguments, colors_to_use)

        # Handle file not found condition
        except OSError:
            error_handler("'-r' MapTasker Error: No settings file found to restore!", 0)
            program_arguments = colors_to_use = {
                "msg": "No settings file found to restore!"
            }
        # Handle file format error
        except json.decoder.JSONDecodeError:  # no saved file
            corrupted_file(program_arguments, colors_to_use)

    return program_arguments, colors_to_use
