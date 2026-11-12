"""What makes a release rehearsable: the Changelog's stamp, check and notes, the environment guard, and the workflow.

The v15.2.0 tag went to PyPI with nothing to stop it, because the `pypi` environment had no required reviewer.  The
workflow is tested as a document -- it is the only thing that says what runs, in what order, and what is never
reached -- and the two scripts it leans on as code.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from tests.doubles import required

_ROOT = Path(__file__).resolve().parent.parent


def _load(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, _ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(required(spec))
    sys.modules[name] = module
    required(required(spec).loader).exec_module(module)
    return module


changelog_release = _load("changelog_release")
release_guard = _load("release_guard")

CHANGELOG = """# MapTasker Change Log

All notable changes to this project will be documented in this file!

## [16.0.0] ??-Nov-2026  # FIX

### Added

- Added: __Plugin Retirement Advisor__ in the Analyze section lists the plugins your file uses that Tasker now does itself. It changes nothing.

- Added: `maptasker -text export` writes every piece of text a person reads on the phone to a spreadsheet.
  `-text import` brings it back.
- Added:

### Changed

- Changed: Switching between dark and light mode no longer repaints a Map that is already on screen. The assigned color survives.
- Changed:

### Removed

### Fixed

- Fixed: A Background color you choose now paints the window's main area, the Tree and Scene views, and the Map, with light or dark text to suit it, which it never did before because of a key that no palette has.

### Known Issues

* Something that is not a change.

## [15.2.0] 10-Nov-2026

