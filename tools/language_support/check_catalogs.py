#! /usr/bin/env python3
"""Check that the translation catalogs and the translated READMEs hold what they should, and bring them up to date.

Run it now and then -- after adding a translate_string() call, rewording a help screen, or just before a
release.  With no options it only looks, changes nothing, and exits 1 if anything needs doing:

    python tools/language_support/check_catalogs.py

and with --fix it does what needs doing:

    python tools/language_support/check_catalogs.py --fix                   translate and add what is missing
    python tools/language_support/check_catalogs.py --fix --no-translate    add it with a blank translation
    python tools/language_support/check_catalogs.py --lang de,fr --verbose  just those two, listing every string
    python tools/language_support/check_catalogs.py --readme-only           leave the catalogs alone
    python tools/language_support/check_catalogs.py --catalogs-only         leave the READMEs alone

WHAT IT CHECKS, for each of maptasker/locale/*/LC_MESSAGES/messages.po

  required     Every string the program asks to have translated -- the first argument of translate_string()
               and its aliases, wherever it is a plain string, and the help texts in userhelp.py.  A catalog
               without one shows the user English where the rest of the window is in their language.
  shared       Strings the program translates through a variable, which no scan of its source can find (the
               names of the languages, say).  They are recognised by being in nearly all of the catalogs
               (90% or more) without being required, and then every catalog is expected to hold them.  The spread of 50 or
               so strings between one language's entry count and another's is mostly these.
  duplicates   A msgid defined twice: the second is dropped when the file is compiled, silently.
  ctx          An entry with a msgctxt.  The program never looks anything up by context, so such an entry is a
               translation the user is never shown -- and it makes the clean-up in sync_and_clean_po.py throw
               away the plain entry added beside it.  --fix makes it plain.
  placeholders A {name} or %s that is in the English and not in the translation (or the other way round),
               which loses a number from a message or fails when the message is built.
  .mo          messages.mo is what the program loads.  A catalog whose .po has changed since the .mo was made
               is not what the user sees.

Not checked, and not touched: the REVERSE entries.  A catalog also holds entries whose msgid is a translated
word and whose msgstr is the English ("Nada" -> "None"), which is how a language the user picked in their own
words is turned back into the English the program works in.  They look like orphans and are not, so nothing
here ever deletes an entry.  The one stage that does -- dropping a help text whose English has since changed --
is sync_and_clean_po.py's, and --fix runs it.

WHAT --fix DOES, in order

  1. removes the second definition of any msgid, and makes any msgctxt entry plain;
  2. adds each missing string.  Translated, by the local Ollama model and then Google (this needs the "ai"
     extra and a network, and is slow: about a second a string a language).  With --no-translate it is added
     with a blank translation instead, which gettext treats as "use the English", so nothing breaks and the
     catalogs agree; translate them later by running this again without --no-translate -- a blank translation
     is counted as missing;
  3. runs sync_and_clean_po.py's repairs (newlines, URLs, quotes, blank lines) over what was translated;
  4. recompiles the .mo of every catalog that changed, or that was stale.

Placeholders it can only report: a translation that lost its {count} has to be fixed by hand or by
translating that one string again.

THE TRANSLATED READMEs, README_translated/README.<code>.md against README.md

Each translation mirrors README.md block for block (a paragraph, heading, list, table, code block ...), with
the links to other files of the project given a "../" and the links to another translation shortened.  It
is found out of step when a block of README.md has no counterpart (missing), has one with other links, images,
code or table shape (changed), or when the translation has one README.md has not (extra).  Also checked: the
note after the title that points back to the English README, and blocks that are still in English (a
paragraph, or a line of a list, quote, heading or table, identical to README.md's).  Words are not compared,
since a translation has different ones.

--fix adds a missing block in the right place, replaces a changed one, drops an extra one, restores the note,
and translates whatever is in English -- the paragraphs whole and the lists, headings and tables a line at a
time.  Code, URLs, link targets and HTML are held back from the translator and put back after; a line that
loses one on the way stays in English and is reported, to be retried on the next run.  With --no-translate
the English is put in as it is.  Rewriting a file also tidies its blank lines.  Machine translation is a
start: read what it wrote before a release.

Exit status: 0 when nothing is wrong, 1 when something is -- after the fixes, if --fix was given.  A blank
translation is not "wrong" unless --strict says so.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import gettext
import importlib.util
import re
import shutil
import struct
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "maptasker" / "src"
LOCALE = ROOT / "maptasker" / "locale"

# The calls whose first argument is a string the user is shown, and that has to be in every catalog.
TRANSLATE_FUNCTIONS = {"translate_string", "_translate", "_"}

# A string no scan finds is "shared" when at least this fraction of the catalogs hold it.  High, because the
# catalogs also hold strings left over from machine translation that are in two thirds of them and are nothing
# the program asks for.
SHARED_FRACTION = 0.9

# ... unless it is this alike a string the program does ask for, in which case it is what the program used to ask
# for, before a typo was fixed or a word changed, and no catalog is expected to hold it.
STALE_VARIANT = 0.92

_QUOTED = r'"(?:[^"\\]|\\.)*"'
ENTRY = re.compile(
    rf"^(?:msgctxt\s+(?P<context>{_QUOTED}(?:\s*\n\s*{_QUOTED})*)\s*\n)?msgid\s+(?P<id>{_QUOTED}(?:\s*\n\s*{_QUOTED})*)\s*\nmsgstr\s+(?P<str>{_QUOTED}(?:\s*\n\s*{_QUOTED})*)[ \t]*$",
    re.MULTILINE,
)
# What a translator must leave alone: {name}, %(name)s, and a bare %s or %d (but not the "%de" of a word
# that happens to start with %d, like Turkish's %değişken).
PLACEHOLDER = re.compile(r"\{[A-Za-z_][A-Za-z_0-9]*\}|%\([A-Za-z_]+\)[sd]|%[sd](?![A-Za-z])")


def decode(literal: str) -> str:
    """A (possibly multi-line) .po string literal as the text it stands for."""
    joined = "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', literal))
    return (
        joined.replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r").replace('\\"', '"').replace("\\\\", "\\")
    )


def encode(text: str) -> str:
    """Text as a single-line .po string literal."""
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
    escaped = escaped.replace("\r", "\\r")
    return f'"{escaped}"'


# ######################################################################################
# What the program asks for
# ######################################################################################
def source_strings(source: Path) -> set[str]:
    """Every plain string handed to translate_string() (or an alias) anywhere under `source`."""
    found: set[str] = set()
    for py_file in sorted(source.rglob("*.py")):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError as error:
            print(f"[skipped] {py_file.name} does not parse: {error}")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
            first = node.args[0]
            if (
                name in TRANSLATE_FUNCTIONS
                and isinstance(first, ast.Constant)
                and isinstance(first.value, str)
                and first.value.strip()
            ):
                found.add(first.value)
    return found


def uses_context(source: Path) -> bool:
    """Whether the program looks anything up by msgctxt (pgettext), which is what a msgctxt entry is for."""
    return any("pgettext(" in py_file.read_text(encoding="utf-8") for py_file in source.rglob("*.py"))


def help_strings(root: Path) -> set[str]:
    """The userhelp.py constants, which are translated as a whole but never appear as a call's argument."""
    sys.path.insert(0, str(root))
    try:
        from maptasker.src.gui import userhelp
    finally:
        sys.path.remove(str(root))
    return {
        value
        for name in dir(userhelp)
        if name.isupper() and name not in {"HELP", "VERSION"}
        if isinstance(value := getattr(userhelp, name), str) and value.strip()
    }


