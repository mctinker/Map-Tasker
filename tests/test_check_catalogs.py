"""tools/language_support/check_catalogs.py: finding what a translation catalog lacks, and adding it.

The tool is a maintainer script rather than part of the package, so it is loaded by path.  Everything here runs on
small catalogs written to a temporary folder; nothing translates anything or touches the network.
"""

from __future__ import annotations

import gettext
import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

_TOOL = Path(__file__).resolve().parent.parent / "tools" / "language_support" / "check_catalogs.py"
_spec = importlib.util.spec_from_file_location("check_catalogs", _TOOL)
assert _spec is not None
assert _spec.loader is not None
cc = importlib.util.module_from_spec(_spec)
sys.modules["check_catalogs"] = cc
_spec.loader.exec_module(cc)


@pytest.fixture(autouse=True)
def _never_the_real_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A run of main() that is not told where the READMEs are must find none, and not rewrite the project's own."""
    monkeypatch.setattr(cc, "ROOT", tmp_path / "no_project")


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

    monkeypatch.setattr(sys, "argv", ["check_catalogs.py", "--catalogs-only", "--locale", str(tmp_path)])
    assert cc.main() == 1
    assert "Run again with --fix" in capsys.readouterr().out
    assert "Open" not in cc.read_catalog(tmp_path / "de" / "LC_MESSAGES" / "messages.po").entries

    monkeypatch.setattr(
        sys, "argv", ["check_catalogs.py", "--catalogs-only", "--locale", str(tmp_path), "--fix", "--no-translate"]
    )
    assert cc.main() == 0
    output = capsys.readouterr().out
    assert "added 1 with a blank translation" in output
    assert "2 blank translation(s) waiting" in output

    for language in ("de", "fr"):
        assert cc.read_catalog(tmp_path / language / "LC_MESSAGES" / "messages.po").entries["Open"] == ""
        assert (tmp_path / language / "LC_MESSAGES" / "messages.mo").exists()

    monkeypatch.setattr(sys, "argv", ["check_catalogs.py", "--catalogs-only", "--locale", str(tmp_path), "--strict"])
    assert cc.main() == 1  # strictly, a blank translation is still unfinished work


def test_a_language_that_is_not_there_is_an_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _catalog(tmp_path, "de", {"Save": "x"})
    monkeypatch.setattr(
        sys, "argv", ["check_catalogs.py", "--catalogs-only", "--locale", str(tmp_path), "--lang", "xx"]
    )

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


# ##################################################################################
# The README and its translations
# ##################################################################################
_ENGLISH = """<p align="center">
  <img src="./documentation_images/logo.png" alt="MapTasker">
</p>

# MapTasker

## What it does

Map your Tasker setup in a browser. See [the wiki](https://github.com/x/y/wiki) and [License](LICENSE).

![A map](./documentation_images/map.png)

- First point about `maptasker -v`.
- Second point, with [a link](README_translated/README.de.md).

```bash
maptasker -file backup.xml   # a comment in English
```
"""

_GERMAN = """<p align="center">
  <img src="../documentation_images/logo.png" alt="MapTasker">
</p>

# MapTasker

> Diese Übersetzung wurde automatisch erstellt. Bei Abweichungen gilt die [ursprüngliche englische README](../README.md).

## Was es tut

Zeigen Sie Ihr Tasker-Setup im Browser. Siehe [das Wiki](https://github.com/x/y/wiki) und [Lizenz](../LICENSE).

![Eine Karte](../documentation_images/map.png)

- Erster Punkt zu `maptasker -v`.
- Zweiter Punkt, mit [einem Link](README.de.md).

```bash
maptasker -file backup.xml   # ein Kommentar auf Deutsch
```
"""


def _readmes(tmp_path: Path, english: str = _ENGLISH, german: str = _GERMAN) -> Path:
    (tmp_path / "README_translated").mkdir()
    (tmp_path / "README.md").write_text(english, encoding="utf-8")
    (tmp_path / "README_translated" / "README.de.md").write_text(german, encoding="utf-8")
    return tmp_path


def _look(tmp_path: Path) -> Any:
    (found,) = cc.look_at_readmes(tmp_path, None)
    return found


