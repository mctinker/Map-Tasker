"""MapTasker export (mapexport, mappdf) Unit Tests

An export is read back out of what its view was drawn from -- MapTasker.html for the Map,
the Diagram's text file and model for the Diagram -- so the fixture here is written in the
Map's own markup, including the parts of it that are not well-formed ("<div <span ...>",
a <DIV> left open), since that is what the reader has to get through.

The PDF is checked the way a viewer reads one: through its cross-reference table.  An
offset that is a byte out opens as a damaged file, and nothing else would notice.
"""

from __future__ import annotations

import json
import os
import re
import zlib

import pytest
from maptasker.src import mapexport, mapfonts, mappdf
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import DIAGRAM_FILE

# One Project, holding a Profile with a Task, a Task in no Profile, and a Scene -- with the
# directory before it and the totals after, which belong to no Project.
_MAP_HTML = """<span class="normtab"></span><!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8"><title>MapTasker</title>
<body style="background-color:#182533">
<span class="heading_color"><h2>MapTasker</h2><br>Tasker Mapping................ Tasker XML version: 6.7.6</span><br>
<style  type="text/css">
.project_color {color: White;}
</style>
<span class="project_color"><span class="normtab"></span>Projects............<br><br></span>
<span class="profile_color">
<table style="width:100%">
  <tr>
    <td><a href=#projects_Home>Home</a></td>
    <td><a href=#projects_Work>Work</a></td>
  </tr>
</table></span>
<hr><br><br>
<a id="mt-project-Home" class="mt-anchor"></a>
<br><span class="project_color projtab"><span class="hover-tooltip" data-tooltip="Profiles: a &gt; b">Project:</span> <em>Home</em></span> &nbsp;&nbsp;<a href='#the_top'>Go to top</a><br>
<br><div <span class="profile_color proftab"><span class="hover-tooltip" data-tooltip="Project: Home">Profile:</span> <em>*Battery Full</em> </span> <span class="profile_condition_color"><br>&nbsp;&nbsp;&nbsp;(State: Battery Level  From=80<br>&nbsp;&nbsp;&nbsp;&nbsp;To=80  )</span>&nbsp;&nbsp;<a href='#the_top'>Go to top</a><br></span></div>
<div><span class="task_color tasktab"><span class="hover-tooltip" data-tooltip="Profile: *Battery Full">Task:</span>&nbsp;<em>Alert</em>&nbsp;&nbsp;&nbsp;&#11013; Entry Task&nbsp;<br>&nbsp;&nbsp;[Priority: 6]&nbsp;<a href='#the_top'>Go to top</a><br></span></div>
<span class="taskernet_color tasktab"></span><div class="text-box"><p><br><span class="h6-text">TaskerNet description: Battery full.</span></p></div>
<span class="normtab"></span><br><div id="mt-task-18-a1" <span class="action_color actiontab">01:</span> <span class="action_name_color">If</span><span class="action_color"> (%LEVEL &gt; 79)</span></div><br>
<div id="mt-task-18-a2" <span class="action_color actiontab">02:</span> <span class="action_name_color">&nbsp;&nbsp;&nbsp;&nbsp;Say</span><span class="action_color">&nbsp;&nbsp;Text=Full<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Engine=default</span></div><br>
<div id="mt-task-18-a3" <span class="action_color actiontab">03:</span> <span class="action_name_color">End If</span></span></div><br>
<span class="normtab"></span><span class="task_color"><br>&nbsp;&nbsp;&nbsp;The following Tasks in Project 'Home' are not in any Profile...</span><br>
<div><span class="task_color tasktab"><span class="hover-tooltip" data-tooltip="Project: Home">Task:</span>&nbsp;<em>Loose</em>&nbsp;<br></span></div>
<div><span class="task_color tasktab"><span class="task_color"><br>Task: Properties...Keep Device Awake:true<br></span></span></div>
<div id="mt-task-9-a1" <span class="action_color actiontab">01:</span> <span class="action_name_color">Beep</span></div><br>
<br><div><div><span class="scene_color scenetab"><span class="hover-tooltip" data-tooltip="Project: Home">Scene:</span>&nbsp;<em>Popup</em>&nbsp;<a href='#the_top'>Go to top</a><br></span></div>
</div><span class="normtab"></span><span class="scene_color">&nbsp;&nbsp;Width/Height: 300 X 500<br></span>
<br><span class="normtab"></span><br><span class="project_color"><br><span class="normtab"></span>Project Global Variables</span>

<style> table, td, th { padding: 5px; } </style><table cellspacing="1" style="text-align:left">
<tr>
<th>Name</th>
<th>Value</th>
</tr>
<tr id="mt-variable-%25Level"><td style="color:White">%Level</td><td style="color:White">80</td></tr>
</table><br>
<span class="project_color"><DIV <span class="normtab"></span><br>Project Home has a total of 1 Profiles and 1 Scenes</DIV><br><br></span>
<hr>
<a id="grand_totals"></a>
<span class="trailing_comments_color"><br><hr><span class="normtab"></span>Tasker Displayed Totals...<br>Total number of Projects: 1</span><br>
</body>
</html>
"""

