"""How a chain of 'If' conditions is grouped by Tasker's boolean operator precedence.

Tasker ranks its joiners, loosest first: And, Or, And+ ("And2"), Or+ ("Or2").  Or binding
tighter than And is the opposite of most languages, so a chain shown without parentheses
reads as a different condition from the one Tasker evaluates.  The first three cases are
the worked examples from Tasker's own userguide.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from maptasker.src.condjoin import boolean_operators, join_conditions

ABCD = ["A", "B", "C", "D"]


@pytest.mark.parametrize(
    ("operators", "expected"),
    [
        (["Or", "And", "Or"], "(A OR B) AND (C OR D)"),
        (["And", "Or", "And"], "A AND (B OR C) AND D"),
        (["And", "Or", "Or2"], "A AND (B OR (C OR D))"),
        (["And2", "Or", "And2"], "(A AND B) OR (C AND D)"),
        (["Or2", "And2", "Or2"], "(A OR B) AND (C OR D)"),
        (["And", "And", "And"], "A AND B AND C AND D"),
        (["Or", "Xor", "Or"], "A OR B XOR C OR D"),
    ],
)
def test_precedence_groups_the_chain(operators: list[str], expected: str) -> None:
    """Each operator groups by its rank; a single-rank chain has no parentheses."""
    assert join_conditions(ABCD, operators) == expected


def test_one_condition_and_none() -> None:
    """A lone condition is shown as is, and no conditions show nothing."""
    assert join_conditions(["A"], []) == "A"
    assert join_conditions([], []) == ""


def test_joiners_are_read_wherever_tasker_put_them() -> None:
    """<boolN> may sit between its pair or after every Condition; a missing one is And."""
    between = ET.fromstring(  # noqa: S314  (fixture text, built in this file)
        '<ConditionList sr="if"><Condition sr="c0"/><bool0>Or</bool0><Condition sr="c1"/>'
        '<bool1>And2</bool1><Condition sr="c2"/></ConditionList>',
    )
    after = ET.fromstring(  # noqa: S314  (fixture text, built in this file)
        '<ConditionList sr="if"><Condition sr="c0"/><Condition sr="c1"/><Condition sr="c2"/>'
        "<bool0>Or</bool0><bool1>And2</bool1></ConditionList>",
    )
    assert boolean_operators(between, 3) == ["Or", "And2"]
    assert boolean_operators(after, 3) == ["Or", "And2"]
    assert boolean_operators(ET.fromstring('<ConditionList sr="if"/>'), 3) == ["And", "And"]  # noqa: S314
