"""guiwins_fix: the Fix Findings dialog -- the repairs the Health Check can make itself."""

#! /usr/bin/env python3

#                                                                                        #
# guiwins_fix: where mapfix hangs off the GUI.                                           #
#                                                                                        #
# One dialog, one list.  Every Health Check finding this program knows how to repair,     #
# with a tick box, what the field holds now, what it will hold, and -- for the three that #
# need a decision -- the decision.                                                        #
#                                                                                        #
# THE RULE THIS IS BUILT AROUND is the Replace tab's and the Refactor dialog's: nothing   #
# is applied unseen.  Here it is structural rather than remembered, because there are no  #
# input fields to go stale: the list on screen IS the plan, the tick boxes and the        #
# pulldowns write straight onto it, and Apply takes that object and no other.  There is   #
# no arrangement of clicks that reaches mapfix.apply with a plan the user has not been    #
# looking at.                                                                             #
#                                                                                        #
# WHY THE LIST IS WIDGETS AND THE SAVED FILE IS Rows                                      #
#                                                                                        #
# The Refactor dialog draws its preview from maprefac's own Rows, and says why: laying    #
# the same thing out twice is how the file and the screen come to disagree.  That         #
# argument does not reach this list, for the Replace tab's reason -- a row here is not a  #
# line of text, it is a tick box and a pulldown, and a Row cannot be either.  So the list #
# is built here and Save Preview writes mapfix.report_rows, which is the same content in  #
# the one shape a file can hold.                                                          #
#                                                                                        #
# WHY THE SCAN RUNS ON OPEN                                                               #
#                                                                                        #
# Because there is nothing to ask first.  The Refactor dialog opens empty because it has  #
# to be told a Task and a range of actions before it has anything to say; this one is     #
# answering a question the user has already asked by pressing the button.  A dialog that  #
# opened empty with a Scan button in it would be one click of ceremony in front of the    #
# only thing it does.  The scan is much cheaper than a full Health Check -- mapfix leaves #
# every category it cannot repair out of it, so the secrets and variables walks over the  #
# configuration do not happen at all.                                                     #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from nicegui import ui

from maptasker.src.core.maputil2 import translate_string
from maptasker.src.mapops import mapfix

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from maptasker.src.core.primitem import RunState

# How many repairs and skips are drawn.  mapfix caps the plan itself (see its _PLAN_LIMIT),
# so these are the second guard rather than the first: a list of several hundred widgets is
# slow to build and nobody reads past the top of it either way.
_FIX_LIMIT = 300
_SKIP_LIMIT = 40

# What the dialog says about itself, under the heading.  The last sentence is the important
# one: this repairs a handful of the forty-five kinds of finding and must not be mistaken
# for repairing the report.
_BLURB = (
    "Every Health Check finding this program knows how to repair, with what it would do to each.  "
    "Tick the ones you want and press Apply -- however many that is, it is one press of Undo "
    "afterwards.  Most kinds of finding are not here: a broken 'Perform Task' or a password in an "
    "action is a decision only you can make, and guessing at one would be worse than reporting it."
)

# What the first step says: which kinds of finding to look at before any of them is listed.
_CHOOSER_BLURB = (
    "Choose which kinds of finding to fix.  Only the kinds ticked are scanned for and listed, so the "
    "next step is as long as you want it to be.  A kind with nothing to fix cannot be ticked."
)

# Said on the one control that arrives with nothing chosen, next to the thing that would
# make its row tickable rather than only in the greyed-out tick box beside it.
_UNDECIDED_TIP = (
    "Nothing is chosen for this one, and nothing will be guessed: a 'Goto' sent to the wrong "
    "label does not fail, it runs the wrong half of the Task."
)


