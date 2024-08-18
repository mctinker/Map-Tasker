"""GUI Window Classes and Definitions"""

#! /usr/bin/env python3

#                                                                                      #
# userwins: provide GUI window functions                                               #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
from __future__ import annotations

import contextlib
import os
import random
import time
import webbrowser
from tkinter import TclError, ttk

import customtkinter as ctk
from PIL import Image, ImageTk

from maptasker.src.getids import get_ids
from maptasker.src.guiutils import (
    add_button,
    add_checkbox,
    add_label,
    add_logo,
    add_option_menu,
    display_analyze_button,
    get_monospace_fonts,
    make_hex_color,
    reset_primeitems_single_names,
    update_tasker_object_menus,
)
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import LLAMA_MODELS, OPENAI_MODELS, logger

# Set up for access to icons
CURRENT_PATH = os.path.dirname(os.path.realpath(__file__))
ICON_DIR = os.path.join(CURRENT_PATH, f"..{PrimeItems.slash}assets", "icons")
ICON_PATH = {
    # "close": (os.path.join(ICON_DIR, "close_black.png"), os.path.join(ICON_DIR, "close_white.png")),
    # # "images": list(os.path.join(ICON_DIR, f"image{i}.jpg") for i in range(1, 4)),
    # "eye1": (os.path.join(ICON_DIR, "eye1_black.png"), os.path.join(ICON_DIR, "eye1_white.png")),
    # "eye2": (os.path.join(ICON_DIR, "eye2_black.png"), os.path.join(ICON_DIR, "eye2_white.png")),
    # "info": os.path.join(ICON_DIR, "info.png"),
    # "warning": os.path.join(ICON_DIR, "warning.png"),
    # "error": os.path.join(ICON_DIR, "error.png"),
    # "left": os.path.join(ICON_DIR, "left.png"),
    # "right": os.path.join(ICON_DIR, "right.png"),
    # "warning2": os.path.join(ICON_DIR, "warning2.png"),
    # "loader": os.path.join(ICON_DIR, "loader.gif"),
    # "icon": os.path.join(ICON_DIR, "icon.png"),
    "arrow": os.path.join(ICON_DIR, "arrow.png"),
    # "image": os.path.join(ICON_DIR, "image.png"),
}


class CTkTreeview(ctk.CTkFrame):
    """Class to handle the Treeview

    Args:
        ctk (ctk): Our GUI framework
    """

    def __init__(self, master: any, items: list) -> None:
        """Function:
        def __init__(self, master: any, items: list):
            Initializes a Treeview widget with a given master and list of items.
            Parameters:
                master (any): The parent widget for the Treeview.
                items (list): A list of items to be inserted into the Treeview.
            Returns:
                None.
            Processing Logic:
                - Sets up the Treeview widget with appropriate styles and bindings.
                - Inserts the given items into the Treeview.

        tkinter treeview configurable items:
            ttk::style configure Treeview -background color
            ttk::style configure Treeview -foreground color
            ttk::style configure Treeview -font namedfont
            ttk::style configure Treeview -fieldbackground color
            ttk::style map Treeview -background \
                [list selected color]
            ttk::style map Treeview -foreground \
                [list selected color]
            ttk::style configure Treeview -rowheight [expr {[font metrics namedfont -linespace] + 2}]
            ttk::style configure Heading -font namedfont
            ttk::style configure Heading -background color
            ttk::style configure Heading -foreground color
            ttk::style configure Heading -padding padding
            ttk::style configure Item -foreground color
            ttk::style configure Item -focuscolor color
        """
        self.root = master
        self.items = items
        super().__init__(self.root)

        self.grid_columnconfigure(0, weight=1)

        # Label widget
        our_label = """
Drag the bottom of the window to expand as needed.\n
Click item and scroll mouse-wheel/trackpad\nas needed to go up or down.
        """
        self.label = ctk.CTkLabel(master=self, text=our_label, font=("", 12))
        self.label.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        # Basic appearance for text, foreground and background.
        self.bg_color = self.root._apply_appearance_mode(ctk.ThemeManager.theme["CTkFrame"]["fg_color"])  # noqa: SLF001
        self.text_color = self.root._apply_appearance_mode(  # noqa: SLF001
            ctk.ThemeManager.theme["CTkLabel"]["text_color"],
        )
        self.selected_color = self.root._apply_appearance_mode(  # noqa: SLF001
            ctk.ThemeManager.theme["CTkButton"]["fg_color"],
        )

        # Set up the style/theme
        self.tree_style = ttk.Style(self)
        self.tree_style.theme_use("default")

        # Get the icons to be used in the Tree view.
        self.im_open = Image.open(ICON_PATH["arrow"])
        self.im_close = self.im_open.rotate(90)
        self.im_empty = Image.new("RGBA", (15, 15), "#00000000")

        self.img_open = ImageTk.PhotoImage(self.im_open, name="img_open", size=(15, 15))
        self.img_close = ImageTk.PhotoImage(self.im_close, name="img_close", size=(15, 15))
        self.img_empty = ImageTk.PhotoImage(self.im_empty, name="img_empty", size=(15, 15))

        # Arrow element configuration
        with contextlib.suppress(TclError):  # Don't throw error if the element already exists.  Just reuse it.
            self.tree_style.element_create(
                "Treeitem.myindicator",
                "image",
                "img_close",
                ("user1", "!user2", "img_open"),
                ("user2", "img_empty"),
                sticky="w",
                width=15,
                height=15,
            )

        # Treeview configuration of the treeview
        self.tree_style.layout(
            "Treeview.Item",
            [
                (
                    "Treeitem.padding",
                    {
                        "sticky": "nsew",
                        "children": [
                            ("Treeitem.myindicator", {"side": "left", "sticky": "nsew"}),
                            ("Treeitem.image", {"side": "left", "sticky": "nsew"}),
                            (
                                "Treeitem.focus",
                                {
                                    "side": "left",
                                    "sticky": "nsew",
                                    "children": [("Treeitem.text", {"side": "left", "sticky": "nsew"})],
                                },
                            ),
                        ],
                    },
                ),
            ],
        )

        self.tree_style.configure(
            "Treeview",
            background=self.bg_color,
            foreground=self.text_color,
            fieldbackground=self.bg_color,
            borderwidth=10,  # Define a border around tree of 10 pixels.
            font=("", 12),
        )

        self.tree_style.map(
            "Treeview",
            background=[("selected", self.bg_color)],
            foreground=[("selected", self.selected_color)],
        )
        self.root.bind("<<TreeviewSelect>>", lambda event: self.root.focus_set())  # noqa: ARG005

        # Define the frame for the treeview
        self.treeview = ttk.Treeview(self, show="tree", height=50, selectmode="browse")

        # Define the width of the column into which the tree will be placed.
        self.treeview["columns"] = [0]
        # self.treeview.column(0, stretch=0, anchor="w", width=150, minwidth=150)
        # To configure the tree column, call this with column = “#0”
        self.treeview.column("#0", stretch=0, anchor="w", width=300, minwidth=200)

        self.treeview.grid(row=1, column=0, padx=10, pady=10, sticky="w")

        # Add items to the tree
        self.insert_items(self.items)

        # Catch window resizing
        self.bind("<Configure>", self.on_resize)

    # Text window was resized.
    def on_resize(self, event: dict) -> None:  # noqa: ARG002
        """
        Resizes the Diagram window based on the event width and height.

        Args:
            event (any): The event object containing the width and height of the window.

        Returns:
            None: This function does not return anything.

        Raises:
            None: This function does not raise any exceptions.

        This function is called when the window is resized. It retrieves the current window position from `self.master.master.{view}_window_position`,
        splits it into width, height, and x and y coordinates. It then updates the window geometry with the new width, height, and x and y coordinates
        based on the event width and height.
        """

        position_key = "tree_window_position"

        # Get the current window position
        window_position = self.root.wm_geometry()
        # Set the 'view' new window position in our GUI self.
        setattr(self.master.master, position_key, window_position)

    # Inset items into the treeview.
    def insert_items(self, items: list, parent="") -> None:  # noqa: ANN001
        """Inserts items into a treeview.
        Parameters:
            items (list): List of items to be inserted.
            parent (str): Optional parent item for the inserted items.
        Returns:
            None: Does not return anything.
        Processing Logic:
            - Inserts items into treeview.
            - If item is a dictionary, insert with id.
            - If item is not a dictionary, insert without id."""
        for item in items:
            if isinstance(item, dict):
                the_id = self.treeview.insert(parent, "end", text=item["name"].ljust(50))
                with contextlib.suppress(KeyError):
                    self.insert_items(item["children"], the_id)
            else:
                self.treeview.insert(parent, "end", text=item)

    # Tree view window is getting closed
    def on_closing(self) -> None:
        """Save the window position and close the window."""
        self.master.tree_window_position = self.wm_geometry()
        self.destroy()


