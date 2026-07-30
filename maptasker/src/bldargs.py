#! /usr/bin/env python3
"""bldargs: harvest missing action/condition arguments from a backup into actionc.py"""

#                                                                                      #
# bldargs: find the <Str>/<Int> arguments a real Tasker backup carries that actionc.py #
#          doesn't declare, and add them to its action_codes dictionary                #
#                                                                                      #
# NOTE: FOR DEVELOPMENT ONLY!!!  Called by proginit.py when 'build_all' is True.        #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #

import os
import re
from collections import Counter, defaultdict

import defusedxml.ElementTree as ET

from maptasker.src.actionc import action_codes
from maptasker.src.sysconst import logger

# Owning xml element tag > suffix of the action_codes key, same mapping bldbndle.py uses.
OWNER_SUFFIX = {"Event": "e", "State": "s", "Action": "t"}

# Element tags worth harvesting, mapped to their arg_type in actionc.py (the index into
# PrimeItems.tasker_arg_specs: "0"=Int, "1"=Str).
#
# <Bundle> is deliberately NOT harvested. A plugin payload is already supplied from
# bundle.py when an action/condition is synthesized (see taskedit._synthesize_bundle_arg),
# so declaring it would add nothing there -- and it would actively hurt the map output,
# because actargs.get_bundle renders whatever <Bundle> the element has without looking at
# which arg slot asked for it, so a second Bundle argument prints the same payload twice.
HARVEST_TAGS = {"Str": "1", "Int": "0"}

# Default name of the Tasker backup xml to read and of the file to update.
DEFAULT_XML_FILE = "backup.xml"
ACTIONC_FILENAME = "actionc.py"

# One entry of an ActionCode's args list, e.g.
#     ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="5", arg_eval="Package="),
_ARG_INDENT = " " * 12
_ARG_ID_RE = re.compile(r'ArgumentCode\(arg_id="(\d+)"')
_ACTION_CODE_RE = re.compile(r'^    "([^"]+)": ActionCode\($')
_ARGS_OPEN = "        args=["
_ARGS_EMPTY = "        args=[],"
_ARGS_CLOSE = "        ],"


def get_backup_arguments(xml_file: str) -> dict:
    """
    Collect the argument slots every Action/Event/State in a backup actually uses.
    Args:
        xml_file (str): the Tasker backup xml file to read
    Returns:
        dict: {action_codes key: {arg id: element tag}} -- e.g. {"2078e": {"0": "Bundle", "1": "Str"}}
    """
    root = ET.parse(xml_file).getroot()

    # An arg slot can legitimately appear with different tags across occurrences (a
    # value written as <Str> in one action and <Int> in another), so count them and
    # let the winner be decided once everything has been seen.
    tallies = defaultdict(lambda: defaultdict(Counter))
    for element in root.iter():
        suffix = OWNER_SUFFIX.get(element.tag)
        if suffix is None:
            continue
        code = element.findtext("code")
        if not code:
            continue

        key = f"{code.strip()}{suffix}"
        for child in element:
            sr = child.attrib.get("sr", "")
            if sr.startswith("arg") and sr[len("arg") :].isdigit():
                tallies[key][sr[len("arg") :]][child.tag] += 1

    return {
        key: {arg_id: tags.most_common(1)[0][0] for arg_id, tags in slots.items()} for key, slots in tallies.items()
    }


def find_missing_arguments(harvested: dict) -> dict:
    """
    Work out which harvested argument slots actionc.py doesn't declare.
    Args:
        harvested (dict): the slots found in the backup -- see get_backup_arguments
    Returns:
        dict: {action_codes key to update: {arg id: arg_type}}, sorted by arg id
    """
    missing = defaultdict(dict)
    for key, slots in harvested.items():
        action_code = action_codes.get(key)
        if action_code is None:
            continue

        # An entry that redirects has no args of its own -- the target holds them (see
        # taskedit.classify_action_addability), so that is what has to be added to.
        owner_key = action_code.redirect or key
        owner = action_codes.get(owner_key)
        if owner is None:
            continue

        declared = {arg.arg_id for arg in owner.args}
        for arg_id, tag in slots.items():
            arg_type = HARVEST_TAGS.get(tag)
            if arg_type is None or arg_id in declared or arg_id in missing[owner_key]:
                continue
            missing[owner_key][arg_id] = arg_type

    return {key: dict(sorted(slots.items(), key=lambda item: int(item[0]))) for key, slots in missing.items() if slots}


def format_argument(arg_id: str, arg_type: str) -> str:
    """
    Build the ArgumentCode source line for one harvested argument.
    Args:
        arg_id (str): the argument's number, as in its 'sr' ("arg1" -> "1")
        arg_type (str): the actionc.py argument type -- see HARVEST_TAGS
    Returns:
        str: the line to insert into an ActionCode's args list
    """
    # The backup says an argument is there and what shape it has, but not what Tasker
    # calls it, so it gets a generic label. arg_eval must not be blank: it is the
    # display prefix, and xmldata.extract_string indexes its last character.  Left as
    # the name too (arg_name=""), so taskedit._display_arg_name derives "Arg n" from it.
    arg_eval = f", Arg {arg_id}="
    return (
        f"{_ARG_INDENT}ArgumentCode("
        f'arg_id="{arg_id}", arg_required=False, arg_name="", '
        f'arg_type="{arg_type}", arg_eval="{arg_eval}"),  # harvested\n'
    )