@dataclass
class _Screen:
    """Everything the drawing below writes to, gathered so it can be passed in one argument.

    The list is redrawn whole on every scan and on every Tick All, and each of its rows
    needs three things that belong to the dialog rather than to the row: where to put the
    widgets, how to follow a link, and how to report that a box has been ticked.  Passing
    those separately down four levels is what made this one function too long to read, and
    a dataclass is cheaper than the closure that was there before.

    `lines` is the "fix:" label of each row, kept so that a changed decision can rewrite its
    own line rather than the whole list being redrawn under the user's pointer.
    """

    area: ui.scroll_area
    summary: ui.label
    jump: Callable  # (Target) -> click handler
    tick: Callable  # (plan, position) -> change handler
    choose: Callable  # (plan, position, checkbox) -> change handler
    lines: dict[int, ui.label] = field(default_factory=dict)


def build_fix_dialog(
    title: str,
    make_jump: Callable,
    rebuild_after_apply: Callable[[], Coroutine],
    save_configuration: Callable[[], Coroutine],
    state: RunState,
) -> ui.dialog | None:
    """Build and return the Fix Findings dialog, or None if there is nothing loaded to scan.

    Takes the four things it needs from the view and nothing else -- what the view is called,
    how to follow a row to the object it names, how to bring the rest of the window up to
    date once something has changed, and how to write the configuration to a file.  Passed
    in rather than imported, for guiwins_refactor's reason: this module is reached FROM
    guiwins, and reaching back into it would be a circular import for four functions' worth
    of behaviour.

    `save_configuration` returns whether the list has to be rebuilt afterwards; it reports
    its own outcome to the user, because what there is to say about a save is not something
    this module knows (see userintr.fix_findings_event, which has all three answers).
    """
    if not state.tasker_root_elements.get("all_tasks"):
        ui.notify(translate_string("No XML file has been loaded.  Get an XML file first."), type="warning")
        return None

    return _FixDialog(title, make_jump, rebuild_after_apply, save_configuration, state).build()