# Define the Text window
class TextWindow(ctk.CTkToplevel):
    """Define our top level window for the analysis view."""

    def __init__(
        self,
        window_position: str | None = None,
        title: str | None = None,
        *args,  # noqa: ANN002
        **kwargs,  # noqa: ANN003
    ) -> None:
        """Creates a window for the configuration diagram.
        Parameters:
            self (object): The object being passed.
            *args (any): Additional arguments.
            **kwargs (any): Additional keyword arguments.
        Returns:
            None: This function does not return anything.
        Processing Logic:
            - Initialize label widget.
            - Pack label widget with padding.
            - Set label widget text."""
        super().__init__(*args, **kwargs)

        # Position the widget
        try:
            self.geometry(window_position)
            # window_ shouldn't be in here.  If it is, pickle file is corrupt.
            window_position = window_position.replace("window_", "")
            work_window_geometry = window_position.split("x")
            self.master.text_window_width = int(work_window_geometry[0])
            self.master.text_window_height = work_window_geometry[1].split("+")[0]
        except (AttributeError, TypeError):
            self.master.text_window_position = "600x800+600+0"
            self.master.text_window_width = "600"
            self.master.text_window_height = "800"
            self.geometry(self.master.text_window_position)

        # Display the title.
        self.title(f"{title} - Drag window to desired position and rerun the {title} command.")

        # Save the window position on closure
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    # Text window is getting closed.  Save the window position.
    def on_closing(self) -> None:
        """Save the window position and close the window."""
        window_position = self.wm_geometry()
        title = self.wm_title()
        if "Diagram" in title:
            self.master.diagram_window_position = window_position
        elif "Analysis" in title:
            self.master.ai_analysis_window_position = window_position
        elif "Tree" in title:
            self.master.tree_window_position = window_position
        elif "Map" in title:
            self.master.map_window_position = window_position

        self.destroy()


