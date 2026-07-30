"""Code to manage the graphical user interface using NiceGUI."""

import contextlib
import pickle
import sys
import time
import webbrowser
from collections.abc import Callable
from typing import TYPE_CHECKING

from nicegui import Event, context, run, ui

from maptasker.src import profedit, projedit, taskedit
from maptasker.src.aiutils import get_api_key
from maptasker.src.bildhtml import build_html
from maptasker.src.colrmode import set_color_mode
from maptasker.src.config import AI_PROMPT, DEFAULT_DISPLAY_DETAIL_LEVEL, OUTPUT_FONT
from maptasker.src.frontmtr import output_the_front_matter
from maptasker.src.getfile import Local_File_Picker
from maptasker.src.getids import get_ids
from maptasker.src.getputer import save_restore_args
from maptasker.src.guiutil2 import get_changelog_file
from maptasker.src.guiutils import (
    SINGLE_ITEM_LABELS,
    add_logo,
    build_profiles,
    check_for_changelog,
    check_new_version,
    clear_android_buttons,
    clear_single_item_names,
    clear_single_item_view_names,
    create_changelog,
    display_analyze_button,
    display_current_file,
    display_error_file_and_ai_response,
    display_model_pulldown,
    display_selected_object_labels,
    get_xml,
    list_tasker_objects,
    ping_android_device,
    refresh_tasker_object_pulldowns,
    reload_gui,
    reset_single_item_pulldowns,
    select_pulldown_option,
    set_ai_key,
    set_tasker_object_names,
    update_analysis_button_color,
    update_tasker_object_menus,
    valid_item,
    validate_or_filelist_xml,
)
from maptasker.src.guiwins import (
    NiceGuiTextView,
    NiceGuiTreeView,
    build_add_profile_dialog,
    build_add_project_dialog,
    build_add_task_dialog,
    build_delete_profile_dialog,
    build_delete_project_dialog,
    build_delete_task_dialog,
    build_edit_profile_dialog,
    build_edit_project_dialog,
    build_edit_task_dialog,
    build_overwrite_confirm_dialog,
    build_rename_dialog,
    build_save_profile_to_android_dialog,
    build_save_project_to_android_dialog,
    build_save_to_android_dialog,
    create_popup_window,
    element_is_live,
    forget_views,
    initialize_gui,
    initialize_screen,
    live_views,
)
from maptasker.src.guiwins2 import APIKeyDialog
from maptasker.src.mapai import get_ai_object, map_ai, valid_api_key
from maptasker.src.maputil2 import (
    file_exists_on_android,
    log_startup_values,
    translate_string,
    write_full_backup_to_current_file,
)
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
from maptasker.src.primitem import (
    PrimeItems,
    initial_directory_items,
    initial_found_named_items,
    initial_grand_totals,
)
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

        # Now restore the settings and update the fields if not resetting.
        self.default_language = "English"
        if not PrimeItems.program_arguments["reset"]:
            self.event_handlers.restore_settings_event()

            # 3. Synchronize runtime arguments
            if self.color_lookup and not PrimeItems.colors_to_use:
                capture_gui_state(self, {})

            # traceback.print_exc()
            print("=" * 50 + "\n")

        # Check if newer version of our code is available on Pypi.
        check_new_version(self)

        # See if we have a changelog, and get it if we do.  This must go before 'self.process_current_messages()' call.
        check_for_changelog(self)

        # Populate the Target specific item if we have a single Project, Profile, or Task name set.
        if (
            PrimeItems.tasker_root_elements["all_projects"]
            or PrimeItems.tasker_root_elements["all_profiles"]
            or PrimeItems.tasker_root_elements["all_tasks"]
        ):
            refresh_tasker_object_pulldowns(self)
        # No data, but we have a file to get -- either a real file object already set by the
        # Android/CLI load paths (PrimeItems.file_to_get), or, failing that, the plain filename
        # restored settings put on self.file purely to show "Current File" in the toolbar (see
        # display_and_set_file): that display never itself populates PrimeItems.file_to_get, so
        # without this fallback the toolbar can show a Current File while PrimeItems.xml_root
        # stays None -- e.g. no single Project/Profile/Task name was saved to restore (the one
        # other path that syncs PrimeItems.file_to_get, via process_single_name_restore) -- and
        # anything that checks xml_root directly (like Add Task) wrongly reports no file loaded.
        elif PrimeItems.file_to_get or self.file:
            if not PrimeItems.file_to_get:
                PrimeItems.file_to_get = self.file
            return_code = get_xml(self.debug, self.appearance_mode)
            if return_code == 0:
                refresh_tasker_object_pulldowns(self)

        # See if we have any carryover error messages from the AI run.
        # Note: this must go after the settings restoration.
        display_error_file_and_ai_response(self)

        # CHG: FOR DEVELOPMENT ONLY
        # PrimeItems.file_to_get = "/Users/mikrubin/$backup.xml"
        # PrimeItems.program_arguments["single_project_name"] = self.single_project_name = PrimeItems.program_arguments[
        #     "single_profile_name"
        # ] = self.single_profile_name = PrimeItems.program_arguments["single_task_name"] = self.single_task_name = "None"
        # PrimeItems.program_arguments["single_project_name"] = self.single_project_name = "Chat GPT"
        # PrimeItems.program_arguments["guiview"] = True
        # _ = get_xml(self.debug, self.appearance_mode)
        # self.view_limit = 9999999
        # list_tasker_objects(self)
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
        self.single_scene_name = ""
        self.file = ""
        self.appearance_mode = "system"

        self.indent = 4
        self.color_labels = []
        self.android_ipaddr = ""
        self.android_port = ""
        self.android_file = ""
        self.android_auth_key = ""  # Cached Tasker HTTP API key for Save To Android (see save_task_to_android_event).
        self.android_auth_key_ipaddr = ""
        self.android_auth_key_port = ""
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

        # Good return from getting the XML. PrimeItems.file_to_get is sometimes an open
        # file object (.name is its path) and sometimes a plain string path/filename
        # (e.g. restored from CLI args or settings) -- see maputil2.py's identical
        # getattr(..., "name", ...) handling.
        file_name = getattr(PrimeItems.file_to_get, "name", PrimeItems.file_to_get)
        if file_name:
            self.display_and_set_file(file_name)
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
        if self.is_updating:
            return
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
        Displays a backup button on the GUI inline within the active context.
        """
        # REMOVED the "with self.gui_right_drawer:" breakout block to preserve row placement order
        self.get_backup_button = (
            ui
            .button(the_text, on_click=routine)
            .style(f"background-color: {color1}; border-color: {color2}; border-width: 2px; color: white;")
            .classes("mt-0 ml-0 font-bold w-full")
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
    def check_name(self: "MyGui", the_name: str, element_name: str, *, quiet_if_missing: bool = False) -> bool:
        """
        Optimized name validity check.
        Uses truth tables for exclusivity and minimized translation overhead.

        quiet_if_missing=True reports any failure as a small message-box toast
        instead of the full-screen "Misc View" error -- for callers validating a
        *restored* selection rather than one the user just picked (see
        process_single_name_restore): a single Project/Profile/Task name saved
        last session may legitimately no longer exist, most commonly a Task/
        Profile added via the Add dialog's "Ok" (kept in memory only, never
        written to the backup file) that a restart has since discarded.
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
            names = [(label, getattr(self, f"single_{label.lower()}_name", "")) for label in SINGLE_ITEM_LABELS]
            # Count how many single_xxx_name names are set
            active_names = [n for n in names if n[1]]

            if len(active_names) > 1:
                # We only ever need to compare the first two found for the error setup
                n1, n2 = active_names[0], active_names[1]
                error_message = [
                    "Error:\n\n",
                    f"You have entered both a {n1[0]} and a {n2[0]} name!\n",
                    f"({n1[0]} {n1[1]} and {n2[0]} {n2[1]})\n",
                    "Try again and only select one.\n",
                ]

            # 4. Check existence if still no error
            elif not valid_item(self, the_name, element_name, self.debug, self.appearance_mode):
                front_error = f'Error: Trying to validate "{the_name}" {element_name}'

                if not _prime.file_to_get:
                    # self.file already being set (as opposed to empty, which is what sends
                    # valid_item to prompt_and_get_file's interactive picker in the first
                    # place) means a filename WAS known -- e.g. restored from a previous
                    # session's saved settings -- but proginit.open_and_get_backup_xml_file
                    # still couldn't open it (its own FileNotFoundError branch already
                    # printed/logged the specific path), not that anyone clicked "Cancel".
                    if self.file:
                        error_message = [
                            f"{front_error}, but the backup file '{self.file}' could not be found.\n",
                            f"The {element_name} selection has been cleared.\n",
                        ]
                    else:
                        error_message = [f'{front_error}, but the "Cancel" was selected!\n']

                    # Clear the stale single-item names up front (not just in the shared
                    # tail below) and reset every pulldown to "None" directly --
                    # set_tasker_object_names only acts on whichever single_*_name is still
                    # set, so once we've cleared them here it would be a no-op and leave the
                    # pulldowns showing the now-invalid name. Guarded by is_updating: setting
                    # a NiceGUI select's .value fires its on_change (single_project_name_event
                    # etc.), which would otherwise re-enter check_name for the same name, fail
                    # valid_item the same way, and recurse into this same branch forever --
                    # the single_xxx_name_event handlers already no-op while
                    # self.is_updating is True specifically to guard against this.
                    clear_single_item_view_names(self)
                    try:
                        self.is_updating = True
                        reset_single_item_pulldowns(self)
                    finally:
                        self.is_updating = False
                else:
                    # Optimized attribute fetch
                    file_name = getattr(_prime.file_to_get, "name", _prime.file_to_get)
                    error_message = [
                        f"{front_error} but it was not found in {file_name}! "
                        "All Projects, Profiles and Tasks will be displayed.\n",
                    ]

        # 5. Handle Errors
        if error_message:
            if quiet_if_missing:
                # A restored-from-settings name that's gone is routine, not an
                # emergency: e.g. a Task added last session with "Ok" was only
                # ever registered in memory, so this session's file doesn't
                # have it. Toast and clear rather than throwing up the
                # full-screen error view.
                self.display_message_box(
                    f'The saved {element_name} selection "{the_name}" was not found in the current file '
                    f"(it may have been added last session but never saved). The selection has been cleared.",
                    "Orange",
                )
            else:
                self.textview = NiceGuiTextView(
                    self,
                    title="Misc View",
                    the_data=error_message,
                )
            clear_single_item_view_names(self)
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
            "Analyze",
            "ai_analyze",
            "ai_model",
            "ai_name",
            "ai_prompt",
            "tab_to_use",
            "guiview",
            "fetched_backup_from_android",
        }
        # Define what to do for each argument restored.
        set_to = translate_string("set to")
        message_map = {
            "android_ipaddr": lambda: f"{translate_string('Android Get XML TCP IP Address')} {set_to} {value}\n",
            "android_port": lambda: f"{translate_string('Android Get XML Port Number')} {set_to} {value}\n",
            "android_file": lambda: f"{translate_string('Android Get XML File Location')} {set_to} {value}\n",
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
            "single_scene_name": lambda: self.process_single_name_restore("Scene", value),
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
        checkbox.value = bool(checked)
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
        if name_entered and self.check_name(name_entered, my_name, quiet_if_missing=True):
            # View-only: PrimeItems.program_arguments still holds the name being
            # restored, so it must not be cleared here.
            clear_single_item_view_names(self)

            try:
                # 1. Engage the lock to silence NiceGUI event triggers
                self.is_updating = True

                # The pulldowns' own populated option lists (see
                # guiutils.get_tasker_objects/build_profiles) use different
                # conventions per item type: Project/Profile options are
                # prefixed ("Project: Base", "Profile: X" -- build_the_tree's
                # own "Project:"/build_profiles' own "Profile: " head text),
                # while Task and Scene options are the raw name with no prefix
                # at all (get_tasker_objects builds those straight from
                # all_tasks_by_name's / all_scenes' keys). "None" itself is
                # always unprefixed. A pulldown's .value has to match one of its
                # own .options verbatim or NiceGUI can't find anything to render
                # as selected and falls back to showing just that pulldown's
                # label ("Project"/"Profile"/"Task"/"Scene") -- which is exactly
                # what setting bare name_entered (no prefix) for Project/Profile,
                # or a "Task: "/"Profile: "-prefixed "None" for the others,
                # used to produce here.
                option_heads = {
                    "Project": f"{translate_string('Project:')} ",
                    "Profile": translate_string("Profile: "),
                }
                if my_name in SINGLE_ITEM_LABELS:
                    setattr(self, f"single_{my_name.lower()}_name", name_entered)

                    # Select it in its own pulldown, adding the option if the live tree
                    # has it but the pulldown list hasn't been rebuilt yet.
                    display_value = f"{option_heads.get(my_name, '')}{name_entered}"
                    optionmenu = getattr(self, f"specific_{my_name.lower()}_optionmenu")
                    if display_value not in optionmenu.options:
                        optionmenu.options.append(display_value)
                    optionmenu.value = display_value
                    reset_single_item_pulldowns(self, except_for=my_name)

                    # Update the Analyze tab's labels: the restored item shows its name,
                    # the rest show "None".
                    for label in SINGLE_ITEM_LABELS:
                        ai_label = getattr(self, f"ai_{label.lower()}_label", None)
                        if ai_label is None:
                            continue
                        if label == my_name:
                            ai_label.text = f"{translate_string(f'{label} to Analyze:')} {name_entered}"
                        else:
                            ai_label.text = f"{label}: None"
            finally:
                # 2. Always release the lock so user interaction still works
                self.is_updating = False

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
                "green",
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


def _open_popout_window(path: str, new_window: bool = False) -> None:
    """Opens a Map/Diagram popout window and remembers it in the browser so 'Close Tabs On Exit'
    (see get_rid_of_windows_and_exit in guiwins.py) can close it later -- window.open()'s return
    value is otherwise discarded and there'd be no handle left to close it with.
    The actual data display is done in rungui.py with a call to NiceGuiTextView() to display the data
    in a new window.  This function just opens the new window and remembers it in the browser.

    Each view gets a stable window name so a second Map/Diagram request re-navigates -- and
    therefore reloads -- the tab that view already has open, rather than spawning another one.
    That is what makes a regenerated view (say, after the font was changed) actually replace
    what the user is looking at: with '_blank', the browser suppresses the new popup whenever
    it decides this doesn't count as a user gesture -- and it often doesn't, since this runs
    from a server-pushed script after the view has been built, not inline in the click -- which
    would silently leave the previous, stale tab on screen as the only Map view in sight.

    `new_window` (the "Open View In New Window" option) trades that reliability for being able
    to compare views side by side: a name nothing has claimed yet behaves exactly like '_blank',
    so every request is a fresh popup the browser is free to suppress. Each popout reads the
    generated file once, on load, so the windows left open do keep showing what they were built
    with rather than all changing together.
    """
    view_name = path.rsplit("/", 1)[-1]
    window_name = f"maptasker_{view_name}_{time.time_ns()}" if new_window else f"maptasker_{view_name}"
    ui.run_javascript(
        "window.mapTaskerPopouts = window.mapTaskerPopouts || []; "
        f"const popout = window.open('{path}', '{window_name}'); "
        "if (popout) { "
        "  if (!window.mapTaskerPopouts.includes(popout)) window.mapTaskerPopouts.push(popout); "
        "  try { popout.focus(); } catch (e) {} "
        "}",
    )


def _confirmed_single_project_name(gui: MyGui) -> str:
    """Returns gui.single_project_name, but only if the Specific Name tab's own
    Project pulldown currently lists it among its options -- not just because
    the cached attribute happens to be set.

    gui.single_project_name can be set (e.g. restored from a previous
    session's saved settings, via process_single_name_restore) before that
    pulldown's own options list has been populated with real Project names --
    it starts as a placeholder ["None"] and only gets replaced once
    refresh_tasker_object_pulldowns runs, which happens *after* settings
    restore in MyGui.__init__. The pulldown then keeps showing nothing/"None"
    selected even though the cached name is still set underneath, silently
    satisfying the Add Task/Add Profile "select a Project first" gate despite
    the user seeing no selection at all in that pulldown. Requiring the name
    to actually appear in the pulldown's current options closes that gap.
    """
    name = getattr(gui, "single_project_name", "")
    if not name:
        return ""
    widget = getattr(gui, "specific_project_optionmenu", None)
    options = getattr(widget, "options", None) if widget is not None else None
    if options is not None and name not in options and f"Project: {name}" not in options:
        return ""
    return name


def _task_arg_values(field_refs: dict) -> dict[str, str]:
    """Snapshots field_refs' action-argument widgets into the string-keyed dict
    taskedit.apply_edits_to_task expects -- shared by every Task-editing entry
    point (Save, Save To Android, Ok, and Add Task's own Save/Ok), which all
    read the same live NiceGUI widget values the same way.
    """
    arg_values = {}
    for key, widget in field_refs.items():
        if key in ("name", "priority", "save_path", "target_project_name"):
            continue
        value = widget.value
        arg_values[key] = "1" if value is True else "0" if value is False else str(value)
    return arg_values


def _notify_if_plugin_needs_configuration(element: object, name: str) -> None:
    """Warns, as a just-added Action/Event/State goes in, that it is a third-party
    plugin whose own configuration can only be set inside Tasker -- see
    taskedit.tasker_configuration_warning, which decides whether one is warranted
    (nothing is shown for anything that isn't a plugin). The item's own panel in
    the dialog carries the same warning standing (guiwins.
    _render_plugin_configuration_warning); this is the moment-of-adding nudge, so
    it isn't missed in a long action list.
    """
    warning = taskedit.tasker_configuration_warning(element, name)
    if warning:
        ui.notify(warning, type="warning", multi_line=True, timeout=8000)


def _reload_saved_copy_and_refresh(gui: MyGui, new_file_path: str) -> tuple[bool, str]:
    """After Save To Current File writes a new, timestamped copy of the backup
    (see maputil2.write_full_backup_to_current_file -- the original file it
    was loaded from is never touched), switches the app over to that copy so
    it -- not the untouched original -- becomes "the current file" for any
    further editing/saving: re-parses it through the same load path
    open_and_get_backup_xml_file uses (open() the file, then
    taskerd.get_the_xml_data()), updates the Current File display, and
    refreshes the Project/Profile/Task pulldowns from the freshly loaded data.

    Returns (True, "") on success, or (False, error_message) if the reload
    itself fails -- the copy was still written to disk either way; only the
    app's in-memory state failed to switch over to it.
    """
    try:
        PrimeItems.file_to_get = open(new_file_path, encoding="utf-8")
    except OSError as e:
        return False, str(e)

    PrimeItems.program_arguments["file"] = new_file_path
    return_code = get_the_xml_data()
    if return_code != 0:
        return False, f"Failed to load '{new_file_path}' (code {return_code})."

    gui.file = new_file_path
    display_current_file(gui, new_file_path)
    refresh_tasker_object_pulldowns(gui)
    return True, ""


def _apply_edited_task(edited_task: taskedit.EditableTask, field_refs: dict) -> bool:
    """Validates and applies an existing Task's field values into the live
    in-memory backup -- the shared body of keep_edited_task_event ("Ok") and
    save_edited_task_to_current_file_event ("Save To Current File"), which
    differ only in what happens after this succeeds. Any error is already
    notified to the user; returns False so the caller knows to stop there.
    """
    arg_values = _task_arg_values(field_refs)
    errors = taskedit.apply_edits_to_task(
        edited_task,
        field_refs["name"].value,
        field_refs["priority"].value,
        arg_values,
    )
    if errors:
        for error in errors:
            ui.notify(error, type="negative")
        return False
    taskedit.apply_edited_task_to_live_tree(edited_task)
    return True


def _validate_and_apply_new_task(
    edited_task: taskedit.EditableTask,
    field_refs: dict,
    *,
    check_save_path: bool = False,
) -> tuple[bool, str]:
    """Validates a brand-new Task's Name (and, if check_save_path, its Save
    path) for conflicts, then applies its field values -- the shared
    validation+apply step of every Add Task success path (Ok, Save, Save To
    Current File), before each goes on to do its own thing with the result
    (see _finish_new_task). Returns (True, name_value) on success, or
    (False, "") if anything failed (errors already notified).
    """
    if not edited_task.actions:
        ui.notify("This Task has no actions yet.", type="warning")

    name_value = field_refs["name"].value.strip()
    conflict_errors = []
    if taskedit.task_name_exists(name_value):
        conflict_errors.append(f"A Task named '{name_value}' already exists in this backup. Choose a different name.")
    if check_save_path:
        save_path = field_refs["save_path"].value.strip()
        if taskedit.save_path_exists(save_path):
            conflict_errors.append(f"A file already exists at '{save_path}'. Choose a different name or location.")
    if conflict_errors:
        for error in conflict_errors:
            ui.notify(error, type="negative")
        return False, ""

    arg_values = _task_arg_values(field_refs)
    errors = taskedit.apply_edits_to_task(edited_task, name_value, field_refs["priority"].value, arg_values)
    if errors:
        for error in errors:
            ui.notify(error, type="negative")
        return False, ""

    return True, name_value


def _finish_new_task(
    gui: MyGui,
    edited_task: taskedit.EditableTask,
    name_value: str,
    on_created: Callable[[str], None] | None,
    field_refs: dict | None = None,
) -> None:
    """Registers a validated, applied new Task into the live in-memory backup,
    fires on_created (see build_add_task_dialog), attaches it to the target
    Project's <tids> if one was required and selected before the top-level
    "Add Task" dialog opened (field_refs["target_project_name"] -- see
    userintr.open_add_task_dialog_event and profedit.add_task_to_project;
    empty for the nested-in-Profile-edit Add Task flow, which doesn't attach
    to a Project at all), and refreshes the Project/Profile/Task pulldowns --
    the common tail of every Add Task success path, run once
    _validate_and_apply_new_task has succeeded (and, for Save, only after its
    standalone file write has too).
    """
    taskedit.register_new_task(edited_task, name_value)
    if on_created is not None:
        on_created(edited_task.task_id)

    target_project_name = field_refs.get("target_project_name") if field_refs else None
    if target_project_name:
        profedit.add_task_to_project(edited_task.task_id, target_project_name)

    refresh_tasker_object_pulldowns(gui)

    # Only for the top-level Add Task flow (target_project_name set, see
    # open_add_task_dialog_event) -- the nested Entry/Exit Task picker inside
    # Add/Edit Profile (open_add_task_for_profile_link_event) never sets it,
    # and selecting the new Task as the app-wide single-Task filter there
    # would be a surprising side effect of just picking an Entry/Exit Task.
    if target_project_name:
        select_pulldown_option(gui.specific_task_optionmenu, name_value)


def _profile_condition_values(field_refs: dict) -> dict[str, str]:
    """Snapshots field_refs' condition-field widgets into the string-keyed dict
    profedit.apply_edits_to_profile expects -- shared by every Profile-editing
    entry point (Save, Save To Android, Ok), same reasoning as _task_arg_values.
    """
    condition_values = {}
    for key, widget in field_refs.items():
        if not key.startswith("cond"):
            continue
        value = widget.value
        condition_values[key] = "1" if value is True else "0" if value is False else str(value)
    return condition_values


def _link_pending_task_pickers(edited_profile: profedit.EditableProfile, field_refs: dict) -> None:
    """Links in whatever's currently picked in the Entry/Exit "Choose a Task"
    dropdown even if the user never clicked its separate "Link" button --
    picking a Task in that dropdown reads as "done" to a user, so Save/Ok/
    Save To Android shouldn't silently discard it and then complain the
    Entry/Exit Task is missing (see profedit.validate_new_profile_requirements)
    just because the extra confirmation click didn't happen. field_refs only
    has "{entry,exit}_task_picker" while that Task is still unlinked (see
    guiwins._build_profile_editor_body) -- already-linked ones have nothing to do here.
    """
    for link_type in ("Entry", "Exit"):
        picker = field_refs.get(f"{link_type.lower()}_task_picker")
        if picker is None or not picker.value:
            continue
        resolved = taskedit.resolve_task_by_name(picker.value)
        if resolved is not None:
            task_id, _ = resolved
            profedit.link_task_to_profile(edited_profile, task_id, link_type)


def _apply_edited_profile(edited_profile: profedit.EditableProfile, field_refs: dict) -> bool:
    """Validates and applies an existing Profile's field values into the live
    in-memory backup -- the shared body of keep_edited_profile_event ("Ok")
    and save_edited_profile_to_current_file_event ("Save To Current File"),
    which differ only in what happens after this succeeds. Any error is
    already notified to the user; returns False so the caller knows to stop there.
    """
    _link_pending_task_pickers(edited_profile, field_refs)
    condition_values = _profile_condition_values(field_refs)
    errors = profedit.apply_edits_to_profile(edited_profile, field_refs["name"].value, condition_values)
    if errors:
        for error in errors:
            ui.notify(error, type="negative")
        return False
    profedit.apply_edited_profile_to_live_tree(edited_profile)
    return True


def _validate_and_apply_new_profile(
    edited_profile: profedit.EditableProfile,
    field_refs: dict,
    *,
    check_save_path: bool = False,
) -> tuple[bool, str, str]:
    """Validates a brand-new Profile's Name and Project (and, if
    check_save_path, its Save path) for conflicts, then applies its field
    values -- the shared validation+apply step of every Add Profile success
    path (Ok, Save, Save To Current File), before each goes on to do its own
    thing with the result (see _finish_new_profile). Returns
    (True, name_value, project_name) on success, or (False, "", "") if
    anything failed (errors already notified).
    """
    _link_pending_task_pickers(edited_profile, field_refs)

    name_value = field_refs["name"].value.strip()
    project_name = field_refs.get("target_project_name", "")

    conflict_errors = []
    if profedit.profile_name_exists(name_value):
        conflict_errors.append(
            f"A Profile named '{name_value}' already exists in this backup. Choose a different name.",
        )
    if check_save_path:
        save_path = field_refs["save_path"].value.strip()
        if profedit.save_path_exists(save_path):
            conflict_errors.append(f"A file already exists at '{save_path}'. Choose a different name or location.")
    if not project_name:
        conflict_errors.append(
            "Choose a Project first -- a Profile has to belong to one to show up anywhere in the app.",
        )
    conflict_errors.extend(profedit.validate_new_profile_requirements(edited_profile))
    if conflict_errors:
        for error in conflict_errors:
            ui.notify(error, type="negative")
        return False, "", ""

    condition_values = _profile_condition_values(field_refs)
    errors = profedit.apply_edits_to_profile(edited_profile, name_value, condition_values)
    if errors:
        for error in errors:
            ui.notify(error, type="negative")
        return False, "", ""

    return True, name_value, project_name


def _finish_new_profile(
    gui: MyGui,
    edited_profile: profedit.EditableProfile,
    name_value: str,
    project_name: str,
) -> None:
    """Registers a validated, applied new Profile into the live in-memory
    backup, attaches it to its Project, and refreshes the Project/Profile/
    Task pulldowns -- the common tail of every Add Profile success path, run
    once _validate_and_apply_new_profile has succeeded (and, for Save, only
    after its standalone file write has too).
    """
    profedit.register_new_profile(edited_profile, name_value)
    profedit.add_profile_to_project(edited_profile, project_name)
    refresh_tasker_object_pulldowns(gui)

    # Select the new Profile as the app-wide single-Profile filter and show it
    # in the pulldown -- also clears any stale single Project/Task selection.
    select_pulldown_option(gui.specific_profile_optionmenu, name_value)


def _finish_new_project(gui: MyGui, edited_project: projedit.EditableProject) -> None:
    """Registers a validated, applied new Project into the live in-memory
    backup and refreshes the Project/Profile/Task pulldowns -- the Add
    Project counterpart of _finish_new_profile. No Project-attachment step
    (unlike _finish_new_profile's add_profile_to_project) -- a Project has no
    parent of its own.
    """
    projedit.register_new_project(edited_project)
    refresh_tasker_object_pulldowns(gui)

    # Select the new Project as the app-wide single-Project filter and show it
    # in the pulldown -- also clears any stale single Profile/Task selection.
    select_pulldown_option(gui.specific_project_optionmenu, edited_project.project_name)


def _reset_specific_name_selection(gui: MyGui) -> None:
    """Clears the single Project/Profile/Task selection and resets all three
    'Specific Name' pulldowns to "None" -- for when a Delete removes the
    currently-selected name out from under them. Anything that merely *renames*
    it uses _select_renamed_item instead: the object is still there, so it stays
    selected under its new name.
    Mirrors the identical guarded reset in process_single_name_restore's
    invalid-name branch: the is_updating guard stops setting .value here from
    re-entering the single_xxx_name_event handlers for a name that no longer
    resolves to anything.
    """
    clear_single_item_view_names(gui)
    try:
        gui.is_updating = True
        reset_single_item_pulldowns(gui)
    finally:
        gui.is_updating = False


def _pulldown_option_for_name(optionmenu: ui.select, item_type: str, new_name: str) -> str:
    """The exact option string this 'Specific Name' pulldown lists for a
    Project/Profile/Task called new_name -- what its .value has to be set to for
    the selection to actually show.

    The three pulldowns don't label their entries the same way. The Task one
    lists plain names (guiutils.get_tasker_objects builds it straight from
    all_tasks_by_name's keys), but the Project and Profile ones list them
    prefixed with the item type -- "Project: $NewProject1", "Profile: My
    Profile" -- built by MyGui.build_the_tree and guiutils.build_profiles
    respectively. Assigning the bare name to those two sets a value that isn't
    among the select's options, and NiceGUI then renders nothing at all, leaving
    just the widget's own "Project"/"Profile" label showing as though nothing
    were selected. (process_single_name_event strips that same prefix back off
    when the user picks one by hand, which is the mirror image of this.)

    Resolved against the widget's live options rather than by rebuilding the
    prefix here, so it stays right whatever those two functions do with it --
    including translation (both build their heads through translate_string).
    Exact match first, then the translated "<type>: <name>" form, then any
    option whose tail is exactly ": <name>". Falls back to the bare name if the
    options don't have it at all -- no worse than not looking.
    """
    options = [option for option in (getattr(optionmenu, "options", None) or []) if isinstance(option, str)]
    if new_name in options:
        return new_name

    prefixed = f"{translate_string(f'{item_type}:')} {new_name}"
    if prefixed in options:
        return prefixed

    tail = f": {new_name}"
    return next((option for option in options if option.endswith(tail)), new_name)


def _select_renamed_item(gui: MyGui, item_type: str, new_name: str) -> None:
    """Makes a just-renamed Project/Profile/Task the current single item and
    points its 'Specific Name' pulldown at the new name -- the Rename
    counterpart to _reset_specific_name_selection, which the rename handlers
    used to call. Clearing the selection was only ever right because the
    pulldown still held the *old* name; the object itself is still there and
    still the one the user is working on, so following the rename is the
    better answer than dropping the selection on the floor.

    Also called by the three Save To Current File handlers, which apply the
    Name field the same way "Ok" does and then rebuild the pulldowns by
    re-parsing the file they just wrote -- so they must re-select *after* that
    reload, and with the name that was actually applied. A save that didn't
    change the name re-selects the same name, which is a harmless no-op.

    item_type is "Project"/"Profile"/"Task", matching process_name_event's own
    vocabulary and the specific_{project,profile,task}_optionmenu attribute names.

    Two steps, in this order:

    1. Point the pulldown at the new name -- as the option string that pulldown
       actually lists it under, which for Project/Profile is not the bare name
       (see _pulldown_option_for_name). It has to be set directly -- nothing
       else does it (process_name_event only ever resets the *other* two, since
       normally the user picking the name is what set this one). Guarded by
       is_updating for the usual reason (see _reset_specific_name_selection):
       assigning .value fires the select's on_change, which would re-enter
       single_*_name_event for the name we're about to hand to
       process_name_event anyway. The option lists must already have been
       rebuilt (refresh_tasker_object_pulldowns) or the new name isn't among
       this select's options yet and the assignment shows blank.

    2. Run the rename through process_name_event, exactly as if the user had
       just picked the new name from that pulldown -- it re-validates the name,
       sets single_{project,profile,task}_name plus the matching
       PrimeItems.program_arguments entry that the Map/Diagram/Tree runs read,
       clears the other two selections (single-item selection is mutually
       exclusive), and refreshes the "Display only ..." label.

    No-op if the pulldown widget doesn't exist yet (defense in depth -- by the
    time an Edit dialog is open the 'Specific Name' tab has long been built).
    """
    optionmenu = getattr(gui, f"specific_{item_type.lower()}_optionmenu", None)
    if optionmenu is None:
        return

    try:
        gui.is_updating = True
        optionmenu.value = _pulldown_option_for_name(optionmenu, item_type, new_name)
        optionmenu.update()
    finally:
        gui.is_updating = False

    # The bare name, not the pulldown's prefixed label -- process_name_event
    # stores it in single_{project,profile,task}_name/PrimeItems.program_arguments,
    # where every consumer expects the name on its own.
    gui.event_handlers.process_name_event(item_type, new_name)


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
        # max_limit = 9999999
        window_title = f"{view_type.capitalize()} View"
        self.gui.event = True  # Set the event flag to True
        logger.info(f"GUI: Switching to {window_title}")

        gui = self.gui
        PrimeItems.view_limit = gui.view_limit if hasattr(gui, "view_limit") else 10000

        # Plug all of our settings back into PrimeItems.program_arguments
        capture_gui_state(gui, {})

        # Start this view generation with a clean slate: found_named_items only ever
        # gets set to True (projects.py/profiles.py/tasks.py/scenes.py, once
        # process_projects_and_their_profiles/its callees find the single Project/
        # Profile/Task/Scene being searched for) -- it's never reset back afterward,
        # since it's meant to stop searching further *within a single run*, not carry
        # over between separate ones. Left stale from an earlier view, a second Map/
        # Diagram/Tree for the same single item (e.g. right after editing it and
        # clicking Ok) would look like it was "already found" and get skipped
        # entirely, even though this run never actually found it yet.
        # Built from primitem.SINGLE_ITEM_SELECTORS rather than written out here, so a
        # newly added single item can't be left out of the reset.
        PrimeItems.found_named_items = initial_found_named_items()

        # Same reasoning for the directory and the running totals -- both accumulate
        # across a single run and are never emptied at the end of one:
        #
        #  - directory_items: add_directory_item only records a name it hasn't seen, and
        #    sets directory_items["current_item"] (which is what makes lineout emit the
        #    "<a id=...>" anchor the directory hyperlink jumps to) *only* on that first
        #    sighting.  Left populated from an earlier view, every name looks
        #    already-seen, so the second view's hyperlinks point at anchors that were
        #    never written -- clicking a directory entry then goes nowhere.
        #  - grand_totals: straight "+=" accumulation, so a second view reports doubled
        #    Project/Profile/Task/Scene counts.
        #
        # Single Project/Profile/Task views happened to escape the directory half of
        # this because they route through lineout.refresh_our_output, which rebuilds
        # both dicts mid-run; a single Scene never calls it, which is how this surfaced.
        PrimeItems.directory_items = initial_directory_items()
        PrimeItems.grand_totals = initial_grand_totals()

        # Map view
        if view_type == "map":
            if PrimeItems.xml_root is None:
                gui.display_message_box("No XML data loaded! Please select a valid XML file first.", "Orange")
                return

            ui.notify(f"Loading {window_title}.  Please stand by ...", type="info", timeout=1000)
            ui.update()  # Force immediate UI update to show notification

            # 1. Clear out stale error codes before starting execution paths
            PrimeItems.error_code = 0
            PrimeItems.error_msg = ""

            # Refresh our output_lines object to ensure we have a clean slate for the new map generation.
            PrimeItems.output_lines.output_lines.clear()
            output_the_front_matter()
            PrimeItems.task_action_warnings = {}

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
            output_length = len(PrimeItems.output_lines.output_lines)

            # Clear out our inline data to free up memory for the GUI display, since we no longer need it.
            PrimeItems.output_lines.output_lines.clear()

            # Display the map in its own browser window/tab rather than the main window.
            _open_popout_window("/popout/map", getattr(gui, "open_view_in_new_window", False))

            # Check for hard stop limit and notify user if output was truncated
            if output_length > gui.view_limit:
                gui.display_message_box(
                    f"Map view truncated {output_length} lines to {gui.view_limit} lines due to view limit.",
                    "Orange",
                )
            gui.display_message_box("Map View opened in a new browser window.", "Green")

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

                    # Check if an entry-point processing failure occurred (e.g. check_limit() in
                    # diagram.py tripping the view_limit) during outline_the_configuration(). Unlike
                    # the "map" branch above, this used to go unchecked: on failure, network_map()
                    # (diagram.py) skips writing DIAGRAM_FILE and computing PrimeItems.diagram_connectors
                    # entirely, so the popout below would silently reopen whatever stale diagram (and
                    # stale/absent connector data) happened to already be on disk from an earlier,
                    # successful run -- which looks like a normal diagram but whose connectors no
                    # longer highlight anything when clicked, with no indication anything went wrong.
                    if getattr(PrimeItems, "error_code", 0) > 0:
                        gui.display_message_box(f"Diagram processing error: {PrimeItems.error_msg}", "Orange")
                        PrimeItems.error_code = 0
                        PrimeItems.error_msg = ""
                        return

                    # Display the diagram in its own browser window/tab rather than the main window.
                    _open_popout_window("/popout/diagram", getattr(gui, "open_view_in_new_window", False))
                    gui.display_message_box("Diagram View opened in a new browser window.", "Green")
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

    def clear_view_event(self: "MapTaskerEventHandlers") -> None:
        """Clears the current view and resets the textview, closing any open Map/Diagram popout tabs."""
        if hasattr(self.gui, "content_container") and self.gui.content_container:
            self.gui.content_container.clear()

        # Drop the references to the views that were just deleted along with those
        # elements. Everything that reaches back into a rendered view guards on those
        # references (handle_color_pick_event's live re-colouring, clear_event's
        # un-highlighting), so leaving the dead objects here left them all working on
        # elements that no longer exist. Back to the "no view rendered" state MyGui
        # starts in (see guiwins.py). The popouts are closed just below, which is what
        # invalidates the views rendered into them too.
        forget_views(self.gui)

        # Close every Map/Diagram popout window this window opened (tracked in
        # window.mapTaskerPopouts, see _open_popout_window() above). Mirrors the cleanup done by
        # get_rid_of_windows_and_exit() in guiwins.py, but without shutting the server down.
        ui.run_javascript(
            "(window.mapTaskerPopouts || []).forEach(w => { try { if (w && !w.closed) w.close(); } "
            "catch (e) {} }); window.mapTaskerPopouts = [];",
        )
        ui.notify("View cleared.", type="info", position="bottom")

    # ==========================================
    # 3. INPUT & DROPDOWN EVENTS
    # ==========================================
    def detail_selected_event(self: "MapTaskerEventHandlers", event_value: Event) -> None:
        """
        NICEGUI PARADIGM SHIFT:
        Dropdown (ui.select) on_change events automatically pass an 'event' object.
        The new selected value is stored in `event`.
        """
        if self.gui.is_updating:
            return

        if isinstance(event_value, int):
            self.gui.display_detail_level = str(event_value)
        elif isinstance(event_value, str) and event_value.isdigit():
            self.gui.display_detail_level = event_value
        else:
            self.gui.display_detail_level = event_value.value
        self.gui.is_updating = True

        self.gui.sidebar_detail_option.value = str(self.gui.display_detail_level)
        self.gui.sidebar_detail_option.update()
        self.gui.is_updating = False

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
        update_analysis_button_color(self.gui)
        ai_apikey = "Set" if getattr(self.gui, "ai_apikey") else "Not Set"
        self.gui.ai_apikey_and_model_lbl.text = (
            f"{getattr(self.gui, 'ai_name', '')} API Key: {ai_apikey}, Model: {self.gui.ai_model}"
        )
        self.gui.ai_apikey_and_model_lbl.update()

    # ==========================================
    # 4. TEXT VIEW CONTROLS
    # ==========================================

    def clear_event(self, view_name: str = "mapview") -> None:
        """Clears the search input and un-highlights all matches left by search_event."""
        # Every open view, not just the newest: with "Open View In New Window" several
        # Map/Diagram windows can be up at once, each with its own highlighted matches.
        for textview in live_views(self.gui):
            self._clear_one_view(textview)

    def _clear_one_view(self, textview: object) -> None:
        """Clears one rendered view's search box and un-highlights its matches."""
        if hasattr(textview, "search_input"):
            textview.search_input.set_value("")

        if hasattr(textview, "scroll_area"):
            # Mirrors the "clearPreviousHighlights" routine inside NiceGuiTextView.search_event:
            # unwrap every '.search-highlight' span back into a plain text node, descending into
            # Shadow DOM roots too since that's where the highlighted matches actually live.
            ui.run_javascript(f"""
                const outerContainer = document.getElementById("c{textview.scroll_area.id}");
                if (!outerContainer) return;
                const container = outerContainer.querySelector('.q-scrollarea__content') || outerContainer;

                function clearHighlights(root) {{
                    const highlights = root.querySelectorAll ? root.querySelectorAll('.search-highlight') : [];
                    highlights.forEach(el => {{
                        const textNode = document.createTextNode(el.textContent);
                        el.parentNode.replaceChild(textNode, el);
                    }});
                    const children = root.querySelectorAll ? root.querySelectorAll('*') : [];
                    children.forEach(child => {{
                        if (child.shadowRoot) clearHighlights(child.shadowRoot);
                    }});
                }}
                clearHighlights(container);

                // Also turn off any Diagram-view connector highlighting left by clicking a connector.
                container.querySelectorAll('.connector-highlight').forEach(el => {{
                    el.classList.remove('connector-highlight');
                }});
            """)

        ui.notify(f"Cleared search highlights in {view_name}.", type="info")

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

        if name_entered in ["No projects found", "No profiles found", "No tasks found", "No scenes found"]:
            the_view.display_message_box("Selection ignored.", "Orange")
            name_entered = "None"
        else:
            if the_view.check_name(name_entered, my_name):
                # The selections are mutually exclusive: clear every single_xxx_name
                # (on the view and in program_arguments) and every found-flag, then set
                # just the one the user picked, below.
                clear_single_item_names(the_view)

                # Reset every pulldown except the one just picked from.  is_updating
                # must be set first -- assigning .value fires the on_change handlers.
                the_view.is_updating = True
                reset_single_item_pulldowns(the_view, except_for=my_name)

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

    def single_scene_name_event(self, name_selected: str) -> None:
        """Generates a single Scene name event."""
        if hasattr(self.gui, "is_updating") and self.gui.is_updating:
            return  # Skip processing if we're in the middle of an update
        self.process_single_name_event("Scene", name_selected)

    def open_edit_task_dialog_event(self) -> None:
        """Opens the Edit Task dialog for the currently selected single Task name."""
        the_view = self.gui
        task_name = getattr(the_view, "single_task_name", "")
        if not task_name:
            ui.notify("Select a single Task first (Task pulldown above).", type="warning")
            return

        edited_task = taskedit.load_task_for_edit(task_name)
        if edited_task is None:
            ui.notify(f"Could not find Task '{task_name}'.", type="negative")
            return

        build_edit_task_dialog(the_view, edited_task)

    def rename_task_event(
        self,
        edited_task: taskedit.EditableTask,
        field_refs: dict,
        title_label: ui.label,
    ) -> None:
        """Opens the Rename prompt for this Task, nested inside Edit Task -- see
        build_rename_dialog. Backs the "Rename" button; mirrors
        rename_profile_event/rename_project_event. The dialog's own Name field
        is read-only, so the prompt is where the new name comes from.
        """
        build_rename_dialog(
            self.gui,
            "Task",
            edited_task.task_element.findtext("nme", ""),
            lambda new_name, rename_dialog: self.confirm_rename_task_event(
                edited_task,
                field_refs,
                title_label,
                new_name,
                rename_dialog,
            ),
        )

    def confirm_rename_task_event(
        self,
        edited_task: taskedit.EditableTask,
        field_refs: dict,
        title_label: ui.label,
        new_name: str,
        rename_dialog: ui.dialog,
    ) -> None:
        """Validates the name typed into the Rename prompt and, if it's good,
        renames the Task in the live in-memory backup right away (see
        taskedit.rename_task_in_live_tree), then refreshes the pulldowns and
        re-selects the Task under its new name, so it stays the current single
        Task and its pulldown follows the rename (see _select_renamed_item).
        Backs the prompt's "Rename" button; mirrors
        confirm_rename_profile_event. The prompt stays open on any error, with
        what was typed still in it to fix.

        Renames *only* the name, and leaves the Edit Task dialog open: it holds
        far more in-progress state than a name (every action's arguments, plus
        any action Add/Copy/Move/Delete already applied to the working copy),
        and closing here would throw the argument edits away. So Rename is a
        self-contained commit of one field the user can keep editing around --
        the title, the read-only Name field and the default export path are all
        brought up to date, and everything else stays pending until Ok/Save.
        """
        errors = taskedit.apply_task_rename(edited_task, new_name)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        old_name = taskedit.rename_task_in_live_tree(edited_task)
        refresh_tasker_object_pulldowns(self.gui)
        _select_renamed_item(self.gui, "Task", new_name)

        title_label.set_text(f"Edit Task: {new_name}")
        # Ok/Save still read this field and apply whatever is in it, so leaving
        # the pre-rename name sitting there would let the next Ok rename the
        # Task straight back.
        field_refs["name"].value = new_name
        # Only re-derive the export path if it's still the one this dialog
        # defaulted to for the old name -- a path the user typed themselves is
        # their choice and shouldn't be silently rewritten by a rename.
        save_path_field = field_refs.get("save_path")
        if save_path_field is not None and save_path_field.value == taskedit.default_save_path(old_name):
            save_path_field.value = taskedit.default_save_path(new_name)

        ui.notify(f"Renamed to '{new_name}'.", type="positive")
        rename_dialog.close()

    def delete_task_event(self, edited_task: taskedit.EditableTask, dialog: ui.dialog) -> None:
        """Opens the Delete Task confirmation dialog, nested inside Edit Task --
        see build_delete_task_dialog. Mirrors delete_profile_event/delete_project_event.
        """
        build_delete_task_dialog(self.gui, edited_task, dialog)

    def confirm_delete_task_event(
        self,
        task_name: str,
        confirm_dialog: ui.dialog,
        parent_dialog: ui.dialog,
    ) -> None:
        """Deletes the Task, along with every reference to it from the Projects
        that own it and the Profiles that run it (see taskedit.delete_task) --
        then refreshes the pulldowns, resets the now-stale single-name selection,
        and closes both dialogs. Backs the confirmation dialog's "Delete Task"
        button; mirrors confirm_delete_profile_event. Both dialogs stay open on
        error so nothing is lost.

        The selection reset is required, not cosmetic: the Task pulldown is still
        pointing at the name just deleted, and leaving it there would let Edit
        Task reopen on a Task that no longer resolves.
        """
        errors = taskedit.delete_task(task_name)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        refresh_tasker_object_pulldowns(self.gui)
        _reset_specific_name_selection(self.gui)

        ui.notify(f"Deleted Task '{task_name}'.", type="positive")
        confirm_dialog.close()
        parent_dialog.close()

    def save_edited_task_event(
        self,
        edited_task: taskedit.EditableTask,
        field_refs: dict,
        dialog: ui.dialog,
    ) -> None:
        """Validates and applies the Edit Task dialog's field values, then writes the
        edited Task out as a standalone .tsk.xml file. Dialog stays open on any error
        so the user's in-progress edits aren't lost.
        """
        arg_values = _task_arg_values(field_refs)

        errors = taskedit.apply_edits_to_task(
            edited_task,
            field_refs["name"].value,
            field_refs["priority"].value,
            arg_values,
        )
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        save_path = field_refs["save_path"].value

        def _write() -> None:
            try:
                taskedit.write_standalone_task_xml(edited_task, save_path)
            except OSError as e:
                ui.notify(f"Could not save file: {e}", type="negative")
                return

            taskedit.apply_edited_task_to_live_tree(edited_task)

            ui.notify(f"Saved to {save_path}", type="positive")
            dialog.close()

        # Unlike Add Task's Save, this export had no up-front save_path_exists
        # check (see _validate_and_apply_new_task) -- confirm rather than clobber.
        if taskedit.save_path_exists(save_path):
            build_overwrite_confirm_dialog(f"'{save_path}'", _write)
            return
        _write()

    def keep_edited_task_event(
        self,
        edited_task: taskedit.EditableTask,
        field_refs: dict,
        dialog: ui.dialog,
    ) -> None:
        """Validates and applies the Edit Task dialog's field values into the live
        in-memory backup (same as Save's apply_edited_task_to_live_tree), without
        writing a standalone file or touching Android, then closes the dialog --
        backs the "Ok" button, which keeps the edit for this session only. Dialog
        stays open on any error so the user's in-progress edits aren't lost.
        """
        if not _apply_edited_task(edited_task, field_refs):
            return
        ui.notify("Changes kept.", type="positive")
        dialog.close()

    def save_edited_task_to_current_file_event(
        self,
        edited_task: taskedit.EditableTask,
        field_refs: dict,
        dialog: ui.dialog,
    ) -> None:
        """Validates and applies the Edit Task dialog's field values (same as
        Ok), then writes the *entire* current backup -- not just this Task --
        out to a new, timestamped copy of whatever file it was loaded from
        (see maputil2.write_full_backup_to_current_file) and switches the app
        over to that copy (see _reload_saved_copy_and_refresh) -- the original
        file is left untouched. Backs the "Save To Current File" button.
        Dialog stays open on any error so the user's in-progress edits aren't
        lost.

        The Name field is applied here just as "Ok" applies it, so this can be a
        rename too -- and the reload rebuilds the pulldowns from the file, which
        would leave the Task pulldown on the old name. Re-selects the Task under
        whatever name was actually applied, after the reload, the same way the
        Rename button does (see _select_renamed_item).
        """
        if not _apply_edited_task(edited_task, field_refs):
            return
        success, result = write_full_backup_to_current_file()
        if not success:
            ui.notify(f"Could not save to current file: {result}", type="negative")
            return
        reload_ok, reload_error = _reload_saved_copy_and_refresh(self.gui, result)
        if not reload_ok:
            ui.notify(f"Saved a copy to {result}, but failed to load it: {reload_error}", type="warning")
            return
        # Read back off the element rather than the Name field: this is the name
        # apply_edits_to_task actually wrote (stripped), i.e. the one now in the
        # reloaded tables and the pulldown's options.
        if applied_name := edited_task.task_element.findtext("nme", ""):
            _select_renamed_item(self.gui, "Task", applied_name)
        ui.notify(f"Saved a copy to {result} and loaded it. The original file was left unchanged.", type="positive")
        dialog.close()

    def open_save_to_android_dialog_event(
        self,
        edited_task: taskedit.EditableTask,
        field_refs: dict,
        parent_dialog: ui.dialog,
        on_created: Callable[[str], None] | None = None,
    ) -> None:
        """Opens the IP/port prompt for importing this Task into Tasker on the Android device."""
        build_save_to_android_dialog(self.gui, edited_task, field_refs, parent_dialog, on_created)

    async def save_task_to_android_event(
        self,
        edited_task: taskedit.EditableTask,
        field_refs: dict,
        android_field_refs: dict,
        android_dialog: ui.dialog,
        parent_dialog: ui.dialog,
        on_created: Callable[[str], None] | None = None,
    ) -> None:
        """Validates and applies the parent dialog's field values (same as a local
        Save), pings the Android device to confirm it's reachable (same check
        fetch_backup_event uses), and then imports the edited Task into Tasker on
        the device. The android prompt dialog stays open on any error so the
        user's connection details aren't lost; on success both it and the parent
        Edit/Add Task dialog are closed.

        on_created, if given, is called with the new Task's id once it's
        registered -- see build_add_task_dialog's on_task_created.
        """
        # A brand-new Task (Add Task) was never registered onto the live tree in
        # the first place -- computed before anything below can change task_id,
        # so it stays accurate for the registration step at the end.
        is_new_task = edited_task.task_id not in PrimeItems.tasker_root_elements.get("all_tasks", {})

        arg_values = _task_arg_values(field_refs)

        errors = taskedit.apply_edits_to_task(
            edited_task,
            field_refs["name"].value,
            field_refs["priority"].value,
            arg_values,
        )
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        if is_new_task and taskedit.task_name_exists(field_refs["name"].value.strip()):
            ui.notify(
                f"A Task named '{field_refs['name'].value.strip()}' already exists in this backup. "
                "Choose a different name.",
                type="negative",
            )
            return

        ip_address = android_field_refs["ip_address"].value.strip()
        ip_port = android_field_refs["ip_port"].value.strip()

        if not await ping_android_device(self.gui, ip_address, ip_port):
            return

        # Reuse a cached API key for this same device -- skips its GET /api/auth
        # confirmation prompt. taskedit.save_task_to_android falls back to fetching
        # a fresh one (and retries) if the device has since rejected it.
        cached_key = (
            getattr(self.gui, "android_auth_key", "")
            if getattr(self.gui, "android_auth_key_ipaddr", "") == ip_address
            and getattr(self.gui, "android_auth_key_port", "") == ip_port
            else ""
        )

        task_name = field_refs["name"].value.strip()
        return_code, result, auth_key = taskedit.save_task_to_android(
            edited_task,
            ip_address,
            ip_port,
            task_name,
            cached_key,
        )
        if return_code != 0:
            ui.notify(f"Could not save to Android device: {result}", type="negative")
            return

        # Cache the auth key (keyed to this ip/port) so the next save skips the
        # device's connection-authorization prompt entirely.
        self.gui.android_auth_key = auth_key
        self.gui.android_auth_key_ipaddr = ip_address
        self.gui.android_auth_key_port = ip_port

        # Remember the connection details for next time, same as the Get XML dialog does.
        self.gui.android_ipaddr = ip_address
        self.gui.android_port = ip_port

        if is_new_task:
            taskedit.register_new_task(edited_task, task_name)
            if on_created is not None:
                on_created(edited_task.task_id)
        else:
            taskedit.apply_edited_task_to_live_tree(edited_task)
        refresh_tasker_object_pulldowns(self.gui)

        # api/import's 200 response doesn't guarantee Tasker actually committed the
        # Task, so confirm via GET /api/tasks before declaring success. If that
        # check fails, retry the same api/import once more (see
        # taskedit.save_task_to_android_directory's docstring for why a retry,
        # not a different endpoint, is the only fallback that can plausibly help).
        if taskedit.verify_task_on_android(ip_address, ip_port, task_name, auth_key):
            ui.notify("Task Uploaded to Tasker", type="positive")
        else:
            fallback_code, fallback_result = taskedit.save_task_to_android_directory(
                edited_task,
                ip_address,
                ip_port,
                task_name,
                auth_key,
            )
            if fallback_code == 0:
                ui.notify("Task Uploaded to Tasker.", type="positive")
            else:
                ui.notify(
                    f"Unable to upload Task to Tasker: {fallback_result}",
                    type="negative",
                )

        android_dialog.close()
        parent_dialog.close()

    def open_add_project_dialog_event(self) -> None:
        """Opens the Add Project dialog for a brand-new Project. Unlike Add
        Profile/Add Task, there's no "select a parent first" gate -- a
        Project is the top of the hierarchy, so there's nothing to attach it to.
        """
        the_view = self.gui
        # See open_add_task_dialog_event's identical self-healing load: the toolbar's
        # "Current File" only means a filename is known, not that it's been parsed
        # into PrimeItems.xml_root yet.
        if PrimeItems.xml_root is None:
            if not PrimeItems.file_to_get and getattr(the_view, "file", ""):
                PrimeItems.file_to_get = the_view.file
            if not PrimeItems.file_to_get or get_xml(the_view.debug, the_view.appearance_mode) != 0:
                ui.notify("No backup file is currently loaded. Use 'Get Local XML' first.", type="warning")
                return

        new_project = projedit.create_new_project("")
        if isinstance(new_project, str):
            ui.notify(new_project, type="warning")
            return

        build_add_project_dialog(self.gui, new_project)

    def keep_new_project_event(
        self,
        edited_project: projedit.EditableProject,
        field_refs: dict,
        dialog: ui.dialog,
    ) -> None:
        """Validates and applies the Add Project dialog's Name field, registers
        the new Project into the live in-memory backup, then closes the
        dialog -- the Add Project dialog's only save action (no standalone
        file or Save To Android surface, see projedit.py's module docstring).
        Dialog stays open on any error so the user's in-progress work isn't lost.
        """
        name_value = field_refs["name"].value.strip()
        if projedit.project_name_exists(name_value):
            ui.notify(
                f"A Project named '{name_value}' already exists in this backup. Choose a different name.",
                type="negative",
            )
            return

        errors = projedit.apply_edits_to_project(edited_project, name_value)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        _finish_new_project(self.gui, edited_project)

        ui.notify("Project added.", type="positive")
        dialog.close()

    def open_edit_project_dialog_event(self) -> None:
        """Opens the Edit Project dialog for the currently selected single Project name."""
        the_view = self.gui
        project_name = _confirmed_single_project_name(the_view)
        if not project_name:
            ui.notify("Select a single Project first (Project pulldown above).", type="warning")
            return

        edited_project = projedit.load_project_for_edit(project_name)
        if edited_project is None:
            ui.notify(f"Could not find Project '{project_name}'.", type="negative")
            return

        build_edit_project_dialog(the_view, edited_project)

    def rename_project_event(
        self,
        edited_project: projedit.EditableProject,
        dialog: ui.dialog,
    ) -> None:
        """Opens the Rename prompt for this Project, nested inside Edit Project
        -- see build_rename_dialog. Backs the "Rename" button; mirrors
        rename_task_event/rename_profile_event. The dialog's own Name field is
        read-only, so the prompt is where the new name comes from.
        """
        build_rename_dialog(
            self.gui,
            "Project",
            edited_project.project_name,
            lambda new_name, rename_dialog: self.confirm_rename_project_event(
                edited_project,
                new_name,
                rename_dialog,
                dialog,
            ),
        )

    def confirm_rename_project_event(
        self,
        edited_project: projedit.EditableProject,
        new_name: str,
        rename_dialog: ui.dialog,
        parent_dialog: ui.dialog,
    ) -> None:
        """Validates the name typed into the Rename prompt and applies it,
        renaming the Project in the live in-memory backup (moving its
        all_projects entry to the new name -- see
        projedit.rename_project_in_live_tree), making it the current single
        Project under that name (see _select_renamed_item), then closing both
        the prompt and the Edit Project dialog. The prompt stays open on any
        error, with what was typed still in it to fix.

        Closes the Edit Project dialog on success, unlike its Task/Profile
        counterparts, which keep theirs open: those hold a dialog full of
        in-progress editing a rename shouldn't discard, whereas Edit Project's
        remaining content is derived from the name (its title and its "Save as"
        path), and this is the behavior that button has always had.
        """
        old_name = edited_project.project_name

        errors = projedit.apply_edits_to_project(edited_project, new_name)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        projedit.rename_project_in_live_tree(old_name, edited_project)
        refresh_tasker_object_pulldowns(self.gui)
        _select_renamed_item(self.gui, "Project", new_name)

        ui.notify(f"Renamed to '{new_name}'.", type="positive")
        rename_dialog.close()
        parent_dialog.close()

    def save_project_to_current_file_event(
        self,
        edited_project: projedit.EditableProject,
        field_refs: dict,
        dialog: ui.dialog,
    ) -> None:
        """Validates and applies the Edit Project dialog's Name field (same as
        Rename), then writes the *entire* current backup -- not just this
        Project -- out to a new, timestamped copy of whatever file it was
        loaded from (see maputil2.write_full_backup_to_current_file) and
        switches the app over to that copy (see _reload_saved_copy_and_refresh)
        -- the original file is left untouched. Mirrors
        save_edited_profile_to_current_file_event/
        save_edited_task_to_current_file_event. Backs the "Save To Current
        File" button. Dialog stays open on any error so the user's
        in-progress edit isn't lost.

        Follows the rename the same way the Rename button does
        (_select_renamed_item), so the Project stays selected under its new
        name -- but only after the reload, never before: this path replaces
        every table wholesale by re-parsing the file it just wrote (see
        _reload_saved_copy_and_refresh), so a selection made beforehand would
        be pointing at state that no longer exists a moment later. Re-selecting
        matters most here of the three: a Project's identity is its name (see
        rename_project_in_live_tree), so a rename through this button would
        otherwise leave the Project pulldown's .value on a name that's gone.
        """
        old_name = edited_project.project_name
        name_value = field_refs["name"].value.strip()

        errors = projedit.apply_edits_to_project(edited_project, name_value)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        projedit.rename_project_in_live_tree(old_name, edited_project)

        success, result = write_full_backup_to_current_file()
        if not success:
            ui.notify(f"Could not save to current file: {result}", type="negative")
            return
        reload_ok, reload_error = _reload_saved_copy_and_refresh(self.gui, result)
        if not reload_ok:
            ui.notify(f"Saved a copy to {result}, but failed to load it: {reload_error}", type="warning")
            return

        _select_renamed_item(self.gui, "Project", name_value)
        ui.notify(f"Saved a copy to {result} and loaded it. The original file was left unchanged.", type="positive")
        dialog.close()

    def save_project_event(
        self,
        edited_project: projedit.EditableProject,
        field_refs: dict,
        dialog: ui.dialog,
    ) -> None:
        """Writes the Project -- every Profile and Task it owns -- out as a
        standalone .prj.xml file (see projedit.write_standalone_project_xml).
        Backs the "Export Project" button.

        Exports under the Project's current, already-applied name
        (edited_project.project_name) regardless of any not-yet-applied edit
        sitting in the Name field -- unlike Rename, this is a read-only export
        and deliberately doesn't also rename the live Project as a side
        effect; use "Rename" first if the new name should carry through.
        Dialog stays open on any error so the user's in-progress edit isn't lost.
        """
        save_path = field_refs["project_save_path"].value.strip()

        def _write() -> None:
            try:
                projedit.write_standalone_project_xml(edited_project.project_name, save_path)
            except (OSError, ValueError) as e:
                ui.notify(f"Could not save file: {e}", type="negative")
                return

            ui.notify(f"Saved Project '{edited_project.project_name}' to {save_path}", type="positive")
            dialog.close()

        if projedit.save_path_exists(save_path):
            build_overwrite_confirm_dialog(f"'{save_path}'", _write)
            return
        _write()

    def delete_project_event(self, edited_project: projedit.EditableProject, dialog: ui.dialog) -> None:
        """Opens the Delete Project confirmation dialog (Keep Contents / Delete
        Contents), nested inside Edit Project -- see build_delete_project_dialog.
        """
        build_delete_project_dialog(self.gui, edited_project, dialog)

    def keep_contents_delete_project_event(
        self,
        project_name: str,
        confirm_dialog: ui.dialog,
        parent_dialog: ui.dialog,
    ) -> None:
        """Deletes the Project, moving its Profiles/Tasks into 'Base'. Backs
        the confirmation dialog's "Keep Contents" button.
        """
        self._finish_delete_project(
            project_name,
            keep_contents=True,
            confirm_dialog=confirm_dialog,
            parent_dialog=parent_dialog,
        )

    def delete_contents_delete_project_event(
        self,
        project_name: str,
        confirm_dialog: ui.dialog,
        parent_dialog: ui.dialog,
    ) -> None:
        """Deletes the Project and everything it owns. Backs the confirmation
        dialog's "Delete Contents" button.
        """
        self._finish_delete_project(
            project_name,
            keep_contents=False,
            confirm_dialog=confirm_dialog,
            parent_dialog=parent_dialog,
        )

    def _finish_delete_project(
        self,
        project_name: str,
        *,
        keep_contents: bool,
        confirm_dialog: ui.dialog,
        parent_dialog: ui.dialog,
    ) -> None:
        """Shared tail of keep_contents_delete_project_event/
        delete_contents_delete_project_event: applies projedit.delete_project,
        refreshes the pulldowns, resets the (now possibly stale) single-name
        selection, and closes both dialogs. Both dialogs stay open on error
        (e.g. "Base" with keep_contents) so nothing is lost/hidden.
        """
        errors = projedit.delete_project(project_name, keep_contents=keep_contents)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        refresh_tasker_object_pulldowns(self.gui)
        _reset_specific_name_selection(self.gui)

        if keep_contents:
            ui.notify(
                f"Deleted '{project_name}'. Its Profiles and Tasks were moved to '{projedit.BASE_PROJECT_NAME}'.",
                type="positive",
            )
        else:
            ui.notify(f"Deleted '{project_name}' and everything it owned.", type="positive")

        confirm_dialog.close()
        parent_dialog.close()

    def open_edit_profile_dialog_event(self) -> None:
        """Opens the Edit Profile dialog for the currently selected single Profile name."""
        the_view = self.gui
        profile_name = getattr(the_view, "single_profile_name", "")
        if not profile_name:
            ui.notify("Select a single Profile first (Profile pulldown above).", type="warning")
            return

        edited_profile = profedit.load_profile_for_edit(profile_name)
        if edited_profile is None:
            ui.notify(f"Could not find Profile '{profile_name}'.", type="negative")
            return

        build_edit_profile_dialog(the_view, edited_profile)

    def rename_profile_event(
        self,
        edited_profile: profedit.EditableProfile,
        field_refs: dict,
        title_label: ui.label,
    ) -> None:
        """Opens the Rename prompt for this Profile, nested inside Edit Profile
        -- see build_rename_dialog. Backs the "Rename" button; mirrors
        rename_task_event. The dialog's own Name field is read-only, so the
        prompt is where the new name comes from.
        """
        build_rename_dialog(
            self.gui,
            "Profile",
            edited_profile.profile_element.findtext("nme", ""),
            lambda new_name, rename_dialog: self.confirm_rename_profile_event(
                edited_profile,
                field_refs,
                title_label,
                new_name,
                rename_dialog,
            ),
        )

    def confirm_rename_profile_event(
        self,
        edited_profile: profedit.EditableProfile,
        field_refs: dict,
        title_label: ui.label,
        new_name: str,
        rename_dialog: ui.dialog,
    ) -> None:
        """Validates the name typed into the Rename prompt and, if it's good,
        renames the Profile in the live in-memory backup right away (see
        profedit.rename_profile_in_live_tree), then refreshes the pulldowns and
        re-selects the Profile under its new name, so it stays the current
        single Profile and its pulldown follows the rename (see
        _select_renamed_item). Backs the prompt's "Rename" button; mirrors
        confirm_rename_task_event exactly, including leaving the Edit Profile
        dialog open and renaming *only* the name, so the conditions and
        Entry/Exit Task links still being edited stay pending until Ok/Save.
        """
        errors = profedit.apply_profile_rename(edited_profile, new_name)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        old_name = profedit.rename_profile_in_live_tree(edited_profile)
        refresh_tasker_object_pulldowns(self.gui)
        _select_renamed_item(self.gui, "Profile", new_name)

        title_label.set_text(f"Edit Profile: {new_name}")
        # Keeps Ok/Save from re-applying the pre-rename name -- see
        # confirm_rename_task_event's identical note.
        field_refs["name"].value = new_name
        # Only re-derive the export path if it's still this dialog's default for
        # the old name -- see confirm_rename_task_event's identical guard.
        save_path_field = field_refs.get("save_path")
        if save_path_field is not None and save_path_field.value == profedit.default_save_path(old_name):
            save_path_field.value = profedit.default_save_path(new_name)

        ui.notify(f"Renamed to '{new_name}'.", type="positive")
        rename_dialog.close()

    def delete_profile_event(self, edited_profile: profedit.EditableProfile, dialog: ui.dialog) -> None:
        """Opens the Delete Profile confirmation dialog, nested inside Edit
        Profile -- see build_delete_profile_dialog. Mirrors delete_project_event.
        """
        build_delete_profile_dialog(self.gui, edited_profile, dialog)

    def confirm_delete_profile_event(
        self,
        profile_name: str,
        confirm_dialog: ui.dialog,
        parent_dialog: ui.dialog,
    ) -> None:
        """Deletes the Profile -- and only the Profile, its Entry/Exit Tasks are
        kept (see profedit.delete_profile) -- then refreshes the pulldowns,
        resets the now-stale single-name selection, and closes both dialogs.
        Backs the confirmation dialog's "Delete Profile" button; mirrors
        _finish_delete_project. Both dialogs stay open on error so nothing is lost.

        The selection reset is required, not cosmetic: the Profile pulldown is
        still pointing at the name just deleted, and leaving it there would let
        Edit Profile reopen on a Profile that no longer resolves.
        """
        errors = profedit.delete_profile(profile_name)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        refresh_tasker_object_pulldowns(self.gui)
        _reset_specific_name_selection(self.gui)

        ui.notify(f"Deleted Profile '{profile_name}'. Its Tasks were kept.", type="positive")
        confirm_dialog.close()
        parent_dialog.close()

    def open_add_profile_dialog_event(self) -> None:
        """Opens the Add Profile dialog for a brand-new Profile, attached to the
        currently selected single Project (see the Project pulldown in the
        Specific Name tab, mirrors open_add_task_dialog_event exactly). A
        Project must already be selected -- the new Profile is attached
        directly to it (added to its <pids>, see profedit.add_profile_to_project)
        rather than picked from within the dialog, so there's no other way to
        know which Project it belongs to.
        """
        the_view = self.gui
        project_name = _confirmed_single_project_name(the_view)
        if not project_name:
            ui.notify("Select a single Project first (Project pulldown above).", type="warning")
            return

        # See open_add_task_dialog_event's identical self-healing load: the toolbar's
        # "Current File" only means a filename is known, not that it's been parsed
        # into PrimeItems.xml_root yet.
        if PrimeItems.xml_root is None:
            if not PrimeItems.file_to_get and getattr(the_view, "file", ""):
                PrimeItems.file_to_get = the_view.file
            if not PrimeItems.file_to_get or get_xml(the_view.debug, the_view.appearance_mode) != 0:
                ui.notify("No backup file is currently loaded. Use 'Get Local XML' first.", type="warning")
                return

        new_profile = profedit.create_new_profile("")
        if isinstance(new_profile, str):
            ui.notify(new_profile, type="warning")
            return

        build_add_profile_dialog(self.gui, new_profile, target_project_name=project_name)

    def link_task_to_profile_event(
        self,
        edited_profile: profedit.EditableProfile,
        link_type: str,
        task_name: str,
    ) -> None:
        """Links an existing Task (by name) to the Profile as its Entry or Exit Task."""
        if not task_name:
            ui.notify("Choose a Task first.", type="warning")
            return
        resolved = taskedit.resolve_task_by_name(task_name)
        if resolved is None:
            ui.notify(f"Could not find Task '{task_name}'.", type="negative")
            return
        task_id, _ = resolved
        profedit.link_task_to_profile(edited_profile, task_id, link_type)

    def unlink_task_from_profile_event(self, edited_profile: profedit.EditableProfile, link_type: str) -> None:
        """Unlinks the Profile's current Entry or Exit Task."""
        profedit.unlink_task_from_profile(edited_profile, link_type)

    def open_add_task_for_profile_link_event(
        self,
        edited_profile: profedit.EditableProfile,
        link_type: str,
        on_linked: Callable[[], None],
    ) -> None:
        """Opens the Add Task dialog nested inside Edit/Add Profile's Entry/Exit
        Task picker -- the alternative to link_task_to_profile_event picking an
        existing Task. On successful creation (Ok/Save/Save To Android in that
        nested dialog), the new Task is linked in as this Profile's Entry/Exit
        Task and on_linked (the picker's own render_task_links) is called to
        refresh the display -- see build_add_task_dialog's on_task_created.
        """
        new_task = taskedit.create_new_task("", "100")
        if isinstance(new_task, str):
            ui.notify(new_task, type="warning")
            return

        def link_new_task(task_id: str) -> None:
            profedit.link_task_to_profile(edited_profile, task_id, link_type)
            on_linked()

        build_add_task_dialog(self.gui, new_task, on_task_created=link_new_task)

    def set_profile_enabled_event(self, edited_profile: profedit.EditableProfile, enabled: bool) -> None:
        """Enables or disables the Profile being edited."""
        profedit.set_profile_enabled(edited_profile, enabled)

    def add_condition_to_profile_event(self, edited_profile: profedit.EditableProfile, cond_type: str) -> None:
        """Adds a new condition (Time/Day/App/Loc) to the Profile being edited."""
        if not cond_type:
            ui.notify("Choose a condition type first.", type="warning")
            return
        result = profedit.add_condition_to_profile(edited_profile, cond_type)
        if isinstance(result, list):
            for error in result:
                ui.notify(error, type="negative")

    def remove_condition_from_profile_event(self, edited_profile: profedit.EditableProfile, cond_index: int) -> None:
        """Removes a condition from the Profile being edited and renumbers the rest."""
        profedit.remove_condition_from_profile(edited_profile, cond_index)

    def add_event_condition_to_profile_event(self, edited_profile: profedit.EditableProfile, event_key: str) -> None:
        """Synthesizes and appends a new Event condition to the Profile being edited."""
        if not event_key:
            ui.notify("Choose an Event type first.", type="warning")
            return
        result = profedit.add_event_condition_to_profile(edited_profile, event_key)
        if isinstance(result, list):
            for error in result:
                ui.notify(error, type="negative")
            return
        _notify_if_plugin_needs_configuration(result.condition_element, profedit.get_condition_display_name(result))

    def add_state_condition_to_profile_event(self, edited_profile: profedit.EditableProfile, state_key: str) -> None:
        """Synthesizes and appends a new State condition to the Profile being edited."""
        if not state_key:
            ui.notify("Choose a State type first.", type="warning")
            return
        result = profedit.add_state_condition_to_profile(edited_profile, state_key)
        if isinstance(result, list):
            for error in result:
                ui.notify(error, type="negative")
            return
        _notify_if_plugin_needs_configuration(result.condition_element, profedit.get_condition_display_name(result))

    def add_app_entry_event(self, edited_profile: profedit.EditableProfile, cond_index: int) -> None:
        """Adds a blank app entry to an App condition being edited."""
        condition = profedit.find_condition(edited_profile, cond_index)
        if condition is not None:
            profedit.add_app_entry(condition)

    def remove_app_entry_event(
        self,
        edited_profile: profedit.EditableProfile,
        cond_index: int,
        entry_index: int,
    ) -> None:
        """Removes one app entry from an App condition being edited."""
        condition = profedit.find_condition(edited_profile, cond_index)
        if condition is not None:
            profedit.remove_app_entry(condition, entry_index)

    def save_edited_profile_event(
        self,
        edited_profile: profedit.EditableProfile,
        field_refs: dict,
        dialog: ui.dialog,
    ) -> None:
        """Validates and applies the Edit Profile dialog's field values, then writes
        the edited Profile out as a standalone .prf.xml file. Dialog stays open on
        any error so the user's in-progress edits aren't lost.
        """
        _link_pending_task_pickers(edited_profile, field_refs)
        condition_values = _profile_condition_values(field_refs)

        errors = profedit.apply_edits_to_profile(edited_profile, field_refs["name"].value, condition_values)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        save_path = field_refs["save_path"].value

        def _write() -> None:
            try:
                profedit.write_standalone_profile_xml(edited_profile, save_path)
            except OSError as e:
                ui.notify(f"Could not save file: {e}", type="negative")
                return

            profedit.apply_edited_profile_to_live_tree(edited_profile)

            ui.notify(f"Saved to {save_path}", type="positive")
            dialog.close()

        # Unlike Add Profile's Save, this export had no up-front save_path_exists
        # check (see _validate_and_apply_new_profile) -- confirm rather than clobber.
        if profedit.save_path_exists(save_path):
            build_overwrite_confirm_dialog(f"'{save_path}'", _write)
            return
        _write()

    def keep_edited_profile_event(
        self,
        edited_profile: profedit.EditableProfile,
        field_refs: dict,
        dialog: ui.dialog,
    ) -> None:
        """Validates and applies the Edit Profile dialog's field values into the
        live in-memory backup (same as Save's apply_edited_profile_to_live_tree),
        without writing a standalone file or touching Android, then closes the
        dialog -- backs the "Ok" button, which keeps the edit for this session
        only. Dialog stays open on any error so the user's in-progress edits aren't lost.
        """
        if not _apply_edited_profile(edited_profile, field_refs):
            return
        ui.notify("Changes kept.", type="positive")
        dialog.close()

    def save_edited_profile_to_current_file_event(
        self,
        edited_profile: profedit.EditableProfile,
        field_refs: dict,
        dialog: ui.dialog,
    ) -> None:
        """Validates and applies the Edit Profile dialog's field values (same as
        Ok), then writes the *entire* current backup -- not just this Profile
        -- out to a new, timestamped copy of whatever file it was loaded from
        (see maputil2.write_full_backup_to_current_file) and switches the app
        over to that copy (see _reload_saved_copy_and_refresh) -- the original
        file is left untouched. Backs the "Save To Current File" button.
        Dialog stays open on any error so the user's in-progress edits aren't
        lost.

        Re-selects the Profile under whatever name was actually applied, after
        the reload -- same reasoning as
        save_edited_task_to_current_file_event's.
        """
        if not _apply_edited_profile(edited_profile, field_refs):
            return
        success, result = write_full_backup_to_current_file()
        if not success:
            ui.notify(f"Could not save to current file: {result}", type="negative")
            return
        reload_ok, reload_error = _reload_saved_copy_and_refresh(self.gui, result)
        if not reload_ok:
            ui.notify(f"Saved a copy to {result}, but failed to load it: {reload_error}", type="warning")
            return
        if applied_name := edited_profile.profile_element.findtext("nme", ""):
            _select_renamed_item(self.gui, "Profile", applied_name)
        ui.notify(f"Saved a copy to {result} and loaded it. The original file was left unchanged.", type="positive")
        dialog.close()

    def save_new_profile_event(
        self,
        edited_profile: profedit.EditableProfile,
        field_refs: dict,
        dialog: ui.dialog,
    ) -> None:
        """Validates and applies the Add Profile dialog's field values, then writes
        the new Profile out as a standalone .prf.xml file. Mirrors
        save_new_task_event exactly. Dialog stays open on any error so the user's
        in-progress work isn't lost.
        """
        ok, name_value, project_name = _validate_and_apply_new_profile(edited_profile, field_refs, check_save_path=True)
        if not ok:
            return

        save_path = field_refs["save_path"].value.strip()
        try:
            profedit.write_standalone_profile_xml(edited_profile, save_path)
        except OSError as e:
            ui.notify(f"Could not save file: {e}", type="negative")
            return

        _finish_new_profile(self.gui, edited_profile, name_value, project_name)

        ui.notify(f"Saved to {save_path}", type="positive")
        dialog.close()

    def keep_new_profile_event(
        self,
        edited_profile: profedit.EditableProfile,
        field_refs: dict,
        dialog: ui.dialog,
    ) -> None:
        """Validates and applies the Add Profile dialog's field values, then
        registers the new Profile into the live in-memory backup (same as Save's
        register_new_profile), without writing a standalone file, then closes the
        dialog -- backs the "Ok" button, which keeps the new Profile for this
        session only. Mirrors keep_new_task_event exactly. Dialog stays open on
        any error so the user's in-progress work isn't lost. Still checks the
        Profile name for a conflict and that a Project was chosen (needed for
        live-tree registration and Project attachment to make sense -- see
        profedit.add_profile_to_project) but not the save path, since no file
        is written.
        """
        ok, name_value, project_name = _validate_and_apply_new_profile(edited_profile, field_refs)
        if not ok:
            return

        _finish_new_profile(self.gui, edited_profile, name_value, project_name)

        ui.notify(
            "Profile kept for this session only -- use 'Save To Current File' to keep it permanently.",
            type="positive",
        )
        dialog.close()

    def save_new_profile_to_current_file_event(
        self,
        edited_profile: profedit.EditableProfile,
        field_refs: dict,
        dialog: ui.dialog,
    ) -> None:
        """Validates and applies the Add Profile dialog's field values,
        registers the new Profile into the live in-memory backup and attaches
        it to its Project, then writes the *entire* current backup out to a
        new, timestamped copy of whatever file it was loaded from (see
        maputil2.write_full_backup_to_current_file) and switches the app over
        to that copy (see _reload_saved_copy_and_refresh) -- the original file
        is left untouched -- unlike Save, which exports just this one Profile
        as a standalone file. Backs the "Save To Current File" button. Dialog
        stays open on any error so the user's in-progress work isn't lost; a
        failed disk write is reported but doesn't undo the registration
        already done (same as Ok, which never touches disk at all).
        """
        ok, name_value, project_name = _validate_and_apply_new_profile(edited_profile, field_refs)
        if not ok:
            return

        _finish_new_profile(self.gui, edited_profile, name_value, project_name)

        success, result = write_full_backup_to_current_file()
        if not success:
            ui.notify(f"Could not save to current file: {result}", type="negative")
            return
        reload_ok, reload_error = _reload_saved_copy_and_refresh(self.gui, result)
        if not reload_ok:
            ui.notify(f"Saved a copy to {result}, but failed to load it: {reload_error}", type="warning")
            return
        ui.notify(f"Saved a copy to {result} and loaded it. The original file was left unchanged.", type="positive")
        dialog.close()

    def open_save_profile_to_android_dialog_event(
        self,
        edited_profile: profedit.EditableProfile,
        field_refs: dict,
        parent_dialog: ui.dialog,
    ) -> None:
        """Opens the IP/port prompt for importing this Profile into Tasker on the Android device."""
        build_save_profile_to_android_dialog(self.gui, edited_profile, field_refs, parent_dialog)

    async def save_profile_to_android_event(
        self,
        edited_profile: profedit.EditableProfile,
        field_refs: dict,
        android_field_refs: dict,
        android_dialog: ui.dialog,
        parent_dialog: ui.dialog,
    ) -> None:
        """Validates and applies the parent dialog's field values (same as a local
        Save), pings the Android device to confirm it's reachable, and then writes
        the edited Profile onto the device's storage under /Tasker/profiles (see
        profedit.save_profile_to_android -- this is a file write, not a live import
        into Tasker, unlike save_task_to_android_event's api/import; /upload needs
        no auth key, so there's no cached-key handling here the way that one has).
        A Profile also needs registering into the live tree (see the is_new_profile
        branch below) -- Tasks don't need the Project-attachment step a Profile does.
        """
        _link_pending_task_pickers(edited_profile, field_refs)
        condition_values = _profile_condition_values(field_refs)

        errors = profedit.apply_edits_to_profile(edited_profile, field_refs["name"].value, condition_values)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        # Add Profile's dialog (unlike Edit Profile's) has a "target_project_name"
        # entry -- its presence is how this shared handler tells a brand-new,
        # not-yet-registered Profile apart from one already in the backup, without
        # threading an extra parameter through every caller.
        is_new_profile = "target_project_name" in field_refs
        project_name = field_refs.get("target_project_name", "") if is_new_profile else ""
        if is_new_profile:
            new_profile_errors = []
            if profedit.profile_name_exists(field_refs["name"].value.strip()):
                new_profile_errors.append(
                    f"A Profile named '{field_refs['name'].value.strip()}' already exists in this backup. "
                    "Choose a different name.",
                )
            if not project_name:
                new_profile_errors.append(
                    "Choose a Project first -- a Profile has to belong to one to show up anywhere in the app.",
                )
            new_profile_errors.extend(profedit.validate_new_profile_requirements(edited_profile))
            if new_profile_errors:
                for error in new_profile_errors:
                    ui.notify(error, type="negative")
                return

        ip_address = android_field_refs["ip_address"].value.strip()
        ip_port = android_field_refs["ip_port"].value.strip()

        if not await ping_android_device(self.gui, ip_address, ip_port):
            return

        profile_name = field_refs["name"].value.strip()

        def _upload() -> None:
            return_code, result = profedit.save_profile_to_android(edited_profile, ip_address, ip_port, profile_name)
            if return_code != 0:
                ui.notify(f"Could not save to Android device: {result}", type="negative")
                return

            # Remember the connection details for next time, same as the Get XML dialog does.
            self.gui.android_ipaddr = ip_address
            self.gui.android_port = ip_port

            if is_new_profile:
                profedit.register_new_profile(edited_profile, profile_name)
                profedit.add_profile_to_project(edited_profile, project_name)
            else:
                profedit.apply_edited_profile_to_live_tree(edited_profile)
            refresh_tasker_object_pulldowns(self.gui)

            ui.notify(f"Profile saved to Android device at {result}", type="positive")
            android_dialog.close()
            parent_dialog.close()

        # See save_project_to_android_event's identical check -- /upload clobbers silently.
        device_path = profedit.android_profile_path(profile_name)
        exists = file_exists_on_android(ip_address, ip_port, device_path)
        if exists is not False:
            build_overwrite_confirm_dialog(
                f"'{device_path}' on the Android device",
                _upload,
                unknown=exists is None,
            )
            return
        _upload()

    def open_save_project_to_android_dialog_event(
        self,
        edited_project: projedit.EditableProject,
        parent_dialog: ui.dialog,
    ) -> None:
        """Opens the IP/port prompt for writing this Project onto the Android device."""
        build_save_project_to_android_dialog(self.gui, edited_project, parent_dialog)

    async def save_project_to_android_event(
        self,
        edited_project: projedit.EditableProject,
        android_field_refs: dict,
        android_dialog: ui.dialog,
        parent_dialog: ui.dialog,
    ) -> None:
        """Pings the Android device to confirm it's reachable, then writes the
        Project -- every Profile and Task it owns -- onto the device's storage
        under /Tasker/projects (see projedit.save_project_to_android). Unlike
        save_profile_to_android_event, there's no field-edit/apply step first --
        a Project has no separate editable model, and this exports under its
        current, already-applied name, same as save_project_event's local export.
        """
        ip_address = android_field_refs["ip_address"].value.strip()
        ip_port = android_field_refs["ip_port"].value.strip()

        if not await ping_android_device(self.gui, ip_address, ip_port):
            return

        def _upload() -> None:
            return_code, result = projedit.save_project_to_android(edited_project.project_name, ip_address, ip_port)
            if return_code != 0:
                ui.notify(f"Could not save to Android device: {result}", type="negative")
                return

            # Remember the connection details for next time, same as the Get XML dialog does.
            self.gui.android_ipaddr = ip_address
            self.gui.android_port = ip_port

            ui.notify(f"Project saved to Android device at {result}", type="positive")
            android_dialog.close()
            parent_dialog.close()

        # /upload overwrites silently and answers 200 either way, so the only way to
        # know is to read the destination back first -- see maputil2.file_exists_on_android
        # (None = couldn't tell, which still prompts rather than risking a silent clobber).
        device_path = projedit.android_project_path(edited_project.project_name)
        exists = file_exists_on_android(ip_address, ip_port, device_path)
        if exists is not False:
            build_overwrite_confirm_dialog(
                f"'{device_path}' on the Android device",
                _upload,
                unknown=exists is None,
            )
            return
        _upload()

    def open_add_task_dialog_event(self) -> None:
        """Opens the Add Task dialog for a brand-new Task, attached to the
        currently selected single Project (see the Project pulldown in the
        Specific Name tab). A Project must already be selected -- the new
        Task is attached directly to it (added to its <tids>, see
        _finish_new_task) rather than through a Profile, so there's no other
        way to know which Project it belongs to.
        """
        the_view = self.gui
        project_name = _confirmed_single_project_name(the_view)
        if not project_name:
            ui.notify("Select a single Project first (Project pulldown above).", type="warning")
            return

        # The toolbar's "Current File" only means a filename is known (see
        # display_and_set_file) -- it doesn't guarantee the backup has actually been
        # parsed into PrimeItems.xml_root yet (see the same self-healing load in
        # MyGui.__init__). Load it now rather than let create_new_task below
        # confusingly report "no file loaded" while a file is plainly shown.
        if PrimeItems.xml_root is None:
            if not PrimeItems.file_to_get and getattr(the_view, "file", ""):
                PrimeItems.file_to_get = the_view.file
            if not PrimeItems.file_to_get or get_xml(the_view.debug, the_view.appearance_mode) != 0:
                ui.notify("No backup file is currently loaded. Use 'Get Local XML' first.", type="warning")
                return

        new_task = taskedit.create_new_task("", "100")
        if isinstance(new_task, str):
            ui.notify(new_task, type="warning")
            return

        build_add_task_dialog(self.gui, new_task, target_project_name=project_name)

    def add_action_to_new_task_event(
        self,
        edited_task: taskedit.EditableTask,
        action_key: str,
        position: int | None = None,
    ) -> int | None:
        """Synthesizes and inserts a new action into the in-progress new Task,
        at `position` (before/after a specific already-added action) or at the
        end if None -- see build_add_task_dialog's "Position" picker, same as
        add_action_to_edit_task_event's.

        Returns the new action's act_number (so the dialog can highlight it as
        the most recently added), or None if it failed.
        """
        result = taskedit.add_action_to_task(edited_task, action_key, position)
        if isinstance(result, list):
            for error in result:
                ui.notify(error, type="negative")
            return None
        _notify_if_plugin_needs_configuration(result.action_element, result.action_name)
        return result.act_number

    def add_if_block_to_new_task_event(
        self,
        edited_task: taskedit.EditableTask,
        variant: str,
        position: int | None = None,
    ) -> int | None:
        """Inserts an "If" action -- plus the "Else"/"End If" companions the
        chosen variant calls for (see guiwins.build_if_variant_dialog) -- as
        consecutive actions into the in-progress new Task, at `position` or at
        the end if None.

        Returns the new "If" action's act_number (so the dialog can highlight
        it as the most recently added), or None if it failed.
        """
        result = taskedit.add_if_block_to_task(edited_task, variant, position)
        if isinstance(result, list):
            for error in result:
                ui.notify(error, type="negative")
            return None
        return result.act_number

    def remove_action_from_new_task_event(self, edited_task: taskedit.EditableTask, act_number: int) -> None:
        """Removes an action from the in-progress new Task and renumbers the rest."""
        taskedit.remove_action_from_task(edited_task, act_number)

    def delete_action_in_edit_task_event(self, edited_task: taskedit.EditableTask, act_number: int) -> None:
        """Removes an action from an existing Task being edited and renumbers the rest."""
        taskedit.remove_action_from_task(edited_task, act_number)

    def add_action_to_edit_task_event(
        self,
        edited_task: taskedit.EditableTask,
        action_key: str,
        position: int | None,
    ) -> int | None:
        """Synthesizes and inserts a new action into a Task being edited, at
        `position` (before/after a specific existing action) or at the end if
        None -- see taskedit.add_action_to_task and build_edit_task_dialog's
        "Add an action" Position picker.

        Returns the new action's act_number (so the dialog can highlight it as
        the most recently added), or None if it failed.
        """
        result = taskedit.add_action_to_task(edited_task, action_key, position)
        if isinstance(result, list):
            for error in result:
                ui.notify(error, type="negative")
            return None
        _notify_if_plugin_needs_configuration(result.action_element, result.action_name)
        return result.act_number

    def add_if_block_to_edit_task_event(
        self,
        edited_task: taskedit.EditableTask,
        variant: str,
        position: int | None,
    ) -> int | None:
        """Inserts an "If" action -- plus the "Else"/"End If" companions the
        chosen variant calls for (see guiwins.build_if_variant_dialog) -- as
        consecutive actions into a Task being edited, at `position` or at the
        end if None (same semantics as add_action_to_edit_task_event's).

        Returns the new "If" action's act_number (so the dialog can highlight
        it as the most recently added), or None if it failed.
        """
        result = taskedit.add_if_block_to_task(edited_task, variant, position)
        if isinstance(result, list):
            for error in result:
                ui.notify(error, type="negative")
            return None
        return result.act_number

    def copy_action_in_edit_task_event(self, edited_task: taskedit.EditableTask, act_number: int) -> None:
        """Duplicates an action (inserted right after the original) in a Task being edited."""
        taskedit.copy_action_in_task(edited_task, act_number)

    def move_action_in_edit_task_event(
        self,
        edited_task: taskedit.EditableTask,
        act_number: int,
        new_position: int,
    ) -> None:
        """Moves an action to a new position among a Task's other actions."""
        taskedit.move_action_in_task(edited_task, act_number, new_position)

    def set_action_enabled_event(
        self,
        edited_task: taskedit.EditableTask,
        act_number: int,
        enabled: bool,
    ) -> None:
        """Enables or disables an action in a Task being edited."""
        taskedit.set_action_enabled(edited_task, act_number, enabled)

    def set_action_continue_after_error_event(
        self,
        edited_task: taskedit.EditableTask,
        act_number: int,
        continue_after_error: bool,
    ) -> None:
        """Sets or clears an action's <se>false</se> ('Continue Task After
        Error') -- backs the checkbox of the same name (see
        guiwins._render_continue_after_error_checkbox).
        """
        taskedit.set_action_continue_after_error(edited_task, act_number, continue_after_error)

    def set_action_condition_event(
        self,
        edited_task: taskedit.EditableTask,
        act_number: int,
        target_input: ui.input,
        operator_select: ui.select,
        value_input: ui.input,
        condition_dialog: ui.dialog,
        checkbox: ui.checkbox,
    ) -> None:
        """Validates and writes a per-action If condition from the prompt's
        field values (see guiwins.build_action_condition_dialog), updates the
        "If" checkbox's text to show it, then closes the prompt. The prompt
        stays open on any validation error so the user can correct the fields.
        """
        target = target_input.value or ""
        operator_label = operator_select.value or ""
        value = value_input.value or ""
        errors = taskedit.set_action_condition(edited_task, act_number, target, operator_label, value)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        checkbox.set_text(f"If: {target.strip()} {operator_label} {value.strip()}".rstrip())
        ui.notify("If condition set.", type="positive")
        condition_dialog.close()

    def remove_action_condition_event(self, edited_task: taskedit.EditableTask, act_number: int) -> None:
        """Removes an action's per-action If condition -- backs unchecking the
        "If" checkbox (idempotent; a no-op if the action has none).
        """
        taskedit.remove_action_condition(edited_task, act_number)

    def save_new_task_event(
        self,
        edited_task: taskedit.EditableTask,
        field_refs: dict,
        dialog: ui.dialog,
        on_created: Callable[[str], None] | None = None,
    ) -> None:
        """Validates and applies the Add Task dialog's field values, then writes the
        new Task out as a standalone .tsk.xml file. Dialog stays open on any error
        so the user's in-progress work isn't lost.

        on_created, if given, is called with the new Task's id once it's
        registered -- see build_add_task_dialog's on_task_created.
        """
        ok, name_value = _validate_and_apply_new_task(edited_task, field_refs, check_save_path=True)
        if not ok:
            return

        save_path = field_refs["save_path"].value.strip()
        try:
            taskedit.write_standalone_task_xml(edited_task, save_path)
        except OSError as e:
            ui.notify(f"Could not save file: {e}", type="negative")
            return

        _finish_new_task(self.gui, edited_task, name_value, on_created, field_refs)

        ui.notify(f"Saved to {save_path}", type="positive")
        dialog.close()

    def keep_new_task_event(
        self,
        edited_task: taskedit.EditableTask,
        field_refs: dict,
        dialog: ui.dialog,
        on_created: Callable[[str], None] | None = None,
    ) -> None:
        """Validates and applies the Add Task dialog's field values, then registers
        the new Task into the live in-memory backup (same as Save's
        register_new_task), without writing a standalone file, then closes the
        dialog -- backs the "Ok" button, which keeps the new Task for this
        session only. Dialog stays open on any error so the user's in-progress
        work isn't lost. Still checks the Task name for a conflict (needed for
        live-tree registration to make sense) but not the save path, since no
        file is written.

        on_created, if given, is called with the new Task's id once it's
        registered -- see build_add_task_dialog's on_task_created.
        """
        ok, name_value = _validate_and_apply_new_task(edited_task, field_refs)
        if not ok:
            return

        _finish_new_task(self.gui, edited_task, name_value, on_created, field_refs)

        ui.notify(
            "Task kept for this session only -- use 'Save To Current File' to keep it permanently.",
            type="positive",
        )
        dialog.close()

    def save_new_task_to_current_file_event(
        self,
        edited_task: taskedit.EditableTask,
        field_refs: dict,
        dialog: ui.dialog,
        on_created: Callable[[str], None] | None = None,
    ) -> None:
        """Validates and applies the Add Task dialog's field values, registers
        the new Task into the live in-memory backup, then writes the *entire*
        current backup out to a new, timestamped copy of whatever file it was
        loaded from (see maputil2.write_full_backup_to_current_file) and
        switches the app over to that copy (see
        _reload_saved_copy_and_refresh) -- the original file is left
        untouched -- unlike Save, which exports just this one Task as a
        standalone file. Backs the "Save To Current File" button. Dialog
        stays open on any error so the user's in-progress work isn't lost; a
        failed disk write is reported but doesn't undo the registration
        already done (same as Ok, which never touches disk at all).
        """
        ok, name_value = _validate_and_apply_new_task(edited_task, field_refs)
        if not ok:
            return

        _finish_new_task(self.gui, edited_task, name_value, on_created, field_refs)

        success, result = write_full_backup_to_current_file()
        if not success:
            ui.notify(f"Could not save to current file: {result}", type="negative")
            return

        reload_ok, reload_error = _reload_saved_copy_and_refresh(self.gui, result)
        if not reload_ok:
            ui.notify(f"Saved a copy to {result}, but failed to load it: {reload_error}", type="warning")
            return

        ui.notify(f"Saved a copy to {result} and loaded it. The original file was left unchanged.", type="positive")
        dialog.close()

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
            clear_single_item_view_names(gui)
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

            # Empty the pulldown menus for Project, Profile, Task and Scene selections
            reset_single_item_pulldowns(gui)

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

        # Valid response
        else:
            the_view.ai_prompt = name_entered
            msg = translate_string("Prompt changed to")
            the_view.display_message_box(
                f"{msg} '{the_view.ai_prompt}'.",
                "Green",
            )

            display_selected_object_labels(the_view)

        # Updates NiceGUI visual rendering colors reactively
        update_analysis_button_color(the_view)

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
        if self.gui.is_updating:
            return  # Exit early to break the recursive loop!
        language = language.value.strip() if hasattr(language, "value") else str(language).strip()
        # Let everyone know we are setting the language
        PrimeItems.language_set = True

        # Determine reference view (matches your event logic structure)
        the_view = self if self.__class__.__name__ == "MyGui" else self.gui
        if the_view.language == language:
            return

        # Set the translation function in PrimeItems. Pass the raw (English) selection
        # as-is -- language_set_event() does its own translate_string(..., set_language=True)
        # to switch locale, so pre-translating it here (with the *old* locale, before the
        # switch) would double-translate it into a string that matches no known language
        # key, causing language_set_event() to fall back to "English" and leaving the
        # pulldown showing the wrong (or blank) selection.
        if hasattr(self, "language_set_event"):
            self.language_set_event(language)

        # Reset selection checkboxes / extended list flags safely using the lock flag
        the_view.displaying_extended_list = None  # Force pulldown to be recreated.
        if hasattr(the_view, "aimodel_extend_checkbox") and the_view.aimodel_extend_checkbox:
            try:
                the_view.is_updating = True  # Engage the lock
                the_view.aimodel_extend_checkbox.value = False
            finally:
                the_view.is_updating = False  # Disengage the lock

        # --- FIX: Defer layout reconstruction to break out of LeftDrawer context nesting ---
        def rebuild_layout() -> None:
            client = context.client

            # Remove previous top-level layout elements (header/drawer/footer). NiceGUI
            # moves those to be direct children of the q-layout (siblings of the page
            # container), so they must be torn down explicitly rather than via
            # `client.layout.clear()`, which would also destroy the page container itself.
            for child in list(client.layout.default_slot.children):
                if child is not client.page_container:
                    child.delete()

            # Clear the actual page content (this is where the new elements get built).
            client.content.clear()

            # Several widgets (e.g. ai_model_option, font_out_label) are only (re)created
            # by helper functions that check "if the attribute is already set, reuse it"
            # instead of always rebuilding. Now that their elements were torn down above,
            # null out any such stale reference on the view so those helpers create fresh
            # ones instead of touching an element NiceGUI considers deleted.
            for attr_name, attr_value in list(vars(the_view).items()):
                if getattr(attr_value, "is_deleted", False):
                    setattr(the_view, attr_name, None)

            # Rebuild inside the page content: NiceGUI requires top-level layout
            # elements (header/drawer/footer) to be created while it is the active slot.
            # Everything below also runs inside this block: the timer callback's own
            # context is the *old* (now-deleted) slot it was created in, so anything
            # relying on the active NiceGUI context (e.g. ui.notify()) would otherwise
            # blow up with "The parent element this slot belongs to has been deleted."
            # once this block exits and that stale context becomes active again.
            with client.content:
                initialize_screen(the_view)

                # Redisplay current file onto the fresh layout
                display_current_file(the_view, the_view.file)

                # Restore settings values so that they are correctly displayed in the new UI instance
                temp_args = {arg: getattr(the_view, arg) for arg in ARGUMENT_NAMES if hasattr(the_view, arg)}
                the_view.extract_settings(temp_args)

                # Trigger task limit label updates
                if hasattr(self, "tasklimit_event"):
                    self.tasklimit_event(the_view.task_action_warning_limit)

                # Reset the single item object tracking names. Guarded the same way as
                # check_name's identical call: setting a pulldown's .value fires its
                # on_change (single_project_name_event etc.), which re-enters check_name --
                # harmless if that validates fine, but an infinite loop if it doesn't (e.g.
                # a restored single_project_name pointing at a file that no longer exists).
                try:
                    the_view.is_updating = True
                    set_tasker_object_names(the_view)
                finally:
                    the_view.is_updating = False

                # Reset single item dropdown select lists
                update_tasker_object_menus(
                    the_view,
                    get_data=False,
                    reset_single_names=False,
                )

                # Handle upgrade buttons checks
                check_new_version(the_view)

                # Update the pull-down menus option items lists
                if "list_tasker_objects" in globals():
                    list_tasker_objects(the_view)

                # Map menu attributes to their target values for a clean batch update
                menu_updates = []

                for label in SINGLE_ITEM_LABELS:
                    name = getattr(the_view, f"single_{label.lower()}_name", "")
                    if name:
                        menu_updates = [
                            (f"specific_{label.lower()}_optionmenu", name),
                            (f"ai_{label.lower()}_optionmenu", name),
                        ]
                        break

                # Batch update the dropdown values safely under the state lock.
                # Via select_pulldown_option, since a Project's option is
                # "Project: <name>" and a Profile's "Profile: <name>", not the
                # bare name held in single_project_name/single_profile_name --
                # assigning the bare name would leave the pulldown blank.
                try:
                    the_view.is_updating = True  # Engage the lock
                    for attr_name, target_value in menu_updates:
                        if hasattr(the_view, attr_name):
                            menu_widget = getattr(the_view, attr_name)
                            if menu_widget:
                                select_pulldown_option(menu_widget, target_value)
                finally:
                    the_view.is_updating = False  # Always disengage the lock

                # Redo the contextual text labels values
                display_selected_object_labels(the_view)

                # Update text labels inside tabs directly by changing properties
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

        # Safely trigger layout swap outside the active event scope in 10ms
        ui.timer(0.01, rebuild_layout, once=True)
        # --- END FIX ---

    def language_set_event(self, language: str | Event) -> None:
        """
        Set the language for the GUI. Comes here via 'restore_display' and 'language_set_event'.
        Uses the state lock to prevent recursive dropdown triggers.

        Args:
            language: The language selected by the user.
        """
        the_view = self if self.__class__.__name__ == "MyGui" else self.gui
        language = language.value.strip() if hasattr(language, "value") else str(language).strip()

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

        # 2. Change the menu dropdown value safely using the lock flag. The dropdown's
        # options are a {english_key: translated_label} dict (see
        # _create_language_selection_section in guiwins.py), so its "value" must be the
        # English key -- assigning the translated label here would match no option and
        # leave the pulldown showing blank.
        if hasattr(the_view, "language_optionmenu") and the_view.language_optionmenu:
            try:
                the_view.is_updating = True  # Engage the lock
                the_view.language_optionmenu.value = language_to_use
                the_view.language_optionmenu.update()
                PrimeItems.program_arguments["language"] = language_to_use
            finally:
                the_view.is_updating = False  # Disengage the lock

        # Translate and format message
        message = f"{translate_string('Language set to')} {language_translated}."

        # Display message in the GUI
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
        the_view = self.gui
        update_maptasker()
        the_view.display_message_box("Program updated.  Restarting...", "Green")
        # Create the Change Log file to be read and displayed after a program update.
        create_changelog()

        # Reload the GUI by running a new process with the new program/version.
        reload_gui(the_view)

    def coffee_event(self) -> None:
        """Opens a web browser to the 'Buy Me A Coffee' page for support."""
        the_view = self.gui
        try:
            webbrowser.open("https://www.buymeacoffee.com/mctinker", new=2)
        except webbrowser.Error:
            the_view.display_message_box(
                "Error: Failed to open output in browser: your browser is not supported.",
                "Red",
            )

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

        # guiview = self.gui

        help_texts = {
            "viewlimit": ("View Limit Help", VIEWLIMIT_HELP_TEXT),
            "view": ("Views Help", VIEW_HELP_TEXT),
            "ai": ("Ai Analyze Help", AI_HELP_TEXT),
            "help": ("", HELP),
            "android": ("Get XML From Android Device Help", BACKUP_HELP_TEXT),
            "listfile": ("List Android Files Help", LISTFILES_HELP_TEXT),
            "apikey": ("API Key Help", APIKEY_HELP_TEXT),
        }
        query_name = query_name.value if isinstance(query_name, Event) else str(query_name).lower()
        title, help_text = help_texts.get(
            query_name,
            ("", "No help available for this query."),
        )
        # Add the changelog to the help text.
        if query_name == "help":
            changes = get_changelog_file(CHANGELOG_URL, "##", 11)
            # Bypass the version number and transl;ate the rest of the help text.
            temp = help_text.find("Help\n\n")
            help_text = f"{help_text[:temp]}\n\n" + translate_string(help_text[temp:])
            help_text = help_text + "\n".join(changes)

        # Create the dialog container on the main thread
        __package__dialog = create_popup_window(
            f"{translate_string(title)}",
            f"{translate_string(help_text)}",
            close_button=True,
        )

    def viewlimit_event(self: object, view_limit: str) -> None:
        """View Limit Event handled safely without recursion."""
        guiview = self.gui
        if getattr(guiview, "is_updating", False):
            return

        # 1. Safely extract the raw string value from NiceGUI Event or raw string
        view_limit_str = view_limit.value if hasattr(view_limit, "value") else str(view_limit)

        # 2. Normalize values to match the options strings exactly
        if view_limit_str == "9999999" or view_limit_str == translate_string("Unlimited"):
            display_value = "Unlimited"
            guiview.view_limit = 9999999
        else:
            display_value = str(view_limit_str)
            if display_value.isdigit():
                guiview.view_limit = int(display_value)
            else:
                display_value = "10000"  # Fallback safety
                guiview.view_limit = 10000

        # 3. Target the correct guiview reference variable
        if hasattr(guiview, "viewlimit_optionmenu") and guiview.viewlimit_optionmenu:
            try:
                guiview.is_updating = True
                guiview.viewlimit_optionmenu.value = display_value
                guiview.viewlimit_optionmenu.update()  # Force NiceGUI to update component properties
            finally:
                guiview.is_updating = False

        # 4. Force global UI panel recalculation to draw changes onto the browser screen
        ui.update()

        text = translate_string("View Limit set to")
        guiview.display_message_box(f"{text} {display_value}.", "Green")

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

            # --- DYNAMIC LIVE REFRESH ---
            # If a Map/Diagram view is currently rendered on screen, update it instantly rather
            # than only taking effect the next time the view is (re)generated. Background gets
            # its own path since it's a container style, not a CSS class add_css() (addcss.py)
            # emits into the rendered HTML; every other category (Tasks, Projects, etc.) is
            # rendered as `<span class="{css_class}">`, so overriding that class's color live
            # (with !important, since it must beat the color already embedded in the loaded
            # HTML's own <style> block) re-colors every matching element already on screen.
            # Both branches reach into the *rendered* views, which may well not be
            # there any more -- "Clear" deletes them (clear_view_event) and a browser
            # reload replaces their client -- so each element is checked for life
            # rather than mere existence; see element_is_live for what touching a
            # dead one does. Nothing is lost when they're gone: the colour has already
            # been recorded above and the next view generated picks it up.
            # Every open view gets re-coloured, since "Open View In New Window" can
            # leave several Map/Diagram windows on screen at once.
            scroll_areas = [
                scroll_area
                for scroll_area in (getattr(view, "scroll_area", None) for view in live_views(the_view))
                if element_is_live(scroll_area)
            ]

            if color_selected_item == "Background":
                the_view.saved_background_color = make_hex_color(color_value)
                for scroll_area in scroll_areas:
                    scroll_area.style(f"background-color: {color_value} !important;")
                if not scroll_areas:
                    ui.notify("The change will take effect the next time you open the view.", color="green")

            else:
                css_class = TYPES_OF_COLOR_NAMES.get(color_selected_item)
                for scroll_area in scroll_areas if css_class else []:
                    with scroll_area:
                        ui.run_javascript(
                            f"""
                            const container = document.getElementById("c{scroll_area.id}");
                            if (container) {{
                                let style = container.querySelector('style[data-live-color-override]');
                                if (!style) {{
                                    style = document.createElement('style');
                                    style.setAttribute('data-live-color-override', '1');
                                    container.appendChild(style);
                                }}
                                style.textContent += ".{css_class} {{ color: {color_value} !important; }}\\n";
                            }}
                            """,
                        )
                if not (css_class and scroll_areas):
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
        if any(getattr(gui, f"single_{label.lower()}_name", "") for label in SINGLE_ITEM_LABELS):
            gui.ai_analyze = True
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

            # Display messages from the AI run.
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

                # Force dynamic button styling update
                update_analysis_button_color(gui)
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

            # Redisplay the UI dependencies
            display_analyze_button(gui, 13, first_time=False)
            display_selected_object_labels(gui)
        else:
            gui.display_message_box("No API keys changed.", "LimeGreen")

        # 6. Close the window view
        dialog_container.close()

        # Updates NiceGUI visual rendering colors reactively
        update_analysis_button_color(gui)

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
        the_view.is_updating = True
        list_tasker_objects(the_view)
        the_view.is_updating = False
        text = translate_string("'List Unnamed Items' checkbox")
        the_view.display_message_box(
            f"{text} {selected}.",
            "Green",
        )

    # Display what is in the changelog for the new release.
    def whatsnew_event(self) -> None:
        """
        Retrieves the latest changelog from the Map-Tasker GitHub repository and displays it in a popup window.

        This function sends a GET request to the specified URL to retrieve the changelog in text format,
        then displays it all at once in a single popup dialog (rather than one message box per line). The
        changelog is displayed starting from the latest version until the "Older History" section is reached.

        Parameters:
            self (object): The instance of the class.

        Returns:
            None
        """
        number_of_versions = 11
        changes = get_changelog_file(CHANGELOG_URL, "##", number_of_versions)

        if changes:
            summary = translate_string(f"End of changelog. The latest {number_of_versions - 1} versions displayed.")
            message = "\n".join(changes) + f"\n\n{summary}"
        else:
            message = translate_string("An error occurred reading the changelog file.")

        create_popup_window(translate_string("What's New?"), message, close_button=True)

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

    async def profiles_per_line_event(self, profiles_per_line: int) -> None:
        """Sets gui.profiles_per_line to the newly selected value and regenerates/redisplays
        the Diagram view (see NiceGuiTextView._profiles_per_line_selected in guiwins.py)."""
        gui = self.gui
        gui.profiles_per_line = profiles_per_line
        PrimeItems.program_arguments["profiles_per_line"] = profiles_per_line

        await run.io_bound(outline_the_configuration)

        # Reload every open Diagram view -- "Open View In New Window" can leave more than one up.
        for view in live_views(gui):
            if hasattr(view, "reload_diagram"):
                view.reload_diagram()

    def ai_apikey_get_event(self, cancel: bool, clear: bool) -> None:  # noqa: D102
        self._handle_event("ai_apikey_process_event", "ai_apikey_window", cancel, clear)


# Define a state container to hold our saved file locationvariable
class AppState:
    """Initialize the variable to hold the selected file path.
    This is a class variable that can be accessed and modified from anywhere in the code."""

    selected_file_path = None
