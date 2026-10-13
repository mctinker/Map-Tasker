"""Tasker <Bundle> definitions extracted from a Tasker export, read on first use."""

#! /usr/bin/env python3

#                                                                                      #
# bundle: the table of plugin <Bundle> definitions, loaded when something asks for it   #
#                                                                                      #
# The table is data, not code: assets/json/bundles.json, written by bldbndle.py from a   #
# real Tasker backup.  It used to be a 6,000-line Python module of escaped strings that  #
# was compiled, unmarshalled and held in memory by every run -- 566 KB, to serve the      #
# editor's "add a plugin action" and the variable cross-reference, neither of which       #
# most runs ever reach.  Now nothing is read until the first lookup.                      #
#                                                                                      #
# 'bundles' behaves as the read-only dict the module used to define (get, items, in,      #
# len, ==...), so a caller imports it and uses it exactly as before.                      #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
from __future__ import annotations

import json
import os
from collections.abc import Iterator, Mapping

# Resolved off this file rather than the working directory: proginit chdir's into the
# assets directory during start-up (see actionc._JSON_DIR).
BUNDLES_FILE = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "json", "bundles.json"),
)


def read_bundles(path: str = BUNDLES_FILE) -> dict:
    """Read a bundles file.

    Args:
        path (str): the json file to read.
    Returns:
        dict: {owning <code> + 'e'/'s'/'t': {'Bundle': {attributes and sub-tags}}}.
    Raises:
        RuntimeError: if the file is missing or is not json -- every plugin action would
            otherwise look like one with no recorded definition, which would read as data.
    """
    try:
        with open(path, encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError as error:
        message = f"bundle: {path} is missing.  MapTasker cannot build a plugin action without it."
        raise RuntimeError(message) from error
    except json.JSONDecodeError as error:
        message = f"bundle: {path} is not valid JSON ({error})."
        raise RuntimeError(message) from error


class LazyBundles(Mapping):
    """A read-only dict of the recorded bundles that is not read from disk until it is used."""

    def __init__(self, path: str = BUNDLES_FILE) -> None:
        """
        Args:
            path (str): the json file the table is read from, on first use.
        """
        self._path = path
        self._table: dict | None = None

    @property
    def table(self) -> dict:
        """The table itself, read the first time it is asked for."""
        if self._table is None:
            self._table = read_bundles(self._path)
        return self._table

    def reload(self) -> None:
        """Forget what was read, so that the next lookup reads the file again (after bldbndle rewrote it)."""
        self._table = None

    def __getitem__(self, key: str) -> dict:
        """The recorded definition for an owning code, as the dict it always was."""
        return self.table[key]

    def __iter__(self) -> Iterator[str]:
        """The codes, in numeric order."""
        return iter(self.table)

    def __len__(self) -> int:
        """How many definitions are recorded."""
        return len(self.table)


bundles = LazyBundles()
