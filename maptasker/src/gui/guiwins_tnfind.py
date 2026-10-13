"""guiwins_tnfind: the Find Links dialog -- look for the TaskerNet share behind each Project, Profile and Task."""

#! /usr/bin/env python3

#                                                                                        #
# guiwins_tnfind: where tnfind hangs off the GUI.                                         #
#                                                                                        #
# One button starts the scan, which can take minutes the first time (it reads TaskerNet's   #
# whole public list, a dozen shares a page).  So the scan runs on a worker thread, and it   #
# belongs to a JOB that outlives this dialog: closing the dialog does not stop it, a        #
# notification says when it has finished, and opening the dialog again picks it up -- still  #
# running, with its progress, or finished, with what it found.  The dialog only WATCHES the   #
# job: a timer reads tnfind.Progress for the status line and the bar, and Stop sets the event  #
# the scan checks between steps.                                                         #
#                                                                                        #
# What it finds is shown in two groups.  The ones whose content agrees are already linked --     #
# the user asked for that to be automatic -- and listed so they can be seen and unlinked.       #
# The ones that might be it, and are not certain, are listed with a tick box each and nothing    #
# is linked until the user says; see tnfind's header for why a name alone decides nothing.      #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                              #
#
from __future__ import annotations

import asyncio
import contextlib
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from nicegui import context, run, ui

from maptasker.src.core.maputil2 import translate_string
from maptasker.src.core.sysconst import logger
from maptasker.src.mapops import tnfind, tnupdate

if TYPE_CHECKING:
    from collections.abc import Callable

    from nicegui import Client

    from maptasker.src.core.primitem import RunState

_BLURB = (
    "Looks through TaskerNet's public shares for the ones your Projects, Profiles, Tasks and Scenes came from.  "
    "A share is linked only when its content agrees with yours, not just its name: a name alone would often be a "
    "different author's share.  The first scan reads TaskerNet's whole list and can take several minutes; it is kept "
    "for a week.  The scan carries on in the background if you close this window, and a notification tells you "
    "when it is done."
)
_PRIVACY = (
    "Only taskernet.com is asked, for its public list and for the shares that might match.  Nothing from your "
    "configuration is sent."
)

# How many rows of each kind are drawn; every row is a link or a tick box.
_ROW_LIMIT = 150


# ##################################################################################
# The scan as a job that outlives the dialog.
# ##################################################################################


@dataclass
class _Job:
    """One scan: its progress, how to stop it, what it found, and who to tell when it ends.

    Kept apart from the dialog because the dialog can be closed -- and rebuilt -- while the scan runs.
    `client` is the browser page that started it, which is who is notified when it ends; `refresh` redraws
    the list of links of whichever dialog asked for the scan, and `listeners` are the Find Links dialogs
    currently watching.
    """

    client: Client
    progress: tnfind.Progress = field(default_factory=tnfind.Progress)
    stop: threading.Event = field(default_factory=threading.Event)
    task: asyncio.Task | None = None
    result: tnfind.ScanResult | None = None
    shown: bool = False
    refresh: Callable[[], None] | None = None
    listeners: list[Callable[[], None]] = field(default_factory=list)

    @property
    def running(self) -> bool:
        """Whether the scan is still going."""
        return self.task is not None and not self.task.done()


# The scan in progress, or the last one that finished.  A dict rather than a module variable so that
# starting one does not need a `global` statement; there is only ever the one key.
_JOBS: dict[str, _Job] = {}
# Running jobs' tasks, held so a task is not garbage-collected before it finishes.
_TASKS: set[asyncio.Task] = set()


def current_job() -> _Job | None:
    """The scan in progress, or the last one finished -- None if there has not been one."""
    return _JOBS.get("current")


def start_job(state: RunState, book: tnupdate.LinkBook, *, refresh_listing: bool, refresh: Callable[[], None]) -> _Job:
    """Start a scan in the background and return it.  Call from a page handler, so the page is known."""
    job = _Job(client=context.client, progress=tnfind.Progress(text=translate_string("Starting...")), refresh=refresh)
    _JOBS["current"] = job
    task = asyncio.create_task(_run(job, state, book, refresh_listing=refresh_listing))
    job.task = task
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    task.add_done_callback(_report_failure)
    return job


async def _run(job: _Job, state: RunState, book: tnupdate.LinkBook, *, refresh_listing: bool) -> None:
    """Run the scan on a worker thread, then tell whoever is watching, and the page that started it."""
    try:
        job.result = await run.io_bound(
            tnfind.scan,
            state,
            book,
            refresh=refresh_listing,
            progress=job.progress,
            stop=job.stop,
        )
    finally:
        _finish(job)