def _split_argument_chunks(existing: list[str]) -> list[list[str]]:
    """
    Group an args list's source lines into one chunk per ArgumentCode.

    An entry is one line when it fits, but a long one is wrapped over several (its
    arg_id, arg_required, ... each on their own), so chunks are cut on parenthesis
    depth rather than per line.
    Args:
        existing (list): the args list's current source lines
    Returns:
        list: a list of line-lists, one per ArgumentCode
    """
    chunks = []
    chunk = []
    depth = 0
    for line in existing:
        chunk.append(line)
        depth += line.count("(") - line.count(")")
        if depth <= 0:
            chunks.append(chunk)
            chunk = []
            depth = 0
    if chunk:
        chunks.append(chunk)
    return chunks


def _merge_argument_lines(existing: list[str], new_arguments: dict) -> list[str]:
    """
    Merge harvested ArgumentCode lines into one args list, keeping it in arg id order.
    Args:
        existing (list): the args list's current source lines
        new_arguments (dict): {arg id: arg_type} to add
    Returns:
        list: the merged source lines
    """
    merged = []
    remaining = dict(new_arguments)
    for chunk in _split_argument_chunks(existing):
        match = _ARG_ID_RE.search("".join(line.strip() for line in chunk))
        # Emit any harvested argument that sorts before this one.
        if match:
            for arg_id in [key for key in remaining if int(key) < int(match.group(1))]:
                merged.append(format_argument(arg_id, remaining.pop(arg_id)))
        merged.extend(chunk)

    merged.extend(format_argument(arg_id, arg_type) for arg_id, arg_type in remaining.items())
    return merged


def insert_arguments(actionc_file: str, missing: dict) -> int:
    """
    Rewrite actionc.py with the harvested arguments added to their action_codes entries.

    Edits the source lines in place rather than regenerating the dictionary, so every
    entry it doesn't touch stays byte for byte as it was.
    Args:
        actionc_file (str): the actionc.py to update
        missing (dict): {action_codes key: {arg id: arg_type}} -- see find_missing_arguments
    Returns:
        int: the number of arguments added
    """
    with open(actionc_file, encoding="utf-8") as file:
        lines = file.readlines()

    output = []
    added = 0
    index = 0
    while index < len(lines):
        line = lines[index]
        output.append(line)
        index += 1

        match = _ACTION_CODE_RE.match(line.rstrip("\n"))
        if match is None or match.group(1) not in missing:
            continue
        new_arguments = missing[match.group(1)]

        # The entry's own 'args=[...]' follows its 'redirect=...' line.
        while index < len(lines) and not lines[index].startswith(_ARGS_OPEN):
            output.append(lines[index])
            index += 1
        if index >= len(lines):
            break

        if lines[index].rstrip("\n") == _ARGS_EMPTY:
            existing = []
            index += 1
        else:
            index += 1  # Step past 'args=['.
            existing = []
            while index < len(lines) and lines[index].rstrip("\n") != _ARGS_CLOSE:
                existing.append(lines[index])
                index += 1
            index += 1  # Step past the closing '],'.

        output.append(f"{_ARGS_OPEN}\n")
        output.extend(_merge_argument_lines(existing, new_arguments))
        output.append(f"{_ARGS_CLOSE}\n")
        added += len(new_arguments)

    with open(actionc_file, "w", encoding="utf-8") as file:
        file.writelines(output)

    return added


def build_arguments(xml_file: str = "", actionc_file: str = "") -> int:
    """
    Harvest the arguments a backup uses but actionc.py doesn't declare, and add them.
    Args:
        xml_file (str): backup xml to read.  Defaults to 'backup.xml' in the project root.
        actionc_file (str): the actionc.py to update.  Defaults to the one beside this file.
    Returns:
        int: 0 if successful, non-zero if the xml or actionc.py could not be read
    """
    src_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(src_dir))

    if not xml_file:
        xml_file = (
            DEFAULT_XML_FILE if os.path.isfile(DEFAULT_XML_FILE) else os.path.join(project_root, DEFAULT_XML_FILE)
        )
    if not actionc_file:
        actionc_file = os.path.join(src_dir, ACTIONC_FILENAME)

    for needed in (xml_file, actionc_file):
        if not os.path.isfile(needed):
            msg = f"bldargs: file not found: {needed}"
            logger.error(msg)
            print(msg)
            return 1

    print("")
    print(f"bldargs: Reading {xml_file} ...")

    try:
        harvested = get_backup_arguments(xml_file)
    except ET.ParseError as error:
        msg = f"bldargs: error parsing {xml_file}: {error}"
        logger.error(msg)
        print(msg)
        return 2

    missing = find_missing_arguments(harvested)
    if not missing:
        print("bldargs: No missing arguments -- actionc.py already declares everything this backup uses.")
        print("")
        return 0

    try:
        added = insert_arguments(actionc_file, missing)
    except OSError as error:
        msg = f"bldargs: error updating {actionc_file}: {error}"
        logger.error(msg)
        print(msg)
        return 3

    print(f"bldargs: Build Complete.  Added {added} arguments to {len(missing)} codes in '/maptasker/src/actionc.py'.")
    print("")

    return 0
