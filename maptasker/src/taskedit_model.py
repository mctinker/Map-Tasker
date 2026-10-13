"""taskedit_model: what an editable Task is made of -- EditableArg, EditableAction and EditableTask -- and the codes and reasons the editor shares.

Edit Task and Add Task are described in taskedit's header.  Nothing here touches the live tree or the XML; this is the
in-memory model the rest of the editor builds, changes, validates and saves."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

# The purely informational Bundle hint (a list of the variables an action/condition
# sets), as opposed to an opaque third-party plugin payload -- see
# classify_action_addability.
OUTPUT_VARIABLES_ARG_NAME = "Output Variables"


@dataclass
class EditableArg:
    """One editable (or read-only) argument belonging to an Action."""

    arg_id: str
    arg_name: str
    widget_kind: str  # "checkbox" | "dropdown" | "text" | "raw_fallback" | "app_picker" | "icon_picker" | "readonly"
    backing_tag: str  # "Int" | "Str" | "App" | "Img" | ""
    is_var: bool
    element: Element | None
    current_value: str
    dropdown_options: list[str] | None = None
    readonly_note: str = ""


@dataclass
class EditableAction:
    """One Action element and its editable arguments, in execution order."""

    action_element: Element
    act_number: int
    code: str
    action_name: str
    args: list[EditableArg] = field(default_factory=list)


@dataclass
class EditableTask:
    """A deep-copied Task element plus its editable-action model."""

    task_id: str
    task_element: Element
    actions: list[EditableAction] = field(default_factory=list)


# The "If" action (code 37) has no Bundle/Int/Str args of its own -- its condition
# lives in a sibling <ConditionList sr="if"><Condition sr="c0" ve="3"><lhs/><op/>
# <rhs/></Condition></ConditionList>, e.g.:
#   <Action sr="act1" ve="7"><code>37</code>
#     <ConditionList sr="if"><Condition sr="c0" ve="3">
#       <lhs>%awcomm</lhs><op>2</op><rhs>&lt;aid_vol_down&gt;</rhs>
#     </Condition></ConditionList>
#   </Action>
# action.py's evaluate_condition already reads these same 12 op codes purely for
# display; this is the write-side (label <-> code) mapping for the Operator
# dropdown build_if_condition_args/apply_arg_values build and write. Codes 8/9
# ("=(Numeric)"/"!=(Numeric)") are kept distinct from 0/1 -- both display as "="/
# "!=" in action.py's own read-only table, but they're written differently by real
# Tasker (all four appear in real backups), so collapsing them would silently
# change an edited action's meaning.
IF_ACTION_KEY = "37t"
ELSE_ACTION_KEY = "43t"
END_IF_ACTION_KEY = "38t"
IF_ACTION_CODE = IF_ACTION_KEY[:-1]
ELSE_ACTION_CODE = ELSE_ACTION_KEY[:-1]
END_IF_ACTION_CODE = END_IF_ACTION_KEY[:-1]

# The choices build_if_variant_dialog offers when the user picks the "If"
# action, mapped to the arg-less follower actions to insert right after it
# (both Else and End If have args=[] in actionc.py, so add_action_to_task can
# always synthesize them).
PERFORM_TASK_ACTION_CODE = "130"  # "Perform Task" (action_codes["130t"])
PERFORM_TASK_NAME_ARG_ID = "0"  # its "Name" arg

IF_BLOCK_VARIANTS: tuple[str, ...] = ("If", "If, End If", "If, Else, End If")
IF_BLOCK_FOLLOWERS: dict[str, tuple[str, ...]] = {
    "If": (),
    "If, End If": (END_IF_ACTION_KEY,),
    "If, Else, End If": (ELSE_ACTION_KEY, END_IF_ACTION_KEY),
}
IF_CONDITION_OPERATORS: tuple[tuple[str, str], ...] = (
    ("0", "="),
    ("1", "!="),
    ("2", "~ (Matches)"),
    ("3", "!~ (Doesn't Match)"),
    ("4", "~R (Matches Regex)"),
    ("5", "!~R (Doesn't Match Regex)"),
    ("6", "<"),
    ("7", ">"),
    ("8", "= (Numeric)"),
    ("9", "!= (Numeric)"),
    ("12", "Is Set"),
    ("13", "Not Set"),
)
IF_CONDITION_OPERATOR_LABELS = [label for _, label in IF_CONDITION_OPERATORS]
IF_CONDITION_CODE_TO_INDEX = {code: i for i, (code, _label) in enumerate(IF_CONDITION_OPERATORS)}
IF_CONDITION_LABEL_TO_CODE = {label: code for code, label in IF_CONDITION_OPERATORS}
# The two refusals that are not permanent.  Every other reason classify_action_addability
# gives is a statement about the action ("this plugin's payload can't be generated"); these
# two are statements about what is loaded right now, and both have the same way out -- a
# fetch from the device -- which the GUI offers wherever it shows either of these exact
# texts (see guiwins_taskedit._render_inventory_fetch).  The icon one has a way out because an app's
# own icon is a package and a launcher activity, which is precisely what the Application
# fetch brings back: see appinv._merged_with_device_icons, and the module docstring
# there for the two icon kinds no fetch can reach.  Named constants rather than literals so
# that recognising one is an equality check against a definition, not a substring guess.
NO_APPS_REASON = "No Applications were found in the loaded configuration to choose from."
NO_ICONS_REASON = "No icons were found in the loaded configuration to choose from."
# The arg_specs.json categories an <Img> backs.  'Icon' is the one Task actions and Profile
# Events declare; 'Img' is proginit.py's own added spec, used by Scene elements.  Both are
# the same element and the same picker, so both are named wherever one is.
ICON_CATEGORIES = ("Icon", "Img")
