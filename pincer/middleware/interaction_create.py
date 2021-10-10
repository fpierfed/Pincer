# Copyright Pincer 2021-Present
# Full MIT License can be found in `LICENSE` at the project root.

from __future__ import annotations

import logging
from inspect import isasyncgenfunction
from typing import Union, Dict, Any, Tuple, List, TYPE_CHECKING

from ..utils.types import Coro
from ..objects.message.embed import Embed
from ..core.dispatch import GatewayDispatch
from ..objects.message.message import Message
from ..objects.app.interactions import Interaction
from ..objects.message.context import MessageContext

if TYPE_CHECKING:
    from PIL.Image import Image

    from ..commands import ChatCommandHandler
    from ..objects.message.file import File
    from ..objects.app.interactions import InteractionFlags
    from ..utils.insertion import should_pass_cls, should_pass_ctx
    from ..utils.types import MISSING
    from ..utils.signature import get_params, get_signature_and_params


_log = logging.getLogger(__name__)


def convert_message(self, message: Union[Embed, Message, str]) -> Message:
    """Converts a message to a Message object

    Parameters
    ----------
    message :
        Message to convert
    """
    if isinstance(message, Embed):
        message = Message(embeds=[message])
    elif isinstance(message, (File, Image)):
        message = Message(attachments=[message])
    elif not isinstance(message, Message):
        message = Message(message) if message else Message(
            self.received_message,
            flags=InteractionFlags.EPHEMERAL
        )
    return message


async def reply(self, interaction: Interaction, message: Message):
    """|coro|

    Sends a reply to an interaction.

    Parameters
    ----------
    interaction :
        The interaction from whom the reply is.
    message :
        The message to reply with.
    """

    content_type, data = message.serialize()

    await self.http.post(
        f"interactions/{interaction.id}/{interaction.token}/callback",
        data,
        content_type=content_type
    )


async def interaction_response_handler(
        self,
        command: Coro,
        context: MessageContext,
        interaction: Interaction,
        kwargs: Dict[str, Any]
):
    """|coro|

    Handle any coroutine as a command.

    Parameters
    ----------
    command :
        The coroutine which will be seen as a command.
    context :
        The context of the command.
    interaction :
        The interaction which is linked to the command.
    kwargs :
        The arguments to be passed to the command.
    """
    if should_pass_cls(command):
        kwargs["self"] = ChatCommandHandler.managers[command.__module__]

    sig, params = get_signature_and_params(command)
    if should_pass_ctx(sig, params):
        kwargs[params[0]] = context

    if isasyncgenfunction(command):
        message = command(**kwargs)
        started = False

        async for msg in message:
            msg = convert_message(self, msg)

            if started:
                await self.http.post(
                    f"webhooks/{interaction.application_id}"
                    f"/{interaction.token}",
                    msg.to_dict().get("data")
                )
            else:
                started = True
                await reply(self, interaction, msg)
    else:
        message = await command(**kwargs)
        await reply(self, interaction, convert_message(self, message))


async def interaction_handler(
        self,
        interaction: Interaction,
        context: MessageContext,
        command: Coro
):
    """|coro|

    Processes an interaction.

    Parameters
    ----------
    interaction :
        The interaction which is linked to the command.
    context :
        The context of the command.
    command :
        The coroutine which will be seen as a command.
    """
    self.throttler.handle(context)

    defaults = {param: None for param in get_params(command)}
    params = {}

    if interaction.data.options is not MISSING:
        params = {
            opt.name: opt.value for opt in interaction.data.options
        }

    kwargs = {**defaults, **params}

    await interaction_response_handler(self, command, context, interaction,
                                       kwargs)


async def interaction_create_middleware(
    self,
    payload: GatewayDispatch
) -> Tuple[str, List[Interaction]]:
    """Middleware for ``on_interaction``, which handles command
    execution.

    Parameters
    ----------
    payload :
        The data received from the interaction event.

    Raises
    ------
    e
        Generic try except on ``await interaction_handler`` and
        ``if 0 < len(params) < 3``
    """
    interaction: Interaction = Interaction.from_dict(
        {**payload.data, "_client": self, "_http": self.http}
    )
    command = ChatCommandHandler.register.get(interaction.data.name)

    if command:
        context = interaction.convert_to_message_context(command)

        try:
            await interaction_handler(self, interaction, context,
                                      command.call)
        except Exception as e:
            if coro := self.get_event_coro("on_command_error"):
                params = get_signature_and_params(coro)[1]

                # Check if a context or error var has been passed.
                if 0 < len(params) < 3:
                    await interaction_response_handler(
                        self,
                        coro,
                        context,
                        interaction,
                        # Always take the error parameter its name.
                        {params[(len(params) - 1) or 0]: e}
                    )
                else:
                    raise e
            else:
                raise e

    return "on_interaction_create", [interaction]


def export() -> Coro:
    return interaction_create_middleware
