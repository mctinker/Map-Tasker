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

import os
from tkinter import font

from maptasker.src.colrmode import set_color_mode
from maptasker.src.lineout import LineOut
from maptasker.src.nameattr import get_tk
from maptasker.src.primitem import PrimeItems
from maptasker.src.proginit import get_data_and_output_intro


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
def ping_android_device(self, backup_info: str) -> tuple[bool, str]:  # noqa: ANN001
    # The following should return a list: [ip_address:port_number, file_location]
    """
    Pings an Android device
    Args:
        backup_info: str - Backup information in ip_address:port_number,file_location format
    Returns:
        tuple[bool, str] - A tuple containing a bool for success/failure and a error message string
                    - If failure, returns True and a blank strings, else False and ip addr and location
    Processing Logic:
    - Splits the backup_info string into ip_address, port_number, and file_location
    - Validates the IP address, port number, and file location
    - Pings the IP address to check connectivity
    - Returns a tuple indicating success/failure and any error message
    """
    temp_info = backup_info.split(",")
    temp_ip = temp_info[0].split(":")

    # Validate IP Address
    temp_ipaddr = temp_ip[0].split(".")
    if len(temp_ipaddr) < 4:
        self.backup_error(f"Invalid IP Address: {temp_ip[0]}.  Try again.")
        return True, "", ""
    for item in temp_ipaddr[0]:
        if not item.isdigit():
            self.backup_error(
                f"Invalid IP Address: {temp_ip[0]}.  Try again.",
            )
            return True, "", ""
    # Verify that the host IP (temp_ip[0]) is reachable:
    self.display_message_box(
        f"Pinging address {temp_ip[0]}.  Please wait...",
        True,
    )
    self.update()  # Force a window refresh.
    # Ping IP address.
    response = os.system("ping -c 1 -t50 > /dev/null " + temp_ip[0])  # noqa: S605
    if response != 0:
        self.backup_error(
            f"{temp_ip[0]} is not reachable (error {response}).  Try again.",
        )
        return True, "", ""
    self.display_message_box(
        "Ping successful.",
        False,
    )
    # Validate port number
    if len(temp_ip) == 1 or not temp_ip[1].isdigit:
        self.backup_error(
            f"Invalid port number: {temp_ipaddr[1]}.  Try again.",
        )
        return True, "", ""

    # Validate file location
    if len(temp_info) < 2 or temp_info[1] == "":
        self.backup_error("File location is missing.  Try again.")
        return None

    # All is well so far...
    self.backup_file_http = temp_info[0]
    self.backup_file_location = temp_info[1]

    # Empty message = good to go...no error.
    self.backup_error("")
    return False, self.backup_file_http, self.backup_file_location
