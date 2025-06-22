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
import re
import sys
from functools import cache
from tkinter import TclError, font
from typing import TYPE_CHECKING

import customtkinter as ctk
import darkdetect
from PIL import Image

from maptasker.src.colrmode import set_color_mode
from maptasker.src.diagcnst import (
    angle,
    bar,
    left_arrow_corner_down,
    left_arrow_corner_up,
    right_arrow,
    right_arrow_corner_down,
    right_arrow_corner_up,
    straight_line,
)
from maptasker.src.error import rutroh_error
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
    CLAUDE_MODELS,
    DEEPSEEK_MODELS,
    ERROR_FILE,
    GEMINI_MODELS,
    KEYFILE,
    MODEL_GROUPS,
    NOW_TIME,
    OPENAI_MODELS,
    TAB_NAMES,
    UNNAMED_ITEM,
    VERSION,
    logger,
)
from maptasker.src.xmldata import tasker_object

if TYPE_CHECKING:
    from collections.abc import Callable

    import defusedxml


all_objects = "Display all Projects, Profiles, and Tasks."

# TODO Change this 'changelog' with each release!  New lines (\n) must be added.
CHANGELOG = """
Version 8.0.3 - Change Log\n
### Added\n
- Added: No additions.\n
- Changed: Gemini model 2.5 Pro has been upgraded from the preview model to 'gemini-2.5-pro'.\n
### Fixed\n
- Fixed: Ai-Analysis windoiw is not getting the focus.\n
- Fixed: Numerous bugs when running on Windows 11.\n
- Fixed: Diagram and Map views are not being displayed in the defined background color.\n
- Fixed: The GUI 'hover tip' background and foreground colors are incorrect.\n
"""

default_font_size = 14


# Make sure the single named item exists...that it is a valid name
def valid_item(
    self: object,
    the_name: str,
    element_name: str,
    debug: bool,
    appearance_mode: str,
) -> bool:
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

    # Get the XML data only if it hasn't been loaded yet
    if (
        not PrimeItems.tasker_root_elements["all_projects"]
        and not PrimeItems.tasker_root_elements["all_profiles"]
        and not PrimeItems.tasker_root_elements["all_tasks"]
    ):
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

    # Special case if Task.
    if (
        root_element == PrimeItems.tasker_root_elements["all_tasks"]
        and UNNAMED_ITEM in the_name
    ):
        task_id = get_taskid_from_unnamed_task(the_name)
        return task_id in root_element

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
    PrimeItems.file_to_use = ""  # Get rid of any previous file
    if not PrimeItems.program_arguments["debug"]:
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
        self.display_message_box(
            f"Pinging address {ip_address}.  Please wait...",
            "Green",
        )
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
    with contextlib.suppress(AttributeError):
        self.list_files_query_button.destroy()
    if (
        not self.first_time
    ):  # If first time, don't destory Upgrade and What's New buttons.
        with contextlib.suppress(AttributeError):
            self.list_files_query_button.destroy()
        with contextlib.suppress(
            AttributeError,
        ):  # Destroy upgrade button since file location would sit on top of it.
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


