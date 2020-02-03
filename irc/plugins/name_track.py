from collections import defaultdict
from irc.message import IRCMessage
from irc.plugin import IRCPlugin
import asyncio


# Source: https://stackoverflow.com/a/2912455
class defaultdict_with_key(defaultdict):
    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError(key)
        else:
            self[key] = self.default_factory(key)
            return self[key]


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
                if nick in await nicks:
                    await self.forget(channel, nick)

        async def KICK(msg):
            channel, nick = msg.args
            await self.forget(channel, nick)

        async def NICK(msg):
            old_nick = msg.sender.nick
            new_nick = msg.args[0]
            await self.rename(old_nick, new_nick)

        if msg.command in ('JOIN', 'PART', 'QUIT', 'KICK', 'NICK'):
            await locals()[msg.command](msg)

    async def query_names(self, channel):
        self.logger.info("No cached names for %s, querying…", channel)
        self.client.send(IRCMessage('NAMES', channel))
        names = set()
        while True:
            response = await self.queue.get()
            if response.command == "366":  # RPL_ENDOFNAMES
                break
            if response.command == "353":  # RPL_NAMREPLY
                if response.args[-1] == channel:
                    names.update(
                        nick.lstrip("@+")
                        for nick in response.body.split()
                    )
        self.logger.info("Nicks on %s: %s", channel, names)
        return names

    async def acknowledge(self, channel, nick):
        self.logger.info("%s joined %s, acknowledging…", nick, channel)
        names = await self.shared_data[channel]
        names.add(nick)

    async def forget(self, channel, nick):
        self.logger.info("%s left %s, forgetting…", nick, channel)
        names = await self.shared_data[channel]
        names.discard(nick)

    async def rename(self, old_nick, new_nick):
        for channel, nicks in self.shared_data.items():
            if old_nick in await nicks:
                self.logger.info(
                    "%s is not known as %s on %s",
                    old_nick, new_nick, channel
                )
                nicks.discard(old_nick)
                nicks.add(new_nick)

    def _shared_data_init(self):
        def factory(channel):
            return asyncio.ensure_future(self.query_names(channel))
        return defaultdict_with_key(factory)
