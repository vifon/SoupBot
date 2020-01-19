class IRCPlugin:
    def __init__(self, client, config=None):
        self.client = client
        self.config = config or {}
        self.logger = self.client.logger.getChild(type(self).__name__)
        self.logger.info("Initalizing plugin.")

    def match(self, msg):
        raise NotImplementedError()

    def respond(self, msg):
        raise NotImplementedError()

    def react(self, msg):
        if self.match(msg):
            self.respond(msg)

    @property
    def db(self):
        return self.client.db
