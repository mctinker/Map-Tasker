"""guiwins_textview: the view of the Map, the Diagram and Misc output as text in the page.

NiceGuiTextView streams the Map through guiwins_mapstream, draws the Diagram through guiwins_diagram, and inherits
Search, Find and Replace from guiwins_search."""

from __future__ import annotations

import asyncio
import json
import re
from typing import TYPE_CHECKING, cast

from nicegui import run, ui

from maptasker.src.core import assettext, mapjump
from maptasker.src.core.htmlsafe import css_color
from maptasker.src.core.maputil2 import suppress_logged, translate_string
from maptasker.src.core.outdir import output_path
from maptasker.src.core.sysconst import DIAGRAM_FILE, logger
from maptasker.src.gui.guiwins_diagram import (
    create_diagram_tools,
    create_export_menu,
    diagram_connectors_by_line,
    wrap_diagram_line,
)
from maptasker.src.gui.guiwins_mapstream import (
    compress_blank_lines,
    fallback_lines_html,
    fallback_map_html,
    optimize_map_html,
    split_for_streaming,
)
from maptasker.src.gui.guiwins_nav import (
    _report_view_failure,
    enable_finding_clicks,
    register_finding_clicks,
    register_view,
)
from maptasker.src.gui.guiwins_search import SEARCH_JAVASCRIPT_TIMEOUT, TextViewSearch
from maptasker.src.gui.guiwins_views import scope_badge_text
from maptasker.src.mapgen import diagintr, mapexport

if TYPE_CHECKING:
    from nicegui.events import ValueChangeEventArguments

    from maptasker.src.analysis import mapfind
    from maptasker.src.gui.userintr import MyGui


