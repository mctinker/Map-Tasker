"""The Map, Diagram, Misc and Tree views: showing them, clearing them, and jumping the Map to an object."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from nicegui import context, run, ui

from maptasker.src.analysis.taskflow import (
    analyze_task_flow,
    flowchart,
    write_flowchart,
)
from maptasker.src.core import assettext, mapjump
from maptasker.src.core.maputil2 import (
    suppress_logged,
    translate_string,
)
from maptasker.src.core.mtexcept import MapTaskerError
from maptasker.src.core.outdir import output_path
from maptasker.src.core.primitem import (
    MAP_OUTPUT_ATTRIBUTES,
    clear_error,
    initial_found_named_items,
    reset_attributes,
)
from maptasker.src.core.runcfg import current_config
from maptasker.src.core.sysconst import (
    DIAGRAM_FILE,
    POPOUT_WINDOW_PREFIX,
    VIEW_LIMIT_DEFAULT,
    logger,
)
from maptasker.src.gui.guistate import SELECTION_KEYS, capture_gui_state, held_overrides
from maptasker.src.gui.guiwins_nav import forget_views, live_views
from maptasker.src.gui.guiwins_textview import NiceGuiTextView
from maptasker.src.gui.guiwins_views import NiceGuiTreeView
from maptasker.src.gui.userintr_group import HandlerGroup
from maptasker.src.mapgen.bildhtml import build_html
from maptasker.src.mapgen.frontmtr import output_the_front_matter
from maptasker.src.mapgen.outline import outline_the_configuration

if TYPE_CHECKING:
    from maptasker.src.gui.userintr import MyGui


def popout_window_name(path: str, new_window: bool = False) -> str:
    """What the browser window holding this view is called.

    Its own function, and not private, because two places have to agree on it: this, which
    opens the window under the name, and the Diagram, which goes looking for the Map's
    window by name so it can raise it when a clicked object is answered by the Map already
    on screen (see diagintr).  A Diagram searching for a name nothing was opened under
    would quietly never raise anything, which is the kind of disagreement that shows up as
    a feature simply not working.

    The query string is deliberately NOT part of the name.  The Map's path carries
    "?goto=...&scope=..." (see view_event), and a name built from the whole path therefore
    changed with every finding clicked and every Project shown -- so each one opened a
    window of its own and only re-clicking the very same item reused anything, which is
    exactly what "Open View In New Window" being off is supposed to prevent.  The name
    identifies the VIEW; what that view is currently showing belongs in the URL alone.

    With "Open View In New Window" on, a unique suffix is appended: a name nothing has
    claimed yet behaves exactly like "_blank", which is what makes every request a fresh
    window.  The stable part stays at the front so the name is still recognisably this
    view's.
    """
    view_name = path.rsplit("/", 1)[-1].split("?", 1)[0]
    stable_name = f"{POPOUT_WINDOW_PREFIX}{view_name}"
    return f"{stable_name}_{time.time_ns()}" if new_window else stable_name


# How the "still working" banner sits on the page: pinned to the top of the window,
# centered, and above everything else, so it is in the same place whatever the user has
# scrolled to and whichever tab of the settings they are on.
BUSY_BANNER_STYLE = (
    "position: fixed; top: 0.75rem; left: 50%; transform: translateX(-50%); z-index: 9999; "
    "padding: 0.5rem 1rem; border-radius: 0.375rem; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.4); "
    "background-color: #1f2937; color: #fb923c;"
)


def _busy_banner(message: str) -> ui.element | None:
    """A spinner and a message that stay on screen for the whole of a long build.

    ui.notify() puts up a toast that takes itself down again after a few seconds, which is
    the wrong shape for work that runs longer than that: the view was announced, the toast
    expired, and the rest of the wait looked like the button had simply done nothing.

    Deliberately an ordinary element rather than ui.notification: a notification is owned
    by Quasar's Notify plugin and is taken down by asking that plugin to do it, which this
    app has no reliable way to make happen.  An element of our own comes down when we
    delete it.

    Returns None when there is no browser window to draw it in (a build started from
    somewhere other than a click in the GUI), which _clear_busy_banner accepts.
    """
    try:
        layout = context.client.layout
    except RuntimeError:
        # No client context -- nobody to tell.  The build itself is unaffected.
        return None
    with layout:
        banner = ui.element("div").classes("flex items-center gap-3").style(BUSY_BANNER_STYLE)
        with banner:
            ui.spinner(size="1.5em", color="orange")
            ui.label(message).classes("italic")
    return banner


def _clear_busy_banner(banner: ui.element | None) -> None:
    """Take down a _busy_banner, whether or not its window is still there."""
    if banner is not None:
        with suppress_logged("Deleting the busy banner"):
            banner.delete()


def _open_popout_window(path: str, new_window: bool = False) -> None:
    """Opens a Map/Diagram popout window and remembers it in the browser so 'Close Tabs On Exit'
    (see get_rid_of_windows_and_exit in guiwins.py) can close it later -- window.open()'s return
    value is otherwise discarded and there'd be no handle left to close it with.
    The actual data display is done in rungui.py with a call to NiceGuiTextView() to display the data
    in a new window.  This function just opens the new window and remembers it in the browser.

    Each view gets a stable window name so a second Map/Diagram request re-navigates -- and
    therefore reloads -- the tab that view already has open, rather than spawning another one.
    That is what makes a regenerated view (say, after the font was changed) actually replace
    what the user is looking at: with '_blank', the browser suppresses the new popup whenever
    it decides this doesn't count as a user gesture -- and it often doesn't, since this runs
    from a server-pushed script after the view has been built, not inline in the click -- which
    would silently leave the previous, stale tab on screen as the only Map view in sight.

    `new_window` (the "Open View In New Window" option) trades that reliability for being able
    to compare views side by side: a name nothing has claimed yet behaves exactly like '_blank',
    so every request is a fresh popup the browser is free to suppress. Each popout reads the
    generated file once, on load, so the windows left open do keep showing what they were built
    with rather than all changing together.
    """
    # See popout_window_name for what the name is and why it is shaped that way.
    window_name = popout_window_name(path, new_window)
    # What it does, and why the handle is kept in two places, is in mapjump.open_popout_js.
    ui.run_javascript(mapjump.open_popout_js(path, window_name))


class ViewEventHandlers(HandlerGroup):
    """The Map, Diagram, Misc and Tree views: showing them, clearing them, and jumping the Map to an object."""

    # ==========================================
    # 2. Display View: Map, Diagram, Misc or Tree
    # ==========================================
    async def view_event(
        self,
        view_type: str,
        goto: str = "",
        overrides: dict[str, Any] | None = None,
    ) -> None:
        """Triggered when Map, Diagram, or Tree buttons are clicked.

        Uses run.io_bound to run blocking file generations in a background thread,
        allowing thread-safe access to internal PrimeItems variables.

        'goto' is a mapjump token the finished Map view scrolls to and highlights once it
        has streamed in -- how a clicked report finding is delivered to a Map that had to
        be built for it (see rebuild_map_for_jump).

        'overrides' are settings this one build needs that the GUI does not currently hold
        -- a detail level high enough to list the actions being jumped to, say.  Applied
        AFTER capture_gui_state, since that overwrites program_arguments wholesale from the
        GUI, and left to the caller to put back: the GUI's own widgets are untouched, so
        nothing the user can see changes.

        Applying them here is not on its own enough to make them STAY applied -- capture_gui_state
        runs again, off NiceGUI's outbox loop, for messages this build itself sends.  A caller
        passing overrides must hold them across this call with guistate.held_overrides.
        """
        # max_limit = 9999999
        window_title = f"{view_type.capitalize()} View"

        # A Map being built ahead of time (see userintr_prebuild) is using the run state this
        # view is about to rewrite -- the output lines, the totals, the settings -- so this waits
        # for it, before it touches any of them.  What it waits for is most of what pressing Map
        # would have done, and the Map is there when it is over.
        if self.hub.prebuild.prebuild_running():
            waiting = _busy_banner(
                f"{translate_string('Building the')} {window_title}.  {translate_string('Please stand by ...')}",
            )
            try:
                await self.hub.prebuild.wait_for_prebuild()
            finally:
                _clear_busy_banner(waiting)

        self.gui.event = True  # Set the event flag to True
        logger.info(f"GUI: Switching to {window_title}")

        self.get_ready_to_build(overrides)

        # Counted so that nothing is built ahead of time while this is built for real.
        with self.hub.prebuild.view_in_progress():
            await self._show_the_view(view_type, window_title, goto)

    async def _show_the_view(self, view_type: str, window_title: str, goto: str) -> None:
        """Build the view asked for and open it."""
        # Map view
        if view_type == "map":
            await self._view_map(window_title, goto)

        # Setup diagram view.
        elif view_type in ("diagram", "misc"):
            if view_type == "diagram":
                await self._view_diagram()
            else:
                self._view_misc()

        elif view_type == "tree":
            self._view_tree()
        else:
            self._view_invalid()

    def get_ready_to_build(self, overrides: dict[str, Any] | None) -> None:
        """Put the run state in the condition every Map, Diagram and Tree build starts from.

        What view_event does before it builds, and what a Map built ahead of time does too --
        which is why it is one thing: the settings a build takes are part of what the Map is
        remembered by (see mapcache), so a Map built ahead of time is only found by a press if the
        two took them the same way.  See view_event for 'overrides'.
        """
        gui = self.gui
        self.state.view_limit = gui.view_limit if hasattr(gui, "view_limit") else VIEW_LIMIT_DEFAULT

        # Plug all of our settings back into PrimeItems.program_arguments
        capture_gui_state(gui, {}, state=self.state)
        if overrides:
            self.state.program_arguments.update(overrides)

        # Start this view generation with a clean slate: found_named_items only ever
        # gets set to True (projects.py/profiles.py/tasks.py/scenes.py, once
        # process_projects_and_their_profiles/its callees find the single Project/
        # Profile/Task/Scene being searched for) -- it's never reset back afterward,
        # since it's meant to stop searching further *within a single run*, not carry
        # over between separate ones. Left stale from an earlier view, a second Map/
        # Diagram/Tree for the same single item (e.g. right after editing it and
        # clicking Ok) would look like it was "already found" and get skipped
        # entirely, even though this run never actually found it yet.
        # Built from primitem.SINGLE_ITEM_SELECTORS rather than written out here, so a
        # newly added single item can't be left out of the reset.
        self.state.found_named_items = initial_found_named_items()

        # Same reasoning for the directory and the running totals -- both accumulate
        # across a single run and are never emptied at the end of one:
        #
        #  - directory_items: add_directory_item only records a name it hasn't seen, and
        #    sets directory_items["current_item"] (which is what makes lineout emit the
        #    "<a id=...>" anchor the directory hyperlink jumps to) *only* on that first
        #    sighting.  Left populated from an earlier view, every name looks
        #    already-seen, so the second view's hyperlinks point at anchors that were
        #    never written -- clicking a directory entry then goes nowhere.
        #  - grand_totals: straight "+=" accumulation, so a second view reports doubled
        #    Project/Profile/Task/Scene counts.
        #
        # Single Project/Profile/Task views happened to escape the directory half of
        # this because they route through lineout.refresh_our_output, which rebuilds
        # both dicts mid-run; a single Scene never calls it, which is how this surfaced.
        #  - emitted_anchors: the same story as the directory.  Left populated from an
        #    earlier view, every object looks already-anchored, so the second view carries
        #    no mapjump anchors at all and a clicked finding has nothing to land on.
        #  - task_action_warnings: the "too many actions" list, accumulated the same way.
        reset_attributes(*MAP_OUTPUT_ATTRIBUTES)

    async def _view_map(self, window_title: str, goto: str) -> None:
        """Build the Map and open it in a window of its own."""
        gui = self.gui
        if not self.state.backup_loaded:
            gui.display_message_box(
                translate_string("No XML data loaded! Please select a valid XML file first."),
                "Orange",
            )
            return

        # Say so before the work starts, and keep saying it right through it.  A large
        # configuration takes real time to build below, and the one-second toast that
        # used to announce it was gone for almost all of that wait -- leaving a window
        # that looked like the button had done nothing.  This one carries a spinner and
        # no timeout, and comes down in the "finally" below whichever way this ends.
        building = _busy_banner(
            f"{translate_string('Building the')} {window_title}.  {translate_string('Please stand by ...')}",
        )
        try:
            # 1. Clear out stale error codes before starting execution paths
            clear_error()

            # Refresh our output_lines object to ensure we have a clean slate for the new map generation.
            self.state.output_lines.output_lines.clear()
            output_the_front_matter(current_config(self.state), state=self.state)

            try:
                # 2. RUN IO BOUND: Uses background threads to preserve memory singletons safely
                await run.io_bound(build_html, "", state=self.state)
            except MapTaskerError as e:
                # Intercept background termination codes gracefully.  This was
                # "except SystemExit" and had to be: build_html and everything under it
                # ended the process outright on any error.  They raise this now, which
                # is an ordinary Exception, so a failed build is one failed build --
                # the window stays up and says what happened, in the error's own words
                # when it has any.
                if e.exit_code == 6:
                    gui.display_message_box(
                        translate_string("Map view creation skipped: No valid XML source found or action canceled."),
                        "Orange",
                    )
                elif e.message:
                    gui.display_message_box(f"Map processing error: {e.message}", "Orange")
                else:
                    gui.display_message_box(f"Map processing halted with system code: {e.exit_code}", "Red")
                return

            # Check if an entry-point processing failure occurred during build_html
            if getattr(self.state, "error_code", 0) > 0:
                gui.display_message_box(f"Map processing error: {self.state.error_msg}", "Orange")
                clear_error()
                return

            # Now process the data for display in the gui.  How big the Map is comes
            # from the build rather than from output_lines, which holds nothing at all
            # when the Map that was already on disk was shown again (see mapcache).
            output_length = self.state.map_output_line_count

            # Clear out our inline data to free up memory for the GUI display, since we no longer need it.
            self.state.output_lines.output_lines.clear()

            # Display the map in its own browser window/tab rather than the main window.
            # A "goto" rides along on the URL rather than being pushed into the window
            # afterwards: the popout is its own page with its own timing, and only it knows
            # when the Map has finished streaming in and is therefore scrollable.
            #
            # "scope" says which Project this Map was built for -- always, not just for a
            # jump -- so that a later clicked finding can tell whether the Map already on
            # screen is one that can show what it points at, or whether it has to build its
            # own.  Read here rather than remembered on PrimeItems because the popout is
            # constructed after this call returns, by which time any overrides for this one
            # build have been put back.
            query = urlencode({"goto": goto, "scope": self.state.program_arguments.single_project_name or ""})
            _open_popout_window(f"/popout/map?{query}", getattr(gui, "open_view_in_new_window", False))

            # Check for hard stop limit and notify user if output was truncated
            if output_length > gui.view_limit:
                gui.display_message_box(
                    f"Map view truncated {output_length} lines to {gui.view_limit} lines due to view limit.",
                    "Orange",
                )
            gui.display_message_box(translate_string("Map View opened in a new browser window."), "Green")
            map_path = output_path("MapTasker.html", state=self.state)
            gui.display_message_box(f"{translate_string('Map saved to')} {map_path}", "Green")
        finally:
            _clear_busy_banner(building)

    async def _view_diagram(self) -> None:
        """Build the Diagram and open it in a window of its own."""
        gui = self.gui
        if self.state.tasker_root_elements["all_projects"] or self.state.tasker_root_elements["all_profiles"]:
            gui.display_message_box(
                translate_string("The 'Diagram' view is running in the background.  Please stand by..."),
                "Green",
            )

            # Offload the configuration outliner to an IO-bound thread safely
            try:
                await run.io_bound(outline_the_configuration, state=self.state)
            except MapTaskerError as error:
                reason = error.message or f"system code: {error.exit_code}"
                gui.display_message_box(f"Diagram processing error: {reason}", "Orange")
                return

            # Check if an entry-point processing failure occurred (e.g. check_limit() in
            # diagram.py tripping the view_limit) during outline_the_configuration(). Unlike
            # the "map" branch above, this used to go unchecked: on failure, network_map()
            # (diagram.py) skips writing DIAGRAM_FILE and computing PrimeItems.diagram_connectors
            # entirely, so the popout below would silently reopen whatever stale diagram (and
            # stale/absent connector data) happened to already be on disk from an earlier,
            # successful run -- which looks like a normal diagram but whose connectors no
            # longer highlight anything when clicked, with no indication anything went wrong.
            if getattr(self.state, "error_code", 0) > 0:
                gui.display_message_box(f"Diagram processing error: {self.state.error_msg}", "Orange")
                clear_error()
                return

            # Display the diagram in its own browser window/tab rather than the main window.
            # What the app was showing when this Diagram was drawn, carried so the
            # view can say so on its own toolbar -- and say when the selection has
            # moved on since.  A Diagram is a snapshot: nothing rebuilds it when the
            # user picks a different single object, so its hotlinks go on pointing at
            # the objects of the selection it was built for, and there was no sign of
            # that anywhere on screen.
            built_for = urlencode({"built_for": mapjump.current_scope(state=self.state).phrase})
            _open_popout_window(
                f"/popout/diagram?{built_for}",
                getattr(gui, "open_view_in_new_window", False),
            )

            # Cut short at the view limit?  Say so, as the "map" branch above does -- the
            # diagram is still shown, up to the point the limit allowed.
            if self.state.diagram_limit_msg:
                gui.display_message_box(self.state.diagram_limit_msg, "Orange")
            gui.display_message_box(translate_string("Diagram View opened in a new browser window."), "Green")
            diagram_path = output_path(DIAGRAM_FILE, state=self.state)
            gui.display_message_box(f"{translate_string('Diagram saved to')} {diagram_path}", "Green")
        else:
            gui.display_message_box(
                translate_string("No XML data loaded! Please select a valid XML file first."),
                "Orange",
            )

    def _view_misc(self) -> None:
        """Open the Misc view, which finds its own content."""
        gui = self.gui
        gui.display_message_box(
            translate_string("The 'Misc' view is running in the background.  Please stand by..."),
            "LimeGreen",
        )
        gui.textview = NiceGuiTextView(
            gui,
            title="Misc View",
            the_data=[],
        )

    def _view_tree(self) -> None:
        """Show the Tree view, or say there is nothing to show it of."""
        gui = self.gui
        tree_data = gui.build_the_tree()
        if tree_data:
            gui.textview = NiceGuiTreeView(gui, "Tree View", items=tree_data)
        else:
            gui.display_message_box(translate_string("No Project(s) Found in XML!"), "Red")
            return

    def _view_invalid(self) -> None:
        """Say that the view asked for is not one there is."""
        gui = self.gui
        ui.notify(
            translate_string("No XML data loaded! Please Get XML from Android or Local drive first."),
            type="warning",
            position="top",
        )
        gui.display_message_box(
            translate_string("Invalid view type specified. Use 'map', 'diagram', or 'tree'."),
            "Red",
        )

    def clear_view_event(self) -> None:
        """Clears the current view and resets the textview, closing any open Map/Diagram popout tabs."""
        if hasattr(self.gui, "content_container") and self.gui.content_container:
            self.gui.content_container.clear()

        # Drop the references to the views that were just deleted along with those
        # elements. Everything that reaches back into a rendered view guards on those
        # references (handle_color_pick_event's live re-colouring, clear_event's
        # un-highlighting), so leaving the dead objects here left them all working on
        # elements that no longer exist. Back to the "no view rendered" state MyGui
        # starts in (see guiwins.py). The popouts are closed just below, which is what
        # invalidates the views rendered into them too.
        forget_views(self.gui)

        # Close every Map/Diagram popout this session opened -- including the ones a popout
        # opened for itself, which is why this is mapjump.close_popouts_js and not a loop
        # over this window's own list: a Map built for a jump from the Diagram belongs to
        # the DIAGRAM's list (see _open_popout_window), and Clear used to close the Diagram
        # and leave that Map behind.  The same call Exit makes, minus shutting anything down.
        ui.run_javascript(mapjump.close_popouts_js())
        ui.notify(translate_string("View cleared."), type="info", position="bottom")

    async def rebuild_map_for_jump(self, target: mapjump.Target) -> None:
        """Build a Map that holds this object, and open it scrolled to it.

        What a clicked report finding falls back to when no Map on screen can show it --
        because none is open, because the one that is shows a single Project, or because
        its detail level leaves out the Tasks and actions the finding is about.

        The build is deliberately the whole configuration at a detail level high enough for
        this object: those are the two settings that decide whether the Map contains it at
        all, and a click that says "take me there" is worth honouring rather than answering
        with a second reason it cannot.  Nothing the user can see changes -- the overrides
        go into program_arguments for this one build and are put straight back, while the
        pulldowns and the detail selector keep whatever they held.  The next Map View press
        is therefore exactly the Map they asked for, not the one this needed.

        Not silently: the settings are not the user's, so the notification says which ones
        this went past.
        """
        level = max(self.state.program_arguments.display_detail_level, mapjump.minimum_detail_level(target))
        # Narrowed to the Project that owns what was clicked, rather than built whole.  A
        # click asks to be shown one thing, and a Map of one Project is both the answer to
        # that and a great deal quicker to build and to read than a Map of everything.
        #
        # Whole file only when there is no Project to narrow to: an orphan Profile, a Scene
        # no Project lists, a Task filed under none -- exactly the objects the reachability
        # findings are about -- and a variable, which the Map indexes per Project but the
        # cross-reference does not attribute to one.
        overrides: dict[str, object] = dict.fromkeys(SELECTION_KEYS, "")
        overrides["display_detail_level"] = level
        scope = mapjump.scope_for(target)
        if scope:
            overrides["single_project_name"] = scope
        # A TaskerNet description is governed by its own option rather than by the detail
        # level, so a finding about what somebody wrote in one needs that option on for the
        # Map to hold the line at all -- the same argument as the detail level above.
        if mapjump.needs_taskernet(target):
            overrides["taskernet"] = True

        # Say which settings this went past, and only those: the point of saying anything is
        # that the Map on screen afterwards is not the one the user's own settings would have
        # produced.  Worked out by comparing the overrides against what is actually set, so
        # that a user already on this Project at this detail level is told nothing at all.
        changed = {key for key, value in overrides.items() if self.state.program_arguments[key] != value}
        reasons: list[str] = []
        if changed & set(SELECTION_KEYS):
            reasons.append(f"{translate_string('Project')} '{scope}'" if scope else translate_string("whole file"))
        if "display_detail_level" in changed:
            reasons.append(f"{translate_string('detail level')} {level}")
        if "taskernet" in changed:
            reasons.append(translate_string("TaskerNet information"))
        ui.notify(
            f"{translate_string('Building the Map to show')} {target.label}"
            + (f" ({', '.join(reasons)})" if reasons else "")
            + " ...",
            type="info",
            position="top",
        )

        # Put back exactly what was there, key by key.
        saved = {key: self.state.program_arguments[key] for key in overrides}
        try:
            # held_overrides, not just the update view_event does, because the build is not
            # the only thing writing these: capture_gui_state re-copies the GUI's own
            # single-item selection over program_arguments from NiceGUI's outbox loop, and
            # one of this build's own notifications is enough to trigger it.  See its
            # definition in guistate for what that cost.
            with held_overrides(overrides, state=self.state):
                await self.view_event("map", goto=target.token(), overrides=overrides)
        finally:
            self.state.program_arguments.update(saved)

    def draw_task_flowchart(self, gui: MyGui) -> None:
        """Draw the single selected Task as a flowchart in its own window, if one is chosen.

        Silent about there being no chart when no single Task is selected -- said as a hint
        rather than as a failure, since the report the user just asked for did run.

        The chart is left on PrimeItems for the popped-out page to pick up: that page is
        built from a URL and is handed nothing, which is the same reason the Diagram popout
        re-reads its own generated file (see rungui.popout_view).
        """
        scope = mapjump.current_scope(state=self.state)
        if scope.label != "Task":
            ui.notify(
                translate_string("Choose a single Task in 'Specific Name' to also see it drawn as a flowchart."),
                type="info",
                position="bottom",
            )
            return

        # A Scope holds every Task id of that name, because a backup may legally hold two
        # Tasks called the same thing (healthck reports that as DUPLICATE-NAME).  Charting
        # them all in one window would read as one enormous Task, so the first is drawn and
        # the user is told the choice was made.
        task_ids = sorted(scope.tasks)
        flow = analyze_task_flow(task_ids[0], state=self.state) if task_ids else None
        if flow is None:
            gui.display_message_box(
                f"{translate_string('Could not find Task')} '{scope.name}'.",
                "Orange",
            )
            return
        if len(task_ids) > 1:
            ui.notify(
                f"{translate_string('More than one Task is named')} '{scope.name}'. "
                f"{translate_string('Drawing the first.')}",
                type="warning",
            )

        self.state.taskflow_rows = flowchart(flow, state=self.state)
        chart_file = write_flowchart(self.state.taskflow_rows, self.state)
        if chart_file:
            gui.display_message_box(f"{translate_string('Flowchart saved as')} {chart_file}", "Green")

        _open_popout_window("/popout/flow", getattr(gui, "open_view_in_new_window", False))
        gui.display_message_box(translate_string("Task Flow View opened in a new browser window."), "Green")

    def clear_event(self, _view_name: str = "mapview") -> None:
        """Clears the search input and un-highlights all matches left by search_event."""
        # Every open view, not just the newest: with "Open View In New Window" several
        # Map/Diagram windows can be up at once, each with its own highlighted matches.
        for textview in live_views(self.gui):
            self._clear_one_view(textview)

    def _clear_one_view(self, textview: NiceGuiTextView) -> None:
        """Clears one rendered view's search box and un-highlights its matches."""
        if hasattr(textview, "search_input"):
            textview.search_input.set_value("")

        # The results this view is holding on to are only replayable while their highlight
        # spans are still in the page, and they are about to stop being.
        if hasattr(textview, "invalidate_search_cache"):
            textview.invalidate_search_cache()

        if hasattr(textview, "scroll_area"):
            # Mirrors the "clearPreviousHighlights" routine inside NiceGuiTextView.search_event:
            # unwrap every '.search-highlight' span back into a plain text node, descending into
            # Shadow DOM roots too since that's where the highlighted matches actually live.
            ui.run_javascript(
                assettext.render(
                    "js/clear_search_highlights.js",
                    SCROLL_AREA_ID=mapjump.dom_id(textview.scroll_area),
                    HIGHLIGHT_CLASS=mapjump.HIGHLIGHT_CLASS,
                )
            )

        ui.notify(translate_string("Cleared the search highlights."), type="info")
