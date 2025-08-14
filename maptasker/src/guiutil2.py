#! /usr/bin/env python3
"""

 guiutil2: General and GUI utilities.

These are functions pulled out of maputils, guiwins and guiutils that would otherwise cause a circular
import error.

"""

import os
import re
import tkinter as tk
import uuid

import customtkinter as ctk
import requests

from maptasker.src.aiutils import get_api_key
from maptasker.src.error import rutroh_error
from maptasker.src.primitem import PrimeItems

# Define label fonts for headings: 0=h0, 1=h1, etc.
heading_fonts = {"0": "10", "1": "24", "2": "22", "3": "20", "4": "18", "5": "16", "6": "14"}


def validate_tkinter_geometry(geometry_string: str) -> bool:
    """
    Validates a tkinter window geometry string with additional constraints.

    Args:
        geometry_string (str): The geometry string in the format
                                 'width x height + position_x + position_y'.

    Returns:
        bool: True if the geometry string is valid and meets the constraints,
              False otherwise.
    """
    pattern = re.compile(r"^\d+x\d+\+\d+\+\d+$")
    if not pattern.match(geometry_string):
        return False

    try:
        parts = geometry_string.replace("+", " ").replace("x", " ").split()
        width = int(parts[0])
        height = int(parts[1])
        pos_x = int(parts[2])
        pos_y = int(parts[3])

        if width < 300:
            print("Error: Window width must be at least 300.")
            return False
        if height < 50:
            print("Error: Window height must be at least 50.")
            return False
        if pos_x < 0:
            print("Error: Window position X must be a non-negative number.")
            return False
        if pos_y < 0:
            print("Error: Window position Y must be a non-negative number.")
            return False

        return True  # noqa: TRY300
    except ValueError:
        print("Error: Invalid numeric value in geometry string.")
        return False


def configure_progress_bar(output_lines: list, title: str) -> tuple:
    """
    Configures and returns a progress bar for the GUI if the 'gui' argument is set in PrimeItems.program_arguments.

    Args:
        output_lines (list): The list of lines to process.
        titele (str): The title of the progress bar.

    Returns:
        progress (dict): The progress bar dictionary.
    """
    # Display a progress bar if coming from the GUI.
    if PrimeItems.program_arguments["gui"]:
        # Avoid a circular import error.  It's gotta be here.
        from maptasker.src.guiwins import ProgressbarWindow  # noqa: PLC0415

        # Make sure we have a geometry set for the progress bar
        if not PrimeItems.program_arguments["map_window_position"]:
            PrimeItems.program_arguments["map_window_position"] = "300x200+600+0"
        # Create a progress bar widget
        # The progress_bar will point to the ProgressbarWindow object, and progress_bar.progressbar will point to the
        # CTkProgressBar object
        progress_bar = ProgressbarWindow()
        progress_bar.title(f"{title} Progress")
        progress_bar.progressbar.set(0.0)
        progress_bar.progressbar.start()
        progress_bar.progressbar.focus_set()

        # Set the geometry of the progress bar
        if validate_tkinter_geometry(
            PrimeItems.program_arguments["progressbar_window_position"],
        ):
            progress_bar.geometry(
                PrimeItems.program_arguments["progressbar_window_position"],
            )

        else:
            PrimeItems.program_arguments["progressbar_window_position"] = "300x500+100+0"
        # Setup for our progress bar.  Use the total number of output lines as the metric.
        # 4 times since we go thru output lines 4 times in a majore way...
        # 1st: the Diagram, 2nd: delete_hanging_bars
        max_data = len(output_lines) * 8

        # Calculate the increment value for each 10% of progress (tenth_increment) based on the maximum value of the
        # progress bar (max_data). If the calculated increment is 0 (which would happen if max_data is less than 10),
        # it sets the increment to 1 to avoid division by zero issues.
        tenth_increment = max_data // 10
        if tenth_increment == 0:
            tenth_increment = 1

        # Save the info
        PrimeItems.progressbar = {
            "progress_bar": progress_bar,
            "tenth_increment": tenth_increment,
            "max_data": max_data,
            "progress_counter": 0,
            "self": None,
        }

        return PrimeItems.progressbar

    # Not the GUI.  Just return an almost empty dictionary.
    return {
        "progress_counter": 0,
    }


