"""GUI Window Classes and Definitions"""

#! /usr/bin/env python3

#                                                                                      #
# userwins: provide GUI window functions                                               #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #

import contextlib
import os
from tkinter import TclError, ttk

import customtkinter as ctk
from PIL import Image, ImageTk

from maptasker.src.guiutils import (
    add_button,
    add_checkbox,
    add_label,
    add_logo,
    add_option_menu,
    display_analyze_button,
    get_monospace_fonts,
)
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import LLAMA_MODELS, OPENAI_MODELS

# Set up for access to icons
CURRENT_PATH = os.path.dirname(os.path.realpath(__file__))
ICON_DIR = os.path.join(CURRENT_PATH, f"..{PrimeItems.slash}assets", "icons")
ICON_PATH = {
    "close": (os.path.join(ICON_DIR, "close_black.png"), os.path.join(ICON_DIR, "close_white.png")),
    # "images": list(os.path.join(ICON_DIR, f"image{i}.jpg") for i in range(1, 4)),
    "eye1": (os.path.join(ICON_DIR, "eye1_black.png"), os.path.join(ICON_DIR, "eye1_white.png")),
    "eye2": (os.path.join(ICON_DIR, "eye2_black.png"), os.path.join(ICON_DIR, "eye2_white.png")),
    "info": os.path.join(ICON_DIR, "info.png"),
    "warning": os.path.join(ICON_DIR, "warning.png"),
    "error": os.path.join(ICON_DIR, "error.png"),
    "left": os.path.join(ICON_DIR, "left.png"),
    "right": os.path.join(ICON_DIR, "right.png"),
    "warning2": os.path.join(ICON_DIR, "warning2.png"),
    "loader": os.path.join(ICON_DIR, "loader.gif"),
    "icon": os.path.join(ICON_DIR, "icon.png"),
    "arrow": os.path.join(ICON_DIR, "arrow.png"),
    "image": os.path.join(ICON_DIR, "image.png"),
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


# Define the Treeview window
class TreeviewWindow(ctk.CTkToplevel):
    """Define our top level window for the tree view."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        """Creates a label widget for a tree view.
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
            self.geometry(self.master.tree_window_position)
        except (AttributeError, TypeError):
            self.geometry("570x800")

        self.title("MapTasker Configuration Treeview")

        # Save the window position on closure
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    # Tree view window is getting closed
    def on_closing(self) -> None:
        """Save the window position and close the window."""
        self.master.tree_window_position = self.wm_geometry()
        self.destroy()


# Display a Analysis structure
class CTkAnalysisview(ctk.CTkFrame):
    """Class to handle the Treeview

    Args:
        ctk (ctk): Our GUI framework
    """

    def __init__(self, master: any, message: str) -> None:
        """Function:
        def __init__(self, master: any, items: list):
            Initializes a Analysisview widget with a given master and list of items.
            Parameters:
                master (any): The parent widget for the Analysisview.
                items (list): A list of items to be inserted into the Analysisview.
            Returns:
                None.
            Processing Logic:
                - Sets up the Analysisview widget with appropriate styles and bindings.
                - Inserts the given items into the Treeview.
        """
        self.root = master
        super().__init__(self.root)

        self.grid_columnconfigure(0, weight=1)

        # Basic appearance for text, foreground and background.
        self.analysis_bg_color = self.root._apply_appearance_mode(  # noqa: SLF001
            ctk.ThemeManager.theme["CTkFrame"]["fg_color"],
        )
        self.analysis_text_color = self.root._apply_appearance_mode(  # noqa: SLF001
            ctk.ThemeManager.theme["CTkLabel"]["text_color"],
        )
        self.selected_color = self.root._apply_appearance_mode(  # noqa: SLF001
            ctk.ThemeManager.theme["CTkButton"]["fg_color"],
        )

        # Set up the style/theme
        self.analysis_style = ttk.Style(self)
        self.analysis_style.theme_use("default")

        # Recreate text box
        self.analysis_textbox = ctk.CTkTextbox(self, height=700, width=550)
        self.analysis_textbox.grid(row=1, column=1, padx=20, pady=40, sticky="nsew")

        # Insert the text with our new message into the text box.
        # Add the test and color to the text box.
        # fmt: off
        self.analysis_textbox.insert("0.0", f"{message}\n")
        self.analysis_textbox.configure(state="disabled", wrap="word")  # configure textbox to be read-only
        self.analysis_textbox.focus_set()


# Define the Ai Analysis window
class AnalysisWindow(ctk.CTkToplevel):
    """Define our top level window for the analysis view."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        """Creates a label widget for a tree view.
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
            self.geometry(self.master.ai_analysis_window_position)
        except (AttributeError, TypeError):
            self.geometry("600x800+600+0")

        self.title("MapTasker Analysis Response")

        # Save the window position on closure
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    # Analysis window is getting closed
    def on_closing(self) -> None:
        """Save the window position and close the window."""
        self.master.ai_analysis_window_position = self.wm_geometry()
        self.destroy()


# Define the Ai Popup window
class PopupWindow(ctk.CTk):
    """Define our top level window for the Popup view."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        """Creates a label widget for a tree view.
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

        # Position the widget over our main GUI
        self.geometry(PrimeItems.program_arguments["window_position"])

        self.title("MapTasker Analysis")

        self.grid_columnconfigure(0, weight=1)

        # Set popup window wait time to .5 seconds, after which popup_button_event will be called.
        self.after(500, self.popup_button_event)

        # Label widget
        our_label = "Analysis is running in the background.  Please stand by..."
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
        get_rid_of_window(self)


# Save the positition of a window
def save_window_position(window: CTkAnalysisview) -> None:
    """
    Saves the window position by getting the geometry of the window.

    Args:
        window: The CTkAnalysisview window to save the position of.

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
    self.android_ipaddr = ""
    self.android_port = ""
    self.android_file = ""
    self.appearance_mode = None
    self.bold = None
    self.color_labels = None
    self.color_lookup = None
    self.color_text_row = None
    self.debug = None
    self.display_detail_level = None
    self.preferences = None
    self.conditions = None
    self.everything = None
    self.taskernet = None
    self.exit = None
    self.fetched_backup_from_android = False
    self.file = None
    self.font = None
    self.go_program = None
    self.gui = True
    self.highlight = None
    self.indent = None
    self.italicize = None
    self.named_item = None
    self.rerun = None
    self.reset = None
    self.restore = False
    self.runtime = False
    self.save = False
    self.single_profile_name = None
    self.single_project_name = None
    self.single_task_name = None
    self.twisty = None
    self.underline = None
    self.outline = False
    self.pretty = False
    self.treeview_window = None
    self.ai_analysis_window = None
    PrimeItems.program_arguments["gui"] = True
    self.list_files = False
    self.ai_apikey = None
    self.ai_model = None
    self.ai_analysis = None
    self.ai_missing_module = None
    self.ai_prompt = None
    self.window_position = None
    self.ai_popup_window_position = ""
    self.ai_analysis_window_position = ""
    self.tree_window_position = ""
    self.color_window_position = ""
    self.all_messages = {}
    self.first_time = True

    self.title("MapTasker Runtime Options")

    # configure grid layout (4x4).  A non-zero weight causes a row or column to grow if there's extra space needed.
    # The default is a weight of zero, which means the column will not grow if there's extra space.
    self.grid_columnconfigure(1, weight=1)
    self.grid_columnconfigure((2, 3), weight=0)  # Columns 2 and 3 are not stretchable.
    self.grid_rowconfigure((0, 3), weight=4)  # Divvy up the extra space needed equally amonst the 4 rows: 0-thru-3

    # load and create background image

    # create sidebar frame with widgets on the left side of the window.
    self.sidebar_frame = ctk.CTkFrame(self, width=140, corner_radius=0)
    self.sidebar_frame.configure(bg_color="black")
    self.sidebar_frame.grid(row=0, column=0, rowspan=17, sticky="nsew")
    # Define sidebar background frame with 17 rows
    self.sidebar_frame.grid_rowconfigure(20, weight=1)  # Make anything in rows 20-xx stretchable.


# Define all of the menu elements
def initialize_screen(self) -> None:  # noqa: ANN001
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
        self.detail_selected_event,
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
        self.everything_event,
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
        self.condition_event,
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
        self.taskernet_event,
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
        self.preferences_event,
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
        self.twisty_event,
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
        self.directory_event,
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
        self.outline_event,
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
        self.pretty_event,
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
    self.bold_checkbox = add_checkbox(self, self.sidebar_frame, self.names_bold_event, "Bold", 12, 0, 20, 0, "ne", "")

    # Italicize
    self.italicize_checkbox = add_checkbox(
        self,
        self.sidebar_frame,
        self.names_italicize_event,
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
        self.names_highlight_event,
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
        self.names_underline_event,
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
        self.indent_selected_event,
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
        self.change_appearance_mode_event,
        ["Light", "Dark", "System"],
        17,
        0,
        0,
        (0, 10),
        "n",
    )

    # 'Tree View' button definition
    self.treeview_button = add_button(
        self,
        self.sidebar_frame,
        "#246FB6",
        "",
        "",
        self.treeview_event,
        2,
        "Tree View",
        0,
        18,
        0,
        0,
        10,
        "",
    )
    #  Query ? button
    self.treeview_query_button = add_button(
        self,
        self.sidebar_frame,
        "#246FB6",
        ("#0BF075", "#ffd941"),
        "#1bc9ff",
        self.treeview_query_event,
        1,
        "?",
        1,
        18,
        0,
        (200, 0),
        (0, 0),
        "",
    )
    self.treeview_query_button.configure(width=20)

    # 'Reset Settings' button definition
    self.reset_button = add_button(
        self,
        self.sidebar_frame,
        "#246FB6",
        "",
        "",
        self.reset_settings_event,
        2,
        "Reset Options",
        1,
        19,
        0,
        20,
        20,
        "s",
    )

    # Start second grid / column definitions

    # Font to use
    self.font_label = add_label(self, self, "Font To Use In Output:", "", 0, "normal", 6, 1, 20, 10, "sw")

    # Get fonts from TkInter
    font_items, res = get_monospace_fonts()
    # Delete the tkroot obtained by get_monospace_fonts
    if PrimeItems.tkroot is not None:
        del PrimeItems.tkroot
        PrimeItems.tkroot = None
    self.font_optionmenu = add_option_menu(
        self,
        self,
        self.font_event,
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
        self.save_settings_event,
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
        self.restore_settings_event,
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
        self.report_issue_event,
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
        self.clear_messages_event,
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
        self.get_backup_event,
    )
    # 'Get local XML' button
    self.getxml_button = add_button(
        self,
        self,
        "",
        "",
        "",
        self.getxml_event,
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
        self.help_event,
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
        self.backup_help_event,
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
        self.run_program,
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
        self.rerun_the_program,
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
        self.exit_program,
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
    # create tabview for Name, Color, and Debug
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
        self.colors_event,
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
        self.color_reset_event,
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
        self.ai_apikey_event,  # command
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
        self.ai_prompt_event,  # command
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
        self.ai_model_selected_event,
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
        self.ai_help_event,  # command
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
        self.debug_checkbox_event,
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
        self.runtime_checkbox_event,
        "Display Runtime Settings",
        3,
        3,
        20,
        10,
        "w",
        "#6563ff",
    )


# Delete the window
def get_rid_of_window(self) -> None:  # noqa: ANN001
    """
    Hides the window and terminates the application.

    This function withdraws the window, which removes it from the screen, and then calls the `quit()` method twice to terminate the application.

    Parameters:
        self (object): The instance of the class.

    Returns:
        None
    """
    self.withdraw()  # Remove the Window
    self.quit()


# Store our various window positions
def store_windows(self) -> None:  # noqa: ANN001
    """
    Stores the positions of the AI analysis and treeview windows.

    This function saves the positions of the AI analysis and treeview windows using the `save_window_position` function. If the window positions are successfully saved, they are assigned to the corresponding instance variables `ai_analysis_window_position` and `tree_window_position`.

    Parameters:
        self (object): The instance of the class.

    Returns:
        None
    """
    if window_pos := save_window_position(self.ai_analysis_window):
        self.ai_analysis_window_position = window_pos
    if window_pos := save_window_position(self.treeview_window):
        self.tree_window_position = window_pos
