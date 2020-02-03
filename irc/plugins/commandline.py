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
            if self.auth(msg.sender) and channel == self.client.nick:
                await super().react(msg)

    async def __join(self, sender, channel, match, msg):
        self.client.send(IRCMessage('JOIN', match[1]))

    async def __part(self, sender, channel, match, msg):
        self.client.send(IRCMessage('PART', match[1]))

    async def __raw(self, sender, channel, match, msg):
        self.client.send(match[1])
