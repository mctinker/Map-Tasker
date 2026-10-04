"""The two kinds of Scene -- Legacy and Version 2 -- behind one interface."""

#! /usr/bin/env python3

#                                                                                      #
# scenemodel: ask a Scene what it holds without knowing which kind it is.                #
#                                                                                      #
# A Scene is one of two things that share a name and little else.  A Legacy Scene is a   #
# list of elements on a pixel canvas, each one XML with its arguments in <Str sr="argN">  #
# children; a Version 2 Scene is one gzipped JSON layout of components and their modifiers #
# and event handlers.  Editing them has nothing in common (restacking and geometry on one  #
# side, component paths and handlers on the other), and that is not what this is for.      #
#                                                                                      #
# What both kinds DO answer is the questions the analyses ask of every Scene:             #
#                                                                                      #
#   text_sites()     every piece of text a Scene holds that may name a %variable -- what   #
#                    varxref records as a read, or, for an input, a read and a write.      #
#   task_bindings()  every Task the Scene runs -- what healthck checks still exists.       #
#                                                                                      #
# Each analysis used to carry two copies of its walk, one per kind, and choose between      #
# them with its own test for the <lj> child.  Now it asks model_of(scene) for the kind's     #
# model and walks the answer, so it never learns which kind it was given, and a third kind     #
# would be one more class here rather than a branch in every analysis.                         #
#                                                                                      #
# The sites are neutral records, not varxref's References or healthck's Referrers: those       #
# belong to the analyses, and this module sits below both.                                      #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
#
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from maptasker.src import sceneedit, sceneedit_legacy, sceneedit_v2
from maptasker.src.editcommon import argument_elements, string_arguments
from maptasker.src.mapjump import (
    scene_component_part,
    scene_element_parts,
    v2_property_holds_a_variable,
    v2_strings,
)
from maptasker.src.sysconst import SCENE_TASK_TYPES

if TYPE_CHECKING:
    from collections.abc import Iterator
    from xml.etree.ElementTree import Element

    from maptasker.src.mapjump import Target


# Deliberately short.  EditText's arg1 and Slider's arg4 are the two confirmed by real
# Scenes (an EditText carries '%aab_form2b' there, a Slider '<var>%AAB_ScaleTaperMidpoint');
# CheckBox and Switch are read from their argument shape, a label in arg0 and a single
# state in arg1 and nothing else.  The other input types are left out rather than guessed
# at, because the cost is asymmetric: a wrong entry here records a set that never happens
# and silently suppresses a real "read but never set", while a missing one only leaves a
# variable looking unset, which the limitations already warn about.
_LEGACY_VALUE_ARGS = {
    "EditTextElement": "1",
    "SliderElement": "4",
    "CheckBoxElement": "1",
    "SwitchElement": "1",
}

# Version 2 component properties that bind two-way, the same as a Legacy value field: a
# TextInput's "value" is both what it displays and where what the user types is put.
_V2_VALUE_KEYS = frozenset({"value", "checked"})


@dataclass(frozen=True)
class TextSite:
    """One piece of text in a Scene that may name a variable.

    `spot` is where it is, in the form the Map view can find; `detail` says what holds it, in
    words a report can print.  `element` is the element whose text this is, so a rewrite can
    reach it (None where an argument is not in the file) -- for a Version 2 Scene that is the
    <Scene> itself, since the text is inside its JSON, and `path` is then (component path,
    property key), which survives a re-decode where a reference into a decoded layout would not.

    `two_way` marks an input's value: the Scene shows what the variable holds and writes back
    what the user types, so it is a read AND a write.
    """

    spot: Target
    detail: str
    text: str
    two_way: bool
    element: Element | None
    path: tuple = ()


@dataclass(frozen=True)
class TaskBinding:
    """One place a Scene runs a Task.

    The two kinds name a Task differently: a Legacy element holds the Task's id, a Version 2
    handler its name.  Exactly one of `task_id` and `task_name` is set, and the analysis
    resolves whichever it was given.  `referrer` is the phrase for "this Task is run by ..."
    and `broken` the sentence for "...but there is no such Task"; both are worded here because
    what a binding is called differs by kind ("Button 'OK' ClickTask" against "component
    'OK'").  `component` is True for a Version 2 component, False for a Legacy element.
    """

    task_id: str
    task_name: str
    referrer: str
    broken: str
    component: bool


class SceneModel(Protocol):
    """What the analyses can ask of a Scene of either kind."""

    # The kind, as the user sees it (sceneedit.SCENE_VERSION_LEGACY / SCENE_VERSION_V2).
    name: str

    def text_sites(self, scene_element: Element, place: Target) -> Iterator[TextSite]:
        """Every piece of text in this Scene that holds something worth reading, in document order."""
        ...

    def task_bindings(self, scene_element: Element) -> Iterator[TaskBinding]:
        """Every Task this Scene runs that can be checked against the file."""
        ...


