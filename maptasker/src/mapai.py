"""Ai Analysis Support
Take the Tasker object, ai model and key and feed it into the approiate AI service.
The response will be saved as a file, which will then be read in by userintr and displayed in a separate textbox
upon reinvocation of the application.
"""

import importlib.util
import os
import re
import sys

from nicegui import run

from maptasker.src.aiutils import get_api_key
from maptasker.src.error import error_handler
from maptasker.src.guiwins import create_popup_window
from maptasker.src.guiwins import create_popup_window as popupwindow
from maptasker.src.maputil2 import translate_string
from maptasker.src.maputil3 import ensure_and_import
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import (
    ANALYSIS_FILE,
    DEEPSEEK_MODELS,
    ERROR_FILE,
    KEYFILE,
)
from maptasker.src.xmldata import remove_html_tags

ai_role = "You are a Tasker programmer on Android"


# Validate OpenAI API key
def valid_api_key(ai: str, api_key: str) -> bool:
    """
    Validate the length/value of the provided API key.  This can only work for OpewnAI and antrhopic, since DeepSeek doesn't
    have a specific API key format, and the only way to validate is to make an API call and see if it works.

    Args:
        ai (str): The AI service to validate the API key for.
        api_key (str): The AI API key to validate.

    Returns:
        bool: True if the API key is valid, False otherwise.
    """
    if ai == "openai_key":
        try:
            # 1. Dynamically get the 'openai' module
            openai_lib = ensure_and_import("openai", "openai")
            if openai_lib is None:
                return False

            # 2. Extract the specific classes needed
            OpenAI = openai_lib.OpenAI  # noqa: N806
            OpenAIError = openai_lib.OpenAIError  # noqa: N806
            try:
                client = OpenAI(api_key=api_key)
                client.models.list()
                return True  # noqa: TRY300
            except OpenAIError:
                return False
        except Exception as e:  # noqa: BLE001
            print(f"Error importing OpenAI: {e}")
            return False

    elif ai == "anthropic_key":
        try:
            anthropic = ensure_and_import("anthropic", "anthropic")
            if anthropic is None:
                return False

            client = anthropic.Anthropic(api_key=api_key)
            client.models.list()
            return True  # noqa: TRY300
        except anthropic.AnthropicError:
            return False

    elif ai == "gemini_key":
        # Regex: Starts with AIzaSy, followed by 33 characters (total 39)
        pattern = r"^AIzaSy[A-Za-z0-9_-]{33}$"
        return bool(re.match(pattern, api_key))

    else:
        # Validate DeepSeek API key.
        expected_length = 32
        pattern = r"^[a-zA-Z0-9_-]{32}$"

        # Check if the API key matches the expected length and pattern
        return bool(len(api_key) == expected_length and re.match(pattern, api_key))


# Determine if a module is available or not.
def module_is_available(module_name: str) -> bool:
    """
    Check if a module is available or not.

    Args:
        module_name (str): The name of the module to check.

    Returns:
        bool: True if the module is available, False otherwise.

    This function checks if a module is already imported or if it can be imported using the `importlib.util.find_spec` function. If the module is already imported, it returns True. If the module can be imported, it imports the module using `importlib.util.module_from_spec` and `spec.loader.exec_module`, adds it to the `sys.modules` dictionary, and returns True. If the module cannot be imported, it returns False.
    """
    if module_name in sys.modules:
        return True
    if (spec := importlib.util.find_spec(module_name)) is not None:
        # If you chose to perform the actual import ...
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return True
    # Load the module dynamically.
    if spec is None:
        _kaka = ensure_and_import(module_name, module_name)
        return _kaka is not None  # Return boolean indicating if the module was successfully imported.

    return False


# Clean up the output list since it has all the front matter and we only need
# the object (Project/Profile/Task)
def cleanup_output() -> list:
    """
    A function that cleans up the output list in prepartion of the query.

    Returns:
        list: The cleaned up output list.
    """
    # Delete everything up to the Profile.
    temp_output = []
    got_it = False
    for line in PrimeItems.output_lines.output_lines:
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
            temp_line = remove_html_tags(temp_line, "")
            temp_output.append(temp_line)

    return temp_output


# Record the response to the analysis logs.
def record_response(response: str, ai_object: str, item: str) -> None:
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
    with open(ANALYSIS_FILE, "w") as response_file:
        response_file.write(
            f'{PrimeItems.program_arguments["ai_name"]} AI Response using model {PrimeItems.program_arguments["ai_model"]} for {ai_object} "{item}":\n\n{response}',
        )
    # Queue up the message to display in the GUI textbox.
    analysis_file_name = ANALYSIS_FILE.split(".")
    process_error(
        f"{response}\n\nAnalysis Response saved in file: {analysis_file_name[0]}-date-time.{analysis_file_name[1]}",
        ai_object,
        item,
    )


