"""Ai Analysis Support
Take the Tasker object, ai model and key and feed it into the approiate AI service.
The response will be saved as a file, which will then be read in by userintr and displayed in a separate textbox
upon reinvocation of the application.
"""

import html
import importlib.util
import re

import httpx
from nicegui import run

from maptasker.src.core import console
from maptasker.src.core.aiutils import OLLAMA_DOWNLOAD_URL, get_api_key, ollama_errors, prepare_ollama_model
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.core.maputil3 import AI_EXTRA_INSTALL_COMMAND, import_optional
from maptasker.src.core.mtexcept import MapTaskerError
from maptasker.src.core.outdir import output_path
from maptasker.src.core.primitem import RunState, get_single_item_requested
from maptasker.src.core.sysconst import (
    ANALYSIS_FILE,
    ERROR_FILE,
    logger,
)
from maptasker.src.core.xmldata import remove_html_tags
from maptasker.src.gui.guiwins import create_popup_window

ai_role = (
    "You are reviewing part of a Tasker configuration for the person who built it.  Tasker is an "
    "Android automation app: a Profile's contexts (events, states, times, apps) trigger Tasks, which "
    "are lists of actions, and Projects group Profiles, Tasks and Scenes.  The data is MapTasker's plain-"
    "text rendering of one Project, Profile, Task or Scene."
)


# Gemini keys as Google has issued them: "AIzaSy" and 33 more characters.
_GEMINI_KEY_PATTERN = re.compile(r"^AIzaSy[A-Za-z0-9_-]{33}$")


def _gemini_key_works(api_key: str) -> bool:
    """True if Google accepts this key: it can ask for the list of models."""
    if not api_key:
        return False
    genai = import_optional("google-genai", "google.genai")
    if genai is None:
        return False
    try:
        next(iter(genai.Client(api_key=api_key).models.list()), None)
    except (genai.errors.APIError, httpx.HTTPError, ValueError):
        # A key Google refuses, no connection to ask over, or a key the client will not take.
        return False
    return True


# Validate an API key
def valid_api_key(ai: str, api_key: str) -> bool:
    """
    Validate the provided API key for one of the services MapTasker can ask.

    OpenAI and Anthropic keys have no format worth checking, so they are tried: a key is valid if
    the service will list its models for it.  A Gemini key is checked against its usual shape first,
    which settles it without a request; a key that does not have that shape is tried too, since
    Google has more than one kind and refusing a good one would be worse than asking.

    Args:
        ai (str): The key to validate: "openai_key", "anthropic_key" or "gemini_key".
        api_key (str): The AI API key to validate.

    Returns:
        bool: True if the API key is valid, False otherwise (or if the service is not one MapTasker can ask).
    """
    if ai == "openai_key":
        # 1. Get the 'openai' module.  It reports its own absence.
        openai_lib = import_optional("openai", "openai")
        if openai_lib is None:
            return False

        # 2. Ask for something only a valid key can see.
        try:
            openai_lib.OpenAI(api_key=api_key).models.list()
        except openai_lib.OpenAIError:
            return False
        return True

    if ai == "anthropic_key":
        anthropic = import_optional("anthropic", "anthropic")
        if anthropic is None:
            return False
        try:
            anthropic.Anthropic(api_key=api_key).models.list()
        except anthropic.AnthropicError:
            return False
        return True

    if ai == "gemini_key":
        return bool(_GEMINI_KEY_PATTERN.match(api_key)) or _gemini_key_works(api_key)

    return False


# Determine if a module is installed or not.
def module_is_available(module_name: str) -> bool:
    """
    Check whether a module is installed, without importing it.

    Args:
        module_name (str): The name of the module to check.

    Returns:
        bool: True if the module is installed, False otherwise.
    """
    try:
        return importlib.util.find_spec(module_name) is not None
    except ModuleNotFoundError:  # A dotted name whose parent package is not installed.
        return False


