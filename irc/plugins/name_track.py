from collections import defaultdict
from irc.message import IRCMessage
from irc.plugin import IRCPlugin
import asyncio

from typing import Awaitable, Dict, Set


# Source: https://stackoverflow.com/a/2912455
class defaultdict_with_key(defaultdict):
    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError(key)
        else:
            self[key] = self.default_factory(key)
            return self[key]


class NameTrack(IRCPlugin):
    shared_data: Dict[str, Awaitable[Set[str]]]

    async def react(self, msg: IRCMessage):
        async def JOIN(msg: IRCMessage):
            assert msg.sender is not None
            channel = msg.args[0]
            nick = msg.sender.nick
            await self.acknowledge(channel, nick)

        async def PART(msg: IRCMessage):
            assert msg.sender is not None
            channel = msg.args[0]
            nick = msg.sender.nick
            await self.forget(channel, nick)

        async def QUIT(msg: IRCMessage):
            assert msg.sender is not None
            nick = msg.sender.nick
            for channel, nicks in self.shared_data.items():
                if nick in await nicks:
                    await self.forget(channel, nick)

        async def KICK(msg: IRCMessage):
            channel, nick = msg.args
            await self.forget(channel, nick)

        async def NICK(msg: IRCMessage):
            assert msg.sender is not None
            old_nick = msg.sender.nick
            new_nick = msg.body
            await self.rename(old_nick, new_nick)

        if msg.command in ('JOIN', 'PART', 'QUIT', 'KICK', 'NICK'):
            await locals()[msg.command](msg)

    async def query_names(self, channel: str) -> Set[str]:
        self.logger.info("No cached names for %s, querying…", channel)
        self.client.send(IRCMessage('NAMES', channel))
        names: Set[str] = set()
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

    async def acknowledge(self, channel: str, nick: str):
        self.logger.info("%s joined %s, acknowledging…", nick, channel)
        names = await self.shared_data[channel]
        names.add(nick)

    async def forget(self, channel: str, nick: str):
        self.logger.info("%s left %s, forgetting…", nick, channel)
        names = await self.shared_data[channel]
        names.discard(nick)

    async def rename(self, old_nick: str, new_nick: str):
        for channel, nicks_coro in self.shared_data.items():
            nicks = await nicks_coro
            if old_nick in nicks:
                self.logger.info(
                    "%s is now known as %s on %s",
                    old_nick, new_nick, channel
                )
                nicks.discard(old_nick)
                nicks.add(new_nick)

    def _shared_data_init(self):
        def factory(channel: str) -> Awaitable[Set[str]]:
            return asyncio.ensure_future(self.query_names(channel))
        return defaultdict_with_key(factory)
