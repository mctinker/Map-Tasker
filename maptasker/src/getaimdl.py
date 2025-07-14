"""List AI Models"""

#                                                                                      #
# mapai: Ai support                                                                    #
#                                                                                      #
import contextlib

import google.generativeai as genai
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

    except Exception as e:
        rutroh_error(f"An error occurred trying to list OpenAi models: {e}")
        return GEMINI_MODELS

    return models_to_keep
