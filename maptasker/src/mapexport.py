#! /usr/bin/env python3
#                                                                                      #
# mapexport: the Map and the Diagram as Markdown, JSON or PDF.                         #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #

"""The Map and the Diagram, written out in formats that can be read without MapTasker.

Both views already exist as files -- MapTasker.html and MapTasker_Map.txt -- but neither
one travels well.  The Map's HTML is styled for MapTasker's own view (a dark page, hover
tooltips, links into itself), and the Diagram only lines up in a monospaced font with wrap
turned off.  This writes each of them as:

  Markdown  for a wiki page, an issue or a note: a heading per object, with the Task
            actions and the Diagram in code blocks so their alignment survives
  JSON      for a script: the Map as a tree of Projects, Profiles, Tasks, actions and
            Scenes; the Diagram as its lines, plus the Projects, objects and calls drawn in it
  PDF       for printing or sending: searchable text, with a bookmark per object (see mappdf)

Everything is read back from what the view itself was drawn from rather than rebuilt from
the XML.  That is what makes an export of a Map built for one Project hold that one
Project, at the detail level it was drawn with: the export is the view, not a second
rendering of the configuration that might disagree with it.

The Map's HTML is written an entry at a time, one entry to a line, and is read back the
same way.  What an entry is comes from the class its object is drawn with -- projtab,
proftab, tasktab, actiontab, scenetab -- rather than from its words, which are translated.
"""

from __future__ import annotations

import html
import json
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from maptasker.src import diagintr, mapfonts, mappdf
from maptasker.src.mapjump import PROFILE, PROJECT, SCENE, TASK
from maptasker.src.maputil2 import translate_string
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import DIAGRAM_EXPORT_FILE, DIAGRAM_FILE, MAP_EXPORT_FILE, MY_VERSION, logger

# The two views that can be exported.
MAP = "map"
DIAGRAM = "diagram"

# The formats, by file extension, and what the Export menu calls each.
MARKDOWN = "md"
JSON = "json"
PDF = "pdf"
FORMATS = {MARKDOWN: "Markdown (.md)", JSON: "JSON (.json)", PDF: "PDF (.pdf)"}

# The file the Map view is displayed from (see guiwins.NiceGuiTextView.process_data).
MAP_SOURCE = "MapTasker.html"

# Written into every JSON export, so that a script can tell which view it was handed and
# notice a layout newer than the one it was written for.
FORMAT_VERSION = 1

# The kinds of entry the Map is read into, beyond the four objects mapjump names.
ACTION = "action"
SECTION = "section"  # A heading that is not an object: "Projects...", "Tasks not in any Profile".
TEXT = "text"
TABLE = "table"

# How deep each object sits.  A new entry closes everything open at its own depth or deeper,
# which is what ends one Profile's Tasks when the next Profile starts.
_DEPTH = {PROJECT: 1, PROFILE: 2, SCENE: 2, TASK: 3, ACTION: 4}
# A section at the top level is as deep as a Project; one inside a Project, as a Profile.
_TOP_SECTION_DEPTH = 1
_PROJECT_SECTION_DEPTH = 2

# The style of text that names no object although it is drawn at an object's indent -- a
# Task's properties, say.  Never a heading, whatever color it is drawn in.
_DETAIL = "detail"

# Colors for the PDF, dark enough to read on white.  The Map's own colors are chosen against
# the Map's background, which a printed page does not have.
_COLORS = {
    PROJECT: (0.08, 0.24, 0.55),
    PROFILE: (0.05, 0.42, 0.20),
    SCENE: (0.42, 0.13, 0.52),
    TASK: (0.62, 0.22, 0.04),
    SECTION: (0.25, 0.25, 0.25),
    TABLE: (0.25, 0.25, 0.25),
}

