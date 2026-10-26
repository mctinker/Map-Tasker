"""tools/language_support/check_catalogs.py: finding what a translation catalog lacks, and adding it.

The tool is a maintainer script rather than part of the package, so it is loaded by path.  Everything here runs on
small catalogs written to a temporary folder; nothing translates anything or touches the network.
"""

from __future__ import annotations

import gettext
import importlib.util
import sys
from pathlib import Path

import pytest

_TOOL = Path(__file__).resolve().parent.parent / "tools" / "language_support" / "check_catalogs.py"
_spec = importlib.util.spec_from_file_location("check_catalogs", _TOOL)
assert _spec is not None
assert _spec.loader is not None
cc = importlib.util.module_from_spec(_spec)
sys.modules["check_catalogs"] = cc
_spec.loader.exec_module(cc)

HEADER = 'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n"Language: xx\\n"\n'


def _catalog(locale: Path, language: str, entries: dict[str, str], *, extra: str = "") -> Path:
    """Write a messages.po holding these entries (and whatever raw text `extra` adds), and return its path."""
    folder = locale / language / "LC_MESSAGES"
    folder.mkdir(parents=True)
    body = "".join(f"\nmsgid {cc.encode(msgid)}\nmsgstr {cc.encode(msgstr)}\n" for msgid, msgstr in entries.items())
    path = folder / "messages.po"
    path.write_text(HEADER + body + extra, encoding="utf-8")
    return path


def _compile(path: Path) -> None:
    """Make the .mo for a catalog, by hand."""
    catalog = cc.read_catalog(path)
    original = cc.shutil.which
    cc.shutil.which = lambda _name: None
    try:
        cc.write_mo(catalog)
    finally:
        cc.shutil.which = original


# ##################################################################################
# Reading
# ##################################################################################
def test_a_catalog_is_read_into_entries_with_its_header_apart(tmp_path: Path) -> None:
    path = _catalog(tmp_path, "de", {"Save": "Speichern", "Two\nlines": "Zwei\nZeilen"})

    catalog = cc.read_catalog(path)

    assert catalog.entries == {"Save": "Speichern", "Two\nlines": "Zwei\nZeilen"}
    assert "charset=UTF-8" in catalog.header
    assert catalog.duplicates == []
    assert catalog.unreadable == 0


def test_a_msgid_defined_twice_is_a_duplicate_and_the_first_definition_stands(tmp_path: Path) -> None:
    path = _catalog(tmp_path, "de", {"Save": "Speichern"}, extra='\nmsgid "Save"\nmsgstr "Sichern"\n')

    catalog = cc.read_catalog(path)

    assert catalog.entries["Save"] == "Speichern"
    assert catalog.duplicates == ["Save"]


def test_a_context_entry_is_not_the_plain_entry_nor_its_duplicate(tmp_path: Path) -> None:
    path = _catalog(tmp_path, "nl", {"Top": "Boven"}, extra='\nmsgctxt "Location"\nmsgid "Top"\nmsgstr "Bovenkant"\n')

    catalog = cc.read_catalog(path)

    assert catalog.entries == {"Top": "Boven"}
    assert catalog.contextual == {("Location", "Top"): "Bovenkant"}
    assert catalog.duplicates == []


# ##################################################################################
# What counts as wrong
# ##################################################################################
@pytest.mark.parametrize(
    ("english", "translated", "differs"),
    [
        ("...and {count} more", "...und {count} weitere", False),
        ("...and {count} more", "...und weitere", True),
        ("%(name)s is %d", "%d ist %(name)s", False),
        ("Trace every %variable", "Verfolge jede %değişken", False),  # "%de" is a word, not a placeholder
        ("Save", "Speichern", False),
    ],
)
def test_a_translation_may_move_a_placeholder_but_not_lose_one(english: str, translated: str, differs: bool) -> None:
    assert cc.placeholders_differ(english, translated) is differs


