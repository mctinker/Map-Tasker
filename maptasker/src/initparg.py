#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# initparg: intialize command line interface/runtime arguments for MapTasker           #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
from maptasker.src.config import BACKUP_FILE_HTTP, BACKUP_FILE_LOCATION, OUTPUT_FONT


#######################################################################################
# Initialize Program runtime arguments to default values
# ##################################################################################
# Command line parameters
def initialize_runtime_arguments() -> dict:
    """
    Initialize the program's runtime arguments...as a dictionary of options.
    The key must be the same name as the key in PrimeItems.program_arguments.
        :return: runtime arguments in dictionary
    """
    return {
        "appearance_mode": "system",  # Appearance mode: "system", "dark", or "light"
        "backup_file_http": BACKUP_FILE_HTTP,  # Port for Android-based Tasker server, to get backup file from
        "backup_file_location": BACKUP_FILE_LOCATION,  # Location of the backup file to grab from Android device
        "bold": False,  # Display Project/Profile?Task/Scene names in bold text
        "debug": False,  # Run in debug mode (create log file)
        "directory": False,  # Display directory
        "display_detail_level": 4,  # Display detail level
        "preferences": False,  # Display Tasker's preferences
        "conditions": False,  # Display Profile and Task conditions
        "taskernet": False,  # Display TaskerNet information
        "fetched_backup_from_android": False,  # Backup file was fetched from Android device
        "file": "",  # If we are re-running, then this is the file to re-use
        "font": OUTPUT_FONT,  # Font to use in the output
        "gui": False,  # Use the GUI to get the runtime and color options
        "highlight": False,  # Highlight Project/Profile?Task/Scene names
        "indent": 4,  # Backup file was fetched from Android device
        "italicize": False,  # Italicise Project/Profile?Task/Scene names
        "outline": False,  # Outline Project/Profile?Task/Scene names
        "rerun": False,  # Is this a GUI re-run?
        "restore": False,  # Restore settings from a previous run
        "runtime": False,  # Display the runtime arguments/settings
        "save": False,  # Save settings for reuse
        "single_profile_name": "",  # Display single Profile name only
        "single_project_name": "",  # Display single Project name only
        "single_task_name": "",  # Display single Task name only
        "twisty": False,  # Add Task twisty "▶︎" clickable icons for Task details
        "underline": False,  # Underline Project/Profile?Task/Scene names
    }
