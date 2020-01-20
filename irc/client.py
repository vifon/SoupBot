from .message import IRCMessage, ParseError
from types import SimpleNamespace
import logging
import sqlite3
logger = logging.getLogger(__name__)


class IRCClient:
    def __init__(
            self,
            socket,
            buffer_size=2048,
            encoding='utf-8',
            sqlite_db=':memory:',
            **config,
    ):
        self.socket = socket
        self.buffer_size = buffer_size
        self.encoding = encoding
        self.config = config
        self.logger = logger.getChild(type(self).__name__)
        self.plugins = []
        self.shared_data = SimpleNamespace()
        self.db = sqlite3.connect(
            sqlite_db,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        self._buffer = bytearray()

    def __iter__(self):
        return self

    def __next__(self):
        return self.recv()

    @property
    def nick(self):
        # TODO: Return real nick when the nick collisions handling
        # gets implemented, not the one in the config.
        return self.config['nick']

    def recv(self):
        separator = b"\r\n"
        separator_pos = self._buffer.find(separator)
        while separator_pos == -1:
            self._buffer.extend(self.socket.recv(self.buffer_size))
            separator_pos = self._buffer.find(separator)
        msg = self._buffer[:separator_pos].decode(self.encoding)
        self._buffer = self._buffer[separator_pos+len(separator):]
        self.logger.info(">>> %s", repr(msg))

        try:
            return IRCMessage.parse(msg)
        except ParseError:
            self.logger.warning("Couldn't parse the message.")
            return IRCMessage.unparsed(msg)

    def send(self, command, *args, body=None):
        msg = IRCMessage(command, *args, body=body)
        self.sendmsg(msg)

    def sendmsg(self, msg):
        self.logger.info("<<< %s", msg)
        self.socket.send(f"{msg}\r\n".encode(self.encoding))

    def join(self, channel):
        self.send('JOIN', channel)
        self.logger.info("Joining %s…", channel)

    def greet(self):
        self.send(
            "USER", self.config['nick'], "*", "*", body=self.config['name']
        )
        self.send('NICK', self.config['nick'])
        # TODO: Handle nick collisions.

    def event_loop(self):
        for msg in self:
            for plugin in self.plugins:
                try:
                    if plugin.react(msg):
                        break
                except Exception:
                    self.logger.exception(
                        "%s caused an exception during processing: %s",
                        plugin, repr(msg),
                    )

    def load_plugins(self, plugins):
        def load_plugins_helper():
            import importlib

            for plugin_name in plugins:
                if isinstance(plugin_name, dict):
                    plugin_name, plugin_config = next(iter(plugin_name.items()))
                else:
                    plugin_config = None

                plugin_module, plugin_class = plugin_name.rsplit(".", 1)
                plugin = getattr(
                    importlib.import_module(plugin_module),
                    plugin_class)(
                        config=plugin_config,
                        client=self,
                    )
                yield plugin

        self.plugins.extend(load_plugins_helper())
