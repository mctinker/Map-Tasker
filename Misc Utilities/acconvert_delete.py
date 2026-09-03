#! /usr/bin/env python3
"""Convert newdict to actionc"""


# This code converts the new action_codess dictionary to a format that is compatible with the NamedTuple class
# for import as 'actionc.py' in the maptasker package.
#
# Input = maptasker/assets/json/newdict.py
#
# This program is used in conjuntion with proginit.py: build = True
#
# The dictionary is formatted to ensure that the values do not exceed a maximum line width of 120 characters.
# The formatted dictionary is written to a new file.

import os


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
