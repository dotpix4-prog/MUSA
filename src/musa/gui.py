```python
import asyncio
import sys
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------
# Make the src directory importable on Streamlit Cloud.
# ---------------------------------------------------------
root_dir = Path(__file__).resolve().parent.parent

if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from musa.crawler.crawler import Crawler
from musa.engine import MusaEngine


# ---------------------------------------------------------
# Page configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="MUSA | AI Search Engine",
    page_icon="🔍",
    layout="wide",
)


# ---------------------------------------------------------
# Styling
# ---------------------------------------------------------
st.markdown(
    """
    <style>
    .main {
        background-color: #f8f9fa;
    }

    .stButton > button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
    }

    .source-card {
        padding: 10px;
        border-radius: 10px;
        border: 1px solid #ddd;
        margin-bottom: 10px;
        background-color: white;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# Engine
# ---------------------------------------------------------
if "engine" not in st.session_state:
    st.session_state.engine = MusaEngine()

engine = st.session_state.engine


# ---------------------------------------------------------
# Sidebar
# ---------------------------------------------------------
with st.sidebar:
    st.title("⚙️ MUSA Control")

    st.markdown("---")

    stats = engine.get_stats()

    st.metric(
        "Total Documents",
        stats["document_count"],
    )

    st.markdown("---")

    if st.button(
        "🗑️ Clear Index",
        use_container_width=True,
    ):
        engine.clear_index()
        st.rerun()

    st.markdown("---")

    st.markdown(
        "### 🛠️ Current Stack"
    )

    st.caption("• Streamlit")
    st.caption("• Async HTTP crawler")
    st.caption("• SQLite + FTS5")
    st.caption("• FAISS vector index")
    st.caption("• Hybrid retrieval")
    st.caption("• Groq-powered QA")


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------
st.title("🔍 MUSA AI Search")

st.markdown(
    "An experimental AI-powered search engine "
    "that crawls, indexes and retrieves web content."
)


tab1, tab2 = st.tabs(
    [
        "💬 Ask MUSA",
        "🌐 Index Website",
    ]
)


# =========================================================
# ASK TAB
# =========================================================
with tab1:

    query = st.text_input(
        "What would you like to know?",
        placeholder=(
            "Ask something about your indexed websites..."
        ),
    )

    if query:

        with st.spinner(
            "Searching MUSA..."
        ):

            try:
                answer, citations = engine.ask(
                    query
                )

                if answer:

                    st.markdown(
                        "### 🤖 MUSA Answer"
                    )

                    st.markdown(
                        answer
                    )

                    if citations:

                        st.markdown("---")
                        st.markdown(
                            "#### 📚 Sources"
                        )

                        for i, doc in enumerate(
                            citations,
                            1,
                        ):
                            st.markdown(
                                f"""
                                <div class="source-card">
                                    <strong>
                                        {i}. {doc.title}
                                    </strong>
                                    <br>
                                    <a href="{doc.url}"
                                       target="_blank">
                                        {doc.url}
                                    </a>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                else:

                    st.warning(
                        "MUSA couldn't find enough "
                        "relevant information."
                    )

            except Exception as e:

                st.error(
                    f"Search error: "
                    f"{type(e).__name__}: {e}"
                )


# =========================================================
# CRAWLER TAB
# =========================================================
with tab2:

    st.subheader(
        "🌐 Add Knowledge"
    )

    url = st.text_input(
        "Website URL",
        placeholder=(
            "https://example.com"
        ),
        key="crawl_url",
    )

    pages = st.number_input(
        "Maximum Pages",
        min_value=1,
        max_value=50,
        value=3,
        step=1,
    )

    depth = st.number_input(
        "Maximum Crawl Depth",
        min_value=0,
        max_value=5,
        value=2,
        step=1,
    )

    if st.button(
        "🚀 Start Crawling",
        use_container_width=True,
    ):

        if not url.strip():

            st.error(
                "Please enter a URL first."
            )

        else:

            logs = []

            log_area = st.empty()

            def log(message: str) -> None:

                logs.append(message)

                # Keep the displayed output
                # from growing uncontrollably.
                visible_logs = logs[-100:]

                log_area.code(
                    "\n".join(
                        visible_logs
                    ),
                    language="text",
                )

            with st.status(
                f"Crawling {url}...",
                expanded=True,
            ) as status:

                log(
                    "Initializing MUSA crawler..."
                )

                try:

                    crawler = Crawler(
                        database=engine.database,
                        max_pages=int(
                            pages
                        ),
                        max_depth=int(
                            depth
                        ),
                        same_domain=True,
                        concurrency=2,
                        request_delay=1.0,
                        log_callback=log,
                    )

                    result = asyncio.run(
                        crawler.crawl(
                            url.strip()
                        )
                    )

                    log("")
                    log(
                        f"Indexed documents in database: "
                        f"{result}"
                    )

                    status.update(
                        label=(
                            "Crawl Complete"
                        ),
                        state="complete",
                        expanded=True,
                    )

                except Exception as e:

                    log(
                        f"[FATAL ERROR] "
                        f"{type(e).__name__}: {e}"
                    )

                    st.error(
                        f"Crawler failed: "
                        f"{type(e).__name__}: {e}"
                    )

                    status.update(
                        label="Crawl Failed",
                        state="error",
                        expanded=True,
                    )
```
