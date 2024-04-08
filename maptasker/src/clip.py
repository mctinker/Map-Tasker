# ruff: noqa
r"""
DO NOT DELETE THE AUTHOR COPYRIGHT
©Connor Talbot 2021 - https://github.com/con-dog/clippy

clip.py - Animate and color a given directory of .txt files.

The text in PIC should be 'frames' in a sequence
to give the impression of animation. For steps to make your own, visit the
GitHub link ReadMe. Its very easy!

The colors in PIC_COLORS map to the above text frames.

Stepping through these clearly shows a boat (and a bird) moving frame by frame

small_boat_1a.txt
-----------------
.................
........~...v....
.........../|....
.....v..../_|__..
.........\-----/.
~~~~~~~~~`~~~~~~'

small_boat_1b.txt
-----------------
.................
.......~...v.....
........../|...\,
....v..../_|__...
........\-----/..
~~~~~~~~`~~~~~~'~

.....
.....

small_boat_1h.txt
-----------------
... /`\..........
...v.............
../|.............
./_|__...........
\-----/..........
`~~~~~~'~~~~~~~~~


Any art samples you create should be of a frame-by-frame nature as above ordered
alphabetically with lowercase lettering. Frame play order is dictated by
this alphabetical order.

All files shall be saved to a relevant directory under the "art" directory in
the repo.

Note that you can also color in your art, but you have to create another txt
file in another subfolder called "color" that holds the color mappings to
accompany the art file for each frame eg:
small_boat_1a.txt, small_boat_1a_color.txt, .... etc
''

For ASCII art ideas visit https://www.asciiart.eu/ and credit the original
author if copying
"""

import os
import re
import sys
import time
from maptasker.src.primitem import PrimeItems

# COLORS: FOREGROUND = F, BACKGROUND = B, Value = ANSI value
COLORS = {
    "F_BLK": "\033[30m",
    "B_BLK": "\033[40m",  # BLACK
    "F_RED": "\033[31m",
    "B_RED": "\033[41m",  # RED
    "F_GRN": "\033[32m",
    "B_GRN": "\033[42m",  # GREEN
    "F_YLW": "\033[33m",
    "B_YLW": "\033[43m",  # YELLOW
    "F_BLU": "\033[34m",
    "B_BLU": "\033[44m",  # BLUE
    "F_MGT": "\033[35m",
    "B_MGT": "\033[45m",  # MAGENTA
    "F_CYA": "\033[36m",
    "B_CYA": "\033[46m",  # CYAN
    "F_WHT": "\033[37m",
    "B_WHT": "\033[47m",  # WHITE
    "F_CLP": "\033[38;5;68m",
    "B_CLP": "\033[48;5;68m",  # CLIPPY
    "F_PYT": "\033[38;5;33m",
    "B_PYT": "\033[48;5;33m",
    "F_BWN": "\033[38;5;130m",
    "B_BWN": "\033[48;5;130m",  # BROWN
    "F_GRY": "\033[38;5;153m",
    "B_GRY": "\033[48;5;153m",  # GRAY
    "F_TRQ": "\033[38;5;50m",
    "B_TRQ": "\033[48;5;50m",  # TURQUOISE
    "F_NVY": "\033[38;5;33m",
    "B_NVY": "\033[48;5;33m",  # NAVY
    "F_STN": "\033[38;5;153m",
    "B_STN": "\033[48;5;153m",  # STONE
    "F_MRN": "\033[38;5;160m",
    "B_MRN": "\033[48;5;160m",  # MORNING
    "F_ONG": "\033[38;5;202m",
    "B_ONG": "\033[48;5;202m",  # ORANGE
    "F_DSK": "\033[38;5;203m",
    "B_DSK": "\033[48;5;203m",  # DUSK
    "F_SND": "\033[38;5;229m",
    "B_SND": "\033[48;5;229m",  # SAND
}

# DEFAULT COLORS AND PLACEHOLDER CHARACTER
DEFAULT_FG = COLORS["F_WHT"]
DEFAULT_BG = COLORS["B_BLK"]
PLACEHOLDER_CHAR = "."
PLACEHOLDER_COLOR = f"{COLORS['F_BLK']}{COLORS['B_BLK']}"
PLACEHOLDER = f"{PLACEHOLDER_COLOR}{PLACEHOLDER_CHAR}"

