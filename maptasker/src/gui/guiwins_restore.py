"""guiwins_restore: the Restore From History dialog -- one object at a time, with a preview."""

#! /usr/bin/env python3

#                                                                                        #
# guiwins_restore: where maprestore hangs off the GUI.                                   #
#                                                                                        #
# One dialog: pick a configuration from the history, see every Task, Profile and Scene   #
# it can restore -- the same rows Changes Since reports as REMOVED, CHANGED and RENAMED   #
# -- and press "Restore this" on one of them.  That shows the preview; Apply makes it.    #
#                                                                                        #
# ONE BUTTON PER ROW, NOT A TICK BOX PER ROW                                              #
#                                                                                        #
# The Fix Findings dialog has tick boxes and one Apply, because its repairs are           #
# independent of one another.  Restores are not: bringing a Task back can change what     #
# restoring the Profile that ran it will do (its link is found by name, and the Task may  #
# have come back under a new id -- see maprestore._resolve_links).  So each restore is    #
# planned against the configuration as the one before it LEFT it, which a batch applied  #
# from one preview cannot be.  One at a time is also the promise the feature makes: the  #
# Compare design put merging out of scope, and a Restore All button would be one.          #
#                                                                                        #
# THE RULE THIS IS BUILT AROUND is the Refactor dialog's: nothing is applied unseen.  A   #
# row's button builds a maprefac_model.Plan and draws its preview; Apply takes that plan and no  #
# other, and is only there while the preview is.  The preview is drawn from               #
# maprefac.report_rows -- the same rows the Refactor dialog draws, so a restore's         #
# refusal and warnings read exactly the way a Duplicate's do.                              #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from nicegui import run, ui

from maptasker.src.analysis import timecomp
from maptasker.src.analysis.diffload import current_configuration
from maptasker.src.core import timeline
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.mapops import maprefac, maprefac_model, maprestore

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from maptasker.src.analysis.xmldiff import Configuration
    from maptasker.src.core.mapjump import Target
    from maptasker.src.core.primitem import RunState

# How many rows are drawn.  Every row is a button and a link, and a history compared against
# a configuration it has little to do with can differ by hundreds of objects -- none of which
# anybody restores one at a time.  Reported rather than silently cut.
_ROW_LIMIT = 200

# How many detail lines a row shows under its location.  The report behind it can list every
# action that changed; the row is for recognising the object, and the preview says the rest.
_DETAIL_LINES = 3

_BLURB = (
    "Every Task, Profile and Scene that has been deleted or changed since the configuration you choose "
    "below.  'Restore this' shows exactly what bringing one back would do before anything happens, and "
    "each restore is one press of Undo.  One object at a time: restoring a Task does not relink the "
    "Profile that ran it -- the preview says what is left for you to do."
)

# Said above the list when the chosen configuration can restore nothing at all.  The usual
# reason is the one worth telling: the newest configuration in the history is the one that was
# loaded, and nothing has been edited since.
_NOTHING = (
    "Nothing in the configuration you have open was deleted or changed since then.  If you are looking for "
    "something older, choose an earlier configuration above."
)


@dataclass
class _State:
    """What the dialog is holding: which snapshot, its configuration, its rows, the plan on screen.

    One object rather than a nest of closures' locals, because every handler below reads and
    writes it -- and because the plan on screen is only valid for the configuration it was
    planned against, which is what `plan` living beside `older` makes plain.
    """

    snapshots: list[timeline.Snapshot] = field(default_factory=list)
    snapshot: timeline.Snapshot | None = None
    older: Configuration | None = None
    offer: maprestore.Offer | None = None
    plan: maprefac_model.Plan | None = None
    # The row whose plan is on screen, so Apply knows which row it restored.
    previewed: maprestore.Candidate | None = None
    # Rows restored from this snapshot, by identity -- their buttons are drawn green.  Kept here
    # because a restored object is usually no longer a difference, and the rescan after Apply
    # would otherwise drop the very row that was just pressed.
    applied: dict[tuple[str, str, str], maprestore.Candidate] = field(default_factory=dict)
    busy: bool = False

    def mark_applied(self) -> None:
        """Remember the row whose plan was just applied, so its button is drawn green."""
        if self.previewed is not None:
            self.applied[self.previewed.identity] = self.previewed


