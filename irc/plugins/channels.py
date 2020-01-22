from irc.plugin import IRCPlugin


class ChannelManager(IRCPlugin):
    async def start(self):
        await super().start()

        channels = set(self.config['channels'])
        join = channels.difference(self.shared_data)
        part = self.shared_data.difference(channels)
        self.shared_data = channels

        for channel in join:
            self.logger.info("Joining %s…", channel)
            await self.client.send('JOIN', channel)
        for channel in part:
            self.logger.info("Parting %s…", channel)
            await self.client.send('PART', channel)

    def _shared_data_init(self):
        return set()
