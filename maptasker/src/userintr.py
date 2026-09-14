"""Code to manage the graphical user interface using NiceGUI.

MapTaskerEventHandlers, the class every button and pulldown in the window is wired to, is being
split by feature so that this file stops being the one place every handler lives:

    userintr_ai.py        the AI model and prompt pickers, the API keys dialog, Analyze
    userintr_android.py   fetching a backup off the device, Save To Android, Import Into Tasker
    userintr_editors.py   the Task, Profile, Scene and Project editors and Object Properties
    userintr_loading.py   opening a backup file, and the Specific Name tab's single-object selection
    userintr_reports.py   Health Check, Variable Cross-Reference, Task Flow, Compare, Changes Since
    userintr_settings.py  the output options, colors, fonts, language, and Save/Restore/Reset

Each feature's handlers are a mixin that MapTaskerEventHandlers inherits, so gui.event_handlers
keeps every name it had.  A handler that moves takes its helpers with it, including one it shares
with code still here: this file imports that back from the new module, as it does
local_xml_start_directory.  None of those modules imports this one except for type checking --
this file imports them at the top, so an import at the top of theirs would close the loop.
"""

import contextlib
import time
import webbrowser
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from nicegui import Event, context, run, ui

from maptasker.src import (
    console,
    mapjump,
    sessundo,
)
from maptasker.src.bildhtml import build_html
from maptasker.src.config import AI_PROMPT, DEFAULT_DISPLAY_DETAIL_LEVEL, OUTPUT_FONT
from maptasker.src.frontmtr import output_the_front_matter
from maptasker.src.getids import get_ids
from maptasker.src.guistate import SELECTION_KEYS, capture_gui_state, held_overrides
from maptasker.src.guiutil2 import get_changelog_file
from maptasker.src.guiutils import (
    SINGLE_ITEM_LABELS,
    build_profiles,
    check_for_changelog,
    check_new_version,
    clear_android_buttons,
    clear_single_item_view_names,
    create_changelog,
    display_current_file,
    display_error_file_and_ai_response,
    display_selected_object_labels,
    get_xml,
    is_no_selection,
    refresh_object_action_buttons,
    refresh_tasker_object_pulldowns,
    reload_gui,
    reset_single_item_pulldowns,
    reset_single_item_selection,
    select_pulldown_option,
    update_analysis_button_color,
    valid_item,
)
from maptasker.src.guiwins import (
    NiceGuiTextView,
    NiceGuiTreeView,
    create_popup_window,
    forget_views,
    go_to_target,
    initialize_gui,
    initialize_screen,
    live_views,
    opening_view_in_a_new_window,
    restore_appearance_mode,
)
from maptasker.src.guiwins_refactor import build_refactor_dialog
from maptasker.src.maputil2 import (
    log_startup_values,
    translate_string,
)
from maptasker.src.maputils import (
    append_to_filename,
    get_current_local_time_auto_timezone,
    make_hex_color,
    rename_file,
    update_maptasker,
)
from maptasker.src.mtexcept import MapTaskerError
from maptasker.src.outline import outline_the_configuration
from maptasker.src.primitem import (
    MAP_OUTPUT_ATTRIBUTES,
    PrimeItems,
    clear_error,
    initial_found_named_items,
    reset_attributes,
)
from maptasker.src.runcfg import current_config
from maptasker.src.sysconst import (
    ALL_OBJECTS_MESSAGE,
    ANALYSIS_FILE,
    CHANGELOG_URL,
    DIAGRAM_PROFILES_PER_LINE,
    NOTIFY_TIMEOUT_DEFAULT,
    POPOUT_WINDOW_PREFIX,
    TAB_NAMES,
    TYPES_OF_COLOR_NAMES,
    VIEW_LIMIT_DEFAULT,
    logger,
)
from maptasker.src.taskerd import get_the_xml_data
from maptasker.src.taskflow import (
    analyze_task_flow,
    flowchart,
    write_flowchart,
)
from maptasker.src.translator import T
from maptasker.src.userhelp import (
    AI_HELP_TEXT,
    APIKEY_HELP_TEXT,
    BACKUP_HELP_TEXT,
    LISTFILES_HELP_TEXT,
    VIEW_HELP_TEXT,
    VIEWLIMIT_HELP_TEXT,
    build_help,
)
from maptasker.src.userintr_ai import AIEventHandlers
from maptasker.src.userintr_android import AndroidEventHandlers
from maptasker.src.userintr_editors import EditorEventHandlers
from maptasker.src.userintr_loading import LoadingEventHandlers
from maptasker.src.userintr_reports import ReportEventHandlers
from maptasker.src.userintr_settings import SettingsEventHandlers

if TYPE_CHECKING:
    from maptasker.src.userintr import MyGui


