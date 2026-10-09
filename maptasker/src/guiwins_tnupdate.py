"""guiwins_tnupdate: the TaskerNet Updates dialog -- linked shares, what is new in them, and taking it."""

#! /usr/bin/env python3

#                                                                                        #
# guiwins_tnupdate: where tnupdate hangs off the GUI.                                    #
#                                                                                        #
# One dialog, in three parts.  The LINKS: each Project, Profile, Task or Scene the user    #
# has tied to a TaskerNet share, with whether the author has published since.  The way in:  #
# paste a share's link, say which of your objects it is, and it is linked.  And the REVIEW:  #
# 'Review' on a link fetches the share and lists what the author changed, each with a       #
# 'Take this' button that shows exactly what taking it would do before anything happens.    #
#                                                                                        #
# IT IS THE RESTORE FROM HISTORY DIALOG'S SECOND SOURCE, AND KEEPS ITS RULES               #
#                                                                                        #
# Taking an update is a maprestore restore with the share as the older side, so the         #
# dialog is guiwins_restore's: one button per row and not a tick box, because each take is    #
# planned against the configuration as the one before it left it; nothing applied unseen;   #
# Apply only while the preview it applies is on screen; each take one press of Undo.  Its   #
# rows and its preview are drawn by the very functions that dialog draws them with.          #
#                                                                                        #
# WHAT LEAVES THE MACHINE                                                                 #
#                                                                                        #
# The address of each linked share, to taskernet.com, and nothing else -- see tnupdate.  The  #
# dialog says so on its face, because "checks for updates" can sound like more than that.     #
#                                                                                        #
# AN UPDATE IS SOMEBODY ELSE'S AUTOMATION                                                  #
#                                                                                        #
# Taking one puts the author's Tasks and Profiles on the user's phone, where they run with   #
# whatever access Tasker has.  So the dialog says to read each preview, and never offers a    #
# way to take everything at once.                                                         #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                              #
#
from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from functools import partial
from typing import TYPE_CHECKING, Literal

from nicegui import context, run, ui

from maptasker.src import diffload, maprefac, maprestore, tnupdate
from maptasker.src.guiwins_restore import draw_preview, draw_row, tip
from maptasker.src.guiwins_tnfind import build_find_dialog
from maptasker.src.maputil2 import translate_string
from maptasker.src.sysconst import logger

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from nicegui import Client

    from maptasker.src.primitem import RunState

# The file the saved report is stamped into.
REPORT_FILE = "MapTasker_TaskerNet.txt"

# How many rows are drawn, for guiwins_restore's reason: every one is a button and a link.
_ROW_LIMIT = 200

# How many detail lines a row shows.  More than the Restore dialog's three: what a new Task does, or
# what changed in a script, is the reason for deciding, and the preview is one more click away.
_DETAIL_LINES = 8

# How many removed objects a note names before "...".
_NAMES_IN_NOTE = 5

_BLURB = (
    "Link a Project, Profile, Task or Scene to the TaskerNet share it came from, and MapTasker tells you when "
    "its author publishes a newer version, shows what they changed, and lets you take each change one at a time or "
    "accept the latest version all at once."
)
_PRIVACY = (
    "'Check Now' sends taskernet.com the address of each defined link and nothing else: no part of your "
    "configuration leaves this computer.  An update is someone else's automation that will run on your phone -- read what "
    "each one does in its preview before you take it."
)

# What a link's status says, and the colour it is said in.
_STATUS_CLASSES = {
    tnupdate.UPDATE: "text-orange-600 dark:text-orange-400 font-bold",
    tnupdate.CURRENT: "text-green-600 dark:text-green-400",
    tnupdate.UNREVIEWED: "text-blue-600 dark:text-blue-400",
    tnupdate.UNCHECKED: "text-gray-500",
}


def _status_text(link: tnupdate.Link) -> str:
    """One line saying where a link stands."""
    published = tnupdate.describe_date(link.latest_ms)
    status = link.status
    if status == tnupdate.UPDATE:
        return f"{translate_string('Newer version published')} {published}"
    if status == tnupdate.CURRENT:
        return f"{translate_string('Up to date -- published')} {published}"
    if status == tnupdate.UNREVIEWED:
        return translate_string("Linked -- press Review to compare it with your copy")
    return translate_string("Not checked yet")


