from irc.plugin import IRCPlugin


class PongPlugin(IRCPlugin):
    async def react(self, msg):
        if msg.command == 'PING':
            await self.client.send('PONG', body=msg.body)
