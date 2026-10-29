#! /usr/bin/env python3

#                                                                                      #
# build_command_wiki: build the searchable "Command Reference" wiki page                #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
"""Generate (and optionally publish) the MapTasker Command Reference wiki page.

The page is laid out like the GUI's own Help screen: the commands listed in
userhelp.py's INFO_TEXT (and the notes the Help screen adds after it) are the page's
table of contents, in the same order and with the same nesting, and every one of them
is a hotlink to a section of its own further down.  The change log note at the end of
the Help screen is left out.

Each section says more than the Help screen does.  Everything is read from the source
with the ``ast`` module -- nothing is imported and no GUI is started, so it runs
anywhere the source tree does:

* the Help screen's own line for the command, and anything it says that is a warning
  (a requirement, a limit, a 'Map and Diagram only') pulled out as a caveat;
* the longer help texts that go with it (BACKUP_HELP_TEXT for 'Get XML from Android
  Device', VIEW_HELP_TEXT for 'Display Views', and so on);
* the command's NiceGUI widget -- a ``ui.button``/``ui.menu_item``, or a
  ``ui.checkbox``/``ui.switch``/``ui.select``/``ui.toggle`` -- with the tooltip that
  explains it, where it is in the window, and the dialog it opens.

A widget's ``on_click`` handler is followed through the call graph until it reaches the
function that builds the next dialog, and that dialog's own widgets become its commands.

A command with nothing to say about it anywhere -- no tooltip, no line in the help
text, no comment above it in the source -- is not given a section and is written to a
log instead, so the gap is a list to work through rather than a page full of
"no description available".

Run it whenever commands are added or changed.  It lives in 'tools/misc' and
finds the source, and writes the page, wherever it is run from::

    python tools/misc/build_command_wiki.py            # write Command-Reference.md
    python tools/misc/build_command_wiki.py --stats    # ... and report what it found
    python tools/misc/build_command_wiki.py --publish  # ... and push it to the wiki

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
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from pathlib import Path

# Publishing lives in its own module, shared with build_generated_files_doc.py, so the
# wiki is only ever spoken to from one place.  Both tools sit in this directory.
from wikipub import add_publish_arguments, publish

# ##################################################################################
# Configuration
# ##################################################################################
HERE = Path(__file__).resolve().parent
PACKAGE_SOURCE = Path("maptasker") / "src"
DEFAULT_PAGE_NAME = "Command-Reference"
DEFAULT_LOG_NAME = "no_description.log"

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
    "guiwins_views.py:NiceGuiTextView._build_toolbar": "Map / Diagram / Tree View Toolbar",
    "guiwins_search.py:_FindDialog.__init__": "Find / Replace",
    "guiwins_search.py:_ReplaceTab.__init__": "Find / Replace (Replace Tab)",
    "guiwins_search.py:TextViewSearch._report_search_results": "Search Results",
    "guiwins_views.py:NiceGuiSceneView.build_ui": "Scene Preview Window",
    "guiwins.py:build_overwrite_confirm_dialog": "Overwrite Confirmation",
    "guiwins.py:build_if_variant_dialog": "Choose An If Variant",
    "guiwins.py:_build_fetch_apps_dialog": "Fetch Applications From Android Device",
    "guiwins.py:_build_item_layout_dialog": "Item Layout Designer",
    "guiwins.py:_build_show_when_dialog": "Variable / Show When Picker",
    "guiwins2.py:APIKeyDialog.__init__": "AI API Key Entry",
    "guiutils.py:check_new_version": "New Version Notice",
    "guiutils.py:validate_or_filelist_xml": "Android XML File List",
    "getfile.py:LocalFilePicker.__init__": "Local File Picker",
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
    "guiwins_views.py:NiceGuiTextView._build_toolbar",
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

# Command-line arguments are documented from the table parsearg.py builds its parser from,
# found beside the source.
CLI_TABLE = Path("assets") / "json" / "cli_arguments.json"


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

    visit_AsyncFunctionDef = visit_FunctionDef

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
        deferred = {id(inner) for outer in ast.walk(node) if isinstance(outer, ast.Lambda) for inner in ast.walk(outer)}
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
        by it -- taskedit_model.IF_BLOCK_VARIANTS is a list of the four 'If' shapes, and one
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
        self.help_constants: dict[str, str] = {}  # The Help screen's pieces, by constant name.
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
        for path in sorted(self.source.rglob("*.py")):
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
                self.help_constants = help_strings(tree)
        for function in self.funcs.values():
            self.by_name[function.name].append(function)
            if function.name == "__init__" and "." in function.qualname:  # LocalFilePicker(...)
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
        # The main window draws nothing itself now: it calls the helpers that draw the header,
        # the drawers and the body, so it is a surface for them to be merged into.
        self.surfaces = {
            key: function for key, function in self.funcs.items() if function.widgets or key == MAIN_SURFACE
        }
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
        Each command takes the HANDLERS that same call passed as well.  A helper that draws
        every Add and Edit button is called with a different handler each time, and a
        command given all of them is credited with whichever dialog is found first -- which
        was every Add button opening 'Add Scene Version', or 'Add Project', depending on the
        order a set happened to come out in.
        """
        for function in self.funcs.values():
            if not any(widget.label_param for widget in function.widgets):
                continue
            named = []
            for widget in function.widgets:
                if not widget.label_param:
                    named.append(widget)
                    continue
                labelled = self._labelled_calls(function, widget.label_param)
                if not labelled:
                    self.unlabelled.append((widget.module, widget.lineno))
                for label, calls in labelled.items():
                    handlers = set()
                    for call in calls:
                        handlers |= self._handlers_at(function, widget, call)
                    named.append(replace(widget, label=label, label_param="", handlers=tuple(sorted(handlers))))
            function.widgets = named

    def _labelled_calls(self, function: Func, parameter: str) -> dict[str, list[ast.Call]]:
        """Every label passed for one argument of a helper by anything that calls it, with the calls that passed it."""
        index = function.params.index(parameter)
        if function.params[0] in {"self", "cls"}:  # A method's call site does not pass it.
            index -= 1
        labels: dict[str, list[ast.Call]] = {}
        for call in self.callsites.get(function.name, []):
            argument = keyword_of(call, parameter)
            if argument is None and 0 <= index < len(call.args):
                argument = call.args[index]
            text = literal_text(argument)
            if is_nameable(text):
                labels.setdefault(text, []).append(call)
        return labels

    @staticmethod
    def _handlers_at(function: Func, widget: Widget, call: ast.Call) -> set[str]:
        """What a widget's handlers are when the helper is called as `call`: a handler passed in is whatever it passed."""
        resolved: set[str] = set()
        for name in widget.handlers:
            if name not in function.params:
                resolved.add(name)
                continue
            index = function.params.index(name)
            if function.params[0] in {"self", "cls"}:
                index -= 1
            argument = keyword_of(call, name)
            if argument is None and 0 <= index < len(call.args):
                argument = call.args[index]
            resolved |= handler_names(argument)
        return resolved

    def _merge_helpers(self) -> None:
        """Folds a widget-drawing helper into every surface that calls it.

        _create_file_and_message_buttons_section() draws into the main window and
        _build_v2_designer() into the Scene dialogs; neither is a place of its own.
        A helper that opens its own ui.dialog() is, so it is left alone, and so is
        one only ever reached from a click handler -- that is a dialog opening, not
        a section being drawn.  A helper two dialogs both draw belongs to both.
        """
        for key in list(self.surfaces):
            for helper in self._drawn_by(key):
                if (
                    helper.key != key
                    and (not helper.creates_dialog or key == MAIN_SURFACE)  # The body holds a picker dialog.
                    and helper.key not in SURFACE_TITLES
                    and key not in self.hosts_of(helper.key)
                ):
                    self.hosts[helper.key].add(key)

    def _drawn_by(self, key: str) -> list[Func]:
        """The surfaces a surface draws as it is built, directly or through a function that
        only calls the ones which draw.

        _create_object_action_rows() has no widgets of its own: it calls the helper that
        makes each Edit/Add button.  The buttons are still the main window's.
        """
        function = self.funcs[key]
        found: list[Func] = []
        seen = {key}
        queue = sorted(function.direct_calls - function.handler_calls)
        while queue:
            name = queue.pop(0)
            for helper in self.lookup(name, near=key):
                if helper.key in seen:
                    continue
                seen.add(helper.key)
                if helper.key in self.surfaces:
                    found.append(helper)
                elif not helper.widgets and not helper.creates_dialog and helper.module == function.module:
                    queue.extend(sorted(helper.direct_calls - helper.handler_calls))
        return found

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
        queue = [(name, 0) for name in sorted(self._handlers_of(widget))]
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

            _render_fetch_apps_button(fetch_then_reopen)  # in the picker


            def _render_fetch_apps_button(on_click): ...  # the button lives here

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
        is drawn into the main window, and LocalFilePicker is a class).
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


