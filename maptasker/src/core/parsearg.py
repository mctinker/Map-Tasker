"""MapTasker runtime argument parser"""

#! /usr/bin/env python3

#                                                                                      #
# parsearg: MapTasker runtime argument parser                                          #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #

import argparse
import json
import os
from argparse import ArgumentParser

from maptasker.src.core import console
from maptasker.src.core.mapfonts import get_monospaced_fonts
from maptasker.src.core.maputils import validate_ip_address, validate_port
from maptasker.src.core.mtexcept import MapTaskerError
from maptasker.src.core.sysconst import (
    ANTHROPIC_MODELS,
    GEMINI_MODELS,
    LLAMA_MODELS,
    OPENAI_MODELS,
    TYPES_OF_COLORS,
    logger,
)


# Validate the -view_limit value
def validate_view_limit(value: str) -> int:
    """Validate the number of lines given for -view_limit.

    Args:
        value (str): the value as it was typed on the command line

    Returns:
        int: the number of output lines to stop the Map at

    Raises:
        argparse.ArgumentTypeError: the value is not a whole number of lines, or is not
            a count that would produce any output at all.
    """
    try:
        limit = int(value)
    except ValueError:
        msg = f"'{value}' is not a number of lines."
        raise argparse.ArgumentTypeError(msg) from None
    if limit < 1:
        msg = f"{limit} would leave the Map empty: give a limit of 1 line or more."
        raise argparse.ArgumentTypeError(msg)
    return limit


# Validate mutually inclusive variables
def validate_vars(var1: str, var2: int, var3: str) -> None:
    """Validate mutually inclusive arguments
    Args:
        var1: First argument to validate
        var2: Second argument to validate
        var3: Third argument to validate
    Returns:
        None: No value is returned
    Processing Logic:
        - Check if only var1 is True and var2 and var3 are False
        - Check if only var2 is True and var1 and var3 are False
        - Check if only var3 is True and var1 and var2 are False
        - If any of the above conditions are True, raise an error"""
    if (var1 and not var2 and not var3) or (not var1 and var2 and not var3) or (not var1 and not var2 and var3):
        msg = "The -android_ipaddr, -android_port and -xandroid_file options are mutually inclusive.  If one is specified, they each must have a value."
        raise MapTaskerError(msg, 7)


# ################################################################################
# TCP IP Address validation
# ################################################################################
def ipaddr_validation(ip_address: str) -> str:
    """Validate IP address string
    Args:
        ip_address: IP address string to validate
    Returns:
        ip_address: Validated IP address string
    Validate IP address:
    - Check if IP address is valid using validate_ip_address function
    - If invalid, raise ArgumentTypeError with error message
    - If valid, simply return IP address string"""
    if ip_address != "" and not validate_ip_address(ip_address):
        msg = f"Invalid TCP IP address.  You specified {ip_address}."
        raise MapTaskerError(msg, 7)

    return ip_address


# ################################################################################
# TCP IP Address validation
# ################################################################################
def port_validation(port_number: str) -> str:
    """Validate IP address string
    Args:
        ip_address: IP address string to validate
    Returns:
        ip_address: Validated IP address string
    Validate IP address:
    - Check if IP address is valid using validate_ip_address function
    - If invalid, raise ArgumentTypeError with error message
    - If valid, simply return IP address string"""
    if port_number != "" and validate_port("", port_number) != 0:
        msg = f"Invalid port number.  You specified {port_number}."
        raise MapTaskerError(msg, 7)

    return port_number


# ################################################################################
# Validate amount of indentation -i argument
# ################################################################################
def indentation_validation(x: int) -> int:
    """
    Validate indentation level
    Args:
        x: Indentation level to validate
    Returns:
        x: Validated indentation level
    - Convert input to integer
    - Check if indentation level is greater than 10
    - Raise error if indentation is greater than 10
    - Return indentation level if valid"""
    x = int(x)
    if x > 10:
        msg = f"Maximum indentation is 10.  You specified {x}."
        raise MapTaskerError(msg, 7)
    return x


################################################################################
# Validate font entered
################################################################################
def font_validation(x: str) -> str:
    """
    Validate font name and return valid font
    Args:
        x: Font name to validate
    Returns:
        x: Validated font name
    - Check if input font name is 'help'
    - Check if input font name is in list of valid monospace fonts
    - If not valid, raise error
    - Otherwise return input font name"""
    valid_fonts = ["Courier"]
    # Get all monospaced fonts installed on this system.
    valid_fonts.extend(f for f in get_monospaced_fonts() if f not in valid_fonts)
    if x != "help" and x not in valid_fonts:
        msg = f"Invalid or non-monospace font name '{x}'."
        raise MapTaskerError(msg, 7)
    if x == "help":
        console.say(f"Valid monospace fonts:  {', '.join(valid_fonts)}")
    return x


