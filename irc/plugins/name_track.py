from collections import defaultdict
from irc.plugin import IRCPlugin


# Source: https://stackoverflow.com/a/2912455
class defaultdict_with_key(defaultdict):
    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError(key)
        else:
            self[key] = self.default_factory(key)
            return self[key]


class NameTrack(IRCPlugin):
    def react(self, msg):
        def JOIN(msg):
            channel = msg.args[0]
            nick = msg.sender.nick
            self.acknowledge(channel, nick)

        def PART(msg):
            channel = msg.args[0]
            nick = msg.sender.nick
            self.forget(channel, nick)

        def QUIT(msg):
            nick = msg.sender.nick
            for channel, nicks in self.shared_data.items():
                if nick in nicks:
                    self.forget(channel, nick)

        def KICK(msg):
            channel, nick = msg.args
            self.forget(channel, nick)

        def NICK(msg):
            old_nick = msg.sender.nick
            new_nick = msg.args[0]
            self.rename(old_nick, new_nick)

        if msg.command in ('JOIN', 'PART', 'QUIT', 'KICK', 'NICK'):
            locals()[msg.command](msg)

    def query_names(self, channel):
        self.logger.info("No cached names for %s, querying…", channel)
        self.client.send('NAMES', channel)
        names = set()
        while True:
            response = self.client.recv()
            if response.command == "366":  # RPL_ENDOFNAMES
                break
            if response.command == "353":  # RPL_NAMREPLY
                if response.args[-1] == channel:
                    names.update(
                        nick.lstrip("@+")
                        for nick in response.body.split()
                    )
        self.logger.info("Nicks on %s: %s", channel, names)
        return names

    def acknowledge(self, channel, nick):
        self.logger.info("%s joined %s, acknowledging…", nick, channel)
        self.shared_data[channel].add(nick)

    def forget(self, channel, nick):
        self.logger.info("%s left %s, forgetting…", nick, channel)
        self.shared_data[channel].discard(nick)

    def rename(self, old_nick, new_nick):
        for channel, nicks in self.shared_data.items():
            if old_nick in nicks:
                self.logger.info(
                    "%s is not known as %s on %s",
                    old_nick, new_nick, channel
                )
                nicks.discard(old_nick)
                nicks.add(new_nick)

    def _shared_data_init(self):
        return defaultdict_with_key(self.query_names)
