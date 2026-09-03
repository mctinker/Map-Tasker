#! /usr/bin/env python3

#                                                                                      #
# build_command_wiki: build the searchable "Command Reference" wiki page                #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
"""Generate (and optionally publish) the MapTasker Command Reference wiki page.

Every command MapTasker offers lives in the source as a NiceGUI widget: a
``ui.button``/``ui.menu_item`` for the commands, ``ui.checkbox``/``ui.switch``/
``ui.select``/``ui.toggle`` for the options that sit beside them, each with the
tooltip that already explains it.  Rather than keep a second, hand-written copy of
all that in a wiki page -- which goes stale the day a new command lands -- this
reads the widgets straight out of the source with the ``ast`` module and writes the
page from what it finds.  Nothing is imported and no GUI is started, so it runs
anywhere the source tree does.

The hierarchy is worked out the same way: a widget's ``on_click`` handler is
followed through the call graph until it reaches the function that builds the next
dialog, and that dialog's own widgets become its children.  That is what turns
'Import Into Tasker' into::

    Edit Profile > Save To Android > Import Into Tasker

A command with nothing to say about it anywhere -- no tooltip, no line in the help
text, no comment above it in the source -- is left off the page entirely and written
to a log instead, so the gap is a list to work through rather than a page full of
"no description available".

Run it whenever commands are added or changed.  It lives in 'Misc Utilities' and
finds the source, and writes the page, wherever it is run from::

    python "Misc Utilities/build_command_wiki.py"            # write Command-Reference.md
    python "Misc Utilities/build_command_wiki.py" --stats    # ... and report what it found
    python "Misc Utilities/build_command_wiki.py" --publish  # ... and push it to the wiki

Publishing clones https://github.com/mctinker/Map-Tasker.wiki.git into a temporary
directory, replaces the one page, commits and pushes.  Push credentials are
whatever git already uses for the Map-Tasker repository; nothing else in the wiki
is touched.  Use --publish --dry-run to see exactly what would be pushed first.
"""

from __future__ import annotations

import argparse
import ast
import datetime
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from pathlib import Path

# ##################################################################################
# Configuration
# ##################################################################################
HERE = Path(__file__).resolve().parent
PACKAGE_SOURCE = Path("maptasker") / "src"
DEFAULT_PAGE_NAME = "Command-Reference"
DEFAULT_LOG_NAME = "no_description.log"
WIKI_URL = "https://github.com/mctinker/Map-Tasker/wiki"
WIKI_REPO = "https://github.com/mctinker/Map-Tasker.wiki.git"

# The widget kinds worth documenting, and how each is labelled on the page.
COMMAND_KINDS = {"button": "Command", "menu_item": "Menu item"}
OPTION_KINDS = {
    "checkbox": "Option",
    "switch": "Option",
    "select": "Pulldown",
    "toggle": "Option",
    "radio": "Option",
    "tab": "Tab",
}
ALL_KINDS = {**COMMAND_KINDS, **OPTION_KINDS}

# Functions that wrap a literal in the running language.  A label written as
# translate_string("Exit") documents as "Exit".
TRANSLATORS = {"translate_string", "gettext", "_"}

# The surface every other one hangs off, and the titles for the windows a user
# would not recognise from the function name alone.  Anything not named here gets
# a title derived from its function name (build_edit_profile_dialog -> "Edit
# Profile"), so a new dialog needs no entry unless the derived name reads badly.
MAIN_SURFACE = "guiwins.py:initialize_screen"
SURFACE_TITLES = {
    MAIN_SURFACE: "Main Window",
    "guiwins.py:NiceGuiTextView.build_ui": "Map / Diagram / Tree View Toolbar",
    "guiwins.py:NiceGuiTextView.find_event": "Find / Replace",
    "guiwins.py:NiceGuiTextView._report_search_results": "Search Results",
    "guiwins.py:NiceGuiSceneView.build_ui": "Scene Preview Window",
    "guiwins.py:build_overwrite_confirm_dialog": "Overwrite Confirmation",
    "guiwins.py:build_if_variant_dialog": "Choose An If Variant",
    "guiwins.py:_build_fetch_apps_dialog": "Fetch Applications From Android Device",
    "guiwins.py:_build_item_layout_dialog": "Item Layout Designer",
    "guiwins.py:_build_show_when_dialog": "Variable / Show When Picker",
    "guiwins2.py:APIKeyDialog.__init__": "AI API Key Entry",
    "guiutils.py:check_new_version": "New Version Notice",
    "guiutils.py:validate_or_filelist_xml": "Android XML File List",
    "getfile.py:Local_File_Picker.__init__": "Local File Picker",
    "userintr.py:MapTaskerEventHandlers.get_xml_from_android_event": "Get XML From Android Device",
    "userintr.py:MapTaskerEventHandlers.ai_prompt_event": "Change Prompt",
    "userintr.py:_choose_comparison_file": "Compare Files",
}

# Reached from so many places that hanging them under every one of them would say
# nothing and repeat a lot: any save can ask before it overwrites a file, and any
# command at all can raise a message box.  They get a section of their own instead.
STANDALONE_SURFACES = {
    "guiwins.py:build_overwrite_confirm_dialog",
    "guiutils.py:check_new_version",
}

# Always a window in their own right: never listed as something a command opens, even
# though a command does open them.  The main window is where everything starts, and the
# view toolbar is the same toolbar whether Map, Diagram or Tree drew it.
WINDOW_SURFACES = {
    "guiwins.py:initialize_screen",
    "guiwins.py:NiceGuiTextView.build_ui",
}

# Not a place a user goes: a message box whose only command is the one that closes it.
EXCLUDED_SURFACES = {
    "guiwins.py:create_popup_window",
}

# The handful of commands no interface bothers to explain, described once here so the
# page does not answer "Cancel" with a shrug.  Anything with a tooltip or a line in the
# help text uses that instead; this is only ever the last resort.
COMMON_DESCRIPTIONS = {
    "cancel": "Closes this dialog and keeps nothing it was holding.",
    "ok": "Keeps what this dialog holds and closes it.  Nothing is written to a file: "
    "the change is kept in the loaded configuration, for a save to write out later.",
    "close": "Closes this window without changing anything.",
    "done": "Closes this dialog, keeping what was edited in it.",
    "use": "Uses what is entered or selected above, and closes the picker.",
    "use selected": "Uses what is selected in the list above, and closes the picker.",
}

# Where the GUI's own help text lives.  Commands whose widget carries no tooltip are
# described from this instead -- it is the text the '?' and Help buttons display, and
# it covers most of the main window's options.
HELP_SOURCE = "userhelp.py"

# How far a widget's handler is followed through the call graph before giving up
# on it opening anything.  Handlers reach their dialog in one or two hops -- the
# handler validates, then builds -- and past three the call graph wanders somewhere
# the click never goes.
MAX_HANDLER_DEPTH = 3

# A loop over a named list of labels documents each of them, up to this many.  Past it
# the list is data being displayed -- every colour, every font -- and not a set of
# commands at all.
MAX_TABLE_LABELS = 12

# A comment shorter than this is a label for the code below it, not a description of
# anything, and one that talks like this is explaining the code rather than the command.
COMMENT_MINIMUM = 30
CODE_TALK = re.compile(r"\(\)|self\.|ui\.|\.q-|__|[a-z]+_[a-z]+|<[a-z]+>")

# A string constant this long is one of the help texts, not an incidental message.
HELP_TEXT_MINIMUM = 200

# How much of a --stats report to print before saying how much more there is.
REPORT_LIMIT = 40

# Command-line arguments are documented from this parser's own add_argument calls.
CLI_SOURCE = "parsearg.py"


