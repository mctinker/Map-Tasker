"""List AI Models"""

#                                                                                      #
# mapai: Ai support                                                                    #
#                                                                                      #
import contextlib

import google.generativeai as genai
import ollama
from openai import OpenAI

from maptasker.src.error import rutroh_error
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import (
    GEMINI_MODELS,
    OPENAI_MODELS,
)


def get_openai_models() -> list:
    """
    Lists all available OpenAI models that can be called from Python,
    with a focus on models suitable for programming hints (like for Android Tasker).

    Requires your OpenAI API key to be set as an environment variable:
    export OPENAI_API_KEY='YOUR_API_KEY'
    """
    try:
        # Get the API key from environment variables
        with contextlib.suppress(KeyError):
            api_key = PrimeItems.ai["openai_key"]

        # If we don't have the api key, then just use the default list of models.
        if not api_key:
            return OPENAI_MODELS
        # Initialize the OpenAI client
        client = OpenAI(api_key=api_key)

        # List all models
        # The .models.list() method returns a ModelsPage object, which is iterable
        all_models = client.models.list()

        if not all_models.data:
            return OPENAI_MODELS

        # Define the preferred mopdel name preficies.
        preferred_model_prefix = [
            "gpt",
            "o",
            "o",
            "text",  # Embedding model, not for text generation but good to be aware of
        ]

        # Create a dictionary for quick lookup and to maintain order
        model_details = {m.id: m for m in all_models.data}

        # Filter and sort models based on preference
        sorted_models = []
        for model in sorted(model_details.keys()):
            for model_prefix in preferred_model_prefix:
                if model.startswith(model_prefix):
                    # print(model_details[model])
                    sorted_models.append(model)
                    break

    except Exception as e:  # noqa: BLE001
        rutroh_error(f"An error occurred trying to list OpenAi models: {e}")
        return OPENAI_MODELS

    return sorted_models


def get_anthropic_models() -> list:
    """
    Provides a curated list of Anthropic Claude models suitable for programming hints
    (like for Android Tasker), based on Anthropic's publicly available information.

    Note: The Anthropic API does not provide a direct 'list_models()' endpoint.
    This function relies on a hardcoded list derived from Anthropic's official
    documentation and common knowledge of their model capabilities.

    Requires your Anthropic API key to be set as an environment variable:
    export ANTHROPIC_API_KEY='YOUR_API_KEY'
    """
    # From : https://docs.anthropic.com/en/api/client-sdks
    return [
        "claude-opus-4-20250514",
        "claude-opus-4-0",  # alias
        "claude-sonnet-4-20250514",
        "claude-sonnet-4-0",  # alias
        # Claude 3.7 Models
        "claude-3-7-sonnet-20250219",
        "claude-3-7-sonnet-latest",  # alias
        # Claude 3.5 Models
        "claude-3-5-haiku-20241022",
        "claude-3-5-haiku-latest",  # alias
        "claude-3-5-sonnet-20241022",
        "claude-3-5-sonnet-latest",  # alias
        "claude-3-5-sonnet-20240620",  # previous version
        # Claude 3 Models
        "claude-3-opus-20240229",
        "claude-3-opus-latest",  # alias
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
    ]


