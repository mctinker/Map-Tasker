"""Module containing action runner logic."""

#! /usr/bin/env python3

#                                                                                      #
# xmldata: deal with the xml data                                                      #
#                                                                                      #
from __future__ import annotations

import codecs
import io
import re
from typing import TYPE_CHECKING

import defusedxml.ElementTree

from maptasker.src.core.action import drop_trailing_comma, process_xml_list
from maptasker.src.core.maputil2 import translate_string

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element, ElementTree

    from maptasker.src.core.actionc import ArgumentCode


# See if the xml tag is one of the predefined types and return result
def tag_in_type(tag: str, flag: bool) -> bool:
    """
    Evaluate the xml tag to see if it is one of our predefined types

    Parameters: the tag to evaluate, and whether this is a Scene or not (which
            determines which list of types to look for)

    Returns: True if tag found, False otherwise
    """
    scene_task_element_types = {
        "ListElementItem",
        "ListElement",
        "TextElement",
        "ImageElement",
        "ButtonElement",
        "OvalElement",
        "EditTextElement",
        "RectElement",
        "WebElement",
        "CheckBoxElement",
        "DoodleElement",
        "PickerElement",
        "SceneElement",
        "SliderElement",
        "SpinnerElement",
        "SwitchElement",
        "ToggleElement",
        "VideoElement",
        "lj",  # Scene V2 compressed JSON element
        "PropertiesElement",  # this element doesn't contain anything of value/import
    }
    scene_task_click_types = {
        "checkchangeTask",
        "clickTask",
        "focuschangeTask",
        "itemselectedTask",
        "keyTask",
        "linkclickTask",
        "longclickTask",
        "mapclickTask",
        "maplongclickTask",
        "pageloadedTask",
        "strokeTask",
        "valueselectedTask",
        "videoTask",
        "itemclickTask",
        "itemlongclickTask",
    }
    # Return a boolean: True if tag found in the appropriate list, False otherwise
    return (flag and tag in scene_task_element_types) or (not flag and tag in scene_task_click_types)  # Boolean


# An argument whose evaluation is a list: its value is a code, and the list says what the code means.
def evaluate_listed_value(argeval: list[str], value: str, the_arg: str, arg: ArgumentCode | None) -> str:
    """
    Say what an argument's value means, according to the list its table entry carries.

    The list is either ["", "e", "text"] -- the value is a flag, and the text is shown when it is
    set -- or ["prefix", "l", "key"] -- the value is a position in the lookup table for the key.

    Args:
        argeval (list[str]): The argument's evaluation, from the action table.
        value (str): The argument's value as the XML holds it.
        the_arg (str): The name of the argument (e.g. 'arg3'), for the error message.
        arg (ArgumentCode | None): This argument, from action_codes; its name labels a lookup.

    Returns:
        str: What the value means, with the trailing comma the list's pieces leave.
    """
    result: list[str] = []
    name = arg[2] if arg is not None else ""
    if len(argeval) > 1:
        # Handle the special case of "e" by adding a space before the value..expects a blank in element 0.
        new_argeval = ["", "e", argeval[1]] if argeval[0] == "e" else argeval
        # Handle special case of 'l' lookup.
        new_argeval = [f"{name}=", "l", argeval[2]] if name and argeval[1] == "l" else new_argeval
    else:
        new_argeval = argeval

    # Process the argument evaluation
    process_xml_list([new_argeval], 0, value, result, [the_arg])
    return " ".join(result)


# We have an integer.  Evaluaate it's value based oon the code's evaluation parameters.
def extract_integer(
    code_action: Element,
    the_arg: str,
    argeval: str | list[str],
    arg: ArgumentCode,
) -> str:
    """
    Extract an integer value from an XML action element.

    Args:
        code_action (XML element): The XML action element to search.
        the_arg (str): The name of the argument to search for.
        argeval (str | list): The evaluation to perform on the integer.
        arg (ArgumentCode): This argument, from action_codes.

    Returns:
        str: The result of the integer evaluation.
    """

    # Find the first matching <Int> element with the desired 'sr' attribute.
    #
    # By hand rather than through find("./Int[@sr='...']"): a path with a predicate in it
    # is parsed, compiled and then walked by ElementTree's own Python code, and this is
    # asked for once per argument of every action in the configuration.  Walking the
    # action's children here is the same search without any of that.
    int_element = next(
        (child for child in code_action if child.tag == "Int" and child.get("sr") == the_arg),
        None,
    )

    if int_element is None:
        return ""

    # 1. Use .get() for the attribute (fast)
    # 2. Use findtext() instead of checking if .find() is not None and then extracting text
    the_int_value = int_element.get("val") or int_element.findtext("var", default="")

    if not the_int_value:
        return ""  # No valid integer or variable name found

    # Aeguement evaluation is a list
    if isinstance(argeval, list):
        final_result = evaluate_listed_value(argeval, the_int_value, the_arg, arg)

    # Argument evaluation is a string.
    else:
        # If eval is missing, just use the argujment name.
        if not argeval:
            argeval = arg.arg_name

        # If boolean and this is a plain text string, then determine if 'selected' or 'Set'
        if arg.arg_type == "3":
            # Selected
            if the_int_value == "1":
                final_result = argeval + " (selected)" if argeval != "Set" else ",Set"
            # Unselected
            elif argeval == "Set":
                final_result = ",Unset"
            else:
                final_result = ""
        else:
            # If it doesn't have an '=', then. add it.
            if argeval[-1] != "=":
                argeval += "="
            final_result = argeval + the_int_value

    # Drop trailing comma if necessary
    return drop_trailing_comma([final_result])[0] if final_result else ""


