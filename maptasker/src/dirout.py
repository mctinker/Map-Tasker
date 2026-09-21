#! /usr/bin/env python3
"""
dirout: Add the directory to the output queue

This module contains functions to create and manage the directory output queue.
"""

#                                                                                      #
# dirout: Add the directory to the output queue                                        #
#                                                                                      #
#         This code is tricky.  We create the directory as we build the output queue,  #
#         and then print it while processing/writing to file the output queue.         #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING

from maptasker.src.maputils import fix_hyperlink_name
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import (
    HOTLINK_STYLE,
    NORMAL_TAB,
    TABLE_BACKGROUND_COLOR,
    TABLE_BORDER,
    UNNAMED_ITEM,
    FormatLine,
)

if TYPE_CHECKING:
    from maptasker.src.runcfg import RunConfig

period = "."

# The id of an anchor the directory can point at: the per-item anchors written by
# lineout.add_directory_link and proclist.add_task_hyperlink (<a id="tasks_My_Task"></a>)
# and the two the Trailing Information entries go to.  Deliberately narrower than "any
# id": the Map is full of other anchors (mapjump's "mt-" ones, for instance) that no
# directory entry ever refers to, and there is no point collecting them.
ANCHOR_ID_PATTERN = re.compile(
    r'id="((?:projects|profiles|tasks|scenes)_[^"]*|grand_totals|unreferenced_variables)"',
)


# Every directory anchor id found in the given output lines.
def collect_anchor_ids(output_lines: list) -> set:
    """
    Gather the ids of the directory's anchors in the given output lines.
        Args:
            output_lines (list): output lines to scan

        Returns:
            set: the anchor ids found in them
    """
    anchor_ids = set()
    for item in output_lines:
        # Legacy entries can still be [level, line] rather than a bare line (see format.format_line).
        line = item[1] if isinstance(item, list) else item
        # Most lines carry no anchor at all, and this check is a good deal cheaper than
        # running the pattern over every one of them.
        if 'id="' in line:
            anchor_ids.update(ANCHOR_ID_PATTERN.findall(line))
    return anchor_ids


# Anchor ids that the view limit's cut drops from the output file.
def unreachable_anchors(output_lines: list, view_limit: int) -> set:
    """
    Determine which anchors the view limit keeps out of the output file.

    bildhtml.write_out_the_file stops writing once it gets past the view limit, so an
    anchor beyond that point never reaches the file and a directory hyperlink aimed at it
    would take the user nowhere.  Only ids found solely past the cut are returned: an id
    that also appears within the limit is still reachable, and one we cannot find at all
    is left alone, so an entry is only ever demoted to plain text when its target is
    known to have been dropped.

        Args:
            output_lines (list): the full output queue, before the directory is inserted
            view_limit (int): the last output line number that gets written

        Returns:
            set: the anchor ids that are not in the written output
    """
    # Everything fits: nothing is cut and every hyperlink still lands somewhere.
    if len(output_lines) <= view_limit + 1:
        return set()
    within_limit = collect_anchor_ids(output_lines[: view_limit + 1])
    return collect_anchor_ids(output_lines[view_limit + 1 :]) - within_limit


# Build a single directory entry: a hyperlink, or plain text if it can't be reached.
def directory_entry(href: str, anchor: str, display_name: str, dropped_anchors: set) -> str:
    """
    Build the directory's cell for one item.

        Args:
            href (str): the hyperlink target, minus the leading "#"
            anchor (str): the id of the anchor the hyperlink lands on
            display_name (str): the name to show the user
            dropped_anchors (set): anchor ids the view limit kept out of the output

        Returns:
            str: the hyperlink, or just the name as plain text if the view limit cut the
                item it points to out of the output.
    """
    if anchor in dropped_anchors:
        return display_name
    return f'<a href=#{href} style="{HOTLINK_STYLE}">{display_name}</a>'


