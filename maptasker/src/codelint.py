"""codelint: the code inside JavaScriptlet and Run Shell actions."""

#! /usr/bin/env python3

#                                                                                       #
# codelint: look inside the code a Task carries -- a JavaScriptlet's script and a Run   #
#           Shell's command -- for the two things a backup can show about it without   #
#           running anything: whether it is even well-formed, and which Tasker          #
#           variables the script reaches for.                                           #
#                                                                                       #
# Same contract as healthck.py, proflint.py and taskflow.py: everything here reads      #
# PrimeItems.tasker_root_elements and nothing else, so it runs the moment an XML file   #
# is loaded and is testable without a GUI.  The dependency runs healthck -> codelint    #
# and varxref -> codelint, never the other way; the severity words and the Problem      #
# record are spelled out again here for proflint's reason.                              #
#                                                                                       #
# The syntax checks are structural, not a parser: brackets that do not pair up,        #
# strings and comments left open, a shell quote or $( never closed.  That is the class  #
# of mistake a script typed on a phone keyboard actually has, it needs nothing          #
# installed, and it cannot be wrong in the way a half-built parser can -- everything it #
# reports really is unbalanced.  Where a construct would need real parsing to judge     #
# (a shell 'case' pattern's lone ')', a here-document), the check stands aside rather   #
# than guess.                                                                            #
#                                                                                       #
# Tasker substitutes %variables into both kinds of code before running it, so a         #
# '%name' is read as a value wherever it appears and never counts against the code.     #
#                                                                                       #
# MIT License   Refer to https://opensource.org/license/mit                             #
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from maptasker.src.mapjump import TASK, Target, actions_in_map_order

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from maptasker.src.primitem import RunState

WARNING = "WARNING"

JAVASCRIPTLET = "129"  # arg0 is the script itself
RUN_SHELL = "123"  # arg0 is the command
# The argument holding the code, for both.
CODE_ARGUMENT = "arg0"

JS_SYNTAX = "CODE-JS-SYNTAX"
SHELL_SYNTAX = "CODE-SHELL-SYNTAX"
TAGS = frozenset({JS_SYNTAX, SHELL_SYNTAX})


@dataclass
class Problem:
    """One finding, in the shape healthck folds into its report (see proflint.Problem)."""

    severity: str
    tag: str
    where: Target
    detail: str


# ##################################################################################
# JavaScript: which Tasker variables a script reads and sets.
# ##################################################################################
# A JavaScriptlet does not name a Tasker variable the way the rest of Tasker does.  A
# script reaches a global through global('Name') and changes it through setGlobal, and
# does the same for a local through local() and setLocal() -- never with the '%' the
# variable checks look for, which is why a global read only by a script was reported as
# never read.  Only a name written out as a string can be known without running the
# script: setLocal(name, value), with the name in a variable, is left alone.
_JS_VARIABLE_CALL = re.compile(
    r"""\b(global|setGlobal|local|setLocal)\s*\(\s*(['"`])%?([A-Za-z][A-Za-z0-9_]*)\2""",
)
_JS_WRITES = frozenset({"setGlobal", "setLocal"})


def js_variable_uses(code: str) -> list[tuple[str, bool]]:
    """[(%name, is_write)] for every Tasker variable a script names through Tasker's own calls.

    In the order they appear.  A '%name' written straight into the script is not here:
    Tasker substitutes those before the script runs, and the variable checks already read
    them as they read any other argument.
    """
    return [(f"%{match.group(3)}", match.group(1) in _JS_WRITES) for match in _JS_VARIABLE_CALL.finditer(code or "")]


# ##################################################################################
# JavaScript: is it well-formed?
# ##################################################################################
_OPENERS = {"(": ")", "[": "]", "{": "}"}
_CLOSERS = {")": "(", "]": "[", "}": "{"}
# After one of these words a '/' starts a regular expression, not a division.
_REGEX_AFTER_WORDS = frozenset(
    {"return", "typeof", "instanceof", "in", "of", "new", "delete", "void", "throw", "case", "do", "else"},
)
_IDENTIFIER_START = re.compile(r"[A-Za-z_$]")
_IDENTIFIER = re.compile(r"[A-Za-z0-9_$]*")
_NUMBER = re.compile(r"[0-9][0-9A-Za-z_.]*")
_TEMPLATE = "${"  # a template literal's substitution, closed by a '}'


