from urllib.parse import urljoin

from bs4 import BeautifulSoup


def parse_html(html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    # ---------------------------------------------------------
    # Remove elements that are almost never useful for search.
    # ---------------------------------------------------------
    for element in soup.find_all(
        [
            "script",
            "style",
            "noscript",
            "svg",
            "canvas",
            "nav",
            "footer",
            "form",
            "button",
            "iframe",
        ]
    ):
        element.decompose()

    # ---------------------------------------------------------
    # Title
    # ---------------------------------------------------------
    title = ""

    if soup.title:
        title = soup.title.get_text(
            " ",
            strip=True,
        )

    # Prefer <h1> as a fallback.
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(
                " ",
                strip=True,
            )

    # ---------------------------------------------------------
    # Meta description
    # ---------------------------------------------------------
    description = ""

    description_tag = soup.find(
        "meta",
        attrs={
            "name": "description"
        },
    )

    if description_tag:
        description = (
            description_tag.get(
                "content",
                "",
            )
            or ""
        ).strip()

    # ---------------------------------------------------------
    # Prefer the actual page content.
    # ---------------------------------------------------------
    content_root = (
        soup.find("article")
        or soup.find("main")
        or soup.find(
            attrs={
                "role": "main"
            }
        )
        or soup.body
        or soup
    )

    # Remove obvious junk inside content root.
    for element in content_root.find_all(
        [
            "script",
            "style",
            "noscript",
            "nav",
            "footer",
            "form",
            "button",
            "aside",
        ]
    ):
        element.decompose()

    # ---------------------------------------------------------
    # Extract text.
    # ---------------------------------------------------------
    content = content_root.get_text(
        separator=" ",
        strip=True,
    )

    # Collapse excessive whitespace.
    content = " ".join(
        content.split()
    )

    # ---------------------------------------------------------
    # Extract useful links.
    # ---------------------------------------------------------
    links = []
    seen_links = set()

    for tag in soup.find_all(
        "a",
        href=True,
    ):
        href = (
            tag.get("href")
            or ""
        ).strip()

        if not href:
            continue

        absolute_url = urljoin(
            base_url,
            href,
        )

        if absolute_url in seen_links:
            continue

        seen_links.add(
            absolute_url
        )

        links.append(
            absolute_url
        )

    return {
        "title": title,
        "description": description,
        "content": content,
        "links": links,
    }
