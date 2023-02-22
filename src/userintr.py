#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# userintr: provide GUI and process input for program arguments                              #
#                                                                                            #
# Add the following statement (without quotes) to your Terminal Shell configuration file     #
#  (BASH, Fish, etc.) to eliminate the runtime msg:                                          #
#  DEPRECATION WARNING: The system version of Tk is deprecated ...                           #
#  "export TK_SILENCE_DEPRECATION = 1"                                                       #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #
import customtkinter

from CTkColorPicker.ctk_color_picker import AskColor
from maptasker.src.getputarg import save_restore_args
from maptasker.src.sysconst import TYPES_OF_COLOR_NAMES

customtkinter.set_appearance_mode(
    "System"
)  # Modes: "System" (standard), "Dark", "Light"
customtkinter.set_default_color_theme(
    "blue"
)  # Themes: "blue" (standard), "green", "dark-blue"
INFO_TEXT = (
    'MapTasker displays your Android Tasker configuration based on your uploaded Tasker backup file (e.g. "backup.xml").  The display '
    "will optionally include all Projects, Profiles, Tasks and their actions, Profile/Task conditions and other Profile/Task"
    "related information.\n\n"
    "* Display options are:\n"
    "    Level 0: display first Task action only, for unnamed Tasks only (silent)\n"
    "    Level 1 = display all Task action details for unknown Tasks only (default)\n"
    "    Level 2 = display full Task action name on every Task\n"
    "    Level 3 = display full Task action details on every Task with action details\n\n"
    "* Display Conditions: Turn on the display of Profile and Task conditions.\n\n"
    "* Display TaskerNet Info - If available, display TaskerNet publishing information\n\n"
    "* Save Settings - Save these settings for later use.\n\n"
    "* Restore Settings - Restore the settings from a previously saved session.\n\n"
    "* GUI Appearance Mode: Dark, Light, or System default.\n\n"
    "* Reset Options: Clear everything and start anew.\n\n"
    "* Run: Run the program with the settings provided.\n\n"
    "* Specific Name tab: enter a single, specific named item to display...\n"
    "   - Project Name: enter a specific Project to display\n"
    "   - Profile Name: enter a specific Profile to display\n"
    "   - Task Name: enter a specific Task to display\n"
    "   (These three are exclusive: enter one only)\n\n"
    "* Colors tab: select colors for various elements of the display\n"
    "              (e.g. color for Projects, Profiles, Tasks, etc.)\n\n"
    "* Exit: Exit the program (quit).\n\n"
    "Note: You will be prompted to identify your Tasker backup file once\n"
    "      you hit the 'Run' button"
)


