from irc.plugin import IRCPlugin
import logging
import re
import time


class OfflineMessages(IRCPlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = self.config['user']
        self.messages = []

    def react(self, msg):
        if msg.command == 'PRIVMSG' \
           and re.search(f"\\b{self.user}\\b", msg.body):
            self.client.send('NAMES', msg.args[0])
            names = self.client.recv().body.split()
            if self.user in names:
                self.logger.info("Not saving, user present.")
            else:
                self.store(msg)
        elif msg.command == 'JOIN' \
             and msg.sender.nick.startswith(self.user):
            self.dump()
            self.messages = []

    def store(self, msg):
        stored = {
            'sender': msg.sender.nick,
            'channel': msg.args[0],
            'body': msg.body,
        }
        self.messages.append(stored)
        self.logger.info("Storing: %s", stored)

    def dump(self):
        self.logger.info("Dumping %d messages.", len(self.messages))
        for message in self.messages:
            self.client.send(
                'PRIVMSG',
                message['channel'],
                body="<{sender}> {body}".format(**message)
            )
            time.sleep(2)