all_objects = ALL_OBJECTS_MESSAGE


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

        # 1a. Install the saved language's translation *before* any of the layout exists.
        # Every label, button, tab title and tooltip is run through translate_string() at
        # the moment it is created, so a language restored further down (restore_settings_event
        # -> extract_settings -> language_set_event) arrives too late to affect anything
        # already built -- which is the entire window.  That left a non-English startup GUI
        # sitting in English until the user re-picked their language from the pulldown.
        self.set_startup_language()

        # 2. Attach Event Handlers
        self.event_handlers = MapTaskerEventHandlers(self)

        # 2a. Put the saved notification duration in force before anything can notify, for the
        # same reason the language goes in before the layout: start-up talks, and by the time
        # the restore below reaches the key that carries the duration it has already said a
        # dozen things at the wrong one.
        self.set_startup_notification_duration()

        # 3. Build the UI Layout directly!
        try:
            initialize_screen(self)
        except Exception as e:  # noqa: BLE001
            ui.label(f"CRASH IN UI LAYOUT: {e}").classes("text-2xl text-red-500 m-8 font-mono")
            # Whatever went wrong, the label above is now the window's entire content, so
            # the user can see it.  sys.exit() used to follow, which was the worst of both
            # worlds: raised inside a NiceGUI page builder it does not end the process, it
            # kills the request handling this page and leaves uvicorn logging a SystemExit
            # traceback -- so the message just written was never displayed.  Returning
            # leaves the message on screen and the server up.
            console.error("\n" + "=" * 50)
            console.error(f"🚨 CRITICAL UI BUILD ERROR 🚨 {e}")
            console.error("=" * 50 + "\n")
            logger.exception("Building the GUI layout failed", exc_info=e)
            return

        # Now restore the settings and update the fields if not resetting.
        if not PrimeItems.program_arguments["reset"]:
            self.event_handlers.restore_settings_event()

            # 3. Synchronize runtime arguments
            if self.color_lookup and not PrimeItems.colors_to_use:
                capture_gui_state(self, {})

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
        self.conditions = self.preferences = self.taskernet = self.debug = self.everything = self.reset = (
            self.restore
        ) = self.exit = self.bold = self.highlight = self.italicize = self.underline = self.outline = self.rerun = (
            self.list_files
        ) = self.runtime = self.save = self.twisty = self.directory = self.pretty = self.fetched_backup_from_android = (
            False
        )
        self.single_project_name = ""
        self.single_profile_name = ""
        self.single_task_name = ""
        self.single_scene_name = ""
        self.file = ""
        self.appearance_mode = "system"

        self.indent = 4
        self.android_ipaddr = ""
        self.android_port = ""
        self.android_file = ""
        self.android_auth_key = ""  # Cached Tasker HTTP API key for Save To Android (see save_task_to_android_event).
        self.android_auth_key_ipaddr = ""
        self.android_auth_key_port = ""
        self.color_lookup = {}  # Setup default dictionary as empty list
        self.saved_background_color = "#3e1414"
        self.font = OUTPUT_FONT
        self.gui = True
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
        # Directory the 'Get Local XML File' picker opens in.  Empty = the home directory,
        # until the user picks a file from somewhere else (see remember_local_xml_directory).
        self.local_xml_directory = ""

        self.reset_numeric_preferences()

        # Display current Items setting.
        with contextlib.suppress(
            AttributeError,
        ):  # single_name_status may not be defined yet.
            self.single_name_status(all_objects, "#3f99ff")

    def reset_numeric_preferences(self: "MyGui") -> None:
        """Put View Limit, Notification Duration and Profiles Per Line back to their defaults.

        Separate from the assignments above it because each of these three is shown by a
        control, and a reset that changed the value without moving the control would leave the
        two disagreeing -- the window saying 30000 while the program used 10000, which is the
        kind of disagreement nobody thinks to doubt.  So each goes through the same path a
        user's own change goes through.

        Nothing here assumes the GUI exists.  set_defaults runs once during start-up, before
        the event handlers are attached and long before any widget is built, and again on
        "Reset Options" when everything is up; the plain assignments cover the first case and
        are all it needs.
        """
        self.view_limit = VIEW_LIMIT_DEFAULT
        self.notify_timeout = NOTIFY_TIMEOUT_DEFAULT
        self.profiles_per_line = DIAGRAM_PROFILES_PER_LINE
        PrimeItems.program_arguments["profiles_per_line"] = DIAGRAM_PROFILES_PER_LINE

        handlers = getattr(self, "event_handlers", None)
        if handlers is None:
            return

        # These two own a pulldown in the settings drawer and know how to move it.
        handlers.viewlimit_event(str(VIEW_LIMIT_DEFAULT))
        handlers.notify_timeout_event(NOTIFY_TIMEOUT_DEFAULT)

        # Profiles Per Line is not in the drawer -- it sits on the Diagram view's own toolbar,
        # and there can be one on each open Diagram view ("Open View In New Window").  Its own
        # handler is not used: that one is async and regenerates the diagram, which is a
        # surprising amount of work to trigger from a settings reset, and pointless when the
        # value it would rebuild with is the one already in place.
        for view in live_views(self):
            selector = getattr(view, "profiles_per_line_select", None)
            if selector is not None:
                selector.value = str(DIAGRAM_PROFILES_PER_LINE)
                selector.update()

    def set_startup_language(self: "MyGui") -> None:
        """Establish the translation function for the saved language before the GUI is built.

        The settings file has already been read by the time the GUI is created (runcli.process_cli
        calls restore_arguments() before process_gui()), so the user's language is sitting in
        PrimeItems.program_arguments.  Load its gettext catalog now so that initialize_screen()
        builds every widget with its text already translated.  language_set_event() still runs
        later, during the normal settings restoration, to set the flag logo and the language
        pulldown; this only front-runs the part it needs before the layout exists.
        """
        # A reset run deliberately ignores the saved settings, so it starts out in English.
        if PrimeItems.program_arguments.get("reset"):
            return

        language = PrimeItems.program_arguments.get("language") or "English"
        # The saved value is the English language name ("German"); anything else (a hand-edited
        # settings file, or a translated name written by an older version) is not something
        # set_language can resolve, so leave the default English in place.
        if language not in PrimeItems.languages:
            logger.warning(f"Saved language '{language}' is not recognized.  Using English.")
            return

        self.language = language
        T.set_language(language)

    def set_startup_notification_duration(self: "MyGui") -> None:
        """Put the saved notification duration in force before the first message goes out.

        The settings file has already been read into PrimeItems.program_arguments by the time
        the GUI is created (the same thing set_startup_language relies on), so the chosen
        duration is available here -- before the layout exists and long before the restore
        gets to it.  It has to be applied this early because start-up is a dozen notifications
        long: set_defaults announces the reset it makes and the restore then announces every
        setting it puts back, and all of that came out at the default duration purely because
        the saved value was not applied until the restore happened to reach its own key, most
        of the way down the list.  restore_settings_event puts it back a second time, after
        set_defaults has reset it, for the rest of that same report.

        The event handler does the work rather than a plain assignment, so an unusable value
        in a hand-edited settings file lands on the default instead of on zero -- which would
        mean every message in the app stays up until it is clicked.
        """
        # A reset run deliberately ignores the saved settings.
        if PrimeItems.program_arguments.get("reset"):
            return

        saved_duration = PrimeItems.program_arguments.get("notify_timeout")
        if saved_duration is not None:
            # The pulldown does not exist yet; notify_timeout_event skips it when it is absent.
            self.event_handlers.notify_timeout_event(saved_duration)

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
                self.display_message_box(translate_string("Cancel button pressed.\n"), "Orange")
                display_current_file(self, none_translated)
            else:
                self.display_message_box(
                    translate_string("Invalid XML!  Click 'Get Local XML File' to try a different XML file."),
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
                translate_string("'Get XML From Android' settings cleared."),
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
        # Only when there is a file to name.  A settings restore hands this every value it
        # has, including an empty one, and "Current file set to " followed by nothing is not
        # worth a message -- the label above already says "No file loaded".
        if self.current_file_display_message and filename:
            text = translate_string("Current file set to")
            self.display_message_box(f"{text} {filename}", "Green")
        self.file = filename  # Set this so it is saved in settings.

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
                        f"{front_error} but it was not found in {file_name}! All Projects, Profiles and Tasks will be displayed.\n",
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
        self.display_message_box(translate_string("Settings restored.\n"), "Green")

        # Recolor 'Run Analysis' now that every setting is in.  Doing it mid-loop isn't enough:
        # ARGUMENT_NAMES restores ai_model well before single_xxx_name, so any refresh triggered
        # by an earlier key still sees no object selected and leaves the button red.
        update_analysis_button_color(self)

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
            # Only consulted when the 'Get Local XML File' picker is opened -- there is no
            # widget of its own to restore it into.
            "local_xml_directory",
            # Likewise only read when a Save To Android panel opens -- see
            # guiwins._android_device_fields.
            "android_check_ids",
            "android_verify",
        }
        # Define what to do for each argument restored.
        set_to = translate_string("set to")
        message_map = {
            "android_ipaddr": lambda: f"{translate_string('Android Get XML TCP IP Address')} {set_to} {value}\n",
            "android_port": lambda: f"{translate_string('Android Get XML Port Number')} {set_to} {value}\n",
            "android_file": lambda: f"{translate_string('Android Get XML File Location')} {set_to} {value}\n",
            # Moves the "Dark Mode" switch and repaints the window.  Without this the saved
            # appearance mode landed on self (every restored key does, via setattr above) and
            # then sat there unused, which is what made dark mode look like it was never saved.
            "appearance_mode": lambda: restore_appearance_mode(self, value),
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
            "notify_timeout": lambda: self.event_handlers.notify_timeout_event(value),
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

                    # Select it in its own pulldown.  Prefer whatever option the list
                    # already holds for this name: the "<type>: " head above is only
                    # right when the XML has Projects to walk -- an exported single
                    # Profile/Task file has no Project, so get_tasker_objects' no-tree
                    # branch lists Profile names bare, and a fabricated "Profile: X"
                    # would match no option and leave the pulldown showing just its
                    # "Profile" label.  Fall back to the prefixed name only when the
                    # live tree has the item but the pulldown list hasn't been rebuilt
                    # for it yet; display_object_pulldowns re-resolves the selection
                    # (reapply_single_item_selections) once it has.
                    optionmenu = getattr(self, f"specific_{my_name.lower()}_optionmenu")
                    select_pulldown_option(optionmenu, name_entered)
                    if is_no_selection(optionmenu.value) or optionmenu.value not in (optionmenu.options or []):
                        display_value = f"{option_heads.get(my_name, '')}{name_entered}"
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

        # The Edit/Add buttons follow the single-item selection (see
        # refresh_object_action_buttons).  This path sets single_<item>_name directly
        # rather than going through process_name_event, so it has to refresh them
        # itself -- otherwise a restored Project comes back with its pulldown filled in
        # but only "Add Project" on screen.  Unconditional: a name that failed
        # check_name above leaves nothing selected, which is equally worth reflecting.
        refresh_object_action_buttons(self)

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
            self.task_action_label.text = f"{translate_string('Task Action Limit:')} {limit_int}"

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


def popout_window_name(path: str, new_window: bool = False) -> str:
    """What the browser window holding this view is called.

    Its own function, and not private, because two places have to agree on it: this, which
    opens the window under the name, and the Diagram, which goes looking for the Map's
    window by name so it can raise it when a clicked object is answered by the Map already
    on screen (see diagintr).  A Diagram searching for a name nothing was opened under
    would quietly never raise anything, which is the kind of disagreement that shows up as
    a feature simply not working.

    The query string is deliberately NOT part of the name.  The Map's path carries
    "?goto=...&scope=..." (see view_event), and a name built from the whole path therefore
    changed with every finding clicked and every Project shown -- so each one opened a
    window of its own and only re-clicking the very same item reused anything, which is
    exactly what "Open View In New Window" being off is supposed to prevent.  The name
    identifies the VIEW; what that view is currently showing belongs in the URL alone.

    With "Open View In New Window" on, a unique suffix is appended: a name nothing has
    claimed yet behaves exactly like "_blank", which is what makes every request a fresh
    window.  The stable part stays at the front so the name is still recognisably this
    view's.
    """
    view_name = path.rsplit("/", 1)[-1].split("?", 1)[0]
    stable_name = f"{POPOUT_WINDOW_PREFIX}{view_name}"
    return f"{stable_name}_{time.time_ns()}" if new_window else stable_name


# How the "still working" banner sits on the page: pinned to the top of the window,
# centered, and above everything else, so it is in the same place whatever the user has
# scrolled to and whichever tab of the settings they are on.
BUSY_BANNER_STYLE = (
    "position: fixed; top: 0.75rem; left: 50%; transform: translateX(-50%); z-index: 9999; "
    "padding: 0.5rem 1rem; border-radius: 0.375rem; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.4); "
    "background-color: #1f2937; color: #fb923c;"
)


def _busy_banner(message: str) -> ui.element | None:
    """A spinner and a message that stay on screen for the whole of a long build.

    ui.notify() puts up a toast that takes itself down again after a few seconds, which is
    the wrong shape for work that runs longer than that: the view was announced, the toast
    expired, and the rest of the wait looked like the button had simply done nothing.

    Deliberately an ordinary element rather than ui.notification: a notification is owned
    by Quasar's Notify plugin and is taken down by asking that plugin to do it, which this
    app has no reliable way to make happen.  An element of our own comes down when we
    delete it.

    Returns None when there is no browser window to draw it in (a build started from
    somewhere other than a click in the GUI), which _clear_busy_banner accepts.
    """
    try:
        layout = context.client.layout
    except RuntimeError:
        # No client context -- nobody to tell.  The build itself is unaffected.
        return None
    with layout:
        banner = ui.element("div").classes("flex items-center gap-3").style(BUSY_BANNER_STYLE)
        with banner:
            ui.spinner(size="1.5em", color="orange")
            ui.label(message).classes("italic")
    return banner


def _clear_busy_banner(banner: ui.element | None) -> None:
    """Take down a _busy_banner, whether or not its window is still there."""
    if banner is not None:
        with contextlib.suppress(Exception):
            banner.delete()


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
    # See popout_window_name for what the name is and why it is shaped that way.
    window_name = popout_window_name(path, new_window)
    # What it does, and why the handle is kept in two places, is in mapjump.open_popout_js.
    ui.run_javascript(mapjump.open_popout_js(path, window_name))


# Which lookup table answers "is this single-item selection still a real item?", per
# SINGLE_ITEM_LABELS.  The two *_by_name tables are the ones keyed the way the pulldowns
# name things: all_profiles and all_tasks are keyed by id, so checking those would say no
# to every Profile and Task there is.
_SELECTION_TABLES = {
    "Project": "all_projects",
    "Profile": "all_profiles_by_name",
    "Task": "all_tasks_by_name",
    "Scene": "all_scenes",
}


def _single_selection_still_exists(gui: MyGui) -> bool:
    """Whether the 'Specific Name' selection, if there is one, still names something.

    An Undo can take away the very item that is selected -- undoing an Add removes it,
    undoing a Rename puts a different name on it -- and a selection naming nothing is not
    harmless: PrimeItems.program_arguments still carries it, so the next Map or Diagram
    would be built filtered on an item that is not there and come back empty.
    """
    for label in SINGLE_ITEM_LABELS:
        name = getattr(gui, f"single_{label.lower()}_name", "")
        if is_no_selection(name):
            continue
        if name not in PrimeItems.tasker_root_elements.get(_SELECTION_TABLES[label], {}):
            return False
    return True


class MapTaskerEventHandlers(
    AIEventHandlers,
    AndroidEventHandlers,
    EditorEventHandlers,
    LoadingEventHandlers,
    ReportEventHandlers,
    SettingsEventHandlers,
):
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
    async def view_event(
        self: "MapTaskerEventHandlers",
        view_type: str,
        goto: str = "",
        overrides: dict | None = None,
    ) -> None:
        """Triggered when Map, Diagram, or Tree buttons are clicked.

        Uses run.io_bound to run blocking file generations in a background thread,
        allowing thread-safe access to internal PrimeItems variables.

        'goto' is a mapjump token the finished Map view scrolls to and highlights once it
        has streamed in -- how a clicked report finding is delivered to a Map that had to
        be built for it (see rebuild_map_for_jump).

        'overrides' are settings this one build needs that the GUI does not currently hold
        -- a detail level high enough to list the actions being jumped to, say.  Applied
        AFTER capture_gui_state, since that overwrites program_arguments wholesale from the
        GUI, and left to the caller to put back: the GUI's own widgets are untouched, so
        nothing the user can see changes.

        Applying them here is not on its own enough to make them STAY applied -- capture_gui_state
        runs again, off NiceGUI's outbox loop, for messages this build itself sends.  A caller
        passing overrides must hold them across this call with guistate.held_overrides.
        """
        # max_limit = 9999999
        window_title = f"{view_type.capitalize()} View"
        self.gui.event = True  # Set the event flag to True
        logger.info(f"GUI: Switching to {window_title}")

        gui = self.gui
        PrimeItems.view_limit = gui.view_limit if hasattr(gui, "view_limit") else VIEW_LIMIT_DEFAULT

        # Plug all of our settings back into PrimeItems.program_arguments
        capture_gui_state(gui, {})
        if overrides:
            PrimeItems.program_arguments.update(overrides)

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
        #  - emitted_anchors: the same story as the directory.  Left populated from an
        #    earlier view, every object looks already-anchored, so the second view carries
        #    no mapjump anchors at all and a clicked finding has nothing to land on.
        #  - task_action_warnings: the "too many actions" list, accumulated the same way.
        reset_attributes(*MAP_OUTPUT_ATTRIBUTES)

        # Map view
        if view_type == "map":
            if PrimeItems.xml_root is None:
                gui.display_message_box(
                    translate_string("No XML data loaded! Please select a valid XML file first."),
                    "Orange",
                )
                return

            # Say so before the work starts, and keep saying it right through it.  A large
            # configuration takes real time to build below, and the one-second toast that
            # used to announce it was gone for almost all of that wait -- leaving a window
            # that looked like the button had done nothing.  This one carries a spinner and
            # no timeout, and comes down in the "finally" below whichever way this ends.
            building = _busy_banner(
                f"{translate_string('Building the')} {window_title}.  {translate_string('Please stand by ...')}",
            )
            try:
                # 1. Clear out stale error codes before starting execution paths
                clear_error()

                # Refresh our output_lines object to ensure we have a clean slate for the new map generation.
                PrimeItems.output_lines.output_lines.clear()
                output_the_front_matter(current_config())

                try:
                    # 2. RUN IO BOUND: Uses background threads to preserve memory singletons safely
                    await run.io_bound(build_html, "")
                except MapTaskerError as e:
                    # Intercept background termination codes gracefully.  This was
                    # "except SystemExit" and had to be: build_html and everything under it
                    # ended the process outright on any error.  They raise this now, which
                    # is an ordinary Exception, so a failed build is one failed build --
                    # the window stays up and says what happened.
                    error_code_extracted = e.exit_code
                    if error_code_extracted == 6:
                        gui.display_message_box(
                            translate_string(
                                "Map view creation skipped: No valid XML source found or action canceled."
                            ),
                            "Orange",
                        )
                    else:
                        gui.display_message_box(
                            f"Map processing halted with system code: {error_code_extracted}", "Red"
                        )
                    return

                # Check if an entry-point processing failure occurred during build_html
                if getattr(PrimeItems, "error_code", 0) > 0:
                    gui.display_message_box(f"Map processing error: {PrimeItems.error_msg}", "Orange")
                    clear_error()
                    return

                # Now process the data for display in the gui
                output_length = len(PrimeItems.output_lines.output_lines)

                # Clear out our inline data to free up memory for the GUI display, since we no longer need it.
                PrimeItems.output_lines.output_lines.clear()

                # Display the map in its own browser window/tab rather than the main window.
                # A "goto" rides along on the URL rather than being pushed into the window
                # afterwards: the popout is its own page with its own timing, and only it knows
                # when the Map has finished streaming in and is therefore scrollable.
                #
                # "scope" says which Project this Map was built for -- always, not just for a
                # jump -- so that a later clicked finding can tell whether the Map already on
                # screen is one that can show what it points at, or whether it has to build its
                # own.  Read here rather than remembered on PrimeItems because the popout is
                # constructed after this call returns, by which time any overrides for this one
                # build have been put back.
                query = urlencode(
                    {"goto": goto, "scope": PrimeItems.program_arguments.get("single_project_name") or ""}
                )
                _open_popout_window(f"/popout/map?{query}", getattr(gui, "open_view_in_new_window", False))

                # Check for hard stop limit and notify user if output was truncated
                if output_length > gui.view_limit:
                    gui.display_message_box(
                        f"Map view truncated {output_length} lines to {gui.view_limit} lines due to view limit.",
                        "Orange",
                    )
                gui.display_message_box(translate_string("Map View opened in a new browser window."), "Green")
            finally:
                _clear_busy_banner(building)

        # Setup diagram view.
        elif view_type in ("diagram", "misc"):
            # Check if we have a Project or Profile
            if view_type == "diagram":
                if PrimeItems.tasker_root_elements["all_projects"] or PrimeItems.tasker_root_elements["all_profiles"]:
                    gui.display_message_box(
                        translate_string("The 'Diagram' view is running in the background.  Please stand by..."),
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
                        clear_error()
                        return

                    # Display the diagram in its own browser window/tab rather than the main window.
                    # What the app was showing when this Diagram was drawn, carried so the
                    # view can say so on its own toolbar -- and say when the selection has
                    # moved on since.  A Diagram is a snapshot: nothing rebuilds it when the
                    # user picks a different single object, so its hotlinks go on pointing at
                    # the objects of the selection it was built for, and there was no sign of
                    # that anywhere on screen.
                    built_for = urlencode({"built_for": mapjump.current_scope().phrase})
                    _open_popout_window(
                        f"/popout/diagram?{built_for}",
                        getattr(gui, "open_view_in_new_window", False),
                    )

                    # Cut short at the view limit?  Say so, as the "map" branch above does -- the
                    # diagram is still shown, up to the point the limit allowed.
                    if PrimeItems.diagram_limit_msg:
                        gui.display_message_box(PrimeItems.diagram_limit_msg, "Orange")
                    gui.display_message_box(translate_string("Diagram View opened in a new browser window."), "Green")
                else:
                    gui.display_message_box(
                        translate_string("No XML data loaded! Please select a valid XML file first."),
                        "Orange",
                    )

            else:
                gui.display_message_box(
                    translate_string("The 'Misc' view is running in the background.  Please stand by..."),
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
                gui.display_message_box(translate_string("No Project(s) Found in XML!"), "Red")
                return
        else:
            ui.notify(
                translate_string("No XML data loaded! Please Get XML from Android or Local drive first."),
                type="warning",
                position="top",
            )
            gui.display_message_box(
                translate_string("Invalid view type specified. Use 'map', 'diagram', or 'tree'."),
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

        # Close every Map/Diagram popout this session opened -- including the ones a popout
        # opened for itself, which is why this is mapjump.close_popouts_js and not a loop
        # over this window's own list: a Map built for a jump from the Diagram belongs to
        # the DIAGRAM's list (see _open_popout_window), and Clear used to close the Diagram
        # and leave that Map behind.  The same call Exit makes, minus shutting anything down.
        ui.run_javascript(mapjump.close_popouts_js())
        ui.notify(translate_string("View cleared."), type="info", position="bottom")

    async def rebuild_map_for_jump(self: "MapTaskerEventHandlers", target: mapjump.Target) -> None:
        """Build a Map that holds this object, and open it scrolled to it.

        What a clicked report finding falls back to when no Map on screen can show it --
        because none is open, because the one that is shows a single Project, or because
        its detail level leaves out the Tasks and actions the finding is about.

        The build is deliberately the whole configuration at a detail level high enough for
        this object: those are the two settings that decide whether the Map contains it at
        all, and a click that says "take me there" is worth honouring rather than answering
        with a second reason it cannot.  Nothing the user can see changes -- the overrides
        go into program_arguments for this one build and are put straight back, while the
        pulldowns and the detail selector keep whatever they held.  The next Map View press
        is therefore exactly the Map they asked for, not the one this needed.

        Not silently: the settings are not the user's, so the notification says which ones
        this went past.
        """
        level = max(PrimeItems.program_arguments.get("display_detail_level", 0), mapjump.minimum_detail_level(target))
        # Narrowed to the Project that owns what was clicked, rather than built whole.  A
        # click asks to be shown one thing, and a Map of one Project is both the answer to
        # that and a great deal quicker to build and to read than a Map of everything.
        #
        # Whole file only when there is no Project to narrow to: an orphan Profile, a Scene
        # no Project lists, a Task filed under none -- exactly the objects the reachability
        # findings are about -- and a variable, which the Map indexes per Project but the
        # cross-reference does not attribute to one.
        overrides = dict.fromkeys(SELECTION_KEYS, "")
        overrides["display_detail_level"] = level
        scope = mapjump.scope_for(target)
        if scope:
            overrides["single_project_name"] = scope
        # A TaskerNet description is governed by its own option rather than by the detail
        # level, so a finding about what somebody wrote in one needs that option on for the
        # Map to hold the line at all -- the same argument as the detail level above.
        if mapjump.needs_taskernet(target):
            overrides["taskernet"] = True

        # Say which settings this went past, and only those: the point of saying anything is
        # that the Map on screen afterwards is not the one the user's own settings would have
        # produced.  Worked out by comparing the overrides against what is actually set, so
        # that a user already on this Project at this detail level is told nothing at all.
        changed = {key for key, value in overrides.items() if PrimeItems.program_arguments.get(key, "") != value}
        reasons = []
        if changed & set(SELECTION_KEYS):
            reasons.append(f"{translate_string('Project')} '{scope}'" if scope else translate_string("whole file"))
        if "display_detail_level" in changed:
            reasons.append(f"{translate_string('detail level')} {level}")
        if "taskernet" in changed:
            reasons.append(translate_string("TaskerNet information"))
        ui.notify(
            f"{translate_string('Building the Map to show')} {target.label}"
            + (f" ({', '.join(reasons)})" if reasons else "")
            + " ...",
            type="info",
            position="top",
        )

        # Put back exactly what was there, key by key -- including any key that was absent,
        # which must go back to being absent rather than to an empty string.
        saved = {key: PrimeItems.program_arguments[key] for key in overrides if key in PrimeItems.program_arguments}
        absent = [key for key in overrides if key not in PrimeItems.program_arguments]
        try:
            # held_overrides, not just the update view_event does, because the build is not
            # the only thing writing these: capture_gui_state re-copies the GUI's own
            # single-item selection over program_arguments from NiceGUI's outbox loop, and
            # one of this build's own notifications is enough to trigger it.  See its
            # definition in guistate for what that cost.
            with held_overrides(overrides):
                await self.view_event("map", goto=target.token(), overrides=overrides)
        finally:
            PrimeItems.program_arguments.update(saved)
            for key in absent:
                PrimeItems.program_arguments.pop(key, None)

    def refactor_event(self: "MapTaskerEventHandlers") -> None:
        """Open the Refactor dialog: the structural moves, with a preview.

        Lives on the main window beside Edit/Add and the Undo group rather than on the Map
        toolbar, because a refactor is an EDIT.  Three of its four operations -- inline,
        move, duplicate -- name an object and act on it whole, and nothing about them
        depends on what is currently drawn; hanging them off a view meant a Map had to be
        built before any of them could be reached at all.

        Rebuilt on every press rather than kept, for the reason maprefac gives about its
        Plan: it closes over live elements, and holding one across a reopen is precisely the
        stale-handle case maprefac.apply's attachment check exists to catch.
        """
        self._dismiss_refactor_dialog()

        def make_jump(target: mapjump.Target) -> Callable[[], Coroutine]:
            """One preview row's click: open what it names in a window of its own.

            The new window is what keeps the dialog: from here the jump has no Map to
            scroll, so go_to_target falls through to building one, and a build that reused
            the tab would take this window -- and the preview in it -- with it.  See
            guiwins.opening_view_in_a_new_window for the whole of why.
            """

            async def go() -> None:
                with opening_view_in_a_new_window(self.gui):
                    await go_to_target(self.gui, target)

            return go

        async def refresh_after_apply() -> None:
            """What to bring up to date once a refactor has been applied.

            The pulldowns, and only the pulldowns.  A refactor adds and removes whole
            objects, so an option list built before one offers names that no longer resolve
            -- the same reason Undo and Redo refresh them (see _step_edit_history).  No view
            is rebuilt: there may not be one, and if there is it is a separate window that
            the user can refresh when they want to look at it.
            """
            refresh_tasker_object_pulldowns(self.gui)

        dialog = build_refactor_dialog("", make_jump, refresh_after_apply)
        if dialog is None:
            return
        self.gui.refactor_dialog = dialog
        dialog.open()

    def _dismiss_refactor_dialog(self: "MapTaskerEventHandlers") -> None:
        """Take down the Refactor dialog if one is still up.

        Deleted rather than closed: a fresh dialog is built per press, so the one being
        replaced has nothing left to hold, and a closed-but-undeleted dialog is a stack that
        grows with the page.  A dialog whose page has gone away raises rather than
        answering; that is one more dialog already gone, not an error to report.
        """
        dialog = getattr(self.gui, "refactor_dialog", None)
        self.gui.refactor_dialog = None
        if dialog is not None:
            with contextlib.suppress(Exception):
                dialog.delete()

    def _step_edit_history(self: "MapTaskerEventHandlers", *, forwards: bool) -> None:
        """Shared body of the Undo and Redo buttons -- the two differ only in which way
        they walk the history and what they say afterwards.

        Refreshing the pulldowns is not cosmetic: the restore replaced every lookup table,
        so an option list built from the old ones would offer names that no longer resolve.
        Whatever single Project/Profile/Task/Scene was selected is deliberately left alone;
        if the step removed it, refresh_tasker_object_pulldowns drops it from the options
        the same way a file load does.
        """
        succeeded, message = sessundo.redo() if forwards else sessundo.undo()
        if not succeeded:
            ui.notify(message, type="warning")
            return

        refresh_tasker_object_pulldowns(self.gui)
        # Only when the step actually took the selected item away -- undoing an edit to
        # some other Task must not clear the Project the user is looking at.
        #
        # display_selected_object_labels is the other half of that reset and not optional:
        # reset_single_item_selection clears the names and the pulldowns, and this is what
        # repaints the three places the old name is still written on screen -- the
        # "Current <item> selection" line, the "Display only ..." caption under the
        # pulldowns, and the Analyze tab's four targets.  The pair is always used together
        # (see guiutils.list_tasker_objects, which loads a new file the same way).
        if not _single_selection_still_exists(self.gui):
            reset_single_item_selection(self.gui)
            display_selected_object_labels(self.gui)
        action = translate_string("Redid") if forwards else translate_string("Undid")
        ui.notify(f"{action}: {message}", type="positive")

    def undo_edit_event(self: "MapTaskerEventHandlers") -> None:
        """Take back the last change made to the loaded configuration -- see sessundo."""
        self._step_edit_history(forwards=False)

    def redo_edit_event(self: "MapTaskerEventHandlers") -> None:
        """Put back the last change Undo took away -- see sessundo."""
        self._step_edit_history(forwards=True)

    def _draw_task_flowchart(self: "MapTaskerEventHandlers", gui: "MyGui") -> None:
        """Draw the single selected Task as a flowchart in its own window, if one is chosen.

        Silent about there being no chart when no single Task is selected -- said as a hint
        rather than as a failure, since the report the user just asked for did run.

        The chart is left on PrimeItems for the popped-out page to pick up: that page is
        built from a URL and is handed nothing, which is the same reason the Diagram popout
        re-reads its own generated file (see rungui.popout_view).
        """
        scope = mapjump.current_scope()
        if scope.label != "Task":
            ui.notify(
                translate_string("Choose a single Task in 'Specific Name' to also see it drawn as a flowchart."),
                type="info",
                position="bottom",
            )
            return

        # A Scope holds every Task id of that name, because a backup may legally hold two
        # Tasks called the same thing (healthck reports that as DUPLICATE-NAME).  Charting
        # them all in one window would read as one enormous Task, so the first is drawn and
        # the user is told the choice was made.
        task_ids = sorted(scope.tasks)
        flow = analyze_task_flow(task_ids[0]) if task_ids else None
        if flow is None:
            gui.display_message_box(
                f"{translate_string('Could not find Task')} '{scope.name}'.",
                "Orange",
            )
            return
        if len(task_ids) > 1:
            ui.notify(
                f"{translate_string('More than one Task is named')} '{scope.name}'. "
                f"{translate_string('Drawing the first.')}",
                type="warning",
            )

        PrimeItems.taskflow_rows = flowchart(flow)
        chart_file = write_flowchart(PrimeItems.taskflow_rows)
        if chart_file:
            gui.display_message_box(f"{translate_string('Flowchart saved as')} {chart_file}", "Green")

        _open_popout_window("/popout/flow", getattr(gui, "open_view_in_new_window", False))
        gui.display_message_box(translate_string("Task Flow View opened in a new browser window."), "Green")

    # ==========================================
    # 4. TEXT VIEW CONTROLS
    # ==========================================

    def clear_event(self, _view_name: str = "mapview") -> None:
        """Clears the search input and un-highlights all matches left by search_event."""
        # Every open view, not just the newest: with "Open View In New Window" several
        # Map/Diagram windows can be up at once, each with its own highlighted matches.
        for textview in live_views(self.gui):
            self._clear_one_view(textview)

    def _clear_one_view(self, textview: object) -> None:
        """Clears one rendered view's search box and un-highlights its matches."""
        if hasattr(textview, "search_input"):
            textview.search_input.set_value("")

        # The results this view is holding on to are only replayable while their highlight
        # spans are still in the page, and they are about to stop being.
        if hasattr(textview, "invalidate_search_cache"):
            textview.invalidate_search_cache()

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

                // Prefer unwrapping the spans search_event recorded, which puts each match's
                // own text node back where the span was. The generic sweep below cannot do
                // that -- it substitutes freshly created text nodes -- and search_event's
                // cached index (see guiwins.py) refers to the nodes themselves, so letting
                // the sweep loose on them means throwing that index away and making the next
                // search crawl the whole view again from scratch.
                const cache = container.__mtSearchIndex;
                if (cache && cache.highlights) {{
                    for (const span of cache.highlights) {{
                        if (span.parentNode && span.firstChild) {{
                            span.parentNode.replaceChild(span.firstChild, span);
                        }}
                    }}
                    cache.highlights = [];
                }}
                if (container.querySelector('.search-highlight')) {{
                    clearHighlights(container);
                    container.__mtSearchIndex = null;  // no longer describes these text nodes
                }}

                // Also turn off any Diagram-view connector highlighting left by clicking a connector.
                container.querySelectorAll('.connector-highlight').forEach(el => {{
                    el.classList.remove('connector-highlight');
                }});

                // ...and the outline left on whatever a clicked report finding jumped to
                // (see mapjump.jump_js).  "Clear" means the view is back to how it was
                // rendered, whichever of the three ways something on it came to stand out.
                container.querySelectorAll('.{mapjump.HIGHLIGHT_CLASS}').forEach(el => {{
                    el.classList.remove('{mapjump.HIGHLIGHT_CLASS}');
                }});
            """)

        ui.notify(translate_string("Cleared the search highlights."), type="info")

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
        ui.notify(
            translate_string("Updating MapTasker in the background.  Please stand by..."),
            type="positive",
            timeout=5.0,
        )
        update_maptasker()
        the_view.display_message_box(translate_string("Program updated.  Restarting..."), "Green")
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
                translate_string("Error: Failed to open output in browser: your browser is not supported."),
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
                translate_string("Error: Failed to open output in browser: your browser is not supported."),
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
            "help": ("", ""),  # assembled below, being the one screen with a version number in it
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
            # Assembled from its separately translated pieces rather than looked up whole --
            # see userhelp.build_help, which owns that split.  Slicing the assembled screen
            # apart here instead is what this used to do, and it broke the moment the help
            # text was reworded: the heading it searched for ("Help\n\n") became "Help  \n",
            # the search missed, and the whole screen went to gettext as one msgid no
            # catalog has -- which is a miss, and a miss reads back as English.
            #
            # The changelog is fetched from GitHub in English and appended afterwards.  It
            # is nobody's msgid and there is nothing to look it up in.
            help_text = build_help(translate_string) + "\n".join(changes)
        else:
            # Every other screen is a whole userhelp constant and so is a msgid in its own
            # right.  Translated here rather than at the create_popup_window call below,
            # because the "help" branch above has already translated its own piece -- and
            # the assembled version number, help text and changelog it produces is not a
            # msgid, so passing that through gettext a second time could only ever miss.
            help_text = translate_string(help_text)

        # Create the dialog container on the main thread
        __package__dialog = create_popup_window(
            f"{translate_string(title)}",
            help_text,
            close_button=True,
            # The help screens are the one place that may carry **bold** and __italic__.
            # Only after the gettext lookups above: the markers are part of the msgid, so
            # a catalog can move them to wherever the emphasis belongs in that language.
            rich=True,
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

        create_popup_window(translate_string("What's New?"), message, close_button=True, rich=True)

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
