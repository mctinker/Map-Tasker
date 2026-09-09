#! /usr/bin/env python3
"""bldargs: harvest missing action/condition arguments from a backup into the overlay"""

#                                                                                      #
# bldargs: find the <Str>/<Int> arguments a real Tasker backup carries that the action #
#          code tables don't declare, and add them to action_overlay.json              #
#                                                                                      #
# NOTE: FOR DEVELOPMENT ONLY!!!  Called by proginit.py when 'build_all' is True.        #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #

import json
import os
from collections import Counter, defaultdict

import defusedxml.ElementTree as ET

from maptasker.src import console
from maptasker.src.actionc import action_codes

# Owning xml element tag > suffix of the action_codes key, same mapping bldbndle.py uses.
OWNER_SUFFIX = {"Event": "e", "State": "s", "Action": "t"}

# Element tags worth harvesting, mapped to their arg_type (the index into
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

# Where the harvested arguments go.  Tasker publishes its Task actions completely --
# across 57 real backups not one missing argument landed on a published code -- so
# everything harvested belongs to an "extra" entry: an Event, State, plugin or Scene
# element that task_all_actions.json does not describe at all.
OVERLAY_FILENAME = os.path.join("..", "assets", "json", "action_overlay.json")


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
    Work out which harvested argument slots the action code tables don't declare.
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


def harvested_argument(arg_id: str, arg_type: str) -> list:
    """
    Build the overlay argument record for one harvested argument.
    Args:
        arg_id (str): the argument's number, as in its 'sr' ("arg1" -> "1")
        arg_type (str): the argument type -- see HARVEST_TAGS
    Returns:
        list: [arg_id, arg_required, arg_name, arg_type, arg_eval], the overlay's arg shape
    """
    # The backup says an argument is there and what shape it has, but not what Tasker
    # calls it, so it gets a generic label. arg_eval must not be blank: it is the
    # display prefix, and xmldata.extract_string indexes its last character.  Left as
    # the name too (arg_name=""), so taskedit._display_arg_name derives "Arg n" from it.
    return [arg_id, False, "", arg_type, f", Arg {arg_id}="]


def format_overlay(overlay: dict) -> str:
    """
    Serialize action_overlay.json with one action code per line.
    Args:
        overlay (dict): the whole overlay, as loaded
    Returns:
        str: the file's contents

    json.dump's own indentation would spread one action code over dozens of lines and
    make the diff of a single added argument unreadable, so each code gets exactly one
    line and the file stays reviewable.
    """

    def block(mapping: dict) -> str:
        """One code per line, numeric codes in numeric order and named ones last."""
        keys = sorted(mapping, key=lambda k: (k[:-1].zfill(12), k) if k[:-1].isdigit() else ("~" + k, k))
        entries = ",\n".join(
            f"    {json.dumps(key)}: {json.dumps(mapping[key], ensure_ascii=False, sort_keys=True)}" for key in keys
        )
        return "{\n" + entries + "\n  }"

    comment = json.dumps(overlay["_comment"], indent=2).replace("\n", "\n  ")
    return (
        f'{{\n  "_comment": {comment},\n  "eval": {block(overlay["eval"])},\n  "extra": {block(overlay["extra"])}\n}}\n'
    )


def insert_arguments(overlay_file: str, missing: dict) -> int:
    """
    Add the harvested arguments to action_overlay.json's 'extra' entries.
    Args:
        overlay_file (str): the action_overlay.json to update
        missing (dict): {code key: {arg id: arg_type}} -- see find_missing_arguments
    Returns:
        int: the number of arguments added

    A code that is not in 'extra' is one task_all_actions.json publishes, and Tasker's
    own table is authoritative for those.  Adding an argument would mean overriding that
    entry outright and freezing it against the next Tasker release, so this reports the
    code and leaves it alone rather than deciding on its own.
    """
    with open(overlay_file, encoding="utf-8") as file:
        overlay = json.load(file)

    added, published = 0, {}
    for key, slots in missing.items():
        entry = overlay["extra"].get(key)
        if entry is None:
            published[key] = slots
            continue
        entry["args"].extend(harvested_argument(arg_id, arg_type) for arg_id, arg_type in slots.items())
        entry["args"].sort(key=lambda arg: int(arg[0]))
        added += len(slots)

    for key, slots in published.items():
        console.say(
            f"bldargs: {key} is published in task_all_actions.json and was NOT changed -- "
            f"this backup uses argument(s) {', '.join(sorted(slots, key=int))} that Tasker "
            f"does not declare.  Add an 'extra' entry by hand if that is really wanted.",
        )

    if added:
        with open(overlay_file, "w", encoding="utf-8") as file:
            file.write(format_overlay(overlay))

    return added


def build_arguments(xml_file: str = "", overlay_file: str = "") -> int:
    """
    Harvest the arguments a backup uses but the action code tables don't declare.
    Args:
        xml_file (str): backup xml to read.  Defaults to 'backup.xml' in the project root.
        overlay_file (str): the action_overlay.json to update.  Defaults to the real one.
    Returns:
        int: 0 if successful, non-zero if the xml or the overlay could not be read
    """
    src_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(src_dir))

    if not xml_file:
        xml_file = (
            DEFAULT_XML_FILE if os.path.isfile(DEFAULT_XML_FILE) else os.path.join(project_root, DEFAULT_XML_FILE)
        )
    if not overlay_file:
        overlay_file = os.path.join(src_dir, OVERLAY_FILENAME)

    for needed in (xml_file, overlay_file):
        if not os.path.isfile(needed):
            msg = f"bldargs: file not found: {needed}"
            console.error(msg)
            return 1

    console.say("")
    console.say(f"bldargs: Reading {xml_file} ...")

    try:
        harvested = get_backup_arguments(xml_file)
    except ET.ParseError as error:
        msg = f"bldargs: error parsing {xml_file}: {error}"
        console.error(msg)
        return 2

    missing = find_missing_arguments(harvested)
    if not missing:
        console.say(
            "bldargs: No missing arguments -- the action code tables already declare everything this backup uses."
        )
        console.say("")
        return 0

    try:
        added = insert_arguments(overlay_file, missing)
    except OSError as error:
        msg = f"bldargs: error updating {overlay_file}: {error}"
        console.error(msg)
        return 3

    console.say(f"bldargs: Build Complete.  Added {added} argument(s) to '{overlay_file}'.")
    console.say("")

    return 0
