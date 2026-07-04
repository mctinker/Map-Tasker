"""Code to manage the graphical user interface using NiceGUI."""

import contextlib
import pickle
import sys
import webbrowser
from collections.abc import Callable
from typing import TYPE_CHECKING

from nicegui import Event, run, ui

from maptasker.src.aiutils import get_api_key
from maptasker.src.bildhtml import build_html
from maptasker.src.colrmode import set_color_mode
from maptasker.src.config import AI_PROMPT, DEFAULT_DISPLAY_DETAIL_LEVEL, OUTPUT_FONT
from maptasker.src.getfile import Local_File_Picker
from maptasker.src.getids import get_ids
from maptasker.src.getputer import save_restore_args
from maptasker.src.guimap import parse_html
from maptasker.src.guiutil2 import get_changelog_file
from maptasker.src.guiutils import (
    add_logo,
    build_profiles,
    clear_android_buttons,
    create_changelog,
    display_analyze_button,
    display_current_file,
    display_error_file_and_ai_response,
    display_model_pulldown,
    display_selected_object_labels,
    get_xml,
    list_tasker_objects,
    ping_android_device,
    reload_gui,
    set_ai_key,
    set_tasker_object_names,
    update_tasker_object_menus,
    valid_item,
    validate_or_filelist_xml,
)
from maptasker.src.guiwins import (
    NiceGuiTextView,
    NiceGuiTreeView,
    initialize_gui,
    initialize_screen,
)
from maptasker.src.guiwins2 import APIKeyDialog
from maptasker.src.mapai import get_ai_object, map_ai, valid_api_key
from maptasker.src.maputil2 import log_startup_values, translate_string
from maptasker.src.maputil3 import validate_xml_file
from maptasker.src.maputils import (
    append_to_filename,
    clear_tasker_data,
    get_current_local_time_auto_timezone,
    make_hex_color,
    rename_file,
    update_maptasker,
)
from maptasker.src.outline import outline_the_configuration
from maptasker.src.primitem import PrimeItems
from maptasker.src.rungui import capture_gui_state
from maptasker.src.sysconst import (
    ANALYSIS_FILE,
    ARGUMENT_NAMES,
    CHANGELOG_URL,
    KEYFILE,
    TAB_NAMES,
    TYPES_OF_COLOR_NAMES,
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
            sys.exit()
            # import traceback

        # Now restore the settings and update the fields if not resetting.
        self.default_language = "English"
        if not PrimeItems.program_arguments["reset"]:
            self.event_handlers.restore_settings_event()

            # 3. Synchronize runtime arguments
            if self.color_lookup and not PrimeItems.colors_to_use:
                capture_gui_state(self, {})

            # traceback.print_exc()
            print("=" * 50 + "\n")

        # FIX: FOR DEVELOPMENT ONLY
        PrimeItems.file_to_get = "/Users/mikrubin/$backup.xml"
        PrimeItems.program_arguments["single_project_name"] = self.single_project_name = PrimeItems.program_arguments[
            "single_profile_name"
        ] = self.single_profile_name = PrimeItems.program_arguments["single_task_name"] = self.single_task_name = "None"
        PrimeItems.program_arguments["single_project_name"] = self.single_project_name = "Chat GPT"
        PrimeItems.program_arguments["guiview"] = True
        _ = get_xml(self.debug, self.appearance_mode)
        self.view_limit = 9999999
        list_tasker_objects(self)
        # self.event_handlers.view_event("map")

        self.initialization = False

    def set_defaults(self: "MyGui") -> None:
        """Initializes all the default variables that MapTasker relies on."""
        logger.info("Setting defaults")
        self.is_updating = False  # Indicator for when we're in the middle of an update to prevent recursive calls
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
        self.saved_background_color = "#3e1414"
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
                self.textview = NiceGuiTextView(
                    master=getattr(self, window_attribute),
                    title=window_title,
                    the_data=data,
                )

        # Setup diagram view.
        elif view_type in ("diagram", "misc"):
            # Display the data.
            if data:
                self.textview = NiceGuiTextView(
                    master=getattr(self, window_attribute),
                    title=window_title,
                    the_data=data,
                )
            else:
                self.display_message_box("No Project(s) Found in XML!", "Red")
                return None
        elif view_type == "tree":
            if data:
                self.textview = NiceGuiTreeView(master=getattr(self, window_attribute), items=data)
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
            .classes("mt-0 ml-0 font-bold")
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
    def check_name(self: "MyGui", the_name: str, element_name: str) -> bool:
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
            self.textview = NiceGuiTextView(
                self,
                title="Misc View",
                the_data=error_message,
            )
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
                # Make the modification based on the specfic setting
                _ = self.restore_display(key, value)
                # # Now display the setting and act on it if necessary.
                # if new_message := self.restore_display(key, value):
                #     self.display_message_box(f"{new_message}\n", "Green")

        # Set the tab to use to the default.
        if self.tab_to_use is None:
            self.tab_to_use = TAB_NAMES[0]

        # We have read colors and runtime args from backup file.  Now extract process_data,  them for use.
        self.extract_colors()

        # Display completion
        self.display_message_box("Settings restored.\n", "Green")
        self.extract_in_progress = False

    def extract_colors(self) -> None:
        """
        Extracts and displays the color settings from the color_lookup dictionary.
        Reverses the TYPES_OF_COLOR_NAMES dictionary to map color names to their corresponding keys.
        Displays each color setting using the display_message_box method, handling cases where the background color is set.
        Ensures all colors are accounted for, setting any missing colors to turquoise.
        """
        # Display the restored color changes, using the reverse dictionary of
        #   TYPES_OF_COLOR_NAMES (found in sysconst.py)
        # inv_color_names = {v: k for k, v in TYPES_OF_COLOR_NAMES.items()}
        # for key, value in self.color_lookup.items():
        #     text_out = value
        #     if key is not None:
        #         if key == "msg":
        #             inv_color_names[key] = ""
        #         else:
        #             # Set the displayed color to that of the color name, unlessa it is the background color.
        #             color = value
        #             if inv_color_names[key] == "Background":
        #                 color = "white"
        #                 text_out = f"{value} (displayed as white)"
        #             with contextlib.suppress(KeyError):
        #                 self.display_message_box(
        #                     f"{inv_color_names[key]} color set to {text_out}\n",
        #                     color,
        #                 )

        # Make sure we have all of our colors.  If any are missing then just make them turquoise.
        if self.color_lookup:
            for key, color in TYPES_OF_COLOR_NAMES.items():
                if color not in self.color_lookup:
                    self.color_lookup[color] = "turquoise"
                    self.display_message_box(
                        f"{key} color missing.  It has been set to turquoise.\n",
                        "turquoise",
                    )

            # Save our background color for later reuse
            self.saved_background_color = make_hex_color(self.color_lookup.get("background_color"))

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
            # FIX Delete the fopllowing code
            # "appearance_mode": lambda: self.event_handlers.change_appearance_mode_event(
            #     value,
            # ),
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
            # "outline": lambda: self.select_deselect_checkbox(
            #     self.outline_checkbox,
            #     value,
            #     "Display Configuration Outline",
            #     display=False,
            # ),
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
        # Read the value from the element directly.
        # Reading a value never fires an event in NiceGUI, so we don't need to suppress anything!
        checkbox_value = checkbox.value

        self.inform_message(title, checkbox_value, "")
        return checkbox_value

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

    def tasklimit_set(self, limit: str | int) -> None:
        """
        Set the limit for the number of Task actions before issuing a warning.
        Updated for NiceGUI tracking values with an integrated state lock.

        Args:
            limit (str | int): The limit to set for the number of Task actions.
        """
        # Convert to int for logic state safety, but preserve string conversion where needed
        limit_int = int(limit)
        self.task_action_warning_limit = limit_int

        # 1. Output feedback notification
        text = translate_string("Task Action Warning Limit set to")
        self.display_message_box(
            f"{text} {limit_int}.\n",
            "Green",
        )

        # 2. Update the tracking text label directly
        if hasattr(self, "task_action_label") and self.task_action_label:
            self.task_action_label.text = f"Task Action Limit: {limit_int}"

        # 3. Update the NiceGUI slider's current knob placement value SAFELY using the lock flag
        if hasattr(self, "task_action_limit") and self.task_action_limit:
            try:
                self.is_updating = True  # Engage the lock to silence slider echoes
                self.task_action_limit.value = limit_int
            finally:
                self.is_updating = False  # Always disengage the lock

    # Inform user of toggle selection
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
        toggle_name = translate_string(toggle_name)
        setit = translate_string(f"set{extra}")
        set_on_off = translate_string(f"{setit}{response}")
        self.display_message_box(f"{translate_string(toggle_name)} {set_on_off}", "Green")

    # Display Ai Analysis response in a separate top level window.
    def display_ai_response(self, analysis_response: str) -> None:
        """
        Display AI response in a GUI window and rename ther anaysis file.

        Args:
            error_msg (str): The error message to display in the GUI.

        Returns:
            None
        """
        # Get our date and time and save it for the file name.
        now_time = get_current_local_time_auto_timezone()
        date_and_time = (
            f"-{now_time.month}-{now_time.day}-{now_time.year}_{now_time.hour}-{now_time.minute}-{now_time.second}"
        )
        analysis_response = analysis_response.replace("-date-time", date_and_time)

        # Rename ANALYSIS_FILE.
        # X Get front part of filename ANALYSIS_FILE and plug it in as the beginning.
        if new_file_name := append_to_filename(ANALYSIS_FILE, date_and_time):
            rename_file(ANALYSIS_FILE, new_file_name)
            text = translate_string("saved as")
            self.display_message_box(
                f"{ANALYSIS_FILE} {text} {new_file_name}",
                "turquoise",
            )
            analysis_response = f"Analysis Response saved in file: {new_file_name}\n\n" + analysis_response.replace(
                ANALYSIS_FILE,
                new_file_name,
            )

        # Display the analysis in the toplevel window.
        self.textview = NiceGuiTextView(
            self,
            title="Misc View",
            the_data=analysis_response,
        )


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
    # 2. Display View: Map, Diagram, Misc or Tree
    # ==========================================
    async def view_event(self: "MapTaskerEventHandlers", view_type: str) -> None:
        """Triggered when Map, Diagram, or Tree buttons are clicked.

        Uses run.io_bound to run blocking file generations in a background thread,
        allowing thread-safe access to internal PrimeItems variables.
        """
        print("bingo view_event begins")

        # FIX This is a temporary workaround to the GUI terminating prematurely due to output size.
        PrimeItems.view_limit = 20000

        window_title = f"{view_type.capitalize()} View"
        self.gui.event = True  # Set the event flag to True
        logger.info(f"GUI: Switching to {window_title}")

        gui = self.gui

        # Map view
        if view_type == "map":
            ui.notify(f"Loading {window_title} View...", type="info", timeout=1000)
            ui.update()  # Force immediate UI update to show notification

            # 1. Clear out stale error codes before starting execution paths
            PrimeItems.error_code = 0
            PrimeItems.error_msg = ""

            try:
                # 2. RUN IO BOUND: Uses background threads to preserve memory singletons safely
                await run.io_bound(build_html, "")
            except SystemExit as e:
                # Intercept background termination codes gracefully
                error_code_extracted = e.code if hasattr(e, "code") else 6
                if error_code_extracted == 6:
                    gui.display_message_box(
                        "Map view creation skipped: No valid XML source found or action canceled.",
                        "Orange",
                    )
                else:
                    gui.display_message_box(f"Map processing halted with system code: {error_code_extracted}", "Red")
                return

            # Check if an entry-point processing failure occurred during build_html
            if getattr(PrimeItems, "error_code", 0) > 0:
                gui.display_message_box(f"Map processing error: {PrimeItems.error_msg}", "Orange")
                PrimeItems.error_code = 0
                PrimeItems.error_msg = ""
                return

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
                    f"{text1}{map_length}, {text2}{gui.view_limit}).  {text3}",
                    "Orange",
                )
                return

            # Define the view and display the map.
            gui.textview = NiceGuiTextView(
                gui,
                title=window_title,
                the_data=map_data,
            )
            gui.display_message_box("Map View displayed.", "Green")

        # Setup diagram view.
        elif view_type in ("diagram", "misc"):
            # Check if we have a Project or Profile
            if view_type == "diagram":
                if PrimeItems.tasker_root_elements["all_projects"] or PrimeItems.tasker_root_elements["all_profiles"]:
                    gui.display_message_box(
                        "The 'Diagram' view is running in the background.  Please stand by...",
                        "Green",
                    )

                    # Offload the configuration outliner to an IO-bound thread safely
                    await run.io_bound(outline_the_configuration)

                    gui.textview = NiceGuiTextView(
                        gui,
                        title=window_title,
                        the_data=[],
                    )
                else:
                    gui.display_message_box("No XML data loaded! Please select a valid XML file first.", "Orange")

            else:
                gui.display_message_box(
                    "The 'Misc' view is running in the background.  Please stand by...",
                    "LimeGreen",
                )
                gui.textview = NiceGuiTextView(
                    gui,
                    title="Misc View",
                    the_data=[],
                )

        elif view_type == "tree":
            tree_data = gui.build_the_tree()
            if tree_data:
                gui.textview = NiceGuiTreeView(gui, "Tree View", items=tree_data)
            else:
                gui.display_message_box("No Project(s) Found in XML!", "Red")
                return
        else:
            ui.notify(
                "No XML data loaded! Please Get XML from Android or Local drive first.",
                type="warning",
                position="top",
            )
            gui.display_message_box(
                "Invalid view type specified. Use 'map', 'diagram', or 'tree'.",
                "Red",
            )

        print("bingo view_event ended")

    # async def view_event(self: "MapTaskerEventHandlers", view_type: str) -> None:
    #     """Triggered when Map, Diagram, or Tree buttons are clicked."""
    #     window_title = f"{view_type.capitalize()} View"
    #     logger.info(f"GUI: Switching to {window_title}")
    #     print("bingo view_event")
    #     ui.notify(f"Loading {window_title} View...", type="info", timeout=1000)
    #     ui.update()  # Force immediate UI update to show notification

    #     # Point to the data
    #     data = PrimeItems.output_lines.output_lines
    #     gui = self.gui
    #     # FIX Temporary fix for view limit.  This will be settable in the GUI later.
    #     PrimeItems.view_limit = 20000

    #     # Map view
    #     if view_type == "map":
    #         # Process all of the data and build/output our html
    #         build_html("")

    #         # Now process the data for display in the gui
    #         map_data = parse_html()

    #         # Check if too much data to display
    #         map_length = len(map_data)
    #         if map_length > gui.view_limit:
    #             text1 = translate_string("Too much data to display (Size=")
    #             text2 = translate_string("View Limit=")
    #             text3 = translate_string(
    #                 "Select a larger 'View Limit' or a single Project / Profile / Task and try again.",
    #             )
    #             gui.display_message_box(
    #                 f"{text1}{map_length}, {text2}{gui.view_limit}).  {text3}",
    #                 "Orange",
    #             )
    #             return

    #         # Define the view and display the map.
    #         gui.textview = NiceGuiTextView(
    #             gui,
    #             title=window_title,
    #             the_data=map_data,
    #         )
    #         gui.display_message_box("Map View displayed.", "Green")

    #     # Setup diagram view.
    #     elif view_type in ("diagram", "misc"):
    #         # Check if we have a Project or Profile
    #         if view_type == "diagram":
    #             # If we don't already have Project, then get some XML.
    #             if PrimeItems.tasker_root_elements["all_projects"] or PrimeItems.tasker_root_elements["all_profiles"]:
    #                 # Let the user know
    #                 gui.display_message_box(
    #                     "The 'Diagram' view is running in the background.  Please stand by...",
    #                     "LimeGreen",
    #                 )
    #                 # Process the diagram: builds the 'network' and then draws it in the GUI
    #                 outline_the_configuration()
    #                 # Display the diagram in the GUI
    #                 window_attribute = f"{view_type}view_window"
    #                 gui.textview = NiceGuiTextView(
    #                     master=getattr(self, window_attribute),
    #                     title=window_title,
    #                     the_data=[],
    #                 )

    #         else:
    #             data = []
    #             gui.display_message_box(
    #                 "The 'Misc' view is running in the background.  Please stand by...",
    #                 "LimeGreen",
    #             )
    #             gui.textview = NiceGuiTextView(
    #                 master=getattr(self, window_attribute),
    #                 title="Misc View",
    #                 the_data=[],
    #             )

    #     elif view_type == "tree":
    #         if data:
    #             gui.textview = NiceGuiTreeView("Tree View", items=data)
    #         else:
    #             gui.display_message_box("No Project(s) Found in XML!", "Red")
    #             return
    #     else:
    #         ui.notify(
    #             "No XML data loaded! Please Get XML from Android or Local drive first.",
    #             type="warning",
    #             position="top",
    #         )
    #         gui.display_message_box(
    #             "Invalid view type specified. Use 'map', 'diagram', or 'tree'.",
    #             "Red",
    #         )

    #     print("bingo view event ended")

    #     return

    # ==========================================
    # 3. INPUT & DROPDOWN EVENTS
    # ==========================================
    def detail_selected_event(self: "MapTaskerEventHandlers", event_value: Event) -> None:
        """
        NICEGUI PARADIGM SHIFT:
        Dropdown (ui.select) on_change events automatically pass an 'event' object.
        The new selected value is stored in `event`.
        """
        self.gui.display_detail_level = event_value
        logger.info(f"Detail level changed to: {event_value}")
        # Note: If you bound this via `.bind_value()`, you don't even need this function!

    def ai_model_selected_event(self: "MapTaskerEventHandlers", event_value: Event) -> None:
        """Updates the AI model based on dropdown selection."""
        if not event_value.value or self.gui.is_updating:
            return

        # 1. Parse out the raw model and provider name for the backend logic
        if isinstance(event_value.value, str):
            if ":" in event_value.value:
                self.gui.ai_model = event_value.value.split(":", 1)[1].strip()
                self.gui.ai_name = event_value.value.split(":")[0].strip()
            else:
                self.gui.ai_model = event_value.value.strip()
            PrimeItems.program_arguments["ai_name"] = self.gui.ai_name
        elif isinstance(event_value.value, list):
            self.gui.ai_model = event_value.value[0]

        logger.info(f"AI Model changed to: {self.gui.ai_model}")

        # Set the PrimeItems.ai model keys and appropriate API key based on the model chosen.
        _ = get_api_key()
        _ = set_ai_key(self.gui, self.gui.ai_model)

        # Update has_model tracking flag context-conditional status
        self.gui.has_model = bool(self.gui.ai_model) and self.gui.ai_model != "None"

        # 2. Force the Dropdown value to stay matched with its prefixed display options list
        # The lookup restoration and explicit .update() refresh cycle is only required for components like
        # dropdowns/comboboxes (ui.select) where the programmatically assigned value gets mutated away from the
        # literal string tokens stored inside the component's visible options array.
        if hasattr(self.gui, "ai_model_option") and self.gui.ai_model_option:
            # Look for the option item that ends with our newly set raw model string
            matching_option = next(
                (opt for opt in self.gui.ai_model_option.options if opt.endswith(self.gui.ai_model)),
                None,
            )
            if matching_option:
                # Use a temporary state lock block to prevent an event loop echo trigger
                try:
                    self.gui.is_updating = True
                    self.gui.ai_model_option.value = matching_option
                    self.gui.ai_model_option.update()  # Force the web browser to refresh the element layout tree
                finally:
                    self.gui.is_updating = False

        # Updates NiceGUI visual rendering colors reactively
        has_all = bool(self.gui.ai_apikey and self.gui.ai_model and self.gui.ai_prompt)
        self.gui.analysis_button.props(f"color={'green' if has_all else 'red'}")

    # ==========================================
    # 4. TEXT VIEW CONTROLS
    # ==========================================

    def clear_event(self, view_name: str = "mapview") -> None:
        """Clears the search input or the view itself."""
        ui.notify(f"Clearing {view_name}...", type="warning")
        # TODO: Implement logic to clear the view or reset the search input.

        # Example of how you interact with the new text engine:
        if hasattr(self.gui, "textview"):
            self.gui.textview.search_input.set_value("")

    def topbottom_event(self, top: bool, _view_name: str = "mapview") -> None:
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

    # ==========================================
    # ANDROID XML BACKUP EVENT HANDLERS
    # ==========================================
    def get_xml_from_android_event(self) -> None:
        """
        Gets Android details from user inside the reactive right drawer container slot.
        Replaces legacy manual CustomTkinter pixel coordinates with automated fluid Flexbox grids.
        """
        gui = self.gui

        # 1. Clear out old entries and unhide the sidebar container panel slot
        gui.android_container.clear()
        gui.android_container.classes(remove="hidden")

        # 2. Extract Fallback Default Values
        android_ipaddr = (
            "192.168.0.210" if gui.android_ipaddr == "" or gui.android_ipaddr is None else gui.android_ipaddr
        )

        android_port = "1821" if gui.android_port == "" or gui.android_port is None else gui.android_port

        if gui.android_file == "" or gui.android_file is None:
            android_file = "/Tasker/configs/user/backup.xml".replace("/", PrimeItems.slash)
        else:
            android_file = gui.android_file.replace("/", PrimeItems.slash)

        # 3. Mount text input fields and control action items into the view hierarchy
        with gui.android_container:
            ui.label("Configure Android Connection:").classes("text-sm font-bold text-blue-500 mb-1 self-start")

            # Form Fields
            gui.ip_entry = ui.input(label="1-TCP/IP Address:", value=android_ipaddr).classes("w-full q-py-none")
            gui.port_entry = ui.input(label="2-Port Number:", value=android_port).classes("w-full q-py-none")
            gui.file_entry = ui.input(label="3-File Location:", value=android_file).classes("w-full q-py-none")

            # Inline Button Row 1 (List XML & Query Help Button)
            with ui.row().classes("w-full items-center justify-between gap-1 mt-2"):
                gui.list_files_button = (
                    ui
                    .button("List XML Files", on_click=gui.event_handlers.list_files_event)
                    .style("background-color: #D62CFF; color: white;")
                    .classes("flex-grow text-xs")
                )

                gui.list_files_query_button = (
                    ui
                    .button("?", on_click=lambda: gui.event_handlers.query_event("listfile"))
                    .style("background-color: #246FB6; color: #ffd941;")
                    .classes("w-10 min-w-[40px] text-xs")
                )

            # Inline Button Row 2 (.or. Separator and Cancel Action)
            with ui.row().classes("w-full items-center justify-center gap-2 mt-1"):
                gui.label_or = ui.label(".or.").classes("text-xs text-gray-400 italic")

                # Close button clears the contents and re-hides the panel drawer clean
                ui.button(
                    "Cancel Entry",
                    on_click=lambda: (
                        gui.android_container.clear(),
                        gui.android_container.classes(add="hidden"),
                    ),
                ).classes("text-xs").props("flat color=negative dense")

            # Master Set XML Backup execution button
            gui.get_backup_button = (
                ui
                .button("Click Here to Set XML Details", on_click=gui.event_handlers.fetch_backup_event)
                .style("background-color: #D62CFF; color: white;")
                .classes("w-full mt-3 font-bold text-xs py-2")
            )

    async def list_files_event(self) -> None:
        """
        List (Android) XML files event updated for NiceGUI.
        Alters the active view tracking text instead of legacy .configure() properties.
        """
        the_view = self.gui  # self maps to MapTaskerEventHandlers, use self.gui to target MyGui

        the_view.list_files = True

        # NiceGUI uses direct text assignment to change the displayed button label
        if hasattr(the_view, "list_files_button") and the_view.list_files_button:
            the_view.list_files_button.set_text("List Files Selected")

        # Trigger the fetch execution routing
        if hasattr(the_view.event_handlers, "fetch_backup_event"):
            # --- CRITICAL FIX: Added 'await' here ---
            await the_view.event_handlers.fetch_backup_event()

    def reset_settings_event(self: "MyGui") -> None:
        """Reset everything back to defaults."""
        self.set_defaults()
        ui.notify("Settings Reset!", type="warning")

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
                # Clear out the current values
                the_view.is_updating = True
                if my_name != "Project":
                    the_view.specific_project_optionmenu.value = "None"
                    the_view.specific_project_optionmenu.update()
                if my_name != "Profile":
                    the_view.specific_profile_optionmenu.value = "None"
                    the_view.specific_profile_optionmenu.update()
                if my_name != "Task":
                    the_view.specific_task_optionmenu.value = "None"
                    the_view.specific_task_optionmenu.update()

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

            the_view.is_updating = False

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
        if hasattr(self.gui, "is_updating") and self.gui.is_updating:
            return  # Skip processing if we're in the middle of an update
        self.process_single_name_event("Project", name_selected)

    def single_profile_name_event(self, name_selected: str) -> None:
        """Generates a single profile name event."""
        if hasattr(self.gui, "is_updating") and self.gui.is_updating:
            return  # Skip processing if we're in the middle of an update
        self.process_single_name_event("Profile", name_selected)

    def single_task_name_event(self, name_selected: str) -> None:
        """Generates a single task name event."""
        if hasattr(self.gui, "is_updating") and self.gui.is_updating:
            return  # Skip processing if we're in the middle of an update
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
        gui.content_container.clear()

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
        """
        the_view = self.gui
        # Get our key, if it exists.
        the_view.ai_apikey = get_api_key()

        # 1. Instantiate the Dialog Class
        api_key_dialog = APIKeyDialog(the_view)

        # 2. Keep the class reference safely stored if needed elsewhere
        the_view.ai_apikey_dialog_instance = api_key_dialog

        # 3. Explicitly open it!
        api_key_dialog.open()
        print("bingo")

    async def ai_prompt_event(self) -> None:
        """
        Handles the event when the AI prompt is changed using an async NiceGUI dialog.
        """
        the_view = self.gui
        if not the_view.ai_prompt:
            _ai_object, _item = get_ai_object()
            the_view.ai_prompt = AI_PROMPT
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

            # UPDATE HAS_PROMPT TRACKING FLAG ---
            the_view.has_prompt = bool(the_view.ai_prompt)

        # Valid response
        else:
            the_view.ai_prompt = name_entered
            msg = translate_string("Prompt changed to")
            the_view.display_message_box(
                f"{msg} '{the_view.ai_prompt}'.",
                "Green",
            )

            # UPDATE HAS_PROMPT TRACKING FLAG ---
            the_view.has_prompt = bool(the_view.ai_prompt)

            display_selected_object_labels(the_view)

        # Updates NiceGUI visual rendering colors reactively
        has_all = bool(the_view.ai_apikey and the_view.ai_model and the_view.ai_prompt)
        the_view.analysis_button.props(f"color={'green' if has_all else 'red'}")

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
        display_model_pulldown(self)

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

        # 1. Check if an automatic programmatic update is currently running
        if getattr(the_view, "is_updating", False):
            return  # Exit early to break the recursive loop!

        # 2. Safely extract the string name from NiceGUI Events or raw strings
        font_name = font_selected.value if hasattr(font_selected, "value") else str(font_selected)
        if not font_name:
            return

        # 3. Update the underlying application state
        the_view.font = font_name

        # 4. Safely synchronize the dropdown UI component using the state lock
        if (
            hasattr(the_view, "font_optionmenu")
            and the_view.font_optionmenu
            and the_view.font_optionmenu.value != font_name
        ):
            try:
                # Engage the lock to completely silence NiceGUI's internal update echoes
                the_view.is_updating = True
                the_view.font_optionmenu.value = font_name
            finally:
                # Always release the lock regardless of execution success
                the_view.is_updating = False

        # 5. Handle the visual label synchronization on the toolbar
        self._update_font_labels(the_view, font_name)

        # 6. Issue the feedback notification toast
        set_to_text = translate_string("Font To Use set to")
        the_view.display_message_box(f"{set_to_text} {font_name}", "Green")

    # Process the Identation Amount selection
    def indent_selected_event(self, ident_amount: str) -> None:
        """Indent selected text or code block without recursive loops."""
        the_view = self.gui
        if getattr(the_view, "is_updating", False):
            return

        the_view.indent = int(ident_amount)

        if hasattr(the_view, "indent_option") and the_view.indent_option:
            try:
                the_view.is_updating = True
                the_view.indent_option.value = str(ident_amount)
            finally:
                the_view.is_updating = False

        the_view.display_message_box(f"Indentation Amount set to {ident_amount}", "green")

    def language_selected_event(self, language: str) -> None:
        """
        Set the language for the GUI and redisplay everything using NiceGUI.
        Uses a state lock to prevent recursive dropdown triggers.

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
        if hasattr(self, "language_set_event"):
            self.language_set_event(translate_string(language))

        # Reset selection checkboxes / extended list flags safely using the lock flag
        the_view.displaying_extended_list = None  # Force pulldown to be recreated.
        if hasattr(the_view, "aimodel_extend_checkbox") and the_view.aimodel_extend_checkbox:
            try:
                the_view.is_updating = True  # Engage the lock
                the_view.aimodel_extend_checkbox.value = False
            finally:
                the_view.is_updating = False  # Disengage the lock

        # Wipe out and rebuild layout context blocks natively
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

        # Map menu attributes to their target values for a clean batch update
        menu_updates = []

        if the_view.single_project_name:
            menu_updates = [
                ("specific_project_optionmenu", the_view.single_project_name),
                ("ai_project_optionmenu", the_view.single_project_name),
            ]
        elif the_view.single_profile_name:
            menu_updates = [
                ("specific_profile_optionmenu", the_view.single_profile_name),
                ("ai_profile_optionmenu", the_view.single_profile_name),
            ]
        elif the_view.single_task_name:
            menu_updates = [
                ("specific_task_optionmenu", the_view.single_task_name),
                ("ai_task_optionmenu", the_view.single_task_name),
            ]

        # Batch update the dropdown values safely under the state lock
        try:
            the_view.is_updating = True  # Engage the lock
            for attr_name, target_value in menu_updates:
                if hasattr(the_view, attr_name):
                    menu_widget = getattr(the_view, attr_name)
                    if menu_widget:
                        menu_widget.value = target_value
        finally:
            the_view.is_updating = False  # Always disengage the lock

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
        Set the language for the GUI. Comes here via 'restore_display' and 'language_set_event'.
        Uses the state lock to prevent recursive dropdown triggers.

        Args:
            language: The language selected by the user.
        """
        the_view = self if self.__class__.__name__ == "MyGui" else self.gui

        # 1. Early exit if an automatic programmatic update loop is already active
        if getattr(the_view, "is_updating", False):
            return

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

        # 2. Change the menu dropdown value safely using the lock flag
        if hasattr(the_view, "language_optionmenu") and the_view.language_optionmenu:
            try:
                the_view.is_updating = True  # Engage the lock
                the_view.language_optionmenu.value = language_translated
                PrimeItems.program_arguments["language"] = language_to_use
            finally:
                the_view.is_updating = False  # Disengage the lock

        # Translate and format message
        message = f"{translate_string('Language set to')} {language_translated}."

        # Display message in the GUI
        the_view.clear_messages = True
        the_view.display_message_box(message, "Green")

    def tasklimit_event(self, slider_value: any) -> None:
        """Handles the task limit slider change event safely using NiceGUI.
        Uses a state lock to prevent recursive updates.
        """
        the_view = self.gui

        # 1. Early exit if an automatic programmatic update loop is already active
        if getattr(the_view, "is_updating", False):
            return

        # Determine if slider_value is a raw number or a NiceGUI Event object
        value = int(slider_value.value if hasattr(slider_value, "value") else slider_value)

        the_view.task_action_warning_limit = value

        if hasattr(the_view, "task_action_label") and the_view.task_action_label:
            the_view.task_action_label.text = f"Task Action Limit: {value}"

        # 2. Update the NiceGUI slider's current knob placement value SAFELY using the lock flag
        if hasattr(the_view, "task_action_limit") and the_view.task_action_limit:
            try:
                the_view.is_updating = True  # Engage the lock
                the_view.task_action_limit.value = value
            finally:
                the_view.is_updating = False  # Always disengage the lock

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
        the_view = self.gui
        temp_args = {value: getattr(the_view, value) for value in ARGUMENT_NAMES}

        # Save the arguments in the temporary dictionary
        temp_args, the_view.color_lookup = save_restore_args(
            temp_args,
            the_view.color_lookup,
            to_save=True,
        )
        the_view.display_message_box("Settings saved.", "Green")

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
        update_maptasker()
        the_view.display_message_box("Program updated.  Restarting...", "Green")
        # Create the Change Log file to be read and displayed after a program update.
        create_changelog()

        # Reload the GUI by running a new process with the new program/version.
        reload_gui(the_view)

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
            translate_string(
                "Go to your browser and create a new issue or feature request, providing as much detail as possible.",
            ),
        )
        the_view = self.gui
        try:
            webbrowser.open(f"https:{PrimeItems.slash * 2}{url}", new=2)
        except webbrowser.Error:
            the_view.display_message_box(
                "Error: Failed to open output in browser: your browser is not supported.",
                "Red",
            )
            return
        the_view.display_message_box(
            translate_string("Report an Issue or Request a Feature\n\n") + issue_text,
            "Green",
        )

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

        guiview = self.gui

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
        # Add the changelog to the help text.
        if query_name == "help":
            changes = get_changelog_file(CHANGELOG_URL, "##", 11)
            # Bypass the version number and transl;ate the rest of the help text.
            temp = help_text.find("Help\n\n")
            help_text = translate_string(help_text[temp:])
            help_text = help_text + "\n".join(changes)

        guiview.new_message_box(f"{translate_string(title)}\n\n{translate_string(help_text)}")
        guiview.clear_messages = True  # Flag to tell display_message_box to clear the message box

    def viewlimit_event(self: object, view_limit: str) -> None:
        """View Limit Event handled safely without recursion."""
        guiview = self.gui
        if getattr(guiview, "is_updating", False):
            return

        # Get the limit and convert it to an integer if it's a digit, otherwise handle "Unlimited"
        view_limit = view_limit.value if hasattr(view_limit, "value") else view_limit
        if isinstance(view_limit, str) and view_limit.isdigit():
            view_limit = int(view_limit)
        guiview.view_limit = 9999999 if view_limit == translate_string("Unlimited") else view_limit
        if view_limit == 9999999:
            view_limit = "Unlimited"

        if hasattr(guiview, "viewlimit_optionmenu") and guiview.viewlimit_optionmenu:
            try:
                guiview.is_updating = True
                guiview.viewlimit_optionmenu.value = view_limit
            finally:
                guiview.is_updating = False

        text = translate_string("View Limit set to")
        guiview.display_message_box(f"{text} {view_limit}.", "Green")

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
        the_view = self.gui
        the_view.all_messages = {}

    def colors_event(self, e: str) -> None:
        """Fires whenever the user changes the dropdown category selection."""
        color_selected_item = e.value if hasattr(e, "value") else e
        if not color_selected_item:
            return

        the_view = self.gui
        warning_check = ["Profile Conditions", "Action Conditions", "TaskerNet Information", "Tasker Preferences"]
        check_against = [the_view.conditions, the_view.conditions, the_view.taskernet, the_view.preferences]

        # Ensure the feature visibility flag is active before changing colors
        with contextlib.suppress(Exception):
            if PrimeItems.program_arguments["language"] != "english":
                color_selected_item = translate_string(color_selected_item)
            the_index = warning_check.index(color_selected_item)
            if not check_against[the_index]:
                the_output_message = color_selected_item.replace("Profile ", "").replace("Action ", "")
                ui.notify(
                    f"Display {the_output_message} is not set to display! Turn on Display {color_selected_item} first.",
                    type="negative",
                )
                return

        # Explicitly tell the user what they are altering
        if hasattr(the_view, "color_change") and the_view.color_change:
            the_view.color_change.set_text(f"Modifying color for: {color_selected_item}")
            the_view.color_change.style("color: inherit;")

    def handle_color_pick_event(self, color_value: str) -> None:
        """Triggered automatically when a hex code or pop-up spectrum value updates."""
        the_view = self.gui

        # Read the active category directly from the dropdown selection box value
        if hasattr(the_view, "color_objects_options") and the_view.color_objects_options:
            color_selected_item = the_view.color_objects_options.value
        else:
            return

        if color_value and color_selected_item:
            translated_color_name = translate_string(color_selected_item)
            ui.notify(
                f"{translated_color_name} {translate_string('color changed to')} {color_value}",
                color=color_value,
            )

            # Plug in the selected color for the selected named item
            the_view.event_handlers.extract_color_from_event(color_value, color_selected_item)

            # --- DYNAMIC BACKGROUND LIVE REFRESH ---
            if color_selected_item == "Background":
                the_view.saved_background_color = make_hex_color(color_value)

                # If a Map/Diagram view is currently rendered on screen, update its background instantly!
                if hasattr(the_view, "textview") and the_view.textview:  # noqa: SIM102
                    # Method A: Force styling directly onto the NiceGUI scroll_area container component
                    if hasattr(the_view.textview, "scroll_area") and the_view.textview.scroll_area:
                        the_view.textview.scroll_area.style(f"background-color: {color_value} !important;")

            else:
                ui.notify("The change will take effect the next time you open the view.", color="green")

            # Update the visual status label text and text color instantly
            if hasattr(the_view, "color_change") and the_view.color_change:
                the_view.color_change.set_text(f"{color_selected_item} displays in this color.")
                the_view.color_change.style(f"color: {color_value};")

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
        the_view = self.gui
        the_view.color_lookup[TYPES_OF_COLOR_NAMES[color_selected_item]] = (
            color  # Add color for the selected item to our dictionary
        )
        PrimeItems.colors_to_use[TYPES_OF_COLOR_NAMES[color_selected_item]] = (
            color  # Add color for the selected item to our dictionary
        )

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
        the_view = self.gui
        PrimeItems.colors_to_use = set_color_mode(the_view.appearance_mode)
        # Save our background color for later reuse
        the_view.saved_background_color = make_hex_color(PrimeItems.colors_to_use.get("background_color"))
        the_view.color_lookup = {}
        the_view.display_message_box(
            "Tasker items set back to their default colors.",
            "Green",
        )

    # Kickoff the AI analysis
    async def ai_analyze_event(self) -> None:
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
        ui.notify("Starting AI Analysis...", type="info")
        gui = self.gui

        # Validate the model
        if gui.ai_model in ("None", ""):
            gui.display_message_box("No model selected.", "Orange")
            return

        # Set the AI API key based on the model selected.
        if gui.ai_name != "LLAMA" and not set_ai_key(
            gui,
            gui.ai_model,
        ):
            text = translate_string("The API Key is not set for model")
            gui.display_message_box(
                f"{text} {gui.ai_model}, or the model {gui.ai_model} is not supported.",
                "Orange",
            )
            return
        # Make sure we have a single name.
        if gui.single_profile_name == translate_string("None or unnamed!"):
            gui.single_profile_name = ""
        # Do we have a single item identified?
        if gui.single_project_name or gui.single_profile_name or gui.single_task_name:
            gui.ai_analyze = True
            # gui.event_handlers.clear_messages_event()  # Clear out all displayed messages.
            text1 = translate_string("Running")
            text2 = translate_string("analysis with model")
            gui.display_message_box(
                f"{text1} {gui.ai_name} {text2} {gui.ai_model}.",
                "Green",
            )

            # Make sure we have the ai name
            if not gui.ai_name:
                if gui.ai_model.startswith("gemini"):
                    gui.ai_name = "Gemini"
                elif gui.ai_model.startswith("claude"):
                    gui.ai_name = "Claude"
                elif gui.ai_model.startswith("gpt") or gui.ai_model.startswith("o"):
                    gui.ai_name = "OpenAI"
                else:
                    gui.ai_name = "Llama"
            else:
                PrimeItems.program_arguments["ai_name"] = gui.ai_name

            # Do the analysis.  First save our windows and settings.
            temp_args = {value: getattr(gui, value) for value in ARGUMENT_NAMES}
            # PrimeItems.program_arguments = temp_args
            _, _ = save_restore_args(temp_args, gui.color_lookup, to_save=True)

            # Now make certain we have the api key set for the model we are using.
            PrimeItems.program_arguments["ai_apikey"] = gui.ai_apikey
            PrimeItems.program_arguments["ai_model"] = gui.ai_model
            # Save the current tab
            gui.tab_to_use = "Analyze"

            # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
            # Ok, run the analysis.  Await the execution of map_ai() so control doesn't leak early!
            # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
            await map_ai()
            print("bingo back from map_ai")
            # See if we have any carryover error messages from the AI run.
            # Note: this must go after the settings restoration.
            display_error_file_and_ai_response(self)

        # Test if no XML data loaded
        elif (
            not PrimeItems.tasker_root_elements["all_projects"]
            and not PrimeItems.tasker_root_elements["all_profiles"]
            and not PrimeItems.tasker_root_elements["all_tasks"]
        ):
            gui.display_message_box(
                "No projects, profiles, or tasks have been loaded!  Load some XML and try again.",
                "Orange",
            )
        # No single item has been selected.
        else:
            gui.display_message_box(
                "Single Project/Profile/Task has not been selected!  Select only one and try again.",
                "Orange",
            )
            # Get the Profile or Task to analyze
            # If there are no Profiles or Tasks, redisplay the Analyze button
            if not list_tasker_objects(gui):
                # Drop here if we don't have any XML loaded yet.
                display_analyze_button(gui, 13, first_time=False)

    def ai_apikey_process_event(
        self: MyGui,
        dialog_container: APIKeyDialog,  # This is now accurately receiving your APIKeyDialog instance
        cancel: bool,
        clear: str,
    ) -> None:
        """
        Process the AI API Dialog key event.
        """
        apikeys_to_validate = ["openai_key", "anthropic_key", "gemini_key"]
        gui = self.gui  # self is MapTaskerEventHandlers, my_gui is MyGui

        if not dialog_container:
            return

        # 1. Handle Cancel Event
        if cancel:
            gui.display_message_box(
                "'Cancel' button selected. No change to the API keys!",
                "Orange",
            )
            dialog_container.close()  # Routes down to the inner dialog element cleanly
            return

        # 2. Handle Clear Event
        if clear:
            apikey_entry = f"entry_{clear}"
            if hasattr(dialog_container, apikey_entry):
                entry_field = getattr(dialog_container, apikey_entry)
                entry_field.set_value("")

                text = translate_string("API key cleared.")
                gui.display_message_box(
                    f"{clear.replace('_key', '').title()} {text}",
                    "LimeGreen",
                )

                # Update state tracking if the cleared key belonged to the active model
                PrimeItems.ai[clear] = ""
                set_ai_key(gui, gui.ai_model)
                gui.has_key = bool(getattr(gui, "ai_apikey", None))

                # Force dynamic button styling update
                has_all = bool(gui.ai_apikey and gui.ai_model and gui.ai_prompt)
                gui.analysis_button.props(f"color={'green' if has_all else 'red'}")
            return

        # 3. GET THE RETURNED API KEYS
        # This will now succeed because dialog_container points to the class object containing attributes
        api_keys = {
            "openai_key": dialog_container.entry_openai_key.value,
            "anthropic_key": dialog_container.entry_anthropic_key.value,
            "deepseek_key": dialog_container.entry_deepseek_key.value,
            "gemini_key": dialog_container.entry_gemini_key.value,
        }

        apikey_changed = False
        _valid_api_key = valid_api_key
        _display_message_box = gui.display_message_box

        # 4. Iterate over keys and validate/commit changes
        for key, value in api_keys.items():
            if PrimeItems.ai.get(key, "") != value:  # Check if the key value changed
                # Validate the length/format of the key if it has a value
                if value and key in apikeys_to_validate and not _valid_api_key(key, value):
                    text = translate_string("API key is invalid!")
                    error_msg = f"{key.replace('_key', '').title()} {text}"
                    _display_message_box(error_msg, "Red")
                    ui.notify(error_msg, type="negative")
                    return

                # Commit change to state
                PrimeItems.ai[key] = value
                apikey_changed = True

                text = translate_string("API key saved:")
                _display_message_box(
                    f"{key.replace('_', ' ').title()} {text} '{value}'.",
                    "LimeGreen",
                )
            else:
                text = translate_string("API key unmodified")
                _display_message_box(
                    f"{key.replace('_', ' ').title()} {text}",
                    "LimeGreen",
                )

        # 5. Save the keys to disk if they have modified state
        if apikey_changed:
            with open(KEYFILE, "wb") as key_file:
                pickle.dump(PrimeItems.ai, key_file)

            # Refresh keys on the GUI instance and update context-conditional state flags
            set_ai_key(gui, gui.ai_model)
            print("bingo apikeys set to:", gui.ai_apikey)
            gui.has_key = bool(getattr(gui, "ai_apikey", None))

            # Redisplay the UI dependencies
            display_analyze_button(gui, 13, first_time=False)
            display_selected_object_labels(gui)
        else:
            gui.display_message_box("No API keys changed.", "LimeGreen")

        # 6. Close the window view
        dialog_container.close()

        # Updates NiceGUI visual rendering colors reactively
        has_all = bool(gui.ai_apikey and gui.ai_model and gui.ai_prompt)
        gui.analysis_button.props(f"color={'green' if has_all else 'red'}")

        # Updates NiceGUI visual rendering colors reactively
        has_all = bool(gui.ai_apikey and gui.ai_model and gui.ai_prompt)
        gui.analysis_button.props(f"color={'green' if has_all else 'red'}")

    def everything_event(self) -> None:
        """
        Handles toggling all options in the 'Everything' event using NiceGUI.

        Args:
            self: The MapTaskerEventHandlers class instance.
        Returns:
            None: Does not return anything.
        """
        # In this architecture, self.gui points directly to the main MyGui instance
        mygui = self.gui
        mygui.event = True  # Flag that an event is being processed

        # NiceGUI reads state directly using the .value property
        value = mygui.everything_checkbox.value
        mygui.everything = value

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
        _select_deselect_checkbox = mygui.select_deselect_checkbox
        for attr_name, display_message in checkbox_map.items():
            checkbox = getattr(mygui, attr_name, None)
            if checkbox:
                # 1. Update the visual element check state using .set_value()
                checkbox.set_value(value)

                # 2. Run your default notification/logging formatting string
                _select_deselect_checkbox(
                    checkbox,
                    value,
                    display_message,
                    display=False,
                )

                # 3. Synchronize underlying property models
                setattr(mygui, attr_name.replace("_checkbox", ""), value)

        # Handle Display Detail Level separately
        # In NiceGUI, we store DEFAULT_DISPLAY_DETAIL_LEVEL as a string configuration
        detail_level_str = str(DEFAULT_DISPLAY_DETAIL_LEVEL)
        mygui.event_handlers.detail_selected_event(detail_level_str)
        mygui.display_detail_level = detail_level_str

        # Safely force the Dropdown select component visual match if it exists
        if hasattr(mygui, "sidebar_detail_option") and mygui.sidebar_detail_option:
            mygui.sidebar_detail_option.value = detail_level_str

        # Optionally display results in a message box
        everything = "on" if value else "off"
        msg = f"Everything toggled {everything} successfully"
        mygui.display_message_box(
            translate_string(msg),
            "Green",
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
        mygui = self.gui
        mygui.event = True
        mygui.pretty = mygui.get_input_and_put_message(
            mygui.pretty_checkbox,
            "Display Pretty Output",
        )
        print("bingo pretty:", PrimeItems.program_arguments["pretty"])

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
        mygui = self.gui
        mygui.event = True
        mygui.conditions = mygui.get_input_and_put_message(
            mygui.conditions_checkbox,
            "Display Profile and Task Action Conditions",
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
        mygui = self.gui
        mygui.event = True
        mygui.preferences = mygui.get_input_and_put_message(
            mygui.preferences_checkbox,
            "Display Tasker Preferences",
        )

    # Process the 'Twisty' checkbox
    def twisty_event(self) -> None:
        """
        Toggle display of task details under a twisty using NiceGUI.

        Args:
            self: The MapTaskerEventHandlers class instance.
        Returns:
            None: No value is returned.
        """
        mygui = self.gui
        mygui.event = True

        # 1. Read the input value using the NiceGUI .value property
        mygui.twisty = mygui.get_input_and_put_message(
            mygui.twisty_checkbox,
            "Hide Task Details Under Twisty",
        )

        # Define the threshold value matching the text explanation (3)
        all_parameters_threshold = 3

        # 2. Check if detail level is too low to support twisties
        if mygui.twisty and int(mygui.display_detail_level) < all_parameters_threshold:
            mygui.display_message_box(
                "This has no effect with Display Detail Level less than 3.  Display Detail Level set to 3!",
                "Red",
            )

            # Update both the dropdown value and the class attribute property
            if hasattr(mygui, "sidebar_detail_option") and mygui.sidebar_detail_option:
                mygui.sidebar_detail_option.value = "3"
            mygui.display_detail_level = "3"
            PrimeItems.program_arguments["display_detail_level"] = 3

        # 3. Check to see if we are doing everything (they are mutually exclusive)
        if mygui.twisty and mygui.everything:
            mygui.display_message_box(
                "'Twisty' and 'Everything' are mutually exclusive.  Unchecking 'Twisty'.",
                "Orange",
            )

            mygui.twisty = False

            # NiceGUI updates checked states programmatically via set_value()
            if hasattr(mygui, "twisty_checkbox") and mygui.twisty_checkbox:
                mygui.twisty_checkbox.set_value(False)

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
        mygui = self.gui
        mygui.event = True
        mygui.directory = mygui.get_input_and_put_message(
            mygui.directory_checkbox,
            "Display Directory",
        )

    def _update_font_labels(self, gui: any, font_name: str) -> None:
        """Helper subroutine to inject or update the toolbar's font indicator text."""
        font_use_text = translate_string("Monospaced Font To Use")
        label_text = f"{font_use_text}: {font_name}"

        if hasattr(gui, "font_out_label") and gui.font_out_label:
            gui.font_out_label.text = label_text
            gui.font_out_label.style(f"font-family: {font_name}; font-size: 14px;")
        else:
            toolbar = getattr(gui, "gui_view_toolbar", None)
            if toolbar:
                with toolbar:
                    gui.font_out_label = (
                        ui
                        .label(label_text)
                        .style(f"font-family: {font_name}; font-size: 14px;")
                        .classes("text-gray-500 italic ml-4")
                    )

    def file_selected_event(self, android_file: str) -> None:
        """
        User has selected a specific Android XML file from a pulldown menu context.
        Removes absolute pixel offsets and handles notifications natively using NiceGUI.
        """
        the_view = self.gui  # Map references directly onto the shared view container state

        # Strip off selection container payload wrappers if Quasar returns an option item dict
        if isinstance(android_file, dict):
            android_file = android_file.get("label", "")

        the_view.android_file = android_file
        clear_android_buttons(the_view)

        # Display the connection feedback confirmations
        the_view.display_message_box(
            f"Get XML IP Address set to: {the_view.android_ipaddr}\n"
            f"Port Number set to: {the_view.android_port}\n"
            f"Get Location set to: {the_view.android_file}\n"
            f"XML file acquired.",
            "Green",
        )
        the_view.file = ""  # Negate any prior local computer directory file tracking pointers

        # Validate the target remote XML structure
        PrimeItems.program_arguments["gui"] = True

        return_code, error_message = validate_xml_file(
            the_view.android_ipaddr,
            the_view.android_port,
            android_file,
        )

        # Handle validation structural failures cleanly
        if return_code > 0:
            the_view.display_message_box(error_message, "Red")
            the_view.android_file = ""
            return

        # Purge pre-existing data tracking fields
        clear_tasker_data()

        # Hide or update the dynamic input container panel block visually
        if hasattr(the_view, "android_container") and the_view.android_container:
            # Clear input fields out and hide the layout strip cleanly
            the_view.android_container.clear()
            the_view.android_container.classes(add="hidden")

        # Execute fallback labels updates
        if hasattr(the_view, "display_backup_details"):
            the_view.display_backup_details()

        # Fully reload and populate the Projects/Profiles/Tasks selection dropdown lists
        update_tasker_object_menus(the_view, get_data=True, reset_single_names=True)

    async def fetch_backup_event(self) -> None:
        """
        Fetches backup/XML details from NiceGUI user input fields and processes them.

        - Validates IP address, port, and file location using .value properties.
        - Pings the Android device to check reachability.
        - Validates or fetches XML filelist.
        - Updates the UI and internal state based on the fetched details.
        """
        gui = self.gui

        # NICEGUI PARADIGM SHIFT: Replace legacy .get() calls with reactive .value properties
        android_ipaddr = gui.ip_entry.value if hasattr(gui, "ip_entry") and gui.ip_entry else ""
        android_port = gui.port_entry.value if hasattr(gui, "port_entry") and gui.port_entry else ""
        android_file = (
            "" if gui.list_files else (gui.file_entry.value if hasattr(gui, "file_entry") and gui.file_entry else "")
        )

        if hasattr(self, "_validate_input"):
            error_msg = self._validate_input(android_ipaddr, android_port)
            if error_msg:
                gui.display_message_box(error_msg, "Red")
                return

        # --- Await the async ping function ---
        if not await ping_android_device(gui, android_ipaddr, android_port):
            return

        # Attempt to pull structural backup contents or directory arrays
        return_code, android_ipaddr, android_port, android_file = validate_or_filelist_xml(
            gui,
            android_ipaddr,
            android_port,
            android_file,
        )

        # Handle structural anomalies gracefully
        if return_code not in (0, 2):
            gui.display_message_box(f"File not found. Return code: {return_code}", "Red")
            return

        # Return code 2 signals that a sub-menu select drop-down tree is actively open waiting for user click feedback
        if return_code == 2:
            return

        # Commit validated settings data properties down to our internal tracking state structures
        if hasattr(self, "_update_internal_state"):
            self._update_internal_state(android_ipaddr, android_port, android_file)
        else:
            gui.android_ipaddr = android_ipaddr
            gui.android_port = android_port
            gui.android_file = android_file

        # Trigger final visual confirmation UI updates
        if hasattr(self, "_display_backup_summary"):
            self._display_backup_summary()
        else:
            gui.display_message_box("Android configuration details matched successfully!", "Green")

    # List unnamed Items checkbox event
    def list_unnamed_items_event(self) -> None:
        """
        Handles the event of listing unnamed tasks.
        Args:
            self: The class instance.
        Returns:
            None
        """
        the_view = self.gui
        the_view.list_unnamed_items = the_view.get_input_and_put_message(
            the_view.list_unnamed_items_checkbox,
            "List Unnamed Items",
        )
        selected = "selected" if the_view.list_unnamed_items else "deselected"
        selected = translate_string(selected)
        # Update the pull-down menus and display message
        list_tasker_objects(the_view)
        text = translate_string("'List Unnamed Items' checkbox")
        the_view.display_message_box(
            f"{text} {selected}.",
            "Green",
        )

    # Front-end event handlers
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
        view = getattr(self.gui, view_name)
        method(view, *args)

    # Handlers for Search/Next/Prev/Clear/Toggle Word Wrap/Display Only ...for each view.
    def diagram_display_only_event(self) -> None:  # noqa: D102
        self._handle_event("display_only_event", "diagramview")

    def analysis_display_only_event(self) -> None:  # noqa: D102
        self._handle_event("display_only_event", "analysisview")

    def map_display_only_event(self) -> None:  # noqa: D102
        self._handle_event("display_only_event", "mapview")

    def diagram_search_event(self) -> None:  # noqa: D102
        self._handle_event("search_event", "diagramview")

    def map_search_event(self) -> None:  # noqa: D102
        self._handle_event("search_event", "mapview")

    def analysis_search_event(self) -> None:  # noqa: D102
        self._handle_event("search_event", "analysisview")

    def diagram_search_here_event(self) -> None:  # noqa: D102
        self._handle_event("search_here_event", "diagramview")

    def map_search_here_event(self) -> None:  # noqa: D102
        self._handle_event("search_here_event", "mapview")

    def analysis_search_here_event(self) -> None:  # noqa: D102
        self._handle_event("search_here_event", "analysisview")

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


# Define a state container to hold our saved file locationvariable
class AppState:
    """Initialize the variable to hold the selected file path.
    This is a class variable that can be accessed and modified from anywhere in the code."""

    selected_file_path = None
