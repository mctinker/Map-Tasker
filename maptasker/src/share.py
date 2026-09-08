"""Handle TaskerNet "Share" information"""

#! /usr/bin/env python3

#                                                                                      #
# share: process TaskerNet "Share" information                                         #
#                                                                                      #
import defusedxml.ElementTree  # Need for type hints

from maptasker.src.format import format_html, format_label
from maptasker.src.mapjump import TASKERNET_PART, Target, anchor_html
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import FormatLine


# Go through xml <Share> elements to grab and output TaskerNet description and
# search-on lines.
def share(
    root_element: defusedxml.ElementTree,
    tab: str,
    where: Target | None = None,
) -> None:
    """
    Go through xml <Share> elements to grab and output TaskerNet description and search-on lines
        :param root_element: beginning xml element (e.g. Project or Task)
        :param tab: "projtab", "proftab" or "tasktab"
        :param where: the object this <Share> belongs to, so its description can be marked
            as somewhere a report finding can jump to.  None leaves it unmarked, which is
            what a caller that has no Target for the object gets.
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
                where,
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
    where: Target | None = None,
) -> None:
    """
    We have a Taskernet description (<Share>).  Clean it up and add it to the output list.

        :param description_element: xml element <d> TaskerNet description.
        :param tab: CSS tab class name to apply to the color HTML.
        :param where: the object this description belongs to, or None not to mark it.
    """
    # Mark the description's place, so a finding about what is written IN it -- the secrets
    # scan reports the email addresses people leave in these -- lands on the description
    # rather than on the object's own line, which can be a screenful above it.  Its own
    # output line rather than the front of the description, for the reason projects.py
    # gives: the description is styled from end to end and an anchor inside it would be
    # styled with it.
    if where is not None and (anchor := anchor_html(where.at_part(TASKERNET_PART))):
        PrimeItems.output_lines.add_line_to_output(5, anchor, FormatLine.dont_format_line)

    # Format the description as if it is a label with embedded html/
    out_string = (
        format_label(f"<h6>TaskerNet description: {description_element.text}")
        .replace("action_label_color", "taskernet_color")
        .replace(" ...with label:", "")
        .replace("\n", "<br>")
    )

    # Add the tab CSS call to the color.
    out_string = PrimeItems.output_lines.add_tab(tab, out_string)

    # Output the description line.
    PrimeItems.output_lines.add_line_to_output(
        2,
        f"{out_string}",
        FormatLine.dont_format_line,
    )
