import re
from groq import Groq
from musa.storage.models import Document

class Generator:
    """Handles LLM-based answer generation using a RAG pipeline via Groq."""

    def __init__(self, api_key: str) -> None:
        self.client = Groq(api_key=api_key)
        self.system_prompt = (
            "You are a helpful and precise search assistant. Use the provided context "
            "to answer the user's query.\n\n"
            "Rules:\n"
            "1. Be concise and accurate.\n"
            "2. Use ONLY the provided context. Do not use outside knowledge.\n"
            "3. Cite sources using [1], [2], etc., based on the source numbering provided in the context.\n"
            "4. If the answer is not contained within the context, state clearly that you do not know.\n"
            "5. Format your response in Markdown."
        )

    def _format_context(self, docs: list[Document]) -> str:
        """Formats documents into a numbered source block for the prompt."""
        context_parts = []
        for i, doc in enumerate(docs, 1):
            part = (
                f"Source [{i}]: {doc.title}\n"
                f"URL: {doc.url}\n"
                f"Content: {doc.content}\n"
            )
            context_parts.append(part)
        return "\n---\n".join(context_parts)

    def generate_answer(self, query: str, docs: list[Document]) -> str:
        """Generates a synthesized answer based on the retrieved documents."""
        context = self._format_context(docs)

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Query: {query}\n\nContext:\n{context}"}
        ]

        # Try a few different stable model IDs in order of availability
        models_to_try = [
            "llama-3.3-70b-versatile",
            "llama3-8b-8192",
            "mixtral-8x7b-32768",
            "llama3-70b-8192"
        ]

        for model in models_to_try:
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.1,
                    max_tokens=1024,
                )
                return response.choices[0].message.content
            except Exception as e:
                print(f"Model {model} failed: {e}")
                continue

        return "Error: I couldn't connect to any of the available AI models. Please check your API key."

    def extract_citations(self, answer: str, docs: list[Document]) -> list[Document]:
        """Extracts cited documents from the answer based on [n] patterns."""
        cited_indices = re.findall(r"\[(\d+)\]", answer)
        cited_docs = []

        for idx_str in cited_indices:
            idx = int(idx_str)
            if 1 <= idx <= len(docs):
                doc = docs[idx - 1]
                if doc not in cited_docs:
                    cited_docs.append(doc)

        return cited_docs
