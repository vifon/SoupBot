from irc.plugin import IRCPlugin


class PongPlugin(IRCPlugin):
    def match(self, msg):
        return msg.command == 'PING'

    def respond(self, msg):
        self.client.send('PONG', body=msg.body)
