"""Utilities used by GUI"""

#! /usr/bin/env python3

#                                                                                      #
# guiutil: Utilities used by GUI                                                       #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #

from __future__ import annotations

import contextlib
import json
import os
import platform
import sys
import time
from tkinter import font
from typing import TYPE_CHECKING, Callable

import customtkinter as ctk
import darkdetect
from PIL import Image

from maptasker.src.colrmode import set_color_mode
from maptasker.src.getids import get_ids
from maptasker.src.lineout import LineOut
from maptasker.src.maputils import (
    append_item_to_list,
    get_pypi_version,
    http_request,
    validate_ip_address,
    validate_port,
    validate_xml_file,
)
from maptasker.src.nameattr import get_tk
from maptasker.src.primitem import PrimeItems
from maptasker.src.profiles import get_profile_tasks
from maptasker.src.proginit import get_data_and_output_intro
from maptasker.src.sysconst import (
    ANALYSIS_FILE,
    ARGUMENT_NAMES,
    CHANGELOG_FILE,
    CHANGELOG_JSON_FILE,
    ERROR_FILE,
    KEYFILE,
    NOW_TIME,
    OPENAI_MODELS,
    VERSION,
    Colors,
    logger,
)

if TYPE_CHECKING:
    from datetime import datetime

    import defusedxml

bar = "│"
right_arrow_corner_down = "╰"
right_arrow_corner_up = "╯"
left_arrow_corner_down = "╭"
left_arrow_corner_up = "╮"
right_arrow = "►"
left_arrow = "◄"
straight_line = "─"
angle = "└─ "
all_objects = "Display all Projects, Profiles, and Tasks."

# TODO Change this 'changelog' with each release!  New lines (\n) must be added.
CHANGELOG = """
Version 6.0 - Change Log\n
### Added\n
- Added: The GUI 'views' now have a 'Top' and 'Bottom' button for quick navigation within the GUI views.\n
- Added: Allow the runtime option '-debug' to be carried into the GUI.\n
- Added: Ai analysis model 'llama3.2' has been added.\n
- Added: Python 3.13 fully supported.\n
### Changed\n
- Changed: The Diagram view connectors have been shifted to the left as much as possible so that more can be seen within the view window.\n
### Fixed\n
- Fixed: The 'IA' Diagram button setting is being reversed (off rather than on, and vice versa) when restored during GUI initialization.\n
### Known Issues\n
- Open Issue: The background color may not be correct if using the Firefox browser in light mode if the system default is dark mode.\n
- Open Issue: The Map view Project/Profile/Task/Scene names with icons are not displaying correctly in the Map view if using highlighting (underline, etc.).\n
"""

default_font_size = 14


# Make sure the single named item exists...that it is a valid name
def valid_item(self, the_name: str, element_name: str, debug: bool, appearance_mode: str) -> bool:  # noqa: ANN001
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
    if the_name == "None":
        return True
    # Set our file to get the file from the local drive since it had previously been pulled from the Android device.
    # Setting PrimeItems.program_arguments["file"] will be used in get_xml() and won't prompt for file if it exists.
    filename_location = self.android_file.rfind(PrimeItems.slash) + 1
    if filename_location != 0:
        PrimeItems.program_arguments["file"] = self.android_file[filename_location:]
    elif self.file:
        PrimeItems.program_arguments["file"] = self.file
    else:
        _ = self.prompt_and_get_file(self.debug, self.appearance_mode)

    # Get the XML data
    return_code = get_xml(debug, appearance_mode)

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


# Get the XML data and setup Primeitems
def get_xml(debug: bool, appearance_mode: str) -> int:
    """ "Returns the tasker root xml items from the backup xml file based on the given debug and appearance mode parameters."
    Parameters:
        debug (bool): Indicates whether the program is in debug mode or not.
        appearance_mode (str): Specifies the color mode to be used.
    Returns:
        int: The return code from getting the xml file.
    Processing Logic:
        - Initialize temporary PrimaryItems object.
        - Set file_to_get variable based on debug mode.
        - Set program_arguments variable for debug mode.
        - Set colors_to_use variable based on appearance mode.
        - Initialize output_lines variable.
        - Return data and output intro."""
    if not PrimeItems.file_to_get:
        PrimeItems.file_to_get = "backup.xml" if debug else ""
    PrimeItems.file_to_use = ""  # Get rid of any previous file
    PrimeItems.program_arguments["debug"] = debug
    PrimeItems.program_arguments["gui"] = True
    PrimeItems.colors_to_use = set_color_mode(appearance_mode)
    PrimeItems.output_lines = LineOut()

    return get_data_and_output_intro(False)


# Get all monospace fonts from TKInter
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


# Build list of all available monospace fonts
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
    # font_items = ["Courier"]
    font_items = [value for value in fonts.values() if "Wingdings" not in value]
    # Find which Courier font is in our list and set.
    res = [i for i in font_items if "Courier" in i]
    # If Courier is not found for some reason, default to Monaco
    if not res:
        res = [i for i in font_items if "Monaco" in i]
    return font_items, res


# Ping the Android evice to make sure it is reachable.
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
        self.display_message_box(f"Pinging address {ip_address}.  Please wait...", "Green")
        self.update()  # Force a window refresh.

        # Ping IP address.
        response = os.system(f"ping -c 1 -t50 > /dev/null {ip_address}")  # noqa: S605
        if response != 0:
            self.backup_error(
                f"{ip_address} is not reachable (error {response}).  Try again.",
            )
            return False
        self.display_message_box("Ping successful.", "Green")
    else:
        self.backup_error(
            f"Invalid IP address: {ip_address}.  Try again.",
        )
        return False

    # Validate port number
    if validate_port(ip_address, port_number) != 0:
        self.backup_error(
            f"Invalid Port number: {port_number} or the given IP address does not permit access to this port.  Try again.",
        )
        return False

    # Valid IP Address...good ping.
    return True


# Clear all buttons associated with fetching the backup file from Android device
def clear_android_buttons(self) -> None:  # noqa: ANN001
    """
    Clears android device configuration buttons and displays backup button
    Args:
        self: The class instance
    Returns:
        None
    - Destroys all labels, buttons and entries associated with fetching the backup file from Android device
    """

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
    if not self.first_time:  # If first time, don't destory Upgrade and What's New buttons.
        with contextlib.suppress(AttributeError):
            self.list_files_query_button.destroy()
        with contextlib.suppress(AttributeError):  # Destroy upgrade button since file location would sit on top of it.
            self.upgrade_button.destroy()

    self.get_backup_button = self.display_backup_button(
        "Get XML from Android Device",
        "#246FB6",
        "#6563ff",
        self.event_handlers.get_xml_from_android_event,
    )


# Compare two versions and return True if version2 is greater than version1.
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


# Checks if 24 hours have passed since the given previous date.
def is_more_than_24hrs(input_datetime: datetime) -> bool:
    """Checks if the input datetime is more than 24 hours ago.
    Arguments:
        input_datetime (datetime): The datetime to be checked.
    Returns:
        bool: True if input datetime is more than 24 hours ago, False otherwise.
    Processing Logic:
        - Calculate seconds in 24 hours.
        - Get current datetime.
        - Check if difference between current datetime and input datetime is greater than 24 hours.
        - Return result as boolean."""
    twenty_four_hours = 86400  # seconds in 24 hours
    return (NOW_TIME - input_datetime).total_seconds() > twenty_four_hours


# Get Pypi version and return True if it is newer than our current version.
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


# List the XML files on the Android device
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


# Write out the changelog
def create_changelog() -> None:
    """Create changelog file."""
    with open(CHANGELOG_FILE, "w") as changelog_file:
        changelog_file.write(CHANGELOG)


