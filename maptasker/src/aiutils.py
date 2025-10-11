"""List AI Models"""

#                                                                                      #
# mapai: Ai support                                                                    #
#                                                                                      #
import os
import pickle
from contextlib import suppress

import ollama
from google.genai import Client
from openai import OpenAI

from maptasker.src.error import rutroh_error
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import (
    DEEPSEEK_MODELS,
    GEMINI_MODELS,
    KEYFILE,
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
        with suppress(KeyError):
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
        bad_models = [
            "audio",
            "transcribe",
            "tts",
            "moderation",
            "embedded",
            "embedding",
            "image",
            "realtime",
            "research",
            "instruct",
        ]

        # Filter and sort models based on preference using list comprehension
        sorted_models = [
            model.id
            for model in sorted(all_models.data, key=lambda m: m.id)  # Sort by model.id
            if any(model.id.startswith(prefix) for prefix in preferred_model_prefix)
            and not contains_any_substring_loop(model.id, bad_models)
        ]

    except Exception as e:  # noqa: BLE001
        rutroh_error(f"An error occurred trying to list OpenAi models: {e}")
        return OPENAI_MODELS

    return sorted_models


def contains_any_substring_loop(main_string: str, substrings: str) -> bool:
    """
    Checks if a main_string contains any of the provided substrings using a for loop.

    Args:
        main_string (str): The string to search within.
        substrings (list): A list of strings to search for.

    Returns:
        bool: True if main_string contains at least one of the substrings, False otherwise.
    """
    return any(sub in main_string for sub in substrings)  # No substring was found


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
        # "claude-opus-4-20250514",
        "claude-opus-4-0",  # alias
        "claude-opus-4-1",  # alias
        # "claude-sonnet-4-20250514",
        "claude-sonnet-4-0",  # alias
        "claude-sonnet-4-5",
        # Claude 3.7 Models
        # "claude-3-7-sonnet-20250219",
        "claude-3-7-sonnet-latest",  # alias
        # Claude 3.5 Models
        # "claude-3-5-haiku-20241022",
        "claude-3-5-haiku-latest",  # alias
        # "claude-3-5-sonnet-20241022",
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
    bad_models = {"text", "image", "vision"}
    # try:
    #     # Get the API key
    #     with suppress(KeyError):
    #         api_key = PrimeItems.ai["gemini_key"]
    #     if not api_key:
    #         return GEMINI_MODELS

    #     # print("Fetching available Gemini models...")
    #     # Configure Gemini
    #     genai.Client(api_key=api_key)
    #     models = []

    #     # List all available models
    #     models = [
    #         m
    #         for m in genai.list_models()
    #         if "generateContent" in m.supported_generation_methods
    #         and not contains_any_substring_loop(m.name, bad_models)
    #     ]

    #     if not models:
    #         # print("No Gemini models found that support text generation.")
    #         return GEMINI_MODELS

    #     # Now get just the names
    #     models_to_keep = [m.name.replace("models/", "") for m in models]

    # except Exception as e:
    #     rutroh_error(f"An error occurred trying to list OpenAi models: {e}")
    #     return GEMINI_MODELS

    # Get the API key
    with suppress(KeyError):
        api_key = PrimeItems.ai["gemini_key"]
    if not api_key:
        return GEMINI_MODELS

    # 1. Initialize the Client
    # The Client will automatically look for your API key in the GOOGLE_API_KEY
    # environment variable.
    try:
        client = Client(api_key=api_key)
    except Exception as e:  # noqa: BLE001
        rutroh_error(f"Error initializing client: {e}")
        rutroh_error("\nPlease ensure your GOOGLE_API_KEY environment variable is set correctly.")
        return []

    # 2. Get the list of models
    all_models = client.models.list()
    if not all_models:
        # print("No Gemini models found that support text generation.")
        return GEMINI_MODELS

    # 3. Iterate and print the model names
    # The models.list() returns a generator, so we iterate over it.
    models_to_keep = []
    model_count = 0
    for model in all_models._page:  # noqa: SLF001
        model_name = model.name[7:]
        # Filter for models whose names start with 'gemini' to focus on Gemini models
        if (
            "gemini" in model_name
            and "generateContent" in model.supported_actions
            and not contains_any_substring_loop(
                model_name,
                bad_models,
            )
        ):
            models_to_keep.append(model_name)

    if model_count == 0:
        rutroh_error("No Gemini models found. There may be a connection issue or a filter problem.")
    # else:
    #     print(f"\nSuccessfully listed {model_count} Gemini models.")
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
        "codegemma:latest",
        "codegemma:2b",
        "codegemma:7b",
        "codellama:latest",
        "codellama:7b",
        "codellama:13b",
        "codeqwen:latest",
        "deepseek-coder",
        "deepseek-coder-v2:latest",
        "deepseek-r1",
        "deepseek-r1:1.5b",
        # "deepseek-v3",  # This model is huge...404gb!
        # "devstral",     # This model is 14gb!
        "dolphin3",
        "exaone-deep",
        "deepcoder",
        "devstral",
        "gemma",
        "gemma2:latest",
        "gemma2:2b",
        "gemma3",
        "gemma3:1b",
        "gemma3n:latest",
        "gemma3n:e2bllama2",
        "gemma3n:e4b",
        "gpt-oss:latest",
        "llama2",
        "llama3",
        "llama3.1:latest",
        "llama3:l:8b",
        "llama3.2:latest",
        "llama3.2:1b",
        "llama3.3",
        "llama4",
        "magistral",
        "mistral",
        "mistral-nemo",
        "olmo2",
        "phi3:latest",
        "phi4",
        "phi4-mini",
        "qwen",
        "qwen2",
        "qwen2.5-coder:latest",
        "qwen2.5-coder:0.5b",
        "qwen2.5-coder:1.5b",
        "qwen2.5-coder:3b",
        "qwen2.5vl:3b",
        "qwen2.5:0.5b",
        "qwen2.5:1.5b",
        "qwen2.5:latest",
        "qwen3:0.6b",
        "gwen3-coder",
        "qwen3:latest",
        "qwen3:1.7b",
        "qwen3:4b",
        "starcoder2:latest",
        "tinyllama",
    ]

    try:
        # Get all locally available models
        all_models = ollama.list()
        loaded_models = []

        # Get the model names into a list.
        loaded_models = [model_info["model"] for model_info in all_models["models"]]

        # Remove duplicates and sort for cleaner output
        return sorted(list(set(modify_list_elements(extended_list, loaded_models, " (installed)"))))

    except ollama.ResponseError as e:
        rutroh_error(f"Error connecting to Ollama: {e}")
        rutroh_error(
            "Please ensure the Ollama server is running. You can usually start it by running 'ollama serve' in your terminal.",
        )
        return extended_list
    except Exception as e:  # noqa: BLE001
        rutroh_error(f"An unexpected error occurred: {e}")
        return extended_list


