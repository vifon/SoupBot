#!/usr/bin/env python3

import logging.config
logging.config.fileConfig("tests/logging.conf")

from irc import load_config, Socket  # noqa: F401
from irc.user import IRCUser         # noqa: F401

import asyncio                       # noqa: F401
import pytest                        # noqa: F401
import re                            # noqa: F401
import socket                        # noqa: F401

from tests.conversation import (                     # noqa: F401
    IRCTestClient,
    ConversationDelay as Delay,
    ConversationNoResponse as NoResponse,
    ConversationRecv as Recv,
    ConversationSend as Send,
    ConversationSendRecv as SendRecv,
    ConversationSendIgnored as SendIgnored,
)


@pytest.fixture(scope="session")
def config():
    return load_config("test_config.yml")


@pytest.fixture
def admin():
    return IRCUser(
        nick="testadmin",
        user="testadmin",
        host="localhost",
    )


@pytest.fixture(scope="class")
def bot(host, client):
    return IRCUser(
        nick=client.config['nick'],
        user=client.config['nick'],
        host=host,
    )


@pytest.fixture(scope="class")
def host():
    return "localhost"


@pytest.fixture(scope="class")
async def client(config, event_loop):
    server_sock = socket.socket()
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    addr = (config['server'], config['port'])
    server_sock.bind(addr)
    print(f'Serving on {addr}')
    server_sock.listen()
    # …and wait for the client.
    sock, _ = server_sock.accept()
    # We don't need any more clients.
    server_sock.shutdown(socket.SHUT_RDWR)
    server_sock.close()

    # Convert the plain socket into the asyncio one.
    asock = Socket(*await(asyncio.open_connection(sock=sock)))

    # Initialize the IRC "client".
    yield IRCTestClient(asock, **config['bot'])

    # Cleanup after the client is finished.
    sock.shutdown(socket.SHUT_RDWR)
    sock.close()


