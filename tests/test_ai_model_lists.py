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


class _Handlers(userintr_ai.AIEventHandlers):
    """Just enough of MapTaskerEventHandlers to drive the Extended checkbox."""

    def __init__(self, *, initialization: bool) -> None:
        self.gui = SimpleNamespace(
            initialization=initialization,
            aimodel_extend_checkbox=SimpleNamespace(value=True),
            get_input_and_put_message=lambda checkbox, _title: checkbox.value,
            ai_model_extended_list=False,
        )


def _count_fetches(monkeypatch) -> list[str]:
    """Stand in for the extended fetch and the pulldown, and note every fetch made."""
    fetched = []
    monkeypatch.setattr(userintr_ai, "get_extended_ai_model_list", lambda: fetched.append("fetch") or [])
    monkeypatch.setattr(userintr_ai, "display_model_pulldown", lambda *_args, **_kwargs: None)
    return fetched


def test_restoring_a_ticked_checkbox_at_start_up_fetches_nothing(monkeypatch) -> None:
    """The restore still records the setting, but the fetch waits for someone to ask."""
    fetched = _count_fetches(monkeypatch)
    handlers = _Handlers(initialization=True)

    assert handlers.extended_models_changed() is None
    assert handlers.gui.ai_model_extended_list is True
    assert fetched == []


def test_ticking_the_checkbox_hands_back_the_fetch_to_run(monkeypatch) -> None:
    """A real click is answered with the coroutine NiceGUI runs in the background."""
    handlers = _Handlers(initialization=False)
    work = handlers.extended_models_changed()

    assert asyncio.iscoroutine(work)
    work.close()  # What it does when run is extended_models_event's business, not this test's.


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
