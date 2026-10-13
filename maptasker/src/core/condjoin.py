"""Join a chain of Tasker 'If' conditions the way Tasker groups them."""

#! /usr/bin/env python3

#                                                                                      #
# condjoin: group chained If conditions by Tasker's boolean operator precedence       #
#                                                                                      #
from __future__ import annotations

# Tasker's boolean operators from lowest to highest precedence (Tasker userguide, Action
# Edit, "If Conditions"): And, Or, And+ and Or+, the last two stored as "And2"/"Or2".  So
# "A | B & C | D" is "(A | B) & (C | D)" -- Or binds tighter than And, unlike most
# languages.  The guide does not rank Xor; it is taken to sit with Or.
_PRECEDENCE = {"and": 0, "or": 1, "xor": 1, "and2": 2, "or2": 3}
# How each operator is shown; the parentheses carry the precedence, so And2/Or2 read plainly.
_DISPLAY = {"and": "AND", "or": "OR", "xor": "XOR", "and2": "AND", "or2": "OR"}


def boolean_operators(condition_list: object, condition_count: int) -> list[str]:
    """The joiners between a <ConditionList>'s Conditions, in order: one fewer than the Conditions.

    <boolN> joins Condition N to Condition N+1.  Tasker writes it either between the pair or,
    in newer backups, after the last Condition, so the joiners are read in document order
    rather than in passing.  A missing or empty joiner is Tasker's default, And.
    """
    joiners = [(child.text or "And").strip() or "And" for child in condition_list if "bool" in child.tag]
    joiners = joiners[: max(condition_count - 1, 0)]
    return joiners + ["And"] * (max(condition_count - 1, 0) - len(joiners))


def join_conditions(conditions: list[str], operators: list[str]) -> str:
    """The conditions joined by their operators, parenthesized wherever precedence groups them.

    'operators' holds Tasker's own values ("And", "Or", "Xor", "And2", "Or2"), one between each
    pair of conditions.  A chain that uses a single operator throughout needs no parentheses.
    """
    if not conditions:
        return ""
    return _group(conditions, [operator.strip().lower() for operator in operators[: len(conditions) - 1]])


def _group(conditions: list[str], operators: list[str]) -> str:
    """Split at the loosest-binding operators present, and group what lies between them."""
    if not operators:
        return conditions[0]
    loosest = min(_PRECEDENCE.get(operator, 0) for operator in operators)

    text = ""
    start = 0
    for position, operator in enumerate([*operators, None]):
        if operator is not None and _PRECEDENCE.get(operator, 0) != loosest:
            continue
        # conditions[start..position] bind tighter than the operator after them.
        group = _group(conditions[start : position + 1], operators[start:position])
        text += f"({group})" if position > start else group
        if operator is not None:
            text += f" {_DISPLAY.get(operator, operator.upper())} "
        start = position + 1
    return text
