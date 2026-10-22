"""sceneview_v2style: a Version 2 component's modifiers, as CSS.

Padding, size, shape, border, shadow, offset, rotate and scale, and the lines of tooltip that name the event
handlers, actions and bindings a component carries."""

from __future__ import annotations

from maptasker.src.core.sysconst import V2_MATERIAL_PALETTE
from maptasker.src.gui.sceneview import VARIABLE_FILL
from maptasker.src.gui.sceneview_v2base import V2_ALIGNMENT, v2_colour


# ------------------------------------------------------------------
# Modifiers
# ------------------------------------------------------------------
def v2_modifier_style(node: dict) -> str:
    """The CSS a component's modifier chain amounts to.

    Compose applies modifiers in order and each wraps the last, so strictly they are nested
    boxes; this merges them into one box's style instead, later modifiers overriding earlier
    ones for the same property.  The two agree for everything real Scenes do -- padding
    inside a border, a background behind both -- and disagree only for orders CSS has no box
    for (a padding outside a border, two paddings in a row).  That trade buys a component
    being one element rather than a stack of six, which is what keeps flex alignment,
    scrolling and the bounds outline all landing on the thing the user selected.

    Every modifier's keys are read defensively.  Size is the reason: sceneedit's schema lists
    width/height, and the Scenes in this repo carry "all".  Both work here.

    The transforming modifiers (Offset, Rotate, Scale) are gathered rather than concatenated,
    for the reason given at _V2_MODIFIER_TRANSFORM, and land after everything else -- a
    transform is applied to the box the rest of the chain has already decided on.
    """
    modifiers = node.get("modifiers")
    if not isinstance(modifiers, list):
        return ""

    style = ""
    transforms = []
    for modifier in modifiers:
        if not isinstance(modifier, dict):
            continue
        modifier_type = str(modifier.get("type", ""))
        style += _V2_MODIFIER_CSS.get(modifier_type, lambda _m: "")(modifier)
        transform = _V2_MODIFIER_TRANSFORM.get(modifier_type, lambda _m: "")(modifier)
        if transform:
            transforms.append(transform)
    if transforms:
        style += f"transform: {' '.join(transforms)};"
    return style


def v2_number(source: dict, *keys: str) -> str:
    """The first of these keys the dict actually carries, as a CSS px length.  "" when none
    of them are there or the value is a %variable, which a length cannot be.

    Used for both modifiers and components -- a Padding's "all" and a Spacer's "height" are
    the same kind of value stored the same way (as a string, see sceneedit_v2props._coerce_like).
    """
    for key in keys:
        value = str(source.get(key, "")).strip()
        if value and not value.startswith("%"):
            try:
                return f"{float(value):g}px"
            except ValueError:
                continue
    return ""


def _v2_padding(modifier: dict) -> str:
    """Padding: all / horizontal / vertical / start / end / top / bottom, applied from the
    most general to the most specific so a {horizontal, bottom} pair composes the way Compose
    composes it.
    """
    style = ""
    for keys, css in (
        (("all",), "padding"),
        (("horizontal",), "padding-left"),
        (("horizontal",), "padding-right"),
        (("vertical",), "padding-top"),
        (("vertical",), "padding-bottom"),
        (("start",), "padding-left"),
        (("end",), "padding-right"),
        (("top",), "padding-top"),
        (("bottom",), "padding-bottom"),
    ):
        length = v2_number(modifier, *keys)
        if length:
            style += f"{css}: {length};"
    return style


def _v2_shape(modifier: dict) -> str:
    """The corner rounding a Clip or a Border asks for: a Circle is a circle whatever its
    radius says, a Rounded is its radius, and a shape with neither is square.
    """
    if str(modifier.get("shape", "")) == "Circle":
        return "border-radius: 50%;"
    radius = v2_number(modifier, "radius")
    return f"border-radius: {radius};" if radius else ""


def _v2_border(modifier: dict) -> str:
    colour = v2_colour(modifier.get("color"), fallback=V2_MATERIAL_PALETTE["outline"])
    width = v2_number(modifier, "width") or "1px"
    return f"border: {width} solid {colour.css}; box-sizing: border-box;{_v2_shape(modifier)}"


def _v2_background(modifier: dict) -> str:
    colour = v2_colour(modifier.get("color"))
    if colour.is_variable:
        return f"background: {VARIABLE_FILL};"
    return f"background: {colour.css};" if colour.known else ""


def _v2_size(modifier: dict) -> str:
    """Size: an explicit width and height.  "all" is what the Scenes here carry and means
    both; width/height are what the editor's schema offers.  Either is accepted.
    """
    both = v2_number(modifier, "all")
    if both:
        return f"width: {both}; height: {both}; flex: none;"
    style = ""
    width = v2_number(modifier, "width")
    height = v2_number(modifier, "height")
    if width:
        style += f"width: {width};"
    if height:
        style += f"height: {height};"
    return f"{style}flex: none;" if style else ""


