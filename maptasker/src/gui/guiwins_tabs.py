"""guiwins_tabs: the tabs of the main body, and the option sections inside them.

The Analyze tab's display, indentation, language, view-limit, notification, output-directory and font sections,
the Colors tab, and the object action rows of the Specific Name tab."""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from nicegui import ui
from nicegui.core import stop_and_exit

from maptasker.src.core import mapjump
from maptasker.src.core.config import EDIT_SCENE
from maptasker.src.core.maputil2 import suppress_logged, translate_string
from maptasker.src.core.outdir import default_output_directory
from maptasker.src.core.sysconst import NOTIFY_TIMEOUT_DEFAULT, VIEW_LIMIT_DEFAULT, logger
from maptasker.src.gui.guiutil2 import get_font_choices, sort_languages_with_priority
from maptasker.src.gui.guiutils import (
    display_model_pulldown,
    refresh_object_action_buttons,
    update_analysis_button_color,
)
from maptasker.src.gui.guiwins import (
    NOTIFY_TIMEOUT_CHOICES,
    create_refactor_button,
    create_undo_section,
    view_limit_options,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from maptasker.src.gui.userintr import MyGui


def create_specific_name_tab(self: MyGui) -> None:
    """The Specific Name tab: pick one Project, Profile, Task or Scene, and edit or add one."""
    ui.label(
        translate_string("Target specific Projects, Profiles, Tasks or Scenes. (Select only one)"),
    ).classes(
        "text-base mb-1",
    )
    self.currently_selected_label = ui.label("").classes("text-xs mb-2 text-gray-500 italic")

    _create_specific_name_pulldowns(self)

    self.specific_name_msg_label = ui.label("").classes("text-xs ml-2 mt-1 text-left")
    self.list_unnamed_items_checkbox = (
        ui.checkbox(
            translate_string("List Unnamed Items"),
            on_change=self.event_handlers.list_unnamed_items_event,
        )
        .classes("mt-1 text-xs")
        .tooltip(
            translate_string(
                "Select this to include Profiles and Tasks that do not have a name in the list.",
            ),
        )
    )
    _create_object_action_buttons(self)


def _create_specific_name_pulldowns(self: MyGui) -> None:
    """The Project, Profile, Task and Scene pulldowns, side by side."""
    # Wrap the pulldowns in a tight row so Project/Profile/Task/Scene sit side by side
    none_translatesd = translate_string("None")
    with ui.row().classes("gap-2 w-full m-0 p-0 items-start"):
        self.specific_project_optionmenu = (
            ui.select(
                [none_translatesd],
                on_change=lambda e: self.event_handlers.single_project_name_event(e.value) if e.value else None,
                label=translate_string("Project"),
                with_input=True,
            )
            .classes("w-48 mb-0")
            .props("dense")
            .tooltip(translate_string("Select a specific Project to target for display or editing."))
        )

        self.specific_profile_optionmenu = (
            ui.select(
                [none_translatesd],
                on_change=lambda e: self.event_handlers.single_profile_name_event(e.value) if e.value else None,
                label=translate_string("Profile"),
                with_input=True,
            )
            .classes("w-48 mb-0")
            .props("dense")
            .tooltip(translate_string("Select a specific Profile to target for display or editing."))
        )

        self.specific_task_optionmenu = (
            ui.select(
                [none_translatesd],
                on_change=lambda e: self.event_handlers.single_task_name_event(e.value) if e.value else None,
                label=translate_string("Task"),
                with_input=True,
            )
            .classes("w-48 mb-0")
            .props("dense")
            .tooltip(translate_string("Select a specific Task to target for display or editing."))
        )

        self.specific_scene_optionmenu = (
            ui.select(
                [none_translatesd],
                on_change=lambda e: self.event_handlers.single_scene_name_event(e.value) if e.value else None,
                label=translate_string("Scene"),
                with_input=True,
            )
            .classes("w-48 mb-0")
            .props("dense")
            .tooltip(translate_string("Select a specific Scene to target for display or editing."))
        )


def _object_action_button(label: str, on_click: Callable[..., object]) -> ui.button:
    """One of the Edit/Add/Run buttons for the selected object.

    Each flexes within its row, capped at 12rem -- the cap is what keeps a row showing one
    button the same width as each half of a row showing two, instead of the lone button
    stretching to the whole column.

    Args:
        label (str): the button's text, already translated.  The caller's own translate_string
            call is what the translation catalogs are built from, so it stays at the call.
        on_click: the event handler the button runs.

    Returns:
        ui.button: the button, for the caller to keep or add to.
    """
    return ui.button(label, on_click=on_click).classes("flex-1 min-w-0 mt-2 bg-blue-500").style("max-width:12rem")


def _create_object_action_rows(self: MyGui) -> None:
    """The Edit/Add button rows (and Run On Android), one row per kind of object.

    All are built here, but only the ones the current pulldown selection can actually drive are
    ever on screen: guiutils.refresh_object_action_buttons hides the rest (and any row left
    with nothing in it) every time the selection changes.  Each row is held on self so it can
    be hidden along with its pair.

    flex-1/min-w-0: takes whatever the Editing group leaves rather than a fixed width, so
    nothing overflows the panel at any window size.
    """
    handlers = self.event_handlers
    with ui.column().classes("flex-1 min-w-0 gap-0 m-0 p-0"):
        with ui.row().classes("w-full gap-2 m-0 p-0") as self.project_buttons_row:
            self.edit_project_button = _object_action_button(
                translate_string("Edit Project"), handlers.open_edit_project_dialog_event
            )
            self.add_project_button = _object_action_button(
                translate_string("Add Project"), handlers.open_add_project_dialog_event
            )
        with ui.row().classes("w-full gap-2 m-0 p-0") as self.profile_buttons_row:
            self.edit_profile_button = _object_action_button(
                translate_string("Edit Profile"), handlers.open_edit_profile_dialog_event
            )
            self.add_profile_button = _object_action_button(
                translate_string("Add Profile"), handlers.open_add_profile_dialog_event
            )
        with ui.row().classes("w-full gap-2 m-0 p-0") as self.task_buttons_row:
            self.edit_task_button = _object_action_button(
                translate_string("Edit Task"), handlers.open_edit_task_dialog_event
            )
            self.add_task_button = _object_action_button(
                translate_string("Add Task"), handlers.open_add_task_dialog_event
            )
            self.run_task_button = _object_action_button(
                translate_string("Run On Android"),
                handlers.open_run_task_on_android_dialog_event,
            ).tooltip(
                translate_string(
                    "Run the selected Task on your Android device and see what it returned.",
                ),
            )
        # The Scene pair is the only one of the four behind a switch -- Scene
        # editing is still filling in (see sceneedit.py).  Not built at all when
        # config.EDIT_SCENE is False, rather than built-and-hidden: nothing else
        # reads these two attributes, so leaving them unset is enough, and it
        # keeps a disabled feature from occupying a row of the tab.
        if EDIT_SCENE:
            with ui.row().classes("w-full gap-2 m-0 p-0") as self.scene_buttons_row:
                self.edit_scene_button = _object_action_button(
                    translate_string("Edit Scene"), handlers.open_edit_scene_dialog_event
                )
                self.add_scene_button = _object_action_button(
                    translate_string("Add Scene"), handlers.open_add_scene_dialog_event
                )


def _create_object_action_buttons(self: MyGui) -> None:
    """The Edit/Add buttons for whatever is selected, and the Editing group pinned beside them."""
    # The Edit/Add pairs on the left, the Editing (Undo/Redo/History) group
    # pinned to the right: "justify-between" with nothing between them puts
    # each against its own edge however wide the window is.  Editing sits here
    # rather than in the drawer because it belongs with the buttons whose work
    # it takes back -- an Undo is only ever wanted after one of these was used.
    #
    # wrap=False is what keeps it pinned rather than merely placed: this panel
    # sits between two drawers and is only ~650px wide, so a wrapping row drops
    # the Editing group underneath the Edit/Add pairs as soon as both are shown
    # -- which is most of the time.  The Edit/Add buttons give up their fixed
    # width to pay for it (see their flex-1 in _object_action_button).
    with ui.row(wrap=False).classes("w-full items-start justify-between gap-4 m-0 p-0"):
        _create_object_action_rows(self)

        # "shrink-0" so the Editing group keeps its width and stays hard against
        # the right edge instead of being squeezed as the Edit/Add rows come and
        # go with the selection.
        with ui.column().classes("w-56 shrink-0 gap-1 m-0 p-0 mt-2 items-center"):
            ui.label(translate_string("Editing")).classes(
                "text-xs font-bold uppercase text-gray-400 self-center",
            )
            create_refactor_button(self)
            create_undo_section(self)

    # Set the buttons to match whatever is selected right now, rather than
    # leaving them as built (all eight visible) until the first selection
    # change.  On start-up that means just "Add Project" -- the one action
    # needing no selection, and nothing is selected yet at this point (the
    # restore runs after initialize_screen).  On a rebuild, though -- a
    # language change re-runs initialize_screen (see reload_gui) -- there
    # very much can be a live selection to match.
    refresh_object_action_buttons(self)


def create_colors_tab(self: MyGui) -> None:
    """The Colors tab: pick a category of the output and give it a colour."""
    ui.label(translate_string("Theme Configuration")).classes("text-base mb-1")
    ui.button(
        translate_string("Reset to Default Colors"),
        on_click=self.event_handlers.color_reset_event,
    ).classes("bg-blue-500 text-xs py-1")

    self.color_change = ui.label(translate_string("Select a category to modify its color.")).classes(
        "text-xs mt-2",
    )

    with ui.column().classes("gap-1 w-full mt-1"):
        self.color_objects_options = (
            ui.select(
                options=[
                    "Projects",
                    "Profiles",
                    "Disabled Profiles",
                    "Launcher Tasks",
                    "Profile Conditions",
                    "Tasks",
                    "Unnamed Tasks",
                    "(Task) Actions",
                    "Action Conditions",
                    "Action Labels",
                    "Action Names",
                    "Scenes",
                    "Background",
                    "TaskerNet Information",
                    "Tasker Preferences",
                    "Highlight",
                    "Heading",
                ],
                value="Projects",
                label=translate_string("Select Category to Colorize"),
            )
            .classes("w-64 mb-0")
            .props("dense")
        )

        self.color_picker_input = (
            ui.color_input(
                label=translate_string("Choose Hex Color"),
                value="#3f99ff",
                on_change=lambda e: self.event_handlers.handle_color_pick_event(e.value or ""),
            )
            .classes("w-64 mb-0")
            .props("dense")
        )


async def get_rid_of_windows_and_exit(self: MyGui, _delete_all: bool = True) -> None:
    """Shuts down the NiceGUI server and exits."""
    if getattr(self, "close_tabs_on_exit", False):
        # Close every Map/Diagram popout this session opened -- the ones this window opened
        # and the ones those opened in turn (see mapjump.close_popouts_js) -- and then this
        # window itself. Browsers only allow script-driven window.close() on tabs/windows the
        # script itself opened, so this window may refuse to close if it wasn't launched via
        # window.open() -- that's an unavoidable browser security restriction, not a bug.
        # Must be awaited: run_javascript() only sends its payload once the event loop gets a
        # chance to run the background task it schedules -- and the shutdown below tears down
        # that same event loop. Without awaiting, shutdown can win the race and the browser never
        # receives the command, so the tabs are left open. window.close()-ing this tab itself may
        # tear down the connection before a response comes back, hence the timeout/suppress.
        with suppress_logged("Closing the pop-out windows"):
            await ui.run_javascript(mapjump.close_popouts_js(close_this_window=True), timeout=2.0)
    ui.notify(translate_string("Shutting down MapTasker..."), type="warning")
    logger.info("Exit button pressed.  Shutting down the GUI server.")

    # Not app.shutdown(): that only asks uvicorn to stop, and uvicorn first waits for every open
    # connection to drain.  On Windows a browser connection that has gone away without closing
    # (a "ghost" connection) never drains, so the server never stops, ui.run() never returns, and
    # the command window is left running with MapTasker still in it (NiceGUI #5443).
    # stop_and_exit() runs the shutdown handlers (which save the settings) and then ends the
    # process outright.  It blocks on the event loop's own thread, so it must be called from
    # another thread -- as NiceGUI itself does -- and after a moment for the notification above
    # to reach the browser.
    def _stop_after_flush() -> None:
        time.sleep(0.5)
        stop_and_exit()

    threading.Thread(target=_stop_after_flush, daemon=True).start()


def create_analyze_tab_content(self: MyGui, tab: ui.tab_panel) -> None:
    """Populates the 'Analyze' (AI) tab using NiceGUI and colors the analysis button contextually."""
    # Use the 'with' context manager to place elements inside the passed tab panel
    with tab:
        # 1. Action Buttons Row
        with ui.row().classes("items-center gap-4 mb-4"):
            self.show_apikeys_button = ui.button(
                translate_string("Show/Edit API Key(s)"),
                on_click=self.event_handlers.ai_apikey_event,
            )
            self.change_prompt_button = ui.button(
                translate_string("Change Prompt"),
                on_click=self.event_handlers.ai_prompt_event,
            )

            self.analysis_button = ui.button(
                translate_string("Run Analysis"),
                on_click=self.event_handlers.ai_analyze_event,
            )
            update_analysis_button_color(self)
            self.analysis_query_button = ui.button(
                "?",
                on_click=lambda: self.event_handlers.query_event("ai"),
            ).classes("bg-blue-600 text-white min-w-[40px]")

        # 2. Model Selection Row
        with ui.row().classes("items-center gap-4"):
            self.model_to_use_label = ui.label(translate_string("Model to Use:")).classes("font-bold")

            # Display the default model list
            display_model_pulldown(self)

            # Extra model list checkbox with chained tooltip
            self.aimodel_extend_checkbox = (
                ui.checkbox(
                    translate_string("Extended"), on_change=lambda: self.event_handlers.extended_models_changed(self)
                )
                .tooltip(
                    translate_string(
                        "Display an extended list of ALL available models.\n\n"
                        "Note: If the API key is not set for OpenAI or Gemini,\n"
                        "      then the default model list for the respective\n"
                        "      AI provider will be displayed.\n\n"
                        "Note: Not all models have been validated and\n"
                        "      one or more may return an error on analysis.\n\n"
                        "Note: Enabling this option for the first time will\n"
                        "      force the installation of the following modules\n"
                        "      and all of their dependencies:\n"
                        "      google-genai, anthropic, openai, ollama",
                    ),
                )
                .style("white-space: pre-wrap")
            )  # Ensures the newline characters format correctly in HTML


def create_name_display_options_section(self: MyGui) -> None:
    """
    Optimized creation of name display options using NiceGUI.
    Renders a section header and a condensed 2x2 grid of styling checkboxes.
    """
    handlers = self.event_handlers

    # 1. Create the Section Label with an inline native tooltip
    self.display_names_label = (
        ui.label(translate_string("Project/Profile/Task/Scene Names:"))
        .classes("text-sm font-semibold mt-4 mb-1 py-0 my-0 gap-y-0 leading-none")
        .tooltip(translate_string("Add highlighting to Project, Profile and Task names in the output."))
    )

    # 2. Define Checkbox Configurations
    checkbox_configs = [
        (
            "bold_checkbox",
            handlers.names_bold_event,
            translate_string("Bold"),
            "Bold and Italicize are mutually exclusive in the Map view.",
        ),
        (
            "italicize_checkbox",
            handlers.names_italicize_event,
            translate_string("Italicize"),
            "Italicize and Bold are mutually exclusive in the Map view.",
        ),
        ("highlight_checkbox", handlers.names_highlight_event, translate_string("Highlight"), None),
        ("underline_checkbox", handlers.names_underline_event, translate_string("Underline"), None),
    ]

    # 3. Batch Creation inside a highly condensed 2-Column Grid Layout
    # Changed gap-y-1 to gap-y-0 to completely eliminate grid vertical row spacing
    with ui.grid(columns=2).classes("w-full gap-x-4 py-0 my-0 gap-y-0 pl-2"):
        for attr, event, label, tip in checkbox_configs:
            # Instantiate the checkbox and strip vertical padding/margins via py-0 my-0
            checkbox = ui.checkbox(label, on_change=event).classes("py-0 my-0")

            # Save the reference dynamically to the 'self' instance
            setattr(self, attr, checkbox)

            # Chain the tooltip natively if one is defined
            if tip:
                checkbox.tooltip(tip)


def create_task_action_limit_section(self: MyGui) -> None:
    """Creates the task 'actions' limit slider in the NiceGUI sidebar."""
    text_to_insert = "Task 'actions' limit"
    text = self.state._(text_to_insert) if hasattr(self.state, "_") else text_to_insert

    # 1. Label tracking the live dynamic value
    self.task_action_label = ui.label(f"{text}: {self.task_action_warning_limit}").classes(
        "text-sm font-semibold mt-4 mb-1 py-0 my-0 gap-y-0",
    )

    # 2. NiceGUI Slider
    # NiceGUI handles styling with Tailwind (e.g., track color tints via accent)
    self.task_action_limit = ui.slider(
        min=10,
        max=100,
        step=1,
        value=100,
        on_change=self.event_handlers.tasklimit_event,
    ).classes(
        "w-full px-2 accent-green-600 py-0 my-0 gap-y-0",
    )
    with self.task_action_limit:
        ui.tooltip(
            translate_string(
                "Select how many actions in a Task before issuing a warning.\n"
                "The warning appears near the bottom of the configuration output,\n"
                "and is intended to help identify Tasks that are too complex\n"
                "and which should potentially be broken up into multiple Tasks.\n"
                "A setting of '100' means there is no limit.",
            ),
        ).style(
            "white-space: pre-wrap",
        )  # Ensures the tooltip text respects newlines for better readability


def create_indentation_section(self: MyGui) -> None:
    """Creates the If/Then/Else indentation dropdown options in the NiceGUI sidebar."""
    self.indent_label = ui.label(translate_string("If/Then/Else Indentation Amount:")).classes(
        "text-sm font-semibold mt-4 mb-1 leading-none py-0 my-0 gap-y-0",
    )

    self.indent_option = ui.select(
        options=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
        value="4",  # Default initial value matching your original comments
        on_change=self.event_handlers.indent_selected_event,
    ).classes("w-full leading-none py-0 my-0 gap-y-0")
    with self.indent_option:
        ui.tooltip(
            translate_string(
                "Set the indentation amount for If/Then/Else blocks.\n\n"
                "The default is '4'.\n\n"
                "This affects how the output is formatted in the Map and Diagram views.",
            ),
        ).style(
            "white-space: pre-wrap",
        )  # Ensures the tooltip text respects newlines for better readability


def create_language_selection_section(self: MyGui) -> None:
    """Creates the language selection dropdown in the NiceGUI sidebar."""
    self.language_label = ui.label(f"{translate_string('Language:')}").classes(
        "text-sm font-semibold mt-4 mb-1 leading-none py-0 my-0 gap-y-0",
    )

    # This returns a list of English language keys, e.g., ["English", "German", "French"]
    languages = sort_languages_with_priority(list(self.state.languages))

    # ui.select's "value" (what on_change reports, and what must be assigned to select
    # a specific entry) is always the dict KEY, never the displayed label -- so map each
    # English key to its translated display label (e.g. "German" -> "Deutsch") here. That
    # keeps the value side in English (matching self.language / PrimeItems.languages) while
    # still showing the user their language's own name instead of always English.
    language_options = {language: translate_string(language) for language in languages}

    self.language_optionmenu = ui.select(
        options=language_options,
        value=self.language,
        on_change=self.event_handlers.language_selected_event,
    ).classes("w-full")


def create_view_limit_section(self: MyGui) -> None:
    """Creates the view limit dropdown in the sidebar drawer."""
    self.viewlimit_label = ui.label(translate_string("View Limit:")).classes(
        "text-sm font-semibold mt-4 mb-1 leading-none py-0 my-0 gap-y-0",
    )

    with ui.row().classes("w-full items-center gap-2"):
        temp_view_limit = getattr(self, "view_limit", str(VIEW_LIMIT_DEFAULT))
        # The pulldown's wording for no limit; self.view_limit itself stays the number it is.
        current_choice = (
            "Unlimited" if temp_view_limit == 9999999 else str(getattr(self, "view_limit", VIEW_LIMIT_DEFAULT))
        )
        self.viewlimit_optionmenu = ui.select(
            options=view_limit_options(current_choice),
            value=current_choice,
            on_change=self.event_handlers.viewlimit_event,
        ).classes("flex-grow")
        with self.viewlimit_optionmenu:
            ui.tooltip(
                translate_string(
                    "Select the maximum number of items to display in the view to be allowed.\n\n"
                    "Anything over this amount will stop the generation of the view as a means to throttle the program.\n\n"
                    "Note: This is only for the 'Map' and 'Diagram' views, not the tree view.",
                ),
            ).style(
                "white-space: pre-wrap",
            )  # Ensures the tooltip text respects newlines for better readability
        self.view_limit = int(temp_view_limit) if temp_view_limit != "Unlimited" else 9999999

        # Query help button
        self.viewlimit_query_button = ui.button(
            "?",
            on_click=lambda: self.event_handlers.query_event("viewlimit"),
        ).classes("bg-blue-600 text-white min-w-[40px]")


def create_notification_duration_section(self: MyGui) -> None:
    """The 'Notification Duration' pulldown in the sidebar drawer.

    Offered as durations rather than milliseconds: the number is an implementation detail of
    Quasar's API, and nobody choosing how long a message should linger is thinking in
    thousandths of a second.  The stored value is still milliseconds, because that is what
    ui.notify wants and what the settings file has always held for numeric settings.
    """
    self.notify_timeout_label = ui.label(translate_string("Notification Duration:")).classes(
        "text-sm font-semibold mt-4 mb-1 leading-none py-0 my-0 gap-y-0",
    )
    with ui.row().classes("w-full items-center gap-2"):
        current = getattr(self, "notify_timeout", NOTIFY_TIMEOUT_DEFAULT)
        labels = {milliseconds: label for label, milliseconds in NOTIFY_TIMEOUT_CHOICES}
        # Fall back through the default to the first choice: an unlistable value is a settings
        # bug, and the whole GUI failing to build is too high a price for one wrong pulldown.
        fallback = labels.get(NOTIFY_TIMEOUT_DEFAULT, NOTIFY_TIMEOUT_CHOICES[0][0])
        self.notify_timeout_optionmenu = ui.select(
            options=[translate_string(label) for label, _ms in NOTIFY_TIMEOUT_CHOICES],
            value=translate_string(labels.get(current, fallback)),
            on_change=self.event_handlers.notify_timeout_event,
        ).classes("flex-grow")
        with self.notify_timeout_optionmenu:
            ui.tooltip(
                translate_string(
                    "How long a pop-up message stays on screen before it disappears.\n\n"
                    "'Until dismissed' keeps every message up until you close it, which is useful "
                    "when a message scrolls past before you can read it.\n\n"
                    "A few messages set their own longer duration because they list things you "
                    "have to read -- the Tasks affected by deleting or renaming a Scene element, "
                    "for instance. Those keep their own timing whatever is chosen here.",
                ),
            ).style("white-space: pre-wrap")


def create_output_directory_section(self: MyGui) -> None:
    """The 'Output Folder' box in the sidebar drawer: where reports, exports and views go.

    Taken on Enter or on leaving the box rather than on every keystroke -- each half-typed
    path would otherwise be made as a folder on the way to the one the user meant.  Empty
    means the default, which the box shows as its placeholder so the user can see where
    that is without looking it up.
    """
    handlers = self.event_handlers
    ui.label(translate_string("Output Folder:")).classes(
        "text-sm font-semibold mt-4 mb-1 leading-none py-0 my-0 gap-y-0",
    )
    with ui.row().classes("w-full items-center gap-2 no-wrap"):
        self.output_directory_input = (
            ui.input(
                value=getattr(self, "output_directory", ""),
                placeholder=str(default_output_directory()),
            )
            .props("dense clearable")
            .classes("flex-grow")
            .on("keydown.enter", handlers.output_directory_event)
            .on("blur", handlers.output_directory_event)
        )
        with self.output_directory_input:
            ui.tooltip(
                translate_string(
                    "The folder MapTasker writes its reports (Health Check, Fix, Find, Compare and the "
                    "rest), view exports, the Map and Diagram files, and standalone exports to.\n\n"
                    "Leave it empty to use a MapTasker folder in your Documents folder.  The folder is "
                    "created if it does not exist.",
                ),
            ).style("white-space: pre-wrap")
        ui.button(
            translate_string("Default"),
            on_click=lambda: handlers.output_directory_event(""),
        ).props("dense").classes("bg-blue-600 text-white")


def create_settings_buttons_section(self: MyGui) -> None:
    """Creates settings buttons in their respective responsive layout containers."""
    handlers = self.event_handlers

    # 1. Sidebar Buttons (Master: self.gui_left_drawer)
    with self.gui_left_drawer:
        self.reset_button = ui.button(
            translate_string("Reset Options"),
            on_click=handlers.reset_settings_event,
        ).classes(
            "w-full bg-blue-600 text-white mt-2",
        )
        # Nest the tooltip explicitly inside the button context
        with self.reset_button:
            ui.tooltip(
                translate_string(
                    "Reset all of the options to their default values, including colors, font used, and other settings.\n\n"
                    "The currently loaded XML will be cleared out.",
                ),
            ).style(
                "white-space: pre-wrap;",
            )  # Tells the web browser to render \n newlines!

    # 2. Main Window Buttons Layout Area
    # Save and Restore side by side, on a row of their own.  Short labels because the drawer is
    # too narrow for "Save Settings" and "Restore Settings" in one row; the "Application
    # Settings" heading above them says what they act on, and the tooltips say it again.
    with ui.row().classes("w-full gap-2 mt-0 justify-center no-wrap"):
        self.save_settings_button = ui.button(
            translate_string("Save"),
            on_click=handlers.save_settings_event,
        ).classes(
            "bg-indigo-600 text-white justify-center",
        )
        with self.save_settings_button:
            ui.tooltip(translate_string("Save these settings for later use."))

        self.restore_settings_button = ui.button(
            translate_string("Restore"),
            on_click=handlers.restore_settings_event,
        ).classes(
            "bg-indigo-600 text-white justify-center",
        )
        with self.restore_settings_button:
            ui.tooltip(translate_string("Restore the settings from a previously saved session."))

    with ui.row().classes("w-full gap-2 mt-0 justify-center"):
        self.report_issue_button = (
            ui.button(
                translate_string("Report Issue"),
                on_click=handlers.report_issue_event,
            )
            .classes(
                "bg-gray-600 text-white justify-center",
            )
            .style("margin-top:-6px")
        )
        with self.report_issue_button:
            ui.tooltip(
                translate_string(
                    "Report any issues and/or suggestions to the developer.\n\n"
                    "This will open a browser window to the GitHub Issues page, and you will need a GitHub account to submit an issue.",
                ),
            ).style("white-space: pre-wrap;")


def create_font_section(self: MyGui) -> None:
    """Creates the font selection dropdown inside the content container."""
    self.font_label = ui.label(translate_string("Font To Use In Output:")).classes(
        "text-sm font-semibold mt-4 mb-1 py-0 my-0 gap-y-0 m-0 p-0 leading-none",
    )

    # {font name: label shown}, so the label can mark a font as monospaced while the
    # value carried by the pulldown stays the plain name the output has to reference.
    if not self.state.mono_fonts:
        font_items = get_font_choices()
        self.state.mono_fonts = font_items
    else:
        font_items = self.state.mono_fonts

    font_names = list(font_items)
    default_font = [name for name in font_names if "Courier" in name]
    self.default_font = default_font[0] if default_font else font_names[0]

    # Show the font actually in effect. It comes from the restored settings and, now that
    # proportional fonts can be offered too, may be anything -- but a font that has since
    # been uninstalled is no longer among the choices, and selecting one that isn't there
    # leaves the pulldown blank.
    current_font = self.font if self.font in font_items else self.default_font

    # ui.select manages choices natively
    self.font_optionmenu = ui.select(
        options=font_items,
        value=current_font,
        on_change=self.event_handlers.font_event,
    ).classes("w-64")
    with self.font_optionmenu:
        ui.tooltip(
            translate_string(
                "This is a list of all of the fonts available on your system, monospaced ones first "
                "and marked as such.\n\n"
                "The font selected will be used in all output.\n\n"
                "'Courier' or 'Courier New' is highly recommended for Diagrams to ensure proper connector "
                "alignment. A font that is not monospaced will not hold the Diagram's connectors or the "
                "output's indentation in line.",
            ),
        ).style(
            "white-space: pre-wrap;",
        )  # Ensures newlines render properly in the tooltip


def create_file_and_message_buttons_section(self: MyGui) -> None:
    """Creates file actions, message configuration button rows, and dynamic android panel containers."""
    with self.gui_right_drawer:
        # This button and its "?" are built once, here, and stay put for the life of the window:
        # opening the Android panel (get_xml_from_android_event in userintr_android.py) adds a panel
        # below them rather than replacing them, and clear_android_buttons() (guiutils.py) only
        # tears that panel down again.
        with ui.row().classes("w-full flex-nowrap items-center justify-center gap-2 mt-0") as self.android_button_row:
            self.get_backup_button = (
                ui.button(
                    translate_string("Get XML from Android Device"),
                    on_click=self.event_handlers.get_xml_from_android_event,
                )
                .style("background-color: #246FB6; border-color: #6563ff; border-width: 2px; color: white;")
                .classes("mt-0 ml-0 font-bold flex-grow text-xs")
            )
            self.android_query_button = ui.button(
                "?",
                on_click=lambda: self.event_handlers.query_event("android"),
            ).classes("bg-blue-600 text-white min-w-[40px] shrink-0")
        with self.get_backup_button:
            ui.tooltip(
                translate_string(
                    "Fetch XML from an Android device.\n\nYou must be on the same network as the Android device, and the device must be running and connected.\n\n",
                ),
            ).style("white-space: pre-wrap")

        # The container panels stay bound right here under the button setup
        self.android_container = ui.column().classes(
            "w-full gap-y-2 mt-4 p-2 bg-gray-50 dark:bg-gray-700 rounded shadow-sm hidden",
        )
        self.upgrade_container = ui.column().classes("w-full gap-y-2 mt-2 items-center text-center hidden")


def create_help_options_section(self: MyGui) -> None:
    """The Display Help and Get Android Help buttons, at the top of the Assistance tab."""
    handlers = self.event_handlers

    # 1. Specialized Help Buttons Row
    with ui.row().classes("w-full gap-2 mt-0 self_center justify-center"):
        self.display_help_button = ui.button(
            translate_string("Display Help"),
            on_click=lambda: handlers.query_event("help"),
        ).classes(
            "bg-blue-600 text-white",
        )

        self.get_android_help_button = ui.button(
            translate_string("Get Android Help"),
            on_click=lambda: handlers.query_event("android"),
        ).classes("bg-blue-600 text-white")
