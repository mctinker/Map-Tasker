"""The Close button sits beside the other buttons of an analysis window, not alone in the far corner.

These windows end in one row of buttons.  A spacer (ui.space()) before Close pushed it to the far right of the window,
a long way from the buttons it belongs with, so none of these windows has one.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_GUI = Path(__file__).resolve().parent.parent / "maptasker" / "src" / "gui"
_WINDOWS = ("notes", "projdeps", "compat", "newphone", "retire")


def _calls(source: str, name: str) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == name
    ]


@pytest.mark.parametrize("window", _WINDOWS)
def test_the_buttons_row_has_no_spacer_before_close(window: str) -> None:
    source = (_GUI / f"guiwins_{window}.py").read_text(encoding="utf-8")

    assert _calls(source, "space") == [], f"guiwins_{window}.py puts a spacer in its layout"
