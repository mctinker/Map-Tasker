#! /usr/bin/env python3
"""

 guiutil2: General and GUI utilities.

These are functions pulled out of maputils, guiwins and guiutils that would otherwise cause a circular
import error.

"""

import contextlib
import os
import re
import tkinter as tk
import tkinter.font as tkfont

import customtkinter as ctk
import requests

from maptasker.src.aiutils import get_api_key
from maptasker.src.error import rutroh_error
from maptasker.src.maputils import make_hex_color
from maptasker.src.primitem import PrimeItems
from maptasker.src.video import handle_image

# Define label fonts for headings: 0=h0, 1=h1, etc.  7 = smallest
heading_fonts = {"0": 12, "1": 18, "2": 17, "3": 16, "4": 15, "5": 14, "6": 13, "7": 10}


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
            rutroh_error("Error: Window width must be at least 300.")
            return False
        if height < 50:
            rutroh_error("Error: Window height must be at least 50.")
            return False
        if pos_x < 0:
            rutroh_error("Error: Window position X must be a non-negative number.")
            return False
        if pos_y < 0:
            rutroh_error("Error: Window position Y must be a non-negative number.")
            return False

        return True  # noqa: TRY300
    except ValueError:
        rutroh_error("Error: Invalid numeric value in geometry string.")
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
            rutroh_error(f"Warning: Could not read source for {filename}:{lineno} - {e}")

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

    The method rutroh_errors a message indicating whether the AI model and API key combination
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


