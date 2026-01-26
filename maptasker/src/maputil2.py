#! /usr/bin/env python3
"""

 maputil2: General and GUI utilities.

These are functions pulled out of maputils, guiwins and guiutils that would otherwise cause a circular
import error.

"""

import contextlib
import os
import re
import sys
from collections.abc import Generator
from contextlib import contextmanager
from tkinter import TclError

import customtkinter as ctk
import requests
from requests.exceptions import ConnectionError, InvalidSchema, Timeout  # noqa: A004

from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import MY_VERSION, NOW_TIME, logger, logging
from maptasker.src.translator import T


def strip_html_tags(text: str) -> str:
    """Removes all HTML tags from a given string.

    Args:
      text: The input string containing HTML tags.

    Returns:
      A string with all HTML tags removed.
    """
    return re.sub(r"<[^>]+>", "", text)


def truncate_string(text: str, max_length: int = 30) -> str:
    """Truncates a string to a specified maximum length.

    Args:
      text: The input string.
      max_length: The maximum number of characters to keep (default is 30).

    Returns:
      The truncated string. If the original string is shorter than or equal to
      max_length, it is returned unchanged. If it's longer, it's truncated and
      an ellipsis (...) is added to the end.
    """
    if len(text) <= max_length:
        return text

    return text[:max_length].rstrip() + "..."


# Set up logging
def setup_logging() -> None:
    """
    Set up the logging: name the file and establish the log type and format
    """
    # Add the date and time to the log filename.
    file_name = f"maptasker_{NOW_TIME.month}-{NOW_TIME.day}-{NOW_TIME.year}_{NOW_TIME.hour}-{NOW_TIME.minute}-{NOW_TIME.second}.log"
    logging.basicConfig(
        filename=file_name,
        filemode="w",
        format="%(asctime)s,%(msecs)d %(levelname)s %(name)s %(funcName)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.DEBUG,
    )
    logger.info(sys.version_info)


# Log the arguments
def log_startup_values() -> None:
    """
    Log the runtime arguments and color mappings
    """
    setup_logging()  # Get logging going
    logger.info(f"{MY_VERSION} {str(NOW_TIME)}")  # noqa: RUF010
    logger.info(f"sys.argv:{str(sys.argv)}")  # noqa: RUF010
    for key, value in PrimeItems.program_arguments.items():
        logger.info(f"{key}: {value}")
    for key, value in PrimeItems.colors_to_use.items():
        logger.info(f"colormap for {key} set to {value}")


def store_windows(self: ctk) -> None:
    """
    Stores the positions of all of our windows.

    This function saves the positions of the various windows using the `save_window_position()` function.

    Returns:
        None
    """
    windows = {
        "ai_analysis_window": "ai_analysis_window_position",
        "treeview_window": "tree_window_position",
        "diagramview_window": "diagram_window_position",
        "mapview_window": "map_window_position",
        "progressbar_window": "progressbar_window_position",
        "apikey_window": "ai_apikey_window_position",
        "miscview_window_position": "misc_window_position",
        "self": "window_position",
    }

    with contextlib.suppress(AttributeError):
        _save_window_position = save_window_position
        for window_attr, position_attr in windows.items():
            window_obj = getattr(self, position_attr, None)
            # Get the window position if a valid window.
            if window_obj and (window_pos := _save_window_position(self, window_attr)):
                setattr(self, position_attr, window_pos)


# Save the position of a window
def save_window_position(self: ctk, window_name: str) -> None:
    """
    Saves the window position by getting the geometry of the window.

    Args:
        self: The MyGui object.
        window_name: The name of the window to save the position of.

    Returns:
        window position or "" if no window
    """
    # Check to see if it our main window
    if window_name == "self":
        return self.wm_geometry()

    # Process other windows.)
    window_object = getattr(self, window_name, None)

    if window_object is not None and hasattr(window_object, "wm_geometry"):
        # Capture the situation in which the window has been closed already, causing a tclerror.
        try:
            return window_object.wm_geometry()
        except TclError:
            return ""
    return ""


