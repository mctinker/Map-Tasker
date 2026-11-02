"""What every kind of editor handler shares."""

from __future__ import annotations

from maptasker.src.gui.guiwins_dialogs import (
    build_unsaved_deletion_dialog,
)
from maptasker.src.gui.userintr_group import HandlerGroup


class EditorHandlerBase(HandlerGroup):
    """What every kind of editor handler shares."""

    def _offer_save_after_delete(self, message: str) -> None:
        """Offer Save To Current File once a delete has closed the dialog that held the only one."""
        build_unsaved_deletion_dialog(message, self.hub.save_whole_configuration)
