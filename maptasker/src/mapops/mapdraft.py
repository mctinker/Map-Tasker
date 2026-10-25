"""mapdraft: a Task drafted from a description, out of real actions and their real arguments."""

#! /usr/bin/env python3

#                                                                                        #
# mapdraft: let a language model propose a Task, and nothing more.                       #
#                                                                                        #
# mapask lets a model fill in the boxes of the Find dialog.  This does the same for the   #
# Add Task dialog: "when I get home, turn wifi on and say hello" becomes the actions that  #
# do it, as a draft the user reads and edits before anything is saved.                   #
#                                                                                        #
# The model is given what the Add Task picker itself offers and nothing else -- the list  #
# of actions this tool can build from scratch (taskedit_addable.list_addable_actions), and, once  #
# it has chosen some, the arguments those actions really have, as the editor would show   #
# them.  It is never shown the configuration, so what the user's Tasks hold stays out of  #
# the prompt and the prompt stays one size whatever the backup.  That includes the names   #
# of the Tasks: a "Perform Task" is given a name only if the user's own description names  #
# one, and the name is then checked against the loaded Tasks here, not by the model.      #
#                                                                                        #
# ONE QUESTION FOR MOST DRAFTS, TWO FOR THE REST.  The catalog is a few hundred actions     #
# and each has its own arguments, so showing the arguments of all of them would bury the    #
# question.  The first call is given a primer on how Tasks work, a short list of the common  #
# actions WITH their arguments, the twenty or so other actions that best match the           #
# description WITH theirs (see mapcards, which also says in a sentence what each is for), and  #
# the rest of the catalog by name alone; it chooses the steps and fills in the arguments of   #
# every action it was shown them for.  A second call, for the arguments of only the steps      #
# chosen from the rest of the catalog, is made only if there are any -- so "flash hello, wait  #
# five seconds" costs one round trip, and the wait is what matters most.  A small local model  #
# gets neither the long list nor the arguments: a handful of actions matching the            #
# description's words, and the same second call.                                            #
#                                                                                        #
# What comes back is not trusted, exactly as in mapask.  An action that is not in the      #
# catalog is dropped and SAID to have been dropped, an argument the action does not have   #
# likewise, and a value is checked the way the editor checks one typed by hand: a number   #
# has to be a number, a choice has to be one of the choices, a checkbox a yes or a no.     #
# A block the model left open ("If" with no "End If") is closed, and says so.  What        #
# survives is built with the same functions the picker uses, so a drafted action is the    #
# very element a hand-added one would be -- and it goes into the editor's own working     #
# copy, where nothing is kept until the user presses Ok.                                  #
#                                                                                        #
# Same contract as mapask: no GUI import, and a provider's library is imported only when a  #
# question is actually put to it.                                                        #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from maptasker.src.analysis.mapask import (
    LLAMA,
    Asker,
    AskError,
    ModelSettings,
    ask_model,
    canonical,
    reply_object,
    values_of,
)
from maptasker.src.core.actionc import action_codes
from maptasker.src.core.sysconst import logger
from maptasker.src.edit import taskedit, taskedit_addable, taskedit_apply, taskedit_args, taskedit_model
from maptasker.src.mapops import mapcards

if TYPE_CHECKING:
    from collections.abc import Collection

    from maptasker.src.core.primitem import RunState

# The longest Task a draft may be.  A description that wants more than this is better
# drafted in pieces, and a model that has run away should not fill the editor.
MAX_STEPS = 30
# The longest description sent.  A paragraph is plenty; a page is a different tool.
MAX_DESCRIPTION = 2000
# How many choices of one dropdown the model is shown.  What it names is checked against the
# whole list either way.
MAX_OPTIONS = 100
# How long a drafted Task's name, and one value of one argument, may be.
MAX_NAME = 80
MAX_VALUE = 4000

# The replies are small JSON objects, but a long Task's arguments are not tiny.
PLAN_MAX_TOKENS = 4096
DETAIL_MAX_TOKENS = 4096
# How long to wait for one answer.  A model that reasons first can be slow, and one running on
# this computer slower still; either way the user can stop sooner (see guiwins_draft).
ASK_TIMEOUT = 120.0
LOCAL_ASK_TIMEOUT = 600.0
# How many actions a small local model is shown, and the actions it is always shown.
MAX_CANDIDATES = 25
# How many of the best-matching actions a cloud model is shown in full, and the most arguments one
# may have to be shown that way; an action with more is shown by name and asked about next.
MAX_RELATED = 20
MAX_RELATED_ARGS = 10
# The most options of a choice that are listed beside a common action; one with more is asked
# about in the second call, where there is room to list them.
MAX_INLINE_OPTIONS = 12

# The blocks the draft keeps balanced: opener -> closer.  If is the one whose middle can be
# split with an Else.  Nothing else in the catalog opens something that has to be closed.
_BLOCK_CLOSER = {taskedit_model.IF_ACTION_KEY: taskedit_model.END_IF_ACTION_KEY, "39t": "40t"}
_BLOCK_NAME = {taskedit_model.IF_ACTION_KEY: "an If", "39t": "a For"}

