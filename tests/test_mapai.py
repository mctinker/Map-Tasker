"""mapai: sending a Tasker object to an AI service and writing down what came back.

mapask (the plain-words Find) and mapdraft are tested with a function standing in for the
model; this is the older analysis path, which talks to each provider's own library.  Those
libraries are optional extras and are never installed on the machines these tests run on --
and must not be reached even where they are -- so every provider is a stand-in object whose
calls are recorded.

What matters: that each provider is called the way its library is called, that a failure of
any kind ends up as a sentence in the error file the GUI reads (rather than a traceback in a
worker thread), that nothing is sent from the wrong provider, and that the text sent is the
Map's text, not its HTML.
"""

from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest
from maptasker.src import console, mapai
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.primitem import RunState
from maptasker.src.sysconst import ANALYSIS_FILE, ERROR_FILE


@pytest.fixture
def state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RunState:
    """A run with an AI model chosen, writing its files into a temporary folder."""
    monkeypatch.chdir(tmp_path)
    run = RunState()
    run.program_arguments = initialize_runtime_arguments()
    run.program_arguments.ai_name = "Anthropic"
    run.program_arguments.ai_model = "claude-sonnet-5"
    run.program_arguments.ai_apikey = "sk-test"
    run.output_lines = SimpleNamespace(output_lines=[])
    monkeypatch.setattr(mapai, "output_path", lambda name, state: str(tmp_path / name))
    return run


def _error_text(tmp_path: Path) -> str:
    return (tmp_path / ERROR_FILE).read_text(encoding="utf-8")


@pytest.fixture
def reported(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int]]:
    """error_handler records what it was told instead of ending the run."""
    errors: list[tuple[str, int]] = []
    monkeypatch.setattr(mapai, "error_handler", lambda message, code, **_: errors.append((message, code)))
    return errors


# ##################################################################################
# Keys.
# ##################################################################################
@pytest.mark.parametrize(
    ("key", "valid"),
    [
        ("AIzaSy" + "a" * 33, True),
        ("AIzaSy" + "A1_-" * 8 + "z", True),
        ("AIzaSy" + "a" * 32, False),
        ("AIzaSy" + "a" * 34, False),
        ("BIzaSy" + "a" * 33, False),
        ("", False),
    ],
)
def test_a_gemini_key_has_a_fixed_shape(key: str, valid: bool) -> None:
    assert mapai.valid_api_key("gemini_key", key) is valid


@pytest.mark.parametrize(
    ("key", "valid"),
    [("a" * 32, True), ("A1_-" * 8, True), ("a" * 31, False), ("a" * 33, False), ("a" * 31 + "!", False), ("", False)],
)
def test_a_deepseek_key_is_thirty_two_plain_characters(key: str, valid: bool) -> None:
    assert mapai.valid_api_key("deepseek_key", key) is valid
    assert mapai.valid_api_key("anything_else", key) is valid


class _OpenAIError(Exception):
    pass


def _fake_openai(*, key_ok: bool) -> SimpleNamespace:
    seen = {}

    class Models:
        def list(self) -> list:
            if not key_ok:
                raise _OpenAIError("bad key")
            return []

    class OpenAI:
        def __init__(self, api_key: str) -> None:
            seen["api_key"] = api_key
            self.models = Models()

    return SimpleNamespace(OpenAI=OpenAI, OpenAIError=_OpenAIError, seen=seen)


def test_an_openai_key_is_valid_if_it_can_list_models(monkeypatch: pytest.MonkeyPatch) -> None:
    library = _fake_openai(key_ok=True)
    monkeypatch.setattr(mapai, "import_optional", lambda *_: library)

    assert mapai.valid_api_key("openai_key", "sk-x") is True
    assert library.seen["api_key"] == "sk-x"


def test_an_openai_key_that_cannot_list_models_is_not_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mapai, "import_optional", lambda *_: _fake_openai(key_ok=False))

    assert mapai.valid_api_key("openai_key", "sk-x") is False


def test_a_provider_that_is_not_installed_has_no_valid_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mapai, "import_optional", lambda *_: None)

    assert mapai.valid_api_key("openai_key", "sk-x") is False
    assert mapai.valid_api_key("anthropic_key", "sk-x") is False


