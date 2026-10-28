"""Handle everything related to "Profiles" from a Tasker project's XML configuration data."""

#! /usr/bin/env python3

#                                                                                      #
# profiles: process Profiles for given project                                         #
#                                                                                      #
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from maptasker.src.core import objprops
from maptasker.src.core.dirout import add_directory_item
from maptasker.src.core.elemvals import child_text
from maptasker.src.core.format import build_tooltip_span, format_html
from maptasker.src.core.mapjump import PROFILE, Target, anchor_html
from maptasker.src.core.nameattr import add_name_attribute
from maptasker.src.core.property import get_properties
from maptasker.src.core.share import share
from maptasker.src.core.sysconst import (
    DISABLED,
    TASK_NAME_MAX_LENGTH,
    UNNAMED_ITEM,
    FormatLine,
)
from maptasker.src.core.xmldata import remove_html_tags
from maptasker.src.mapgen import condition, tasks
from maptasker.src.mapgen.actione import fix_json
from maptasker.src.mapgen.proclist import output_task_list

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from maptasker.src.core.primitem import RunState
    from maptasker.src.core.runcfg import RunConfig


# Get a specific Profile's Tasks (maximum of two:entry and exit)
def get_profile_tasks(
    the_profile: Element,
    found_tasks_list: list,
    task_output_line: list,
    config: RunConfig,
    state: RunState,
) -> list:
    """
    Get a specific Profile's Tasks (maximum of two: entry and exit).

    :param the_profile: XML element pointing to the Profile.
    :param found_tasks_list: List of tasks that have been found.
    :param task_output_line: List to store the output lines of tasks.
    :param config: the run's settings.  (single_profile_name is written here, so it is not read from it.)
    :return: List of tasks with their XML elements and names.
    """
    keys_we_dont_want = {"cdate", "edate", "flags", "id", "limit"}
    list_of_tasks = []
    single_task_name = config.single_task_name

    _get_task_name = tasks.get_task_name
    for child in the_profile:
        tag = child.tag
        if tag in keys_we_dont_want:
            continue

        if "mid" in tag:
            task_type = "Exit" if tag == "mid1" else "Entry"
            task_id = child.text
            # A <mid0/> that names no Task, or a Task that is not in the file (Health Check: BROKEN-TASK-REF), has
            # nothing to look up.
            if not task_id or task_id not in state.tasker_root_elements["all_tasks"]:
                continue

            if task_id not in found_tasks_list:
                state.task_count_for_profile += 1
            task_element, task_name = _get_task_name(
                task_id, found_tasks_list, task_output_line, task_type, config, state=state
            )
            # Add the Task to our list of found Tasks, and use the Task output line as the name.
            list_of_tasks.append({"xml": task_element, "name": task_output_line[-1]})

            if single_task_name and single_task_name == task_name:
                state.found_named_items["single_task_found"] = True
                profile_name = the_profile.find("nme")
                if profile_name is not None:
                    state.program_arguments.single_profile_name = profile_name.text or ""
                break

        elif tag == "nme":
            break

    return list_of_tasks


# Get a specific Profile's name
def _profile_id(profile: Element) -> str:
    """The id the Profile is keyed on in the table: its <id>, or where a damaged backup has none, the number in sr="profNN"."""
    return profile.findtext("id") or profile.get("sr", "")[4:]


