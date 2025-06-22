"""Code to manage the graphical user interface."""

#                                                                                      #
# userintr: provide GUI and process input for program arguments                        #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #

from __future__ import annotations  # noqa: I001

import contextlib
import json
import os
import pickle
import webbrowser
from pathlib import Path
from tkinter import *  # noqa: F403

from tkinter import TclError
from tkinter.ttk import *  # noqa: F403

from typing import TYPE_CHECKING

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
    add_button,
    add_cancel_button,
    add_label,
    build_profiles,
    check_for_changelog,
    clear_android_buttons,
    create_changelog,
    display_analyze_button,
    display_current_file,
    display_messages_from_last_run,
    display_no_xml_message,
    display_selected_object_labels,
    fresh_message_box,
    get_api_key,
    get_appropriate_color,
    get_xml,
    is_new_version,
    list_tasker_objects,
    make_hex_color,
    no_search_string,
    output_label,
    ping_android_device,
    reload_gui,
    remove_tags_from_bars_and_names,
    reset_primeitems_single_names,
    search_nextprev_string,
    search_substring_in_list,
    set_ai_key,
    set_tab_to_use,
    set_tasker_object_names,
    setup_name_error,
    update_tasker_object_menus,
    valid_item,
    validate_or_filelist_xml,
)
from maptasker.src.guiwins import (
    APIKeyDialog,
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
from maptasker.src.mapai import valid_api_key
from maptasker.src.mapit import clean_up_memory, mapit_all
from maptasker.src.maputils import (
    clear_tasker_data,
    close_logfile,
    is_color_dark,
    update,
    validate_xml_file,
)
from maptasker.src.primitem import PrimeItems, PrimeItemsReset
from maptasker.src.proginit import log_startup_values
from maptasker.src.sysconst import (
    ARGUMENT_NAMES,
    CHANGELOG_JSON_URL,
    DIAGRAM_FILE,
    KEYFILE,
    LLAMA_MODELS,
    OPENAI_MODELS,
    TAB_NAMES,
    TYPES_OF_COLOR_NAMES,
    DISPLAY_DETAIL_LEVEL_all_parameters,
    logger,
)
from maptasker.src.taskerd import get_the_xml_data
from maptasker.src.userhelp import (
    AI_HELP_TEXT,
    APIKEY_HELP_TEXT,
    BACKUP_HELP_TEXT,
    HELP,
    LISTFILES_HELP_TEXT,
    PPP_HELP_TEXT,
    SEARCH_HELP_TEXT,
    VIEW_HELP_TEXT,
    VIEWLIMIT_HELP_TEXT,
)

if TYPE_CHECKING:
    from collections.abc import Callable

# Color Modes: "System" (standard), "Dark", "Light"
customtkinter.set_appearance_mode("System")
# Themes: "blue" (standard), "green", "dark-blue"
customtkinter.set_default_color_theme("blue")


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
        logger.info("Starting GUI")
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

        # If debug set as runtime option, then set it in the GUI aswell.
        if PrimeItems.program_arguments["debug"]:
            self.reset_debug_at_end = not self.debug
            self.debug = True
            self.debug_checkbox.select()

        # Set the window's geometry
        self.set_main_window_geometry()

        # See if we have any carryover error messages from last run (rerun).
        # Note: this must go after the settings restoration.
        display_messages_from_last_run(self)

        # If we are getting XML from Android device, display the details.
        if self.android_ipaddr:
            # Display backup details as a label
            self.display_backup_details()

        # Check if newer version of our code is available on Pypi.
        self.check_new_version()

        # See if we have a changelog, and get it if we do.  This must go before 'self.process_current_messages()' call.
        check_for_changelog(self)

        # See if we have any current messages to display.
        self.process_current_messages()

        # Finally, show the window. It was hidden in initialize_screen.
        self.deiconify()
        # The following line is equivalent to a call to update_tasker_object_menus but only when the Analysis tab is clicked.
        self.tabview.configure(
            "Analyze",
            command=update_tasker_object_menus(
                self,
                get_data=True,
                reset_single_names=False,
            ),
        )

        # Update the analysis button
        logger.info("Updating analysis button")
        display_analyze_button(self, 13, first_time=True)

        # Update the Project/Profile/Task pulldown option menus.
        set_tasker_object_names(self)
        logger.info("Updating pulldown menus")
        update_tasker_object_menus(self, get_data=False, reset_single_names=False)

        # We are done with the initialization.
        logger.info("Initialization complete")
        self.display_message_box("Initialization complete.\n", "Green")

        # Set the focus to the last used tab.
        logger.info("Set tab")
        set_tab_to_use(self)

        # Turn off first time
        self.first_time = True
        # Save ourself
        PrimeItems.mygui = self

        # CHG ME: For Development Only!
        # The following lines are for testing only.
        # self.event_handlers.diagram_event()
        # self.event_handlers.map_event()
        # self.event_handlers.ai_apikey_event()

    # Establish all the default values used
    def set_defaults(self) -> None:
        # Item names must be the same as their value in
        #  PrimeItems.program_arguments
        """
                Sets default values for attributes.
        the api key        Args:
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
        logger.info("Setting defaults")
        self.sidebar_detail_option.configure(values=["0", "1", "2", "3", "4", "5"])
        self.sidebar_detail_option.set(str(DEFAULT_DISPLAY_DETAIL_LEVEL))
        self.display_detail_level = DEFAULT_DISPLAY_DETAIL_LEVEL
        self.conditions = self.preferences = self.taskernet = self.debug = (
            self.everything
        ) = self.clear_settings = self.reset = self.restore = self.exit = self.bold = (
            self.highlight
        ) = self.italicize = self.underline = self.go_program = self.outline = (
            self.rerun
        ) = self.list_files = self.runtime = self.save = self.twisty = (
            self.directory
        ) = self.pretty = self.fetched_backup_from_android = False
        self.single_project_name = ""
        self.single_profile_name = ""
        self.single_task_name = ""
        self.file = ""
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
        self.list_unnamed_items = False
        # Setup default window position = current position or first-time position
        if self.first_time:
            if PrimeItems.program_arguments["window_position"]:
                self.window_position = PrimeItems.program_arguments["window_position"]
            else:
                self.window_position = "1129x987+698+145"  # Default window position
        else:
            self.window_position = save_window_position(self)

        # Display current Items setting.
        with contextlib.suppress(
            AttributeError,
        ):  # single_name_status may not be defined yet.
            self.single_name_status(all_objects, "#3f99ff")

    # Display the Backup button
    def display_backup_button(
        self,
        the_text: str,
        color1: str,
        color2: str,
        routine: Callable,
    ) -> None:
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
        self.textbox.tag_config(
            line_num_str,
            foreground=self.all_messages[line_num]["color"],
        )

        # If current message is a setting ("set On/Off/True/False"), then color it
        if self.check_message_for_special_highlighting(message, line_num_str):
            ...

        # self.textbox.focus_set()
        # Set the font
        self.textbox.configure(font=(self.font, 14))

    # Check the current messsage for additional highlighting
    def check_message_for_special_highlighting(
        self,
        message: str,
        line_num_str: str,
    ) -> None:
        """
        Checks if the message is a setting and highlights it if so.

        Args:
            message (str): The message to check.
            line_num_str (str): The line number of the message.

        Returns:
            bool: True if we highlighted the text, false if we didn't.
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
            self.highlight_string(
                message,
                line_num_str,
                final_position,
                highlight_color,
            )
            return True
        return False

    # Highlight a string in the textbox.
    def highlight_string(
        self,
        message: str,
        line_num_str: str,
        highlight_position: int,
        highlight_color: str,
    ) -> None:
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
            error_message = setup_name_error(
                "Project",
                "Profile",
                self.single_project_name,
                self.single_profile_name,
            )
        elif self.single_project_name and self.single_task_name:
            error_message = setup_name_error(
                "Project",
                "Task",
                self.single_project_name,
                self.single_task_name,
            )
        elif self.single_profile_name and self.single_task_name:
            error_message = setup_name_error(
                "Profile",
                "Task",
                self.single_profile_name,
                self.single_task_name,
            )

        # Make sure the named item exists
        elif not valid_item(
            self,
            the_name,
            element_name,
            self.debug,
            self.appearance_mode,
        ):
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
            self.display_message_box(
                "'None' selected.  Displaying all Projects, Profiles and Tasks.",
                "Green",
            )
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
        # Load file for def get_xml
        if self.file:
            PrimeItems.file_to_get = self.file

        ## Let uer know what is happening
        # self.display_message_box(f"Verifing {my_name}...", "Green")

        # Validate the name by using the existing XML or reading it in.
        # We will prompt user for XML file if it hasn't already been loaded.
        name_entered = name_entered.strip()
        if name_entered and self.check_name(name_entered, my_name):
            self.single_project_name = self.single_profile_name = (
                self.single_task_name
            ) = ""

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
        self.textbox.configure(
            font=(self.font, 14),
            wrap="word",
            scrollbar_button_color="#6563ff",
        )
        self.hyperlink = CTkHyperlinkManager(
            self.textbox,
            text_color=get_appropriate_color(self, "blue"),
        )

    # ################################################################################
    # Select or deselect a checkbox based on the value passed in
    # ################################################################################
    def get_input_and_put_message(self, checkbox: customtkinter, title: str) -> bool:
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
        # Get rid of old messages
        fresh_message_box(self)

        # Insert the text.
        self.textbox.insert("0.0", message)

        # Check for hyperlink
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
                    self.textbox.delete(
                        f"{num + 1}.{hyper}",
                        f"{num + 1}.{end_hyper + 1}",
                    )
                    # Add the link
                    self.textbox.insert(
                        f"{num + 1}.{end_hyper + 2}",
                        link,
                        self.hyperlink.add(link),
                    )

        # Display some colored text: the heading
        self.textbox.tag_add(
            "color",
            "1.0",
            f"1.{len(message)}",
        )  # '1.5' means first line, 5th character; '1.11' means first line, 11th character
        self.textbox.tag_config("color", foreground="green")

    # ################################################################################
    # Inform user of toggle selection
    # ################################################################################
    def inform_message(
        self,
        toggle_name: str,
        toggle_value: str,
        number_value: str,
    ) -> None:
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
        checkbox: customtkinter,
        checked: bool,
        argument_name: str,
        display: bool,
    ) -> str:
        """Select or deselect a checkbox widget
        Args:
            checkbox: The checkbox widget to select or deselect
            checked: Whether to select or deselect the checkbox
            argument_name: The name of the argument being checked/unchecked
            display: True if we are to display the message, false if not.
        Returns:
            status: A string indicating if the checkbox was selected or deselected
        - Check if checked is True, call checkbox.select() to select it
        - Check if checked is False, call checkbox.deselect() to deselect it
        - Return a string with the argument name and checked status"""
        checkbox.select() if checked else checkbox.deselect()
        if display:
            onoff = "On" if checked else "Off"
            self.display_message_box(f"{argument_name} set {onoff}.", "Green")
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
            "ai_apikey_window_position",
            "ai_popup_window_position",
            "color_window_position",
            "diagram_window_position",
            "map_window_position",
            "progressbar_window_position",
            "tree_window_position",
            "guiview",
            "fetched_backup_from_android",
        }
        # Define what to do for each argument restored.
        message_map = {
            "android_ipaddr": lambda: f"Android Get XML TCP IP Address set to {value}\n",
            "android_port": lambda: f"Android Get XML Port Number set to {value}\n",
            "android_file": lambda: f"Android Get XML File Location set to {value}\n",
            "appearance_mode": lambda: self.event_handlers.change_appearance_mode_event(
                value,
            ),
            "bold": lambda: self.select_deselect_checkbox(
                self.bold_checkbox,
                value,
                "Display Names in Bold",
                display=False,
            ),
            "conditions": lambda: self.select_deselect_checkbox(
                self.conditions_checkbox,
                value,
                "Display Profile/Task Conditions",
                display=False,
            ),
            "debug": lambda: self.select_deselect_checkbox(
                self.debug_checkbox,
                value,
                "Debug Mode",
                display=False,
            ),
            "directory": lambda: self.select_deselect_checkbox(
                self.directory_checkbox,
                value,
                "Display Directory",
                display=False,
            ),
            "display_detail_level": lambda: self.event_handlers.detail_selected_event(
                value,
            ),
            "file": lambda: self.display_and_set_file(value),
            "font": lambda: self.event_handlers.font_event(value),
            # "font": lambda: f"Font set to {value}.\n",
            "highlight": lambda: self.select_deselect_checkbox(
                self.highlight_checkbox,
                value,
                "Display Names Highlighted",
                display=False,
            ),
            "indent": lambda: self.event_handlers.indent_selected_event(value),
            "italicize": lambda: self.select_deselect_checkbox(
                self.italicize_checkbox,
                value,
                "Display Names Italicized",
                display=False,
            ),
            "list_unnamed_items": lambda: self.select_deselect_checkbox(
                self.list_unnamed_items_checkbox,
                value,
                "Display Unnamed Tasks",
                display=False,
            ),
            "view_limit": lambda: self.event_handlers.viewlimit_event(value),
            "outline": lambda: self.select_deselect_checkbox(
                self.outline_checkbox,
                value,
                "Display Configuration Outline",
                display=False,
            ),
            "preferences": lambda: self.select_deselect_checkbox(
                self.preferences_checkbox,
                value,
                "Display Tasker Preferences",
                display=False,
            ),
            "pretty": lambda: self.select_deselect_checkbox(
                self.pretty_checkbox,
                value,
                "Display Prettier",
                display=False,
            ),
            "runtime": lambda: self.select_deselect_checkbox(
                self.runtime_checkbox,
                value,
                "Display Runtime Settings",
                display=False,
            ),
            "single_profile_name": lambda: self.process_single_name_restore(
                "Profile",
                value,
            ),
            "single_project_name": lambda: self.process_single_name_restore(
                "Project",
                value,
            ),
            "single_task_name": lambda: self.process_single_name_restore("Task", value),
            "task_action_warning_limit": lambda: self.tasklimit_set(value),
            "taskernet": lambda: self.select_deselect_checkbox(
                self.taskernet_checkbox,
                value,
                "Display TaskerNet Information",
                display=False,
            ),
            "twisty": lambda: self.select_deselect_checkbox(
                self.twisty_checkbox,
                value,
                "Hide Task Details Under Twisty",
                display=False,
            ),
            "underline": lambda: self.select_deselect_checkbox(
                self.underline_checkbox,
                value,
                "Display Names Underlined",
                display=False,
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
                message = (
                    message_func()
                )  # This calls the lambda function and takes a bit of time.
            # Catch bug where we have a key but no lambda function to process it.
            elif self.debug:
                logger.debug(
                    f"userintr: no lambda rtn for key or value: {key}, {value}",
                )

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

    def extract_colors(self) -> None:
        """
        Extracts and displays the color settings from the color_lookup dictionary.
        Reverses the TYPES_OF_COLOR_NAMES dictionary to map color names to their corresponding keys.
        Displays each color setting using the display_message_box method, handling cases where the background color is set.
        Ensures all colors are accounted for, setting any missing colors to turquoise.
        """
        # @profile
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
                        self.display_message_box(
                            f"{inv_color_names[key]} color set to {text_out}\n",
                            color,
                        )

        # Make sure we have all of our colors.  If any are missing then just make them turquoise.
        if self.color_lookup:
            for key, color in TYPES_OF_COLOR_NAMES.items():
                if color not in self.color_lookup:
                    self.color_lookup[color] = "turquoise"
                    self.display_message_box(
                        f"{key} color missing.  It has been set to turquoise.\n",
                        "turquoise",
                    )

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
        # Indicate that an extraction is in progress so we don't inadvertently change the colors already set via the 'appearance_mode' setting.
        self.extract_in_progress = True
        for key, value in temp_args.items():
            if key is not None:
                setattr(self, key, value)
                if new_message := self.restore_display(key, value):
                    self.display_message_box(f"{new_message}\n", "Green")

        # Set the tab to use to the default.
        if self.tab_to_use is None:
            self.tab_to_use = TAB_NAMES[0]

        # We have read colors and runtime args from backup file.  Now extract them for use.
        self.extract_colors()

        # Display completion
        self.display_message_box("Settings restored.\n", "Green")
        self.extract_in_progress = False

    def tasklimit_set(self, limit: str) -> str:
        """Set the limit for the number of Task actions before issuing a warning.

        Args:
            limit (str): The limit to set for the number of Task actions before issuing a warning.

        Returns:
            None: Does not return anything
        """
        self.task_action_warning_limit = limit
        self.display_message_box(
            f"Task Action Warning Limit set to {limit}.\n",
            "Green",
        )
        self.task_action_label.configure(text=f"Task Action Limit: {limit}")
        self.task_action_limit.set(limit)

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
        logger.info("Displaying backup details...")
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
                display_current_file(self, "None")
            else:
                self.display_message_box(
                    "Click 'Get Local XML' to try a different XML file.",
                    "Red",
                )
                display_current_file(self, "None")
            return False

        # Good return from getting the XML
        if PrimeItems.file_to_get.name:
            self.display_and_set_file(PrimeItems.file_to_get.name)
            self.android_file = self.android_ipaddr = self.android_port = ""
            clear_android_buttons(self)
            self.display_message_box(
                "'Get XML From Android' settings cleared.",
                "Green",
            )
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
        ) or self.android_ipaddr:
            if self.android_ipaddr == "" or self.android_file == "":
                if not self.prompt_and_get_file(self.debug, self.appearance_mode):
                    return False

            # We have a file identified.  We now have to read it in.
            else:
                filename_location = self.android_file.rfind(PrimeItems.slash) + 1
                file_to_use = PrimeItems.program_arguments["android_file"][
                    filename_location:
                ]
                if not file_to_use:
                    file_to_use = self.android_file[filename_location:]
                try:
                    PrimeItems.file_to_get = open(file_to_use)
                except FileNotFoundError:
                    # self.display_message_box(
                    #     f"XML file {file_to_use} not found.",
                    #     "Red",
                    # )
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
                if profile_ids := get_ids(
                    True,
                    projects[project]["xml"],
                    project_name,
                    [],
                ):
                    # Build our list of Profiles in this Project.
                    profile_list = build_profiles(root, profile_ids, project)

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
                tree_data.append(
                    {"name": f"Project: {project_name}", "children": profile_list},
                )

        # Return our data tree
        return tree_data

    def display_view(self, view_type: str, data: list | dict | None = None) -> object:
        """
        Displays a window with the given view type and data.

        Parameters:
            view_type (str): The type of view to display ("map", "diagram", or "tree").
            data (list or dict, optional): List of data to be displayed in the view. Defaults to None.

        Returns:
            View (object): Thwindow view.

        Processing Logic:
            - Creates a new window if one does not exist.
            - Focuses on the window if it already exists.
            - Displays the given data in the specified view format.
            - Packs the view in the window with specified padding and filling.
        """
        window_attribute = f"{view_type}view_window"
        window_position_attribute = f"{view_type}_window_position"
        window_title = f"{view_type.capitalize()} View"

        if (
            getattr(self, window_attribute) is None
            or not getattr(self, window_attribute).winfo_exists()
        ):
            setattr(
                self,
                window_attribute,
                TextWindow(
                    master=self,
                    window_position=getattr(self, window_position_attribute),
                    title=window_title,
                ),
            )  # create window if its None or destroyed
        else:
            getattr(self, window_attribute).focus()  # if window exists focus it

        # Map view
        if view_type == "map":
            map_data = get_the_map()
            # Check if too much data to display
            map_length = len(map_data)
            if map_length > self.view_limit:
                self.display_message_box(
                    f"Too much data to display (Size={map_length}, View Limit={self.view_limit}).  Select a larger 'View Limit' or a single Project / Profile / Task and try again.",
                    "Orange",
                )
                if self.mapview_window is not None:
                    self.mapview_window.destroy()
                return None

            # Define the view.
            view = CTkTextview(
                master=getattr(self, window_attribute),
                title=window_title,
                the_data=map_data,
            )

        # Setup diagram view.
        elif view_type == "diagram":
            # Display the data.
            if data:
                view = CTkTextview(
                    master=getattr(self, window_attribute),
                    title=window_title,
                    the_data=data,
                )
            else:
                self.display_message_box("No Project(s) Found in XML!", "Red")
                return None
        elif view_type == "tree":
            if data:
                view = CTkTreeview(master=getattr(self, window_attribute), items=data)
            else:
                self.display_message_box("No Project(s) Found in XML!", "Red")
                return None
        else:
            self.display_message_box()(
                "Invalid view type specified. Use 'map', 'diagram', or 'tree'.",
                "Red",
            )

        view.pack(padx=10, pady=10, fill="none", expand=True)
        return view

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
        if (
            self.ai_analysis_window is None
            or not self.ai_analysis_window.winfo_exists()
        ):
            self.ai_analysis_window = TextWindow(
                master=self,
                window_position=self.ai_analysis_window_position,
                title="Analysis View",
            )
        else:
            self.ai_analysis_window.focus()  # if window exists focus it

        # Display the analysis in the toplevel window.
        analysisview = CTkTextview(
            master=self.ai_analysis_window,
            title="Analysis View",
            the_data=error_msg,
        )
        analysisview.pack(padx=10, pady=10, fill="both", expand=True)
        analysisview.after(
            10,
            self.ai_analysis_window.lift,
        )  # Make window jump to the front
        analysisview.focus()

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
        logger.info("Checking for new version...")
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
            self.whats_new_button = add_button(
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

    # Display any messages we may currently have..
    def process_current_messages(self) -> None:
        """
        Process any messages we may currently have.
        Args:
            self: The class instance
        Returns:
            None
        """
        logger.info("Processing current messages...")
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
        logger.info("Setting main window geometry")
        # Set the window geometry.  Use saved coordinates if available.
        if self.window_position:
            self.geometry(self.window_position)
        else:
            # Get the screen size
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()

            # Overall window dimensions: width x height + x offset + y offset
            self.geometry(f"1129x1188+{screen_width // 4}+{screen_height // 6}")

    # Re-invoke mapit.

    def remapit(self, clear_names: bool = True) -> None:
        """
        Re-invoke the 'mapit' function.

        Parameters:
            clear_names (bool): Indicates whether to clear names.

        Returns:
            None
        """
        # Save windows and delete previous mapview window.
        store_windows(self)

        # Get rid of previous map view.
        if self.mapview_window is not None:
            self.mapview_window.destroy()

        # Turn off settings that don't work in a textbox
        save_twisty = self.twisty
        save_outline = self.outline
        self.twisty = False
        self.outline = False

        # Make sure we have all of our colors.  If any are missing then just make them turquoise.
        for color in TYPES_OF_COLOR_NAMES.values():
            if color not in self.color_lookup:
                self.color_lookup[color] = "turquoise"

        # Save the settings
        # temp_args = {value: getattr(self, value) for value in ARGUMENT_NAMES}
        temp_args = {}
        for value in ARGUMENT_NAMES:
            try:
                temp_args[value] = getattr(self, value)
            except AttributeError:
                temp_args[value] = ""

        temp_args["ai_analyze"] = (
            False  # Turn this off in event it was on from settings file.
        )
        _, _ = save_restore_args(temp_args, self.color_lookup, True)

        # force a reset of PrimeItems in mapit.py: initialize_everything.
        PrimeItemsReset()

        # Now flag the fact that we are rerunning for the map view.
        # These flags are critical for the proper proceessing of the map.
        self.guiview = True  # Set it for save_settings
        PrimeItems.program_arguments["guiview"] = True  # Set it for mapit_all
        PrimeItems.colors_to_use = (
            self.color_lookup
        )  # Make sure we have a color to use for mapit_all.

        # Initialize a few things first
        if clear_names:
            reset_primeitems_single_names()
        fresh_message_box(self)

        self.display_message_box(
            "The 'Map' view is running in the background.  Please stand by...",
            "LimeGreen",
        )

        # Launch the main MapTasker to display all or single item.
        _ = mapit_all("")

        # Restore settings
        self.twisty = save_twisty
        self.outline = save_outline

        # Check for error and display it and exit if necessary.
        if PrimeItems.error_code > 0:
            self.display_message_box(
                f"Map View not displayed.  {PrimeItems.error_msg}",
                "Orange",
            )
            PrimeItems.error_code = 0
            PrimeItems.error_msg = ""
            reset_primeitems_single_names()
            return

        # Now display the results.
        self.mapview = self.display_view("map")
        self.textview = self.mapview
        if self.mapview is not None:
            self.display_message_box("Map View displayed.", "Green")


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
        self.parent = (
            parent  # Save 'self' so widget event handlers can reference 'self'
        )

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
        the_view = self.parent
        the_view.all_messages = {}
        the_view.textbox.destroy()
        the_view.create_new_textbox()

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
        the_view = self.parent
        the_view.set_defaults()  # Reset all values
        temp_args = {}
        the_view.color_lookup = {}
        # Restore all changes that have been saved
        temp_args, the_view.color_lookup = save_restore_args(
            temp_args,
            the_view.color_lookup,
            False,
        )

        # Check for errors
        with contextlib.suppress(KeyError):
            if temp_args["msg"]:
                the_view.display_message_box(temp_args["msg"], "Red")
                temp_args["msg"] = ""
                self.color_reset_event()
                return

        # If no colors restored, let user know.
        if not the_view.color_lookup:
            the_view.display_message_box("Colors set to defaults.", "Green")

        # Restore progargs values
        if temp_args or the_view.color_lookup:
            the_view.extract_settings(temp_args)
            the_view.restore = True

        # No arguments mean no settings.
        else:  # Empty?
            the_view.display_message_box("No settings file found.", "Orange")

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
        the_view = self.parent
        # First clear out any entries we may already have filled in.
        clear_android_buttons(the_view)
        # Everyhting is based off row 7 for better spacing control
        ###  TCP/IP Address ###
        android_ipaddr = (
            "192.168.0.210"
            if the_view.android_ipaddr == "" or the_view.android_ipaddr is None
            else the_view.android_ipaddr
        )
        the_view.ip_entry = the_view.ip_label = None
        the_view.ip_entry, the_view.ip_label = the_view.display_label_and_input(
            "1-TCP/IP Address:",
            android_ipaddr,
            7,
            110,
            35,
            70,
            the_view.ip_entry,
            the_view.ip_label,
            True,
        )

        ### Port Number ###
        android_port = (
            "1821"
            if the_view.android_port == "" or the_view.android_port is None
            else the_view.android_port
        )
        the_view.port_entry = the_view.port_label = None
        the_view.port_entry, the_view.port_label = the_view.display_label_and_input(
            "2-Port Number:",
            android_port,
            7,
            127,
            100,
            130,
            the_view.port_entry,
            the_view.port_label,
            True,
        )

        ###  File Location ###
        if the_view.android_file == "" or the_view.android_file is None:
            android_file = "/Tasker/configs/user/backup.xml".replace(
                "/",
                PrimeItems.slash,
            )
        else:
            android_file = the_view.android_file.replace("/", PrimeItems.slash)
        the_view.file_entry = the_view.file_label = None
        the_view.file_entry, the_view.file_label = the_view.display_label_and_input(
            "3-File Location:",
            android_file,
            7,  # Start row
            129,  # Indentation x
            160,  # Indentation y
            190,
            the_view.file_entry,
            the_view.file_label,
            True,
        )

        # Add 'List XML Files' button
        the_view.list_files_button = add_button(
            the_view,
            the_view,
            "#D62CFF",
            ("#0BF075", "#FFFFFF"),
            "#6563ff",
            the_view.event_handlers.list_files_event,
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
        add_cancel_button(the_view, row=7, delta_y=70)

        ## Add ..or.. label.
        the_view.label_or = add_label(
            the_view,
            the_view,
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
        the_view.list_files_query_button = add_button(
            the_view,
            the_view,
            "#246FB6",
            ("#0BF075", "#ffd941"),
            "#1bc9ff",
            lambda: the_view.event_handlers.query_event("listfile"),
            1,
            "?",
            2,
            7,
            1,
            (0, 230),
            (190, 0),
            "ne",
        )
        the_view.list_files_query_button.configure(width=20)

        # Replace backup button.
        the_view.get_backup_button = the_view.display_backup_button(
            "Enter 1-3 and Click Here to Set XML Details",
            "#D62CFF",
            "#6563ff",
            the_view.event_handlers.fetch_backup_event,
        )
        the_view.get_backup_button.configure(anchor="center", width=600)

    def fetch_backup_event(self) -> None:
        """
        Fetches backup/XML details from user input and processes them.

        - Validates IP address, port, and file location.
        - Pings the Android device to check reachability.
        - Validates or fetches XML filelist.
        - Updates the UI and internal state based on the fetched details.
        """
        the_view = self.parent

        # Extract user input.
        android_ipaddr = the_view.ip_entry.get()
        android_port = the_view.port_entry.get()
        android_file = "" if the_view.list_files else the_view.file_entry.get()

        # Validate input fields.
        error_msg = self._validate_input(android_ipaddr, android_port)
        if error_msg:
            the_view.display_message_box(error_msg, "Red")
            return

        # Validate reachability and fetch file/XML list.
        if not ping_android_device(the_view, android_ipaddr, android_port):
            return

        return_code, android_ipaddr, android_port, android_file = (
            validate_or_filelist_xml(
                the_view,
                android_ipaddr,
                android_port,
                android_file,
            )
        )

        # Handle invalid file location or file not found.
        if return_code not in (0, 2):
            the_view.backup_error(f"File not found. Return code: {return_code}")
            return

        # Handle successful filelist fetch.
        if return_code == 2:
            return

        # All validations passed; update the internal state.
        self._update_internal_state(android_ipaddr, android_port, android_file)

        # Display backup details and update UI.
        self._display_backup_summary()

    def _validate_input(self: object, ip: str, port: str) -> str:
        """
        Validates the IP address and port number input by the user.

        Args:
            ip (str): The IP address input by the user.
            port (str): The port number input by the user.

        Returns:
            str: An error message if validation fails; empty string if valid.
        """
        if not ip:
            return "Please enter an IP address."
        if not port:
            return "Please enter a port number."
        return ""

    def _update_internal_state(self: object, ip: str, port: str, file: str) -> None:
        """
        Updates the internal state of the view with the validated details.

        Args:
            ip (str): The validated IP address.
            port (str): The validated port number.
            file (str): The validated file location.
        """
        the_view = self.parent
        the_view.android_ipaddr = ip
        the_view.android_port = port
        if not the_view.list_files:
            the_view.android_file = file
        clear_android_buttons(the_view)

        # Set the file to use
        PrimeItems.file_to_use = the_view.android_file.split(PrimeItems.slash)[-1]

    def _display_backup_summary(self) -> None:
        """
        Displays a summary of the backup details and updates the UI accordingly.
        """
        the_view = self.parent
        the_view.display_multiple_messages(
            [
                f"Android Get XML IP Address set to: {the_view.android_ipaddr}\n",
                f"Android Port Number set to: {the_view.android_port}\n",
                f"Android Get Location set to: {the_view.android_file}\n",
                "XML file acquired.\n",
            ],
            "Green",
        )
        the_view.display_backup_details()
        update_tasker_object_menus(the_view, get_data=True, reset_single_names=True)

    # Cancel the entry of backup parameters
    def backup_cancel_event(self) -> None:
        """
        Closes the backup details window.
        Args:
            self: The class instance
        Returns:
            None
        """
        the_view = self.parent
        clear_android_buttons(the_view)
        the_view.fetched_backup_from_android = False
        the_view.android_file = ""
        the_view.android_ipaddr = ""
        the_view.android_port = ""
        the_view.display_message_box("'Get XML From Android' canceled.", "Orange")

    # List (Android) XML files event
    def list_files_event(self) -> None:
        """
        List (Android) XML files event.
        Args:
            self: The class instance
        Returns:
            None
        """
        the_view = self.parent
        the_view.list_files = True
        the_view.list_files_button.configure(text="List Files Selected")
        the_view.event_handlers.fetch_backup_event()

    # User has selected a specific XML file to get from Android device from pulldown menu.
    def file_selected_event(self, android_file: str) -> None:
        """User has selected a specific Android XML file from pulldown menu.
        Returns:
            - None: Adds android_file to file_list."""
        the_view = self.parent
        the_view.android_file = android_file
        clear_android_buttons(the_view)
        the_view.display_multiple_messages(
            [
                f"Get XML IP Address set to: {the_view.android_ipaddr}\n",
                f"Port Number set to: {the_view.android_port}\n",
                f"Get Location set to: {the_view.android_file}\n",
                "XML file acquired.\n",
            ],
            "Green",
        )
        the_view.file = ""  # Negate any local file.

        # Validate XML file.
        PrimeItems.program_arguments["gui"] = True
        return_code, error_message = validate_xml_file(
            the_view.android_ipaddr,
            the_view.android_port,
            android_file,
        )

        # Not valid XML...
        if return_code > 0:
            the_view.display_message_box(error_message, "Red")  # Error out and exit
            the_view.android_file = ""
            return

        # Get rid of any data we currently have
        clear_tasker_data()

        # Display backup details as a labels again.
        the_view.display_backup_details()

        # Refresh the Projects/Profiles/Tasks pulldown menus and labels
        update_tasker_object_menus(the_view, get_data=True, reset_single_names=True)

    # Process the 'Reset Settings' button
    def reset_settings_event(self) -> None:
        """
        Resets all class settings to default values.
        Args:
            self: The class instance.
        Returns:
            None
        """
        the_view = self.parent

        # Clear Android-specific settings
        clear_android_buttons(the_view)
        the_view.android_ipaddr = the_view.android_port = the_view.android_file = ""

        # Reset option menus and checkboxes
        default_settings = {
            the_view.sidebar_detail_option: DEFAULT_DISPLAY_DETAIL_LEVEL,
            the_view.indent_option: "4",
            the_view.appearance_mode_optionmenu: "System",
            the_view.viewlimit_optionmenu: "10000",
        }

        for option, value in default_settings.items():
            option.set(value)

        checkboxes_to_deselect = [
            the_view.conditions_checkbox,
            the_view.preferences_checkbox,
            the_view.pretty_checkbox,
            the_view.taskernet_checkbox,
            the_view.debug_checkbox,
            the_view.twisty_checkbox,
            the_view.directory_checkbox,
            the_view.bold_checkbox,
            the_view.italicize_checkbox,
            the_view.highlight_checkbox,
            the_view.underline_checkbox,
            the_view.runtime_checkbox,
            the_view.outline_checkbox,
            the_view.everything_checkbox,
            the_view.list_unnamed_items_checkbox,
        ]

        # Go through list and uncheck all checkboxes.
        for checkbox in checkboxes_to_deselect:
            checkbox.deselect()

        # Reset font and appearance
        customtkinter.set_appearance_mode("System")
        the_view.event_handlers.font_event(the_view.default_font)

        # Clear color labels
        if the_view.color_labels:
            for label in the_view.color_labels:
                label.configure(text="")

        # Reset default settings and cleanup
        the_view.set_defaults()
        clean_up_memory()

        # Reinitialize PrimeItems
        PrimeItems.colors_to_use = set_color_mode(the_view.appearance_mode)
        PrimeItems.output_lines = LineOut()
        PrimeItems.program_arguments = initialize_runtime_arguments()
        PrimeItems.program_arguments["debug"] = the_view.debug

        # Reset AI settings
        the_view.ai_prompt = AI_PROMPT
        the_view.ai_model = ""

        # Reset Tasker-related option menus
        tasker_optionmenus = []
        with contextlib.suppress(AttributeError):
            tasker_optionmenus = [
                the_view.project_optionmenu,
                the_view.profile_optionmenu,
                the_view.task_optionmenu,
            ]
        for menu in tasker_optionmenus:
            with contextlib.suppress(AttributeError):
                menu.set("None")

        # Display current file as "None"
        display_current_file(the_view, "None")

        # Display reset message
        the_view.display_message_box("Settings reset.", "Green")

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
            - If checked and backup.xml file exists, show success message
            - If unchecked, show confirmation message
        """
        the_view = self.parent
        the_view.debug = the_view.debug_checkbox.get()
        if the_view.debug:
            # Make sure we're logging freom now on.
            log_startup_values()
            if not Path("backup.xml").is_file():
                the_view.debug = False
                the_view.display_message_box(
                    (
                        "Debug mode requires Tasker XML file to be named: 'backup.xml', which is missing.  Debug mode disabled."
                    ),
                    "Red",
                )
            the_view.display_message_box("Debug mode enabled.", "Green")
        else:
            the_view.display_message_box("Debug mode disabled.", "Green")
            logger.info("Debug mode disabled. Logfile being closed")
            close_logfile()

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
        the_view = self.parent
        PrimeItems.colors_to_use = set_color_mode(the_view.appearance_mode)
        the_view.color_lookup = {}
        the_view.display_message_box(
            "Tasker items set back to their default colors.",
            "Green",
        )
        with contextlib.suppress(Exception):
            the_view.color_change.destroy()

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
        the_view = self.parent
        update()
        the_view.display_message_box("Program updated.  Restarting...", "Green")
        # Create the Change Log file to be read and displayed after a program update.
        create_changelog()

        # Reload the GUI by running a new process with the new program/version.
        reload_gui(the_view)

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
        issue_text = "Go to your browser and create a new issue or feature request, providing as much detail as possible."
        the_view = self.parent
        try:
            webbrowser.open(f"https:{PrimeItems.slash * 2}{url}", new=2)
        except webbrowser.Error:
            the_view.display_message_box(
                "Error: Failed to open output in browser: your browser is not supported.",
                "Red",
            )
            return
        the_view.display_message_box(
            "Report an Issue or Request a Feature\n\n" + issue_text,
        )

    # Process single name selection/event
    def process_name_event(
        self,
        my_name: str,
        name_entered: str,
    ) -> None:
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
        the_view = self.parent

        if name_entered in ["No projects found", "No profiles found", "No tasks found"]:
            the_view.display_message_box("Selection ignored.", "Orange")
            name_entered = "None"
        else:
            if the_view.check_name(name_entered, my_name):
                # First set the names all to 'empty
                the_view.single_project_name = ""
                the_view.single_profile_name = ""
                the_view.single_task_name = ""
                # Save the name in mygui signle_xxx_name
                name_entered = "" if name_entered == "None" else name_entered
                setattr(the_view, f"single_{my_name.lower()}_name", name_entered)
                if name_entered:
                    the_view.specific_name_msg = (
                        f"Display only {my_name} '{name_entered}'."
                    )
                else:
                    the_view.specific_name_msg = f"Display all {my_name}."
            else:
                the_view.single_name_msg = all_objects
            # Set the names in the pulldown menus and update the pulldown menus.
            set_tasker_object_names(the_view)
            update_tasker_object_menus(
                the_view,
                get_data=False,
                reset_single_names=False,
            )
            display_analyze_button(the_view, 13, first_time=False)

    def process_single_name_event(self, event_type: str, name_selected: str) -> None:
        """Processes a name event for the given event type.
        Args:
            self: The class instance.
            event_type: The type of the event (e.g., "Project", "Profile", "Task").
            name_selected: The name selected.
        Returns:
            None: Does not return anything.
        - Calls process_name_event() to handle the event.
        """
        the_view = self.parent
        name_selected = name_selected.replace(f"{event_type}: ", "")
        the_view.event_handlers.process_name_event(event_type, name_selected)

    def single_project_name_event(self, name_selected: str) -> None:
        """Generates a single project name event."""
        self.process_single_name_event("Project", name_selected)

    def single_profile_name_event(self, name_selected: str) -> None:
        """Generates a single profile name event."""
        self.process_single_name_event("Profile", name_selected)

    def single_task_name_event(self, name_selected: str) -> None:
        """Generates a single task name event."""
        self.process_single_name_event("Task", name_selected)

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

        the_view = self.parent
        customtkinter.set_appearance_mode(new_appearance_mode)
        the_view.appearance_mode = new_appearance_mode.lower()
        the_view.appearance_mode_optionmenu.set(the_view.appearance_mode.capitalize())
        if not the_view.extract_in_progress:
            the_view.color_lookup = set_color_mode(the_view.appearance_mode)
        the_view.display_message_box(
            "Appearance mode set to " + the_view.appearance_mode.capitalize(),
            "Green",
        )

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
        the_view = self.parent
        the_view.font = font_selected
        with contextlib.suppress(Exception):
            the_view.font_out_label.destroy()
        the_view.font_out_label = customtkinter.CTkLabel(
            master=the_view,
            text=f"Monospaced Font To Use: {font_selected}",
            anchor="sw",
            font=(font_selected, 14),
        )
        the_view.font_out_label.grid(row=6, column=1, padx=10, pady=10, sticky="sw")
        the_view.font_optionmenu.set(font_selected)
        the_view.display_message_box(f"Font To Use set to {font_selected}", "Green")

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
        the_view = self.parent
        the_view.display_detail_level = display_detail
        the_view.sidebar_detail_option.set(display_detail)
        the_view.inform_message("Display Detail Level", True, display_detail)
        # Disable twisty if detail level is less than 3
        if (
            the_view.twisty
            and int(display_detail) < DISPLAY_DETAIL_LEVEL_all_parameters
        ):
            the_view.display_message_box(
                f"Hiding Tasks with Twisty has no effect with Display Detail Level set to {display_detail}.  Twisty disabled!",
                "Red",
            )
            the_view.twisty = False
            the_view.twisty_checkbox.deselect()

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
        the_view = self.parent
        the_view.indent = int(ident_amount)
        the_view.indent_option.set(ident_amount)
        the_view.inform_message("Indentation Amount", True, ident_amount)

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
        the_view = self.parent
        warning_check = [
            "Profile Conditions",
            "Action Conditions",
            "TaskerNet Information",
            "Tasker Preferences",
        ]
        check_against = [
            the_view.conditions,
            the_view.conditions,
            the_view.taskernet,
            the_view.preferences,
        ]
        max_row = 14

        # Let's first make sure that if a color has been chosen for a display flag,
        # that the associated display flag is True (e.g. display this colored item)
        with contextlib.suppress(Exception):
            the_index = warning_check.index(color_selected_item)
            if not check_against[the_index]:
                the_output_message = color_selected_item.replace("Profile ", "")
                the_output_message = the_output_message.replace("Action ", "")
                the_view.display_message_box(
                    f"Display {the_output_message} is not set to display!  Turn on Display {color_selected_item} first.",
                    "Red",
                )
                return
        # Put up color picker and get the color
        pick_color = AskColor()  # Open the Color Picker
        pick_color.focus_set()  # Set focus to the color picker
        color = pick_color.get()  # Get the color
        if color is not None:
            the_view.display_message_box(
                f"{color_selected_item} color changed to {color}",
                color,
            )

            # Okay, plug in the selected color for the selected named item
            the_view.event_handlers.extract_color_from_event(color, color_selected_item)

            # Destroy previous label and display the color as a label.
            with contextlib.suppress(Exception):
                the_view.color_change.destroy()
            the_view.color_change = customtkinter.CTkLabel(
                the_view.tabview.tab("Colors"),
                text=f"{color_selected_item} displays in this color.",
                text_color=color,
            )
            the_view.color_change.grid(row=the_view.color_row, column=0, padx=0, pady=0)
            the_view.color_row += 1
            if the_view.color_row > max_row:
                the_view.color_row = 4

        # Nothing selected
        else:
            the_view.display_message_box("No color selected.", "Orange")

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
        the_view = self.parent
        the_view.color_lookup[TYPES_OF_COLOR_NAMES[color_selected_item]] = (
            color  # Add color for the selected item to our dictionary
        )
        PrimeItems.colors_to_use[TYPES_OF_COLOR_NAMES[color_selected_item]] = (
            color  # Add color for the selected item to our dictionary
        )

    # Process the 'conditions' checkbox
    def condition_event(self) -> None:
        """
        Get input and put message for condition checkbox
        Args:
            self: The class instance
            conditions_checkbox: Condition checkbox input
            message: Message to display
        Returns:
            None: No return value
        - Get input value from conditions_checkbox
        - Display message to user
        - Store input value in self.conditions"""
        the_view = self.parent
        the_view.conditions = the_view.get_input_and_put_message(
            the_view.conditions_checkbox,
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
        the_view = self.parent
        the_view.outline = the_view.get_input_and_put_message(
            the_view.outline_checkbox,
            "Display Configuration Outline",
        )

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
        the_view = self.parent
        the_view.pretty = the_view.get_input_and_put_message(
            the_view.pretty_checkbox,
            "Display Pretty Output",
        )

    # Process the 'everything' checkbox
    def everything_event(self) -> None:
        """
        Handles toggling all options in the 'Everything' event.
        Args:
            self: The class instance.
        Returns:
            None: Does not return anything.
        """
        the_view = self.parent
        value = the_view.everything_checkbox.get()
        the_view.everything = value

        # Dictionary of checkbox attributes and corresponding display messages
        checkbox_map = {
            "conditions_checkbox": "Display Profile/Task Conditions",
            "directory_checkbox": "Display Directory",
            "outline_checkbox": "Display Configuration Outline",
            "preferences_checkbox": "Display Tasker Preferences",
            "pretty_checkbox": "Display Prettier Output",
            "runtime_checkbox": "Display Runtime Settings",
            "taskernet_checkbox": "Display TaskerNet Information",
            "list_unnamed_items_checkbox": "Display Unnamed Tasks",
        }

        # Toggle each checkbox and set attributes
        for attr_name, display_message in checkbox_map.items():
            checkbox = getattr(the_view, attr_name, None)
            if checkbox:
                the_view.select_deselect_checkbox(
                    checkbox,
                    value,
                    display_message,
                    display=True,
                )
                setattr(the_view, attr_name.replace("_checkbox", ""), value)

        # Handle Display Detail Level separately
        the_view.event_handlers.detail_selected_event(DEFAULT_DISPLAY_DETAIL_LEVEL)
        the_view.display_detail_level = DEFAULT_DISPLAY_DETAIL_LEVEL

        # Optionally display results in a message box (only if needed)
        evereything = "on" if value else "off"
        the_view.display_message_box(
            f"Everything toggled {evereything} successfully",
            "Green",
        )

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
        the_view = self.parent
        the_view.preferences = the_view.get_input_and_put_message(
            the_view.preferences_checkbox,
            "Display Tasker Preferences",
        )

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
        the_view = self.parent
        the_view.twisty = the_view.get_input_and_put_message(
            the_view.twisty_checkbox,
            "Hide Task Details Under Twisty",
        )
        if (
            the_view.twisty
            and int(the_view.display_detail_level) < DISPLAY_DETAIL_LEVEL_all_parameters
        ):
            the_view.display_message_box(
                "This has no effect with Display Detail Level less than 3.  Display Detail Level set to 3!",
                "Red",
            )
            the_view.sidebar_detail_option.set("3")  # display detail level
            the_view.display_detail_level = "3"

        # Check to see if we are doing everything (they are mutually exclusive)
        if the_view.twisty and the_view.everything:
            the_view.display_message_box(
                "'Twisty' and 'Everything' are mutually exclusive.  Unchecking 'Twisty'.",
                "Orange",
            )
            the_view.twisty = False
            the_view.twisty_checkbox.deselect()

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
        the_view = self.parent
        the_view.directory = the_view.get_input_and_put_message(
            the_view.directory_checkbox,
            "Display Directory",
        )

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
        the_view = self.parent
        the_view.bold = the_view.get_input_and_put_message(
            the_view.bold_checkbox,
            "Display Names in Bold",
        )

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
        the_view = self.parent
        the_view.highlight = the_view.get_input_and_put_message(
            the_view.highlight_checkbox,
            "Display Names Highlighted",
        )

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
        the_view = self.parent
        the_view.italicize = the_view.get_input_and_put_message(
            the_view.italicize_checkbox,
            "Display Names Italicized",
        )

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
        the_view = self.parent
        the_view.underline = the_view.get_input_and_put_message(
            the_view.underline_checkbox,
            "Display Names Underlined",
        )

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
        the_view = self.parent
        the_view.taskernet = the_view.get_input_and_put_message(
            the_view.taskernet_checkbox,
            "Display TaskerNet Information",
        )

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
        the_view = self.parent
        the_view.runtime = the_view.get_input_and_put_message(
            the_view.runtime_checkbox,
            "Display Runtime Settings",
        )

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
        the_view = self.parent
        temp_args = {value: getattr(the_view, value) for value in ARGUMENT_NAMES}

        # Save the arguments in the temporary dictionary
        temp_args, the_view.color_lookup = save_restore_args(
            temp_args,
            the_view.color_lookup,
            True,
        )
        the_view.display_message_box("Settings saved.", "Green")

    # List unnamed Items checkbox event
    def list_unnamed_items_event(self) -> None:
        """
        Handles the event of listing unnamed tasks.
        Args:
            self: The class instance.
        Returns:
            None
        """
        the_view = self.parent
        the_view.list_unnamed_items = the_view.list_unnamed_items_checkbox.get()
        selected = "selected" if the_view.list_unnamed_items else "deselected"
        # Update the pull-down menus and display message
        list_tasker_objects(the_view)
        the_view.display_message_box(
            f"'List Unnamed Items' checkbox {selected}.",
            "Green",
        )

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
        the_view = self.parent
        PrimeItems.error_code = 0  # Clear any previous error.

        # Do we already have the XML?
        # If we don't have any data, get it.
        if PrimeItems.tasker_root_elements["all_projects"]:
            # Ok, we have our root Tasker elements.  Build the tree
            if the_view.treeview_window is not None:
                the_view.treeview_window.destroy()

            # Build our tree from XML data
            tree_data = the_view.build_the_tree()

            # Display the tree
            the_view.treeview = the_view.display_view("tree", tree_data)
            the_view.display_message_box("Tree View displayed.", "Green")
        else:
            display_no_xml_message(the_view)
            the_view.display_message_box(
                "XML must have at least one Project.",
                "Orange",
            )

    # Get XML button clicked.  Prompt usere for XML and load it.
    def getxml_event(self) -> None:
        """
        Get rid of any existing data, clear tasker root elements, and negate file indications.
        Set IP address, port, and file to empty strings.
        Prompt user for a new XML file and display the current file if successful.
        """
        the_view = self.parent
        # Get rid of any data we currently have
        clear_tasker_data()
        the_view.single_project_name = ""
        the_view.single_profile_name = ""
        the_view.single_task_name = ""
        the_view.specific_name_msg = ""
        # Negate any indication that we have a file
        PrimeItems.file_to_get = ""
        PrimeItems.program_arguments["file"] = ""
        the_view.android_ipaddr = ""
        the_view.android_port = ""
        the_view.android_file = ""
        program_args = PrimeItems.program_arguments
        program_args["android_file"] = ""
        program_args["android_ipaddr"] = ""
        program_args["android_port"] = ""

        # Redisplay the Projects/Profiles/Tasks pulldown menus for selection
        # It will call 'display_and_set_file' to display the current file name via call to 'load_xml'
        the_view.current_file_display_message = True
        update_tasker_object_menus(the_view, get_data=True, reset_single_names=True)
        the_view.current_file_display_message = False

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
        the_view = self.parent
        # Get our key, if it exists.
        the_view.ai_apikey = get_api_key()

        # Issue the dialog box for the API key.
        api_key = APIKeyDialog()
        # Save the window
        api_key.master.ai_apikey_window = api_key

    def ai_apikey_process_event(
        self,
        apikey_window: customtkinter,
        cancel: bool,
        clear: str,
    ) -> None:
        """
        Process the AI API Dialog key event.

        Args:
            apikey_window (customtkinter): The API key dialog window.
            cancel (bool): Indicates if the operation was canceled.
            clear (str): "openai_key", "claude_key", etc.

        Returns:
            None
        """
        apikeys_to_validate = ["openai_key", "claude_key"]
        # self points to the 'event_handlers'; apikey_window is the dialog box window (APIKeyDialog).
        my_gui = self.parent
        # Bail out if user hit 'Cancel' button.
        if cancel:
            my_gui.display_message_box(
                "'Cancel' button selected.  No change to the API keys!",
                "Orange",
            )
            # Save the window position and delete the window.  Then return.
            my_gui.ai_apikey_window_position = save_window_position(apikey_window)
            apikey_window.destroy()
            return

        # Get the API keys and update PrimeItems if necessary: key and length of key.
        api_keys = {
            "openai_key": apikey_window.openai_key.get(),
            "claude_key": apikey_window.claude_key.get(),
            "deepseek_key": apikey_window.deepseek_key.get(),
            "gemini_key": apikey_window.gemini_key.get(),
        }
        apikey_changed = False
        # Go through the API key entries.
        for key, value in api_keys.items():
            # See if 'Clear' button was selected.  Blank it out if it was.
            if clear == key:
                apikey_entry = f"entry_{key}"
                entry_field = getattr(apikey_window, apikey_entry)
                entry_field.delete(0, "end")
                my_gui.display_message_box(
                    f"{key.replace('_key', '').title()} API key cleared.",
                    "LimeGreen",
                )
                return

            # See if a valid API key was entered
            if (
                PrimeItems.ai[key] != value
            ):  # If the key ent4ered doesn't matych what we already have.
                # Validate the lngth of the key
                if (
                    value
                    and key in apikeys_to_validate
                    and not valid_api_key(key, value)
                ):
                    error_msg = f"{key.replace('_key', '').title()} API key is invalid!"
                    my_gui.display_message_box(
                        error_msg,
                        "Red",
                    )
                    apikey_error_label = add_label(
                        apikey_window,
                        apikey_window,
                        error_msg,
                        "Red",
                        14,
                        "normal",
                        5,
                        0,
                        20,
                        20,
                        "nw",
                    )
                    return

                # Delete any error message that might exist.
                with contextlib.suppress(Exception):
                    apikey_error_label.destroy()
                PrimeItems.ai[key] = value
                apikey_changed = True
                my_gui.display_message_box(
                    f"{key.replace('_', ' ').title()} API key saved: '{value}' .",
                    "LimeGreen",
                )
            else:
                my_gui.display_message_box(
                    f"{key.replace('_', ' ').title()} API key unmodified",
                    "LimeGreen",
                )

        # Save the keys if they have changed.
        if apikey_changed:
            # Write out the new keys via pickle with filetype binary (b)
            with open(KEYFILE, "wb") as key_file:
                pickle.dump(PrimeItems.ai, key_file)

            # Redisplay ai settings with new key.
            display_selected_object_labels(my_gui)
        else:
            my_gui.display_message_box("No API keys changed.", "LimeGreen")

        # Save window position and destroy the window.
        my_gui.ai_apikey_window_position = save_window_position(apikey_window)
        apikey_window.destroy()

    # Show for edit the AI API Key
    def ai_model_selected_event(self, modelplus: str) -> None:
        """
        Set the AI model to the specified model.

        Parameters:
            model (str): The model to set.

        Returns:
            None
        """
        the_view = self.parent

        #  model:  OpenAI: GPT-3.5
        model = modelplus.split(": ")[1]
        if model == "None":
            the_view.display_message_box("No model selected.", "Orange")
            the_view.ai_model = ""
            display_analyze_button(the_view, 13, first_time=False)
            return
        the_view.ai_model = model
        the_view.display_message_box("Model set to " + model + ".", "Green")

        # Set the appropriate API key based on the mdeol chosen.
        set_ai_key(self, model)

        # Redisplay the Analyze button.
        display_analyze_button(the_view, 13, first_time=False)

        # Redisplay the ai settings
        display_selected_object_labels(the_view)

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
        the_view = self.parent

        # Validate the model
        if the_view.ai_model in ("None", ""):
            the_view.display_message_box("No model selected.", "Orange")
            return
        # Set the AI API key based on the model selected.
        if the_view.ai_model not in LLAMA_MODELS and not set_ai_key(
            the_view,
            the_view.ai_model,
        ):
            the_view.display_message_box(
                f"The API Key is not set for model {the_view.ai_model}.",
                "Orange",
            )
            return
        # Make sure we have a single name.
        if the_view.single_profile_name == "None or unnamed!":
            the_view.single_profile_name = ""
        # Do we have a single item identified?
        if (
            the_view.single_project_name
            or the_view.single_profile_name
            or the_view.single_task_name
        ):
            the_view.ai_analyze = True
            the_view.event_handlers.clear_messages_event()  # Clear out all displayed messages.
            the_view.display_message_box(
                f"Running analysis with model {the_view.ai_model}.",
                "Green",
            )
            the_view.tab_to_use = the_view.tabview.get()

            # Do the analysis.  First save our windows and settings.
            store_windows(the_view)
            temp_args = {value: getattr(the_view, value) for value in ARGUMENT_NAMES}
            _, _ = save_restore_args(temp_args, the_view.color_lookup, True)

            # Ok, run the analysis by rerunning the program with our ai_analyze = True
            # The analysis output file will be created and displayed upon reentry to MyGui.
            the_view.event_handlers.rerun_event()
        # Test if no XML data loaded
        elif (
            not PrimeItems.tasker_root_elements["all_projects"]
            and not PrimeItems.tasker_root_elements["all_profiles"]
            and not PrimeItems.tasker_root_elements["all_tasks"]
        ):
            the_view.display_message_box(
                "No projects, profiles, or tasks have been loaded!  Load some XML and try again.",
                "Orange",
            )
        # No single item has been selected.
        else:
            the_view.display_message_box(
                "Single Project/Profile/Task has not been selected!  Select only one and try again.",
                "Orange",
            )
            # Get the Profile or Task to analyze
            # If there are no Profiles or Tasks, redisplay the Analyze button
            if not list_tasker_objects(the_view):
                # Drop here if we don't have any XML loaded yet.
                display_analyze_button(the_view, 13, first_time=False)

            # Update the Project/Profile/Task pulldown option menus.
            set_tasker_object_names(the_view)

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
        the_view = self.parent
        dialog = customtkinter.CTkInputDialog(
            text=f"Current prompt: '{the_view.ai_prompt}'\n\nEnter a new prompt for the AI to use:",
            title="Change the Ai Prompt",
        )
        dialog.focus_set()  # Make sure it is selectable.
        # Get the name entered
        name_entered = dialog.get_input()
        # Canceled?
        if name_entered is None:
            the_view.display_message_box("Prompt change canceled.", "Orange")
        # The same?
        elif name_entered == the_view.ai_prompt:
            the_view.display_message_box("Prompt did not change.", "Orange")
        else:
            # Valid response.
            the_view.ai_prompt = name_entered
            the_view.display_message_box(
                f"Prompt changed to '{the_view.ai_prompt}'.",
                "Green",
            )
            display_selected_object_labels(the_view)

    def coffee_event(self) -> None:
        """
        Opens a web browser to the 'Buy Me a Coffee' page for support.

        This function uses the webbrowser module to open a URL link
        that directs the user to a page where they can support the
        developer by buying a coffee.

        Parameters:
            self (object): The instance of the class.

        Returns:
            None
        """
        coffee_link = "https://www.buymeacoffee.com/mctinker"
        webbrowser.open(coffee_link)

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
        the_view = self.parent
        try:
            changelog = requests.get(CHANGELOG_JSON_URL).json()  # noqa: S113
        except (json.decoder.JSONDecodeError, ConnectionError, Exception):
            the_view.display_message_box("Failed to get changelog.", "Red")
            return
        the_view.event_handlers.clear_messages_event()  # Clear out all displayed messages.
        # Go through loaded dictionary and display each line
        for key, value in changelog.items():
            if (
                "Older History" in value
            ):  # Get out if we hit then of the the new version changes.
                break
            if key == "version":
                the_view.display_message_box(
                    f"Changes in the new version {value}:",
                    "Green",
                )
                the_view.display_message_box("", "Green")
            elif "##" in value:
                # Add spaces as needed to make it more readible
                the_view.display_message_box("", "Green")
                the_view.display_message_box(f"{value}", "Green")
                the_view.display_message_box("", "Green")
            else:
                the_view.display_message_box(f"{value}", "Green")

        the_view.display_message_box("End of changelog.", "Green")

    # The 'Run' program button has been pressed.  Set the run flag and close the GUI
    def run_program_event(self) -> None:
        """
        Starts the program and displays a message box.
        Args:
            self: The class instance.
        Returns:
            None: Does not return anything.
        - Sets the go_program attribute to True to start the program
        - Displays a message box with the text "Program running..." and blocks user interaction
        - Calls the quit() method to exit the program"""
        the_view = self.parent
        the_view.go_program = True
        the_view.rerun = False

        # Reset fund items in case they had already been set by 'Map' view.
        PrimeItems.found_named_items = {
            "single_project_found": False,
            "single_profile_found": False,
            "single_task_found": False,
        }

        # Save the last tab used.
        the_view.tab_to_use = the_view.tabview.get()

        # Validate the XML and cleanup
        the_view.cleanup_and_run(run_only=True)

    # The 'ReRun' program button has been pressed.  Set the run flag and close the GUI
    def rerun_event(self) -> None:
        """
        Resets the program state and exits.
        Args:
            self: The class instance.
        Returns:
            None: Does not return anything.
        - Sets the rerun flag to True to restart the program on next run
        - Calls withdraw() to reset the program state
        - Calls quit() twice to ensure program exits"""
        the_view = self.parent
        # Reset the program state since it may have been previously set by the 'Map' view.
        reset_primeitems_single_names()
        the_view.rerun = True
        the_view.cleanup_and_run(run_only=False)

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
        the_view = self.parent
        # Get and store the position of the windows.
        store_windows(the_view)

        # Save the last tab used.
        the_view.tab_to_use = the_view.tabview.get()

        # Disable debug if we turned it on due to runtime argument '-debug'
        # if the_view.reset_debug_at_end:
        #     the_view.debug = False

        # Indicate that the user hit the 'Exit' button.
        the_view.exit = True

        # Save our last window position
        the_view.window_position = the_view.winfo_geometry()
        # Close it down
        the_view.quit()
        the_view.quit()

    # Diagram View event
    def diagram_event(self) -> None:
        """
        The 'Diagram' view button has been pressed.  Process the diagram file and display it in the GUI.
        Args:
            self: The object instance
        Returns:
            None: Does not return anything
        - Saves the current window positions
        - Checks if there is a Project or Profile
        - If a Project or Profile, it processes the diagram file and displays it in the GUI
        - If not a Project or Profile, it displays a message box indicating that no XML file is loaded.
        """
        guiview = self.parent

        # Make sure we are not currently doing a diagram
        if guiview.map_in_progress:
            return
        guiview.map_in_progress = True

        # Save windows and delete previous mapview window.
        store_windows(self)

        # Check if we have a Project or Profile
        # If we don't already have Project, then get some XML.
        if (
            PrimeItems.tasker_root_elements["all_projects"]
            or PrimeItems.tasker_root_elements["all_profiles"]
        ):
            # Process the diagram: builds the 'network' and then draws it in the GUI
            save_outline = guiview.outline
            guiview.outline = True
            # The following doesn't display
            guiview.display_message_box(
                "The 'Diagram' view is running in the background.  Please stand by...",
                "LimeGreen",
            )
            guiview.textbox.focus_set()

            # Get rid of the previous window
            if guiview.diagramview_window is not None:
                guiview.diagramview_window.destroy()

            # Save the settings
            temp_args = {value: getattr(guiview, value) for value in ARGUMENT_NAMES}
            _, _ = save_restore_args(temp_args, guiview.color_lookup, True)

            # Reset PrimItems
            reset_primeitems_single_names()

            # Now flag the fact that we are rerunning for the map view.
            # These flags are critical for the proper proceessing of the map.
            guiview.guiview = True  # Set it for save_settings
            PrimeItems.program_arguments["guiview"] = True  # Set it for mapit_all
            guiview.doing_diagram = True
            PrimeItems.program_arguments["doing_diagram"] = True  # Set it for mapit_all

            # Set our target objects since mapit-all will bypass setting these values
            PrimeItems.program_arguments["single_project_name"] = (
                guiview.single_project_name
            )
            PrimeItems.program_arguments["single_profile_name"] = (
                guiview.single_profile_name
            )
            PrimeItems.program_arguments["single_task_name"] = guiview.single_task_name

            # Re-invoke ourselves to force the html to be written
            _ = mapit_all("")

            # See if errors occurred
            if PrimeItems.error_code == 1:
                guiview.display_message_box(PrimeItems.error_msg, "Orange")
                PrimeItems.error_code = 0
                PrimeItems.error_msg = ""
                guiview.map_in_progress = False
                return

            # Process the diagram file
            diagram_dir = f"{os.getcwd()}{PrimeItems.slash}{DIAGRAM_FILE}"  # Get the directory from which we are running.
            # Read the diagram file
            with open(str(diagram_dir), encoding="utf-8") as diagram_file:
                diagram_data = [
                    line.rstrip() for line in diagram_file
                ]  # Read file into a list

                # Display the diagram
                guiview.diagramview = guiview.display_view("diagram", diagram_data)
                guiview.textview = guiview.diagramview
                guiview.display_message_box("Diagram View displayed.", "Green")
                diagram_file.close()

            # Cleanup
            guiview.outline = save_outline
            guiview.guiview = False
            PrimeItems.program_arguments["guiview"] = False

            # Save window.
            store_windows(guiview)
        else:
            display_no_xml_message(guiview)

        # Indicate that we are dont.
        guiview.map_in_progress = False

    def map_event(self) -> None:
        """
        Executes the map event.

        This function checks if the XML file is loaded. If it is, it checks if there are any projects, profiles, tasks,
        or scenes in the XML. If there are, it sets the `guiview` attribute to `True` and executes the `mapit_all`
        function. If there are no projects, profiles, tasks, or scenes, it displays a message box indicating that the
        map is not possible. If the XML is not loaded, it displays a message box indicating that the map is not
        possible because there is no XML file loaded.

        Parameters:
            None

        Returns:
            None
        """
        guiview = self.parent
        # Make sure we are not already doing a map
        if guiview.map_in_progress:
            return
        guiview.map_in_progress = True

        # If we have some XML, then map it.
        if (
            PrimeItems.tasker_root_elements["all_projects"]
            or PrimeItems.tasker_root_elements["all_profiles"]
            or PrimeItems.tasker_root_elements["all_tasks"]
            or PrimeItems.tasker_root_elements["all_scenes"]
        ):
            # In order for the map to work, we need to ensure that we have the colors defined.
            if not guiview.color_lookup:
                guiview.color_lookup = set_color_mode(guiview.appearance_mode)

            # Initiate the map view.
            try:
                guiview.remapit(clear_names=True)
            except TclError:
                return
        else:
            display_no_xml_message(guiview)

        # Indicate that we are done.
        guiview.map_in_progress = False

    def viewlimit_event(self: object, view_limit: str) -> None:
        """
        View Limit Event
        """
        guiview = self.parent
        guiview.view_limit = 9999999 if view_limit == "Unlimited" else int(view_limit)
        if view_limit == 9999999:
            view_limit = "Unlimited"
        guiview.viewlimit_optionmenu.set(view_limit)
        guiview.display_message_box(f"View Limit set to {view_limit}.", "Green")

    # Process the '?' List XML Files query button
    def query_event(self: object, query_name: str) -> None:
        """Function to display help text for the query_event method.
        Parameters:
            - self (object): The object that the method is being called on.
            - query_name (str): The name of the query to display help for.
        Returns:
            - None: This method does not return anything.
        Processing Logic:
            - Displays help text for query_event method.
            - Uses new_message_box method.
            - Help text is stored in {query_event.upper}_HELP_TEXT variable."""

        guiview = self.parent

        help_texts = {
            "viewlimit": ("View Limit Help", VIEWLIMIT_HELP_TEXT),
            "view": ("Views Help", VIEW_HELP_TEXT),
            "ai": ("Ai Analyze Help", AI_HELP_TEXT),
            "help": ("", HELP),
            "android": ("Get XML From Android Device Help", BACKUP_HELP_TEXT),
            "listfile": ("List Android Files Help", LISTFILES_HELP_TEXT),
            "search": ("Search Help", SEARCH_HELP_TEXT),
            "ppp": ("Profiles Per Line Help", PPP_HELP_TEXT),
            "apikey": ("API Key Help", APIKEY_HELP_TEXT),
        }

        title, help_text = help_texts.get(
            query_name,
            ("", "No help available for this query."),
        )

        guiview.new_message_box(f"{title}\n\n{help_text}")
        guiview.clear_messages = (
            True  # Flag to tell display_message_box to clear the message box
        )

    # Search textbox event
    def search_event(self: object, textview: CTkTextview) -> None:
        """
        Handles the search event in the text view box.

        This function retrieves the search input from the user, removes any existing 'found' tags,
        and then searches for the input string in the text view box. If the string is found, it is
        tagged as 'found' and highlighted in red. The function then sets the focus back to the text
        view box.
        Note: The tkinter search function is not used since it never returns when hitting the stopindex.

        Parameters:
            self (object): The instance of the class.
            title (str): The title of the view to be searched:L diagram or map

        Returns:
            None
        """
        # Start search at beginning
        textview.search_current_line = "1.0"
        try:
            textview.search_indecies = []
        except AttributeError:
            return

        # Get the string to search for.
        search_input = textview.search_input.get()

        # remove tag 'found' from index 1 to END
        textview.textview_textbox.tag_remove("found", "1.0", "end")

        # Check if search_input is not empty
        if search_input:
            # Determine the color to highlight the next/previous string in.
            if is_color_dark(PrimeItems.colors_to_use["background_color"]):
                textview.search_color_text = "darkblue"
                textview.search_color_highlight = "yellow"
                textview.search_color_nextprev = "orange"
            else:
                textview.search_color_text = "yellow"
                textview.search_color_highlight = "orange"
                textview.search_color_nextprev = "blue"

            textview.search_string = search_input
            # Get the entire textbox into a list, one item per line.
            ty = textview.textview_textbox.get("1.0", "end").rstrip().split("\n")
            # Find all matches.
            search_hits = search_substring_in_list(
                ty,
                search_input,
                stop_on_first_match=False,
            )
            number_of_hits = len(search_hits)

            # Process the matches
            first_time = True
            if number_of_hits > 0:
                for match in search_hits:
                    # Point to the actual line and position of the match.
                    text_line_num = match[0] + 1
                    text_line_pos = match[1]

                    # Get the index and last-index for the match.
                    idx = f"{text_line_num!s}.{text_line_pos!s}"
                    lastidx = f"{idx}+{len(search_input)}c"

                    # Keep track of it for 'Next' and 'Prev'.
                    textview.search_indecies.append(idx)
                    if first_time:
                        textview.search_current_line = idx
                        first_time = False

                    # Add the tag for highlighting the matches.
                    textview.textview_textbox.tag_add("found", idx, lastidx)

                    # Tag it so that it will get caught by 'click_text' for hover.
                    textview.tag_items("found", f"Found: {search_input}   ")

                    # Add the list of matches to this entry in mygui.
                    self.parent.items_for_selection["found"]["indecies"] = (
                        textview.search_indecies
                    )

                # Mark located string by highlighting it.
                textview.textview_textbox.tag_config(
                    "found",
                    foreground=textview.search_color_text,
                    background=textview.search_color_highlight,
                )

                # Set the line at the first hit.  "See" makes it visible (sometimes).
                textview.textview_textbox.see(textview.search_current_line)
                textview.textview_textbox.focus_set()

            # Search string not found.
            else:
                output_label(textview, "Search string not found.")

        else:
            no_search_string(textview)

    def clear_event(self: object, textview: CTkTextview) -> None:
        """
        Handles the clear event in the text view box.

        This function clears the search text (highl;ighted) from the text view box.

        Parameters:
            self (object): The instance of the class.
            title (str): The title of the view to be searched: diagram or map

        Returns:
            None
        """
        # remove tag 'found' and "next" from index 1 to END
        textview.textview_textbox.tag_remove("found", "1.0", "end")
        textview.textview_textbox.tag_remove("next", "1.0", "end")
        textview.textview_textbox.tag_remove("inlist", "1.0", "end")
        if textview.textview_textbox.diagram_highlighted_connector:
            remove_tags_from_bars_and_names(textview)
            textview.textview_textbox.tag_config(
                textview.textview_textbox.diagram_highlighted_connector,
                background=make_hex_color(
                    textview.master.master.color_lookup["background_color"],
                ),
            )
            textview.textview_textbox.diagram_highlighted_connector = ""
        # Clear the search input field.
        kaka = textview.search_input.get()
        textview.search_input.delete(0, len(kaka) + 1)
        # Remove the jump-to buttons
        with contextlib.suppress(AttributeError):
            textview.jump_top.destroy()
        with contextlib.suppress(AttributeError):
            textview.jump_bottom.destroy()

    def wordwrap_event(self: object, textview: CTkTextview) -> None:
        """
        Handles the wordwrap event in the text view box.

        This function toggles the wordwrap setting in the text view box.

        Parameters:
            self (object): The instance of the class.
            title (str): The title of the view to be searched: diagram or map

        Returns:
            None
        """
        # Configure the textbox.
        textview.wordwrap = not textview.wordwrap
        if textview.wordwrap:
            textview.textview_textbox.configure(state="normal", wrap="word")
            wrap_msg = "on"
        else:
            textview.textview_textbox.configure(state="normal", wrap="none")
            wrap_msg = "off"

        # Let the user know.
        output_label(textview, f"Word wrap is {wrap_msg}")

    def nextprev_search_event(self, textview: CTkTextview, search_next: bool) -> None:
        """
        Handles the next search event in the text view box.

        This function searches the text view box for the next occurrence of the search string,
        and positions the string so that it is within the visible area of the text view box.

        Parameters:
            self (object): The instance of the class.
            title (str): The title of the view to be searched: diagram or map
            next (bool): Whether to search next or previous.
        """
        if search_next:
            search_nextprev_string(self, textview, "next")
        else:
            search_nextprev_string(self, textview, "previous")

    def topbottom_event(self: object, textview: CTkTextview, top: bool) -> None:
        """
        Handles going to top/bottom of text view.

        This function toggles the wordwrap setting in the text view box.

        Parameters:
            self (object): The instance of the class.

        Returns:
            None
        """
        # Go to the top of the textbox.
        if top:
            textview.textview_textbox.see("1.0")
            display_msg = "Top"
            with contextlib.suppress(AttributeError, IndexError):
                textview.search_current_line = textview.search_indecies[
                    0
                ]  # Point to first search hit.
            textview.top = True
        else:
            # Go to bottom
            if "Diagram" in textview.title:
                textview.textview_textbox.see("end-1c")
            else:
                # Go to bottom (first valid non-blank line)
                line_count = int(
                    textview.textview_textbox.index("end-1c").split(".")[0],
                )
                line_pos = line_count - 1
                while line_pos:
                    line = textview.textview_textbox.get(
                        f"{line_pos!s}.0",
                        f"{line_pos!s}.end",
                    )
                    if "CAVEATS:" in line:
                        break
                    line_pos -= 1
                textview.textview_textbox.see(f"{line_pos!s}.0")
            display_msg = "Bottom"

        # Let the user know.
        output_label(textview, f"{display_msg} of text view displayed.")

    def jump_topbottom_event(
        self: object,
        textview: CTkTextview,
        top: bool,
        connector: int,
    ) -> None:
        """
        Handles going to jump-to top/bottom of text view.

        This function toggles the wordwrap setting in the text view box.

        Parameters:
            self (object): The instance of the class

        Returns:
            None
        """
        # Calculate half the length of the task name.   We have to subntract half the length
        # because we want the line to be in the beginning of the task name rather than the middle.
        task_half_length = len(connector["task_upper"][0]) // 2
        # Get the correct line/position based on top or bottom.
        if top:
            seek_line = f"{connector['start_top'][0]!s}.{connector['start_top'][1] - task_half_length!s}"
            modifier = "top"
        else:
            # Bottom: Find the max bottom value.
            bottom_line = connector["end_bottom"][0]
            for extra_bar in connector["extra_bars"]:
                bottom_line = max(bottom_line, extra_bar[0])
            seek_line = (
                f"{bottom_line!s}.{connector['start_bottom'][1] - task_half_length!s}"
            )
            modifier = "bottom"
        # Display the Task
        textview.textview_textbox.see(seek_line)

        output_label(
            textview,
            f"Showing {modifier} of connection to {connector['task_upper'][0]}",
        )

    def profiles_level_event(
        self: object,
        textview: CTkTextview,
        profiles_per_line: str,
    ) -> None:
        """
        Handles the profile level event in the text view box.

        This function toggles the profile level setting in the text view box.

        Parameters:
            self (object): The instance of the class.

        Returns:
            None
        """
        # Get thhe number of Profiles per line
        PrimeItems.profiles_per_line = int(profiles_per_line)

        # Relaunch the diagram
        self.diagram_event()

        # Reset the default for this diagram only.
        self.parent.textview.profiles_per_line_option.set(profiles_per_line)

        # Let the user know.
        output_label(self.parent.textview, f"Profile Per Line is {profiles_per_line}.")

    def tasklimit_event(self: object, slider_value: float) -> None:
        """
        Handles the task limit event in the text view box.

        This function sets the task limit of the text view box.

        Parameters:
            self (object): The instance of the class.
            textview (CTkTextview): The text view box.

        Returns:
            None
        """
        # Get and set thew Task action warning limit
        slider_value = int(slider_value)
        self.parent.task_action_warning_limit = slider_value
        self.parent.task_action_label.configure(
            text=f"Task Action Limit: {slider_value}",
        )

    def _handle_event(self, event_method: str, view_name: str, *args: str) -> None:
        """
        Internal method to handle events based on event method and view name.

        Parameters:
            event_method (str): The name of the event method to call.
            view_name (str): The name of the view to apply the event to.
            *args (str): Additional arguments to pass to the event method.

        Returns:
            None
        """
        method = getattr(self, event_method)
        view = getattr(self.parent, view_name)
        method(view, *args)

    # Handlers for Search/Next/Prev/Clear and Toglle Word Wrap for each view.
    def diagram_search_event(self) -> None:  # noqa: D102
        self._handle_event("search_event", "diagramview")

    def map_search_event(self) -> None:  # noqa: D102
        self._handle_event("search_event", "mapview")

    def analysis_search_event(self) -> None:  # noqa: D102
        self._handle_event("search_event", "analysisview")

    def diagram_nextprev_event(self, search_next: bool) -> None:  # noqa: D102
        self._handle_event("nextprev_search_event", "diagramview", search_next)

    def map_nextprev_event(self, search_next: bool) -> None:  # noqa: D102
        self._handle_event("nextprev_search_event", "mapview", search_next)

    def analysis_nextprev_event(self, search_next: bool) -> None:  # noqa: D102
        self._handle_event("nextprev_search_event", "analysisview", search_next)

    def diagram_clear_event(self) -> None:  # noqa: D102
        self._handle_event("clear_event", "diagramview")

    def map_clear_event(self) -> None:  # noqa: D102
        self._handle_event("clear_event", "mapview")

    def analysis_clear_event(self) -> None:  # noqa: D102
        self._handle_event("clear_event", "analysisview")

    def diagram_wordwrap_event(self) -> None:  # noqa: D102
        self._handle_event("wordwrap_event", "diagramview")

    def map_wordwrap_event(self) -> None:  # noqa: D102
        self._handle_event("wordwrap_event", "mapview")

    def analysis_wordwrap_event(self) -> None:  # noqa: D102
        self._handle_event("wordwrap_event", "analysisview")

    def analysis_topbottom_event(self, top: bool) -> None:  # noqa: D102
        self._handle_event("topbottom_event", "analysisview", top)

    def map_topbottom_event(self, top: bool) -> None:  # noqa: D102
        self._handle_event("topbottom_event", "mapview", top)

    def diagram_topbottom_event(self, top: bool) -> None:  # noqa: D102
        self._handle_event("topbottom_event", "diagramview", top)

    def diagram_jump_topbottom_event(self, top: bool, connector: int) -> None:  # noqa: D102
        self._handle_event("jump_topbottom_event", "diagramview", top, connector)

    def profiles_per_line_event(self, profiles_per_line: str) -> None:  # noqa: D102
        self._handle_event("profiles_level_event", "diagramview", profiles_per_line)

    def ai_apikey_get_event(self, cancel: bool, clear: bool) -> None:  # noqa: D102
        self._handle_event("ai_apikey_process_event", "ai_apikey_window", cancel, clear)