def build_restore_dialog(
    make_jump: Callable,
    rebuild_after_apply: Callable[[], Coroutine],
    save_configuration: Callable[[], Coroutine],
    state: RunState,
) -> ui.dialog | None:
    """Build and return the Restore From History dialog, or None if there is nothing to restore from.

    Takes what it needs from the view and nothing else -- how to follow a row to the object it
    names, how to bring the rest of the window up to date once something has changed, and how
    to write the configuration to a file -- for guiwins_fix's reason: this module is reached
    FROM guiwins, and reaching back into it would be a circular import.
    """
    if not state.tasker_root_elements.get("all_tasks"):
        ui.notify(translate_string("No XML file has been loaded.  Get an XML file first."), type="warning")
        return None

    held = _State(snapshots=list(reversed(timeline.snapshots())))
    if not held.snapshots:
        ui.notify(
            translate_string(
                "No configuration history has been recorded yet -- every file you load is kept from now on.",
            ),
            type="warning",
        )
        return None

    return _RestoreDialog(make_jump, rebuild_after_apply, save_configuration, state, held).build()


class _RestoreDialog:
    """The Restore From History dialog: its widgets, and the handlers that work on them.

    Every handler reads and writes the dialog's _State and draws into the same few widgets, so
    they are methods of one object rather than closures over a dozen locals.
    """

    def __init__(
        self,
        make_jump: Callable,
        rebuild_after_apply: Callable[[], Coroutine],
        save_configuration: Callable[[], Coroutine],
        state: RunState,
        held: _State,
    ) -> None:
        """
        Args:
            make_jump: How to follow a row to the object it names.
            rebuild_after_apply: How to bring the rest of the window up to date once something has changed.
            save_configuration: How to write the configuration to a file.
            state: The run's state.
            held: What the dialog is holding, which starts out as the snapshots in the history.
        """
        self.make_jump = make_jump
        self.rebuild_after_apply = rebuild_after_apply
        self.save_configuration = save_configuration
        self.state = state
        self.held = held
        self.dialog: ui.dialog
        self.choice: ui.select
        self.summary: ui.label
        self.left_out: ui.column
        self.list_area: ui.scroll_area
        self.preview_heading: ui.label
        self.preview_area: ui.scroll_area
        self.apply_button: ui.button

    def build(self) -> ui.dialog:
        """Draw the dialog, and start reading the newest configuration once it is on a page."""
        # `persistent`, by the Refactor and Fix Findings dialogs' rule: a dialog holding a preview
        # leaves on a button and nothing else.  The pulldown makes it acute -- Quasar renders a
        # select's popup outside the card, so the click that picks a configuration would otherwise
        # be the click that closes the dialog.
        with ui.dialog().props("persistent") as self.dialog, ui.card().classes("w-[1000px] max-w-full p-6"):
            ui.label(translate_string("Restore From History")).classes("text-lg font-bold text-blue-600")
            ui.label(translate_string(_BLURB)).classes("text-xs text-gray-500 italic mb-2 mt-1")

            self._build_choice()
            self.summary = ui.label("").classes("text-sm font-bold text-orange-500 mt-2")
            self.left_out = ui.column().classes("w-full gap-0")
            self.list_area = ui.scroll_area().classes("w-full h-[300px] border rounded dark:border-gray-700 mt-1")
            self.preview_heading = ui.label("").classes("text-sm font-bold text-blue-600 mt-3")
            self.preview_area = ui.scroll_area().classes("w-full h-[200px] border rounded dark:border-gray-700 mt-1")
            self._build_buttons()

            self.choice.on_value_change(lambda event: self.load(event.value or 0))
            # A timer rather than an await here: this function builds the dialog and returns it,
            # and the first read has to happen once the dialog is on a page to write into.
            ui.timer(0.1, lambda: self.load(0), once=True)

        return self.dialog

    def _build_choice(self) -> None:
        """The pulldown of configurations in the history, with its explanation underneath."""
        self.choice = ui.select(
            {position: snapshot.described() for position, snapshot in enumerate(self.held.snapshots)},
            value=0,
            label=translate_string("Restore from the configuration as it was on"),
        ).classes("w-full")
        # A line under the pulldown rather than a tooltip on it: a tooltip on a select opens as
        # the pointer reaches it and sits over the top of its own menu, hiding the newest --
        # most-wanted -- configurations behind the explanation of them.
        ui.label(
            translate_string(
                "Newest first.  The newest is usually the file you have open, so it holds anything deleted or "
                "edited this session; for something that was gone before you loaded this file, choose an "
                "earlier one.",
            ),
        ).classes("text-xs text-gray-500")

    def _build_buttons(self) -> None:
        """The row of buttons along the bottom: Apply, Cancel Preview, Save To Current File and Close."""
        with ui.row().classes("w-full justify-end mt-4 gap-2"):
            self.apply_button = ui.button(translate_string("Apply"), on_click=self.do_apply).classes("px-4")
            self.apply_button.props("color=orange")
            self.apply_button.disable()
            tip(
                self.apply_button,
                "Make the restore the preview describes, and nothing else.\n\n"
                "Greyed out until a row's 'Restore this' has drawn a preview that can be applied.\n\n"
                "One press of Undo afterwards puts the configuration back as it is now.\n\n",
            )
            ui.button(translate_string("Cancel Preview"), on_click=self.clear_preview).props("outline")
            tip(
                ui.button(translate_string("Save To Current File"), color="green", on_click=self.do_save).classes(
                    "text-white px-4",
                ),
                "Write the whole configuration -- what you have restored and every other edit made this "
                "session -- to a new, timestamped copy of the file you loaded.  The file you loaded is never "
                "written to.\n\n"
                "Until you press this, a restore exists only in memory and is lost on exit.\n\n",
            )
            ui.button(translate_string("Close"), on_click=self.dialog.close).props("color=red").classes(
                "text-white px-4",
            )

    def clear_preview(self) -> None:
        """Throw the preview away and take Apply with it -- the Refactor dialog's one rule."""
        self.held.plan = None
        self.held.previewed = None
        self.preview_heading.set_text("")
        self.preview_area.clear()
        self.apply_button.disable()

    def show_preview(self, candidate: maprestore.Candidate) -> None:
        """Plan one row's restore against the configuration as it is NOW, and draw it.

        Planned at the click, not when the list was drawn: another dialog can have edited
        since, and every check the plan makes -- is the id free, is the name taken, is the
        Project here -- is only true for a moment.
        """
        held = self.held
        if held.older is None or held.snapshot is None:
            return
        plan = maprestore.plan_restore(candidate, held.older, held.snapshot.described(), state=self.state)
        held.plan = plan
        held.previewed = candidate
        self.preview_heading.set_text(translate_string("Preview -- nothing has changed yet"))
        draw_preview(self.preview_area, plan, self.make_jump)
        if plan.can_apply:
            self.apply_button.enable()
        else:
            self.apply_button.disable()

    async def load(self, position: int) -> None:
        """Read the chosen configuration from the history and list what it can restore.

        Off the event loop: expanding and parsing a snapshot is megabytes of work, the same
        reason Changes Since does it there.
        """
        held = self.held
        if held.busy:
            return
        held.busy = True
        self.clear_preview()
        held.snapshot = held.snapshots[position]
        # What was restored is only true of the snapshot it was restored from.
        held.applied.clear()
        self.summary.set_text(translate_string("Reading that configuration..."))
        self.list_area.clear()
        self.left_out.clear()
        try:
            result = await run.io_bound(_read, held.snapshot, state=self.state)
        finally:
            held.busy = False
        # None from nicegui means the wait was cancelled or the app is stopping.
        if result is None:
            return
        older, offer, problem = result
        if problem:
            self.summary.set_text("")
            ui.notify(translate_string(problem), type="negative")
            return
        if older is None or offer is None:
            return
        held.older, held.offer = older, offer
        self._draw_list(offer)

    async def rescan(self) -> None:
        """List again against the configuration as it now is -- after a restore, or a save."""
        held = self.held
        if held.older is None:
            await self.load(self.choice.value or 0)
            return
        self.clear_preview()
        offer = await run.io_bound(
            maprestore.candidates, held.older, current_configuration(state=self.state), state=self.state
        )
        if offer is None:
            return
        held.offer = offer
        self._draw_list(offer)

    def _draw_list(self, offer: maprestore.Offer) -> None:
        """Draw the rows the offer lists, each with a button that previews its restore."""
        _draw_list(
            self.list_area,
            self.left_out,
            self.summary,
            offer,
            self.held.applied,
            self.make_jump,
            self.show_preview,
        )

    async def do_apply(self) -> None:
        """Apply exactly the plan on screen.  One press of Undo takes it back."""
        plan = self.held.plan
        if plan is None:
            ui.notify(translate_string("Press 'Restore this' on a row first."), type="warning")
            return
        done, errors = maprestore.restore(plan, state=self.state)
        for message in errors[:4]:
            ui.notify(message, type="negative")
        if not done:
            return
        self.held.mark_applied()
        ui.notify(f"{plan.what}.  {translate_string('Undo is available.')}", type="positive", position="top")
        await self.rebuild_after_apply()
        await self.rescan()

    async def do_save(self) -> None:
        """Write the whole configuration to a timestamped copy -- see guiwins_fix's own.

        Rescanned afterwards, and it must be: the switch to the saved copy reloads the whole
        configuration.  The snapshot being read is untouched by that, so it stays chosen.
        """
        if await self.save_configuration():
            await self.rescan()


