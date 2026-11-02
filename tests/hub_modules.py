"""Patching the hub's handlers, which are written in userintr, userintr_views and userintr_tools.

The Map, Diagram, Misc and Tree views are ViewEventHandlers (userintr_views), the tools menu's windows are
ToolEventHandlers (userintr_tools), and what they share is on MapTaskerEventHandlers (userintr).  A name a handler
uses is looked up in the module it is written in, so a test that stands something in for it has to do so in every
module that has it -- which is what `patch_hub` does.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from maptasker.src.gui import userintr, userintr_tools, userintr_views

if TYPE_CHECKING:
    import pytest

HUB_MODULES = (userintr, userintr_views, userintr_tools)


def patch_hub(monkeypatch: pytest.MonkeyPatch, name: str, value: Any) -> None:
    """Stand `value` in for `name` in every hub module that uses it."""
    found = [module for module in HUB_MODULES if hasattr(module, name)]
    assert found, f"no hub module has {name!r}"
    for module in found:
        monkeypatch.setattr(module, name, value)