def get_profile_name(
    profile: Element, config: RunConfig, project_name: str = "", task_names: list[str] | None = None, *, state: RunState
) -> tuple[str, str]:
    """
    Get a specific Profile's name

        :param profile: xml element pointing to the Profile
        :param config: the run's settings
        :param project_name: name of the Project this Profile belongs to (for the "Profile:" tooltip)
        :param task_names: names of the Tasks this Profile references (for the "Profile:" tooltip)
        :return: Profile name with appropriate html and the profile name itself
    """
    # If we don't have the name, then set it to 'No Profile'
    profile_id = _profile_id(profile)
    if not (the_profile_name := state.tasker_root_elements["all_profiles"].get(profile_id, {}).get("name")):
        the_profile_name = UNNAMED_ITEM

    # Make the Project name bold, italicize, underline and/or highlighted if requested
    altered_profile_name = add_name_attribute(the_profile_name, config)

    # If this is an unnamed Profile, then italicize it if not already italicised.
    if UNNAMED_ITEM in altered_profile_name and "<em>" not in altered_profile_name:
        pos = altered_profile_name.rfind(".")
        if pos != -1:
            just_the_name = altered_profile_name[:pos]
            all_but_the_name = altered_profile_name[pos:]
            altered_profile_name = f"<em>{just_the_name}</em>{all_but_the_name}"

    # Add a tooltip to the "Profile:" label showing the owning Project and this Profile's Tasks,
    # one Task per line.
    tooltip_lines = []
    if project_name:
        tooltip_lines.append(f"Project: {project_name}")
    if task_names:
        tooltip_lines.append("Tasks:")
        tooltip_lines.extend(task_names)
    profile_label = build_tooltip_span("Profile:", tooltip_lines)

    # Add html color and font for Profile name
    profile_name_with_html = format_html(
        "profile_color",
        "",
        f"{profile_label} {altered_profile_name} ",
        True,
    )

    # If we are debugging, add the Profile ID
    if config.debug:
        profile_id = child_text(profile, "id")
        profile_name_with_html = (
            f"{profile_name_with_html} {format_html('unknown_task_color', '', f', ID:{profile_id}', True)}"
        )

    return profile_name_with_html, the_profile_name


def remove_substring_and_next(
    main_string: str,
    substring: str,
    chars_to_remove_after: int = 1,
) -> str:
    """
    Searches for a substring in a string and removes the substring
    along with a specified number of characters immediately following it.

    Args:
        main_string (str): The string to search within.
        substring (str): The substring to search for.
        chars_to_remove_after (int, optional): The number of characters to remove
                                               after the substring. Defaults to 1.

    Returns:
        str: The modified string with the substring and the following
             characters removed, or the original string if the substring
             is not found.
    """
    try:
        start_index = main_string.find(substring)
        if start_index != -1:
            end_index = start_index + len(substring) + chars_to_remove_after
            return main_string[:start_index] + main_string[end_index:]
    except IndexError:
        # Handle the case where the substring is at or near the end
        end_index = start_index + len(substring)
        return main_string[:start_index]
    except TypeError:
        return main_string
    return main_string


def delete_non_blank_before_equals(text: str) -> str:
    """
    Searches a string for '=', and for each match, deletes the non-blank
    characters immediately preceding it.

    Args:
        text (str): The input string to process.

    Returns:
        str: The modified string with non-blank characters before '=' removed.
    """
    modified_text = list(text)  # Convert to a list for easier modification
    indices_to_delete = set()

    for i, char in enumerate(text):
        if char == "=":
            indices_to_delete.add(i)  # Mark the '=' for deletion
            # Look backwards for non-blank characters to delete
            j = i - 1
            while j >= 0 and modified_text[j] != " " and modified_text[j] != "=":
                indices_to_delete.add(j)
                j -= 1

    # Create a new list excluding the characters at the marked indices
    result = [char for i, char in enumerate(modified_text) if i not in indices_to_delete]
    return "".join(result)


# The condition kinds whose label is dropped from a Profile name made out of its conditions.
_NAME_CONDITION_TYPES = (
    # "State",
    "Event",
    # "Time",
    # "Application",
    # "Days of Week",
    # "Location",
    "Condition(s)",
    "Active=Any",
    "Class",
    "Priority",
)
# What a condition name is cleaned of: the tags and spacing the conditions' HTML carries.
_NAME_CLEANUPS = {
    "<em>AND</em>": "",
    "&nbsp;&nbsp;": " ",
    "is set": "set",
    "<br>": "",
    " ,": ",",
    ",  ": ", ",
}