# Parse the changelog and dump it as a json file.
def save_changelog_as_json(self) -> None:  # noqa: ANN001
    """
    Save the changelog from a markdown file to a JSON file.

    This function reads the contents of the "changelog.md" file and parses it to create a dictionary representing the changelog. The dictionary contains the version number as the key and the changes as the value. The function then writes the dictionary to a JSON file named "changelog.json".

    Parameters:
        None

    Returns:
        None
    """
    if os.path.isfile("changelog.md"):
        changelog_dict = {}
        have_first_bracket = False
        change_count = 0
        with open("changelog.md") as changelog:
            lines = changelog.readlines()
            for line in lines:
                if "[" in line:
                    if have_first_bracket:  # If we already have the bracket and encounter another, stop reading
                        break
                    have_first_bracket = True
                    bracket_start_pos = line.find("[")
                    bracket_end_pos = line.find("]")
                    changelog_dict["version"] = line[bracket_start_pos + 1 : bracket_end_pos]
                elif line != "\n" and have_first_bracket:
                    changelog_dict[f"change{change_count!s}"] = line
                    change_count += 1
        with open(CHANGELOG_JSON_FILE, "w") as changelog_file:
            json.dump(changelog_dict, changelog_file)

        self.display_message_box(f"{CHANGELOG_JSON_FILE} file saved.", "Turquoise")


# Read the change log file, add it to the messages to be displayed and then remove it.
def check_for_changelog(self) -> None:  # noqa: ANN001
    """Function to check for a changelog file and add its contents to a message if the current version is correct.
    Parameters:
        - self (object): The object that the function is being called on.
    Returns:
        - None: The function does not return anything, but updates the message attribute of the object.
    Processing Logic:
        - Check if the changelog file exists.
        - If it exists, prepare to display changes and remove the file so we only display the changes once.
    Note: The changelog file is created immdiately after the program is updated (userintr upgrade_event)
    """
    # TODO Test changelog before posting to PyPi.  Comment it out after testing.
    # self.message = CHANGELOG

    if os.path.isfile(CHANGELOG_FILE):
        with open(CHANGELOG_FILE) as changelog_file:
            for line in changelog_file:
                self.message += f"{line}\n"
        os.remove(CHANGELOG_FILE)

    # Write changelog out as json file if in debug mode.
    # TODO Set debug on and rerun to create the 'maptasker_changelog.json' file
    if self.debug:
        save_changelog_as_json(self)


# Add the MapTasker icon to the screen
def add_logo(self) -> None:  # noqa: ANN001
    """Function:
        add_logo
    Parameters:
        - self (object): The object that the function is being called on.
    Returns:
        - None: The function does not return anything.
    Processing Logic:
        - Get the path to our logos.
        - Switch to our temp directory (assets).
        - Create a CTkImage object to display the logo.
        - Try to display the logo with a CTkLabel.
        - Switch back to proper directory."""
    # Add our logo
    # Get the path to our logos:
    # current_dir = directory from which we are running.
    # abspath = path of this source code (userintr.py).
    # cwd = directory from which the main program is (main.py)
    # dname = directory of src
    current_dir = os.getcwd()
    abspath = os.path.abspath(__file__)
    # cwd = os.path.abspath(os.path.dirname(sys.argv[0]))
    dname = os.path.dirname(abspath)
    temp_dir = dname.replace("src", "assets")
    # Switch to our temp directory (assets)
    os.chdir(temp_dir)

    # Create a CTkImage object to display the logo
    my_image = ctk.CTkImage(
        light_image=Image.open("maptasker_logo_light.png"),
        dark_image=Image.open("maptasker_logo_dark.png"),
        size=(190, 50),
    )
    try:
        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame,
            image=my_image,
            text="",
            compound="left",
            font=ctk.CTkFont(size=1, weight="bold"),
        )  # display image with a CTkLabel
        self.logo_label.grid(row=0, column=0, padx=0, pady=0, sticky="n")
    except:  # noqa: S110
        pass
    # del my_image  # Done with image...get rid of it.

    # Switch back to proper directory
    os.chdir(current_dir)


# Create a label general routine
def add_label(
    self,  # noqa: ANN001, ARG001
    frame: ctk.CTkFrame,
    text: str,
    text_color: str,
    font_size: int,
    font_weight: str,
    row: int,
    column: int,
    padx: tuple,
    pady: tuple,
    sticky: str,
) -> None:
    """Adds a custom label to a custom tkinter frame.
    Parameters:
        - frame (ctk.CTkFrame): The frame to add the label to.
        - name (ctk.CTkLabel): The label to be added.
        - text (str): The text to be displayed on the label.
        - text_color (str): color for the text
        - font_size (int): The font size of the label.
        - font_weight (str): The font weight of the label.
        - row (int): The row number to place the label in.
        - column (int): The column number to place the label in.
        - padx (tuple): The horizontal padding of the label.
        - pady (tuple): The vertical padding of the label.
        - sticky (str): The alignment of the label within its grid cell.
    Returns:
        - label_name (str): The name of the label.
    Processing Logic:
        - Creates a custom label with the given parameters.
        - Places the label in the specified row and column of the frame.
        - Adds horizontal and vertical padding to the label.
        - Aligns the label within its grid cell."""
    if not font_size or font_size == 0:
        font_size = default_font_size
    if not text_color:
        label_name = ctk.CTkLabel(
            frame,
            text=text,
            font=ctk.CTkFont(size=font_size, weight=font_weight),
        )
    else:
        label_name = ctk.CTkLabel(
            frame,
            text=text,
            text_color=text_color,
            font=ctk.CTkFont(size=font_size, weight=font_weight),
        )
    label_name.grid(row=row, column=column, padx=padx, pady=pady, sticky=sticky)
    return label_name


# Create a checkbox general routine
def add_checkbox(
    self,  # noqa: ANN001, ARG001
    frame: ctk.CTkFrame,
    command: Callable,
    text: str,
    row: int,
    column: int,
    padx: tuple,
    pady: tuple,
    sticky: str,
    border_color: str,
) -> None:
    """Add a checkbox to a custom tkinter frame.
    Parameters:
        - frame (ctk.CTkFrame): The custom tkinter frame to add the checkbox to.
        - command (object): The command to be executed when the checkbox is clicked.
        - text (str): The text to be displayed next to the checkbox.
        - row (int): The row to place the checkbox in.
        - column (int): The column to place the checkbox in.
        - padx (tuple): The horizontal padding for the checkbox.
        - pady (tuple): The vertical padding for the checkbox.
        - sticky (str): The alignment of the checkbox within its grid cell.
        - border_color (str): The color to highlightn the button with.
    Returns:
        - checkbox_name: the named checkbox.
    Processing Logic:
        - Create a custom tkinter checkbox.
        - Add the checkbox to the specified frame.
        - Place the checkbox in the specified row and column.
        - Apply the specified padding to the checkbox.
        - Align the checkbox within its grid cell."""
    checkbox_name = ctk.CTkCheckBox(
        frame,
        command=command,
        text=text,
        font=ctk.CTkFont(size=default_font_size, weight="normal"),
        onvalue=True,
        offvalue=False,
    )
    if border_color:
        checkbox_name.configure(border_color=border_color)
    checkbox_name.grid(row=row, column=column, padx=padx, pady=pady, sticky=sticky)
    return checkbox_name


# Create a button general routine
def add_button(
    self,  # noqa: ANN001, ARG001
    frame: ctk.CTkFrame,
    fg_color: str,
    text_color: str,
    border_color: str,
    command: Callable,
    border_width: int,
    text: str,
    columnspan: int,
    row: int,
    column: int,
    padx: tuple,
    pady: tuple,
    sticky: str,
) -> None:
    """Add a button to a custom tkinter frame.
    Parameters:
        - frame (ctk.CTkFrame): The frame to add the button to.
        - fg_color (str): The color of the button's text.
        - text_color (str) The color of the button's text.
        - command (object): The function to be executed when the button is clicked.
        - border_width (int): The width of the button's border.
        - text (str): The text to be displayed on the button.
        - columnspan (int): The number of columns to span the button across.
        - row (int): The row to place the button in.
        - column (int): The column to place the button in.
        - padx (tuple): The amount of padding on the x-axis.
        - pady (tuple): The amount of padding on the y-axis.
        - sticky (str): The alignment of the button within its cell.
    Returns:
        - button_name: the named button.
    Processing Logic:
        - Create a custom tkinter button with the given parameters.
        - Place the button in the specified row and column.
        - Add padding and alignment to the button."""
    if not fg_color:
        fg_color = "#246FB6"
    if not text_color:
        text_color = "#FFFFFF"
    if not border_color:
        border_color = "Gray"
    if not columnspan:
        columnspan = 1
    button_name = ctk.CTkButton(
        frame,
        fg_color=fg_color,
        text_color=text_color,
        font=ctk.CTkFont(size=default_font_size, weight="normal"),
        border_color=border_color,
        command=command,
        border_width=border_width,
        text=text,
    )
    button_name.grid(row=row, column=column, columnspan=columnspan, padx=padx, pady=pady, sticky=sticky)
    return button_name


