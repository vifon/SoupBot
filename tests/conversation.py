from typing import List
import asyncio
import logging
import pytest
import re

from irc.client import IRCClient

logger = logging.getLogger(__name__)


class ConversationStep:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def __call__(self, client):
        pass


class ConversationDelay(ConversationStep):
    def __init__(self, delay, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.delay = delay

    async def __call__(self, client):
        logger.debug("Waiting for %d seconds…", self.delay)
        await asyncio.sleep(self.delay)
        logger.debug("Continuing after the delay.")
        await super().__call__(client)


class ConversationSend(ConversationStep):
    def __init__(self, msg, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.msg = msg

    async def __call__(self, client):
        logger.debug("Sending %s", self.msg)
        await client._send(self.msg, allow_unsafe=True)
        await super().__call__(client)


class ConversationRecv(ConversationStep):
    def __init__(self, expected_resp, *args, regexp=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.expected_resp = expected_resp
        self.regexp = regexp

    async def __call__(self, client):
        logger.debug("Expecting %s", self.expected_resp)
        try:
            received_resp = await asyncio.wait_for(client.recv(), timeout=5)
        except asyncio.TimeoutError:
            logger.error('Expected "%s", got nothing.', self.expected_resp)
            raise
        logger.debug("Received %s", received_resp)
        if self.regexp:
            assert re.match(self.expected_resp, str(received_resp))
        else:
            assert str(received_resp) == self.expected_resp
        await super().__call__(client)


class ConversationNoResponse(ConversationStep):
    def __init__(self, timeout=0.1, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timeout = timeout

    async def __call__(self, client):
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                client.recv(),
                timeout=self.timeout,
            )
        await super().__call__(client)


class ConversationSendIgnored(ConversationSend, ConversationNoResponse):
    pass


class ConversationSendRecv(ConversationSend, ConversationRecv):
    pass


class IRCTestClient(IRCClient):
    async def conversation(self, exchange: List[ConversationStep]):
        for step in exchange:
            await step(self)