# Get Pypi version and return True if it is newer than our current version.
def is_new_version() -> bool:
    """
    Check if the new version is available
    Args:
        self: The class instance
    Returns:
        bool: True if new version is available, False if not"""
    # Check if newer version of our code is available on Pypi.
    pypi_version_code = get_pypi_version()
    if pypi_version_code:
        pypi_version = pypi_version_code.split("==")[1]
        PrimeItems.last_run = (
            NOW_TIME  # Update last run to now since we are doing the check.
        )
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
    return_code, file_contents = http_request(
        ip_address,
        ip_port,
        file_location,
        "maplist",
        "?xml",
    )

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
    version_indicator = "## ["
    if os.path.isfile("Changelog.md"):
        changelog_dict = {}
        have_first_bracket = False
        change_count = 0
        with open("Changelog.md") as changelog:
            lines = changelog.readlines()
            for line in lines:
                if version_indicator in line or "## Older History Logs" in line:
                    if have_first_bracket:  # If we already have the bracket and encounter another, stop reading
                        break
                    have_first_bracket = True
                    bracket_start_pos = line.find(version_indicator)
                    if bracket_start_pos == -1:
                        continue
                    bracket_end_pos = line.find("]", bracket_start_pos + 4)
                    changelog_dict["version"] = line[
                        bracket_start_pos + 4 : bracket_end_pos
                    ]
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
    Note: The changelog file is created immediately after the program is updated (userintr upgrade_event)
    """
    logger.info("Checking for changelog file.")
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


def add_logo(self, logo_type: str) -> None:  # noqa: ANN001
    """Add a logo to the screen.

    Parameters:
        - self (object): The calling object.
        - logo_type (str): The logo identifier ('maptasker' or 'coffee').

    Returns:
        - None: The function modifies the GUI components directly.
    """
    logo_map = {
        "maptasker": (
            "maptasker_logo_light.png",
            "maptasker_logo_dark.png",
            (190, 50),
            self.sidebar_frame,
            (0, 0),
            "0",
            "0",
            "n",
        ),
        "coffee": (
            "bmc-logo-no-background.png",
            "bmc-logo-no-background.png",
            (36, 54),
            self.tabview.tab("Debug"),
            (5, 3),
            "10",
            "0",
            "se",
        ),
    }
    # Get the path to our logos:
    # current_dir = directory from which we are running.
    # abspath = path of this source code (userintr.py).
    # cwd = directory from which the main program is (main.py)
    current_dir = os.getcwd()
    abspath = os.path.abspath(__file__)
    # cwd = os.path.abspath(os.path.dirname(sys.argv[0]))
    assets_dir = os.path.dirname(abspath).replace("src", "assets")
    # Switch to our temp directory (assets)
    os.chdir(assets_dir)

    if logo_type in logo_map:
        light_img, dark_img, size, parent, grid_pos, padx, pady, sticky = logo_map[
            logo_type
        ]
        my_image = ctk.CTkImage(
            light_image=Image.open(light_img),
            dark_image=Image.open(dark_img),
            size=size,
        )
        try:
            label = ctk.CTkLabel(
                parent,
                image=my_image,
                text="",
                compound="left",
                font=ctk.CTkFont(size=1, weight="bold"),
            )
            label.grid(
                row=grid_pos[0],
                column=grid_pos[1],
                padx=padx,
                pady=pady,
                sticky=sticky,
            )
        except (FileNotFoundError, TypeError, TclError) as e:
            rutroh_error(
                f"Error displaying {logo_type} logo: {e}  Unable to attach Tkinter for image.",
            )
    else:
        rutroh_error("Invalid logo type")
    # Put the directory back to where it should be.
    os.chdir(current_dir)

    if logo_type == "coffee":
        _ = add_button(
            self,
            parent,
            "#246FB6",
            "",
            "",
            self.event_handlers.coffee_event,
            1,
            "Buy Me A Coffee",
            1,
            *grid_pos,
            20,
            10,
            "nw",
        )

    return my_image


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
    padx: int | tuple,
    pady: int | tuple,
    sticky: str,
) -> ctk.CTkLabel:
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
        # Note: If user double-clicks a button, the textbox is not valid on the second click.
        try:
            label_name = ctk.CTkLabel(
                frame,
                text=text,
                text_color=text_color,
                font=ctk.CTkFont(size=font_size, weight=font_weight),
            )
        except TclError:
            return None
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
    fg_color: str | tuple,
    text_color: str | tuple,
    border_color: str,
    command: Callable,
    border_width: int,
    text: str,
    columnspan: int,
    row: int,
    column: int,
    padx: int | tuple,
    pady: int | tuple,
    sticky: str,
) -> ctk.CTkButton:
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
    button_name.grid(
        row=row,
        column=column,
        columnspan=columnspan,
        padx=padx,
        pady=pady,
        sticky=sticky,
    )
    return button_name


# Create a button general routine
def add_option_menu(
    self,  # noqa: ANN001, ARG001
    frame: ctk.CTkFrame,
    command: Callable,
    values: str | list,
    row: int,
    column: int,
    padx: int | tuple,
    pady: int | tuple,
    sticky: str,
) -> ctk.CTkOptionMenu:
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
        - option_menu_name (ctk.CTkOptionMenu): The option menu.
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
    # Make sure Ai model is blank if value is "None"
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

    # Set up for the display line of the API key and model details.
    key_model = PrimeItems.program_arguments["ai_model"]
    # key_to_display = "Unset" if self.ai_apikey == "None" or not self.ai_apikey else "Set"
    key_to_display = "N/A"
    for ai, models in MODEL_GROUPS.items():
        if self.ai_model in models:
            key_model = ai
            if ai == "LLAMA":
                key_to_display = "N/A"
            else:
                apikey_name = f"{key_model.lower()}_key"
                key_to_display = "Unset" if not PrimeItems.ai[apikey_name] else "Set"
            break
    model_to_display = self.ai_model if self.ai_model else "None"

    self.ai_set_label1 = add_label(
        self,
        self.tabview.tab("Analyze"),
        f"{key_model} API Key: {key_to_display}, Model: {model_to_display}",
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
    project_to_display = (
        self.single_project_name if self.single_project_name else "None"
    )
    profile_to_display = (
        self.single_profile_name if self.single_profile_name else "None"
    )
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
    display_prompt = "\n".join(
        self.ai_prompt[i : i + maxlen] for i in range(0, len(self.ai_prompt), maxlen)
    )
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
def get_api_key() -> tuple:
    """
    Retrieves the API key from the specified file.

    This function checks if the KEYFILE exists and if it does, it opens the file and reads the first line. The first line is assumed to be the API key. If the KEYFILE does not exist, it returns the string "None".

    Returns:
        tuple: The file type and the API key if it exists, otherwise "None".
    """
    if os.path.isfile(KEYFILE):
        kind_of_file, contents = detect_and_read_file(KEYFILE)
        if kind_of_file == "text":
            return contents
        if kind_of_file == "pickle":
            PrimeItems.ai["api_key"] = contents["api_key"]
            PrimeItems.ai["openai_key"] = contents["openai_key"]
            PrimeItems.ai["claude_key"] = contents["claude_key"]
            PrimeItems.ai["deepseek_key"] = contents["deepseek_key"]
            with contextlib.suppress(KeyError):
                PrimeItems.ai["gemini_key"] = contents["gemini_key"]
            return PrimeItems.ai["api_key"]
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
        return_code, file_contents = http_request(
            android_ipaddr,
            android_port,
            android_file,
            "file",
            "?download=1",
        )

        # Validate XML file.
        if return_code == 0:
            PrimeItems.program_arguments["gui"] = True
            return_code, error_message = validate_xml_file(
                android_ipaddr,
                android_port,
                android_file,
            )
            if return_code != 0:
                self.display_message_box(error_message, "Red")
                return 1, android_ipaddr, android_port, android_file
        else:
            return 1, android_ipaddr, android_port, android_file

    # File location not provided.  Get the list of all XML files from the Android device and present it to the user.
    else:
        clear_android_buttons(self)
        # Get list from Tasker directory (/Tasker) or system directory (/storage/emulated/0)
        return_code, filelist = get_list_of_files(
            android_ipaddr,
            android_port,
            "/storage/emulated/0/Tasker",
        )
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
        return (
            2,
            "",
            "",
            "",
        )  # Just return with error so the prompt comes up to select file.

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
        _ = add_label(
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
        _ = add_label(
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
        _ = add_label(
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
    The profile names and tasks are cleaned up by removing the "Profile: (Unnamed)" and "Task: ...(Unnamed)" entries.
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
    return_code, projects_to_display, profiles_to_display, tasks_to_display = (
        get_tasker_objects(self)
    )
    if not return_code:
        return False

    # Eliminate the Dummy

    # Make alphabetical
    if projects_to_display:
        projects_to_display.sort()
        projects_to_display.insert(0, "None")
    if profiles_to_display:
        # Filter out dummy profiles created for Tasks with no Profile.
        profiles = [
            profile for profile in profiles_to_display if profile != "No Profile"
        ]
        profiles_to_display = profiles
        profiles_to_display.sort()
        profiles_to_display.insert(0, "None")
    tasks_to_display.insert(0, "None")

    # Display the object pulldowns in 'Analyze' tab
    self.ai_project_optionmenu, self.ai_profile_optionmenu, self.ai_task_optionmenu = (
        display_object_pulldowns(
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
    )

    # Display the object pulldowns in 'Specific Name' tab
    if not projects_to_display:  # If no Projects to display
        projects_to_display = ["None"]
    (
        self.specific_project_optionmenu,
        self.specific_profile_optionmenu,
        self.specific_task_optionmenu,
    ) = display_object_pulldowns(
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
    return True


# Get all Projects, Profiles and Tasks to display
def get_tasker_objects(self) -> tuple:  # noqa: ANN001
    """
    Retrieves the projects, profiles, and tasks available in the XML file.

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
        profiles = [
            value["name"]
            for value in PrimeItems.tasker_root_elements["all_profiles"].values()
        ]
        # tasks = [value["name"] for value in PrimeItems.tasker_root_elements["all_tasks"].values()]
    # We have the Tasker objects.  Collect all Projects, Profiles and Tasks from the tree data.
    else:
        for project in tree_data:
            projects_to_display.append(project["name"])
            for profile in project["children"]:
                with contextlib.suppress(TypeError):
                    profiles.append(profile["name"])
                    tasks.extend(profile["children"])

    # Clean up the object lists by removing anonymous or missing objects.
    if self.list_unnamed_items:
        profiles_to_display = profiles
    else:
        profiles_to_display = [
            profile for profile in profiles if UNNAMED_ITEM not in profile
        ]
    if not projects_to_display:
        projects_to_display = ["No projects found"]
    if not profiles_to_display:
        profiles_to_display = ["No profiles found"]

    # Build list of Task names to display in the GUI pulldown.
    tasks_to_display = list(PrimeItems.tasker_root_elements["all_tasks_by_name"])

    # Check for no tasks.
    if not tasks_to_display:
        tasks_to_display = ["No tasks found"]
    else:
        if not self.list_unnamed_items:
            # Remove unnamed Tasks from the list.
            new_task_list = []
            for task in tasks_to_display:
                if UNNAMED_ITEM in task:
                    continue
                # If the task is not in the list of tasks, add it to the new list.
                new_task_list.append(task)
            # Remove duplicates and sort the list.
            tasks_to_display = list(set(new_task_list))
        tasks_to_display.sort()

    return True, projects_to_display, profiles_to_display, tasks_to_display


