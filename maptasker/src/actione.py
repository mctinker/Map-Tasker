#! /usr/bin/env python3

######################################################################################################################
#                                                                                                                    #
#  actione: action evaluation                                                                                        #
#           given the xml <code>nn</code>, figure out what (action) code it is and return the translation            #
#                                                                                                                    #
#          code_child: used to parse the specific <code> xml for action details.                                     #
#          code_action: the nnn in <code>nnn</code> xml                                                              #
#          action_type: true if Task action, False if not (e.g. a Profile state or event condition)                  #
#                                                                                                                    #
######################################################################################################################
import copy
import re
import defusedxml.ElementTree  # Need for type hints

import maptasker.src.actionr as action_results

from maptasker.src.action import get_extra_stuff
from maptasker.src.frmthtml import format_html
from maptasker.src.error import error_handler
from maptasker.src.actionc import action_codes
from maptasker.src.sysconst import logger
from maptasker.src.sysconst import FONT_TO_USE


# pattern1 = re.compile(r'<.*?>')  # Get rid of all <something> html code


# ####################################################################################################
# Delete crap that might be in the label
# ####################################################################################################
def cleanup_the_result(results: str) -> str:
    """
    Delete html crap that might be in the label, and which would screw up the output formatting
        :param results: the string to clean
        :return: the cleaned string
    """
    # The following line works as well, going through each character in the string
    # results = ', '.join([x.strip() for x in results.split(',') if not x.isspace() and x != ''])
    results = results.replace(
        ",  <font>", "<font>"
    )  # Get rid of comma on last parameter
    results = results.replace(", (", "")
    pattern = re.compile(r",[, ]+")
    results = pattern.sub(", ", results)  # Delete repeating commas
    results = results.replace(", <span", "<span")
    results = results.replace(",  <span", "  <span")
    results = results.replace(", code:", "")
    results = results.replace("<big>", "")
    results = results.replace("<small>", "")
    results = results.replace("<tt>", "")
    results = results.replace("<i>", "")
    results = results.replace("<u>", "")
    results = results.replace(", <font", "<font")
    return results


# ####################################################################################################
# For debug purposes, this searches dictionary for missing keys: 'reqargs' and 'display'
# ####################################################################################################
def look_for_missing_req() -> None:
    """
    For debug purposes, this searches dictionary for missing keys: 'reqargs' and 'display'
        If found, the error is handled and the program exits
        :return: nothing
    """
    for item in action_codes:
        entry = action_codes[item]
        numargs = entry["numargs"]
        # Required arguments missing?  Exit with program error if so.
        if numargs > 0 and "reqargs" not in entry:
            error_handler(
                f"the_action_code_plus {item} missing reqargs!  numargs:{numargs}",
                1,
            )
        # Missing the entry's display name?
        if "display" not in entry:
            error_handler(f'the_action_code_plus {item} missing "display"!', 1)

    return


# ####################################################################################################
# See if this Task or Profile code isa deprecated
# ####################################################################################################
def check_for_deprecation(the_action_code_plus: str) -> None:
    """
    See if this Task or Profile code isa deprecated
        :param the_action_code_plus: the action code plus the type of action (e.g. "861t", "t" = Task, "e" = Event, "s" = State)
        :return: nothing
    """
    from maptasker.src.depricated import depricated

    lookup = the_action_code_plus[:-1]  # Remove last character to get just the digits
    if lookup in depricated and the_action_code_plus in action_codes:
        action_codes[the_action_code_plus] = {
            "display": (
                action_codes[the_action_code_plus]["display"]
                + "<em> (Is Deprecated)</em> "
            )
        }
    return


