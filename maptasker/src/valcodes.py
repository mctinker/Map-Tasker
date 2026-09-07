#! /usr/bin/env python3
"""Validate the Event and State codes in the overlay against Tasker's own source"""

#                                                                                      #
# valcodes: check action_overlay.json's Event/State codes against Tasker's published    #
#           Java constants                                                             #
#                                                                                      #
# Updating MapTasker for a new Tasker release:                                          #
#                                                                                      #
# 1- Run the new version of Tasker and invoke the WebUI in the new Tasker interface.    #
# 2- Access the WebUI via browser on desktop: https://192.168.0.xx:8745                 #
# 3- Run 'Get Args' to list all of the Task action codes.                               #
# 4- Copy the results into /maptasker/assets/json/task_all_actions.json                 #
# 5- Modify proginit 'build_all = True' and run, to check the result.                   #
#                                                                                      #
# There used to be two more steps -- generate a replacement dictionary and paste it     #
# over actionc.py.  Both are gone: actionc.py reads task_all_actions.json directly, so  #
# step 4 IS the update.  What still needs checking is the half Tasker does not publish  #
# in that file, which is what this module does: Event and State codes come from the     #
# Java constants on Tasker's site and are compared against action_overlay.json.         #
#                                                                                      #
# This was 'acmerge' when merging Tasker's table into actionc.py was most of what it    #
# did.  That half is gone with the merge; what is left validates, so it is named for    #
# that.                                                                                #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #

import re

import requests

from maptasker.src.actionc import action_codes
from maptasker.src.primitem import PrimeItems

NEWLINE = "\n"


def java_constants_to_dict(url: str) -> dict:
    """
    Fetches a Java source file from the given URL and extracts public static final int constants.

    Args:
        url (str): The URL of the Java source file.

    Returns:
        dict: A dictionary where the keys are the constant names and the values are their corresponding integer values.

    Raises:
        requests.exceptions.RequestException: If there is an issue with the HTTP request.

        This code snippet fetches a Java source file (or similar text) from a given URL, extracts constant integer
        values from public static final int declarations using regex, and returns them as a dictionary.
    """
    constants = {}
    pattern = re.compile(r"public\s+static\s+final\s+int\s+(\w+)\s*=\s*(-?\d+);")

    response = requests.get(url, timeout=10)
    response.raise_for_status()

    for line in response.text.splitlines():
        match = pattern.search(line)
        if match:
            constants[match.group(1)] = int(match.group(2))

    return constants


def debug_print(message: str) -> None:
    """
    Prints a debug message if the debug mode is enabled.

    Args:
        message (str): The debug message to be printed.

    Returns:
        None
    """
    filename = "buildit.log"

    if PrimeItems.program_arguments["debug"]:
        print(message)
        try:
            # 2. Open the file in write mode ('w')
            # 'w' mode will create the file if it doesn't exist, or overwrite it if it does.
            with open(filename, "a") as file:
                # 3. Write the text string to the file
                file.write(message)
        except OSError as e:
            # 4. Handle potential I/O errors (e.g., permission issues, disk full)
            print(f"valcodes:Error: Could not write to file '{filename}'. Reason: {e}")
        except Exception as e:  # noqa: BLE001
            # Catch any other unexpected errors
            print(f"valcodes: An unexpected error occurred: {e}")


def format_string(s: str) -> str:
    """
    Converts a string of fully capitalized words separated by underscores
    into a properly capitalized sentence with spaces.

    Example:
    format_string("HELLO_WORLD_THIS_IS_CHATGPT") -> "Hello World This Is Chatgpt"

    :param s: The input string with words in uppercase separated by underscores.
    :return: A formatted string with spaces instead of underscores and correct capitalization.
    """
    return " ".join(word.capitalize() for word in s.split("_"))


def format_columns(entries: list) -> str:
    """
    Formats a list of entries into aligned columns.

    :param entries: List of strings containing mismatched Tasker names.
    :return: A formatted string with aligned columns.
    """
    formatted_entries = []

    for entry in entries:
        parts = entry.split("   <<< ")
        names = parts[0].split(" vs ")
        code = parts[1] if len(parts) > 1 else ""
        formatted_entries.append((names[0].strip(), names[1].strip(), code.strip()))

    # Determine column widths
    col1_width = max(len(row[0]) for row in formatted_entries)
    col2_width = max(len(row[1]) for row in formatted_entries)
    col3_width = max(len(row[2]) for row in formatted_entries)

    # Format output
    return "".join(
        f"{row[0]:<{col1_width}} != {row[1]:<{col2_width}} <<< {row[2]:<{col3_width}}\n" for row in formatted_entries
    )


def validate_states_and_events(code_type: str, url: str) -> None:
    """
    Validates the state and event codes by fetching the Java source file from the given URL and converting the
    public static final int constants to a dictionary.

    Args:
        code_type (str): The type of code to validate ('s' for states, 'e' for events).
        url (str): The URL of the Java source file containing the constants.

    Returns:
        None

    Raises:
        requests.exceptions.RequestException: If there is an issue with the HTTP request.
    """
    missing_codes = []
    # Get the data.
    if code_type == "s":
        code_name = "State"
        target = PrimeItems.tasker_state_codes
    else:
        code_name = "Event"
        target = PrimeItems.tasker_event_codes

    codes = java_constants_to_dict(url)
    target.update(codes)

    # Make sure the Tasker codes are in our dictionary
    for key, code in codes.items():
        modified_code = str(code) + code_type
        if code != -1 and modified_code not in action_codes:
            debug_print(f"Tasker's {key} {code_name} code {code!s} not found in actionc table!  Needs to be added.")

    # Reverse the dictionary of Tasker codes
    reverse_codes = {v: k for k, v in codes.items()}

    # Make sure our action codes are in Tasker's dictionary
    for key in action_codes:
        action_code_type = key[-1]
        code = key[:-1]
        if action_code_type == code_type and int(code) not in reverse_codes:
            missing_codes.append(f"{code}{code_type}")

    if missing_codes:
        debug_print("Note: Codes '6s' and '37s' are for older versions of Tasker (Prior to version 6)")
        debug_print(f"Our action codes (actionc) not found in Tasker's {code_name} table: {', '.join(missing_codes)}")

    # Make sure Tasker code 'names' are the same as our actionc code 'names'
    mismatch_names = []
    for key, code in codes.items():
        code_name = format_string(key)
        modified_code = str(code) + code_type
        if code != -1 and modified_code in action_codes and code_name != action_codes[modified_code][2]:
            mismatch_names.append(
                f"{code_name} vs {action_codes[modified_code][2]}   <<< Tasker's name mismatch for actionc table code:{modified_code}.",
            )
    if mismatch_names:
        debug_print("Tasker Code ... vs ... Our actionc Code")
        debug_print(format_columns(mismatch_names))