# Build a list of Profiles that are under the given project
def build_profiles(
    root: dict,
    profile_ids: list,
    project: defusedxml.ElementTree,
) -> list:
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
                    task_list.append(f"Task: {task['name']}")
                    found_tasks.append(task["name"])  # Keep track of found tasks
        else:
            task_list = ["No Profile Tasks Found"]

        # Get the Profile name.
        profile_name = f"Profile: {profiles[profile]['name']}"

        # Combine the Profile with it's Tasks
        profile_list.append({"name": profile_name, "children": task_list})

    # Now add tasks that are not found in any Profile that belong to the Project
    no_profile_tasks = []
    task_ids = get_ids(
        False,
        PrimeItems.tasker_root_elements["all_projects"][project]["xml"],
        project,
        [],
    )
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
    logger.info("Displaying messages from last run.")
    # See if we have any carryover error messages from last run (rerun).
    if os.path.isfile(ERROR_FILE):
        with open(ERROR_FILE) as error_file:
            error_msg = error_file.read()
            # Handle potential mssing modules
            # if "cria" in error_msg:
            #     self.ai_missing_module = "cria"
            # elif "openai" in error_msg:
            #     self.ai_missing_module = "openai"

            # Handle Ai Response and display it in a new toplevel window
            if "Ai Response" in error_msg:
                self.display_ai_response(error_msg)
                self.display_message_box(
                    f"Analysis response is in a separate Window and saved as {ANALYSIS_FILE}.",
                    "Turquoise",
                )
                self.tabview.set("Analyze")  # Switch to the 'Analyze' tab
            # Some other message.  Just display it in the message box and break it up if needed.
            elif "\n" in error_msg:
                messages = error_msg.split("\n")
                self.clear_messages = True
                for message_line in messages:
                    self.display_message_box(message_line, "Red")
            else:
                self.clear_messages = True
                self.display_message_box(error_msg, "Red")
            # Get rid of error message so we don't display it again.
            os.remove(
                ERROR_FILE,
            )  # Get rid of error message so we don't display it again.

    # Display any error message from other rountines
    if PrimeItems.error_msg:
        self.display_message_box(
            f"{PrimeItems.error_msg} with return code {PrimeItems.error_code}.",
            "Red",
        )


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
def setup_name_error(
    object1_name: str,
    object2_name: str,
    single_name1: str,
    single_name2: str,
) -> None:
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


