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


def load_plugins(client, config):
    for plugin_name in config['plugins']:
        if isinstance(plugin_name, dict):
            plugin_name, plugin_config = next(iter(plugin_name.items()))
        else:
            plugin_config = None

        plugin_module, plugin_class = plugin_name.rsplit(".", 1)
        logger.info("Loading %s", plugin_name)
        plugin = getattr(
            importlib.import_module(plugin_module),
            plugin_class)(
                config=plugin_config,
                client=client,
            )
        yield plugin


def run_bot():
    conf = load_config("bot_config.yml")
    hostname = conf.pop('server')
    port = conf.pop('port')
    with socket.create_connection((hostname, port)) as sock:
        context = ssl.create_default_context()
        with context.wrap_socket(sock, server_hostname=hostname) as ssock:
            bot = IRCClient(ssock, **conf['bot'])
            bot.plugins.extend(load_plugins(bot, conf))
            bot.greet()
            for channel in conf['channels']:
                bot.join(channel)
            bot.event_loop()


if __name__ == '__main__':
    run_bot()
