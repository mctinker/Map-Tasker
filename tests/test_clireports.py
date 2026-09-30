"""clireports Unit Tests

The reports that do not need the window -- Health Check, Compare, Changes Since, Export and the
folder watch -- run from the command line.  What a script relies on is tested here: the exit
code, that the report and only the report is on standard output, and that a run changes
nothing it was not asked to (no browser, no rewritten settings file, no error file left for the
window to greet the user with).

Every test runs clireports.run() in a working directory of its own, which is where the history,
the settings file and the error file would land.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from maptasker.src import clireports, timeline
from maptasker.src.primitem import PrimeItems, PrimeItemsReset
from maptasker.src.sysconst import ARGUMENTS_FILE, ERROR_FILE

from tests.test_healthck import _DEFECTIVE_XML

_SYNTHETIC_BACKUP = Path(__file__).parent / "data" / "synthetic_backup.xml"
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _a_clean_run_in_a_scratch_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A working directory of the test's own, and PrimeItems put back afterwards."""
    monkeypatch.chdir(tmp_path)
    yield
    timeline.use_history_folder(None)
    PrimeItemsReset()
    PrimeItems.headless = False


def _backup(tmp_path: Path, name: str = "backup.xml", *, renamed: str = "", modified: float | None = None) -> Path:
    """A copy of the synthetic backup, with one Task renamed if asked, dated `modified`."""
    text = _SYNTHETIC_BACKUP.read_text(encoding="utf-8")
    if renamed:
        assert "<nme>Remind Me</nme>" in text
        text = text.replace("<nme>Remind Me</nme>", f"<nme>{renamed}</nme>", 1)
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    if modified is not None:
        os.utime(path, (modified, modified))
    return path


def _run(*argv: str) -> int:
    return clireports.run(list(argv))


# ##################################################################################
# Which command lines are reports
# ##################################################################################
@pytest.mark.parametrize(
    "argv",
    [
        ["-healthcheck"],
        ["--healthcheck", "-file", "a.xml"],
        ["-compare", "a.xml", "b.xml"],
        ["-changes_since=week"],
        ["-file", "a.xml", "-export", "map"],
        ["-watch", "folder"],
    ],
)
def test_these_command_lines_ask_for_a_report(argv: list[str]) -> None:
    assert clireports.wants_report(argv)


@pytest.mark.parametrize(
    "argv",
    [[], ["-g"], ["-file", "backup.xml"], ["-detail", "3"], ["-debug"], ["-v"], ["-healthchecks"], ["healthcheck"]],
)
def test_these_command_lines_are_left_to_the_window(argv: list[str]) -> None:
    assert not clireports.wants_report(argv)


