from irc.message import IRCMessage
from irc.plugin import IRCCommandPlugin, NotAuthorizedError, authenticated


class Commandline(IRCCommandPlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.commands.update({
            r'\.join +(\#\#?[\w-]+)$': self.__join,
            r'\.part +(\#\#?[\w-]+)$': self.__part,
            r'\.raw +(.+)$': self.__raw,
        })

    def auth(self, sender, channel):
        super().auth(sender, channel)
        if channel != self.client.nick:
            raise NotAuthorizedError(sender, channel)

    @authenticated
    async def __join(self, sender, channel, match, msg):
        self.client.send(IRCMessage('JOIN', match[1]))

    @authenticated
    async def __part(self, sender, channel, match, msg):
        self.client.send(IRCMessage('PART', match[1]))

    @authenticated
    async def __raw(self, sender, channel, match, msg):
        self.client.send(match[1])