# Clean up the output list since it has all the front matter and we only need
# the object (Project/Profile/Task)
def cleanup_output(state: RunState) -> list:
    """
    A function that cleans up the output list in prepartion of the query.

    Returns:
        list: The cleaned up output list.
    """
    # Delete everything up to the Profile.
    temp_output = []
    got_it = False
    for line in state.output_lines.output_lines:
        if "Profile:" in line or "Project:" in line or "Task:" in line:
            got_it = True
        if got_it:
            # Ignore blank lines.
            if not line:
                continue
            # Quit if at end of Project.
            if "Tasks not in any Profile," in line:
                break
            temp_line = line.replace("&nbsp;", " ")
            # The model is sent text, not html: "&#11013;" is the arrow it stands for.
            temp_line = html.unescape(remove_html_tags(temp_line, "")).strip("\n")
            # The Map's line breaks, left behind with nothing on them.
            if not temp_line.strip():
                continue
            temp_output.append(temp_line)

    return temp_output


# Record the response to the analysis logs.
def record_response(response: str, ai_object: str, item: str, state: RunState) -> None:
    """
    Writes the given response to the ANALYSIS_FILE and ERROR_FILE. The ERROR_FILE will be displayed in GUI on ReRun.

    Args:
        response (str): The response to be written to the file.
        ai_object (str): The object that was analyzed.
        item (str): The item name that was analyzed.

    Returns:
        None: This function does not return anything.

    This function opens the ANALYSIS_FILE in write mode and writes the given response to it.
    If the file does not exist, it will be created. If the file already exists, its contents will be overwritten.
    The ERROR_FILE will be read and displayed in the GUI on ReRun, with the response handled in
    'display_messages_from_last_run' and 'display_ai_response'
    """
    with open(output_path(ANALYSIS_FILE, state=state), "w", encoding="utf-8") as response_file:
        response_file.write(
            f'{state.program_arguments.ai_name} AI Response using model {state.program_arguments.ai_model} for {ai_object} "{item}":\n\n{response}',
        )
    # Queue up the message to display in the GUI textbox.
    analysis_file_name = ANALYSIS_FILE.split(".")
    process_error(
        f"{response}\n\nAnalysis Response saved in file: {analysis_file_name[0]}-date-time.{analysis_file_name[1]}",
        ai_object,
        item,
        state=state,
    )


# Do local Ai processing.
def local_ai(query: str, ai_object: str, item: str, state: RunState) -> None:
    """
    Perform local AI processing on the given query, with a model run by Ollama.

    Args:
        query (str): The query to be processed by the local AI model.
        ai_object (str): The object to be processed by the local AI model.
        item (str): the object's name

    Returns:
        None: This function does not return anything.

    Description:
        Starts the Ollama server if none is answering, downloads the model if it is not installed,
        and asks it the same question, in the same way, as the server-based services are asked.
    """
    ollama = import_optional("ollama", "ollama")
    if ollama is None:  # The library is not installed; import_optional has said how to get it.
        message = (
            f"Ollama support could not be loaded.  Install the AI libraries with: {AI_EXTRA_INSTALL_COMMAND}"
            f", and Ollama itself from '{OLLAMA_DOWNLOAD_URL}'."
        )
        raise MapTaskerError(message, 12, show_code=False)

    if state.program_arguments.ai_model == "None":
        message = "No model selected."
        raise MapTaskerError(message, 12)

    console.say(f"Model: {state.program_arguments.ai_model}")
    # Make sure we don't come back if this fails.
    state.program_arguments.ai_analyze = False

    # The server, and the model on it.  Either may have to be started or downloaded, and neither is
    # something to end the analysis thread with a traceback over: say what is wrong.
    model, reason = prepare_ollama_model(state.program_arguments.ai_model)
    if model is None:
        raise MapTaskerError(reason, 12, show_code=False)

    messages = [{"role": "system", "content": ai_role}, {"role": "user", "content": query}]
    try:
        reply = ollama.Client().chat(model=model, messages=messages)
        response = reply["message"]["content"]
    except (*ollama_errors(), KeyError, TypeError, ValueError) as e:
        message = f"Ai analysis error: {e}.  Try again."
        raise MapTaskerError(message, 12) from e

    # The response is queued up in the error file, for display back in the GUI.
    record_response(response, ai_object, item, state=state)


