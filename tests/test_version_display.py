"""'maptasker -v' Unit Tests

Asking for the version printed a banner drawn in block characters, and on a Windows console in a legacy code page
those cannot be written: the run died with UnicodeEncodeError (or, in a window that closed at once, simply seemed to
do nothing).  The version is the point of '-v', so what is tested is that it is always said -- on a terminal that can
draw the banner, on one that cannot, and on a pipe -- and that the cursor-moving animation is kept to a terminal.
"""

from __future__ import annotations

import io

import pytest
from maptasker.src.core import versiondisplay
from maptasker.src.core.mtexcept import MapTaskerError
from maptasker.src.core.sysconst import MY_VERSION


class Terminal(io.TextIOWrapper):
    """A stdout with an encoding of its own, and an answer to 'are you a terminal'."""

    def __init__(self, encoding: str, *, tty: bool) -> None:
        super().__init__(io.BytesIO(), encoding=encoding, errors="strict", write_through=True)
        self.tty = tty

    def isatty(self) -> bool:
        return self.tty

    def said(self) -> str:
        return bytes(self.buffer.getvalue()).decode(self.encoding, errors="replace")  # type: ignore[attr-defined]


@pytest.fixture
def animated(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The animation replaced by a note that it ran."""
    ran: list[str] = []
    monkeypatch.setattr(versiondisplay, "clip_figure", lambda figure, colored: ran.append(figure))
    return ran


def ask(monkeypatch: pytest.MonkeyPatch, terminal: Terminal) -> str:
    monkeypatch.setattr(versiondisplay.sys, "stdout", terminal)
    with pytest.raises(MapTaskerError) as ended:
        versiondisplay.display_version()
    assert ended.value.exit_code == 0
    return terminal.said()


def test_a_terminal_that_can_draw_it_gets_the_banner_the_version_and_the_animation(
    monkeypatch: pytest.MonkeyPatch, animated: list[str]
) -> None:
    said = ask(monkeypatch, Terminal("utf-8", tty=True))

    assert "█" in said
    assert MY_VERSION in said
    assert animated == ["castles"]


def test_a_legacy_windows_console_gets_the_version_and_no_traceback(
    monkeypatch: pytest.MonkeyPatch, animated: list[str]
) -> None:
    said = ask(monkeypatch, Terminal("cp1252", tty=True))

    assert MY_VERSION in said
    assert "under license" in said
    assert "█" not in said
    assert animated == [], "the animation is drawn in the same characters"


def test_a_pipe_gets_the_version_without_the_cursor_moving_animation(
    monkeypatch: pytest.MonkeyPatch, animated: list[str]
) -> None:
    said = ask(monkeypatch, Terminal("utf-8", tty=False))

    assert MY_VERSION in said
    assert animated == []


def test_an_encoding_python_does_not_know_is_treated_as_one_that_cannot_draw(monkeypatch: pytest.MonkeyPatch) -> None:
    class Odd:
        encoding = "not-a-real-codec"

    monkeypatch.setattr(versiondisplay.sys, "stdout", Odd())

    assert versiondisplay.stream_can_show_the_banner() is False


class _Kernel32:
    """Enough of kernel32 to be asked for a console's mode and told a new one."""

    def __init__(self, *, console: bool) -> None:
        self.console = console
        self.set_to: int | None = None

    def GetStdHandle(self, which: int) -> int:
        return which

    def GetConsoleMode(self, handle: int, mode: object) -> bool:
        mode._obj.value = 3  # type: ignore[attr-defined]  # what byref() wraps: the c_ulong the caller will read
        return self.console

    def SetConsoleMode(self, handle: int, mode: int) -> bool:
        self.set_to = mode
        return True


def _windows_with(monkeypatch: pytest.MonkeyPatch, kernel: _Kernel32) -> None:
    monkeypatch.setattr(versiondisplay.sys, "platform", "win32")
    monkeypatch.setattr(versiondisplay.ctypes, "windll", type("W", (), {"kernel32": kernel}), raising=False)


def test_colour_handling_is_switched_on_for_a_windows_console(monkeypatch: pytest.MonkeyPatch) -> None:
    kernel = _Kernel32(console=True)
    _windows_with(monkeypatch, kernel)

    versiondisplay.enable_ansi_on_windows()

    assert kernel.set_to == 3 | 0x0004


def test_a_windows_pipe_is_left_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    kernel = _Kernel32(console=False)
    _windows_with(monkeypatch, kernel)

    versiondisplay.enable_ansi_on_windows()

    assert kernel.set_to is None


def test_nothing_is_done_off_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    kernel = _Kernel32(console=True)
    _windows_with(monkeypatch, kernel)
    monkeypatch.setattr(versiondisplay.sys, "platform", "darwin")

    versiondisplay.enable_ansi_on_windows()

    assert kernel.set_to is None
