#! /usr/bin/env python3
#                                                                                      #
# mappdf: monospaced text written out as a PDF.                                        #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #

"""Monospaced text written out as a PDF, with nothing but the standard library.

The Map and the Diagram are both text laid out in columns, so a PDF of either needs only a
small part of what a PDF can do: one monospaced font, lines of text in a few colors, pages,
and bookmarks to find a Project by.  That part is small enough to write here rather than
add a PDF library to every install for it.

The font is the part that takes care.  The Diagram is drawn with box-drawing characters,
which none of the fonts a PDF viewer is guaranteed to carry can show, so a monospaced
TrueType font from this system is embedded (see mapfonts.embeddable_font) and addressed by
glyph number.  A ToUnicode map goes with it, which is what keeps the PDF's text searchable
and copyable rather than a picture of text.  Only when no such font can be found does this
fall back on Courier, with the drawing characters traded for the nearest ASCII.
"""

from __future__ import annotations

import re
import zlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from maptasker.src.mapfonts import EmbeddableFont

Color = tuple[float, float, float]
BLACK: Color = (0.0, 0.0, 0.0)

# Page sizes in points (1/72 inch), which is what a PDF measures everything in.
LETTER_PORTRAIT = (612.0, 792.0)
LETTER_LANDSCAPE = (792.0, 612.0)

# The largest a page may be in either direction -- the PDF implementation limit, and the
# point past which viewers start refusing to show it.
_MAX_PAGE_SIDE = 14400.0
_MARGIN = 36.0
# Baseline to baseline, as a multiple of the font size.
_LEADING = 1.2

# Characters that draw nothing: joiners and emoji presentation selectors.  Left in, each
# would be drawn as a missing-glyph box and push everything after it a column to the right.
_INVISIBLE = frozenset("\u200b\u200c\u200d\ufe0e\ufe0f")

# The nearest ASCII character to each drawing character, for when there is no font to draw
# the real ones with.  One character for one, so that the Diagram's columns still line up.
_ASCII_DRAWING = str.maketrans(
    {
        "═": "=",  # double horizontal
        "║": "|",  # double vertical
        "╔": "+",
        "╗": "+",
        "╚": "+",
        "╝": "+",
        "─": "-",  # light horizontal
        "│": "|",  # light vertical
        "┌": "+",
        "┐": "+",
        "└": "+",
        "┘": "+",
        "├": "+",
        "┤": "+",
        "╭": "+",  # rounded corners
        "╮": "+",
        "╰": "+",
        "╯": "+",
        "◄": "<",  # arrowheads
        "►": ">",
        "▶": ">",
        "▼": "v",
        "▲": "^",
        "⬅": "<",  # the Map's entry and exit Task arrows
        "⮕": ">",
    },
)


@dataclass(frozen=True)
class Line:
    """One line of text, and the color to draw it in."""

    text: str
    color: Color = BLACK


@dataclass(frozen=True)
class Bookmark:
    """A bookmark named `title`, pointing at the line numbered `line`, `level` deep in the tree."""

    title: str
    line: int
    level: int = 0