# ######################################################################################
# Reading a catalog
# ######################################################################################
@dataclass
class Catalog:
    """One messages.po as the check sees it."""

    language: str
    path: Path
    header: str = ""  # the metadata entry (the empty msgid)
    entries: dict[str, str] = field(default_factory=dict)  # msgid -> msgstr (the first definition of each)
    contextual: dict[tuple[str, str], str] = field(default_factory=dict)  # (msgctxt, msgid) -> msgstr
    duplicates: list[str] = field(default_factory=list)  # msgids defined more than once
    unreadable: int = 0  # msgid lines the entry pattern did not make an entry of

    @property
    def mo_path(self) -> Path:
        """The compiled catalog the program loads."""
        return self.path.with_suffix(".mo")


def read_catalog(path: Path) -> Catalog:
    """Parse one messages.po.  The header (the empty msgid) is left out."""
    catalog = Catalog(language=path.parent.parent.name, path=path)
    text = path.read_text(encoding="utf-8")
    for match in ENTRY.finditer(text):
        msgid = decode(match.group("id"))
        if match.group("context") is not None:
            # A msgctxt entry is looked up with pgettext(), which nothing here calls; it is kept apart so
            # that it is neither mistaken for the plain entry of the same msgid nor for a duplicate of it.
            catalog.contextual[decode(match.group("context")), msgid] = decode(match.group("str"))
            continue
        if not msgid:
            catalog.header = decode(match.group("str"))
            continue
        if msgid in catalog.entries:
            catalog.duplicates.append(msgid)
            continue
        catalog.entries[msgid] = decode(match.group("str"))
    # Every msgid line should have become an entry (or the header); one that did not is a malformed entry.
    catalog.unreadable = len(re.findall(r"^msgid\s", text, re.MULTILINE)) - len(ENTRY.findall(text))
    return catalog


def read_catalogs(locale: Path, languages: set[str] | None) -> list[Catalog]:
    """Every catalog under `locale`, or just the languages asked for."""
    paths = sorted(locale.glob("*/LC_MESSAGES/messages.po"))
    return [read_catalog(path) for path in paths if languages is None or path.parent.parent.name in languages]


# ######################################################################################
# The check
# ######################################################################################
@dataclass
class Findings:
    """What is wrong with one catalog."""

    catalog: Catalog
    missing_required: list[str] = field(default_factory=list)
    missing_shared: list[str] = field(default_factory=list)
    blank: list[str] = field(default_factory=list)  # expected, present, and not yet translated
    placeholders: list[str] = field(default_factory=list)  # msgids whose placeholders the translation changed
    dead_context: list[str] = field(default_factory=list)  # msgctxt entries, which the program never looks up
    stale_mo: str = ""  # why messages.mo is not what messages.po says, or ""

    @property
    def to_add(self) -> list[str]:
        """The strings --fix has to put in, or translate: missing, and blank."""
        return sorted({*self.missing_required, *self.missing_shared, *self.blank})

    def problems(self, *, strict: bool) -> int:
        """How many things are wrong, for the exit status."""
        count = (
            len(self.missing_required)
            + len(self.missing_shared)
            + len(self.catalog.duplicates)
            + len(self.placeholders)
            + len(self.dead_context)
            + self.catalog.unreadable
            + bool(self.stale_mo)
        )
        return count + (len(self.blank) if strict else 0)


def shared_strings(catalogs: list[Catalog], required: set[str]) -> set[str]:
    """Strings no scan of the source finds that most catalogs nevertheless hold, and so all are expected to.

    A reverse entry ("Nada" -> "None": a translated word in, the English out) is in many catalogs too, but it
    is a lookup for one language's words, not a string to translate into the rest, so an entry whose
    translation is itself an English string is not counted.
    """
    english = set(required)
    holders: dict[str, int] = {}
    for catalog in catalogs:
        for msgid in catalog.entries:
            if msgid not in required:
                holders[msgid] = holders.get(msgid, 0) + 1
    candidates = {msgid for msgid, count in holders.items() if count >= SHARED_FRACTION * len(catalogs)}
    english |= candidates

    required_list = sorted(required)
    shared = set()
    for msgid in candidates:
        translations = [catalog.entries[msgid] for catalog in catalogs if msgid in catalog.entries]
        if sum(translation in english for translation in translations) >= len(translations) / 2:
            continue  # A reverse entry.
        # A string a few characters off one the program asks for is what the program used to ask for.
        if difflib.get_close_matches(msgid, required_list, n=1, cutoff=STALE_VARIANT) and len(msgid) > 8:
            continue
        shared.add(msgid)
    return shared


def placeholders_differ(msgid: str, msgstr: str) -> bool:
    """Whether a translation has lost, added or changed a placeholder."""
    return sorted(PLACEHOLDER.findall(msgid)) != sorted(PLACEHOLDER.findall(msgstr))


