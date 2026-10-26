#! /usr/bin/env python3

#                                                                                      #
# tasks: shell_sort   Sort Actions, args and misc.                                     #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
#
# WHY THIS IS NO LONGER A SHELL SORT
#
# It was one: three nested Python loops, comparing two elements at a time, run once per
# Task for its actions and again for the arguments of individual actions.  Python's own
# sort does the same job in C, and this is the hottest sort in the Map build -- a large
# configuration runs it thousands of times.  The ordering it produces is unchanged:
# ascending by the number in the 'sr' attribute, which is what both callers want.


# Sort an Action list (Actions are not necessarily in numeric order in XML backup file).
"""shelsort: shell sort, for ordering Actions, arguments and other miscellany."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element


def _argument_order(element: Element) -> tuple[int, int]:
    """<Action sr='act12'> / <Str sr='arg3'>: order by the number after the prefix.

    An element whose 'sr' holds no number cannot be placed by it -- Tasker's 'if' argument is the
    one that turns up in practice -- so those keep the order the file has them in, at the end.
    Python's sort is stable, which is what keeps them there.
    """
    suffix = element.attrib.get("sr", "")[3:]
    return (0, int(suffix)) if suffix.isdigit() else (1, 0)


def _numeric_order(value: str | int) -> tuple[int, int]:
    """Numbers as numbers: '10' after '9', not before it."""
    return (0, int(value))


def shell_sort(arr: list[Any], do_arguments: bool, by_numeric: bool) -> None:
    """
    Sort the list in-place, ascending.
    Args:
        arr: The list to sort
        do_arguments: Whether to treat elements as xml elements carrying an 'sr' attribute
        by_numeric: Whether to sort the values numerically rather than as text
    Returns:
        None
    """
    if do_arguments:
        arr[:] = sorted(arr, key=_argument_order)
    elif by_numeric:
        arr[:] = sorted(arr, key=_numeric_order)
    else:
        arr[:] = sorted(arr)
