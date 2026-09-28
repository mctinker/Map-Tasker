"""The open views, and the jumps that take a result to the object it names.

Split out of guiwins.py along with the views themselves (guiwins_views.py) and their
Search, Find and Replace (guiwins_search.py).  It sits below both: a Find result, a search
hit and a clicked Health Check finding all end in go_to_target, and every view registers
itself here as it is drawn, so neither of those modules can be the one this imports.

Two things live here:

  * The registry of rendered views -- register_view, live_views and the liveness checks
    behind them.  A view outlives the event that built it, and every handler that reaches
    back into one has to know whether it is still on a page.
  * The jumps -- go_to_target and the Map and Diagram jumps it chooses between, plus the
    click wiring that turns a Health Check finding into one.

It names the view classes only as types, under TYPE_CHECKING, and never imports them.
"""

from __future__ import annotations

import contextlib
import weakref
from typing import TYPE_CHECKING

from nicegui import Event, context, ui

from maptasker.src import mapjump
from maptasker.src.maputil2 import translate_string
from maptasker.src.sysconst import logger

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Iterator

    from maptasker.src.guiwins_views import NiceGuiTextView
    from maptasker.src.userintr import MyGui


# ##################################################################################
# The rendered-view registry
# ##################################################################################
def element_is_live(element: object) -> bool:
    """Whether a NiceGUI element can still be safely interacted with -- it hasn't
    been deleted, and the client (the browser page) it was built for is still
    around.

    Needed because this app keeps references to elements across events: the rendered
    Map/Diagram/Tree views outlive the event that built them, and anything reaching
    into one later (live re-colouring in handle_color_pick_event, un-highlighting in
    clear_event) is one step removed from whether that view still exists. Three things
    invalidate it -- "Clear" deletes the rendered view's elements (see clear_view_event),
    a browser reload replaces the client outright, and closing a popout tab takes its
    client with it -- and none of them clears the reference, so a plain truthiness check
    passes while the element underneath is dead. Using one then raises
    RuntimeError("The client this element belongs to has been deleted.") from inside
    NiceGUI's own element.client, which reaches the user as a console traceback rather
    than anything actionable.

    element.client raises rather than returning None once the client has been
    garbage-collected, so that access is what has to be guarded; is_deleted covers
    the other case, where the element itself was deleted but its client is still
    alive (exactly what "Clear" leaves behind).
    """
    if not element or getattr(element, "is_deleted", False):
        return False
    try:
        client = element.client
    except RuntimeError:
        return False
    return not getattr(client, "is_deleted", False)


def view_is_live(view: object) -> bool:
    """Whether a rendered view is still on a page we can safely touch."""
    if not view:
        return False
    # The text views hang everything off a scroll_area; the tree view off a tree.
    return element_is_live(getattr(view, "scroll_area", None) or getattr(view, "tree", None))


def register_view(master_gui: MyGui, view: object) -> None:
    """Record a freshly rendered view as the current one, and add it to the live set.

    `master_gui.textview` stays the most recent view, which is what the single-view
    callers want. `master_gui.textviews` additionally keeps every view still open, so
    that with "Open View In New Window" enabled -- where several Map/Diagram tabs can
    be on screen at once -- the handlers that reach back into a rendered view can
    reach all of them rather than only the newest.
    """
    master_gui.textviews = [*live_views(master_gui), view]
    master_gui.textview = view


def live_views(master_gui: MyGui) -> list:
    """Every rendered view still safe to touch, oldest first, pruning any that died."""
    views = [view for view in getattr(master_gui, "textviews", None) or [] if view_is_live(view)]
    master_gui.textviews = views
    return views


def forget_views(master_gui: MyGui) -> None:
    """Drop every rendered-view reference -- for when they've all just been deleted."""
    master_gui.textviews = []
    master_gui.textview = False


# Pages whose report rows are already wired to the jump handler.  Same guard, and for the
# same reason, as _CANVAS_EVENT_CLIENTS above: ui.on() subscribes for the page it is called
# from, and a second subscription would run every jump twice.
_FINDING_CLICK_CLIENTS: weakref.WeakSet = weakref.WeakSet()


def _bring_to_front(view: NiceGuiTextView) -> None:
    """Raise the window a jump has just landed in, so the user is looking at the answer.

    Only for a jump answered by a view that was ALREADY open.  The other path --
    rebuild_map_for_jump -- ends in window.open(), which raises the window it opens on its
    own; this is the case that had nothing doing it (see mapjump.bring_to_front_js).

    Not awaited.  The window is being raised for the user's benefit and nothing here
    depends on the outcome, so there is no reason to hold the jump open for a round trip --
    and a browser that declines to raise the window is not a failure to report.  The
    request is still sent: NiceGUI's run_javascript queues the message eagerly and only the
    response needs awaiting.

    A view whose page has gone away raises rather than answering, which is one more window
    that cannot be raised; the caller is already treating that as "not this one".
    """
    view.scroll_area.client.run_javascript(mapjump.bring_to_front_js())