def test_an_anthropic_key_is_valid_if_it_can_list_models(monkeypatch: pytest.MonkeyPatch) -> None:
    class AnthropicError(Exception):
        pass

    def library(*, ok: bool) -> SimpleNamespace:
        class Models:
            def list(self) -> list:
                if not ok:
                    raise AnthropicError("401")
                return []

        class Anthropic:
            def __init__(self, api_key: str) -> None:
                self.models = Models()

        return SimpleNamespace(Anthropic=Anthropic, AnthropicError=AnthropicError)

    monkeypatch.setattr(mapai, "import_optional", lambda *_: library(ok=True))
    assert mapai.valid_api_key("anthropic_key", "sk-ant") is True

    monkeypatch.setattr(mapai, "import_optional", lambda *_: library(ok=False))
    assert mapai.valid_api_key("anthropic_key", "sk-ant") is False


def test_a_module_is_found_without_being_imported() -> None:
    assert mapai.module_is_available("json") is True
    assert mapai.module_is_available("definitely_not_installed_anywhere") is False
    assert (
        mapai.module_is_available("definitely_not_installed.sub") is False
    )  # A parent that is missing is not an error.


# ##################################################################################
# What is sent.
# ##################################################################################
def test_the_model_is_sent_the_object_as_text_without_the_maps_front_matter(state: RunState) -> None:
    state.output_lines.output_lines = [
        "MapTasker Version 14",
        "Current Tasker configuration",
        "Project: <span class='c'>Home</span>&nbsp;&nbsp;[Enabled]",
        "",
        "  Profile: Morning &#11013; <b>on</b>",
        "<br>",
        "&nbsp;&nbsp;Task: Noisy &amp; loud",
    ]

    assert mapai.cleanup_output(state=state) == [
        "Project: Home  [Enabled]",
        "  Profile: Morning ⬅ on",  # The indentation is the hierarchy, and is kept.
        "  Task: Noisy & loud",
    ]


def test_the_object_stops_where_the_project_s_loose_tasks_begin(state: RunState) -> None:
    state.output_lines.output_lines = [
        "Project: P",
        "Profile: A",
        "Tasks not in any Profile, but in Project P",
        "Task: Stray",
    ]

    assert mapai.cleanup_output(state=state) == ["Project: P", "Profile: A"]


def test_nothing_before_the_first_profile_project_or_task_line_is_sent(state: RunState) -> None:
    state.output_lines.output_lines = ["Secret preamble", "Another line"]

    assert mapai.cleanup_output(state=state) == []


def test_a_task_alone_is_enough_to_start(state: RunState) -> None:
    state.output_lines.output_lines = ["junk", "Task: Only", "Action: 1"]

    assert mapai.cleanup_output(state=state) == ["Task: Only", "Action: 1"]


# ##################################################################################
# What comes back.
# ##################################################################################
def test_a_response_is_saved_and_queued_for_the_gui(state: RunState, tmp_path: Path) -> None:
    mapai.record_response("It flashes text.", "Task", "Noisy", state=state)

    saved = (tmp_path / ANALYSIS_FILE).read_text(encoding="utf-8")
    assert saved.startswith('Anthropic AI Response using model claude-sonnet-5 for Task "Noisy":')
    assert saved.endswith("It flashes text.")
    queued = _error_text(tmp_path)
    assert "AI Response using model claude-sonnet-5 for Task Noisy" in queued  # guiutils recognizes it by this.
    assert "It flashes text." in queued
    assert f"saved in file: {ANALYSIS_FILE.split('.')[0]}-date-time.txt" in queued