def _v2_size_in(modifier: dict) -> str:
    style = ""
    max_width = v2_number(modifier, "maxWidth")
    max_height = v2_number(modifier, "maxHeight")
    if max_width:
        style += f"max-width: {max_width};"
    if max_height:
        style += f"max-height: {max_height};"
    return style


def _v2_alpha(modifier: dict) -> str:
    value = str(modifier.get("value", "")).strip()
    try:
        return f"opacity: {max(0.0, min(1.0, float(value)))};"
    except ValueError:
        return ""


# The weights a Weight modifier is set from (sceneedit_v2.V2_FONT_WEIGHTS), as the numbers CSS
# knows them by.  Keyed without spaces or case so "ExtraLight", "Extra Light" and "extra
# light" all arrive at the same weight -- the same looseness sceneedit_v2state.v2_state_of reads them
# with, and for the same reason: which of the two spellings Tasker writes is not in evidence.
_V2_FONT_WEIGHT_CSS: dict[str, int] = {
    "thin": 100,
    "extralight": 200,
    "light": 300,
    "normal": 400,
    "medium": 500,
    "semibold": 600,
    "bold": 700,
    "extrabold": 800,
    "black": 900,
}


# What a Blur is drawn as when it says nothing about how much.  No Blur in any sample carries
# a radius and Tasker's name for one is not in evidence (see sceneedit's schema note), so this
# is a stand-in: enough to show that the component is blurred, not a claim about how much.
_V2_DEFAULT_BLUR = "4px"


def _v2_weight(modifier: dict) -> str:
    """Weight: how heavy the text is drawn.

    A named weight off Compose's scale, or a plain 100-900 that CSS would take as one.  A
    %variable, or a leftover number from when this modifier was read as a layout weight, is
    not a font weight and draws nothing -- the modifier is still named in the tooltip.
    """
    amount = str(modifier.get("amount", "")).strip()
    named = _V2_FONT_WEIGHT_CSS.get("".join(amount.split()).lower())
    if named:
        return f"font-weight: {named};"
    try:
        numeric = int(float(amount))
    except ValueError:
        return ""
    return f"font-weight: {numeric};" if 100 <= numeric <= 900 else ""


def _v2_fraction(modifier: dict) -> str:
    """How much of the available space a Fill* modifier takes, as a CSS percentage.  Absent
    means all of it, which is how most of the samples' Fills are written.
    """
    value = str(modifier.get("fraction", "")).strip()
    try:
        return f"{max(0.0, min(1.0, float(value))) * 100:g}%"
    except ValueError:
        return "100%"


def _v2_shadow(modifier: dict) -> str:
    """Shadow: elevation as the distance the component is lifted off what is behind it.

    Compose states an elevation in dp and works the shadow out from it; CSS wants the offset
    and the blur, so the one number becomes both -- dropped half its elevation, blurred by the
    whole of it, which is the shape of Material's own elevation overlays.  The shape is
    carried too, so a shadow under a rounded card is rounded rather than square.
    """
    elevation = v2_number(modifier, "elevation")
    if not elevation:
        return _v2_shape(modifier)
    depth = float(elevation.removesuffix("px"))
    return f"box-shadow: 0 {depth / 2:g}px {depth:g}px rgba(0,0,0,0.28);{_v2_shape(modifier)}"


def _v2_offset(modifier: dict) -> str:
    """Offset: x and y, either of which can be negative and either of which can be absent."""
    x = v2_number(modifier, "x") or "0px"
    y = v2_number(modifier, "y") or "0px"
    return "" if x == "0px" and y == "0px" else f"translate({x}, {y})"


def _v2_rotate(modifier: dict) -> str:
    degrees = str(modifier.get("degrees", "")).strip()
    try:
        return f"rotate({float(degrees):g}deg)"
    except ValueError:
        return ""


def _v2_scale(modifier: dict) -> str:
    amount = str(modifier.get("all", "")).strip()
    try:
        return f"scale({float(amount):g})"
    except ValueError:
        return ""