# Create a button general routine
def add_option_menu(
    self,  # noqa: ANN001, ARG001
    frame: ctk.CTkFrame,
    command: Callable,
    values: str | list,
    row: int,
    column: int,
    padx: tuple,
    pady: tuple,
    sticky: str,
) -> None:
    """Adds an option menu to a given frame with specified parameters.
    Parameters:
        - frame (ctk.CTkFrame): The frame to add the option menu to.
        - command (object): The function to be called when an option is selected.
        - values (str | list): The options to be displayed in the menu.
        - row (int): The row in which the option menu should be placed.
        - column (int): The column in which the option menu should be placed.
        - padx (tuple): The amount of padding in the x-direction.
        - pady (tuple): The amount of padding in the y-direction.
        - sticky (str): The direction in which the option menu should stick to the frame.
    Returns:
        - None: This function does not return any value.
    Processing Logic:
        - Adds an option menu to a frame.
        - Sets the command to be called when an option is selected.
        - Displays the specified options in the menu.
        - Places the option menu in the specified row and column.
        - Adds padding to the option menu.
        - Sets the direction in which the option menu should stick to the frame."""
    option_menu_name = ctk.CTkOptionMenu(
        frame,
        values=values,
        command=command,
    )
    option_menu_name.grid(row=row, column=column, padx=padx, pady=pady, sticky=sticky)
    return option_menu_name


# Display Ai 'Analyze" button
def display_analyze_button(self, row: int, first_time: bool) -> None:  # noqa: ANN001
    """
    Display the 'Analyze' button for the AI API key.

    This function creates and displays a button on the 'Analyze' tab of the tabview. The button is used to run the analysis for the AI API key.

    Parameters:
        self (object): The instance of the class.
        row (int): The row number to display the button.
        first_time (bool): True if this is the first time the button is to be displayed

    Returns:
        None: This function does not return anything.
    """
    # Make sure Ai model is blkank if value is "None"
    if self.ai_model == "None":
        self.ai_model = ""
    # Highlight the button if we have everything to run the Analysis.
    if ((self.ai_model in OPENAI_MODELS and self.ai_apikey) or self.ai_model) and (
        self.single_task_name or self.single_profile_name or self.single_project_name
    ):
        fg_color = "#f55dff"
        text_color = "#FFFFFF"
    # Otherwise, use the default colors.
    else:
        fg_color = "#246FB6"
        text_color = "#FFFFFF"
    # First time only, add the button
    if first_time:
        self.ai_analyze_button = add_button(
            self,
            self.tabview.tab("Analyze"),
            fg_color,  # fg_color: str,
            text_color,  # text_color: str,
            "#6563ff",  # border_color: str,
            self.event_handlers.ai_analyze_event,  # command
            2,  # border_width: int,
            "Run Analysis",  # text: str,
            1,  # columnspan: int,
            row,  # row: int,
            0,  # column: int,
            50,  # padx: tuple,
            (10, 10),  # pady: tuple,
            "n",
        )
    else:  # Not first time, just reconfigure the colors of the button.
        self.ai_analyze_button.configure(fg_color=fg_color, text_color=text_color)


# $ Delete existing Ai labels
def delete_ai_labels(self) -> None:  # noqa: ANN001
    """
    Deletes the AI labels if they exist.
    """
    with contextlib.suppress(AttributeError):
        self.ai_set_label1.destroy()
    with contextlib.suppress(AttributeError):
        self.ai_set_label2.destroy()
    with contextlib.suppress(AttributeError):
        self.ai_set_label3.destroy()
    with contextlib.suppress(AttributeError):
        self.ai_set_label4.destroy()
    with contextlib.suppress(AttributeError):
        self.ai_set_label5.destroy()
    with contextlib.suppress(AttributeError):
        self.single_label.destroy()  # Include the single name label


# Display the current settings for Ai
def display_selected_object_labels(self) -> None:  # noqa: ANN001
    """
    Display the current settings for Ai
    """
    # Delete previous labels since they may be longer than new labels
    delete_ai_labels(self)

    # Read the api key.
    self.ai_apikey = get_api_key()
    key_to_display = "Unset" if self.ai_apikey == "None" or not self.ai_apikey else "Set"
    model_to_display = self.ai_model if self.ai_model else "None"
    self.ai_set_label1 = add_label(
        self,
        self.tabview.tab("Analyze"),
        f"API Key: {key_to_display}, Model: {model_to_display}",
        "",
        0,
        "normal",
        14,
        0,
        10,
        (0, 30),
        "nw",
    )
    # Set up name to display
    project_to_display = self.single_project_name if self.single_project_name else "None"
    profile_to_display = self.single_profile_name if self.single_profile_name else "None"
    task_to_display = self.single_task_name if self.single_task_name else "None"
    self.ai_model_option.set(model_to_display)  # Set the current model in the pulldown.

    # Display the Project to analyze
    self.ai_set_label2 = add_label(
        self,
        self.tabview.tab("Analyze"),
        f"Project to Analyze: {project_to_display}",
        "",
        0,
        "normal",
        14,
        0,
        10,
        (0, 0),
        "sw",
    )
    # Display the Profile to analyze
    self.ai_set_label3 = add_label(
        self,
        self.tabview.tab("Analyze"),
        f"Profile to Analyze: {profile_to_display}",
        "",
        0,
        "normal",
        15,
        0,
        10,
        (0, 30),
        "nw",
    )
    # Display the Task to analyze
    self.ai_set_label4 = add_label(
        self,
        self.tabview.tab("Analyze"),
        f"Task to Analyze: {task_to_display}",
        "",
        0,
        "normal",
        15,
        0,
        10,
        (0, 0),
        "sw",
    )
    # Display the Prompt..newline after every maxlen characters forces it to wrap.
    maxlen = 35
    # display_prompt = self.ai_prompt[:maxlen] + "..." if len(self.ai_prompt) > maxlen else self.ai_prompt
    display_prompt = "\n".join(self.ai_prompt[i : i + maxlen] for i in range(0, len(self.ai_prompt), maxlen))
    self.ai_set_label5 = add_label(
        self,
        self.tabview.tab("Analyze"),
        f"Prompt: '{display_prompt}'",
        "",
        0,
        "normal",
        16,
        0,
        10,
        (0, 30),
        "nw",
    )
    # self.ai_set_label5.configure(wraplength=maxlen + 15, justify="left")

    # Display the label on 'Specific Name' tab.
    # First time through, self.specific_name_msg = ''
    name_to_display = self.specific_name_msg if self.specific_name_msg else all_objects

    self.single_label = add_label(
        self,
        self.tabview.tab("Specific Name"),
        name_to_display,
        "",
        # ("#0BF075", "#3f99ff"),
        0,
        "normal",
        10,
        0,
        20,
        (10, 10),
        "w",
    )


# Update the Project/Profile/Task pulldown option menus.
# @profile
def update_tasker_object_menus(self, get_data: bool, reset_single_names: bool) -> None:  # noqa: ANN001
    """
    Update the Project/Profile/Task pulldown option menus. Only do this if we have the object name since it forces a read of XML.

    Parameters:
        get_data (bool): If True, then get the data tree, list and set the Project/Profile/Task list in 'Specific Name' and 'Analyze' tab. If False, then don't get the data.
        reset_single_names (bool): If True, then reset the Project/Profile/Task name fields in 'Specific Name' tab. If False, then don't reset the fields.

    Returns:
        None
    """
    if get_data:
        if reset_single_names:
            self.single_project_name = ""
            self.single_profile_name = ""
            self.single_task_name = ""
        return_code = list_tasker_objects(self)
        if not return_code:
            return

    # Update the Project/Profile/Task pulldown option menus.

    # Update the text labels
    display_selected_object_labels(self)


# Get the Ai api key
def get_api_key() -> str:
    """
    Retrieves the API key from the specified file.

    This function checks if the KEYFILE exists and if it does, it opens the file and reads the first line. The first line is assumed to be the API key. If the KEYFILE does not exist, it returns the string "None".

    Returns:
        str: The API key if it exists, otherwise "None".
    """
    if os.path.isfile(KEYFILE):
        # Open output file
        with open(KEYFILE) as key_file:
            return key_file.readline()
    else:
        return "None"