_ACTIONS = ["01: If (%LEVEL > 79)", "02:     Say  Text=Full", "            Engine=default", "03: End If"]

# A Diagram of one Project whose Task calls another -- drawn twice, as a call is under every
# Profile that runs its Task -- and the model diagram.network_map would have recorded for it.
_DIAGRAM_LINES = [
    "MapTasker version 14.0.2     Configuration Map",
    "     ╔═══════════════╗",
    "     ║ Project: Test ║",
    "     ╚═══════════════╝",
    "            └─ Caller [Calls ──▶ Callee]",
    "            └─ Callee [Called by ◄── Caller]",
]
_DIAGRAM_MODEL = {
    "regions": [{"anchor": "p", "name": "Test", "line": 2, "start": 1, "fold": 4, "end": 5}],
    "nodes": [
        {"anchor": "p", "kind": "project", "name": "Test", "line": 2, "col": 16, "len": 4, "project": "Test"},
        {"anchor": "t1", "kind": "task", "name": "Caller", "line": 4, "col": 15, "len": 6, "project": "Test"},
        {"anchor": "t2", "kind": "task", "name": "Callee", "line": 5, "col": 15, "len": 6, "project": "Test"},
    ],
    "edges": [{"caller": "t1", "called": "t2", "groups": [0]}, {"caller": "t1", "called": "t2", "groups": [1]}],
}


@pytest.fixture
def meta() -> dict:
    """The metadata an export of the Map carries."""
    return mapexport.metadata(mapexport.MAP)


@pytest.fixture
def no_system_fonts(monkeypatch: pytest.MonkeyPatch) -> None:
    """PDFs drawn in Courier, whatever fonts this machine has -- quick, and the same everywhere."""
    monkeypatch.setattr(mapfonts, "embeddable_font", lambda *_args, **_kwargs: None)


def _child(block: mapexport.Block, kind: str) -> mapexport.Block:
    """The first entry of `kind` directly under `block`."""
    return next(child for child in block.children if child.kind == kind)


# ##################################################################################
# Reading the Map
# ##################################################################################
def test_every_object_is_read_with_its_name() -> None:
    """Objects come from the class they are drawn with; a heading naming no object is text."""
    objects = [
        (block.kind, block.name)
        for block in mapexport.map_blocks(_MAP_HTML)
        if block.kind in ("project", "profile", "task", "scene")
    ]
    # "Task: Properties..." is drawn at a Task's indent but is the Task's details, and the
    # TaskerNet description (taskernet_color tasktab) is not a Task either.
    assert objects == [("project", "Home"), ("profile", "*Battery Full"), ("task", "Alert"), ("task", "Loose"), ("scene", "Popup")]


def test_actions_keep_their_numbers_and_alignment() -> None:
    """The Map's runs of spaces are what line an action's arguments up; they are kept."""
    actions = [block for block in mapexport.map_blocks(_MAP_HTML) if block.kind == mapexport.ACTION]
    assert [action.number for action in actions] == [1, 2, 3, 1]
    assert [line for action in actions[:3] for line in action.lines] == _ACTIONS


