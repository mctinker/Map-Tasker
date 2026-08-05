"""List AI Models"""

#                                                                                      #
# mapai: Ai support                                                                    #
#                                                                                      #
import importlib.util
import os
import pickle
import shutil
import subprocess
import time
from contextlib import suppress
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from maptasker.src.userintr import MyGui

# import ollama
# from google.genai import Client
# from openai import OpenAI
from maptasker.src.error import rutroh_error
from maptasker.src.maputil3 import ensure_and_import
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import (
    DEEPSEEK_MODELS,
    GEMINI_MODELS,
    KEYFILE,
    OPENAI_MODELS,
)

# How long to wait for a just-started Ollama server to begin answering, and how often to ask.
# A first start straight after an install is the slow case: it has its model store to set up
# before it will answer anything.
OLLAMA_STARTUP_TIMEOUT = 30  # seconds
OLLAMA_POLL_SECONDS = 1.0
OLLAMA_DOWNLOAD_URL = "https://ollama.com/download"


# Is there an Ollama server up and answering?
def ollama_is_responding(ollama: object) -> bool:
    """True if an Ollama server is running and answering requests.

    Args:
        ollama (object): the imported 'ollama' package.

    Returns:
        bool: True if the server answered, False for any reason it did not.
    """
    try:
        ollama.list()
    except Exception:  # noqa: BLE001  Any failure at all here simply means "not answering".
        return False
    return True


