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
from maptasker.src.sysconst import CHANGELOG_FILE, EDIT, NOW_TIME, VERSION

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
    changelog = """
Version 3.1.3 Change Log (includes 3.1.2 changes)
- Fixed: File error displayed after getting the list of Android files in the GUI.
- Fixed: The Task name does not appear if the XML consists solely of a single Task.
- Fixed: If the 'Get XML File' IP address is a valid address on the local network but not accepting access via the port given, specify this in the error message.

- Changed: Don't reread the Android XML file if "Run" has been selected since we've already read the file to validate the XML.
- Changed: Improved the GUI help information for using the 'List XML File' button/feature.

- Added: The GUI has a new button to 'Report Issue', which can be used for bugs and new feature requests.
- Added: The GUI 'Color" tab now has a button to reset all Tasker objects to their default colors.
"""
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
    self.geometry("1100x800")
    self.width = 1100
    self.height = 800

    # configure grid layout (4x4)
    self.grid_columnconfigure(1, weight=1)
    self.grid_columnconfigure((2, 3), weight=0)
    self.grid_rowconfigure(0, weight=1)

    # load and create background image

    # create sidebar frame with widgets on the left side of the window.
    self.sidebar_frame = customtkinter.CTkFrame(self, width=140, corner_radius=0)
    # self.sidebar_frame.configure(height=self._apply_window_scaling(800))
    self.sidebar_frame.configure(bg_color="black")
    self.sidebar_frame.grid(row=0, column=0, rowspan=13, sticky="nsew")
    # Define sidebar background frame with 14 rows
    self.sidebar_frame.grid_rowconfigure(14, weight=1)


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

    # # Add the background image.
    # bg_image = customtkinter.CTkImage(
    #     Image.open("bg_gradient.jpg"),
    #     size=(self.width, self.height),
    # )
    # self.bg_image_label = customtkinter.CTkLabel(self, image=bg_image)
    # self.bg_image_label.grid(row=0, column=0)

    # Switch back to proper directory
    os.chdir(current_dir)