# #######################################################################################
# Class to define the GUI configuration
# #######################################################################################
class MyGui(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        # configure window
        self.title("MapTasker Runtime Options")
        self.geometry("1100x580")

        # configure grid layout (4x4)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure((2, 3), weight=0)
        self.grid_rowconfigure((0, 1, 2), weight=1)

        # create sidebar frame with widgets
        self.sidebar_frame = customtkinter.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=6, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(6, weight=1)
        self.logo_label = customtkinter.CTkLabel(
            self.sidebar_frame,
            text="MapTasker",
            font=customtkinter.CTkFont(size=20, weight="bold"),
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Display Detail Level
        self.detail_label = customtkinter.CTkLabel(
            self.sidebar_frame, text="Display Detail Level:", anchor="w"
        )
        self.detail_label.grid(row=1, column=0, padx=20, pady=(10, 0))
        self.sidebar_detail_option = customtkinter.CTkOptionMenu(
            self.sidebar_frame,
            values=["0", "1", "2", "3"],
            command=self.detail_selected_event,
        )
        self.sidebar_detail_option.grid(row=2, column=0, padx=20, pady=(10, 0))

        # Display 'Condition' button
        self.condition_button = customtkinter.CTkCheckBox(
            self.sidebar_frame,
            command=self.condition_event,
            text="Display Conditions",
            onvalue=True,
            offvalue=False,
        )
        self.condition_button.grid(row=3, column=0, padx=20, pady=10, sticky="w")

        # Display 'TaskerNet' button
        self.display_taskernet_button = customtkinter.CTkCheckBox(
            self.sidebar_frame,
            command=self.display_taskernet_event,
            text="Display TaskerNet Info",
            onvalue=True,
            offvalue=False,
        )
        self.display_taskernet_button.grid(
            row=4, column=0, padx=20, pady=10, sticky="w"
        )

        # Save settings button
        self.save_settings_button = customtkinter.CTkButton(
            self.sidebar_frame,
            border_color="#6563ff",
            border_width=2,
            text="Save Settings",
            command=self.save_settings_event,
        )
        self.save_settings_button.grid(row=5, column=0, padx=20, pady=10, sticky="n")

        # Restore settings button
        self.restore_settings_button = customtkinter.CTkButton(
            self.sidebar_frame,
            border_color="#6563ff",
            border_width=2,
            text="Restore Settings",
            command=self.restore_settings_event,
        )
        self.restore_settings_button.grid(row=6, column=0, padx=20, pady=10, sticky="n")

        # Screen Appearance: Light / Dark / System
        self.appearance_mode_label = customtkinter.CTkLabel(
            self.sidebar_frame, text="GUI Appearance Mode:", anchor="w"
        )
        self.appearance_mode_label.grid(row=7, column=0, padx=20)
        self.appearance_mode_optionemenu = customtkinter.CTkOptionMenu(
            self.sidebar_frame,
            values=["Light", "Dark", "System"],
            command=self.change_appearance_mode_event,
        )
        self.appearance_mode_optionemenu.grid(row=8, column=0, padx=0, sticky="n")

        # 'Reset Settings' button definition
        self.reset_button = customtkinter.CTkButton(
            master=self,
            fg_color="#246FB6",
            border_width=2,
            text="Reset Options",
            command=self.reset_settings_event,
        )
        self.reset_button.grid(
            row=6, column=0, padx=(20, 20), pady=(20, 20), sticky="nsew"
        )

        # 'Run' button definition
        self.run_button = customtkinter.CTkButton(
            master=self,
            fg_color="#246FB6",
            border_width=2,
            text="Run",
            command=self.run_program,
            text_color=("#0BF075", "#1AD63D"),
        )
        self.run_button.grid(
            row=7, column=0, padx=(20, 20), pady=(20, 20), sticky="nsew"
        )

        # 'Exit' button definition
        self.exit_button = customtkinter.CTkButton(
            master=self,
            fg_color="#246FB6",
            border_width=2,
            text="Exit",
            command=self.exit_program,
            text_color="Red",
        )
        self.exit_button.grid(row=7, column=2, padx=(20, 20), pady=(20, 20))

        # create textbox for Help information
        self.textbox = customtkinter.CTkTextbox(self, height=100, width=250)
        self.textbox.configure(scrollbar_button_color="#6563ff")
        self.textbox.grid(row=0, column=1, padx=(20, 0), pady=(20, 0), sticky="nsew")

        # create tabview for Name, Color and Debug
        self.tabview = customtkinter.CTkTabview(
            self, width=250, segmented_button_fg_color="#6563ff"
        )
        self.tabview.grid(row=0, column=2, padx=(20, 0), pady=(20, 0), sticky="nsew")
        self.tabview.add("Specific Name")
        self.tabview.add("Colors")
        self.tabview.add("Debug")
        self.tabview.tab("Specific Name").grid_columnconfigure(
            0, weight=1
        )  # configure grid of individual tabs
        self.tabview.tab("Colors").grid_columnconfigure(0, weight=1)

        # Project Name
        self.string_input_button1 = customtkinter.CTkRadioButton(
            self.tabview.tab("Specific Name"),
            text="Project Name",
            command=self.single_project_name_event,
            fg_color="#6563ff",
            border_color="#1bc9ff",
        )
        self.string_input_button1.grid(
            row=1, column=0, padx=20, pady=(10, 10), sticky="nsew"
        )

        # Profile Name
        self.string_input_button2 = customtkinter.CTkRadioButton(
            self.tabview.tab("Specific Name"),
            text="Profile Name",
            command=self.single_profile_name_event,
            fg_color="#6563ff",
            border_color="#1bc9ff",
        )
        self.string_input_button2.grid(
            row=2, column=0, padx=20, pady=(10, 10), sticky="nsew"
        )

        # Task Name
        self.string_input_button3 = customtkinter.CTkRadioButton(
            self.tabview.tab("Specific Name"),
            text="Task Name",
            command=self.single_task_name_event,
            fg_color="#6563ff",
            border_color="#1bc9ff",
        )
        self.string_input_button3.grid(
            row=3, column=0, padx=20, pady=(10, 10), sticky="nsew"
        )

        # Prompt for the name
        self.name_label = customtkinter.CTkLabel(
            self.tabview.tab("Specific Name"), text="(Pick ONLY One)", anchor="w"
        )
        self.name_label.grid(row=4, column=0, padx=20, pady=(10, 10))

        # Setup to get various display colors
        self.label_tab_2 = customtkinter.CTkLabel(
            self.tabview.tab("Colors"), text="Set Various Display Colors Here"
        )
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
        self.textbox.configure(border_color="#6563ff")
        self.debug_checkbox.pack(padx=20, pady=10)

        # set default values
        self.set_defaults(True)

    # #######################################################################################
    # Set the value defaults
    # #######################################################################################
    def set_defaults(self, first_time: bool):
        self.sidebar_detail_option.configure(values=["0", "1", "2", "3"])
        self.sidebar_detail_option.set("1")
        self.display_detail_level = 1
        self.display_profile_conditions = False
        self.display_taskernet = False
        self.single_project_name = ""
        self.single_profile_name = ""
        self.single_task_name = ""
        self.color_text_row = 2
        self.debug = False
        self.clear_settings = False
        self.reset = False
        self.exit = False
        self.appearance_mode_optionemenu.set("Dark")
        self.color_labels = []
        self.appearance_mode = "System"
        if first_time:
            self.textbox.insert("0.0", "MapTasker Help\n\n" + INFO_TEXT)
        self.go_program = False
        self.color_lookup = {}  # Setup default dictionary as empty list

    # #######################################################################################
    # Display Error Box
    # #######################################################################################
    def display_error_box(self, error_message):
        self.textbox = customtkinter.CTkTextbox(self)
        self.textbox.grid(row=4, column=2, padx=10, pady=10)
        self.textbox.insert("0.0", error_message)  # insert at line 0 character 0
        self.text = self.textbox.get(
            "0.0", "end"
        )  # get text from line 0 character 0 till the end
        self.textbox.configure(
            state="disabled", text_color="Red"
        )  # configure textbox to be read-only
        self.textbox.focus_set()

    # #######################################################################################
    # Display Message Box
    # #######################################################################################
    def display_message_box(self, message, good):
        color = 'Green' if good else 'Red'
        self.textbox = customtkinter.CTkTextbox(self)
        self.textbox.grid(row=4, column=1, padx=10, pady=10)
        self.textbox.insert("0.0", f"{message}\n")  # insert at line 0 character 0
        self.text = self.textbox.get(
            "0.0", "end"
        )  # get text from line 0 character 0 till the end
        self.textbox.configure(
            state="disabled", text_color=color
        )  # configure textbox to be read-only
        self.textbox.focus_set()

    # #######################################################################################
    # Validate name entered
    # #######################################################################################
    def check_name(self, the_name, element_name):
        error_message = ""
        if not the_name:
            error_message = (
                "Error:\n\nThe name entered for the " + element_name + " is blank!\n\n"
                "Try again."
            )
            self.named_item = False
        if self.single_project_name and self.single_profile_name:
            error_message = (
                "Error:\n\nYou have entered both a Project and a Profile name!\n\n"
                "Try again and only select one."
            )
        elif self.single_project_name and self.single_task_name:
            error_message = (
                "Error:\n\nYou have entered both a Project and a Task name!\n\n"
                "Try again and only select one."
            )
        elif self.single_profile_name and self.single_task_name:
            error_message = (
                "Error:\n\nYou have entered both a Profile and a Task name!\n\n"
                "Try again and only select one."
            )

        if error_message:
            self.display_error_box(error_message)

            (
                self.single_project_name,
                self.single_profile_name,
                self.single_task_name,
            ) = ("", "", "")
        else:
            self.display_message_box((f"Display only the '{the_name}' {element_name}"), True)

    # #######################################################################################
    # Process the Project Name entry
    # #######################################################################################
    def single_project_name_event(self):
        #  Clear any prior error message
        error_message = ""
        self.display_error_box(error_message)
        # Turn off Profile and Task buttons
        self.string_input_button2.deselect()
        self.string_input_button3.deselect()
        # Display prompt for name
        dialog = customtkinter.CTkInputDialog(
            text="Enter Project name:", title="Display Specific Project"
        )
        # Get the name
        self.single_project_name = dialog.get_input()
        # Validate the name
        self.check_name(self.single_project_name, "Project")

    # #######################################################################################
    # Process the Profile Name entry
    # #######################################################################################
    def single_profile_name_event(self):
        #  Clear any prior error message
        error_message = ""
        self.display_error_box(error_message)
        # Turn off Project and Task buttons
        self.string_input_button1.deselect()
        self.string_input_button3.deselect()
        # Display prompt for name
        dialog = customtkinter.CTkInputDialog(
            text="Enter Profile name:", title="Display Specific Profile"
        )
        # Get the name
        self.single_profile_name = dialog.get_input()
        # Validate the name
        self.check_name(self.single_profile_name, "Profile")

    # #######################################################################################
    # Process the Profile Name entry
    # #######################################################################################
    def single_task_name_event(self):
        #  Clear any prior error message
        error_message = ""
        self.display_error_box(error_message)
        # Turn off Project and Profile buttons
        self.string_input_button1.deselect()
        self.string_input_button2.deselect()
        # Display prompt for name
        dialog = customtkinter.CTkInputDialog(
            text="Enter Task name:", title="Display Specific Task"
        )
        # Get the name
        self.single_task_name = dialog.get_input()
        # Validate the name
        self.check_name(self.single_task_name, "Task")

    # #######################################################################################
    # Process the screen mode: dark, light, system
    # #######################################################################################
    def change_appearance_mode_event(self, new_appearance_mode: str):
        customtkinter.set_appearance_mode(new_appearance_mode)
        self.appearance_mode = new_appearance_mode

    # #######################################################################################
    # Process the Display Detail Level selection
    # #######################################################################################
    def detail_selected_event(self, display_detail: str):
        self.display_detail_level = display_detail

    # #######################################################################################
    # Process color selection
    # #######################################################################################
    def colors_event(self, color_selected_item: str):
        # Put up color picker and get the color
        pick_color = AskColor()  # Open the Color Picker
        color = pick_color.get()  # Get the color
        if color is not None:
            row = self.color_text_row
            print('color_selected_item:', color_selected_item, ' color:', color)
            self.color_lookup[
                TYPES_OF_COLOR_NAMES[color_selected_item]
            ] = color  # Add color for the selected item to our dictionary
            self.color_labels.append(
                customtkinter.CTkLabel(
                    self.tabview.tab("Colors"),
                    text=f"{color_selected_item} << color",
                    text_color=color,
                )
            )
            self.color_labels[-1].grid(
                row=self.color_text_row, column=0, padx=0, pady=0
            )
            self.color_text_row += 1
            self.display_message_box(f"{color_selected_item} color changed to {color}", True)

    # #######################################################################################
    # Process the 'conditions' checkbox
    # #######################################################################################
    def condition_event(self):
        self.display_profile_conditions = self.condition_button.get()

    # #######################################################################################
    # Process the 'taskernet' checkbox
    # #######################################################################################
    def display_taskernet_event(self):
        self.display_taskernet = self.display_taskernet_button.get()

    # #######################################################################################
    # Process the 'Save Settings' checkbox
    # #######################################################################################
    def save_settings_event(self):
        temp_args = {
            "display_detail_level": self.display_detail_level,
            "display_profile_conditions": self.display_profile_conditions,
            "display_taskernet": self.display_taskernet,
            "single_project_name": self.single_project_name,
            "single_profile_name": self.single_profile_name,
            "single_task_name": self.single_task_name,
            "debug": self.debug,
        }
        temp_args, self.color_lookup = save_restore_args(True, self.color_lookup, temp_args)
        self.display_message_box("Settings saved.", True)

    # #######################################################################################
    # Restore displays settings from restored values
    # #######################################################################################
    def restore_display(self, key, value):
        message = ''
        match key:
            case "debug":
                if value:
                    self.debug_checkbox.select()
                else:
                    self.debug_checkbox.deselect()
            case "display_detail_level":
                self.sidebar_detail_option.set(str(value))
            case "display_profile_conditions":
                if value:
                    self.condition_button.select()
                else:
                    self.condition_button.deselect()
            case "display_taskernet":
                if value:
                    self.display_taskernet_button.select()
                else:
                    self.display_taskernet_button.deselect()
            case "single_project_name":
                if value:
                    message = f"{message}Project set to {value}.\n"
            case "single_profile_name":
                if value:
                    message = f"{message}Profile set to {value}.\n"
            case "single_task_name":
                if value:
                    message = f"{message}Task set to {value}.\n"
            case _:
                self.display_message_box(f"Rutroh!  Undefined argument: {value}")
        return message

    # #######################################################################################
    # Process the 'Restore Settings' checkbox
    # #######################################################################################
    def restore_settings_event(self):
        self.set_defaults(False)  # Reset all values
        temp_args = {}
        # Restore all changes that have been saved
        temp_args, self.color_lookup = save_restore_args(
            False, self.color_lookup, temp_args
        )
        # Restore progargs values
        if temp_args or self.color_lookup:
            all_messages, new_message = '', ''
            for key, value in temp_args.items():
                if key is not None:
                    setattr(self, key, value)
                    if new_message := self.restore_display(key, value):
                        all_messages = all_messages + new_message
            # Display the restored color changes
            inv_color_names = {v: k for k, v in TYPES_OF_COLOR_NAMES.items()}
            for key, value in self.color_lookup.items():
                if key is not None:
                    all_messages = f"{all_messages} {inv_color_names[key]} color set to {value}\n"
            # Display the queue of messages
            self.display_message_box(f"{all_messages}\nSettings restored.", True)

        else:  # Empty?
            self.display_message_box("No settings file found.", False)

    # #######################################################################################
    # Process the 'Reset Settings' button
    # #######################################################################################
    def reset_settings_event(self):
        self.sidebar_detail_option.set("1")  # display detail level
        self.condition_button.deselect()  # Conditions
        self.display_taskernet_button.deselect()  # TaskerNet
        self.appearance_mode_optionemenu.set("Dark")  # Appearance
        customtkinter.set_appearance_mode("Dark")  # Enforce appearance
        self.debug_checkbox.deselect()  # Debug
        self.display_message_box("Settings reset.", True)
        self.display_error_box("")
        if self.color_labels:  # is there any color text?
            for label in self.color_labels:
                label.configure(text="")
        self.set_defaults(False)  # Reset all defaults

    # #######################################################################################
    # Process Debug Mode checkbox
    # #######################################################################################
    def debug_checkbox_event(self):
        self.debug = self.debug_checkbox.get()
        self.display_message_box(
            "Debug mode requires Tasker backup file to be named: backup.xml", True
        )

    # #######################################################################################
    # The 'Run' program button has been pressed.  Set the run flag and close the GUI
    # #######################################################################################
    def run_program(self):
        self.go_program = True
        self.quit()

    # #######################################################################################
    # The 'Exit' program button has been pressed.  Call it quits
    # #######################################################################################
    def exit_program(self):
        self.exit = True
        self.quit()
