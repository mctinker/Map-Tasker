"""GUI Window Classes and Definitions (NiceGUI Version)"""

from nicegui import ui

from maptasker.src.aiutils import get_api_key
from maptasker.src.getputer import save_restore_args
from maptasker.src.primitem import PrimeItems


class APIKeyDialog:
    """Manages the AI API Keys popup using a NiceGUI modal dialog."""

    def __init__(self, master_gui: object) -> None:
        """Initialize the NiceGUI dialog container."""
        self.master = master_gui
        self.my_gui = master_gui

        # Create the inner NiceGUI dialog element
        self.dialog = ui.dialog()

        # CHANGE: Store the custom class instance container on my_gui instead of the raw dialog
        self.my_gui.ai_apikey_window = self

        # Build the layout inside the dialog
        with self.dialog, ui.card().classes("w-[700px] p-6 max-w-full"):
            ui.label("API Key Options").classes("text-xl font-bold text-blue-600 mb-4")

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
                    "OK",
                    on_click=lambda: self.my_gui.event_handlers.ai_apikey_get_event(cancel=False, clear=""),
                ).classes("bg-blue-600 text-white px-6")

                # Help/Query Button
                ui.button("?", on_click=lambda: self.my_gui.event_handlers.query_event("apikey")).classes(
                    "bg-gray-500 text-white min-w-[40px]",
                )

                # Cancel Button
                ui.button(
                    "Cancel",
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
                ui
                .input(value=PrimeItems.ai.get(placeholder_key, ""), placeholder="Not configured...")
                .props("password clearable")
                .classes("flex-grow")
            )

            # Save widget representation dynamically to the dialog instance
            setattr(self, entry_name, input_widget)

            # Clear button action
            ui.button(
                "Clear",
                on_click=lambda: self.my_gui.event_handlers.ai_apikey_get_event(
                    cancel=False,
                    clear=placeholder_key,
                ),
            ).classes("bg-gray-300 text-black text-xs")

        return input_widget


def open_api_key_dialog(gui_instance: object = None) -> ui.dialog:
    """
    Opens a NiceGUI dialog to manage AI API keys.
    Replaces the old CTk APIKeyDialog class.
    """

    # 1. Fetch existing keys from your backend
    openai_key = get_api_key("openai") or ""
    anthropic_key = get_api_key("anthropic") or ""
    gemini_key = get_api_key("gemini") or ""
    deepseek_key = get_api_key("deepseek") or ""
    llama_key = get_api_key("llama") or ""

    # 2. Create the Modal Dialog
    with ui.dialog() as dialog, ui.card().classes("w-full max-w-md p-6"):
        ui.label("Manage AI API Keys").classes("text-2xl font-bold mb-4 text-blue-600")
        ui.label("Enter your API keys below. They will be saved securely.").classes("text-sm text-gray-500 mb-4")

        # 3. Input fields (password=True masks the input like asterisks)
        openai_input = ui.input("OpenAI Key", value=openai_key, password=True).classes("w-full mb-2")
        anthropic_input = ui.input("Anthropic Key", value=anthropic_key, password=True).classes("w-full mb-2")
        gemini_input = ui.input("Gemini Key", value=gemini_key, password=True).classes("w-full mb-2")
        deepseek_input = ui.input("DeepSeek Key", value=deepseek_key, password=True).classes("w-full mb-2")
        llama_input = ui.input("LLaMA Key (Optional)", value=llama_key, password=True).classes("w-full mb-6")

        def save_keys():
            """Saves the inputs back to PrimeItems and writes to disk."""
            PrimeItems.program_arguments["openai_api_key"] = openai_input.value
            PrimeItems.program_arguments["anthropic_api_key"] = anthropic_input.value
            PrimeItems.program_arguments["gemini_api_key"] = gemini_input.value
            PrimeItems.program_arguments["deepseek_api_key"] = deepseek_input.value
            PrimeItems.program_arguments["llama_api_key"] = llama_input.value

            # Use your existing save routine
            save_restore_args(PrimeItems.program_arguments, "save")

            ui.notify("API Keys saved successfully!", type="positive")
            dialog.close()

        # 4. Action Buttons
        with ui.row().classes("w-full justify-end mt-2"):
            ui.button("Cancel", on_click=dialog.close).classes("bg-gray-400 text-white")
            ui.button("Save", on_click=save_keys).classes("bg-blue-600 text-white ml-2")

    # Open the dialog when the function is called
    dialog.open()
    return dialog