# Elements that show a reader nothing: styling, scripts, the page title, and the "Go to top"
# link every object carries.
_INVISIBLE_ELEMENTS = re.compile(
    r"<(style|script|title)\b.*?</\1\s*>|<a\s+href='#the_top'>.*?</a>",
    re.IGNORECASE | re.DOTALL,
)
_TABLE = re.compile(r"<table\b.*?</table\s*>", re.IGNORECASE | re.DOTALL)
_ROW = re.compile(r"<tr\b[^>]*>(.*?)</tr\s*>", re.IGNORECASE | re.DOTALL)
# A tag, quoted attribute values and all: a tooltip's text may hold a ">" of its own.
_TAG_BODY = r"(?:[^>\"']|\"[^\"]*\"|'[^']*')*>"
_CELL = re.compile(rf"<t[dh]\b{_TAG_BODY}(.*?)</t[dh]\s*>", re.IGNORECASE | re.DOTALL)
_TAG = re.compile(rf"<{_TAG_BODY}")
# The tags that end a line where they stand.  The Map writes some of these unclosed and
# with a second tag inside them ("<div <span class=...>"), which _TAG_BODY takes as one tag.
_BREAK = re.compile(rf"<(?:br|hr|/?div|/?p|/?h[1-6]|/?li)\b{_TAG_BODY}", re.IGNORECASE)

# The class an object's heading or an action is drawn with.  Matched as the whole class
# attribute so that a TaskerNet description drawn at a Task's indent ("taskernet_color
# tasktab") is not taken for a Task.
_HEADING = re.compile(
    r'class="(project_color projtab|profile_color proftab|task_color tasktab|scene_color scenetab|action_color actiontab)"',
)
_HEADING_KINDS = {"projtab": PROJECT, "proftab": PROFILE, "tasktab": TASK, "scenetab": SCENE, "actiontab": ACTION}
_NAME = re.compile(r"<em>(.*?)</em>", re.DOTALL)
_ACTION_NUMBER = re.compile(r'actiontab">\s*(\d+)')
_FIRST_COLOR = re.compile(r'class="([a-z_]+)_color')

# The Markdown characters that would otherwise be read as formatting.
_MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]<>#|~])")
# The starts of a line that would make it a list item or a numbered item.
_MARKDOWN_LIST_START = re.compile(r"[-+]\s|\d+[.)]\s")


class ExportError(Exception):
    """There is nothing to export.  The message is written for the user."""


@dataclass
class Block:
    """One entry of the Map: an object's heading, an action, some text, or a table.

    `lines` is the entry's text as the Map draws it, spacing included: the Map is drawn in a
    monospaced font, and the runs of spaces in it are what line an action's arguments up
    under its name.
    """

    kind: str
    lines: list[str] = field(default_factory=list)
    name: str = ""  # The object's name, for a Project, Profile, Task or Scene.
    number: int = 0  # An action's number within its Task.
    rows: list[list[str]] = field(default_factory=list)  # A table's cells.
    style: str = ""  # The color class text is drawn in, which says what a heading is.
    children: list[Block] = field(default_factory=list)


# ##################################################################################
# Reading the Map
# ##################################################################################
def _inline_text(fragment: str) -> str:
    """A fragment of HTML as one line of plain text."""
    return " ".join(html.unescape(_TAG.sub("", fragment)).replace("\xa0", " ").split())


def _text_lines(fragment: str) -> list[str]:
    """What a fragment of the Map reads as, one string per line it is drawn on.

    Blank lines at either end are dropped and runs of them inside are kept as one: the Map
    spaces its entries out with line breaks, which say nothing once the entries are apart.
    """
    text = html.unescape(_TAG.sub("", _BREAK.sub("\n", fragment))).replace("\xa0", " ")
    lines: list[str] = []
    for line in text.split("\n"):
        stripped = line.rstrip()
        if stripped or (lines and lines[-1]):
            lines.append(stripped)
    while lines and not lines[-1]:
        lines.pop()
    return lines