# A colon that separates a condition from its label, and not one between two digits.
_CONDITION_COLON = re.compile(r"(?<!\d):|:(?!\d)")


def _split_conditions(profile_conditions: str) -> list[str]:
    """A Profile's condition text broken at its colons, with the Priority and the extra spacing taken out."""
    # Remove 'Priority:n'
    profile_conditions = remove_substring_and_next(profile_conditions, "Priority:")

    # Change filter of '=:=' temproarily so that we don't break it up.
    # We will change it back to '=:=' later.
    profile_conditions = profile_conditions.replace("=:=", "-+-")
    # Find and replace separate douyble-spaces
    # Make sure it is not preceded or followed by another &nbsp;
    pos = profile_conditions.find("&nbsp;&nbsp;")
    if pos != -1 and profile_conditions[pos - 1] != ";" and profile_conditions[pos + 12] != "&":
        profile_conditions = profile_conditions.replace("&nbsp;&nbsp;", " ", 1)
    # Break out the conditions, at every colon but the one inside a time (9:00): that is part of what the
    # condition says, and the name made of the pieces has no other way to get it back.
    return _CONDITION_COLON.split(
        profile_conditions.replace("&nbsp;&nbsp;Configuration Parameter(s):<br>", " ").replace("&nbsp;", ""),
    )


def _name_from_conditions(conditions: list[str]) -> str:
    """The conditions joined into one name, each with its kind's label dropped."""
    new_name = ""
    # Go thru our list of conditions.  Repair all '=:=' strings.
    for cond in conditions[1:]:  # Start at second element
        # Fix the condition
        new_cond = f":{cond.replace('-+-', '=:=')}" if "-+-" in cond else cond
        new_cond = new_cond.replace("<br>", " ")
        if (new_cond.startswith("com.") and new_cond.endswith("Class")) or len(
            new_cond,
        ) == 1:
            continue

        # Cleanup "Applcation" condition, which lost it's ':' due to the split(":") above.
        new_cond = new_cond.replace("Application", "Application:")

        # Drop any conditions we don't want.
        modified_condition = ""
        for condition_type in _NAME_CONDITION_TYPES:
            if new_cond.endswith(condition_type):
                # If the condition is a type, then set the name to the condition
                modified_condition += new_cond.replace(condition_type, "")

        if modified_condition:
            # If the condition is not empty, then set the name to the condition
            new_name += modified_condition.lstrip()
        else:
            # If the condition is empty, then set the name to the condition
            new_name += new_cond.lstrip()
    return new_name


def _tidy_condition_name(new_name: str) -> str:
    """A name made of conditions, cleaned of its HTML and cut to the length a Profile name may be."""
    # Remove text in front of any '='
    if "=" in new_name and not "=:=" in new_name:
        new_name = delete_non_blank_before_equals(new_name)

    # Get rid of priority
    priority = new_name.find("Priority")
    if priority != -1:
        new_name = new_name[: priority + 2].rstrip()

    # Italicize the name and clean it up.
    for old, new in _NAME_CLEANUPS.items():
        new_name = new_name.replace(old, new)
    # new_name = f"<em>*{new_name}</em>"

    # Truncate the name
    if len(new_name) > TASK_NAME_MAX_LENGTH:
        new_name = remove_html_tags(new_name, "")
        new_name = new_name[:35].rstrip()
    return new_name


def set_name_to_condition(
    profile_conditions: str,
    profile_name: str,
) -> str:
    """
    Set the Profile name to the condition if it is not already set.

        :param profile_conditions: The conditions of the profile.
        :param profile_name: The current profile name.
        :param profile_name_with_html: The HTML formatted profile name.
        :return: The name made from the conditions, starred; "" if there is no name to set.
    """
    if not profile_name:
        return profile_name

    new_name = _name_from_conditions(_split_conditions(profile_conditions))

    # If the Profile name is 'No Profile', then set it to the condition
    if new_name:
        new_name = _tidy_condition_name(new_name)

    return f"*{new_name}"


