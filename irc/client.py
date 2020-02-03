from .message import IRCMessage, IRCSecurityError
from types import SimpleNamespace
import asyncio
import logging
import sqlite3
logger = logging.getLogger(__name__)

from typing import TYPE_CHECKING, Dict, List, Any, Union, Optional  # noqa: F402, E501
if TYPE_CHECKING:  # pragma: no cover
    from .plugin import IRCPlugin  # noqa: F401


class IRCClient:
    def __init__(
            self,
            socket,
            encoding: str = 'utf-8',
            sqlite_db: str = ':memory:',
            delay: int = 2,
            **config: Any,
    ):
        self.socket = socket
        self.encoding = encoding
        self.delay = delay
        self.config = config
        self.logger = logger.getChild(type(self).__name__)
        self.db = sqlite3.connect(
            sqlite_db,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        self.nick = self.config['nick']
        self._buffer = bytearray()
        self.plugins: List['IRCPlugin'] = []
        self.shared_data = SimpleNamespace()
        self.outgoing_queue: asyncio.Queue = asyncio.Queue()

    def __aiter__(self):
        return self

    async def __anext__(self) -> IRCMessage:
        msg = await self.recv()
        if msg:
            return msg
        else:
            raise StopAsyncIteration()

    async def recv(self) -> Optional[IRCMessage]:
        separator = b"\r\n"
        separator_pos = self._buffer.find(separator)
        while separator_pos == -1:
            self._buffer.extend(await self.socket.reader.read(512))
            if self.at_eof():
                return None
            separator_pos = self._buffer.find(separator)
        msg = self._buffer[:separator_pos].decode(self.encoding)
        self._buffer = self._buffer[separator_pos+len(separator):]
        self.logger.info(">>> %s", repr(msg))
        return IRCMessage.parse(msg)

    def at_eof(self) -> bool:
        return self.socket.reader.at_eof()

    def send(self, msg: Union[IRCMessage, str]):
        self.outgoing_queue.put_nowait(msg)

    async def _send(self, msg: Union[IRCMessage, str]):
        if self.at_eof():
            self.logger.info("<!< %s", repr(str(msg)))
            raise IOError("The IRC socket is closed.")
        self.logger.info("<<< %s", repr(str(msg)))
        if isinstance(msg, IRCMessage):
            msg.sanitize()
        elif isinstance(msg, str):
            IRCMessage.parse(msg).sanitize()
        self.socket.writer.write(f"{msg}\r\n".encode(self.encoding))
        await self.socket.writer.drain()

    async def greet(self):
        await self._send(IRCMessage(
            "USER", self.nick, "*", "*", body=self.config['name'],
        ))
        await self._send(IRCMessage('NICK', self.nick))
        async for msg in self:
            if msg.command == '433':  # ERR_NICKNAMEINUSE
                self.nick += "_"
                await self._send(IRCMessage('NICK', self.nick))
            if msg.command == '001':  # RPL_WELCOME
                break

    async def event_loop(self):
        async def irc_reader():
            try:
                async for msg in self:
                    for plugin in self.plugins:
                        plugin.logger.debug(
                            "Queue size on append: %d", plugin.queue.qsize()
                        )
                        await plugin.queue.put(msg)
                self.logger.info("Encountered the IRC stream EOF.")
            finally:
                self.logger.info("IRC reader closing.")

        async def irc_writer():
            while True:
                msg = await self.outgoing_queue.get()
                try:
                    await self._send(msg)
                except IRCSecurityError:
                    self.logger.warning("A possible abuse detected!")
                else:
                    await asyncio.sleep(self.delay)

        async def plugin_runner():
            try:
                await asyncio.gather(
                    *(plugin.event_loop() for plugin in self.plugins)
                )
            except asyncio.CancelledError:
                self.logger.info("Forcibly closing all plugins.")
            finally:
                self.logger.info("All the plugins have finished.")

        plugin_runner_task = asyncio.ensure_future(plugin_runner())
        irc_writer_task = asyncio.ensure_future(irc_writer())
        self.logger.info("Starting the IRC event loop.")
        try:
            await irc_reader()
        finally:
            self.logger.info("The IRC event loop has finished.")
            plugin_runner_task.cancel()
            irc_writer_task.cancel()

    async def load_plugins(
            self,
            plugins: List[str],
            old_data: Dict[str, Any] = None,
    ):
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
                    plugin_name, plugin_config = \
                        next(iter(plugin_name.items()))
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
