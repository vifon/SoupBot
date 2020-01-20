from irc.plugin import IRCPlugin
import re


class UserScore(IRCPlugin):
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

    def match(self, msg):
        if msg.command == 'PRIVMSG':
            channel = msg.args[0]
            if not channel.startswith("#"):
                return
            names = self.client.shared_data.NameTrack[channel]
            name_re = "|".join(map(re.escape, names))
            operators = ["++", "--"]
            operator_re = "|".join(map(re.escape, operators))
            match = re.search(
                fr'''
                (?:\W|^)
                (?P<pre>{operator_re})?
                (?P<nick>{name_re})
                (?P<post>{operator_re})?
                (?:\W|$)
                ''',
                msg.body,
                flags=re.VERBOSE,
            )
            if match:
                if bool(match.group('pre')) == bool(match.group('post')):
                    # We only want one of the operators, not both or none.
                    return
                operator = match.group('pre') or match.group('post')
                return match.group('nick'), channel, operator

    def respond(self, data):
        nick, channel, operator = data
        value_map = {
            '++': +1,
            '--': -1,
        }
        change = value_map[operator]
        self.change_score(nick, channel, change)
        score = self.score(nick, channel)
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
            return 0
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