- Added: An older change.
"""


# ##################################################################################
# The Changelog: stamp
# ##################################################################################
def test_the_stamp_puts_the_version_and_the_date_in_the_top_heading_and_changes_nothing_else() -> None:
    stamped = changelog_release.stamp(CHANGELOG, "16.0.0", date(2026, 11, 12))

    assert "## [16.0.0] 12-Nov-2026  # FIX" in stamped
    assert stamped.replace("12-Nov-2026", "??-Nov-2026") == CHANGELOG


def test_the_stamp_follows_the_version_it_is_given_and_never_touches_an_older_heading() -> None:
    stamped = changelog_release.stamp(CHANGELOG, "16.0.1", date(2026, 1, 5))

    assert "## [16.0.1] 05-Jan-2026  # FIX" in stamped
    assert "## [15.2.0] 10-Nov-2026" in stamped


def test_the_month_is_written_in_english_whatever_the_locale() -> None:
    assert [changelog_release.format_date(date(2026, month, 1)) for month in (1, 5, 12)] == [
        "01-Jan-2026",
        "01-May-2026",
        "01-Dec-2026",
    ]


def test_a_file_with_no_version_heading_is_refused() -> None:
    with pytest.raises(ValueError, match="no '## \\[version\\] date' heading"):
        changelog_release.stamp("# Nothing here\n", "1.0.0", date(2026, 1, 1))


# ##################################################################################
# The Changelog: check
# ##################################################################################
def test_a_heading_with_no_date_is_not_ready_and_says_how_to_make_it_so() -> None:
    [problem] = changelog_release.problems(CHANGELOG, "16.0.0")

    assert "no release date" in problem
    assert "changelog_release.py stamp" in problem


def test_a_stamped_heading_for_the_version_is_ready() -> None:
    assert changelog_release.problems(changelog_release.stamp(CHANGELOG, "16.0.0", date(2026, 11, 12)), "16.0.0") == []


def test_a_heading_for_another_version_is_not_ready() -> None:
    stamped = changelog_release.stamp(CHANGELOG, "16.0.0", date(2026, 11, 12))

    [problem] = changelog_release.problems(stamped, "16.0.1")

    assert "[16.0.0], not [16.0.1]" in problem


@pytest.mark.parametrize("written", ["??-Nov-2026", "32-Nov-2026", "10-Nox-2026", "2026-11-12", "30-Feb-2026"])
def test_only_a_real_date_in_the_changelogs_form_counts(written: str) -> None:
    assert changelog_release.parse_date(written) is None


# ##################################################################################
# The Changelog: the release text
# ##################################################################################
def test_each_change_is_one_brief_sentence_under_its_category() -> None:
    notes = changelog_release.release_notes(CHANGELOG, "16.0.0")

    assert "### Added" in notes
    assert (
        "- Plugin Retirement Advisor in the Analyze section lists the plugins your file uses that Tasker now does itself."
        in notes
    )
    assert "It changes nothing" not in notes, "the second sentence is left to the Changelog"
    assert "- Switching between dark and light mode no longer repaints a Map that is already on screen." in notes
    assert "The assigned color survives" not in notes


def test_a_change_that_runs_over_two_lines_is_one_change() -> None:
    notes = changelog_release.release_notes(CHANGELOG, "16.0.0")

    assert "- `maptasker -text export` writes every piece of text a person reads on the phone to a spreadsheet" in notes
    assert "-text import" not in notes


def test_a_long_sentence_is_cut_where_a_clause_ends_so_it_still_reads_as_a_sentence() -> None:
    sentence = changelog_release.one_sentence(
        "A Background color you choose now paints the window's main area, the Tree and Scene views, and the Map, "
        "with light or dark text to suit it, which it never did before because of a key that no palette has."
    )

    assert (
        sentence
        == "A Background color you choose now paints the window's main area, the Tree and Scene views, and the Map, with light or dark text to suit it."
    )


def test_a_long_sentence_is_never_cut_inside_a_bracket() -> None:
    sentence = changelog_release.one_sentence(
        "Plugin Advisor lists the plugins your file uses that Tasker now does itself, such as AutoShortcut "
        "(the Shortcut action, Tasker 5.9) and Join (Remote Action Execution, 6.4), with the built-in that takes over."
    )

    assert sentence.count("(") == sentence.count(")")


def test_a_long_sentence_with_no_clause_to_cut_at_is_cut_at_a_word_and_marked() -> None:
    sentence = changelog_release.one_sentence("Word " * 60)

    assert len(sentence) <= changelog_release.SENTENCE_LIMIT
    assert sentence.endswith("...")
    assert not sentence[:-3].endswith(" ")


def test_every_sentence_in_the_text_is_within_the_limit() -> None:
    for words in (5, 30, 80):
        assert len(changelog_release.one_sentence("Alpha beta, " * words)) <= changelog_release.SENTENCE_LIMIT


def test_the_placeholders_known_issues_and_older_sections_are_not_in_the_text() -> None:
    notes = changelog_release.release_notes(CHANGELOG, "16.0.0")

    assert "Something that is not a change" not in notes
    assert "An older change" not in notes
    assert "### Removed" not in notes, "a category with nothing in it is not shown"
    assert "- Added:" not in notes and "- Changed:" not in notes


def test_the_heading_of_the_text_carries_the_date_once_the_changelog_has_one() -> None:
    undated = changelog_release.release_notes(CHANGELOG, "16.0.0")
    dated = changelog_release.release_notes(
        changelog_release.stamp(CHANGELOG, "16.0.0", date(2026, 11, 12)), "16.0.0", "https://example.test/Changelog.md"
    )

    assert undated.startswith("## MapTasker 16.0.0\n")
    assert dated.startswith("## MapTasker 16.0.0 (12-Nov-2026)\n")
    assert "[Changelog](https://example.test/Changelog.md)" in dated


def test_the_changelog_in_the_repository_makes_a_release_text() -> None:
    """Whatever is in Changelog.md now: every change gets a sentence, none runs long, and nothing is left bare."""
    text = (_ROOT / "Changelog.md").read_text(encoding="utf-8")

    notes = changelog_release.release_notes(text, changelog_release.pyproject_version())

    lines = [line for line in notes.splitlines() if line.startswith("- ")]
    assert lines
    assert all(len(line) <= changelog_release.SENTENCE_LIMIT + 2 for line in lines)
    assert not any("__" in line for line in lines)


# ##################################################################################
# The guard
# ##################################################################################
def _environment(*, reviewers: list[dict[str, Any]], kind: str = "required_reviewers") -> dict[str, Any]:
    return {"name": "pypi", "protection_rules": [{"type": kind, "reviewers": reviewers}]}


def test_an_environment_with_a_required_reviewer_passes() -> None:
    assert release_guard.reviewer_problem(_environment(reviewers=[{"type": "User"}]), "pypi") == ""


@pytest.mark.parametrize(
    "environment",
    [
        {"name": "pypi", "protection_rules": []},
        {"name": "pypi"},
        _environment(reviewers=[]),
        _environment(reviewers=[{"type": "User"}], kind="wait_timer"),
    ],
)
def test_an_environment_with_no_reviewer_to_approve_fails_and_says_why(environment: dict[str, Any]) -> None:
    problem = release_guard.reviewer_problem(environment, "pypi")

    assert "no required reviewer" in problem
    assert "v15.2.0" in problem


def _answer(monkeypatch: pytest.MonkeyPatch, outcome: object) -> list[list[str]]:
    """Stand in for `gh api`: an environment as JSON, or a failure with this stderr (or this exception)."""
    asked: list[list[str]] = []

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        asked.append([*command, f"token={kwargs['env']['GH_TOKEN']}"])
        if isinstance(outcome, Exception):
            raise outcome
        if isinstance(outcome, str):
            return subprocess.CompletedProcess(command, 1, "", outcome)
        return subprocess.CompletedProcess(command, 0, json.dumps(outcome), "")

    monkeypatch.setattr(release_guard.subprocess, "run", run)
    return asked


def test_the_guard_asks_github_about_the_named_environment_with_the_token_it_was_given(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    asked = _answer(monkeypatch, _environment(reviewers=[{"type": "User"}]))
    monkeypatch.setenv("GITHUB_REPOSITORY", "mctinker/Map-Tasker")
    monkeypatch.setenv("GH_TOKEN", "secret")

    assert release_guard.main(["--environment", "pypi"]) == 0

    assert asked[0] == ["gh", "api", "repos/mctinker/Map-Tasker/environments/pypi", "token=secret"]
    assert "requires a reviewer" in capsys.readouterr().out


def test_the_guard_fails_when_the_environment_has_no_reviewer(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _answer(monkeypatch, {"name": "pypi", "protection_rules": []})
    monkeypatch.setenv("GITHUB_REPOSITORY", "mctinker/Map-Tasker")
    monkeypatch.setenv("GH_TOKEN", "secret")

    assert release_guard.main([]) == 1

    assert "no required reviewer" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("outcome", "says"),
    [
        ("gh: Not Found (HTTP 404)", "no 'pypi' environment"),
        ("gh: Resource not accessible by integration (HTTP 403)", "Administration"),
        (FileNotFoundError("gh"), "Could not ask GitHub"),
    ],
)
def test_the_guard_fails_when_it_cannot_find_out_rather_than_passing_blind(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], outcome: Exception, says: str
) -> None:
    _answer(monkeypatch, outcome)
    monkeypatch.setenv("GITHUB_REPOSITORY", "mctinker/Map-Tasker")
    monkeypatch.setenv("GH_TOKEN", "secret")

    assert release_guard.main([]) == 1

    assert says in capsys.readouterr().out


def test_the_guard_fails_when_it_has_no_token(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GITHUB_REPOSITORY", "mctinker/Map-Tasker")
    monkeypatch.delenv("GH_TOKEN", raising=False)

    assert release_guard.main([]) == 1

    assert "ENVIRONMENT_CHECK_TOKEN" in capsys.readouterr().out


# ##################################################################################
# The workflow
# ##################################################################################
@pytest.fixture(scope="module")
def workflow() -> dict[str, Any]:
    return yaml.safe_load((_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8"))


def _text(job: dict[str, Any]) -> str:
    return yaml.safe_dump(job)


def test_the_release_runs_on_a_tag_and_can_be_rehearsed_by_hand(workflow: dict[str, Any]) -> None:
    triggers: dict[str, Any] = cast("dict[Any, Any]", workflow).get("on") or cast("dict[Any, Any]", workflow)[True]

    assert triggers["push"]["tags"] == ["v*"]
    assert "workflow_dispatch" in triggers


def test_a_rehearsal_never_reaches_pypi_or_makes_a_release(workflow: dict[str, Any]) -> None:
    jobs = workflow["jobs"]

    assert "rehearsal == 'false'" in jobs["pypi"]["if"]
    assert "rehearsal == 'false'" in jobs["github-release"]["if"]
    assert "rehearsal == 'true'" in jobs["rehearsal"]["if"]
    assert "id-token" not in jobs["rehearsal"].get("permissions", {}), "the report has nothing to publish with"


def test_a_rehearsal_uploads_a_version_testpypi_has_not_seen(workflow: dict[str, Any]) -> None:
    steps = workflow["jobs"]["build"]["steps"]
    [rename] = [step for step in steps if "one nothing has used" in step.get("name", "")]

    assert rename["if"] == "needs.check.outputs.rehearsal == 'true'"
    assert ".dev${{ github.run_number }}" in rename["run"]
    assert workflow["jobs"]["testpypi"]["needs"] == ["check", "build"]


def test_the_guard_is_in_the_check_that_everything_waits_for_and_cannot_be_skipped(workflow: dict[str, Any]) -> None:
    check = workflow["jobs"]["check"]
    [guard] = [step for step in check["steps"] if "release_guard.py" in step.get("run", "")]

    assert "continue-on-error" not in guard, "a guard that can be waved through is not one"
    assert "if" not in guard, "it runs for a tag and for a rehearsal alike"
    assert guard["env"]["GH_TOKEN"] == "${{ secrets.ENVIRONMENT_CHECK_TOKEN }}"
    assert workflow["jobs"]["build"]["needs"] == "check"
    assert set(workflow["jobs"]["pypi"]["needs"]) >= {"check", "testpypi"}


def test_an_unstamped_changelog_stops_a_release_and_only_warns_a_rehearsal(workflow: dict[str, Any]) -> None:
    [step] = [s for s in workflow["jobs"]["check"]["steps"] if "changelog_release.py check" in s.get("run", "")]

    assert step["continue-on-error"] == "${{ steps.version.outputs.rehearsal == 'true' }}"


def test_the_github_release_comes_after_pypi_and_is_made_from_the_changelog(workflow: dict[str, Any]) -> None:
    release = workflow["jobs"]["github-release"]
    text = _text(release)

    assert set(release["needs"]) == {"check", "testpypi", "pypi"}
    assert "needs.pypi.result == 'success'" in release["if"]
    assert release["permissions"] == {"contents": "write"}
    assert "changelog_release.py notes" in text
    assert "gh release create" in text
    assert "--notes-file release-notes.md" in text
    assert "--prerelease" in text, "a pre-release tag is marked as one"
    assert "--verify-tag" in text


def test_only_the_real_pypi_job_can_publish_to_pypi(workflow: dict[str, Any]) -> None:
    publishers = [
        name
        for name, job in workflow["jobs"].items()
        if any("gh-action-pypi-publish" in step.get("uses", "") and "with" not in step for step in job.get("steps", []))
    ]

    assert publishers == ["pypi"], "an upload with no repository-url goes to PyPI itself"