def help_strings(tree: ast.AST) -> dict[str, str]:
    """Every module-level string constant in the help module, by name: INFO_TEXT,
    BACKUP_HELP_TEXT and the rest.
    """
    strings: dict[str, str] = {}
    for node in getattr(tree, "body", []):
        if not isinstance(node, ast.Assign):
            continue
        text = literal_text(node.value)
        if text is None:
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                strings[target.id] = text
    return strings


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
    """The runtime arguments, read from the table parsearg.py builds its parser from."""
    path = source.parent / CLI_TABLE
    if not path.exists():
        return []
    arguments = []
    for entry in json.loads(path.read_text(encoding="utf-8")).get("arguments", []):
        if entry.get("hidden"):
            continue
        if entry.get("expand") == "colors":  # One '-c<code>' per kind of thing that can be colored.
            arguments.append(
                {
                    "flags": ["-c<code>"],
                    "help": "Provide a valid color for one kind of item in the output.  Example: -cp Blue",
                    "choices": "",
                },
            )
            continue
        help_text = entry.get("help", "")
        choices = entry.get("choices", "")
        arguments.append(
            {
                "flags": entry["names"],
                "help": "<br>".join(
                    " ".join(line.split())
                    for line in ([help_text] if isinstance(help_text, str) else help_text)
                    if line.strip()
                ),
                "choices": "the available AI models"
                if isinstance(choices, str) and choices
                else ", ".join(str(choice) for choice in choices),
            },
        )
    arguments.sort(key=lambda argument: argument["flags"][0].lstrip("-").casefold())
    return arguments


