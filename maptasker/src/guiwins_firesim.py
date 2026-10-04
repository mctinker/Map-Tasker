"""guiwins_firesim: the "What Fires When?" dialog -- firesim, with the scenario as controls."""

#! /usr/bin/env python3

#                                                                                        #
# guiwins_firesim: where firesim hangs off the GUI.                                      #
#                                                                                        #
# Four inputs along the top -- the date and time, the Wi-Fi network, the app in front,   #
# the battery level -- and underneath, redrawn on every change, what that moment makes    #
# of the configuration: where Profiles collide, the order their entry Tasks are queued   #
# in, which Profiles are active, which are still waiting on something the scenario does  #
# not describe, and (folded away) which are ruled out and by what.                       #
#                                                                                        #
# Collisions come first for mapswap's and guiwins_fix's reason: they are the part the    #
# user must read and the part they will not scroll back down for.                        #
#                                                                                        #
# Recomputed on every change rather than behind a Simulate button: firesim over a        #
# backup of several hundred Profiles takes a few milliseconds, so there is no cost to     #
# make the user wait on, and moving the time a minute at a time to watch a repeating     #
# Profile tick on and off is the way this is meant to be used.                           #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

import time as clock
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from nicegui import ui

from maptasker.src import firesim
from maptasker.src.maputil2 import translate_string

if TYPE_CHECKING:
    from collections.abc import Callable

    from maptasker.src.mapjump import Target
    from maptasker.src.primitem import RunState

# The two answers a Wi-Fi or app picker can give besides a real network or app.  Keys that
# no SSID or package can be, so a network actually named "(not connected)" cannot be
# mistaken for the absence of one.
_SKIP = "\x00skip"
_NONE = "\x00none"

# Inactive Profiles can run to hundreds on a large backup, and are folded away already.
_INACTIVE_LIMIT = 300

_BLURB = (
    "Choose a moment and see which Profiles it makes active, the order their Tasks start in, and "
    "where they collide.  Anything left 'not simulated' -- and anything no input here describes, "
    "such as an Event, a location or a %variable -- is treated as unknown, so a Profile that "
    "depends on it is shown as possible rather than guessed at."
)

_STATE_CLASSES = {
    firesim.ACTIVE: "text-green-700 dark:text-green-400",
    firesim.POSSIBLE: "text-amber-600 dark:text-amber-400",
    firesim.INACTIVE: "text-gray-500",
}
_OUTCOME_MARK = {firesim.YES: "✓", firesim.NO: "✗", firesim.UNKNOWN: "?"}


@dataclass
class _Inputs:
    """The four controls, read together into a Scenario."""

    date: ui.input
    time: ui.input
    wifi: ui.select
    app: ui.select
    battery: ui.number

    def scenario(self) -> firesim.Scenario | None:
        """The moment the controls describe, or None while the date or time does not parse."""
        try:
            # Naive on purpose: a Time condition reads the device's own local clock.
            when = datetime.fromisoformat(f"{self.date.value}T{self.time.value}")
        except (TypeError, ValueError):
            return None
        battery = self.battery.value
        return firesim.Scenario(
            when=when,
            wifi=_picked(self.wifi.value),
            app=_picked(self.app.value),
            battery=None if battery is None else max(0, min(100, int(battery))),
        )


def _picked(value: object) -> str | None:
    """A picker's value as the Scenario takes it: None for not simulated, "" for none."""
    if value in (None, _SKIP):
        return None
    if value == _NONE:
        return ""
    return str(value).strip()


