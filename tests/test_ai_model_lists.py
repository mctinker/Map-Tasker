"""The extended list of AI models is fetched when it is asked for, and survives the network.

Restoring the saved settings at start-up ticks the Extended checkbox, and that used to set
off the whole extended fetch -- installing openai and google.genai and going out to every
provider -- before anyone had asked for AI at all.  And a dropped connection while listing
Gemini's models came out as a traceback instead of the built-in list.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from maptasker.src import aiutils, userintr_ai
from maptasker.src.primitem import PrimeItems


def _a_window(*, initialization: bool) -> tuple[SimpleNamespace, list[str]]:
    """Just enough of a window for the Extended checkbox, and a note of every fetch started."""
    started = []

    async def extended_models_event() -> None:
        started.append("fetch")

    gui = SimpleNamespace(initialization=initialization, event_handlers=SimpleNamespace())
    gui.event_handlers.extended_models_event = extended_models_event
    return gui, started


def test_restoring_a_ticked_checkbox_at_start_up_fetches_nothing() -> None:
    """The restore has already put the setting in place; the fetch waits for someone to ask."""
    gui, started = _a_window(initialization=True)

    assert userintr_ai.AIEventHandlers.extended_models_changed(gui) is None
    assert started == []


def test_ticking_the_checkbox_hands_back_the_fetch_to_run() -> None:
    """A real click is answered with the coroutine NiceGUI runs in the background."""
    gui, started = _a_window(initialization=False)
    work = userintr_ai.AIEventHandlers.extended_models_changed(gui)

    assert asyncio.iscoroutine(work)
    asyncio.run(work)
    assert started == ["fetch"]


def test_a_dropped_connection_while_listing_gemini_gives_the_built_in_list(monkeypatch) -> None:
    """The error from the field: the SSL handshake cut short mid-list.  No traceback."""

    class _DroppedConnection:
        def __init__(self, **_kwargs) -> None:
            self.models = self

        def list(self) -> None:
            message = "[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol"
            raise ConnectionError(message)

    monkeypatch.setitem(PrimeItems.ai, "gemini_key", "a-key")
    monkeypatch.setattr(aiutils, "ensure_and_import", lambda *_args: SimpleNamespace(Client=_DroppedConnection))
    reported = []
    monkeypatch.setattr(aiutils, "rutroh_error", reported.append)

    assert aiutils.get_gemini_models() == aiutils.GEMINI_MODELS
    assert any("UNEXPECTED_EOF" in message for message in reported)