# CURSOR ANSI ESCAPE PATTERNS
CURSOR_UP = "\033[1A"  # moves cursor up one line
CURSOR_DOWN = "\033[1B"  # moves cursor up one line
CURSOR_RESET = "\033[u"  # resets the cursor
CURSOR_OFF = "\033[?25l"  # makes cursor invisible
CURSOR_ON = "\033[?25h"  # makes cursor visible
CURSOR_SAVE_POS = "\033[s"  # saves cursor position
CURSOR_RESTORE_POS = "\033[u"  # returns cursor to last saved position

PIC = (
    [
        ".......|~......",
        r"....../.\......",
        r")..|~/___\.|~..",
        r"../_\|::.|/_\..",
        r"..|$||/^\||$|..",
        "..|nnn|I|nnn|..",
    ],
    [
        "......~|.......",
        r"(x).../.\......",
        r"..~|./___\.|~..",
        r"../_\|::.|/_\..",
        r"..|$||/^\||$|..",
        "..|nnn|I|nnn|..",
    ],
    [
        "...(X).|~......",
        r"....../.\......",
        r"..~|./___\~|...",
        r"../_\|::.|/_\..",
        r"..|$||/^\||$|..",
        "..|nnn|I|nnn|..",
    ],
    [
        "......~|.(X)...",
        r"....../.\......",
        r"...|~/___\.|~..",
        r"../_\|::.|/_\..",
        r"..|$||/^\||$|..",
        "..|nnn|I|nnn|..",
    ],
    [
        ".*....~|..*....",
        r"...*../.\....(o",
        r"..~|./___\.|~..",
        r"../_\|::.|/_\..",
        r"..|$||/^\||$|..",
        "..|nnn|I|nnn|..",
    ],
    [
        "...*...|~....*.",
        r".*..*./.\.*...*",
        r"...|~/___\~|..(",
        r"../_\|::.|/_\..",
        r"..|$||/^\||$|..",
        "..|nnn|I|nnn|..",
    ],
)

PIC_COLORS = [
    "[0][7] = F_WHT, B_BLU",
    "[0][7] = F_WHT, B_BLU",
    "[1][6] = F_WHT, B_BLU",
    "[1][8] = F_WHT, B_BLU",
    "[2][0] = F_MGT",
    "[2][3] = F_WHT, B_BLU",
    "[2][5] = F_WHT, B_BLU",
    "[2][6] = F_WHT, B_BLU",
    "[2][7] = F_WHT, B_BLU",
    "[2][8] = F_WHT, B_BLU",
    "[2][9] = F_WHT, B_BLU",
    "[3][2] = F_WHT, B_BLU",
    "[3][3] = F_WHT, B_BLU",
    "[3][4] = F_WHT, B_BLU",
    "[3][5] = F_WHT, B_BLU",
    "[3][9] = F_WHT, B_BLU",
    "[3][10] = F_WHT, B_BLU",
    "[3][11] = F_WHT, B_BLU",
    "[3][12] = F_WHT, B_BLU",
    "[4][2] = F_WHT, B_BLU",
    "[4][4] = F_WHT, B_BLU",
    "[4][5] = F_WHT, B_BLU",
    "[4][9] = F_WHT, B_BLU",
    "[4][10] = F_WHT, B_BLU",
    "[4][12] = F_WHT, B_BLU",
    "[5][2] = F_WHT, B_BLU",
    "[5][6] = F_WHT, B_BLU",
    "[5][8] = F_WHT, B_BLU",
    "[5][12] = F_WHT, B_BLU",
]


class ClipException(Exception):
    """Raise Exception if Clip class methods are misused"""

    pass


