"""What the fuzz tests share: how many examples to try, and how a file or a reply is spoiled.

Every input MapTasker reads from outside -- a backup, a settings file, a history snapshot, an answer from the phone or
from TaskerNet, a reply from an AI model -- is something it did not write.  The tests that fuzz them start from a
well-formed one and spoil it, in the ways such things really are spoiled, and check that the reader answers (a result,
a message, a MapTaskerError) and never raises.

MAPTASKER_FUZZ_SCALE=20 runs twenty times as many examples, for a long run before a release.
"""

from __future__ import annotations

import json
import os
from typing import Any

from hypothesis import HealthCheck, settings
from hypothesis import strategies as st
from maptasker.src.core.settingsmigrate import SETTINGS_VERSION, VERSION_KEY

SCALE = float(os.environ.get("MAPTASKER_FUZZ_SCALE", "1"))


def fuzz(examples: int) -> settings:
    """The settings for one fuzz test: no deadline, nothing written to .hypothesis."""
    return settings(
        max_examples=max(1, int(examples * SCALE)),
        deadline=None,
        database=None,
        print_blob=True,
        suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow, HealthCheck.data_too_large],
    )


class Shown(bytes):
    """Bytes that print as their first few thousand, so a failure on a large file reports in a screenful."""

    def __repr__(self) -> str:
        shown = bytes.__repr__(self[:3000])
        return shown if len(self) <= 3000 else f"{shown} ... ({len(self)} bytes in all)"


# ##################################################################################
# Spoiling bytes
# ##################################################################################
@st.composite
def byte_operations(draw: st.DrawFn) -> tuple[str, float, float, bytes]:
    """One way to spoil the bytes: where (as a fraction of the file), how far, and what is written there."""
    return (
        draw(st.sampled_from(["truncate", "cut", "insert", "overwrite"])),
        draw(st.integers(min_value=20, max_value=1000)) / 1000,
        draw(st.integers(min_value=0, max_value=200)) / 1000,
        draw(st.binary(max_size=8)),
    )


def spoil_bytes(data: bytes, operation: tuple[str, float, float, bytes]) -> bytes:
    """Apply one byte operation: cut the file short, cut a slice out, or write junk in the middle."""
    kind, where, how_far, junk = operation
    start = int(len(data) * where)
    end = min(len(data), start + max(1, int(len(data) * how_far)))
    match kind:
        case "truncate":
            return data[:start]
        case "cut":
            return data[:start] + data[end:]
        case "insert":
            return data[:start] + junk + data[start:]
        case _:
            return data[:start] + junk + data[start + len(junk) :]


def spoiled(base: bytes, *, max_operations: int = 3) -> st.SearchStrategy[bytes]:
    """`base`, with up to `max_operations` byte operations applied -- often untouched, which is a good file too."""

    @st.composite
    def build(draw: st.DrawFn) -> bytes:
        data = base
        for operation in draw(st.lists(byte_operations(), max_size=max_operations)):
            data = spoil_bytes(data, operation)
        return Shown(data)

    return build()


# ##################################################################################
# Documents of the wrong shape
# ##################################################################################
# Any JSON value at all: what a reader is handed when the other end sends a list for an object, a string for a number.
JSON_VALUES: st.SearchStrategy[Any] = st.recursive(
    st.none()
    | st.booleans()
    | st.integers(min_value=-(2**70), max_value=2**70)
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(max_size=12),
    lambda children: st.lists(children, max_size=4) | st.dictionaries(st.text(max_size=8), children, max_size=4),
    max_leaves=14,
)


def reshaped(base: Any) -> st.SearchStrategy[Any]:
    """`base` (a JSON value) with one part of it replaced by any other JSON value -- the right shape, almost."""

    @st.composite
    def build(draw: st.DrawFn) -> Any:
        copy = json.loads(json.dumps(base))
        if not isinstance(copy, (dict, list)) or not copy:
            return draw(JSON_VALUES)
        for _ in range(draw(st.integers(min_value=0, max_value=3))):
            node: Any = copy
            while True:
                keys = list(node) if isinstance(node, dict) else list(range(len(node)))
                if not keys:
                    break
                key = draw(st.sampled_from(keys))
                child = node[key]
                if isinstance(child, (dict, list)) and child and draw(st.booleans()):
                    node = child
                    continue
                node[key] = draw(JSON_VALUES)
                break
        return copy

    return build()


def json_text(value: Any) -> str:
    """A JSON value as the text a reader is handed."""
    return json.dumps(value)


def json_documents(base: Any) -> st.SearchStrategy[str]:
    """Text a reader of `base`'s shape might be handed: the real thing, reshaped, any value, or its bytes spoiled."""
    return st.one_of(
        reshaped(base).map(json_text),
        JSON_VALUES.map(json_text),
        spoiled(json.dumps(base).encode("utf-8")).map(lambda data: data.decode("utf-8", errors="replace")),
    )


# ##################################################################################
# Settings files of every age
# ##################################################################################
_HISTORIC_VALUES: dict[str, Any] = {
    "language": st.sampled_from(["Tamali", "Tamil", "English", "Deutsch"]),
    "ai_name": st.sampled_from(["DeepSeek", "OpenAI", "Gemini", ""]),
    "ai_model": st.sampled_from(["gemini-3.1-flash_lite", "gemini-3.1-flash-lite", "deepseek-chat", "gpt-5.5", ""]),
}


@st.composite
def files_of_any_age(draw: st.DrawFn) -> dict[str, Any]:
    """A settings document with historical values wherever they were ever kept, and any version (or none)."""
    arguments: dict[str, Any] = {name: draw(values) for name, values in _HISTORIC_VALUES.items() if draw(st.booleans())}
    document: dict[str, Any] = {"program_arguments": arguments}
    version = draw(st.one_of(st.none(), st.integers(min_value=0, max_value=SETTINGS_VERSION)))
    if version is not None:
        document[VERSION_KEY] = version
    return document
