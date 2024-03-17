"""Code to manage the graphical user interface."""

#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# userintr: provide GUI and process input for program arguments                        #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
import contextlib
import webbrowser
from pathlib import Path

import customtkinter
from CTkColorPicker.ctk_color_picker import AskColor

from maptasker.src.colrmode import set_color_mode
from maptasker.src.config import OUTPUT_FONT
from maptasker.src.getputer import save_restore_args
from maptasker.src.guiutils import (
    add_button,
    add_label,
    check_for_changelog,
    clear_android_buttons,
    create_changelog,
    initialize_gui,
    initialize_screen,
    is_new_version,
    ping_android_device,
    valid_item,
    validate_or_filelist_xml,
)
from maptasker.src.mapit import do_rerun
from maptasker.src.maputils import update, validate_xml_file
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import (
    ARGUMENT_NAMES,
    TYPES_OF_COLOR_NAMES,
    VERSION,
    DISPLAY_DETAIL_LEVEL_all_parameters,
)

# Color Modes: "System" (standard), "Dark", "Light"
customtkinter.set_appearance_mode("System")
# Themes: "blue" (standard), "green", "dark-blue"
customtkinter.set_default_color_theme("blue")

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
    "conditions, TaskerNet information, preferences, twisties, directory, and configuration outline.\n\n"
    "* Display Conditions: Turn on the display of Profile and Task conditions.\n\n"
    "* Display TaskerNet Info - If available, display TaskerNet publishing information.\n\n"
    "* Display Tasker Preferences - display Tasker's system Preferences.\n\n"
    "* Hide Task Details under Twisty: hide Task information within ► and click to display.\n\n"
    "* Display Directory of hyperlinks at beginning.\n\n"
    "* Display Configuration Outline and Map of your Projects/Profiles/Tasks/Scenes.\n\n"
    "* Project/Profile/Task/Scene Names options to italicize, bold, underline and/or highlight their names.\n\n"
    "* Indentation amount for If/Then/Else Task Actions.\n\n"
    "* Save Settings - Save these settings for later use.\n\n"
    "* Restore Settings - Restore the settings from a previously saved session.\n\n"
    "* Report Issue - This will bring up your browser to the issue reporting site, and you can use this to "
    "either report a bug or request a new feature ( [Feature Request] )\n\n"
    "* Appearance Mode: Dark, Light, or System default.\n\n"
    "* Reset Options: Clear everything and start anew.\n\n"
    "* Font To Use: Change the monospace font used for the output.\n\n"
    "* Display Outline: Display Projects/Profiles/Tasks/Scenes configuration outline.\n\n"
    "* Get XML from Android Device: fetch the backup/exported "
    "XML file from Androiddevice.  You will be asked for the IP address and port number for your"
    " Android device, as well as the file location on the device.\n\n"
    "* Run: Run the program with the settings provided and then exit.\n"
    "* ReRun: Run multiple times (each time with new settings) without exiting.\n\n"
    "* Specific Name tab: enter a single, specific named item to display...\n"
    "   - Project Name: enter a specific Project to display.\n"
    "   - Profile Name: enter a specific Profile to display.\n"
    "   - Task Name: enter a specific Task to display.\n"
    "   (These three are exclusive: enter one only)\n\n"
    "* Colors tab: select colors for various elements of the display.\n"
    "              (e.g. color for Projects, Profiles, Tasks, etc.).\n\n"
    "* Debug tab: Display Runtime Settings option and turn on Debug mode.\n\n"
    "* Exit: Exit the program (quit).\n\n"
    "Note: You will be prompted to identify your Tasker XML file once you hit the 'Run' button if you have not yet done so.\n\n"
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
    "    https://shorturl.at/buvK6\n\n"
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

HELP = f"MapTasker {VERSION} Help\n\n{INFO_TEXT}"


