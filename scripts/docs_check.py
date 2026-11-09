"""Hold the generated documents and the README to the code they describe.

Three pages in tools/misc are written by programs from the source -- the Command Reference (every command in the
window, and the reports that run with no window), the Runtime Options (every command-line option, read from the
program's own parsers) and the Generated Output (every file MapTasker writes) -- and each is published to the wiki.
A page that is not regenerated when the code changes goes on saying what the code used to do, and nothing noticed:
the Command Reference had no `-healthcheck`, `-compare`, `-export` or `-text` in it, and the Generated Output page
missed a file for a month.  So this runs each generator with its own `--check`, which writes nothing and fails if
the page on disk is not what the generator writes now.

README.md is written by hand, so the page cannot be regenerated; what can be held to the code is the part of it that
is a list of things the code has:

  * every report that runs with no window (`-healthcheck`, `-compare` ...) is named in the README, in its section on
    reports from the command line; and
  * the exit codes in that section's table are the ones the program documents.

    uv run python scripts/docs_check.py          check (what CI runs)

Fixing a failure: run the generator the message names (``publish-wikis.sh`` runs all three), and commit what it
writes; or, for the README, add the report or the code.
"""

from __future__ import annotations

import importlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools" / "misc"
README = ROOT / "README.md"

# The pages that are generated, by the program that writes each.
GENERATORS = ("build_command_wiki.py", "build_runtime_options_wiki.py", "build_generated_files_doc.py")

# The README section that lists the reports, and the heading that ends it.
README_SECTION = "### Reports from the command line"


def readme_section(text: str) -> str:
    """The README's section on reports from the command line, or "" when it has none."""
    start = text.find(README_SECTION)
    if start < 0:
        return ""
    end = re.search(r"^#{1,3} ", text[start + len(README_SECTION) :], re.MULTILINE)
    return text[start : start + len(README_SECTION) + end.start()] if end else text[start:]


def reports_missing(section: str, reports: list[str]) -> list[str]:
    """The reports (as `-healthcheck`) the README section does not name."""
    return [report for report in reports if not re.search(rf"(?<![\w-]){re.escape(report)}(?![\w-])", section)]


def codes_in_table(section: str) -> set[int]:
    """The exit codes in the section's table: the number at the start of each row."""
    return {int(match.group(1)) for match in re.finditer(r"^\s*\|\s*(\d+)\s*\|", section, re.MULTILINE)}


def documented_codes(main_epilog: str) -> set[int]:
    """The exit codes the program documents: 0 for success, and every 'exit N-' its help gives."""
    return {0, *(int(code) for code in re.findall(r"\bexit (\d+)-", main_epilog))}


def readme_problems(text: str, reports: list[str], main_epilog: str) -> list[str]:
    """What is wrong with the README, as sentences; none when it agrees with the code."""
    section = readme_section(text)
    if not section:
        return [f"README.md has no '{README_SECTION}' section."]
    problems = []
    if missing := reports_missing(section, reports):
        problems.append(
            f"README.md's '{README_SECTION.lstrip('# ')}' does not name {', '.join(missing)}.  Every report that "
            "runs with no window is listed there."
        )
    listed, documented = codes_in_table(section), documented_codes(main_epilog)
    if listed != documented:
        only_readme = sorted(listed - documented)
        only_program = sorted(documented - listed)
        problems.append(
            "README.md's exit-code table is not the program's"
            + (f": it lists {only_readme}, which the program does not document" if only_readme else "")
            + (f": it leaves out {only_program}" if only_program else "")
            + "."
        )
    return problems


def generated_pages_problems() -> list[str]:
    """Run each generator's --check; the output of those that fail."""
    problems = []
    for generator in GENERATORS:
        command = [sys.executable, str(TOOLS / generator), "--check"]
        done = subprocess.run(command, capture_output=True, text=True, cwd=ROOT, check=False)
        if done.returncode != 0:
            problems.append((done.stderr or done.stdout).strip() or f"{generator} --check failed.")
    return problems


def the_programs_own_words() -> tuple[list[str], str]:
    """(the reports that run with no window, the exit-code help of the main parser), asked of the parsers themselves."""
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(TOOLS))
    runtime_options = importlib.import_module("build_runtime_options_wiki")  # found through the path just set

    main_parser, report_parser = runtime_options.load_parsers()
    reports = [option.names[0] for option in runtime_options.read_parser(report_parser) if option.exclusive_with]
    return reports, main_parser.epilog or ""


def main() -> int:
    """Check everything; print what is out of step; return 1 if anything is."""
    problems = generated_pages_problems()
    reports, epilog = the_programs_own_words()
    problems += readme_problems(README.read_text(encoding="utf-8"), reports, epilog)
    if problems:
        print("The documents are out of step with the code:\n", file=sys.stderr)
        for problem in problems:
            print(f"  * {problem}", file=sys.stderr)
        print("\nRegenerate the pages with ./publish-wikis.sh --dry-run (it rewrites tools/misc), and edit README.md.")
        return 1
    print("docs check: the generated pages are current and the README names every report.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
