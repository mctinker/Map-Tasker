"""The AI model pulldown and the checks that go with it: which models are offered, which key goes with which, and whether a configuration can be used."""

from typing import TYPE_CHECKING, cast

from nicegui import ui

# Keep your existing logic imports (e.g., from maptasker.src.core.aiutils import ...)
from maptasker.src.core.aiutils import (
    get_anthropic_models,
    get_api_key,
    get_gemini_models,
    get_llama_models,
    get_openai_models,
)
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.core.primitem import SINGLE_ITEM_LABELS, RunState
from maptasker.src.core.sysconst import (
    LLAMA_MODELS,
    MODEL_GROUPS,
    logger,
)
from maptasker.src.gui.guiutil2 import window_state

if TYPE_CHECKING:
    from maptasker.src.gui.userintr import MyGui


# ==========================================
# 2. DYNAMIC COMPONENT UPDATERS
# ==========================================
def is_ollama_model(gui: "MyGui") -> bool:
    """True if the selected model is a local Ollama (LLAMA group) model, which runs without an API key.

    The model name is checked three ways, since it can arrive from either the built-in list or
    the extended list of models actually installed under Ollama:
      - the provider prefix the dropdown was built with ("LLAMA: llama3.2" -> ai_name "LLAMA"),
      - the built-in LLAMA_MODELS list, and
      - whatever Ollama reported as installed (PrimeItems.ai["llama_models"]), whose entries carry
        a " (installed)" suffix that has to come off before comparing.
    """
    model = (getattr(gui, "ai_model", "") or "").replace(" (installed)", "").strip()
    if not model or model == "None":
        return False

    # The dropdown prefixes every model with its provider group, and ai_model_selected_event
    # stashes that prefix in ai_name -- the most reliable signal when one is present.
    if (getattr(gui, "ai_name", "") or "").upper() in ("LLAMA", "OLLAMA"):
        return True

    installed = {item.replace(" (installed)", "").strip() for item in gui.state.ai.get("llama_models", [])}
    return model in set(LLAMA_MODELS) | installed


def update_analysis_button_color(gui: "MyGui") -> None:
    """Colors the 'Run Analysis' button green once everything ai_analyze_event needs is in place:
      - a prompt,
      - a single Tasker object (Project, Profile, Task or Scene) selected, and
      - a model that is either a local Ollama model (no API key needed) or a cloud model whose
        API key is set.
    Red otherwise. "None" is the dropdown's own placeholder for "nothing selected", so it counts
    as not having a model even though it's a non-empty string.
    """
    # Called from several state-change paths, some of which can run before the button exists.
    button = getattr(gui, "analysis_button", None)
    if button is None:
        return

    has_model = bool(getattr(gui, "ai_model", None)) and gui.ai_model != "None"
    has_prompt = bool(getattr(gui, "ai_prompt", None))
    # "Hidden" is the placeholder shown in place of a real key, not a key.
    has_key = bool(getattr(gui, "ai_apikey", None)) and gui.ai_apikey != "Hidden"
    has_single_item = any(getattr(gui, f"single_{label.lower()}_name", "") for label in SINGLE_ITEM_LABELS)

    ready = has_prompt and has_single_item and has_model and (is_ollama_model(gui) or has_key)
    button.props(f"color={'green' if ready else 'red'}")


def _window_from(gui_arg: object) -> "MyGui | None":
    """The MyGui window a handler's first argument stands for, or None (logged) if it is not one."""
    window = getattr(gui_arg, "gui", None)
    if window.__class__.__name__ == "MyGui":
        gui_instance = cast("MyGui", window)
    elif hasattr(gui_arg, "client") or hasattr(gui_arg, "sender"):
        # It's a NiceGUI UI Event object; try to fetch from PrimeItems or a cross-reference
        gui_instance = cast("MyGui", getattr(getattr(gui_arg, "state", None), "mygui", gui_arg))
    else:
        gui_instance = cast("MyGui", gui_arg)

    if gui_instance.__class__.__name__ != "MyGui":
        logger.error(f"display_model_pulldown received an invalid GUI context object: {type(gui_arg)}")
        return None
    return gui_instance


def _models_to_display(gui_instance: "MyGui", extended_models: list[str] | None) -> list[str] | None:
    """The model names the pulldown should hold, or None if it already holds them."""
    predefined = sorted(model for name, models in MODEL_GROUPS.items() for model in prefix_and_sort(models, name))

    # An extended list was asked for.
    if gui_instance.ai_model_extended_list and not gui_instance.initialization:
        if gui_instance.displaying_extended_list is not None and gui_instance.displaying_extended_list:
            return None
        # Get the extended list...only if we are not in the middle of setting/changing the language.
        if gui_instance.state.language_set:
            return predefined
        models = (
            extended_models if extended_models is not None else get_extended_ai_model_list(state=gui_instance.state)
        )
        gui_instance.displaying_extended_list = True
        return models

    # Just the pre-defined model names.
    if gui_instance.displaying_extended_list is not None and not gui_instance.displaying_extended_list:
        return None
    gui_instance.displaying_extended_list = False
    return predefined


