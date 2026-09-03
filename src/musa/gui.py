import asyncio
import sys
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------
# Make src/ importable BEFORE importing the musa package.
# ---------------------------------------------------------
SRC_DIR = Path(__file__).resolve().parent.parent

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# IMPORTANT:
# These imports must come AFTER the sys.path fix.
from musa.engine import MusaEngine
from musa.crawler.crawler import Crawler


# ---------------------------------------------------------
# Streamlit page configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="MUSA | AI Search Engine",
    page_icon="🔍",
    layout="wide",
)


# ---------------------------------------------------------
# Basic styling
# ---------------------------------------------------------
st.markdown(
    """
    <style>
    .main {
        background-color: #f8f9fa;
    }

    .source-card {
        padding: 12px;
        border-radius: 10px;
        border: 1px solid #dddddd;
        margin-bottom: 10px;
        background-color: white;
    }

    div.stButton > button {
        width: 100%;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# Initialize engine once per Streamlit session
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

    try:
        stats = engine.get_stats()

        st.metric(
            "Indexed Documents",
            stats.get("document_count", 0),
        )

    except Exception as e:

        st.warning(
            "Could not load database statistics."
        )

        st.caption(
            "{}: {}".format(
                type(e).__name__,
                e,
            )
        )

    st.markdown("---")

    if st.button(
        "🗑️ Clear Index",
        use_container_width=True,
    ):

        try:
            engine.clear_index()
            st.success("Index cleared.")
            st.rerun()

        except Exception as e:

            st.error(
                "Could not clear index: {}: {}".format(
                    type(e).__name__,
                    e,
                )
            )

    st.markdown("---")

    st.markdown("### 🛠️ MUSA Stack")

    st.caption("• Streamlit")
    st.caption("• Python")
    st.caption("• Async HTTP crawler")
    st.caption("• BeautifulSoup")
    st.caption("• SQLite + FTS5")
    st.caption("• FAISS")
    st.caption("• Groq")


# ---------------------------------------------------------
# Main heading
# ---------------------------------------------------------
st.title("🔍 MUSA AI Search")

st.write(
    "An experimental AI-powered search engine "
    "that crawls, indexes and retrieves web content."
)


# ---------------------------------------------------------
# Tabs
# ---------------------------------------------------------
search_tab, crawl_tab = st.tabs(
    [
        "💬 Ask MUSA",
        "🌐 Index Website",
    ]
)


# =========================================================
# SEARCH TAB
# =========================================================
with search_tab:

    st.subheader("Ask MUSA")

    query = st.text_input(
        "What would you like to know?",
        placeholder=(
            "Ask something about the websites "
            "you have indexed..."
        ),
        key="search_query",
    )

    if st.button(
        "🔎 Search",
        use_container_width=True,
    ):

        if not query.strip():

            st.warning(
                "Enter a question first."
            )

        else:

            with st.spinner(
                "Searching MUSA..."
            ):

                try:

                    answer, citations = engine.ask(
                        query.strip()
                    )

                    if answer:

                        st.markdown(
                            "### 🤖 MUSA Answer"
                        )

                        st.markdown(answer)

                    else:

                        st.warning(
                            "MUSA could not generate "
                            "an answer."
                        )

                    if citations:

                        st.markdown("---")

                        st.markdown(
                            "### 📚 Sources"
                        )

                        for index, doc in enumerate(
                            citations,
                            start=1,
                        ):

                            title = getattr(
                                doc,
                                "title",
                                None,
                            ) or "Untitled"

                            url = getattr(
                                doc,
                                "url",
                                None,
                            ) or ""

                            st.markdown(
                                """
                                <div class="source-card">
                                    <strong>{}. {}</strong>
                                    <br>
                                    <a href="{}"
                                       target="_blank">
                                       {}
                                    </a>
                                </div>
                                """.format(
                                    index,
                                    title,
                                    url,
                                    url,
                                ),
                                unsafe_allow_html=True,
                            )

                except Exception as e:

                    st.error(
                        "Search failed: {}: {}".format(
                            type(e).__name__,
                            e,
                        )
                    )


# =========================================================
# CRAWLER TAB
# =========================================================
with crawl_tab:

    st.subheader(
        "🌐 Crawl a Website"
    )

    st.write(
        "Add a website to MUSA's search index."
    )

    url = st.text_input(
        "Website URL",
        placeholder=(
            "https://example.com"
        ),
        key="crawl_url",
    )

    col1, col2 = st.columns(2)

    with col1:

        max_pages = st.number_input(
            "Maximum Pages",
            min_value=1,
            max_value=50,
            value=5,
            step=1,
        )

    with col2:

        max_depth = st.number_input(
            "Maximum Crawl Depth",
            min_value=0,
            max_value=5,
            value=1,
            step=1,
        )

    st.caption(
        "MUSA respects robots.txt and will not crawl "
        "pages that disallow the crawler."
    )

    start_crawl = st.button(
        "🚀 Start Crawling",
        use_container_width=True,
    )

    if start_crawl:

        if not url.strip():

            st.error(
                "Please enter a URL."
            )

        else:

            logs = []

            log_area = st.empty()

            def log_callback(message):

                logs.append(
                    str(message)
                )

                # Keep only the latest 150 lines
                # so Streamlit does not grow indefinitely.
                visible = logs[-150:]

                log_area.code(
                    "\n".join(visible),
                    language="text",
                )

            with st.status(
                "Starting crawler...",
                expanded=True,
            ) as status:

                try:

                    log_callback(
                        "Initializing MUSA crawler..."
                    )

                    crawler = Crawler(
                        database=engine.database,
                        max_pages=int(
                            max_pages
                        ),
                        max_depth=int(
                            max_depth
                        ),
                        same_domain=True,
                        concurrency=2,
                        request_delay=1.0,
                        max_retries=3,
                        log_callback=log_callback,
                    )

                    result = asyncio.run(
                        crawler.crawl(
                            url.strip()
                        )
                    )

                    log_callback("")
                    log_callback(
                        "Crawl completed."
                    )

                    log_callback(
                        "Documents currently indexed: {}".format(
                            result
                        )
                    )

                    status.update(
                        label="✅ Crawl Complete",
                        state="complete",
                        expanded=True,
                    )

                except Exception as e:

                    log_callback("")
                    log_callback(
                        "[FATAL ERROR] {}: {}".format(
                            type(e).__name__,
                            e,
                        )
                    )

                    status.update(
                        label="❌ Crawl Failed",
                        state="error",
                        expanded=True,
                    )

                    st.error(
                        "Crawler failed: {}: {}".format(
                            type(e).__name__,
                            e,
                        )
                    )