# ##################################################################################
# Source model
# ##################################################################################
@dataclass
class Widget:
    """One command, option or tab found in the source."""

    kind: str
    label: str
    tooltip: str = ""
    icon: str = ""
    module: str = ""
    lineno: int = 0
    owner: str = ""  # Key of the function that creates it.
    handlers: tuple[str, ...] = ()  # Simple names its click handler reaches.
    label_param: str = ""  # Set when the label is an argument, resolved after scanning.
    parent_lineno: int = 0  # Line of the widget this one drops out of, for menu items.
    comment: str = ""  # The comment written above it, if any.
    described_by: str = ""  # Which of the sources its description came from.
    opens: str | None = None  # Key of the surface it opens, once resolved.

    @property
    def sort_key(self) -> str:
        """Case-insensitive ordering for the alphabetical index."""
        return self.label.lstrip("'\"").casefold()


@dataclass
class Func:
    """A top-level function or method, with everything the graph needs from it."""

    key: str  # "module.py:qualname"
    name: str  # Simple name, which is what a call site gives us.
    module: str
    qualname: str
    lineno: int
    doc: str
    owner: str = ""  # For a function defined inside another, the outer one's key.
    params: list[str] = field(default_factory=list)  # Its arguments, callbacks included.
    calls: set[str] = field(default_factory=set)
    direct_calls: set[str] = field(default_factory=set)  # Not inside a lambda.
    own_calls: set[str] = field(default_factory=set)  # Run when it runs: no callbacks.
    handler_calls: set[str] = field(default_factory=set)  # Named by an on_click.
    creates_dialog: bool = False
    widgets: list[Widget] = field(default_factory=list)


def literal_text(node: ast.AST | None) -> str | None:
    """The static text of a label/tooltip expression, or None if it is built at runtime.

    Handles the shapes actually used for labels: a plain string, a translate_string()
    wrapper, adjacent strings added together, and a conditional that picks between two
    labels (the first is taken, since either one names the same command).
    """
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else None
    if isinstance(node, ast.JoinedStr):  # An f-string: keep what is static.
        parts = [literal_text(value) or "..." for value in node.values]
        return "".join(parts)
    if isinstance(node, ast.FormattedValue):
        return "..."
    if isinstance(node, ast.Call):
        called = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        if called in TRANSLATORS | {"dedent", "cleandoc"} and node.args:
            return literal_text(node.args[0])
        if called in {"strip", "rstrip", "lstrip"} and isinstance(node.func, ast.Attribute):
            return literal_text(node.func.value)  # A help string written as '''...'''.strip()
        return None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = literal_text(node.left), literal_text(node.right)
        return None if left is None or right is None else left + right
    if isinstance(node, ast.IfExp):
        return literal_text(node.body) or literal_text(node.orelse)
    return None


