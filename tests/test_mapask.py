"""MapTasker plain-words Find (mapask) Unit Tests

mapask stands between a language model and mapfind, and these tests stand in for the
model with a function returning a canned reply.  What is under test is everything that is
NOT the model: what the prompt shows it, and what is let through of what it says back --
which is the part that keeps the answer exact whatever the model gets wrong.

The configuration is test_mapfind's own fixture, so a translated query can be run and its
answer compared with the one the hand-built query is already tested to give.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from maptasker.src.analysis import mapask, mapfind
from maptasker.src.core.mapjump import PROFILE
from maptasker.src.core.primitem import PrimeItems

from tests.test_mapfind import _FIXTURE_XML, _load, _named

_SETTINGS = mapask.ModelSettings(mapask.ANTHROPIC, "claude-sonnet-5", "test-key")


@pytest.fixture
def index() -> mapfind.FindIndex:
    """The search index for test_mapfind's fixture."""
    _load(_FIXTURE_XML)
    return mapfind.build_index(state=PrimeItems)


@pytest.fixture
def ai(monkeypatch: pytest.MonkeyPatch) -> dict:
    """PrimeItems.ai with one known model per provider and only an Anthropic key saved."""
    table = {
        "openai_models": ["gpt-5"],
        "anthropic_models": ["claude-sonnet-5"],
        "gemini_models": ["gemini-3-pro"],
        "llama_models": ["llama3.2 (installed)"],
        "openai_key": "",
        "anthropic_key": "sk-ant-test",
        "gemini_key": "",
    }
    monkeypatch.setattr(PrimeItems, "ai", table)
    monkeypatch.setattr(mapask, "get_api_key", lambda **_kw: "None")
    return table


def _reply(**fields: object) -> str:
    """A well-formed reply with every key present, the given ones filled in."""
    empty = dict.fromkeys(("action", "trigger", "app", "scene", "text", "project", "unexpressed"), "")
    return json.dumps(empty | fields)


# ##################################################################################
# What the model is shown.
# ##################################################################################
def test_prompt_shows_the_schema_not_the_configuration(index: mapfind.FindIndex) -> None:
    """Every pulldown value and Project is offered; nothing any object holds is."""
    system, user = mapask.build_prompt("every Profile that fires on wifi at home", index)
    for facet in (mapfind.ACTION, mapfind.TRIGGER, mapfind.APP, mapfind.SCENE_FACET):
        for choice in index.choices(facet):
            assert json.dumps(choice.value) in user
    assert '"Home"' in user
    assert '"Away"' in user
    assert "Question: every Profile that fires on wifi at home" in user
    # A Task's name, an action's argument, a context's setting, an action label, the XML.
    for private in ("Fetcher", "https://example.com/feed", "HomeNet", "said quietly", "<Action"):
        assert private not in system + user


def test_a_long_catalog_is_cut_commonest_first(index: mapfind.FindIndex) -> None:
    """What is left out of the prompt is what the file uses least."""
    schema = mapask.facet_schema(index, limit=1)
    assert schema[mapfind.ACTION] == ["Flash"]  # used three times, more than any other


# ##################################################################################
# What is let through of the reply.
# ##################################################################################
@pytest.mark.asyncio
async def test_wifi_at_home_compiles_to_an_exact_query(index: mapfind.FindIndex) -> None:
    """The headline question, end to end: the reply becomes a Query mapfind answers exactly."""
    seen = {}

    async def model(settings: mapask.ModelSettings, system: str, user: str) -> str:
        seen.update(settings=settings, system=system, user=user)
        return _reply(trigger="State: Wifi Connected", text="HomeNet")

    translation = await mapask.translate("every Profile that fires on wifi at home", index, _SETTINGS, ask=model)

    assert translation == mapask.Translation(mapfind.Query(trigger="State: Wifi Connected", text="HomeNet"))
    assert _named(mapfind.run_query(index, translation.query)[0]) == {(PROFILE, "Watch")}
    assert seen["settings"] is _SETTINGS
    assert "wifi at home" in seen["user"]


def test_a_value_the_configuration_does_not_use_is_dropped_and_said(index: mapfind.FindIndex) -> None:
    """An invented value never reaches the query -- and the dialog is told it was left out."""
    translation = mapask.parse_reply(_reply(action="HTTP Post", app="Spotify", project="Office"), index)
    assert translation.query == mapfind.Query(app="Spotify")
    assert translation.unknown == ("Task action 'HTTP Post'", "Project 'Office'")


