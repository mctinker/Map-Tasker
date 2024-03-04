"""Utilities used by GUI
"""

#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# guiutil: Utilities used by GUI                                                       #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
# #################################################################################### #
from __future__ import annotations

import contextlib
import os
from tkinter import font
from typing import TYPE_CHECKING

from maptasker.src.colrmode import set_color_mode
from maptasker.src.lineout import LineOut
from maptasker.src.maputils import get_pypi_version, http_request, validate_ip_address, validate_port
from maptasker.src.nameattr import get_tk
from maptasker.src.primitem import PrimeItems
from maptasker.src.proginit import get_data_and_output_intro
from maptasker.src.sysconst import CHANGELOG_FILE, NOW_TIME, VERSION

if TYPE_CHECKING:
    from datetime import datetime


# ##################################################################################
# Make sure the single named item exists...that it is a valid name
# ##################################################################################
def valid_item(the_name: str, element_name: str, debug: bool, appearance_mode: str) -> bool:
    """
    Checks if an item name is valid
    Args:
        the_name: String - Name to check
        element_name: String - Element type being checked
        debug: boolean - GUI debug mode True or False
        appearance_mode: String - Light/Dark/System
    Returns:
        Boolean - Whether the name is valid
    Processing Logic:
    - Initialize temporary primary items object
    - Get backup xml data and root elements
    - Match element type and get corresponding root element
    - Check if item name exists by going through all names in root element
    """

    # We need to get all tasker root xml items from the backup xml file.
    # To do so, we need to go through initializing a temporary PrimaryItems object
    # Set up just enough PrimeItems variables to validate name.
    if not PrimeItems.file_to_get:
        PrimeItems.file_to_get = "backup.xml" if debug else ""
    PrimeItems.program_arguments["debug"] = debug
    PrimeItems.colors_to_use = set_color_mode(appearance_mode)
    PrimeItems.output_lines = LineOut()

    return_code = get_data_and_output_intro()

    # Did we get an error reading the backup file?
    if return_code > 0:
        if return_code == 6:
            PrimeItems.error_msg = "Cancel button pressed."
        PrimeItems.error_code = 0
        return False

    # Set up for name checking
    # Find the specific item and get it's root element
    root_element_choices = {
        "Project": PrimeItems.tasker_root_elements["all_projects"],
        "Profile": PrimeItems.tasker_root_elements["all_profiles"],
        "Task": PrimeItems.tasker_root_elements["all_tasks"],
    }
    root_element = root_element_choices[element_name]

    # See if the item exists by going through all names
    return any(root_element[item]["name"] == the_name for item in root_element)


# ##################################################################################
# Get all monospace fonts from TKInter
# ##################################################################################
def get_mono_fonts() -> None:
    """
    Returns a dictionary of fixed-width fonts
    Args:
        self: The class instance
    Returns:
        dict: A dictionary of fixed-width fonts and their family names
    - Get all available fonts from the font module
    - Filter fonts to only those with a fixed width
    - Build a dictionary with font name as key and family as value
    """
    # Make sure we have the Tkinter window/root
    get_tk()
    fonts = [font.Font(family=f) for f in font.families()]
    return {f.name: f.actual("family") for f in fonts if f.metrics("fixed")}


# ##################################################################################
# Build list of all available monospace fonts
# ##################################################################################
def get_monospace_fonts() -> dict:
    """
    Returns monospace fonts from system fonts.
    Args:
        fonts: All system fonts
    Returns:
        font_items: List of monospace fonts
        res: List containing Courier or default Monaco font
    - Get all system fonts
    - Filter fonts to only include monospace fonts excluding Wingdings
    - Find Courier font in list and set as res
    - If Courier not found, set Monaco as default res
    - Return lists of monospace fonts and Courier/Monaco font
    """
    fonts = get_mono_fonts()
    font_items = ["Courier"]
    font_items = [value for value in fonts.values() if "Wingdings" not in value]
    # Find which Courier font is in our list and set.
    res = [i for i in font_items if "Courier" in i]
    # If Courier is not found for some reason, default to Monaco
    if not res:
        res = [i for i in font_items if "Monaco" in i]
    return font_items, res