def mo_problem(catalog: Catalog) -> str:
    """Why messages.mo does not say what messages.po does, or "" when it does."""
    if not catalog.mo_path.exists():
        return "messages.mo is missing"
    try:
        with catalog.mo_path.open("rb") as file:
            compiled = gettext.GNUTranslations(file)
    except (OSError, ValueError):
        return "messages.mo cannot be read"
    stale = sum(1 for msgid, msgstr in catalog.entries.items() if msgstr and compiled.gettext(msgid) != msgstr)
    stale += sum(
        1
        for (context, msgid), msgstr in catalog.contextual.items()
        if msgstr and compiled.pgettext(context, msgid) != msgstr
    )
    return f"messages.mo is out of date ({stale} entries differ)" if stale else ""


def check(catalogs: list[Catalog], required: set[str], *, context_used: bool = False) -> list[Findings]:
    """What is wrong with each catalog.  `context_used` is whether the program looks anything up by msgctxt."""
    shared = shared_strings(catalogs, required)
    results = []
    for catalog in catalogs:
        findings = Findings(catalog)
        for msgid in sorted(required | shared):
            target = findings.missing_required if msgid in required else findings.missing_shared
            if msgid not in catalog.entries:
                target.append(msgid)
            elif not catalog.entries[msgid]:
                findings.blank.append(msgid)
        findings.placeholders = [
            msgid for msgid, msgstr in catalog.entries.items() if msgstr and placeholders_differ(msgid, msgstr)
        ]
        if not context_used:
            findings.dead_context = [msgid for _context, msgid in catalog.contextual]
        findings.stale_mo = mo_problem(catalog)
        results.append(findings)
    return results


def look(locale: Path, required: set[str], languages: set[str] | None) -> list[Findings]:
    """check() over every catalog -- what is "shared" depends on all of them -- reporting on the languages asked for."""
    results = check(read_catalogs(locale, None), required, context_used=uses_context(SOURCE))
    return [found for found in results if languages is None or found.catalog.language in languages]


def report(results: list[Findings], required: set[str], *, verbose: bool) -> None:
    """Print the counts, one line a language, and with --verbose the strings themselves."""
    print(f"{len(required)} strings required (call sites and help texts)\n")
    print(f"{'':6}{'entries':>8}{'missing':>9}{'shared':>8}{'blank':>7}{'dups':>6}{'ctx':>5}{'placeholders':>14}  .mo")
    for found in results:
        catalog = found.catalog
        print(
            f"{catalog.language:6}{len(catalog.entries):>8}{len(found.missing_required):>9}"
            f"{len(found.missing_shared):>8}{len(found.blank):>7}{len(catalog.duplicates):>6}"
            f"{len(found.dead_context):>5}{len(found.placeholders):>14}  {found.stale_mo or 'ok'}",
        )
    if not verbose:
        return
    for found in results:
        for label, strings in (
            ("missing", found.missing_required),
            ("missing (shared)", found.missing_shared),
            ("blank", found.blank),
            ("duplicate", found.catalog.duplicates),
            ("context entry nothing looks up", found.dead_context),
            ("placeholders changed", found.placeholders),
        ):
            for msgid in strings:
                print(f"{found.catalog.language}: {label}: {msgid[:90]!r}")


# ######################################################################################
# The fixes
# ######################################################################################
def drop_duplicates(path: Path) -> int:
    """Remove the second and later definitions of a msgid from one file.  Returns how many."""
    text = path.read_text(encoding="utf-8")
    seen: set[str] = set()
    removed = 0

    def keep(match: re.Match[str]) -> str:
        nonlocal removed
        msgid = decode(match.group("id"))
        if msgid and msgid in seen:
            removed += 1
            return ""
        seen.add(msgid)
        return match.group(0)

    cleaned = ENTRY.sub(keep, text)
    if removed:
        path.write_text(re.sub(r"\n{3,}", "\n\n", cleaned), encoding="utf-8")
    return removed


def fold_context(path: Path) -> int:
    """Make each msgctxt entry a plain one, or drop it if the plain entry is there already.  Returns how many.

    The program looks strings up with gettext(), which never finds an entry that has a context, and the clean-up
    stages of sync_and_clean_po.py take a context entry's msgid for the plain entry's duplicate.  So a context
    entry is a translation the user is not shown, and that stops the plain one being added.
    """
    text = path.read_text(encoding="utf-8")
    plain = {decode(match.group("id")) for match in ENTRY.finditer(text) if match.group("context") is None}
    folded = 0

    def fold(match: re.Match[str]) -> str:
        nonlocal folded
        if match.group("context") is None:
            return match.group(0)
        folded += 1
        if decode(match.group("id")) in plain:
            return ""
        return f"msgid {match.group('id')}\nmsgstr {match.group('str')}"

    folded_text = ENTRY.sub(fold, text)
    if folded:
        path.write_text(re.sub(r"\n{3,}", "\n\n", folded_text), encoding="utf-8")
    return folded


def drop_blank_entries(path: Path) -> int:
    """Remove entries with an empty translation, so that translating them again adds them back.  Returns how many."""
    text = path.read_text(encoding="utf-8")
    removed = 0

    def keep(match: re.Match[str]) -> str:
        nonlocal removed
        if decode(match.group("id")) and not decode(match.group("str")):
            removed += 1
            return ""
        return match.group(0)

    cleaned = ENTRY.sub(keep, text)
    if removed:
        path.write_text(re.sub(r"\n{3,}", "\n\n", cleaned), encoding="utf-8")
    return removed


def append_blank(path: Path, strings: list[str]) -> None:
    """Add each string with an empty translation: gettext then shows the English."""
    with path.open("a", encoding="utf-8") as file:
        for msgid in strings:
            file.write(f'\nmsgid {encode(msgid)}\nmsgstr ""\n')


_loaded_tools: dict[str, ModuleType] = {}  # sync_and_clean_po, once it has been loaded


