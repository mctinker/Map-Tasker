"""Build the Project/Profile/Task/Scene lookup tables from a parsed Tasker backup."""

#! /usr/bin/env python3

#                                                                                      #
# taskertables: turn the root of a parsed backup into the tables the application        #
#               navigates it by -- and name the Profiles and Tasks that have no name.    #
#                                                                                      #
# Split out of taskerd, which still re-exports every name here and is still the only     #
# way a FILE becomes the loaded configuration.  What the split is for: sessundo rebuilds  #
# these tables after an undo, and taskerd calls sessundo (to clear the history) and       #
# timeline (to record the load) as it loads a file.  With the tables inside taskerd,      #
# sessundo had to reach back for them from inside a function; with them here it imports   #
# them at the top, and nothing in this module knows about files, history or undo.         #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
#
import re
from xml.etree.ElementTree import Element

from maptasker.src import condition
from maptasker.src.actionc import load_arg_specs
from maptasker.src.actione import get_action_code
from maptasker.src.maputil2 import strip_html_tags, truncate_string
from maptasker.src.primitem import RunState
from maptasker.src.profiles import conditions_to_name
from maptasker.src.runcfg import current_config
from maptasker.src.sysconst import UNNAMED_ITEM


# Convert list of xml to dictionary
# Optimized
def move_xml_to_table(all_xml: list, get_id: bool, name_qualifier: str) -> dict:
    """
    Given a list of Profile/Task/Scene elements, find each name and store the element and name in a dictionary.
        :param all_xml: the head xml element for Profile/Task/Scene
        :param get_id: True if we are to get the <id>
        :param name_qualifier: the qualifier to find the element's name.
        :return: dictionary that we created
    """
    new_table = {}
    for item in all_xml:
        # Get the element name
        name_element = item.find(name_qualifier)
        name = name_element.text.strip() if name_element is not None and name_element.text else ""

        # Get the Profile/Task identifier: id=number for Profiles and Tasks,
        id_element = item.find("id")
        item_id = id_element.text if get_id and id_element is not None else name

        new_table[item_id] = {"xml": item, "name": name}

    all_xml.clear()  # Ok, we're done with the list
    return new_table


# The name Tasker gives an Anchor action's label in the text get_first_action renders,
# used below to turn an unnamed Anchor Task into a readable name.  Was a local in
# get_the_xml_data until build_tasker_tables was split out of it.
_ANCHOR_LABEL = "Anchor ...with label:\n"


