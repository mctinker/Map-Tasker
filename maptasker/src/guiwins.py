"""GUI Window Classes and Definitions (NiceGUI Version)"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import app, ui

from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import DIAGRAM_PROFILES_PER_LINE, logger

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


def create_progressbar_window() -> tuple[ui.dialog, ui.linear_progress]:
    """Creates a modal with a progress bar. Replaces ProgressbarWindow."""
    with ui.dialog() as dialog, ui.card().classes("min-w-[400px] p-6 items-center"):
        ui.label("Processing...").classes("text-lg mb-4 font-bold")
        progress = ui.linear_progress(value=0.0, show_value=False).classes("w-full")

    dialog.open()
    return dialog, progress


# ==========================================
# 3. VIEWS (Tree and Text)
# ==========================================
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

    def build_ui(self) -> None:
        """Builds the UI layout for the text view, including toolbar and scrollable display area."""
        # Toolbar
        with ui.row().classes("w-full items-center gap-2 p-2 mb-2 bg-gray-200 dark:bg-gray-800 rounded"):
            ui.label(f"{self.title} View").classes("text-orange-500 font-bold mr-4")
            self.search_input = ui.input(placeholder="Search...").classes("w-48")
            ui.button("Search", on_click=self.search_event).classes("bg-blue-600")
            ui.button("Clear", on_click=lambda: self.search_input.set_value("")).classes("bg-blue-600")
            ui.separator().props("vertical")
            ui.button("Top", on_click=lambda: self.scroll("top")).classes("bg-blue-600")
            ui.button("Bottom", on_click=lambda: self.scroll("bottom")).classes("bg-blue-600")

        # Text Display Area
        self.scroll_area = ui.scroll_area().classes(
            "w-full h-[70vh] border-2 border-gray-600 p-4 font-mono text-sm whitespace-pre bg-white dark:bg-black",
        )
        with self.scroll_area:
            self.html_display = ui.html()

    def process_data(self: MyGui, the_data: dict | list) -> None:
        """Converts data to an HTML string."""
        if self.is_map:
            html_builder = []
            for num, (linenum, value) in enumerate(the_data.items()):
                text_list = value.get("text", [])
                color_list = value.get("color", [])
                line_html = "<div>"
                for t_idx, text_segment in enumerate(text_list):
                    safe_text = str(text_segment).replace("<", "&lt;").replace(">", "&gt;")
                    color = color_list[t_idx] if t_idx < len(color_list) else "inherit"
                    line_html += f"<span style='color: {color};'>{safe_text}</span>"
                html_builder.append(line_html + "</div>")
            self.html_display.content = "".join(html_builder)
        else:
            safe_lines = [line.replace("<", "&lt;").replace(">", "&gt;") for line in the_data]
            self.html_display.content = "<div>" + "</div><div>".join(safe_lines) + "</div>"

    def search_event(self) -> None:
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
def initialize_gui(self) -> None:
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


def initialize_screen(self: MyGui) -> None:
    """Initializes the main GUI screen layout using NiceGUI."""
    logger.info("Building UI Layout...")

    # Header
    with ui.header().classes("bg-blue-900 text-white p-4 justify-between items-center"):
        ui.label("MapTasker").classes("text-2xl font-bold")
        ui.switch("Dark Mode", value=True, on_change=lambda e: ui.dark_mode(e.value))

    # Sidebar (Left Drawer)
    with ui.left_drawer(fixed=True).classes("bg-gray-100 dark:bg-gray-800 p-4 w-80 flex flex-col gap-2"):
        ui.label("Display Options").classes("text-lg font-bold mb-2")

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

        ui.checkbox("Just Display Everything!").bind_value(self, "everything")
        ui.checkbox("Display Conditions").bind_value(self, "conditions")
        ui.checkbox("Display TaskerNet Info").bind_value(self, "taskernet")
        ui.checkbox("Display Tasker Preferences").bind_value(self, "preferences")
        ui.checkbox("Hide Task Details Under Twisty").bind_value(self, "twisty")
        ui.checkbox("Display Directory").bind_value(self, "directory")
        ui.checkbox("Display Configuration Outline").bind_value(self, "outline")
        ui.checkbox("Display Prettier Output").bind_value(self, "pretty")

        ui.separator().classes("my-4")

        # Sidebar buttons
        with ui.row().classes("w-full justify-between gap-2"):
            ui.button(
                "Get Local XML File",
                color="green",
                on_click=self.event_handlers.getxml_event,
                icon="folder",
            ).classes(
                "flex-grow",
            )
            ui.button("Run & Exit", color="green", on_click=self.event_handlers.run_program_event).classes("flex-grow")
            ui.button("ReRun", color="green", on_click=self.event_handlers.rerun_event).classes("flex-grow")

        ui.button("Exit", color="red", on_click=lambda: get_rid_of_windows_and_exit(self)).classes("w-full mt-4")

    # Main Content Area
    with ui.column().classes("p-6 w-full max-w-5xl mx-auto"):
        # View Buttons
        # --> FIXED: Pointed to self.event_handlers
        with ui.row().classes("gap-4 mb-6"):
            ui.button("Map View", on_click=lambda: self.event_handlers.view_event("map")).classes("bg-blue-500")
            ui.button("Diagram View", on_click=lambda: self.event_handlers.view_event("diagram")).classes("bg-blue-500")
            ui.button("Tree View", on_click=lambda: self.event_handlers.view_event("treeview")).classes("bg-blue-500")
            self.current_file = ui.label("No file loaded").classes("text-gray-500 italic")

        # Tabs
        with ui.tabs().classes("w-full") as tabs:
            self.tab_specific_name = ui.tab("Specific Name", icon="filter_list")
            self.tab_colors = ui.tab("Colors", icon="palette")
            self.tab_analyze = ui.tab("Analyze", icon="analytics")
            self.tab_debug = ui.tab("Debug", icon="bug_report")

        with ui.tab_panels(tabs, value=self.tab_specific_name).classes("w-full border rounded shadow-inner p-6 mt-2"):
            with ui.tab_panel(self.tab_specific_name):
                ui.label("Target specific Projects, Profiles, or Tasks.").classes("text-lg mb-4")
                ui.select(["None"], label="Project").classes("w-64 mb-2")
                ui.select(["None"], label="Profile").classes("w-64 mb-2")
                ui.select(["None"], label="Task").classes("w-64 mb-2")
                ui.checkbox("List Unnamed Items")

            with ui.tab_panel(self.tab_colors):
                ui.label("Theme Configuration").classes("text-lg")
                ui.button("Reset to Default Colors")

            with ui.tab_panel(self.tab_analyze):
                ui.label("AI Analysis").classes("text-lg mb-4")
                with ui.row().classes("gap-4"):
                    ui.button("Show/Edit API Key(s)")
                    ui.button("Change Prompt")

            with ui.tab_panel(self.tab_debug):
                ui.checkbox("Debug Mode").bind_value(self, "debug")
                ui.checkbox("Display Runtime Settings")


def get_rid_of_windows_and_exit(self: MyGui, delete_all: bool = True) -> None:
    """Shuts down the NiceGUI server and exits."""
    ui.notify("Shutting down MapTasker...", type="warning")
    app.shutdown()
