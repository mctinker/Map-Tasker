"""MapTasker Runtime Arguments Unit Tests

ProgramArguments replaced a plain dictionary whose worst habit was agreeing with typos:
program_arguments.get("veiw_limit") handed back None, and program_arguments["ai_analysis"]
= False added a key nothing ever read.  What matters here is that a misspelled name now
fails loudly by every route -- attribute or item, read or write -- while a settings file
from another version, which legitimately carries names this one does not know, still
loads.
"""

from __future__ import annotations

import copy

import pytest
from maptasker.src.initparg import ProgramArguments, initialize_runtime_arguments
from maptasker.src.sysconst import ARGUMENT_NAMES, TRANSIENT_ARGUMENTS


# ##################################################################################### #
# A typo is an error                                                                     #
# ##################################################################################### #
def test_reading_a_misspelled_attribute_fails() -> None:
    """The case that started it: a misspelled read used to come back as None."""
    with pytest.raises(AttributeError):
        _ = ProgramArguments().veiw_limit


def test_writing_a_misspelled_attribute_fails() -> None:
    """Slotted, so a misspelled write cannot quietly create an attribute nothing reads."""
    arguments = ProgramArguments()

    with pytest.raises(AttributeError):
        arguments.ai_analysis = False  # the real one is ai_analyze


@pytest.mark.parametrize("operation", ["read", "write"])
def test_a_misspelled_computed_name_fails(operation) -> None:
    """program_arguments[name], used where the name is computed, is just as strict."""
    arguments = ProgramArguments()

    with pytest.raises(KeyError):
        if operation == "read":
            _ = arguments["veiw_limit"]
        else:
            arguments["veiw_limit"] = 5


def test_there_is_no_forgiving_get() -> None:
    """dict.get's default is what let a typo through; there is deliberately no .get."""
    assert not hasattr(ProgramArguments(), "get")


def test_update_with_a_misspelled_name_changes_nothing() -> None:
    """Every name is checked before any value is set, so a bad update is all or nothing."""
    arguments = ProgramArguments()

    with pytest.raises(KeyError):
        arguments.update(twisty=True, veiw_limit=5)

    assert arguments.twisty is False


# ##################################################################################### #
# Still usable where a dictionary was                                                    #
# ##################################################################################### #
def test_computed_names_read_and_write_the_same_setting() -> None:
    """[name] and .name are two ways to reach one value."""
    arguments = ProgramArguments()

    arguments["view_limit"] = 25

    assert arguments.view_limit == 25
    assert arguments["view_limit"] == 25
    assert "view_limit" in arguments
    assert "veiw_limit" not in arguments


def test_dict_of_it_has_every_setting() -> None:
    """dict(), ** and .items() all see every setting -- the settings file is written this way."""
    arguments = ProgramArguments(font="Menlo")

    assert dict(arguments) == {**arguments} == dict(arguments.items()) == arguments.as_dict()
    assert list(arguments) == list(ProgramArguments.NAMES)
    assert arguments.as_dict()["font"] == "Menlo"


def test_every_saved_setting_is_declared() -> None:
    """Every setting the settings file saves has a field -- otherwise a save or a restore
    would trip over its own name."""
    assert set(ARGUMENT_NAMES) - set(ProgramArguments.NAMES) == set()
    assert set(TRANSIENT_ARGUMENTS) - set(ProgramArguments.NAMES) == set()


def test_each_one_has_its_own_lists() -> None:
    """A mutable default shared between instances would carry one run's choices into the next."""
    first, second = ProgramArguments(), ProgramArguments()
    first.health_check_skip.append("unused_variables")

    assert second.health_check_skip == []
    assert initialize_runtime_arguments().health_check_skip == []


def test_a_deep_copy_is_independent() -> None:
    """PrimeItemsReset hands out deep copies of the defaults; they must not share state."""
    original = ProgramArguments()
    duplicate = copy.deepcopy(original)
    duplicate.health_check_skip.append("unused_variables")
    duplicate.view_limit = 1

    assert original == ProgramArguments()


def test_the_api_key_stays_out_of_repr() -> None:
    """repr() is what ends up in a log line or a traceback."""
    assert "sk-secret" not in repr(ProgramArguments(ai_apikey="sk-secret"))


# ##################################################################################### #
# A settings file from another version still loads                                       #
# ##################################################################################### #
def test_restore_takes_what_it_knows_and_reports_the_rest() -> None:
    """An older settings file carries names that no longer exist; they are skipped, not fatal."""
    arguments = ProgramArguments()

    ignored = arguments.restore({"twisty": True, "setting_from_an_old_version": 1, "msg": "corrupt"})

    assert arguments.twisty is True
    assert ignored == ["setting_from_an_old_version", "msg"]


def test_from_dict_defaults_what_is_missing() -> None:
    """A settings file from before a setting existed gives it its default."""
    arguments = ProgramArguments.from_dict({"font": "Menlo"})

    assert arguments.font == "Menlo"
    assert arguments.view_limit == ProgramArguments().view_limit
