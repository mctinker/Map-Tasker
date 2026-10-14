"""List AI Models"""

#                                                                                      #
# mapai: Ai support                                                                    #
#                                                                                      #
import importlib.util
import shutil
import subprocess
import time
from collections.abc import Callable
from contextlib import suppress
from types import ModuleType

import httpx

# import ollama
# from google.genai import Client
# from openai import OpenAI
from maptasker.src.core import console
from maptasker.src.core.apikeys import load_api_keys
from maptasker.src.core.error import rutroh_error
from maptasker.src.core.maputil3 import AI_EXTRA_INSTALL_COMMAND, import_optional
from maptasker.src.core.primitem import RunState
from maptasker.src.core.sysconst import (
    ANTHROPIC_EXTENDED_MODELS,
    GEMINI_MODELS,
    OPENAI_MODELS,
    logger,
)

# How long to wait for a just-started Ollama server to begin answering, and how often to ask.
# A first start straight after an install is the slow case: it has its model store to set up
# before it will answer anything.
OLLAMA_STARTUP_TIMEOUT = 30  # seconds
OLLAMA_POLL_SECONDS = 1.0
OLLAMA_DOWNLOAD_URL = "https://ollama.com/download"


# What an Ollama call raises when the server cannot answer it.
def ollama_errors() -> tuple[type[Exception], ...]:
    """The exceptions an Ollama call raises when there is no usable answer.

    The client turns a refused connection into ConnectionError and an error reply into
    ollama.ResponseError.  Anything else the transport meets -- a timeout, a connection
    dropped mid-reply -- comes through as httpx's own HTTPError, httpx being what the
    client talks over.

    Only for use once the 'ollama' package has been imported (by import_optional): an
    Ollama call cannot have been made before that.

    Returns:
        tuple[type[Exception], ...]: the exceptions, ready for an except clause.
    """
    return (ConnectionError, importlib.import_module("ollama").ResponseError, httpx.HTTPError)


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
    except ollama_errors():
        return False
    return True


# Start the Ollama server ('ollama serve') and wait until it is ready to be used.
def start_ollama_server() -> tuple[bool, str]:
    """Start the Ollama server with the 'ollama serve' terminal command and wait for it to answer.

    Having the 'ollama' package does not mean a server is running: the Ollama desktop app may
    not be open, or an earlier run's server may have gone away.  Without this, the call that
    needed it would fail with a bare connection error, leaving the user to go and start the
    server by hand.

    Reports nothing itself: the two callers differ on what a failure means (an analysis says so
    through error_handler, the model pulldown only logs it and falls back to its stock list), so
    the reason is handed back for them to deal with.

    Returns:
        tuple[bool, str]: (True, "") once a server is answering, otherwise (False, reason).
    """
    ollama = import_optional("ollama", "ollama")
    if ollama is None:
        return (
            False,
            (
                f"The 'ollama' package is not installed.  Install it with: {AI_EXTRA_INSTALL_COMMAND}"
                f", and Ollama itself from '{OLLAMA_DOWNLOAD_URL}'."
            ),
        )

    # Already up?  Then this run has nothing to start: the Ollama desktop app, an earlier
    # MapTasker run, or the user's own 'ollama serve' is already serving it.
    if ollama_is_responding(ollama):
        return True, ""

    # The Python package and the Ollama application are two separate installs, and only the
    # first one is ours to do.  Say so plainly rather than letting the missing command surface
    # as a FileNotFoundError deep inside an analysis.
    if shutil.which("ollama") is None:
        return (
            False,
            f"Ollama is not installed.  Please install the Ollama app from '{OLLAMA_DOWNLOAD_URL}' and try again.",
        )

    console.say("MapTasker: --- Starting the Ollama server ('ollama serve')... ---")
    try:
        # Not waited on: 'ollama serve' runs for as long as the server does.  Left running
        # afterwards on purpose -- an analysis needs it for its whole duration, and the next
        # request finds this same server (ollama_is_responding) rather than starting a second.
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
            console.say("MapTasker: --- The Ollama server is running. ---")
            return True, ""
        time.sleep(OLLAMA_POLL_SECONDS)

    return (
        False,
        (
            f"The Ollama server did not start within {OLLAMA_STARTUP_TIMEOUT} seconds.  "
            "Try running 'ollama serve' in a terminal, then try again."
        ),
    )


# The suffix the model pulldown puts on a model the user has installed.
INSTALLED_SUFFIX = " (installed)"