def _row_tag(candidate: maprestore.Candidate) -> str:
    """The row's tag in the share's terms: what xmldiff calls 'removed' is something the author has and you do not."""
    kind = candidate.kind.upper()
    return f"{kind}-NEW" if candidate.action == maprestore.BRING_BACK else f"{kind}-CHANGED"


@dataclass
class _Held:
    """What the dialog is holding: the review on screen, the plan on screen, and what has been taken."""

    review: tnupdate.Review | None = None
    plan: maprefac.Plan | None = None
    previewed: maprestore.Candidate | None = None
    applied: dict[tuple[str, str, str], maprestore.Candidate] = field(default_factory=dict)
    busy: bool = False
    # Whether the review on screen was the first this link had, so the wording that says what
    # that means survives the rescan after something is taken.
    first_review: bool = False


def build_tnupdate_dialog(
    make_jump: Callable,
    rebuild_after_apply: Callable[[], Coroutine],
    save_configuration: Callable[[], Coroutine],
    state: RunState,
) -> ui.dialog | None:
    """Build and return the TaskerNet Updates dialog, or None if there is no configuration to link to.

    Takes what it needs from the view and nothing else, for guiwins_restore's reason: this module
    is reached FROM guiwins, and reaching back into it would be a circular import.
    """
    if not state.tasker_root_elements.get("all_tasks") and not state.tasker_root_elements.get("all_projects"):
        ui.notify(translate_string("No XML file has been loaded.  Get an XML file first."), type="warning")
        return None
    return _UpdatesDialog(make_jump, rebuild_after_apply, save_configuration, state, tnupdate.default_book()).build()


