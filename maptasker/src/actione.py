"""Evaluate Task actions."""

#! /usr/bin/env python3

# ####################################################################################
#                                                                                    #
#  actione: action evaluation                                                        #
#           given the xml <code>nn</code>, figure out what (action) code it is and   #
#               return the translation                                               #
#                                                                                    #
#          code_child: used to parse the specific <code> xml for action details.     #
#          code_action: the nnn in <code>nnn</code> xml                              #
#          action_type: true if Task action, False if not (e.g. a Profile state      #
#                       or event condition)                                          #
#                                                                                    #
# ####################################################################################
import contextlib
import re

import defusedxml.ElementTree  # Need for type hints

import maptasker.src.actionr as action_results
from maptasker.src.action import get_extra_stuff
from maptasker.src.actionc import ActionCode, action_codes
from maptasker.src.config import CONTINUE_LIMIT
from maptasker.src.debug import not_in_dictionary
from maptasker.src.deprecate import depricated
from maptasker.src.format import format_html
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import logger, pattern13

blank = "&nbsp;"


# See if this Task or Profile code is deprecated.
def check_for_deprecation(the_action_code_plus: str) -> None:
    """
    See if this Task or Profile code isa deprecated
        :param the_action_code_plus: the action code plus the type of action
            (e.g. "861t", "t" = Task, "e" = Event, "s" = State)
        :return: nothing
    """

    lookup = the_action_code_plus[:-1]  # Remove last character to get just the digits
    if lookup in depricated and the_action_code_plus in action_codes:
        return "<em> (Is Deprecated)</em> "

    return ""


# Given an action code, evaluate it for display.
def get_action_code(
    code_child: defusedxml.ElementTree.XML,
    code_action: defusedxml.ElementTree.XML,
    action_type: bool,
    code_type: str,
) -> str:
    """
    Given an action code, evaluate it for display
        :param code_child: xml element of the <code>
        :param code_action: value of <code> (e.g. "549")
        :param action_type: entry or exit
        :param code_type: 'e'=event, 's'=state, 't'=task
        :return: formatted output line with action details
    """
    # logger.debug(f"get action code:{code_child.text}{code_type}")
    the_action_code_plus = code_child.text + code_type

    # See if this code is deprecated
    depricated = check_for_deprecation(the_action_code_plus)

    # We have a code that is not yet in the dictionary?
    if the_action_code_plus not in action_codes or not action_codes[the_action_code_plus].display:
        the_result = f"Code {the_action_code_plus} not yet mapped{get_extra_stuff(code_action, action_type)}"
        not_in_dictionary(
            "Action/Condition",
            f"'display' for code {the_action_code_plus}",
        )

    else:
        # Format the output with HTML if this is a Task
        if action_type:
            # The code is in our dictionary.  Add the display name
            the_result = format_html(
                "action_name_color",
                "",
                f"{action_codes[the_action_code_plus].display}{depricated}",
                True,
            )
        # Not a Task.  Must be a condition.
        else:
            the_result = f"{action_codes[the_action_code_plus].display}{depricated}"

        numargs = action_codes[the_action_code_plus].numargs if action_codes[the_action_code_plus].numargs else 0

        # If there are required args, then parse them
        if numargs != 0 and action_codes[the_action_code_plus].reqargs:
            the_result = action_results.get_action_results(
                the_action_code_plus,
                action_codes,
                code_action,
                action_type,
                action_codes[the_action_code_plus].reqargs,
                action_codes[the_action_code_plus].evalargs,
            )

        # If this is a redirected lookup entry, create a temporary mirror
        # dictionary entry.
        # Then grab the 'display' key and fill in rest with directed-to keys
        with contextlib.suppress(KeyError):
            if action_codes[the_action_code_plus].redirect:
                # Get the referred-to dictionary item.
                referral = action_codes[the_action_code_plus].redirect

                # Create a temporary mirror dictionary entry using values of redirected code
                temp_lookup_codes = {}
                temp_lookup_codes[the_action_code_plus] = ActionCode(
                    action_codes[referral].numargs,
                    "",
                    action_codes[referral].args,
                    action_codes[referral].types,
                    action_codes[the_action_code_plus].display,
                    action_codes[referral].reqargs,
                    action_codes[referral].evalargs,
                )

                # Get the results from the (copy of the) referred-to dictionary entry
                the_result = action_results.get_action_results(
                    the_action_code_plus,
                    temp_lookup_codes,
                    code_action,
                    action_type,
                    temp_lookup_codes[the_action_code_plus].reqargs,
                    temp_lookup_codes[the_action_code_plus].evalargs,
                )

    return the_result