# Either validate the file location provided or provide a filelist of XML files
def validate_or_filelist_xml(
    self,  # noqa: ANN001
    android_ipaddr: str,
    android_port: str,
    android_file: str,
) -> tuple[int, str]:
    # If we don't have the file location yet and we don't yet have a list of files, then get the XML file
    # to validate that it exists.
    """Function to validate an XML file on an Android device and return the file's contents if it exists.
    Parameters:
        - android_ipaddr (str): IP address of the Android device.
        - android_port (str): Port number of the Android device.
        - android_file (str): File name of the XML file to validate.
    Returns:
        - Tuple[int, str]: A tuple containing the return code and the file's contents if it exists.
    Processing Logic:
        - Get the XML file from the Android device if no file location is provided.
        - Validate the XML file.
        - If the file does not exist, display an error message.
        - If the file location is not provided, get a list of all XML files from the Android device and present it to the user.
    """
    # If we don't yet have the file, then get it from the Android device.
    if len(android_file) != 0 and android_file != "" and self.list_files == False:
        return_code, file_contents = http_request(android_ipaddr, android_port, android_file, "file", "?download=1")

        # Validate XML file.
        if return_code == 0:
            PrimeItems.program_arguments["gui"] = True
            return_code, error_message = validate_xml_file(android_ipaddr, android_port, android_file)
            if return_code != 0:
                self.display_message_box(error_message, "Red")
                return 1, android_ipaddr, android_port, android_file
        else:
            return 1, android_ipaddr, android_port, android_file

    # File location not provided.  Get the list of all XML files from the Android device and present it to the user.
    else:
        clear_android_buttons(self)
        # Get list from Tasker directory (/Tasker) or system directory (/storage/emulated/0)
        return_code, filelist = get_list_of_files(android_ipaddr, android_port, "/storage/emulated/0/Tasker")
        if return_code != 0:
            # Error getting list of files.
            self.display_message_box(filelist, "Red")
            return 1, android_ipaddr, android_port, android_file

        # Display File List for file selection
        self.filelist_label = add_label(
            self,
            self,
            "Select XML From Android Device:",
            "",
            0,
            "normal",
            7,
            1,
            (200, 0),
            (0, 10),
            "w",
        )
        self.filelist_option = add_option_menu(
            self,
            self,
            self.event_handlers.file_selected_event,
            filelist,
            7,
            1,
            (200, 0),
            (50, 10),
            "w",
        )
        # Add 'Cancel Entry' button.
        add_cancel_button(self, row=8, delta_y=0)

        # Set backup IP and file location attributes if valid
        self.android_ipaddr = android_ipaddr
        self.android_port = android_port
        return 2, "", "", ""  # Just return with error so the prompt comes up to select file.

    # All is okay
    return 0, android_ipaddr, android_port, android_file


# Add pulldown menus for the Projects/Profiles/Tasks for selection
def display_object_pulldowns(
    self,  # noqa: ANN001
    frame: ctk.CTkFrame,
    row: int,
    projects_to_display: list,
    profiles_to_display: list,
    tasks_to_display: list,
    project_name_event: Callable,
    profile_name_event: Callable,
    task_name_event: Callable,
) -> None:
    """
    Displays the pulldown menus for selecting profiles and tasks.

    Parameters:
        frame (ctk.CTkFrame): The frame to display the pulldown menus in.
        row (int): The row number to start displaying the pulldown menus.
        projects_to_display (list): The list of projects to display in the projects pulldown menu.
        profiles_to_display (list): The list of profiles to display in the profiles pulldown menu.
        tasks_to_display (list): The list of tasks to display in the tasks pulldown menu.
        project_name_event (object): The event to trigger when a project is selected.
        profile_name_event (object): The event to trigger when a profile is selected.
        task_name_event (object): The event to trigger when a task is selected.

    Returns:
        None
    """
    # Display all of the Projects for selection.
    profile_row = row + 2
    task_row = row + 4

    # Make sure there is something to display
    if not projects_to_display and not profiles_to_display and not tasks_to_display:
        self.project_label = add_label(
            self,
            frame,
            "No Projects, Profiles or Tasks to display!",
            "",
            0,
            "normal",
            row,
            0,
            20,
            (10, 0),
            "s",
        )

    # Okay, we have some actual data to display
    else:
        self.project_label = add_label(
            self,
            frame,
            "Select Project to process:",
            "",
            0,
            "normal",
            row,
            0,
            20,
            (10, 0),
            "s",
        )
        project_option = add_option_menu(
            self,
            frame,
            project_name_event,
            projects_to_display,
            row + 1,
            0,
            20,
            (0, 10),
            "n",
        )

        # Display all of the Profiles for selection.
        self.profile_label = add_label(
            self,
            frame,
            "Select Profile to process:",
            "",
            0,
            "normal",
            profile_row,
            0,
            20,
            (0, 0),
            "s",
        )
        profile_option = add_option_menu(
            self,
            frame,
            profile_name_event,
            profiles_to_display,
            profile_row + 1,
            0,
            20,
            (0, 10),
            "n",
        )

        # Display all of the Tasks for selection.
        self.task_label = add_label(
            self,
            frame,
            "Select Task to process:",
            "",
            0,
            "normal",
            task_row,
            0,
            20,
            (0, 0),
            "n",
        )
        task_option = add_option_menu(
            self,
            frame,
            task_name_event,
            tasks_to_display,
            task_row,
            0,
            20,
            (30, 0),
            "s",
        )
    return project_option, profile_option, task_option


# Delete old pulldown menus since the older selected items could be longer than the new,
# and both will appear.
def delete_old_pulldown_menus(self) -> None:  # noqa: ANN001
    """
    Deletes the old pulldown menus.

    This function deletes the old pulldown menus that were created in the GUI. It checks if each menu exists and then destroys it.

    Parameters:
        self (object): The current instance of the class.

    Returns:
        None
    """
    with contextlib.suppress(AttributeError):
        self.specific_project_optionmenu.destroy()
    with contextlib.suppress(AttributeError):
        self.specific_profile_optionmenu.destroy()
    with contextlib.suppress(AttributeError):
        self.specific_task_optionmenu.destroy()
    with contextlib.suppress(AttributeError):
        self.ai_project_optionmenu.destroy()
    with contextlib.suppress(AttributeError):
        self.ai_profile_optionmenu.destroy()
    with contextlib.suppress(AttributeError):
        self.ai_task_optionmenu.destroy()
    with contextlib.suppress(AttributeError):
        self.single_label.destroy()


# Provide a pulldown list for the selection of a Profile name
# @profile
def list_tasker_objects(self) -> bool:  # noqa: ANN001
    """
    Lists the projects, profiles and tasks available in the XML file.  The list for each will appear in a pulldown option list.

    This function checks if the XML file has already been loaded. If not, it loads the XML file and builds the tree data.
    Then, it goes through each project and retrieves all the profile names and tasks.
    The profile names and tasks are cleaned up by removing the "Profile: Unnamed/Anonymous" and "Task: Unnamed/Anonymous." entries.
    If there are no profiles or tasks found, a message box is displayed and the function returns False.
    The profile names and tasks are then sorted alphabetically and duplicates are removed.
    The profile names are displayed in a label for selection, and the corresponding tasks are displayed in another label for selection.

    Returns:
        bool: True if the XML file has Profiles or Tasks, False otherwise.
    """

    # Do we already have the XML?
    # If we don't have any data, get it.
    if not self.load_xml():
        return False

    # Get rid of previous data
    delete_old_pulldown_menus(self)

    # Get all of the Tasker objects: Projects/Profiles/Tasks/Scenes
    return_code, projects_to_display, profiles_to_display, tasks_to_display = get_tasker_objects(self)
    if not return_code:
        return False

    # Make alphabetical
    if projects_to_display:
        projects_to_display = sorted(projects_to_display)
        projects_to_display.insert(0, "None")
    profiles_to_display = sorted(profiles_to_display)
    profiles_to_display.insert(0, "None")
    tasks_to_display.insert(0, "None")

    # Remove 'No Profile' profiles
    new_profiles = [profile for profile in profiles_to_display if profile != "No Profile"]
    if new_profiles:
        profiles_to_display = new_profiles

    # Display the object pulldowns in 'Analyze' tab
    self.ai_project_optionmenu, self.ai_profile_optionmenu, self.ai_task_optionmenu = display_object_pulldowns(
        self,
        self.tabview.tab("Analyze"),
        8,
        projects_to_display,
        profiles_to_display,
        tasks_to_display,
        self.event_handlers.single_project_name_event,
        self.event_handlers.single_profile_name_event,
        self.event_handlers.single_task_name_event,
    )

    # Display the object pulldowns in 'Specific Name' tab
    if not projects_to_display:  # If no Projects to display
        projects_to_display = ["None"]
    self.specific_project_optionmenu, self.specific_profile_optionmenu, self.specific_task_optionmenu = (
        display_object_pulldowns(
            self,
            self.tabview.tab("Specific Name"),
            5,
            projects_to_display,
            profiles_to_display,
            tasks_to_display,
            self.event_handlers.single_project_name_event,
            self.event_handlers.single_profile_name_event,
            self.event_handlers.single_task_name_event,
        )
    )
    return True