def test_near_misses_are_spelled_the_way_the_configuration_spells_them(index: mapfind.FindIndex) -> None:
    """Case and a pulldown's count are forgiven; the value that results is the file's own."""
    translation = mapask.parse_reply(
        _reply(trigger="state: WIFI connected", action="Flash  (3)", project="home"),
        index,
    )
    assert translation.query == mapfind.Query(trigger="State: Wifi Connected", action="Flash", project="Home")
    assert translation.unknown == ()


def test_one_value_per_box(index: mapfind.FindIndex) -> None:
    """A list where one value goes keeps the first and says what else was offered."""
    translation = mapask.parse_reply(_reply(action=["HTTP Request", "Flash"], text=["feed", "other"]), index)
    assert translation.query == mapfind.Query(action="HTTP Request", text="feed")
    assert translation.surplus == ("Task action 'Flash'", "Text 'other'")


@pytest.mark.parametrize(
    "wrapped",
    [
        "```json\n{body}\n```",
        "Here is the query:\n{body}\nHope that helps.",
        '<think>Maybe {{"app": "Nope"}} would do?</think>\n{body}',
    ],
)
def test_the_query_is_found_however_the_reply_wraps_it(index: mapfind.FindIndex, wrapped: str) -> None:
    """Fences, prose around it, and a reasoning model's working with braces of its own."""
    translation = mapask.parse_reply(wrapped.format(body=_reply(app="Spotify")), index)
    assert translation.query == mapfind.Query(app="Spotify")


@pytest.mark.parametrize("reply", ["I'm sorry, I can't help with that.", "[1, 2]", '{"action": "Flash",'])
def test_a_reply_with_no_query_in_it_is_an_error_not_an_empty_search(index: mapfind.FindIndex, reply: str) -> None:
    """An empty search would answer 'nothing found', which is not what happened."""
    with pytest.raises(mapask.AskError):
        mapask.parse_reply(reply, index)


def test_what_the_boxes_cannot_say_is_passed_on(index: mapfind.FindIndex) -> None:
    """The model's note survives; a note that says there is nothing to note does not."""
    translation = mapask.parse_reply(_reply(trigger="Time", unexpressed="'Not on weekends' is a NOT."), index)
    assert translation.unexpressed == "'Not on weekends' is a NOT."
    assert mapask.parse_reply(_reply(trigger="Time", unexpressed="None."), index).unexpressed == ""


@pytest.mark.asyncio
async def test_an_empty_question_is_not_sent(index: mapfind.FindIndex) -> None:
    """Nothing to translate is said without spending a call on it."""

    async def model(*_: object) -> str:
        message = "the model should not have been asked"
        raise AssertionError(message)

    with pytest.raises(mapask.AskError):
        await mapask.translate("   ", index, _SETTINGS, ask=model)