# Search a list of lists for a given string.  Return True if found.
def search_lists(search_string: str, list_of_lists: list) -> bool:
    """
    Search a list of lists for a given string.  Return True if found.
        Args:
            search_string (str): string to search for
            list_of_lists (list): pointer to the list of lists to search through

        Returns:
            boolean: True if string found in list of lists, False otherwise
    """
    # Convert list to a set for faster performance.
    lookup = {item[1] for item in list_of_lists}
    return search_string in lookup


# Add directory item (Project/Profile/Task/Scene) to our dictionary of items
def add_directory_item(key: str, name: str) -> None:
    """
    We are doing a directory.  Add the Project/Profile/Task/Scene name and hyperlink name to our dictionary of items
        Args:
            key (str): "project", "profile", "task", or "scene"
            directory_head (list): pointer to
                PrimeItems.directory_items"]["directory_head"]
                where "directory_head is "project", "profile", "task", or "scene"
            name (str): name of the Project/Profile/Task/Scene
    """
    # If it is an unnamed task, and we are not doing the list of unnamed tasks, then skip it.
    if UNNAMED_ITEM in name and not PrimeItems.program_arguments["list_unnamed_items"]:
        return
    # Clean up the name
    # name = name.replace(" (Scene)", "")
    # Only set values if we haven't already done this named item
    if not search_lists(name, PrimeItems.directory_items[key]) and name != UNNAMED_ITEM:
        # fix_hyperlink_name rather than a plain swap of spaces for underscores, for the
        # reason proclist.add_task_hyperlink gives: a name is the user's own text and can
        # hold a "<" or a ">" -- "System >> Say Response" -- which ends the tag it is
        # written into.  This one name becomes both the anchor and the hyperlink that
        # looks for it, so escaping it here keeps the two of them saying the same thing.
        hyperlink_name = fix_hyperlink_name(name)
        PrimeItems.directory_items["current_item"] = f"{key}_{hyperlink_name}"
        PrimeItems.directory_items[key].append([hyperlink_name, name])
    else:
        PrimeItems.directory_items["current_item"] = ""


#######################################################################################
# Given a list of hyperlinks,determine the optimum number of rows and columns
#######################################################################################
def calculate_grid_size(items: list, max_columns: int) -> tuple:
    """
    Calculates the size of a grid based on the number of items in a list.
    The column width can be no larger than 6

    Args:
        items (list): A list of items.
        max_columns: maximum width/column size allowed

    Returns:
        tuple: A tuple containing the number of rows and columns in the grid.

    Example:
        ```python
        items = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        num_rows, num_columns = calculate_grid_size(items)
        print(f"Number of rows: {num_rows}")
        print(f"Number of columns: {num_columns}")
        ```
    """
    num_items = len(items)
    num_columns = min(
        max_columns,
        num_items,
    )  # Limit the number of columns to 6 at most
    num_rows = math.ceil(num_items / num_columns)
    return num_rows, num_columns


#######################################################################################
# Given a list of hyperlinks, build a table and output the table
#######################################################################################
def output_table(hyperlinks: list, max_columns: int) -> None:
    """
    Generates a Python docstring for the `output_table` function.

    The function takes two parameters: `hyperlinks` and max_columns.
    It outputs a table based on the provided primary items and hyperlinks.

    Args:
        hyperlinks (list): A boolean value indicating whether hyperlinks should be
            included in the table.
        max_columns (int): Integer for the number of columns to make the table.

    Returns:
        None
    """

    # max_columns = 6  # Maximum number of columns
    num_rows, max_columns = calculate_grid_size(hyperlinks, max_columns)

    # Now build the html needed for the table with the hyperlinks in it
    html_table = generate_html_table(hyperlinks, num_rows, max_columns)

    PrimeItems.output_lines.add_line_to_output(
        5,
        html_table,
        ["", "profile_color", FormatLine.add_end_span],
    )