# Display a Diagram structure
class CTkTextview(ctk.CTkFrame):
    """Class to handle the Treeview

    Args:
        ctk (ctk): Our GUI framework
    """

    def __init__(self, master: any, title: str, the_data: list) -> None:
        """Function:
        def __init__(self, master: any, items: list):
            Initializes a Textview widget with a given master and list of items.
            Parameters:
                master (any): The parent widget for the Textview.
                items (list): A list of items to be inserted into the Textview.
            Returns:
                None.
            Processing Logic:
                - Sets up the ATextview widget with appropriate styles and bindings.
                - Inserts the given items into the Textview.
        """
        self.root = master
        super().__init__(self.root)

        self.grid_columnconfigure(0, weight=1)

        # Basic appearance for text, foreground and background.
        self.textview_bg_color = self.root._apply_appearance_mode(  # noqa: SLF001
            ctk.ThemeManager.theme["CTkFrame"]["fg_color"],
        )
        self.textview_text_color = self.root._apply_appearance_mode(  # noqa: SLF001
            ctk.ThemeManager.theme["CTkLabel"]["text_color"],
        )
        self.selected_color = self.root._apply_appearance_mode(  # noqa: SLF001
            ctk.ThemeManager.theme["CTkButton"]["fg_color"],
        )

        # Set up the style/theme
        self.textview_style = ttk.Style(self)
        self.textview_style.theme_use("default")
        self.title = f"{title} - Drag window to desired position and rerun the {title} command."

        # Recreate text box
        width = getattr(master.master, "text_window_width")
        height = getattr(master.master, "text_window_height")
        # height = str(int(getattr(master.master, "text_window_height")) - 100)
        font = getattr(master.master, "font")
        self.textview_textbox = ctk.CTkTextbox(
            self,
            font=(font, 12),
        )
        self.textview_textbox.grid(row=0, column=0, padx=20, pady=40, sticky="nsew")

        self.textview_textbox.configure(
            height=height,
            width=width,
        )

        # Enable hyperlinks if needed
        self.textview_hyperlink = CTkHyperlinkManager(self.textview_textbox)

        # Get the special fonts
        self.bold_font = ctk.CTkFont(family=PrimeItems.program_arguments["font"], weight="bold", size=12)
        self.italic_font = ctk.CTkFont(family=PrimeItems.program_arguments["font"], size=12, slant="italic")

        # Defile a scollbar
        self.scrollbar = ctk.CTkScrollbar(self)

        # Insert the text with our new message into the text box.
        # fmt: off
        if type(the_data) == str:
            the_data = the_data.split("\n")

        # Process list data (list of lines)
        if type(the_data) !=  dict:
            for num, line in enumerate(the_data):
                text_line = num + 1
                self.textview_textbox.insert(f"{text_line!s}.0", f"{line}\n")

        # Process the Map view (dictionary of lines)
        else:
            self.output_map(the_data)

        # Get rid of the data since we don't need it anymore
        the_data = None

        # Configure the textbox and add label.
        self.textview_textbox.configure(state="normal", wrap="none")  # configure textbox
        # Add label
        self.drag_label = add_label(
                self,
                self,
                f"Drag window to desired position and rerun the {title} command.",
                "Orange",
                12,
                "normal",
                0,
                0,
                10,
                10,
                "n",
        )

        # Set a timer so we can delete the label after a certain amount of time.
        self.after(3000, self.delay_event)  # 3 second timer
        self.textview_textbox.focus_set()

    # Text window was resized.
    def on_resize(self, event: dict) -> None:  # noqa: ARG002
        """
        Resizes the Diagram window based on the event width and height.

        Args:
            event (any): The event object containing the width and height of the window.

        Returns:
            None: This function does not return anything.

        Raises:
            None: This function does not raise any exceptions.

        This function is called when the window is resized. It retrieves the current window position from `self.master.master.{view}_window_position`,
        splits it into width, height, and x and y coordinates. It then updates the window geometry with the new width, height, and x and y coordinates
        based on the event width and height.

        Note: The code snippet provided is incomplete and does not contain the implementation of the function.
        """

        if "Diagram" in self.title:
            position_key = "diagram_window_position"
        elif "Analysis" in self.title:
            position_key = "ai_analysis_window_position"
        elif "Tree" in self.title:
            position_key = "tree_window_position"
        elif "Map" in self.title:
            position_key = "map_window_position"
        else:
            return

        # Get the current window position
        window_position = self.root.wm_geometry()
        # Set the 'view' new window position in our GUI self.
        setattr(self.master.master, position_key, window_position)

    # Output the map view data to the text window.
    def output_map(self, the_data: dict) -> None:
        """
        Outputs the data from the given map data (dictionary) to a text box.

        Args:
            the_data (dict): The dictionary containing the data to output.

        Returns:
            None
        """
        # Iterate through dictionary of lines and insert into textbox
        line_num = 1
        tags = []
        previous_color = "white"
        previous_directory = ""
        previous_value = ""
        char_position = 0

        # Make sure we have the window position set for the progress bar
        if not PrimeItems.program_arguments["map_window_position"]:
            PrimeItems.program_arguments["map_window_position"] = self.master.master.window_position

        # Create a progress bar widget
        self.progress_bar = ProgressbarWindow()
        self.progress_bar.progressbar.configure(width=300, height=30)
        self.progress_bar.progressbar.start()

        # Go through all of the map data and format it accordingly.
        self.process_map_data(
            line_num,
            tags,
            char_position,
            previous_color,
            previous_directory,
            previous_value,
            the_data,
        )

        # Stop the progress bar and destroy the widget
        self.progress_bar.progressbar.stop()
        self.progress_bar.progressbar.destroy()
        self.progress_bar.destroy()

    # Go through all of the map data and format it accordingly.
    def process_map_data(
        self: object,
        line_num: int,
        tags: list,
        char_position: int,
        previous_color: str,
        previous_directory: str,
        previous_value: str,
        the_data: dict,
    ) -> None:
        """
        Process the given map data and output the text lines and colors to a text box.

        Args:
            line_num (int): The current line number.
            tags (list): The list of tags.
            char_position (int): The current character position.
            previous_color (str): The previous color.
            previous_directory (str): The previous directory.
            previous_value (str): The previous value.
            the_data (dict): The dictionary containing the map data.
        """
        max_data = len(the_data)
        tenth_increment = max_data // 10 or 1  # Avoid division by zero

        # Go through the data and format it accordingly.
        for num, (_, value) in enumerate(the_data.items()):
            if num % tenth_increment == 0:
                self.display_progress_bar(max_data, num, tenth_increment)
            # Ignore blank lines
            text = value.get("text", [])
            if text and text[0] == "  \n":
                continue

            # Check if we need to bump the line number
            line_num, char_position = self.check_bump(line_num, char_position, previous_value, value)

            # Check if we need to change the color
            if not value["color"] and value["text"]:
                value["color"] = [previous_color]

            if value["color"]:
                line_num, previous_color, previous_value, tags = self.process_colored_text(
                    value,
                    line_num,
                    previous_color,
                    previous_value,
                    tags,
                )
                # Check if we need to go one level up
                if "Directory    (entries are hotlinks)" in value["text"][0]:
                    line_num, previous_directory, previous_value, char_position = self.one_level_up(
                        line_num,
                        previous_directory,
                        previous_value,
                        char_position,
                    )

            # Process the directory
            elif value.get("directory"):
                if previous_value != "directory":
                    char_position = 0
                char_position, previous_directory, line_num = self.process_directory(
                    value,
                    line_num,
                    previous_directory,
                    char_position,
                )
                previous_value = "directory"

            if self.master.master.debug:
                logger.info(f"Map View Value: {value}")

    def check_bump(self: object, line_num: int, char_position: int, previous_value: str, current_value: dict) -> tuple:
        """
        Check if there is a need to bump the line number and reset the character position based on the previous value and the current value.

        Args:
            line_num (int): The current line number.
            char_position (int): The current character position.
            previous_value (str): The previous value.
            current_value (dict): The current value.

        Returns:
            tuple: Updated line number and character position.
        """
        # Extract relevant fields from the current value dictionary
        current_text = current_value.get("text", [])
        current_directory = current_value.get("directory", False)

        # If the previous value was a directory and the current one isn't, bump the line number
        if previous_value == "directory" and not current_directory:
            # if (
            #     previous_value == "directory" and not current_directory) or (current_text
            #     and previous_value != current_text[0]
            # ):
            line_num += 1
            char_position = 0

        # If we are still within the same directory, increase the character position
        if current_directory and previous_value == "directory":
            char_position += len(current_text[0]) if current_text else 0

        return line_num, char_position

    def one_level_up(
        self: object,
        line_num: int,
        previous_directory: str,
        previous_value: str,
        char_position: int,
    ) -> tuple:
        """
        Moves one level up in the directory hierarchy.

        Args:
            self (object): The instance of the class.
            line_num (int): The current line number.
            previous_directory (str): The previous directory.
            previous_value (str): The previous value.
            char_position (int): The current character position.

        Returns:
            tuple: A tuple containing the updated line number, previous directory, previous value, and character position.
        """
        single_project = PrimeItems.program_arguments["single_project_name"]
        single_profile = PrimeItems.program_arguments["single_profile_name"]
        single_task = PrimeItems.program_arguments["single_task_name"]
        # Don't do anything if we are not doing a single item.
        if not single_project and not single_profile and not single_task:
            return line_num, previous_directory, previous_value, char_position

        value = {}
        # Doing single Project
        if single_project:
            value = {"directory": ["%%", ""]}
        # Doing single Profile
        elif single_profile:
            value = {"directory": ["%%projects", self.find_owning_project(single_profile)]}
        # Doing single Task
        elif single_task:
            single_profile_name = self.find_owning_profile(single_task)
            if not single_profile_name:
                value = {"directory": ["%%projects", self.find_task_owning_project(single_task)]}
            else:
                value = {"directory": ["%%profiles", single_profile_name]}

        # Build the direcetory entry
        char_position, previous_directory, line_num = self.process_directory(
            value,
            line_num,
            previous_directory,
            char_position,
        )
        previous_value = "directory"
        return line_num, previous_directory, previous_value, char_position

    # Find owning Project given a Profile name
    def find_owning_project(self: object, profile_name: str) -> str:
        """
        Find the owning Project given a Profile name.

        Args:
            self (object): The instance of the class.
            profile_name (str): The name of the Profile.

        Returns:
            str: The owning Project name.
        """
        # Get this Profile's pid
        profile_dict = PrimeItems.tasker_root_elements["all_profiles"]
        profile_ids = {value["name"]: key for key, value in profile_dict.items()}
        pid = profile_ids.get(profile_name)

        # Find the owning Project
        if pid:
            projects_dict = PrimeItems.tasker_root_elements["all_projects"]
            for project_name, project_value in projects_dict.items():
                if pid in get_ids(
                    True,
                    project_value["xml"],
                    project_name,
                    [],
                ):
                    return project_name
        return ""

    # Find Task's owning Project
    def find_task_owning_project(self: object, task_name: str) -> str:
        """
        Find the owning project of a task given its name.

        Args:
            self (object): The instance of the class.
            task_name (str): The name of the task.

        Returns:
            str: The name of the owning project, or an empty string if not found.
        """
        all_projects = PrimeItems.tasker_root_elements["all_projects"]
        all_tasks = PrimeItems.tasker_root_elements["all_tasks"]

        for project_key, project_value in all_projects.items():
            project_xml = project_value["xml"]
            task_ids = get_ids(False, project_xml, project_key, [])

            for task_id in task_ids:
                task = all_tasks.get(task_id)
                if task and task["name"] == task_name:
                    return project_value["name"]

        return ""

    # Find the owning Profile given a Task name
    def find_owning_profile(self: object, task_name: str) -> str:
        """
        Find the owning Profile given a Task name.

        This function takes a Task name as input and searches for the corresponding Task ID in the `PrimeItems.tasker_root_elements["all_tasks"]` dictionary. It then iterates over the `PrimeItems.tasker_root_elements["all_projects"]` dictionary to find the Project that contains the Task ID. If a matching Project is found, its name is returned. If no matching Project is found, an empty string is returned.

        Parameters:
            task_name (str): The name of the Task.

        Returns:
            str: The name of the owning Profile, or an empty string if no matching Profile is found.
        """
        # Get this Task's tid
        tid = ""
        for key, value in PrimeItems.tasker_root_elements["all_tasks"].items():
            if value["name"] == task_name:
                tid = key
                break

        # Find the owning Profile
        # Go through all Profiles looking for "mid0" or "mid1" that matches our Task
        if tid:
            for profile in PrimeItems.tasker_root_elements["all_profiles"]:
                profile_value = PrimeItems.tasker_root_elements["all_profiles"][profile]
                mid = profile_value["xml"].find("mid0")
                if mid is not None and mid.text == tid:
                    return profile_value["name"]
                mid = profile_value["xml"].find("mid1")
                if mid is not None and mid.text == tid:
                    return profile_value["name"]
        return ""

    def display_progress_bar(self: object, max_data: int, num: int, tenth_increment: int) -> None:
        """
        Display a progress bar with a specified color based on the progress percentage.

        Args:
            self (object): The instance of the class.
            max_data (int): The maximum value for the progress bar.
            num (int): The current value of the progress bar.
            tenth_increment (int): The increment value for each 10% of progress.

        Returns:
            None: This function does not return anything.
        """
        threshold = num / tenth_increment
        if threshold <= 2:
            progress_color = "red"
        elif threshold <= 4:
            progress_color = "orangered"
        elif threshold <= 6:
            progress_color = "orange"
        elif threshold <= 8:
            progress_color = "limegreen"
        else:
            progress_color = "green"

        self.progress_bar.progressbar.set(num / max_data)
        self.progress_bar.progressbar.configure(progress_color=progress_color)
        self.progress_bar.progressbar.update()
        # Print alert if necessary.
        if (
            self.progress_bar.progressbar.print_alert
            and round(time.time() * 1000) - self.progress_bar.progressbar.start_time > 4000
        ):
            print("You can ignore the error message: IMKClient Stall detected, *please Report*...")
            self.progress_bar.progressbar.print_alert = False

    def process_colored_text(
        self: object,
        value: dict,
        line_num: int,
        previous_color: str,
        previous_value: str,
        tags: list,
    ) -> tuple:
        """
        Process colored text and output the text lines and colors to a text box.

        Args:
            self (object): The instance of the class.
            value (dict): A dictionary containing the text and color information.
            line_num (int): The current line number.
            previous_color (str): The previous color.
            previous_value (str): The previous value.
            tags (list): The list of tags.

        Returns:
            tuple: A tuple containing the updated line number, previous color, previous value, and tags.

        This function processes colored text and outputs the text lines and colors to a text box.
        It handles special cases of directory and "Projects..." lines by adding extra newlines.
        It outputs each text line and color in the data 'value' entry. It also updates the line number,
        previous color, previous value, and tags accordingly.
        """
        # line_num += 1  # For a bump in line number since we are adding a '\n' to text

        # Handle special case of Directory and "Projects....." etc. lines by adding ane xtra '\n'
        if value["text"][0] == "Directory\n":
            value["text"] = ["Directory    (entries are hotlinks)\n"]
        # \nn indicates a directory header (e.g. Projects...........)
        elif value["text"][0].startswith("\nn"):
            save_text = value["text"][0][2:]
            save_color = value["color"]
            value["text"] = "\n\n"
            previous_color = self.output_map_text_lines(value, line_num, tags, previous_color)
            line_num += 1
            value["text"] = save_text
            value["color"] = save_color

        # Output the each text line and color in the data 'value' entry.
        previous_color = self.output_map_text_lines(value, line_num, tags, previous_color)
        line_num += 1
        previous_value = "color"

        return line_num, previous_color, previous_value, tags

    def process_directory(self, value: dict, line_num: int, previous_directory: str, char_position: int) -> tuple:
        """
        A function that processes a directory based on the given values.

        Parameters:
            - self: The object itself.
            - value: A dictionary containing information about the directory.
            - line_num: An integer representing the line number.
            - previous_directory: The previous Tasker type ("projects", "profiles", etc.) that was processed.
            - char_position: An integer representing the character position in the text line.

        Returns:
            char_position: An integer representing the updated character position in the text line.
            previous_directory: The previous Tasker type ("projects", "profiles", etc.) that was processed.
            line_num: An integer representing the updated line number.

        Note: Clicking on a hotlink will open the corresponding Tasker object via a call to self.remap_single_item.
                In effect, mapit is re-invoked for the corresponding Tasker object that was clicked on.
        """
        spacing = 40
        columns = 3

        # We dont't support Scenes or Grand Totals hotlinks (yet)
        if value["directory"][0] in ("scenes", "grand", "</td"):
            char_position = 0
            return char_position, previous_directory, line_num

        # If we have a change in directory Tasker object, reset positon to 0.
        if previous_directory != value["directory"][0]:
            char_position = 0

        # Setup the info to insert into the text box.
        line_num_str = str(line_num)
        hotlink_name = value["directory"][1]

        # Check for special "Up One Level" hotlink and modify the text to be displayed if it is.
        if value["directory"][0][:2] == "%%":
            value["directory"][0] = value["directory"][0][2:]

            name_to_go_up = "entire configuration" if value["directory"][1] == "" else value["directory"][1]
            object_name = "" if value["directory"][1] == "" else value["directory"][0][:-1].capitalize()

            hotlink_name = f"Up One Level to {object_name}: {name_to_go_up}"
            name_to_insert = hotlink_name
            link = [value["directory"][0], value["directory"][1]]
            spacer = ""
        else:
            spacer = "\n" if char_position == spacing * columns - spacing else ""
            name_to_insert = f'{hotlink_name.ljust(spacing, " ")}{spacer}'
            link = [value["directory"][0], hotlink_name]

        # Add the text to the text box.  The tag is obtained from call to self.textview_hyperlink.add.
        tag_id = self.textview_hyperlink.add(link)
        self.textview_textbox.insert(
            f"{line_num_str}.{char_position!s}",
            name_to_insert,
            tag_id,
        )

        # Add color to the tag
        self.textview_textbox.tag_config(
            tag_id[1],
            background=make_hex_color(self.master.master.color_lookup["background_color"]),
        )

        # Set up for next time through...
        char_position += spacing
        if char_position == spacing * columns:
            line_num += 1
            char_position = 0

        previous_directory = value["directory"][0]

        return char_position, previous_directory, line_num

    def output_map_text_lines(self, value: dict, line_num: int, tags: list, previous_color: str) -> str:
        """
        A function that outputs text lines with specified colors and formatting to a text box for the value passed in.
        Parameters:
            - value: A dictionary 'value' containing text, color, and highlights information.
            - line_num: An integer representing the line number.
            - tags: A list of tags for text formatting.
            - previous_color: A string representing the previous color used.
        Returns:
            previous_color: A string representing the previous color used.
        """
        spaces = " " * 20  # Approximate amount of spacing prior to a Task parameter.
        # Go through all of the text/color combinations
        char_position = 0
        line_num_str = str(line_num)
        previous_color = ""
        go_to_top = False

        # Loop through all of the text strings.
        for num, message in enumerate(value["text"]):
            # Get rid of double blank lines
            new_message = message.replace("\n\n", "\n")

            # Ignore extra blank line after "[⛔ DISABLED]" text...it is following a disabled "Profile:"" line.
            if new_message == "      ":
                continue

            # Remove "Go to top" from the end of the message if it is there.  This is for "Go to top" hyperlink code below., which must follow the text insertion code.
            if "Go to top" in new_message:
                new_message = new_message.replace("Go to top", "")
                go_to_top = True

            # Add a couple more blanks to the beginning of each line if we are doing pretty.
            if self.master.master.pretty and new_message[0:20] == spaces:
                new_message = f"  {new_message}"

            # Add line number to output message
            # if self.master.master.debug:
            #     new_message = f"{line_num_str} {new_message}"

            # Build the tag to use and make sure it is unique
            char_position_str = str(char_position)
            tag_id = f"{line_num_str}{char_position_str}"
            while tag_id in tags:
                tag_id = f"{tag_id}{random.randint(100, 999)}"  # noqa: S311
            tags.append(tag_id)

            # Determine if this is the last item in the list of text elements and add a new line if it is.
            line_to_insert = (
                f"{new_message}\n" if new_message == value["text"][-1] and "\n" not in new_message else new_message
            )

            # Insert the text to the text box.  The tag is obtained from call to self.textview_hyperlink.add.
            self.textview_textbox.insert(f"{line_num_str}.{char_position_str}", f"{line_to_insert}", tag_id)
            self.textview_textbox.tag_add(
                tag_id,
                f"{line_num_str}.{char_position_str}",
                f"{line_num_str}.{len(line_to_insert)!s}",
            )
            # fmt: on
            char_position += len(line_to_insert)  # Point to next position for text

            # Go to top in the text line.  Add a hyperlink.
            # Note: This must fall after the text is inserted into the text box.
            if go_to_top:

                # The following is debug code.
                # Position just after the last character in the buffer.
                # end_line_col = self.textview_textbox.index("end")
                # Get contents of last line in text box.
                # td = self.textview_textbox.get("end-1c linestart", "end-1c lineend")
                # Get the entire contents of the text box into a list
                # ty = self.textview_textbox.get("1.0", "end").rstrip()
                # tz = ty.split("\n")

                # Get the total number of lines in the text box
                line_count = int(self.textview_textbox.index("end-1c").split(".")[0])
                # Get the contents of the last line in the text box.
                line_pos = str(line_count - 1)
                tx = self.textview_textbox.get(f"{line_pos}.0", "end-1c")
                # If "Go to top" is in the line, then start at position 1.  Otherwise, start at end of text.
                gototop_char_position = 1 if "Go to top" in tx else len(tx)

                # If the position is in the first character, then we need to rely on line_num ass the current line of text.
                if gototop_char_position == 1:
                    line_pos = line_num_str
                    tx = self.textview_textbox.get(f"{line_num}.0", "end-1c")
                    gototop_char_position = len(tx)

                # Add the hyperlink.
                # The tag is obtained from call to self.textview_hyperlink.add.
                link = ["gototop", "Go to top"]
                top_tag_id = self.textview_hyperlink.add(link)
                # Add the text to the text box.
                # For some reason, we have to back up 2 lines to get the right position.
                self.textview_textbox.insert(
                    f"{line_pos}.{gototop_char_position!s}",
                    "Go to top",
                    top_tag_id,
                )
                # Add color to the tag
                self.textview_textbox.tag_config(
                    top_tag_id[1],
                    background=make_hex_color(self.master.master.color_lookup["background_color"]),
                )
                go_to_top = False

                # Display the text
                # inputvalue = self.textview_textbox.get("1.0", "end-1c")
                # print(inputvalue)
                # exit()

            # Do color and name highlighting (bold/italicize/underline/highlight).  Use previous color if it doesn't exist.
            # Have to handle background color separately
            color = previous_color
            if "Color for Background set to" in line_to_insert or "highlighted for visibility" in line_to_insert:
                color = "White"
            # Determine the proper color and highlighting to use.
            else:
                color = self.output_map_colors_highlighting(
                    value,
                    tags,
                    previous_color,
                    num,
                    line_to_insert,
                    tag_id,
                    color,
                )

            # Save previous color and text in case we need to use it.
            previous_color = color

            # Set the foreground and background colors
            self.textview_textbox.tag_config(
                tag_id,
                foreground=color,
                background=make_hex_color(self.master.master.color_lookup["background_color"]),
            )

        return previous_color

    def output_map_colors_highlighting(
        self,
        value: dict,
        tags: list,
        previous_color: str,
        num: int,
        message: str,
        tag_id: str,
        color: str,
    ) -> str:
        """
        A function to apply color highlighting to text based on the specified configurations.

        Parameters:
            - self: the object instance
            - value: a dictionary containing the value to be highlighted
            - tags: a list of tags to be applied
            - previous_color: a string representing the previous color used
            - num: an integer representing a specific number
            - message: a string containing the message to be highlighted
            - tag_id: a string representing the tag ID
            - color: a string representing the color

        Returns:
            - color (string): the color to be applied
        """
        # Set up the highlighting elements
        highlight_configurations = {
            "bold": {"font": self.bold_font},
            "italic": {"font": self.italic_font},
            "underline": {"underline": True},
            "mark": {"background": PrimeItems.colors_to_use["highlight_color"]},
        }

        # Set the line number accordingly.  Push it back if there is a direclty due to extra '\n's
        # line_num_str = str(line_num - 3) if PrimeItems.program_arguments["directory"] else str(line_num)

        # Look for special string highlighting in value (bold, italic, underline, highlight)
        with contextlib.suppress(KeyError):
            if num == 0 and value["highlights"]:
                for highlight in value["highlights"]:
                    # Go through all highlights for this line/value
                    highlights = highlight.split(",")
                    start_position = message.find(highlights[1])
                    end_position = start_position + len(highlights[1])
                    # print(f"{line_num_str}.{start_position} - {line_num_str}.{end_position}")
                    highlight_type = highlights[0]
                    if highlight_type in highlight_configurations:

                        # Found a highlight type.
                        new_tag = f"{tag_id}{highlight_type}"
                        tags.append(new_tag)

                        # Get the total number of lines in the text box
                        line_count = int(self.textview_textbox.index("end-1c").split(".")[0])

                        # If a new line proceeds the highlighted item, then use the current line.  Otherwise use the previous line.
                        tx = self.textview_textbox.get(f"{line_count-1!s}.0", "end-1c")
                        t1 = tx.find("\n   ")
                        line_to_highlight = str(line_count) if tx[0:1] == "\n" or t1 != -1 else str(line_count - 1)

                        # Add the tag
                        self.textview_textbox.tag_add(
                            new_tag,
                            f"{line_to_highlight}.{start_position!s}",
                            f"{line_to_highlight}.{end_position!s}",
                        )
                        self.textview_textbox.tag_config(new_tag, **highlight_configurations[highlight_type])

                        # Add a line number to the output for debugging purposes.
                        # if self.master.master.debug:
                        #     line_num = int(line_num_str) - 2
                        #     print("line number", line_num, "start position", start_position, "end position", end_position)
                        #     self.textview_textbox.insert(
                        #         f"{line_num!s}.{end_position+1!s}", "<< Here is a highlight >>", tag_id,
                        #     )

        # Now color the text.
        try:
            color = self.master.master.color_lookup.get(f'{value["color"][num]}')

            # If color is None, then it wasn't found in the lookup table.  It is a raw color name.
            if color is None and value["color"][num] != "n/a":
                color = value["color"][num]
            elif color is None and value["color"][num] == "n/a" or "-" in color:
                color = previous_color
            else:
                previous_color = color
        except IndexError:
            color = previous_color

        # Deal with a hex value for color
        if color and color.isdigit():
            color = f"#{color}"
        return color

    def delay_event(self) -> None:
        """
        A method that handles the delay event for the various text views.
        It deletes the label after a certain amount of time.
        """
        self.drag_label.destroy()
        # Catch window resizing
        self.bind("<Configure>", self.on_resize)

    def new_tag_config(self, tagName: str, **kwargs: list) -> object:  # noqa: N803
        """
        A function to override the CustomTkinter tag configuration to allow a font= argument.

        Parameters:
            - self: The object instance.
            - tagName: The name of the tag to be configured.
            - **kwargs: Additional keyword arguments for configuring the tag.

        Returns:
            The result of calling tag_config on the _textbox attribute with the provided tagName and keyword arguments.
        """
        return self._textbox.tag_config(tagName, **kwargs)

    ctk.CTkTextbox.tag_config = new_tag_config