class _UpdatesDialog:
    """The TaskerNet Updates dialog: its widgets, and the handlers that work on them."""

    def __init__(
        self,
        make_jump: Callable,
        rebuild_after_apply: Callable[[], Coroutine],
        save_configuration: Callable[[], Coroutine],
        state: RunState,
        book: tnupdate.LinkBook,
    ) -> None:
        """
        Args:
            make_jump: How to follow a row to the object it names.
            rebuild_after_apply: How to bring the rest of the window up to date once something has changed.
            save_configuration: How to write the configuration to a file.
            state: The run's state.
            book: The links, kept between runs.
        """
        self.make_jump = make_jump
        self.rebuild_after_apply = rebuild_after_apply
        self.save_configuration = save_configuration
        self.state = state
        self.book = book
        self.held = _Held()
        self.reference: tnupdate.ShareRef | None = None
        self.dialog: ui.dialog
        self.links_area: ui.column
        self.link_input: ui.input
        self.local_pick: ui.select
        self.link_note: ui.label
        self.add_button: ui.button
        self.check_button: ui.button
        self.find_button: ui.button
        self.find_dialog: ui.dialog | None = None
        self.summary: ui.label
        self.notes: ui.column
        self.show_all: ui.checkbox
        self.list_area: ui.scroll_area
        self.preview_heading: ui.label
        self.preview_area: ui.scroll_area
        self.apply_button: ui.button
        self.accept_button: ui.button
        self.latest_button: ui.button
        self.report_button: ui.button

    def _notify(
        self,
        message: str,
        *,
        kind: Literal["positive", "negative", "warning", "info"] = "info",
        position: Literal["top", "bottom"] = "bottom",
    ) -> None:
        """Show a notification from the dialog's own context.

        Not ui.notify bare: a handler runs in the context of the button that was pressed, and
        the buttons in the list of links are deleted and drawn again by the very handlers that
        then want to say something -- which leaves ui.notify a slot whose element is gone.
        """
        with self.dialog:
            ui.notify(message, type=kind, position=position)

    # ##############################################################################
    # Layout.
    # ##############################################################################

    def build(self) -> ui.dialog:
        """Draw the dialog, and look for anything newer once it is on a page."""
        # `persistent`, by the Restore dialog's rule: a dialog holding a preview leaves on a button.
        with ui.dialog().props("persistent") as self.dialog, ui.card().classes("w-[1000px] max-w-full p-6"):
            ui.label(translate_string("TaskerNet Updates")).classes("text-lg font-bold text-blue-600")
            ui.label(translate_string(_BLURB)).classes("text-xs text-gray-500 italic mt-1")
            ui.label(translate_string(_PRIVACY)).classes("text-xs text-gray-500 italic mb-2")
            self._build_links_section()
            self._build_add_section()
            self.summary = ui.label("").classes("text-sm font-bold text-orange-500 mt-2")
            self.notes = ui.column().classes("w-full gap-0")
            self.show_all = ui.checkbox(
                translate_string("Show every difference from my copy, not only the author's changes"),
                on_change=self._redraw_list,
            ).classes("text-xs")
            self.show_all.set_visibility(False)
            self.list_area = ui.scroll_area().classes("w-full h-[220px] border rounded dark:border-gray-700 mt-1")
            self.preview_heading = ui.label("").classes("text-sm font-bold text-blue-600 mt-3")
            self.preview_area = ui.scroll_area().classes("w-full h-[160px] border rounded dark:border-gray-700 mt-1")
            self._build_buttons()
            self._draw_links()
            ui.timer(0.1, self._first_check, once=True)
        return self.dialog

    def _build_links_section(self) -> None:
        """The heading, the Check Now button and the list of links."""
        with ui.row().classes("w-full items-center justify-between mt-2"):
            ui.label(translate_string("Linked shares")).classes("text-sm font-bold")
            self.check_button = ui.button(translate_string("Check Now"), icon="cloud_sync", on_click=self.check_now)
            self.check_button.props("dense outline")
            self.find_button = ui.button(
                translate_string("Find Links"), icon="travel_explore", on_click=self.find_links
            )
            self.find_button.props("dense outline")
            tip(
                self.find_button,
                "Look through TaskerNet's public shares for the ones your Projects, Profiles, Tasks and Scenes "
                "came from, and link them for you.\n\n"
                "A share is linked only when its content agrees with yours, not just its name.  Ones that might "
                "be yours are listed for you to tick.\n\n"
                "The first scan reads TaskerNet's whole list of shares and can take several minutes.",
            )
            tip(
                self.check_button,
                "Ask TaskerNet whether each linked share has been published again since the version you have.\n\n"
                "One small request per link; nothing is downloaded and nothing of yours is sent.",
            )
        self.links_area = ui.column().classes("w-full gap-0 border rounded dark:border-gray-700 p-1")

    def _build_add_section(self) -> None:
        """Paste a link, say which of your objects it is, and link it."""
        ui.label(translate_string("Link a share")).classes("text-sm font-bold mt-2")
        self.link_input = ui.input(
            label=translate_string("TaskerNet share link"),
            placeholder="https://taskernet.com/shares/?user=...&id=Project%3A...",
            on_change=self._link_changed,
        ).classes("w-full")
        # A line under the box rather than a tooltip on it: a tooltip on the box opens over the
        # picker and the note below it, hiding exactly what the pasted address has just filled in.
        ui.label(
            translate_string(
                "Open the share's own page on TaskerNet (the one that displays when you click on the 'Import' "
                "button (e.g. has the 'Import:' instructions) and paste its address here.  This is a one-time setup process "
                "only for each project/profile/task to establish its linkage to TaskerNet.",
            ),
        ).classes("text-xs text-gray-500")
        with ui.row().classes("w-full items-center no-wrap gap-2"):
            self.local_pick = ui.select({}, label=translate_string("Which one of yours is it?")).classes("flex-1")
            self.add_button = ui.button(translate_string("Link"), icon="link", on_click=self.add_link)
            self.add_button.props("outline")
            self.add_button.disable()
        self.link_note = ui.label("").classes("text-xs text-gray-500")

    def _build_buttons(self) -> None:
        """Apply, Cancel Preview, Mark As Up To Date, Save Report, Save To Current File and Close."""
        with ui.row().classes("w-full justify-end mt-4 gap-2"):
            self.apply_button = ui.button(translate_string("Apply"), on_click=self.do_apply).classes("px-4")
            self.apply_button.props("color=orange")
            self.apply_button.disable()
            tip(
                self.apply_button,
                "Make the change the preview describes, and nothing else.\n\n"
                "Greyed out until a row's 'Take this' has drawn a preview that can be applied.\n\n"
                "One press of Undo afterwards puts the configuration back as it is now.",
            )
            ui.button(translate_string("Cancel Preview"), on_click=self.clear_preview).props("outline")
            self.latest_button = ui.button(translate_string("Accept Latest Version"), on_click=self.accept_latest)
            self.latest_button.props("color=orange outline")
            self.latest_button.disable()
            tip(
                self.latest_button,
                "Take the author's version of everything listed below, in one go, instead of pressing 'Take "
                "this' on each row.  There is no preview and no Apply: pressing this does it.\n\n"
                "Each change is made one after another; one that cannot be made is skipped and listed.  One "
                "press of Undo takes them all back.\n\n"
                "Then the version you have becomes the one published, as 'Mark As Up To Date' does.\n\n"
                "Ticking 'Show every difference' first includes the ones that are not the author's -- your "
                "own edits among them -- so read the list before you press this.",
            )
            self.accept_button = ui.button(translate_string("Mark As Up To Date"), on_click=self.mark_current)
            self.accept_button.props("outline")
            self.accept_button.disable()
            tip(
                self.accept_button,
                "Treat the version on screen as the one you have -- once you have taken what you want from it, "
                "or if you do not want it.  The notice goes away until the author publishes again, and the next "
                "update is compared with this version.",
            )
            self.report_button = ui.button(translate_string("Save Report"), on_click=self.save_report)
            self.report_button.props("outline")
            self.report_button.disable()
            tip(
                ui.button(translate_string("Save To Current File"), color="green", on_click=self.do_save).classes(
                    "text-white px-4",
                ),
                "Write the whole configuration -- what you have taken and every other edit made this session -- "
                "to a new, timestamped copy of the file you loaded.  The file you loaded is never written to.\n\n"
                "Until you press this, a change exists only in memory and is lost on exit.",
            )
            ui.button(translate_string("Close"), on_click=self.dialog.close).props("color=red").classes(
                "text-white px-4",
            )

    # ##############################################################################
    # The links.
    # ##############################################################################

    def _draw_links(self) -> None:
        """One row per link: what it is attached to, where it stands, and its buttons."""
        self.links_area.clear()
        with self.links_area:
            links = self.book.ordered()
            if not links:
                ui.label(translate_string("No shares are linked yet.  Link one below.")).classes(
                    "text-sm text-gray-500 italic p-2",
                )
            for link in links:
                self._draw_link_row(link)

    def _draw_link_row(self, link: tnupdate.Link) -> None:
        """One linked share."""
        loaded = tnupdate.local_scope(link, self.state) is not None
        with ui.row().classes("w-full items-center no-wrap gap-2 border-b dark:border-gray-700 py-1 px-2"):
            ui.label(link.kind.upper()).classes("font-mono text-xs font-bold text-orange-500 w-16 shrink-0")
            with ui.column().classes("flex-1 min-w-0 gap-0"):
                with ui.row().classes("items-baseline gap-2 min-w-0"):
                    ui.label(link.name).classes("font-mono text-sm break-all" + ("" if loaded else " text-gray-400"))
                    ui.link(translate_string("on TaskerNet"), link.link, new_tab=True).classes("text-xs")
                    if link.auto:
                        ui.label(translate_string("found automatically")).classes("text-xs text-gray-500 italic")
                if not loaded:
                    ui.label(translate_string("Not in the configuration that is loaded.")).classes(
                        "text-xs text-gray-500 italic",
                    )
                ui.label(_status_text(link)).classes("text-xs " + _STATUS_CLASSES[link.status])
                if link.problem:
                    ui.label(link.problem).classes("text-xs text-red-500 break-all")
            review = ui.button(translate_string("Review"), on_click=partial(self.review, link))
            review.props("dense outline").classes("shrink-0")
            tip(
                review,
                "Download this share from TaskerNet and set it beside your copy.  Nothing in your "
                "configuration is changed.\n\n"
                "Lists what the author changed since the version you last accepted, each with a 'Take this' "
                "button that previews before anything happens.\n\n"
                "The first time, there is no earlier version to compare with: the version published now is "
                "recorded as the one you have, and everything that differs from your copy is listed "
                "(some of it is Tasker rewriting the share when it was imported).\n\n"
                "Later reviews leave the version you have alone until you press 'Mark As Up To Date'.",
            )
            if not loaded:
                review.disable()
            unlink = ui.button(translate_string("Unlink"), on_click=partial(self.unlink, link))
            unlink.props("dense flat").classes("shrink-0")

    def unlink(self, link: tnupdate.Link) -> None:
        """Forget a link.  Nothing about the object it was attached to changes."""
        if self.held.review is not None and self.held.review.link is link:
            self._clear_review()
        self.book.remove(link)
        self._draw_links()

    def _link_changed(self, event: object) -> None:
        """Read the pasted address, and offer the objects of that kind to attach it to."""
        text = (getattr(event, "value", "") or "").strip()
        self.reference = None
        self.add_button.disable()
        if not text:
            self.link_note.set_text("")
            return
        try:
            self.reference = tnupdate.parse_link(text)
        except tnupdate.TaskerNetError as error:
            self.link_note.set_text(str(error))
            return
        names = tnupdate.local_names(self.reference.kind, self.state)
        self.local_pick.set_options(names, value=self.reference.name if self.reference.name in names else None)
        self.link_note.set_text(
            f"{translate_string('A')} {self.reference.kind} {translate_string('shared as')} '{self.reference.name}'.  "
            f"{translate_string('Pick the one of yours it is, then press Link.')}",
        )
        self.add_button.enable()

    async def add_link(self) -> None:
        """Link the pasted share to the chosen object, and compare it with that object straight away."""
        if self.reference is None or not self.local_pick.value:
            self._notify(translate_string("Choose which one of yours the share is."), kind="warning")
            return
        try:
            link = self.book.add(self.reference.kind, self.local_pick.value, str(self.link_input.value or ""))
        except tnupdate.TaskerNetError as error:
            self._notify(str(error), kind="negative")
            return
        self.link_input.set_value("")
        self._draw_links()
        await self.review(link)

    def find_links(self) -> None:
        """Open the Find Links dialog; what it links is drawn here when it is done."""
        # The one opened before is taken down first: a closed dialog stays in the page, and its buttons would
        # go on answering to a scan it is no longer showing.
        if self.find_dialog is not None:
            with contextlib.suppress(RuntimeError):
                self.find_dialog.delete()
        self.find_dialog = build_find_dialog(self.state, self.book, self._draw_links)
        if self.find_dialog is not None:
            self.find_dialog.open()

    async def _first_check(self) -> None:
        """Look for anything newer in links not checked lately, as the dialog opens."""
        if any(link.due for link in self.book.links.values()):
            await self._check(only_due=True)

    async def check_now(self) -> None:
        """Ask TaskerNet about every link, and say what it found."""
        waiting = await self._check(only_due=False, announce=True)
        if waiting is None:
            return
        problems = sum(1 for link in self.book.links.values() if link.problem)
        if waiting:
            self._notify(f"{waiting} {translate_string('linked share(s) have a newer version.')}", kind="info")
        elif problems:
            self._notify(translate_string("Some links could not be checked -- see the list."), kind="warning")
        else:
            self._notify(translate_string("Everything linked is up to date."), kind="positive")

    async def _check(self, *, only_due: bool, announce: bool = False) -> int | None:
        """Check the links off the event loop and redraw them.  The number with something newer, or None.

        `announce` puts a notice up for as long as TaskerNet is being asked, which is as long as its
        slowest answer or the timeout.  It is for the button the user pressed; the check made as the
        dialog opens runs quietly.
        """
        if self.held.busy:
            return None
        self.held.busy = True
        self.check_button.disable()
        pending = self._announce(translate_string("Asking TaskerNet.  Please stand by...")) if announce else None
        try:
            waiting = await run.io_bound(tnupdate.check_all, self.book, only_due=only_due)
        finally:
            self.held.busy = False
            self.check_button.enable()
            if pending is not None:
                pending.dismiss()
        self._draw_links()
        return waiting

    def _announce(self, message: str) -> ui.notification:
        """A notice with a spinner and no timeout, for something in progress; the caller dismisses it."""
        with self.dialog:
            return ui.notification(message, type="ongoing", spinner=True, timeout=None)

    # ##############################################################################
    # Reviewing.
    # ##############################################################################

    def _clear_review(self) -> None:
        """Put the review area back to empty, and take the buttons that act on it away."""
        self.held.review = None
        self.held.applied.clear()
        self.show_all.set_value(False)
        self.show_all.set_visibility(False)
        self.summary.set_text("")
        self.notes.clear()
        self.list_area.clear()
        self.clear_preview()
        self.accept_button.disable()
        self.latest_button.disable()
        self.report_button.disable()

    async def review(self, link: tnupdate.Link) -> None:
        """Fetch a share and set it beside the object it is linked to.

        Off the event loop -- a download and two or three parses -- by the Restore dialog's reason.
        A link reviewed for the first time is taken to be at what is published now: nothing says
        which version was imported, so the summary says what that means and the list shows how
        the copy compares.
        """
        if self.held.busy:
            return
        self.held.busy = True
        self._clear_review()
        self.summary.set_text(translate_string("Asking TaskerNet.  Please stand by..."))
        try:
            result = await run.io_bound(tnupdate.review, link, self.state, self.book)
        finally:
            self.held.busy = False
        if result is None:
            return
        held, problem = result
        if held is None:
            link.problem = problem
            self.book.save()
            self.summary.set_text("")
            self._draw_links()
            self._notify(problem, kind="negative")
            return
        first = not link.seen_ms
        if first:
            tnupdate.accept(self.book, held)
        self.book.save()
        self.held.review, self.held.first_review = held, first
        self._draw_links()
        self.accept_button.enable()
        self.latest_button.enable()
        self.report_button.enable()
        self._draw_review()

    def _draw_review(self) -> None:
        """The summary, the notes and the list of what can be taken."""
        held = self.held.review
        if held is None:
            return
        self.show_all.set_visibility(len(held.everything) > len(held.offer.candidates))
        self.summary.set_text(self._summary_text(held, first=self.held.first_review))
        self.notes.clear()
        with self.notes:
            for line in self._note_lines(held):
                ui.label(line).classes("text-xs text-gray-500")
        self._draw_list(held)

    def _summary_text(self, held: tnupdate.Review, *, first: bool) -> str:
        """What the review found, in a sentence."""
        published = tnupdate.describe_date(held.info.published_ms)
        author = held.author
        if author is not None and author.nothing:
            accepted = tnupdate.describe_date(held.link.seen_ms)
            return (
                f"{translate_string('The author has published nothing new since the version you accepted')} "
                f"({accepted}): {translate_string('the version published')} {published} "
                f"{translate_string('has the same content as it.')}"
            )
        if author is not None:
            return (
                f"{translate_string('The author changed')} {len(author.keys)} {translate_string('object(s) since the version you accepted')}"
                f" -- {len(held.offer.candidates)} {translate_string('can be taken here.')}"
            )
        lead = (
            f"{translate_string('Linked.  The version published')} {published} "
            f"{translate_string('is now the one MapTasker takes you to have.')}  "
            if first
            else f"{translate_string('No earlier version is on file.')}  "
        )
        return (
            f"{lead}{len(held.offer.candidates)} {translate_string('difference(s) from your copy are listed.')}"
            if held.offer.candidates
            else f"{lead}{translate_string('Your copy matches it.')}"
        )

    def _note_lines(self, held: tnupdate.Review) -> list[str]:
        """What is not offered, and why, so a short list does not read as a short comparison."""
        lines = []
        if held.everything:
            # xmldiff's lines read "older -> newer", and here the share is the older side.
            lines.append(translate_string("Each change reads: the author's version -> your copy."))
        if held.author is None and held.offer.candidates:
            lines.append(
                translate_string(
                    "With no earlier version to compare against, this lists everything that differs from your copy.  "
                    "Tasker rewrites some things when it imports a share, so not every difference is the author's.  "
                    "From the next update on, only what the author changed is listed.",
                ),
            )
        hidden = len(held.everything) - len(held.offer.candidates)
        if held.author is not None and hidden > 0:
            lines.append(
                f"{hidden} {translate_string('object(s) still differ from your copy, but not because of anything the author changed -- Tasker rewrites a share when it imports it, or you edited them.  Tick the box below to list them.')}",
            )
        if held.author is not None and held.author.removed:
            names = "; ".join(held.author.removed[:_NAMES_IN_NOTE])
            more = " ..." if len(held.author.removed) > _NAMES_IN_NOTE else ""
            lines.append(
                f"{translate_string('Removed by the author -- not offered; delete them in their own Edit dialogs')}: {names}{more}",
            )
        for reason, count in held.offer.left_out.items():
            if reason == maprestore.LEFT_OUT_PROJECT:
                lines.append(
                    f"{count} {translate_string('change(s) to the Project itself (its description or variables, say) are not offered one by one -- see Save Report.')}",
                )
            elif reason == maprestore.LEFT_OUT_ADDED:
                lines.append(
                    f"{count} {translate_string('object(s) exist only in your copy and are left alone.')}",
                )
        return lines

    def _redraw_list(self) -> None:
        """Draw the list again after the 'show every difference' box was ticked or cleared."""
        held = self.held.review
        if held is not None:
            self.clear_preview()
            self._draw_list(held)

    def _draw_list(self, held: tnupdate.Review) -> None:
        """The rows, each with its button.  Rows already taken stay, with a green button, until the next review."""
        self.list_area.clear()
        candidates = held.everything if self.show_all.value else held.offer.candidates
        offered = {candidate.identity for candidate in candidates}
        with self.list_area, ui.column().classes("w-full gap-0 p-1"):
            for identity, candidate in self.held.applied.items():
                if identity not in offered:
                    self._row(candidate, applied=True, finished=True)
            if not candidates and not self.held.applied:
                ui.label(translate_string("Nothing to take.")).classes("text-sm text-gray-500 italic p-2")
            for candidate in candidates[:_ROW_LIMIT]:
                self._row(candidate, applied=candidate.identity in self.held.applied)
            if len(candidates) > _ROW_LIMIT:
                ui.label(f"...{len(candidates) - _ROW_LIMIT} {translate_string('more.')}").classes(
                    "text-xs text-gray-500 italic mt-2",
                )

    def _row(self, candidate: maprestore.Candidate, *, applied: bool, finished: bool = False) -> None:
        """One object the author has, with 'Take this'."""
        draw_row(
            candidate,
            self.make_jump,
            self.show_preview,
            applied=applied,
            finished=finished,
            tag=_row_tag(candidate),
            button_label="Take this",
            detail_lines=_DETAIL_LINES,
        )

    # ##############################################################################
    # Previewing and taking.
    # ##############################################################################

    def clear_preview(self) -> None:
        """Throw the preview away and take Apply with it -- the Refactor dialog's one rule."""
        self.held.plan = None
        self.held.previewed = None
        self.preview_heading.set_text("")
        self.preview_area.clear()
        self.apply_button.disable()

    def show_preview(self, candidate: maprestore.Candidate) -> None:
        """Plan one row against the configuration as it is NOW, and draw it.

        Planned at the click, not when the list was drawn: another dialog can have edited since,
        and every check the plan makes -- is the id free, is the name taken -- is only true for a moment.
        """
        held = self.held.review
        if held is None:
            return
        plan = maprestore.plan_restore(candidate, held.shared, held.from_when, state=self.state)
        self.held.plan, self.held.previewed = plan, candidate
        self.preview_heading.set_text(translate_string("Preview -- nothing has changed yet"))
        draw_preview(self.preview_area, plan, self.make_jump)
        if plan.can_apply:
            self.apply_button.enable()
        else:
            self.apply_button.disable()

    async def do_apply(self) -> None:
        """Apply exactly the plan on screen.  One press of Undo takes it back."""
        plan, candidate = self.held.plan, self.held.previewed
        if plan is None or candidate is None:
            self._notify(translate_string("Press 'Take this' on a row first."), kind="warning")
            return
        done, errors = maprestore.restore(plan, state=self.state)
        for message in errors[:4]:
            self._notify(message, kind="negative")
        if not done:
            return
        self.held.applied[candidate.identity] = candidate
        self._notify(f"{plan.what}.  {translate_string('Undo is available.')}", kind="positive", position="top")
        await self.rebuild_after_apply()
        await self.rescan()

    def _listed(self, held: tnupdate.Review) -> list[maprestore.Candidate]:
        """The changes the list on screen shows -- the author's, or every difference when that box is ticked."""
        return list(held.everything if self.show_all.value else held.offer.candidates)

    async def accept_latest(self) -> None:
        """Take every change listed, in one go, and make the version published the one the user has.

        No preview and no Apply of its own: pressing the button IS the decision to take what the
        list shows, which is why the list is on screen before the button is enabled and why the
        button says in its tooltip what it takes.  What 'Take this' previews one object at a time is
        taken here together, and the way back is the same -- one press of Undo.
        """
        held = self.held.review
        if held is None:
            return
        changes = self._listed(held)
        if not changes:
            self.mark_current()
            return
        self.clear_preview()
        # On the event loop, as 'Take this' is: it changes the configuration, and the undo history
        # and the tables it rebuilds are not meant to be written from two threads.
        taken = tnupdate.accept_changes(changes, held, self.state)
        for line in taken.skipped[:4]:
            self._notify(line, kind="negative")
        if taken.done:
            self._notify(
                f"{taken.done} {translate_string('change(s) taken.  Undo is available.')}",
                kind="positive",
                position="top",
            )
            await self.rebuild_after_apply()
        if not taken.skipped:
            # All of it is in: the version published is now the one the user has.
            tnupdate.accept(self.book, held)
            self._draw_links()
        else:
            self._notify(
                translate_string("Some changes were skipped, so this version is not marked as the one you have."),
                kind="warning",
            )
        await self.rescan()

    async def rescan(self) -> None:
        """List again against the object as it now is -- after something was taken, or saved."""
        held = self.held.review
        if held is None:
            return
        self.clear_preview()
        after = await run.io_bound(tnupdate.rescan, held, self.state)
        if after is None:
            self._clear_review()
            self._draw_links()
            return
        self.held.review = after
        self._draw_review()

    def mark_current(self) -> None:
        """Take the version on screen as the one the user has."""
        held = self.held.review
        if held is None:
            return
        tnupdate.accept(self.book, held)
        self._draw_links()
        self._notify(translate_string("Marked as up to date."), kind="positive")

    async def save_report(self) -> None:
        """Write what the author changed and how the copy compares to a text file in the Output Folder."""
        held = self.held.review
        if held is None:
            return
        sections = []
        if held.author is not None:
            sections += ["WHAT THE AUTHOR CHANGED", held.author.report, ""]
        sections += ["HOW YOUR COPY COMPARES WITH THE PUBLISHED VERSION", held.report]
        path = await run.io_bound(diffload.write_comparison_report, "\n".join(sections), REPORT_FILE, state=self.state)
        if path:
            self._notify(f"{translate_string('Report saved as')} {path}", kind="positive")
        else:
            self._notify(translate_string("The report could not be saved."), kind="negative")

    async def do_save(self) -> None:
        """Write the whole configuration to a timestamped copy -- see guiwins_restore's own."""
        if await self.save_configuration():
            await self.rescan()


