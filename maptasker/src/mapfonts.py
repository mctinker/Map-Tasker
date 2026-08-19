#! /usr/bin/env python3
"""mapfonts: locate system fonts and identify the monospaced ones.

This is a pure standard-library replacement for the Tkinter font handling that
MapTasker used previously.  Font files are located per operating system and their
sfnt tables (``name``, ``cmap``, ``hmtx``, ``hhea``, ``head`` and ``OS/2``) are
parsed directly, so no GUI toolkit needs to be installed or initialized.
"""

#                                                                                      #
# mapfonts: system font discovery and monospace detection                              #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #

from __future__ import annotations

import platform
import struct
import subprocess
import unicodedata
from functools import lru_cache
from pathlib import Path

# Returned when the system reports no monospaced fonts at all.
FALLBACK_MONO_FONTS = ("Courier New", "Courier")

# Appended to a font's name in the picker to mark it as monospaced.
MONOSPACED_LABEL = "  —  monospaced"

# Font file types we know how to parse.  ".ttc"/".otc" are collections holding
# several faces in a single file.
FONT_SUFFIXES = frozenset({".ttf", ".otf", ".ttc", ".otc"})

# Characters used to decide whether a font is monospaced.  A font qualifies when it
# has a glyph for every one of these and they all share the same advance width.
_PROBE_CHARS = "iWM.l"

# Style names that identify the face best representing a family, best first.
_PREFERRED_STYLES = ("regular", "roman", "book", "normal", "medium", "")

# PANOSE bProportion value denoting a monospaced design.
_PANOSE_MONOSPACED = 9


# ##################################################################################
# Low-level sfnt (TrueType/OpenType) table parsing
# ##################################################################################
def _face_offsets(data: bytes) -> list[int]:
    """Return the offset of each face in the file (collections hold more than one)."""
    if data[:4] == b"ttcf":
        count = struct.unpack(">I", data[8:12])[0]
        return list(struct.unpack(f">{count}I", data[12 : 12 + count * 4]))
    return [0]


def _table_directory(data: bytes, offset: int) -> dict[bytes, tuple[int, int]]:
    """Return {table tag: (offset, length)} for the face starting at `offset`."""
    num_tables = struct.unpack(">H", data[offset + 4 : offset + 6])[0]
    directory = {}
    for i in range(num_tables):
        entry = offset + 12 + i * 16
        tag, _checksum, table_offset, length = struct.unpack(">4sIII", data[entry : entry + 16])
        directory[tag] = (table_offset, length)
    return directory


def _read_names(data: bytes, directory: dict[bytes, tuple[int, int]]) -> tuple[str, str]:
    """Return the (family, style) names of a face from its `name` table."""
    if b"name" not in directory:
        return "", ""
    base = directory[b"name"][0]
    count, string_offset = struct.unpack(">HH", data[base + 2 : base + 6])
    strings = base + string_offset
    # Name IDs: 1/2 are the legacy family/style, 16/17 the typographic ones (preferred).
    best: dict[int, tuple[int, str]] = {}
    for i in range(count):
        entry = base + 6 + i * 12
        platform_id, _encoding, _language, name_id, length, offset = struct.unpack(">HHHHHH", data[entry : entry + 12])
        if name_id not in (1, 2, 16, 17):
            continue
        raw = data[strings + offset : strings + offset + length]
        try:
            text = raw.decode("mac-roman") if platform_id == 1 else raw.decode("utf-16-be")
        except (UnicodeDecodeError, LookupError):
            continue
        text = text.replace("\x00", "").strip()
        if not text:
            continue
        # Prefer the Windows/Unicode records; they are the ones users recognize.
        priority = 1 if platform_id == 1 else 2
        if name_id not in best or priority > best[name_id][0]:
            best[name_id] = (priority, text)

    family = (best.get(16) or best.get(1) or (0, ""))[1]
    style = (best.get(17) or best.get(2) or (0, ""))[1]
    return family, style