async def jump_map_view(master_gui: MyGui, target: mapjump.Target) -> bool:
    """Scroll an open Map view to a Target and highlight it.  False if none could.

    Only a Map built for the Project this object needs is used.  Merely CONTAINING the
    object is not enough: a Map of the whole file contains everything, so without this a
    click would keep landing in whatever wide Map happened to be open and the user would
    never see the Map of one Project they asked for -- which is exactly what happened the
    first time this shipped.  Nothing is reused across scopes, so the Map on screen after a
    click is always the one that click would have built.

    Tries the most recently opened Map view first.  With "Open View In New Window" on,
    several can be up at once, showing different runs, and the one the user is most likely
    looking at is the last one they asked for.  Any that turns out not to hold this object
    is passed over rather than treated as a failure, so the answer is "no Map on screen has
    it", not "the first one I tried didn't".

    A view whose page has gone away between live_views() pruning it and this reaching it
    raises rather than answering; that is one more Map without the object, not an error to
    report.
    """
    wanted = mapjump.scope_for(target)
    for view in reversed(live_views(master_gui)):
        if not str(getattr(view, "title", "")).startswith("Map"):
            continue
        if getattr(view, "map_scope", "") != wanted:
            continue
        try:
            landed = await view.scroll_area.client.run_javascript(mapjump.jump_js(target.anchor), timeout=5)
            if landed:
                _bring_to_front(view)
        except (TimeoutError, RuntimeError, AttributeError):
            continue
        if landed:
            return True
    return False


def _report_view_failure(task: asyncio.Task) -> None:
    """Log whatever a view's rendering task raised, instead of losing it.

    Cancellation is ordinary -- a view whose page went away mid-render -- and says nothing.
    """
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        logger.exception("Rendering a view failed", exc_info=error)


async def jump_diagram_view(master_gui: MyGui, target: mapjump.Target) -> bool:
    """Scroll an open Diagram view to a Target and highlight it.  False if none could.

    The Diagram's counterpart to jump_map_view.  Where the Map is addressed by the anchor
    ids it carries, the Diagram is addressed by the line the object was drawn on, recorded
    while the diagram was built (see diagram.py's note above flatten_with_quotes) and
    looked up here.  That is what makes the jump land on THIS Task rather than on the first
    Task drawn with the same name, which is ordinary in Tasker.

    Falls back to matching the drawn text when there is no recorded line: a Diagram built
    before this version, or one whose file is on disk from an earlier run.  Weaker, and
    knowingly so -- it cannot tell two copies of a name apart -- but better than refusing
    to move.

    Most recently opened Diagram first, and any that turns out not to hold the object is
    passed over, exactly as jump_map_view treats its Maps: with "Open View In New Window"
    on, several can be up at once showing different runs.
    """
    placement = mapjump.diagram_placement(target)
    patterns = mapjump.diagram_patterns(target)
    anchor = mapjump.diagram_anchor(target)
    # Nothing to go on at all: an object the Diagram neither recorded nor draws a line for
    # -- an unnamed Task, a variable.  Answered here rather than with a match on something
    # else that happens to be nearby.  An anchor counts as something to go on: an
    # interactive Diagram carries one on every name it drew, including the unnamed Task's,
    # which is drawn under a derived name no pattern can reconstruct.
    if placement is None and not patterns and not anchor:
        return False
    for view in reversed(live_views(master_gui)):
        if not str(getattr(view, "title", "")).startswith("Diagram"):
            continue
        try:
            landed = await view.scroll_area.client.run_javascript(
                mapjump.diagram_jump_js(
                    f"c{view.scroll_area.id}",
                    patterns,
                    placement,
                    anchor,
                ),
                timeout=5,
            )
            if landed:
                _bring_to_front(view)
        except (TimeoutError, RuntimeError, AttributeError):
            continue
        if landed:
            return True
    return False


