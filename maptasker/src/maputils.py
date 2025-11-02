"""General Utilities"""

#! /usr/bin/env python3

#                                                                                      #
# maputils: General utilities used by program.                                         #
#                                                                                      #
from __future__ import annotations

import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import (
    ZoneInfo,
    ZoneInfoNotFoundError,
)  # Import ZoneInfoNotFoundError for specific error handling

import defusedxml.ElementTree as et  # noqa: N813
import requests
import webcolors
from requests.exceptions import ConnectionError, InvalidSchema, Timeout  # noqa: A004

from maptasker.src.error import rutroh_error
from maptasker.src.format import format_html
from maptasker.src.getbakup import write_out_backup_file
from maptasker.src.getids import get_ids
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import FormatLine, logger
from maptasker.src.taskerd import get_the_xml_data
from maptasker.src.xmldata import rewrite_xml

if TYPE_CHECKING:
    from collections.abc import Generator


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
    """Update this package."""
    version = get_pypi_version()
    packageversion = "maptasker" + version
    subprocess.call(  # noqa: S603
        [sys.executable, "-m", "pip", "install", packageversion, "--upgrade"],
    )


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

    # Loop until we get a valid XML file or invalid XML
    while process_file:
        # Validate the file
        if return_code == 0:
            # Process the XML file
            PrimeItems.program_arguments["android_file"] = android_file

            # If getting file from Android device, write out the backup file first.
            if ip_address:
                write_out_backup_file(file_contents)

            # We don't have the file yet.  Lets get it.
            else:
                return_code = get_the_xml_data()
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
                rewrite_xml(file_to_validate)
                counter += 1
                if counter > 2:
                    error_message = f"Unicode error in {android_file}.  Try again."
                    break
                process_file = True  # Loop one more time.
            except Exception as e:  # any other errorError out and exit  # noqa: BLE001
                error_message = f"XML parsing error {e} in file {android_file}.\n\nTry again."
                process_file = False  # Get out of while/loop

    return error_message, xml_tree


