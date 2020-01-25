from datetime import datetime
from irc.plugin import IRCPlugin
import re


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

    async def react(self, msg):
        if msg.command == 'PRIVMSG':
            channel = msg.args[0]
            users = self.users.get(channel, [])
            for user in map(re.escape, users):
                if re.search(fr"\b{user}\b", msg.body):
                    await self.store_maybe(msg, user)
        elif msg.command == 'JOIN':
            channel = msg.args[0]
            users = self.users.get(channel, [])
            if msg.sender.nick in users:
                await self.dump(msg.sender.nick, channel)

    async def store_maybe(self, msg, recipient):
        channel = msg.args[0]
        if not channel.startswith("#"):
            # It doesn't make sense to store messages sent directly to
            # the bot.  It was also a possible DoS attack.
            return
        try:
            names = await self.client.shared_data.NameTrack[channel]
        except AttributeError:
            # Fall back to manual querying if the NameTrack plugin
            # isn't loaded.
            await self.client.send('NAMES', channel)
            response = await self.queue.get()
            names = (nick.lstrip("@+") for nick in response.body.split())
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
            VALUES (?, ?, ?, ?, ?)
            ''',
            (datetime.now(), msg.sender.nick, recipient, channel, msg.body)
        )
        self.db.commit()
        self.logger.info("Storing %s for %s", repr(msg.body), recipient)

    async def dump(self, recipient, channel):
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
            SELECT time, sender, body FROM offline_msg
            WHERE channel=? AND recipient=?
            ORDER BY rowid
            ''',
            (channel, recipient)
        )
        for timestamp, sender, body in c:
            await self.client.send(
                'PRIVMSG',
                channel,
                body="{time} <{sender}> {body}".format(
                    time=timestamp.strftime("%H:%M"),
                    sender=sender,
                    body=body,
                )
            )

        c.execute(
            'DELETE FROM offline_msg WHERE channel=? AND recipient=?',
            (channel, recipient)
        )
        self.db.commit()
