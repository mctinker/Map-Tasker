"""The two Scene designers behind one interface: pick the one for a Scene, mount it."""

#! /usr/bin/env python3

#                                                                                      #
# guiwins_designers: which designer a Scene gets, decided in one place.                  #
#                                                                                      #
# A Legacy Scene is edited as a picture on a canvas and a Version 2 Scene as a tree of    #
# components, and what each designer does has almost nothing in common -- so what is shared  #
# here is deliberately small: how a dialog MOUNTS one (build_body) and what its Preview       #
# button promises (preview_tooltip).  The designers' own operations are not behind this        #
# interface, because there is nothing true to say about restacking an element and moving a      #
# component that both would satisfy.                                                            #
#                                                                                      #
# Before this, the Scene dialogs chose between the two with their own test of the Scene's       #
# kind and a branch.  Now they ask designer_for(scene) and call what they get, so the one        #
# place that knows there are two kinds of Scene is scenemodel (which decides) and this           #
# module (which maps each kind to its designer).                                                  #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
#
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from maptasker.src import sceneedit, scenemodel
from maptasker.src.guiwins_designer_legacy import LegacyDesigner
from maptasker.src.guiwins_designer_v2 import V2Designer

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from nicegui import ui

    from maptasker.src.primitem import RunState
    from maptasker.src.userintr import MyGui


class SceneDesigner(Protocol):
    """What a Scene dialog needs from the designer of whichever kind of Scene it was handed."""

    # English source text for the Preview button's tooltip (translate_string is applied by the
    # dialog): the two kinds preview from different things -- the size typed in the dialog, or a
    # screen the preview itself offers -- and the tooltip says which.
    preview_tooltip: str

    def build_body(
        self,
        gui: MyGui,
        edited_scene: sceneedit.EditableScene,
        field_refs: dict,
        dialog: ui.dialog | None,
        *,
        state: RunState,
    ) -> None:
        """Put everything below the Scene's name into the dialog being built.

        Anything the dialog has to read back at save time goes into field_refs; what the designer
        edits in place needs nothing from either dialog beyond the dict it is already handed.
        """
        ...


_DESIGNERS: dict[str, SceneDesigner] = {
    sceneedit.SCENE_VERSION_LEGACY: LegacyDesigner(),
    sceneedit.SCENE_VERSION_V2: V2Designer(),
}


def designer_for(scene_element: Element) -> SceneDesigner:
    """The designer for this Scene's kind."""
    return _DESIGNERS[scenemodel.model_of(scene_element).name]
