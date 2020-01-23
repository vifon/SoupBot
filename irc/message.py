from .user import IRCUser
import re

from typing import List, Optional, Iterator


class ParseError(Exception):
    pass


class IRCMessage:
    def __init__(
            self,
            command: str,
            *args: str,
            sender: IRCUser = None,
            body: str = None,
            raw: str = None
    ):
        self.command: str = command
        self.args = args
        self.sender = sender
        self.body = body
        self.raw = raw

    @classmethod
    def parse(cls, msgstr: str) -> 'IRCMessage':
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
        )
        return msg

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
