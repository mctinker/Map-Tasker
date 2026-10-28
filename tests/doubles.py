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
    from maptasker.src.core.primitem import RunState
    from maptasker.src.core.runcfg import RunConfig
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
