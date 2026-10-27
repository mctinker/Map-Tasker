"""guiwins_drawers: the screen's frame -- header, left and right drawers, and the main body.

initialize_screen lays the page out; the sections of each drawer (execution, views, history, analysis, simulation)
and the Specific Name pulldowns are built here.  The tabs of the main body are guiwins_tabs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from maptasker.src.core.maputil2 import translate_string
from maptasker.src.core.sysconst import NOTIFY_TIMEOUT_DEFAULT, logger
from maptasker.src.gui import webassets
from maptasker.src.gui.guiutils import add_logo
from maptasker.src.gui.guiwins import (
    PREBUILD_POLL_SECONDS,
    STARTUP_DARK_MODE,
    apply_appearance_mode,
    clear_notification_log,
    display_notification_log,
    install_notification_timeout,
    set_notification_timeout,
)
from maptasker.src.gui.guiwins_canvas import _register_canvas_events
from maptasker.src.gui.guiwins_nav import register_finding_clicks
from maptasker.src.gui.guiwins_tabs import (
    create_analyze_tab_content,
    create_colors_tab,
    create_file_and_message_buttons_section,
    create_font_section,
    create_help_options_section,
    create_indentation_section,
    create_language_selection_section,
    create_name_display_options_section,
    create_notification_duration_section,
    create_output_directory_section,
    create_settings_buttons_section,
    create_specific_name_tab,
    create_task_action_limit_section,
    create_view_limit_section,
    get_rid_of_windows_and_exit,
)

if TYPE_CHECKING:
    from maptasker.src.core.primitem import RunState
    from maptasker.src.gui.userintr import MyGui


# =========================================================================
# Initialize the GUI screen layout using NiceGUI with split sidebars and main content area.
# =========================================================================
# How often the window looks at the edit history to run the Task tests again after an edit.
TASK_TESTS_POLL_SECONDS = 1.0


def document_language_html(state: RunState) -> str:
    """Head markup declaring the GUI's language and asking the browser not to translate it.

    Without a lang attribute the browser sniffs the text instead.  With the GUI set to
    German, Chrome detects German, sees a browser configured for English, and helpfully
    translates the entire UI back to English -- undoing every translation MapTasker just
    applied.  That is indistinguishable, on screen, from the translations having failed.

    So state the language outright, and mark the UI as not-to-be-translated: the user
    already chose their language in the sidebar, and that choice should win over the
    browser's guess.  'translate="no"', the notranslate class and the google meta tag are
    all listed because browsers vary in which one they honour.

    Note the lang code is baked in when the page is built.  A language switched at runtime
    rebuilds the layout but not the document, so language_set_event() updates the live
    attributes itself -- see set_document_language_js().
    """
    lang_code = state.languages.get(state.program_arguments.language or "English", "en")
    return f'<meta name="google" content="notranslate"><script>{set_document_language_js(lang_code)}</script>'


def set_document_language_js(lang_code: str) -> str:
    """The JavaScript that stamps a language onto the live document.

    Shared by the initial page build and the runtime language switch so the two can never
    drift apart.  The lang code comes from PrimeItems.languages, so it is always one of our
    own short ISO codes -- never user text -- and is safe to interpolate.
    """
    return (
        f'document.documentElement.lang = "{lang_code}";'
        'document.documentElement.setAttribute("translate", "no");'
        'document.documentElement.classList.add("notranslate");'
    )


def inject_shared_head_styles(state: RunState) -> None:
    """Links the stylesheet and script shared by every page of the app (maptasker/assets/css and
    maptasker/assets/js: scrollbar theming, light-mode overrides, Map/Diagram/Tree table layout,
    the Diagram view's click-to-highlight connector styling, and the Scene canvas's handlers),
    plus the document's language declaration (see document_language_html).

    ui.add_head_html() only affects the page it's called from -- each NiceGUI @ui.page is its own
    independent document. Call this from every page function (the main window's initialize_screen()
    and the "/popout/{view_type}" route in rungui.py), or a popped-out window renders Diagram
    connectors that respond to clicks (the JS wiring is unaffected) but never visibly highlight,
    since the .connector-highlight rule defined here would simply be missing from that page.
    """
    # Every page needs this for the same reason it needs the CSS below: each @ui.page is its
    # own document, so a popped-out Map/Diagram window would otherwise be left for the
    # browser to sniff and translate on its own.
    ui.add_head_html(document_language_html(state=state))

    ui.add_head_html(webassets.head_html())


def initialize_screen(self: MyGui) -> None:
    """Initializes the main GUI screen layout using NiceGUI with split sidebars."""
    logger.info("Building UI Layout...")

    inject_shared_head_styles(state=self.state)
    # Before anything can notify: the wrapper has to be in place for the first message, and
    # start-up is capable of producing several (see restore_settings_event's running report).
    install_notification_timeout()
    set_notification_timeout(getattr(self, "notify_timeout", NOTIFY_TIMEOUT_DEFAULT))
    # While the layout is still being built, rather than when a Scene designer first opens --
    # see guiwins_canvas._register_canvas_events for why the timing is the whole point.
    _register_canvas_events()
    # Same timing, same reason: a clicked Health Check finding emits an event this has to be
    # subscribed to before the browser has the layout (see register_finding_clicks).
    register_finding_clicks(self)

    # =========================================================================
    # 1. HEADER
    # =========================================================================
    _create_header(self)

    # =========================================================================
    # 2. LEFT SIDEBAR: CONFIGURATIONS, DROPDOWNS & CHECKBOXES
    # =========================================================================
    _create_left_drawer(self)

    # =========================================================================
    # 3. RIGHT SIDEBAR: ALL ACTION, HELP & SETTINGS BUTTONS
    # =========================================================================
    _create_right_drawer(self)

    # =========================================================================
    # 4. MAIN BODY CONTENT AREA
    # =========================================================================
    _create_main_body(self)

    if self.tab_to_use:
        # The Assistance tab was called "Debug" in settings files saved by earlier versions.
        if self.tab_to_use == "Debug":
            self.tab_to_use = "Assistance"
        self.gui_main_tabs_container.set_value(self.tab_to_use)


def _create_header(self: MyGui) -> None:
    """The title bar: the app's name, the MapTasker logo and the Dark Mode switch."""
    with ui.header().classes("bg-blue-900 text-white p-4 justify-between items-center") as self.gui_header:
        ui.label("MapTasker").classes("text-2xl font-bold")
        add_logo(self, "maptasker")

        # Stated outright rather than left to ui.dark_mode()'s own default: ui.run()'s
        # dark=None (auto) is applied before Vue mounts and this element then overrides it,
        # so this -- not the system appearance, and not the switch -- is what the page comes
        # up as. Only the mode the window OPENS in: restore_settings_event() runs after this
        # whole layout is built and puts the saved mode on top (see restore_appearance_mode).
        self.dm_controller = ui.dark_mode(value=STARTUP_DARK_MODE)

        self.dark_mode_switch = ui.switch(
            translate_string("Dark Mode"),
            value=STARTUP_DARK_MODE,
            on_change=lambda e: apply_appearance_mode(self, bool(e.value)),
        )


