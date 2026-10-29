"""A report row that is a link must not take the browser to "#".

A row in Missing Resources, Find, the Monitor and the other report windows is a ui.link to "#" with a click handler: the
"#" is only there to make it look and tab like a link.  Left alone, the browser follows it, which pushes an entry onto the
main tab's history -- and a script may close only a tab it opened or one with a single history entry, so Exit with "Close
Tabs On Exit" ticked then left the main tab open.  So every such link cancels the browser's own follow-up in the click
itself, before the click goes on to the server.

The behaviour is in the browser, and the simulated user has no browser; what can be pinned here is that no link of the kind
is written without the JavaScript that cancels it, and what that JavaScript says.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from maptasker.src.core import mapjump

GUI = Path(__file__).parent.parent / "maptasker" / "src" / "gui"
LINK_HANDLERS = ("LINK_CLICK_JS", "find_result_click_js")


def _is_hash_link(node: ast.AST) -> bool:
    """Whether this is ``ui.link(<anything>, "#")``."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "link"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "ui"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and node.args[1].value == "#"
    )


def _link_of(click: ast.Call) -> ast.Call:
    """The ``ui.link(...)`` call a ``.on(...)`` hangs off."""
    assert isinstance(click.func, ast.Attribute)
    assert isinstance(click.func.value, ast.Call)
    return click.func.value


def _hash_link_clicks() -> list[tuple[str, int, ast.Call]]:
    """Every ``.on(...)`` hung directly off a ui.link to "#", with the file and line it is on."""
    found: list[tuple[str, int, ast.Call]] = []
    for path in sorted(GUI.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "on"
                and _is_hash_link(node.func.value)
            ):
                found.append((path.name, node.lineno, node))
    return found


def test_there_are_report_links_to_check() -> None:
    assert len(_hash_link_clicks()) >= 15, "the scan found too few: it has stopped seeing the links"


@pytest.mark.parametrize(
    ("name", "line", "call"),
    _hash_link_clicks(),
    ids=[f"{name}:{line}" for name, line, _ in _hash_link_clicks()],
)
def test_every_link_to_hash_cancels_the_browsers_own_navigation(name: str, line: int, call: ast.Call) -> None:
    handler = next((keyword.value for keyword in call.keywords if keyword.arg == "js_handler"), None)

    assert handler is not None, f"{name}:{line} is a link to '#' that the browser will follow"
    text = ast.unparse(handler)
    assert any(known in text for known in LINK_HANDLERS), (
        f"{name}:{line} cancels it with something unrecognised: {text}"
    )


def test_a_link_to_hash_is_never_left_without_a_click_handler() -> None:
    handled = {(name, _link_of(call).lineno) for name, _, call in _hash_link_clicks()}
    bare = [
        f"{path.name}:{node.lineno}"
        for path in sorted(GUI.glob("*.py"))
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call) and _is_hash_link(node) and (path.name, node.lineno) not in handled
    ]

    assert not bare, f"links to '#' with no .on(...) beside them: {bare}"


def test_the_handler_cancels_the_default_and_then_sends_the_click_on() -> None:
    script = mapjump.LINK_CLICK_JS

    assert script.index("preventDefault()") < script.index("emit(")


@pytest.mark.parametrize("guard", ["", "mt-diagram-anchor"])
def test_a_find_result_row_cancels_the_default_before_it_does_anything_else(guard: str) -> None:
    script = mapjump.find_result_click_js(guard)

    assert script.index("preventDefault()") < script.index("emit(")
    assert script.startswith("(...args) => {")
    assert script.index("preventDefault()") < script.index("raise") or "raise" not in script
