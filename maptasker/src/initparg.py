#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# runcli: intialize command line interface arguments for MapTasker                     #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
from maptasker.src.config import BACKUP_FILE_HTTP, BACKUP_FILE_LOCATION
from maptasker.src.sysconst import FONT_TO_USE


#######################################################################################
# Initialize Program runtime arguments to default values
# ##################################################################################
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
        "bold": False,  # Display Project/Profile?Task/Scene names in bold text
        "highlight": False,  # Highlight Project/Profile?Task/Scene names
        "italicize": False,  # Italicise Project/Profile?Task/Scene names
        "underline": False,  # Underline Project/Profile?Task/Scene names
        "appearance_mode": "system",  # Appearance mode: "system", "dark", or "light"
        "indent": 4,
    }
