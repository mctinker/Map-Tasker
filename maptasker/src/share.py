"""Handle TaskerNet "Share" information"""

#! /usr/bin/env python3

#                                                                                      #
# share: process TaskerNet "Share" information                                         #
#                                                                                      #
import defusedxml.ElementTree  # Need for type hints

from maptasker.src.format import format_html
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import FormatLine


# Go through xml <Share> elements to grab and output TaskerNet description and
# search-on lines.
def share(
    root_element: defusedxml.ElementTree,
    tab: str,
) -> None:
    """
    Go through xml <Share> elements to grab and output TaskerNet description and search-on lines
        :param root_element: beginning xml element (e.g. Project or Task)
        :param tab: "projtab", "proftab" or "tasktab"
    """
    # Get the <share> element, if any
    share_element: defusedxml.ElementTree = root_element.find("Share")
    if share_element is not None:
        #  We have a <Share> .  Find the description
        description_element = share_element.find("d")
        # Process the description
        if description_element is not None:
            description_element_output(
                description_element,
                tab,
            )

        # Look for TaskerNet search parameters
        search_element = share_element.find("g")
        if search_element is not None and search_element.text:
            # Found search...format and output
            out_string = format_html(
                "taskernet_color",
                "",
                f"\n<br>TaskerNet search on: {search_element.text}\n<br>",
                True,
            )
            # Add the tab CSS call to the color.
            out_string = PrimeItems.output_lines.add_tab(tab, out_string)
            PrimeItems.output_lines.add_line_to_output(
                2,
                f"<br>{out_string}<br>",
                FormatLine.dont_format_line,
            )

        # Force a break when done with last Share element, only if there isn't one there already.
        break_html = "" if PrimeItems.output_lines.output_lines[-1] == "<br>" else "<br>"
        PrimeItems.output_lines.add_line_to_output(
            0,
            f"{break_html}",
            FormatLine.dont_format_line,
        )

        # Now get rid of the last duplicate <br> lines at the bottom of the output.
        for num, item in reversed(
            list(enumerate(PrimeItems.output_lines.output_lines)),
        ):
            if "TaskerNet description:" in item:
                break
            if item == "<br>" and PrimeItems.output_lines.output_lines[num - 1] == "<br>":
                PrimeItems.output_lines.output_lines.remove(num)
                break
            if tab != "proftab" and item.endswith("<br><br>"):
                PrimeItems.output_lines.output_lines[-1] = item.replace(
                    "<br><br>",
                    "<br>",
                )
                break


# ################################################################################
# Process the description <d> element
# ################################################################################
def description_element_output(
    description_element: defusedxml.ElementTree,
    tab: str,
) -> None:
    """
    We have a Taskernet description (<Share>).  Clean it up and add it to the output list.

        :param description_element: xml element <d> TaskerNet description.
        :param tab: CSS tab class name to apply to the color HTML.
    """
    # We need to properly format this since it has embedded stuff that screws it up
    out_string = format_html(
        "taskernet_color",
        "",
        f"TaskerNet description: {description_element.text}",
        True,
    )

    # Replace all of the Taskernet imbedded HTML with our HTML.
    indent_html = f'<div <span class="{PrimeItems.colors_to_use["taskernet_color"]} {tab}"></span"></div>'

    # Indent the description and override various embedded HTML attributes
    out_string = out_string.replace("<p>", indent_html)
    out_string = out_string.replace("<P>", indent_html)
    out_string = out_string.replace("</p>", "")
    out_string = out_string.replace("</P>", "")
    out_string = out_string.replace("<b>", "")
    out_string = out_string.replace("<br>", indent_html)
    out_string = out_string.replace("<h1>", indent_html)
    out_string = out_string.replace("\r", indent_html)
    out_string = out_string.replace("<li>", indent_html)
    out_string = out_string.replace("</li>", "")
    out_string = out_string.replace("<strong>", "")
    out_string = out_string.replace("\n\n", "<br><br>")  # N
    out_string = out_string.replace("\n", "<br>")  # New line break.
    out_string = out_string.replace("  ", "<br>")  # Break after two blanks.
    out_string = out_string.replace("- ", "<br>")  # Break after dash blank.

    out_string = out_string.replace(
        "<table>",
        (
            "\n<style>\n.myTable2 {\n color:"
            + PrimeItems.colors_to_use["taskernet_color"]
            + ';}\n</style>\n<table class="myTable2 {tab}">'
        ),
    )

    # Add the tab CSS call to the color.
    out_string = PrimeItems.output_lines.add_tab(tab, out_string)

    # Output the description line.
    PrimeItems.output_lines.add_line_to_output(
        2,
        f"{out_string}",
        FormatLine.dont_format_line,
    )