def _finish(job: _Job) -> None:
    """The scan has ended (or failed): redraw the links, wake the dialogs watching it, and say so."""
    if job.refresh is not None:
        with contextlib.suppress(RuntimeError):
            job.refresh()
    for listener in list(job.listeners):
        with contextlib.suppress(RuntimeError):
            listener()
    _announce(job)


def _announce(job: _Job) -> None:
    """Tell the page that started the scan how it went.  The page may be gone; then there is nobody to tell."""
    result = job.result
    if result is None:
        message, kind = translate_string("The TaskerNet scan could not be completed."), "negative"
    else:
        message = (
            f"{translate_string('TaskerNet scan finished:')} {len(result.linked)} {translate_string('linked')}, "
            f"{len(result.possible)} {translate_string('possible')}.  "
            f"{translate_string('Open Find Links to see them.')}"
        )
        kind = "warning" if result.problem or result.stopped else ("info" if result.listing_stopped else "positive")
    try:
        with job.client:
            ui.notify(message, type=kind, timeout=20000, close_button=True)
    except RuntimeError:
        logger.info("The page that started the TaskerNet scan is gone; nobody was told it finished.")


def _report_failure(task: asyncio.Task) -> None:
    """Log whatever the scan raised instead of losing it.  Cancellation is ordinary and says nothing."""
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        logger.exception("The TaskerNet scan failed", exc_info=error)


def _published(match: tnfind.Match) -> str:
    """'published 25-Sep-2024 13:30', or 'date unknown' when TaskerNet would not say."""
    if not match.published_ms:
        return translate_string("date unknown")
    return f"{translate_string('published')} {tnupdate.describe_date(match.published_ms)}"


def build_find_dialog(state: RunState, book: tnupdate.LinkBook, on_change: Callable[[], None]) -> ui.dialog | None:
    """Build the Find Links dialog, or None if no configuration is loaded to look for shares of.

    `on_change` is called when links have been added, so the dialog this was opened from can draw them.
    """
    tables = state.tasker_root_elements
    if not any(tables.get(name) for name in ("all_projects", "all_profiles", "all_tasks")):
        ui.notify(translate_string("No XML file has been loaded.  Get an XML file first."), type="warning")
        return None
    return _FindDialog(state, book, on_change).build()


