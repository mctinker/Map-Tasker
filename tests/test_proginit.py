"""Start-up: the run counter, finding the backup file to open, the colours and the Python version."""

from __future__ import annotations

from pathlib import Path

import pytest
from maptasker.src.core.mtexcept import MapTaskerError
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.mapgen import proginit


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
@pytest.mark.parametrize("gui", [False, True])
def test_no_file_chosen_is_an_error_whoever_is_asking(gui: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    """Raised either way; whether that ends the run or goes back to the window is the caller's to say."""
    monkeypatch.setattr(PrimeItems, "file_to_get", None)
    monkeypatch.setattr(PrimeItems.program_arguments, "gui", gui)
    with pytest.raises(MapTaskerError) as raised:
        proginit.prompt_for_backup_file("", state=PrimeItems)
    assert raised.value.message == "Backup file selection canceled.  Program ended."
    assert raised.value.exit_code == 6


def test_a_file_already_open_needs_no_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PrimeItems, "file_to_get", object())
    proginit.prompt_for_backup_file("", state=PrimeItems)


def test_a_named_file_is_opened(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    backup = tmp_path / "backup.xml"
    backup.write_text("<TaskerData/>", encoding="utf-8")
    monkeypatch.setattr(PrimeItems.program_arguments, "android_ipaddr", "")
    monkeypatch.setattr(PrimeItems.program_arguments, "file", str(backup))

    proginit.open_and_get_backup_xml_file(state=PrimeItems)

    try:
        assert PrimeItems.file_to_get.read() == "<TaskerData/>"
    finally:
        PrimeItems.file_to_get.close()


def test_a_file_object_is_opened_by_its_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_a_file_that_is_not_there_is_an_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PrimeItems.program_arguments, "android_ipaddr", "")
    monkeypatch.setattr(PrimeItems.program_arguments, "file", str(tmp_path / "missing.xml"))

    with pytest.raises(MapTaskerError) as raised:
        proginit.open_and_get_backup_xml_file(state=PrimeItems)

    assert raised.value.exit_code == 6
    assert "missing.xml not found" in raised.value.message


def test_a_file_that_cannot_be_read_is_an_error_that_says_so(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr(PrimeItems.program_arguments, "android_ipaddr", "")
    monkeypatch.setattr(PrimeItems.program_arguments, "file", str(tmp_path / "locked.xml"))
    monkeypatch.setattr("builtins.open", refuse)

    with pytest.raises(MapTaskerError) as raised:
        proginit.open_and_get_backup_xml_file(state=PrimeItems)

    assert raised.value.exit_code == 6
    assert "locked.xml not accessible" in raised.value.message


def test_with_no_file_at_all_there_is_nothing_to_open(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PrimeItems.program_arguments, "android_ipaddr", "")
    monkeypatch.setattr(PrimeItems.program_arguments, "file", "")
    monkeypatch.setattr(PrimeItems.program_arguments, "gui", False)

    with pytest.raises(MapTaskerError) as raised:
        proginit.open_and_get_backup_xml_file(state=PrimeItems)

    assert (raised.value.message, raised.value.exit_code) == ("Backup file selection canceled.  Program ended.", 6)


def _from_device(monkeypatch: pytest.MonkeyPatch, fetched: str | None, *, gui: bool) -> None:
    monkeypatch.setattr(PrimeItems.program_arguments, "android_ipaddr", "192.168.0.5")
    monkeypatch.setattr(PrimeItems.program_arguments, "android_port", "1821")
    monkeypatch.setattr(PrimeItems.program_arguments, "android_file", "/Tasker/backup.xml")
    monkeypatch.setattr(PrimeItems.program_arguments, "gui", gui)
    monkeypatch.setattr(PrimeItems.program_arguments, "file", "")
    monkeypatch.setattr(proginit, "get_backup_file", lambda state: fetched)


def test_a_backup_fetched_from_the_device_is_the_file_used(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    backup = tmp_path / "backup.xml"
    backup.write_text("<TaskerData/>", encoding="utf-8")
    _from_device(monkeypatch, str(backup), gui=False)

    proginit.open_and_get_backup_xml_file(state=PrimeItems)

    try:
        assert PrimeItems.program_arguments.file == str(backup)
        assert PrimeItems.file_to_get is not None
    finally:
        PrimeItems.file_to_get.close()


def test_a_device_fetch_that_raises_is_not_caught_here(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_backup_file says why it failed (code 8); what that means in the window is the window's to decide."""
    _from_device(monkeypatch, None, gui=True)

    def fail(state: object) -> str:
        message = "The device did not answer."
        raise MapTaskerError(message, 8)

    monkeypatch.setattr(proginit, "get_backup_file", fail)

    with pytest.raises(MapTaskerError) as raised:
        proginit.open_and_get_backup_xml_file(state=PrimeItems)

    assert raised.value.exit_code == 8


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
    monkeypatch.setattr(proginit.sys, "version", "3.12.1 (main, Jan 1 2026)")
    proginit.check_versions()


def test_an_old_python_is_an_error_with_a_failure_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(proginit.sys, "version", "3.10.4 (main, Jan 1 2026)")

    with pytest.raises(MapTaskerError) as raised:
        proginit.check_versions()

    assert raised.value.exit_code == 1
    assert "3.11" in raised.value.message