# What a model says for a checkbox, in place of the "true"/"false" it was asked for.
_YES = {"true", "1", "yes", "on", "y"}
_NO = {"false", "0", "no", "off", "n"}

# The replies' shapes, which models that can be held to one are held to (see mapask).  The
# arguments are a list of {id, value} rather than an object keyed by id: a schema cannot
# describe an object whose keys are not known in advance.
_ARGS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {"id": {"type": "string"}, "value": {"type": "string"}},
        "required": ["id", "value"],
        "additionalProperties": False,
    },
}
PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "purpose": {"type": "string"},
                    "label": {"type": "string"},
                    "args": _ARGS_SCHEMA,
                },
                "required": ["action", "purpose", "label", "args"],
                "additionalProperties": False,
            },
        },
        "unexpressed": {"type": "string"},
    },
    "required": ["name", "steps", "unexpressed"],
    "additionalProperties": False,
}
DETAIL_SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"step": {"type": "integer"}, "label": {"type": "string"}, "args": _ARGS_SCHEMA},
                "required": ["step", "label", "args"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["steps"],
    "additionalProperties": False,
}

# The common actions, and which of their arguments the first question lists beside them (by
# the id the editor gives each).  Chosen for what a description in plain words most often asks
# for.  An action is looked up by key, so one the catalog does not have (a newer or older
# Tasker) is quietly not listed; the arguments left off a listed action are the rarely used ones,
# and a model that names one anyway has it checked like any other.
_COMMON_ACTIONS: dict[str, tuple[str, ...]] = {
    taskedit_model.IF_ACTION_KEY: ("if_lhs", "if_op", "if_rhs"),
    taskedit_model.ELSE_ACTION_KEY: (),
    taskedit_model.END_IF_ACTION_KEY: (),
    "39t": ("0", "1"),  # For: Variable, Items
    "40t": (),
    "547t": ("0", "1", "3"),  # Variable Set: Name, To, Do Maths
    "888t": ("0", "1"),  # Variable Add
    "890t": ("0", "1"),  # Variable Subtract
    "549t": ("0",),  # Variable Clear
    "545t": ("0", "1", "2"),  # Variable Randomize: Name, Min, Max
    "548t": ("0", "1"),  # Flash: Text, Long
    "559t": ("0",),  # Say: Text
    "523t": ("0", "1"),  # Notify: Title, Text
    "30t": ("0", "1", "2", "3"),  # Wait: MS, Seconds, Minutes, Hours
    "130t": ("0", "2", "3", "4"),  # Perform Task: Name, Parameter 1, Parameter 2, Return Value Variable
    "137t": (),  # Stop
    "126t": ("0",),  # Return: Value
    "135t": ("0", "1"),  # Goto: Type, Number
    "339t": ("1", "2", "3", "5"),  # HTTP Request: Method, URL, Headers, Body
    "104t": ("0",),  # Browse URL
    "105t": ("0",),  # Set Clipboard: Text
    "41t": ("0", "1"),  # Send SMS: Number, Message
    "61t": ("0",),  # Vibrate: Time
    "425t": ("0",),  # WiFi: Set
    "294t": ("0",),  # Bluetooth: Set
    "433t": ("0",),  # Mobile Data: Set
    "333t": ("0",),  # Airplane Mode: Set
    "511t": ("0",),  # Torch: Set
    "810t": ("0",),  # Display Brightness: Level
    "307t": ("0",),  # Media Volume: Level
    "304t": ("0",),  # Ringer Volume: Level
}
# What a small local model is always shown, whatever the description says.
_BASIC_ACTIONS = (
    taskedit_model.IF_ACTION_KEY,
    taskedit_model.ELSE_ACTION_KEY,
    taskedit_model.END_IF_ACTION_KEY,
    "547t",
    "548t",
    "30t",
)

_PRIMER = """\
How Tasker Tasks work:
  - A Task is a list of actions that run in order, top to bottom. Each action does one thing: \
show a message, set a variable, change a setting, fetch a web address, run another Task.
  - Variables are written %name. A lower-case one (%count) belongs to the Task; an upper-case \
one (%WIFI, %BATT) is a Tasker built-in or a global. They can be used inside any text argument, \
as in "Hello %name". Variable Set stores a value in a variable; with "Do Maths" on, its value is \
a calculation such as %count+1.
  - Logic is made from actions: If <Target> <Operator> <Value>, optionally Else, then End If; \
For <Variable> in <Items>, then End For. Every If and every For must be closed. Stop ends the \
Task early and Perform Task runs another Task by name.
  - To test two things, nest one If inside the other, each closed by its own End If. The \
actions between the innermost If and its End If run only when both hold.
  - A trigger -- "when I get home", "at 8am", "when the battery is low" -- is not an action. It \
belongs to a Profile, which the Task is attached to later. Leave it out and say so in "unexpressed".
  - Wait takes its length in the argument for the unit: Seconds for seconds, Minutes for minutes.
  - A setting such as WiFi, Bluetooth, Mobile Data, Airplane Mode or Torch has a "Set" checkbox: \
"true" switches it on, "false" off.
  - Prefer the common actions to the rest, and the built-in actions to a plugin's.
"""
# What a small model has room for.
_PRIMER_SHORT = """\
A Task is a list of Tasker actions that run in order. Variables are written %name. Logic is the \
actions If, Else and End If, and For and End For, which must be closed. A trigger such as "when \
I get home" is a Profile, not an action.
"""

