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
# 6- Run with debug on to create 'newdict.py'.  Look for errors and missing codes.
# 7- Replace 'actionc.py' with '/assets/json/arg_dict.py' contents.
#
# The code herein performs step # 5.
#
import contextlib
import json
import os
import re

import requests

from maptasker.src.actionc import ActionCode, action_codes
from maptasker.src.primitem import PrimeItems

NEWLINE = "\n"


def _repr_value(value: str | bool | list) -> str:
    """
    Helper to correctly represent different types of values for Python code output.
    Handles strings, booleans, lists.
    """
    if isinstance(value, str):
        return repr(value)  # Uses single quotes and escapes correctly
    if isinstance(value, bool):
        return str(value)  # True/False
    if isinstance(value, list):
        return "[" + ", ".join([_repr_value(item) for item in value]) + "]"
    return str(value)  # Fallback for numbers, None, etc.


def generate_refactored_action_codes(original_dict: dict) -> str:
    """
    Takes the original action_codes dictionary and returns a string
    representing the refactored dictionary with explicit keyword arguments.
    """
    output_lines = ["action_codes = {"]
    for action_id, action_code in original_dict.items():
        output_lines.append(f"    {_repr_value(action_id)}: ActionCode(")

        # Handle ActionCode arguments with explicit keywords
        action_args = []
        action_args.append(f"redirect={_repr_value(action_code.redirect)}")

        # Process the args list (list of ArgumentCode)
        if action_code.args:
            arg_list_lines = []
            for arg in action_code.args:
                # Assuming arg is a list that needs to be converted to ArgumentCode
                # If arg is already an ArgumentCode namedtuple, you would access attributes directly
                # e.g., ArgumentCode(arg_id=_repr_value(arg.arg_id), ... )
                if isinstance(arg[4], list) and len(arg[4]) == 3:
                    arg[4][2] = arg[4][2].replace('"', "'")
                arg[2] = arg[2].replace('"', "'")

                arg_list_lines.append(
                    f"            ArgumentCode("
                    f"arg_id={_repr_value(arg[0])}, "
                    f"arg_required={_repr_value(arg[1])}, "
                    f"arg_name={_repr_value(arg[2])}, "
                    f"arg_type={_repr_value(arg[3])}, "
                    f"arg_eval={_repr_value(arg[4])}"
                    f")",
                )
            action_args.append(
                f"args=[{NEWLINE}{NEWLINE.join(arg_list_lines)},{NEWLINE}        ]",
            )
        else:
            action_args.append("args=[]")

        action_name = action_code.name.replace('"', "'")
        action_args.append(f"name={_repr_value(action_name)}")
        action_args.append(f"category={_repr_value(action_code.category)}")
        action_args.append(f"canfail={_repr_value(action_code.canfail)},")

        output_lines.append("        " + ",\n        ".join(action_args))
        output_lines.append("    ),")
    output_lines.append("}")
    return "\n".join(output_lines)


def read_dictionary_from_file(filepath: str) -> dict:
    """
    Reads a Python file that is expected to contain a dictionary
    and returns that dictionary.

    Args:
        filepath (str): The path to the Python file.

    Returns:
        dict: The dictionary found in the file, or an empty dictionary
              if no dictionary named 'my_dict' (or whatever you name it)
              is found or if the file is empty/invalid.
    """
    if not os.path.exists(filepath):
        debug_print(f"Error: File not found at '{filepath}'")
        return {}

    # Create an empty dictionary to hold the local variables after execution
    local_vars = {}
    try:
        with open(filepath) as file:
            file_content = file.read()
            # Execute the file content within the 'local_vars' scope
            # This makes any variables defined in the file accessible in local_vars
            exec(file_content, {}, local_vars)  # noqa: S102

            # Assuming your dictionary in the file is named 'action_codes'
            # You can change 'action_codes' to whatever your dictionary is named in the file.
            if "action_codes" in local_vars and isinstance(
                local_vars["action_codes"],
                dict,
            ):
                return local_vars["action_codes"]
            debug_print(
                f"Warning: No dictionary named 'action_codes' found or it's not a dictionary in '{filepath}'.",
            )
            return {}
    except Exception as e:  # noqa: BLE001
        debug_print(f"An error occurred while reading or executing the file: {e}")
        return {}


