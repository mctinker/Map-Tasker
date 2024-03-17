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
from tkinter import font
from typing import TYPE_CHECKING

import customtkinter
from PIL import Image

from maptasker.src.colrmode import set_color_mode
from maptasker.src.lineout import LineOut
from maptasker.src.maputils import get_pypi_version, http_request, validate_ip_address, validate_port, validate_xml_file
from maptasker.src.nameattr import get_tk
from maptasker.src.primitem import PrimeItems
from maptasker.src.proginit import get_data_and_output_intro
from maptasker.src.sysconst import CHANGELOG_FILE, NOW_TIME, VERSION

if TYPE_CHECKING:
    from datetime import datetime

# TODO Change this 'changelog' with each release!  New lines (\n) must be added.
CHANGELOG = """
Version 3.1.5 Change Log\n\n
- Added: The GUI message window now displays the message history.\n\n
- Changed: The 'Get XML Help' button in the GUI is now called 'Get Android Help' for clarity.\n\n
- Fixed: The wrong changelog information is being displayed with a new version update in the GUI.\n\n
- Fixed: The GUI 'Upgrade to Latest Version' button is sitting on top of the 'Report Issue' button.\n\n
- Fixed: The GUI 'Just Display Everything' button is missing.\n\n
- Fixed: The alignment of the Android XML fields in the GUI is off.\n\n
"""
default_font_size = 14


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
        "Get XML from Android Device", "#246FB6", "#6563ff", self.get_backup_event
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
    self.edit = False
    self.edit_type = ""
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
    self.toplevel_window = None
    PrimeItems.program_arguments["gui"] = True
    self.list_files = False

    self.title("MapTasker Runtime Options")
    # Overall window dimensions
    self.geometry("1100x900")
    # self.width = 1100
    # self.height = 800

    # configure grid layout (4x4)
    self.grid_columnconfigure(1, weight=1)
    self.grid_columnconfigure((2, 3), weight=0)
    self.grid_rowconfigure(0, weight=1)

    # load and create background image

    # create sidebar frame with widgets on the left side of the window.
    self.sidebar_frame = customtkinter.CTkFrame(self, width=140, corner_radius=0)
    self.sidebar_frame.configure(bg_color="black")
    self.sidebar_frame.grid(row=0, column=0, rowspan=12, sticky="nsew")
    # Define sidebar background frame with 14 rows
    self.sidebar_frame.grid_rowconfigure(13, weight=1)


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
    my_image = customtkinter.CTkImage(
        light_image=Image.open("maptasker_logo_light.png"),
        dark_image=Image.open("maptasker_logo_dark.png"),
        size=(190, 50),
    )
    try:
        self.logo_label = customtkinter.CTkLabel(
            self.sidebar_frame,
            image=my_image,
            text="",
            compound="left",
            font=customtkinter.CTkFont(size=1, weight="bold"),
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
    frame: customtkinter.CTkFrame,
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
        - frame (customtkinter.CTkFrame): The frame to add the label to.
        - name (customtkinter.CTkLabel): The label to be added.
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
    label_name = customtkinter.CTkLabel(
        frame,
        text=text,
        text_color=text_color,
        font=customtkinter.CTkFont(size=font_size, weight=font_weight),
    )
    label_name.grid(row=row, column=column, padx=padx, pady=pady, sticky=sticky)
    return label_name


# ##################################################################################
# Create a checkbox general routine
# ##################################################################################
def add_checkbox(
    self,  # noqa: ANN001, ARG001
    frame: customtkinter.CTkFrame,
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
        - frame (customtkinter.CTkFrame): The custom tkinter frame to add the checkbox to.
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
    checkbox_name = customtkinter.CTkCheckBox(
        frame,
        command=command,
        text=text,
        font=customtkinter.CTkFont(size=default_font_size, weight="normal"),
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
    frame: customtkinter.CTkFrame,
    fg_color: str,
    text_color: str,
    border_color: str,
    command: object,
    border_width: int,
    text: str,
    row: int,
    column: int,
    padx: tuple,
    pady: tuple,
    sticky: str,
) -> None:
    """Add a button to a custom tkinter frame.
    Parameters:
        - frame (customtkinter.CTkFrame): The frame to add the button to.
        - fg_color (str): The color of the button's text.
        - text_color (str) The color of the button's text.
        - command (object): The function to be executed when the button is clicked.
        - border_width (int): The width of the button's border.
        - text (str): The text to be displayed on the button.
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
    button_name = customtkinter.CTkButton(
        frame,
        fg_color=fg_color,
        text_color=text_color,
        font=customtkinter.CTkFont(size=default_font_size, weight="normal"),
        border_color=border_color,
        command=command,
        border_width=border_width,
        text=text,
    )
    button_name.grid(row=row, column=column, padx=padx, pady=pady, sticky=sticky)
    return button_name


# ##################################################################################
# Create a button general routine
# ##################################################################################
def add_option_menu(
    self,  # noqa: ANN001, ARG001
    frame: customtkinter.CTkFrame,
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
        - frame (customtkinter.CTkFrame): The frame to add the option menu to.
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
    option_menu_name = customtkinter.CTkOptionMenu(
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
        - If the program is in edit mode, creates a fifth grid / column for selecting new or existing projects.
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
        "w",
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

    # Names: Bold / Highlight / Italicise
    self.display_names_label = add_label(
        self,
        self.sidebar_frame,
        "Project/Profile/Task/Scene Names:",
        "",
        0,
        "normal",
        10,
        0,
        20,
        10,
        "s",
    )

    # Bold
    self.bold_checkbox = add_checkbox(self, self.sidebar_frame, self.names_bold_event, "Bold", 11, 0, 20, 0, "ne", "")

    # Italicize
    self.italicize_checkbox = add_checkbox(
        self,
        self.sidebar_frame,
        self.names_italicize_event,
        "italicize",
        11,
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
        12,
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
        12,
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
        13,
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
        14,
        0,
        0,
        (0, 40),
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
        15,
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
        16,
        0,
        0,
        (0, 50),
        "n",
    )

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
        17,
        0,
        20,
        20,
        "",
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
        9,
        1,
        20,
        0,
        "sw",
    )

    # 'Get Backup Settings' button definition
    self.get_backup_button = self.display_backup_button(
        "Get XML from Android Device", "#246FB6", "#6563ff", self.get_backup_event
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
        6,
        2,
        (20, 20),
        (20, 20),
        "ne",
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
        7,
        2,
        (20, 20),
        (0, 20),
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
        "Run",
        8,
        2,
        (20, 20),
        (20, 0),
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
        9,
        2,
        (20, 20),
        (20, 50),
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
        10,
        2,
        (20, 20),
        (20, 20),
        "ne",
    )

    # Create textbox for Help information
    self.textbox = customtkinter.CTkTextbox(self, height=600, width=250)
    self.textbox.configure(scrollbar_button_color="#6563ff", wrap="word")
    self.textbox.grid(row=0, column=1, padx=(20, 0), pady=(20, 0), sticky="ew")

    # Start third grid / column definitions
    # create tabview for Name, Color, and Debug
    self.tabview = customtkinter.CTkTabview(self, width=250, segmented_button_fg_color="#6563ff")
    self.tabview.grid(row=0, column=2, padx=(20, 0), pady=(20, 0), sticky="nsew")
    self.tabview.add("Specific Name")
    self.tabview.add("Colors")
    self.tabview.add("Debug")
    #if EDIT:
    #    self.tabview.add("Edit")

    self.tabview.tab("Specific Name").grid_columnconfigure(0, weight=1)  # configure grid of individual tabs
    self.tabview.tab("Colors").grid_columnconfigure(0, weight=1)

    # Project Name
    self.string_input_button1 = customtkinter.CTkRadioButton(
        self.tabview.tab("Specific Name"),
        text="Project Name",
        font=customtkinter.CTkFont(size=default_font_size, weight="normal"),
        command=self.single_project_name_event,
        fg_color="#6563ff",
        border_color="#1bc9ff",
    )
    self.string_input_button1.grid(row=1, column=0, padx=20, pady=(10, 10), sticky="nsew")

    # Profile Name
    self.string_input_button2 = customtkinter.CTkRadioButton(
        self.tabview.tab("Specific Name"),
        text="Profile Name",
        font=customtkinter.CTkFont(size=default_font_size, weight="normal"),
        command=self.single_profile_name_event,
        fg_color="#6563ff",
        border_color="#1bc9ff",
    )
    self.string_input_button2.grid(row=2, column=0, padx=20, pady=(10, 10), sticky="nsew")

    # Task Name
    self.string_input_button3 = customtkinter.CTkRadioButton(
        self.tabview.tab("Specific Name"),
        text="Task Name",
        font=customtkinter.CTkFont(size=default_font_size, weight="normal"),
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
        3,
        0,
        20,
        (10, 10),
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

    ## Edit Section Prompts
    #if EDIT:
    #    # TODO Clean up the geometry
    #    self.edit_label = add_label(
    #        self,
    #        self.tabview.tab("Edit"),
    #        "New or existing?",
    #        0,
    #        "",
    #        "normal",
    #        10,
    #        2,
    #        (20, 20),
    #        (20, 20),
    #        "e",
    #    )
    #    self.edit_optionemenu = add_option_menu(
    #        self,
    #        self.tabview.tab("Edit"),
    #        self.edit_event,
    #        [
    #            "Create New",
    #            "Edit Existing",
    #        ],
    #        3,
    #        3,
    #        (20, 20),
    #        (20, 20),
    #        "e",
    #    )

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
    if len(android_file) != 0 and android_file != "" and self.list_files == False:
        return_code, file_contents = http_request(android_ipaddr, android_port, android_file, "file", "?download=1")

        # Validate XML file.
        if return_code == 0:
            return_code, error_message = validate_xml_file(android_ipaddr, android_port, android_file)
            if return_code != 0:
                self.display_message_box(error_message, False)
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
            self.display_message_box(filelist, False)
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