def _run_length(pattern: re.Pattern[str], text: str, position: int) -> int:
    """How many characters from this position the pattern matches (0 if none)."""
    match = pattern.match(text, position)
    return len(match.group(0)) if match else 0


def _line_of(text: str, position: int) -> int:
    """The line a position is on, counting from 1."""
    return text.count("\n", 0, position) + 1


# A Tasker variable as Tasker substitutes it: %name, or an array reference such as
# %items(1), %items(#) or %items(2:4) -- whose brackets are Tasker's, not the code's.
_TASKER_VARIABLE = re.compile(r"%[A-Za-z][A-Za-z0-9_]*(?:\([^()\n]*\))?")


def _tasker_variable_end(text: str, position: int) -> int:
    """Where a Tasker variable starting at this position ends, or the position itself if none does."""
    match = _TASKER_VARIABLE.match(text, position)
    return match.end() if match else position


def _skip_quoted(code: str, start: int, quote: str) -> int | None:
    """The position just past a '...' or "..." string, or None if the line ends first."""
    position = start + 1
    while position < len(code):
        char = code[position]
        if char == "\\":
            position += 2  # an escaped character, a line continuation included
            continue
        if char == quote:
            return position + 1
        if char == "\n":
            return None
        position += 1
    return None


def _skip_regex(code: str, start: int) -> int | None:
    """The position just past a /regex/flags literal, or None if the line ends first."""
    position = start + 1
    in_class = False
    while position < len(code):
        char = code[position]
        if char == "\\":
            position += 2
            continue
        if char == "\n":
            return None
        if in_class:
            in_class = char != "]"
        elif char == "[":
            in_class = True
        elif char == "/":
            return position + 1 + _run_length(_IDENTIFIER, code, position + 1)  # and its flags
        position += 1
    return None


class _ScriptScan:
    """One pass over a script, a token at a time -- js_syntax_problem's working state.

    Each _step_ method looks at the character under the cursor and returns (handled,
    problem): handled when it consumed something, and a problem sentence when what it found
    is malformed.  They are tried in a fixed order, which is the order the checks have to be
    made in: a comment before a division, a Tasker variable before a '%' operator.
    """

    def __init__(self, code: str) -> None:
        """Start at the top, where a '/' begins a regular expression."""
        self.code = code
        self.position = 0
        self.stack: list[tuple[str, int]] = []  # (opener, position), "${" for a template's substitution
        self.regex_allowed = True  # at the start, and after an operator, '/' begins a regex
        self.in_template = False  # inside a `...` literal, outside any ${...}

    def line(self, position: int | None = None) -> int:
        """The line of a position, the cursor's by default."""
        return _line_of(self.code, self.position if position is None else position)

    def run(self) -> str:
        """Scan to the end; the first problem found, or ""."""
        steps = (self._step_space_or_comment, self._step_quoted, self._step_tasker_variable, self._step_bracket)
        while self.position < len(self.code):
            if self.in_template:
                self._step_template()
                continue
            for step in steps:
                handled, problem = step(self.code[self.position])
                if problem:
                    return problem
                if handled:
                    break
            else:
                self._step_word_or_operator(self.code[self.position])
        return self._left_open()

    def _step_template(self) -> None:
        """Inside a `...` literal: its end, a ${ substitution, or text."""
        code, position = self.code, self.position
        if code[position] == "\\":
            self.position += 2
        elif code[position] == "`":
            self.stack.pop()  # the template's own "`" entry, which is on top here
            self.in_template = False
            self.regex_allowed = False
            self.position += 1
        elif code.startswith(_TEMPLATE, position):
            self.stack.append((_TEMPLATE, position))
            self.in_template = False
            self.regex_allowed = True
            self.position += 2
        else:
            self.position += 1

    def _step_space_or_comment(self, char: str) -> tuple[bool, str]:
        """Whitespace, a // comment or a /* comment */."""
        code, position = self.code, self.position
        if char in " \t\r\n":
            self.position += 1
            return True, ""
        if code.startswith("//", position):
            newline = code.find("\n", position)
            self.position = len(code) if newline == -1 else newline
            return True, ""
        if code.startswith("/*", position):
            end = code.find("*/", position + 2)
            if end == -1:
                return True, f"A comment opened on line {self.line()} is never closed."
            self.position = end + 2
            return True, ""
        return False, ""

    def _step_quoted(self, char: str) -> tuple[bool, str]:
        """A string, the start of a template literal, or a regular expression."""
        if char in "'\"":
            end = _skip_quoted(self.code, self.position, char)
            if end is None:
                return True, f"A string opened with {char} on line {self.line()} is not closed on that line."
        elif char == "`":
            self.stack.append(("`", self.position))
            self.in_template = True
            self.position += 1
            return True, ""
        elif char == "/" and self.regex_allowed:
            end = _skip_regex(self.code, self.position)
            if end is None:
                return True, f"A regular expression on line {self.line()} is not closed on that line."
        else:
            return False, ""
        self.position = end
        self.regex_allowed = False
        return True, ""

    def _step_tasker_variable(self, _char: str) -> tuple[bool, str]:
        """A Tasker variable, substituted before the script runs: a value, like a name."""
        end = _tasker_variable_end(self.code, self.position)
        if end == self.position:
            return False, ""
        self.position = end
        self.regex_allowed = False
        return True, ""

    def _step_bracket(self, char: str) -> tuple[bool, str]:
        """An opening bracket, or a closing one that has to match what is open."""
        if char in _OPENERS:
            self.stack.append((char, self.position))
            self.position += 1
            self.regex_allowed = True
            return True, ""
        if char not in _CLOSERS:
            return False, ""
        self.position += 1
        if char == "}" and self.stack and self.stack[-1][0] == _TEMPLATE:
            # The end of a ${...}: back inside the template literal that holds it.
            self.stack.pop()
            self.in_template = True
            return True, ""
        line = self.line(self.position - 1)
        if not self.stack:
            return True, f"A '{char}' on line {line} closes nothing."
        opener, where = self.stack[-1]
        if opener != _CLOSERS[char]:
            return True, f"A '{char}' on line {line} closes the '{opener}' opened on line {self.line(where)}."
        self.stack.pop()
        self.regex_allowed = char == "}"
        return True, ""

    def _step_word_or_operator(self, char: str) -> None:
        """A name, a number, or an operator -- which decides what a '/' after it means."""
        if _IDENTIFIER_START.match(char):
            word = self.code[self.position : self.position + _run_length(_IDENTIFIER, self.code, self.position)]
            self.position += len(word)
            self.regex_allowed = word in _REGEX_AFTER_WORDS
        elif char.isdigit():
            self.position += _run_length(_NUMBER, self.code, self.position)
            self.regex_allowed = False
        else:
            self.position += 1
            self.regex_allowed = True

    def _left_open(self) -> str:
        """What is still open at the end of the script, if anything."""
        if self.in_template:
            return f"A template literal opened on line {self.line(self.stack[-1][1])} is never closed."
        if self.stack:
            opener, where = self.stack[0]
            return f"The '{opener}' opened on line {self.line(where)} is never closed."
        return ""


