"""GUI Window Classes and Definitions (NiceGUI Version)"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

from nicegui import app, ui

from maptasker.src.guiutil2 import sort_languages_with_priority
from maptasker.src.guiutils import display_model_pulldown, get_monospace_fonts
from maptasker.src.maputil2 import translate_string
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import DIAGRAM_FILE, DIAGRAM_PROFILES_PER_LINE, logger

if TYPE_CHECKING:
    from maptasker.src.userintr import MyGui


# ==========================================
# 1. TOOLTIPS
# ==========================================
def create_tooltip(widget: object, text: str) -> None:
    """
    Wrapper for NiceGUI tooltips to maintain compatibility with existing code calls.
    """
    widget.tooltip(text)


# ==========================================
# 2. DIALOGS & POPUPS
# ==========================================
def create_popup_window(title: str, message: str = "") -> ui.dialog:
    """Creates a modal dialog. Replaces PopupWindow and CTkToplevel."""
    with ui.dialog() as dialog, ui.card().classes("min-w-[300px] items-center p-6"):
        ui.label(title).classes("text-xl font-bold text-blue-600")
        if message:
            ui.label(message).classes("mt-2 text-center")
        ui.button("Close", on_click=dialog.close).classes("mt-6 bg-red-500 text-white w-full")

    dialog.open()
    return dialog


# 1. Ensure your window creation function allows easy access/closing
def create_progressbar_window(title: str = "Processing Data...") -> tuple[ui.dialog, ui.linear_progress, ui.label]:
    """Creates a modal with a progress bar and status text."""
    with ui.dialog() as dialog, ui.card().classes("min-w-[400px] p-6 items-center"):
        status_label = ui.label(title).classes("text-lg mb-4 font-bold")
        # show_value=False keeps it clean, or True to show percentage
        progress = ui.linear_progress(value=0.0, show_value=True).classes("w-full")

    dialog.open()
    return dialog, progress, status_label


# ==========================================
# 3. VIEWS (Tree and Text)
# ==========================================
# Pre-compile the regex pattern at the module level for maximum execution performance.
# This scans the HTML string and hits all target replacements in a single pass O(N).
HTML_OPTIMIZE_PATTERN = re.compile(
    r"(\n\n\n|\n\n|<br>\n<br><br>|\n<br><br>|<br>\n|<br><br>|<br></span>|\n<br>|<h2>MapTasker</h2>|<h2><span class=\"normtab\"></span>Directory</h2>)",
)

# Map the targeted string matches directly to their optimized counterparts.
HTML_REPLACEMENT_MAP = {
    "\n\n\n": "",
    "\n\n": "",
    "<br>\n<br><br>": "",
    "\n<br><br>": "<br>",
    "<br>\n": "<br>",
    "<br><br>": "<br>",
    "<br></span>": "</span>",
    "\n<br>": "<br>",
    "<h2>MapTasker</h2>": '<a id="the_top"></a><h5>MapTasker</h5>',
    '<h2><span class="normtab"></span>Directory</h2>': '<h6><span class="normtab"></span>Directory</h6>',
}


class NiceGuiTreeView:
    """Replaces CTkTreeview. Renders a hierarchical tree representation."""

    def __init__(self: MyGui, master_gui: object, title: str, items: list) -> None:
        self.master_gui = master_gui
        self.title = title
        self.build_ui(items)

    def build_ui(self: MyGui, items: list) -> None:
        with ui.card().classes("w-full max-w-4xl mx-auto mt-4 p-6 shadow-lg"):
            with ui.row().classes("items-center justify-between w-full border-b pb-4 mb-4"):
                ui.label(f"{self.title} View").classes("text-2xl font-bold text-blue-600")
                ui.label("Click arrows to expand/collapse.").classes("text-sm text-gray-500 italic")

            tree_data = self._format_data(items)
            self.tree = ui.tree(tree_data, label_key="label", children_key="children", tick_strategy="none").classes(
                "w-full text-lg",
            )

    def _format_data(self: MyGui, items: list, parent_id: str = "node") -> list:
        """Converts MapTasker lists/dicts into NiceGUI's strict dict format."""
        formatted_nodes = []
        for i, item in enumerate(items):
            current_id = f"{parent_id}_{i}"
            if isinstance(item, dict):
                node = {"id": current_id, "label": item.get("name", "Unnamed").ljust(50)}
                if item.get("children"):
                    node["children"] = self._format_data(item["children"], current_id)
                formatted_nodes.append(node)
            else:
                formatted_nodes.append({"id": current_id, "label": str(item)})
        return formatted_nodes


