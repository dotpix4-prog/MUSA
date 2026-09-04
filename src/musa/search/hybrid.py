import collections
import re

from musa.storage.database import Database
from musa.storage.models import Document


class HybridSearcher:
    """
    Hybrid retrieval pipeline for MUSA.

    Retrieval stages:

    1. Query normalization
    2. Lexical retrieval
    3. Vector retrieval
    4. Reciprocal Rank Fusion
    5. Re-ranking using:
       - exact query matches
       - title matches
       - query-term coverage
       - phrase matches
    """

    def __init__(
        self,
        database,
        k=60,
    ):
        self.database = database
        self.k = k

        self.stopwords = {
            "a",
            "an",
            "and",
            "are",
            "as",
            "at",
            "be",
            "by",
            "for",
            "from",
            "how",
            "i",
            "in",
            "is",
            "it",
            "of",
            "on",
            "or",
            "that",
            "the",
            "this",
            "to",
            "was",
            "what",
            "when",
            "where",
            "which",
            "who",
            "why",
            "with",
        }

    def _normalize_query(self, query):
        query = str(query or "").lower().strip()

        query = re.sub(
            r"[^a-z0-9_\-\s]",
            " ",
            query,
        )

        tokens = query.split()

        useful_tokens = [
            token
            for token in tokens
            if token not in self.stopwords
            and len(token) > 1
        ]

        return {
            "original": query,
            "tokens": useful_tokens,
            "text": " ".join(useful_tokens),
        }

    def _safe_lexical_query(self, tokens):
        """
        Create an FTS5 query from useful query terms.

        OR is intentionally used here so an entity such as
        'Yhwach' can still retrieve a document even when the
        rest of the natural-language question isn't present.
        """

        if not tokens:
            return None

        safe_tokens = []

        for token in tokens:
            token = re.sub(
                r'["*():]',
                "",
                token,
            )

            if token:
                safe_tokens.append(
                    '"{}"'.format(token)
                )

        if not safe_tokens:
            return None

        return " OR ".join(
            safe_tokens
        )

    def _rerank(self, query_info, documents):
        """
        Re-rank retrieved documents with entity-aware signals.

        This is especially useful for questions such as:

            Who was Yhwach?
            What is Ichigo?
            Who is Batman?

        because exact entity matches receive a strong boost.
        """

        original = query_info["original"]
        tokens = query_info["tokens"]

        if not documents:
            return []

        scored = []

        for doc in documents:

            title = (
                str(doc.title or "")
                .lower()
            )

            content = (
                str(doc.content or "")
                .lower()
            )

            description = (
                str(doc.description or "")
                .lower()
            )

            combined = (
                title
                + "\n"
                + description
                + "\n"
                + content
            )

            score = 0.0

            # -------------------------------------------------
            # Exact phrase match
            # -------------------------------------------------
            if (
                original
                and original in combined
            ):
                score += 8.0

            # -------------------------------------------------
            # Exact useful token match
            # -------------------------------------------------
            matched = 0

            for token in tokens:

                if token in title:
                    score += 6.0
                    matched += 1

                elif token in description:
                    score += 2.5
                    matched += 1

                elif token in content:
                    score += 1.5
                    matched += 1

            # -------------------------------------------------
            # Entity/title coverage
            # -------------------------------------------------
            if tokens:

                coverage = (
                    matched
                    / len(tokens)
                )

                score += coverage * 8.0

            # -------------------------------------------------
            # Put large exact-name matches ahead
            # -------------------------------------------------
            if (
                len(tokens) == 1
                and tokens[0]
                and tokens[0] in title
            ):
                score += 15.0

            # Existing RRF score is retained.
            score += float(
                getattr(doc, "score", 0.0)
                or 0.0
            )

            scored.append(
                (
                    score,
                    doc,
                )
            )

        scored.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        results = []

        for score, doc in scored:

            doc.score = score

            results.append(
                doc
            )

        return results

    def search(
        self,
        query,
        top_n=5,
    ):
        query_info = self._normalize_query(
            query
        )

        tokens = query_info["tokens"]

        if not tokens:
            return []

        # -----------------------------------------------------
        # 1. Lexical retrieval
        # -----------------------------------------------------
        lexical_query = self._safe_lexical_query(
            tokens
        )

        lexical_results = []

        if lexical_query:

            try:
                lexical_results = (
                    self.database.lexical_search(
                        lexical_query,
                        top_n=top_n * 4,
                    )
                )
            except Exception as e:
                print(
                    "[SEARCH] Lexical search failed: {}".format(
                        e
                    ),
                    flush=True,
                )

        # -----------------------------------------------------
        # 2. Semantic retrieval
        # -----------------------------------------------------
        semantic_results = []

        try:

            from musa.search.embeddings import Embedder

            embedder = Embedder()

            query_vector = embedder.encode(
                query
            )

            semantic_results = (
                self.database.semantic_search(
                    query_vector,
                    top_n=top_n * 4,
                )
            )

        except Exception as e:

            print(
                "[SEARCH] Semantic search failed: {}".format(
                    e
                ),
                flush=True,
            )

        # -----------------------------------------------------
        # 3. Fallback lexical retrieval
        #
        # If FTS didn't return anything, try searching for
        # the strongest individual entity term.
        # -----------------------------------------------------
        if not lexical_results and tokens:

            strongest = sorted(
                tokens,
                key=len,
                reverse=True,
            )[0]

            try:

                lexical_results = (
                    self.database.lexical_search(
                        '"{}"'.format(
                            strongest
                        ),
                        top_n=top_n * 4,
                    )
                )

            except Exception:
                pass

        # -----------------------------------------------------
        # 4. Reciprocal Rank Fusion
        # -----------------------------------------------------
        scores = collections.defaultdict(
            float
        )

        docs_map = {}

        for rank, doc in enumerate(
            lexical_results,
            1,
        ):

            scores[doc.url] += (
                1.0
                / (
                    self.k + rank
                )
            )

            docs_map[
                doc.url
            ] = doc

        for rank, doc in enumerate(
            semantic_results,
            1,
        ):

            scores[doc.url] += (
                1.0
                / (
                    self.k + rank
                )
            )

            if doc.url not in docs_map:
                docs_map[
                    doc.url
                ] = doc

        if not scores:
            return []

        # -----------------------------------------------------
        # 5. Build initial candidate list
        # -----------------------------------------------------
        candidate_urls = sorted(
            scores.keys(),
            key=lambda url: scores[url],
            reverse=True,
        )

        candidates = []

        for url in candidate_urls:

            doc = docs_map[url]

            doc.score = scores[url]

            candidates.append(
                doc
            )

        # Keep a much larger candidate pool before reranking.
        candidates = candidates[
            : max(top_n * 4, 10)
        ]

        # -----------------------------------------------------
        # 6. Entity-aware reranking
        # -----------------------------------------------------
        candidates = self._rerank(
            query_info,
            candidates,
        )

        return candidates[
            :top_n
        ]