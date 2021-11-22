"""An experimental watchdog closing the bot after a period of inactivity.

The expectation is for some service manager (systemd, supervisord…) to
restart the bot after it exits.

"""

from irc.message import IRCMessage
from irc.plugin import IRCPlugin

import asyncio
import sys

from typing import Optional  # noqa: F402, E501


class WatchdogPlugin(IRCPlugin):
    shared_data: Optional[asyncio.Future]

    async def react(self, msg: IRCMessage) -> None:
        if self.shared_data:
            self.shared_data.cancel()

        async def killer() -> None:
            await asyncio.sleep(self.config["timeout"])
            sys.exit(1)

        self.shared_data = asyncio.ensure_future(killer())
