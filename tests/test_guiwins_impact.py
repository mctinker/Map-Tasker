"""The impact panel in every Delete dialog: what a delete takes, what it leaves, where to look.

The analysis itself is test_impact's.  What is tested here is what the panel does with an
answer -- how it words and colours it, whether it draws the list, and when it wires the
clicks -- so the analysis is replaced with one built by hand and the panel is drawn on a
page of NiceGUI's in-process user simulation.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from maptasker.src import guiwins_impact, impact
from maptasker.src.primitem import RunState
from nicegui import core, ui
from nicegui.testing.user_simulation import user_simulation

_drawn: dict = {}


def _consequence(severity: str = impact.BREAKS) -> impact.Consequence:
    return impact.Consequence(
        severity, "DANGLING-PERFORM-TASK", "Task 'Caller' action 2", "Performs a Task that is gone."
    )


def _page() -> None:
    """The page the panel is drawn on: arguments come from _drawn, so a test can choose them."""
    guiwins_impact.build_impact_panel(_drawn["gui"], "Task", "Helper", **_drawn.get("options", {}))


@pytest.fixture
def wired(monkeypatch: pytest.MonkeyPatch) -> list:
    """Click wiring recorded rather than run: it is javascript, and there is no browser."""
    calls: list = []
    monkeypatch.setattr(guiwins_impact, "wire_impact_clicks", lambda gui, container: calls.append(container))
    return calls


def _analysis(monkeypatch: pytest.MonkeyPatch, analysis: impact.Impact) -> None:
    _drawn.clear()
    _drawn["gui"] = SimpleNamespace(state=RunState())
    monkeypatch.setattr(guiwins_impact.impact, "analyze_delete", lambda *_args, **_kwargs: analysis)


async def _draw() -> list[str]:
    """Draw the panel and return the text of every label on it."""
    try:
        async with user_simulation(root=_page) as user:
            await user.open("/")
            return [element.text for element in user.find(kind=ui.label).elements]
    finally:
        if core.app.is_started:
            await core.app.stop()


# ##################################################################################
# Colour: red only when something is actually left pointing at nothing
# ##################################################################################
def test_a_delete_that_breaks_something_is_red() -> None:
    """The one case the colour exists for."""
    analysis = impact.Impact("x", consequences=[_consequence(impact.BREAKS)])
    assert guiwins_impact._summary_classes(analysis) == guiwins_impact._BREAKS_CLASSES  # noqa: SLF001


def test_a_delete_that_only_changes_things_is_amber_not_red() -> None:
    """A warning that fires on everything stops meaning anything on the delete that matters."""
    analysis = impact.Impact("x", consequences=[_consequence(impact.CHANGES)])
    assert guiwins_impact._summary_classes(analysis) == guiwins_impact._CHANGES_CLASSES  # noqa: SLF001


def test_a_delete_that_affects_nothing_is_green() -> None:
    """Nothing else points at it."""
    assert guiwins_impact._summary_classes(impact.Impact("x")) == guiwins_impact._CLEAN_CLASSES  # noqa: SLF001


# ##################################################################################
# The panel
# ##################################################################################
@pytest.mark.asyncio
async def test_a_harmless_delete_says_so_and_draws_no_list(monkeypatch: pytest.MonkeyPatch, wired: list) -> None:
    """What goes, then the one-line all-clear -- and no empty box under it."""
    _analysis(monkeypatch, impact.Impact("x", goes=["This Task will be deleted."]))

    labels = await _draw()

    assert "This Task will be deleted." in labels
    assert "Nothing else in this configuration points at it -- nothing will be left dangling." in labels
    assert not any("Click any line above" in label for label in labels)
    assert wired == []


@pytest.mark.asyncio
async def test_a_delete_with_consequences_draws_them_and_wires_the_clicks(
    monkeypatch: pytest.MonkeyPatch,
    wired: list,
) -> None:
    """The summary, the list, the hint that its lines are clickable, and the wiring that makes them so."""
    _analysis(monkeypatch, impact.Impact("x", consequences=[_consequence()]))

    labels = await _draw()

    assert "1 place(s) will be left pointing at something that is gone." in labels
    assert "Click any line above to see that place in the Map view." in labels
    assert len(wired) == 1


@pytest.mark.asyncio
async def test_a_caller_that_wires_its_own_ancestor_is_left_to_it(
    monkeypatch: pytest.MonkeyPatch,
    wired: list,
) -> None:
    """The Project dialog draws two panels and wires a parent of both; wiring each would miss the unopened tab."""
    _analysis(monkeypatch, impact.Impact("x", consequences=[_consequence()]))
    _drawn["options"] = {"wire": False}

    await _draw()

    assert wired == []


@pytest.mark.asyncio
async def test_the_scan_is_asked_about_what_the_delete_will_do(monkeypatch: pytest.MonkeyPatch, wired: list) -> None:
    """Kind and name pass straight through, and keep_contents reaches the analysis."""
    asked: dict = {}

    def fake(kind: str, name: str, **kwargs: object) -> impact.Impact:
        asked.update(kind=kind, name=name, **kwargs)
        return impact.Impact("x")

    _analysis(monkeypatch, impact.Impact("x"))
    monkeypatch.setattr(guiwins_impact.impact, "analyze_delete", fake)
    _drawn["options"] = {"keep_contents": False}

    await _draw()

    assert (asked["kind"], asked["name"], asked["keep_contents"]) == ("Task", "Helper", False)


# ##################################################################################
# The click wiring
# ##################################################################################
def test_the_wiring_is_installed_by_polling_until_the_browser_has_the_panel(monkeypatch: pytest.MonkeyPatch) -> None:
    """A dialog's contents are not in the page when it is built, so one try would find nothing."""
    registered: list = []
    timers: list = []
    sent: list = []
    monkeypatch.setattr(guiwins_impact, "register_finding_clicks", registered.append)
    monkeypatch.setattr(
        guiwins_impact.ui, "timer", lambda delay, callback, **kwargs: timers.append((delay, callback, kwargs))
    )
    monkeypatch.setattr(guiwins_impact.ui, "run_javascript", sent.append)
    gui = SimpleNamespace()

    guiwins_impact.wire_impact_clicks(gui, SimpleNamespace(id=42))

    assert registered == [gui]
    [(delay, callback, kwargs)] = timers
    assert (delay, kwargs) == (0.1, {"once": True})
    callback()
    [script] = sent
    assert 'document.getElementById("c42")' in script
    assert "attempts++ < 50" in script
    assert "setTimeout(attempt, 100)" in script
