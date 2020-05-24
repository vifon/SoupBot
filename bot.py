#!/usr/bin/env python3

from irc.client import IRCClient
from collections import namedtuple
import argparse
import asyncio
import logging
import logging.config
import os
import signal
import yaml


def load_config(path) -> dict:
    with open(path, 'r') as conf_fd:
        return yaml.safe_load(conf_fd.read())


def live_debug(*ignore):
    import pdb
    pdb.set_trace()
signal.signal(signal.SIGUSR2, live_debug)  # noqa: E305


Socket = namedtuple('Socket', ('reader', 'writer'))


async def run_bot():
    parser = argparse.ArgumentParser()
    parser.add_argument('config_file')
    args = parser.parse_args()

    conf = load_config(args.config_file)

    log_config = conf.get('logging', 'logging.conf')
    logging.config.fileConfig(log_config)
    logger = logging.getLogger(__name__)

    hostname = conf['server']
    port = conf['port']
    ssl = conf.get('ssl', True)
    socket = Socket(*await asyncio.open_connection(hostname, port, ssl=ssl))
    bot = IRCClient(socket, **conf['bot'])

    reload_task = None

    async def reload_plugins():
        logger.info("Plugin reload initiated…")

        nonlocal conf
        conf = load_config(args.config_file)

        nonlocal bot_task
        bot_task.cancel()
        logger.info("Loading the new plugins…")
        await bot.load_plugins(
            conf['plugins'],
            old_data=bot.unload_plugins()
        )
        logger.info("Restaring the IRC event loop with new plugins…")
        bot_task = asyncio.ensure_future(bot.event_loop())

    def schedule_reload_plugins():
        nonlocal reload_task
        reload_task = asyncio.ensure_future(asyncio.shield(reload_plugins()))

    asyncio.get_event_loop().add_signal_handler(
        signal.SIGUSR1,
        schedule_reload_plugins,
    )
    logger.info(
        f"Use 'kill -SIGUSR1 {os.getpid()}' to reload all plugins."
    )

    await bot.greet()
    await bot.load_plugins(conf['plugins'])
    bot_task = asyncio.ensure_future(bot.event_loop())
    while True:
        try:
            await bot_task
        except asyncio.CancelledError:
            if reload_task is not None:
                await reload_task
                reload_task = None
            else:
                raise
        else:
            return


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        bot_task = asyncio.ensure_future(run_bot())
        loop.run_until_complete(bot_task)
    except KeyboardInterrupt:
        pass
    finally:
        bot_task.cancel()
        try:
            loop.run_until_complete(bot_task)
        except asyncio.CancelledError:
            pass
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
