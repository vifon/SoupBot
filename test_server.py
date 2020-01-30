#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s:%(name)s: %(message)s",
    datefmt="%H:%M:%S"
)

from bot import load_config, Socket  # noqa: F401
from datetime import datetime        # noqa: F401
from irc.client import IRCClient     # noqa: F401
from irc.user import IRCUser         # noqa: F401
import asyncio                       # noqa: F401
import re                            # noqa: F401
import socket                        # noqa: F401
import unittest                      # noqa: F401

from lib.async import asynchronize, avait  # noqa: F401
from lib.test.conversation import (        # noqa: F401
    ConversationSend as Send,
    ConversationRecv as Recv,
    ConversationSendRecv as SendRecv,
    ConversationDelay as Delay,
    conversation,
)

TEST_CONFIG = "test_config.yml"
conf = load_config(TEST_CONFIG)


class IRCTestServer(IRCClient):
    async def sendmsg(self, msg):
        await super().sendmsg(msg, delay=0)


class IRCTests(unittest.TestCase):
    IDLE_TIME = 3

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
        cls.client = IRCTestServer(cls.asock, **conf['bot'])

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
        await self.client.sendmsg(
            f":{self.host} 433 * {self.bot.nick}"
            " :Nickname is already in use.",
        )
        self.bot.nick += "_"
        new_nick_greeting = await self.client.recv()
        self.assertEqual(str(new_nick_greeting), f"NICK {self.bot.nick}")
        await self.client.sendmsg(
            f":{self.host} 001 {self.bot.nick}"
            " :Welcome to the Internet Relay Chat mock server"
            " {self.bot.nick}"
        )

    def send_names(self, channel, names):
        return [
            self.client.sendmsg(
                f":{self.host} 353 {self.bot.nick} @ {channel}"
                f" :{names}"
            ),
            self.client.sendmsg(
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
            await self.client.sendmsg(f"{str(self.bot)} JOIN {channel}")
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
        time = datetime.now().strftime("%H:%M")
        delay = 0.2
        return [
            # User absent, bot should notify him when he's back.
            Send(f"{str(self.admin)} PRIVMSG #test-channel1"
                 " :offline_user: Ping me when you get online."),
            Delay(delay),
            SendRecv(":offline_user!offline@localhost JOIN #test-channel1",
                     f"PRIVMSG #test-channel1 :{time} <{self.admin.nick}>"
                     " offline_user: Ping me when you get online."),
            Delay(delay),

            # User present, no notification expected.
            Send(f"{str(self.admin)} PRIVMSG #test-channel1"
                 " :offline_user: Don't ping me, as you're online."),
            Delay(delay),
            Send(":offline_user!offline@localhost PART #test-channel1"),
            Delay(delay),
            Send(":offline_user!offline@localhost JOIN #test-channel1"),
            Delay(delay),

            # User's offline again, let's make sure he'll get only the
            # latest message and the previous won't get resent.
            Send(":offline_user!offline@localhost PART #test-channel1"),
            Delay(delay),
            Send(f"{str(self.admin)} PRIVMSG #test-channel1"
                 " :offline_user: Ping me again!"),
            Delay(delay),
            SendRecv(":offline_user!offline@localhost JOIN #test-channel1",
                     f"PRIVMSG #test-channel1 :{time} <{self.admin.nick}>"
                     " offline_user: Ping me again!"),
            Delay(delay),
            Send(":offline_user!offline@localhost PART #test-channel1"),
        ]

    def test_99_expect_silence(self):
        """All the previous tests should already expect the whole output
        generated by the bot.

        """
        self.assertRaises(
            asyncio.TimeoutError,
            lambda: avait(asyncio.wait_for(self.client.recv(), timeout=0.5)),
        )


if __name__ == '__main__':
    unittest.main()
