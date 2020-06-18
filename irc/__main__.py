#!/usr/bin/env python3

from irc import load_config, Socket
from irc.client import IRCClient
import argparse
import asyncio
import logging
import logging.config
import os
import signal


def live_debug(*ignore):
    import pdb
    pdb.set_trace()


async def run_bot():
    parser = argparse.ArgumentParser()
    parser.add_argument('config_file')
    args = parser.parse_args()

    conf = load_config(args.config_file)

    try:
        logging.config.dictConfig(conf['logging'])
    except KeyError:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s:%(name)s: %(message)s",
            datefmt="%H:%M:%S"
        )

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


def start_event_loop():
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


if __name__ == '__main__':
    signal.signal(signal.SIGUSR2, live_debug)  # noqa: E305
    start_event_loop()