def _create_left_drawer(self: MyGui) -> None:
    """The left drawer: every option that decides what the output shows and how."""
    with (
        ui.left_drawer(value=True, fixed=True)
        .props("breakpoint=0")
        .classes(
            "bg-gray-100 dark:bg-gray-800 p-4 w-96 force-scrollbar gap-y-0 m-0 p-0 leading-none",
        ) as self.gui_left_drawer
    ):
        ui.label(translate_string("Display Options")).classes("text-lg font-bold mb-2 gap-y-0 m-0 p-0 leading-none")

        # Detail level pulldown
        self.sidebar_detail_option = (
            ui.select(
                options=["0", "1", "2", "3", "4", "5"],
                value=str(self.display_detail_level),
                label=translate_string("Detail Level"),
                on_change=self.event_handlers.settings.detail_selected_event,
            )
            .tooltip(translate_string("0 = least detail, 5 = most detail."))
            .classes("w-full")
            .props("dense")
        )

        # Core Feature Checkboxes
        self.everything_checkbox = ui.checkbox(
            translate_string("Just Display Everything!"),
            on_change=self.event_handlers.settings.everything_event,
        ).tooltip(
            translate_string(
                "Enables the display of Conditions, TaskerNet Info, Preferences, the Directory, and Prettier Output.",
            ),
        )

        self.conditions_checkbox = ui.checkbox(
            translate_string("Display Conditions"),
            on_change=self.event_handlers.settings.condition_event,
        ).tooltip(
            translate_string(
                "Enables the display of Profile Conditions (e.g. State, Event, etc.) details in the output.",
            ),
        )

        self.taskernet_checkbox = ui.checkbox(
            translate_string("Display TaskerNet Info"),
            on_change=self.event_handlers.settings.taskernet_event,
        ).tooltip(translate_string("Enables the display of TaskerNet Descriptions in the output."))

        self.preferences_checkbox = ui.checkbox(
            translate_string("Display Tasker Preferences"),
            on_change=self.event_handlers.settings.preferences_event,
        ).tooltip(translate_string("Enables the display a breakdown of the Tasker system Preferences in the output."))

        self.twisty_checkbox = ui.checkbox(
            translate_string("Hide Task Details Under Twisty"),
            on_change=self.event_handlers.settings.twisty_event,
        ).tooltip(
            translate_string(
                "When enabled, Task details are hidden under a twisty (expand/collapse) control in the output.",
            ),
        )

        self.directory_checkbox = ui.checkbox(
            translate_string("Display Directory"),
            on_change=self.event_handlers.settings.directory_event,
        ).tooltip(translate_string("Enables the display of the Project/Profile/Task/Scene Directory in the output."))

        self.pretty_checkbox = ui.checkbox(
            translate_string("Display Prettier Output"),
            on_change=self.event_handlers.settings.pretty_event,
        ).tooltip(translate_string("Enables the display of aligned text in the output."))

        create_name_display_options_section(self)
        create_task_action_limit_section(self)
        create_indentation_section(self)
        create_language_selection_section(self)
        create_font_section(self)
        create_view_limit_section(self)
        create_notification_duration_section(self)
        create_output_directory_section(self)