_PLAN_INSTRUCTIONS = """\
You draft a Tasker (Android automation) Task from a description, for MapTasker's Add Task \
dialog. You choose the actions; a person reviews and edits the draft before anything is saved.

{primer}
{given}

Rules for the reply:
  - "action" is a key copied exactly from what you are given, and only the key -- "548t", not \
"548t Flash". Never invent one. If nothing does a part of the description, leave that part out and say so in "unexpressed".
  - Prefer the fewest actions that do the job. At most {max_steps} steps.
  - Every If and every For must be closed by its End If or End For, and Else belongs between an \
If and its End If.
  - "purpose" is one short sentence saying what the step does, with the specific values it \
needs -- the text to show, the variable to set, the number of seconds.
  - "label" is a short name for the step, or "".
{arguments}
  - "name" is a short name for the Task, or "" if the description gives none to suggest.
  - "unexpressed": one short sentence naming any part of the description that no action can do, \
or "" if there is none.
  - Reply with one JSON object and nothing else, with exactly these keys: "name", "steps" (a \
list of objects with "action", "purpose", "label" and "args"), "unexpressed".
"""

_GIVEN_FULL = """\
You are given the common actions with the arguments they take, then the other actions that best \
match the description, some with their arguments too, and then every remaining action the editor \
can build, each as "key name" under its category. Under an action, an indented line says what it is \
for. Prefer an action from the first two lists when one does the job."""
_GIVEN_SHORT = """\
You are given some of the actions the editor can build, each as "key name"."""

_ARGUMENTS_FULL = """\
  - "args": for an action listed with arguments, a list of {"id", "value"} for the arguments the \
step has to set, using only the ids listed for it; leave out every argument it does not need, which \
keeps its default. For any action listed without arguments give [] -- its arguments, if it has \
any, are asked for next.
  - A "text" argument takes any text, and may use variables such as %city. A "number" argument \
takes a whole number only. A "checkbox" takes "true" or "false". A "choice" takes one of its \
options, copied exactly.
  - In an If, "Target" is a variable (such as %WIFI) or plain text, "Operator" is one of its \
options, copied exactly ("=" for "is" or "equals"), and "Value" is what it is compared with.
  - A "Perform Task" Name is the name of a Task that already exists, and you are not told which \
Tasks there are: give it only if the description names one, exactly as written there.
  - The text, number or value the description gives goes in "args", not only in "purpose": a \
step with a blank "args" keeps the action's defaults and does nothing useful.

Example. For the description "flash Hi if %WIFI is on" the reply is:
{"name": "Hi on WiFi", "steps": [\
{"action": "37t", "purpose": "if WiFi is on", "label": "", "args": [{"id": "if_lhs", "value": "%WIFI"}, \
{"id": "if_op", "value": "="}, {"id": "if_rhs", "value": "on"}]}, \
{"action": "548t", "purpose": "show Hi", "label": "", "args": [{"id": "0", "value": "Hi"}]}, \
{"action": "38t", "purpose": "end the If", "label": "", "args": []}], "unexpressed": ""}"""
_ARGUMENTS_SHORT = """\
  - "args" is always []: the arguments are asked for next."""

_DETAIL_INSTRUCTIONS = """\
You fill in the arguments of the steps of a Tasker Task that has been drafted from a \
description. You are given the description and, for each step, the action, what it is for, \
and the arguments it has.

Rules for the reply:
  - For each step with something to set, give "step" (its number as given), a "label" (a short \
name for the step, or "") and "args": a list of {{"id", "value"}} using only the argument ids \
listed for that step. Leave out every argument the step does not need; it keeps its default.
  - A "text" argument takes any text, and may use Tasker variables such as %city. A "number" \
argument takes a whole number only. A "checkbox" takes "true" or "false". A "choice" takes \
one of the options listed, copied exactly.
  - In an If, the argument "Target" is a variable (such as %WIFI) or plain text, "Operator" is \
one of its options and "Value" is what it is compared with.
  - A "Perform Task" Name is the name of a Task that already exists, and you are not told \
which Tasks there are: give it only if the description names one, exactly as written there, \
and otherwise leave it out.
  - Never invent an argument id or an option.
  - Variables are written %name, and a text argument may use them.
  - Reply with one JSON object and nothing else, with exactly one key: "steps".
"""


# ##################################################################################
# What the model proposes, and what is left of it once it has been checked.
# ##################################################################################
@dataclass(frozen=True)
class PlanStep:
    """One action the model chose, what it said the step is for, and any arguments it already gave.

    'args' are (argument id, value) as the model wrote them, unchecked: they are checked once
    the steps are final, when the number a note names the step by can no longer change.
    """

    action_key: str
    purpose: str = ""
    label: str = ""
    args: tuple[tuple[str, object], ...] = ()