#######################################################################################
# Given a number of rows and columns and data, format it as a table in html
#######################################################################################
def generate_html_table(data: list, rows: int, columns: int) -> str:
    """
    Generates an HTML table from a given data dictionary.

    The function takes a data dictionary and converts it into an HTML table format.

    Args:
        data (dict): A dictionary containing the data for the table, already in the order
            it is to appear in.  Sorting is the caller's, since an entry the view limit
            reduced to plain text no longer sorts alongside the hyperlinks.
        rows: number of rows for table
        columns: number of columns for table

    Returns:
        str: The generated HTML table.

    Example:
        ```python
        data = {
            "header": ["Name", "Age", "City"],
            "rows": [
                ["John Doe", 25, "New York"],
                ["Jane Smith", 30, "Los Angeles"],
                ["Mike Johnson", 35, "Chicago"],
            ],
        }

        html_table = generate_html_table(data)
        print(html_table)
        ```
    """

    # Set up the variables
    html = f'{TABLE_BORDER}<table style="width:100%;margin-left: 20;text-align:left;background-color:\
    {TABLE_BACKGROUND_COLOR};">\n'
    index = 0

    # Build our table
    for _ in range(rows):
        html += "  <tr>\n"
        for _ in range(columns):
            if index < len(data):
                html += f"    <td>{data[index]}</td>\n"
                index += 1
            else:
                html += "    <td></td>\n"
        html += "  </tr>\n"

    html += "</table>"
    return html


#######################################################################################
# Output directory for information at the bottom of the output
#######################################################################################
def do_trailing_matters(config: RunConfig, dropped_anchors: set) -> None:
    """
    Create a hyperlinks for key items that are at the bottom of the output

    Args:
        config (RunConfig): the run's settings, for the detail level.
        dropped_anchors (set): anchor ids the view limit kept out of the output.  These
            items sit at the very bottom, so they are the first to go when the output is
            cut short, and they are listed as plain text when they do.

    Returns:
        None
    """
    trailing_matter = []
    PrimeItems.output_lines.add_line_to_output(
        5,
        f"<br><br>{NORMAL_TAB}Trailing Information{period * 50}<br><br>",
        ["", "project_color", FormatLine.add_end_span],
    )

    # Do the Configuration Variables
    if config.display_detail_level == 4:
        trailing_matter.append(
            directory_entry(
                "unreferenced_variables",
                "unreferenced_variables",
                "Unreferenced Global Variables",
                dropped_anchors,
            ),
        )

    # Add Grand Totals.
    trailing_matter.append(directory_entry("grand_totals", "grand_totals", "Grand Totals", dropped_anchors))

    # Output the table
    trailing_matter.sort()
    output_table(trailing_matter, 4)


# ##################################################################################
# Which Project a Profile/Task/Scene belongs to, and what the single item selected
# brings into the directory with it.
#
# The directory only ever holds names the Map actually wrote (add_directory_item is
# called as each object is output), so these filters are not deciding what the run
# displayed -- they are keeping the directory to the one object that was asked for.  An
# item that some OTHER Project claims is the thing to drop; an item no Project claims at
# all is kept, because Tasker leaves Tasks that way -- a Task attached only to a Scene is
# not always listed in its Project's <tids> -- and dropping those would lose directory
# entries for Tasks that are on the page.
#
# Read straight off the Project XML rather than through maputils' equivalents: dirout
# sits below maputils in the import graph (maputils -> taskerd -> profiles -> dirout).
# ##################################################################################
def project_owning(items_tag: str, item_to_match: str) -> str:
    """Find the Project that claims a Profile, Task or Scene.

        Args:
            items_tag (str): the Project element holding the list to search: "pids" for
                Profile ids, "tids" for Task ids, "scenes" for Scene names.
            item_to_match (str): the Profile id, Task id or Scene name to look for.

        Returns:
            str: the name of the Project that lists it, or "" when none does.
    """
    if not item_to_match:
        return ""
    for project_name, project in PrimeItems.tasker_root_elements["all_projects"].items():
        items_in_project = project["xml"].find(items_tag)
        if items_in_project is not None and items_in_project.text and item_to_match in items_in_project.text.split(","):
            return project_name
    return ""


