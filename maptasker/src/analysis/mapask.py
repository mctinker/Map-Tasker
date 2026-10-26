"""mapask: a question asked in plain words, compiled into a mapfind Query."""

#! /usr/bin/env python3

#                                                                                        #
# mapask: let a language model write the Find dialog's query, and nothing more.          #
#                                                                                        #
# mapfind answers exact questions -- "Profiles triggered by State: Wifi Connected whose   #
# settings mention 'home'" -- but only once they have been put in its terms: a value      #
# picked from each of four pulldowns and a piece of text.  "Every Profile that fires on   #
# wifi at home" is the same question before that translation, and the translation is the #
# part a language model is actually reliable at.  So that is the only part it is given.   #
#                                                                                        #
# What the model is shown is the facet SCHEMA -- what each box means and the values this  #
# configuration's own pulldowns offer -- never the XML.  That keeps the prompt small      #
# whatever the size of the backup, keeps what the user's Tasks hold out of it, and leaves  #
# the model no answer of its own to give: all it can do is fill in the boxes.             #
#                                                                                        #
# What comes back is not trusted.  Every value is checked against the same catalogs the   #
# pulldowns are built from, and one the configuration does not use is dropped and SAID to #
# have been dropped, rather than passed on to quietly answer nothing.  What survives is   #
# run by mapfind exactly as if it had been picked by hand, and is put back into the       #
# pulldowns so the user can read what was asked and change it.  A wrong translation is    #
# visible on screen; a wrong answer to the query that is shown is not possible.           #
#                                                                                        #
# Same contract as mapfind: no GUI import.  A provider's library is imported only when a  #
# question is actually put to it, the way mapai imports them.                            #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from maptasker.src.analysis import mapfind
from maptasker.src.core.aiutils import get_api_key, prepare_ollama_model
from maptasker.src.core.maputil3 import AI_EXTRA_INSTALL_COMMAND, AiClient, import_optional
from maptasker.src.core.sysconst import logger

if TYPE_CHECKING:
    from types import ModuleType

    from maptasker.src.core.primitem import RunState

# The providers, spelled the way the Analyze tab's model pulldown groups them and the way
# mapai dispatches on them.
OPENAI = "OpenAI"
ANTHROPIC = "Anthropic"
GEMINI = "Gemini"
LLAMA = "LLAMA"

# Every spelling of a provider that reaches gui.ai_name.  The pulldown writes the first
# form; ai_analyze_event's fallback, for a model picked before the pulldown carried a
# prefix, writes "Claude" and "Llama".
_PROVIDER_NAMES = {
    "openai": OPENAI,
    "anthropic": ANTHROPIC,
    "claude": ANTHROPIC,
    "gemini": GEMINI,
    "llama": LLAMA,
    "ollama": LLAMA,
}

# Where the run state's ai lists each provider's models, for a model whose provider was not named.
_MODEL_LISTS = (
    (OPENAI, "openai_models"),
    (ANTHROPIC, "anthropic_models"),
    (GEMINI, "gemini_models"),
    (LLAMA, "llama_models"),
)

# Where the run state's ai keeps each provider's API key.  Ollama runs locally and has none.
_KEY_NAMES = {OPENAI: "openai_key", ANTHROPIC: "anthropic_key", GEMINI: "gemini_key"}

# The boxes whose value must be one the configuration uses, in the order the prompt lists
# them.  The text box is free, and the Project box is checked against the Project list.
_CATALOGUED = (mapfind.ACTION, mapfind.TRIGGER, mapfind.APP, mapfind.SCENE_FACET)
PROJECT_KEY = "project"
UNEXPRESSED_KEY = "unexpressed"

# How many values of one facet the model is shown.  Commonest first, so what is cut is
# what the file uses least; a value past the cut that the model names anyway is still
# accepted, because the check is against the whole catalog rather than against the prompt.
MAX_CHOICES = 400