def test_what_shows_nothing_is_left_out() -> None:
    """Styling, tooltips and "Go to top" links are not part of what the Map reads as."""
    text = "\n".join(line for block in mapexport.map_blocks(_MAP_HTML) for line in block.lines)
    assert "Go to top" not in text
    assert "color: White" not in text
    assert "Profiles: a > b" not in text


def test_entries_nest_the_way_the_map_draws_them() -> None:
    """Profiles under their Project, Tasks under their Profile, actions under their Task."""
    roots = mapexport.map_tree(mapexport.map_blocks(_MAP_HTML))
    assert [root.kind for root in roots] == ["text", "section", "project", "text"]

    directory = roots[1]
    assert directory.name == "Projects"
    assert _child(directory, "table").rows == [["Home", "Work"]]

    project = roots[2]
    assert [(child.kind, child.name) for child in project.children[:3]] == [
        ("profile", "*Battery Full"),
        ("section", "The following Tasks in Project 'Home' are not in any Profile"),
        ("scene", "Popup"),
    ]
    task = _child(_child(project, "profile"), "task")
    assert task.name == "Alert"
    assert [child.kind for child in task.children] == ["text", "action", "action", "action"]


def test_tasks_in_no_profile_are_not_taken_for_the_last_profiles() -> None:
    """The "not in any Profile" heading is what separates them from the Profile above."""
    project = mapexport.map_tree(mapexport.map_blocks(_MAP_HTML))[2]
    assert [task.name for task in _child(project, "profile").children] == ["Alert"]
    loose = _child(_child(project, "section"), "task")
    assert loose.name == "Loose"
    assert [child.kind for child in loose.children] == ["text", "action"]


def test_a_projects_variables_and_summary_stay_in_the_project() -> None:
    """A table after a Project-colored heading is that heading's; the summary is the Project's.

    Neither may be filed under the Project's last Scene, which is what is open when they appear.
    """
    roots = mapexport.map_tree(mapexport.map_blocks(_MAP_HTML))
    project = roots[2]
    variables = project.children[-2]
    assert (variables.kind, variables.name) == ("section", "Project Global Variables")
    assert _child(variables, "table").rows == [["Name", "Value"], ["%Level", "80"]]
    assert project.children[-1].lines == ["Project Home has a total of 1 Profiles and 1 Scenes"]
    assert [child.lines for child in _child(project, "scene").children] == [["  Width/Height: 300 X 500"]]
    assert roots[-1].lines == ["Tasker Displayed Totals...", "Total number of Projects: 1"]


def test_carriage_returns_after_breaks_change_nothing() -> None:
    """The Map writes a carriage return after each "<br>"; the Map reads the same with them."""
    with_returns = _MAP_HTML.replace("<br>", "<br>" + chr(13)).replace("\n", chr(13) + "\n", 3)

    def shape(blocks: list[mapexport.Block]) -> list:
        return [(block.kind, block.name, block.lines, block.rows) for block in blocks]

    assert shape(mapexport.map_blocks(with_returns)) == shape(mapexport.map_blocks(_MAP_HTML))


def test_a_carriage_return_inside_text_breaks_the_line() -> None:
    """One that follows no tag is a line break in the text, not the end of the entry."""
    blocks = mapexport.map_blocks(_MAP_HTML.replace("Text=Full", "Text=Full" + chr(13) + "and more"))
    say = next(block for block in blocks if block.kind == mapexport.ACTION and block.number == 2)
    assert say.lines == ["02:     Say  Text=Full", "and more", "            Engine=default"]


def test_the_tree_can_be_built_again() -> None:
    """Building the tree leaves the entries alone, so a second export of them is not doubled."""
    blocks = mapexport.map_blocks(_MAP_HTML)
    first = mapexport.map_json(blocks, {})
    assert mapexport.map_json(blocks, {}) == first


