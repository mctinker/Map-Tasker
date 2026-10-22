"""userintr_group: the base of the handler groups that MapTaskerEventHandlers is made of.

The handlers used to be mixins: eight classes MapTaskerEventHandlers inherited, all reading and calling each
other through one shared `self`.  Nothing in a mixin said which of its names came from the others, so every
method was annotated `self: MapTaskerEventHandlers` to be type-checked at all, and any new method could
silently take the name of one in another group.

Now each group is an object of its own, held by the hub as an attribute (hub.editors, hub.settings ...).  What
a group shares with the rest is the hub, `self.hub`, and through it the window and the run state; whatever it
needs of another group it asks for by name (`self.hub.prebuild.view_in_progress()`), so the dependencies
between groups can be read off the code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from maptasker.src.core.primitem import RunState
    from maptasker.src.gui.userintr import MapTaskerEventHandlers, MyGui


class HandlerGroup:
    """One feature's event handlers: the hub they belong to, and the window and run state it holds."""

    def __init__(self, hub: MapTaskerEventHandlers) -> None:
        """Remember the hub; the window and the run state are read from it, not copied."""
        self.hub = hub

    @property
    def gui(self) -> MyGui:
        """The window these handlers act on."""
        return self.hub.gui

    @property
    def state(self) -> RunState:
        """The run state the window shows and edits."""
        return self.hub.state