def _entry(fragment: str) -> Block | None:
    """A fragment of the Map as the entry it draws, or None when it draws nothing."""
    lines = _text_lines(fragment)
    if not lines:
        return None
    heading = _HEADING.search(fragment)
    if heading is not None:
        kind = _HEADING_KINDS[heading.group(1).split()[1]]
        if kind == ACTION:
            number = _ACTION_NUMBER.search(fragment, heading.start())
            return Block(ACTION, lines, number=int(number.group(1)) if number else 0)
        name = _NAME.search(fragment, heading.end())
        if name is not None:
            return Block(kind, lines, name=_inline_text(name.group(1)))
        return Block(TEXT, lines, style=_DETAIL)
    color = _FIRST_COLOR.search(fragment)
    return Block(TEXT, lines, style=color.group(1) if color else "")


def map_blocks(document: str) -> list[Block]:
    """The Map's HTML read into its entries, in the order the Map draws them.

    Consecutive text in one color is one entry.  A table is always its own entry, wherever
    on its line it starts.
    """
    # The Map follows its line breaks with a carriage return ("<br>\r").  Read as universal
    # newlines, every one of those would be a line of its own, cutting an entry off from the
    # class it is drawn with -- so the file is read with newline="" (see _read), and returns
    # are dealt with here: after a tag or at the end of a line one says nothing, and anywhere
    # else it is a break in the text it sits in.
    document = re.sub(r"(?<=>)\r|\r(?=\n)", "", document).replace("\r", "<br>")
    document = _INVISIBLE_ELEMENTS.sub("", document)
    # A table is written across many lines but is one entry.
    document = _TABLE.sub(lambda match: match.group(0).replace("\n", " "), document)
    blocks: list[Block] = []
    for line in document.split("\n"):
        position = 0
        pieces = []
        for table in _TABLE.finditer(line):
            pieces.extend([(False, line[position : table.start()]), (True, table.group(0))])
            position = table.end()
        pieces.append((False, line[position:]))

        for is_table, fragment in pieces:
            if is_table:
                rows = [
                    cells
                    for cells in ([_inline_text(cell) for cell in _CELL.findall(row)] for row in _ROW.findall(fragment))
                    if any(cells)
                ]
                if rows:
                    blocks.append(Block(TABLE, rows=rows))
                continue
            entry = _entry(fragment)
            if entry is None:
                continue
            previous = blocks[-1] if blocks else None
            if entry.kind == TEXT and previous is not None and previous.kind == TEXT and previous.style == entry.style:
                previous.lines.extend(entry.lines)
            else:
                blocks.append(entry)
    return blocks


def map_tree(blocks: list[Block]) -> list[Block]:
    """The Map's entries nested the way the Map draws them.

    Projects hold their Profiles, Scenes and Tasks; Profiles hold Tasks; Tasks hold actions.
    Text and tables belong to whatever is open when they appear -- a Task's TaskerNet
    description to the Task, a Scene's elements to the Scene -- with three exceptions,
    each of which changes what is open instead:

      - a heading in the Task color inside a Project ("The following Tasks ... are not in
        any Profile") opens a section, so the Tasks after it are not taken for the last
        Profile's
      - text in the Project color is the heading of the table after it ("Project Global
        Variables", the directory's "Projects...") and opens a section for it; with no table
        after it, inside a Project, it is the Project's own -- its closing summary -- rather
        than its last Scene's
      - text in the trailing-comments color starts again at the top: the totals and notes
        after the last Project

    The tree is built from copies, leaving `blocks` as they were, so it can be built again.
    """
    roots: list[Block] = []
    open_blocks: list[tuple[int, Block]] = []

    def place(block: Block, depth: int) -> None:
        while open_blocks and open_blocks[-1][0] >= depth:
            open_blocks.pop()
        (open_blocks[-1][1].children if open_blocks else roots).append(block)
        open_blocks.append((depth, block))

    def section(block: Block) -> Block:
        heading = Block(SECTION, block.lines)
        heading.name = _heading(heading)
        return heading

    for index, original in enumerate(blocks):
        block = Block(
            original.kind,
            original.lines,
            name=original.name,
            number=original.number,
            rows=original.rows,
            style=original.style,
        )
        if block.kind in _DEPTH:
            place(block, _DEPTH[block.kind])
            continue
        project = next((opened for _, opened in open_blocks if opened.kind == PROJECT), None)
        heads_a_table = index + 1 < len(blocks) and blocks[index + 1].kind == TABLE
        if block.kind == TEXT and block.style == "task" and project is not None:
            place(section(block), _PROJECT_SECTION_DEPTH)
        elif block.kind == TEXT and block.style == "project" and heads_a_table:
            place(section(block), _TOP_SECTION_DEPTH if project is None else _PROJECT_SECTION_DEPTH)
        elif block.kind == TEXT and block.style == "project" and project is not None:
            while open_blocks[-1][1] is not project:
                open_blocks.pop()
            project.children.append(block)
        elif block.kind == TEXT and block.style == "trailing_comments":
            open_blocks.clear()
            roots.append(block)
        else:
            (open_blocks[-1][1].children if open_blocks else roots).append(block)
    return roots


