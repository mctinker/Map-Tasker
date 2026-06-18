"""Code to manage the graphical user interface using NiceGUI."""

import contextlib
import os
from collections.abc import Callable
from typing import TYPE_CHECKING

from nicegui import Event, ui

from maptasker.src.aiutils import get_api_key
from maptasker.src.bildhtml import build_html
from maptasker.src.config import AI_PROMPT, DEFAULT_DISPLAY_DETAIL_LEVEL, OUTPUT_FONT
from maptasker.src.getfile import Local_File_Picker
from maptasker.src.getids import get_ids
from maptasker.src.getputer import save_restore_args
from maptasker.src.guimap import parse_html
from maptasker.src.guiutils import (
    add_logo,
    build_profiles,
    clear_android_buttons,
    display_analyze_button,
    display_current_file,
    display_model_pulldown,
    display_selected_object_labels,
    get_xml,
    list_tasker_objects,
    reload_gui,
    reset_primeitems_single_names,
    set_tasker_object_names,
    update_tasker_object_menus,
    valid_item,
)
from maptasker.src.guiwins import (
    NiceGuiTextView,
    NiceGuiTreeView,
    create_appearance_mode_section,
    initialize_gui,
    initialize_screen,
)
from maptasker.src.guiwins2 import APIKeyDialog
from maptasker.src.mapit import mapit_all
from maptasker.src.maputil2 import log_startup_values, translate_string
from maptasker.src.maputils import (
    clear_tasker_data,
    make_hex_color,
)
from maptasker.src.primitem import PrimeItems, PrimeItemsReset
from maptasker.src.sysconst import (
    ARGUMENT_NAMES,
    TAB_NAMES,
    TYPES_OF_COLOR_NAMES,
    logger,
)
from maptasker.src.taskerd import get_the_xml_data

if TYPE_CHECKING:
    from maptasker.src.userintr import MyGui


all_objects = "Display all Projects, Profiles, and Tasks."


