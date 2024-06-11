#! /usr/bin/env python3

#                                                                                      #
# lineout: format the output for a line and adding it to an output queue (List)        #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
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


# Class definition for our output lines
class LineOut:
    """Class definition for our output lines"""

    def __init__(self) -> None:
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
        self,
        include_the_profile: bool,
        project_name: str,
        profile_name: str,
    ) -> None:
        """self.add_line_to_output(
                2,
                f"Project: {project_name}",
                ["", "project_color", FormatLine.add_end_span],
            )
        Refreshes the output by clearing existing output and starting anew.
        Parameters:
            include_the_profile (bool): Flag to indicate whether this is a Profile to be included.
            project_name (str): Name of the Project, if any.
            profile_name (str): Name of the Profile, if any.
        Returns:
            - None: No return value.
        Processing Logic:
            - Clears existing output and starts anew.
            - Adds directory item.
            - Starts Project list.
            - Checks if Profile is to be included.
            - Starts Profile list.
            - Starts Project list."""
        """
        For whatever reason, we need to clear out the existing output and start anew.

                :param include_the_profile: Boolean flag to indicate whether this is
                    a Profile to be included
                :param project_name: name of the Project, if any
                :param profile_name: name of the Profile, if any
                :return: nothing
        """

        # Clear whatever is already in the output queue
        if PrimeItems.program_arguments["ai_analyze"]:
            PrimeItems.ai["output_lines"].clear()
        self.output_lines.clear()

        # Clear the directory
        PrimeItems.directory_items = {
            "current_item": "",
            "projects": [],
            "profiles": [],
            "tasks": [],
            "scenes": [],
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

        # Generate an updated output line with HTML style details

    # Input is a dictionary containing the requirements:
    #  color - color to user
    #  tab - CSS tab to use
    #  font - the m,onospace font to use
    #  element - the actual output line
    def add_style(self, style_details: dict) -> str:
        """
        Add appropriate HTML style tags based on parameters in dictionary passed in
            :param style_details: True if we are to output a list (<li>), False if not
            :return: updated output line with style details added
        """

        line_with_style = ""
        if style_details["tab"]:
            # Note: add <div> to force a divisional block so any text wraparound stays within the block of text.
            line_with_style = f'<div><span class="{style_details["color"]} {style_details["tab"]}">{style_details["element"]}</span></div>\n'

        elif style_details["is_taskernet"]:
            line_with_style = (
                f'<p class="{style_details["tab"]} {style_details["color"]}>{style_details["element"]}</p><br>\n'
            )
            line_with_style = line_with_style.replace("<span></span>", "")

        return line_with_style

    #  Adds a directory link to the provided string.
    def add_directory_link(self, arg1: str, element: str, arg3: str) -> str:
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

    # Find the color attribute/class and add the tab attribute to it.
    def add_tab(self, tab: str, element: str) -> str:
        r"""

        This function adds a tab before the substring "_color" in a given element string.

        Parameters:
        - tab (str): The tab to be added before the "_color" substring.
        - element (str): The element string in which the tab should be added before "_color".

        Returns:
        - str: The modified element string with the tab added before "_color".

        Processing Logic:
        - Find the position of the "_color" substring in the element string.
        - Insert a tab before the "_color" substring using string slicing and concatenation.
        - Return the modified element string.

        Examples:
        - Example usage of the function:

            # Calling the function with tab = "\t" and element = 'background_color:"red"'
            add_tab("\t", 'background_color:"red"')
            # Output: '\tbackground_color "red"'

        """
        color_pos = element.find('_color"')
        return f'{element[0:color_pos]}_color {tab}"{element[(color_pos+7):]}'

    # Given a text string to output, format it based on it's contents:
    #   Project/Profile/Task/Actrion/Scene
    def format_line_list_item(self, element: str) -> str:
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

        if element.startswith("Task:") or "&#45;&#45;Task:" in element or "Task: Properties" in element:
            return self.handle_task(element, font)

        if element.startswith("Scene:"):
            return self.handle_scene(element, font)

        if "Action:" in element:
            return self.handle_action(element)

        if "TaskerNet " in element:
            return self.handle_taskernet(element)

        # Must be additional item
        return self.handle_additional(element)

    # Insert the hyperlink target if doing a the directory
    def handle_project(self, element: str) -> str:
        """
        Insert the hyperlink target if doing a the directory
                Args:

                    element (str): text to incorporate after the target

                Returns:
                    _type_: output text with hyperlink target embedded
        """
        element = self.add_tab("projtab", element)
        return self.add_directory_link("<br>", element, "\n")

    # Handles profile element by adding directory link
    def handle_profile(self, element: str) -> None:
        """Handles profile element by adding directory link
        Args:
            element: Profile element to handle
        Returns:
            str: Formatted profile element with directory link
        - Adds opening and closing tags for list item
        - Calls method to add directory link
        - Returns formatted string"""
        element = self.add_tab("proftab", element)
        # Add the directory link to the Profile line.
        # Add <div </div> to ensure line wrap breaks at proftab (Profile spacing)
        return self.add_directory_link("<br><div ", element, "</div><br>\n")

    # Handle styling for a task element
    def handle_task(self, element: str, font: str) -> str:
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
            "tab": "tasktab",
            "font": font,
            "element": element,
            "color": ("unknown_task_color" if UNKNOWN_TASK_NAME in element else "task_color"),
        }

        # Note: add <div> to force a divisional block so any text wraparound stays within the block of text.
        return self.add_style(style_details)

    # Handle Scene
    def handle_scene(self, element: str, font: str) -> str:
        r"""
        This function handles a scene element by generating a string with HTML tags and style details. The function takes two parameters: element and font.

        Parameters:
        - element (str): The scene element that needs to be processed.
        - font (str): The font to use for the scene element.

        Returns:
        - str: The processed string with HTML tags and style details.

        Processing Logic:
        - If the program_arguments "directory" and the directory_items "current_item" are both true, the function extracts the scene name from the element and assigns it to the variable scene_name.
        - It then checks if any of the program_arguments "bold", "italicize", "highlight", or "underline" are true. If any of them are true, it calls the remove_html_tags() function to remove any name attributions from the scene name.
        - The function assigns an empty string to the variable directory if the program_arguments "directory" and the directory_items "current_item" are both false.
        - The function then creates a dictionary called style_details with details about the style of the scene element.
        - It finally returns a formatted string with the directory and the result of calling the add_style() function with the style_details dictionary.

        Examples:
        - Example usage of the function:
            handle_scene('Scene:&nbsp;1', 'Arial')
            # Returns: '<a id="scenes_1"></a>\n<style=color:scene_color;font:Arial;element:Scene:&nbsp;1;>'
        """
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

            directory = f'<a id="{scene_name.replace(" ","_")}"></a>\n'
        style_details = {
            "tab": "scenetab",
            "color": "scene_color",
            "font": font,
            "element": element,
        }

        # Note: add <div> to force a divisional block so any text wraparound stays within the block of text.
        return f"{directory}<br><div>{self.add_style(style_details)}</div>"

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

    # Handles the action element.
    def handle_action(self, element: str) -> str:
        """
        This function handles an action element by processing its contents and formatting it into HTML code.

        Parameters:
        - self: The object reference to the class instance.
        - element (str): The action element that needs to be processed.

        Returns:
        - str: The formatted HTML code for the action element.

        Processing Logic:
        - First, the function generates the necessary number of whitespace characters for indentation.
        - If the action element starts with "Action: ...", it checks for a continuation line.
        - If there is a continuation line, it splits the element into the indentation level and the remaining part of the line.
        - If the indentation level is 0, it sets an indentation of 5 spaces.
        - Otherwise, it sets the indentation based on the specified level.
        - It then replaces the "Action: ..." part of the line with the indentation and the continuation indicator.
        - Finally, it formats the element into HTML code by adding a class and line break.

        Examples:
        - Usage of the function:

            handler = ActionHandler()
            element = "Action: ...indent=2item=Attribute"
            formatted_element = handler.handle_action(element)
            print(formatted_element)

            Output:
            <span class="actiontab"></span><span class="indentation">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;continued >>> Attribute</span><br>
        """
        blank = "&nbsp;"
        # Is this a continuation line?
        if "Action: ..." in element:
            if element[11:] == "":  # This catches valid lines that have "Action: ..." in them
                return ""
            # We have a continuation line: Action: ...indent=nitem=remaindertheline
            # Example:
            # '<span ...">Action: ...indent=2item=Attribute</span><span ...</span>>'
            start1 = element.split("indent=")
            start2 = start1[1].split("item=")  # Indentation amount
            # Force an indent of at least 1
            indentation = f"{'&nbsp;' * 5}" if start2[0] == "0" else f"{blank * (int(start2[0]) + 8)}"
            # Add indentation for contination line
            tmp = start1[0].replace("Action: ...", f"{indentation}continued >>> {start2[1]}")

            element = tmp

        # Add action tab to existing class.
        element = self.add_tab("actiontab", element)

        # Note: add <div> to force a divisional block so any text wraparound stays within the block of text.
        return f"<div {element}</span></div><br>\n"

    # Handle taskernet
    def handle_taskernet(self, element: str) -> str:
        r"""
        This function handles a taskernet by appending a given element to a new line.

        Parameters:
        - element (str): The element to be added to the taskernet.

        Returns:
        - str: The taskernet with the given element appended to a new line.

        Processing Logic:
        - The function takes in a string representing an element.
        - It appends the element to a new line using the '\n' character.
        - The modified taskernet is then returned.

        Examples:
        - Example usage of the function:

            handle_taskernet("Task 1")
            Output: "Task 1\n"
            Explanation: The function appends the element "Task 1" to a new line and returns it as a taskernet.
        """
        return f"{element}\n"

    # Handle additional elements and return a formatted list item string.
    def handle_additional(self, element: str) -> str:
        """
        Handle additional elements and return a formatted list item string.

        Parameters:
            self: The instance of the class.
            element: The element to be added to the list item string.

        Returns:
            A formatted list item string with the provided element.
        """
        return element

        # Generate the output string based on the input XML <code> passed in

    # Returns a formatted string for output based on the input codes
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

            return f'<span class="normtab"></span>{element}<br>'

            # return f'<div <span class="normtab"></span>{element}</div><br>'

        if lvl == 1:
            # Start list
            return f"{element}\n"

        if lvl == 2:
            # List item
            if PrimeItems.program_arguments["twisty"] and "Scene:" in element:
                return f"{self.format_line_list_item(element)}"
            return self.format_line_list_item(element)

        if lvl == 3:
            # End list
            return ""

        if lvl == 5:
            # Plain text
            return f"{element}\n"
        return element

    # Write line of output
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
                format_line[1],  # Color code
                format_line[0],  # Text before.
                out_string,  # Text after.
                format_line[2],  # End span True or False
            )

        # Drop ID: nnn since we don't need it anymore
        if "Task ID:" in out_string and PrimeItems.program_arguments["debug"] is False:
            temp_element = out_string.split("Task ID:")
            out_string = temp_element[0]

        # Add to Ai prompt if we are doing an Ai run.  Maker sure to remove all HTML tags first.
        if PrimeItems.program_arguments["ai_analyze"]:
            # Format thew output line.
            # out_string = self.format_line_out(out_string, list_level)
            PrimeItems.ai["output_lines"].append(remove_html_tags(out_string, ""))

        # Go configure the output based on the contents of the element and the
        #   list level. Call format_line before appending it.
        self.output_lines.append(
            self.format_line_out(
                out_string,
                list_level,
            ),
        )

        # Log the generated output if in special debug mode
        if debug_out:
            debug_msg = f"out_string: {self.output_lines[-1]}"
            logger.debug(debug_msg)