def draw_box_around_text(self: ctk, line_num: int) -> tuple[int, list]:
    """
    Draws a styled box around text in the custom textbox widget.
    Handles multi-line, images, tables, labels, and TaskerNet descriptions.
    NOTE: He who dares ent4er this function does so on his/her own cognizance!
    """

    mygui = self.master.master
    textview = self.textview_textbox
    cget_width = textview.cget
    all_values = self.draw_box["all_values"]

    # Initialize state
    max_msg_len = 0
    number_of_inserted_lines = 0
    end_of_label = False
    its_a_label = True
    prev_msg = "---none---"
    first_message = True
    self.previous_heading = "0"
    self.previous_font = "None"
    lines_to_skip = 0
    in_list = False
    ordered_list = False
    # Cached strings and sets for fast membership/compare
    skip_tags = {"<big>", "</big>", "<small>", "</small>"}
    list_start_tags = {"<ul>", "<p>"}
    hr_tag = "<hr>"
    img_tag = "<img src="
    end_list_tags = ("</ul>", "</ol>")
    newline_set = {"", "       * "}

    # Setup text widget insertion
    line_num = int(textview.index("end-1c").split(".")[0]) + 1
    start_idx = f"{line_num}.0"
    begin_box = start_idx

    # Localize helper functions for faster access: compues only once.
    _clean = _clean_message
    _newline = _insert_newline
    _handle_img = handle_image
    _tnet = _handle_taskernet_description
    _lbl_end = _handle_label_end
    _norm = _normalize_message
    _find_box = _find_begin_box
    _close = _close_label
    _final = _finalize_bottom
    _bbox = _apply_bounding_box
    _html = starts_with_html
    _insert_text = _insert_and_tag
    _proc_tbl = process_table
    _hr = "―" * (int(cget_width("width")) - 2)

    for num, value in enumerate(all_values):
        spacing = value["spacing"] if num == 0 else 0
        char_position = 0

        for inner_num, message in enumerate(value["text"]):
            # Ignore <p> after TaskerNet description
            # if message == "<p>" and inner_num == 1:
            #     continue
            if value["end"][inner_num]:
                end_of_label = True

            # Modify line as needed and setup the starting index
            clean_message = _clean(self, message, value, inner_num)
            start_idx = f"{line_num}.{char_position}"

            # Handle empty/newline message, but only if it isn't html of some sort.
            if (not clean_message and not message.startswith("<")) or clean_message in {"\n\n", "<p>"}:
                char_position, spacing, line_num, start_idx = _newline(self, start_idx, value, line_num)
                if clean_message in ("<p>", "\n\n") and prev_msg not in ("<p>", "\n\n"):
                    char_position, spacing, line_num, start_idx = _newline(self, start_idx, value, line_num)
                    prev_msg = clean_message
                continue

            # Handle multi-line messages
            all_messages = clean_message.split("\n")

            msg_idx = 0
            # NOTE: If one or more lines are repeated in the output, that means that
            #       guimap 'process_label_html' is returning 1 or more too shy...
            #       (lines_to_skip is too small)
            while msg_idx < len(all_messages):
                msg = all_messages[msg_idx]

                msg_idx += 1
                # Skip or process special content
                if lines_to_skip > 0:
                    lines_to_skip -= 1
                    continue
                if value["table"] and value["table"][inner_num]:
                    lines_to_skip, line_num, start_idx = _proc_tbl(self, value, inner_num)
                    continue
                if img_tag in msg:
                    _handle_img(self, msg, start_idx)
                    line_num += 3  # 1='\n', 2=image link, 3='\n'
                    start_idx = f"{line_num!s}.0"
                    continue
                if msg == "</a>":
                    continue
                if msg == hr_tag:  # Horizontal line
                    width = int(textview.cget("width"))
                    hr_line = "―" * (width - 2)  # or use "-" or "—"
                    textview.insert("insert", hr_line + "\n")
                    continue
                # Handle start and end lists
                if msg in list_start_tags:
                    ordered_list = False
                    char_position, spacing, line_num, start_idx = _newline(
                        self,
                        start_idx,
                        value,
                        line_num,
                    )
                    continue
                if msg == "<ol>":
                    ordered_list = True
                    ordered_count = 0
                    char_position, spacing, line_num, start_idx = _newline(
                        self,
                        start_idx,
                        value,
                        line_num,
                    )
                    continue
                if msg.startswith(end_list_tags):
                    if msg.startswith("</ol>"):
                        ordered_list = False
                        ordered_count = 0
                    in_list = False
                    prev_msg = msg
                    in_list = False
                    continue
                # Ignore blank messages in lists
                if not msg and in_list:
                    continue

                # Handle breaks by breaking them up and injecting the items into all_messages.
                line_break = False
                if "<br>" in msg:
                    line_break = True
                    parts = msg.split("<br>")
                    msg = parts[0]
                    all_messages[msg_idx:msg_idx] = ["", *parts[1:]]

                # Handle TaskerNet description
                msg, its_a_label = _tnet(msg, its_a_label)

                # End-of-label adjustments
                updated_msg, end_of_label = _lbl_end(msg, end_of_label, value, inner_num)

                # Handle list items
                if "<li>" in updated_msg or (msg and in_list):
                    in_list = True
                    if "<li>" in updated_msg and ordered_list:
                        ordered_count += 1
                        updated_msg = updated_msg.replace("<li>", f"{ordered_count!s}. ")
                    else:
                        updated_msg = updated_msg.replace("<li>", "* ")
                if "</li>" in updated_msg:
                    in_list = False
                    updated_msg = updated_msg.replace("</li>", "")

                # Insert newline if needed before non-html text after html text.
                html_starter = _html(updated_msg)

                # Ignore msg and insert a '\n' if this is html only tags, ir just the start of a list item/newline,
                # or specific tags or just plain empty.
                if (
                    not html_starter
                    and (updated_msg in newline_set)
                    and not message.startswith("<a href")
                    and message not in skip_tags
                    and prev_msg.strip()
                ) or (not updated_msg and prev_msg == "</ul>"):
                    # Insert the new line
                    char_position, spacing, line_num, start_idx = _newline(
                        self,
                        start_idx,
                        value,
                        line_num,
                    )
                    prev_msg = ""
                    continue

                # Ignore two newlines in a row
                if not updated_msg.strip() and not prev_msg.strip():
                    continue

                # Handle list items and get rid of html artifacts
                between_line_spacing = -20 if updated_msg.startswith("* ") else 0
                msg_to_insert = _norm(updated_msg, its_a_label, char_position)

                # Just insert a newline if we have a blank message at the beginning of a line
                if (
                    char_position == 0
                    and (msg_to_insert == " " or not msg_to_insert.strip())
                    and message not in skip_tags
                ):
                    char_position, spacing, line_num, start_idx = _newline(
                        self,
                        start_idx,
                        value,
                        line_num,
                    )
                else:
                    # Insert & tag message
                    max_msg_len, char_position, line_num = _insert_text(
                        self,
                        msg_to_insert,
                        max_msg_len,
                        spacing,
                        between_line_spacing,
                        start_idx,
                        char_position,
                        value,
                        inner_num,
                    )
                    # Handle line break if any
                    if line_break:
                        line_break = False
                        char_position, spacing, line_num, start_idx = _newline(
                            self,
                            start_idx,
                            value,
                            line_num,
                        )

                # Debug code to find what text is being inserted
                # if "ChatGPT API" in msg or "The" in msg:  # --- IGNORE ---
                #     last_line = textview.get("end-1line", "end")
                # Ensure that if we are adding an empty message, our starting position is at 0
                if updated_msg == "":
                    char_position = 0

                # Update starting index
                number_of_inserted_lines += 1
                start_idx = f"{line_num}.{char_position}"

                if first_message:
                    begin_box, _line_num = _find_box(self, msg_to_insert, its_a_label)
                    first_message = False

                # Reset spacing after concatenation.  Don't do it if we just added a newline
                if msg:
                    spacing = 0

                prev_msg = msg_to_insert

            if end_of_label:
                break

        if end_of_label:
            if prev_msg != "":
                line_num, start_idx = _close(self, line_num, value)
            break

    # Even out the bottom of the box
    line_num, start_idx = _final(self, line_num, start_idx)

    # Calculate between-line spacing
    minimum_space = bool(len(all_values[0]["text"]) == 1 and len(all_messages) == 1)

    # Add bounding box tag
    line_num = _bbox(
        self,
        begin_box,
        line_num,
        max_msg_len,
        mygui.saved_background_color,
        its_a_label,
        minimum_space,
    )

    # Insert newline after the label
    textview.insert(f"{line_num}.0", "\n", "bg_color")
    line_num += 1
    textview.tag_config("bg_color", background=mygui.saved_background_color)

    # Reset state for next draw
    self.draw_box = {"all_values": [], "start_idx": None, "end_idx": None, "spacing": 0, "end": False}

    return line_num