# ##################################################################################
# At startup.
# ##################################################################################


# Running checks, held so a task is not garbage-collected before it finishes.
_background: set[asyncio.Task] = set()


def check_links_at_startup() -> None:
    """Ask TaskerNet about the linked shares without holding up the window, and say if any has something newer.

    Called once as the GUI comes up, from the page's own build, so the page it will notify is the
    one current here.  With no links this does nothing at all -- no thread, no request -- so a user
    who has not used the feature never sees it.
    """
    book = tnupdate.default_book()
    if not book.links:
        return
    task = asyncio.create_task(_notify_if_newer(context.client, book))
    _background.add(task)
    task.add_done_callback(_background.discard)
    task.add_done_callback(_report_failure)


async def _notify_if_newer(client: Client, book: tnupdate.LinkBook) -> None:
    """Check on a worker thread (a request blocks until it answers or times out), then tell the user."""
    waiting = await run.io_bound(tnupdate.check_all, book, only_due=True)
    if not waiting:
        return
    with client:
        ui.notify(
            f"TaskerNet: {waiting} {translate_string('linked share(s) have a newer version.  Open TaskerNet Updates to see what changed.')}",
            type="info",
            timeout=20000,
            close_button=True,
        )


def _report_failure(task: asyncio.Task) -> None:
    """Log whatever the check raised instead of losing it.  Cancellation is ordinary and says nothing."""
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        logger.exception("Checking TaskerNet for updates failed", exc_info=error)
