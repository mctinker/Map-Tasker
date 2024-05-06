"""Utilities used by GUI"""

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
from tkinter import TclError, font, ttk
from typing import TYPE_CHECKING

import customtkinter as ctk
from PIL import Image, ImageTk

from maptasker.src.colrmode import set_color_mode
from maptasker.src.lineout import LineOut
from maptasker.src.maputils import (
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
    CHANGELOG_FILE,
    ERROR_FILE,
    KEYFILE,
    LLAMA_MODELS,
    NOW_TIME,
    OPENAI_MODELS,
    VERSION,
)

if TYPE_CHECKING:
    from datetime import datetime

# TODO Change this 'changelog' with each release!  New lines (\n) must be added.
CHANGELOG = """
Version 4.0/4.0.1 - (Major) Change Log\n
This version introduces Ai Analysis.\n
## Added\n
- Added: Ai analysis support for Profiles and Tasks: both ChatGPT (server-based) and (O)llama (local-based).  See 'Analyze' tab.\n
- Added: Display the current file in GUI.\n
- Added: A new 'Get Local XML' button has been added to enable the GUI to get the local XML file and validate it for analysis.\n
## Changed\n
- Changed: GUI color settings are now displayed in their colors on the startup of the GUI.\n
- Changed: GUI warning messages are now displayed in orange rather than red.\n
## Fixed\n
- Fixed: The program gets runtime errors if the settings saved file is corrupted.\n
- Fixed: The settings are not properly saved upon exit from the GUI.\n
- Fixed: Removed error message 'Program canceled by user (killed GUI)' if the 'Exit' button is selected.\n
- Fixed: If the Android file location is specified on startup and the file is found on the local drive from the previous run, then use it and don't prompt again for it.\n
"""
default_font_size = 14

# Set up for access to icons
CURRENT_PATH = os.path.dirname(os.path.realpath(__file__))
ICON_DIR = os.path.join(CURRENT_PATH, "../assets", "icons")
ICON_PATH = {
    "close": (os.path.join(ICON_DIR, "close_black.png"), os.path.join(ICON_DIR, "close_white.png")),
    # "images": list(os.path.join(ICON_DIR, f"image{i}.jpg") for i in range(1, 4)),
    "eye1": (os.path.join(ICON_DIR, "eye1_black.png"), os.path.join(ICON_DIR, "eye1_white.png")),
    "eye2": (os.path.join(ICON_DIR, "eye2_black.png"), os.path.join(ICON_DIR, "eye2_white.png")),
    "info": os.path.join(ICON_DIR, "info.png"),
    "warning": os.path.join(ICON_DIR, "warning.png"),
    "error": os.path.join(ICON_DIR, "error.png"),
    "left": os.path.join(ICON_DIR, "left.png"),
    "right": os.path.join(ICON_DIR, "right.png"),
    "warning2": os.path.join(ICON_DIR, "warning2.png"),
    "loader": os.path.join(ICON_DIR, "loader.gif"),
    "icon": os.path.join(ICON_DIR, "icon.png"),
    "arrow": os.path.join(ICON_DIR, "arrow.png"),
    "image": os.path.join(ICON_DIR, "image.png"),
}


# ##################################################################################
# Make sure the single named item exists...that it is a valid name
# ##################################################################################
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


# ##################################################################################
# Get the XML data and setup Primeitems
# ##################################################################################
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
    PrimeItems.program_arguments["debug"] = debug
    PrimeItems.program_arguments["gui"] = True
    PrimeItems.colors_to_use = set_color_mode(appearance_mode)
    PrimeItems.output_lines = LineOut()

    return get_data_and_output_intro(False)


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
    with contextlib.suppress(AttributeError):  # Destroy upgrade button since file location would sit on top of it.
        self.upgrade_button.destroy()

    self.get_backup_button = self.display_backup_button(
        "Get XML from Android Device",
        "#246FB6",
        "#6563ff",
        self.get_backup_event,
    )


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
    with open(CHANGELOG_FILE, "w") as changelog_file:
        changelog_file.write(CHANGELOG)


# ##################################################################################
# Read the change log file, add it to the messages to be displayed and then remove it.
# ##################################################################################
def check_for_changelog(self) -> None:  # noqa: ANN001
    """Function to check for a changelog file and add its contents to a message if the current version is correct.
    Parameters:
        - self (object): The object that the function is being called on.
    Returns:
        - None: The function does not return anything, but updates the message attribute of the object.
    Processing Logic:
        - Check if the changelog file exists.
        - If it exists, prepare to display changes and remove the file so we only display the changes once."""
    # TODO Test changelog before posting to PyPi.  Comment it out after testing.
    #self.message = CHANGELOG

    if os.path.isfile(CHANGELOG_FILE):
        self.message = CHANGELOG
        os.remove(CHANGELOG_FILE)


# ##################################################################################
# Initialize the GUI (_init_ method)
# ##################################################################################
def initialize_gui(self) -> None:  # noqa: ANN001
    """Initializes the GUI by initializing variables and adding a logo.
    Parameters:
        - self (class): The class object.
    Returns:
        - None: Does not return anything.
    Processing Logic:
        - Calls initialize_variables function.
        - Calls add_logo function."""
    initialize_variables(self)
    add_logo(self)