# ##################################################################################
# The page
# ##################################################################################
def find_source() -> Path:
    """The maptasker/src directory, looked for above this program and above the current
    directory.  This lives in 'tools/misc', but it keeps working if it is moved
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


def flatten(nodes: list[Node]) -> list[Node]:
    """Depth-first: a command, then everything reachable from it."""
    ordered = []
    for node in nodes:
        ordered.append(node)
        ordered.extend(flatten(node.children))
    return ordered


# ##################################################################################
# The Help screen
# ##################################################################################
@dataclass
class HelpEntry:
    """One command, as the Help screen lists it."""

    name: str
    text: str = ""  # What the Help screen says about it, as written.
    is_group: bool = False  # A heading ('Editing commands...') rather than a command.
    options: list[tuple[str, str]] = field(default_factory=list)  # 'Level 0: ...' lines.
    children: list[HelpEntry] = field(default_factory=list)
    parent: HelpEntry | None = None
    anchor: str = ""
    nodes: list[Node] = field(default_factory=list)  # Its widgets in the GUI.
    related: list[str] = field(default_factory=list)  # Longer help texts that go with it.
    extra_caveats: list[str] = field(default_factory=list)
    known_issues: list[str] = field(default_factory=list)

    @property
    def depth(self) -> int:
        """How many entries it is nested beneath."""
        return 0 if self.parent is None else self.parent.depth + 1

    def within(self, name: str) -> bool:
        """Whether this entry is, or sits beneath, the entry of that name."""
        entry: HelpEntry | None = self
        while entry:
            if entry.name == name:
                return True
            entry = entry.parent
        return False


@dataclass
class HelpDoc:
    """The Help screen, taken apart."""

    intro: list[str] = field(default_factory=list)
    entries: list[HelpEntry] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# The pieces build_help() joins into the Help screen, in its order.  COMMAND_REFERENCE_TEXT,
# the Help screen's pointer to this very page, is left out.
HELP_PIECES = (
    "INFO_TEXT",
    "OUTPUT_FOLDER_HELP_TEXT",
    "TASKERNET_UPDATES_HELP_TEXT",
    "TASKSTEP_HELP_TEXT",
    "TREND_HELP_TEXT",
    "VARIABLE_HELP_TEXT",
    "RESOURCES_HELP_TEXT",
    "MONITOR_HELP_TEXT",
    "PREBUILD_HELP_TEXT",
    "CARRY_HELP_TEXT",
    "TASKTESTS_HELP_TEXT",
    "OUTBOUND_HELP_TEXT",
    "TNDESC_HELP_TEXT",
    "LAUNCHER_HELP_TEXT",
)

# The longer help texts that go with one command: what the command is called in the Help
# screen (normalised), and the constants in userhelp.py that explain it further.
RELATED_HELP = {
    "get xml from android device": ("BACKUP_HELP_TEXT",),
    "list xml files": ("LISTFILES_HELP_TEXT",),
    "display views": ("VIEW_HELP_TEXT",),
    "analyze tab": ("AI_HELP_TEXT",),
    "view limit": ("VIEWLIMIT_HELP_TEXT",),
    "show edit api key s": ("APIKEY_HELP_TEXT",),
}

# The group of commands that belongs to the Map/Diagram/Tree views' toolbar.
TOOLBAR_GROUP = "Map / Diagram / Tree View Toolbar"

# Commands the Help screen does not list but that have caveats of their own to be said somewhere:
# the command, the Help-screen command it belongs to, and what it does.  The description is the
# one the GUI itself shows beneath it.
EXTRA_COMMANDS = {
    "Draft with AI": (
        "Add Project/Profile/Task/Scene",
        "In the Add Task window, turns a description in plain words into actions.  The AI model chosen on the "
        "Analyze tab drafts actions from the ones the editor can build, and they are added to the Task unsaved, "
        "for you to review and edit.  Whatever the AI suggested that MapTasker is unable to build is listed beside "
        "the draft, and a Stop button gives up on a slow model.",
    ),
}

# What is known not to work well yet, by the command it concerns (the Help screen's name for it,
# normalised).  These lived in Changelog.md's Known Issues until they were moved here, where
# they sit with the command they are about.
KNOWN_ISSUES = {
    "taskernet updates": [
        "It matches Tasks and Profiles by name, so one the author renames, or one with no name, can show up as "
        "new rather than changed.",
        "The first time you link a share, differences caused by Tasker rewriting it on import are listed along "
        "with real ones; later updates list only what the author changed.",
    ],
    "draft with ai": [
        "It is slow and often unusable on very small local models (such as tinyllama); a larger local model or a "
        "cloud model is recommended.",
        "It cannot choose an Application or an icon for an action, and a plugin action it picks still has to be "
        "configured inside Tasker; both are left at their defaults for you to fill in.",
    ],
    "add edit and save": [
        "Not all Task actions and Profile states or events editing are supported.  What remains unsupported is "
        "third-party plugins: their settings are an opaque payload that only the plugin's own configurator "
        "understands, so those still have to be set up inside Tasker.",
    ],
}

# A note that closes the Help screen, and the commands it is a caveat of: the phrase to
# look for in the note, and the (normalised) names of the commands it applies to.
NOTE_APPLIES_TO = {"appearance mode": ("dark mode", "colors tab")}

# Help lines that name a command in a sentence rather than a 'Name: text' pair, or head
# a group of commands, and what each should be called.  Keyed by how the line begins.
DISPLAY_NAMES = {
    "display options are": ("Detail Level", "How much of each Task the output shows.  The levels are:"),
    "display directory of hyperlinks": (
        "Display Directory",
        "Display a directory of hyperlinks at the beginning of the output.",
    ),
    "project/profile/task/scene names options": (
        "Project/Profile/Task/Scene Names",
        "Options to italicize, bold, underline and/or highlight the names of Projects, Profiles, Tasks and Scenes.",
    ),
    "indentation amount": ("Indentation", "The indentation amount for If/Then/Else Task Actions."),
    "map/diagram/tree view toolbar": (
        TOOLBAR_GROUP,
        "The commands on the toolbar of the Map, Diagram and Tree views.",
    ),
    "add and edit projects": (
        "Add, Edit and Save",
        "Add and Edit Projects, Profiles, Tasks and Scenes directly in the GUI, with various save options.",
    ),
    "editing commands": ("Editing Commands", "Reverse and review the changes made to the loaded XML."),
}

# What a command is called in the GUI when that is not what the Help screen calls it:
# the label the widget carries (normalised), keyed by the Help screen's name (normalised).
WIDGET_ALIASES = {
    "application settings save": ("save",),
    "application settings restore": ("restore",),
    "detail level": ("detail level",),
    "indentation": ("indent option",),
    "view limit": ("viewlimit optionmenu",),
    "notification duration": ("notify timeout optionmenu",),
    "font to use": ("font optionmenu",),
}

# The windows whose commands are the Map/Diagram/Tree toolbar's, which a command of the same
# name elsewhere (Replace, Save Results...) must not be mistaken for.
TOOLBAR_SURFACES = {
    "guiwins_views.py:NiceGuiTextView._build_toolbar",
    "guiwins_search.py:_FindDialog.__init__",
    "guiwins_search.py:_ReplaceTab.__init__",
    "guiwins_search.py:TextViewSearch._report_search_results",
}

# A description of more sentences than this is set out as a list rather than one block of text.
LONG_DESCRIPTION = 4

# How much of a caveat has to be said already for it to be a repeat of it.
OVERLAP = 0.75

# How many places, hover texts and dialog commands a section lists before saying 'and N more'.
WHERE_LIMIT = 3
HOVER_LIMIT = 3
OPENS_LIMIT = 15

# 'Name: what it does', or 'Name - what it does'.  The earlier of the two wins.
HELP_PAIR = re.compile(r"^(.{2,70}?)(?:\s*:\s+|\s+-\s+)(\S.*)$")
HELP_SUBPAIR = re.compile(r"^(\w{2,10})\s+-\s+(\S.*)$")  # 'Save - Save these settings...'
HELP_LEVEL = re.compile(r"^(Level \d+)\s*[:=]\s*(.*)$")
HELP_LOCATION = re.compile(r"^\((in [^()]*)\)\s*", re.IGNORECASE)  # '(in the Find/Replace window) ...'
HELP_AVAILABILITY = re.compile(r"^\(([^()]*\bonly)\)\s*", re.IGNORECASE)  # '(Map and Diagram only) ...'

# A sentence that warns of something: a requirement, a limit, or a place it is not offered.
CAVEAT = re.compile(
    r"\b(only (for|in|when|if|works?|available|offered|applies|one|a single)|(is|are|be|works?|applies|available"
    r"|offered|exclusive|one) only|requires?|must|unless|cannot|can't|is not|are not|will not|isn't|aren't"
    r"|not simulated|not offered|safety copy|overwrit\w*|exclusive|extended run times|up to \d+ seconds"
    r"|will time ?out|allow a few seconds|not instant)\b",
    re.IGNORECASE,
)
LIST_MARKER = re.compile(r"^(?:[-*o]|\d+-)\s+")
NOTE_PREFIX = re.compile(r"^note:\s*", re.IGNORECASE)
ABBREVIATION = re.compile(r"\b(e\.g|i\.e|etc|vs)\.", re.IGNORECASE)
CHANGELOG = re.compile(r"change\s?log", re.IGNORECASE)


def normalize(text: str) -> str:
    """A name reduced to lower-case words, so 'Just Display Everything!' finds 'just display everything'."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.casefold()).split())


