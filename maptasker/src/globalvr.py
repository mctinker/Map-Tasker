"""Display global variables in output HTML"""

#! /usr/bin/env python3

#                                                                                      #
# variables: process Tasker variables.                                                 #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #

import html
from xml.etree.ElementTree import Element

from maptasker.src import caches, varxref
from maptasker.src.mapjump import VARIABLE, Target
from maptasker.src.maputils import fix_hyperlink_name
from maptasker.src.primitem import RunState
from maptasker.src.runcfg import RunConfig
from maptasker.src.sysconst import NORMAL_TAB, TABLE_BACKGROUND_COLOR, TABLE_BORDER, FormatLine
from maptasker.src.taskervars import tasker_global_variables

# The where-used counts for the table below, built once per run and reused for every
# Project's table.  Kept or dropped by get_variables, which runs once at the start of a Map.
#
# Cached rather than recomputed because varxref.build_index walks every Task action,
# Profile and Scene in the file: cheap once, but this table is emitted once per Project
# plus once for the unreferenced list, and doing that walk eighty times over would be the
# slowest thing in the Map.
_cross_reference: caches.Slot[dict | None] = caches.Slot("globalvr.cross_reference", None)
# Which configuration the counts above were worked out from (see get_variables).
_cross_reference_key: caches.Slot[str] = caches.Slot("globalvr.cross_reference_key", "")


# Read in the variables and save them for now.
def get_variables(configuration: str = "", *, state: RunState) -> None:
    """
    Read in and save the Tasker variables.
        :param configuration: a digest of the configuration these variables are being
            read from (mapcache.configuration_digest()), or "" when the caller cannot
            say.  The where-used counts are kept only while that stays the same.
    """
    # The counts describe one configuration.  A Map built again from that same
    # configuration -- the display detail level changed, a colour changed, a Project
    # picked out of the whole -- can have them as they stand rather than walking every
    # Task action in the file for a second time to arrive at the same numbers.  Anything
    # else, including a caller that cannot say what it is looking at, starts again.
    if not configuration or configuration != _cross_reference_key.value:
        _cross_reference.value = None
        _cross_reference_key.value = configuration

    # Get all of the Tasker variables
    if not (global_variables := state.xml_root.findall("Variable")):
        return
    # Save each in a dictionary.
    # Loop through the variables.
    for variable in global_variables:
        for num, child in enumerate(variable):
            if num == 0:
                variable_name = child.text
            else:
                variable_value = child.text

        # Format the output.  The value is data somebody stored in Tasker, not markup meant
        # to be rendered, so escape it before adding any of our own: a variable holding a
        # whole HTML document (a Scene V2 WebView's page, say) would otherwise have its
        # '<style>'/'<script>' turned loose on the map itself -- see get_display_text in
        # property.py, where the same thing blanked out an entire Project's Map view.
        if variable_value:
            variable_value = html.escape(variable_value)
            variable_value = variable_value.replace(",", "<br>")
            variable_value = variable_value.replace(" ", "&nbsp;")

        # Add it to our dictionary
        state.variables[variable_name] = {
            "value": variable_value,
            "project": [],
            "verified": True,
        }


def _get_cross_reference(state: RunState) -> dict:
    """{variable name: its varxref record}, for the names this table can show.

    Locals are left out: they are scoped to one Task, Profile or Scene, and this table is
    the file's global variables.  Built on first use rather than at import, so a Map run
    that never reaches detail level 4 never pays for it.
    """
    if _cross_reference.value is None:
        index = varxref.build_index(state=state)
        _cross_reference.value = {
            variable.name: variable for (name, owner), variable in index.variables.items() if owner == ""
        }
    return _cross_reference.value


def _usage_cell(references: list, table_definition: str, config: RunConfig, state: RunState) -> str:
    """One Set or Read cell: how many, linked to the Tasks it happens in.

    The count is the useful thing at a glance -- a zero in the Set column beside a
    non-zero Read is a variable being read that nothing fills.  The link is what turns
    the table from a list into an index, and it only appears when the directory is on:
    the 'tasks_<name>' anchors it jumps to are written by proclist.add_task_hyperlink,
    which is itself gated on that same setting, so linking without it would produce
    hyperlinks that land nowhere.
    """
    if not references:
        return f"{table_definition}0</td>"

    all_tasks = state.tasker_root_elements["all_tasks"]
    # Ordered, de-duplicated: a Task that sets a variable four times is one place to look.
    task_names = list(
        dict.fromkeys(
            all_tasks[reference.scope_id]["name"]
            for reference in references
            if reference.scope_id in all_tasks and all_tasks[reference.scope_id]["name"]
        ),
    )
    count = len(references)
    if not task_names or not config.directory:
        return f"{table_definition}{count}</td>"

    # Tooltip lists every Task; the link goes to the first, which is where a reader
    # starts.  Both are escaped -- a Task name is the user's text and can hold quotes.
    tooltip = html.escape(", ".join(task_names), quote=True)
    anchor = fix_hyperlink_name(task_names[0])
    return f'{table_definition}<a href="#tasks_{anchor}" title="{tooltip}">{count}</a></td>'


