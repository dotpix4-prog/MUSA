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

    def crawl(self, url: str, max_pages: int = 10):
        import asyncio
        crawler = Crawler(self.database, max_pages=max_pages)
        return asyncio.run(crawler.crawl(url))

    def search(self, query: str, top_n: int = 5):
        searcher = HybridSearcher(self.database)
        return searcher.search(query, top_n=top_n)

    def ask(self, query: str):
        # 1. Retrieve
        searcher = HybridSearcher(self.database)
        docs = searcher.search(query, top_n=5)

        if not docs:
            return None, []

        # 2. Generate
        # Priority: Check env vars first, then Config (e.g. .env file)
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            try:
                api_key = Config().groq_api_key
            except EnvironmentError:
                api_key = None

        if not api_key:
            return "Error: GROQ_API_KEY not found in environment secrets.", []

        generator = Generator(api_key)
        answer = generator.generate_answer(query, docs)

        # 3. Cite
        citations = generator.extract_citations(answer, docs)

        return answer, citations

    def get_stats(self):
        return {
            "document_count": self.database.count_documents()
        }

    def clear_index(self):
        self.database.clear_index()

    def close(self):
        self.database.close()