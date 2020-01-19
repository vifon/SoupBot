from .message import IRCMessage, ParseError
import logging
logger = logging.getLogger(__name__)


class IRCClient:
    def __init__(self, socket, buffer_size=2048, encoding='utf-8', **config):
        self.socket = socket
        self.buffer_size = buffer_size
        self.encoding = encoding
        self.config = config
        self.logger = logger.getChild(type(self).__name__)
        self.plugins = []
        self._buffer = bytearray()

    def __iter__(self):
        return self

    def __next__(self):
        return self.recv()

    def recv(self):
        separator = b"\r\n"
        separator_pos = self._buffer.find(separator)
        while separator_pos == -1:
            self._buffer.extend(self.socket.recv(self.buffer_size))
            separator_pos = self._buffer.find(separator)
        msg = self._buffer[:separator_pos].decode(self.encoding)
        self._buffer = self._buffer[separator_pos+len(separator):]
        self.logger.info(" >>> %s", repr(msg))

        try:
            return IRCMessage.parse(msg)
        except ParseError:
            self.logger.warning("Couldn't parse the message.")
            return IRCMessage.unparsed(msg)

    def send(self, command, *args, body=None):
        msg = IRCMessage(command, *args, body=body)
        self.sendmsg(msg)

    def sendmsg(self, msg):
        self.logger.info(" <<< %s", msg)
        self.socket.send(f"{msg}\r\n".encode(self.encoding))

    def join(self, channel):
        self.send('JOIN', channel)
        self.logger.info("Joining %s…", channel)

    def greet(self):
        self.send(
            "USER", self.config['nick'], "*", "*", body=self.config['name']
        )
        self.send('NICK', self.config['nick'])

    def event_loop(self):
        for msg in self:
            for plugin in self.plugins:
                try:
                    if plugin.react(msg):
                        break
                except Exception as e:
                    self.logger.exception(
                        "Plugin %s caused an exception during processing: %s",
                        plugin, repr(msg),
                    )