# ##################################################################################
# Cancelling.
# ##################################################################################
@pytest.mark.asyncio
async def test_cancelling_the_question_cancels_the_request(
    index: mapfind.FindIndex,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closing the dialog or clearing the question reaches the provider's call itself.

    The request is cancelled where it is waiting, rather than left to finish -- and it is
    cancelled, not turned into an AskError: a question taken back is not a failure to
    report.
    """
    started = asyncio.Event()
    outcome = {}

    async def waiting(*_: object) -> str:
        started.set()
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            outcome["cancelled"] = True
            raise
        return _reply(app="Spotify")

    monkeypatch.setattr(mapask, "_ask_anthropic", waiting)
    task = asyncio.create_task(mapask.translate("what launches Spotify", index, _SETTINGS))
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert outcome == {"cancelled": True}


# ##################################################################################
# Which model is asked.
# ##################################################################################
@pytest.mark.parametrize(
    ("ai_name", "ai_model", "provider"),
    [
        ("Anthropic", "claude-sonnet-5", mapask.ANTHROPIC),
        ("Claude", "claude-sonnet-5", mapask.ANTHROPIC),  # ai_analyze_event's fallback spelling
        ("LLAMA", "anything", mapask.LLAMA),
        ("", "gemini-3-pro", mapask.GEMINI),  # no name recorded: found in the model lists
        ("", "llama3.2", mapask.LLAMA),
        ("", "some-new-model", ""),
    ],
)
def test_the_provider_is_named_or_looked_up(ai: dict, ai_name: str, ai_model: str, provider: str) -> None:
    """The pulldown's recorded provider first, then whichever list holds the model."""
    assert mapask.resolve_provider(ai_name, ai_model) == provider


def test_settings_carry_the_providers_key(ai: dict) -> None:
    """A cloud model is asked with its own provider's key; a local one with none."""
    assert mapask.model_settings("Anthropic", "claude-sonnet-5", state=PrimeItems) == mapask.ModelSettings(
        mapask.ANTHROPIC,
        "claude-sonnet-5",
        "sk-ant-test",
    )
    assert mapask.model_settings("LLAMA", "llama3.2 (installed)", state=PrimeItems) == mapask.ModelSettings(
        mapask.LLAMA, "llama3.2"
    )


@pytest.mark.parametrize(
    ("ai_name", "ai_model", "says"),
    [
        ("", "", "No AI model is selected"),
        ("", "None", "No AI model is selected"),
        ("OpenAI", "gpt-5", "No OpenAI API key is set"),
        ("", "some-new-model", "cannot tell which AI service"),
    ],
)
def test_missing_settings_are_said_before_anything_is_sent(ai: dict, ai_name: str, ai_model: str, says: str) -> None:
    """Each gap on the Analyze tab is named, so the user knows where to go and fix it."""
    with pytest.raises(mapask.AskError, match=says):
        mapask.model_settings(ai_name, ai_model, state=PrimeItems)


@pytest.mark.asyncio
async def test_anthropic_is_sent_the_schema_as_its_system_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    """The call's shape, with the library replaced: the async client, system prompt apart,
    reply text joined, and the client closed afterwards."""
    sent = {}

    class Messages:
        async def create(self, **kwargs: object) -> SimpleNamespace:
            sent.update(kwargs)
            return SimpleNamespace(content=[SimpleNamespace(type="text", text='{"app": '), SimpleNamespace(text='""}')])

    class AsyncAnthropic:
        def __init__(self, api_key: str) -> None:
            sent["api_key"] = api_key
            self.messages = Messages()

        async def __aenter__(self) -> AsyncAnthropic:  # noqa: PYI034
            return self

        async def __aexit__(self, *_: object) -> None:
            sent["closed"] = True

    monkeypatch.setattr(mapask, "_library", lambda *_: SimpleNamespace(AsyncAnthropic=AsyncAnthropic))
    reply = await mapask.ask_model(_SETTINGS, "the rules", "the question")

    assert reply == '{"app": ""}'
    assert sent["api_key"] == "test-key"
    assert sent["system"] == "the rules"
    assert sent["messages"] == [{"role": "user", "content": "the question"}]
    assert sent["closed"]


@pytest.mark.asyncio
async def test_a_failing_service_is_reported_not_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    """Whatever a provider's library raises reaches the dialog as a sentence."""

    async def broken(*_: object) -> str:
        message = "invalid x-api-key"
        raise RuntimeError(message)

    monkeypatch.setattr(mapask, "_ask_anthropic", broken)
    with pytest.raises(mapask.AskError, match="invalid x-api-key"):
        await mapask.ask_model(_SETTINGS, "system", "user")


def _fake_anthropic(monkeypatch: pytest.MonkeyPatch) -> dict:
    sent: dict = {}

    class Messages:
        async def create(self, **kwargs: object) -> SimpleNamespace:
            sent.update(kwargs)
            return SimpleNamespace(content=[SimpleNamespace(text="{}")])

    class AsyncAnthropic:
        def __init__(self, api_key: str) -> None:
            self.messages = Messages()

        async def __aenter__(self) -> AsyncAnthropic:  # noqa: PYI034
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

    monkeypatch.setattr(mapask, "_library", lambda *_: SimpleNamespace(AsyncAnthropic=AsyncAnthropic))
    return sent


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model", "takes_effort"),
    [
        ("claude-fable-5-1", True),
        ("claude-sonnet-5-5", True),
        ("claude-opus-5-5", True),
        ("claude-haiku-5-5", True),
        ("claude-haiku-4-5", False),
        ("claude-haiku-4-5-20251001", False),
    ],
)
async def test_effort_is_asked_for_only_of_the_models_that_take_it(
    monkeypatch: pytest.MonkeyPatch,
    model: str,
    takes_effort: bool,
) -> None:
    sent = _fake_anthropic(monkeypatch)
    await mapask.ask_model(mapask.ModelSettings(mapask.ANTHROPIC, model, "k", effort="low"), "system", "user")

    assert ("effort" in sent.get("output_config", {})) is takes_effort
    if takes_effort:
        assert sent["output_config"]["effort"] == "low"