def translate_string(text: str, set_language: bool = False) -> str:
    """
    Translates a given string using PrimeItems._ if available. and sets the language if requested.

    Args:
        text: The input string to be translated.
    Returns:
        The translated string if PrimeItems._ is available, otherwise the original string.
    """
    # If we have a language set, then translate the test
    if text:
        if hasattr(PrimeItems, "_"):
            # If we are to set the language, then first translate it and then set it.
            if set_language:
                lang_to_set = PrimeItems._(text) if text not in PrimeItems.languages else text
                T.set_language(lang_to_set)
                # Set/reset "No Profile" string length in new language.
                no_profile_text = PrimeItems._("No Profile")
                PrimeItems.no_profile_translated_length = len(no_profile_text)
            return PrimeItems._(text)

        # If this is a language, then set the language and translate the text.
        if text in PrimeItems.languages and set_language:
            T.set_language(text)
            return PrimeItems._(text)
    return text


@contextmanager
def suppress_stdout() -> Generator:  # type: ignore  # noqa: PGH003
    """
    Context manager that suppresses the standard output during its execution.

    This context manager redirects the standard output to `/dev/null`, effectively suppressing any output.
    It uses the `open` function to open `/dev/null` in write mode and assigns it to the `devnull` variable.
    Then, it saves the current standard output in the `old_stdout` variable.
    After that, it sets the standard output to `devnull`.

    The `yield` statement is used to enter the context manager's block.
    Once the block is executed, the `finally` block is executed to restore the standard output to its original value.

    This context manager is useful when you want to suppress the standard output of a specific block of code."""
    with open(os.devnull, "w") as devnull:
        old_stdout = sys.stdout
        sys.stdout = devnull
        old_stderr = sys.stderr
        sys.stderr = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr


# Issue HTTP Request to get something from the Android device.
def http_request(
    ip_address: str,
    ip_port: str,
    file_location: str,
    request_name: str,
    request_parm: str,
) -> tuple[int, object]:
    """
    Issue HTTP Request to get the backup XML file from the Android device.
    Tasker's HTTP Server Example must be installed for this to work:
    https://taskernet.com/shares/?user=AS35m8ne7oO4s%2BaDx%2FwlzjdFTfVMWstg1ay5AkpiNdrLoSXEZdFfw1IpXiyJCVLNW0yn&id=Project%3AHttp+Server+Example
        :param backup_file_http: the port to use for the Android device's Tasker server
        :param backup_file_location: location of
        :return: return code, response: eitherr text string with error message or the
        contents of the backup file
    """
    # Create the URL to request the backup xml file from the Android device running the
    # Tasker server.
    # Something like: 192.168.0.210:1821/file/path/to/backup.xml?download=1
    http = "http://" if "http://" not in ip_address else ""
    url = f"{http}{ip_address}:{ip_port}/{request_name}{file_location}{request_parm}"

    # Make the request.
    error_message = ""
    response = ""

    with suppress_stdout():  # Suppress any errors (system IMK)
        try:
            response = requests.get(url, timeout=5)
        except InvalidSchema:
            error_message = f"Request failed for url: {url} .  Invalid url!"
        except ConnectionError:
            error_message = f"Request failed for url: {url} .  Connection error! Unable to get XML from Android device."
        except Timeout:
            error_message = f"Request failed for url: {url} .  Timeout error.  Or perhaps the profile 'MapTasker List' has not been imported into Tasker on the Android device!"
        except Exception as e:  # noqa: BLE001
            error_message = f"Request failed for url: {url}, error: {e} ."

    # If we have an error message, return as error.
    if error_message:
        logger.debug(error_message)
        return 8, error_message

    # Check the response status code.  200 is good!
    if response and response.status_code == 200:
        # Return the contents of the file.
        return 0, response.content

    if response and response.status_code == 404:
        return 6, "File " + file_location + " not found."

    return (
        8,
        f"Request failed for url: {url} ...with status code {response.status_code}",
    )
