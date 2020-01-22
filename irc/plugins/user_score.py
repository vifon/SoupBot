from irc.plugin import IRCPlugin, IRCCommandPlugin
import itertools
import re


class UserScoreQueryMixin(IRCCommandPlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.commands.update({
            r'\.score +(\w+)': self.__show_score,
            r'\.scores(?: +([0-9]+))?$': self.__list_scores,
        })

    def __show_score(self, sender, channel, match, msg):
        scorable = match[1]
        score = self.score(scorable, channel)
        if score is None:
            body = f"{scorable} has no score."
        else:
            body = f"{scorable}'s score is {score}."
        self.client.send('PRIVMSG', channel, body=body)

    def __list_scores(self, sender, channel, match, msg):
        count = match[1] or 5
        c = self.db.cursor()
        c.execute(
            '''
            SELECT nick, score FROM score
            WHERE channel=?
            ORDER BY score DESC
            LIMIT ?
            ''',
            (channel, int(count))
        )
        for nick, score in c:
            self.client.send(
                'PRIVMSG', channel, body=f"{nick}'s score is {score}."
            )
        self.client.send(
            'PRIVMSG', channel, body="End of scores."
        )


class UserScoreEraseMixin(IRCCommandPlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.commands.update({
            r'\.descore +(\w+)': self.__erase_scores,
        })

    def __erase_scores(self, sender, channel, match, msg):
        if sender != self.config.get('admin'):
            return

        nick = match[1]
        c = self.db.cursor()
        c.execute(
            '''
            DELETE FROM score
            WHERE nick=? AND channel=?
            ''',
            (nick, channel,)
        )
        self.client.send(
            'PRIVMSG', channel, body=f"{nick}'s score erased."
        )


class UserScore(UserScoreQueryMixin, UserScoreEraseMixin, IRCPlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        c = self.db.cursor()
        c.execute(
            '''
            CREATE TABLE IF NOT EXISTS score
            (
                nick STRING,
                channel STRING,
                score INTEGER,
                UNIQUE(nick, channel)
            )
            '''
        )

    def react(self, msg):
        super().react(msg)

        if msg.command == 'PRIVMSG':
            channel = msg.args[0]
            if not channel.startswith("#"):
                return
            names = self.client.shared_data.NameTrack[channel]
            scorables = itertools.chain(self.config['scorables'], names)
            name_re = "|".join(map(re.escape, scorables))
            operators = ["++", "--"]
            operator_re = "|".join(map(re.escape, operators))
            separator_re = r'[^\w+-]'
            match = re.search(
                fr'''
                (?:{separator_re}|^)
                (?P<op1>{operator_re})
                (?P<nick1>{name_re})
                (?:{separator_re}|$)
                |
                (?:{separator_re}|^)
                (?P<nick2>{name_re})
                (?P<op2>{operator_re})
                (?:{separator_re}|$)
                ''',
                msg.body,
                flags=re.VERBOSE,
            )
            if match:
                nick = match.group('nick1') or match.group('nick2')
                op = match.group('op1') or match.group('op2')
                self.respond_score(msg.sender.nick, nick, channel, op)

    def respond_score(self, sender, nick, channel, operator):
        if sender == nick:
            self.client.send('PRIVMSG', channel, body=f"{sender}: No self-scoring!")
            return

        value_map = {
            '++': +1,
            '--': -1,
        }
        change = value_map[operator]
        self.change_score(nick, channel, change)
        score = self.score(nick, channel) or 0
        self.client.send('PRIVMSG', channel, body=f"{nick}'s score is now {score}.")

    def score(self, nick, channel):
        c = self.db.cursor()
        c.execute(
            '''
            SELECT score FROM score
            WHERE nick=? AND channel=?
            ''',
            (nick, channel)
        )
        value = c.fetchone()
        if value is None:
            return None
        else:
            return value[0]

    def change_score(self, nick, channel, change):
        c = self.db.cursor()
        c.execute(
            '''
            INSERT INTO score
            (nick, channel, score)
            VALUES (?, ?, ?)
            ON CONFLICT(nick, channel) DO
            UPDATE SET score = score + ?
            ''',
            (nick, channel, change, change)
        )
        self.db.commit()
