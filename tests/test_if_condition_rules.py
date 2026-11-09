"""What an If condition's Target and Value may hold.

Tasker takes any text on either side of a condition.  An array is written %name(index): %name(#) is how many
elements it has, %name() all of them joined, %name(2) the second.  A Value is often a regex ('.apk$',
'Success|success'), a list ('1,2') or a phrase ('Third Party').  The editor refused all of these when 'ADB App
Manager' was imported -- 85 conditions in a Task that runs -- and it still has to refuse a variable Tasker would not
accept.
"""

from __future__ import annotations

import pytest
from maptasker.src.edit.taskedit_apply import validate_condition_fields


@pytest.mark.parametrize(
    "target",
    [
        "%match(#)",
        "%ld_selected_index()",
        "%ld_selected_index(1)",
        "%aw_output(2:5)",
        "%app_package(%i)",
        "%WIFII",
        "%par1",
        "%var1 %var2",
        "Plain Text",
        "a.b",
    ],
)
def test_a_target_may_be_an_array_reference_or_any_text(target: str) -> None:
    assert validate_condition_fields(target, "=", "1") == []


@pytest.mark.parametrize(
    "value",
    [
        "=:=",
        ".apk$",
        "true$",
        "Success|success",
        "suspended=true",
        "Enabled System",
        "installed for user:",
        "1,2",
        "5,6,7/6,7/5,7/7/1,7",
        "-u",
        "com.samsung.android.kgclient/android/com.android.systemui",
        "new state: enabled$",
        "%other(#)",
        "%DATE",
    ],
)
def test_a_value_may_be_any_text_a_regex_included(value: str) -> None:
    assert validate_condition_fields("%x_y", "~", value) == []


@pytest.mark.parametrize("field", ["%", "%(#)", "%ab", "%a(#)", "%_abc", "%abc_", "%_abc_(#)", "%%x", "%a b c!"])
def test_a_variable_tasker_would_not_accept_is_still_refused(field: str) -> None:
    assert len(validate_condition_fields(field, "=", "1")) == 1
    assert len(validate_condition_fields("%good", "=", field)) == 1
    assert "valid variable" in validate_condition_fields(field, "=", "1")[0]


def test_a_missing_target_or_value_is_still_refused() -> None:
    assert validate_condition_fields("", "=", "1") == ["The If condition's Target must be set."]
    assert validate_condition_fields("%abc", "=", "") == [
        "The If condition's Value must be set when the Operator is '='."
    ]
    assert validate_condition_fields("%abc", "Is Set", "") == []
