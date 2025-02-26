# Copyright Pincer 2021-Present
# Full MIT License can be found in `LICENSE` at the project root.

from __future__ import annotations

from typing import TYPE_CHECKING

from ...objects.message.component import MessageComponent

from ...utils.api_object import APIObject
if TYPE_CHECKING:
    from typing import Dict


class ActionRow(APIObject):
    """Represents an Action Row

    Parameters
    ----------
    \\*components : :class:`~pincer.objects.message.component.MessageComponent`
        :class:`~pincer.objects.message.component.MessageComponent`,
        :class:`~pincer.objects.message.button.Button`, or
        :class:`~pincer.objects.message.select_menu.SelectMenu`
    """

    def __init__(self, *components: MessageComponent):
        self.components = components

    def to_dict(self) -> Dict:
        return {
            "type": 1,
            "components": [component.to_dict() for component in self.components]
        }
