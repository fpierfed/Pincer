# -*- coding: utf-8 -*-
# MIT License
#
# Copyright (c) 2021 Pincer
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
import logging
from asyncio import iscoroutinefunction
from typing import Optional, Any, Union, Dict, Tuple, List

from pincer import __package__
from pincer._config import GatewayConfig, events
from pincer.core.dispatch import GatewayDispatch
from pincer.core.gateway import Dispatcher
from pincer.core.http import HTTPClient
from pincer.exceptions import InvalidEventName
from pincer.objects.user import User
from pincer.utils.extraction import get_index
from pincer.utils.insertion import should_pass_cls
from pincer.utils.types import Coro

_log = logging.getLogger(__package__)

middleware_type = Optional[Union[Coro, Tuple[str, List[Any], Dict[str, Any]]]]

_events: Dict[str, Optional[Union[str, Coro]]] = {}

for event in events:
    event_final_executor = f"on_{event}"

    # Event middleware for the library. Function argument is a payload
    # (GatewayDispatch). The function must return a string which
    # contains the main event key. As second value a list with arguments,
    # and thee third value value must be a dictionary. The last two are
    # passed on as *args and **kwargs.
    #
    # NOTE: These return values must be passed as a tuple!
    _events[event] = event_final_executor

    # The registered event by the client. Do not manually overwrite.
    _events[event_final_executor] = None


def middleware(call: str):
    # TODO: Write docs
    # TODO: Write implementation example
    def decorator(func: Coro):
        async def wrapper(cls, payload: GatewayDispatch):
            _log.debug("`%s` middleware has been invoked", call)
            return await func(cls, payload) \
                if should_pass_cls(func) \
                else await func(payload)

        _events[call] = wrapper
        return wrapper

    return decorator


class Client(Dispatcher):
    def __init__(self, token: str):
        """
        The client is the main instance which is between the programmer and the
        discord API. This client represents your bot.

        :param token: The secret bot token which can be found in
            https://discord.com/developers/applications/<bot_id>/bot.
        """
        # TODO: Implement intents
        super().__init__(
            token,
            handlers={
                # Use this event handler for opcode 0.
                0: self.event_handler
            }
        )

        # TODO: close the client after use
        self.http = HTTPClient(token, version=GatewayConfig.version)
        self.bot: Optional[User] = None

    @staticmethod
    def event(coroutine: Coro):
        # TODO: Write docs

        if not iscoroutinefunction(coroutine):
            raise TypeError(
                "Any event which is registered must be a coroutine function"
            )

        name: str = coroutine.__name__.lower()

        if not name.startswith("on_"):
            raise InvalidEventName(
                f"The event `{name}` its name must start with `on_`"
            )

        if _events.get(name) is not None:
            raise InvalidEventName(
                f"The event `{name}` has already been registered or is not "
                f"a valid event name."
            )

        _events[name] = coroutine
        return coroutine

    async def handle_middleware(
            self,
            payload: GatewayDispatch,
            key: str,
            *args,
            **kwargs
    ) -> tuple[Optional[Coro], List[Any], Dict[str, Any]]:
        """
        Handles all middleware recursively. Stops when it has found an
        event name which starts with "on_".

        :param payload: The original payload for the event.
        :param key: The index of the middleware in `_events`.
        :param *args: The arguments which will be passed to the middleware.
        :param **kwargs: The named arguments which will be passed to the
                        middleware.

        :return: A tuple where the first element is the final executor
            (so the event) its index in `_events`. The second and third
            element are the `*args` and `**kwargs` for the event.
        """
        ware: middleware_type = _events.get(key)
        next_call, arguments, params = ware, list(), dict()

        if iscoroutinefunction(ware):
            extractable = await ware(self, payload, *args, **kwargs)

            if not isinstance(extractable, tuple):
                raise RuntimeError(f"Return type from `{key}` middleware must "
                                   f"be tuple. ")

            next_call = get_index(extractable, 0, "")
            arguments = get_index(extractable, 1, list())
            params = get_index(extractable, 2, dict())

        if next_call is None:
            raise RuntimeError(f"Middleware `{key}` has not been registered.")

        return (next_call, arguments, params) \
            if next_call.startswith("on_") \
            else await self.handle_middleware(payload, next_call,
                                              *arguments, **params)

    async def event_handler(self, _, payload: GatewayDispatch):
        """
        Handles all payload events with opcode 0.
        """
        event_name = payload.event_name.lower()

        key, args, kwargs = await self.handle_middleware(payload, event_name)

        call = _events.get(key)

        if iscoroutinefunction(call):
            if should_pass_cls(call):
                kwargs["self"] = self

            await call(*args, **kwargs)

    @middleware("ready")
    async def on_ready_middleware(self, payload: GatewayDispatch):
        """Middleware for `on_ready` event. """
        self.bot = User.from_dict(payload.data.get("user"))
        return "on_ready"


Bot = Client