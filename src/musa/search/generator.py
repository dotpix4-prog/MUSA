import re

from groq import Groq

from musa.storage.models import Document


class Generator:
    """Handles LLM-based answer generation using a RAG pipeline via Groq."""

    # Hard limits to prevent oversized Groq requests.
    MAX_DOCUMENTS = 5
    MAX_CHARS_PER_DOCUMENT = 5000
    MAX_TOTAL_CONTEXT_CHARS = 18000

    def __init__(self, api_key):
        self.client = Groq(api_key=api_key)

        self.system_prompt = (
            "You are a helpful and precise search assistant. "
            "Use the provided context to answer the user's query.\n\n"
            "Rules:\n"
            "1. Be concise and accurate.\n"
            "2. Use ONLY the provided context. Do not use outside knowledge.\n"
            "3. Cite sources using [1], [2], etc., based on the source "
            "numbering provided in the context.\n"
            "4. If the answer is not contained within the context, "
            "state clearly that you do not know.\n"
            "5. Format your response in Markdown."
        )

    def _trim_document(self, content):
        """
        Trim a document so large webpages cannot consume the entire
        LLM context window.
        """

        if not content:
            return ""

        content = str(content).strip()

        if len(content) <= self.MAX_CHARS_PER_DOCUMENT:
            return content

        # Keep the beginning and end because useful information can
        # appear in either place.
        half = self.MAX_CHARS_PER_DOCUMENT // 2

        return (
            content[:half]
            + "\n\n[...content truncated...]\n\n"
            + content[-half:]
        )

    def _format_context(self, docs):
        """
        Formats only a limited amount of retrieved content into the prompt.
        """

        context_parts = []
        total_chars = 0

        # Never send more than MAX_DOCUMENTS to the LLM.
        selected_docs = docs[: self.MAX_DOCUMENTS]

        for i, doc in enumerate(selected_docs, 1):

            title = getattr(
                doc,
                "title",
                "",
            ) or "Untitled"

            url = getattr(
                doc,
                "url",
                "",
            ) or ""

            content = getattr(
                doc,
                "content",
                "",
            ) or ""

            content = self._trim_document(
                content
            )

            # Calculate the approximate size this source would add.
            part = (
                "Source [{}]: {}\n"
                "URL: {}\n"
                "Content: {}\n"
            ).format(
                i,
                title,
                url,
                content,
            )

            # Enforce the total context limit.
            remaining = (
                self.MAX_TOTAL_CONTEXT_CHARS
                - total_chars
            )

            if remaining <= 0:
                break

            if len(part) > remaining:

                # Keep the source metadata and as much content
                # as fits within the remaining budget.
                header = (
                    "Source [{}]: {}\n"
                    "URL: {}\n"
                    "Content: "
                ).format(
                    i,
                    title,
                    url,
                )

                available = (
                    remaining
                    - len(header)
                    - len("\n")
                )

                if available <= 0:
                    break

                content = content[:available]

                part = (
                    header
                    + content
                    + "\n"
                )

            context_parts.append(part)
            total_chars += len(part)

        return "\n---\n".join(
            context_parts
        )

    def generate_answer(self, query, docs):
        """
        Generates an answer from a limited amount of retrieved context.
        """

        if not docs:
            return (
                "I couldn't find any relevant information "
                "in the indexed documents."
            )

        context = self._format_context(
            docs
        )

        messages = [
            {
                "role": "system",
                "content": self.system_prompt,
            },
            {
                "role": "user",
                "content": (
                    "Query: {}\n\n"
                    "Context:\n{}"
                ).format(
                    query,
                    context,
                ),
            },
        ]

        # Current Groq model IDs.
        models_to_try = [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "openai/gpt-oss-120b",
        ]

        last_error = None

        for model in models_to_try:

            try:

                print(
                    "[LLM] Trying model: {}".format(
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

                content = (
                    response
                    .choices[0]
                    .message
                    .content
                )

                if content:
                    return content

                last_error = (
                    "Model returned an empty response."
                )

            except Exception as e:

                last_error = e

                print(
                    "[LLM ERROR] {} failed: {}".format(
                        model,
                        e,
                    ),
                    flush=True,
                )

                # Try the next available model.
                continue

        if last_error is not None:

            return (
                "Error: I couldn't connect to any of the "
                "available AI models. Last error: {}".format(
                    last_error
                )
            )

        return (
            "Error: I couldn't connect to any of the "
            "available AI models."
        )

    def extract_citations(self, answer, docs):
        """
        Extract [1], [2], etc. citations from the generated answer.
        """

        if not answer:
            return []

        cited_indices = re.findall(
            r"\[(\d+)\]",
            answer,
        )

        cited_docs = []

        for idx_str in cited_indices:

            try:
                idx = int(idx_str)
            except ValueError:
                continue

            if 1 <= idx <= len(docs):

                doc = docs[idx - 1]

                if doc not in cited_docs:
                    cited_docs.append(doc)

        return cited_docs