def set_tasker_object_names(self) -> None:  # noqa: ANN001
    """
    Sets the names to display in the pulldown menus based on the current tasker object names.
    """
    # Define defaults
    defaults = {
        "project": "None",
        "profile": "None",
        "task": "None",
        "display_only": "Display only ",
    }

    if self.single_project_name:
        _set_single_project_name(self, defaults)
    elif self.single_profile_name:
        _set_single_profile_name(self, defaults)
    elif self.single_task_name:
        _set_single_task_name(self, defaults)
    else:
        _set_default_names(self, defaults)


def _set_single_project_name(self: object, defaults: dict) -> None:
    """Handles setting names when a single project name is available."""
    self.specific_name_msg = (
        f"{defaults['display_only']}Project '{self.single_project_name}'"
    )
    try:
        self.specific_project_optionmenu.set(self.single_project_name)
    except AttributeError:
        return
    self.ai_project_optionmenu.set(self.single_project_name)
    self.specific_profile_optionmenu.set(defaults["profile"])
    self.ai_profile_optionmenu.set(defaults["profile"])
    self.specific_task_optionmenu.set(defaults["task"])
    self.ai_task_optionmenu.set(defaults["task"])


def _set_single_profile_name(self: object, defaults: dict) -> None:
    """Handles setting names when a single profile name is available."""
    self.specific_name_msg = (
        f"{defaults['display_only']}Profile '{self.single_profile_name}'"
    )
    try:
        self.specific_profile_optionmenu.set(self.single_profile_name)
    except AttributeError:
        return
    self.ai_profile_optionmenu.set(self.single_profile_name)
    self.ai_project_optionmenu.set(defaults["project"])
    self.specific_project_optionmenu.set(defaults["project"])
    self.specific_task_optionmenu.set(defaults["task"])
    self.ai_task_optionmenu.set(defaults["task"])


def _set_single_task_name(self: object, defaults: dict) -> None:
    """Handles setting names when a single task name is available."""
    self.specific_name_msg = f"{defaults['display_only']}Task '{self.single_task_name}'"
    try:
        self.specific_task_optionmenu.set(self.single_task_name)
    except AttributeError:
        return
    self.ai_task_optionmenu.set(self.single_task_name)
    self.specific_project_optionmenu.set(defaults["project"])
    self.specific_profile_optionmenu.set(defaults["profile"])
    self.ai_project_optionmenu.set(defaults["project"])
    self.ai_profile_optionmenu.set(defaults["profile"])


def _set_default_names(self: object, defaults: dict) -> None:
    """Handles setting names when no specific name is available."""
    self.specific_name_msg = ""
    try:
        self.specific_project_optionmenu.set(defaults["project"])
        if not PrimeItems.tasker_root_elements["all_projects"]:
            self.specific_project_optionmenu.configure(values=["None"])
            self.ai_project_optionmenu.configure(values=["None"])
        if not PrimeItems.tasker_root_elements["all_profiles"]:
            self.specific_profile_optionmenu.configure(values=["None"])
            self.ai_profile_optionmenu.configure(values=["None"])
        if not PrimeItems.tasker_root_elements["all_tasks"]:
            self.specific_task_optionmenu.configure(values=["None"])
            self.ai_task_optionmenu.configure(values=["None"])
        self.specific_profile_optionmenu.set(defaults["profile"])
        self.ai_project_optionmenu.set(defaults["project"])
        self.ai_profile_optionmenu.set(defaults["profile"])
        self.specific_task_optionmenu.set(defaults["task"])
        self.ai_task_optionmenu.set(defaults["task"])
    except AttributeError:
        pass


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
    from maptasker.src.getputer import save_restore_args  # noqa: PLC0415
    from maptasker.src.guiwins import store_windows  # noqa: PLC0415

    # Save windows
    store_windows(self)

    # Save the settings
    temp_args = {value: getattr(self, value) for value in ARGUMENT_NAMES}
    _, _ = save_restore_args(temp_args, self.color_lookup, True)

    # ReRun via a new process, which will load and run the new program/version.
    # Note: this will cause an OS error, 'python[35833:461355] Task policy set failed: 4 ((os/kern) invalid argument)'
    # Note: this current process will not return after this call, but simply be killed.
    print(
        "The following error message can be ignored: 'Task policy set failed: 4 ((os/kern) invalid argument)'.",
    )
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
    self.textbox.configure(
        font=(self.font, 14),
        wrap="word",
        scrollbar_button_color="#6563ff",
    )
    self.hyperlink = ctk.HyperlinkManager(
        self.textbox,
        text_color=get_appropriate_color(self, "blue"),
    )


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