def load_sync_tool(locale: Path) -> ModuleType:
    """sync_and_clean_po.py, pointed at this tree.  It needs the "ai" extra and deep-translator, so only --fix loads it."""
    if "sync" not in _loaded_tools:
        path = Path(__file__).with_name("sync_and_clean_po.py")
        spec = importlib.util.spec_from_file_location("sync_and_clean_po", path)
        if spec is None or spec.loader is None:
            message = f"cannot load {path}"
            raise ImportError(message)
        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(ROOT))
        spec.loader.exec_module(module)
        _loaded_tools["sync"] = module
    tool = _loaded_tools["sync"]
    vars(tool).update(SRC_PATH=SOURCE, LOCALE_PATH=locale)  # the stages read these as globals
    return tool


def translate_missing(results: list[Findings], locale: Path) -> int:
    """Translate and append each catalog's missing strings.  Returns how many could not be translated."""
    tool = load_sync_tool(locale)
    total = sum(len(found.to_add) for found in results)
    failed = 0
    with tool.Progress(
        tool.TextColumn("[progress.description]{task.description}"),
        tool.BarColumn(),
        tool.MofNCompleteColumn(),
        tool.TimeElapsedColumn(),
        tool.TimeRemainingColumn(),
    ) as progress:
        overall = progress.add_task("All languages", total=total)
        for found in results:
            _added, bad = tool.sync_language(
                found.catalog.path, found.catalog.language, found.to_add, progress, overall
            )
            failed += bad
    return failed


def clean_translated(locale: Path) -> None:
    """sync_and_clean_po.py's repairs for what machine translation gets wrong, over every catalog."""
    tool = load_sync_tool(locale)
    for number in (3, 4, 5, 6, 7):  # dups, newlines, urls, quotes, blanks
        _name, banner, run = tool.STAGES[number]
        print(f"\n{banner}")
        run()


def prune_stale_help(locale: Path) -> None:
    """Drop help texts whose English has since been reworded (sync_and_clean_po.py's stage 2)."""
    tool = load_sync_tool(locale)
    tool.stage_prune_stale_help_msgids()


