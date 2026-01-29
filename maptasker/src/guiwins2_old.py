#! /usr/bin/env python3
"""GUI Window Classes and Definitions"""

#                                                                                      #
# guiwins: provide GUI window functions                                                #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
import contextlib
import tkinter as tk
import webbrowser

import customtkinter as ctk

from maptasker.src.error import rutroh_error
from maptasker.src.guiutils import (
    add_button,
    add_label,
    destroy_hover_tooltip,
    display_selected_object_labels,
    get_foreground_background_colors,
    on_closing,
    output_label,
    reset_primeitems_single_names,
    search_substring_in_list,
    set_tasker_object_names,
    update_tasker_object_menus,
)
from maptasker.src.maputils import make_hex_color
from maptasker.src.primitem import PrimeItems


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
        self.anthropic_key = self.create_key_entry(1, "Claude API Key:", "anthropic_key")
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
        apikey_ok_button.configure(width=140)

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
            (300, 0),
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
            (350, 90),
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

        # Find MyGui from the top level window.  It could sbe hanging off a number of 'masters'
        mygui = event.widget
        while mygui:
            if mygui.__class__.__name__ == "MyGui":
                break
            mygui = mygui.master

        background_color, foreground_color, _ = get_foreground_background_colors(
            mygui,
        )

        # Find the tag associated with the item entered so we can add hover text.
        for tag in self.text.tag_names(ctk.CURRENT):
            # Delete any previous hover tooltip.
            with contextlib.suppress(AttributeError):
                destroy_hover_tooltip(self.hover_tooltip)
            if tag.startswith("hyper-") and self.links:
                link = self.links[tag]
                if link[0] in tasker_object:
                    # Add a hover text to the link entered of the name of the link.
                    label = tk.Label(
                        event.widget.master,
                        text=f"{tasker_object[link[0]]}: {link[1]}",
                        bg=background_color,
                        fg=foreground_color,
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
        _remap_single_item = self.remap_single_item
        for tag in self.text.tag_names(ctk.CURRENT):
            if tag.startswith("hyper-"):
                if self.links:
                    link = self.links[tag]
                    if isinstance(link, list):
                        # Go up one level: Remap single Project/Profile/Task
                        action, name = link
                        guiself = event.widget.master.master.root.master
                        _remap_single_item(action, name, guiself)
                    else:
                        try:
                            webbrowser.open(link)
                        except Exception as e:  # noqa: BLE001
                            rutroh_error(f"Error opening link '{link}': {e}")
                    return

                # Misc view hyperlink...pick up the links from deep down
                link = self.text.master.hyperlink.links[tag]
                mygui = event.widget.master.master.root.master
                try:
                    textbox = mygui.textview.textview_textbox
                except AttributeError:
                    # The target textbox is gone.  Maybe it is an analysis window
                    try:
                        textbox = mygui.analysisview.textview_textbox
                    except AttributeError:
                        # The target textbox is gone altogether.
                        textbox.destroy()
                        mygui.miscview_window.destroy()
                        return

                line_number = link[1]
                start_idx = f"{line_number}.0"

                # Remove previous highlights
                tagid = "misc_high"
                try:
                    textbox.tag_remove(tagid, "1.0", "end")
                except tk.TclError:
                    # The target textbox is gone.
                    textbox.destroy()
                    mygui.miscview_window.destroy()
                    return
                # Highlight the hyperlink target
                textbox.tag_add("misc_high", start_idx, f"{line_number}.end")
                # Now color it in.
                textbox.tag_config("misc_high", background=make_hex_color(mygui.color_lookup["highlight_color"]))
                textbox.see(start_idx)

                # Now bring the 'viewe' window to the front.  A combination of one of these has got to work!
                with contextlib.suppress(AttributeError):
                    mygui.miscview_window.lower()
                    mygui.miscview_window.iconify()
                    mygui.textview.focus()
                    mygui.textview.focus_set()
                    mygui.textview.lift()

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
            single_name_parm = action[0 : len(action) - 1]
            # Update self.single_xxx_name
            setattr(guiself, f"single_{single_name_parm}_name", name)
            PrimeItems.program_arguments[f"single_{single_name_parm}_name"] = name

            # Reset single item labels
            update_tasker_object_menus(
                guiself,
                get_data=True,
                reset_single_names=False,
            )
            # Reset the single item pulldown (this has to go after reset of labels!).
            set_tasker_object_names(guiself)

            # Redo the labels
            display_selected_object_labels(guiself)

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
        length_to_use = len(search_string) - 6 if "(Scene)" in orig_name else len(search_string)
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
