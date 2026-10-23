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
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import httpx
import pytest
from maptasker.src.core import console
from maptasker.src.core.initparg import initialize_runtime_arguments
from maptasker.src.core.mtexcept import MapTaskerError
from maptasker.src.core.primitem import RunState
from maptasker.src.core.sysconst import ANALYSIS_FILE, ERROR_FILE
from maptasker.src.gui import mapai

if TYPE_CHECKING:
    from collections.abc import Callable


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
def reported() -> Callable[..., list[tuple[str, int]]]:
    """Run something that reports a failure by raising it, and say what it reported: [(message, code)]."""

    def run(call: Callable[..., object], *args: object, **kwargs: object) -> list[tuple[str, int]]:
        try:
            call(*args, **kwargs)
        except MapTaskerError as error:
            return [(error.message, error.exit_code)]
        return []

    return run


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
def test_a_gemini_key_has_a_fixed_shape(key: str, valid: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    # A key without the usual shape is asked about; here Google refuses it.
    monkeypatch.setattr(mapai, "_gemini_key_works", lambda api_key: False)
    assert mapai.valid_api_key("gemini_key", key) is valid


def test_a_gemini_key_of_the_usual_shape_is_accepted_without_asking_google(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mapai, "_gemini_key_works", lambda api_key: pytest.fail("Google was asked"))
    assert mapai.valid_api_key("gemini_key", "AIzaSy" + "a" * 33) is True


def test_a_gemini_key_of_another_shape_is_accepted_if_google_accepts_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mapai, "_gemini_key_works", lambda api_key: api_key == "a-newer-kind-of-key")
    assert mapai.valid_api_key("gemini_key", "a-newer-kind-of-key") is True
    assert mapai.valid_api_key("gemini_key", "another") is False


class _GenaiAPIError(Exception):
    pass


def _fake_genai(*, listing: object) -> SimpleNamespace:
    """google.genai, whose client lists models as `listing` says: an iterable, or an exception to raise."""
    seen: dict = {}

    class Models:
        def list(self) -> object:
            if isinstance(listing, Exception):
                raise listing
            return iter(listing)

    class Client:
        def __init__(self, api_key: str) -> None:
            seen["api_key"] = api_key
            self.models = Models()

    return SimpleNamespace(Client=Client, errors=SimpleNamespace(APIError=_GenaiAPIError), seen=seen)


def test_google_is_asked_by_listing_models_with_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    library = _fake_genai(listing=[SimpleNamespace(name="models/gemini-3.5-flash")])
    monkeypatch.setattr(mapai, "import_optional", lambda *_: library)

    assert mapai._gemini_key_works("the-key") is True
    assert library.seen["api_key"] == "the-key"


@pytest.mark.parametrize(
    "failure",
    [_GenaiAPIError("API key not valid"), httpx.ConnectError("no network"), ValueError("no key")],
)
def test_a_key_google_refuses_or_cannot_be_asked_about_is_not_valid(
    failure: Exception, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mapai, "import_optional", lambda *_: _fake_genai(listing=failure))
    assert mapai._gemini_key_works("the-key") is False


def test_no_key_at_all_is_never_sent_to_google(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mapai, "import_optional", lambda *_: pytest.fail("the library was loaded"))
    assert mapai._gemini_key_works("") is False


def test_gemini_without_its_library_has_no_valid_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mapai, "import_optional", lambda *_: None)
    assert mapai._gemini_key_works("the-key") is False


@pytest.mark.parametrize("service", ["deepseek_key", "api_key", "anything_else", ""])
def test_a_service_mapask_cannot_ask_has_no_valid_key(service: str) -> None:
    assert mapai.valid_api_key(service, "a" * 32) is False


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
        ("Something else entirely", "claude-sonnet-5", "Something else entirely"),
        ("Error code: 401", "claude-sonnet-5", "Error code: 401"),  # Anything else is passed on as it came.
    ],
)
def test_a_known_failure_is_explained_and_an_unknown_one_is_passed_on(
    state: RunState, tmp_path: Path, error: str, model: str, expected: str
) -> None:
    state.program_arguments.ai_model = model

    mapai.process_error(error, "Task", "Noisy", state=state)

    assert expected in _error_text(tmp_path)


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

    assert mapai._process_openai_response(client, "the query", state=state) == "It does this."
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

    mapai._process_openai_response(client, "q", state=state)

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
            stop_reason="end_turn",
        )

    client = SimpleNamespace(messages=SimpleNamespace(create=create))

    assert mapai._process_anthropic_response(client, "the query", state=state) == "Part one. Part two."
    assert sent["model"] == "claude-sonnet-5"
    assert sent["max_tokens"] == 16000
    assert sent["system"] == mapai.ai_role
    assert sent["messages"] == [{"role": "user", "content": "the query"}]