# Define the Progressbar window
class ProgressbarWindow(ctk.CTk):
    """Define our top level window for the Progressbar view."""

    def __init__(self) -> None:
        """Intialize our top level window for the Progressbar view."""
        super().__init__()

        # Position the widget over our main GUI
        self.geometry(PrimeItems.program_arguments["map_window_position"])
        self.value = 0
        self.progressbar = ctk.CTkProgressBar(self)
        self.title("Map Progress")
        self.progressbar.pack(pady=20)
        self.progressbar.set(self.value)
        self.progressbar.start_time = round(time.time() * 1000)
        self.progressbar.print_alert = True


# Define the Ai Popup window
class PopupWindow(ctk.CTk):
    """Define our top level window for the Popup view."""

    def __init__(
        self,
        title: str = "",
        message: str = "",
        exit_when_done: bool = False,
        delay: int = 500,
        *args,  # noqa: ANN002
        **kwargs,  # noqa: ANN003
    ) -> None:
        """
        Initializes the PopupWindow object.

        Parameters:
            title (str): The title of the popup window. Default is an empty string.
            message (str): The message to be displayed in the popup window. Default is an empty string.
            exit_when_done (bool): Whether the popup window should exit when done. Default is False.
            delay (int): The delay in milliseconds before the popup window exits. Default is 500.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            None
        """
        super().__init__(*args, **kwargs)

        # Position the widget over our main GUI
        self.geometry(PrimeItems.program_arguments["window_position"])

        self.title(title)

        self.grid_columnconfigure(0, weight=1)

        # Set popup window wait time to .5 seconds, after which popup_button_event will be called.
        if exit_when_done:
            self.after(delay, self.popup_button_event)

        # Label widget
        our_label = message
        self.text = ""
        self.count = 0
        self.Popup_label = ctk.CTkLabel(master=self, text=self.text, font=("", 24), text_color="turquoise")
        self.Popup_label.grid(row=0, column=0, padx=0, pady=10, sticky="n")

        # Basic appearance for text, foreground and background.
        self.Popup_bg_color = self._apply_appearance_mode(ctk.ThemeManager.theme["CTkFrame"]["fg_color"])
        self.Popup_text_color = self._apply_appearance_mode(
            ctk.ThemeManager.theme["CTkLabel"]["text_color"],
        )
        self.selected_color = self._apply_appearance_mode(
            ctk.ThemeManager.theme["CTkButton"]["fg_color"],
        )

        # Set up the style/theme
        self.Popup_style = ttk.Style(self)
        self.Popup_style.theme_use("default")

        # Animate the text so it is more visable
        def slider() -> None:
            """
            Animates the text on the Popup_label widget by gradually displaying each character from the `our_label` string.

            This function is called recursively using the `after` method to create a sliding effect. It checks if the current index `count` has reached the length of `our_label`. If it has, it resets the `count` to -1 and clears the `text` variable. If not, it appends the character at the current index to the `text` variable and updates the `Popup_label` widget with the new text. The `count` is incremented and the `slider` function is called again after a delay of 5 milliseconds.

            Parameters:
                None

            Returns:
                None
            """
            if self.count >= len(our_label):
                self.count = -1
                self.text = ""
                return
            self.text = self.text + our_label[self.count]
            self.Popup_label.configure(text=self.text)
            self.count += 1
            self.after(5, slider)

        # Set the focus on our popup window and start the animation.
        self.Popup_label.focus_set()
        slider()

    # The "after" n second timer tripped from popup window.  Close the window.
    # Note: rungui will have already completely run by this time.
    def popup_button_event(self) -> None:
        """
        Define the behavior of the popup button event function.  Close the window and exit.
        """
        get_rid_of_window(self, delete_all=False)