def _read_cmap(data: bytes, directory: dict[bytes, tuple[int, int]]) -> dict[int, int]:
    """Return {codepoint: glyph id} from the most complete Unicode cmap subtable."""
    if b"cmap" not in directory:
        return {}
    base = directory[b"cmap"][0]
    num_subtables = struct.unpack(">H", data[base + 2 : base + 4])[0]
    # Rank the (platform, encoding) pairs so full-Unicode subtables win over BMP-only ones.
    ranking = {(3, 10): 5, (0, 6): 5, (0, 4): 5, (3, 1): 4, (0, 3): 4, (0, 1): 3, (0, 0): 3, (3, 0): 1}
    best: tuple[int, int] | None = None
    for i in range(num_subtables):
        platform_id, encoding_id, offset = struct.unpack(">HHI", data[base + 4 + i * 8 : base + 12 + i * 8])
        score = ranking.get((platform_id, encoding_id))
        if score is not None and (best is None or score > best[0]):
            best = (score, base + offset)
    if best is None:
        return {}

    sub = best[1]
    table_format = struct.unpack(">H", data[sub : sub + 2])[0]
    cmap: dict[int, int] = {}

    if table_format == 4:
        seg_bytes = struct.unpack(">H", data[sub + 6 : sub + 8])[0]
        segments = seg_bytes // 2
        ends = struct.unpack(f">{segments}H", data[sub + 14 : sub + 14 + seg_bytes])
        starts_at = sub + 16 + seg_bytes
        starts = struct.unpack(f">{segments}H", data[starts_at : starts_at + seg_bytes])
        deltas_at = starts_at + seg_bytes
        deltas = struct.unpack(f">{segments}h", data[deltas_at : deltas_at + seg_bytes])
        ranges_at = deltas_at + seg_bytes
        range_offsets = struct.unpack(f">{segments}H", data[ranges_at : ranges_at + seg_bytes])
        for i in range(segments):
            start, end = starts[i], ends[i]
            if start == 0xFFFF:
                continue
            for codepoint in range(start, min(end, 0xFFFE) + 1):
                if range_offsets[i] == 0:
                    glyph = (codepoint + deltas[i]) & 0xFFFF
                else:
                    at = ranges_at + i * 2 + range_offsets[i] + (codepoint - start) * 2
                    if at + 2 > len(data):
                        continue
                    glyph = struct.unpack(">H", data[at : at + 2])[0]
                    if glyph:
                        glyph = (glyph + deltas[i]) & 0xFFFF
                if glyph:
                    cmap[codepoint] = glyph

    elif table_format == 12:
        num_groups = struct.unpack(">I", data[sub + 12 : sub + 16])[0]
        for i in range(num_groups):
            at = sub + 16 + i * 12
            start, end, glyph = struct.unpack(">III", data[at : at + 12])
            # Guard against absurd ranges in malformed fonts.
            for step in range(min(end - start + 1, 0x10000)):
                cmap[start + step] = glyph + step

    elif table_format == 6:
        first, count = struct.unpack(">HH", data[sub + 6 : sub + 10])
        glyphs = struct.unpack(f">{count}H", data[sub + 10 : sub + 10 + count * 2])
        cmap = {first + i: glyph for i, glyph in enumerate(glyphs) if glyph}

    elif table_format == 0:
        for codepoint in range(256):
            glyph = data[sub + 6 + codepoint]
            if glyph:
                cmap[codepoint] = glyph

    return cmap


