from bs4 import BeautifulSoup
from urllib.parse import urljoin


def parse_html(html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    for element in soup(
        ["script", "style", "noscript", "nav", "footer"]
    ):
        element.decompose()

    title = ""

    if soup.title:
        title = soup.title.get_text(strip=True)

    description = ""

    description_tag = soup.find(
        "meta",
        attrs={"name": "description"}
    )

    if description_tag:
        description = description_tag.get("content", "")

    content = soup.get_text(
        separator=" ",
        strip=True,
    )

    links = []

    for tag in soup.find_all("a", href=True):
        absolute_url = urljoin(
            base_url,
            tag["href"]
        )

        links.append(absolute_url)

    return {
        "title": title,
        "description": description,
        "content": content,
        "links": links,
    }
