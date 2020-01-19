from irc.plugin import IRCPlugin
import logging
import re
import sqlite3
import time


class OfflineMessages(IRCPlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = self.config['user']
        c = self.client.db.cursor()
        c.execute(
            '''
            CREATE TABLE IF NOT EXISTS offline_msg
            (
                sender STRING,
                channel STRING,
                body STRING
            )
            '''
        )

    def react(self, msg):
        if msg.command == 'PRIVMSG' \
           and re.search(f"\\b{self.user}\\b", msg.body):
            self.store_maybe(msg)
        elif msg.command == 'JOIN' \
             and msg.sender.nick.startswith(self.user):
            channel = msg.args[0]
            self.dump(channel)

    def store_maybe(self, msg):
        channel = msg.args[0]
        if not channel.startswith("#"):
            # It doesn't make sense to store messages sent directly to
            # the bot.  It was also a possible DoS attack.
            return
        self.client.send('NAMES', channel)
        names = self.client.recv().body.split()
        if self.user in names:
            self.logger.info("Not saving, user present.")
        else:
            self.store(msg)

    def store(self, msg):
        channel = msg.args[0]
        c = self.client.db.cursor()
        c.execute(
            '''
            INSERT INTO offline_msg (sender, channel, body) VALUES (?, ?, ?)
            ''',
            (msg.sender.nick, channel, msg.body)
        )
        self.logger.info("Storing: %s", repr(msg.body))

    def dump(self, channel):
        c = self.client.db.cursor()
        c.execute(
            '''
            SELECT sender, channel, body FROM offline_msg
            WHERE channel=?
            ORDER BY rowid
            '''
            (channel,)
        )
        if c.rowcount <= 0:
            return
        self.logger.info("Dumping %d messages.", c.rowcount)
        for sender, channel, body in c:
            self.client.send(
                'PRIVMSG',
                channel,
                body="<{sender}> {body}".format(
                    sender=sender,
                    body=body,
                )
            )
            time.sleep(2)
        c.execute('DELETE FROM offline_msg WHERE channel=?', (channel,))
