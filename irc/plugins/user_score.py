from irc.plugin import IRCCommandPlugin
import itertools
import re


class UserScore(IRCCommandPlugin):
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

    command_re = r'\.score (\w+)'

    def command(self, sender, channel, match, msg):
        scorable = match[1]
        score = self.score(scorable, channel)
        if score is None:
            body = f"{scorable} has no score."
        else:
            body = f"{scorable}'s score is {score}."
        self.client.send('PRIVMSG', channel, body=body)

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
