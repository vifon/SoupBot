class IRCPlugin:
    def __init__(self, client, config=None):
        self.client = client
        self.logger = self.client.logger.getChild(type(self).__name__)
        self.logger.info("Initalizing plugin.")

        self.config = config or {}
        self.shared_data = self._shared_data_init()

    def match(self, msg):
        """Check whether to react to the given message.

        This value is also passed to `respond()` instead of the
        original message if it's not boolean but still true-like
        value.

        """
        return None

    def respond(self, msg):
        raise NotImplementedError()

    def react(self, msg):
        match = self.match(msg)
        if match:
            if match is True:
                self.respond(msg)
            else:
                self.respond(match)

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
