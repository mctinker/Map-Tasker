#! /usr/bin/env python3
import _pickle
import contextlib

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
import pickle
from os import rename
from pathlib import Path

from maptasker.src.getputarg import save_restore_args
from maptasker.src.error import error_handler


# #######################################################################################
# Save program arguments
# #######################################################################################
def restore_old_args(file_to_check: Path) -> tuple[dict, dict]:
    """
    Save program arguments
        :param file_to_check: file path/object to restore
        :return: program runtime arguments and colors to use in output
    """
    colormap = program_args = {}

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
    Disspaly and log error message and reset colors and program args to empty
        :param error_msg: error to print/log
        :return: empty colormap and program runtime arguments
    """
    error_handler(error_msg, 0)
    return {}, {}


# #######################################################################################
# Migrate from old filename/format to new for saved runtime arguments
# #######################################################################################
def migrate() -> None:
    """
    Migrate from old filename/format to new for saved runtime arguments
      We have changed from using the unsecure "pickle" code to using "json"
      to save the program arguments and colors
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
        program_args, colormap = restore_old_args(file_to_check)
        # Save as JSON file
        nada, nada = save_restore_args(True, colormap, program_args)
        # Now delete the old file
        file_to_check.unlink()

    return
