from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx


class Robots:

    def __init__(
        self,
        user_agent="MUSA/0.1"
    ):
        self.user_agent = user_agent
        self.parsers = {}

    async def is_allowed(
        self,
        url,
        client,
    ):

        parsed = urlparse(url)

        if not parsed.netloc:
            return False

        domain = parsed.netloc.lower()

        if domain in self.parsers:

            return self.parsers[
                domain
            ].can_fetch(
                self.user_agent,
                url,
            )

        robots_url = (
            "{}://{}/robots.txt".format(
                parsed.scheme,
                domain,
            )
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

            if response.status_code == 404:

                self.parsers[
                    domain
                ] = parser

                return True

            if response.status_code >= 400:
                return False

            parser.parse(
                response.text.splitlines()
            )

            self.parsers[
                domain
            ] = parser

            return parser.can_fetch(
                self.user_agent,
                url,
            )

        except (
            httpx.TimeoutException,
            httpx.RequestError,
        ):

            return False

        except Exception:

            return False
