from urllib.parse import urljoin, urlparse, urlunparse


def normalize_url(url: str, base_url: str | None = None) -> str | None:
    if base_url:
        url = urljoin(base_url, url)

    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        return None

    if not parsed.netloc:
        return None

    # Remove fragments such as #section
    normalized = parsed._replace(
        fragment=""
    )

    return urlunparse(normalized)