def get_gemini_models() -> list:
    """
    Lists all available Gemini models that can be called from Python,
    with a focus on models suitable for programming hints (like for Android Tasker).

    Requires your Google Cloud API key to be set as an environment variable:
    export GOOGLE_API_KEY='YOUR_API_KEY'
    """
    try:
        # Get the API key
        with contextlib.suppress(KeyError):
            api_key = PrimeItems.ai["gemini_key"]
        if not api_key:
            return GEMINI_MODELS

        # print("Fetching available Gemini models...")
        # Configure Gemini
        genai.configure(api_key=api_key)
        models = []

        # List all available models
        models = [m for m in genai.list_models() if "generateContent" in m.supported_generation_methods]

        if not models:
            # print("No Gemini models found that support text generation.")
            return GEMINI_MODELS

        # Now get just the names
        models_to_keep = [m.name.replace("models/", "") for m in models]

        # print("\nAvailable Gemini models for programming hints (ordered by general capability):\n")
        # # Sort models to prioritize more capable ones, though the exact ordering might evolve
        # # We'll also consider models that are generally good for coding/reasoning.

        # # Define a desired order of preference for models
        # # These are generally the most capable for reasoning and complex tasks
        # preferred_order = [
        #     "gemini-1.5-pro",
        #     "gemini-1.5-flash",
        #     "gemini-2.5-pro",  # Note: 2.5 models might be preview/experimental
        #     "gemini-2.5-flash",
        #     "gemini-2.0-flash",  # Older but stable "Flash"
        #     "gemini-pro",  # Original stable Pro model
        # ]

        # # Create a dictionary for quick lookup and to maintain order
        # model_details = {m.name: m for m in models}

        # # Filter and sort models based on preference
        # sorted_models = []
        # for model_name in preferred_order:
        #     if model_name in model_details:
        #         sorted_models.append(model_details[model_name])
        #         del model_details[model_name]  # Remove to avoid duplicates

        # # Add any remaining models that weren't in the preferred list
        # for model_name in sorted(model_details.keys()):
        #     sorted_models.append(model_details[model_name])

        # for model in sorted_models:
        #     description = model.description if model.description else "No description available."
        #     print(f"  Model Name: {model.name}")
        #     print(f"  Description: {description}")
        #     print(f"  Input Modalities: {model.input_token_limit} tokens for input")
        #     print(f"  Output Tokens: {model.output_token_limit} tokens for output")
        #     print(f"  Temperature: {model.temperature:.2f}")
        #     print(f"  Top P: {model.top_p:.2f}")
        #     print(f"  Top K: {model.top_k:.2f}")
        #     print("-" * 40)

    except Exception as e:  # noqa: BLE001
        rutroh_error(f"An error occurred trying to list OpenAi models: {e}")
        return GEMINI_MODELS

    return models_to_keep


def modify_list_elements(list1: list[str], list2: list[str], suffix: str) -> list[str]:
    """
    Modifies elements in the first list if they are found in the second list.

    For each string in `list2`, if it matches an element in `list1`, the
    matching element in `list1` will have the `suffix` appended to it.
    The modification happens in place, and the modified list1 is also returned.

    Args:
        list1 (list[str]): The list of strings to be modified.
        list2 (list[str]): The list of strings to check against `list1`.
        suffix (str): The string to append to matching elements in `list1`.

    Returns:
        list[str]: The modified list1.
    """
    # Create a set from list2 for efficient lookups.
    # This makes checking if an element from list1 is in list2 much faster,
    # especially with large lists.
    list2_set = set(list2)

    # Iterate through list1 using an index so we can modify elements in place.
    for i in range(len(list1)):
        # Check if the current element of list1 exists in list2_set.
        if list1[i] in list2_set:
            # If it matches, append the suffix to the element.
            list1[i] += suffix
    return list1


def get_llama_models() -> list:
    """
    Returns a list of names of Ollama AI models that are typically used for coding.

    This function fetches all locally available Ollama models and filters them
    based on keywords commonly found in the names of coding-oriented models.

    Returns:
        list[str]: A list of model names (e.g., "codellama", "deepseek-coder").
    """
    extended_list = [
        "aya",
        "codegemma",
        "codellama",
        "deepseek-coder",
        "deepseek-coder-v2",
        "deepseek-r1",
        "deepseek-r1:1.5b",
        # "deepseek-v3",  # This model is huge...404gb!
        # "devstral",     # This model is 14gb!
        "exaone-deep",
        "gemma",
        "gemma2:latest",
        "gemma2:2b",
        "gemma3",
        "gemma3:1b",
        "gemma3n",
        "llama2",
        "llama3:latest",
        "llama3.1:latest",
        "llama3.2",
        "llama3.3",
        "mistral",
        "mistral-nemo",
        "phi3",
        "phi4",
        "phi4-mini",
        "qwen",
        "qwen2",
        "qwen2.5-coder",
        "qwen2.5vl:3b",
        "qwen2.5",
        "qwen3:1.7b",
        "tinyllama",
    ]

    try:
        # Get all locally available models
        all_models = ollama.list()
        loaded_models = []

        # Get the model names into a list.
        for model_info in all_models["models"]:
            loaded_models.append(model_info["name"])

        # Remove duplicates and sort for cleaner output
        return sorted(list(set(modify_list_elements(extended_list, loaded_models, " (loaded)"))))

    except ollama.ResponseError as e:
        rutroh_error(f"Error connecting to Ollama: {e}")
        rutroh_error(
            "Please ensure the Ollama server is running. You can usually start it by running 'ollama serve' in your terminal.",
        )
        return []
    except Exception as e:  # noqa: BLE001
        rutroh_error(f"An unexpected error occurred: {e}")