# Extracts and returns the text from the given argument as a string.
def extract_string(
    action: Element,
    arg: str,
    argeval: str | list[str],
    argument: ArgumentCode | None = None,
) -> str:
    """
    Extracts a string from an XML action element.

    Args:
        action (XML element): The XML action element to search.
        arg (str): The name of the string argument to search for.
        argeval (str | list[str]): The prefix to add to the matched string, or the list that says what
            its value means (see evaluate_listed_value).
        argument (ArgumentCode | None): This argument, from action_codes, when the evaluation is a list.

    Returns:
        str: Extracted string with prefix or an empty string.
    """
    if isinstance(argeval, list):
        return _extract_listed_string(action, arg, argeval, argument)

    # Find the first matching <Str> element with the desired 'sr' attribute.  Walks the
    # action's children directly rather than building the list of every <Str> first --
    # the match is usually found long before the end of it, and this runs once per
    # argument of every action in the configuration.
    str_element = next(
        (child for child in action if child.tag == "Str" and child.get("sr") == arg),
        None,
    )

    if str_element is None or str_element.text is None:
        return ""  # No matching element found

    # Extract text value with prefix
    prefix = argeval
    new_argeval = prefix if prefix.endswith("=") else f"{prefix}="
    extracted_text = (
        f"{prefix}(carriage return)" if str_element.text == "\n" else f"{new_argeval}{str_element.text or ''}"
    )

    # Drop trailing comma if necessary
    return drop_trailing_comma([extracted_text])[0] if extracted_text else ""


# A string argument whose table entry carries a list evaluation, rather than a prefix.
def _extract_listed_string(
    action: Element,
    arg: str,
    argeval: list[str],
    argument: ArgumentCode | None,
) -> str:
    """
    The meaning of a string argument that is really a code.

    The table calls these arguments strings, but what they hold is a code (a flag, or a position in a
    lookup) that the list in the table says how to read -- and Tasker writes some of them as <Int>
    rather than <Str>.  So the value is taken from either, and a %variable is shown as it stands.

    Args:
        action (XML element): The XML action element to search.
        arg (str): The name of the argument to search for (e.g. 'arg3').
        argeval (list[str]): The evaluation from the action table.
        argument (ArgumentCode | None): This argument, from action_codes.

    Returns:
        str: What the value means, or an empty string if the argument is not there or is empty.
    """
    element = next(
        (child for child in action if child.tag in {"Str", "Int"} and child.get("sr") == arg),
        None,
    )
    if element is None:
        return ""
    value = (element.text if element.tag == "Str" else element.get("val") or element.findtext("var")) or ""
    value = value.strip()
    if not value:
        return ""

    # A flag that is not set leaves nothing but its separator behind.
    result = evaluate_listed_value(argeval, value, arg, argument)
    return drop_trailing_comma([result])[0].strip() if result else ""


def is_tasker_object(text: str, blank_trailer: bool) -> bool:
    """
    Checks if the input string contains any of the following keywords,
    where spaces are replaced with '&nbsp;':
    'Task:&nbsp;', 'Profile:&nbsp;', 'Profile:$nbsp;', or 'Scene:&nbsp;'.

    Args:
        text: The string to be tested.
        blank_trailer: True if keyword followed by space, otherwise followed by '&nbsp;'

    Returns:
        True if any of the modified keywords are found in the text, False otherwise.
    """
    keywords_nbsp = [
        "Task:&nbsp;",
        "Profile:&nbsp;",
        "Profile:$nbsp;",
        "Scene:&nbsp;",
        "Task <a href=#tasks_",
    ]
    if blank_trailer:
        keywords_nbsp = [translate_string(keyword.replace("&nbsp;", " ")) for keyword in keywords_nbsp]
    return any(keyword in text for keyword in keywords_nbsp)


