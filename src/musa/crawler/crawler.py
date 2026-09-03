import asyncio
import random
from datetime import datetime, timezone
from typing import Optional, Set

from urllib.parse import urlparse

import httpx

from musa.crawler.parser import parse_html
from musa.crawler.robots import Robots
from musa.crawler.url_utils import normalize_url
from musa.search.embeddings import Embedder
from musa.storage.database import Database
from musa.storage.models import Document


class CrawlState:
    def __init__(self, max_pages):
        self.pages_crawled = 0
        self.max_pages = max_pages
        self.stop_event = asyncio.Event()
        self.active_workers = 0
        self.lock = asyncio.Lock()

    async def increment(self):
        async with self.lock:
            self.pages_crawled += 1

            if self.pages_crawled >= self.max_pages:
                self.stop_event.set()
                return True

            return False


class Crawler:
    def __init__(
        self,
        database,
        max_pages=10,
        max_depth=2,
        same_domain=True,
        concurrency=2,
        request_delay=1.0,
        max_retries=3,
        log_callback=None,
    ):
        self.database = database
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.same_domain = same_domain

        self.concurrency = max(
            1,
            min(concurrency, 5)
        )

        self.request_delay = max(
            0.0,
            request_delay
        )

        self.max_retries = max(
            1,
            max_retries
        )

        self.log_callback = log_callback

        self.robots = Robots(
            user_agent="MUSA/0.1"
        )

        self.embedder = Embedder()

    def log(self, message):
        print(message, flush=True)

        if self.log_callback is not None:
            try:
                self.log_callback(message)
            except Exception:
                pass

    async def crawl(self, start_url):
        self.log("")
        self.log("=" * 60)
        self.log("MUSA CRAWLER")
        self.log("=" * 60)
        self.log("Start URL : {}".format(start_url))
        self.log("Max pages : {}".format(self.max_pages))
        self.log("Max depth : {}".format(self.max_depth))
        self.log("Workers   : {}".format(self.concurrency))
        self.log("")

        start_url = normalize_url(start_url)

        if start_url is None:
            self.log("[ERROR] Invalid URL.")
            return self.database.count_documents()

        start_domain = urlparse(
            start_url
        ).netloc.lower()

        if not start_domain:
            self.log(
                "[ERROR] Could not determine domain."
            )
            return self.database.count_documents()

        state = CrawlState(
            self.max_pages
        )

        url_queue = asyncio.Queue()
        write_queue = asyncio.Queue()

        visited = set()
        visited_lock = asyncio.Lock()

        await url_queue.put(
            (start_url, 0)
        )

        timeout = httpx.Timeout(
            connect=10.0,
            read=25.0,
            write=10.0,
            pool=10.0,
        )

        headers = {
            "User-Agent": (
                "MUSA/0.1 "
                "(educational search engine)"
            ),
            "Accept": (
                "text/html,"
                "application/xhtml+xml"
            ),
            "Accept-Language": (
                "en-US,en;q=0.9"
            ),
        }

        async with httpx.AsyncClient(
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
        ) as client:

            writer_task = asyncio.create_task(
                self._writer(
                    write_queue
                )
            )

            workers = []

            for _ in range(
                self.concurrency
            ):
                workers.append(
                    asyncio.create_task(
                        self._worker(
                            url_queue,
                            write_queue,
                            client,
                            state,
                            visited,
                            visited_lock,
                            start_domain,
                        )
                    )
                )

            try:
                while True:

                    if state.stop_event.is_set():
                        break

                    if (
                        url_queue.empty()
                        and state.active_workers == 0
                    ):
                        break

                    await asyncio.sleep(
                        0.1
                    )

            finally:
                state.stop_event.set()

                for _ in range(
                    self.concurrency
                ):
                    await url_queue.put(
                        None
                    )

                results = await asyncio.gather(
                    *workers,
                    return_exceptions=True,
                )

                for i, result in enumerate(
                    results
                ):
                    if isinstance(
                        result,
                        Exception
                    ):
                        self.log(
                            "[WORKER {} ERROR] {}: {}".format(
                                i,
                                type(result).__name__,
                                result,
                            )
                        )

                await write_queue.put(
                    None
                )

                await writer_task

        self.log("")
        self.log("=" * 60)
        self.log("CRAWL FINISHED")
        self.log("=" * 60)
        self.log(
            "Pages processed : {}".format(
                state.pages_crawled
            )
        )
        self.log(
            "Documents total : {}".format(
                self.database.count_documents()
            )
        )
        self.log("=" * 60)

        return self.database.count_documents()

    async def _worker(
        self,
        url_queue,
        write_queue,
        client,
        state,
        visited,
        visited_lock,
        start_domain,
    ):

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
                        "[SKIP] Max depth: {}".format(
                            url
                        )
                    )
                    continue

                async with visited_lock:

                    if url in visited:
                        continue

                    visited.add(url)

                if self.same_domain:

                    current_domain = (
                        urlparse(url)
                        .netloc
                        .lower()
                    )

                    if (
                        current_domain
                        != start_domain
                    ):
                        self.log(
                            "[SKIP] External domain: {}".format(
                                url
                            )
                        )
                        continue

                self.log("")
                self.log(
                    "[CRAWL] Depth {}: {}".format(
                        depth,
                        url,
                    )
                )

                # -------------------------------------------------
                # ROBOTS
                # -------------------------------------------------

                self.log(
                    "[1/7] Checking robots.txt..."
                )

                try:

                    allowed = (
                        await self.robots.is_allowed(
                            url,
                            client,
                        )
                    )

                except Exception as e:

                    self.log(
                        "[ROBOTS ERROR] {}: {}".format(
                            type(e).__name__,
                            e,
                        )
                    )

                    allowed = False

                if not allowed:

                    self.log(
                        "[BLOCKED] robots.txt: {}".format(
                            url
                        )
                    )

                    continue

                self.log(
                    "[ROBOTS] Allowed."
                )

                # -------------------------------------------------
                # HTTP
                # -------------------------------------------------

                response = None

                for attempt in range(
                    1,
                    self.max_retries + 1
                ):

                    try:

                        self.log(
                            "[2/7] HTTP request "
                            "(attempt {}/{})...".format(
                                attempt,
                                self.max_retries,
                            )
                        )

                        response = await client.get(
                            url
                        )

                        self.log(
                            "[HTTP] {} {}".format(
                                response.status_code,
                                response.reason_phrase,
                            )
                        )

                        if response.status_code == 429:

                            if (
                                attempt
                                < self.max_retries
                            ):

                                delay = (
                                    2 ** (
                                        attempt - 1
                                    )
                                    + random.uniform(
                                        0.2,
                                        0.8,
                                    )
                                )

                                self.log(
                                    "[RATE LIMITED] "
                                    "Retrying in {:.1f}s...".format(
                                        delay
                                    )
                                )

                                await asyncio.sleep(
                                    delay
                                )

                                continue

                            break

                        if response.status_code in (
                            500,
                            502,
                            503,
                            504,
                        ):

                            if (
                                attempt
                                < self.max_retries
                            ):

                                delay = (
                                    2 ** (
                                        attempt - 1
                                    )
                                    + random.uniform(
                                        0.2,
                                        0.8,
                                    )
                                )

                                self.log(
                                    "[SERVER ERROR] "
                                    "Retrying in {:.1f}s...".format(
                                        delay
                                    )
                                )

                                await asyncio.sleep(
                                    delay
                                )

                                continue

                        break

                    except httpx.TimeoutException as e:

                        self.log(
                            "[TIMEOUT] {}: {}".format(
                                type(e).__name__,
                                e,
                            )
                        )

                        if (
                            attempt
                            < self.max_retries
                        ):

                            await asyncio.sleep(
                                2 ** (
                                    attempt - 1
                                )
                            )

                    except httpx.RequestError as e:

                        self.log(
                            "[NETWORK ERROR] {}: {}".format(
                                type(e).__name__,
                                e,
                            )
                        )

                        if (
                            attempt
                            < self.max_retries
                        ):

                            await asyncio.sleep(
                                2 ** (
                                    attempt - 1
                                )
                            )

                    except Exception as e:

                        self.log(
                            "[HTTP ERROR] {}: {}".format(
                                type(e).__name__,
                                e,
                            )
                        )

                        break

                if response is None:
                    continue

                if response.status_code >= 400:

                    self.log(
                        "[SKIP] HTTP {}: {}".format(
                            response.status_code,
                            url,
                        )
                    )

                    continue

                # -------------------------------------------------
                # CONTENT TYPE
                # -------------------------------------------------

                self.log(
                    "[3/7] Checking content type..."
                )

                content_type = (
                    response.headers
                    .get(
                        "Content-Type",
                        ""
                    )
                    .lower()
                )

                if (
                    "text/html"
                    not in content_type
                    and "application/xhtml+xml"
                    not in content_type
                ):

                    self.log(
                        "[SKIP] Not HTML: {}".format(
                            content_type
                        )
                    )

                    continue

                final_url = normalize_url(
                    str(response.url)
                )

                if final_url is None:
                    continue

                # -------------------------------------------------
                # PARSER
                # -------------------------------------------------

                self.log(
                    "[4/7] Parsing HTML..."
                )

                try:

                    parsed = await asyncio.to_thread(
                        parse_html,
                        response.text,
                        final_url,
                    )

                except Exception as e:

                    self.log(
                        "[PARSE ERROR] {}: {}".format(
                            type(e).__name__,
                            e,
                        )
                    )

                    continue

                title = parsed.get(
                    "title",
                    ""
                )

                content = parsed.get(
                    "content",
                    ""
                )

                description = parsed.get(
                    "description",
                    ""
                )

                links = parsed.get(
                    "links",
                    []
                )

                self.log(
                    "[PARSE] Title: {}".format(
                        title or "(no title)"
                    )
                )

                self.log(
                    "[PARSE] Content: {:,} characters".format(
                        len(content)
                    )
                )

                self.log(
                    "[PARSE] Links: {}".format(
                        len(links)
                    )
                )

                if not content.strip():

                    self.log(
                        "[SKIP] No usable text."
                    )

                    continue

                # -------------------------------------------------
                # EMBEDDING
                # -------------------------------------------------

                self.log(
                    "[5/7] Generating embedding..."
                )

                text_to_embed = (
                    "{}\n{}\n{}".format(
                        title,
                        description,
                        content,
                    )
                ).strip()

                try:

                    vector = await asyncio.to_thread(
                        self.embedder.encode,
                        text_to_embed,
                    )

                except Exception as e:

                    self.log(
                        "[EMBEDDING ERROR] {}: {}".format(
                            type(e).__name__,
                            e,
                        )
                    )

                    continue

                # -------------------------------------------------
                # DOCUMENT
                # -------------------------------------------------

                domain = (
                    urlparse(final_url)
                    .netloc
                    .lower()
                )

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

                reached_limit = (
                    await state.increment()
                )

                self.log(
                    "[6/7] Accepted page "
                    "({}/{})".format(
                        state.pages_crawled,
                        self.max_pages,
                    )
                )

                if reached_limit:

                    self.log(
                        "[INFO] Maximum pages reached."
                    )

                # -------------------------------------------------
                # LINKS
                # -------------------------------------------------

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
                            )
                            .netloc
                            .lower()
                        )

                        if (
                            link_domain
                            != start_domain
                        ):
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
                    "[7/7] Queued {} URLs.".format(
                        added
                    )
                )

                if self.request_delay > 0:

                    await asyncio.sleep(
                        self.request_delay
                    )

            except asyncio.CancelledError:
                raise

            except Exception as e:

                self.log(
                    "[CRAWLER ERROR] {}: {}: {}".format(
                        url,
                        type(e).__name__,
                        e,
                    )
                )

            finally:

                state.active_workers -= 1
                url_queue.task_done()

    async def _writer(
        self,
        write_queue,
    ):

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
                    "[INDEXED] {}".format(
                        doc.title
                        or "(no title)"
                    )
                )

            except Exception as e:

                self.log(
                    "[DATABASE ERROR] {}: {}".format(
                        type(e).__name__,
                        e,
                    )
                )

            finally:

                write_queue.task_done()
