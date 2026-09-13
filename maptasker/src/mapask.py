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
import importlib.util
import json
import re
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass

from maptasker.src import mapfind
from maptasker.src.aiutils import get_api_key, start_ollama_server
from maptasker.src.maputil3 import ensure_and_import
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import logger

# The providers, spelled the way the Analyze tab's model pulldown groups them and the way
# mapai dispatches on them.
OPENAI = "OpenAI"
ANTHROPIC = "Anthropic"
DEEPSEEK = "DeepSeek"
GEMINI = "Gemini"
LLAMA = "LLAMA"

# Every spelling of a provider that reaches gui.ai_name.  The pulldown writes the first
# form; ai_analyze_event's fallback, for a model picked before the pulldown carried a
# prefix, writes "Claude" and "Llama".
_PROVIDER_NAMES = {
    "openai": OPENAI,
    "anthropic": ANTHROPIC,
    "claude": ANTHROPIC,
    "deepseek": DEEPSEEK,
    "gemini": GEMINI,
    "llama": LLAMA,
    "ollama": LLAMA,
}

# Where PrimeItems.ai lists each provider's models, for a model whose provider was not named.
_MODEL_LISTS = (
    (OPENAI, "openai_models"),
    (ANTHROPIC, "anthropic_models"),
    (DEEPSEEK, "deepseek_models"),
    (GEMINI, "gemini_models"),
    (LLAMA, "llama_models"),
)

# Where PrimeItems.ai keeps each provider's API key.  Ollama runs locally and has none.
_KEY_NAMES = {OPENAI: "openai_key", ANTHROPIC: "anthropic_key", DEEPSEEK: "deepseek_key", GEMINI: "gemini_key"}

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
    """Which model to ask, and with what key -- read off the Analyze tab when Ask is pressed."""

    provider: str
    model: str
    api_key: str = ""


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


def resolve_provider(ai_name: str, ai_model: str) -> str:
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
        if model in {_bare_model(entry) for entry in PrimeItems.ai.get(list_name, [])}:
            return provider
    return ""


def model_settings(ai_name: str, ai_model: str) -> ModelSettings:
    """The settings to ask with, or an AskError saying what is missing from the Analyze tab."""
    model = _bare_model(ai_model)
    if not model or model == "None":
        message = "No AI model is selected.  Choose one on the Analyze tab first."
        raise AskError(message)
    provider = resolve_provider(ai_name, model)
    if not provider:
        message = f"MapTasker cannot tell which AI service runs '{model}'.  Choose it again on the Analyze tab."
        raise AskError(message)
    if provider == LLAMA:
        return ModelSettings(provider, model)

    key_name = _KEY_NAMES[provider]
    key = PrimeItems.ai.get(key_name) or ""
    if not key:
        # The saved keys are only read in when something first needs one.
        get_api_key()
        key = PrimeItems.ai.get(key_name) or ""
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
def _reply_object(reply: str) -> dict:
    """The JSON object in a reply, however much prose or fencing a model wraps it in."""
    text = _THINKING.sub("", reply or "")
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        message = "The AI model did not reply with a search.  Try rewording the question."
        raise AskError(message)
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError as error:
        message = "The AI model's reply could not be read as a search.  Try asking again."
        raise AskError(message) from error
    if not isinstance(parsed, dict):
        message = "The AI model did not reply with a search.  Try rewording the question."
        raise AskError(message)
    return parsed


def _values(raw: object) -> list[str]:
    """A box's reply as a list of non-empty strings: one for a value, more for a list of them."""
    items = raw if isinstance(raw, list) else [raw]
    return [str(item).strip() for item in items if item is not None and str(item).strip()]


def _canonical(value: str, known: Iterable[str]) -> str:
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
    fields = _reply_object(reply)
    labels = {**mapfind.FACET_LABELS, PROJECT_KEY: "Project"}
    catalogs: dict[str, Iterable[str]] = {facet: index.catalog.get(facet, {}) for facet in _CATALOGUED}
    catalogs[PROJECT_KEY] = index.projects

    chosen: dict[str, str] = {}
    unknown: list[str] = []
    surplus: list[str] = []
    for box, catalog in catalogs.items():
        values = _values(fields.get(box))
        if not values:
            chosen[box] = ""
            continue
        surplus += [f"{labels[box]} '{value}'" for value in values[1:]]
        chosen[box] = _canonical(values[0], catalog)
        if not chosen[box]:
            unknown.append(f"{labels[box]} '{values[0]}'")

    texts = _values(fields.get(mapfind.TEXT))
    surplus += [f"{labels[mapfind.TEXT]} '{text}'" for text in texts[1:]]
    note = " ".join(_values(fields.get(UNEXPRESSED_KEY)))

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
def _library(pypi_name: str, import_path: str) -> object:
    """A provider's library, installed first if need be, or an AskError if it cannot be had."""
    module = ensure_and_import(pypi_name, import_path)
    if module is None:
        message = f"The '{pypi_name}' package is not installed and could not be installed."
        raise AskError(message)
    return module