class _FixDialog:
    """The Fix Findings dialog: the plan on screen, its widgets, and the handlers that work on them.

    Every handler reads and writes the same plan and the same summary line, so they are methods
    of one object rather than closures over a handful of locals.
    """

    def __init__(
        self,
        title: str,
        make_jump: Callable,
        rebuild_after_apply: Callable[[], Coroutine],
        save_configuration: Callable[[], Coroutine],
        state: RunState,
    ) -> None:
        """
        Args:
            title: What the view this was opened from is called, or "" from the main window.
            make_jump: How to follow a row to the object it names.
            rebuild_after_apply: How to bring the rest of the window up to date once something has changed.
            save_configuration: How to write the configuration to a file; returns whether to rescan.
            state: The run's state.
        """
        self.title = title
        self.make_jump = make_jump
        self.rebuild_after_apply = rebuild_after_apply
        self.save_configuration = save_configuration
        self.state = state
        # The plan on screen.  Held in a dict rather than as an attribute of its own because
        # it cannot be remembered on the view between openings: it closes over live elements,
        # and holding one across a reopen is exactly the stale-handle case mapfix.apply's
        # attachment check exists to catch.
        self.held: dict = {"plan": None}
        # The kinds of finding the user has chosen to fix.  Everything to begin with: the
        # first step shows them all ticked, so pressing Continue is the same as the single
        # list this dialog used to open on.
        self.categories: set[str] = set(mapfix.FIXABLE_TAGS)
        self.boxes: dict[str, ui.checkbox] = {}
        # The buttons that only mean something when there is a kind to choose.
        self.choice_buttons: list[ui.button] = []
        self.dialog: ui.dialog
        self.summary: ui.label
        self.screen: _Screen
        self.chooser_view: ui.column
        self.chooser_area: ui.scroll_area
        self.list_view: ui.column
        self.chosen_label: ui.label

    def build(self) -> ui.dialog:
        """Draw the dialog, which opens on the choice of what to fix, and nothing is scanned for until it is made."""
        # `persistent`, by the same rule as the Refactor and Find/Replace dialogs: a dialog
        # holding work in progress or asking for a decision leaves on a button and nothing else.
        # A list of half-made choices is both, and the pulldowns make it acute -- Quasar renders
        # a select's popup OUTSIDE the card, so the click that picks a label would otherwise be
        # the click that throws away every tick on the list.
        with ui.dialog().props("persistent") as self.dialog, ui.card().classes("w-[1000px] max-w-full p-6"):
            title = self.title
            heading = f"{translate_string('Fix Findings')} -- {title}" if title else translate_string("Fix Findings")
            ui.label(heading).classes("text-lg font-bold text-blue-600")

            # Two steps in one card, one shown at a time.  The same dialog rather than a
            # prompt in front of it, so there is one thing to close and one place the
            # user's choices live -- and the list can send them back for another go.
            self.chooser_view = ui.column().classes("w-full gap-1")
            self.list_view = ui.column().classes("w-full gap-1")

            with self.chooser_view:
                self._build_chooser()

            with self.list_view:
                ui.label(translate_string(_BLURB)).classes("text-xs text-gray-500 italic mb-2 mt-1")
                self.chosen_label = ui.label("").classes("text-xs text-gray-500 font-mono")
                self.summary = ui.label("").classes("text-sm font-bold text-orange-500")
                list_area = ui.scroll_area().classes("w-full h-[460px] border rounded dark:border-gray-700 mt-1")
                self.screen = _Screen(
                    area=list_area,
                    summary=self.summary,
                    jump=self.make_jump,
                    tick=self.ticker,
                    choose=self.chooser,
                )

                _build_buttons(
                    self.dialog,
                    {
                        "categories": self.show_chooser,
                        "tick_all": lambda: self.set_all(ticked=True),
                        "tick_none": lambda: self.set_all(ticked=False),
                        "rescan": lambda: self.scan(restore=True),
                        "apply": self.do_apply,
                        "save_file": self.do_save,
                        "save": lambda: _save_preview(self.held["plan"], self.state),
                    },
                )

            self.show_chooser()

        return self.dialog

    def _build_chooser(self) -> None:
        """The first step's frame: what it asks, where the kinds are listed, and its buttons."""
        ui.label(translate_string(_CHOOSER_BLURB)).classes("text-xs text-gray-500 italic mb-2 mt-1")
        self.chooser_area = ui.scroll_area().classes("w-full h-[320px] border rounded dark:border-gray-700 mt-1")
        with ui.row().classes("w-full justify-end mt-4 gap-2"):
            self.choice_buttons = [
                ui.button(translate_string("Select All"), on_click=lambda: self.set_all_categories(ticked=True)).props(
                    "outline",
                ),
                ui.button(
                    translate_string("Deselect All"), on_click=lambda: self.set_all_categories(ticked=False)
                ).props("outline"),
                ui.button(translate_string("Continue"), on_click=self.choose_categories).classes(
                    "bg-blue-600 text-white px-4"
                ),
            ]
            ui.button(translate_string("Cancel"), on_click=self.dialog.close).classes("bg-red-500 text-white px-4")

    def show_chooser(self) -> None:
        """Show the choice of what to fix, counted afresh: the configuration may have changed since it was last shown."""
        skip = self.state.program_arguments.health_check_skip or []
        counts = mapfix.count_findings(skip, state=self.state)

        excluded = [tag for tag in mapfix.FIXABLE_TAGS if tag in skip]
        nothing_to_fix = not any(counts.get(tag) for tag in mapfix.FIXABLE_TAGS if tag not in skip)

        self.boxes.clear()
        self.chooser_area.clear()
        with self.chooser_area, ui.column().classes("w-full gap-1 p-1"):
            if nothing_to_fix:
                ui.label(translate_string("There is nothing to fix.")).classes("text-sm font-bold text-orange-500 ml-2")
            if excluded:
                ui.label(
                    f"{translate_string('Excluded by the Health Check settings, and so unavailable')}: "
                    f"{', '.join(excluded)}",
                ).classes("text-xs text-gray-500 ml-2 mb-1")
            # With nothing found there is nothing to tick: only the excluded kinds are listed, so
            # that the user can see which of them is why a kind they expected is missing.
            for tag in mapfix.FIXABLE_TAGS:
                if not nothing_to_fix or tag in skip:
                    self._draw_category(tag, counts.get(tag), tag in skip)

        # Nothing to choose from means nothing to select, deselect or continue with.
        for button in self.choice_buttons:
            button.set_enabled(not nothing_to_fix)

        self.list_view.set_visibility(False)
        self.chooser_view.set_visibility(True)

    def _draw_category(self, tag: str, count: int | None, skipped: bool) -> None:
        """One kind of finding: a tick box, its tag, how many there are, and what fixing one does.

        The tag is what the Health Check report and this dialog's list print, so "the NO-TIMEOUT
        ones" is the same group in all three.  A kind with nothing to fix, or one the Health
        Check has been told to leave out, cannot be ticked: it could only produce an empty list.
        """
        available = bool(count) and not skipped
        with ui.row().classes("items-center gap-2 ml-2 no-wrap"):
            box = ui.checkbox(value=available and tag in self.categories).props("dense")
            if not available:
                box.disable()
            self.boxes[tag] = box
            with ui.column().classes("gap-0"):
                with ui.row().classes("items-baseline gap-2"):
                    ui.label(tag).classes("font-mono text-xs font-bold text-orange-500")
                    if skipped:
                        note = translate_string("left out of the Health Check")
                    else:
                        note = f"{count} {translate_string('found')}" if count else translate_string("none found")
                    ui.label(note).classes("text-xs text-gray-400")
                ui.label(translate_string(mapfix.WHAT_IT_DOES.get(tag, ""))).classes("text-xs text-gray-500")

    def set_all_categories(self, *, ticked: bool) -> None:
        """Tick or untick every kind that has something to fix."""
        for box in self.boxes.values():
            if box.enabled:
                box.value = ticked

    def choose_categories(self) -> None:
        """Continue: remember which kinds are ticked, and scan for those and no others."""
        chosen = {tag for tag, box in self.boxes.items() if box.value}
        if not chosen:
            ui.notify(translate_string("Tick at least one kind of finding first."), type="warning")
            return
        self.categories = chosen
        # In the order the list groups them, not the order they were ticked in.
        self.chosen_label.set_text(
            f"{translate_string('Fixing')}: {', '.join(tag for tag in mapfix.FIXABLE_TAGS if tag in chosen)}",
        )
        self.chooser_view.set_visibility(False)
        self.list_view.set_visibility(True)
        # Ticks and decisions already made on an earlier list come back for the findings that are still there.
        self.scan(restore=self.held["plan"] is not None)

    def ticker(self, plan: mapfix.Plan, position: int) -> Callable:
        """One row's tick box: put this repair in or out of what Apply makes.

        A factory rather than a lambda built in the loop, for the usual reason: a lambda
        would close over the loop variable and every box would tick the last row.
        """

        def ticked(event: object) -> None:
            if getattr(event, "value", False):
                plan.selected.add(position)
            else:
                plan.selected.discard(position)
            self.summary.set_text(_summary_text(plan))

        return ticked

    def chooser(self, plan: mapfix.Plan, position: int, box: ui.checkbox) -> Callable:
        """One row's decision: remember it, and let the repair be ticked once it is made.

        The tick box starts disabled for a repair whose Choice has no default -- which
        label a broken 'Goto' was meant to name -- so the one decision nobody can make
        for the user is one the dialog cannot be clicked past.  mapfix.apply refuses an
        undecided repair as well; this is the half that stops it being offered.
        """

        def chosen(event: object) -> None:
            raw = getattr(event, "value", "") or ""
            # A number box hands back a float whatever its format string says, so "60"
            # arrives as 60.0.  Canonicalised on the way in so that what is stored, what
            # the line below says, and what gets written are one number -- see
            # mapfix.whole_seconds, which is tolerant of it either way.
            plan.chosen[position] = mapfix.whole_seconds(str(raw)) if isinstance(raw, (int, float)) else str(raw)
            if plan.is_ready(position):
                box.enable()
            else:
                box.disable()
                box.value = False
                plan.selected.discard(position)
            self.screen.lines[position].set_text(plan.describe(position))
            self.summary.set_text(_summary_text(plan))

        return chosen

    def scan(self, *, restore: bool = False) -> None:
        """Run the scan and show what it found.

        `restore` carries the user's ticks and decisions across a rescan, by what they
        point at rather than by where they sat -- see mapfix.Fix.identity.  Without it,
        a rescan after editing something in another window would throw away every choice
        already made, which is the work this dialog exists to collect.
        """
        previous = self.held["plan"] if restore else None
        ticks = previous.ticked_identities() if previous is not None else set()
        values = (
            {previous.fixes[position].identity: value for position, value in previous.chosen.items()}
            if previous is not None
            else {}
        )

        plan = mapfix.plan_fixes(
            self.state.program_arguments.health_check_skip or [],
            only=self.categories,
            state=self.state,
        )
        if previous is not None:
            plan.restore(ticks, values)
        self.held["plan"] = plan
        _draw(plan, self.screen)

    def set_all(self, *, ticked: bool) -> None:
        """Tick or untick every repair that CAN be ticked, and redraw.

        "That can be" is the whole of the difference from a plain select-all: a repair
        waiting on a decision stays out, because ticking it would be ticking something
        nobody has decided.
        """
        plan = self.held["plan"]
        if plan is None:
            return
        plan.selected = (
            {position for position in range(len(plan.fixes)) if plan.is_ready(position)} if ticked else set()
        )
        _draw(plan, self.screen)

    async def do_apply(self) -> None:
        """The Apply button.  Makes exactly the repairs ticked on screen.

        The list is rebuilt afterwards rather than the dialog closed: repairing eight
        findings out of thirty is the ordinary way this gets used, and somebody who has
        just done the eight easy ones should find the other twenty-two still in front of
        them -- with the repaired ones gone, because the scan is run again.
        """
        plan = self.held["plan"]
        if plan is None or not plan.selected:
            ui.notify(translate_string("Tick something first."), type="warning")
            return

        repaired, errors = mapfix.apply(plan, state=self.state)
        for message in errors[:4]:
            ui.notify(message, type="negative")
        if len(errors) > 4:
            ui.notify(
                f"{len(errors) - 4} {translate_string('more problems -- see the log.')}",
                type="negative",
            )

        if repaired:
            ui.notify(
                f"{repaired} {translate_string('repaired.')} {translate_string('Undo is available.')}",
                type="positive",
                position="top",
            )
            # The rest of the window first: a repair can delete a Task, so an option list
            # built before one offers names that no longer resolve -- the same reason Undo
            # and Redo refresh them.
            await self.rebuild_after_apply()

        # Ticks are NOT carried over.  What was just applied is gone from the new scan and
        # anything that failed is still there, so a restored tick would be a tick on a
        # repair that has already been tried and did not work.
        self.scan()

    async def do_save(self) -> None:
        """The Save button: write the repairs -- and every other edit this session -- to a file.

        HERE BECAUSE THE REPAIRS ARE IN MEMORY AND NOTHING ELSE ON THIS SCREEN SAYS SO.
        Apply changes the loaded configuration and no file, the same way every Edit dialog's
        Ok does; without this the only way to get eight ticked repairs onto disk was to open
        an editor on some unrelated object and press its own Save To Current File, which is
        a strange place to have to go for the result of a press made here.

        The list is rebuilt when the save reports it should be, and it must be: the switch
        to the saved copy reloads the whole configuration, so every element the plan is
        holding belongs to a tree nothing renders from any more.  Ticks and choices are
        carried across by identity, so repairs decided and not yet applied survive it.
        """
        if await self.save_configuration():
            self.scan(restore=True)