def _create_right_drawer(self: MyGui) -> None:
    """The right drawer: every action, report, setting and help button."""
    with (
        ui.right_drawer(value=True, fixed=True)
        .props("breakpoint=0")
        .classes(
            "bg-gray-100 dark:bg-gray-800 p-4 w-80 force-scrollbar flex flex-col items-center text-center",
        )
        # NiceGUI's drawer wraps its children, and a column that wraps starts a second column to the right
        # of the first as soon as the buttons are taller than the window -- off-screen, behind a horizontal
        # scroll bar.  Not wrapping makes the drawer scroll up and down instead.
        .style("flex-wrap: nowrap") as self.gui_right_drawer
    ):
        ui.label(translate_string("Actions & Control")).classes("text-lg font-bold mb-2 self-center")

        ui.label(translate_string("Execution")).classes("text-xs font-bold uppercase text-gray-400 mt-2 self-center")
        _create_execution_section(self)

        ui.label(translate_string("File Operations")).classes(
            "text-xs font-bold uppercase text-gray-400 mt-3 self-center",
        ).style("margin-top:5px")
        create_file_and_message_buttons_section(self)

        ui.label(translate_string("Display Views")).classes(
            "text-xs font-bold uppercase text-gray-400 mt-3 self-center",
        )
        _create_view_buttons_section(self)
        # Health Check stays out where it can be seen -- it is the most used of these and the others
        # (Fix Findings beside it, Missing Resources) are its follow-ups.  The rest are tucked into two
        # sections that open with a click, so the drawer is a few lines tall until one is wanted.
        _create_health_check_row(self)

        with _drawer_section(self, "history", "Compare & History", "history"):
            _create_history_buttons_section(self)
            _create_trend_button(self)

        with _drawer_section(self, "analyze", "Analyze", "analytics"):
            _create_resources_button(self)
            _create_analysis_buttons_section(self)
            _create_monitor_button(self)

        ui.button(translate_string("Clear"), on_click=self.event_handlers.clear_view_event).classes(
            "bg-blue-500"
        ).style("margin-top:-6px")

        ui.label(translate_string("Application Settings")).classes(
            "text-xs font-bold uppercase text-gray-400 mt-4 self-center",
        ).style("margin-top:5px")
        create_settings_buttons_section(self)

        # The "Buy Me A Coffee" logo and button close out the drawer.  add_logo() re-enters
        # gui_right_drawer itself rather than nesting inside a wrapper here, so the bottom
        # spacing (mt-auto) lives on the elements it creates, not on a container.
        add_logo(self, "coffee")


def _drawer_section(self: MyGui, key: str, title: str, icon: str) -> ui.expansion:
    """One collapsible group of buttons in the right drawer, closed until it is wanted.

    Whether each section is open is kept on the window (drawer_sections), so a section the user opened stays
    open when the drawer is drawn again -- a change of language or appearance rebuilds the page -- and is not
    saved between sessions: they start folded, which is the point of having them.  `key` is the section's
    identity; `title` is what the header says.
    """
    section = (
        ui.expansion(translate_string(title), icon=icon, value=self.drawer_sections.get(key, False))
        .classes(
            "w-full rounded bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-gray-100 font-bold text-xs uppercase"
        )
        .props("dense dense-toggle")
    )
    section.on_value_change(lambda event: self.drawer_sections.__setitem__(key, bool(event.value)))
    return section