# Do local Ai processing.
def local_ai(query: str, ai_object: str, item: str) -> None:
    """
    Perform local AI processing on the given query.

    Args:
        query (str): The query to be processed by the local AI model.
        ai_objeect (str): The object to be processed by the local AI model.
        item (str): the object's name

    Returns:
        None: This function does not return anything.

    Description:
        This function performs local AI processing on the given query using the specified model.
        It opens the model using the `cria.Model` context manager and retrieves the response.
        It then iterates over the response and prints each chunk of the chat.
        Finally, it closes the model.

    Example:
        local_ai("What is the capital of France?")
        # Output: "Paris"
    """
    from maptasker.src import cria  # noqa: PLC0415

    # if PrimeItems.program_arguments["ai_analyze"] and not module_is_available("cria"):
    #     error_handler("Module 'cria' not found.  Please install the 'cria' module and the Ollama app.", 12)
    #     return

    # Fix the model name
    if PrimeItems.program_arguments["ai_model"] == "None":
        error_handler("No model selected.", 12)
        return

    print(f"Model: {PrimeItems.program_arguments['ai_model']}")
    # print(f"Query: {query}")

    # Prep the querey for the model.
    prompt = query.split(":", maxsplit=1)[0]  # Skip the first character, which is a colon.
    context = query.replace(prompt[1:], "")  # All of the Project/Profile/Task data
    # Set up the query
    messages = [
        {
            "role": "system",
            "content": f"You are a programmer using Tasker, and Android task management tool. The program code follows, with each line separated by '\n'. {prompt}:{context}",
        },
        {"role": "user", "content": context},
    ]
    response = ""
    # Make sure we don't come back if cria fails.
    PrimeItems.program_arguments["ai_analyze"] = False

    # Call Cria
    ai = cria.Cria()

    # Open the model and get the response
    try:
        with cria.Model(PrimeItems.program_arguments["ai_model"]) as ai:
            for chunk in ai.chat(messages=messages, prompt=prompt):
                response = f"{response}{chunk}"
            ai.clear()

        # Open error file, since we're going to queue up the response in this file for display back to the GUI.
        record_response(response, ai_object, item)

    except (FileNotFoundError, ValueError, TypeError, UnboundLocalError) as e:
        error_handler(
            f"Ai analysis error: {e}.  Try again.",
            12,
        )


# Handle ChatGPT Error
def process_error(error: str, ai_object: str, item: str) -> None:
    """
    Process errors based on the given error message and record the response.

    Args:
        error (str): The error message to be processed.
        ai_object (str): The object that caused the error.
        item (str): The item name that caused the error.

    Returns:
        None: This function does not return anything.
    """
    extra = ""
    if "Request too large" in error:
        output_error = f"{ai_object} too large for ChatGPT or ChatGPT quota not enough!\n\n"
    elif "'Incorrect API key provided" in error:
        output_error = "Invalid ChatGPT API key provided!\n\n"
    elif PrimeItems.program_arguments["ai_model"] in DEEPSEEK_MODELS and "Error code:" in error:
        if ": 401" in error:
            extra = "DeepSeek error code 401...possible invalid DeepSeek API key provided!\n\n"
        output_error = (
            f"{extra}Refer to DeepSeek error codes: https://api-docs.deepseek.com/quick_start/error_codes\n\n"
        )
    else:
        output_error = error

    # Write the error to the error file, which will be read in by guiutils and displayed in GUI text box.
    # Note: "Ai Response" must be a part of the message for it to be recognized by guiutils.
    with open(ERROR_FILE, "w") as error_file:
        error_file.write(
            f"'{PrimeItems.program_arguments['ai_name']} AI Response using model {PrimeItems.program_arguments['ai_model']} for {ai_object} {item}:\n\n{output_error}",
        )
    error_file.close()


def _process_openai_response(client: object, query: str) -> str:
    """Helper function to process OpenAI responses."""
    model = PrimeItems.program_arguments["ai_model"]
    role = ai_role
    roletype = "user" if "o1" in PrimeItems.program_arguments["ai_model"] else "system"
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


def _process_anthropic_response(client: object, query: str) -> str:
    """Helper function to process Anthropic (Claude) responses."""
    role = ai_role
    message = client.messages.create(
        model=PrimeItems.program_arguments["ai_model"],
        max_tokens=1024,
        messages=[
            {"role": "user", "content": f"{role} {query}"},
        ],
    )
    return message.content[0].text


def _process_deepseek_response(client: object, query: str) -> str:
    """Helper function to process DeepSeek responses."""
    model = PrimeItems.program_arguments["ai_model"]
    role = ai_role
    message = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": role},
            {"role": "user", "content": query},
        ],
        max_tokens=1024,
        temperature=0.0,  # Changed from 0.7 to 0.0 for more deterministic output.
        stream=False,
    )
    return message.choices[0].message.content