@dataclass(frozen=True)
class Plan:
    """The first reply, checked: only actions in the catalog, and every block closed."""

    name: str
    steps: tuple[PlanStep, ...]
    # Actions named that the editor cannot build, as the model spelled them.
    unknown: tuple[str, ...] = ()
    # What was changed to make the steps a Task that can be built.
    adjusted: tuple[str, ...] = ()
    # The model's own note on what the description asks for that no action does.
    unexpressed: str = ""


@dataclass(frozen=True)
class DraftStep:
    """One drafted action: which, how it is labelled, and the arguments that were set.

    'values' is by argument id, and holds only values that passed the check -- an argument
    left out keeps the default the editor gives a hand-added action.
    """

    action_key: str
    label: str = ""
    values: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Draft:
    """A Task as drafted, with everything that was left out of it and why."""

    name: str
    steps: tuple[DraftStep, ...]
    unknown: tuple[str, ...] = ()
    # Arguments or values that could not be used, as "Step 2 (Flash): ...".
    dropped: tuple[str, ...] = ()
    adjusted: tuple[str, ...] = ()
    unexpressed: str = ""

    @property
    def is_empty(self) -> bool:
        """Whether there is nothing to put in the editor."""
        return not self.steps


@dataclass(frozen=True)
class FillableArg:
    """One argument of an action that a draft may set, in the terms the model is given."""

    arg_id: str
    name: str
    kind: str  # "text" | "number" | "checkbox" | "choice"
    options: tuple[str, ...] = ()
    is_task_name: bool = False


@dataclass(frozen=True)
class Applied:
    """What putting a draft into an editor's Task came to."""

    # Where the first drafted action landed, or None if none could be added.
    first_act_number: int | None
    added: int = 0
    # Everything that did not go in as drafted, and plugin actions that need configuring.
    notes: tuple[str, ...] = ()


# ##################################################################################
# What the model is shown.
# ##################################################################################
def action_catalog(state: RunState) -> list[dict]:
    """The actions a draft may use: exactly the ones the Add Task picker lets the user add."""
    return [row for row in taskedit_addable.list_addable_actions(state=state) if row["addable"]]


def _catalog_text(rows: list[dict]) -> str:
    """The catalog as the model reads it: a heading per category, then 'key name' lines."""
    by_category: dict[str, list[dict]] = {}
    for row in rows:
        by_category.setdefault(row["category_name"], []).append(row)
    lines = []
    for category in sorted(by_category):
        lines.append(f"## {category}")
        lines += [f"{row['action_key']} {row['name']}" for row in by_category[category]]
    return "\n".join(lines)


def common_actions(state: RunState, scratch: dict | None = None) -> dict[str, list[FillableArg]]:
    """The common actions this catalog has, with the arguments the first question lists for each."""
    keys = {row["action_key"] for row in action_catalog(state)}
    common: dict[str, list[FillableArg]] = {}
    for key, arg_ids in _COMMON_ACTIONS.items():
        if key not in keys:
            continue
        common[key] = [
            arg
            for arg in fillable_args(key, state, scratch)
            if arg.arg_id in arg_ids and len(arg.options) <= MAX_INLINE_OPTIONS
        ]
    return common


def _listing_text(heading: str, listed: dict[str, list[FillableArg] | None]) -> str:
    """Actions as the model reads them: 'key name', then each argument it may set, then what the action is for.

    An action whose arguments are None is listed by name alone, to be asked about next.
    """
    lines = [heading]
    for key, args in listed.items():
        shown = "; ".join(f"{arg.arg_id} {arg.name} ({_kind_for_prompt(arg)})" for arg in args or ())
        lines.append(f"{key} {action_codes[key].name}" + (f": {shown}" if shown else ""))
        lines += mapcards.card_lines(key)
    return "\n".join(lines)


def _kind_for_prompt(arg: FillableArg) -> str:
    """An argument's kind, with a choice's options after it."""
    return f"choice: {' | '.join(arg.options)}" if arg.options else arg.kind


def _candidates(description: str, rows: list[dict]) -> list[dict]:
    """The few actions that most plausibly do what a description says, for a model with no room for them all.

    Ranked by mapcards on the words of the description against each action's name and card.  The
    actions every Task is likely to need are always included.  Only what is SHOWN is limited --
    what comes back is checked against the whole catalog.
    """
    chosen = mapcards.rank(description, rows, MAX_CANDIDATES)
    keys = {row["action_key"] for row in chosen}
    basics = [row for row in rows if row["action_key"] in _BASIC_ACTIONS and row["action_key"] not in keys]
    return basics + chosen