def display_model_pulldown(
    gui_arg: object,
    *_args: object,
    extended_models: list[str] | None = None,
    **_kwargs: object,
) -> None:
    """Displays the AI model selection dropdown list.

    Normalizes `gui_arg` whether it's passed a direct MyGui instance,
    a NiceGUI event object, or a MapTaskerEventHandlers instance.

    `extended_models` is the extended list already fetched (see extended_models_event, which
    fetches it off the event loop); None fetches it here when it is wanted.
    """
    gui_instance = _window_from(gui_arg)
    if gui_instance is None:
        return

    display_models = _models_to_display(gui_instance, extended_models)
    if display_models is None:
        return  # Already showing the list that was asked for.

    # If the select dropdown already exists on the GUI instance, just update its options
    if hasattr(gui_instance, "ai_model_option") and gui_instance.ai_model_option:
        gui_instance.ai_model_option.options = display_models
        keep_selected_model(gui_instance, display_models)
        gui_instance.ai_model_option.update()
    else:
        # Otherwise, if we are building it for the first time
        # Always the "None" placeholder to begin with: keep_selected_model puts the chosen model back once the
        # list is in place.  (This once compared a one-item list with the strings in display_models, which can
        # never match, so it always came to the same answer; a plain "None" is not among the options and
        # NiceGUI refuses to build a select whose value it cannot find.)
        current_model = ["None"]
        gui_instance.ai_model_option = (
            ui.select(
                options=display_models,
                value=current_model,
                label=translate_string("AI Model"),
                on_change=gui_instance.event_handlers.ai.ai_model_selected_event,
            )
            .classes("w-64")
            .tooltip(translate_string("Select the model belonging to the AI you wish to use."))
        )

        # Updates NiceGUI visual rendering colors reactively
        update_analysis_button_color(gui_instance)


def keep_selected_model(gui_instance: "MyGui", display_models: list[str]) -> None:
    """Point the model pulldown back at the selected model once its options are replaced.

    The two lists spell a model differently -- the extended one marks an installed Ollama model
    " (installed)" -- and a select whose value is not among its new options is left blank, which
    looked as if switching lists had thrown the chosen model away.
    """
    model = (getattr(gui_instance, "ai_model", "") or "").replace(" (installed)", "").strip()
    match = next(
        (option for option in display_models if option.split(": ", 1)[-1].replace(" (installed)", "").strip() == model),
        None,
    )
    if match is None:
        return
    try:
        gui_instance.is_updating = True  # Not a new choice, so ai_model_selected_event has nothing to do.
        gui_instance.ai_model_option.value = match
    finally:
        gui_instance.is_updating = False


def prefix_and_sort(strings: list[str], name: str) -> list[str]:
    """
    Prefixes each string in a list with a given name and returns the modified list sorted.

    Args:
        strings: A list of strings.
        name: The name to prefix each string with.

    Returns:
        A new list of strings with each original string prefixed by `name`, sorted alphabetically.
    """

    prefixed_strings = [f"{name}: {s}" for s in strings]
    prefixed_strings.sort()
    return prefixed_strings


def get_extended_ai_model_list(state: RunState) -> list[str]:
    """Retrieves and compiles an extended list of available AI models from various providers.

    This function fetches models from OpenAI, Anthropic, and Gemini (assuming respective
    API keys are configured or default lists are available). It groups these models
    by their provider, applies a prefix and sorts them within their groups,
    and then consolidates them into a single, sorted list.

    The process involves:
    1. Attempting to retrieve API keys (though the result is not directly used here).
    2. Fetching available models from OpenAI.
    3. Fetching available models from Anthropic.
    4. Fetching available models from Gemini.
    5. Organizing these models into a dictionary, keyed by provider name.
    6. Iterating through each provider's models, applying 'prefix_and_sort'
       (which is expected to add a provider-specific prefix and sort them).
    7. Consolidating all processed models into a single list.
    8. Performing a final sort on the entire consolidated list.

    Returns:
        list: A sorted list of strings, where each string represents an AI model,
              potentially prefixed with its provider name (e.g., "OpenAI/gpt-4o",
              "Anthropic/claude-3-opus-20240229", "Gemini/gemini-pro").
              Returns an empty list if no models are retrieved.
    """
    _ = get_api_key(state=state)
    state.ai["openai_models"] = get_openai_models(state=state)
    state.ai["anthropic_models"] = get_anthropic_models(state=state)
    state.ai["gemini_models"] = get_gemini_models(state=state)
    state.ai["llama_models"] = get_llama_models()

    # Define the models
    extended_model_groups = {
        "OpenAI": state.ai["openai_models"],
        "Anthropic": state.ai["anthropic_models"],
        "Gemini": state.ai["gemini_models"],
        "LLAMA": state.ai["llama_models"],
    }
    # all_models = openai_models + anthropic_models + gemini_models

    # Create an empty list to store the display models
    display_models: list[str] = []

    # Iterate through the items in extended_model_groups
    for name, models in extended_model_groups.items():
        # Apply prefix_and_sort to the current group of models
        sorted_models_with_prefix = prefix_and_sort(models, name)

        # Extend the display_models list with the processed models
        display_models.extend(sorted_models_with_prefix)

    # Finally, sort the entire list of display models
    return sorted(display_models)