def expr_key(node: ast.AST) -> str | None:
    """The dotted name of an assignment target or 'with' subject: self.exit_button, zoom_in."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = expr_key(node.value)
        return f"{base}.{node.attr}" if base else None
    return None


def ui_kind(node: ast.AST, kinds: set[str]) -> str | None:
    """The widget kind of a ``ui.<kind>(...)`` call, if it is one we document."""
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "ui"
        and node.func.attr in kinds
    ):
        return node.func.attr
    return None


def base_call(node: ast.AST) -> ast.AST:
    """The call at the bottom of a chain: ui.button(...).props(...).classes(...) -> the button."""
    current = node
    while isinstance(current, ast.Call) and isinstance(current.func, ast.Attribute):
        inner = current.func.value
        if isinstance(inner, ast.Call):
            current = inner
            continue
        break
    return current


def keyword_of(node: ast.Call, name: str) -> ast.AST | None:
    """The value of one keyword argument of a call, or None."""
    for keyword in node.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def handler_names(node: ast.AST | None) -> set[str]:
    """Every function a widget's handler could reach: the handler itself, or, for a
    lambda/partial, whatever it calls.
    """
    if node is None:
        return set()
    names: set[str] = set()
    if isinstance(node, ast.Attribute):
        names.add(node.attr)
    elif isinstance(node, ast.Name):
        names.add(node.id)
    else:
        for inner in ast.walk(node):
            if isinstance(inner, ast.Call):
                function = inner.func
                if isinstance(function, ast.Attribute):
                    names.add(function.attr)
                elif isinstance(function, ast.Name):
                    names.add(function.id)
            elif isinstance(inner, (ast.Name, ast.Attribute)) and isinstance(node, (ast.Tuple, ast.List)):
                key = expr_key(inner)
                if key:
                    names.add(key.rsplit(".", 1)[-1])
    return {name for name in names if name}


def is_nameable(label: str | None) -> bool:
    """Whether a label is a name at all.  An f-string of runtime values reduces to
    something like "... (...)", which is not a command anyone can look up.
    """
    return bool(label and re.search(r"[A-Za-z0-9]", label))


def label_from_identifier(identifier: str) -> str:
    """A readable label for an icon-only widget, from the variable it is assigned to:
    ``self.get_xml_button`` -> "Get Xml", ``zoom_out`` -> "Zoom Out".
    """
    tail = identifier.rsplit(".", 1)[-1]
    tail = re.sub(r"^(the|my)_", "", tail)
    tail = re.sub(r"_?(button|btn|checkbox|switch|select|toggle|tab|widget|field)$", "", tail)
    words = [word for word in tail.split("_") if word]
    return " ".join(word.capitalize() for word in words)


class ModuleScanner(ast.NodeVisitor):
    """Collects the functions, their calls, and the widgets they create, one module."""

    def __init__(
        self,
        module: str,
        kinds: set[str],
        constants: dict[str, list[str]] | None = None,
        lines: list[str] | None = None,
    ) -> None:
        """Prepares to read one module for the given widget kinds."""
        self.module = module
        self.kinds = kinds
        self.constants = {} if constants is None else constants
        self.lines = [] if lines is None else lines
        self.funcs: dict[str, Func] = {}
        self.callsites: dict[str, list[ast.Call]] = defaultdict(list)  # name -> calls to it
        self.unlabelled: list[tuple[str, int]] = []  # Widgets named at runtime.
        self._class_stack: list[str] = []

    # -- traversal ---------------------------------------------------------------
    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # The ast API's own method name.
        """Records the class so its methods get a qualified key."""
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # The ast API's own method name.
        """Takes the whole function, nested definitions included, as one surface.

        A dialog builder's inner render_toolbar()/render_inspector() draw into the
        very dialog that defines them, so their widgets belong to it rather than to
        a surface of their own.  The inner ones are still registered, without any
        widgets of their own, because a button's on_click names them and the call
        graph has to be able to follow it.
        """
        qualname = ".".join([*self._class_stack, node.name])
        key = f"{self.module}:{qualname}"
        self.funcs[key] = self._build_func(node, qualname)
        self._register_inner(node, qualname, key)
        # Deliberately not recursing further: the widgets inside all belong to this one.

    visit_AsyncFunctionDef = visit_FunctionDef  # noqa: N815  (the ast API's own name)

    def _register_inner(self, node: ast.FunctionDef, qualname: str, owner: str) -> None:
        """Registers every function defined inside this one, for handler resolution only."""
        for inner in ast.walk(node):
            if inner is node or not isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            inner_qualname = f"{qualname}.{inner.name}"
            function = self._build_func(inner, inner_qualname, with_widgets=False)
            function.owner = owner
            self.funcs.setdefault(function.key, function)

    # -- one function ------------------------------------------------------------
    def _build_func(self, node: ast.FunctionDef, qualname: str, with_widgets: bool = True) -> Func:
        """Everything the graph needs to know about one function."""
        function = Func(
            key=f"{self.module}:{qualname}",
            name=node.name,
            module=self.module,
            qualname=qualname,
            lineno=node.lineno,
            doc=(ast.get_docstring(node) or "").strip(),
            params=[argument.arg for argument in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]],
        )
        # A call written inside a lambda or an inner def is a callback: it happens when
        # something else fires it, not when this function runs.  Which of those to ignore
        # depends on the question -- see direct_calls and own_calls.
        deferred = {
            id(inner)
            for outer in ast.walk(node)
            if isinstance(outer, ast.Lambda)
            for inner in ast.walk(outer)
        }
        callbacks = deferred | {
            id(inner)
            for outer in ast.walk(node)
            if outer is not node and isinstance(outer, (ast.FunctionDef, ast.AsyncFunctionDef))
            for inner in ast.walk(outer)
        }
        for inner in ast.walk(node):
            if isinstance(inner, ast.Call):
                called = inner.func.attr if isinstance(inner.func, ast.Attribute) else getattr(inner.func, "id", None)
                if called:
                    function.calls.add(called)
                    self.callsites[called].append(inner)
                    if id(inner) not in deferred:
                        function.direct_calls.add(called)
                    if id(inner) not in callbacks:
                        function.own_calls.add(called)
                if ui_kind(inner, {"dialog"}):
                    function.creates_dialog = True
        if with_widgets:
            function.widgets = self._widgets_in(node, function)
            for widget in function.widgets:
                function.handler_calls.update(widget.handlers)
        return function

    # -- the widgets it creates --------------------------------------------------
    def _widgets_in(self, node: ast.FunctionDef, function: Func) -> list[Widget]:
        """Every documented widget created anywhere in the function."""
        tooltips = self._tooltip_map(node)
        tables = self._loop_labels(node)
        statements = [
            (statement.lineno, statement.end_lineno or statement.lineno)
            for statement in ast.walk(node)
            if isinstance(statement, ast.stmt)
        ]
        widgets = []
        for inner in ast.walk(node):
            kind = ui_kind(inner, self.kinds)
            if kind is None:
                continue
            comment = self._comment_above(inner.lineno, statements)
            widgets.extend(self._widgets_from(inner, kind, function, tooltips, tables, comment))
        widgets.sort(key=lambda item: (item.lineno, item.label))
        return widgets

    def _widgets_from(
        self,
        node: ast.Call,
        kind: str,
        function: Func,
        tooltips: dict[int, str],
        tables: list[tuple[int, int, dict[str, list[str]]]],
        comment: str = "",
    ) -> list[Widget]:
        """The widget(s) one ``ui.<kind>()`` call creates.

        Usually one.  A toolbar built by looping over a literal table of commands is
        a single call that creates one widget per row, and each row is a command in
        its own right, so each gets its own entry.
        """
        labels = [label for label in self._labels_for(node, tables) if is_nameable(label)]
        parameter = "" if labels else self._label_parameter(node, function)
        if not labels and not parameter:
            self.unlabelled.append((self.module, node.lineno))
            return []
        icon = literal_text(keyword_of(node, "icon")) or ""
        handlers = tuple(sorted(handler_names(keyword_of(node, "on_click") or keyword_of(node, "on_change"))))
        return [
            Widget(
                kind=kind,
                label=" ".join(label.split()),
                label_param=parameter,
                tooltip=tooltips.get(id(node), ""),
                comment=comment,
                icon=icon,
                module=self.module,
                lineno=node.lineno,
                parent_lineno=getattr(self._parents.get(id(node)), "lineno", 0),
                owner=function.key,
                handlers=handlers,
            )
            for label in labels or [""]
        ]

    def _labels_for(self, node: ast.Call, tables: list[tuple[int, int, dict[str, list[str]]]]) -> list[str]:
        """What a widget is called: its own text, the table it is looped out of, the
        variable it is assigned to, or its icon -- in that order.  Empty when it is
        named at runtime from data and so cannot be documented from the source.
        """
        label = literal_text(node.args[0]) if node.args else None
        if label is None:
            label = literal_text(keyword_of(node, "text")) or literal_text(keyword_of(node, "label"))
        if label:
            return [label]
        looped = self._looped_labels(node, tables)
        if looped:
            return looped
        identifier = self._identifiers.get(id(node), "")
        if identifier:
            return [label_from_identifier(identifier)]
        icon = literal_text(keyword_of(node, "icon"))
        return [label_from_identifier(icon)] if icon else []

    @staticmethod
    def _label_parameter(node: ast.Call, function: Func) -> str:
        """The argument a widget takes its label from, when the label is handed in.

        _render_variable_entry(on_variable, button_text) draws a button labelled
        `button_text`, so what it is called is decided by whoever called that helper.
        Named here, resolved once every module has been read (see CommandModel).
        """
        labelled = (keyword.value for keyword in node.keywords if keyword.arg in {"text", "label"})
        for candidate in [*node.args[:1], *labelled]:
            inner = candidate
            if isinstance(inner, ast.Call) and inner.args:  # translate_string(button_text)
                called = inner.func.attr if isinstance(inner.func, ast.Attribute) else getattr(inner.func, "id", "")
                if called in TRANSLATORS:
                    inner = inner.args[0]
            if isinstance(inner, ast.Name) and inner.id in function.params:
                return inner.id
        return ""

    def _table_rows(self, iterated: ast.AST) -> list[ast.AST] | None:
        """The rows of a loop's table, when the loop walks one that can be read here.

        Either written out in the loop itself, or a module-level list of labels named
        by it -- taskedit.IF_BLOCK_VARIANTS is a list of the four 'If' shapes, and one
        button is built per entry.  A long list is data being listed, not a set of
        commands, so it is left alone.
        """
        if isinstance(iterated, (ast.Tuple, ast.List)):
            return list(iterated.elts)
        name = iterated.attr if isinstance(iterated, ast.Attribute) else getattr(iterated, "id", None)
        values = self.constants.get(name) if name else None
        if values and len(values) <= MAX_TABLE_LABELS:
            return [ast.Constant(value=value) for value in values]
        return None

    @staticmethod
    def _looped_labels(node: ast.Call, tables: list[tuple[int, int, dict[str, list[str]]]]) -> list[str]:
        """The labels a widget takes when it is created inside a loop over a literal table."""
        name = node.args[0].id if node.args and isinstance(node.args[0], ast.Name) else None
        if name is None:
            for keyword in node.keywords:
                if keyword.arg in {"text", "label"} and isinstance(keyword.value, ast.Name):
                    name = keyword.value.id
        if name is None:
            return []
        for start, end, values in tables:
            if start <= node.lineno <= end and name in values:
                return values[name]
        return []

    def _loop_labels(self, node: ast.FunctionDef) -> list[tuple[int, int, dict[str, list[str]]]]:
        """Every ``for`` loop over a literal table, and the values each of its names takes.

        The Scene designer's toolbars are written this way -- one ui.button() inside a
        loop over ("Up", "arrow_upward", ...), ("Down", ...) -- and each row of that
        table is a command a user clicks.
        """
        tables = []
        for inner in ast.walk(node):
            if not isinstance(inner, ast.For):
                continue
            rows = self._table_rows(inner.iter)
            if rows is None:
                continue
            if isinstance(inner.target, ast.Name):
                names = [inner.target.id]
            elif isinstance(inner.target, ast.Tuple):
                names = [expr_key(element) or "" for element in inner.target.elts]
            else:
                continue
            values: dict[str, list[str]] = defaultdict(list)
            for row in rows:
                cells = row.elts if isinstance(row, (ast.Tuple, ast.List)) else [row]
                for name, element in zip(names, cells, strict=False):
                    text = literal_text(element)
                    if name and text:
                        values[name].append(text)
            if values:
                tables.append((inner.lineno, inner.end_lineno or inner.lineno, dict(values)))
        return tables

    def _comment_above(self, lineno: int, statements: list[tuple[int, int]]) -> str:
        """The comment block written immediately above a widget, as one paragraph.

        Plenty of commands carry no tooltip but do have a note above them saying what
        they are for, and that note is the only description of them anywhere.  The
        comment is looked for above the whole statement the widget belongs to, since
        `self.health_check_button = (` puts the comment several lines up from the
        ui.button() call itself.

        Directives (noqa, type:) and rules of #### are not descriptions and are skipped.
        """
        anchor = max((start for start, end in statements if start <= lineno <= end), default=lineno)
        collected = []
        for index in range(anchor - 2, -1, -1):  # anchor is 1-based; start on the line above.
            line = self.lines[index].strip() if index < len(self.lines) else ""
            if not line.startswith("#"):
                break
            text = line.lstrip("#").strip()
            if not text or not re.search(r"[A-Za-z]", text):  # A rule of ### or a blank comment.
                continue
            if re.match(r"^(noqa|type:|ruff:|mypy:|pylint:|pragma|fmt:|!)", text, re.IGNORECASE):
                continue
            collected.append(text)
        return " ".join(reversed(collected)).strip()

    def _tooltip_map(self, node: ast.FunctionDef) -> dict[int, str]:
        """Maps each widget call to its tooltip text, and records what each is named.

        Two shapes are in use and both are read: the widget is assigned to a variable
        and a ``with`` block adds ui.tooltip() to it, or .tooltip() is chained straight
        onto the widget.  The same pass notes which widgets drop out of another one --
        a menu's items -- and what each widget is called in the code, which is the last
        thing left to name an icon-only button by.
        """
        self._identifiers = {}
        self._parents = {}
        named = self._named_widgets(node)
        tooltips = self._chained_tooltips(node)
        self._record_menu_items(node, named)
        for widget_call, text in self._with_block_tooltips(node, named):
            tooltips.setdefault(id(widget_call), text)
        return tooltips

    def _named_widgets(self, node: ast.FunctionDef) -> dict[str, ast.Call]:
        """Every widget assigned to a variable, by that variable's name."""
        named: dict[str, ast.Call] = {}
        for inner in ast.walk(node):
            if isinstance(inner, ast.Assign):
                targets, value = inner.targets, inner.value
            elif isinstance(inner, ast.AnnAssign) and inner.value is not None:
                targets, value = [inner.target], inner.value
            elif isinstance(inner, ast.withitem) and inner.optional_vars is not None:
                targets, value = [inner.optional_vars], inner.context_expr
            else:
                continue
            widget_call = base_call(value)
            if not ui_kind(widget_call, self.kinds):
                continue
            for target in targets:
                key = expr_key(target)
                if key:
                    named[key] = widget_call
                    self._identifiers.setdefault(id(widget_call), key)
        return named

    def _chained_tooltips(self, node: ast.FunctionDef) -> dict[int, str]:
        """Tooltips written as ui.button(...).props(...).tooltip("...")."""
        tooltips: dict[int, str] = {}
        for inner in ast.walk(node):
            if not (isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute)):
                continue
            if inner.func.attr != "tooltip" or not isinstance(inner.func.value, ast.Call) or not inner.args:
                continue
            widget_call = base_call(inner.func.value)
            text = literal_text(inner.args[0])
            if ui_kind(widget_call, self.kinds) and text:
                tooltips[id(widget_call)] = text
        return tooltips

    def _record_menu_items(self, node: ast.FunctionDef, named: dict[str, ast.Call]) -> None:
        """Notes the widgets that drop out of another one: `with a_button, ui.menu():`."""
        for inner in ast.walk(node):
            if not isinstance(inner, ast.With):
                continue
            owners = [named[key] for key in (expr_key(item.context_expr) for item in inner.items) if key in named]
            if not owners:
                continue
            for statement in inner.body:
                for candidate in ast.walk(statement):
                    if ui_kind(candidate, self.kinds) and candidate is not owners[0]:
                        self._parents[id(candidate)] = owners[0]

    def _with_block_tooltips(
        self,
        node: ast.FunctionDef,
        named: dict[str, ast.Call],
    ) -> list[tuple[ast.Call, str]]:
        """Tooltips written as `with a_button: ui.tooltip("...")`."""
        found = []
        for inner in ast.walk(node):
            if not isinstance(inner, ast.With):
                continue
            subjects = [expr_key(item.context_expr) for item in inner.items]
            widget_calls = [named[subject] for subject in subjects if subject and subject in named]
            for statement in inner.body if widget_calls else []:
                for candidate in ast.walk(statement):
                    if not (isinstance(candidate, ast.Call) and ui_kind(base_call(candidate), {"tooltip"})):
                        continue
                    text = literal_text(base_call(candidate).args[0]) if base_call(candidate).args else None
                    found.extend((widget_call, text) for widget_call in widget_calls if text)
        return found