# Hyperlink in textbox support
class CTkHyperlinkManager:
    """
    Modified class for implementing hyperlink in CTkTextbox
    """

    def __init__(self, master: object, text_color: str = "#82c7ff") -> None:
        """
        Initializes the CTkHyperlinkManager class.

        Args:
            master (tk.Text): The master widget.
            text_color (str, optional): The color of the hyperlink text. Defaults to "#82c7ff".

        Returns:
            None
        """
        self.text = master
        self.text.tag_config("hyper", foreground=text_color, underline=0)
        self.text.tag_bind("hyper", "<Enter>", self._enter)
        self.text.tag_bind("hyper", "<Leave>", self._leave)
        self.text.tag_bind("hyper", "<Button-1>", self._click)
        self.links = {}

    def add(self, link: str) -> tuple:
        """
        Adds a hyperlink to the CTkHyperlinkManager.

        Args:
            link (str): The hyperlink to add.


        Returns:
            tuple: A tuple containing the type of link ("hyper") and the tag of the link.
        """
        tag = "hyper-%d" % len(self.links)
        self.links[tag] = link
        return "hyper", tag

    def _enter(self, event: object) -> None:  # noqa: ARG002
        """
        Set the cursor to a hand pointer when the mouse enters the text widget.

        Args:
            event (object): The event object.

        Returns:
            None
        """
        self.text.configure(cursor="hand2")

    def _leave(self, event: object) -> None:  # noqa: ARG002
        """
        Set the cursor to the default cursor when the mouse leaves the text widget.

        Args:
            event (object): The event object.

        Returns:
            None
        """
        self.text.configure(cursor="xterm")

    def _click(self, event: object) -> None:
        """
        Handle the click event on the text widget.

        Args:
            event (object): The click event object.

        Returns:
            None: This function does not return anything.

        This function is called when the user clicks on the text widget. It iterates over the tags of the current
        selection and checks if any of them start with "hyper-". If a tag starting with "hyper-" is found, it opens
        the corresponding URL using the `webbrowser.open()` function. The function then returns, ending the execution.

        Note: This function assumes that the `text` attribute of the class instance is a `ctk.Text` widget and
        the `links` attribute is a dictionary mapping tag names to URLs.
        """
        for tag in self.text.tag_names(ctk.CURRENT):
            if tag.startswith("hyper-"):
                link = self.links[tag]
                if isinstance(link, list):
                    # Reset text to line 1?
                    if link[0] == "gototop":
                        self.text.master.textview_textbox.see("1.0")
                    else:
                        # Remap single Project/Profile/Task
                        action, name = link
                        guiself = event.widget.master.master.root.master
                        self.remap_single_item(action, name, guiself)
                else:
                    webbrowser.open(link)
                return

    # The user has clicked on a hotlink.  Get the item clicked and remap using only that single item.
    def remap_single_item(self, action: str, name: str, guiself: ctk) -> None:
        """
        Remap with single item based on action type.

        Args:
            action (str): The type of action to perform (e.g., 'projects', 'profiles', 'tasks').
            name (str): The name of the item to remap.
            guiself (ctk): The GUI self reference.

        Returns:
            None: This function does not return anything.
        """
        if action in ("scenes", "grand"):
            nogo_name = "Grand Totals" if action == "grand" else "Scene"
            guiself.display_message_box(f"'{nogo_name}' hotlinks are not working yet.", "Orange")
        else:
            # Reset all names
            reset_primeitems_single_names()
            guiself.single_project_name = ""
            guiself.single_profile_name = ""
            guiself.single_task_name = ""
            # Set up for single item
            PrimeItems.program_arguments[f"single_{action}_name"] = name
            single_name_parm = action[0 : len(action) - 1]
            # Update self.single_xxx_name
            setattr(guiself, f"single_{single_name_parm}_name", name)
            # Reset single item menus
            update_tasker_object_menus(guiself, get_data=False)
            # Remap it.
            guiself.remapit(clear_names=False)


