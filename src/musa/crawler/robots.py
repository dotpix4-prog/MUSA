```python
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx


class Robots:
    def __init__(
        self,
        user_agent: str = "MUSA/0.1",
    ) -> None:
        self.user_agent = user_agent
        self.parsers: dict[
            str,
            RobotFileParser,
        ] = {}

    async def is_allowed(
        self,
        url: str,
        client: httpx.AsyncClient,
    ) -> bool:

        parsed = urlparse(url)

        if not parsed.netloc:
            return False

        domain = parsed.netloc.lower()

        # Already cached.
        if domain in self.parsers:
            return self.parsers[
                domain
            ].can_fetch(
                self.user_agent,
                url,
            )

        robots_url = (
            f"{parsed.scheme}://"
            f"{domain}/robots.txt"
        )

        parser = RobotFileParser()
        parser.set_url(
            robots_url
        )

        try:
            response = await client.get(
                robots_url,
                timeout=10.0,
            )

            # No robots.txt = allowed.
            if response.status_code == 404:
                self.parsers[domain] = parser
                return True

            # Server failure: fail closed.
            if response.status_code >= 400:
                return False

            parser.parse(
                response.text.splitlines()
            )

            self.parsers[domain] = parser

            return parser.can_fetch(
                self.user_agent,
                url,
            )

        except (
            httpx.TimeoutException,
            httpx.RequestError,
        ):
            # We couldn't verify the site's rules,
            # so do not crawl.
            return False

        except Exception:
            return False
```