# ----------------
# Helper methods
# ----------------
def _insert_and_tag(
    self: ctk,
    message: str,
    max_msg_len: int,
    spacing: int,
    between_line_spacing: int,
    start_idx: str,
    char_position: int,
    value: dict,
    inner_num: int,
) -> tuple[int, int, int]:
    """Inserts and tags a message in a custom text widget.

    This private helper function is responsible for inserting a formatted message
    into a text widget (`textview_textbox`), applying a custom tag to it, and
    configuring the tag with specific font, background, and foreground colors.
    It also updates various tracking variables like line number and character position.

    Parameters
    ----------
    self : ctk
        The instance of the `ctk` class, which holds the text widget.
    message : str
        The string content to be inserted into the text widget.
    max_msg_len : int
        The current maximum length of a message. This value is updated if the
        current message is longer.
    spacing : int
        The number of leading spaces to add to the message. A value of 0 means
        no leading spaces are added.
    between_line_spacing : int
        The spacing to add after the current line ('spacing2' in tag_config)
    start_idx : str
        The starting index (e.g., "1.0") for the text insertion.
    char_position : int
        The character position on the current line.
    value : dict
        A dictionary containing formatting information, including 'spacing',
        'highlights', and 'color'.
    inner_num : int
        An index used to access specific values from the 'highlights' and
        'color' lists within the `value` dictionary.

    Returns
    -------
    tuple[int, int, int]
        A tuple containing the updated values for:
        - `max_msg_len`
        - `char_position`
        - 'line_num'
    """
    # Optimized version: inserts and tags a message in a custom text widget.
    mygui = self.master.master
    bg_color = (mygui.saved_background_color,)

    # Local vars to avoid repeated dict lookups
    highlights = value["highlights"][inner_num]
    decor = value["decor"][inner_num].strip()
    color_val = value["color"][inner_num]

    temp_font = highlights.split(";")
    heading_num = self.previous_heading

    # Font style detection
    first_font = temp_font[0]
    if first_font == "italic":
        font = "italic"
    elif first_font == "bold":
        font = "bold"
    else:
        heading_num = (
            "0" if message == " TaskerNet description:\n " or not first_font else first_font.replace("-text", "")[1]
        )
        font = "normal"

    underline = decor == "underline"

    # Get font size safely
    font_size = heading_fonts.get(heading_num, heading_fonts["0"])
    if font_size < 12 and char_position == 0:
        spacing += 3

    if PrimeItems.windows_system:  # Precompute platform check once globally
        font_size *= 2

    # Debugging: prepend font size
    if PrimeItems.program_arguments.get("debug") and not message.startswith("<a href="):
        message = f"{font_size}{message}"

    # Adjust spacing if this is the largest font
    font_sizes = list(heading_fonts.values())
    max_font_size = max(font_sizes)
    if font_size == max_font_size:  # Precompute max_font_size globally
        spacing = spacing // 2 if spacing > 0 else 0

    # Reuse or assign font
    font_key = f"{mygui.font}{font}{font_size}"
    font_to_use = mygui.font_table.get(font_key)
    if font_to_use is None:
        font_to_use = assign_font(mygui.font, font_size, font, underline)
        mygui.font_table[font_key] = font_to_use

    # Handle hyperlinks
    href = ""
    if "<a href=" in message:
        orig_message = message
        # Add hyperlink for alt text
        temp = message.split('"')

        # Handle first part before href, if any.
        href = ""  # Clear href to avoid double insert below
        message = orig_message.split('<a href="')[0]
        if message:
            if spacing > 0:
                # Build the spaces string once and use normal string concatenation to avoid nested f-strings
                spaces = " " * spacing
                message = spaces + message.replace("\n", "\n" + spaces).lstrip()
            tag_id = f"{heading_num};{font}:{color_val}:{decor}:{between_line_spacing}"
            _insert_styled_message(
                self=self,
                message=message,
                start_idx=start_idx,
                tag_id=tag_id,
                font_to_use=font_to_use,
                bg_color=bg_color,
                fg_color=color_val,
                underline=underline,
                between_line_spacing=between_line_spacing,
                spacing=spacing,
                temp_font=temp_font,
                font=font,
                font_size=font_size,
                mygui=mygui,
            )
            spacing = 0  # Set spacing to 0 for hyperlink part

        # Handle href part
        start_idx = self.textview_textbox.index(tk.END + "-1c")
        href = temp[1]
        message = temp[2][1 : len(temp[2]) - 4]
        tag_id = self.textview_hyperlink.add(href)
        message_to_display = message if spacing == 0 and char_position == 0 else f"{' ' * spacing}{message}"
        self.textview_textbox.insert(start_idx, message_to_display, tag_id)

        # Add video link if there is one.
        if "youtu.be" in orig_message or "youtube" in orig_message or "mp4" in orig_message:
            temp = start_idx.split(".")
            start_idx = f"{temp[0]}.{int(temp[1]) + len(message) + 2!s}"
            handle_image(self, orig_message, start_idx)
            temp = start_idx.split(".")
            char_position += len(href) + 12  #  '[> VIDEO: href]'

    else:
        tag_id = f"{heading_num};{font}:{color_val}:{decor}:{between_line_spacing}"

    # Apply spacing.  'TaskerNet description' has a '\n' between it and before the first line
    if spacing > 0:
        message = " " * spacing + message.replace("\n", f"\n{spacing * ' '}").lstrip()

    # Update max message length
    max_msg_len = _get_max_msg_len(message, max_msg_len)

    # Insert normal text if not hyperlink
    if not href:
        _insert_styled_message(
            self=self,
            message=message,
            start_idx=start_idx,
            tag_id=tag_id,
            font_to_use=font_to_use,
            bg_color=bg_color,
            fg_color=color_val,
            underline=underline,
            between_line_spacing=between_line_spacing,
            spacing=spacing,
            temp_font=temp_font,
            font=font,
            font_size=font_size,
            mygui=mygui,
        )

    # Update state
    char_position += len(message)
    self.previous_heading = heading_num
    self.previous_font = font_to_use
    last_char_index = self.textview_textbox.index(tk.END + "-1c")
    line_number, _ = last_char_index.split(".")

    return max_msg_len, char_position, int(line_number) + 1