# Get all Projects, Profiles and Tasks to display
def get_tasker_objects(self) -> tuple:  # noqa: ANN001
    """
    Retrieves the projects, profiles, and tasks available in the XML file.

    This function checks if the XML file has already been loaded. If not, it loads the XML file and builds the tree data.
    Then, it goes through each project and retrieves all the profile names and tasks.
    The profile names and tasks are cleaned up by removing the "Profile: Unnamed/Anonymous" and "Task: Unnamed/Anonymous." entries.
    If there are no profiles or tasks found, a message box is displayed and the function returns False.
    The profile names and tasks are then sorted alphabetically and duplicates are removed.

    Returns:
        tuple: A tuple containing the following:
            - bool: True if the XML file has Profiles or Tasks, False otherwise.
            - list: A list of project names.
            - list: A list of profile names to display.
            - list: A list of task names to display.
    """
    projects_to_display = []
    profiles = []
    tasks = []
    # Build the tree of Tasker objects
    tree_data = self.build_the_tree()
    # If no tree data, then we don't have any Projects.  Just get the Profiles and Tasks.
    if not tree_data:
        profiles = [value["name"] for value in PrimeItems.tasker_root_elements["all_profiles"].values()]
        tasks = [value["name"] for value in PrimeItems.tasker_root_elements["all_tasks"].values()]
    # We have the Tasker objects.  Collect all Projects, Profiles and Tasks from the tree data.
    else:
        for project in tree_data:
            projects_to_display.append(project["name"])
            for profile in project["children"]:
                with contextlib.suppress(TypeError):
                    profiles.append(profile["name"])
                    tasks.extend(profile["children"])
    # Clean up the object lists by removing anonymous or missing objects.

    profiles_to_display = [profile for profile in profiles if profile != "Profile: Unnamed/Anonymous"]
    if not projects_to_display:
        projects_to_display = ["No projects found"]
    if not profiles_to_display:
        profiles_to_display = ["No profiles found"]

    # Cleanup Task names.
    tasks_to_display = []
    for task in tasks:
        name_to_use = task if task[0:5] == "Task:" else "Task: " + task
        if name_to_use != "Task: Unnamed/Anonymous.":
            tasks_to_display.append(name_to_use)

    # Check for no tasks.
    if not tasks_to_display:
        tasks_to_display = ["No tasks found"]
    else:
        tasks_to_display = list(set(tasks_to_display))
        tasks_to_display.sort()

    return True, projects_to_display, profiles_to_display, tasks_to_display


# Build a list of Profiles that are under the given project
def build_profiles(root: dict, profile_ids: list, project: defusedxml.ElementTree) -> list:
    """Parameters:
        - root (dict): Dictionary containing all profiles and their tasks.
        - profile_ids (list): List of profile IDs to be processed.
        - project (defusedxml.ElementTree): The project xml element.
    Returns:
        - list: List of dictionaries containing profile names and their corresponding tasks.
    Processing Logic:
        - Get all profiles from root dictionary.
        - Create an empty list to store profile names and tasks.
        - Loop through each profile ID in the provided list.
        - Get the tasks for the current profile.
        - If tasks are found, create a list to store task names.
        - Loop through each task and add its name to the task list.
        - If no tasks are found, add a default message to the task list.
        - Get the name of the current profile.
        - If no name is found, add a default message to the profile name.
        - Combine the profile name and task list into a dictionary and add it to the profile list.
        - Return the profile list."""
    profiles = root["all_profiles"]
    profile_list = []
    found_tasks = []
    for profile in profile_ids:
        # Get the Profile's Tasks
        PrimeItems.task_count_unnamed = 0  # Avoid an error in get_profile_tasks
        if the_tasks := get_profile_tasks(profiles[profile]["xml"], [], []):
            task_list = []
            # Process each Task.  Tasks are simply a flat list of names.
            for task in the_tasks:
                if task["name"] == "":
                    task_list.append("Task: Unnamed Task")
                else:
                    task_list.append(f'Task: {task["name"]}')
                    found_tasks.append(task["name"])  # Keep track of found tasks
        else:
            task_list = ["No Profile Tasks Found"]

        # Get the Profile name.
        if profiles[profile]["name"] == "":
            profile_name = "Profile: Unnamed/Anonymous"
        else:
            profile_name = f'Profile: {profiles[profile]["name"]}'

        # Combine the Profile with it's Tasks
        profile_list.append({"name": profile_name, "children": task_list})

    # Now add tasks that are not found in any Profile that belong to the Project
    no_profile_tasks = []
    task_ids = get_ids(False, PrimeItems.tasker_root_elements["all_projects"][project]["xml"], project, [])
    for task_id in task_ids:
        if root["all_tasks"][task_id]["name"] not in found_tasks:
            no_profile_tasks.append(root["all_tasks"][task_id]["name"])  # noqa: PERF401
    if no_profile_tasks:
        profile_list.append({"name": "No Profile", "children": no_profile_tasks})

    return profile_list


# Display startup messages which are a carryover from the last run.
def display_messages_from_last_run(self) -> None:  # noqa: ANN001
    """
    Displays messages from the last run.

    This function checks if there are any carryover error messages from the last run (rerun).
    If there are, it reads the error message from the file specified by the `ERROR_FILE` constant and handles
    potential missing modules. If the error message contains the string "Ai Response", it displays the
    error message in a new toplevel window and displays a message box indicating that the analysis response
    is in a separate window and saved as `ANALYSIS_FILE`. If the error message contains newline characters,
    it breaks the message up into multiple lines and displays each line in a message box. If the error message
    does not contain newline characters, it displays the error message in a message box. After displaying the
    error message, it removes the error file to prevent it from being displayed again.

    If there is an error message from other routines, it displays the error message in a message box with the return code.

    Parameters:
    - None

    Returns:
    - None
    """
    # See if we have any carryover error messages from last run (rerun).
    if os.path.isfile(ERROR_FILE):
        with open(ERROR_FILE) as error_file:
            error_msg = error_file.read()
            # Handle potential mssing modules
            if "cria" in error_msg:
                self.ai_missing_module = "cria"
            elif "openai" in error_msg:
                self.ai_missing_module = "openai"

            # Handle Ai Response and display it in a new toplevel window
            if "Ai Response" in error_msg:
                self.display_ai_response(error_msg)
                self.display_message_box(
                    f"Analysis response is in a separate Window and saved as {ANALYSIS_FILE}.",
                    "Turquoise",
                )
            # Some other message.  Just display it in the message box and break it up if needed.
            elif "\n" in error_msg:
                messages = error_msg.split("\n")
                for message_line in messages:
                    self.display_message_box(message_line, "Red")
            else:
                self.display_message_box(error_msg, "Red")
            # Get rid of error message so we don't display it again.
            os.remove(ERROR_FILE)  # Get rid of error message so we don't display it again.

    # Display any error message from other rountines
    if PrimeItems.error_msg:
        self.display_message_box(f"{PrimeItems.error_msg} with return code {PrimeItems.error_code}.", "Red")


