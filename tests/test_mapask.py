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
from maptasker.src import mapask, mapfind
from maptasker.src.mapjump import PROFILE
from maptasker.src.primitem import PrimeItems

from tests.test_mapfind import _FIXTURE_XML, _load, _named

_SETTINGS = mapask.ModelSettings(mapask.ANTHROPIC, "claude-sonnet-5", "test-key")


@pytest.fixture
def index() -> mapfind.FindIndex:
    """The search index for test_mapfind's fixture."""
    _load(_FIXTURE_XML)
    return mapfind.build_index()


@pytest.fixture
def ai(monkeypatch: pytest.MonkeyPatch) -> dict:
    """PrimeItems.ai with one known model per provider and only an Anthropic key saved."""
    table = {
        "openai_models": ["gpt-5"],
        "anthropic_models": ["claude-sonnet-5"],
        "deepseek_models": ["deepseek-chat"],
        "gemini_models": ["gemini-3-pro"],
        "llama_models": ["llama3.2 (installed)"],
        "openai_key": "",
        "anthropic_key": "sk-ant-test",
        "deepseek_key": "",
        "gemini_key": "",
    }
    monkeypatch.setattr(PrimeItems, "ai", table)
    monkeypatch.setattr(mapask, "get_api_key", lambda: "None")
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
    assert mapask.model_settings("Anthropic", "claude-sonnet-5") == mapask.ModelSettings(
        mapask.ANTHROPIC,
        "claude-sonnet-5",
        "sk-ant-test",
    )
    assert mapask.model_settings("LLAMA", "llama3.2 (installed)") == mapask.ModelSettings(mapask.LLAMA, "llama3.2")


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
        mapask.model_settings(ai_name, ai_model)


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