def conditions_to_name(
    profile: Element,
    profile_conditions: str,
    profile_name: str,
    profile_name_with_html: str,
    config: RunConfig,
    state: RunState,
) -> tuple[str, str, str]:
    """
    Update the profile name and its HTML representation based on the profile's conditions.

    Parameters
    ----------
    profile : Element
        The XML element representing the profile.
    profile_conditions : str
        The conditions associated with the profile.
    profile_name : str
        The current name of the profile.
    profile_name_with_html : str
        The HTML-formatted representation of the profile name.
    config : RunConfig
        The run's settings.

    Returns
    -------
    tuple[str, str, str]
        The HTML-formatted profile name, the updated profile name, and the conditions (made pretty if asked).
    """
    profile_name = set_name_to_condition(
        profile_conditions,
        profile_name,
    )
    # Put this name back into the master profile dictionary in PrimeItems.
    # Add a unique identifier to the name: the profile id: profile_name.id
    profile_id = _profile_id(profile)
    # Add the profile id and unnamed portion
    profile_name = f"{profile_name.rstrip()}.{profile_id} {UNNAMED_ITEM}"

    # Now cleanup the name in order to use it.
    new_profile_name = f"{profile_name.replace('<em>', '').replace('</em>', '').rstrip()}"
    if profile_id in state.tasker_root_elements["all_profiles"]:
        state.tasker_root_elements["all_profiles"][profile_id]["name"] = new_profile_name

    # Handle directory hyperlink
    if config.directory:
        add_directory_item("profiles", new_profile_name, config=config, state=state)

    # Make the conditions pretty
    if config.pretty:
        # condition_length = profile_conditions.find(":")
        # Add spacing for profile name, condition name and "Profile:"
        profile_conditions = profile_conditions.replace(",", "<br>")
        # Fix splitting up of JSON Structure Output text
        profile_conditions = fix_json(profile_conditions, "Structure Output")

    return profile_name_with_html, profile_name, profile_conditions


# Get the Profile's key attributes: limit, launcher task, run conditions
def _profile_flags_html(profile: Element) -> str:
    """The Profile's <flags> decoded for debug mode, in the launcher-task colour, or "" if it has none."""
    # Display flags for debug mode, decoded: <flags> is a bitmask, and "flags: 43" tells a
    # reader nothing that "flags: 43 (Hide In Notification, Collapsed, Ignore Settings, Run
    # Exit Task On Startup)" does not.  The names come from objprops, which owns the bit
    # layout, so this line and the Properties editor cannot disagree about what a value means.
    flags = profile.find("flags")
    if flags is None:
        return ""
    names = objprops.describe_flags(objprops.flag_bits(profile), objprops.PROFILE_FLAG_NAMES)
    decoded = f" flags: {flags.text}" + (f" ({', '.join(names)})" if names else "")
    return format_html("launcher_task_color", "", decoded, True)


def _prettify_profile_extras(temp: str) -> str:
    """Break the conditions, launcher and flags text into separate lines, indented one space."""
    blank = "&nbsp;"
    indentation = 1
    # Break at comma
    temp = temp.replace(", ", f"<br>{blank * indentation}")
    # Break at paren
    temp = temp.replace(" (", f"<br>{blank * indentation}  (")
    # Break at bracket
    return temp.replace(" [", f"<br>{blank * indentation}  [")


