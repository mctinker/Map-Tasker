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
    display_progress_bar,
    get_appropriate_color,
    get_monospace_fonts,
    make_hex_color,
    output_label,
    reset_primeitems_single_names,
    search_substring_in_list,
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

    # Tree window was resized.
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
            self.master.text_window_width = work_window_geometry[0]
            self.master.text_window_height = work_window_geometry[1].split("+")[0]
        except (AttributeError, TypeError):
            self.master.text_window_position = "600x800+600+0"
            self.master.text_window_width = "600"
            self.master.text_window_height = "800"
            self.geometry(self.master.text_window_position)

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

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


# Display a Text structure: Used for 'Map', 'Diagram' and 'Tree' views.
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
        # Shorten the height so that the scrollbar is shown.
        height = str(int(height) - 70)
        font = getattr(master.master, "font")
        self.textview_textbox = ctk.CTkTextbox(
            self,
            font=(font, 12),
        )
        self.textview_textbox.grid(row=0, column=0, padx=20, pady=40, sticky="nsew")

        # Define a scrollbar
        self.scrollbar = ctk.CTkScrollbar(self)

        # Set the height and width
        self.textview_textbox.configure(
            height=height,
            width=width,
            state="normal",
            wrap="none",
        )

        # Enable hyperlinks if needed
        self.textview_hyperlink = CTkHyperlinkManager(
            self.textview_textbox,
            get_appropriate_color(master.master, "blue"),
        )

        # Get the special fonts
        self.bold_font = ctk.CTkFont(family=PrimeItems.program_arguments["font"], weight="bold", size=12)
        self.italic_font = ctk.CTkFont(family=PrimeItems.program_arguments["font"], size=12, slant="italic")

        # Insert the text with our new message into the text box.
        # fmt: off
        if type(the_data) == str:
            the_data = the_data.split("\n")

        # Process list data (list of lines): diagram view.
        if type(the_data) !=  dict:
            for num, line in enumerate(the_data):
                text_line = num + 1
                self.textview_textbox.insert(f"{text_line!s}.0", f"{line}\n")
            # Add the CustomTkinter widgets
            self.add_view_widgets("Diagram")

        else:
            # Process the Map view (dictionary of lines)
            self.output_map(the_data)
            # Add the CustomTkinter widgets
            self.add_view_widgets("Map")

        # Get rid of the data since we don't need it anymore
        the_data = None

        # Set a timer so we can delete the label after a certain amount of time.
        self.after(3000, self.delay_event)  # 3 second timer
        self.textview_textbox.focus_set()

    def add_view_widgets(self, title: str) -> None:
        """
        Adds CustomTkinter widgets to the map view, including a search input field and a search button.

        Parameters:
            None

        Returns:
            None
        """
        # Set up appropriate event handlers: diagram vs map
        gui_view = self.master.master
        if "Analysis" in self.textview_textbox.master.title:
            search_event = gui_view.event_handlers.analysis_search_event
            next_event = gui_view.event_handlers.analysis_next_event
            previous_event = gui_view.event_handlers.analysis_previous_event
            clear_event = gui_view.event_handlers.analysis_clear_event
            wordwrap_event = gui_view.event_handlers.analysis_wordwrap_event
        elif title == "Diagram":
            search_event = gui_view.event_handlers.diagram_search_event
            next_event = gui_view.event_handlers.diagram_next_event
            previous_event = gui_view.event_handlers.diagram_previous_event
            clear_event = gui_view.event_handlers.diagram_clear_event
            wordwrap_event = gui_view.event_handlers.diagram_wordwrap_event
        elif title == "Map":
            search_event = gui_view.event_handlers.map_search_event
            next_event = gui_view.event_handlers.map_next_event
            previous_event = gui_view.event_handlers.map_previous_event
            clear_event = gui_view.event_handlers.map_clear_event
            wordwrap_event = gui_view.event_handlers.map_wordwrap_event

        # Add label
        self.text_message_label = add_label(
            self,
            self,
            f"Drag window to desired position and rerun the {title} command.",
            "Orange",
            12,
            "normal",
            0,
            0,
            10,
            40,
            "n",
        )
        # Search input field# Search input field
        search_input = ctk.CTkEntry(
            self,
            placeholder_text="",
        )
        search_input.configure(
            # width=320,
            # fg_color="#246FB6",
            border_color="#1bc9ff",
            text_color=("#0BF075", "#1AD63D"),
        )
        search_input.insert(0, "")
        search_input.grid(
            row=0,
            column=0,
            # columnspan=1,
            padx=20,
            pady=5,
            sticky="nw",
        )
        # Search button
        search_button = add_button(
            self,
            self,
            "#246FB6",
            "",
            "",
            search_event,
            1,
            "Search",
            1,
            0,
            0,
            170,
            5,
            "nw",
        )
        search_button.configure(width=60)
        # Next search button
        next_search_button = add_button(
            self,
            self,
            "#246FB6",
            "",
            "",
            next_event,
            1,
            "Next",
            1,
            0,
            0,
            240,
            5,
            "nw",
        )
        next_search_button.configure(width=40)
        # Previous search button
        prev_search_button = add_button(
            self,
            self,
            "#246FB6",
            "",
            "",
            previous_event,
            1,
            "Prev",
            1,
            0,
            0,
            290,
            5,
            "nw",
        )
        prev_search_button.configure(width=40)
        # Clear search button
        clear_search_button = add_button(
            self,
            self,
            "#246FB6",
            "",
            "",
            clear_event,
            1,
            "Clear",
            1,
            0,
            0,
            345,
            5,
            "nw",
        )
        clear_search_button.configure(width=50)
        # Word wrap button
        _ = add_button(
            self,
            self,
            "#246FB6",
            "",
            "",
            wordwrap_event,
            1,
            "Toggle Word Wrap",
            1,
            0,
            0,
            440,
            5,
            "nw",
        )
        #  Query ? button
        search_query_button = add_button(
            self,
            self,
            "#246FB6",
            ("#0BF075", "#ffd941"),
            "#1bc9ff",
            lambda: self.master.master.event_handlers.query_event("search"),
            1,
            "?",
            1,
            0,
            0,
            400,
            5,
            "nw",
        )
        search_query_button.configure(width=20)

        # Save the widgets to the correct view: diagram or map
        if "Analysis" in self.textview_textbox.master.title:
            gui_view.analysisview = self
            gui_view.analysisview.message_label = self.text_message_label
            gui_view.analysisview.search_input = search_input
            # gui_view.analysisview.search_button = search_button
            # gui_view.analysisview.next_search_button = next_search_button
            # gui_view.analysisview.prev_search_button = prev_search_button
            # gui_view.analysisview.clear_search_button = clear_search_button
            # gui_view.analysisview.wordwrap_button = wrap_search_button
            # gui_view.analysisview.query_button = search_query_button
        elif title == "Diagram":
            gui_view.diagramview = self  # Save our textview in the main Gui view.
            gui_view.diagramview.message_label = self.text_message_label
            gui_view.diagramview.search_input = search_input
            # gui_view.diagramview.search_button = search_button
            # gui_view.diagramview.next_search_button = next_search_button
            # gui_view.diagramview.prev_search_button = prev_search_button
            # gui_view.diagramview.clear_search_button = clear_search_button
            # gui_view.diagramview.wordwrap_button = wrap_search_button
            # gui_view.diagramview.query_button = search_query_button
        elif title == "Map":
            gui_view.mapview = self  # Save our textview in the main Gui view.
            gui_view.mapview.message_label = self.text_message_label
            gui_view.mapview.search_input = search_input
            # gui_view.mapview.search_button = search_button
            # gui_view.mapview.next_search_button = next_search_button
            # gui_view.mapview.prev_search_button = prev_search_button
            # gui_view.mapview.clear_search_button = clear_search_button
            # gui_view.mapview.wordwrap_button = wrap_search_button
            # gui_view.mapview.query_button = search_query_button

        # Catch window resizing
        self.bind("<Configure>", self.on_resize)
        self.master.bind("<Key>", self.ctrlevent)

        # Set up default variables
        self.wordwrap = False
        self.search_string = ""

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

        Parameters:
            line_num (int): The current line number.
            tags (list): The list of tags.
            char_position (int): The current character position.
            previous_color (str): The previous color.
            previous_directory (str): The previous directory.
            previous_value (str): The previous value.
            the_data (dict): The dictionary containing the map data.

        Returns:
            None
        """
        max_data = len(the_data)
        tenth_increment = max_data // 10 or 1
        # Go through the data and format it accordingly.
        for num, (_, value) in enumerate(the_data.items()):
            if num % tenth_increment == 0:
                display_progress_bar(self, max_data, num, tenth_increment, is_instance_method=True)

            # Get the text of the value and ignore blank lines.
            text = value.get("text", [])
            if text and text[0] == "  \n":
                continue

            # Check to see if we need to bump the line number.
            line_num, char_position = self.check_bump(line_num, char_position, previous_value, value)

            # Check if we need to change the color
            if not value["color"] and value["text"]:
                value["color"] = [previous_color]

            # Go through all of the text/color combinations
            if value.get("color"):
                line_num, previous_color, previous_value, tags = self.process_colored_text(
                    value,
                    line_num,
                    previous_color,
                    previous_value,
                    tags,
                )
                if text[0] == "Directory\n":
                    line_num, previous_directory, previous_value, char_position = self.one_level_up(
                        line_num,
                        previous_directory,
                        previous_value,
                        char_position,
                    )
            elif value.get("directory"):
                char_position, previous_directory, line_num = self.process_directory(
                    value,
                    line_num,
                    previous_directory,
                    0 if previous_value != "directory" else char_position,
                )
                previous_value = "directory"

            if self.master.master.debug:
                logger.info(f"Map View Value: {value}")

    def check_bump(
        self: object,
        line_num: int,
        char_position: int,
        previous_value: str,
        current_value: dict,
    ) -> tuple:
        """
        Check if we need to bump the line number based on the current and previous value.

        If the current value is not a directory and the previous value was a directory, then
        bump the line number and set the character position to 0.
        If the current value is a directory and the previous value was also a directory, then
        add the length of the current text to the character position.

        Args:
            self: The instance of the class.
            line_num: The current line number.
            char_position: The current character position.
            previous_value: The previous value.
            current_value: The current value.

        Returns:
            tuple: A tuple containing the line number and character position.
        """
        current_directory = current_value.get("directory", False)

        if previous_value == "directory" and not current_directory:
            line_num += 1
            char_position = 0
        elif current_directory and previous_value == "directory":
            current_text = current_value.get("text", [])
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
        Process a single item (project, profile, or task) differently than normal items.

        If a single item is specified, then we need to process it differently than normal items.
        This function will return the line number, previous directory, previous value, and character
        position for the single item.

        The logic is as follows:
        - If the single item is a project, then set the value to the project name.
        - If the single item is a profile, then set the value to the profile name and the owning project.
        - If the single item is a task, then set the value to the task name and the owning project.

        Args:
            self: The instance of the class.
            line_num: The current line number.
            previous_directory: The previous directory.
            previous_value: The previous value.
            char_position: The current character position.

        Returns:
            tuple: A tuple containing the line number, previous directory, previous value, and character position.
        """
        single_project = PrimeItems.program_arguments.get("single_project_name")
        single_profile = PrimeItems.program_arguments.get("single_profile_name")
        single_task = PrimeItems.program_arguments.get("single_task_name")
        # Don't do anything if we are not doing a single item.
        if not any([single_project, single_profile, single_task]):
            return line_num, previous_directory, previous_value, char_position

        if single_project:
            value = {"directory": ["%%", ""]}
        elif single_profile:
            value = {"directory": ["%%projects", self.find_owning_project(single_profile)]}
        elif single_task:
            single_profile_name = self.find_owning_profile(single_task)
            if not single_profile_name:
                value = {"directory": ["%%projects", self.find_task_owning_project(single_task)]}
            else:
                value = {"directory": ["%%profiles", single_profile_name]}

        char_position, previous_directory, line_num = self.process_directory(
            value,
            line_num,
            previous_directory,
            char_position,
        )
        return line_num, previous_directory, "directory", char_position

    # Find owning Project given a Profile name
    def find_owning_project(self: object, profile_name: str) -> str:
        """
        Find the owning Project given a Profile name.

        Args:
            self: The instance of the class.
            profile_name (str): The Profile name.

        Returns:
            str: The owning Project name, or an empty string if not found.
        """
        profile_dict = PrimeItems.tasker_root_elements["all_profiles"]
        profile_id = {v["name"]: k for k, v in profile_dict.items()}.get(profile_name)

        if profile_id:
            for project_name, project_value in PrimeItems.tasker_root_elements["all_projects"].items():
                if profile_id in get_ids(True, project_value["xml"], project_name, []):
                    return project_name
        return ""

    # Find Task's owning Project
    def find_task_owning_project(self: object, task_name: str) -> str:
        """
        Find the owning project of a task given its name.

        Args:
            self: The instance of the class.
            task_name (str): The name of the task.

        Returns:
            str: The owning project name, or an empty string if not found.
        """
        all_tasks = PrimeItems.tasker_root_elements["all_tasks"]

        for project_value in PrimeItems.tasker_root_elements["all_projects"].values():
            if any(all_tasks[task_id]["name"] == task_name for task_id in get_ids(False, project_value["xml"], "", [])):
                return project_value["name"]
        return ""

    # Find the owning Profile given a Task name
    def find_owning_profile(self: object, task_name: str) -> str:
        """
        Find the owning Profile given a Task name.

        This function takes a Task name as input and searches for the corresponding Task ID in the `PrimeItems.tasker_root_elements["all_tasks"]` dictionary. It then iterates over the `PrimeItems.tasker_root_elements["all_profiles"]` dictionary to find the Profile that contains the Task ID. If a matching Profile is found, its name is returned. If no matching Profile is found, an empty string is returned.

        Parameters:
            task_name (str): The name of the Task.

        Returns:
            str: The name of the owning Profile, or an empty string if no matching Profile is found.
        """
        tid = next((k for k, v in PrimeItems.tasker_root_elements["all_tasks"].items() if v["name"] == task_name), "")

        # Find the owning Profile
        if tid:
            for profile_value in PrimeItems.tasker_root_elements["all_profiles"].values():
                for mid_key in ["mid0", "mid1"]:
                    mid = profile_value["xml"].find(mid_key)
                    if mid is not None and mid.text == tid:
                        return profile_value["name"]

        return ""

    def process_colored_text(
        self: object,
        value: dict,
        line_num: int,
        previous_color: str,
        previous_value: str,
        tags: list,
    ) -> tuple:
        """
        Process a single colored text element.

        This function takes a single colored text element from a list of colored text elements and processes it. It
        updates the input dictionary with the new text and color, and returns the updated line number, the color of the
        previous element, and the tag for the color of the previous element.

        Parameters:
            value (dict): The colored text element to process. It should have the keys "text" and "color".
            line_num (int): The current line number.
            previous_color (str): The color of the previous element.
            previous_value (str): The value of the previous element.
            tags (list): A list of tags for the colors of the elements.

        Returns:
            tuple: A tuple containing the updated line number, the color of the previous element, the tag for the color
            of the previous element, and the list of tags.
        """
        text = value["text"][0]

        if text == "Directory\n":
            value["text"] = ["Directory    (blue entries are hotlinks)\n"]
        elif text.startswith("\nn"):
            save_text, save_color = text[2:], value["color"]
            value["text"] = "\n\n"
            previous_color = self.output_map_text_lines(value, line_num, tags, previous_color, previous_value)
            line_num += 1
            value.update(text=save_text, color=save_color)

        previous_color = self.output_map_text_lines(value, line_num, tags, previous_color, previous_value)
        return line_num + 1, previous_color, "color", tags

    def process_directory(
        self: object,
        value: dict,
        line_num: int,
        previous_directory: str,
        char_position: int,
    ) -> tuple:
        """
        Process a single directory entry.

        This function takes a single directory entry from a list of directory entries and processes it. It
        updates the input dictionary with the new text and color, and returns the updated character position,
        the previous directory, and the line number.

        Parameters:
            value (dict): The directory entry to process. It should have the keys "text" and "color".
            line_num (int): The current line number.
            previous_directory (str): The previous directory.
            char_position (int): The current character position.

        Returns:
            tuple: A tuple containing the updated character position, the previous directory, and the line number.
        """
        spacing, columns = 40, 3
        directory_type = value["directory"][0]
        # We dont't support Scenes or Grand Totals hotlinks (yet)
        if directory_type in {"scenes", "grand", "</td"}:
            return 0, previous_directory, line_num

        if previous_directory != directory_type:
            char_position = 0

        line_num_str = str(line_num)
        hotlink_name = value["directory"][1]

        # Determine the name to go up to, which will be used for the tag id.
        name_to_go_up = hotlink_name if hotlink_name else "entire configuration"

        # Check for special "Up One Level" hotlink and modify the text to be displayed if it is.
        up_one_level = False
        if directory_type.startswith("%%"):
            up_one_level = True
            directory_type = f"{directory_type[2:]}_up"
            object_name = directory_type[:-3].capitalize() if hotlink_name else ""
            hotlink_name = f"Up One Level to {object_name}: {name_to_go_up}"
            name_to_insert, spacer = hotlink_name, ""
        else:
            name_to_insert = (hotlink_name[: spacing - 3] + "...") if len(hotlink_name) > spacing else hotlink_name

            # Determine additional space to add to lines if needed.
            spacer = "\n" if char_position == spacing * columns - spacing else ""
            name_to_insert = f'{name_to_insert.ljust(spacing, " ")}{spacer}'

        tag_id = self.textview_hyperlink.add([directory_type, name_to_go_up])
        self.textview_textbox.insert(f"{line_num_str}.{char_position}", name_to_insert, tag_id)
        self.textview_textbox.tag_config(
            tag_id[1],
            background=make_hex_color(self.master.master.color_lookup["background_color"]),
        )

        char_position = 0 if char_position == spacing * columns else char_position + spacing
        previous_directory = directory_type

        # Add a second "up one more level" hotlink
        if up_one_level and name_to_go_up != "entire configuration":
            new_char_pos = len(hotlink_name) + 10
            # self.textview_textbox.insert(f"{line_num_str}.{new_char_pos}", "%%%%", "up_two_levels")
            if directory_type:
                if directory_type == "profiles_up":
                    name_to_go_up = self.find_owning_project(name_to_go_up)
                    go_up_type = "projects_up"
                    name_object = "Project:"
                elif directory_type == "tasks_up":
                    name_to_go_up = self.find_owning_profile(name_to_go_up)
                    go_up_type = "profiles_up"
                    name_object = "Profile:"
                else:
                    # We're at the Project level.  Do nothing.
                    go_up_type = "all"
                    name_to_go_up = "entire configuration"
                    name_object = ""
            else:
                go_up_type = directory_type

            # If we are going up a second level, we need to insert the second "up one more level" hotlink
            if go_up_type:
                hotlink_name = f"Up Two Levels to {name_object} {name_to_go_up}"
                tag_id = self.textview_hyperlink.add([f"{go_up_type}", name_to_go_up])
                self.textview_textbox.insert(f"{line_num_str}.{new_char_pos}", f"     {hotlink_name}", tag_id)
                self.textview_textbox.tag_config(
                    tag_id[1],
                    background=make_hex_color(self.master.master.color_lookup["background_color"]),
                )
            up_one_level = False

        return char_position, previous_directory, line_num + (char_position == 0)

    def output_map_text_lines(
        self,
        value: dict,
        line_num: int,
        tags: set,
        previous_color: str,
        previous_value: str,
    ) -> str:
        """
        A function that outputs text lines with specified colors and formatting to a text box for the value passed in.
        Parameters:
            - value: A dictionary 'value' containing text, color, and highlights information.
            - line_num: An integer representing the line number.
            - tags: A set of tags for text formatting.
            - previous_color: A string representing the previous color used.
            - previous_value: A string representing the previous value used.
        Returns:
            previous_color: A string representing the previous color used.
        """

        spaces = " " * 20  # Approximate amount of spacing prior to a Task parameter.
        char_position = 0
        line_num_str = str(line_num)
        go_to_top = False

        # Precompute the background color once.
        background_color = make_hex_color(self.master.master.color_lookup["background_color"])

        # Loop through all of the text strings.
        for num, message in enumerate(value["text"]):
            new_message = message.replace("\n\n", "\n")

            # Force a newline if this is the very first Project.
            if previous_value == "directory" and "Project:" in new_message:
                new_message = f"\n{new_message}"
            # Ignore extra blank line after "[⛔ DISABLED]" text...it is following a disabled "Profile:"" line.
            if new_message == "      ":
                continue
            # Remove "Go to top" from the end of the message if it is there.
            # This is for "Go to top" hyperlink code below., which must follow the text insertion code.
            if "Go to top" in new_message:
                new_message = new_message.replace("Go to top", "")
                go_to_top = True

            if self.master.master.pretty and new_message.startswith(spaces):
                new_message = f"  {new_message}"

            # Add line number to output message
            # if self.master.master.debug:
            #     new_message = f"{line_num_str} {new_message}"

            char_position_str = str(char_position)
            tag_id = f"{line_num_str}{char_position_str}"

            # Ensure unique tag_id by appending random numbers until unique
            while tag_id in tags:
                tag_id = f"{tag_id}{random.randint(100, 999)}"  # noqa: S311
            tags.append(tag_id)

            # Determine if this is the last item in the list of text elements and add a new line if it is.
            line_to_insert = (
                f"{new_message}\n" if new_message == value["text"][-1] and "\n" not in new_message else new_message
            )

            # Insert the text to the text box.
            # The tag is obtained from call to self.textview_hyperlink.add.
            self.textview_textbox.insert(f"{line_num_str}.{char_position_str}", line_to_insert, tag_id)
            self.textview_textbox.tag_add(
                tag_id,
                f"{line_num_str}.{char_position_str}",
                f"{line_num_str}.{char_position + len(line_to_insert)}",
            )
            # Bump the character position beyond the text we just inserted..
            char_position += len(line_to_insert)

            if go_to_top:
                line_count = int(self.textview_textbox.index("end-1c").split(".")[0])
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
                link = ["gototop", "Go to top"]
                # Add the text to the text box.
                top_tag_id = self.textview_hyperlink.add(link)
                self.textview_textbox.insert(
                    f"{line_pos}.{gototop_char_position}",
                    "Go to top     ",
                    top_tag_id,
                )
                # Add color to the tag
                self.textview_textbox.tag_config(
                    top_tag_id[1],
                    background=background_color,
                )
                # Go to bottom: Add the hyperlink.
                # The tag is obtained from call to self.textview_hyperlink.add.
                link = ["gotobot", "Go to bot"]
                top_tag_id = self.textview_hyperlink.add(link)
                # Add the text to the text box.
                # For some reason, we have to back up 2 lines to get the right position.
                self.textview_textbox.insert(
                    f"{line_pos}.{gototop_char_position + 16}",
                    "Go to bottom",
                    top_tag_id,
                )
                # Add background color to the tag
                self.textview_textbox.tag_config(
                    top_tag_id[1],
                    background=background_color,
                )
                go_to_top = False

            # Do color and name highlighting (bold/italicize/underline/highlight).
            # Use previous color if it doesn't exist.
            # Have to handle background color separately
            color = previous_color
            if "Color for Background set to" in line_to_insert or "highlighted for visibility" in line_to_insert:
                color = "White"
            else:
                color, tags = self.output_map_colors_highlighting(
                    value,
                    tags,
                    previous_color,
                    previous_value,
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
                background=background_color,
            )

        return previous_color

    def output_map_colors_highlighting(
        self,
        value: dict,
        tags: list,
        previous_color: str,
        previous_value: str,
        num: int,
        message: str,
        tag_id: str,
        color: str,
    ) -> tuple:
        """
        A function to apply color highlighting to text based on the specified configurations.

        Parameters:
            - self: the object instance
            - value: a dictionary containing the value to be highlighted
            - tags: a list of tags to be applied
            - previous_color: a string representing the previous color used
            - previous_value: a string representing the previous value
            - num: an integer representing a specific number of the value
            - message: a string containing the message to be highlighted
            - tag_id: a string representing the tag ID
            - color: a string representing the color

        Returns:
            - color (string): the color to be applied
            - tags (list): the list of tags to be applied
        """

        # Look for special string highlighting in value (bold, italic, underline, highlight)
        # starting_line_to_search = 1
        with contextlib.suppress(KeyError):
            if num == 0 and value["highlights"]:
                tags = self.add_highlights(message, value, previous_value, tag_id, tags)

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
        return color, tags

    def add_highlights(self, message: str, value: dict, previous_value: str, tag_id: str, tags: list) -> list:
        # Set up the highlighting elements
        """
        Add highlights to the text box.

        This function takes a message, a dictionary of values, a previous value, a tag ID, and a list of tags.
        It adds highlighting to the text box based on the highlights in the value dictionary.

        The highlights are specified as a list of strings in the value dictionary, where each string
        is in the format "highlight_type,highlight_text".  The highlight_type is one of "bold", "italic",
        "underline", or "mark".  The highlight_text is the text to be highlighted.

        The function returns the updated list of tags.

        Parameters:
            - message (str): the message to be highlighted
            - value (dict): the dictionary containing the highlights
            - previous_value (str): the previous value
            - tag_id (str): the tag ID
            - tags (list): the list of tags

        Returns:
            - list: the updated list of tags
        """
        highlight_configurations = {
            "bold": {"font": self.bold_font},
            "italic": {"font": self.italic_font},
            "underline": {"underline": True},
            "mark": {"background": PrimeItems.colors_to_use["highlight_color"]},
        }

        for highlight in value["highlights"]:
            # Go through all highlights for this line/value
            highlights = highlight.split(",")
            start_position = message.find(highlights[1])
            end_position = start_position + len(highlights[1])
            highlight_type = highlights[0]
            if highlight_type in highlight_configurations:
                # Found a highlight type.
                # If this is the first Project, then we need to backup one since we added a "\n"
                if previous_value == "directory":
                    start_position -= 1
                    end_position -= 1
                new_tag = f"{tag_id}{highlight_type}"
                tags.append(new_tag)

                # Figure out exactly what we are looking for.
                if "Task: " in message:
                    search_word = "Task: "
                elif "Profile: " in message:
                    search_word = "Profile: "
                elif "Project: " in message:
                    search_word = "Project: "
                else:
                    search_word = "Scene: "

                # Get the total number of lines in the text box
                line_count = int(self.textview_textbox.index("end-1c").split(".")[0])
                # Now find the line we want to highlight based on our search word. Search from the bottom up.
                while line_count:
                    # Get just the line.
                    # 'lineend' is end of line without the newline.  'lineend+1c' includes newline.
                    tx = self.textview_textbox.get(f"{line_count!s}.0", f"{line_count!s}.0 lineend")
                    if search_word in tx:
                        break
                    line_count -= 1
                line_to_highlight = str(line_count)

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
        return tags

    def ctrlevent(self, event: object) -> str:
        """Event handler for Ctrl+C and Ctrl+V"""
        # Ctrl+C ...copy
        # if event.state == 4 and event.keysym == "c":
        if event.keysym == "c":
            try:
                content = self.textview_textbox.selection_get()
            except TclError:  # Copy with no sting selected
                return ""
            self.clipboard_clear()
            self.clipboard_append(content)
            output_label(self, self, f"Text '{content}' copied to clipboard.")
            return "break"
        # Ctrl+V ...paste
        if event.state == 4 and event.keysym == "v":
            self.textview_textbox.insert("end", self.selection_get(selection="CLIPBOARD"))
            return "break"
        return "break"

    def delay_event(self) -> None:
        """
        A method that handles the delay event for the various text views.
        It deletes the label after a certain amount of time.
        """
        self.text_message_label.destroy()
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
        # TODO self.text.master.textview_textbox not correct
        # output_label(self, self.text.master.textview_textbox, "ahah")

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
                    elif link[0] == "gotobot":
                        # Go to bottom (first valid non-blank line)
                        line_count = int(self.text.master.textview_textbox.index("end-1c").split(".")[0])
                        line_pos = line_count - 1
                        while line_pos:
                            line = self.text.master.textview_textbox.get(f"{line_pos!s}.0", f"{line_pos!s}.end")
                            if "CAVEATS:" in line:
                                break
                            line_pos -= 1
                        self.text.master.textview_textbox.see(f"{line_pos!s}.0")
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
        # Don't yet support scenee or grand total hotlinks
        if action in ("scenes", "grand"):
            nogo_name = "Grand Totals" if action == "grand" else "Scene"
            guiself.display_message_box(f"'{nogo_name}' hotlinks are not working yet.", "Orange")
        # Handle single Project/Profile/Task going up a level
        elif action in ("projects_up", "profiles_up", "projects_up"):
            action = action.replace("_up", "")
            self.rebuildmap_single_item(action, name, guiself)
        # Regular directory hotlink.  See ifd it is already in the view.
        elif (
            (action == "tasks" and self.name_in_list(name, PrimeItems.tasker_root_elements["all_tasks"]))
            or (action == "profiles" and self.name_in_list(name, PrimeItems.tasker_root_elements["all_profiles"]))
            or (action == "projects" and self.name_in_list(name, PrimeItems.tasker_root_elements["all_projects"]))
        ):
            # Find and point to the item in the map view.
            self.find_and_point_to_item(action, name, guiself)

        # Drop here if the item was not found in the map/list
        else:
            # Item not found.  We'll have to rebuild the map.
            self.rebuildmap_single_item(action, name, guiself)

    # The user has clicked on a hotlink.  Get the item clicked and remap using only that single item.
    def rebuildmap_single_item(self, action: str, name: str, guiself: ctk) -> None:
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
            update_tasker_object_menus(guiself, get_data=False, reset_single_names=False)
            # Remap it.
            guiself.remapit(clear_names=False)

    def name_in_list(self: object, name: str, tasker_items: dict) -> bool:
        """
        Determine if a specific name is in a dictionary of items.

        Args:
            name (str): The name to search for.
            tasker_items (dict): The dictionary of tasker items (Project/Profiles/Tasksto search in.

        Returns:
            bool: True if the name is found, False otherwise.
        """
        return any(tasker_items[key]["name"] == name for key in tasker_items)

    # Search for and point to the specific item in the textbox.
    def find_and_point_to_item(self, action: str, name: str, guiself: ctk) -> None:
        # Build the srach string
        """
        Search for and point to the specific item in the textbox.

        Args:
            action (str): The type of action to perform (e.g., 'projects', 'profiles', 'tasks').
            name (str): The name of the item to point to.
            guiself (ctk): The GUI self reference.

        Returns:
            None: This function does not return anything.
        """
        our_view = guiself.mapview
        search_string = f"{action[:-1].capitalize()}: {name}"
        # Get the entire textbox into a list, one item per line.
        search_list = our_view.textview_textbox.get("1.0", "end").rstrip().split("\n")

        # Search for all hits for our search string.
        search_hits = search_substring_in_list(search_list, search_string, stop_on_first_match=True)
        if not search_hits:
            guiself.display_message_box(f"Could not find '{search_string}' in the list.", "Orange")
            return
        first_hit = search_hits[0]
        line_num = first_hit[0] + 1
        line_pos = first_hit[1]
        # Point to the first hit
        our_view.textview_textbox.see(f"{line_num!s}.{line_pos!s}")
        # Highlight the match
        value = {}
        value["highlights"] = [f"mark,{search_string}"]

        # Highlight the string so it is easy to find.
        # Delete old tag and add new tag.
        our_view.textview_textbox.tag_remove("inlist", "1.0", "end")
        our_view.textview_textbox.tag_add(
            "inlist",
            f"{line_num}.{line_pos!s}",
            f"{line_num}.{(line_pos+len(search_string))!s}",
        )
        highlight_configurations = {
            "mark": {"background": PrimeItems.colors_to_use["highlight_color"]},
        }
        our_view.textview_textbox.tag_config("inlist", **highlight_configurations["mark"])


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
    self.doing_diagram = False
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
    self.view_limit = 10000
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
    self.conditions_checkbox = add_checkbox(
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
    # View Limit
    self.viewlimit_label = add_label(
        self,
        self.sidebar_frame,
        "View Limit:",
        "",
        0,
        "normal",
        20,
        0,
        30,
        20,
        "nw",
    )
    self.viewlimit_optionmenu = add_option_menu(
        self,
        self.sidebar_frame,
        self.event_handlers.viewlimit_event,
        ["5000", "10000", "15000", "20000", "25000", "30000", "Unlimited"],
        20,
        0,
        (20, 0),
        20,
        "n",
    )
    #  Query ? button
    self.viewlimit_query_button = add_button(
        self,
        self.sidebar_frame,
        "#246FB6",
        ("#0BF075", "#ffd941"),
        "#1bc9ff",
        lambda: self.event_handlers.query_event("viewlimit"),
        1,
        "?",
        1,
        20,
        0,
        (200, 0),
        20,
        "n",
    )
    self.viewlimit_query_button.configure(width=20)

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
        self.event_handlers.rerun_event,
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
    with contextlib.suppress(AttributeError):
        if window_pos := save_window_position(self.ai_analysis_window):
            self.ai_analysis_window_position = window_pos
    with contextlib.suppress(AttributeError):
        if window_pos := save_window_position(self.treeview_window):
            self.tree_window_position = window_pos
    with contextlib.suppress(AttributeError):
        if window_pos := save_window_position(self.diagramview_window):
            self.diagram_window_position = window_pos
    with contextlib.suppress(AttributeError):
        if window_pos := save_window_position(self.mapview_window):
            self.map_window_position = window_pos
    with contextlib.suppress(AttributeError):
        if window_pos := save_window_position(self):
            self.window_position = window_pos
