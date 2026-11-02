"""Ratchet the translation drift so it can only go down.

tools/language_support/check_catalogs.py reports what is out of step in the translation catalogs
(maptasker/locale/*/LC_MESSAGES/messages.po, and the messages.mo the program loads) and in the translated
READMEs (README_translated/README.<code>.md against README.md).  Fixing it means machine-translating, which
needs a network and the "ai" extra, so CI cannot just demand a clean result.  It holds the drift where it
stands instead, in translation_baseline.json beside this script:

  * A finding that is not in the baseline fails: a string the program asks to have translated that a catalog
    lacks (or holds blank), a placeholder a translation lost, a .mo that is not what the .po says, a README
    block with no counterpart in a translation.  Run ``check_catalogs.py --fix``, and commit what it writes.
  * A finding that is in the baseline but is gone also fails, until the baseline is lowered to match.
    Otherwise the cleanup would leave room for the same amount of new drift.  ``--update`` lowers it.

The baseline is keyed by what was found and the languages it was found in -- never by a count -- so
translating one string and leaving another untranslated does not cancel out.

    uv run python scripts/translation_ratchet.py            check (what CI runs)
    uv run python scripts/translation_ratchet.py --update   lower the baseline after a cleanup
    uv run python tools/language_support/check_catalogs.py  the full report, and --fix

``--update`` never adds a finding.  If drift really is to be accepted, ``--accept`` writes everything found now
as the baseline, and the diff shows the reviewer exactly what was accepted.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
BASELINE = Path(__file__).with_name("translation_baseline.json")
TOOL = ROOT / "tools" / "language_support" / "check_catalogs.py"
UPDATE_HINT = "uv run python scripts/translation_ratchet.py --update"
FIX_HINT = "uv run python tools/language_support/check_catalogs.py --fix"

# {kind: {what was found: the languages it was found in}}
Findings = dict[str, dict[str, set[str]]]

CATALOGS = "catalogs"
READMES = "READMEs"


def load_tool() -> ModuleType:
    """Import check_catalogs.py, which is a command-line tool and so lives outside any package."""
    spec = importlib.util.spec_from_file_location("check_catalogs", TOOL)
    if spec is None or spec.loader is None:
        message = f"cannot load {TOOL}"
        raise ImportError(message)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _add(found: Findings, kind: str, what: str, language: str) -> None:
    found.setdefault(kind, {}).setdefault(what, set()).add(language)


class _Catalog(Protocol):
    language: str
    duplicates: list[str]
    unreadable: int


class _CatalogResult(Protocol):
    """What check_catalogs.Findings holds of one catalog, as far as this reads it."""

    catalog: _Catalog
    missing_required: list[str]
    missing_shared: list[str]
    blank: list[str]
    placeholders: list[str]
    dead_context: list[str]
    stale_mo: str


class _ReadmeResult(Protocol):
    """What check_catalogs.ReadmeFindings holds of one translated README, as far as this reads it."""

    language: str
    exists: bool
    missing: list[str]
    changed: list[str]
    extra: list[str]
    untranslated: list[str]
    disclaimer: str


def _catalog_findings(found: Findings, result: _CatalogResult) -> None:
    """Add what is wrong with one catalog (a check_catalogs.Findings)."""
    language = result.catalog.language
    for kind, msgids in (
        ("missing", result.missing_required),
        ("missing (shared)", result.missing_shared),
        ("blank", result.blank),
        ("defined twice", result.catalog.duplicates),
        ("msgctxt entry", result.dead_context),
        ("placeholders changed", result.placeholders),
    ):
        for msgid in msgids:
            _add(found, f"{CATALOGS}: {kind}", msgid, language)
    if result.catalog.unreadable:
        _add(found, f"{CATALOGS}: malformed entry", "an entry the pattern could not read", language)
    if result.stale_mo:
        # Without the count of entries that differ: fixing one of them should not read as a new finding.
        _add(found, f"{CATALOGS}: messages.mo", result.stale_mo.split(" (")[0], language)


def _readme_findings(found: Findings, readme: _ReadmeResult) -> None:
    """Add what is out of step in one translated README (a check_catalogs.ReadmeFindings)."""
    language = readme.language
    if not readme.exists:
        _add(found, f"{READMES}: file", "the translation is missing", language)
        return
    for kind, blocks in (
        ("missing", readme.missing),
        ("changed", readme.changed),
        ("extra", readme.extra),
        ("still English", readme.untranslated),
        ("note", [readme.disclaimer] if readme.disclaimer else []),
    ):
        for block in blocks:
            _add(found, f"{READMES}: {kind}", block, language)


def find_drift(tool: ModuleType | None = None, root: Path | None = None) -> Findings:
    """Return everything check_catalogs.py finds wrong, as {kind: {what: languages}}."""
    tool = tool or load_tool()
    root = root or ROOT
    found: Findings = {}

    source = root / "maptasker" / "src"
    required = tool.source_strings(source) | tool.help_strings(root)
    catalogs = tool.read_catalogs(root / "maptasker" / "locale", None)
    for result in tool.check(catalogs, required, context_used=tool.uses_context(source)):
        _catalog_findings(found, result)
    for readme in tool.look_at_readmes(root, None):
        _readme_findings(found, readme)
    return found


def load_baseline(path: Path = BASELINE) -> Findings:
    """Return the committed allowance."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        kind: {what: set(languages.split()) for what, languages in entries.items()} for kind, entries in raw.items()
    }


