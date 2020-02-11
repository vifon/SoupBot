from functools import wraps
import asyncio

from .async_helpers import asynchronize, avait


class ConversationStep:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def __call__(self, test, logger):
        pass


class ConversationDelay(ConversationStep):
    def __init__(self, delay, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.delay = delay

    async def __call__(self, test, logger):
        logger.debug("Waiting for %d seconds…", self.delay)
        await asyncio.sleep(self.delay)
        logger.debug("Continuing after the delay.")
        await super().__call__(test, logger)


class ConversationSend(ConversationStep):
    def __init__(self, msg, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.msg = msg

    async def __call__(self, test, logger):
        logger.debug("Sending %s", self.msg)
        await test.client._send(self.msg, allow_unsafe=True)
        await super().__call__(test, logger)


class ConversationRecv(ConversationStep):
    def __init__(self, expected_resp, *args, regexp=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.expected_resp = expected_resp
        self.regexp = regexp

    async def __call__(self, test, logger):
        logger.debug("Expecting %s", self.expected_resp)
        try:
            received_resp = await asyncio.wait_for(test.client.recv(), timeout=5)
        except asyncio.TimeoutError:
            logger.error('Expected "%s", got nothing.', self.expected_resp)
            raise
        logger.debug("Received %s", received_resp)
        if self.regexp:
            test.assertRegex(str(received_resp), self.expected_resp)
        else:
            test.assertEqual(str(received_resp), self.expected_resp)
        await super().__call__(test, logger)


class ConversationNoResponse(ConversationStep):
    def __init__(self, timeout=0.01, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timeout = timeout

    async def __call__(self, test, logger):
        try:
            response = await asyncio.wait_for(
                test.client.recv(),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            did_timeout = True
        else:
            did_timeout = False
            logger.error('Expected nothing, got "%s"', response)
        test.assertTrue(did_timeout)
        await super().__call__(test, logger)


class ConversationSendIgnored(ConversationSend, ConversationNoResponse):
    pass


class ConversationSendRecv(ConversationSend, ConversationRecv):
    pass


def conversation(orig_test):
    @wraps(orig_test)
    @asynchronize
    async def real_test(self):
        exchange = orig_test(self)
        logger = self.logger.getChild(orig_test.__name__)
        for step in exchange:
            await step(self, logger)
    return real_test