class NiceGuiTextView:
    """Replaces CTkTextview. Handles rendering MapTasker data using HTML."""

    def __init__(self: MyGui, master_gui, title: str, the_data: list | dict) -> None:
        self.master_gui = master_gui
        self.title = title
        self.is_map = isinstance(the_data, dict)
        self.build_ui()
        self.process_data(the_data)

    def build_ui(self: MyGui) -> None:
        """Builds the UI layout for the various text views, including toolbar and scrollable display area."""

        # Clear the previously displayed dynamic view and target the dedicated full-width slot
        if hasattr(self.master_gui, "content_container") and self.master_gui.content_container:
            self.master_gui.content_container.clear()
            container_context = self.master_gui.content_container
        else:
            container_context = ui.column()  # Fallback context if called standalone

        with container_context:
            # Toolbar
            with ui.row().classes("w-full items-center gap-2 p-2 mb-2 bg-gray-200 dark:bg-gray-800 rounded"):
                ui.label(f"{self.title}").classes("text-orange-500 font-bold mr-4")
                self.search_input = ui.input(placeholder="Search...").classes("w-48")
                ui.button("Search", on_click=self.search_event).classes("bg-blue-600")
                ui.button("Clear", on_click=lambda: self.search_input.set_value("")).classes("bg-blue-600")
                ui.separator().props("vertical")
                ui.button("Top", on_click=lambda: self.scroll("top")).classes("bg-blue-600")
                ui.button("Bottom", on_click=lambda: self.scroll("bottom")).classes("bg-blue-600")

            # --- DYNAMIC TEXT WRAPPING CONFIGURATION ---
            # Diagram view needs strict, un-wrapped columns. Map and others can use pre-wrap.
            if "Diagram" in self.title:
                wrap_class = "whitespace-pre"  # Disables wrapping, enables horizontal scrollbar
                break_class = ""  # Remove word breaks so characters align perfectly
            else:
                wrap_class = "whitespace-pre-wrap"  # Normal wrapping behavior for Map view
                break_class = "break-words"

            # Text Display Area
            self.scroll_area = (
                ui
                .scroll_area()
                .classes(
                    f"w-full max-w-full block h-[70vh] border-2 border-gray-600 p-4 font-mono text-sm {wrap_class} {break_class} bg-blue-100 dark:bg-blue-900",
                )
                .style("width: 100%; max-width: 100%;")
            )

            with self.scroll_area:
                # Direct structural constraints onto the raw HTML content block container
                html_style = "width: 100%; max-width: 100%;"
                if "Diagram" not in self.title:
                    html_style += " word-break: break-word;"

                self.html_display = ui.html().classes("w-full block max-w-full").style(html_style)

    def process_data(self: MyGui, the_data: dict | list) -> None:
        """Converts data to an HTML string, properly handling embedded CSS styles."""

        # Get the appropriate file to process.
        if self.title.startswith("Map"):
            file_to_read = os.path.join(os.getcwd(), "MapTasker.html")
        elif self.title.startswith("Diagram"):
            file_to_read = os.path.join(os.getcwd(), DIAGRAM_FILE)

        # Get the data to process
        # --- 1. TRY TO READ PRE-COMPRESSED HTML FILE FIRST ---
        try:
            with open(file_to_read, encoding="utf-8") as f:
                final_html = f.read()
                # Remove excessive blank lines and redundant <br> tags for cleaner display
                # OPTIMIZED: Replaced 10 chained .replace() calls with a single-pass regex lookup
                final_html = HTML_OPTIMIZE_PATTERN.sub(
                    lambda match: HTML_REPLACEMENT_MAP[match.group(0)],
                    final_html,
                )

            # The file is already pure, raw HTML.
            # We completely bypass all loops and assign it directly! Let NiceGui display it.
            self.html_display.content = final_html
            return  # noqa: TRY300

        # Fallback gracefully to your legacy processing if MapTasker.html doesn't exist yet and use the
        # passed data to build the HTML content.
        except FileNotFoundError:
            pass

        # Execute processing via fallback function
        self._process_fallback_data(the_data)

    def _process_fallback_data(self: MyGui, the_data: dict | list) -> None:
        """Fallback logic to assemble HTML content strings when the source file is missing."""
        html_builder = []
        in_style_block = False
        style_buffer = []

        def is_css_line(text: str) -> bool:
            """Helper function to determine if a stray line is actually a CSS rule."""
            clean = text.strip()
            if clean.startswith((".", "#", "}", "{")):
                return True
            return bool(":" in clean and (clean.endswith(";") or "/*" in clean or "*/" in clean))

        def escape_text_except_html(text: str) -> str:
            """Escapes < and > but preserves intended HTML tags like tables and links."""

            parts = re.split(r"(<[^>]+>)", text)

            allowed_tags = {
                "a",
                "table",
                "tr",
                "td",
                "th",
                "tbody",
                "thead",
                "div",
                "span",
                "br",
                "style",
                "b",
                "i",
                "u",
                "strong",
                "em",
                "hr",
                "!doctype",
                "html",
                "head",
                "meta",
                "title",
                "body",
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
                "p",
                "ul",
                "ol",
                "li",
            }

            for i in range(len(parts)):
                if i % 2 == 0:
                    parts[i] = parts[i].replace("<", "&lt;").replace(">", "&gt;")
                else:
                    tag_name_match = re.match(r"^</?([!a-zA-Z0-9]+)", parts[i])
                    if tag_name_match and tag_name_match.group(1).lower() in allowed_tags:
                        pass
                    else:
                        parts[i] = parts[i].replace("<", "&lt;").replace(">", "&gt;")
            return "".join(parts)

        # --- 2. FALLBACK DICTIONARY PROCESSING (Legacy Map View) ---
        if self.is_map:
            for num, (linenum, value) in enumerate(the_data.items()):
                text_list = value.get("text", [])
                color_list = value.get("color", [])
                full_line_text = "".join(str(t) for t in text_list)

                if "<style>" in full_line_text:
                    in_style_block = True

                if in_style_block:
                    clean_line = full_line_text.replace("<style>", "").replace("</style>", "").replace('"""', "")
                    style_buffer.append(clean_line)
                    if "</style>" in full_line_text:
                        in_style_block = False
                        html_builder.append(f"<style>{''.join(style_buffer)}</style>")
                        style_buffer = []
                elif is_css_line(full_line_text):
                    html_builder.append(f"<style>{full_line_text}</style>")
                else:
                    line_html = "<div>"
                    for t_idx, text_segment in enumerate(text_list):
                        if '"""' in str(text_segment):
                            text_segment = str(text_segment).replace('"""', "")
                        safe_text = escape_text_except_html(str(text_segment))
                        color = color_list[t_idx] if t_idx < len(color_list) else "inherit"
                        line_html += f"<span style='color: {color};'>{safe_text}</span>"
                    line_html = line_html.rstrip("\r\n")
                    html_builder.append(line_html + "</div>")

        # --- 3. FALLBACK LIST DATA PROCESSING (Other Views) ---
        else:
            for line in the_data:
                if line.strip() == "":
                    html_builder.append("<div>&nbsp;</div>")
                    continue
                if "<br><br>" in line:
                    line = line.replace("<br><br>", "")
                if '"""' in line:
                    if line in {"<div>  </tr>\n</div>", "<div>\n</div>"}:
                        continue
                    line = line.replace('"""', "")

                if "<style>" in line:
                    in_style_block = True

                if in_style_block:
                    clean_line = line.replace("<style>", "").replace("</style>", "")
                    style_buffer.append(clean_line)
                    if "</style>" in line:
                        in_style_block = False
                        html_builder.append(f"<style>{''.join(style_buffer)}</style>")
                        style_buffer = []
                elif is_css_line(line):
                    html_builder.append(f"<style>{line}</style>")
                else:
                    clean_text_line = line.rstrip("\r\n")
                    safe_line = escape_text_except_html(clean_text_line)
                    html_builder.append(f"<div>{safe_line}</div>")

        # --- 4. COMPRESS MULTIPLE BLANK LINES FOR FALLBACK DATA ---
        final_html = "".join(html_builder)
        empty_div_pattern = r"(<div>(?:\s|&nbsp;|<span[^>]*>(?:\s|&nbsp;)*</span>)*</div>\s*){2,}"
        final_html = re.sub(empty_div_pattern, "", final_html)
        final_html = re.sub(r"\n{3,}", "\n", final_html)
        final_html = re.sub(r"(<br\s*/?>\s*){2,}", "<br>", final_html)

        self.html_display.content = final_html

    def search_event(self: MyGui) -> None:
        """Search for the input text in the displayed content."""
        ui.notify(f"Searching for: {self.search_input.value}", type="info")

    def scroll(self: MyGui, direction: str) -> None:
        if direction == "top":
            ui.run_javascript(f"document.getElementById('c{self.scroll_area.id}').scrollTop = 0")
        else:
            ui.run_javascript(
                f"const el = document.getElementById('c{self.scroll_area.id}'); el.scrollTop = el.scrollHeight",
            )


