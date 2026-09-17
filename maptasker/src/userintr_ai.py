"""AI event handlers: the model and prompt pickers, the API keys dialog and the Analyze button.

Split out of userintr.py the same way userintr_android.py was.  AIEventHandlers is a mixin that
MapTaskerEventHandlers inherits, so gui.event_handlers keeps every name the window wires up,
and a handler here reaches the others through self -- the API keys dialog's buttons arrive
through MapTaskerEventHandlers._handle_event, which stays in userintr.

The AI work itself is not here: mapai runs an analysis, aiutils lists the models and apikeys
keeps the keys.  This is only what the window's AI controls do when they are used.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from maptasker.src.aiutils import get_api_key
from maptasker.src.apikeys import fallback_file, save_api_keys
from maptasker.src.config import AI_PROMPT
from maptasker.src.getputer import save_restore_args
from maptasker.src.guistate import gui_settings
from maptasker.src.guiutils import (
    SINGLE_ITEM_LABELS,
    display_analyze_button,
    display_error_file_and_ai_response,
    display_model_pulldown,
    display_selected_object_labels,
    list_tasker_objects,
    set_ai_key,
    update_analysis_button_color,
)
from maptasker.src.guiwins2 import APIKeyDialog
from maptasker.src.mapai import get_ai_object, map_ai, valid_api_key
from maptasker.src.maputil2 import translate_string
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import logger

if TYPE_CHECKING:
    from nicegui import Event

    from maptasker.src.userintr import MapTaskerEventHandlers, MyGui


class AIEventHandlers:
    """The AI handlers MapTaskerEventHandlers inherits: self.gui is the window, and every other
    handler is reached through self, just as it was before these moved here."""

    def ai_model_selected_event(self: MapTaskerEventHandlers, event_value: Event) -> None:
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

    # Show for edit the AI API Key
    def ai_apikey_event(self) -> None:
        """
        Prompts the user to enter their API key, or leaves it as is if it already exists.
        If the user enters a new API key, it is saved (see apikeys).
        """
        the_view = self.gui
        # Get our key, if it exists.
        the_view.ai_apikey = get_api_key()

        # 1. Instantiate the Dialog Class
        api_key_dialog = APIKeyDialog(the_view)

        # # 2. Keep the class reference safely stored if needed elsewhere
        # the_view.ai_apikey_dialog_instance = api_key_dialog

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

        # persistent: this holds a typed-in prompt, so it closes on Submit or Cancel only --
        # a stray click on the backdrop would otherwise throw the typing away.  Same reason
        # every Add/Edit dialog in guiwins carries it.
        with ui.dialog().props("persistent") as dialog, ui.card().classes("w-[500px] p-6"):
            ui.label(dialog_title).classes("text-xl font-bold text-blue-600 mb-2")

            # Display current prompt info
            ui.label(f"{msg1} '{the_view.ai_prompt}'").classes("text-sm text-gray-500 italic mb-4")
            ui.label(msg2).classes("text-sm font-semibold")

            # Input field (initialized with current prompt text for convenience)
            prompt_input = ui.input(value=the_view.ai_prompt).classes("w-full mb-6")

            # Actions Row
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button(translate_string("Cancel"), on_click=lambda: dialog.submit(None)).classes(
                    "bg-gray-400 text-white",
                )
                ui.button(translate_string("Submit"), on_click=lambda: dialog.submit(prompt_input.value)).classes(
                    "bg-blue-600 text-white",
                )

        # 2. Open the dialog and execution halts here until dialog.submit() is triggered
        name_entered = await dialog

        # 3. Handle the resulting inputs identically to your original logic
        # Canceled? (User clicked Cancel or closed the modal backdrop)
        if name_entered is None:
            the_view.display_message_box(translate_string("Prompt change canceled."), "Orange")

        # The same?
        elif name_entered == the_view.ai_prompt:
            the_view.display_message_box(translate_string("Prompt did not change."), "Orange")

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
        ui.notify(translate_string("Starting AI Analysis..."), type="info")
        gui = self.gui

        # Validate the model
        if gui.ai_model in ("None", ""):
            gui.display_message_box(translate_string("No model selected."), "Orange")
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
            _, _ = save_restore_args(gui_settings(gui), gui.color_lookup, to_save=True)

            # Now make certain we have the api key set for the model we are using.
            PrimeItems.program_arguments["ai_apikey"] = gui.ai_apikey
            PrimeItems.program_arguments["ai_model"] = gui.ai_model
            # Save the current tab
            gui.tab_to_use = "Analyze"

            # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
            # Ok, run the analysis.  Await the execution of map_ai() so control doesn't leak early!
            # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
            try:
                await map_ai()
            finally:
                # The analysis is over, so stop saying it is running.  map_ai clears its own
                # PrimeItems copy of the flag; this is the view's, which every later save and
                # every rerun copies back into PrimeItems (see rungui.process_gui).  In a
                # 'finally' because an analysis that failed is just as over as one that worked.
                gui.ai_analyze = False

            # Display messages from the AI run.
            display_error_file_and_ai_response(self)

        # Test if no XML data loaded
        elif (
            not PrimeItems.tasker_root_elements["all_projects"]
            and not PrimeItems.tasker_root_elements["all_profiles"]
            and not PrimeItems.tasker_root_elements["all_tasks"]
        ):
            gui.display_message_box(
                translate_string("No projects, profiles, or tasks have been loaded!  Load some XML and try again."),
                "Orange",
            )
        # No single item has been selected.
        else:
            gui.display_message_box(
                translate_string("Single Project/Profile/Task has not been selected!  Select only one and try again."),
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
                translate_string("'Cancel' button selected. No change to the API keys!"),
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
                # Only the entry is cleared.  The key itself goes when 'Ok' saves the
                # dialog -- a blank entry is a change like any other -- and stays if
                # 'Cancel' backs out, as the dialog's help says.
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

        # 5. Save the keys if they have modified state
        if apikey_changed:
            try:
                in_password_store = save_api_keys(PrimeItems.ai)
            except OSError as error:
                text = translate_string("The API keys could not be saved:")
                _display_message_box(f"{text} {error}", "Red")
                ui.notify(f"{text} {error}", type="negative")
            else:
                if not in_password_store:
                    text = translate_string(
                        "No password store was available, so the API keys were saved to a file only you can read:"
                    )
                    _display_message_box(f"{text} {fallback_file()}", "Orange")

            # Refresh keys on the GUI instance and update context-conditional state flags
            set_ai_key(gui, gui.ai_model)

            # Redisplay the UI dependencies
            display_analyze_button(gui, 13, first_time=False)
            display_selected_object_labels(gui)
        else:
            gui.display_message_box(translate_string("No API keys changed."), "LimeGreen")

        # 6. Close the window view
        dialog_container.close()

        # Updates NiceGUI visual rendering colors reactively
        update_analysis_button_color(gui)

    def ai_apikey_get_event(self, cancel: bool, clear: bool) -> None:  # noqa: D102
        self._handle_event("ai_apikey_process_event", "ai_apikey_window", cancel, clear)
