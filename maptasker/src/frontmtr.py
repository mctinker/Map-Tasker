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

from maptasker.src.addcss import add_css
from maptasker.src.debug import display_debug_info
from maptasker.src.format import format_html
from maptasker.src.prefers import get_preferences
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import MY_VERSION, NORMAL_TAB, NOW_TIME, FormatLine


# ##################################################################################
# Add the heading matter to the output: heading, source, screen size, etc.
# ##################################################################################
def output_the_heading() -> None:
    """
    Display the heading and source file details
    """
    window_dimensions = """
<p id="mywin"></p>

<script>
var w = window.innerWidth;
var h = window.innerHeight;

var x = document.getElementById("mywin");
# x.innerHTML = "Browser width: " + w + ", height: " + h + ".";
</script>"""

    # Start out by outputting our colors and font CSS
    add_css()

    tasker_mapping = "Tasker Mapping................ Tasker version:"

    # Get the screen dimensions from <dmetric> xml
    screen_element = PrimeItems.xml_root.find("dmetric")
    screen_size = (
        f'&nbsp;&nbsp;Device screen size: {screen_element.text.replace(",", " X ")}'
        if screen_element is not None
        else ""
    )

    # Set up highlight background color if needed
    if PrimeItems.program_arguments["highlight"]:
        background_color_html = (
            "<style>\nmark { \nbackground-color: " + PrimeItems.colors_to_use["highlight_color"] + ";\n}\n</style>\n"
        )
    else:
        background_color_html = ""

    # Output date and time if in debug mode
    if PrimeItems.program_arguments["debug"]:
        now_for_output = NOW_TIME.strftime("%m/%d/%y %H:%M:%S")
    else:
        now_for_output = ""

    # Format the output heading
    heading_color = "heading_color"
    PrimeItems.heading = (
        f'<!doctype html>\n<html lang=”en”>\n<head>\n<meta charset="UTF-8">{background_color_html}<title>MapTasker</title>\n<body'
        f" style=\"background-color:{PrimeItems.colors_to_use['background_color']}\">\n"
        + format_html(
            heading_color,
            "",
            (
                f"<h2>{NORMAL_TAB}MapTasker</h2><br>{NORMAL_TAB}{tasker_mapping}"
                f" {PrimeItems.xml_root.attrib['tv']}&nbsp;&nbsp;&nbsp;&nbsp;"
                f"{MY_VERSION}{screen_size}&nbsp;&nbsp;&nbsp;&nbsp;{now_for_output}"
            ),
            True,
        )
    )

    # Add script to get window dimensions
    PrimeItems.output_lines.add_line_to_output(
        0,
        window_dimensions,
        FormatLine.dont_format_line,
    )

    # Add a blank line
    PrimeItems.output_lines.add_line_to_output(
        0,
        PrimeItems.heading,
        FormatLine.dont_format_line,
    )

    # Display where the source file came from
    # Did we restore the backup from Android?
    if PrimeItems.program_arguments["fetched_backup_from_android"]:
        source_file = (
            "From Android device"
            f' TCP IP address:{PrimeItems.program_arguments["android_ipaddr"]}'
            f' on port:{PrimeItems.program_arguments["android_port"]}'
            f' with file location: {PrimeItems.program_arguments["android_file"]}'
        )
    elif PrimeItems.program_arguments["debug"] or not PrimeItems.program_arguments["file"]:
        filename = isinstance(PrimeItems.file_to_get, str)
        filename = PrimeItems.file_to_get.name if not filename else PrimeItems.file_to_get
        source_file = filename
    else:
        source_file = PrimeItems.program_arguments["file"]
    # Add source to output
    PrimeItems.output_lines.add_line_to_output(
        0,
        f"<br><br>Source backup file: {source_file}",
        ["", "heading_color", FormatLine.add_end_span],
    )


# ##################################################################################
# Output the heading etc. as the front matter.
# ##################################################################################
def output_the_front_matter() -> None:
    """
    Generates the front matter for the output file: heading, runtime settings,
    directory, Tasker preferences.
    """

    # Heading information
    output_the_heading()

    # If we are debugging, output the runtime arguments and colors
    if PrimeItems.program_arguments["debug"] or PrimeItems.program_arguments["runtime"]:
        display_debug_info()

    # Output a flag to indicate this is where the directory goes
    PrimeItems.output_lines.add_line_to_output(5, "maptasker_directory", FormatLine.dont_format_line)

    # If doing Tasker preferences, get them
    if PrimeItems.program_arguments["preferences"]:
        get_preferences()