@contextlib.contextmanager
def opening_view_in_a_new_window(gui: MyGui) -> Iterator[None]:
    """Turn "Open View In New Window" on for the duration of one jump, then put it back.

    WHAT IT IS FOR.  A Map view IS a popout window, opened by userintr._open_popout_window
    under a name popout_window_name keeps STABLE while that option is off.  A stable name is
    what makes window.open reuse a tab -- which is the whole point of the option, and the
    wrong behaviour for a jump launched from a dialog, because the tab it reuses is the tab
    the dialog is in.  The dialog goes, and with it whatever it was holding.

    THE REAL SETTING, and it does survive being put back.  The attribute is bound two-way to
    its checkbox, so the obvious worry is that the restore loses a race with NiceGUI's
    binding loop.  It does not, and the reason is the order bind() registers its two links:
    bind_from goes first, so _refresh_step propagates gui-attribute -> checkbox BEFORE the
    checkbox -> gui-attribute link is reached.  The attribute is therefore always the winner
    of a disagreement, which is exactly what a restore needs.  Pinned by a test that drives
    the real nicegui.binding rather than a stand-in, because a stand-in cannot answer this.

    The checkbox does visibly tick for as long as the jump takes.  That is the option being
    on, honestly shown, rather than a hidden mode.

    The one way it can outlive the jump is the process dying mid-jump -- kill the app while
    a Map is building and the finally never runs, so the option is saved on as if it had
    been chosen.  Losing a setting to a kill is what a kill does; it is not worth a second,
    unbound flag to guard against.
    """
    remembered = getattr(gui, "open_view_in_new_window", False)
    gui.open_view_in_new_window = True
    try:
        yield
    finally:
        gui.open_view_in_new_window = remembered


async def go_to_target(master_gui: MyGui, target: mapjump.Target, prefer_diagram: bool = False) -> None:
    """Take one clicked row -- a report finding, or a Find result -- to what it points at.

    The whole of what a click does, in one place, because there are now two things that
    emit one: the reports' clickable rows (see register_finding_clicks) and the Find
    results list, which is a NiceGUI dialog and reaches this directly rather than through
    the browser.

    prefer_diagram is set by a Find run from a Diagram view, where the user is looking at
    the Diagram and expects the answer to appear in it.  It is a preference and not a
    demand: a Diagram that does not hold the object -- or an object the Diagram draws no
    line for at all -- falls through to the Map, which can always be built to show it.
    """
    # A report, and a set of results, are both snapshots.  The object named can have been
    # renamed or deleted in the editor since, so say so rather than scrolling to nothing.
    if not mapjump.exists(target):
        ui.notify(
            f"{target.label} {translate_string('is no longer in the loaded configuration.')}",
            type="warning",
            position="top",
        )
        return

    if prefer_diagram and await jump_diagram_view(master_gui, target):
        return
    if await jump_map_view(master_gui, target):
        return

    # Nothing on screen can show it.  Whether that is because no Map is open, because the
    # one that is covers a single Project, or because its detail level leaves the Tasks and
    # actions out is not worth telling apart here -- the answer to all three is the same
    # Map, so build it (see rebuild_map_for_jump, which says what it is doing and why).
    handlers = getattr(master_gui, "event_handlers", None)
    if handlers is None:
        ui.notify(
            translate_string("No Map view is open.  Run Map View, then click this again."),
            type="warning",
            position="top",
        )
        return
    await handlers.rebuild_map_for_jump(target)


def register_finding_clicks(master_gui: MyGui) -> None:
    """Subscribe this page's report-jump event, once, while the layout is still being built.

    Called from initialize_screen for exactly the reason guiwins_canvas._register_canvas_events is, and it
    is the whole reason clicking a finding did nothing at first: ui.on adds its listener to
    client.layout, and adding one to an element the browser already has makes NiceGUI
    re-render that element and everything under it.  Registering this from the report view's
    own background task -- later than any dialog -- meant the re-render tore out the click
    listener enable_finding_clicks had just installed on the report's container, so the
    spans were there, styled and focusable, and a click reached nothing at all.

    A report view still calls this itself, so a page built without going through
    initialize_screen is not left without the plumbing; the guard makes that call a no-op.
    """
    client = context.client
    if client in _FINDING_CLICK_CLIENTS:
        return
    _FINDING_CLICK_CLIENTS.add(client)

    async def jump(event: Event) -> None:
        """Take one clicked report row to where it points."""
        target = mapjump.Target.from_token(str((event.args or {}).get("target", "")))
        if target is not None:
            await go_to_target(master_gui, target)

    ui.on("mt_jump", jump)


def enable_finding_clicks(view: NiceGuiTextView) -> None:
    """Install the browser-side click listener for one rendered report.

    DOM work only.  The Python subscription that acts on what this emits is registered at
    page build time instead -- see register_finding_clicks for why it cannot be done from
    here.  The call below is the no-op guard for a page that never went through
    initialize_screen; on the main window it has already happened.
    """
    # Everything here needs an active NiceGUI slot, and this runs from process_data's
    # background task, where there is none: the slot stack is per-task and empty, so
    # ui.run_javascript cannot tell which client to target and context.client -- which
    # register_finding_clicks reads -- raises outright.  Re-entering the scroll area
    # restores both, the same way _enable_connector_highlighting does.
    with view.scroll_area:
        register_finding_clicks(view.master_gui)
        ui.run_javascript(mapjump.click_wiring_js(f"c{view.scroll_area.id}"))
