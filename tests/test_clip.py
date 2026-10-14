"""The terminal splash animation: its argument checks, its frames and a whole playback."""

from __future__ import annotations

import pytest
from maptasker.src.core import clip
from maptasker.src.core.primitem import PrimeItems


@pytest.fixture(autouse=True)
def _no_waiting(monkeypatch: pytest.MonkeyPatch) -> None:
    """A playback sleeps between frames; the tests have no reason to."""
    monkeypatch.setattr(clip.time, "sleep", lambda _seconds: None)


@pytest.mark.parametrize(
    ("speed", "cycles", "color"),
    [
        (50, 0, False),  # fewer than one cycle
        (50, 1001, False),  # more than a thousand
        (50, "3", False),  # not a number
        (0, 3, False),  # too slow
        (101, 3, False),  # too fast
        (50.5, 3, False),  # not a whole number
        (50, 3, "yes"),  # not a True/False
    ],
)
def test_arguments_that_do_not_make_sense_are_refused(speed: object, cycles: object, color: object) -> None:
    with pytest.raises(clip.ClipError):
        clip.Clip("folder", speed, cycles, color)


def test_the_arguments_are_kept_and_speed_becomes_a_delay() -> None:
    animation = clip.Clip("folder", 100, 3, color=True)
    assert animation.source_folder == "folder"
    assert animation.color is True
    assert animation.play_cycles == 3
    assert animation.play_speed == pytest.approx(0.1)  # the faster the speed, the shorter the pause


def test_frames_are_made_from_the_picture_one_cell_each() -> None:
    animation = clip.Clip("folder", 50, 1)
    animation.get_frames()
    assert len(animation.frames) == len(clip.PIC)
    assert animation.frames[0][0] == list(clip.PIC[0][0])


def test_every_cell_starts_in_the_default_colours_and_blanks_are_hidden() -> None:
    animation = clip.Clip("folder", 50, 1)
    animation.get_frames()
    animation.set_char_base_color()
    cells = [cell for frame in animation.frames for row in frame for cell in row]
    assert all(cell.startswith((clip.DEFAULT_FG, clip.PLACEHOLDER_COLOR)) for cell in cells)
    assert clip.PLACEHOLDER in cells  # the picture's "." cells are drawn black on black


def test_colour_instructions_recolour_the_cell_they_name() -> None:
    """Each "[row][column] = FOREGROUND, BACKGROUND" line recolours one cell; text that is not
    one of those lines is ignored rather than crashing a splash screen."""
    animation = clip.Clip("folder", 50, 1, color=True)
    animation.get_frames()
    animation.set_char_base_color()
    animation.frame_color_maps = [["[0][0] = F_RED, B_BLU", "not a colour line"]]

    before = animation.frames[0][0][0][-1]
    animation.color_cells()

    assert animation.frames[0][0][0] == f"{clip.COLORS['F_RED']}{clip.COLORS['B_BLU']}{before}"


def test_a_colour_name_it_does_not_know_is_left_out() -> None:
    animation = clip.Clip("folder", 50, 1, color=True)
    animation.get_frames()
    animation.set_char_base_color()
    animation.frame_color_maps = [["[0][0] = F_NOSUCH"]]

    before = animation.frames[0][0][0][-1]
    animation.color_cells()

    assert animation.frames[0][0][0] == before


def test_a_whole_playback_cycles_the_picture_and_puts_the_terminal_back(capsys: pytest.CaptureFixture[str]) -> None:
    animation = clip.Clip("folder", 100, 2, color=True)
    animation.run()
    written = capsys.readouterr().out
    assert written.startswith(clip.CURSOR_OFF)
    assert written.count(clip.CURSOR_SAVE_POS) == len(clip.PIC) * 2  # every frame, on each of two cycles
    assert clip.CURSOR_RESTORE_POS in written
    assert clip.CURSOR_ON in written
    assert written.endswith(f"{clip.COLORS['F_WHT']}{clip.COLORS['B_BLK']}")


def test_the_uncoloured_playback_never_reads_the_colour_map(capsys: pytest.CaptureFixture[str]) -> None:
    animation = clip.Clip("folder", 100, 1)
    animation.run()
    capsys.readouterr()
    assert not hasattr(animation, "frame_color_maps")


def test_the_splash_runs_and_rings_the_bell(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    said: list[str] = []
    monkeypatch.setattr(clip.console, "say", said.append)
    monkeypatch.setattr(PrimeItems, "slash", "/")

    clip.clip_figure("", colored=False)

    assert capsys.readouterr().out
    assert said == ["\a"]
