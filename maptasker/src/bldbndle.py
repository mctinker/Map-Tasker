#! /usr/bin/env python3
"""bldbndle: build the Tasker <Bundle> dictionary from a backup XML file"""

#                                                                                      #
# bldbndle: read a Tasker backup xml and merge every <Bundle> into assets/json/bundles.json #
#                                                                                      #
# NOTE: FOR DEVELOPMENT ONLY!!!  Called by proginit.py when 'build_all' is True.        #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #

import json
import os
from typing import Any
from xml.etree.ElementTree import Element  # Need for type hints

import defusedxml.ElementTree as ET

from maptasker.src import console
from maptasker.src.bundle import BUNDLES_FILE, read_bundles

# Owning xml element tag > suffix appended to the <code> value to make the key.
OWNER_SUFFIX = {"Event": "e", "State": "s", "Action": "t"}

# Default name of the Tasker backup xml to read.  What is written is bundle.BUNDLES_FILE.
DEFAULT_XML_FILE = "backup.xml"

# The plugin blurb is the specific configuration of the plugin in this backup, which is
# of no use in a generic dictionary.  Blank it out (the '-type' sub-tag is left alone).
BLANK_OUT_TAG = "com.twofortyfouram.locale.intent.extra.BLURB"


def escape_xml_text(text: str) -> str:
    """
    Put the entity references back into an element's text, leaving it exactly as it
    reads in the xml file: '&lt;' and '&gt;' stay '&lt;' and '&gt;' rather than
    being handed back as the '<' and '>' the parser decoded them into.
    '&' is escaped first (and so must be unescaped last -- see
    taskedit_addable._unescape_bundle_text, which reverses this to rebuild the xml), or a
    value holding a literal '&lt;' (from an '&amp;lt;' in the file, of which this
    backup has plenty) would be indistinguishable from an escaped '<'.
    Args:
        text (str): the element text as the xml parser decoded it
    Returns:
        str: the same text in its xml source form
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def element_to_dict(element: Element) -> Any:  # noqa: ANN401
    """
    Recursively convert an xml element into a dictionary of its sub-tags and values.
    Args:
        element (Element): the xml element to convert
    Returns:
        Any: a dict of {tag: value} for elements with children, else the element's text
    """
    children = list(element)

    # A leaf: just return its text (attributes carry the value for <Int val="1"/> etc.)
    if not children:
        if element.attrib:
            leaf = dict(element.attrib)
            if element.text and element.text.strip():
                leaf["#text"] = escape_xml_text(element.text.strip())
            return leaf
        return escape_xml_text(element.text.strip()) if element.text else ""

    # A branch: keep its attributes (<Bundle sr="arg0">, <Vals sr="val">) then map
    # each sub-tag to its value, making a list if the tag repeats.
    result = dict(element.attrib)
    for child in children:
        value = "" if child.tag == BLANK_OUT_TAG else element_to_dict(child)
        if child.tag in result:
            if not isinstance(result[child.tag], list):
                result[child.tag] = [result[child.tag]]
            result[child.tag].append(value)
        else:
            result[child.tag] = value
    return result


def get_bundles(xml_file: str) -> dict:
    """
    Read the backup xml and build a dictionary of every <Bundle> found.
    Args:
        xml_file (str): the Tasker backup xml file to read
    Returns:
        dict: dictionary keyed by the owning <code> value plus an 'e'/'s'/'t' suffix,
              each value being {'Bundle': {the <Bundle> attributes and sub-tags}}
    """
    root = ET.parse(xml_file).getroot()

    # Map each element to its parent since ElementTree has no parent pointer.
    parent_of = {child: parent for parent in root.iter() for child in parent}

    bundles = {}
    for bundle in root.iter("Bundle"):
        owner = parent_of.get(bundle)
        if owner is None:
            continue

        # Only Events, States and Actions own a code we can key on.
        suffix = OWNER_SUFFIX.get(owner.tag)
        if suffix is None:
            continue

        code = owner.findtext("code")
        if code is None:
            continue

        key = f"{code.strip()}{suffix}"

        # First bundle for a given key wins; ignore any duplicates.  Keep the <Bundle>
        # tag itself so the entry mirrors the xml: {'Bundle': {attributes and sub-tags}}.
        if key not in bundles:
            bundles[key] = {bundle.tag: element_to_dict(bundle)}

    return bundles


def load_existing_bundles(path: str) -> dict:
    """
    Read back the bundles a previously written bundles file holds.
    Args:
        path (str): a bundles.json to read, which need not exist
    Returns:
        dict: the bundles it defines, or {} if there is no such file or it cannot be read
    """
    if not os.path.isfile(path):
        return {}
    try:
        return dict(read_bundles(path))
    except (OSError, RuntimeError) as error:
        msg = f"bldbndle: could not read existing bundles from {path}: {error}"
        console.error(msg)
        return {}


def merge_bundles(existing: dict, harvested: dict) -> tuple[dict, list[str]]:
    """
    Combine the bundles already recorded with the ones just read out of a backup.

    A rebuild used to replace bundles.json outright, which quietly threw away every
    definition the new backup did not happen to contain -- and could also downgrade one
    it did, because get_bundles keeps the FIRST <Bundle> it meets for a code and a code
    can appear both fully configured and bare in the same file.  That is exactly what
    happened to 2099e: a rebuild returned it without the RELEVANT_VARIABLES payload the
    file already had.  So nothing is dropped here, and where both sides define a code
    the fuller definition wins, on the grounds that the failure being guarded against is
    truncation rather than change.  Every such decision is reported, because 'fuller' is
    a heuristic and a genuine change of format in a new Tasker release would show up
    here as a shrinking definition that should be taken rather than refused.

    Args:
        existing (dict): the bundles already recorded
        harvested (dict): the bundles read out of this backup
    Returns:
        tuple[dict, list[str]]: the merged bundles, and one note per non-obvious decision
    """
    merged = dict(existing)
    notes = []
    for key, payload in harvested.items():
        current = merged.get(key)
        if current is None:
            merged[key] = payload
        elif current != payload:
            if len(repr(payload)) > len(repr(current)):
                merged[key] = payload
                notes.append(f"{key}: took this backup's fuller definition")
            else:
                notes.append(f"{key}: kept the existing definition; this backup's holds less")
    return merged, notes


def save_bundles(bundles: dict, output_file: str) -> None:
    """
    Write the bundle dictionary out as a json file.

    One top-level entry to a line, so that a rebuild that adds or changes a definition
    shows in a diff as that line and not as a rewrite of the file.  Compact within a line:
    the file is read by a program, and the indentation was most of its size.
    Args:
        bundles (dict): the dictionary of bundles to save
        output_file (str): the json file to create
    Returns:
        None
    """
    # Sort numerically by code, then by the owner suffix, so the output is stable.
    ordered = sorted(bundles.items(), key=lambda item: (int(item[0][:-1]), item[0][-1]))
    lines = [
        f"{json.dumps(key)}: {json.dumps(value, ensure_ascii=False, separators=(',', ':'))}" for key, value in ordered
    ]
    with open(output_file, "w", encoding="utf-8") as out:
        out.write("{\n" + ",\n".join(lines) + "\n}\n")


def build_bundles(xml_file: str = "", output_file: str = "", live_file: str = "") -> int:
    """
    Merge the <Bundle> definitions in a Tasker backup xml into 'bundles.json'.
    Args:
        xml_file (str): backup xml to read.  Defaults to 'backup.xml' in the project root.
        output_file (str): json file to write.  Defaults to 'assets/json/bundles.json',
            which is the file the program reads -- a build lands where it is used, with
            no copy to make afterwards.
        live_file (str): the bundles file the program reads, merged in so that a build
            writing somewhere else still carries everything already recorded.  Defaults
            to 'assets/json/bundles.json' as well, so it matters only when output_file is
            pointed elsewhere; pass a path that does not exist to merge with the output
            file alone.
    Returns:
        int: 0 if successful, non-zero if the xml file could not be read
    """
    # Work out where everything lives: '/maptasker/src' > project root.
    src_dir = os.path.dirname(os.path.abspath(__file__))
    maptasker_dir = os.path.dirname(src_dir)
    project_root = os.path.dirname(maptasker_dir)

    if not xml_file:
        # Prefer a backup.xml in the current directory, else fall back to the project root.
        xml_file = (
            DEFAULT_XML_FILE if os.path.isfile(DEFAULT_XML_FILE) else os.path.join(project_root, DEFAULT_XML_FILE)
        )
    if not output_file:
        # Straight into the file taskedit and varxref read.  A build used to be written
        # somewhere else and copied across by hand, which is how a rebuild that had quietly
        # dropped 218 definitions could get as far as being installed.
        output_file = BUNDLES_FILE
    if not live_file:
        live_file = BUNDLES_FILE

    if not os.path.isfile(xml_file):
        msg = f"bldbndle: backup xml file not found: {xml_file}"
        console.error(msg)
        return 1

    console.say("")
    console.say(f"bldbndle: Reading {xml_file} ...")

    try:
        harvested = get_bundles(xml_file)
    except ET.ParseError as error:
        msg = f"bldbndle: error parsing {xml_file}: {error}"
        console.error(msg)
        return 2

    # Merge into everything already recorded.  Both the file the program imports and the
    # previous output are read: they are the same file when output_file is left at the
    # default, and when it is not, an earlier build's definitions would otherwise be lost.
    existing, _ = merge_bundles(
        load_existing_bundles(live_file),
        load_existing_bundles(output_file),
    )
    bundles, notes = merge_bundles(existing, harvested)
    added = len(bundles) - len(existing)

    try:
        save_bundles(bundles, output_file)
    except OSError as error:
        msg = f"bldbndle: error writing {output_file}: {error}"
        console.error(msg)
        return 3

    for note in notes:
        console.say(f"bldbndle: {note}")
    console.say(
        f"bldbndle: Build Complete.  {len(bundles)} bundles written to '{output_file}' "
        f"({added} new, {len(existing)} already recorded).",
    )
    console.say("")

    return 0
