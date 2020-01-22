#!/usr/bin/env python3

from irc.client import IRCClient
from collections import namedtuple
import argparse
import asyncio
import logging
import os
import signal
import yaml
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s:%(name)s: %(message)s",
    datefmt="%H:%M"
)


def load_config(path):
    with open(path, 'r') as conf_fd:
        return yaml.safe_load(conf_fd.read())


def live_debug(*ignore):
    import pdb
    pdb.set_trace()
signal.signal(signal.SIGUSR2, live_debug)


Socket = namedtuple('Socket', ('reader', 'writer'))


async def run_bot():
    parser = argparse.ArgumentParser()
    parser.add_argument('config_file')
    args = parser.parse_args()

    conf = load_config(args.config_file)
    hostname = conf['server']
    port = conf['port']
    socket = Socket(*await asyncio.open_connection(
        hostname, port, ssl=True
    ))
    bot = IRCClient(socket, **conf['bot'])

    async def reload_plugins():
        nonlocal conf
        conf = load_config(args.config_file)
        await bot.load_plugins(
            conf['plugins'],
            old_data=bot.unload_plugins()
        )
    asyncio.get_event_loop().add_signal_handler(
        signal.SIGUSR1,
        lambda: asyncio.ensure_future(reload_plugins()),
    )
    logger.info(
        f"Use 'kill -SIGUSR1 {os.getpid()}' to reload all plugins."
    )

    await bot.greet()
    await bot.load_plugins(conf['plugins'])
    await bot.event_loop()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_bot())
    loop.close()
