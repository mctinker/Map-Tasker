"""General Utilities"""

#! /usr/bin/env python3

#                                                                                      #
# maputils: General utilities used by program.                                         #
#                                                                                      #
from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from zoneinfo import (
    ZoneInfo,
    ZoneInfoNotFoundError,
)  # Import ZoneInfoNotFoundError for specific error handling

import defusedxml.ElementTree as et  # noqa: N813
import requests
from deep_translator import GoogleTranslator
from requests.exceptions import ConnectionError  # noqa: A004

from maptasker.src.error import rutroh_error
from maptasker.src.format import format_html
from maptasker.src.getbakup import write_out_backup_file
from maptasker.src.getids import get_ids
from maptasker.src.maputil2 import translate_string
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import FormatLine, logger, logging
from maptasker.src.taskerd import get_the_xml_data
from maptasker.src.xmldata import rewrite_xml


# Validate TCP/IP Address
def validate_ip_address(address: str) -> bool:
    """
    Validates an IP address.

    Args:
        address (str): The IP address to validate.

    Returns:
        bool: True if the IP address is valid, False otherwise.
    """
    try:
        ipaddress.ip_address(address)
    except ValueError:
        logger.debug(f"Invalid IP address: {address}")
        return False
    return True


# Validate Port Number
def validate_port(address: str, port_number: int) -> bool:
    """
    Validates a port number.

    Args:
        address (str): The address to connect to.
        port_number (int): The port number to validate.

    Returns:
        bool: True if the port number is valid, False otherwise.
    """
    if port_number.isdigit():
        port_int = int(port_number)
    else:
        return 1
    if port_int < 1024 or port_int > 65535:
        return 1
    if address:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_addr = (address, port_int)
        result = sock.connect_ex(server_addr)
        sock.close()
        return result
    return 0


# Auto Update our code
def update_maptasker() -> None:
    """Update this package using uv if available, otherwise fall back to pip."""
    version = get_pypi_version()  # Assuming this is defined elsewhere in your code
    packageversion = "maptasker" + version

    # 1. Check if 'uv' is installed and available on the system
    if shutil.which("uv"):
        # Build the command for uv
        # uv uses the syntax: uv pip install <package>
        command = ["uv", "pip", "install", packageversion, "--upgrade"]
        print("Updating with uv...")
    else:
        # Build the fallback command for pip
        command = [sys.executable, "-m", "pip", "install", packageversion, "--upgrade"]
        print("Updating with pip...")

    # 2. Execute the chosen command
    subprocess.call(command)  # noqa: S603


# Get the version of our code out on Pypi
def get_pypi_version() -> str:
    """Get the PyPi version of this package."""
    url = "https://pypi.org/pypi/maptasker/json"
    try:
        version = "==" + requests.get(url).json()["info"]["version"]  # noqa: S113
    except (json.decoder.JSONDecodeError, ConnectionError, Exception):  # noqa: BLE001
        logger.debug("Unable to get version from PYPI!")
        version = ""
    return version


# Validate XML
def validate_xml(
    ip_address: str,
    android_file: str,
    return_code: int,
    file_contents: str,
) -> tuple:
    # Run loop since we may have to rerun validation if unicode error
    """Validates an XML file and returns an error message and the parsed XML tree.
    Parameters:
        android_file (str): The path to the XML file to be validated.
        return_code (int): The return code from the validation process.
        file_contents (str): The contents of the XML file.
        ip_address (str): The TCP/IP address of the Android device or blank.
    Returns:
        error_message (str): A message describing any errors encountered during validation.
        xml_tree (ElementTree): The parsed XML tree if validation was successful.
    Processing Logic:
        - Runs a loop to allow for revalidation in case of a unicode error.
        - Sets the process_file flag to False to exit the loop if validation is successful or an error is encountered.
        - If validation is successful, sets the xml_tree variable to the parsed XML tree.
        - If an error is encountered, sets the error_message variable to a descriptive message and exits the loop.
        - If a unicode error is encountered, rewrites the XML file and loops one more time.
        - If any other error is encountered, sets the error_message variable to a descriptive message and exits the loop.
        - Returns the error_message and xml_tree variables."""
    process_file = True
    error_message = ""
    counter = 0
    xml_tree = None
    _write_out_backup_file = write_out_backup_file
    _get_the_xml_data = get_the_xml_data
    _rewrite_xml = rewrite_xml

    # Loop until we get a valid XML file or invalid XML
    while process_file:
        # Validate the file
        if return_code == 0:
            # Process the XML file
            PrimeItems.program_arguments["android_file"] = android_file

            # If getting file from Android device, write out the backup file first.
            if ip_address:
                _write_out_backup_file(file_contents)

            # We don't have the file yet.  Lets get it.
            else:
                return_code = _get_the_xml_data()
                if return_code != 0:
                    return PrimeItems.error_msg, None

            # Run the XML file through the XML parser to validate it.
            try:
                filename_location = android_file.rfind(PrimeItems.slash) + 1
                file_to_validate = PrimeItems.program_arguments["android_file"][filename_location:]
                xmlp = et.XMLParser(encoding=" iso8859_9")
                xml_tree = et.parse(file_to_validate, parser=xmlp)
                process_file = False  # Get out of while/loop
            except et.ParseError:  # Parsing error
                error_message = f"Improperly formatted XML in {android_file}. Try again."
                process_file = False  # Get out of while/loop
            except UnicodeDecodeError:  # Unicode error
                _rewrite_xml(file_to_validate)
                counter += 1
                if counter > 2:
                    error_message = f"Unicode error in {android_file}.  Try again."
                    break
                process_file = True  # Loop one more time.
            except Exception as e:  # any other errorError out and exit  # noqa: BLE001
                error_message = f"XML parsing error {e} in file {android_file}.\n\nTry again."
                process_file = False  # Get out of while/loop

    return error_message, xml_tree