# ##################################################################################
# Ping the Android evice to make sure it is reachable.
# ##################################################################################
def ping_android_device(self, ip_address: str, port_number: str) -> bool:  # noqa: ANN001
    # The following should return a list: [ip_address:port_number, file_location]
    """
    Pings an Android device
    Args:
        ip_address: str - TCP IP address of the Android device
        port_number: str - TCP port number of the Android device
    Return:
        Error: True if error, false if all is good.
    Processing Logic:
    - Splits the backup_info string into ip_address, port_number, and file_location
    - Validates the IP address, port number, and file location
    - Pings the IP address to check connectivity
    - Returns a tuple indicating success/failure and any error message
    """
    # Validate IP Address
    if validate_ip_address(ip_address):
        # Verify that the host IP is reachable:
        self.display_message_box(
            f"Pinging address {ip_address}.  Please wait...",
            True,
        )
        self.update()  # Force a window refresh.

        # Ping IP address.
        response = os.system("ping -c 1 -t50 > /dev/null " + ip_address)  # noqa: S605
        if response != 0:
            self.backup_error(
                f"{ip_address} is not reachable (error {response}).  Try again.",
            )
            return False
        self.display_message_box(
            "Ping successful.",
            True,
        )
    else:
        self.backup_error(
            f"Invalid IP address: {ip_address}.  Try again.",
        )
        return False

    # Validate port number
    if validate_port(ip_address, port_number) != 0:
        self.backup_error(
            f"Invalid Port number: {port_number}.  Try again.",
        )
        return False

    # Valid IP Address...good ping.
    return True


# ##################################################################################
# Clear all buttons associated with fetching the backup file from Android device
# ##################################################################################
def clear_android_buttons(self) -> None:  # noqa: ANN001
    """
    Clears android device configuration buttons and displays backup button
    Args:
        self: The class instance
    Returns:
        None
    - Destroys IP, port, file entry and label widgets
    - Destroys get backup button
    - Displays new backup button with callback to get_backup_event method"""

    # Each element to be destoryed needs a suppression since any one suppression will be triggered if any one of
    # the elements is not defined.
    with contextlib.suppress(AttributeError):
        self.ip_entry.destroy()
    with contextlib.suppress(AttributeError):
        self.port_entry.destroy()
    with contextlib.suppress(AttributeError):
        self.file_entry.destroy()
    with contextlib.suppress(AttributeError):
        self.ip_label.destroy()
    with contextlib.suppress(AttributeError):
        self.port_label.destroy()
    with contextlib.suppress(AttributeError):
        self.file_label.destroy()
    with contextlib.suppress(AttributeError):
        self.get_backup_button.destroy()
    with contextlib.suppress(AttributeError):
        self.cancel_entry_button.destroy()
    with contextlib.suppress(AttributeError):
        self.list_files_button.destroy()
    with contextlib.suppress(AttributeError):
        self.label_or.destroy()
    with contextlib.suppress(AttributeError):
        self.filelist_label.destroy()
    with contextlib.suppress(AttributeError):
        self.filelist_option.destroy()
    with contextlib.suppress(AttributeError):
        self.list_files_query_button.destroy()

    self.display_backup_button("Get XML from Android Device", "#246FB6", "#6563ff", self.get_backup_event)


# ##################################################################################
# Compare two versions and return True if version2 is greater than version1.
# ##################################################################################
def is_version_greater(version1: str, version2: str) -> bool:
    """
    This function checks if version2 is greater than version1.

    Args:
        version1: A string representing the first version in the format "major.minor.patch".
        version2: A string representing the second version in the format "major.minor.patch".

    Returns:
        True if version2 is greater than version1, False otherwise.
    """

    # Split the versions by "."
    v1_parts = [int(x) for x in version1.split(".")]
    v2_parts = [int(x) for x in version2.split(".")]

    # Iterate through each part of the version
    for i in range(min(len(v1_parts), len(v2_parts))):
        if v1_parts[i] < v2_parts[i]:
            return True
        if v1_parts[i] > v2_parts[i]:
            return False

    # If all parts are equal, check length
    return len(v2_parts) > len(v1_parts)