# A reply is one small JSON object.  Generous, so a model that explains itself first is
# not cut off before it gets to the object.
MAX_REPLY_TOKENS = 1024
# Claude's limit counts its thinking as well as the reply, and current Claude models think by
# default -- so 1024 can be spent before the object is written.
ANTHROPIC_MAX_TOKENS = 16000

# The reply's shape, which Claude models that support structured output are held to exactly.
# Other models (and other providers) are left to the prompt and to reply_object.
# The Claude models that take output_config.effort.  Not every Claude model does -- Haiku 4.5
# turns the field down -- so it is sent only to these.
EFFORT_MODELS = ("claude-fable-5", "claude-opus-5", "claude-opus-4-8", "claude-sonnet-5", "claude-haiku-5")
# The OpenAI models that reason before they answer, and so take reasoning_effort.
OPENAI_REASONING_MODELS = ("gpt-5", "o3", "o4")
STRUCTURED_OUTPUT_MODELS = (
    "claude-fable-5",
    "claude-opus-5",
    "claude-opus-4-8",
    "claude-opus-4-5",
    "claude-sonnet-5",
    "claude-haiku-4-5",
    "claude-haiku-5",
)
REPLY_SCHEMA = {
    "type": "object",
    "properties": {
        key: {"type": "string"} for key in ("action", "trigger", "app", "scene", "text", "project", "unexpressed")
    },
    "required": ["action", "trigger", "app", "scene", "text", "project", "unexpressed"],
    "additionalProperties": False,
}

# A reasoning model's working, which can hold braces of its own and is never the answer.
_THINKING = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
# The count a pulldown shows beside a value -- "Flash  (37)" -- echoed back by a model
# that has seen the dialog described.
_COUNT_SUFFIX = re.compile(r"\s*\(\d+\)$")
# What a model writes in place of leaving a note empty.
_NO_NOTE = {"", "none", "n/a", "null", "nothing"}

_INSTRUCTIONS = """\
You translate a question about a Tasker (Android automation) configuration into a search \
query for MapTasker's Find dialog. You do not answer the question; the search does that.

The query has these fields:
  action  -- a Task action. Finds the Tasks that perform it.
  trigger -- a Profile context: "Event: ...", "State: ...", "Time", "Day", "Location" or \
"Application". Finds the Profiles it triggers. Only the kind of context is listed, not its \
settings (a Wifi network's name, a time of day, a place).
  app     -- an app named by a Task action or by a Profile's Application context.
  scene   -- a Scene. Finds the Scene, the Tasks that use it and the Project listing it.
  text    -- one piece of text, matched case-insensitively inside object names, action \
labels and arguments, the settings of a Profile's Event and State contexts (such as a Wifi \
network's name) and the text of Scene elements.
  project -- limits the whole search to one Project.

How the fields combine:
  - Every field filled in must match. There is no OR and no NOT, and each field holds one \
value.
  - A Task has no trigger, so a trigger leaves only Profiles. A trigger together with an \
action, app or scene finds the Profiles with that trigger whose Tasks do that -- this is \
how "Profiles that ... and run a Task that ..." is asked.
  - The results list every kind of object that matches; there is no field for the kind, \
so do not report that as something the fields cannot express.

Rules for the reply:
  - action, trigger, app, scene and project must be copied exactly from the lists given \
with the question, or left "". Never invent a value. If nothing in a list fits, leave it "".
  - Use text only for something specific the question names that no list covers -- a \
network name, a place, a URL, part of a name -- and choose the single most distinctive \
word. Leave it "" otherwise.
  - Leave "" every field the question does not need.
  - unexpressed: one short sentence naming any part of the question these fields cannot \
express (an "or", a "not", a time of day, a count), or "" if there is none.
  - Reply with one JSON object and nothing else, with exactly these keys: \
"action", "trigger", "app", "scene", "text", "project", "unexpressed".
"""


class AskError(Exception):
    """A question that could not be asked or answered, worded for the person who asked it."""


