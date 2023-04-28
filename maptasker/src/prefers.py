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
import gc
import re
from operator import itemgetter

from maptasker.src.outputl import my_output
from maptasker.src.frmthtml import format_html
from maptasker.src.servicec import service_codes


def process_service(
    colormap: dict, service_name: str, service_value: str, output_lines: list
) -> None:
    """
    We have a service xml element that we have mapped as a preference.  Process it.
        :param colormap: colors to use in output
        :param service_name: name of the preference in <Service xml
        :param service_value: value of the preference in <Service xml
        :param output_lines: accumulated output lines generated thus far (to append to)
    """
    preferences_html = format_html(colormap, "preferences_color", "", "", False)
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

    output_lines.append(
        [
            service_codes[service_name]['num'],
            (
                format_html(
                    colormap,
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


def get_preferences(
    output_list: list, program_args: dict, colormap: dict, all_tasker_items: dict
) -> None:
    """
    Get Tasker 'preferences' and output them
        :param output_list: list of output lines generated thus far
        :param program_args: runtime arguments
        :param colormap: colors to use in putput
        :param all_tasker_items: all Project/Profile/Task/Scene/Service xml elements
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
    output_lines = []
    preferences_html = format_html(colormap, "preferences_color", "", "", False)
    blank = "&nbsp;"
    first_time = True

    # Output title line
    my_output(
        colormap,
        program_args,
        output_list,
        4,
        (
            format_html(
                colormap,
                "preferences_color",
                "",
                "Tasker Preferences >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>",
                True,
            )
        ),
    )

    # Go through each <Service xml element
    current_section = 999
    dummy_num = 100
    for service in all_tasker_items["all_services"]:
        service_name = service.find("n").text
        service_type = service.find("t").text
        service_value = service.find("v").text
        # See if the service name is in our dictionary of preferences
        if service_name in service_codes:
            # Got a hit.  Go process it.
            process_service(colormap, service_name, service_value, output_lines)

        # Preference not found
        elif program_args["debug"]:
            # Add a blank line if this is the first unmapped item
            if first_time:
                first_time = False
                output_lines.append([dummy_num, "<br>"])
            # Add the output details to our list of output stuff
            output_lines.append(
                [
                    dummy_num,
                    format_html(
                        colormap,
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

    # All service xml elements have been processed.
    # Sort our output by order of display in Tasker (key=list element 0)
    sorted_output = sorted(output_lines, key=itemgetter(0))

    # Now output them: go through list of output lines (sorted) and "output" each
    for line in sorted_output:
        # See if we have a new preference section and display the section if new
        num = line[0]  # Get our current "num" key
        # Find this line's entry in our lookup dictionary
        for item in service_codes.items():
            if item[1]["num"] == num and current_section != item[1]["section"]:
                # Add the preference in the order it appears in Tasker
                my_output(
                    colormap,
                    program_args,
                    output_list,
                    4,
                    format_html(
                        colormap,
                        "preferences_color",
                        "",
                        f"<br>&nbsp;Section: {section_names[item[1]['section']]}",
                        True,
                    ),
                )
                current_section = item[1]["section"]
        my_output(colormap, program_args, output_list, 4, line[1])

    my_output(
        colormap,
        program_args,
        output_list,
        4,
        f"{preferences_html}<br>&nbsp;The remaining preferences are not yet mapped",
    )
    my_output(colormap, program_args, output_list, 4, "")

    # We are done with <Service xml elements
    del all_tasker_items["all_services"]
    gc.collect()
    return
