#!/usr/bin/env python3

from irc.client import IRCClient
import importlib
import logging
import socket
import ssl
import yaml
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


def load_config(path):
    with open(path, 'r') as conf_fd:
        return yaml.safe_load(conf_fd.read())


def run_bot():
    conf = load_config("bot_config.yml")
    hostname = conf.pop('server')
    port = conf.pop('port')
    with socket.create_connection((hostname, port)) as sock:
        context = ssl.create_default_context()
        with context.wrap_socket(sock, server_hostname=hostname) as ssock:
            bot = IRCClient(ssock, **conf['bot'])
            bot.load_plugins(conf['plugins'])
            bot.greet()
            for channel in conf['channels']:
                bot.join(channel)
            bot.event_loop()


if __name__ == '__main__':
    run_bot()
