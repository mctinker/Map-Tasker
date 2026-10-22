"""sceneedit_v2state: a component's state fields and its Show-When condition.

Which of a component's properties are state (a switch's checked, a text box's value), what the Show-When
builder offers to compare against, and reading a state field as its dynamic, variable or literal form."""

from __future__ import annotations

from typing import TYPE_CHECKING

from maptasker.src.core.taskervars import tasker_global_variable_names, tasker_global_variables
from maptasker.src.edit.sceneedit_v2 import (
    V2_DYNAMIC_STATE,
    V2_SHOW_WHEN_ENVIRONMENT,
    V2_SHOW_WHEN_LOGICAL_OPERATORS,
    V2_SHOW_WHEN_OPERATORS,
    V2_STATE_FIELDS,
    V2_VARIABLE_STATE,
    V2ShowWhenChoice,
    V2StateField,
)

if TYPE_CHECKING:
    from maptasker.src.core.primitem import RunState


def _v2_global_choices(state: RunState) -> tuple[list[V2ShowWhenChoice], list[V2ShowWhenChoice]]:
    """(user globals, built-in globals) out of the loaded backup's <Variable> elements.

    Read straight from the XML rather than from PrimeItems.variables, which looks like the
    obvious source and is the wrong one twice over: it is only ever filled by
    globalvr.get_variables() on the Map-output path, so in a GUI session that has not built a
    Map it is simply empty; and what it does hold has been through HTML escaping (spaces to
    &nbsp;, commas to <br>) for the benefit of the Map, which is not what a dialog should
    show.

    The two categories come from different places, and have to.

    User globals are the same set globalvr.print_the_variables treats as the user's: every
    <Variable> in the backup whose name Tasker does not own.  It is read here straight off
    the XML rather than out of PrimeItems.variables, which is the dict that function walks
    and would be the obvious thing to reuse, for two reasons: PrimeItems.variables is only
    ever filled by globalvr.get_variables() on the Map-output path, so in a GUI session that
    has not built a Map it is simply empty; and the values it holds have been HTML-escaped
    for the Map (spaces to &nbsp;, commas to <br>).  The names are identical either way,
    which is all this needs -- the name is both the label and what gets inserted.

    Built-ins are Tasker's own fixed set, and NOT the built-in-looking names found in the
    file: Tasker only writes a <Variable> for a value it has actually stored, so sourcing
    them from the backup yields an *empty* category on a real backup while %BATT and %WIFI
    are perfectly usable in a Show When.  Each is offered under its documented name --
    "Airplane Mode Status", not "%AIR", which is not something anyone browses a hundred-item
    list by -- from taskervars.tasker_global_variable_names, falling back to the variable
    itself for the handful that table has no name for.  Either way what gets inserted is the
    variable.  The set is the union of that table and globalvr's list, since each holds a few
    the other doesn't (see the note above tasker_global_variable_names).

    Both lists come back sorted by what the picker shows, ignoring case and any leading %,
    because Tasker's own ordering in the file is the order they were created in and means
    nothing to someone looking for one by name.
    """

    builtin_names = set(tasker_global_variables) | set(tasker_global_variable_names)
    stored_names = (
        [variable.findtext("n") for variable in state.xml_root.findall("Variable")]
        if state.xml_root is not None
        else []
    )

    user = [V2ShowWhenChoice(name, name) for name in dict.fromkeys(stored_names) if name and name not in builtin_names]
    builtin = [V2ShowWhenChoice(tasker_global_variable_names.get(name, name), name) for name in builtin_names]

    def sort_key(choice: V2ShowWhenChoice) -> str:
        return choice.label.lstrip("%").lower()

    user.sort(key=sort_key)
    builtin.sort(key=sort_key)
    return user, builtin


def v2_show_when_choices(state: RunState) -> list[tuple[str, list[V2ShowWhenChoice]]]:
    """The whole Show When picker, as (category, choices) in V2_SHOW_WHEN_GROUPS order.

    A category with nothing in it is still returned, empty -- a backup with no variables of
    its own should say "User Globals: none" rather than silently offering two categories
    where the user was told there are three.
    """
    user, builtin = _v2_global_choices(state=state)
    return [
        ("Environment", list(V2_SHOW_WHEN_ENVIRONMENT)),
        ("Operators", list(V2_SHOW_WHEN_OPERATORS)),
        ("Logical Operators", list(V2_SHOW_WHEN_LOGICAL_OPERATORS)),
        ("User Globals", user),
        ("Built-in Globals", builtin),
    ]


