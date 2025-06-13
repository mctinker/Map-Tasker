#! /usr/bin/env python3
"""Build new Task action codes dictionary by merging what we already have with that from
Tasker"""

#                                                                                      #
# acmerge: Task action codes merge with Tasker's action codes                          #
#                                                                                      #

# 1- Run the new version of Tasker and invoke the WebUI in the new Tasker interface.
# 2- Access the WebUI via browser on desktop: https://192.168.0.xx:8745
# 3- Run 'Get Args' to list all of the Task action codes.
# 4- Copy the results into /maptasker/asseets/json/task_all_actions.json
# 5- Modify proginit 'build_it_all = True
# 6- Run with debug on to create 'newdict.py'.  Look for erros and missing codes.
# 7- Run /maptasker/maptasker_misc_code/format_120_linelength.py to create superdict.py
# 8- Replace 'actionc.py' with 'superdfict.py' contents.
#
# The code herein performs step # 5.
#
import json
import re

import requests

from maptasker.src.actionc import ActionCode, action_codes
from maptasker.src.primitem import PrimeItems


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


class CustomJSONEncoder(json.JSONEncoder):
    """
    Custom JSON Encoder that capitalizes JSON boolean values.

    This encoder overrides the default JSONEncoder to replace lowercase
    boolean values ('true', 'false') with their capitalized counterparts
    ('True', 'False') in the resulting JSON string.
    """

    def iterencode(self, obj: object, _one_shot: bool = False) -> object:
        """
        Encodes the given object to a JSON formatted string, replacing lowercase
        JSON booleans with their capitalized counterparts.

        Args:
            obj: The object to encode.
            _one_shot (bool): Whether to use a single-pass encoding process.

        Yields:
            str: Chunks of the JSON encoded string with capitalized booleans.
        """
        for chunk in super().iterencode(obj, _one_shot):
            yield chunk.replace("true", "True").replace(
                "false",
                "False",
            )  # Capitalizing JSON booleans


def save_dict_to_json(dictionary: dict, filename: str) -> None:
    """
    Save a dictionary to a JSON file.

    Args:
        dictionary (dict): The dictionary to save.
        filename (str): The path to the file where the dictionary will be saved.

    Returns:
        None
    """
    with open(filename, "w") as file:
        json.dump(dictionary, file, indent=4, cls=CustomJSONEncoder)


def merge_custom_sort(lst: list) -> list:
    """
    Sorts a list of strings based on a custom sorting key.

    The sorting key is determined by the first character of each string:
    - If the first character is a digit, it is converted to a float and used as the primary sorting key.
    - If the first character is not a digit, it is assigned a float value of infinity for sorting purposes.
    - The secondary sorting key is the first character itself.

    Args:
        lst (list): A list of strings to be sorted.

    Returns:
        list: A new list of strings sorted based on the custom sorting key.
    """

    def sort_key(item: str) -> tuple:
        key = item[0]
        return (float(key) if key.isdigit() else float("inf"), key) if key.isdigit() else (float("inf"), key)

    return sorted(lst, key=sort_key)


def merge_add_code(
    new_dict: dict,
    code: str,
    redirect: str,
    args: list,
    name: str,
    category: str,
    canfail: bool,
) -> dict:
    """
    Adds a new ActionCode to the provided dictionary with the given parameters.

    Args:
        new_dict (dict): The dictionary to which the new ActionCode will be added.
        code (str): The key under which the new ActionCode will be stored in the dictionary.
        redirect (str): The redirect URL or path for the ActionCode.
        args (list): A list of arguments associated with the ActionCode.
        name (str): The display name or description for the ActionCode.
        category (str): The category to which the ActionCode belongs.
        canfail (bool): A flag indicating whether the ActionCode can fail.

    Returns:
        dict: The updated dictionary with the new ActionCode added.
    """
    new_dict[code] = ActionCode(redirect, args, name, category, canfail)
    return new_dict