def search_substring_in_list(
    strings: list,
    substring: str,
    stop_on_first_match: bool,
) -> list:
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
    # If this is an Unknown Task or Task in warning dict, we need to search for the Task ID in A Scene as well.
    if "Task: " in substring and "(Unnamed)" in substring:
        # Get the Task ID.
        task_id = get_taskid_from_unnamed_task(substring)
        second_search_string = f"id:{task_id}"
    elif substring[6:] in PrimeItems.task_action_warnings:
        second_search_string = (
            f"id: {PrimeItems.task_action_warnings[substring[6:]]['id']}"
        )
    else:
        second_search_string = ""
    lower_substring = substring.lower()

    # If stop on first match and a Tasker object, then indicate we need an exact match.
    exact_match = bool(stop_on_first_match and tasker_object(substring, True))

    # Go through all data looking for our substring.  Do all compares in lowercase.
    # If we don't find a match, then search on second substring.
    for i, string in enumerate(strings):
        lower_string = string.lower()
        lower_string_len = len(lower_string)
        start = 0
        while start < lower_string_len:
            pos = lower_string.find(lower_substring, start)
            # Do we need to search for a Task in a Scene (ID: task_id)?
            if pos == -1 and second_search_string:
                pos = lower_string.find(second_search_string, start)
                # If we have the "id:task_id" then get the position of the name.
                if pos != -1:
                    lower_substring = lower_substring.replace("task: ", "")
                    pos = lower_string.find(lower_substring, start)
            if pos == -1 or "up one level" in lower_string:
                break

            # Drop here if we have a potential match.
            # If doing an exact match on a Tasker object, m ake sure we have an exact match.
            if exact_match:
                potential_match = lower_string[pos:]
                # Handle possible --Task ... ID:
                pos2 = potential_match.find(" id:")
                if pos2 != -1:
                    potential_match = potential_match[:pos2]
                pos1 = potential_match.find("   ")
                if pos2 != -1:
                    potential_match = potential_match[:pos2]
                pos1 = potential_match.find("   ")
                if pos1 != -1 or (len(potential_match) != len(lower_substring)):
                    new_lower_substring = potential_match[:pos1]
                    if new_lower_substring != lower_substring:
                        break

            # Okay, we have the match!
            matches.append((i, pos))
            if stop_on_first_match:
                return matches
            start = pos + 1  # Move start index forward to continue searching
    return matches