def _insert_styled_message(
    self: object,
    message: str,
    start_idx: str,
    tag_id: str,
    font_to_use: tuple,
    bg_color: str,
    fg_color: str,
    underline: bool,
    between_line_spacing: int,
    spacing: int,
    temp_font: list,
    font: str,
    font_size: int,
    mygui: object,
) -> None:
    """Insert a styled message into the text widget."""

    # Convert color to hex
    fg_color = make_hex_color(fg_color)

    # Configure base tag
    _configure_tag(self, tag_id, font_to_use, bg_color, fg_color, underline, between_line_spacing)

    # Handle underline spacing at beginning of line
    if underline and spacing > 0:
        underline = False
        _configure_tag(self, "blank", font_to_use, bg_color, bg_color, underline, between_line_spacing)

        # Insert the spacing blanks
        self.textview_textbox.insert(start_idx, f"{spacing * ' '}", "blank")

        # Update start index after spacing
        start_idx = f"{start_idx.split('.')[0]}.{1 + spacing!s}"

        # Remove spacing from the message
        message = message[spacing:]

    # Secondary font specified?
    if len(temp_font) > 1:
        new_font = temp_font[1]
        tag_id = tag_id.replace(font, new_font)
        font_to_use = (mygui.font, font_size, new_font)
        _configure_tag(self, tag_id, font_to_use, bg_color, fg_color, underline, between_line_spacing)

    # Insert the main message
    self.textview_textbox.insert(start_idx, message, tag_id)

    # Special case: left alignment when first character
    if start_idx.endswith(".0"):
        self.textview_textbox.tag_config(tag_id, lmargin1=0, lmargin2=0, justify="left")

    # Table heading detection
    if "+───" in message:
        table_heading = message.split("\n")[1] if "\n" in message else ""
        if table_heading:
            th_tag_id = f"table_heading;bold:{fg_color}:decor:{between_line_spacing}"
            font_to_use = assign_font(mygui.font, font_size, "bold", underline)
            _configure_tag(self, th_tag_id, font_to_use, bg_color, fg_color, underline, between_line_spacing)

            self.textview_textbox.tag_add(th_tag_id, f"{start_idx}+1c", f"{start_idx}+{1 + len(table_heading)}c")