# ##################################################################################
# Fonts
# ##################################################################################
class _TrueType:
    """A TrueType font embedded in the file and addressed by glyph number (Identity-H).

    By glyph number rather than character code because a character code in a PDF string is
    a single byte unless a CMap says otherwise, and the Diagram's characters are nowhere near
    the first 256.  The ToUnicode map written along with it turns the glyph numbers back
    into text for search, copy and screen readers.
    """

    def __init__(self, font: EmbeddableFont) -> None:
        """Wrap `font`, with nothing yet drawn in it."""
        self.font = font
        self.scale = 1000 / font.units_per_em
        # What a character the font has no glyph for is drawn as.
        self.missing = font.cmap.get(ord("?"), 0)
        # Every glyph drawn, and the text it stands for -- the ToUnicode map.
        self.used: dict[int, str] = {}
        self._widths: dict[str, float] = {}

    def _advance(self, glyph: int) -> float:
        """A glyph's advance width in thousandths of the font size."""
        advances = self.font.advances
        if not advances:
            return 600.0
        # Glyphs past the last entry all share the final advance width.
        return (advances[glyph] if glyph < len(advances) else advances[-1]) * self.scale

    def char_width(self, char: str) -> float:
        """How wide `char` is drawn, in thousandths of the font size."""
        width = self._widths.get(char)
        if width is None:
            width = 0.0 if char in _INVISIBLE else self._advance(self.font.cmap.get(ord(char), self.missing))
            self._widths[char] = width
        return width

    def show(self, text: str) -> str:
        """`text` as the string a Tj operator draws, noting every glyph it uses."""
        codes = []
        for char in text:
            if char in _INVISIBLE:
                continue
            glyph = self.font.cmap.get(ord(char), self.missing)
            self.used.setdefault(glyph, char if glyph != self.missing else "?")
            codes.append(f"{glyph:04X}")
        return f"<{''.join(codes)}>"

    def write(self, pdf: _Objects, number: int) -> None:
        """Write the font into `pdf`, the font dictionary the pages name as object `number`.

        Called after every page has been drawn, so that the widths and the ToUnicode map
        cover exactly the glyphs the pages use.
        """
        font = self.font
        name = _name(font.family)
        program = pdf.add_stream(font.sfnt, f"/Length1 {len(font.sfnt)}")
        ascent, descent = round(font.ascent * self.scale), round(font.descent * self.scale)
        bbox = " ".join(str(round(value * self.scale)) for value in font.bbox)
        # Flags: FixedPitch (1) + Symbolic (4), which is what a font addressed by glyph
        # number rather than through a standard encoding has to declare.
        descriptor = pdf.add(
            f"<< /Type /FontDescriptor /FontName {name} /Flags 5 /FontBBox [{bbox}] /ItalicAngle 0 "
            f"/Ascent {ascent} /Descent {descent} /CapHeight {ascent} /StemV 80 /FontFile2 {program} 0 R >>",
        )
        default = round(self.char_width(" "))
        widths = " ".join(
            f"{glyph} [{width}]" for glyph in sorted(self.used) if (width := round(self._advance(glyph))) != default
        )
        descendant = pdf.add(
            f"<< /Type /Font /Subtype /CIDFontType2 /BaseFont {name} "
            "/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> "
            f"/FontDescriptor {descriptor} 0 R /DW {default} /W [{widths}] /CIDToGIDMap /Identity >>",
        )
        to_unicode = pdf.add_stream(_to_unicode(self.used))
        pdf.put(
            number,
            f"<< /Type /Font /Subtype /Type0 /BaseFont {name} /Encoding /Identity-H "
            f"/DescendantFonts [{descendant} 0 R] /ToUnicode {to_unicode} 0 R >>",
        )


class _Courier:
    """Courier, which every PDF viewer has built in: for when no TrueType font was found.

    It has no box-drawing characters, and a PDF viewer is only obliged to know the
    Windows-1252 characters of it, so everything else is traded for ASCII (see
    _ASCII_DRAWING) or, failing that, a question mark.
    """

    @staticmethod
    def char_width(char: str) -> float:
        """How wide `char` is drawn, in thousandths of the font size: Courier is 600 throughout."""
        return 0.0 if char in _INVISIBLE else 600.0

    @staticmethod
    def show(text: str) -> str:
        """`text` as the string a Tj operator draws."""
        visible = "".join(char for char in text if char not in _INVISIBLE).translate(_ASCII_DRAWING)
        return "(" + "".join(_literal(byte) for byte in visible.encode("cp1252", "replace")) + ")"

    @staticmethod
    def write(pdf: _Objects, number: int) -> None:
        """Write the font dictionary the pages name as object `number`."""
        pdf.put(number, "<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>")


