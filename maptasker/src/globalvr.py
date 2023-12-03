#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# variables: process Tasker variables.                                                 #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
import defusedxml.ElementTree  # Need for type hints

from maptasker.src.sysconst import FormatLine
from maptasker.src.primitem import PrimeItems

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


# ##################################################################################
# Read in the variables and save them for now.
# ##################################################################################
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


# ##################################################################################
# Print the variables (Project's or Unreferenced)
# ##################################################################################
def print_the_variables(color_to_use: str, project: defusedxml.ElementTree) -> None:
    """
    Print the variables (Project's or Unreferenced)
        Args:
            color_to_use (str): Colot to use in the output.
            project (xml element): xml element of the Project.
        Return: list of output lines to be added to output queue.
    """
    table_definition = f'<td style="height:16px; color:{color_to_use}; text-align:left">'
    variable_output_lines = []

    # Go through all of the Tasker global variables.
    for key, value in sorted(PrimeItems.variables.items()):
        # If this is a Tasker global variable, change the value to "global"
        if key in tasker_global_variables:
            value["value"] = "<em>Tasker Global</em>"

        # If doing the Project variables, first find the Project
        if project:
            # Does this variable have a list of Projects?
            if PrimeItems.variables[key]["project"]:
                variable_output_lines.extend(
                    f'<tr>{table_definition}{key}</td>{table_definition}{value["value"]}</td></tr>'
                    for variable_project in PrimeItems.variables[key]["project"]
                    if variable_project["xml"] == project
                )
        # If this is a verified "tasker variable", and not a Project global var?
        elif PrimeItems.variables[key]["verified"] and not PrimeItems.variables[key]["project"]:
            variable_output_lines.append(f"<tr>{table_definition}{key}</td>{table_definition}{value}</td></tr>")

    return variable_output_lines


# ##################################################################################
# Print variables by adding them to the output.
# ##################################################################################
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
    if not project and PrimeItems.program_arguments["directory"]:
        PrimeItems.output_lines.add_line_to_output(
            5,
            '<a id="unreferenced_variables"></a>',
            FormatLine.dont_format_line,
        )

    # Force an indentation and set color to use in output.
    if not project:
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

    if variable_output_lines := print_the_variables(color_to_use, project):
        PrimeItems.output_lines.add_line_to_output(
            5,
            heading,
            ["", color_name, FormatLine.add_end_span],
        )

        # Define table
        table_definition = f'<table cellspacing="1" cellpadding="2" border="1" style="height:16px; color:{color_to_use}; text-align:left">\n<tr>\n<th>Name</th>\n<th>Value</th>\n</tr>'
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
        if not project:
            PrimeItems.output_lines.add_line_to_output(
                3,
                "",
                FormatLine.dont_format_line,
            )