def optimize_message_formatting(message: str) -> str:
    """
    Optimizes the replacement of specific newline patterns and resulting <br> sequences
    using a single regular expression substitution.

    :param message: The input string (e.g., text content).
    :return: The formatted string.
    """

    # 1. Define a replacement function to handle the original logic's priorities.
    def replace_match(match: str) -> str:
        matched_string = match.group(0)

        # Handle the longest/most specific pattern first (5 newlines)
        if matched_string == "\n\n\n\n\n":
            return "<br>"
        # Handle the second-longest/second-specific pattern (4 newlines)
        if matched_string == "\n\n\n\n":
            return "\n\n"
        # Handle the resulting <br><br> pattern
        if matched_string == "<br><br>":
            return "<p>"
        return matched_string  # Should not happen, but a safe default

    # 2. Combine all patterns into a single regex for a single pass.
    # The 'or' operator `|` makes the regex engine search for ANY of these patterns.
    # Crucially, the patterns must be listed with the most specific/longest patterns first
    # to ensure they are matched preferentially.
    # We are matching: 5 newlines OR 4 newlines OR <br><br>
    pattern = r"\n{5}|\n{4}|<br><br>"

    # 3. Use re.sub with the replacement function.
    # This iterates over the string once, finds all matches for the combined pattern,
    # and calls replace_match to determine the substitution for each.
    return re.sub(pattern, replace_match, message)


def _clean_message(self: ctk.CTkTextbox, message: str, value: dict, inner_num: int) -> str:
    if message == "<p>":
        return "<p>"

    # Reduce the number of newlines...add(# message = message.replace("\n\n\n\n\n", "<br>")
    # message = message.replace("\n\n\n\n", "\n\n")
    # message = message.replace("<br><br>", "<p>"))
    message = optimize_message_formatting(message)

    # Deal with <pre> formatted text
    if "<pre>" in message or "</pre>" in message:
        if "<pre>" in message:
            # The <pre" is at innernum, it's text is at inner_num + 1
            value["highlights"][inner_num + 1] = "bold"
        message = message.replace("<pre>", " \n").replace("</pre>", "\n\n").replace("\n\n\n\n", "\n\n")

    # Deal with <big> and <small> tags.  Make it one heading bigger/smaller
    if "<big>" in message or "</big>" in message or "<small>" in message or "</small>" in message:
        if "<big>" in message:
            # Save current heading
            self.current_heading = _get_current_heading(value, inner_num)
            # Handling <big> tag: Decrease the heading number (e.g., h5 -> h4)
            heading_num = (
                int(value["highlights"][inner_num][1]) if value["highlights"][inner_num].startswith("h") else 0
            )
            entry_to_update = inner_num + 1 if message.endswith("<big>") else inner_num
            if heading_num == 0:
                # If no heading, set a default (e.g., h5-text, you might adjust this)
                value["highlights"][entry_to_update] = "h5-text"
            else:
                # Decrease the heading number by 1 (making the text "bigger")
                value["highlights"][
                    entry_to_update
                ] = f"h{max(1, heading_num - 1)!s}-text"  # Use max(1, ...) to prevent h0

        elif "<small>" in message:
            # Save current heading
            self.current_heading = _get_current_heading(value, inner_num)
            # Handling <small> tag: Increase the heading number (e.g., h4 -> h5)
            heading_num = (
                int(value["highlights"][inner_num][1]) if value["highlights"][inner_num].startswith("h") else 0
            )
            entry_to_update = inner_num + 1 if message == "<small>" or message.endswith("<small>") else inner_num
            if heading_num == 0:
                # If no heading, set a default (e.g., h6-text, you might adjust this)
                value["highlights"][entry_to_update] = "h7-text"
            else:
                # Increase the heading number by 1 (making the text "smaller")
                value["highlights"][
                    entry_to_update
                ] = f"h{min(6, heading_num + 1)!s}-text"  # Use min(6, ...) to prevent > h6

        elif "</big>" in message or "</small>" in message:
            if message.startswith(("</big>", "</small>")):
                if "\n\n" not in value["text"][inner_num] or (
                    message.startswith(("</big>\n\n", "</small>\n\n"))
                    and (message not in {"</big>\n\n", "</small>\n\n"})
                ):
                    value["highlights"][inner_num] = self.current_heading
                else:
                    value["highlights"][inner_num + 1] = self.current_heading
            else:
                with contextlib.suppress(IndexError):
                    if "\n\n" not in value["text"][inner_num + 1]:
                        value["highlights"][inner_num + 1] = self.current_heading
                    else:
                        value["highlights"][inner_num + 2] = self.current_heading

    # Remove both <big> and <small> tags from the message
    message = message.replace("<big>", "").replace("</big>", "")
    return message.replace("<small>", "").replace("</small>", "")


