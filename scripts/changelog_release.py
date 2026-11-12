"""The Changelog's part in a release: stamp its heading, check it, and write the release notes from it.

Changelog.md keeps the section for the version being worked on at the top, headed

    ## [16.0.0] ??-Nov-2026  # FIX

with the date left as ``??-Nov-2026`` until the release.  Three things are done with that section, and each is a
subcommand so a person and the release workflow use the same code:

    python scripts/changelog_release.py stamp               put the version and today's date in the heading
    python scripts/changelog_release.py check               say whether the heading is ready to release
    python scripts/changelog_release.py notes               print the GitHub Release text

  * stamp rewrites the top heading to "## [<version in pyproject.toml>] <today as DD-Mmm-YYYY>" and keeps whatever
    follows the date (the "# FIX" marker).  It touches nothing else.  Run it, commit, push, and tag.
  * check is what the release workflow asks before it publishes anything: the heading names the version being
    released, and its date is a real one.  A heading still carrying "??" is a release that was not prepared.
  * notes writes the GitHub Release text: each change in the section as ONE brief sentence -- its first -- under the
    category it was filed in.  The Changelog's own bullets run to two sentences and say more than a release page needs;
    the Changelog stays the full record, and the release links to it.  Known Issues are not changes and are left out.

A sentence is cut, at a word, when it runs past SENTENCE_LIMIT characters, since "brief" is the point of the page.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "Changelog.md"
PYPROJECT = ROOT / "pyproject.toml"

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
CATEGORIES = ("Added", "Changed", "Removed", "Fixed")
SENTENCE_LIMIT = 160

# "## [16.0.0] 12-Nov-2026  # FIX" -- the version, the date as written, and whatever follows it.
HEADING = re.compile(r"^## \[(?P<version>[^\]]+)\] (?P<date>\S+)(?P<rest>.*)$")
DATE = re.compile(r"^(?P<day>\d{2})-(?P<month>[A-Z][a-z]{2})-(?P<year>\d{4})$")
BULLET = re.compile(r"^- (?P<category>[A-Za-z ]+?):(?P<text>.*)$")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z_`'\"(\[])")


@dataclass(frozen=True)
class Heading:
    """The Changelog's top heading, in its parts."""

    version: str
    written_date: str
    rest: str  # what follows the date, spaces included: "  # FIX"


def format_date(day: date) -> str:
    """12 November 2026 as the Changelog writes it: 12-Nov-2026 (the month in English, whatever the locale)."""
    return f"{day.day:02d}-{MONTHS[day.month - 1]}-{day.year}"


def parse_date(text: str) -> date | None:
    """The date a heading writes, or None when it is not one (a "??-Nov-2026", a month that does not exist ...)."""
    found = DATE.match(text)
    if found is None or found["month"] not in MONTHS:
        return None
    try:
        return date(int(found["year"]), MONTHS.index(found["month"]) + 1, int(found["day"]))
    except ValueError:
        return None


def top_heading_index(lines: list[str]) -> int:
    """The line number of the newest version's heading, the first "## [" in the file."""
    for number, line in enumerate(lines):
        if HEADING.match(line):
            return number
    message = "Changelog.md has no '## [version] date' heading."
    raise ValueError(message)


def parse_heading(line: str) -> Heading:
    """The parts of a version heading."""
    found = HEADING.match(line)
    if found is None:
        message = f"not a version heading: {line!r}"
        raise ValueError(message)
    return Heading(found["version"], found["date"], found["rest"])


def stamp(text: str, version: str, today: date) -> str:
    """The Changelog with its top heading naming `version` and `today`, and nothing else changed."""
    lines = text.split("\n")
    index = top_heading_index(lines)
    heading = parse_heading(lines[index])
    lines[index] = f"## [{version}] {format_date(today)}{heading.rest}"
    return "\n".join(lines)


def problems(text: str, version: str) -> list[str]:
    """What is wrong with the top heading for a release of `version`; [] when it is ready."""
    try:
        heading = parse_heading(text.split("\n")[top_heading_index(text.split("\n"))])
    except ValueError as error:
        return [str(error)]
    found: list[str] = []
    if heading.version != version:
        found.append(f"The Changelog's newest section is [{heading.version}], not [{version}].")
    if parse_date(heading.written_date) is None:
        found.append(
            f"The Changelog's heading for [{heading.version}] has no release date ({heading.written_date!r}). "
            "Run 'python scripts/changelog_release.py stamp', commit it, push it, and tag that commit."
        )
    return found


def top_section(text: str) -> list[str]:
    """The lines of the newest version's section, after its heading and up to the next version's."""
    lines = text.split("\n")
    start = top_heading_index(lines) + 1
    end = next((number for number in range(start, len(lines)) if HEADING.match(lines[number])), len(lines))
    return lines[start:end]


