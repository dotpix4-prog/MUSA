import os

from musa.storage.database import Database
from musa.crawler.crawler import Crawler
from musa.search.hybrid import HybridSearcher
from musa.search.generator import Generator
from musa.config import Config


class MusaEngine:

    def __init__(self):
        self.config = Config()
        self.database = Database()

    def crawl(
        self,
        url,
        max_pages=10,
        max_depth=2,
    ):
        import asyncio

        crawler = Crawler(
            self.database,
            max_pages=max_pages,
            max_depth=max_depth,
        )

        return asyncio.run(
            crawler.crawl(url)
        )

    def search(
        self,
        query,
        top_n=5,
    ):
        searcher = HybridSearcher(
            self.database
        )

        return searcher.search(
            query,
            top_n=top_n,
        )

    def ask(
        self,
        query,
        language="English",
    ):

        searcher = HybridSearcher(
            self.database
        )

        docs = searcher.search(
            query,
            top_n=5,
        )

        if not docs:
            return (
                "I could not find any relevant indexed sources.",
                [],
            )

        print(
            "[SEARCH] Query: {}".format(
                query
            ),
            flush=True,
        )

        for i, doc in enumerate(
            docs,
            1,
        ):

            print(
                "[SEARCH] #{} {} | score={}".format(
                    i,
                    doc.title,
                    getattr(
                        doc,
                        "score",
                        None,
                    ),
                ),
                flush=True,
            )

        api_key = os.environ.get(
            "GROQ_API_KEY"
        )

        if not api_key:

            try:
                api_key = (
                    self.config
                    .groq_api_key
                )
            except Exception:
                api_key = None

        if not api_key:

            return (
                "Error: GROQ_API_KEY not found.",
                [],
            )

        generator = Generator(
            api_key
        )

        answer = generator.generate_answer(
            query,
            docs,
            language=language,
        )

        citations = (
            generator.extract_citations(
                answer,
                docs,
            )
        )

        return (
            answer,
            citations,
        )

    def get_stats(self):
        return {
            "document_count": (
                self.database
                .count_documents()
            )
        }

    def clear_index(self):
        self.database.clear_index()

    def close(self):
        self.database.close()