def _create_execution_section(self: MyGui) -> None:
    """The Execution group: Get Local XML File, Exit, and the two checkboxes that shape what Exit and a new view do."""
    get_file_color = "green" if self.state.file_to_get else "red"
    blink_class = "" if self.state.file_to_get else " animate-pulse"

    self.get_xml_button = ui.button(
        translate_string("Get Local XML File"),
        color=get_file_color,
        on_click=self.event_handlers.loading.getxml_event,
        icon="folder",
    ).classes(f"w-full justify-center {blink_class}")
    with self.get_xml_button:
        ui.tooltip(
            translate_string(
                "Fetch XML from a local drive on this computer.\n\nThe XML fetched will become the current source for MapTasker commands.",
            ),
        ).style("white-space: pre-wrap")

    self.exit_button = ui.button(
        translate_string("Exit"),
        color="orange",
        on_click=lambda: get_rid_of_windows_and_exit(self),
    ).classes(
        "w-full bg-red-600 text-white mt-0 justify-center",
    )

    self.close_tabs_on_exit_checkbox = (
        ui.checkbox(translate_string("Close Tabs On Exit"))
        .bind_value(self, "close_tabs_on_exit")
        .props("dense")
        .classes("text-xs mt-0")
    )
    with self.close_tabs_on_exit_checkbox:
        ui.tooltip(
            translate_string(
                "When enabled, clicking 'Exit' also closes the main MapTasker window and any "
                "Map/Diagram windows/tabs it opened.\n\nWhen disabled, 'Exit' shuts down MapTasker "
                "but leaves those windows/tabs open.",
            ),
        ).style("white-space: pre-wrap")

    self.open_view_in_new_window_checkbox = (
        ui.checkbox(translate_string("Open View In New Window"))
        .bind_value(self, "open_view_in_new_window")
        .props("dense")
        .classes("text-xs mt-0")
        .style("margin-top:-6px")
    )
    with self.open_view_in_new_window_checkbox:
        ui.tooltip(
            translate_string(
                "When enabled, each Map/Diagram request opens in its own new window/tab, so you can "
                "keep earlier ones up alongside it to compare.\n\nWhen disabled, a request reuses "
                "that view's existing window/tab, replacing what's in it.\n\nLeave it off unless you "
                "want to compare: a brand new window/tab is the one your browser may block, since "
                "it gets opened once the view has finished building rather than the instant you click.",
            ),
        ).style("white-space: pre-wrap")

    self.prebuild_map_checkbox = (
        ui.checkbox(translate_string("Pre-Build The Map"))
        .bind_value(self, "prebuild_map")
        .props("dense")
        .classes("text-xs mt-0")
        .style("margin-top:-6px")
    )
    with self.prebuild_map_checkbox:
        ui.tooltip(
            translate_string(
                "When enabled, the Map is built in the background as soon as a file has been loaded, and "
                "again each time you choose a different single Project, Profile, Task or Scene, so "
                "the Map button opens it at once.\n\nWhen disabled, the Map is built when you ask for it.\n\n"
                "Pressing Map or Diagram while it is still building waits for it to finish.  Changing a "
                "setting, or editing the configuration, before you press Map means it is built again.  "
                "It uses the computer for a few seconds after each file is loaded or item chosen, whether "
                "or not you go on to ask for the Map.",
            ),
        ).style("white-space: pre-wrap")
    # Looks every moment or two for a configuration it has not yet built the Map of -- a file
    # that has just been loaded, however it was: the file picker, the Android fetch, Undo.
    ui.timer(PREBUILD_POLL_SECONDS, self.event_handlers.prebuild.prebuild_tick)


def _create_view_buttons_section(self: MyGui) -> None:
    """The Map, Diagram and Tree buttons, side by side."""
    with ui.row().classes("w-full justify-center gap-2 gap-y-0 mt-0"):
        v_map = ui.button(translate_string("Map"), on_click=lambda: self.event_handlers.view_event("map")).classes(
            "bg-blue-500",
        )
        with v_map:
            ui.tooltip(
                translate_string(
                    "Displays the Map view.\n\nUse this to display the Tasker configuration of your Projects, Profiles, Tasks, and Scenes.",
                ),
            ).style("white-space: pre-wrap")
        v_diagram = ui.button(
            translate_string("Diagram"),
            on_click=lambda: self.event_handlers.view_event("diagram"),
        ).classes(
            "bg-blue-500",
        )
        with v_diagram:
            ui.tooltip(
                translate_string(
                    "Displays the Diagram view.\n\nUse this to visualize the relationships between your Projects, Profiles, Tasks, and Scenes.",
                ),
            ).style("white-space: pre-wrap")
        v_tree = ui.button(
            translate_string("Tree"),
            on_click=lambda: self.event_handlers.view_event("tree"),
        ).classes(
            "bg-blue-500",
        )
        with v_tree:
            ui.tooltip(
                translate_string(
                    "Displays the Tree view.\n\nUse this to navigate the hierarchical structure of your Projects, Profiles, Tasks, and Scenes.",
                ),
            ).style("white-space: pre-wrap")


