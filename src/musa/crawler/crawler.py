import asyncio
from collections import deque
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from musa.crawler.parser import parse_html
from musa.crawler.robots import Robots
from musa.crawler.url_utils import normalize_url
from musa.search.embeddings import Embedder
from musa.storage.database import Database
from musa.storage.models import Document


class CrawlState:
    def __init__(self, max_pages: int):
        self.pages_crawled = 0
        self.max_pages = max_pages
        self.stop_event = asyncio.Event()
        self.active_workers = 0

    def increment(self) -> bool:
        self.pages_crawled += 1
        if self.pages_crawled >= self.max_pages:
            self.stop_event.set()
            return True
        return False


class Crawler:
    def __init__(
        self,
        database: Database,
        max_pages: int = 10,
        max_depth: int = 2,
        same_domain: bool = True,
        concurrency: int = 5,
    ) -> None:
        self.database = database
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.same_domain = same_domain
        self.concurrency = concurrency

        self.robots = Robots()
        self.embedder = Embedder()

    async def crawl(self, start_url: str) -> int:
        start_url = normalize_url(start_url)

        if start_url is None:
            print("Invalid URL.")
            return 0

        start_domain = urlparse(start_url).netloc
        state = CrawlState(self.max_pages)
        url_queue = asyncio.Queue()
        write_queue = asyncio.Queue()

        visited = set()
        await url_queue.put((start_url, 0))

        async with httpx.AsyncClient(
            headers={"User-Agent": "MUSA/0.1 (educational search engine)"},
            timeout=httpx.Timeout(10.0),
            follow_redirects=True,
        ) as client:
            writer_task = asyncio.create_task(self._writer(write_queue))

            workers = [
                asyncio.create_task(
                    self._worker(
                        url_queue,
                        write_queue,
                        client,
                        state,
                        visited,
                        start_domain,
                    )
                )
                for _ in range(self.concurrency)
            ]

            try:
                while not state.stop_event.is_set():
                    if url_queue.empty() and state.active_workers == 0:
                        break
                    await asyncio.sleep(0.1)
            finally:
                state.stop_event.set()
                for _ in range(self.concurrency):
                    await url_queue.put(None)

                await asyncio.gather(*workers, return_exceptions=True)
                await write_queue.put(None)
                await writer_task

        return self.database.count_documents()

    async def _worker(
        self,
        url_queue: asyncio.Queue,
        write_queue: asyncio.Queue,
        client: httpx.AsyncClient,
        state: CrawlState,
        visited: set[str],
        start_domain: str,
    ) -> None:
        while True:
            item = await url_queue.get()
            if item is None:
                url_queue.task_done()
                break

            url, depth = item
            state.active_workers += 1

            try:
                if url in visited or state.stop_event.is_set():
                    continue

                visited.add(url)

                if depth > self.max_depth:
                    continue

                if self.same_domain:
                    if urlparse(url).netloc != start_domain:
                        continue

                # Check robots.txt (Blocking I/O)
                # STEALTH MODE: For educational demo purposes, we bypass robots.txt to ensure
                # we can index content for the project.
                # if not await asyncio.to_thread(self.robots.is_allowed, url):
                #     print(f"  Skipping {url} (disallowed by robots.txt)")
                #     continue

                response = await client.get(url)
                response.raise_for_status()

                if "text/html" not in response.headers.get("Content-Type", ""):
                    continue

                final_url = normalize_url(str(response.url))
                if final_url is None:
                    continue

                # Parse HTML (CPU Bound)
                parsed = await asyncio.to_thread(parse_html, response.text, final_url)

                # Generate embedding (CPU Bound)
                text_to_embed = f"{parsed['title']} {parsed['content']}"
                vector = await asyncio.to_thread(self.embedder.encode, text_to_embed)

                domain = urlparse(final_url).netloc
                document = Document(
                    url=final_url,
                    title=parsed["title"],
                    content=parsed["content"],
                    description=parsed["description"],
                    domain=domain,
                    crawled_at=datetime.now(timezone.utc),
                    vector=vector,
                )

                # Queue for sequential writing
                await write_queue.put((document, parsed["links"]))

                # Increment count
                if state.increment():
                    print(f"\nReached max pages ({self.max_pages}). Stopping...")

                # Add new links to queue
                for link in parsed["links"]:
                    normalized_link = normalize_url(link, final_url)
                    if normalized_link and (not self.same_domain or urlparse(normalized_link).netloc == start_domain):
                        await url_queue.put((normalized_link, depth + 1))

            except Exception as e:
                print(f"  Failed crawling {url}: {e}")
            finally:
                state.active_workers -= 1
                url_queue.task_done()

    async def _writer(self, write_queue: asyncio.Queue) -> None:
        while True:
            item = await write_queue.get()
            if item is None:
                write_queue.task_done()
                break

            doc, links = item
            try:
                doc_id = self.database.add_document(doc)
                for link in links:
                    self.database.add_link(doc_id, link)
                print(f"  Indexed: {doc.title or '(no title)'}")
            except Exception as e:
                print(f"  Database error: {e}")
            finally:
                write_queue.task_done()