def related_actions(
    description: str,
    state: RunState,
    scratch: dict | None = None,
) -> dict[str, list[FillableArg] | None]:
    """The actions outside the common list that best match a description, with their arguments where they fit.

    An action maps to its arguments when it can be listed in full -- few enough arguments, and none
    with a long list of choices -- and to None when it can only be named, its arguments being
    asked about in the second question.  Order is best match first.
    """
    common = set(_COMMON_ACTIONS)
    rows = [row for row in action_catalog(state) if row["action_key"] not in common]
    related: dict[str, list[FillableArg] | None] = {}
    for row in mapcards.rank(description, rows, MAX_RELATED):
        args = fillable_args(row["action_key"], state, scratch)
        fits = len(args) <= MAX_RELATED_ARGS and all(len(arg.options) <= MAX_INLINE_OPTIONS for arg in args)
        related[row["action_key"]] = args if fits else None
    return related


def listed_with_arguments(
    description: str,
    state: RunState,
    scratch: dict | None = None,
) -> dict[str, list[FillableArg]]:
    """Every action the first question lists WITH its arguments: the common ones, and the best matches that fit."""
    listed = dict(common_actions(state, scratch))
    listed.update({key: args for key, args in related_actions(description, state, scratch).items() if args is not None})
    return listed


def build_plan_prompt(
    description: str,
    state: RunState,
    scratch: dict | None = None,
    *,
    compact: bool = False,
) -> tuple[str, str]:
    """(system prompt, user message) for the first question: which actions, in what order, and their arguments.

    'compact' is for a model with room for little: no argument lists and only the actions that
    look relevant, so everything it chooses has its arguments asked for in the second question.
    """
    rows = action_catalog(state)
    if compact:
        primer, given, arguments = _PRIMER_SHORT, _GIVEN_SHORT, _ARGUMENTS_SHORT
        listing = _catalog_text(_candidates(description, rows))
    else:
        primer, given, arguments = _PRIMER, _GIVEN_FULL, _ARGUMENTS_FULL
        common = common_actions(state, scratch)
        related = related_actions(description, state, scratch)
        listed = set(common) | set(related)
        listing = "\n\n".join(
            part
            for part in (
                _listing_text("## Common actions, with their arguments", common),
                _listing_text("## Best matches for this description", related) if related else "",
                "## Other actions",
                _catalog_text([r for r in rows if r["action_key"] not in listed]),
            )
            if part
        )
    system = _PLAN_INSTRUCTIONS.format(max_steps=MAX_STEPS, primer=primer, given=given, arguments=arguments)
    user = "\n".join(["Actions you may use:", listing, "", f"Description: {description.strip()}"])
    return system, user


def fillable_args(action_key: str, state: RunState, scratch: dict | None = None) -> list[FillableArg]:
    """The arguments of an action that a draft can set, read off the action as the editor builds it.

    Built the way Add Task builds a new one, in a Task of its own that is thrown away, so the
    arguments and choices are the ones the user would be shown and cannot drift from them.
    Pickers for an Application or an icon, and anything the editor shows read-only, are left
    out: there is nothing here the model could choose them from.

    'scratch' memoizes the answer across the actions of one draft.
    """
    if scratch is not None and action_key in scratch:
        return scratch[action_key]
    task = taskedit.create_new_task("draft", "100", state=state)
    result: list[FillableArg] = []
    if not isinstance(task, str):
        action = taskedit.add_action_to_task(task, action_key, state=state)
        if not isinstance(action, list):
            result = [spec for arg in action.args if (spec := _fillable(action.code, arg)) is not None]
    if scratch is not None:
        scratch[action_key] = result
    return result


def _fillable(action_code: str, arg: taskedit_model.EditableArg) -> FillableArg | None:
    """One editor argument as the model is told about it, or None if it is not one it can set."""
    if arg.widget_kind == "checkbox":
        return FillableArg(arg.arg_id, arg.arg_name, "checkbox")
    if arg.widget_kind == "dropdown":
        return FillableArg(arg.arg_id, arg.arg_name, "choice", tuple(arg.dropdown_options or ()))
    if arg.widget_kind in ("text", "raw_fallback"):
        kind = "number" if arg.backing_tag == "Int" and not arg.is_var else "text"
        is_task_name = taskedit_args.is_perform_task_name_arg(action_code, arg)
        return FillableArg(arg.arg_id, arg.arg_name, kind, is_task_name=is_task_name)
    return None


def build_detail_prompt(
    description: str,
    plan: Plan,
    state: RunState,
    scratch: dict | None = None,
    answered: Collection[int] = (),
) -> tuple[str, str] | None:
    """(system prompt, user message) for the second question, or None if no step has an argument to set.

    'answered' are the steps (counted from 0) whose arguments the first question already got: the
    model has had its chance to set those, so they are not asked about again.
    """
    steps = []
    for number, step in enumerate(plan.steps):
        if number in answered:
            continue
        args = fillable_args(step.action_key, state, scratch)
        if not args:
            continue
        shown: dict[str, object] = {
            "step": number + 1,
            "action": action_codes[step.action_key].name,
            "purpose": step.purpose,
        }
        card = mapcards.cards().get(step.action_key)
        if card is not None and card.note:
            shown["note"] = card.note
        shown["args"] = [_arg_for_prompt(arg) for arg in args]
        steps.append(shown)
    if not steps:
        return None

    lines = [
        f"Description: {description.strip()}",
        "",
        "Steps, numbered from 1:",
        *(json.dumps(step, ensure_ascii=False) for step in steps),
    ]
    return _DETAIL_INSTRUCTIONS, "\n".join(lines)