# ##################################################################################
# The command tree
# ##################################################################################
@dataclass
class Node:
    """One command in the tree, with the path a user follows to reach it."""

    widget: Widget
    path: tuple[str, ...]
    surface: str  # Key of the surface it lives on.
    root: str  # Key of the window it ultimately belongs to.
    children: list[Node] = field(default_factory=list)
    opens_title: str = ""
    recursive: bool = False  # Its dialog is one already open further up the path.


class CommandModel:
    """Reads the source and works out what commands there are and how they nest."""

    def __init__(self, source: Path, kinds: set[str]) -> None:
        """Reads the source and builds the command tree for the given widget kinds."""
        self.source = source
        self.kinds = kinds
        self.funcs: dict[str, Func] = {}
        self.by_name: dict[str, list[Func]] = defaultdict(list)
        self.hosts: dict[str, set[str]] = defaultdict(set)  # helper -> surfaces it draws into
        self.callsites: dict[str, list[ast.Call]] = defaultdict(list)
        self.help_text: dict[str, str] = {}
        self.unlabelled: list[tuple[str, int]] = []  # Widgets named at runtime.
        self.undescribed: list[Widget] = []  # Widgets the source says nothing about.
        self._widget_cache: dict[str, list[Widget]] = {}
        self._scan()
        self._resolve()

    # -- reading the source ------------------------------------------------------
    def _scan(self) -> None:
        """Parses every module in the source directory."""
        trees: dict[str, ast.AST] = {}
        sources: dict[str, list[str]] = {}
        for path in sorted(self.source.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            try:
                trees[path.name] = ast.parse(text, filename=str(path))
            except SyntaxError as error:  # A module we cannot read is not fatal.
                print(f"  ! skipped {path.name}: {error}", file=sys.stderr)
                continue
            sources[path.name] = text.splitlines()
        constants = literal_constants(trees.values())
        for module, tree in trees.items():
            scanner = ModuleScanner(module, self.kinds, constants, sources[module])
            scanner.visit(tree)
            self.funcs.update(scanner.funcs)
            self.unlabelled.extend(scanner.unlabelled)
            for called, calls in scanner.callsites.items():
                self.callsites[called].extend(calls)
            if module == HELP_SOURCE:
                self.help_text = help_descriptions(tree)
        for function in self.funcs.values():
            self.by_name[function.name].append(function)
            if function.name == "__init__" and "." in function.qualname:  # Local_File_Picker(...)
                self.by_name[function.qualname.rsplit(".", 2)[-2]].append(function)

    def lookup(self, name: str, near: str = "") -> list[Func]:
        """The functions a call site could mean, the likeliest first.

        A name like render() or close() is defined a dozen times over, so the one
        defined inside the very function doing the calling wins, then one in the same
        module, and only then anything else.
        """
        candidates = self.by_name.get(name, [])
        if len(candidates) > 1 and near:
            inner = [function for function in candidates if function.owner == near]
            if inner:
                return inner
            if "." in near:  # A method calling build_ui() means its own class's build_ui.
                sibling = near.rsplit(".", 1)[0] + "."
                same_class = [function for function in candidates if function.key.startswith(sibling)]
                if same_class:
                    return same_class
            module = near.split(":", 1)[0]
            same = [function for function in candidates if function.module == module]
            if same:
                return same
        return candidates

    # -- surfaces ----------------------------------------------------------------
    def _resolve(self) -> None:
        """Names what could not be named while scanning, merges helper surfaces into
        their host, and resolves what each widget opens.
        """
        self._resolve_passed_labels()
        self.surfaces = {key: function for key, function in self.funcs.items() if function.widgets}
        self._merge_helpers()
        for key in list(self.surfaces):
            if key in self.hosts or key in EXCLUDED_SURFACES:
                del self.surfaces[key]
        for function in self.funcs.values():
            for widget in function.widgets:
                widget.opens = self._surface_opened_by(widget)
                self._describe(widget)
        self._drop_undescribed()

    @staticmethod
    def _describe_from(widget: Widget, help_text: dict[str, str]) -> tuple[str, str]:
        """The best description available for one widget, and where it came from."""
        label = widget.label.casefold()
        for source, text in (
            ("tooltip", widget.tooltip),
            ("help text", help_text.get(label, "")),
            ("common", COMMON_DESCRIPTIONS.get(label, "")),
            ("comment", usable_comment(widget.comment, widget.label)),
        ):
            if text:
                return text, source
        return "", ""

    def _describe(self, widget: Widget) -> None:
        """Gives a widget its description: its tooltip, the GUI's own help text, the
        wording every interface shares for an Ok or a Cancel, or -- last -- the comment
        written above it in the source.  Anything still undescribed is dropped later.
        """
        widget.tooltip, widget.described_by = self._describe_from(widget, self.help_text)

    def _drop_undescribed(self) -> None:
        """Leaves out every command the source says nothing about, for the log to list.

        A page entry that reads "no description available" is worse than no entry: it
        takes up a line in the index and answers nothing.  Dropping one can orphan the
        dialog it opened, and that dialog then becomes a section of its own rather than
        disappearing with it -- see roots().
        """
        for function in self.funcs.values():
            described = [widget for widget in function.widgets if widget.tooltip]
            self.undescribed.extend(widget for widget in function.widgets if not widget.tooltip)
            function.widgets = described
        self._widget_cache.clear()
        for key in list(self.surfaces):
            if not self.widgets_of(key):
                del self.surfaces[key]
        for function in self.funcs.values():
            for widget in function.widgets:
                if widget.opens and (widget.opens not in self.surfaces or not self.widgets_of(widget.opens)):
                    widget.opens = None
        self.undescribed.sort(key=lambda widget: (widget.module, widget.lineno, widget.label))

    def _resolve_passed_labels(self) -> None:
        """Names the widgets whose label was handed to their helper as an argument.

        The calls to the helper are looked up and every label any of them passes is
        documented, since each is a real command: one helper, two callers, two names.
        """
        for function in self.funcs.values():
            if not any(widget.label_param for widget in function.widgets):
                continue
            named = []
            for widget in function.widgets:
                if not widget.label_param:
                    named.append(widget)
                    continue
                labels = self._labels_from_callers(function, widget.label_param)
                if not labels:
                    self.unlabelled.append((widget.module, widget.lineno))
                named.extend(replace(widget, label=label, label_param="") for label in labels)
            function.widgets = named

    def _labels_from_callers(self, function: Func, parameter: str) -> list[str]:
        """Every label passed for one argument of a helper, by anything that calls it."""
        index = function.params.index(parameter)
        if function.params[0] in {"self", "cls"}:  # A method's call site does not pass it.
            index -= 1
        labels = []
        for call in self.callsites.get(function.name, []):
            argument = keyword_of(call, parameter)
            if argument is None and 0 <= index < len(call.args):
                argument = call.args[index]
            text = literal_text(argument)
            if is_nameable(text) and text not in labels:
                labels.append(text)
        return labels

    def _merge_helpers(self) -> None:
        """Folds a widget-drawing helper into every surface that calls it.

        _create_file_and_message_buttons_section() draws into the main window and
        _build_v2_designer() into the Scene dialogs; neither is a place of its own.
        A helper that opens its own ui.dialog() is, so it is left alone, and so is
        one only ever reached from a click handler -- that is a dialog opening, not
        a section being drawn.  A helper two dialogs both draw belongs to both.
        """
        for key, function in list(self.surfaces.items()):
            for name in sorted(function.direct_calls - function.handler_calls):
                for helper in self.lookup(name, near=key):
                    if (
                        helper.key in self.surfaces
                        and helper.key != key
                        and not helper.creates_dialog
                        and helper.key not in SURFACE_TITLES
                        and key not in self.hosts_of(helper.key)
                    ):
                        self.hosts[helper.key].add(key)

    def hosts_of(self, key: str, seen: set[str] | None = None) -> set[str]:
        """The surfaces a possibly-merged helper's widgets actually appear on."""
        seen = set() if seen is None else seen
        if key in seen:
            return set()
        seen.add(key)
        if key not in self.hosts:
            return {key}
        found: set[str] = set()
        for host in self.hosts[key]:
            found |= self.hosts_of(host, seen)
        return found

    def widgets_of(self, surface: str) -> list[Widget]:
        """Every widget drawn on a surface, its merged-in helpers' included."""
        if surface not in self._widget_cache:
            widgets = list(self.funcs[surface].widgets)
            for key in self.hosts:
                if surface in self.hosts_of(key) and key in self.funcs:
                    widgets.extend(self.funcs[key].widgets)
            self._widget_cache[surface] = self._deduplicate(widgets)
        return self._widget_cache[surface]

    @staticmethod
    def _deduplicate(widgets: list[Widget]) -> list[Widget]:
        """One entry per command per surface, keeping the one that has a tooltip."""
        best: dict[tuple[str, str], Widget] = {}
        for widget in sorted(widgets, key=lambda item: item.lineno):
            key = (widget.kind, widget.label.casefold())
            if key not in best or (not best[key].tooltip and widget.tooltip):
                best[key] = widget
        return sorted(best.values(), key=lambda item: item.lineno)

    def _surface_opened_by(self, widget: Widget) -> str | None:
        """Follows a widget's handler until it reaches the dialog it opens, if any.

        Breadth-first, so the nearest dialog wins: an Edit Profile button's handler
        validates, notifies and then builds a dialog, and it is that dialog we want,
        not whatever the dialog itself can go on to open.
        """
        here = self.hosts_of(widget.owner) | {widget.owner}
        queue = [(name, 0) for name in self._handlers_of(widget)]
        seen: set[str] = set()
        while queue:
            name, depth = queue.pop(0)
            if depth > MAX_HANDLER_DEPTH:
                continue
            candidates = self.lookup(name, near=widget.owner)
            for function in candidates:
                if function.key in seen:
                    continue
                seen.add(function.key)
                # A name defined in a dozen places (render, close, build_ui) says nothing
                # about which of them this click reaches, so it is not read as opening one.
                opened = self._opens(function, here) if len(candidates) == 1 else None
                if opened:
                    return opened
                if function.key in self.surfaces or function.key in self.hosts:
                    # Stop at anything that draws: a dialog's own commands are its own,
                    # and a section-drawing helper is not handling this click at all.
                    continue
                if function.owner and depth:
                    continue  # An inner function two hops out is no longer this click.
                queue.extend((called, depth + 1) for called in sorted(function.own_calls))
        return None

    def _handlers_of(self, widget: Widget) -> set[str]:
        """A widget's handlers, with any that were handed in from outside resolved.

        The two Application pickers share one 'App not listed?' button, drawn by a
        helper that is told what to do when it is clicked::

            _render_fetch_apps_button(fetch_then_reopen)   # in the picker
            def _render_fetch_apps_button(on_click): ...   # the button lives here

        The handler is 'on_click', which names nothing on its own, so the calls to the
        helper are looked up and whatever each passes for that argument is used instead.
        """
        owner = self.funcs.get(widget.owner)
        if owner is None:
            return set(widget.handlers)
        resolved: set[str] = set()
        for name in widget.handlers:
            if name not in owner.params:
                resolved.add(name)
                continue
            index = owner.params.index(name)
            if owner.params[0] in {"self", "cls"}:  # A method's call site does not pass it.
                index -= 1
            for call in self.callsites.get(owner.name, []):
                argument = keyword_of(call, name)
                if argument is None and index < len(call.args):
                    argument = call.args[index]
                resolved |= handler_names(argument)
        return resolved

    def _opens(self, function: Func, here: set[str]) -> str | None:
        """The surface this function puts on screen, if it is one a command can open.

        It has to be a dialog of its own -- a helper that draws into the caller is not
        somewhere a user goes -- or one of the panels named in SURFACE_TITLES, which
        are places in their own right without being a ui.dialog (the Android file list
        is drawn into the main window, and Local_File_Picker is a class).
        """
        if not (function.creates_dialog or function.key in SURFACE_TITLES):
            return None
        for host in sorted(self.hosts_of(function.key)):
            if (
                host in self.surfaces
                and host not in here
                and host not in STANDALONE_SURFACES
                and host not in WINDOW_SURFACES
                and self.widgets_of(host)
            ):
                return host
        return None

    # -- the tree ----------------------------------------------------------------
    def roots(self) -> list[str]:
        """The windows: surfaces nothing else opens, main window first."""
        opened = {widget.opens for function in self.funcs.values() for widget in function.widgets if widget.opens}
        roots = [key for key in self.surfaces if key not in opened and self.widgets_of(key)]
        roots.sort(key=lambda key: (key != MAIN_SURFACE, self.title_of(key)))
        return roots

    def places_of(self, widget: Widget) -> str:
        """The window(s) a widget appears in, named as the page would name them."""
        titles = sorted({self.title_of(host) for host in self.hosts_of(widget.owner)})
        return " and ".join(titles) if titles else self.title_of(widget.owner)

    def title_of(self, key: str) -> str:
        """A window's name: the one configured for it, or one derived from its function."""
        if key in SURFACE_TITLES:
            return SURFACE_TITLES[key]
        name = key.split(":", 1)[1].rsplit(".", 1)[-1]
        name = re.sub(r"^_?(build|create|open|display|show)_", "", name)
        name = re.sub(r"_(dialog|window|event|section|body|content)$", "", name)
        return " ".join(word.capitalize() for word in name.split("_") if word) or key

    def tree(self) -> list[Node]:
        """Every command, as one tree per window."""
        nodes = []
        for root in self.roots():
            nodes.extend(self._nodes_for(root, path=(), root=root, chain=(root,)))
        return nodes

    def _nodes_for(self, surface: str, path: tuple[str, ...], root: str, chain: tuple[str, ...]) -> list[Node]:
        """The commands on one surface, with their own sub-commands under them."""
        widgets = self.widgets_of(surface)
        drops_out_of = {widget.parent_lineno for widget in widgets if widget.parent_lineno}
        nodes = []
        by_line: dict[int, Node] = {}
        for widget in widgets:
            parent = by_line.get(widget.parent_lineno)
            base = parent.path if parent else path
            node = Node(widget=widget, path=(*base, widget.label), surface=surface, root=root)
            if widget.opens:
                node.opens_title = self.title_of(widget.opens)
                if widget.opens in chain:
                    # Edit Task can be reached from inside Edit Task; say so and stop.
                    node.recursive = True
                else:
                    node.children = self._nodes_for(widget.opens, node.path, root, (*chain, widget.opens))
            if widget.lineno in drops_out_of:
                by_line[widget.lineno] = node
            if parent:
                parent.children.append(node)
            else:
                nodes.append(node)
        return nodes


# ##################################################################################
# The GUI's own help text
# ##################################################################################
def usable_comment(comment: str, label: str) -> str:
    """A comment above a command, if it describes the command rather than the code.

    Most comments in a GUI module are written for whoever maintains it -- which Quasar
    class had to go where, which name a variable must not be given -- and putting one of
    those on the page is worse than leaving the command off it.  Rejected here are the
    notes that talk about code, the ones too short to be a sentence, and the ones that
    only repeat the command's own name ("'What's New' Button").
    """
    if len(comment) < COMMENT_MINIMUM or CODE_TALK.search(comment):
        return ""
    bare = re.sub(r"[\"\'`]", "", comment).strip(" .")
    trailing = r"\s+(button|buttons|checkbox|checkboxes|option|options|pulldown|menu)$"
    bare = re.sub(trailing, "", bare, flags=re.IGNORECASE)
    if bare.strip().casefold() == label.strip().casefold():
        return ""
    return comment


def literal_constants(trees: object) -> dict[str, list[str]]:
    """Module-level lists of strings, by name, for loops that build one widget per entry."""
    constants: dict[str, list[str]] = {}
    for tree in trees:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, (ast.List, ast.Tuple)):
                continue
            values = [literal_text(element) for element in node.value.elts]
            if not values or any(value is None for value in values):
                continue
            for target in node.targets:
                name = expr_key(target)
                if name and name.isupper():
                    constants.setdefault(name, values)
    return constants