def test_a_missing_string_is_found_and_a_blank_one_is_waiting(tmp_path: Path) -> None:
    _catalog(tmp_path, "de", {"Save": "Speichern", "Open": ""})
    catalogs = cc.read_catalogs(tmp_path, None)

    (found,) = cc.check(catalogs, {"Save", "Open", "Close"})

    assert found.missing_required == ["Close"]
    assert found.blank == ["Open"]
    assert found.to_add == ["Close", "Open"]


def test_a_blank_translation_is_a_problem_only_when_asked(tmp_path: Path) -> None:
    path = _catalog(tmp_path, "de", {"Open": ""})
    _compile(path)
    (found,) = cc.check(cc.read_catalogs(tmp_path, None), {"Open"})

    assert found.problems(strict=False) == 0
    assert found.problems(strict=True) == 1


def test_a_string_nearly_every_catalog_holds_is_expected_of_all_of_them(tmp_path: Path) -> None:
    for language in ("de", "fr", "es", "it", "nl", "pt", "sv", "da", "fi", "no"):
        _catalog(tmp_path, language, {"Save": language + "-save", "Turkish": language + "-tr"})
    _catalog(tmp_path, "zh", {"Save": "zh-save"})
    catalogs = cc.read_catalogs(tmp_path, None)

    assert cc.shared_strings(catalogs, {"Save"}) == {"Turkish"}
    zh = next(found for found in cc.check(catalogs, {"Save"}) if found.catalog.language == "zh")
    assert zh.missing_shared == ["Turkish"]


def test_a_reverse_entry_is_not_expected_of_the_other_languages(tmp_path: Path) -> None:
    """'Nada' -> 'None' turns a Spanish word back into the English the program works in; it is not a string to translate."""
    for language in ("de", "fr", "es", "it", "nl", "pt", "sv", "da", "fi", "no"):
        _catalog(tmp_path, language, {"None": language + "-none", "Nada": "None"})
    catalogs = cc.read_catalogs(tmp_path, None)

    assert cc.shared_strings(catalogs, {"None"}) == set()


def test_what_the_program_used_to_ask_for_is_not_expected(tmp_path: Path) -> None:
    for language in ("de", "fr", "es", "it", "nl", "pt", "sv", "da", "fi", "no"):
        _catalog(tmp_path, language, {"Android Get XML Port Number": "x", "ndroid Get XML Port Number": "y"})
    catalogs = cc.read_catalogs(tmp_path, None)

    assert cc.shared_strings(catalogs, {"Android Get XML Port Number"}) == set()


def test_a_compiled_catalog_that_is_missing_or_behind_its_source_is_reported(tmp_path: Path) -> None:
    path = _catalog(tmp_path, "de", {"Save": "Speichern"})
    assert "missing" in cc.mo_problem(cc.read_catalog(path))

    _compile(path)
    assert cc.mo_problem(cc.read_catalog(path)) == ""

    path.write_text(path.read_text(encoding="utf-8").replace("Speichern", "Sichern"), encoding="utf-8")
    assert "out of date" in cc.mo_problem(cc.read_catalog(path))


# ##################################################################################
# Fixing
# ##################################################################################
def test_a_hand_compiled_catalog_says_what_the_source_says_and_leaves_blanks_to_the_english(tmp_path: Path) -> None:
    path = _catalog(
        tmp_path,
        "de",
        {"Save": "Speichern", "Open": "", "Two\nlines": "Zwei\nZeilen", "Grün": "Green"},
        extra='\nmsgctxt "Location"\nmsgid "Top"\nmsgstr "Bovenkant"\n',
    )
    _compile(path)

    with path.with_suffix(".mo").open("rb") as file:
        compiled = gettext.GNUTranslations(file)

    assert compiled.gettext("Save") == "Speichern"
    assert compiled.gettext("Two\nlines") == "Zwei\nZeilen"
    assert compiled.gettext("Grün") == "Green"
    assert compiled.gettext("Open") == "Open"
    assert compiled.pgettext("Location", "Top") == "Bovenkant"
    assert "charset=UTF-8" in compiled.info()["content-type"]