def _anthropic_client(**reply: object) -> SimpleNamespace:
    message = SimpleNamespace(content=[SimpleNamespace(type="text", text="Some analysis.")], **reply)
    return SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: message))


@pytest.mark.parametrize("model", ["claude-fable-5-1", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"])
def test_every_current_claude_model_is_asked_the_same_way(state: RunState, model: str) -> None:
    sent = {}
    client = SimpleNamespace(
        messages=SimpleNamespace(
            create=lambda **kwargs: (
                sent.update(kwargs)
                or SimpleNamespace(content=[SimpleNamespace(type="text", text="ok")], stop_reason="end_turn")
            ),
        ),
    )
    state.program_arguments.ai_model = model

    assert mapai._process_anthropic_response(client, "q", state=state) == "ok"
    assert sent["model"] == model
    # None of the options the newer models refuse: no sampling settings, no thinking budget, no forced tool.
    assert not {"temperature", "top_p", "top_k", "thinking", "tool_choice"} & set(sent)


def test_a_claude_reply_that_ran_out_of_room_says_so(state: RunState) -> None:
    client = _anthropic_client(stop_reason="max_tokens")

    reply = mapai._process_anthropic_response(client, "q", state=state)

    assert reply.startswith("Some analysis.")
    assert "cut short" in reply


def test_a_claude_that_declines_is_reported_as_declining_not_as_an_empty_analysis(state: RunState) -> None:
    message = SimpleNamespace(
        content=[],
        stop_reason="refusal",
        stop_details=SimpleNamespace(type="refusal", category="cyber", explanation="..."),
    )
    client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: message))

    reply = mapai._process_anthropic_response(client, "q", state=state)

    assert reply == "The model declined to analyze this (cyber).  Try another model."


def test_a_decline_with_no_category_still_says_so(state: RunState) -> None:
    client = _anthropic_client(stop_reason="refusal", stop_details=None)

    assert "declined to analyze this." in mapai._process_anthropic_response(client, "q", state=state)


def test_gemini_is_given_no_tools_to_call(state: RunState) -> None:
    sent = {}

    def generate(**kwargs: object) -> SimpleNamespace:
        sent.update(kwargs)
        return SimpleNamespace(text="Gemini says.")

    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    state.program_arguments.ai_model = "gemini-3-pro"

    assert mapai._process_gemini_response(client, "the query", state=state) == "Gemini says."
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
        ("Gemini", "_process_gemini_response"),
    ):
        monkeypatch.setattr(mapai, function, lambda client, query, state, name=name: called.append(name) or name)

    for name in ("OpenAI", "Anthropic", "Gemini"):
        state.program_arguments.ai_name = name
        mapai.process_ai_query_and_response(object(), "q", "Task", "t", state=state)

    assert called == ["OpenAI", "Anthropic", "Gemini"]


def test_a_name_no_processor_knows_is_reported(state: RunState, reported: Callable[..., list]) -> None:
    state.program_arguments.ai_name = "Nobody"

    errors = reported(mapai.process_ai_query_and_response, object(), "q", "Task", "t", state=state)

    assert errors == [("Invalid AI name selected.", 12)]


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
        ("not-a-model", "boom", "Unknown failed with error: boom"),
    ],
)
def test_a_provider_s_failure_is_put_in_words(state: RunState, model: str, message: str, expected: str) -> None:
    state.program_arguments.ai_model = model
    state.ai["openai_models"] = ["gpt-5"]
    state.ai["anthropic_models"] = ["claude-sonnet-5"]
    state.ai["gemini_models"] = ["gemini-3-pro"]

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
    state: RunState, reported: Callable[..., list], monkeypatch: pytest.MonkeyPatch, starter: str, needs_message: str
) -> None:
    monkeypatch.setattr(mapai, "import_optional", lambda *_: None)
    monkeypatch.setattr(mapai, "process_ai_query_and_response", lambda *args, **kwargs: pytest.fail("a query was sent"))

    errors = reported(getattr(mapai, starter), "q", "Task", "t", state=state)

    assert needs_message in errors[0][0]
    assert mapai.AI_EXTRA_INSTALL_COMMAND in errors[0][0]
    assert errors[0][1] == 12