# Display the current file as a label
def display_current_file(self, file_name: str) -> None:  # noqa: ANN001
    """
    A function to display the current file as a label in the GUI.

    Args:
        self: The object instance.
        file_name (str): The name of the file to be displayed.

    Returns:
        None: This function does not return anything.
    """
    # Clear previous if filled.
    with contextlib.suppress(AttributeError):
        self.current_file_label.destroy()
    # Check for slashes and remove if nessesary
    filename_location = file_name.rfind(PrimeItems.slash) + 1
    if filename_location != -1:
        file_name = file_name[filename_location:]
    self.current_file_label = add_label(
        self,
        self,
        f"Current File: {file_name}",
        "",
        "",
        "normal",
        8,
        1,
        20,
        (20, 0),
        "w",
    )
    # Update UI elements
    update_tasker_object_menus(self, get_data=False, reset_single_names=False)
    display_analyze_button(self, 13, first_time=False)


# Set up error message for single Project/Profile/Task name that was entered.  Called by check_name in userintr.
def setup_name_error(object1_name: str, object2_name: str, single_name1: str, single_name2: str) -> None:
    """
    Set up an error message for when both a Project and a Profile name are entered.

    Args:
        object1_name (str): The name of the first object (Project).
        object2_name (str): The name of the second object (Profile).
        single_name1 (str): The name of the Project.
        single_name2 (str): The name of the Profile.

    Returns:
        None: This function does not return anything.
    """
    return [
        "Error:\n\n",
        f"You have entered both a {object1_name} and a {object2_name} name!\n",
        f"(Project {single_name1} and Profile {single_name2})\n",
        "Try again and only select one.\n",
    ]


# Set the current Project/Profile/Task names in the pulldown menus
def set_tasker_object_names(self) -> None:  # noqa: ANN001
    """
    Sets the names to display in the pulldown menus based on the current tasker object names.

    This function determines the values to be displayed in the option menus for the tasker objects. The values are determined based on the following conditions:

    - If a single project name is available, the project option menu is set to the project name, and the profile and task option menus are set to their default values.
    - If a single profile name is available, the profile option menu is set to the profile name, and the project and task option menus are set to their default values.
    - If a single task name is available and the list of tasker objects is not empty, the task option menu is set to the task name, and the project and profile option menus are set to their default values.
    - If none of the above conditions are met, all option menus are set to their default values.

    Parameters:
    - self (object): The current instance of the class.

    Returns:
    - None: This function does not return anything.
    """
    # Define defaults
    default_project = "None"
    default_profile = "None"
    default_task = "None"
    default_display_only = "Display only "

    # Determine values based on conditions
    # Update the Project/Profile/Task pulldown option menus.
    if self.single_project_name:
        self.specific_name_msg = f"{default_display_only}Project '{self.single_project_name}'"
        self.specific_project_optionmenu.set(self.single_project_name)
        self.ai_project_optionmenu.set(self.single_project_name)
        self.specific_profile_optionmenu.set(default_profile)
        self.ai_profile_optionmenu.set(default_profile)
        self.specific_task_optionmenu.set(default_task)
        self.ai_task_optionmenu.set(default_task)
    elif self.single_profile_name:
        self.specific_name_msg = f"{default_display_only}Profile '{self.single_profile_name}'"
        self.specific_profile_optionmenu.set(self.single_profile_name)
        self.ai_profile_optionmenu.set(self.single_profile_name)
        self.ai_project_optionmenu.set(default_project)
        self.specific_project_optionmenu.set(default_project)
        self.specific_task_optionmenu.set(default_task)
        self.ai_task_optionmenu.set(default_task)
    elif self.single_task_name:
        self.specific_name_msg = f"{default_display_only}Task '{self.single_task_name}'"
        self.specific_task_optionmenu.set(self.single_task_name)
        self.ai_task_optionmenu.set(self.single_task_name)
        self.specific_project_optionmenu.set(default_project)
        self.specific_profile_optionmenu.set(default_profile)
        self.ai_project_optionmenu.set(default_project)
        self.ai_profile_optionmenu.set(default_profile)
    else:
        self.specific_name_msg = ""
        try:  # If it works on the first one, then all others will work as well.
            self.specific_project_optionmenu.set(default_project)
            if not PrimeItems.tasker_root_elements["all_projects"]:
                self.specific_project_optionmenu.configure(values=["None"])
                self.ai_project_optionmenu.configure(values=["None"])
            if not PrimeItems.tasker_root_elements["all_profiles"]:
                self.specific_profile_optionmenu.configure(values=["None"])
                self.ai_profile_optionmenu.configure(values=["None"])
            if not PrimeItems.tasker_root_elements["all_tasks"]:
                self.specific_task_optionmenu.configure(values=["None"])
                self.ai_task_optionmenu.configure(values=["None"])
            self.specific_profile_optionmenu.set(default_profile)
            self.ai_project_optionmenu.set(default_project)
            self.ai_profile_optionmenu.set(default_profile)
            self.specific_task_optionmenu.set(default_task)
            self.ai_task_optionmenu.set(default_task)
        except AttributeError:
            pass


# Clear all Tasker XML data from memory so we start anew.
def clear_tasker_data() -> None:
    """
    Clears all the tasker data stored in the PrimeItems class.

    This function clears the tasker data by clearing the following lists:
    - all_projects: a list of all the projects
    - all_profiles: a list of all the profiles
    - all_tasks: a list of all the tasks
    - all_scenes: a list of all the scenes

    This function does not take any parameters.

    This function does not return anything.
    """
    # Get rid of any data we currently have
    PrimeItems.tasker_root_elements["all_projects"].clear()
    PrimeItems.tasker_root_elements["all_profiles"].clear()
    PrimeItems.tasker_root_elements["all_tasks"].clear()
    PrimeItems.tasker_root_elements["all_scenes"].clear()


# Adds the "Cancel Entry" button to the GUI.
def add_cancel_button(self, row: int, delta_y: int) -> None:  # noqa: ANN001
    """
    Adds a cancel button to the GUI.

    This function creates a cancel button and adds it to the GUI. The button is created using the `add_button` function
    and is assigned to the `cancel_entry_button` attribute of the `self` object.
    The button is styled with specific colors and has a label "Cancel Entry".

    Parameters:
        row (int): The row number where the button should be placed.
        delta_y (int): The vertical offset of the button.

    Returns:
        None
    """
    # Add Cancel button
    self.cancel_entry_button = add_button(
        self,
        self,
        "#246FB6",
        "",
        "#1bc9ff",
        self.event_handlers.backup_cancel_event,
        2,  # border width
        "Cancel Entry",
        2,  # column span
        row,  # row
        1,  # column
        (80, 260),
        (delta_y, 0),
        "ne",
    )


# Reload the program
def reload_gui(self: object) -> None:
    """
    Reload the GUI by running a new process with the new program/version.

    This function reloads the GUI by running a new process using the `os.execl` function.
    The new process will load and run the new program/version.

    Note:
        - This function will cause an OS error, 'python[35833:461355] Task policy set failed: 4 ((os/kern) invalid argument)'.
        - The current process will not return after this call, but will simply be killed.

    Parameters:
        *args (list): A variable-length argument list of command-line arguments to be passed to the new process.

    Returns:
        None
    """
    # Imports are here to avoid circular import.
    from maptasker.src.getputer import save_restore_args
    from maptasker.src.guiwins import store_windows

    # Save windows
    store_windows(self)

    # Save the settings
    temp_args = {value: getattr(self, value) for value in ARGUMENT_NAMES}
    _, _ = save_restore_args(temp_args, self.color_lookup, True)

    # ReRun via a new process, which will load and run the new program/version.
    # Note: this will cause an OS error, 'python[35833:461355] Task policy set failed: 4 ((os/kern) invalid argument)'
    # Note: this current process will not return after this call, but simply be killed.
    print("The following error message can be ignored: 'Task policy set failed: 4 ((os/kern) invalid argument)'.")
    os.execl(sys.executable, "python", *sys.argv)


def display_no_xml_message(self) -> None:  # noqa: ANN001
    """
    Display a message indicating that a map is not possible because there are no projects, profiles, tasks, or scenes
    in the current XML file.

    This function does not take any parameters.

    Returns:
        None
    """
    self.display_message_box(
        "View not possible.  No Projects, Profiles Tasks (or Scenes) in the current XML file.\n",
        "Orange",
    )
    self.display_message_box(
        "Click the 'Get Local XML' or 'Get XML From Android' button to load some XML first.",
        "Orange",
    )
    # Clear everything out.
    update_tasker_object_menus(self, get_data=False, reset_single_names=True)