def _read(snapshot: timeline.Snapshot, state: RunState) -> tuple[Configuration | None, maprestore.Offer | None, str]:
    """Read one snapshot and list what it can restore.  (configuration, offer, problem)."""
    older, problem = timecomp.configuration_of(snapshot, state=state)
    if older is None:
        return None, None, problem
    return older, maprestore.candidates(older, current_configuration(state=state), state=state), ""


# ##################################################################################
# Drawing.
# ##################################################################################


def _draw_list(
    area: ui.scroll_area,
    left_out: ui.column,
    summary: ui.label,
    offer: maprestore.Offer,
    applied: dict[tuple[str, str, str], maprestore.Candidate],
    make_jump: Callable,
    on_restore: Callable[[maprestore.Candidate], None],
) -> None:
    """The rows, each with its button, and a line for everything deliberately not offered.

    Rows already restored keep their place on screen with a green button.  Those the rescan no
    longer offers -- the usual case, since a restored object has nothing left to restore -- are
    drawn first, and their button is disabled: pressing it again would plan the same restore
    against a configuration that already has it.
    """
    area.clear()
    left_out.clear()

    brought = sum(1 for c in offer.candidates if c.action == maprestore.BRING_BACK)
    reverted = len(offer.candidates) - brought
    summary.set_text(
        f"{brought} {translate_string('deleted since, to bring back')} -- "
        f"{reverted} {translate_string('changed since, to put back')}",
    )

    # What is not offered, and why, so a short list does not read as a short comparison.
    with left_out:
        for reason, count in offer.left_out.items():
            ui.label(f"{count} {translate_string('not offered')}: {translate_string(reason)}").classes(
                "text-xs text-gray-500",
            )

    offered = {candidate.identity for candidate in offer.candidates}
    with area, ui.column().classes("w-full gap-0 p-1"):
        for identity, candidate in applied.items():
            if identity not in offered:
                draw_row(candidate, make_jump, on_restore, applied=True, finished=True)
        if offer.is_empty:
            ui.label(translate_string(_NOTHING)).classes("text-sm text-gray-500 italic p-2")
            return
        for candidate in offer.candidates[:_ROW_LIMIT]:
            draw_row(candidate, make_jump, on_restore, applied=candidate.identity in applied)
        if len(offer.candidates) > _ROW_LIMIT:
            ui.label(
                f"...{len(offer.candidates) - _ROW_LIMIT} {translate_string('more.  Choose a more recent configuration.')}",
            ).classes("text-xs text-gray-500 italic mt-2")