# If we have set the single Project name due to a single Task or Profile name, then reset it.
def reset_named_objects() -> None:
    """_summary_
    Reset the single Project name if it was set due to a single Task or Profile name.
    Parameters:
        None
    Returns:
        None
    """
    # Check in name hierarchy: Task then Profile
    if PrimeItems.program_arguments["single_task_name"]:
        PrimeItems.program_arguments["single_project_name"] = ""
        PrimeItems.found_named_items["single_project_found"] = False
        PrimeItems.program_arguments["single_profile_name"] = ""
        PrimeItems.found_named_items["single_profile_found"] = False
    elif PrimeItems.program_arguments["single_profile_name"]:
        PrimeItems.program_arguments["single_project_name"] = ""
        PrimeItems.found_named_items["single_project_found"] = False
        PrimeItems.program_arguments["single_task_name"] = ""
        PrimeItems.found_named_items["single_task_found"] = False


# Count the number of consecutive occurrences of a substring within a main string.
def count_consecutive_substr(main_str: str, substr: str) -> int:
    """
    Count the maximum consecutive occurrences of 'substr' inside 'main_str'.
    Highly optimized: performs a single linear scan with no repeated .find() calls.
    """
    if not main_str or not substr:
        return 0

    sub_len = len(substr)
    max_count = 0
    count = 0

    i = 0
    end = len(main_str)

    while i <= end - sub_len:
        # Direct substring match without slicing
        if main_str.startswith(substr, i):
            count += 1
            i += sub_len
        else:
            max_count = max(max_count, count)
            count = 0
            i += 1

    return max(max_count, count)


def pretty(d: dict, indent: int = 0) -> None:
    """
    Print out a dictionary in a human-readable format.

    Args:
        d: The dictionary to print.
        indent: The number of tabs to indent the output with.
    """
    _pretty = pretty
    for key, value in d.items():
        print("\t" * indent + str(key))
        if isinstance(value, dict):
            _pretty(value, indent + 1)
        else:
            print("\t" * (indent + 1) + str(value))


def find_all_positions(string: str, substring: str, start_position: int = 0) -> list:
    """
    Finds all positions of a substring in a string.

    Args:
        string (str): The string to search in.
        substring (str): The substring to search for.
        start_position (int, optional): The position to start the search from. Defaults to 0.

    Returns:
        list: A list of all positions of the substring in the string.
    """

    positions = []
    start = start_position
    while True:
        pos = string.find(substring, start)
        if pos == -1:
            break
        positions.append(pos)
        start = pos + 1  # Continue search from the next character
    return positions