@dataclass(frozen=True)
class ModelSettings:
    """Which model to ask, and with what key -- read off the Analyze tab when Ask is pressed.

    'schema' and 'max_tokens' are for a question whose reply is not a Find query -- see
    mapdraft, which asks twice with two different shapes of reply.  Left alone they are the
    Find's own.
    """

    provider: str
    model: str
    api_key: str = ""
    # The shape of the reply, for the models that can be held to one; None means REPLY_SCHEMA.
    schema: dict | None = None
    max_tokens: int = MAX_REPLY_TOKENS
    # How hard a model that reasons before it answers is asked to: "low" for a question whose
    # answer needs no deliberation.  Applied only where the provider and model take it, and
    # dropped, with the request made again, if the service turns it down.  "" leaves it alone.
    effort: str = ""
    # Seconds to wait for the answer before giving up on it; None waits as long as it takes.
    timeout: float | None = None


@dataclass(frozen=True)
class Translation:
    """What a reply amounted to, once everything the configuration cannot answer is taken out.

    'query' is only ever built from values that passed the check, so it is safe to put
    straight into the pulldowns.  The other three are what was left out of it and why,
    for the dialog to say -- a query quietly missing half of the question would answer
    with fewer objects than asked for and look exactly like a right answer.
    """

    query: mapfind.Query
    # Values the configuration does not use, as "<box> '<value>'".
    unknown: tuple[str, ...] = ()
    # Second and later values the model put in a box that holds one.
    surplus: tuple[str, ...] = ()
    # The model's own note on what the boxes cannot say.
    unexpressed: str = ""


# ##################################################################################
# Which model.
# ##################################################################################
def _bare_model(model: str) -> str:
    """A model name without the marker the pulldown adds to an installed Ollama model."""
    return (model or "").replace(" (installed)", "").strip()


def resolve_provider(ai_name: str, ai_model: str, state: RunState) -> str:
    """Which provider serves the selected model, or "" if that cannot be told.

    The name the pulldown recorded is taken first, as guiutils.is_ollama_model takes it:
    it is the one place the provider is stated rather than inferred.  Failing that, the
    provider whose model list holds the model.
    """
    named = _PROVIDER_NAMES.get((ai_name or "").strip().lower())
    if named:
        return named
    model = _bare_model(ai_model)
    for provider, list_name in _MODEL_LISTS:
        if model in {_bare_model(entry) for entry in state.ai.get(list_name, [])}:
            return provider
    return ""


def model_settings(ai_name: str, ai_model: str, state: RunState) -> ModelSettings:
    """The settings to ask with, or an AskError saying what is missing from the Analyze tab."""
    model = _bare_model(ai_model)
    if not model or model == "None":
        message = "No AI model is selected.  Choose one on the Analyze tab first."
        raise AskError(message)
    provider = resolve_provider(ai_name, model, state)
    if not provider:
        message = f"MapTasker cannot tell which AI service runs '{model}'.  Choose it again on the Analyze tab."
        raise AskError(message)
    if provider == LLAMA:
        return ModelSettings(provider, model)

    key_name = _KEY_NAMES[provider]
    key = state.ai.get(key_name) or ""
    if not key:
        # The saved keys are only read in when something first needs one.
        get_api_key(state=state)
        key = state.ai.get(key_name) or ""
    if not key or key == "Hidden":
        message = f"No {provider} API key is set.  Enter one with 'Show/Edit API Key(s)' on the Analyze tab."
        raise AskError(message)
    return ModelSettings(provider, model, key)


# ##################################################################################
# The prompt.
# ##################################################################################
def facet_schema(index: mapfind.FindIndex, limit: int = MAX_CHOICES) -> dict[str, list[str]]:
    """{box: the values it may hold} -- what the model is shown in place of the configuration.

    The values are the pulldowns' own, so the model is choosing from exactly what the user
    would have been offered, and nothing it is shown says what any object contains.
    """
    schema = {facet: [choice.value for choice in index.choices(facet)[:limit]] for facet in _CATALOGUED}
    schema[PROJECT_KEY] = index.projects[:limit]
    return schema


