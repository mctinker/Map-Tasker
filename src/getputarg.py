#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# getputarg: Save and restore program arguments                                              #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #
import json

from maptasker.src.sysconst import ARGUMENTS_FILE
from maptasker.src.sysconst import logger
from pathlib import Path


# #######################################################################################
# Save and restore colors to use and program arguments
# #######################################################################################
def save_restore_args(
    to_save: bool, colormap: dict, temp_args: dict
) -> tuple[dict, dict]:
    """
    Save and restore colors to use and program arguments
        :param to_save: True if we are to save the info, False to restore the info
        :param colormap: colors to use in output
        :param temp_args: runtime arguments
        :return: colors and runtime arguments saved/restored
    """
    the_file = f"{Path.cwd()}/{ARGUMENTS_FILE}"
    if to_save:
        # Save dictionaries
        list_to_save = [colormap, temp_args]
        with open(the_file, "w") as f:
            json.dump(list_to_save, f)
            f.close()
    else:
        # Restore dictionaries
        try:
            with open(the_file, "r") as f:
                list_to_restore = json.load(f)
                colormap = list_to_restore[0]
                temp_args = list_to_restore[1]
                f.close()
        # Handle file not found condition
        except OSError:
            error_msg = "'-r' Error: No settings file found to restore!"
            print(error_msg)
            logger.debug(error_msg)
            temp_args = colormap = {"msg": "No settings file found to restore!"}
        # Handle file format error
        except json.decoder.JSONDecodeError:  # no saved file
            error_msg = f"'-r' Error: The settings file,  {ARGUMENTS_FILE} is corrupt!"
            print(error_msg)
            logger.debug(error_msg)
            temp_args = colormap = {
                "msg": "The settings file is corrupt!  Re-save your settings."
            }

    return temp_args, colormap