def _get_current_heading(value: dict, inner_num: int) -> str:
    for i in range(inner_num, -1, -1):
        element = value["highlights"][i]
        if element[1].isdigit():
            return element
    return value["highlights"][inner_num]


def _handle_taskernet_description(msg: str, its_a_label: bool) -> tuple[str, bool]:
    if "TaskerNet description:" in msg:
        its_a_label = False
        return msg.replace("TaskerNet description:", "TaskerNet description:\n"), its_a_label
    return msg, its_a_label


def _handle_label_end(
    msg: str,
    end_of_label: bool,
    value: dict,
    inner_num: int,
) -> tuple[str, bool]:
    if not end_of_label and (value["end"][inner_num] or ":lblend" in msg):
        return msg.replace('<data-flag=":lblend">', "") + " ", True
    if end_of_label:
        return msg.replace('<data-flag=":lblend">', ""), True
    return msg, end_of_label


def _normalize_message(msg: str, its_a_label: bool, char_position: int) -> str:
    msg = msg.replace("&nbsp;", " ").replace("<p>", "\n").replace("</p></div>", "")
    if char_position == 0 and not its_a_label and not msg.startswith((" ", "<a href=")):
        msg = " " + msg
    return msg


def _find_begin_box(self: ctk.CTkTextbox, msg_to_insert: str, its_a_label: bool) -> tuple[str, int]:
    max_tries = 30
    last_char_index = self.textview_textbox.index(tk.END + "-1c")
    line_number, _ = last_char_index.split(".")
    prev_num = int(line_number)
    if "\n" in msg_to_insert:
        msg_to_insert = msg_to_insert.split("\n")[1]

    # Handle href case.  Just look for the front part.  Avoid a loop situation.
    if "<a href=" in msg_to_insert:
        temp = msg_to_insert.split('"')
        msg_to_insert = temp[0][1 : len(temp[2]) - 4]

    content = ""
    while msg_to_insert not in content:
        # Bilout if we've searched too much.
        max_tries -= 1
        if max_tries <= 0 or prev_num <= 1:
            break
        content = self.textview_textbox.get(f"{prev_num}.0", f"{prev_num}.end")
        if msg_to_insert not in content:
            prev_num -= 1
    begin_box = f"{prev_num}.0" if its_a_label else f"{prev_num - 1}.0"
    return begin_box, int(line_number)


def _close_label(self: ctk.CTkTextbox, line_num: int, value: dict) -> tuple[int, str]:
    # line_num += 1
    _, _, line_num, start_idx = _insert_newline(self, f"{line_num}.0", value, line_num)
    return line_num, start_idx


def _finalize_bottom(
    self: ctk.CTkTextbox,
    line_num: int,
    start_idx: str,
) -> tuple[int, str]:
    line_num = int(self.textview_textbox.index("end-1c").split(".")[0])
    start_idx = f"{line_num}.0"
    return line_num, start_idx


