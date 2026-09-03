from urllib.parse import (
    parse_qsl,
    urlencode,
    urljoin,
    urlparse,
    urlunparse,
)


# Query parameters that generally do not identify
# unique page content.
TRACKING_PARAMETERS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "ref",
    "referrer",
    "source",
    "session",
}


# URL path prefixes that usually point to
# administrative or non-content pages.
BLOCKED_PATH_PREFIXES = (
    "/special:",
    "/file:",
    "/category:",
    "/template:",
    "/help:",
    "/talk:",
    "/user:",
)


def normalize_url(
    url: str,
    base_url: str | None = None,
) -> str | None:

    if not url:
        return None

    url = url.strip()

    if base_url:
        url = urljoin(
            base_url,
            url,
        )

    parsed = urlparse(url)

    # ---------------------------------------------------------
    # Protocol
    # ---------------------------------------------------------
    if parsed.scheme.lower() not in {
        "http",
        "https",
    }:
        return None

    if not parsed.netloc:
        return None

    # ---------------------------------------------------------
    # Normalize hostname
    # ---------------------------------------------------------
    hostname = (
        parsed.hostname
        or ""
    ).lower()

    if not hostname:
        return None

    # ---------------------------------------------------------
    # Remove default ports
    # ---------------------------------------------------------
    port = parsed.port

    if (
        port is None
        or (
            parsed.scheme == "http"
            and port == 80
        )
        or (
            parsed.scheme == "https"
            and port == 443
        )
    ):
        netloc = hostname
    else:
        netloc = f"{hostname}:{port}"

    # ---------------------------------------------------------
    # Remove fragment
    # ---------------------------------------------------------
    path = parsed.path or "/"

    # ---------------------------------------------------------
    # Filter known junk paths
    # ---------------------------------------------------------
    lowered_path = path.lower()

    for prefix in BLOCKED_PATH_PREFIXES:
        if lowered_path.startswith(prefix):
            return None

    # ---------------------------------------------------------
    # Remove trailing slash except root
    # ---------------------------------------------------------
    if path != "/":
        path = path.rstrip("/")

    # ---------------------------------------------------------
    # Filter query parameters
    # ---------------------------------------------------------
    clean_params = []

    for key, value in parse_qsl(
        parsed.query,
        keep_blank_values=True,
    ):
        if key.lower() in TRACKING_PARAMETERS:
            continue

        clean_params.append(
            (key, value)
        )

    query = urlencode(
        clean_params,
        doseq=True,
    )

    # ---------------------------------------------------------
    # Rebuild URL
    # ---------------------------------------------------------
    normalized = urlunparse(
        (
            parsed.scheme.lower(),
            netloc,
            path,
            "",
            query,
            "",
        )
    )

    # ---------------------------------------------------------
    # Safety limits
    # ---------------------------------------------------------
    if len(normalized) > 2000:
        return None

    return normalized