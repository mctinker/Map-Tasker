"""The AI services MapTasker supports: OpenAI, Anthropic (Claude), Gemini, and Ollama for local models.

The calls each service is sent are test_mapai's (the Analyze tab) and test_mapask's (the Find box).  This is what
stands behind them: the lists of models offered, which are exact strings a service either takes or answers with a
404; the Models API listing that keeps the Claude list current; getting a local Ollama model ready to be asked;
and the saved choices -- a selected service, a saved key -- of one that is no longer supported.  Every library is a
stand-in: the optional AI libraries are not installed where these run, and no request may be made where they are.
"""

from __future__ import annotations

import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from maptasker.src.core import aiutils, getputer, sysconst
from maptasker.src.core.primitem import RunState
from maptasker.src.gui import userintr_ai
from maptasker.src.gui.userintr import MapTaskerEventHandlers, MyGui


# ##################################################################################
# The lists of models.
# ##################################################################################
def test_the_services_offered_are_openai_claude_gemini_and_ollama() -> None:
    assert set(sysconst.MODEL_GROUPS) == {"OpenAI", "Anthropic", "Gemini", "LLAMA"}
    assert set(RunState().ai) >= {"openai_models", "anthropic_models", "gemini_models", "llama_models"}
    assert not [key for key in RunState().ai if "deepseek" in key.lower()]


def test_no_list_of_models_names_a_service_that_is_no_longer_supported() -> None:
    everything = [
        *sysconst.OPENAI_MODELS,
        *sysconst.ANTHROPIC_MODELS,
        *sysconst.ANTHROPIC_EXTENDED_MODELS,
        *sysconst.GEMINI_MODELS,
        *sysconst.LLAMA_MODELS,
    ]
    assert not [model for model in everything if "deepseek" in model.lower()]
    assert not hasattr(sysconst, "DEEPSEEK_MODELS")


def test_the_extended_list_of_local_models_names_none_either(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aiutils, "import_optional", lambda *_: None)
    monkeypatch.setattr(aiutils, "rutroh_error", lambda *_: None)

    assert not [model for model in aiutils.get_llama_models() if "deepseek" in model.lower()]


@pytest.mark.parametrize(
    "models",
    [sysconst.OPENAI_MODELS, sysconst.ANTHROPIC_MODELS, sysconst.ANTHROPIC_EXTENDED_MODELS, sysconst.GEMINI_MODELS],
)
def test_a_list_names_each_model_once(models: list[str]) -> None:
    assert len(models) == len(set(models))


def test_claude_models_are_named_by_their_ids_without_a_date() -> None:
    """The current models have no snapshot suffix; a name with one is a name the API answers with a 404."""
    for model in sysconst.ANTHROPIC_EXTENDED_MODELS:
        assert re.fullmatch(r"claude-[a-z]+-\d+(-\d+)?", model), model


def test_the_current_claude_models_are_offered() -> None:
    assert {
        "claude-fable-5-1",
        "claude-opus-5-5",
        "claude-sonnet-5-5",
        "claude-haiku-5-5",
    } <= set(sysconst.ANTHROPIC_MODELS)


def test_the_extended_claude_list_holds_the_default_one_and_the_earlier_models() -> None:
    assert set(sysconst.ANTHROPIC_MODELS) <= set(sysconst.ANTHROPIC_EXTENDED_MODELS)
    assert {"claude-opus-4-8", "claude-sonnet-4-6"} <= set(sysconst.ANTHROPIC_EXTENDED_MODELS)


# ##################################################################################
# Claude models, from the Models API.
# ##################################################################################
class _AnthropicError(Exception):
    pass


def _fake_anthropic(*, ids: list[str] | None = None, raises: Exception | None = None) -> SimpleNamespace:
    seen: dict = {}

    class Models:
        def list(self) -> list:
            if raises is not None:
                raise raises
            return [SimpleNamespace(id=model) for model in ids or []]

    class Anthropic:
        def __init__(self, api_key: str) -> None:
            seen["api_key"] = api_key
            self.models = Models()

    return SimpleNamespace(Anthropic=Anthropic, AnthropicError=_AnthropicError, seen=seen)