def _create_health_check_row(self: MyGui) -> None:
    """Health Check and Fix Findings, sharing one row."""
    # Health Check and Fix Findings share a row, each taking half of it: Fix Findings is the
    # answer to the report Health Check produces, so it sits beside it.  Not a fourth button
    # in the row above: the drawer is w-80, and a fourth button wraps.  At half width a
    # label beside its icon wraps ("HEALTH / CHECK"), so the icon goes above the label and
    # the side padding is halved, which leaves each label room for one line.
    # Coloured through the "color" prop rather than a bg-* class, the way the Get XML and
    # Exit buttons are.  Quasar puts its own bg-primary on every button, and that wins over
    # a Tailwind bg-* added here -- a bg-teal-600 class renders plain blue.
    health_row = ui.row().classes("w-full no-wrap gap-2").style("margin-top:-6px")
    with health_row:
        self.health_check_button = (
            ui.button(
                translate_string("Health Check"),
                color="teal",
                on_click=self.event_handlers.reports.health_check_event,
                icon="health_and_safety",
            )
            .classes("flex-1 justify-center")
            .props("stack")
            .style("padding-left:8px; padding-right:8px")
        )
    with self.health_check_button:
        ui.tooltip(
            translate_string(
                "Scan the loaded XML for broken references, unreferenced Tasks, Profiles and "
                "Scenes, naming problems, Task flow, variables, behaviour on the device, and "
                "secrets.\n\nYou choose which of those to report before it runs, and that "
                "choice is remembered.\n\nResults are displayed here and saved to a text file "
                "in the Output Folder.",
            ),
        ).style("white-space: pre-wrap")

    # Beside Health Check, because it is the answer to the report that button produces and
    # is useless anywhere else.  Its own button rather than something inside the report:
    # the report is displayed as one escaped blob of text in a <pre> (see
    # userintr_reports.health_check_event on why), and a tick box cannot be put into one.
    with health_row:
        self.fix_findings_button = (
            ui.button(
                translate_string("Fix Findings"),
                color="teal",
                on_click=self.event_handlers.fix_findings_event,
                icon="build",
            )
            .classes("flex-1 justify-center")
            .props("stack")
            .style("padding-left:8px; padding-right:8px")
        )
    with self.fix_findings_button:
        ui.tooltip(
            translate_string(
                "Repair the Health Check findings that have an obvious fix: set a long Task's "
                "collision handling, give a blocking action a timeout, close an 'If' that is never "
                "closed, point a broken 'Goto' at a label that exists, delete a Task nothing "
                "runs.\n\nEverything is shown before anything is done, you tick what you want, and "
                "the whole lot is one press of Undo afterwards.\n\nMost kinds of finding are not "
                "offered here -- a broken 'Perform Task' or a password written into an action is a "
                "decision only you can make.",
            ),
        ).style("white-space: pre-wrap")


def _create_history_buttons_section(self: MyGui) -> None:
    """The reports that compare the loaded configuration with another one: Compare Files, Changes Since and Restore From History."""
    # Full width, because the drawer is w-80 and this label is too long to share a row, and
    # coloured through "color" because Quasar's own bg-primary beats a Tailwind bg-* class.
    self.compare_files_button = (
        ui.button(
            translate_string("Compare Files"),
            color="teal",
            on_click=self.event_handlers.reports.compare_files_event,
            icon="difference",
        )
        .classes("w-full justify-center")
        .style("margin-top:-6px")
    )
    with self.compare_files_button:
        ui.tooltip(
            translate_string(
                "Compare another XML file against the loaded one: what was added, removed, "
                "renamed and changed.\n\nUse it to see what a TaskerNet import brought in, what "
                "an edit changed, or what is different between two backups.\n\nIf the loaded "
                "file came from 'Save to Current File', the file it was saved from is offered "
                "directly.\n\nResults are displayed here and saved to a text file in the "
                "Output Folder.",
            ),
        ).style("white-space: pre-wrap")

    # The comparison above needs two files and the user to know which two.  This one
    # needs neither: every configuration loaded is kept (see timeline.py), so the
    # older side is already on disk and picked by date.
    self.timeline_button = (
        ui.button(
            translate_string("Changes Since..."),
            color="teal",
            on_click=self.event_handlers.reports.timeline_event,
            icon="history",
        )
        .classes("w-full justify-center")
        .style("margin-top:-6px")
    )
    with self.timeline_button:
        ui.tooltip(
            translate_string(
                "What has changed in your configuration since a moment you choose: today, "
                "this week, this month, everything kept, or a specific date.\n\nNo file to "
                "pick -- every configuration you load is kept, compressed, in a "
                "MapTasker_Timeline folder in the current directory, and the one from back "
                "then is compared against what you have open now.\n\nResults are displayed "
                "here and saved to a text file in the Output Folder.",
            ),
        ).style("white-space: pre-wrap")

    # Directly under Changes Since, because it is that report's other half: the report says
    # what was deleted or changed since a configuration in the history, and this puts one
    # of those objects back.  Same width and colouring as the buttons around it, for their
    # reasons (see the Health Check button).
    self.restore_history_button = (
        ui.button(
            translate_string("Restore From History"),
            color="teal",
            on_click=self.event_handlers.restore_history_event,
            icon="restore",
        )
        .classes("w-full justify-center")
        .style("margin-top:-6px")
    )
    with self.restore_history_button:
        ui.tooltip(
            translate_string(
                "Bring back a Task, Profile or Scene that has been deleted, or put one back as it "
                "was before it was edited -- from any configuration kept in the history that "
                "'Changes Since...' reads.\n\nOne object at a time, never a merge: every restore "
                "is shown before anything happens, says what it leaves for you to do (a Profile "
                "to relink, say), and is one press of Undo afterwards.",
            ),
        ).style("white-space: pre-wrap")

    # Under Restore From History because it is that dialog's other source: an object brought in
    # one at a time from a configuration that is not the one open -- here, the TaskerNet share
    # it came from rather than a file kept in the history.
    taskernet_updates_button = (
        ui.button(
            translate_string("TaskerNet Updates"),
            color="teal",
            on_click=self.event_handlers.taskernet_updates_event,
            icon="cloud_sync",
        )
        .classes("w-full justify-center")
        .style("margin-top:-6px")
    )
    with taskernet_updates_button:
        ui.tooltip(
            translate_string(
                "Link a Project, Profile, Task or Scene to the TaskerNet share it came from, and find "
                "out when its author publishes a newer version.\n\nShows what the author changed and "
                "lets you take each change on its own, previewed first and one press of Undo "
                "afterwards.\n\nOnly the address of each linked share is sent to taskernet.com; "
                "nothing from your configuration leaves this computer.",
            ),
        ).style("white-space: pre-wrap")
    _create_import_button(self)


