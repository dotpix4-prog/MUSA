import re

from groq import Groq


class Generator:
    """
    Generates answers from retrieved MUSA sources.

    MUSA can explicitly control the output language instead
    of allowing the language of the retrieved source to leak
    into the answer.
    """

    MAX_DOCUMENTS = 5
    CHUNK_SIZE = 1800
    CHUNK_OVERLAP = 250
    MAX_CHUNKS = 7
    MAX_TOTAL_CONTEXT = 16000

    SUPPORTED_LANGUAGES = {
        "English": "English",
        "German": "German",
        "Urdu": "Urdu",
        "Spanish": "Spanish",
        "French": "French",
    }

    def __init__(self, api_key):
        self.client = Groq(
            api_key=api_key
        )

        self.base_system_prompt = (
            "You are MUSA, a precise search assistant.\n\n"
            "You must answer the user's question using ONLY "
            "the provided indexed sources.\n\n"
            "Rules:\n"
            "1. Be accurate and concise.\n"
            "2. Never invent facts.\n"
            "3. Do not use outside knowledge.\n"
            "4. Cite factual claims using [1], [2], etc.\n"
            "5. Only cite a source when that source supports "
            "the claim.\n"
            "6. If the answer is not contained in the supplied "
            "sources, clearly say that the information could "
            "not be found in the indexed sources.\n"
            "7. Format the answer using Markdown.\n"
        )

    def _build_system_prompt(self, language):
        language = self.SUPPORTED_LANGUAGES.get(
            language,
            "English",
        )

        return (
            self.base_system_prompt
            + "\n"
            + "LANGUAGE REQUIREMENT:\n"
            + "Write the ENTIRE answer in {}.\n".format(
                language
            )
            + "Do not switch languages because the source "
            "documents are written in another language.\n"
            + "Source text may be in any language, but your "
            "final answer must be entirely in {}.\n".format(
                language
            )
            + "Keep names, titles, URLs and citation markers "
            "such as [1] unchanged when appropriate."
        )

    def _tokenize(self, text):
        return set(
            re.findall(
                r"\b[a-zA-Z0-9_\-]{2,}\b",
                str(text).lower(),
            )
        )

    def _make_chunks(self, text):
        if not text:
            return []

        text = str(text).strip()

        if len(text) <= self.CHUNK_SIZE:
            return [text]

        chunks = []

        start = 0
        text_length = len(text)

        while start < text_length:

            end = min(
                start + self.CHUNK_SIZE,
                text_length,
            )

            chunk = text[
                start:end
            ].strip()

            if chunk:
                chunks.append(chunk)

            if end >= text_length:
                break

            start = max(
                0,
                end - self.CHUNK_OVERLAP,
            )

        return chunks

    def _score_chunk(
        self,
        query,
        chunk,
        title,
    ):
        query_lower = (
            str(query)
            .lower()
            .strip()
        )

        chunk_lower = (
            str(chunk)
            .lower()
        )

        title_lower = (
            str(title or "")
            .lower()
        )

        query_tokens = self._tokenize(
            query_lower
        )

        chunk_tokens = self._tokenize(
            chunk_lower
        )

        if not query_tokens:
            return 0.0

        score = 0.0

        # Exact question/phrase.
        if query_lower in chunk_lower:
            score += 30.0

        matched = 0

        for token in query_tokens:

            if token in chunk_tokens:
                score += 5.0
                matched += 1

            if token in title_lower:
                score += 8.0

        if query_tokens:
            coverage = (
                matched
                / len(query_tokens)
            )

            score += (
                coverage * 20.0
            )

        return score

    def _select_relevant_chunks(
        self,
        query,
        docs,
    ):
        candidates = []

        selected_docs = docs[
            :self.MAX_DOCUMENTS
        ]

        for source_number, doc in enumerate(
            selected_docs,
            1,
        ):

            title = (
                getattr(
                    doc,
                    "title",
                    "",
                )
                or "Untitled"
            )

            url = (
                getattr(
                    doc,
                    "url",
                    "",
                )
                or ""
            )

            content = (
                getattr(
                    doc,
                    "content",
                    "",
                )
                or ""
            )

            chunks = self._make_chunks(
                content
            )

            for chunk_number, chunk in enumerate(
                chunks
            ):

                score = self._score_chunk(
                    query,
                    chunk,
                    title,
                )

                candidates.append(
                    {
                        "score": score,
                        "source_number": source_number,
                        "chunk_number": chunk_number,
                        "title": title,
                        "url": url,
                        "text": chunk,
                    }
                )

        candidates.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        selected = []
        source_counts = {}

        for item in candidates:

            source = item[
                "source_number"
            ]

            count = source_counts.get(
                source,
                0,
            )

            if count >= 3:
                continue

            selected.append(
                item
            )

            source_counts[source] = (
                count + 1
            )

            if len(selected) >= self.MAX_CHUNKS:
                break

        return selected

    def _format_context(
        self,
        query,
        docs,
    ):
        chunks = self._select_relevant_chunks(
            query,
            docs,
        )

        if not chunks:
            return ""

        parts = []
        total_chars = 0

        for item in chunks:

            part = (
                "Source [{}]\n"
                "Title: {}\n"
                "URL: {}\n"
                "Passage:\n{}\n"
            ).format(
                item["source_number"],
                item["title"],
                item["url"],
                item["text"],
            )

            remaining = (
                self.MAX_TOTAL_CONTEXT
                - total_chars
            )

            if remaining <= 0:
                break

            if len(part) > remaining:
                part = part[:remaining]

            parts.append(part)
            total_chars += len(part)

        return "\n---\n".join(
            parts
        )

    def generate_answer(
        self,
        query,
        docs,
        language="English",
    ):

        if not docs:
            return (
                "I could not find any relevant indexed sources."
            )

        context = self._format_context(
            query,
            docs,
        )

        if not context:
            return (
                "I could not find any relevant passages "
                "in the indexed sources."
            )

        system_prompt = self._build_system_prompt(
            language
        )

        messages = [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": (
                    "Question:\n{}\n\n"
                    "Indexed context:\n{}"
                ).format(
                    query,
                    context,
                ),
            },
        ]

        models_to_try = [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "openai/gpt-oss-120b",
        ]

        last_error = None

        for model in models_to_try:

            try:

                print(
                    "[LLM] Trying {}".format(
                        model
                    ),
                    flush=True,
                )

                response = (
                    self.client
                    .chat
                    .completions
                    .create(
                        model=model,
                        messages=messages,
                        temperature=0.1,
                        max_tokens=768,
                    )
                )

                answer = (
                    response
                    .choices[0]
                    .message
                    .content
                )

                if answer:
                    return answer

            except Exception as e:

                last_error = e

                print(
                    "[LLM ERROR] {}: {}".format(
                        model,
                        e,
                    ),
                    flush=True,
                )

        if last_error:

            return (
                "Error: MUSA could not generate an answer. "
                "Last error: {}".format(
                    last_error
                )
            )

        return (
            "Error: MUSA could not generate an answer."
        )

    def extract_citations(
        self,
        answer,
        docs,
    ):
        if not answer:
            return []

        cited_indices = re.findall(
            r"\[(\d+)\]",
            answer,
        )

        cited_docs = []

        for index_string in cited_indices:

            try:
                index = int(
                    index_string
                )
            except ValueError:
                continue

            if 1 <= index <= len(docs):

                doc = docs[
                    index - 1
                ]

                if doc not in cited_docs:
                    cited_docs.append(
                        doc
                    )

        return cited_docs