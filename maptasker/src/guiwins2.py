"""GUI Window Classes and Definitions (NiceGUI Version)"""

from nicegui import ui

from maptasker.src.maputil2 import translate_string
from maptasker.src.primitem import PrimeItems


class APIKeyDialog:
    """Manages the AI API Keys popup using a NiceGUI modal dialog."""

    def __init__(self, master_gui: object) -> None:
        """Initialize the NiceGUI dialog container."""
        self.master = master_gui
        self.my_gui = master_gui

        # Create the inner NiceGUI dialog element.  persistent: it holds typed-in API keys,
        # so it closes on OK or Cancel only -- a stray click on the backdrop would otherwise
        # throw them away.  Same reason every Add/Edit dialog in guiwins carries it.
        self.dialog = ui.dialog().props("persistent")

        # CHANGE: Store the custom class instance container on my_gui instead of the raw dialog
        self.my_gui.ai_apikey_window = self

        # Build the layout inside the dialog
        with self.dialog, ui.card().classes("w-[700px] p-6 max-w-full"):
            ui.label(translate_string("API Key Options")).classes("text-xl font-bold text-blue-600 mb-4")

            # Form grid layout area (Labels, Inputs, and Clears)
            with ui.column().classes("w-full gap-4 mb-6"):
                self.openai_key = self.create_key_entry("OpenAI API Key:", "openai_key")
                self.anthropic_key = self.create_key_entry("Claude API Key:", "anthropic_key")
                self.deepseek_key = self.create_key_entry("DeepSeek API Key:", "deepseek_key")
                self.gemini_key = self.create_key_entry("Gemini API Key:", "gemini_key")

            # Action Buttons Row (OK, ?, and Cancel)
            with ui.row().classes("w-full justify-end items-center gap-2 border-t pt-4"):
                # OK Button
                ui.button(
                    translate_string("OK"),
                    on_click=lambda: self.my_gui.event_handlers.ai_apikey_get_event(cancel=False, clear=""),
                ).classes("bg-blue-600 text-white px-6")

                # Help/Query Button
                ui.button("?", on_click=lambda: self.my_gui.event_handlers.query_event("apikey")).classes(
                    "bg-gray-500 text-white min-w-[40px]",
                )

                # Cancel Button
                ui.button(
                    translate_string("Cancel"),
                    on_click=lambda: self.my_gui.event_handlers.ai_apikey_get_event(cancel=True, clear=""),
                ).classes("bg-red-500 text-white px-6")

    def open(self) -> None:
        """Public method to show the dialog."""
        self.dialog.open()

    def close(self) -> None:
        """Public method to close the dialog."""
        self.dialog.close()

    def create_key_entry(self, label_text: str, placeholder_key: str) -> ui.input:
        """Helper function to create a label, text entry, and 'Clear' button for an API key."""
        entry_name = f"entry_{placeholder_key}"

        # Align each key group in a single clean horizontal row
        with ui.row().classes("w-full items-center justify-between gap-4"):
            # Label
            ui.label(label_text).classes("text-orange-500 font-semibold w-32")

            # Input field tied directly to dynamic object variable names
            # Using password mode keeps keys masked out securely on screen
            input_widget = (
                ui.input(
                    value=PrimeItems.ai.get(placeholder_key, ""), placeholder=translate_string("Not configured...")
                )
                .props("password clearable")
                .classes("flex-grow")
            )

            # Save widget representation dynamically to the dialog instance
            setattr(self, entry_name, input_widget)

            # Clear button action
            ui.button(
                translate_string("Clear"),
                on_click=lambda: self.my_gui.event_handlers.ai_apikey_get_event(
                    cancel=False,
                    clear=placeholder_key,
                ),
            ).classes("bg-gray-300 text-black text-xs")

        return input_widget