def _heading(block: Block) -> str:
    """The line an object or section is headed by, with single spaces: "Profile: Battery Full"."""
    first = next((line for line in block.lines if line.strip()), block.name)
    heading = " ".join(first.split())
    # A section heading is drawn trailing a row of dots ("Projects.........").
    return heading.rstrip(". ") if block.kind == SECTION else heading


def _body(block: Block) -> list[str]:
    """An object's lines after its heading: a Profile's conditions, a Task's priority."""
    for index, line in enumerate(block.lines):
        if line.strip():
            return block.lines[index + 1 :]
    return []


def _dedent(lines: list[str]) -> list[str]:
    """`lines` with the indentation they all share taken off."""
    indent = min((len(line) - len(line.lstrip(" ")) for line in lines if line.strip()), default=0)
    return [line[indent:] for line in lines]


# ##################################################################################
# Shared
# ##################################################################################
def metadata(view: str) -> dict:
    """What every export says about itself: which view, which MapTasker, when, and from what.

    The source is the backup file's name without its folder.  An export is made to be passed
    around, and a full path would carry the name of the account it was made on.
    """
    source = getattr(PrimeItems.file_to_get, "name", PrimeItems.file_to_get)
    return {
        "format": f"maptasker-{view}",
        "format_version": FORMAT_VERSION,
        "generator": MY_VERSION,
        "exported": datetime.now(UTC).astimezone().isoformat(timespec="seconds"),
        "source": os.path.basename(source) if isinstance(source, str) else "",
    }


def _details(meta: dict) -> list[str]:
    """The metadata as lines a person reads."""
    details = [
        f"{translate_string('Generator')}: {meta['generator']}",
        f"{translate_string('Exported')}: {meta['exported']}",
    ]
    if meta["source"]:
        details.append(f"{translate_string('Source')}: {meta['source']}")
    return details


def _font(text: str) -> mapfonts.EmbeddableFont | None:
    """The font a PDF of `text` is drawn in, or None to fall back on Courier."""
    font = mapfonts.embeddable_font(text, PrimeItems.program_arguments.get("font", ""))
    if font is None:
        logger.info("PDF export: no monospaced TrueType font found, so drawing characters become ASCII in Courier.")
    return font


def _escape(text: str) -> str:
    """`text` for Markdown, where it should read as it is written rather than as formatting."""
    escaped = _MARKDOWN_SPECIAL.sub(r"\\\1", text)
    return f"\\{escaped}" if _MARKDOWN_LIST_START.match(escaped) else escaped


def _code_block(lines: list[str], out: list[str]) -> None:
    """`lines` as a Markdown code block, whose fence nothing inside it can close early."""
    fence = "```"
    while any(line.lstrip().startswith(fence) for line in lines):
        fence += "`"
    out.extend([f"{fence}text", *lines, fence, ""])