# ##################################################################################
# The Map, written out
# ##################################################################################
def test_map_markdown(meta: dict) -> None:
    """A heading per object, the actions in one code block, the directory as a table."""
    markdown = mapexport.map_markdown(mapexport.map_blocks(_MAP_HTML), meta)
    assert markdown.startswith("# MapTasker Map\n")
    for heading in (
        "## Projects",
        "## Project: Home",
        "### Profile: \\*Battery Full",
        "#### Task: Alert ⬅ Entry Task",
        "### The following Tasks in Project 'Home' are not in any Profile",
        "#### Task: Loose",
        "### Scene: Popup",
    ):
        assert f"\n{heading}\n" in markdown
    assert "\n```text\n" + "\n".join(_ACTIONS) + "\n```\n" in markdown
    assert "| Home | Work |\n| --- | --- |" in markdown
    # Written as the Map shows it, not read as Markdown formatting.
    assert "\\[Priority: 6\\]" in markdown
    assert "(State: Battery Level From=80  \nTo=80 )" in markdown


def test_map_json(meta: dict) -> None:
    """The same tree, with names, action numbers and lines a script can use."""
    document = json.loads(mapexport.map_json(mapexport.map_blocks(_MAP_HTML), meta))
    assert document["format"] == "maptasker-map"
    assert document["format_version"] == mapexport.FORMAT_VERSION
    project = next(entry for entry in document["entries"] if entry["kind"] == "project")
    assert project["name"] == "Home"
    profile = project["children"][0]
    assert profile["lines"] == ["Profile: *Battery Full", "   (State: Battery Level  From=80", "    To=80  )"]
    task = profile["children"][0]
    actions = [child for child in task["children"] if child["kind"] == "action"]
    assert [action["number"] for action in actions] == [1, 2, 3]
    assert actions[1]["lines"] == ["02:     Say  Text=Full", "            Engine=default"]


def test_map_pdf_bookmarks_every_object(meta: dict, no_system_fonts: None) -> None:
    """One bookmark per Project, Profile, Task, Scene and section, nested as the Map is."""
    pdf = mapexport.map_pdf(mapexport.map_blocks(_MAP_HTML), meta)
    objects = _objects(pdf)
    titles = [_title(body) for body in objects.values() if b"/Parent" in body and b"/Title" in body]
    assert titles == [
        "Projects",
        "Project: Home",
        "Profile: *Battery Full",
        "Task: Alert ⬅ Entry Task",
        "The following Tasks in Project 'Home' are not in any Profile",
        "Task: Loose",
        "Scene: Popup",
        "Project Global Variables",
    ]


def test_a_table_is_lined_up_only_when_it_fits_the_page(meta: dict, no_system_fonts: None) -> None:
    """Padding that the page then wraps is worse than none, so a wide table goes unpadded."""
    content = _content(_objects(mapexport.map_pdf(mapexport.map_blocks(_MAP_HTML), meta)))
    assert b"(    Name   | Value) Tj" in content
    assert b"(    %Level | 80) Tj" in content

    wide = "<table><tr>" + "".join(f"<td>{letter * 40}</td>" for letter in "ABC") + "<td></td></tr></table>"
    content = _content(_objects(mapexport.map_pdf(mapexport.map_blocks(wide), meta)))
    rows = " ".join(row.decode() for row in re.findall(rb"\((.*?)\) Tj", content))
    assert " ".join(rows.split()).endswith(f"{'A' * 40} | {'B' * 40} | {'C' * 40}")


def test_the_source_is_named_without_its_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    """An export gets passed around; the folder it was made in is the maker's business."""
    monkeypatch.setattr(PrimeItems, "file_to_get", os.path.join("Users", "someone", "backup.xml"))
    assert mapexport.metadata(mapexport.MAP)["source"] == "backup.xml"


# ##################################################################################
# The Diagram, written out
# ##################################################################################
def test_diagram_markdown_keeps_the_drawing_exact(meta: dict) -> None:
    """The drawing goes in a code block untouched; its calls are listed once each."""
    markdown = mapexport.diagram_markdown(_DIAGRAM_LINES, _DIAGRAM_MODEL, meta)
    assert "\n```text\n" + "\n".join(_DIAGRAM_LINES) + "\n```\n" in markdown
    assert "\n## Projects\n\n- Test\n" in markdown
    assert markdown.count("Caller → Callee") == 1


def test_a_fence_in_the_drawing_cannot_close_the_code_block(meta: dict) -> None:
    """A Task named with backticks would otherwise end the code block partway down."""
    lines = ["```Odd Task```", "plain"]
    markdown = mapexport.diagram_markdown(lines, {}, meta)
    assert "\n````text\n```Odd Task```\nplain\n````\n" in markdown


