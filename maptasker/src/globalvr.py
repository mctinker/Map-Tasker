"""Display global variables in output HTML"""

#! /usr/bin/env python3

#                                                                                      #
# variables: process Tasker variables.                                                 #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #

import defusedxml.ElementTree  # Need for type hints

from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import NORMAL_TAB, TABLE_BACKGROUND_COLOR, TABLE_BORDER, FormatLine

# What each built-in variable is called in Tasker's own documentation, for anywhere a person
# has to *choose* one rather than read one -- the Version 2 Scene designer's Show When picker
# is the first such place ("Airplane Mode Status", not "%AIR", which nobody browses by).
#
# Transcribed from https://tasker.joaoapps.com/userguide-donut/de/variables.html, under
# "Built-in Variables".  That page documents 83 of the 101 names in tasker_global_variables
# below; the other 18 (%HUMIDITY, %PRESSURE, %SDK, %ROOT, the %DEV* and %CAL* families, ...)
# postdate it and are deliberately absent here rather than given a name this app invented --
# callers fall back to showing the variable itself, which is at least always true.
#
# Three names go the other way, documented but missing from the list below: %CLIP, %QTIME and
# %UIMODE.  They are named here so the picker can still offer them.  Note %UIMODE against the
# list's %UIMOD -- one of the two is a typo, and since it is not clear which, both are left
# in place rather than one being silently "corrected" into a variable that never matches.
tasker_global_variable_names = {
    "%AIR": "Airplane Mode Status",
    "%BATT": "Battery Level",
    "%BLUE": "Bluetooth Status",
    "%CNAME": "Call Name (In)",
    "%CNUM": "Call Number (In)",
    "%CDATE": "Call Date (In)",
    "%CTIME": "Call Time (In)",
    "%CONAME": "Call Name (Out)",
    "%CONUM": "Call Number (Out)",
    "%CODATE": "Call Date (Out)",
    "%COTIME": "Call Time (Out)",
    "%CODUR": "Call Duration (Out)",
    "%CELLID": "Cell ID",
    "%CELLSIG": "Cell Signal Strength",
    "%CELLSRV": "Cell Service State",
    "%CLIP": "Clipboard Contents",
    "%CPUFREQ": "CPU Frequency",
    "%CPUGOV": "CPU Governor",
    "%DATE": "Date",
    "%DAYM": "Day of the Month",
    "%DAYW": "Day of the Week",
    "%BRIGHT": "Display Brightness",
    "%DTOUT": "Display Timeout",
    "%EFROM": "Email From",
    "%ECC": "Email Cc",
    "%ESUBJ": "Email Subject",
    "%EDATE": "Email Date",
    "%ETIME": "Email Time",
    "%MEMF": "Free Memory",
    "%GPS": "GPS Status",
    "%HTTPR": "HTTP Response Code",
    "%HTTPD": "HTTP Response Data",
    "%HTTPL": "HTTP Content Length",
    "%KEYG": "Keyguard Status",
    "%LAPP": "Last Application",
    "%FOTO": "Last Photo",
    "%LIGHT": "Light Level",
    "%LOC": "Location",
    "%LOCACC": "Location Accuracy",
    "%LOCALT": "Location Altitude",
    "%LOCSPD": "Location Speed",
    "%LOCTMS": "Location Fix Time Seconds",
    "%LOCN": "Location (Net)",
    "%LOCNACC": "Location Accuracy (Net)",
    "%LOCNTMS": "Location Fix Time (Net)",
    "%MTRACK": "Music Track",
    "%MUTED": "Muted",
    "%NIGHT": "Night Mode",
    "%NTITLE": "Notification Title",
    "%PNUM": "Phone Number",
    "%PACTIVE": "Profiles Active",
    "%PENABLED": "Profiles Enabled",
    "%ROAM": "Roaming",
    "%SCREEN": "Screen",
    "%SILENT": "Silent Mode",
    "%SIMNUM": "SIM Serial Number",
    "%SIMSTATE": "SIM State",
    "%SPHONE": "Speakerphone",
    "%SPEECH": "Speech",
    "%QTIME": "Task Queue Seconds",
    "%TRUN": "Tasks Running",
    "%TNET": "Telephone Network",
    "%SMSRF": "Text From",
    "%SMSRN": "Text Name",
    "%SMSRB": "Text Body",
    "%SMSRD": "Text Date",
    "%MMSRS": "Text Subject",
    "%SMSRT": "Text Time",
    "%TIME": "Time",
    "%TIMES": "Time Seconds",
    "%UIMODE": "UI Mode",
    "%UPS": "Uptime Seconds",
    "%VOLA": "Volume - Alarm",
    "%VOLC": "Volume - Call",
    "%VOLD": "Volume - DTMF",
    "%VOLM": "Volume - Media",
    "%VOLN": "Volume - Notification",
    "%VOLR": "Volume - Ringer",
    "%VOLS": "Volume - System",
    "%WIFII": "WiFi Info",
    "%WIFI": "WiFi Status",
    "%WIMAX": "Wimax Status",
    "%WIN": "Window Label",
}

