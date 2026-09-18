"""Settings and appearance event handlers: the output options, colors, fonts, language and settings files.

Split out of userintr.py the same way userintr_android.py, userintr_ai.py and userintr_editors.py
were.  SettingsEventHandlers is a mixin that MapTaskerEventHandlers inherits, so gui.event_handlers
keeps every name the window's controls are wired to: the output options (detail level, conditions,
directory, twisty and the rest), name styling, indent, font, colors, language, the view and action
limits, the notification timeout, and the Save, Restore and Reset buttons.

rebuild_gui_layout moved with them: it is how Reset and a change of language redraw the window,
and nothing else calls it.  The window itself is still laid out by guiwins.initialize_screen,
and the settings are still read and written by getputer.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from nicegui import context, run, ui

from maptasker.src.colrmode import set_color_mode
from maptasker.src.config import DEFAULT_DISPLAY_DETAIL_LEVEL
from maptasker.src.getputer import save_restore_args
from maptasker.src.guistate import gui_settings
from maptasker.src.guiutils import (
    SINGLE_ITEM_LABELS,
    add_logo,
    check_new_version,
    display_current_file,
    display_selected_object_labels,
    refresh_tasker_object_pulldowns,
    select_pulldown_option,
    selected_tab_name,
    set_tasker_object_names,
    update_tasker_object_menus,
)
from maptasker.src.guiwins import (
    NOTIFY_TIMEOUT_CHOICES,
    element_is_live,
    initialize_screen,
    live_views,
    set_document_language_js,
    set_notification_timeout,
)
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.maputil2 import translate_string
from maptasker.src.maputils import clear_tasker_data, make_hex_color
from maptasker.src.outline import outline_the_configuration
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import ARGUMENT_NAMES, NOTIFY_TIMEOUT_DEFAULT, TYPES_OF_COLOR_NAMES, VIEW_LIMIT_DEFAULT

if TYPE_CHECKING:
    from nicegui import Event

    from maptasker.src.userintr import MapTaskerEventHandlers, MyGui


class SettingsEventHandlers:
    """The settings handlers MapTaskerEventHandlers inherits: self.gui is the window, and every other
    handler is reached through self, just as it was before these moved here."""

    # ==========================================
    # 3. INPUT & DROPDOWN EVENTS
    # ==========================================
    def detail_selected_event(self: MapTaskerEventHandlers, event_value: Event) -> None:
        """
        NICEGUI PARADIGM SHIFT:
        Dropdown (ui.select) on_change events automatically pass an 'event' object.
        The new selected value is stored in `event`.

        Accepts the pulldown's event object, a bare string (what a restored settings file and
        the 'Everything' toggle hand over) or an int, and always leaves an int on the GUI --
        see the note below on why the type matters.
        """
        if self.gui.is_updating:
            return

        # The level is an int on the GUI object.  save_settings_event() writes these attributes
        # to the settings file as-is, and every reader of program_arguments["display_detail_level"]
        # compares it numerically (> 2, == 4, >= DISPLAY_DETAIL_LEVEL_all_tasks ...), so a string
        # here is what wrote display_detail_level = "5" into the TOML and left capture_gui_state() (guistate.py)
        # and process_gui() (rungui.py) converting it back on every run.  The pulldown keeps a
        # string of its own below, since its options are strings.
        raw_level = event_value if isinstance(event_value, (int, str)) else event_value.value
        # Anything unconvertible (an empty pulldown, say) leaves the current level alone rather
        # than replacing it with something no comparison can handle.
        with contextlib.suppress(TypeError, ValueError):
            self.gui.display_detail_level = int(raw_level)
        self.gui.is_updating = True

        self.gui.sidebar_detail_option.value = str(self.gui.display_detail_level)
        self.gui.sidebar_detail_option.update()
        self.gui.is_updating = False

    def reset_settings_event(self: MapTaskerEventHandlers) -> None:
        """Put every setting back to its default and rebuild the window to show it."""
        the_view = self.gui
        previous_language = the_view.language

        # The loaded XML goes with the settings.  The settings being reset here are the ones
        # that say which file to read and which single item to map, so data read under the
        # old ones has no business outliving them -- and the button's tooltip promises as
        # much.  Both the parsed data and the file it came from go.
        clear_tasker_data()
        PrimeItems.file_to_get = ""

        # Back to the runtime arguments a fresh run starts with.  Not literally a fresh run,
        # though: this one is still the GUI, and a good deal of the program asks
        # program_arguments whether it is (error reporting, XML loading, the map build), so
        # that one flag is put straight back.
        PrimeItems.program_arguments = initialize_runtime_arguments()
        PrimeItems.program_arguments["gui"] = True

        # Reset the view's own settings, then the colors that follow from the appearance mode
        # it just reset.
        the_view.set_defaults()
        PrimeItems.colors_to_use = set_color_mode(the_view.appearance_mode)

        # set_defaults puts the language back to English but does not touch the catalog the
        # rest of the program translates through, so the window would come back in the old
        # language while every setting claimed English -- and 'Save Settings' would then save
        # English for a window that is not in it.  Only when there is a switch to make: the
        # handler announces the language it sets, which is not something to say to somebody
        # who was in English all along and pressed a button marked "Reset Options".
        if previous_language != "English":
            self.language_set_event("English")

        # Rebuild the whole layout rather than walk it putting each control back by hand.
        # That is what this used to do -- a hand-written list of every option menu and every
        # checkbox to reset -- and a control added anywhere else in the window was a control
        # the reset quietly missed.  Rebuilding reads each one back from the settings that
        # have just been defaulted, so there is nothing to keep in step.
        ui.timer(
            0.01,
            lambda: self.rebuild_gui_layout(the_view, announce=translate_string("Settings Reset!")),
            once=True,
        )

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

        # set_defaults has just put the notification duration back to the default, and the
        # restore below does not reach the key that undoes that until a dozen messages later --
        # every one of which would sit on screen for the default duration rather than the
        # chosen one.  The saved value is in hand now, so put it in force before the restore
        # starts reporting itself.  The loop restores it again on its way past, to the same
        # value, which costs nothing.
        if "notify_timeout" in temp_args:
            self.notify_timeout_event(temp_args["notify_timeout"])

        # Check for errors
        with contextlib.suppress(KeyError):
            if temp_args["msg"]:
                the_view.display_message_box(temp_args["msg"], "Red")
                temp_args["msg"] = ""
                self.color_reset_event()
                return

        # If no colors restored, let user know.
        if not the_view.color_lookup:
            the_view.display_message_box(translate_string("Colors set to defaults."), "Green")

        # Restore progargs values
        if temp_args or the_view.color_lookup:
            the_view.extract_settings(temp_args)
            the_view.restore = True

        # No arguments mean no settings.
        else:  # Empty?
            the_view.display_message_box(translate_string("No settings file found."), "Orange")

        # Save our background color for later reuse
        the_view.saved_background_color = make_hex_color(the_view.color_lookup.get("background_color"))

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

        # Deferred so the teardown happens outside the LeftDrawer context this event
        # fired from (see rebuild_gui_layout).
        ui.timer(0.01, lambda: self.rebuild_gui_layout(the_view), once=True)

    def rebuild_gui_layout(self: MapTaskerEventHandlers, the_view: MyGui, announce: str = "") -> None:
        """Tear the whole layout down and build it again from the view's current settings.

        Used by anything that changes settings wholesale rather than one control at a time:
        a language switch (every label has to be restated) and 'Reset Options' (every control
        has to go back to its default).  Both would otherwise have to walk the entire window
        putting each widget back by hand, which is what 'Reset Options' used to do and what
        left it a control behind every time a new one was added.

        Call it from a ui.timer rather than directly, so the rebuild happens outside the
        event's own NiceGUI context -- deleting the drawer the event fired from while that
        drawer is the active slot is what the callers' 10ms deferral avoids.

            :param the_view: the GUI whose window is to be rebuilt
            :param announce: message to put on screen once the new layout is standing
        """
        client = context.client

        # Carry the tab the user is actually looking at across the rebuild.
        #
        # initialize_screen() re-selects self.tab_to_use, but nothing updates that when
        # a tab is clicked -- it only ever holds what the settings file restored, or
        # "Analyze" from the last analysis run (see analyze_event).  So a language
        # switch used to land on whatever tab was saved rather than the one on screen.
        # Read it off the live ui.tabs here, while the old layout is still standing.
        selected_tab = selected_tab_name(the_view)
        if selected_tab is not None:
            the_view.tab_to_use = selected_tab

        # Remove previous top-level layout elements (header/drawer/footer). NiceGUI
        # moves those to be direct children of the q-layout (siblings of the page
        # container), so they must be torn down explicitly rather than via
        # `client.layout.clear()`, which would also destroy the page container itself.
        #
        # Skip anything already deleted.  Dialogs are siblings of the page container
        # too -- create_popup_window() and friends only close() them, so every dialog
        # ever opened is still sitting in this list -- and NiceGUI plants a hidden
        # "canary" element for each one in whatever slot was active when the dialog
        # was built (see Dialog.__init__), with a weakref.finalize that deletes the
        # dialog once that canary is collected.  MapTasker's dialogs are built from
        # drawer/content callbacks, so deleting a drawer below drops the canary's last
        # reference and CPython runs the finalizer right there, mid-loop, taking those
        # dialogs out of the list this loop is walking a snapshot of.  Deleting one a
        # second time is what raised "ValueError: list.remove(x): x not in list".
        for child in list(client.layout.default_slot.children):
            if child is not client.page_container and not child.is_deleted:
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

            # Redisplay current file onto the fresh layout.  Only when there is one: with
            # nothing loaded the label as just built reads "No file loaded", which is the
            # right thing to say, and display_current_file would replace it with a bare
            # "Current File: ".
            if the_view.file:
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

            # Update the pull-down menus option items lists.
            #
            # refresh_tasker_object_pulldowns, not list_tasker_objects: the latter
            # gates on load_xml(), which with nothing loaded yet goes off and opens
            # the file picker, and reports the user's not having picked one as a red
            # "Cancel button pressed." toast -- on a language switch, where no file
            # was ever asked for.  (It also re-fetches from the Android device
            # whenever android_ipaddr is set, which is just as unwanted here.)  The
            # pulldowns are all this needs, and refreshing them is exactly what the
            # split-out tail does: it rebuilds the lists from whatever is already in
            # PrimeItems.tasker_root_elements, filling in translated "No projects
            # found" placeholders when that is empty -- which is the right answer for
            # a relabel-everything pass anyway.
            refresh_tasker_object_pulldowns(the_view)

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

            # No tab relabelling here: initialize_screen() above rebuilt the tabs from
            # scratch, translating each label as it went, so there is nothing left to
            # restate.  What used to stand here assigned translate_string(...) to each
            # tab's ".text", which a ui.tab does not have (its caption is ".label", see
            # NiceGUI's LabelElement) -- so it set a stray attribute on the element and
            # relabelled nothing.  It only ever looked like it worked because the real
            # translation had already happened a few lines earlier.

            # Whatever the caller wants said about the rebuild is said here, inside the new
            # layout's context: by the time this returns, the active context is the deleted
            # slot the timer was created in, where ui.notify() raises "The parent element
            # this slot belongs to has been deleted."
            if announce:
                ui.notify(announce, type="warning")

            # Forces the tab panel component container to process text and redraw updates
            ui.update()

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

        # Re-stamp the live document's language.  Switching language rebuilds the layout but
        # not the document, so the lang attribute baked in at page build (see
        # document_language_html in guiwins.py) would still name the previous language --
        # and a browser that trusts it could decide the newly translated UI needs
        # translating.  Only possible once a client is connected, which is not the case
        # during the startup settings restore that also lands here.
        with contextlib.suppress(Exception):
            if PrimeItems.mygui is not None and context.client.has_socket_connection:
                ui.run_javascript(
                    set_document_language_js(PrimeItems.languages.get(language_to_use, "en")),
                )

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
            the_view.task_action_label.text = f"{translate_string('Task Action Limit:')} {value}"

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
        # Save the arguments in the temporary dictionary
        _, the_view.color_lookup = save_restore_args(
            gui_settings(the_view),
            the_view.color_lookup,
            to_save=True,
        )
        the_view.display_message_box(translate_string("Settings saved."), "Green")

    def notify_timeout_event(self: object, choice: object) -> None:
        """Notification Duration pulldown, and the same key on restore.

        Takes either the label the pulldown shows ("10 seconds") or the milliseconds the
        settings file holds (10000), because both arrive here: the widget sends its label and
        restore_display sends the saved number.  Anything unrecognised falls back to the
        default rather than to zero -- a bad value should not silently turn every message in
        the app into one that never goes away.
        """
        guiview = self.gui
        if getattr(guiview, "is_updating", False):
            return None

        raw = choice.value if hasattr(choice, "value") else choice
        by_label = {translate_string(label): milliseconds for label, milliseconds in NOTIFY_TIMEOUT_CHOICES}
        by_label.update(dict(NOTIFY_TIMEOUT_CHOICES))

        if isinstance(raw, str) and raw in by_label:
            milliseconds = by_label[raw]
        else:
            try:
                milliseconds = int(str(raw).strip())
            except (TypeError, ValueError):
                milliseconds = NOTIFY_TIMEOUT_DEFAULT
            if milliseconds not in {value for _label, value in NOTIFY_TIMEOUT_CHOICES}:
                milliseconds = NOTIFY_TIMEOUT_DEFAULT

        guiview.notify_timeout = milliseconds
        set_notification_timeout(milliseconds)

        label_for = {value: label for label, value in NOTIFY_TIMEOUT_CHOICES}
        display_value = translate_string(label_for[milliseconds])
        widget = getattr(guiview, "notify_timeout_optionmenu", None)
        if widget:
            try:
                guiview.is_updating = True
                widget.value = display_value
                widget.update()
            finally:
                guiview.is_updating = False
        return f"{translate_string('Notification Duration')} {translate_string('set to')} {display_value}\n"

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
                display_value = str(VIEW_LIMIT_DEFAULT)  # Fallback safety
                guiview.view_limit = VIEW_LIMIT_DEFAULT

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
                    ui.notify(
                        translate_string("The change will take effect the next time you open the view."),
                        color="green",
                    )

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
                    ui.notify(
                        translate_string("The change will take effect the next time you open the view."),
                        color="green",
                    )

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
            translate_string("Tasker items set back to their default colors."),
            "Green",
        )

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

        # Handle Display Detail Level separately.  detail_selected_event() is what puts the
        # level (an int) on the GUI; only the pulldown itself takes the string, its options
        # being strings.
        detail_level_str = str(DEFAULT_DISPLAY_DETAIL_LEVEL)
        mygui.event_handlers.detail_selected_event(DEFAULT_DISPLAY_DETAIL_LEVEL)

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
        if mygui.twisty and mygui.display_detail_level < all_parameters_threshold:
            mygui.display_message_box(
                translate_string(
                    "This has no effect with Display Detail Level less than 3.  Display Detail Level set to 3!",
                ),
                "Red",
            )

            # Update both the dropdown value (a string, like its options) and the class
            # attribute property (an int, like everything that compares it).
            if hasattr(mygui, "sidebar_detail_option") and mygui.sidebar_detail_option:
                mygui.sidebar_detail_option.value = "3"
            mygui.display_detail_level = all_parameters_threshold
            PrimeItems.program_arguments["display_detail_level"] = all_parameters_threshold

        # 3. Check to see if we are doing everything (they are mutually exclusive)
        if mygui.twisty and mygui.everything:
            mygui.display_message_box(
                translate_string("'Twisty' and 'Everything' are mutually exclusive.  Unchecking 'Twisty'."),
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
                        ui.label(label_text)
                        .style(f"font-family: {font_name}; font-size: 14px;")
                        .classes("text-gray-500 italic ml-4")
                    )

    async def profiles_per_line_event(self, profiles_per_line: int) -> None:
        """Sets gui.profiles_per_line to the newly selected value and regenerates/redisplays
        the Diagram view (see NiceGuiTextView._profiles_per_line_selected in guiwins.py)."""
        gui = self.gui
        gui.profiles_per_line = profiles_per_line
        PrimeItems.program_arguments["profiles_per_line"] = profiles_per_line

        # Nothing to check for None here: this call returns nothing, so nicegui's cancelled-wait
        # answer and its ordinary one are the same value (see nicegui.run._run).
        await run.io_bound(outline_the_configuration)

        # Reload every open Diagram view -- "Open View In New Window" can leave more than one up.
        for view in live_views(gui):
            if hasattr(view, "reload_diagram"):
                view.reload_diagram()