def test_diagram_json(meta: dict) -> None:
    """Projects, objects and calls by name, in the lines' own coordinates."""
    document = json.loads(mapexport.diagram_json(_DIAGRAM_LINES, _DIAGRAM_MODEL, meta))
    assert document["lines"] == _DIAGRAM_LINES
    assert document["projects"] == [{"name": "Test", "start": 1, "end": 5}]
    assert document["calls"] == [
        {"caller": "Caller", "caller_project": "Test", "called": "Callee", "called_project": "Test"},
    ]
    caller = document["objects"][1]
    line = document["lines"][caller["line"]]
    assert line[caller["column"] : caller["column"] + caller["length"]] == "Caller"


def test_diagram_pdf_is_as_wide_as_the_drawing(meta: dict, no_system_fonts: None) -> None:
    """No line of a Diagram is broken, so the page widens to hold the longest one."""
    lines = [*_DIAGRAM_LINES, "─" * 400]
    objects = _objects(mapexport.diagram_pdf(lines, _DIAGRAM_MODEL, meta))
    width = float(re.search(rb"/MediaBox \[0 0 ([\d.]+)", _body_of_type(objects, b"/Page ")).group(1))
    # 400 Courier columns at 7 points, 0.6 of the size each, and a half-inch margin a side.
    assert width == pytest.approx(400 * 7 * 0.6 + 72)
    content = _content(objects)
    assert b"(" + b"-" * 400 + b") Tj" in content
    # With no font to draw box characters in, the nearest ASCII stands in, column for column.
    assert b"(     +===============+) Tj" in content


# ##################################################################################
# The PDF itself
# ##################################################################################
def _objects(pdf: bytes) -> dict[int, bytes]:
    """Every object in `pdf`, found through its cross-reference table."""
    assert pdf.startswith(b"%PDF-1.7\n")
    start = int(re.search(rb"startxref\n(\d+)\n%%EOF\n$", pdf).group(1))
    table = pdf[start:].split(b"\n")
    assert table[0] == b"xref"
    size = int(table[1].split()[1])
    offsets = {}
    for number in range(1, size):
        entry = table[2 + number] + b"\n"
        assert len(entry) == 20, "every cross-reference entry is 20 bytes"
        offsets[number] = int(entry[:10])
        assert pdf.startswith(f"{number} 0 obj\n".encode(), offsets[number])
    ends = [*sorted(offsets.values())[1:], start]
    by_offset = dict(zip(sorted(offsets.values()), ends, strict=True))
    return {number: pdf[offset : by_offset[offset]] for number, offset in offsets.items()}


def _stream(body: bytes) -> bytes:
    """The decompressed contents of a stream object."""
    return zlib.decompress(body[body.index(b"stream\n") + 7 : body.rindex(b"\nendstream")])


def _body_of_type(objects: dict[int, bytes], marker: bytes) -> bytes:
    """The first object whose dictionary holds `marker`."""
    return next(body for body in objects.values() if marker in body)


def _content(objects: dict[int, bytes], page: int = 0) -> bytes:
    """The drawing instructions of the page at index `page`."""
    kids = [int(number) for number in re.findall(rb"(\d+) 0 R", re.search(rb"/Kids \[([^\]]*)\]", _body_of_type(objects, b"/Type /Pages")).group(1))]
    contents = int(re.search(rb"/Contents (\d+) 0 R", objects[kids[page]]).group(1))
    return _stream(objects[contents])


def _title(body: bytes) -> str:
    """A bookmark's title, out of its UTF-16 hex string."""
    return bytes.fromhex(re.search(rb"/Title <FEFF([0-9A-F]*)>", body).group(1).decode()).decode("utf-16-be")


def test_long_lines_wrap_under_where_they_start() -> None:
    """A line too wide for the page continues on the next, indented past its own start."""
    text = "  " + "word " * 60
    content = _content(_objects(mappdf.render([mappdf.Line(text)], title="Wrap", font=None)))
    rows = [row.decode() for row in re.findall(rb"\((.*?)\) Tj", content)]
    # A Letter page less its margins holds 112 columns of 8 point Courier.
    assert len(rows) == 3
    assert all(len(row) <= 112 for row in rows)
    assert rows[0].startswith("  word")
    assert all(row.startswith("    word") for row in rows[1:])
    assert " ".join(" ".join(rows).split()) == " ".join(text.split())


