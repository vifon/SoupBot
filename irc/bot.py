from .client import IRCClient
from .plugin import IRCPlugin
import logging
import re
import time
logger = logging.getLogger(__name__)


class OfflineMessages(IRCPlugin):
    def __init__(self, user, *args, **kwargs):
        self.user = re.escape(user)
        super().__init__(*args, **kwargs)
        self.messages = []

    def react(self, msg):
        if msg.command == 'PRIVMSG' \
           and re.search(f"\\b{self.user}\\b", msg.body):
            self.client.send('NAMES', msg.args[0])
            names = self.client.recv().body.split()
            if self.user in names:
                logger.info("Not saving, user present.")
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
        logger.info("Storing: %s", stored)

    def dump(self):
        logger.info("Dumping %d messages.", len(self.messages))
        for message in self.messages:
            self.client.send(
                'PRIVMSG',
                message['channel'],
                body="<{sender}> {body}".format(**message)
            )
            time.sleep(2)


class MessageBot(IRCClient):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        self.plugins.append(OfflineMessages(user, self))
