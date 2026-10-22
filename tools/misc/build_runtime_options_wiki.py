#! /usr/bin/env python3

#                                                                                      #
# build_runtime_options_wiki: build the "Runtime Options" wiki page                     #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
"""Generate (and optionally publish) the MapTasker Runtime Options wiki page.

The runtime options are the command-line arguments MapTasker takes.  There are two sets:
the ones that choose what the output looks like and where the backup comes from
(maptasker/src/core/parsearg.py, built from the table in cli_arguments.json), and the
ones that run a report with no window (maptasker/src/clireports.py).  A hand-written
list of them is wrong the day an option is added, so this asks the two parsers
themselves -- the same ones '-h' prints -- and writes the page from what they say.
Nothing is parsed, no file is read and no GUI is started.

Unlike the other two wiki generators this one imports the program rather than reading its
source, because the parsers are built by code (a table, and the color options made from
a list).  It therefore needs the project's own Python -- which 'publish-wikis.sh' uses
whenever there is a virtual environment.

The page carries the version and no date, so a run that changes nothing leaves the page
as it was and is not pushed again.

It lives in 'tools/misc' and finds the source, and writes the page, wherever it is
run from::

    python tools/misc/build_runtime_options_wiki.py            # write Runtime-Options.md
    python tools/misc/build_runtime_options_wiki.py --check    # don't write; fail if stale
    python tools/misc/build_runtime_options_wiki.py --print    # write nothing, show the page
    python tools/misc/build_runtime_options_wiki.py --publish  # ... and push it to the wiki

Publishing replaces <wiki>/Runtime-Options and nothing else, using whatever credentials git
already has for the Map-Tasker repository -- see 'wikipub.py'.  Use '--publish --dry-run'
to see exactly what would be pushed first.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Publishing lives in its own module, shared with the other generators.  All sit in this directory.
from wikipub import add_publish_arguments, publish

# ##################################################################################
# Configuration
# ##################################################################################
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.parent
OUTPUT_PAGE = HERE / "Runtime-Options.md"
DEFAULT_PAGE_NAME = "Runtime-Options"

# A list of choices longer than this is written under the description rather than beside the option.
INLINE_CHOICES_LIMIT = 6

# What -h prints for an option nobody has described.
SUPPRESSED = argparse.SUPPRESS


# ##################################################################################
# Reading the parsers
# ##################################################################################
class Option:
    """One option, as the page needs it."""

    def __init__(self, action: argparse.Action, group: str, exclusive_with: list[str]) -> None:
        self.names = [name for name in action.option_strings]
        self.group = group
        self.exclusive_with = exclusive_with
        self.description = (action.help or "").strip()
        self.value = self._value(action)
        self.choices = list(action.choices) if action.choices is not None else []
        self.default = self._default(action)

    @staticmethod
    def _value(action: argparse.Action) -> str:
        """The value the option takes, as the usage line writes it: '' for a flag."""
        if action.nargs == 0:
            return ""
        if isinstance(action.metavar, tuple):
            return " ".join(action.metavar)
        if action.metavar:
            return str(action.metavar)
        if action.choices is not None:
            return "{" + ",".join(str(choice) for choice in action.choices) + "}"
        return action.dest.upper()

    @staticmethod
    def _default(action: argparse.Action) -> str:
        """What the option is when it is not given, or '' when that says nothing."""
        default = action.default
        if default is None or default is False or default in {SUPPRESSED, ""}:
            return ""
        return str(default)

    @property
    def spelling(self) -> str:
        """'-e, -everything', the way the option is typed."""
        return ", ".join(self.names)

    @property
    def shown_value(self) -> str:
        """The value for the table, with a long list of choices left to the description."""
        if len(self.choices) > INLINE_CHOICES_LIMIT:
            return "one of the choices below"
        return self.value


def read_parser(parser: argparse.ArgumentParser) -> list[Option]:
    """Every option the parser has, in the order -h lists them, with the group each is in.

    Args:
        parser (argparse.ArgumentParser): one of the program's two parsers.

    Returns:
        list[Option]: the options.  -h itself is left out; the page says so once.
    """
    belongs: dict[int, str] = {}
    for group in parser._action_groups:
        for action in group._group_actions:
            belongs[id(action)] = group.title or ""

    exclusive: dict[int, list[argparse.Action]] = {}
    for group in parser._mutually_exclusive_groups:
        for action in group._group_actions:
            exclusive[id(action)] = list(group._group_actions)

    options = []
    for action in parser._actions:
        if not action.option_strings or "-h" in action.option_strings or action.help == SUPPRESSED:
            continue
        others = [other.option_strings[0] for other in exclusive.get(id(action), []) if other is not action]
        options.append(Option(action, belongs.get(id(action), "options"), others))
    return options


# ##################################################################################
# Writing the page
# ##################################################################################
def escape_cell(text: str) -> str:
    """Make text safe inside a markdown table cell: no bare pipes, no raw line breaks, '<' kept literal."""
    return text.replace("|", "\\|").replace("<", "&lt;").replace("\n", "<br>")


def describe(option: Option, *, say_exclusive: bool = True) -> str:
    """The description cell: the help text, line for line, with the extras the parser knows."""
    lines = [line.strip() for line in option.description.splitlines() if line.strip()]
    cell = []
    for line in lines:
        # An example is code; put it in code so the dashes are not turned into list markers.
        match = re.match(r"^(Example:?)\s*(.*)$", line)
        cell.append(f"{match.group(1)} `{match.group(2)}`" if match and match.group(2) else line)
    text = "<br>".join(escape_cell(line) if "`" not in line else line.replace("|", "\\|") for line in cell)
    if option.exclusive_with and say_exclusive:
        text += "<br>_Use only one of:_ " + ", ".join(f"`{name}`" for name in [option.names[0], *option.exclusive_with])
    if len(option.choices) > INLINE_CHOICES_LIMIT:
        text += "<br>_Choices:_ " + ", ".join(f"`{choice}`" for choice in option.choices)
    return text


def table(options: list[Option], *, say_exclusive: bool = True) -> list[str]:
    """One table of options; `say_exclusive` is False where the heading above already says so."""
    lines = ["| Option | Value | Default | What it does |", "| --- | --- | --- | --- |"]
    for option in options:
        value = f"`{escape_cell(option.shown_value)}`" if option.shown_value else ""
        if option.shown_value == "one of the choices below":
            value = "_one of the choices below_"
        default = f"`{escape_cell(option.default)}`" if option.default else ""
        lines.append(f"| `{option.spelling}` | {value} | {default} | {describe(option, say_exclusive=say_exclusive)} |")
    return lines


def anchor(title: str) -> str:
    """The GitHub anchor for a heading."""
    return re.sub(r"[^a-z0-9 -]", "", title.lower()).replace(" ", "-")


def version() -> str:
    """The program's version, from pyproject.toml."""
    for line in (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        match = re.match(r'^version\s*=\s*"([^"]+)"', line)
        if match:
            return match.group(1)
    return "unknown"


def code_block(text: str) -> list[str]:
    """Text kept exactly as written, which is what the exit codes and report examples need."""
    return ["```text", *text.strip("\n").splitlines(), "```"]


def build_page(main_parser: argparse.ArgumentParser, report_parser: argparse.ArgumentParser) -> str:
    """The whole page, from the two parsers."""
    main_options = read_parser(main_parser)
    report_options = read_parser(report_parser)

    # Groups in the order the parser makes them; the plain 'options' group first.
    main_groups: dict[str, list[Option]] = {}
    for option in main_options:
        main_groups.setdefault(option.group, []).append(option)

    group_titles = {
        "options": "General options",
        "mutually inclusive": "Fetching the backup from an Android device",
        "Output Color Options": "Output color options",
    }
    sections = [(group_titles.get(title, title), table(group), "") for title, group in main_groups.items()]

    chosen = [option for option in report_options if option.exclusive_with]
    modifiers = [option for option in report_options if not option.exclusive_with]

    contents = [f"* [{title}](#{anchor(title)})" for title, _, _ in sections]
    contents += [
        "* [Reports with no window](#reports-with-no-window)",
        "  * [Choose one report](#choose-one-report)",
        "  * [Options for the reports](#options-for-the-reports)",
        "* [Exit codes](#exit-codes)",
    ]

    page = [
        "# MapTasker Runtime Options",
        "",
        "The options MapTasker takes on the command line.  Everything here is also what `-h` prints.",
        "",
        f"_Generated from the MapTasker {version()} source by `build_runtime_options_wiki.py`._ "
        "_Do not edit this page by hand -- rerun that program instead._",
        "",
        "## How to use this page",
        "",
        "* Options are written with a single dash, as in `-detail 3`.  A value with spaces in it goes in quotes.",
        "* **Default** is what the option is when you do not give it.  MapTasker remembers the options you give it "
        "from one run to the next; `-reset` forgets them, and `-runtime` prints the ones in force at the top of the "
        "output.",
        "* `-h` shows this list in the terminal.  `-g` (or `-gui`) asks for the options in a window instead, and "
        "overrides every other option.",
        "* To run one of the reports below with no window, name it on the command line.  Those take the second "
        "set of options and nothing from the first.",
        "",
        "## Contents",
        "",
        *contents,
        "",
    ]

    for title, rows, _ in sections:
        page += [f"## {title}", ""]
        if title == "Fetching the backup from an Android device":
            page += [
                "The three `-android_` options go together: give all of them or none.  They fetch the backup "
                "from the device's Tasker HTTP server instead of reading a file with `-file`.",
                "",
            ]
        if title == "Output color options":
            page += [
                "Each takes a color name (`-ch` lists the valid ones) or a hex value, as in "
                "`-cTask Green -cBackground Black -cProfile 19c8ff`.",
                "",
            ]
        page += [*rows, ""]

    page += [
        "## Reports with no window",
        "",
        "These run a report from the command line and write it to standard output; everything else goes to "
        "standard error.  Name one report, then any of the options after it.  `maptasker -healthcheck -h` shows "
        "just these options.",
        "",
        "### Choose one report",
        "",
        "Exactly one of these is required.",
        "",
        *table(chosen, say_exclusive=False),
        "",
        "### Options for the reports",
        "",
        "Where an option is for one report only, its description says which.",
        "",
        *table(modifiers),
        "",
        "## Exit codes",
        "",
        "What MapTasker exits with, so a script can tell what happened.",
        "",
        *code_block(exit_codes(main_parser)),
        "",
        "The reports above use these as well:",
        "",
        *code_block(report_parser.epilog or ""),
        "",
    ]
    return "\n".join(page).rstrip("\n") + "\n"


def exit_codes(parser: argparse.ArgumentParser) -> str:
    """The exit-code lines from the main parser's own epilog, as it prints them."""
    epilog = parser.epilog or ""
    start = epilog.find("Exit codes")
    if start < 0:
        return epilog
    end = epilog.find("\nReports that run", start)
    return epilog[start : end if end > 0 else len(epilog)].strip()


def load_parsers() -> tuple[argparse.ArgumentParser, argparse.ArgumentParser]:
    """The program's two parsers, imported from the source tree this tool lives in."""
    sys.path.insert(0, str(PROJECT_ROOT))
    from maptasker.src import clireports
    from maptasker.src.core import parsearg

    return parsearg.build_parser(), clireports.build_parser()


def main() -> int:
    """Build the page.

    Returns:
        int: 0, or 1 if '--check' found the page on disk out of date.
    """
    parser = argparse.ArgumentParser(description="Build the MapTasker Runtime Options wiki page.")
    parser.add_argument("--check", action="store_true", help="write nothing; fail if the page on disk is out of date")
    parser.add_argument("--print", dest="to_stdout", action="store_true", help="write nothing; print the page")
    parser.add_argument(
        "--page-name", default=DEFAULT_PAGE_NAME, help=f"Wiki page name (default: {DEFAULT_PAGE_NAME})."
    )
    add_publish_arguments(parser)
    arguments = parser.parse_args()
    if arguments.publish and (arguments.to_stdout or arguments.check):
        parser.error("--publish pushes the page on disk, so it cannot be used with --print or --check.")

    try:
        main_parser, report_parser = load_parsers()
    except ImportError as error:
        print(f"Cannot import MapTasker ({error}).  Run this with the project's own Python.", file=sys.stderr)
        return 1
    page = build_page(main_parser, report_parser)

    if arguments.to_stdout:
        print(page)
    elif arguments.check:
        current = OUTPUT_PAGE.read_text(encoding="utf-8") if OUTPUT_PAGE.is_file() else ""
        if current != page:
            print(
                f"{OUTPUT_PAGE.name} is out of date.  Run: python tools/misc/build_runtime_options_wiki.py",
                file=sys.stderr,
            )
            return 1
        print(f"{OUTPUT_PAGE.name} is up to date.")
    else:
        OUTPUT_PAGE.write_text(page, encoding="utf-8")
        count = len(read_parser(main_parser)) + len(read_parser(report_parser))
        print(f"Wrote {OUTPUT_PAGE.relative_to(PROJECT_ROOT)} -- {count} options.")

    if arguments.publish:
        return publish(OUTPUT_PAGE, arguments.page_name, arguments.wiki_repo, arguments.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