class TestIRC:
    @pytest.mark.asyncio
    async def test_01_greeting(self, client, config, bot):
        await client.conversation([
            Recv(f"USER {bot.nick} * * :{client.config['name']}"),
            Recv(f"NICK {bot.nick}"),
        ])

    @pytest.mark.asyncio
    async def test_02_nick_collision(self, client, bot, host):
        await client._send(
            f":{host} 433 * {bot.nick}"
            " :Nickname is already in use.",
        )
        bot.nick += "_"
        new_nick_greeting = await client.recv()
        assert str(new_nick_greeting) == f"NICK {bot.nick}"
        await client._send(
            f":{host} 001 {bot.nick}"
            " :Welcome to the Internet Relay Chat mock server"
            " {bot.nick}"
        )

    @pytest.mark.asyncio
    async def test_03_expect_joins(self, client, bot, host, admin):
        def send_names(channel, names):
                return [
                    client._send(
                        f":{host} 353 {bot.nick} @ {channel}"
                        f" :{names}"
                    ),
                    client._send(
                        f":{host} 366 {bot.nick} {channel}"
                        " :End of /NAMES list."
                    ),
                ]

        channels = {
            '#test-channel1': [bot.nick, admin.nick],
            '#test-channel2': [bot.nick],
        }

        for _ in channels:
            join = await client.recv()
            channel = re.match(r'JOIN (.+)', str(join)).group(1)
            assert channel in channels
            await client._send(f"{bot} JOIN {channel}")
            # The bot should ignore these lines for now.
            names = channels[channel]
            for coro in send_names(channel, " ".join(names)):
                await coro

        for _ in channels:
            names_request = await client.recv()
            channel = re.match(r'NAMES (.+)', str(names_request)).group(1)
            assert channel in channels
            assert str(names_request) == f"NAMES {channel}"
            names = channels[channel]
            for coro in send_names(channel, " ".join(names)):
                await coro

    @pytest.mark.asyncio
    async def test_04_ping(self, client, host):
        await client.conversation([
            SendRecv(f"PING :{host}", f"PONG :{host}")
        ])

    @pytest.mark.asyncio
    async def test_05_offline_msg(self, client, admin):
        time_re = r'\d\d:\d\d'

        user = IRCUser(
            nick="offline_user",
            user="offline",
            host="localhost",
        )

        await client.conversation([
            # User absent, bot should notify him when he's back.
            SendIgnored(f"{admin} PRIVMSG #test-channel1"
                        f" :{user.nick}: Ping me when you get online."),
            SendRecv(f"{user} JOIN #test-channel1",
                     f"PRIVMSG #test-channel1 :{time_re} <{admin.nick}>"
                     f" {user.nick}: Ping me when you get online\\.$",
                     regexp=True),

            # User present, no notification expected.
            SendIgnored(f"{admin} PRIVMSG #test-channel1"
                        f" :{user.nick}: Don't ping me, as you're online."),
            SendIgnored(f"{user} PART #test-channel1"),
            SendIgnored(f"{user} JOIN #test-channel1"),

            # User's offline again, let's make sure he'll get only the
            # latest message and the previous won't get resent.
            SendIgnored(f"{user} PART #test-channel1"),
            SendIgnored(f"{admin} PRIVMSG #test-channel1"
                        f" :{user.nick}: Ping me again!"),
            SendRecv(f"{user} JOIN #test-channel1",
                     f"PRIVMSG #test-channel1 :{time_re} <{admin.nick}>"
                     f" {user.nick}: Ping me again!$",
                     regexp=True),
            SendIgnored(f"{user} PART #test-channel1"),
        ])

    @pytest.mark.asyncio
    async def test_06_offline_msg_dynamic(self, client, admin):
        time_re = r'\d\d:\d\d'

        untracked = IRCUser(
            nick="untracked_user",
            user="untracked",
            host="localhost",
        )

        await client.conversation([
            # User absent, but not on the list.
            SendIgnored(f"{admin} PRIVMSG #test-channel1"
                        f" :{untracked.nick}: Ping me when you get online."),
            SendIgnored(f"{untracked} JOIN #test-channel1"),
            SendIgnored(f"{untracked} PART #test-channel1"),

            # Add the user to the list with managed offline messages.
            SendRecv(f"{admin} PRIVMSG #test-channel1"
                     f" :.offline_add {untracked.nick}",
                     f"PRIVMSG #test-channel1 :Understood,"
                     f" I'll keep the messages for {untracked.nick}\\.$",
                     regexp=True),

            # User absent, and now on the list.
            SendIgnored(f"{admin} PRIVMSG #test-channel1"
                        f" :{untracked.nick}: Ping me when you get online."),
            SendRecv(f"{untracked} JOIN #test-channel1",
                     f"PRIVMSG #test-channel1 :{time_re} <{admin.nick}>"
                     f" {untracked.nick}: Ping me when you get online\\.$",
                     regexp=True),
            SendIgnored(f"{untracked} PART #test-channel1"),

            # Remove the user from the list with managed offline messages.
            SendRecv(f"{admin} PRIVMSG #test-channel1"
                     f" :.offline_del {untracked.nick}",
                     f"PRIVMSG #test-channel1 :Understood,"
                     f" I'll stop keeping messages for {untracked.nick}."),

            # User absent, and once again not on the list.
            SendIgnored(f"{admin} PRIVMSG #test-channel1"
                        f" :{untracked.nick}: Ping me when you get online."),
            SendIgnored(f"{untracked} JOIN #test-channel1"),
            SendIgnored(f"{untracked} PART #test-channel1"),
        ])

    @pytest.mark.asyncio
    async def test_07_rating(self, client, bot, admin):
        no_admin = IRCUser(
            nick='someguy',
            user='nobody',
            host="localhost",
        )

        await client.conversation([
            SendRecv(f"{admin} PRIVMSG #test-channel1 :.score bacon",
                     "PRIVMSG #test-channel1 :bacon has no score."),

            SendRecv(f"{admin} PRIVMSG #test-channel1 :.scores",
                     "PRIVMSG #test-channel1 :End of scores."),

            SendRecv(f"{admin} PRIVMSG #test-channel1"
                     " :I like bacon++.",
                     "PRIVMSG #test-channel1 :bacon's score is now 1."),

            Send(f"{admin} PRIVMSG #test-channel1 :.scores"),
            Recv("PRIVMSG #test-channel1 :bacon's score is 1."),
            Recv("PRIVMSG #test-channel1 :End of scores."),

            SendRecv(f"{admin} PRIVMSG #test-channel1"
                     " :++bacon is great.",
                     "PRIVMSG #test-channel1 :bacon's score is now 2."),

            SendRecv(f"{admin} PRIVMSG #test-channel1"
                     f" :{bot.nick}++",
                     "PRIVMSG #test-channel1"
                     f" :{bot.nick}'s score is now 1."),

            Send(f"{admin} PRIVMSG #test-channel1 :.scores"),
            Recv("PRIVMSG #test-channel1 :bacon's score is 2."),
            Recv(f"PRIVMSG #test-channel1 :{bot.nick}'s score is 1."),
            Recv("PRIVMSG #test-channel1 :End of scores."),

            SendRecv(f"{admin} PRIVMSG #test-channel1"
                     f" :{bot.nick}++",
                     "PRIVMSG #test-channel1"
                     f" :{bot.nick}'s score is now 2."),

            SendRecv(f"{admin} PRIVMSG #test-channel1"
                     f" :{bot.nick}++",
                     "PRIVMSG #test-channel1"
                     f" :{bot.nick}'s score is now 3."),

            Send(f"{admin} PRIVMSG #test-channel1 :.scores"),
            Recv(f"PRIVMSG #test-channel1 :{bot.nick}'s score is 3."),
            Recv("PRIVMSG #test-channel1 :bacon's score is 2."),
            Recv("PRIVMSG #test-channel1 :End of scores."),

            Send(f"{admin} PRIVMSG #test-channel1 :.scores -5"),
            Recv("PRIVMSG #test-channel1 :bacon's score is 2."),
            Recv(f"PRIVMSG #test-channel1 :{bot.nick}'s score is 3."),
            Recv("PRIVMSG #test-channel1 :End of scores."),

            SendRecv(f"{admin} PRIVMSG #test-channel1"
                     f" :.descore {bot.nick}",
                     "PRIVMSG #test-channel1"
                     f" :{bot.nick}'s score erased."),

            Send(f"{admin} PRIVMSG #test-channel1 :.scores"),
            Recv("PRIVMSG #test-channel1 :bacon's score is 2."),
            Recv("PRIVMSG #test-channel1 :End of scores."),

            SendRecv(f"{admin} PRIVMSG #test-channel1 :bacon++",
                     "PRIVMSG #test-channel1 :bacon's score is now 3."),
            SendRecv(f"{admin} PRIVMSG #test-channel1"
                     " :Screw bacon--",
                     "PRIVMSG #test-channel1 :bacon's score is now 2."),
            SendRecv(f"{admin} PRIVMSG #test-channel1 :++bacon",
                     "PRIVMSG #test-channel1 :bacon's score is now 3."),

            SendRecv(f"{admin} PRIVMSG #test-channel1 :.score bacon",
                     "PRIVMSG #test-channel1 :bacon's score is 3."),
            SendRecv(f"{no_admin} PRIVMSG #test-channel1 :.score bacon",
                     "PRIVMSG #test-channel1 :bacon's score is 3."),

            SendRecv(f"{admin} PRIVMSG #test-channel1 :--bacon",
                     "PRIVMSG #test-channel1 :bacon's score is now 2."),

            SendIgnored(f"{no_admin} PRIVMSG #test-channel1"
                        " :.descore bacon"),
            SendRecv(f"{admin} PRIVMSG #test-channel1 :.score bacon",
                     "PRIVMSG #test-channel1 :bacon's score is 2."),

            SendRecv(f"{admin} PRIVMSG #test-channel2 :.score bacon",
                     "PRIVMSG #test-channel2 :bacon has no score."),

            Send(f"{admin} PRIVMSG #test-channel2 :.scores"),
            Recv("PRIVMSG #test-channel2 :End of scores."),

            SendIgnored(f"{admin} PRIVMSG {bot.nick} :bacon++"),

            Send(f"{admin} PRIVMSG #test-channel1 :.scores"),
            Recv("PRIVMSG #test-channel1 :bacon's score is 2."),
            Recv("PRIVMSG #test-channel1 :End of scores."),

            Send(f"{admin} PRIVMSG #test-channel1 :.scores 11"),
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

            SendRecv(f"{admin} PRIVMSG #test-channel1"
                     " :.descore bacon",
                     "PRIVMSG #test-channel1 :bacon's score erased."),
            SendRecv(f"{admin} PRIVMSG #test-channel1 :.score bacon",
                     "PRIVMSG #test-channel1 :bacon has no score."),

            SendRecv(f"{admin} PRIVMSG #test-channel1 :.scores",
                     "PRIVMSG #test-channel1 :End of scores."),
            SendRecv(f"{no_admin} PRIVMSG #test-channel1 :.scores 10",
                     "PRIVMSG #test-channel1 :End of scores."),
            SendRecv(f"{no_admin} PRIVMSG #test-channel1 :.scores 11",
                     f"PRIVMSG #test-channel1 :{no_admin.nick}:"
                     " Too many scores requested."),

            SendRecv(f"{admin} PRIVMSG #test-channel1"
                     f" :{admin.nick}++",
                     "PRIVMSG #test-channel1 "
                     f":{admin.nick}: No self-scoring!"),
        ])

    @pytest.mark.asyncio
    async def test_08_commandline(self, client, bot, admin):
        no_admin = IRCUser(
            nick='someguy',
            user='nobody',
            host="localhost",
        )

        await client.conversation([
            SendIgnored(f"{no_admin} PRIVMSG {bot.nick} :.raw"
                        " PRIVMSG #test-channel1 test"),
            SendRecv(f"{admin} PRIVMSG {bot.nick} :.raw"
                     " PRIVMSG #test-channel1 test",
                     "PRIVMSG #test-channel1 test"),
            SendIgnored(f"{admin} PRIVMSG #test-channel1 :.raw"
                        " PRIVMSG #test-channel1 test"),
            SendRecv(f"{admin} PRIVMSG {bot.nick} :.part"
                     " #test-channel2",
                     "PART #test-channel2"),
            SendRecv(f"{admin} PRIVMSG {bot.nick} :.join"
                     " #test-channel2",
                     "JOIN #test-channel2"),
            SendIgnored(f"{no_admin} PRIVMSG {bot.nick} :.part"
                        " #test-channel2"),
        ])

    @pytest.mark.asyncio
    async def test_09_abuse_detection(self, client, bot, admin):
        await client.conversation([
            SendRecv(f"{admin} PRIVMSG {bot.nick} :.raw"
                     " PRIVMSG #test-channel1 :A short message.",
                     "PRIVMSG #test-channel1 :A short message."),
            SendIgnored(f"{admin} PRIVMSG {bot.nick} :.raw"
                        f" PRIVMSG #test-channel1 :A{' long' * 100} message."),
            SendIgnored(f"{admin} PRIVMSG {bot.nick} :.raw"
                        " PRIVMSG #test-channel1"
                        " :A short but malicious \0 message."),
        ])

    @pytest.mark.usefixtures('http_server')
    @pytest.mark.asyncio
    async def test_10_http_preview(self, client, admin):
        url = "http://127.0.0.1:8080"

        await client.conversation([
            SendRecv(f"{admin} PRIVMSG #test-channel1"
                     f" :{url}/simple-webpage",
                     "PRIVMSG #test-channel1"
                     f" :{admin.nick}: Simple Webpage"),
            SendIgnored(f"{admin} PRIVMSG #test-channel1"
                        f" :{url}/malicious-webpage"),
            SendIgnored(f"{admin} PRIVMSG #test-channel1"
                        f" :{url}/long-webpage"),
            SendRecv(f"{admin} PRIVMSG #test-channel1"
                     f" :{url}/slow-webpage",
                     "PRIVMSG #test-channel1"
                     f" :{admin.nick}: Preview timed out."),
            SendIgnored(f"{admin} PRIVMSG #test-channel1"
                        f" :{url}/redirecting-webpage"),
            SendIgnored(f"{admin} PRIVMSG #test-channel1"
                        f" :{url}/redirecting-webpage-mutual"),
            Send(f"{admin} PRIVMSG #test-channel1"
                 f" :{url}/simple-webpage and {url}/another-webpage"),
            Recv("PRIVMSG #test-channel1"
                 f" :{admin.nick}: Simple Webpage"),
            Recv("PRIVMSG #test-channel1"
                 f" :{admin.nick}: Another Webpage"),
        ])

    @pytest.mark.asyncio
    async def test_99_expect_silence(self, client):
        """All the previous tests should already expect the whole output
        generated by the bot.

        """
        await client.conversation([
            NoResponse(timeout=1),
        ])


if __name__ == '__main__':
    pytest.main()
