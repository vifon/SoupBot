#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s:%(name)s: %(message)s",
    datefmt="%H:%M:%S"
)

from bot import load_config, Socket
from irc.client import IRCClient
from irc.user import IRCUser
import asyncio
import re
import socket
import unittest

TEST_CONFIG = "test_config.yml"
conf = load_config(TEST_CONFIG)


class IRCTestServer(IRCClient):
    async def sendmsg(self, msg):
        await super().sendmsg(msg, delay=0)


def avait(coro):
    loop = asyncio.get_event_loop()
    task = asyncio.ensure_future(coro)
    return loop.run_until_complete(task)


def asynchronize(coro):
    def sync_fun(*args, **kwargs):
        return avait(coro(*args, **kwargs))
    return sync_fun


def conversation(test):
    @asynchronize
    async def real_test(self):
        exchange = test(self)
        logger = self.logger.getChild(f"{test.__name__}")
        for msg, expected_resp in exchange:
            if msg:
                logger.debug("Sending %s", msg)
                await self.client.sendmsg(msg)
            if expected_resp:
                logger.debug("Expecting %s", expected_resp)
                received_resp = await self.client.recv()
                logger.debug("Received %s", received_resp)
                self.assertEqual(str(received_resp), expected_resp)
    return real_test


class IRCTests(unittest.TestCase):
    IDLE_TIME = 3

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logger.getChild(type(self).__name__)

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
            (None, f"USER {self.bot.nick} * * :{self.client.config['name']}"),
            (None, f"NICK {self.bot.nick}"),
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
            (f"PING :{self.host}", f"PONG :{self.host}")
        ]


if __name__ == '__main__':
    unittest.main()