# Handle ChatGPT Error
def process_error(error: str, ai_object: str, item: str, state: RunState) -> None:
    """
    Process errors based on the given error message and record the response.

    Args:
        error (str): The error message to be processed.
        ai_object (str): The object that caused the error.
        item (str): The item name that caused the error.

    Returns:
        None: This function does not return anything.
    """
    if "Request too large" in error:
        output_error = f"{ai_object} too large for ChatGPT or ChatGPT quota not enough!\n\n"
    elif "'Incorrect API key provided" in error:
        output_error = "Invalid ChatGPT API key provided!\n\n"
    else:
        output_error = error

    # Write the error to the error file, which will be read in by guiutils and displayed in GUI text box.
    # Note: "Ai Response" must be a part of the message for it to be recognized by guiutils.
    with open(ERROR_FILE, "w", encoding="utf-8") as error_file:
        error_file.write(
            f"'{state.program_arguments.ai_name} AI Response using model {state.program_arguments.ai_model} for {ai_object} {item}:\n\n{output_error}",
        )
    error_file.close()


def _process_openai_response(client: object, query: str, state: RunState) -> str:
    """Helper function to process OpenAI responses."""
    model = state.program_arguments.ai_model
    role = ai_role
    roletype = "user" if "o1" in state.program_arguments.ai_model else "system"
    stream_feed = client.chat.completions.create(
        model=model,
        messages=[
            {"role": roletype, "content": role},
            {"role": "user", "content": [{"type": "text", "text": query}]},
        ],
        stream=True,
        response_format={"type": "text"},
    )
    return "".join(chunk.choices[0].delta.content or "" for chunk in stream_feed)


def _process_anthropic_response(client: object, query: str, state: RunState) -> str:
    """Helper function to process Anthropic (Claude) responses."""
    message = client.messages.create(
        model=state.program_arguments.ai_model,
        # Room for the model's thinking as well as the analysis: on models that think by
        # default, thinking counts toward this limit.
        max_tokens=16000,
        system=ai_role,
        messages=[{"role": "user", "content": query}],
    )
    # A model that thinks puts a thinking block ahead of its text, so content[0] is not the reply.
    text = "".join(block.text for block in message.content if block.type == "text")
    # A model can decline, and can run out of room to finish.  Either leaves a reply that is empty or
    # ends mid-sentence, and it should not pass for the whole analysis.
    if message.stop_reason == "refusal":
        category = getattr(getattr(message, "stop_details", None), "category", None)
        reason = f" ({category})" if category else ""
        return f"{text}\n\nThe model declined to analyze this{reason}.  Try another model.".strip()
    if message.stop_reason == "max_tokens":
        return f"{text}\n\n[The response was cut short: it reached the model's output limit.]"
    return text


def _process_gemini_response(client: object, query: str, state: RunState) -> str:
    """Helper function to process Gemini responses."""
    model = state.program_arguments.ai_model
    role = ai_role
    # Suppress logging warnings
    # message = client.GenerativeModel(model)
    # response1 = message.generate_content(role + query)
    response = client.models.generate_content(
        model=model,
        contents=f"{role}  {query}",
        # MapTasker gives the model no tools, so there is nothing for it to call.  Left unset,
        # the library defaults to automatic function calling and warns that using it this way
        # is "not recommended".
        config={"automatic_function_calling": {"disable": True}},
        # NOTE: Need to add logic to determine specific model eligability for the following option.
        # config=types.GenerateContentConfig(thinking_config=types.ThinkingConfig(thinking_level="low")),
    )
    return response.text