@pytest.mark.parametrize(
    ("error", "model", "expected"),
    [
        ("Request too large for model", "claude-sonnet-5", "Task too large for ChatGPT or ChatGPT quota not enough!"),
        ("'Incorrect API key provided: sk-...", "claude-sonnet-5", "Invalid ChatGPT API key provided!"),
        (
            "Error code: 401 - bad",
            "deepseek-chat",
            "DeepSeek error code 401...possible invalid DeepSeek API key provided!",
        ),
        ("Error code: 500 - down", "deepseek-chat", "Refer to DeepSeek error codes"),
        ("Something else entirely", "claude-sonnet-5", "Something else entirely"),
        ("Error code: 401", "claude-sonnet-5", "Error code: 401"),  # Only DeepSeek's codes are explained.
    ],
)
def test_a_known_failure_is_explained_and_an_unknown_one_is_passed_on(
    state: RunState, tmp_path: Path, error: str, model: str, expected: str
) -> None:
    state.program_arguments.ai_model = model

    mapai.process_error(error, "Task", "Noisy", state=state)

    assert expected in _error_text(tmp_path)


def test_a_401_from_deepseek_gets_the_extra_line_and_a_500_does_not(state: RunState, tmp_path: Path) -> None:
    state.program_arguments.ai_model = "deepseek-chat"

    mapai.process_error("Error code: 500", "Task", "t", state=state)

    assert "401" not in _error_text(tmp_path)


# ##################################################################################
# Each provider, called the way its library is called.
# ##################################################################################
def test_openai_is_sent_the_role_and_the_query_and_the_stream_is_joined(state: RunState) -> None:
    sent = {}

    def create(**kwargs: object) -> list:
        sent.update(kwargs)
        return [
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=text))])
            for text in ("It ", None, "does ", "this.")
        ]

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    state.program_arguments.ai_model = "gpt-5"

    assert mapai._process_openai_response(client, "the query", state=state) == "It does this."  # noqa: SLF001
    assert sent["model"] == "gpt-5"
    assert sent["stream"] is True
    assert sent["messages"][0] == {"role": "system", "content": mapai.ai_role}
    assert sent["messages"][1]["content"] == [{"type": "text", "text": "the query"}]


def test_the_o1_models_take_their_role_as_a_user_message(state: RunState) -> None:
    sent = {}
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: sent.update(kw) or []))
    )
    state.program_arguments.ai_model = "o1-preview"

    mapai._process_openai_response(client, "q", state=state)  # noqa: SLF001

    assert sent["messages"][0]["role"] == "user"


def test_anthropic_gets_room_to_think_and_only_the_text_blocks_are_kept(state: RunState) -> None:
    sent = {}

    def create(**kwargs: object) -> SimpleNamespace:
        sent.update(kwargs)
        return SimpleNamespace(
            content=[
                SimpleNamespace(type="thinking", thinking="hmm"),
                SimpleNamespace(type="text", text="Part one. "),
                SimpleNamespace(type="text", text="Part two."),
            ],
        )

    client = SimpleNamespace(messages=SimpleNamespace(create=create))

    assert mapai._process_anthropic_response(client, "the query", state=state) == "Part one. Part two."  # noqa: SLF001
    assert sent["model"] == "claude-sonnet-5"
    assert sent["max_tokens"] == 16000
    assert sent["system"] == mapai.ai_role
    assert sent["messages"] == [{"role": "user", "content": "the query"}]


def test_deepseek_is_asked_for_a_deterministic_short_reply(state: RunState) -> None:
    sent = {}

    def create(**kwargs: object) -> SimpleNamespace:
        sent.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Answer."))])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    state.program_arguments.ai_model = "deepseek-chat"

    assert mapai._process_deepseek_response(client, "q", state=state) == "Answer."  # noqa: SLF001
    assert (sent["temperature"], sent["stream"], sent["max_tokens"]) == (0.0, False, 1024)
    assert sent["messages"][0]["role"] == "system"


def test_gemini_is_given_no_tools_to_call(state: RunState) -> None:
    sent = {}

    def generate(**kwargs: object) -> SimpleNamespace:
        sent.update(kwargs)
        return SimpleNamespace(text="Gemini says.")

    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    state.program_arguments.ai_model = "gemini-3-pro"

    assert mapai._process_gemini_response(client, "the query", state=state) == "Gemini says."  # noqa: SLF001
    assert sent["config"] == {"automatic_function_calling": {"disable": True}}
    assert sent["contents"].endswith("the query")
    assert sent["contents"].startswith(mapai.ai_role)