def js_syntax_problem(code: str) -> str:
    """What is structurally wrong with a script, as a sentence -- or "" if nothing is.

    Checks that every bracket closes the one it should, and that no string, template
    literal, comment or regular expression is left open.  Stops at the first problem: the
    second is usually the first one seen from the other end.
    """
    return _ScriptScan(code).run()


# ##################################################################################
# Shell: is it well-formed?
# ##################################################################################
# A here-document's body is text, not shell, and a 'case' pattern ends in a ')' that
# nothing opened.  Telling either apart from a real mistake needs a parser, so a command
# holding one is given the benefit of the doubt on brackets -- quotes are still checked.
_HERE_DOCUMENT = re.compile(r"<<-?\s*['\"]?\w")
_CASE = re.compile(r"(^|[\s;&|(])case\s")
_WORD_BREAK = " \t\n;&|()<>"

_SHELL_NAMES = {"'": "single quote", '"': "double quote", "`": "backquote", "(": "'('", "$(": "'$('", "${": "'${'"}


class _CommandScan:
    """One pass over a shell command -- shell_syntax_problem's working state.

    'stack' holds what is open: a double quote, a backquote, a $( or ( and a ${.  What a
    character means depends on the innermost of those, which is why the double-quoted
    context has a step of its own: inside one, only another double quote, a $(, a ${ or a
    backquote means anything.
    """

    def __init__(self, command: str, check_brackets: bool) -> None:
        """Start at the top with nothing open."""
        self.command = command
        self.check_brackets = check_brackets
        self.position = 0
        self.stack: list[tuple[str, int]] = []

    def context(self) -> str:
        """The innermost thing open, or "" at the top level."""
        return self.stack[-1][0] if self.stack else ""

    def run(self) -> str:
        """Scan to the end; the first problem found, or ""."""
        command = self.command
        while self.position < len(command):
            char = command[position := self.position]
            if char == "\\":
                self.position += 2
            elif self.context() == '"':
                self._step_in_double_quotes(char)
            elif (end := _tasker_variable_end(command, position)) > position:
                self.position = end  # substituted by Tasker before the shell ever sees it
            elif char == "'":
                end = command.find("'", position + 1)
                if end == -1:
                    return f"A single quote opened on line {_line_of(command, position)} is never closed."
                self.position = end + 1
            elif char == "#" and (position == 0 or command[position - 1] in _WORD_BREAK):
                newline = command.find("\n", position)
                self.position = len(command) if newline == -1 else newline
            elif problem := self._step_structure(char):
                return problem
        if self.stack:
            opener, where = self.stack[0]
            return f"The {_SHELL_NAMES[opener]} opened on line {_line_of(command, where)} is never closed."
        return ""

    def _open_substitution(self) -> bool:
        """A $( or ${ at the cursor opens one; True if it did."""
        for opener in ("$(", "${"):
            if self.command.startswith(opener, self.position):
                self.stack.append((opener, self.position))
                self.position += 2
                return True
        return False

    def _step_in_double_quotes(self, char: str) -> None:
        """Inside "...": its end, a substitution, or a backquote -- anything else is text."""
        if self._open_substitution():
            return
        if char == '"':
            self.stack.pop()
        elif char == "`":
            self.stack.append(("`", self.position))
        self.position += 1

    def _step_structure(self, char: str) -> str:
        """Quotes, backquotes, substitutions and brackets outside double quotes."""
        if self._open_substitution():
            return ""
        context = self.context()
        if char == '"' or (char == "`" and context != "`"):
            self.stack.append((char, self.position))
        elif (char == "`" and context == "`") or (char == "}" and context == "${"):
            self.stack.pop()
        elif char == "(" and self.check_brackets:
            self.stack.append(("(", self.position))
        elif char == ")" and context in ("(", "$("):
            self.stack.pop()
        elif char == ")" and self.check_brackets:
            return f"A ')' on line {_line_of(self.command, self.position)} closes nothing."
        self.position += 1
        return ""


