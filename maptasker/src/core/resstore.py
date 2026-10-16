"""resstore: what the last Missing Resources check found on each device, kept between runs."""

#! /usr/bin/env python3

#                                                                                        #
# resstore: the answers of the Missing Resources check, per device.                      #
#                                                                                        #
# The check itself needs the phone (see deviceresource): a path exists or not on a        #
# particular device, at a particular moment.  The Health Check, though, is a read of the  #
# file that never goes to the network (plugchk makes the same bargain with the app list). #
# So the check writes down what it was told, and says when, and the Health Check reads   #
# that back -- the answer is as old as the last check, and says so.                       #
#                                                                                        #
# Kept per device, as appinv keeps its app lists, because "is it there" is a question     #
# about one phone.  A reference is reported missing only when no device that was asked    #
# about it has it: the backup does not say which phone it came from, and a file that is  #
# on the tablet checked last month may be exactly where this configuration runs.          #
#                                                                                        #
# What is stored is the question and the answer -- (kind, value, whether it was there) -- #
# and not where in the configuration it was asked from.  Places move when a Task is       #
# edited; a path does not.  The Health Check works out the places afresh from the         #
# configuration in front of it and looks each path up here.                              #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

import json
import os
from typing import Any, cast

from maptasker.src.core import clock
from maptasker.src.core.sysconst import RESOURCES_CACHE_FILE, logger

# (kind, value) -- what was asked about.
Question = tuple[str, str]
# {device: (when it was checked, {question: whether it was there})}
Answers = dict[str, tuple[str, dict[Question, bool]]]


def cache_path() -> str:
    """Where the answers are kept -- beside MapTasker_Apps.json, in the current directory."""
    return os.path.join(os.getcwd(), RESOURCES_CACHE_FILE)


def _read() -> dict[str, Any]:
    """The cache file, or an empty one.  A missing or damaged file means "nothing has been checked"."""
    try:
        with open(cache_path(), encoding="utf-8") as cache_file:
            cache: Any = json.load(cache_file)
    except (OSError, ValueError) as error:
        logger.debug(f"No usable {RESOURCES_CACHE_FILE}: {error}")
        return {}
    return _dict(cache)


def _dict(value: object) -> dict[str, Any]:
    """A JSON value as a dict, or an empty one if it is anything else."""
    return cast("dict[str, Any]", value) if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    """A JSON value as a list, or an empty one if it is anything else."""
    return cast("list[Any]", value) if isinstance(value, list) else []


def _write(cache: dict[str, Any]) -> str:
    """Save the cache.  Returns "" or why it could not be saved."""
    try:
        with open(cache_path(), "w", encoding="utf-8") as cache_file:
            json.dump(cache, cache_file, indent=2)
    except OSError as error:
        logger.error(f"Could not write {cache_path()}: {error}")
        return str(error)
    return ""


def answers() -> Answers:
    """Every device's answers, as last stored.  Empty when nothing has been checked."""
    found: Answers = {}
    for device, record in sorted(_dict(_read().get("devices")).items()):
        known: dict[Question, bool] = {}
        for row in map(_list, _list(_dict(record).get("answers"))):
            if len(row) == 3:
                known[(str(row[0]), str(row[1]))] = bool(row[2])
        found[device] = (str(_dict(record).get("checked", "")), known)
    return found


def store(device: str, known: dict[Question, bool]) -> str:
    """Record one device's answers, replacing what it said last time.  Returns "" or why it could not be saved.

    Replaced rather than merged, for that device: a file deleted since the last check must not stay "present",
    and a file put back must not stay "missing".  Other devices' records are left alone.
    """
    cache = _read()
    devices = _dict(cache.get("devices"))
    cache["devices"] = devices
    devices[device] = {
        "checked": clock.now().strftime("%Y-%m-%d %H:%M:%S"),
        "answers": [[kind, value, present] for (kind, value), present in sorted(known.items())],
    }
    return _write(cache)


def forget(device: str) -> str:
    """Drop one device's answers.  Returns "" or why the file could not be rewritten."""
    cache = _read()
    devices = _dict(cache.get("devices"))
    if device not in devices:
        return ""
    del devices[device]
    cache["devices"] = devices
    return _write(cache)