# ##################################################################################
# Initialize the GUI varliables (e..g _init_ method)
# ##################################################################################
def initialize_variables(self) -> None:  # noqa: ANN001
    """
    Initialize variables for the MapTasker Runtime Options window.
    """
    self.android_ipaddr = ""
    self.android_port = ""
    self.android_file = ""
    self.appearance_mode = None
    self.bold = None
    self.color_labels = None
    self.color_lookup = None
    self.color_text_row = None
    self.debug = None
    self.display_detail_level = None
    self.preferences = None
    self.conditions = None
    self.everything = None
    self.taskernet = None
    self.exit = None
    self.fetched_backup_from_android = False
    self.file = None
    self.font = None
    self.go_program = None
    self.gui = True
    self.highlight = None
    self.indent = None
    self.italicize = None
    self.named_item = None
    self.rerun = None
    self.reset = None
    self.restore = False
    self.runtime = False
    self.save = False
    self.single_profile_name = None
    self.single_project_name = None
    self.single_task_name = None
    self.twisty = None
    self.underline = None
    self.outline = False
    self.pretty = False
    self.toplevel_window = None
    PrimeItems.program_arguments["gui"] = True
    self.list_files = False
    self.ai_apikey = None
    self.ai_model = None
    self.ai_analysis = None
    self.ai_missing_module = None

    self.title("MapTasker Runtime Options")
    # Overall window dimensions
    self.geometry("1100x900")

    # configure grid layout (4x4)
    self.grid_columnconfigure(1, weight=1)
    self.grid_columnconfigure((2, 3), weight=0)
    self.grid_rowconfigure((0, 3), weight=1)

    # load and create background image

    # create sidebar frame with widgets on the left side of the window.
    self.sidebar_frame = ctk.CTkFrame(self, width=140, corner_radius=0)
    self.sidebar_frame.configure(bg_color="black")
    self.sidebar_frame.grid(row=0, column=0, rowspan=17, sticky="nsew")
    # Define sidebar background frame with 17 rows
    self.sidebar_frame.grid_rowconfigure(17, weight=1)


# ##################################################################################
# Add the MapTasker icon to the screen
# ##################################################################################
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


# ##################################################################################
# Create a label general routine
# ##################################################################################
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
        text_color = "#FFFFFF"
    label_name = ctk.CTkLabel(
        frame,
        text=text,
        text_color=text_color,
        font=ctk.CTkFont(size=font_size, weight=font_weight),
    )
    label_name.grid(row=row, column=column, padx=padx, pady=pady, sticky=sticky)
    return label_name


