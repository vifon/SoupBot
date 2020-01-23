from .message import IRCMessage
from types import SimpleNamespace
from typing import Dict, List, Any, Iterator
import asyncio
import logging
import sqlite3
import time
logger = logging.getLogger(__name__)


class IRCClient:
    def __init__(
            self,
            socket,
            encoding='utf-8',
            sqlite_db=':memory:',
            **config,
    ):
        self.socket = socket
        self.incoming_queue = asyncio.Queue()
        self.encoding = encoding
        self.config = config
        self.logger = logger.getChild(type(self).__name__)
        self.db = sqlite3.connect(
            sqlite_db,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        self._buffer = bytearray()
        self.plugins = []
        self.shared_data = SimpleNamespace()

    def __aiter__(self):
        return self

    async def __anext__(self) -> IRCMessage:
        return await self._recv()

    @property
    def nick(self) -> str:
        # TODO: Return real nick when the nick collisions handling
        # gets implemented, not the one in the config.
        return self.config['nick']

    async def recv(self) -> IRCMessage:
        return await self.incoming_queue.get()

    async def _recv(self) -> IRCMessage:
        separator = b"\r\n"
        separator_pos = self._buffer.find(separator)
        while separator_pos == -1:
            self._buffer.extend(await self.socket.reader.read(512))
            separator_pos = self._buffer.find(separator)
        msg = self._buffer[:separator_pos].decode(self.encoding)
        self._buffer = self._buffer[separator_pos+len(separator):]
        self.logger.info(">>> %s", repr(msg))
        return IRCMessage.parse(msg)

    async def send(self, command: str, *args: str, body: str = None, delay: int = 2):
        msg = IRCMessage(command, *args, body=body)
        await self.sendmsg(msg, delay)

    async def sendmsg(self, msg: IRCMessage, delay: int = 2):
        self.logger.info("<<< %s", msg)
        self.socket.writer.write(f"{msg}\r\n".encode(self.encoding))
        await self.socket.writer.drain()
        await asyncio.sleep(delay)

    async def greet(self):
        await self.send(
            "USER", self.config['nick'], "*", "*", body=self.config['name'],
            delay=0,
        )
        await self.send('NICK', self.config['nick'], delay=0)
        # TODO: Handle nick collisions.

    async def event_loop(self):
        async def irc_reader():
            async for msg in self:
                await self.incoming_queue.put(msg)

        async def plugin_caller():
            while True:
                msg = await self.recv()
                await asyncio.gather(*(plugin.react(msg) for plugin in self.plugins))

        await asyncio.gather(irc_reader(), plugin_caller())

    async def load_plugins(self, plugins: List[str], old_data: Dict[str, Any] = None):
        if old_data is None:
            old_data = {}

        failed_plugins = []

        def load_plugins_helper():
            def load_or_reload(module):
                import importlib
                if old_data:
                    return importlib.reload(importlib.import_module(module))
                else:
                    return importlib.import_module(module)

            for plugin_name in plugins:
                if isinstance(plugin_name, dict):
                    plugin_name, plugin_config = next(iter(plugin_name.items()))
                else:
                    plugin_config = None

                plugin_module, plugin_class = plugin_name.rsplit(".", 1)
                try:
                    plugin = getattr(
                        load_or_reload(plugin_module),
                        plugin_class)(
                            config=plugin_config,
                            client=self,
                            old_data=old_data.get(plugin_class),
                        )
                    yield plugin
                except Exception:
                    self.logger.exception(
                        "%s caused an exception during loading.", plugin_class
                    )
                    failed_plugins.append(plugin_class)

        self.plugins.extend(load_plugins_helper())
        self.logger.info(
            "Initialized plugins: %s",
            [type(plugin).__name__ for plugin in self.plugins],
        )
        if failed_plugins:
            self.logger.warning("Failed plugins: %s", failed_plugins)
        for plugin in self.plugins:
            await plugin.start()

    def unload_plugins(self) -> Dict[str, Any]:
        self.logger.info("Unloading plugins…")
        old_data = vars(self.shared_data)
        self.plugins = []
        self.shared_data = SimpleNamespace()
        return old_data