def build_prompt(question: str, index: mapfind.FindIndex) -> tuple[str, str]:
    """(system prompt, user message) for one question."""
    lines = [
        "Values this configuration uses, most used first:",
        json.dumps(facet_schema(index), ensure_ascii=False, indent=1),
    ]
    if any(len(index.catalog.get(facet, ())) > MAX_CHOICES for facet in _CATALOGUED) or (
        len(index.projects) > MAX_CHOICES
    ):
        lines.append(f"(A list holds at most the {MAX_CHOICES} most used values.)")
    lines += ["", f"Question: {question.strip()}"]
    return _INSTRUCTIONS, "\n".join(lines)


# ##################################################################################
# The reply.
# ##################################################################################
def reply_object(reply: str, what: str = "search") -> dict:
    """The JSON object in a reply, however much prose or fencing a model wraps it in.

    'what' is what the reply was meant to be, for the message when it is not.
    """
    text = _THINKING.sub("", reply or "")
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        message = f"The AI model did not reply with a {what}.  Try rewording the question."
        raise AskError(message)
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError as error:
        message = f"The AI model's reply could not be read as a {what}.  Try asking again."
        raise AskError(message) from error
    if not isinstance(parsed, dict):
        message = f"The AI model did not reply with a {what}.  Try rewording the question."
        raise AskError(message)
    return parsed


def values_of(raw: object) -> list[str]:
    """A box's reply as a list of non-empty strings: one for a value, more for a list of them."""
    items = raw if isinstance(raw, list) else [raw]
    return [str(item).strip() for item in items if item is not None and str(item).strip()]


def canonical(value: str, known: Iterable[str]) -> str:
    """The value spelled as the configuration spells it, or "" if the configuration does not use it.

    Exact first, so a value that really does end in "(2)" is not stripped of it; then
    without a pulldown's count; then ignoring case, which is the slip a model makes most
    ("State: WiFi Connected").  No closer guessing than that: a value near a real one is
    still not the one the user asked about, and dropping it is said out loud.
    """
    known = list(known)
    if value in known:
        return value
    bare = _COUNT_SUFFIX.sub("", value).strip()
    if bare in known:
        return bare
    folded = bare.casefold()
    return next((entry for entry in known if entry.casefold() == folded), "")


def parse_reply(reply: str, index: mapfind.FindIndex) -> Translation:
    """Turn a model's reply into a Query of only the values this configuration uses."""
    fields = reply_object(reply)
    labels = {**mapfind.FACET_LABELS, PROJECT_KEY: "Project"}
    catalogs: dict[str, Iterable[str]] = {facet: index.catalog.get(facet, {}) for facet in _CATALOGUED}
    catalogs[PROJECT_KEY] = index.projects

    chosen: dict[str, str] = {}
    unknown: list[str] = []
    surplus: list[str] = []
    for box, catalog in catalogs.items():
        values = values_of(fields.get(box))
        if not values:
            chosen[box] = ""
            continue
        surplus += [f"{labels[box]} '{value}'" for value in values[1:]]
        chosen[box] = canonical(values[0], catalog)
        if not chosen[box]:
            unknown.append(f"{labels[box]} '{values[0]}'")

    texts = values_of(fields.get(mapfind.TEXT))
    surplus += [f"{labels[mapfind.TEXT]} '{text}'" for text in texts[1:]]
    note = " ".join(values_of(fields.get(UNEXPRESSED_KEY)))

    return Translation(
        query=mapfind.Query(
            action=chosen[mapfind.ACTION],
            trigger=chosen[mapfind.TRIGGER],
            app=chosen[mapfind.APP],
            scene=chosen[mapfind.SCENE_FACET],
            text=texts[0] if texts else "",
            project=chosen[PROJECT_KEY],
        ),
        unknown=tuple(unknown),
        surplus=tuple(surplus),
        unexpressed="" if note.strip(" .").casefold() in _NO_NOTE else note,
    )