def bullets(section: list[str]) -> list[tuple[str, str]]:
    """(category, text) for every change in a section, a bullet's continuation lines joined to it.

    The empty "- Changed:" placeholder each category keeps is not a change.  Known Issues use another kind of bullet
    altogether ("* ") and never match.
    """
    found: list[tuple[str, str]] = []
    for line in section:
        match = BULLET.match(line)
        if match:
            found.append((match["category"].strip(), match["text"].strip()))
        elif found and line.startswith("  ") and line.strip():
            category, text = found[-1]
            found[-1] = (category, f"{text} {line.strip()}")
    return [(category, text) for category, text in found if text]


def plain(text: str) -> str:
    """The text without the Changelog's markdown: __bold__ and `code` marks, and links reduced to their words."""
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    return re.sub(r"\*\*([^*]+)\*\*", r"\1", text)


# Where a long sentence is best cut: a dash, a semicolon or a comma, so what is left still reads as a sentence.
CLAUSE_BREAK = re.compile(r"\s+--\s+|;\s+|,\s+")
MIN_CLAUSE = 50


def one_sentence(text: str) -> str:
    """The first sentence of a change, brought under SENTENCE_LIMIT when it runs longer.

    A long one is cut at its last clause break that fits (a dash, semicolon or comma) that leaves at least MIN_CLAUSE
    characters and no bracket open, and ends there; with no such break it is cut at a word and marked with "...".
    """
    sentence = SENTENCE_END.split(plain(text).strip(), maxsplit=1)[0].strip()
    if len(sentence) > SENTENCE_LIMIT:
        # The last break that still fits and leaves no bracket open: as much of the change as a brief sentence holds.
        for found in reversed(list(CLAUSE_BREAK.finditer(sentence[:SENTENCE_LIMIT]))):
            kept = sentence[: found.start()]
            if len(kept) >= MIN_CLAUSE and kept.count("(") == kept.count(")"):
                return f"{kept.rstrip(' ,;:-')}."
        return f"{sentence[: SENTENCE_LIMIT - 3].rsplit(' ', 1)[0].rstrip(' ,;:-')}..."
    return sentence if sentence.endswith((".", "!", "?")) else f"{sentence}."


def release_notes(text: str, version: str, changelog_url: str = "Changelog.md") -> str:
    """The GitHub Release text for the newest section: one brief sentence per change, grouped by category.

    `changelog_url` is where the full record is linked from the page; a release page needs an absolute one.
    """
    heading = parse_heading(text.split("\n")[top_heading_index(text.split("\n"))])
    changes = bullets(top_section(text))
    parts = [f"## MapTasker {version}", ""]
    if (released := parse_date(heading.written_date)) is not None:
        parts = [f"## MapTasker {version} ({format_date(released)})", ""]
    for category in CATEGORIES:
        sentences = [one_sentence(body) for kind, body in changes if kind == category]
        if sentences:
            parts += [f"### {category}", "", *(f"- {sentence}" for sentence in sentences), ""]
    parts.append(f"Every change in full is in the [Changelog]({changelog_url}).")
    return "\n".join(parts) + "\n"


def pyproject_version() -> str:
    """The version pyproject.toml declares."""
    return str(tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["version"])


def main(argv: list[str] | None = None) -> int:
    """Run one subcommand; 1 when `check` finds the heading not ready."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("command", choices=("stamp", "check", "notes"))
    parser.add_argument("--version", help="the version being released (default: pyproject.toml's)")
    parser.add_argument("--date", help="stamp with this date, YYYY-MM-DD (default: today)")
    parser.add_argument("--changelog", type=Path, default=CHANGELOG)
    parser.add_argument(
        "--changelog-url", default="Changelog.md", help="where the release text links the full Changelog"
    )
    options = parser.parse_args(argv)

    version = options.version or pyproject_version()
    text = options.changelog.read_text(encoding="utf-8")

    if options.command == "stamp":
        day = date.fromisoformat(options.date) if options.date else datetime.now().astimezone().date()
        options.changelog.write_text(stamp(text, version, day), encoding="utf-8")
        print(f"Changelog heading is now [{version}] {format_date(day)}.")
        return 0
    if options.command == "check":
        found = problems(text, version)
        for problem in found:
            print(f"changelog: {problem}")
        if not found:
            print(f"changelog: the heading for [{version}] is dated and ready.")
        return 1 if found else 0
    sys.stdout.write(release_notes(text, version, options.changelog_url))
    return 0


if __name__ == "__main__":
    sys.exit(main())
