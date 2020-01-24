from collections import defaultdict
from irc.plugin import IRCPlugin
import asyncio


class NameSet(set):
    def __init__(self, logger, queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logger.getChild(type(self).__name__)
        self.queue = queue

    async def refresh_if_empty(self, channel, client):
        if not self:
            self.logger.info("No cached names for %s, querying…", channel)
            await client.send('NAMES', channel)
            while True:
                response = await self.queue.get()
                if response.command == "366":  # RPL_ENDOFNAMES
                    break
                if response.command == "353":  # RPL_NAMREPLY
                    if response.args[-1] == channel:
                        self.update(
                            nick.lstrip("@+")
                            for nick in response.body.split()
                        )
            self.logger.info("Nicks on %s: %s", channel, self)
        return self


class NameTrack(IRCPlugin):
    async def react(self, msg):
        async def JOIN(msg):
            channel = msg.args[0]
            nick = msg.sender.nick
            await self.acknowledge(channel, nick)

        async def PART(msg):
            channel = msg.args[0]
            nick = msg.sender.nick
            await self.forget(channel, nick)

        async def QUIT(msg):
            nick = msg.sender.nick
            for channel, nicks in self.shared_data.items():
                if nick in nicks:
                    await self.forget(channel, nick)

        async def KICK(msg):
            channel, nick = msg.args
            await self.forget(channel, nick)

        async def NICK(msg):
            old_nick = msg.sender.nick
            new_nick = msg.args[0]
            self.rename(old_nick, new_nick)

        if msg.command in ('JOIN', 'PART', 'QUIT', 'KICK', 'NICK'):
            await locals()[msg.command](msg)

    async def acknowledge(self, channel, nick):
        self.logger.info("%s joined %s, acknowledging…", nick, channel)
        names = await self.shared_data[channel].refresh_if_empty(
            channel=channel,
            client=self.client,
        )
        names.add(nick)

    async def forget(self, channel, nick):
        self.logger.info("%s left %s, forgetting…", nick, channel)
        names = await self.shared_data[channel].refresh_if_empty(
            channel=channel,
            client=self.client,
        )
        names.discard(nick)

    def rename(self, old_nick, new_nick):
        for channel, nicks in self.shared_data.items():
            if old_nick in nicks:
                self.logger.info(
                    "%s is not known as %s on %s",
                    old_nick, new_nick, channel
                )
                nicks.discard(old_nick)
                nicks.add(new_nick)

    def _shared_data_init(self):
        def factory():
            return NameSet(
                logger=self.logger,
                queue=self.queue,
            )
        return defaultdict(factory)
