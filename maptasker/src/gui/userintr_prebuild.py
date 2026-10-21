"""userintr_prebuild: build the Map in the background once a file is loaded, if the user asked for that."""

#! /usr/bin/env python3

#                                                                                        #
# userintr_prebuild: the Pre-Build The Map checkbox's half of the event handlers.            #
#                                                                                        #
# Building the Map of a large configuration is the longest wait in the window, and the     #
# window sits idle for as long as the user reads the Display Options.  With the checkbox   #
# ticked, that time is spent building it, so that the Map button finds it done.            #
#                                                                                        #
# WHEN.  A timer looks every moment for a loaded configuration, with the single Project, Profile,   #
# Task or Scene now selected, that this has not built the Map of (prebuild_tick) rather than     #
# every way of loading a file or choosing an item announcing itself: there are five ways to load   #
# one -- the picker, the Android fetch, the start-up load, Undo and Redo, a comparison's "switch      #
# to this file" -- and the one that forgot would be the one that does nothing.  A Map is built    #
# for once the same configuration and selection have been there for two looks running, so a load  #
# that is still in the middle of building its tables, or a pulldown still being worked, is never   #
# built from; and not while a view is being built for the user, nor while the AI is analysing.     #
# Changing the selection builds again because the cache holds one Map, and the Map of one Project   #
# is not the Map of the whole file.                                                         #
#                                                                                        #
# HOW.  Exactly as pressing Map would: the same preparation (get_ready_to_build, shared with   #
# view_event, so the settings it builds from are the settings a press will take), the same   #
# build, on the same thread pool.  Nothing is shown and nothing is said.                  #
#                                                                                        #
# AND THEN THE PRESS FINDS IT.  The cache (mapcache) remembers the Map against what it was    #
# built from, and a first build changes that -- it settles unnamed Tasks and Profiles into   #
# their names -- so the press would not match what was just built and would build it again.   #
# mapcache.settle moves the record to the configuration the build left, and the settings as   #
# the window would give them to a press (read again, for the build edits them in passing).    #
# That is only vouched for when nothing edited the configuration while the build ran, since an   #
# edit and the settling look the same to a digest: an edit, or a different file, and the    #
# record is dropped and the press builds, as it would have without any of this.            #
#                                                                                        #
# A PRESS DURING THE BUILD WAITS.  The build and a view share the run state -- the output      #
# lines, the totals, the settings -- so view_event waits for it (wait_for_prebuild) before it     #
# touches any of them, then carries on and finds the Map done.                              #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from nicegui import run

from maptasker.src.core.maputil2 import suppress_logged
from maptasker.src.core.outdir import output_path
from maptasker.src.core.primitem import clear_error
from maptasker.src.core.runcfg import current_config
from maptasker.src.core.sysconst import logger
from maptasker.src.edit import sessundo
from maptasker.src.gui.guistate import SELECTION_KEYS
from maptasker.src.mapgen import mapcache
from maptasker.src.mapgen.bildhtml import build_html
from maptasker.src.mapgen.frontmtr import output_the_front_matter

if TYPE_CHECKING:
    from collections.abc import Generator

    from maptasker.src.core.primitem import RunState
    from maptasker.src.gui.userintr import MyGui

# The tables that say a configuration is loaded, any one of which is enough to have a Map of.
_OBJECT_TABLES = ("all_projects", "all_profiles", "all_tasks")


def _report_failure(task: asyncio.Task[None]) -> None:
    """Log whatever a build ahead of time raised, instead of losing it.  Cancellation says nothing."""
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        logger.error("Building the Map ahead of time failed", exc_info=error)


# What a Map is built for: the loaded configuration, and the selection -- the names of the single Task,
# Scene, Profile and Project selected, which the Map is limited to ("" for none).  Two Maps with the same
# configuration and a different selection are different Maps, and the cache holds only one.
BuiltFor = tuple[object, tuple[str, ...]]


@dataclass
class _Building:
    """What the build ahead of time and the views being built have to agree on, for the whole program.

    Not on the event handlers: every browser tab, and every reload of one, builds its own window and
    its own handlers, and all of them share one run state.  Two sets of handlers each deciding, by
    their own count of what is going on, that it is their turn to build is how two builds would end
    up rewriting the same output lines.
    """

    # The build under way or last made, and what it was made for: the loaded configuration and the
    # single Project, Profile, Task or Scene selected (see BuiltFor).
    task: asyncio.Task[None] | None = None
    built_for: BuiltFor | None = None
    # What the last look found wanting a build.  Built for once seen twice running.
    seen: BuiltFor | None = None
    # How many views are being built for the user right now (see view_event).
    views: int = 0


