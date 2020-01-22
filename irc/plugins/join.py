from irc.plugin import IRCPlugin


class JoinChannels(IRCPlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        channels = set(self.config['channels'])
        join = channels.difference(self.shared_data)
        part = self.shared_data.difference(channels)
        self.shared_data = channels

        for channel in join:
            self.client.send('JOIN', channel)
            self.logger.info("Joining %s…", channel)
        for channel in part:
            self.client.send('PART', channel)
            self.logger.info("Parting %s…", channel)

    def _shared_data_init(self):
        return set()