def write_mo(catalog: Catalog) -> None:
    """Compile one catalog with msgfmt if there is one (as po_to_mo.sh does), or by hand if not."""
    msgfmt = shutil.which("msgfmt")
    if msgfmt:
        result = subprocess.run(
            [msgfmt, "--check", "-o", str(catalog.mo_path), str(catalog.path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            print(f"{catalog.language}: msgfmt reported:\n{result.stderr.strip()}")
        return

    # No msgfmt: the GNU .mo format is a sorted table of (msgid, msgstr) behind a small header.
    fresh = read_catalog(catalog.path)
    pairs = {"": fresh.header, **{msgid: msgstr for msgid, msgstr in fresh.entries.items() if msgstr}}
    pairs.update({f"{context}\x04{msgid}": msgstr for (context, msgid), msgstr in fresh.contextual.items() if msgstr})
    keys = sorted(pairs)
    ids = b""
    strs = b""
    offsets = []
    for key in keys:
        raw_key, raw_value = key.encode("utf-8"), pairs[key].encode("utf-8")
        offsets.append((len(ids), len(raw_key), len(strs), len(raw_value)))
        ids += raw_key + b"\0"
        strs += raw_value + b"\0"
    table_size = 7 * 4 + 16 * len(keys)
    id_start, str_start = table_size, table_size + len(ids)
    id_table = b"".join(struct.pack("<II", length, id_start + offset) for offset, length, _, _ in offsets)
    str_table = b"".join(struct.pack("<II", length, str_start + offset) for _, _, offset, length in offsets)
    header_bytes = struct.pack("<7I", 0x950412DE, 0, len(keys), 7 * 4, 7 * 4 + 8 * len(keys), 0, 0)
    catalog.mo_path.write_bytes(header_bytes + id_table + str_table + ids + strs)


def fix(results: list[Findings], required: set[str], locale: Path, *, translate: bool) -> int:
    """Bring the catalogs up to date.  Returns how many strings could not be translated."""
    languages = {found.catalog.language for found in results}
    for found in results:
        removed = drop_duplicates(found.catalog.path)
        if removed:
            print(f"{found.catalog.language}: removed {removed} duplicate definition(s)")
        if found.dead_context:
            folded = fold_context(found.catalog.path)
            print(f"{found.catalog.language}: made {folded} context entr{'y' if folded == 1 else 'ies'} plain")

    if translate:
        # A blank translation is taken out so that it is translated now and added back whole, and a help text
        # whose English has changed is dropped so that the current one is added in its place.
        for found in results:
            drop_blank_entries(found.catalog.path)
        prune_stale_help(locale)

    results = look(locale, required, languages)
    if not translate:
        for found in results:
            missing = sorted({*found.missing_required, *found.missing_shared})
            if missing:
                append_blank(found.catalog.path, missing)
                print(f"{found.catalog.language}: added {len(missing)} with a blank translation")
        return 0

    failed = translate_missing([found for found in results if found.to_add], locale)
    clean_translated(locale)
    return failed


# ######################################################################################
# The README and its translations
# ######################################################################################
# README_translated/README.<code>.md follows README.md block for block: the same headings, paragraphs, lists,
# images, code and links, in the same order, with the prose translated and the relative paths pointing one
# folder up.  So the check does not read the translation; it compares what a translator must leave alone.
FENCE_OPEN = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
LINK_TARGET = re.compile(r"\]\(<?([^)>\s]+)>?(?:\s+\"[^\"]*\")?\)")
HTML_TARGET = re.compile(r"""(?:src|href|srcset)=["']([^"']+)["']""")
BARE_URL = re.compile(r"(?<![(<\"'=])https?://[^\s)>\"'\]]+")
CODE_SPAN = re.compile(r"(`+)(.+?)\1")
HTML_TAG = re.compile(r"</?[A-Za-z][^>]*>")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")
COMMENT_IN_CODE = re.compile(r"(?:^|\s+)#\s.*$")
# The translations keep the English README's relative paths, one folder further up.
LOCALIZED_PREFIXES = ("README_translated/", "./", "../")
NOT_TRANSLATED = {"code", "html", "rule"}


@dataclass
class ReadmeFindings:
    """What is out of step between README.md and one translation of it."""

    language: str
    path: Path
    exists: bool = True
    blocks: int = 0
    missing: list[str] = field(default_factory=list)  # blocks of the English README with no counterpart
    changed: list[str] = field(default_factory=list)  # English blocks whose counterpart has other code, links or images
    extra: list[str] = field(default_factory=list)  # blocks of the translation with no English original
    untranslated: list[str] = field(default_factory=list)  # blocks that are still the English text
    disclaimer: str = ""  # why the "automatic translation" note is wrong, or ""
    plan: list[tuple[str, int, int, int, int]] = field(default_factory=list)  # difflib opcodes, for --fix

    def problems(self, *, strict: bool) -> int:
        """How many things are wrong, for the exit status."""
        count = len(self.missing) + len(self.changed) + len(self.extra) + bool(self.disclaimer) + (not self.exists)
        return count + (len(self.untranslated) if strict else 0)


def opens_fence(line: str) -> str:
    """The fence a line opens ("```" or "~~~"), or "".  A backtick fence has no backtick after it: ```x``` is code spans."""
    opening = FENCE_OPEN.match(line)
    if opening and not (opening.group(1)[0] == "`" and "`" in opening.group(2)):
        return opening.group(1)
    return ""


def split_blocks(text: str) -> list[str]:
    """The blocks of a markdown file: runs of lines between blank lines, with a fenced code block kept whole."""
    blocks: list[str] = []
    current: list[str] = []
    fence = ""
    for line in text.split("\n"):
        if fence:
            current.append(line)
            closing = FENCE_OPEN.match(line)
            if closing and closing.group(1)[0] == fence[0] and len(closing.group(1)) >= len(fence):
                fence = ""
        elif fence := opens_fence(line):
            current.append(line)
        elif not line.strip():
            if current:
                blocks.append("\n".join(current))
                current = []
        else:
            current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


def block_kind(block: str) -> str:
    """What sort of block this is: a heading of some level, html, code, table, quote, list, rule or paragraph."""
    first = block.split("\n", 1)[0]
    if opens_fence(first):
        return "code"
    if first.startswith("#"):
        return f"h{len(first) - len(first.lstrip('#'))}"
    if first.startswith("<"):
        return "html"
    if first.startswith("|"):
        return "table"
    if first.startswith(">"):
        return "quote"
    if LIST_ITEM.match(first):
        return "list"
    return "rule" if re.fullmatch(r"[-*_]{3,}", first.strip()) else "p"


def neutral(target: str) -> str:
    """A link target as the English README would write it, so the two can be compared."""
    target = target.strip()
    stripped = True
    while stripped:
        stripped = False
        for prefix in LOCALIZED_PREFIXES:
            if target.startswith(prefix):
                target = target.removeprefix(prefix)
                stripped = True
    return target


def signature(block: str) -> tuple[object, ...]:
    """What a translator must not change in a block: its kind, links, images, code and the shape of its list."""
    kind = block_kind(block)
    if kind == "code":
        # The words after a # in a code block are comments, and are translated; the commands are not.
        lines = [COMMENT_IN_CODE.sub("", line).rstrip() for line in block.split("\n")]
        return (kind, tuple(line for line in lines if line.strip()))
    if kind == "html":
        # The tags and where they point; the words between them are the translation.
        tags = tuple(
            re.sub(r"""(src|href|srcset)=(["'])([^"']+)\2""", lambda m: f"{m[1]}={neutral(m[3])}", tag)
            for tag in HTML_TAG.findall(block)
        )
        return (kind, tags)
    targets = [neutral(m[1]) for m in LINK_TARGET.finditer(block)]
    targets += [neutral(m[1]) for m in HTML_TARGET.finditer(block)]
    targets += [neutral(m[0]) for m in BARE_URL.finditer(block)]
    spans = tuple(m[2] for m in CODE_SPAN.finditer(block))
    items = sum(1 for line in block.split("\n") if LIST_ITEM.match(line)) if kind == "list" else 0
    rows = block.count("\n") if kind == "table" else 0
    columns = block.split("\n", 1)[0].count("|") if kind == "table" else 0
    return (kind, tuple(sorted(set(targets))), spans, items, columns, rows)


def is_disclaimer(blocks: list[str], index: int) -> bool:
    """Whether blocks[index] is the note a machine-translated README opens with: a quote straight after the title."""
    return index > 0 and block_kind(blocks[index]) == "quote" and block_kind(blocks[index - 1]) == "h1"


def words(block: str, *, link_text: bool = True) -> list[str]:
    """The words of a block that are prose: not its code, tags or link targets, and with link_text=False not
    the words a link is made of either (a list of product names is all links, and is not English to translate)."""
    prose = CODE_SPAN.sub(" ", HTML_TAG.sub(" ", block))
    prose = re.sub(r"!?\[[^\]]*\]\([^)]*\)", " ", prose) if not link_text else LINK_TARGET.sub("]", prose)
    return re.findall(r"[^\W\d_]{3,}", BARE_URL.sub(" ", prose))


def excerpt(block: str) -> str:
    """The start of a block, on one line, for the report."""
    return " ".join(block.split())[:70]


def readme_languages(readme_dir: Path) -> dict[str, Path]:
    """{code: path} for each README_translated/README.<code>.md."""
    found = sorted((readme_dir / "README_translated").glob("README.*.md"))
    return {path.name[len("README.") : -len(".md")]: path for path in found}


RTL_OPEN = re.compile(r"""^<div\s+dir=["']rtl["'][^>]*>$""")


def without_rtl_wrapper(blocks: list[str]) -> tuple[list[str], tuple[int, str, str | None] | None]:
    """The blocks less the <div dir="rtl"> a right-to-left language wraps its README in, and the wrapper.

    The wrapper is (where its opening tag was, the tag, its closing "</div>" if the last block is one).
    """
    for index, block in enumerate(blocks):
        if RTL_OPEN.match(block.strip()):
            rest = blocks[:index] + blocks[index + 1 :]
            closing = rest.pop() if rest and rest[-1].strip() == "</div>" else None
            return rest, (index, block, closing)
    return blocks, None


def without_disclaimer(blocks: list[str]) -> tuple[list[str], str | None]:
    """The blocks less the machine-translation note, and the note (None if there is none)."""
    for index in range(len(blocks)):
        if is_disclaimer(blocks, index):
            return blocks[:index] + blocks[index + 1 :], blocks[index]
    return blocks, None


ANCHOR = re.compile(r"[A-Z][A-Za-z0-9_.+-]{2,}|\d[\w.]*")
GAP = -1.0


def anchors(block: str) -> set[str]:
    """The names, numbers and acronyms in a block's prose, which a translation tends to keep as they are."""
    return set(ANCHOR.findall(CODE_SPAN.sub(" ", HTML_TAG.sub(" ", block))))


def pair_score(english: str, translated: str) -> float | None:
    """How well a block of the translation can be the counterpart of one of the English, or None if it cannot.

    Blocks of one kind with the same links, code and images are a likelier pair than those with different ones,
    and among those the one that keeps more of the English block's names, numbers and about its length is likelier.
    Without this, two paragraphs that have no links in them look the same, and a new one is paired with an old one.
    """
    if block_kind(english) != block_kind(translated):
        return None
    base = 3.0 if signature(english) == signature(translated) else 0.5
    names = anchors(english)
    shared = len(names & set(re.findall(ANCHOR, translated))) / len(names) if names else 0.0
    ratio = min(len(english), len(translated)) / max(len(english), len(translated), 1)
    return base + 3.0 * shared + ratio


def align(english: list[str], translated: list[str]) -> list[tuple[str, int, int, int, int]]:
    """How the translation lines up with the English: the steps that are not a match, as difflib-style opcodes.

    "delete" is a block only the English has, "insert" one only the translation has, and "replace" a pair that
    line up but differ in their links, images or code.  Found by the best path through the two lists in order.
    """
    rows, columns = len(english), len(translated)
    best = [[0.0] * (columns + 1) for _ in range(rows + 1)]
    for i in range(1, rows + 1):
        best[i][0] = i * GAP
    for j in range(1, columns + 1):
        best[0][j] = j * GAP
    for i in range(1, rows + 1):
        for j in range(1, columns + 1):
            score = pair_score(english[i - 1], translated[j - 1])
            options = [best[i - 1][j] + GAP, best[i][j - 1] + GAP]
            if score is not None:
                options.append(best[i - 1][j - 1] + score)
            best[i][j] = max(options)

    steps: list[tuple[str, int, int, int, int]] = []
    i, j = rows, columns
    while i or j:
        score = pair_score(english[i - 1], translated[j - 1]) if i and j else None
        if score is not None and best[i][j] == best[i - 1][j - 1] + score:
            if signature(english[i - 1]) != signature(translated[j - 1]):
                steps.append(("replace", i - 1, i, j - 1, j))
            i, j = i - 1, j - 1
        elif i and best[i][j] == best[i - 1][j] + GAP:
            steps.append(("delete", i - 1, i, j, j))
            i -= 1
        else:
            steps.append(("insert", i, i, j - 1, j))
            j -= 1
    return steps[::-1]


def look_at_readme(english: list[str], code: str, path: Path) -> ReadmeFindings:
    """Compare one translation with the English blocks."""
    found = ReadmeFindings(language=code, path=path)
    if not path.exists():
        found.exists = False
        return found
    blocks = split_blocks(path.read_text(encoding="utf-8"))
    found.blocks = len(blocks)

    body, _wrapper = without_rtl_wrapper(blocks)
    kept, note = without_disclaimer(body)
    if note is None:
        found.disclaimer = "the note that this is a machine translation is missing"
    elif "../README.md" not in note:
        found.disclaimer = "the note does not link to the original ../README.md"

    found.plan = align(english, kept)
    for op, i1, i2, j1, j2 in found.plan:
        if op == "insert":
            found.extra += [excerpt(kept[j]) for j in range(j1, j2)]
        elif op == "delete":
            found.missing += [excerpt(english[i]) for i in range(i1, i2)]
        else:
            # replace: the blocks that line up are changed; the surplus on either side is missing or extra.
            pairs = min(i2 - i1, j2 - j1)
            found.changed += [excerpt(english[i1 + k]) for k in range(pairs)]
            found.missing += [excerpt(english[i]) for i in range(i1 + pairs, i2)]
            found.extra += [excerpt(kept[j]) for j in range(j1 + pairs, j2)]

    found.untranslated = [excerpt(block) for block in still_english(english, kept)]
    return found


def english_prose_lines(english: list[str]) -> set[str]:
    """The lines of README.md's lists, quotes, headings and tables that are prose to translate."""
    return {
        line
        for block in english
        if block_kind(block) not in NOT_TRANSLATED | {"p"}
        for line in block.split("\n")
        if len(words(line, link_text=False)) >= 3
    }


def still_english(english: list[str], translated: list[str]) -> list[str]:
    """The blocks of the translation that are still the English: a paragraph word for word, or a list, quote,
    heading or table with a line of it left (one the translator could not do keeps its English line)."""
    paragraphs = {block for block in english if block_kind(block) == "p" and len(words(block, link_text=False)) >= 3}
    lines = english_prose_lines(english)
    return [
        block
        for block in translated
        if block in paragraphs
        or (block_kind(block) not in NOT_TRANSLATED | {"p"} and any(line in lines for line in block.split("\n")))
    ]


def look_at_readmes(readme_dir: Path, languages: set[str] | None) -> list[ReadmeFindings]:
    """README.md against each translation (or just the languages asked for)."""
    main = readme_dir / "README.md"
    if not main.exists():
        return []
    english = split_blocks(main.read_text(encoding="utf-8"))
    wanted = None if languages is None else {name.replace("_", "-").lower() for name in languages}
    return [
        look_at_readme(english, code, path)
        for code, path in readme_languages(readme_dir).items()
        if wanted is None or code.replace("_", "-").lower() in wanted
    ]


def report_readmes(results: list[ReadmeFindings], *, verbose: bool) -> None:
    """One line a translation, and with --verbose the blocks."""
    if not results:
        return
    print("\nREADME_translated, against README.md\n")
    print(f"{'':8}{'blocks':>7}{'missing':>9}{'changed':>9}{'extra':>7}{'english':>9}  note")
    for found in results:
        note = found.disclaimer or ("ok" if found.exists else "the file is missing")
        print(
            f"{found.language:8}{found.blocks:>7}{len(found.missing):>9}{len(found.changed):>9}{len(found.extra):>7}"
            f"{len(found.untranslated):>9}  {note}"
        )
    if not verbose:
        return
    for found in results:
        for label, blocks in (
            ("missing", found.missing),
            ("changed", found.changed),
            ("extra", found.extra),
            ("still English", found.untranslated),
        ):
            for block in blocks:
                print(f"README.{found.language}: {label}: {block!r}")


# ---- Putting a block into another language -----------------------------------------------------------
# What a translator must give back unchanged is swapped for a marker before the text goes out and put back
# after.  A marker that does not come back exactly once means the translator mangled the block, and the English
# stays in the file (to be reported as "still English") rather than a broken translation.
_PROTECTED = re.compile(
    r"`+.+?`+"  # code
    r"|(?<=\]\()<?[^)>\s]+>?(?:\s+\"[^\"]*\")?(?=\))"  # a link's target; the brackets stay
    r"|</?[A-Za-z][^>]*>"  # html
    r"|https?://[^\s)>\"'\]]+"  # a bare URL
    r"|\[\[|\]\]"  # [[double brackets]], which a translator tends to turn into one
)
_MARKER = re.compile(r"XQ(\d+)QX")
BADGES = re.compile(r"(?:\s*!?\[[^\]]*\]\([^)]*\)[\s,]*)+")
BADGE_WORDS = 3
_MARKUP_PREFIX = re.compile(r"^((?:\s*(?:#{1,6}\s+|>\s?|(?:[-*+]|\d+[.)])\s+))*\s*)(.*)$", re.DOTALL)

Translator = Callable[[str, str], "str | None"]


def protect(text: str) -> tuple[str, list[str]]:
    """The text with each thing that must not be translated replaced by a marker, and the list of what they were."""
    kept: list[str] = []

    def hide(match: re.Match[str]) -> str:
        kept.append(match.group(0))
        return f"XQ{len(kept) - 1}QX"

    return _PROTECTED.sub(hide, text), kept


def restore(text: str, kept: list[str]) -> str | None:
    """The markers put back, or None if the translation lost one or grew another."""
    if sorted(int(number) for number in _MARKER.findall(text)) != list(range(len(kept))):
        return None
    return _MARKER.sub(lambda match: kept[int(match.group(1))], text)


def localize(text: str) -> str:
    """The relative links and images of a block of README.md, as they must be written from README_translated/."""

    def move(target: str) -> str:
        if re.match(r"^(?:[a-z][a-z0-9+.-]*:|#|//)", target, re.IGNORECASE):
            return target  # a URL, a mail address or an anchor in the same file
        if target.startswith("README_translated/"):
            return target.removeprefix("README_translated/")
        return "../" + target.removeprefix("./")

    text = LINK_TARGET.sub(lambda m: m.group(0).replace(m.group(1), move(m.group(1)), 1), text)
    return re.sub(
        r"""((?:src|href|srcset)=["'])([^"']+)(["'])""",
        lambda m: f"{m.group(1)}{move(m.group(2))}{m.group(3)}",
        text,
    )


def translate_text(text: str, language: str, translate: Translator) -> str | None:
    """Some prose, in `language`, with its markup, code and links intact; None if that could not be done."""
    matched = _MARKUP_PREFIX.match(text)
    prefix, body = (matched.group(1), matched.group(2)) if matched else ("", text)
    if not words(body) or (BADGES.fullmatch(body.strip()) and len(words(body)) <= BADGE_WORDS):
        return text  # nothing to say, or a row of badges and product names
    hidden, kept = protect(body)
    translated = translate(hidden, language)
    restored = None if translated is None else restore(translated.strip(), kept)
    return None if restored is None else prefix + restored


def translate_block(block: str, language: str, translate: Translator) -> tuple[str, int]:
    """A block of README.md in `language`, ready for README_translated/, and how many of its lines stayed English.

    A paragraph is given whole, since its sentences run on; a list, quote, heading or table goes line by line, so
    one line the translator mangles stays English without taking the others with it.
    """
    kind = block_kind(block)
    if kind in NOT_TRANSLATED:
        return localize(block), 0  # code, markup and rules stay; so do the few words in markup (a caption)
    if kind == "p":
        done = translate_text(block, language, translate)
        return (localize(done), 0) if done is not None else (localize(block), 1)

    lines = []
    failed = 0
    for line in block.split("\n"):
        if kind == "table" and set(line.replace("|", "").strip()) <= set("-: "):
            lines.append(line)  # the row of dashes under a header
            continue
        parts = line.split("|") if kind == "table" else [line]
        done = [translate_text(part, language, translate) if part.strip() else part for part in parts]
        if None in done:
            failed += 1
            lines.append(line)
        else:
            lines.append("|".join(part for part in done if part is not None))
    return localize("\n".join(lines)), failed


DISCLAIMER = (
    "This translation was created automatically. "
    "If anything differs, the [original English README](../README.md) applies."
)


def machine_translator(locale: Path) -> Translator:
    """sync_and_clean_po.py's translator -- the local Ollama model, then Google -- as a function of (text, language)."""
    tool = load_sync_tool(locale)
    translators: dict[str, object] = {}

    def translate(text: str, language: str) -> str | None:
        if language not in translators:
            try:
                translators[language] = tool.GoogleTranslator(source="en", target=language)
            except Exception as error:  # any failure just means the local model alone
                print(f"  [Error] could not create GoogleTranslator for {language}: {error}")
                translators[language] = None
        return tool.translate_preserving_edges(translators[language], language, text)

    return translate


def retranslate_lines(
    block: str, english_lines: set[str], found: ReadmeFindings, translate: Translator
) -> tuple[str, int]:
    """`block` with each line that is still the English put into the language, and how many could not be."""
    out = []
    failed = 0
    for line in block.split("\n"):
        done = translate_text(line, found.language, translate) if line in english_lines else line
        if done is None:
            failed += 1
            print(f"  [Failed] README.{found.language}: {excerpt(line)!r} stays English")
        out.append(localize(line if done is None else done))
    return "\n".join(out), failed


def fix_readme(english: list[str], found: ReadmeFindings, translate: Translator | None) -> int:
    """Bring one translation into step with README.md.  Returns how many blocks could not be translated."""
    body, wrapper = without_rtl_wrapper(split_blocks(found.path.read_text(encoding="utf-8")))
    kept, note = without_disclaimer(body)
    failed = 0

    def made(block: str) -> str:
        """`block` of README.md in this language, or, failing that, as it is with its links moved."""
        nonlocal failed
        if translate is None:
            return localize(block)
        done, lines = translate_block(block, found.language, translate)
        if lines:
            failed += lines
            print(f"  [Failed] README.{found.language}: {lines} line(s) of {excerpt(block)!r} stay English")
        return done

    result: list[str] = []
    fresh: set[int] = set()  # where the blocks just made are: they have had their turn
    cursor = 0
    for op, i1, i2, j1, j2 in found.plan:
        result += kept[cursor:j1]
        # "delete" is a block only the English has (to be added), "insert" one only the translation has (dropped).
        if op != "insert":
            fresh.update(range(len(result), len(result) + i2 - i1))
            result += [made(english[i]) for i in range(i1, i2)]
        cursor = j2
    result += kept[cursor:]

    # What is still English is translated where it stands: a whole paragraph, or the lines left in a list.
    if translate is not None:
        in_english = set(still_english(english, result))
        lines = english_prose_lines(english)
        for index, block in enumerate(result):
            if block not in in_english or index in fresh:
                continue
            if block_kind(block) == "p":
                result[index] = made(block)
            else:
                result[index], lines_failed = retranslate_lines(block, lines, found, translate)
                failed += lines_failed

    # The note goes straight after the title.
    if note is None or "../README.md" not in note:
        note = f"> {(translate(DISCLAIMER, found.language) if translate else None) or DISCLAIMER}"
    title = next((index for index, block in enumerate(result) if block_kind(block) == "h1"), -1)
    result.insert(title + 1, note)
    if wrapper is not None:
        index, opening, closing = wrapper
        result.insert(min(index, len(result)), opening)
        result += [closing] if closing is not None else []

    found.path.write_text("\n\n".join(result) + "\n", encoding="utf-8")
    return failed


def main() -> int:
    """Check the catalogs and the translated READMEs, fix them if asked, and say whether they are right."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--fix", action="store_true", help="make the changes (default: only report)")
    parser.add_argument(
        "--no-translate",
        action="store_true",
        help="with --fix, add missing strings with a blank translation, and missing README blocks in English",
    )
    parser.add_argument("--lang", help="comma-separated language codes to look at (default: all)")
    parser.add_argument("--verbose", action="store_true", help="list every string and block, not only the counts")
    parser.add_argument(
        "--strict", action="store_true", help="count a blank translation or untranslated block as a problem"
    )
    parser.add_argument("--locale", type=Path, default=LOCALE, help="the catalogs to look at (default: the project's)")
    parser.add_argument("--readme-dir", type=Path, default=ROOT, help="where README.md and README_translated/ are")
    only = parser.add_mutually_exclusive_group()
    only.add_argument("--catalogs-only", action="store_true", help="leave the READMEs alone")
    only.add_argument("--readme-only", action="store_true", help="leave the catalogs alone")
    options = parser.parse_args()

    languages = set(options.lang.split(",")) if options.lang else None
    status = 0
    if not options.readme_only:
        status = max(status, check_catalogs(options, languages))
    if not options.catalogs_only:
        status = max(status, check_readmes(options, languages))
    return status


def check_catalogs(options: argparse.Namespace, languages: set[str] | None) -> int:
    """The catalogs half of main(): 0 if they are right, 1 if not, 2 if there are none."""
    catalogs = read_catalogs(options.locale, None)
    if not catalogs or (languages and not languages & {catalog.language for catalog in catalogs}):
        print(f"No catalogs found under {options.locale}", file=sys.stderr)
        return 2

    required = source_strings(SOURCE) | help_strings(ROOT)
    results = look(options.locale, required, languages)
    report(results, required, verbose=options.verbose)

    if options.fix:
        if any(found.to_add or found.catalog.duplicates or found.dead_context for found in results):
            print("\nFixing...")
            failed = fix(results, required, options.locale, translate=not options.no_translate)
            if failed:
                print(f"\n{failed} string(s) could not be translated; run again to retry them.")
        # Recompile whatever changed or was stale, then look again at what is left.
        for found in look(options.locale, required, languages):
            if found.stale_mo:
                write_mo(found.catalog)
        results = look(options.locale, required, languages)
        print("\nAfter the fixes:\n")
        report(results, required, verbose=options.verbose)

    problems = sum(found.problems(strict=options.strict) for found in results)
    pending = sum(len(found.blank) for found in results)
    print(f"\n{problems} problem(s)." + (f"  {pending} blank translation(s) waiting." if pending else ""))
    if problems and not options.fix:
        print("Run again with --fix to put them right (add --no-translate to skip the translating).")
    return 1 if problems else 0


def check_readmes(options: argparse.Namespace, languages: set[str] | None) -> int:
    """The README half of main(): 0 if every translation follows README.md, 1 if not."""
    results = look_at_readmes(options.readme_dir, languages)
    if not results:
        print(f"\nNo README.md and README_translated/ under {options.readme_dir}")
        return 0
    report_readmes(results, verbose=options.verbose)

    if options.fix:
        todo = [found for found in results if found.exists and (found.plan or found.disclaimer or found.untranslated)]
        if todo:
            print("\nFixing the READMEs...")
            english = split_blocks((options.readme_dir / "README.md").read_text(encoding="utf-8"))
            translate = None if options.no_translate else machine_translator(options.locale)
            failed = sum(fix_readme(english, found, translate) for found in todo)
            if failed:
                print(f"\n{failed} README block(s) could not be translated and are in English; run again to retry.")
        results = look_at_readmes(options.readme_dir, languages)
        print("\nAfter the fixes:")
        report_readmes(results, verbose=options.verbose)

    problems = sum(found.problems(strict=options.strict) for found in results)
    waiting = sum(len(found.untranslated) for found in results)
    print(f"\n{problems} README problem(s)." + (f"  {waiting} block(s) still in English." if waiting else ""))
    if problems and not options.fix:
        print("Run again with --fix to put them right (add --no-translate to skip the translating).")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
