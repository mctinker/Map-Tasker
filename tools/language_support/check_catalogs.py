#! /usr/bin/env python3
"""Check that every translation catalog holds what the program asks for, and bring them up to date.

Run it now and then -- after adding a translate_string() call, rewording a help screen, or just before a
release.  With no options it only looks, changes nothing, and exits 1 if anything needs doing:

    python tools/language_support/check_catalogs.py

and with --fix it does what needs doing:

    python tools/language_support/check_catalogs.py --fix                   translate and add what is missing
    python tools/language_support/check_catalogs.py --fix --no-translate    add it with a blank translation
    python tools/language_support/check_catalogs.py --lang de,fr --verbose  just those two, listing every string

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


_sync_tool: ModuleType | None = None


def load_sync_tool(locale: Path) -> ModuleType:
    """sync_and_clean_po.py, pointed at this tree.  It needs the "ai" extra and deep-translator, so only --fix loads it."""
    global _sync_tool  # noqa: PLW0603  (loaded once, on first use)
    if _sync_tool is None:
        path = Path(__file__).with_name("sync_and_clean_po.py")
        spec = importlib.util.spec_from_file_location("sync_and_clean_po", path)
        if spec is None or spec.loader is None:
            message = f"cannot load {path}"
            raise ImportError(message)
        _sync_tool = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(ROOT))
        spec.loader.exec_module(_sync_tool)
    vars(_sync_tool).update(SRC_PATH=SOURCE, LOCALE_PATH=locale)  # the stages read these as globals
    return _sync_tool


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


def main() -> int:
    """Check the catalogs, fix them if asked, and say whether they are right."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--fix", action="store_true", help="make the changes (default: only report)")
    parser.add_argument(
        "--no-translate", action="store_true", help="with --fix, add missing strings with a blank translation"
    )
    parser.add_argument("--lang", help="comma-separated language codes to look at (default: all)")
    parser.add_argument("--verbose", action="store_true", help="list every string, not only the counts")
    parser.add_argument("--strict", action="store_true", help="count a blank translation as a problem")
    parser.add_argument("--locale", type=Path, default=LOCALE, help="the catalogs to look at (default: the project's)")
    options = parser.parse_args()

    languages = set(options.lang.split(",")) if options.lang else None
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


if __name__ == "__main__":
    sys.exit(main())