def _apply_bounding_box(
    self: ctk.CTkTextbox,
    begin_box: str,
    line_num: int,
    max_msg_len: int,
    bg_color: str,
    its_a_label: bool,
    minimum_space: bool,
) -> int:
    if not its_a_label:
        begin_box = f"{(int(begin_box.split('.')[0]) + 1)}.0"
    end_box = f"{line_num!s}.{max_msg_len + 1!s}"

    spacing1, spacing2, spacing3 = (5, 0, 5) if minimum_space else (-5, -30, -5)
    bbox_tag = f"{begin_box}:bbox:{spacing1}:{spacing2}:{spacing3}"

    self.textview_textbox.tag_add(bbox_tag, begin_box, end_box)
    # spacing1: extra space before a line
    # spacing2: space between wrapped lines of the same paragraph
    # spacing3: extra space after a line
    self.textview_textbox.tag_config(
        bbox_tag,
        background=bg_color,
        relief="ridge",
        borderwidth=2,
        spacing1=spacing1,
        spacing2=spacing2,
        spacing3=spacing3,
        rmargin=10,
        justify="left",
        lmargin1=0,
        lmargin2=0,
    )
    return line_num + 1


def _configure_tag(
    self: ctk,
    tag_id: str,
    font_to_use: tkfont,
    bg_color: str,
    fg_color: str,
    underline: str,
    between_line_spacing: int,
) -> None:
    self.textview_textbox.tag_config(
        tag_id,
        font=font_to_use,
        background=bg_color,
        foreground=fg_color,
        underline=underline,
        spacing2=between_line_spacing,  # This is ovberridden by the bbox spacing.
        justify="left",
    )


def assign_font(font_name: str, font_size: int, font: str, underline: bool) -> tkfont:
    """Creates and returns a CTkFont object with specified attributes.

    This function generates a CustomTkinter font object based on a given font family,
    size, and style. It supports "normal", "bold", and "italic" styles.

    Args:
        font_name (str): The name of the font family (e.g., "Arial").
        font_size (int): The size of the font in points.
        font (str): The font style. Must be one of "normal", "bold", or "italic".
        underline (bool): A boolean indicating whether the font should be underlined.

    Returns:
        tkfont: A configured CTkFont object.

    Raises:
        ValueError: If an unsupported font style is provided.
    """
    if font == "normal":
        return ctk.CTkFont(family=font_name, size=font_size, underline=underline)
    if font == "bold":
        return ctk.CTkFont(family=font_name, size=font_size, weight="bold", underline=underline)
    return ctk.CTkFont(family=font_name, size=font_size, slant="italic", underline=underline)


def _insert_newline(self: ctk, start_idx: str, value: dict, line_num: int) -> tuple[int, int, int, str]:
    """Inserts a newline character into the textbox and updates state variables.

    This helper function is designed to handle the logic for adding a new line
    to the Tkinter text widget, resetting the character position, and
    incrementing the line number for subsequent text insertions.

    Args:
        self: The instance of the custom textbox class (ctk).
        start_idx: The current starting index for text insertion.
        value: A dictionary containing data, including spacing information.
        line_num: The current line number.

    Returns:
        A tuple containing:
        - The reset character position (always 0).
        - The spacing value for the new line.
        - The updated line number.
        - The new start index string.
    """
    self.textview_textbox.insert("end", "\n")
    char_position = 0
    line_num += 1
    start_idx = str(line_num) + "." + str(char_position)
    return 0, value["spacing"], line_num, start_idx


def _get_max_msg_len(message: str, max_msg_len: int) -> int:
    """Get the maximum length of the messages"""
    return max(max_msg_len, len(message))