def build_tasker_tables(state: RunState) -> None:
    """Build PrimeItems.tasker_root_elements from PrimeItems.xml_root -- the
    Project/Profile/Task/Scene/Setting lookup tables the whole application navigates
    the backup through, including the derived names an unnamed Profile or Task is
    listed under.

    Split out of get_the_xml_data (which still calls it, and is still the only way a
    file becomes the loaded configuration) so that sessundo can rebuild the tables
    after replacing xml_root with an undo checkpoint, without a file, a parse, or any
    of the validation that only makes sense the first time.

    It writes into the global rather than returning a dict, and that is deliberate --
    see diffload.py's module comment for the trap: profiles.conditions_to_name, called
    from the unnamed-Profile pass below, writes its derived name back through
    PrimeItems.tasker_root_elements itself.  A version that filled a local dict would
    have that pass writing into whatever table the global happened to hold instead.
    """

    # Extract and transform data into Projects, Profiles, Tasks, Scenes and Services
    _move_xml_to_table = move_xml_to_table
    state.tasker_root_elements = {
        "all_projects": _move_xml_to_table(
            state.xml_root.findall("Project"),
            False,
            "name",
        ),
        "all_profiles": _move_xml_to_table(
            state.xml_root.findall("Profile"),
            True,
            "nme",
        ),
        "all_tasks": _move_xml_to_table(
            state.xml_root.findall("Task"),
            True,
            "nme",
        ),
        "all_scenes": _move_xml_to_table(
            state.xml_root.findall("Scene"),
            False,
            "nme",
        ),
        "all_services": state.xml_root.findall("Setting"),
    }

    # Assign names to Profiles that have no name = their condition.nnn (Unnamed)
    # Cache external references and methods to local variables
    # This avoids repeated global/attribute lookups in the loop
    all_profiles = state.tasker_root_elements["all_profiles"]
    _parse_condition = condition.parse_profile_condition
    _conditions_to_name = conditions_to_name
    unnamed_label = UNNAMED_ITEM
    config = current_config(state)

    # Pre-compile regex if multiple tags need cleaning (faster than multiple .replace)
    tag_cleaner = re.compile(r"</?em>")

    for profile in all_profiles.values():
        # Check if the name is missing or empty
        if not profile.get("name"):
            xml_content = profile["xml"]
            conditions = _parse_condition(xml_content, state=state)

            current_name = unnamed_label

            if conditions:
                # Assuming _to_name returns (something, name, something_else)
                _, current_name, _ = _conditions_to_name(
                    xml_content, conditions, unnamed_label, "", config, state=state
                )

            # Efficiently strip HTML tags
            if "<em>" in current_name:
                current_name = tag_cleaner.sub("", current_name)

            # Direct update to the dictionary reference
            profile["name"] = current_name

    # Get Profiles by name (mirrors all_tasks_by_name below) -- profedit.py's
    # Edit Profile feature resolves a Profile by its displayed name through this.
    state.tasker_root_elements["all_profiles_by_name"] = {
        profile["name"]: {"xml": profile["xml"], "id": key} for key, profile in all_profiles.items()
    }

    # Get Tasks by name and handle Tasks with no name.
    state.tasker_root_elements["all_tasks_by_name"] = {}
    _get_first_action = get_first_action
    for key, value in state.tasker_root_elements["all_tasks"].items():
        if not value["name"]:
            # Get the first Task Action and user it as the Task name.
            first_action = _get_first_action(value["xml"], state=state)
            # Handle special case of 'Anchor ...with label:\n'
            if _ANCHOR_LABEL in first_action:
                first_action = 'Anchor "' + first_action.split(_ANCHOR_LABEL, 1)[1]

            # Put the new name back into PrimeItems.tasker_root_elements["all_tasks"]
            value["name"] = f"{first_action.rstrip()}.{key!s} (Unnamed)"

        state.tasker_root_elements["all_tasks_by_name"][value["name"]] = {
            "xml": value["xml"],
            "id": key,
        }

    # Sort them for easier debug.
    temp = sorted(state.tasker_root_elements["all_tasks"].items())
    state.tasker_root_elements["all_tasks"] = dict(temp)
    temp = sorted(state.tasker_root_elements["all_tasks_by_name"].items())
    state.tasker_root_elements["all_tasks_by_name"] = dict(temp)


def get_first_action(task: Element, state: RunState) -> str:
    """
    Retrieve the name of the first action code from a Tasker task XML element.

    Args:
        task (Element): The XML element representing a Tasker task.

    Returns:
        str: The name of the first action's code if found, otherwise an empty string.

    Processing Logic:
        - Finds all "Action" elements within the task.
        - Searches for the first action with attribute sr="act0".
        - If found, retrieves the "code" child element of that action.
        - Looks up the action code in the action_codes dictionary and returns its name.
        - Returns an empty string if no suitable action is found.
    """
    # Build the Tasker argument codes dictionary if we don't yet have it.
    if not state.tasker_arg_specs:
        load_arg_specs()

    task_actions = task.findall("Action")
    if task_actions is not None:
        have_first_action = False
        # Go through Actions looking for the first one ("act0")
        for action in task_actions:
            action_number = action.attrib.get("sr")
            if action_number == "act0":
                have_first_action = True
                break

        if not have_first_action:
            return ""

        # Now get the Action code
        child = action.find("code")
        the_result = get_action_code(child, action, True, "t", state=state)
        clean_text = strip_html_tags(the_result)
        clean_text = (
            clean_text.replace("&nbsp;&nbsp;", "&nbsp;")
            .replace("( ", "(")
            .replace("(", "")
            .replace(")", "")
            .replace("&nbsp;", " ")
            .replace("...with label: ", "")
            .replace("&lt;", "{")
            .replace("&gt;", "}")
        )
        # Truncate the string at 30 charatcers.
        return truncate_string(clean_text, 30)
    return ""
