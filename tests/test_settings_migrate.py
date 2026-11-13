"""The settings file's history: every shape it has ever had, and what reading each must give (settingsmigrate).

A settings file outlives the version of MapTasker that wrote it.  Each migration in settingsmigrate.MIGRATIONS exists
because some old file would otherwise come back wrong -- Tamil under a spelling nothing recognises, a Gemini model
Google answers with a 404, a service that is no longer there -- so each has, below, one such file as it was written
and the settings it has to come back as.  A migration with no entry here fails `test_every_migration_has_a_file`.
"""

from __future__ import annotations

import copy
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import tomli_w
from hypothesis import given
from maptasker.src.core import getputer, settingsmigrate
from maptasker.src.core.colrmode import set_color_mode
from maptasker.src.core.initparg import initialize_runtime_arguments
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.core.settingsmigrate import MIGRATIONS, SETTINGS_VERSION, VERSION_KEY

from tests.fuzzing import files_of_any_age, fuzz
from tests.test_fuzz_backup import a_scratch_run, prime_a_run


@dataclass(frozen=True)
class OldFile:
    """A settings file as an older MapTasker wrote it, and what it has to come back as."""

    written: str  # the file, TOML text; no settings_version, which did not exist yet
    comes_back_as: dict[str, Any]  # these settings, after the read
    untouched: dict[str, Any]  # and these, which the migration has no business changing


HISTORICAL_SHAPES: dict[str, OldFile] = {
    "tamil-spelling": OldFile(
        written="""
[program_arguments]
appearance_mode = "dark"
bold = true
indent = 6
language = "Tamali"
""",
        comes_back_as={"language": "Tamil"},
        untouched={"appearance_mode": "dark", "bold": True, "indent": 6},
    ),
    "renamed-ai-models": OldFile(
        written="""
[program_arguments]
ai_name = "Gemini"
ai_model = "gemini-3.1-flash_lite"
language = "English"
""",
        comes_back_as={"ai_model": "gemini-3.1-flash-lite"},
        untouched={"ai_name": "Gemini", "language": "English"},
    ),
    "retired-ai-selection": OldFile(
        written="""
[program_arguments]
ai_name = "DeepSeek"
ai_model = "deepseek-chat"
ai_analyze = false
""",
        comes_back_as={"ai_name": "", "ai_model": ""},
        untouched={"ai_analyze": False},
    ),
}


def _read(tmp_path: Path, text: str, state: Any = PrimeItems) -> dict[str, Any]:
    """The [program_arguments] a read of this file gives back."""
    path = tmp_path / "MapTasker_Settings.toml"
    path.write_text(text, encoding="utf-8")
    prime_a_run()
    arguments, _ = getputer.read_toml_file(str(path), state)
    return arguments


# ##################################################################################
# The table itself
# ##################################################################################
def test_every_migration_has_a_file() -> None:
    """Add a migration, add the old file it is for: this is what makes the history something that is tested."""
    assert {migration.name for migration in MIGRATIONS} == set(HISTORICAL_SHAPES)


def test_the_versions_are_consecutive_from_one_and_every_migration_says_what_it_is_for() -> None:
    assert [migration.version for migration in MIGRATIONS] == list(range(1, len(MIGRATIONS) + 1))
    assert SETTINGS_VERSION == len(MIGRATIONS)
    assert all(migration.name and migration.shape for migration in MIGRATIONS)
    assert len({migration.name for migration in MIGRATIONS}) == len(MIGRATIONS)


# ##################################################################################
# Each historical shape
# ##################################################################################
@pytest.mark.parametrize("name", sorted(HISTORICAL_SHAPES))
def test_each_old_file_comes_back_in_the_current_shape(tmp_path: Path, name: str) -> None:
    old = HISTORICAL_SHAPES[name]
    assert VERSION_KEY not in tomllib.loads(old.written), "an old file has no version"

    arguments = _read(tmp_path, old.written)

    for setting, value in old.comes_back_as.items():
        assert arguments[setting] == value, f"{name}: {setting}"
    for setting, value in old.untouched.items():
        assert arguments[setting] == value, f"{name}: {setting} was changed"


@pytest.mark.parametrize("name", sorted(HISTORICAL_SHAPES))
def test_each_old_file_is_migrated_by_that_migration_and_stamped(name: str) -> None:
    document = tomllib.loads(HISTORICAL_SHAPES[name].written)

    notes = settingsmigrate.migrate(document)

    assert [note.split(":")[0] for note in notes] == [name], "exactly the migration this file is for ran"
    assert document[VERSION_KEY] == SETTINGS_VERSION


@pytest.mark.parametrize("name", sorted(HISTORICAL_SHAPES))
def test_migrating_a_second_time_changes_nothing(name: str) -> None:
    document = tomllib.loads(HISTORICAL_SHAPES[name].written)
    settingsmigrate.migrate(document)
    migrated = copy.deepcopy(document)

    assert settingsmigrate.migrate(document) == []
    assert document == migrated


def test_a_file_that_is_every_old_shape_at_once_is_carried_over_by_all_of_them(tmp_path: Path) -> None:
    arguments = _read(
        tmp_path,
        """
[program_arguments]
language = "Tamali"
ai_name = "Gemini"
ai_model = "gemini-3.1-flash_lite"
""",
    )
    assert (arguments["language"], arguments["ai_model"]) == ("Tamil", "gemini-3.1-flash-lite")

    arguments = _read(
        tmp_path,
        """
[program_arguments]
language = "Tamali"
ai_name = "DeepSeek"
ai_model = "deepseek-chat"
""",
    )
    assert (arguments["language"], arguments["ai_name"], arguments["ai_model"]) == ("Tamil", "", "")