def process_table(
    self: ctk,
    value: dict,
    inner_num: str,
) -> tuple[int, int, str]:
    """
    Process and render a text-based table by surrounding its rows with ASCII boxes
    and inserting them into the target widget.

    The function:
    1. Collects all contiguous table lines from `value["text"]` starting at `inner_num`.
    2. Boxes the collected lines using `box_strings`.
    3. Iterates over the boxed lines and inserts them into the widget with
       appropriate styling, updating the line counter and text index.

    Parameters
    ----------
    self : ctk
        The widget or controller object that manages insertion of formatted text.
    value : dict
        A dictionary containing the text and table structure. Expected keys:
        - "text": list of strings containing the table content.
        - "table": list of booleans indicating which lines belong to a table.
    inner_num : str
        Index (as a string) of the current line within `value["text"]`.

    Returns
    -------
    tuple[int, int, str]
        A tuple containing:
        - lines_to_skip (int): Number of table lines consumed from `value["text"]`.
        - line_num (int): Updated line number after inserting the boxed table.
        - start_idx (str): Updated insertion index after processing.

    Notes
    -----
    - Stops inserting when a line containing `"==========="` is encountered.
    - Uses `_insert_and_tag` to insert lines with styling and tagging.
    - The box width is determined by the longest line in the collected table.
    """

    table = ["<table>"]
    lines_to_skip = 0
    inner_num += 1
    # Gather all lines of the table
    while inner_num < len(value["text"]) and value["table"][inner_num]:
        table.append(value["text"][inner_num])
        lines_to_skip += 1
        inner_num += 1
    inner_num -= 1  # Back-off the last increment

    # Box the lines
    boxed_table = html_table_to_ascii(table)

    # Output it onto the screen
    # Join everything into one big string
    big_block_of_text = "\n".join(boxed_table) + "\n\n"

    # Get the next line number and start index
    line_num = int(self.textview_textbox.index("end-1c").split(".")[0]) + 1
    start_idx = str(line_num) + ".0"

    # Insert, in a single call, all of the lines of data.
    value["decor"][inner_num] = ""  # No underline for table
    _, _, _ = _insert_and_tag(
        self,
        big_block_of_text,
        0,
        0,
        -40,
        start_idx,
        0,
        value,
        inner_num,
    )

    # Get the next line number and start index
    line_num = int(self.textview_textbox.index("end-1c").split(".")[0]) + 1
    start_idx = str(line_num) + ".0"
    return lines_to_skip, line_num, start_idx


def html_table_to_ascii(html_lines: list[str]) -> list[str]:
    """
    Convert a list of strings representing HTML <table> elements
    into an ASCII-art table, without using BeautifulSoup.
    """
    # Join all lines into a single string
    html = "".join(html_lines)

    # Extract rows <tr>...</tr>
    row_matches = re.findall(r"<tr.*?>(.*?)</tr>", html, flags=re.DOTALL | re.IGNORECASE)
    rows = []

    for row in row_matches:
        # Extract cells <td> or <th>
        cells = re.findall(r"<t[dh].*?>(.*?)</t[dh]>", row, flags=re.DOTALL | re.IGNORECASE)
        # Clean up whitespace and inner tags
        cells = [re.sub(r"<.*?>", "", c).strip() for c in cells]
        rows.append(cells)

    if not rows:
        return ["[Empty <table>]"]

    # Compute column widths
    col_widths = [max(len(row[i]) if i < len(row) else 0 for row in rows) for i in range(max(len(r) for r in rows))]

    # ASCII helpers
    def make_separator() -> str:
        return "+" + "+".join("─" * (w + 2) for w in col_widths) + "+"

    def make_row(row: list[str]) -> str:
        return "│" + "│".join(f" {row[i] if i < len(row) else ''}".ljust(w + 2) for i, w in enumerate(col_widths)) + "│"

    # Build ASCII table
    ascii_table = [make_separator()]
    for row in rows:
        ascii_table.append(make_row(row))
        ascii_table.append(make_separator())

    return ascii_table


def starts_with_html(text: str) -> bool:
    """
    Determines if a string starts with common HTML structures.

    The function is case-insensitive and ignores leading whitespace.
    It looks for:
    1. The HTML DOCTYPE declaration: <!DOCTYPE ...>
    2. An opening <html> tag: <html>
    3. Any opening tag starting with < followed by a letter: <p>, <div>, <h1>, etc.

    Args:
        text: The string to be checked.

    Returns:
        True if the string starts with a common HTML structure, False otherwise.
    """
    # 1. Strip leading whitespace to handle cases like: "  <!DOCTYPE html>..."
    cleaned_text = text.lstrip()

    # 2. Define a regular expression pattern
    # r'^': Start of the string
    # ( ... ): Grouping the possible matches
    #   '<!DOCTYPE': Matches the start of the DOCTYPE declaration (case-insensitive)
    #   '|': OR operator
    #   '<[a-z]': Matches an opening tag starting with a letter (e.g., '<p', '<div', '<h1')

    # We use re.IGNORECASE to handle variations like "<html>", "<HTML>", or "<p>"
    html_pattern = re.compile(r"^(<!DOCTYPE|<[a-z])", re.IGNORECASE)

    # 3. Check for a match at the beginning of the cleaned string
    return bool(html_pattern.match(cleaned_text))


class TranslatedLabel(ctk.CTkLabel):
    """Translate text if we have set the language"""

    def __init__(self, *args: complex, text: str = "", **kwargs: complex) -> None:
        """Rewturn translated tyext if translation is available"""
        translated_text = PrimeItems._(text) if hasattr(PrimeItems, "_") else text
        super().__init__(*args, text=translated_text, **kwargs)