################################################################################
# Validate file location entered
################################################################################
def file_validation(file: str) -> str:
    """
    Validate file extension for android backup file
    Args:
        file: File path to validate
    Returns:
        file: Validated file path
    - Check if file extension contains ".xml"
    - If not, raise error with message specifying missing ".xml" extension
    - Otherwise, return original file path
    """
    if file != "" and "xml" not in file:
        msg = f"Invalid android file location '{file}'.  Missing the backup '.xml' extension."
        raise MapTaskerError(msg, 7)
    return file


##################################################################################
# The command-line options are data: assets/json/cli_arguments.json.  Its "arguments" are in
# the order they are listed in the help, and each says what add_argument is told about it;
# only the checks are code, and they are named there ("type": "ipaddr") and found here.
##################################################################################
CLI_ARGUMENTS_FILE = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "json", "cli_arguments.json"),
)

# The "type" an argument names in the table, and the function that checks and converts it.
_ARGUMENT_TYPES = {
    "ipaddr": ipaddr_validation,
    "port": port_validation,
    "file": file_validation,
    "font": font_validation,
    "indent": indentation_validation,
    "view_limit": validate_view_limit,
    "int": int,
    "str": str,
}
# What an argument's "choices" may name rather than list: values the program already holds.
_ARGUMENT_CHOICES = {
    "@ai_models": lambda: OPENAI_MODELS + LLAMA_MODELS + ANTHROPIC_MODELS + GEMINI_MODELS,
}
# Table keys that are not add_argument's own, and so are not passed to it.
_NOT_ARGPARSE = {"names", "group", "hidden", "comment"}


def _text(value: str | list[str]) -> str:
    """A string from the table, which stores a multi-line one as a list of its lines."""
    return value if isinstance(value, str) else "\n".join(value)


def _argument_keywords(entry: dict) -> dict:
    """The keyword arguments add_argument is called with for one entry of the table."""
    keywords = {key: value for key, value in entry.items() if key not in _NOT_ARGPARSE}
    if entry.get("hidden"):
        keywords["help"] = argparse.SUPPRESS  # Don't display this in the help
    elif "help" in keywords:
        keywords["help"] = _text(keywords["help"])
    if "type" in keywords:
        keywords["type"] = _ARGUMENT_TYPES[keywords["type"]]
    if isinstance(keywords.get("choices"), str):
        keywords["choices"] = _ARGUMENT_CHOICES[keywords["choices"]]()
    return keywords


def _add_color_arguments(group: argparse._ArgumentGroup) -> None:
    """One '-c<kind>' option for each kind of thing that can be colored."""
    for key, value in TYPES_OF_COLORS.items():
        group.add_argument(
            f"-c{key}",
            help=f"Provide a valid color for {value}.  Example: -c{key} Blue",
            required=False,
            type=str,
            nargs=1,
        )


def build_parser() -> ArgumentParser:
    """The command-line parser, built from the table of options.

    Returns:
        ArgumentParser: the parser, ready for parse_args.
    """
    with open(CLI_ARGUMENTS_FILE, encoding="utf-8") as file:
        table = json.load(file)

    settings = table["parser"]
    parser = ArgumentParser(
        prog=settings["prog"],
        description=_text(settings["description"]),
        epilog=_text(settings["epilog"]),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # A group is made when the first option in it is, which is also where it is first
    # listed: the order of the table is the order of the help.
    groups: dict[str, argparse._ActionsContainer] = {}

    def group_for(name: str) -> argparse._ActionsContainer:
        if name not in groups:
            spec = table["groups"][name]
            groups[name] = (
                parser.add_mutually_exclusive_group()
                if spec.get("exclusive")
                else parser.add_argument_group(spec["title"])
            )
        return groups[name]

    for entry in table["arguments"]:
        target = group_for(entry["group"]) if "group" in entry else parser
        if entry.get("expand") == "colors":
            _add_color_arguments(target)
        else:
            target.add_argument(*entry["names"], **_argument_keywords(entry))
    return parser


##################################################################################
# Get the program arguments from the command line
def runtime_parser() -> argparse.Namespace:
    """
    Get the program arguments from the command line
    Returns:
        Namespace: the options given, with the defaults for those that were not
    Processing Logic:
        - Build the argument parser from the table of options
        - Parse the arguments
        - Make certain the three Android options are given together, if any is
    """
    parser = build_parser()
    args = parser.parse_args()
    if args is None:
        # No arguments provide
        parser.print_help()

    # Make certain that if android args entered, they are inclusive.
    elif args.android_ipaddr or args.android_port or args.android_file:
        validate_vars(
            args.android_ipaddr[0],
            args.android_port[0],
            args.android_file[0],
        )
        output_results(args)
    return args


# Log the arguments the program was given
def output_results(args: object) -> None:
    # Arguments have been provided
    """Outputs logging information about function arguments
    Args:
        args: The arguments passed to the function
    Returns:
        None: This function does not return anything
    - Format the arguments into a message string
    - Call the logger to output an info log message with the arguments"""
    message_out = f"Arguments: {args}"
    logger.info(message_out)