def _paragraphs(lines: list[str], out: list[str]) -> None:
    """Lines of text as Markdown paragraphs, broken where the Map breaks them."""
    paragraph: list[str] = []
    for line in [*lines, ""]:
        if line.strip():
            paragraph.append(_escape(" ".join(line.split())))
        elif paragraph:
            # Two trailing spaces: the hard line break every Markdown dialect understands.
            out.extend(["  \n".join(paragraph), ""])
            paragraph = []


def _markdown_document(title: str, meta: dict) -> list[str]:
    """The top of a Markdown export: its title and what it was made from."""
    return [f"# {title}", "", *(f"- {_escape(detail)}" for detail in _details(meta)), ""]


def _finish(out: list[str]) -> str:
    """Markdown lines as the file's text, ending in exactly one newline."""
    return "\n".join(out).rstrip() + "\n"


# ##################################################################################
# The Map, written out
# ##################################################################################
def map_markdown(blocks: list[Block], meta: dict) -> str:
    """The Map as Markdown: a heading per object, each Task's actions in a code block."""
    out = _markdown_document(translate_string("MapTasker Map"), meta)
    _markdown_children(map_tree(blocks), out, 2)
    return _finish(out)


def _markdown_children(children: list[Block], out: list[str], level: int) -> None:
    """Entries as Markdown, a Task's actions gathered into one code block."""
    index = 0
    while index < len(children):
        if children[index].kind == ACTION:
            actions: list[str] = []
            while index < len(children) and children[index].kind == ACTION:
                actions.extend(children[index].lines)
                index += 1
            _code_block(actions, out)
            continue
        block = children[index]
        if block.kind == TABLE:
            _markdown_table(block.rows, out)
        elif block.kind == TEXT:
            _paragraphs(block.lines, out)
        else:
            # Markdown has six levels of heading; anything deeper shares the sixth.
            out.extend([f"{'#' * min(level, 6)} {_escape(_heading(block))}", ""])
            _paragraphs(_body(block), out)
        _markdown_children(block.children, out, level + 1)
        index += 1


def _markdown_table(rows: list[list[str]], out: list[str]) -> None:
    """A table of the Map as a Markdown table.  Markdown requires a header, so the first row is it."""
    width = max(len(row) for row in rows)
    cells = [[_escape(cell) for cell in row] + [""] * (width - len(row)) for row in rows]
    out.append(f"| {' | '.join(cells[0])} |")
    out.append(f"|{' --- |' * width}")
    out.extend(f"| {' | '.join(row)} |" for row in cells[1:])
    out.append("")


def map_json(blocks: list[Block], meta: dict) -> str:
    """The Map as JSON: the metadata, and the Map's entries as a tree under "entries".

    Every entry has a "kind" -- project, profile, task, action, scene, section, text or
    table.  Objects and sections have a "name", actions a "number", tables their "rows" and
    everything else its "lines"; anything with entries of its own has "children".
    """
    return (
        json.dumps(
            {**meta, "entries": [_json_entry(block) for block in map_tree(blocks)]}, ensure_ascii=False, indent=2
        )
        + "\n"
    )


def _json_entry(block: Block) -> dict:
    """One entry of the Map, and everything under it, as JSON-ready data."""
    entry: dict = {"kind": block.kind}
    if block.kind in (PROJECT, PROFILE, TASK, SCENE, SECTION):
        entry["name"] = block.name
    if block.kind == ACTION:
        entry["number"] = block.number
    if block.kind == TABLE:
        entry["rows"] = block.rows
    else:
        entry["lines"] = _dedent(block.lines)
    if block.children:
        entry["children"] = [_json_entry(child) for child in block.children]
    return entry


