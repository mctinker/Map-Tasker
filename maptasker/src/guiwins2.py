"""GUI Window Classes and Definitions (NiceGUI Version)"""

from nicegui import ui

from maptasker.src.aiutils import get_api_key
from maptasker.src.getputer import save_restore_args
from maptasker.src.primitem import PrimeItems


def open_api_key_dialog(gui_instance: object = None):
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