# List of Tasker global variables
tasker_global_variables = [
    "%AIR",
    "%AIRR",
    "%BATT",
    "%BLUE",
    "%CALS",
    "%CALTITLE",
    "%CALDESCR",
    "%CALLOC",
    "%CNAME",
    "%CNUM",
    "%CDATE",
    "%CTIME",
    "%CONAME",
    "%CONUM",
    "%CODATE",
    "%COTIME",
    "%CODUR",
    "%CELLID",
    "%CELLSIG",
    "%CELLSRV",
    "%CPUFREQ",
    "%CPUGOV",
    "%DATE",
    "%DAYM",
    "%DAYW",
    "%DEVID",
    "%DEVMAN",
    "%DEVMOD",
    "%DEVPROD",
    "%DEVTID",
    "%BRIGHT",
    "%DTOUT",
    "%EFROM",
    "%ECC",
    "%ESUBJ",
    "%EDATE",
    "%ETIME",
    "%MEMF",
    "%GPS",
    "%HEART",
    "%HTTPR",
    "%HTTPD",
    "%HTTPL",
    "%HUMIDITY",
    "%IMETHOD",
    "%INTERRUPT",
    "%KEYG",
    "%LAPP",
    "%FOTO",
    "%LIGHT",
    "%LOC",
    "%LOCACC",
    "%LOCALT",
    "%LOCSPD",
    "%LOCTMS",
    "%LOCN",
    "%LOCNACC",
    "%LOCNTMS",
    "%MFIELD",
    "%MTRACK",
    "%MUTED",
    "%NIGHT",
    "%NTITLE",
    "%PNUM",
    "%PRESSURE",
    "%PACTIVE",
    "%PENABLED",
    "%ROAM",
    "%ROOT",
    "%SCREEN",
    "%SDK",
    "%SILENT",
    "%SIMNUM",
    "%SIMSTATE",
    "%SPHONE",
    "%SPEECH",
    "%TRUN",
    "%TNET",
    "%TEMP",
    "%SMSRF",
    "%SMSRN",
    "%SMSRB",
    "%MMSRS",
    "%SMSRD",
    "%SMSRT",
    "%TIME",
    "%TIMEMS",
    "%TIMES",
    "%UIMOD",
    "%UPS",
    "%VOLA",
    "%VOLC",
    "%VOLD",
    "%VOLM",
    "%VOLN",
    "%VOLR",
    "%VOLS",
    "%WIFII",
    "%WIFI",
    "%WIMAX",
    "%WIN",
]


# Read in the variables and save them for now.
def get_variables() -> None:
    """
    Read in and save the Tasker variables.
        Args:

    """
    # Get all of the Tasker variables
    if not (global_variables := PrimeItems.xml_root.findall("Variable")):
        return
    # Save each in a dictionary.
    # Loop through the variables.
    for variable in global_variables:
        for num, child in enumerate(variable):
            if num == 0:
                variable_name = child.text
            else:
                variable_value = child.text

        # Format the output
        if variable_value:
            variable_value = variable_value.replace(",", "<br>")
            variable_value = variable_value.replace(" ", "&nbsp;")

        # Add it to our dictionary
        PrimeItems.variables[variable_name] = {
            "value": variable_value,
            "project": [],
            "verified": True,
        }