def get_deepseek_models() -> list:
    """
    Get the list of deepseek AI models.

    Returns:
        list: _description_
    """
    return DEEPSEEK_MODELS


# Get the Ai api key
def get_api_key() -> tuple:
    """
    Retrieves the API key from the specified file.

    This function checks if the KEYFILE exists and if it does, it opens the file and reads the first line. The first line is assumed to be the API key. If the KEYFILE does not exist, it returns the string "None".

    Returns:
        tuple: The file type and the API key if it exists, otherwise "None".
    """
    if os.path.isfile(KEYFILE):
        kind_of_file, contents = detect_and_read_file(KEYFILE)
        if kind_of_file == "text":  # Legacy?
            return contents
        if kind_of_file == "pickle":
            PrimeItems.ai["api_key"] = contents["api_key"]
            PrimeItems.ai["openai_key"] = contents["openai_key"]
            PrimeItems.ai["deepseek_key"] = contents["deepseek_key"]
            # For snthropic, try the old key name first.
            try:
                PrimeItems.ai["anthropic_key"] = contents["claude_key"]
            except KeyError:  # New key name.
                PrimeItems.ai["anthropic_key"] = contents["anthropic_key"]
            with suppress(KeyError):
                PrimeItems.ai["gemini_key"] = contents["gemini_key"]
            with suppress(KeyError):
                PrimeItems.ai["ai_name"] = contents["ai_name"]
            return PrimeItems.ai["api_key"]
    return "None"


def detect_and_read_file(file_path: object) -> tuple:
    """
    Detects the file type and reads its content.

    Args:
        file_path (object): The path to the file to be read.

    Returns:
        tuple: A tuple containing the file type and its content.
    """
    try:
        # Try opening the file as a pickle
        with open(file_path, "rb") as file:
            content = pickle.load(file)  # noqa: S301
        return "pickle", content  # noqa: TRY300
    except (pickle.UnpicklingError, EOFError):
        pass

    try:
        # Try opening the file as text
        with open(file_path, encoding="utf-8") as file:
            content = file.read()
        return "text", content  # noqa: TRY300
    except UnicodeDecodeError:
        pass

    return "None", None