# Save the positition of a window
def save_window_position(window: CTkTextview) -> None:
    """
    Saves the window position by getting the geometry of the window.

    Args:
        window: The CTkTextview window to save the position of.

    Returns:
        window position or "" if no window
    """
    with contextlib.suppress(Exception):
        if window is not None:
            return window.wm_geometry()
    return ""


# Initialize the GUI (_init_ method)
def initialize_gui(self) -> None:  # noqa: ANN001
    """Initializes the GUI by initializing variables and adding a logo.
    Parameters:
        - self (class): The class object.
    Returns:
        - None: Does not return anything.
    Processing Logic:
        - Calls initialize_variables function.
        - Calls add_logo function."""
    initialize_variables(self)
    add_logo(self)


# Initialize the GUI varliables (e..g _init_ method)
def initialize_variables(self) -> None:  # noqa: ANN001
    """
    Initialize variables for the MapTasker Runtime Options window.
    """
    PrimeItems.program_arguments["gui"] = True
    self.ai_analysis = None
    self.ai_analysis_window = None
    self.ai_analysis_window_position = ""
    self.ai_apikey = None
    self.ai_missing_module = None
    self.ai_model = ""
    self.ai_popup_window_position = ""
    self.ai_prompt = None
    self.all_messages = {}
    self.android_file = ""
    self.android_ipaddr = ""
    self.android_port = ""
    self.appearance_mode = None
    self.bold = None
    self.clear_messages = False
    self.color_labels = None
    self.color_lookup = None
    self.color_text_row = None
    self.color_window_position = ""
    self.conditions = None
    self.debug = None
    self.default_font = ""
    self.diagramview = False
    self.diagram_window_position = ""
    self.diagramview_window = None
    self.display_detail_level = None
    self.everything = None
    self.extract_in_progress = False
    self.exit = None
    self.fetched_backup_from_android = False
    self.file = None
    self.first_time = True
    self.font = None
    self.go_program = None
    self.gui = True
    self.guiview = False
    self.highlight = None
    self.indent = None
    self.italicize = None
    self.list_files = False
    self.map_limit = 10000
    self.map_window_position = ""
    self.mapview_window = None
    self.named_item = None
    self.outline = False
    self.preferences = None
    self.pretty = False
    self.rerun = None
    self.reset = None
    self.restore = False
    self.runtime = False
    self.save = False
    self.single_profile_name = None
    self.single_project_name = None
    self.single_task_name = None
    self.taskernet = None
    self.title("MapTasker Runtime Options")
    self.tree_window_position = ""
    self.treeview_window = None
    self.twisty = None
    self.underline = None
    self.window_position = None

    # configure grid layout (4x4).  A non-zero weight causes a row or column to grow if there's extra space needed.
    # The default is a weight of zero, which means the column will not grow if there's extra space.
    self.grid_columnconfigure(1, weight=1)
    self.grid_columnconfigure((2, 3), weight=0)  # Columns 2 and 3 are not stretchable.
    self.grid_rowconfigure((0, 3), weight=4)  # Divvy up the extra space needed equally amonst the 4 rows: 0-thru-3

    # load and create background image

    # create sidebar frame with widgets on the left side of the window.
    self.sidebar_frame = ctk.CTkFrame(self, width=140, corner_radius=0)
    self.sidebar_frame.configure(bg_color="black")
    self.sidebar_frame.grid(row=0, column=0, rowspan=19, sticky="nsew")
    # Define sidebar background frame with 17 rows
    self.sidebar_frame.grid_rowconfigure(22, weight=1)  # Make anything in rows 20-xx stretchable.