# Define the output file for the trace log
TRACE_LOG_FILE = "trace_log.txt"

# Function to clear the log file at the start (optional)
if os.path.exists(TRACE_LOG_FILE):
    os.remove(TRACE_LOG_FILE)


def my_trace_function(frame, event, arg) -> None:  # noqa: ANN001
    """
    Custom trace function that logs execution details.

    Invoked with:
    import sys
    from maptasker.src.guiutil2 import my_trace_function
    if PrimeItems.program_arguments["debug"]:
            PrimeItems.trace = True
            sys.settrace(my_trace_function)
    """
    # Only start logging if the 'start_tracing' flag is True
    if not PrimeItems.trace:
        return my_trace_function  # Keep the trace function active but don't log yet

    # Get relevant information from the frame
    co = frame.f_code
    filename = co.co_filename
    lineno = frame.f_lineno
    func_name = co.co_name

    # --- ADD THIS CHECK ---
    # Skip if the filename is not a regular file path (e.g., frozen modules, <string>, etc.)
    # Or if it refers to the trace function itself to avoid recursion
    if (
        not os.path.exists(filename)
        or not os.path.isfile(filename)
        or func_name == "my_trace_function"
        or filename == os.path.basename(__file__)
        or "<frozen" in filename
    ):  # Explicitly check for frozen modules
        return my_trace_function
    # --- END ADDITION ---

    log_message = ""
    if event == "line":
        # Get the line of code being executed
        try:
            with open(
                filename,
                encoding="utf-8",
            ) as f:  # Use the full filename here
                lines = f.readlines()
                current_line_code = lines[lineno - 1].strip() if 0 <= lineno - 1 < len(lines) else "<CODE NOT FOUND>"
        except (OSError, UnicodeDecodeError) as e:
            # Handle potential file access or decoding errors gracefully if they slip past the initial check
            current_line_code = f"<ERROR READING CODE: {e}>"
            # You might want to log this error to a separate debug log
            # print(f"Warning: Could not read source for {filename}:{lineno} - {e}", file=sys.stderr)

        log_message = f"LINE: {os.path.basename(filename)}:{lineno} {func_name}() - {current_line_code}"
    elif event == "call":
        log_message = f"CALL: {os.path.basename(filename)}:{lineno} Entering function: {func_name}()"
    elif event == "return":
        log_message = f"RETURN: {os.path.basename(filename)}:{lineno} Exiting function: {func_name}() (Returned: {arg})"
    elif event == "exception":
        exc_type, exc_value, _ = arg
        log_message = (
            f"EXCEPTION: {os.path.basename(filename)}:{lineno} {func_name}() - {exc_type.__name__}: {exc_value}"
        )

    if log_message:
        with open(TRACE_LOG_FILE, "a") as f:
            f.write(log_message + "\n")

    # Important: The trace function must return itself (or another trace function)
    # to continue tracing in the current or new scope.
    return my_trace_function


