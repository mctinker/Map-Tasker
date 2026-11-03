"""tools/language_support/sync_and_clean_po.py: translating with Ollama, and falling back to GoogleTranslator when that fails.

The tool is a maintainer script rather than part of the package, so it is loaded by path.  Neither translator is real:
`ollama` is a stand-in module that answers, raises or hangs as each test says, and the GoogleTranslator is a stand-in that
returns a marked string.  What is tested is the decision -- which of the two a string comes from -- for every way Ollama can
fail, and that a run against a machine with no Ollama on it asks it a few times and then stops, instead of once per string
in each of thirty-odd languages.
"""

from __future__ import annotations

import importlib.util
import socket
import sys
import types
from collections.abc import Iterator
from pathlib import Path
from typing import Any, ClassVar

import pytest

_TOOL = Path(__file__).resolve().parent.parent / "tools" / "language_support" / "sync_and_clean_po.py"


def _load_tool() -> Any:
    """The tool, loaded without leaving its process-wide 20 second socket timeout behind for the other tests."""
    before = socket.getdefaulttimeout()
    spec = importlib.util.spec_from_file_location("sync_and_clean_po", _TOOL)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["sync_and_clean_po"] = module
    try:
        spec.loader.exec_module(module)
    finally:
        socket.setdefaulttimeout(before)
    return module


tool = _load_tool()


class FakeOllama:
    """What `ollama.Client(...)` returns: answers each chat from a list of replies, or raises what a reply is."""

    instances: ClassVar[list[FakeOllama]] = []

    def __init__(self, replies: list[Any], **kwargs: Any) -> None:
        self.replies = replies
        self.kwargs = kwargs
        self.asked: list[dict[str, Any]] = []
        FakeOllama.instances.append(self)

    def chat(self, **kwargs: Any) -> Any:
        self.asked.append(kwargs)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, BaseException):
            raise reply
        return types.SimpleNamespace(message=types.SimpleNamespace(content=reply))


class FakeGoogle:
    """A GoogleTranslator that marks what it translated, and counts how often it was asked."""

    def __init__(self, answer: str | BaseException | None = None) -> None:
        self.answer = answer
        self.asked: list[str] = []

    def translate(self, text: str) -> str | None:
        self.asked.append(text)
        if isinstance(self.answer, BaseException):
            raise self.answer
        return f"[G] {text}" if self.answer is None else self.answer


@pytest.fixture(autouse=True)
def _fresh(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    tool.AI_HEALTH.reset()
    FakeOllama.instances.clear()
    monkeypatch.setattr(tool.time, "sleep", lambda _seconds: None)
    yield
    tool.AI_HEALTH.reset()


def ollama_says(monkeypatch: pytest.MonkeyPatch, *replies: Any) -> list[Any]:
    """Install a fake `ollama` package whose model gives these replies in turn (the last repeats)."""
    queue = list(replies)
    module = types.ModuleType("ollama")
    module.Client = lambda **kwargs: FakeOllama(queue, **kwargs)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "ollama", module)
    return queue


def translate(text: str, google: FakeGoogle | None) -> str | None:
    return tool.translate_with_fallback(google, "de", text)


# ##################################################################################
# Ollama works
# ##################################################################################
def test_a_translation_from_ollama_is_used_and_the_other_translator_is_not_asked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ollama_says(monkeypatch, "Speichern")
    google = FakeGoogle()

    assert translate("Save", google) == "Speichern"
    assert google.asked == []


def test_a_translation_that_keeps_its_placeholders_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    ollama_says(monkeypatch, "Gespeichert als {name} (%d Zeilen)")
    google = FakeGoogle()

    assert translate("Saved as {name} (%d lines)", google) == "Gespeichert als {name} (%d Zeilen)"
    assert google.asked == []


# ##################################################################################
# Every way Ollama can fail, and the fallback that follows
# ##################################################################################
@pytest.mark.parametrize(
    "failure",
    [
        ConnectionError("connection refused"),
        TimeoutError("timed out"),
        RuntimeError("model 'translategemma' not found"),
        OSError("no route to host"),
    ],
    ids=["server not running", "timeout", "model not installed", "network"],
)
def test_when_ollama_raises_the_string_is_translated_by_the_fallback(
    monkeypatch: pytest.MonkeyPatch, failure: BaseException
) -> None:
    ollama_says(monkeypatch, failure)
    google = FakeGoogle()

    assert translate("Save", google) == "[G] Save"
    assert google.asked == ["Save"]


def test_when_ollama_cannot_be_imported_the_tool_still_runs_and_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "ollama", None)  # `import ollama` then raises ImportError
    google = FakeGoogle()

    assert translate("Save", google) == "[G] Save"
    assert "cannot be imported" in tool.AI_HEALTH.last_reason


def test_the_tool_can_be_loaded_with_no_ollama_package_at_all(monkeypatch: pytest.MonkeyPatch) -> None:
    """The import used to be at the top of the file, so a machine without it failed before translating anything."""
    monkeypatch.setitem(sys.modules, "ollama", None)

    module = _load_tool()

    assert callable(module.ai_translate)


@pytest.mark.parametrize("reply", ["", "   \n ", None], ids=["empty", "blank", "none"])
def test_an_empty_reply_is_a_failure_and_falls_back(monkeypatch: pytest.MonkeyPatch, reply: str | None) -> None:
    ollama_says(monkeypatch, reply)
    google = FakeGoogle()

    assert translate("Save", google) == "[G] Save"
    assert tool.AI_HEALTH.last_reason == "the reply was empty"