def _literal(byte: int) -> str:
    """One byte of a PDF literal string, escaped where the syntax needs it."""
    if byte in b"()\\":
        return "\\" + chr(byte)
    if 32 <= byte < 127:
        return chr(byte)
    return f"\\{byte:03o}"


def _to_unicode(used: dict[int, str]) -> bytes:
    """The ToUnicode CMap that turns each drawn glyph number back into its text."""
    entries = sorted(used.items())
    blocks = []
    # No more than 100 mappings to a bfchar block -- the CMap format's own limit.
    for start in range(0, len(entries), 100):
        chunk = entries[start : start + 100]
        pairs = "\n".join(f"<{glyph:04X}> <{text.encode('utf-16-be').hex().upper()}>" for glyph, text in chunk)
        blocks.append(f"{len(chunk)} beginbfchar\n{pairs}\nendbfchar")
    return (
        "/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
        "/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n"
        "1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n"
        + "\n".join(blocks)
        + "\nendcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n"
    ).encode("ascii")


# ##################################################################################
# The file
# ##################################################################################
class _Objects:
    """The numbered objects a PDF is made of, and the cross-reference table that finds them."""

    def __init__(self) -> None:
        """Start with no objects."""
        self.bodies: list[bytes] = []

    def reserve(self) -> int:
        """A number for an object whose contents are not known yet -- see put."""
        self.bodies.append(b"")
        return len(self.bodies)

    def put(self, number: int, body: str | bytes) -> int:
        """Set the contents of object `number`."""
        self.bodies[number - 1] = body.encode("latin-1") if isinstance(body, str) else body
        return number

    def add(self, body: str | bytes) -> int:
        """A new object holding `body`."""
        return self.put(self.reserve(), body)

    def add_stream(self, data: bytes, entries: str = "") -> int:
        """A new stream object holding `data`, compressed."""
        packed = zlib.compress(data)
        head = f"<< /Length {len(packed)} /Filter /FlateDecode {entries}>>\nstream\n".encode("latin-1")
        return self.add(head + packed + b"\nendstream")

    def serialize(self, root: int, info: int) -> bytes:
        """The whole file: every object, then the table of where each one starts."""
        out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for number, body in enumerate(self.bodies, start=1):
            offsets.append(len(out))
            out += f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
        start = len(out)
        size = len(self.bodies) + 1
        # Every entry exactly 20 bytes, its end of line included: that is how a reader finds
        # the entry for an object without reading the table from the top.
        out += f"xref\n0 {size}\n0000000000 65535 f \n".encode("ascii")
        out += "".join(f"{offset:010d} 00000 n \n" for offset in offsets).encode("ascii")
        out += f"trailer\n<< /Size {size} /Root {root} 0 R /Info {info} 0 R >>\nstartxref\n{start}\n%%EOF\n".encode(
            "ascii",
        )
        return bytes(out)


