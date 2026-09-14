"""Loading event handlers: opening a backup file, and choosing the one Project, Profile, Task or Scene to show.

Split out of userintr.py the same way userintr_android.py, userintr_ai.py, userintr_editors.py and
userintr_settings.py were.  LoadingEventHandlers is a mixin that MapTaskerEventHandlers inherits, so
gui.event_handlers keeps every name the window's controls are wired to: 'Get Local XML File' and the
file then chosen, the 'Specific Name' tab's four pulldowns and its 'List Unnamed Items' checkbox,
and selecting the object a single-object export holds once it has been loaded.

They belong together because loading a file decides what can be selected: every path that loads
one ends by resetting the selection or by selecting the export's own object.  Fetching a backup off
the Android device is in userintr_android, which calls select_single_item_export here through self.
local_xml_start_directory lives here as well, and userintr imports it back for the file picker the
Compare button opens.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from nicegui import ui

from maptasker.src.getbakup import validate_xml_file
from maptasker.src.getfile import Local_File_Picker
from maptasker.src.guiutils import (
    SINGLE_ITEM_LABELS,
    clear_android_buttons,
    clear_single_item_names,
    clear_single_item_view_names,
    display_analyze_button,
    is_no_selection,
    list_tasker_objects,
    reset_single_item_pulldowns,
    select_pulldown_option,
    single_item_export_selection,
    update_analysis_button_color,
    update_tasker_object_menus,
)
from maptasker.src.guiwins import refresh_scope_badges
from maptasker.src.maputil2 import translate_string
from maptasker.src.maputils import clear_tasker_data
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import ALL_OBJECTS_MESSAGE

if TYPE_CHECKING:
    from maptasker.src.userintr import MyGui


def local_xml_start_directory(gui: MyGui) -> str:
    """The directory the 'Get Local XML File' picker should open in.

    That is the directory the user last took an XML file from, so pulling in another file
    from the same place doesn't mean walking down to it again every time.  Falls back to
    the home directory when nothing has been picked yet, or when the remembered directory
    is no longer there (renamed, deleted, or on a drive that isn't mounted any more) --
    Local_File_Picker would otherwise come up empty on a path it can't list.

        :param gui: the GUI object holding the remembered directory
        :return: directory to start the file picker in ('~' if there is nothing usable)
    """
    saved_directory = getattr(gui, "local_xml_directory", "") or PrimeItems.program_arguments.get(
        "local_xml_directory",
        "",
    )
    if saved_directory and Path(saved_directory).expanduser().is_dir():
        return saved_directory
    return "~"


def remember_local_xml_directory(gui: MyGui, file_path: str) -> None:
    """Make the directory an XML file was just picked from the default for the next pick.

    Recorded in both places so it survives however the settings get written: the GUI's
    'Save Settings' (and reload_gui) builds what it saves out of the view's attributes,
    while a map run saves PrimeItems.program_arguments (see bildhtml).  'local_xml_directory'
    is in ARGUMENT_NAMES, so it is carried across sessions in the settings file.

        :param gui: the GUI object to record the directory on
        :param file_path: the XML file the user just picked
    """
    if not file_path:
        return
    directory = str(Path(file_path).expanduser().parent)
    gui.local_xml_directory = directory
    PrimeItems.program_arguments["local_xml_directory"] = directory


def _single_item_selection_message(gui: MyGui, item_type: str, name_entered: str) -> str:
    """The 'Specific Name' tab's summary line for the selection just made.

    Choosing "None" does not mean "display only the item called None" -- it means that item
    is no longer being filtered on.  The four selectors are mutually exclusive, so clearing
    one normally leaves nothing selected anywhere; confirm that rather than assume it, and
    if some other item is somehow still set, report that one instead of claiming everything
    is on display.
    """
    display_only = translate_string("Display only")
    if not is_no_selection(name_entered):
        return f"{display_only} {translate_string(item_type)} '{name_entered}'."

    # Nothing selected for this item -- make sure that holds for every other one too.
    for label in SINGLE_ITEM_LABELS:
        still_selected = getattr(gui, f"single_{label.lower()}_name", "")
        if not is_no_selection(still_selected):
            return f"{display_only} {translate_string(label)} '{still_selected}'."

    return translate_string(ALL_OBJECTS_MESSAGE)


# Define a state container to hold our saved file locationvariable
class AppState:
    """Initialize the variable to hold the selected file path.
    This is a class variable that can be accessed and modified from anywhere in the code."""

    selected_file_path = None


class LoadingEventHandlers:
    """The loading handlers MapTaskerEventHandlers inherits: self.gui is the window, and every other
    handler is reached through self, just as it was before these moved here."""

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
        name_entered = name_entered.replace(f"{my_name_translated}: ", "")

        if name_entered in ["No projects found", "No profiles found", "No tasks found", "No scenes found"]:
            the_view.display_message_box(translate_string("Selection ignored."), "Orange")
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

                # Save the name in mygui signle_xxx_name.  Every form of "nothing selected"
                # stores as empty, so nothing downstream has to know about the others.
                name_entered = "" if is_no_selection(name_entered) else name_entered

                # Now save the name where it counts: the_view andf PrimeItems.program_arguments for use in mapit_all.
                setattr(the_view, f"single_{my_name.lower()}_name", name_entered)
                key_name = f"single_{my_name.lower()}_name"
                # Assign it to the dictionary
                PrimeItems.program_arguments[key_name] = name_entered

                # Built after the name is stored, so the "is anything still selected?" check
                # sees this selection too.
                the_view.specific_name_msg = _single_item_selection_message(the_view, my_name, name_entered)

            # Update the pulldown menus.
            update_tasker_object_menus(
                the_view,
                get_data=False,
                reset_single_names=False,
            )
            display_analyze_button(the_view, 13, first_time=False)

            # The 'Run Analysis' button goes green only once a single object is selected, so it
            # has to be recolored whenever that selection changes.
            update_analysis_button_color(the_view)

            # And every view already on screen was drawn for the selection that just changed.
            # A Diagram in particular is a snapshot whose hotlinks point at the objects of the
            # selection it was built for, so it says on its own toolbar that the app has moved
            # on -- see NiceGuiTextView._build_scope_badge.
            refresh_scope_badges(the_view)

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

    def select_single_item_export(self, file_path: str) -> None:
        """Select the one object a single-object export holds, if that is what was loaded.

        Args:
            file_path: the file just loaded -- a local path (or the open file object
                PrimeItems.file_to_get holds) for 'Get Local XML File', or the Android
                path for a file fetched from the device.

        Tasker writes an export of one Project/Profile/Task/Scene as
        "<name>.prj|prf|tsk|scn.xml", and such a file has exactly one thing in it worth
        looking at.  Selecting it here saves the user picking the only candidate out of
        a 'Specific Name' pulldown by hand before anything can be mapped, diagrammed or
        analyzed.  A full backup selects nothing and everything is displayed, as before.

        Goes through process_single_name_event rather than setting single_<item>_name
        directly, so an automatic selection lands everywhere a hand-made one does: the
        view, PrimeItems.program_arguments, the pulldown widget, the "Display only ..."
        caption, which Edit/Add buttons are on screen, and the 'Run Analysis' button's
        color.

        Call this only once the file has been loaded -- see
        guiutils.single_item_export_selection, which resolves the name against the XML
        rather than trusting the file's own name.
        """
        label, name = single_item_export_selection(file_path)
        if not label:
            return

        self.process_single_name_event(label, name)

        # ...and put the name in the pulldown itself, which process_name_event does not
        # do for the item being selected: it resets every pulldown *except* that one
        # (reset_single_item_pulldowns' except_for), on the reasonable assumption that
        # the user just picked the value there themselves and the widget already holds
        # it.  Nobody picked anything here, so without this the Project is selected
        # everywhere -- the filter, the caption, the Edit/Add buttons -- while its
        # pulldown carries on reading "None".
        #
        # select_pulldown_option because a Project's option is "Project: <name>" rather
        # than the bare name, and under is_updating because assigning .value fires the
        # widget's on_change (single_project_name_event and friends), which would
        # otherwise re-enter process_name_event for the selection just made.
        optionmenu = getattr(self.gui, f"specific_{label.lower()}_optionmenu", None)
        if optionmenu is None:
            return
        try:
            self.gui.is_updating = True
            select_pulldown_option(optionmenu, name)
            optionmenu.update()
        finally:
            self.gui.is_updating = False

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

        # Open the file picker in the directory the last XML file was taken from, falling
        # back to the home directory ('~').
        # The 'await' pauses this specific function until the user finishes picking a file.
        # The ceiling stays at home no matter where we start: Local_File_Picker's default
        # upper_limit is whatever directory it opens in, which would leave the user unable
        # to navigate up out of a remembered subdirectory.
        result = await Local_File_Picker(local_xml_start_directory(gui), upper_limit="~", multiple=False)

        # 3. Check if the user selected a file or canceled the dialog
        if result:
            # Save the exact file location and name to our variable
            # (local_file_picker returns a tuple if multiple=True, or a string if multiple=False)
            AppState.selected_file_path = result[0] if isinstance(result, tuple) else result

            # Update the UI to reflect the saved variable
            gui.current_file.text = f"Saved Variable: {AppState.selected_file_path}"
            gui.current_file.classes(replace="text-green-600 font-bold")
            ui.notify(translate_string("File path saved successfully!"), type="positive")

            # Let everyone knmow which file we are working with
            PrimeItems.file_to_get = (
                AppState.selected_file_path[0]
                if isinstance(AppState.selected_file_path, list)
                else AppState.selected_file_path
            )

            # Open the picker here next time.
            remember_local_xml_directory(gui, PrimeItems.file_to_get)

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

            # If this was a single-object export, select the one object it holds.  Done
            # last, after the pulldowns have been rebuilt for the new file and
            # reset_single_names has cleared the previous file's selection, so this
            # selection is the one left standing.
            self.select_single_item_export(PrimeItems.file_to_get)

        else:
            # Handle the case where the user hit "Cancel" or closed the dialog
            ui.notify(translate_string("File selection canceled."), type="warning")

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

        # A file fetched off the device is as likely to be a single-object export as one
        # picked off the local drive, so it gets the same treatment 'Get Local XML File'
        # gets: the export's own Project/Profile/Task/Scene selected outright.  The
        # Android path names its file with the device's path, but only the file's own
        # name is read, so the two arrive at the same place.
        self.select_single_item_export(the_view.android_file)

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