# ####################################################################################################
# Given an action code, evaluate it for display
# ####################################################################################################
def get_action_code(
    primary_items: dict,
    code_child: defusedxml.ElementTree.XML,
    code_action: defusedxml.ElementTree.XML,
    action_type: bool,
    code_type: str,
) -> str:
    """
    Given an action code, evaluate it for display
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :param code_child: xml element of the <code>
        :param code_action: value of <code> (e.g. "549")
        :param action_type:
        :param code_type: 'e'=event, 's'=state, 't'=task
        :return: formatted output line with action details
    """
    logger.debug(f"get action code:{code_child.text}{code_type}")
    the_action_code_plus = code_child.text + code_type
    # See if this code is deprecated
    check_for_deprecation(the_action_code_plus)
    # We have a code that is not yet in the dictionary?
    if (
        the_action_code_plus not in action_codes
        or "display" not in action_codes[the_action_code_plus]
    ):
        the_result = (
            f"Code {the_action_code_plus} not yet"
            f" mapped{get_extra_stuff(primary_items, code_action, action_type)}"
        )
        logger.debug(f"unmapped task code: {the_action_code_plus} ")

    else:
        # The code is in our dictionary.  Add the display name
        the_result = format_html(
            primary_items["colors_to_use"],
            "action_name_color",
            "",
            action_codes[the_action_code_plus]["display"],
            True,
        )

        if "numargs" in action_codes[the_action_code_plus]:
            numargs = action_codes[the_action_code_plus]["numargs"]
        else:
            numargs = 0
        # If there are required args, then parse them
        if numargs != 0 and "reqargs" in action_codes[the_action_code_plus]:
            the_result = action_results.get_action_results(
                primary_items,
                the_action_code_plus,
                action_codes,
                code_action,
                action_type,
                action_codes[the_action_code_plus]["reqargs"],
                action_codes[the_action_code_plus]["evalargs"],
            )
        # If this is a redirected lookup entry, create a temporary mirror dictionary entry.
        # Then grab the 'display' key and fill in rest with directed-to keys
        if "redirect" in action_codes[the_action_code_plus]:
            referral = action_codes[the_action_code_plus]["redirect"][
                0
            ]  # Get the referred-to dictionary item
            temp_lookup_codes = {
                the_action_code_plus: copy.deepcopy(action_codes[referral])
            }
            display_name = action_codes[the_action_code_plus][
                "display"
            ]  # Add this guy's display name
            temp_lookup_codes["display"] = copy.deepcopy(display_name)
            # Get the results from the (copy of the) referred-to dictionary entry
            the_result = action_results.get_action_results(
                primary_items,
                the_action_code_plus,
                temp_lookup_codes,
                code_action,
                action_type,
                temp_lookup_codes[the_action_code_plus]["reqargs"],
                temp_lookup_codes[the_action_code_plus]["evalargs"],
            )

    the_result = cleanup_the_result(the_result)
    return the_result


# #############################################################################################
# Construct Task Action output line
# #############################################################################################
def build_action(
    primary_items: dict,
    alist: list,
    task_code_line: str,
    code_element: defusedxml.ElementTree.XML,
    indent: int,
    indent_amt: str,
) -> list:
    """
    Construct Task Action output line
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :param alist: list of actions (all <Actions> for task
        :param task_code_line: output text of Task
        :param code_element: xml element of <code> under <Action>
        :param indent: the number of spaces to indent the output line
        :param indent_amt: the indent number of spaces as "&nbsp;" for each space
        :return: finalized output string
    """
    from maptasker.src.config import CONTINUE_LIMIT

    # Calculate total indentation to put in front of action
    count = indent
    if count != 0:
        task_code_line = task_code_line.replace(
            f'{FONT_TO_USE}">', f'{FONT_TO_USE}">{indent_amt}', 1
        )
        count = 0
    if count < 0:
        task_code_line = indent_amt + task_code_line

    # Break-up very long actions at new line
    if not task_code_line:  # If no Action details
        alist.append(
            format_html(
                primary_items,
                "unknown_task_color",
                "",
                f"Action {code_element.text}: not yet mapped",
                True,
            )
        )
    else:  # We have Task Action details
        newline = task_code_line.find("\n")  # Break-up new line breaks
        task_code_line_len = len(task_code_line)

        # If no new line break or line break less than width set for browser, just put it as is
        # Otherwise, make it a continuation line using '...' has the continuation flag
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
                    alist.append(f"...{item}")
                count += 1
                # Only display up to so many continued lines
                if count == CONTINUE_LIMIT:
                    # Add comment that we have reached the limit for continued details
                    alist[-1] = f"{alist[-1]}</span>" + format_html(
                        primary_items,
                        "Red",
                        "",
                        (
                            f' ... continue limit of {str(CONTINUE_LIMIT)} '
                            'reached.  See "CONTINUE_LIMIT =" in config.py for '
                            'details'
                        ),
                        True,
                    )
                    break

    return alist