def help_descriptions(tree: ast.AST) -> dict[str, str]:
    """Descriptions taken from the help text the GUI itself displays.

    Most commands explain themselves through a tooltip, but the main window's older
    options are described only in userhelp.py's INFO_TEXT, as lines like::

        * Display Conditions: Turn on the display of Profile and Task conditions.
        - Rename: Give the object being edited a new name.

    Those are read here and used for any command whose widget has no tooltip, so the
    page says something about as much of the interface as the source knows about.
    Names written together ("Add Project/Profile/Task/Scene") describe each one.
    """
    descriptions: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        text = literal_text(node.value)
        if not text or len(text) < HELP_TEXT_MINIMUM:  # The help constants, not a short string.
            continue
        for line in text.split("\n"):
            match = re.match(r"^\s*[*\-]\s+(.{2,70}?)\s*:\s+(\S.*)$", line)
            if not match:
                continue
            described, description = match.group(1), " ".join(match.group(2).split())
            for variant in name_variants(described):
                descriptions.setdefault(variant.casefold(), description)
    return descriptions


def name_variants(name: str) -> list[str]:
    """Every command one help line names: 'Add Project/Profile/Task/Scene' names four."""
    name = re.sub(r"\s*\(.*?\)\s*", " ", name).strip()
    name = re.sub(r"\s+(tab|option|options|button|buttons)$", "", name, flags=re.IGNORECASE).strip()
    words = name.split()
    variants = [name]
    for index, word in enumerate(words):
        if "/" in word:
            for alternative in word.split("/"):
                if alternative:
                    variants.append(" ".join([*words[:index], alternative, *words[index + 1 :]]))
    return [variant.strip(" .") for variant in variants if variant.strip(" .")]


