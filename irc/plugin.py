class IRCPlugin:
    def __init__(self, client, config=None):
        self.client = client
        self.config = config or {}
        self.logger = self.client.logger.getChild(type(self).__name__)
        self.shared_data = self._shared_data_init()
        self.logger.info("Initalizing plugin.")

    def match(self, msg):
        raise NotImplementedError()

    def respond(self, msg):
        raise NotImplementedError()

    def react(self, msg):
        if self.match(msg):
            self.respond(msg)

    def _shared_data_init(self):
        return None

    @property
    def shared_data(self):
        return getattr(
            self.client.shared_data,
            type(self).__name__,
        )

    @shared_data.setter
    def shared_data(self, value):
        return setattr(
            self.client.shared_data,
            type(self).__name__,
            value,
        )

    @property
    def db(self):
        return self.client.db
