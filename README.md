# 🔍 MUSA: AI-Powered Semantic Search Engine

MUSA is a high-performance, command-line and web-based search engine built from the ground up in Python. It implements a modern **Retrieval-Augmented Generation (RAG)** pipeline, combining traditional lexical search with state-of-the-art semantic embeddings to provide cited, AI-generated answers based on real-time web data.

## 🚀 Key Features

- **Asynchronous Web Crawling**: A high-concurrency crawler utilizing `httpx` and `asyncio` to index websites rapidly without blocking the event loop.
- **Hybrid Retrieval**: Combines **BM25 (Lexical)** and **Dense Vector (Semantic)** search to ensure both keyword precision and conceptual relevance.
- **Efficient Vector Storage**: Powered by **FAISS (Facebook AI Similarity Search)** for $O(\log N)$ approximate nearest neighbor retrieval.
- **Reciprocal Rank Fusion (RRF)**: A sophisticated ranking algorithm that merges multiple search streams into a single, optimized result list.
- **LLM-Powered QA**: Integrates **Claude 3.5 Sonnet** to synthesize retrieved documents into concise, accurate answers with inline citations.
- **Interactive Web Portal**: A sleek **Streamlit** dashboard for real-time indexing and querying.

## 🛠️ Technical Architecture

### The Pipeline
`User Query` $\rightarrow$ `Hybrid Retrieval (BM25 + FAISS)` $\rightarrow$ `RRF Re-ranking` $\rightarrow$ `LLM Synthesis` $\rightarrow$ `Cited Answer`

### Deep Dive
- **Embedding Model**: Uses `all-MiniLM-L6-v2` to project text into a 384-dimensional vector space.
- **Normalization**: All vectors are L2-normalized, allowing the system to use Inner Product search as a mathematically exact proxy for Cosine Similarity.
- **Concurrency**: Employs a Worker-Writer pattern. Multiple async workers handle network I/O and CPU-bound embedding tasks, while a dedicated sequential writer ensures SQLite database integrity.
- **Storage**: SQLite with FTS5 extension for lexical search and a serialized FAISS index for semantic search.

## 📦 Installation & Setup

### Prerequisites
- Python 3.10+
- Anthropic API Key

### Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/musa-search.git
   cd musa-search
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set your API key:
   ```bash
   export ANTHROPIC_API_KEY='your-api-key-here'
   ```

### Running the App
To launch the interactive web portal:
```bash
streamlit run src/musa/gui.py
```

## 📈 Performance Metrics
- **Retrieval Complexity**: Reduced from $O(N)$ linear scan to $O(\log N)$ via FAISS.
- **Ingestion Speed**: Multi-threaded asynchronous fetching allows for $N\times$ faster indexing compared to sequential crawling.