def map_pdf(blocks: list[Block], meta: dict) -> bytes:
    """The Map as a PDF: indented by depth, headings in color, a bookmark for every object."""
    title = translate_string("MapTasker Map")
    lines = [mappdf.Line(title, _COLORS[PROJECT]), *(mappdf.Line(detail) for detail in _details(meta))]
    bookmarks: list[mappdf.Bookmark] = []
    _pdf_lines(map_tree(blocks), lines, bookmarks, 0)
    return mappdf.render(
        lines,
        title=title,
        font=_font("".join(line.text for line in lines)),
        bookmarks=bookmarks,
        producer=meta["generator"],
    )


def _pdf_lines(blocks: list[Block], lines: list[mappdf.Line], bookmarks: list[mappdf.Bookmark], depth: int) -> None:
    """Entries as lines of the PDF, two columns further in for each level down."""
    indent = "  " * depth
    for block in blocks:
        color = _COLORS.get(block.kind, mappdf.BLACK)
        if block.kind in (PROJECT, PROFILE, SCENE, TASK, SECTION):
            if lines and lines[-1].text:
                lines.append(mappdf.Line(""))
            bookmarks.append(mappdf.Bookmark(_heading(block), len(lines), depth))
        if block.kind == TABLE:
            lines.extend(
                mappdf.Line(indent + row, color) for row in _table_rows(block.rows, _PDF_COLUMNS - len(indent))
            )
        else:
            lines.extend(mappdf.Line(f"{indent}{text}" if text else "", color) for text in _dedent(block.lines))
        _pdf_lines(block.children, lines, bookmarks, depth + 1)


# About how many columns of text a Letter page holds at the PDF's 8 points, with room to spare.
_PDF_COLUMNS = 100


def _table_rows(rows: list[list[str]], columns: int) -> list[str]:
    """A table as lines of text: its columns lined up if that fits in `columns`, and otherwise not.

    Lined-up columns too wide for the page are wrapped by it, which leaves every row's
    padding in the wrong place -- harder to read than no padding at all.  Unpadded, a row
    reads as a list, and the empty cells that only filled out the grid are left out.
    """
    widths = [
        max(len(row[column]) for row in rows if column < len(row)) for column in range(max(len(row) for row in rows))
    ]
    if sum(widths) + 3 * (len(widths) - 1) <= columns:
        return [" | ".join(cell.ljust(widths[column]) for column, cell in enumerate(row)).rstrip() for row in rows]
    return [" | ".join(cell for cell in row if cell) for row in rows]


# ##################################################################################
# The Diagram, written out
# ##################################################################################
def diagram_contents(model: dict) -> dict:
    """What the Diagram draws, by name: its Projects, every drawing of an object, every call.

    Lines count from 0 and columns in characters, both into the Diagram's lines -- the same
    coordinates the Diagram view works in (see diagintr).  A call drawn more than once (a
    Task run by several Profiles is drawn under each, and its calls with it) is listed once.
    """
    nodes = model.get("nodes", [])
    by_anchor: dict[str, dict] = {}
    for node in nodes:
        by_anchor.setdefault(node["anchor"], node)
    calls: list[dict] = []
    for edge in model.get("edges", []):
        caller, called = by_anchor.get(edge["caller"]), by_anchor.get(edge["called"])
        if caller is None or called is None:
            continue
        call = {
            "caller": caller["name"],
            "caller_project": caller["project"],
            "called": called["name"],
            "called_project": called["project"],
        }
        if call not in calls:
            calls.append(call)
    return {
        "projects": [
            {"name": region["name"], "start": region["start"], "end": region["end"]}
            for region in model.get("regions", [])
        ],
        "objects": [
            {
                "kind": node["kind"],
                "name": node["name"],
                "project": node["project"],
                "line": node["line"],
                "column": node["col"],
                "length": node["len"],
            }
            for node in nodes
        ],
        "calls": calls,
    }