# type -> the CSS it contributes.  A modifier absent from here and from
# _V2_MODIFIER_TRANSFORM contributes nothing visually and is reported in the component's
# tooltip instead (see v2_tooltip): WindowDrag is behaviour rather than appearance -- a
# picture cannot show that a window can be dragged -- and an unrecognised one is not going to
# be invented.
_V2_MODIFIER_CSS: dict[str, object] = {
    "FillWidth": lambda m: f"width: {_v2_fraction(m)};",
    "FillHeight": lambda m: f"height: {_v2_fraction(m)};",
    "FillSize": lambda m: f"width: {_v2_fraction(m)}; height: {_v2_fraction(m)};",
    "Size": _v2_size,
    "SizeIn": _v2_size_in,
    "Padding": _v2_padding,
    "Clip": lambda m: f"overflow: hidden;{_v2_shape(m)}",
    "Border": _v2_border,
    "Shadow": _v2_shadow,
    "Background": _v2_background,
    "Align": lambda m: f"align-self: {V2_ALIGNMENT.get(str(m.get('alignment', '')), 'auto')};",
    "Weight": _v2_weight,
    "AspectRatio": lambda m: f"aspect-ratio: {m.get('ratio', '1')};",
    "Alpha": _v2_alpha,
    "Blur": lambda m: f"filter: blur({v2_number(m, 'radius', 'all', 'value') or _V2_DEFAULT_BLUR});",
    "VerticalScroll": lambda _m: "overflow-y: auto;",
    "HorizontalScroll": lambda _m: "overflow-x: auto;",
    "Clickable": lambda _m: "cursor: pointer;",
}


# The three that are all the same CSS property.  Kept apart from the table above because
# `transform` takes a *list* of functions and the styles here are concatenated: written as
# ordinary declarations, a component carrying both a Rotate and a Scale would keep only
# whichever came last.  Gathered instead, and emitted as one transform in modifier order.
_V2_MODIFIER_TRANSFORM: dict[str, object] = {
    "Offset": _v2_offset,
    "Rotate": _v2_rotate,
    "Scale": _v2_scale,
}


def v2_modifier_drawn(modifier_type: str) -> bool:
    """Whether the preview has anything to draw for this modifier -- what the tooltip's
    "(not drawn)" note is the answer to.
    """
    return modifier_type in _V2_MODIFIER_CSS or modifier_type in _V2_MODIFIER_TRANSFORM


# ------------------------------------------------------------------
# Event handlers and variable bindings
# ------------------------------------------------------------------
def v2_handler_lines(node: dict) -> list[str]:
    """ "click, hold -> SetVariable sd_button = Close; DismissLayout" for each handler.

    A V2 component's behaviour is entirely in here -- there is no clickTask child the way a
    Legacy element has -- so a preview that showed only the layout would be hiding the half
    of the Scene that does anything.
    """
    handlers = (node.get("eventHandlers") or {}).get("handlers")
    if not isinstance(handlers, list):
        return []

    lines = []
    for handler in handlers:
        if not isinstance(handler, dict):
            continue
        events = ", ".join(
            str(event.get("type", "?")) + (f" [{event['variableName']}]" if event.get("variableName") else "")
            for event in handler.get("events") or []
            if isinstance(event, dict)
        )
        actions = "; ".join(
            _v2_action_text(action) for action in handler.get("actions") or [] if isinstance(action, dict)
        )
        if events or actions:
            lines.append(f"{events or '?'} → {actions or '(nothing)'}")
    return lines


def _v2_action_text(action: dict) -> str:
    """One action, in the shape sceneedit_v2events.V2_ACTION_SCHEMA says it has.  An action type this
    app has not seen is named anyway, with whatever scalar properties it carries -- better a
    slightly clumsy "DoSomething(x=1)" than silently dropping what the button does.
    """
    kind = str(action.get("type", "?"))
    if kind == "SetVariable":
        return f"SetVariable {action.get('variable', '?')} = {action.get('value', '')}"
    if kind == "ToggleVariable":
        return f"ToggleVariable {action.get('variable', '?')}"
    if kind == "RunTask":
        return f"RunTask '{action.get('task', '?')}'"
    if kind == "DismissLayout":
        result = action.get("result")
        return f"DismissLayout{f' → {result}' if result else ''}"
    if kind == "OutputToVariable":
        bindings = action.get("bindings")
        if isinstance(bindings, dict):
            pairs = ", ".join(f"{key}→{', '.join(str(v) for v in value)}" for key, value in bindings.items())
            return f"OutputToVariable {pairs}"
        return "OutputToVariable"
    extras = ", ".join(
        f"{key}={value}" for key, value in action.items() if key != "type" and not isinstance(value, (dict, list))
    )
    return f"{kind}({extras})" if extras else kind


def v2_binding_lines(node: dict) -> list[str]:
    """The Tasker variables this component writes its value into.

    Held under a per-type state key -- textState for a TextInput, sliderValueState for a
    Slider (sceneedit_v2events.V2_STATE_BY_TYPE) -- but found here by shape rather than by type, so a
    component from a newer Tasker with its own state key still reports its bindings.
    """
    lines = []
    for key, value in node.items():
        if not key.endswith("State") or not isinstance(value, dict):
            continue
        bindings = value.get("outputVariableBindings")
        if not isinstance(bindings, dict):
            continue
        for slot, variables in bindings.items():
            names = (
                ", ".join(str(variable) for variable in variables) if isinstance(variables, list) else str(variables)
            )
            if names:
                lines.append(f"{slot} → {names}")
    return lines