def save_baseline(allowed: Findings, path: Path = BASELINE) -> None:
    """Write the allowance sorted, one line a finding: its languages are a single space-separated string."""
    ordered = {
        kind: {what: " ".join(sorted(allowed[kind][what])) for what in sorted(allowed[kind])}
        for kind in sorted(allowed)
        if allowed[kind]
    }
    path.write_text(json.dumps(ordered, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def compare(
    found: Findings, allowed: Findings
) -> tuple[list[tuple[str, str, set[str]]], list[tuple[str, str, set[str]]]]:
    """Return (new, gone): findings above the allowance, and allowance above the findings, each with its languages."""
    new: list[tuple[str, str, set[str]]] = []
    gone: list[tuple[str, str, set[str]]] = []
    for kind in sorted(found.keys() | allowed.keys()):
        here, expected = found.get(kind, {}), allowed.get(kind, {})
        for what in sorted(here.keys() | expected.keys()):
            if extra := here.get(what, set()) - expected.get(what, set()):
                new.append((kind, what, extra))
            if missing := expected.get(what, set()) - here.get(what, set()):
                gone.append((kind, what, missing))
    return new, gone


def lowered(found: Findings, allowed: Findings) -> Findings:
    """The allowance with everything that is gone taken out; nothing is ever added."""
    result: Findings = {}
    for kind, entries in allowed.items():
        for what, languages in entries.items():
            if still := languages & found.get(kind, {}).get(what, set()):
                result.setdefault(kind, {})[what] = still
    return result


def _describe(kind: str, what: str, languages: set[str]) -> str:
    shown = " ".join(sorted(languages))
    return f"{kind}: {what[:90]!r}  [{shown}]"


def main() -> int:
    """Compare the drift found now with the baseline; return the exit status."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--update", action="store_true", help="lower the baseline to the drift found now")
    action.add_argument("--accept", action="store_true", help="write everything found now as the baseline")
    options = parser.parse_args()

    found = find_drift()
    total = sum(len(languages) for entries in found.values() for languages in entries.values())

    if options.accept:
        save_baseline(found)
        print(f"{BASELINE.name}: {total} findings accepted.")
        return 0

    allowed = load_baseline()
    new, gone = compare(found, allowed)
    allowance = sum(len(languages) for entries in allowed.values() for languages in entries.values())

    for kind, what, languages in new:
        print(_describe(kind, what, languages))
    if new:
        print(
            f"\n{sum(len(languages) for _, _, languages in new)} new translation finding(s). Put them right with:"
            f"\n  {FIX_HINT}\nand commit what it writes.  (Add --no-translate to skip the machine translation.)",
        )
        return 1

    if options.update:
        if gone:
            save_baseline(lowered(found, allowed))
        print(f"{BASELINE.name}: {total} findings ({allowance - total} fewer).")
        return 0

    for kind, what, languages in gone:
        print(f"gone: {_describe(kind, what, languages)}")
    if gone:
        print(f"\nLess drift than the baseline allows -- lock that in with:\n  {UPDATE_HINT}")
        return 1

    print(f"translation ratchet: {total} known findings, none new.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
