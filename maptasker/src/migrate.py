#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# migrate: migrate old formatted files to new formats to retain settings                     #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #
import _pickle
import contextlib
import pickle
from os import rename, path
from pathlib import Path

from maptasker.src.error import error_handler
from maptasker.src.getputarg import save_restore_args
from maptasker.src.sysconst import ARGUMENTS_FILE


# #######################################################################################
# Save program arguments
# #######################################################################################
def restore_old_args(file_to_check: Path) -> tuple[dict, dict]:
    """
    Save program arguments
        :param file_to_check: file path/object to restore
        :return: program runtime arguments and colors to use in output
    """

    # Restore dictionaries
    try:
        with open(file_to_check, "rb") as f:
            colormap = pickle.load(f)
            program_args = pickle.load(f)
    except OSError:  # no saved file
        colormap, program_args = process_error(
            (
                "'-r' Error (Restoring Older Settings File): There are no saved items"
                " found to migrate. Prior settings lost."
            ),
        )

    except _pickle.UnpicklingError:  # Format error
        colormap, program_args = process_error(
            (
                f"'-r' Error (Restoring Older Settings File): File {file_to_check} is"
                " corrupt.  Migration ignored.  Prior settings lost."
            ),
        )
    except EOFError:
        colormap, program_args = process_error(
            (
                f"'-r' Error (Restoring Older Settings File): File {file_to_check} is"
                " corrupt.  Migration ignored."
            ),
        )

    f.close()

    return program_args, colormap


def process_error(error_msg: str) -> tuple[dict, dict]:
    """
    Display and log error message and reset colors and program args to empty
        :param error_msg: error to print/log
        :return: empty colormap and program runtime arguments
    """
    error_handler(error_msg, 0)
    return {}, {}


# #######################################################################################
# Migrate from old filename/format to new for saved runtime arguments
# #######################################################################################
def migrate(primary_items: dict) -> dict:
    """
    Migrate from old filename/format to new for saved runtime arguments
      We have changed from using the unsecure "pickle" code to using "json"
      to save the program arguments and colors
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :return: nothing
    """
    old_arguments_file = ".MapTasker_arguments.txt"
    file_to_check = Path(f"{old_arguments_file}")

    dir_path = Path.cwd()
    # If we have an old formatted argument file, convert it to new old name
    with contextlib.suppress(FileNotFoundError):
        rename(f"{dir_path}/.arguments.txt", f"{dir_path}/{old_arguments_file}")

    # Now, if we have the old binary file saved via pickle, convert it to JSON
    if file_to_check.is_file():
        primary_items["program_arguments"], primary_items["colors_to_use"] = (
            restore_old_args(file_to_check)
        )
        # Save as JSON file.  We don't care about the returned values
        _, _ = save_restore_args(
            primary_items["colors_to_use"], primary_items["program_arguments"], True
        )
        # Now delete the old file
        file_to_check.unlink()

    else:
        file_to_check = f"{dir_path}/{ARGUMENTS_FILE}"
        if path.exists(file_to_check):
            # Get the current arguments and colors
            temp_args, temp_colormap = save_restore_args({}, {}, False)
            # Reset any "msg" left over from previous run
            with contextlib.suppress(KeyError):
                if temp_colormap["msg"] or temp_args["msg"]:
                    temp_args["msg"] = temp_colormap["msg"] = ""
                    _, _ = save_restore_args(temp_colormap, temp_args, True)
    return primary_items