# ##################################################################################
# Define all of the menu elements
# ##################################################################################
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
    self.logo_label = customtkinter.CTkLabel(
        self.sidebar_frame,
        text="Display Options",
        font=customtkinter.CTkFont(size=20, weight="bold"),
    )
    self.logo_label.grid(row=0, column=0, padx=20, pady=(60, 10), sticky="s")

    # Start first grid / column definitions

    # Display Detail Level
    self.detail_label = customtkinter.CTkLabel(self.sidebar_frame, text="Display Detail Level:", anchor="w")
    self.detail_label.grid(row=1, column=0, padx=20, pady=(10, 0))
    self.sidebar_detail_option = customtkinter.CTkOptionMenu(
        self.sidebar_frame,
        values=["0", "1", "2", "3", "4"],
        command=self.detail_selected_event,
    )
    self.sidebar_detail_option.grid(row=2, column=0, padx=20, pady=(10, 10))

    # Display 'Condition' checkbox
    self.condition_checkbox = customtkinter.CTkCheckBox(
        self.sidebar_frame,
        command=self.condition_event,
        text="Display Profile and Task Action Conditions",
        onvalue=True,
        offvalue=False,
    )
    self.condition_checkbox.grid(row=4, column=0, padx=20, pady=10, sticky="w")

    # Display 'TaskerNet' checkbox
    self.taskernet_checkbox = customtkinter.CTkCheckBox(
        self.sidebar_frame,
        command=self.taskernet_event,
        text="Display TaskerNet Info",
        onvalue=True,
        offvalue=False,
    )
    self.taskernet_checkbox.grid(row=5, column=0, padx=20, pady=10, sticky="w")

    # Display 'Tasker Preferences' checkbox
    self.preferences_checkbox = customtkinter.CTkCheckBox(
        self.sidebar_frame,
        command=self.preferences_event,
        text="Display Tasker Preferences",
        onvalue=True,
        offvalue=False,
    )
    self.preferences_checkbox.grid(row=6, column=0, padx=20, pady=10, sticky="w")

    # Display 'Twisty' checkbox
    self.twisty_checkbox = customtkinter.CTkCheckBox(
        self.sidebar_frame,
        command=self.twisty_event,
        text="Hide Task Details Under Twisty",
        onvalue=True,
        offvalue=False,
    )
    self.twisty_checkbox.grid(row=7, column=0, padx=20, pady=10, sticky="w")

    # Display 'directory' checkbox
    self.directory_checkbox = customtkinter.CTkCheckBox(
        self.sidebar_frame,
        command=self.directory_event,
        text="Display Directory",
        onvalue=True,
        offvalue=False,
    )
    self.directory_checkbox.grid(row=8, column=0, padx=20, pady=10, sticky="w")

    # Outline
    self.outline_checkbox = customtkinter.CTkCheckBox(
        self.sidebar_frame,
        command=self.outline_event,
        text="Display Configuration Outline",
        onvalue=True,
        offvalue=False,
    )
    self.outline_checkbox.grid(row=9, column=0, padx=20, pady=10, sticky="w")

    # Names: Bold / Highlight / Italicise
    self.display_names_label = customtkinter.CTkLabel(
        self.sidebar_frame,
        text="Project/Profile/Task/Scene Names:",
        anchor="s",
    )
    self.display_names_label.grid(row=10, column=0, padx=20, pady=10)
    # Bold
    self.bold_checkbox = customtkinter.CTkCheckBox(
        self.sidebar_frame,
        command=self.names_bold_event,
        text="Bold",
        onvalue=True,
        offvalue=False,
    )
    self.bold_checkbox.grid(row=11, column=0, padx=20, pady=0, sticky="ne")
    # Italicize
    self.italicize_checkbox = customtkinter.CTkCheckBox(
        self.sidebar_frame,
        command=self.names_italicize_event,
        text="Italicize",
        onvalue=True,
        offvalue=False,
    )
    self.italicize_checkbox.grid(row=11, column=0, padx=20, pady=0, sticky="nw")
    # Highlight
    self.highlight_checkbox = customtkinter.CTkCheckBox(
        self.sidebar_frame,
        command=self.names_highlight_event,
        text="Highlight",
        onvalue=True,
        offvalue=False,
    )
    self.highlight_checkbox.grid(row=12, column=0, padx=20, pady=5, sticky="ne")
    # Underline
    self.underline_checkbox = customtkinter.CTkCheckBox(
        self.sidebar_frame,
        command=self.names_underline_event,
        text="Underline",
        onvalue=True,
        offvalue=False,
    )
    self.underline_checkbox.grid(row=12, column=0, padx=20, pady=5, sticky="nw")

    # Indentation
    self.indent_label = customtkinter.CTkLabel(
        self.sidebar_frame,
        text="If/Then/Else Indentation Amount:",
        anchor="s",
    )
    self.indent_label.grid(row=13, column=0, padx=20, pady=(10, 0))
    # Indentation Amount
    self.indent_option = customtkinter.CTkOptionMenu(
        self.sidebar_frame,
        values=[
            "0",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "10",
        ],
        command=self.indent_selected_event,
    )
    self.indent_option.grid(row=14, column=0, padx=20, pady=(10, 10))

    # Screen Appearance: Light / Dark / System
    self.appearance_mode_label = customtkinter.CTkLabel(self.sidebar_frame, text="Appearance Mode:", anchor="sw")
    self.appearance_mode_label.grid(row=15, column=0, padx=20, pady=10)
    self.appearance_mode_optionemenu = customtkinter.CTkOptionMenu(
        self.sidebar_frame,
        values=["Light", "Dark", "System"],
        command=self.change_appearance_mode_event,
    )
    self.appearance_mode_optionemenu.grid(row=16, column=0, padx=0, sticky="n")

    # 'Reset Settings' button definition
    self.reset_button = customtkinter.CTkButton(
        # master=self,
        self.sidebar_frame,
        fg_color="#246FB6",
        border_width=2,
        text="Reset Options",
        command=self.reset_settings_event,
    )
    self.reset_button.grid(row=17, column=0, padx=20, pady=20, sticky="")

    # Start second grid / column definitions

    # Font to use
    self.font_label = customtkinter.CTkLabel(master=self, text="Font To Use In Output:", anchor="sw")
    self.font_label.grid(row=6, column=1, padx=20, pady=10, sticky="sw")
    # Get fonts from TkInter
    font_items, res = get_monospace_fonts()
    # Delete the tkroot obtained by get_monospace_fonts
    if PrimeItems.tkroot is not None:
        del PrimeItems.tkroot
        PrimeItems.tkroot = None
    self.font_optionemenu = customtkinter.CTkOptionMenu(
        master=self,
        values=font_items,
        command=self.font_event,
    )
    self.font_optionemenu.set(res[0])
    self.font_optionemenu.grid(row=7, column=1, padx=20, sticky="nw")

    # Save settings button
    self.save_settings_button = customtkinter.CTkButton(
        master=self,
        border_color="#6563ff",
        border_width=2,
        text="Save Settings",
        command=self.save_settings_event,
    )
    self.save_settings_button.grid(row=8, column=1, padx=20, sticky="sw")

    # Restore settings button
    self.restore_settings_button = customtkinter.CTkButton(
        master=self,
        border_color="#6563ff",
        border_width=2,
        text="Restore Settings",
        command=self.restore_settings_event,
    )
    self.restore_settings_button.grid(row=9, column=1, padx=20, pady=10, sticky="nw")

    # Report Issue
    self.report_issue_button = customtkinter.CTkButton(
        master=self,
        border_color="#6563ff",
        border_width=2,
        text="Report Issue",
        command=self.report_issue_event,
    )
    self.report_issue_button.grid(row=10, column=1, padx=20, pady=10, sticky="nw")
    # 'Get Backup Settings' button definition
    self.display_backup_button("Get XML from Android Device", "#246FB6", "#6563ff", self.get_backup_event)

    # 'Display Help' button definition
    self.help_button = customtkinter.CTkButton(
        master=self,
        fg_color="#246FB6",
        border_width=2,
        text="Display Help",
        command=self.help_event,
        text_color=("#0BF075", "#ffd941"),
    )
    self.help_button.grid(row=6, column=2, padx=(20, 20), pady=(20, 20), sticky="ne")

    # 'Backup Help' button definition
    self.backup_help_button = customtkinter.CTkButton(
        master=self,
        fg_color="#246FB6",
        border_width=2,
        text="Get XML Help",
        command=self.backup_help_event,
        text_color=("#0BF075", "#ffd941"),
    )
    self.backup_help_button.grid(row=7, column=2, padx=(20, 20), pady=(20, 20), sticky="ne")

    # 'Run' button definition
    self.run_button = customtkinter.CTkButton(
        master=self,
        fg_color="#246FB6",
        border_width=2,
        text="Run",
        command=self.run_program,
        text_color=("#0BF075", "#1AD63D"),
    )
    self.run_button.grid(row=8, column=2, padx=(20, 20), pady=(20, 20), sticky="e")

    # 'ReRun' button definition
    self.rerun_button = customtkinter.CTkButton(
        master=self,
        fg_color="#246FB6",
        border_width=2,
        text="ReRun",
        command=self.rerun_the_program,
        text_color=("#0BF075", "#1AD63D"),
    )
    self.rerun_button.grid(row=9, column=2, padx=(20, 20), pady=(20, 20), sticky="e")

    # 'Exit' button definition
    self.exit_button = customtkinter.CTkButton(
        master=self,
        fg_color="#246FB6",
        border_width=2,
        text="Exit",
        command=self.exit_program,
        text_color="Red",
    )
    self.exit_button.grid(row=10, column=2, padx=(20, 20), pady=(20, 20), sticky="e")

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
    if EDIT:
        self.tabview.add("Edit")

    self.tabview.tab("Specific Name").grid_columnconfigure(0, weight=1)  # configure grid of individual tabs
    self.tabview.tab("Colors").grid_columnconfigure(0, weight=1)

    # Project Name
    self.string_input_button1 = customtkinter.CTkRadioButton(
        self.tabview.tab("Specific Name"),
        text="Project Name",
        command=self.single_project_name_event,
        fg_color="#6563ff",
        border_color="#1bc9ff",
    )
    self.string_input_button1.grid(row=1, column=0, padx=20, pady=(10, 10), sticky="nsew")

    # Profile Name
    self.string_input_button2 = customtkinter.CTkRadioButton(
        self.tabview.tab("Specific Name"),
        text="Profile Name",
        command=self.single_profile_name_event,
        fg_color="#6563ff",
        border_color="#1bc9ff",
    )
    self.string_input_button2.grid(row=2, column=0, padx=20, pady=(10, 10), sticky="nsew")

    # Task Name
    self.string_input_button3 = customtkinter.CTkRadioButton(
        self.tabview.tab("Specific Name"),
        text="Task Name",
        command=self.single_task_name_event,
        fg_color="#6563ff",
        border_color="#1bc9ff",
    )
    self.string_input_button3.grid(row=3, column=0, padx=20, pady=(10, 10), sticky="nsew")

    # Prompt for the name
    self.name_label = customtkinter.CTkLabel(self.tabview.tab("Specific Name"), text="(Pick ONLY One)", anchor="w")
    self.name_label.grid(row=4, column=0, padx=20, pady=(10, 10))

    # Setup to get various display colors
    self.label_tab_2 = customtkinter.CTkLabel(self.tabview.tab("Colors"), text="Set Various Display Colors Here")
    self.label_tab_2.grid(row=0, column=0, padx=0, pady=0)
    self.colors_optionemenu = customtkinter.CTkOptionMenu(
        self.tabview.tab("Colors"),
        values=[
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
        command=self.colors_event,
    )
    self.colors_optionemenu.grid(row=1, column=0, padx=20, pady=(10, 10))

    # Reset to Default Colors button
    self.color_reset_button = customtkinter.CTkButton(
        master=self.tabview.tab("Colors"),
        border_width=2,
        text="Reset to Default Colors",
        command=self.color_reset_event,
        # text_color=("#0BF075", "#1AD63D"),
    )
    self.color_reset_button.grid(row=3, column=0, padx=20, pady=(10, 10))

    # Debug Mode checkbox
    self.debug_checkbox = customtkinter.CTkCheckBox(
        self.tabview.tab("Debug"),
        text="Debug Mode",
        command=self.debug_checkbox_event,
        onvalue=True,
        offvalue=False,
    )
    self.debug_checkbox.configure(border_color="#6563ff")
    self.debug_checkbox.grid(row=4, column=3, padx=20, pady=10, sticky="w")

    # Edit Section Prompts
    if EDIT:
        # TODO Clean up the geometry
        self.edit_label = customtkinter.CTkLabel(self.tabview.tab("Edit"), text="New or existing?")
        self.edit_label.grid(row=10, column=2, padx=(20, 20), pady=(20, 20), sticky="e")

        self.edit_optionemenu = customtkinter.CTkOptionMenu(
            self.tabview.tab("Edit"),
            values=[
                "Create New",
                "Edit Existing",
            ],
            fg_color="#246FB6",
            command=self.edit_event,
        )
        self.edit_optionemenu.grid(row=10, column=2, padx=(20, 20), pady=(20, 20), sticky="e")

    # Runtime
    self.runtime_checkbox = customtkinter.CTkCheckBox(
        self.tabview.tab("Debug"),
        text="Display Runtime Settings",
        command=self.runtime_checkbox_event,
        onvalue=True,
        offvalue=False,
    )
    self.runtime_checkbox.configure(border_color="#6563ff")
    self.runtime_checkbox.grid(row=3, column=3, padx=20, pady=10, sticky="w")


# ##################################################################################
# Either validate the file location provided or provide a filelist of XML files
# ##################################################################################
def validate_or_filelist_xml(
    self, android_ipaddr: str, android_port: str, android_file: str
) -> tuple[int, str]:  # noqa: ANN001
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
        self.filelist_label = customtkinter.CTkLabel(
            self,
            text="Select XML File From Android Device:",
            anchor="w",
        )
        self.filelist_label.grid(row=9, column=1, columnspan=2, padx=(200, 10), pady=(0, 10), sticky="sw")
        self.filelist_option = customtkinter.CTkOptionMenu(
            self,
            values=filelist,
            command=self.file_selected_event,
        )
        self.filelist_option.grid(row=10, column=1, columnspan=2, padx=(200, 10), pady=(0, 10), sticky="nw")
        self.android_ipaddr = android_ipaddr
        self.android_port = android_port
        return 2, "", "", ""  # Just return with error so the prompt comes up to select file.

    # All is okay
    return 0, android_ipaddr, android_port, android_file