# ==========================================
# 4. INITIALIZATION & LAYOUT
# ==========================================
def initialize_gui(self: MyGui) -> None:
    """Initialize state variables. 'self' is the MyGui instance."""
    _initialize_gui_settings(self)
    _initialize_ai_settings(self)
    _initialize_android_settings(self)
    _initialize_display_settings(self)
    _initialize_feature_flags(self)
    _initialize_window_positions(self)
    _initialize_data_structures(self)
    _initialize_runtime_options(self)


def _initialize_gui_settings(self: MyGui) -> None:
    """Initializes GUI-related appearance and display settings."""
    PrimeItems.program_arguments["gui"] = True
    self.gui = True
    self.guiview = False
    self.appearance_mode = None
    self.default_font = ""
    self.font = None
    self.bold = None
    self.italicize = None
    self.underline = None
    self.highlight = None
    self.color_labels = None
    self.color_lookup = None
    self.twisty = None
    self.indent = None
    self.display_detail_level = None
    self.everything = None
    self.view_limit = 10000
    self.profiles_per_line = DIAGRAM_PROFILES_PER_LINE
    self.clear_messages = False
    self.pretty = False
    self.task_action_warning_limit = 20
    self.language = "English"
    self.initialization = True
    self.textview = False


def _initialize_ai_settings(self: MyGui) -> None:
    """Initializes AI-related variables."""
    self.ai_analysis = None
    self.ai_analysis_window = None
    self.ai_apikey = None
    self.ai_apikey_window = None
    self.ai_model = ""
    self.ai_name = ""
    self.ai_model_extended_list = False
    self.displaying_extended_list = None
    self.ai_prompt = None


def _initialize_android_settings(self: MyGui) -> None:
    """Initializes Android device connection settings."""
    self.android_file = ""
    self.android_ipaddr = ""
    self.android_port = ""
    self.fetched_backup_from_android = False


def _initialize_display_settings(self: MyGui) -> None:
    """Initializes settings related to how data is displayed."""
    self.doing_diagram = False
    self.diagramview_window = None
    self.map_in_progress = False
    self.mapview_window = None
    self.miscview_window = None
    self.treeview_window = None
    self.video_window = None
    self.outline = False
    self.font_table = {}


def _initialize_feature_flags(self: MyGui) -> None:
    """Initializes boolean flags for various features and states."""
    self.extract_in_progress = False
    self.first_time = True
    self.list_files = False
    self.list_unnamed_items = False
    self.reset_debug_at_end = False
    self.restore = False
    self.runtime = False
    self.save = False
    self.checked_ffmpeg = False
    self.have_ffmpeg = False


def _initialize_window_positions(self: MyGui) -> None:
    """Initializes variables for storing window positions."""
    self.ai_analysis_window_position = ""
    self.ai_apikey_window_position = ""
    self.ai_popup_window_position = ""
    self.color_window_position = ""
    self.diagram_window_position = ""
    self.map_window_position = ""
    self.misc_window_position = ""
    # self.progressbar_window_position = "" # Uncomment if you decide to use this
    self.tree_window_position = ""
    self.window_position = None  # This one is generic, consider if it's needed


def _initialize_data_structures(self: MyGui) -> None:
    """Initializes data structures used by the application."""
    self.all_messages = {}
    self.conditions = None  # Consider if this should be initialized to a dict or list
    self.named_item = None  # Consider if this should be initialized to a specific type
    self.single_profile_name = None
    self.single_project_name = None
    self.single_task_name = None
    self.tab_to_use = None  # Consider if this should be initialized to a default tab
    self.check_boxes = []


def _initialize_runtime_options(self: MyGui) -> None:
    """Initializes variables related to runtime actions and program flow."""
    self.debug = None
    self.exit = None
    self.file = None  # Consider if this should be initialized to an empty string or specific file object
    self.go_program = None
    self.preferences = None
    self.rerun = None
    self.reset = None
    self.taskernet = None


