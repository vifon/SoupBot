#!/usr/bin/env python3

import socket
import ssl
import yaml

import logging
from irc.bot import MessageBot
logging.basicConfig(level=logging.DEBUG)


def load_config(path):
    with open(path, 'r') as conf_fd:
        return yaml.safe_load(conf_fd.read())


if __name__ == '__main__':
    conf = load_config("irc_conf.yml")
    hostname = conf.pop('server')
    with socket.create_connection((hostname, conf.pop('port'))) as sock:
        context = ssl.create_default_context()
        with context.wrap_socket(sock, server_hostname=hostname) as ssock:
            bot = MessageBot(ssock, **conf['bot'])
            bot.greet()
            for channel in conf['channels']:
                bot.join(channel)
            bot.event_loop()
