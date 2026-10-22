"""The rendered views: Map, Diagram and Misc, Tree, and Scene Preview.

Split out of guiwins.py, which after the dialog families left still held all three views
and everything they draw with.  The views are now one module each:

    guiwins_textview     the Map, Diagram and Misc text view (NiceGuiTextView)
    guiwins_mapstream    what the text view streams the Map through: the clean-up and the splitter
    guiwins_diagram      the Diagram's own drawing: connector spans, line wrapping, its toolbar
    guiwins_sceneview    the Scene Preview view, and the Scene editor session hand-off

What is left here is the Tree view (NiceGuiTreeView), the toolbar's scope badge, and the colours
every view takes from the page's theme.

Search, Find and Replace are in guiwins_search.py, which NiceGuiTextView inherits them
from; the registry of open views and the jumps into them are in guiwins_nav.py.  Both sit
below the views, and guiwins.py above them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from maptasker.src.core.maputil2 import translate_string
from maptasker.src.gui.guiwins_nav import (
    live_views,
    register_view,
)

if TYPE_CHECKING:
    from maptasker.src.gui.userintr import MyGui


# ==========================================
# THE VIEWS
# ==========================================
def scope_badge_text(built_for: str, now: str) -> tuple[str, str]:
    """What the toolbar badge says: (what this view was drawn for, what has changed since).

    The second half is "" when the two agree, which is what the view shows and hides the
    stale line and the Rebuild button by.  Both halves name the selection in the words the
    pulldowns use ("Project 'Home'", "Task 'Wake Up'"), and the whole configuration is said
    rather than left as a blank, because a badge reading "Drawn for" and then nothing looks
    like something failed to load.
    """
    everything = translate_string("the whole configuration")
    drawn = f"{translate_string('Drawn for')} {built_for or everything}"
    if (built_for or "") == (now or ""):
        return drawn, ""
    return drawn, f"-- {translate_string('now showing')} {now or everything}"


def refresh_scope_badges(master_gui: MyGui) -> None:
    """Tell every open view that the single-item selection has changed.

    Called from the one funnel a changed selection goes through (userintr_loading.process_name_event),
    so a Diagram drawn for the old selection says so the moment the user picks a new one
    rather than the next time they happen to look at its toolbar.

    Touches text and visibility on elements that already exist, which is what makes it safe
    from a pulldown's handler in the MAIN window: those elements belong to the popout's
    client, and NiceGUI sends a property change to whichever client owns the element.
    Creating one there would be the problem -- see register_finding_clicks on what building
    into a live page costs.
    """
    for view in live_views(master_gui):
        try:
            view.refresh_scope_badge()
        except (AttributeError, RuntimeError):
            continue  # A view without a badge, or one whose page went away mid-update.


def view_theme_colors(master_gui: MyGui) -> tuple[str, str]:
    """The (background, foreground) a view should paint itself with right now.

    Same pair the dark-mode toggle hands to the drawers, panels and text views, so a view
    that has to colour itself at build time -- the toggle's on_change only fires when the
    switch is actually clicked -- lands on exactly what the rest of the window is using.
    Defaults to light when the switch has never been touched, which is the state the page
    starts in (ui.dark_mode() mounts disabled regardless of the switch's initial value).
    """
    is_dark = bool(getattr(master_gui, "dark_mode", False))
    bg = "#1e293b" if is_dark else "#ffffff"
    fg = "#ffffff" if is_dark else "#000000"
    return (getattr(master_gui, "color_lookup", None) or {}).get("background", bg), fg


class NiceGuiTreeView:
    """Replaces CTkTreeview. Renders a hierarchical tree representation in the main view column."""

    def __init__(self, master_gui: MyGui, title: str, items: list) -> None:
        """Initialize the Tree view with a title and hierarchical items."""
        self.master_gui = master_gui
        self.title = title
        self.build_ui(items)
        register_view(master_gui, self)

    def build_ui(self, items: list) -> None:
        """Build the base UI layout for the Tree view inside the main content container slot."""

        # 1. Target and clear the dedicated full-width main view column slot
        if hasattr(self.master_gui, "content_container") and self.master_gui.content_container:
            self.master_gui.content_container.clear()
            container_context = self.master_gui.content_container
        else:
            container_context = ui.column()  # Fallback context if called standalone

        # 2. Render the layout inside the main application body container
        with container_context:
            self.card = ui.card().classes(
                "maptasker-tree-card w-full max-w-full mx-auto p-6 shadow-md border-2 border-gray-300",
            )
            with self.card:
                # Header row with title and navigation hints
                with ui.row().classes("items-center justify-between w-full border-b pb-3 mb-4"):
                    ui.label(f"{self.title}").classes("text-orange-500 font-bold text-lg")
                    ui.label(translate_string("Click arrows to expand/collapse details.")).classes(
                        "text-xs text-gray-500 italic",
                    )

                # Convert MapTasker nested dictionary list nodes to NiceGUI tree notation
                tree_data = self._format_data(items)

                # 3. Create a scrollable window container for large tree structures
                self.scroll_area = ui.scroll_area().classes("w-full h-[65vh] p-2")
                with self.scroll_area:
                    # Render the native responsive Tree component
                    # Injected custom fonts to preserve monospace formatting matches
                    self.tree = (
                        ui.tree(tree_data, label_key="label", children_key="children", tick_strategy=None)
                        .classes("w-full text-base")
                        .style(f"font-family: '{self.master_gui.font}', monospace;")
                    )

        self.apply_theme(*view_theme_colors(self.master_gui))

    def apply_theme(self, bg: str, fg: str) -> None:
        """Paint this view's card and scroll area for the mode the window is currently in.

        Unlike the Map/Diagram views -- whose scroll area the dark-mode toggle restyles by
        hand -- the Tree view's container used to carry no colours of its own, leaving it to
        whichever stylesheet rule won the cascade for .q-card / .q-scrollarea. That is a
        fragile thing to depend on across browsers and NiceGUI/Quasar releases (it is what
        left this one container white in dark mode), so state the colours outright instead.
        "!important" for the same reason the Map view's background needs it: it has to beat
        the equally-important light/dark overrides injected by inject_shared_head_styles().
        The node labels follow along through the .maptasker-tree-card rule in that same
        stylesheet, which hands them this card's colour instead of Quasar's theme colour.
        """
        style = f"background-color: {bg} !important; color: {fg} !important;"
        self.card.style(style)
        self.scroll_area.style(style)

    def _format_data(self, items: list, parent_id: str = "node") -> list:
        """Converts MapTasker lists/dicts into NiceGUI's strict dict format,

        replacing HTML non-breaking spaces (&nbsp;) with standard spaces
        and cleaning raw arrow entities (&#11013;) into clear symbols.
        """
        formatted_nodes = []
        for i, item in enumerate(items):
            current_id = f"{parent_id}_{i}"
            if isinstance(item, dict):
                # Extract the name and clean out the raw HTML markup fragments
                raw_name = item.get("name", "Unnamed")
                clean_name = (
                    raw_name.replace("&nbsp;", " ")
                    .replace("&#9940;", "⛔")
                    .replace("&#11013;", "⬅️")
                    .replace("&#11157;", "➡️")
                    .ljust(50)
                )

                node = {"id": current_id, "label": clean_name}
                if item.get("children"):
                    node["children"] = self._format_data(item["children"], current_id)
                formatted_nodes.append(node)
            else:
                # Handle raw string line items (like nested Task Actions or standalone strings)
                clean_string = (
                    str(item)
                    .replace("&nbsp;", " ")
                    .replace("&#9940;", "⛔")
                    .replace("&#11013;", "⬅️")
                    .replace("&#11157;", "➡️")
                )
                formatted_nodes.append({"id": current_id, "label": clean_string})
        return formatted_nodes