def add_arg_names() -> None:
    """Reformat superdict.py by adding the argument names to the dictionary elements"""

    if os.path.exists("superdict.py"):
        # print("\nAttempting to read dictionary from '/assets/json/superdict.py'...")
        action_codes = read_dictionary_from_file("superdict.py")

    if not action_codes:
        debug_print(
            "acaddnam: Failed to read dictionary from '/assets/json/superdict.py'.  Program terminated",
        )
        return 12

    # Generate the refactored content
    refactored_content = generate_refactored_action_codes(action_codes)

    # Prepare the full content for the file, including imports and namedtuple definitions
    file_content = f"""from collections import namedtuple

    # Define the namedtuples
    ActionCode = namedtuple(
        "ActionCode",
        ["redirect", "args", "name", "category", "canfail"],
    )
    ArgumentCode = namedtuple(
        "ArgumentCode",
        ["arg_id", "arg_required", "arg_name", "arg_type", "arg_eval"],
    )

    # Refactored action_codes dictionary with explicit keyword arguments
    {refactored_content.replace("'", '"').replace(f"){NEWLINE}", f"),{NEWLINE}").replace('Don"t', "Don't")}
    """
    file_content = (
        file_content.replace('"Open With"', "'Open With'")
        .replace(
            '"Disable Always On Display" On',
            "'Disable Always On Display' On",
        )
        .replace('"Grayscale" On', "'Grayscale' On")
        .replace('"Wallpaper" On', "'Wallpaper' On")
    )

    # Write the content to 'arg_dict.py'
    output_filename = "arg_dict.py"
    try:
        with open(output_filename, "w") as f:
            f.write(file_content)
            debug_print(
                f"Successfully wrote refactored dictionary to '/maptasker/assets/json/{output_filename}'",
            )
            os.remove("newdict.py")
            os.remove("superdict.py")
    except OSError as e:
        debug_print(f"Error writing to file '{output_filename}': {e}")
        return 8

    return 0


def format_python_dict_file(
    input_file: str,
    output_file: str,
    max_width: int = 120,
) -> None:
    """
    Reads a Python file containing a dictionary definition, formats it with a maximum line width,
    and writes it back while ensuring dictionary values do not exceed the specified width.

    :param input_file: Path to the input Python file.
    :param output_file: Path to the output formatted file.
    :param max_width: Maximum line width before breaking the next value into a new line.
    """
    try:
        # Read the Python file
        with open(input_file, encoding="utf-8") as f:
            content = f.read()
            content = f"ac = {content}"

        # Extract dictionary definition
        namespace = {}
        exec(content, {}, namespace)  # noqa: S102
        parsed_dict = None
        for value in namespace.values():
            if isinstance(value, dict):
                parsed_dict = value
                break

        if parsed_dict is None:
            msg = "Input file does not contain a valid dictionary definition."
            raise ValueError(msg)  # noqa: TRY301

        # Format and wrap dictionary values manually
        formatted_lines = ["from collections import namedtuple"]
        formatted_lines.append(
            'ActionCode = namedtuple("ActionCode", ["redirect", "args", "name", "category", "canfail"])',
        )
        formatted_lines.append(
            'ArgumentCode = namedtuple("ArgumentCode", ["arg_id", "arg_required", "arg_name", "arg_type", "arg_eval"])',
        )
        formatted_lines.append("action_codes = {")
        current_line = "    "
        for key, value in parsed_dict.items():
            ac = list_to_comma_string(value)
            ac = ac.replace('[", e"]', '["", "e"]')
            entry = f"{key!r}: ActionCode({ac}), "
            if len(current_line) + len(entry) > max_width:
                formatted_lines.append(current_line.rstrip())
                current_line = "    " + entry
            else:
                current_line += entry

        if current_line.strip():
            formatted_lines.append(current_line.rstrip())

        formatted_lines.append("}")
        for num, line in enumerate(formatted_lines):
            formatted_lines[num] = (
                line.replace("'", '"')
                .replace('"Open With"', "'Open With'")
                .replace(
                    '"Disable Always On Display" On',
                    "'Disable Always On Display' On",
                )
                .replace('"Wallpaper" On', "'Wallpaper' On")
                .replace('"Grayscale" On', "'Grayscale' On")
                # .replace(', \\"Open With\\"', "'Open With'")
                .replace('Don"t', "Don't")
                .replace('""", "e",', '"", "e",')
            )

        # Write the formatted dictionary back
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(formatted_lines))

        print(f"Formatted dictionary written to {output_file}")
    except Exception as e:  # noqa: BLE001
        print(f"Error processing dictionary file: {e}")


def list_to_comma_string(elements: list) -> str:  # noqa: D103
    def format_element(el: object) -> str:
        if isinstance(el, list):
            return f"[{', '.join(str(e) for e in el)}]"  # Retain brackets, no quotes
        return f'"{el!s}"'  # Wrap other elements in quotes

    return ", ".join(format_element(el) for el in elements)


def convert_accode() -> None:
    """Format/convert ac dictionary to a more usable format.n"""
    path = os.getcwd()
    # Change this to your input Python file containing a dictionary
    input_filename = f"{path}/newdict.py"
    if not os.path.isfile(input_filename):
        print(f"acconvert: File '{input_filename}' not found!  Program terminated.")
        return 12
    output_filename = "superdict.py"  # Change this to your desired output file
    format_python_dict_file(input_filename, output_filename, max_width=100)
    print("acconvert: Formatting completed.")
    return 0


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
            print(f"acmerge:Error: Could not write to file '{filename}'. Reason: {e}")
        except Exception as e:  # noqa: BLE001
            # Catch any other unexpected errors
            print(f"acmerge: An unexpected error occurred: {e}")


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
    # Remove any previous log file
    with contextlib.suppress(FileNotFoundError):
        os.remove("buildit.log")

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

    debug_print("acmegerge: New Action Codes dictionary save as 'newdict.py'.")

    # Convert the output of the above merge to the action_code disctionary format
    return_code = convert_accode()
    if return_code != 0:
        return

    # Add the argument names
    return_code = add_arg_names()
    if return_code != 0:
        return