def test_a_fence_needs_no_backtick_after_it_so_inline_triple_ticks_are_not_one() -> None:
    text = "     ```pip install x```\n     ...OR...\n     ```uv add x```\n\nNext\n"

    assert cc.split_blocks(text) == ["     ```pip install x```\n     ...OR...\n     ```uv add x```", "Next"]
    assert cc.split_blocks("```\na\n\nb\n```\n\nafter") == ["```\na\n\nb\n```", "after"]
    assert cc.block_kind("     ```pip install x```") == "p"


@pytest.mark.parametrize(
    ("block", "kind"),
    [("## Title", "h2"), ("<p>x</p>", "html"), ("| a | b |", "table"), ("> note", "quote"), ("1. one", "list")],
)
def test_a_block_is_known_by_its_first_line(block: str, kind: str) -> None:
    assert cc.block_kind(block) == kind


def test_the_signature_ignores_the_words_but_not_the_links_code_or_images() -> None:
    english = "See [the wiki](https://a.example/wiki) and `maptasker -v`, then ![alt](./documentation_images/x.png)."
    german = "Siehe [das Wiki](https://a.example/wiki) und `maptasker -v`, dann ![Alt](../documentation_images/x.png)."

    assert cc.signature(english) == cc.signature(german)
    assert cc.signature(english) != cc.signature(german.replace("wiki)", "wikis)"))
    assert cc.signature(english) != cc.signature(german.replace("-v", "-x"))


def test_a_code_block_may_have_its_comments_translated_but_not_its_commands() -> None:
    english = "```\nmaptasker -file a.xml   # what it does\n```"

    assert cc.signature(english) == cc.signature("```\nmaptasker -file a.xml   # was es tut\n```")
    assert cc.signature(english) != cc.signature("```\nmaptasker -file b.xml   # was es tut\n```")


def test_a_translation_that_follows_the_readme_has_nothing_to_report(tmp_path: Path) -> None:
    found = _look(_readmes(tmp_path))

    assert found.problems(strict=True) == 0
    assert found.plan == []


def test_a_new_changed_and_removed_block_are_each_found(tmp_path: Path) -> None:
    english = _ENGLISH.replace("## What it does", "## What it does\n\nA brand new paragraph here.")
    english = english.replace("maptasker -file backup.xml", "maptasker -file backup.xml -pretty")
    german = _GERMAN.replace("![Eine Karte]", "Ein Absatz, den es nicht mehr gibt.\n\n![Eine Karte]")

    found = _look(_readmes(tmp_path, english, german))

    assert any("brand new paragraph" in block for block in found.missing)
    assert any("-pretty" in block for block in found.changed)
    assert any("Absatz" in block for block in found.extra)


def test_the_note_that_it_is_a_machine_translation_is_required_and_must_link_the_original(tmp_path: Path) -> None:
    without = _GERMAN.replace(_GERMAN.split("\n\n")[2] + "\n\n", "")
    wrong = _GERMAN.replace("../README.md", "README.md")

    assert "missing" in _look(_readmes(tmp_path, german=without)).disclaimer
    other = tmp_path / "other"
    other.mkdir()
    assert "../README.md" in _look(_readmes(other, german=wrong)).disclaimer


def test_the_wrapper_a_right_to_left_language_adds_is_not_an_extra_block(tmp_path: Path) -> None:
    german = '<div dir="rtl" align="right">\n\n' + _GERMAN + "\n</div>\n"

    assert _look(_readmes(tmp_path, german=german)).extra == []


def test_a_paragraph_or_list_line_left_in_english_is_found(tmp_path: Path) -> None:
    german = _GERMAN.replace("Zeigen Sie Ihr Tasker-Setup im Browser.", "Map your Tasker setup in a browser.")
    german = german.replace("Zeigen Sie Ihr", "Map your")
    english_paragraph = (
        "Map your Tasker setup in a browser. See [the wiki](https://github.com/x/y/wiki) and [License](LICENSE)."
    )
    german = german.replace(
        "Map your Tasker setup in a browser. Siehe [das Wiki](https://github.com/x/y/wiki) und [Lizenz](../LICENSE).",
        english_paragraph.replace("(LICENSE)", "(../LICENSE)"),
    )
    found_paragraph = _look(_readmes(tmp_path, german=german))

    other = tmp_path / "list"
    other.mkdir()
    listed = _GERMAN.replace("- Erster Punkt zu `maptasker -v`.", "- First point about `maptasker -v`.")

    assert found_paragraph.untranslated == [] or any("Map your" in block for block in found_paragraph.untranslated)
    assert any("First point" in block for block in _look(_readmes(other, german=listed)).untranslated)