@pytest.mark.parametrize(
    ("text", "reply"),
    [
        ("Saved as {name}", "Gespeichert als"),
        ("Saved as {name}", "Gespeichert als {Name}"),
        ("%d files", "Dateien"),
        ("Hello", "Hallo {name}"),
        ("%(count)s items", "%(zaehler)s Elemente"),
    ],
    ids=["lost", "renamed", "lost %d", "invented", "renamed named"],
)
def test_a_reply_that_lost_or_changed_a_placeholder_falls_back(
    monkeypatch: pytest.MonkeyPatch, text: str, reply: str
) -> None:
    ollama_says(monkeypatch, reply)
    google = FakeGoogle()

    assert translate(text, google) == f"[G] {text}"
    assert tool.AI_HEALTH.last_reason == "the reply lost or changed a placeholder"


def test_a_word_that_merely_begins_like_a_placeholder_is_not_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """Turkish's %değişken is a word, not %d -- the pattern check_catalogs.py holds the catalogs to says the same."""
    ollama_says(monkeypatch, "%değişken ayarla")
    google = FakeGoogle()

    assert translate("Set %variable", google) == "%değişken ayarla"
    assert google.asked == []


def test_when_both_fail_the_string_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    ollama_says(monkeypatch, ConnectionError("down"))
    google = FakeGoogle(RuntimeError("blocked"))

    assert translate("Save", google) is None


def test_with_no_fallback_translator_for_the_language_a_failure_is_a_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ollama_says(monkeypatch, ConnectionError("down"))

    assert translate("Save", None) is None
    assert "GoogleTranslator is not available for this language" in capsys.readouterr().out


def test_the_reason_ollama_failed_is_said_when_the_fallback_is_used(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ollama_says(monkeypatch, ConnectionError("connection refused"))

    translate("Save", FakeGoogle())

    assert (
        "[Fallback] AI translation failed (ConnectionError: connection refused) -- trying GoogleTranslator"
        in capsys.readouterr().out
    )


# ##################################################################################
# A request that never fails
# ##################################################################################
def test_the_request_to_ollama_has_a_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ollama's client has none of its own, and a request that never fails never reaches the fallback."""
    ollama_says(monkeypatch, "Speichern")

    translate("Save", FakeGoogle())

    assert FakeOllama.instances[0].kwargs == {"timeout": tool.AI_TIMEOUT_SECONDS}
    assert 0 < tool.AI_TIMEOUT_SECONDS <= 600


# ##################################################################################
# Giving up on Ollama for the rest of the run
# ##################################################################################
def test_after_a_few_failures_in_a_row_ollama_is_not_asked_again(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ollama_says(monkeypatch, ConnectionError("down"))
    google = FakeGoogle()

    results = [translate(f"String {n}", google) for n in range(10)]

    assert results == [f"[G] String {n}" for n in range(10)], "every string is still translated"
    assert len(FakeOllama.instances[0].asked) == tool.AI_FAILURES_BEFORE_GIVING_UP
    out = capsys.readouterr().out
    assert out.count("for the rest of this run") == 1, "said once, not once per string"


def test_a_success_in_between_starts_the_count_again(monkeypatch: pytest.MonkeyPatch) -> None:
    ollama_says(
        monkeypatch,
        ConnectionError("down"),
        ConnectionError("down"),
        "Gut",
        ConnectionError("down"),
        ConnectionError("down"),
        "Gut",
    )
    google = FakeGoogle()

    for text in ("a", "b", "c", "d", "e", "f"):
        translate(text, google)

    assert not tool.AI_HEALTH.given_up
    assert len(FakeOllama.instances[0].asked) == 6


def test_replies_that_are_unusable_do_not_count_as_ollama_being_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """The model is working; it just got those strings wrong, and the next may be fine."""
    ollama_says(monkeypatch, "")
    google = FakeGoogle()

    for number in range(10):
        translate(f"String {number}", google)

    assert not tool.AI_HEALTH.given_up
    assert len(FakeOllama.instances[0].asked) == 10


def test_giving_up_when_ollama_is_not_installed_asks_the_import_only_a_few_times(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "ollama", None)
    google = FakeGoogle()

    results = [translate(f"S{n}", google) for n in range(6)]

    assert all(result is not None for result in results)
    assert tool.AI_HEALTH.given_up


# ##################################################################################
# Through the whole string path
# ##################################################################################
def test_a_long_string_is_translated_in_pieces_each_by_whichever_translator_can(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Three pieces: Ollama does the first, and fails on the other two, which are the fallback's."""
    run = "x" * 3990
    long_text = f"First paragraph.\n\n{run}\n\nLast paragraph."
    assert len(tool.split_for_translation(long_text)) == 3
    ollama_says(monkeypatch, "Erster Absatz.", ConnectionError("down"))
    google = FakeGoogle()

    result = tool.translate_preserving_edges(google, "de", long_text)

    assert result == f"Erster Absatz.\n\n[G] {run}\n\n[G] Last paragraph."
    assert google.asked == [run, "Last paragraph."]


def test_a_string_with_leading_and_trailing_newlines_keeps_them_whichever_translator_does_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ollama_says(monkeypatch, ConnectionError("down"))

    assert tool.translate_preserving_edges(FakeGoogle(), "de", "\nSave\n") == "\n[G] Save\n"