def _arg_for_prompt(arg: FillableArg) -> dict:
    """One argument as a small JSON object for the second prompt."""
    shown: dict[str, object] = {"id": arg.arg_id, "name": arg.name, "kind": arg.kind}
    if arg.options:
        shown["options"] = list(arg.options[:MAX_OPTIONS])
    return shown


# ##################################################################################
# The replies.
# ##################################################################################
def _action_key(raw: str, rows: list[dict]) -> str:
    """The catalog key a model's action reference means, or "" if it names none.

    The key itself, with or without the trailing 't'; the line it was copied from ("37t If",
    which is how the catalog is written, and is what a model most often sends back); failing
    those the action's name, but only when exactly one action has that name.
    """
    text = raw.strip()
    keys = {row["action_key"] for row in rows}
    first = text.split(maxsplit=1)[0].rstrip(":,") if text else ""
    for candidate in (text, f"{text}t", first, f"{first}t"):
        if candidate in keys:
            return candidate
    named = [row["action_key"] for row in rows if row["name"].casefold() == text.casefold()]
    return named[0] if len(named) == 1 else ""


def _name(raw: object) -> str:
    """A drafted Task's name, on one line and no longer than a name should be."""
    return " ".join(str(raw or "").split())[:MAX_NAME]


def _label(raw: object) -> str:
    """A drafted action's label, on one line and no longer than a label should be."""
    return " ".join(str(raw or "").split())[:MAX_NAME]


def _given_args(item: dict) -> tuple[tuple[str, object], ...]:
    """The (id, value) pairs a step of a reply carries, as written."""
    given = item.get("args")
    entries = [entry for entry in given if isinstance(entry, dict)] if isinstance(given, list) else []
    return tuple((str(entry.get("id") or ""), entry.get("value")) for entry in entries)


def parse_plan(reply: str, state: RunState) -> Plan:
    """Turn the first reply into steps that are all in the catalog, with every block closed."""
    fields = reply_object(reply, "draft")
    rows = action_catalog(state)

    named = fields.get("steps")
    if not isinstance(named, list):
        named = []
    steps: list[PlanStep] = []
    unknown: list[str] = []
    for item in named:
        if not isinstance(item, dict):
            continue
        raw = str(item.get("action") or "").strip()
        if not raw:
            continue
        key = _action_key(raw, rows)
        if key:
            steps.append(
                PlanStep(key, str(item.get("purpose") or "").strip(), _label(item.get("label")), _given_args(item)),
            )
        else:
            unknown.append(raw)

    adjusted: list[str] = []
    if len(steps) > MAX_STEPS:
        adjusted.append(f"Kept the first {MAX_STEPS} of {len(steps)} steps.")
        steps = steps[:MAX_STEPS]
    steps, balanced = _balanced(steps)
    adjusted += balanced

    note = " ".join(values_of(fields.get("unexpressed")))
    return Plan(
        name=_name(fields.get("name")),
        steps=tuple(steps),
        unknown=tuple(unknown),
        adjusted=tuple(adjusted),
        unexpressed="" if note.strip(" .").casefold() in {"", "none", "n/a", "null", "nothing"} else note,
    )


def _balanced(steps: list[PlanStep]) -> tuple[list[PlanStep], list[str]]:
    """The steps with every If and For closed, and any Else or End that closes nothing taken out.

    Said, not silent: the model asked for something other than what is left.  A block left
    open is closed at the end, innermost first, because an unclosed If runs the rest of the
    Task only when its condition holds and a draft that does that unannounced is a bug.
    """
    kept: list[PlanStep] = []
    notes: list[str] = []
    open_blocks: list[str] = []
    has_else: list[bool] = []
    closers = {closer: opener for opener, closer in _BLOCK_CLOSER.items()}
    for step in steps:
        key = step.action_key
        if key in _BLOCK_CLOSER:
            open_blocks.append(key)
            has_else.append(False)
        elif key == taskedit_model.ELSE_ACTION_KEY:
            if not open_blocks or open_blocks[-1] != taskedit_model.IF_ACTION_KEY or has_else[-1]:
                notes.append("Left out an Else that was not inside an If.")
                continue
            has_else[-1] = True
        elif key in closers:
            if not open_blocks or open_blocks[-1] != closers[key]:
                name = action_codes[key].name
                notes.append(f"Left out an {name} that closed nothing.")
                continue
            open_blocks.pop()
            has_else.pop()
        kept.append(step)
    for opener in reversed(open_blocks):
        kept.append(PlanStep(_BLOCK_CLOSER[opener]))
        notes.append(f"Added the {action_codes[_BLOCK_CLOSER[opener]].name} that closes {_BLOCK_NAME[opener]}.")
    return kept, notes


