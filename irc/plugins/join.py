from irc.plugin import IRCPlugin


class JoinChannels(IRCPlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for channel in self.config['channels']:
            self.client.send('JOIN', channel)
            self.logger.info("Joining %s…", channel)

