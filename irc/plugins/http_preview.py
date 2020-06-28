from irc.message import IRCMessage
from irc.plugin import IRCPlugin

from bs4 import BeautifulSoup
from urlextract import URLExtract
import asyncio
import httpx
import re

from typing import Optional


class HTTPPreview(IRCPlugin):
    extractor = URLExtract()

    retries = 3

    bad_results = {
        r'^https?://(?:www\.)?youtube\.com/': 'YouTube',
    }

    def get_bad_result(self, url):
        for pattern in self.bad_results:
            if re.search(pattern, url):
                return self.bad_results[pattern]

    async def generate_preview(
            self,
            client: httpx.AsyncClient,
            url: str,
    ) -> Optional[str]:
        bad_result = self.get_bad_result(url)
        self.logger.debug("Expected bad result: %s", bad_result)

        for _ in range(0, self.retries):
            self.logger.info("Generating preview for: %s", url)
            response = await asyncio.wait_for(
                client.get(url),
                timeout=self.config.get('timeout', 10),
            )
            self.logger.debug("%s fetched.", url)
            response.raise_for_status()
            html = response.text
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

            title: str = soup.title.get_text().strip()
            self.logger.debug(
                "%s title extracted: %s", url, title
            )
            if title == bad_result:
                self.logger.info(
                    'The title matched the expected "bad title", retrying…'
                )
            else:
                return title
        return None

    async def react(self, msg: IRCMessage) -> None:
        if msg.command == 'PRIVMSG':
            assert msg.sender is not None

            if msg.sender.identity in self.config.get('ignore', []):
                return

            channel = msg.args[0]
            nick = msg.sender.nick
            async with httpx.AsyncClient() as client:
                for url in self.extractor.gen_urls(msg.body):
                    try:
                        title = await self.generate_preview(client, url)
                    except asyncio.TimeoutError:
                        self.client.send(IRCMessage(
                            'PRIVMSG', channel,
                            body=f"{nick}: Preview timed out.",
                        ))
                        self.logger.exception(
                            "Error during processing %s", url
                        )
                    except Exception:
                        self.logger.exception(
                            "Error during processing %s", url
                        )
                    else:
                        if title:
                            self.client.send(IRCMessage(
                                'PRIVMSG', channel,
                                body=f"{nick}: {title}",
                            ))
