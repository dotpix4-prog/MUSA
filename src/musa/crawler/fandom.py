import html
from urllib.parse import (
    parse_qs,
    urlencode,
    urlparse,
)

import httpx
from bs4 import BeautifulSoup


class FandomAdapter:
    """
    Adapter for MediaWiki-based Fandom wikis.

    Instead of requesting the normal wiki page, MUSA uses
    the wiki's MediaWiki API to obtain page content and links.

    This avoids relying on normal HTML page delivery when a
    wiki exposes structured API access.
    """

    def __init__(self, user_agent="MUSA/0.1"):
        self.user_agent = user_agent

    def is_fandom_url(self, url):
        parsed = urlparse(url)

        if not parsed.netloc:
            return False

        domain = parsed.netloc.lower()

        return (
            domain == "fandom.com"
            or domain.endswith(".fandom.com")
        )

    def _page_title_from_url(self, url):
        parsed = urlparse(url)

        path = parsed.path.strip("/")

        if not path:
            return "Main Page"

        if path.lower().startswith("wiki/"):
            page_title = path[5:]
        else:
            page_title = path

        # Decode common wiki URL encoding.
        page_title = page_title.replace(
            "_",
            " ",
        )

        return page_title

    def _api_url(self, url):
        parsed = urlparse(url)

        return "{}://{}/api.php".format(
            parsed.scheme,
            parsed.netloc,
        )

    async def fetch(
        self,
        url,
        client,
    ):
        """
        Fetch a Fandom page through MediaWiki's API.

        Returns:
            {
                "title": str,
                "content_html": str,
                "links": list[str],
                "url": str,
            }

        or None if the API cannot provide the page.
        """

        if not self.is_fandom_url(url):
            return None

        page_title = self._page_title_from_url(
            url
        )

        api_url = self._api_url(url)

        params = {
            "action": "parse",
            "page": page_title,
            "prop": "text|links",
            "redirects": "1",
            "format": "json",
            "formatversion": "2",
        }

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }

        try:

            response = await client.get(
                api_url,
                params=params,
                headers=headers,
                timeout=25.0,
            )

            print(
                "[FANDOM API] HTTP {} {}".format(
                    response.status_code,
                    response.reason_phrase,
                ),
                flush=True,
            )

            if response.status_code >= 400:
                print(
                    "[FANDOM API] Request failed.",
                    flush=True,
                )
                return None

            data = response.json()

        except Exception as e:

            print(
                "[FANDOM API ERROR] {}: {}".format(
                    type(e).__name__,
                    e,
                ),
                flush=True,
            )

            return None

        if "error" in data:

            error = data.get(
                "error",
                {},
            )

            print(
                "[FANDOM API] {}: {}".format(
                    error.get(
                        "code",
                        "unknown",
                    ),
                    error.get(
                        "info",
                        "unknown error",
                    ),
                ),
                flush=True,
            )

            return None

        parsed = data.get(
            "parse"
        )

        if not parsed:
            print(
                "[FANDOM API] No parse result.",
                flush=True,
            )
            return None

        title = (
            parsed.get(
                "title"
            )
            or page_title
        )

        text_html = (
            parsed.get(
                "text"
            )
            or ""
        )

        # -----------------------------------------------------
        # Extract links from API-returned HTML.
        # -----------------------------------------------------
        links = []

        soup = BeautifulSoup(
            text_html,
            "html.parser",
        )

        base_domain = urlparse(
            url
        ).netloc

        for tag in soup.find_all(
            "a",
            href=True,
        ):

            href = (
                tag.get(
                    "href"
                )
                or ""
            ).strip()

            if not href:
                continue

            # Fandom API links are often /wiki/Page.
            if href.startswith(
                "/wiki/"
            ):

                absolute = "{}://{}{}".format(
                    urlparse(url).scheme,
                    base_domain,
                    href,
                )

                links.append(
                    absolute
                )

        # Remove duplicate links.
        links = list(
            dict.fromkeys(
                links
            )
        )

        return {
            "title": html.unescape(
                title
            ),
            "content_html": text_html,
            "links": links,
            "url": str(response.url),
        }