def build_profile_line(
    profile: Element, config: RunConfig, project_name: str = "", task_names: list[str] | None = None, *, state: RunState
) -> str:
    """
    Get the Profile's key attributes: limit, launcher task, run conditions and output it

        :param project: the Project xml element
        :param profile: the Profile xml element
        :param config: the run's settings
        :param project_name: name of the Project this Profile belongs to (for the "Profile:" tooltip)
        :param task_names: names of the Tasks this Profile references (for the "Profile:" tooltip)
        :return: Profile name
    """

    flags = ""
    condition_text = ""
    # Set up HTML to use
    disabled_profile_html = format_html(
        "disabled_profile_color",
        "",
        DISABLED,
        True,
    )
    launcher_task_html = format_html(
        "launcher_task_color",
        "",
        "[Launcher Task]",
        True,
    )

    # Look for disabled Profile
    limit = profile.find("limit")  # Is the Profile disabled?
    disabled = disabled_profile_html if limit is not None and limit.text == "true" else ""

    # Is there a Launcher Task with this Project?
    launcher_xml = profile.find("ProfileVariable")
    launcher = launcher_task_html if launcher_xml is not None else ""

    if config.debug:
        flags = _profile_flags_html(profile)

    # Get the Profile name
    profile_name_with_html, profile_name = get_profile_name(profile, config, project_name, task_names, state=state)
    unmodified_profile_name = profile_name

    # Handle directory hyperlink
    if config.directory:
        add_directory_item("profiles", profile_name, config=config, state=state)

    # Get the Profile's conditions
    if config.conditions and (profile_conditions := condition.parse_profile_condition(profile, state=state)):
        # Add the HTML
        condition_text = format_html(
            "profile_condition_color",
            "",
            f" ({profile_conditions})",
            True,
        )

    # Break it up into separate lines if we are doing pretty output
    temp = f"{condition_text} {launcher}{disabled} {flags}"
    if config.pretty:
        temp = _prettify_profile_extras(temp)

    # Okay, string it all together
    profile_info = f"{profile_name_with_html} {temp}"

    # Do final alignment of the HTML string...must include the Profile name.
    if config.pretty and condition_text:
        profile_info = align_html_text(profile_info)

    # Mark this Profile's place so a report finding can be clicked and land on it (mapjump).
    # The id comes from the "sr" attribute the same way get_profile_name reads it, rather
    # than from the name: two Profiles may share a name, and an unnamed one has none.
    anchor = anchor_html(
        Target(PROFILE, profile.attrib.get("sr", "")[4:], unmodified_profile_name, project_name), state=state
    )
    if anchor:
        state.output_lines.add_line_to_output(5, anchor, FormatLine.dont_format_line)

    # Fix the column alignment of the final html string
    # Output the Profile line
    state.output_lines.add_line_to_output(
        2,
        profile_info,
        FormatLine.dont_format_line,
    )
    return profile_name


