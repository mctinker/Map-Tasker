#! /usr/bin/env python3
"""

 maputil2: General and GUI utilities.

These are functions pulled out of maputils, guiwins and guiutils that would otherwise cause a circular
import error.

"""

import contextlib
import re
import sys
from tkinter import TclError

import customtkinter as ctk

from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import MY_VERSION, NOW_TIME, logger, logging


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
        for window_attr, position_attr in windows.items():
            window_obj = getattr(self, position_attr, None)
            # Get the window position if a valid window.
            if window_obj and (window_pos := save_window_position(self, window_attr)):
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
