#! /usr/bin/env python3

#                                                                                      #
# tasks: shell_sort   Sort Actions, args and misc.                                     #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #

from maptasker.src.sysconst import logger


# Shell sort for Action list (Actions are not necessarily in numeric order in XML backup file).
def shell_sort(arr: list, do_arguments: bool, by_numeric: bool) -> None:
    """
    Shell sort the list in-place
    Args:
        arr: The list to sort
        do_arguments: Whether to treat elements as arguments
        by_numeric: Whether to sort numerically
    Returns:
        None
    Processing Logic:
        1. Set the gap size initially as half of list size
        2. Keep reducing gap size by half until it reaches 1
        3. For current gap size, check all pairs of elements gap positions apart and swap if out of order
        4. Repeat step 3 for all elements in list with current gap
    """
    n = len(arr)
    gap = n // 2
    while gap > 0:
        j = gap
        # Check the array in from left to right
        # Till the last possible index of j
        while j < n:
            i = j - gap  # This will keep help in maintain gap value
            while i >= 0:
                if do_arguments:
                    # Get the n from <Action sr='actn' ve='7'> as a number for comparison purposes
                    attr1 = arr[i]
                    attr2 = arr[i + gap]
                    val1 = attr1.attrib.get("sr", "")
                    val2 = attr2.attrib.get("sr", "")
                    if val1[3:] == "" or val2[3:] == "":  # 'if' argument...skip
                        break
                    comp1 = val1[3:]
                    comp2 = val2[3:]
                else:
                    # General list sort
                    comp1 = arr[i]
                    comp2 = arr[i + gap]
                # Sort by value or numeric(value)?
                if by_numeric:
                    comp1 = int(comp1)
                    comp2 = int(comp2)
                # If value on right side is already greater than left side value
                # We don't do swap else we swap
                if not comp1.isdigit() or not comp2.isdigit():
                    logger.debug(f"MapTasker.py:shell_sort: comp1:{comp1!s} comp2:{comp2!s}")
                if do_arguments and int(comp2) > int(comp1) or not do_arguments and comp2 > comp1:
                    break
                arr[i + gap], arr[i] = arr[i], arr[i + gap]
                i = i - gap  # To check left side also
            # If the element present is greater than current element
            j += 1
        gap = gap // 2
    # We are done
