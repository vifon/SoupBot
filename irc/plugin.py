class IRCPlugin:
    def __init__(self, client, config=None):
        self.client = client
        self.logger = self.client.logger.getChild(type(self).__name__)
        self.logger.info("Initalizing plugin.")

        self.config = config or {}
        self.shared_data = self._shared_data_init()

    def react(self, msg):
        """React to the received message in some way.

        If returns a true value, the message won't be processed by any
        more plugins.

        """
        return None

    def _shared_data_init(self):
        """The initial value of IRCClient.shared_data.ThisPlugin"""
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
