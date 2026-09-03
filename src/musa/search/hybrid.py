import collections
from musa.storage.database import Database
from musa.storage.models import Document

class HybridSearcher:
    def __init__(self, database: Database, k: int = 60) -> None:
        self.database = database
        self.k = k

    def search(self, query: str, top_n: int = 5) -> list[Document]:
        # 1. Lexical Search
        lexical_results = self.database.lexical_search(query, top_n=top_n * 2)

        # 2. Semantic Search
        from musa.search.embeddings import Embedder
        embedder = Embedder()
        query_vector = embedder.encode(query)
        semantic_results = self.database.semantic_search(query_vector, top_n=top_n * 2)

        # 3. Reciprocal Rank Fusion (RRF)
        # Map URL -> Score
        scores = collections.defaultdict(float)

        # Map URL -> Document object to retrieve it later
        docs_map: dict[str, Document] = {}

        for rank, doc in enumerate(lexical_results, 1):
            scores[doc.url] += 1.0 / (self.k + rank)
            docs_map[doc.url] = doc

        for rank, doc in enumerate(semantic_results, 1):
            scores[doc.url] += 1.0 / (self.k + rank)
            if doc.url not in docs_map:
                docs_map[doc.url] = doc

        # Sort by score descending
        sorted_urls = sorted(scores.keys(), key=lambda url: scores[url], reverse=True)

        results = []
        for url in sorted_urls[:top_n]:
            doc = docs_map[url]
            doc.score = scores[url]
            results.append(doc)

        return results
