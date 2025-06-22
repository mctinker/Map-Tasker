#! /usr/bin/env python3
"""GUI Window Classes and Definitions"""

#                                                                                      #
# guiwins: provide GUI window functions                                                #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
from __future__ import annotations

import contextlib
import os
import random
import re
import time
import tkinter as tk
import webbrowser
from tkinter import Label, TclError, Toplevel, ttk
from typing import TYPE_CHECKING

import customtkinter as ctk
from PIL import Image, ImageTk

from maptasker.src.actione import get_action_code
from maptasker.src.colrmode import set_color_mode
from maptasker.src.diagcnst import task_delimeter
from maptasker.src.diagutil import width_and_height_calculator_in_pixel
from maptasker.src.error import rutroh_error
from maptasker.src.getids import get_ids
from maptasker.src.guiutils import (
    add_button,
    add_checkbox,
    add_label,
    add_logo,
    add_option_menu,
    build_connectors,
    destroy_hover_tooltip,
    display_analyze_button,
    display_progress_bar,
    extract_number_from_line,
    find_the_line,
    get_appropriate_color,
    get_item_xml,
    get_monospace_fonts,
    get_profiles_in_project,
    get_taskid_from_unnamed_task,
    get_tasks_in_project,
    kill_the_progress_bar,
    make_hex_color,
    merge_lists,
    on_closing,
    output_label,
    parse_pairs_to_columns,
    prefix_and_sort,
    remove_tags_from_bars_and_names,
    reset_primeitems_single_names,
    search_substring_in_list,
    update_tasker_object_menus,
)
from maptasker.src.lineout import LineOut
from maptasker.src.maputils import (
    find_all_positions,
    find_owning_profile,
    find_owning_project,
    find_task_pattern,
    get_first_substring_match,
    is_color_dark,
)
from maptasker.src.primitem import PrimeItems
from maptasker.src.property import get_properties
from maptasker.src.scenes import get_details
from maptasker.src.shelsort import shell_sort
from maptasker.src.sysconst import (
    DIAGRAM_PROFILES_PER_LINE,
    MODEL_GROUPS,
    TAB_NAMES,
    UNNAMED_ITEM,
    clean,
    logger,
)
from maptasker.src.xmldata import remove_html_tags

if TYPE_CHECKING:
    import defusedxml.ElementTree

# Set up for access to icons
kaka = os.getcwd()
kaka1 = os.path.realpath(__file__)
CURRENT_PATH = os.path.dirname(os.path.realpath(__file__))
ICON_DIR = os.path.join(CURRENT_PATH, f"..{PrimeItems.slash}assets", "icons")
ICON_PATH = {"arrow": os.path.join(ICON_DIR, "arrow.png")}
bar = "│"
box_line = "═"
straight_line = "─"
down_arrow = "▼"
up_arrow = "▲"
left_arrow = "◄"
right_arrow = "►"
right_arrow_corner_down = "╰"
right_arrow_corner_up = "╯"
left_arrow_corner_down = "╭"
left_arrow_corner_up = "╮"
angle = "└─ "


