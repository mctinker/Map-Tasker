"""Settings file migrations: what an older file's shape is carried over to, in one place.

The settings file (MapTasker_Settings.toml) outlives the program that wrote it.  A file saved by last year's
MapTasker is read by this year's, and in between a language was respelled, a model was found to have been listed
under the wrong name, and a service was dropped.  Each of those was handled where the file is read, one `if` after
another, with nothing to say which files they were for or whether a file had been through them.

A file now says what shape it is.  It carries a top-level ``settings_version`` (written by every save); a file with
none is from before there was one and counts as version 0.  MIGRATIONS is the whole history, oldest first: each entry
brings a file up to its own version, and `migrate` runs the ones a file has not been through.  A file at or past
SETTINGS_VERSION is left alone -- one from a newer MapTasker is not ours to rewrite.

To change what the file means:

  1. append a Migration to MIGRATIONS, with the next version number, and describe the shape it recognises;
  2. add that shape to HISTORICAL_SHAPES in tests/test_settings_migrate.py: an old file as it was written, and what
     reading it must give.  A test fails until each migration has one.

A migration changes the document in place and returns a line per change, for the log.  It must be safe to run on a
file that is already in the new shape, because a file with no version may have been migrated by hand, and a file read
twice before it is saved is migrated twice.

Separate from all of that is `repair`, which runs on every file whatever its version.  A value of the wrong kind
("indent = 'wide'") is not a shape the file once had; it is what a hand edit or a crash leaves, and can happen to a
file written yesterday.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from maptasker.src.core.initparg import initialize_runtime_arguments
from maptasker.src.core.sysconst import RENAMED_AI_MODELS, RETIRED_AI_MODEL_PREFIXES, RETIRED_AI_NAMES, logger

if TYPE_CHECKING:
    from collections.abc import Callable

# A settings table as TOML gives it back (or as the GUI hands it over): names to values of any kind.
Settings = dict[str, Any]

VERSION_KEY = "settings_version"


@dataclass(frozen=True)
class Migration:
    """One step in the history of the settings file."""

    version: int  # the settings_version of a file once this has been applied
    name: str  # what it is called in the log and in the tests
    shape: str  # the old shape of file it recognises, in a sentence
    apply: Callable[[Settings], list[str]]  # changes the whole document in place; returns what it changed


def _arguments(settings: Settings) -> Settings | None:
    """The [program_arguments] table of a document, or None when it has none (or is not a table)."""
    table = settings.get("program_arguments")
    return cast("Settings", table) if isinstance(table, dict) else None


# --- The migrations ----------------------------------------------------------------------
def _tamil_spelling(settings: Settings) -> list[str]:
    """Tamil was listed as 'Tamali', and the language is saved by its name: carry it over instead of falling
    back to English."""
    arguments = _arguments(settings)
    if arguments is None or arguments.get("language") != "Tamali":
        return []
    arguments["language"] = "Tamil"
    return ["language 'Tamali' is now 'Tamil'"]


def _renamed_ai_models(settings: Settings) -> list[str]:
    """A model saved under a spelling that was listed wrongly (Google answers such a name with '404 NOT_FOUND') is
    carried over to its real name."""
    arguments = _arguments(settings)
    model = arguments.get("ai_model") if arguments is not None else None
    if arguments is None or not isinstance(model, str) or model not in RENAMED_AI_MODELS:
        return []
    arguments["ai_model"] = RENAMED_AI_MODELS[model]
    return [f"ai_model {model!r} is now {RENAMED_AI_MODELS[model]!r}"]


def drop_unsupported_ai_selection(arguments: Settings) -> bool:
    """Clear the saved AI service and model if they are ones MapTasker can no longer run.

    A settings file saved while one was selected would otherwise bring it back on the Analyze tab, where nothing
    could be done with it: the model is in no list, and no key is kept for it.  Cleared, the tab comes up as it
    does when no model has ever been chosen.

    Args:
        arguments (dict): the [program_arguments] table just read, changed in place.

    Returns:
        bool: True if a selection was cleared.
    """
    model = str(arguments.get("ai_model") or "").lower()
    if arguments.get("ai_name") not in RETIRED_AI_NAMES and not model.startswith(RETIRED_AI_MODEL_PREFIXES):
        return False
    logger.info(
        f"The saved AI selection ({arguments.get('ai_name')!r}, {arguments.get('ai_model')!r}) is "
        "no longer supported, so it has been cleared.",
    )
    arguments["ai_name"] = ""
    arguments["ai_model"] = ""
    return True


def _retired_ai_selection(settings: Settings) -> list[str]:
    """A saved choice of an AI service MapTasker no longer supports is cleared, since nothing it names can run."""
    arguments = _arguments(settings)
    if arguments is None or not drop_unsupported_ai_selection(arguments):
        return []
    return ["the saved AI service and model are no longer supported and were cleared"]


# The history, oldest first.  Versions are consecutive from 1; never reorder or edit one that has shipped.
MIGRATIONS: tuple[Migration, ...] = (
    Migration(1, "tamil-spelling", "language = 'Tamali', the way Tamil was once listed", _tamil_spelling),
    Migration(
        2, "renamed-ai-models", "ai_model = 'gemini-3.1-flash_lite', a name Google answers with 404", _renamed_ai_models
    ),
    Migration(
        3,
        "retired-ai-selection",
        "ai_name = 'DeepSeek' (or a deepseek model), a service since dropped",
        _retired_ai_selection,
    ),
)

SETTINGS_VERSION = MIGRATIONS[-1].version


# --- Running them ------------------------------------------------------------------------
def file_version(settings: Settings) -> int:
    """The version a document says it is: 0 when it says nothing, or says something that is not a version."""
    version = settings.get(VERSION_KEY)
    if isinstance(version, bool) or not isinstance(version, int) or version < 0:
        return 0
    return version


def migrate(settings: Settings) -> list[str]:
    """Bring a document read from the settings file up to SETTINGS_VERSION, in place.

    Runs each migration the document has not been through, oldest first, and stamps it with the current version.
    A document from a newer MapTasker (a version past ours) is left exactly as it is.

    Returns:
        list[str]: what was changed, a line for each.
    """
    version = file_version(settings)
    if version > SETTINGS_VERSION:
        logger.info(f"The settings file is version {version}, newer than this MapTasker's {SETTINGS_VERSION}.")
        return []
    notes: list[str] = []
    for migration in MIGRATIONS:
        if migration.version <= version:
            continue
        for note in migration.apply(settings):
            logger.info(
                f"Settings migration {migration.name} (to version {migration.version}, for a file with "
                f"{migration.shape}): {note}."
            )
            notes.append(f"{migration.name}: {note}")
    settings[VERSION_KEY] = SETTINGS_VERSION
    return notes


def drop_values_of_the_wrong_kind(arguments: Settings) -> list[str]:
    """Take out of the [program_arguments] table just read any value that is not the kind its setting holds.

    A hand-edited or damaged file ("indent = 'wide'", "bold = 'yes'") hands the window a value that its controls
    and every later int() cannot use, and the window then fails to open.  Dropped, the setting stays at the run's
    own value, and the rest of the file is restored as written.

    A whole number may be written as text (an older version saved some of them that way), and is kept.

    Args:
        arguments (dict): the table, changed in place.

    Returns:
        list[str]: the names that were dropped.
    """
    defaults = initialize_runtime_arguments()
    dropped: list[str] = []
    for name in list(arguments):
        if name not in defaults:
            continue  # An unknown setting: restore() says so, and ignores it.
        default, value = defaults[name], arguments[name]
        if isinstance(default, bool):
            fits = isinstance(value, bool)
        elif isinstance(default, int):
            fits = (isinstance(value, int) and not isinstance(value, bool)) or (
                isinstance(value, str) and value.strip().lstrip("-").isdigit()
            )
        elif isinstance(default, str):
            fits = isinstance(value, str)
        else:
            fits = True
        if not fits:
            logger.warning(f"Ignoring the saved setting {name} = {value!r}: it should be {type(default).__name__}.")
            del arguments[name]
            dropped.append(name)
    return dropped


def repair(settings: Settings) -> list[str]:
    """What is wrong with a file whatever its age: values of the wrong kind are dropped, in place.

    Returns:
        list[str]: the names that were dropped.
    """
    arguments = _arguments(settings)
    return drop_values_of_the_wrong_kind(arguments) if arguments is not None else []