# ##################################################################################
# The report is on standard output, and everything else is not
# ##################################################################################
def test_the_health_check_is_on_stdout_and_the_status_is_on_stderr(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    backup = _backup(tmp_path)

    code = _run("-healthcheck", "-file", str(backup))

    captured = capsys.readouterr()
    assert code == clireports.EXIT_OK
    assert captured.out.startswith("MapTasker Health Check")
    assert "loaded" not in captured.out, "status leaked into the report"
    assert "Health Check:" in captured.err
    assert "loaded" in captured.err


# ##################################################################################
# Health Check exit codes
# ##################################################################################
def test_a_backup_with_errors_exits_10(tmp_path: Path) -> None:
    broken = tmp_path / "broken.xml"
    broken.write_text(_DEFECTIVE_XML, encoding="utf-8")

    assert _run("-healthcheck", "-file", str(broken)) == clireports.EXIT_FOUND


def test_warnings_alone_do_not_fail_the_run_unless_asked_to(tmp_path: Path) -> None:
    backup = _backup(tmp_path)  # 0 errors, some warnings.

    assert _run("-healthcheck", "-file", str(backup)) == clireports.EXIT_OK
    assert _run("-healthcheck", "-file", str(backup), "-fail_on", "warning") == clireports.EXIT_FOUND


def test_fail_on_never_always_exits_0_once_the_report_is_made(tmp_path: Path) -> None:
    broken = tmp_path / "broken.xml"
    broken.write_text(_DEFECTIVE_XML, encoding="utf-8")

    assert _run("-healthcheck", "-file", str(broken), "-fail_on", "never") == clireports.EXIT_OK


# ##################################################################################
# Files that are not there, or not backups
# ##################################################################################
def test_no_file_given_is_exit_6(capsys: pytest.CaptureFixture) -> None:
    assert _run("-healthcheck") == clireports.EXIT_NO_FILE
    assert "No backup was given" in capsys.readouterr().err


def test_a_file_that_is_not_there_is_exit_6(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    assert _run("-healthcheck", "-file", str(tmp_path / "nope.xml")) == clireports.EXIT_NO_FILE
    assert "nope.xml was not found" in capsys.readouterr().err


def test_a_folder_with_no_backup_in_it_is_exit_6(tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()

    assert _run("-healthcheck", "-file", str(tmp_path / "empty")) == clireports.EXIT_NO_FILE


def test_a_folder_means_the_newest_backup_in_it(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    folder = tmp_path / "backups"
    folder.mkdir()
    _backup(folder, "old.xml", modified=1_700_000_000)
    _backup(folder, "new.xml", modified=1_800_000_000)

    assert _run("-healthcheck", "-file", str(folder)) == clireports.EXIT_OK
    assert "new.xml" in capsys.readouterr().err


@pytest.mark.parametrize("content", ["<hello/>", "this is not xml at all"])
def test_a_file_that_is_not_a_backup_is_exit_3_and_leaves_no_error_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
    content: str,
) -> None:
    junk = tmp_path / "junk.xml"
    junk.write_text(content, encoding="utf-8")

    assert _run("-healthcheck", "-file", str(junk)) == clireports.EXIT_NOT_A_BACKUP
    assert capsys.readouterr().err.strip(), "a failure with no reason given"
    assert not Path(ERROR_FILE).exists(), "the window would greet the user with this run's error"


def test_an_error_file_already_there_is_left_exactly_as_it_was(tmp_path: Path) -> None:
    Path(ERROR_FILE).write_bytes(b"an earlier error\n1\n")
    junk = tmp_path / "junk.xml"
    junk.write_text("<hello/>", encoding="utf-8")

    _run("-healthcheck", "-file", str(junk))

    assert Path(ERROR_FILE).read_bytes() == b"an earlier error\n1\n"


# ##################################################################################
# Bad options
# ##################################################################################
@pytest.mark.parametrize(
    "argv",
    [
        ["-healthcheck", "-fail_on", "sometimes"],
        ["-export", "tree"],
        ["-export", "map", "-format", "docx"],
        ["-healthcheck", "-compare", "a.xml", "b.xml"],  # One report at a time.
        ["-compare", "only-one.xml"],
        ["-file", "backup.xml"],  # A file but no report (and so not a report run at all).
    ],
)
def test_an_option_that_makes_no_sense_is_exit_7(argv: list[str]) -> None:
    assert _run(*argv) == clireports.EXIT_BAD_OPTION


def test_help_is_answered_and_exits_0(capsys: pytest.CaptureFixture) -> None:
    assert _run("-healthcheck", "-h") == clireports.EXIT_OK
    assert "Exit codes" in capsys.readouterr().out


# ##################################################################################
# Compare
# ##################################################################################
def test_two_backups_that_differ_exit_10_and_say_what_changed(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    older = _backup(tmp_path, "older.xml", modified=1_700_000_000)
    newer = _backup(tmp_path, "newer.xml", renamed="Remind Me RENAMED", modified=1_800_000_000)

    code = _run("-compare", str(older), str(newer))

    out = capsys.readouterr().out
    assert code == clireports.EXIT_FOUND
    assert "Remind Me RENAMED" in out
    assert "1 renamed" in out


def test_compare_reads_the_same_whichever_way_round_they_are_given(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Which is older is settled by the files' dates, as in the window."""
    older = _backup(tmp_path, "older.xml", modified=1_700_000_000)
    newer = _backup(tmp_path, "newer.xml", renamed="Remind Me RENAMED", modified=1_800_000_000)

    _run("-compare", str(older), str(newer))
    forward = capsys.readouterr().out
    _run("-compare", str(newer), str(older))
    backward = capsys.readouterr().out

    def body(report: str) -> str:
        return "\n".join(line for line in report.splitlines() if not line.startswith("Generated:"))

    assert body(forward) == body(backward)


def test_two_backups_holding_the_same_configuration_exit_0(tmp_path: Path) -> None:
    first = _backup(tmp_path, "first.xml")
    second = _backup(tmp_path, "second.xml")

    assert _run("-compare", str(first), str(second)) == clireports.EXIT_OK


def test_comparing_a_file_with_itself_is_exit_7(tmp_path: Path) -> None:
    backup = _backup(tmp_path)

    assert _run("-compare", str(backup), str(backup)) == clireports.EXIT_BAD_OPTION


def test_compare_with_a_missing_file_is_exit_6(tmp_path: Path) -> None:
    assert _run("-compare", str(_backup(tmp_path)), str(tmp_path / "nope.xml")) == clireports.EXIT_NO_FILE


def test_compare_with_something_that_is_not_a_backup_is_exit_3(tmp_path: Path) -> None:
    junk = tmp_path / "junk.xml"
    junk.write_text("<hello/>", encoding="utf-8")

    assert _run("-compare", str(_backup(tmp_path)), str(junk)) == clireports.EXIT_NOT_A_BACKUP


def test_comparing_does_not_add_either_file_to_the_history(tmp_path: Path) -> None:
    _run("-compare", str(_backup(tmp_path, "a.xml")), str(_backup(tmp_path, "b.xml", renamed="Remind Me 2")))

    assert timeline.snapshots() == []


# ##################################################################################
# Changes Since
# ##################################################################################
def test_with_no_history_the_first_run_starts_it_and_exits_11(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    backup = _backup(tmp_path)

    code = _run("-changes_since", "week", "-file", str(backup))

    assert code == clireports.EXIT_NO_HISTORY
    assert "first entry" in capsys.readouterr().err
    assert len(timeline.snapshots()) == 1, "the backup should now be the start of the history"


def test_changes_since_a_period_exits_10_when_the_configuration_changed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
) -> None:
    yesterday = datetime.now().astimezone() - timedelta(days=1)
    timeline.record(str(_backup(tmp_path, "old.xml")), when=yesterday)
    newer = _backup(tmp_path, "new.xml", renamed="Remind Me RENAMED")

    code = _run("-changes_since", "today", "-file", str(newer))

    out = capsys.readouterr().out
    assert code == clireports.EXIT_FOUND
    assert "Remind Me RENAMED" in out


def test_changes_since_exits_0_when_nothing_changed_in_the_period(tmp_path: Path) -> None:
    yesterday = datetime.now().astimezone() - timedelta(days=1)
    same = _backup(tmp_path, "same.xml")
    timeline.record(str(same), when=yesterday)

    assert _run("-changes_since", "today", "-file", str(same)) == clireports.EXIT_OK


def test_a_history_that_does_not_reach_back_far_enough_says_so_but_still_compares(
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
) -> None:
    timeline.record(str(_backup(tmp_path, "old.xml")), when=datetime.now().astimezone() - timedelta(hours=2))

    code = _run("-changes_since", "30d", "-file", str(_backup(tmp_path, "new.xml", renamed="Remind Me RENAMED")))

    assert code == clireports.EXIT_FOUND
    assert "does not reach back that far" in capsys.readouterr().err


@pytest.mark.parametrize("period", ["fortnight", "", "2026-13-45", "d3"])
def test_a_period_that_is_not_one_is_exit_7(tmp_path: Path, period: str) -> None:
    assert _run("-changes_since", period, "-file", str(_backup(tmp_path))) == clireports.EXIT_BAD_OPTION


@pytest.mark.parametrize(
    ("period", "days_back"),
    [("3d", 3), ("10D", 10), ("today", None), ("week", 7), ("month", 30), ("all", "all"), ("2026-09-01", "date")],
)
def test_the_periods_that_are_understood(period: str, days_back: object) -> None:
    cutoff = clireports._cutoff(period)  # noqa: SLF001

    if days_back == "all":
        assert cutoff is None
    elif days_back == "date":
        assert (cutoff.year, cutoff.month, cutoff.day, cutoff.hour) == (2026, 9, 1, 0)
    elif days_back is None:
        assert cutoff.hour == cutoff.minute == 0
    else:
        assert abs((datetime.now().astimezone() - cutoff) - timedelta(days=days_back)) < timedelta(seconds=5)


# ##################################################################################
# Export
# ##################################################################################
def test_export_writes_the_file_and_prints_only_its_path(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    out_folder = tmp_path / "out"
    out_folder.mkdir()

    code = _run("-export", "map", "-format", "md", "-file", str(_backup(tmp_path)), "-outdir", str(out_folder))

    written = capsys.readouterr().out.strip()
    assert code == clireports.EXIT_OK
    assert Path(written).parent == out_folder
    assert Path(written).name.endswith(".md")
    assert "Reminders" in Path(written).read_text(encoding="utf-8"), "the Map should hold the backup's Projects"


@pytest.mark.parametrize(("view", "fmt"), [("map", "json"), ("diagram", "md"), ("diagram", "json")])
def test_the_other_views_and_formats_export_too(tmp_path: Path, capsys: pytest.CaptureFixture, view: str, fmt: str) -> None:
    out_folder = tmp_path / "out"
    out_folder.mkdir()

    code = _run("-export", view, "-format", fmt, "-file", str(_backup(tmp_path)), "-outdir", str(out_folder))

    assert code == clireports.EXIT_OK
    assert Path(capsys.readouterr().out.strip()).is_file()


def test_export_never_opens_a_browser(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda *args, **kwargs: opened.append(args) or True)

    _run("-export", "map", "-file", str(_backup(tmp_path)), "-outdir", str(tmp_path))

    assert opened == []


def test_export_leaves_the_users_settings_file_alone(tmp_path: Path) -> None:
    settings = tmp_path / ARGUMENTS_FILE
    settings.write_text('[program_arguments]\ndisplay_detail_level = 2\n', encoding="utf-8")
    before = settings.read_bytes()

    _run("-export", "map", "-detail", "4", "-file", str(_backup(tmp_path)), "-outdir", str(tmp_path))

    assert settings.read_bytes() == before, "an export rewrote the settings the window keeps"


def test_a_run_with_no_settings_file_does_not_create_one(tmp_path: Path) -> None:
    _run("-export", "map", "-file", str(_backup(tmp_path)), "-outdir", str(tmp_path))
    _run("-healthcheck", "-file", str(_backup(tmp_path)))

    assert not (tmp_path / ARGUMENTS_FILE).exists()


# ##################################################################################
# Saving
# ##################################################################################
def test_save_also_writes_the_report_the_way_the_window_does(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    out_folder = tmp_path / "out"
    out_folder.mkdir()

    _run("-healthcheck", "-save", "-file", str(_backup(tmp_path)), "-outdir", str(out_folder))

    assert list(out_folder.glob("MapTasker_HealthCheck_*.txt"))
    assert "saved as" in capsys.readouterr().err


def test_a_report_that_cannot_be_saved_is_exit_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("maptasker.src.healthck.write_health_check_report", lambda _rows: "")

    assert _run("-healthcheck", "-save", "-file", str(_backup(tmp_path))) == clireports.EXIT_OUTPUT_FAILED


def test_an_output_folder_that_cannot_be_used_is_exit_2(tmp_path: Path) -> None:
    not_a_folder = tmp_path / "file.txt"
    not_a_folder.write_text("x", encoding="utf-8")

    assert _run("-healthcheck", "-file", str(_backup(tmp_path)), "-outdir", str(not_a_folder)) == clireports.EXIT_OUTPUT_FAILED


# ##################################################################################
# The history, and the folder watch
# ##################################################################################
def test_a_load_is_recorded_in_the_history_unless_told_to_keep_it_elsewhere(tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere"

    _run("-healthcheck", "-file", str(_backup(tmp_path)), "-history_dir", str(elsewhere))

    assert list(elsewhere.glob("*.xml.gz"))
    assert not (tmp_path / timeline.HISTORY_FOLDER).exists()


def test_the_history_folder_override_does_not_outlive_the_run(tmp_path: Path) -> None:
    _run("-healthcheck", "-file", str(_backup(tmp_path)), "-history_dir", str(tmp_path / "elsewhere"))
    _run("-healthcheck", "-file", str(_backup(tmp_path, "later.xml", renamed="Remind Me 2")))

    assert list((tmp_path / timeline.HISTORY_FOLDER).glob("*.xml.gz")), "the next run kept using the last run's folder"


def test_watch_once_records_the_newest_backup_and_exits_0(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    folder = tmp_path / "backups"
    folder.mkdir()
    _backup(folder, "new.xml", modified=1_800_000_000)

    code = _run("-watch", str(folder), "-once")

    assert code == clireports.EXIT_OK
    assert "recorded new.xml" in capsys.readouterr().out
    assert len(timeline.snapshots()) == 1


def test_watching_something_that_is_not_a_folder_is_exit_6(tmp_path: Path) -> None:
    assert _run("-watch", str(tmp_path / "nowhere"), "-once") == clireports.EXIT_NO_FILE


def test_a_watch_is_stopped_cleanly_by_an_interrupt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = tmp_path / "backups"
    folder.mkdir()

    def stop(*_args: object, **_kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("maptasker.src.folderwatch.watch", stop)

    assert _run("-watch", str(folder)) == clireports.EXIT_OK


# ##################################################################################
# Through the real entry point, in a process of its own
# ##################################################################################
def _command_line(*argv: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "maptasker.main", *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONPATH": str(_PROJECT_ROOT)},
        check=False,
        timeout=180,
    )


def test_the_real_command_line_ends_with_the_exit_code_and_keeps_stdout_clean(tmp_path: Path) -> None:
    broken = tmp_path / "broken.xml"
    broken.write_text(_DEFECTIVE_XML, encoding="utf-8")

    result = _command_line("-healthcheck", "-file", str(broken), cwd=tmp_path)

    assert result.returncode == clireports.EXIT_FOUND
    assert result.stdout.startswith("MapTasker Health Check")
    assert "Health Check:" in result.stderr


def test_the_real_command_line_reports_a_missing_file_with_exit_6(tmp_path: Path) -> None:
    result = _command_line("-healthcheck", "-file", "nope.xml", cwd=tmp_path)

    assert result.returncode == clireports.EXIT_NO_FILE
    assert result.stdout == ""


def test_a_report_run_never_loads_the_gui(tmp_path: Path) -> None:
    """A scheduled job on a machine with no display should not start the GUI framework to read a file."""
    script = "import sys; import maptasker.src.clireports; print('nicegui' in sys.modules)"
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(_PROJECT_ROOT)},
        check=False,
        timeout=120,
    )

    assert result.stdout.strip() == "False", result.stderr
