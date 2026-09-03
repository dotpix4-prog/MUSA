```python
import asyncio
import random
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
        self.lock = asyncio.Lock()

    async def increment(self) -> bool:
        async with self.lock:
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
        concurrency: int = 3,
        request_delay: float = 1.0,
        max_retries: int = 3,
        log_callback=None,
    ) -> None:
        self.database = database
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.same_domain = same_domain
        self.concurrency = max(1, min(concurrency, 5))
        self.request_delay = max(0.0, request_delay)
        self.max_retries = max(1, max_retries)
        self.log_callback = log_callback

        self.robots = Robots(
            user_agent="MUSA/0.1"
        )
        self.embedder = Embedder()

    def log(self, message: str) -> None:
        print(message, flush=True)

        if self.log_callback is not None:
            try:
                self.log_callback(message)
            except Exception:
                pass

    async def crawl(self, start_url: str) -> int:
        self.log("")
        self.log("=" * 60)
        self.log("MUSA CRAWLER")
        self.log("=" * 60)
        self.log(f"Start URL : {start_url}")
        self.log(f"Max pages : {self.max_pages}")
        self.log(f"Max depth : {self.max_depth}")
        self.log(f"Workers   : {self.concurrency}")
        self.log("")

        start_url = normalize_url(start_url)

        if start_url is None:
            self.log("[ERROR] Invalid URL.")
            return self.database.count_documents()

        start_domain = urlparse(start_url).netloc.lower()

        if not start_domain:
            self.log("[ERROR] Could not determine domain.")
            return self.database.count_documents()

        state = CrawlState(self.max_pages)

        url_queue: asyncio.Queue = asyncio.Queue()
        write_queue: asyncio.Queue = asyncio.Queue()

        visited: set[str] = set()
        visited_lock = asyncio.Lock()

        await url_queue.put((start_url, 0))

        timeout = httpx.Timeout(
            connect=10.0,
            read=25.0,
            write=10.0,
            pool=10.0,
        )

        headers = {
            "User-Agent": (
                "MUSA/0.1 "
                "(educational search engine; "
                "contact unavailable)"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }

        async with httpx.AsyncClient(
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
        ) as client:

            writer_task = asyncio.create_task(
                self._writer(write_queue)
            )

            workers = [
                asyncio.create_task(
                    self._worker(
                        url_queue=url_queue,
                        write_queue=write_queue,
                        client=client,
                        state=state,
                        visited=visited,
                        visited_lock=visited_lock,
                        start_domain=start_domain,
                    )
                )
                for _ in range(self.concurrency)
            ]

            try:
                while True:
                    if state.stop_event.is_set():
                        break

                    if (
                        url_queue.empty()
                        and state.active_workers == 0
                    ):
                        break

                    await asyncio.sleep(0.1)

            finally:
                state.stop_event.set()

                for _ in range(self.concurrency):
                    await url_queue.put(None)

                results = await asyncio.gather(
                    *workers,
                    return_exceptions=True,
                )

                for index, result in enumerate(results):
                    if isinstance(result, Exception):
                        self.log(
                            f"[WORKER {index} ERROR] "
                            f"{type(result).__name__}: {result}"
                        )

                await write_queue.put(None)
                await writer_task

        self.log("")
        self.log("=" * 60)
        self.log("CRAWL FINISHED")
        self.log("=" * 60)
        self.log(
            f"Pages processed : {state.pages_crawled}"
        )
        self.log(
            f"Documents total : "
            f"{self.database.count_documents()}"
        )
        self.log("=" * 60)

        return self.database.count_documents()

    async def _worker(
        self,
        url_queue: asyncio.Queue,
        write_queue: asyncio.Queue,
        client: httpx.AsyncClient,
        state: CrawlState,
        visited: set[str],
        visited_lock: asyncio.Lock,
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
                if state.stop_event.is_set():
                    continue

                if depth > self.max_depth:
                    self.log(
                        f"[SKIP] Max depth reached: {url}"
                    )
                    continue

                async with visited_lock:
                    if url in visited:
                        continue

                    visited.add(url)

                if self.same_domain:
                    current_domain = urlparse(url).netloc.lower()

                    if current_domain != start_domain:
                        self.log(
                            f"[SKIP] External domain: {url}"
                        )
                        continue

                self.log("")
                self.log(
                    f"[CRAWL] Depth {depth}: {url}"
                )

                # -----------------------------------------------------
                # ROBOTS.TXT
                # -----------------------------------------------------
                self.log("[1/7] Checking robots.txt...")

                try:
                    allowed = await self.robots.is_allowed(
                        url,
                        client,
                    )
                except Exception as e:
                    self.log(
                        f"[ROBOTS ERROR] "
                        f"{type(e).__name__}: {e}"
                    )
                    allowed = False

                if not allowed:
                    self.log(
                        f"[BLOCKED] robots.txt: {url}"
                    )
                    continue

                self.log("[ROBOTS] Allowed.")

                # -----------------------------------------------------
                # REQUEST
                # -----------------------------------------------------
                response = None

                for attempt in range(
                    1,
                    self.max_retries + 1,
                ):
                    if state.stop_event.is_set():
                        break

                    try:
                        self.log(
                            f"[2/7] HTTP request "
                            f"(attempt {attempt}/"
                            f"{self.max_retries})..."
                        )

                        response = await client.get(url)

                        self.log(
                            f"[HTTP] "
                            f"{response.status_code} "
                            f"{response.reason_phrase}"
                        )

                        if response.status_code == 429:
                            if attempt < self.max_retries:
                                delay = (
                                    2 ** (attempt - 1)
                                    + random.uniform(0.2, 0.8)
                                )

                                self.log(
                                    f"[RATE LIMITED] "
                                    f"Retrying in "
                                    f"{delay:.1f}s..."
                                )

                                await asyncio.sleep(delay)
                                continue

                            self.log(
                                "[RATE LIMITED] "
                                "Giving up."
                            )
                            break

                        if response.status_code in {
                            500,
                            502,
                            503,
                            504,
                        }:
                            if attempt < self.max_retries:
                                delay = (
                                    2 ** (attempt - 1)
                                    + random.uniform(0.2, 0.8)
                                )

                                self.log(
                                    f"[SERVER ERROR] "
                                    f"Retrying in "
                                    f"{delay:.1f}s..."
                                )

                                await asyncio.sleep(delay)
                                continue

                        break

                    except httpx.TimeoutException as e:
                        self.log(
                            f"[TIMEOUT] {type(e).__name__}: {e}"
                        )

                        if attempt < self.max_retries:
                            delay = (
                                2 ** (attempt - 1)
                                + random.uniform(0.2, 0.8)
                            )
                            await asyncio.sleep(delay)
                        else:
                            self.log(
                                "[TIMEOUT] "
                                "Maximum retries reached."
                            )

                    except httpx.RequestError as e:
                        self.log(
                            f"[NETWORK ERROR] "
                            f"{type(e).__name__}: {e}"
                        )

                        if attempt < self.max_retries:
                            delay = (
                                2 ** (attempt - 1)
                                + random.uniform(0.2, 0.8)
                            )
                            await asyncio.sleep(delay)

                    except Exception as e:
                        self.log(
                            f"[HTTP ERROR] "
                            f"{type(e).__name__}: {e}"
                        )
                        break

                if response is None:
                    continue

                if response.status_code >= 400:
                    self.log(
                        f"[SKIP] HTTP "
                        f"{response.status_code}: {url}"
                    )
                    continue

                # -----------------------------------------------------
                # CONTENT TYPE
                # -----------------------------------------------------
                self.log("[3/7] Checking content type...")

                content_type = (
                    response.headers
                    .get("Content-Type", "")
                    .lower()
                )

                if (
                    "text/html" not in content_type
                    and "application/xhtml+xml"
                    not in content_type
                ):
                    self.log(
                        f"[SKIP] Not HTML: "
                        f"{content_type or 'unknown'}"
                    )
                    continue

                final_url = normalize_url(
                    str(response.url)
                )

                if final_url is None:
                    self.log(
                        "[SKIP] Could not normalize "
                        "final URL."
                    )
                    continue

                # -----------------------------------------------------
                # PARSE
                # -----------------------------------------------------
                self.log("[4/7] Parsing HTML...")

                try:
                    parsed = await asyncio.to_thread(
                        parse_html,
                        response.text,
                        final_url,
                    )
                except Exception as e:
                    self.log(
                        f"[PARSE ERROR] "
                        f"{type(e).__name__}: {e}"
                    )
                    continue

                title = parsed.get(
                    "title",
                    "",
                )
                content = parsed.get(
                    "content",
                    "",
                )
                description = parsed.get(
                    "description",
                    "",
                )
                links = parsed.get(
                    "links",
                    [],
                )

                self.log(
                    f"[PARSE] Title: "
                    f"{title or '(no title)'}"
                )
                self.log(
                    f"[PARSE] Content: "
                    f"{len(content):,} characters"
                )
                self.log(
                    f"[PARSE] Links: "
                    f"{len(links)}"
                )

                if not content.strip():
                    self.log(
                        "[SKIP] No usable page text."
                    )
                    continue

                # -----------------------------------------------------
                # EMBEDDING
                # -----------------------------------------------------
                self.log("[5/7] Generating embedding...")

                text_to_embed = (
                    f"{title}\n"
                    f"{description}\n"
                    f"{content}"
                ).strip()

                try:
                    vector = await asyncio.to_thread(
                        self.embedder.encode,
                        text_to_embed,
                    )
                except Exception as e:
                    self.log(
                        f"[EMBEDDING ERROR] "
                        f"{type(e).__name__}: {e}"
                    )
                    continue

                self.log("[EMBEDDING] Complete.")

                # -----------------------------------------------------
                # DOCUMENT
                # -----------------------------------------------------
                domain = urlparse(
                    final_url
                ).netloc.lower()

                document = Document(
                    url=final_url,
                    title=title,
                    content=content,
                    description=description,
                    domain=domain,
                    crawled_at=datetime.now(
                        timezone.utc
                    ),
                    vector=vector,
                )

                await write_queue.put(
                    (
                        document,
                        links,
                    )
                )

                # -----------------------------------------------------
                # COUNT
                # -----------------------------------------------------
                reached_limit = await state.increment()

                self.log(
                    f"[6/7] Page accepted "
                    f"({state.pages_crawled}/"
                    f"{self.max_pages})"
                )

                if reached_limit:
                    self.log(
                        "[INFO] Maximum page count reached."
                    )

                # -----------------------------------------------------
                # DISCOVER LINKS
                # -----------------------------------------------------
                added = 0

                for link in links:
                    if state.stop_event.is_set():
                        break

                    normalized_link = normalize_url(
                        link,
                        final_url,
                    )

                    if not normalized_link:
                        continue

                    if self.same_domain:
                        link_domain = (
                            urlparse(
                                normalized_link
                            ).netloc.lower()
                        )

                        if link_domain != start_domain:
                            continue

                    async with visited_lock:
                        if normalized_link in visited:
                            continue

                    await url_queue.put(
                        (
                            normalized_link,
                            depth + 1,
                        )
                    )

                    added += 1

                self.log(
                    f"[7/7] Queued {added} new URLs."
                )

                if self.request_delay > 0:
                    await asyncio.sleep(
                        self.request_delay
                    )

            except asyncio.CancelledError:
                raise

            except Exception as e:
                self.log(
                    f"[CRAWLER ERROR] {url}\n"
                    f"                 "
                    f"{type(e).__name__}: {e}"
                )

            finally:
                state.active_workers -= 1
                url_queue.task_done()

    async def _writer(
        self,
        write_queue: asyncio.Queue,
    ) -> None:

        while True:
            item = await write_queue.get()

            if item is None:
                write_queue.task_done()
                break

            doc, links = item

            try:
                doc_id = self.database.add_document(
                    doc
                )

                for link in links:
                    self.database.add_link(
                        doc_id,
                        link
                    )

                self.log(
                    f"[INDEXED] "
                    f"{doc.title or '(no title)'}"
                )

            except Exception as e:
                self.log(
                    f"[DATABASE ERROR] "
                    f"{type(e).__name__}: {e}"
                )

            finally:
                write_queue.task_done()
```