def draw_row(
    candidate: maprestore.Candidate,
    make_jump: Callable,
    on_restore: Callable[[maprestore.Candidate], None],
    *,
    applied: bool = False,
    finished: bool = False,
    tag: str | None = None,
    button_label: str = "Restore this",
    detail_lines: int = _DETAIL_LINES,
) -> None:
    """One object: its tag, where it is (a link, when it is here to go to), and 'Restore this'.

    `applied` draws the button green, for a row whose restore has been applied; `finished`
    also disables it, for one that has nothing left to restore.  `tag`, `button_label` and `detail_lines` are
    for the other dialog that draws these rows -- TaskerNet Updates, where "removed" would be
    the wrong word for something the author added -- and default to this dialog's own.
    """
    # min-w-0 and break-all are what keep the button on screen.  A flex child will not shrink
    # below its content's width unless told it may, and a detail line holding one long unbroken
    # string -- a URL, a JSON layout -- is wider than the dialog: without these the text column
    # grows past the edge and pushes 'Restore this' out of sight on exactly the rows that have
    # the most to say.  Measured on a real history, where it hid every button in the list.
    with ui.row().classes("w-full items-start gap-2 border-b dark:border-gray-700 py-1 px-2 no-wrap"):
        with ui.column().classes("flex-1 min-w-0 gap-0"):
            with ui.row().classes("items-baseline gap-2 min-w-0"):
                ui.label(tag or candidate.tag).classes("font-mono text-xs font-bold text-orange-500 shrink-0")
                if candidate.target is not None:
                    ui.link(candidate.where, "#").on("click", make_jump(candidate.target)).classes(
                        "text-blue-600 dark:text-blue-400 font-mono text-sm decoration-dotted hover:underline "
                        "break-all min-w-0",
                    )
                else:
                    ui.label(candidate.where).classes("font-mono text-sm break-all min-w-0")
            for detail in candidate.details[:detail_lines]:
                ui.label(detail).classes("text-xs text-gray-600 dark:text-gray-300 font-mono pl-4 break-all")
            if len(candidate.details) > detail_lines:
                ui.label(
                    f"...{len(candidate.details) - detail_lines} {translate_string('more -- the preview lists them all')}",
                ).classes("text-xs text-gray-500 italic pl-4")
        button = ui.button(translate_string(button_label), on_click=lambda: on_restore(candidate)).classes(
            "shrink-0",
        )
        button.props("dense color=green" if applied else "dense outline")
        if finished:
            button.disable()


