"""caches: what modules keep about the loaded configuration, in one place that can be cleared."""

#! /usr/bin/env python3

#                                                                                        #
# caches: the module-level state that outlives a call but not a configuration.           #
#                                                                                        #
# The GUI is one long-running process, and several modules keep something worked out     #
# from the configuration it has loaded: the app inventory, which actions can be added,    #
# the variables' cross-reference, the Map already on disk.  Each used to be a global that #
# its module reassigned, with its own way of noticing that it no longer applied -- and     #
# whatever PrimeItemsReset did not know about went on describing the last backup after    #
# the next one was loaded.                                                                #
#                                                                                        #
# So each is declared here instead, as a Slot (one value) or a KeyedCache (a value built   #
# from inputs that can change), and every one declared is on the registry.  clear_all()   #
# empties them together; PrimeItemsReset and loading another configuration both call it, #
# so a new cache is cleared the moment it exists rather than when someone remembers to    #
# add it to a reset.  A KeyedCache still rebuilds by itself when its key moves -- the app #
# inventory changes when a device list is fetched, with no configuration loaded at all -- #
# so the registry is the backstop, not the only thing keeping a cache honest.             #
#                                                                                        #
# Deliberately imports nothing from maptasker: primitem and maputils both call into it.   #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                              #
#
from __future__ import annotations

from typing import TYPE_CHECKING, Generic, Protocol, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")


class Clearable(Protocol):
    """Anything the registry can empty: a name to report it by, and a clear()."""

    name: str

    def clear(self) -> None:
        """Forget everything worked out from the configuration."""


_REGISTRY: list[Clearable] = []


def register(cache: Clearable) -> Clearable:
    """Put a cache on the registry, so clear_all() empties it.  Returns it, for assignment."""
    _REGISTRY.append(cache)
    return cache


def clear_all() -> None:
    """Empty every registered cache: another configuration is loaded, or the run starts over."""
    for cache in _REGISTRY:
        cache.clear()


def registered_names() -> list[str]:
    """The names of the registered caches, in the order they were declared."""
    return [cache.name for cache in _REGISTRY]


class Slot(Generic[T]):
    """One value a module keeps between calls, put back to its default by clear_all().

    The default must be immutable (None, False, "", a tuple): it is handed back as it stands,
    not copied, every time the slot is cleared.
    """

    def __init__(self, name: str, default: T) -> None:
        """Declare the slot and register it."""
        self.name = name
        self._default = default
        self.value: T = default
        register(self)

    def clear(self) -> None:
        """Back to the default."""
        self.value = self._default


_NOTHING = object()


class KeyedCache(Generic[T]):
    """A value built from inputs that can change, kept only while they have not.

    The key stands for those inputs -- a generation counter, a digest of the configuration.
    get() hands back what it built last time when the key is the same, and builds again when
    it is not; clear_all() throws the value away whatever the key.
    """

    def __init__(self, name: str) -> None:
        """Declare the cache and register it."""
        self.name = name
        self._key: object = _NOTHING
        self._value: object = _NOTHING
        register(self)

    def get(self, key: object, build: Callable[[], T]) -> T:
        """The value for this key: the one already built, or build() if the key has moved."""
        if self._value is _NOTHING or key != self._key:
            self._value = build()
            self._key = key
        return self._value  # type: ignore[return-value]

    def clear(self) -> None:
        """Forget the value and the key it was built for."""
        self._key = _NOTHING
        self._value = _NOTHING