# Define all of the menu elements
def initialize_screen(self: object) -> None:  # noqa: PLR0915
    # Add grid title
    """Initializes the screen with various display options and settings.
    Parameters:
        - self (object): The object to which the function belongs.
    Returns:
        - None: This function does not return any value.
    Processing Logic:
        - Creates a grid title and adds it to the sidebar frame.
        - Defines the first grid / column for display detail level.
        - Defines the second grid / column for checkboxes related to display options.
        - Defines the third grid / column for buttons related to program settings.
        - Creates a textbox for displaying help information.
        - Creates a tabview for setting specific names, colors, and debug options.
        - Defines the fourth grid / column for checkboxes related to debug options.
        - Defines the sixth grid / column for checkboxes related to runtime settings."""

    # Display the frame title
    self.logo_label = add_label(self, self.sidebar_frame, "Display Options", "", 20, "bold", 0, 0, 20, (60, 10), "s")

    # Start first grid / column definitions

    # Display Detail Level
    self.detail_label = add_label(
        self,
        self.sidebar_frame,
        "Display Detail Level:",
        "",
        0,
        "normal",
        1,
        0,
        20,
        (10, 0),
        "",
    )
    self.sidebar_detail_option = add_option_menu(
        self,
        self.sidebar_frame,
        self.event_handlers.detail_selected_event,
        ["0", "1", "2", "3", "4"],
        2,
        0,
        20,
        (10, 10),
        "",
    )
    # Display 'Everything' checkbox
    self.everything_checkbox = add_checkbox(
        self,
        self.sidebar_frame,
        self.event_handlers.everything_event,
        "Just Display Everything!",
        3,
        0,
        20,
        10,
        "w",
        "",
    )

    # Display 'Condition' checkbox
    self.condition_checkbox = add_checkbox(
        self,
        self.sidebar_frame,
        self.event_handlers.condition_event,
        "Display Profile and Task Action Conditions",
        4,
        0,
        20,
        10,
        "w",
        "",
    )

    # Display 'TaskerNet' checkbox
    self.taskernet_checkbox = add_checkbox(
        self,
        self.sidebar_frame,
        self.event_handlers.taskernet_event,
        "Display TaskerNet Info",
        5,
        0,
        20,
        10,
        "w",
        "",
    )

    # Display 'Tasker Preferences' checkbox
    self.preferences_checkbox = add_checkbox(
        self,
        self.sidebar_frame,
        self.event_handlers.preferences_event,
        "Display Tasker Preferences",
        6,
        0,
        20,
        10,
        "w",
        "",
    )

    # Display 'Twisty' checkbox
    self.twisty_checkbox = add_checkbox(
        self,
        self.sidebar_frame,
        self.event_handlers.twisty_event,
        "Hide Task Details Under Twisty",
        7,
        0,
        20,
        10,
        "w",
        "",
    )

    # Display 'directory' checkbox
    self.directory_checkbox = add_checkbox(
        self,
        self.sidebar_frame,
        self.event_handlers.directory_event,
        "Display Directory",
        8,
        0,
        20,
        10,
        "w",
        "",
    )

    # Outline
    self.outline_checkbox = add_checkbox(
        self,
        self.sidebar_frame,
        self.event_handlers.outline_event,
        "Display Configuration Outline",
        9,
        0,
        20,
        10,
        "w",
        "",
    )

    # Pretty Output
    self.pretty_checkbox = add_checkbox(
        self,
        self.sidebar_frame,
        self.event_handlers.pretty_event,
        "Display Prettier Output",
        10,
        0,
        20,
        10,
        "w",
        "",
    )

    # Names: Bold / Highlight / Italicise / Underline
    self.display_names_label = add_label(
        self,
        self.sidebar_frame,
        "Project/Profile/Task/Scene Names:",
        "",
        0,
        "normal",
        11,
        0,
        20,
        10,
        "s",
    )

    # Bold
    self.bold_checkbox = add_checkbox(
        self,
        self.sidebar_frame,
        self.event_handlers.names_bold_event,
        "Bold",
        12,
        0,
        20,
        0,
        "ne",
        "",
    )

    # Italicize
    self.italicize_checkbox = add_checkbox(
        self,
        self.sidebar_frame,
        self.event_handlers.names_italicize_event,
        "italicize",
        12,
        0,
        20,
        0,
        "nw",
        "",
    )

    # Highlight
    self.highlight_checkbox = add_checkbox(
        self,
        self.sidebar_frame,
        self.event_handlers.names_highlight_event,
        "Highlight",
        13,
        0,
        20,
        5,
        "ne",
        "",
    )

    # Underline
    self.underline_checkbox = add_checkbox(
        self,
        self.sidebar_frame,
        self.event_handlers.names_underline_event,
        "Underline",
        13,
        0,
        20,
        5,
        "nw",
        "",
    )

    # Indentation
    self.indent_label = add_label(
        self,
        self.sidebar_frame,
        "If/Then/Else Indentation Amount:",
        "",
        0,
        "normal",
        14,
        0,
        20,
        10,
        "s",
    )

    # Indentation Amount
    self.indent_option = add_option_menu(
        self,
        self.sidebar_frame,
        self.event_handlers.indent_selected_event,
        ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
        15,
        0,
        0,
        (0, 10),
        "n",
    )

    # Screen Appearance: Light / Dark / System
    self.appearance_mode_label = add_label(
        self,
        self.sidebar_frame,
        "Appearance Mode:",
        "",
        0,
        "normal",
        16,
        0,
        0,
        (10, 0),
        "s",
    )

    self.appearance_mode_optionmenu = add_option_menu(
        self,
        self.sidebar_frame,
        self.event_handlers.change_appearance_mode_event,
        ["Light", "Dark", "System"],
        17,
        0,
        0,
        (0, 10),
        "n",
    )

    # Views
    self.appearance_mode_label = add_label(
        self,
        self.sidebar_frame,
        "Views",
        "",
        0,
        "normal",
        18,
        0,
        0,
        0,
        "s",
    )

    # 'Map View' button definition
    self.mapview_button = add_button(
        self,
        self.sidebar_frame,
        "#246FB6",
        "",
        "",
        self.event_handlers.map_event,
        1,
        "Map",
        1,
        19,
        0,
        (20, 0),
        0,
        "sw",
    )
    self.mapview_button.configure(width=50)

    # 'Diagram View' button definition
    self.diagramview_button = add_button(
        self,
        self.sidebar_frame,
        "#246FB6",
        "",
        "",
        self.event_handlers.diagram_event,
        2,
        "Diagram",
        1,
        19,
        0,
        0,
        0,
        "s",
    )
    self.diagramview_button.configure(width=120)

    # 'Tree View' button definition
    self.treeview_button = add_button(
        self,
        self.sidebar_frame,
        "#246FB6",
        "",
        "",
        self.event_handlers.treeview_event,
        2,
        "Tree",
        0,
        19,
        0,
        (0, 40),
        0,
        "se",
    )
    self.treeview_button.configure(width=50)
    #  Query ? button
    self.view_query_button = add_button(
        self,
        self.sidebar_frame,
        "#246FB6",
        ("#0BF075", "#ffd941"),
        "#1bc9ff",
        lambda: self.event_handlers.query_event("view"),
        1,
        "?",
        1,
        19,
        0,
        (300, 0),
        0,
        "s",
    )
    self.view_query_button.configure(width=20)

    # View Map Limit
    self.maplimit_label = add_label(
        self,
        self.sidebar_frame,
        "Map Limit:",
        "",
        0,
        "normal",
        20,
        0,
        30,
        20,
        "nw",
    )
    self.maplimit_optionmenu = add_option_menu(
        self,
        self.sidebar_frame,
        self.event_handlers.maplimit_event,
        ["5000", "10000", "20000", "30000", "Unlimited"],
        20,
        0,
        (20, 0),
        20,
        "n",
    )
    #  Query ? button
    self.maplimit_query_button = add_button(
        self,
        self.sidebar_frame,
        "#246FB6",
        ("#0BF075", "#ffd941"),
        "#1bc9ff",
        lambda: self.event_handlers.query_event("maplimit"),
        1,
        "?",
        1,
        20,
        0,
        (200, 0),
        20,
        "n",
    )
    self.maplimit_query_button.configure(width=20)

    # 'Reset Settings' button definition
    self.reset_button = add_button(
        self,
        self.sidebar_frame,
        "#246FB6",
        "",
        "",
        self.event_handlers.reset_settings_event,
        2,
        "Reset Options",
        1,
        21,
        0,
        20,
        (20, 10),
        "",
    )

    # Start second grid / column definitions

    # Font to use
    self.font_label = add_label(self, self, "Font To Use In Output:", "", 0, "normal", 6, 1, 20, 10, "sw")

    # Get fonts from TkInter
    font_items, res = get_monospace_fonts()
    default_font = [value for value in font_items if "Courier" in value]
    self.default_font = default_font[0]

    # Delete the tkroot obtained by get_monospace_fonts
    if PrimeItems.tkroot is not None:
        del PrimeItems.tkroot
        PrimeItems.tkroot = None
    self.font_optionmenu = add_option_menu(
        self,
        self,
        self.event_handlers.font_event,
        font_items,
        7,
        1,
        20,
        (0, 0),
        "nw",
    )
    self.font_optionmenu.set(res[0])

    # Save settings button
    self.save_settings_button = add_button(
        self,
        self,
        "#6563ff",
        "",
        "",
        self.event_handlers.save_settings_event,
        2,
        "Save Settings",
        1,
        7,
        1,
        20,
        (60, 0),
        "nw",
    )

    # Restore settings button
    self.restore_settings_button = add_button(
        self,
        self,
        "#6563ff",
        "",
        "",
        self.event_handlers.restore_settings_event,
        2,
        "Restore Settings",
        1,
        7,
        1,
        20,
        (98, 0),
        "nw",
    )

    # Report Issue
    self.report_issue_button = add_button(
        self,
        self,
        "",
        "",
        "",
        self.event_handlers.report_issue_event,
        2,
        "Report Issue",
        1,
        7,
        1,
        20,
        (150, 0),
        "nw",
    )

    # 'Clear Messages' button definition
    self.reset_button = add_button(
        self,
        self,
        "#246FB6",
        "",
        "",
        lambda: self.event_handlers.clear_messages_event(),
        2,
        "Clear Messages",
        1,
        5,
        1,
        0,
        0,
        "s",
    )
    # 'Get Backup Settings' button definition
    self.get_backup_button = self.display_backup_button(
        "Get XML from Android Device",
        "#246FB6",
        "#6563ff",
        self.event_handlers.get_xml_from_android_event,
    )
    # 'Get local XML' button
    self.getxml_button = add_button(
        self,
        self,
        "",
        "",
        "",
        self.event_handlers.getxml_event,
        2,
        "Get Local XML",
        1,
        6,
        2,
        (20, 20),
        (0, 0),
        "ne",
    )

    # 'Display Help' button definition
    self.help_button = add_button(
        self,
        self,
        "#246FB6",
        ("#0BF075", "#ffd941"),
        "",
        lambda: self.event_handlers.query_event("help"),
        2,
        "Display Help",
        1,
        7,
        2,
        (0, 20),
        (10, 0),
        "ne",
    )

    # 'Backup Help' button definition
    self.backup_help_button = add_button(
        self,
        self,
        "#246FB6",
        ("#0BF075", "#ffd941"),
        "",
        lambda: self.event_handlers.query_event("android"),
        2,
        "Get Android Help",
        1,
        7,
        2,
        (0, 20),
        (48, 0),
        "ne",
    )

    # 'Run' button definition
    self.run_button = add_button(
        self,
        self,
        "#246FB6",
        ("#0BF075", "#1AD63D"),
        "",
        self.event_handlers.run_program_event,
        2,
        "Run and Exit",
        1,
        7,
        2,
        (0, 20),
        (100, 0),
        "ne",
    )

    # 'ReRun' button definition
    self.rerun_button = add_button(
        self,
        self,
        "#246FB6",
        ("#0BF075", "#1AD63D"),
        "",
        self.event_handlers.rerun_the_program_event,
        2,
        "ReRun",
        1,
        7,
        2,
        (0, 20),
        (138, 10),
        "ne",
    )

    # 'Exit' button definition
    self.exit_button = add_button(
        self,
        self,
        "#246FB6",
        "Red",
        "",
        self.event_handlers.exit_program_event,
        2,
        "Exit",
        1,
        8,
        2,
        (20, 20),
        (10, 10),
        "e",
    )

    # Create textbox for information/feedback
    self.create_new_textbox()

    # Start third grid / column definitions
    # create tabview for Name, Color, Analysis and Debug
    self.tabview = ctk.CTkTabview(self, width=250, segmented_button_fg_color="#6563ff")
    self.tabview.grid(row=0, column=2, padx=(20, 0), pady=(20, 0), sticky="nsew")
    self.tabview.add("Specific Name")
    self.tabview.add("Colors")
    self.tabview.add("Analyze")
    self.tabview.add("Debug")

    self.tabview.tab("Specific Name").grid_columnconfigure(0, weight=1)  # configure grid of individual tabs
    self.tabview.tab("Colors").grid_columnconfigure(0, weight=1)
    self.tabview.tab("Analyze").grid_columnconfigure(0, weight=1)

    # Prompt for the name
    self.name_label = add_label(
        self,
        self.tabview.tab("Specific Name"),
        "(Pick ONLY One)",
        "",
        0,
        "normal",
        4,
        0,
        20,
        (10, 10),
        "w",
    )

    # Setup to get various display colors
    self.label_tab_2 = add_label(
        self,
        self.tabview.tab("Colors"),
        "Set Various Display Colors Here:",
        "",
        0,
        "normal",
        0,
        0,
        0,
        0,
        "",
    )
    self.colors_optionmenu = add_option_menu(
        self,
        self.tabview.tab("Colors"),
        self.event_handlers.colors_event,
        [
            "Projects",
            "Profiles",
            "Disabled Profiles",
            "Launcher Task",
            "Profile Conditions",
            "Tasks",
            "(Task) Actions",
            "Action Conditions",
            "Action Labels",
            "Action Names",
            "Scenes",
            "Background",
            "TaskerNet Information",
            "Tasker Preferences",
            "Highlight",
            "Heading",
        ],
        1,
        0,
        20,
        (10, 10),
        "",
    )

    # Reset to Default Colors button
    self.color_reset_button = add_button(
        self,
        self.tabview.tab("Colors"),
        "",
        "",
        "",
        self.event_handlers.color_reset_event,
        2,
        "Reset to Default Colors",
        1,
        3,
        0,
        20,
        (10, 10),
        "",
    )

    # AI Tab fields
    center = 50
    # API Key
    self.ai_apikey_button = add_button(
        self,
        self.tabview.tab("Analyze"),
        "",  # fg_color: str,
        "",  # text_color: str,
        "",  # border_color: str,
        self.event_handlers.ai_apikey_event,  # command
        2,  # border_width: int,
        "Show/Edit OpenAI API Key",  # text: str,
        1,  # columnspan: int,
        3,  # row: int,
        0,  # column: int,
        center,  # padx: tuple,
        (10, 10),  # pady: tuple,
        "",
    )
    # Change Prompt
    self.ai_apikey_button = add_button(
        self,
        self.tabview.tab("Analyze"),
        "",  # fg_color: str,
        "",  # text_color: str,
        "",  # border_color: str,
        self.event_handlers.ai_prompt_event,  # command
        2,  # border_width: int,
        "Change Prompt",  # text: str,
        1,  # columnspan: int,
        4,  # row: int,
        0,  # column: int,
        center,  # padx: tuple,
        (10, 10),  # pady: tuple,
        "",
    )
    # Model selection
    self.ai_model_label = add_label(
        self,
        self.tabview.tab("Analyze"),
        "Model to Use:",
        "",
        0,
        "normal",
        6,
        0,
        center,
        (0, 0),
        "n",
    )
    display_models = [*OPENAI_MODELS, *LLAMA_MODELS]  # Combine lists
    display_models.sort()
    (
        display_models.insert(0, PrimeItems.program_arguments["ai_model"])
        if PrimeItems.program_arguments["ai_model"]
        else display_models.insert(0, "None")
    )
    self.ai_model_option = add_option_menu(
        self,
        self.tabview.tab("Analyze"),
        self.event_handlers.ai_model_selected_event,
        display_models,
        6,
        0,
        center,
        (30, 0),
        "s",
    )

    # Analyize button
    display_analyze_button(self, 13, first_time=True)

    # Readme Help button
    self.ai_help_button = add_button(
        self,
        self.tabview.tab("Analyze"),
        "#246FB6",
        ("#0BF075", "#ffd941"),
        "#1bc9ff",  # border_color: str,
        lambda: self.event_handlers.query_event("ai"),  # command
        1,  # border_width: int,
        "?",  # text: str,
        1,  # columnspan: int,
        13,  # row: int,
        0,  # column: int,
        (190, 0),  # padx: tuple, don't change this.
        (10, 10),  # pady: tuple,
        "n",
    )
    self.ai_help_button.configure(width=20)

    # Debug Mode checkbox
    self.debug_checkbox = add_checkbox(
        self,
        self.tabview.tab("Debug"),
        self.event_handlers.debug_checkbox_event,
        "Debug Mode",
        4,
        3,
        20,
        10,
        "w",
        "#6563ff",
    )
    # Runtime
    self.runtime_checkbox = add_checkbox(
        self,
        self.tabview.tab("Debug"),
        self.event_handlers.runtime_checkbox_event,
        "Display Runtime Settings",
        3,
        3,
        20,
        10,
        "w",
        "#6563ff",
    )


