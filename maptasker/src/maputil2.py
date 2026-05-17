#! /usr/bin/env python3
"""

 maputil2: General and GUI utilities.

These are functions pulled out of maputils, guiwins and guiutils that would otherwise cause a circular
import error.

"""

import contextlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Generator
from contextlib import contextmanager
from tkinter import TclError

import customtkinter as ctk
import pygixml
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


def ensure_and_import(pypi_name: str, import_path: str) -> object:
    """
    Determine if a module is available, and if not, install it and then import it.
    Supports standard pip and uv-managed environments.
    Returns None if the module cannot be installed or imported.
    """
    # 1. Attempt to import if already present
    try:
        return importlib.import_module(import_path)
    except ImportError:
        pass

    print(f"MapTasker: --- Package {import_path} not found. Preparing installation... ---")

    # 2. Determine the installer command
    # Check if uv is available and if we are in a uv-managed env or if pip is missing
    has_uv = shutil.which("uv") is not None

    # Try to see if 'pip' module exists in the current sys.executable
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"], capture_output=True, check=True)
        use_uv = False
    except (subprocess.CalledProcessError, FileNotFoundError):
        use_uv = has_uv  # Use uv if pip failed but uv exists

    # Construct the command
    if use_uv:
        # 'uv pip install' targets the active virtualenv by default
        cmd = ["uv", "pip", "install", pypi_name]
        print(f"MapTasker: --- Using uv to install {pypi_name} ---")
    else:
        cmd = [sys.executable, "-m", "pip", "install", pypi_name]
        print(f"MapTasker: --- Using pip to install {pypi_name} ---")

    # 3. Execution
    try:
        subprocess.check_call(  # noqa: S603
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )

        importlib.invalidate_caches()

        # 4. Final Import
        return importlib.import_module(import_path)

    except (subprocess.CalledProcessError, ImportError) as e:
        print(f"MapTasker: --- Failed to provide Package {import_path}: {e} ---")
        return None


def find_first_tag_by_value(node: pygixml.XMLNode, tag_name: str, the_arg: str) -> pygixml.XMLNode | None:
    """
    Traverses the tree to find the first node with a specific tag name
    and a specific value.
    Parameters:
        node: The current XML node being inspected.
        tag_name: The name of the tag to search for.
        the_arg: The value to match against the node's child value.
    Returns:
        The first XML node that matches the specified tag name and value, or None if no match is found.
    """
    # Standardize comparison value
    target_val = str(the_arg)

    # 1. Check if the current node matches both the tag name and the value
    if isinstance(node, pygixml.XMLNode) and node.name == tag_name and node.child_value() == target_val:
        return node
    if isinstance(node, str):
        return find_first_stringtag_by_value(node, the_arg)

    # 2. Recursively search children
    for child in node.children():
        result = find_first_tag_by_value(child, tag_name, the_arg)

        # 3. Short-circuit: return as soon as the first match is found
        if result:
            return result

    return None


def find_first_stringtag_by_value(xml_string: str, tag_name: str) -> dict | None:
    """
    Parses an XML string and returns a dictionary containing the 'tag' and 'value'
    of the FIRST element matching the specified tag_name. Returns None if no match is found.
    """
    # Parse the string into a pygixml document
    # FIX THIS doesn't work for shit.
    doc = pygixml.parse_string(xml_string)

    # Use XPath to find the first element matching the given tag name
    xpath_query = f"//*[local-name()='{tag_name}']"
    match = doc.select_node(xpath_query)

    # If no matching element exists, return None
    if not match:
        return None

    node = match.node

    # Extract internal text value
    text_value = node.child_value()

    # Fallback: If the tag is self-closing but has a 'val' attribute (like <Int val="30" />)
    if not text_value and node.attribute("val"):
        text_value = node.attribute("val").value

    return {"tag": node.name, "value": text_value}


def get_xml_value(node: str, tag_name: str) -> str:
    """
    Retrieves the value of the first child node with a specific tag name.
    Parameters:
        node: The current XML node being inspected.
        tag_name: The name of the tag to search for.
    Returns:
        The value of the first child node that matches the specified tag name, or an empty string if no match is found.
    """
    # Parse the XML string
    if not isinstance(node, str):
        node = node.xml
    doc = pygixml.parse_string(node)

    # If the tag_name is 'sr', then we need the attribute value since 'sr' isn't <sr>'
    if tag_name == "sr":
        return doc.root.attribute("sr").value

    # Get the <tag_name> element's text content
    the_element = doc.root.select_node(tag_name)

    # Return its text content
    if the_element is not None:
        return the_element.node.value

    # 2. If no matching child is found, return an empty string
    return ""
