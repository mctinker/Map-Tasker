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
from maptasker.src.core import getputer
from maptasker.src.core.colrmode import color_overrides, effective_colors, set_color_mode
from maptasker.src.core.initparg import ProgramArguments, initialize_runtime_arguments
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.core.sysconst import (
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


def test_saving_settings_writes_the_toml_file_and_nothing_else(
    program_arguments: ProgramArguments, tmp_path: Path
) -> None:
    """There is one settings file now."""
    getputer.save_restore_args(program_arguments, set_color_mode("Dark"), to_save=True, state=PrimeItems)

    assert sorted(path.name for path in tmp_path.glob("*Settings*")) == [ARGUMENTS_FILE]


def test_settings_come_back_from_the_toml_file_alone(program_arguments: ProgramArguments) -> None:
    """Every saved argument and color is restored with no second file to read."""
    colors = set_color_mode("Dark")
    getputer.save_restore_args(program_arguments, colors, to_save=True, state=PrimeItems)

    restored_arguments, restored_colors = getputer.save_restore_args({}, {}, to_save=False, state=PrimeItems)

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

    getputer.save_restore_args({}, {}, to_save=False, state=PrimeItems)
    assert legacy_file.exists()

    getputer.save_restore_args(program_arguments, set_color_mode("Dark"), to_save=True, state=PrimeItems)
    assert not legacy_file.exists()
    assert not marker.exists()


def test_a_settings_file_with_no_debug_setting_still_comes_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The missing key was read as a missing [program_arguments] table, and every setting in the file was dropped."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ARGUMENTS_FILE).write_text("[program_arguments]\nbold = true\nindent = 6\n", encoding="utf-8")

    restored, _ = getputer.save_restore_args({}, {}, to_save=False, state=PrimeItems)

    assert (restored["bold"], restored["indent"]) == (True, 6)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("indent", "wide"),
        ("bold", "yes"),
        ("display_detail_level", "all"),
        ("view_limit", 3.5),
        ("language", 4),
        ("indent", True),
    ],
)
def test_a_saved_value_of_the_wrong_kind_is_dropped_and_the_rest_kept(name: str, value: object) -> None:
    arguments = {"underline": True, name: value}

    dropped = getputer.drop_values_of_the_wrong_kind(arguments)

    assert dropped == [name]
    assert arguments == {"underline": True}


def test_a_whole_number_written_as_text_is_kept() -> None:
    """Older versions saved display_detail_level as "5"."""
    arguments = {"display_detail_level": "5", "indent": -1, "some_future_setting": object()}

    assert getputer.drop_values_of_the_wrong_kind(arguments) == []
    assert arguments["display_detail_level"] == "5"


def test_a_language_saved_under_the_old_tamil_spelling_is_carried_over(program_arguments: ProgramArguments) -> None:
    """Tamil was listed as 'Tamali', and the language is saved by its name.  A settings file from
    before the fix has to come back as Tamil, not as a name nothing recognizes."""
    program_arguments.language = "Tamali"
    getputer.save_restore_args(program_arguments, set_color_mode("Dark"), to_save=True, state=PrimeItems)

    restored_arguments, _ = getputer.save_restore_args({}, {}, to_save=False, state=PrimeItems)

    assert restored_arguments["language"] == "Tamil"
    assert restored_arguments["language"] in PrimeItems.languages


def test_a_gemini_model_saved_under_the_wrong_spelling_is_carried_over(program_arguments: ProgramArguments) -> None:
    """'gemini-3.1-flash_lite' was offered for a while; Google's name has a hyphen, and answers the
    underscore with 404 NOT_FOUND.  A settings file saved with it has to come back as the real name."""
    program_arguments.ai_model = "gemini-3.1-flash_lite"
    getputer.save_restore_args(program_arguments, set_color_mode("Dark"), to_save=True, state=PrimeItems)

    restored_arguments, _ = getputer.save_restore_args({}, {}, to_save=False, state=PrimeItems)

    assert restored_arguments["ai_model"] == "gemini-3.1-flash-lite"
    assert restored_arguments["ai_model"] in GEMINI_MODELS


def test_a_model_that_was_never_misspelled_is_left_alone(program_arguments: ProgramArguments) -> None:
    program_arguments.ai_model = "gemini-3.5-flash-lite"
    getputer.save_restore_args(program_arguments, set_color_mode("Dark"), to_save=True, state=PrimeItems)

    restored_arguments, _ = getputer.save_restore_args({}, {}, to_save=False, state=PrimeItems)

    assert restored_arguments["ai_model"] == "gemini-3.5-flash-lite"


def test_no_gemini_model_is_listed_with_an_underscore() -> None:
    """Google's model names are hyphenated throughout; an underscore is a typo that 404s."""
    assert not [model for model in GEMINI_MODELS if "_" in model]


