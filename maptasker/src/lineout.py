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
from maptasker.src.dirout import add_directory_item
from maptasker.src.format import format_html
from maptasker.src.frontmtr import output_the_front_matter
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import UNKNOWN_TASK_NAME, FormatLine, debug_out, logger
from maptasker.src.xmldata import remove_html_tags


# ##################################################################################
# Class definition for our output lines
# ##################################################################################
class LineOut:
    """Class definition for our output lines"""

    def __init__(self) -> None:  # noqa: ANN101
        """
        Initialize an object
        Args:
            self: The object being initialized
        Returns:
            None: Nothing is returned
        - Initialize an empty list to store output lines
        - The list will be used to store lines of text as the object is used"""
        self.output_lines = []

    def refresh_our_output(
        self,  # noqa: ANN101
        include_the_profile: bool,
        project_name: str,
        profile_name: str,
    ) -> None:
        """
        For whatever reason, we need to clear out the existing output and start anew.

                :param include_the_profile: Boolean flag to indicate whether this is
                    a Profile to be included
                :param project_name: name of the Project, if any
                :param profile_name: name of the Profile, if any
                :return: nothing
        """

        # Clear whatever is already in the output queue
        self.output_lines.clear()
        PrimeItems.directory_items = {
            "current_item": "",
            "projects": [],
            "profiles": [],
            "tasks": [],
            "scenes": [],
        }

        PrimeItems.scene_countgrand_totals = {
            "projects": 0,
            "profiles": 0,
            "unnamed_tasks": 0,
            "named_tasks": 0,
            "scenes": 0,
        }

        PrimeItems.grand_totals = {
            "projects": 0,
            "profiles": 0,
            "unnamed_tasks": 0,
            "named_tasks": 0,
            "scenes": 0,
        }

        # Display th starting information in beginning of output
        output_the_front_matter()

        # Re-add the directory item
        if PrimeItems.program_arguments["directory"]:
            add_directory_item("projects", project_name)

        # Start Project list
        self.add_line_to_output(
            2,
            f"Project: {project_name}",
            ["", "project_color", FormatLine.add_end_span],
        )

        # Are we to include the Profile?
        if include_the_profile:
            # Start Profile list
            self.add_line_to_output(1, "", FormatLine.dont_format_line)
            self.add_line_to_output(
                2,
                f"Profile: {profile_name}",
                ["", "profile_color", FormatLine.add_end_span],
            )
            # Start Project list
            self.add_line_to_output(1, "", FormatLine.dont_format_line)

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
    def add_style(self, style_details: dict) -> str:
        """
        Add appropriate HTML style tags based on parameters in dictionary passed in
            :param style_details: True if we are to output a list (<li>), False if not
            :return: updated output line with style details added
        """

        line_with_style = ""
        if style_details["is_list"]:
            line_with_style = f'<li "<span class="{style_details["color"]}">{style_details["element"]}</span></li>\n'

        elif style_details["is_taskernet"]:
            line_with_style = f'<p class="{style_details["color"]}{style_details["element"]}</p>\n'
            line_with_style = line_with_style.replace("<span></span>", "")

        return line_with_style

    # ##################################################################################
    # Given a text string to output, format it based on it's contents:
    #   Project/Profile/Task/Actrion/Scene
    # ##################################################################################
    def format_line_list_item(self, element: str) -> str:  # noqa: ANN101
        """
        Generate the output list (<li>) string based on the input XML <code> passed in

        :param element: text string to be added to output
        :return: the formatted text to add to the output queue
        """

        font = PrimeItems.program_arguments["font"]
        if "Project:" in element or "Project has no Profiles" in element:
            return self.handle_project(element)

        if "Profile:" in element:
            return self.handle_profile(element)

        if element.startswith("Task:") or "&#45;&#45;Task:" in element:
            return self.handle_task(element, font)

        if element.startswith("Scene:"):
            return self.handle_scene(element, font)

        if "Action:" in element:
            return self.handle_action(element)

        if "TaskerNet " in element:
            return self.handle_taskernet(element)

        # Must be additional item
        return self.handle_additional(element)

    # ##################################################################################
    # Insert the hyperlink target if doing a the directory
    # ##################################################################################
    def handle_project(self, element: str) -> str:  # noqa: ANN101
        """
        Insert the hyperlink target if doing a the directory
                Args:

                    element (str): text to incorporate after the target

                Returns:
                    _type_: output text with hyperlink target embedded
        """
        return self.add_directory_link("<li ", element, "</li>\n")

    def handle_profile(self, element: str) -> None:  # noqa: ANN101
        """Handles profile element by adding directory link
        Args:
            element: Profile element to handle
        Returns:
            str: Formatted profile element with directory link
        - Adds opening and closing tags for list item
        - Calls method to add directory link
        - Returns formatted string"""
        return self.add_directory_link("<br><li ", element, "</span></li>\n")

    # ##################################################################################
    #  Adds a directory link to the provided string.
    # ##################################################################################
    def add_directory_link(self, arg1: str, element: str, arg3: str) -> str:  # noqa: ANN101
        """
        Adds a directory link to the provided string.
        Args:
            self: The class instance
            arg1: First part of the string
            element: Middle part of the string
            arg3: Last part of the string
        Returns:
            String: The full string with directory link added if applicable
        Processes the function:
            - Checks if a directory is specified in arguments
            - Gets the current directory item if set
            - Generates the directory link HTML
            - Concatenates all parts and returns the full string
        """
        directory = ""

        if PrimeItems.program_arguments["directory"] and PrimeItems.directory_items["current_item"]:
            directory_item = f'"{PrimeItems.directory_items["current_item"]}"'
            directory = f"<a id={directory_item}></a>\n"
        return f"{directory}{arg1}{element}{arg3}"

    def handle_task(self, element: str, font: str) -> str:  # noqa: ANN101
        """Handle styling for a task element
        Args:
            element: Element name in one line
            font: Font name in one line
        Returns:
            style_details: Styled element details in one line
        Processing Logic:
            - Check if element name contains UNKNOWN_TASK_NAME
            - Set color to "unknown_task_color" if true else "task_color"
            - Add font and element details to style
            - Return styled element from add_style method"""
        style_details = {
            "is_list": True,
            "font": font,
            "element": element,
            "color": ("unknown_task_color" if UNKNOWN_TASK_NAME in element else "task_color"),
        }
        return self.add_style(style_details)

    def handle_scene(self, element, font):
        directory = ""
        if PrimeItems.program_arguments["directory"] and PrimeItems.directory_items["current_item"]:
            scene_name = f'scenes_{element.split("Scene:&nbsp;")[1]}'
            # Get rid of any name attributions
            if (
                PrimeItems.program_arguments["bold"]
                or PrimeItems.program_arguments["italicize"]
                or PrimeItems.program_arguments["highlight"]
                or PrimeItems.program_arguments["underline"]
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
        return f"{directory}{self.add_style(style_details)}"

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

    def handle_action(self, element) -> str:
        r"""
        Handles the action element.

        Args:
            element: The action element to be handled.

        Returns:
            The formatted HTML list item element.

        Examples:
            >>> handle_action(self, "Action: ...indent=2item=Attribute")
            '<li ...">continued >>> Attribute</span></li>\n'
        """

        blanks = f'{"&nbsp;"*PrimeItems.program_arguments["indent"]}&nbsp;&nbsp;&nbsp;'
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
            tmp = start1[0].replace("Action: ...", f"{indentation}continued >>> {start2[1]}")
            # tmp = action_evaluate.cleanup_the_result(
            #     start1[0].replace(
            #         "Action: ...", f"{indentation}continued >>> {start2[1]}"
            #     )
            # )
            element = tmp

        return f"<li {element}</span></li>\n"

    def handle_taskernet(self, element):
        return f"{element}\n"

    def handle_additional(self, element):
        return f"<li {element}" + "</span></li>\n"

    def end_unordered_list(self):
        if PrimeItems.unordered_list_count > 0:
            PrimeItems.unordered_list_count -= 1
        return "</ul>" if PrimeItems.unordered_list_count >= 0 else ""

    def delete_last_line(self):
        # self.my_traceback("3", f"delete last element:{self.output_lines[-1]}")
        if PrimeItems.unordered_list_count > 0:
            if self.output_lines[-1] == "</ul>":
                PrimeItems.unordered_list_count += 1
            else:
                PrimeItems.unordered_list_count -= 1
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
    def format_line_out(self, element: str, lvl: int) -> str:
        """
        Start formatting the output line with appropriate HTML
                :param element: the text line being formatted
                :param lvl: the hierarchical list level for output- 0=heading,
                    1=start list, 2= list item, 3= end list, 4= plain text
                :return: modified output line

        """

        if lvl == 0:
            # Heading / break
            return f"{element}<br>"

        if lvl == 1:
            # Start list
            return f"<ul>{element}\n"

        if lvl == 2:
            # List item
            if PrimeItems.program_arguments["twisty"] and "Scene:" in element:
                return f"<ul>{self.format_line_list_item(element)}"
            return self.format_line_list_item(element)

        if lvl == 3:
            # End list
            return PrimeItems.output_lines.end_unordered_list()

        if lvl == 5:
            # Plain text
            return f"{element}\n"

    # ##################################################################################
    # Write line of output
    # ##################################################################################
    def add_line_to_output(
        self,
        list_level: int,
        out_string: str,
        format_line: list,
    ) -> None:
        """
        Add line to the list of output lines.  The output entry is based on the
        list_level and the contents of the output_str
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
                format_line[1],
                format_line[0],
                out_string,
                format_line[2],
            )

        # Drop ID: nnn since we don't need it anymore
        if "Task ID:" in out_string and PrimeItems.program_arguments["debug"] is False:
            temp_element = out_string.split("Task ID:")
            out_string = temp_element[0]

        # Go configure the output based on the contents of the element and the
        #   list level. Call format_line before appending it.
        self.output_lines.append(
            self.format_line_out(
                out_string,
                list_level,
            )
        )
        # Log the generated output if in special debug mode
        if debug_out:
            debug_msg = f"out_string: {self.output_lines[-1]}"
            logger.debug(debug_msg)
        return