# Delete the windows
def get_rid_of_window(self, delete_all: bool = True) -> None:  # noqa: ANN001
    """
    Hides open windows and terminates the application.

    This function withdraws the window, which removes it from the screen, and then calls the `quit()` method twice to terminate the application.

    Parameters:
        self (object): The instance of the class.

    Returns:
        None
    """
    self.withdraw()  # Remove the Window
    if delete_all:
        if self.ai_analysis_window is not None:
            self.ai_analysis_window.destroy()
        if self.diagramview_window is not None:
            self.diagramview_window.destroy()
        if self.treeview_window is not None:
            self.treeview_window.destroy()
        if self.mapview_window is not None:
            self.mapview_window.destroy()
    self.quit()


# Store our various window positions
def store_windows(self) -> None:  # noqa: ANN001
    """
    Stores the positions of the AI analysis and treeview windows.

    This function saves the positions of the various windows using the `save_window_position()` function.

    Parameters:
        self (object): The instance of the class.

    Returns:
        None
    """
    if window_pos := save_window_position(self.ai_analysis_window):
        self.ai_analysis_window_position = window_pos
    if window_pos := save_window_position(self.treeview_window):
        self.tree_window_position = window_pos
    if window_pos := save_window_position(self.diagramview_window):
        self.diagram_window_position = window_pos
    if window_pos := save_window_position(self.mapview_window):
        self.map_window_position = window_pos
    if window_pos := save_window_position(self):
        self.window_position = window_pos
