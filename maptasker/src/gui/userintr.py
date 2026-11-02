"""Code to manage the graphical user interface using NiceGUI.

MapTaskerEventHandlers, the class every button and pulldown in the window is wired to, is made of
groups by feature so that this file stops being the one place every handler lives:

    userintr_ai.py        the AI model and prompt pickers, the API keys dialog, Analyze
    userintr_android.py   fetching a backup off the device, Save To Android, Import Into Tasker
    userintr_carry.py     Import With Dependencies
    userintr_editors.py   the Task, Profile, Scene and Project editors and Object Properties
    userintr_loading.py   opening a backup file, and the Specific Name tab's single-object selection
    userintr_prebuild.py  building the Map ahead of time
    userintr_reports.py   Health Check, Variable Cross-Reference, Task Flow, Compare, Changes Since
    userintr_settings.py  the output options, colors, fonts, language, and Save/Restore/Reset
    userintr_tasktests.py the Task Tests dialog, and running the tests after every edit

Each group is an object of its own (see userintr_group.HandlerGroup) that MapTaskerEventHandlers
holds as an attribute, so the window wires a button to gui.event_handlers.<group>.<name>; what is
left on MapTaskerEventHandlers itself is what the groups share.  A handler that moves takes its
helpers with it, including one it shares with code still here: this file imports that back from the
new module, as it does local_xml_start_directory.  None of those modules imports this one except for
type checking -- this file imports them at the top, so an import at the top of theirs would close the
loop.
"""

import contextlib
import webbrowser
from typing import TYPE_CHECKING, Any, cast

from nicegui import ui

from maptasker.src.core import console
from maptasker.src.core.config import AI_PROMPT, DEFAULT_DISPLAY_DETAIL_LEVEL, OUTPUT_FONT
from maptasker.src.core.elemvals import get_ids
from maptasker.src.core.error import record_error
from maptasker.src.core.initparg import ProgramArguments
from maptasker.src.core.maputil2 import (
    log_startup_values,
    translate_string,
    write_full_backup_to_current_file,
)
from maptasker.src.core.maputils import (
    append_to_filename,
    get_current_local_time_auto_timezone,
    make_hex_color,
    rename_file,
    update_maptasker,
)
from maptasker.src.core.mtexcept import MapTaskerError
from maptasker.src.core.outdir import output_path
from maptasker.src.core.primitem import (
    SINGLE_ITEM_LABELS,
    RunState,
)
from maptasker.src.core.sysconst import (
    ALL_OBJECTS_MESSAGE,
    ANALYSIS_FILE,
    CHANGELOG_URL,
    DIAGRAM_PROFILES_PER_LINE,
    NOTIFY_TIMEOUT_DEFAULT,
    TAB_NAMES,
    TYPES_OF_COLOR_NAMES,
    VIEW_LIMIT_DEFAULT,
    logger,
)
from maptasker.src.core.translator import T
from maptasker.src.gui.guistate import capture_gui_state
from maptasker.src.gui.guiutil2 import get_changelog_file
from maptasker.src.gui.guiutils import (
    build_profiles,
    check_for_changelog,
    check_new_version,
    clear_single_item_view_names,
    create_changelog,
    display_current_file,
    display_error_file_and_ai_response,
    get_xml,
    is_no_selection,
    refresh_object_action_buttons,
    refresh_tasker_object_pulldowns,
    reload_gui,
    reset_single_item_pulldowns,
    select_pulldown_option,
    update_analysis_button_color,
    valid_item,
)
from maptasker.src.gui.guiutils_android import clear_android_buttons
from maptasker.src.gui.guiwins import create_popup_window, initialize_gui, restore_appearance_mode
from maptasker.src.gui.guiwins_drawers import initialize_screen
from maptasker.src.gui.guiwins_nav import live_views
from maptasker.src.gui.guiwins_textview import NiceGuiTextView
from maptasker.src.gui.guiwins_tnupdate import check_links_at_startup
from maptasker.src.gui.userhelp import (
    AI_HELP_TEXT,
    APIKEY_HELP_TEXT,
    BACKUP_HELP_TEXT,
    LISTFILES_HELP_TEXT,
    VIEW_HELP_TEXT,
    VIEWLIMIT_HELP_TEXT,
    build_help,
)
from maptasker.src.gui.userintr_ai import AIEventHandlers
from maptasker.src.gui.userintr_android import AndroidEventHandlers
from maptasker.src.gui.userintr_carry import CarryEventHandlers
from maptasker.src.gui.userintr_editors import EditorEventHandlers
from maptasker.src.gui.userintr_finish import reload_saved_copy_and_refresh, show_save_in_progress_notice
from maptasker.src.gui.userintr_loading import LoadingEventHandlers
from maptasker.src.gui.userintr_prebuild import PrebuildEventHandlers
from maptasker.src.gui.userintr_reports import ReportEventHandlers
from maptasker.src.gui.userintr_settings import SettingsEventHandlers
from maptasker.src.gui.userintr_tasktests import TaskTestEventHandlers
from maptasker.src.gui.userintr_tools import ToolEventHandlers
from maptasker.src.gui.userintr_views import ViewEventHandlers
from maptasker.src.mapgen.taskerd import get_the_xml_data