def sentences(text: str) -> list[str]:
    """Text split into its sentences, 'e.g.' and 'etc.' not counting as the end of one."""
    protected = ABBREVIATION.sub(lambda match: match.group(0).replace(".", "\x00"), text)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z'\"(\[%*])", protected)
    return [part.replace("\x00", ".").strip() for part in parts if part.strip()]


def caveat_sentences(text: str) -> list[str]:
    """Just the sentences of one line of a help text that warn of something."""
    line = NOTE_PREFIX.sub("", LIST_MARKER.sub("", " ".join(text.split())))
    return [sentence for sentence in split_caveats(line, keep_first=False)[1] if not sentence.endswith(":")]


def sentence_case(text: str) -> str:
    """A sentence that starts with a capital and ends with a full stop."""
    text = text.strip()
    if not text:
        return text
    text = text[0].upper() + text[1:]
    text = text[:-3].rstrip() + "." if text.endswith("...") else text
    return text if text[-1] in ".!?:" else f"{text}."


def split_caveats(text: str, *, keep_first: bool = True) -> tuple[str, list[str]]:
    """A command's text divided into what it does and what to watch out for.

    The opening sentence is always what the command does, however many warnings it
    contains, so a long first sentence is never moved wholesale into the caveats.  A
    leading '(Map and Diagram only)' becomes a caveat of its own.
    """
    caveats: list[str] = []
    availability = HELP_AVAILABILITY.match(text)
    if availability:
        caveats.append(f"{availability.group(1)[0].upper()}{availability.group(1)[1:]}.")
        text = text[availability.end() :]
    plain = []
    for index, sentence in enumerate(sentences(text)):
        if CAVEAT.search(sentence) and not (index == 0 and keep_first):
            caveats.append(sentence_case(NOTE_PREFIX.sub("", sentence.strip("()").strip())))
        else:
            plain.append(sentence)
    return " ".join(plain), caveats