def test_a_bookmark_leads_to_the_page_its_line_is_on() -> None:
    """75 lines of 8 point text fit a Letter page, so line 150 starts the third."""
    lines = [mappdf.Line(f"line {number}") for number in range(200)]
    objects = _objects(mappdf.render(lines, title="Pages", font=None, bookmarks=[mappdf.Bookmark("Here", 150)]))
    kids = re.findall(rb"(\d+) 0 R", re.search(rb"/Kids \[([^\]]*)\]", _body_of_type(objects, b"/Type /Pages")).group(1))
    assert len(kids) == 3
    item = _body_of_type(objects, b"/Title")
    assert re.search(rb"/Dest \[(\d+) 0 R", item).group(1) == kids[2]
    assert _body_of_type(objects, b"/Type /Catalog").count(b"/Outlines") == 1


def test_colors_and_escapes_in_courier() -> None:
    """A color is set only when it changes, and PDF string syntax is escaped."""
    lines = [mappdf.Line("a (b) \\ c", (1.0, 0.0, 0.0)), mappdf.Line("same", (1.0, 0.0, 0.0)), mappdf.Line("black")]
    content = _content(_objects(mappdf.render(lines, title="Colors", font=None)))
    assert content.count(b" rg") == 2
    assert b"(a \\(b\\) \\\\ c) Tj" in content


def test_an_embedded_font_draws_the_diagram_searchably() -> None:
    """With a TrueType font, box characters are drawn as themselves and map back to text."""
    font = mapfonts.embeddable_font("╔═║▶")
    if font is None:
        pytest.skip("No monospaced TrueType font is installed on this machine.")

    # The face stands on its own: the tables a .ttc shares between faces were copied out.
    directory = mapfonts._table_directory(font.sfnt, 0)
    assert b"glyf" in directory
    assert mapfonts._read_cmap(font.sfnt, directory) == font.cmap

    objects = _objects(mappdf.render([mappdf.Line("║ Project: Test ║")], title="Font", font=font))
    assert b"/FontFile2" in _body_of_type(objects, b"/Type /FontDescriptor")
    wall = f"{font.cmap[0x2551]:04X}".encode()
    assert wall in _content(objects)
    to_unicode = int(re.search(rb"/ToUnicode (\d+) 0 R", _body_of_type(objects, b"/Subtype /Type0")).group(1))
    assert b"<" + wall + b"> <2551>" in _stream(objects[to_unicode])


# ##################################################################################
# Exporting a view
# ##################################################################################
def test_export_view_writes_each_format(monkeypatch: pytest.MonkeyPatch, tmp_path: os.PathLike, no_system_fonts: None) -> None:
    """Each view, in each format, from the file it is displayed from."""
    monkeypatch.chdir(tmp_path)
    with pytest.raises(mapexport.ExportError):
        mapexport.export_view(mapexport.MAP, mapexport.MARKDOWN)
    with pytest.raises(mapexport.ExportError):
        mapexport.export_view(mapexport.DIAGRAM, mapexport.MARKDOWN)

    (tmp_path / mapexport.MAP_SOURCE).write_text(_MAP_HTML, encoding="utf-8")
    (tmp_path / DIAGRAM_FILE).write_text("\n".join(_DIAGRAM_LINES) + "\n", encoding="utf-8")
    monkeypatch.setattr(PrimeItems, "diagram_model", _DIAGRAM_MODEL)
    for view in (mapexport.MAP, mapexport.DIAGRAM):
        for fmt in mapexport.FORMATS:
            path = mapexport.export_view(view, fmt)
            assert os.path.dirname(path) == str(tmp_path)
            assert os.path.basename(path).endswith(f"_Export.{fmt}")
            assert os.path.getsize(path) > 0

    diagram = json.loads((tmp_path / "MapTasker_Diagram_Export.json").read_text(encoding="utf-8"))
    assert diagram["lines"] == _DIAGRAM_LINES
    assert diagram["calls"][0]["called"] == "Callee"