# Process the Profile passed in.
def do_profile(
    item: Element,
    project_name: str,
    profile: Element,
    list_of_found_tasks: list,
    config: RunConfig,
    state: RunState,
) -> bool:
    """Function:
        This function searches for a specific Profile and outputs its Tasks.
    Parameters:
        - item (Element): The current item being processed.
        - project_name (str): The name of the current project.
        - profile (Element): The current profile being processed.
        - list_of_found_tasks (list): A list of all found tasks.
        - config (RunConfig): the run's settings.  single_profile_name and single_project_name
            are not read from it: they are written below and read live everywhere.
    Returns:
        - bool: True if a specific Task is being searched for, False otherwise.
    Processing Logic:
        - Checks if a specific Profile is being searched for.
        - Checks if the current item's name matches the specified Profile name.
        - If a match is found, sets the appropriate flags and clears the output list.
        - Gets the list of Tasks for the current Profile.
        - Outputs the Profile line and its properties.
        - Processes any <Share> information from TaskerNet.
        - Outputs the Tasks for the current Profile.
        - Returns True if a specific Task is being searched for, False otherwise."""
    # Are we searching for a specific Profile?
    if state.program_arguments.single_profile_name:
        # Make sure this item's name is in our list of profiles.
        if not (profile_name := state.tasker_root_elements["all_profiles"][item]["name"]):
            return False  # Not our Profile...go to next Profile ID

        if state.program_arguments.single_profile_name != profile_name:
            return False  # Not our Profile...go to next Profile ID

        # Oh, Yeah! We found the Profile we were looking for!
        # Identify items found.
        state.found_named_items["single_profile_found"] = True
        state.program_arguments.single_project_name = project_name
        state.found_named_items["single_project_found"] = True

        # Clear the output list to prepare for single Profile only
        state.output_lines.refresh_our_output(
            False,
            project_name,
            "",
        )

        # Start Profile list
        state.output_lines.add_line_to_output(1, "", FormatLine.dont_format_line)
    # Get Task xml element and name
    task_output_lines = []  # Profile's Tasks will be filled in here
    list_of_tasks = get_profile_tasks(profile, list_of_found_tasks, task_output_lines, config, state=state)

    # Examine Profile attributes and output Profile line
    # Pull the clean Task name (drop the html/markup) off the front of each Task's output line.
    task_names_for_tooltip = [task["name"].split("&nbsp;")[0] for task in list_of_tasks if task.get("name")]
    profile_name = build_profile_line(profile, config, project_name, task_names_for_tooltip, state=state)

    # Process Profile Properties
    if config.display_detail_level > 2:
        get_properties(
            "Profile:", profile, Target(PROFILE, profile.attrib.get("sr", "")[4:]), config=config, state=state
        )

    # Process any <Share> information from TaskerNet.  The Profile's identity comes from
    # its "sr" attribute the same way get_profile_name reads it -- see the anchor written
    # alongside the Profile's own line above.
    if config.taskernet:
        share(profile, "proftab", Target(PROFILE, profile.attrib.get("sr", "")[4:]), state=state, config=config)
        # Add a spacer if detail is 0
        if config.display_detail_level == 0:
            state.output_lines.add_line_to_output(
                0,
                "",
                FormatLine.dont_format_line,
            )

    # We have the Tasks for this Profile.  Now let's output them.
    # Return True = we're looking for a specific Task
    # Return False = this is a normal Task
    return output_task_list(
        list_of_tasks,
        project_name,
        profile_name,
        task_output_lines,
        list_of_found_tasks,
        True,
        config,
        state=state,
    )


# The start of the first condition in a Profile line: the condition-colour span, then the first of these
# labels -- which is what tells align_html_text how wide the first condition's label is.
_CONDITION_START = re.compile(
    r'(<span class="profile_condition_color">.*?)'
    r"(\(Event:|\(State:|\(Time:|\(Application:|\(Days of Week:|\(Location:)",
    re.DOTALL,
)
_CONDITION_LABELS = (
    "State:",
    "Event:",
    "Time:",
    "Application:",
    "Days of Week:",
    "Location:",
)
_BREAK_SPLIT = re.compile(r"(<br>)")
_AND_TAG = re.compile(r"(<em>AND</em>)")


def _align_condition_text(text: str, spaces_before_position: int, aligned_parts: list[str]) -> int:
    """Add one condition line, indented to line up with the first, to `aligned_parts`.

    Args:
        text (str): the line, with its spacing already removed.
        spaces_before_position (int): how far in the condition lines are indented so far.
        aligned_parts (list[str]): the output so far, added to in place.

    Returns:
        int: the indentation for the lines that follow.  A '[DISABLED]' line is indented 8 less,
        and so is every line after it.
    """
    # Check for <em>AND</em> and insert a break if found
    and_match = _AND_TAG.search(text)
    if and_match:
        and_position = and_match.start(1)
        # split the string at the AND tag
        before_and = text[:and_position]
        after_and = text[and_position + len("<em>AND</em>") :]
        aligned_parts.append(before_and)
        aligned_parts.append(
            "&nbsp;" * (spaces_before_position + 1) + "<em>AND</em>",
        )
        aligned_parts.append("<br>")
        aligned_parts.append(
            "&nbsp;" * (spaces_before_position) + after_and,
        )
        return spaces_before_position

    if "[&#9940;DISABLED]" in text:
        spaces_before_position -= 8
        # Add spacers since we removed them all.
        text = text.replace(
            "[&#9940;DISABLED]",
            "[&#9940;&nbsp;DISABLED]",
        )
    # Adds the appropriate spacing before the text
    if any(cond in text for cond in _CONDITION_LABELS):
        new_space_before = spaces_before_position
    else:
        new_space_before = spaces_before_position + 8
    aligned_parts.append("&nbsp;" * new_space_before + text)
    return spaces_before_position