# ===============================================
# Initialize the GUI screen layout using NiceGUI with split sidebars and main content area.
# ==============================================
def initialize_screen(self: MyGui) -> None:
    """Initializes the main GUI screen layout using NiceGUI with split sidebars."""
    logger.info("Building UI Layout...")

    # Inject an ultra-high-contrast scrollbar theme block targeting drawers and view scroll areas
    ui.add_head_html("""
        <style>
            /* Force scrollbar tracks to be visible on our target components */
            .force-scrollbar,
            .force-scrollbar .q-drawer__content {
                overflow-y: scroll !important; 
                overflow-x: auto !important;   
            }

            /* =========================================================================
               NATIVE BROWSER SCROLLBARS (WebKit: Chrome, Safari, Edge) - LIGHT MODE CONTRAST
               ========================================================================= */
            .force-scrollbar::-webkit-scrollbar,
            .force-scrollbar .q-drawer__content::-webkit-scrollbar {
                display: block !important;
                width: 10px !important;  /* Widened slightly for better visibility */
                height: 10px !important; 
            }
            .force-scrollbar::-webkit-scrollbar-track,
            .force-scrollbar .q-drawer__content::-webkit-scrollbar-track {
                background: rgba(0, 0, 0, 0.08) !important; /* Darkened track background */
                border-radius: 4px !important;
            }
            .force-scrollbar::-webkit-scrollbar-thumb,
            .force-scrollbar .q-drawer__content::-webkit-scrollbar-thumb {
                background: #475569 !important; /* Dark slate grey for maximum light-mode contrast */
                border-radius: 4px !important;
                border: 1px solid #ffffff !important; /* Adds a crisp border outline */
            }
            .force-scrollbar::-webkit-scrollbar-thumb:hover,
            .force-scrollbar .q-drawer__content::-webkit-scrollbar-thumb:hover {
                background: #1e293b !important; /* Deep charcoal on hover */
            }

            /* =========================================================================
               QUASAR SCROLL AREA COMPONENT (NiceGUI ui.scroll_area) - LIGHT MODE CONTRAST
               ========================================================================= */
            .q-scrollarea__thumb--v,
            .q-scrollarea__thumb--h {
                background: #475569 !important; /* Dark slate grey */
                opacity: 0.95 !important;        /* Raised opacity from 0.7 to 0.95 for heavy visibility */
                border: 1px solid #ffffff !important;
            }

            .q-scrollarea__thumb--v:hover,
            .q-scrollarea__thumb--h:hover {
                background: #1e293b !important; /* Charcoal hover */
                opacity: 1 !important;
            }

            /* =========================================================================
               DARK MODE HIGH-CONTRAST OVERRIDES (Crisp Silver/White on Dark Backgrounds)
               ========================================================================= */
            .dark .force-scrollbar::-webkit-scrollbar-track,
            .dark .force-scrollbar .q-drawer__content::-webkit-scrollbar-track {
                background: rgba(255, 255, 255, 0.1) !important; /* Visible track rule */
            }
            .dark .force-scrollbar::-webkit-scrollbar-thumb,
            .dark .force-scrollbar .q-drawer__content::-webkit-scrollbar-thumb,
            .dark .q-scrollarea__thumb--v,
            .dark .q-scrollarea__thumb--h {
                background: #e2e8f0 !important; /* Bright silver-white for popping off dark backgrounds */
                border: 1px solid #1e293b !important; /* Dark contrasting border frame */
                opacity: 0.95 !important;
            }
            .dark .force-scrollbar::-webkit-scrollbar-thumb:hover,
            .dark .force-scrollbar .q-drawer__content::-webkit-scrollbar-thumb:hover,
            .dark .q-scrollarea__thumb--v:hover,
            .dark .q-scrollarea__thumb--h:hover {
                background: #ffffff !important; /* Blinding white focus highlight */
                opacity: 1 !important;
            }

            /* Firefox Engine Fallback High-Contrast */
            .force-scrollbar,
            .force-scrollbar .q-drawer__content {
                scrollbar-width: auto !important; /* Reset to normal width for visual tracking */
                scrollbar-color: #475569 rgba(0, 0, 0, 0.08) !important;
            }
            .dark .force-scrollbar,
            .dark .force-scrollbar .q-drawer__content {
                scrollbar-color: #e2e8f0 rgba(255, 255, 255, 0.1) !important;
            }
        </style>
    """)

    # =========================================================================
    # 1. HEADER
    # =========================================================================
    with ui.header().classes("bg-blue-900 text-white p-4 justify-between items-center"):
        ui.label("MapTasker").classes("text-2xl font-bold")
        dark_mode = ui.switch("Dark Mode", value=True, on_change=lambda e: ui.dark_mode(e.value))
        self.dark_mode = dark_mode.value
        if self.dark_mode:
            self.appearance_mode = "dark"
        else:
            self.appearance_mode = "light"

    # =========================================================================
    # 2. LEFT SIDEBAR: CONFIGURATIONS, DROPDOWNS & CHECKBOXES
    # =========================================================================
    with ui.left_drawer(fixed=True).classes(
        "bg-gray-100 dark:bg-gray-800 p-4 w-96 force-scrollbar gap-y-0 m-0 p-0 leading-none",
    ) as self.left_drawer:
        ui.label("Display Options").classes("text-lg font-bold mb-2 gap-y-0 m-0 p-0 leading-none")

        # Detail level pulldown
        self.sidebar_detail_option = (
            ui
            .select(
                options=["0", "1", "2", "3", "4", "5"],
                value="2",
                label="Detail Level",
                on_change=self.event_handlers.detail_selected_event,
            )
            .tooltip("0 = least detail, 5 = most detail.")
            .classes("w-full")
        )

        # Core Feature Checkboxes
        self.everything_checkbox = ui.checkbox("Just Display Everything!").bind_value(self, "everything")
        self.conditions_checkbox = ui.checkbox("Display Conditions").bind_value(self, "conditions")
        self.taskernet_checkbox = ui.checkbox("Display TaskerNet Info").bind_value(self, "taskernet")
        self.preferences_checkbox = ui.checkbox("Display Tasker Preferences").bind_value(self, "preferences")
        self.twisty_checkbox = ui.checkbox("Hide Task Details Under Twisty").bind_value(self, "twisty")
        self.directory_checkbox = ui.checkbox("Display Directory").bind_value(self, "directory")
        self.configuration_checkbox = ui.checkbox("Display Configuration Outline").bind_value(self, "outline")
        self.pretty_checkbox = ui.checkbox("Display Prettier Output").bind_value(self, "pretty")

        # Build styling checkboxes, inputs, dropdown configurations
        # create_appearance_mode_section(self)
        _create_name_display_options_section(self)
        _create_task_action_limit_section(self)
        _create_indentation_section(self)
        _create_language_selection_section(self)
        _create_font_section(self)
        _create_view_limit_section(self)

    # =========================================================================
    # 3. RIGHT SIDEBAR: ALL ACTION, HELP & SETTINGS BUTTONS
    # =========================================================================
    # OPTIMIZED: Added 'items-center text-center' to center all items horizontally
    with ui.right_drawer(fixed=True).classes(
        "bg-gray-100 dark:bg-gray-800 p-4 w-80 force-scrollbar flex flex-col items-center text-center",
    ) as self.right_drawer:
        ui.label("Actions & Control").classes("text-lg font-bold mb-2 self-center")

        # Global Runtime Execution Triggers
        ui.label("Execution").classes("text-xs font-bold uppercase text-gray-400 mt-2 self-center")
        get_file_color = "green" if PrimeItems.file_to_get else "red"
        blink_class = "" if PrimeItems.file_to_get else " animate-pulse"

        # OPTIMIZED: Changed text layout properties to ensure centering internal contents
        self.get_xml_button = ui.button(
            "Get Local XML File",
            color=get_file_color,
            on_click=self.event_handlers.getxml_event,
            icon="folder",
        ).classes(f"w-full justify-center {blink_class}")

        self.exit_button = ui.button("Exit", on_click=lambda: get_rid_of_windows_and_exit(self)).classes(
            "w-full bg-red-600 text-white mt-4 justify-center",
        )

        # Section headings for clarity
        ui.label("File Operations").classes("text-xs font-bold uppercase text-gray-400 mt-2 self-center")
        _create_file_and_message_buttons_section(self)

        # Settings Configuration State Saving
        ui.label("Application Settings").classes("text-xs font-bold uppercase text-gray-400 mt-2 self-center")
        _create_settings_buttons_section(self)

    # =========================================================================
    # 4. MAIN BODY CONTENT AREA
    # =========================================================================
    with ui.column().classes("p-6 w-full max-w-full mx-auto"):
        # View Navigation Switching Buttons Row
        with ui.row().classes("gap-4 mb-6"):
            ui.button("Map View", on_click=lambda: self.event_handlers.view_event("map")).classes("bg-blue-500")
            ui.button("Diagram View", on_click=lambda: self.event_handlers.view_event("diagram")).classes("bg-blue-500")
            ui.button("Tree View", on_click=lambda: self.event_handlers.view_event("treeview")).classes("bg-blue-500")
            self.current_file = ui.label("No file loaded").classes("text-gray-500 italic")

        # Primary Multi-tab Application Panel Window Layout Structure
        with ui.tabs().classes("w-full") as self.main_tabs_container:
            self.tab_specific_name = ui.tab("Specific Name", icon="filter_list")
            self.tab_colors = ui.tab("Colors", icon="palette")
            self.tab_analyze = ui.tab("Analyze", icon="analytics")
            self.tab_debug = ui.tab("Debug", icon="bug_report")

        with ui.tab_panels(self.main_tabs_container, value=self.tab_specific_name).classes(
            "w-full border rounded shadow-inner p-6 mt-2",
        ):
            # Specific Name panel for targeting specific Projects, Profiles, or Tasks
            with ui.tab_panel(self.tab_specific_name):
                ui.label("Target specific Projects, Profiles, or Tasks.").classes("text-lg mb-4")
                self.specific_project_optionmenu = ui.select(["None"], label="Project").classes("w-64 mb-2")
                self.specific_profile_optionmenu = ui.select(["None"], label="Profile").classes("w-64 mb-2")
                self.specific_task_optionmenu = ui.select(["None"], label="Task").classes("w-64 mb-2")
                self.specific_name_msg_label = ui.label("").classes("text-xs ml-2 mt-2 text-left")
                self.list_unnamed_items_checkbox = ui.checkbox("List Unnamed Items").bind_value(
                    self,
                    "list_unnamed_items",
                )

            # Colors panel for configuring theme colors and styles
            with ui.tab_panel(self.tab_colors):
                ui.label("Theme Configuration").classes("text-lg mb-2")
                ui.button(
                    "Reset to Default Colors",
                    on_click=self.event_handlers.color_reset_event,
                ).classes("bg-blue-500")

                # Dynamic placeholder label to display the active state
                self.color_change = ui.label("Select a category to modify its color.").classes("text-sm mt-4")

                # The Dropdown Select Menu
                self.color_objects_options = ui.select(
                    options=[
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
                    value="Projects",
                    label="Select Category to Colorize",
                ).classes("w-64 mt-2")

                # Place a persistent native Color Input field directly in the layout
                self.color_picker_input = ui.color_input(
                    label="Choose Hex Color",
                    value="#3f99ff",
                    on_change=lambda e: self.event_handlers.handle_color_pick_event(e.value),
                ).classes("w-64 mt-2")

            # AI Analysis panel for configuring AI model, API keys, and prompts
            with ui.tab_panel(self.tab_analyze):
                ui.label("AI Analysis").classes("text-lg mb-4")
                _create_analyze_tab_content(self, ui.tab_panel(self.tab_analyze))

            # Debug panel for toggling debug mode and runtime settings
            with ui.tab_panel(self.tab_debug):
                self.debug_checkbox = ui.checkbox("Debug Mode").bind_value(self, "debug")
                self.runtime_checkbox = ui.checkbox("Display Runtime Settings")

        # Dedicated full-width dynamic container slot block target for (Map, etc.) views now displays
        # BELOW the tabs.
        self.content_container = ui.column().classes("w-full max-w-full p-0 m-0 mt-6")

        # Persistent global dialog container for selecting display colors safely
        with ui.dialog() as self.picker_dialog, ui.card().classes("p-4 items-center"):
            self.picker_title_label = ui.label("").classes("font-bold text-sm mb-2")
            self.picker_engine = ui.color_picker()
            ui.button("Cancel", on_click=self.picker_dialog.close).classes("mt-4 w-full bg-gray-500 text-white")

    # Set the last-used tab to use
    if self.tab_to_use:
        self.main_tabs_container.set_value = self.tab_to_use


def get_rid_of_windows_and_exit(self: MyGui, delete_all: bool = True) -> None:
    """Shuts down the NiceGUI server and exits."""
    ui.notify("Shutting down MapTasker...", type="warning")
    app.shutdown()


def _create_analyze_tab_content(self: MyGui, tab: ui.tab_panel) -> None:
    """Populates the 'Analyze' (AI) tab using NiceGUI and colors the analysis button contextually."""

    # Use the 'with' context manager to place elements inside the passed tab panel
    with tab:
        # 1. Action Buttons Row
        with ui.row().classes("items-center gap-4 mb-4"):
            self.show_apikeys_button = ui.button("Show/Edit API Key(s)", on_click=self.event_handlers.ai_apikey_event)
            self.change_prompt_button = ui.button("Change Prompt", on_click=self.event_handlers.ai_prompt_event)

            # --- DYNAMIC ANALYSIS BUTTON COLORING LOGIC ---
            # Determine if any required fields are empty/None
            has_key = bool(getattr(self, "ai_apikey", None))
            has_model = bool(getattr(self, "ai_model", "")) and getattr(self, "ai_model") != "None"
            has_prompt = bool(getattr(self, "ai_prompt", ""))

            # If everything is filled out, make it green. Otherwise, color it red.
            analysis_btn_color = "green" if (has_key and has_model and has_prompt) else "red"

            self.analysis_button = ui.button(
                "Run Analysis",
                color=analysis_btn_color,
                on_click=self.event_handlers.ai_analyze_event,
            )

        # 2. Model Selection Row
        with ui.row().classes("items-center gap-4"):
            self.model_to_use_label = ui.label("Model to Use:").classes("font-bold")

            # Display the default model list
            display_model_pulldown(self)

            # Extra model list checkbox with chained tooltip
            self.aimodel_extend_checkbox = (
                ui
                .checkbox("Extended", on_change=self.event_handlers.extended_models_event)
                .tooltip(
                    "Display an extended list of ALL available models.\n\n"
                    "Note: If the API key is not set for OpenAI or Gemini,\n"
                    "      then the default model list for the respective\n"
                    "      AI provider will be displayed.\n\n"
                    "Note: Not all models have been validated and\n"
                    "      one or more may return an error on analysis.\n\n"
                    "Note: Enabling this option for the first time will\n"
                    "      force the installation of the following modules\n"
                    "      and all of their dependencies:\n"
                    "      google-genai, anthropic, openai, ollama",
                )
                .style("white-space: pre-line")
            )  # Ensures the newline characters format correctly in HTML


# FIX Delete code
# def create_appearance_mode_section(self: MyGui) -> None:
#     """Creates the appearance mode selection in the NiceGUI sidebar."""
#     # Label for the section
#     self.appearance_mode_label = ui.label("Appearance Mode:").classes(
#         "text-sm font-semibold mt-2 gap-y-0 m-0 p-0 leading-none",
#     )

#     # Dropdown select menu mapping to your event handler
#     self.appearance_mode_optionmenu = ui.select(
#         options=["Light", "Dark", "System"],
#         value="Dark",  # Default initial value
#         on_change=self.event_handlers.change_appearance_mode_event,
#     ).classes("w-full py-0 my-0 gap-y-0 m-0 p-0 leading-none")  # Adjust padding and margin to reduce spacing


def _create_name_display_options_section(self: MyGui) -> None:
    """
    Optimized creation of name display options using NiceGUI.
    Renders a section header and a condensed 2x2 grid of styling checkboxes.
    """
    handlers = self.event_handlers

    # 1. Create the Section Label with an inline native tooltip
    self.display_names_label = (
        ui
        .label("Project/Profile/Task/Scene Names:")
        .classes("text-sm font-semibold mt-4 mb-1 py-0 my-0 gap-y-0 leading-none")
        .tooltip("Add highlighting to Project, Profile and Task names in the output.")
    )

    # 2. Define Checkbox Configurations
    checkbox_configs = [
        (
            "bold_checkbox",
            handlers.names_bold_event,
            "Bold",
            "Bold and Italicize are mutually exclusive in the Map view.",
        ),
        (
            "italicize_checkbox",
            handlers.names_italicize_event,
            "Italicize",
            "Italicize and Bold are mutually exclusive in the Map view.",
        ),
        ("highlight_checkbox", handlers.names_highlight_event, "Highlight", None),
        ("underline_checkbox", handlers.names_underline_event, "Underline", None),
    ]

    # 3. Batch Creation inside a highly condensed 2-Column Grid Layout
    # Changed gap-y-1 to gap-y-0 to completely eliminate grid vertical row spacing
    with ui.grid(columns=2).classes("w-full gap-x-4 py-0 my-0 gap-y-0 pl-2"):
        for attr, event, label, tip in checkbox_configs:
            # Instantiate the checkbox and strip vertical padding/margins via py-0 my-0
            checkbox = ui.checkbox(label, on_change=event).classes("py-0 my-0")

            # Save the reference dynamically to the 'self' instance
            setattr(self, attr, checkbox)

            # Chain the tooltip natively if one is defined
            if tip:
                checkbox.tooltip(tip)


def _create_task_action_limit_section(self: MyGui) -> None:
    """Creates the task 'actions' limit slider in the NiceGUI sidebar."""
    text_to_insert = "Task 'actions' limit"
    text = PrimeItems._(text_to_insert) if hasattr(PrimeItems, "_") else text_to_insert

    # 1. Label tracking the live dynamic value
    self.task_action_label = ui.label(f"{text}: {self.task_action_warning_limit}").classes(
        "text-sm font-semibold mt-4 mb-1 py-0 my-0 gap-y-0",
    )

    # 2. NiceGUI Slider
    # CustomTkinter uses 'command=', NiceGUI uses 'on_change='
    # NiceGUI handles styling with Tailwind (e.g., track color tints via accent)
    self.task_action_limit = ui.slider(
        min=10,
        max=100,
        step=1,
        value=100,
        on_change=self.event_handlers.tasklimit_event,
    ).classes(
        "w-full px-2 accent-green-600 py-0 my-0 gap-y-0",
    )
    with self.task_action_limit:
        ui.tooltip(
            "Select how many actions in a Task before issuing a warning.\n"
            "The warning appears near the bottom of the configuration output,\n"
            "and is intended to help identify Tasks that are too complex\n"
            "and which should potentially be broken up into multiple Tasks.\n"
            "A setting of '100' means there is no limit.",
        ).style("white-space: pre-line")  # Ensures the tooltip text respects newlines for better readability


def _create_indentation_section(self: MyGui) -> None:
    """Creates the If/Then/Else indentation dropdown options in the NiceGUI sidebar."""
    self.indent_label = ui.label("If/Then/Else Indentation Amount:").classes(
        "text-sm font-semibold mt-4 mb-1 leading-none py-0 my-0 gap-y-0",
    )

    # CustomTkinter's option menu transforms into ui.select
    self.indent_option = ui.select(
        options=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
        value="4",  # Default initial value matching your original comments
        on_change=self.event_handlers.indent_selected_event,
    ).classes("w-full leading-none py-0 my-0 gap-y-0")
    with self.indent_option:
        ui.tooltip(
            "Set the indentation amount for If/Then/Else blocks.\n\n"
            "The default is '4'.\n\n"
            "This affects how the output is formatted in the Map and Diagram views.",
        ).style("white-space: pre-line")  # Ensures the tooltip text respects newlines for better readability


def _create_language_selection_section(self: MyGui) -> None:
    """Creates the language selection dropdown in the NiceGUI sidebar."""
    self.language_label = ui.label("Language:").classes(
        "text-sm font-semibold mt-4 mb-1 leading-none py-0 my-0 gap-y-0",
    )

    languages = sort_languages_with_priority(PrimeItems.languages.keys())

    # Pre-determine current translated initial string match
    initial_language = translate_string(self.language)

    self.language_optionmenu = ui.select(
        options=languages,
        value=initial_language,
        on_change=self.event_handlers.language_selected_event,
    ).classes("w-full")


def _create_view_limit_section(self: MyGui) -> None:
    """Creates the view limit dropdown in the sidebar drawer."""
    self.viewlimit_label = ui.label("View Limit:").classes(
        "text-sm font-semibold mt-4 mb-1 leading-none py-0 my-0 gap-y-0",
    )

    with ui.row().classes("w-full items-center gap-2"):
        # CustomTkinter's option menu becomes a ui.select dropdown
        self.viewlimit_optionmenu = ui.select(
            options=["5000", "10000", "15000", "20000", "25000", "30000", "Unlimited"],
            value=str(getattr(self, "view_limit", "10000")),
            on_change=self.event_handlers.viewlimit_event,
        ).classes("flex-grow")
        with self.viewlimit_optionmenu:
            ui.tooltip(
                "Select the maximum number of items to display in the view to be allowed.\n\n"
                "Anything over this amount will stop the generation of the view as a means to throttle the program.\n\n"
                "Note: This is only for the 'Map' and 'Diagram' views, not the tree view.",
            ).style("white-space: pre-line")  # Ensures the tooltip text respects newlines for better readability

        # Query help button
        self.viewlimit_query_button = ui.button(
            "?",
            on_click=lambda: self.event_handlers.query_event("viewlimit"),
        ).classes("bg-blue-600 text-white min-w-[40px]")


def _create_settings_buttons_section(self: MyGui) -> None:
    """Creates settings buttons in their respective responsive layout containers."""
    handlers = self.event_handlers

    # 1. Sidebar Buttons (Master: self.left_drawer)
    with self.left_drawer:
        self.reset_button = ui.button("Reset Options", on_click=handlers.reset_settings_event).classes(
            "w-full bg-blue-600 text-white mt-2",
        )
        # Nest the tooltip explicitly inside the button context
        with self.reset_button:
            ui.tooltip(
                "Reset all of the options to their default values, including colors, font used, and other settings.\n\n"
                "The currently loaded XML will be cleared out.",
            ).style("white-space: pre-line;")  # Tells the web browser to render \n newlines!

    # 2. Main Window Buttons Layout Area
    # Placed in a clean horizontal flexrow inside the body content columns
    # 2. Main Window Buttons Layout Area
    # OPTIMIZED: Added 'justify-center w-full' to ensure proper alignment controls
    with ui.row().classes("w-full gap-2 mt-4 justify-center"):
        self.save_settings_button = ui.button("Save Settings", on_click=handlers.save_settings_event).classes(
            "bg-indigo-600 text-white justify-center",
        )

        self.restore_settings_button = ui.button("Restore Settings", on_click=handlers.restore_settings_event).classes(
            "bg-indigo-600 text-white justify-center",
        )

        self.report_issue_button = ui.button("Report Issue", on_click=handlers.report_issue_event).classes(
            "bg-gray-600 text-white justify-center",
        )
        with self.report_issue_button:
            ui.tooltip(
                "Report any issues and/or suggestions to the developer.\n\n"
                "This will open a browser window to the GitHub Issues page, and you will need a GitHub account to submit an issue.",
            ).style("white-space: pre-line;")


def _create_font_section(self: MyGui) -> None:
    """Creates the monospaced font selection dropdown inside the content container."""
    self.font_label = ui.label("Font To Use In Output:").classes(
        "text-sm font-semibold mt-4 mb-1 py-0 my-0 gap-y-0 m-0 p-0 leading-none",
    )

    if not PrimeItems.mono_fonts:
        font_items = get_monospace_fonts()
        PrimeItems.mono_fonts = font_items
    else:
        font_items = PrimeItems.mono_fonts

    default_font = [value for value in font_items if "Courier" in value]
    self.default_font = default_font[0] if default_font else font_items[0]

    # ui.select manages choices natively
    self.font_optionmenu = ui.select(
        options=font_items,
        value=font_items[0] if font_items else self.default_font,
        on_change=self.event_handlers.font_event,
    ).classes("w-64")
    with self.font_optionmenu:
        ui.tooltip(
            "This is a list of all of the monospaced fonts available on your system.\n\n"
            "The font selected will be used in all output.\n\n"
            "'Courier' or 'Courier New' is highly recommended for Diagrams to ensure proper connector alignment.",
        ).style("white-space: pre-line;")  # Ensures newlines render properly in the tooltip


def _create_file_and_message_buttons_section(self: MyGui) -> None:
    """Creates file actions and message configuration button rows."""
    # OPTIMIZED: Added 'justify-center' to center-align the row contents
    with ui.row().classes("w-full items-center justify-center gap-4 mt-4"):
        # Uses your existing display_backup_button logic defined in guiwins.py
        self.get_backup_button = self.display_backup_button(
            "Get XML from Android Device",
            "#246FB6",
            "#6563ff",
            self.event_handlers.get_xml_from_android_event,
        )
        with self.get_backup_button:
            ui.tooltip(
                "Fetch XML from an Android device.\n\n"
                "Note: This requires ADB to be installed and configured on your computer, and the Android device to have USB debugging enabled.\n\n"
                "The XML fetched will become the current source for MapTasker commands.",
            ).style("white-space: pre-line")

        # OPTIMIZED: Added 'w-full justify-center' so it matches structural formatting boundaries
        self.getxml_button = ui.button("Get Local XML", on_click=self.event_handlers.getxml_event).classes(
            "bg-green-600 text-white w-full justify-center",
        )
        with self.getxml_button:
            ui.tooltip(
                "Fetch XML from a local drive on this computer.\n\nThe XML fetched will become the current source for MapTasker commands.",
            ).style("white-space: pre-line")  # Ensures the tooltip text respects newlines for better readability

        self.getxml_button = ui.button("Get Local XML", on_click=self.event_handlers.getxml_event).classes(
            "bg-green-600 text-white",
        )
        with self.getxml_button:
            ui.tooltip(
                "Fetch XML from a local drive on this computer.\n\nThe XML fetched will become the current source for MapTasker commands.",
            ).style("white-space: pre-line")  # Ensures the tooltip text respects newlines for better readability


# FIX Deleet section below if not needed.  It was used in the original Tkinter GUI but is not needed in NiceGUI.
# def _create_browser_options_section(self: MyGui) -> None:
#     """Creates browser execution panels, help routing shortcuts, and app termination controls."""
#     handlers = self.event_handlers

#     # 1. Specialized Help Buttons Row
#     with ui.row().classes("w-full gap-2 mt-4"):
#         self.display_help_button = ui.button("Display Help", on_click=lambda: handlers.query_event("help")).classes(
#             "bg-blue-600 text-white",
#         )

#         self.get_android_help_button = ui.button(
#             "Get Android Help",
#             on_click=lambda: handlers.query_event("android"),
#         ).classes("bg-blue-600 text-white")


# 2. Section Subtitle Label
# self.text_message_label = ui.label("Browser Options").classes("text-lg font-bold mt-6 mb-2")

# # 3. Execution Action Action Controllers
# with ui.row().classes("w-full gap-2"):
#     self.run_button = ui.button("Run and Exit", on_click=handlers.run_program_event).classes(
#         "bg-green-600 text-white",
#     )
#     with self.run_button:
#         ui.tooltip(
#             "Generate a map of the current XML, save the results as an html file and display the map in the default browser.\n\n"
#             "The program terminates when done.",
#         ).style("white-space: pre-line")  # Ensures the tooltip text respects newlines for better readability

#     self.rerun_button = ui.button("ReRun", on_click=handlers.rerun_event).classes("bg-green-600 text-white")
#     with self.rerun_button:
#         ui.tooltip(
#             "Same as the 'Run and Exit' button,\nbut the program restarts after displaying the browser output.",
#         ).style("white-space: pre-line")  # Ensures the tooltip text respects newlines for better readability

# 4. Global Application Exit Button
# Uses your exit router already linked in initialize_screen inside guiwins.py
