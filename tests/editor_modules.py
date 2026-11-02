"""Patching the editor handlers, which are one module to a kind.

The handlers are written in userintr_editors_task, _project, _scene and _profile and put together in
userintr_editors.EditorEventHandlers.  A name a handler uses is looked up in the module it is written in, so a test
that stands something in for it has to do so in every module that has it -- which is what `patch_editors` does.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from maptasker.src.gui import (
    userintr_editors_base,
    userintr_editors_profile,
    userintr_editors_project,
    userintr_editors_scene,
    userintr_editors_task,
)

if TYPE_CHECKING:
    import pytest

EDITOR_MODULES = (
    userintr_editors_base,
    userintr_editors_task,
    userintr_editors_project,
    userintr_editors_scene,
    userintr_editors_profile,
)

# NiceGUI's own ui module, which every one of them holds: patching an attribute of it is patching it for all.
editor_ui = userintr_editors_task.ui


def patch_editors(monkeypatch: pytest.MonkeyPatch, name: str, value: Any) -> None:
    """Stand `value` in for `name` in every editor module that uses it."""
    found = [module for module in EDITOR_MODULES if hasattr(module, name)]
    assert found, f"no editor module has {name!r}"
    for module in found:
        monkeypatch.setattr(module, name, value)
