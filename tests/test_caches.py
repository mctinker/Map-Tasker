"""The caches registry: module state about the configuration, emptied when another is loaded.

The GUI is one long-running process.  Anything a module keeps about the configuration it
has loaded -- and that nothing empties -- goes on describing that configuration after the
next one is loaded.  Every such cache is declared through caches.py and so is on its
registry; loading a configuration (maputils.clear_tasker_data) and a full reset
(PrimeItemsReset) empty the lot.
"""

from __future__ import annotations

import pytest
from maptasker.src.primitem import PrimeItems
from maptasker.src import appinv, bildhtml, caches, globalvr, mapcache, profedit, scenes, taskedit
from maptasker.src.maputils import clear_tasker_data
from maptasker.src.primitem import PrimeItemsReset

# Every cache the package declares.  A new one is on the registry the moment it is declared,
# so this list only has to grow when one is added -- and it fails if one is lost.
EXPECTED = {
    "appinv.inventory",
    "bildhtml.map_just_written",
    "globalvr.cross_reference",
    "globalvr.cross_reference_key",
    "mapcache.remembered",
    "profedit.addable_conditions",
    "scenes.carrying_scene_colour",
    "taskedit.addable_actions",
}


# ##################################################################################
# Slot and KeyedCache
# ##################################################################################
def test_a_slot_is_put_back_to_its_default() -> None:
    """clear() is the only reset a slot needs: its default is where it started."""
    slot = caches.Slot("test.slot", "")
    slot.value = "something"
    slot.clear()
    assert slot.value == ""


def test_a_keyed_cache_is_built_once_per_key() -> None:
    """The same key hands back what was built; a new key builds again."""
    built = []
    cache = caches.KeyedCache("test.keyed")

    def build() -> list:
        built.append(len(built))
        return list(built)

    first = cache.get(1, build)
    assert cache.get(1, build) is first
    assert cache.get(2, build) is not first
    assert len(built) == 2


def test_a_keyed_cache_builds_again_after_clear_even_for_the_same_key() -> None:
    """Clearing is not undone by asking with the key the value was built for."""
    cache = caches.KeyedCache("test.cleared")
    first = cache.get(7, list)
    cache.clear()
    assert cache.get(7, list) is not first


# ##################################################################################
# The registry
# ##################################################################################
def test_every_cache_the_package_declares_is_registered() -> None:
    """Declaring through caches is registering: nothing has to remember to."""
    assert set(caches.registered_names()) >= EXPECTED


@pytest.mark.parametrize(
    "reset",
    [lambda: clear_tasker_data(state=PrimeItems), PrimeItemsReset],
    ids=["new-configuration", "full-reset"],
)
def test_loading_another_configuration_empties_every_cache(reset: object) -> None:
    """Both ways the program starts over leave nothing of the last configuration behind."""
    globalvr._cross_reference.value = {"%Stale": object()}  # noqa: SLF001
    globalvr._cross_reference_key.value = "old configuration"  # noqa: SLF001
    mapcache._remembered.value = ("config", "settings", "MapTasker.html", (1, 2), 3)  # noqa: SLF001
    bildhtml._map_just_written.value = "MapTasker.html"  # noqa: SLF001
    scenes._carrying_scene_colour.value = True  # noqa: SLF001
    stale_rows = taskedit._addable_actions.get("old generation", lambda: ["stale"])  # noqa: SLF001
    stale_conditions = profedit._addable_condition_codes.get("old generation", dict)  # noqa: SLF001

    reset()

    assert globalvr._cross_reference.value is None  # noqa: SLF001
    assert globalvr._cross_reference_key.value == ""  # noqa: SLF001
    assert not mapcache.is_current("MapTasker.html", ("config", "settings"))
    assert bildhtml._map_just_written.value == ""  # noqa: SLF001
    assert taskedit._addable_actions.get("old generation", list) is not stale_rows  # noqa: SLF001
    assert profedit._addable_condition_codes.get("old generation", dict) is not stale_conditions  # noqa: SLF001


def test_a_scene_left_open_by_a_failed_build_does_not_open_the_next() -> None:
    """The one real leak this closes.  The Scene colour is held open across a Scene's lines
    and closed as it finishes; a build that failed in between left it held, and the next
    build began by closing a <span> it had never opened.
    """
    scenes._carrying_scene_colour.value = True  # noqa: SLF001  as a failed build leaves it
    clear_tasker_data(state=PrimeItems)
    assert scenes._carrying_scene_colour.value is False  # noqa: SLF001


def test_the_inventory_generation_only_goes_up() -> None:
    """Clearing rebuilds the inventory, and the rebuild moves the generation on -- never back
    to a number a memo keyed on it has already seen.
    """
    before = appinv.generation(state=PrimeItems)
    clear_tasker_data(state=PrimeItems)
    assert appinv.generation(state=PrimeItems) > before
