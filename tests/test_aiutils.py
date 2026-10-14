"""Finding AI models: starting Ollama, asking each provider for its list and falling back when it will not say."""

from __future__ import annotations

from types import ModuleType, SimpleNamespace

import pytest
from maptasker.src.core import aiutils


@pytest.fixture(autouse=True)
def _errors_are_connection_errors(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Ollama's error types come from the package itself; ConnectionError stands in for them here.
    Anything reported through rutroh_error is collected instead of shown."""
    monkeypatch.setattr(aiutils, "ollama_errors", lambda: (ConnectionError,))
    reported: list[str] = []
    monkeypatch.setattr(aiutils, "rutroh_error", reported.append)
    return reported


@pytest.fixture
def said(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    heard: list[str] = []
    monkeypatch.setattr(aiutils.console, "say", heard.append)
    return heard


class _Ollama:
    """The parts of the 'ollama' package these functions use."""

    def __init__(self, *, answers: list | None = None, models: list[str] | None = None) -> None:
        self.answers = list(answers) if answers is not None else []
        self.models = models or []
        self.pulled: list[str] = []
        self.pull_failure: Exception | None = None

    def list(self) -> dict:
        if self.answers:
            answer = self.answers.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return answer
        return {"models": [{"model": name} for name in self.models]}

    def pull(self, name: str, stream: bool = False) -> list[dict]:  # noqa: FBT001, FBT002
        if self.pull_failure:
            raise self.pull_failure
        self.pulled.append(name)
        return [{"status": "pulling"}, {"status": "pulling"}, {"status": "success"}, {}]


def _provide(monkeypatch: pytest.MonkeyPatch, **packages: object) -> None:
    monkeypatch.setattr(aiutils, "import_optional", lambda name, _module: packages.get(name))


# ##################################################################################
# Is a server up, and can one be started?
# ##################################################################################
def test_a_server_that_answers_is_responding() -> None:
    assert aiutils.ollama_is_responding(_Ollama()) is True


def test_a_server_that_refuses_is_not() -> None:
    assert aiutils.ollama_is_responding(_Ollama(answers=[ConnectionError("refused")])) is False


def test_without_the_package_no_server_can_be_started(monkeypatch: pytest.MonkeyPatch) -> None:
    _provide(monkeypatch)
    started, reason = aiutils.start_ollama_server()
    assert not started
    assert "'ollama' package is not installed" in reason


def test_a_server_already_up_is_left_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    _provide(monkeypatch, ollama=_Ollama())
    monkeypatch.setattr(aiutils.subprocess, "Popen", lambda *_a, **_k: pytest.fail("nothing to start"))
    assert aiutils.start_ollama_server() == (True, "")


def test_without_the_ollama_app_the_user_is_told_where_to_get_it(monkeypatch: pytest.MonkeyPatch) -> None:
    _provide(monkeypatch, ollama=_Ollama(answers=[ConnectionError("down")]))
    monkeypatch.setattr(aiutils.shutil, "which", lambda _name: None)
    started, reason = aiutils.start_ollama_server()
    assert not started
    assert aiutils.OLLAMA_DOWNLOAD_URL in reason


def test_a_server_that_cannot_be_launched_says_why(monkeypatch: pytest.MonkeyPatch, said: list[str]) -> None:
    _provide(monkeypatch, ollama=_Ollama(answers=[ConnectionError("down")]))
    monkeypatch.setattr(aiutils.shutil, "which", lambda _name: "/usr/bin/ollama")

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise OSError("exec format error")

    monkeypatch.setattr(aiutils.subprocess, "Popen", refuse)
    started, reason = aiutils.start_ollama_server()
    assert not started
    assert "exec format error" in reason


def test_a_server_that_comes_up_is_waited_for(monkeypatch: pytest.MonkeyPatch, said: list[str]) -> None:
    # Down when checked first, down once more after launching, then answering.
    ollama = _Ollama(answers=[ConnectionError("down"), ConnectionError("down")])
    _provide(monkeypatch, ollama=ollama)
    launched: list[list[str]] = []
    monkeypatch.setattr(aiutils.shutil, "which", lambda _name: "/usr/bin/ollama")
    monkeypatch.setattr(aiutils.subprocess, "Popen", lambda command, **_kw: launched.append(command))
    monkeypatch.setattr(aiutils.time, "sleep", lambda _seconds: None)

    assert aiutils.start_ollama_server() == (True, "")
    assert launched == [["ollama", "serve"]]
    assert any("is running" in line for line in said)


def test_a_server_that_never_comes_up_gives_up(monkeypatch: pytest.MonkeyPatch, said: list[str]) -> None:
    _provide(monkeypatch, ollama=_Ollama(answers=[ConnectionError("down")] * 100))
    monkeypatch.setattr(aiutils.shutil, "which", lambda _name: "/usr/bin/ollama")
    monkeypatch.setattr(aiutils.subprocess, "Popen", lambda *_a, **_k: None)
    monkeypatch.setattr(aiutils.time, "sleep", lambda _seconds: None)
    clock = iter([0.0, 0.0, 10.0, 31.0])
    monkeypatch.setattr(aiutils.time, "monotonic", lambda: next(clock))

    started, reason = aiutils.start_ollama_server()

    assert not started
    assert "did not start within 30 seconds" in reason


# ##################################################################################
# Naming installed models
# ##################################################################################
def test_a_name_with_no_tag_means_latest() -> None:
    assert aiutils.tagged_model_name("tinyllama") == "tinyllama:latest"
    assert aiutils.tagged_model_name("llama3.1:8b") == "llama3.1:8b"


@pytest.mark.parametrize(
    ("asked", "installed", "expected"),
    [
        ("tinyllama", ["tinyllama:latest"], "tinyllama:latest"),
        ("tinyllama (installed)", ["tinyllama:latest"], "tinyllama:latest"),
        ("llama3.1", ["llama3.1:8b", "llama3.1:70b"], "llama3.1:70b"),  # the alphabetically first tag
        ("llama3.1:8b", ["llama3.1:70b"], None),  # a tag that was asked for must be that tag
        ("phi4", ["tinyllama:latest"], None),
        ("", ["tinyllama:latest"], None),
    ],
)
def test_the_installed_name_for_a_model(asked: str, installed: list[str], expected: str | None) -> None:
    assert aiutils.installed_ollama_model(asked, installed) == expected


def test_installed_models_are_marked_and_the_users_extras_are_added() -> None:
    marked = aiutils.mark_installed_models(["tinyllama", "phi4"], ["tinyllama:latest", "mine:7b"])
    assert marked == ["tinyllama (installed)", "phi4", "mine:7b (installed)"]


# ##################################################################################
# Getting a model ready
# ##################################################################################
def test_no_server_means_no_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aiutils, "start_ollama_server", lambda: (False, "no server"))
    assert aiutils.prepare_ollama_model("phi4") == (None, "no server")


def test_an_installed_model_is_used_as_it_is(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aiutils, "start_ollama_server", lambda: (True, ""))
    _provide(monkeypatch, ollama=_Ollama(models=["phi4:latest"]))
    assert aiutils.prepare_ollama_model("phi4") == ("phi4:latest", "")


def test_a_missing_model_is_downloaded_with_progress_reported_once_per_step(
    monkeypatch: pytest.MonkeyPatch, said: list[str]
) -> None:
    monkeypatch.setattr(aiutils, "start_ollama_server", lambda: (True, ""))
    ollama = _Ollama(models=["other:latest"])
    _provide(monkeypatch, ollama=ollama)
    heard: list[str] = []

    assert aiutils.prepare_ollama_model("phi4", say=heard.append) == ("phi4", "")

    assert ollama.pulled == ["phi4"]
    assert heard.count("MapTasker: pulling") == 1  # a repeated status is not repeated to the user
    assert heard[-1] == "MapTasker: --- 'phi4' is installed. ---"


def test_a_download_that_fails_says_where_to_look(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aiutils, "start_ollama_server", lambda: (True, ""))
    ollama = _Ollama()
    ollama.pull_failure = ConnectionError("offline")
    _provide(monkeypatch, ollama=ollama)

    model, reason = aiutils.prepare_ollama_model("phi4", say=lambda _line: None)

    assert model is None
    assert "offline" in reason
    assert "ollama.com/library" in reason


def test_a_server_that_cannot_list_its_models_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aiutils, "start_ollama_server", lambda: (True, ""))
    _provide(monkeypatch, ollama=_Ollama(answers=[ConnectionError("dropped")]))
    model, reason = aiutils.prepare_ollama_model("phi4")
    assert model is None
    assert "dropped" in reason


def test_an_answer_of_the_wrong_shape_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aiutils, "start_ollama_server", lambda: (True, ""))
    _provide(monkeypatch, ollama=_Ollama(answers=[{"unexpected": []}]))
    model, reason = aiutils.prepare_ollama_model("phi4")
    assert model is None
    assert reason.startswith("Unexpected response from Ollama")


def test_a_package_that_vanished_between_checks_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aiutils, "start_ollama_server", lambda: (True, ""))
    _provide(monkeypatch)
    model, reason = aiutils.prepare_ollama_model("phi4")
    assert model is None
    assert "not installed" in reason


# ##################################################################################
# The local model list
# ##################################################################################
def test_without_the_package_the_built_in_list_is_offered(
    monkeypatch: pytest.MonkeyPatch, _errors_are_connection_errors: list[str]
) -> None:
    _provide(monkeypatch)
    models = aiutils.get_llama_models()
    assert "tinyllama" in models
    assert _errors_are_connection_errors


def test_installed_models_are_marked_in_the_list(monkeypatch: pytest.MonkeyPatch) -> None:
    _provide(monkeypatch, ollama=_Ollama(models=["tinyllama:latest", "mine:7b"]))
    models = aiutils.get_llama_models()
    assert "tinyllama (installed)" in models
    assert "mine:7b (installed)" in models
    assert models == sorted(models)


def test_a_server_that_was_down_is_started_and_asked_again(monkeypatch: pytest.MonkeyPatch) -> None:
    _provide(monkeypatch, ollama=_Ollama(answers=[ConnectionError("down")], models=["tinyllama:latest"]))
    monkeypatch.setattr(aiutils, "start_ollama_server", lambda: (True, ""))
    assert "tinyllama (installed)" in aiutils.get_llama_models()


def test_a_server_that_will_not_start_leaves_the_built_in_list(
    monkeypatch: pytest.MonkeyPatch, _errors_are_connection_errors: list[str]
) -> None:
    _provide(monkeypatch, ollama=_Ollama(answers=[ConnectionError("down")]))
    monkeypatch.setattr(aiutils, "start_ollama_server", lambda: (False, "not installed"))
    assert "tinyllama" in aiutils.get_llama_models()
    assert "not installed" in _errors_are_connection_errors


def test_a_server_that_fails_again_after_starting_leaves_the_built_in_list(
    monkeypatch: pytest.MonkeyPatch, _errors_are_connection_errors: list[str]
) -> None:
    _provide(monkeypatch, ollama=_Ollama(answers=[ConnectionError("down"), ConnectionError("still down")]))
    monkeypatch.setattr(aiutils, "start_ollama_server", lambda: (True, ""))
    assert "tinyllama" in aiutils.get_llama_models()
    assert any("still down" in line for line in _errors_are_connection_errors)


def test_an_answer_of_the_wrong_shape_leaves_the_built_in_list(
    monkeypatch: pytest.MonkeyPatch, _errors_are_connection_errors: list[str]
) -> None:
    _provide(monkeypatch, ollama=_Ollama(answers=[{"unexpected": []}]))
    assert "tinyllama" in aiutils.get_llama_models()
    assert any("Unexpected response" in line for line in _errors_are_connection_errors)


# ##################################################################################
# The cloud providers
# ##################################################################################
def test_no_openai_key_means_the_built_in_list() -> None:
    assert aiutils.get_openai_models(SimpleNamespace(ai={})) == aiutils.OPENAI_MODELS


def test_no_openai_package_means_the_built_in_list(monkeypatch: pytest.MonkeyPatch) -> None:
    _provide(monkeypatch)
    assert aiutils.get_openai_models(SimpleNamespace(ai={"openai_key": "k"})) == aiutils.OPENAI_MODELS


def _openai(models: list[str] | Exception) -> ModuleType:
    package = ModuleType("openai")

    class OpenAIError(Exception):
        pass

    class Client:
        def __init__(self, api_key: str) -> None:
            self.models = self

        def list(self) -> SimpleNamespace:
            if isinstance(models, Exception):
                raise OpenAIError(str(models))
            return SimpleNamespace(data=[SimpleNamespace(id=name) for name in models])

    package.OpenAIError = OpenAIError
    package.OpenAI = Client
    return package


def test_openai_models_are_filtered_to_the_ones_that_write_text(monkeypatch: pytest.MonkeyPatch) -> None:
    ids = ["gpt-5", "gpt-5-realtime", "whisper-1", "o3", "text-embedding-3", "gpt-4o-audio", "dall-e-3"]
    _provide(monkeypatch, openai=_openai(ids))
    listed = aiutils.get_openai_models(SimpleNamespace(ai={"openai_key": "k"}))
    assert listed == ["gpt-5", "o3"]


def test_an_openai_error_gives_the_built_in_list(
    monkeypatch: pytest.MonkeyPatch, _errors_are_connection_errors: list[str]
) -> None:
    _provide(monkeypatch, openai=_openai(RuntimeError("bad key")))
    assert aiutils.get_openai_models(SimpleNamespace(ai={"openai_key": "k"})) == aiutils.OPENAI_MODELS
    assert any("bad key" in line for line in _errors_are_connection_errors)


def test_an_empty_openai_answer_gives_the_built_in_list(monkeypatch: pytest.MonkeyPatch) -> None:
    _provide(monkeypatch, openai=_openai([]))
    assert aiutils.get_openai_models(SimpleNamespace(ai={"openai_key": "k"})) == aiutils.OPENAI_MODELS


def test_no_anthropic_key_means_the_built_in_list() -> None:
    assert aiutils.get_anthropic_models(SimpleNamespace(ai={})) == sorted(aiutils.ANTHROPIC_EXTENDED_MODELS)


def test_no_anthropic_package_means_the_built_in_list(monkeypatch: pytest.MonkeyPatch) -> None:
    _provide(monkeypatch)
    assert aiutils.get_anthropic_models(SimpleNamespace(ai={"anthropic_key": "k"})) == sorted(
        aiutils.ANTHROPIC_EXTENDED_MODELS
    )


def _anthropic(ids: list[str] | Exception) -> ModuleType:
    package = ModuleType("anthropic")

    class AnthropicError(Exception):
        pass

    class Client:
        def __init__(self, api_key: str) -> None:
            self.models = self

        def list(self) -> list[SimpleNamespace]:
            if isinstance(ids, Exception):
                raise AnthropicError(str(ids))
            return [SimpleNamespace(id=name) for name in ids]

    package.AnthropicError = AnthropicError
    package.Anthropic = Client
    return package


def test_anthropic_models_are_what_the_key_can_use(monkeypatch: pytest.MonkeyPatch) -> None:
    _provide(monkeypatch, anthropic=_anthropic(["claude-b", "claude-a", "claude-a", "other-model"]))
    assert aiutils.get_anthropic_models(SimpleNamespace(ai={"anthropic_key": "k"})) == ["claude-a", "claude-b"]


def test_an_anthropic_answer_with_no_claude_model_gives_the_built_in_list(monkeypatch: pytest.MonkeyPatch) -> None:
    _provide(monkeypatch, anthropic=_anthropic(["other-model"]))
    assert aiutils.get_anthropic_models(SimpleNamespace(ai={"anthropic_key": "k"})) == sorted(
        aiutils.ANTHROPIC_EXTENDED_MODELS
    )


def test_an_anthropic_error_gives_the_built_in_list(
    monkeypatch: pytest.MonkeyPatch, _errors_are_connection_errors: list[str]
) -> None:
    _provide(monkeypatch, anthropic=_anthropic(RuntimeError("no network")))
    assert aiutils.get_anthropic_models(SimpleNamespace(ai={"anthropic_key": "k"})) == sorted(
        aiutils.ANTHROPIC_EXTENDED_MODELS
    )
    assert any("no network" in line for line in _errors_are_connection_errors)


def _genai(names: list[tuple[str, list[str]]] | Exception | None) -> ModuleType:
    package = ModuleType("google.genai")

    class Client:
        def __init__(self, api_key: str) -> None:
            self.models = self

        def list(self) -> object:
            if isinstance(names, Exception):
                raise names
            if names is None:
                return []
            return SimpleNamespace(
                _page=[SimpleNamespace(name=f"models/{name}", supported_actions=actions) for name, actions in names],
            )

    package.Client = Client
    return package


def test_gemini_models_keep_only_the_ones_that_generate_text(monkeypatch: pytest.MonkeyPatch) -> None:
    _provide(
        monkeypatch,
        **{
            "google-genai": _genai(
                [
                    ("gemini-2.5-pro", ["generateContent"]),
                    ("gemini-embedding", ["embedContent"]),
                    ("gemini-2.5-flash-image", ["generateContent"]),
                    ("imagen-4", ["generateContent"]),
                ]
            )
        },
    )
    assert aiutils.get_gemini_models(SimpleNamespace(ai={"gemini_key": "k"})) == ["gemini-2.5-pro"]


def test_no_gemini_key_means_the_built_in_list() -> None:
    assert aiutils.get_gemini_models(SimpleNamespace(ai={"gemini_key": ""})) == aiutils.GEMINI_MODELS


def test_no_gemini_package_means_the_built_in_list(monkeypatch: pytest.MonkeyPatch) -> None:
    _provide(monkeypatch)
    assert aiutils.get_gemini_models(SimpleNamespace(ai={"gemini_key": "k"})) == aiutils.GEMINI_MODELS


def test_an_empty_gemini_answer_gives_the_built_in_list(monkeypatch: pytest.MonkeyPatch) -> None:
    _provide(monkeypatch, **{"google-genai": _genai(None)})
    assert aiutils.get_gemini_models(SimpleNamespace(ai={"gemini_key": "k"})) == aiutils.GEMINI_MODELS


def test_gemini_with_nothing_usable_says_so(
    monkeypatch: pytest.MonkeyPatch, _errors_are_connection_errors: list[str]
) -> None:
    _provide(monkeypatch, **{"google-genai": _genai([("imagen-4", ["generateContent"])])})
    assert aiutils.get_gemini_models(SimpleNamespace(ai={"gemini_key": "k"})) == []
    assert any("No Gemini models found" in line for line in _errors_are_connection_errors)


# ##################################################################################
# Saved keys
# ##################################################################################
def test_with_no_saved_keys_the_ai_settings_are_left_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aiutils, "load_api_keys", lambda: {"api_key": "", "openai_key": ""})
    state = SimpleNamespace(ai={"api_key": "keep"})
    assert aiutils.get_api_key(state) == "None"
    assert state.ai == {"api_key": "keep"}


def test_saved_keys_are_copied_into_the_ai_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aiutils, "load_api_keys", lambda: {"api_key": "secret", "openai_key": "other"})
    state = SimpleNamespace(ai={})
    assert aiutils.get_api_key(state) == "secret"
    assert state.ai["openai_key"] == "other"
