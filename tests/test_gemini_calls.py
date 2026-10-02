"""The two places MapTasker calls Gemini, and the library's automatic function calling.

google-genai defaults to automatic function calling (the model calling tools the caller
supplies) and, the first time it does so through Models.generate_content, logs that this use
is "not recommended".  MapTasker supplies no tools, so it switches the feature off, and the
warning never appears.  The first two tests need nothing installed; the third runs the real
library where it is there (the "ai" extra), and is skipped where it is not.
"""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

import pytest
from maptasker.src import mapai, mapask
from maptasker.src.primitem import PrimeItems

AFC_OFF = {"automatic_function_calling": {"disable": True}}


def test_the_analysis_call_turns_automatic_function_calling_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PrimeItems.program_arguments, "ai_model", "gemini-test", raising=False)
    seen: dict = {}

    def generate_content(**kwargs: object) -> SimpleNamespace:
        seen.update(kwargs)
        return SimpleNamespace(text="an answer")

    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))

    assert mapai._process_gemini_response(client, "the query", state=PrimeItems) == "an answer"
    assert seen["config"] == AFC_OFF
    assert seen["model"] == "gemini-test"


def test_the_ask_call_turns_automatic_function_calling_off(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict = {}

    async def generate_content(**kwargs: object) -> SimpleNamespace:
        seen.update(kwargs)
        return SimpleNamespace(text="{}")

    async def aclose() -> None:
        return None

    aio = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content), aclose=aclose)
    monkeypatch.setattr(
        mapask,
        "_library",
        lambda *_args: SimpleNamespace(Client=lambda **_kwargs: SimpleNamespace(aio=aio)),
    )
    settings = mapask.ModelSettings(mapask.GEMINI, "gemini-test", "a-key")

    assert asyncio.run(mapask._ask_gemini(settings, "system text", "user text")) == "{}"
    assert seen["config"]["automatic_function_calling"] == AFC_OFF["automatic_function_calling"]
    assert seen["config"]["system_instruction"] == "system text"


def test_the_real_library_logs_no_function_calling_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    genai = pytest.importorskip("google.genai")
    from google.genai import models  # noqa: PLC0415

    monkeypatch.setattr(models.Models, "_logged_afc_warning", False)  # It warns once per process.
    monkeypatch.setattr(PrimeItems.program_arguments, "ai_model", "gemini-test", raising=False)
    client = genai.Client(api_key="not-a-real-key")
    monkeypatch.setattr(client.models, "_generate_content", lambda **_kwargs: SimpleNamespace(text="an answer"))

    with caplog.at_level(logging.INFO):
        assert mapai._process_gemini_response(client, "the query", state=PrimeItems) == "an answer"

    assert "automatic function calling" not in caplog.text.lower()
