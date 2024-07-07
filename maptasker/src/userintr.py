"""Code to manage the graphical user interface."""

#! /usr/bin/env python3

#                                                                                      #
# userintr: provide GUI and process input for program arguments                        #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #

import contextlib
import json
import os
import sys
import webbrowser
from pathlib import Path
from typing import Callable

import customtkinter
import requests

from maptasker.src.colrmode import set_color_mode
from maptasker.src.config import AI_PROMPT, DEFAULT_DISPLAY_DETAIL_LEVEL, OUTPUT_FONT

# from CTkColorPicker.ctk_color_picker import AskColor
from maptasker.src.ctk_color_picker import AskColor
from maptasker.src.getids import get_ids
from maptasker.src.getputer import save_restore_args
from maptasker.src.guimap import get_the_map
from maptasker.src.guiutils import (
    CHANGELOG,
    add_button,
    add_cancel_button,
    add_label,
    build_profiles,
    check_for_changelog,
    clear_android_buttons,
    clear_tasker_data,
    create_changelog,
    display_analyze_button,
    display_current_file,
    display_messages_from_last_run,
    display_selected_object_labels,
    get_api_key,
    get_xml,
    is_new_version,
    list_tasker_objects,
    ping_android_device,
    reload_gui,
    set_tasker_object_names,
    setup_name_error,
    update_tasker_object_menus,
    valid_item,
    validate_or_filelist_xml,
)
from maptasker.src.guiwins import (
    CTkHyperlinkManager,
    CTkTextview,
    CTkTreeview,
    TextWindow,
    get_rid_of_window,
    initialize_gui,
    initialize_screen,
    save_window_position,
    store_windows,
)
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.lineout import LineOut
from maptasker.src.mapit import clean_up_memory, mapit_all
from maptasker.src.maputils import update, validate_xml_file
from maptasker.src.outline import outline_the_configuration
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import (
    ARGUMENT_NAMES,
    CHANGELOG_JSON_URL,
    DIAGRAM_FILE,
    KEYFILE,
    OPENAI_MODELS,
    TYPES_OF_COLOR_NAMES,
    VERSION,
    DISPLAY_DETAIL_LEVEL_all_parameters,
    logger,
)
from maptasker.src.taskerd import get_the_xml_data

# Color Modes: "System" (standard), "Dark", "Light"
customtkinter.set_appearance_mode("System")
# Themes: "blue" (standard), "green", "dark-blue"
customtkinter.set_default_color_theme("blue")

# NOTE: The textbox is used for help information via new_message_box, normal one-liner messages via display_message_box
#       and multi-line messages via display_multiple_message.
# Help Text
INFO_TEXT = (
    "MapTasker displays your Android Tasker configuration based on your uploaded Tasker XML "
    "file (e.g. 'backup.xml'). The display will optionally include all Projects, Profiles, Tasks "
    "and their actions, Profile/Task conditions and other Profile/Task related information.\n\n"
    "* Display options are:\n"
    "    Level 0: display first Task action only, for unnamed Tasks only (silent).\n"
    "    Level 1 = display all Task action details for unknown Tasks only (default).\n"
    "    Level 2 = display full Task action name on every Task.\n"
    "    Level 3 = display full Task action details on every Task with action details.\n"
    "    Level 4 = display level of 3 plus Project's global variables.\n\n"
    "* Just Display Everything: Turns on the display of "
    "conditions, TaskerNet information, preferences, pretty output, directory, and configuration outline.\n\n"
    "* Display Conditions: Turn on the display of Profile and Task conditions.\n\n"
    "* Display TaskerNet Info - If available, display TaskerNet publishing information.\n\n"
    "* Display Tasker Preferences - display Tasker's system Preferences.\n\n"
    "* Hide Task Details under Twisty: hide Task information within ► and click to display.\n\n"
    "* Display Directory of hyperlinks at beginning.\n\n"
    "* Display Configuration Outline and Map of your Projects/Profiles/Tasks/Scenes.\n\n"
    "* Display Prettier Output: Make the output more human-readable by adding newlines and indentation for all arguments.\n\n"
    "* Project/Profile/Task/Scene Names options to italicize, bold, underline and/or highlight their names.\n\n"
    "* Indentation amount for If/Then/Else Task Actions.\n\n"
    "* Save Settings - Save these settings for later use.\n\n"
    "* Restore Settings - Restore the settings from a previously saved session.\n\n"
    "* Report Issue - This will bring up your browser to the issue reporting site, and you can use this to "
    "either report a bug or request a new feature ( [Feature Request] )\n\n"
    "* Appearance Mode: Dark, Light, or System default.\n\n"
    "* Tree View: Display a tree of your Projects/Profiles/Tasks.\n\n"
    "* Reset Options: Clear everything and start anew.\n\n"
    "* Clear Messages: Clear any messages in the textbox.\n\n"
    "* Font To Use: Change the monospace font used for the output.\n\n"
    "* Display Outline: Display Projects/Profiles/Tasks/Scenes configuration outline.\n\n"
    "* Get XML from Android Device: fetch the backup/exported "
    "XML file from Androiddevice.  You will be asked for the IP address and port number for your"
    " Android device, as well as the file location on the device.\n\n"
    "* Get Local XML: fetch the backup/exported XML file from your local drive.\n\n"
    "* Run and Exit: Run the program with the settings provided and then exit.\n"
    "* ReRun: Run multiple times (each time with new settings) without exiting.\n\n"
    "* Specific Name tab: enter a single, specific named item to display...\n"
    "   - Project Name: enter a specific Project to display.\n"
    "   - Profile Name: enter a specific Profile to display.\n"
    "   - Task Name: enter a specific Task to display.\n"
    "   (These three are exclusive: enter one only)\n\n"
    "* Colors tab: select colors for various elements of the display.\n"
    "              (e.g. color for Projects, Profiles, Tasks, etc.).\n\n"
    "* Analyze tab: Run the analysis for a Project, Profile or Task against an Ai model.\n\n"
    "* Debug tab: Display Runtime Settings option and turn on Debug mode.\n\n"
    "* Exit: Exit the program (quit).\n\n"
    "Notes:\n\n"
    "- You will be prompted to identify your Tasker XML file once you hit the 'Run and Exit' or 'ReRun' button if you have not yet done so.\n\n"
    "- If running on OS X Ventura, you may receive the runtime error: '+[CATransaction synchronize] called within transaction'. This is a bug in OS X Ventura. This can be ignored and the program will still run correctly.\n\n"
    "- If you receive the runtime error: 'IMKClient Stall detected...', this can be ignored.\n\n"
    "- Drag the window to expand the text as desired.\n\n"
)
BACKUP_HELP_TEXT = (
    "The following steps are required in order to fetch a Tasker XML file directly"
    " from your Android device.\n\n"
    "1- Both this device and the Android device must be on the same named network.\n\n"
    "2- The Tasker Project 'HTTP Server Example' or identical function must be"
    " installed and active on the Android device (the server must be running):\n\n"
    "    https://shorturl.at/bwCD4\n\n"
    "3- If you want to use the 'List XML Files' option, then you must also import the following profile "
    "into the Android device and make sure the imported profile 'MapTasker List' is enabled:\n\n"
    "    https://shorturl.at/sGS08\n\n"
    "You will be asked for the IP address, the port number for your Android device,"
    " as well as the file location on the Android device.  Default values are supplied, where...\n\n"
    "'192.168.0.210' is the default IP address,\n\n'1821' is the default port number for the Tasker HTTP"
    " Server Example running on your Android device\n\n'/Tasker/configs/user/backup.xml' is the default file location.  "
    "If you don't know the file location and have already entered your IP address and port, then you can select "
    "the 'List XML Files' button to get a list of available XML files on your Android device for selection.\n\n"
    "Usage Notes:\n\n"
    "The IP address and port can be obtained by installing the 'HTTP Server Example' project from the above URL "
    "on your Android device. Then run the task named 'Update GD HTTP Info' to get the Android notification:\n\n"
    "HTTP Server Info\n"
    'Server info updated {"device name":"http://192.168.0.49:1821"}\n\n'
    "- To fetch the XML file, click on the button\n\n 'Get XML from Android Device'\n\n"
    "Then modify the default values presented in the input fields below this button, and then"
    " click on the button 'Enter and Click Here to Set XML Details' or 'List XML Files'.\n\n"
    "- Hitting either button will ping the Android device to see if it is available.  The ping will timeout after"
    " 10 seconds if the device is not reachable.  Make sure that the IP address is correct.\n\n"
    "Click on the 'Cancel Entry' button to back out of this fetch process.\n\n"
)
LISTFILES_HELP_TEXT = (
    "Clicking this button will result in the following actions:\n\n"
    "- The IP Address will be used to ping the Android device.\n\n"
    "- The IP Address and port number will be used to query the Android device and get a list of available XML files "
    "found in the Tasker folder.\n\n"
    "- The list of found XML files will be presented in a pulldown menu from which you can select the one you want "
    "to use.\n\n"
    "- Once you have selected the XML file, it will be fetched and verified as valid XML which is then used as "
    "input to the program once you subsequently click on the 'Run' or 'ReRun' button.\n\n"
    "In order for this to work, you MUST have already imported the 'MapTasker List' profile into Tasker running "
    "on your Android device.  This profile can be found at the following URL:\n\n"
    "    https://shorturl.at/buvK6\n\n"
)

VIEW_HELP_TEXT = (
    "XML must first be obtained from the either local drive or Android device for the views to work.\n\n"
    "All view windows can be stretched and moved as needed.  Rerun the specific view command to refresh the view with the new size and position.\n\n"
    "If the XML has already been fetched, it will be used as input to the view.  Hitting the 'Reset' button will clear the view data."
    " In otherwords, the view will remain the same until either the 'Reset' button is hit, or a new XML file is fetched from the"
    " local drive or Android device.\n\n"
    "\nThe Map View has the following behavior:\n\n"
    " - The coloring and highlighting of the map is targeted for a future release.\n\n"
    " - While the browser is not invoked directly, the map is displayed in the browser by opening the 'MapTasker.html' file.\n\n"
    " - The horizontal scrollbar goes beyond the end of the map for some reason.\n\n"
    " - The vertical scrollbar only appears for lines that are too long for the text window.\n\n"
    " - The display 'Directory' and 'Outline' settings are ignored since they do not work in the Map view.\n\n"
    "\nThe Diagram View has the following behavior:\n\n"
    " - Only Projects and Profiles can be displayed. XML consisting of only a single Task or Scene will not be displayed.\n\n"
    "\nThe Tree View has the following behavior:\n\n"
    "- Huge configurations that scroll beyond the bottom of the screen are not viewable in their entirety yet.\n\n"
    "- Only Projects can be displayed. XML consisting of only a single Profile or Task or Scene will not be displayed.\n\n"
)

AI_HELP_TEXT = (
    "The Analyze tab is used to run the Ai analysis on your Profile, using either the local llama model or the server-based Open Ai model.\n\n"
    "The following steps are required in order to run Ai against your Profile.\n\n"
    "1- If using Open Ai, you must have a valid Open Ai API key.  You can use the 'Show/Edit Open AI key' button to enter your key.\n\n"
    "2- The default prompt is:'how could it be improved:', and is automatically preceded by: 'Given the following (Project/Profile/Task) in Tasker, '.  If modifying the prompt, you are only modifing the 'how could it be improved:' portion.\n\n"
    "3- If you select a local model that has not yet been loaded, Ollama will be loaded in the background once the analysis begins.\n\n"
    "4- Select the model you want to use.\n\n"
    "5- Click the 'Run Analysis' button.  It will turn pink when all of the necessary data has been entered.\n\n"
    "   o If you have not yet selected a model, prompt or single Project, Profile or Task, then you will be prompted to do so first.\n\n"
    "   o The process may take some time and runs in the background.  The results will appear in a separate window.\n\n"
    "Your designated api-key (if any), model, selected Project, Profile or Task and Ai prompt will all be saved across sessions.\n\n"
    "Models that start with 'gpt' are server-based models.  All others are local models.\n\n"
    "The 'Rerun' feature will be used to display the results of the analysis in a new window.\n\n"
)

HELP = f"MapTasker {VERSION} Help\n\n{INFO_TEXT}{CHANGELOG}"
all_objects = "Display all Projects, Profiles, and Tasks."