def installed_ollama_model(name: str, installed: list[str]) -> str | None:
    """The name Ollama itself knows `name` by, if the user has that model.

    Ollama names a model 'name:tag' ("tinyllama:latest", "llama3.1:8b"), and a name with no tag
    means ':latest'.  A name given without a tag also means the model when the user has it under
    some other tag -- "llama3.1" for an installed "llama3.1:8b" -- so that is accepted too, taking
    the alphabetically first when there are several, so the choice does not depend on the order
    Ollama happened to list them in.

    Args:
        name (str): the model asked for, as the pulldown or a command line spells it.
        installed (list[str]): the names Ollama reports as installed.

    Returns:
        str | None: the installed name, or None if the user does not have the model.
    """
    wanted = name.replace(INSTALLED_SUFFIX, "").strip()
    if not wanted:
        return None
    by_tag = {tagged_model_name(model): model for model in installed}
    if tagged_model_name(wanted) in by_tag:
        return by_tag[tagged_model_name(wanted)]
    if ":" not in wanted:
        return next((by_tag[tag] for tag in sorted(by_tag) if tag.split(":", maxsplit=1)[0] == wanted), None)
    return None


def prepare_ollama_model(name: str, say: Callable[[str], None] = console.say) -> tuple[str | None, str]:
    """Get a local model ready to be asked: a server answering, and the model installed.

    Blocking -- starting a server and downloading a model both take as long as they take -- so an
    async caller runs it in a thread.  A model the user does not have is pulled from Ollama's
    library, with its progress reported through `say`, the way running it at the command line
    would have.

    Args:
        name (str): the model asked for.
        say (Callable[[str], None]): where progress goes.

    Returns:
        tuple[str | None, str]: (the installed model's name, "") when ready, otherwise (None, why not).
    """
    started, reason = start_ollama_server()
    if not started:
        return None, reason
    ollama = import_optional("ollama", "ollama")
    if ollama is None:  # start_ollama_server has just imported it, so this is not expected.
        return None, f"The 'ollama' package is not installed.  Install it with: {AI_EXTRA_INSTALL_COMMAND}"

    try:
        installed = [model["model"] for model in ollama.list()["models"]]
    except ollama_errors() as error:
        return None, f"Could not ask Ollama which models are installed: {error}"
    except (KeyError, TypeError) as error:
        return None, f"Unexpected response from Ollama: {error}"

    if (found := installed_ollama_model(name, installed)) is not None:
        return found, ""

    wanted = name.replace(INSTALLED_SUFFIX, "").strip()
    say(f"MapTasker: --- The Ollama model '{wanted}' is not installed.  Downloading it (this may take a while)... ---")
    try:
        last_status = ""
        for progress in ollama.pull(wanted, stream=True):
            status = progress.get("status") or ""
            if status and status != last_status:
                say(f"MapTasker: {status}")
                last_status = status
    except ollama_errors() as error:
        return None, (
            f"The Ollama model '{wanted}' is not installed and could not be downloaded ({error}).  "
            "See the model library at https://ollama.com/library"
        )
    say(f"MapTasker: --- '{wanted}' is installed. ---")
    return wanted, ""


def get_openai_models(state: RunState) -> list:
    """
    Lists all available OpenAI models that can be called from Python,
    with a focus on models suitable for programming hints (like for Android Tasker).

    Requires your OpenAI API key to be set as an environment variable:
    export OPENAI_API_KEY='YOUR_API_KEY'
    """
    # If we don't have the api key, then just use the default list of models.
    api_key = state.ai.get("openai_key", "")
    if not api_key:
        return OPENAI_MODELS

    # Dynamically get the 'openai' module.
    openai_lib = import_optional("openai", "openai")
    if not isinstance(openai_lib, ModuleType):  # None: it is not installed.
        return OPENAI_MODELS

    try:
        # List all models
        # The .models.list() method returns a ModelsPage object, which is iterable
        all_models = openai_lib.OpenAI(api_key=api_key).models.list()
    except openai_lib.OpenAIError as e:
        # The SDK's whole hierarchy: a bad key, a refused or dropped connection, a timeout.
        # Any of it means the same thing here: fall back to the built-in model list.
        rutroh_error(f"An error occurred trying to list OpenAi models: {e}")
        return OPENAI_MODELS

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
    return [
        model.id
        for model in sorted(all_models.data, key=lambda m: m.id)  # Sort by model.id
        if any(model.id.startswith(prefix) for prefix in preferred_model_prefix)
        and not contains_any_substring_loop(model.id, bad_models)
    ]


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