def is_valid_ai_config(self: ctk) -> bool:
    """
    Validates the AI model and API key against predefined configurations in PrimeItems.

    This method iterates through a list of known AI providers (e.g., OpenAI, Anthropic, Gemini)
    and checks if the instance's `self.ai_model` exists within any provider's model list.
    If a matching model is found, it further checks if the `self.ai_apikey` matches
    the corresponding API key stored in `PrimeItems.ai` for that provider.
    Some providers (like 'llama' in this example) may not require an API key check.

    The method prints a message indicating whether the AI model and API key combination
    is considered valid based on the configurations.

    Returns:
        bool: True if the `self.ai_model` and `self.ai_apikey` (if required)
              are valid according to `PrimeItems.ai` configurations; False otherwise.
    """
    # Dictionary mapping provider names to their models and key attributes in PrimeItems.ai
    # If 'llama_models' needs an API key, add 'llama_key' here.
    ai_providers = {
        "openai": {"models": "openai_models", "key": "openai_key"},
        "anthropic": {"models": "anthropic_models", "key": "anthropic_key"},
        "gemini": {"models": "gemini_models", "key": "gemini_key"},
        "deepseek": {"models": "deepseek_models", "key": "deepseek_key"},
        "llama": {"models": "llama_models", "key": None},  # Assuming no key for llama based on original if
    }
    if not self.ai_model:
        return False  # Don't do anything if there is no model to check against.

    # Make sure we have read in the api keys.
    if not self.ai_apikey or self.ai_apikey == "Hidden":
        self.ai_apikey = get_api_key()

    is_valid_config = False
    for provider, config in ai_providers.items():
        models = PrimeItems.ai.get(config["models"], [])
        key_to_check = PrimeItems.ai.get(config["key"], None)
        api_key = key_to_check if provider != "llama" and key_to_check == PrimeItems.ai[f"{provider}_key"] else None

        # If llama, then we need to strip " (Installed)" off the name.
        if provider == "llama":
            models = [item.replace(" (installed)", "") for item in models]

        if self.ai_model in models:
            if provider != "llama" and not api_key:
                # We have found the model but it doesn't have the api key.
                break
            if api_key is None or PrimeItems.ai[config["key"]] == api_key:  # No key check needed for this provider
                is_valid_config = True
                self.ai_apikey = api_key
                break
            break

    return is_valid_config


def get_changelog_file(url: str, delimiter: str, n: int) -> list:
    """
    Fetches a text file from a URL and returns a list of lines until the nth
    occurrence of a specified delimiter is encountered.

    Args:
        url (str): The URL of the text file.
        delimiter (str): The string to count occurrences of (e.g., "##").
        n (int): The nth occurrence of the delimiter to stop at.

    Returns:
        list: A list of text lines up to (but not including) the line
              where the nth occurrence of the delimiter is found.
              Returns an empty list if the URL is invalid or the delimiter
              is not found 'n' times.
    """
    if n <= 0:
        rutroh_error(f"Invalid integer value for n: {n!s}")
        return []

    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
    except requests.exceptions.RequestException as e:
        rutroh_error(f"Error fetching the URL: {e}")
        return []

    lines = []
    delimiter_count = 0

    # Decode the content and split into lines
    text_content = response.text
    for line in text_content.splitlines():
        if line.startswith(f"{delimiter} "):
            delimiter_count += 1
        if delimiter_count == n:
            break  # Stop when the nth occurrence is found
        lines.append(line)

    return lines


