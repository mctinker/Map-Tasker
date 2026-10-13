"""mapswap_sites: reading and writing the one place a Change points at -- an argument, a Scene binding, a declaration."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from maptasker.src.core.mapjump import VARIABLE, Target, current_scope
from maptasker.src.edit import scenemodel, taskedit_addable
from maptasker.src.mapops.mapswap_model import (
    BUNDLE,
    CONDITION,
    DECLARATION,
    IMPORT_VARIABLE,
    INT_VALUE,
    INT_VAR,
    LEGACY_SCENE,
    NEW_ARG,
    STR_ARG,
    V2_SCENE,
    Site,
    effective_args,
    order_action_children,
)

if TYPE_CHECKING:
    import re
    from xml.etree.ElementTree import Element

    from maptasker.src.core.primitem import RunState
    from maptasker.src.mapgen import varxref


def is_plugin_declaration(element: Element) -> bool:
    """Whether this Bundle entry is a plugin declaring its OUTPUT variables.

    A plugin lists what it produces in a RELEVANT_VARIABLES entry, which varxref reads to
    work out what sets %http_data and its like.  It is metadata about the plugin, not a
    use of the user's variable, and 4313 of them sit in one real backup -- rewriting them
    would edit the plugin's description of itself while changing nothing about what it
    actually sets.
    """
    return element.tag.endswith("RELEVANT_VARIABLES")


def site_kind(reference: varxref.Reference) -> str:
    """Which sort of field a reference sits in -- for the preview's wording, and for the
    one case (write_site) where the rewrite genuinely differs.
    """
    if reference.path or reference.element is None:
        return V2_SCENE
    if reference.element.tag in ("lhs", "rhs"):
        return CONDITION
    if reference.element.tag == "var":
        return INT_VAR
    # A Project's or Profile's own declaration of a variable to configure on import: the
    # name in <pvn>, the value offered for it in <pvv>.  Named rather than left to fall
    # through to BUNDLE below: the preview prints the kind, and "bundle" would tell the
    # user this rename is touching a plugin's payload when it is touching the Project's
    # properties.
    if reference.element.tag in ("pvn", "pvv"):
        return IMPORT_VARIABLE
    if reference.element.tag == "Str":
        return LEGACY_SCENE if "component" in reference.detail or "value" in reference.detail else STR_ARG
    return BUNDLE


def declaration_site(old_name: str, entries: list[varxref.Variable], rename: tuple, state: RunState) -> Site | None:
    """The top-level <Variable> that declares this name, if the file carries one.

    Why a rename cannot be done by walking Tasks alone: Tasker's Variables tab holds the
    declaration and its value, and leaving it behind orphans the value under a name
    nothing uses any more.
    """
    if not any(entry.declared for entry in entries) or state.xml_root is None:
        return None

    # Only when the whole configuration is in play.  A <Variable> is a file-level object,
    # not part of any Project/Profile/Task/Scene, so it is not inside the one object a
    # scoped run was told to touch -- and renaming it from inside a single Task would
    # rename Tasker's Variables tab entry out from under every OTHER Task still using the
    # old name.  A scoped rename is partial by the user's own choice; this keeps it
    # partial in the safe direction.
    if not current_scope(state=state).is_everything:
        return None
    for element in state.xml_root.findall("Variable"):
        children = list(element)
        if children and (children[0].text or "").strip() == old_name:
            return Site(
                kind=DECLARATION,
                element=children[0],
                where=Target(kind=VARIABLE, key=old_name, name=old_name),
                detail="Tasker's Variables tab",
                rename=rename,
            )
    return None


def current_value(site: Site) -> str:
    """What this field holds now, whichever shape it holds it in.

    The odd one out is INT_VALUE: Tasker writes a plain numeric argument as an ATTRIBUTE
    (<Int sr="arg1" val="7"/>) and everything else in this module as element text, so a
    single .text read would report every numeric argument as empty and then replace an
    empty string with the new value -- which would look right in the preview and write
    nothing anybody could see.
    """
    if site.kind == NEW_ARG:
        # Nothing holds it yet.  Read off site.element and this would be the <Action>'s own
        # text -- the whitespace before its first child -- shown to the user as the value
        # they are about to replace.
        return ""
    if site.kind == INT_VALUE:
        return site.element.attrib.get("val", "")
    return site.element.text or ""


def _set_value(site: Site, value: str, state: RunState) -> None:
    """Put a value into this field, in the shape the field keeps it in.  The write half of
    current_value, and the reason the two sit together."""
    if site.kind == NEW_ARG:
        _create_argument(site, value, state=state)
        return
    if site.kind == INT_VALUE:
        site.element.set("val", value)
        return
    site.element.text = value


def _create_argument(site: Site, value: str, state: RunState) -> None:
    """Write an argument the action has never carried, and put the value in it.

    Built through taskedit_addable.build_synthesized_args -- the same function Add Action uses, and
    the same one swap_one_action synthesizes a whole argument set with -- so an argument
    added here is indistinguishable from one Tasker itself wrote: <Str sr="argN" ve="3"> for
    text, <Int sr="argN" val="0"/> for a number or a checkbox.  A second definition of "what
    an empty argument looks like" is exactly the thing that goes stale.

    No action key is passed, which is deliberate: given one, that function also writes the
    plugin payload <Bundle> for the action, and this is adding one argument to an action
    that already has whatever payload it came with.

    Raises rather than returning quietly if nothing was built -- apply() catches it and
    reports that one change, which is the right outcome for an argument that turns out not
    to be synthesizable after the preview said it was.
    """
    action_key, arg_id = site.create_arg
    argument = next((entry for entry in effective_args(action_key) if entry.arg_id == arg_id), None)
    if argument is None:
        unbuildable = f"{action_key} has no argument {arg_id} to add"
        raise ValueError(unbuildable)

    built = taskedit_addable.build_synthesized_args(type(site.element), site.element, [argument], state=state)
    if not built or built[0].element is None:
        unbuildable = f"an argument of this kind cannot be written from nothing ({site.detail})"
        raise ValueError(unbuildable)

    element = built[0].element
    if element.tag == "Int":
        element.set("val", value)
    else:
        element.text = value
    # In the order Tasker writes them, rather than appended at the end.  See order_action_children.
    order_action_children(site.element)


def rewrite_site(site: Site, pattern: re.Pattern | None = None, new_name: str = "") -> tuple[str, str]:
    """(before, after) for one site, without writing anything.  The read half of apply().

    Per-kind, because a value does not live in the same place twice:
      STR_ARG        element.text
      INT_VAR        element.find('var').text
      CONDITION      the <lhs>/<rhs> child named in site.detail
      BUNDLE         element.text, anywhere under the <Bundle>
      LEGACY_SCENE   the <Str sr="argN"> named in site.detail
      V2_SCENE       site.path into the parsed JSON layout, re-serialized on write
      DECLARATION    the <Variable>'s name child
      IMPORT_VARIABLE the <pvn> element's own text
      INT_VALUE      the <Int>'s val= attribute

    A Version 2 Scene is the one that is not a string swap: the layout is gzipped JSON, so
    the value has to be decoded, changed at site.path and re-encoded.  Not batched per
    Scene -- each site decodes the layout as it now stands, so two changes to one Scene
    compose correctly; it costs a decode and an encode each, on the handful of V2 Scenes a
    configuration has.
    """
    if site.kind == V2_SCENE:
        value = scenemodel.V2.property_value(site.element, site.path)
        return _flatten(value), _flatten(_substitute(value, pattern, new_name))

    before = current_value(site)
    # A whole value replaced, rather than something matched inside it.  Checked first
    # because such a Site carries no pattern at all: what it is going to hold does not
    # depend on what it holds now.
    if site.new_value is not None:
        return before, site.new_value
    if pattern is None:
        msg = "A Site needs either a new value or a pattern to replace with it."
        raise ValueError(msg)
    return before, pattern.sub(new_name, before)


def _substitute(value: object, pattern: re.Pattern, new_name: str) -> object:
    """The value with every whole-name match rewritten, at whatever depth it sits.

    Recursive because a V2 property is not always a string: a component's value can be a
    dict or a list of them, which is why mapjump.v2_strings has to recurse to FIND the
    names.  Anything that is not a string, dict or list is returned as it stands -- a
    number or a boolean cannot hold a variable name.
    """
    if isinstance(value, str):
        return pattern.sub(new_name, value)
    if isinstance(value, dict):
        return {key: _substitute(item, pattern, new_name) for key, item in value.items()}
    if isinstance(value, list):
        return [_substitute(item, pattern, new_name) for item in value]
    return value


def _flatten(value: object) -> str:
    """One line of preview text for a value that may not be a string."""
    if isinstance(value, str):
        return value
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def write_site(site: Site, state: RunState) -> None:
    """Rewrite one field in place -- the write half of rewrite_site.

    Takes no value: the Site carries the pattern and the new name, so what gets written is
    computed here from what the field holds NOW rather than from what it held when the
    plan was built.  That is what makes two renames touching one field compose, and what
    stops a stale preview value being written over a field somebody edited meanwhile.
    """
    if site.new_value is not None:
        _set_value(site, site.new_value, state=state)
        return

    pattern, new_name = site.rename

    if site.kind == V2_SCENE:
        # Decoded fresh by the model every time: the layout a plan was built from is long gone
        # by the time anything is applied, and what is on disk is the <lj> of the element.
        if not scenemodel.V2.rewrite_property(
            site.element, site.path, lambda value: _substitute(value, pattern, new_name)
        ):
            # A layout that will not decode, or a path that no longer resolves.  Left alone
            # rather than rebuilt: a layout that cannot be read certainly should not be
            # re-encoded over the original.
            unreachable = f"the Version 2 layout of {site.where.label} could not be read"
            raise ValueError(unreachable)
        return

    _set_value(site, pattern.sub(new_name, current_value(site)), state=state)
