from dataclasses import dataclass
from datetime import datetime


@dataclass
class Document:
    url: str
    title: str
    content: str
    description: str = ""
    domain: str = ""
    crawled_at: datetime | None = None
    vector: list[float] | None = None
    score: float | None = None