# Put the line '"Structure Output (JSON, etc)' back together.
def fix_json(line_to_fix: str, text_to_match: str) -> str:
    """
    Fix the JSON line by undoing the breakup at the comma for "Structure Output (JSON, etc)".

    Args:
        line_to_fix (str): The line to be fixed.
        texct_to_match (str): The text to match against.

    Returns:
        str: The fixed line.
    """
    # We have to undo the breakup at the comma for "Structure Output (JSON, etc)
    json_location = line_to_fix.find(f"{text_to_match} (JSON")
    if json_location != -1:
        etc_location = line_to_fix.find("etc", json_location)
        temp_line = f"{line_to_fix[:json_location-1]}{text_to_match} (JSON, {line_to_fix[etc_location:]}"
        line_to_fix = temp_line
    return line_to_fix


# Make the action line pretty by aligning the arguments.
def make_action_pretty(task_code_line: str, indent_amt: int) -> str:
    """
    Makes the given task code line prettier by adding line breaks and indentation.

    Args:
        task_code_line (str): The task code line to be made prettier.
        indent_amt (int): The amount of indentation to be added.

    Returns:
        str: The prettified task code line.
    """

    # Add our leading spaces (indent_amt) and extra spaces for the Task action name.
    temp_line = task_code_line.replace(blank, "")  # Strip blanks from line to figure out Task action name length.
    close_bracket = temp_line.find(">")
    open_bracket = temp_line.find("<", close_bracket)
    extra_blanks = open_bracket - close_bracket + 5
    # Break at comma followed by a space.
    task_code_line = task_code_line.replace(", ", f", <br>{indent_amt}{blank*extra_blanks}")
    # Break at newline and comma if not a config param.
    # NOTE: There may be one or more double '\n' strings, which is ok.
    if "Configuration Parameter(s):" not in task_code_line:
        # Replace all commas followed by a nonblank with a break
        task_code_line = re.sub(pattern13, f"<br>{indent_amt}{blank*(extra_blanks+7)}", task_code_line)
        # Now handle newlines
        task_code_line = task_code_line.replace("\n", f"<br>{indent_amt}{blank*(extra_blanks+7)}")  # 7 for "Values="

    # Break at bracket
    task_code_line = task_code_line.replace("[", f"<br>{indent_amt}{blank*extra_blanks}[")
    # Break at (If condition
    task_code_line = task_code_line.replace("(<em>IF", f"<br>{indent_amt}{blank*extra_blanks}(<em>IF")
    # Break at label
    task_code_line = task_code_line.replace(
        "...with label:",
        f"<br>{indent_amt}{blank*extra_blanks} ...with label:",
    )

    # Fix up "Structure Output (JSON, etc)", which got separated by the comma
    task_code_line = fix_json(task_code_line, "Structure Output")

    # Finally, rtemove the trailing comma since each argument is separated already
    task_code_line = task_code_line.replace(", <br>", "<br>")

    return task_code_line, extra_blanks