def test_openai_that_is_not_installed_is_reported_before_the_key_is_looked_up(
    state: RunState, reported: Callable[..., list], monkeypatch: pytest.MonkeyPatch
) -> None:
    state.program_arguments.ai_analyze = True
    monkeypatch.setattr(mapai, "module_is_available", lambda name: False)
    monkeypatch.setattr(mapai, "get_api_key", lambda state: pytest.fail("the keyring was asked"))

    errors = reported(mapai.open_ai, "q", "Task", "t", state=state)

    assert "Module 'openai' not found" in errors[0][0]


def test_a_library_that_cannot_be_loaded_ends_quietly_for_openai(
    state: RunState, monkeypatch: pytest.MonkeyPatch
) -> None:
    """import_optional has already said why; there is nothing more to do."""
    monkeypatch.setattr(mapai, "import_optional", lambda *_: None)
    monkeypatch.setattr(mapai, "process_ai_query_and_response", lambda *args, **kwargs: pytest.fail("a query was sent"))

    mapai.open_ai("q", "Task", "t", state=state)


# ##################################################################################
# Local models.
# ##################################################################################
def _fake_ollama(*, reply: str = "It does things.", raises: Exception | None = None) -> SimpleNamespace:
    """The ollama package, whose client answers `reply` (or raises) and records what it was asked."""
    asked: dict = {}

    class Client:
        def chat(self, model: str, messages: list) -> dict:
            asked.update(model=model, messages=messages)
            if raises is not None:
                raise raises
            return {"message": {"content": reply}}

    return SimpleNamespace(Client=Client, asked=asked)


@pytest.fixture
def local(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """A local run: the library, the model preparation and the console, all replaced and recorded."""
    setup = SimpleNamespace(ollama=_fake_ollama(), prepared=[], result=("llama3:latest", ""))
    monkeypatch.setattr(mapai, "import_optional", lambda *_: setup.ollama)
    monkeypatch.setattr(mapai, "prepare_ollama_model", lambda name: setup.prepared.append(name) or setup.result)
    monkeypatch.setattr(mapai, "ollama_errors", lambda: (ConnectionError,))
    monkeypatch.setattr(console, "say", lambda *_: None)
    return setup


def test_a_local_model_answers_and_the_answer_is_recorded(
    state: RunState, tmp_path: Path, local: SimpleNamespace
) -> None:
    state.program_arguments.ai_name = "LLAMA"
    state.program_arguments.ai_model = "llama3 (installed)"
    state.program_arguments.ai_analyze = True

    mapai.local_ai("Analyze this:Task data", "Task", "Noisy", state=state)

    assert local.prepared == ["llama3 (installed)"], "the model is made ready by the name the pulldown gave"
    assert local.ollama.asked["model"] == "llama3:latest", "and asked by the name Ollama knows it by"
    assert local.ollama.asked["messages"] == [
        {"role": "system", "content": mapai.ai_role},
        {"role": "user", "content": "Analyze this:Task data"},
    ], "the question goes the way it does to every other service"
    assert "It does things." in (tmp_path / ANALYSIS_FILE).read_text(encoding="utf-8")
    assert state.program_arguments.ai_analyze is False  # So a failure does not come back round.


def test_a_local_model_that_is_not_chosen_is_reported(
    state: RunState, reported: Callable[..., list], local: SimpleNamespace
) -> None:
    state.program_arguments.ai_model = "None"

    errors = reported(mapai.local_ai, "q:x", "Task", "t", state=state)

    assert errors == [("No model selected.", 12)]
    assert local.prepared == []


def test_a_model_that_cannot_be_made_ready_is_reported_with_the_reason(
    state: RunState, reported: Callable[..., list], local: SimpleNamespace
) -> None:
    local.result = (None, "Ollama is not installed.  Please install the Ollama app from 'https://ollama.com/download'.")
    state.program_arguments.ai_model = "llama3"

    errors = reported(mapai.local_ai, "q:x", "Task", "t", state=state)

    assert errors == [(local.result[1], 12)]
    assert local.ollama.asked == {}, "nothing was asked"
    assert state.program_arguments.ai_analyze is False


@pytest.mark.parametrize("failure", [ConnectionError("refused"), KeyError("message"), TypeError("bad reply")])
def test_a_local_model_that_fails_while_answering_is_reported_as_one_error(
    state: RunState, reported: Callable[..., list], local: SimpleNamespace, failure: Exception
) -> None:
    local.ollama = _fake_ollama(raises=failure)
    state.program_arguments.ai_model = "llama3"

    errors = reported(mapai.local_ai, "q:x", "Task", "t", state=state)

    assert errors and "Ai analysis error:" in errors[0][0]


def test_the_local_libraries_failing_to_load_is_reported_with_how_to_fix_it(
    state: RunState, reported: Callable[..., list], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mapai, "import_optional", lambda *_: None)

    errors = reported(mapai.local_ai, "q:x", "Task", "t", state=state)

    assert "Ollama support could not be loaded" in errors[0][0]
    assert mapai.AI_EXTRA_INSTALL_COMMAND in errors[0][0]
    assert mapai.OLLAMA_DOWNLOAD_URL in errors[0][0]
    assert errors[0][1] == 12


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
        ("Gemini", "gemini_ai"),
        ("LLAMA", "local_ai"),
    ],
)
def test_each_ai_name_runs_its_own_worker(state: RunState, worker: SimpleNamespace, name: str, function: str) -> None:
    state.program_arguments.ai_name = name
    state.output_lines.output_lines = ["Task: Noisy", "Action: 1"]

    asyncio.run(mapai._run_analysis_in_background(_Popup(), state=state))

    assert [call[0] for call in worker.ran] == [getattr(mapai, function)]