# Class to define the GUI configuration
class MyGui(customtkinter.CTk):
    """
    Main class for GUI.
        Args:
            customtkinter (_type_): GUI class from customtkinter library.
    """

    def __init__(self) -> None:
        """
        Initializes the GUI, adds menu elements, and sets default values.
        If not resetting, restores settings and updates fields.
        Checks for single item to be displayed. Checks for newer version of code on Pypi every 24 hours.
        Displays upgrade button if new version is available.
        Checks for changelog and displays message box if applicable."""
        super().__init__()
        # Set up event handlers
        self.event_handlers = EventHandlers(self)

        # Initialize GUI
        initialize_gui(self)

        # Hide the window since initialize_screen would otherwise display an incomplete window until the geometry is properly set.
        self.withdraw()

        # Add menu elements
        initialize_screen(self)

        # set default values
        self.set_defaults()

        # Now restore the settings and update the fields if not resetting.
        if not PrimeItems.program_arguments["reset"]:
            self.event_handlers.restore_settings_event()
        else:
            self.display_message_box("GUI started with the '-reset' option.\n", "Green")

        # Set the window's geometry
        self.set_main_window_geometry()

        # See if we have any carryover error messages from last run (rerun).
        # Note: this must go after the settings restoration.
        display_messages_from_last_run(self)

        # If we are getting XML from Android device, display the details.
        if self.android_ipaddr:
            # Display backup details as a label
            self.display_backup_details()

        # Update the Project/Profile/Task pulldown option menus and text labels.
        # update_tasker_object_menus(self, get_data=True)

        # Check if newer version of our code is available on Pypi.
        self.check_new_version()

        # See if we have a changelog, and get it if we do.  This must go before 'self.process_current_messages()' call.
        check_for_changelog(self)

        # See if we have any current messages to display.
        self.process_current_messages()

        # Finally, show the window. It was hidden in initialize_screen.
        self.deiconify()
        # The following line is equivelent to a call to update_tasker_object_menus but only when the Analysis tab is clicked.
        self.tabview.configure("Analyze", command=update_tasker_object_menus(self, get_data=True))

        # Update the analysis button
        display_analyze_button(self, 13, first_time=True)

        # Process Map View
        if PrimeItems.program_arguments["mapgui"]:
            self.display_map()

        # We are done with the initialization.
        self.display_message_box("Initialization complete.\n", "Green")

        # Turn off first time
        self.first_time = False

    # Establish all of the default values used
    def set_defaults(self) -> None:
        # Item names must be the same as their value in
        #  PrimeItems.program_arguments
        """
        Sets default values for attributes.
        Args:
            first_time: {bool}: Indicates if it is the first time running the program.
        Returns:
            None: No value is returned.
        {Processing Logic:
        - Sets default values for attributes like sidebar detail level, conditions flags etc.
        - Sets appearance mode, indent etc.
        - Inserts help text if first_time is True
        - Initializes empty dictionaries and default font
        - Handles initialization of backup file attributes if not already defined
        - Displays single name status message
        }"""
        self.sidebar_detail_option.configure(values=["0", "1", "2", "3", "4", "5"])
        self.sidebar_detail_option.set(str(DEFAULT_DISPLAY_DETAIL_LEVEL))
        self.display_detail_level = DEFAULT_DISPLAY_DETAIL_LEVEL
        self.conditions = self.preferences = self.taskernet = self.debug = self.everything = self.clear_settings = (
            self.reset
        ) = self.restore = self.exit = self.bold = self.highlight = self.italicize = self.underline = (
            self.go_program
        ) = self.outline = self.rerun = self.list_files = self.runtime = self.save = self.twisty = self.directory = (
            self.pretty
        ) = self.fetched_backup_from_android = False
        self.single_project_name = ""
        self.single_profile_name = ""
        self.single_task_name = ""
        self.file = ""
        self.color_text_row = 2
        self.appearance_mode_optionmenu.set("System")
        self.appearance_mode = "system"
        self.indent_option.set(DEFAULT_DISPLAY_DETAIL_LEVEL)
        self.indent = 4
        self.color_labels = []
        self.android_ipaddr = ""
        self.android_port = ""
        self.android_file = ""
        if self.first_time:
            self.all_messages = {}
        self.color_lookup = {}  # Setup default dictionary as empty list
        self.font = OUTPUT_FONT
        self.gui = True
        self.color_row = 4
        self.message = ""
        self.ai_model = ""
        self.ai_analyze = False
        self.ai_model = ""
        self.ai_prompt = AI_PROMPT
        self.specific_name_msg = ""
        self.current_file_display_message = True
        # Setup default window position = current position or first-time position
        if self.first_time:
            if PrimeItems.program_arguments["window_position"]:
                self.window_position = PrimeItems.program_arguments["window_position"]
            else:
                self.window_position = "1129x937+698+145"  # Default window position
        else:
            self.window_position = save_window_position(self)

        # Display current Items setting.
        with contextlib.suppress(AttributeError):  # single_name_status may not be defined yet.
            self.single_name_status(all_objects, "#3f99ff")

    # Display the Backup button
    def display_backup_button(self, the_text: str, color1: str, color2: str, routine: Callable) -> None:
        """
        Displays a backup button on the GUI.
        Args:
            the_text: The text to display on the button in one line
            color1: The foreground color of the button in one line
            color2: The border color of the button in one line
        Returns:
            self.get_backup_button: the button object
        Processing Logic:
            - Creates a CTkButton object with the given text, colors and command
            - Places the button on row 7, column 1 spanning 2 columns with padding
            - Configures the button to be stuck to the northwest side of its cell
        """
        # 'Get Backup Settings' button definition
        self.get_backup_button = add_button(
            self,
            self,
            color1,
            ("#0BF075", "#FFFFFF"),
            color2,
            routine,
            1,
            the_text,
            2,  # Column span
            7,  # row
            1,  # col
            (210, 165),
            (0, 10),
            "nw",
        )
        return self.get_backup_button

    # Display Message Box
    def display_message_box(self, message: str, color: str) -> None:
        """
        Display Message Box

        Args:
            message (str): The text to display in the textbox.
            color (str): The color of the text.

        Returns:
            None

        This method deletes the contents of the existing text box and recreates it with a new height and width.
        It then iterates through the messages stored in the `all_messages` dictionary and inserts each message into the text box.
        The messages are tagged with a unique identifier and their color is configured.
        After inserting all the messages, the new message and its color are added to the text box.
        The text box is configured to wrap words and the inserted text is tagged with its color.
        Finally, the text box gains focus.
        """
        # Catch erroneous message
        if message == "None":
            return

        # Clear previous messages
        if self.clear_messages:
            self.clear_messages = False
            self.event_handlers.clear_messages_event()

        # Convert numeric to proper format
        if color.isnumeric():
            color = f"#{color}"

        # Get the total number of lines already in the text box.
        line_num = len(self.all_messages)

        # Insert the text with our new message into the text box.
        line_num += 1  # Increment our line number to the line with the message
        line_num_str = str(line_num)
        # message = f"{line_num_str}: {message}"  # For debug only
        # Add this message to our dictionary of messages.
        self.all_messages[line_num] = {
            "text": f"{message}\n",
            "color": color,
            "highlight_color": "",
            "highlight_position": "",
        }
        # Add the text and color to the text box.
        # fmt: off
        self.textbox.insert(f"{line_num_str}.0", f"{message}\n", (line_num_str))
        self.textbox.tag_add(line_num_str, f"{line_num_str}.0", f"{line_num_str}.{len(message)!s}")
        # fmt: on
        self.textbox.tag_config(line_num_str, foreground=self.all_messages[line_num]["color"])

        # If current message is a setting ("set On/Off/True/False"), then color it
        self.check_message_for_special_highlighting(message, line_num_str)

        # self.textbox.focus_set()
        # Set the font
        self.textbox.configure(font=(self.font, 14))

    # Check the current messsage for additional highlighting
    def check_message_for_special_highlighting(self, message: str, line_num_str: str) -> None:
        """
        Checks if the message is a setting and highlights it if so.

        Args:
            message (str): The message to check.
            line_num_str (str): The line number of the message.

        Returns:
            None
        """
        keywords = {
            "set Off": "Red",
            "set On": "LimeGreen",
            "set to False": "Red",
            "set to True": "LimeGreen",
            "is not named": "Red",
            "is named": "LimeGreen",
            "set to": "LimeGreen",
            "is not set": "Red",
        }

        final_position = -1
        highlight_color = ""

        for keyword, color in keywords.items():
            position = message.find(keyword)
            if position != -1:
                highlight_color = color
                final_position = position
                break

        if final_position == -1:  # No specific keyword found
            position = message.find("set to")
            if position != -1 and "color" not in message:
                highlight_color = "LimeGreen"
                final_position = position

        # Do we have a highlight color?  If so, highlight the string.
        if highlight_color:
            self.highlight_string(message, line_num_str, final_position, highlight_color)

    # Highlight a string in the textbox.
    def highlight_string(self, message: str, line_num_str: str, highlight_position: int, highlight_color: str) -> None:
        """
        Adds a tag to the text box highlighting a specific portion of text in a specific color.

        Args:
            message (str): The text to highlight.
            line_num_str (str): The line number of the text.
            highlight_position (int): The position in the line to start highlighting.
            highlight_color (str): The color for the highlighted text.

        Returns:
            None
        """
        self.textbox.tag_add(
            f"{line_num_str}setto",
            f"{line_num_str}.{highlight_position!s}",
            f"{line_num_str}.{len(message)!s}",
        )
        self.textbox.tag_config(f"{line_num_str}setto", foreground=highlight_color)
        self.all_messages[int(line_num_str)]["highlight_color"] = highlight_color
        self.all_messages[int(line_num_str)]["highlight_position"] = highlight_position

    # Validate name entered
    def check_name(self, the_name: str, element_name: str) -> bool:
        """
        Checks name validity
        Args:
            the_name: str - Name to check
            element_name: str - Element type being named
        Returns:
            bool - Whether name is valid
        Processing Logic:
            1. Check for blank name
            2. Check that only one of project, profile, task is named
            3. Check that named item exists in valid items
            4. If error, display message and clear individual names
            5. If valid, display confirmation message and return True
        """
        error_message = ""
        # Check for missing name
        if not the_name:
            error_message = [
                f"Either the name entered for the {element_name} is blank or the 'Cancel' button was clicked.\n",
                "All Projects, Profiles, and Tasks will be displayed.\n",
            ]

            self.named_item = False
        # Check to make sure only one named item has been entered
        elif self.single_project_name and self.single_profile_name:
            error_message = setup_name_error("Project", "Profile", self.single_project_name, self.single_profile_name)
        elif self.single_project_name and self.single_task_name:
            error_message = setup_name_error("Project", "Task", self.single_project_name, self.single_task_name)
        elif self.single_profile_name and self.single_task_name:
            error_message = setup_name_error("Profile", "Task", self.single_profile_name, self.single_task_name)

        # Make sure the named item exists
        elif not valid_item(self, the_name, element_name, self.debug, self.appearance_mode):
            front_error = f'Error: Trying to validate "{the_name}" {element_name}'
            if not PrimeItems.file_to_get:
                error_message = [
                    f'{front_error}, but the "Cancel" was selected!\n',
                ]
                set_tasker_object_names(self)  # Update pulldown menus
            else:
                try:
                    file_name = PrimeItems.file_to_get.name
                except AttributeError:
                    file_name = PrimeItems.file_to_get
                error_message = [
                    f"{front_error} but it was not found in {file_name}!  All Projects, Profiles and Tasks will be displayed.\n",
                ]

        # If we have an error, display it and blank out the various individual names
        if error_message:
            self.display_multiple_messages(error_message, "Red")
            (
                self.single_project_name,
                self.single_profile_name,
                self.single_task_name,
            ) = ("", "", "")
            return False

        # No error.
        if the_name == "None":
            self.display_message_box("'None' selected.  Displaying all Projects, Profiles and Tasks.", "Green")
        else:
            self.display_message_box(
                f"Display only the '{the_name}' {element_name} (overrides any previous set name).",
                "Green",
            )
        return True

    # Process single name restore
    def process_single_name_restore(
        self,
        my_name: str,
        name_entered: str,
    ) -> None:
        """
        Restores a single name based on the provided name type.
        Args:
            my_name: Name of the type to restore (Project, Profile, Task)
            name_entered: Name entered by the user
        Returns:
            None: No value is returned
        Processing Logic:
            - Check if the entered name is valid
            - Clear existing single name values
            - Match the name type and assign the entered name to the correct single name attribute
            - Do nothing if an invalid name type is provided"""
        # Don't display current_file message
        self.current_file_display_message = False
        # Make sure it is a valid Profile name
        if name_entered == "None or unnamed!":
            self.single_profile_name = ""
            return  # Ignore unnamed file
        if self.file:
            PrimeItems.file_to_get = self.file  # Load file for def get_xml

        ## Let uer know what is happening
        # self.display_message_box(f"Verifing {my_name}...", "Green")

        # Validate the name by using the existing XML or reading it in.
        # We will prompt user for XML file if it hasn't already been loaded.
        if name_entered and self.check_name(name_entered, my_name):
            self.single_project_name = self.single_profile_name = self.single_task_name = ""

            match my_name:
                case "Project":
                    self.single_project_name = name_entered
                case "Profile":
                    self.single_profile_name = name_entered
                case "Task":
                    self.single_task_name = name_entered
                case _:
                    pass

    # Define the textbox for information/feedback
    def create_new_textbox(self) -> None:
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
        """
        self.textbox = customtkinter.CTkTextbox(self, height=650, width=250)
        self.textbox.grid(row=0, column=1, padx=(20, 0), pady=(20, 0), sticky="ew")
        self.textbox.configure(font=(self.font, 14), wrap="word", scrollbar_button_color="#6563ff")
        self.hyperlink = CTkHyperlinkManager(self.textbox)

    # ################################################################################
    # Select or deselect a checkbox based on the value passed in
    # ################################################################################
    def get_input_and_put_message(self, checkbox: customtkinter.CHECKBUTTON, title: str) -> bool:
        """
        Get checkbox value and display message
        Args:
            checkbox: Customtkinter checkbox object
            title: Title of message box
        Returns:
            checkbox_value: Value of checkbox
        - Get value of checkbox passed as argument
        - Display message box with title and checkbox value
        - Return checkbox value"""
        checkbox_value = checkbox.get()
        self.inform_message(title, checkbox_value, "")
        return checkbox_value

    # Rebuilld message box with new text (e.g. for Help).
    def new_message_box(self, message: str) -> None:
        # Clear any prior error message
        """
        Displays a message in a textbox widget.
        Args:
            message (str): The message to display
        Returns:
            None
        Processing Logic:
            - Clears any prior error message in the textbox
            - Recreates the textbox widget
            - Inserts the message text
            - Sets the textbox to read-only and wraps text
            - Applies a color tag to a portion of the text
        """
        self.textbox.destroy()

        # Recreate text box
        self.create_new_textbox()
        # Insert the text.
        self.textbox.insert("0.0", message)

        # Check for hyperlink
        # [hypers.append(m.start()) for m in re.finditer("https://", message)]
        hyper = message.find("https://")
        if hyper != -1:
            text_lines = message.split("\n")
            for num, line in enumerate(text_lines):
                hyper = line.find("https://")
                if hyper != -1:
                    end_hyper = line.find(" ", hyper)
                    if end_hyper == -1:
                        end_hyper = len(line)
                    link = line[hyper : end_hyper + 1]
                    # Delete the http url
                    self.textbox.delete(f"{num+1}.{hyper}", f"{num+1}.{end_hyper+1}")
                    # Add the link
                    self.textbox.insert(f"{num+1}.{end_hyper+2}", link, self.hyperlink.add(link))

        # Display some colored text: the heading
        self.textbox.tag_add(
            "color",
            "1.0",
            f"1.{len(message)}",
        )  # '1.5' means first line, 5th character; '1.11' means first line, 11th character
        self.textbox.tag_config("color", foreground="green")
        self.all_messages = {}

    # ################################################################################
    # Inform user of toggle selection
    # ################################################################################
    def inform_message(self, toggle_name: str, toggle_value: str, number_value: str) -> None:
        """
        Set a toggle and display a message box
        Args:
            toggle_name: Name of the toggle being set
            toggle_value: Value of the toggle
            number_value: Optional number value
        Returns:
            None
        - Check if number_value is empty, set response to number_value and extra text to " to "
        - If toggle_value is True, set response to "On"
        - If toggle_value is False, set response to "Off"
        - Display message box with toggle name, response and extra text
        """
        extra = " "
        if number_value != "":
            response = number_value
            extra = " to "
        elif toggle_value:
            response = "On"
        else:
            response = "Off"
        self.display_message_box(f"{toggle_name} set{extra}{response}", "Green")

    # ################################################################################
    # Select or deselect a checkbox based on the value passed in
    # ################################################################################
    def select_deselect_checkbox(
        self,
        checkbox: customtkinter.CHECKBUTTON,
        checked: bool,
        argument_name: str,
    ) -> str:
        """Select or deselect a checkbox widget
        Args:
            checkbox: The checkbox widget to select or deselect
            checked: Whether to select or deselect the checkbox
            argument_name: The name of the argument being checked/unchecked
        Returns:
            status: A string indicating if the checkbox was selected or deselected
        - Check if checked is True, call checkbox.select() to select it
        - Check if checked is False, call checkbox.deselect() to deselect it
        - Return a string with the argument name and checked status"""
        checkbox.select() if checked else checkbox.deselect()
        return f"{argument_name} set to {checked}.\n"

    # Given a setting key and value, set the attribute for the key to the value and return the setting as a message.
    # @profile
    def restore_display(self, key: str, value: str) -> str:
        # Dictionary of program arguments and function to run for each upon restoration.
        """
        Restores display settings
        Args:
            key: str - Setting name
            value: str - Setting value
        Returns:
            message: str - Message describing setting change
        {Processing Logic}:
            - Maps setting names to lambda functions for processing
            - Checks for special case settings and sets attribute directly
            - Looks up and runs corresponding lambda function
            - Returns message generated by lambda function
        """
        message = ""
        keys_to_ignore = {
            "gui",
            "save",
            "restore",
            "rerun",
            "reset",
            "window_position",
            "ai_analysis_window_position",
            "color_window_position",
            "diagram_window_position",
            "map_window_position",
            "tree_window_position",
            "mapgui",
            "fetched_backup_from_android",
        }
        message_map = {
            "android_ipaddr": lambda: f"Android Get XML TCP IP Address set to {value}\n",
            "android_port": lambda: f"Android Get XML Port Number set to {value}\n",
            "android_file": lambda: f"Android Get XML File Location set to {value}\n",
            "appearance_mode": lambda: self.event_handlers.change_appearance_mode_event(value),
            "bold": lambda: self.select_deselect_checkbox(self.bold_checkbox, value, "Display Names in Bold"),
            "conditions": lambda: self.select_deselect_checkbox(
                self.condition_checkbox,
                value,
                "Display Profile/Task Conditions",
            ),
            "debug": lambda: self.select_deselect_checkbox(self.debug_checkbox, value, "Debug Mode"),
            "directory": lambda: self.select_deselect_checkbox(self.directory_checkbox, value, "Display Directory"),
            "display_detail_level": lambda: self.event_handlers.detail_selected_event(value),
            # "fetched_backup_from_android": lambda: f"Fetched XML From Android:{value}.\n",
            "file": lambda: self.display_and_set_file(value),
            "font": lambda: self.event_handlers.font_event(value),
            # "font": lambda: f"Font set to {value}.\n",
            "highlight": lambda: self.select_deselect_checkbox(
                self.highlight_checkbox,
                value,
                "Display Names Highlighted",
            ),
            "indent": lambda: self.event_handlers.indent_selected_event(value),
            "italicize": lambda: self.select_deselect_checkbox(
                self.italicize_checkbox,
                value,
                "Display Names Italicized",
            ),
            "outline": lambda: self.select_deselect_checkbox(
                self.outline_checkbox,
                value,
                "Display Configuration Outline",
            ),
            "preferences": lambda: self.select_deselect_checkbox(
                self.preferences_checkbox,
                value,
                "Display Tasker Preferences",
            ),
            "pretty": lambda: self.select_deselect_checkbox(
                self.pretty_checkbox,
                value,
                "Display Prettier",
            ),
            "runtime": lambda: self.select_deselect_checkbox(self.runtime_checkbox, value, "Display Runtime Settings"),
            "single_profile_name": lambda: self.process_single_name_restore("Profile", value),
            "single_project_name": lambda: self.process_single_name_restore("Project", value),
            "single_task_name": lambda: self.process_single_name_restore("Task", value),
            "taskernet": lambda: self.select_deselect_checkbox(
                self.taskernet_checkbox,
                value,
                "Display TaskerNet Information",
            ),
            "twisty": lambda: self.select_deselect_checkbox(
                self.twisty_checkbox,
                value,
                "Hide Task Details Under Twisty",
            ),
            "underline": lambda: self.select_deselect_checkbox(
                self.underline_checkbox,
                value,
                "Display Names Underlined",
            ),
        }

        # Processs specific items that have no effect on the GUI
        if key in keys_to_ignore:
            message = ""
            # Check if key is an attribute on self before setting
            if hasattr(self, key):
                setattr(self, key, value)
        else:
            # Use dictionary lookup and lambda funtion to process key/value.
            message_func = message_map.get(key)
            if message_func:
                # Note: display_detail_level, file, font, indent, and single object name all return a message of 'None'.
                message = message_func()  # This calls the lambda function and takes a bit of time.
            elif self.debug:
                logger.debug("userintr: no lambda rtn for key or value: ", key, value)

        # Cleanup the end of the message if it is not set.
        the_empty_ending = "set to \n"
        the_empty_ending_length = len(the_empty_ending)
        named_ending = "named ''.\n"
        named_ending_length = len(named_ending)
        if message is None or message == "":
            return ""
        if message.endswith(the_empty_ending):
            message = f"{message[:-the_empty_ending_length]} is not set.\n"
        elif message.endswith(named_ending):
            message = f"{message[:-named_ending_length]} is not named.\n"

        return message

    # We have read colors and runtime args from backup file.  Now extract them for use.
    # @profile
    def extract_settings(self, temp_args: dict) -> None:
        """
        Extract settings from arguments dictionary
        Args:
            temp_args: Dictionary of settings
        Returns:
            None: Does not return anything
        - Loops through dictionary and sets attributes on object
        - Calls restore_display to get message for setting change
        - Loops through color lookup and builds message of color changes
        - Displays message box with all setting changes
        """
        for key, value in temp_args.items():
            if key is not None:
                setattr(self, key, value)
                if new_message := self.restore_display(key, value):
                    self.display_message_box(f"{new_message}\n", "Green")
        # Display the restored color changes, using the reverse dictionary of
        #   TYPES_OF_COLOR_NAMES (found in sysconst.py)
        inv_color_names = {v: k for k, v in TYPES_OF_COLOR_NAMES.items()}
        for key, value in self.color_lookup.items():
            text_out = value
            if key is not None:
                if key == "msg":
                    inv_color_names[key] = ""
                else:
                    # Set the displayed color to that of the color name, unlessa it is the background color.
                    color = value
                    if inv_color_names[key] == "Background":
                        color = "white"
                        text_out = f"{value} (displayed as white)"
                    with contextlib.suppress(KeyError):
                        self.display_message_box(f"{inv_color_names[key]} color set to {text_out}\n", color)

        # Display completion
        self.display_message_box("Settings restored.\n", "Green")

    # Display an input field and a label for the user to input a value
    def display_label_and_input(
        self,
        label: str,
        default_value: str,
        starting_row: int,
        indentation_x_label: int,
        indentation_y_label: int,
        indentation_y_input: int,
        input_name: customtkinter.CTkButton,
        label_name: customtkinter.CTkLabel,
        do_input: bool,
    ) -> None:
        """
        Display an input field and a label for the user to input a value
        Args:
            label: The label to display
            default_value: The default value to display
            starting_row: The grid row that the label starts on
            indentation_x_label: the x indentation amount for the label
            indentation_y_label: the y indentation amount for the label
            indentation_y_input: the y indentation amount for the input field
            input_name: the name of the input field
            do_input: whether to display the input field (True) or not (False)
        Returns:
            The value entered by the user
        Processing Logic:
            - Creates an entry field
            - Adds a label above the entry field
            - Inserts the default value into the entry field
            - Returns the value entered by the user
        """
        # Draw each on the same row, incrementing y factor for each
        # Add a label over the TCPIP entry field.
        label_name = customtkinter.CTkLabel(
            master=self,
            text=label,
            anchor="sw",
        )
        label_name.grid(
            row=starting_row,
            column=1,
            columnspan=1,
            padx=(200, indentation_x_label),
            pady=(indentation_y_label, 0),
            sticky="nw",
        )

        if do_input:
            # Display prompt/input field
            input_name = customtkinter.CTkEntry(
                self,
                placeholder_text=default_value,
            )
            input_name.configure(
                # width=320,
                fg_color="#246FB6",
                border_color="#1bc9ff",
                text_color=("#0BF075", "#1AD63D"),
            )
            input_name.insert(0, default_value)

            # Input field
            input_name.grid(
                row=starting_row,
                column=1,
                # columnspan=1,
                padx=(200, 70),
                pady=(indentation_y_input, 0),
                sticky="nw",
            )
        return input_name, label_name

    # Fetch Backup info error...process it.
    def backup_error(self, error_message: str) -> None:
        # Setup error message
        """
        Displays an error message and resets the UI.

        Args:
            error_message (str): The error message to display.
        Returns:
            None

        Processing Logic:
            - Display the error message in a message box
            - Delete any text in the entry field
            - Reset the 'Get Backup Settings' button definition and grid placement
        """
        if error_message:
            self.display_message_box(error_message, "Red")

    # Get list of lines and output them.
    def display_multiple_messages(self, details: list, color: str) -> None:
        """
        Display Android settings based on the given details list.

        :param self: The instance of the class.
        :param details: A list containing the details to be displayed.
        :param color: The color to display to error message in the message box.
        :return: None
        """
        # color = "Green" if good_or_bad else "Red"
        for line in details:
            self.display_message_box(line, color)

    # Fetching backup from Android.  Let the user know the specific details.
    def display_backup_details(self) -> None:
        """
        Displays backup details from Android device.
        Args:
            self: The class instance.
        Returns:
            None: Does not return anything.
        Processing Logic:
            - Displays label and input for getting backup.xml file from Android device
            - Displays label and input for TCP/IP Address and Port of Android device
            - Displays label and input for location of backup file on Android device
        """
        self.ip_label = add_label(
            self,
            self,
            "Getting XML file from Android device:",
            "",
            12,
            "normal",
            7,
            1,
            (0, 40),
            (50, 0),
            "ne",
        )

        # IP address and port
        self.port_label = add_label(
            self,
            self,
            f"TCP/IP Address: {self.android_ipaddr}   Port: {self.android_port}",
            "",
            12,
            "normal",
            7,
            1,
            (60, 0),
            (70, 0),
            "ne",
        )

        # Location of backup file on Android device...on same row as IP address and port.
        self.file_label = add_label(
            self,
            self,
            f"Location: {self.android_file}",
            "",
            13,
            "normal",
            7,
            1,
            (60, 0),
            (90, 50),
            "ne",
        )

        # Display the current file in sidebar
        display_current_file(self, self.android_file)

    # Close the GUI.
    def cleanup(self, run_only: bool) -> None:
        """Function:
        Closes the application.
        Parameters:
            run_only (bool): If True, only closes the application. If False, closes the application and withdraws the funds.
        Returns:
            None: Does not return anything.
        Processing Logic:
            - Closes the application.
            - If run_only is True, only closes the application.
            - If run_only is False, withdraws the funds before closing the application."""
        # Store window positions.
        store_windows(self)

        # If 'Run and Exit' only, then just quit.  Otherwise, destroy sidebar frame.
        if run_only:
            self.quit()
        else:
            # ReRun
            get_rid_of_window(self, delete_all=True)
            # Now get rid of stuff we don't want around anymore
            self.sidebar_frame.destroy()
            with contextlib.suppress(AttributeError):
                self.treeview_window.destroy()

    # Validate XML and close the GUI.
    def cleanup_and_run(self, run_only: bool) -> None:
        """Function: cleanup_and_run
        Parameters:
            run_only (bool): Flag to determine if program should only run and not display GUI.
        Returns:
            None: Does not return any value.
        Processing Logic:
            - Display "Program running..." message.
            - If XML is not valid, return to GUI.
            - If XML is valid, exit and return to process_gui.
            - If XML is not valid, return to GUI."""
        # Save our last window position
        self.window_position = self.winfo_geometry()

        # If XML is not valid, simply return to GUI.  Otherwise, exit and return to process_gui.
        if PrimeItems.xml_tree is None:
            PrimeItems.program_arguments["gui"] = True
            # Get and validate the XML.
            if self.load_xml():  # If true, the XML is valid.  Cleanup and exit.
                self.cleanup(run_only)
                self.display_message_box("Program running...", "Green")

            # XML error.  Just return to the GUI.
            else:
                return

        # Do the final cleanup of windows and exit.
        self.cleanup(run_only)

    # Prompt for and get the XML file from the local drive.
    def prompt_and_get_file(self, debug: bool, appearance_mode: str) -> bool:
        """
        Prompt for and get the XML file from the local drive.

        Args:
            self: The object instance.
            debug: Debug flag.
            appearance_mode: Mode of appearance.

        Returns:
            bool: True if successful, False otherwise.
        """
        return_code = get_xml(debug, appearance_mode)
        # Did we get an error reading the backup file?
        if return_code > 0:
            if return_code == 6:
                self.display_message_box("Cancel button pressed.\n", "Orange")
            else:
                self.display_multiple_messages(
                    [f"{PrimeItems.error_msg}\n", "Click 'Get Local XML' to try a different XML file."],
                    "Red",
                )
            return False

        # Good return from getting the XML
        if PrimeItems.file_to_get.name:
            self.display_and_set_file(PrimeItems.file_to_get.name)
            self.android_file = self.android_ipaddr = self.android_port = ""
            clear_android_buttons(self)
            self.display_message_box("'Get XML From Android' settings cleared.", "Green")
        return True

    # Load the XML if not already loaded.
    def load_xml(self) -> bool:
        """Load XML from a file or URL.
        Parameters:
            self (Tasker): Instance of Tasker class.
        Returns:
            - bool: True if successful, False otherwise.
        Processing Logic:
            - Check if file is specified.
            - If file is specified, read it.
            - If file is not specified, get from URL.
            - If file is not found, display error.
            - If error reading file, display error.
            - If successful, return True."""
        if (
            not PrimeItems.tasker_root_elements["all_projects"]
            and not PrimeItems.tasker_root_elements["all_profiles"]
            and not PrimeItems.tasker_root_elements["all_tasks"]
            or self.android_ipaddr
        ):
            if self.android_ipaddr == "" or self.android_file == "":
                if not self.prompt_and_get_file(self.debug, self.appearance_mode):
                    return False

            # We have a file identified.  We now have to read it in.
            else:
                filename_location = self.android_file.rfind(PrimeItems.slash) + 1
                file_to_use = PrimeItems.program_arguments["android_file"][filename_location:]
                if not file_to_use:
                    file_to_use = self.android_file[filename_location:]
                try:
                    PrimeItems.file_to_get = open(file_to_use)
                except FileNotFoundError:
                    self.display_message_box(f"XML file {file_to_use} not found.", "Red")
                    return False

                # Display the current file
                display_current_file(self, file_to_use)

                # Get the XML
                PrimeItems.program_arguments["gui"] = True
                return_code = get_the_xml_data()
                if return_code != 0:
                    return False

        return True

    # Build a hierarchical list of all of the Tasker elements.
    def build_the_tree(self) -> list:
        """Builds the hierarchical list of all of the Tasker elements.
        Parameters:
            self (object): The object calling the function.
        Returns:
            tree_data (list): The hierarchical list of all of the Tasker elements.
        Processing Logic:
            - Checks if the XML file has already been retrieved.
            - If not, calls the get_xml function.
            - If there is an error reading the backup file, displays an error message.
            - If the file has been identified, attempts to open it.
            - If the file is not found, displays an error message.
            - Gets all of the Tasker elements.
        """

        tree_data = []
        root = PrimeItems.tasker_root_elements
        # Start with Projects
        projects = root["all_projects"]
        if projects:
            for project in projects:
                project_name = projects[project]["name"]

                # Retrieves profile IDs for a given project and project name, excluding projects without profiles.
                if profile_ids := get_ids(True, projects[project]["xml"], project_name, []):
                    # Build our list of Profiles in this Project.
                    profile_list = build_profiles(root, profile_ids)

                # Project has no Profiles
                else:
                    profile_list = ["No Profiles Found"]

                # Process Scenes
                scene_names = None
                with contextlib.suppress(Exception):
                    scene_names = projects[project]["xml"].find("scenes").text
                if scene_names is not None:
                    scene_list = scene_names.split(",")
                    for scene in scene_list:
                        profile_list.append(f"Scene: {scene}")

                # Put it all together: Project, Profiles, and Tasks
                tree_data.append({"name": f"Project: {project_name}", "children": profile_list})

        # Return our data tree
        return tree_data

    # Display the tree view.
    def display_tree(self, tree_data: list) -> None:
        """Displays a treeview window with given data.
        Parameters:
            tree_data (list): List of data to be displayed in the treeview.
        Returns:
            None: This function does not return anything.
        Processing Logic:
            - Creates a new window if one does not exist.
            - Focuses on the window if it already exists.
            - Displays the given data in a treeview format.
            - Packs the treeview in the window with specified padding and filling."""
        if tree_data:
            if self.treeview_window is None or not self.treeview_window.winfo_exists():
                self.treeview_window = TextWindow(
                    master=self,
                    window_position=self.tree_window_position,
                    title="Tree View",
                )  # create window if its None or destroyed

            else:
                self.treeview_window.focus()  # if window exists focus it

            # Display the tree in the toplevel window.
            tree_view = CTkTreeview(master=self.treeview_window, items=tree_data)
            tree_view.pack(padx=10, pady=10, fill="both", expand=True)
        else:
            self.display_message_box("No Project(s) Found in XML!", "Red")

    # Display diagram view
    def display_diagram(self, diagram_data: list) -> None:
        """Displays a diagram window with given data.
        Parameters:
            diagram_data (list): List of data to be displayed in the diagramview.
        Returns:
            None: This function does not return anything.
        Processing Logic:
            - Creates a new window if one does not exist.
            - Focuses on the window if it already exists.
            - Displays the given data in a view format.
            - Packs the diagramview in the window with specified padding and filling."""
        if diagram_data:
            if self.diagramview_window is None or not self.diagramview_window.winfo_exists():
                self.diagramview_window = TextWindow(
                    master=self,
                    window_position=self.diagram_window_position,
                    title="Diagram View",
                )  # create window if its None or destroyed
            else:
                self.diagramview_window.focus()  # if window exists focus it

            # Display the diagram.
            diagram_view = CTkTextview(master=self.diagramview_window, title="Diagram View", the_data=diagram_data)
            diagram_view.pack(padx=10, pady=10, fill="both", expand=True)
        else:
            self.display_message_box("No Project(s) Found in XML!", "Red")

    # Display dmap view
    def display_map(self) -> None:
        """
        A method to display the map view, creating a TextWindow if not already existing, and focusing on it if it does.
        Creates a map view using CTkTextview with the specified title and empty data, packing it with certain padding
        and expansion properties.
        """
        if self.mapview_window is None or not self.mapview_window.winfo_exists():
            self.mapview_window = TextWindow(
                master=self,
                window_position=self.map_window_position,
                title="Map View",
            )  # create window if its None or destroyed
        else:
            self.mapview_window.focus()  # if window exists focus it

        # Display the diagram.
        map_data = get_the_map()
        map_view = CTkTextview(master=self.mapview_window, title="Map View", the_data=map_data)
        map_view.pack(padx=10, pady=10, fill="both", expand=True)

    # Display Ai Analysis response in a separate top level window.
    def display_ai_response(self, error_msg: str) -> None:
        """
        Display AI response in a GUI window.

        Args:
            error_msg (str): The error message to display in the GUI.

        Returns:
            None
        """
        # create window if its None or destroyed
        if self.ai_analysis_window is None or not self.ai_analysis_window.winfo_exists():
            self.ai_analysis_window = TextWindow(
                master=self,
                window_position=self.ai_analysis_window_position,
                title="Analysis View",
            )
        else:
            self.ai_analysis_window.focus()  # if window exists focus it

        # Display the analysis in the toplevel window.
        analysis_view = CTkTextview(master=self.ai_analysis_window, title="Analysis View", the_data=error_msg)
        analysis_view.pack(padx=10, pady=10, fill="both", expand=True)
        analysis_view.after(10, self.ai_analysis_window.lift)  # Make window jump to the front

    # Set and display the file name.
    def display_and_set_file(self, filename: str) -> None:
        """
        Display the current file name in a button on the GUI and set it as the current file.

        Args:
            filename (str): The name of the current file.

        Returns:
            None: This function does not return anything.

        This function creates a label on the GUI that displays the current file name. The label is created using the `display_current_file` function and is placed in the second row and tenth column of the GUI. The label's text is set to "Current File: {filename}". The `display_message_box` function is called to display a message box indicating that the current file has been set to the specified filename. Finally, the `self.file` attribute is set to the name of the current file obtained from `PrimeItems.file_to_get.name`.

        Note:
            - The `display_current_file` function is assumed to be defined elsewhere in the codebase.
            - The `display_message_box` function is assumed to be defined elsewhere in the codebase.

        Example:
            ```python
            gui_instance.display_and_set_file("example.txt")
            ```
        """
        display_current_file(self, filename)
        if self.current_file_display_message:
            self.display_message_box(f"Current file set to {filename}", "Green")
        self.file = filename  # Set this so it is saved in settings.

    # Check to see if a new version of our code is available.
    # Add Update Version button if there is a new version.
    def check_new_version(self) -> None:
        """
        Check if the new version is available
        Args:
            self: The class instance
        Returns:
            None"""
        # If so, add a button to enable user to update.
        # TODO For testing only = True.  False for production
        test_button = False
        if is_new_version() or test_button:
            self.new_version = True
            # We have a new version.  Let user upgrade.
            self.upgrade_button = add_button(
                self,
                self,
                "",
                "#79ff94",
                "#6563ff",
                self.event_handlers.upgrade_event,
                1,
                "Upgrade to Latest Version",
                "1",
                6,
                2,
                (0, 170),
                (0, 10),
                "w",
            )
            #  Query ? button
            self.list_files_query_button = add_button(
                self,
                self,
                "#246FB6",
                "#79ff94",
                "#6563ff",
                # ("#0BF075", "#ffd941"),
                # "#1bc9ff",
                self.event_handlers.whatsnew_event,
                1,
                "What's New?",
                2,
                6,
                2,
                (0, 180),
                (80, 10),
                "",
            )
            self.message = self.message + "\n\nA new version of MapTasker is available."
        else:
            self.new_version = False

    # Display any meesaagaes we may currently have..
    def process_current_messages(self) -> None:
        """
        Process any messages we may currently have.
        Args:
            self: The class instance
        Returns:
            None
        """
        # See if we have any current messages to display.
        if self.message:
            self.display_message_box(self.message, "Green")
            self.message = ""

        if self.ai_prompt:
            prompt = self.ai_prompt
        else:
            prompt = AI_PROMPT
            self.ai_prompt = prompt

        # Now that we have loaded our settings, reconfigure the ai analyze button
        if ((self.ai_model in OPENAI_MODELS and self.ai_apikey) or self.ai_model) and (
            self.single_task_name or self.single_profile_name
        ):
            self.ai_analyze_button.configure(fg_color="#f55dff", text_color="#5554ff")

    # Set up the main window's geometry
    def set_main_window_geometry(self) -> None:
        """
        Set the main window geometry
        Args:
            self: The class instance
        Returns:
            None
        """
        # Set the window geometry.  Use saved coordinates if available.
        if self.window_position:
            self.geometry(self.window_position)
        else:
            # Get the screen size
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()

            # Overall window dimensions
            self.geometry(f"1129x988+{screen_width//4}+{screen_height//6}")


# Event handlers for Customtkinter widgets
class EventHandlers:
    """
    Initializes an instance of the EventHandlers class with the given parent.

    Args:
        parent (object): The parent object (self).

    Returns:
        None
    """

    def __init__(self, parent: object) -> None:
        """
        Initializes an instance of the EventHandlers class with the given parent.

        Args:
            parent (object): The parent object (self).

        Returns:
            None
        """
        self.parent = parent  # Save 'self' so widget event handlers can reference 'self'

    # Clear the message text box.
    def clear_messages_event(self) -> None:
        """
        Clears the message box
        Args:
            None
        Returns:
            None
        Processing Logic:
            - Destroys the message box
        """
        self = self.parent
        self.all_messages = {}
        self.textbox.destroy()
        self.create_new_textbox()

    # Process the 'Restore Settings' checkbox
    def restore_settings_event(self) -> None:
        """
        Resets settings to defaults and restores from saved settings file
        Args:
            self: The class instance
            first_time: bool - True if this is the first time the checkbox is clicked
        Returns:
            None: No value is returned
        Processing Logic:
            - Reset all values to defaults
            - Restore saved settings from file
            - Check for errors and display messages
            - Extract restored settings into class attributes
            - Empty message queue after restoring
        """
        self = self.parent
        self.set_defaults()  # Reset all values
        temp_args = self.color_lookup = {}
        # Restore all changes that have been saved
        temp_args, self.color_lookup = save_restore_args(temp_args, self.color_lookup, False)

        # Check for errors
        with contextlib.suppress(KeyError):
            if temp_args["msg"]:
                self.display_message_box(temp_args["msg"], "Red")
                temp_args["msg"] = ""
                return

        # If no colors restored, let user know.
        if not self.color_lookup:
            self.display_message_box("Colors set to defaults.", "Green")

        # Restore progargs values
        if temp_args or self.color_lookup:
            self.extract_settings(temp_args)
            self.restore = True

        # No arguments mean no settings.
        else:  # Empty?
            self.display_message_box("No settings file found.", "Orange")

    # Process the 'Backup' IP Address/port/file location
    def get_xml_from_android_event(self) -> None:
        # Set up default values
        """
        Gets Android details from user.
        Args:
            self: The class instance.
        Returns:
            None: No value is returned.
        Processing Logic:
        - Sets default backup file HTTP address and location if not provided
        - Creates an entry field to input backup details
        - Adds a label above the entry field
        - Inserts the default backup info into the entry field
        - Replaces the backup button to fetch input details on click
        """
        self = self.parent
        # First clear out any entries we may already have filled in.
        clear_android_buttons(self)
        # Everyhting is based off row 7 for better spacing control
        ###  TCP/IP Address ###
        android_ipaddr = (
            "192.168.0.210" if self.android_ipaddr == "" or self.android_ipaddr is None else self.android_ipaddr
        )
        self.ip_entry = self.ip_label = None
        self.ip_entry, self.ip_label = self.display_label_and_input(
            "1-TCP/IP Address:",
            android_ipaddr,
            7,
            110,
            35,
            70,
            self.ip_entry,
            self.ip_label,
            True,
        )

        ### Port Number ###
        android_port = "1821" if self.android_port == "" or self.android_port is None else self.android_port
        self.port_entry = self.port_label = None
        self.port_entry, self.port_label = self.display_label_and_input(
            "2-Port Number:",
            android_port,
            7,
            127,
            100,
            130,
            self.port_entry,
            self.port_label,
            True,
        )

        ###  File Location ###
        if self.android_file == "" or self.android_file is None:
            android_file = "/Tasker/configs/user/backup.xml".replace("/", PrimeItems.slash)
        else:
            android_file = self.android_file.replace("/", PrimeItems.slash)
        self.file_entry = self.file_label = None
        self.file_entry, self.file_label = self.display_label_and_input(
            "3-File Location:",
            android_file,
            7,  # Start row
            129,  # Indentation x
            160,  # Indentation y
            190,
            self.file_entry,
            self.file_label,
            True,
        )

        # Add 'List XML Files' button
        self.list_files_button = add_button(
            self,
            self,
            "#D62CFF",
            ("#0BF075", "#FFFFFF"),
            "#6563ff",
            self.event_handlers.list_files_event,
            2,
            "List XML Files",
            2,
            7,
            1,
            (5, 270),
            (190, 0),
            "ne",
        )

        # Add 'Cancel Entry' button
        add_cancel_button(self, row=7, delta_y=70)

        ## Add ..or.. label.
        self.label_or = add_label(
            self,
            self,
            ".or.",
            "",
            12,
            "normal",
            7,
            1,
            (250, 0),
            (195, 0),
            "s",
        )

        #  Query ? button
        self.list_files_query_button = add_button(
            self,
            self,
            "#246FB6",
            ("#0BF075", "#ffd941"),
            "#1bc9ff",
            self.event_handlers.listfile_query_event,
            1,
            "?",
            2,
            7,
            1,
            (0, 230),
            (190, 0),
            "ne",
        )
        self.list_files_query_button.configure(width=20)

        # Replace backup button.
        self.get_backup_button = self.display_backup_button(
            "Enter 1-3 and Click Here to Set XML Details",
            "#D62CFF",
            "#6563ff",
            self.event_handlers.fetch_backup_event,
        )
        self.get_backup_button.configure(anchor="center", width=600)

    # Fetch the backup ip and file details, and validate.
    # This function can be entered through two paths:
    # 1- User clicked on the 'Get Backup Settings' button
    # 2- User clicked on the 'List XML Files' button
    def fetch_backup_event(self) -> None:
        """Fetches backup/XML from Android event details from user input

        Args:
            self: The class instance
        Returns:
            None: No value is returned

        Processes user input:
        - Splits input into IP address, port and file location
        - Validates IP address format and checks reachability via ping
        - Validates port number format
        - Validates file location is provided
        - Sets backup IP and file location attributes if valid
        - Displays message with backup details
        """
        self = self.parent

        # Get the input entered by the user.
        android_ipaddr = self.ip_entry.get()
        android_port = self.port_entry.get()
        # Only get the file if we are not doing a file list.
        android_file = "" if self.list_files else self.file_entry.get()

        # Make sure something was entered into each field.
        error_msg = ""
        if android_ipaddr == "" or android_ipaddr is None:
            error_msg = "Please enter an IP address."
        if android_port == "" or android_port is None:
            error_msg = "Please enter a port number."
        if error_msg:
            self.display_message_box(error_msg, "Red")
            return

        # Validate each field entered and ping the Android device to make sure it is reachible.
        if not ping_android_device(
            self,
            android_ipaddr,
            android_port,
        ):
            return

        # Either validate the file provided or provide a filelist.  Return code = 2 if list is good.
        return_code, android_ipaddr, android_port, android_file = validate_or_filelist_xml(
            self,
            android_ipaddr,
            android_port,
            android_file,
        )

        # Drop here if bad file location or XML file not found.
        if return_code not in (0, 2):
            self.backup_error("File not found.  Return code: " + str(return_code))
            return

        # If we got a good return from getting the XML filelist, then return to process it.
        if return_code == 2:
            return

        # All is well.  Save the info, restore the button and get rid of the input fields.
        self.android_ipaddr = android_ipaddr
        self.android_port = android_port
        if not self.list_files:
            self.android_file = android_file
        clear_android_buttons(self)

        # Set our file to get
        filename_location = self.android_file.rfind(PrimeItems.slash) + 1
        PrimeItems.file_to_use = self.android_file[filename_location:]

        self.display_multiple_messages(
            [
                f"Android Get XML IP Address set to: {self.android_ipaddr}\n",
                f"Android Port Number set to: {self.android_port}\n",
                f"Android Get Location set to: {self.android_file}\n",
                "XML file acquired.\n",
            ],
            "Green",
        )

        # Display backup details as a label again.
        self.display_backup_details()

        # Update the Project/Profile/Task pulldown option menus and labels.
        update_tasker_object_menus(self, get_data=False)

    # Process the 'Display Help' button
    def help_event(self) -> None:
        """Displays help information in a message box.
        Args:
            self: The class instance.
        Returns:
            None: Does not return anything.
        - Constructs a message with help text information
        - Opens a new message box window
        - Displays the help message text in the message box"""
        self = self.parent
        self.new_message_box(HELP)
        self.clear_messages = True  # Flag to tell display_message_box to clear the message box

    # Process the 'Get Backup Help' button
    def backup_help_event(self) -> None:
        """Backs up help text and displays it in a message box
        Args:
            self: The class instance
        Returns:
            None: Does not return anything
        Processes:
            - Fetches the backup help text from a constant
            - Creates a new message box window
            - Displays the backup help text in the message box"""
        self = self.parent
        self.new_message_box("Fetch Backup Help\n\n" + BACKUP_HELP_TEXT)
        self.clear_messages = True  # Flag to tell display_message_box to clear the message box

    # Process the '?' List XML Files query button
    def listfile_query_event(self) -> None:
        """Function to display help text for the listfile_query_event method.
        Parameters:
            - self (object): The object that the method is being called on.
        Returns:
            - None: This method does not return anything.
        Processing Logic:
            - Displays help text for listfile_query_event method.
            - Uses new_message_box method.
            - Help text is stored in LISTFILES_HELP_TEXT variable."""
        self = self.parent
        self.new_message_box("List XML Files Help\n\n" + LISTFILES_HELP_TEXT)
        self.clear_messages = True  # Flag to tell display_message_box to clear the message box

    # Process the '?' Tree View query button
    def treeview_query_event(self) -> None:
        """Function to display help text for the listfile_query_event method.
        Parameters:
            - self (object): The object that the method is being called on.
        Returns:
            - None: This method does not return anything.
        Processing Logic:
            - Displays help text for treeview_query_event method.
            - Uses new_message_box method.
            - Help text is stored in LISTFILES_HELP_TEXT variable."""
        self = self.parent
        self.new_message_box("View Help\n\n" + VIEW_HELP_TEXT)
        self.clear_messages = True  # Flag to tell display_message_box to clear the message box

    # Cancel the entry of backup parameters
    def backup_cancel_event(self) -> None:
        """
        Closes the backup details window.
        Args:
            self: The class instance
        Returns:
            None
        """
        self = self.parent
        clear_android_buttons(self)
        self.fetched_backup_from_android = False
        self.android_file = ""
        self.android_ipaddr = ""
        self.android_port = ""
        self.display_message_box("'Get XML From Android' canceled.", "Orange")

    # List (Android) XML files event
    def list_files_event(self) -> None:
        """
        List (Android) XML files event.
        Args:
            self: The class instance
        Returns:
            None
        """
        self = self.parent
        self.list_files = True
        self.list_files_button.configure(text="List Files Selected")
        self.event_handlers.fetch_backup_event()

    # User has selected a specific XML file to get from Android device from pulldown menu.
    def file_selected_event(self, android_file: str) -> None:
        """User has selected a specific Android XML file from pulldown menu.
        Returns:
            - None: Adds android_file to file_list."""
        self = self.parent
        self.android_file = android_file
        clear_android_buttons(self)
        self.display_multiple_messages(
            [
                f"Get XML IP Address set to: {self.android_ipaddr}\n",
                f"Port Number set to: {self.android_port}\n",
                f"Get Location set to: {self.android_file}\n",
                "XML file acquired.\n",
            ],
            "Green",
        )
        self.file = ""  # Negate any local file.

        # Validate XML file.
        PrimeItems.program_arguments["gui"] = True
        return_code, error_message = validate_xml_file(self.android_ipaddr, self.android_port, android_file)

        # Not valid XML...
        if return_code > 0:
            self.display_message_box(error_message, "Red")  # Error out and exit
            self.android_file = ""
            return

        # Get rid of any data we currently have
        clear_tasker_data()

        # Display backup details as a labels again.
        self.display_backup_details()

        # Refresh the Projects/Profiles/Tasks pulldown menus and labels
        update_tasker_object_menus(self, get_data=False)

    # Process the 'Reset Settings' button
    def reset_settings_event(self) -> None:
        """
        Resets all class settings to default values.
        Args:
            self: The class instance.
        Returns:
            None
        """
        self = self.parent
        clear_android_buttons(self)
        self.android_ipaddr = ""
        self.android_port = ""
        self.android_file = ""
        self.sidebar_detail_option.set(DEFAULT_DISPLAY_DETAIL_LEVEL)  # display detail level
        self.indent_option.set("4")  # Indentation amount
        self.condition_checkbox.deselect()  # Conditions
        self.preferences_checkbox.deselect()  # Tasker Preferences
        self.pretty_checkbox.deselect()  # Pretty output
        self.taskernet_checkbox.deselect()  # TaskerNet
        self.appearance_mode_optionmenu.set("System")  # Appearance
        customtkinter.set_appearance_mode("System")  # Enforce appearance
        self.debug_checkbox.deselect()  # Debug
        self.display_message_box("Settings reset.", "Green")
        self.twisty_checkbox.deselect()  # Twisty
        self.directory_checkbox.deselect()  # directory
        self.bold_checkbox.deselect()  # bold
        self.italicize_checkbox.deselect()  # italicize
        self.highlight_checkbox.deselect()  # highlight
        self.underline_checkbox.deselect()  # underline
        self.runtime_checkbox.deselect()  # Display runtime
        self.outline_checkbox.deselect()  # Display outline
        self.everything_checkbox.deselect()  # Display everything
        self.event_handlers.font_event(self.default_font)  # Set the font to the default font
        if self.color_labels:  # is there any color text?
            for label in self.color_labels:
                label.configure(text="")
        self.set_defaults()  # Reset all defaults

        # Cleanup the inline data.
        clean_up_memory()

        # Setup a temporary PrimeItems since the clean_up_memory cleared it all out.
        PrimeItems.colors_to_use = set_color_mode(self.appearance_mode)
        PrimeItems.output_lines = LineOut()
        PrimeItems.program_arguments = initialize_runtime_arguments()
        PrimeItems.program_arguments["debug"] = self.debug

        # Reset/display our Ai settings.
        with contextlib.suppress(AttributeError):
            self.profile_optionmenu.set("None")
        with contextlib.suppress(AttributeError):
            self.task_optionmenu.set("None")
        self.ai_prompt = AI_PROMPT
        self.ai_model = ""

        # Update the Tasker selected object pulldown names and labels
        update_tasker_object_menus(self, get_data=False)

        # Reset Analyze button to non-pink
        display_analyze_button(self, 13, first_time=False)

        # Reset current file
        display_current_file(self, "None")

    # Process Debug Mode checkbox
    def debug_checkbox_event(self) -> None:
        """
        Handle debug checkbox event
        Args:
            self: The class instance
        Returns:
            None
        Processing Logic:
            - Get the state of the debug checkbox
            - If checked:
                - Check if backup.xml file exists
                - If exists, show success message
                - If missing, show error and uncheck box
            - If unchecked:
                - Show confirmation message
        """
        self = self.parent
        self.debug = self.debug_checkbox.get()
        if self.debug:
            if Path("backup.xml").is_file():
                self.display_message_box("Debug mode enabled.", "Green")
            else:
                self.display_message_box(
                    ("Debug mode requires Tasker XML file to be named: 'backup.xml', which is missing.  No change."),
                    "Red",
                )
                self.debug = False
        else:
            self.display_message_box("Debug mode disabled.", "Green")

    # User has requested that the colors be result to their defaults.
    def color_reset_event(self) -> None:
        """Resets the color mode for Tasker items.
        Parameters:
            self (object): The current instance of the class.
        Returns:
            None: This function does not return anything.
        Processing Logic:
            - Resets color mode for Tasker items.
            - Sets color mode to default.
            - Displays message box to confirm reset.
            - Destroys color change window."""
        self = self.parent
        PrimeItems.colors_to_use = set_color_mode(self.appearance_mode)
        self.color_lookup = {}
        self.display_message_box("Tasker items set back to their default colors.", "Green")
        with contextlib.suppress(Exception):
            self.color_change.destroy()

    # The Upgrade Version button has been pressed.
    def upgrade_event(self) -> None:
        """ "Runs an update and reruns the program."
        Parameters:
            - self (object): Instance of the class.
        Returns:
            - None: No return value.
        Processing Logic:
            - Calls the update function.
            - Reruns the program to pick up the update."""
        self = self.parent
        update()
        self.display_message_box("Program updated.  Restarting...", "Green")
        # Create the Change Log file to be read and displayed after a program update.
        create_changelog()

        # Reload the GUI by running a new process with the new program/version.
        reload_gui(self, sys.argv)
        ## ReRun via a new process, which will load and run the new program/version.
        ## Note: this will cause an OS error, 'python[35833:461355] Task policy set failed: 4 ((os/kern) invalid argument)'
        ## Note: this current process will not return after this call, but simply be killed.
        # print("The following error message can be ignored: 'Task policy set failed: 4 ((os/kern) invalid argument)'.")
        # os.execl(sys.executable, "python", *sys.argv)

    # The Upgrade Version button has been pressed.
    def report_issue_event(self) -> None:
        """Opens a web browser and directs the user to create a new issue on GitHub for the Map-Tasker project.
        Parameters:
            - self (object): The instance of the class calling the function.
        Returns:
            - None: This function does not return any values.
        Processing Logic:
            - Opens a web browser using the webbrowser module.
            - Uses the url variable to direct the user to the correct page on GitHub.
            - If the web browser is not supported, a message box is displayed.
            - If the web browser is supported, a message box is displayed with instructions for creating a new issue."""
        url = "//github.com/mctinker/Map-Tasker/issues"
        issue_text = (
            "Go to your browser and create a new issue or feature request, providing as much detail as possible."
        )
        self = self.parent
        try:
            webbrowser.open(f"https:{PrimeItems.slash*2}{url}", new=2)
        except webbrowser.Error:
            self.display_message_box("Error: Failed to open output in browser: your browser is not supported.", "Red")
            return
        self.display_message_box("Report an Issue or Request a Feature\n\n" + issue_text)

    # Process single name selection/event
    def process_name_event(
        self,
        my_name: str,
        name_entered: str,
    ) -> None:
        #  Clear any prior error message.
        """
        Processes name event from checkboxes.
        Args:
            my_name: Name of item to filter by
            name_entered: Name entered
        Returns:
            None
        Processing Logic:
            - Clear any prior error message
            - Deselect the other two checkboxes
            - Display prompt to enter name
            - Get name entered
            - Check if name is valid
            - If valid, deselect other buttons and set name
            - Notify user of filter
            - Deselect checkbox clicked
        """
        self = self.parent
        if name_entered in ["No projects found", "No profiles found", "No tasks found"]:
            self.display_message_box("Selection ignored.", "Orange")
            name_entered = "None"
        # Make sure it is a valid name and display message.
        if self.check_name(name_entered, my_name):
            # Name is valid... deselect other buttons and set the name
            self.single_project_name = self.single_profile_name = self.single_task_name = ""
            name_entered = "" if name_entered == "None" else name_entered
            # Get the name entered
            match my_name:
                case "Project":
                    self.single_project_name = name_entered
                    # Clear out all of the old data for this new Project.
                    # They will get repopulated by call to...
                    # (below) update_tasker_object_menus() > list_tasker_objects() > load_xml()
                    clear_tasker_data()

                case "Profile":
                    self.single_profile_name = name_entered

                case "Task":
                    self.single_task_name = name_entered

            # Let the user know...
            if name_entered:
                self.specific_name_msg = f"Display only {my_name} '{name_entered}'."

        else:
            self.single_name_msg = all_objects

        # Update the pulldown menus and text labels, and set the color for Analyze button
        update_tasker_object_menus(self, get_data=True)
        display_analyze_button(self, 13, first_time=False)

    # Process the Project Name entry
    def single_project_name_event(self, name_selected: str) -> None:
        """Generates a single project name event from button inputs
        Args:
            self: The class instance
            name_selected: The name selected
        Returns:
            None: No value is returned
        - Calls process_name_event() to generate the event"""
        self = self.parent
        name_selected = name_selected.replace("Project: ", "")
        self.event_handlers.process_name_event("Project", name_selected)

    # Process the Profile Name entry
    def single_profile_name_event(self, name_selected: str) -> None:
        """Generates a single profile name event from button inputs
        Args:
            self: The class instance
            name_selected: The name selected
        Returns:
            None: No value is returned
        - Calls process_name_event to generate the event"""
        self = self.parent
        name_selected = name_selected.replace("Profile: ", "")
        self.event_handlers.process_name_event("Profile", name_selected)

    # Process the Task Name entry
    def single_task_name_event(self, name_selected: str) -> None:
        """Processes a single task name event.
        Args:
            self: The class instance.
            name_selected: The name selected
        Returns:
            None: Does not return anything.
        - Calls process_name_event() to handle the full event"""
        self = self.parent
        name_selected = name_selected.replace("Task: ", "")
        self.event_handlers.process_name_event("Task", name_selected)

    # Process the screen mode: dark, light, system
    def change_appearance_mode_event(self, new_appearance_mode: str) -> None:
        """
        Change the appearance mode of the GUI
        Args:
            new_appearance_mode: The new appearance mode as a string
        Returns:
            None: Does not return anything
        - Set the global appearance mode to the new mode
        - Update the local appearance mode attribute to the new lowercased mode"""
        self = self.parent
        customtkinter.set_appearance_mode(new_appearance_mode)
        self.appearance_mode = new_appearance_mode.lower()
        self.appearance_mode_optionmenu.set(self.appearance_mode.capitalize())
        self.display_message_box("Appearance mode set to " + self.appearance_mode.capitalize(), "Green")

    # Process the screen mode: dark, light, system
    def font_event(self, font_selected: str) -> None:
        """
        Sets the font for the GUI
        Args:
            font_selected: The font name selected by the user
        Returns:
            None: No value is returned
        Processing Logic:
            - Sets the internal font attribute to the selected font
            - Destroys any existing font label to update it
            - Creates a new label displaying the selected font
            - Places the label in the GUI
            - Displays a message box confirming the font change
        """
        self = self.parent
        self.font = font_selected
        with contextlib.suppress(Exception):
            self.font_out_label.destroy()
        self.font_out_label = customtkinter.CTkLabel(
            master=self,
            text=f"Monospaced Font To Use: {font_selected}",
            anchor="sw",
            font=(font_selected, 14),
        )
        self.font_out_label.grid(row=6, column=1, padx=10, pady=10, sticky="sw")
        self.font_optionmenu.set(font_selected)
        self.display_message_box(f"Font To Use set to {font_selected}", "Green")

    # Process the Display Detail Level selection
    def detail_selected_event(self, display_detail: str) -> None:
        """
        Set display detail level and update UI
        Args:
            display_detail (str): The selected display detail level
        Returns:
            None
        Processing Logic:
            - Set the display detail level attribute to the selected value
            - Update the sidebar detail option dropdown to the selected value
            - Display an inform message with the selected detail level
            - Disable the twisty checkbox if detail level is less than 3 and display a message
        """
        self = self.parent
        self.display_detail_level = display_detail
        self.sidebar_detail_option.set(display_detail)
        self.inform_message("Display Detail Level", True, display_detail)
        # Disable twisty if detail level is less than 3
        if self.twisty and int(display_detail) < DISPLAY_DETAIL_LEVEL_all_parameters:
            self.display_message_box(
                f"Hiding Tasks with Twisty has no effect with Display Detail Level set to {display_detail}.  Twisty disabled!",
                "Red",
            )
            self.twisty = False
            self.twisty_checkbox.deselect()

    # Process the Identation Amount selection
    def indent_selected_event(self, ident_amount: str) -> None:
        """Indent selected text or code block
        Args:
            ident_amount: The amount of indentation to apply as a string
        Returns:
            None: No value is returned
        - Set the indent attribute to the passed ident_amount
        - Update the indent option dropdown to the selected amount
        - Display confirmation message of indentation amount"""
        self = self.parent
        self.indent = ident_amount
        self.indent_option.set(ident_amount)
        self.inform_message("Indentation Amount", True, ident_amount)

    # Process color selection
    def colors_event(self, color_selected_item: str) -> None:
        """
        Changes the color for a selected item
        Args:
            color_selected_item (str): The item whose color is to be changed
        Returns:
            None
        - Checks if the associated display flag for the selected item is True
        - Opens a color picker dialog to select a new color
        - Saves the new color for the selected item
        - Displays the new color for the selected item
        """
        self = self.parent
        warning_check = [
            "Profile Conditions",
            "Action Conditions",
            "TaskerNet Information",
            "Tasker Preferences",
        ]
        check_against = [
            self.conditions,
            self.conditions,
            self.taskernet,
            self.preferences,
        ]
        max_row = 14

        # Let's first make sure that if a color has been chosen for a display flag,
        # that the associated display flag is True (e.g. display this colored item)
        with contextlib.suppress(Exception):
            the_index = warning_check.index(color_selected_item)
            if not check_against[the_index]:
                the_output_message = color_selected_item.replace("Profile ", "")
                the_output_message = the_output_message.replace("Action ", "")
                self.display_message_box(
                    f"Display {the_output_message} is not set to display!  Turn on Display {color_selected_item} first.",
                    "Red",
                )
                return
        # Put up color picker and get the color
        pick_color = AskColor()  # Open the Color Picker
        pick_color.focus_set()  # Set focus to the color picker
        color = pick_color.get()  # Get the color
        if color is not None:
            self.display_message_box(f"{color_selected_item} color changed to {color}", color)

            # Okay, plug in the selected color for the selected named item
            self.event_handlers.extract_color_from_event(color, color_selected_item)

            # Destroy previous label and display the color as a label.
            with contextlib.suppress(Exception):
                self.color_change.destroy()
            self.color_change = customtkinter.CTkLabel(
                self.tabview.tab("Colors"),
                text=f"{color_selected_item} displays in this color.",
                text_color=color,
            )
            self.color_change.grid(row=self.color_row, column=0, padx=0, pady=0)
            self.color_row += 1
            if self.color_row > max_row:
                self.color_row = 4

        # Nothing selected
        else:
            self.display_message_box("No color selected.", "Orange")

        # Cleanup
        pick_color.destroy()
        pick_color.grab_release()
        del pick_color

    # Color selected...process it.
    def extract_color_from_event(self, color: str, color_selected_item: str) -> None:
        """Maps a color name to a selected item
        Args:
            color: str - The color name
            color_selected_item: str - The name of the selected item
        Returns:
            None - No return value
        Maps a color name to a selected item:
            - Looks up the color name in a dictionary of color types
            - Adds the color as a value to the color lookup dictionary using the looked up color type as the key
            - This associates the given color with the given selected item"""
        self = self.parent
        self.color_lookup[TYPES_OF_COLOR_NAMES[color_selected_item]] = (
            color  # Add color for the selected item to our dictionary
        )

    # Process the 'conditions' checkbox
    def condition_event(self) -> None:
        """
        Get input and put message for condition checkbox
        Args:
            self: The class instance
            condition_checkbox: Condition checkbox input
            message: Message to display
        Returns:
            None: No return value
        - Get input value from condition_checkbox
        - Display message to user
        - Store input value in self.conditions"""
        self = self.parent
        self.conditions = self.get_input_and_put_message(
            self.condition_checkbox,
            "Display Profile and Task Action Conditions",
        )

    # Process the 'Outline' checkbox
    def outline_event(self) -> None:
        """
        Display Configuration Outline
        Args:
            self: The class instance
        Returns:
            None: Does not return anything
        - Get the input value of the outline_checkbox attribute
        - Call the get_input_and_put_message method to get user input and display a message
        - Assign the return value to the outline attribute
        """
        self = self.parent
        self.outline = self.get_input_and_put_message(self.outline_checkbox, "Display Configuration Outline")

    # Process the 'Prettier' checkbox
    def pretty_event(self) -> None:
        """
        Display Configuration Outline
        Args:
            self: The class instance
        Returns:
            None: Does not return anything
        - Get the input value of the outline_checkbox attribute
        - Call the get_input_and_put_message method to get user input and display a message
        - Assign the return value to the outline attribute
        """
        self = self.parent
        self.pretty = self.get_input_and_put_message(self.pretty_checkbox, "Display Pretty Output")

    # Process the 'everything' checkbox
    def everything_event(self) -> None:
        # Dictionary of program arguments and function to run for each upon restoration.
        """
        Handles toggling all options in the Everything event
        Args:
            self: The class instance
        Returns:
            None: Does not return anything
        Processing Logic:
            - Defines a dictionary mapping option names to functions for toggling them
            - Gets the value of the everything checkbox
            - Loops through the dictionary toggling each option
            - Sets the attribute on self for each option to the everything value
            - Sets the display detail level to 4
            - Displays a message box with the results
        """
        self = self.parent
        message_map = {
            "conditions": lambda: self.select_deselect_checkbox(
                self.condition_checkbox,
                value,
                "Display Profile/Task Conditions",
            ),
            "directory": lambda: self.select_deselect_checkbox(self.directory_checkbox, value, "Display Directory"),
            "outline": lambda: self.select_deselect_checkbox(
                self.outline_checkbox,
                value,
                "Display Configuration Outline",
            ),
            "preferences": lambda: self.select_deselect_checkbox(
                self.preferences_checkbox,
                value,
                "Display Tasker Preferences",
            ),
            "pretty": lambda: self.select_deselect_checkbox(
                self.pretty_checkbox,
                value,
                "Display Prettier Output",
            ),
            "runtime": lambda: self.select_deselect_checkbox(self.runtime_checkbox, value, "Display Runtime Settings"),
            "taskernet": lambda: self.select_deselect_checkbox(
                self.taskernet_checkbox,
                value,
                "Display TaskerNet Information",
            ),
            # "twisty": lambda: self.select_deselect_checkbox(
            #    self.twisty_checkbox,
            #    value,
            #    "Hide Task Details Under Twisty",
            # ),
            "display_detail_level": lambda: self.event_handlers.detail_selected_event(DEFAULT_DISPLAY_DETAIL_LEVEL),
        }

        self.everything = self.everything_checkbox.get()
        value = self.everything

        # new_message = all_messages = ""
        for key in message_map:
            if message_func := message_map.get(key):
                # Handle toggle: select/deselect checkbox and set/unset setting.
                self.display_message_box(f"{message_func()}", "Green")

            # Check if key is an attribute on self before setting
            if hasattr(self, key) and key != "display_detail_level":
                setattr(self, key, value)

        # Handle Display Detail Level
        self.display_detail_level = DEFAULT_DISPLAY_DETAIL_LEVEL

    # Process the 'Tasker Preferences' checkbox
    def preferences_event(self) -> None:
        """
        Get user input on whether to display tasker preferences
        Args:
            self: The class instance
        Returns:
            None: Does not return anything
        - Get user input from preferences_checkbox checkbox
        - Store input in self.preferences
        - Display message based on input to confirm action"""
        self = self.parent
        self.preferences = self.get_input_and_put_message(self.preferences_checkbox, "Display Tasker Preferences")

    # Process the 'Twisty' checkbox
    def twisty_event(self) -> None:
        """
        Toggle display of task details under a twisty
        Args:
            self: The class instance
        Returns:
            None: No value is returned
        - Get the state of the twisty checkbox and put a message
        - If twisty is checked and display detail level is less than all_parameters, display a message box and set detail level to 3
        - No return value, function call has side effects on instance state
        """
        self = self.parent
        self.twisty = self.get_input_and_put_message(self.twisty_checkbox, "Hide Task Details Under Twisty")
        if self.twisty and int(self.display_detail_level) < DISPLAY_DETAIL_LEVEL_all_parameters:
            self.display_message_box(
                "This has no effect with Display Detail Level less than 3.  Display Detail Level set to 3!",
                "Red",
            )
            self.sidebar_detail_option.set("3")  # display detail level
            self.display_detail_level = "3"

        # Check to see if we are doing everything (they are mutually exclusive)
        if self.twisty and self.everything:
            self.display_message_box(
                "'Twisty' and 'Everything' are mutually exclusive.  Unchecking 'Twisty'.",
                "Orange",
            )
            self.twisty = False
            self.twisty_checkbox.deselect()

    # Process the 'Display Directory' checkbox
    def directory_event(self) -> None:
        """
        Get input and put message for directory checkbox
        Args:
            self: The class instance
            directory_checkbox: The directory checkbox
            "Display Directory": The message to display
        Returns:
            None: Does not return anything
        - Get input value from directory_checkbox
        - If checked, put message "Display Directory"
        - Does not return anything, just updates class attribute"""
        self = self.parent
        self.directory = self.get_input_and_put_message(self.directory_checkbox, "Display Directory")

    # Process the 'Bold Names' checkbox
    def names_bold_event(self) -> None:
        """
        Get input to display names in bold and put message
        Args:
            self: The class instance
        Returns:
            None: No value is returned
        - Get input value from bold_checkbox attribute
        - Put message "Display Names in Bold" based on input
        - No return value, function updates attribute on class instance"""
        self = self.parent
        self.bold = self.get_input_and_put_message(self.bold_checkbox, "Display Names in Bold")

    # Process the 'Highlight Names' checkbox
    def names_highlight_event(self) -> None:
        """
        Get input and put message for names highlight checkbox
        Args:
            self: The class instance
            highlight_checkbox: The checkbox input element
            "Display Names Highlighted": The message to display
        Returns:
            None: No value is returned
        - Get the value of the highlight_checkbox input
        - If checked, put the "Display Names Highlighted" message
        - If not checked, do not put any message
        """
        self = self.parent
        self.highlight = self.get_input_and_put_message(self.highlight_checkbox, "Display Names Highlighted")

    # Process the 'Italicize Names' checkbox
    def names_italicize_event(self) -> None:
        """
        Italicize names based on checkbox input
        Args:
            self: The class instance
        Returns:
            None: No value is returned
        - Get input value from italicize_checkbox checkbox
        - Put message based on input value to "Display Names Italicized" label
        - No return value, function updates UI state directly
        """
        self = self.parent
        self.italicize = self.get_input_and_put_message(self.italicize_checkbox, "Display Names Italicized")

    # Process the 'Underline Names' checkbox
    def names_underline_event(self) -> None:
        """
                Gets user input to display names underlined or not
                Args:
                    self: The class instance
                Returns:
                    None: No value is returned
                - Gets user input from the underline_checkbox checkbox
                - Passes the input value and a label to get_input_and_put_message()
        #Loading.
        """
        self = self.parent
        self.underline = self.get_input_and_put_message(self.underline_checkbox, "Display Names Underlined")

    # Process the 'Taskernet' checkbox
    def taskernet_event(self) -> None:
        """
        Display TaskerNet Information
        Args:
            self: The TaskerNet object
        Returns:
            None: Does not return anything
        - Check if TaskerNet checkbox is checked
        - Get user input for displaying TaskerNet information
        - Put message dialog to display TaskerNet information
        """
        self = self.parent
        self.taskernet = self.get_input_and_put_message(self.taskernet_checkbox, "Display TaskerNet Information")

    # Process the 'Runtime' checkbox
    def runtime_checkbox_event(self) -> None:
        """
        Get input and put message for runtime checkbox
        Args:
            self: The class instance
        Returns:
            None: No return value
        - Get value of runtime_checkbox input
        - If checked, put message "Display Runtime Settings"
        - No return value, function modifies instance attributes"""
        self = self.parent
        self.runtime = self.get_input_and_put_message(self.runtime_checkbox, "Display Runtime Settings")

    # Process the 'Save Settings' checkbox
    def save_settings_event(self) -> None:
        # Get program arguments from GUI and store in a temporary dictionary
        """
        Saves program settings from GUI to file.
        Args:
            self: The class instance.
        Returns:
            None
        - Get program arguments from GUI and store in a temporary dictionary
        - Save the arguments in the temporary dictionary to file
        - Display confirmation message box
        """
        self = self.parent
        temp_args = {value: getattr(self, value) for value in ARGUMENT_NAMES}

        # Save the arguments in the temporary dictionary
        temp_args, self.color_lookup = save_restore_args(temp_args, self.color_lookup, True)
        self.display_message_box("Settings saved.", "Green")

    # Display a treeview of the XML.
    def treeview_event(self) -> None:
        """Handles the event of clicking on the treeview.
        Parameters:
            - self (object): The object calling the function.
        Returns:
            - None: This function does not return anything.
        Processing Logic:
            - Checks if the XML file has already been retrieved.
            - If not, calls the get_xml function.
            - If there is an error reading the backup file, displays an error message.
            - If the file has been identified, attempts to open it.
            - If the file is not found, displays an error message.
            - Calls the build_the_tree function to build the tree.
            - Calls the display_tree function to display the tree."""
        self = self.parent
        PrimeItems.error_code = 0  # Clear any previous error.

        # Do we already have the XML?
        # If we don't have any data, get it.
        if self.load_xml():
            # Ok, we have our root Tasker elements.  Build the tree
            self.treeview_window = None

            # Build our tree from XML data
            tree_data = self.build_the_tree()

            # Display the tree
            self.display_tree(tree_data)
            self.display_message_box("Tree View displayed.", "Green")

    # Get XML button clicked.  Prompt usere for XML and load it.
    def getxml_event(self) -> None:
        """
        Get rid of any existing data, clear tasker root elements, and negate file indications.
        Set IP address, port, and file to empty strings.
        Prompt user for a new XML file and display the current file if successful.
        """
        self = self.parent
        # Get rid of any data we currently have
        PrimeItems.tasker_root_elements["all_projects"].clear()
        PrimeItems.tasker_root_elements["all_profiles"].clear()
        PrimeItems.tasker_root_elements["all_tasks"].clear()
        PrimeItems.tasker_root_elements["all_scenes"].clear()
        self.single_project_name = ""
        self.single_profile_name = ""
        self.single_task_name = ""
        self.specific_name_msg = ""
        # Negate any indication that we have a file
        PrimeItems.file_to_get = ""
        PrimeItems.program_arguments["file"] = ""
        self.android_ipaddr = ""
        self.android_port = ""
        self.android_file = ""

        # Redisplay the Projects/Profiles/Tasks pulldown menus for selection
        # It will call 'display_and_set_file' to display the current file name via call to 'load_xml'
        self.current_file_display_message = True
        update_tasker_object_menus(self, get_data=True)
        self.current_file_display_message = False
        # If debug is on, let the user know that we are using 'backup.xml'
        if self.debug:
            self.display_message_box("Using backup.xml since debug mode is on.", "Orange")

    # Show for edit the AI API Key
    def ai_apikey_event(self) -> None:
        """
        Prompts the user to enter their API key, or leaves it as is if it already exists.
        If the user enters a new API key, it is saved to a file.

        Parameters:
            None

        Returns:
            None
        """
        self = self.parent
        # Get our key, if it exists.
        self.ai_apikey = get_api_key()

        # Present user with input dialog for the key.
        dialog = customtkinter.CTkInputDialog(
            text=f"Enter your API Key (Cancel to leave as is):\nkey={self.ai_apikey}",
            title="API Key",
        )
        # Get the name entered
        new_key = dialog.get_input()

        # If user did not hit 'Cancel', then save the key
        if new_key is not None and new_key != "":
            # Write out the new key
            with open(KEYFILE, "w") as key_file:
                key_file.write(new_key)
                self.display_message_box(f"API key saved: '{new_key}' .", "Green")
                self.ai_apikey = new_key

            # Redisplay ai settings with new key.
            display_selected_object_labels(self)

        # Usaer hit 'Cancel' or didn't input anything
        else:
            self.display_message_box("No change to the API key!", "Orange")

    # Show for edit the AI API Key
    def ai_model_selected_event(self, model: str) -> None:
        """
        Set the AI model to the specified model.

        Parameters:
            model (str): The model to set.

        Returns:
            None
        """
        self = self.parent
        if model == "None":
            self.display_message_box("No model selected.", "Orange")
            self.ai_model = ""
            display_analyze_button(self, 13, first_time=False)
            return
        self.ai_model = model
        self.display_message_box("Model set to " + model + ".", "Green")

        # Redisplay the Analyze button.
        display_analyze_button(self, 13, first_time=False)

        # Redisplay the ai settings
        display_selected_object_labels(self)

    # Kickoff the AI analysis
    def ai_analyze_event(self) -> None:
        """
        Analyzes a single item identified by the current instance.

        This function checks if the instance has a single project name, profile name, or task name.
        If so, it sets the `ai_analyze` attribute to True, displays a message box indicating the analysis is running
        with the current model, and reruns the program.

        If no single item is identified, it displays a message box indicating that a single project, profile,
        or task has not been selected.

        Parameters:
            self (object): The current instance of the class.

        Returns:
            None
        """
        self = self.parent
        if self.ai_model is None or self.ai_model == "None" or self.ai_model == "":
            self.display_message_box("No model selected.", "Orange")
            return
        if self.single_profile_name == "None or unnamed!":
            self.single_profile_name = ""
        # Do we have a single item identified?
        if self.single_project_name or self.single_profile_name or self.single_task_name:
            self.ai_analyze = True
            self.event_handlers.clear_messages_event()  # Clear out all displayed messages.
            self.display_message_box(f"Running analysis with model {self.ai_model}.", "Green")
            if self.ai_analysis_window is not None:
                self.ai_analysis_window.destroy()  # Delete previous window before creating a new one.
            self.event_handlers.rerun_the_program_event()
        # Test if no XML data loaded
        elif (
            not PrimeItems.tasker_root_elements["all_projects"]
            and not PrimeItems.tasker_root_elements["all_profiles"]
            and not PrimeItems.tasker_root_elements["all_tasks"]
        ):
            self.display_message_box(
                "No projects, profiles, or tasks have been loaded!  Load some XML and try again.",
                "Orange",
            )
        # No single item has been selected.
        else:
            self.display_message_box(
                "Single Project/Profile/Task has not been selected!  Select only one and try again.",
                "Orange",
            )
            # Get the Profile or Task to analyze
            # self.ai_analyze_button.destroy()
            # If there are no Profiles or Tasks, redisplay the Analyze button
            if not list_tasker_objects(self):
                # Drop here if we don't have any XML loaded yet.
                display_analyze_button(self, 13, first_time=False)

            # Update the Project/Profile/Task pulldown option menus.
            set_tasker_object_names(self)

    # Process the '?' Ai query button
    def ai_help_event(self) -> None:
        """Function to display help text for the Analysis tab.
        Parameters:
            - self (object): The object that the method is being called on.
        Returns:
            - None: This method does not return anything.
        Processing Logic:
            - Displays help text for Analysis tab.
            - Uses new_message_box method.
            - Help text is stored in AI_HELP_TEXT variable."""
        self = self.parent
        self.new_message_box("Analyze Help\n\n" + AI_HELP_TEXT)
        self.clear_messages = True  # Flush messages after displaying this help info.

    # Handle Ai Prompt change event.
    def ai_prompt_event(self) -> None:
        """
        Handles the event when the AI prompt is changed.

        Opens a dialog box for the user to enter a new AI prompt. Displays the current prompt and prompts the user to
        enter a new prompt.

        If the user cancels the prompt change, a message box is displayed indicating that the prompt change was canceled.
        If the user enters the same prompt as the current prompt, a message box is displayed indicating that the prompt did not change.
        If the user enters a new prompt, the AI prompt is updated and a message box is displayed indicating the new prompt.

        Parameters:
            self (object): The instance of the class.

        Returns:
            None
        """
        self = self.parent
        dialog = customtkinter.CTkInputDialog(
            text=f"Current prompt: '{self.ai_prompt}'\n\nEnter a new prompt for the AI to use:",
            title="Change the Ai Prompt",
        )
        dialog.focus_set()  # Make sure it is selectable.
        # Get the name entered
        name_entered = dialog.get_input()
        # Canceled?
        if name_entered is None:
            self.display_message_box("Prompt change canceled.", "Orange")
        # The same?
        elif name_entered == self.ai_prompt:
            self.display_message_box("Prompt did not change.", "Orange")
        else:
            # Valid response.
            self.ai_prompt = name_entered
            self.display_message_box(f"Prompt changed to '{self.ai_prompt}'.", "Green")
            display_selected_object_labels(self)

    # Display what is in the changelog for the new release.
    def whatsnew_event(self) -> None:
        """
        Retrieves the latest changelog from the Map-Tasker GitHub repository and displays it in the user interface.

        This function sends a GET request to the specified URL to retrieve the changelog in JSON format. It then iterates through the changelog dictionary and displays each line in the user interface using the `display_message_box` method. The changelog is displayed starting from the latest version until the "Older History" section is reached. The function also clears any previously displayed messages before displaying the changelog.

        Parameters:
            self (object): The instance of the class.

        Returns:
            None
        """
        self = self.parent
        try:
            changelog = requests.get(CHANGELOG_JSON_URL).json()  # noqa: S113
        except (json.decoder.JSONDecodeError, ConnectionError, Exception):
            self.display_message_box("Failed to get changelog.", "Red")
            return
        self.event_handlers.clear_messages_event()  # Clear out all displayed messages.
        # Go through loaded dictionary and display each line
        for key, value in changelog.items():
            if "Older History" in value:  # Get out if we hit then of the the new version changes.
                break
            if key == "version":
                self.display_message_box(f"Changes in the new version {value}:", "Green")
                self.display_message_box("", "Green")
            elif "##" in value:
                # Add spaces as needed to make it more readible
                self.display_message_box("", "Green")
                self.display_message_box(f"{value}", "Green")
                self.display_message_box("", "Green")
            else:
                self.display_message_box(f"{value}", "Green")

        self.display_message_box("End of changelog.", "Green")

    # The 'Run' program button has been pressed.  Set the run flag and close the GUI
    def run_program_event(self) -> None:
        """
        Starts a program and displays a message box.
        Args:
            self: The class instance.
        Returns:
            None: Does not return anything.
        - Sets the go_program attribute to True to start the program
        - Displays a message box with the text "Program running..." and blocks user interaction
        - Calls the quit() method to exit the program"""
        self = self.parent
        self.go_program = True
        self.rerun = False

        # Validate the XML and cleanup
        self.cleanup_and_run(run_only=True)

    # The 'ReRun' program button has been pressed.  Set the run flag and close the GUI
    def rerun_the_program_event(self) -> None:
        """
        Resets the program state and exits.
        Args:
            self: The class instance.
        Returns:
            None: Does not return anything.
        - Sets the rerun flag to True to restart the program on next run
        - Calls withdraw() to reset the program state
        - Calls quit() twice to ensure program exits"""
        self = self.parent
        self.rerun = True
        self.cleanup_and_run(run_only=False)

    # The 'Exit' program button has been pressed.  Call it quits
    def exit_program_event(self) -> None:
        """
        Exits the program by setting exit flag and calling quit twice
        Args:
            self: The object instance
        Returns:
            None: Does not return anything
        - Sets the exit flag to True to indicate program exit
        - Calls quit() twice to ensure program exits cleanly
        - Calling quit() twice is done as a precaution in case one call fails to exit for some reason
        """
        self = self.parent
        # Get and store the position of the windows.
        store_windows(self)

        # Indicate that the user hit the 'Exit' button.
        self.exit = True

        # Save our last window position
        self.window_position = self.winfo_geometry()
        # Close it down
        self.quit()
        self.quit()

    # Diagram View event
    def diagram_event(self) -> None:
        """
        Event handler for the diagram event.

        This method is responsible for processing the diagram when the diagram event is triggered. It performs the following steps:
        1. It assigns the parent object to the current object.
        2. It checks if there is already a Project.
            - If there is a Project, it performs the following steps:
                - It calls the `outline_the_configuration` function to process the diagram and build the 'network'.
                - It clears the `PrimeItems.output_lines.output_lines` list.
                - It retrieves the directory from which the diagram file is being run.
                - It opens the diagram file in read mode using UTF-8 encoding.
                - It reads the contents of the file into a list called `diagram_data` by stripping the trailing newline characters.
                - It calls the `display_diagram` method of the current object, passing `diagram_data` as an argument.
            - If there is no Project, it displays a message box indicating that the diagram is not possible due to no Projects in the current XML file.
        3. If there is no XML file loaded, it displays a message box indicating that the diagram is not possible due to no XML file loaded.

        This method does not return any value.
        """
        self = self.parent
        # If we don't already have Project, then get some XML.
        if self.load_xml():
            if PrimeItems.tasker_root_elements["all_projects"] or PrimeItems.tasker_root_elements["all_profiles"]:
                # Process the diagram: builds the 'network' and then draws it in the GUI
                outline_the_configuration()
                PrimeItems.output_lines.output_lines.clear()
                # Process the diagram file
                diagram_dir = (
                    f"{os.getcwd()}{PrimeItems.slash}{DIAGRAM_FILE}"  # Get the directory from which we are running.
                )
                with open(str(diagram_dir), encoding="utf-8") as diagram_file:
                    diagram_data = [line.rstrip() for line in diagram_file]  # Read file into a list

                    # Display the diagram
                    self.display_diagram(diagram_data)
                    self.display_message_box("Diagram View displayed.", "Green")
            else:
                self.display_message_box(
                    "Diagram not possible.  No Projects or Profiles in the current XML file.",
                    "Orange",
                )
        else:
            # No XML to diagram.
            self.display_message_box("Diagram not possible.  No XML file loaded.", "Orange")

    def map_event(self) -> None:
        """
        Executes the map event.

        This function checks if the XML file is loaded. If it is, it checks if there are any projects, profiles, tasks,
        or scenes in the XML. If there are, it sets the `mapgui` attribute to `True` and executes the `mapit_all`
        function. If there are no projects, profiles, tasks, or scenes, it displays a message box indicating that the
        map is not possible. If the XML is not loaded, it displays a message box indicating that the map is not
        possible because there is no XML file loaded.

        Parameters:
            None

        Returns:
            None
        """
        self = self.parent
        # If we don't already have Project, then get some XML.
        if self.load_xml():
            if (
                PrimeItems.tasker_root_elements["all_projects"]
                or PrimeItems.tasker_root_elements["all_profiles"]
                or PrimeItems.tasker_root_elements["all_tasks"]
                or PrimeItems.tasker_root_elements["all_scenes"]
            ):

                # Save windows and delete previous mapview window.
                store_windows(self)

                # Get rid of previous map view.
                if self.mapview_window is not None:
                    self.mapview_window.destroy()

                # Turn off settings that don't work in a textbox
                save_directory = self.directory
                save_twisty = self.twisty
                save_outline = self.outline
                self.directory = False
                self.twisty = False
                self.outline = False

                # Save the settings
                temp_args = {value: getattr(self, value) for value in ARGUMENT_NAMES}
                _, _ = save_restore_args(temp_args, self.color_lookup, True)

                # Remove the current GUI
                # self.withdraw()

                # Now flag the fact that we are rerunning for the map view.
                # These flags are critical for the proper proceessing of the map.
                self.mapgui = True  # Set it for save_settings
                PrimeItems.program_arguments["mapgui"] = True  # Set it for mapit_all

                # Re-invoke ourselves to force the html to be written
                _ = mapit_all("")

                # Restore settings
                self.directory = save_directory
                self.twisty = save_twisty
                self.outline = save_outline

                # Now display the results
                self.display_map()
                self.display_message_box("Map View displayed.", "Green")

                # Reload the GUI by running a new process with the new program/version.
                # reload_gui(self, sys.argv[0], "-g", "-mapgui")
                # There is no return from the above call.
            else:
                self.display_message_box(
                    "Map not possible.  No Projects, Profiles, Tasks or Scenes in the current XML file.",
                    "Orange",
                )

        else:
            # No XML to diagram.
            self.display_message_box("Map not possible.  No XML file loaded.", "Orange")
