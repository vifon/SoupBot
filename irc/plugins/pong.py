from irc.plugin import IRCPlugin


class PongPlugin(IRCPlugin):
    def react(self, msg):
        if msg.command == 'PING':
            self.client.send('PONG', body=msg.body)
