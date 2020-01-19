from .user import IRCUser
import re


class ParseError(Exception):
    pass


class IRCMessage:
    def __init__(self, command, *args, sender=None, body=None, raw=None):
        self.sender = sender
        self.command = command
        self.args = args
        self.body = body
        self.raw = raw

    @classmethod
    def unparsed(cls, msgstr):
        msg = cls(None, raw=msgstr)
        return msg

    @classmethod
    def parse(cls, msgstr):
        msg = cls(None, raw=msgstr)

        match = re.match(
            r'''
            (?:
              (?P<sender> :\S+)
            \s+)?
            (?P<command> [A-Z]+ | [0-9][0-9][0-9])
            (?: \s+
              (?P<args> .*)
            )?
            $
            ''',
            msgstr,
            flags=re.VERBOSE,
        )
        if match is None:
            raise ParseError(msgstr)

        sender = match.group('sender')
        if sender:
            msg.sender = IRCUser.parse(sender)
        else:
            msg.sender = None

        msg.command = match.group('command')

        args = match.group('args')
        if args:
            try:
                args, msg.body = args.split(":", 1)
            except ValueError:
                msg.body = None
            msg.args = args.split()
        else:
            msg.args = []
            msg.body = None

        return msg

    def __str__(self):
        def parts():
            if self.sender:
                yield str(self.sender)

            yield self.command

            yield from self.args

            if self.body:
                yield f":{self.body}"

        if self.raw and not self.command:
            return self.raw
        else:
            return " ".join(parts())