# Read XML file and validate the XML.
def validate_xml_file(ip_address: str, port: str, android_file: str) -> bool:
    # Read the file
    """Validates an XML file from an Android device.
    Parameters:
        - ip_address (str): IP address of the Android device.
        - port (str): Port number of the Android device.
        - android_file (str): Name of the XML file to be validated.
    Returns:
        - bool: True if the file is valid, False if not.
    Processing Logic:
        - Reads the file from the Android device.
        - Validates the XML file.
        - Checks if the file is Tasker XML.
        - Returns True if the file is valid, False if not."""
    if ip_address:
        return_code, file_contents = http_request(
            ip_address,
            port,
            android_file,
            "file",
            "?download=1",
        )
        if return_code != 0:
            return 1, file_contents
    else:
        return_code = 0

    # Validate the xml
    error_message, xml_tree = validate_xml(
        ip_address,
        android_file,
        return_code,
        file_contents,
    )

    # If there was an error, bail out.
    if error_message:
        logger.debug(error_message)
        return 1, error_message

    # Make surre this is Tasker XML
    xml_root = xml_tree.getroot()
    if xml_root.tag != "TaskerData":
        return 0, f"File {android_file} is not valid Tasker XML.\n\nTry again."

    return 0, ""


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
    Count the maximum consecutive occurrences of a substring within a main string.
    Args:
        main_str: The main string to search for consecutive substrings.
        substr: The substring to count consecutive occurrences of.

    Returns:
        The maximum count of consecutive occurrences of the substring within the main string.
    NOTE: Oprtimized version to reduce string slicing operations.
    """
    if not main_str or not substr:
        return 0

    sub_len = len(substr)
    max_count = count = 0
    i = main_str.find(substr)

    while i != -1:
        # Check if this occurrence is consecutive with the previous
        next_i = i + sub_len
        next_found = main_str.find(substr, next_i)
        count = 1

        while next_found == next_i:
            count += 1
            next_i += sub_len
            next_found = main_str.find(substr, next_i)

        max_count = max(max_count, count)
        i = main_str.find(substr, next_i)

    return max_count


def pretty(d: dict, indent: int = 0) -> None:
    """
    Print out a dictionary in a human-readable format.

    Args:
        d: The dictionary to print.
        indent: The number of tabs to indent the output with.
    """
    for key, value in d.items():
        print("\t" * indent + str(key))
        if isinstance(value, dict):
            pretty(value, indent + 1)
        else:
            print("\t" * (indent + 1) + str(value))


def append_item_to_list(item: str, lst: list = []) -> list:  # noqa: B006
    """
    Append the given item to the list and return the list.

    Args:
        item: The item to append to the list.
        lst: The list to append to. Defaults to an empty list.

    Returns:
        The list with the item appended.
    """
    lst.append(item)
    return lst


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
    warnings = [
        format_html(
            "trailing_comments_color",
            "",
            f"Tasks With Too Many Actions (Limit is {PrimeItems.program_arguments['task_action_warning_limit']})...",
            False,
        ),
    ]
    # Go through the warnings and add to our output list.
    for task_name, value in PrimeItems.task_action_warnings.items():
        # Build the hotlink to the Task.
        href_name = fix_hyperlink_name(task_name)
        # Build the hyperelink reference
        href = f"<a href=#tasks_{href_name}>{task_name}</a>"

        # Add the warning to the list.
        warnings.append(f"Task {href} has {value['count']} actions")

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


def get_first_substring_match(main_string: str, substrings: list) -> str | None:
    """
    Checks if any of the substrings in a list are present in a given string.

    Args:
      main_string: The string to search within.
      substrings: A list of strings to search for.

    Returns:
      The first substring found in the main string, or None if no match is found.
    """
    for sub in substrings:
        if sub in main_string:
            return sub
    return None


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
        for project_name, project_value in PrimeItems.tasker_root_elements["all_projects"].items():
            if profile_id in get_ids(True, project_value["xml"], project_name, []):
                return project_name
    return ""


def find_task_pattern(text: str) -> bool:
    r"""
    Checks if the pattern 'xTask x has x actions\n' exists in the given string.

    Args:
        text (str): The string to search within.

    Returns:
        bool: True if the pattern is found, False otherwise.
    """
    # The '.*?' matches any character (except newline) zero or more times, non-greedily.
    # We use re.DOTALL to make '.' match newlines as well, in case 'x' spans multiple lines,
    # though your specific pattern has a newline character.
    # The '\n' at the end of the pattern matches a literal newline character.
    pattern = r".*?Task .*? has .*? actions\n"

    # re.search() scans through the string looking for the first location
    # where the regular expression pattern produces a match.
    return bool(re.search(pattern, text, re.DOTALL))


def close_logfile() -> None:
    """Close the log file(s)"""
    for handler in logger.handlers[:]:  # Iterate over a copy to avoid issues during modification
        handler.close()  # Close the stream associated with the handler
        logger.removeHandler(handler)  # Remove the handler from the logger


def exit_program(return_code: int = 0) -> None:
    """Common program exit code."""
    close_logfile()
    sys.exit(return_code)


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """
    Converts a hexadecimal color string (e.g., '#RRGGBB' or 'RRGGBB') to an RGB tuple.

    Args:
        hex_color (str): The hexadecimal color string.

    Returns:
        tuple[int, int, int]: An RGB tuple (R, G, B) where each component is 0-255.

    Raises:
        ValueError: If the hex color string is malformed.
    """
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return False
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r, g, b)  # noqa: TRY300

    except ValueError:
        logger.debug("Invalid hex color input: " + hex_color)
        return False


def get_rgb_from_color_input(color_input: str) -> tuple[int, int, int]:
    """
    Converts a color input (either name or hex) to an RGB tuple.

    Args:
        color_input (str): The color name (e.g., "blue") or hex value (e.g., "#ffffe0").

    Returns:
        tuple[int, int, int]: An RGB tuple (R, G, B) where each component is 0-255.

    Raises:
        ValueError: If the color_input is not a valid color name or hex code.
    """
    color_input = color_input.strip()
    if color_input.startswith("#") or (color_input.isdigit and len(color_input) == 6):
        return hex_to_rgb(color_input)

    try:
        # webcolors.name_to_rgb expects a lowercase name
        return webcolors.name_to_rgb(color_input.lower())
    except ValueError:
        logger.debug(f"Invalid color input: {color_input}")
        return False


def is_color_dark(color_input: str, luminance_threshold: float = 0.5) -> bool:
    """
    Determines if a given color is darker than it is light based on its perceived luminance.

    Args:
        color_input (str): The color name (e.g., "blue") or hex value (e.g., "#ffffe0").
        luminance_threshold (float): A value between 0.0 and 1.0 (inclusive)
                                     where 0.0 is black and 1.0 is white.
                                     Colors with luminance below this threshold are
                                     considered 'dark'. Default is 0.5.

    Returns:
        bool: True if the color is darker than the threshold, False otherwise.

    Raises:
        ValueError: If the color_input is invalid or the threshold is out of range.
    """
    if not (0.0 <= luminance_threshold <= 1.0):
        logger.debug("luminance_threshold must be between 0.0 and 1.0.")
        return False

    r, g, b = get_rgb_from_color_input(color_input)

    # Calculate perceived luminance (a common formula for sRGB)
    # The components are first normalized to 0-1, then weighted.
    # These weights account for human perception of brightness (green > red > blue).
    normalized_r = r / 255.0
    normalized_g = g / 255.0
    normalized_b = b / 255.0

    # Note: For strict WCAG (Web Content Accessibility Guidelines) luminance,
    # a more complex gamma correction might be applied before weighting.
    # However, this simpler weighted sum is generally sufficient for a "darker than light" check.
    luminance = 0.299 * normalized_r + 0.587 * normalized_g + 0.114 * normalized_b

    # print(f"Color: '{color_input}' (RGB: {r},{g},{b}) -> Luminance: {luminance:.4f}")

    return luminance < luminance_threshold


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
    sys.exit(0)  # Exit the current script cleanly


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