# ##################################################################################
# Drawing the list.
#
# Module level rather than nested in the dialog, and taking a _Screen: the dialog was one
# function holding six of these, which is exactly the shape nobody can read.  Nothing here
# reaches back into it -- what a row needs from the dialog travels on the _Screen.
# ##################################################################################
def _summary_text(plan: mapfix.Plan) -> str:
    """The line above the list: what is on offer and how much of it is ticked."""
    if plan.is_empty:
        return translate_string("Nothing here can be repaired automatically.")
    return f"{plan.tally()} {translate_string('ticked')}, {len(plan.fixes)} {translate_string('offered')}"


def _draw(plan: mapfix.Plan, screen: _Screen) -> None:
    """Draw the plan: warnings, then what cannot be repaired, then what can.

    Skips before repairs, for mapswap's reason: they are the part the user must read and
    the part they will not scroll back up for.  Every location is a link, because the only
    way to judge "should this Task really be deleted" is to go and look at it -- and that
    is the whole reason these rows are clickable.
    """
    screen.area.clear()
    screen.lines.clear()
    screen.summary.set_text(_summary_text(plan))

    with screen.area, ui.column().classes("w-full gap-1 p-1"):
        for warning in plan.warnings:
            ui.label(warning).classes(
                "text-xs text-orange-600 dark:text-orange-400 border-l-4 border-orange-400 pl-2 py-1",
            )

        _draw_skips(plan, screen)

        if plan.is_empty:
            ui.label(
                translate_string(
                    "Nothing in this configuration can be repaired from here.  Run the Health Check "
                    "itself to see everything else it has to say.",
                ),
            ).classes("text-sm text-gray-500 italic mt-3")
            return

        current_tag = ""
        for position, fix in enumerate(plan.fixes[:_FIX_LIMIT]):
            if fix.tag != current_tag:
                current_tag = fix.tag
                _draw_group_heading(fix.tag)
            _draw_fix(plan, position, fix, screen)

        if len(plan.fixes) > _FIX_LIMIT:
            ui.label(
                f"...{len(plan.fixes) - _FIX_LIMIT} {translate_string('more -- apply these, then scan again')}",
            ).classes("text-xs text-gray-500 italic mt-2")


