"""Handler the GUI for MapTasker"""
#! /usr/bin/env python3

#                                                                                      #
# rungui: process GUI for MapTasker                                                    #
#                                                                                      #
# Add the following statement (without quotes) to your Terminal Shell config file.     #
#  (BASH, Fish, etc.) to eliminate the runtime msg:                                    #
#  DEPRECATION WARNING: The system version of Tk is deprecated ...                     #
#  "export TK_SILENCE_DEPRECATION = 1"                                                 #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
from __future__ import annotations

import contextlib
import os

from maptasker.src.colrmode import set_color_mode
from maptasker.src.error import error_handler
from maptasker.src.getputer import save_restore_args
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.maputils import exit_program
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import ARGUMENT_NAMES, logger

# Define the output file for the trace log

TRACE_LOG_FILE = "trace_log.txt"

# Flag to indicate when to start tracing
start_tracing = False

# Function to clear the log file at the start (optional)
if os.path.exists(TRACE_LOG_FILE):
    os.remove(TRACE_LOG_FILE)


def my_trace_function(frame, event, arg):
    """
    Custom trace function that logs execution details.
    """
    global start_tracing

    # Only start logging if the 'start_tracing' flag is True
    if not start_tracing:
        return my_trace_function  # Keep the trace function active but don't log yet

    # Get relevant information from the frame
    co = frame.f_code
    filename = co.co_filename
    lineno = frame.f_lineno
    func_name = co.co_name

    # --- ADD THIS CHECK ---
    # Skip if the filename is not a regular file path (e.g., frozen modules, <string>, etc.)
    # Or if it refers to the trace function itself to avoid recursion
    if (
        not os.path.exists(filename)
        or not os.path.isfile(filename)
        or func_name == "my_trace_function"
        or filename == os.path.basename(__file__)
        or "<frozen" in filename
    ):  # Explicitly check for frozen modules
        return my_trace_function
    # --- END ADDITION ---

    log_message = ""
    if event == "line":
        # Get the line of code being executed
        try:
            with open(
                filename,
                encoding="utf-8",
            ) as f:  # Use the full filename here
                lines = f.readlines()
                current_line_code = (
                    lines[lineno - 1].strip()
                    if 0 <= lineno - 1 < len(lines)
                    else "<CODE NOT FOUND>"
                )
        except (OSError, UnicodeDecodeError) as e:
            # Handle potential file access or decoding errors gracefully if they slip past the initial check
            current_line_code = f"<ERROR READING CODE: {e}>"
            # You might want to log this error to a separate debug log
            # print(f"Warning: Could not read source for {filename}:{lineno} - {e}", file=sys.stderr)

        log_message = f"LINE: {os.path.basename(filename)}:{lineno} {func_name}() - {current_line_code}"
    elif event == "call":
        log_message = f"CALL: {os.path.basename(filename)}:{lineno} Entering function: {func_name}()"
    elif event == "return":
        log_message = f"RETURN: {os.path.basename(filename)}:{lineno} Exiting function: {func_name}() (Returned: {arg})"
    elif event == "exception":
        exc_type, exc_value, _ = arg
        log_message = f"EXCEPTION: {os.path.basename(filename)}:{lineno} {func_name}() - {exc_type.__name__}: {exc_value}"

    if log_message:
        with open(TRACE_LOG_FILE, "a") as f:
            f.write(log_message + "\n")

    # Important: The trace function must return itself (or another trace function)
    # to continue tracing in the current or new scope.
    return my_trace_function


# ################################################################################
# Convert a value to integere, and if not an integer then use default value
# ################################################################################
def convert_to_integer(value_to_convert: str, default_value: int) -> int:
    """
    Convert a value to integere, and if not an integer then use default value
        Args:
            value_to_convert (str): The string value to convert to an integer
            where_to_put_it (int): Where to place the converted integer
            default_value (int): The default to plug in if the value to convert
                is not an integer
            :return: converted value as integer"""
    try:
        return int(value_to_convert)
    except (ValueError, TypeError):
        return default_value