def draw_box_around_text(self: ctk, line_num: int, tags: list) -> tuple[int, list]:
    """Draws a box around text in a custom textbox widget.

    This function iterates through a set of text values, formats them,
    and inserts them into a textbox widget. It configures a tag for each
    piece of text to apply a specific font, foreground color, and background color,
    effectively creating a styled "box" around the text.

    Args:
        self: The instance of the custom textbox class (ctk).
        line_num: The starting line number where the text will be inserted.
        tags: A list of existing tags to ensure the generated tag ID is unique.

    Returns:
        The final line number and a list of all tags used thus far.
    """
    mygui = self.master.master
    all_values = self.draw_box["all_values"]
    line_num_str = str(line_num)
    begin_box = f"{line_num_str}.0"
    last_line = get_last_line(self.textview_textbox)
    max_tag_len = 0
    print("bingo", begin_box, last_line)

    # Get the background color
    bg_color = mygui.color_lookup["background_color"]
    if bg_color.isdigit():
        bg_color = "#" + bg_color

    # Go through all of the values in the label and output them
    for num, value in enumerate(all_values):
        # Get spacing only if this is first element.
        if num == 0:
            spacing = value["spacing"]
        char_position = 0

        # Iterate over a list or a string.
        for inner_num, message in enumerate(value["text"]):
            # Build the start and end indecies
            start_idx = str(line_num) + "." + str(char_position)
            end_idx = str(line_num) + "." + str(char_position + len(message))
            end_box = end_idx

            # Handle a new line.
            if message == "\n":
                self.textview_textbox.insert(start_idx, message)
                char_position = 0
                continue

            # Format the message
            formatted_message = (" " * value["spacing"]) + message if spacing > 0 else message

            # Add a newline to string if it begins with a %
            temp = message.lstrip()
            if temp.startswith("%"):
                message = message + "\n"  # noqa: PLW2901

            # # Create a tag with a border
            # tag_id = f"{start_idx}:{value['highlights'][num]}:{value['color'][num]}"
            # tags.append(tag_id)
            # max_tag_len = max(max_tag_len, len(tag_id))

            # # Get the html attributes
            # font_size = heading_fonts[tag_id.split(":")[1][1]]
            # fg_color = make_hex_color(value["color"][num])

            # Insert the unformatted text
            # Specifying the tag_id in the insert eliminates the need to do a tag_add.
            clean_message = message.replace(":lblend", "")
            value["text"][inner_num] = clean_message
            self.textview_textbox.insert(start_idx, clean_message)

            # # Apply the html attributes
            # self.textview_textbox.tag_config(
            #     tag_id,
            #     font=(mygui.font, font_size),
            #     background=bg_color,
            #     foreground=fg_color,
            # )

            char_position += len(formatted_message)

        line_num += 1
        char_position = 0

    # Draw the bounding box
    box_text_with_unicode(self.textview_textbox, begin_box, end_box, spacing, max_tag_len)

    # Apply the highlights to label
    apply_highlights(self.textview_textbox, begin_box, all_values, tags)

    # Point to the next available line by geting our last line number.
    line_num = get_last_line(self.textview_textbox)

    # Reset for next label
    self.draw_box = {"all_values": [], "start_idx": None, "end_idx": None, "spacing": 0}

    return line_num, tags


def box_text_with_unicode(
    text_widget: ctk,
    start: str = "1.0",
    end: str = "end-1c",
    left_margin_spaces: int = 0,
    max_tag_len: int = 0,
) -> int:
    """
    Replaces the text in the given range with a visually boxed version using Unicode box characters.
    Adds a left margin spacer before the box.

    Args:
        text_widget: The tk.Text widget.
        start (str): Start index of the text.
        end (str): End index of the text.
        left_margin_spaces (int): Number of spaces to prepend as a margin.
    """
    # Get the text
    content = text_widget.get(start, end)
    lines = content.split("\n")
    max_len = max(len(line) for line in lines) + max_tag_len

    # Left margin spacer
    spacer = " " * left_margin_spaces

    # Build box lines
    top = "\n" + spacer + "┌" + "─" * (max_len + 2) + "┐"
    bottom = spacer + "└" + "─" * (max_len + 2) + "┘\n"
    middle = [spacer + f"│ {line.ljust(max_len)} │" for line in lines]

    # Combine lines
    boxed_text = "\n".join([top, *middle, bottom])

    # Replace text in widget
    text_widget.delete(start, end)
    text_widget.insert(start, boxed_text)


def get_last_line(self: ctk) -> int:
    """
    Calculates the last line number in a tkinter Text widget.

    Args:
      text_widget: The Tkinter Text widget to inspect.

    Returns:
      The last line number as an integer.
    """
    # Get the index of the last character in the text widget.
    last_char_index = self.index("end" + "-1c")

    # Split the index string to get the line number.
    return int(last_char_index.split(".")[0])


def generate_unique_string() -> str:
    """
    Generates a unique 5-digit string using a UUID.

    Returns:
        str: A unique 5-character string.
    """
    # Generate a UUID (Universally Unique Identifier)
    unique_id = uuid.uuid4()

    # Convert the UUID to a hexadecimal string and take the first 5 characters
    return unique_id.hex[:5]


def make_hex_color(color: str) -> str:
    """
    Converts a given color string to a hex color string if it's a digit.

    Args:
        color (str): The color string to be converted.

    Returns:
        str: The hex color string if the input is a digit, otherwise the original color string.
    """
    # Add color to the tag
    if color.isdigit():
        return "#" + color
    return color


