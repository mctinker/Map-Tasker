#! /usr/bin/env python3
"""Process profile condition: time, date, state, event, location, app"""

#                                                                                      #
# condition: Process profile condition: time, date, state, event, location, app        #
#                                                                                      #
import defusedxml.ElementTree

import maptasker.src.actiond as process_action_codes
import maptasker.src.actione as action_evaluate
from maptasker.src.actargs import extract_condition

# action_codes: Master dictionary of Task action and Profile condition codes
from maptasker.src.actionc import action_codes
from maptasker.src.debug import not_in_dictionary
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import logger
from maptasker.src.taskflag import get_priority
from maptasker.src.tasks import reformat_html

space = "&nbsp;"
spaces = f"{space * 50}"


# Profile condition: Time
def condition_time(the_item: defusedxml.ElementTree, the_output_condition: str) -> str:
    """
    Handle the "Time" condition.

    :param the_item: The XML element with the Condition.
    :param the_output_condition: The base condition output text.
    :return: The formatted condition output string.
    """

    time_values = {
        "fh": "",
        "fm": "",
        "th": "",
        "tm": "",
        "rep": "",
        "rep_type": "",
        "fromvar": "",
        "tovar": "",
        "cname": "",
    }

    for child in the_item:
        match child.tag:
            case "fh" | "fm" | "th" | "tm" | "fromvar" | "tovar":
                time_values[child.tag] = child.text or ""
            case "rep":
                time_values["rep_type"] = " minutes " if child.text == "2" else " hours "
            case "repval":
                time_values["rep"] = f" repeat every {child.text}{time_values['rep_type']}"
            case "cname":
                time_values["cname"] = f" Name={child.text}"
            case _:
                return (
                    f"{the_output_condition}{child.text} not yet mapped!",
                    not_in_dictionary(
                        "Condition Time",
                        child.text,
                    ),
                )

    from_time = f"{time_values['fh']}:{time_values['fm'].zfill(2)}"
    to_time = f"{time_values['th']}:{time_values['tm'].zfill(2)}"
    from_variable, to_variable = time_values["fromvar"], time_values["tovar"]
    rep = time_values["rep"]

    if from_time.strip(":"):
        the_output_condition += f"Time: from {from_time}{rep}"
        if to_time.strip(":"):
            the_output_condition += f" to {to_time}"
    elif from_variable or to_variable:
        the_output_condition += f"Time: from {from_variable} to {to_variable} {rep}"

    return the_output_condition + time_values["cname"]


# Profile condition: Day
def condition_day(the_item: defusedxml.ElementTree, the_output_condition: str) -> str:
    """
    Handle the "Day" condition
        :param the_item: the xml element with the Condition
        :param the_output_condition: text into which the condition output is to
            be formatted
        :return: the formatted condition's output string
    """
    weekdays = [
        "Sunday",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
    ]
    months = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]

    results = {"wday": [], "mday": [], "mnth": [], "cname": ""}

    for child in the_item:
        if "wday" in child.tag:
            results["wday"].append(weekdays[int(child.text) - 1])
        elif "mday" in child.tag:
            results["mday"].append(child.text)
        elif "mnth" in child.tag:
            results["mnth"].append(months[int(child.text)])
        elif "cname" in child.tag:
            results["cname"] = f" ,Name={child.text}"

    formatted_parts = [
        f"Days of Week: {' '.join(results['wday'])}" if results["wday"] else "",
        f"Days of Month: {' '.join(results['mday'])}" if results["mday"] else "",
        f"Months: {' '.join(results['mnth'])}" if results["mnth"] else "",
        results["cname"],
    ]

    return the_output_condition + " ".join(filter(None, formatted_parts)) + " "


# Profile condition: State
def condition_state(
    the_item: defusedxml.ElementTree,
    the_output_condition: str,
) -> str:
    """
    Handle the "State" condition
        :param the_item: the xml element with the Condition
        :param the_output_condition: text into which the condition output is to
            be formated
        :return: the formatted condition's output string
    """
    # Go through the XML for this 'State', looking for items of interest.
    for child in the_item:
        # Process the state code
        if child.tag == "code":
            logger.debug(f"condition_state:{child.text}")
            state_code = f"{child.text}s" if "s" not in child.text else child.text
            if state_code not in action_codes:
                process_action_codes.build_action_codes(
                    child,
                    the_item,
                )  # Add it to our action dictionary
            # child.text = state_code
            state = action_evaluate.get_action_code(
                child,
                the_item,
                False,
                "s",
            )

            # If pretty text, then reformat it.
            if "Configuration Parameter(s):" in state and PrimeItems.program_arguments["pretty"]:
                state = reformat_html(state)

            # Add this State to any preceding State
            state = state.replace("\n", spaces)
            the_output_condition = f"{the_output_condition}State: {state}"
            invert = the_item.find("pin")
            if invert is not None and invert.text == "true":
                the_output_condition = f"{the_output_condition} <em>[inverted]</em>"
            if PrimeItems.program_arguments["debug"]:
                the_output_condition = f"{the_output_condition} (code:{child.text})"

        elif child.tag == "ConditionList":
            evaluated_results = {}
            extract_condition(evaluated_results, "0", "", the_item)
            the_output_condition = f"{the_output_condition}, Condition(s): {evaluated_results['arg0']['value']}"
            break

    return the_output_condition
    # return ""