def v2_insert_show_when(current: str, value: str, caret: int | None = None) -> tuple[str, int]:
    """Put one variable or operator into a Show When expression at `caret`, and hand back
    (new text, where the caret should now be).

    Inserts rather than replaces, because a Show When is an expression built a piece at a
    time -- "%sv2_render_is_portrait" is a complete condition on its own, but
    "%BATT < 20" is a variable, an operator and something typed, in that order.

    caret is where the user last had the cursor in the field; None, or a position that no
    longer fits the text, means the end.  The end is also the right answer for the common
    case of never having clicked into the field at all, where the caret sits at 0 and
    inserting there would build the expression backwards.

    Single spaces are added around the inserted text where its neighbours don't already
    provide them, so picking a variable and then an operator gives "%BATT <" rather than
    "%BATT<" -- and the returned caret sits *after* that trailing space, ready for whatever
    comes next.
    """
    position = len(current) if caret is None or not 0 <= caret <= len(current) else caret
    before, after = current[:position], current[position:]
    lead = "" if not before or before[-1].isspace() else " "
    trail = "" if not after or after[0].isspace() else " "
    inserted = f"{lead}{value}{trail}"
    return f"{before}{inserted}{after}", position + len(inserted)


def v2_dynamic_variable_choices(state: RunState) -> list[tuple[str, list[V2ShowWhenChoice]]]:
    """The variables offered for a Dynamic state field, as (category, choices).

    The same three categories of variable the Show When picker lists -- Environment, User
    Globals, Built-in Globals -- because these fields can be driven by a variable in exactly
    the way a Show When can.  What they do not borrow from that picker are its Operators and
    Logical Operators: those build a comparison out of two values, and these fields hold one.

    Empty categories are returned empty, for the reason v2_show_when_choices gives.
    """
    user, builtin = _v2_global_choices(state=state)
    return [
        ("Environment", list(V2_SHOW_WHEN_ENVIRONMENT)),
        ("User Globals", user),
        ("Built-in Globals", builtin),
    ]


def v2_state_field(key: str) -> V2StateField | None:
    """The state field this property key belongs to, or None for a key that isn't one."""
    return next((field for field in V2_STATE_FIELDS if field.key == key), None)


def v2_is_variable(text: str) -> bool:
    """Whether this is one variable and nothing else -- "%BATT", not "%BATT > 20" and not
    "<b>%name</b>".

    The whole test is a leading % and no whitespace, which is what tells a value the Select
    Variable state produced from one someone typed under Dynamic.  It is deliberately a shape
    test rather than a lookup in the picker's own lists: a Scene can perfectly well be driven
    by a local variable, or one a Task creates at run time, and neither appears in any list
    this app can build.
    """
    stripped = text.strip()
    return stripped.startswith("%") and len(stripped) > 1 and not any(c.isspace() for c in stripped)


def v2_state_of(field: V2StateField, value: object) -> str:
    """Which state a stored value reads as -- or "" for a component that carries no such
    property at all, which is not the same as one set to its "off" state.

    A settling state is matched ignoring case *and* spaces, and a real JSON boolean is read as
    the "true"/"false" it prints as.  So a Scene from a newer Tasker spelling Enabled as true
    rather than "true" still lands on On, and one spelling a weight "ExtraLight" where this
    app spells it "Extra Light" still lands on that weight rather than falling through to
    Dynamic.  Nothing is lost by being that loose: no two states in any of these tables differ
    only by case or a space.

    What is left is one of the two open states, told apart by v2_is_variable: a bare %variable
    reads as Select Variable, anything else as Dynamic.  The point of the distinction is that
    the field reopens on the control that could have produced what is stored -- a picked
    variable in the variable box, typed text in the text box.
    """
    text = str(value).strip()
    if not text:
        return ""

    def loose(word: str) -> str:
        return "".join(word.split()).lower()

    settled = next((state for state, stored in field.fixed if loose(text) == loose(stored)), "")
    if settled:
        return settled
    return V2_VARIABLE_STATE if v2_is_variable(text) else V2_DYNAMIC_STATE


def v2_state_value(field: V2StateField, value: object, state: str = "") -> str:
    """What an open state is carrying -- the typed text, or the picked variable -- and "" for
    any settling state, so that the box starts empty rather than showing "true" for a
    component the user has only just switched over.

    `state` asks for the value of one particular open state, which is how the two boxes are
    filled from the one stored property: the one that state produced gets it, the other starts
    empty rather than both opening with the same text.
    """
    current = v2_state_of(field, value)
    if current not in (V2_DYNAMIC_STATE, V2_VARIABLE_STATE):
        return ""
    return str(value).strip() if state in ("", current) else ""
