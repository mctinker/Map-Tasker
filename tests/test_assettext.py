"""assettext: the scripts and stylesheets kept as files, and how they are filled in.

Three things are pinned.  The loader does what its header promises -- one read per file,
one substitution pass, a refusal when the values and the placeholders disagree.  Every call
in the program that fills a file in names exactly the placeholders that file has, which is
checked from the source rather than by driving the GUI paths that make those calls.  And
every script is well formed enough to be sent to a browser (balanced brackets, no
placeholder left unfilled), plus a real syntax check when Node is installed.
"""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from maptasker.src import assettext, mapjump

_SRC = Path(assettext.__file__).parent
_ASSETS = assettext.ASSETS_DIR


def _forget_loaded_files() -> None:
    """Empty every cache the loader keeps, so a test's files are read afresh."""
    assettext.text.cache_clear()
    assettext._pieces.cache_clear()  # noqa: SLF001
    assettext.placeholders.cache_clear()


@pytest.fixture
def fake_assets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An assets folder of the test's own, with the loader's caches emptied on the way in and out."""
    monkeypatch.setattr(assettext, "ASSETS_DIR", tmp_path)
    _forget_loaded_files()
    yield tmp_path
    _forget_loaded_files()


def test_a_placeholder_is_replaced_wherever_it_appears(fake_assets: Path) -> None:
    """Every occurrence is filled, inside a string literal or out of one."""
    (fake_assets / "a.js").write_text('const id = "c__ID__"; use(__ID__, __NAME__);', encoding="utf-8")

    assert assettext.render("a.js", ID="7", NAME='"x"') == 'const id = "c7"; use(7, "x");'


def test_a_value_that_looks_like_a_placeholder_is_left_alone(fake_assets: Path) -> None:
    """One pass: what was put in is not looked through again, whatever order the values come in."""
    (fake_assets / "a.js").write_text("__ONE__ __TWO__", encoding="utf-8")

    assert assettext.render("a.js", ONE="__TWO__", TWO="__ONE__") == "__TWO__ __ONE__"


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"ID": "1"}, "NAME"),  # A placeholder nobody filled would reach the browser as an undefined name.
        ({"ID": "1", "NAME": "2", "EXTRA": "3"}, "EXTRA"),  # A value nothing asked for is a caller out of step.
    ],
)
def test_the_values_must_be_exactly_the_placeholders(fake_assets: Path, values: dict, message: str) -> None:
    """Missing a value and offering an unwanted one are both refused, naming the odd one out."""
    (fake_assets / "a.js").write_text("__ID__ __NAME__", encoding="utf-8")

    with pytest.raises(KeyError, match=message):
        assettext.render("a.js", **values)


def test_a_file_is_read_once_however_often_it_is_rendered(fake_assets: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The cost of a script after its first use is the substitution, not the disk."""
    (fake_assets / "a.js").write_text("__ID__", encoding="utf-8")
    reads: list[Path] = []
    real = Path.read_text
    monkeypatch.setattr(Path, "read_text", lambda self, *a, **k: (reads.append(self), real(self, *a, **k))[1])

    for number in range(50):
        assert assettext.render("a.js", ID=str(number)) == str(number)

    assert len(reads) == 1


def test_a_text_without_placeholders_comes_back_unchanged(fake_assets: Path) -> None:
    """text() and render() agree on a file with nothing to fill in."""
    (fake_assets / "plain.css").write_text("a { color: red; }\n", encoding="utf-8")

    assert assettext.text("plain.css") == "a { color: red; }\n"
    assert assettext.render("plain.css") == "a { color: red; }\n"