@pytest.mark.parametrize("none_in_the_users_language", ["None", "Keine"])
def test_nothing_selected_is_saved_as_nothing_in_any_language(
    program_arguments: ProgramArguments, monkeypatch: pytest.MonkeyPatch, none_in_the_users_language: str
) -> None:
    """ "None" in the pulldown means no selection, and is saved as empty so the next run does not go
    looking for a Project called "Keine".  The check used to translate the result of a comparison
    rather than compare with the translation, so only the English word was ever recognised."""
    monkeypatch.setattr(getputer, "translate_string", lambda text: {"None": "Keine"}.get(text, text))
    monkeypatch.setattr(program_arguments, "language", "German")
    arguments = program_arguments.as_dict()
    arguments["single_project_name"] = none_in_the_users_language

    getputer.save_restore_args(arguments, set_color_mode("Dark"), to_save=True, state=PrimeItems)
    restored, _ = getputer.save_restore_args({}, {}, to_save=False, state=PrimeItems)

    assert restored["single_project_name"] == ""


# ##################################################################################
# One meaning for [colors_to_use]: the colours that differ from the appearance mode's own palette
# ##################################################################################
def _saved_colors(tmp_path: Path) -> dict[str, str]:
    import tomllib

    return tomllib.loads((tmp_path / ARGUMENTS_FILE).read_text(encoding="utf-8"))["colors_to_use"]


def test_the_file_keeps_only_the_colours_that_differ_from_the_modes_palette(
    program_arguments: ProgramArguments, tmp_path: Path
) -> None:
    program_arguments.appearance_mode = "dark"
    colors = {**set_color_mode("dark"), "project_color": "Red"}

    getputer.save_restore_args(program_arguments, colors, to_save=True, state=PrimeItems)

    assert _saved_colors(tmp_path) == {"project_color": "Red"}


def test_every_way_of_holding_the_same_colours_saves_the_same_file(
    program_arguments: ProgramArguments, tmp_path: Path
) -> None:
    """The whole palette (an exit save), only what the user changed (the Save button) and a palette with extras
    in it all come to the same colours, so they write the same file."""
    program_arguments.appearance_mode = "light"
    changed = {"task_color": "Blue", "project_color": "Red"}
    holdings = [{**set_color_mode("light"), **changed}, dict(changed), {**changed, "heading_color": "DarkSlateGray"}]

    written = []
    for held in holdings:
        getputer.save_restore_args(program_arguments, held, to_save=True, state=PrimeItems)
        written.append(_saved_colors(tmp_path))

    assert written[0] == written[1] == written[2] == changed


def test_a_file_saved_with_no_changed_colour_has_an_empty_table_and_restores_the_palette(
    program_arguments: ProgramArguments, tmp_path: Path
) -> None:
    program_arguments.appearance_mode = "dark"

    getputer.save_restore_args(program_arguments, {}, to_save=True, state=PrimeItems)
    _, restored = getputer.save_restore_args({}, {}, to_save=False, state=PrimeItems)

    assert _saved_colors(tmp_path) == {}
    assert restored == set_color_mode("dark")


def test_the_colours_restored_are_the_palette_of_the_saved_mode_with_the_changes_on_top(
    program_arguments: ProgramArguments,
) -> None:
    program_arguments.appearance_mode = "light"
    getputer.save_restore_args(program_arguments, {"project_color": "Red"}, to_save=True, state=PrimeItems)

    _, restored = getputer.save_restore_args({}, {}, to_save=False, state=PrimeItems)

    assert restored == {**set_color_mode("light"), "project_color": "Red"}


def test_a_palette_saved_by_an_older_version_still_reads_as_the_same_colours(
    program_arguments: ProgramArguments, tmp_path: Path
) -> None:
    """Older versions wrote the whole palette: to this version that is a long list of colours that are changes."""
    palette = {**set_color_mode("dark"), "task_color": "Blue"}
    import tomli_w

    (tmp_path / ARGUMENTS_FILE).write_bytes(
        tomli_w.dumps({"program_arguments": {"appearance_mode": "dark"}, "colors_to_use": palette}).encode("utf-8")
    )

    _, restored = getputer.save_restore_args({}, {}, to_save=False, state=PrimeItems)

    assert restored == palette


def test_something_in_the_colour_table_that_is_not_a_colour_is_not_kept() -> None:
    spoiled = {"project_color": "Red", "task_color": 7, "msg": "corrupt", "scene_color": "", 3: "Blue"}

    assert color_overrides(spoiled, "light") == {"project_color": "Red"}
    assert effective_colors(spoiled, "light") == {**set_color_mode("light"), "project_color": "Red"}
    assert effective_colors("not a table", "light") == set_color_mode("light")
    assert effective_colors(None, 7) == set_color_mode("system")


def test_the_chosen_background_is_only_a_background_that_differs_from_the_palettes() -> None:
    from maptasker.src.core.colrmode import chosen_background, set_color_mode

    assert chosen_background(set_color_mode("light"), "light") == ""
    assert chosen_background({**set_color_mode("light"), "background_color": "Red"}, "light") == "Red"
    assert chosen_background({"background_color": "Lavender"}, "light") == "", "Lavender is light mode's own"
    assert chosen_background({"background_color": "Lavender"}, "dark") == "Lavender", "but a choice in dark mode"
    assert chosen_background({"background_color": "abc123"}, "light") == "#abc123"
    assert chosen_background(None, "light") == chosen_background({}, None) == ""