def _draw_skips(plan: mapfix.Plan, screen: _Screen) -> None:
    """The findings this program knows how to repair and cannot repair here, with the reason.

    Printed rather than dropped: a silent skip is the worst outcome this feature can
    produce, because the user reads "6 repaired", believes the check is that much shorter
    now, and the two it could not touch are the two still waiting.
    """
    if not plan.skips:
        return

    ui.label(f"{translate_string('Cannot be repaired here')} ({len(plan.skips)})").classes(
        "text-xs font-bold text-red-500 mt-2",
    )
    for skip in plan.skips[:_SKIP_LIMIT]:
        with ui.column().classes("w-full gap-0 pl-2 pb-1"):
            ui.link(f"[{skip.tag}]  {skip.where.label}", "#").on("click", screen.jump(skip.where)).classes(
                "text-blue-600 dark:text-blue-400 font-mono text-xs decoration-dotted hover:underline",
            )
            ui.label(skip.explanation).classes("text-xs text-gray-500")
    if len(plan.skips) > _SKIP_LIMIT:
        ui.label(f"...{len(plan.skips) - _SKIP_LIMIT} {translate_string('more')}").classes(
            "text-xs text-gray-500 italic pl-2",
        )


def _draw_group_heading(tag: str) -> None:
    """The tag, and what a repair of it does.

    The tag is the heading because the tag is the word the Health Check report prints in
    brackets in front of every finding -- so "the six NO-TIMEOUT ones" is a group here as
    well as there, without the user having to learn a second vocabulary for the same thing.
    """
    with ui.row().classes("w-full items-baseline gap-2 mt-3"):
        ui.label(tag).classes("font-mono text-xs font-bold text-orange-500")
        ui.label(translate_string(mapfix.WHAT_IT_DOES.get(tag, ""))).classes("text-xs text-gray-500")


