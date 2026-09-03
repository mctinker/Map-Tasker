"""Add explicit argument names to the actionc (action codes) dictionary arguments."""  # noqa: INP001

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


def add_arg_names() -> None:
    """Reformat superdict.py by adding the argument names to the dictionary elements"""

    if os.path.exists("config.py"):
        print("\nAttempting to read dictionary from 'config.py'...")
        action_codes = read_dictionary_from_file("config.py")

    if not action_codes:
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
        print(f"Successfully wrote refactored dictionary to '{output_filename}'")
    except OSError as e:
        print(f"Error writing to file '{output_filename}': {e}")

    return 0