class LegacyModel:
    """A Legacy Scene: a flat list of elements, each with arguments in child elements."""

    name = sceneedit.SCENE_VERSION_LEGACY

    def text_sites(self, scene_element: Element, place: Target) -> Iterator[TextSite]:
        """The text of every element's arguments.

        .iter() rather than direct children, because a Legacy element can hold another (every
        element here carries a RectElement background), and a binding on a nested one is every
        bit as real.

        Every site is against the ELEMENT, not the Scene.  A Scene is the one object in a report
        whose findings are never about the object itself -- "%Notes is read and nothing sets it"
        is a fact about one element of a Scene that may hold fifty of them -- so the location
        says which element, and a click on it lands on that element's own line in the Map.
        Elements the Map does not anchor keep the Scene's own anchor.
        """
        parts = scene_element_parts(scene_element)
        for element in scene_element.iter():
            if not element.tag.endswith("Element"):
                continue
            label = sceneedit_legacy.legacy_element_label(element)
            spot = place.at_part(parts.get(id(element), ""), f"element {label}")
            value_arg = _LEGACY_VALUE_ARGS.get(element.tag)
            nodes = argument_elements(element)
            for arg_id, text in string_arguments(element).items():
                if not text:
                    continue
                two_way = arg_id == value_arg
                detail = f"{label} value (two-way)" if two_way else label
                yield TextSite(spot, detail, text, two_way, nodes.get(arg_id))

    def task_bindings(self, scene_element: Element) -> Iterator[TaskBinding]:
        """The Task id each element's <clickTask> and friends names.

        .iter() for the reason text_sites gives.  An anonymous Task lives inside the Scene itself
        under a negative id, is in no table, and has nothing to check -- it is left out, along
        with an event with no Task bound at all.
        """
        for element in scene_element.iter():
            if not element.tag.endswith("Element"):
                continue
            # legacy_element_label reads the element's own name from arg0 and renders it the way
            # the designer's tree does ("Button 'Cancel'"), so a finding names the element by
            # what the user will see when they go to fix it.
            label = sceneedit_legacy.legacy_element_label(element)
            for binding in element:
                if binding.tag not in SCENE_TASK_TYPES:
                    continue
                task_id = (binding.text or "").strip()
                if not task_id or task_id.startswith(sceneedit_legacy.LEGACY_ANONYMOUS_TASK_PREFIX):
                    continue
                event = SCENE_TASK_TYPES[binding.tag]
                yield TaskBinding(
                    task_id=task_id,
                    task_name="",
                    referrer=f"{label} {event}",
                    broken=f"{label} '{event}' fires Task id {task_id}, which is not in this file.",
                    component=False,
                )


class V2Model:
    """A Version 2 Scene: one gzipped JSON layout of components."""

    name = sceneedit.SCENE_VERSION_V2

    def text_sites(self, scene_element: Element, place: Target) -> Iterator[TextSite]:
        """The text of every component property that can hold a variable.

        Each component is read for its OWN properties only -- child slots are skipped, because
        a node's dict contains its whole subtree and counting that would report every variable
        once per ancestor, which on a 53-component Scene means a variable read once looking read
        six times.

        Every site is against the component's own PROPERTY, not the Scene, and one property
        rather than one component, because the Map writes a V2 component out one property per
        line, so there is an exact line for a finding to land on.
        """
        layout = sceneedit.decode_v2_layout(scene_element)
        # None means an <lj> that would not decode.  Guessing at a corrupt layout would invent
        # references, so there is nothing to yield.
        if layout is None:
            return

        for row in sceneedit_v2.v2_flatten(layout):
            child_slots = {slot for slot, _ in sceneedit_v2.v2_child_slots(row.node)}
            for key, value in row.node.items():
                if key in child_slots:
                    continue
                # Asked before the strings are walked, rather than left to the test below, so
                # that the properties this yields are visibly the same set the Map anchors --
                # see mapjump.v2_property_holds_a_variable, which is that one question.
                if not v2_property_holds_a_variable(value):
                    continue
                for text in v2_strings(value):
                    if "%" not in text:
                        continue
                    spot = place.at_part(
                        scene_component_part(row.path, key),
                        f"component {row.label} {key}",
                    )
                    yield TextSite(
                        spot,
                        f"component '{row.label}' {key}",
                        text,
                        key in _V2_VALUE_KEYS,
                        scene_element,
                        (row.path, key),
                    )

    def task_bindings(self, scene_element: Element) -> Iterator[TaskBinding]:
        """The Task each RunTask handler names.

        A handler names its Task rather than pointing at an id.  A name is yielded as it stands,
        variable-bearing ones included: whether a name can be checked at all is the analysis's
        policy, not a fact about a Scene.
        """
        layout = sceneedit.decode_v2_layout(scene_element)
        # None means a Legacy Scene or an <lj> that would not decode.  Either way there is
        # nothing here to check, and guessing at a corrupt layout would invent findings.
        if layout is None:
            return

        for row in sceneedit_v2.v2_flatten(layout):
            for handler in sceneedit_v2.v2_handlers(row.node):
                for action in handler.get("actions") or ():
                    if not isinstance(action, dict) or action.get("type") != "RunTask":
                        continue
                    task_name = (action.get("task") or "").strip()
                    if not task_name:
                        continue
                    yield TaskBinding(
                        task_id="",
                        task_name=task_name,
                        referrer=f"component '{row.label}'",
                        broken=f"component '{row.label}' runs Task '{task_name}', which is not in this file.",
                        component=True,
                    )


_LEGACY = LegacyModel()
_V2 = V2Model()


def model_of(scene_element: Element) -> SceneModel:
    """The model for this Scene's kind.

    Told apart by whether it has an <lj> child, which is the whole test in both directions --
    see sceneedit.is_v2_scene, the one place that is decided.
    """
    return _V2 if sceneedit.is_v2_scene(scene_element) else _LEGACY
