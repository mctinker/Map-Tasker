#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# runcli: intialize command line interface arguments for MapTasker                           #
#                                                                                            #
# Add the following statement (without quotes) to your Terminal Shell configuration file     #
#  (BASH, Fish, etc.) to eliminate the runtime msg:                                          #
#  DEPRECATION WARNING: The system version of Tk is deprecated ...                           #
#  "export TK_SILENCE_DEPRECATION = 1"                                                       #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #
from maptasker.src.sysconst import FONT_TO_USE
from maptasker.src.config import BACKUP_FILE_HTTP
from maptasker.src.config import BACKUP_FILE_LOCATION


#######################################################################################
# Initialize Program runtime arguments to default values
# #######################################################################################
# Command line parameters
def initialize_runtime_arguments() -> dict:
    """
    Initialize the program's runtime arguments...as a dictionary of options
        :return: runtime arguments in dictionary
    """
    return {
        "display_detail_level": 3,  # Display detail level
        "single_task_name": "",  # Display single Task name only
        "single_profile_name": "",  # Display single Profile name only
        "single_project_name": "",  # Display single Project name only
        "display_profile_conditions": False,  # Display Profile and Task conditions
        "display_preferences": False,  # Display Tasker's preferences
        "display_taskernet": False,  # Display TaskerNet information
        "debug": False,  # Run in debug mode (create log file)
        "font_to_use": FONT_TO_USE,  # The output font to use, preferably monospaced
        "gui": False,  # Use the GUI to get the runtime and color options
        "rerun": False,  # Is this a GUI re-run?
        "file": "",  # If we are re-running, then this is the file to re-use
        "backup_file_http": (
            BACKUP_FILE_HTTP
        ),  # Port for Android-based Tasker server, to get backup file from
        "backup_file_location": (
            BACKUP_FILE_LOCATION
        ),  # Location of the backup file to grab from Android device
        "fetched_backup_from_android": (
            False
        ),  # Backup file was fetched from Android device
        "twisty": False,  # Add Task twisty "▶︎" clickable icons for Task details
        "directory": False,  # Display directory
    }
