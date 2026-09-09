#! /usr/bin/env python3
"""
Make every msgstr agree with its msgid about leading/trailing newlines.

msgfmt reports a mismatch as a fatal error ("'msgid' and 'msgstr' entries do not both end
with '\\n'") and exits 1.  It does still write the .mo, that entry included, so this is
not data loss -- but it fails the build and, more usefully, means the translated string
lost the trailing blank line the English one uses to space a tooltip out.  Machine
translation is the usual source: Google drops those blank lines.

Only the leading and trailing newline runs of the msgstr are touched -- the translated
text itself is left exactly as it was.  Safe to re-run; it reports what it changed.
"""

import re
import sys
from pathlib import Path

LOCALE_PATH = Path("/Users/mikrubin/MapTasker_Dev/maptasker/locale")

# One "msgid "..."\nmsgstr "..."" pair, allowing the multi-line continuation form.
ENTRY_RE = re.compile(
    r'(?P<id_kw>^msgid\s+)(?P<id>"(?:[^"\\]|\\.)*"(?:\s*\n\s*"(?:[^"\\]|\\.)*")*)'
    r'(?P<gap>\s*\n)(?P<str_kw>msgstr\s+)(?P<str>"(?:[^"\\]|\\.)*"(?:\s*\n\s*"(?:[^"\\]|\\.)*")*)',
    re.MULTILINE,
)


def decode(po_literal: str) -> str:
    """Concatenate a (possibly multi-line) .po string literal into its actual value."""
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', po_literal)
    joined = "".join(parts)
    return (
        joined.replace("\\n", "\n")
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


def edges(text: str) -> tuple[str, str]:
    """The leading and trailing runs of newlines in a string."""
    leading = text[: len(text) - len(text.lstrip("\n"))]
    trailing = text[len(text.rstrip("\n")) :]
    return leading, trailing


def fix_file(po_file: Path) -> int:
    """Repair every mismatched entry in one catalog.  Returns the number fixed."""
    source = po_file.read_text(encoding="utf-8")
    fixed = 0

    def repair(match: re.Match) -> str:
        nonlocal fixed
        msgid = decode(match.group("id"))
        msgstr = decode(match.group("str"))

        # The header entry (empty msgid) is a different animal -- leave it alone.
        if not msgid or not msgstr:
            return match.group(0)

        want_lead, want_trail = edges(msgid)
        have_lead, have_trail = edges(msgstr)
        if want_lead == have_lead and want_trail == have_trail:
            return match.group(0)

        rebuilt = want_lead + msgstr.strip("\n") + want_trail
        fixed += 1
        return f"{match.group('id_kw')}{match.group('id')}{match.group('gap')}{match.group('str_kw')}{encode(rebuilt)}"

    repaired = ENTRY_RE.sub(repair, source)
    if fixed:
        po_file.write_text(repaired, encoding="utf-8")
    return fixed


def main() -> int:
    """Repair every catalog under LOCALE_PATH."""
    total = 0
    for po_file in sorted(LOCALE_PATH.glob("*/LC_MESSAGES/messages.po")):
        count = fix_file(po_file)
        if count:
            print(f"{po_file.parent.parent.name}: fixed {count}")
        total += count
    print(f"\nTotal entries repaired: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