def _create_import_button(self: MyGui) -> None:
    """Import With Dependencies, under TaskerNet Updates: one more way of bringing an object in from another file."""
    self.import_with_dependencies_button = (
        ui.button(
            translate_string("Import With Dependencies"),
            color="teal",
            on_click=self.event_handlers.carry.import_with_dependencies_event,
            icon="move_to_inbox",
        )
        .classes("w-full justify-center")
        .style("margin-top:-6px")
    )
    with self.import_with_dependencies_button:
        ui.tooltip(
            translate_string(
                "Bring a Project, Profile, Task or Scene in from another backup together with everything it "
                "needs: the Tasks it performs, the Scenes it shows and the Tasks those run, and the global "
                "variables they use.\n\nShows what would be copied, renamed and left alone before anything "
                "happens.  A Task or Scene this file already has, and that is identical, is used rather than "
                "copied.\n\nNothing already in this file is changed, and the whole import is one press of "
                "Undo.",
            ),
        ).style("white-space: pre-wrap")


def _create_resources_button(self: MyGui) -> None:
    """Missing Resources, under the Health Check it extends: do the files, Scenes and apps the actions use still exist?"""
    resources_button = (
        ui.button(
            translate_string("Missing Resources"),
            color="teal",
            on_click=self.event_handlers.missing_resources_event,
            icon="find_in_page",
        )
        .classes("w-full justify-center")
        .style("margin-top:-6px")
    )
    with resources_button:
        ui.tooltip(
            translate_string(
                "Do the files, folders, images, sounds, Scenes and apps your Tasks and Profiles use still exist on "
                "your Android device?  Asks the device and lists the ones it does not have, with every place that "
                "uses each.\n\nThe Health Check reports the same findings from the last time you checked."
            ),
        ).style("white-space: pre-wrap")


def _create_monitor_button(self: MyGui) -> None:
    """Live Run Monitor, under What Fires When and the Task Stepper, whose predictions it checks against the phone."""
    monitor_button = (
        ui.button(
            translate_string("Live Run Monitor"),
            color="teal",
            on_click=self.event_handlers.live_monitor_event,
            icon="monitor_heart",
        )
        .classes("w-full justify-center")
        .style("margin-top:-6px")
    )
    with monitor_button:
        ui.tooltip(
            translate_string(
                "Watch which Profiles and Tasks fire on your Android device as they do, and see them light up in "
                "the Diagram.\n\nCompare what the device really has active with what What Fires When "
                "predicted for the same moment.\n\nIt samples several times a second, so a Task that runs for a "
                "moment can be missed.  Nothing on the device is changed but one small helper Task."
            ),
        ).style("white-space: pre-wrap")


def _create_trend_button(self: MyGui) -> None:
    """Trend Dashboard, last among the buttons that read the history: is the configuration getting healthier or messier?"""
    trend_button = (
        ui.button(
            translate_string("Trend Dashboard"),
            color="teal",
            on_click=self.event_handlers.trend_dashboard_event,
            icon="trending_up",
        )
        .classes("w-full justify-center")
        .style("margin-top:-6px")
    )
    with trend_button:
        ui.tooltip(
            translate_string(
                "Is your configuration getting healthier or messier?  Measures every configuration the history "
                "has kept -- Task length, nesting depth, how deep Perform Task calls go, and what the Health Check "
                "finds -- and shows each number over time, for the whole configuration and for each "
                "Project.\n\nEach configuration is measured once and the figures are kept, so only the first look "
                "is slow."
            ),
        ).style("white-space: pre-wrap")