def display_task_warnings() -> None:
    """
    Output any warnings for tasks with too many actions.

    This function goes through the list of tasks with too many actions
    and adds them to the output list.  It then outputs all the warnings.
    """
    task_translated = translate_string("Task")
    has_translated = translate_string("has")
    actions_translated = translate_string("actions")
    warnings = [
        format_html(
            "trailing_comments_color",
            "",
            f"\n{translate_string('Tasks With Too Many Actions (Limit is')} {PrimeItems.program_arguments['task_action_warning_limit']})...",
            False,
        ),
    ]
    # Go through the warnings and add to our output list.
    _fix_hyperlink_name = fix_hyperlink_name
    for task_name, value in PrimeItems.task_action_warnings.items():
        # Build the hotlink to the Task.
        href_name = _fix_hyperlink_name(task_name)
        # Build the hyperelink reference.  The explicit color/underline is needed because this
        # link sits inside a "trailing_comments_color" span: NiceGUI's Map view runs on Tailwind,
        # whose CSS reset makes <a> inherit the parent span's color/text-decoration instead of
        # the browser's default link styling, so without this it renders as plain, unclickable-
        # looking text (it's still a real, working link either way).
        href = f'<a href=#tasks_{href_name} style="color: #3399ff; text-decoration: underline;">{task_name}</a>'

        # Add the warning to the list.
        warnings.append(f"{task_translated} {href} {has_translated} {value['count']} {actions_translated}")

    # Start the output
    PrimeItems.output_lines.add_line_to_output(0, "<hr>", FormatLine.dont_format_line)

    # Output all Task warning lines
    for warning in warnings:
        # Add the line to the output.
        PrimeItems.output_lines.add_line_to_output(
            0,
            warning,
            ["", "trailing_comments_color", FormatLine.add_end_span],
        )


def fix_hyperlink_name(name: str) -> str:
    """
    Fix the hyperlink name so it doesn't screw up the html output.

    Args:
        name (str): The name to fix.

    Returns:
        str: The fixed name.
    """
    return name.replace(" ", "_").replace(">", "&gt;").replace("<", "&lt;")


def get_value_if_match(
    data: dict,
    match_key: str,
    match_value: str,
    return_key: str,
) -> str | None:
    """
    Retrieve a specific value from a dictionary if another value matches a given string.

    Parameters:
    - data (dict): The dictionary to search.
    - match_key (str): The key to check for the match.
    - match_value (str): The value to match against.
    - return_key (str): The key whose value to return if a match is found.

    Returns:
    - The value associated with return_key if a match is found, else None.
    """
    for key, item in data.items():
        if item[match_key] == match_value:
            return item[return_key], key
    return None, None


# Clear all Tasker XML data from memory so we start anew.
def clear_tasker_data() -> None:
    """
    Clears all the tasker data stored in the PrimeItems class.

    This function clears the tasker data by clearing the following lists:
    - all_projects: a list of all the projects
    - all_profiles: a list of all the profiles
    - all_tasks: a list of all the tasks
    - all_scenes: a list of all the scenes

    This function does not take any parameters.

    This function does not return anything.
    """
    # Get rid of any data we currently have
    PrimeItems.tasker_root_elements["all_projects"].clear()
    PrimeItems.tasker_root_elements["all_profiles"].clear()
    PrimeItems.tasker_root_elements["all_tasks"].clear()
    PrimeItems.tasker_root_elements["all_tasks_by_name"].clear()
    PrimeItems.tasker_root_elements["all_scenes"].clear()


def count_unique_substring(string_list: list, substring: str) -> int:
    """
    Counts the number of strings in a list that contain a given substring,
    assuming each string has at most one instance of the substring.

    Args:
      string_list: A list of strings to search within.
      substring: The substring to count.

    Returns:
      An integer representing the number of strings containing the substring.
    """
    count = 0
    for text in string_list:
        if substring in text:
            count += 1
    return count


# Find the owning Profile given a Task name
def find_owning_profile(task_name: str) -> str:
    """
    Find the owning Profile given a Task name.

    This function takes a Task name as input and searches for the corresponding Task ID in the `PrimeItems.tasker_root_elements["all_tasks"]` dictionary. It then iterates over the `PrimeItems.tasker_root_elements["all_profiles"]` dictionary to find the Profile that contains the Task ID. If a matching Profile is found, its name is returned. If no matching Profile is found, an empty string is returned.

    Parameters:
        task_name (str): The name of the Task.

    Returns:
        str: The name of the owning Profile, or an empty string if no matching Profile is found.
    """
    tid = next(
        (k for k, v in PrimeItems.tasker_root_elements["all_tasks"].items() if v["name"] == task_name),
        "",
    )

    # Find the owning Profile
    if tid:
        for profile_value in PrimeItems.tasker_root_elements["all_profiles"].values():
            for mid_key in ["mid0", "mid1"]:
                mid = profile_value["xml"].find(mid_key)
                if mid is not None and mid.text == tid:
                    return profile_value["name"]

    return ""


