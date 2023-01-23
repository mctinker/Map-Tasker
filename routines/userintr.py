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
    "* Appearance Mode: Dark mode, Light mode, or System default mode.\n\n"
    "* Reset Options: Clear everything and start anew.\n\n"
    "* Run: Run the program with the settings provided.\n\n"
    "* Specific Name tab: enter a specific named item to display...\n"
    "   - Project Name: enter a specific Project to display\n"
    "   - Profile Name: enter a specific Profile to display\n"
    "   - Task Name: enter a specific Task to display\n\n"
    "* Colors tab: select colors for various elements of the display\n"
    "              (e.g. color for Projects, Profiles, Tasks, etc.)\n\n"
    "* Exit: Exit the program (quit).\n\n"
    "Note: You will be prompted to identify your Tasker backup file once\n"
    "      you hit the 'un' button"
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
            onvalue=1,
            offvalue=0,
        )
        self.condition_button.grid(row=3, column=0, padx=20, pady=10)

        # Screen Appearance: Light / Dark / System
        self.appearance_mode_label = customtkinter.CTkLabel(
            self.sidebar_frame, text="GUI Appearance Mode:", anchor="w"
        )
        self.appearance_mode_label.grid(row=5, column=0, padx=20)
        self.appearance_mode_optionemenu = customtkinter.CTkOptionMenu(
            self.sidebar_frame,
            values=["Light", "Dark", "System"],
            command=self.change_appearance_mode_event,
        )
        self.appearance_mode_optionemenu.grid(row=6, column=0, padx=0, sticky="n")

        # 'Reset Settings' button definition
        self.reset_button = customtkinter.CTkButton(
            master=self,
            fg_color="#246FB6",
            border_width=2,
            text="Reset Options",
            command=self.reset_settings_event,
            # command=lambda: self.destroy(),
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

        # create tabview
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
        self.string_input_button = customtkinter.CTkButton(
            self.tabview.tab("Specific Name"),
            text="Project Name",
            command=self.project_name_event,
        )
        self.string_input_button.grid(row=1, column=0, padx=20, pady=(10, 10))

        # Profile Name
        self.string_input_button = customtkinter.CTkButton(
            self.tabview.tab("Specific Name"),
            text="Profile Name",
            command=self.profile_name_event,
        )
        self.string_input_button.grid(row=2, column=0, padx=20, pady=(10, 10))

        # Task Name
        self.string_input_button = customtkinter.CTkButton(
            self.tabview.tab("Specific Name"),
            text="Task Name",
            command=self.task_name_event,
        )
        self.string_input_button.grid(row=3, column=0, padx=20, pady=(10, 10))

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
                "Bullet",
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
        self.conditions = False
        self.project_name = ""
        self.profile_name = ""
        self.task_name = ""
        self.color_text_row = 2
        self.debug_mode = False
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
    def display_message_box(self, message):
        self.textbox = customtkinter.CTkTextbox(self)
        self.textbox.grid(row=4, column=1, padx=10, pady=10)
        self.textbox.insert("0.0", message)  # insert at line 0 character 0
        self.text = self.textbox.get(
            "0.0", "end"
        )  # get text from line 0 character 0 till the end
        self.textbox.configure(
            state="disabled", text_color="Green"
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
        if self.project_name and self.profile_name:
            error_message = (
                "Error:\n\nYou have entered both a Project and a Profile name!\n\n"
                "Try again and only select one."
            )
        elif self.project_name and self.task_name:
            error_message = (
                "Error:\n\nYou have entered both a Project and a Task name!\n\n"
                "Try again and only select one."
            )
        elif self.profile_name and self.task_name:
            error_message = (
                "Error:\n\nYou have entered both a Profile and a Task name!\n\n"
                "Try again and only select one."
            )

        if error_message:
            self.display_error_box(error_message)
            self.display_message_box("")
            self.project_name, self.profile_name, self.task_name = "", "", ""
        else:
            self.display_message_box((f"Display only the '{the_name}' {element_name}"))

    # #######################################################################################
    # Process the Project Name entry
    # #######################################################################################
    def project_name_event(self):
        #  Clear any prior error message
        error_message = ""
        self.display_error_box(error_message)
        # Display prompt for name
        dialog = customtkinter.CTkInputDialog(
            text="Enter Project name:", title="Display Specific Project"
        )
        # Get the name
        self.project_name = dialog.get_input()
        # Validate the name
        self.check_name(self.project_name, "Project")

    # #######################################################################################
    # Process the Profile Name entry
    # #######################################################################################
    def profile_name_event(self):
        #  Clear any prior error message
        error_message = ""
        self.display_error_box(error_message)
        # Display prompt for name
        dialog = customtkinter.CTkInputDialog(
            text="Enter Profile name:", title="Display Specific Profile"
        )
        # Get the name
        self.profile_name = dialog.get_input()
        # Validate the name
        self.check_name(self.profile_name, "Profile")

    # #######################################################################################
    # Process the Profile Name entry
    # #######################################################################################
    def task_name_event(self):
        #  Clear any prior error message
        error_message = ""
        self.display_error_box(error_message)
        # Display prompt for name
        dialog = customtkinter.CTkInputDialog(
            text="Enter Task name:", title="Display Specific Task"
        )
        # Get the name
        self.task_name = dialog.get_input()
        # Validate the name
        self.check_name(self.task_name, "Task")

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
        self.display_detail = display_detail

    # #######################################################################################
    # Process color selection
    # #######################################################################################
    def colors_event(self, color_selected_item: str):
        # Put up color picker and get the color
        pick_color = AskColor()  # Open the Color Picker
        color = pick_color.get()  # Get the color
        if color is not None:
            row = self.color_text_row
            self.color_lookup[
                color_selected_item
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

    # #######################################################################################
    # Process the 'conditions' checkbox
    # #######################################################################################
    def condition_event(self):
        self.conditions = self.condition_button.get()

    # #######################################################################################
    # Process the 'Reset Settings' button
    # #######################################################################################
    def reset_settings_event(self):
        self.sidebar_detail_option.set("1")  # display detail level
        self.condition_button.deselect()  # Conditions
        self.appearance_mode_optionemenu.set("Dark")  # Appearance
        customtkinter.set_appearance_mode("Dark")  # Enforce appearance
        self.debug_checkbox.deselect()  # Debug
        self.display_message_box("")
        self.display_error_box("")
        if self.color_labels:  # is there any color text?
            for label in self.color_labels:
                label.configure(text="")
        self.set_defaults(False)  # Reset all defaults

    # #######################################################################################
    # Process Debug Mode checkbox
    # #######################################################################################
    def debug_checkbox_event(self):
        self.debug_mode = self.debug_checkbox.get()
        self.display_message_box(
            "Debug mode requires Tasker backup file to be named: backup.xml"
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