def _read_metrics(data: bytes, directory: dict[bytes, tuple[int, int]]) -> tuple[int, list[int]]:
    """Return (units per em, glyph advance widths) for a face."""
    units_per_em = 1000
    if b"head" in directory:
        head = directory[b"head"][0]
        units_per_em = struct.unpack(">H", data[head + 18 : head + 20])[0] or 1000

    num_metrics = 0
    if b"hhea" in directory:
        hhea = directory[b"hhea"][0]
        num_metrics = struct.unpack(">H", data[hhea + 34 : hhea + 36])[0]

    advances: list[int] = []
    if b"hmtx" in directory and num_metrics:
        hmtx = directory[b"hmtx"][0]
        advances = [struct.unpack(">H", data[hmtx + i * 4 : hmtx + i * 4 + 2])[0] for i in range(num_metrics)]

    return units_per_em, advances


def _read_panose_proportion(data: bytes, directory: dict[bytes, tuple[int, int]]) -> int | None:
    """Return the PANOSE bProportion byte from the `OS/2` table, if present."""
    if b"OS/2" not in directory:
        return None
    offset, length = directory[b"OS/2"]
    # PANOSE is a 10-byte array starting at offset 32; bProportion is its 4th byte.
    return data[offset + 35] if length >= 42 else None


class _Face:
    """A single font face (one entry of a font file) and the metrics we need from it."""

    __slots__ = ("advances", "cmap", "family", "panose", "style", "units_per_em")

    def __init__(self, data: bytes, offset: int) -> None:
        """Parse the sfnt tables of the face starting at `offset` within `data`."""
        directory = _table_directory(data, offset)
        self.family, self.style = _read_names(data, directory)
        self.cmap = _read_cmap(data, directory)
        self.units_per_em, self.advances = _read_metrics(data, directory)
        self.panose = _read_panose_proportion(data, directory)

    def advance(self, codepoint: int) -> float | None:
        """Return the advance width of `codepoint` in em units, or None if not in the font."""
        glyph = self.cmap.get(codepoint)
        if glyph is None or not self.advances:
            return None
        # Glyphs past the last entry all share the final advance width.
        raw = self.advances[glyph] if glyph < len(self.advances) else self.advances[-1]
        return raw / self.units_per_em

    def is_monospaced(self) -> bool:
        """Return True if every probe character is present and shares one advance width."""
        widths = {self.advance(ord(char)) for char in _PROBE_CHARS}
        if None not in widths and len(widths) == 1 and widths != {0.0}:
            return True
        # Symbol fonts remap ASCII, so trust the designer's PANOSE classification too.
        return self.panose == _PANOSE_MONOSPACED


# ##################################################################################
# Locating font files on each operating system
# ##################################################################################
def _windows_font_files() -> list[Path]:
    """Return the font files listed in the Windows registry."""
    import winreg  # noqa: PLC0415 - Windows-only module; importing it elsewhere fails.

    reg_key = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
    font_dir = Path("C:/Windows/Fonts")
    files = []
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_key) as key:
        index = 0
        while True:
            try:
                _name, file_name, _kind = winreg.EnumValue(key, index)
            except OSError:
                break
            index += 1
            path = Path(file_name)
            if not path.is_absolute():
                path = font_dir / path
            if path.suffix.lower() in FONT_SUFFIXES and path.exists():
                files.append(path)
    return files


def _linux_font_files() -> list[Path]:
    """Return the font files known to Fontconfig, or found by scanning font directories."""
    try:
        output = subprocess.check_output(["fc-list", ":", "file"], text=True)  # noqa: S607
    except (OSError, subprocess.SubprocessError):
        return _scan_font_dirs([Path("/usr/share/fonts"), Path("/usr/local/share/fonts"), Path.home() / ".fonts"])

    files = []
    for line in output.splitlines():
        # fc-list emits "<path>: <family>"; the path is everything before the first colon.
        path = Path(line.split(":", 1)[0].strip())
        if path.suffix.lower() in FONT_SUFFIXES:
            files.append(path)
    return files


def _scan_font_dirs(dirs: list[Path]) -> list[Path]:
    """Return every font file found under the given directories."""
    files = []
    for directory in dirs:
        if directory.exists():
            files.extend(path for path in directory.rglob("*") if path.suffix.lower() in FONT_SUFFIXES)
    return files


