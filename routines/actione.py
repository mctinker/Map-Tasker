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
import xml.etree.ElementTree  # Need for type hints

import routines.actionr as action_results
from config import *
from routines.action import get_extra_stuff
from routines.actionc import action_codes
from routines.sysconst import logger

pattern = re.compile(r",[, ]+")
# pattern1 = re.compile(r'<.*?>')  # Get rid of all <something> html code


# ####################################################################################################
# Delete crap that might be in the label
# ####################################################################################################
def cleanup_the_result(results):
    # The following line works as well, going through each character in the string
    # results = ', '.join([x.strip() for x in results.split(',') if not x.isspace() and x != ''])
    results = results.replace(
        ",  <font>", "<font>"
    )  # Get rid of comma on last parameter
    results = results.replace(", (", "")
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
def look_for_missing_req():
    flag = False
    for item in action_codes:
        entry = action_codes[item]
        numargs = entry["numargs"]
        if numargs > 0 and "reqargs" not in entry:
            error_msg = f"dict_code {item} missing reqargs!  numargs:{numargs}"
            print(error_msg)
            logger.debug(f"{error_msg}")
            flag = True
        if "display" not in entry:
            error_msg = f'dict_code {item} missing "display"!'
            print(error_msg)
            logger.debug(error_msg)
            entry["display"] = "unmapped"
            flag = True
    if flag:
        exit(99)


# ####################################################################################################
# See if this Task or Profile code isa deprecated
# ####################################################################################################
def check_for_deprecation(dict_code):
    from routines.depricated import depricated

    lookup = dict_code[:-1]  # Remove last character to get just the digits
    if lookup in depricated and dict_code in action_codes:
        action_codes[dict_code] = {
            "display": action_codes[dict_code]["display"] + "<em> (Is Deprecated)</em>"
        }
    return


# ####################################################################################################
# Given an action code, evaluate it for display
# ####################################################################################################
def get_action_code(
    code_child: xml.etree.ElementTree,
    code_action: xml.etree.ElementTree,
    action_type: bool,
    colormap: dict,
    code_type: str,
    program_args: dict,
) -> str:
    logger.debug(f"getcode:{code_child.text}{code_type}")
    dict_code = code_child.text + code_type
    # See if this code is deprecated
    check_for_deprecation(dict_code)
    if (
        dict_code not in action_codes or "display" not in action_codes[dict_code]
    ):  # We have a code that is not yet in the dictionary?
        the_result = f"Code {dict_code} not yet mapped{get_extra_stuff(code_action, action_type, colormap, program_args)}"
        logger.debug(f"unmapped task code: {dict_code} ")

    else:
        the_result = (
            '<span style="color:'
            + colormap["action_name_color"]
            + '"</span>'
            + action_codes[dict_code]["display"]
        )  # Just get the basics for now
        if "numargs" in action_codes[dict_code]:
            numargs = action_codes[dict_code]["numargs"]
        else:
            numargs = 0
        if numargs != 0 and "reqargs" in action_codes[dict_code]:
            the_result = action_results.get_action_results(
                dict_code,
                action_codes,
                code_action,
                action_type,
                colormap,
                action_codes[dict_code]["reqargs"],
                action_codes[dict_code]["evalargs"],
                program_args,
            )
        # If this is a redirected lookup entry, create a temporary mirror dictionary entry.
        # Then grab the 'display' key and fill in rest with directed-to keys
        if "redirect" in action_codes[dict_code]:
            referral = action_codes[dict_code]["redirect"][
                0
            ]  # Get the referred-to dictionary item
            temp_lookup_codes = {dict_code: copy.deepcopy(action_codes[referral])}
            display_name = action_codes[dict_code][
                "display"
            ]  # Add this guy's display name
            temp_lookup_codes["display"] = copy.deepcopy(display_name)
            # Get the results from the (copy of the) referred-to dictionary entry
            the_result = action_results.get_action_results(
                dict_code,
                temp_lookup_codes,
                code_action,
                action_type,
                colormap,
                temp_lookup_codes[dict_code]["reqargs"],
                temp_lookup_codes[dict_code]["evalargs"],
                program_args,
            )

    the_result = cleanup_the_result(the_result)
    return the_result


# #############################################################################################
# Construct Task Action output line
# #############################################################################################
def build_action(alist, tcode, code_element, indent, indent_amt):
    # Calculate total indentation to put in front of action
    count = indent
    if count != 0:
        tcode = indent_amt + tcode
        count = 0
    if count < 0:
        tcode = indent_amt + tcode

    # Break-up very long actions at new line
    if tcode != "":
        newline = tcode.find("\n")  # Break-up new line breaks
        tcode_len = len(tcode)
        # If no new line break or line break less than width set for browser, just put it as is
        # Otherwise, make it a continuation line using '...' has the continuation flag
        if newline == -1 and tcode_len > 80:
            alist.append(tcode)
        else:
            array_of_lines = tcode.split("\n")
            count = 0
            for item in array_of_lines:
                if count == 0:
                    alist.append(item)
                else:
                    alist.append(f"...{item}")
                count += 1
                if (
                    count == CONTINUE_LIMIT
                ):  # Only display up to so many continued lines
                    alist.append(
                        f'<font color:red> ... continue limit of {str(CONTINUE_LIMIT)} reached.  See "CONTINUE_LIMIT =" in code for details'
                    )
                    break
    else:
        alist.append(f"Action {code_element.text}: not yet mapped")
    return