def apply_highlights(self: ctk, begin_box: str, all_values: list, tags: list) -> None:
    """Applies syntax highlighting to a custom text widget based on provided data.

    This function iterates through a list of text values and their corresponding
    highlight attributes, applying specific tags to portions of text within the
    widget. It calculates the correct line numbers and character positions to
    apply font and color styling.

    Args:
        self: The custom text widget instance.
        begin_box: A string in the format 'line.column' indicating the starting
                   point for highlighting.
        all_values: A list of dictionaries, where each dictionary contains text
                    to be highlighted, highlighting types, and colors.
        tags: An empty list that will be populated with the created tag IDs
              during the process.

    Returns:
        None: The function modifies the text widget and the 'tags' list in place.
    """
    mygui = self.master.master.master
    bg_color = make_hex_color(mygui.color_lookup["background_color"])
    max_tag_len = 0

    line_num = int(begin_box.split(".")[0]) + 1
    # content = self.get(begin_box, "end").split("\n")

    # Go through all of the values in the label and output them
    for num, value in enumerate(all_values):
        # Get spacing only if this is first element.
        if num == 0:
            spacing = value["spacing"]
        char_position = 0

        # Iterate over a list or a string.
        for inner_num, message in enumerate(value["text"]):
            if message == "\n":
                continue
            if "stop task" in message:
                print("bingo")
            clean_message = message.replace("\n", "")

            # Find the message in our textbox.
            line_num, char_position = search_text_from_line(self, clean_message, line_num, char_position)
            if line_num is None:
                print("bingo rutroh...string not found:", message, line_num, char_position)

            # Tag it and get the attributes
            new_start_idx = str(line_num) + "." + str(char_position)
            new_end_idx = str(line_num) + "." + str(char_position + len(message))

            tag_id = f"{new_start_idx}:{value['highlights'][inner_num]}:{value['color'][inner_num]}"
            max_tag_len = max(max_tag_len, len(tag_id))
            tags.append(tag_id)
            font_size = heading_fonts[tag_id.split(":")[1][1]]
            fg_color = make_hex_color(value["color"][inner_num])

            # Apply the html attributes
            self.tag_add(tag_id, new_start_idx, new_end_idx)
            self.tag_config(
                tag_id,
                font=(mygui.font, font_size),
                background=bg_color,
                foreground=fg_color,
            )
            modified_line = get_line_contents(self, str(line_num))
            print("bingo", modified_line, len(modified_line))

            # char_position += len(message)
            char_position = 0

        # line_num += 1
        char_position = -1


def get_line_contents(text_widget: ctk, line_number: str) -> str:
    """
    Retrieves the contents of a specific line number from a tkinter Text widget.

    Args:
        text_widget: The tkinter Text widget instance.
        line_number: The 1-based line number to retrieve.

    Returns:
        The string content of the specified line, or an empty string if the line doesn't exist.
    """
    try:
        # Construct the start and end indices for the line
        start_index = f"{line_number}.0"
        end_index = f"{line_number}.end"

        # Get the text from the widget
        return text_widget.get(start_index, end_index)

    except tk.TclError:
        # Handle cases where the line number might be out of range
        return ""


def search_text_from_line(
    text_widget: tk.Text,
    search_string: str,
    start_line: int,
    start_char: int,
) -> tuple[int, int] | None:
    """
    Searches a Tkinter Text widget for a specific string, starting from a given
    line number and character position.

    Args:
        text_widget: The Tkinter Text widget to search.
        search_string: The string to search for.
        start_line: The 1-based line number to begin the search.
        start_char: The 0-based character position on the starting line.

    Returns:
        A tuple (line_number, char_position) of the first match, or (None, None) if no match is found.
    """
    # Construct the starting index for the search with both line and character position
    start_index = f"{start_line}.{start_char}"

    # Use the Text widget's built-in search method
    match_index = text_widget.search(search_string, start_index, tk.END, nocase=True)

    if match_index:
        # If a match is found, parse the index to get line and character position
        line, char = map(int, match_index.split("."))
        return line, char

    return None, None