def _checked_value(arg: FillableArg, raw: object, state: RunState) -> tuple[str, str]:
    """(the value to set, "") or ("", why it cannot be) -- the check the editor applies, up front."""
    text = str(raw).strip() if not isinstance(raw, bool) else str(raw).lower()
    if arg.kind == "checkbox":
        if text.casefold() in _YES:
            return "1", ""
        if text.casefold() in _NO:
            return "0", ""
        return "", f"'{text}' is not true or false"
    if arg.kind == "choice":
        chosen = canonical(text, arg.options)
        return (chosen, "") if chosen else ("", f"'{text}' is not one of its options")
    if arg.kind == "number":
        if text.lstrip("-").isdigit():
            return text, ""
        return "", f"'{text}' is not a whole number"
    value = str(raw)[:MAX_VALUE]
    if arg.is_task_name:
        chosen = canonical(value.strip(), taskedit_args.get_all_task_names(state))
        return (chosen, "") if chosen else ("", f"there is no Task named '{value.strip()}'")
    return value, ""


def settle_plan(plan: Plan, state: RunState, scratch: dict | None = None) -> tuple[list[DraftStep], list[str]]:
    """The plan's steps as drafted, with the arguments the first reply gave checked against the actions' own.

    Returns:
        One DraftStep per step of the plan, and what was left out and why.
    """
    dropped: list[str] = []
    drafted: list[DraftStep] = []
    for number, step in enumerate(plan.steps):
        values: dict[str, str] = {}
        if step.args:
            specs = {arg.arg_id: arg for arg in fillable_args(step.action_key, state, scratch)}
            where = f"Step {number + 1} ({action_codes[step.action_key].name})"
            entries = [{"id": arg_id, "value": value} for arg_id, value in step.args]
            values = _checked_values(entries, specs, where, dropped, state)
        drafted.append(DraftStep(step.action_key, step.label, values))
    return drafted, dropped


def parse_details(
    reply: str,
    plan: Plan,
    drafted: list[DraftStep],
    state: RunState,
    scratch: dict | None = None,
) -> tuple[list[DraftStep], list[str]]:
    """Add the second reply's labels and argument values to the steps drafted so far, checked as the first's were.

    Returns:
        The steps, with each one the reply was about carrying what it said, and what was left out and why.
    """
    by_step, dropped = _replies_by_step(reply_object(reply, "draft"), len(plan.steps))

    steps = list(drafted)
    for number, item in by_step.items():
        step = drafted[number]
        where = f"Step {number + 1} ({action_codes[step.action_key].name})"
        specs = {arg.arg_id: arg for arg in fillable_args(step.action_key, state, scratch)}
        values = {**step.values, **_checked_values(item.get("args"), specs, where, dropped, state)}
        steps[number] = DraftStep(step.action_key, _label(item.get("label")) or step.label, values)
    return steps, dropped


def _replies_by_step(fields: dict, step_count: int) -> tuple[dict[int, dict], list[str]]:
    """The second reply's entries by the step they are for (counted from 0), and the ones for no step."""
    given = fields.get("steps")
    by_step: dict[int, dict] = {}
    dropped: list[str] = []
    for item in given if isinstance(given, list) else []:
        number = item.get("step") if isinstance(item, dict) else None
        if isinstance(number, str) and number.strip().isdigit():
            number = int(number)
        if isinstance(number, int) and not isinstance(number, bool) and 1 <= number <= step_count:
            by_step.setdefault(number - 1, item)
        else:
            dropped.append(f"A reply for a step that does not exist ({number!r}).")
    return by_step, dropped


def _spec_for(raw_id: str, specs: dict[str, FillableArg]) -> FillableArg | None:
    """The argument a model's id means: the id itself, or the name it was listed under (a model's other slip)."""
    spec = specs.get(raw_id)
    if spec is not None:
        return spec
    named = [arg for arg in specs.values() if arg.name.casefold() == raw_id.casefold()]
    return named[0] if len(named) == 1 else None


def _checked_values(
    args: object,
    specs: dict[str, FillableArg],
    where: str,
    dropped: list[str],
    state: RunState,
) -> dict[str, str]:
    """The values in one step's reply that its action's arguments accept; the rest go on 'dropped'."""
    values: dict[str, str] = {}
    for entry in args if isinstance(args, list) else []:
        if not isinstance(entry, dict):
            continue
        raw_id = str(entry.get("id") or "").strip().removeprefix("arg")
        raw = entry.get("value")
        if raw is None or str(raw).strip() == "":
            continue
        spec = _spec_for(raw_id, specs)
        if spec is None:
            dropped.append(f"{where}: there is no argument '{raw_id}'.")
        elif spec.arg_id in values:
            dropped.append(f"{where}: '{spec.name}' was given twice.")
        else:
            value, why = _checked_value(spec, raw, state)
            if why:
                dropped.append(f"{where}: '{spec.name}' left at its default, because {why}.")
            else:
                values[spec.arg_id] = value
    return values


