"""The extended list of AI models is fetched when it is asked for, and survives the network.

Restoring the saved settings at start-up ticks the Extended checkbox, and that used to set
off the whole extended fetch -- installing openai and google.genai and going out to every
provider -- before anyone had asked for AI at all.  And a dropped connection while listing
Gemini's models came out as a traceback instead of the built-in list.
"""

from __future__ import annotations

import asyncio
import sys
from types import ModuleType, SimpleNamespace

import httpx
import pytest

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
    monkeypatch.setattr(aiutils, "import_optional", lambda *_args: SimpleNamespace(Client=_DroppedConnection))
    reported = []
    monkeypatch.setattr(aiutils, "rutroh_error", reported.append)

    assert aiutils.get_gemini_models(state=PrimeItems) == aiutils.GEMINI_MODELS
    assert any("UNEXPECTED_EOF" in message for message in reported)


# -- Only the failures that mean "no answer" are caught ------------------------------------
# These handlers used to catch every exception, so a bug in the code around the call came
# back as "Ollama is not running" or as the built-in model list, and was never seen.


def _an_ollama(error: BaseException) -> SimpleNamespace:
    """An 'ollama' package whose list() raises the given error."""

    def failing_list() -> None:
        raise error

    return SimpleNamespace(list=failing_list)


@pytest.fixture
def _ollama_package(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stand in for the 'ollama' package, which only the "ai" extra installs.

    ollama_errors() names ollama.ResponseError, so these tests need the module to exist -- and
    they should not depend on the real one being installed.
    """
    fake = ModuleType("ollama")
    fake.ResponseError = type("ResponseError", (Exception,), {})
    monkeypatch.setitem(sys.modules, "ollama", fake)


@pytest.mark.usefixtures("_ollama_package")
def test_ollama_refusing_the_connection_is_not_answering() -> None:
    assert aiutils.ollama_is_responding(_an_ollama(ConnectionError("refused"))) is False


@pytest.mark.usefixtures("_ollama_package")
def test_an_ollama_timeout_is_not_answering() -> None:
    assert aiutils.ollama_is_responding(_an_ollama(httpx.ReadTimeout("timed out"))) is False


@pytest.mark.usefixtures("_ollama_package")
def test_a_bug_while_asking_ollama_is_not_mistaken_for_no_server() -> None:
    with pytest.raises(TypeError):
        aiutils.ollama_is_responding(_an_ollama(TypeError("a bug, not a network problem")))


def _an_openai(error: BaseException) -> ModuleType:
    """An 'openai' package whose model listing raises the given error."""

    class _Client:
        def __init__(self, **_kwargs) -> None:
            self.models = self

        def list(self) -> None:
            raise error

    openai_lib = ModuleType("openai")
    openai_lib.OpenAI = _Client
    openai_lib.OpenAIError = _OpenAIError
    return openai_lib


class _OpenAIError(Exception):
    """Stands in for openai.OpenAIError, the base of everything the SDK raises."""


def test_an_openai_error_while_listing_gives_the_built_in_list(monkeypatch) -> None:
    monkeypatch.setitem(PrimeItems.ai, "openai_key", "a-key")
    monkeypatch.setattr(aiutils, "import_optional", lambda *_args: _an_openai(_OpenAIError("bad key")))
    reported = []
    monkeypatch.setattr(aiutils, "rutroh_error", reported.append)

    assert aiutils.get_openai_models(state=PrimeItems) == aiutils.OPENAI_MODELS
    assert any("bad key" in message for message in reported)


def test_a_bug_while_listing_openai_models_is_not_hidden(monkeypatch) -> None:
    monkeypatch.setitem(PrimeItems.ai, "openai_key", "a-key")
    monkeypatch.setattr(aiutils, "import_optional", lambda *_args: _an_openai(TypeError("a bug")))

    with pytest.raises(TypeError):
        aiutils.get_openai_models(state=PrimeItems)
