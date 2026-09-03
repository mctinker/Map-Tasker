#! /usr/bin/env python3
"""
Remove catalog entries for help texts whose English wording has since been edited.

The help screens in userhelp.py are translated as one big msgid each.  Change a single
sentence of the English and the msgid no longer matches what the code looks up, so that
help screen silently falls back to English -- while the old entry stays in the catalog,
unreachable, still describing the previous behaviour.  VIEWLIMIT_HELP_TEXT, for instance,
kept telling users "no output map will be generated" long after the code changed to stop
the output where the limit is hit.

This finds those orphans by similarity -- a stale help text is a near-copy of a current
one -- and deletes them, so sync_missing_msgids.py can add a correctly-worded replacement.

Only near-copies of the current userhelp constants are ever touched.  A catalog holds many
msgids this project does not produce from userhelp, and none of them resemble a multi-line
help screen closely enough to be considered.  Nothing is deleted without being reported.

Usage:  prune_stale_help_msgids.py [--apply]     (defaults to a dry run)
"""

import difflib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Language_Support_Utilities.sync_missing_msgids import help_text_strings

LOCALE_PATH = Path("/Users/mikrubin/MapTasker_Dev/maptasker/locale")

# How alike a catalog msgid must be to a current help text before it counts as that help
# text's stale predecessor.  0.55 comfortably clears the most heavily rewritten one seen
# (VIEW_HELP_TEXT, 57%) while staying far above any unrelated string's resemblance.
SIMILARITY_FLOOR = 0.55

# A help text is long and multi-line; nothing short can be a stale copy of one.
MIN_LENGTH = 300

ENTRY_RE = re.compile(
    r'^msgid\s+(?P<id>"(?:[^"\\]|\\.)*"(?:\s*\n\s*"(?:[^"\\]|\\.)*")*)'
    r'\s*\nmsgstr\s+(?P<str>"(?:[^"\\]|\\.)*"(?:\s*\n\s*"(?:[^"\\]|\\.)*")*)\s*?$',
    re.MULTILINE,
)


def decode(po_literal: str) -> str:
    """Concatenate a (possibly multi-line) .po string literal into its actual value."""
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', po_literal)
    return (
        ""
        .join(parts)
        .replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace("\\r", "\r")
        .replace('\\"', '"')
        .replace("\\\\", "\\")
    )


def prune(po_file: Path, current: set[str], apply: bool) -> list[tuple[str, float]]:
    """Drop stale help entries from one catalog.  Returns (excerpt, similarity) removed."""
    source = po_file.read_text(encoding="utf-8")
    removed = []

    def drop(match: re.Match) -> str:
        msgid = decode(match.group("id"))
        if len(msgid) < MIN_LENGTH or msgid in current:
            return match.group(0)

        best = max(
            (difflib.SequenceMatcher(None, msgid, text).ratio() for text in current),
            default=0.0,
        )
        if best < SIMILARITY_FLOOR:
            return match.group(0)

        removed.append((msgid[:70].replace("\n", " "), best))
        return ""  # Drop the whole entry; sync_missing_msgids will re-add a current one.

    pruned = ENTRY_RE.sub(drop, source)
    if removed and apply:
        # Collapse the blank-line run the deletion leaves behind.
        po_file.write_text(re.sub(r"\n{3,}", "\n\n", pruned), encoding="utf-8")
    return removed


def main() -> int:
    """Prune every catalog, dry-run unless --apply is given."""
    # apply = "--apply" in sys.argv
    apply = True  # TODO: remove this line once the script is ready to be run for real
    current = help_text_strings()
    print(f"Current help texts: {len(current)}")
    print("Mode:", "APPLY" if apply else "dry run (pass --apply to write)", "\n")

    total = 0
    for po_file in sorted(LOCALE_PATH.glob("*/LC_MESSAGES/messages.po")):
        removed = prune(po_file, current, apply)
        if removed:
            print(f"{po_file.parent.parent.name}: {len(removed)} stale")
            for excerpt, ratio in removed:
                print(f"    {ratio:.0%}  {excerpt!r}")
            total += len(removed)

    print(f"\nTotal stale entries {'removed' if apply else 'found'}: {total}")
    if not apply:
        print("Re-run with --apply to remove them, then run sync_missing_msgids.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
