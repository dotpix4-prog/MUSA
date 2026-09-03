from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse


class Robots:
    def __init__(self) -> None:
        self.parsers: dict[str, RobotFileParser] = {}

    def is_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        domain = parsed.netloc

        if not domain:
            return True

        if domain not in self.parsers:
            rp = RobotFileParser()
            try:
                # Try to fetch and read robots.txt for the domain.
                robots_url = f"{parsed.scheme}://{domain}/robots.txt"
                rp.set_url(robots_url)
                rp.read()
            except Exception:
                # If we can't read robots.txt, we assume it's allowed.
                return True

            self.parsers[domain] = rp

        return self.parsers[domain].can_fetch("MUSA/0.1", url)
