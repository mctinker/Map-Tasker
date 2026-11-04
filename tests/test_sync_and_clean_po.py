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


# ##################################################################################
# google-genai: installed for the run when it is missing, and uninstalled again with what it brought
# ##################################################################################
class FakeEnvironment:
    """The installed packages, and an installer that changes them -- in place of the real environment."""

    def __init__(self, installed: set[str], *, brings: set[str], works: bool = True) -> None:
        self.installed = set(installed)
        self.brings = brings
        self.works = works
        self.calls: list[tuple[str, list[str]]] = []

    def run_installer(self, verb: str, packages: list[str]) -> bool:
        self.calls.append((verb, packages))
        if not self.works:
            return False
        if verb == "install":
            self.installed |= self.brings
        else:
            self.installed -= set(packages)
        return True

    def importable(self, _module: str) -> bool:
        return "google-genai" in self.installed


def use(monkeypatch: pytest.MonkeyPatch, environment: FakeEnvironment) -> None:
    monkeypatch.setattr(tool, "run_installer", environment.run_installer)
    monkeypatch.setattr(tool, "importable", environment.importable)
    monkeypatch.setattr(tool, "installed_distributions", lambda: set(environment.installed))


def test_a_package_that_is_already_installed_is_used_and_left_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    environment = FakeEnvironment({"google-genai", "httpx"}, brings=set())
    use(monkeypatch, environment)

    with tool.temporary_package("google-genai", "google.genai") as ready:
        assert ready

    assert environment.calls == []
    assert "google-genai" in environment.installed


def test_a_missing_package_is_installed_for_the_block_and_uninstalled_with_what_it_brought(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = FakeEnvironment({"rich", "httpx"}, brings={"google-genai", "google-auth", "pyasn1"})
    use(monkeypatch, environment)

    with tool.temporary_package("google-genai", "google.genai") as ready:
        assert ready
        assert {"google-genai", "google-auth", "pyasn1"} <= environment.installed

    assert environment.installed == {"rich", "httpx"}
    assert environment.calls == [
        ("install", ["google-genai"]),
        ("uninstall", ["google-auth", "google-genai", "pyasn1"]),
    ]


def test_only_what_was_not_there_before_is_uninstalled(monkeypatch: pytest.MonkeyPatch) -> None:
    """httpx is already installed, so installing google-genai does not add it and uninstalling must not remove it."""
    environment = FakeEnvironment({"httpx"}, brings={"google-genai", "httpx", "tenacity"})
    use(monkeypatch, environment)

    with tool.temporary_package("google-genai", "google.genai"):
        pass

    assert "httpx" in environment.installed
    assert environment.calls[-1] == ("uninstall", ["google-genai", "tenacity"])


def test_the_package_is_uninstalled_when_the_block_fails_or_is_interrupted(monkeypatch: pytest.MonkeyPatch) -> None:
    for error in (RuntimeError("stage failed"), KeyboardInterrupt()):
        environment = FakeEnvironment({"rich"}, brings={"google-genai", "tenacity"})
        use(monkeypatch, environment)

        with pytest.raises(type(error)), tool.temporary_package("google-genai", "google.genai"):
            raise error

        assert environment.installed == {"rich"}


def test_a_failed_install_is_reported_not_ready_and_nothing_is_uninstalled(monkeypatch: pytest.MonkeyPatch) -> None:
    environment = FakeEnvironment({"rich"}, brings={"google-genai"}, works=False)
    use(monkeypatch, environment)

    with tool.temporary_package("google-genai", "google.genai") as ready:
        assert not ready

    assert environment.calls == [("install", ["google-genai"])]


def test_a_failed_uninstall_says_how_to_do_it_by_hand(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    environment = FakeEnvironment({"rich"}, brings={"google-genai", "tenacity"})
    use(monkeypatch, environment)
    real_run = environment.run_installer
    monkeypatch.setattr(tool, "run_installer", lambda verb, packages: real_run(verb, packages) and verb == "install")

    with tool.temporary_package("google-genai", "google.genai"):
        pass

    assert "uv pip uninstall google-genai tenacity" in capsys.readouterr().out


def test_names_are_compared_however_they_are_spelled() -> None:
    assert tool.distribution_name("Google_GenAI") == tool.distribution_name("google-genai") == "google-genai"
    assert tool.distribution_name("typing.extensions") == "typing-extensions"


def test_uv_is_tried_first_and_pip_after_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool.shutil, "which", lambda _name: "/usr/local/bin/uv")

    commands = tool.installer_commands("uninstall", ["a", "b"])

    assert commands[0] == ["uv", "pip", "uninstall", "--python", sys.executable, "a", "b"]
    assert commands[1] == [sys.executable, "-m", "pip", "uninstall", "-y", "a", "b"]


def test_without_uv_pip_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool.shutil, "which", lambda _name: None)

    assert tool.installer_commands("install", ["google-genai"]) == [
        [sys.executable, "-m", "pip", "install", "google-genai"]
    ]


def test_the_next_installer_is_tried_when_the_first_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool.shutil, "which", lambda _name: "/usr/local/bin/uv")
    tried: list[str] = []

    def fake_run(command: list[str], **_kwargs: Any) -> Any:
        tried.append(command[0])
        return types.SimpleNamespace(returncode=2 if command[0] == "uv" else 0, stdout="", stderr="externally managed")

    monkeypatch.setattr(tool.subprocess, "run", fake_run)

    assert tool.run_installer("install", ["google-genai"])
    assert tried == ["uv", sys.executable]


def test_an_installer_that_cannot_be_run_is_a_failure_not_a_crash(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(tool.shutil, "which", lambda _name: None)

    def fake_run(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("no such file")

    monkeypatch.setattr(tool.subprocess, "run", fake_run)

    assert not tool.run_installer("install", ["google-genai"])
    assert "Could not install google-genai" in capsys.readouterr().out


def test_a_run_has_the_package_installed_while_the_stages_run_and_gone_after(monkeypatch: pytest.MonkeyPatch) -> None:
    environment = FakeEnvironment({"rich"}, brings={"google-genai", "tenacity"})
    use(monkeypatch, environment)
    seen: list[bool] = []

    def stage() -> int:
        seen.append("google-genai" in environment.installed)
        return 0

    monkeypatch.setattr(tool, "STAGES", {1: ("sync", "Sync", stage)})
    monkeypatch.setattr(sys, "argv", ["sync_and_clean_po.py", "--stages", "1"])

    assert tool.main() == 0

    assert seen == [True]
    assert environment.installed == {"rich"}


def test_a_run_goes_on_without_the_package_when_it_cannot_be_installed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    environment = FakeEnvironment({"rich"}, brings={"google-genai"}, works=False)
    use(monkeypatch, environment)
    monkeypatch.setattr(tool, "STAGES", {1: ("sync", "Sync", lambda: 0)})
    monkeypatch.setattr(sys, "argv", ["sync_and_clean_po.py", "--stages", "1"])

    assert tool.main() == 0
    assert "Carrying on without google-genai" in capsys.readouterr().out