# ##################################################################################
# Asking.
# ##################################################################################
async def draft_task(description: str, settings: ModelSettings, state: RunState, ask: Asker = ask_model) -> Draft:
    """Draft a Task from a description in plain words.

    A coroutine, so that the caller can run it as a task and cancel it, which cancels the
    request to the model with it -- see mapask.translate.  'ask' is the model call, a
    parameter so that everything around it can be tested with a function standing in.

    Raises:
        AskError: for a description that is empty, no backup to draft against, or a model
            that could not be asked or did not answer with a draft.
    """
    description = (description or "").strip()
    if not description:
        message = "Describe the Task first."
        raise AskError(message)
    if state.xml_root is None:
        message = "Load a Tasker backup file first (a draft is built the way Add Task builds a Task)."
        raise AskError(message)
    description = description[:MAX_DESCRIPTION]

    # A model on this computer is held to the short prompt and given longer to answer; one in the
    # cloud is asked not to deliberate over what is a lookup.
    compact = settings.provider == LLAMA
    timeout = LOCAL_ASK_TIMEOUT if compact else ASK_TIMEOUT
    scratch: dict = {}

    system, user = build_plan_prompt(description, state, scratch, compact=compact)
    plan_settings = dataclasses.replace(
        settings,
        schema=PLAN_SCHEMA,
        max_tokens=PLAN_MAX_TOKENS,
        effort="low",
        timeout=timeout,
    )
    reply = await ask(plan_settings, system, user)
    logger.debug(f"mapdraft: {settings.model} planned {reply!r}")
    plan = parse_plan(reply, state)
    steps, dropped = settle_plan(plan, state, scratch)

    # The arguments of the actions listed with theirs were asked for with the steps; the others are asked
    # for now.  So is a listed action that was given none, though it has some listed: a Flash with no text
    # is a model that put the text in the step's purpose, not one that meant it to say nothing.
    listed = {} if compact else listed_with_arguments(description, state, scratch)
    answered = {
        number
        for number, (planned, drafted) in enumerate(zip(plan.steps, steps, strict=True))
        if planned.action_key in listed and (drafted.values or not listed[planned.action_key])
    }
    detail = build_detail_prompt(description, plan, state, scratch, answered) if plan.steps else None
    if detail is not None:
        system, user = detail
        detail_settings = dataclasses.replace(
            settings,
            schema=DETAIL_SCHEMA,
            max_tokens=DETAIL_MAX_TOKENS,
            effort="low",
            timeout=timeout,
        )
        reply = await ask(detail_settings, system, user)
        logger.debug(f"mapdraft: {settings.model} detailed {reply!r}")
        steps, more = parse_details(reply, plan, steps, state, scratch)
        dropped += more

    return Draft(
        name=plan.name,
        steps=tuple(steps),
        unknown=plan.unknown,
        dropped=tuple(dropped),
        adjusted=plan.adjusted,
        unexpressed=plan.unexpressed,
    )


# ##################################################################################
# Putting the draft in the editor.
# ##################################################################################
def apply_draft(edited_task: taskedit_model.EditableTask, draft: Draft, state: RunState) -> Applied:
    """Append the drafted actions to an editor's working copy of a Task.

    Built with taskedit's own add_action_to_task, so each is the action a hand-added one
    would be, and nothing reaches the loaded configuration: the working copy is only kept
    when the user presses Ok.  A step whose values fail the editor's own check goes in with
    its defaults and says so, rather than being refused whole.
    """
    first: int | None = None
    added = 0
    notes: list[str] = []
    for number, step in enumerate(draft.steps):
        action = taskedit.add_action_to_task(edited_task, step.action_key, None, state=state)
        where = f"Step {number + 1} ({action_codes[step.action_key].name})"
        if isinstance(action, list):
            notes.append(f"{where}: could not be added -- {action[0] if action else 'unknown reason'}")
            continue
        added += 1
        if first is None:
            first = action.act_number
        _set_values(action, step, where, notes, state)
        if taskedit_addable.needs_tasker_configuration(action.action_element):
            notes.append(f"{where}: {taskedit_addable.PLUGIN_CONFIGURATION_WARNING.format(name=action.action_name)}")
    return Applied(first, added, tuple(notes))


def _set_values(
    action: taskedit_model.EditableAction,
    step: DraftStep,
    where: str,
    notes: list[str],
    state: RunState,
) -> None:
    """Write one drafted action's label and argument values onto it, if they pass the editor's checks."""
    if step.label:
        taskedit_apply.set_action_label(action, step.label)
    if not step.values:
        return

    def key_for_arg(arg: taskedit_model.EditableArg) -> str:
        return taskedit_apply.arg_key(action.act_number, arg.arg_id)

    arg_values = {key_for_arg(arg): step.values[arg.arg_id] for arg in action.args if arg.arg_id in step.values}
    errors = taskedit_apply.validate_arg_values(action.args, key_for_arg, arg_values)
    if action.code == taskedit_model.IF_ACTION_CODE:
        errors += taskedit_apply.validate_if_condition_values(action, key_for_arg, arg_values)
    if errors:
        notes.extend(f"{where}: left at its defaults -- {error}" for error in errors)
        return
    taskedit_apply.apply_arg_values(action.args, key_for_arg, arg_values, state=state)
    # The values now live in the XML; rebuild what the editor shows from it.
    taskedit_args.reclassify_action_args(action, state=state)
