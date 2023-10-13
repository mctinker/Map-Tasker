#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# lineout: format the output for a line and adding it to an output queue (List)        #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
"""_summary_
The LineOut class is responsible for generating the output lines that will be displayed 
to the user.

It has a method called refresh_our_output() that clears any existing output and 
generates new output starting with the heading, project name, and optionally the 
profile name if passed in.

The add_style() method takes in a dictionary of styling details and returns a string 
with the appropriate HTML styling applied. This is used to add colors, fonts, etc.

The format_line_list_item() method takes an element string and formats it with styling 
based on whether it is a Project, Profile, Task, Action, etc. It calls specific handler 
methods like handle_project(), handle_profile(), etc. to generate the properly formatted
output line.

So in summary, LineOut handles generating and formatting each line of output with 
styling and structure based on the type of element being displayed. The output lines 
are accumulated and ultimately used to generate the final HTML output file.
"""
import maptasker.src.actione as action_evaluate
from maptasker.src.format import format_html
from maptasker.src.frontmtr import output_the_front_matter
from maptasker.src.sysconst import UNKNOWN_TASK_NAME, FormatLine, debug_out, logger
from maptasker.src.xmldata import remove_html_tags


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
                :param primary_items:  Program registry.  See primitem.py for details.
                :param include_the_profile: Boolean flag to indicate whether this is
                    a Profile to be included
                :param project_name: name of the Project, if any
                :param profile_name: name of the Profile, if any
                :return: nothing
        """

        # Clear whatever is already in the output queue
        self.output_lines.clear()
        primary_items["dirctory_items"] = (
            {
                "current_item": "",
                "projects": [],
                "profiles": [],
                "tasks": [],
                "scenes": [],
            },
        )
        primary_items["grand_totals"] = {
            "projects": 0,
            "profiles": 0,
            "unnamed_tasks": 0,
            "named_tasks": 0,
            "scenes": 0,
        }

        # Display th starting information in beginning of output
        output_the_front_matter(primary_items)

        # Start Project list
        self.add_line_to_output(
            primary_items,
            2,
            f"Project: {project_name}",
            ["", "project_color", FormatLine.add_end_span],
        )

        # Are we to include the Profile?
        if include_the_profile:
            # Start Profile list
            self.add_line_to_output(primary_items, 1, "", FormatLine.dont_format_line)
            self.add_line_to_output(
                primary_items,
                2,
                f"Profile: {profile_name}",
                ["", "profile_color", FormatLine.add_end_span],
            )
            # Start Project list
            self.add_line_to_output(primary_items, 1, "", FormatLine.dont_format_line)
        return

    # ##################################################################################
    # Generate an updated output line with HTML style details
    # Input is a dictionary containing the requirements:
    #  color1 - color to user
    #  color2 - optional 2nd color to use
    #  color3 - optional third color to tack onto end of string
    #  is_list - boolean: True= is a list HTML element
    #  span - boolean: True= requires a <span> element
    #  font - font to use
    # ##################################################################################
    def add_style(self, primary_items, style_details: dict) -> str:
        """
        Add appropriate HTML style tags based on parameters in dictionary passed in
            :param style_details: True if we are to output a list (<li>), False if not
            :return: updated output line with style details added
        """

        line_with_style = ""
        if style_details["is_list"]:
            line_with_style = (
                f'<li "<span class="{style_details["color"]}">'
                f'{style_details["element"]}</span></li>\n'
            )

        elif style_details["is_taskernet"]:
            line_with_style = (
                f'<p class="{style_details["color"]}'
                f'{style_details["element"]}</p>\n'
            )
            line_with_style = line_with_style.replace("<span></span>", "")

        return line_with_style

    # ##################################################################################
    # Given a text string to output, format it based on it's contents:
    #   Project/Profile/Task/Actrion/Scene
    # ##################################################################################
    def format_line_list_item(self, primary_items: dict, element: str) -> str:
        """
        Generate the output list (<li>) string based on the input XML <code> passed in
        :param primary_items:  Program registry.  See primitem.py for details.
        :param element: text string to be added to output
        :return: the formatted text to add to the output queue
        """

        font = primary_items["program_arguments"]["font"]
        if "Project:" in element or "Project has no Profiles" in element:
            return self.handle_project(primary_items, element)

        elif "Profile:" in element:
            return self.handle_profile(primary_items, element)

        elif element.startswith("Task:") or "&#45;&#45;Task:" in element:
            return self.handle_task(primary_items, element, font)

        elif element.startswith("Scene:"):
            return self.handle_scene(primary_items, element, font)

        elif "Action:" in element:
            return self.handle_action(primary_items, element)

        elif "TaskerNet " in element:
            return self.handle_taskernet(element)

        else:  # Must be additional item
            return self.handle_additional(element)

    def handle_project(self, primary_items: dict, element: str):
        """_summary_
        Insert the hyperlink target if doing a the directory
                Args:
                    :param primary_items:  Program registry.  See primitem.py for details.
                    element (str): text to incorporate after the target

                Returns:
                    _type_: output text with hyperlink target embedded
        """
        return self.add_direcory_link(primary_items, "<li ", element, "</li>\n")

    def handle_profile(self, primary_items, element):
        return self.add_direcory_link(
            primary_items, "<br><li ", element, "</span></li>\n"
        )

    def add_direcory_link(self, primary_items, arg1, element, arg3):
        directory = ""
        if (
            primary_items["program_arguments"]["directory"]
            and primary_items["directory_items"]["current_item"]
        ):
            directory_item = f'"{primary_items["directory_items"]["current_item"]}"'
            directory = f"<a id={directory_item}></a>\n"
        return f"{directory}{arg1}{element}{arg3}"

    def handle_task(self, primary_items, element, font):
        style_details = {
            "is_list": True,
            "font": font,
            "element": element,
            "color": (
                "unknown_task_color" if UNKNOWN_TASK_NAME in element else "task_color"
            ),
        }
        return self.add_style(primary_items, style_details)

    def handle_scene(self, primary_items, element, font):
        directory = ""
        if (
            primary_items["program_arguments"]["directory"]
            and primary_items["directory_items"]["current_item"]
        ):
            scene_name = f'scenes_{element.split("Scene:&nbsp;")[1]}'
            # Get rid of any name attributions
            if (
                primary_items["program_arguments"]["bold"]
                or primary_items["program_arguments"]["italicize"]
                or primary_items["program_arguments"]["highlight"]
                or primary_items["program_arguments"]["underline"]
            ):
                scene_name = remove_html_tags(scene_name, "")
                # scene_name = self.remove_attributes(scene_name)
            directory = f'<a id="{scene_name.replace(" ","_")}"></a>\n'
        style_details = {
            "is_list": True,
            "color": "scene_color",
            "font": font,
            "element": element,
        }
        return f"{directory}{self.add_style(primary_items, style_details)}"

    # def remove_attributes(self, scene_name):
    #     scene_name = scene_name.replace("<em>", "")
    #     scene_name = scene_name.replace("</em>", "")
    #     scene_name = scene_name.replace("<b>", "")
    #     scene_name = scene_name.replace("</b>", "")
    #     scene_name = scene_name.replace("<mark>", "")
    #     scene_name = scene_name.replace("</mark>", "")
    #     scene_name = scene_name.replace("<u>", "")
    #     scene_name = scene_name.replace("</u>", "")
    #     return scene_name

    def handle_action(self, primary_items, element):
        blanks = (
            f'{"&nbsp;"*primary_items["program_arguments"]["indent"]}&nbsp;&nbsp;&nbsp;'
        )
        if "Action: ..." in element:
            if element[11:] == "":
                return ""
            # We have a continuation line: Action: ...indent=nitem=remaindertheline
            # Example:
            # '<span ...">Action: ...indent=2item=Attribute</span><span ...</span>>'
            start1 = element.split("indent=")
            start2 = start1[1].split("item=")
            # Force an indent of at least 1
            if start2[0] == "0":
                indentation = f'{"&nbsp;"*5}'
            else:
                indentation = f'{blanks*int(start2[0])}{"&nbsp;"*int(start2[0])}&nbsp;'
            # Add indentation for contination line
            tmp = action_evaluate.cleanup_the_result(
                start1[0].replace(
                    "Action: ...", f"{indentation}continued >>> {start2[1]}"
                )
            )
            element = tmp
        return f"<li {element}</span></li>\n"

    def handle_taskernet(self, element):
        return f"{element}\n"

    def handle_additional(self, element):
        return f"<li {element}" + "</span></li>\n"

    def end_unordered_list(self, primary_items):
        if primary_items["unordered_list_count"] > 0:
            primary_items["unordered_list_count"] -= 1
        return "</ul>" if primary_items["unordered_list_count"] >= 0 else ""

    def delete_last_line(self, primary_items):
        # self.my_traceback("3", f"delete last element:{self.output_lines[-1]}")
        if primary_items["unordered_list_count"] > 0:
            if self.output_lines[-1] == "</ul>":
                primary_items["unordered_list_count"] += 1
            else:
                primary_items["unordered_list_count"] -= 1
        self.output_lines[-1] = ""

    def my_traceback(self, key, element):
        import sys
        import traceback

        print(f"--------------------------- Traceback:{key}", file=sys.stderr)
        print(element, file=sys.stderr)
        traceback.print_stack()

    # ##################################################################################
    # Generate the output string based on the input XML <code> passed in
    # Returns a formatted string for output based on the input codes
    # ##################################################################################
    def format_line(self, primary_items: dict, element: str, lvl: int) -> str:
        """
        Start formatting the output line with appropriate HTML
                :param primary_items:  Program registry.  See primitem.py for details.
                :param element: the text line being formatted
                :param lvl: the hierarchical list level for output- 0=heading,
                    1=start list, 2= list item, 3= end list, 4= plain text
                :return: modified output line
        """
        # list lvl: 0=heading 1=start list 2=Task/Profile/Scene 3=end list
        #           4=special Task
        string = ""

        # Look at level and set up accordingly: 0=str and break, 1=start list,
        #   2=list item, 3= end list, 4=heading, 5=simple string
        match lvl:
            case 0:
                string = f"{element}<br>"
            case 1:  # lvl=1 >>> Start list
                # self.my_traceback(" <ul>", element)
                string = f"<ul>{element}\n"
                primary_items["unordered_list_count"] += 1
            case 2:  # lvl=2 >>> List item
                string = self.format_line_list_item(
                    primary_items,
                    element,
                )
                # If we are doing twisty and this is a Scene, then we need to add
                # an extra <ul>
                if primary_items["program_arguments"]["twisty"] and "Scene:" in string:
                    string = f"<ul>{string}"
                    primary_items["unordered_list_count"] += 1
            case 3:  # lvl=3 >>> End list
                # self.my_traceback(" </ul>", element)
                string = primary_items["output_lines"].end_unordered_list(primary_items)
            case 4:  # lvl=4 >>> Heading or plain text line
                string = f"{element}<br>"
            case 5:  # lvl=5 >>> Plain text line
                string = f"{element}\n"
        return string

    # ##################################################################################
    # Write line of output
    # ##################################################################################
    def add_line_to_output(
        self,
        primary_items: dict,
        list_level: int,
        out_string: str,
        format_line: list,
    ) -> None:
        """
        Add line to the list of output lines.  The output entry is based on the
        list_level and the contents of the output_str
            :param primary_items:  Program registry.  See primitem.py for details.
            :param list_level: level we are outputting
            :param out_string: the string to add to the output
            :param format_line: List if we need to first format the output line by
                adding HTML to it. Empty if we are not to first format the line.
                format_line[0] = text_before: The text to add before out_string.
                format_line[1] = color_to_use: The color to use if formatting line
                format_line[2] = add_span: Boolean to determine if a <span> tag
                    should be added if formatting the line.
            :return: none
        """

        # Format the output line by adding appropriate HTML.
        if format_line != FormatLine.dont_format_line:
            out_string = format_html(
                primary_items,
                format_line[1],
                format_line[0],
                out_string,
                format_line[2],
            )

        # Drop ID: nnn since we don't need it anymore
        if (
            "Task ID:" in out_string
            and primary_items["program_arguments"]["debug"] is False
        ):
            temp_element = out_string.split("Task ID:")
            out_string = temp_element[0]

        # Go configure the output based on the contents of the element and the
        #   list level. Call format_line before appending it.
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