@pytest.mark.asyncio
async def test_no_effort_is_sent_unless_asked_for(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = _fake_anthropic(monkeypatch)
    await mapask.ask_model(_SETTINGS, "system", "user")

    assert "effort" not in sent.get("output_config", {})


@pytest.mark.asyncio
async def test_an_answer_that_takes_too_long_is_given_up_on_and_said(monkeypatch: pytest.MonkeyPatch) -> None:
    async def slow(*_: object) -> str:
        await asyncio.sleep(3600)
        return ""

    monkeypatch.setattr(mapask, "_ask_anthropic", slow)
    settings = mapask.ModelSettings(mapask.ANTHROPIC, "claude-sonnet-5-5", "k", timeout=0.05)

    with pytest.raises(mapask.AskError, match="did not answer within"):
        await mapask.ask_model(settings, "system", "user")


@pytest.mark.asyncio
async def test_a_reasoning_model_that_refuses_the_effort_is_asked_again_without_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    class Completions:
        async def create(self, **kwargs: object) -> SimpleNamespace:
            calls.append(kwargs)
            if "reasoning_effort" in kwargs:
                message = "unsupported parameter"
                raise RuntimeError(message)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))])

    class AsyncOpenAI:
        def __init__(self, api_key: str) -> None:
            self.chat = SimpleNamespace(completions=Completions())

        async def __aenter__(self) -> AsyncOpenAI:  # noqa: PYI034
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

    monkeypatch.setattr(mapask, "_library", lambda *_: SimpleNamespace(AsyncOpenAI=AsyncOpenAI))
    reply = await mapask.ask_model(mapask.ModelSettings(mapask.OPENAI, "gpt-5", "k", effort="low"), "system", "user")

    assert reply == "{}"
    assert ["reasoning_effort" in call for call in calls] == [True, False]


@pytest.mark.asyncio
async def test_an_option_a_model_refuses_is_dropped_and_the_question_asked_again() -> None:
    calls = []

    async def refused() -> str:
        calls.append("with")
        message = "unsupported"
        raise RuntimeError(message)

    async def plain() -> str:
        calls.append("without")
        return "reply"

    assert await mapask._first_that_works("an option", refused, plain) == "reply"  # noqa: SLF001
    assert calls == ["with", "without"]


@pytest.mark.asyncio
async def test_the_last_attempt_is_not_caught() -> None:
    async def broken() -> str:
        message = "down"
        raise RuntimeError(message)

    with pytest.raises(RuntimeError, match="down"):
        await mapask._first_that_works("an option", broken)  # noqa: SLF001


# ##################################################################################
# The other providers, each called the way its library is called.
# ##################################################################################
@pytest.mark.parametrize("ai_name", ["DeepSeek", "deepseek"])
def test_deepseek_is_no_longer_a_service_that_can_be_asked(ai: dict, ai_name: str) -> None:
    ai["anthropic_key"] = "sk-ant-test"
    with pytest.raises(mapask.AskError, match="cannot tell which AI service runs 'deepseek-chat'"):
        mapask.model_settings(ai_name, "deepseek-chat", state=PrimeItems)


def test_a_provider_with_no_handler_is_refused() -> None:
    with pytest.raises(mapask.AskError, match="is not an AI service MapTasker can ask"):
        asyncio.run(mapask.ask_model(mapask.ModelSettings("DeepSeek", "deepseek-chat", "k"), "system", "user"))


class _FakeOpenAIClient:
    """openai.AsyncOpenAI: an async context manager whose chat completions answer `reply`."""

    def __init__(self, sent: dict, *, refuse: tuple[str, ...] = (), reply: str = "{}") -> None:
        self._sent = sent
        self._refuse = refuse
        self._reply = reply
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs: object) -> SimpleNamespace:
        self._sent.setdefault("calls", []).append(kwargs)
        if any(name in kwargs for name in self._refuse):
            message = "Unrecognized request argument"
            raise RuntimeError(message)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self._reply))])

    async def __aenter__(self) -> _FakeOpenAIClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        self._sent["closed"] = self._sent.get("closed", 0) + 1


def _fake_openai(monkeypatch: pytest.MonkeyPatch, **options: object) -> dict:
    sent: dict = {}

    def async_openai(api_key: str) -> _FakeOpenAIClient:
        sent["api_key"] = api_key
        return _FakeOpenAIClient(sent, **options)

    monkeypatch.setattr(mapask, "_library", lambda *_: SimpleNamespace(AsyncOpenAI=async_openai))
    return sent