# Find owning Project given a Profile name
def find_owning_project(profile_name: str) -> str:
    """
    Find the owning Project given a Profile name.

    Args:
        self: The instance of the class.
        profile_name (str): The Profile name.

    Returns:
        str: The owning Project name, or an empty string if not found.
    """
    profile_dict = PrimeItems.tasker_root_elements["all_profiles"]
    profile_id = {v["name"]: k for k, v in profile_dict.items()}.get(profile_name)

    if profile_id:
        _get_ids = get_ids
        for project_name, project_value in PrimeItems.tasker_root_elements["all_projects"].items():
            if profile_id in _get_ids(True, project_value["xml"], project_name, []):
                return project_name
    return ""


def close_logfile() -> None:
    """Close the log file(s)"""
    # The FileHandler lives on the ROOT logger, not on "MapTasker": maputil2.setup_logging() installs
    # it via logging.basicConfig(), and our logger simply propagates up to it.  Iterating
    # logger.handlers here would walk an empty list and close nothing at all.
    for target in (logger, logging.root):
        for handler in target.handlers[:]:  # Iterate over a copy to avoid issues during modification
            handler.close()  # Close the stream associated with the handler
            target.removeHandler(handler)  # Remove the handler from the logger


def exit_program(return_code: int = 0) -> None:
    """Common program exit code."""
    close_logfile()
    sys.exit(return_code)


def append_to_filename(original_filename_with_type: str, text_to_append: str) -> str:
    """
    Appends a text string to the filename part of a given filename, preserving the file type.

    Args:
        original_filename_with_type (str): The original filename including its extension (e.g., "document.pdf").
        text_to_append (str): The text string to append to the filename (e.g., "_new").

    Returns:
        str: The new filename with the text appended, or None if the input is invalid.
    """
    if not isinstance(original_filename_with_type, str) or not isinstance(
        text_to_append,
        str,
    ):
        logger.error(
            "Error: Both original_filename_with_type and text_to_append must be strings.",
        )
        return None

    # Use os.path.splitext to separate the filename and its extension
    filename_without_extension, file_extension = os.path.splitext(
        original_filename_with_type,
    )

    # Append the text to the filename
    new_filename_without_extension = filename_without_extension + text_to_append

    # Combine the new filename with the original extension
    return new_filename_without_extension + file_extension


def get_timezone_from_ip() -> str:
    """
    Attempts to determine the current timezone using IP geolocation via ipinfo.io.
    Requires an internet connection.

    Returns:
        str: The IANA timezone name (e.g., 'America/Mexico_City'), or None if not found.
    """
    try:
        # Send a request to ipinfo.io to get IP details (including timezone)
        # This will query your public IP
        response = requests.get("https://ipinfo.io/json", timeout=5)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        data = response.json()

        timezone_name = data.get("timezone")
        if timezone_name:
            logger.info(f"Discovered timezone via IP: {timezone_name}")
            return timezone_name
        logger.debug("Timezone information not found in IP geolocation data.")
        return None  # noqa: TRY300
    except requests.exceptions.RequestException as e:
        logger.debug(f"Error connecting to geolocation service or getting data: {e}")
        return None
    except Exception as e:  # noqa: BLE001
        logger.debug(f"An unexpected error occurred during IP geolocation: {e}")
        return None


def get_current_local_time_auto_timezone() -> str:
    """
    Attempts to get the current local time by first discovering the timezone
    via IP geolocation. Works with Python 3.9+.
    """
    timezone_string = get_timezone_from_ip()

    if timezone_string:
        try:
            local_tz = ZoneInfo(timezone_string)
            now_aware = datetime.now(local_tz)
            logger.info(f"\nAutomatically determined current local time: {now_aware}")
            logger.info(f"Timezone info: {now_aware.tzinfo}")
            logger.info(f"Offset from UTC: {now_aware.utcoffset()}")
            return now_aware  # noqa: TRY300
        except ZoneInfoNotFoundError:
            logger.debug(
                f"Error: Discovered timezone '{timezone_string}' is not recognized by zoneinfo.",
            )
            return datetime.now()  # noqa: DTZ005
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Error creating timezone-aware datetime: {e}")
            return datetime.now()  # noqa: DTZ005
    else:
        logger.debug(
            "\nCould not determine timezone automatically. Falling back to naive datetime.",
        )
        logger.debug(f"Current naive datetime: {datetime.now()}")  # noqa: DTZ005
        return datetime.now()  # noqa: DTZ005


