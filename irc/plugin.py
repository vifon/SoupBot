import asyncio
import re

from typing import TYPE_CHECKING, Dict, Any, Callable, Match, Optional
if TYPE_CHECKING:
    from irc.client import IRCClient    # noqa: F401
    from irc.message import IRCMessage  # noqa: F401
    import sqlite3                      # noqa: F401


class IRCPlugin:
    def __init__(
            self,
            client: 'IRCClient',
            config: Dict,
            old_data: Any = None,
    ):
        self.client = client
        self.logger = self.client.logger.getChild(type(self).__name__)
        self.logger.info("Initalizing plugin.")

        self.queue: asyncio.Queue['IRCMessage'] = asyncio.Queue()

        self.config = config or {}

        if old_data:
            self.shared_data = old_data
        else:
            self.shared_data = self._shared_data_init()

    async def start(self) -> None:
        """Called when all the plugins are already loaded."""
        pass

    async def event_loop(self):
        try:
            while True:
                msg = await self.queue.get()
                self.logger.debug(
                    "Queue size on processing: %d", self.queue.qsize()
                )
                await self.react(msg)
                self.queue.task_done()
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger.exception(
                "%s caused an exception during processing: %s",
                self, repr(msg),
            )
        finally:
            self.logger.info("%s has finished.", self)

    async def react(self, msg: 'IRCMessage'):
        """React to the received message in some way."""
        pass

    def _shared_data_init(self) -> Any:
        """The initial value of IRCClient.shared_data.ThisPlugin"""
        return None

    @property
    def shared_data(self) -> Any:
        return getattr(
            self.client.shared_data,
            type(self).__name__,
        )

    @shared_data.setter
    def shared_data(self, value: Any) -> None:
        return setattr(
            self.client.shared_data,
            type(self).__name__,
            value,
        )

    @property
    def db(self) -> 'sqlite3.Connection':
        return self.client.db

    def auth(self, sender):
        return sender.identity in self.config['admin']


class IRCCommandPlugin(IRCPlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.commands: Dict[str, Callable] = {}

    async def react(self, msg: 'IRCMessage') -> Optional[bool]:
        if msg.command == 'PRIVMSG':
            assert msg.body is not None
            assert msg.sender is not None

            for command_re, command in self.commands.items():
                match = re.match(command_re, msg.body)
                if match:
                    channel = msg.args[0]
                    sender = msg.sender
                    if await command(sender, channel, match, msg):
                        return True
        await super().react(msg)

    async def command(
            self,
            sender: str,
            channel: str,
            match: Match,
            msg: 'IRCMessage',
    ) -> Optional[bool]:
        raise NotImplementedError()