# ##################################################################################
# Command-line arguments
# ##################################################################################
def command_line_arguments(source: Path) -> list[dict]:
    """The runtime arguments, read from the parser's own add_argument() calls."""
    path = source / CLI_SOURCE
    if not path.exists():
        return []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    arguments = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "add_argument":
            continue
        flags = [text for text in (literal_text(argument) for argument in node.args) if text]
        if not flags:
            continue
        help_text = literal_text(keyword_of(node, "help")) or ""
        choices = keyword_of(node, "choices")
        choice_text = ""
        if isinstance(choices, (ast.List, ast.Tuple)):
            names = [literal_text(element) for element in choices.elts]
            choice_text = ", ".join(name for name in names if name)
        arguments.append({"flags": flags, "help": " ".join(help_text.split()), "choices": choice_text})
    arguments.sort(key=lambda argument: argument["flags"][0].lstrip("-").casefold())
    return arguments


# ##################################################################################
# The page
# ##################################################################################
def find_source() -> Path:
    """The maptasker/src directory, looked for above this program and above the current
    directory.  This lives in 'Misc Utilities', but it keeps working if it is moved
    elsewhere in the tree or run from somewhere else.
    """
    for start in (HERE, Path.cwd().resolve()):
        for directory in (start, *start.parents):
            candidate = directory / PACKAGE_SOURCE
            if candidate.is_dir():
                return candidate
    return HERE / PACKAGE_SOURCE


def version_of(source: Path) -> str:
    """MapTasker's version, from the package metadata the program itself reports.

    sysconst.VERSION is importlib.metadata.version("maptasker"), which is this, so the
    page is stamped with the version of the source it was built from.
    """
    for candidate in (path / "pyproject.toml" for path in (source.parent.parent, source.parent, HERE.parent)):
        if candidate.exists():
            match = re.search(r'^version\s*=\s*["\']([^"\']+)', candidate.read_text(encoding="utf-8"), re.MULTILINE)
            if match:
                return match.group(1)
    return "unknown"