# Print the variables (Project's or Unreferenced)
def print_the_variables(color_to_use: str, project: defusedxml.ElementTree) -> None:
    """Parameters:
        - color_to_use (str): The color to use for the table definition.
        - project (defusedxml.ElementTree): The project to use, if applicable.
    Returns:
        - None: This function does not return anything.
    Processing Logic:
        - Create table definition.
        - Create empty list for variable output lines.
        - Sort the Tasker global variables.
        - If the key is a Tasker global variable, change the value to "global".
        - If project is not None or an empty string, find the Project.
        - If the variable has a list of Projects, extend the variable output lines with the key and value.
        - If the variable is a verified "tasker variable" and not a Project global variable, append the key and value to the variable output lines.
        - Return the variable output lines."""
    table_definition = f'<td style="height:16px; color:{color_to_use}; text-align:left">'
    variable_output_lines = []

    # Go through all of the Tasker global variables.
    for key, value in sorted(PrimeItems.variables.items()):
        # If this is a Tasker global variable, change the value to "global"
        if key in tasker_global_variables:
            value["value"] = "<em>Tasker Global</em>"

        # If doing the Project variables, first find the Project
        if project is not None and project != "":
            # Does this variable have a list of Projects?
            if PrimeItems.variables[key]["project"]:
                variable_output_lines.extend(
                    [
                        f"<tr>{table_definition}{key}</td>{table_definition}{value['value']}</td></tr>"
                        for variable_project in PrimeItems.variables[key]["project"]
                        if variable_project["xml"] == project
                    ],
                )

        # If this is a verified "tasker variable", and not a Project global var?
        elif PrimeItems.variables[key]["verified"] and not PrimeItems.variables[key]["project"]:
            # It is an unrefereenced variable.
            variable_output_lines.append(
                f"<tr>{table_definition}{key}</td>{table_definition}{value['value']}</td></tr>",
            )

    return variable_output_lines


# Print variables by adding them to the output.
def output_variables(heading: str, project: defusedxml.ElementTree) -> None:
    """
    Print variables by adding them to the output.
        Args:

            heading (str): Heading to print.
            project (xml.etree.ElementTree): Project to print.
    """
    if not PrimeItems.variables:
        return
    # Add a directory entry for variables.
    if (project is None or project == "") and PrimeItems.program_arguments["directory"]:
        PrimeItems.output_lines.add_line_to_output(
            5,
            '<a id="unreferenced_variables"></a>',
            FormatLine.dont_format_line,
        )

    # Output unreferenced global variables.  The Project will be "".
    # Force an indentation and set color to use in output.
    if project is None or project == "":
        color_to_use = PrimeItems.colors_to_use["trailing_comments_color"]
        color_name = "trailing_comments_color"
        PrimeItems.output_lines.add_line_to_output(
            1,
            "",
            ["", "trailing_comments_color", FormatLine.add_end_span],
        )
        # Print a ruler
        PrimeItems.output_lines.add_line_to_output(
            5,
            "<br><hr>",
            FormatLine.dont_format_line,
        )
    else:
        color_to_use = PrimeItems.colors_to_use["project_color"]
        color_name = "project_color"

    # Print the heading if we have global variables.
    if variable_output_lines := print_the_variables(color_to_use, project):
        PrimeItems.output_lines.add_line_to_output(
            5,
            f"<br>{NORMAL_TAB}{heading}",
            ["", color_name, FormatLine.add_end_span],
        )

        # Define table
        table_definition = f'{TABLE_BORDER}<table cellspacing="1" cellpadding="2" border="1" style="height:16px; margin-left: 20;color:{color_to_use};background-color:{TABLE_BACKGROUND_COLOR};font-family:{PrimeItems.program_arguments["font"]};text-align:left">\n<tr>\n<th>Name</th>\n<th>Value</th>\n</tr>'
        PrimeItems.output_lines.add_line_to_output(
            5,
            table_definition,
            FormatLine.dont_format_line,
        )

        # Now go through our dictionary outputing the (sorted) variables
        for line in variable_output_lines:
            PrimeItems.output_lines.add_line_to_output(
                5,
                line,
                FormatLine.dont_format_line,
            )

        # Wrap things up
        # End table
        PrimeItems.output_lines.add_line_to_output(
            5,
            "</table><br>",
            FormatLine.dont_format_line,
        )
        # Un-indent the output only if doing unreferenced variables.
        if project is None or project == "":
            PrimeItems.output_lines.add_line_to_output(
                3,
                "",
                FormatLine.dont_format_line,
            )