def _draw_fix(plan: mapfix.Plan, position: int, fix: mapfix.Fix, screen: _Screen) -> None:
    """One repair: tick box, where it is, what is there now, and what it will become."""
    with ui.column().classes("w-full gap-0 border-b dark:border-gray-700 pb-1"):
        with ui.row().classes("w-full items-baseline gap-2 px-2"):
            box = ui.checkbox(value=position in plan.selected, on_change=screen.tick(plan, position)).props("dense")
            if not plan.is_ready(position):
                box.disable()
            ui.link(fix.where.label, "#").on("click", screen.jump(fix.where)).classes(
                "text-blue-600 dark:text-blue-400 font-mono text-sm decoration-dotted hover:underline",
            )

        with ui.row().classes("w-full items-baseline gap-2 pl-10"):
            ui.label(f"{translate_string('now')}:").classes("text-xs text-gray-400 w-8 shrink-0")
            ui.label(fix.before).classes("text-xs text-gray-600 dark:text-gray-300 font-mono")

        with ui.row().classes("w-full items-center gap-2 pl-10"):
            ui.label(f"{translate_string('fix')}:").classes("text-xs text-gray-400 w-8 shrink-0")
            screen.lines[position] = ui.label(plan.describe(position)).classes(
                "text-xs text-green-700 dark:text-green-400 font-mono",
            )
            if fix.choice is not None:
                _draw_choice(plan, position, fix.choice, box, screen)

        if fix.note:
            ui.label(fix.note).classes("text-xs text-orange-600 dark:text-orange-400 pl-10 pr-2")


