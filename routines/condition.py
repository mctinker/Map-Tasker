# ########################################################################################## #
#                                                                                            #
# condition: Process profile condition: time, date, state, event, location, app              #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #
from routines import actione as action_evaluate, actiond as process_action_codes
from routines.actionc import *  # action_codes: Master dictionary of Task action and Profile condition codes
from routines.sysconst import logger


# #######################################################################################
# Profile condition: Time
# #######################################################################################
def condition_time(the_item, cond_string):
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

    if from_hour or from_minute:
        cond_string = f"{cond_string}Time: from {from_hour}:{from_minute.zfill(2)}{rep}"

    if to_hour or to_minute:
        cond_string = f"{cond_string} to {to_hour}:{to_minute.zfill(2)}"
    elif from_variable or to_variable:
        cond_string = f"{cond_string}Time: from {from_variable} to {to_variable} {rep}"
    else:
        cond_string = cond_string + child.text + " not yet mapped"
    return cond_string


# #######################################################################################
# Profile condition: Day
# #######################################################################################
def condition_day(the_item, cond_string):
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
            the_days_of_week = the_days_of_week + weekdays[int(child.text) - 1] + " "
        elif "mday" in child.tag:
            days_of_month = days_of_month + child.text + " "
        elif "mnth" in child.tag:
            the_months = the_months + months[int(child.text)] + " "
        else:
            break
    if the_days_of_week:
        cond_string = f"{cond_string}Days of Week: {the_days_of_week}"
    if days_of_month:
        cond_string = f"{cond_string}Days of Month: {days_of_month} "
    if the_months:
        cond_string = f"{cond_string}Months: {the_months} "
    return cond_string


# #######################################################################################
# Profile condition: State
# #######################################################################################
def condition_state(the_item, cond_string, colormap, program_args):
    # mobile_network_type = {0: '2G', 1: '3G', 2: '3G HSPA', 3: '4G', 4: '5G'}
    # orientation_type = {0: 'Face Up', 1: 'Face Down', 2: 'Standing Up', 3: 'Upside Down', 4: 'Left Side',
    #                     5: 'Right Side'}
    for child in the_item:
        if child.tag == "code":
            logger.debug(f"condition_state:{child.text}")
            state_code = f"{child.text}s" if "s" not in child.text else child.text
            if state_code not in action_codes:
                process_action_codes.build_action_codes(
                    child, the_item, "s", program_args
                )  # Add it to our action dictionary
            # child.text = state_code
            state = action_evaluate.get_action_code(
                child, the_item, False, colormap, "s", program_args
            )

            # Add this State to any preceding State
            cond_string = f"{cond_string}State: {state}"
            invert = the_item.find("pin")
            if invert is not None and invert.text == "true":
                cond_string = f"{cond_string} <em>[inverted]</em>"
            if program_args["debug"]:
                cond_string = f"{cond_string} (code:{child.text})"
        return cond_string
    return


# #######################################################################################
# Profile condition: Event
# #######################################################################################
def condition_event(the_item, cond_string, colormap, program_args):
    the_event_code = the_item.find("code")

    # Determine what the Event code is and return the actual Event text
    logger.debug(f"code:{the_event_code.text}")
    if "e" not in the_event_code.text:
        event_code = f"{the_event_code.text}e"
    else:
        event_code = the_event_code.text
    if event_code not in action_codes:
        process_action_codes.build_action_codes(
            the_event_code, the_item, "e", program_args
        )  # Add it to our action dictionary
    # the_event_code.text = event_code
    event = action_evaluate.get_action_code(
        the_event_code, the_item, False, colormap, "e", program_args
    )

    cond_string = f"{cond_string}Event: {event}"
    if program_args["debug"]:  # if program_args['debug'] then add the code
        cond_string = f"{cond_string} (code:{the_event_code.text})"
    return cond_string


# #######################################################################################
# Given a Profile, return its list of conditions
# #######################################################################################
def parse_profile_condition(the_profile, colormap, program_args):
    ignore_items = ["cdate", "edate", "flags", "id", "ProfileVariable"]
    condition = ""  # Assume no condition
    for item in the_profile:
        if (
            item.tag in ignore_items or "mid" in item.tag
        ):  # Bypass junk we don't care about
            continue
        if condition:  # If we already have a condition, add 'and' (italicized)
            condition = f"{condition} <em>and</em> "

        # Find out what the condition is and handle it
        match item.tag:
            case "Time":
                condition = condition_time(item, condition)  # Get the Time condition

            case "Day":
                condition = condition_day(item, condition)

            case "State":
                condition = condition_state(item, condition, colormap, program_args)

            case "Event":
                condition = condition_event(item, condition, colormap, program_args)

            case "App":
                the_apps = ""
                for apps in item:
                    if "label" in apps.tag:
                        the_apps = f"{the_apps} {apps.text}"
                condition = f"{condition}Application:{the_apps}"

            case "Loc":
                lat = item.find("lat").text
                lon = item.find("long").text
                rad = item.find("rad").text
                if lat:
                    condition = f"{condition}Location with latitude {lat} longitude {lon} radius {rad}"

            case _:
                pass

    return "" if condition == "" else f"condition {condition}"
