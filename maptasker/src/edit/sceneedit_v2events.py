"""sceneedit_v2events: a component's modifiers, event handlers, actions and variable bindings.

The schemas for each, and adding, deleting and moving them on a node."""

from __future__ import annotations

from maptasker.src.edit.sceneedit_v2 import V2_STATE_FIELDS, V2Prop

# --------------------------------------------------------------------------------------
# Version 2 designer, phase 3: the three things hanging off a component that phases 1 and 2
# carried through untouched -- its modifiers, its event handlers, and its output bindings.
#
# Between them these are what make a Scene do something rather than just look like something:
# modifiers decide how a component sizes and sits (there is no geometry anywhere else),
# handlers decide what happens when it is touched, and bindings are how the values a user
# typed or dragged get back out to Tasker variables.
#
# Same in-place discipline as phases 1 and 2 -- lists are mutated, never rebuilt, so a
# component nobody touched still re-encodes to its original bytes.
# --------------------------------------------------------------------------------------

# What any modifier can carry, whatever its type: the condition deciding whether it applies at
# all.  Universal rather than declared per type because the Scenes in XML/ carry it on six
# unrelated modifiers -- Size, Padding, Alpha, Background, Rotate and VerticalScroll -- which
# says it belongs to modifiers in general rather than to any of them in particular.
#
# An expression in the same language a component's showWhen is written in ("%floatbutton ==
# \"Add\"", "%description_toggle"), which is why it is offered as a field to write in rather
# than a pulldown of anything.  "textvar" so that field also carries the Select Variable
# picker: the expression is built out of variables nobody remembers the spelling of, and a
# misspelt one doesn't fail, it just quietly never applies the modifier.  Every modifier on
# every component is offered this property (v2_schema_props appends the universal ones for all
# of them), so the picker is there wherever an Apply when is.
V2_MODIFIER_UNIVERSAL_PROPS: tuple[V2Prop, ...] = (V2Prop("applyWhen", "Apply when", "textvar"),)


# Modifier types and what each takes.  Order within a node's "modifiers" list is
# significant -- they compose in sequence, so Padding-then-Border draws a different thing
# from Border-then-Padding, which is why the editor offers move up/down rather than sorting.
#
# Read off the Version 2 Scenes in XML/ rather than from any published schema (there is none):
# every key below appears in a real Scene, at the spelling written here.  A type or key that
# does not appear is not invented -- see the "no properties observed" group at the end, and
# _v2_unschemad's fallback, which still shows anything a newer Tasker writes.
V2_MODIFIER_SCHEMA: dict[str, tuple[V2Prop, ...]] = {
    # "fraction" is how much of the available space to fill: 0.83, 0.9, 1.  Absent means all
    # of it, which is why most of the 58 FillWidths in the samples carry nothing at all.
    "FillWidth": (V2Prop("fraction", "Fraction", "number"),),
    "FillSize": (V2Prop("fraction", "Fraction", "number"),),
    # INFERRED, and the only inferred entry here: no FillHeight in any sample carries a
    # fraction, but its two siblings above both do, and a "fill the height" that could not be
    # told to fill half of it would be the odd one of the three.
    "FillHeight": (V2Prop("fraction", "Fraction", "number"),),
    "WindowDrag": (),
    # "all" -- one number for both sides -- is the commonest form of this modifier by some way
    # (47 of the samples' Sizes), and was missing here while width/height were not.
    "Size": (
        V2Prop("all", "All", "number"),
        V2Prop("width", "Width", "number"),
        V2Prop("height", "Height", "number"),
    ),
    "SizeIn": (
        V2Prop("minWidth", "Min width", "number"),
        V2Prop("minHeight", "Min height", "number"),
        V2Prop("maxWidth", "Max width", "number"),
        V2Prop("maxHeight", "Max height", "number"),
    ),
    "Padding": (
        V2Prop("all", "All", "number"),
        V2Prop("horizontal", "Horizontal", "number"),
        V2Prop("vertical", "Vertical", "number"),
        V2Prop("start", "Start", "number"),
        V2Prop("end", "End", "number"),
        V2Prop("top", "Top", "number"),
        V2Prop("bottom", "Bottom", "number"),
    ),
    "Offset": (V2Prop("x", "X", "number"), V2Prop("y", "Y", "number")),
    "Clip": (V2Prop("shape", "Shape", "choice", ("Rounded", "Circle")), V2Prop("radius", "Radius", "number")),
    "Border": (
        V2Prop("color", "Colour", "color"),
        V2Prop("shape", "Shape", "choice", ("Rounded", "Circle")),
        V2Prop("radius", "Radius", "number"),
        V2Prop("width", "Width", "number"),
    ),
    "Shadow": (
        V2Prop("elevation", "Elevation", "number"),
        V2Prop("shape", "Shape", "choice", ("Rounded", "Circle")),
        V2Prop("radius", "Radius", "number"),
    ),
    "Background": (V2Prop("color", "Colour", "color"),),
    "Align": (V2Prop("alignment", "Alignment", "choice", ("Start", "Center", "End")),),
    # The one modifier whose value is a state field rather than a plain property: a weight is
    # picked off Compose's scale (V2_FONT_WEIGHTS), or worked out when the Scene is shown.
    "Weight": (next(field for field in V2_STATE_FIELDS if field.key == "amount").prop,),
    "AspectRatio": (V2Prop("ratio", "Ratio"),),
    "Alpha": (V2Prop("value", "Opacity", "number"),),
    # A fraction rather than a size: the samples' Scales are 0.7, 0.8, 0.9.  Only "all" is
    # ever written in them, so only "all" is offered -- Compose scales each axis separately
    # and Tasker may well too, but under a spelling that is not in evidence here.
    "Scale": (V2Prop("all", "All", "number"),),
    "Rotate": (V2Prop("degrees", "Degrees", "number"),),
    "VerticalScroll": (),
    "HorizontalScroll": (),
    # Listed so they can be added and are named as themselves, with no properties because none
    # of them carries one in any sample.  Blur especially will have something to set (a radius,
    # if it follows Compose) -- but what Tasker calls it is not in evidence here, and a guessed
    # key writes a property Tasker would ignore.  Anything they do carry still shows through
    # the unschema'd fallback in v2_schema_props.
    "Blur": (),
    # Clickable's one key, "actions", is a nested {"click:2": {"task": ...}} rather than a
    # scalar, so it is not offered as a field at all -- it is carried through untouched, and
    # the Task it names is edited where Tasks are edited.
    "Clickable": (),
}