def process_ai_query_and_response(
    client: object,
    query: str,
    ai_object: str,
    item: str,
    state: RunState,
) -> None:
    """
    Generic function to process AI responses from various AI services.

    Args:
        client: The AI client (OpenAI, Claude, Gemini).
        query (str): The query to send to the AI.
        ai_object (str): The object being processed.
        item (str): The name of the object being processed.

    Returns:
        None: This function does not return anything.
    """
    name = state.program_arguments.ai_name

    # Map AI names to their respective processing functions
    ai_processors = {
        "OpenAI": _process_openai_response,
        "Anthropic": _process_anthropic_response,
        "Gemini": _process_gemini_response,
    }

    process_function = ai_processors.get(name)
    if process_function is None:
        message = "Invalid AI name selected."
        raise MapTaskerError(message, 12)

    try:
        response = process_function(client, query, state=state)
        record_response(response, ai_object, item, state=state)
    except Exception as e:
        # Deliberately broad: four AI providers, four unrelated exception hierarchies --
        # handle_ai_error exists precisely to turn any of them into a sentence, so
        # enumerating them here would duplicate that and go stale faster.  The traceback is
        # logged so that a bug in the response handling does not pass for a provider error.
        logger.exception("The %s request failed", name)
        error_message = handle_ai_error(e, state=state)  # Pass the exception object directly
        with open(ERROR_FILE, "w", encoding="utf-8") as response_file:
            response_file.write(error_message)


def handle_ai_error(error: Exception, state: RunState) -> str:
    """
    Handles errors for AI processing.

    Args:
        error (Exception): The exception raised during processing.

    Returns:
        str: The formatted error message.
    """
    # Determine the AI being used.
    model = state.program_arguments.ai_model
    ai = next(
        (
            name
            for name, models in {
                "OpenAI": state.ai["openai_models"],
                "Anthropic": state.ai["anthropic_models"],
                "Llama": state.ai["llama_models"],
                "Gemini": state.ai["gemini_models"],
            }.items()
            if model in models
        ),
        "Unknown",
    )

    # Capture the specific error message, if there is one.
    message = str(error)  # Get the string representation of the exception.

    # Return the appropriate error message.
    if ai == "OpenAI":
        return f"OpenAI failed with error: {error!s}"
    if "invalid x-api-key" in message or "API key not valid" in message:
        return f"Invalid {ai} API key provided: key='{state.program_arguments.ai_apikey}' for model {model}!\n\n"
    if "Connection error" in message:
        return "Connection Error: Check your firewall. If this is not the issue, try another Anthropic API key.  Also check out their 'Initial Setup' steps.\n\n"
    return f"{ai} failed with error: {error!s}"


def open_ai(query: str, ai_object: str, item: str, state: RunState) -> None:
    """
    Sends a query to the OpenAI API to generate a completion using the specified model.

    Args:
        query (str): The query to be sent to the OpenAI API.
        ai_object (str): The object to be processed by the OpenAI API.
        item (str): The name of the object.

    Returns:
        None: This function does not return anything.
    """
    if state.program_arguments.ai_analyze and not module_is_available("openai"):
        message = f"Module 'openai' not found. Install it with: {AI_EXTRA_INSTALL_COMMAND}"
        raise MapTaskerError(message, 12, show_code=False)

    api_key = state.program_arguments.ai_apikey
    if api_key == "Hidden":
        # The settings file only ever holds the word "Hidden"; the key itself is saved apart.
        get_api_key(state=state)
        api_key = state.ai["openai_key"]
    # 1. Dynamically get the 'openai' module
    openai_lib = import_optional("openai", "openai")
    if openai_lib is None:
        return

    # 2. Extract the specific classes needed
    client_class = openai_lib.OpenAI

    client = client_class(api_key=api_key)
    process_ai_query_and_response(client, query, ai_object, item, state=state)


def claude_ai(query: str, ai_object: str, item: str, state: RunState) -> None:
    """
    Sends a query to the Claude API to generate a completion using the specified model.

    Args:
        query (str): The query to be sent to the Claude API.
        ai_object (str): The object to be processed by the Claude API.
        item (str): The name of the object.

    Returns:
        None: This function does not return anything.
    """
    anthropic = import_optional("anthropic", "anthropic")
    if anthropic is None:
        message = f"Module 'anthropic' not found. Install it with: {AI_EXTRA_INSTALL_COMMAND}"
        raise MapTaskerError(message, 12, show_code=False)
    client = anthropic.Anthropic(api_key=state.program_arguments.ai_apikey)
    process_ai_query_and_response(client, query, ai_object, item, state=state)