# ##################################################################################
# Create a checkbox general routine
# ##################################################################################
def add_checkbox(
    self,  # noqa: ANN001, ARG001
    frame: ctk.CTkFrame,
    command: object,
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


# ##################################################################################
# Create a button general routine
# ##################################################################################
def add_button(
    self,  # noqa: ANN001, ARG001
    frame: ctk.CTkFrame,
    fg_color: str,
    text_color: str,
    border_color: str,
    command: object,
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


# ##################################################################################
# Create a button general routine
# ##################################################################################
def add_option_menu(
    self,  # noqa: ANN001, ARG001
    frame: ctk.CTkFrame,
    command: object,
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


# ##################################################################################
# Define all of the menu elements
# ###################################################################################
def initialize_screen(self) -> None:  # noqa: ANN001
    # Add grid title
    """Initializes the screen with various display options and settings.
    Parameters:
        - self (object): The object to which the function belongs.
    Returns:
        - None: This function does not return any value.
    Processing Logic:
        - Creates a grid title and adds it to the sidebar frame.
        - Defines the first grid / column for display detail level.
        - Defines the second grid / column for checkboxes related to display options.
        - Defines the third grid / column for buttons related to program settings.
        - Creates a textbox for displaying help information.
        - Creates a tabview for setting specific names, colors, and debug options.
        - Defines the fourth grid / column for checkboxes related to debug options.
        - Defines the sixth grid / column for checkboxes related to runtime settings."""

    # Display the frame title
    self.logo_label = add_label(self, self.sidebar_frame, "Display Options", "", 20, "bold", 0, 0, 20, (60, 10), "s")

    # Start first grid / column definitions

    # Display Detail Level
    self.detail_label = add_label(
        self,
        self.sidebar_frame,
        "Display Detail Level:",
        "",
        0,
        "normal",
        1,
        0,
        20,
        (10, 0),
        "",
    )
    self.sidebar_detail_option = add_option_menu(
        self,
        self.sidebar_frame,
        self.detail_selected_event,
        ["0", "1", "2", "3", "4"],
        2,
        0,
        20,
        (10, 10),
        "",
    )

    # Display 'Everything' checkbox
    self.everything_checkbox = add_checkbox(
        self,
        self.sidebar_frame,
        self.everything_event,
        "Just Display Everything!",
        3,
        0,
        20,
        10,
        "w",
        "",
    )

    # Display 'Condition' checkbox
    self.condition_checkbox = add_checkbox(
        self,
        self.sidebar_frame,
        self.condition_event,
        "Display Profile and Task Action Conditions",
        4,
        0,
        20,
        10,
        "w",
        "",
    )

    # Display 'TaskerNet' checkbox
    self.taskernet_checkbox = add_checkbox(
        self,
        self.sidebar_frame,
        self.taskernet_event,
        "Display TaskerNet Info",
        5,
        0,
        20,
        10,
        "w",
        "",
    )

    # Display 'Tasker Preferences' checkbox
    self.preferences_checkbox = add_checkbox(
        self,
        self.sidebar_frame,
        self.preferences_event,
        "Display Tasker Preferences",
        6,
        0,
        20,
        10,
        "w",
        "",
    )

    # Display 'Twisty' checkbox
    self.twisty_checkbox = add_checkbox(
        self,
        self.sidebar_frame,
        self.twisty_event,
        "Hide Task Details Under Twisty",
        7,
        0,
        20,
        10,
        "w",
        "",
    )

    # Display 'directory' checkbox
    self.directory_checkbox = add_checkbox(
        self,
        self.sidebar_frame,
        self.directory_event,
        "Display Directory",
        8,
        0,
        20,
        10,
        "w",
        "",
    )

    # Outline
    self.outline_checkbox = add_checkbox(
        self,
        self.sidebar_frame,
        self.outline_event,
        "Display Configuration Outline",
        9,
        0,
        20,
        10,
        "w",
        "",
    )

    # Pretty Output
    self.pretty_checkbox = add_checkbox(
        self,
        self.sidebar_frame,
        self.pretty_event,
        "Display Prettier Output",
        10,
        0,
        20,
        10,
        "w",
        "",
    )

    # Names: Bold / Highlight / Italicise / Underline
    self.display_names_label = add_label(
        self,
        self.sidebar_frame,
        "Project/Profile/Task/Scene Names:",
        "",
        0,
        "normal",
        11,
        0,
        20,
        10,
        "s",
    )

    # Bold
    self.bold_checkbox = add_checkbox(self, self.sidebar_frame, self.names_bold_event, "Bold", 12, 0, 20, 0, "ne", "")

    # Italicize
    self.italicize_checkbox = add_checkbox(
        self,
        self.sidebar_frame,
        self.names_italicize_event,
        "italicize",
        12,
        0,
        20,
        0,
        "nw",
        "",
    )

    # Highlight
    self.highlight_checkbox = add_checkbox(
        self,
        self.sidebar_frame,
        self.names_highlight_event,
        "Highlight",
        13,
        0,
        20,
        5,
        "ne",
        "",
    )

    # Underline
    self.underline_checkbox = add_checkbox(
        self,
        self.sidebar_frame,
        self.names_underline_event,
        "Underline",
        13,
        0,
        20,
        5,
        "nw",
        "",
    )

    # Indentation
    self.indent_label = add_label(
        self,
        self.sidebar_frame,
        "If/Then/Else Indentation Amount:",
        "",
        0,
        "normal",
        14,
        0,
        20,
        10,
        "s",
    )

    # Indentation Amount
    self.indent_option = add_option_menu(
        self,
        self.sidebar_frame,
        self.indent_selected_event,
        ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
        15,
        0,
        0,
        (0, 30),
        "n",
    )

    # Screen Appearance: Light / Dark / System
    self.appearance_mode_label = add_label(
        self,
        self.sidebar_frame,
        "Appearance Mode:",
        "",
        0,
        "normal",
        16,
        0,
        0,
        (0, 10),
        "s",
    )

    self.appearance_mode_optionemenu = add_option_menu(
        self,
        self.sidebar_frame,
        self.change_appearance_mode_event,
        ["Light", "Dark", "System"],
        17,
        0,
        0,
        (0, 45),
        "",
    )

    # 'Tree View' button definition
    self.treeview_button = add_button(
        self,
        self.sidebar_frame,
        "#246FB6",
        "",
        "",
        self.treeview_event,
        2,
        "Tree View",
        1,
        17,
        0,
        0,
        0,
        "n",
    )
    #  Query ? button
    self.treeview_query_button = add_button(
        self,
        self.sidebar_frame,
        "#246FB6",
        ("#0BF075", "#ffd941"),
        "#1bc9ff",
        self.treeview_query_event,
        1,
        "?",
        1,
        17,
        0,
        (200, 0),
        (0, 0),
        "n",
    )
    self.treeview_query_button.configure(width=20)

    # 'Reset Settings' button definition
    self.reset_button = add_button(
        self,
        self.sidebar_frame,
        "#246FB6",
        "",
        "",
        self.reset_settings_event,
        2,
        "Reset Options",
        1,
        18,
        0,
        20,
        20,
        "s",
    )

    # Start second grid / column definitions

    # Font to use
    self.font_label = add_label(self, self, "Font To Use In Output:", "", 0, "normal", 6, 1, 20, 10, "sw")

    # Get fonts from TkInter
    font_items, res = get_monospace_fonts()
    # Delete the tkroot obtained by get_monospace_fonts
    if PrimeItems.tkroot is not None:
        del PrimeItems.tkroot
        PrimeItems.tkroot = None
    self.font_optionemenu = add_option_menu(
        self,
        self,
        self.font_event,
        font_items,
        7,
        1,
        20,
        0,
        "nw",
    )
    self.font_optionemenu.set(res[0])

    # Save settings button
    self.save_settings_button = add_button(
        self,
        self,
        "#6563ff",
        "",
        "",
        self.save_settings_event,
        2,
        "Save Settings",
        1,
        8,
        1,
        20,
        0,
        "sw",
    )

    # Restore settings button
    self.restore_settings_button = add_button(
        self,
        self,
        "#6563ff",
        "",
        "",
        self.restore_settings_event,
        2,
        "Restore Settings",
        1,
        9,
        1,
        20,
        10,
        "nw",
    )

    # Report Issue
    self.report_issue_button = add_button(
        self,
        self,
        "",
        "",
        "",
        self.report_issue_event,
        2,
        "Report Issue",
        1,
        10,
        1,
        20,
        0,
        "nw",
    )

    # 'Clear Messages' button definition
    self.reset_button = add_button(
        self,
        self,
        "#246FB6",
        "",
        "",
        self.clear_messages_event,
        2,
        "Clear Messages",
        1,
        5,
        1,
        0,
        0,
        "s",
    )
    # 'Get Backup Settings' button definition
    self.get_backup_button = self.display_backup_button(
        "Get XML from Android Device",
        "#246FB6",
        "#6563ff",
        self.get_backup_event,
    )
    # 'Get local XML' button
    self.getxml_button = add_button(
        self,
        self,
        "",
        "",
        "",
        self.getxml_event,
        2,
        "Get Local XML",
        1,
        6,
        2,
        (20, 20),
        (10, 10),
        "e",
    )

    # 'Display Help' button definition
    self.help_button = add_button(
        self,
        self,
        "#246FB6",
        ("#0BF075", "#ffd941"),
        "",
        self.help_event,
        2,
        "Display Help",
        1,
        7,
        2,
        (0, 20),
        (10, 5),
        "se",
    )

    # 'Backup Help' button definition
    self.backup_help_button = add_button(
        self,
        self,
        "#246FB6",
        ("#0BF075", "#ffd941"),
        "",
        self.backup_help_event,
        2,
        "Get Android Help",
        1,
        8,
        2,
        (0, 20),
        (5, 10),
        "ne",
    )

    # 'Run' button definition
    self.run_button = add_button(
        self,
        self,
        "#246FB6",
        ("#0BF075", "#1AD63D"),
        "",
        self.run_program,
        2,
        "Run and Exit",
        1,
        9,
        2,
        (0, 20),
        (10, 5),
        "se",
    )

    # 'ReRun' button definition
    self.rerun_button = add_button(
        self,
        self,
        "#246FB6",
        ("#0BF075", "#1AD63D"),
        "",
        self.rerun_the_program,
        2,
        "ReRun",
        1,
        10,
        2,
        (0, 20),
        (5, 10),
        "ne",
    )

    # 'Exit' button definition
    self.exit_button = add_button(
        self,
        self,
        "#246FB6",
        "Red",
        "",
        self.exit_program,
        2,
        "Exit",
        1,
        11,
        2,
        (20, 20),
        (20, 20),
        "ne",
    )

    # Create textbox for Help information
    self.textbox = ctk.CTkTextbox(self, height=600, width=250)
    self.textbox.configure(scrollbar_button_color="#6563ff", wrap="word")
    self.textbox.grid(row=0, column=1, padx=(20, 0), pady=(20, 0), sticky="ew")

    # Start third grid / column definitions
    # create tabview for Name, Color, and Debug
    self.tabview = ctk.CTkTabview(self, width=250, segmented_button_fg_color="#6563ff")
    self.tabview.grid(row=0, column=2, padx=(20, 0), pady=(20, 0), sticky="nsew")
    self.tabview.add("Specific Name")
    self.tabview.add("Colors")
    self.tabview.add("Analyze")
    self.tabview.add("Debug")

    self.tabview.tab("Specific Name").grid_columnconfigure(0, weight=1)  # configure grid of individual tabs
    self.tabview.tab("Colors").grid_columnconfigure(0, weight=1)

    # Project Name
    self.string_input_button1 = ctk.CTkRadioButton(
        self.tabview.tab("Specific Name"),
        text="Project Name",
        font=ctk.CTkFont(size=default_font_size, weight="normal"),
        command=self.single_project_name_event,
        fg_color="#6563ff",
        border_color="#1bc9ff",
    )
    self.string_input_button1.grid(row=1, column=0, padx=20, pady=(10, 10), sticky="nsew")

    # Profile Name
    self.string_input_button2 = ctk.CTkRadioButton(
        self.tabview.tab("Specific Name"),
        text="Profile Name",
        font=ctk.CTkFont(size=default_font_size, weight="normal"),
        command=self.single_profile_name_event,
        fg_color="#6563ff",
        border_color="#1bc9ff",
    )
    self.string_input_button2.grid(row=2, column=0, padx=20, pady=(10, 10), sticky="nsew")

    # Task Name
    self.string_input_button3 = ctk.CTkRadioButton(
        self.tabview.tab("Specific Name"),
        text="Task Name",
        font=ctk.CTkFont(size=default_font_size, weight="normal"),
        command=self.single_task_name_event,
        fg_color="#6563ff",
        border_color="#1bc9ff",
    )
    self.string_input_button3.grid(row=3, column=0, padx=20, pady=(10, 10), sticky="nsew")

    # Prompt for the name
    self.name_label = add_label(
        self,
        self.tabview.tab("Specific Name"),
        "(Pick ONLY One)",
        "",
        0,
        "normal",
        4,
        0,
        20,
        (10, 10),
        "w",
    )

    # Setup to get various display colors
    self.label_tab_2 = add_label(
        self,
        self.tabview.tab("Specific Name"),
        "Set Various Display Colors Here:",
        "",
        0,
        "normal",
        0,
        0,
        0,
        0,
        "",
    )
    self.colors_optionemenu = add_option_menu(
        self,
        self.tabview.tab("Colors"),
        self.colors_event,
        [
            "Projects",
            "Profiles",
            "Disabled Profiles",
            "Launcher Task",
            "Profile Conditions",
            "Tasks",
            "(Task) Actions",
            "Action Conditions",
            "Action Labels",
            "Action Names",
            "Scenes",
            "Background",
            "TaskerNet Information",
            "Tasker Preferences",
            "Highlight",
            "Heading",
        ],
        1,
        0,
        20,
        (10, 10),
        "",
    )

    # Reset to Default Colors button
    self.color_reset_button = add_button(
        self,
        self.tabview.tab("Colors"),
        "",
        "",
        "",
        self.color_reset_event,
        2,
        "Reset to Default Colors",
        1,
        3,
        0,
        20,
        (10, 10),
        "",
    )

    # AI Tab fields
    # API Key
    center = 50
    self.ai_apikey_button = add_button(
        self,
        self.tabview.tab("Analyze"),
        "",  # fg_color: str,
        "",  # text_color: str,
        "",  # border_color: str,
        self.ai_apikey_event,  # command
        2,  # border_width: int,
        "Show/Edit OpenAI API Key",  # text: str,
        1,  # columnspan: int,
        3,  # row: int,
        0,  # column: int,
        center,  # padx: tuple,
        (10, 10),  # pady: tuple,
        "",
    )
    # Model selection
    self.ai_model_label = add_label(
        self,
        self.tabview.tab("Analyze"),
        "Model to Use:",
        "",
        0,
        "normal",
        4,
        0,
        center,
        (20, 0),
        "s",
    )
    display_models = ["none (llama3)", *OPENAI_MODELS, *LLAMA_MODELS]  # Combine lists
    self.ai_model_option = add_option_menu(
        self,
        self.tabview.tab("Analyze"),
        self.ai_model_selected_event,
        display_models,
        5,
        0,
        center,
        (0, 10),
        "n",
    )

    # Analyize button
    display_analyze_button(self, 10)

    # Readme Help button
    self.ai_help_button = add_button(
        self,
        self.tabview.tab("Analyze"),
        "",  # fg_color: str,
        "",  # text_color: str,
        "",  # border_color: str,
        self.ai_help_event,  # command
        2,  # border_width: int,
        "Help",  # text: str,
        1,  # columnspan: int,
        11,  # row: int,
        0,  # column: int,
        center,  # padx: tuple,
        (10, 10),  # pady: tuple,
        "",
    )

    # Debug Mode checkbox
    self.debug_checkbox = add_checkbox(
        self,
        self.tabview.tab("Debug"),
        self.debug_checkbox_event,
        "Debug Mode",
        4,
        3,
        20,
        10,
        "w",
        "#6563ff",
    )
    # Runtime
    self.runtime_checkbox = add_checkbox(
        self,
        self.tabview.tab("Debug"),
        self.runtime_checkbox_event,
        "Display Runtime Settings",
        3,
        3,
        20,
        10,
        "w",
        "#6563ff",
    )


# ##################################################################################
# Display Ai 'Analyze" button
# ##################################################################################
def display_analyze_button(self, row: int) -> None:  # noqa: ANN001
    """
    Display the 'Analyze' button for the AI API key.

    This function creates and displays a button on the 'Analyze' tab of the tabview. The button is used to run the analysis for the AI API key.

    Parameters:
        self (object): The instance of the class.
        row (int): The row number to display the button.

    Returns:
        None: This function does not return anything.
    """
    # Highlight the button if we have everything to run the Analysis.
    if ((self.ai_model in OPENAI_MODELS and self.ai_apikey) or self.ai_model) and (
        self.single_task_name or self.single_profile_name
    ):
        fg_color = "#f55dff"
        text_color = "#5554ff"
    else:
        fg_color = ""
        text_color = ""

    self.ai_analyze_button = add_button(
        self,
        self.tabview.tab("Analyze"),
        fg_color,  # fg_color: str,
        text_color,  # text_color: str,
        "",  # border_color: str,
        self.ai_analyze_event,  # command
        2,  # border_width: int,
        "Run Analysis",  # text: str,
        1,  # columnspan: int,
        row,  # row: int,
        0,  # column: int,
        50,  # padx: tuple,
        (10, 10),  # pady: tuple,
        "",
    )


# ##################################################################################
# Display the current settings for Ai
# ##################################################################################
def display_ai_settings(self) -> None:  # noqa: ANN001
    """
    Display the current settings for Ai
    """
    # Read the api key.
    self.ai_apikey = get_api_key()
    key_to_display = "Set" if self.ai_apikey else "Unset"
    model_to_display = self.ai_model if self.ai_model else "none (llama3)"
    self.ai_set_label1 = add_label(
        self,
        self.tabview.tab("Analyze"),
        f"API Key: {key_to_display}, Model: {model_to_display}",
        "",
        0,
        "normal",
        12,
        0,
        10,
        (20, 0),
        "w",
    )

    # Note: Nothing beyond this point will appear in the grid.  Row 12 is the max.
    # self.ai_set_label2 = add_label(
    #    self,
    #    self.tabview.tab("Analyze"),
    #    f"Model: {model_to_display}",
    #    "",
    #    0,
    #    "normal",
    #    13,
    #    0,
    #    10,
    #    (20, 0),
    #    "w",
    # )
    profile_to_display = self.single_profile_name if self.single_profile_name else "Undefined"
    task_to_display = self.single_task_name if self.single_task_name else "Undefined"
    self.ai_model_option.set(model_to_display)  # Set the current model in the pulldown.

    # The label should have been destroyed, but isn't due to tk bug.  So we have to blank fill if necessary.
    profile_length = len(profile_to_display)
    fill = 16
    if profile_length < fill:
        profile_to_display = profile_to_display.ljust(fill - profile_length, " ")

    # Display the Profile to analyze
    self.ai_set_label3 = add_label(
        self,
        self.tabview.tab("Analyze"),
        f"Profile to Analyze: {profile_to_display}",
        "",
        0,
        "normal",
        14,
        0,
        10,
        (20, 0),
        "w",
    )
    # Display the Task to analyze
    self.ai_set_label3 = add_label(
        self,
        self.tabview.tab("Analyze"),
        f"Task to Analyze: {task_to_display}",
        "",
        0,
        "normal",
        15,
        0,
        10,
        (20, 0),
        "w",
    )


# ##################################################################################
# Get the Ai api key
# ##################################################################################
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


# ##################################################################################
# Either validate the file location provided or provide a filelist of XML files
# ##################################################################################
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
            "Select XML File From Android Device:",
            "",
            0,
            "normal",
            8,
            1,
            (185, 0),
            (0, 10),
            "sw",
        )
        self.filelist_option = add_option_menu(
            self,
            self,
            self.file_selected_event,
            filelist,
            9,
            1,
            (185, 10),
            (0, 10),
            "nw",
        )

        # Set backup IP and file location attributes if valid
        self.android_ipaddr = android_ipaddr
        self.android_port = android_port
        return 2, "", "", ""  # Just return with error so the prompt comes up to select file.

    # All is okay
    return 0, android_ipaddr, android_port, android_file


# ##################################################################################
# Provide a pulldown list for the selection of a Profile name
# ##################################################################################
def list_profiles_and_tasks(self) -> bool:  # noqa: ANN001
    """
    Lists the profiles and tasks available in the XML file.  The list for each will appear in a pulldown option list.

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

    profiles = []
    tasks = []

    # Ok, we have our root Tasker elements.  Build the tree.
    tree_data = self.build_the_tree()
    # If no tree, then there are no Projects in the XML.
    if not tree_data:
        if PrimeItems.tasker_root_elements["all_profiles"]:
            profiles = [value["name"] for value in PrimeItems.tasker_root_elements["all_profiles"].values()]
        if PrimeItems.tasker_root_elements["all_tasks"]:
            tasks = [value["name"] for value in PrimeItems.tasker_root_elements["all_tasks"].values()]

        # self.display_message_box("No Projects found in XML file.  Load another XML file with at least one Project and try again.", "Red")
        # return False

    # We have a treeBuild our list of Profiles and Tasks in the Projects.
    else:
        # Go through the Projects and get all of the Profile names.
        for project in tree_data:
            for profile in project["children"]:
                with contextlib.suppress(TypeError):
                    profiles.append(profile["name"])
                    tasks.extend(profile["children"])

    # Cleanup the lists
    have_profiles = have_tasks = True  # Assume we have Profiles and Tasks
    profiles_to_display = [profile for profile in profiles if profile != "Profile: Unnamed/Anonymous"]
    if not profiles_to_display:
        profiles_to_display = ["No profiles found"]
        have_profiles = False
    tasks_to_display = [task for task in tasks if task != "Task: Unnamed/Anonymous."]
    if not tasks_to_display:
        tasks_to_display = ["No tasks found"]
        have_tasks = False
    if not have_profiles and not have_tasks:
        self.display_message_box("No profiles or tasks found in XML file.  Using the 'Get Local Xml button, load another XML file and try again.", "Red")
        return False

    # Make alphabetical
    profiles_to_display = sorted(profiles_to_display)
    profiles_to_display.insert(0, "None")

    # Remove dups from Tasks and sort them
    tasks_to_display = list(set(tasks_to_display))
    tasks_to_display = sorted(tasks_to_display)
    tasks_to_display.insert(0, "None")

    # Display all of the Profiles for selection.
    self.ai_profile_label = add_label(
        self,
        self.tabview.tab("Analyze"),
        "Select Profile to Analyze:",
        "",
        0,
        "normal",
        6,
        0,
        20,
        (20, 0),
        "s",
    )
    # Get the project desired
    self.profile_optionemenu = add_option_menu(
        self,
        self.tabview.tab("Analyze"),
        self.ai_profile_selected_event,
        profiles_to_display,
        7,
        0,
        20,
        (0, 10),
        "n",
    )

    # Display all of the Tasks for selection.
    self.ai_task_label = add_label(
        self,
        self.tabview.tab("Analyze"),
        "Select Task to Analyze:",
        "",
        0,
        "normal",
        8,
        0,
        20,
        (20, 0),
        "s",
    )
    # Get the project desired
    self.task_optionemenu = add_option_menu(
        self,
        self.tabview.tab("Analyze"),
        self.ai_task_selected_event,
        tasks_to_display,
        9,
        0,
        20,
        (0, 10),
        "n",
    )

    return True


# ##################################################################################
# Build a list of Profiles that are under the given project
# ##################################################################################
def build_profiles(root: dict, profile_ids: list) -> list:
    """Parameters:
        - root (dict): Dictionary containing all profiles and their tasks.
        - profile_ids (list): List of profile IDs to be processed.
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
        else:
            task_list = ["No Profile Tasks Found"]

        # Get the Profile name.
        if profiles[profile]["name"] == "":
            profile_name = "Profile: Unnamed/Anonymous"
        else:
            profile_name = f'Profile: {profiles[profile]["name"]}'

        # Combine the Profile with it's Tasks
        profile_list.append({"name": profile_name, "children": task_list})

    return profile_list


# ##################################################################################
# Display startup messages which are a carryover from the last run.
# ##################################################################################
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

            # Handle Ai Response in new toplevel window
            if "Ai Response" in error_msg:
                self.display_ai_response(error_msg)
                self.display_message_box(
                    f"Analysis response is in a spearate Window and saved as {ANALYSIS_FILE}.",
                    "Turquoise",
                )
            # Some other message.  Just display it in the message box and break it up if needed.
            elif "\n" in error_msg:
                messages = error_msg.split("\n")
                for message_line in messages:
                    self.display_message_box(message_line, "Red")
            else:
                self.display_message_box(error_msg, "Red")
            os.remove(ERROR_FILE)  # Get rid of error message so we don't display it again.

    # Display any error message from other rountines
    if PrimeItems.error_msg:
        self.display_message_box(f"{PrimeItems.error_msg} with return code {PrimeItems.error_code}.", "Red")


# ##################################################################################
# Display the current file as a label
# ##################################################################################
def display_current_file(self, file_name: str) -> None:  # noqa: ANN001
    """
    Display the current file name in a button on the GUI.

    Args:
        file_name (str): The name of the current file.

    Returns:
        None: This function does not return anything.

    This function creates a button on the GUI that displays the current file name. The button is created using the `add_button` function and is placed in the second row and tenth column of the GUI. The button's text is set to "Current File: {file_name}". The `self.report_issue_event` function is assigned as the button's click event handler.

    Note:
        - The `add_button` function is assumed to be defined elsewhere in the codebase.
        - The `self.report_issue_event` function is assumed to be defined elsewhere in the codebase.

    Example:
        ```python
        gui_instance.display_current_file("example.txt")
        ```
    """
    # Check for slashes and remove if nessesary
    filename_location = file_name.rfind(PrimeItems.slash) + 1
    if filename_location != -1:
        file_name = file_name[filename_location:]
    self.report_issue_button = add_label(
        self,
        self,
        f"Current File: {file_name}",
        "",
        "",
        "normal",
        11,
        1,
        20,
        0,
        "w",
    )


# ##################################################################################
# Display a tree structure
# ##################################################################################
class CTkTreeview(ctk.CTkFrame):
    """Class to handle the Treeview

    Args:
        ctk (ctk): Our GUI framework
    """

    def __init__(self, master: any, items: list) -> None:
        """Function:
        def __init__(self, master: any, items: list):
            Initializes a Treeview widget with a given master and list of items.
            Parameters:
                master (any): The parent widget for the Treeview.
                items (list): A list of items to be inserted into the Treeview.
            Returns:
                None.
            Processing Logic:
                - Sets up the Treeview widget with appropriate styles and bindings.
                - Inserts the given items into the Treeview.

        tkinter treeview configurable items:
            ttk::style configure Treeview -background color
            ttk::style configure Treeview -foreground color
            ttk::style configure Treeview -font namedfont
            ttk::style configure Treeview -fieldbackground color
            ttk::style map Treeview -background \
                [list selected color]
            ttk::style map Treeview -foreground \
                [list selected color]
            ttk::style configure Treeview -rowheight [expr {[font metrics namedfont -linespace] + 2}]
            ttk::style configure Heading -font namedfont
            ttk::style configure Heading -background color
            ttk::style configure Heading -foreground color
            ttk::style configure Heading -padding padding
            ttk::style configure Item -foreground color
            ttk::style configure Item -focuscolor color
        """
        self.root = master
        self.items = items
        super().__init__(self.root)

        self.grid_columnconfigure(0, weight=1)

        # Label widget
        our_label = """
Drag the bottom of the window to expand as needed.\n
Click item and scroll mouse-wheel/trackpad\nas needed to go up or down.
        """
        self.label = ctk.CTkLabel(master=self, text=our_label, font=("", 12))
        self.label.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        # Basic appearance for text, foreground and background.
        self.bg_color = self.root._apply_appearance_mode(ctk.ThemeManager.theme["CTkFrame"]["fg_color"])  # noqa: SLF001
        self.text_color = self.root._apply_appearance_mode(  # noqa: SLF001
            ctk.ThemeManager.theme["CTkLabel"]["text_color"],
        )
        self.selected_color = self.root._apply_appearance_mode(  # noqa: SLF001
            ctk.ThemeManager.theme["CTkButton"]["fg_color"],
        )

        # Set up the style/theme
        self.tree_style = ttk.Style(self)
        self.tree_style.theme_use("default")

        # Gteth the icons to be used in the Tree view.
        self.im_open = Image.open(ICON_PATH["arrow"])
        self.im_close = self.im_open.rotate(90)
        self.im_empty = Image.new("RGBA", (15, 15), "#00000000")

        self.img_open = ImageTk.PhotoImage(self.im_open, name="img_open", size=(15, 15))
        self.img_close = ImageTk.PhotoImage(self.im_close, name="img_close", size=(15, 15))
        self.img_empty = ImageTk.PhotoImage(self.im_empty, name="img_empty", size=(15, 15))

        # Arrow element configuration
        with contextlib.suppress(TclError):  # Don't throw error if the element already exists.  Just reuse it.
            self.tree_style.element_create(
                "Treeitem.myindicator",
                "image",
                "img_close",
                ("user1", "!user2", "img_open"),
                ("user2", "img_empty"),
                sticky="w",
                width=15,
                height=15,
            )

        # Treeview configuration of the treeview
        self.tree_style.layout(
            "Treeview.Item",
            [
                (
                    "Treeitem.padding",
                    {
                        "sticky": "nsew",
                        "children": [
                            ("Treeitem.myindicator", {"side": "left", "sticky": "nsew"}),
                            ("Treeitem.image", {"side": "left", "sticky": "nsew"}),
                            (
                                "Treeitem.focus",
                                {
                                    "side": "left",
                                    "sticky": "nsew",
                                    "children": [("Treeitem.text", {"side": "left", "sticky": "nsew"})],
                                },
                            ),
                        ],
                    },
                ),
            ],
        )

        self.tree_style.configure(
            "Treeview",
            background=self.bg_color,
            foreground=self.text_color,
            fieldbackground=self.bg_color,
            borderwidth=10,  # Define a border around tree of 10 pixels.
            font=("", 12),
        )

        self.tree_style.map(
            "Treeview",
            background=[("selected", self.bg_color)],
            foreground=[("selected", self.selected_color)],
        )
        self.root.bind("<<TreeviewSelect>>", lambda event: self.root.focus_set())  # noqa: ARG005

        # Define the frame for the treeview
        self.treeview = ttk.Treeview(self, show="tree", height=50, selectmode="browse")

        # Define the width of the column into which the tree will be placed.
        self.treeview["columns"] = [0]
        # self.treeview.column(0, stretch=0, anchor="w", width=150, minwidth=150)
        # To configure the tree column, call this with column = “#0”
        self.treeview.column("#0", stretch=0, anchor="w", width=300, minwidth=200)

        self.treeview.grid(row=1, column=0, padx=10, pady=10, sticky="w")

        # Add items to the tree
        self.insert_items(self.items)

    # ##################################################################################
    # Inset items into the treeview.
    # ##################################################################################
    def insert_items(self, items: list, parent="") -> None:  # noqa: ANN001
        """Inserts items into a treeview.
        Parameters:
            items (list): List of items to be inserted.
            parent (str): Optional parent item for the inserted items.
        Returns:
            None: Does not return anything.
        Processing Logic:
            - Inserts items into treeview.
            - If item is a dictionary, insert with id.
            - If item is not a dictionary, insert without id."""
        for item in items:
            if isinstance(item, dict):
                the_id = self.treeview.insert(parent, "end", text=item["name"].ljust(50))
                with contextlib.suppress(KeyError):
                    self.insert_items(item["children"], the_id)
            else:
                self.treeview.insert(parent, "end", text=item)


# ##################################################################################
# Define the Treeview window
# ##################################################################################
class TreeviewWindow(ctk.CTkToplevel):
    """Define our top level window for the tree view."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        """Creates a label widget for a tree view.
        Parameters:
            self (object): The object being passed.
            *args (any): Additional arguments.
            **kwargs (any): Additional keyword arguments.
        Returns:
            None: This function does not return anything.
        Processing Logic:
            - Initialize label widget.
            - Pack label widget with padding.
            - Set label widget text."""
        super().__init__(*args, **kwargs)
        self.geometry("600x600")
        self.title("MapTasker Configuration Treeview")


# ##################################################################################
# Display a Analysis structure
# ##################################################################################
class CTkAnalysisview(ctk.CTkFrame):
    """Class to handle the Treeview

    Args:
        ctk (ctk): Our GUI framework
    """

    def __init__(self, master: any, message: str) -> None:
        """Function:
        def __init__(self, master: any, items: list):
            Initializes a Analysisview widget with a given master and list of items.
            Parameters:
                master (any): The parent widget for the Analysisview.
                items (list): A list of items to be inserted into the Analysisview.
            Returns:
                None.
            Processing Logic:
                - Sets up the Analysisview widget with appropriate styles and bindings.
                - Inserts the given items into the Treeview.
        """
        self.root = master
        super().__init__(self.root)

        self.grid_columnconfigure(0, weight=1)

        # Add a label to the top of window
        # our_label = "Drag the bottom of the window to expand as needed."
        # self.analysis_label = ctk.CTkLabel(master=self, text=our_label, font=("", 12))
        # self.analysis_label.grid(row=0, column=1, padx=10, pady=10, sticky="n")

        # Basic appearance for text, foreground and background.
        self.analysis_bg_color = self.root._apply_appearance_mode(ctk.ThemeManager.theme["CTkFrame"]["fg_color"])  # noqa: SLF001
        self.analysis_text_color = self.root._apply_appearance_mode(  # noqa: SLF001
            ctk.ThemeManager.theme["CTkLabel"]["text_color"],
        )
        self.selected_color = self.root._apply_appearance_mode(  # noqa: SLF001
            ctk.ThemeManager.theme["CTkButton"]["fg_color"],
        )

        # Set up the style/theme
        self.analysis_style = ttk.Style(self)
        self.analysis_style.theme_use("default")

        # Recreate text box
        self.analysis_textbox = ctk.CTkTextbox(self, height=700, width=550)
        self.analysis_textbox.grid(row=1, column=1, padx=20, pady=40, sticky="nsew")

        # Insert the text with our new message into the text box.
        # Add the test and color to the text box.
        # fmt: off
        self.analysis_textbox.insert("0.0", f"{message}\n")
        self.analysis_textbox.configure(state="disabled")  # configure textbox to be read-only
        self.analysis_textbox.configure(wrap="word")
        self.analysis_textbox.focus_set()


# ##################################################################################
# Define the Ai Analysis window
# ##################################################################################
class AnalysisWindow(ctk.CTkToplevel):
    """Define our top level window for the analysis view."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        """Creates a label widget for a tree view.
        Parameters:
            self (object): The object being passed.
            *args (any): Additional arguments.
            **kwargs (any): Additional keyword arguments.
        Returns:
            None: This function does not return anything.
        Processing Logic:
            - Initialize label widget.
            - Pack label widget with padding.
            - Set label widget text."""
        super().__init__(*args, **kwargs)
        self.geometry("600x800")
        self.title("MapTasker Analysis Response")


# ##################################################################################
# Define the Ai Popup window
# ##################################################################################
# class PopupWindow(ctk.CTk):
#    """Define our top level window for the Popup view."""

#    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
#        """Creates a label widget for a tree view.
#        Parameters:
#            self (object): The object being passed.
#            *args (any): Additional arguments.
#            **kwargs (any): Additional keyword arguments.
#        Returns:
#            None: This function does not return anything.
#        Processing Logic:
#            - Initialize label widget.
#            - Pack label widget with padding.
#            - Set label widget text."""
#        super().__init__(*args, **kwargs)
#        self.geometry("600x800")
#        self.title("MapTasker Analysis Popup Response")

#        self.grid_columnconfigure(0, weight=1)

#        # Label widget
#        our_label = "Analysis is running.  Please stand by..."
#        self.Popup_label = ctk.CTkLabel(master=self, text=our_label, font=("", 12))
#        self.Popup_label.grid(row=0, column=1, padx=10, pady=10, sticky="n")

#        # Basic appearance for text, foreground and background.
#        self.Popup_bg_color = self._apply_appearance_mode(ctk.ThemeManager.theme["CTkFrame"]["fg_color"])
#        self.Popup_text_color = self._apply_appearance_mode(
#            ctk.ThemeManager.theme["CTkLabel"]["text_color"],
#        )
#        self.selected_color = self._apply_appearance_mode(
#            ctk.ThemeManager.theme["CTkButton"]["fg_color"],
#        )

#        # Set up the style/theme
#        self.Popup_style = ttk.Style(self)
#        self.Popup_style.theme_use("default")

#        # Recreate text box
#        self.popup_button = ctk.CTkButton(master=self,
#                                width=120,
#                                height=32,
#                                border_width=0,
#                                corner_radius=8,
#                                text="Click to close this window",
#                                command=self.popup_button_event)
#        self.popup_button.place(relx=0.5, rely=0.5)
#        self.popup_button.focus_set()


#    def popup_button_event(self) -> None:
#        """
#        Define the behavior of the popup button event function.  Close the window and exit.
#        """
#        PrimeItems.loop_active = False
#        self.exit = True
#        self.quit()
#        self.quit()
