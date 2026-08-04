#! /usr/bin/env python3
"""
guiutil2: General utilities (NiceGUI Version).
These are pure Python functions pulled out to avoid circular imports.
"""

import os

import requests

# import re
# import requests
from maptasker.src.config import INCLUDE_PROPORTIONAL_FONTS
from maptasker.src.error import rutroh_error
from maptasker.src.mapfonts import get_font_choices as get_font_selections
from maptasker.src.mapfonts import get_monospaced_fonts

# Define label fonts for headings (Replaced hardcoded pixel sizes with Tailwind text classes)
from maptasker.src.primitem import PrimeItems

# Define the output file for the trace log
TRACE_LOG_FILE = "trace_log.txt"
# Function to clear the log file at the start (optional)
if os.path.exists(TRACE_LOG_FILE):
    os.remove(TRACE_LOG_FILE)


# ==========================================
# PURE PYTHON UTILITIES (Keep your existing logic here)
# ==========================================


def sort_languages_with_priority(languages: list) -> list:
    """
    Sorts a list of languages, ensuring primary languages (like English)
    appear at the top of the dropdown.
    """
    # Keep your exact same sorting logic here!
    sorted_langs = sorted(languages)
    if "English" in sorted_langs:
        sorted_langs.remove("English")
        sorted_langs.insert(0, "English")
    return sorted_langs


def my_trace_function(frame, event, arg) -> None:  # noqa: ANN001
    """
    Custom trace function that logs execution details.

    Invoked with:
    import sys
    from maptasker.src.guiutil2 import my_trace_function
    if PrimeItems.program_arguments["debug"]:
            PrimeItems.trace = True
            sys.settrace(my_trace_function)
    """
    # Only start logging if the 'start_tracing' flag is True
    if not PrimeItems.trace:
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
                current_line_code = lines[lineno - 1].strip() if 0 <= lineno - 1 < len(lines) else "<CODE NOT FOUND>"
        except (OSError, UnicodeDecodeError) as e:
            # Handle potential file access or decoding errors gracefully if they slip past the initial check
            current_line_code = f"<ERROR READING CODE: {e}>"
            # You might want to log this error to a separate debug log
            rutroh_error(f"Warning: Could not read source for {filename}:{lineno} - {e}")

        log_message = f"LINE: {os.path.basename(filename)}:{lineno} {func_name}() - {current_line_code}"
    elif event == "call":
        log_message = f"CALL: {os.path.basename(filename)}:{lineno} Entering function: {func_name}()"
    elif event == "return":
        log_message = f"RETURN: {os.path.basename(filename)}:{lineno} Exiting function: {func_name}() (Returned: {arg})"
    elif event == "exception":
        exc_type, exc_value, _ = arg
        log_message = (
            f"EXCEPTION: {os.path.basename(filename)}:{lineno} {func_name}() - {exc_type.__name__}: {exc_value}"
        )

    if log_message:
        with open(TRACE_LOG_FILE, "a") as f:
            f.write(log_message + "\n")

    # Important: The trace function must return itself (or another trace function)
    # to continue tracing in the current or new scope.
    return my_trace_function


def get_changelog_file(url: str, delimiter: str, n: int) -> list:
    """
    Fetches a text file from a URL and returns a list of lines until the nth
    occurrence of a specified delimiter is encountered.

    Args:
        url (str): The URL of the text file.
        delimiter (str): The string to count occurrences of (e.g., "##").
        n (int): The nth occurrence of the delimiter to stop at.

    Returns:
        list: A list of text lines up to (but not including) the line
              where the nth occurrence of the delimiter is found.
              Returns an empty list if the URL is invalid or the delimiter
              is not found 'n' times.
    """
    if n <= 0:
        rutroh_error(f"Invalid integer value for n: {n!s}")
        return []

    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
    except requests.exceptions.RequestException as e:
        rutroh_error(f"Error fetching the URL: {e}")
        return []

    lines = []
    delimiter_count = 0

    # Decode the content and split into lines
    text_content = response.text
    for line in text_content.splitlines():
        if line.startswith(f"{delimiter} "):
            delimiter_count += 1
        if delimiter_count == n:
            break  # Stop when the nth occurrence is found
        lines.append(line)

    return lines


def get_monospace_fonts() -> list[str]:
    """Queries the OS font files to retrieve the available monospaced fonts."""
    try:
        # mapfonts reads the installed font files directly and supplies its own
        # fallback list if none of them turn out to be monospaced.
        return get_monospaced_fonts()
    except Exception as e:  # noqa: BLE001
        rutroh_error(f"Unable to retrieve the system monospaced fonts: {e}")
        return ["Courier New", "Courier"]


def get_font_choices() -> dict[str, str]:
    """Returns the {font name: label to show} choices for the GUI's font pulldown.

    Which fonts are offered is governed by config.INCLUDE_PROPORTIONAL_FONTS.
    """
    try:
        return get_font_selections(INCLUDE_PROPORTIONAL_FONTS)
    except Exception as e:  # noqa: BLE001
        rutroh_error(f"Unable to retrieve the system fonts: {e}")
        return {"Courier New": "Courier New", "Courier": "Courier"}
