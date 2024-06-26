"""Ai Analysis Support"""

#! /usr/bin/env python3

#                                                                                      #
# mapai: Ai support                                                                    #
#                                                                                      #
import contextlib
import importlib.util
import os
import sys

import cria
from openai import OpenAI, OpenAIError

from maptasker.src.config import AI_PROMPT
from maptasker.src.error import error_handler
from maptasker.src.guiutils import get_api_key
from maptasker.src.guiwins import PopupWindow
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import ANALYSIS_FILE, ERROR_FILE, KEYFILE, OPENAI_MODELS


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
    if PrimeItems.program_arguments["ai_analyze"] and not module_is_available("cria"):
        error_handler("Module 'cria' not found.  Please install the 'cria' module and the Ollama app.", 12)
        return

    # Fix the model name
    if PrimeItems.program_arguments["ai_model"] == "None":
        error_handler("No model selected.", 12)
        return

    # Open the model and get the response
    try:
        print(f"Model: {PrimeItems.program_arguments['ai_model']}")
        with cria.Model(PrimeItems.program_arguments["ai_model"]) as ai:
            response = ai.chat(query, stream=False)

        # Open error file, since we're going to queue up the response in this file for display back to the GUI.
        record_response(response, ai_object, item)

        # for chunk in response:
        #    print(chunk, end="")

        ai.close()  # Not required, but best practice.

    except (FileNotFoundError, ValueError):
        error_handler(
            f"Model {PrimeItems.program_arguments['ai_model']} not found.  Make sure 'Ollama' is installed and run once for the initial setup.  Then try again.",
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
    if "Request too large" in error:
        output_error = f"{ai_object} too large for ChatGPT or ChatGPT quota not enough!\n\n"
    elif "'Incorrect API key provided" in error:
        output_error = "Invalid ChatGPT API key provided!\n\n"
    else:
        output_error = error

    # Write the error to the error file, which will be read in by guiutils and displayed in GUI text box.
    # Note: "Ai Response" must be a part of the message for it to be recognized by guiutils.
    with open(ERROR_FILE, "w") as error_file:
        error_file.write(
            f'Ai Response using model {PrimeItems.program_arguments["ai_model"]} for {ai_object} {item}:\n\n{output_error}',
        )


# Do server-side ChatGPT Ai processing.
def server_openai(query: str, ai_object: str, item: str) -> None:
    """
    Sends a query to the OpenAI API to generate a completion using the specified model.

    Args:
        query (str): The query to be sent to the OpenAI API.
        ai_object (str): The object to be processed by the OpenAI API.
        item (str): the object's name

    Returns:
        None: This function does not return anything.
    """
    # Make sure openai is available.
    if PrimeItems.program_arguments["ai_analyze"] and not module_is_available("openai"):
        error_handler("Module 'cria' not found.  Please install the 'cria' module and Ollama.", 12)
        return

    # Get the api key
    if PrimeItems.program_arguments["ai_apikey"] == "Hidden" and os.path.isfile(KEYFILE):
        apikey = get_api_key  # Get the key from the file
    else:
        apikey = PrimeItems.program_arguments["ai_apikey"]

    # Set up the OpenAI client and send the query
    client = OpenAI(api_key=apikey)

    try:
        stream_feed = client.chat.completions.create(
            model=PrimeItems.program_arguments["ai_model"],
            messages=[{"role": "system", "content": "You are a Tasker programmer"}, {"role": "user", "content": query}],
            stream=True,
        )

        response = ""
        for chunk in stream_feed:
            response += chunk.choices[0].delta.content or ""
            # print(chunk.choices[0].delta.content or "", end="")
        # Open error file, since we're going to queue up the response in this file for display back to the GUI.
        record_response(response, ai_object, item)

    # Handle all OpenAI API errors
    except OpenAIError as e:
        process_error(str(e), ai_object, item)

    except Exception as e:  # noqa: BLE001
        # Open error file, since we're going to queue up the response in this file for display back to the GUI.
        with open(ERROR_FILE, "w") as response_file:
            response_file.write(f"OpenAi failed with error: {e!s}")


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
    got_profile = False
    for line in PrimeItems.ai["output_lines"]:
        if "Profile:" in line:
            got_profile = True
        if got_profile:
            # Ignore blank lines.
            if not line:
                continue
            # Quit if at end of Project.
            if "Tasks not in any Profile," in line:
                break
            temp_line = line.replace("&nbsp;", " ")
            temp_output.append(temp_line)

    return temp_output


# Map Ai: set up Ai query and call appropriate function based on the model.
def map_ai() -> None:
    """
    A function that determines whether to call the OpenAI or local AI routine based on the model specified in PrimeItems.

    Does the setup for the query by concatenating the lines in PrimeItems.ai["output_lines"].
    """
    # Display a popup window telling user we are analyzing
    popup = PopupWindow()
    popup.mainloop()

    # Clean up the output list since it has all the front matter and we only need the object (Project/Profile/Task)
    temp_output = cleanup_output()

    # Save the ai popup window position
    with contextlib.suppress(AttributeError):
        PrimeItems.program_arguments["ai_popup_window_position"] = popup.ai_popup_window_position

    # Setup the query
    if PrimeItems.program_arguments["single_project_name"]:
        ai_object = "Project"
        item = PrimeItems.program_arguments["single_project_name"]
    elif PrimeItems.program_arguments["single_profile_name"]:
        ai_object = "Profile"
        item = PrimeItems.program_arguments["single_profile_name"]
    elif PrimeItems.program_arguments["single_task_name"]:
        ai_object = "Task"
        item = PrimeItems.program_arguments["single_task_name"]

    # Put the query together
    prompt = PrimeItems.program_arguments["ai_prompt"] if PrimeItems.program_arguments["ai_prompt"] else AI_PROMPT
    if not prompt.endswith(":"):
        prompt = f"{prompt}:"
    query = f"Given the following {ai_object} in Tasker, {prompt}"
    for line in temp_output:
        query += f"{line}\n"

    # Let the user know what is going on.
    print(f"MapTasker analysis for {ai_object} '{item}' is running in the background.  Please wait...")

    # Call appropriate AI routine: OpenAI or local Ollama
    if PrimeItems.program_arguments["ai_model"] in OPENAI_MODELS:
        server_openai(query, ai_object, item)
    else:
        local_ai(query, ai_object, item)

    # Indicate that we are done
    PrimeItems.program_arguments["ai_analyze"] = False