def reset_primeitems_single_names() -> None:
    """
    Reset the prime items related to single names.
    """
    PrimeItems.found_named_items = {
        "single_project_found": False,
        "single_profile_found": False,
        "single_task_found": False,
    }
    PrimeItems.directory_items = {
        "current_item": "",
        "projects": [],
        "profiles": [],
        "tasks": [],
        "scenes": [],
    }
    PrimeItems.program_arguments["single_project_name"] = ""
    PrimeItems.program_arguments["single_profile_name"] = ""
    PrimeItems.program_arguments["single_task_name"] = ""
    PrimeItems.found_named_items = {
        "single_project_found": False,
        "single_profile_found": False,
        "single_task_found": False,
    }
    # self.single_project_name = ""
    # self.single_profile_name = ""
    # self.single_task_name = ""


def fresh_message_box(self: ctk.windows.Window) -> None:
    """
    A function to refresh the message box by destroying the existing textbox and creating a new one.
    No parameters are taken, and no return value is provided.
    """
    self.all_messages = {}
    with contextlib.suppress(AttributeError):
        self.textbox.destroy()
    self.create_new_textbox()


# Define the textbox for information/feedback
def create_new_textbox(self: object) -> None:
    """
    Creates a new text box widget with specified dimensions and configuration.

    This function initializes a new `CTkTextbox` widget with the specified height and width.
    The widget is then added to the grid layout of the parent widget (`self`) at row 0, column 1,
    with a padding of 20 pixels on the left and right. The widget is also configured with the
    following properties:
    - `state` is set to "disabled" to make the text box read-only.
    - `font` is set to `(self.font, 14)` to use the specified font with a size of 14 points.
    - `wrap` is set to "word" to enable word wrapping.
    - `scrollbar_button_color` is set to "#6563ff" to set the color of the scrollbar buttons.

    Parameters:
        None

    Returns:
        None

    Note: This is a duplciate of the samd function in userintr.py.
    It can not be imported since it would cause a circular import.
    """
    self.textbox = ctk.CTkTextbox(self, height=650, width=250)
    self.textbox.grid(row=0, column=1, padx=(20, 0), pady=(20, 0), sticky="ew")
    self.textbox.configure(font=(self.font, 14), wrap="word", scrollbar_button_color="#6563ff")
    self.hyperlink = ctk.HyperlinkManager(self.textbox, text_color=get_appropriate_color(self, "blue"))


def make_hex_color(color: str) -> str:
    """
    Converts a given color string to a hex color string if it's a digit.

    Args:
        color (str): The color string to be converted.

    Returns:
        str: The hex color string if the input is a digit, otherwise the original color string.
    """
    # Add color to the tag
    if color.isdigit():
        return "#" + color
    return color


def search_substring_in_list(strings: list, substring: str, stop_on_first_match: bool) -> list:
    """
    Searches for a given substring within a list of strings and returns a list of tuples containing the index of the string and the position of the substring.

    Args:
        strings (list): A list of strings to search within.
        substring (str): The substring to search for.
        stop_on_first_match (bool): Whether to stop searching after the first match is found.

    Returns:
        list: A list of tuples containing the index of the string and the position of the substring.
    """
    matches = []
    lower_substring = substring.lower()
    for i, string in enumerate(strings):
        lower_string = string.lower()
        start = 0
        while start < len(lower_string):
            pos = lower_string.find(lower_substring, start)
            if pos == -1 or "up one level" in lower_string:
                break
            matches.append((i, pos))
            if stop_on_first_match:
                return matches
            start = pos + 1  # Move start index forward to continue searching
    return matches


def search_nextprev_string(self: object, textview: ctk.CTkTextbox, direction: str) -> None:
    """
    Searches for the next or previous occurrence of a string in a text box based on the given direction.

    Args:
        self (object): The object instance.
        direction (str): The direction to search, either "next" or "previous".

    Returns:
        None
    """
    if not textview.search_string:
        no_search_string(textview)
        return

    # Remove tag 'next' from index 1 to END
    textview.textview_textbox.tag_remove("next", "1.0", "end")
    try:
        search_indices = textview.search_indecies
    except:
        no_search_string(self)
        return

    for num, idx in enumerate(search_indices):
        if idx == textview.search_current_line:
            if (direction == "next" and idx == search_indices[-1]) or (
                direction == "previous" and idx == search_indices[0]
            ):
                # Add label for reaching the end or beginning of the text
                message = (
                    "The end of the text has been reached."
                    if direction == "next"
                    else "The beginning of the text has been reached."
                )
                output_label(textview, message)
            else:
                # Determine the new current line based on direction
                if direction == "next":
                    textview.search_current_line = search_indices[num + 1]
                elif direction == "previous":
                    textview.search_current_line = search_indices[num - 1]

                # Add tag to highlight the found text
                temp = textview.search_current_line.split(".")
                end_index = int(temp[1]) + len(textview.search_string)
                textview.textview_textbox.tag_add("next", textview.search_current_line, f"{temp[0]!s}.{end_index}")
                textview.textview_textbox.tag_config(
                    "next",
                    foreground=textview.search_color_text,
                    background=textview.search_color_nextprev,
                    relief="raised",
                )

                # Set the line at the first hit. "See" makes it visible.
                textview.textview_textbox.see(textview.search_current_line)
                textview.textview_textbox.focus_set()
                break


def no_search_string(textview: ctk.CTkTextbox) -> None:
    """
    Displays a message box indicating that no search string was found.

    Args:
        self (object): The object instance.

    Returns:
        None
    """
    output_label(textview, "No search string was entered.")


def output_label(textview: ctk.CTkTextbox, message: str) -> None:
    """
    Displays a message label in the GUI.

    Args:
        self (object): The object instance.
        message (str): The message to display.

    Returns:
        None
    """
    # Get the right view/textview
    if "Analysis" in textview.title:
        the_view = textview.master.master.analysisview
    elif "Diagram" in textview.title:
        the_view = textview.master.master.diagramview
    else:
        the_view = textview.master.master.mapview

    the_view.text_message_label.destroy()
    the_view.text_message_label = add_label(
        textview,
        textview,
        message,
        "Orange",
        12,
        "bold",
        0,
        0,
        10,
        40,
        "n",
    )

    the_view.after(3000, textview.delay_event)  # 3-second timer
    the_view.focus_set()


def get_appropriate_color(self: object, color_to_use: str) -> str:
    """Given a color to use, returns the appropriate color to use in the GUI for dark and light modes.

    Args:
        color_to_use (str): color to check against

    Returns:
        color_to_use (str): color to use based on dark or light mode
    """
    # Color matching dictionary: color_to_use: [dark-mode color, light-mode color], ...
    color_match = {"blue": ["LightSkyBlue", "darkblue"], "green": ["lightgreen", "darkgreen"]}

    if self.appearance_mode is None:
        self.appearance_mode = "system"

    for key, color in color_match.items():
        if color_to_use == key and (
            self.appearance_mode == "dark" or (self.appearance_mode == "system" and darkdetect.isDark())
        ):
            # Return the dark-mode color
            return color[0]
        if color_to_use == key:
            # Return the light-mode color
            return color[1]
    return color_to_use


def display_progress_bar(
    progress: dict,
    is_instance_method: bool = False,
) -> None:
    """
    Update and display a progress bar with a specified color based on the progress percentage.

    Args:
        progress (dict): The dictionary containing the progress bar details.
        is_instance_method (bool): Flag to determine if the function is used as a class instance method.

    Returns:
        None: This function does not return anything.
    """
    progress_bar = progress["progress_bar"]
    tenth_increment = progress["tenth_increment"]
    progress_counter = progress["progress_counter"]
    max_data = progress["max_data"]

    # If used as an instance method (Map), adjust the progress_bar reference.
    if is_instance_method:
        progress_bar = progress["progress_bar"].progress_bar
        comp2 = 2
        comp4 = 4
        comp6 = 6
        comp8 = 8
        threshold = progress_counter / tenth_increment
    else:
        # Diagram view
        comp2 = tenth_increment * 2
        comp4 = tenth_increment * 4
        comp6 = tenth_increment * 6
        comp8 = tenth_increment * 8
        threshold = progress_counter

    # Calculate our progress value based on the maximum value and current value.
    progress_value = round((progress_counter / max_data), 2)

    # Determine the progress color based on the current value.
    if threshold <= comp2:
        progress_color = "red"
    elif threshold <= comp4:
        progress_color = "orangered"
    elif threshold <= comp6:
        progress_color = "orange"
    elif threshold <= comp8:
        progress_color = "limegreen"
    else:
        progress_color = "green"
        # If value is over .99, for some reason the progress bar users a value of .02 ratherr than 1.
        # So we have to force it to something just short of 1.
        if progress_counter / max_data >= 0.99:
            progress_value = 0.97

    # Update the progress bar with the current value and color.
    progress_bar.progressbar.set(progress_value)
    progress_bar.progressbar.configure(progress_color=progress_color)
    progress_bar.progressbar.update()

    # Check if an alert needs to be printed (OS X only).
    if (
        platform.system() == "Darwin"
        and progress_bar.progressbar.print_alert
        and round(time.time() * 1000) - progress_bar.progressbar.start_time > 4000
    ):
        print(f"{Colors.Green}You can ignore the error message: 'IMKClient Stall detected, *please Report*...'")
        progress_bar.progressbar.print_alert = False