_building = _Building()


class PrebuildEventHandlers:
    """The Pre-Build The Map handlers MapTaskerEventHandlers inherits: self.gui is the window, and the
    preparation a build starts with is reached through self, as view_event reaches it."""

    # The run state the window shows: MapTaskerEventHandlers, which inherits this class, answers with
    # its window's.
    state: RunState
    gui: MyGui
    # Whether this window's box was ticked at its last look.
    was_ticked: bool = False

    if TYPE_CHECKING:

        def get_ready_to_build(self, overrides: dict[str, Any] | None) -> None:
            """MapTaskerEventHandlers's: the condition a build starts from, shared with view_event."""

    @contextlib.contextmanager
    def view_in_progress(self) -> Generator[None, None, None]:
        """Held for as long as a view is being built for the user, so that nothing is built ahead of time meanwhile."""
        _building.views += 1
        try:
            yield
        finally:
            _building.views -= 1

    def _selection(self) -> tuple[str, ...]:
        """The single items selected, as a press of Map would take them from the window."""
        return tuple(str(getattr(self.gui, key, "") or "") for key in SELECTION_KEYS)

    def prebuild_running(self) -> bool:
        """Whether a build ahead of time is still under way."""
        return _building.task is not None and not _building.task.done()

    async def wait_for_prebuild(self) -> None:
        """Return when no build ahead of time is under way.

        A build the caller is waiting on is not stopped by the caller going away: the wait is
        abandoned, the build is not.
        """
        task = _building.task
        if task is not None and not task.done():
            await asyncio.wait({task})

    def _may_prebuild(self) -> bool:
        """Whether the checkbox is ticked and nothing else is using the run state."""
        arguments = self.state.program_arguments
        return (
            bool(getattr(self.gui, "prebuild_map", False))
            and any(self.state.tasker_root_elements.get(table) for table in _OBJECT_TABLES)
            and not self.prebuild_running()
            and not _building.views
            and not arguments.ai_analyze
            and not arguments.rerun
        )

    def prebuild_tick(self) -> None:
        """One look: start a build if the loaded configuration, as it is selected, is waiting for one.

        Called by a timer on the window.  Cheap when there is nothing to do -- a few attribute
        reads -- which is what lets it run all the time.
        """
        # Ticking the box is asking for the Map to be built, whether or not this configuration has
        # been built for already -- and a setting changed since means the Map built then is not the
        # one a press would take.  Each window follows its own box, so two windows that disagree
        # about it cannot send each other round in circles.
        ticked = bool(getattr(self.gui, "prebuild_map", False))
        if ticked and not self.was_ticked:
            _building.built_for = None
        self.was_ticked = ticked

        root = cast("object | None", self.state.xml_root)
        if root is None or not self._may_prebuild():
            _building.seen = None
            return
        wanted: BuiltFor = (root, self._selection())
        if wanted == _building.built_for:
            _building.seen = None
            return
        if wanted != _building.seen:
            # Seen once.  Give a load that is still finishing, or a selection that is still being
            # made, a moment.
            _building.seen = wanted
            return
        _building.built_for = wanted
        _building.task = asyncio.create_task(self._prebuild_the_map(root))
        _building.task.add_done_callback(_report_failure)

    async def _prebuild_the_map(self, root: object) -> None:
        """Build the Map as pressing the button would, say nothing, and have the press find it.

        :param root: the configuration being built for, which must still be the loaded one at the end
        """
        state = self.state
        edits_before = tuple(sessundo.history(state))
        built = False
        with suppress_logged("Building the Map ahead of time"):
            self.get_ready_to_build(None)
            selection = self._selection()
            state.output_lines.output_lines.clear()
            output_the_front_matter(current_config(state), state=state)
            await run.io_bound(build_html, "", state=state)

            if state.error_code > 0:
                clear_error()
            elif (
                state.xml_root is root
                and tuple(sessundo.history(state)) == edits_before
                # The build reads the selection as it goes, so a Map built while it was changed is
                # neither one.
                and self._selection() == selection
            ):
                # The settings a press would take now, read the way a press reads them.
                self.get_ready_to_build(None)
                built = mapcache.settle(output_path("MapTasker.html", state=state), mapcache.digests(state=state))
        if not built:
            mapcache.forget()
        state.output_lines.output_lines.clear()
