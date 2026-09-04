from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx


class Robots:
    """
    Robots.txt handler for MUSA.

    MUSA normally respects robots.txt.

    Explicitly supported domains can be added to
    ALLOWED_DOMAINS when you have decided that MUSA
    should be able to crawl them.
    """

    ALLOWED_DOMAINS = {
        "bleach.fandom.com",
    }

    def __init__(
        self,
        user_agent="MUSA/0.1",
    ):
        self.user_agent = user_agent
        self.parsers = {}

    def _is_explicitly_allowed(
        self,
        domain,
    ):
        domain = domain.lower()

        # Exact match
        if domain in self.ALLOWED_DOMAINS:
            return True

        # Allow subdomains of explicitly allowed domains
        for allowed_domain in self.ALLOWED_DOMAINS:
            if domain.endswith(
                "." + allowed_domain
            ):
                return True

        return False

    async def is_allowed(
        self,
        url,
        client,
    ):
        parsed = urlparse(url)

        if not parsed.netloc:
            return False

        domain = parsed.netloc.lower()

        # -------------------------------------------------
        # Explicit MUSA domain override
        # -------------------------------------------------
        if self._is_explicitly_allowed(
            domain
        ):
            print(
                "[ROBOTS] Explicitly allowed domain: {}".format(
                    domain
                ),
                flush=True,
            )
            return True

        # -------------------------------------------------
        # Cached robots.txt
        # -------------------------------------------------
        if domain in self.parsers:
            parser = self.parsers[
                domain
            ]

            return parser.can_fetch(
                self.user_agent,
                url,
            )

        robots_url = "{}://{}/robots.txt".format(
            parsed.scheme,
            domain,
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

            # No robots.txt means there are no
            # published crawler rules to parse.
            if response.status_code == 404:

                self.parsers[
                    domain
                ] = parser

                return True

            # If robots.txt itself cannot be fetched,
            # fail closed for unknown domains.
            if response.status_code >= 400:
                print(
                    "[ROBOTS] Could not read robots.txt: "
                    "HTTP {}".format(
                        response.status_code
                    ),
                    flush=True,
                )

                return False

            parser.parse(
                response.text.splitlines()
            )

            self.parsers[
                domain
            ] = parser

            allowed = parser.can_fetch(
                self.user_agent,
                url,
            )

            return allowed

        except (
            httpx.TimeoutException,
            httpx.RequestError,
        ) as e:

            print(
                "[ROBOTS ERROR] {}: {}".format(
                    type(e).__name__,
                    e,
                ),
                flush=True,
            )

            return False

        except Exception as e:

            print(
                "[ROBOTS ERROR] {}: {}".format(
                    type(e).__name__,
                    e,
                ),
                flush=True,
            )

            return False