def build_firesim_dialog(make_jump: Callable, state: RunState) -> ui.dialog | None:
    """Build and return the What Fires When? dialog, or None if nothing is loaded.

    `make_jump` turns a Target into a click handler, and is passed in rather than imported
    for guiwins_fix's reason: this module is reached FROM guiwins, and reaching back into it
    would be a circular import.
    """
    if not state.tasker_root_elements.get("all_profiles"):
        ui.notify(
            translate_string("No XML file with Profiles has been loaded.  Get an XML file first."), type="warning"
        )
        return None

    # Not persistent: nothing here is work in progress, so a click outside may close it.
    with ui.dialog() as dialog, ui.card().classes("w-[1000px] max-w-full p-6"):
        ui.label(translate_string("What Fires When?")).classes("text-lg font-bold text-blue-600")
        ui.label(translate_string(_BLURB)).classes("text-xs text-gray-500 italic mb-2 mt-1")

        with ui.row().classes("w-full items-end gap-3 no-wrap"):
            date = ui.input(translate_string("Date"), value=clock.strftime("%Y-%m-%d")).props("type=date dense")
            time = ui.input(translate_string("Time"), value=clock.strftime("%H:%M")).props("type=time dense")
            wifi = (
                ui.select(
                    {
                        _SKIP: translate_string("(not simulated)"),
                        _NONE: translate_string("(not connected)"),
                        **{name: name for name in firesim.wifi_networks(state=state)},
                    },
                    value=_SKIP,
                    label=translate_string("Wi-Fi network"),
                    with_input=True,
                    new_value_mode="add-unique",
                )
                .props("dense options-dense")
                .classes("min-w-[190px]")
            )
            app = (
                ui.select(
                    {
                        _SKIP: translate_string("(not simulated)"),
                        _NONE: translate_string("(no app in front)"),
                        **firesim.condition_apps(state=state),
                    },
                    value=_SKIP,
                    label=translate_string("App in front"),
                    with_input=True,
                    new_value_mode="add-unique",
                )
                .props("dense options-dense")
                .classes("min-w-[190px]")
            )
            battery = (
                ui.number(translate_string("Battery %"), value=None, min=0, max=100, format="%d")
                .props("dense clearable")
                .classes("w-28")
            )
            battery.tooltip(translate_string("Leave empty to not simulate the battery level."))

        inputs = _Inputs(date, time, wifi, app, battery)
        summary = ui.label("").classes("text-sm font-bold text-orange-500 mt-2")
        area = ui.scroll_area().classes("w-full h-[480px] border rounded dark:border-gray-700 mt-1")

        def redraw() -> None:
            # ui.number's min and max bound its arrows, not what is typed into it.  Put the
            # box right rather than simulate a level it does not show; the change this makes
            # comes back through here.
            if battery.value is not None and not 0 <= battery.value <= 100:
                battery.value = max(0, min(100, int(battery.value)))
                return
            scenario = inputs.scenario()
            if scenario is None:
                summary.set_text(translate_string("Choose a date and a time."))
                area.clear()
                return
            result = firesim.simulate(scenario, state=state)
            summary.set_text(_summary_text(result))
            _draw(result, area, make_jump)

        def reset_to_now() -> None:
            date.value = clock.strftime("%Y-%m-%d")
            time.value = clock.strftime("%H:%M")

        for control in (date, time, wifi, app, battery):
            control.on_value_change(redraw)

        with ui.row().classes("w-full justify-end mt-4 gap-2"):
            ui.button(translate_string("Now"), on_click=reset_to_now).props("outline").tooltip(
                translate_string("Set the date and time back to this moment."),
            )
            ui.button(translate_string("Close"), on_click=dialog.close).classes("bg-red-500 text-white px-4")

        redraw()

    return dialog


# ##################################################################################
# Drawing the answer.
# ##################################################################################
def _summary_text(result: firesim.Simulation) -> str:
    """The line above the answer."""
    certain = sum(1 for collision in result.collisions if collision.certain)
    parts = [
        f"{len(result.active)} {translate_string('active')}",
        f"{len(result.possible)} {translate_string('possible')}",
        f"{len(result.inactive)} {translate_string('not active')}",
    ]
    if result.disabled:
        parts.append(f"{result.disabled} {translate_string('disabled')}")
    collisions = f"{len(result.collisions)} {translate_string('collision(s)')}"
    if result.collisions and certain != len(result.collisions):
        collisions += f" ({certain} {translate_string('certain')})"
    return f"{', '.join(parts)}  --  {collisions}"


def _link(target: Target, make_jump: Callable, classes: str = "") -> None:
    """A clickable name that goes to the object in the Map view."""
    ui.link(target.label, "#").on("click", make_jump(target)).classes(
        f"text-blue-600 dark:text-blue-400 font-mono text-sm decoration-dotted hover:underline {classes}",
    )


def _heading(text: str, classes: str = "text-blue-600") -> None:
    """A section heading, already translated by the caller."""
    ui.label(text).classes(f"text-sm font-bold mt-3 {classes}")