def belongs_to(items_tag: str, item_to_match: str, project_name: str) -> bool:
    """Is this Profile, Task or Scene one that the given Project owns?

        Args:
            items_tag (str): "pids", "tids" or "scenes" -- see project_owning.
            item_to_match (str): the Profile id, Task id or Scene name to place.
            project_name (str): the name of the Project it has to belong to.

        Returns:
            bool: True unless another Project claims it (see this section's note on the
                items no Project claims at all).
    """
    owner = project_owning(items_tag, item_to_match)
    return owner in ("", project_name)


def profile_id(profile_name: str) -> str:
    """Get the id of the Profile with this name, or "" if there is no such Profile.

        Args:
            profile_name (str): the Profile's name, as the directory holds it -- which for
                an unnamed Profile is the name MapTasker gave it (see profiles.py).

        Returns:
            str: the Profile's id.
    """
    for this_id, profile in PrimeItems.tasker_root_elements.get("all_profiles", {}).items():
        if profile.get("name") == profile_name:
            return this_id
    return ""


def task_id(task_name: str) -> str:
    """Get the id of the Task with this name, or "" if there is no such Task.

        Args:
            task_name (str): the Task's name, without the " (Scene)" the directory appends
                to a Task that belongs to a Scene.

        Returns:
            str: the Task's id.
    """
    return PrimeItems.tasker_root_elements.get("all_tasks_by_name", {}).get(task_name, {}).get("id", "")


# Get the Task IDs that a Profile directly references: its Entry/Exit Tasks.
def get_profile_task_ids(profile_name: str) -> set:
    """
    Get the IDs of the Tasks a Profile directly references (its Entry and Exit Tasks)
        Args:
            profile_name (str): name of the Profile whose Task IDs we want

        Returns:
            set: the Profile's Task IDs, empty if the Profile is unknown.
    """
    profile = PrimeItems.tasker_root_elements.get("all_profiles_by_name", {}).get(profile_name, {}).get("xml")
    if profile is None:
        return set()
    # A Profile's Entry Task is <mid0> and its Exit Task is <mid1> (see
    # profiles.get_profile_tasks, which walks the same children).
    return {child.text for child in profile if "mid" in child.tag and child.text}


# Doing Task hyperlink.  Make sure it is okay to do this Task hyperlink.
def check_task(item: str, config: RunConfig) -> bool:
    """
    Check to make sure this Task should be included in the output
        Args:
            item (str): directory hyperlink item we are processing
            config (RunConfig): the run's settings, for the single-item selection.

        Returns:
            bool: True if we should output this hyperlink, False if it is to be ingored.
    """
    # A Task that belongs to a Scene is held with " (Scene)" on the end of its name.
    this_task_id = task_id(item[1].replace(" (Scene)", ""))

    # Doing a single Task?  Only that Task.  An unnamed Task is let through whatever its
    # name: the name it is listed under is one MapTasker made up from its first action.
    if config.single_task_name:
        return item[1] == config.single_task_name or UNNAMED_ITEM in item[1]

    # Doing a single Profile?
    if config.single_profile_name:
        # The Profile's own Entry/Exit Tasks always belong to it.  Check these first:
        # Tasker doesn't always list such a Task in the owning Project's <tids>, and
        # the Task would otherwise be dropped from the directory even though it is
        # displayed in the output.
        if this_task_id in get_profile_task_ids(config.single_profile_name):
            return True
        # Otherwise the Task has to belong to the Project that owns this Profile
        # (e.g. a Task attached to one of that Project's Scenes).
        owning_project = project_owning("pids", profile_id(config.single_profile_name))
        return bool(owning_project) and belongs_to("tids", this_task_id, owning_project)

    # Doing a single Project?  Only the Tasks that Project owns.
    if config.single_project_name:
        return belongs_to("tids", this_task_id, config.single_project_name)

    # Doing a single Scene?  Only the Tasks of the Project the Scene belongs to -- which
    # are the Scene's own Tasks, since that is all the run displayed.
    if config.single_scene_name:
        owning_project = project_owning("scenes", config.single_scene_name)
        return bool(owning_project) and belongs_to("tids", this_task_id, owning_project)

    return True


