"""tools/language_support/check_catalogs.py --fix: when Ollama fails, the string is translated by the fallback.

check_catalogs.py has no translator of its own.  It loads sync_and_clean_po.py and hands every string to it -- a catalog's
through sync_language, a README block's through machine_translator -- and both reach translate_with_fallback.  These tests
run the real --fix, with the real sync_and_clean_po loaded, over small catalogs and READMEs in a temporary folder, with a stand-in
`ollama` that fails in each way and a stand-in GoogleTranslator, so what is checked is the whole path: that a string Ollama cannot
do still comes out translated, in the catalogs and in the READMEs, and that nothing has to be installed for that to be so.
"""

from __future__ import annotations

import importlib.util
import socket
import sys
import types
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

import pytest

from tests.test_check_catalogs import _ENGLISH, HEADER, _readmes

if TYPE_CHECKING:
    from collections.abc import Iterator

_TOOL = Path(__file__).resolve().parent.parent / "tools" / "language_support" / "check_catalogs.py"
_MODULE = "check_catalogs_fallback"


def _load() -> Any:
    spec = importlib.util.spec_from_file_location(_MODULE, _TOOL)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE] = module
    spec.loader.exec_module(module)
    return module


cc = _load()


class FakeGoogle:
    """deep_translator.GoogleTranslator, marking what it translated and counting how often it was asked."""

    # Shared on purpose: the tool makes the instances, so the test has to read what they recorded from the class.
    asked: ClassVar[list[tuple[str, str]]] = []

    def __init__(self, source: str = "en", target: str = "de") -> None:
        self.target = target

    def translate(self, text: str) -> str:
        FakeGoogle.asked.append((self.target, text))
        return f"[G] {text}"


class FakeOllama:
    """What `ollama.Client(...)` returns: it raises, or answers with a marked translation."""

    behaviour: Any = ConnectionError("connection refused")
    chats = 0

    def __init__(self, **_kwargs: Any) -> None:
        pass

    def chat(self, **_kwargs: Any) -> Any:
        FakeOllama.chats += 1
        if isinstance(FakeOllama.behaviour, BaseException):
            raise FakeOllama.behaviour
        return types.SimpleNamespace(message=types.SimpleNamespace(content=f"[AI] {FakeOllama.behaviour}"))


@pytest.fixture(autouse=True)
def _environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """No network, no real Ollama, no msgfmt, no waiting -- and the tool loaded afresh, with its socket timeout undone."""
    import deep_translator

    before = socket.getdefaulttimeout()
    FakeGoogle.asked.clear()
    FakeOllama.chats = 0
    FakeOllama.behaviour = ConnectionError("connection refused")
    ollama = types.ModuleType("ollama")
    ollama.Client = FakeOllama  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "ollama", ollama)
    monkeypatch.setattr(deep_translator, "GoogleTranslator", FakeGoogle)
    monkeypatch.setattr(cc.shutil, "which", lambda _name: None)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    cc._loaded_tools.clear()
    yield
    if (tool := cc._loaded_tools.get("sync")) is not None:
        tool.AI_HEALTH.reset()
    cc._loaded_tools.clear()
    socket.setdefaulttimeout(before)


def _catalog(locale: Path, language: str, entries: dict[str, str]) -> Path:
    folder = locale / language / "LC_MESSAGES"
    folder.mkdir(parents=True)
    path = folder / "messages.po"
    path.write_text(HEADER + "".join(f"\nmsgid {cc.encode(k)}\nmsgstr {cc.encode(v)}\n" for k, v in entries.items()))
    return path


def _fix_catalogs(locale: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    monkeypatch.setattr(cc, "source_strings", lambda _source: {"Save", "Open"})
    monkeypatch.setattr(cc, "help_strings", lambda _root: set())
    monkeypatch.setattr(sys, "argv", ["check_catalogs.py", "--catalogs-only", "--locale", str(locale), "--fix"])
    return cc.main()


# ##################################################################################
# The catalogs
# ##################################################################################
@pytest.mark.parametrize(
    "failure",
    [
        ConnectionError("connection refused"),
        RuntimeError("model 'translategemma' not found"),
        TimeoutError("timed out"),
    ],
    ids=["server not running", "model not installed", "timeout"],
)
def test_fixing_the_catalogs_uses_the_fallback_when_ollama_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: BaseException
) -> None:
    FakeOllama.behaviour = failure
    path = _catalog(tmp_path, "de", {"Save": "Speichern"})

    assert _fix_catalogs(tmp_path, monkeypatch) == 0

    assert cc.read_catalog(path).entries["Open"] == "[G] Open"
    assert ("de", "Open") in FakeGoogle.asked


def test_fixing_the_catalogs_uses_the_fallback_when_ollama_is_not_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "ollama", None)  # `import ollama` then raises ImportError
    path = _catalog(tmp_path, "de", {"Save": "Speichern"})

    assert _fix_catalogs(tmp_path, monkeypatch) == 0

    assert cc.read_catalog(path).entries["Open"] == "[G] Open"


def test_fixing_the_catalogs_uses_ollama_when_it_works_and_never_asks_the_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    FakeOllama.behaviour = "translated"
    path = _catalog(tmp_path, "de", {"Save": "Speichern"})

    assert _fix_catalogs(tmp_path, monkeypatch) == 0

    assert cc.read_catalog(path).entries["Open"] == "[AI] translated"
    assert FakeGoogle.asked == []


def test_every_language_is_translated_though_ollama_is_given_up_on_part_way(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ollama fails three times and is not asked again; the rest of the languages still come out translated."""
    languages = ("de", "fr", "es", "it", "nl", "pl")
    paths = {language: _catalog(tmp_path, language, {"Save": language}) for language in languages}

    assert _fix_catalogs(tmp_path, monkeypatch) == 0

    assert all(cc.read_catalog(path).entries["Open"] == "[G] Open" for path in paths.values())
    assert FakeOllama.chats == 3, "asked until it was given up on, and no more"


# ##################################################################################
# The READMEs
# ##################################################################################
def _fix_readmes(root: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    monkeypatch.setattr(sys, "argv", ["check_catalogs.py", "--readme-only", "--readme-dir", str(root), "--fix"])
    return cc.main()


def test_fixing_a_readme_uses_the_fallback_when_ollama_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    english = _ENGLISH.replace("## What it does", "## What it does\n\nA brand new paragraph in the README.")
    root = _readmes(tmp_path, english)

    assert _fix_readmes(root, monkeypatch) == 0

    text = (root / "README_translated" / "README.de.md").read_text(encoding="utf-8")
    assert "[G] A brand new paragraph in the README." in text
    assert "[AI]" not in text


def test_fixing_a_readme_uses_the_fallback_when_ollama_is_not_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "ollama", None)
    english = _ENGLISH.replace("## What it does", "## What it does\n\nA brand new paragraph in the README.")
    root = _readmes(tmp_path, english)

    assert _fix_readmes(root, monkeypatch) == 0

    assert "[G] A brand new paragraph" in (root / "README_translated" / "README.de.md").read_text(encoding="utf-8")


def test_a_readmes_markup_survives_the_fallback_as_it_does_the_local_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    english = _ENGLISH.replace(
        "## What it does", "## What it does\n\nA brand new paragraph with `code` and [a link](./docs/x.md)."
    )
    root = _readmes(tmp_path, english)

    assert _fix_readmes(root, monkeypatch) == 0

    text = (root / "README_translated" / "README.de.md").read_text(encoding="utf-8")
    assert "`code`" in text
    assert "[a link](../docs/x.md)" in text, "a relative link is re-pointed for README_translated/"