def _process_gemini_response(client: object, query: str) -> str:
    """Helper function to process Gemini responses."""
    model = PrimeItems.program_arguments["ai_model"]
    role = ai_role
    # Suppress logging warnings
    # message = client.GenerativeModel(model)
    # response1 = message.generate_content(role + query)
    response = client.models.generate_content(
        model=model,
        contents=f"{role}.  {query}",
        # NOTE: Need to add logic to determine specific model eligability for the following option.
        # config=types.GenerateContentConfig(thinking_config=types.ThinkingConfig(thinking_level="low")),
    )
    return response.text


def process_ai_query_and_response(
    client: object,
    query: str,
    ai_object: str,
    item: str,
) -> None:
    """
    Generic function to process AI responses from various AI services.

    Args:
        client: The AI client (OpenAI, Claude, DeepSeek, Gemini).
        query (str): The query to send to the AI.
        ai_object (str): The object being processed.
        item (str): The name of the object being processed.

    Returns:
        None: This function does not return anything.
    """
    name = PrimeItems.program_arguments["ai_name"]

    # Map AI names to their respective processing functions
    ai_processors = {
        "OpenAI": _process_openai_response,
        "Anthropic": _process_anthropic_response,
        "DeepSeek": _process_deepseek_response,
        "Gemini": _process_gemini_response,
    }

    try:
        process_function = ai_processors.get(name)
        if process_function:
            response = process_function(client, query)
            record_response(response, ai_object, item)
        else:
            error_handler("Invalid AI name selected.", 12)
    except Exception as e:  # noqa: BLE001
        error_message = handle_ai_error(e)  # Pass the exception object directly
        with open(ERROR_FILE, "w") as response_file:
            response_file.write(error_message)