def _font_files() -> list[Path]:
    """Return the font files installed on this system."""
    os_type = platform.system()
    try:
        if os_type == "Windows":
            return _windows_font_files()
        if os_type == "Darwin":
            return _scan_font_dirs(
                [Path("/System/Library/Fonts"), Path("/Library/Fonts"), Path.home() / "Library/Fonts"],
            )
        return _linux_font_files()
    except Exception:  # noqa: BLE001 - font discovery must never take the program down.
        return []


# ##################################################################################
# The font index: family name -> best face
# ##################################################################################
@lru_cache(maxsize=1)
def _font_index() -> dict[str, _Face]:
    """Return {family name: face}, keeping the face that best represents each family.

    Building this reads every installed font file once, so the result is cached for
    the life of the process.
    """
    index: dict[str, _Face] = {}
    ranks: dict[str, int] = {}
    for path in _font_files():
        try:
            data = path.read_bytes()
            offsets = _face_offsets(data)
        except (OSError, struct.error):
            continue
        for offset in offsets:
            try:
                face = _Face(data, offset)
            except (struct.error, IndexError, ValueError):
                continue
            # Families beginning with "." are reserved for the OS and are not selectable.
            if not face.family or face.family.startswith("."):
                continue
            style = face.style.lower()
            rank = _PREFERRED_STYLES.index(style) if style in _PREFERRED_STYLES else len(_PREFERRED_STYLES)
            if face.family not in index or rank < ranks[face.family]:
                index[face.family] = face
                ranks[face.family] = rank
    return index


# ##################################################################################
# Public interface
# ##################################################################################
def get_system_fonts() -> list[str]:
    """Return the sorted names of every font family installed on this system."""
    return sorted(_font_index())


@lru_cache(maxsize=1)
def _monospaced_families() -> tuple[str, ...]:
    """Return the monospaced font families, cached."""
    return tuple(sorted(family for family, face in _font_index().items() if face.is_monospaced()))


def get_monospaced_fonts() -> list[str]:
    """Return the sorted names of the monospaced font families on this system.

    Falls back to a pair of common monospaced names if none could be identified,
    so callers always have something usable to offer.
    """
    return list(_monospaced_families()) or list(FALLBACK_MONO_FONTS)


def is_monospaced(family: str) -> bool:
    """Return True if `family` is an installed monospaced font."""
    return family in _monospaced_families()


def get_font_choices(include_proportional: bool = True) -> dict[str, str]:
    """Return an ordered {font family: label to show} mapping for a font picker.

    With `include_proportional` False this is just the monospaced families under their
    own plain names -- the same set get_monospaced_fonts() returns. Otherwise every
    installed family is offered, with the monospaced ones sorted to the top and marked,
    since those are the only ones the diagram's box-drawing characters and the output's
    column alignment survive.
    """
    monospaced = _monospaced_families()
    if not include_proportional:
        return {family: family for family in (monospaced or FALLBACK_MONO_FONTS)}

    families = get_system_fonts()
    if not families:
        return {family: family for family in FALLBACK_MONO_FONTS}

    monospaced_set = set(monospaced)
    choices = {family: f"{family}{MONOSPACED_LABEL}" for family in families if family in monospaced_set}
    choices.update({family: family for family in families if family not in monospaced_set})
    return choices


def is_double_width(char: str) -> bool:
    """Return True if `char` occupies two columns when rendered in a monospaced font.

    Uses the Unicode East Asian Width property, which is what browsers and terminals
    use to lay monospaced text out.  That makes the answer identical on every machine,
    unlike measuring the character against whichever fonts happen to be installed.
    """
    if not char:
        return False
    # Wide and Fullwidth cover CJK and the pictographic/emoji planes.
    if unicodedata.east_asian_width(char) in ("W", "F"):
        return True
    # Supplementary symbol planes render as emoji even when marked Neutral/Ambiguous.
    return ord(char) >= 0x1F000
