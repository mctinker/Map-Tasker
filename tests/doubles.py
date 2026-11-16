"""Typed stand-ins for the objects the tests do not want to build whole.

A test of one function rarely needs a real window or a whole run: it needs something with the two or three attributes
that function reads.  A SimpleNamespace is exactly that, but it is a SimpleNamespace as far as the type checker goes, so
every call that hands it to a function taking a MyGui, a RunState or a RunConfig is a type error -- and a type error that
a test carries is one that no longer means anything, since it cannot tell a stand-in from a signature that drifted.

These build the same SimpleNamespace and say what it stands in for.  The attributes are whatever the test names, and
only those, which is the point of using one: code under test that reaches for anything else fails loudly in the test
instead of quietly finding a default.

    state = fake_state(program_arguments=ProgramArguments(...))   # a RunState, as far as the checker is concerned
    window = fake_window(ai_model="")                              # a MyGui
    config = fake_config(display_detail_level=3)                   # a RunConfig
"""

from __future__ import annotations

import argparse
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, TypeVar, cast

T = TypeVar("T")

if TYPE_CHECKING:
    from maptasker.src.core.diagmodel import DiagramEdge, DiagramNode, DiagramRegion
    from maptasker.src.core.primitem import RunState
    from maptasker.src.core.runcfg import RunConfig
    from maptasker.src.gui.guiwins import AndroidFields
    from maptasker.src.gui.userintr import MyGui


def fake_state(**attributes: Any) -> RunState:
    """Something that is a RunState to the checker and has only the attributes given."""
    return cast("RunState", SimpleNamespace(**attributes))


def fake_window(**attributes: Any) -> MyGui:
    """Something that is the window (MyGui) to the checker and has only the attributes given."""
    return cast("MyGui", SimpleNamespace(**attributes))


def fake_config(**attributes: Any) -> RunConfig:
    """Something that is a RunConfig to the checker and has only the attributes given."""
    return cast("RunConfig", SimpleNamespace(**attributes))


def fake_namespace(**attributes: Any) -> argparse.Namespace:
    """Something that is the parsed command line (argparse.Namespace) to the checker, with only the attributes given."""
    return cast("argparse.Namespace", SimpleNamespace(**attributes))


def required(value: T | None) -> T:
    """`value`, which the test knows is there: a test that reads `.text` of a `find()` wants a failure, not a None."""
    assert value is not None, "expected a value, found None"
    return value


def expect(value: object, kind: type[T]) -> T:
    """`value`, which the test knows is a `kind`: a call that returns either a result or an error message is read as a result."""
    assert isinstance(value, kind), f"expected a {kind.__name__}, found {value!r}"
    return value


def diagram_node(
    anchor: str = "a",
    kind: str = "task",
    name: str = "",
    line: int = 0,
    col: int = 0,
    length: int = 4,
    project: str = "",
    index: int = 0,
) -> DiagramNode:
    """A Diagram node with every field a node has, so a test names only the ones it is about."""
    return {
        "anchor": anchor,
        "kind": kind,
        "name": name,
        "line": line,
        "col": col,
        "len": length,
        "project": project,
        "token": "",
        "index": index,
    }


def diagram_region(
    anchor: str = "p", name: str = "Test", line: int = 2, start: int = 1, fold: int = 4, end: int = 5
) -> DiagramRegion:
    """A Diagram region with every field a region has."""
    return {"anchor": anchor, "name": name, "line": line, "start": start, "fold": fold, "end": end}


def diagram_edge(caller: str, called: str, groups: list[int]) -> DiagramEdge:
    """A Diagram call edge."""
    return {"caller": caller, "called": called, "groups": groups}


def fake_android_fields(**widgets: object) -> AndroidFields:
    """A Save To Android panel's device fields, built from stand-ins: only the ones a test is about need be given."""
    return cast("AndroidFields", dict(widgets))


def stand_in(value: object) -> Any:
    """`value`, a test double, handed to code that asks for the real thing: a widget, a window or a state it does not need whole.

    For a stand-in that is built on the spot, fake_window / fake_state / fake_config say what it stands in for.  This is
    for one that already exists -- a recording widget class a test defines, a MagicMock -- where saying which real type
    it replaces would only repeat the parameter it is passed to.
    """
    return value


def no_error(value: T | str | list[str]) -> T:
    """`value`, which the test knows is the object asked for and not the message (or list of messages) that stands in for it.

    The editors' loaders answer with the object or with why they could not make one; a test of the object has nothing to
    say about the other case, and wants it to fail loudly if it happens.
    """
    assert not isinstance(value, (str, list)), f"expected the object, found the error {value!r}"
    return value


def set_attr(target: object, **values: object) -> None:
    """Set attributes the target's class does not allow a test to give them: no backup loaded (`xml_root=None`), a
    recording stand-in where the real object goes.  The names are keywords, so a misspelling is at least one place."""
    for name, value in values.items():
        setattr(target, name, value)