# Events a handler can fire on.  screen_variable_changed carries a variableName; the rest
# take no arguments of their own.
V2_EVENT_TYPES = ("click", "hold", "text_changed", "screen_variable_changed")


V2_EVENT_SCHEMA: dict[str, tuple[V2Prop, ...]] = {
    "screen_variable_changed": (V2Prop("variableName", "Variable"),),
}


# What a handler can do.  RunTask's "task" is a Task *name*, which is why the dialog offers
# a picker over the loaded backup's Tasks rather than a free text field.
V2_ACTION_SCHEMA: dict[str, tuple[V2Prop, ...]] = {
    "SetVariable": (V2Prop("variable", "Variable"), V2Prop("value", "Value")),
    "ToggleVariable": (V2Prop("variable", "Variable"),),
    "RunTask": (V2Prop("task", "Task", "task"),),
    "DismissLayout": (V2Prop("result", "Result"),),
    "OutputToVariable": (),
}


V2_ACTION_TYPES = tuple(V2_ACTION_SCHEMA)


# Which components write a value back out, and under what key.  The state object is always
# {"<state>": {"outputVariableBindings": {"<key>": [variable, ...]}}} -- confirmed in the
# 'Dialog' Scene (a TextInput carrying an empty textState) and in every build*() of the
# dialog-builder Project's compiler.
#
# NOTE the compiler is inconsistent about the "%" prefix inside those lists: it writes
# textState as ["%" + var] but sliderValueState as [var]. Both evidently work, so the
# editor shows the stored string as-is and does not normalise either way -- guessing wrong
# would silently repoint a working Scene's output at a different variable.
V2_STATE_BY_TYPE: dict[str, tuple[str, str]] = {
    "TextInput": ("textState", "text"),
    "Slider": ("sliderValueState", "value"),
    "Dropdown": ("selectionState", "selected_indices"),
    "SegmentedButtonRow": ("selectionState", "selected_indices"),
    "Switch": ("selectionState", "selected_indices"),
    "Checkbox": ("selectionState", "selected_indices"),
}


_V2_BINDINGS_KEY = "outputVariableBindings"


def v2_schema_props(
    schema: dict[str, tuple[V2Prop, ...]],
    item: dict,
    universal: tuple[V2Prop, ...] = (),
) -> list[V2Prop]:
    """The editable properties of a modifier / event / action, from its schema, then any
    `universal` property its kind carries whatever its type, then any other scalar key it
    happens to hold.  The same forward-compatible shape v2_editable_props uses for components,
    and for the same reason: these tables are read off one backup, so anything newer must
    still be visible and editable rather than silently dropped.

    A universal property already named by the type's own schema is not offered twice.
    """
    props = list(schema.get(item.get("type", ""), ()))
    declared = {prop.key for prop in props}
    props += [prop for prop in universal if prop.key not in declared]
    known = {prop.key for prop in props}
    for key, value in item.items():
        if key != "type" and key not in known and isinstance(value, (str, int, float, bool)):
            props.append(V2Prop(key, key))
    return props


def v2_modifiers(node: dict) -> list[dict]:
    """This component's modifier list -- always a real list, so callers can index it."""
    modifiers = node.get("modifiers")
    return modifiers if isinstance(modifiers, list) else []


def v2_add_modifier(node: dict, modifier_type: str) -> int:
    """Append a modifier and return its index.  Appends rather than inserts because a
    modifier's position is its place in the composition order, and the end is the only
    position that means "on top of what is already there".
    """
    modifiers = node.setdefault("modifiers", [])
    modifiers.append({"type": modifier_type})
    return len(modifiers) - 1


