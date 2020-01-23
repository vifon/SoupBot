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
    def parse(cls, msgstr):
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

        command = match.group('command')

        sender = match.group('sender')
        if sender:
            sender = IRCUser.parse(sender)
        else:
            sender = None

        args = match.group('args')
        if args:
            try:
                args, body = args.split(":", 1)
            except ValueError:
                body = None
            args = args.split()
        else:
            args = []
            body = None

        msg = cls(
            command,
            *args,
            sender=sender,
            body=body,
            raw=msgstr,
        )
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