def get_anthropic_models(state: RunState) -> list:
    """
    Lists the Claude models the Analyze tab's extended list offers.

    With an Anthropic API key to ask with, this is what the Models API says the key can use, so a
    model released after this version of MapTasker is offered too.  Without one -- or when it cannot
    be asked -- it is the built-in list (sysconst.ANTHROPIC_EXTENDED_MODELS).

    Args:
        state (RunState): the run, whose AI settings hold the key.

    Returns:
        list: the model ids, sorted.
    """
    api_key = state.ai.get("anthropic_key", "")
    if not api_key:
        return sorted(ANTHROPIC_EXTENDED_MODELS)

    anthropic = import_optional("anthropic", "anthropic")
    if anthropic is None:
        return sorted(ANTHROPIC_EXTENDED_MODELS)

    try:
        # models.list() pages by itself as it is iterated.
        listed = sorted({model.id for model in anthropic.Anthropic(api_key=api_key).models.list()})
    except anthropic.AnthropicError as e:
        # A bad key, a refused or dropped connection, a timeout: the SDK's whole hierarchy.  None of
        # it is a reason to leave the pulldown empty.
        rutroh_error(f"An error occurred trying to list Anthropic models: {e}")
        return sorted(ANTHROPIC_EXTENDED_MODELS)

    claude = [model for model in listed if model.startswith("claude-")]
    return claude or sorted(ANTHROPIC_EXTENDED_MODELS)


def get_gemini_models(state: RunState) -> list:
    """
    Lists all available Gemini models that can be called from Python,
    with a focus on models suitable for programming hints (like for Android Tasker).

    Requires your Google Cloud API key to be set as an environment variable:
    export GOOGLE_API_KEY='YOUR_API_KEY'
    """
    bad_models = {"text", "image", "vision", "tts"}

    # Get the API key
    with suppress(KeyError):
        api_key = state.ai["gemini_key"]
    if not api_key:
        return GEMINI_MODELS

    try:
        # 1. Initialize the Client
        google_lib = import_optional("google-genai", "google.genai")
        if google_lib is None:
            return GEMINI_MODELS
        client = google_lib.Client(api_key=api_key)

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
    except Exception as e:
        # Deliberately broad.  google.genai installs itself on demand, then goes out to the
        # network: the client, a dropped connection or SSL failure, the SDK's own errors and a
        # changed response shape (this reads a private attribute) all mean the same thing here
        # -- fall back to the built-in model list.  The traceback is logged so that a bug in
        # the code above does not pass for a network problem.
        logger.exception("Listing the Gemini models failed")
        rutroh_error(f"An error occurred trying to list Gemini models: {e}")
        return GEMINI_MODELS

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
        list[str]: A list of model names (e.g., "codellama", "qwen2.5-coder").
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
        "glm-5.2",
        "glm-4.7-flash",
        "gpt-oss:latest",
        "granite4.1",
        "llama2",
        "llama3",
        "llama3.1:latest",
        "llama3.2:latest",
        "llama3.2:1b",
        "llama3.3",
        "llama4",
        "lfm2",
        "kimi-k3",
        "magistral",
        "minimmax-m3",
        "mistral",
        "mistral-nemo",
        "olmo2",
        "ornith:latest",
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

    # Get all locally available models
    ollama = import_optional("ollama", "ollama")
    if ollama is None:
        rutroh_error(
            f"The 'ollama' package is not installed.  Install it with: {AI_EXTRA_INSTALL_COMMAND}"
            f", and Ollama itself from '{OLLAMA_DOWNLOAD_URL}'.",
        )
        return extended_list

    try:
        all_models = ollama.list()
    except ollama_errors() as e:
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
        except ollama_errors() as retry_error:
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


# Get the Ai api keys
def get_api_key(state: RunState) -> str:
    """
    Copy the saved AI API keys into PrimeItems.ai.

    The keys are kept by apikeys -- in the system password store, or in a file only the user
    can read where there is no store -- which reads them once a run.

    Returns:
        str: the saved 'api_key' entry, or "None" if no keys have been saved at all, in
            which case PrimeItems.ai is left as it is.
    """
    saved_keys = load_api_keys()
    if not any(saved_keys.values()):
        return "None"
    state.ai.update(saved_keys)
    return state.ai["api_key"]