if TYPE_CHECKING:
    from maptasker.src.gui.userintr import MyGui


all_objects = ALL_OBJECTS_MESSAGE


# We'll use a class to maintain your state, just like before,
# but it NO LONGER inherits from customtkinter.CTk
def check_for_updates(gui: "MyGui") -> None:
    """Look for a newer MapTasker on PyPI, and for newer versions of the TaskerNet shares linked.

    Both are asked off the event loop and say nothing unless there is something to say.  The
    second asks nothing at all if no share has been linked.
    """
    check_new_version(gui)
    check_links_at_startup()


# ##################################################################################
# What restoring each saved setting does (MyGui.restore_display).
# ##################################################################################
# Settings that have nothing to restore into: they are set as attributes on the window and
# say nothing.
RESTORE_KEYS_TO_IGNORE = frozenset(
    {
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
        # guiwins.android_device_fields.
        "android_check_ids",
        "android_verify",
        # Only read when an Android dialog opens -- see guiutils_android.android_address_defaults.
        "android_last_ipaddr",
        "android_last_port",
    },
)
# Setting -> (the window's checkbox for it, the name the message calls it).
RESTORE_CHECKBOXES = {
    "ai_model_extended_list": ("aimodel_extend_checkbox", "Display Profile/Task Conditions"),
    "bold": ("bold_checkbox", "Display Names in Bold"),
    "conditions": ("conditions_checkbox", "Display Profile/Task Conditions"),
    "debug": ("debug_checkbox", "Debug Mode"),
    "directory": ("directory_checkbox", "Display Directory"),
    "highlight": ("highlight_checkbox", "Display Names Highlighted"),
    "italicize": ("italicize_checkbox", "Display Names Italicized"),
    "list_unnamed_items": ("list_unnamed_items_checkbox", "Display Unnamed Tasks"),
    "preferences": ("preferences_checkbox", "Display Tasker Preferences"),
    "pretty": ("pretty_checkbox", "Display Prettier"),
    "runtime": ("runtime_checkbox", "Display Runtime Settings"),
    "taskernet": ("taskernet_checkbox", "Display TaskerNet Information"),
    "twisty": ("twisty_checkbox", "Hide Task Details Under Twisty"),
    "underline": ("underline_checkbox", "Display Names Underlined"),
}
# Setting -> what the message calls an Android address setting ("<label> set to <value>").
RESTORE_ANDROID_LABELS = {
    "android_ipaddr": "Android Get XML TCP IP Address",
    "android_port": "Android Get XML Port Number",
    "android_file": "Android Get XML File Location",
}
# Setting -> the settings handler that takes the value and applies it.
RESTORE_EVENT_HANDLERS = {
    "display_detail_level": "detail_selected_event",
    "font": "font_event",
    "indent": "indent_selected_event",
    "language": "language_set_event",
    "notify_timeout": "notify_timeout_event",
    "output_directory": "output_directory_restored",
    "view_limit": "viewlimit_event",
}
# Setting -> the kind of object whose name it holds.
RESTORE_SINGLE_NAMES = {
    "single_profile_name": "Profile",
    "single_project_name": "Project",
    "single_task_name": "Task",
    "single_scene_name": "Scene",
}