def shell_syntax_problem(command: str) -> str:
    """What is structurally wrong with a shell command, as a sentence -- or "" if nothing is.

    Checks that every quote, backquote, $(...) and ${...} is closed, and that no ')'
    closes something that was never opened.
    """
    if _HERE_DOCUMENT.search(command):
        return ""
    return _CommandScan(command, check_brackets=not _CASE.search(command)).run()


# ##################################################################################
# What healthck calls.
# ##################################################################################
def _code_of(action: Element) -> str:
    """The code an action carries in arg0, or ""."""
    for child in action.findall("Str"):
        if child.attrib.get("sr") == CODE_ARGUMENT:
            return child.text or ""
    return ""


def _task_owners(state: RunState) -> dict[str, str]:
    """{Task id: owning Project name}, in one pass (see proflint._project_owners)."""
    owners: dict[str, str] = {}
    for project_name, project in state.tasker_root_elements["all_projects"].items():
        for member in (item.strip() for item in (project["xml"].findtext("tids") or "").split(",")):
            if member:
                owners[member] = project_name
    return owners


def lint_problems(state: RunState) -> list[Problem]:
    """Every JavaScriptlet and Run Shell action whose code is not well-formed.

    Safe to call with nothing loaded: an empty list comes back.
    """
    problems: list[Problem] = []
    owners = _task_owners(state=state)
    for task_id, task in state.tasker_root_elements["all_tasks"].items():
        where = Target(TASK, task_id, task["name"], owners.get(task_id, ""))
        for number, action in enumerate(actions_in_map_order(task["xml"]), start=1):
            code = action.findtext("code")
            if code not in (JAVASCRIPTLET, RUN_SHELL):
                continue
            text = _code_of(action)
            if not text.strip():
                continue
            if code == JAVASCRIPTLET:
                problem = js_syntax_problem(text)
                tag, what = JS_SYNTAX, "script"
            else:
                problem = shell_syntax_problem(text)
                tag, what = SHELL_SYNTAX, "command"
            if problem:
                problems.append(
                    Problem(
                        WARNING,
                        tag,
                        where.at_action(number),
                        f"{problem}  A {what} that does not parse does not run at all, so this action"
                        " fails every time it is reached.",
                    ),
                )
    return problems