def unique_caveats(caveats: list[str], known: str = "") -> list[str]:
    """Caveats with repeats removed, in the order first met.

    One that largely restates a sentence already on the page -- `known`, or a caveat
    already kept -- is a repeat even when it is worded a little differently: the
    Help screen and the tooltip often both say it.
    """
    kept: list[str] = []
    seen = [set(normalize(known).split())] if known else []
    for caveat in caveats:
        words = set(normalize(caveat).split())
        if not words or any(len(words & earlier) / len(words) > OVERLAP for earlier in seen):
            continue
        kept.append(caveat)
        seen.append(words)
    return kept


def help_lines(text: str) -> list[str]:
    """A help text as Markdown: its numbered steps and dashes become lists, the rest paragraphs."""
    lines: list[str] = []
    previous_was_item = False
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        numbered = re.match(r"^(\d+)-\s*(.*)$", line)
        if numbered:
            item = f"{numbered.group(1)}. {numbered.group(2)}"
        elif line.startswith("- "):
            item = f"* {line[2:]}"
        elif line.startswith("o "):
            item = f"    * {line[2:]}"
        else:
            item = ""
        if lines and not (item and previous_was_item):
            lines.append("")
        lines.append(item or line)
        previous_was_item = bool(item)
    return lines


def match_names(entry: HelpEntry) -> list[str]:
    """Every name the GUI could know a Help-screen command by, normalised.

    'Add Project/Profile/Task/Scene' is four buttons; 'Zoom, Collapse All, Expand All,
    Reset' is four more; 'Specific Name tab' is the tab called 'Specific Name'.
    """
    names = [normalize(entry.name), *[normalize(variant) for variant in name_variants(entry.name)]]
    for part in re.split(r"\s*,\s*|\s+/\s+", entry.name):
        names += [normalize(variant) for variant in name_variants(part)]
    for alias in WIDGET_ALIASES.get(normalize(entry.name), ()):
        names.append(alias)
    return list(dict.fromkeys(name for name in names if name))


def make_entry(text: str, parent: HelpEntry | None, *, group: bool = False) -> HelpEntry:
    """A Help line made into an entry: its name, and what it says."""
    text = " ".join(text.split())
    pair = HELP_PAIR.match(text)
    if pair:
        name, body = pair.groups()
        sub = HELP_SUBPAIR.match(body)
        if sub:  # 'Application Settings: Save - Save these...' is the command 'Application Settings: Save'.
            name, body = f"{name}: {sub.group(1)}", sub.group(2)
    elif text.endswith(":"):
        name, body = text[:-1], ""
    else:
        name, body = text.rstrip(". "), text
    located = HELP_LOCATION.match(body)  # '(in the Find/Replace window) Type the question...'
    if located:
        body = f"{body[located.end() :].rstrip()} This is {located.group(1)}."
    for start, (display, description) in DISPLAY_NAMES.items():
        if normalize(name).startswith(normalize(start)):
            name, body = display, description if group or not pair else body
            break
    entry = HelpEntry(
        name=name.strip(),
        text=sentence_case(body),
        is_group=group or (not body and not pair),
        parent=parent,
    )
    if parent:
        parent.children.append(entry)
    return entry


