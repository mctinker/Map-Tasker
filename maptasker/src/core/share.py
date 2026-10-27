"""Handle TaskerNet "Share" information"""

#! /usr/bin/env python3

#                                                                                      #
# share: process TaskerNet "Share" information                                         #
#                                                                                      #

from collections.abc import Mapping
from xml.etree.ElementTree import Element

from maptasker.src.core.format import format_html
from maptasker.src.core.htmllabel import format_label
from maptasker.src.core.mapjump import TASKERNET_PART, Target, anchor_html
from maptasker.src.core.primitem import RunState
from maptasker.src.core.runcfg import RunConfig
from maptasker.src.core.sysconst import FormatLine


# Go through xml <Share> elements to grab and output TaskerNet description and
# search-on lines.
def share(root_element: Element, tab: str, where: Target | None = None, *, config: RunConfig, state: RunState) -> None:
    """
    Go through xml <Share> elements to grab and output TaskerNet description and search-on lines
        :param root_element: beginning xml element (e.g. Project or Task)
        :param tab: "projtab", "proftab" or "tasktab"
        :param where: the object this <Share> belongs to, so its description can be marked
            as somewhere a report finding can jump to.  None leaves it unmarked, which is
            what a caller that has no Target for the object gets.
        :param config: the run's settings (the colors the description is drawn in)
    """
    # Get the <share> element, if any
    share_element: Element | None = root_element.find("Share")
    if share_element is not None:
        #  We have a <Share> .  Find the description
        description_element = share_element.find("d")
        # Process the description
        if description_element is not None:
            description_element_output(description_element, tab, where, state=state, config=config)

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
            out_string = state.output_lines.add_tab(tab, out_string)
            state.output_lines.add_line_to_output(
                2,
                f"<br>{out_string}<br>",
                FormatLine.dont_format_line,
            )

        # Force a break when done with last Share element, only if there isn't one there already.
        break_html = "" if state.output_lines.output_lines[-1] == "<br>" else "<br>"
        state.output_lines.add_line_to_output(
            0,
            f"{break_html}",
            FormatLine.dont_format_line,
        )

        # Now get rid of the last duplicate <br> lines at the bottom of the output.  Walked
        # back by position: the loop stops at the first thing it recognises, usually within
        # a few lines of the end, so a copy of every line of the output so far -- which is
        # what enumerating a list of it made, on every call -- is a cost that grows with the Map.
        lines = state.output_lines.output_lines
        for num in range(len(lines) - 1, -1, -1):
            item = lines[num]
            if "TaskerNet description:" in item:
                break
            if item == "<br>" and state.output_lines.output_lines[num - 1] == "<br>":
                # By position: remove() takes a value, and `num` is an index, so this raised ValueError.
                del state.output_lines.output_lines[num]
                break
            if tab != "proftab" and item.endswith("<br><br>"):
                state.output_lines.output_lines[-1] = item.replace(
                    "<br><br>",
                    "<br>",
                )
                break


# ################################################################################
# Process the description <d> element
# ################################################################################
def description_html(text: str | None, colors: Mapping[str, str]) -> str:
    """One TaskerNet description as the Map draws it: formatted as if it were a label with embedded html.

    A function of its own so that what the TaskerNet Description editor previews is made by
    the very code that makes what the Map shows, and cannot drift from it.
    """
    return (
        format_label(f"<h6>TaskerNet description: {text}", colors=colors)
        .replace("action_label_color", "taskernet_color")
        .replace(" ...with label:", "")
        .replace("\n", "<br>")
    )


def description_element_output(
    description_element: Element, tab: str, where: Target | None = None, *, config: RunConfig, state: RunState
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
    if where is not None and (anchor := anchor_html(where.at_part(TASKERNET_PART), state=state)):
        state.output_lines.add_line_to_output(5, anchor, FormatLine.dont_format_line)

    # Add the tab CSS call to the color.
    out_string = state.output_lines.add_tab(tab, description_html(description_element.text, config.colors))

    # Output the description line.
    state.output_lines.add_line_to_output(
        2,
        f"{out_string}",
        FormatLine.dont_format_line,
    )
