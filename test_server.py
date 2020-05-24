#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s:%(name)s: %(message)s",
    datefmt="%H:%M:%S"
)

from irc import load_config, Socket  # noqa: F401
from irc.client import IRCClient     # noqa: F401
from irc.user import IRCUser         # noqa: F401
import asyncio                       # noqa: F401
import re                            # noqa: F401
import socket                        # noqa: F401
import unittest                      # noqa: F401

from tests.async_helpers import asynchronize, avait  # noqa: F401
from tests.conversation import (                     # noqa: F401
    ConversationDelay as Delay,
    ConversationNoResponse as NoResponse,
    ConversationRecv as Recv,
    ConversationSend as Send,
    ConversationSendRecv as SendRecv,
    ConversationSendIgnored as SendIgnored,
    conversation,
)

TEST_CONFIG = "test_config.yml"
conf = load_config(TEST_CONFIG)


class IRCTests(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logger.getChild(type(self).__name__)
        if 'log_level' in conf:
            self.logger.setLevel(conf['log_level'])

    @classmethod
    def setUpClass(cls):
        # Initialize the raw server socket…
        server_sock = socket.socket()
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        addr = (conf['server'], conf['port'])
        server_sock.bind(addr)
        print(f'Serving on {addr}')
        server_sock.listen()
        # …and wait for the client.
        cls.sock, _ = server_sock.accept()
        # We don't need any more clients.
        server_sock.shutdown(socket.SHUT_RDWR)
        server_sock.close()

        # Convert the plain socket into the asyncio one.
        cls.asock = Socket(*avait(asyncio.open_connection(sock=cls.sock)))

        # Initialize the IRC "client".
        cls.client = IRCClient(cls.asock, **conf['bot'])

        # Initialize some auxiliary constants.
        cls.bot = IRCUser(
            nick=cls.client.config['nick'],
            user=cls.client.config['nick'],
            host="localhost",
        )
        cls.admin = IRCUser(
            nick="testadmin",
            user="testadmin",
            host="localhost",
        )
        cls.host = "localhost"

    @classmethod
    def tearDownClass(cls):
        cls.sock.shutdown(socket.SHUT_RDWR)
        cls.sock.close()

    @conversation
    def test_01_greeting(self):
        return [
            Recv(f"USER {self.bot.nick} * * :{self.client.config['name']}"),
            Recv(f"NICK {self.bot.nick}"),
        ]

    @asynchronize
    async def test_02_nick_collision(self):
        await self.client._send(
            f":{self.host} 433 * {self.bot.nick}"
            " :Nickname is already in use.",
        )
        self.bot.nick += "_"
        new_nick_greeting = await self.client.recv()
        self.assertEqual(str(new_nick_greeting), f"NICK {self.bot.nick}")
        await self.client._send(
            f":{self.host} 001 {self.bot.nick}"
            " :Welcome to the Internet Relay Chat mock server"
            " {self.bot.nick}"
        )

    def send_names(self, channel, names):
        return [
            self.client._send(
                f":{self.host} 353 {self.bot.nick} @ {channel}"
                f" :{names}"
            ),
            self.client._send(
                f":{self.host} 366 {self.bot.nick} {channel}"
                " :End of /NAMES list."
            ),
        ]

    @asynchronize
    async def test_03_expect_joins(self):
        channels = {
            '#test-channel1': [self.bot.nick, self.admin.nick],
            '#test-channel2': [self.bot.nick],
        }

        for _ in channels:
            join = await self.client.recv()
            channel = re.match(r'JOIN (.+)', str(join)).group(1)
            self.assertIn(channel, channels)
            await self.client._send(f"{self.bot} JOIN {channel}")
            # The bot should ignore these lines for now.
            names = channels[channel]
            for coro in self.send_names(channel, " ".join(names)):
                await coro

        for _ in channels:
            names_request = await self.client.recv()
            channel = re.match(r'NAMES (.+)', str(names_request)).group(1)
            self.assertIn(channel, channels)
            self.assertEqual(str(names_request), f"NAMES {channel}")
            names = channels[channel]
            for coro in self.send_names(channel, " ".join(names)):
                await coro

    @conversation
    def test_04_ping(self):
        return [
            SendRecv(f"PING :{self.host}", f"PONG :{self.host}")
        ]

    @conversation
    def test_05_offline_msg(self):
        time_re = r'\d\d:\d\d'

        user = IRCUser(
            nick="offline_user",
            user="offline",
            host="localhost",
        )

        return [
            # User absent, bot should notify him when he's back.
            SendIgnored(f"{self.admin} PRIVMSG #test-channel1"
                        f" :{user.nick}: Ping me when you get online."),
            SendRecv(f"{user} JOIN #test-channel1",
                     f"PRIVMSG #test-channel1 :{time_re} <{self.admin.nick}>"
                     f" {user.nick}: Ping me when you get online\\.$",
                     regexp=True),

            # User present, no notification expected.
            SendIgnored(f"{self.admin} PRIVMSG #test-channel1"
                        f" :{user.nick}: Don't ping me, as you're online."),
            SendIgnored(f"{user} PART #test-channel1"),
            SendIgnored(f"{user} JOIN #test-channel1"),

            # User's offline again, let's make sure he'll get only the
            # latest message and the previous won't get resent.
            SendIgnored(f"{user} PART #test-channel1"),
            SendIgnored(f"{self.admin} PRIVMSG #test-channel1"
                        f" :{user.nick}: Ping me again!"),
            SendRecv(f"{user} JOIN #test-channel1",
                     f"PRIVMSG #test-channel1 :{time_re} <{self.admin.nick}>"
                     f" {user.nick}: Ping me again!$",
                     regexp=True),
            SendIgnored(f"{user} PART #test-channel1"),
        ]

    @conversation
    def test_06_offline_msg_dynamic(self):
        time_re = r'\d\d:\d\d'

        untracked = IRCUser(
            nick="untracked_user",
            user="untracked",
            host="localhost",
        )

        return [
            # User absent, but not on the list.
            SendIgnored(f"{self.admin} PRIVMSG #test-channel1"
                        f" :{untracked.nick}: Ping me when you get online."),
            SendIgnored(f"{untracked} JOIN #test-channel1"),
            SendIgnored(f"{untracked} PART #test-channel1"),

            # Add the user to the list with managed offline messages.
            SendRecv(f"{self.admin} PRIVMSG #test-channel1"
                     f" :.offline_add {untracked.nick}",
                     f"PRIVMSG #test-channel1 :Understood,"
                     f" I'll keep the messages for {untracked.nick}\\.$",
                     regexp=True),

            # User absent, and now on the list.
            SendIgnored(f"{self.admin} PRIVMSG #test-channel1"
                        f" :{untracked.nick}: Ping me when you get online."),
            SendRecv(f"{untracked} JOIN #test-channel1",
                     f"PRIVMSG #test-channel1 :{time_re} <{self.admin.nick}>"
                     f" {untracked.nick}: Ping me when you get online\\.$",
                     regexp=True),
            SendIgnored(f"{untracked} PART #test-channel1"),

            # Remove the user from the list with managed offline messages.
            SendRecv(f"{self.admin} PRIVMSG #test-channel1"
                     f" :.offline_del {untracked.nick}",
                     f"PRIVMSG #test-channel1 :Understood,"
                     f" I'll stop keeping messages for {untracked.nick}."),

            # User absent, and once again not on the list.
            SendIgnored(f"{self.admin} PRIVMSG #test-channel1"
                        f" :{untracked.nick}: Ping me when you get online."),
            SendIgnored(f"{untracked} JOIN #test-channel1"),
            SendIgnored(f"{untracked} PART #test-channel1"),
        ]

    @conversation
    def test_07_rating(self):
        no_admin = IRCUser(
            nick='someguy',
            user='nobody',
            host="localhost",
        )

        return [
            SendRecv(f"{self.admin} PRIVMSG #test-channel1 :.score bacon",
                     "PRIVMSG #test-channel1 :bacon has no score."),

            SendRecv(f"{self.admin} PRIVMSG #test-channel1 :.scores",
                     "PRIVMSG #test-channel1 :End of scores."),

            SendRecv(f"{self.admin} PRIVMSG #test-channel1"
                     " :I like bacon++.",
                     "PRIVMSG #test-channel1 :bacon's score is now 1."),

            Send(f"{self.admin} PRIVMSG #test-channel1 :.scores"),
            Recv("PRIVMSG #test-channel1 :bacon's score is 1."),
            Recv("PRIVMSG #test-channel1 :End of scores."),

            SendRecv(f"{self.admin} PRIVMSG #test-channel1"
                     " :++bacon is great.",
                     "PRIVMSG #test-channel1 :bacon's score is now 2."),

            SendRecv(f"{self.admin} PRIVMSG #test-channel1"
                     f" :{self.bot.nick}++",
                     "PRIVMSG #test-channel1"
                     f" :{self.bot.nick}'s score is now 1."),

            Send(f"{self.admin} PRIVMSG #test-channel1 :.scores"),
            Recv("PRIVMSG #test-channel1 :bacon's score is 2."),
            Recv(f"PRIVMSG #test-channel1 :{self.bot.nick}'s score is 1."),
            Recv("PRIVMSG #test-channel1 :End of scores."),

            SendRecv(f"{self.admin} PRIVMSG #test-channel1"
                     f" :{self.bot.nick}++",
                     "PRIVMSG #test-channel1"
                     f" :{self.bot.nick}'s score is now 2."),

            SendRecv(f"{self.admin} PRIVMSG #test-channel1"
                     f" :{self.bot.nick}++",
                     "PRIVMSG #test-channel1"
                     f" :{self.bot.nick}'s score is now 3."),

            Send(f"{self.admin} PRIVMSG #test-channel1 :.scores"),
            Recv(f"PRIVMSG #test-channel1 :{self.bot.nick}'s score is 3."),
            Recv("PRIVMSG #test-channel1 :bacon's score is 2."),
            Recv("PRIVMSG #test-channel1 :End of scores."),

            Send(f"{self.admin} PRIVMSG #test-channel1 :.scores -5"),
            Recv("PRIVMSG #test-channel1 :bacon's score is 2."),
            Recv(f"PRIVMSG #test-channel1 :{self.bot.nick}'s score is 3."),
            Recv("PRIVMSG #test-channel1 :End of scores."),

            SendRecv(f"{self.admin} PRIVMSG #test-channel1"
                     f" :.descore {self.bot.nick}",
                     "PRIVMSG #test-channel1"
                     f" :{self.bot.nick}'s score erased."),

            Send(f"{self.admin} PRIVMSG #test-channel1 :.scores"),
            Recv("PRIVMSG #test-channel1 :bacon's score is 2."),
            Recv("PRIVMSG #test-channel1 :End of scores."),

            SendRecv(f"{self.admin} PRIVMSG #test-channel1 :bacon++",
                     "PRIVMSG #test-channel1 :bacon's score is now 3."),
            SendRecv(f"{self.admin} PRIVMSG #test-channel1"
                     " :Screw bacon--",
                     "PRIVMSG #test-channel1 :bacon's score is now 2."),
            SendRecv(f"{self.admin} PRIVMSG #test-channel1 :++bacon",
                     "PRIVMSG #test-channel1 :bacon's score is now 3."),

            SendRecv(f"{self.admin} PRIVMSG #test-channel1 :.score bacon",
                     "PRIVMSG #test-channel1 :bacon's score is 3."),
            SendRecv(f"{no_admin} PRIVMSG #test-channel1 :.score bacon",
                     "PRIVMSG #test-channel1 :bacon's score is 3."),

            SendRecv(f"{self.admin} PRIVMSG #test-channel1 :--bacon",
                     "PRIVMSG #test-channel1 :bacon's score is now 2."),

            SendIgnored(f"{no_admin} PRIVMSG #test-channel1"
                        " :.descore bacon"),
            SendRecv(f"{self.admin} PRIVMSG #test-channel1 :.score bacon",
                     "PRIVMSG #test-channel1 :bacon's score is 2."),

            SendRecv(f"{self.admin} PRIVMSG #test-channel2 :.score bacon",
                     "PRIVMSG #test-channel2 :bacon has no score."),

            Send(f"{self.admin} PRIVMSG #test-channel2 :.scores"),
            Recv("PRIVMSG #test-channel2 :End of scores."),

            SendIgnored(f"{self.admin} PRIVMSG {self.bot.nick} :bacon++"),

            Send(f"{self.admin} PRIVMSG #test-channel1 :.scores"),
            Recv("PRIVMSG #test-channel1 :bacon's score is 2."),
            Recv("PRIVMSG #test-channel1 :End of scores."),

            Send(f"{self.admin} PRIVMSG #test-channel1 :.scores 11"),
            Recv("PRIVMSG #test-channel1 :bacon's score is 2."),
            Recv("PRIVMSG #test-channel1 :End of scores."),

            Send(f"{no_admin} PRIVMSG #test-channel1 :.scores"),
            Recv("PRIVMSG #test-channel1 :bacon's score is 2."),
            Recv("PRIVMSG #test-channel1 :End of scores."),

            Send(f"{no_admin} PRIVMSG #test-channel1 :.scores 10"),
            Recv("PRIVMSG #test-channel1 :bacon's score is 2."),
            Recv("PRIVMSG #test-channel1 :End of scores."),

            SendIgnored(f"{no_admin} PRIVMSG #test-channel1"
                        " :.descore bacon"),

            SendRecv(f"{no_admin} PRIVMSG #test-channel1 :.scores 11",
                     f"PRIVMSG #test-channel1 :{no_admin.nick}:"
                     " Too many scores requested."),

            SendRecv(f"{self.admin} PRIVMSG #test-channel1"
                     " :.descore bacon",
                     f"PRIVMSG #test-channel1 :bacon's score erased."),
            SendRecv(f"{self.admin} PRIVMSG #test-channel1 :.score bacon",
                     "PRIVMSG #test-channel1 :bacon has no score."),

            SendRecv(f"{self.admin} PRIVMSG #test-channel1 :.scores",
                     "PRIVMSG #test-channel1 :End of scores."),
            SendRecv(f"{no_admin} PRIVMSG #test-channel1 :.scores 10",
                     "PRIVMSG #test-channel1 :End of scores."),
            SendRecv(f"{no_admin} PRIVMSG #test-channel1 :.scores 11",
                     f"PRIVMSG #test-channel1 :{no_admin.nick}:"
                     " Too many scores requested."),

            SendRecv(f"{self.admin} PRIVMSG #test-channel1"
                     f" :{self.admin.nick}++",
                     "PRIVMSG #test-channel1 "
                     f":{self.admin.nick}: No self-scoring!"),
        ]

    @conversation
    def test_08_commandline(self):
        no_admin = IRCUser(
            nick='someguy',
            user='nobody',
            host="localhost",
        )

        return [
            SendIgnored(f"{no_admin} PRIVMSG {self.bot.nick} :.raw"
                        " PRIVMSG #test-channel1 test"),
            SendRecv(f"{self.admin} PRIVMSG {self.bot.nick} :.raw"
                     " PRIVMSG #test-channel1 test",
                     "PRIVMSG #test-channel1 test"),
            SendIgnored(f"{self.admin} PRIVMSG #test-channel1 :.raw"
                        " PRIVMSG #test-channel1 test"),
            SendRecv(f"{self.admin} PRIVMSG {self.bot.nick} :.part"
                     " #test-channel2",
                     "PART #test-channel2"),
            SendRecv(f"{self.admin} PRIVMSG {self.bot.nick} :.join"
                     " #test-channel2",
                     "JOIN #test-channel2"),
            SendIgnored(f"{no_admin} PRIVMSG {self.bot.nick} :.part"
                        " #test-channel2"),
        ]

    @conversation
    def test_09_abuse_detection(self):
        return [
            SendRecv(f"{self.admin} PRIVMSG {self.bot.nick} :.raw"
                     " PRIVMSG #test-channel1 :A short message.",
                     "PRIVMSG #test-channel1 :A short message."),
            SendIgnored(f"{self.admin} PRIVMSG {self.bot.nick} :.raw"
                        f" PRIVMSG #test-channel1 :A{' long' * 100} message."),
            SendIgnored(f"{self.admin} PRIVMSG {self.bot.nick} :.raw"
                        " PRIVMSG #test-channel1"
                        " :A short but malicious \0 message."),
        ]

    @conversation
    def test_10_http_preview(self):
        url = "http://127.0.0.1:8080"

        return [
            SendRecv(f"{self.admin} PRIVMSG #test-channel1"
                     f" :{url}/simple-webpage",
                     "PRIVMSG #test-channel1"
                     f" :{self.admin.nick}: Simple Webpage"),
            SendIgnored(f"{self.admin} PRIVMSG #test-channel1"
                        f" :{url}/malicious-webpage"),
            SendIgnored(f"{self.admin} PRIVMSG #test-channel1"
                        f" :{url}/long-webpage"),
            SendRecv(f"{self.admin} PRIVMSG #test-channel1"
                     f" :{url}/slow-webpage",
                     "PRIVMSG #test-channel1"
                     f" :{self.admin.nick}: Preview timed out."),
            SendIgnored(f"{self.admin} PRIVMSG #test-channel1"
                        f" :{url}/redirecting-webpage"),
            SendIgnored(f"{self.admin} PRIVMSG #test-channel1"
                        f" :{url}/redirecting-webpage-mutual"),
            Send(f"{self.admin} PRIVMSG #test-channel1"
                 f" :{url}/simple-webpage and {url}/another-webpage"),
            Recv("PRIVMSG #test-channel1"
                 f" :{self.admin.nick}: Simple Webpage"),
            Recv("PRIVMSG #test-channel1"
                 f" :{self.admin.nick}: Another Webpage"),
        ]

    @conversation
    def test_99_expect_silence(self):
        """All the previous tests should already expect the whole output
        generated by the bot.

        """
        return [
            NoResponse(timeout=1),
        ]


if __name__ == '__main__':
    unittest.main()
