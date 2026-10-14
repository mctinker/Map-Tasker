"""Start-up: the run counter, finding the backup file to open, the colours and the Python version."""

from __future__ import annotations

from pathlib import Path

import pytest
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.mapgen import proginit


@pytest.fixture
def errors(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int]]:
    """error_handler replaced by a recorder, because the real one ends the run for most codes."""
    seen: list[tuple[str, int]] = []
    monkeypatch.setattr(proginit, "error_handler", lambda message, code, **_kw: seen.append((message, code)))
    return seen


# ##################################################################################
# The run counter
# ##################################################################################
def test_the_first_run_counts_as_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(proginit, "COUNTER_FILE", str(tmp_path / "counter.txt"))
    assert proginit.read_counter() == 0


def test_each_later_run_counts_one_more(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    counter = tmp_path / "counter.txt"
    counter.write_text("4", encoding="utf-8")
    monkeypatch.setattr(proginit, "COUNTER_FILE", str(counter))
    assert proginit.read_counter() == 5


def test_the_count_is_written_for_the_next_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    counter = tmp_path / "counter.txt"
    monkeypatch.setattr(proginit, "COUNTER_FILE", str(counter))
    monkeypatch.setattr(proginit, "run_counter", 7)
    proginit.write_counter()
    assert counter.read_text(encoding="utf-8") == "7"


# ##################################################################################
# Finding the backup file
# ##################################################################################
def test_no_file_chosen_ends_a_command_line_run(errors: list, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PrimeItems, "file_to_get", None)
    monkeypatch.setattr(PrimeItems.program_arguments, "gui", False)
    proginit.prompt_for_backup_file("", state=PrimeItems)
    assert errors == [("Backup file selection canceled.  Program ended.", 6)]


def test_no_file_chosen_in_the_window_returns_to_the_window(errors: list, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PrimeItems, "file_to_get", None)
    monkeypatch.setattr(PrimeItems, "error_code", 0)
    monkeypatch.setattr(PrimeItems.program_arguments, "gui", True)
    proginit.prompt_for_backup_file("", state=PrimeItems)
    assert errors == []
    assert PrimeItems.error_code == 5


def test_a_file_already_open_needs_no_prompt(errors: list, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PrimeItems, "file_to_get", object())
    proginit.prompt_for_backup_file("", state=PrimeItems)
    assert errors == []


def test_a_named_file_is_opened(tmp_path: Path, errors: list, monkeypatch: pytest.MonkeyPatch) -> None:
    backup = tmp_path / "backup.xml"
    backup.write_text("<TaskerData/>", encoding="utf-8")
    monkeypatch.setattr(PrimeItems.program_arguments, "android_ipaddr", "")
    monkeypatch.setattr(PrimeItems.program_arguments, "file", str(backup))

    proginit.open_and_get_backup_xml_file(state=PrimeItems)

    try:
        assert PrimeItems.file_to_get.read() == "<TaskerData/>"
    finally:
        PrimeItems.file_to_get.close()
    assert errors == []


def test_a_file_object_is_opened_by_its_name(tmp_path: Path, errors: list, monkeypatch: pytest.MonkeyPatch) -> None:
    """The GUI hands over a file it has already opened; the name is what is reopened."""
    backup = tmp_path / "backup.xml"
    backup.write_text("<TaskerData/>", encoding="utf-8")
    monkeypatch.setattr(PrimeItems.program_arguments, "android_ipaddr", "")
    with backup.open(encoding="utf-8") as handed_over:
        monkeypatch.setattr(PrimeItems.program_arguments, "file", handed_over)
        proginit.open_and_get_backup_xml_file(state=PrimeItems)
    try:
        assert PrimeItems.file_to_get.name == str(backup)
    finally:
        PrimeItems.file_to_get.close()


def test_a_file_that_is_not_there_is_an_error(tmp_path: Path, errors: list, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PrimeItems.program_arguments, "android_ipaddr", "")
    monkeypatch.setattr(PrimeItems.program_arguments, "file", str(tmp_path / "missing.xml"))

    proginit.open_and_get_backup_xml_file(state=PrimeItems)

    assert errors[0][1] == 6
    assert "missing.xml not found" in errors[0][0]


def test_a_file_that_cannot_be_read_is_a_warning_then_a_prompt(
    tmp_path: Path, errors: list, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr(PrimeItems.program_arguments, "android_ipaddr", "")
    monkeypatch.setattr(PrimeItems.program_arguments, "file", str(tmp_path / "locked.xml"))
    monkeypatch.setattr("builtins.open", refuse)

    proginit.open_and_get_backup_xml_file(state=PrimeItems)

    assert errors[0][1] == 100
    assert errors[-1] == ("Backup file selection canceled.  Program ended.", 6)  # nothing opened, so it prompts


def test_with_no_file_at_all_the_user_is_asked(errors: list, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PrimeItems.program_arguments, "android_ipaddr", "")
    monkeypatch.setattr(PrimeItems.program_arguments, "file", "")
    monkeypatch.setattr(PrimeItems.program_arguments, "gui", False)

    proginit.open_and_get_backup_xml_file(state=PrimeItems)

    assert errors == [("Backup file selection canceled.  Program ended.", 6)]


def _from_device(monkeypatch: pytest.MonkeyPatch, fetched: str | None, *, gui: bool) -> None:
    monkeypatch.setattr(PrimeItems.program_arguments, "android_ipaddr", "192.168.0.5")
    monkeypatch.setattr(PrimeItems.program_arguments, "android_port", "1821")
    monkeypatch.setattr(PrimeItems.program_arguments, "android_file", "/Tasker/backup.xml")
    monkeypatch.setattr(PrimeItems.program_arguments, "gui", gui)
    monkeypatch.setattr(PrimeItems.program_arguments, "file", "")
    monkeypatch.setattr(proginit, "get_backup_file", lambda state: fetched)


def test_a_backup_fetched_from_the_device_is_the_file_used(
    tmp_path: Path, errors: list, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup = tmp_path / "backup.xml"
    backup.write_text("<TaskerData/>", encoding="utf-8")
    _from_device(monkeypatch, str(backup), gui=False)

    proginit.open_and_get_backup_xml_file(state=PrimeItems)

    try:
        assert PrimeItems.program_arguments.file == str(backup)
        assert PrimeItems.file_to_get is not None
    finally:
        PrimeItems.file_to_get.close()


def test_a_failed_device_fetch_in_the_window_goes_back_to_the_window(
    errors: list, monkeypatch: pytest.MonkeyPatch
) -> None:
    _from_device(monkeypatch, None, gui=True)
    assert proginit.open_and_get_backup_xml_file(state=PrimeItems) is None
    assert errors == []


# ##################################################################################
# Colours
# ##################################################################################
def test_a_named_appearance_is_used_as_given(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PrimeItems.program_arguments, "appearance_mode", "dark")
    dark = proginit.setup_colors(PrimeItems)
    monkeypatch.setattr(PrimeItems.program_arguments, "appearance_mode", "light")
    assert proginit.setup_colors(PrimeItems) != dark


def test_the_system_appearance_keeps_a_colour_the_user_already_chose(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PrimeItems.program_arguments, "appearance_mode", "system")
    monkeypatch.setattr(PrimeItems, "colors_to_use", {"project_color": "Fuchsia"})
    assert proginit.setup_colors(PrimeItems)["project_color"] == "Fuchsia"


# ##################################################################################
# The Python version
# ##################################################################################
def test_a_supported_python_is_left_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    exits: list[int] = []
    monkeypatch.setattr(proginit, "exit_program", exits.append)
    monkeypatch.setattr(proginit.sys, "version", "3.12.1 (main, Jan 1 2026)")
    proginit.check_versions()
    assert exits == []


def test_an_old_python_ends_the_run_with_a_failure_status(monkeypatch: pytest.MonkeyPatch) -> None:
    exits: list[int] = []
    shown: list[str] = []
    monkeypatch.setattr(proginit, "exit_program", exits.append)
    monkeypatch.setattr(proginit.console, "error", shown.append)
    monkeypatch.setattr(proginit.sys, "version", "3.10.4 (main, Jan 1 2026)")

    proginit.check_versions()

    assert exits == [1]
    assert "3.11" in shown[0]