def search_nextprev_string(
    self: object,
    textview: ctk.CTkTextbox,
    direction: str,
) -> None:
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
            # End of search?
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
                    # Point to next search if we didn't just do a 'Top' button.
                    if not textview.top:
                        textview.search_current_line = search_indices[num + 1]
                    else:
                        textview.top = False
                elif direction == "previous":
                    textview.search_current_line = search_indices[num - 1]

                # Add tag to highlight the found text
                temp = textview.search_current_line.split(".")
                end_index = int(temp[1]) + len(textview.search_string)
                textview.textview_textbox.tag_add(
                    "next",
                    textview.search_current_line,
                    f"{temp[0]!s}.{end_index}",
                )
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
    color_match = {
        "blue": ["LightSkyBlue", "darkblue"],
        "green": ["lightgreen", "darkgreen"],
    }

    if self.appearance_mode is None:
        self.appearance_mode = "system"

    for key, color in color_match.items():
        if color_to_use == key and (
            self.appearance_mode == "dark"
            or (self.appearance_mode == "system" and darkdetect.isDark())
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
    # Set values for use in this function.
    tenth_increment = progress["tenth_increment"]
    progress_counter = progress["progress_counter"]
    max_data = progress["max_data"]

    # If used as an instance method (Map), adjust the progress_bar reference.
    if is_instance_method:
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

    if PrimeItems.program_arguments["debug"]:
        print(
            "Display Progressbar",
            progress_value,
            threshold,
            progress_counter,
            max_data,
        )

    # Update the progress bar with the current value and color.
    progress["progress_bar"].progressbar.set(progress_value)
    progress["progress_bar"].progressbar.configure(progress_color=progress_color)
    progress["progress_bar"].progressbar.update()

    # # Check if an alert needs to be printed (OS X only).
    # if (
    #     platform.system() == "Darwin"
    #     and progress
    #     and progress["progress_bar"].progressbar.print_alert
    #     and round(time.time() * 1000) - progress["progress_bar"].progressbar.start_time > 4000
    # ):
    #     print(
    #         f"{Colors.Green}You can ignore the error message: 'IMKClient Stall detected, *please Report*...'",
    #     )
    #     progress["progress_bar"].progressbar.print_alert = False


def find_connector(
    output_lines: list,
    line_num: int,
    start_symbol: str,
    end_symbol: str,
) -> tuple:
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
            right_lower_elbow = output_lines[line_num].find(
                right_corner_up,
                end_elbow,
                end_elbow + 1,
            )
            if right_lower_elbow != -1:
                found_arrow = True
                left_lower_elbow = output_lines[line_num].find(left_corner_down)
                if left_lower_elbow == -1:
                    rutroh_error(
                        f"Missing left lower elbow in line {line_num} guiutils.py:build_connectors line:\n{output_lines[line_num]}",
                    )
                return line_num, right_lower_elbow, left_lower_elbow
        else:
            return line_num, -1, -1
    return None, None, None


def get_connected_task(
    output_lines: list,
    line_num: int,
    elbow: int,
    top: bool,
) -> tuple:
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

    return (
        line[left_position - 1 : right_position].strip(),
        left_position,
        right_position,
    )


def build_connectors(
    output_lines: list,
    line_num: int,
    diagram_connectors: dict,
) -> dict:
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
    start_elbow, end_elbow = find_connector(
        output_lines,
        line_num,
        right_arrow_corner_down,
        left_arrow_corner_up,
    )
    if start_elbow is not None:
        next_line, right_lower_elbow, left_lower_elbow = find_lower_elbows(
            output_lines,
            line_num,
            end_elbow,
            right_arrow_corner_up,
            left_arrow_corner_down,
        )

        # Build the connector
        diagram_connectors[f"{line_num + 1}"] = {
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
        diagram_connectors[f"{line_num + 1}"]["task_upper"] = append_item_to_list(
            (task_to_highlight),
            diagram_connectors[f"{line_num + 1}"]["task_upper"],
        )

    # Handle bottom-up connectors
    else:
        start_elbow, end_elbow = find_connector(
            output_lines,
            line_num,
            left_arrow_corner_down,
            left_arrow_corner_up,
        )
        if start_elbow is not None:
            next_line, right_lower_elbow, left_lower_elbow = find_lower_elbows(
                output_lines,
                line_num,
                end_elbow,
                right_arrow_corner_up,
                right_arrow_corner_down,
            )

            # Build the connector
            diagram_connectors[f"{line_num + 1}"] = {
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
            diagram_connectors[f"{line_num + 1}"]["task_upper"] = append_item_to_list(
                (task_to_highlight),
                diagram_connectors[f"{line_num + 1}"]["task_upper"],
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
            number_of_lines_to_highlight = (
                values["start_bottom"][0] - values["start_top"][0] + 1
            )
            for _ in range(number_of_lines_to_highlight):
                self.textview_textbox.tag_remove(
                    values["tag"],
                    f"{line_num}.{values['end_top'][1]!s}",
                    f"{line_num}.{values['end_top'][1] + 1!s}",
                )
                line_num += 1
            for bar in values["extra_bars"]:
                self.textview_textbox.tag_remove(
                    values["tag"],
                    f"{bar[0]!s}.{bar[1]!s}",
                    f"{bar[0]!s}.{bar[1] + 1!s}",
                )
            values["tag"] = ""

        # Remove the tags in the Task names.
        if values["task_upper"] and len(values["task_upper"]) > 1:
            task = values["task_upper"]
            self.textview_textbox.tag_remove(
                values["tag"],
                f"{task[1]}.{task[2]!s}",
                f"{task[1]}.{task[3]!s}",
            )


def kill_the_progress_bar(progress_bar: dict, remove_windows: bool = False) -> None:
    """
    Stop and destroy the progress bar. and any open views.

    Args:
        progress_bar (dict): The dictionary containing the progress bar information.

    Returns:
        None
    """
    # Make sure we have a progressbar.
    if not progress_bar:
        return
    # Keep import here to avoid circular import
    from maptasker.src.guiwins import save_window_position  # noqa: PLC0415

    # Save the window position in our main window (self=MyGui).
    if PrimeItems.progressbar:
        PrimeItems.mygui.progressbar_window_position = save_window_position(
            progress_bar["progress_bar"],
        )
        # Get rid of the progressbar
        progress_bar["progress_bar"].progressbar.stop()
        progress_bar["progress_bar"].progressbar.destroy()
        progress_bar["progress_bar"].destroy()
        progress_bar.clear()
        PrimeItems.progressbar.clear()
        # Get rid of any open views.
        if remove_windows:
            for window_attr in [
                "mapview_window",
                "diagramview_window",
                "treeview_window",
            ]:
                window = getattr(PrimeItems.mygui, window_attr, None)
                if window is not None:
                    window.destroy()
                    setattr(PrimeItems.mygui, window_attr, None)
    # If we don't have PrimeItems.progressbar, we have a runaway situation (tkinter bug).
    # Just destory the window.
    else:
        progress_bar = {}
        PrimeItems.program_arguments["guiview"] = True


def get_profiles_in_project(project_name: str) -> str:
    r"""
    Retrieves and returns a string of profile names for a given project.

    Args:
        project_name (str): The name of the project for which to retrieve profile names.

    Returns:
        str: A string containing the list of profile names associated with the project,
            formatted as "Profiles:\n" followed by a comma-separated list of names.
            Returns an empty string if no profiles are found.
    """
    # Get the Project's profile Ids.
    pids = get_ids(
        True,
        PrimeItems.tasker_root_elements["all_projects"][project_name]["xml"],
        project_name,
        [],
    )
    # Get all of the Profiles in the Project
    profile_names = [
        PrimeItems.tasker_root_elements["all_profiles"][pid]["name"] for pid in pids
    ]
    if pids:
        return profile_names
    return ""


def get_tasks_in_project(project_name: str) -> str:
    r"""
    Retrieves and returns a string of task names for a given project.

    Args:
        project_name (str): The name of the project.

    Returns:
        str: A string containing the list of task names associated with the project,
            formatted as "Tasks:\n" followed by a comma-separated list of names.
            Returns an empty string if no tasks are found.
    """
    task_names = []
    if not project_name:
        return task_names

    # Get the Project's Task Ids.
    tids = get_ids(
        False,
        PrimeItems.tasker_root_elements["all_projects"][project_name]["xml"],
        project_name,
        [],
    )
    # Get the Project's Profile Ids.
    pids = get_ids(
        True,
        PrimeItems.tasker_root_elements["all_projects"][project_name]["xml"],
        project_name,
        [],
    )
    # Get all of the Tasks in the Profile
    task_names = [
        PrimeItems.tasker_root_elements["all_tasks"][tid]["name"] for tid in tids
    ]
    # Include the Tasks under Profiles with no name.
    if pids:
        # Go through all Profiles in Project loking for anonymous names.
        for pid in pids:
            profile = PrimeItems.tasker_root_elements["all_profiles"][pid]
            possible_task = None
            if profile["name"].startswith("*"):
                possible_task = profile["xml"].find("mid0")
                if possible_task is None:
                    possible_task = profile["xml"].find("mid1")
                if possible_task is not None:
                    task_names.append(
                        PrimeItems.tasker_root_elements["all_tasks"][
                            possible_task.text
                        ]["name"],
                    )

        # Remove duplicates and sort the list.
        task_names = list(set(task_names))
        task_names.sort()
    return task_names


def merge_lists(list1: list, list2: list) -> tuple:
    """
    Merge two lists into a single list of pairs.

    Args:
        list1 (list): The first list to merge.
        list2 (list): The second list to merge.

    Returns:
        list: A list of pairs, where each pair is a tuple containing one element from
            each of the two input lists, in order. The lists are extended with None
            to the maximum length of the two lists.
    """
    # Find the maximum length of the two lists
    max_length = max(len(list1), len(list2))

    # Make sure we have a valid list
    if not list1:
        list1 = [" "]
    if not list2:
        list2 = [" "]

    # Extend both lists to the same length with None (or any placeholder)
    list1.extend([""] * (max_length - len(list1)))
    list2.extend([""] * (max_length - len(list2)))

    # Merge the lists into pairs and return it.
    return [(list1[i], list2[i]) for i in range(max_length)]


def parse_pairs_to_columns(pairs: list) -> str:
    """
    Parses a list of string pairs into two aligned columns.

    Args:
        pairs (list of tuples): A list of (string1, string2) pairs.

    Returns:
        str: A string representing the two-column formatted text.
    """
    # Find the maximum width of the first column
    max_width_col1 = 0
    for pair in pairs:
        max_width_col1 = max(len(pair[0]), max_width_col1)
    max_width_col1 += 2

    # Format each pair into two columns
    formatted_lines = [f"{pair[0].ljust(max_width_col1)}{pair[1]}" for pair in pairs]

    # Join all lines with a newline character
    return "\n".join(formatted_lines)


# Window is getting closed. Save the window position.
def on_closing(self: object) -> None:
    """Save the window position and close the window."""
    window_position = self.wm_geometry()
    title = self.wm_title()

    # Mapping keywords to their corresponding master attributes
    window_position_map = {
        "Diagram": "diagram_window_position",
        "Progress": "progressbar_window_position",
        "Analysis": "ai_analysis_window_position",
        "Tree": "tree_window_position",
        "Map View": "map_window_position",
        "API": "apikey_window_position",
    }
    if "Progress" in title:
        progressbar = PrimeItems.progressbar or self.progressbar
        kill_the_progress_bar(progressbar, remove_windows=True)
        return
    # Find the window being closed and save it's position.
    for keyword, attribute in window_position_map.items():
        # If this is for the progressbar, then handle separately.
        if keyword in title:
            setattr(self.master, attribute, window_position)
            break

    # Special handling if this is our main windows.
    if "Runtime" in title:
        # Save the window position on closure
        self.event_handlers.exit_program_event()

    self.destroy()


import pickle


def detect_and_read_file(file_path: object) -> tuple:
    """
    Detects the file type and reads its content.

    Args:
        file_path (object): The path to the file to be read.

    Returns:
        tuple: A tuple containing the file type and its content.
    """
    try:
        # Try opening the file as a pickle
        with open(file_path, "rb") as file:
            content = pickle.load(file)  # noqa: S301
        return "pickle", content  # noqa: TRY300
    except (pickle.UnpicklingError, EOFError):
        pass

    try:
        # Try opening the file as text
        with open(file_path, encoding="utf-8") as file:
            content = file.read()
        return "text", content  # noqa: TRY300
    except UnicodeDecodeError:
        pass

    return "None", None


def prefix_and_sort(strings: list[str], name: str) -> list[str]:
    """
    Prefixes each string in a list with a given name and returns the modified list sorted.

    Args:
        strings: A list of strings.
        name: The name to prefix each string with.

    Returns:
        A new list of strings with each original string prefixed by `name`, sorted alphabetically.
    """

    prefixed_strings = [f"{name}: {s}" for s in strings]
    prefixed_strings.sort()
    return prefixed_strings


@cache
def get_item_xml(item_type: str, item_name: str) -> defusedxml.Element | None:
    """
    Retrieve the XML element for a given item type and name.

    Args:
        self (object): The instance of the class.
        item_type (str): The type of the item (e.g., "Task").
        item_name (str): The name of the item.

    Returns:
        defusedxml.Element | None: The XML element if found, otherwise None.
    """
    if item_type == "Task":
        return next(
            (
                v["xml"]
                for v in PrimeItems.tasker_root_elements["all_tasks"].values()
                if v["name"] == item_name
            ),
            None,
        )
    return PrimeItems.tasker_root_elements["all_projects"].get(item_name, {}).get("xml")


def set_ai_key(self: object, model: str) -> None:
    """
    Set the API key for the AI service.

    Args:
        self (object): The instance of the class.
        model (str): The model name for which to set the API key.

    Returns:
        None
    """
    # Set the appropriate API key based on the mdeol chosen.
    model_keys = {
        **dict.fromkeys(OPENAI_MODELS, "openai_key"),
        **dict.fromkeys(CLAUDE_MODELS, "claude_key"),
        **dict.fromkeys(DEEPSEEK_MODELS, "deepseek_key"),
        **dict.fromkeys(GEMINI_MODELS, "gemini_key"),
    }
    self.ai_apikey = PrimeItems.ai.get(model_keys.get(model, ""), "")
    return bool(self.ai_apikey)


def align_text(text: str, column: int) -> str:
    """
    Aligns the given text so that its first non-&nbsp; character starts at the specified column.

    :param text: The input string where '&nbsp;' is treated as a space.
    :param column: The desired starting column for the first non-&nbsp; character.
    :return: The aligned string.
    """
    nbsp = "&nbsp;"
    stripped_text = text.lstrip(nbsp)  # Remove leading '&nbsp;' characters
    leading_spaces = (len(text) - len(stripped_text)) // len(
        nbsp,
    )  # Count '&nbsp;' as spaces
    adjusted_column = max(0, column - leading_spaces)  # Ensure non-negative padding

    return (nbsp * adjusted_column) + text  # Adjust spacing to align correctly


def destroy_hover_tooltip(tooltip: object | list) -> None:
    """
    Destroy the hover tooltip if it exists.

    Args:
        tooltip (object): The instance of the tk.label or list.

    Returns:
        None
    """
    if tooltip:
        if isinstance(tooltip, list):
            try:
                tooltip[0].destroy()
                tooltip[1].destroy()
            except AttributeError:
                pass
        else:
            tooltip.destroy()
    tooltip = None


def validate_tkinter_geometry(geometry_string: str) -> bool:
    """
    Validates a tkinter window geometry string with additional constraints.

    Args:
        geometry_string (str): The geometry string in the format
                                 'width x height + position_x + position_y'.

    Returns:
        bool: True if the geometry string is valid and meets the constraints,
              False otherwise.
    """
    pattern = re.compile(r"^\d+x\d+\+\d+\+\d+$")
    if not pattern.match(geometry_string):
        return False

    try:
        parts = geometry_string.replace("+", " ").replace("x", " ").split()
        width = int(parts[0])
        height = int(parts[1])
        pos_x = int(parts[2])
        pos_y = int(parts[3])

        if width < 300:
            print("Error: Width must be at least 300.")
            return False
        if height < 50:
            print("Error: Height must be at least 50.")
            return False
        if pos_x < 0:
            print("Error: Position X must be a non-negative number.")
            return False
        if pos_y < 0:
            print("Error: Position Y must be a non-negative number.")
            return False

        return True  # noqa: TRY300
    except ValueError:
        print("Error: Invalid numeric value in geometry string.")
        return False


def extract_number_from_line(line: str) -> str | None:
    """
    Checks if a string ends with '.n' or '.nn' or '.nnn' (where 'n' represents a digit)
    and returns the number part as a string. Leading zeros are not required.

    Args:
      line: The input string.

    Returns:
      The number part as a string if the line ends with a dot followed by one or more digits, otherwise None.
    """
    match = re.search(r"\.(\d+)$", line)
    if match:
        return match.group(1)
    return None


def find_the_line(
    textbox: ctk.CTkTextbox,
    line: str,
    text_line_num: str,
) -> tuple[str, str]:
    """
    Searches for a line containing a specific substring in a CTkTextbox, starting from a given line number and moving upwards.

    Args:
        textbox (ctk.CTkTextbox): The text widget to search in.
        line (str): The substring to search for within each line.
        text_line_num (str): The starting line number as a string.

    Returns:
        tuple[str, str]: A tuple containing the found line number, the line content, and a boolean indicating if the line was not found.
    """
    line_to_get = text_line_num
    dont_got_line = True
    # Search the lines in reverse order for the originating line number.
    while dont_got_line and line_to_get != "0":
        # Get the line and check for the owner name.
        idx = f"{line_to_get}.0"
        prev_line = textbox.get(idx, idx + " lineend")
        if line in prev_line:
            dont_got_line = False
            break
        # If not found, decrement the line number.
        line_to_get = str(int(line_to_get) - 1)

    # Convert the line number back to a string and return everything needed.
    line_to_get = str(int(line_to_get) - 1)
    return line_to_get, prev_line, dont_got_line


def get_taskid_from_unnamed_task(unnamed_task: str) -> str:
    """
    Extracts the task ID from an unnamed task string.

    Args:
        unnamed_task (str): The unnamed task string.

    Returns:
        str: The extracted task ID.
    """
    # Extract the task ID from the unnamed task string
    position = unnamed_task.rfind(".")
    if position != -1:
        return unnamed_task[position + 1 :].split(" (Unnamed)")[0]

    rutroh_error(f"Error.  Missing period for task ID in Taask name: '{unnamed_task}'")
    return unnamed_task.split(".")[1].strip()


def set_tab_to_use(self: object) -> None:
    """Set the Tab to display as the last tab used."""
    if self.tab_to_use:
        self.tabview.set(self.tab_to_use)
    else:
        self.tabview.set(TAB_NAMES[0])
