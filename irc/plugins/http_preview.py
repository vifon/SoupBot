from irc.message import IRCMessage
from irc.plugin import IRCPlugin

from bs4 import BeautifulSoup
from urlextract import URLExtract
import aiohttp
import asyncio


async def fetch(session, url):
    async with session.get(url) as response:
        return await response.text()


class HTTPPreview(IRCPlugin):
    extractor = URLExtract()

    async def react(self, msg):
        if msg.command == 'PRIVMSG':
            channel = msg.args[0]
            nick = msg.sender.nick
            for url in self.extractor.gen_urls(msg.body):
                self.logger.info("Generating preview for: %s", url)
                try:
                    async with aiohttp.ClientSession() as session:
                        try:
                            html = await asyncio.wait_for(
                                fetch(session, url),
                                timeout=self.config.get('timeout', 10),
                            )
                            self.logger.debug("%s fetched.", url)
                            loop = asyncio.get_event_loop()
                            soup = await asyncio.wait_for(
                                loop.run_in_executor(
                                    None,
                                    BeautifulSoup, html, 'html.parser',
                                ),
                                # 2 seconds should be a plenty for
                                # sane webpages.
                                timeout=2,
                            )
                            self.logger.debug("%s parsed.", url)
                        except asyncio.TimeoutError:
                            self.client.send(IRCMessage(
                                'PRIVMSG', channel,
                                body=f"{nick}: Preview timed out.",
                            ))
                            raise
                        else:
                            title = soup.title.get_text()
                            self.logger.debug(
                                "%s title extracted: %s", url, title
                            )
                            self.client.send(IRCMessage(
                                'PRIVMSG', channel,
                                body=f"{nick}: {title}",
                            ))
                except Exception:
                    self.logger.exception("Error during processing %s", url)
