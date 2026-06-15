"""Code to manage the graphical user interface using NiceGUI."""

import contextlib
import os
from collections.abc import Callable
from typing import TYPE_CHECKING

from nicegui import Event, ui

from maptasker.src.config import AI_PROMPT, DEFAULT_DISPLAY_DETAIL_LEVEL, OUTPUT_FONT
from maptasker.src.getfile import Local_File_Picker
from maptasker.src.getids import get_ids
from maptasker.src.getputer import save_restore_args
from maptasker.src.guimap import parse_html
from maptasker.src.guiutils import (
    build_profiles,
    clear_android_buttons,
    display_current_file,
    get_xml,
    reload_gui,
    reset_primeitems_single_names,
    update_tasker_object_menus,
)
from maptasker.src.guiwins import (
    NiceGuiTextView,
    initialize_gui,
    initialize_screen,
)
from maptasker.src.mapit import mapit_all
from maptasker.src.maputil2 import translate_string
from maptasker.src.maputils import (
    clear_tasker_data,
)
from maptasker.src.primitem import PrimeItems, PrimeItemsReset
from maptasker.src.sysconst import (
    ARGUMENT_NAMES,
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
        """Initializes the GUI and sets up all necessary state and layout."""
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
            print("🚨 CRITICAL UI BUILD ERROR 🚨")
            import traceback  # noqa: PLC0415

            traceback.print_exc()
            print("=" * 50 + "\n")

        self.initialization = False

        # 5. Start the server
        ui.run(
            reload=False,
            host="127.0.0.1",
            # FIX
            storage_secret="maptasker_gui_storage",
            title="MapTasker",
            port=8080,
            dark=None,
            show=True,  # Force the browser to open the correct HTTP link
        )

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
        window_position_attribute = f"{view_type}_window_position"
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

        # Setup diagram view.
        elif view_type in ("diagram", "misc"):
            # Display the data.
            if data:
                view = NiceGuiTextView(
                    master=getattr(self, window_attribute),
                    title=window_title,
                    the_data=data,
                )
            else:
                self.display_message_box("No Project(s) Found in XML!", "Red")
                return None
        elif view_type == "tree":
            if data:
                view = NiceGuiTextView(master=getattr(self, window_attribute), items=data)
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

        the_view = self.parent
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
    # 2. VIEW & TAB NAVIGATION
    # ==========================================
    def view_event(self: "MapTaskerEventHandlers", view_type: str) -> None:
        """Triggered when Map, Diagram, or Tree buttons are clicked."""
        logger.info(f"GUI: Switching to {view_type} view")
        ui.notify(f"Loading {view_type.title()} View...", type="info", timeout=1000)

        # Here you would trigger the logic to fetch the data and update
        # your NiceGuiTextView or NiceGuiTreeView components.

    # ==========================================
    # 3. INPUT & DROPDOWN EVENTS
    # ==========================================
    def detail_selected_event(self: "MapTaskerEventHandlers", event: Event) -> None:
        """
        NICEGUI PARADIGM SHIFT:
        Dropdown (ui.select) on_change events automatically pass an 'event' object.
        The new selected value is stored in `event.value`.
        """
        self.gui.display_detail_level = event.value
        logger.info(f"Detail level changed to: {event.value}")
        # Note: If you bound this via `.bind_value()`, you don't even need this function!

    def ai_model_selected_event(self: "MapTaskerEventHandlers", event: Event) -> None:
        """Updates the AI model based on dropdown selection."""
        self.gui.ai_model = event.value
        logger.info(f"AI Model changed to: {event.value}")
        print("bingo")

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
        the_view = self.parent

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

            # Redisplay the Projects/Profiles/Tasks pulldown menus for selection
            # It will call 'display_and_set_file' to display the current file name via call to 'load_xml'
            gui.current_file_display_message = True
            update_tasker_object_menus(gui, get_data=True, reset_single_names=True)
            gui.current_file_display_message = False

        else:
            # Handle the case where the user hit "Cancel" or closed the dialog
            ui.notify("File selection canceled.", type="warning")


# Define a state container to hold our saved file locationvariable
class AppState:
    """Initialize the variable to hold the selected file path.
    This is a class variable that can be accessed and modified from anywhere in the code."""

    selected_file_path = None