class HelpParser:
    """Reads the Help screen's outline, one line at a time."""

    def __init__(self, doc: HelpDoc) -> None:
        """Starts reading into a document."""
        self.doc = doc
        self.start_piece()

    def start_piece(self) -> None:
        """Each piece of the Help screen starts again from the left margin."""
        self.top: HelpEntry | None = None
        self.group: HelpEntry | None = None
        self.last: HelpEntry | None = None
        self.in_notes = False

    def read(self, raw: str) -> None:
        """Takes one line: a command, a command beneath one, a group, a note or more of the last."""
        text = raw.strip()
        if not text:
            return
        indent = len(raw) - len(raw.lstrip())
        if indent == 0 and text.casefold().startswith("notes:"):
            self.in_notes = True
        elif self.in_notes:
            self.read_note(text)
        elif indent == 0 and text.startswith(("* ", "- ")):
            self.top = self.last = make_entry(text[2:], None, group=text.endswith("...") and ": " not in text)
            self.group = None
            self.doc.entries.append(self.top)
        elif indent == 0 and self.top is None:
            self.doc.intro.append(text)
        elif self.top is not None and self.last is not None:
            self.read_indented(text, indent)

    def read_note(self, text: str) -> None:
        """One of the closing 'Notes:', which may run over more than a line."""
        if text.startswith("- "):
            self.doc.notes.append(text[2:].strip())
        elif self.doc.notes:
            self.doc.notes[-1] += f" {text}"

    def read_indented(self, text: str, indent: int) -> None:
        """A line beneath a command: a command of its own, a group heading, or more about the last."""
        if indent <= 3 and text.startswith("- "):
            self.last = make_entry(text[2:], self.group or self.top)
        elif indent <= 3 and text.endswith("...") and not text.startswith("("):
            self.group = self.last = make_entry(text, self.top, group=True)
        elif indent <= 3 and text.startswith("(") and self.top:
            self.top.text = f"{self.top.text} {text}".strip()
        elif self.last:
            level = HELP_LEVEL.match(text)
            if level:
                self.last.options.append((level.group(1), level.group(2)))
            else:
                self.last.text = f"{self.last.text} {text}".strip()


def parse_help(constants: dict[str, str]) -> HelpDoc:
    """The Help screen, as the outline it is written in.

    A line starting '* ' (or '- ', in the pieces added after INFO_TEXT) is a command.  An
    indented '- ' line is a command beneath it, and an indented line ending '...' heads a
    group of them.  Anything else indented carries on the line above, or -- when it is
    a '(note)' sitting at the level of the commands -- is a note about the whole tab.
    The closing 'Notes:' are kept apart, minus the one that points at the change log.
    """
    doc = HelpDoc()
    parser = HelpParser(doc)
    for piece in HELP_PIECES:
        parser.start_piece()
        for raw in constants.get(piece, "").split("\n"):
            parser.read(raw)
    doc.notes = [note for note in doc.notes if not CHANGELOG.search(note)]
    return doc


def flatten_entries(entries: list[HelpEntry]) -> list[HelpEntry]:
    """Depth-first: an entry, then the entries beneath it."""
    ordered = []
    for entry in entries:
        ordered.append(entry)
        ordered.extend(flatten_entries(entry.children))
    return ordered