# Profile condition: Event
def condition_event(
    the_item: defusedxml.ElementTree,
    the_output_condition: str,
) -> str:
    """
    Handle the "Event" condition
        :param the_item: the xml element with the Condition
        :param the_output_condition: text into which the condition output is to
            be formatted
        :return: the formatted condition's output string
    """
    the_event_code = the_item.find("code")

    # Determine what the Event code is and return the actual Event text
    event_code = f"{the_event_code.text}e" if "e" not in the_event_code.text else the_event_code.text
    if event_code not in action_codes:
        logger.debug(f"code:{the_event_code.text} not found in action codes!")
        # Build new (template_ action code if not in our dictionary of codes yet
        process_action_codes.build_action_codes(
            the_event_code,
            the_item,
        )  # Add it to our action dictionary

    # Get the event code and its arguments with spacing added for 'pretty' text
    # the_event_code.text = event_code
    event = action_evaluate.get_action_code(
        the_event_code,
        the_item,
        False,
        "e",
    )

    # If pretty text, then reformat it.
    if "Configuration Parameter(s):" in event and PrimeItems.program_arguments["pretty"]:
        event = reformat_html(event)

    # Get the event priority
    event = f"{event}{get_priority(the_item, True)}"

    # Handle any conditions in the Event
    condition_list = the_item.find("ConditionList")
    if condition_list is not None:
        evaluated_results = {}
        extract_condition(evaluated_results, "0", "", the_item)
        event = f"{event}, Condition(s): {evaluated_results['arg0']['value']}"

    # Format the Event text
    event = event.replace("\n", "<br>")
    the_output_condition = f"{the_output_condition}Event: {event}"
    if PrimeItems.program_arguments["debug"]:  # if program_args['debug'] then add the code
        the_output_condition = f"{the_output_condition} (code:{the_event_code.text})"
    return the_output_condition


# Profile condition: App (application)
def condition_app(item: defusedxml.ElementTree, condition: str) -> str:
    """
    Handle the "App" condition
        :param the_item: the xml element with the Condition
        :param the_output_condition: text into which the condition output is to
            be formatted
        :return: the formatted condition's output string
    """
    the_apps = ""
    for apps in item:
        if "label" in apps.tag:
            the_apps = f"{the_apps} {apps.text}"
    return f"{condition}Application:{the_apps}"


# Profile condition: Loc (location)
def condition_loc(item: defusedxml.ElementTree, condition: str) -> str:
    """
    Handle the "Location" condition
        :param the_item: the xml element with the Condition
        :param the_output_condition: text into which the condition output is to
            be formatted
        :return: the formatted condition's output string
    """
    lat = item.find("lat").text
    lon = item.find("long").text
    rad = item.find("rad").text
    if lat:
        return f"{condition}Location with latitude {lat} longitude {lon} radius {rad}"
    return ""


# Given a Profile, return its list of conditions
def parse_profile_condition(the_profile: defusedxml.ElementTree) -> str:
    """
    Given a Profile, return its list of conditions
        :param the_profile: the xml element pointing to <Profile object
        :return: the formatted condition's output string
    """
    # Map of our functions to call based on the tag on the Profile item
    function_map = {
        "Time": condition_time,
        "Day": condition_day,
        "State": condition_state,
        "Event": condition_event,
        "App": condition_app,
        "Loc": condition_loc,
    }
    ignore_items = [
        "cdate",
        "edate",
        "flags",
        "id",
        "ProfileVariable",
        "nme",
        "mid",
        "pri",
    ]
    condition = ""  # Assume no condition

    # Go through Profile'x sub-XML looking for conditions
    for item in the_profile:
        if item.tag in ignore_items or "mid" in item.tag:  # Bypass junk we don't care about
            continue
        if condition:  # If we already have a condition, add 'and' (italicized)
            condition = f"{condition}, <em>AND</em> "

        # Find out what the condition is and handle it.
        if item.tag in function_map:
            condition = function_map[item.tag](item, condition)

    return condition