def gemini_ai(query: str, ai_object: str, item: str, state: RunState) -> None:
    """
    Sends a query to theGoogle's Gemini API to generate a completion using the specified model.

    Args:
        query (str): The query to be sent to the Claude API.
        ai_object (str): The object to be processed by the Claude API.
        item (str): The name of the object.

    Returns:
        None: This function does not return anything.
    """
    genai = import_optional("google-genai", "google.genai")
    if genai is None:
        message = f"Module 'google-genai' not found. Install it with: {AI_EXTRA_INSTALL_COMMAND}"
        raise MapTaskerError(message, 12, show_code=False)
    client = genai.Client(api_key=state.program_arguments.ai_apikey)
    process_ai_query_and_response(client, query, ai_object, item, state=state)


# Determine the Tasker single-named object name (Task, Profile or Project) and item name.
def get_ai_object() -> tuple[str, str]:
    """
    Determine the Tasker single-named object name (Task, Profile, Project or Scene) and
    item name.

    Returns:
        tuple: A tuple containing the AI object type and its name.
    """
    return get_single_item_requested()


# Default AI prompt..
AI_PROMPT = "Analyze the following Tasker data"


def _no_ai_selected(*_args: object, **_kwargs: object) -> None:
    """Stand in for the analysis when the model chosen names no provider."""
    message = "Invalid model selected (AI name is blank)."
    raise MapTaskerError(message, 12)


async def _run_analysis_in_background(popup: object, state: RunState) -> None:
    """
    This function contains the main analysis logic, now asynchronous
    to prevent blocking the NiceGUI event loop.
    """
    try:
        # 1. Gather data quickly on the main thread
        temp_output = cleanup_output(state=state)
        ai_object, item = get_ai_object()

        prompt = state.program_arguments.ai_prompt if state.program_arguments.ai_prompt else AI_PROMPT
        if not prompt.endswith(":"):
            prompt = f"{prompt}:"
        query = f"Given the following {ai_object} in Tasker, an Android automation tool, {prompt}"
        for line in temp_output:
            query += f"{line}\n"

        console.say(
            f"MapTasker analysis for {ai_object} '{item}' is running in the background.  Please wait...",
        )

        name_function_map = {
            "OpenAI": open_ai,
            "Anthropic": claude_ai,
            "Gemini": gemini_ai,
            "LLAMA": local_ai,
        }
        ai_name = state.program_arguments.ai_name

        # Get the targeted worker function
        ai_func = name_function_map.get(ai_name, _no_ai_selected)

        # Use NiceGUI's run.io_bound to run the AI function in a separate thread so it doesn't block the main event
        # loop.  In this way, the popup window can be displayed while the AI processing is happening in the background.
        # The delay is to give the popup window time to display before the AI processing starts, so the user sees the
        # "Please wait..." message.
        # Nothing to check for None here: this call returns nothing, so nicegui's cancelled-wait
        # answer and its ordinary one are the same value (see nicegui.run._run).
        await run.io_bound(ai_func, query, ai_object, item, state=state)

        console.say(f"MapTasker analysis for {ai_object} '{item}' is done.")

    finally:
        # 3. Resume main thread operations securely
        state.program_arguments.ai_analyze = False

        # Remove the popup window using NiceGUI syntax
        if popup:
            # The dialog itself, or something that holds it (the AI popup used to be a wrapper).
            closer = getattr(popup, "close", None) or getattr(getattr(popup, "dialog", None), "close", None)
            if closer:
                closer()


# Map Ai: set up Ai query and call appropriate function based on the model.
async def map_ai(state: RunState) -> None:
    """
    A function that determines whether to call the OpenAI or local AI routine based on the model specified in PrimeItems.

    Does the setup for the query by concatenating the lines in PrimeItems.ai["output_lines"].
    """
    # Create the dialog container on the main thread
    dialog = create_popup_window(
        translate_string("MapTasker Analysis >>>>>>>>>> Please stand by..."),
        translate_string(
            "Analysis is running in the background.\n\nOnce complete, the results will appear in a new window.\n\nPlease stand by...",
        ),
    )

    # Instead of a ui.timer fire-and-forget loop, await the background processing task cleanly!
    await _run_analysis_in_background(dialog, state=state)