class Clip:
    """A class to manage all aspects of a clip."""

    def __init__(self, source_folder, play_speed, play_cycles, color=False) -> None:
        """Initialize instance of Tile"""
        sys.stdout.write(CURSOR_OFF)
        self._source_folder = source_folder
        self.play_speed = 5.1 - (play_speed / 20)
        self.play_cycles = play_cycles
        self._color = color

        if not isinstance(self.play_cycles, int):
            raise ClipException("play cycles must be an integer")
        if (self.play_cycles < 1) or (self.play_cycles > 1000):
            raise ClipException("play cycles must be an integer from 1-1000")
        if not isinstance(play_speed, int):
            raise ClipException("Speed must be an integer from 1-100")
        if (play_speed < 1) or (play_speed > 100):
            raise ClipException("Speed must be an integer from 1-100")
        if not isinstance(self._color, bool):
            raise ClipException('colorless by default - pass "True" for color')

    @property
    def source_folder(self):
        """Instance read only property"""
        return self._source_folder

    @property
    def color(self):
        """Instance read only property"""
        return self._color

    def get_frames(self):
        """Get all the frame art from the ascii sub-directory in alphabetical
        order."""
        self.frames = []
        for line in PIC:
            frame = []
            frame.extend(list(row) for row in line)
            self.frames.append(frame)
        ...

    def set_char_base_color(self):
        """Loop over each frames characters, and set them to defaults"""
        for f, frame in enumerate(self.frames):
            for r, row in enumerate(frame):
                for c, char in enumerate(self.frames[f][r]):
                    if char != PLACEHOLDER_CHAR:
                        self.frames[f][r][c] = f"{DEFAULT_FG}{DEFAULT_BG}{char}"
                    else:
                        self.frames[f][r][c] = PLACEHOLDER

    def get_frame_color_maps(self):
        """Get all the color mappings from the color sub-directory in
        alphabetical order."""
        # Get the colors to map to ascii characters
        self.frame_color_maps = []
        lines = PIC_COLORS
        # Remove any empty lines. Required for regex
        frame_color_map = [line for line in lines if line]
        self.frame_color_maps.append(frame_color_map)

    def color_cells(self):
        """Color the cells by mapping the frames color map to that frames
        characters"""
        map_regex = re.compile(
            r"""
            \[(\d*)\]  # group 1: Match [digit/s] for row
            \[(\d*)\]  # group 2: Match [digit/s] for column
            [\s=\s]*  # get everything around equals sign
            (\w*[^,])  # group 3: match the 1st color (not optional)
            (,[\s]*(\w*))?  # group 5: match an optional second color
            """,
            re.VERBOSE,
        )
        # need the index of the frame_color_map to map to the corresponding
        # frame in self.frames
        for frame_index, frame_color_map in enumerate(self.frame_color_maps):
            for char_color_map in frame_color_map:
                mo = map_regex.search(char_color_map)
                row = int(mo[1])
                column = int(mo[2])
                color_1_text = mo[3]
                color_2_text = mo[5]
                # just get the ASCII character, not its color!
                char = self.frames[frame_index][row][column][-1]

                # map colors string to COLORS variables constants values
                color_1 = COLORS.get(color_1_text, "")
                color_2 = COLORS.get(color_2_text, "")

                updated_char = f"{color_1}{color_2}{char}"
                self.frames[frame_index][row][column] = updated_char

    def play_clip(self):
        """Loop through a clips frames to display it to screen at the given
        speed"""
        sys.stdout.flush()
        for frame in self.frames:
            for row in frame:  # Iterate over each frames rows
                for char in row:
                    sys.stdout.write(char)
                sys.stdout.write("\n")  # newline after all cells in row shown
            sys.stdout.write(CURSOR_SAVE_POS)  # save cursor position
            # Move cursor back to top of display and draw next frame
            sys.stdout.write(CURSOR_UP * len(frame))
            time.sleep(self.play_speed)

    def loop_clip(self):
        """Loop through the clip the given number of cycles"""
        while self.play_cycles > 1:
            self.play_clip()
            self.play_cycles -= 1
        sys.stdout.write(CURSOR_RESTORE_POS)  # restore cursor to saved position

    def run(self):
        """
        Call instance functions to animate the frames to the screen and cycle
        the animation
        """
        self.get_frames()
        self.set_char_base_color()
        if self.color:
            self.get_frame_color_maps()
            self.color_cells()
        self.play_clip()
        self.loop_clip()
        sys.stdout.write(CURSOR_ON)
        sys.stdout.write(f'{COLORS["F_WHT"]}{COLORS["B_BLK"]}')


def clippy(path, speed, cycles, color):
    """main function for module"""
    clip = Clip(path, speed, cycles, color)
    clip.run()


# if __name__ == "__main__":
def clip_figure(figure: str, colored: bool) -> None:
    # small_boat = "/clip/sea/boats/small_boat_1"  # Colors = True
    # boats = "/clip/sea/boats"  # Colors = False
    # dance = "/clip/dance"  # Colors = False
    colored = False
    if not figure:
        figure = "/clip/castles"  # Colors = False

    colored = True

    my_output_dir = f"{os.getcwd()}{PrimeItems.slash}clip{PrimeItems.slash}{figure}"
    clippy(my_output_dir, 100, 3, colored)
    print("\a")  # Bell/alert