# ##################################################################################
# Class to define the GUI configuration
# ##################################################################################
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

        # Initialize GUI
        initialize_gui(self)

        # Add menu elements
        initialize_screen(self)

        # set default values
        self.set_defaults(True)

        # Now restore the settings and update the fields if not resetting.
        if not PrimeItems.program_arguments["reset"]:
            self.restore_settings_event()

            self.display_message_box("Settings restored.", True)

            self.message = "Settings restored."  # self.message set to "" in set_defaults, above.

            if self.android_ipaddr:
                # Display backup details as a label
                self.display_backup_details()

            # Check for single item only to be displayed
            if self.single_project_name:
                self.single_name_status(f"Display only Project '{self.single_project_name}'.", "#3f99ff")
            if self.single_profile_name:
                self.single_name_status(f"Display only Profile '{self.single_profile_name}'.", "#3f99ff")
            if self.single_task_name:
                self.single_name_status(f"Display only Task '{self.single_task_name}'.", "#3f99ff")

        # Check if newer version of our code is available on Pypi (only check every 24 hours).
        if is_new_version():
            self.new_version = True
            # We have a new version.  Let user upgrade.
            self.upgrade_button = add_button(
                self,
                self,
                "",
                "#79ff94",
                "#6563ff",
                self.upgrade_event,
                1,
                "Upgrade to Latest Version",
                7,
                2,
                (0, 170),
                (0, 20),
                "sw",
            )

            self.message = self.message + "\n\nA new version of MapTasker is available."
        else:
            self.new_version = False

        # See if we have a changelog, and get it if we do.
        check_for_changelog(self)

        if self.message:
            self.display_message_box(self.message, True)

    # ##################################################################################
    # Establish all of the default values used
    # ##################################################################################
    def set_defaults(self, first_time: bool) -> None:
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
        self.sidebar_detail_option.configure(values=["0", "1", "2", "3", "4"])
        self.sidebar_detail_option.set("4")
        self.display_detail_level = 4
        self.conditions = self.preferences = self.taskernet = self.debug = self.everything = self.clear_settings = (
            self.reset
        ) = self.restore = self.exit = self.bold = self.highlight = self.italicize = self.underline = (
            self.go_program
        ) = self.outline = self.rerun = self.list_files = self.runtime = self.save = self.twisty = self.directory = (
            self.fetched_backup_from_android
        ) = False
        self.single_project_name = self.single_profile_name = self.single_task_name = self.file = ""
        self.color_text_row = 2
        self.appearance_mode_optionemenu.set("System")
        self.appearance_mode = "system"
        self.indent_option.set("4")
        self.indent = 4
        self.color_labels = []
        self.android_ipaddr = ""
        self.android_port = ""
        self.android_file = ""
        if first_time:
            # self.textbox.insert("0.0", HELP)
            self.all_messages = ""
        self.color_lookup = {}  # Setup default dictionary as empty list
        self.font = OUTPUT_FONT
        self.gui = True
        self.color_row = 4
        self.edit = False
        self.edit_type = ""

        self.message = ""

        # Display current Items setting.
        self.single_name_status("Display all Projects, Profiles, and Tasks.", "#3f99ff")

    # ##################################################################################
    # Display the Backup button
    # ##################################################################################
    def display_backup_button(self, the_text: str, color1: str, color2: str, routine: object) -> None:
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
        # self.get_backup_button = add_button(
        #    self,
        #    self,
        #    color1,
        #    ("#0BF075", "#1AD63D"),
        #    color2,
        #    routine,
        #    2,
        #    the_text,
        #    7,
        #    1,
        #    (200, 10),
        #    (0, 10),
        #    "nw",
        # )
        width = len(the_text) + 4
        self.get_backup_button = customtkinter.CTkButton(
            master=self,
            fg_color=color1,
            border_color=color2,
            border_width=2,
            width=width,
            text=the_text,
            command=routine,
            text_color=("#0BF075", "#1AD63D"),
        )
        self.get_backup_button.grid(row=7, column=1, columnspan=2, padx=(200, 200), pady=(0, 10), sticky="nw")
        return self.get_backup_button

    # ##################################################################################
    # Display Message Box
    # ##################################################################################
    def display_message_box(self, message: str, good: bool) -> None:
        # If "good", display in green.  Otherwise, must be bad and display in red.
        r"""
        Displays a message box with the given message and color.

        Args:
            message: The message to display in one line.
            good: Whether the message is good or bad in one line.
        Returns:
            None: No return value in one line.

        - Deletes prior textbox contents
        - Recreates the textbox
        - Sets the color based on good/bad
        - Inserts the accumulated messages
        - Configures textbox properties
        """
        color = "Green" if good else "Red"
        # Delete prior contents
        self.textbox.destroy()

        # Recreate text box
        self.textbox = customtkinter.CTkTextbox(self, height=500, width=600)
        self.textbox.grid(row=0, column=1, padx=20, pady=40, sticky="nsew")

        # Display some colored text
        # self.textbox.insert('end', 'This is some colored text.\n')
        # self.textbox.tag_add('color', '1.5', '1.11')  # '1.5' means first line, 5th character; '1.11' means first line, 11th character
        # self.textbox.tag_config('color', foreground='red')

        self.all_messages = f"{self.all_messages}{message}\n"
        # self.all_messages = f"{message}\n"
        # insert at line 0 character 0
        self.textbox.insert("0.0", self.all_messages)
        # Set read-only, color, wrap around and font
        self.textbox.configure(state="disabled", text_color=color, wrap="word", font=(self.font, 14))
        self.textbox.focus_set()

    # ##################################################################################
    # Validate name entered
    # ##################################################################################
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
            error_message = (
                f"\n\nEither the name entered for the {element_name} is blank or the"
                f" 'Cancel' button was clicked.\n\nAll {element_name}s will be"
                " displayed."
            )
            self.named_item = False
        # Check to make sure only one named item has been entered
        elif self.single_project_name and self.single_profile_name:
            error_message = (
                "Error:\n\nYou have entered both a Project and a Profile name!\n\nTry again and only select one."
            )
        elif self.single_project_name and self.single_task_name:
            error_message = (
                "Error:\n\nYou have entered both a Project and a Task name!\n\nTry again and only select one."
            )
        elif self.single_profile_name and self.single_task_name:
            error_message = (
                "Error:\n\nYou have entered both a Profile and a Task name!\n\nTry again and only select one."
            )
        # Make sure the named item exists
        elif not valid_item(the_name, element_name, self.debug, self.appearance_mode):
            error_message = f'Error: "{the_name}" {element_name} not found!!  Try again.\n{PrimeItems.error_msg}'

        # If we have an error, display it and blank out the various individual names
        if error_message:
            # Delete prior contents
            self.all_messages = ""

            self.display_message_box(error_message, False)
            (
                self.single_project_name,
                self.single_profile_name,
                self.single_task_name,
            ) = ("", "", "")
            return False

        self.display_message_box(
            f"Display only the '{the_name}' {element_name} (overrides any previous set name).",
            True,
        )
        return True

    # ##################################################################################
    # Display single item status.
    # ##################################################################################
    def single_name_status(self, status_message: str, color_to_use: str) -> None:
        # Display The selection
        """
        Display a status message with a given color.
        Args:
            status_message: The status message to display in one line.
            color_to_use: The color to use for the text in one line.
        Returns:
            None: No value is returned.
        - The status message and color are passed to a CTkLabel widget.
        - The label is placed in a grid layout on the "Specific Name" tab.
        - Text color is set using the passed color."""
        self.single_label = add_label(
            self,
            self.tabview.tab("Specific Name"),
            status_message,
            ("#0BF075", f"{color_to_use}"),
            0,
            "normal",
            5,
            0,
            20,
            (10, 10),
            "w",
        )
        # self.single_label = customtkinter.CTkLabel(
        #    self.tabview.tab("Specific Name"),
        #    text=status_message,
        #    anchor="w",
        #    text_color=("#0BF075", color_to_use),
        # )
        # self.single_label.grid(row=5, column=0, padx=20, pady=(10, 10), sticky="nsew")

    # ##################################################################################
    # Process single name selection/event
    # ##################################################################################
    def process_name_event(
        self,
        my_name: str,
        checkbox1: customtkinter.CHECKBUTTON,
        checkbox2: customtkinter.CHECKBUTTON,
        checkbox3: customtkinter.CHECKBUTTON,
    ) -> None:
        #  Clear any prior error message.
        """
        Processes name event from checkboxes.
        Args:
            my_name: Name of item to filter by
            checkbox1: First checkbox
            checkbox2: Second checkbox
            checkbox3: Checkbox clicked
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
        self.textbox.destroy()
        # Deselect the other two check boxes.
        checkbox1.deselect()
        checkbox2.deselect()
        # Display prompt for name
        dialog = customtkinter.CTkInputDialog(
            text=f"Enter {my_name} name (case sensitive):",
            title=f"Display Specific {my_name}",
        )
        # Get the name entered
        name_entered = dialog.get_input()
        # Name sure it is a valid name and display message.
        if self.check_name(name_entered, my_name):
            # Name is valid... deselect other buttons and set the name
            self.single_project_name = self.single_profile_name = self.single_task_name = ""
            # Get the name entered
            match my_name:
                case "Project":
                    self.single_project_name = name_entered

                case "Profile":
                    self.single_profile_name = name_entered

                case "Task":
                    self.single_task_name = name_entered

                case _:
                    pass

            # Let the user know...
            self.single_name_status(f"Display only {my_name} '{name_entered}'.", "#3f99ff")

        else:
            self.single_name_status("Display all Projects, Profiles, and Tasks.", "#3f99ff")

        # Deselect the check box just selected
        checkbox3.deselect()

    # ##################################################################################
    # Process single name restore
    # ##################################################################################
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
        # Make sure it is a valid name
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

    # ##################################################################################
    # Process the Project Name entry
    # ##################################################################################
    def single_project_name_event(self) -> None:
        """Generates a single project name event from button inputs
        Args:
            self: The class instance
        Returns:
            None: No value is returned
        - Gets the project name from the second button
        - Gets the event type from the third button
        - Gets the timestamp from the first button
        - Calls process_name_event() to generate the event"""
        self.process_name_event(
            "Project",
            self.string_input_button2,
            self.string_input_button3,
            self.string_input_button1,
        )

    # ##################################################################################
    # Process the Profile Name entry
    # ##################################################################################
    def single_profile_name_event(self) -> None:
        """Generates a single profile name event from button inputs
        Args:
            self: The class instance
        Returns:
            None: No value is returned
        - Gets name from button1 input
        - Gets category from button3 input
        - Gets action from button2 input
        - Calls process_name_event to generate the event"""
        self.process_name_event(
            "Profile",
            self.string_input_button1,
            self.string_input_button3,
            self.string_input_button2,
        )

    # ##################################################################################
    # Process the Task Name entry
    # ##################################################################################
    def single_task_name_event(self) -> None:
        """Processes a single task name event.
        Args:
            self: The class instance.
        Returns:
            None: Does not return anything.
        - Gets the task name from the first string input button
        - Gets additional details from the other string input buttons
        - Calls process_name_event() to handle the full event"""
        self.process_name_event(
            "Task",
            self.string_input_button1,
            self.string_input_button2,
            self.string_input_button3,
        )

    # ##################################################################################
    # Process the screen mode: dark, light, system
    # ##################################################################################
    def change_appearance_mode_event(self, new_appearance_mode: str) -> None:
        """
        Change the appearance mode of the GUI
        Args:
            new_appearance_mode: The new appearance mode as a string
        Returns:
            None: Does not return anything
        - Set the global appearance mode to the new mode
        - Update the local appearance mode attribute to the new lowercased mode"""
        customtkinter.set_appearance_mode(new_appearance_mode)
        self.appearance_mode = new_appearance_mode.lower()

    # ##################################################################################
    # Process the screen mode: dark, light, system
    # ##################################################################################
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
        self.display_message_box(f"Font To Use set to {font_selected}", True)

    # ##################################################################################
    # Process the Display Detail Level selection
    # ##################################################################################
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
        self.display_detail_level = display_detail
        self.sidebar_detail_option.set(display_detail)
        self.inform_message("Display Detail Level", True, display_detail)
        # Disable twisty if detail level is less than 3
        if self.twisty and int(display_detail) < DISPLAY_DETAIL_LEVEL_all_parameters:
            self.display_message_box(
                f"Hiding Tasks with Twisty has no effect with Display Detail Level set to {display_detail}.  Twisty disabled!",
                False,
            )
            self.twisty = False
            self.twisty_checkbox.deselect()

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

    # ##################################################################################
    # Process the Identation Amount selection
    # ##################################################################################
    def indent_selected_event(self, ident_amount: str) -> None:
        """Indent selected text or code block
        Args:
            ident_amount: The amount of indentation to apply as a string
        Returns:
            None: No value is returned
        - Set the indent attribute to the passed ident_amount
        - Update the indent option dropdown to the selected amount
        - Display confirmation message of indentation amount"""
        self.indent = ident_amount
        self.indent_option.set(ident_amount)
        self.inform_message("Indentation Amount", True, ident_amount)

    # ##################################################################################
    # Edit selection
    # ##################################################################################
    def edit_event(self, edit_type: str) -> None:
        """
        Edit an event by setting the edit type.

        :param edit_type: A string representing the type of edit.
        :return: None
        """

        self.edit_type = edit_type
        self.edit = True

        from edittasker.src.edtnewui import ToplevelWindow

        self.edit_type = edit_type
        self.edit = True
        if self.toplevel_window is None or not self.toplevel_window.winfo_exists():
            self.toplevel_window = ToplevelWindow(self)  # create window if its None or destroyed
        else:
            self.toplevel_window.focus()  # if window exists focus it

    # ##################################################################################
    # Process color selection
    # ##################################################################################
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
                    False,
                )
                return
        # Put up color picker and get the color
        pick_color = AskColor()  # Open the Color Picker
        color = pick_color.get()  # Get the color
        if color is not None:
            self.display_message_box(f"{color_selected_item} color changed to {color}", True)

            # Okay, plug in the selected color for the selected named item
            self.extract_color_from_event(color, color_selected_item)

            # Display the color.
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

    # ##################################################################################
    # Color selected...process it.
    # ##################################################################################
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
        self.color_lookup[TYPES_OF_COLOR_NAMES[color_selected_item]] = (
            color  # Add color for the selected item to our dictionary
        )

    # ##################################################################################
    # Process the 'conditions' checkbox
    # ##################################################################################
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
        self.conditions = self.get_input_and_put_message(
            self.condition_checkbox,
            "Display Profile and Task Action Conditions",
        )

    # ##################################################################################
    # Process the 'conditions' checkbox
    # ##################################################################################
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
        self.outline = self.get_input_and_put_message(self.outline_checkbox, "Display Configuration Outline")

    # ##################################################################################
    # Process the 'everything' checkbox
    # ##################################################################################
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
            "runtime": lambda: self.select_deselect_checkbox(self.runtime_checkbox, value, "Display Runtime Settings"),
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
            "display_detail_level": lambda: self.detail_selected_event("4"),
        }

        self.everything = self.everything_checkbox.get()
        value = self.everything

        new_message = all_messages = ""
        for key in message_map:
            if message_func := message_map.get(key):
                new_message = f"{message_func()}"
                if key == "display_detail_level":
                    new_message = f"Display Detail Level: {self.display_detail_level}"
                all_messages = f"{all_messages}{new_message}"
            # Check if key is an attribute on self before setting
            if hasattr(self, key) and key != "display_detail_level":
                setattr(self, key, value)

        # Handle Display Detail Level
        self.display_detail_level = 4

        self.display_message_box(all_messages, True)

    # ##################################################################################
    # Process the 'Tasker Preferences' checkbox
    # ##################################################################################
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
        self.preferences = self.get_input_and_put_message(self.preferences_checkbox, "Display Tasker Preferences")

    # ##################################################################################
    # Process the 'Twisty' checkbox
    # ##################################################################################
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
        self.twisty = self.get_input_and_put_message(self.twisty_checkbox, "Hide Task Details Under Twisty")
        if self.twisty and int(self.display_detail_level) < DISPLAY_DETAIL_LEVEL_all_parameters:
            self.display_message_box(
                "This has no effect with Display Detail Level less than 3.  Display Detail Level set to 3!",
                False,
            )
            self.sidebar_detail_option.set("3")  # display detail level
            self.display_detail_level = "3"

    # ##################################################################################
    # Process the 'Display Directory' checkbox
    # ##################################################################################
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
        self.directory = self.get_input_and_put_message(self.directory_checkbox, "Display Directory")

    # ##################################################################################
    # Process the 'Bold Names' checkbox
    # ##################################################################################
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
        self.bold = self.get_input_and_put_message(self.bold_checkbox, "Display Names in Bold")

    # ##################################################################################
    # Process the 'Highlight Names' checkbox
    # ##################################################################################
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
        self.highlight = self.get_input_and_put_message(self.highlight_checkbox, "Display Names Highlighted")

    # ##################################################################################
    # Process the 'Italicize Names' checkbox
    # ##################################################################################
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
        self.italicize = self.get_input_and_put_message(self.italicize_checkbox, "Display Names Italicized")

    # ##################################################################################
    # Process the 'Underline Names' checkbox
    # ##################################################################################
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
        self.underline = self.get_input_and_put_message(self.underline_checkbox, "Display Names Underlined")

    # ##################################################################################
    # Process the 'Taskernet' checkbox
    # ##################################################################################
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
        self.taskernet = self.get_input_and_put_message(self.taskernet_checkbox, "Display TaskerNet Information")

    # ##################################################################################
    # Process the 'Runtime' checkbox
    # ##################################################################################
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
        self.runtime = self.get_input_and_put_message(self.runtime_checkbox, "Display Runtime Settings")

    # ##################################################################################
    # Rebuilld message box with new text (e.g. for Help).
    # ##################################################################################
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
        self.textbox = customtkinter.CTkTextbox(self, height=600, width=250)
        self.textbox.configure(scrollbar_button_color="#6563ff", wrap="word")
        self.textbox.grid(row=0, column=1, padx=(20, 0), pady=(20, 0), sticky="ew")
        # Insert the text.
        self.textbox.insert("0.0", message)
        # Set read-only, color, wrap around and font
        self.textbox.configure(state="disabled", font=(self.font, 14), wrap="word")
        # Display some colored text
        # self.textbox.insert('end', 'This is some colored text.\n')
        self.textbox.tag_add(
            "color",
            "1.0",
            f"1.{len(message)}",
        )  # '1.5' means first line, 5th character; '1.11' means first line, 11th character
        self.textbox.tag_config("color", foreground="green")
        self.all_messages = ""

    # ##################################################################################
    # Process the 'Display Help' button
    # ##################################################################################
    def help_event(self) -> None:
        """Displays help information in a message box.
        Args:
            self: The class instance.
        Returns:
            None: Does not return anything.
        - Constructs a message with help text information
        - Opens a new message box window
        - Displays the help message text in the message box"""
        self.new_message_box(HELP)

    # ##################################################################################
    # Process the 'Get Backup Help' button
    # ##################################################################################
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
        self.new_message_box("Fetch Backup Help\n\n" + BACKUP_HELP_TEXT)

    # ##################################################################################
    # Process the '?' List XML Files query button
    # ##################################################################################
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
        self.new_message_box("List XML Files Help\n\n" + LISTFILES_HELP_TEXT)

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
        self.display_message_box(f"{toggle_name} set{extra}{response}", True)

    # ##################################################################################
    # Process the 'Save Settings' checkbox
    # ##################################################################################
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
        """
        Saves program settings from GUI to file.
        Args:
            self: The class instance.
        Returns:
            None
        - Get program arguments from GUI and store in a temporary dictionary
        - Save the arguments in the temporary dictionary to file
        - Display confirmation message box"""
        temp_args = {value: getattr(self, value) for value in ARGUMENT_NAMES}

        # Save the arguments in the temporary dictionary
        temp_args, self.color_lookup = save_restore_args(temp_args, self.color_lookup, True)
        self.display_message_box("Settings saved.", True)

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

    # ##################################################################################
    # Restore displays setting from restored value!
    # ##################################################################################
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
        message_map = {
            "android_ipaddrt": lambda: f"Get XML TCP IP Address set to {value}\n",
            "android_port": lambda: f"Get XML Port Number set to {value}\n",
            "android_file": lambda: f"Get XML File Location set to {value}\n",
            "appearance_mode": lambda: f"Appearance mode set to {value}.\n",
            "bold": lambda: self.select_deselect_checkbox(self.bold_checkbox, value, "Display Names in Bold"),
            "conditions": lambda: self.select_deselect_checkbox(
                self.condition_checkbox,
                value,
                "Display Profile/Task Conditions",
            ),
            "debug": lambda: self.select_deselect_checkbox(self.debug_checkbox, value, "Debug Mode"),
            "directory": lambda: self.select_deselect_checkbox(self.directory_checkbox, value, "Display Directory"),
            "display_detail_level": lambda: self.detail_selected_event(value),
            "fetched_backup_from_android": lambda: f"Fetched XML From Android:{value}.\n",
            "file": lambda: f"Get XML file named '{value}'.\n",
            "font": lambda: f"Font set to {value}.\n",
            "highlight": lambda: self.select_deselect_checkbox(
                self.highlight_checkbox,
                value,
                "Display Names Highlighted",
            ),
            "indent": lambda: self.indent_selected_event(value),
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
        if key in {"gui", "save", "restore", "rerun"}:
            message = ""
            # Check if key is an attribute on self before setting
            if hasattr(self, key):
                setattr(self, key, value)
        else:
            # Use dictionary lookup anmd lambda funtion to process key/value
            message_func = message_map.get(key)
            if message_func:
                message = message_func()

        return message

    # ##################################################################################
    # Process the 'Restore Settings' checkbox
    # ##################################################################################
    def restore_settings_event(self) -> None:
        """
        Resets settings to defaults and restores from saved settings file
        Args:
            self: The class instance
        Returns:
            None: No value is returned
        Processing Logic:
            - Reset all values to defaults
            - Restore saved settings from file
            - Check for errors and display messages
            - Extract restored settings into class attributes
            - Empty message queue after restoring
        """
        self.set_defaults(False)  # Reset all values
        temp_args = self.color_lookup = {}
        # Restore all changes that have been saved
        temp_args, self.color_lookup = save_restore_args(temp_args, self.color_lookup, False)
        # Check for errors
        with contextlib.suppress(KeyError):
            if temp_args["msg"]:
                self.display_message_box(temp_args["msg"], False)
                temp_args["msg"] = ""
                return
        # Restore progargs values
        if temp_args or self.color_lookup:
            self.extract_settings(temp_args)
            self.restore = True
        else:  # Empty?
            self.display_message_box("No settings file found.", False)
        # Empty message queue so we don't fill it up (causes as display text problem)
        self.all_messages = ""

    # ##################################################################################
    # We have read colors and runtime args from backup file.  Now extract them for use.
    # ##################################################################################
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
        all_messages, new_message = "", ""
        self.all_messages = ""
        for key, value in temp_args.items():
            if key is not None:
                setattr(self, key, value)
                if new_message := self.restore_display(key, value):
                    all_messages = f"{all_messages}{new_message}"
        # Display the restored color changes, using the reverse dictionary of
        #   TYPES_OF_COLOR_NAMES (found in sysconst.py)
        inv_color_names = {v: k for k, v in TYPES_OF_COLOR_NAMES.items()}
        for key, value in self.color_lookup.items():
            if key is not None:
                if key == "msg":
                    inv_color_names[key] = ""
                else:
                    with contextlib.suppress(KeyError):
                        all_messages = f"{all_messages} {inv_color_names[key]} color set to {value}\n"

        # Display the queue of messages
        self.display_message_box(f"{all_messages}\nSettings restored.", True)

    # ##################################################################################
    # Display an input field and a label for the user to input a value
    # ##################################################################################
    def display_label_and_input(
        self,
        label: str,
        default_value: str,
        starting_row: int,
        indentation_x_label: int,
        indentation_y_label: int,
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
            padx=(0, indentation_x_label),
            pady=(indentation_y_label, 5),
            sticky="ne",
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
            next_row = starting_row + 1
            # If file location, we have to push line up by 1 for some reason.
            if next_row == 10:
                next_row = 9
                sticky = "se"
            else:
                sticky = "ne"
            input_name.grid(
                row=next_row,
                column=1,
                columnspan=1,
                padx=(0, 80),
                pady=(0, 0),
                sticky=sticky,
            )
        return input_name, label_name

    # ##################################################################################
    # Process the 'Backup' IP Address/port/file location
    # ##################################################################################
    def get_backup_event(self) -> None:
        # Set up default values
        """
        Gets backup event details from user.
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
        # First clear out any entries we may already have filled in.
        clear_android_buttons(self)
        ###  TCP/IP Address ###
        if self.android_ipaddr == "" or self.android_ipaddr is None:
            self.android_ipaddr = "192.168.0.210"
        self.ip_entry = self.ip_label = None
        self.ip_entry, self.ip_label = self.display_label_and_input(
            "1-TCP/IP Address:",
            self.android_ipaddr,
            7,
            100,
            30,
            self.ip_entry,
            self.ip_label,
            True,
        )

        ### Port Number ###
        if self.android_port == "" or self.android_port is None:
            self.android_port = "1821"
        self.port_entry = self.port_label = None
        self.port_entry, self.port_label = self.display_label_and_input(
            "2-Port Number:",
            self.android_port,
            8,
            117,
            30,
            self.port_entry,
            self.port_label,
            True,
        )

        ###  File Location ###
        if self.android_file == "" or self.android_file is None:
            self.android_file = "/Tasker/configs/user/backup.xml".replace("/", PrimeItems.slash)
        self.file_entry = self.file_label = None
        self.file_entry, self.file_label = self.display_label_and_input(
            "3-File Location:",
            self.android_file,
            9,
            119,
            40,
            self.file_entry,
            self.file_label,
            True,
        )

        # Add Cancel button
        self.cancel_entry_button = customtkinter.CTkButton(
            self,
            fg_color="#246FB6",
            border_width=2,
            text="Cancel Entry",
            command=self.backup_cancel_event,
        )
        self.cancel_entry_button.configure(
            # width=320,
            fg_color="#246FB6",
            border_color="#1bc9ff",
        )
        self.cancel_entry_button.grid(row=8, column=1, columnspan=2, padx=(80, 220), pady=(0, 0), sticky="ne")

        # Add 'List XML Files' button
        self.list_files_button = customtkinter.CTkButton(
            self,
            fg_color="#246FB6",
            border_width=2,
            text="List XML Files",
            command=self.list_files_event,
        )
        self.list_files_button.configure(
            # width=320,
            fg_color="#246FB6",
            border_color="#1bc9ff",
            text_color=("#0BF075", "#1AD63D"),
        )
        self.list_files_button.grid(row=9, column=1, columnspan=2, padx=(0, 220), pady=(0, 0), sticky="se")

        # Add ...or... label.
        self.label_or = customtkinter.CTkLabel(
            master=self,
            text="...or...",
            anchor="sw",
        )
        self.label_or.grid(
            row=9,
            column=1,
            columnspan=1,
            padx=(0, 38),
            pady=(0, 0),
            sticky="se",
        )

        #  Query ? button
        self.list_files_query_button = customtkinter.CTkButton(
            self,
            fg_color="#246FB6",
            border_width=1,
            text="?",
            width=20,
            command=self.listfile_query_event,
        )
        self.list_files_query_button.configure(
            fg_color="#246FB6",
            border_color="#1bc9ff",
            text_color=("#0BF075", "#ffd941"),
        )
        self.list_files_query_button.grid(row=9, column=1, columnspan=2, padx=(0, 180), pady=(0, 0), sticky="se")

        # Replace backup button.
        self.get_backup_button = self.display_backup_button(
            "Enter 1-3 and Click Here to Set XML Details",
            "#D62CFF",
            "#6563ff",
            self.fetch_backup_event,
        )
        self.get_backup_button.configure(anchor="center", width=600)

    # ##################################################################################
    # Fetch Backup info error...process it.
    # ##################################################################################
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
            self.display_message_box(
                error_message,
                False,
            )

    # ##################################################################################
    # Fetch the backup ip and file details, and validate.
    # This function can be entered through two paths:
    # 1- User clicked on the 'Get Backup Settings' button
    # 2- User clicked on the 'List XML Files' button
    # ##################################################################################
    def fetch_backup_event(self) -> None:
        """Fetches backup event details from user input

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
            self.display_message_box(error_msg, False)
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

        # If we got a good return from getting ther XML filelist, then return to process it.
        if return_code == 2:
            return

        # All is well.  Save the info, restore the button and get rid of the input fields.
        self.android_ipaddr = android_ipaddr
        self.android_port = android_port
        if not self.list_files:
            self.android_file = android_file
        clear_android_buttons(self)
        self.display_message_box(
            (
                f"\n\nGet XML IP Address set to: {self.android_ipaddr}\n\nPort"
                f" Number set to: {self.android_port}\n\nGet"
                f" Location set to: {self.android_file}"
                f"\n\nXML file will be fetched when 'Run' is selected."
            ),
            True,
        )

        # Display backup details as a label again.
        self.display_backup_details()

    # ##################################################################################
    # Fetching backup from Android.  Let the user know the specific details.
    # ##################################################################################
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
        self.ip_label = self.port_label = self.file_label = None
        self.ip_label = add_label(
            self,
            self,
            "Getting XML file from Android device:",
            "",
            12,
            "normal",
            7,
            1,
            (30, 0),
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
            8,
            1,
            (60, 0),
            (0, 50),
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
            8,
            1,
            (60, 0),
            (0, 50),
            "ne",
        )

    # ##################################################################################
    # Cancel the entry of backup parameters
    # ##################################################################################
    def backup_cancel_event(self) -> None:
        """
        Closes the backup details window.
        Args:
            self: The class instance
        Returns:
            None
        """
        clear_android_buttons(self)
        self.fetched_backup_from_android = False
        self.android_file = ""
        self.android_ipaddr = ""
        self.android_port = ""
        self.display_message_box("Get XML Details Cancelled.", True)

    # ##################################################################################
    # List files event
    # ##################################################################################
    def list_files_event(self) -> None:
        """
        Closes the backup details window.
        Args:
            self: The class instance
        Returns:
            None
        """
        self.list_files = True
        self.list_files_button.configure(text="List Files Selected")
        self.fetch_backup_event()

    # ##################################################################################
    # User has selected a specific XML file from pulldown menu.
    # ##################################################################################
    def file_selected_event(self, android_file: str) -> None:
        """User has selected a specific XML file from pulldown menu.
        Returns:
            - None: Adds android_file to file_list."""
        self.android_file = android_file
        clear_android_buttons(self)
        self.display_message_box(
            (
                f"\n\nGet XML IP Address set to: {self.android_ipaddr}\n\nPort"
                f" Number set to: {self.android_port}\n\nGet"
                f" Location set to: {self.android_file}"
                f"\n\nXML file will be fetched when 'Run' is selected."
            ),
            True,
        )

        # Validate XML file.add
        return_code, error_message = validate_xml_file(self.android_ipaddr, self.android_port, android_file)

        if return_code > 0:
            self.display_message_box(error_message, False)  # Error out and exit
            return

        # Display backup details as a label again.
        self.display_backup_details()

    # ##################################################################################
    # Process the 'Reset Settings' button
    # ##################################################################################
    def reset_settings_event(self) -> None:
        """
        Resets all class settings to default values.
        Args:
            self: The class instance.
        Returns:
            None
        """
        clear_android_buttons(self)
        self.android_ipaddr = ""
        self.android_port = ""
        self.android_file = ""
        self.sidebar_detail_option.set("3")  # display detail level
        self.indent_option.set("4")  # Indentation amount
        self.condition_checkbox.deselect()  # Conditions
        self.preferences_checkbox.deselect()  # Tasker Preferences
        self.taskernet_checkbox.deselect()  # TaskerNet
        self.appearance_mode_optionemenu.set("System")  # Appearance
        customtkinter.set_appearance_mode("System")  # Enforce appearance
        self.debug_checkbox.deselect()  # Debug
        self.display_message_box("Settings reset.", True)
        self.twisty_checkbox.deselect()  # Twisty
        self.directory_checkbox.deselect()  # directory
        self.bold_checkbox.deselect()  # bold
        self.italicize_checkbox.deselect()  # italicize
        self.highlight_checkbox.deselect()  # highlight
        self.underline_checkbox.deselect()  # underline
        self.runtime_checkbox.deselect()  # Display runtime
        self.outline_checkbox.deselect()  # Display outline
        self.everything_checkbox.deselect()  # Display everything
        if self.color_labels:  # is there any color text?
            for label in self.color_labels:
                label.configure(text="")
        self.set_defaults(False)  # Reset all defaults

    # ##################################################################################
    # Process Debug Mode checkbox
    # ##################################################################################
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
        self.debug = self.debug_checkbox.get()
        if self.debug:
            if Path("backup.xml").is_file():
                self.display_message_box("Debug mode enabled.", True)
            else:
                self.display_message_box(
                    ("Debug mode requires Tasker XML file to be named: 'backup.xml', which is missing!"),
                    False,
                )
                self.debug = False
        else:
            self.display_message_box("Debug mode disabled.", True)

    # ##################################################################################
    # User has requested that the colors be result to their defaults.
    # ##################################################################################
    def color_reset_event(self) -> None:
        """Resets the color mode for Tasker items.
        Parameters:
            - self (object): The current instance of the class.
        Returns:
            - None: This function does not return anything.
        Processing Logic:
            - Resets color mode for Tasker items.
            - Sets color mode to default.
            - Displays message box to confirm reset.
            - Destroys color change window."""
        PrimeItems.colors_to_use = set_color_mode(self.appearance_mode)
        self.color_lookup = {}
        self.display_message_box("Tasker items set back to their default colors.", True)
        with contextlib.suppress(Exception):
            self.color_change.destroy()

    # ##################################################################################
    # The 'Run' program button has been pressed.  Set the run flag and close the GUI
    # ##################################################################################
    def run_program(self) -> None:
        """
        Starts a program and displays a message box.
        Args:
            self: The class instance.
        Returns:
            None: Does not return anything.
        - Sets the go_program attribute to True to start the program
        - Displays a message box with the text "Program running..." and blocks user interaction
        - Calls the quit() method to exit the program"""
        self.go_program = True
        self.rerun = False
        self.display_message_box("Program running...", True)
        self.quit()

    # ##################################################################################
    # The 'ReRun' program button has been pressed.  Set the run flag and close the GUI
    # ##################################################################################
    def rerun_the_program(self) -> None:
        """
        Resets the program state and exits.
        Args:
            self: The class instance.
        Returns:
            None: Does not return anything.
        - Sets the rerun flag to True to restart the program on next run
        - Calls withdraw() to reset the program state
        - Calls quit() twice to ensure program exits"""
        self.rerun = True
        self.withdraw()
        self.quit()
        self.quit()

    # ##################################################################################
    # The Upgrade Version button has been pressed.
    # ##################################################################################
    def upgrade_event(self) -> None:
        """ "Runs an update and reruns the program."
        Parameters:
            - self (object): Instance of the class.
        Returns:
            - None: No return value.
        Processing Logic:
            - Calls the update function.
            - Reruns the program to pick up the update."""
        update()
        self.display_message_box("Program updated.  Restarting...", True)
        # Create the Change Log file to be read and displayed after a program update.
        create_changelog()
        do_rerun()

    # ##################################################################################
    # The Upgrade Version button has been pressed.
    # ##################################################################################
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
        try:
            webbrowser.open(f"https:{PrimeItems.slash*2}{url}", new=2)
        except webbrowser.Error:
            self.display_message_box("Error: Failed to open output in browser: your browser is not supported.", False)
            return
        self.new_message_box("Report an Issue or Request a Feature\n\n" + issue_text)

    # ##################################################################################
    # The 'Exit' program button has been pressed.  Call it quits
    # ##################################################################################
    def exit_program(self) -> None:
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
        self.exit = True
        self.quit()
        self.quit()
