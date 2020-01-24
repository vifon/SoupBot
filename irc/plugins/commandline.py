from irc.message import IRCMessage
from irc.plugin import IRCCommandPlugin


class Commandline(IRCCommandPlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.commands.update({
            r'\.join +(\#\#?[\w-]+)$': self.__join,
            r'\.part +(\#\#?[\w-]+)$': self.__part,
            r'\.raw +(.+)$': self.__raw,
        })

    async def react(self, msg):
        if msg.command == 'PRIVMSG':
            channel = msg.args[0]
            if msg.sender.identity == self.config['admin'] \
               and channel == self.client.nick:
                await super().react(msg)

    async def __join(self, sender, channel, match, msg):
        await self.client.send('JOIN', match[1])

    async def __part(self, sender, channel, match, msg):
        await self.client.send('PART', match[1])

    async def __raw(self, sender, channel, match, msg):
        new_message = IRCMessage.parse(match[1])
        await self.client.sendmsg(new_message)