class CTkTreeview(ctk.CTkFrame):
    """Class to handle the Treeview

    Args:
        ctk (ctk): Our GUI framework
    """

    def __init__(self, master: ctk.CTkToplevel, items: list) -> None:
        """Function:
        def __init__(self, master: any, items: list):
            Initializes a Treeview widget with a given master and list of items.
            Parameters:
                master ( ctk.CTkToplevel): The parent widget for the Treeview.
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
        self.bg_color = self.root._apply_appearance_mode(  # noqa: SLF001
            ctk.ThemeManager.theme["CTkFrame"]["fg_color"],
        )
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
        self.img_close = ImageTk.PhotoImage(
            self.im_close,
            name="img_close",
            size=(15, 15),
        )
        self.img_empty = ImageTk.PhotoImage(
            self.im_empty,
            name="img_empty",
            size=(15, 15),
        )

        # Arrow element configuration
        with contextlib.suppress(
            TclError,
        ):  # Don't throw error if the element already exists.  Just reuse it.
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
                            (
                                "Treeitem.myindicator",
                                {"side": "left", "sticky": "nsew"},
                            ),
                            ("Treeitem.image", {"side": "left", "sticky": "nsew"}),
                            (
                                "Treeitem.focus",
                                {
                                    "side": "left",
                                    "sticky": "nsew",
                                    "children": [
                                        (
                                            "Treeitem.text",
                                            {"side": "left", "sticky": "nsew"},
                                        ),
                                    ],
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
                the_id = self.treeview.insert(
                    parent,
                    "end",
                    text=item["name"].ljust(50),
                )
                with contextlib.suppress(KeyError):
                    self.insert_items(item["children"], the_id)
            else:
                self.treeview.insert(parent, "end", text=item)


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

        # Save the window position on closure
        self.protocol("WM_DELETE_WINDOW", lambda: on_closing(self))


# Display a Text structure: Used for 'Map', 'Diagram' and 'Tree' views.
class CTkTextview(ctk.CTkFrame):
    """Class to handle the Treeview

    Args:
        ctk (ctk): Our GUI framework
    """

    def __init__(self, master: ctk.CTkTextbox, title: str, the_data: list) -> None:
        """Function:
        def __init__(self, master: any, items: list):
            Initializes a Textview widget with a given master and list of items.
            Parameters:
                master (ctk.CTkTextbox): The parent widget for the Textview.
                items (list): A list of items to be inserted into the Textview.
            Returns:
                None.
            Processing Logic:
                - Sets up the ATextview widget with appropriate styles and bindings.
                - Inserts the given items into the Textview.
        """
        self.root = master
        super().__init__(self.root)

        # Define a single column and make it extendable.
        self.grid_columnconfigure(0, weight=1)

        # Setup our appearance for text, foreground and background.
        self._setup_appearance()

        # Set up the title
        self.title = (
            f"{title} - Drag window to desired position and rerun the {title} command."
        )

        # Setup the textbox.
        self._setup_textbox(master)

        # Process the data and insert it into the text box.
        self.process_data(the_data)

        # Set a timer so we can delete the label after a certain amount of time.
        self.after(3000, self.delay_event)  # 3 second timer
        self.textview_textbox.focus_set()

    def _setup_appearance(self) -> None:
        """
        Sets up the appearance of the text view by configuring colors based on the current theme.
        """
        self.textview_bg_color = self._get_appearance_color("CTkFrame", "fg_color")
        self.textview_text_color = self._get_appearance_color("CTkLabel", "text_color")
        self.selected_color = self._get_appearance_color("CTkButton", "fg_color")

        # Set up the style/theme
        self.textview_style = ttk.Style(self)
        self.textview_style.theme_use("default")

        # Get the special fonts
        font = getattr(self.master.master, "font", ("Arial", 12))  # Default font
        self.bold_font = ctk.CTkFont(
            family=font,
            weight="bold",
            size=12,
        )
        self.italic_font = ctk.CTkFont(
            family=font,
            size=12,
            slant="italic",
        )
        background_color = make_hex_color(
            self.master.master.color_lookup["background_color"],
        )
        self.configure(fg_color=background_color)

    def _get_appearance_color(self, widget_type: object, color_type: str) -> object:
        """
        Retrieves the appearance color for a given widget type and color type.

        Args:
            widget_type (object): The type of the widget.
            color_type (str): The type of the color.

        Returns:
            object: The appearance color.
        """
        return self.root._apply_appearance_mode(  # noqa: SLF001
            ctk.ThemeManager.theme[widget_type][color_type],
        )

    def _setup_textbox(self, master: ctk.CTkTextbox) -> None:
        """
        Sets up the text box widget with the specified master widget.

        Args:
            master (ctk.CTkTextbox): The parent widget for the text box.

        Returns:
            None
        """
        font = getattr(master.master, "font")
        self.textview_textbox = ctk.CTkTextbox(
            self,
            font=(font, 12),
        )
        self.textview_textbox.grid(row=0, column=0, padx=20, pady=40, sticky="nsew")

        # Get thew width and height of the text box.
        width = getattr(master.master, "text_window_width")
        height = getattr(master.master, "text_window_height")
        # Shorten the height so that the scrollbar is shown.
        height = str(int(height) - 70)

        # Define a scrollbar
        _ = ctk.CTkScrollbar(self)

        # Configure the text box
        self.textview_textbox.configure(
            height=int(height),
            width=int(width),
            state="normal",
            wrap="none",
        )

        # Enable hyperlinks if needed
        self.textview_hyperlink = CTkHyperlinkManager(
            self.textview_textbox,
            get_appropriate_color(master.master, "blue"),
        )

        # Initialize variables
        self.textview_textbox.diagram_highlighted_connector = ""
        self.top = False  # Used by Next / Prev buttons

    def process_data(self, the_data: list) -> None:
        """
        Processes the given data and inserts it into the text box.

        Args:
            the_data (list): The data to be processed and inserted.
        """
        # Insert the text with our new message into the text box.
        if type(the_data) == str:
            the_data = the_data.split("\n")

        # Setup to save items (Projects, Profiles, Tasks, and Scenes)
        self.master.master.items_for_selection = {}  # MyGui

        # Process list data (list of lines): diagram view.
        if not isinstance(the_data, dict):
            self.output_list(the_data)

        else:
            # Process the Map view (dictionary of lines)
            self.output_map(the_data)
            # Add the CustomTkinter widgets
            self.add_view_widgets("Map")

    def output_list(self, the_data: list) -> None:
        """
        Output the text data to the text box, adding line numbers if in debug mode.
        If the title contains 'Diagram', then color the text, and if the title contains
        'Analysis', then add the analysis CustomTkinter widgets.

        Args:
            the_data (list): List of lines to insert into the text box.
        """
        is_diagram = "Diagram" in self.title

        # -------------------------------------------------------------------------
        # BUILD ALL LINES INTO ONE STRING AND DO ONE INSERT
        # -------------------------------------------------------------------------
        # Create the lines for insertion in a single pass
        debug_mode = getattr(self.master.master, "debug", False)  # Get debug mode
        # Include the line number in front of the line if debug mode.
        # Use a list comprehension to build the lines.
        # Truncate the lines greater than max_length due to output corruption beyond max_length.
        max_length = 4500
        trunncated = "...truncated!\n"
        lines = [
            (
                f"{i + 1}{line[: max_length - 3]}{trunncated}"
                if len(line) > max_length - 3 and debug_mode
                else (
                    f"{i + 1}{line}\n"
                    if debug_mode
                    else f"{line[:max_length]}{trunncated}"
                    if len(line) > max_length
                    else f"{line}\n"
                )
            )
            for i, line in enumerate(the_data)
        ]

        # Join everything into one big string
        big_block_of_text = "".join(lines)

        # Clear the Text widget once
        self.textview_textbox.delete("1.0", "end")

        # Insert in a single call all of the lines of data.
        self.textview_textbox.insert("1.0", big_block_of_text)

        if is_diagram:
            # -------------------------------------------------------------------------
            # Go thru the data:
            #    - Add tags (aka highlight) for Project/Profile/Task name colors
            #    - Build the Task-to-Task connectors
            # -------------------------------------------------------------------------
            self.diagram_connectors = {}
            for i, line in enumerate(the_data):
                self.highlight_text(line, i + 1)
                self.diagram_connectors = build_connectors(
                    the_data,
                    i,
                    self.diagram_connectors,
                )

            # Configure tag colors once if a highlight was applied
            guiview = self.master.master
            # In order for the map to work, we need to ensure that we have the colors defined.
            if not getattr(guiview, "color_lookup", None):
                guiview.color_lookup = set_color_mode(guiview.appearance_mode)
            color_lookup = guiview.color_lookup
            self.textview_textbox.tag_config(
                "project",
                foreground=color_lookup["project_color"],
            )
            self.textview_textbox.tag_config(
                "profile",
                foreground=color_lookup["profile_color"],
            )
            self.textview_textbox.tag_config(
                "task",
                foreground=color_lookup["task_color"],
            )
            self.textview_textbox.tag_config(
                "scene",
                foreground=color_lookup["scene_color"],
            )

            # Add connector tags so theey can be highlighted when clicked.
            self.add_connector_tags(self.diagram_connectors)

        # Add the CustomTkinter widgets
        if "Analysis" in self.title:
            self.add_view_widgets("Analysis")
        else:
            self.add_view_widgets("Diagram")
            # Force courier new for diagram view if just Courier...perfect character alignment.
            background_color = make_hex_color(
                self.master.master.color_lookup["background_color"],
            )
            if getattr(self.master.master, "font", "Arial") == "Courier":
                self.textview_textbox.configure(
                    self,
                    font=("Courier New", 12),
                    fg_color=background_color,
                )

        # Save a pointer to the data.
        self.data = the_data

        # Make it the focus
        self.focus_set()

    def add_view_widgets(self, title: str) -> None:
        """
        Adds CustomTkinter widgets to the map view, including a search input field and a search button.

        Parameters:
            None

        Returns:
            None
        """
        # Define the event handlers based on the specific 'view'.
        gui_view = self.master.master

        # Dictionary mapping titles to lambdas that assign the events
        event_assignments: dict[str, callable[[], None]] = {
            "Analysis": lambda: (
                gui_view.event_handlers.analysis_search_event,
                gui_view.event_handlers.analysis_nextprev_event,
                gui_view.event_handlers.analysis_clear_event,
                gui_view.event_handlers.analysis_wordwrap_event,
                gui_view.event_handlers.analysis_topbottom_event,
            ),
            "Diagram": lambda: (
                gui_view.event_handlers.diagram_search_event,
                gui_view.event_handlers.diagram_nextprev_event,
                gui_view.event_handlers.diagram_clear_event,
                gui_view.event_handlers.diagram_wordwrap_event,
                gui_view.event_handlers.diagram_topbottom_event,
            ),
            "Map": lambda: (
                gui_view.event_handlers.map_search_event,
                gui_view.event_handlers.map_nextprev_event,
                gui_view.event_handlers.map_clear_event,
                gui_view.event_handlers.map_wordwrap_event,
                gui_view.event_handlers.map_topbottom_event,
            ),
        }

        # Retrieve and assign the customtkinter return 'events' based on the title
        if title in event_assignments:
            (
                search_event,
                nextprev_event,
                clear_event,
                wordwrap_event,
                topbottom_event,
            ) = event_assignments[title]()

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
        # Search input field
        # Note: The following will capture a double click, in which case the second click will be ignored
        try:
            search_input = ctk.CTkEntry(
                self,
                placeholder_text="",
            )
        except TclError:
            return
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
            (170, 0),
            5,
            "nw",
        )
        search_button.configure(width=60)
        create_tooltip(
            search_button,
            text="Click this button to initiate a search for the string you have entered to the left and highlight the matches.\n\nClick the ? to get more info.",
        )

        # Next search button
        next_search_button = add_button(
            self,
            self,
            "#246FB6",
            "",
            "",
            lambda: nextprev_event(search_next=True),
            1,
            "Next",
            1,
            0,
            0,
            (240, 0),
            5,
            "nw",
        )
        next_search_button.configure(width=40)
        create_tooltip(
            next_search_button,
            text="Make the next matched string visible.\n\nClick the ? to get more info.",
        )
        # Previous search button
        prev_search_button = add_button(
            self,
            self,
            "#246FB6",
            "",
            "",
            lambda: nextprev_event(search_next=False),
            1,
            "Prev",
            1,
            0,
            0,
            (290, 0),
            5,
            "nw",
        )
        prev_search_button.configure(width=40)
        create_tooltip(
            prev_search_button,
            text="Make the previous matched string visible.\n\nClick the ? to get more info.",
        )
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
            (345, 0),
            5,
            "nw",
        )
        clear_search_button.configure(width=50)

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
            (400, 0),
            5,
            "nw",
        )
        search_query_button.configure(width=20)

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
            (440, 0),
            5,
            "nw",
        )

        # Top button
        top_button = add_button(
            self,
            self,
            "#246FB6",
            "",
            "",
            lambda: topbottom_event(True),
            1,
            "Top",
            1,
            0,
            0,
            (600, 0),
            5,
            "nw",
        )
        top_button.configure(width=40)

        # Bottom button
        top_button = add_button(
            self,
            self,
            "#246FB6",
            "",
            "",
            lambda: topbottom_event(False),
            1,
            "Bottom",
            1,
            0,
            0,
            (650, 0),
            5,
            "nw",
        )
        top_button.configure(width=50)

        # Save the widgets to the correct view: diagram or map
        if "Analysis" in self.textview_textbox.master.title:
            gui_view.analysisview = self
            gui_view.analysisview.message_label = self.text_message_label
            gui_view.analysisview.search_input = search_input

        elif title == "Diagram":
            gui_view.diagramview = self  # Save our textview in the main Gui view.
            gui_view.diagramview.message_label = self.text_message_label
            gui_view.diagramview.search_input = search_input
            # Add label
            _ = add_label(
                self,
                self,
                "Profiles Per Line:",
                "Orange",
                "",
                "normal",
                0,
                0,
                (930, 0),
                5,
                "nw",
            )
            # Add Profile Level pulldown
            self.profiles_per_line_option = add_option_menu(
                self,
                self,
                gui_view.event_handlers.profiles_per_line_event,
                ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
                0,
                0,
                (1050, 0),
                5,
                "nw",
            )
            self.profiles_per_line_option.configure(width=50)
            self.profiles_per_line_option.set("6")
            # Query ? button
            ppp_query_button = add_button(
                self,
                self,
                "#246FB6",
                ("#0BF075", "#ffd941"),
                "#1bc9ff",
                lambda: self.master.master.event_handlers.query_event("ppp"),
                1,
                "?",
                1,
                0,
                0,
                (1110, 0),
                5,
                "nw",
            )
            ppp_query_button.configure(width=20)
            create_tooltip(
                self.profiles_per_line_option,
                text="Select how many Profiles\nto display per line.  The default is 6.\n\nClick the ? to get more info.",
            )

        elif title == "Map":
            gui_view.mapview = self  # Save our textview in the main Gui view.
            gui_view.mapview.message_label = self.text_message_label
            gui_view.mapview.search_input = search_input

        # Catch window resizing
        self.bind("<Configure>", self.on_resize)
        self.master.bind("<Key>", self.ctrlevent)

        # Set up default variables
        self.wordwrap = False
        self.search_string = ""

    def add_jumpto_buttons(self, connector: dict) -> None:
        """
        Adds jump-to-top and jump-to-bottom buttons to the GUI.

        This function creates two buttons that allow users to quickly jump to
        the top or bottom of a diagram view, based on the start and end positions
        provided in the connector dictionary. The buttons are styled and positioned
        using specific parameters and are connected to event handlers for navigation.

        Args:
            connector (dict): A dictionary containing the start and end positions
                            for the top and bottom jump actions.

        Returns:
            None
        """
        # Point to the GUI self.
        gui_view = self.master.master

        # Jump-to Top button
        self.jump_top = add_button(
            self,
            self,
            "#246FB6",
            "",
            "",
            lambda: gui_view.event_handlers.diagram_jump_topbottom_event(
                True,
                connector,
            ),
            1,
            "Top Task",
            1,
            0,
            0,
            (730, 0),
            5,
            "nw",
        )
        self.jump_top.configure(width=60)
        create_tooltip(
            self.jump_top,
            text="Make the Task at the top of the highlighted connection visible.",
        )

        # Jump-to Bottom button
        self.jump_bottom = add_button(
            self,
            self,
            "#246FB6",
            "",
            "",
            lambda: gui_view.event_handlers.diagram_jump_topbottom_event(
                False,
                connector,
            ),
            1,
            "Bottom Task",
            1,
            0,
            0,
            (815, 0),
            5,
            "nw",
        )
        self.jump_bottom.configure(width=60)
        create_tooltip(
            self.jump_bottom,
            text="Make the Task at the bottom of the highlighted connection visible.",
        )

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

        This function is called when the window is resized. It retrieves the current window position from
        `self.master.master.{view}_window_position`,
        splits it into width, height, and x and y coordinates. It then updates the window geometry with the new width,
        height, and x and y coordinates
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

    def click_text(self, event: object) -> None:
        """
        Gets the index of the mouse click on the text box and processed it based on its tag.

        Args:
            event: The event object containing the coordinates of the mouse click.

        Returns:
            None: This function does not return anything.

        Raises:
            None: This function does not raise any exceptions.

        This function is called when the text box is clicked. It uses the event object to get the coordinates of the mouse click and then gets the index of the text box at those coordinates. The index is then used to get the text between the start and end indices of the tag "adj" at the mouse click location.
        """
        text_widget = event.widget
        # print(f"Widget: {event.widget}")
        # print(f"Event type: {event.type}")
        # print(f"Mouse position (widget): {event.x}, {event.y}")
        # print(f"Mouse position (root): {event.x_root}, {event.y_root}")
        # print(f"Key symbol (if key event): {event.keysym}")
        # print(f"Key character (if key event): {event.char}")
        # print(f"Button number (if mouse event): {event.num}")
        # print(f"State (modifier keys/mouse buttons): {event.state}")
        # print(f"Timestamp: {event.time}")
        # print(
        #    f"Widget under pointer: {event.widget.winfo_containing(event.x_root, event.y_root)}",
        # )

        # get the index of the mouse click
        index = text_widget.index(f"@{event.x},{event.y}")

        # Get the tags at that index
        tags_at_index = text_widget.tag_names(index)
        connector_tagid = self.textview_textbox.diagram_highlighted_connector
        connector = ""

        # Go through the tags for the character clicked.  There should only be one.
        tag = tags_at_index[0]
        tag_flag = tags_at_index[1] if len(tags_at_index) > 1 else ""

        # If it is a connector, then highlight it.
        if "wire_" in tag:
            connector = self.display_connector_details(
                tag,
                connector,
                connector_tagid,
            )

        # Handle item name (Project, Profile, Task, Scene or search name tags)
        elif "." in tag:
            # Add the info to the hover tooltip.
            self.display_hover_info(tag, tag_flag, event, index)

        # Add 'Jump to' buttons.
        if connector:
            self.add_jumpto_buttons(connector)

    def display_connector_details(
        self,
        tag: str,
        connector: dict,
        connector_tagid: str,
    ) -> dict:
        """
        Given a tag, the tag of the connector, and the tagid of the previously highlighted connector,
        remove the previous highlighting, and highlight the new connector.

        Args:
        tag (str): The tag of the new connector to be highlighted.
        connector (dict): The dictionary of the connector to be highlighted.
        connector_tagid (str): The tagid of the previously highlighted connector.

        Returns:
        dict: The updated dictionary of the connector to be highlighted.
        """
        # Find and delete our previous highlighted up/down bars.  We do this for performance.
        remove_tags_from_bars_and_names(self)

        # Now turn the highlighting off.
        self.textview_textbox.tag_config(
            connector_tagid,
            background=make_hex_color(
                self.master.master.color_lookup["background_color"],
            ),
        )
        connector_tagid = ""

        # Add tags for up/down bars.
        connector_key = tag[5:]
        connector = self.diagram_connectors[connector_key]
        line_num = connector["start_top"][0]
        number_of_lines_to_highlight = (
            connector["start_bottom"][0] - connector["start_top"][0] + 1
        )
        end_top_col = connector["end_top"][1]
        for _ in range(number_of_lines_to_highlight):
            self.textview_textbox.tag_add(
                tag,
                f"{line_num}.{end_top_col!s}",
                f"{line_num}.{end_top_col + 1!s}",
            )
            connector["extra_bars"].append((line_num, end_top_col))
            line_num += 1

        # See if there are bars directly above top left elbow, and highlight if there are.
        self.highlight_bars_above(connector, connector["start_top"], tag, bar)

        # See if there are bars directly above bottom left elbow, and highlight if there are.
        self.highlight_bars_above(connector, connector["start_bottom"], tag, bar)

        # See if there are bars directly above top left elbow, and highlight if there are.
        self.highlight_bars_below(
            connector,
            connector["start_top"],
            tag,
            left_arrow_corner_down,
        )

        # See if there are bars directly above bottom left elbow, and highlight if there are.
        self.highlight_bars_below(
            connector,
            connector["start_bottom"],
            tag,
            left_arrow_corner_down,
        )

        # Identify this connector aas the active tag.
        connector["tag"] = tag

        # Now highlight the selected connector.
        self.textview_textbox.tag_config(
            tag,
            background=make_hex_color("blue"),
        )
        self.textview_textbox.diagram_highlighted_connector = tag

        return connector

    def display_hover_info(
        self,
        tag: str,
        tag_flag: str,
        event: object,
        index: str,
    ) -> None:
        """
        Displays a hover tooltip with information about the item associated with the given tag.

        Args:
            tag (str): The tag identifier for the selected item.
            tag_flag (str): The flag indicating search value 'found'.
            event (object): The event object containing information about the mouse event.
            index (str): The index of the text box where the mouse click occurred.

        Description:
            This method retrieves and formats information about the item associated with the given tag
            and displays it as a tooltip near the mouse cursor. The information displayed depends on the
            type of item (task, profile, or project), and includes the item's name and related context
            such as the owning profile or project. Task-related information includes profile and project
            associations, while project-related information includes project properties.

        """
        with contextlib.suppress(AttributeError):
            destroy_hover_tooltip(self.hover_tooltip)

        # If this is a 'search' tag, then make the tag = 'found'.
        if tag_flag == "found":
            tag_hover_line = index.split(".")[0]
            tag = tag_flag

        # Point to our gui self.
        mygui = self.master.master

        # Make sure it is a good tag.
        try:
            item_data = mygui.items_for_selection[tag]
            item_type = item_data["item"]
            name = item_data["name"]
            text = f"{item_type.capitalize()}: {name}"
        except KeyError:
            return

        hover_handlers = {
            "task": self.hover_task,
            "profile": self.hover_profile,
            "scene": self.hover_scene,
            "project": self.hover_project,
            "found": self.hover_search,
        }

        # Determine the hover type and get the text associated with it.
        if item_type in hover_handlers:
            # If 'Search' match, get the owner.
            if item_type == "found":
                text, owner_text, max_len = hover_handlers[item_type](tag_hover_line)
                # Recalculate the max line length based on the window width.
                char_width_in_pixels = width_and_height_calculator_in_pixel(
                    "m",
                    PrimeItems.program_arguments["font"],
                    12,
                )[0]
                window_width_in_pixels = int(
                    PrimeItems.mygui.map_window_position.split("x")[0],
                )
                # Calculate ther max length for the second label (right-most text) = start_x position.
                max_len = min(
                    max_len,
                    (window_width_in_pixels // char_width_in_pixels) - 30,
                )
            else:
                owner_text = ""
                text = (
                    hover_handlers[item_type](tag, name, text)
                    if item_type == "task"
                    else hover_handlers[item_type](name, text)
                )
        else:
            return

        # Establish appropriate colors
        if is_color_dark(mygui.color_lookup["background_color"]):
            background_color = "#092944"
            foreground_color1 = "white"
            foreground_color2 = "yellow"
        else:
            background_color = "white"
            foreground_color1 = "black"
            foreground_color2 = "darkgreen"

        # Create the label.
        label = tk.Label(
            self,
            text=text,
            bg=background_color,
            fg=foreground_color1,
            justify="left",
            font=("Courier", 12),
            padx=5,
            pady=5,
        )
        # Place the label at the mouse position
        label.place(x=event.x + 100, y=event.y)
        self.hover_tooltip = label

        # If we have owner_text, draw as separate label overlay in different color.
        if owner_text:
            label1 = tk.Label(
                self,
                text=owner_text,
                bg=background_color,
                fg=foreground_color2,
                justify="left",
                font=("Courier", 12),
                padx=5,
                pady=5,
            )
            label1.place(
                x=event.x + (char_width_in_pixels * (max_len - 8)),
                y=event.y,
            )
            self.hover_tooltip = [label, label1]

    def hover_search(self, tag_hover_line: str) -> str:
        """
        Args:
            tag_hover_line (str): The tag position of the item being hovered over.
        Returns the text for the search tooltip.

        This method returns a string indicating that the item is a search result.

        Returns:
            str: The text indicating that the item is a search result.
        """
        text = ""
        owner_text = ""
        mygui = self.master.master
        textbox = self.textview_textbox
        indecies = mygui.items_for_selection["found"]["indecies"]
        max_len = 0
        gen_output = False
        number_out = 0
        allow_character_number = 100
        # Go through list of match indecies
        for index in indecies:
            text_line_num = index.split(".")[0]
            # Only generate output if we are on the same line as the hover line or beyond.
            if text_line_num == tag_hover_line:
                gen_output = True
            if not gen_output:
                continue
            text_line = f"{index.split('.')[0]}.0"
            line = textbox.get(text_line, text_line + " lineend")
            owner, _, _ = self.get_owner_name_from_textbox(
                textbox,
                text_line_num,
                line,
            )
            # Format the text for display.  Only display a maximum of 100 characters.
            if len(line) > allow_character_number:
                line = line[:allow_character_number]
            text += f"{line.strip()}\n"
            owner_text += f"{owner}\n"
            number_out += 1
            if owner:
                max_len = max(len(line), max_len)
            # Only do a maximum of 80 lines.
            if number_out > 80:
                text = "Displaying only the next 80 matches...\n" + text
                owner_text = "Displaying only the next 80 matches...\n" + owner_text
                max_len = max(40, max_len)
                break
        return text, owner_text, max_len

    def hover_project(self, name: str, text: str) -> str:
        """
        Retrieves project-related information and appends it to the tooltip text.

        This method finds the list of profiles in the project and appends this
        information to the provided tooltip text.

        Args:
            name (str): The name of the project.
            text (str): The initial text to append the project information to.

        Returns:
            str: The updated tooltip text including the list of profiles.
        """
        # Get the Project's properties (temporarily commented out for now).
        if name == "N/A":
            return ""
        properties = ""
        # Get a list of the Profiles and Tasks in the Project.
        profiles = get_profiles_in_project(name)
        tasks = get_tasks_in_project(name)

        # Merge the Profiles and Tasks lists.
        profiles_and_tasks = merge_lists(profiles, tasks)

        # Add column headings.
        max_profile_length = max((len(s) for s in profiles), default=0)
        max_task_length = max((len(s) for s in tasks), default=0)
        profile_header = f"{'Profiles'.ljust(max_profile_length, '.')}"
        task_header = f"{' Tasks in Project'.ljust(max_task_length, '.')}"
        profiles_and_tasks.insert(0, [f"\n\n{profile_header}", task_header])

        # Convert to columns.
        results_in_columns = parse_pairs_to_columns(profiles_and_tasks)
        return f"{text} {properties}{results_in_columns}"

    def hover_profile(self, name: str, text: str) -> str:
        """
        Retrieves profile-related information and appends it to the tooltip text.

        This method finds the project associated with the given profile name and
        retrieves the list of tasks in the profile. It appends this information to
        the provided tooltip text.

        Args:
            name (str): The name of the profile.
            text (str): The initial text to append the profile information to.

        Returns:
            str: The updated tooltip text including the project and task list.
        """
        # Get owning Profile and Project.
        if not name:
            return ""
        project = find_owning_project(name)
        tasks = get_tasks_in_project(project)

        # Can't combine the following into opne large 'f-string' since can not have '\' in f-string.
        temp = f"\n  In Project: {project}\n  Tasks in Project...\n"
        all_tasks = "\n   ".join(tasks)
        return text + f"{temp}   {all_tasks}"

    def hover_task(self, tag: str, name: str, text: str) -> str:
        """
        Get the Task related info and add it to the tooltip.

        Finds the Profile and Project associated with the Task and adds
        it to the tooltip.  Also, gets and adds the Task's properties.

        Parameters:
            self: The instance of the class.
            tag (str): The tag name of the item.
            name (str): The name of the item.
            text (str): The initial text to add to the tooltip.

        Returns:
            str: The updated tooltip text.
        """
        # Get the owning Profile.
        textbox = self.textview_textbox
        line_number = tag.split(".")[0]

        # See if this is a launcher task.  If it is, ignore it.
        _, prev_line, dont_got_line = find_the_line(
            textbox,
            name,
            line_number,
        )
        if not dont_got_line and "Launcher Task: " in prev_line:
            return ""

        # fmt: off
        owning_profile_name, line_num_found, line_found = self.get_owner_name_from_textbox(
                textbox,
                line_number,
                text,
            )
        # fmt: on

        # Get the owning Project.
        if owning_profile_name:
            owning_project_name, _, _ = self.get_owner_name_from_textbox(
                textbox,
                line_num_found,
                line_found,
            )
            # Check for situation in which there is a Project and no Profile (i.e. the Profile has the Project name).
            if owning_project_name == "<<< Owner=Project":
                owning_project_name = owning_profile_name
                owning_profile_name = ""
        else:
            return ""

        # Get the Properties
        properties = self.get_properties_for_hover("Task", name)

        # Get the list of Task actions.
        if UNNAMED_ITEM in name:
            task_id = get_taskid_from_unnamed_task(name)
            # Handle Tasks under Scenes with a Task ID.
            id_loc = task_id.find("ID:")
            if id_loc != -1:
                task_id = task_id[: id_loc - 1]
            # Get the Task XML element.
            task_xml = PrimeItems.tasker_root_elements["all_tasks"][task_id]["xml"]
            task_item = self.get_list_of_actions("", task_xml)
        elif name:
            task_item = self.get_list_of_actions(name, None)
        else:
            task_item = ""

        # Cleanup the text
        owning_profile_name = owning_profile_name.replace("<<< Owner=", "   ")
        owning_project_name = owning_project_name.replace("<<< Owner=", "   ")

        # Cleanup the line and return it for display
        return (
            text
            + f"\n {owning_profile_name}\n {owning_project_name}{properties}{task_item}"
        )

    def hover_scene(self, name: str, text: str) -> str:
        """
        Get the Scene related info and add it to the tooltip.

        Finds the Profile and Project associated with the Task and adds
        it to the tooltip.  Also, gets and adds the Task's properties.

        Parameters:
            self: The instance of the class.
            tag (str): The tag name of the item.
            name (str): The name of the item.
            text (str): The initial text to add to the tooltip.

        Returns:
            str: The updated tooltip text.
        """
        scene_xml = PrimeItems.tasker_root_elements["all_scenes"][name]["xml"]
        # Put the Scene's details into the output_lines.
        PrimeItems.output_lines.output_lines = []
        get_details(scene_xml, [], 0)
        # Get just the elements
        elements = [
            line
            for line in PrimeItems.output_lines.output_lines
            if "Element of type" in line
        ]
        for num, element in enumerate(elements):
            elements[num] = remove_html_tags(element, "").replace("&nbsp;", "")
        return text + "\nElements...\n" + "\n".join(elements)

    def get_list_of_actions(self, name: str, task_xml: defusedxml) -> str:
        """
        Retrieves the list of Actions for a given Task and appends them to a string.

        Finds the Task in the dictionary of all Tasks and retrieves the list of Actions.
        It then iterates through each Action, gets the 'code' element and appends it to
        the string in the format: "  <code>".

        Args:
            name (str): The name of the Task.

        Returns:
            str: The updated string with the list of Actions.
        """
        blank = " "
        task_item = "\n\nActions:"
        spacer = 0
        # Get the Task xml element
        if name:
            for task in PrimeItems.tasker_root_elements["all_tasks"].values():
                if task["name"] == name:
                    task_element = task["xml"]
                    break
        else:
            task_element = task_xml

        # Get the Task actions.
        try:
            task_actions = task_element.findall("Action")
        # Handle situations in which "Task:" appears elsewhere.
        except (AttributeError, UnboundLocalError):
            return ""
        if len(task_actions) > 0:
            shell_sort(task_actions, True, False)

        # Now go through each Action to start processing it.  They are in "argn" "n" order.
        for action in task_actions:
            child = action.find("code")  # Get the <code> element
            action_code = child.text
            display_level = PrimeItems.program_arguments["display_detail_level"]
            PrimeItems.program_arguments["display_detail_level"] = 2
            action_line = get_action_code(child, action_code, "", "t")
            PrimeItems.program_arguments["display_detail_level"] = display_level
            # Backup indentation if needed.
            if action_line in ("End", "Else", "Else/Else If", "End If", "End For"):
                spacer -= 3
            indentation = f"{blank * spacer}"
            # Format the action line
            task_item += f"\n    {indentation}{action_line}"
            # Calculate indentation
            if action_line in ("If", "Else", "Else/Else If", "For"):
                spacer += 3

        return task_item

    def get_owner_name_from_textbox(
        self,
        textbox: CTkTextview,
        text_line_num: str,
        line: str,
    ) -> tuple[str, str, str]:
        """
        Retrieves the owner name from a textbox widget by searching for specific keywords
        in the lines preceding a given line number.

        Args:
            textbox: The textbox widget containing the text to search.
            text_line_num (str): The line number (as a string) from which to start searching
                in reverse for the owner name.
            line (str): The current line of text being processed.

        Returns:
            tuple:
            - A formatted string containing the owner type and name if found,
            otherwise an empty string;
            - The line number of the owner or empty string;
            - The line of text where the owner was found.

        Notes:
            - The function searches for specific keywords ("Task: ", "Profile: ",
              "Project: ", "Scene: ") in the lines above the given line number.
            - If a match is found, it extracts the owner name and returns it in the
              format "Owning <owner_type>: <owner_name>  >>> ".
            - If no match is found, the function returns an empty string.
        """
        # Global variables are a special case.
        pgv = "Project Global Variables"
        if pgv == line:
            return f"<<< Owner={pgv}", "", ""
        owner_keys = [
            "Task: ",
            "Profile: ",
            "Project: ",
            "Scene: ",
            pgv,
        ]
        invalid_keys = [
            "Properties Collision Handling",
            "Run Both Together",
            " Properties",
        ]
        # Identify the possible owners based on what is in the line.
        if "Project: " in line:
            return "<<< Owner=Project", "", ""
        if "Profile: " in line:
            owner_keys.pop(0)  # Remove tasks
            owner_keys.pop(0)  # Remove profiles
        elif "Scene: " in line:
            owner_keys.pop(0)  # Remove tasks
            owner_keys.pop(0)  # Remove profiles
            owner_keys.pop()  # Remove scenes
        elif "Task: " in line:
            owner_keys.pop(0)  # Remove tasks

        # First make sure we are at the line number that contains the text we are starting from.
        line_to_get, prev_line, dont_got_line = find_the_line(
            textbox,
            line,
            text_line_num,
        )
        if dont_got_line:
            return "", "", ""

        # Get the lines in reverse, looking for the owner name.
        owner = ""
        while line_to_get != "0":
            # Get the line and check for the owner name.
            idx = f"{line_to_get}.0"
            prev_line = textbox.get(idx, idx + " lineend")
            if tasker_object := get_first_substring_match(prev_line, owner_keys):
                if tasker_object != pgv:
                    owner = prev_line.split(":")[1].split("   ")[0].strip()
                    owner = owner.split("(Not referenced by any ")[0].strip()
                    # Filter out 'Task:' that isn't a Task, and "Properties..."
                    if _ := any(
                        invalid_key in prev_line for invalid_key in invalid_keys
                    ):
                        line_to_get = str(int(line_to_get) - 1)
                        continue
                return (
                    f"<<< Owner={tasker_object}{owner.strip()}",
                    line_to_get,
                    prev_line,
                )
            # If not found, decrement the line number.
            line_to_get = str(int(line_to_get) - 1)
        return "", "", ""

    def click_name_leave(self, event: object) -> None:  # noqa: ARG002
        """
        Deletes the hover label.

        Args:
            event: The event object containing the coordinates of the mouse click.

        Returns:
            None: This function does not return anything.

        Raises:
            None: This function does not raise any exceptions.
        # Get the tags at that index
        tags_at_index = text_widget.tag_names(index)
        """
        with contextlib.suppress(AttributeError):
            destroy_hover_tooltip(self.hover_tooltip)

    def get_properties_for_hover(self, item_type: str, item_name: str) -> str:
        """
        Retrieves and formats the properties of a specified item type.

        Args:
            item_type (str): The type of the item (e.g., "Project", "Task").
            item_name (str): The name of the item whose properties are to be retrieved.

        Returns:
            str: A formatted string containing the properties of the item, or an empty
            string if no properties are found.

        Processing Logic:
            - Intializes a LineOut object to store output lines.
            - Retrieves the XML representation of the project's properties.
            - Searches the output lines for property information related to the specified
            item type.
            - Cleans and formats the properties for output.
        """
        # Get the item's XML so we can chase down its properities.
        xml = get_item_xml(item_type, item_name)
        if xml is None:
            return ""

        # Clear out the output and get the Project's properties
        PrimeItems.output_lines = LineOut()
        with contextlib.suppress(KeyError):
            get_properties(item_type, xml)

        # Get the properties from the properties output.
        properties = []
        search_key = f"{item_type} Properties"
        for line in PrimeItems.output_lines.output_lines:
            property_leadup = line.find(search_key)
            if property_leadup != -1:
                properties_with_html = line[
                    property_leadup + len(search_key) + 1 :
                ].replace("<br>", "\n")
                # Get rid of html
                properties_layed_out = re.sub(clean, "", properties_with_html)
                properties.append(
                    properties_layed_out.replace(",", "\n").replace("&nbsp;", ""),
                )
        if properties:
            return f"\n\nProperties: {' '.join(properties)}"
        return ""

    def highlight_bars(
        self,
        connector: dict,
        start_position: tuple,
        tag: str,
        char: str,
        direction: str,
    ) -> None:
        """
        Highlights bars in the specified direction from the given starting position in the Text widget.

        :param connector: The connector to highlight.
        :param start_position: Tuple indicating the row and column to start checking from.
        :param tag: The tag to apply to the highlighted text.
        :param char: The character to check for.
        :param direction: Direction to check, 'up' for above and 'down' for below.
        """
        line_num, col_num = start_position
        step = -1 if direction == "up" else 1

        # Adjust the starting line for the 'up' direction
        if direction == "up":
            line_num -= 2

        while (
            0 <= line_num < len(self.data)
            and len(self.data[line_num]) > col_num
            and self.data[line_num][col_num] == char
        ):
            line_to_highlight = line_num + 1
            self.textview_textbox.tag_add(
                tag,
                f"{line_to_highlight}.{col_num}",
                f"{line_to_highlight}.{col_num + 1}",
            )
            connector["extra_bars"].append((line_to_highlight, col_num))
            line_num += step

        # Adjust line number if at end of file.
        if line_num == len(self.data):
            line_num = len(self.data) - 1

        # Highlight the task name.
        if connector["task_upper"] and angle in self.data[line_num]:
            task_name = connector["task_upper"][0]
            # Make sure to point to the correct task if it is called multiple times on the same line.
            matches = find_all_positions(self.data[line_num], task_name)
            for match in matches:
                if match < col_num < match + len(task_name):
                    task_location = match
                    task_end = (task_location + len(task_name)) - 1
                    connector["task_upper"] = (
                        task_name,
                        line_num + 1,
                        task_location,
                        task_end,
                    )
                    self.textview_textbox.tag_add(
                        tag,
                        f"{line_num + 1}.{task_location}",
                        f"{line_num + 1}.{task_end + 1}",
                    )

    def highlight_bars_above(
        self,
        connector: dict,
        start_position: tuple,
        tag: str,
        char: str,
    ) -> None:
        """
        Highlights bars directly above the given starting position in the Text widget.
        """
        self.highlight_bars(connector, start_position, tag, char, direction="up")

    def highlight_bars_below(
        self,
        connector: dict,
        start_position: tuple,
        tag: str,
        char: str,
    ) -> None:
        """
        Highlights bars directly below the given starting position in the Text widget.
        """
        self.highlight_bars(connector, start_position, tag, char, direction="down")

    def add_highlight(
        self,
        tagid: str,
        line_num: int,
        highlight_start: int,
        highlight_end: int,
        _: str,
    ) -> None:
        """
        Adds a tag to the text box for the given highlight range.

        Args:
            tagid (str): The tag ID to add.
            line_num (int): The line number to add the highlight to.
            highlight_start (int): The start column of the highlight.
            highlight_end (int): The end column of the highlight.
            name (str): The name of the item being highlighted.

        Returns:
            None: This function does not return anything.
        """
        self.textview_textbox.tag_add(
            tagid,
            f"{line_num}.{highlight_start!s}",
            f"{line_num}.{highlight_end!s}",
        )
        self.textview_textbox.tag_bind(tagid, "<Button-1>", self.click_text)

    def highlight_item_names(self, tagid: str, line: str, line_num: int) -> None:
        """
        Highlights item names in the line.

        Args:
            tagid (str): The tag ID to add.
            line (str): The line to highlight.
            line_num (int): The line number to add the highlight to.

        Returns:
            None: This function does not return anything.

        This function highlights the item names in the line by getting the occurrences of the left_arrow_corner_up "║" character in the line.
        It then adds a tag to the text box for the given highlight range.
        """
        # Get the occurrences of left_arrow_corner_up "║" in the line and use it to determine start and end.
        occurrences = [i for i, c in enumerate(line) if c == "║"]
        # Get the locations of all icons in the names.
        icons = [
            i
            for i, char in enumerate(line)
            if ord(char) > 1000 and char not in ("│", "║")
        ]
        for num, occurrence in enumerate(occurrences):
            if num % 2 == 0:  # Even?
                highlight_start = occurrence + 2
                highlight_end = ""
            else:  # Odd?
                highlight_end = occurrence - 1
            # We have the name if odd (e.g. we have highlight_end).
            if highlight_end:
                # If icon in name, push out by number of icon positions.
                for num_icon, icon in enumerate(icons):
                    if highlight_start >= icon <= highlight_end:
                        highlight_end += num_icon + 1
                        highlight_start += num_icon + 2
                    break

                # Finally, add the highlighting.
                item_name = line[highlight_start:highlight_end]
                self.add_highlight(
                    tagid,
                    line_num,
                    highlight_start,
                    highlight_end,
                    item_name,
                )

    def highlight_text(self, line: str, line_num: int) -> None:
        """
        Main function to check the line of text for specific items to highlight
        and adds the corresponding tag to the text box for the given highlight range.
        """
        project_index, have_profile, have_task, have_scene = self.identify_items(line)

        if project_index != -1:
            self.handle_project_highlight(line, line_num, project_index)
        elif have_profile:
            self.highlight_item_names("profile", line, line_num)
        elif have_task:
            self.handle_task_highlight(line, line_num)
        elif have_scene:
            self.highlight_item_names("scene", line, line_num)

    def add_connector_tags(self, diagram_connectors: dict) -> None:
        """
        This function adds tags to the text box for the given connector range for each connector.

        It loops through the PrimeItems.diagram_connectors dictionary and for each key (line number),
        it adds a tag to the text box for the given highlight range.
        It also adds a tag for each bar in the list of bars.

        Args:
            diagram_connectors: Dictionary of connectors in the diagram.

        Returns:
            None
        """
        # Go through all of the connectors.
        for key, value in diagram_connectors.items():
            tagid = f"wire_{key!s}"
            # Add the tag for the top line
            self.textview_textbox.tag_add(
                tagid,
                f"{key}.{value['start_top'][1]!s}",
                f"{key}.{value['end_top'][1] + 1!s}",
            )
            # Add the tag for the bottom line.
            self.textview_textbox.tag_add(
                tagid,
                f"{value['start_bottom'][0]!s}.{value['start_bottom'][1]!s}",
                f"{value['end_bottom'][0]!s}.{value['end_bottom'][1] + 1!s}",
            )

            # Make them clickable.
            self.textview_textbox.tag_bind(tagid, "<Button-1>", self.click_text)

    def identify_items(self, line: str) -> tuple:
        """
        Identifies if the line contains 'Project:', 'Profile', 'Task', or 'Scene'.

        Returns:
            Tuple of:
            - project_index (int): Position of 'Project:' in the line (-1 if not found).
            - have_profile (bool): True if profile is found.
            - have_task (bool): True if task is found.
            - have_scene (bool): True if scene is found.
        """
        have_profile = have_task = have_scene = False

        # Check for Project
        project_index = line.find("Project:")
        if project_index != -1:
            return project_index, False, False, False

        # Check for Task or Profile/Scene
        if "└─" in line:
            have_task = True
        elif "║" in line:
            if "Scenes:" in line:
                have_scene = True
            else:
                have_profile = True

        return project_index, have_profile, have_task, have_scene

    def handle_project_highlight(
        self,
        line: str,
        line_num: int,
        project_index: int,
    ) -> None:
        """
        Handles highlighting for a project item.
        """
        highlight_start = project_index + 9
        highlight_end = line.find("║", highlight_start) - 1
        project_name = line[highlight_start:highlight_end]
        self.add_highlight(
            "project",
            line_num,
            highlight_start,
            highlight_end,
            project_name,
        )

    def handle_task_highlight(self, line: str, line_num: int) -> None:
        """
        Handles highlighting for a task item.
        """
        hits = ["[Called by ", "[Calls ", "(entry)", "(exit)", "  "]
        highlight_start = line.find("└─") + 3
        highlight_end = self.find_task_end(line, highlight_start, hits)
        task_name = line[highlight_start:highlight_end]

        self.add_highlight("task", line_num, highlight_start, highlight_end, task_name)

    def find_task_end(self, line: str, highlight_start: int, hits: list) -> int:
        """
        Determines the end position of a task based on specific delimiters.

        Returns:
            int: The end position for the highlight.
        """
        have_end = False
        for deliminator in hits:
            position = line.find(deliminator, highlight_start)
            if position != -1:
                have_end = True
                break

        highlight_end = position - 1 if have_end else len(line)
        if deliminator == "  ":
            highlight_end += 1

        return highlight_end

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
            PrimeItems.program_arguments["map_window_position"] = (
                self.master.master.window_position
            )

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
        # Define the progress bar.  Import must stay here to avoid circular import.
        from maptasker.src.diagram import configure_progress_bar  # noqa: PLC0415

        progress = configure_progress_bar(the_data, "Map")
        progress.update(
            {
                "max_data": len(the_data),
                "tenth_increment": max(
                    1,
                    len(the_data) // 10,
                ),  # Avoid division by zero
                "self": self.master.master,
            },
        )
        # self.master.master.progress_bar = progress
        check_bump = self.check_bump
        master_debug = self.master.master.debug
        log_info = (
            logger.info if master_debug else lambda *_: None
        )  # No-op if debug is off
        process_directory = self.process_directory
        process_colored_text = self.process_colored_text
        PrimeItems.track_task_warnings = []
        previous_text = ""

        # Go through the data and format it accordingly.
        for num, (_, value) in enumerate(the_data.items()):
            if not progress:  # If progress bar has been destroyed, quick get out.
                return
            if num % progress["tenth_increment"] == 0:
                progress["progress_counter"] = num
                display_progress_bar(progress, is_instance_method=True)

            # Get the text of the value and ignore duplicate blank lines.
            response, previous_text, text = self.do_special_spacing(
                previous_text,
                value,
                line_num,
                char_position,
                tags,
            )
            if not response:
                continue

            # Check to see if we need to bump the line number.
            line_num, char_position = check_bump(
                line_num,
                char_position,
                previous_value,
                value,
            )

            # Check if we need to change the color
            if not value["color"] and value["text"]:
                value["color"] = [previous_color]

            # Go through all the text/color combinations
            if value.get("color"):
                line_num, previous_color, previous_value, tags = process_colored_text(
                    value,
                    line_num,
                    previous_color,
                    previous_value,
                    tags,
                )
                if text[0] == "Directory\n":
                    line_num, previous_directory, previous_value, char_position = (
                        self.one_level_up(
                            line_num,
                            previous_directory,
                            previous_value,
                            char_position,
                        )
                    )
            elif "directory" in value:
                char_position, previous_directory, line_num = process_directory(
                    value,
                    line_num,
                    previous_directory,
                    0 if previous_value != "directory" else char_position,
                )
                previous_value = "directory"

            # Log debug information if enabled
            log_info(f"Map View Value: {value}")

        # Stop the progress bar and destroy the widget
        kill_the_progress_bar(progress, remove_windows=False)

    def do_special_spacing(
        self: object,
        previous_text: str,
        value: dict,
        line_num: int,
        char_position: int,
        tags: list,
    ) -> tuple:
        """
        Add any special spacing to the text as needed.

        Parameters:
            self: object - The instance of the class.
            previous_text: str - The previous text.
            value: dict - The value to generate a comment for.
            line_num: int - The line number.
            char_position: int - The character position.
            tags: list - A list of tags.

        Returns:
            tuple: The updated line number, previous text, and text.
        """
        text = value.get("text", [])
        if text and isinstance(text, list):
            if previous_text == "\n" and text[0] == "\n":
                return False, previous_text, text
            previous_text = text[0]
            # Handle special spacing for directory headings
            if text[0].startswith("\nn"):
                # If dictionary header, then let's add a leading blank line.
                # Add hyperlink directory entry
                tag_id = self._generate_unique_tag_id(line_num, char_position, tags)
                self.textview_textbox.tag_config(
                    tag_id,
                    background=make_hex_color(
                        self.master.master.color_lookup["background_color"],
                    ),
                )
                self.textview_textbox.insert("end", "\n", tag_id)
        return True, previous_text, text

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
            value = {
                "directory": ["%%projects", find_owning_project(single_profile)],
            }
        elif single_task:
            single_profile_name = find_owning_profile(single_task)
            if not single_profile_name:
                value = {
                    "directory": [
                        "%%projects",
                        self.find_task_owning_project(single_task),
                    ],
                }
            else:
                value = {"directory": ["%%profiles", single_profile_name]}

        char_position, previous_directory, line_num = self.process_directory(
            value,
            line_num,
            previous_directory,
            char_position,
        )
        return line_num, previous_directory, "directory", char_position

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
            if any(
                all_tasks[task_id]["name"] == task_name
                for task_id in get_ids(False, project_value["xml"], "", [])
            ):
                return project_value["name"]
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

        Parameters:
            value (dict): The colored text element to process.
            line_num (int): The current line number.
            previous_color (str): The color of the previous element.
            previous_value (str): The value of the previous element.
            tags (list): A list of tags for the colors of the elements.

        Returns:
            tuple: Updated line number, the previous color, the tag for the color, and the list of tags.
        """
        text = value["text"][0]

        if text == "Directory\n":
            # Replace text with the formatted directory description
            value["text"] = ["Directory    (blue entries are hotlinks)\n \n"]

        # Process directory headings (e.g. 'Projects...')
        elif text.startswith("\nn"):
            # Save and temporarily update text and color
            save_text = text[2:]
            save_color = value["color"]
            value["text"][0] = "\n"

            # Output current text and increment line number
            previous_color = self.output_map_text_lines(
                value,
                line_num,
                tags,
                previous_color,
                previous_value,
            )
            line_num += 1
            # return line_num + 1, previous_color, "color", tags

            # Restore original text and color
            value["text"][0] = save_text
            value["color"] = save_color

        # Output the updated text and color
        previous_color = self.output_map_text_lines(
            value,
            line_num,
            tags,
            previous_color,
            previous_value,
        )

        # Return updated parameters
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
        spacing, columns = 50, 3
        directory_type = value["directory"][0]
        # We don't support Grand Totals hotlinks (yet)
        if directory_type in {"grand", "</td"}:
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
            # Normal directory entry.  If name greater than spacing allows, truncate it.
            if len(hotlink_name) > spacing:
                name_to_insert = hotlink_name[: spacing - 3] + "   "
                # Add the Profile ID if this is a profile with no name.
                # Make it look like: 'some_profile_name.123...'
                if name_to_insert.startswith("*") and (
                    prof_id := extract_number_from_line(hotlink_name)
                ):
                    name_to_insert = hotlink_name[: spacing - 6] + "   "
                    name_to_insert = (
                        name_to_insert[: spacing - 7]
                        + "."
                        + prof_id
                        + name_to_insert[spacing - 6 :]
                    )

            else:
                name_to_insert = hotlink_name

            # Determine additional space to add to lines if needed.
            spacer = "\n" if char_position == spacing * columns - spacing else ""
            # Take care of special characters.
            name_to_insert = name_to_insert.replace("&gt;", ">").replace("&lt;", "<")
            name_to_insert = f"{name_to_insert.ljust(spacing, ' ')}{spacer}"

        name_to_go_up = name_to_go_up.replace("&gt;", ">").replace("&lt;", "<")
        # Add hyperlink directory entry
        tag_id = self.textview_hyperlink.add([directory_type, name_to_go_up])
        # Note: If user double-clicks a button, the textbox is not valid on the second click.
        try:
            self.textview_textbox.insert(
                f"{line_num_str}.{char_position}",
                name_to_insert,
                tag_id,
            )
        except TclError:
            return char_position, previous_directory, line_num + (char_position == 0)
        # Configure the tag for the hyperlink in the background color
        self.textview_textbox.tag_config(
            tag_id[1],
            background=make_hex_color(
                self.master.master.color_lookup["background_color"],
            ),
        )

        char_position = (
            0 if char_position == spacing * columns else char_position + spacing
        )
        previous_directory = directory_type

        # Add a second "up one more level" hotlink
        if up_one_level and name_to_go_up != "entire configuration":
            new_char_pos = len(hotlink_name) + 10

            if directory_type:
                if directory_type == "profiles_up":
                    name_to_go_up = find_owning_project(name_to_go_up)
                    go_up_type = "projects_up"
                    name_object = "Project:"
                elif directory_type == "tasks_up":
                    name_to_go_up = find_owning_profile(name_to_go_up)
                    go_up_type = "profiles_up"
                    name_object = "Profile:"
                else:
                    # We're at the Project level. Do nothing.
                    go_up_type = "all"
                    name_to_go_up = "entire configuration"
                    name_object = ""
            else:
                go_up_type = directory_type

            # If we are going up a second level, we need to insert the second "up one more level" hotlink
            if go_up_type:
                hotlink_name = f"Up Two Levels to {name_object} {name_to_go_up}"
                tag_id = self.textview_hyperlink.add([f"{go_up_type}", name_to_go_up])
                self.textview_textbox.insert(
                    f"{line_num_str}.{new_char_pos}",
                    f"     {hotlink_name}",
                    tag_id,
                )
                self.textview_textbox.tag_config(
                    tag_id[1],
                    background=make_hex_color(
                        self.master.master.color_lookup["background_color"],
                    ),
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
        Outputs the given map data to a text box, determining colors, highlights, and formatting.
        """
        spaces = " " * 20
        line_num_str = str(line_num)
        char_position = 0

        # Pre-compute the background color
        background_color = make_hex_color(
            self.master.master.color_lookup["background_color"],
        )
        pretty = self.master.master.pretty
        debug = self.master.master.debug

        # Iterate over a list or a string.
        for num, message in enumerate(
            value["text"] if isinstance(value["text"], list) else [value["text"]],
        ):
            # If the text is not a list, just get the string.
            if message == "     \n":
                continue
            # Formats the message for pretty output, debug, and specific cases.
            formatted_message = self._format_message(
                message,
                previous_value,
                spaces,
                pretty,
                debug,
            )
            if not formatted_message:
                continue

            # Determine if this is the last item and add a newline if necessary
            if formatted_message == value["text"][-1] and "\n" not in formatted_message:
                formatted_message += "\n"

            tag_id = self._generate_unique_tag_id(line_num_str, char_position, tags)

            # If new line, just do it and get out.
            if message == "\n":
                self.textview_textbox.insert("end", "\n", tag_id)
            else:
                char_position = self._insert_message(
                    line_num_str,
                    char_position,
                    formatted_message,
                    tag_id,
                    background_color,
                )
            previous_color = self._handle_color_and_highlighting(
                value,
                tags,
                previous_color,
                previous_value,
                num,
                formatted_message,
                tag_id,
            )

        return previous_color

    def _format_message(
        self,
        message: str,
        previous_value: str,
        spaces: str,
        pretty: bool,
        debug: bool,  # noqa: ARG002
    ) -> str:
        """Formats the message for pretty output, debug, and specific cases."""
        # Clean up the message content
        message = message.replace("\n\n", "\n").replace("Go to top", "")

        # Handle special case for 'directory'
        if previous_value == "directory" and "Project:" in message:
            message = f"\n{message}"

        # Short-circuit for empty messages
        if message.strip() == "      ":
            return ""

        # Format for pretty output
        if pretty and message.startswith(spaces):
            message = f"  {message}"

        # Add debug information
        # if debug:
        #    message = f"{line_num_str} {message}"

        return message

    def _generate_unique_tag_id(
        self,
        line_num_str: str,
        char_position: int,
        tags: set,
    ) -> str:
        """Generates a unique tag ID for the text box."""
        tag_id = f"{line_num_str}.{char_position}"
        while tag_id in tags:
            tag_id = f"{tag_id}{random.randint(100, 999)}"  # noqa: S311
        tags.append(tag_id)
        return tag_id

    def _insert_message(
        self,
        line_num_str: str,
        char_position: int,
        message: str,
        tag_id: str,
        background_color: str,
    ) -> int:
        """Inserts the formatted message into the text box and applies the necessary tags."""
        start_idx = f"{line_num_str}.{char_position}"
        end_idx = f"{line_num_str}.{char_position + len(message)}"

        # Handle Task Action Limit Warnings: too many actions. We have to break it up into 3 pieces:
        # 1. Before the Task name.
        # 2. The Task name as a hyperlink.
        # 3. After the Task name.
        # if message.startswith("Task ") and message.endswith("actions\n"):
        if find_task_pattern(message):
            # Get the Task name.
            got_it = False
            for task_name in PrimeItems.task_action_warnings:
                if f"Task {task_name} has" in message:
                    got_it = True
                    break
            if not got_it:
                _ = self._insert_text_and_tag(start_idx, end_idx, message, tag_id)
                return char_position
            if task_name not in message:
                rutroh_error(f"Task {task_name} not found in the message, '{message}'!")

            # Get the insertion positions.
            taskname_start = message.find(task_name)
            taskname_end = taskname_start + len(task_name)

            # Check to see if we have already done this Task.
            if task_name in PrimeItems.track_task_warnings:
                return char_position
            PrimeItems.track_task_warnings.append(task_name)

            # Add #1.
            end_start = (
                f"{line_num_str}.{char_position + 5!s}"  # 5 is the length of "Task "
            )
            if not self._insert_text_and_tag(start_idx, end_start, "Task ", tag_id):
                return char_position

            # Add #2.
            # Add hyperlink tag for this task name.
            hyper_tag_id = self.textview_hyperlink.add(["tasks", task_name])
            taskname_start_idx = f"{line_num_str}.{char_position + taskname_start!s}"
            taskname_end_inx = f"{line_num_str}.{char_position + taskname_end!s}"
            if not self._insert_text_and_tag(
                taskname_start_idx,
                taskname_end_inx,
                task_name,
                hyper_tag_id,
            ):
                return char_position

            # Add #3.
            message = message.replace(task_delimeter, "")
            trailer_start_idx = f"{line_num_str}.{char_position + taskname_end + 1!s}"
            if not self._insert_text_and_tag(
                trailer_start_idx,
                end_idx,
                f" {message[taskname_end + 1 :]}",
                tag_id,
            ):
                return char_position

        # Just normal text.  Insert it.
        elif not self._insert_text_and_tag(start_idx, end_idx, message, tag_id):
            return char_position

        # Tag items for hover and background highlight
        if ": Properties" not in message and any(
            keyword in message
            for keyword in ("Task: ", "Profile: ", "Project: ", "Scene: ")
        ):
            self.tag_items(tag_id, message)
            self.textview_textbox.tag_config(tag_id, background=background_color)

        return char_position + len(message)

    def _insert_text_and_tag(
        self,
        start_idx: str,
        end_idx: str,
        message: str,
        tag_id: str,
    ) -> None:
        # Insert the message into the text box
        try:
            self.textview_textbox.insert(start_idx, message, tag_id)
        except TclError:
            return False
        self.textview_textbox.tag_add(tag_id, start_idx, end_idx)
        return True

    def _handle_color_and_highlighting(
        self,
        value: dict,
        tags: set,
        previous_color: str,
        previous_value: str,
        num: int,
        message: str,
        tag_id: str,
    ) -> str:
        """Determines the color and highlighting settings for the current message."""
        if (
            "Color for Background set to" in message
            or "highlighted for visibility" in message
        ):
            color = "White"
        else:
            color, tags = self.output_map_colors_highlighting(
                value,
                tags,
                previous_color,
                previous_value,
                num,
                message,
                tag_id,
                previous_color,
            )

        # Apply color settings to the tag
        background_color = make_hex_color(
            self.master.master.color_lookup["background_color"],
        )
        self.textview_textbox.tag_config(
            tag_id,
            foreground=color,
            background=background_color,
        )
        return color

    def tag_items(self, tag_id: str, message: str) -> None:
        """
        Tag items in the message with their item type (task, profile, or project)
        and bind the <Enter> and <Leave> events to the click_name function.
        Save the items in MyGui.items_for_selection

        Parameters:
            tag_id (str): The tag id to assign to the item.
            message (str): The message to parse.

        Returns:
            None
        """
        keywords = {
            "Task: ": "task",
            "Profile: ": "profile",
            "Project: ": "project",
            "Scene: ": "scene",
            "Found:": "found",
        }
        # Find the first matching keyword and corresponding item type
        item, start_position = next(
            (
                (value, message.find(keyword) + len(keyword))
                for keyword, value in keywords.items()
                if keyword in message
            ),
            (None, None),
        )
        # If we have a valid Tasker item and it isn't a Launcher name.
        if item and not item.startswith(" [Launcher Task: "):
            self.textview_textbox.tag_bind(tag_id, "<Enter>", self.click_text)
            self.textview_textbox.tag_bind(tag_id, "<Leave>", self.click_name_leave)

            end_position = message.find("   ", start_position)
            # Get the name of the item
            name = message[start_position:end_position]
            not_referenced = name.find("(Not referenced by")
            if not_referenced != -1:
                name = name[: not_referenced - 1]
            name = name.strip()

            self.master.master.items_for_selection[tag_id] = {
                "item": item,
                "name": name,
                "start_position": start_position,
                "end_position": end_position,
            }

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
            color = self.master.master.color_lookup.get(f"{value['color'][num]}")

            # If color is None, then it wasn't found in the lookup table.  It is a raw color name.
            if color is None and value["color"][num] != "n/a":
                color = value["color"][num]
            elif (color is None and value["color"][num] == "n/a") or "-" in color:
                color = previous_color
            else:
                previous_color = color
        except IndexError:
            color = previous_color

        # Deal with a hex value for color
        if color and color.isdigit():
            color = f"#{color}"
        return color, tags

    def add_highlights(
        self,
        message: str,
        value: dict,
        previous_value: str,
        tag_id: str,
        tags: list,
    ) -> list:
        """
        Add highlights to the text box based on a dictionary of highlight configurations.
        """
        highlight_configurations = {
            "bold": {"font": self.bold_font},
            "italic": {"font": self.italic_font},
            "underline": {"underline": True},
            "mark": {"background": PrimeItems.colors_to_use["highlight_color"]},
        }

        search_word_mapping = {
            "Task: ": "Task: ",
            "Profile: ": "Profile: ",
            "Project: ": "Project: ",
            "Scene: ": "Scene: ",
        }

        # Find the search word context
        search_word = next(
            (word for word in search_word_mapping if word in message),
            None,
        )
        if not search_word:
            return tags  # No valid highlight context found

        for highlight in value.get("highlights", []):
            highlight_type, highlight_text = self._parse_highlight(highlight)

            if not highlight_type or highlight_type not in highlight_configurations:
                rutroh_error(
                    f"gywin parse failed {highlight_type} {highlight_text}  '{message}'",
                )
                continue

            start_pos, end_pos = self._get_highlight_positions(
                message.rstrip(),
                highlight_text,
                previous_value,
            )
            if start_pos == -1:
                rutroh_error(
                    f"gywin position not found {highlight_type} {highlight_text}  '{message}'",
                )
                continue

            line_to_highlight = self._find_highlight_line(search_word)
            if line_to_highlight is None:
                rutroh_error(
                    f"gywin find line failed {highlight_type} {highlight_text}  '{message}'",
                )
                continue

            new_tag = f"{tag_id}{highlight_type}"
            tags.append(new_tag)
            self._apply_highlight(
                new_tag,
                line_to_highlight,
                start_pos,
                end_pos,
                highlight_configurations[highlight_type],
            )
            # Do highlighting as well, if needed.
            if "<mark>" in highlight_text:
                new_tag = f"{tag_id}highlight"
                tags.append(new_tag)
                self._apply_highlight(
                    new_tag,
                    line_to_highlight,
                    start_pos,
                    end_pos,
                    {"background": PrimeItems.colors_to_use["highlight_color"]},
                )

            # if self.master.master.debug:
            #    self._debug_highlight(line_to_highlight, start_pos, end_pos, tag_id)

        return tags

    def _parse_highlight(self, highlight: str) -> tuple:
        """Parse a highlight string into type and text."""
        try:
            return highlight.split(",", 1)
        except ValueError:
            return None, None

    def _get_highlight_positions(
        self,
        message: str,
        highlight_text: str,
        previous_value: str,
    ) -> tuple:
        """Determine the start and end positions of the highlight text."""
        tags_to_remove = ["<mark>", "</mark>", "<em>", "</em>", "<b>", "</b>"]
        for tag in tags_to_remove:
            highlight_text = highlight_text.replace(tag, "")
        start_pos = message.find(highlight_text)
        if start_pos == -1:
            return -1, -1

        end_pos = len(highlight_text) + start_pos

        # Adjust positions for "directory" case
        if previous_value == "directory":
            start_pos = max(0, start_pos - 1)
            end_pos = -max(0, end_pos - 1)

        return start_pos, end_pos

    def _find_highlight_line(self, search_word: str) -> str:
        """Find the line number containing the search word."""
        line_count = int(self.textview_textbox.index("end-1c").split(".")[0])
        for line_num in range(line_count, 0, -1):
            line_text = self.textview_textbox.get(
                f"{line_num}.0",
                f"{line_num}.0 lineend",
            )
            if search_word in line_text:
                return str(line_num)
        return None

    def _apply_highlight(
        self,
        tag: str,
        line: str,
        start: int,
        end: int,
        config: dict,
    ) -> None:
        """Apply a highlight to the specified range."""
        self.textview_textbox.tag_add(tag, f"{line}.{start}", f"{line}.{end}")
        self.textview_textbox.tag_config(tag, **config)

    def _debug_highlight(self, line: str, start: int, end: int, tag_id: str) -> None:
        """Output debug information for the highlight."""
        line_num = int(line) - 2
        print(
            f"GUIWINS Debug: Line {line_num}, Start {start}, Line {line_num}, End {end}, Tagid {tag_id}",
        )
        self.textview_textbox.insert(
            f"{line_num}.{end + 1}",
            "<< Here is a highlight >>",
            tag_id,
        )

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
            output_label(self, f"Text '{content}' copied to clipboard.")
            return "break"
        # Ctrl+V ...paste
        if event.state == 4 and event.keysym == "v":
            self.textview_textbox.insert(
                "end",
                self.selection_get(selection="CLIPBOARD"),
            )
            return "break"
        return "break"

    def delay_event(self) -> None:
        """
        A method that handles the delay event for the various text views.
        It deletes the label after a certain amount of time.
        """
        # Catch error caused bvy a possible double-click.
        try:
            self.text_message_label.destroy()
        except AttributeError:
            return
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
# Create a custom application class "App" that inherits from CTk (Custom Tkinter)
class ProgressbarWindow(ctk.CTk):
    """Define our top level window for the Progressbar view."""

    def __init__(self) -> None:
        """Initialize our top level window for the Progressbar view."""
        # Call the constructor of the parent class (CTk) using super()
        super().__init__()

        # Get the map window position
        # window_position = PrimeItems.program_arguments["map_window_position"].split("+")
        # dimensions = window_position[0].split("x")

        # Create the progress bar...
        self.progressbar = ctk.CTkProgressBar(
            self,
            width=300,
            height=50,
            corner_radius=20,
            border_width=2,
            border_color="turquoise",
            # fg_color="green",
        )
        # self now points to the ProgressbarWindow.

        # Save the window position on closure
        self.protocol("WM_DELETE_WINDOW", lambda: on_closing(self))

        self.progressbar.set(0.0)  # Start with progress of 0.
        self.progressbar.pack(padx=20, pady=20)

        # Setup values so we can determine the amount of time before we issue an IMKClient message.
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
            delay = 0  # Override delay since we are not doing the animation (it doesn't work)
            self.after(delay, self.popup_button_event)

        # Label widget
        # our_label = message
        self.text = ""
        self.count = 0
        self.Popup_label = ctk.CTkLabel(
            master=self,
            text=self.text,
            font=("", 24),
            text_color="turquoise",
        )
        self.Popup_label.grid(row=0, column=0, padx=0, pady=10, sticky="n")

        # Basic appearance for text, foreground and background.
        self.Popup_bg_color = self._apply_appearance_mode(
            ctk.ThemeManager.theme["CTkFrame"]["fg_color"],
        )
        self.Popup_text_color = self._apply_appearance_mode(
            ctk.ThemeManager.theme["CTkLabel"]["text_color"],
        )
        self.selected_color = self._apply_appearance_mode(
            ctk.ThemeManager.theme["CTkButton"]["fg_color"],
        )

        # Set up the style/theme
        self.Popup_style = ttk.Style(self)
        self.Popup_style.theme_use("default")

        # Display the message
        self.Popup_label.configure(text=message)
        self.Popup_label.focus_set()

        ## Animate the text so it is more visable
        # def slider() -> None:
        #    """
        #    Animates the text on the Popup_label widget by gradually displaying each character from the `our_label` string.

        #    This function is called recursively using the `after` method to create a sliding effect. It checks if the
        #    current index `count` has reached the length of `our_label`. If it has, it resets the `count` to -1 and
        #    clears the `text` variable. If not, it appends the character at the current index to the `text` variable
        #    and updates the `Popup_label` widget with the new text. The `count` is incremented and the `slider`
        #    function is called again after a delay of 5 milliseconds.

        #    Parameters:
        #        None

        #    Returns:
        #        None
        #    """
        #    if self.count >= len(our_label):
        #        self.count = -1
        #        self.text = ""
        #        return
        #    self.text = self.text + our_label[self.count]
        #    self.Popup_label.configure(text=self.text)
        #    self.count += 1
        #    self.after(1, slider)

        ## Set the focus on our popup window and start the animation.
        # self.Popup_label.focus_set()
        # slider()

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
        self.text.tag_bind("hyper", "<Motion>", self._enter)
        self.links = {}

    def add(self, link: str) -> tuple:
        """
        Adds a hyperlink to the CTkHyperlinkManager.

        Args:
            link (str): The hyperlink to add.


        Returns:
            tuple: A tuple containing the type of link ("hyper") and the tag of the link.
        """
        tag = f"hyper-{len(self.links)}"
        self.links[tag] = link
        return "hyper", tag

    def _enter(self, event: object) -> None:
        """
        Set the cursor to a hand pointer when the mouse enters the text widget.

        Args:
            event (object): The event object.

        Returns:
            None
        """
        tasker_object = {
            "_up": "Up",
            "tasks": "Task",
            "profiles": "Profile",
            "scenes": "Scene",
        }
        # Set the cursor to a hand pointer.
        self.text.configure(cursor="hand2")

        # Find the tag associated with the item entered so we can add hover text.
        for tag in self.text.tag_names(ctk.CURRENT):
            # Delete any previous hover tooltip.
            with contextlib.suppress(AttributeError):
                destroy_hover_tooltip(self.hover_tooltip)
            if tag.startswith("hyper-"):
                link = self.links[tag]
                if link[0] in tasker_object:
                    # Add a hover text to the link entered of the name of the link.
                    label = tk.Label(
                        event.widget.master,
                        text=f"{tasker_object[link[0]]}: {link[1]}",
                        bg="#092944",
                        justify="left",
                        padx=5,
                        pady=5,
                    )
                    # Place the label at the mouse position
                    label.place(x=event.x + 100, y=event.y)
                    self.hover_tooltip = label

    def _leave(self, event: object) -> None:  # noqa: ARG002
        """
        Set the cursor to the default cursor when the mouse leaves the text widget.

        Args:
            event (object): The event object.

        Returns:
            None
        """
        self.text.configure(cursor="xterm")
        # Delete any previous hover tooltip.
        with contextlib.suppress(AttributeError):
            destroy_hover_tooltip(self.hover_tooltip)

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
                    # Go up one level: Remap single Project/Profile/Task
                    action, name = link
                    guiself = event.widget.master.master.root.master
                    self.remap_single_item(action, name, guiself)
                else:
                    webbrowser.open(link)
                return

    def remap_single_item(self, action: str, name: str, guiself: ctk) -> None:
        """
        Remap with a single item based on action type.

        Args:
            action (str): The type of action to perform (e.g., 'projects', 'profiles', 'tasks').
            name (str): The name of the item to remap.
            guiself (ctk): The GUI self-reference.

        Returns:
            None: This function does not return anything.
        """
        # Unsupported hotlinks
        if action == "grand":
            nogo_name = "Grand Totals"
            guiself.display_message_box(
                f"'{nogo_name}' hotlinks are not working yet.",
                "Orange",
            )
            return

        # Handle "up" actions
        if action.endswith("_up"):
            action = action.removesuffix("_up")
            self.rebuildmap_single_item(action, name, guiself)
            return

        # Map action to corresponding root elements
        action_map = {
            "tasks": PrimeItems.tasker_root_elements["all_tasks"],
            "profiles": PrimeItems.tasker_root_elements["all_profiles"],
            "projects": PrimeItems.tasker_root_elements["all_projects"],
            "scenes": PrimeItems.tasker_root_elements["all_scenes"],
        }

        # If this is an unnamed Task in a Scene, remove the scene part of the name.
        cleaned_name = name.replace(" (Scene)", "").strip()

        # If we find a match, then point to it and return.
        if action in action_map and self.name_in_list(cleaned_name, action_map[action]):
            # Search for and point to the item in the map view
            self.find_and_point_to_item(action, name, cleaned_name, guiself)
            return

        # No match found. Rebuild the map for the given name.
        self.rebuildmap_single_item(action, cleaned_name, guiself)

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
        if action == "grand":
            nogo_name = "Grand Totals"
            guiself.display_message_box(
                f"'{nogo_name}' hotlinks are not working yet.",
                "Orange",
            )
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
            update_tasker_object_menus(
                guiself,
                get_data=False,
                reset_single_names=False,
            )
            # Remap it.
            guiself.remapit(clear_names=False)

    def name_in_list(self: object, name: str, tasker_items: dict) -> bool:
        """
        Determine if a specific name is in a dictionary of items.

        Args:
            name (str): The name to search for.
            tasker_items (dict): The dictionary of tasker items (Project/Profiles/Tasks to search in.

        Returns:
            bool: True if the name is found, False otherwise.
        """
        # return any(tasker_items[key]["name"] == name for key in tasker_items)
        names = {tasker_items[key]["name"] for key in tasker_items}
        return name in names

    # Search for and point to the specific item in the textbox.
    def find_and_point_to_item(
        self,
        action: str,
        orig_name: str,
        name: str,
        guiself: ctk,
    ) -> None:
        """
        Search for and point to the specific item in the textbox.

        Args:
            action (str): The type of action to perform (e.g., 'projects', 'profiles', 'tasks').
            orig_name (str): The original name of the item to point to.
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
        search_hits = search_substring_in_list(
            search_list,
            search_string,
            stop_on_first_match=True,
        )
        if not search_hits:
            message = f"Could not find '{search_string}' in the list."
            guiself.display_message_box(message, "Orange")
            output_label(guiself.textview, message)
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
        if "(Scene)" in orig_name:
            length_to_use = len(search_string) - 6
        else:
            length_to_use = len(search_string)
        our_view.textview_textbox.tag_remove("inlist", "1.0", "end")
        our_view.textview_textbox.tag_add(
            "inlist",
            f"{line_num}.{line_pos!s}",
            f"{line_num}.{(line_pos + length_to_use)!s}",
        )
        highlight_configurations = {
            "mark": {"background": PrimeItems.colors_to_use["highlight_color"]},
        }
        our_view.textview_textbox.tag_config(
            "inlist",
            **highlight_configurations["mark"],
        )


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
    logger.info("Initializing GUI...")
    initialize_variables(self)


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
    self.ai_apikey_window = None
    self.ai_apikey_window_position = ""
    # self.ai_missing_module = None
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
    self.list_unnamed_items = False
    self.view_limit = 10000
    self.map_window_position = ""
    self.map_in_progress = False
    self.mapview_window = None
    self.named_item = None
    self.outline = False
    self.preferences = None
    self.profiles_per_line = DIAGRAM_PROFILES_PER_LINE
    # self.progressbar_window_position = ""
    self.pretty = False
    self.rerun = None
    self.reset = None
    self.reset_debug_at_end = False
    self.restore = False
    self.runtime = False
    self.save = False
    self.single_profile_name = None
    self.single_project_name = None
    self.single_task_name = None
    self.task_action_warning_limit = 20
    self.tab_to_use = None
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
    self.grid_rowconfigure(
        (0, 3),
        weight=4,
    )  # Divvy up the extra space needed equally amonst the 4 rows: 0-thru-3

    # load and create background image

    # create sidebar frame with widgets on the left side of the window.
    self.sidebar_frame = ctk.CTkFrame(self, width=140, corner_radius=0)
    self.sidebar_frame.configure(bg_color="black")
    self.sidebar_frame.grid(row=0, column=0, rowspan=19, sticky="nsew")
    # Define sidebar background frame with 17 rows
    self.sidebar_frame.grid_rowconfigure(
        22,
        weight=1,
    )  # Make anything in rows 20-xx stretchable.


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
    logger.info("Initializing screen...")

    # Save the window position on closure
    self.protocol("WM_DELETE_WINDOW", lambda: on_closing(self))

    # Display the frame title
    self.logo_label = add_label(
        self,
        self.sidebar_frame,
        "Display Options",
        "",
        20,
        "bold",
        0,
        0,
        20,
        (60, 10),
        "s",
    )

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
    create_tooltip(
        self.everything_checkbox,
        text="Checks all of the below checkboxes except for 'twistyt' and sets the display level to the maximum detail level.",
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
    create_tooltip(
        self.directory_checkbox,
        text="Display a directory of all Projects, Profiles, Tasks and Scenes with hotlinks at the begging of the output.",
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
    create_tooltip(
        self.outline_checkbox,
        text="Display a diagram of the configuration with all Task connections your the default text editor.\nThis option only relates to the 'Run and Exit' and 'ReRun' buttons.",
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
    create_tooltip(
        self.pretty_checkbox,
        text="Align all Task action arguments and parameters for nicer output.",
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
    create_tooltip(
        self.display_names_label,
        text="Add highlighting to Project, Profile and Task names in the output.",
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
    create_tooltip(
        self.bold_checkbox,
        text="Bold and Italicize are mutually exclusive in the Map view.",
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
    create_tooltip(
        self.italicize_checkbox,
        text="Italicize and Bold are mutually exclusive in the Map view.",
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

    # Task 'actions' limit
    self.task_action_label = add_label(
        self,
        self.sidebar_frame,
        f"Task 'actions' limit: {self.task_action_warning_limit}",
        "",
        0,
        "normal",
        14,
        0,
        20,
        (10, 0),
        "n",
    )
    self.task_action_limit = ctk.CTkSlider(
        self.sidebar_frame,
        from_=10,
        to=100,
        number_of_steps=100,
        orientation="horizontal",
        command=self.event_handlers.tasklimit_event,
        hover=True,
        button_hover_color="blue",
        progress_color="green",
    )
    self.task_action_limit.grid(row=14, column=0, padx=20, pady=40, sticky="n")
    self.task_action_limit.set(100)
    create_tooltip(
        self.task_action_limit,
        text="Select how many actions in a Task before issuing a warning.\nThe warning appears near th4e bottom of the configuration output,\nand is intended to help identify Tasks that are too comple\nand which should potentially be broken up into multiple Tasks.\nA setting of '100' means there is no limit.",
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
        10,
        (80, 0),
        "n",
    )

    # Indentation Amount
    self.indent_option = add_option_menu(
        self,
        self.sidebar_frame,
        self.event_handlers.indent_selected_event,
        ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
        16,
        0,
        0,
        (0, 10),
        "n",
    )
    create_tooltip(
        self.indent_option,
        text="Set the indentation amount for If/Then/Else blocks.\n\nThe default is '4'.",
    )

    # Screen Appearance: Light / Dark / System
    self.appearance_mode_label = add_label(
        self,
        self.sidebar_frame,
        "Appearance Mode:",
        "",
        0,
        "normal",
        17,
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
        18,
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
        19,
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
        20,
        0,
        (20, 0),
        0,
        "sw",
    )
    self.mapview_button.configure(width=50)
    create_tooltip(
        self.mapview_button,
        text="Show a detailed view of your configuration, with connections between tasks.\n\nThis is identical to the 'ReRun' button, but the output is displayed inside another window rather than in a browser.",
    )

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
        20,
        0,
        105,
        0,
        "sw",
    )
    self.diagramview_button.configure(width=120)
    create_tooltip(
        self.diagramview_button,
        text="Show a diagrammatic view of your configuration, with connections between tasks.\n\nThis is identical to the 'ReRun' button combined with the 'Display Configuration Outline' checkbox selected,\nbut the output is displayed inside another window rather than in a text editor.",
    )

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
        20,
        0,
        (0, 40),
        0,
        "se",
    )
    self.treeview_button.configure(width=50)
    create_tooltip(
        self.treeview_button,
        text="Show a simple hierarchical tree view of your configuration.",
    )
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
        20,
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
        21,
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
        21,
        0,
        (20, 0),
        20,
        "n",
    )
    create_tooltip(
        self.viewlimit_optionmenu,
        text="Select the maximum number of items to display in the view to be allowed.\n\nAnything over this amount will stop the generation of the view as a means to throttle the program.\n\nNote: This is only for the 'Map' and 'Diagram' views, not the tree view.",
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
        21,
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
        (80, 10),
        "",
    )
    create_tooltip(
        self.reset_button,
        text="Reset all of the options to their default values, including colors, font used, and other settings.\n\nThe currently loaded XML will be cleared out.",
    )

    # Start second grid / column definitions

    # Font to use
    self.font_label = add_label(
        self,
        self,
        "Font To Use In Output:",
        "",
        0,
        "normal",
        6,
        1,
        20,
        10,
        "sw",
    )

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
    create_tooltip(
        self.font_optionmenu,
        text="This is a list of all of the monospaced fonts available on your system.\n\nThe font selected will be used in all output.\n\n'Courier' or 'Courier New' is highly recommended for Diagrams to ensure proper connector alignment.",
    )

    # Save settings button
    _ = add_button(
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
    _ = add_button(
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
    create_tooltip(
        self.report_issue_button,
        text="Report any issues and/or suggestions to the developer.\n\nThis will open a browser window to the GitHub Issues page, and you will need a GitHub account to submit an issue.",
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
        10,
        "s",
    )
    # 'Get Backup Settings' button definition
    self.get_backup_button = self.display_backup_button(
        "Get XML from Android Device",
        "#246FB6",
        "#6563ff",
        self.event_handlers.get_xml_from_android_event,
    )
    create_tooltip(
        self.get_backup_button,
        text="Fetch XML from an Android device.\n\nClick on the 'Get Android Help' button for more info.",
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
        5,
        2,
        (20, 20),
        (10, 0),
        "ne",
    )
    create_tooltip(
        self.getxml_button,
        text="Fetch XML from a local drive on this computer.\n\nThe XML fetched will become the current source for MapTasker commands.",
    )

    # 'Display Help' button definition
    _ = add_button(
        self,
        self,
        "#246FB6",
        ("#0BF075", "#ffd941"),
        "",
        lambda: self.event_handlers.query_event("help"),
        2,
        "Display Help",
        1,
        6,
        2,
        (0, 20),
        (20, 0),
        "ne",
    )

    # 'Backup Help' button definition
    _ = add_button(
        self,
        self,
        "#246FB6",
        ("#0BF075", "#ffd941"),
        "",
        lambda: self.event_handlers.query_event("android"),
        2,
        "Get Android Help",
        1,
        6,
        2,
        (0, 20),
        (58, 0),
        "ne",
    )

    # Add "Browser" label
    self.text_message_label = add_label(
        self,
        self,
        "Browser Options",
        "",
        14,
        "normal",
        7,
        2,
        (0, 35),
        (50, 0),
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
        (80, 0),
        "ne",
    )
    create_tooltip(
        self.run_button,
        text="Generate a map of the current XML, save the results as an html file and display the map in the default browser.\n\nThe program terminates when done.",
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
        (118, 10),
        "ne",
    )
    create_tooltip(
        self.rerun_button,
        text="Same as the 'Run' button, but the program does not terminate when done.",
    )

    # 'Exit' button definition
    _ = add_button(
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

    # Add our tabs
    for item in TAB_NAMES:
        self.tabview.add(item)

    self.tabview.tab("Specific Name").grid_columnconfigure(
        0,
        weight=1,
    )  # configure grid of individual tabs
    self.tabview.tab("Colors").grid_columnconfigure(0, weight=1)
    self.tabview.tab("Analyze").grid_columnconfigure(0, weight=1)
    self.tabview.tab("Debug").grid_columnconfigure(0, weight=1)

    # Prompt for the name
    _ = add_label(
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

    # Display 'List Unnamed Items' checkbox
    self.list_unnamed_items_checkbox = add_checkbox(
        self,
        self.tabview.tab("Specific Name"),
        self.event_handlers.list_unnamed_items_event,
        "List Unnamed Items",
        14,
        0,
        (10, 20),
        (10, 0),
        "s",
        "",
    )
    create_tooltip(
        self.list_unnamed_items_checkbox,
        text="""
Check this if you want to see unnamed Profiles and Tasks in the\npulldown lists (above) and in the optional directory.\n\n
Leaving this unchecked will leave unnamed Tasks and Profiles\nout of the pulldown lists and out of the directory,
but the unnamed Profile and Task details will still appear in the output.
""",
    )

    # Setup to get various display colors
    _ = add_label(
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
    _ = add_option_menu(
        self,
        self.tabview.tab("Colors"),
        self.event_handlers.colors_event,
        [
            "Projects",
            "Profiles",
            "Disabled Profiles",
            "Launcher Tasks",
            "Profile Conditions",
            "Tasks",
            "Unnamed Tasks",
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
    _ = add_button(
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
    _ = add_button(
        self,
        self.tabview.tab("Analyze"),
        "",  # fg_color: str,
        "",  # text_color: str,
        "",  # border_color: str,
        self.event_handlers.ai_apikey_event,  # command
        2,  # border_width: int,
        "Show/Edit API Key(s)",  # text: str,
        1,  # columnspan: int,
        3,  # row: int,
        0,  # column: int,
        center,  # padx: tuple,
        (10, 10),  # pady: tuple,
        "",
    )
    # Change Prompt
    _ = add_button(
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

    # Prefix, sort, and combine the model lists
    display_models = sorted(
        model
        for name, models in MODEL_GROUPS.items()
        for model in prefix_and_sort(models, name)
    )

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
    # Add maptasker icon
    _ = add_logo(self, "maptasker")
    # Buy Me A Coffee button
    self._dict_icon = add_logo(self, "coffee")


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


def store_windows(self) -> None:  # noqa: ANN001
    """
    Stores the positions of all of our windows.

    This function saves the positions of the various windows using the `save_window_position()` function.

    Returns:
        None
    """
    windows = {
        "ai_analysis_window": "ai_analysis_window_position",
        "treeview_window": "tree_window_position",
        "diagramview_window": "diagram_window_position",
        "mapview_window": "map_window_position",
        "progressbar_window": "progressbar_window_position",
        "apikey_window": "ai_apikey_window_position",
        "self": "window_position",
    }

    with contextlib.suppress(AttributeError):
        for window_attr, position_attr in windows.items():
            window_obj = getattr(self, window_attr, None)
            if window_obj and (window_pos := save_window_position(window_obj)):
                setattr(self, position_attr, window_pos)


class ToolTip(object):  # noqa: UP004
    """ToolTip class to display info as a popup box of text on cursor hover."""

    def __init__(self, widget: object) -> None:
        """
        Initialize the ToolTip object.

        Parameters:
            widget (Widget): The widget on which the tooltip will appear.

        Returns:
            None
        """
        self.widget = widget
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0

    def showtip(self, text: str) -> None:
        """
        Show ToolTip text in a popup window.

        Parameters:
            text (str): The text to be displayed in the tooltip popup.

        Returns:
            None
        """
        self.text = text
        if self.tipwindow or not self.text:
            return
        x, y, _, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 57
        y = y + cy + self.widget.winfo_rooty() + 27
        self.tipwindow = tw = Toplevel(self.widget)
        tw.wm_overrideredirect(1)
        tw.wm_geometry(f"+{x}+{y}")

        # Find MyGui from the top level window.  It could sbe hanging off a number of 'masters'
        mygui = tw
        while mygui:
            if mygui.__class__.__name__ == "MyGui":
                break
            mygui = mygui.master

        # Get the font the user has selected.
        try:
            font = mygui.font
        except AttributeError:
            font = "Courier"

        # Get our color table so we can get the background color definition.
        color_lookup = mygui.color_lookup
        try:
            background_color = make_hex_color(color_lookup["background_color"])
        except KeyError:
            background_color = "Black"

        foreground_color = "white" if is_color_dark(background_color) else "black"
        label = Label(
            tw,
            text=self.text,
            justify="left",
            # background="#ffffe0",
            background=background_color,
            foreground=foreground_color,
            relief="solid",
            borderwidth=1,
            font=(font, "12", "normal"),
        )

        label.pack(ipadx=1)

    def hidetip(self) -> None:
        """
        Hides the tooltip.

        This function sets the `tipwindow` attribute to None and then calls the `destroy()` method on the tooltip window if it exists.

        Returns:
            None
        """
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()


def create_tooltip(widget: object, text: str) -> None:
    """
    Create a tooltip for a given widget.

    This function creates a ToolTip object, then binds the widget to the enter and leave events.
    When the mouse enters the widget, it calls the showtip method of the tooltip object with the given text.
    When the mouse leaves the widget, it calls the hidetip method of the tooltip object.

    Parameters:
        widget (Widget): The widget on which the tooltip will appear.
        text (str): The text to be displayed in the tooltip popup.

    Returns:
        None
    """
    tooltip = ToolTip(widget)

    def enter(event: object) -> None:  # noqa: ARG001
        """
        Event handler for when the mouse enters the widget.

        This function calls the showtip() method of the tooltip object with the text given when the tooltip was created.

        Parameters:
            event (object): The event object.

        Returns:
            None
        """
        tooltip.showtip(text)

    def leave(event: object) -> None:  # noqa: ARG001
        """
        Event handler for when the mouse leaves the widget.

        This function calls the hidetip() method of the tooltip object.

        Parameters:
            event (object): The event object.

        Returns:
            None
        """
        tooltip.hidetip()

    widget.bind("<Enter>", enter)
    widget.bind("<Leave>", leave)


class APIKeyDialog(ctk.CTkToplevel):
    """
    A class to represent the GetApiKey top-level window.  This is used to manage the AI API Keys.

    This class inherits from CTk and is used to create a window for managing API keys.
    """

    def __init__(self, *args: dict, **kwargs: dict) -> None:
        """
        Initialize the CTkToplevel class.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        super().__init__(*args, **kwargs)

        # Get our GUI
        my_gui = self.master

        # Basic appearance for text, foreground and background.
        width = "800"
        height = "400"
        self.title("API Key Options")
        self.apiview_bg_color = self._apply_appearance_mode(
            ctk.ThemeManager.theme["CTkFrame"]["fg_color"],
        )
        self.apiview_text_color = self._apply_appearance_mode(
            ctk.ThemeManager.theme["CTkLabel"]["text_color"],
        )
        self.selected_color = self._apply_appearance_mode(
            ctk.ThemeManager.theme["CTkButton"]["fg_color"],
        )

        # Position the widget
        window_position = my_gui.ai_apikey_window_position
        try:
            self.geometry(window_position)
            # window_ shouldn't be in here.  If it is, pickle file is corrupt.
            window_position = window_position.replace("window_", "")
            work_window_geometry = window_position.split("x")
            self.master.ai_apikey_window_width = work_window_geometry[0]
            self.master.ai_apikey_window_height = work_window_geometry[1].split("+")[0]
        except (AttributeError, TypeError):
            self.master.ai_apikey_window_position = f"{width}x{height}+600+0"
            self.master.ai_apikey_window_width = width
            self.master.ai_apikey_window_height = height
            self.geometry(f"{width}x{height}")
        # Save the window position on closure
        self.protocol("WM_DELETE_WINDOW", lambda: on_closing(self))

        # Define the grid.
        self.grid_columnconfigure(1, weight=1)

        # Save the window
        my_gui.ai_apikey_window = self

        # Get the server-based keys
        self.openai_key = self.create_key_entry(0, "OpenAI API Key:", "openai_key")
        self.claude_key = self.create_key_entry(1, "Claude API Key:", "claude_key")
        self.deepseek_key = self.create_key_entry(
            2,
            "DeepSeek API Key:",
            "deepseek_key",
        )
        self.gemini_key = self.create_key_entry(3, "Gemini API Key:", "gemini_key")

        #  OK button
        apikey_ok_button = add_button(
            self,
            self,
            "#246FB6",
            ("#0BF075", "#ffd941"),
            "#1bc9ff",
            # Note: lambda needs the '_:' to pass the event object.
            lambda: my_gui.event_handlers.ai_apikey_get_event(cancel=False, clear=""),
            1,
            "OK",
            1,
            4,
            0,
            (150, 0),
            20,
            "nw",
        )
        apikey_ok_button.configure(width=30)

        #  Query ? button
        apikey_query_button = add_button(
            self,
            self,
            "#246FB6",
            ("#0BF075", "#ffd941"),
            "#1bc9ff",
            lambda: my_gui.event_handlers.query_event("apikey"),
            1,
            "?",
            1,
            4,
            0,
            (200, 0),
            20,
            "nw",
        )
        apikey_query_button.configure(width=20)
        # Cancel button
        _ = add_button(
            self,
            self,
            "",
            ("#0BF075", "#FFFFFF"),
            "",
            # Note: lambda needs the '_:' to pass the event object.
            lambda: my_gui.event_handlers.ai_apikey_get_event(cancel=True, clear=""),
            1,
            "Cancel",
            1,  # Column span
            4,  # row
            0,  # col
            (250, 90),
            0,
            "ew",
        )
        self.focus()

    def create_key_entry(
        self,
        row: int,
        label_text: str,
        placeholder_key: str,
    ) -> ctk.CTkEntry:
        """Helper function to create a label, entry and 'Clear' button for an API key."""
        _ = add_label(
            self,
            self,
            label_text,
            "Orange",
            14,
            "normal",
            row,
            0,
            20,
            20,
            "nw",
        )
        # Generate the dynamic entry field name / widget
        entry_name = f"entry_{placeholder_key}"
        setattr(
            self,
            entry_name,
            ctk.CTkEntry(self, placeholder_text=PrimeItems.ai[placeholder_key]),
        )
        # Access the dynamically created entry widget
        entry_widget = getattr(self, entry_name)
        entry_widget.grid(row=row, column=0, padx=(150, 10), pady=20, sticky="ne")
        entry_widget.configure(width=565)
        entry_widget.insert(0, PrimeItems.ai[placeholder_key])

        # Get our GUI
        my_gui = self.master

        # Add 'Clear" button
        clear = add_button(
            self,
            self,
            "",
            ("#0BF075", "#FFFFFF"),
            "",
            # Note: lambda needs the '_:' to pass the event object.
            lambda: my_gui.event_handlers.ai_apikey_get_event(
                cancel=False,
                clear=placeholder_key,
            ),
            1,
            "Clear",
            1,  # Column span
            row,  # row
            1,  # col
            (10, 10),
            20,
            "ne",
        )
        clear.configure(width=20)

        return entry_widget
