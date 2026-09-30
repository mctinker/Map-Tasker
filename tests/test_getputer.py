"""Settings file (getputer) Unit Tests

MapTasker saves its settings to MapTasker_Settings.toml in the working directory.  Older
versions also pickled a second file, '.MapTasker_Settings.pkl', which never held anything --
and loading a pickle runs whatever code has been put in it.  It is no longer written or read,
and saving settings deletes a leftover one without opening it.  Every test runs in a
temporary working directory, which is where the settings files are written.
"""

from __future__ import annotations

import os
import pickle
from pathlib import Path

import pytest
from maptasker.src import getputer
from maptasker.src.colrmode import set_color_mode
from maptasker.src.initparg import ProgramArguments, initialize_runtime_arguments
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import (
    ARGUMENT_NAMES,
    ARGUMENTS_FILE,
    GEMINI_MODELS,
    LEGACY_SYSTEM_SETTINGS_FILE,
)


@pytest.fixture
def program_arguments(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ProgramArguments:
    """A fresh run's arguments, in a working directory of this test's own."""
    monkeypatch.chdir(tmp_path)
    arguments = initialize_runtime_arguments()
    monkeypatch.setattr(PrimeItems, "program_arguments", arguments)
    return arguments


def test_saving_settings_writes_the_toml_file_and_nothing_else(program_arguments: ProgramArguments, tmp_path: Path) -> None:
    """There is one settings file now."""
    getputer.save_restore_args(program_arguments, set_color_mode("Dark"), to_save=True)

    assert sorted(path.name for path in tmp_path.glob("*Settings*")) == [ARGUMENTS_FILE]


def test_settings_come_back_from_the_toml_file_alone(program_arguments: ProgramArguments) -> None:
    """Every saved argument and color is restored with no second file to read."""
    colors = set_color_mode("Dark")
    getputer.save_restore_args(program_arguments, colors, to_save=True)

    restored_arguments, restored_colors = getputer.save_restore_args({}, {}, to_save=False)

    assert {name: restored_arguments[name] for name in ARGUMENT_NAMES} == {
        name: program_arguments[name] for name in ARGUMENT_NAMES
    }
    assert restored_colors == colors


class _RunsCodeWhenLoaded:
    """Pickles as a call to os.mkdir -- which pickle.load would make."""

    def __init__(self, target: Path) -> None:
        self.target = target

    def __reduce__(self) -> tuple:
        return (os.mkdir, (str(self.target),))


def test_an_old_system_settings_pickle_is_never_loaded_and_is_deleted_on_save(
    program_arguments: ProgramArguments,
    tmp_path: Path,
) -> None:
    """Restoring ignores the old pickle; saving deletes it; nothing in it ever runs."""
    marker = tmp_path / "code-ran"
    legacy_file = Path(LEGACY_SYSTEM_SETTINGS_FILE)
    legacy_file.write_bytes(pickle.dumps({"payload": _RunsCodeWhenLoaded(marker)}))

    getputer.save_restore_args({}, {}, to_save=False)
    assert legacy_file.exists()

    getputer.save_restore_args(program_arguments, set_color_mode("Dark"), to_save=True)
    assert not legacy_file.exists()
    assert not marker.exists()


def test_a_language_saved_under_the_old_tamil_spelling_is_carried_over(program_arguments: ProgramArguments) -> None:
    """Tamil was listed as 'Tamali', and the language is saved by its name.  A settings file from
    before the fix has to come back as Tamil, not as a name nothing recognizes."""
    program_arguments.language = "Tamali"
    getputer.save_restore_args(program_arguments, set_color_mode("Dark"), to_save=True)

    restored_arguments, _ = getputer.save_restore_args({}, {}, to_save=False)

    assert restored_arguments["language"] == "Tamil"
    assert restored_arguments["language"] in PrimeItems.languages


def test_a_gemini_model_saved_under_the_wrong_spelling_is_carried_over(program_arguments: ProgramArguments) -> None:
    """'gemini-3.1-flash_lite' was offered for a while; Google's name has a hyphen, and answers the
    underscore with 404 NOT_FOUND.  A settings file saved with it has to come back as the real name."""
    program_arguments.ai_model = "gemini-3.1-flash_lite"
    getputer.save_restore_args(program_arguments, set_color_mode("Dark"), to_save=True)

    restored_arguments, _ = getputer.save_restore_args({}, {}, to_save=False)

    assert restored_arguments["ai_model"] == "gemini-3.1-flash-lite"
    assert restored_arguments["ai_model"] in GEMINI_MODELS


def test_a_model_that_was_never_misspelled_is_left_alone(program_arguments: ProgramArguments) -> None:
    program_arguments.ai_model = "gemini-3.5-flash-lite"
    getputer.save_restore_args(program_arguments, set_color_mode("Dark"), to_save=True)

    restored_arguments, _ = getputer.save_restore_args({}, {}, to_save=False)

    assert restored_arguments["ai_model"] == "gemini-3.5-flash-lite"


def test_no_gemini_model_is_listed_with_an_underscore() -> None:
    """Google's model names are hyphenated throughout; an underscore is a typo that 404s."""
    assert not [model for model in GEMINI_MODELS if "_" in model]