def slug(text: str) -> str:
    """A stable anchor name for a command path."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")
    return cleaned or "command"


def cell(text: str) -> str:
    """Text made safe for a Markdown table cell."""
    return text.replace("|", "\\|").replace("\n", " ").strip()


def first_sentence(text: str) -> str:
    """The opening sentence of a tooltip, for the one-line index."""
    if not text:
        return ""
    paragraph = text.strip().split("\n\n")[0].replace("\n", " ")
    match = re.search(r"(?<=[.!?])\s", paragraph)
    sentence = paragraph[: match.start()] if match else paragraph
    return " ".join(sentence.split())


def describe(text: str) -> list[str]:
    """A tooltip split into the paragraphs it was written as."""
    if not text:
        return []
    return [" ".join(block.split()) for block in text.strip().split("\n\n") if block.strip()]


def flatten(nodes: list[Node]) -> list[Node]:
    """Depth-first: a command, then everything reachable from it."""
    ordered = []
    for node in nodes:
        ordered.append(node)
        ordered.extend(flatten(node.children))
    return ordered


class PageWriter:
    """Renders the tree as one searchable Markdown page."""

    def __init__(self, model: CommandModel, nodes: list[Node], version: str, page_name: str) -> None:
        """Prepares to render one page from a command tree."""
        self.model = model
        self.nodes = nodes
        self.flat = flatten(nodes)
        self.version = version
        self.page_name = page_name
        self.anchors = self._anchors()

    def _anchors(self) -> dict[int, str]:
        """A unique anchor per command, keyed by the node itself."""
        anchors: dict[int, str] = {}
        used: dict[str, int] = {}
        for node in self.flat:
            base = f"cmd-{slug(' '.join(node.path))}"
            used[base] = used.get(base, 0) + 1
            anchors[id(node)] = base if used[base] == 1 else f"{base}-{used[base]}"
        return anchors

    def render(self, arguments: list[dict]) -> str:
        """The whole page."""
        lines: list[str] = []
        lines += self._header()
        lines += self._index()
        lines += self._detail()
        if arguments:
            lines += self._arguments(arguments)
        lines += self._footer()
        return "\n".join(lines).rstrip() + "\n"

    # -- sections ----------------------------------------------------------------
    def _header(self) -> list[str]:
        """Title, what the page is, and how to search it."""
        today = datetime.date.today().isoformat()
        commands = sum(1 for node in self.flat if node.widget.kind in COMMAND_KINDS)
        return [
            "# MapTasker Command Reference",
            "",
            f"Every command, option and pulldown in the MapTasker user interface: **{len(self.flat)}** entries "
            f"(**{commands}** of them commands) across **{len(self.model.roots())}** windows.",
            "",
            f"_Generated from the MapTasker {self.version} source on {today} by `build_command_wiki.py`._ "
            "_Do not edit this page by hand -- rerun that program instead._",
            "",
            "## How to use this page",
            "",
            "* **Searching:** press `Ctrl`/`⌘` + `F` and type any part of a command's name. "
            "Every command appears twice -- once in the alphabetical index, once in full under its window -- "
            "so a search always lands on something.",
            "* **Reading a path:** commands are written as the clicks that get you there. "
            "`Edit Profile > Save To Android > Import Into Tasker` means click **Edit Profile**, "
            "then **Save To Android** in the dialog that opens, then **Import Into Tasker**.",
            "* **Kinds:** _Command_ is a button, _Menu item_ sits in a pulldown menu, "
            "_Option_ is a checkbox or switch, _Pulldown_ is a list to choose from, and _Tab_ switches panels.",
            "* **Descriptions** are the text MapTasker shows when you hover over the command.  Where a command "
            "has no hover text, the description comes from MapTasker's own Help, or from the note written "
            "beside it in the source -- which is said, where that is so.",
            "",
            "## Contents",
            "",
            "* [Command Index (A-Z)](#command-index-a-z)",
            *[f"* [{self.model.title_of(root)}](#{slug(self.model.title_of(root))})" for root in self.model.roots()],
            "* [Command-Line Arguments](#command-line-arguments)",
            "",
        ]

    def _index(self) -> list[str]:
        """Every command in one alphabetical table."""
        lines = [
            "## Command Index (A-Z)",
            "",
            "| Command | Kind | Where it is | What it does |",
            "| --- | --- | --- | --- |",
        ]
        for node in sorted(self.flat, key=lambda item: (item.widget.sort_key, " ".join(item.path))):
            widget = node.widget
            anchor = self.anchors[id(node)]
            where = " &gt; ".join(node.path[:-1]) or self.model.title_of(node.root)
            if node.root != MAIN_SURFACE and node.path[:-1]:
                where = f"{self.model.title_of(node.root)} &gt; {where}"
            lines.append(
                f"| [{cell(widget.label)}](#{anchor}) | {ALL_KINDS.get(widget.kind, widget.kind)} "
                f"| {cell(where)} | {cell(first_sentence(widget.tooltip))} |",
            )
        lines.append("")
        return lines

    def _detail(self) -> list[str]:
        """Every command in full, grouped by the window it belongs to."""
        lines: list[str] = []
        by_root: dict[str, list[Node]] = defaultdict(list)
        for node in self.flat:
            by_root[node.root].append(node)
        for root in self.model.roots():
            title = self.model.title_of(root)
            lines += [f"## {title}", ""]
            if self.model.funcs[root].doc:
                lines += [f"_{first_sentence(self.model.funcs[root].doc)}_", ""]
            for node in by_root.get(root, []):
                lines += self._entry(node, title)
        return lines

    def _entry(self, node: Node, window: str) -> list[str]:
        """One command: its name, the path to it, and what it does."""
        widget = node.widget
        heading = "#" * min(3 + len(node.path) - 1, 6)
        path = " &gt; ".join(node.path)
        lines = [
            f'<a id="{self.anchors[id(node)]}"></a>',
            f"{heading} {widget.label}",
            "",
            f"**Path:** {window} &gt; {path}  ",
            f"**Kind:** {ALL_KINDS.get(widget.kind, widget.kind)}",
            "",
        ]
        if widget.described_by == "comment":
            lines += ["_There is no tooltip on this one; this is the note written beside it in the source._", ""]
        lines += [f"{paragraph}\n" for paragraph in describe(widget.tooltip)]
        if node.opens_title:
            if node.recursive:
                lines += [f"Opens the **{node.opens_title}** dialog, which is documented above.", ""]
            elif node.children:
                lines += [f"Opens **{node.opens_title}**, whose own commands are listed beneath this one.", ""]
            else:
                lines += [f"Opens **{node.opens_title}**.", ""]
        lines += [f"<sub>Source: `{widget.module}` line {widget.lineno}</sub>", ""]
        return lines

    def _arguments(self, arguments: list[dict]) -> list[str]:
        """The command-line arguments, for running MapTasker without the GUI."""
        lines = [
            "## Command-Line Arguments",
            "",
            "MapTasker can also be run from a terminal, where these arguments do the same job "
            "the settings above do in the window:",
            "",
            "```",
            "maptasker [arguments]",
            "```",
            "",
            "| Argument | Choices | What it does |",
            "| --- | --- | --- |",
        ]
        for argument in arguments:
            flags = ", ".join(f"`{flag}`" for flag in argument["flags"])
            lines.append(f"| {flags} | {cell(argument['choices'])} | {cell(argument['help'])} |")
        lines.append("")
        return lines

    def _footer(self) -> list[str]:
        """Where the page came from and how to rebuild it."""
        return [
            "---",
            "",
            "This page is generated from the MapTasker source by "
            "[`build_command_wiki.py`]"
            "(https://github.com/mctinker/Map-Tasker/blob/Master/Misc%20Utilities/build_command_wiki.py). "
            "To refresh it after commands are added or changed:",
            "",
            "```",
            'python "Misc Utilities/build_command_wiki.py" --publish',
            "```",
            "",
        ]


def write_no_description_log(path: Path, model: CommandModel, version: str) -> int:
    """Writes the commands left off the page, so the gap is a list to work through.

    One line each: where it is, what it is called, and the file and line to add a
    tooltip to.  The file is written even when nothing is missing, so that a log left
    over from an earlier run is never mistaken for the current state.
    """
    today = datetime.date.today().isoformat()
    lines = [
        f"MapTasker {version} -- commands with no description, {today}",
        f"Written by {Path(__file__).name}.  Regenerated in full on every run.",
        "",
    ]
    if not model.undescribed:
        lines += ["Nothing is missing: every command found has a description.", ""]
    else:
        lines += [
            f"These {len(model.undescribed)} are left out of the command reference entirely.  Each has no",
            "tooltip, no line in userhelp.py's help text, and no comment above it in the source,",
            "so there is nothing to say about it on the page.  Adding a ui.tooltip() to any of",
            "them -- or a comment above it -- puts it on the page the next time this is run.",
            "",
            f"{'WHERE':<44}{'COMMAND':<34}{'KIND':<11}SOURCE",
            "-" * 110,
        ]
        lines += [
            f"{model.places_of(widget)[:42]:<44}{widget.label[:32]:<34}"
            f"{ALL_KINDS.get(widget.kind, widget.kind):<11}{widget.module}:{widget.lineno}"
            for widget in model.undescribed
        ]
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return len(model.undescribed)


# ##################################################################################
# Publishing
# ##################################################################################
def run_git(arguments: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """One git command, with its output kept for reporting."""
    return subprocess.run(  # noqa: S603
        ["git", *arguments],  # noqa: S607
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def publish(page: Path, page_name: str, repo: str, dry_run: bool) -> int:
    """Clones the wiki, replaces the one page, and pushes it back.

    Only <page_name>.md is written; every other wiki page is left as it is.  With
    dry_run the clone and the write still happen so the diff can be shown, but
    nothing is committed or pushed.
    """
    with tempfile.TemporaryDirectory(prefix="maptasker-wiki-") as workspace:
        clone = Path(workspace) / "wiki"
        print(f"Cloning {repo} ...")
        result = run_git(["clone", "--depth", "1", repo, str(clone)], cwd=Path(workspace))
        if result.returncode != 0:
            print(result.stderr.strip(), file=sys.stderr)
            print(
                "Could not clone the wiki.  The wiki has to have at least one page already "
                "(create it once at " + WIKI_URL + "), and git needs push access to it.",
                file=sys.stderr,
            )
            return 1
        target = clone / f"{page_name}.md"
        target.write_text(page.read_text(encoding="utf-8"), encoding="utf-8")
        status = run_git(["status", "--porcelain"], cwd=clone)
        if not status.stdout.strip():
            print(f"'{page_name}' is already up to date -- nothing to push.")
            return 0
        diff = run_git(["diff", "--stat"], cwd=clone)
        print(diff.stdout.strip() or f"{page_name}.md is new.")
        if dry_run:
            print("--dry-run: not committing or pushing.")
            return 0
        message = f"Update {page_name} from build_command_wiki.py"
        for arguments in (["add", target.name], ["commit", "-m", message], ["push"]):
            result = run_git(arguments, cwd=clone)
            if result.returncode != 0:
                print(result.stderr.strip() or result.stdout.strip(), file=sys.stderr)
                return 1
        print(f"Pushed '{page_name}' to {WIKI_URL}/{page_name}")
    return 0


# ##################################################################################
# Entry point
# ##################################################################################
def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    """This program's own arguments."""
    parser = argparse.ArgumentParser(
        description="Build the MapTasker Command Reference wiki page from the source.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            '  python "Misc Utilities/build_command_wiki.py"            write the page\n'
            '  python "Misc Utilities/build_command_wiki.py" --stats    ... and report what was found\n'
            '  python "Misc Utilities/build_command_wiki.py" --publish  ... and push it to the wiki\n'
            '  python "Misc Utilities/build_command_wiki.py" --publish --dry-run   show what would be pushed\n'
        ),
    )
    parser.add_argument("--source", type=Path, default=None, help="MapTasker source directory.")
    parser.add_argument("--out", type=Path, default=None, help="Markdown file to write (default: <page name>.md).")
    parser.add_argument("--page-name", default=DEFAULT_PAGE_NAME, help="Wiki page name (default: Command-Reference).")
    parser.add_argument("--commands-only", action="store_true", help="Buttons and menu items only: no options or tabs.")
    parser.add_argument("--no-cli", action="store_true", help="Leave out the command-line arguments section.")
    parser.add_argument("--json", type=Path, default=None, help="Also write the commands to this JSON file.")
    parser.add_argument(
        "--log",
        type=Path,
        default=None,
        help=f"Where to list the commands with no description (default: {DEFAULT_LOG_NAME} beside the page).",
    )
    parser.add_argument("--stats", action="store_true", help="Report what was found, and what could not be named.")
    parser.add_argument("--publish", action="store_true", help="Push the page to the GitHub wiki.")
    parser.add_argument("--dry-run", action="store_true", help="With --publish: show the change, push nothing.")
    parser.add_argument("--wiki-repo", default=WIKI_REPO, help="Wiki git repository to publish to.")
    return parser.parse_args(argv)