def _create_analysis_buttons_section(self: MyGui) -> None:
    """The reports that read the configuration's behaviour: Variable Xref, Task Flow and What Fires When."""
    # Full width and coloured through "color" for the same two reasons the two buttons
    # above are: the drawer is w-80 and this label will not fit beside another, and
    # Quasar's own bg-primary beats a Tailwind bg-* class added here.
    # Variable Xref and its live twin share a row.  Each grows to half of it ("flex-grow"
    # rather than w-full, which would push the second onto a line of its own), and the row
    # carries the negative margin the lone button used to.
    with ui.row().classes("w-full no-wrap gap-1").style("margin-top:-6px"):
        self.variable_xref_button = ui.button(
            translate_string("Variable Xref"),
            color="teal",
            on_click=self.event_handlers.reports.variable_xref_event,
            icon="manage_search",
        ).classes("flex-grow justify-center")
        with self.variable_xref_button:
            ui.tooltip(
                translate_string(
                    "Trace every %variable in the loaded XML: where each one is set, where it is "
                    "read, which are read but never set, which are set but never read, and which "
                    "near-identical names (%MyVar against %Myvar) are likely typos.\n\nSearched: "
                    "Task actions and their conditions, plugin configuration, Profile contexts and "
                    "Scenes.\n\nResults are displayed here and saved to a text file in the Output "
                    "Folder.",
                ),
            ).style("white-space: pre-wrap")

        variable_xref_live_button = ui.button(
            translate_string("Xref Live"),
            color="teal",
            on_click=self.event_handlers.reports.variable_xref_live_event,
            icon="sensors",
        ).classes("flex-grow justify-center")
        with variable_xref_live_button:
            ui.tooltip(
                translate_string(
                    "The Variable Xref, plus what each global variable holds right now on the Android "
                    "device, read through Tasker's HTTP API.\n\nIt also checks the 'read but never set' "
                    "and 'set but never read' findings against the device: a variable the device does "
                    "not have is a confirmed problem, and one it does have was set or read by something "
                    "outside this file.\n\nNothing on the device is changed.  Values appear in the "
                    "saved report.",
                ),
            ).style("white-space: pre-wrap")

    # Full width and coloured through "color" for the same two reasons the three buttons
    # above are: the drawer is w-80, this label will not fit beside another, and Quasar's
    # own bg-primary beats a Tailwind bg-* class added here.
    self.task_flow_button = (
        ui.button(
            translate_string("Task Flow"),
            color="teal",
            on_click=self.event_handlers.reports.task_flow_event,
            icon="account_tree",
        )
        .classes("w-full justify-center")
        .style("margin-top:-6px")
    )
    with self.task_flow_button:
        ui.tooltip(
            translate_string(
                "Read every Task's control flow -- its If/Else/End If, For/End For, Goto and "
                "Stop -- and report what does not hold together: a block that is never closed, "
                "a Goto aimed at a label no action carries, and actions nothing can ever "
                "reach.\n\nWith a single Task chosen in the 'Specific Name' tab, that Task is "
                "also drawn as a flowchart in its own window, with an arrow from every Goto to "
                "the action it lands on.\n\nResults are displayed here and saved to a text file "
                "in the Output Folder.",
            ),
        ).style("white-space: pre-wrap")

    _create_outbound_button(self)
    _create_simulation_buttons(self)


def _create_outbound_button(self: MyGui) -> None:
    """Outbound Inventory, last of the reports that read the whole configuration: what does it send, call or run?"""
    outbound_button = (
        ui.button(
            translate_string("Outbound Inventory"),
            color="teal",
            on_click=self.event_handlers.reports.outbound_event,
            icon="travel_explore",
        )
        .classes("w-full justify-center")
        .style("margin-top:-6px")
    )
    with outbound_button:
        ui.tooltip(
            translate_string(
                "List everything the configuration reaches outside the phone with, Project by Project: every "
                "URL and host it contacts, and every SMS, call, shell command, root command and Intent it "
                "sends.\n\nThe actions worth a look come first -- a command run as root, a request over plain "
                "http, an address built from a variable, an action carrying a key or password.  Keys found in "
                "an address are replaced in the report.\n\nResults are displayed here and saved to a text file "
                "in the Output Folder.",
            ),
        ).style("white-space: pre-wrap")


def _create_simulation_buttons(self: MyGui) -> None:
    """The two buttons that ask what the configuration WOULD do: What Fires When? and the Task Stepper."""
    # Under the other reports that read the configuration's behaviour, full width and
    # coloured through "color" for the reasons the buttons above give.
    fire_simulator_button = (
        ui.button(
            translate_string("What Fires When?"),
            color="teal",
            on_click=self.event_handlers.fire_simulator_event,
            icon="schedule",
        )
        .classes("w-full justify-center")
        .style("margin-top:-6px")
    )
    with fire_simulator_button:
        ui.tooltip(
            translate_string(
                "Pick a moment -- a date and time, the Wi-Fi network the device is on, the app in "
                "front and the battery level -- and see which Profiles it makes active, the order "
                "their Tasks start in, and where they collide.\n\nAnything the inputs do not "
                "describe, such as an Event or a location, is treated as unknown, so a Profile that "
                "depends on it is shown as possible and says what it is waiting on.",
            ),
        ).style("white-space: pre-wrap")

    # Beside What Fires When because it is that report's next question: once a Profile has started a
    # Task, what does the Task do?
    task_stepper_button = (
        ui.button(
            translate_string("Task Stepper"),
            color="teal",
            on_click=self.event_handlers.task_stepper_event,
            icon="skip_next",
        )
        .classes("w-full justify-center")
        .style("margin-top:-6px")
    )
    with task_stepper_button:
        ui.tooltip(
            translate_string(
                "Dry-run one Task: pick it, say what its variables hold when it starts, and see which If, "
                "Else If, For and Goto branches it takes and what every variable holds after each "
                "action.\n\nActions that talk to the outside world are listed as 'not simulated', and a "
                "variable one of them may have set is treated as unknown rather than guessed.  Nothing is "
                "run on your phone and nothing in the configuration changes.",
            ),
        ).style("white-space: pre-wrap")
    _create_task_tests_button(self)