# Given a string, remove all HTML (anything between < >) tags from it
# Precompile regex for maximum performance
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def remove_html_tags(text: str, replacement: str) -> str:
    """
    Remove HTML tags from a string efficiently.
    Keeps strings untouched if they appear to be Tasker/Title text.
    NOTE: Optimized for performance.
    """
    # Skip HTML stripping for specific conditions
    if is_tasker_object(text, False) or "&nbsp;&nbsp;Title=" in text:
        return text

    # If there's no '<', skip regex completely (fast path)
    if "<" not in text:
        return text

    # Use precompiled regex substitution (C-level speed)
    cleaned = _HTML_TAG_RE.sub(replacement, text)

    # Return cleaned text or replacement if empty
    return cleaned if cleaned.strip() else replacement


# A start tag, and a closing quote that runs straight into the next attribute name.
_START_TAG = re.compile(rb"<[A-Za-z_][^<>]*>")
_ATTRIBUTE_GAP = re.compile(rb'"(?=[A-Za-z_][\w.:-]*=")')


def separate_attributes(xml_bytes: bytes) -> bytes:
    """Insert the whitespace XML requires between attributes.

    Some Tasker versions (e.g. 6.7.6-beta) write compact backups such as
    <TaskerData sr=""dvi="1"tv="6.7.6-beta">, which strict XML parsers reject as
    "not well-formed (invalid token)".  Only start tags are touched; text content
    cannot hold a raw '<', so it is left as is.
    """
    return _START_TAG.sub(lambda tag: _ATTRIBUTE_GAP.sub(b'" ', tag.group()), xml_bytes)


# The byte-order marks, longest first: the UTF-32 little-endian mark begins with the UTF-16 one.
_BYTE_ORDER_MARKS = (
    (codecs.BOM_UTF32_LE, "utf-32"),
    (codecs.BOM_UTF32_BE, "utf-32"),
    (codecs.BOM_UTF8, "utf-8-sig"),
    (codecs.BOM_UTF16_LE, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16"),
)
# UTF-16 with no mark still begins "<?" with a zero byte beside each character (XML 1.0, appendix F).
_UNMARKED_UTF16 = ((b"<\x00?\x00", "utf-16-le"), (b"\x00<\x00?", "utf-16-be"))
# The encoding an XML declaration names.  Looked for in the first bytes only, as a parser does.
_DECLARED_ENCODING = re.compile(rb"""^\s*<\?xml[^>]*?\bencoding\s*=\s*["']([A-Za-z][A-Za-z0-9._-]*)["']""")


def backup_as_utf8(data: bytes) -> bytes:
    """A backup's bytes as UTF-8, whatever encoding the file is in.

    The order is the one that cannot turn a good file into a wrong one.  A byte-order mark is
    decisive.  Without one, bytes that are valid UTF-8 are UTF-8 -- which is what Tasker writes, and
    which a file that merely *declares* something else (an editor that changed the label and not the
    bytes) also is -- and so are plain ASCII ones, which read the same in every encoding.  Only bytes
    that are not valid UTF-8 are read as the encoding the XML declaration names, and a file that names
    none, or one this interpreter has no codec for, is refused rather than guessed at.

    Raises:
        UnicodeDecodeError: the bytes are not in the encoding they claim, or in none that can be found.
    """
    for mark, codec in _BYTE_ORDER_MARKS:
        if data.startswith(mark):
            return data.decode(codec).encode("utf-8")
    for start, codec in _UNMARKED_UTF16:
        if data.startswith(start):
            return data.decode(codec).encode("utf-8")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as not_utf8:
        declared = _DECLARED_ENCODING.match(data[:512])
        if declared is None:
            raise
        name = declared.group(1).decode("ascii")
        try:
            codecs.lookup(name)
        except LookupError:
            raise not_utf8 from None
        return data.decode(name).encode("utf-8")
    return data


def parse_tasker_xml(file_to_parse: str) -> ElementTree:
    """Parse a Tasker backup file, tolerating attributes with no whitespace between them.

    The file is read, never written: whatever its encoding (see backup_as_utf8), what is parsed is a
    copy held in memory, and the file on disk is the same bytes afterwards.

    Raises ET.ParseError / UnicodeDecodeError when the file is bad for any other reason.
    """
    with open(file_to_parse, "rb") as xml_file:
        data = backup_as_utf8(xml_file.read())
    try:
        return _parse_utf8(data)
    except defusedxml.ElementTree.ParseError:
        repaired = separate_attributes(data)
        if repaired == data:
            raise
        return _parse_utf8(repaired)


def _parse_utf8(data: bytes) -> ElementTree:
    """The tree for XML bytes already in UTF-8."""
    return defusedxml.ElementTree.parse(io.BytesIO(data), parser=defusedxml.ElementTree.XMLParser(encoding="utf-8"))