class _FindDialog:
    """The Find Links dialog: its widgets, and the handlers that work on them."""

    def __init__(self, state: RunState, book: tnupdate.LinkBook, on_change: Callable[[], None]) -> None:
        """
        Args:
            state: The run's state.
            book: The links.  Shared with the dialog this was opened from.
            on_change: Called after links are added.
        """
        self.state = state
        self.book = book
        self.on_change = on_change
        self.job: _Job | None = None
        self.offered: list[tuple[tnfind.Match, ui.checkbox]] = []
        self.dialog: ui.dialog
        self.refresh_box: ui.checkbox
        self.start_button: ui.button
        self.stop_button: ui.button
        self.link_button: ui.button
        self.select_button: ui.button
        self.deselect_button: ui.button
        self.bar: ui.linear_progress
        self.status: ui.label
        self.results: ui.scroll_area
        self.timer: ui.timer

    def build(self) -> ui.dialog:
        """Draw the dialog."""
        # `persistent`, by the other dialogs' rule: a scan under way is stopped by a button, not by a stray click.
        with ui.dialog().props("persistent") as self.dialog, ui.card().classes("w-[900px] max-w-full p-6"):
            ui.label(translate_string("Find TaskerNet Links")).classes("text-lg font-bold text-blue-600")
            ui.label(translate_string(_BLURB)).classes("text-xs text-gray-500 italic mt-1")
            ui.label(translate_string(_PRIVACY)).classes("text-xs text-gray-500 italic mb-2")
            self.refresh_box = ui.checkbox(
                translate_string("Read TaskerNet's list of shares again, even if one was read lately"),
            ).classes("text-xs")
            with ui.row().classes("w-full items-center no-wrap gap-2"):
                self.start_button = ui.button(translate_string("Scan"), icon="travel_explore", on_click=self.start)
                self.stop_button = ui.button(translate_string("Stop"), on_click=self.stop).props("outline")
                self.stop_button.disable()
                self.bar = ui.linear_progress(value=0, show_value=False).classes("flex-1")
            self.status = ui.label("").classes("text-sm font-bold text-orange-500 mt-1")
            self.results = ui.scroll_area().classes("w-full h-[320px] border rounded dark:border-gray-700 mt-2")
            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                self.select_button = ui.button(translate_string("Select All"), on_click=self.select_all).props(
                    "outline"
                )
                self.deselect_button = ui.button(translate_string("Deselect All"), on_click=self.deselect_all).props(
                    "outline",
                )
                self.select_button.disable()
                self.deselect_button.disable()
                self.link_button = ui.button(translate_string("Link Ticked"), on_click=self.link_ticked)
                self.link_button.props("color=orange")
                self.link_button.disable()
                ui.button(translate_string("Close"), on_click=self.close).props("color=red").classes("text-white px-4")
            self.timer = ui.timer(0.3, self._tick, active=False)
        self._pick_up_job()
        return self.dialog

    def _pick_up_job(self) -> None:
        """Opened while a scan is running, or after one finished unseen: show where it is, or what it found."""
        job = current_job()
        if job is None:
            return
        if job.running:
            self._watch(job)
        elif job.result is not None and not job.shown:
            self.job = job
            self._show(job.result)

    def _notify(self, message: str, kind: Literal["positive", "negative", "warning", "info"] = "info") -> None:
        """A notification from the dialog's own context, so it works whatever button the handler was run from."""
        with self.dialog:
            ui.notify(message, type=kind)

    # ##############################################################################
    # Running the scan.
    # ##############################################################################

    def _tick(self) -> None:
        """Show what the scan thread says it is doing."""
        if self.job is None:
            return
        progress = self.job.progress
        self.status.set_text(progress.text)
        if progress.phase == tnfind.COMPARING and not self.job.stop.is_set() and not self.stop_button.enabled:
            # Stop pressed during the reading of the list ended only that; Stop is there again to end the comparing.
            self.stop_button.enable()
        if progress.total:
            self.bar.props(remove="indeterminate")
            self.bar.set_value(progress.done / progress.total)
        else:
            self.bar.props("indeterminate")

    def start(self) -> None:
        """Start the scan in the background and watch it.  Closing this dialog does not stop it."""
        job = current_job()
        if job is not None and job.running:
            self._watch(job)
            return
        self.results.clear()
        self._set_checklist_buttons(enabled=False)
        self._watch(
            start_job(self.state, self.book, refresh_listing=bool(self.refresh_box.value), refresh=self.on_change),
        )

    def _watch(self, job: _Job) -> None:
        """Follow a running scan: the status line and bar, Stop enabled, and told when it ends."""
        self.job = job
        job.refresh = self.on_change  # whoever is looking now is who wants the list of links redrawn
        job.listeners.append(self._ended)
        self.start_button.disable()
        self.stop_button.enable()
        self.timer.activate()

    def _ended(self) -> None:
        """The scan this dialog was watching has finished: stop watching, and show what it found."""
        self.timer.deactivate()
        self.start_button.enable()
        self.stop_button.disable()
        self.bar.props(remove="indeterminate")
        job = self.job
        if job is None or job.result is None:
            self.status.set_text(translate_string("The scan could not be completed."))
            return
        self.bar.set_value(1.0 if not job.result.stopped else self.bar.value)
        self._show(job.result)

    def stop(self) -> None:
        """Ask the scan to stop at its next step.  What it has linked stays linked."""
        if self.job is not None:
            self.job.stop.set()
        self.stop_button.disable()
        self.status.set_text(translate_string("Stopping..."))

    def close(self) -> None:
        """Close the dialog.  A scan under way carries on, and a notification says when it is done."""
        if self.job is not None and self.job.running:
            with contextlib.suppress(ValueError):
                self.job.listeners.remove(self._ended)
            self._notify(translate_string("The scan carries on in the background.  You will be told when it is done."))
            self.timer.deactivate()
        self.dialog.close()

    # ##############################################################################
    # What it found.
    # ##############################################################################

    def _show(self, result: tnfind.ScanResult) -> None:
        """The summary line, then what was linked, then what is for the user to choose."""
        if self.job is not None:
            self.job.shown = True
        self.status.set_text(self._summary(result))
        self.offered = []
        self.results.clear()
        with self.results, ui.column().classes("w-full gap-0 p-2"):
            if result.problem:
                ui.label(result.problem).classes("text-xs text-red-500 mb-1")
            if not result.catalogue_size:
                ui.label(translate_string("TaskerNet's list of shares could not be read.")).classes("text-sm italic")
            self._show_linked(result.linked)
            self._show_possible(result.possible)
            if not result.linked and not result.possible and result.catalogue_size:
                ui.label(translate_string("Nothing you have matched a public share.")).classes("text-sm italic")
        self._set_checklist_buttons(enabled=bool(self.offered))

    def _summary(self, result: tnfind.ScanResult) -> str:
        """One sentence: what happened and what it found."""
        part = "" if result.catalogue_complete else f" ({translate_string('only part of the list was read')})"
        stopped = f" {translate_string('Stopped early.')}" if result.stopped else ""
        if result.listing_stopped:
            part = f" ({translate_string('stopped while reading the list, so only part of it was compared')})"
        return (
            f"{len(result.linked)} {translate_string('linked')}, {len(result.possible)} "
            f"{translate_string('possible')}, {result.different} {translate_string('with a share of the same name but different content')}; "
            f"{result.checked} {translate_string('of yours checked against')} {result.catalogue_size} "
            f"{translate_string('public shares')}{part}.{stopped}"
        )

    def _show_linked(self, linked: list[tnfind.Match]) -> None:
        """What was linked automatically, each with a link to its page."""
        if not linked:
            return
        ui.label(f"{translate_string('Linked automatically')} ({len(linked)})").classes("text-sm font-bold mt-1")
        for match in linked[:_ROW_LIMIT]:
            with ui.row().classes("items-baseline gap-2 no-wrap"):
                ui.label(match.kind.upper()).classes("font-mono text-xs font-bold text-orange-500 w-16 shrink-0")
                ui.label(match.name).classes("font-mono text-sm break-all")
                ui.label(f"{match.score:.0%}").classes("text-xs text-green-600 shrink-0")
                ui.label(_published(match)).classes("text-xs text-gray-500 shrink-0")
                ui.link(translate_string("on TaskerNet"), match.ref.link, new_tab=True).classes("text-xs shrink-0")

    def _show_possible(self, possible: list[tnfind.Match]) -> None:
        """What might be it, each with a tick box."""
        if not possible:
            return
        ui.label(
            f"{translate_string('Possible matches -- tick the ones that are yours')} ({len(possible)})",
        ).classes("text-sm font-bold mt-3")
        for match in possible[:_ROW_LIMIT]:
            with ui.row().classes("items-center gap-2 no-wrap"):
                box = ui.checkbox("")
                self.offered.append((match, box))
                ui.label(match.kind.upper()).classes("font-mono text-xs font-bold text-orange-500 w-16 shrink-0")
                ui.label(match.name).classes("font-mono text-sm break-all")
                ui.label(
                    f"{match.score:.0%} {translate_string('alike')}, {match.downloads} {translate_string('downloads')}, "
                    f"{_published(match)}",
                ).classes("text-xs text-gray-500 shrink-0")
                ui.link(translate_string("on TaskerNet"), match.ref.link, new_tab=True).classes("text-xs shrink-0")

    def _set_checklist_buttons(self, *, enabled: bool) -> None:
        """Select All, Deselect All and Link Ticked work on the checklist, so they are there only when there is one."""
        for button in (self.select_button, self.deselect_button, self.link_button):
            if enabled:
                button.enable()
            else:
                button.disable()

    def select_all(self) -> None:
        """Tick every match on the checklist that has not already been linked."""
        self._tick_all(value=True)

    def deselect_all(self) -> None:
        """Clear every tick."""
        self._tick_all(value=False)

    def _tick_all(self, *, value: bool) -> None:
        """Set every box that can still be set -- one whose match has been linked is greyed out and stays as it is."""
        for _match, box in self.offered:
            if box.enabled:
                box.set_value(value)

    async def link_ticked(self) -> None:
        """Link the ones ticked.  Where several shares are ticked for one object, the best agreeing one is used."""
        chosen: dict[tuple[str, str], tnfind.Match] = {}
        for match, box in self.offered:
            key = (match.kind, match.name)
            if box.value and (key not in chosen or match.score > chosen[key].score):
                chosen[key] = match
        if not chosen:
            self._notify(translate_string("Tick the ones to link first."), "warning")
            return
        self._set_checklist_buttons(enabled=False)
        await run.io_bound(self._link_all, list(chosen.values()))
        for match, box in self.offered:
            if (match.kind, match.name) in chosen:
                box.set_value(False)
                box.disable()
        self.on_change()
        self._set_checklist_buttons(enabled=any(box.enabled for _match, box in self.offered))
        self._notify(f"{len(chosen)} {translate_string('linked.')}", "positive")

    def _link_all(self, matches: list[tnfind.Match]) -> None:
        """Link each match (a request to TaskerNet for its date, so off the event loop)."""
        for match in matches:
            tnfind.link_match(self.book, match, auto=False)