def _create_task_tests_button(self: MyGui) -> None:
    """Task Tests, under the Task Stepper whose runs it keeps -- and the timer that runs them all after an edit."""
    self.task_tests_button = (
        ui.button(
            translate_string("Task Tests"),
            color="teal",
            on_click=self.event_handlers.tasktests.task_tests_event,
            icon="fact_check",
        )
        .classes("w-full justify-center")
        .style("margin-top:-6px")
    )
    with self.task_tests_button:
        ui.tooltip(
            translate_string(
                "Run the tests you have saved from the Task Stepper: a Task, the values it started with and what "
                "it did -- how it ended, the variables it set, and what it showed and sent.\n\nThey are run again "
                "after every edit, Fix Findings pass, refactor or import, and you are told if a Task no longer does "
                "what it did.",
            ),
        ).style("white-space: pre-wrap")
    # Looked at every moment or two: what is cheap when nothing has been edited, and the one place that cannot
    # miss an edit, since every one is a checkpoint in the history Undo reads.
    ui.timer(TASK_TESTS_POLL_SECONDS, self.event_handlers.tasktests.edit_tick)


def _create_main_body(self: MyGui) -> None:
    """The middle of the window: the four tabs, the view underneath them, and the colour picker."""
    with ui.column().classes("p-6 w-full max-w-full mx-auto") as self.gui_main_column:
        with ui.row().classes("gap-4 mb-6") as self.gui_view_toolbar:
            self.current_file = ui.label(translate_string("No file loaded")).classes("text-gray-500 italic")

        # A tab's *name* -- ui.tab's first argument -- is the value ui.tabs carries, what
        # tab_to_use holds, and what TAB_NAMES and the settings file record, so it has to
        # stay English.  Only the label the user reads is translated.  Handing ui.tab the
        # translated string on its own (which makes it both name and label) meant the tab
        # names changed with the language: after a switch, the set_value(self.tab_to_use)
        # at the end of initialize_screen matched no tab at all and left every tab deselected,
        # and switching back to English made a stale tab_to_use match again and jump there.
        with ui.tabs().classes("w-full") as self.gui_main_tabs_container:
            self.tab_specific_name = ui.tab(
                "Specific Name",
                label=translate_string("Specific Name"),
                icon="filter_list",
            )
            self.tab_colors = ui.tab("Colors", label=translate_string("Colors"), icon="palette")
            self.tab_analyze = ui.tab("Analyze", label=translate_string("Analyze"), icon="analytics")
            self.tab_debug = ui.tab("Assistance", label=translate_string("Assistance"), icon="support_agent")

        with ui.tab_panels(self.gui_main_tabs_container, value=self.tab_specific_name).classes(
            "w-full border rounded shadow-inner p-4 mt-1 gap-y-0 m-0 p-0 leading-none",
        ) as self.gui_tab_panels:
            # --- TAB 1: SPECIFIC NAME (MINIMIZED SPACING) ---
            with ui.tab_panel(self.tab_specific_name).classes("p-2 m-0") as self.gui_tasker_object_panel:
                create_specific_name_tab(self)

            # --- TAB 2: COLORS (MINIMIZED SPACING) ---
            with ui.tab_panel(self.tab_colors).classes("p-2 m-0") as self.gui_color_panel:
                create_colors_tab(self)

            # --- TAB 3: ANALYZE (MINIMIZED SPACING) ---
            with ui.tab_panel(self.tab_analyze).classes("p-2 m-0") as self.gui_ai_panel:
                ui.label(translate_string("AI Analysis")).classes("text-base mb-2")
                create_analyze_tab_content(self, ui.tab_panel(self.tab_analyze))

            # --- TAB 4: ASSISTANCE: help buttons plus the debug aids (MINIMIZED SPACING) ---
            with (
                ui.tab_panel(self.tab_debug).classes("p-2 m-0") as self.gui_debug_panel,
                ui.column().classes("gap-1"),
            ):
                create_help_options_section(self)
                self.debug_checkbox = (
                    ui.checkbox(translate_string("Debug Mode")).bind_value(self, "debug").classes("text-xs")
                )
                self.runtime_checkbox = (
                    ui.checkbox(translate_string("Display Runtime Settings"))
                    .bind_value(self, "runtime")
                    .classes("text-xs")
                )
                with ui.row().classes("gap-2 mt-2"):
                    ui.button(translate_string("Display Log"), on_click=display_notification_log)
                    ui.button(translate_string("Clear Log"), on_click=clear_notification_log)

        self.content_container = ui.column().classes("w-full max-w-full min-w-0 p-0 m-0 mt-6")

        with ui.dialog() as self.picker_dialog, ui.card().classes("p-4 items-center"):
            self.picker_title_label = ui.label("").classes("font-bold text-sm mb-2")
            self.picker_engine = ui.color_picker()
            ui.button(translate_string("Cancel"), on_click=self.picker_dialog.close).classes(
                "mt-4 w-full bg-gray-500 text-white",
            )