# ##################################################################################
# Asking.
# ##################################################################################
def _library(pypi_name: str, import_path: str) -> ModuleType:
    """A provider's library, or an AskError if it is not installed."""
    module = import_optional(pypi_name, import_path)
    if module is None:
        message = f"The '{pypi_name}' package is not installed.  Install it with: {AI_EXTRA_INSTALL_COMMAND}"
        raise AskError(message)
    return module


# Every provider below is asked through its ASYNC client, and that is what lets a question
# be taken back.  A request made from a thread cannot be stopped -- cancelling the await on
# it only stops waiting, while the thread runs on to a reply nobody will read.  A request
# made by an asyncio task is abandoned where it waits when the task is cancelled: its
# connection is closed, and the provider stops generating the reply.
async def _chat_completion(client: AiClient, model: str, system: str, user: str, **extra: object) -> str:
    """One OpenAI chat completion."""
    # The o1 family refuses a system message; mapai makes the same allowance for it.
    role = "user" if "o1" in model else "system"
    async with client:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": role, "content": system}, {"role": "user", "content": user}],
            **extra,
        )
    return response.choices[0].message.content or ""


async def _first_that_works(what: str, *attempts: Callable[[], Awaitable[str]]) -> str:
    """The reply of the first attempt that gets one; the last is not caught, so its failure is the caller's.

    For an option -- a reasoning effort, a reply schema -- that only some versions of a model or
    server take, and that a refusal of is not worth failing the question over.  A question
    taken back is not a failure: cancellation passes through.
    """
    for attempt in attempts[:-1]:
        try:
            reply = await attempt()
        except Exception as error:  # noqa: BLE001 -- any refusal, from any provider's library
            logger.debug(f"mapask: {what} was not taken ({error}); asking without it")
        else:
            return reply
    return await attempts[-1]()


async def _ask_openai(settings: ModelSettings, system: str, user: str) -> str:
    def attempt(**extra: object) -> Awaitable[str]:
        client = _library("openai", "openai").AsyncOpenAI(api_key=settings.api_key)
        return _chat_completion(client, settings.model, system, user, **extra)

    attempts: list[Callable[[], Awaitable[str]]] = [attempt]
    if settings.effort and settings.model.startswith(OPENAI_REASONING_MODELS):
        attempts.insert(0, lambda: attempt(reasoning_effort=settings.effort))
    return await _first_that_works(f"{settings.model}'s reasoning_effort", *attempts)


async def _ask_anthropic(settings: ModelSettings, system: str, user: str) -> str:
    extra = {}
    output_config: dict = {}
    if settings.model.startswith(STRUCTURED_OUTPUT_MODELS):
        output_config["format"] = {"type": "json_schema", "schema": settings.schema or REPLY_SCHEMA}
    # Current Claude models think before they answer, which is most of the wait for a reply
    # this small; "low" spends far less of it.
    if settings.effort and settings.model.startswith(EFFORT_MODELS):
        output_config["effort"] = settings.effort
    if output_config:
        extra["output_config"] = output_config
    async with _library("anthropic", "anthropic").AsyncAnthropic(api_key=settings.api_key) as client:
        message = await client.messages.create(
            model=settings.model,
            max_tokens=ANTHROPIC_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
            **extra,
        )
    return "".join(getattr(block, "text", "") for block in message.content)


