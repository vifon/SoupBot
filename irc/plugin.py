class IRCPlugin:
    def __init__(self, client):
        self.client = client

    def match(self, msg):
        raise NotImplementedError()

    def respond(self, msg):
        raise NotImplementedError()

    def react(self, msg):
        if self.match(msg):
            self.respond(msg)


class PongPlugin(IRCPlugin):
    def match(self, msg):
        return msg.command == 'PING'

    def respond(self, msg):
        self.client.send('PONG', body=msg.body)