# Doing Profile hyperlink.  Make sure it is okay to do this Profile hyperlink.
def check_profile(item: str, config: RunConfig) -> bool:
    """
    Check to make sure this Profile should be included in the output
        Args:
            item (str): directory hyperlink item we are processing
            config (RunConfig): the run's settings, for the single-item selection.

        Returns:
            bool: True if we should output this hperlink, False if it is to be ingored.
    """
    # Doing a single Profile?  Only that Profile.
    if config.single_profile_name:
        return item[1] == config.single_profile_name

    # No Profiles are displayed for a single Task or a single Scene, so don't link any.
    if config.single_task_name or config.single_scene_name:
        return False

    # Doing a single Project?  Only the Profiles that Project owns.
    if config.single_project_name:
        return belongs_to("pids", profile_id(item[1]), config.single_project_name)

    return True


# Doing Project hyperlinks.  Make sure it is okay to do this Project hyperlink.
def check_project(item: str, config: RunConfig) -> bool:
    """
    Check to make sure this Project should be included in the output
        Args:
            item (str): directory hyperlink item we are processing
            config (RunConfig): the run's settings, for the single-item selection.

        Returns:
            bool: True if we should output this hperlink, False if it is to be ingored.
    """
    # Doing a single Project?  Only that Project.
    if config.single_project_name:
        return item[1] == config.single_project_name

    # Doing a single Scene?  Only the Project that owns it is displayed, so only it gets a
    # link.
    if config.single_scene_name:
        return item[1] == project_owning("scenes", config.single_scene_name)

    # Doing a single Profile or a single Task?  No Project is listed: the object asked for
    # is the whole of what the directory is for.  output_directory leaves the Projects
    # section out altogether for those two; this says the same thing for the one entry at
    # a time, so the two cannot disagree.
    return not (config.single_profile_name or config.single_task_name)


# Doing Scene hyperlink.  Make sure it is okay to do this Scene hyperlink.
def check_scene(item: str, config: RunConfig) -> bool:
    """
    Check to make sure this Scene should be included in the output
        Args:
            item (str): directory hyperlink item we are processing
            config (RunConfig): the run's settings, for the single-item selection.

        Returns:
            bool: True if we should output this hperlink, False if it is to be ingored.
    """
    # Doing a single Scene?  Only that Scene.
    if config.single_scene_name:
        return item[1] == config.single_scene_name

    # Doing a single Project?  Only that Project's Scenes.
    if config.single_project_name:
        return belongs_to("scenes", item[1], config.single_project_name)

    # Doing a single Profile?  Only the Scenes of the Project that owns it, which are
    # displayed along with it.
    if config.single_profile_name:
        owning_project = project_owning("pids", profile_id(config.single_profile_name))
        return bool(owning_project) and belongs_to("scenes", item[1], owning_project)

    # Doing a single Task?  Only the Scenes of the Project that owns the Task.
    if config.single_task_name:
        owning_project = project_owning("tids", task_id(config.single_task_name))
        return bool(owning_project) and belongs_to("scenes", item[1], owning_project)

    return True


# Check to make sure this directory item should be included in the output.
def check_item(name: str, item: str, config: RunConfig) -> bool:
    """
    Check to make sure this item should be included in the output
        Args:
            name: element name: directory we are doing:
                    "projects", "profiles", "tasks", "scenes"
            item (str): directory hyperlink item we are processing
            config (RunConfig): the run's settings, for the single-item selection.

        Returns:
            bool: True if we should output this hyperlink, False if it is to be ingored.
    """
    function_mappings = {
        "projects": check_project,
        "profiles": check_profile,
        "tasks": check_task,
        "scenes": check_scene,
    }
    # Check if doing a single item...only build directory for that item.
    return function_mappings[name](item, config)


