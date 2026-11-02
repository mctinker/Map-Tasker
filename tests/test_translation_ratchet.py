"""scripts/translation_ratchet.py: what it finds in the catalogs and READMEs, and what it makes of the comparison.

The gate is that the drift may only shrink: a finding the baseline does not list fails, one it lists that has gone
fails until the baseline is lowered, and --update only ever removes.  Findings are keyed by what was found and the
languages it was found in, so fixing one string while leaving another out is not a wash.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "translation_ratchet.py"
_spec = importlib.util.spec_from_file_location("translation_ratchet", _SCRIPT)
assert _spec is not None
assert _spec.loader is not None
tr = importlib.util.module_from_spec(_spec)
sys.modules["translation_ratchet"] = tr
_spec.loader.exec_module(tr)

MISSING = "catalogs: missing"


def test_a_finding_the_baseline_does_not_list_is_new() -> None:
    found = {MISSING: {"Hello": {"de"}, "Bye": {"de"}}}
    allowed = {MISSING: {"Hello": {"de"}}}

    assert tr.compare(found, allowed) == ([(MISSING, "Bye", {"de"})], [])


def test_a_listed_string_missing_from_one_more_language_is_new() -> None:
    found = {MISSING: {"Hello": {"de", "fr"}}}
    allowed = {MISSING: {"Hello": {"de"}}}

    assert tr.compare(found, allowed) == ([(MISSING, "Hello", {"fr"})], [])


def test_translating_one_string_does_not_make_room_for_another() -> None:
    found = {MISSING: {"Bye": {"de"}}}
    allowed = {MISSING: {"Hello": {"de"}}}

    new, gone = tr.compare(found, allowed)

    assert new == [(MISSING, "Bye", {"de"})]
    assert gone == [(MISSING, "Hello", {"de"})]


def test_a_listed_finding_that_has_gone_is_reported_as_gone() -> None:
    found = {MISSING: {"Hello": {"de"}}}
    allowed = {MISSING: {"Hello": {"de", "fr"}}, "READMEs: changed": {"A block": {"ja"}}}

    assert tr.compare(found, allowed) == ([], [("READMEs: changed", "A block", {"ja"}), (MISSING, "Hello", {"fr"})])


def test_lowering_removes_what_is_gone_and_adds_nothing() -> None:
    found = {MISSING: {"Hello": {"de"}, "Brand new": {"de"}}}
    allowed = {MISSING: {"Hello": {"de", "fr"}, "Old": {"de"}}}

    assert tr.lowered(found, allowed) == {MISSING: {"Hello": {"de"}}}


def test_the_baseline_is_saved_sorted_one_line_a_finding(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"

    tr.save_baseline({"b: kind": {"z": {"fr", "de"}}, MISSING: {"m": {"ja"}, "a": {"de"}}, "empty": {}}, path)

    assert json.loads(path.read_text(encoding="utf-8")) == {
        MISSING: {"a": "de", "m": "ja"},
        "b: kind": {"z": "de fr"},
    }
    assert tr.load_baseline(path) == {MISSING: {"a": {"de"}, "m": {"ja"}}, "b: kind": {"z": {"de", "fr"}}}


def test_the_committed_baseline_is_the_drift_found_now() -> None:
    """The check CI runs: no new drift, and none the baseline still allows that has gone."""
    new, gone = tr.compare(tr.find_drift(), tr.load_baseline())

    assert new == []
    assert gone == []


# ---- find_drift on a small project of its own ----------------------------------------------------------
_PO_HEADER = 'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'


def _project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, catalog: str, readme_translation: str) -> ModuleType:
    """A project that asks for "Hello" and "Save {count}", with one German catalog and one German README."""
    source = tmp_path / "maptasker" / "src"
    source.mkdir(parents=True)
    (source / "app.py").write_text(
        'translate_string("Hello")\ntranslate_string("Save {count}")\n',
        encoding="utf-8",
    )
    locale = tmp_path / "maptasker" / "locale" / "de" / "LC_MESSAGES"
    locale.mkdir(parents=True)
    (locale / "messages.po").write_text(_PO_HEADER + catalog, encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "# Title\n\nFirst paragraph here.\n\nSecond paragraph here.\n", encoding="utf-8"
    )
    translated = tmp_path / "README_translated"
    translated.mkdir()
    (translated / "README.de.md").write_text(readme_translation, encoding="utf-8")
    tool = tr.load_tool()
    monkeypatch.setattr(tool, "help_strings", lambda _root: set())
    monkeypatch.setattr(tool, "mo_problem", lambda _catalog: "")
    return tool


def test_a_string_the_program_asks_for_that_a_catalog_lacks_is_a_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tool = _project(
        tmp_path,
        monkeypatch,
        catalog='msgid "Hello"\nmsgstr "Hallo"\n',
        readme_translation="",
    )

    found = tr.find_drift(tool, tmp_path)

    assert found[MISSING] == {"Save {count}": {"de"}}


def test_a_lost_placeholder_is_a_finding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tool = _project(
        tmp_path,
        monkeypatch,
        catalog='msgid "Hello"\nmsgstr "Hallo"\n\nmsgid "Save {count}"\nmsgstr "Speichern"\n',
        readme_translation="",
    )

    found = tr.find_drift(tool, tmp_path)

    assert found["catalogs: placeholders changed"] == {"Save {count}": {"de"}}
    assert MISSING not in found


def test_a_readme_edit_that_is_not_in_the_translation_is_a_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tool = _project(
        tmp_path,
        monkeypatch,
        catalog='msgid "Hello"\nmsgstr "Hallo"\n\nmsgid "Save {count}"\nmsgstr "Speichern {count}"\n',
        readme_translation="# Titel\n\nErster Absatz.\n",
    )

    found = tr.find_drift(tool, tmp_path)

    assert any(kind.startswith("READMEs: ") for kind in found)
    assert not any(kind.startswith("catalogs: ") for kind in found)