def v2_delete_modifier(node: dict, index: int) -> None:
    """Remove a modifier, and the whole "modifiers" key with it when the last one goes --
    Tasker writes no empty modifiers list on any component in this repo's backup, and an
    empty one is a difference from what it would have written.
    """
    modifiers = v2_modifiers(node)
    if 0 <= index < len(modifiers):
        del modifiers[index]
    if not modifiers and "modifiers" in node:
        del node["modifiers"]


def v2_move_modifier(node: dict, index: int, offset: int) -> int | None:
    """Reorder a modifier; returns its new index, or None if it can't move that way."""
    modifiers = v2_modifiers(node)
    new_index = index + offset
    if not (0 <= index < len(modifiers) and 0 <= new_index < len(modifiers)):
        return None
    modifiers.insert(new_index, modifiers.pop(index))
    return new_index


def v2_handlers(node: dict) -> list[dict]:
    """This component's event handlers -- always a real list."""
    handlers = (node.get("eventHandlers") or {}).get("handlers")
    return handlers if isinstance(handlers, list) else []


def v2_add_handler(node: dict, event_type: str) -> int:
    """Add an event handler firing on one event, with no actions yet, and return its index.

    A handler with no actions is legal and is the only sensible starting point -- the user
    picks the event first, then says what it should do.
    """
    event_handlers = node.setdefault("eventHandlers", {})
    handlers = event_handlers.setdefault("handlers", [])
    handlers.append({"events": [{"type": event_type}], "actions": []})
    return len(handlers) - 1


def v2_delete_handler(node: dict, index: int) -> None:
    """Remove an event handler, and the whole "eventHandlers" object with it when the last
    one goes -- same reasoning as v2_delete_modifier.  A stopPropagation flag set alongside
    the handlers goes with them, since it only means anything in their company.
    """
    handlers = v2_handlers(node)
    if 0 <= index < len(handlers):
        del handlers[index]
    if not handlers and "eventHandlers" in node:
        del node["eventHandlers"]


def v2_add_action(handler: dict, action_type: str) -> int:
    """Append an action to a handler and return its index.  Order matters: the actions of
    a handler run in sequence, which is how the 'Dialog' Scene's close button sets two
    variables *before* dismissing the layout.
    """
    actions = handler.setdefault("actions", [])
    actions.append({"type": action_type})
    return len(actions) - 1


def v2_delete_action(handler: dict, index: int) -> None:
    """Remove one action from a handler, leaving the handler in place even if empty."""
    actions = handler.get("actions")
    if isinstance(actions, list) and 0 <= index < len(actions):
        del actions[index]


def v2_move_action(handler: dict, index: int, offset: int) -> int | None:
    """Reorder an action within its handler; returns the new index or None."""
    actions = handler.get("actions")
    if not isinstance(actions, list):
        return None
    new_index = index + offset
    if not (0 <= index < len(actions) and 0 <= new_index < len(actions)):
        return None
    actions.insert(new_index, actions.pop(index))
    return new_index


def v2_binding_slot(node: dict) -> tuple[str, str] | None:
    """The (state key, binding key) this component writes its value out through, or None
    if it has no output.

    Falls back to whatever <x>State the node already carries when its type isn't in
    V2_STATE_BY_TYPE, so a binding written by a newer Tasker on a component this app
    doesn't know is still shown and editable rather than hidden.
    """
    known = V2_STATE_BY_TYPE.get(node.get("type", ""))
    if known:
        return known
    for key, value in node.items():
        if key.endswith("State") and isinstance(value, dict) and _V2_BINDINGS_KEY in value:
            bindings = value[_V2_BINDINGS_KEY]
            if isinstance(bindings, dict) and bindings:
                return key, next(iter(bindings))
    return None


def v2_get_binding(node: dict, slot: tuple[str, str]) -> str:
    """The variable this component currently writes to, as a comma-separated string.

    The stored form is a list -- Tasker allows more than one target -- but one is the
    normal case, so the editor is a single field and the list is joined for display.
    """
    state_key, binding_key = slot
    bindings = (node.get(state_key) or {}).get(_V2_BINDINGS_KEY, {})
    values = bindings.get(binding_key) if isinstance(bindings, dict) else None
    if isinstance(values, list):
        return ", ".join(str(value) for value in values)
    return "" if values is None else str(values)


def v2_set_binding(node: dict, slot: tuple[str, str], text: str) -> None:
    """Point this component's output at one or more variables, creating the state object
    if it isn't there.

    Clearing the field leaves an *empty list* rather than deleting the state object,
    because that is exactly what a real Scene contains: the 'Dialog' Scene's filter_bar
    carries "textState": {"outputVariableBindings": {"text": []}} -- the binding declared
    but unset.  Deleting the object instead would be a different document from the one
    Tasker wrote.
    """
    state_key, binding_key = slot
    state = node.setdefault(state_key, {})
    if not isinstance(state, dict):
        state = node[state_key] = {}
    bindings = state.setdefault(_V2_BINDINGS_KEY, {})
    if not isinstance(bindings, dict):
        bindings = state[_V2_BINDINGS_KEY] = {}
    bindings[binding_key] = [part.strip() for part in text.split(",") if part.strip()]
