from datetime import datetime
from irc.plugin import IRCPlugin
import logging
import re
import sqlite3
import time


class OfflineMessages(IRCPlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.users = self.config['users']
        c = self.db.cursor()
        c.execute(
            '''
            CREATE TABLE IF NOT EXISTS offline_msg
            (
                time TIMESTAMP,
                sender STRING,
                recipient STRING,
                channel STRING,
                body STRING
            )
            '''
        )

    def react(self, msg):
        if msg.command == 'PRIVMSG':
           for user in self.users:
               if re.search(f"\\b{user}\\b", msg.body):
                   self.store_maybe(msg, user)
        elif msg.command == 'JOIN':
            if msg.sender.nick in self.users:
                channel = msg.args[0]
                self.dump(msg.sender.nick, channel)

    def store_maybe(self, msg, recipient):
        channel = msg.args[0]
        if not channel.startswith("#"):
            # It doesn't make sense to store messages sent directly to
            # the bot.  It was also a possible DoS attack.
            return
        self.client.send('NAMES', channel)
        names = (nick.lstrip("@+") for nick in self.client.recv().body.split())
        if recipient in names:
            self.logger.info("Not saving, user present.")
        else:
            self.store(msg, recipient)

    def store(self, msg, recipient):
        channel = msg.args[0]
        c = self.db.cursor()
        c.execute(
            '''
            INSERT INTO offline_msg
            (time, sender, recipient, channel, body)
            VALUES
            (?, ?, ?, ?, ?)
            ''',
            (datetime.now(), msg.sender.nick, recipient, channel, msg.body)
        )
        self.db.commit()
        self.logger.info("Storing %s for %s", repr(msg.body), recipient)

    def dump(self, recipient, channel):
        c = self.db.cursor()

        c.execute(
            'SELECT COUNT(*) FROM offline_msg WHERE channel=? AND recipient=?',
            (channel, recipient)
        )
        count = c.fetchone()[0]
        if count == 0:
            self.logger.info("No messages for %s.", recipient)
            return
        self.logger.info("Dumping %d messages for %s.", count, recipient)

        c.execute(
            '''
            SELECT time, sender, channel, body FROM offline_msg
            WHERE channel=? AND recipient=?
            ORDER BY rowid
            ''',
            (channel, recipient)
        )
        for timestamp, sender, channel, body in c:
            self.client.send(
                'PRIVMSG',
                channel,
                body="{time} <{sender}> {body}".format(
                    time=timestamp.strftime("%H:%M"),
                    sender=sender,
                    body=body,
                )
            )
            time.sleep(2)

        c.execute(
            'DELETE FROM offline_msg WHERE channel=? AND recipient=?',
            (channel, recipient)
        )
        self.db.commit()