def displayed_model(self: "MyGui") -> str:
    """The text the AI model dropdown should show for the active model."""
    model_to_display = "None"
    if self.ai_model:
        # If the dropdown widget exists, look for the choice that ends with our active model
        if getattr(self, "ai_model_option", None) and self.ai_model_option.options:
            matching_option = next((opt for opt in self.ai_model_option.options if opt.endswith(self.ai_model)), None)
            model_to_display = matching_option or self.ai_model
        else:
            model_to_display = self.ai_model

    return model_to_display


def is_valid_ai_config(self: "MyGui") -> bool:
    """
    Validates the AI model and API key against predefined configurations in PrimeItems.

    This method iterates through a list of known AI providers (e.g., OpenAI, Anthropic, Gemini)
    and checks if the instance's `self.ai_model` exists within any provider's model list.
    If a matching model is found, it further checks if the `self.ai_apikey` matches
    the corresponding API key stored in `PrimeItems.ai` for that provider.
    Some providers (like 'llama' in this example) may not require an API key check.

    The method rutroh_errors a message indicating whether the AI model and API key combination
    is considered valid based on the configurations.

    Returns:
        bool: True if the `self.ai_model` and `self.ai_apikey` (if required)
              are valid according to `PrimeItems.ai` configurations; False otherwise.
    """
    # Dictionary mapping provider names to their models and key attributes in PrimeItems.ai
    # If 'llama_models' needs an API key, add 'llama_key' here.
    ai_providers: dict[str, dict[str, str | None]] = {
        "openai": {"models": "openai_models", "key": "openai_key"},
        "anthropic": {"models": "anthropic_models", "key": "anthropic_key"},
        "gemini": {"models": "gemini_models", "key": "gemini_key"},
        "llama": {"models": "llama_models", "key": None},  # Assuming no key for llama based on original if
    }
    if not self.ai_model:
        return False  # Don't do anything if there is no model to check against.

    # Make sure we have read in the api keys.
    if not self.ai_apikey or self.ai_apikey == "Hidden":
        self.ai_apikey = get_api_key(state=self.state)

    is_valid_config = False
    for provider, config in ai_providers.items():
        models: list[str] = self.state.ai.get(config["models"] or "", [])
        key_name = config["key"]
        key_to_check = self.state.ai.get(key_name) if key_name else None
        api_key = key_to_check if provider != "llama" and key_to_check == self.state.ai[f"{provider}_key"] else None

        # If llama, then we need to strip " (Installed)" off the name.
        if provider == "llama":
            models = [item.replace(" (installed)", "") for item in models]

        if self.ai_model in models:
            if provider != "llama" and not api_key:
                # We have found the model but it doesn't have the api key.
                break
            if api_key is None or self.state.ai[key_name or ""] == api_key:  # No key check needed for this provider
                is_valid_config = True
                self.ai_apikey = api_key
                break
            break

    return is_valid_config


def set_ai_key(self: "MyGui", model: str) -> bool:
    """
    Set the API key for the AI service based on the selected model.

    Args:
        self (object): The instance of the class.
        model (str): The model name for which to set the API key.

    Returns:
        None
    """
    # Set the appropriate API key based on the model chosen.  This doesn't apply to llama (no apikey).
    model_keys = {
        **dict.fromkeys(window_state(self).ai["openai_models"], "openai_key"),
        **dict.fromkeys(window_state(self).ai["anthropic_models"], "anthropic_key"),
        **dict.fromkeys(window_state(self).ai["gemini_models"], "gemini_key"),
    }
    ai_to_get = model_keys.get(model, "")
    if not ai_to_get:
        return False
    self.ai_apikey = window_state(self).ai.get(ai_to_get)

    # If we didn't find the key, then see if we are using the extended list and need to get the key.
    if not self.ai_apikey and self.ai_model_extended_list:
        self.ai_apikey = get_api_key(state=window_state(self))
        # Try again using the updated model list.
        self.ai_apikey = window_state(self).ai.get(model_keys.get(model, ""), "")

    return bool(self.ai_apikey)
