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

import defusedxml.ElementTree  # Need for type hints

import maptasker.src.actionr as action_results
from maptasker.src.action import get_extra_stuff
from maptasker.src.actionc import ActionCode, action_codes
from maptasker.src.config import CONTINUE_LIMIT
from maptasker.src.debug import not_in_dictionary
from maptasker.src.deprecate import depricated
from maptasker.src.format import format_html
from maptasker.src.sysconst import logger


# ##################################################################################
# See if this Task or Profile code is deprecated.
# ##################################################################################
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


# ##################################################################################
# Given an action code, evaluate it for display.
# ##################################################################################
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
    logger.debug(f"get action code:{code_child.text}{code_type}")
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


# ##################################################################################
# Construct Task Action output line
# ##################################################################################
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
        # task_code_line = f"{indent_amt}{task_code_line}"

    # Flag Action if not yet known to us
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
        newline = task_code_line.find("\n")  # Break-up new line breaks
        task_code_line_len = len(task_code_line)

        # If no new line break or line break less than width set for browser,
        # just put it as is.
        # Otherwise, make it a continuation line using '...' has the continuation flag.
        if newline == -1 and task_code_line_len > 80:
            alist.append(task_code_line)
        else:
            # Break into individual lines at line break (\n)
            array_of_lines = task_code_line.split("\n")
            count = 0
            # Determine if a single line or a continued line
            for item in array_of_lines:
                if count == 0:
                    alist.append(item)
                else:
                    alist.append(f"...indent={indent}item={item}")
                count += 1

                # Only display up to so many continued lines
                if count == CONTINUE_LIMIT:
                    # Add comment that we have reached the limit for continued details
                    alist[-1] = f"{alist[-1]}</span>" + format_html(
                        "Red",
                        "",
                        (
                            f" ... continue limit of {CONTINUE_LIMIT!s} "
                            'reached.  See "CONTINUE_LIMIT =" in config.py for '
                            "details"
                        ),
                        True,
                    )
                    # Done with this item...get out of loop.
                    break

    return alist