def rename_file(old_file_path: str, new_file_path: str) -> bool:
    """
    Renames a file from an old path to a new path.

    Args:
        old_file_path (str): The current path/name of the file.
        new_file_path (str): The desired new path/name for the file.

    Returns:
        bool: True if the file was successfully renamed, False otherwise.
    """
    if not isinstance(old_file_path, str) or not isinstance(new_file_path, str):
        rutroh_error("Error: Both old_file_path and new_file_path must be strings.")
        return False

    try:
        # Check if the old file exists before attempting to rename
        if not os.path.exists(old_file_path):
            rutroh_error(f"Error: The file '{old_file_path}' does not exist.")
            return False

        os.rename(old_file_path, new_file_path)
        rutroh_error(f"File '{old_file_path}' successfully renamed to '{new_file_path}'.")

        return True  # noqa: TRY300
    except OSError as e:
        rutroh_error(f"Error renaming file: {e}")
        return False


def restart_program_subprocess() -> None:
    """
    Restarts the current program by spawning a new process and exiting the old one.
    This is often more reliable on Windows.
    NOTE: This is a duplicate of 'rurun_process' in mapit.py, to avoid circular import error.
    """
    # Get the absolute path of the current script file
    # This is more robust than relying directly on sys.argv[0]
    script_path = os.path.abspath(__file__)
    script_path = script_path.replace(f"src{PrimeItems.slash}maputils.py", "main.py")

    # Prepare the arguments for the new process
    # The first argument is the Python interpreter
    # The second is the absolute path to the script
    # The rest are any original command-line arguments (excluding the script name itself)
    new_process_args = [sys.executable, script_path, *sys.argv[1:]]

    subprocess.Popen(new_process_args)  # noqa: S603
    print("Restarting program.  Please stand by...")
    time.sleep(0.2)

    # If we're inside a running event loop (e.g. this was triggered from a NiceGUI
    # button click), sys.exit() only raises SystemExit inside that task, which crashes
    # the loop/uvicorn server with a messy traceback instead of cleanly ending the process.
    # NiceGUI's core.stop_and_exit() is built for exactly this: it runs shutdown
    # handlers/atexit callbacks and then hard-exits via os._exit().
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        sys.exit(0)  # Not in an event loop: plain, clean exit.
    else:
        from nicegui.core import stop_and_exit  # noqa: PLC0415

        # stop_and_exit() blocks on asyncio.run_coroutine_threadsafe(...).result(),
        # which needs the event loop's own thread free to run the scheduled coroutine.
        # Calling it directly from here (already on the loop's thread, inside this
        # button-click handler) deadlocks that wait for a full 30s, during which the
        # old process still holds the port that the freshly-spawned new process is
        # trying to bind to. NiceGUI itself always calls stop_and_exit() from a
        # separate thread (see nicegui/server.py) for this exact reason.
        threading.Thread(target=stop_and_exit, daemon=True).start()


def make_hex_color(color_string: str) -> str:
    """
    Validates a string input to determine if it's a color name or a hex code.

    - If it's a valid 6-digit hex code (with or without a leading '#'), it returns
      the 6 digits prefixed with a '#'.
    - If it's a valid 3-digit hex code, it returns the 3 digits without the '#'.
    - Otherwise, the original string is returned, assuming it's a color name.

    Args:
        color_string: The string representing the color (e.g., 'green', '00ff20', '#33aaff').

    Returns:
        The validated color string (e.g., '#00ff20', 'f00', 'green').
    """
    # Remove leading/trailing whitespace and convert to lowercase for consistent checking
    color_input = color_string.strip().lower()

    # Define the regular expression pattern for a hex color code
    # This pattern matches: #?([0-9a-f]{3}|[0-9a-f]{6})
    hex_pattern = re.compile(r"^#?([0-9a-f]{3}|[0-9a-f]{6})$")

    match = hex_pattern.match(color_input)

    if match:
        # The captured hex value (3 or 6 chars) is in group(1)
        hex_value = match.group(1)

        # --- MODIFICATION START ---
        if len(hex_value) == 6:
            # If it's a 6-digit code, return it with the '#' prefix
            return f"#{hex_value}"
        # This handles the 3-digit hex codes
        # If it's a 3-digit code, return it without the '#' prefix
        return hex_value
        # --- MODIFICATION END ---
    # If it's not a hex code, we assume it's a color name and return the original string.
    return color_string.strip()


def live_translate_text(text: str) -> str:
    """
    Translates text using live translation if enabled.
    Args:
        text: The text to be translated.
    Returns:
        translated text if live translation is enabled, otherwise the original text.
    """
    target = PrimeItems.program_arguments["language"]
    if target == "English":
        return text
    if target == "Traditional Chinese":
        target_lang = "chinese (traditional)"
    elif target == "Simplified Chinese":
        target_lang = "chinese (simplified)"
    else:
        target_lang = PrimeItems.languages[target]

    return GoogleTranslator(source="auto", target=target_lang).translate(text)