def _draw(result: firesim.Simulation, area: ui.scroll_area, make_jump: Callable) -> None:
    """Collisions, then the run order, then the Profiles by state."""
    area.clear()
    with area, ui.column().classes("w-full gap-1 p-1"):
        if result.collisions:
            _heading(translate_string("Collisions"), "text-red-600 dark:text-red-400")
            for collision in result.collisions:
                with ui.column().classes("w-full gap-0 pl-2 pb-1"):
                    with ui.row().classes("items-baseline gap-2"):
                        ui.label(f"[{collision.kind}]").classes("font-mono text-xs font-bold text-orange-500")
                        _link(collision.where, make_jump)
                    ui.label(collision.detail).classes(
                        "text-xs "
                        + ("text-gray-600 dark:text-gray-300" if collision.certain else "text-gray-500 italic"),
                    )

        _heading(translate_string("Run order"))
        ui.label(
            translate_string(
                "Each Profile's entry Task, highest priority first.  'tied' starts share a priority, and Tasker "
                "does not fix the order among them.",
            ),
        ).classes("text-xs text-gray-500 pl-2")
        if not result.queue:
            ui.label(translate_string("No Profile that is, or may be, active starts a Task.")).classes(
                "text-xs text-gray-500 italic pl-2",
            )
        for run in result.queue:
            with ui.column().classes("w-full gap-0 pl-2 pb-1"):
                with ui.row().classes("w-full items-baseline gap-2"):
                    ui.label(f"{run.position}.").classes("font-mono text-xs text-gray-400 w-6 shrink-0")
                    ui.label(f"{translate_string('priority')} {run.profile.priority}").classes(
                        "font-mono text-xs text-gray-400 shrink-0",
                    )
                    _link(run.task, make_jump)
                    if run.tied:
                        ui.badge(translate_string("tied"), color="grey").props("outline")
                    if run.profile.state == firesim.POSSIBLE:
                        ui.badge(translate_string("if the Profile is active"), color="amber").props("outline")
                with ui.row().classes("w-full items-baseline gap-2 pl-8"):
                    ui.label(translate_string("started by")).classes("text-xs text-gray-400")
                    _link(run.profile.target, make_jump, _STATE_CLASSES[run.profile.state])

        _draw_profiles("Active", result.active, make_jump, show=lambda profile: profile.verdicts)
        _draw_profiles("Possible -- waiting on", result.possible, make_jump, show=lambda profile: profile.waiting_on)

        if result.inactive:
            with ui.expansion(f"{translate_string('Not active')} ({len(result.inactive)})").classes(
                "w-full text-sm text-gray-500 mt-2",
            ):
                for profile in result.inactive[:_INACTIVE_LIMIT]:
                    reason = profile.ruled_out_by
                    with ui.row().classes("w-full items-baseline gap-2 pl-2"):
                        _link(profile.target, make_jump)
                        if reason is not None:
                            ui.label(f"{reason.label}: {reason.reason}").classes("text-xs text-gray-500")
                if len(result.inactive) > _INACTIVE_LIMIT:
                    ui.label(f"...{len(result.inactive) - _INACTIVE_LIMIT} {translate_string('more')}").classes(
                        "text-xs text-gray-500 italic pl-2",
                    )


def _draw_profiles(title: str, profiles: list[firesim.ProfileResult], make_jump: Callable, show: Callable) -> None:
    """One group of Profiles, each with the conditions worth reading about it."""
    _heading(f"{translate_string(title)} ({len(profiles)})", "text-blue-600")
    if not profiles:
        ui.label(translate_string("None.")).classes("text-xs text-gray-500 italic pl-2")
    for profile in profiles:
        with ui.column().classes("w-full gap-0 pl-2 pb-1"):
            with ui.row().classes("items-baseline gap-2"):
                _link(profile.target, make_jump, _STATE_CLASSES[profile.state])
                if profile.instant:
                    ui.label(translate_string("(fires at a moment, then is done)")).classes(
                        "text-xs text-gray-500 italic",
                    )
            for verdict in show(profile):
                ui.label(f"{_OUTCOME_MARK[verdict.outcome]} {verdict.label}: {verdict.reason}").classes(
                    "text-xs text-gray-600 dark:text-gray-300 pl-6",
                )