def _usage_cells(key: str, table_definition: str, config: RunConfig, state: RunState) -> str:
    """The Set and Read cells for one variable, or empty cells if it is not in the index."""
    variable = _get_cross_reference(state=state).get(key)
    if variable is None:
        return f"{table_definition}&nbsp;</td>{table_definition}&nbsp;</td>"
    return _usage_cell(variable.sets, table_definition, config, state=state) + _usage_cell(
        variable.reads, table_definition, config, state=state
    )


# Print the variables (Project's or Unreferenced)
def _variable_anchor(name: str, wanted: bool) -> str:
    """The id attribute that lets a report finding jump to this variable's row, or "".

    The id sits on the <tr> itself rather than on an anchor element inside it, which is
    the shape everything else in the Map uses (see mapjump.anchor_html).  A row is already
    a real element to highlight, and an <a> written between a <tr> and its <td>s is not
    valid table markup -- the browser would hoist it out of the table before the jump ever
    ran, leaving the id somewhere above the variable it names.
    """
    return f' id="{Target(VARIABLE, name).anchor}"' if wanted else ""


def print_the_variables(color_to_use: str, project: Element, config: RunConfig, state: RunState) -> None:
    """Parameters:
        - color_to_use (str): The color to use for the table definition.
        - project (Element): The project to use, if applicable.
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
    for key, value in sorted(state.variables.items()):
        # If this is a Tasker global variable, change the value to "global"
        if key in tasker_global_variables:
            value["value"] = "<em>Tasker Global</em>"

        # If doing the Project variables, first find the Project
        if project is not None and project != "":
            # Does this variable have a list of Projects?
            if state.variables[key]["project"]:
                # A variable used in three Projects gets a row in each of their tables, but
                # an HTML id may only appear once in a document -- so the anchor goes on the
                # row in the FIRST Project that uses it, and the rest are plain rows.  A jump
                # to the variable then lands on a real use of it rather than on nothing.
                first_project = state.variables[key]["project"][0]["xml"]
                variable_output_lines.extend(
                    [
                        f"<tr{_variable_anchor(key, variable_project['xml'] is first_project)}>"
                        f"{table_definition}{key}</td>{table_definition}{value['value']}</td>"
                        f"{_usage_cells(key, table_definition, config, state=state)}</tr>"
                        for variable_project in state.variables[key]["project"]
                        if variable_project["xml"] == project
                    ],
                )

        # If this is a verified "tasker variable", and not a Project global var?
        elif state.variables[key]["verified"] and not state.variables[key]["project"]:
            # It is an unrefereenced variable.
            variable_output_lines.append(
                f"<tr{_variable_anchor(key, True)}>"
                f"{table_definition}{key}</td>{table_definition}{value['value']}</td>"
                f"{_usage_cells(key, table_definition, config, state=state)}</tr>",
            )

    return variable_output_lines


# Print variables by adding them to the output.
def output_variables(heading: str, project: Element, config: RunConfig, state: RunState) -> None:
    """
    Print variables by adding them to the output.
        Args:

            heading (str): Heading to print.
            project (xml.etree.ElementTree): Project to print.
            config (RunConfig): the run's settings (directory, font and colors)
    """
    if not state.variables:
        return
    # Add a directory entry for variables.
    if (project is None or project == "") and config.directory:
        state.output_lines.add_line_to_output(
            5,
            '<a id="unreferenced_variables"></a>',
            FormatLine.dont_format_line,
        )

    # Output unreferenced global variables.  The Project will be "".
    # Force an indentation and set color to use in output.
    if project is None or project == "":
        color_to_use = config.colors["trailing_comments_color"]
        color_name = "trailing_comments_color"
        state.output_lines.add_line_to_output(
            1,
            "",
            ["", "trailing_comments_color", FormatLine.add_end_span],
        )
        # Print a ruler
        state.output_lines.add_line_to_output(
            5,
            "<br><hr>",
            FormatLine.dont_format_line,
        )
    else:
        color_to_use = config.colors["project_color"]
        color_name = "project_color"

    # Print the heading if we have global variables.
    if variable_output_lines := print_the_variables(color_to_use, project, config, state=state):
        state.output_lines.add_line_to_output(
            5,
            f"<br>{NORMAL_TAB}{heading}",
            ["", color_name, FormatLine.add_end_span],
        )

        # Define table
        table_definition = f'{TABLE_BORDER}<table cellspacing="1" cellpadding="2" border="1" style="height:16px; margin-left: 20;color:{color_to_use};background-color:{TABLE_BACKGROUND_COLOR};font-family:{config.font};text-align:left">\n<tr>\n<th>Name</th>\n<th>Value</th>\n<th>Set</th>\n<th>Read</th>\n</tr>'
        state.output_lines.add_line_to_output(
            5,
            table_definition,
            FormatLine.dont_format_line,
        )

        # Now go through our dictionary outputing the (sorted) variables
        for line in variable_output_lines:
            state.output_lines.add_line_to_output(
                5,
                line,
                FormatLine.dont_format_line,
            )

        # Wrap things up
        # End table
        state.output_lines.add_line_to_output(
            5,
            "</table><br>",
            FormatLine.dont_format_line,
        )
        # Un-indent the output only if doing unreferenced variables.
        if project is None or project == "":
            state.output_lines.add_line_to_output(
                3,
                "",
                FormatLine.dont_format_line,
            )