def report(model: CommandModel, nodes: list[Node]) -> None:
    """What was found, per window, plus anything that could not be documented."""
    flat = flatten(nodes)
    print("\nWindows and dialogs:")
    for root in model.roots():
        count = sum(1 for node in flat if node.root == root)
        print(f"  {count:4d}  {model.title_of(root)}")
    print(f"\n{len(flat)} entries, {len(model.surfaces)} surfaces, {len(model.hosts)} helpers merged.")
    sources = Counter(node.widget.described_by for node in flat)
    print("\nDescriptions came from:")
    for name, count in sources.most_common():
        print(f"  {count:4d}  {name}")
    print(f"\n{len(model.undescribed)} commands were left off the page for want of a description (see the log).")
    print(f"\n{len(model.unlabelled)} widgets could not be named at all (their label is built at runtime):")
    for module, lineno in model.unlabelled[:REPORT_LIMIT]:
        print(f"    {module}:{lineno}")
    if len(model.unlabelled) > REPORT_LIMIT:
        print(f"    ... and {len(model.unlabelled) - REPORT_LIMIT} more")


def main(argv: list[str] | None = None) -> int:
    """Builds the page, and publishes it when asked to."""
    options = parse_arguments(argv)
    source = (options.source or find_source()).resolve()
    if not source.is_dir():
        print(f"MapTasker source directory not found: {source}", file=sys.stderr)
        print("Run this from anywhere in the Map-Tasker tree, or pass --source.", file=sys.stderr)
        return 1

    kinds = set(COMMAND_KINDS) if options.commands_only else set(ALL_KINDS)
    model = CommandModel(source, kinds)
    nodes = model.tree()
    arguments = [] if options.no_cli else command_line_arguments(source)
    page = PageWriter(model, nodes, version_of(source), options.page_name).render(arguments)


    out = options.out or HERE / f"{options.page_name}.md"
    out.write_text(page, encoding="utf-8")
    print(f"Wrote {out} ({len(page.splitlines())} lines, {len(flatten(nodes))} entries).")

    log = options.log or out.parent / DEFAULT_LOG_NAME
    missing = write_no_description_log(log, model, version_of(source))
    print(f"Wrote {log} ({missing} command{'' if missing == 1 else 's'} left off the page for want of a description).")

    if options.json:
        payload = [
            {
                "command": node.widget.label,
                "kind": node.widget.kind,
                "window": model.title_of(node.root),
                "path": list(node.path),
                "description": node.widget.tooltip,
                "opens": node.opens_title or None,
                "source": f"{node.widget.module}:{node.widget.lineno}",
            }
            for node in flatten(nodes)
        ]
        options.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote {options.json} ({len(payload)} entries).")

    if options.stats:
        report(model, nodes)

    if options.publish:
        return publish(out, options.page_name, options.wiki_repo, options.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
