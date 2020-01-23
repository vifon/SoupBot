import re

from typing import TYPE_CHECKING, Dict, Any, Callable, Match
if TYPE_CHECKING:
    from irc.client import IRCClient
    from irc.message import IRCMessage
    import sqlite3


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

        self.config = config or {}

        if old_data:
            self.shared_data = old_data
        else:
            self.shared_data = self._shared_data_init()

    def react(self, msg: 'IRCMessage'):
        """React to the received message in some way.

        If returns a true value, the message won't be processed by any
        more plugins.

        """
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


class IRCCommandPlugin(IRCPlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.commands: Dict[str, Callable] = {}

    def react(self, msg: 'IRCMessage'):
        super().react(msg)

        if msg.command == 'PRIVMSG':
            assert msg.body is not None
            assert msg.sender is not None

            for command_re, command in self.commands.items():
                match = re.match(command_re, msg.body)
                if match:
                    channel = msg.args[0]
                    sender = msg.sender.nick
                    command(sender, channel, match, msg)

    def command(self, sender: str, channel: str, match: Match, msg: 'IRCMessage') -> None:
        raise NotImplementedError()
