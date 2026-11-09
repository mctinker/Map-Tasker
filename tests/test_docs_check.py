"""The gate that holds the generated pages and the README to the code (scripts/docs_check.py)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from tests.doubles import required

_ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location("docs_check", _ROOT / "scripts" / "docs_check.py")
docs_check = importlib.util.module_from_spec(required(_SPEC))
sys.modules["docs_check"] = docs_check
required(required(_SPEC).loader).exec_module(docs_check)

_EPILOG = """Exit codes...
    exit 1- program error
    exit 2- output file failure
    exit 10- a command-line report found something
"""

_README = """# MapTasker

### Reports from the command line

```
maptasker -healthcheck -file backup.xml
maptasker -text export -file backup.xml
```

  | Code | Meaning |
  |---|---|
  | 0 | Done |
  | 10 | The report found something |
  | 1 | Program error |
  | 2 | A file could not be written |

## Program Output

Mentions -trend here, outside the section, which does not count.
"""


def test_the_readmes_section_on_reports_ends_at_the_next_heading() -> None:
    section = docs_check.readme_section(_README)

    assert "-healthcheck" in section
    assert "Program Output" not in section
    assert "-trend" not in section


def test_a_report_the_readme_does_not_name_is_found_missing() -> None:
    section = docs_check.readme_section(_README)

    assert docs_check.reports_missing(section, ["-healthcheck", "-text", "-trend", "-watch"]) == ["-trend", "-watch"]


def test_a_flag_is_not_found_inside_a_longer_one() -> None:
    assert docs_check.reports_missing("-text_format csv", ["-text"]) == ["-text"]
    assert docs_check.reports_missing("a -text export", ["-text"]) == []


def test_the_exit_codes_are_the_numbers_that_start_the_tables_rows() -> None:
    assert docs_check.codes_in_table(docs_check.readme_section(_README)) == {0, 10, 1, 2}
    assert docs_check.documented_codes(_EPILOG) == {0, 1, 2, 10}


def test_a_readme_that_agrees_with_the_code_has_no_problem() -> None:
    assert docs_check.readme_problems(_README, ["-healthcheck", "-text"], _EPILOG) == []


def test_a_missing_report_and_a_wrong_exit_code_are_each_a_sentence() -> None:
    problems = docs_check.readme_problems(
        _README + "", ["-healthcheck", "-trend"], _EPILOG + "    exit 8- the device failed\n"
    )

    assert len(problems) == 2
    assert "does not name -trend" in problems[0]
    assert "leaves out [8]" in problems[1]


def test_an_exit_code_the_program_does_not_have_is_named() -> None:
    problems = docs_check.readme_problems(_README, ["-healthcheck"], "exit 1- a\n")

    assert any("lists [2, 10], which the program does not document" in problem for problem in problems)


def test_a_readme_without_the_section_says_so() -> None:
    assert docs_check.readme_problems("# Nothing here", ["-healthcheck"], _EPILOG) == [
        "README.md has no '### Reports from the command line' section."
    ]


def test_the_readme_in_this_repository_agrees_with_the_code() -> None:
    """The live one: a new report that is not in the README, or an exit code the table lacks, fails here as well."""
    reports, epilog = docs_check.the_programs_own_words()

    assert "-healthcheck" in reports
    assert docs_check.readme_problems((_ROOT / "README.md").read_text(encoding="utf-8"), reports, epilog) == []


@pytest.mark.parametrize(
    "report", ["-healthcheck", "-compare", "-export", "-text", "-trend", "-watch", "-changes_since"]
)
def test_the_command_reference_names_every_report(report: str) -> None:
    """The page had none of them: it described the window and a subset of the options."""
    page = (_ROOT / "tools" / "misc" / "Command-Reference.md").read_text(encoding="utf-8")

    assert f"`{report}`" in page


def test_the_command_reference_carries_no_date_so_a_second_run_changes_nothing() -> None:
    import re

    page = (_ROOT / "tools" / "misc" / "Command-Reference.md").read_text(encoding="utf-8")

    assert not re.search(r"source on \d{4}-\d{2}-\d{2}", page)