def handle_ai_error(error: Exception) -> str:
    """
    Handles errors for AI processing.

    Args:
        error (Exception): The exception raised during processing.

    Returns:
        str: The formatted error message.
    """
    # Determine the AI being used.
    model = PrimeItems.program_arguments["ai_model"]
    ai = next(
        (
            name
            for name, models in {
                "OpenAI": PrimeItems.ai["openai_models"],
                "Anthropic": PrimeItems.ai["anthropic_models"],
                "DeepSeek": PrimeItems.ai["deepseek_models"],
                "Llama": PrimeItems.ai["llama_models"],
                "Gemini": PrimeItems.ai["gemini_models"],
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
        return (
            f"Invalid {ai} API key provided: key='{PrimeItems.program_arguments['ai_apikey']}' for model {model}!\n\n"
        )
    if "Connection error" in message:
        return "Connection Error: Check your firewall. If this is not the issue, try another Anthropic API key.  Also check out their 'Initial Setup' steps.\n\n"
    return f"{ai} failed with error: {error!s}"


def open_ai(query: str, ai_object: str, item: str) -> None:
    """
    Sends a query to the OpenAI API to generate a completion using the specified model.

    Args:
        query (str): The query to be sent to the OpenAI API.
        ai_object (str): The object to be processed by the OpenAI API.
        item (str): The name of the object.

    Returns:
        None: This function does not return anything.
    """
    if PrimeItems.program_arguments["ai_analyze"] and not module_is_available("openai"):
        error_handler(
            "Module 'openai' not found. Please install the 'openai' module.",
            12,
        )
        return

    api_key = (
        get_api_key
        if PrimeItems.program_arguments["ai_apikey"] == "Hidden" and os.path.isfile(KEYFILE)
        else PrimeItems.program_arguments["ai_apikey"]
    )
    # 1. Dynamically get the 'openai' module
    openai_lib = ensure_and_import("openai", "openai")
    if openai_lib is None:
        return

    # 2. Extract the specific classes needed
    OpenAI = openai_lib.OpenAI  # noqa: N806

    client = OpenAI(api_key=api_key)
    process_ai_query_and_response(client, query, ai_object, item)


def claude_ai(query: str, ai_object: str, item: str) -> None:
    """
    Sends a query to the Claude API to generate a completion using the specified model.

    Args:
        query (str): The query to be sent to the Claude API.
        ai_object (str): The object to be processed by the Claude API.
        item (str): The name of the object.

    Returns:
        None: This function does not return anything.
    """
    anthropic = ensure_and_import("anthropic", "anthropic")
    if anthropic is None:
        error_handler("Module 'anthropic' not found. Please install the 'anthropic' module.", 12)
        return
    client = anthropic.Anthropic(api_key=PrimeItems.program_arguments["ai_apikey"])
    process_ai_query_and_response(client, query, ai_object, item)


def deepseek_ai(query: str, ai_object: str, item: str) -> None:
    """
    Sends a query to the DeepSeek API to generate a completion using the specified model.

    Args:
        query (str): The query to be sent to the OpenAI API, pointing to deepseek.
        ai_object (str): The object to be processed by the OpenAI API.
        item (str): The name of the object.

    Returns:
        None: This function does not return anything.
    """
    # 1. Dynamically get the 'openai' module
    openai_lib = ensure_and_import("openai", "openai")
    if openai_lib is None:
        return

    # 2. Extract the specific classes needed
    OpenAI = openai_lib.OpenAI  # noqa: N806
    client = OpenAI(
        api_key=PrimeItems.program_arguments["ai_apikey"],
        base_url="https://api.deepseek.com",
    )
    process_ai_query_and_response(client, query, ai_object, item)


def gemini_ai(query: str, ai_object: str, item: str) -> None:
    """
    Sends a query to theGoogle's Gemini API to generate a completion using the specified model.

    Args:
        query (str): The query to be sent to the Claude API.
        ai_object (str): The object to be processed by the Claude API.
        item (str): The name of the object.

    Returns:
        None: This function does not return anything.
    """
    genai = ensure_and_import("google.genai", "google.genai")
    if genai is None:
        error_handler("Module 'google-genai' not found. Please install the 'google-genai' module.", 12)
        return
    client = genai.Client(api_key=PrimeItems.program_arguments["ai_apikey"])
    process_ai_query_and_response(client, query, ai_object, item)


# Determine the Tasker single-named object name (Task, Profile or Project) and item name.
def get_ai_object() -> tuple:
    """
    Determine the Tasker single-named object name (Task, Profile, or Project) and item name.

    Returns:
        tuple: A tuple containing the AI object type and its name.
    """
    options = {
        "single_task_name": "Task",
        "single_profile_name": "Profile",
        "single_project_name": "Project",
    }
    return next(
        ((obj, PrimeItems.program_arguments[key]) for key, obj in options.items() if PrimeItems.program_arguments[key]),
        ("", ""),
    )


# Default AI prompt..
AI_PROMPT = "Analyze the following Tasker data"


async def _run_analysis_in_background(popup: popupwindow) -> None:
    """
    This function contains the main analysis logic, now asynchronous
    to prevent blocking the NiceGUI event loop.
    """
    try:
        # 1. Gather data quickly on the main thread
        temp_output = cleanup_output()
        ai_object, item = get_ai_object()

        prompt = PrimeItems.program_arguments["ai_prompt"] if PrimeItems.program_arguments["ai_prompt"] else AI_PROMPT
        if not prompt.endswith(":"):
            prompt = f"{prompt}:"
        query = f"Given the following {ai_object} in Tasker, an Android automation tool, {prompt}"
        for line in temp_output:
            query += f"{line}\n"

        print(
            f"MapTasker analysis for {ai_object} '{item}' is running in the background.  Please wait...",
        )

        name_function_map = {
            "OpenAI": open_ai,
            "Anthropic": claude_ai,
            "DeepSeek": deepseek_ai,
            "Gemini": gemini_ai,
            "LLAMA": local_ai,
        }
        ai_name = PrimeItems.program_arguments["ai_name"]

        # Get the targeted worker function
        ai_func = name_function_map.get(
            ai_name,
            lambda *args: error_handler("Invalid model selected (AI name is blank).", 12),  # noqa: ARG005
        )

        # Use NiceGUI's run.io_bound to run the AI function in a separate thread so it doesn't block the main event
        # loop.  In this way, the popup window can be displayed while the AI processing is happening in the background.
        # The delay is to give the popup window time to display before the AI processing starts, so the user sees the
        # "Please wait..." message.
        await run.io_bound(ai_func, query, ai_object, item)

        print(f"MapTasker analysis for {ai_object} '{item}' is done.")

    finally:
        # 3. Resume main thread operations securely
        PrimeItems.program_arguments["ai_analyze"] = False

        # Remove the popup window using NiceGUI syntax
        if popup:
            if hasattr(popup, "close"):
                popup.close()
            elif hasattr(popup, "dialog") and hasattr(popup.dialog, "close"):
                popup.dialog.close()


# FIX Do we need to popup any messages to the user?  If so, we can do that here, but we need to make sure we don't block the main thread.
# def display_the_popup(title: str, text: str) -> None:
#     """
#     Displays a popup window telling user we are analyzing.
#     Calls _run_analysis_in_background via a one-time timer.
#     """
#     # Create and open the dialog using the helper
#     dialog = create_popup_window(title, text)

#     # ui.timer handles async functions natively when they are called
#     ui.timer(0.2, lambda: _run_analysis_in_background(dialog), once=True)


# Map Ai: set up Ai query and call appropriate function based on the model.
async def map_ai() -> None:
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
    await _run_analysis_in_background(dialog)