# ##################################################################################
# The dispatcher, and its failures.
# ##################################################################################
def test_a_successful_query_is_recorded(state: RunState, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mapai, "_process_anthropic_response", lambda client, query, state: "Fine.")

    mapai.process_ai_query_and_response(object(), "q", "Task", "Noisy", state=state)

    assert "Fine." in (tmp_path / ANALYSIS_FILE).read_text(encoding="utf-8")


def test_each_ai_name_goes_to_its_own_processor(
    state: RunState, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = []
    for name, function in (
        ("OpenAI", "_process_openai_response"),
        ("Anthropic", "_process_anthropic_response"),
        ("DeepSeek", "_process_deepseek_response"),
        ("Gemini", "_process_gemini_response"),
    ):
        monkeypatch.setattr(mapai, function, lambda client, query, state, name=name: called.append(name) or name)

    for name in ("OpenAI", "Anthropic", "DeepSeek", "Gemini"):
        state.program_arguments.ai_name = name
        mapai.process_ai_query_and_response(object(), "q", "Task", "t", state=state)

    assert called == ["OpenAI", "Anthropic", "DeepSeek", "Gemini"]


def test_a_name_no_processor_knows_is_reported(state: RunState, reported: list) -> None:
    state.program_arguments.ai_name = "Nobody"

    mapai.process_ai_query_and_response(object(), "q", "Task", "t", state=state)

    assert reported == [("Invalid AI name selected.", 12)]


def test_any_failure_becomes_a_sentence_in_the_error_file_not_a_traceback(
    state: RunState, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(client: object, query: str, state: RunState) -> str:
        raise RuntimeError("the socket fell over")

    monkeypatch.setattr(mapai, "_process_anthropic_response", broken)

    mapai.process_ai_query_and_response(object(), "q", "Task", "t", state=state)  # Must not raise.

    assert "failed with error: the socket fell over" in _error_text(tmp_path)
    assert not (tmp_path / ANALYSIS_FILE).exists()


@pytest.mark.parametrize(
    ("model", "message", "expected"),
    [
        ("gpt-5", "anything at all", "OpenAI failed with error: anything at all"),
        ("claude-sonnet-5", "Error: invalid x-api-key", "Invalid Anthropic API key provided"),
        ("gemini-3-pro", "API key not valid. Please pass a valid API key.", "Invalid Gemini API key provided"),
        ("claude-sonnet-5", "Connection error.", "Connection Error: Check your firewall."),
        ("deepseek-chat", "boom", "DeepSeek failed with error: boom"),
        ("not-a-model", "boom", "Unknown failed with error: boom"),
    ],
)
def test_a_provider_s_failure_is_put_in_words(state: RunState, model: str, message: str, expected: str) -> None:
    state.program_arguments.ai_model = model
    state.ai["openai_models"] = ["gpt-5"]
    state.ai["anthropic_models"] = ["claude-sonnet-5"]
    state.ai["gemini_models"] = ["gemini-3-pro"]
    state.ai["deepseek_models"] = ["deepseek-chat"]

    assert expected in mapai.handle_ai_error(RuntimeError(message), state=state)


# ##################################################################################
# Starting each provider.
# ##################################################################################
def _library(**members: object) -> SimpleNamespace:
    return SimpleNamespace(**members)


def test_claude_is_started_with_the_key_and_given_the_query(state: RunState, monkeypatch: pytest.MonkeyPatch) -> None:
    made = {}
    handed = {}
    monkeypatch.setattr(
        mapai, "import_optional", lambda *_: _library(Anthropic=lambda api_key: made.update(key=api_key) or "CLIENT")
    )
    monkeypatch.setattr(
        mapai,
        "process_ai_query_and_response",
        lambda client, query, ai_object, item, state: handed.update(client=client, query=query),
    )

    mapai.claude_ai("the query", "Task", "t", state=state)

    assert made == {"key": "sk-test"}
    assert handed == {"client": "CLIENT", "query": "the query"}


def test_deepseek_is_the_openai_library_pointed_at_deepseek(state: RunState, monkeypatch: pytest.MonkeyPatch) -> None:
    made = {}
    monkeypatch.setattr(
        mapai, "import_optional", lambda *_: _library(OpenAI=lambda **kwargs: made.update(kwargs) or "CLIENT")
    )
    monkeypatch.setattr(mapai, "process_ai_query_and_response", lambda *args, **kwargs: made.update(done=True))

    mapai.deepseek_ai("q", "Task", "t", state=state)

    assert made == {"api_key": "sk-test", "base_url": "https://api.deepseek.com", "done": True}


def test_gemini_is_started_with_the_key(state: RunState, monkeypatch: pytest.MonkeyPatch) -> None:
    made = {}
    monkeypatch.setattr(
        mapai, "import_optional", lambda *_: _library(Client=lambda api_key: made.update(key=api_key) or "CLIENT")
    )
    monkeypatch.setattr(mapai, "process_ai_query_and_response", lambda *args, **kwargs: made.update(done=True))

    mapai.gemini_ai("q", "Task", "t", state=state)

    assert made == {"key": "sk-test", "done": True}


def test_openai_asks_for_a_hidden_key_to_be_fetched_from_where_it_is_kept(
    state: RunState, monkeypatch: pytest.MonkeyPatch
) -> None:
    made = {}
    state.program_arguments.ai_apikey = "Hidden"
    state.program_arguments.ai_analyze = True
    monkeypatch.setattr(mapai, "module_is_available", lambda name: True)
    monkeypatch.setattr(mapai, "get_api_key", lambda state: state.ai.update(openai_key="the-real-key"))
    monkeypatch.setattr(
        mapai, "import_optional", lambda *_: _library(OpenAI=lambda api_key: made.update(key=api_key) or "CLIENT")
    )
    monkeypatch.setattr(mapai, "process_ai_query_and_response", lambda *args, **kwargs: made.update(done=True))

    mapai.open_ai("q", "Task", "t", state=state)

    assert made == {"key": "the-real-key", "done": True}


def test_openai_uses_the_key_it_was_given_when_it_is_not_hidden(
    state: RunState, monkeypatch: pytest.MonkeyPatch
) -> None:
    made = {}
    monkeypatch.setattr(mapai, "get_api_key", lambda state: pytest.fail("the keyring was asked"))
    monkeypatch.setattr(
        mapai, "import_optional", lambda *_: _library(OpenAI=lambda api_key: made.update(key=api_key) or "CLIENT")
    )
    monkeypatch.setattr(mapai, "process_ai_query_and_response", lambda *args, **kwargs: None)

    mapai.open_ai("q", "Task", "t", state=state)

    assert made == {"key": "sk-test"}


@pytest.mark.parametrize(
    ("starter", "needs_message"),
    [("claude_ai", "Module 'anthropic' not found"), ("gemini_ai", "Module 'google-genai' not found")],
)
def test_a_provider_that_is_not_installed_is_reported_with_how_to_install_it(
    state: RunState, reported: list, monkeypatch: pytest.MonkeyPatch, starter: str, needs_message: str
) -> None:
    monkeypatch.setattr(mapai, "import_optional", lambda *_: None)
    monkeypatch.setattr(mapai, "process_ai_query_and_response", lambda *args, **kwargs: pytest.fail("a query was sent"))

    getattr(mapai, starter)("q", "Task", "t", state=state)

    assert needs_message in reported[0][0]
    assert mapai.AI_EXTRA_INSTALL_COMMAND in reported[0][0]
    assert reported[0][1] == 12


def test_openai_that_is_not_installed_is_reported_before_the_key_is_looked_up(
    state: RunState, reported: list, monkeypatch: pytest.MonkeyPatch
) -> None:
    state.program_arguments.ai_analyze = True
    monkeypatch.setattr(mapai, "module_is_available", lambda name: False)
    monkeypatch.setattr(mapai, "get_api_key", lambda state: pytest.fail("the keyring was asked"))

    mapai.open_ai("q", "Task", "t", state=state)

    assert "Module 'openai' not found" in reported[0][0]


def test_a_library_that_cannot_be_loaded_ends_quietly_for_openai_and_deepseek(
    state: RunState, monkeypatch: pytest.MonkeyPatch
) -> None:
    """import_optional has already said why; there is nothing more to do."""
    monkeypatch.setattr(mapai, "import_optional", lambda *_: None)
    monkeypatch.setattr(mapai, "process_ai_query_and_response", lambda *args, **kwargs: pytest.fail("a query was sent"))

    mapai.deepseek_ai("q", "Task", "t", state=state)
    mapai.open_ai("q", "Task", "t", state=state)


# ##################################################################################
# Local models.
# ##################################################################################
def _fake_cria(chunks: list[str], *, record: dict | None = None, raises: Exception | None = None) -> types.ModuleType:
    module = types.ModuleType("maptasker.src.cria")

    class Cria:
        def __init__(self) -> None:
            if raises is not None:
                raise raises

    class Model:
        def __init__(self, name: str, state: object) -> None:
            if record is not None:
                record["model"] = name

        def __enter__(self) -> Model:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def chat(self, messages: list, prompt: str) -> list[str]:
            if record is not None:
                record.update(messages=messages, prompt=prompt)
            return chunks

        def clear(self) -> None:
            if record is not None:
                record["cleared"] = True

    module.Cria = Cria
    module.Model = Model
    return module


def test_a_local_model_answers_and_the_answer_is_recorded(
    state: RunState, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict = {}
    monkeypatch.setitem(sys.modules, "maptasker.src.cria", _fake_cria(["It ", "does ", "things."], record=seen))
    monkeypatch.setattr(console, "say", lambda *_: None)
    state.program_arguments.ai_name = "LLAMA"
    state.program_arguments.ai_model = "llama3"
    state.program_arguments.ai_analyze = True

    mapai.local_ai("Analyze this:Task data", "Task", "Noisy", state=state)

    assert seen["model"] == "llama3"
    assert seen["cleared"] is True
    assert seen["messages"][0]["role"] == "system"
    assert seen["messages"][1]["role"] == "user"
    assert "It does things." in (tmp_path / ANALYSIS_FILE).read_text(encoding="utf-8")
    assert state.program_arguments.ai_analyze is False  # So a failure does not come back round.


def test_a_local_model_that_is_not_chosen_is_reported(
    state: RunState, reported: list, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "maptasker.src.cria", _fake_cria([]))
    state.program_arguments.ai_model = "None"

    mapai.local_ai("q:x", "Task", "t", state=state)

    assert reported == [("No model selected.", 12)]


def test_ollama_not_being_installed_is_reported_not_raised(
    state: RunState, reported: list, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "maptasker.src.cria", _fake_cria([], raises=FileNotFoundError("ollama")))
    monkeypatch.setattr(console, "say", lambda *_: None)
    state.program_arguments.ai_model = "llama3"

    mapai.local_ai("q:x", "Task", "t", state=state)

    assert reported and "Ai analysis error: ollama" in reported[0][0]
    assert state.program_arguments.ai_analyze is False


def test_the_local_libraries_failing_to_load_is_reported_with_how_to_fix_it(
    state: RunState, reported: list, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "maptasker.src.cria", None)  # An import of None raises ImportError.

    mapai.local_ai("q:x", "Task", "t", state=state)

    assert "Ollama support could not be loaded" in reported[0][0]
    assert mapai.AI_EXTRA_INSTALL_COMMAND in reported[0][0]
    assert mapai.OLLAMA_DOWNLOAD_URL in reported[0][0]


# ##################################################################################
# Running it all, off the event loop.
# ##################################################################################
class _Popup:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def worker(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """The provider functions and the thread pool, replaced: what was run is recorded."""
    calls = SimpleNamespace(ran=[], said=[])

    async def io_bound(function: object, *args: object, **kwargs: object) -> None:
        calls.ran.append((function, args, kwargs))

    monkeypatch.setattr(mapai.run, "io_bound", io_bound)
    monkeypatch.setattr(console, "say", calls.said.append)
    monkeypatch.setattr(mapai, "get_ai_object", lambda: ("Task", "Noisy"))
    return calls


@pytest.mark.parametrize(
    ("name", "function"),
    [
        ("OpenAI", "open_ai"),
        ("Anthropic", "claude_ai"),
        ("DeepSeek", "deepseek_ai"),
        ("Gemini", "gemini_ai"),
        ("LLAMA", "local_ai"),
    ],
)
def test_each_ai_name_runs_its_own_worker(state: RunState, worker: SimpleNamespace, name: str, function: str) -> None:
    state.program_arguments.ai_name = name
    state.output_lines.output_lines = ["Task: Noisy", "Action: 1"]

    asyncio.run(mapai._run_analysis_in_background(_Popup(), state=state))  # noqa: SLF001

    assert [call[0] for call in worker.ran] == [getattr(mapai, function)]


def test_the_query_names_the_object_carries_the_prompt_and_every_line(state: RunState, worker: SimpleNamespace) -> None:
    state.output_lines.output_lines = ["Task: Noisy", "Action: 1", "Action: 2"]
    state.program_arguments.ai_prompt = "Explain it"

    asyncio.run(mapai._run_analysis_in_background(_Popup(), state=state))  # noqa: SLF001

    _function, args, kwargs = worker.ran[0]
    query, ai_object, item = args
    assert (
        query
        == "Given the following Task in Tasker, an Android automation tool, Explain it:Task: Noisy\nAction: 1\nAction: 2\n"
    )
    assert (ai_object, item) == ("Task", "Noisy")
    assert kwargs == {"state": state}


def test_a_prompt_that_already_ends_in_a_colon_is_not_given_another(state: RunState, worker: SimpleNamespace) -> None:
    state.program_arguments.ai_prompt = "Explain it:"

    asyncio.run(mapai._run_analysis_in_background(_Popup(), state=state))  # noqa: SLF001

    assert "Explain it:" in worker.ran[0][1][0]
    assert "::" not in worker.ran[0][1][0]


def test_no_prompt_means_the_default_one(state: RunState, worker: SimpleNamespace) -> None:
    state.program_arguments.ai_prompt = ""

    asyncio.run(mapai._run_analysis_in_background(_Popup(), state=state))  # noqa: SLF001

    assert mapai.AI_PROMPT in worker.ran[0][1][0]


def test_the_popup_is_closed_and_analysis_marked_done_whatever_happens(
    state: RunState, worker: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing(*_: object, **__: object) -> None:
        raise RuntimeError("worker died")

    monkeypatch.setattr(mapai.run, "io_bound", failing)
    popup = _Popup()
    state.program_arguments.ai_analyze = True

    with pytest.raises(RuntimeError, match="worker died"):
        asyncio.run(mapai._run_analysis_in_background(popup, state=state))  # noqa: SLF001

    assert popup.closed is True
    assert state.program_arguments.ai_analyze is False


def test_a_popup_that_holds_its_dialog_is_closed_through_it(state: RunState, worker: SimpleNamespace) -> None:
    popup = SimpleNamespace(dialog=_Popup())

    asyncio.run(mapai._run_analysis_in_background(popup, state=state))  # noqa: SLF001

    assert popup.dialog.closed is True


def test_no_popup_is_no_problem(state: RunState, worker: SimpleNamespace) -> None:
    asyncio.run(mapai._run_analysis_in_background(None, state=state))  # noqa: SLF001


def test_a_blank_ai_name_is_reported_not_run(state: RunState, worker: SimpleNamespace, reported: list) -> None:
    state.program_arguments.ai_name = ""

    asyncio.run(mapai._run_analysis_in_background(_Popup(), state=state))  # noqa: SLF001
    worker.ran[0][0]("q", "Task", "t", state=state)  # What io_bound would have run.

    assert reported == [("Invalid model selected (AI name is blank).", 12)]


def test_map_ai_shows_a_popup_then_runs_the_analysis(
    state: RunState, worker: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    popup = _Popup()
    titles = []
    monkeypatch.setattr(mapai, "create_popup_window", lambda title, body: titles.append((title, body)) or popup)

    asyncio.run(mapai.map_ai(state))

    assert len(titles) == 1
    assert "Please stand by" in titles[0][0]
    assert popup.closed is True
    assert worker.ran
