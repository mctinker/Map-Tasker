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
import os
from pathlib import Path
from tkinter import font

import customtkinter
from CTkColorPicker.ctk_color_picker import AskColor
from PIL import Image

from maptasker.src.colrmode import set_color_mode
from maptasker.src.config import OUTPUT_FONT
from maptasker.src.getputer import save_restore_args
from maptasker.src.lineout import LineOut
from maptasker.src.primitem import PrimeItems
from maptasker.src.proginit import get_data_and_output_intro
from maptasker.src.sysconst import ARGUMENT_NAMES, TYPES_OF_COLOR_NAMES

# Color Modes: "System" (standard), "Dark", "Light"
customtkinter.set_appearance_mode("System")
# Themes: "blue" (standard), "green", "dark-blue"
customtkinter.set_default_color_theme("blue")

# Help Text
INFO_TEXT = (
    "MapTasker displays your Android Tasker "
    "configuration based on your uploaded Tasker backup "
    "file (e.g. 'backup.xml'). The display will "
    "optionally include all Projects, Profiles, Tasks "
    "and their actions, Profile/Task conditions and "
    "other Profile/Task related information.\n\n"
    "* Display options are:\n"
    "    Level 0: display first Task action only, for "
    "unnamed Tasks only (silent).\n"
    "    Level 1 = display all Task action details for "
    "unknown Tasks only (default).\n"
    "    Level 2 = display full Task action name on "
    "every Task.\n"
    "    Level 3 = display full Task action details on "
    "every Task with action details.\n"
    "    Level 4 = display level of 3 plus Project's global variables.\n\n"
    "* Just Display Everything: Turns on the display of "
    "conditions, TaskerNet information, preferences, twisties, directory, "
    "and configuration outline.\n\n"
    "* Display Conditions: Turn on the display of "
    "Profile and Task conditions.\n\n"
    "* Display TaskerNet Info - If available, display "
    "TaskerNet publishing information.\n\n"
    "* Display Tasker Preferences - display Tasker's "
    "system Preferences.\n\n"
    "* Hide Task Details under Twisty: hide Task "
    "information within ► and click to display.\n\n"
    "* Display Directory of hyperlinks at beginning."
    "\n\n"
    "* Display Configuration Outline and Map of your Projects/Profiles/Tasks/Scenes."
    "\n\n"
    "* Project/Profile/Task/Scene Names options to "
    "italicize, bold, underline and/or highlight their "
    "names.\n\n"
    "* Indentation amount for If/Then/Else Task Actions.\n\n"
    "* Save Settings - Save these settings for later "
    "use.\n\n"
    "* Restore Settings - Restore the settings from a "
    "previously saved session.\n\n"
    "* Appearance Mode: Dark, Light, or System "
    "default.\n\n"
    "* Reset Options: Clear everything and start "
    "anew.\n\n"
    "* Font To Use: Change the monospace font used for the output.\n\n"
    "* Display Outline: Display Projects/Profiles/Tasks/Scenes configuration outline.\n\n"
    "* Get Backup from Android Device: fetch the backup "
    "xml file from device.  You will be asked for the IP address and port number for your"
    " Android device, as well as the file location on the device.\n\n"
    "* Run: Run the program with the settings "
    "provided and then exit.\n"
    "* ReRun: Run multiple times (each time with "
    "new settings) without exiting.\n\n"
    "* Specific Name tab: enter a single, specific "
    "named item to display...\n"
    "   - Project Name: enter a specific Project to "
    "display.\n"
    "   - Profile Name: enter a specific Profile to "
    "display.\n"
    "   - Task Name: enter a specific Task to "
    "display.\n"
    "   (These three are exclusive: enter one "
    "only)\n\n"
    "* Colors tab: select colors for various elements "
    "of the display.\n"
    "              (e.g. color for Projects, Profiles, "
    "Tasks, etc.).\n\n"
    "* Debug tab: Display Runtime Settings option and "
    "turn on Debug mode.\n\n"
    "* Exit: Exit the program (quit).\n\n"
    "Note: You will be prompted to identify your Tasker "
    "backup file once you hit the 'Run' button."
)
BACKUP_HELP_TEXT = (
    "The following steps aree required in order to fetch a Tasker backup file directly"
    " from your Android device.\n\n"
    "1- Both this device and the Android device must be on the same named network.\n\n"
    "2- The Tasker Project 'HTTP Server Example' or identical function must be"
    " installed and active on the Android device (the server must be running):\n\n"
    "https://taskernet.com/shares/?user=AS35m8ne7oO4s%2BaDx%2FwlzjdFTfVMWstg1ay5AkpiNdrLoSXEZdFfw1IpXiyJCVLNW0yn&id=Project%3AHttp+Server+Example\n\n"
    "You will be asked for the IP address and port number for your Android device,"
    " as well as the file location on the device.  The input format is...\n\n"
    "    'IP Address:Port Number,/path/to/file'\n\n"
    "The default value is for this field is: \n\n'192.168.0.210:1821,/Tasker/configs/user/backup.xml'\n\n,"
    "...where '192.168.0.210' is the IP address and '1821' is the port number for the Tasker HTTP"
    " Server Example running on your Android device.  The default file location of\n"
    " the Tasker backup file on the Android device is: '/Tasker/configs/user/backup.xml'.\n\n"
    "Usage Notes:\n\n"
    "The IP address and port can be obtained from your Android device by running the"
    " 'HTTP Server Example' Tasker Project on your Android device, and this will"
    " then issue the notification something like:\n\n"
    "HTTP Server Info\n"
    'Server info updated {"device name":"http://192.168.0.49:1821"}\n\n'
    "- To fetch the backup fille, click on the 'Get Backup from Android Device' button,"
    " modify the default value presented in the input field to the right, and then"
    " click on the button 'Enter and Click Here to Set >>=>'.\n\n"
    "- the Fetch backup settings are only used once the 'Run' button is pressed, but"
    " this program will try to ping your Android device to see if it is available"
    " once your enter the HTTP and file location values.  The ping will timeout after"
    " 10 seconds if the device is not reachable.  Check that the IP address is correct.\n\n"
)