def render(
    lines: Iterable[Line],
    *,
    title: str,
    font: EmbeddableFont | None,
    bookmarks: Iterable[Bookmark] = (),
    wrap: bool = True,
    page_size: tuple[float, float] = LETTER_PORTRAIT,
    font_size: float = 8.0,
    producer: str = "",
) -> bytes:
    """The PDF of `lines`, as bytes, drawn in `font` (Courier when it is None).

    wrap=True keeps to `page_size` and breaks any line too long for it, indenting what
    spills over under where the line starts -- right for the Map, whose lines are prose.

    wrap=False never breaks a line -- the Diagram's connectors mean nothing outside the
    columns they were drawn in -- and widens the page to the longest line instead, keeping
    `page_size`'s proportions.  The text is shrunk only if even the widest page a PDF may
    have is not wide enough.

    Each bookmark leads to the page and height of the line it names.
    """
    face: _TrueType | _Courier = _TrueType(font) if font is not None else _Courier()
    source = list(lines)
    size = font_size
    if wrap:
        width, height = page_size
        rows, starts = _wrap_lines(source, face, (width - 2 * _MARGIN) * 1000 / size)
    else:
        rows, starts = source, list(range(len(source)))
        widest = max((_width(face, line.text) for line in source), default=0.0)
        if widest:
            size = min(font_size, (_MAX_PAGE_SIDE - 2 * _MARGIN) * 1000 / widest)
        width = min(_MAX_PAGE_SIDE, max(page_size[0], widest * size / 1000 + 2 * _MARGIN))
        height = min(_MAX_PAGE_SIDE, max(page_size[1], width * page_size[1] / page_size[0]))
    leading = size * _LEADING
    per_page = max(1, int((height - 2 * _MARGIN) // leading))

    pdf = _Objects()
    catalog = pdf.reserve()
    pages = pdf.reserve()
    font_number = pdf.reserve()
    page_numbers = []
    for start in range(0, max(len(rows), 1), per_page):
        content = pdf.add_stream(_page_content(rows[start : start + per_page], face, size, height))
        page_numbers.append(
            pdf.add(
                f"<< /Type /Page /Parent {pages} 0 R /MediaBox [0 0 {_number(width)} {_number(height)}] "
                f"/Resources << /Font << /F1 {font_number} 0 R >> >> /Contents {content} 0 R >>",
            ),
        )
    face.write(pdf, font_number)
    kids = " ".join(f"{number} 0 R" for number in page_numbers)
    pdf.put(pages, f"<< /Type /Pages /Kids [{kids}] /Count {len(page_numbers)} >>")

    marks = [
        (
            bookmark,
            page_numbers[starts[bookmark.line] // per_page],
            height - _MARGIN - (starts[bookmark.line] % per_page) * leading,
        )
        for bookmark in sorted(bookmarks, key=lambda bookmark: bookmark.line)
        if 0 <= bookmark.line < len(starts)
    ]
    outlines = f" /Outlines {_write_outlines(pdf, marks)} 0 R /PageMode /UseOutlines" if marks else ""
    pdf.put(catalog, f"<< /Type /Catalog /Pages {pages} 0 R{outlines} >>")
    created = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    info = pdf.add(
        f"<< /Title {_text(title)} /Producer {_text(producer or 'MapTasker')} /CreationDate (D:{created}Z) >>"
    )
    return pdf.serialize(catalog, info)


def _page_content(rows: list[Line], face: _TrueType | _Courier, size: float, height: float) -> bytes:
    """The drawing instructions for one page of rows."""
    commands = [
        "BT",
        f"/F1 {_number(size)} Tf",
        f"{_number(size * _LEADING)} TL",
        f"{_number(_MARGIN)} {_number(height - _MARGIN - size)} Td",
    ]
    color = None
    for row in rows:
        text = row.text.rstrip()
        if text:
            if row.color != color:
                color = row.color
                commands.append(f"{' '.join(_number(part) for part in color)} rg")
            commands.append(f"{face.show(text)} Tj")
        commands.append("T*")
    commands.append("ET")
    return "\n".join(commands).encode("latin-1")


def _write_outlines(pdf: _Objects, marks: list[tuple[Bookmark, int, float]]) -> int:
    """Write the bookmark tree and answer the number of its root.

    Each bookmark sits under the nearest one before it with a lower level.  Everything is
    written closed, so a Map of forty Projects opens as a list of forty Projects.
    """
    root = pdf.reserve()
    tree: list[dict] = []
    open_nodes: list[dict] = []
    for bookmark, page, top in marks:
        node = {"bookmark": bookmark, "page": page, "top": top, "children": [], "number": pdf.reserve()}
        while open_nodes and open_nodes[-1]["bookmark"].level >= bookmark.level:
            open_nodes.pop()
        (open_nodes[-1]["children"] if open_nodes else tree).append(node)
        open_nodes.append(node)
    _write_outline_level(pdf, tree, root)
    pdf.put(
        root, f"<< /Type /Outlines /First {tree[0]['number']} 0 R /Last {tree[-1]['number']} 0 R /Count {len(tree)} >>"
    )
    return root


def _write_outline_level(pdf: _Objects, siblings: list[dict], parent: int) -> None:
    """Write one level of the bookmark tree, and everything under it."""
    for index, node in enumerate(siblings):
        entries = [
            f"/Title {_text(node['bookmark'].title)}",
            f"/Parent {parent} 0 R",
            f"/Dest [{node['page']} 0 R /XYZ {_number(_MARGIN)} {_number(node['top'])} null]",
        ]
        if index:
            entries.append(f"/Prev {siblings[index - 1]['number']} 0 R")
        if index + 1 < len(siblings):
            entries.append(f"/Next {siblings[index + 1]['number']} 0 R")
        children = node["children"]
        if children:
            # A negative count is what marks a bookmark as closed.
            entries.append(
                f"/First {children[0]['number']} 0 R /Last {children[-1]['number']} 0 R /Count -{len(children)}"
            )
            _write_outline_level(pdf, children, node["number"])
        pdf.put(node["number"], f"<< {' '.join(entries)} >>")


# ##################################################################################
# Laying out lines
# ##################################################################################
def _width(face: _TrueType | _Courier, text: str) -> float:
    """How wide `text` is drawn, in thousandths of the font size."""
    return sum(face.char_width(char) for char in text)


def _wrap_lines(lines: list[Line], face: _TrueType | _Courier, limit: float) -> tuple[list[Line], list[int]]:
    """Every line broken to fit `limit`, and the row each line starts on."""
    rows: list[Line] = []
    starts: list[int] = []
    for line in lines:
        starts.append(len(rows))
        rows.extend(Line(piece, line.color) for piece in _wrap(line.text.rstrip(), face, limit))
    return rows, starts


def _wrap(text: str, face: _TrueType | _Courier, limit: float) -> list[str]:
    """`text` in pieces no wider than `limit`, broken at a space where there is one to break at.

    What spills over is indented two columns past where the line itself starts, so a wrapped
    action argument still reads as part of its action.  The indent is capped at half the
    line: text that starts far to the right must not be left one letter a row.
    """
    if _width(face, text) <= limit:
        return [text]
    columns = int(limit / (face.char_width(" ") or 600.0))
    indent = " " * min(len(text) - len(text.lstrip(" ")) + 2, columns // 2)
    pieces = []
    rest, prefix = text, ""
    while rest:
        cut = _fit(rest, face, limit - _width(face, prefix))
        if cut < len(rest):
            space = rest.rfind(" ", 0, cut + 1)
            if space > cut // 2 and rest[:space].strip():
                cut = space
        pieces.append(prefix + rest[:cut].rstrip())
        rest = rest[cut:].lstrip(" ")
        prefix = indent
    return pieces


def _fit(text: str, face: _TrueType | _Courier, room: float) -> int:
    """How many of `text`'s leading characters fit in `room` -- never fewer than one."""
    used = 0.0
    for index, char in enumerate(text):
        used += face.char_width(char)
        if used > room:
            return max(index, 1)
    return len(text)


# ##################################################################################
# PDF syntax
# ##################################################################################
def _number(value: float) -> str:
    """A number as a PDF writes one: no exponent, no trailing zeros."""
    return f"{value:.3f}".rstrip("0").rstrip(".") or "0"


def _name(family: str) -> str:
    """A font family as a PDF name, which may not hold spaces or most punctuation."""
    return "/" + (re.sub(r"[^A-Za-z0-9-]", "", family) or "MapTaskerMono")


def _text(value: str) -> str:
    """A PDF text string, in UTF-16 so that a title can be in any language."""
    return f"<FEFF{value.encode('utf-16-be').hex().upper()}>"