def _draw_choice(
    plan: mapfix.Plan,
    position: int,
    choice: mapfix.Choice,
    box: ui.checkbox,
    screen: _Screen,
) -> None:
    """The decision one repair needs, as the control that fits it.

    A list of answers is a pulldown; a length of time is a box to type a number in.  Both
    write straight onto the plan, so what Apply makes is what is on screen with no step in
    between that could come to disagree with it.
    """
    chosen = plan.value_of(position)

    if choice.kind == mapfix.CHOICE_NUMBER:
        ui.number(
            label=translate_string(choice.prompt),
            value=int(chosen) if chosen.isdigit() else None,
            min=1,
            format="%d",
            on_change=screen.choose(plan, position, box),
        ).props("dense").classes("w-28").tooltip(translate_string(f"{choice.prompt} in {choice.units}."))
        ui.label(translate_string(choice.units)).classes("text-xs text-gray-400")
        return

    select = ui.select(
        dict(choice.options),
        label=translate_string(choice.prompt),
        value=chosen or None,
        on_change=screen.choose(plan, position, box),
    )
    select.props("dense options-dense").classes("min-w-[260px]")
    if not chosen:
        select.tooltip(translate_string(_UNDECIDED_TIP))


def _save_preview(plan: mapfix.Plan | None, state: RunState) -> None:
    """Write the list to a text file, exactly as it stands.

    Worth having for the repairs the user decides NOT to make as much as the ones they do: a
    skip names what has to be done by hand before the repair can be offered at all, and that
    work list does not survive closing this window.

    NOT the same button as Save To Current File, which is why that one is coloured apart from
    every other button here: this writes a REPORT about the configuration, that writes the
    configuration, and two buttons beginning "Save" sitting side by side had better not read
    as a pair.
    """
    if plan is None:
        return
    file_name = mapfix.write_fix_report(mapfix.report_rows(plan), state=state)
    if file_name:
        ui.notify(f"{translate_string('Fix preview saved as')} {file_name}", type="positive")
    else:
        ui.notify(translate_string("Fix preview could not be saved."), type="negative")