def test_duplicates_and_blanks_are_taken_out_and_blank_strings_added(tmp_path: Path) -> None:
    path = _catalog(tmp_path, "de", {"Save": "Speichern", "Open": ""}, extra='\nmsgid "Save"\nmsgstr "Sichern"\n')

    assert cc.drop_duplicates(path) == 1
    assert cc.drop_blank_entries(path) == 1
    cc.append_blank(path, ["Close"])

    catalog = cc.read_catalog(path)
    assert catalog.entries == {"Save": "Speichern", "Close": ""}
    assert catalog.duplicates == []


def test_the_run_reports_then_fixes_and_the_second_look_is_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for language in ("de", "fr"):
        _catalog(tmp_path, language, {"Save": language + "-save"})
    monkeypatch.setattr(cc, "source_strings", lambda _source: {"Save", "Open"})
    monkeypatch.setattr(cc, "help_strings", lambda _root: set())
    monkeypatch.setattr(cc.shutil, "which", lambda _name: None)

    monkeypatch.setattr(sys, "argv", ["check_catalogs.py", "--locale", str(tmp_path)])
    assert cc.main() == 1
    assert "Run again with --fix" in capsys.readouterr().out
    assert "Open" not in cc.read_catalog(tmp_path / "de" / "LC_MESSAGES" / "messages.po").entries

    monkeypatch.setattr(sys, "argv", ["check_catalogs.py", "--locale", str(tmp_path), "--fix", "--no-translate"])
    assert cc.main() == 0
    output = capsys.readouterr().out
    assert "added 1 with a blank translation" in output
    assert "2 blank translation(s) waiting" in output

    for language in ("de", "fr"):
        assert cc.read_catalog(tmp_path / language / "LC_MESSAGES" / "messages.po").entries["Open"] == ""
        assert (tmp_path / language / "LC_MESSAGES" / "messages.mo").exists()

    monkeypatch.setattr(sys, "argv", ["check_catalogs.py", "--locale", str(tmp_path), "--strict"])
    assert cc.main() == 1  # strictly, a blank translation is still unfinished work


def test_a_language_that_is_not_there_is_an_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _catalog(tmp_path, "de", {"Save": "x"})
    monkeypatch.setattr(sys, "argv", ["check_catalogs.py", "--locale", str(tmp_path), "--lang", "xx"])

    assert cc.main() == 2


# ##################################################################################
# Context entries
# ##################################################################################
_CONTEXT = '\nmsgctxt "Location"\nmsgid "Top"\nmsgstr "Bovenkant"\n'


def test_an_entry_with_a_context_is_a_problem_while_nothing_looks_up_by_context(tmp_path: Path) -> None:
    _catalog(tmp_path, "nl", {"Save": "Opslaan"}, extra=_CONTEXT)
    catalogs = cc.read_catalogs(tmp_path, None)

    (unused,) = cc.check(catalogs, {"Save", "Top"})
    (used,) = cc.check(catalogs, {"Save"}, context_used=True)

    assert unused.dead_context == ["Top"]
    assert unused.missing_required == ["Top"]  # the plain entry the program asks for is not there
    assert used.dead_context == []


def test_a_context_entry_becomes_the_plain_one_or_goes_if_the_plain_one_is_there(tmp_path: Path) -> None:
    alone = _catalog(tmp_path, "nl", {"Save": "Opslaan"}, extra=_CONTEXT)
    beside = _catalog(tmp_path, "de", {"Top": "Oben"}, extra=_CONTEXT)

    assert cc.fold_context(alone) == 1
    assert cc.fold_context(beside) == 1

    assert cc.read_catalog(alone).entries == {"Save": "Opslaan", "Top": "Bovenkant"}
    assert cc.read_catalog(alone).contextual == {}
    assert cc.read_catalog(beside).entries == {"Top": "Oben"}
    assert cc.read_catalog(beside).contextual == {}
    assert cc.fold_context(alone) == 0