def draw_preview(
    area: ui.scroll_area,
    plan: maprefac_model.Plan,
    make_jump: Callable[[Target], Callable[[], Coroutine[Any, Any, None]]],
) -> None:
    """The plan, from maprefac.report_rows -- the same rows the Refactor dialog draws."""
    area.clear()
    with area, ui.column().classes("w-full gap-0 p-2"):
        for row in maprefac.report_rows(plan):
            if row.target is not None:
                ui.link(row.text, "#").on("click", make_jump(row.target)).classes(
                    "text-blue-600 dark:text-blue-400 font-mono text-xs whitespace-pre decoration-dotted hover:underline",
                )
            else:
                ui.label(row.text).classes("font-mono text-xs whitespace-pre " + _row_classes(row.text))


def _row_classes(text: str) -> str:
    """How one preview line is coloured, from what it says -- guiwins_refactor's rule."""
    if text.startswith("CANNOT BE DONE"):
        return "font-bold text-red-500"
    if text.startswith("BEFORE YOU DO THIS"):
        return "font-bold text-orange-600 dark:text-orange-400"
    if text.startswith("WHAT WILL HAPPEN"):
        return "font-bold text-green-600 dark:text-green-400"
    return "text-gray-700 dark:text-gray-300"


def tip(element: ui.element, text: str) -> ui.element:
    """Attach one of this dialog's tooltips; pre-wrap keeps its blank lines (see guiwins_fix._tip)."""
    with element:
        ui.tooltip(translate_string(text)).style("white-space: pre-wrap")
    return element