def align_html_text(html_string: str) -> str:
    """
    Align the Profile condition arguments...
    Adds non-breaking spaces to an HTML string to align text following <br> and <em>AND</em> tags.

    This function specifically targets the given HTML structure, identifying the
    offset of the first condition and adds the appropriate number of "&nbsp;"
    to subsequent lines to align them.  It also handles the case where
    '<em>AND</em>' is present, inserting a line break and aligning the subsequent
    text.  It also realigns '[DISABLED]' and 'Priority=' text.

    Args:
        html_string: The HTML string to adjust.

    Returns:
        The modified HTML string with added "&nbsp;" for alignment.
    """
    # Find the starting position of the first occurrence of any of the target substrings
    position_match = _CONDITION_START.search(html_string)

    if not position_match:
        return html_string  # Return original if none of the substrings are found

    # The width of the first condition's label, plus the initial spacing.
    spaces_before_position = position_match.end(2) - position_match.start(2) + 20

    # NOTE: do not derive any extra indentation from where 'Configuration Parameter(s):'
    # sits in the string.  That offset is a raw *markup* offset -- it counts every
    # character of the '&nbsp;' entities reformat_html() has already sprinkled through
    # the condition (six characters apiece), so a plugin Event with configuration
    # parameters produced an indent of over a thousand spaces.  Wrapped, that pushed
    # several blank lines between every argument.  Every continuation line is aligned
    # by spaces_before_position alone, which is a count of rendered columns.

    # Format Priority and '[(icon)DISABLED]'
    html_string = html_string.replace(" Priority:", "<br>Priority:").replace(
        "[&#9940;&nbsp;DISABLED]",
        "<br>[&#9940;&nbsp;DISABLED]",
    )

    # Split the string by <br> tags within the profile_condition_color span
    parts = _BREAK_SPLIT.split(html_string)
    aligned_parts = [parts[0]]  # Keep the initial part unchanged

    # Go thru every other string in the list, starting with 1.
    for i in range(1, len(parts), 2):
        if parts[i] == "<br>":
            aligned_parts.append("<br>")

        # Remove any and all spacing.  Ignore empty strings.
        text = parts[i + 1].replace("&nbsp;", "").strip()
        if not text:
            continue
        spaces_before_position = _align_condition_text(text, spaces_before_position, aligned_parts)
    return "".join(aligned_parts)


# Go through all Projects Profiles...and output them
def process_profiles(
    project_name: str,
    profile_ids: list,
    list_of_found_tasks: list,
    config: RunConfig,
    state: RunState,
) -> None:
    """
    Go through Project's Profiles and output each
        all Tasker xml root elements, and a list of all output lines.
        :param project_name: Project's name
        :param profile_ids: list of Profiles in Project
        :param list_of_found_tasks: list of Tasks found
        :param config: the run's settings
        :return: nothing
    """

    # Go through the Profiles found in the Project
    _do_profile = do_profile
    for item in profile_ids:
        # A Profile the Project lists that is not in the file (Health Check: BROKEN-PROFILE-REF) is not output.
        if item not in state.tasker_root_elements["all_profiles"]:
            continue
        profile = state.tasker_root_elements["all_profiles"][item]["xml"]
        if profile is None:  # If Project has no profiles, skip
            return
        specific_task = _do_profile(item, project_name, profile, list_of_found_tasks, config, state=state)

        # Get out if doing a specific Task, and it was found, or not specific task but
        # found speficic Profile.  No need to process any more Profiles.
        if (specific_task and config.single_task_name and state.found_named_items["single_task_found"]) or (
            not specific_task and state.found_named_items["single_profile_found"]
        ):  # Get out if we've got the Task we're looking for
            break
        if not specific_task:
            continue