# ##################################################################################
# Versions
# ##################################################################################
def test_only_the_migrations_a_file_has_not_been_through_are_run() -> None:
    """A file at version 2 has had the Tamil and model fixes; the retired service is the one it still needs."""
    document = {VERSION_KEY: 2, "program_arguments": {"language": "Tamali", "ai_name": "DeepSeek", "ai_model": ""}}

    notes = settingsmigrate.migrate(document)

    assert [note.split(":")[0] for note in notes] == ["retired-ai-selection"]
    assert document["program_arguments"]["language"] == "Tamali", "version 1's job, already done as far as it says"
    assert document[VERSION_KEY] == SETTINGS_VERSION


def test_a_file_already_at_the_current_version_is_left_alone() -> None:
    document = {VERSION_KEY: SETTINGS_VERSION, "program_arguments": {"language": "Tamali"}}

    assert settingsmigrate.migrate(document) == []
    assert document["program_arguments"] == {"language": "Tamali"}


def test_a_file_from_a_newer_maptasker_is_not_rewritten() -> None:
    document = {VERSION_KEY: SETTINGS_VERSION + 5, "program_arguments": {"language": "Tamali"}}

    assert settingsmigrate.migrate(document) == []
    assert document[VERSION_KEY] == SETTINGS_VERSION + 5, "it keeps its own version"
    assert document["program_arguments"] == {"language": "Tamali"}


@pytest.mark.parametrize("version", ["two", -1, 2.5, True, None, [], {}])
def test_a_version_that_is_not_one_counts_as_no_version_and_the_file_is_migrated(version: object) -> None:
    document = {VERSION_KEY: version, "program_arguments": {"language": "Tamali"}}

    settingsmigrate.migrate(document)

    assert document["program_arguments"]["language"] == "Tamil"
    assert document[VERSION_KEY] == SETTINGS_VERSION


@pytest.mark.parametrize("document", [{}, {"program_arguments": "not a table"}, {"program_arguments": None}])
def test_a_file_with_no_program_arguments_table_is_migrated_without_complaint(document: dict[str, Any]) -> None:
    assert settingsmigrate.migrate(document) == []
    assert document[VERSION_KEY] == SETTINGS_VERSION


# ##################################################################################
# Saving, and what is not a migration
# ##################################################################################
def test_a_save_stamps_the_file_with_the_current_version_and_reading_it_back_changes_nothing(tmp_path: Path) -> None:
    with a_scratch_run(b"") as path:
        prime_a_run()
        target = path.with_name("MapTasker_Settings.toml")
        arguments = initialize_runtime_arguments().as_dict()
        getputer.save_arguments(arguments, dict(set_color_mode("dark")), str(target), PrimeItems)

        written = tomllib.loads(target.read_text(encoding="utf-8"))
        assert written[VERSION_KEY] == SETTINGS_VERSION
        assert settingsmigrate.migrate(written) == []


def test_a_value_of_the_wrong_kind_is_repaired_in_a_file_of_any_version(tmp_path: Path) -> None:
    """That is damage, not history, so a file saved yesterday gets it too."""
    for version in ("", f"{VERSION_KEY} = {SETTINGS_VERSION}\n"):
        arguments = _read(tmp_path, f'{version}\n[program_arguments]\nindent = "wide"\nbold = true\n')

        assert "indent" not in arguments
        assert arguments["bold"] is True


def test_the_migrations_and_the_repair_are_the_only_things_that_change_a_file_on_reading(tmp_path: Path) -> None:
    arguments = _read(tmp_path, "[program_arguments]\nbold = true\nindent = 6\nsome_future_setting = 'x'\n")

    assert (arguments["bold"], arguments["indent"], arguments["some_future_setting"]) == (True, 6, "x")


# ##################################################################################
# Properties
# ##################################################################################
@fuzz(200)
@given(document=files_of_any_age())
def test_a_file_of_any_age_comes_back_with_no_historical_value_in_it(document: dict[str, Any]) -> None:
    """The migrations leave nothing old behind -- for an unversioned file, or one stopped at any version of the history."""
    version = settingsmigrate.file_version(document)
    migrated = copy.deepcopy(document)

    settingsmigrate.migrate(migrated)

    arguments = migrated["program_arguments"]
    assert migrated[VERSION_KEY] == SETTINGS_VERSION
    if version < 1:
        assert arguments.get("language") != "Tamali"
    if version < 2:
        assert arguments.get("ai_model") != "gemini-3.1-flash_lite"
    if version < 3:
        assert arguments.get("ai_name") != "DeepSeek"
        assert not str(arguments.get("ai_model") or "").lower().startswith("deepseek")


@fuzz(200)
@given(document=files_of_any_age())
def test_migrating_is_idempotent_for_a_file_of_any_age(document: dict[str, Any]) -> None:
    once = copy.deepcopy(document)
    settingsmigrate.migrate(once)
    twice = copy.deepcopy(once)

    assert settingsmigrate.migrate(twice) == []
    assert twice == once


@fuzz(100)
@given(document=files_of_any_age())
def test_a_file_of_any_age_is_read_whole_through_the_real_reader(document: dict[str, Any]) -> None:
    """Through read_toml_file itself, as a file on disk, as every other settings test is."""
    with a_scratch_run(b"") as path:
        prime_a_run()
        target = path.with_name("MapTasker_Settings.toml")
        target.write_text(tomli_w.dumps(document), encoding="utf-8")
        arguments, colors = getputer.read_toml_file(str(target), PrimeItems)

    assert isinstance(arguments, dict)
    assert isinstance(colors, dict)
    assert arguments.get("language") != "Tamali" or settingsmigrate.file_version(document) >= 1