# Finalize the action line and append it to the list of actions.
def finalize_action_details(task_code_line: str, alist: list, indent: int, extra_blanks: int, count: int) -> list:
    r"""
    Finalize the action line and append it to the list of actions.

    Args:
        task_code_line (str): The action line to be finalized.
        alist (list): The list of actions.
        indent (int): The number of spaces to indent the output line.
        extra_blanks (int): The number of extra blanks to add to the output line.
        count (int): The count of continued lines.

    Returns:
        list: The updated list of actions.

    Description:
        This function finalizes the action line by breaking it into individual lines at line break (\n).
        It determines whether to put the action line as is or make it a continuation line using '...' as the continuation flag.
        It appends the finalized action line to the list of actions.
        If the action line has no new line break or its line break is less than the width set for the browser,
        or if pretty output is being done, it appends the action line as is.
        Otherwise, it breaks the action line into individual lines at line break (\n).
        It determines whether each line is a single line or a continued line.
        If it is a continued line, it appends the line with '...indent={indent+extra_blanks}item={item}' format.
        It only displays up to a certain number of continued lines.
        If the count of continued lines reaches the limit, it adds a comment indicating that the limit has been reached.
        It returns the updated list of actions.

    Note:
        - The action line is assumed to have line breaks already broken up.
        - The action line is assumed to have leading empty fields removed.
    """
    newline = task_code_line.find("\n")  # Break-up new line breaks
    task_code_line_len = len(task_code_line)

    # If no new line break or line break less than width set for browser...or doing pretty output,
    # just put it as is.
    # Otherwise, make it a continuation line using '...' has the continuation flag.
    if (newline == -1 and task_code_line_len > 80) or (PrimeItems.program_arguments["pretty"]):
        alist.append(task_code_line)
    else:
        # Break into individual lines at line break (\n)
        array_of_lines = task_code_line.split("\n")
        count = 0
        # Determine if a single line or a continued line
        for count, item in enumerate(array_of_lines):
            if count == 0:
                alist.append(item)
            else:
                alist.append(f"...indent={indent+extra_blanks}item={item}")
            # count += 1

            # Only display up to so many continued lines
            if count == CONTINUE_LIMIT:
                # Add comment that we have reached the limit for continued details.
                alist[-1] = f"{alist[-1]}</span>" + format_html(
                    "Red",
                    "",
                    (
                        f"<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;... continue limit of {CONTINUE_LIMIT!s} "
                        'reached.  See "CONTINUE_LIMIT =" in config.py for '
                        "details"
                    ),
                    True,
                )
                # Done with this item...get out of loop.
                break

    return alist


# Construct Task Action output line
def build_action(
    alist: list,
    task_code_line: str,
    code_element: defusedxml.ElementTree.XML,
    indent: int,
    indent_amt: str,
) -> list:
    """
    Construct Task Action output line
        :param alist: list of actions (all <Actions> formatted for output
        :param task_code_line: output text of Task
        :param code_element: xml element of <code> under <Action>
        :param indent: the number of spaces to indent the output line
        :param indent_amt: the indent number of spaces as "&nbsp;" for each space
        :return: finalized output string
    """

    # Clean up the action line by removing any leading ermpty field
    task_code_line = task_code_line.replace(f"{blank*2},", f"{blank*2}")  # Drop the leading comma if present.

    # Calculate total indentation to put in front of action
    count = indent

    if count != 0:
        # Add the indent amount to the front of the Action output line
        front_matter = '<span class="action_name_color">'
        task_code_line = task_code_line.replace(front_matter, f"{front_matter}{indent_amt}", 1)
        count = 0
    if count < 0:
        indent_amt += task_code_line
        task_code_line = indent_amt

    # Make the output align/pretty.
    if PrimeItems.program_arguments["pretty"]:
        task_code_line, extra_blanks = make_action_pretty(task_code_line, indent_amt)
    else:
        extra_blanks = 0

    # Flag Action if not yet known to us.  Tell user (and me) about it.
    if not task_code_line:  # If no Action details
        alist.append(
            format_html(
                "unknown_task_color",
                "",
                f"Action {code_element.text}: not yet mapped",
                True,
            ),
        )
        # Handle this
        not_in_dictionary("Action", code_element.text)

    # We have Task Action details
    else:
        alist = finalize_action_details(task_code_line, alist, indent, extra_blanks, count)

    return alist