class PageWriter:
    """Renders the Help screen's commands as one searchable Markdown page."""

    def __init__(self, model: CommandModel, nodes: list[Node], version: str, page_name: str) -> None:
        """Prepares to render one page: reads the Help screen, then finds each of its
        commands in the widget tree so that the page can say more than the Help does.
        """
        self.model = model
        self.nodes = nodes
        self.flat = flatten(nodes)
        self.version = version
        self.page_name = page_name
        self.doc = parse_help(model.help_constants)
        self._add_extra_commands()
        self.entries = flatten_entries(self.doc.entries)
        self.attached_notes: set[str] = set()
        self._assign_anchors()
        self._attach_widgets()
        self._attach_related_help()
        self._attach_notes()
        self._attach_known_issues()

    def _add_extra_commands(self) -> None:
        """Gives the commands the Help screen leaves out, but that have known issues, a section
        beneath the command they belong to.
        """
        existing = flatten_entries(self.doc.entries)
        for name, (parent_name, text) in EXTRA_COMMANDS.items():
            parent = next((entry for entry in existing if normalize(entry.name) == normalize(parent_name)), None)
            if parent:
                parent.children.append(HelpEntry(name=name, text=text, parent=parent))

    # -- joining the Help screen to the rest of the source -------------------------
    def _assign_anchors(self) -> None:
        """A unique anchor per entry, and a way to find the entry a command name belongs to."""
        used: dict[str, int] = {}
        self.link_for: dict[str, str] = {}
        for entry in self.entries:
            base = f"cmd-{slug(entry.name)}"
            used[base] = used.get(base, 0) + 1
            entry.anchor = base if used[base] == 1 else f"{base}-{used[base]}"
            if entry.is_group:
                continue
            for name in match_names(entry):
                self.link_for.setdefault(name, entry.anchor)

    def _attach_widgets(self) -> None:
        """Finds the widgets each command is in the GUI, so its hover text, its place in the
        window and the dialog it opens can be added to the page.
        """
        by_label: dict[str, list[Node]] = defaultdict(list)
        for node in self.flat:
            by_label[normalize(node.widget.label)].append(node)
        for entry in self.entries:
            if entry.is_group:
                continue
            on_toolbar = entry.within(TOOLBAR_GROUP)
            found: list[Node] = []
            for name in match_names(entry):
                found.extend(node for node in by_label.get(name, []) if (node.root in TOOLBAR_SURFACES) == on_toolbar)
            main = [node for node in found if node.root == MAIN_SURFACE]
            entry.nodes = list({id(node): node for node in (main or found)}.values())

    def _attach_related_help(self) -> None:
        """Adds the longer help text (BACKUP_HELP_TEXT, VIEW_HELP_TEXT...) that goes with a command."""
        for entry in self.entries:
            for constant in RELATED_HELP.get(normalize(entry.name), ()):
                text = self.model.help_constants.get(constant, "")
                if text:
                    entry.related.append(text)

    def _attach_known_issues(self) -> None:
        """Hangs each known issue on the command it is about."""
        for entry in self.entries:
            entry.known_issues = KNOWN_ISSUES.get(normalize(entry.name), [])

    def _attach_notes(self) -> None:
        """Hangs a general note on the commands it is about, as a caveat of theirs."""
        for note in self.doc.notes:
            for phrase, names in NOTE_APPLIES_TO.items():
                if phrase not in note.casefold():
                    continue
                for entry in self.entries:
                    if normalize(entry.name) in names:
                        entry.extra_caveats.append(note)
                        self.attached_notes.add(note)

    # -- the page ----------------------------------------------------------------
    def render(self, arguments: list[dict]) -> str:
        """The whole page."""
        lines: list[str] = []
        lines += self._header()
        lines += self._contents(has_arguments=bool(arguments))
        lines += ["## Commands", ""]
        for entry in self.doc.entries:
            lines += self._entry(entry)
        if arguments:
            lines += self._arguments(arguments)
        lines += self._notes()
        lines += self._footer()
        return "\n".join(lines).rstrip() + "\n"

    def _header(self) -> list[str]:
        """Title, what MapTasker does, and how to use the page."""
        today = datetime.date.today().isoformat()
        described = sum(1 for entry in self.entries if not entry.is_group)
        return [
            "# MapTasker Command Reference",
            "",
            *[f"{paragraph}\n" for paragraph in self.doc.intro],
            f"This page describes each of the **{described}** commands, options and tabs in MapTasker's Help screen, "
            "in the same order, with more detail on each and the caveats that go with it.",
            "",
            f"_Generated from the MapTasker {self.version} source on {today} by `build_command_wiki.py`._ "
            "_Do not edit this page by hand -- rerun that program instead._",
            "",
            "## How to use this page",
            "",
            "* **Finding a command:** the Contents below lists the commands alphabetically.  Click a name to go to "
            "its section, or press `Ctrl`/`⌘` + `F` and type any part of the name.  The sections themselves follow the "
            "order of MapTasker's own Help screen.",
            "* **Reading a section:** each says what the command does, where it is in the window, the text MapTasker "
            "shows when you hover over it, and the dialog it opens.  Anything to watch out for -- a requirement, a "
            "limit, a command offered in only some views -- is under **Caveats**.",
            "* **Nesting:** a command that belongs to a tab or a toolbar is listed beneath it, and says so.",
            "",
        ]

    def _contents(self, *, has_arguments: bool) -> list[str]:
        """The directory of hotlinks: every command in the Help screen, as it is nested there."""
        lines = ["## Contents", ""]

        def listing(entries: list[HelpEntry], depth: int) -> None:
            for entry in entries:
                lines.append(f"{'  ' * depth}* [{entry.name}](#{entry.anchor})")
                listing(entry.children, depth + 1)

        # The commands are alphabetical here to be found by name; below, and within a tab
        # or a group, they stay in the order the Help screen gives them.
        listing(sorted(self.doc.entries, key=lambda entry: entry.name.casefold().lstrip("'\"")), 0)
        if has_arguments:
            lines.append("* [Command-Line Arguments](#command-line-arguments)")
        if self._unattached_notes():
            lines.append("* [Notes](#notes)")
        lines.append("")
        return lines

    def _entry(self, entry: HelpEntry) -> list[str]:
        """One command in full: what it does, where it is, what it opens, and its caveats."""
        plain, caveats = split_caveats(entry.text)
        heading = "#" * min(3 + entry.depth, 6)
        lines = [f'<a id="{entry.anchor}"></a>', f"{heading} {entry.name}", ""]
        if entry.parent:
            lines += [f"_Part of [{entry.parent.name}](#{entry.parent.anchor})._", ""]
        lines += self._where(entry)
        lines += self._description(plain)
        if entry.options:
            lines += [f"* **{key}:** {value}" for key, value in entry.options] + [""]
        hovers, hover_caveats = self._hover_text(entry, plain)
        if len(hovers) == 1:
            lines += [f"**Hover text:** {hovers[0]}", ""]
        elif hovers:
            lines += ["**Hover text:**", "", *[f"* {hover}" for hover in hovers], ""]
        lines += self._opens(entry)
        for text in entry.related:
            lines += ["**More detail:**", "", *help_lines(text), ""]
            caveats += [sentence for line in text.split("\n") for sentence in caveat_sentences(line)]
        caveats = unique_caveats(caveats + hover_caveats + entry.extra_caveats, known=plain)
        if caveats:
            lines += ["**Caveats:**", "", *[f"* {caveat}" for caveat in caveats], ""]
        if entry.known_issues:
            lines += ["**Known issues:**", "", *[f"* {issue}" for issue in entry.known_issues], ""]
        return lines + [line for child in entry.children for line in self._entry(child)]

    @staticmethod
    def _description(plain: str) -> list[str]:
        """What a command does: a paragraph, or -- when the Help screen has a great deal to
        say -- its opening sentence and then the rest one point to a line.
        """
        parts = sentences(plain)
        if len(parts) <= LONG_DESCRIPTION:
            return [plain, ""] if plain else []
        return [parts[0], "", *[f"* {part}" for part in parts[1:]], ""]

    def _where(self, entry: HelpEntry) -> list[str]:
        """The one line saying what kind of thing this is and where it sits in the window."""
        if not entry.nodes:
            return []
        kinds = sorted({ALL_KINDS.get(node.widget.kind, node.widget.kind) for node in entry.nodes})
        places = []
        for node in sorted(entry.nodes, key=lambda item: (item.root != MAIN_SURFACE, len(item.path))):
            place = " &gt; ".join([self.model.title_of(node.root), *node.path[:-1]])
            if place not in places:
                places.append(place)
        shown = places[:WHERE_LIMIT]
        more = f" (and {len(places) - len(shown)} more)" if len(places) > len(shown) else ""
        return [f"**Type:** {' / '.join(kinds)}  ", f"**Where:** {'; '.join(shown)}{more}", ""]

    def _hover_text(self, entry: HelpEntry, plain: str) -> tuple[list[str], list[str]]:
        """What MapTasker's own tooltips say about the command, where that adds to the Help screen.

        A tooltip that only repeats the Help screen's line is left out, and the sentences of
        a tooltip that warn of something are returned apart, as caveats.
        """
        known = normalize(f"{entry.text} {plain}")
        hovers: list[str] = []
        caveats: list[str] = []
        seen: set[str] = set()
        labels = {node.widget.label for node in entry.nodes}
        for node in entry.nodes:
            widget = node.widget
            if widget.described_by != "tooltip" or normalize(widget.tooltip) in seen:
                continue
            seen.add(normalize(widget.tooltip))
            if normalize(widget.tooltip) in known or (len(known) > 60 and known in normalize(widget.tooltip)):
                continue
            body, warned = split_caveats(" ".join(widget.tooltip.split()))
            caveats += warned
            if body:
                hovers.append(f"**{widget.label}** -- {body}" if len(labels) > 1 else body)
        return hovers[:HOVER_LIMIT], caveats

    def _opens(self, entry: HelpEntry) -> list[str]:
        """The dialog a command opens, and the commands in it, linking those the Help screen covers."""
        titles = list(dict.fromkeys(node.opens_title for node in entry.nodes if node.opens_title))
        if not titles:
            return []
        inside: dict[str, None] = {}
        for node in entry.nodes:
            for child in node.children:
                label = child.widget.label
                if label.casefold() not in COMMON_DESCRIPTIONS and self.link_for.get(normalize(label)) != entry.anchor:
                    inside[label] = None
        lines = [f"**Opens:** {', '.join(titles)}", ""]
        if inside:
            shown = list(inside)[:OPENS_LIMIT]
            names = [
                f"[{label}](#{self.link_for[normalize(label)]})" if normalize(label) in self.link_for else label
                for label in shown
            ]
            more = f", and {len(inside) - len(shown)} more" if len(inside) > len(shown) else ""
            lines += [f"**Commands in it:** {', '.join(names)}{more}", ""]
        return lines

    def _unattached_notes(self) -> list[str]:
        """The Help screen's closing notes that are not already a caveat on a command."""
        return [note for note in self.doc.notes if note not in self.attached_notes]

    def _notes(self) -> list[str]:
        """The Help screen's closing notes, minus the one pointing at the change log."""
        notes = self._unattached_notes()
        if not notes:
            return []
        return ["## Notes", "", *[f"* {note}" for note in notes], ""]

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
            "python tools/misc/build_command_wiki.py --publish",
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
# Entry point
# ##################################################################################
def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    """This program's own arguments."""
    parser = argparse.ArgumentParser(
        description="Build the MapTasker Command Reference wiki page from the source.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python tools/misc/build_command_wiki.py            write the page\n"
            "  python tools/misc/build_command_wiki.py --stats    ... and report what was found\n"
            "  python tools/misc/build_command_wiki.py --publish  ... and push it to the wiki\n"
            "  python tools/misc/build_command_wiki.py --publish --dry-run   show what would be pushed\n"
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
    add_publish_arguments(parser)
    return parser.parse_args(argv)


def report(model: CommandModel, nodes: list[Node], writer: PageWriter) -> None:
    """What was found, per window, plus anything that could not be documented."""
    flat = flatten(nodes)
    commands = [entry for entry in writer.entries if not entry.is_group]
    print(f"\nHelp screen: {len(commands)} commands, {len(writer.entries) - len(commands)} groups.")
    bare = [entry.name for entry in commands if not entry.nodes]
    print(f"{len(bare)} have no widget of that name in the GUI (their section is the Help screen's text alone):")
    for name in bare[:REPORT_LIMIT]:
        print(f"    {name}")
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
    writer = PageWriter(model, nodes, version_of(source), options.page_name)
    page = writer.render(arguments)
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
        report(model, nodes, writer)

    if options.publish:
        return publish(out, options.page_name, options.wiki_repo, options.dry_run, tool="build_command_wiki.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
