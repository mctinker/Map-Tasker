#! /usr/bin/env python3
"""
Restore URLs that machine translation altered inside translated strings.

A URL is not language.  Google mostly leaves them alone, but not reliably -- observed in
MapTasker's own catalogs:

  * a letter dropped     https://taskernet.com/?public&tags=maptasker  ->  ...tags=matasker
  * case changed         https://t.ly/8vI1f                           ->  https://t.ly/8vi1f
  * a particle fused on  ...Changelog.md                              ->  ...Changelog.md에서

The first two produce a link that simply does not work, and neither is visible without
comparing against the English -- the help screen looks perfectly translated.

Repair rule, applied per entry, matching the Nth URL of the msgstr to the Nth URL of the
msgid (only when the two agree on how many there are, so nothing is guessed):

  * identical                  -> left alone
  * translated URL starts with
    the English one            -> the English URL, then the extra text, separated by a
                                  space so the link ends where it should.  Trailing ASCII
                                  punctuation is dropped instead, since the English had
                                  none there.
  * anything else              -> replaced with the English URL outright (corruption)

Usage:  fix_urls_in_po.py [--apply]      (defaults to a dry run)
"""

import re
import sys
from pathlib import Path

LOCALE_PATH = Path("/Users/mikrubin/MapTasker_Dev/maptasker/locale")

# Stop at whitespace and at quotes, so a URL embedded in a quoted JSON example does not
# swallow the closing quote.
URL_RE = re.compile(r"https?://[^\s'\"]+")

ENTRY_RE = re.compile(
    r'(?P<head>^msgid\s+)(?P<id>"(?:[^"\\]|\\.)*"(?:\s*\n\s*"(?:[^"\\]|\\.)*")*)'
    r'(?P<mid>\s*\nmsgstr\s+)(?P<str>"(?:[^"\\]|\\.)*"(?:\s*\n\s*"(?:[^"\\]|\\.)*")*)',
    re.MULTILINE,
)


def decode(po_literal: str) -> str:
    """Concatenate a (possibly multi-line) .po string literal into its actual value."""
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', po_literal)
    return (
        "".join(parts)
        .replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace("\\r", "\r")
        .replace('\\"', '"')
        .replace("\\\\", "\\")
    )


def encode(text: str) -> str:
    """Render a value back as a single-line .po string literal."""
    escaped = (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
        .replace("\r", "\\r")
    )
    return f'"{escaped}"'


def repair_urls(msgid: str, msgstr: str) -> tuple[str, list[tuple[str, str]]]:
    """Return the msgstr with its URLs restored, plus a list of (before, after) changes."""
    expected = URL_RE.findall(msgid)
    found = URL_RE.findall(msgstr)
    if not expected or len(expected) != len(found):
        # Nothing to do, or the counts disagree -- in which case positional matching would
        # be a guess, so leave it for a human rather than corrupt it further.
        return msgstr, []

    changes = []
    result = msgstr
    for english, translated in zip(expected, found):
        if translated == english:
            continue
        if translated.startswith(english):
            extra = translated[len(english) :]
            # Punctuation the English did not have is noise; anything else is words, and
            # keeping them (spaced off the URL) preserves the sentence.
            replacement = english if extra.strip(".,;:!?)") == "" else f"{english} {extra}"
        else:
            replacement = english
        result = result.replace(translated, replacement, 1)
        changes.append((translated, replacement))
    return result, changes


def fix_file(po_file: Path, apply: bool) -> list[tuple[str, str]]:
    """Repair one catalog.  Returns every (before, after) change made or proposed."""
    source = po_file.read_text(encoding="utf-8")
    all_changes = []

    def repair(match: re.Match) -> str:
        msgid = decode(match.group("id"))
        msgstr = decode(match.group("str"))
        if not msgid or not msgstr:
            return match.group(0)

        fixed, changes = repair_urls(msgid, msgstr)
        if not changes:
            return match.group(0)

        all_changes.extend(changes)
        return f"{match.group('head')}{match.group('id')}{match.group('mid')}{encode(fixed)}"

    repaired = ENTRY_RE.sub(repair, source)
    if all_changes and apply:
        po_file.write_text(repaired, encoding="utf-8")
    return all_changes


def main() -> int:
    """Audit every catalog, repairing only when --apply is given."""
    apply = "--apply" in sys.argv
    print("Mode:", "APPLY" if apply else "dry run (pass --apply to write)", "\n")

    total = 0
    for po_file in sorted(LOCALE_PATH.glob("*/LC_MESSAGES/messages.po")):
        changes = fix_file(po_file, apply)
        if changes:
            print(f"{po_file.parent.parent.name}:")
            for before, after in changes:
                print(f"    {before}")
                print(f" -> {after}")
            total += len(changes)

    print(f"\nURLs {'repaired' if apply else 'needing repair'}: {total}")
    if total and not apply:
        print("Re-run with --apply, then po_to_mo.sh.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
