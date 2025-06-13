"""Ai Analysis Support"""

#                                                                                      #
# mapai: Ai support                                                                    #
#                                                                                      #
import contextlib
import importlib.util
import os
import re
import sys

import anthropic
import google.generativeai as genai
from openai import OpenAI, OpenAIError

from maptasker.src import cria
from maptasker.src.config import AI_PROMPT
from maptasker.src.error import error_handler
from maptasker.src.guiutils import get_api_key
from maptasker.src.guiwins import PopupWindow
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import (
    ANALYSIS_FILE,
    CLAUDE_MODELS,
    DEEPSEEK_MODELS,
    ERROR_FILE,
    GEMINI_MODELS,
    KEYFILE,
    LLAMA_MODELS,
    OPENAI_MODELS,
)


# Validate OpenAI API key
def valid_api_key(ai: str, api_key: str) -> bool:
    """
    Validate the provided OpenAI API key.

    Args:
        ai (str): The AI service to validate the API key for.
        api_key (str): The OpenAI API key to validate.

    Returns:
        bool: True if the API key is valid, False otherwise.
    """
    if ai == "openai_key":
        try:
            client = OpenAI(api_key=api_key)
            client.models.list()
            return True  # noqa: TRY300
        except OpenAIError:
            return False

    elif ai == "claude_key":
        try:
            client = anthropic.Anthropic(api_key=api_key)
            client.models.list()
            return True  # noqa: TRY300
        except anthropic.AnthropicError:
            return False
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
    for line in PrimeItems.ai["output_lines"]:
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
    """

    with open(ANALYSIS_FILE, "w") as response_file:
        response_file.write(
            f'Ai Response using model {PrimeItems.program_arguments["ai_model"]} for {ai_object} "{item}":\n\n{response}',
        )
    # QAueue up the message to display in the GUI textbox.
    process_error(f"{response}\n\nAnalysis Response saved in file: " + ANALYSIS_FILE, ai_object, item)


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
    prompt = query.split(":")[0]  # Skip the first character, which is a colon.
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
            f'Ai Response using model {PrimeItems.program_arguments["ai_model"]} for {ai_object} {item}:\n\n{output_error}',
        )


def process_ai_query_and_response(
    client: object,
    query: str,
    ai_object: str,
    item: str,
) -> None:
    """
    Generic function to process AI responses from OpenAI or Claude.

    Args:
        client: The AI client (OpenAI or Claude).
        query (str): The query to send to the AI.
        ai_object (str): The object being processed.
        item (str): The name of the object being processed.

    Returns:
        None: This function does not return anything.
    """
    model = PrimeItems.program_arguments["ai_model"]
    role = "You are a Tasker programmer on Android"
    try:
        if model in OPENAI_MODELS:
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
            response = "".join(chunk.choices[0].delta.content or "" for chunk in stream_feed)
        elif model in CLAUDE_MODELS:
            message = client.messages.create(
                model=PrimeItems.program_arguments["ai_model"],
                max_tokens=1024,
                # temperature=0.7,
                messages=[
                    {"role": "user", "content": f"{role} {query}"},
                ],
            )
            response = message.content[0].text
        elif model in DEEPSEEK_MODELS:
            message = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": role},
                    {"role": "user", "content": query},
                ],
                max_tokens=1024,
                temperature=0.7,
                stream=False,
            )
            response = message.choices[0].message.content
        elif model in GEMINI_MODELS:
            # Suppress logging warnings
            message = client.GenerativeModel(model)
            response1 = message.generate_content(role + query)
            response = response1.text

        record_response(response, ai_object, item)
    # Handle all OpenAI API errors
    except OpenAIError as e:
        process_error(str(e), ai_object, item)
    except Exception as e:  # noqa: BLE001
        error_message = handle_ai_error(e)
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
                "OpenAI": OPENAI_MODELS,
                "Claude": CLAUDE_MODELS,
                "DeepSeek": DEEPSEEK_MODELS,
                "Llama": LLAMA_MODELS,
                "Gemini": GEMINI_MODELS,
            }.items()
            if model in models
        ),
        "Unknown",
    )

    # Capture the specific error message, if there is one.
    try:
        message = error.message
    except AttributeError:
        message = ""

    # Return the appropriate error message.
    if ai == "OpenAI":
        return f"OpenAI failed with error: {error!s}"
    if "invalid x-api-key" in str(error) or "API key not valid" in message:
        return (
            f"Invalid {ai} API key provided: key='{PrimeItems.program_arguments['ai_apikey']}' for model {model}!\n\n"
        )
    if "Connection error" in str(error):
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
        error_handler("Module 'openai' not found. Please install the 'openai' module.", 12)
        return

    api_key = (
        get_api_key
        if PrimeItems.program_arguments["ai_apikey"] == "Hidden" and os.path.isfile(KEYFILE)
        else PrimeItems.program_arguments["ai_apikey"]
    )
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
    client = anthropic.Anthropic(api_key=PrimeItems.program_arguments["ai_apikey"])
    process_ai_query_and_response(client, query, ai_object, item)


def deepseek_ai(query: str, ai_object: str, item: str) -> None:
    """
    Sends a query to the DeepSeek API to generate a completion using the specified model.

    Args:
        query (str): The query to be sent to the Claude API.
        ai_object (str): The object to be processed by the Claude API.
        item (str): The name of the object.

    Returns:
        None: This function does not return anything.
    """
    client = OpenAI(api_key=PrimeItems.program_arguments["ai_apikey"], base_url="https://api.deepseek.com")
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
    genai.configure(api_key=PrimeItems.program_arguments["ai_apikey"])
    process_ai_query_and_response(genai, query, ai_object, item)


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


# Map Ai: set up Ai query and call appropriate function based on the model.
def map_ai() -> None:
    """
    A function that determines whether to call the OpenAI or local AI routine based on the model specified in PrimeItems.

    Does the setup for the query by concatenating the lines in PrimeItems.ai["output_lines"].
    """
    # Display a popup window telling user we are analyzing
    popup = PopupWindow(
        title="MapTasker Analysis",
        message="Analysis is running in the background.  Please stand by...",
        exit_when_done=True,
        delay=500,
    )
    popup.mainloop()

    # Clean up the output list since it has all the front matter and we only need the object (Project/Profile/Task)
    temp_output = cleanup_output()

    # Save the ai popup window position
    with contextlib.suppress(AttributeError):
        PrimeItems.program_arguments["ai_popup_window_position"] = popup.ai_popup_window_position

    # Setup the query: ai_object (Task, Profile or Project) and item (name of the object)
    ai_object, item = get_ai_object()

    # Put the query together
    prompt = PrimeItems.program_arguments["ai_prompt"] if PrimeItems.program_arguments["ai_prompt"] else AI_PROMPT
    if not prompt.endswith(":"):
        prompt = f"{prompt}:"
    query = f"Given the following {ai_object} in Tasker, an Android automation tool, {prompt}"
    for line in temp_output:
        query += f"{line}\n"

    # Let the user know what is going on.
    print(f"MapTasker analysis for {ai_object} '{item}' is running in the background.  Please wait...")

    # Call appropriate AI routine: OpenAI or local Ollama
    model_function_map = {
        **{model: open_ai for model in OPENAI_MODELS},
        **{model: local_ai for model in LLAMA_MODELS},
        **{model: claude_ai for model in CLAUDE_MODELS},
        **{model: deepseek_ai for model in DEEPSEEK_MODELS},
        **{model: gemini_ai for model in GEMINI_MODELS},
    }
    model = PrimeItems.program_arguments["ai_model"]
    model_function_map.get(model, lambda *args: error_handler("Invalid model selected.", 12))(
        query,
        ai_object,
        item,
    )

    # We're done
    print(f"MapTasker analysis for {ai_object} '{item}' is done.")

    # Indicate that we are done
    PrimeItems.program_arguments["ai_analyze"] = False
