from .user import IRCUser
import re
import unicodedata

from typing import List, Optional, Iterator


class ParseError(Exception):
    pass


class IRCSecurityError(Exception):
    pass


class InjectionError(IRCSecurityError):
    pass


class ExcessiveLengthError(IRCSecurityError):
    pass


class IRCMessage:
    def __init__(
            self,
            command: str,
            *args: str,
            sender: IRCUser = None,
            body: str = None,
            raw: str = None,
            allow_unsafe: bool = False,
    ):
        self.command: str = command
        self.args = args
        self.sender = sender
        self.body = body
        self.raw = raw

        if not allow_unsafe:
            self._sanitize()

    def _sanitize(self):
        def isprintable(string):
            return all(not unicodedata.category(c) == 'Cc' for c in string)

        if self.body is not None:
            if not isprintable(self.body):
                raise InjectionError()
        for arg in self.args:
            if not isprintable(arg):
                raise InjectionError()

        if len(str(self)) > 512:
            raise ExcessiveLengthError()

    @classmethod
    def parse(cls, msgstr: str, allow_unsafe: bool = False) -> 'IRCMessage':
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

        sender: Optional[IRCUser] = None
        sender_str = match.group('sender')
        if sender_str:
            sender = IRCUser.parse(sender_str)

        args: List[str] = []
        body: Optional[str] = None
        args_str = match.group('args')
        if args_str:
            try:
                args_str, body = args_str.split(":", 1)
            except ValueError:
                pass
            args = args_str.split()

        msg = cls(
            command,
            *args,
            sender=sender,
            body=body,
            raw=msgstr,
            allow_unsafe=allow_unsafe,
        )
        return msg

    def __repr__(self):
        return f'<{__name__}.{type(self).__name__} "{str(self)}">'

    def __str__(self) -> str:
        def parts() -> Iterator[str]:
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