# ##################################################################################
# Checks if 24 hours have passed since the given previous date.
# ##################################################################################
def is_more_than_24hrs(input_datetime: datetime) -> bool:
    """Checks if the input datetime is more than 24 hours ago.
    Parameters:
        - input_datetime (datetime): The datetime to be checked.
    Returns:
        - bool: True if input datetime is more than 24 hours ago, False otherwise.
    Processing Logic:
        - Calculate seconds in 24 hours.
        - Get current datetime.
        - Check if difference between current datetime and input datetime is greater than 24 hours.
        - Return result as boolean."""
    twenty_four_hours = 86400  # seconds in 24 hours
    return (NOW_TIME - input_datetime).total_seconds() > twenty_four_hours


# ##################################################################################
# Get Pypi version and return True if it is newer than our current version.
# ##################################################################################
def is_new_version() -> bool:
    """
    Check if the new version is available
    Args:
        self: The class instance
    Returns:
        bool: True if new version is available, False if not"""
    # Check if newer version of our code is available on Pypi.
    # if is_more_than_24hrs(PrimeItems.last_run):  # Only check every 24 hours.
    pypi_version_code = get_pypi_version()
    if pypi_version_code:
        pypi_version = pypi_version_code.split("==")[1]
        PrimeItems.last_run = NOW_TIME  # Update last run to now since we are doing the check.
        return is_version_greater(VERSION, pypi_version)
    return False


# ##################################################################################
# List the XML files on the Android device
# ##################################################################################
def get_list_of_files(ip_address: str, ip_port: str, file_location: str) -> tuple:
    """Get list of files from given IP address.
    Parameters:
        - ip_address (str): IP address to connect to.
        - ip_port (str): Port number to connect to.
        - file_location (str): Location of the file to retrieve.
    Returns:
        - tuple: Return code and list of file locations.
    Processing Logic:
        - Retrieve file contents using http_request.
        - If return code is 0, split the decoded string into a list and return.
        - Otherwise, return error with empty string."""

    # Get the contents of the file.
    return_code, file_contents = http_request(ip_address, ip_port, file_location, "maplist", "?xml")

    # If good return code, get the list of XML file locations into a list and return.
    if return_code == 0:
        decoded_string = (file_contents.decode("utf-8")).split(",")
        # Strip off the count field
        for num, item in enumerate(decoded_string):
            temp_item = item[:-3]  # Drop last 3 characters
            decoded_string[num] = temp_item.replace("/storage/emulated/0", "")
        # Remove items that are in the trash
        final_list = [item for item in decoded_string if ".Trash" not in item]
        return 0, final_list

    # Otherwise, return error
    return return_code, file_contents


# ##################################################################################
# Write out the changelog
# ##################################################################################
def create_changelog() -> None:
    """Create changelog file."""
    # TODO Change this 'changelog' with each release!
    changelog = '''
Version 3.1.2 Change Log
- Added: Display this Changelog in the GUI.
- Fixed: Icons in Profile and Task names are invalid due to bad encoding.
- Fixed: GUI "?" left in the window after "Get Backup from Android Device" completed.
- Fixed: Check for Update now working in the GUI.
- Changed: All references to "Backup" in the GUI have been changed to "XML".
'''  # noqa: Q001
    with open(CHANGELOG_FILE, "w") as changelog_file:
        changelog_file.write(changelog)

# ##################################################################################
# Read the change log file, add it to the messages to be displayed and then remove it.
# ##################################################################################
def check_for_changelog(self) -> None:  # noqa: ANN001
    """Function to check for a changelog file, read its contents, and remove the file if it exists.
    Parameters:
        - self (object): The object calling the function.
    Returns:
        - None: The function does not return anything.
    Processing Logic:
        - Check if changelog file exists.
        - Read the contents of the file.
        - Append each line to the message variable.
        - Remove the changelog file."""
    if os.path.isfile(CHANGELOG_FILE):
        with open(CHANGELOG_FILE) as changelog_file:
            lines = changelog_file.readlines()
            for line in lines:
                self.message = self.message + line + "\n"
        os.remove(CHANGELOG_FILE)