# How a restore message ends when the setting has no value, and what it says instead.
_UNSET_ENDING = "set to \n"
_UNNAMED_ENDING = "named ''.\n"


def tidy_restore_message(message: str | None) -> str:
    """The restore message with an empty ending put into words ("set to" nothing is "is not set").

    Args:
        message (str | None): what the handler returned; None and "" both mean nothing to say.

    Returns:
        str: the message to show, or "".
    """
    if not message:
        return ""
    if message.endswith(_UNSET_ENDING):
        return f"{message[: -len(_UNSET_ENDING)]} is not set.\n"
    if message.endswith(_UNNAMED_ENDING):
        return f"{message[: -len(_UNNAMED_ENDING)]} is not named.\n"
    return message


class MyGui:
    """Main UI Interface for MapTasker using NiceGUI."""

    # Widgets the layout code in guiwins creates and keeps on the window.  Declared here so the
    # type checker knows they exist; each is assigned once, when the layout is built.
    # The run state this window shows and edits: PrimeItems, the one the program runs on, for a real run, or
    # another for a test.  Everything under the window reads it from here.
    state: RunState
    gui_header: ui.header
    save_settings_button: ui.button
    restore_settings_button: ui.button
    report_issue_button: ui.button
    # The TaskerNet Updates dialog while one is up (see taskernet_updates_event).
    tnupdate_dialog: ui.dialog | None
    carry_dialog: ui.dialog | None
    import_with_dependencies_button: ui.button
    # The Task Stepper dialog while one is up (see task_stepper_event).
    taskstep_dialog: ui.dialog | None
    # The Task Tests dialog while one is up (see TaskTestEventHandlers.task_tests_event).
    tasktests_dialog: ui.dialog | None
    task_tests_button: ui.button
    # The Trend Dashboard dialog while one is up (see trend_dashboard_event).
    trend_dialog: ui.dialog | None
    # The Missing Resources dialog while one is up (see missing_resources_event).
    resources_dialog: ui.dialog | None
    # The Live Run Monitor dialog while one is up (see live_monitor_event).
    monitor_dialog: ui.dialog | None
    # Everything else the window keeps on itself, declared so the type checker knows it exists.
    # Widgets are assigned once, when the layout is built (initialize_screen and the guiwins builders).
    add_profile_button: ui.button
    add_project_button: ui.button
    add_scene_button: ui.button
    add_task_button: ui.button
    ai_apikey_and_model_lbl: ui.label
    aimodel_extend_checkbox: ui.checkbox
    analysis_button: ui.button
    analysis_query_button: ui.button
    android_button_row: ui.row
    android_container: ui.column
    android_query_button: ui.button
    change_prompt_button: ui.button
    close_tabs_on_exit_checkbox: ui.checkbox
    coffee_button: ui.button
    color_change: ui.label
    color_objects_options: ui.select
    color_picker_input: ui.color_input
    conditions_checkbox: ui.checkbox
    content_container: ui.column
    current_file: ui.label
    current_file_label: ui.label
    currently_selected_label: ui.label
    dark_mode_switch: ui.switch
    debug_checkbox: ui.checkbox
    directory_checkbox: ui.checkbox
    display_help_button: ui.button
    display_names_label: ui.label
    dm_controller: ui.dark_mode
    edit_history_button: ui.button
    edit_profile_button: ui.button
    edit_project_button: ui.button
    edit_scene_button: ui.button
    edit_task_button: ui.button
    everything_checkbox: ui.checkbox
    exit_button: ui.button
    filelist_label: ui.label
    filelist_option: ui.select
    fix_findings_button: ui.button
    font_label: ui.label
    font_optionmenu: ui.select
    get_android_help_button: ui.button
    get_backup_button: ui.button
    get_xml_button: ui.button
    gui_ai_panel: ui.tab_panel
    gui_color_panel: ui.tab_panel
    gui_debug_panel: ui.tab_panel
    gui_left_drawer: ui.left_drawer
    gui_main_column: ui.column
    gui_main_tabs_container: ui.tabs
    gui_right_drawer: ui.right_drawer
    gui_tab_panels: ui.tab_panels
    gui_tasker_object_panel: ui.tab_panel
    gui_view_toolbar: ui.row
    health_check_button: ui.button
    indent_label: ui.label
    indent_option: ui.select
    language_label: ui.label
    language_optionmenu: ui.select
    list_unnamed_items_checkbox: ui.checkbox
    model_to_use_label: ui.label
    notify_timeout_label: ui.label
    notify_timeout_optionmenu: ui.select
    open_view_in_new_window_checkbox: ui.checkbox
    prebuild_map_checkbox: ui.checkbox
    picker_dialog: ui.dialog
    picker_engine: ui.color_picker
    picker_title_label: ui.label
    preferences_checkbox: ui.checkbox
    pretty_checkbox: ui.checkbox
    profile_buttons_row: ui.row
    project_buttons_row: ui.row
    redo_edit_button: ui.button
    refactor_button: ui.button
    reset_button: ui.button
    run_task_button: ui.button
    runtime_checkbox: ui.checkbox
    scene_buttons_row: ui.row
    scroll_area: ui.scroll_area
    show_apikeys_button: ui.button
    sidebar_detail_option: ui.select
    specific_name_msg_label: ui.label
    specific_profile_optionmenu: ui.select
    specific_project_optionmenu: ui.select
    specific_scene_optionmenu: ui.select
    specific_task_optionmenu: ui.select
    tab_analyze: ui.tab
    tab_colors: ui.tab
    tab_debug: ui.tab
    tab_specific_name: ui.tab
    task_action_label: ui.label
    task_action_limit: ui.slider
    task_buttons_row: ui.row
    task_flow_button: ui.button
    taskernet_checkbox: ui.checkbox
    twisty_checkbox: ui.checkbox
    undo_edit_button: ui.button
    undo_next_label: ui.label
    upgrade_button: ui.button
    upgrade_container: ui.column
    variable_xref_button: ui.button
    viewlimit_label: ui.label
    viewlimit_optionmenu: ui.select
    viewlimit_query_button: ui.button
    whats_new_button: ui.button
    bold_checkbox: ui.checkbox
    highlight_checkbox: ui.checkbox
    italicize_checkbox: ui.checkbox
    underline_checkbox: ui.checkbox
    font_out_label: ui.label
    # The Get XML From Android Device section's widgets (userintr_android builds them).
    ip_entry: ui.input
    port_entry: ui.input
    file_entry: ui.input
    list_files_button: ui.button
    list_files_query_button: ui.button
    helper_tasks_button: ui.button
    helper_project_button: ui.button
    set_xml_details_button: ui.button
    label_or: ui.label
    # Plain values the settings and the event handlers keep.
    android_check_ids: bool
    android_verify: bool
    close_tabs_on_exit: bool
    default_font: str
    doing_diagram: bool
    event: bool
    first_time: bool
    font_table: dict
    guiview: bool
    map_in_progress: bool
    open_view_in_new_window: bool
    prebuild_map: bool
    reset_debug_at_end: bool
    scene_editor_session: dict | None
    textview: Any
    textviews: list
    view_limit: int
    # Set to None until the layout, the settings restore or a dialog gives them a value, and then
    # set to a widget, a string or a flag; typed loosely for that reason rather than as the Optional that
    # every use would then have to test.
    _version_check: Any
    ai_analysis: Any
    ai_analysis_window: Any
    ai_analyze_button: Any
    ai_apikey: Any
    ai_apikey_window: Any
    ai_model: str
    ai_model_option: Any
    ai_name: str
    ai_profile_label: Any
    ai_project_label: Any
    ai_prompt: Any
    ai_scene_label: Any
    ai_task_label: Any
    appearance_mode: Any
    bold: Any
    color_lookup: Any
    conditions: Any
    dark_mode: Any
    debug: Any
    diagramview_window: Any
    display_detail_level: Any
    displaying_extended_list: Any
    everything: Any
    exit: Any
    file: Any
    fix_dialog: Any
    font: Any
    highlight: Any
    indent: Any
    is_map: Any
    italicize: Any
    mapview_window: Any
    miscview_window: Any
    named_item: Any
    preferences: Any
    refactor_dialog: Any
    rerun: Any
    reset: Any
    restore_dialog: Any
    single_name_status: Any
    single_profile_name: Any
    single_project_name: Any
    single_scene_name: Any
    single_task_name: Any
    tab_to_use: Any
    taskernet: Any
    treeview_window: Any
    twisty: Any
    underline: Any
    video_window: Any

    def __init__(self: "MyGui", state: RunState) -> None:
        """Initialize the GUI and set up all necessary state and layout.

        Args:
            state (RunState): the run state this window shows and edits.
        """
        logger.info("Starting GUI")
        self.state = state
        self.initialization = True
        # The 'Output Folder' box, once the layout has built it -- see
        # guiwins_tabs.create_output_directory_section.
        self.output_directory_input: ui.input | None = None
        # The What Fires When? dialog while one is up -- see fire_simulator_event.
        self.firesim_dialog: ui.dialog | None = None
        # Which sections of the right drawer are open, by key -- see guiwins_drawers._drawer_section.
        self.drawer_sections: dict[str, bool] = {}

        # 1. Initialize settings and state
        initialize_gui(self)
        self.set_defaults()
        self.state.mygui = self

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

        # 3. Build the UI Layout directly!  Nothing more is done if that fails: the message is the window.
        if not self._build_layout():
            return

        # Now restore the settings and update the fields if not resetting.
        if not self.state.program_arguments.reset:
            self.event_handlers.settings.restore_settings_event()

            # 3. Synchronize runtime arguments
            if self.color_lookup and not self.state.colors_to_use:
                capture_gui_state(self, {}, state=self.state)

        # A view limit asked for on this run's command line goes on last, over whatever the
        # restore above put in place.
        self.seed_view_limit_from_command_line()

        # Check if newer version of our code is available on Pypi, and any share linked to TaskerNet.
        check_for_updates(self)

        # See if we have a changelog, and get it if we do.  This must go before 'self.process_current_messages()' call.
        check_for_changelog(self)

        self._populate_object_pulldowns()

        # See if we have any carryover error messages from the AI run.
        # Note: this must go after the settings restoration.
        display_error_file_and_ai_response(self)

        self.initialization = False

    def _build_layout(self: "MyGui") -> bool:
        """Build the window's layout.  False if that failed, and the failure is what the window now shows."""
        try:
            initialize_screen(self)
        except Exception as e:
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
            return False
        return True

    def _populate_object_pulldowns(self: "MyGui") -> None:
        """Fill the Project/Profile/Task pulldowns from what is loaded, loading the restored file if need be."""
        # Populate the Target specific item if we have a single Project, Profile, or Task name set.
        if (
            self.state.tasker_root_elements["all_projects"]
            or self.state.tasker_root_elements["all_profiles"]
            or self.state.tasker_root_elements["all_tasks"]
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
        elif self.state.file_to_get or self.file:
            if not self.state.file_to_get:
                self.state.file_to_get = self.file
            return_code = get_xml(self.debug, self.appearance_mode, state=self.state)
            if return_code == 0:
                refresh_tasker_object_pulldowns(self)

    def seed_view_limit_from_command_line(self: "MyGui") -> None:
        """Put a view limit given with -view_limit in force, over the restored settings.

        The settings file knows nothing about this run's command line, so the restore that
        has just finished would quietly discard a limit the user asked for a moment ago.
        The value goes in through the same handler a user's own change goes through, so the
        pulldown moves with it rather than sitting on a number that is no longer true.

        Once only, and the command line's value is dropped on the way past: the GUI builds a
        fresh MyGui for every page load, and a limit the user changed in the window during
        the session must not be put back by a refresh.
        """
        view_limit = self.state.cli_view_limit
        if view_limit is None:
            return
        self.state.cli_view_limit = None
        self.event_handlers.settings.viewlimit_event(str(view_limit))

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
        self.android_last_ipaddr = ""
        self.android_last_port = ""
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
        # Where reports, exports and the view files go.  Empty = Documents/MapTasker (outdir).
        self.output_directory = ""

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
        self.state.program_arguments.profiles_per_line = DIAGRAM_PROFILES_PER_LINE

        handlers = getattr(self, "event_handlers", None)
        if handlers is None:
            return

        # These two own a pulldown in the settings drawer and know how to move it.
        handlers.settings.viewlimit_event(str(VIEW_LIMIT_DEFAULT))
        handlers.settings.notify_timeout_event(NOTIFY_TIMEOUT_DEFAULT)

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
        if self.state.program_arguments.reset:
            return

        language = self.state.program_arguments.language or "English"
        # The saved value is the English language name ("German"); anything else (a hand-edited
        # settings file, or a translated name written by an older version) is not something
        # set_language can resolve, so leave the default English in place.
        if language not in self.state.languages:
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
        if self.state.program_arguments.reset:
            return

        saved_duration = self.state.program_arguments.notify_timeout
        if saved_duration is not None:
            # The pulldown does not exist yet; notify_timeout_event skips it when it is absent.
            self.event_handlers.settings.notify_timeout_event(saved_duration)

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
            not self.state.tasker_root_elements["all_projects"]
            and not self.state.tasker_root_elements["all_profiles"]
            and not self.state.tasker_root_elements["all_tasks"]
        ) or self.android_ipaddr:
            if self.android_ipaddr == "" or self.android_file == "":
                if not self.prompt_and_get_file(self.debug, self.appearance_mode):
                    return False

            # We have a file identified.  We now have to read it in.
            else:
                filename_location = self.android_file.rfind(self.state.slash) + 1
                file_to_use = self.state.program_arguments.android_file[filename_location:]
                if not file_to_use:
                    file_to_use = self.android_file[filename_location:]
                try:
                    self.state.file_to_get = open(file_to_use, encoding="utf-8")
                except FileNotFoundError:
                    # self.display_message_box(
                    #     f"XML file {file_to_use} not found.",
                    #     "Red",
                    # )
                    return False

                # Display the current file
                display_current_file(self, file_to_use)

                # Get the XML
                self.state.program_arguments.gui = True
                try:
                    get_the_xml_data(state=self.state)
                except MapTaskerError as error:
                    record_error(error, self.state)
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
        return_code = get_xml(debug, appearance_mode, state=self.state)
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
        file_name = getattr(self.state.file_to_get, "name", self.state.file_to_get)
        if file_name and isinstance(file_name, str):
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
    def build_the_tree(self) -> list[dict[str, Any]]:
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

        tree_data: list[dict[str, Any]] = []
        root = self.state.tasker_root_elements
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
                    profile_list = _build_profiles(root, profile_ids, project, state=self.state)

                # Project has no Profiles
                else:
                    profile_list = [no_profiles]

                # Process Scenes
                # None when the Project has no <scenes> element, or an empty one.
                scene_names = projects[project]["xml"].findtext("scenes") or None
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
        error_message = self._name_problem(the_name, element_name)

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

        self._say_name_accepted(the_name, element_name)
        return True

    def _name_problem(self: "MyGui", the_name: str, element_name: str) -> list[str] | None:
        """Why this single-item name cannot be used, as the lines to show, or None if it can.

        Also clears what the name left behind when the file it was meant for is gone.
        """
        _prime = self.state
        error_message = None

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
        return error_message

    def _say_name_accepted(self: "MyGui", the_name: str, element_name: str) -> None:
        """Say in the message box that the name was taken (or, for "None", that all are shown)."""
        _translate = translate_string
        _prime = self.state
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

    def extract_settings(self, temp_args: ProgramArguments | dict[str, Any]) -> None:
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
        # A blank saved prompt means "none chosen", not "prompt with nothing": keep the default
        # rather than leave the Analyze tab showing Prompt: '' and the 'Run Analysis' button red
        # for a prompt the user never took away.
        if "ai_prompt" in temp_args and not temp_args["ai_prompt"]:
            temp_args["ai_prompt"] = AI_PROMPT
        for key, value in temp_args.items():
            if key is not None:
                setattr(self, key, value)
                # Start log if debug
                if key == "debug" and value:
                    log_startup_values(state=self.state)
                # Make the modification based on the specfic setting
                # A saved value is whatever type the setting is (str, int, bool); its handler reads it as one.
                _ = self.restore_display(key, cast("Any", value))
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
        """
        Restores display settings
        Args:
            key: str - Setting name
            value: str - Setting value
        Returns:
            message: str - Message describing setting change
        {Processing Logic}:
            - Settings that have no widget of their own are just set as attributes
            - Every other setting is looked up in the tables above and run through its handler
            - The message that comes back is tidied up for a setting that has no value
        """
        message = ""
        if key in RESTORE_KEYS_TO_IGNORE:
            # Process specific items that have no effect on the GUI: set the attribute, if there is one.
            if hasattr(self, key):
                setattr(self, key, value)
        else:
            handled, message = self._restore_setting(key, value)
            # Catch bug where we have a key but nothing to process it.
            if not handled and self.debug:
                logger.debug(
                    f"userintr: no lambda rtn for key or value: {key}, {value}",
                )
        return tidy_restore_message(message)

    def _restore_setting(self, key: str, value: str) -> tuple[bool, str | None]:
        """Run the handler for one restored setting.  Returns (a handler exists, the message it gave).

        The message can be None: display_detail_level, file, font, indent and the single object
        names all answer with nothing, because they say what they did themselves.
        """
        if key in RESTORE_CHECKBOXES:
            attribute, label = RESTORE_CHECKBOXES[key]
            return True, self.select_deselect_checkbox(getattr(self, attribute), value, label, display=False)
        if key in RESTORE_ANDROID_LABELS:
            return True, f"{translate_string(RESTORE_ANDROID_LABELS[key])} {translate_string('set to')} {value}\n"
        if key in RESTORE_EVENT_HANDLERS:
            return True, getattr(self.event_handlers.settings, RESTORE_EVENT_HANDLERS[key])(value)
        if key in RESTORE_SINGLE_NAMES:
            return True, self.process_single_name_restore(RESTORE_SINGLE_NAMES[key], value)
        if key == "appearance_mode":
            # Moves the "Dark Mode" switch and repaints the window.  Without this the saved
            # appearance mode landed on self (every restored key does, via setattr above) and
            # then sat there unused, which is what made dark mode look like it was never saved.
            return True, restore_appearance_mode(self, value)
        if key == "file":
            return True, self.display_and_set_file(value)
        if key == "task_action_warning_limit":
            return True, self.tasklimit_set(value)
        return False, None

    # ################################################################################
    # Select or deselect a checkbox based on the value passed in
    # ################################################################################
    def select_deselect_checkbox(
        self,
        checkbox: ui.checkbox,
        checked: object,
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
        checkbox_value = bool(checkbox.value)

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
            self.state.file_to_get = self.file

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
                if my_name in SINGLE_ITEM_LABELS:
                    self._show_restored_name(my_name, name_entered)
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

    def _show_restored_name(self, my_name: str, name_entered: str) -> None:
        """Select a restored name in its own pulldown, clear the others, and say so on the Analyze tab."""
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
        toggle_value: bool | str | None,
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
            new_file_path = output_path(new_file_name, state=self.state)
            rename_file(output_path(ANALYSIS_FILE, state=self.state), new_file_path)
            text = translate_string("saved as")
            self.display_message_box(
                f"{ANALYSIS_FILE} {text} {new_file_path}",
                "green",
            )
            analysis_response = f"Analysis Response saved in file: {new_file_path}\n\n" + analysis_response.replace(
                ANALYSIS_FILE,
                new_file_path,
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

    The handlers of each feature are a group of their own, held here as an attribute -- hub.ai,
    hub.android, hub.carry, hub.editors, hub.loading, hub.prebuild, hub.reports, hub.settings, hub.tasktests,
    hub.tools (the tools menu's windows and the edit history) and hub.views (the Map, Diagram, Misc and Tree
    views) -- and what is defined on this class is what two or more of them share: saving the whole
    configuration and the handlers of the About and Help menu.  Each group reaches this class as self.hub,
    and another group as self.hub.<group>.
    """

    def __init__(self, gui_instance: MyGui) -> None:
        """Initialize MapTaskerEventHandlers with a reference to the main MyGui instance."""
        # We store a reference to the main MyGui instance so we can read
        # checkbox states, inputs, and update the UI elements.
        self.gui = gui_instance
        self.ai = AIEventHandlers(self)
        self.android = AndroidEventHandlers(self)
        self.carry = CarryEventHandlers(self)
        self.editors = EditorEventHandlers(self)
        self.loading = LoadingEventHandlers(self)
        self.prebuild = PrebuildEventHandlers(self)
        self.reports = ReportEventHandlers(self)
        self.settings = SettingsEventHandlers(self)
        self.tasktests = TaskTestEventHandlers(self)
        self.tools = ToolEventHandlers(self)
        self.views = ViewEventHandlers(self)

    @property
    def state(self) -> RunState:
        """The run state the window shows and edits: its own, which the handler groups read."""
        return self.gui.state

    async def save_whole_configuration(self) -> bool:
        """The 'Save To Current File' of the Refactor, Fix Findings, Restore and TaskerNet Updates dialogs.

        Returns True when the dialog's list must be rebuilt.

        The same two steps, in the same order, as every Edit dialog's button of that name
        (see userintr_editors.save_edited_task_to_current_file_event): write the WHOLE
        configuration to a new timestamped copy of the loaded file, then switch the app
        over to that copy.  The original file is never written to.

        Here rather than in guiwins_fix or guiwins_restore for the reason make_jump is: those
        modules build widgets and know nothing about what a backup is, and reaching back into
        this one for the save path would be a circular import.  A method rather than a closure
        in each dialog's event because the two dialogs need exactly the same three answers.

        Reported here rather than returned as a message, because the three outcomes are
        three different things to say and only one of them is an error:

          SAVED AND SWITCHED.  The ordinary case.  The list has to be rebuilt afterwards
          -- the reload replaces every lookup table, so the plan is holding elements that
          are no longer in the configuration, which is exactly what mapfix.apply's
          and maprefac.apply's attachment checks would refuse on.

          SAVED, BUT THE COPY WOULD NOT LOAD.  The file is on disk and the work is safe;
          what failed is the switch to it.  Rebuilt anyway, because the tables may have
          been part-replaced -- the same reading the Edit dialogs take of this case.

          NOT SAVED.  Nothing was written and nothing changed, so there is nothing to
          rebuild and the list is left exactly as it was.
        """
        notice = await show_save_in_progress_notice()
        # Dismissed however this ends: an exception from the write or the reload must not leave
        # the "in progress" spinner on screen for ever, which reads as a hung save.
        try:
            saved, result = write_full_backup_to_current_file(state=self.state)
            if not saved:
                ui.notify(f"{translate_string('Could not save to current file:')} {result}", type="negative")
                return False

            loaded, error = reload_saved_copy_and_refresh(self.gui, result)
        finally:
            notice.dismiss()

        if not loaded:
            ui.notify(
                f"{translate_string('Saved a copy to')} {result}, "
                f"{translate_string('but it could not be loaded:')} {error}",
                type="warning",
            )
            return True

        ui.notify(
            f"{translate_string('Saved a copy to')} {result} "
            f"{translate_string('and loaded it.  The original file was left unchanged.')}",
            type="positive",
            position="top",
        )
        return True

    # ==========================================
    # 4. TEXT VIEW CONTROLS
    # ==========================================

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
        updated, complaint = update_maptasker()

        # The update did not happen: say so, say what went wrong, and stay where we are.
        # Restarting would just bring back the same version, but wearing a "Program
        # updated" message.
        if not updated:
            # Only the tail of it: the installers print a wall of progress before the
            # sentence that matters.
            last_lines = "\n".join(complaint.splitlines()[-3:]) if complaint else ""
            the_view.display_message_box(
                translate_string("The update failed and MapTasker is still on the version you were running."),
                "Red",
            )
            if last_lines:
                the_view.display_message_box(last_lines, "Red")
            the_view.display_message_box(
                translate_string(
                    "Exit MapTasker and update it from the command line: 'pip install --upgrade maptasker'.",
                ),
                "Red",
            )
            return

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
        url = "https://github.com/mctinker/Map-Tasker/issues"
        issue_text = translate_string(
            "Go to your browser and create a new issue or feature request, providing as much detail as possible.",
        )
        the_view = self.gui
        try:
            webbrowser.open(url, new=2)
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
    def query_event(self, query_name: str) -> None:
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
        query_name = str(query_name).lower()
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