# ##################################################################################
# Class to define the GUI configuration
# ##################################################################################
class MyGui(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        # configure window
        self.appearance_mode = None
        self.backup_file_http = None
        self.backup_file_location = None
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
        PrimeItems.program_arguments["gui"] = True

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

        # create sidebar frame with widgets
        self.sidebar_frame = customtkinter.CTkFrame(self, width=140, corner_radius=0)
        # self.sidebar_frame.configure(height=self._apply_window_scaling(800))
        self.sidebar_frame.grid(row=0, column=0, rowspan=13, sticky="nsew")
        # Define sidebar background frame with 14 rows
        self.sidebar_frame.grid_rowconfigure(14, weight=1)

        # Add our logo
        # Get the path to our logos
        current_dir = os.getcwd()
        abspath = os.path.abspath(__file__)
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
        self.logo_label = customtkinter.CTkLabel(
            self,
            image=my_image,
            text="",
            compound="left",
            font=customtkinter.CTkFont(size=1, weight="bold"),
        )  # display image with a CTkLabel
        self.logo_label.grid(row=0, column=0, padx=0, pady=0, sticky="n")

        # # Add the background image.
        # bg_image = customtkinter.CTkImage(
        #     Image.open("bg_gradient.jpg"),
        #     size=(self.width, self.height),
        # )
        # self.bg_image_label = customtkinter.CTkLabel(self, image=bg_image)
        # self.bg_image_label.grid(row=0, column=0)

        # Switch back to proper directory
        os.chdir(current_dir)

        # Add grid title
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

        # Everything
        self.everything_checkbox = customtkinter.CTkCheckBox(
            self.sidebar_frame,
            command=self.everything_event,
            text="Just Display Everything!",
            onvalue=True,
            offvalue=False,
        )
        self.everything_checkbox.grid(row=3, column=0, padx=20, pady=10, sticky="w")

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
            self.sidebar_frame, text="Project/Profile/Task/Scene Names:", anchor="s"
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
            self.sidebar_frame, text="If/Then/Else Indentation Amount:", anchor="s"
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
        fonts = self.get_fonts()
        font_items = ["Courier"]
        for key, value in fonts.items():
            if "Wingdings" not in value:
                font_items.append(value)
        self.font_optionemenu = customtkinter.CTkOptionMenu(
            master=self,
            values=font_items,
            command=self.font_event,
        )
        self.font_optionemenu.grid(row=7, column=1, padx=20, sticky="nw")

        # Save settings button
        self.save_settings_button = customtkinter.CTkButton(
            master=self,
            border_color="#6563ff",
            border_width=2,
            text="Save Settings",
            command=self.save_settings_event,
        )
        self.save_settings_button.grid(row=8, column=1, padx=20, pady=10, sticky="sw")

        # Restore settings button
        self.restore_settings_button = customtkinter.CTkButton(
            master=self,
            border_color="#6563ff",
            border_width=2,
            text="Restore Settings",
            command=self.restore_settings_event,
        )
        self.restore_settings_button.grid(row=9, column=1, padx=20, pady=10, sticky="nw")

        # 'Get Backup Settings' button definition
        self.get_backup_button = customtkinter.CTkButton(
            master=self,
            fg_color="#246FB6",
            border_color="#6563ff",
            border_width=2,
            text="Get Backup from Android Device",
            command=self.get_backup_event,
            text_color=("#0BF075", "#1AD63D"),
        )
        self.get_backup_button.grid(row=10, column=1, padx=10, pady=(20, 20), sticky="w")

        # 'Display Help' button definition
        self.help_button = customtkinter.CTkButton(
            master=self,
            fg_color="#246FB6",
            border_width=2,
            text="Display Help",
            command=self.help_event,
            text_color=("#0BF075", "#ffd941"),
        )
        self.help_button.grid(row=6, column=2, padx=(20, 20), pady=(20, 20), sticky="n")

        # 'Backup Help' button definition
        self.backup_help_button = customtkinter.CTkButton(
            master=self,
            fg_color="#246FB6",
            border_width=2,
            text="Get Backup Help",
            command=self.backup_help_event,
            text_color=("#0BF075", "#ffd941"),
        )
        self.backup_help_button.grid(row=7, column=2, padx=(20, 20), pady=(20, 20), sticky="n")

        # 'Run' button definition
        self.run_button = customtkinter.CTkButton(
            master=self,
            fg_color="#246FB6",
            border_width=2,
            text="Run",
            command=self.run_program,
            text_color=("#0BF075", "#1AD63D"),
        )
        self.run_button.grid(row=8, column=2, padx=(20, 20), pady=(20, 20))

        # 'ReRun' button definition
        self.rerun_button = customtkinter.CTkButton(
            master=self,
            fg_color="#246FB6",
            border_width=2,
            text="ReRun",
            command=self.rerun_the_program,
            text_color=("#0BF075", "#1AD63D"),
        )
        self.rerun_button.grid(row=9, column=2, padx=(20, 20), pady=(20, 20))

        # 'Exit' button definition
        self.exit_button = customtkinter.CTkButton(
            master=self,
            fg_color="#246FB6",
            border_width=2,
            text="Exit",
            command=self.exit_program,
            text_color="Red",
        )
        self.exit_button.grid(row=10, column=2, padx=(20, 20), pady=(20, 20))

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
                "Bullets",
                "TaskerNet Information",
                "Tasker Preferences",
                "Highlight",
                "Heading",
            ],
            command=self.colors_event,
        )
        self.colors_optionemenu.grid(row=1, column=0, padx=20, pady=(10, 10))

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

        # set default values
        self.set_defaults(True)

    # ##################################################################################
    # Establish all of the default values used
    # ##################################################################################
    def set_defaults(self, first_time: bool):
        # Item names must be the same as their value in
        #  PrimeItems.program_arguments
        self.sidebar_detail_option.configure(values=["0", "1", "2", "3", "4"])
        self.sidebar_detail_option.set("4")
        self.display_detail_level = 4
        self.conditions = (
            self.preferences
        ) = (
            self.taskernet
        ) = (
            self.debug
        ) = (
            self.everything
        ) = (
            self.clear_settings
        ) = (
            self.reset
        ) = (
            self.restore
        ) = (
            self.exit
        ) = (
            self.bold
        ) = (
            self.highlight
        ) = (
            self.italicize
        ) = (
            self.underline
        ) = (
            self.go_program
        ) = (
            self.outline
        ) = (
            self.rerun
        ) = self.runtime = self.save = self.twisty = self.directory = self.fetched_backup_from_android = False
        self.single_project_name = self.single_profile_name = self.single_task_name = self.file = ""
        self.color_text_row = 2
        self.appearance_mode_optionemenu.set("System")
        self.appearance_mode = "system"
        self.indent_option.set("4")
        self.indent = 4
        self.color_labels = []
        if first_time:
            self.textbox.insert("0.0", "MapTasker Help\n\n" + INFO_TEXT)
            self.all_messages = ""
        self.color_lookup = {}  # Setup default dictionary as empty list
        self.font = OUTPUT_FONT
        self.gui = True
        self.color_row = 4

        # We only want to initialize the next two variables only if they have not yet
        # been defined.
        #  Ignore sourcery recommendation to reformat these!!
        # The following will fail with an attribute error if it does not already existis not set to display!
        try:
            if self.backup_file_http:
                pass
        except AttributeError:
            self.backup_file_http = ""
        try:
            if self.backup_file_location:
                pass
        except AttributeError:
            self.backup_file_location = ""
        # Display current Items setting.
        self.single_name_status("Display all Projects, Profiles, and Tasks.", "#3f99ff")

    # ##################################################################################
    # Display Message Box
    # ##################################################################################
    def display_message_box(self, message, good):
        # If "good", display in green.  Otherwise, must be bad and display in red.
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
        # insert at line 0 character 0
        self.textbox.insert("0.0", self.all_messages)
        # Set read-only, color, wrap around and font
        self.textbox.configure(state="disabled", text_color=color, wrap="word", font=(self.font, 14))
        self.textbox.focus_set()

    # ##################################################################################
    # Validate name entered
    # ##################################################################################
    def check_name(self, the_name, element_name):
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
                "Error:\n\nYou have entered both a Project and a Profile name!\n\n" "Try again and only select one."
            )
        elif self.single_project_name and self.single_task_name:
            error_message = (
                "Error:\n\nYou have entered both a Project and a Task name!\n\n" "Try again and only select one."
            )
        elif self.single_profile_name and self.single_task_name:
            error_message = (
                "Error:\n\nYou have entered both a Profile and a Task name!\n\n" "Try again and only select one."
            )
        # Make sure the named item exists
        elif not self.valid_item(the_name, element_name):
            error_message = f'Error: "{the_name}" {element_name} not found!!  Try again.'

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
        else:
            self.display_message_box(
                f"Display only the '{the_name}' {element_name} (overrides any previous set name).",
                True,
            )
            return True

    # ##################################################################################
    # Display single item status.
    # ##################################################################################
    def single_name_status(self, status_message, color_to_use):
        # Display The selection
        self.single_label = customtkinter.CTkLabel(
            self.tabview.tab("Specific Name"),
            text=status_message,
            anchor="w",
            text_color=("#0BF075", color_to_use),
        )
        self.single_label.grid(row=5, column=0, padx=20, pady=(10, 10), sticky="nsew")

    # ##################################################################################
    # Make sure the single named item exists...that it is a valid name
    # ##################################################################################
    def valid_item(self, the_name, element_name):
        # We need to get all tasker root xml items from the backup xml file.
        # To do so, we need to go through initializing a temporary PrimaryItems object
        """
        Checks if an item name is valid
        Args:
            the_name: String - Name to check
            element_name: String - Element type being checked
        Returns:
            Boolean - Whether the name is valid
        Processing Logic:
        - Initialize temporary primary items object
        - Get backup xml data and root elements
        - Match element type and get corresponding root element
        - Check if item name exists by going through all names in root element
        """

        # Set up just enough PrimeItems variables to validate name.
        if not PrimeItems.file_to_get:
            PrimeItems.file_to_get = "backup.xml" if self.debug else ""
        PrimeItems.program_arguments["debug"] = self.debug
        PrimeItems.colors_to_use = set_color_mode(self.appearance_mode)
        PrimeItems.output_lines = LineOut()
        return_code = get_data_and_output_intro()

        # Did we get an error reading the backlup file?
        if return_code > 0:
            error_msg = PrimeItems.error_msg.replace("  Program ended.", "")
            self.display_message_box(error_msg, False)
            PrimeItems.error_code = 0
            PrimeItems.error_msg = ""
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
        for item in root_element:
            if root_element[item]["name"] == the_name:
                return True

        return False

    # ##################################################################################
    # Process single name selection/event
    # ##################################################################################
    def process_name_event(
        self,
        my_name: str,
        checkbox1: customtkinter.CHECKBUTTON,
        checkbox2: customtkinter.CHECKBUTTON,
        checkbox3: customtkinter.CHECKBUTTON,
    ):
        #  Clear any prior error message.
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
    ):
        # Name sure it is a valid name
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
    def single_project_name_event(self):
        self.process_name_event(
            "Project",
            self.string_input_button2,
            self.string_input_button3,
            self.string_input_button1,
        )

    # ##################################################################################
    # Process the Profile Name entry
    # ##################################################################################
    def single_profile_name_event(self):
        self.process_name_event(
            "Profile",
            self.string_input_button1,
            self.string_input_button3,
            self.string_input_button2,
        )

    # ##################################################################################
    # Process the Task Name entry
    # ##################################################################################
    def single_task_name_event(self):
        self.process_name_event(
            "Task",
            self.string_input_button1,
            self.string_input_button2,
            self.string_input_button3,
        )

    # ##################################################################################
    # Process the screen mode: dark, light, system
    # ##################################################################################
    def change_appearance_mode_event(self, new_appearance_mode: str):
        customtkinter.set_appearance_mode(new_appearance_mode)
        self.appearance_mode = new_appearance_mode.lower()

    # ##################################################################################
    # Process the screen mode: dark, light, system
    # ##################################################################################
    def font_event(self, font_selected: str):
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
    def detail_selected_event(self, display_detail: str):
        self.display_detail_level = display_detail
        self.sidebar_detail_option.set(display_detail)
        self.inform_message("Display Detail Level", True, display_detail)
        # Disable twisty if detail level is less than 3
        if self.twisty and int(display_detail) < 3:
            self.display_message_box(
                f"Hiding Tasks with Twisty has no effect with Display Detail Level set to {display_detail}.  Twisty disabled!",
                False,
            )
            self.twisty = False
            self.twisty_checkbox.deselect()

    # ################################################################################
    # Select or deselect a checkbox based on the value passed in
    # ################################################################################
    def get_input_and_put_message(self, checkbox: customtkinter.CHECKBUTTON, title: str):
        checkbox_value = checkbox.get()
        self.inform_message(title, checkbox_value, "")
        return checkbox_value

    # ##################################################################################
    # Process the Identation Amount selection
    # ##################################################################################
    def indent_selected_event(self, ident_amount: str):
        self.indent = ident_amount
        self.indent_option.set(ident_amount)
        self.inform_message("Indentation Amount", True, ident_amount)

    # ##################################################################################
    # Process color selection
    # ##################################################################################
    def colors_event(self, color_selected_item: str):
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
            if self.color_row > 14:
                self.color_row = 4

    # ##################################################################################
    # Color selected...process it.
    # ##################################################################################
    def extract_color_from_event(self, color, color_selected_item):
        self.color_lookup[
            TYPES_OF_COLOR_NAMES[color_selected_item]
        ] = color  # Add color for the selected item to our dictionary

    # ##################################################################################
    # Process the 'conditions' checkbox
    # ##################################################################################
    def condition_event(self):
        self.conditions = self.get_input_and_put_message(
            self.condition_checkbox, "Display Profile and Task Action Conditions"
        )

    # ##################################################################################
    # Process the 'conditions' checkbox
    # ##################################################################################
    def outline_event(self):
        self.outline = self.get_input_and_put_message(self.outline_checkbox, "Display Configuration Outline")

    # ##################################################################################
    # Process the 'everything' checkbox
    # ##################################################################################
    def everything_event(self):
        # Dictionary of program arguments and function to run for each upon restoration.
        message_map = {
            "conditions": lambda: self.select_deselect_checkbox(
                self.condition_checkbox, value, "Display Profile/Task Conditions"
            ),
            "directory": lambda: self.select_deselect_checkbox(self.directory_checkbox, value, "Display Directory"),
            "outline": lambda: self.select_deselect_checkbox(
                self.outline_checkbox, value, "Display Configuration Outline"
            ),
            "preferences": lambda: self.select_deselect_checkbox(
                self.preferences_checkbox, value, "Display Tasker Preferences"
            ),
            "runtime": lambda: self.select_deselect_checkbox(self.runtime_checkbox, value, "Display Runtime Settings"),
            "taskernet": lambda: self.select_deselect_checkbox(
                self.taskernet_checkbox, value, "Display TaskerNet Information"
            ),
            "twisty": lambda: self.select_deselect_checkbox(
                self.twisty_checkbox, value, "Hide Task Details Under Twisty"
            ),
            "display_detail_level": lambda: self.detail_selected_event("4"),
        }

        self.everything = self.everything_checkbox.get()
        value = self.everything

        new_message = all_messages = ""
        for key in message_map:
            if message_func := message_map.get(key):
                new_message = f"{message_func()}"
                all_messages = f"{all_messages}{new_message}"
            # Check if key is an attribute on self before setting
            if hasattr(self, key) and key != "display_detail_level":
                setattr(self, key, value)

        # Handle Display Detail Level
        self.display_detail_level

        self.display_message_box(all_messages, True)

    # ##################################################################################
    # Process the 'Tasker Preferences' checkbox
    # ##################################################################################
    def preferences_event(self):
        self.preferences = self.get_input_and_put_message(self.preferences_checkbox, "Display Tasker Preferences")

    # ##################################################################################
    # Process the 'Twisty' checkbox
    # ##################################################################################
    def twisty_event(self):
        self.twisty = self.get_input_and_put_message(self.twisty_checkbox, "Hide Task Details Under Twisty")
        if self.twisty and int(self.display_detail_level) < 3:
            self.display_message_box(
                "This has no effect with Display Detail Level less than 3.  Display Detail Level set to 3!",
                False,
            )
            self.sidebar_detail_option.set("3")  # display detail level
            self.display_detail_level = "3"

    # ##################################################################################
    # Process the 'Display Directory' checkbox
    # ##################################################################################
    def directory_event(self):
        self.directory = self.get_input_and_put_message(self.directory_checkbox, "Display Directory")

    # ##################################################################################
    # Process the 'Bold Names' checkbox
    # ##################################################################################
    def names_bold_event(self):
        self.bold = self.get_input_and_put_message(self.bold_checkbox, "Display Names in Bold")

    # ##################################################################################
    # Process the 'Highlight Names' checkbox
    # ##################################################################################
    def names_highlight_event(self):
        self.highlight = self.get_input_and_put_message(self.highlight_checkbox, "Display Names Highlighted")

    # ##################################################################################
    # Process the 'Italicize Names' checkbox
    # ##################################################################################
    def names_italicize_event(self):
        self.italicize = self.get_input_and_put_message(self.italicize_checkbox, "Display Names Italicized")

    # ##################################################################################
    # Process the 'Underline Names' checkbox
    # ##################################################################################
    def names_underline_event(self):
        self.underline = self.get_input_and_put_message(self.underline_checkbox, "Display Names Underlined")

    # ##################################################################################
    # Process the 'Taskernet' checkbox
    # ##################################################################################
    def taskernet_event(self):
        self.taskernet = self.get_input_and_put_message(self.taskernet_checkbox, "Display TaskerNet Information")

    # ##################################################################################
    # Process the 'Runtime' checkbox
    # ##################################################################################
    def runtime_checkbox_event(self):
        self.runtime = self.get_input_and_put_message(self.runtime_checkbox, "Display Runtime Settings")

    # ##################################################################################
    # Rebuilld message box with new text.
    # ##################################################################################
    def new_message_box(self, message):
        # Clear any prior error message
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
            "color", "1.0", f"1.{len(message)}"
        )  # '1.5' means first line, 5th character; '1.11' means first line, 11th character
        self.textbox.tag_config("color", foreground="green")
        self.all_messages = ""

    # ##################################################################################
    # Process the 'Display Help' checkbox
    # ##################################################################################
    def help_event(self):
        self.new_message_box("MapTasker Help\n\n" + INFO_TEXT)

    # ##################################################################################
    # Process the 'Display Help' checkbox
    # ##################################################################################
    def backup_help_event(self):
        self.new_message_box("Fetch Backup Help\n\n" + BACKUP_HELP_TEXT)

    # ################################################################################
    # Inform user of toggle selection
    # ################################################################################
    def inform_message(self, toggle_name, toggle_value, number_value):
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
    def save_settings_event(self):
        # Get program arguments from GUI and store in a temporary dictionary
        temp_args = {value: getattr(self, value) for value in ARGUMENT_NAMES}

        # Save the arguments in the temporary dictionary
        temp_args, self.color_lookup = save_restore_args(temp_args, self.color_lookup, True)
        self.display_message_box("Settings saved.", True)

    # ################################################################################
    # Select or deselect a checkbox based on the value passed in
    # ################################################################################
    def select_deselect_checkbox(self, checkbox: customtkinter.CHECKBUTTON, checked: bool, argument_name: str):
        checkbox.select() if checked else checkbox.deselect()
        return f"{argument_name} set to {checked}.\n"

    # ##################################################################################
    # Restore displays setting from restored value!
    # ##################################################################################
    def restore_display(self, key, value):
        # Dictionary of program arguments and function to run for each upon restoration.
        message_map = {
            "appearance_mode": lambda: f"Appearance mode set to {value}.\n",
            "backup_file_http": lambda: f"Get Backup IP Address set to {value}\n",
            "backup_file_location": lambda: f"Get Backup File Location set to {value}\n",
            "bold": lambda: self.select_deselect_checkbox(self.bold_checkbox, value, "Display Names in Bold"),
            "conditions": lambda: self.select_deselect_checkbox(
                self.condition_checkbox, value, "Display Profile/Task Conditions"
            ),
            "debug": lambda: self.select_deselect_checkbox(self.debug_checkbox, value, "Debug Mode"),
            "directory": lambda: self.select_deselect_checkbox(self.directory_checkbox, value, "Display Directory"),
            "display_detail_level": lambda: self.detail_selected_event(value),
            "fetched_backup_from_android": lambda: f"Fetched Backup From Android:{value}.\n",
            "file": lambda: f"Get backup file named '{value}'.\n",
            "font": lambda: f"Font set to {value}.\n",
            "highlight": lambda: self.select_deselect_checkbox(
                self.highlight_checkbox, value, "Display Names Highlighted"
            ),
            "indent": lambda: self.indent_selected_event(value),
            "italicize": lambda: self.select_deselect_checkbox(
                self.italicize_checkbox, value, "Display Names Italicized"
            ),
            "outline": lambda: self.select_deselect_checkbox(
                self.outline_checkbox, value, "Display Configuration Outline"
            ),
            "preferences": lambda: self.select_deselect_checkbox(
                self.preferences_checkbox, value, "Display Tasker Preferences"
            ),
            "runtime": lambda: self.select_deselect_checkbox(self.runtime_checkbox, value, "Display Runtime Settings"),
            "single_profile_name": lambda: self.process_single_name_restore("Profile", value),
            "single_project_name": lambda: self.process_single_name_restore("Project", value),
            "single_task_name": lambda: self.process_single_name_restore("Task", value),
            "taskernet": lambda: self.select_deselect_checkbox(
                self.taskernet_checkbox, value, "Display TaskerNet Information"
            ),
            "twisty": lambda: self.select_deselect_checkbox(
                self.twisty_checkbox, value, "Hide Task Details Under Twisty"
            ),
            "underline": lambda: self.select_deselect_checkbox(
                self.underline_checkbox, value, "Display Names Underlined"
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
    def restore_settings_event(self):
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
                    all_messages = f"{all_messages} {inv_color_names[key]} color set to {value}\n"

        # Display the queue of messages
        self.display_message_box(f"{all_messages}\nSettings restored.", True)

    # ##################################################################################
    # Process the 'Backup' IP Address
    # ##################################################################################
    def get_backup_event(self):
        # Set up default values
        if self.backup_file_http == "" or self.backup_file_http is None:
            self.backup_file_http = "192.168.0.210:1821"

        if not self.backup_file_location:
            self.backup_file_location = "/Tasker/configs/user/backup.xml"

        # Create main entry field right next to backup button.
        self.entry = customtkinter.CTkEntry(
            self,
            placeholder_text=f"{self.backup_file_http},{self.backup_file_location}",
        )
        self.entry.configure(
            width=400,
            fg_color="#246FB6",
            border_color="#1bc9ff",
            text_color=("#0BF075", "#1AD63D"),
        )
        # Add a label over the main entry field.
        self.detail_label = customtkinter.CTkLabel(
            master=self,
            text="Enter Android Device IP Address/Port/Location:",
            anchor="s",
        )
        self.detail_label.grid(
            row=9,
            column=1,
            padx=(254, 0),
            pady=(20, 0),
            sticky="s",
        )
        # Insert the backup info for input by user.
        self.entry.insert(0, f"{self.backup_file_http},{self.backup_file_location}")
        self.entry.grid(
            row=10,
            column=1,
            columnspan=2,
            padx=(90, 0),
            pady=(20, 20),
            sticky="n",
        )
        # Replace backup button.
        self.get_backup_button = customtkinter.CTkButton(
            master=self,
            fg_color="#D62CFF",
            border_color="#6563ff",
            border_width=2,
            text="Enter and Click Here to Set >>=>",
            command=self.fetch_backup_event,
            text_color=("#0BF075", "#1AD63D"),
        )
        self.get_backup_button.grid(row=10, column=1, padx=10, pady=(20, 20), sticky="w")

    # ##################################################################################
    # Fetch Backup info error...process it.
    # ##################################################################################
    def backup_error(self, error_message):
        # Setup error message
        if error_message:
            self.display_message_box(
                error_message,
                False,
            )

            # Delete entry field by overlaying it.
            self.entry.delete(0, "end")

        # Reset 'Get Backup Settings' button definition
        self.get_backup_button = customtkinter.CTkButton(
            master=self,
            fg_color="#246FB6",
            border_color="#6563ff",
            border_width=2,
            text="Get Backup from Android Device",
            command=self.get_backup_event,
            text_color=("#0BF075", "#1AD63D"),
        )
        self.get_backup_button.grid(row=10, column=1, padx=10, pady=(20, 20), sticky="w")

    # ##################################################################################
    # Fetch the backup ip and file details, and validate.
    # ##################################################################################
    def fetch_backup_event(self):
        backup_info = self.entry.get()
        # User entered values other than default?
        if backup_info != "*":
            # The following should return a list: [ip_address:port_number, file_location]
            temp_info = backup_info.split(",")
            temp_ip = temp_info[0].split(":")

            # Validate IP Address
            temp_ipaddr = temp_ip[0].split(".")
            if len(temp_ipaddr) < 4:
                self.backup_error(f"Invalid IP Address: {temp_ip[0]}.  Try again.")
                return
            for item in temp_ipaddr[0]:
                if not item.isdigit():
                    self.backup_error(
                        f"Invalid IP Address: {temp_ip[0]}.  Try again.",
                    )
                    return
            # Verify that the host IP (temp_ip[0]) is reachable:
            self.display_message_box(
                f"Pinging address {temp_ip[0]}.  Please wait...",
                True,
            )
            MyGui.update(self)  # Force a window refresh.
            # Ping IP address.
            response = os.system("ping -c 1 -t50 > /dev/null " + temp_ip[0])
            if response != 0:
                self.backup_error(
                    f"{temp_ip[0]} is not reachable (error {response}).  Try again.",
                )
                return
            self.display_message_box(
                "Ping successful.",
                False,
            )
            # Validate port number
            if not temp_ipaddr[1].isdigit:
                self.backup_error(
                    f"Invalid port number: {temp_ipaddr[1]}.  Try again.",
                )
                return

            # Validate file location
            if len(temp_info) < 2:
                self.backup_error("File location is missing.  Try again.")
                return

            # All is well so far...
            self.backup_file_http = temp_info[0]
            self.backup_file_location = temp_info[1]

            # Empty message = good to go...no error.
            self.backup_error("")

        self.get_backup_button.grid(row=10, column=1, padx=10, pady=(20, 20), sticky="w")

        self.display_message_box(
            (
                f"Get Backup IP Address set to: {self.backup_file_http}\nGet"
                f" Location set to: {self.backup_file_location}"
            ),
            True,
        )

    # ##################################################################################
    # Process the 'Reset Settings' button
    # ##################################################################################
    def reset_settings_event(self):
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
        self.backup_file_location = self.backup_file_http = ""
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
    def debug_checkbox_event(self):
        self.debug = self.debug_checkbox.get()
        if self.debug:
            if Path("backup.xml").is_file():
                self.display_message_box("Debug mode enabled.", True)
            else:
                self.display_message_box(
                    ("Debug mode requires Tasker backup file to be named:" " 'backup.xml', which is missing!"),
                    False,
                )
                self.debug = False
        else:
            self.display_message_box("Debug mode disabled.", True)

    # ##################################################################################
    # Get all monospace fonts from TKInter
    # ##################################################################################
    def get_fonts(self):
        fonts = [font.Font(family=f) for f in font.families()]
        return {f.name: f.actual("family") for f in fonts if f.metrics("fixed")}

    # ##################################################################################
    # The 'Run' program button has been pressed.  Set the run flag and close the GUI
    # ##################################################################################
    def run_program(self):
        self.go_program = True
        self.display_message_box("Program running...", True)
        self.quit()

    # ##################################################################################
    # The 'ReRun' program button has been pressed.  Set the run flag and close the GUI
    # ##################################################################################
    def rerun_the_program(self):
        self.rerun = True
        self.withdraw()
        self.quit()
        self.quit()

    # ##################################################################################
    # The 'Exit' program button has been pressed.  Call it quits
    # ##################################################################################
    def exit_program(self):
        self.exit = True
        self.quit()
        self.quit()