# Get the colors to use.
def do_colors(user_input: dict) -> dict:
    """Sets color mode and processes colors.
    Parameters:
        - user_input (dict): User input dictionary containing appearance mode and color lookup.
    Returns:
        - colormap (dict): Dictionary of colors after processing.
    Processing Logic:
        - Set color mode based on user input.
        - Process color lookup if provided.
        - Set flag for GUI usage."""

    # Appearance change: Dark or Light mode?
    colormap = set_color_mode(user_input.appearance_mode)

    # Process the colors
    if user_input.color_lookup:
        for key, value in user_input.color_lookup.items():
            colormap[key] = value

    PrimeItems.program_arguments["gui"] = True  # Set flag to indicate we are using GUI

    return colormap


# Get the program arguments from GUI
def process_gui(use_gui: bool) -> tuple[dict, dict]:
    # global MyGui
    """Parameters:
        - use_gui (bool): Flag to indicate whether to use GUI or not.
    Returns:
        - tuple[dict, dict]: Tuple containing program arguments and colors to use.
    Processing Logic:
        - Import MyGui if use_gui is True.
        - Set flag to indicate GUI usage.
        - Delete previous Tkinter window if it exists.
        - Display GUI and get user input.
        - Initialize runtime arguments if not already set.
        - If user clicks "Exit" button, save settings and exit program.
        - If user closes window, cancel program.
        - If user clicks "Run" button, get input from GUI variables.
        - Set program arguments in dictionary.
        - Convert display_detail_level and indent to integers.
        - Get font from GUI.
        - Return program arguments and colors to use."""
    # CODE STARTS HERE
    logger.info("starting")
    # Keep this here to avoid circular import
    if use_gui:
        import linecache
        import sys

        from maptasker.src.userintr import MyGui

    PrimeItems.program_arguments["gui"] = True  # Set flag to indicate we are using GUI

    # Get rid of any previous Tkinter window
    if PrimeItems.tkroot is not None:
        del PrimeItems.tkroot
        PrimeItems.tkroot = None
    # Display GUI and get the user input
    user_input = MyGui()
    logger.info("Starting mainloop")
    # breakpoint()
    # --- Start Tracing Here ---
    global start_tracing
    start_tracing = True
    sys.settrace(my_trace_function)  # Activate the trace function

    linecache.clearcache()
    user_input.mainloop()
    # Get rid of window
    MyGui.quit(user_input)
    del MyGui

    # Establish our runtime default values if we don't yet have 'em.
    if not PrimeItems.colors_to_use:
        PrimeItems.program_arguments = initialize_runtime_arguments()

    # Has the user closed the window?
    if not user_input.go_program and not user_input.rerun and not user_input.exit:
        error_handler("Program canceled by user (killed GUI)", 100)

    # 'Run' button hit.  Get all the input from GUI variables
    PrimeItems.program_arguments["gui"] = True
    # Do we already have the file object?
    if value := user_input.file:
        PrimeItems.file_to_get = value if isinstance(value, str) else value.name

    # Hide the Ai key so when settings are saved, it isn't written to toml file.
    if user_input.ai_apikey is not None and user_input.ai_apikey:
        PrimeItems.ai["api_key"] = user_input.ai_apikey
        PrimeItems.program_arguments["ai_apikey"] = "HIDDEN"

    # Get the program arguments and save them in our dictionary
    for value in ARGUMENT_NAMES:
        with contextlib.suppress(AttributeError):
            PrimeItems.program_arguments[value] = getattr(user_input, value)
            logger.info(
                f"GUI arg: {value} set to: {PrimeItems.program_arguments[value]}",
            )

    # Convert display_detail_level to integer
    PrimeItems.program_arguments["display_detail_level"] = convert_to_integer(
        PrimeItems.program_arguments["display_detail_level"],
        4,
    )
    # Convert indent to integer
    PrimeItems.program_arguments["indent"] = convert_to_integer(
        PrimeItems.program_arguments["indent"],
        4,
    )
    # Get the font
    if the_font := user_input.font:
        PrimeItems.program_arguments["font"] = the_font

    # If user selected the "Exit" button, call it quits.
    if user_input.exit:
        # Save the runtijme settings first.
        _, _ = save_restore_args(
            PrimeItems.program_arguments,
            PrimeItems.colors_to_use,
            True,
        )
        # Spit out the message and log it.
        error_handler("Program exited. Goodbye.", 0)

        # Call it quits.
        exit_program(0)

    # Return the program arguments and colors to use.
    return (PrimeItems.program_arguments, do_colors(user_input))