# Every provider below is asked through its ASYNC client, and that is what lets a question
# be taken back.  A request made from a thread cannot be stopped -- cancelling the await on
# it only stops waiting, while the thread runs on to a reply nobody will read.  A request
# made by an asyncio task is abandoned where it waits when the task is cancelled: its
# connection is closed, and the provider stops generating the reply.
async def _chat_completion(client: object, model: str, system: str, user: str, **extra: object) -> str:
    """One OpenAI-style chat completion -- OpenAI's own API, and DeepSeek's copy of it."""
    # The o1 family refuses a system message; mapai makes the same allowance for it.
    role = "user" if "o1" in model else "system"
    async with client:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": role, "content": system}, {"role": "user", "content": user}],
            **extra,
        )
    return response.choices[0].message.content or ""


async def _ask_openai(settings: ModelSettings, system: str, user: str) -> str:
    client = _library("openai", "openai").AsyncOpenAI(api_key=settings.api_key)
    return await _chat_completion(client, settings.model, system, user)


async def _ask_deepseek(settings: ModelSettings, system: str, user: str) -> str:
    client = _library("openai", "openai").AsyncOpenAI(api_key=settings.api_key, base_url="https://api.deepseek.com")
    return await _chat_completion(client, settings.model, system, user, temperature=0.0, max_tokens=MAX_REPLY_TOKENS)


async def _ask_anthropic(settings: ModelSettings, system: str, user: str) -> str:
    async with _library("anthropic", "anthropic").AsyncAnthropic(api_key=settings.api_key) as client:
        message = await client.messages.create(
            model=settings.model,
            max_tokens=MAX_REPLY_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    return "".join(getattr(block, "text", "") for block in message.content)


async def _ask_gemini(settings: ModelSettings, system: str, user: str) -> str:
    client = _library("google-genai", "google.genai").Client(api_key=settings.api_key)
    try:
        response = await client.aio.models.generate_content(
            model=settings.model,
            contents=user,
            config={"system_instruction": system, "response_mime_type": "application/json"},
        )
    finally:
        # A google-genai release older than aclose closes its connections with the client.
        close = getattr(client.aio, "aclose", None)
        if close is not None:
            await close()
    return response.text or ""


async def _ask_llama(settings: ModelSettings, system: str, user: str) -> str:
    # Asked before cria is imported, for the reason mapai.local_ai gives: importing cria is
    # what installs the 'ollama' package, after which there is no telling that this run did.
    was_installed = importlib.util.find_spec("ollama") is not None
    try:
        from maptasker.src import cria  # noqa: PLC0415
    except Exception as error:
        # Its module-level install can fail in several ways.
        message = f"Ollama support could not be loaded: {error}"
        raise AskError(message) from error
    if not was_installed:
        started, reason = await asyncio.to_thread(start_ollama_server)
        if not started:
            raise AskError(reason)

    # Cria starts a server if none is up and works out which installed model the name means.
    # All of that blocks, so it goes to a thread; a question taken back while it runs is
    # dropped before anything is asked, though the preparation itself finishes.
    # Standalone: nothing is left running an 'ollama run' of its own for one short reply.
    ai = await asyncio.to_thread(cria.Cria, model=settings.model, standalone=True, silence_output=True)
    if ai.model is None:
        message = f"The Ollama model '{settings.model}' is not installed and could not be downloaded."
        raise AskError(message)
    # The request itself goes through ollama's async client, for the reason given above.
    client = _library("ollama", "ollama").AsyncClient()
    response = await client.chat(
        model=ai.model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        format="json",
    )
    return response["message"]["content"] or ""


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
        DEEPSEEK: _ask_deepseek,
        GEMINI: _ask_gemini,
        LLAMA: _ask_llama,
    }
    handler = handlers.get(settings.provider)
    if handler is None:
        message = f"'{settings.provider}' is not an AI service MapTasker can ask."
        raise AskError(message)
    try:
        return await handler(settings, system, user)
    except AskError:
        raise
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