@pytest.mark.asyncio
async def test_openai_is_sent_the_rules_as_the_system_message_and_the_client_is_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent = _fake_openai(monkeypatch, reply='{"app": ""}')

    reply = await mapask.ask_model(mapask.ModelSettings(mapask.OPENAI, "gpt-5.5", "sk-openai"), "the rules", "the question")

    assert reply == '{"app": ""}'
    assert sent["api_key"] == "sk-openai"
    ((call,),) = [(c,) for c in sent["calls"]]
    assert call["model"] == "gpt-5.5"
    assert call["messages"] == [
        {"role": "system", "content": "the rules"},
        {"role": "user", "content": "the question"},
    ]
    assert sent["closed"] == 1


@pytest.mark.asyncio
async def test_the_o1_models_are_sent_the_rules_as_a_user_message(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = _fake_openai(monkeypatch)

    await mapask.ask_model(mapask.ModelSettings(mapask.OPENAI, "o1-mini", "k"), "the rules", "the question")

    assert sent["calls"][0]["messages"][0] == {"role": "user", "content": "the rules"}


@pytest.mark.asyncio
@pytest.mark.parametrize(("model", "takes_effort"), [("gpt-5.5", True), ("o3", True), ("o4-mini", True), ("gpt-4o", False)])
async def test_reasoning_effort_goes_only_to_the_openai_models_that_reason(
    monkeypatch: pytest.MonkeyPatch, model: str, takes_effort: bool
) -> None:
    sent = _fake_openai(monkeypatch)

    await mapask.ask_model(mapask.ModelSettings(mapask.OPENAI, model, "k", effort="low"), "system", "user")

    assert ("reasoning_effort" in sent["calls"][0]) is takes_effort


@pytest.mark.asyncio
async def test_an_openai_model_that_turns_the_effort_down_is_asked_again_without_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent = _fake_openai(monkeypatch, refuse=("reasoning_effort",), reply='{"app": "x"}')

    reply = await mapask.ask_model(mapask.ModelSettings(mapask.OPENAI, "gpt-5.5", "k", effort="low"), "system", "user")

    assert reply == '{"app": "x"}'
    assert ["reasoning_effort" in call for call in sent["calls"]] == [True, False]


class _FakeGeminiClient:
    """google.genai.Client: `aio.models.generate_content` answers `reply`, and `aio.aclose` is recorded."""

    def __init__(self, sent: dict, *, refuse: bool = False, reply: str = "{}") -> None:
        async def generate_content(**kwargs: object) -> SimpleNamespace:
            sent.setdefault("calls", []).append(kwargs)
            if refuse and "thinking_config" in kwargs["config"]:
                message = "thinking_level is not supported"
                raise RuntimeError(message)
            return SimpleNamespace(text=reply)

        async def aclose() -> None:
            sent["closed"] = True

        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content), aclose=aclose)


def _fake_gemini(monkeypatch: pytest.MonkeyPatch, **options: object) -> dict:
    sent: dict = {}

    def client(api_key: str) -> _FakeGeminiClient:
        sent["api_key"] = api_key
        return _FakeGeminiClient(sent, **options)

    monkeypatch.setattr(mapask, "_library", lambda *_: SimpleNamespace(Client=client))
    return sent


@pytest.mark.asyncio
async def test_gemini_is_sent_the_rules_as_its_system_instruction_and_asked_for_json_with_no_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent = _fake_gemini(monkeypatch, reply='{"app": ""}')

    reply = await mapask.ask_model(mapask.ModelSettings(mapask.GEMINI, "gemini-3.5-flash", "AIza-k"), "the rules", "the question")

    assert reply == '{"app": ""}'
    assert sent["api_key"] == "AIza-k"
    (call,) = sent["calls"]
    assert call["model"] == "gemini-3.5-flash"
    assert call["contents"] == "the question"
    assert call["config"]["system_instruction"] == "the rules"
    assert call["config"]["response_mime_type"] == "application/json"
    assert call["config"]["automatic_function_calling"] == {"disable": True}
    assert sent["closed"] is True, "the client is closed whatever happened"


