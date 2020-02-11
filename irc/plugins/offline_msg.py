from collections import defaultdict
from datetime import datetime
from irc.message import IRCMessage
from irc.plugin import (
    IRCCommandPlugin,
    IRCPlugin,
    NotAuthorizedError,
    authenticated,
)
import itertools
import re


class OfflineMessagesDynamic(IRCCommandPlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.commands.update({
            r'\.offline_add +(\w+)$': self.__add,
            r'\.offline_del +(\w+)$': self.__del,
        })

    def auth(self, sender, channel):
        super().auth(sender, channel)
        if not channel.startswith("#"):
            raise NotAuthorizedError(sender, channel)

    @authenticated
    async def __add(self, sender, channel, match, msg):
        self.shared_data[channel].add(match[1])
        self.client.send(IRCMessage(
            'PRIVMSG', channel,
            body=f"Understood, I'll keep the messages for {match[1]}."
        ))
        self.logger.debug(
            "Currently saving messages for: %s", dict(self.shared_data)
        )
        return True

    @authenticated
    async def __del(self, sender, channel, match, msg):
        self.shared_data[channel].discard(match[1])
        self.client.send(IRCMessage(
            'PRIVMSG', channel,
            body=f"Understood, I'll stop keeping messages for {match[1]}."
        ))
        return True


class OfflineMessages(OfflineMessagesDynamic, IRCPlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._users = self.config['users']
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
        if await super().react(msg):
            return

        if msg.command == 'PRIVMSG':
            channel = msg.args[0]
            users = self.users(channel)
            for user in map(re.escape, users):
                if re.search(fr"\b{user}\b", msg.body):
                    await self.store_maybe(msg, user)
        elif msg.command == 'JOIN':
            channel = msg.args[0]
            users = self.users(channel)
            if msg.sender.nick in users:
                await self.dump(msg.sender.nick, channel)

    def users(self, channel):
        return itertools.chain(
            self._users.get(channel, []),
            self.shared_data.get(channel, []),
        )

    async def store_maybe(self, msg, recipient):
        channel = msg.args[0]
        if not channel.startswith("#"):
            # It doesn't make sense to store messages sent directly to
            # the bot.  It was also a possible DoS attack.
            return
        names = await self.client.shared_data.NameTrack[channel]
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
            self.client.send(IRCMessage(
                'PRIVMSG',
                channel,
                body="{time} <{sender}> {body}".format(
                    time=timestamp.strftime("%H:%M"),
                    sender=sender,
                    body=body,
                )
            ))

        c.execute(
            'DELETE FROM offline_msg WHERE channel=? AND recipient=?',
            (channel, recipient)
        )
        self.db.commit()

    def _shared_data_init(self):
        return defaultdict(set)