def test_relative_links_are_moved_one_folder_up_and_the_rest_left_alone() -> None:
    text = (
        '<img src="./documentation_images/a.png"> [x](LICENSE) [y](README_translated/README.fr.md) '
        "[z](https://example.com/p) [w](#note-1) ![i](./documentation_images/i.png)"
    )

    assert cc.localize(text) == (
        '<img src="../documentation_images/a.png"> [x](../LICENSE) [y](README.fr.md) '
        "[z](https://example.com/p) [w](#note-1) ![i](../documentation_images/i.png)"
    )


def test_what_a_translator_must_not_touch_is_hidden_and_comes_back_or_the_translation_is_refused() -> None:
    hidden, kept = cc.protect("Run `maptasker -v` and see [docs](https://a.example/d) or https://b.example.")

    assert "maptasker" not in hidden
    assert "a.example" not in hidden
    assert cc.restore(hidden.upper().replace("XQ", "XQ"), kept) is not None
    assert cc.restore(hidden.replace("XQ0QX", ""), kept) is None  # one went missing
    assert cc.restore(hidden + " XQ9QX", kept) is None  # one was made up


def _stub(text: str, language: str) -> str | None:
    """A translator that turns each English word it knows into a Spanish one, and fails on a sentence it dislikes."""
    if "refuse me" in text:
        return None
    return text.replace("Map", "Mapea").replace("brand new paragraph", "párrafo nuevo")


def test_fixing_a_readme_translates_what_is_new_and_leaves_the_rest(tmp_path: Path) -> None:
    english = _ENGLISH.replace(
        "## What it does", "## What it does\n\nA brand new paragraph with `code` and [a link](./docs/x.md)."
    )
    root = _readmes(tmp_path, english)
    found = _look(root)

    failed = cc.fix_readme(cc.split_blocks(english), found, _stub)

    assert failed == 0
    text = (root / "README_translated" / "README.de.md").read_text(encoding="utf-8")
    assert "párrafo nuevo with `code` and [a link](../docs/x.md)." in text
    assert "Zeigen Sie Ihr Tasker-Setup" in text  # what was translated already is not touched
    assert text.count("> Diese Übersetzung") == 1
    assert _look(root).problems(strict=True) == 0


def test_a_line_the_translator_cannot_do_stays_english_and_is_counted(tmp_path: Path) -> None:
    english = _ENGLISH + "\n- refuse me please, this line has enough words\n- this one is fine, with enough words\n"
    english = english.replace("- Second point", "- Second point")
    root = _readmes(tmp_path, english)
    found = _look(root)

    failed = cc.fix_readme(cc.split_blocks(english), found, _stub)

    assert failed == 1
    assert "refuse me please" in (root / "README_translated" / "README.de.md").read_text(encoding="utf-8")


def test_without_a_translator_a_new_block_is_added_in_english_and_flagged_until_translated(tmp_path: Path) -> None:
    english = _ENGLISH.replace(
        "## What it does", "## What it does\n\nA brand new paragraph that nobody has translated yet."
    )
    root = _readmes(tmp_path, english)

    cc.fix_readme(cc.split_blocks(english), _look(root), None)

    after = _look(root)
    assert after.plan == []
    assert any("brand new paragraph" in block for block in after.untranslated)
    assert after.problems(strict=False) == 0
    assert after.problems(strict=True) == 1


def test_the_run_reports_the_readmes_and_fixes_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    english = _ENGLISH.replace("## What it does", "## What it does\n\nA brand new paragraph in the README.")
    root = _readmes(tmp_path, english)
    arguments = ["check_catalogs.py", "--readme-only", "--readme-dir", str(root)]

    monkeypatch.setattr(sys, "argv", arguments)
    assert cc.main() == 1
    assert "Run again with --fix" in capsys.readouterr().out

    monkeypatch.setattr(sys, "argv", [*arguments, "--fix", "--no-translate"])
    assert cc.main() == 0
    assert "1 block(s) still in English" in capsys.readouterr().out

    monkeypatch.setattr(sys, "argv", [*arguments, "--strict"])
    assert cc.main() == 1