#######################################################################################
# Output table for specific Tasker element: Projects, Profiles, Tasks, Scenes
#######################################################################################
def do_tasker_element(name: str, config: RunConfig, dropped_anchors: set) -> None:
    """
    Build an html table and output it for the given Tasker element: Project, Profile,
        Scene or Task.  DO this by traversing the entire xml trees.

    This function adds project information to the output lines.
    It generates hyperlinks for each project and builds an HTML table with hyperlinks.

    Args:
        name: element name: directory we are doing:
                "projects", "profiles", "tasks", "scenes"
        config (RunConfig): the run's settings, for the single-item selection.
        dropped_anchors (set): anchor ids the view limit kept out of the output.  An item
            whose anchor is among them is listed as plain text rather than as a hyperlink
            that would go nowhere.

    Returns:
        None
    """
    # Output the table header
    if PrimeItems.directory_items[name]:
        # Go through each item and accumulate the names to be used for
        # the directory hyperlinks
        directory_hyperlinks = []

        _check_item = check_item
        for item in PrimeItems.directory_items[name]:
            if _check_item(name, item, config):
                # Directory item is valid for this name.
                # Get the name and display name for this item
                item_name = item[0].replace("_(Scene)", "")
                hyperlink_name = item_name.replace(">", "&gt;").replace("<", "&lt;")
                display_name = item[1].replace(">", "&gt;").replace("<", "&lt;")
                # Append our hyperlink to this Project to the list.  The anchor itself is
                # written with the name as-is (lineout.add_directory_link), so it is the
                # unescaped name that has to be matched against the dropped anchors.
                directory_hyperlinks.append(
                    (
                        f"{name}_{hyperlink_name}",
                        directory_entry(
                            f"{name}_{hyperlink_name}",
                            f"{name}_{item_name}",
                            display_name,
                            dropped_anchors,
                        ),
                    ),
                )

        if directory_hyperlinks:
            # Sort by the item's name here rather than leaving it to the table, which
            # would otherwise sort the plain-text entries apart from the hyperlinks.
            directory_hyperlinks.sort()
            directory_hyperlinks = [entry for _, entry in directory_hyperlinks]
            # Output the name title: Project, Profile, Task, Scene
            PrimeItems.output_lines.add_line_to_output(
                5,
                f"{NORMAL_TAB}{name.capitalize()}{period * 60}<br><br>",
                ["<br><br>", "project_color", FormatLine.add_end_span],
            )
            # 6 columns for projects, 5 columns for tasks
            number_of_columns = 5 if name == "tasks" else 6
            output_table(directory_hyperlinks, number_of_columns)


#######################################################################################
# Output directory by appending it to our output queue
#######################################################################################
def output_directory(config: RunConfig, dropped_anchors: set | None = None) -> None:
    """
    Writes the directory to the output queue.

    Args:
        config (RunConfig): the run's settings, threaded down to the per-item filters.
        dropped_anchors (set): anchor ids the view limit kept out of the output, from
            unreachable_anchors().  Entries pointing at one of them are listed as plain
            text instead of as a hyperlink that would go nowhere.  None/empty means the
            whole output was written and every entry gets its hyperlink.

    Returns:
        None
    """
    if dropped_anchors is None:
        dropped_anchors = set()

    # Add heading
    PrimeItems.output_lines.add_line_to_output(
        5,
        f"<h2>{NORMAL_TAB}Directory</h2><br><br>",
        ["<br><br>", "profile_color", FormatLine.add_end_span],
    )
    # Ok, run through the Tasker key elements and output the directory for each
    # Only do Projects and Profiles if not looking for a single Project or Profile
    if not (config.single_profile_name or config.single_task_name):
        do_tasker_element("projects", config, dropped_anchors)
    do_tasker_element("profiles", config, dropped_anchors)
    if config.display_detail_level != 0:
        do_tasker_element("tasks", config, dropped_anchors)
    do_tasker_element("scenes", config, dropped_anchors)

    do_trailing_matters(config, dropped_anchors)

    # Add final rule and break
    PrimeItems.output_lines.add_line_to_output(
        5,
        "<hr><br><br>\n",
        FormatLine.dont_format_line,
    )