# We'll use a class to maintain your state, just like before,
# but it NO LONGER inherits from customtkinter.CTk
class MyGui:
    """Main UI Interface for MapTasker using NiceGUI."""

    def __init__(self: "MyGui") -> None:
        """Initialize the GUI and set up all necessary state and layout."""
        # # Trace code
        # PrimeItems.program_arguments["debug"] = True  # Set this to True to enable tracing
        # # Create the trace object (set trace=False to only get function names, not every line)
        # def trace_calls(frame, event, arg):
        #     if event == "call":
        #         func_name = frame.f_code.co_name
        #         file_name = frame.f_code.co_filename

        #         # Filter out standard library calls
        #         if "site-packages" not in file_name and "lib/python" not in file_name:
        #             # 2. Write to the file instead of the terminal
        #             logger.debug(f"CALL: {func_name}() in {file_name}\n")

        #     return trace_calls

        # # Enable the profiler
        # sys.setprofile(trace_calls)

        logger.info("Starting GUI")
        self.initialization = True

        # 1. Initialize settings and state
        initialize_gui(self)
        self.set_defaults()
        PrimeItems.mygui = self

        # 2. Attach Event Handlers
        self.event_handlers = MapTaskerEventHandlers(self)
        # 3. Build the UI Layout directly!
        try:
            initialize_screen(self)
        except Exception as e:  # noqa: BLE001
            ui.label(f"CRASH IN UI LAYOUT: {e}").classes("text-2xl text-red-500 m-8 font-mono")
            print("\n" + "=" * 50)
            print("🚨 CRITICAL UI BUILD ERROR 🚨", e)
            exit(99)
            # import traceback

        # Now restore the settings and update the fields if not resetting.
        default_language = "English"
        if not PrimeItems.program_arguments["reset"]:
            self.event_handlers.restore_settings_event()

            traceback.print_exc()
            print("=" * 50 + "\n")

        # FIX: FOR DEVELOPMENT ONLY
        PrimeItems.file_to_get = "/Users/mikrubin/$backup.xml"
        PrimeItems.single_project_name = self.single_project_name = PrimeItems.program_arguments[
            "single_project_name"
        ] = "Chat GPT"
        PrimeItems.program_arguments["guiview"] = True
        _ = get_xml(self.debug, self.appearance_mode)
        self.view_limit = 30000
        self.event_handlers.view_event("map")

        self.initialization = False

    def set_defaults(self: "MyGui") -> None:
        """Initializes all the default variables that MapTasker relies on."""
        logger.info("Setting defaults")
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
        self.appearance_mode = "system"

        self.indent = 4
        self.color_labels = []
        self.android_ipaddr = ""
        self.android_port = ""
        self.android_file = ""
        if self.first_time:
            self.all_messages = {}
        self.color_lookup = {}  # Setup default dictionary as empty list
        self.saved_backgfround_color = "#3e1414"
        self.font = OUTPUT_FONT
        self.gui = True
        self.color_row = 4
        self.message = ""
        self.ai_model = ""
        self.ai_name = ""
        self.ai_analyze = False
        self.ai_model_extended_list = False
        self.language = "English"
        self.ai_prompt = AI_PROMPT
        self.specific_name_msg = ""
        self.current_file_display_message = True
        self.list_unnamed_items = False

        # Display current Items setting.
        with contextlib.suppress(
            AttributeError,
        ):  # single_name_status may not be defined yet.
            self.single_name_status(all_objects, "#3f99ff")

    # Utility functions
    def display_message_box(self: "MyGui", message: str, color: str) -> None:
        """Replaces your custom textbox message logging with NiceGUI notifications/logs."""
        # Translate the color to a Tailwind/NiceGUI equivalent if needed
        # We can push it to the UI log, or show a toast notification
        ui.notify(message, type="positive" if color.lower() == "green" else "negative")
        if hasattr(self, "log_output"):
            self.log_output.push(message)

    # Re-invoke mapit.
    def remapit(self, clear_names: bool = True) -> None:
        """
        Re-invoke the 'mapit' function.

        Parameters:
            clear_names (bool): Indicates whether to clear names.

        Returns:
            None
        """

        # Fix figure out how to do this in NiceGUI.  We want to destroy the old map view and create a new one with the updated settings.
        # if self.mapview_window is not None:
        #     self.mapview_window.destroy()

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

        temp_args["ai_analyze"] = False  # Turn this off in event it was on from settings file.
        _, _ = save_restore_args(temp_args, self.color_lookup, to_save=True)

        # force a reset of PrimeItems in mapit.py: initialize_everything.
        PrimeItemsReset()

        # Now flag the fact that we are rerunning for the map view.
        # These flags are critical for the proper proceessing of the map.
        self.guiview = True  # Set it for save_settings
        PrimeItems.program_arguments["guiview"] = True  # Set it for mapit_all
        PrimeItems.colors_to_use = self.color_lookup  # Make sure we have a color to use for mapit_all.

        # Initialize a few things first
        if clear_names:
            reset_primeitems_single_names()

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

        # Now display the results: map view.
        self.mapview = self.display_view("map")
        self.textview = self.mapview
        if self.mapview is not None:
            self.display_message_box("Map View displayed.", "Green")

    def display_view(self, view_type: str, data: list | dict | None = None) -> object:
        """
        Displays a window with the given view type and data.

        Parameters:
            view_type (str): The type of view to display ("map", "diagram", or "tree").
            data (list or dict, optional): List of data to be displayed in the view. Defaults to None.

        Returns:
            View (object): The window view.

        Processing Logic:
            - Creates a new window if one does not exist.
            - Focuses on the window if it already exists.
            - Displays the given data in the specified view format.
            - Packs the view in the window with specified padding and filling.
        """
        window_attribute = f"{view_type}view_window"
        window_title = f"{view_type.capitalize()} View"

        # Map view
        if view_type == "map":
            map_data = parse_html()
            # Check if too much data to display
            map_length = len(map_data)
            if map_length > self.view_limit:
                text1 = translate_string("Too much data to display (Size=")
                text2 = translate_string("View Limit=")
                text3 = translate_string(
                    "Select a larger 'View Limit' or a single Project / Profile / Task and try again.",
                )
                self.display_message_box(
                    f"{text1}{map_length}, {text2}{self.view_limit}).  {text3}",
                    "Orange",
                )
                return None
            if data:
                NiceGuiTextView(
                    master=getattr(self, window_attribute),
                    title=window_title,
                    the_data=data,
                )

        # Setup diagram view.
        elif view_type in ("diagram", "misc"):
            # Display the data.
            if data:
                NiceGuiTextView(
                    master=getattr(self, window_attribute),
                    title=window_title,
                    the_data=data,
                )
            else:
                self.display_message_box("No Project(s) Found in XML!", "Red")
                return None
        elif view_type == "tree":
            if data:
                NiceGuiTreeView(master=getattr(self, window_attribute), items=data)
            else:
                self.display_message_box("No Project(s) Found in XML!", "Red")
                return None
        else:
            self.display_message_box()(
                "Invalid view type specified. Use 'map', 'diagram', or 'tree'.",
                "Red",
            )

        return None

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
                file_to_use = PrimeItems.program_arguments["android_file"][filename_location:]
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
            none_translated = translate_string("None")
            if return_code == 6:
                self.display_message_box("Cancel button pressed.\n", "Orange")
                display_current_file(self, none_translated)
            else:
                self.display_message_box(
                    "Click 'Get Local XML' to try a different XML file.",
                    "Red",
                )
                display_current_file(self, none_translated)
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
            text = translate_string("Current file set to")
            self.display_message_box(f"{text} {filename}", "Green")
        self.file = filename  # Set this so it is saved in settings.

    def display_backup_button(
        self,
        the_text: str,
        color1: str,
        color2: str,
        routine: Callable,
    ) -> ui.button:
        """
        Displays a backup button on the GUI.

        Args:
            the_text: The text to display on the button.
            color1: The background color of the button (Hex code).
            color2: The border color of the button (Hex code).
            routine: The function to execute when the button is clicked.

        Returns:
            ui.button: The generated NiceGUI button object.
        """

        # ui.button creates the button and binds the click event instantly.
        # .style() applies the specific hex colors.
        # .classes() applies Tailwind CSS for margins (spacing) and alignment.
        self.get_backup_button = (
            ui
            .button(the_text, on_click=routine)
            .style(f"background-color: {color1}; border-color: {color2}; border-width: 2px; color: white;")
            .classes("mt-4 ml-4 font-bold")
        )

        return self.get_backup_button

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
        _build_profiles = build_profiles
        _get_ids = get_ids
        project_head = translate_string("Project:")
        scene_head = translate_string("Scene:")
        no_profiles = translate_string("No Profiles Found")
        if projects:
            for project in projects:
                project_name = projects[project]["name"]

                # Retrieves profile IDs for a given project and project name, excluding projects without profiles.
                if profile_ids := _get_ids(
                    True,
                    projects[project]["xml"],
                    project_name,
                    [],
                ):
                    # Build our list of Profiles in this Project.
                    profile_list = _build_profiles(root, profile_ids, project)

                # Project has no Profiles
                else:
                    profile_list = [no_profiles]

                # Process Scenes
                scene_names = None
                with contextlib.suppress(Exception):
                    scene_names = projects[project]["xml"].find("scenes").text
                if scene_names is not None:
                    scene_list = scene_names.split(",")
                    for scene in scene_list:
                        profile_list.append(f"{scene_head} {scene}")

                # Put it all together: Project, Profiles, and Tasks
                tree_data.append(
                    {"name": f"{project_head} {project_name}", "children": profile_list},
                )

        # Return our data tree
        return tree_data

    # Validate name entered
    def check_name(self, the_name: str, element_name: str) -> bool:
        """
        Optimized name validity check.
        Uses truth tables for exclusivity and minimized translation overhead.
        """
        # 1. Local caching for speed
        _translate = translate_string
        _prime = PrimeItems
        error_message = None

        # 2. Check for missing name (Early exit potential)
        if not the_name:
            error_message = [
                f"Either the name entered for the {element_name} is blank or the 'Cancel' button was clicked.\n",
                "All Projects, Profiles, and Tasks will be displayed.\n",
            ]
            self.named_item = False

        # 3. Optimized Mutual Exclusivity Check
        # Instead of nested elifs, we check the 'truthiness' count
        else:
            names = [
                ("Project", self.single_project_name),
                ("Profile", self.single_profile_name),
                ("Task", self.single_task_name),
            ]
            # Count how many names are set
            active_names = [n for n in names if n[1]]

            if len(active_names) > 1:
                # We only ever need to compare the first two found for the error setup
                n1, n2 = active_names[0], active_names[1]
                error_message = [
                    "Error:\n\n",
                    f"You have entered both a {n1[0]} and a {n2[0]} name!\n",
                    f"(Project {n1[1]} and Profile {n2[1]})\n",
                    "Try again and only select one.\n",
                ]

            # 4. Check existence if still no error
            elif not valid_item(self, the_name, element_name, self.debug, self.appearance_mode):
                front_error = f'Error: Trying to validate "{the_name}" {element_name}'

                if not _prime.file_to_get:
                    error_message = [f'{front_error}, but the "Cancel" was selected!\n']
                    set_tasker_object_names(self)
                else:
                    # Optimized attribute fetch
                    file_name = getattr(_prime.file_to_get, "name", _prime.file_to_get)
                    error_message = [
                        f"{front_error} but it was not found in {file_name}! "
                        "All Projects, Profiles and Tasks will be displayed.\n",
                    ]

        # 5. Handle Errors
        if error_message:
            self.display_multiple_messages(error_message, "Red")
            self.single_project_name = self.single_profile_name = self.single_task_name = ""
            return False

        # 6. Success Logic (Minimized translations)
        none_text = _translate("None")
        if the_name == none_text:
            msg = _translate("'None' selected.  Displaying all Projects, Profiles and Tasks.")
            self.display_message_box(msg, "Green")
        else:
            # Check for localization method once
            localized_el = _prime._(element_name) if hasattr(_prime, "_") else element_name
            text1 = _translate("Display only the")
            text2 = _translate("overrides any previous set name")
            self.display_message_box(f"{text1} '{the_name}' {localized_el} ({text2}).", "Green")

        return True

    def extract_settings(self, temp_args: dict) -> None:
        """
        Extract settings from arguments dictionary.  Invoke the argument's lamba routine to set the value and display message.
        Args:
            temp_args: Dictionary of settings
        Returns:
            None: Does not return anything
        - Loops through dictionary and sets attributes on object
        - Calls restore_display to get message for setting change
        - Loops through color lookup and builds message of color changes
        - Displays message box with all setting changes
        """
        # Indicate that an extraction is in progress so we don't inadvertently change the colors already set
        # via the 'appearance_mode' setting.
        self.extract_in_progress = True
        for key, value in temp_args.items():
            if key is not None:
                setattr(self, key, value)
                # Start log if debug
                if key == "debug" and value:
                    log_startup_values()
                # Now display the setting and act on it if necessary.
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

    # Given a setting key and value, set the attribute for the key to the value and return the setting as a message.
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
            "Analyze",
            "ai_analyze",
            "ai_analysis_window_position",
            "ai_apikey_window_position",
            "ai_model",
            "ai_name",
            "ai_popup_window_position",
            "ai_prompt",
            "color_window_position",
            "diagram_window_position",
            "map_window_position",
            "misc_window_position",
            "progressbar_window_position",
            "tab_to_use",
            "tree_window_position",
            "guiview",
            "fetched_backup_from_android",
        }
        # Define what to do for each argument restored.
        set_to = translate_string("set to")
        message_map = {
            "android_ipaddr": lambda: f"{translate_string('Android Get XML TCP IP Address')} {set_to} {value}\n",
            "android_port": lambda: f"{translate_string('Android Get XML Port Number')} {set_to} {value}\n",
            "android_file": lambda: f"{translate_string('Android Get XML File Location')} {set_to} {value}\n",
            "appearance_mode": lambda: self.event_handlers.change_appearance_mode_event(
                value,
            ),
            "ai_model_extended_list": lambda: self.select_deselect_checkbox(
                self.aimodel_extend_checkbox,
                value,
                "Display Profile/Task Conditions",
                display=False,
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
            "language": lambda: self.event_handlers.language_set_event(value),
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
                message = message_func()  # This calls the lambda function and takes a bit of time.
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

    # ################################################################################
    # Select or deselect a checkbox based on the value passed in
    # ################################################################################
    def select_deselect_checkbox(
        self,
        checkbox: ui.checkbox,
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
        checkbox = not checkbox if checked else checkbox
        if display:
            onoff = "On" if checked else "Off"
            set_on_off = translate_string(f"set {onoff}")
            self.display_message_box(f"{translate_string(argument_name)} {set_on_off}.", "Green")
        return f"{argument_name} set to {checked}.\n"

    # ################################################################################
    # Select or deselect a checkbox based on the value passed in
    # ################################################################################
    def get_input_and_put_message(self, checkbox: ui.checkbox, title: str) -> bool:
        """
        Get checkbox value and display message using NiceGUI.
        Args:
            checkbox: NiceGUI checkbox object
            title: Title of message box
        Returns:
            checkbox_value: Value of checkbox (True/False)
        """
        # In NiceGUI, use .value instead of .get()
        checkbox_value = checkbox.value

        self.inform_message(title, checkbox_value, "")
        return checkbox_value


class MapTaskerEventHandlers:
    """
    Handles all UI interactions (button clicks, dropdown changes, toggles).
    Decouples logic from the main UI drawing routines.
    """

    def __init__(self: "MapTaskerEventHandlers", gui_instance: MyGui) -> None:
        """Initialize MapTaskerEventHandlers with a reference to the main MyGui instance."""
        # We store a reference to the main MyGui instance so we can read
        # checkbox states, inputs, and update the UI elements.
        self.gui = gui_instance

    # ==========================================
    # 1. CORE EXECUTION EVENTS
    # ==========================================
    def run_program_event(self: "MapTaskerEventHandlers") -> None:
        """Triggered when 'Run & Exit' is clicked."""
        logger.info("GUI: Run Program Event Triggered")
        ui.notify("Executing MapTasker...", type="info")

        the_view = self.gui
        the_view.go_program = True
        the_view.rerun = False

        # Reset fund items in case they had already been set by 'Map' view.
        PrimeItems.found_named_items = {
            "single_project_found": False,
            "single_profile_found": False,
            "single_task_found": False,
        }

        # Validate the XML and cleanup
        the_view.cleanup_and_run(run_only=True)

    def rerun_event(self: "MapTaskerEventHandlers", output_to_browser: bool = True) -> None:
        """Triggered when 'ReRun' is clicked."""
        logger.info("GUI: ReRun Event Triggered")
        ui.notify("Re-running MapTasker with current settings...", type="ongoing")

        the_view = self.gui

        if output_to_browser:
            # Remap everything with the current settings from the GUI.
            the_view.remapit(clear_names=False)

            # Setup to redisplay the output in the browser.
            # Get the output directory/folder path
            my_output_dir = os.getcwd()
            # Finally, write out all of the output that is queued up.
            my_file_name = f"{PrimeItems.slash}MapTasker.html"
            # These need to be off for the web browsere to display
            PrimeItems.program_arguments["guiview"] = False
            PrimeItems.program_arguments["ai_analyze"] = False
            # Display the final results in the default web browser
            the_view.display_message_box(f"{my_output_dir}, {my_file_name}", "green")

        reload_gui(the_view)

    # ==========================================
    # 2. Display View: Map, Diagram, Misc or Tree
    # ==========================================
    def view_event(self: "MapTaskerEventHandlers", view_type: str) -> None:
        """Triggered when Map, Diagram, or Tree buttons are clicked."""
        window_title = f"{view_type.capitalize()} View"
        logger.info(f"GUI: Switching to {window_title}")
        ui.notify(f"Loading {window_title} View...", type="info", timeout=1000)

        # Point to the data
        data = PrimeItems.output_lines.output_lines
        gui = self.gui

        # Map view
        if view_type == "map":
            # Process all of the data and build/output our html
            build_html("")

            # Now process the data for display in the gui
            map_data = parse_html()

            # Check if too much data to display
            map_length = len(map_data)
            if map_length > gui.view_limit:
                text1 = translate_string("Too much data to display (Size=")
                text2 = translate_string("View Limit=")
                text3 = translate_string(
                    "Select a larger 'View Limit' or a single Project / Profile / Task and try again.",
                )
                gui.display_message_box(
                    f"{text1}{map_length}, {text2}{self.view_limit}).  {text3}",
                    "Orange",
                )
                if self.mapview_window is not None:
                    self.mapview_window.destroy()
                return

            # Define the view and display the map.
            NiceGuiTextView(
                self.gui,
                title=window_title,
                the_data=map_data,
            )

        # Setup diagram view.
        elif view_type in ("diagram", "misc"):
            # Display the data.
            if data:
                view = NiceGuiTextView(
                    gui,
                    title=window_title,
                    the_data=map_data,
                )
            else:
                self.display_message_box("No Project(s) Found in XML!", "Red")
                return
        elif view_type == "tree":
            if data:
                view = NiceGuiTreeView(master=getattr(self, window_attribute), items=data)
            else:
                self.display_message_box("No Project(s) Found in XML!", "Red")
                return
        else:
            self.display_message_box()(
                "Invalid view type specified. Use 'map', 'diagram', or 'tree'.",
                "Red",
            )

        return
        NiceGuiTextView if view_type != "tree" else NiceGuiTreeView(self.gui, f"{view_type} View", "place_holder")

    # ==========================================
    # 3. INPUT & DROPDOWN EVENTS
    # ==========================================
    def detail_selected_event(self: "MapTaskerEventHandlers", event_value: Event) -> None:
        """
        NICEGUI PARADIGM SHIFT:
        Dropdown (ui.select) on_change events automatically pass an 'event' object.
        The new selected value is stored in `event.value`.
        """
        self.gui.display_detail_level = event_value
        logger.info(f"Detail level changed to: {event_value}")
        # Note: If you bound this via `.bind_value()`, you don't even need this function!

    def ai_model_selected_event(self: "MapTaskerEventHandlers", event_value: Event) -> None:
        """Updates the AI model based on dropdown selection."""
        self.gui.ai_model = event_value
        logger.info(f"AI Model changed to: {event_value}")

    # ==========================================
    # 4. TEXT VIEW CONTROLS (Replacing the old _handle_event router)
    # ==========================================

    def clear_event(self, view_name: str = "mapview") -> None:
        """Clears the search input or the view itself."""
        ui.notify(f"Clearing {view_name}...", type="warning")
        # TODO: Implement logic to clear the view or reset the search input.

        # Example of how you interact with the new text engine:
        if hasattr(self.gui, "textview"):
            self.gui.textview.search_input.set_value("")

    def topbottom_event(self, top: bool, view_name: str = "mapview") -> None:
        """Jumps the view to the top or bottom."""
        direction = "top" if top else "bottom"

        # Call the Javascript scroll function we built into the text view
        if hasattr(self.gui, "textview"):
            self.gui.textview.scroll(direction)

    def wordwrap_event(self, view_name: str = "mapview") -> None:
        """Toggles CSS word-wrapping on the HTML output."""
        ui.notify(f"Toggling word wrap for {view_name}", type="info")

        if hasattr(self.gui, "textview"):
            # NiceGUI allows us to toggle Tailwind classes dynamically!
            if "whitespace-pre" in self.gui.textview.scroll_area.classes:
                self.gui.textview.scroll_area.classes(remove="whitespace-pre", add="whitespace-normal")
            else:
                self.gui.textview.scroll_area.classes(remove="whitespace-normal", add="whitespace-pre")

    def get_xml_from_android_event(self: "MyGui") -> None:
        """Equivalent to your old event handler."""
        ui.notify("Fetching XML from Android...", type="info")
        # TODO: Implement fetching logic here...

    def reset_settings_event(self: "MyGui") -> None:
        """Reset everything back to defaults."""
        self.set_defaults()
        ui.notify("Settings Reset!", type="warning")

    def ai_analyze_event(self: "MyGui") -> None:
        """Run analysis using the selected AI model and api key."""
        ui.notify("Starting AI Analysis...", type="info")
        # TODO: Implement analysis logic here...

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
        the_view = self.gui

        # Handle translation of item first
        my_name_translated = translate_string(my_name)
        none_translated = translate_string("None")
        name_entered = name_entered.replace(f"{my_name_translated}: ", "")

        if name_entered in ["No projects found", "No profiles found", "No tasks found"]:
            the_view.display_message_box("Selection ignored.", "Orange")
            name_entered = "None"
        else:
            if the_view.check_name(name_entered, my_name):
                # First set the names all to 'empty
                the_view.single_project_name = ""
                the_view.single_profile_name = ""
                the_view.single_task_name = ""
                PrimeItems.program_arguments["single_project_name"] = ""
                PrimeItems.program_arguments["single_profile_name"] = ""
                PrimeItems.program_arguments["single_task_name"] = ""
                PrimeItems.found_named_items["single_project_name"] = False
                PrimeItems.found_named_items["single_profile_name"] = False
                PrimeItems.found_named_items["single_task_name"] = False

                # Save the name in mygui signle_xxx_name.
                name_entered = "" if name_entered == none_translated else name_entered

                # Now save the name where it counts: the_view andf PrimeItems.program_arguments for use in mapit_all.
                setattr(the_view, f"single_{my_name.lower()}_name", name_entered)
                key_name = f"single_{my_name.lower()}_name"
                # Assign it to the dictionary
                PrimeItems.program_arguments[key_name] = name_entered

                text1 = translate_string("Display only")
                text2 = translate_string("Display all")
                name_entered = PrimeItems._(name_entered) if hasattr(PrimeItems, "_") else name_entered
                if name_entered:
                    the_view.specific_name_msg = f"{text1} {my_name_translated} '{name_entered}'."
                else:
                    the_view.specific_name_msg = f"{text2} {my_name_translated}."
            else:
                the_view.single_name_msg = all_objects
            # Update the pulldown menus.
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
        the_view = self.gui
        if isinstance(name_selected, dict):
            name_selected = name_selected["label"]
        if name_selected.startswith(f"{event_type}: "):
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

    # Define the asynchronous callback for the button
    async def getxml_event(self) -> None:
        """
        Opens the file dialog and saves the result.
        Get rid of any existing data, clear tasker root elements, and negate file indications.
        Set IP address, port, and file to empty strings.
        Prompt user for a new XML file and display the current file if successful.
        """
        gui = self.gui

        # Open the file picker starting at the home directory ('~')
        # The 'await' pauses this specific function until the user finishes picking a file
        result = await Local_File_Picker("~", multiple=False)

        # 3. Check if the user selected a file or canceled the dialog
        if result:
            # Save the exact file location and name to our variable
            # (local_file_picker returns a tuple if multiple=True, or a string if multiple=False)
            AppState.selected_file_path = result[0] if isinstance(result, tuple) else result

            # Update the UI to reflect the saved variable
            gui.current_file.text = f"Saved Variable: {AppState.selected_file_path}"
            gui.current_file.classes(replace="text-green-600 font-bold")
            ui.notify("File path saved successfully!", type="positive")

            # Let everyone knmow which file we are working with
            PrimeItems.file_to_get = (
                AppState.selected_file_path[0]
                if isinstance(AppState.selected_file_path, list)
                else AppState.selected_file_path
            )

            clear_tasker_data()
            gui.single_project_name = ""
            gui.single_profile_name = ""
            gui.single_task_name = ""
            gui.specific_name_msg = ""
            # Indicate that we have note yet gotten the file.
            PrimeItems.program_arguments["file"] = ""
            gui.android_ipaddr = ""
            gui.android_port = ""
            gui.android_file = ""
            program_args = PrimeItems.program_arguments
            program_args["android_file"] = ""
            program_args["android_ipaddr"] = ""
            program_args["android_port"] = ""

            # UPDATE THE XML BUTTON COLOR & STOP BLINKING
            if hasattr(gui, "get_xml_button"):
                gui.get_xml_button.props("color=green")  # Switch color from red to green
                gui.get_xml_button.classes(remove="animate-pulse")  # Strip out blinking animation

            # Redisplay the Projects/Profiles/Tasks pulldown menus for selection
            # It will call 'display_and_set_file' to display the current file name via call to 'load_xml'
            gui.current_file_display_message = True
            update_tasker_object_menus(gui, get_data=True, reset_single_names=True)
            gui.current_file_display_message = False

        else:
            # Handle the case where the user hit "Cancel" or closed the dialog
            ui.notify("File selection canceled.", type="warning")

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
        the_view = self.gui
        the_view.set_defaults()  # Reset all values
        temp_args = {}
        the_view.color_lookup = {}
        # Restore all changes that have been saved
        temp_args, the_view.color_lookup = save_restore_args(
            temp_args,
            the_view.color_lookup,
            to_save=False,
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

        # Save our background color for later reuse
        the_view.saved_background_color = make_hex_color(the_view.color_lookup.get("background_color"))

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
        the_view = self.gui
        # Get our key, if it exists.
        the_view.ai_apikey = get_api_key()

        # Issue the dialog box for the API key.
        api_key = APIKeyDialog(the_view)
        # Save the window
        api_key.master.ai_apikey_window = api_key

    async def ai_prompt_event(self) -> None:
        """
        Handles the event when the AI prompt is changed using an async NiceGUI dialog.
        """
        the_view = self.gui
        msg1 = translate_string("Current prompt:")
        msg2 = translate_string("Enter a new prompt for the AI to use:")
        dialog_title = translate_string("Change the Ai Prompt")

        # 1. Create a custom asynchronous input dialog structure
        # This structure waits for the user to click either 'Submit' or 'Cancel'
        name_entered = None

        with ui.dialog() as dialog, ui.card().classes("w-[500px] p-6"):
            ui.label(dialog_title).classes("text-xl font-bold text-blue-600 mb-2")

            # Display current prompt info
            ui.label(f"{msg1} '{the_view.ai_prompt}'").classes("text-sm text-gray-500 italic mb-4")
            ui.label(msg2).classes("text-sm font-semibold")

            # Input field (initialized with current prompt text for convenience)
            prompt_input = ui.input(value=the_view.ai_prompt).classes("w-full mb-6")

            # Actions Row
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=lambda: dialog.submit(None)).classes("bg-gray-400 text-white")
                ui.button("Submit", on_click=lambda: dialog.submit(prompt_input.value)).classes(
                    "bg-blue-600 text-white",
                )

        # 2. Open the dialog and execution halts here until dialog.submit() is triggered
        name_entered = await dialog

        # 3. Handle the resulting inputs identically to your original logic
        # Canceled? (User clicked Cancel or closed the modal backdrop)
        if name_entered is None:
            the_view.display_message_box("Prompt change canceled.", "Orange")

        # The same?
        elif name_entered == the_view.ai_prompt:
            the_view.display_message_box("Prompt did not change.", "Orange")

        # Valid response
        else:
            the_view.ai_prompt = name_entered
            msg = translate_string("Prompt changed to")
            the_view.display_message_box(
                f"{msg} '{the_view.ai_prompt}'.",
                "Green",
            )
            display_selected_object_labels(the_view)

    def extended_models_event(self) -> None:
        """
        Get input to display names in bold and put message
        Args:
            self: The class instance
        Returns:
            None: No value is returned
        - Get input value from bold_checkbox attribute
        - Put message "Display Names in Bold" based on input
        - No return value, function updates attribute on class instance"""
        the_view = self.gui

        # Re-display pulldown list.
        the_view.ai_model_extended_list = the_view.get_input_and_put_message(
            the_view.aimodel_extend_checkbox,
            "Display The Extended List of AI Models",
        )

        # Display the model pulldown list.
        display_model_pulldown(self, 50)

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

        the_view = self.gui

        # Determine if the selected appearance mode is one of the standard modes or a translated mode, and set the mode accordingly.
        # First, check if it is a previously-set language mode.
        if (
            new_appearance_mode not in ["Dark", "Light", "System", "dark", "light", "system"]
            and PrimeItems.appearance_translated
        ):
            # Find our new appearance mode in the translated values and set the language to the corresponding key to
            # translate it back to English for the appearance mode setting.
            for key, value in PrimeItems.appearance_translated.items():
                if new_appearance_mode in value:
                    save_language = PrimeItems.program_arguments["language"]
                    PrimeItems.program_arguments["language"] = key
                    _ = translate_string(key, set_language=True)
                    new_appearance_mode = translate_string(new_appearance_mode.capitalize()).lower()
                    PrimeItems.program_arguments["language"] = save_language
                    _ = translate_string(save_language, set_language=True)
                    break
        elif new_appearance_mode not in ["Dark", "Light", "System", "dark", "light", "system"]:
            new_appearance_mode = "system"

        if PrimeItems.program_arguments["language"] != "English":
            # Translated string is capitalized, so we need to translate first and then lowercase for the appearance mode.
            new_appearance_mode_translated = translate_string(new_appearance_mode.capitalize())
            # Recreate the pulldown menu translated.
            the_view.appearance_mode_optionmenu.destroy()
            create_appearance_mode_section(the_view)
            if new_appearance_mode in ["dark", "light", "system"]:
                appearance_mode_to_set = new_appearance_mode_translated.capitalize()
                mode_to_set = new_appearance_mode
            else:
                appearance_mode_to_set = new_appearance_mode
                mode_to_set = new_appearance_mode_translated.lower()
        else:
            new_appearance_mode_translated = new_appearance_mode.capitalize()
            # FIX what is this for?
            appearance_mode_to_set = new_appearance_mode_translated
            mode_to_set = new_appearance_mode

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
        the_view = self.gui
        the_view.bold = the_view.get_input_and_put_message(
            the_view.bold_checkbox,
            "Display Names in Bold",
        )

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
        the_view = self.gui
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
        the_view = self.gui
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
        the_view = self.gui
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
        the_view = self.gui
        the_view.taskernet = the_view.get_input_and_put_message(
            the_view.taskernet_checkbox,
            "Display TaskerNet Information",
        )

    def font_event(self, font_selected: str) -> None:
        """
        Sets the font for the GUI using NiceGUI properties.
        Args:
            font_selected: The font name selected by the user
        """
        the_view = self.gui
        the_view.font = font_selected

        # Prepare translated text
        font_use_text = translate_string("Monospaced Font To Use")
        label_text = f"{font_use_text}: {font_selected}"

        # 1. Update or create the label
        # In NiceGUI, we just check if the attribute exists and isn't None
        if hasattr(the_view, "font_out_label") and the_view.font_out_label:
            the_view.font_out_label.text = label_text
            # Dynamically change the font-family styling over the web
            the_view.font_out_label.style(f"font-family: {font_selected}; font-size: 14px;")
        else:
            # Assuming this falls back to a layout container context if created on the fly,
            # or you can pre-instantiate it in your main layout setup.
            the_view.font_out_label = (
                ui.label(label_text).style(f"font-family: {font_selected}; font-size: 14px;").classes("mt-2 ml-2")
            )

        # 2. Update the option menu selection drop-down
        if hasattr(the_view, "font_optionmenu") and the_view.font_optionmenu:
            the_view.font_optionmenu.value = font_selected

        # 3. Toast confirmation message box
        set_to_text = translate_string("Font To Use set to")
        the_view.display_message_box(f"{set_to_text} {font_selected}", "Green")

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
        the_view = self.gui
        the_view.indent = int(ident_amount)
        the_view.indent_option.value = str(ident_amount)
        the_view.display_message_box(f"Indentation Amount set to {ident_amount}", "green")

    def language_selected_event(self, language: str) -> None:
        """
        Set the language for the GUI and redisplay everything using NiceGUI.

        Args:
            language: The language selected by the user.
        """
        # Let everyone know we are setting the language
        PrimeItems.language_set = True

        # Determine reference view (matches your event logic structure)
        the_view = self if self.__class__.__name__ == "MyGui" else self.gui
        if the_view.language == language:
            return

        # Set the translation function in PrimeItems
        # Assuming language_set_event handles internal localization configurations
        if hasattr(self, "language_set_event"):
            self.language_set_event(translate_string(language))

        # Reset selection checkboxes / extended list flags
        the_view.displaying_extended_list = None  # Force pulldown to be recreated.
        if hasattr(the_view, "aimodel_extend_checkbox") and the_view.aimodel_extend_checkbox:
            the_view.aimodel_extend_checkbox.value = False

        # Wipe out and rebuild layout context blocks natively
        # Re-initialize the screen components using the new localized string tables
        initialize_screen(the_view)

        # Redisplay current file
        display_current_file(the_view, the_view.file)

        # Restore settings values so that they are correctly displayed in the new UI instance
        temp_args = {arg: getattr(the_view, arg) for arg in ARGUMENT_NAMES if hasattr(the_view, arg)}
        the_view.extract_settings(temp_args)

        # Trigger task limit label updates
        if hasattr(self, "tasklimit_event"):
            self.tasklimit_event(the_view.task_action_warning_limit)

        # Reset the single item object tracking names
        set_tasker_object_names(the_view)

        # Reset single item dropdown select lists
        update_tasker_object_menus(
            the_view,
            get_data=False,
            reset_single_names=False,
        )

        # Handle upgrade buttons checks
        if hasattr(the_view, "check_new_version"):
            the_view.check_new_version()

        # Update the pull-down menus option items lists
        if "list_tasker_objects" in globals():
            list_tasker_objects(the_view)

        # Plug back current localized option value matches into dropdown selectors (.value replaces .set())
        if the_view.single_project_name:
            if hasattr(the_view, "specific_project_optionmenu") and the_view.specific_project_optionmenu:
                the_view.specific_project_optionmenu.value = the_view.single_project_name
            if hasattr(the_view, "ai_project_optionmenu") and the_view.ai_project_optionmenu:
                the_view.ai_project_optionmenu.value = the_view.single_project_name
        elif the_view.single_profile_name:
            if hasattr(the_view, "specific_profile_optionmenu") and the_view.specific_profile_optionmenu:
                the_view.specific_profile_optionmenu.value = the_view.single_profile_name
            if hasattr(the_view, "ai_profile_optionmenu") and the_view.ai_profile_optionmenu:
                the_view.ai_profile_optionmenu.value = the_view.single_profile_name
        elif the_view.single_task_name:
            if hasattr(the_view, "specific_task_optionmenu") and the_view.specific_task_optionmenu:
                the_view.specific_task_optionmenu.value = the_view.single_task_name
            if hasattr(the_view, "ai_task_optionmenu") and the_view.ai_task_optionmenu:
                the_view.ai_task_optionmenu.value = the_view.single_task_name

        # Redo the contextual text labels values
        display_selected_object_labels(the_view)

        # Update text labels inside tabs directly by changing the properties of references saved in guiwins.py
        if hasattr(the_view, "tab_specific_name") and the_view.tab_specific_name:
            the_view.tab_specific_name.text = translate_string("Specific Name")
        if hasattr(the_view, "tab_colors") and the_view.tab_colors:
            the_view.tab_colors.text = translate_string("Colors")
        if hasattr(the_view, "tab_analyze") and the_view.tab_analyze:
            the_view.tab_analyze.text = translate_string("Analyze")
        if hasattr(the_view, "tab_debug") and the_view.tab_debug:
            the_view.tab_debug.text = translate_string("Debug")

        # Forces the tab panel component container to process text and redraw updates
        ui.update()

    def language_set_event(self, language: str) -> None:
        """
        Set the language for the GUI.  COmes here via 'restore_display' and 'language_set_event'

        Args:
            language: The language selected by the user.
        """
        the_view = self if self.__class__.__name__ == "MyGui" else self.gui

        # Get or Set and Get the language to use in English: Spanish, German, etc.
        language_translated = translate_string(language, set_language=True)
        if language in PrimeItems.languages:
            language_to_use = language
        elif language_translated in PrimeItems.languages:
            language_to_use = language_translated
        else:
            language_to_use = "English"
        the_view.language = language_to_use

        flag_language = language if language in PrimeItems.languages else translate_string(language)
        try:
            flag = f"flag_{PrimeItems.languages[flag_language]}"
            add_logo(the_view, flag)
        except KeyError:
            pass

        language_translated = translate_string(language_to_use)
        # Change the menu to reflect the selected language
        if hasattr(the_view, "language_optionmenu"):
            the_view.language_optionmenu.set(language_translated)
            PrimeItems.program_arguments["language"] = language_to_use

        # Translate and format message
        message = f"{translate_string('Language set to')} {language_translated}."

        # Display message in the GUI
        the_view.clear_messages = True
        the_view.display_message_box(message, "Green")

    def tasklimit_event(self, slider_value: any) -> None:
        """
        Handles the task limit slider change event using NiceGUI.

        This function updates the internal task warning limit and dynamically
        refreshes the text on the sidebar label.
        """
        # Determine if slider_value is a raw number or a NiceGUI Event object
        value = int(slider_value.value if hasattr(slider_value, "value") else slider_value)

        # In your event handler class context, self.gui represents 'the_view' (self.gui)
        the_view = self.gui

        # 1. Update the backend state logic
        the_view.task_action_warning_limit = value

        # 2. Update the tracking label text dynamically over the web interface
        if hasattr(the_view, "task_action_label") and the_view.task_action_label:
            the_view.task_action_label.text = f"Task Action Limit: {value}"


# Define a state container to hold our saved file locationvariable
class AppState:
    """Initialize the variable to hold the selected file path.
    This is a class variable that can be accessed and modified from anywhere in the code."""

    selected_file_path = None
