#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# lineout: generate the output for a line                                                    #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #

import maptasker.src.actione as action_evaluate
from maptasker.src.debug import display_debug_info
from maptasker.src.frmthtml import format_html
from maptasker.src.sysconst import FONT_TO_USE
from maptasker.src.sysconst import UNKNOWN_TASK_NAME
from maptasker.src.sysconst import debug_out
from maptasker.src.sysconst import logger


class LineOut:
    def __init__(self):
        self.output_lines = []

    def refresh_our_output(
        self,
        primary_items: dict,
        include_the_profile: bool,
        project_name: str,
        profile_name: str,
    ) -> None:
        """
        For whatever reason, we need to clear out the existing output and start anew.
                :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
                :param include_the_profile: Boolean flag to indicate whether this is a Profile to be included
                :param project_name: name of the Project, if any
                :param profile_name: name of the Profile, if any
                :return: nothing
        """

        # Clear whatever is already in the output queue
        self.output_lines.clear()

        # Output the heading
        self.add_line_to_output(
            primary_items, 0, f'{FONT_TO_USE}{primary_items["heading"]}'
        )
        # If debugging, put out our runtime arguments first
        if primary_items["program_arguments"]["debug"]:
            display_debug_info(primary_items)

        # Start the Project list (<ul>)
        self.add_line_to_output(primary_items, 1, "")
        # Output the Project name as list item (<li>)
        self.add_line_to_output(
            primary_items,
            2,
            format_html(
                primary_items["colors_to_use"],
                "project_color",
                "",
                f"Project: {project_name}",
                True,
            ),
        )

        # Are we to include the Profile?
        if include_the_profile:
            # Start Profile list
            self.add_line_to_output(primary_items, 1, "")
            self.add_line_to_output(
                primary_items,
                2,
                format_html(
                    primary_items["colors_to_use"],
                    "profile_color",
                    "",
                    f"Profile: {profile_name}",
                    True,
                ),
            )
            self.add_line_to_output(primary_items, 1, "")  # Start Project list
        return

    # #############################################################################################
    # Generate an updated output line with HTML style details
    # Input is a dictionary containing the requirements:
    #  color1 - color to user
    #  color2 - optional 2nd color to use
    #  color3 - optional third color to tack onto end of string
    #  is_list - boolean: True= is a list HTML element
    #  span - boolean: True= requires a <span> element
    #  font - font to use
    # #############################################################################################
    def add_style(self, style_details: dict) -> str:
        """
        Add appropriate HTML style tags based on parameters in dictionary passed in
            :param style_details: True if we are to output a list (<li>), False if not
            :return: updated output line with style details added
        """
        line_with_style = ""
        if style_details["is_list"]:
            line_with_style = (
                f'<li style="color:{style_details["color1"]}"><span style="color:'
                f'{style_details["color2"]}{style_details["font"]}">'
                f'{style_details["element"]}</span></li>\n'
            )

        elif style_details["is_taskernet"]:
            line_with_style = (
                '<p style="margin-left:20px;margin-right:50px;color:'
                f'{style_details["color2"]}{FONT_TO_USE}">'
                f'{style_details["element"]}</p>\n'
                f'<p style="color:{style_details["color1"]}">'
            )
            line_with_style = line_with_style.replace("<span></span>", "")

        return line_with_style

    # #############################################################################################
    # Generate the output string based on the input XML <code> passed in
    # Returns a formatted string for output based on the input codes
    # #############################################################################################
    def format_line_list_item(
        self, primary_items, element: str, colormap: dict, font_to_use: str
    ) -> str:
        """
        Generate the output list (<li>) string based on the input XML <code> passed in
            :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
            :param element: text string to be added to output
            :param colormap:
            :param font_to_use:
            :return:
        """
        directory = ""

        # Project ========================
        if (
            f'{font_to_use}">Project:' in element
            or "Project has no Profiles" in element
        ):
            if primary_items["program_arguments"]["directory"]:
                directory_item = f'"{primary_items["directory_item"]}"'
                directory = f"<a id={directory_item}</a>\n"
            return f'{directory}<li style=color:{colormap["bullet_color"]}>{element}</li>\n'

        # Profile =========================
        elif f'{font_to_use}">Profile:' in element:
            if primary_items["program_arguments"]["directory"]:
                directory_item = f'"{primary_items["directory_item"]}"'
                directory = f"<a id={directory_item}</a>\n"
            return f'{directory}<br><li style=color:{colormap["bullet_color"]}>{element}</span></li>\n'

        # Task =========================
        elif element.startswith("Task:") or "&#45;&#45;Task:" in element:
            if UNKNOWN_TASK_NAME in element:
                return self.add_style(
                    style_details={
                        "is_list": True,
                        "color1": colormap["bullet_color"],
                        "color2": colormap["unknown_task_color"],
                        "font": font_to_use,
                        "element": element,
                    }
                )
            else:
                return self.add_style(
                    style_details={
                        "is_list": True,
                        "color1": colormap["bullet_color"],
                        "color2": colormap["task_color"],
                        "font": font_to_use,
                        "element": element,
                    }
                )

        # Scene =========================
        elif element.startswith("Scene:"):
            if primary_items["program_arguments"]["directory"]:
                directory_item = f'scene_{element.split("Scene:&nbsp;")[1]}'
                directory = f'<a id="{directory_item.replace(" ","_")}"</a>\n'
            return directory + self.add_style(
                style_details={
                    "is_list": True,
                    "color1": colormap["bullet_color"],
                    "color2": colormap["scene_color"],
                    "font": font_to_use,
                    "element": element,
                }
            )

        elif "Action:" in element:
            if (
                "Action: ..." in element
            ):  # If this is continued from the previous line, indicate so and ensure proper font
                if element[11:] == "":
                    return ""
                tmp = action_evaluate.cleanup_the_result(
                    element.replace("Action: ...", "&nbsp;&nbsp;continued >>> ")
                )
                element = tmp
            return f'<li style=color:{colormap["bullet_color"]}>{element}</span></li>\n'
        elif "TaskerNet " in element:  # TaskerNet
            return f"{element}\n"
        else:  # Must be additional item
            return f"<li {element}" + "</span></li>\n"

    # #############################################################################################
    # Generate the output string based on the input XML <code> passed in
    # Returns a formatted string for output based on the input codes
    # #############################################################################################
    def format_line(self, primary_items: dict, element: str, lvl: int) -> str:
        """
        Start formatting the output line with appropriate HTML
                :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
                :param element: the text line being formatted
                :param lvl: the hierarchical list level for output- 0=heading, 1=start list, 2= list item, 3= end list, 4= plain text
                :return: modified output line
        """
        # list lvl: 0=heading 1=start list 2=Task/Profile/Scene 3=end list 4=special Task
        string = ""

        # Look at level and set up accordingly: 0=str and break, 1=start list, 2=list item, 3= end list, 4=heading, 5=simple string
        match lvl:
            case 0:
                string = f"{element}" + "<br>\n"
            case 1:  # lvl=1 >>> Start list
                string = f"<ul>{element}" + "\n"
            case 2:  # lvl=2 >>> List item
                string = self.format_line_list_item(
                    primary_items,
                    element,
                    primary_items["colors_to_use"],
                    primary_items["program_arguments"]["font_to_use"],
                )
                # If we are doing twisty and this is a Scene, then we need to add an extra <ul>
                if primary_items["program_arguments"]["twisty"] and "Scene:" in string:
                    string = f"<ul>{string}"
            case 3:  # lvl=3 >>> End list
                string = "</ul>"
            case 4:  # lvl=4 >>> Heading or plain text line
                string = f"{element}<br>\n"
            case 5:  # lvl=5 >>> Plain text line
                string = element + "\n"
        return string

    # #############################################################################################
    # Write line of output
    # #############################################################################################
    def add_line_to_output(
        self,
        primary_items: dict,
        list_level: int,
        out_string: str,
    ) -> None:
        """
        Add line to the list of output lines.  The output entry is based on the list_level and the contents of the output_str
            :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
            :param list_level: level we are outputting
            :param out_string: the string to add to the output
            :return: none
        """

        if (
            "Task ID:" in out_string
            and primary_items["program_arguments"]["debug"] is False
        ):  # Drop ID: nnn since we don't need it anymore
            temp_element = out_string.split("Task ID:")
            out_string = temp_element[0]

        # Go configure the output based on the contents of the element and the list level
        self.output_lines.append(
            self.format_line(
                primary_items,
                out_string,
                list_level,
            )
        )
        # Log the generated output if in special debug mode
        if debug_out:
            debug_msg = f"out_string: {self.output_lines[-1]}"
            logger.debug(debug_msg)
        return