@pytest.fixture
def run() -> RunState:
    return RunState()


def test_without_a_key_the_built_in_extended_list_is_offered(run: RunState, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aiutils, "import_optional", lambda *_: pytest.fail("the library was loaded"))
    run.ai["anthropic_key"] = ""

    assert aiutils.get_anthropic_models(state=run) == sorted(sysconst.ANTHROPIC_EXTENDED_MODELS)


def test_with_a_key_the_models_the_key_can_use_are_offered_sorted_and_only_claude_ones(
    run: RunState, monkeypatch: pytest.MonkeyPatch
) -> None:
    library = _fake_anthropic(ids=["claude-sonnet-9-9", "claude-fable-5-1", "not-a-claude", "claude-sonnet-9-9"])
    monkeypatch.setattr(aiutils, "import_optional", lambda *_: library)
    run.ai["anthropic_key"] = "sk-ant"

    assert aiutils.get_anthropic_models(state=run) == ["claude-fable-5-1", "claude-sonnet-9-9"]
    assert library.seen["api_key"] == "sk-ant"


def test_a_model_released_after_this_version_is_offered_when_the_key_can_use_it(
    run: RunState, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(aiutils, "import_optional", lambda *_: _fake_anthropic(ids=["claude-opus-6"]))
    run.ai["anthropic_key"] = "sk-ant"

    assert "claude-opus-6" in aiutils.get_anthropic_models(state=run)


def test_a_failure_to_list_gives_the_built_in_list_and_says_why(run: RunState, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aiutils, "import_optional", lambda *_: _fake_anthropic(raises=_AnthropicError("401")))
    reported: list[str] = []
    monkeypatch.setattr(aiutils, "rutroh_error", reported.append)
    run.ai["anthropic_key"] = "sk-ant"

    assert aiutils.get_anthropic_models(state=run) == sorted(sysconst.ANTHROPIC_EXTENDED_MODELS)
    assert any("401" in message for message in reported)


def test_a_bug_while_listing_is_not_mistaken_for_a_failed_request(
    run: RunState, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(aiutils, "import_optional", lambda *_: _fake_anthropic(raises=AttributeError("a bug")))
    run.ai["anthropic_key"] = "sk-ant"

    with pytest.raises(AttributeError):
        aiutils.get_anthropic_models(state=run)


@pytest.mark.parametrize("library", [None, "empty"])
def test_no_library_or_no_claude_model_gives_the_built_in_list(
    run: RunState, monkeypatch: pytest.MonkeyPatch, library: str | None
) -> None:
    monkeypatch.setattr(
        aiutils, "import_optional", lambda *_: None if library is None else _fake_anthropic(ids=["other"])
    )
    run.ai["anthropic_key"] = "sk-ant"

    assert aiutils.get_anthropic_models(state=run) == sorted(sysconst.ANTHROPIC_EXTENDED_MODELS)


# ##################################################################################
# Getting a local model ready.
# ##################################################################################
@pytest.mark.parametrize(
    ("asked", "installed", "expected"),
    [
        ("tinyllama", ["tinyllama:latest"], "tinyllama:latest"),
        ("tinyllama:latest", ["tinyllama:latest"], "tinyllama:latest"),
        ("llama3.1", ["llama3.1:8b"], "llama3.1:8b"),
        ("llama3.1:8b", ["llama3.1:8b"], "llama3.1:8b"),
        ("llama3.1 (installed)", ["llama3.1:8b"], "llama3.1:8b"),
        ("llama3.1", ["llama3.1:70b", "llama3.1:8b"], "llama3.1:70b"),  # the first alphabetically, not the first listed
        ("llama3.1:70b", ["llama3.1:8b"], None),  # a tag that is asked for must be that tag
        ("llama", ["llama3.1:8b"], None),  # not a prefix match
        ("mistral", ["tinyllama:latest"], None),
        ("", ["tinyllama:latest"], None),
        ("tinyllama", [], None),
    ],
)
def test_the_name_ollama_knows_a_model_by(asked: str, installed: list[str], expected: str | None) -> None:
    assert aiutils.installed_ollama_model(asked, installed) == expected


class _FakeOllama:
    """The ollama package: a list of installed models, and a pull that reports progress."""

    def __init__(
        self, installed: list[str], *, pull_steps: list[str] | None = None, pull_error: Exception | None = None
    ):
        self.installed = installed
        self.pull_steps = pull_steps or []
        self.pull_error = pull_error
        self.pulled: list[str] = []
        self.list_error: Exception | None = None

    def list(self) -> dict:
        if self.list_error is not None:
            raise self.list_error
        return {"models": [{"model": name} for name in self.installed]}

    def pull(self, name: str, stream: bool) -> list[dict]:
        assert stream is True
        self.pulled.append(name)
        if self.pull_error is not None:
            raise self.pull_error
        return [{"status": step} for step in self.pull_steps]


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """A running Ollama server holding no models yet; start_ollama_server and the library replaced."""
    setup = SimpleNamespace(ollama=_FakeOllama([]), start=(True, ""))
    monkeypatch.setattr(aiutils, "start_ollama_server", lambda: setup.start)
    monkeypatch.setattr(aiutils, "import_optional", lambda *_: setup.ollama)
    monkeypatch.setattr(aiutils, "ollama_errors", lambda: (ConnectionError,))
    return setup


def test_an_installed_model_is_ready_at_once_and_nothing_is_downloaded(server: SimpleNamespace) -> None:
    server.ollama = _FakeOllama(["llama3.1:8b"])
    said: list[str] = []

    assert aiutils.prepare_ollama_model("llama3.1 (installed)", say=said.append) == ("llama3.1:8b", "")
    assert server.ollama.pulled == []
    assert said == []


def test_a_model_that_is_not_installed_is_downloaded_with_its_progress_reported(server: SimpleNamespace) -> None:
    server.ollama = _FakeOllama(["tinyllama:latest"], pull_steps=["pulling manifest", "pulling manifest", "success"])
    said: list[str] = []

    assert aiutils.prepare_ollama_model("mistral", say=said.append) == ("mistral", "")
    assert server.ollama.pulled == ["mistral"]
    assert any("not installed" in line and "mistral" in line for line in said)
    assert [line for line in said if "pulling manifest" in line] == ["MapTasker: pulling manifest"], "each step once"
    assert any("success" in line for line in said)


def test_a_model_that_cannot_be_downloaded_says_why(server: SimpleNamespace) -> None:
    server.ollama = _FakeOllama([], pull_error=ConnectionError("no route"))

    model, reason = aiutils.prepare_ollama_model("nonesuch", say=lambda _line: None)

    assert model is None
    assert "nonesuch" in reason and "no route" in reason
    assert "ollama.com/library" in reason


def test_a_server_that_will_not_start_is_the_reason_given(server: SimpleNamespace) -> None:
    server.start = (False, "Ollama is not installed.  Please install the Ollama app.")

    assert aiutils.prepare_ollama_model("llama3.1") == (
        None,
        "Ollama is not installed.  Please install the Ollama app.",
    )


def test_a_server_that_stops_answering_before_the_list_is_reported(server: SimpleNamespace) -> None:
    server.ollama.list_error = ConnectionError("refused")

    model, reason = aiutils.prepare_ollama_model("llama3.1")

    assert model is None and "refused" in reason


def test_an_unexpected_answer_to_the_list_is_reported_rather_than_raised(server: SimpleNamespace) -> None:
    server.ollama.list = lambda: {"models": [{"nothing": "here"}]}

    model, reason = aiutils.prepare_ollama_model("llama3.1")

    assert model is None and "Unexpected response from Ollama" in reason


# ##################################################################################
# A saved choice of a service that is no longer supported.
# ##################################################################################
@pytest.mark.parametrize(
    "saved",
    [
        {"ai_name": "DeepSeek", "ai_model": "deepseek-chat"},
        {"ai_name": "DeepSeek", "ai_model": ""},
        {"ai_name": "", "ai_model": "deepseek-chat"},
        {"ai_name": "LLAMA", "ai_model": "deepseek-r1:1.5b"},
        {"ai_name": "LLAMA", "ai_model": "deepseek-coder (installed)"},
        {"ai_name": "LLAMA", "ai_model": "DeepSeek-R1"},
    ],
)
def test_a_saved_deepseek_selection_is_cleared(saved: dict) -> None:
    arguments = {**saved, "ai_apikey": "Hidden", "debug": False}

    assert getputer.drop_unsupported_ai_selection(arguments) is True

    assert (arguments["ai_name"], arguments["ai_model"]) == ("", "")
    assert arguments["debug"] is False, "nothing else is touched"


@pytest.mark.parametrize(
    "saved",
    [
        {"ai_name": "Anthropic", "ai_model": "claude-opus-5-5"},
        {"ai_name": "OpenAI", "ai_model": "gpt-5.5"},
        {"ai_name": "Gemini", "ai_model": "gemini-3.5-flash"},
        {"ai_name": "LLAMA", "ai_model": "llama3.1 (installed)"},
        {"ai_name": "", "ai_model": ""},
        {},
    ],
)
def test_a_selection_that_is_still_supported_is_left_alone(saved: dict) -> None:
    arguments = dict(saved)

    assert getputer.drop_unsupported_ai_selection(arguments) is False
    assert arguments == saved


def test_a_missing_or_blank_model_is_not_mistaken_for_a_retired_one() -> None:
    assert getputer.drop_unsupported_ai_selection({"ai_name": "OpenAI", "ai_model": None}) is False


# ##################################################################################
# Naming the service when the Analyze tab was not told.
# ##################################################################################
@pytest.fixture
def analysis(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """The Analyze button's handler, with everything round the analysis replaced and the analysis itself recorded."""
    setup = SimpleNamespace(ran=[], saved=[])
    state = RunState()
    gui = MagicMock(spec=MyGui)
    gui.state = state
    gui.ai_apikey = "the-key"
    gui.ai_name = ""
    gui.color_lookup = {}
    for label in ("project", "profile", "task", "scene"):
        setattr(gui, f"single_{label}_name", "")
    gui.single_task_name = "Noisy"
    gui.event_handlers = MagicMock()

    async def map_ai(state: RunState) -> None:
        setup.ran.append((state.program_arguments.ai_name, state.program_arguments.ai_model))

    monkeypatch.setattr(userintr_ai, "ui", MagicMock())
    monkeypatch.setattr(userintr_ai, "set_ai_key", lambda *_: True)
    monkeypatch.setattr(userintr_ai, "gui_settings", lambda _gui: {})
    monkeypatch.setattr(userintr_ai, "save_restore_args", lambda *a, **k: setup.saved.append(a) or ({}, {}))
    monkeypatch.setattr(userintr_ai, "build_analysis_lines", AsyncMock(return_value=True))
    monkeypatch.setattr(userintr_ai, "display_error_file_and_ai_response", lambda _self: None)
    monkeypatch.setattr(userintr_ai, "map_ai", map_ai)
    setup.gui = gui
    setup.handlers = MapTaskerEventHandlers(gui)
    return setup


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model", "named"),
    [
        ("claude-opus-5-5", "Anthropic"),
        ("claude-haiku-5-5", "Anthropic"),
        ("gemini-3.5-flash", "Gemini"),
        ("gpt-5.5", "OpenAI"),
        ("o3", "OpenAI"),
        ("o4-mini", "OpenAI"),
        ("llama3.1:8b", "LLAMA"),
        ("olmo2", "LLAMA"),  # begins with an "o", but is not an OpenAI model
        ("tinyllama", "LLAMA"),
    ],
)
async def test_a_model_chosen_without_its_service_is_run_by_the_name_the_analysis_dispatches_on(
    analysis: SimpleNamespace, model: str, named: str
) -> None:
    analysis.gui.ai_model = model

    await analysis.handlers.ai_analyze_event()

    assert analysis.ran == [(named, model)], "mapai looks the service up by this exact spelling"


@pytest.mark.asyncio
async def test_a_service_the_pulldown_named_is_kept(analysis: SimpleNamespace) -> None:
    analysis.gui.ai_model = "claude-opus-5-5"
    analysis.gui.ai_name = "Anthropic"

    await analysis.handlers.ai_analyze_event()

    assert analysis.ran == [("Anthropic", "claude-opus-5-5")]
