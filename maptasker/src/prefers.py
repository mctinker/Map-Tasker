#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# prefers: Process Tasker's Preferences                                                      #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #

import re
from operator import itemgetter

from maptasker.src.frmthtml import format_html
from maptasker.src.servicec import service_codes
from maptasker.src.error import error_handler


def process_service(
    primary_items: dict,
    service_name: str,
    service_value: str,
    temp_output_lines,
) -> None:
    """
    We have a service xml element that we have mapped as a preference.  Process it.
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :param service_name: name of the preference in <Service xml
        :param service_value: value of the preference in <Service xml
        :param temp_output_lines: list of service/preference output lines
    """
    preferences_html = format_html(
        primary_items["colors_to_use"], "preferences_color", "", "", False
    )
    blank = "&nbsp;"

    # Get the name to display
    output_service_name = service_codes[service_name]["display"]
    # Left justify and fill to 15 characters
    output_service_name = output_service_name.ljust(45, '.')

    # If value is a selected item from list, get the item
    if "values" in service_codes[service_name]:
        service_value = service_codes[service_name]["values"][int(service_value)]

    # Handle special cases
    # Tasker icon default is "cust_notification"
    if service_value == "cust_notification":
        service_value = "Default"

    # Accessibility: parse value to get a list of settings
    elif service_name == "PREF_KEEP_ACCESSIBILITY_SERVICES_RUNNING":
        package_names = ""
        packages = [m.start() for m in re.finditer('"packageName":', service_value)]
        packages_end = [m.start() for m in re.finditer('}', service_value)]
        for number, position in enumerate(packages):
            package_names = (
                f"{package_names}<br>{blank * 50}{service_value[position + 14:packages_end[number]]}"
            )
        service_value = package_names

    # Add the service name to the output list
    temp_output_lines.append(
        [
            service_codes[service_name]['num'],
            (
                format_html(
                    primary_items["colors_to_use"],
                    "preferences_color",
                    "",
                    (
                        f"{preferences_html}{blank * 2}{output_service_name}{blank * 4}{service_value}"
                    ),
                    True,
                )
            ),
        ]
    )


def process_preferences(primary_items: dict, temp_output_lines: list) -> None:
    """
    Go through all of the <service> xml elements to process the Tasker preferences
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :param temp_output_lines: list of service/preference output lines
        :return: nothing
    """
    dummy_num = 100
    first_time = True
    blank = "&nbsp;"

    # Go through each <service> xml element
    for service in primary_items["tasker_root_elements"]["all_services"]:
        # Make sure the <Setting> xml element is valid
        if all(service.find(tag) is not None for tag in ("n", "t", "v")):
            # Get the service codes
            service_name = service.find("n").text or ""
            service_type = service.find("t").text or ""
            service_value = service.find("v").text or ""

            # See if the service name is in our dictionary of preferences
            if service_name in service_codes:
                # Got a hit.  Go process it.
                process_service(
                    primary_items, service_name, service_value, temp_output_lines
                )

            # If debugging, list specific preferences which can't be identified.
            elif primary_items["program_arguments"]["debug"]:
                # Add a blank line and the output details to our list of output stuff
                # Add a blank line if this is the first unmapped item
                if first_time:
                    first_time = False
                    temp_output_lines.append([dummy_num, "<br>"])
                # Add the output details to our list of output stuff
                temp_output_lines.append(
                    [
                        dummy_num,
                        format_html(
                            primary_items["colors_to_use"],
                            "preferences_color",
                            "",
                            (
                                f"{blank * 2}Not yet"
                                f" mapped:{service_name}{blank * 4}type:{service_type}{blank * 4}value:{service_value}"
                            ),
                            True,
                        ),
                    ]
                )
                dummy_num += 1
        # Invalid <Setting> xml element
        else:
            error_handler(
                "Error: the backup xml file is corrupt.  Program terminated.", 3
            )

    return


def get_preferences(primary_items: dict) -> None:
    """
    Go through the Tasker <service> xml elements, each representing a Tasker preference
    :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
    :rtype: nothing
    """
    section_names = [
        "UI > General",
        "UI > Main Screen",
        "UI > UI Lock",
        "UI > Localization",
        "Monitor > General",
        "Monitor > Display On Monitoring",
        "Monitor > Display Off Monitoring",
        "Monitor > General Monitoring",
        "Monitor > Calibrate",
        "Action",
        "Action > Reset Error Notifications",
        "Misc",
        "Misc > Debugging",
        "Unlisted (Perhaps Deprecated)",
    ]
    temp_output_lines = []
    blank = "&nbsp;"

    # Output title line
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        4,
        format_html(
            primary_items["colors_to_use"],
            "preferences_color",
            "",
            "Tasker Preferences >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>",
            True,
        ),
    )

    # Go through each <Service xml element
    # We are going to put them all in a temporary output list to be sorted at the end:
    #   service number (for sorting on), and service details
    previous_section = None

    # Okay, let's deal with the Tasker preferences
    process_preferences(primary_items, temp_output_lines)

    # All service xml elements have been processed.
    # Sort our output by order of display in Tasker (key=list element 0)
    sorted_output = sorted(temp_output_lines, key=itemgetter(0))

    # Now output them: go through list of output lines (sorted) and "output" each
    for index, (num, line) in enumerate(sorted_output):
        section = next(
            (
                item[1]["section"]
                for item in service_codes.items()
                if item[1]["num"] == num
            ),
            None,
        )
        if section is not None and section != previous_section:
            # Add the preference in the order it appears in Tasker
            primary_items["output_lines"].add_line_to_output(
                primary_items,
                4,
                format_html(
                    primary_items["colors_to_use"],
                    "preferences_color",
                    "",
                    f"<br>&nbsp;Section: {section_names[section]}",
                    True,
                ),
            )
            previous_section = section
        primary_items["output_lines"].add_line_to_output(primary_items, 4, f"{line}")

    # Let user know that we have not mapped the remaining items
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        4,
        format_html(
            primary_items["colors_to_use"],
            "preferences_color",
            "",
            "The remaining preferences are not yet mapped",
            True,
        ),
    )
    primary_items["output_lines"].add_line_to_output(primary_items, 4, "")