def merge_codes(new_dict: dict, just_the_code: str, code: str, value: object) -> dict:
    """
    Merges tasker 'Task' action codes into a new dictionary.

    Args:
        new_dict (dict): The dictionary to merge the codes into.
        just_the_code (str): The key to look up in the tasker action codes.
        code (str): The code to use as the key in the new dictionary.
        value (object): An object containing the Tasker values / arguments for a specific code.

    Returns:
        dict: The updated dictionary with the new code added.

    Raises:
        KeyError: If the `just_the_code` is not found in `PrimeItems.tasker_action_codes`.
    """
    # See if our code is in Tasker's json data and merge it if it is.
    try:
        tasker_action_code = PrimeItems.tasker_action_codes[just_the_code]
        args = []
        for arg in tasker_action_code["args"]:
            arg_eval = ""
            try:
                id_to_compare_to = str(arg["id"])
                for arg_lookup in value.args:
                    if arg_lookup[0] == id_to_compare_to:
                        arg_eval = arg_lookup[4]
                        break
            except (ValueError, AttributeError):
                arg_eval = ""
            # Add the argument
            args.append(
                (
                    str(arg["id"]),
                    arg["isMandatory"],
                    arg["name"],
                    str(arg["type"]),
                    arg_eval,
                ),
            )

        # Sort the args.
        args = merge_custom_sort(args)

        # Get optional values
        category = tasker_action_code.get("category_code", "")
        canfail = tasker_action_code.get("canfail", "")
        # Build the dictionary
        new_dict = merge_add_code(
            new_dict,
            code,
            "",
            args,
            tasker_action_code["name"],
            category,
            canfail,
        )

    # It's a plugin, or simply not in Tasker's table.
    except KeyError:
        # Ignore code 100t (test) and codes > 4 digits (plugins)
        if len(just_the_code) <= 4 and code != "1000t":
            debug_print(f"Code {code} not found in Tasker's table.")
        # Copy relevant argument(s) data to new dictionary.
        args = value.args

        # Add it to our dictionary
        new_dict = merge_add_code(
            new_dict,
            code,
            value.redirect,
            args,
            value.name,
            value.category,
            "",
        )

    return new_dict


def merge_action_codes() -> None:
    """
    Merges action codes from the global `action_codes` dictionary and `PrimeItems.tasker_action_codes` dictionary
    into a new dictionary, and saves the result to a file.

    The function performs the following steps:
    1. Iterates through the old `action_codes` dictionary and processes each code based on its type.
       - If the code type is 't', 's', or 'e' and the code (excluding the last character) is numeric, it merges the code
       with the code table read from Tasker's development site (`PrimeItems.tasker_action_codes`).
       - Otherwise, it handles screen elements by creating a list of arguments and adding them to the new dictionary.
    2. Ensures that all codes from `PrimeItems.tasker_action_codes` are included in the new dictionary.
       - If a code is not present, it merges the code with a modified version of the code.
    3. Saves the new dictionary to a file named "newdict.txt" in Python syntax.

    The function does not return any value.
    """
    new_dict = {}
    for code, value in action_codes.items():
        just_the_code = code[:-1]
        code_type = code[-1]
        # Task?
        if code_type == "t" and just_the_code.isdigit():
            # Merge our Task action code with that of Tasker's.
            new_dict = merge_codes(new_dict, just_the_code, code, value)

        # Handle 's', 'e' and screen elements
        else:
            # Copy relevant argument(s) data to new dictionary.
            args = value.args
            # Add it to our dictionary
            new_dict = merge_add_code(
                new_dict,
                code,
                value.redirect,
                args,
                value.name,
                "",
                "",
            )

    # Check if all PrimeItems.tasker_action_codes are in action_codes, and if not, then add it.
    for just_the_code, value in PrimeItems.tasker_action_codes.items():
        modified_code = f"{just_the_code}t"
        if modified_code not in new_dict:
            # New code!  Add it.
            tasker_action_code = PrimeItems.tasker_action_codes[just_the_code]
            # Format the arguments
            args = []
            for arg in tasker_action_code["args"]:
                args.append(
                    (
                        str(arg["id"]),
                        arg["isMandatory"],
                        arg["name"],
                        str(arg["type"]),
                        f", {arg['name']}",
                    ),
                )
            # Get optional values
            category = tasker_action_code.get("category_code", "")
            canfail = tasker_action_code.get("canfail", "")
            debug_print(
                f"Adding Task action: {value['name']}...validate the arguments!",
            )
            new_dict = merge_add_code(
                new_dict,
                modified_code,
                "",
                args,
                value["name"],
                category,
                canfail,
            )

    # Sort and save the new dictionary so we can import it.
    new_dict = dict(sorted(new_dict.items()))
    save_dict_to_json(new_dict, "newdict.py")

    debug_print("New Action Codes dictionary saved.")


def debug_print(message: str) -> None:
    """
    Prints a debug message if the debug mode is enabled.

    Args:
        message (str): The debug message to be printed.

    Returns:
        None
    """
    if PrimeItems.program_arguments["debug"]:
        print(message)


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
            debug_print(
                f"Tasker's {key} {code_name} code {code!s} not found in actionc table!  Needs to be added.",
            )

    # Reverse the dictionary of Tasker codes
    reverse_codes = {v: k for k, v in codes.items()}

    # Make sure our action codes are in Tasker's dictionary
    for key in action_codes:
        action_code_type = key[-1]
        code = key[:-1]
        if action_code_type == code_type and int(code) not in reverse_codes:
            missing_codes.append(f"{code}{code_type}")

    if missing_codes:
        debug_print(
            f"Our action codes (actionc) not found in Tasker's {code_name} table: {', '.join(missing_codes)}",
        )

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
        debug_print(format_columns(mismatch_names))