# ##################################################################################
# The button row.
# ##################################################################################
def _build_buttons(dialog: ui.dialog, handlers: dict) -> None:
    """The row along the bottom, with the tooltip each button needs.

    A tooltip here is not a restatement of the label.  Each says the thing the label cannot:
    what Scan Again does to the ticks already made, what Apply costs in Undo, why Save
    Preview is worth pressing for the repairs you have decided against.
    """
    with ui.row().classes("w-full justify-end mt-4 gap-2"):
        _tip(
            ui.button(translate_string("Kinds..."), on_click=handlers["categories"]).props("outline"),
            "Go back and choose which kinds of finding to fix.\n\n"
            "Your ticks and decisions on the findings that are still in the list are kept.\n\n"
            "Nothing is changed by pressing this.\n\n",
        )
        _tip(
            ui.button(translate_string("Tick All"), on_click=handlers["tick_all"]).props("outline"),
            "Tick every repair that is ready to be made.\n\n"
            "A repair still waiting on a decision -- which label a broken 'Goto' should point at -- is "
            "left out, because ticking it would be ticking something nobody has decided.\n\n",
        )
        ui.button(translate_string("Tick None"), on_click=handlers["tick_none"]).props("outline")

        _tip(
            ui.button(translate_string("Scan Again"), on_click=handlers["rescan"]).classes(
                "bg-blue-600 text-white px-4",
            ),
            "Run the scan again and rebuild the list.\n\n"
            "Worth pressing after editing something in another window.  Your ticks and choices are "
            "kept, matched to the findings they were made about rather than to their place in the "
            "list.\n\nNothing is changed by pressing this.\n\n",
        )
        _tip(
            ui.button(translate_string("Apply"), on_click=handlers["apply"]).classes("bg-orange-600 text-white px-4"),
            "Make the ticked repairs, and nothing else.\n\n"
            "However many there are, the whole lot is one press of Undo afterwards.\n\n"
            "The list is scanned again straight away, so what is left in front of you is what is still "
            "wrong.\n\n",
        )
        _tip(
            # Coloured through the "color" prop rather than a bg-* class, for the reason the
            # drawer's own Health Check button gives: Quasar puts bg-primary on every button
            # and that beats a Tailwind bg-* added here, so a bg-green-700 renders plain blue.
            # It is the one button on this row that writes the configuration, and the only one
            # whose effect outlives the session, so it is the one that does not look like the
            # rest -- in particular not like "Save Preview" beside it.
            ui.button(translate_string("Save To Current File"), color="green", on_click=handlers["save_file"]).classes(
                "text-white px-4",
            ),
            "Write the whole configuration -- these repairs and every other edit made this session -- "
            "to a file.\n\n"
            "It goes to a new, timestamped copy of the file you loaded: backup.xml becomes "
            "backup_20260728_143005.xml.  The file you loaded is never written to, so it is left "
            "exactly as it was.\n\n"
            "The app then switches to the copy, and this list is scanned again against it.  Your "
            "ticks and choices are kept.\n\n"
            "Until you press this, the repairs exist only in memory and are lost on exit.\n\n",
        )
        _tip(
            ui.button(translate_string("Save Preview"), on_click=handlers["save"]).classes(
                "bg-blue-600 text-white px-4",
            ),
            "Write this list to a text file in the working folder.\n\n"
            "Worth having for the repairs you decide NOT to make: a refusal names what has to be done "
            "by hand first, and that list does not survive closing this window.\n\n",
        )
        _tip(
            ui.button(translate_string("Close"), on_click=dialog.close).classes("bg-red-500 text-white px-4"),
            "Close this window.\n\n"
            "Nothing is changed: a repair happens when Apply is pressed and at no other time, so there "
            "is never anything left pending here.\n\n",
        )


def _tip(element: ui.element, text: str) -> None:
    """Attach one of this dialog's explanatory tooltips to a control.

    Same shape as the Refactor dialog's: the text is translated, and pre-wrap is what makes
    the blank lines in it survive -- without it Quasar collapses the whole thing into one
    paragraph and the tooltip becomes the wall of text it was written not to be.
    """
    with element:
        ui.tooltip(translate_string(text)).style("white-space: pre-wrap")