class NiceGuiTextView(TextViewSearch):
    """Replaces CTkTextview. Handles rendering MapTasker data using HTML."""

    # The Diagram toolbar's caption, put there by the builder that makes the toolbar.
    diagram_state_label: ui.label

    def __init__(
        self,
        master_gui: MyGui,
        title: str,
        the_data: list | dict | str,
        container: ui.column | None = None,
        jump_to: str = "",
        map_scope: str = "",
        built_for: str = "",
    ) -> None:
        """Initialize the NiceGuiTextView.

        If `container` is given, the view is built inside it directly instead of the
        master GUI's main content_container -- used to render into a separate popped-out
        browser window/tab without disturbing the main window's layout.

        `jump_to` is a mapjump token this view scrolls to and highlights the moment its
        content has finished streaming in -- how a clicked report finding reaches a Map
        that had to be built for it.  Acted on there and not before, because a chunk that
        has not arrived cannot be scrolled to.

        `map_scope` is the Project a Map view was built for ("" for the whole file).  It is
        what lets a later clicked finding tell a Map that can show what it points at from
        one that merely contains it -- see jump_map_view.

        `built_for` is what the app was displaying when this view was drawn, as the phrase a
        person reads -- "Project 'Home'", "" for the whole configuration.  Only the toolbar
        badge uses it (see _build_scope_badge); nothing decides anything by it.
        """
        self.master_gui = master_gui
        self.title = title
        self.is_map = isinstance(the_data, dict)
        self.external_container = container
        self.jump_to = jump_to
        self.map_scope = map_scope
        self.built_for = built_for
        # The toolbar's "built for" line and the "the selection has moved on" line beside it.
        # Held on the view so refresh_scope_badges can update them later without a slot: an
        # element's text can be changed from anywhere, while CREATING one cannot.
        self.scope_label = None
        self.scope_stale_label = None
        self.scope_rebuild_button = None
        # Search caching (see search_event). The token identifies the content currently in
        # this view: 0 means "not searchable as a stable document yet" -- process_data streams
        # the content in chunk by chunk, so anything cached about the DOM mid-stream would be
        # a snapshot of a partial document. _mark_content_ready() bumps it once streaming ends,
        # and reload_diagram() drops it back to 0 while the content is replaced.
        self._content_token = 0
        self._content_generation = 0
        self._last_search: tuple[str, list, int, bool] | None = None
        # The last structured question asked of this view (see find_event).  Held so that
        # re-opening Find comes back to the query whose result row the user just followed,
        # rather than to an empty dialog they have to fill in again.
        self.find_query: mapfind.Query | None = None
        # The Find dialog's question out with an AI model, while it is out -- held on the view
        # rather than the dialog so that _dismiss_find_dialog, which deletes a dialog without
        # its "hide" firing, can still cancel it (see cancel_find_ask).
        self.find_ask: asyncio.Task | None = None
        # The last Replace the user set up on this view -- ("action", old key, new key,
        # project) or ("variable", name, owner, new name).  The INPUTS, not the Plan: a
        # Plan holds live elements, and holding those across a dialog that may have been
        # reopened after another edit is the stale-handle bug apply()'s own attachment
        # check exists to catch.  Reopening rebuilds the plan from these instead.
        self.replace_inputs: tuple | None = None
        # The Find/Replace dialog this view currently has up, or None.  Held because that
        # dialog no longer always takes itself down: following one of its own rows docks it
        # to the right edge and leaves it there (see _FindDialog.dock), so a second press
        # of Find/Replace has to dispose of the one already on screen rather than build a
        # second one over it.
        self.find_dialog: ui.dialog | None = None
        # The "still working on it" banner this view shows itself while its content is
        # being read and streamed in (see _show_loading).  Created by build_ui below, so
        # it is part of the very first paint of the window rather than something that has
        # to arrive over the socket afterwards.
        self._loading_row: ui.element | None = None
        self._loading_label: ui.label | None = None
        # Tasks this view starts and does not wait for.  asyncio keeps only a weak reference to a
        # running task, so one nobody holds can be collected before it finishes.
        self._background_tasks: set[asyncio.Task] = set()
        self.build_ui()
        register_view(master_gui, self)
        # Schedule the coroutine into the active event loop safely
        self._task = asyncio.create_task(self.process_data(the_data))
        # A bare create_task drops whatever the coroutine raises on the floor: the view is
        # left half-built and the app says nothing, which is a long way to debug from.  Every
        # failure in here shows up as "the view did not finish", so it is worth a line in the
        # log saying which one it was.
        self._task.add_done_callback(_report_view_failure)

    def _show_loading(self) -> None:
        """Put a spinner and a progress line at the top of this view's scroll area.

        A popped-out view opens as an empty window and stays that way for as long as it
        takes process_data to read its generated file and stream the whole of it in --
        seconds, on a large configuration, during which the window said nothing at all and
        looked like it had simply come up blank.  This is what it says instead, and
        _hide_loading takes it away the moment the content is all there.

        Built here rather than pushed over the socket later so that it is part of the
        window's first paint: it has to be on screen before the work that delays
        everything else, not after it.
        """
        if self._loading_row is not None or not hasattr(self, "scroll_area"):
            return
        with self.scroll_area:
            self._loading_row = ui.row().classes("w-full items-center gap-3 p-2")
            with self._loading_row:
                ui.spinner(size="1.5em", color="orange")
                self._loading_label = ui.label(
                    translate_string("Building the view.  Please stand by ..."),
                ).classes("text-orange-500 italic")

    def _set_loading_text(self, message: str) -> None:
        """Say how far along the streaming is, if the banner is still up."""
        if self._loading_label is not None:
            self._loading_label.set_text(message)

    def _hide_loading(self) -> None:
        """Take the progress banner down.  Safe to call when there isn't one."""
        row, self._loading_row, self._loading_label = self._loading_row, None, None
        if row is not None:
            with suppress_logged("Deleting the progress banner"):
                row.delete()

    def _mark_content_ready(self) -> None:
        """Marks this view's content as fully streamed in, under a fresh content token.

        The token is what lets the browser-side search index (and the results cache below)
        be trusted: it changes whenever the content does, so an index built against the
        previous content can never be mistaken for one built against this one.
        """
        self._content_generation += 1
        self._content_token = self._content_generation
        self._last_search = None
        # Every path through process_data ends here, which makes this the one place the
        # progress banner can be taken down without having to remember each of them.
        self._hide_loading()

    async def _enable_in_page_links(self) -> None:
        """Make the Map's own hyperlinks land on what they name.

        The directory at the top of the Map, the "Go to top" links and every Task name that
        points at its own entry are plain '<a href="#...">' links, which the browser follows
        by itself.  That works only while the browser knows where the target is -- and the
        Map arrives as pieces marked "content-visibility: auto", which is what lets it skip
        the layout of everything off screen (see split_for_streaming).  A piece it has
        skipped has never been laid out, so a link into one lands at that piece's ESTIMATED
        position rather than its real one, which on a large Map is thousands of lines out.

        So the click is taken over here: the piece holding the target is asked to lay itself
        out for real, and only then is the target scrolled to.  Exactly what a clicked report
        finding and a search result already do (mapjump.REVEAL_ANCESTORS_JS), now that an
        ordinary hyperlink needs it too.

        Inside the view's own slot, as _deliver_jump runs its jump: ui.run_javascript needs
        a client to send to, and it raises rather than guesses when it is called from a
        background task with no slot in context -- which the rest of this method's work
        then never happens inside.
        """
        with self.scroll_area:
            try:
                await self._wire_in_page_links()
            except (TimeoutError, RuntimeError):
                # The page went away, or never finished connecting, while the content was
                # still arriving.  The links then fall back to what the browser does with
                # them, which is right for everything it has already laid out.
                logger.debug("Map view: the in-page link handler was not installed.")

    async def _wire_in_page_links(self) -> None:
        """Install the click handler described by _enable_in_page_links."""
        await ui.run_javascript(
            assettext.render(
                "js/in_page_links.js",
                SCROLL_AREA_ID=str(self.scroll_area.id),
                REVEAL_ANCESTORS_JS=mapjump.REVEAL_ANCESTORS_JS,
                RESOLVE_TARGET_JS=mapjump.RESOLVE_TARGET_JS,
            ),
            timeout=SEARCH_JAVASCRIPT_TIMEOUT,
        )

    async def _deliver_jump(self) -> None:
        """Take this freshly built Map to the object a clicked report finding asked for.

        Runs once and then forgets the token: this is the delivery of one click, not a
        property of the view, and a later reload of the same page should not silently jump
        somewhere the user has since scrolled away from.

        Says so when the object turns out not to be there after all.  The rebuild that led
        here already went to the whole configuration at a detail level chosen for this
        object, so the remaining explanations are narrow -- the view limit cut the Map short
        before reaching it, or it is one of the things the Map has no line for (a variable
        the Map's own variable table does not list, for one) -- and either way the useful
        thing to say is that it is not there, not to guess which.
        """
        token, self.jump_to = self.jump_to, ""
        target = mapjump.Target.from_token(token) if token else None
        if target is None:
            return

        with self.scroll_area:
            try:
                landed = await ui.run_javascript(mapjump.jump_js(target.anchor), timeout=5)
            except (TimeoutError, RuntimeError):
                # The page went away, or never finished connecting, between the content
                # arriving and this asking it to scroll.  There is nobody left to tell.
                return
            if not landed:
                ui.notify(
                    f"{translate_string('Built the Map, but it has no line for')} {target.label}",
                    type="warning",
                    position="top",
                )

    def _build_scope_badge(self) -> None:
        """The toolbar line saying what this view was drawn for, and whether that is still
        what the app is showing.

        A Diagram is a SNAPSHOT.  Nothing rebuilds it when the user picks a different single
        Project, Profile, Task or Scene, so it goes on drawing the selection it was built
        for -- and its hotlinks go on pointing at those objects, which is fine until the user
        moves on and then reads the two views as though they agree.  Clicking one of those
        hotlinks then answers with a Map of the object clicked (see rebuild_map_for_jump),
        replacing the Map the user had just built for their new selection, which is a
        surprise precisely because nothing on screen said the Diagram was from another time.

        So it says so, in the one place the clicking happens.  Nothing is disabled and no
        behaviour changes: the hotlinks still work, and the Rebuild button is offered rather
        than done, because a Diagram of a large configuration is slow to draw and the user
        may well want the old one a moment longer.

        Both labels are created here whatever the state, and only their text and visibility
        change afterwards -- see refresh_scope_badges for why that distinction matters.
        """
        self.scope_label = ui.label("").classes("text-xs text-gray-500 italic ml-4")
        self.scope_stale_label = ui.label("").classes("text-xs text-orange-500 font-bold")

        async def rebuild() -> None:
            """Draw this view again for whatever is selected now.

            Through view_event, the same call the Diagram button makes, so the rebuild is
            the view the user would get by pressing it -- this is a shortcut to that button,
            not a second way of building a Diagram.
            """
            handlers = getattr(self.master_gui, "event_handlers", None)
            if handlers is None:
                ui.notify(translate_string("Press Diagram View to rebuild it."), type="info", position="top")
                return
            await handlers.view_event("diagram")

        self.scope_rebuild_button = (
            ui.button(translate_string("Rebuild"), on_click=rebuild).props("dense flat").classes("text-orange-500")
        )
        self.refresh_scope_badge()

    def refresh_scope_badge(self) -> None:
        """Put the current answer into the badge built above.

        Text and visibility only.  Called at build time and again whenever the selection
        changes, from a context that has no NiceGUI slot -- which is exactly why nothing here
        creates an element.
        """
        if self.scope_label is None or self.scope_stale_label is None or self.scope_rebuild_button is None:
            return
        drawn, changed = scope_badge_text(self.built_for, mapjump.current_scope(state=self.master_gui.state).phrase)
        self.scope_label.set_text(drawn)
        self.scope_stale_label.set_text(changed)
        self.scope_stale_label.set_visibility(bool(changed))
        self.scope_rebuild_button.set_visibility(bool(changed))

    def _build_toolbar(self, is_diagram: bool) -> None:
        """The toolbar above the text: Search, Clear, Find/Replace and Export (Map and Diagram), scrolling, wrap, and the Diagram's controls."""
        with ui.row().classes("w-full items-center gap-2 p-2 mb-2 shrink-0") as self.gui_toolbar:
            ui.label(f"{self.title}").classes("text-orange-500 font-bold mr-4")
            self.search_input = ui.input(placeholder=translate_string("Search...")).classes("w-48")
            search_button = ui.button(translate_string("Search"), on_click=self.search_event).classes("bg-blue-600")
            with search_button:
                ui.tooltip(
                    translate_string(
                        "The 'Search' button will search for and highlight every instance of the case-insensitive string entered in the search box, starting at the top of the data.\n\n"
                        "It will only show the first 200 instances of the search string.\n\n"
                        "Click on the line number to go to that line in the text view box.\n\n"
                        "The 'Clear' button will clear the search results.\n\n",
                    ),
                ).style("white-space: pre-wrap")
            ui.button(translate_string("Clear"), on_click=self.master_gui.event_handlers.clear_event).classes(
                "bg-blue-600",
            )
            # Structured search, alongside the text one rather than replacing it: the
            # two answer different questions (see find_event).  Offered on the Map and
            # the Diagram and nowhere else -- it answers with objects in the loaded
            # configuration, which is what those two views draw; the Misc view shows
            # reports, which have their own clickable rows already.
            if self.is_map or is_diagram:
                find_button = ui.button(translate_string("Find/Replace"), on_click=self.find_event).classes(
                    "bg-blue-600",
                )
                with find_button:
                    ui.tooltip(
                        translate_string(
                            "'Find/Replace' asks the loaded configuration a question rather than searching the "
                            "text on screen: every Task performing a given action, every Profile a given "
                            "trigger fires, everything that names a given app or Scene.\n\n"
                            "The boxes combine -- pick a trigger and an action to find the Profiles that "
                            "trigger that way and run a Task that does that.\n\n"
                            "Results come back as a list of objects; click one to be taken to it.\n\n",
                        ),
                    ).style("white-space: pre-wrap")
                # On the same two views as Find/Replace, and for the same reason: they draw
                # the configuration, which is what an export is of (see mapexport).
                create_export_menu(self)
            ui.separator().props("vertical")
            ui.button(translate_string("Top"), on_click=lambda: self.scroll("top")).classes("bg-blue-600")
            ui.button(translate_string("Bottom"), on_click=lambda: self.scroll("bottom")).classes("bg-blue-600")
            ui.button(translate_string("Toggle Wrap"), on_click=self.toggle_wrap).classes("bg-blue-600")
            if self.is_map:
                self.map_message_label = ui.label(self.master_gui.state.view_limit_msg).classes(
                    "text-orange-400 italic ml-4"
                )
            if is_diagram:
                ui.separator().props("vertical")
                # Held on the view, not left anonymous, so "Reset Options" can move it:
                # this pulldown lives on the Diagram view's own toolbar rather than in the
                # settings drawer, and a reset that changed the value without moving the
                # control would leave the two disagreeing on screen.
                self.profiles_per_line_select = (
                    ui.select(
                        options=[str(n) for n in range(11)],
                        value=str(self.master_gui.profiles_per_line),
                        label=translate_string("Profiles Per Line"),
                        on_change=self._profiles_per_line_selected,
                    )
                    .classes("w-40")
                    .props("dense")
                )
                create_diagram_tools(self)
                self.diagram_message_label = ui.label("").classes("text-orange-400 italic ml-4")
                self._build_scope_badge()

    def _build_scroll_area(self, is_popout: bool, is_diagram: bool, is_flow: bool) -> None:
        """The scrollable area the text is streamed into, wrapped or not and styled for the kind of view."""
        self.wrap_enabled = not (is_diagram or is_flow)
        self.wrap_classes = "whitespace-pre-wrap break-words" if self.wrap_enabled else "whitespace-pre"

        # min-h-0 lets this flex item shrink below its content's intrinsic size -- without it
        # a flex column's default min-height:auto would keep growing the scroll area (and the
        # page) to fit all the streamed-in content instead of scrolling internally.
        scroll_height_classes = "flex-1 min-h-0" if is_popout else "h-[70vh]"

        # Tailwind's text-sm utility (below) pairs a 14px font with a 20px line-height --
        # comfortable for prose, but visibly loose for a dense box-drawn diagram. Tighten it
        # for the Diagram view only; keep process_data()'s approx_px_per_line chunk-height
        # estimate in sync with this so scrolling doesn't jump around as chunks pop in.
        line_height_style = " line-height: 1.2;" if is_diagram or is_flow else ""

        # The Map view renders MapTasker.html, every color in which was picked against the
        # configured output background -- the same one frontmtr writes onto that file's
        # <body>. The app's own page background is set from the dark-mode toggle instead,
        # so the two disagreed: open the file and the output sits on Lavender, show the
        # same output here and it sat on white. Anything the output colors near-matches
        # (a TaskerNet description's white headings, say) then disappears. Use the
        # configured background here too, so the view shows what the file shows.
        # "!important" is needed, not decorative: the light-mode overrides injected by
        # inject_shared_head_styles() force "background-color: #ffffff !important" onto
        # every .q-scrollarea to keep macOS's system appearance from bleeding through, and
        # a plain inline style loses to that. An important declaration in the style
        # attribute is the one thing that outranks an important rule in a stylesheet, and
        # it applies to this one scroll area rather than weakening the override for the
        # drawers, cards and tab panels that rely on it.
        background_style = ""
        if self.title.startswith("Map"):
            background = css_color(self.master_gui.state.colors_to_use.get("background_color", ""))
            if background:
                background_style = f" background-color: {background} !important;"

        self.scroll_area = (
            ui.scroll_area()
            # min-w-0 keeps this a flex child that can't be stretched wider than its container by
            # long unbreakable content; without it the default flex min-width:auto lets the box
            # (and the whole page) grow past the viewport once the full content has streamed in.
            .classes(
                f"mt-textview w-full max-w-full min-w-0 block {scroll_height_classes} "
                f"border-2 border-gray-600 p-4 text-sm {self.wrap_classes}",
            )
            .style(
                # The font the output was generated with, which process_data() then
                # reconciles against the file it actually reads. Deliberately not
                # master_gui.font -- see the note there on why that can be stale.
                f"width: 100%; max-width: 100%; "
                f"font-family: '{self.master_gui.state.program_arguments.font}', monospace;"
                f"{line_height_style}{background_style}",
            )
        )

    def build_ui(self) -> None:
        """Builds the UI layout for the various text views, including toolbar and scrollable display area."""

        # A popped-out view (its own browser window/tab, see rungui.py's "/popout/{view_type}"
        # page) has the whole viewport to itself, so its scroll area flex-fills the remaining
        # height after the toolbar instead of the fixed 70vh used when embedded alongside the
        # rest of the main window's layout.
        is_popout = self.external_container is not None

        if self.external_container is not None:
            container_context = self.external_container
            container_context.classes("w-full h-screen flex flex-col p-0 m-0 gap-0")
        elif hasattr(self.master_gui, "content_container") and self.master_gui.content_container:
            self.master_gui.content_container.clear()
            container_context = self.master_gui.content_container
        else:
            container_context = ui.column()

        # "Diagram" view intentionally starts unwrapped so ASCII-art connectors stay aligned.
        is_diagram = self.title.startswith("Diagram")
        # The Task Flow view is a drawing too -- one Task's control flow, box-drawn by
        # taskflow.py -- so it inherits the Diagram's unwrapped, tightly-led layout without
        # inheriting the Diagram's toolbar, none of which (Profiles Per Line, folding, the
        # call chain) means anything for a single Task.
        is_flow = self.title.startswith("Task Flow")

        # Set the main container to a vertical layout with full width and height
        with container_context:
            self._build_toolbar(is_diagram)
            self._build_scroll_area(is_popout, is_diagram, is_flow)

            # The window is about to be handed to the browser with nothing in it yet.  Say
            # what it is waiting for, right here in the first paint -- see _show_loading.
            self._show_loading()

    async def process_data(self, the_data: dict | list | str) -> None:
        """Converts data to HTML chunks, preventing single-packet WebSocket buffer overruns.

        All ui.html() calls below pass sanitize=False: the content is this program's own
        MapTasker.html/diagram output, not untrusted input. NiceGUI's default client-side
        sanitizer (the browser's Sanitizer API) strips "id", "class", and "data-*" attributes,
        which silently breaks in-page #fragment hyperlinks (e.g. the "Task ... has too many
        actions" links) and the Diagram view's click-to-highlight connectors -- their <a href>
        source tags survive sanitizing, but the <a id="..."> targets and .connector/
        data-connector-id spans they depend on do not.
        """
        is_diagram = self.title.startswith("Diagram")
        is_flow = self.title.startswith("Task Flow")
        # Starting point, used as-is by the Misc and Task Flow views (neither of which has a
        # generated file behind it).  The file-backed views replace this below with the font
        # their file actually carries.
        html_style = (
            f"width: 100%; max-width: 100%; font-family: '{self.master_gui.state.program_arguments.font}', monospace;"
        )
        if not (is_diagram or is_flow):
            html_style += " word-break: break-word;"

        if self.title.startswith("Map"):
            file_to_read = output_path("MapTasker.html", state=self.master_gui.state)
        elif is_diagram:
            file_to_read = output_path(DIAGRAM_FILE, state=self.master_gui.state)
        elif self.title.startswith("Misc") or is_flow:
            self._show_report(the_data, html_style, is_flow)
            return

        try:
            with open(file_to_read, encoding="utf-8") as f:
                final_html = f.read()
                # The diagram file is plain text (no HTML markup), and its line numbers must line
                # up 1:1 with PrimeItems.diagram_connectors (recorded when the diagram was built) so
                # clicking a connector highlights the right one -- so skip the HTML-specific/blank-line
                # collapsing optimizations here; they aren't meaningful for plain text anyway.
                if not is_diagram:
                    final_html = optimize_map_html(final_html)

            html_style = self._style_for_file_font(final_html, is_diagram)
            chunks, diagram_model, connectors_by_line = self._chunk_view_html(final_html, is_diagram)
            await self._stream_chunks(chunks, html_style, is_diagram)
            await self._finish_view(diagram_model, connectors_by_line)

        except FileNotFoundError:
            pass
        else:
            return

        # Apply the fallback generation if the file does not exist
        self._process_fallback_data(the_data)
        self._mark_content_ready()

    def _show_report(self, the_data: dict | list | str, html_style: str, is_flow: bool) -> None:
        """Show the Misc or Task Flow view: a report that has no generated file behind it."""
        # The Task Flow view is this renderer with the Diagram's habits: rows mapjump has
        # already made clickable, but a drawing rather than prose, so nothing may wrap
        # (see build_ui).  Its content comes off PrimeItems rather than through the_data
        # because a popped-out window builds itself from a URL and is handed nothing --
        # the same reason the Diagram popout re-reads its own file (rungui.popout_view).
        with self.scroll_area:
            content_str = (
                mapjump.html_report(self.master_gui.state.taskflow_rows)
                if is_flow
                else ("\n".join(str(line) for line in the_data) if isinstance(the_data, list) else str(the_data))
            )
            ui.html(f"<pre style='{html_style}'>{content_str}</pre>", sanitize=False)
        # A report rendered by mapjump.html_report marks the rows that point at
        # something in the Map (see its FINDING_CLASS).  Tested for rather than assumed,
        # since this branch also shows reports that carry no such rows at all -- the
        # file comparison, and any report from a build before those rows existed.
        if mapjump.FINDING_CLASS in content_str:
            enable_finding_clicks(self)
        self._mark_content_ready()

    def _style_for_file_font(self, final_html: str, is_diagram: bool) -> str:
        """The style the view's chunks are given, in the font the file being shown was built with.

        Also brings the scroll area into step, since build_ui() styled it before the file had
        been read.

        Args:
            final_html: The contents of the Map or Diagram file.
            is_diagram: Whether this is the Diagram view, which is plain text and does not wrap.

        Returns:
            The CSS for each chunk, before its own content-visibility rules are added.
        """
        # Render in whatever font the file we just read was actually generated with,
        # rather than overriding it with the GUI's current selection.
        #
        # This used to rewrite the file's font-family to self.master_gui.font. That is
        # only right while the two agree -- and the popout page resolves its gui through
        # PrimeItems.mygui, which is simply the most recently constructed MyGui, so a
        # main window that got rebuilt (a reload, a reconnect, a second window) leaves a
        # .font behind that never generated anything. Rewriting to it then replaced a
        # correct font with a stale one, which is why the saved MapTasker.html could show
        # the selected font while the Map view of that very same file did not.
        #
        # Reading the font back out of the file removes the disagreement outright: the
        # view can only ever show what the output it is displaying was built with. The
        # Diagram file is plain text with no CSS of its own, hence the fallback to the
        # font that generated this run.
        extracted_font = self.extract_first_font_name(final_html)
        view_font = (
            extracted_font if extracted_font != "Font name not found" else self.master_gui.state.program_arguments.font
        )
        html_style = f"width: 100%; max-width: 100%; font-family: '{view_font}', monospace;"
        if not is_diagram:
            html_style += " word-break: break-word;"
        # build_ui() styled the scroll area before this file had been read, so bring it
        # into step now that the font it is actually holding is known.
        self.scroll_area.style(f"font-family: '{view_font}', monospace;")
        return html_style

    def _chunk_view_html(self, final_html: str, is_diagram: bool) -> tuple[list[tuple[str, int]], dict, dict | None]:
        """Cut the file's text into the pieces it is streamed to the browser in.

        Args:
            final_html: The contents of the Map or Diagram file.
            is_diagram: Whether this is the Diagram view.

        Returns:
            The chunks, each as (its content, how many lines it holds); the Diagram's
            interactive model, {} for the other views; and the Diagram's connectors by line
            number, None for the other views.
        """
        # Slice the giant HTML text by lines and push them in digestible blocks
        html_lines = final_html.splitlines()
        if html_lines and html_lines[0].strip() == '<span class="normtab"></span><!doctype html>':
            del html_lines[0]  # Remove the first line if it matches the unwanted header

        connectors_by_line = diagram_connectors_by_line(state=self.master_gui.state) if is_diagram else None
        # What makes the Diagram clickable rather than merely drawn -- see diagintr.
        # Empty for a Diagram file left on disk by an older run, in which case the
        # lines below are wrapped exactly as they always were.
        diagram_model = diagintr.model(state=self.master_gui.state) if is_diagram else {}
        nodes_by_line = diagintr.nodes_by_line(diagram_model)
        folds_by_line = diagintr.folds_by_line(diagram_model)

        # The Diagram is a drawing made of lines, and every one of them has to keep its
        # own number for a connector click to land on it, so it is still cut into pieces
        # of 150 lines.  The Map is not: by the time it reaches here the newlines
        # between its tags have been optimized away, so cutting it by lines left the
        # whole Map in one piece however big it was (see split_for_streaming).
        if is_diagram:
            chunks = [
                (
                    "".join(
                        wrap_diagram_line(
                            start + offset,
                            line,
                            connectors_by_line or {},
                            nodes_by_line,
                            folds_by_line,
                        )
                        for offset, line in enumerate(html_lines[start : start + 150])
                    ),
                    len(html_lines[start : start + 150]),
                )
                for start in range(0, len(html_lines), 150)
            ]
        else:
            # Joined back exactly as the chunks used to be written, so that what the
            # browser is given is the same text it was given before -- only cut up
            # differently.  How tall a piece is, near enough to reserve scrollbar space
            # for: every line of the Map ends in a <br>, so counting those counts lines.
            chunks = [(piece, piece.count("<br>") or 1) for piece in split_for_streaming("\n".join(html_lines))]
        return chunks, diagram_model, connectors_by_line

    async def _stream_chunks(self, chunks: list[tuple[str, int]], html_style: str, is_diagram: bool) -> None:
        """Push the chunks into the scroll area, a few at a time, with a progress percentage.

        Args:
            chunks: What _chunk_view_html made: each chunk's content and how many lines it holds.
            html_style: The style every chunk is given, before its own content-visibility rules.
            is_diagram: Whether this is the Diagram view.
        """
        # The Diagram view's click-to-highlight feature wraps every connector character in its
        # own <span> (tens of thousands of them on a large diagram, since a run only merges
        # with its neighbor when they're on the very same line -- see
        # compute_diagram_connector_groups() in diagram.py). That many extra inline elements
        # makes the browser's layout/paint work on scroll noticeably heavier, so the Diagram
        # view is chunked much more finely than other views. Every view's chunks are marked
        # content-visibility: auto though, which lets the browser skip layout and paint
        # entirely for chunks that are scrolled out of view instead of doing that work for the
        # whole document on every frame -- on a very large Map view that's the difference
        # between laying out the whole document up front and only what's on screen.
        # contain-intrinsic-size reserves roughly the right amount of scrollbar space for an
        # unrendered chunk so scrolling doesn't jump around as chunks pop in and out; it
        # doesn't need to be exact, just close. For the Map/Misc views this estimate is fuzzier
        # than for Diagram's plain monospace text, since long lines there can word-wrap
        # (word-break: break-word, set above) into more than one visual line -- a minor
        # scrollbar jitter, not a correctness issue.
        # text-sm is 14px; at the Diagram view's tightened line-height (1.2, set in build_ui)
        # that's ~17px per line instead of Tailwind's default ~20px.
        approx_px_per_line = 17 if is_diagram else 20

        delivered = 0
        total_size = sum(len(content) for content, _ in chunks) or 1
        with self.scroll_area:
            for number, (chunk_content, chunk_lines) in enumerate(chunks):
                chunk_height = chunk_lines * approx_px_per_line
                chunk_style = html_style + f" content-visibility: auto; contain-intrinsic-size: auto {chunk_height}px;"
                chunk = ui.html(chunk_content, sanitize=False).classes("w-full block max-w-full").style(chunk_style)
                # How many lines this chunk holds, so that zooming can re-reserve the
                # right amount of scrollbar space for it while it is still unrendered --
                # the height above was worked out against the unzoomed line height.
                if is_diagram:
                    chunk.props(f"data-lines={chunk_lines}")
                # How far along, on the banner _show_loading put up.  Content arrives
                # top-down so there is something to look at almost at once, but on a
                # large configuration it goes on arriving for a while after that, and
                # a percentage is the difference between "still working" and "stuck".
                delivered += len(chunk_content)
                self._set_loading_text(
                    f"{translate_string('Building the view')} ... {min(100, round(100 * delivered / total_size))}%",
                )
                # Yields the loop to keep the WebSocket alive.  Not after every piece:
                # the Map is now cut into far more of them, and a hundredth of a second
                # each would put a wait of its own in front of the user.
                if number % 4 == 0:
                    await asyncio.sleep(0.01)

    async def _finish_view(self, diagram_model: dict, connectors_by_line: dict | None) -> None:
        """Everything that happens once the last chunk is on the page: wiring, hints, and the jump.

        Args:
            diagram_model: The Diagram's interactive model, {} for the other views.
            connectors_by_line: The Diagram's connectors by line number, None for the other views.
        """
        if connectors_by_line:
            self._enable_connector_highlighting(diagintr.connector_tasks(diagram_model))
            if hasattr(self, "diagram_message_label"):
                self.diagram_message_label.set_text(translate_string("Click on connector to highlight"))
        if diagram_model.get("nodes"):
            self._enable_diagram_interaction(diagram_model)
            # Replaces the connector hint rather than joining it: both are about
            # clicking the diagram, and this one covers the connectors too.
            if hasattr(self, "diagram_message_label"):
                self.diagram_message_label.set_text(
                    translate_string("Click a name for its Map entry \u00b7 shift-click a Task for its call chain"),
                )
        # A diagram cut short at the view limit (diagclean.check_limit) says so here, in place
        # of the connector hint: that the diagram stops early is the more important of the
        # two things to tell the user, and this is the Map view's view_limit_msg field by
        # another name (see NiceGuiTextView.build_ui).
        if self.master_gui.state.diagram_limit_msg and hasattr(self, "diagram_message_label"):
            self.diagram_message_label.set_text(self.master_gui.state.diagram_limit_msg)
        await self._enable_in_page_links()
        self._mark_content_ready()
        # Everything is on the page now, so a report finding that asked for this Map can
        # finally be taken to.  Last, deliberately: the anchor it wants may be in the
        # chunk that only just arrived.
        await self._deliver_jump()

    def _enable_diagram_interaction(self, diagram_model: dict) -> None:
        """Wire up the Diagram view's clickable nodes, folds, chains and zoom.

        The DOM half of it.  The Python half is one subscription -- the same "mt_jump" a
        clicked report finding raises -- so that a node click and a report row are answered
        by the very same code (see go_to_target): the Diagram is one more thing that points
        at the Map, not a second way of getting there.

        Needs an active NiceGUI slot for both, and this runs from process_data's background
        task where the slot stack is empty, hence the scroll area re-entry -- the same
        reason, spelled out at greater length, as in _enable_connector_highlighting.
        """
        with self.scroll_area:
            register_finding_clicks(self.master_gui)
            status_id = f"c{self.diagram_state_label.id}" if hasattr(self, "diagram_state_label") else ""
            ui.run_javascript(diagintr.interaction_js(f"c{self.scroll_area.id}", status_id, diagram_model))

    def diagram_command(self, name: str, argument: float | None = None) -> None:
        """Carry one of the Diagram toolbar's buttons to the view it belongs to."""
        with self.scroll_area:
            ui.run_javascript(diagintr.command_js(f"c{self.scroll_area.id}", name, argument))

    def _enable_connector_highlighting(self, connector_tasks: dict[str, list[str]] | None = None) -> None:
        """Wires up click-to-highlight for Diagram view connector spans.

        Clicking a connector span highlights every span sharing its data-connector-id and clears
        any previously-highlighted connector; clicking empty space clears the highlight too. If
        either end of the highlighted connector -- its topmost or bottommost cell, since a
        connector's spans are emitted top-to-bottom in document order -- is scrolled out of the
        visible area, a floating "Jump to Start"/"Jump to End" button appears so the user can
        bring it into view without hunting for it manually; the button hides itself again once
        the user scrolls that end into view (or clicks away). A jump scrolls vertically to that
        end's line and horizontally back to column 1, so the line is read from its beginning
        rather than from wherever the connector happens to sit across a wide diagram -- unless
        the Task that end belongs to is drawn out of view to the right, in which case it
        scrolls sideways as far as that Task needs and no further.  `connector_tasks` (see
        diagintr.connector_tasks) says which Tasks each connector joins, and so which get a
        red rectangle drawn round them when it is clicked; without it a jump only ever goes
        to the line and nothing is boxed.
        """
        # ui.run_javascript() needs an active NiceGUI "slot" to know which client to target.
        # This runs from a background asyncio task (self._task), after the `with self.scroll_area:`
        # block used to stream in the chunks has already closed, so the slot stack is empty here --
        # calling it unguarded raises RuntimeError (silently, since self._task is fire-and-forget)
        # and the click handler never reaches the browser. Re-entering the scroll_area as a context
        # manager restores the slot so the script actually gets sent.
        with self.scroll_area:
            ui.run_javascript(
                assettext.render(
                    "js/connector_highlighting.js",
                    SCROLL_AREA_ID=str(self.scroll_area.id),
                    CONNECTOR_TASKS=json.dumps(connector_tasks or {}),
                    REVEAL_ANCESTORS_JS=mapjump.REVEAL_ANCESTORS_JS,
                )
            )

    async def export_event(self, what: str, fmt: str) -> None:
        """Save the Map or the Diagram as Markdown, JSON or PDF, and say where it went.

        Run off the event loop: a PDF of a large Map takes a moment, most of it spent the
        first time on looking through the system's fonts for one to embed (see
        mapfonts.embeddable_font), and the window should not stop answering meanwhile.
        """
        try:
            path = await run.io_bound(mapexport.export_view, what, fmt, state=self.master_gui.state)
        except mapexport.ExportError as error:
            ui.notify(str(error), type="warning", position="top")
            return
        except OSError as error:
            ui.notify(f"{translate_string('The export could not be saved:')} {error}", type="negative", position="top")
            return
        # None is not a path: nicegui answers it when the wait is cancelled or the app is
        # stopping (see nicegui.run._run).  The file is written either way; what is gone is the
        # page that would have been told where.
        if path is None:
            return
        ui.notify(f"{translate_string('Exported to')} {path}", type="positive", position="top")

    def extract_first_font_name(self, text: str) -> str:
        """
        Scans the given text to identify and return the font name
        following the very first 'font-family:' rule declaration.
        """
        # Regex Breakdown:
        # font-family\s*:\s* -> Matches 'font-family', optional spaces, a colon, and optional spaces
        # ([^,;{}]+)         -> Capture Group 1: the first family in the list, i.e. everything
        #                       up to the comma that starts the fallback stack, or to the end
        #                       of the declaration when there is no fallback
        #
        # The comma has to end the capture rather than be excluded from it.  Every
        # font-family MapTasker writes carries a fallback -- addcss.py emits
        # "font-family:<font>, monospace;" and the view styles below build the same shape --
        # so a pattern that had to reach a ';' or '}' without crossing a comma matched none
        # of them.  This returned "Font name not found" for all real output, and the caller
        # fell back to program_arguments.font every single time: exactly the stale-font
        # behaviour that reading the font back out of the file is meant to avoid.
        pattern = re.compile(r"font-family\s*:\s*([^,;{}]+)")

        match = pattern.search(text)

        if match:
            # Return the captured font name, stripping off any outer quotes or accidental whitespace
            return match.group(1).strip().strip("'\"")

        return "Font name not found"

    def _process_fallback_data(self, the_data: dict | list | str) -> None:
        """Fallback logic to assemble HTML content strings when the source file is missing."""
        # --- 2. FALLBACK DICTIONARY PROCESSING (Legacy Map View) ---
        # --- 3. FALLBACK LIST DATA PROCESSING (Other Views) ---
        # A report arrives as one string; its lines are what the fallback lays out.
        lines = the_data.splitlines() if isinstance(the_data, str) else the_data
        html_builder = (
            fallback_map_html(cast("dict", the_data)) if self.is_map else fallback_lines_html(cast("list", lines))
        )

        # --- 4. COMPRESS MULTIPLE BLANK LINES FOR FALLBACK DATA ---
        # Into the scroll area, as every other path puts the view's content.  This runs from
        # process_data's background task, where no slot is in context, hence the re-entry.
        with self.scroll_area:
            ui.html(compress_blank_lines("".join(html_builder)), sanitize=False)

    def scroll(self, direction: str) -> None:
        """Manages the scroll position of the view's content area based on the specified direction ('top' or 'bottom').

        Also resets horizontal scroll back to column 1, since the view may have been scrolled
        sideways (e.g. via the search feature or a wide diagram) before Top/Bottom is clicked.
        """
        # Reset horizontal scroll back to the leftmost column regardless of direction.
        self.scroll_area.scroll_to(percent=0.0, axis="horizontal")
        if direction == "top":
            # Native NiceGUI scroll to top (0% progress)
            self.scroll_area.scroll_to(percent=0.0)
        else:
            self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        """Scroll the view all the way down, with the last line actually on screen.

        scroll_to(percent=1.0) hands Quasar a percentage of the scroll size it currently knows
        about -- and while the chunks process_data() streamed in are still being skipped by
        "content-visibility: auto", that size is the sum of their *estimated* heights
        (contain-intrinsic-size), not their real ones. The estimate runs short on the last chunk,
        so "100%" stopped a line or so above the true end of the content.

        Setting scrollTop past the end instead lets the browser clamp it to the real maximum,
        and doing that again over the next few frames picks up the correction as the chunks
        being scrolled into view get laid out for real and the scroll height grows.
        """
        ui.run_javascript(assettext.render("js/scroll_to_bottom.js", SCROLL_AREA_ID=str(self.scroll_area.id)))

    def toggle_wrap(self) -> None:
        """Toggles word-wrap on/off for this view's content, replacing the exact prior classes."""
        self.wrap_enabled = not self.wrap_enabled
        new_classes = "whitespace-pre-wrap break-words" if self.wrap_enabled else "whitespace-pre"
        self.scroll_area.classes(remove=self.wrap_classes, add=new_classes)
        self.wrap_classes = new_classes
        ui.notify(f"Word wrap {'enabled' if self.wrap_enabled else 'disabled'} for {self.title}.", type="info")

    def _profiles_per_line_selected(self, event: ValueChangeEventArguments | int | str) -> None:
        """Fires when the Diagram view's 'Profiles Per Line' pulldown selection changes."""
        new_value = int(str(getattr(event, "value", event)))
        if new_value != self.master_gui.profiles_per_line:
            task = asyncio.create_task(self.master_gui.event_handlers.profiles_per_line_event(new_value))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
            task.add_done_callback(_report_view_failure)

    def reload_diagram(self) -> None:
        """Clears and re-streams the Diagram view's content in place after it has been
        regenerated (e.g. after the 'Profiles Per Line' pulldown changes the diagram's layout).
        """
        # The content this view's cached search index and results were built against is about
        # to be thrown away; process_data() issues a new token once the replacement is fully
        # streamed in. Until then nothing about the old content may be reused.
        self._content_token = 0
        self._last_search = None
        self.scroll_area.clear()
        # clear() took the previous banner's element with it, so forget the handle before
        # asking for a fresh one -- the re-stream is another wait, and says so too.
        self._loading_row = self._loading_label = None
        self._show_loading()
        self._task = asyncio.create_task(self.process_data([]))
