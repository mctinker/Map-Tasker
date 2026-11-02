"""The tools menu's windows: refactor, fix findings, history, TaskerNet updates, the fire simulator, the monitor, missing resources, trends, the task stepper, and undo/redo."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nicegui import ui

from maptasker.src.analysis import livemon, taskcases
from maptasker.src.core.maputil2 import (
    suppress_logged,
    translate_string,
)
from maptasker.src.core.primitem import (
    SINGLE_ITEM_LABELS,
)
from maptasker.src.edit import sessundo
from maptasker.src.gui.guistate import SELECTION_KEYS, held_overrides
from maptasker.src.gui.guiutils import (
    display_selected_object_labels,
    is_no_selection,
    refresh_tasker_object_pulldowns,
    reset_single_item_selection,
)
from maptasker.src.gui.guiwins_firesim import build_firesim_dialog
from maptasker.src.gui.guiwins_fix import build_fix_dialog
from maptasker.src.gui.guiwins_monitor import build_monitor_dialog
from maptasker.src.gui.guiwins_nav import go_to_target, opening_view_in_a_new_window
from maptasker.src.gui.guiwins_refactor import build_refactor_dialog
from maptasker.src.gui.guiwins_resources import build_resources_dialog
from maptasker.src.gui.guiwins_restore import build_restore_dialog
from maptasker.src.gui.guiwins_taskstep import build_taskstep_dialog
from maptasker.src.gui.guiwins_tnupdate import build_tnupdate_dialog
from maptasker.src.gui.guiwins_trend import build_trend_dialog
from maptasker.src.gui.userintr_group import HandlerGroup

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from maptasker.src.core import mapjump
    from maptasker.src.gui.userintr import MyGui

# Which lookup table answers "is this single-item selection still a real item?", per
# SINGLE_ITEM_LABELS.  The two *_by_name tables are the ones keyed the way the pulldowns
# name things: all_profiles and all_tasks are keyed by id, so checking those would say no
# to every Profile and Task there is.
_SELECTION_TABLES = {
    "Project": "all_projects",
    "Profile": "all_profiles_by_name",
    "Task": "all_tasks_by_name",
    "Scene": "all_scenes",
}


def _single_selection_still_exists(gui: MyGui) -> bool:
    """Whether the 'Specific Name' selection, if there is one, still names something.

    An Undo can take away the very item that is selected -- undoing an Add removes it,
    undoing a Rename puts a different name on it -- and a selection naming nothing is not
    harmless: PrimeItems.program_arguments still carries it, so the next Map or Diagram
    would be built filtered on an item that is not there and come back empty.
    """
    for label in SINGLE_ITEM_LABELS:
        name = getattr(gui, f"single_{label.lower()}_name", "")
        if is_no_selection(name):
            continue
        if name not in gui.state.tasker_root_elements.get(_SELECTION_TABLES[label], {}):
            return False
    return True


class ToolEventHandlers(HandlerGroup):
    """The tools menu's windows: refactor, fix findings, history, TaskerNet updates, the fire simulator, the monitor, missing resources, trends, the task stepper, and undo/redo."""

    def refactor_event(self) -> None:
        """Open the Refactor dialog: the structural moves, with a preview.

        Lives on the main window beside Edit/Add and the Undo group rather than on the Map
        toolbar, because a refactor is an EDIT.  Three of its four operations -- inline,
        move, duplicate -- name an object and act on it whole, and nothing about them
        depends on what is currently drawn; hanging them off a view meant a Map had to be
        built before any of them could be reached at all.

        Rebuilt on every press rather than kept, for the reason maprefac gives about its
        Plan: it closes over live elements, and holding one across a reopen is precisely the
        stale-handle case maprefac.apply's attachment check exists to catch.
        """
        self._dismiss_refactor_dialog()

        def make_jump(target: mapjump.Target) -> Callable[[], Coroutine[Any, Any, None]]:
            """One preview row's click: open what it names in a window of its own.

            The new window is what keeps the dialog: from here the jump has no Map to
            scroll, so go_to_target falls through to building one, and a build that reused
            the tab would take this window -- and the preview in it -- with it.  See
            guiwins_nav.opening_view_in_a_new_window for the whole of why.
            """

            async def go() -> None:
                with opening_view_in_a_new_window(self.gui):
                    await go_to_target(self.gui, target)

            return go

        async def refresh_after_apply() -> None:
            """What to bring up to date once a refactor has been applied.

            The pulldowns, and only the pulldowns.  A refactor adds and removes whole
            objects, so an option list built before one offers names that no longer resolve
            -- the same reason Undo and Redo refresh them (see _step_edit_history).  No view
            is rebuilt: there may not be one, and if there is it is a separate window that
            the user can refresh when they want to look at it.
            """
            refresh_tasker_object_pulldowns(self.gui)

        dialog = build_refactor_dialog(
            "", make_jump, refresh_after_apply, self.hub.save_whole_configuration, state=self.state
        )
        if dialog is None:
            return
        self.gui.refactor_dialog = dialog
        dialog.open()

    def fix_findings_event(self) -> None:
        """Open the Fix Findings dialog: the Health Check's findings, with a repair for each.

        Lives beside the Health Check button rather than inside its report, because the
        report is one escaped blob of text in a <pre> and a tick box is not something that
        can be put into one.  Pressing it runs a scan of its own -- a much smaller one than
        the check's, since mapfix leaves out every category it cannot repair -- so this does
        not depend on a Health Check having been run first, and does not go stale when one
        was run an hour ago.

        Rebuilt on every press rather than kept, for the reason maprefac gives about its
        Plan and refactor_event repeats: it closes over live elements, and holding one
        across a reopen is precisely the stale-handle case mapfix.apply's attachment check
        exists to catch.
        """
        self._dismiss_fix_dialog()

        def make_jump(target: mapjump.Target) -> Callable[[], Coroutine[Any, Any, None]]:
            """One row's click: open what it names in a window of its own.

            The new window is what keeps this dialog up -- see refactor_event's own copy of
            this, and guiwins_nav.opening_view_in_a_new_window for the whole of why.  It matters
            more here than there: the list holds ticks and decisions the user has been
            making, and going to look at one of the Tasks must not cost them the lot.
            """

            async def go() -> None:
                with opening_view_in_a_new_window(self.gui):
                    await go_to_target(self.gui, target)

            return go

        async def refresh_after_apply() -> None:
            """What to bring up to date once repairs have been made.

            The pulldowns, and only the pulldowns.  A repair can delete a Task, so an option
            list built before one offers names that no longer resolve -- the same reason Undo
            and Redo refresh them.  No view is rebuilt: there may not be one, and if there is
            it is a separate window the user can refresh when they want to look at it.
            """
            refresh_tasker_object_pulldowns(self.gui)

        dialog = build_fix_dialog(
            "", make_jump, refresh_after_apply, self.hub.save_whole_configuration, state=self.state
        )
        if dialog is None:
            return
        self.gui.fix_dialog = dialog
        dialog.open()

    def restore_history_event(self) -> None:
        """Open the Restore From History dialog: bring a deleted object back, or undo an edit.

        Beside Changes Since because it is the other half of that report -- the report says
        what was deleted or changed since a configuration in the history, and this is where
        one of those rows can be put back.  One object at a time, never a merge; see
        maprestore's header.

        Rebuilt on every press, for fix_findings_event's reason: a preview closes over live
        elements, and holding one across a reopen is the stale-handle case maprefac.apply's
        attachment check exists to catch.
        """
        self._dismiss_restore_dialog()

        def make_jump(target: mapjump.Target) -> Callable[[], Coroutine[Any, Any, None]]:
            """One row's click: open what it names in a window of its own, keeping this one up."""

            async def go() -> None:
                with opening_view_in_a_new_window(self.gui):
                    await go_to_target(self.gui, target)

            return go

        async def refresh_after_apply() -> None:
            """The pulldowns: a restore adds whole objects, so an option list built before one is short."""
            refresh_tasker_object_pulldowns(self.gui)

        dialog = build_restore_dialog(
            make_jump, refresh_after_apply, self.hub.save_whole_configuration, state=self.state
        )
        if dialog is None:
            return
        self.gui.restore_dialog = dialog
        dialog.open()

    def taskernet_updates_event(self) -> None:
        """Open the TaskerNet Updates dialog: linked shares, what their authors changed, and taking it.

        Beside Restore From History because it is that dialog's other source: both bring an
        object in from a configuration that is not the one open, one at a time, previewed first.

        Rebuilt on every press, for restore_history_event's reason: a preview closes over live
        elements, and holding one across a reopen is the stale-handle case maprefac.apply's
        attachment check exists to catch.
        """
        self._dismiss_tnupdate_dialog()

        def make_jump(target: mapjump.Target) -> Callable[[], Coroutine[Any, Any, None]]:
            """One row's click: open what it names in a window of its own, keeping this one up."""

            async def go() -> None:
                with opening_view_in_a_new_window(self.gui):
                    await go_to_target(self.gui, target)

            return go

        async def refresh_after_apply() -> None:
            """The pulldowns: taking an update can add whole objects, so an option list built before one is short."""
            refresh_tasker_object_pulldowns(self.gui)

        dialog = build_tnupdate_dialog(
            make_jump, refresh_after_apply, self.hub.save_whole_configuration, state=self.state
        )
        if dialog is None:
            return
        self.gui.tnupdate_dialog = dialog
        dialog.open()

    def _dismiss_tnupdate_dialog(self) -> None:
        """Take down the TaskerNet Updates dialog if one is still up -- see _dismiss_restore_dialog."""
        dialog = getattr(self.gui, "tnupdate_dialog", None)
        self.gui.tnupdate_dialog = None
        if dialog is not None:
            with suppress_logged("Deleting the TaskerNet Updates dialog"):
                dialog.delete()

    def fire_simulator_event(self) -> None:
        """Open the What Fires When? dialog: pick a moment, see which Profiles it makes active.

        Rebuilt on every press, for fix_findings_event's reason, and more simply here: the
        Wi-Fi and app pickers are filled from the configuration loaded at the moment of the
        press, and a dialog kept from an earlier file would offer that file's networks.
        """
        dialog = getattr(self.gui, "firesim_dialog", None)
        self.gui.firesim_dialog = None
        if dialog is not None:
            with suppress_logged("Deleting the Fire Simulator dialog"):
                dialog.delete()

        def make_jump(target: mapjump.Target) -> Callable[[], Coroutine[Any, Any, None]]:
            """One row's click: open what it names in a window of its own, keeping this one up."""

            async def go() -> None:
                with opening_view_in_a_new_window(self.gui):
                    await go_to_target(self.gui, target)

            return go

        dialog = build_firesim_dialog(make_jump, state=self.state, step_task=self.task_stepper_event)
        if dialog is None:
            return
        self.gui.firesim_dialog = dialog
        dialog.open()

    async def bring_up_the_diagram_for_the_monitor(self, projects: set[str]) -> None:
        """Build and open the Diagram the Live Run Monitor will light up: one that holds what has fired.

        The Diagram button builds for whatever single Project, Profile or Task is selected in the main window, which
        is the wrong Diagram to watch a phone with -- the objects that fire are mostly not the selected one.  So
        this builds for the one Project everything seen so far belongs to, or for the whole configuration when
        that is several (or nothing has been seen yet), and puts the selection back as it was: the overrides go into
        program_arguments for this one build and are restored straight after, as rebuild_map_for_jump does.
        """
        scope = livemon.diagram_scope(projects)
        overrides: dict[str, object] = dict.fromkeys(SELECTION_KEYS, "")
        if scope:
            overrides["single_project_name"] = scope
        ui.notify(
            f"{translate_string('Building the Diagram of')} "
            f"{translate_string('Project') + ' ' + repr(scope) if scope else translate_string('the whole configuration')}"
            " ...",
            type="info",
            position="top",
        )
        saved = {key: self.state.program_arguments[key] for key in overrides}
        try:
            with held_overrides(overrides, state=self.state):
                await self.hub.views.view_event("diagram", overrides=overrides)
        finally:
            self.state.program_arguments.update(saved)

    async def live_monitor_event(self) -> None:
        """Open the Live Run Monitor: which Profiles and Tasks fire on the phone, lit up in the Diagram as they do.

        Rebuilt on every press, for fire_simulator_event's reason: it watches the configuration loaded at the moment
        of the press.  An earlier one is stopped before it is taken down, so a monitor is never left asking the
        phone with nothing on screen to stop it.
        """
        dialog = getattr(self.gui, "monitor_dialog", None)
        monitor = getattr(dialog, "monitor", None)
        self.gui.monitor_dialog = None
        if monitor is not None:
            await monitor.stop_monitoring()
        if dialog is not None:
            with suppress_logged("Deleting the Live Run Monitor dialog"):
                dialog.delete()

        def make_jump(target: mapjump.Target) -> Callable[[], Coroutine[Any, Any, None]]:
            """One row's click: open what it names in a window of its own, keeping this one up."""

            async def go() -> None:
                with opening_view_in_a_new_window(self.gui):
                    await go_to_target(self.gui, target)

            return go

        dialog = build_monitor_dialog(self.gui, make_jump, self.bring_up_the_diagram_for_the_monitor)
        if dialog is None:
            return
        self.gui.monitor_dialog = dialog
        dialog.open()

    def missing_resources_event(self) -> None:
        """Open Missing Resources: do the files, folders, images, sounds, Scenes and apps the actions use still exist?

        Rebuilt on every press, for fire_simulator_event's reason: it opens on what the configuration loaded at the
        moment of the press refers to.
        """
        dialog = getattr(self.gui, "resources_dialog", None)
        self.gui.resources_dialog = None
        if dialog is not None:
            with suppress_logged("Deleting the Missing Resources dialog"):
                dialog.delete()

        def make_jump(target: mapjump.Target) -> Callable[[], Coroutine[Any, Any, None]]:
            """One row's click: open what it names in a window of its own, keeping this one up."""

            async def go() -> None:
                with opening_view_in_a_new_window(self.gui):
                    await go_to_target(self.gui, target)

            return go

        dialog = build_resources_dialog(self.gui, make_jump)
        if dialog is None:
            return
        self.gui.resources_dialog = dialog
        dialog.open()

    def trend_dashboard_event(self) -> None:
        """Open the Trend Dashboard: how the configuration's size, complexity and findings have moved over the history.

        Rebuilt on every press, for fire_simulator_event's reason: the file it starts on is the one open now.
        """
        dialog = getattr(self.gui, "trend_dialog", None)
        self.gui.trend_dialog = None
        if dialog is not None:
            with suppress_logged("Deleting the Trend Dashboard dialog"):
                dialog.delete()
        dialog = build_trend_dialog(self.state)
        if dialog is None:
            return
        self.gui.trend_dialog = dialog
        dialog.open()

    def task_stepper_event(self, task: str = "", case: taskcases.Case | None = None) -> None:
        """Open the Task Stepper: dry-run one Task with the variables it starts with.

        `task` is the Task to start with, when it is opened from somewhere that knows which (a line of What
        Fires When); `case` a saved test to open it on, with its values filled in (a row of Task Tests).  Rebuilt on every press, for fire_simulator_event's reason: the Task picker is filled
        from the configuration loaded at the moment of the press.
        """
        dialog = getattr(self.gui, "taskstep_dialog", None)
        self.gui.taskstep_dialog = None
        if dialog is not None:
            with suppress_logged("Deleting the Task Stepper dialog"):
                dialog.delete()

        def make_jump(target: mapjump.Target) -> Callable[[], Coroutine[Any, Any, None]]:
            """One line's click: open what it names in a window of its own, keeping this one up."""

            async def go() -> None:
                with opening_view_in_a_new_window(self.gui):
                    await go_to_target(self.gui, target)

            return go

        dialog = build_taskstep_dialog(make_jump, self.state, task, case)
        if dialog is None:
            return
        self.gui.taskstep_dialog = dialog
        dialog.open()

    def _dismiss_restore_dialog(self) -> None:
        """Take down the Restore dialog if one is still up -- see _dismiss_fix_dialog."""
        dialog = getattr(self.gui, "restore_dialog", None)
        self.gui.restore_dialog = None
        if dialog is not None:
            with suppress_logged("Deleting the Restore dialog"):
                dialog.delete()

    def _dismiss_fix_dialog(self) -> None:
        """Take down the Fix Findings dialog if one is still up.

        Deleted rather than closed, for _dismiss_refactor_dialog's reason: a fresh dialog is
        built per press, and a closed-but-undeleted one is a stack that grows with the page.
        """
        dialog = getattr(self.gui, "fix_dialog", None)
        self.gui.fix_dialog = None
        if dialog is not None:
            with suppress_logged("Deleting the Fix Findings dialog"):
                dialog.delete()

    def _dismiss_refactor_dialog(self) -> None:
        """Take down the Refactor dialog if one is still up.

        Deleted rather than closed: a fresh dialog is built per press, so the one being
        replaced has nothing left to hold, and a closed-but-undeleted dialog is a stack that
        grows with the page.  A dialog whose page has gone away raises rather than
        answering; that is one more dialog already gone, not an error to report.
        """
        dialog = getattr(self.gui, "refactor_dialog", None)
        self.gui.refactor_dialog = None
        if dialog is not None:
            with suppress_logged("Deleting the Refactor dialog"):
                dialog.delete()

    def _step_edit_history(self, *, forwards: bool) -> None:
        """Shared body of the Undo and Redo buttons -- the two differ only in which way
        they walk the history and what they say afterwards.

        Refreshing the pulldowns is not cosmetic: the restore replaced every lookup table,
        so an option list built from the old ones would offer names that no longer resolve.
        Whatever single Project/Profile/Task/Scene was selected is deliberately left alone;
        if the step removed it, refresh_tasker_object_pulldowns drops it from the options
        the same way a file load does.
        """
        succeeded, message = sessundo.redo(state=self.state) if forwards else sessundo.undo(state=self.state)
        if not succeeded:
            ui.notify(message, type="warning")
            return

        refresh_tasker_object_pulldowns(self.gui)
        # Only when the step actually took the selected item away -- undoing an edit to
        # some other Task must not clear the Project the user is looking at.
        #
        # display_selected_object_labels is the other half of that reset and not optional:
        # reset_single_item_selection clears the names and the pulldowns, and this is what
        # repaints the three places the old name is still written on screen -- the
        # "Current <item> selection" line, the "Display only ..." caption under the
        # pulldowns, and the Analyze tab's four targets.  The pair is always used together
        # (see guiutils.list_tasker_objects, which loads a new file the same way).
        if not _single_selection_still_exists(self.gui):
            reset_single_item_selection(self.gui)
            display_selected_object_labels(self.gui)
        action = translate_string("Redid") if forwards else translate_string("Undid")
        ui.notify(f"{action}: {message}", type="positive")

    def undo_edit_event(self) -> None:
        """Take back the last change made to the loaded configuration -- see sessundo."""
        self._step_edit_history(forwards=False)

    def redo_edit_event(self) -> None:
        """Put back the last change Undo took away -- see sessundo."""
        self._step_edit_history(forwards=True)
