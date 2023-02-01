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
import pickle
from routines.sysconst import ARGUMENTS_FILE
from routines.sysconst import logger
from pathlib import Path


# #######################################################################################
# Save program arguments
# #######################################################################################
def save_restore_args(to_save, colormap, temp_args):
    dir_path = Path.cwd()
    if to_save:
        # Save dictionaries
        with open(f"{dir_path}/{ARGUMENTS_FILE}", "wb") as f:
            pickle.dump(colormap, f)
            pickle.dump(temp_args, f)

    else:
        # Restore dictionaries
        try:
            with open(f"{dir_path}/{ARGUMENTS_FILE}", "rb") as f:
                colormap = pickle.load(f)
                temp_args = pickle.load(f)
        except Exception as e:  # no saved file
            error_msg = "'-r' Error: There are no saved items found to restore!"
            print(error_msg)
            logger.debug(error_msg)

    return temp_args, colormap
