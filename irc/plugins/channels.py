from irc.message import IRCMessage
from irc.plugin import IRCPlugin

from typing import Set


class ChannelManager(IRCPlugin):
    shared_data: Set[str]

    def start(self) -> None:
        super().start()

        channels: Set[str] = set(self.config['channels'])
        join = channels.difference(self.shared_data)
        part = self.shared_data.difference(channels)
        self.shared_data = channels

        for channel in join:
            self.logger.info("Joining %s…", channel)
            self.client.send(IRCMessage('JOIN', channel))
        for channel in part:
            self.logger.info("Parting %s…", channel)
            self.client.send(IRCMessage('PART', channel))

    def _shared_data_init(self) -> Set[str]:
        return set()