@pytest.mark.asyncio
@pytest.mark.parametrize(("model", "takes_level"), [("gemini-3.5-flash", True), ("gemini-2.5-flash", False)])
async def test_a_thinking_level_goes_only_to_the_gemini_3_models(
    monkeypatch: pytest.MonkeyPatch, model: str, takes_level: bool
) -> None:
    sent = _fake_gemini(monkeypatch)

    await mapask.ask_model(mapask.ModelSettings(mapask.GEMINI, model, "k", effort="low"), "system", "user")

    assert ("thinking_config" in sent["calls"][0]["config"]) is takes_level


@pytest.mark.asyncio
async def test_a_gemini_that_turns_the_thinking_level_down_is_asked_again_without_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent = _fake_gemini(monkeypatch, refuse=True, reply='{"app": "x"}')

    reply = await mapask.ask_model(mapask.ModelSettings(mapask.GEMINI, "gemini-3.5-flash", "k", effort="low"), "s", "u")

    assert reply == '{"app": "x"}'
    assert ["thinking_config" in call["config"] for call in sent["calls"]] == [True, False]


@pytest.mark.asyncio
async def test_a_gemini_whose_client_cannot_be_closed_is_still_answered(monkeypatch: pytest.MonkeyPatch) -> None:
    """A google-genai release older than aclose closes its connections with the client."""
    sent = _fake_gemini(monkeypatch)
    original = _FakeGeminiClient.__init__

    def without_aclose(self: _FakeGeminiClient, *args: object, **kwargs: object) -> None:
        original(self, *args, **kwargs)
        del self.aio.aclose

    monkeypatch.setattr(_FakeGeminiClient, "__init__", without_aclose)

    assert await mapask.ask_model(mapask.ModelSettings(mapask.GEMINI, "gemini-3.5-flash", "k"), "s", "u") == "{}"
    assert "closed" not in sent


def _fake_ollama(monkeypatch: pytest.MonkeyPatch, *, prepared: tuple = ("llama3.2:latest", ""), refuse_schema: bool = False) -> dict:
    seen: dict = {"chats": []}

    class AsyncClient:
        async def chat(self, model: str, messages: list, format: object) -> dict:  # noqa: A002
            seen["chats"].append({"model": model, "messages": messages, "format": format})
            if refuse_schema and isinstance(format, dict):
                message = "format must be a string"
                raise RuntimeError(message)
            return {"message": {"content": '{"app": ""}'}}

    monkeypatch.setattr(mapask, "_library", lambda *_: SimpleNamespace(AsyncClient=AsyncClient))
    monkeypatch.setattr(mapask, "prepare_ollama_model", lambda name: seen.setdefault("prepared", []).append(name) or prepared)
    return seen


@pytest.mark.asyncio
async def test_a_local_model_is_made_ready_and_then_asked_by_the_name_ollama_knows_it_by(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _fake_ollama(monkeypatch)

    reply = await mapask.ask_model(mapask.ModelSettings(mapask.LLAMA, "llama3.2"), "the rules", "the question")

    assert reply == '{"app": ""}'
    assert seen["prepared"] == ["llama3.2"]
    ((chat,),) = [(c,) for c in seen["chats"]]
    assert chat["model"] == "llama3.2:latest"
    assert chat["messages"] == [{"role": "system", "content": "the rules"}, {"role": "user", "content": "the question"}]
    assert chat["format"] == "json"


@pytest.mark.asyncio
async def test_a_local_model_is_held_to_the_replys_shape_when_it_is_given_one(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _fake_ollama(monkeypatch)

    await mapask.ask_model(mapask.ModelSettings(mapask.LLAMA, "llama3.2", schema=mapask.REPLY_SCHEMA), "s", "u")

    assert [chat["format"] for chat in seen["chats"]] == [mapask.REPLY_SCHEMA]


@pytest.mark.asyncio
async def test_an_ollama_too_old_to_take_a_schema_is_asked_again_with_json(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _fake_ollama(monkeypatch, refuse_schema=True)

    await mapask.ask_model(mapask.ModelSettings(mapask.LLAMA, "llama3.2", schema=mapask.REPLY_SCHEMA), "s", "u")

    assert [chat["format"] for chat in seen["chats"]] == [mapask.REPLY_SCHEMA, "json"]


@pytest.mark.asyncio
async def test_a_local_model_that_cannot_be_made_ready_says_why_and_is_not_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _fake_ollama(monkeypatch, prepared=(None, "Ollama is not installed."))

    with pytest.raises(mapask.AskError, match="Ollama is not installed."):
        await mapask.ask_model(mapask.ModelSettings(mapask.LLAMA, "llama3.2"), "s", "u")

    assert seen["chats"] == []
