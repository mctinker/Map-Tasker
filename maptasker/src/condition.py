"""Process profile condition: time, date, state, event, location, app"""

#! /usr/bin/env python3
#                                                                                      #
# condition: Process profile condition: time, date, state, event, location, app        #
#                                                                                      #
import defusedxml.ElementTree

import maptasker.src.actiond as process_action_codes
import maptasker.src.actione as action_evaluate

# action_codes: Master dictionary of Task action and Profile condition codes
from maptasker.src.actionc import action_codes
from maptasker.src.debug import not_in_dictionary
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import logger
from maptasker.src.taskflag import get_priority


# Profile condition: Time
def condition_time(the_item: defusedxml.ElementTree, the_output_condition: str) -> str:
    """
    Handle the "Time" condition
        :param the_item: the xml element with the Condition
        :param the_output_condition: text into which the condition output is to
            be formated
        :return: the formatted condition's output string
    """

    (
        to_hour,
        to_minute,
        from_hour,
        from_minute,
        rep,
        rep_type,
        from_variable,
        to_variable,
    ) = (
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
    )
    child = None
    for child in the_item:
        match child.tag:
            case "fh":
                from_hour = child.text
            case "fm":
                from_minute = child.text
            case "th":
                to_hour = child.text
            case "tm":
                to_minute = child.text
            case "rep":
                rep_type = " minutes " if child.text == "2" else " hours "
            case "repval":
                rep = f" repeat every {child.text}{rep_type}"
            case "fromvar":
                from_variable = child.text
            case "tovar":
                to_variable = child.text
            case _:
                child.text = "Rutroh"

    if from_hour or from_minute:
        the_output_condition = f"{the_output_condition}Time: from {from_hour}:{from_minute.zfill(2)}{rep}"

    if to_hour or to_minute:
        the_output_condition = f"{the_output_condition} to {to_hour}:{to_minute.zfill(2)}"
    elif from_variable or to_variable:
        the_output_condition = f"{the_output_condition}Time: from {from_variable} to {to_variable} {rep}"
    else:
        the_output_condition = f"{the_output_condition}{child.text} not yet mapped!"
        not_in_dictionary("Condition Time", child.text)
    return the_output_condition


# Profile condition: Day
def condition_day(the_item: defusedxml.ElementTree.XML, the_output_condition: str) -> str:
    """
    Handle the "Day" condition
        :param the_item: the xml element with the Condition
        :param the_output_condition: text into which the condition output is to
            be formated
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

    the_days_of_week = ""
    days_of_month = ""
    the_months = ""
    for child in the_item:
        if "wday" in child.tag:
            the_days_of_week = f"{the_days_of_week}{weekdays[int(child.text) - 1]} "
        elif "mday" in child.tag:
            days_of_month = f"{days_of_month}{child.text} "
        elif "mnth" in child.tag:
            the_months = f"{the_months}{months[int(child.text)]} "
        else:
            break
    if the_days_of_week:
        the_output_condition = f"{the_output_condition}Days of Week: {the_days_of_week}"
    if days_of_month:
        the_output_condition = f"{the_output_condition}Days of Month: {days_of_month} "
    if the_months:
        the_output_condition = f"{the_output_condition}Months: {the_months} "
    return the_output_condition


# Profile condition: State
def condition_state(the_item: defusedxml.ElementTree.XMLParse, the_output_condition: str) -> str:
    """
    Handle the "State" condition
        :param the_item: the xml element with the Condition
        :param the_output_condition: text into which the condition output is to
            be formated
        :return: the formatted condition's output string
    """
    for child in the_item:
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

            # Add this State to any preceding State
            the_output_condition = f"{the_output_condition}State: {state}"
            invert = the_item.find("pin")
            if invert is not None and invert.text == "true":
                the_output_condition = f"{the_output_condition} <em>[inverted]</em>"
            if PrimeItems.program_arguments["debug"]:
                the_output_condition = f"{the_output_condition} (code:{child.text})"
        return the_output_condition
    return ""


# Profile condition: Event
def condition_event(the_item: defusedxml.ElementTree.XMLParse, the_output_condition: str) -> str:
    """
    Handle the "Event" condition
        :param the_item: the xml element with the Condition
        :param the_output_condition: text into which the condition output is to
            be formatted
        :return: the formatted condition's output string
    """
    the_event_code = the_item.find("code")

    # Determine what the Event code is and return the actual Event text
    logger.debug(f"code:{the_event_code.text}")
    event_code = f"{the_event_code.text}e" if "e" not in the_event_code.text else the_event_code.text
    if event_code not in action_codes:
        # Build new (template_ action code if not in our dictionary of codes yet
        process_action_codes.build_action_codes(the_event_code, the_item)  # Add it to our action dictionary
    # the_event_code.text = event_code
    event = action_evaluate.get_action_code(
        the_event_code,
        the_item,
        False,
        "e",
    )
    # Get the event priority
    event = f"{event}{get_priority(the_item, True)}"

    the_output_condition = f"{the_output_condition}Event: {event}"
    if PrimeItems.program_arguments["debug"]:  # if program_args['debug'] then add the code
        the_output_condition = f"{the_output_condition} (code:{the_event_code.text})"
    return the_output_condition


# Profile condition: App (application)
def condition_app(item: defusedxml.ElementTree.XMLParse, condition: str) -> str:
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
def condition_loc(item: defusedxml.ElementTree.XMLParse, condition: str) -> str:
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
    ignore_items = ["cdate", "edate", "flags", "id", "ProfileVariable"]
    condition = ""  # Assume no condition

    # Go through Profile'x sub-XML looking for conditions
    for item in the_profile:
        if item.tag in ignore_items or "mid" in item.tag:  # Bypass junk we don't care about
            continue
        if condition:  # If we already have a condition, add 'and' (italicized)
            condition = f"{condition} <em>AND</em> "

        # Find out what the condition is and handle it.
        if item.tag in function_map:
            condition = function_map[item.tag](item, condition)

    return "" if condition == "" else f"{condition}"
