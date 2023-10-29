# #################################################################################### #
#                                                                                      #
# frontmtr - Output the front matter: heading, runtime settings, directory, prefs      #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
from datetime import datetime

from maptasker.src.addcss import add_css
from maptasker.src.debug import display_debug_info
from maptasker.src.format import format_html
from maptasker.src.prefers import get_preferences
from maptasker.src.sysconst import MY_VERSION, FormatLine


# ##################################################################################
# Add the heading matter to the output: heading, source, screen size, etc.
# ##################################################################################
def output_the_heading(primary_items: dict) -> None:
    """
    Display the heading and source file details
        :param primary_items:  Program registry.  See primitem.py for details.
    """

    # Start out by outputting our colors and font CSS
    add_css(primary_items)

    tasker_mapping = "Tasker Mapping................ Tasker version:"

    # Get the screen dimensions from <dmetric> xml
    screen_element = primary_items["xml_root"].find("dmetric")
    screen_size = (
        f'&nbsp;&nbsp;Device screen size: {screen_element.text.replace(",", " X ")}'
        if screen_element is not None
        else ""
    )

    # Set up highlight background color if needed
    if primary_items["program_arguments"]["highlight"]:
        background_color_html = (
            "<style>\nmark { \nbackground-color: "
            + primary_items["colors_to_use"]["highlight_color"]
            + ";\n}\n</style>\n"
        )
    else:
        background_color_html = ""

    # Output date and time if in debug mode
    if primary_items["program_arguments"]["debug"]:
        now = datetime.now()
        now_for_output = now.strftime("%m/%d/%y %H:%M:%S")
    else:
        now_for_output = ""

    # Format the output heading
    heading_color = "heading_color"
    primary_items["heading"] = (
        f"<!doctype html>\n<html lang=”en”>\n<head>\n{background_color_html}<title>MapTasker</title>\n<body"
        f" style=\"background-color:{primary_items['colors_to_use']['background_color']}\">\n"
        + format_html(
            heading_color,
            "",
            (
                f"<h2>MapTasker</h2><br> {tasker_mapping}"
                f" {primary_items['xml_root'].attrib['tv']}&nbsp;&nbsp;&nbsp;&nbsp;"
                f"{MY_VERSION}{screen_size}&nbsp;&nbsp;&nbsp;&nbsp;{now_for_output}"
            ),
            True,
        )
    )

    primary_items["output_lines"].add_line_to_output(
        primary_items,
        0,
        primary_items["heading"],
        FormatLine.dont_format_line,
    )

    # Display where the source file came from
    # Did we restore the backup from Android?
    if primary_items["program_arguments"]["fetched_backup_from_android"]:
        source_file = (
            "From Android device"
            f' {primary_items["program_arguments"]["backup_file_http"]} at'
            f' {primary_items["program_arguments"]["backup_file_location"]}'
        )
    elif (
        primary_items["program_arguments"]["debug"]
        or not primary_items["program_arguments"]["file"]
    ):
        source_file = primary_items["file_to_get"].name
    else:
        source_file = primary_items["program_arguments"]["file"]
    # Add source to output
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        0,
        f"<br><br>Source backup file: {source_file}",
        ["", "heading_color", FormatLine.add_end_span],
    )


# ##################################################################################
# Output the heading etc. as the front matter.
# ##################################################################################
def output_the_front_matter(primary_items: dict) -> None:
    """_summary_
    Generates the front matter for the output file: heading, runtime settings, directory, Tasker preferences
        Args:
            primary_items (dict): Program registry.  See primitem.py for details.
    """

    # Heading information
    output_the_heading(primary_items)

    # If we are debugging, output the runtime arguments and colors
    if (
        primary_items["program_arguments"]["debug"]
        or primary_items["program_arguments"]["runtime"]
    ):
        display_debug_info(primary_items)

    # Start a list (<ul>) to force everything to tab over
    # primary_items["unordered_list_count"] = 0
    primary_items["output_lines"].add_line_to_output(
        primary_items, 1, "", FormatLine.dont_format_line
    )

    # Output a flag to indicate this is where the directory goes
    primary_items["output_lines"].add_line_to_output(
        primary_items, 5, "maptasker_directory", FormatLine.dont_format_line
    )

    # If doing Tasker preferences, get them
    if primary_items["program_arguments"]["preferences"]:
        get_preferences(primary_items)