@pytest.mark.parametrize("name", ["DeepSeek", "Deepseek", "", "Nobody"])
def test_an_ai_name_that_is_not_a_supported_service_runs_nothing_and_says_so(
    state: RunState, worker: SimpleNamespace, reported: Callable[..., list], name: str
) -> None:
    state.program_arguments.ai_name = name
    state.output_lines.output_lines = ["Task: Noisy", "Action: 1"]

    asyncio.run(mapai._run_analysis_in_background(_Popup(), state=state))

    assert worker.ran[0][0] is not mapai.open_ai
    # The lookup falls back to a function that reports the problem, run in the worker thread.
    errors = reported(worker.ran[0][0], "q", "Task", "Noisy", state=state)
    assert errors and "Invalid model selected" in errors[-1][0]


def test_the_query_names_the_object_carries_the_prompt_and_every_line(state: RunState, worker: SimpleNamespace) -> None:
    state.output_lines.output_lines = ["Task: Noisy", "Action: 1", "Action: 2"]
    state.program_arguments.ai_prompt = "Explain it"

    asyncio.run(mapai._run_analysis_in_background(_Popup(), state=state))

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

    asyncio.run(mapai._run_analysis_in_background(_Popup(), state=state))

    assert "Explain it:" in worker.ran[0][1][0]
    assert "::" not in worker.ran[0][1][0]


def test_no_prompt_means_the_default_one(state: RunState, worker: SimpleNamespace) -> None:
    state.program_arguments.ai_prompt = ""

    asyncio.run(mapai._run_analysis_in_background(_Popup(), state=state))

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
        asyncio.run(mapai._run_analysis_in_background(popup, state=state))

    assert popup.closed is True
    assert state.program_arguments.ai_analyze is False


def test_a_popup_that_holds_its_dialog_is_closed_through_it(state: RunState, worker: SimpleNamespace) -> None:
    popup = SimpleNamespace(dialog=_Popup())

    asyncio.run(mapai._run_analysis_in_background(popup, state=state))

    assert popup.dialog.closed is True


def test_no_popup_is_no_problem(state: RunState, worker: SimpleNamespace) -> None:
    asyncio.run(mapai._run_analysis_in_background(None, state=state))


def test_a_blank_ai_name_is_reported_not_run(
    state: RunState, worker: SimpleNamespace, reported: Callable[..., list]
) -> None:
    state.program_arguments.ai_name = ""

    asyncio.run(mapai._run_analysis_in_background(_Popup(), state=state))
    errors = reported(worker.ran[0][0], "q", "Task", "t", state=state)  # What io_bound would have run.

    assert errors == [("Invalid model selected (AI name is blank).", 12)]


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