# ##################################################################################
# Every call that fills a file in, against the file.
# ##################################################################################
def _asset_calls() -> list[tuple[str, int, str, set[str] | None]]:
    """(source file, line, asset, keyword names) for each assettext.render/text call naming an asset.

    The asset is the first argument when it is a string literal.  Calls that take it from a
    variable are followed through the module-level constant that holds it.
    """
    calls = []
    for path in sorted(_SRC.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        constants = {
            node.targets[0].id: node.value.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        }
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "assettext"
                and node.func.attr in {"render", "text"}
                and node.args
            ):
                continue
            first = node.args[0]
            asset = first.value if isinstance(first, ast.Constant) else constants.get(getattr(first, "id", ""))
            if asset is None:
                continue
            names = None if node.func.attr == "text" else {kw.arg for kw in node.keywords if kw.arg}
            calls.append((path.name, node.lineno, asset, names))
    return calls


def test_the_calls_were_found() -> None:
    """A scan that finds nothing would make the next test pass for the wrong reason."""
    assert len(_asset_calls()) >= 15


@pytest.mark.parametrize(("source", "line", "asset", "names"), _asset_calls())
def test_each_call_fills_in_exactly_what_its_file_has(source: str, line: int, asset: str, names: set | None) -> None:
    """The keyword names at the call and the placeholders in the file are the same set."""
    wanted = set(assettext.placeholders(asset))

    assert (names is None and not wanted) or names == wanted, f"{source}:{line} -> {asset}"


# ##################################################################################
# The scripts themselves.
# ##################################################################################
_SCRIPTS = sorted(p.relative_to(_ASSETS).as_posix() for p in (_ASSETS / "js").glob("*.js"))
_STYLESHEETS = sorted(p.relative_to(_ASSETS).as_posix() for p in (_ASSETS / "css").glob("*.css"))


def _without_strings_and_comments(code: str) -> str:
    """The code with string literals, regular-expression literals and comments blanked out."""
    code = re.sub(r"//[^\n]*", "", code)
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    code = re.sub(r"\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*'|`(?:\\.|[^`\\])*`", '""', code)
    return re.sub(r"(?<=[=(,:;!&|?{}])\s*/(?:\\.|[^/\\\n])+/[a-z]*", " 0", code)


@pytest.mark.parametrize("asset", _SCRIPTS)
def test_every_script_has_balanced_brackets(asset: str) -> None:
    """A cheap well-formedness check that needs no JavaScript engine."""
    code = _without_strings_and_comments(assettext.text(asset))
    stack = []
    for character in code:
        if character in "([{":
            stack.append(character)
        elif character in ")]}":
            assert stack, f"{asset}: unmatched {character}"
            assert stack.pop() == {")": "(", "]": "[", "}": "{"}[character], f"{asset}: mismatched {character}"
    assert not stack, f"{asset}: unclosed {stack}"


@pytest.mark.parametrize("asset", [*_SCRIPTS, *_STYLESHEETS])
def test_every_asset_is_utf8_and_ends_cleanly(asset: str) -> None:
    """The file reads as UTF-8 and is not empty."""
    assert assettext.text(asset).strip(), asset


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is not installed")
@pytest.mark.parametrize("asset", _SCRIPTS)
def test_every_script_parses_as_javascript(asset: str, tmp_path: Path) -> None:
    """Node's own parser, on the script as the browser receives it: a function body, holes filled with 0."""
    body = re.sub(r"__[A-Z][A-Z0-9_]*[A-Z0-9]__", "0", assettext.text(asset))
    wrapped = tmp_path / "script.js"
    wrapped.write_text(f"(function () {{\n{body}\n}});\n", encoding="utf-8")

    result = subprocess.run(["node", "--check", str(wrapped)], capture_output=True, text=True, check=False)  # noqa: S603, S607

    assert result.returncode == 0, f"{asset}: {result.stderr}"


def test_the_shared_snippets_are_the_files_they_say_they_are() -> None:
    """The constants other modules embed are the asset files, not copies that could drift."""
    assert assettext.text("js/reveal_ancestors.js") == mapjump.REVEAL_ANCESTORS_JS
    assert "mtJumpTarget" in mapjump.RESOLVE_TARGET_JS