def find_connector(output_lines: list, line_num: int, start_symbol: str, end_symbol: str) -> tuple:
    """
    Finds the start and end positions for a connector within a line of the diagram.

    Args:
        output_lines (list): The list of strings representing the diagram.
        line_num (int): The line number to search within.
        start_symbol (str): The symbol indicating the start of the connector.
        end_symbol (str): The symbol indicating the end of the connector.

    Returns:
        tuple: (start_position, end_position) if found, otherwise (None, None).
    """
    start_pos = output_lines[line_num].find(start_symbol)
    if start_pos != -1:
        end_pos = output_lines[line_num].find(end_symbol)
        if end_pos != -1:
            return start_pos, end_pos
    return None, None


def find_lower_elbows(
    output_lines: list,
    line_num: int,
    end_elbow: str,
    right_corner_up: str,
    left_corner_down: str,
) -> tuple:
    """
    Finds the positions of the lower elbows in the connector.

    Args:
        output_lines (list): The list of strings representing the diagram.
        line_num (int): The starting line number for the search.
        end_elbow (int): The column position of the end elbow.
        right_corner_up (str): The symbol for the right lower elbow.
        left_corner_down (str): The symbol for the left lower elbow.

    Returns:
        tuple: (next_line, right_lower_elbow, left_lower_elbow)
    """
    found_arrow = False
    while not found_arrow:
        line_num += 1
        if line_num < len(output_lines):
            right_lower_elbow = output_lines[line_num].find(right_corner_up, end_elbow, end_elbow + 1)
            if right_lower_elbow != -1:
                found_arrow = True
                left_lower_elbow = output_lines[line_num].find(left_corner_down)
                if left_lower_elbow == -1:
                    if PrimeItems.program_arguments["debug"]:
                        print(
                            "Rutroh! Missing lower elbow in line",
                            line_num,
                            "(guiutils.py:build_connectors):",
                            output_lines[line_num],
                        )
                    else:
                        logger.error("Missing lower elbow in line %s %s", line_num, output_lines[line_num])
                return line_num, right_lower_elbow, left_lower_elbow
        else:
            return line_num, -1, -1
    return None, None, None


def get_connected_task(output_lines: list, line_num: int, elbow: int, top: bool) -> tuple:
    """
    Finds the connected task in the connector.

    Args:
        output_lines (list): The list of strings representing the diagram.
        line_num (int): The line number to search within.
        elbow (int): The column position of the lower elbow.
        top (bool): True if the tasak is up, False if the task is below.

    Returns:
        tuple: (connected_task, left_position, right_position)
    """
    # Get the line with the task name in it.
    if top:
        while angle not in output_lines[line_num]:
            line_num -= 1
    else:
        while angle not in output_lines[line_num]:
            line_num += 1
    line = output_lines[line_num]

    # Get the left position of the name
    comma_found = False
    search_position = elbow
    while not comma_found:
        if line[search_position] in (",", right_arrow, straight_line, "[", "]"):
            break
        search_position -= 1
    left_position = search_position + 3

    # Get the right position of the name
    comma_found = False
    search_position = left_position
    while not comma_found:
        if (
            len(line) == search_position
            or line[search_position] in (",", "]", "[", "(", bar)
            or line[search_position][0:3] == "    "
        ):
            break
        search_position += 1
    right_position = search_position

    return line[left_position - 1 : right_position].strip(), left_position, right_position


def build_connectors(output_lines: list, line_num: int, diagram_connectors: dict) -> dict:
    """
    Build the connectors for a given line number.

    Args:
        output_lines (list): The list of strings representing the diagram.
        line_num (int): The line number to build the connectors for.
        diagram_connectors (dict): The dictionary to store the connectors information.

    Returns:
        dict: Updated dictionary of connectors.
    """
    # Handle top-down connectors
    start_elbow, end_elbow = find_connector(output_lines, line_num, right_arrow_corner_down, left_arrow_corner_up)
    if start_elbow is not None:
        next_line, right_lower_elbow, left_lower_elbow = find_lower_elbows(
            output_lines,
            line_num,
            end_elbow,
            right_arrow_corner_up,
            left_arrow_corner_down,
        )

        # Build the connector
        diagram_connectors[f"{line_num+1}"] = {
            "start_top": (line_num + 1, start_elbow),
            "end_top": (line_num + 1, end_elbow),
            "start_bottom": (next_line + 1, left_lower_elbow),
            "end_bottom": (next_line + 1, right_lower_elbow),
            "tag": "",
            "extra_bars": [],
            "task_upper": [],
        }

        # Get the connecting task name at above the elbow.
        task_to_highlight, left_position, right_position = get_connected_task(
            output_lines,
            line_num,
            start_elbow,
            True,
        )
        diagram_connectors[f"{line_num+1}"]["task_upper"] = append_item_to_list(
            (task_to_highlight),
            diagram_connectors[f"{line_num+1}"]["task_upper"],
        )

    # Handle bottom-up connectors
    else:
        start_elbow, end_elbow = find_connector(output_lines, line_num, left_arrow_corner_down, left_arrow_corner_up)
        if start_elbow is not None:
            next_line, right_lower_elbow, left_lower_elbow = find_lower_elbows(
                output_lines,
                line_num,
                end_elbow,
                right_arrow_corner_up,
                right_arrow_corner_down,
            )

            # Build the connector
            diagram_connectors[f"{line_num+1}"] = {
                "start_top": (line_num + 1, start_elbow),
                "end_top": (line_num + 1, end_elbow),
                "start_bottom": (next_line + 1, left_lower_elbow),
                "end_bottom": (next_line + 1, right_lower_elbow),
                "tag": "",
                "extra_bars": [],
                "task_upper": [],
            }

            # Get the connecting task name at above the elbow.
            task_to_highlight, left_position, right_position = get_connected_task(
                output_lines,
                line_num,
                start_elbow,
                False,
            )
            diagram_connectors[f"{line_num+1}"]["task_upper"] = append_item_to_list(
                (task_to_highlight),
                diagram_connectors[f"{line_num+1}"]["task_upper"],
            )

    return diagram_connectors


def remove_tags_from_bars_and_names(self: object) -> None:
    """
    Remove the tags from the bars in the diagram.

    This function loops through all of the connectors and Task names in the diagram and removes the tags from each.
    The tags are removed from the bars in the connectors, and the "tag" key in the connector dictionary is set to an empty string.
    """
    for values in self.diagram_connectors.values():
        # Remove the bars from the text widget.
        if values["tag"]:
            line_num = values["start_top"][0]
            number_of_lines_to_highlight = values["start_bottom"][0] - values["start_top"][0] + 1
            for _ in range(number_of_lines_to_highlight):
                self.textview_textbox.tag_remove(
                    values["tag"],
                    f"{line_num}.{values['end_top'][1]!s}",
                    f"{line_num}.{values['end_top'][1]+1!s}",
                )
                line_num += 1
            for bar in values["extra_bars"]:
                self.textview_textbox.tag_remove(values["tag"], f"{bar[0]!s}.{bar[1]!s}", f"{bar[0]!s}.{bar[1]+1!s}")
            values["tag"] = ""

        # Remove the tags in the Task names.
        if values["task_upper"] and len(values["task_upper"]) > 1:
            task = values["task_upper"]
            self.textview_textbox.tag_remove(
                values["tag"],
                f"{task[1]}.{task[2]!s}",
                f"{task[1]}.{task[3]!s}",
            )
