"""Add explicit argument names to the actionc (action codes) dictionary arguments."""

import os

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


def read_dictionary_from_file(filepath):
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
        print(f"Error: File not found at '{filepath}'")
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
            print(
                f"Warning: No dictionary named 'action_codes' found or it's not a dictionary in '{filepath}'.",
            )
            return {}
    except Exception as e:  # noqa: BLE001
        print(f"An error occurred while reading or executing the file: {e}")
        return {}


def add_arg_names() -> None:
    """Reformat superdict.py by adding the argument names to the dictionary elements"""

    if os.path.exists("superdict.py"):
        # print("\nAttempting to read dictionary from '/assets/json/superdict.py'...")
        action_codes = read_dictionary_from_file("superdict.py")

    if not action_codes:
        print(
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
            print(
                f"Successfully wrote refactored dictionary to '/maptasker/assets/json/{output_filename}'",
            )
            os.remove("newdict.py")
            os.remove("superdict.py")
    except OSError as e:
        print(f"Error writing to file '{output_filename}': {e}")
        return 8

    return 0