def diagram_markdown(lines: list[str], model: dict, meta: dict) -> str:
    """The Diagram as Markdown: its Projects and calls as lists, the drawing in a code block."""
    contents = diagram_contents(model)
    out = _markdown_document(translate_string("MapTasker Diagram"), meta)
    if contents["projects"]:
        out.extend([f"## {translate_string('Projects')}", ""])
        out.extend(f"- {_escape(project['name'])}" for project in contents["projects"])
        out.append("")
    if contents["calls"]:
        out.extend([f"## {translate_string('Calls')}", ""])
        out.extend(f"- {_escape(call['caller'])} → {_escape(call['called'])}" for call in contents["calls"])
        out.append("")
    out.extend([f"## {translate_string('Diagram')}", ""])
    _code_block(lines, out)
    return _finish(out)


def diagram_json(lines: list[str], model: dict, meta: dict) -> str:
    """The Diagram as JSON: the metadata, what it draws (see diagram_contents), and its lines."""
    return json.dumps({**meta, **diagram_contents(model), "lines": lines}, ensure_ascii=False, indent=2) + "\n"


def diagram_pdf(lines: list[str], model: dict, meta: dict) -> bytes:
    """The Diagram as a PDF: pages as wide as its widest line, and a bookmark for each Project."""
    return mappdf.render(
        [mappdf.Line(line) for line in lines],
        title=translate_string("MapTasker Diagram"),
        font=_font("".join(lines)),
        bookmarks=[mappdf.Bookmark(region["name"], region["start"]) for region in model.get("regions", [])],
        wrap=False,
        page_size=mappdf.LETTER_LANDSCAPE,
        font_size=7.0,
        producer=meta["generator"],
    )


# ##################################################################################
# Exporting a view
# ##################################################################################
_MAP_WRITERS = {MARKDOWN: map_markdown, JSON: map_json, PDF: map_pdf}
_DIAGRAM_WRITERS = {MARKDOWN: diagram_markdown, JSON: diagram_json, PDF: diagram_pdf}


def _read(path: str, missing: str) -> str:
    """The text of the file a view was drawn from, or an ExportError saying `missing`."""
    try:
        # newline="" leaves carriage returns where they are rather than making lines of them
        # -- see map_blocks.
        with open(path, encoding="utf-8", errors="replace", newline="") as source:
            return source.read()
    except FileNotFoundError as error:
        message = translate_string(missing)
        raise ExportError(message) from error


def export_view(view: str, fmt: str) -> str:
    """Write the Map or the Diagram, as last built, in format `fmt`, and answer the path written.

    Read from and written to the current directory, which is where the views are built.
    Raises ExportError when the view has not been built, and lets OSError through when the
    export cannot be written.
    """
    if view not in (MAP, DIAGRAM) or fmt not in FORMATS:
        message = f"Cannot export {view!r} as {fmt!r}"
        raise ValueError(message)
    directory = os.getcwd()
    meta = metadata(view)
    if view == MAP:
        document = _read(os.path.join(directory, MAP_SOURCE), "There is no Map to export.  Display the Map first.")
        content = _MAP_WRITERS[fmt](map_blocks(document), meta)
        stem = MAP_EXPORT_FILE
    else:
        text = _read(
            os.path.join(directory, DIAGRAM_FILE),
            "There is no Diagram to export.  Display the Diagram first.",
        )
        # Split on newlines alone, once a Windows line ending is one: the model's line numbers
        # count the file's lines, and str.splitlines would also break at the separators
        # Unicode defines.
        lines = text.replace("\r\n", "\n").split("\n")
        if lines and not lines[-1]:
            lines.pop()
        content = _DIAGRAM_WRITERS[fmt](lines, diagintr.model(), meta)
        stem = DIAGRAM_EXPORT_FILE

    path = os.path.join(directory, f"{stem}.{fmt}")
    if isinstance(content, bytes):
        with open(path, "wb") as output:
            output.write(content)
    else:
        with open(path, "w", encoding="utf-8", newline="\n") as output:
            output.write(content)
    return path