# Start the Ollama server ('ollama serve') and wait until it is ready to be used.
def start_ollama_server() -> tuple[bool, str]:
    """Start the Ollama server with the 'ollama serve' terminal command and wait for it to answer.

    MapTasker installs the 'ollama' package itself when it is missing (cria.py does it on
    import, via ensure_and_import), and a machine that has just had it installed has no server
    running yet.  Without this, whatever triggered the install would be the thing to fail --
    with a bare connection error -- leaving the user to go and start the server by hand.

    Reports nothing itself: the two callers differ on what a failure means (an analysis says so
    through error_handler, the model pulldown only logs it and falls back to its stock list), so
    the reason is handed back for them to deal with.

    Returns:
        tuple[bool, str]: (True, "") once a server is answering, otherwise (False, reason).
    """
    ollama = ensure_and_import("ollama", "ollama")
    if ollama is None:
        return (
            False,
            f"The 'ollama' package could not be installed.  Please install Ollama from '{OLLAMA_DOWNLOAD_URL}'.",
        )

    # Already up?  Then this run has nothing to start: the Ollama desktop app, an earlier
    # MapTasker run, or the user's own 'ollama serve' is already serving it.
    if ollama_is_responding(ollama):
        return True, ""

    # The Python package and the Ollama application are two separate installs, and only the
    # first one is ours to do.  Say so plainly rather than letting the missing command surface
    # as the FileNotFoundError cria raises deep inside an analysis.
    if shutil.which("ollama") is None:
        return (
            False,
            f"Ollama is not installed.  Please install the Ollama app from '{OLLAMA_DOWNLOAD_URL}' and try again.",
        )

    print("MapTasker: --- Starting the Ollama server ('ollama serve')... ---")
    try:
        # Not waited on: 'ollama serve' runs for as long as the server does.  Left running
        # afterwards on purpose -- an analysis needs it for its whole duration, and cria finds
        # this same process rather than starting a second one.
        subprocess.Popen(
            ["ollama", "serve"],  # noqa: S607  Deliberately found on PATH, as the user runs it.
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as e:
        return False, f"Could not start the Ollama server: {e}"

    # Starting it is not the same as it being ready, so wait for it to actually answer.
    deadline = time.monotonic() + OLLAMA_STARTUP_TIMEOUT
    while time.monotonic() < deadline:
        if ollama_is_responding(ollama):
            print("MapTasker: --- The Ollama server is running. ---")
            return True, ""
        time.sleep(OLLAMA_POLL_SECONDS)

    return (
        False,
        f"The Ollama server did not start within {OLLAMA_STARTUP_TIMEOUT} seconds.  "
        "Try running 'ollama serve' in a terminal, then try again.",
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
        # 1. Dynamically get the 'openai' module
        openai_lib = ensure_and_import("openai", "openai")
        if openai_lib is None:
            return OPENAI_MODELS

        # 2. Extract the specific classes needed
        OpenAI = openai_lib.OpenAI  # noqa: N806

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
            "codex",
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
        "claude-opus-4-5",  # alias
        "claude-opus-4-6",
        # "claude-sonnet-4-20250514",
        "claude-sonnet-4-0",  # alias
        "claude-sonnet-4-5",
        "claude-sonnet-4-6",
        # Claude 3.5 Models
        "claude-3-5-haiku-latest",  # alias
        "claude-haiku-4-5",  # alias
        # "claude-3-5-sonnet-20241022",
        "claude-3-5-sonnet-latest",  # alias
        "claude-sonnet-4-5",  # alias
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
    bad_models = {"text", "image", "vision", "tts"}

    # Get the API key
    with suppress(KeyError):
        api_key = PrimeItems.ai["gemini_key"]
    if not api_key:
        return GEMINI_MODELS

    # 1. Initialize the Client
    # The Client will automatically look for your API key in the GOOGLE_API_KEY
    # environment variable.
    try:
        google_lib = ensure_and_import("google.genai", "google.genai")
        if google_lib is None:
            return GEMINI_MODELS
        # genai = google_lib.genai
        client = google_lib.Client(api_key=api_key)
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
            model_count += 1

    if model_count == 0:
        rutroh_error("No Gemini models found. There may be a connection issue or a filter problem.")
    # else:
    #     print(f"\nSuccessfully listed {model_count} Gemini models.")
    return models_to_keep


# The model name Ollama itself knows a model by.
def tagged_model_name(name: str) -> str:
    """Ollama's full 'name:tag' for a model.  A name with no tag means ':latest' to Ollama."""
    return name if ":" in name else f"{name}:latest"


# Mark the models the user has, and add any of theirs the built-in list does not know about.
def mark_installed_models(catalog: list[str], installed: list[str], suffix: str = " (installed)") -> list[str]:
    """Flag every model in `catalog` that the user actually has under Ollama.

    Ollama reports a model by its full 'name:tag' ("tinyllama:latest", "llama3.1:8b"), while the
    built-in catalog is a mix of both forms ("tinyllama", but also "llama3.1:latest") -- and an
    omitted tag means ':latest'.  Comparing the two as plain strings therefore only ever matched
    when the catalog happened to spell out the same tag, which is why an installed
    "tinyllama:latest" left the catalog's "tinyllama" sitting there unmarked.  Compare on the
    tagged form instead.

    A model the user has installed that the catalog knows nothing about (a different tag of a
    listed model, like "llama3.1:8b", or something the catalog has never heard of) is added to
    the list rather than dropped, since the whole point of the list is to pick a model to run.

    Args:
        catalog (list[str]): the built-in model names.
        installed (list[str]): the model names Ollama reported as installed.
        suffix (str): what to append to the ones the user has.

    Returns:
        list[str]: the catalog with installed models marked, plus any installed extras.
    """
    # Tagged name -> the name to show for it, so each installed model is looked at once.
    installed_by_tag = {tagged_model_name(name): name for name in installed}

    marked = []
    accounted_for = set()
    for entry in catalog:
        tag = tagged_model_name(entry)
        if tag in installed_by_tag:
            accounted_for.add(tag)
            marked.append(f"{entry}{suffix}")
        else:
            marked.append(entry)

    # Whatever the user has that nothing in the catalog covers, under the name Ollama gave it.
    marked.extend(f"{name}{suffix}" for tag, name in installed_by_tag.items() if tag not in accounted_for)

    return marked


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
        "gemini-3-flash-preview",
        "gemma",
        "gemma2:latest",
        "gemma2:2b",
        "gemma3",
        "gemma3:1b",
        "gemma3n:latest",
        "gemma3n:e2bllama2",
        "gemma3n:e4b",
        "glm-4.7",
        "glm-4.7-flash",
        "gpt-oss:latest",
        "granite4.1",
        "llama2",
        "llama3",
        "llama3.1:latest",
        "llama3:l:8b",
        "llama3.2:latest",
        "llama3.2:1b",
        "llama3.3",
        "llama4",
        "lfm2",
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
        "qwen2.5",
        "gwen3-coder",
        "qwen3-coder-next",
        "qwen3-next",
        "qwen3.5:0.8b",
        "qwen3.6:latest",
        "starcoder2:latest",
        "tinyllama",
    ]

    # Ask BEFORE ensure_and_import: it is the call that installs the package, and afterwards
    # there is no telling whether this run was the one that installed it.
    ollama_was_installed = importlib.util.find_spec("ollama") is not None

    # Get all locally available models
    ollama = ensure_and_import("ollama", "ollama")
    if ollama is None:
        rutroh_error(f"The 'ollama' package could not be installed.  Install Ollama from '{OLLAMA_DOWNLOAD_URL}'.")
        return extended_list

    # We just installed it, so nothing can be serving it yet.  Start the server rather than
    # quietly handing back the stock list as though Ollama had no models installed.
    if not ollama_was_installed:
        started, reason = start_ollama_server()
        if not started:
            rutroh_error(reason)
            return extended_list

    try:
        all_models = ollama.list()
    except Exception as e:  # noqa: BLE001  Whatever it was, the list did not come back.
        # Nothing answering.  Start the server and ask once more -- this used to tell the user
        # to go and run 'ollama serve' themselves, and then show a list of models that took no
        # account of what they actually have installed.
        started, reason = start_ollama_server()
        if not started:
            rutroh_error(f"Error connecting to Ollama: {e}")
            rutroh_error(reason)
            return extended_list
        try:
            all_models = ollama.list()
        except Exception as retry_error:  # noqa: BLE001
            rutroh_error(f"Error connecting to Ollama: {retry_error}")
            return extended_list

    try:
        # Get the model names into a list.
        loaded_models = [model_info["model"] for model_info in all_models["models"]]

        # Remove duplicates and sort for cleaner output
        return sorted(set(mark_installed_models(extended_list, loaded_models)))
    except (KeyError, TypeError) as e:
        rutroh_error(f"Unexpected response from Ollama: {e}")
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
    ai_providers = {
        "openai": {"models": "openai_models", "key": "openai_key"},
        "anthropic": {"models": "anthropic_models", "key": "anthropic_key"},
        "gemini": {"models": "gemini_models", "key": "gemini_key"},
        "deepseek": {"models": "deepseek_models", "key": "deepseek_key"},
        "llama": {"models": "llama_models", "key": None},  # Assuming no key for llama based on original if
    }
    if not self.ai_model:
        return False  # Don't do anything if there is no model to check against.

    # Make sure we have read in the api keys.
    if not self.ai_apikey or self.ai_apikey == "Hidden":
        self.ai_apikey = get_api_key()

    is_valid_config = False
    for provider, config in ai_providers.items():
        models = PrimeItems.ai.get(config["models"], [])
        key_to_check = PrimeItems.ai.get(config["key"], None)
        api_key = key_to_check if provider != "llama" and key_to_check == PrimeItems.ai[f"{provider}_key"] else None

        # If llama, then we need to strip " (Installed)" off the name.
        if provider == "llama":
            models = [item.replace(" (installed)", "") for item in models]

        if self.ai_model in models:
            if provider != "llama" and not api_key:
                # We have found the model but it doesn't have the api key.
                break
            if api_key is None or PrimeItems.ai[config["key"]] == api_key:  # No key check needed for this provider
                is_valid_config = True
                self.ai_apikey = api_key
                break
            break

    return is_valid_config