async def _ask_gemini(settings: ModelSettings, system: str, user: str) -> str:
    client = _library("google-genai", "google.genai").Client(api_key=settings.api_key)
    config = {
        "system_instruction": system,
        "response_mime_type": "application/json",
        # No tools are given, so nothing can be called; see mapai._process_gemini_response.
        "automatic_function_calling": {"disable": True},
    }

    async def attempt(**extra: object) -> str:
        response = await client.aio.models.generate_content(
            model=settings.model,
            contents=user,
            config={**config, **extra},
        )
        return response.text or ""

    attempts: list[Callable[[], Awaitable[str]]] = [attempt]
    if settings.effort and "gemini-3" in settings.model:
        attempts.insert(0, lambda: attempt(thinking_config={"thinking_level": settings.effort}))
    try:
        return await _first_that_works(f"{settings.model}'s thinking_level", *attempts)
    finally:
        # A google-genai release older than aclose closes its connections with the client.
        close = getattr(client.aio, "aclose", None)
        if close is not None:
            await close()


async def _ask_llama(settings: ModelSettings, system: str, user: str) -> str:
    ollama = _library("ollama", "ollama")
    # The server, and the model on it, which may have to be started or downloaded.  All of that
    # blocks, so it goes to a thread; a question taken back while it runs is dropped before anything
    # is asked, though the preparation itself finishes.
    model, reason = await asyncio.to_thread(prepare_ollama_model, settings.model)
    if model is None:
        raise AskError(reason)
    # The request itself goes through ollama's async client, for the reason given above.
    client = ollama.AsyncClient()
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

    async def attempt(reply_format: object) -> str:
        response = await client.chat(model=model, messages=messages, format=reply_format)
        return response["message"]["content"] or ""

    # A schema holds a small model to the reply's shape, which "json" alone does not; a server
    # too old to take one is asked again with "json".
    attempts = [lambda: attempt("json")]
    if settings.schema:
        attempts.insert(0, lambda: attempt(settings.schema))
    return await _first_that_works("a reply schema", *attempts)


# (ModelSettings, system prompt, user message) -> the reply's text.
Asker = Callable[[ModelSettings, str, str], Awaitable[str]]


async def ask_model(settings: ModelSettings, system: str, user: str) -> str:
    """Put one prompt to the selected model and return its reply's text.

    Every failure comes back as an AskError: five providers raise five unrelated exception
    hierarchies, and all the dialog can do with any of them is say what went wrong.  The one
    thing let through untouched is cancellation -- asyncio.CancelledError is not an
    Exception -- so a question taken back reaches the caller as cancelled, not as a failure.
    """
    handlers: dict[str, Asker] = {
        OPENAI: _ask_openai,
        ANTHROPIC: _ask_anthropic,
        GEMINI: _ask_gemini,
        LLAMA: _ask_llama,
    }
    handler = handlers.get(settings.provider)
    if handler is None:
        message = f"'{settings.provider}' is not an AI service MapTasker can ask."
        raise AskError(message)
    try:
        if settings.timeout is None:
            return await handler(settings, system, user)
        async with asyncio.timeout(settings.timeout):
            return await handler(settings, system, user)
    except AskError:
        raise
    except TimeoutError as error:
        message = (
            f"{settings.provider} ({settings.model}) did not answer within {settings.timeout:.0f} seconds.  "
            "A faster model chosen on the Analyze tab, or a shorter request, may help."
        )
        raise AskError(message) from error
    except Exception as error:
        logger.error(f"mapask: {settings.provider} {settings.model} failed: {error}")
        message = f"{settings.provider} ({settings.model}) could not be asked: {error}"
        raise AskError(message) from error


async def translate(
    question: str,
    index: mapfind.FindIndex,
    settings: ModelSettings,
    ask: Asker = ask_model,
) -> Translation:
    """Compile one plain-words question into a checked Query.

    A coroutine, so that the caller can run it as a task and cancel it -- which cancels the
    request to the model with it.  'ask' is the model call, a parameter so that everything
    around it can be tested with a function standing in for the model.
    """
    if not question.strip():
        message = "Type a question first."
        raise AskError(message)
    system, user = build_prompt(question, index)
    reply = await ask(settings, system, user)
    logger.debug(f"mapask: {settings.model} replied {reply!r}")
    return parse_reply(reply, index)
