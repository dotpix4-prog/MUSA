import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st


# =========================================================
# IMPORT PATH
# =========================================================

SRC_DIR = Path(__file__).resolve().parent.parent

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from musa.engine import MusaEngine
from musa.crawler.crawler import Crawler


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="MUSA | AI Search Engine",
    page_icon="🔍",
    layout="wide",
)


# =========================================================
# VISITOR LOGGING
# =========================================================

VISITOR_LOG = Path("data/visitors.jsonl")


def get_visitor_ip():
    """
    Get visitor IP from Streamlit when available.
    """
    try:
        return st.context.ip_address
    except Exception:
        return None


def log_visitor():
    """
    Log one visitor per Streamlit session.

    Logging errors never stop the application.
    """

    if st.session_state.get(
        "visitor_logged",
        False,
    ):
        return

    ip = get_visitor_ip()

    if not ip:
        st.session_state[
            "visitor_logged"
        ] = True
        return

    try:

        VISITOR_LOG.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        record = {
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "ip": str(ip),
        }

        with VISITOR_LOG.open(
            "a",
            encoding="utf-8",
        ) as file:

            file.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                )
                + "\n"
            )

    except Exception:
        pass

    st.session_state[
        "visitor_logged"
    ] = True


# =========================================================
# INITIALIZE VISITOR LOGGING
# =========================================================

log_visitor()


# =========================================================
# CSS
# =========================================================

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


# =========================================================
# ENGINE
# =========================================================

if "engine" not in st.session_state:

    st.session_state.engine = MusaEngine()


engine = st.session_state.engine


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.title("⚙️ MUSA Control")

    st.markdown("---")

    # -----------------------------------------------------
    # Database statistics
    # -----------------------------------------------------

    try:

        stats = engine.get_stats()

        st.metric(
            "Indexed Documents",
            stats.get(
                "document_count",
                0,
            ),
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

    # -----------------------------------------------------
    # Clear index
    # -----------------------------------------------------

    if st.button(
        "🗑️ Clear Index",
        use_container_width=True,
    ):

        try:

            engine.clear_index()

            st.success(
                "Index cleared."
            )

            st.rerun()

        except Exception as e:

            st.error(
                "Could not clear index: {}: {}".format(
                    type(e).__name__,
                    e,
                )
            )

    st.markdown("---")

    # -----------------------------------------------------
    # Visitor log administration
    # -----------------------------------------------------

    st.markdown(
        "### 🔐 Visitor Logs"
    )

    st.caption(
        "Admin access required to view visitor records."
    )

    admin_password = st.text_input(
        "Admin Password",
        type="password",
        key="admin_password",
    )

    try:

        configured_password = st.secrets.get(
            "ADMIN_PASSWORD",
            "",
        )

    except Exception:

        configured_password = os.environ.get(
            "ADMIN_PASSWORD",
            "",
        )

    if st.button(
        "View Visitor Logs",
        use_container_width=True,
    ):

        if not configured_password:

            st.error(
                "ADMIN_PASSWORD is not configured."
            )

        elif admin_password != configured_password:

            st.error(
                "Incorrect admin password."
            )

        else:

            st.session_state[
                "show_visitor_logs"
            ] = True

    if st.session_state.get(
        "show_visitor_logs",
        False,
    ):

        st.markdown(
            "#### Recorded Visitors"
        )

        if VISITOR_LOG.exists():

            try:

                lines = VISITOR_LOG.read_text(
                    encoding="utf-8"
                ).splitlines()

                # Show newest records first.
                lines = list(
                    reversed(lines)
                )

                if not lines:

                    st.info(
                        "No visitor records yet."
                    )

                else:

                    # Limit displayed records.
                    lines = lines[:100]

                    for line in lines:

                        try:

                            record = json.loads(
                                line
                            )

                            timestamp = record.get(
                                "timestamp",
                                "Unknown",
                            )

                            ip = record.get(
                                "ip",
                                "Unknown",
                            )

                            st.code(
                                "{} | {}".format(
                                    timestamp,
                                    ip,
                                ),
                                language="text",
                            )

                        except Exception:

                            st.code(
                                line,
                                language="text",
                            )

            except Exception as e:

                st.error(
                    "Could not read visitor log: {}: {}".format(
                        type(e).__name__,
                        e,
                    )
                )

        else:

            st.info(
                "No visitor records found."
            )

    st.markdown("---")

    # -----------------------------------------------------
    # Stack
    # -----------------------------------------------------

    st.markdown(
        "### 🛠️ MUSA Stack"
    )

    st.caption("• Streamlit")
    st.caption("• Async HTTP crawler")
    st.caption("• BeautifulSoup")
    st.caption("• SQLite + FTS5")
    st.caption("• FAISS")
    st.caption("• Groq")


# =========================================================
# MAIN HEADER
# =========================================================

st.title(
    "🔍 MUSA AI Search"
)

st.write(
    "An experimental AI-powered search engine "
    "that crawls, indexes and retrieves web content."
)


# =========================================================
# TABS
# =========================================================

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

    st.subheader(
        "Ask MUSA"
    )

    query = st.text_input(
        "What would you like to know?",
        placeholder=(
            "Ask something about your indexed websites..."
        ),
        key="search_query",
    )

    answer_language = st.selectbox(
        "Answer Language",
        [
            "English",
            "German",
            "Urdu",
            "Spanish",
            "French",
        ],
        index=0,
        key="answer_language",
    )

    search_button = st.button(
        "🔎 Search",
        use_container_width=True,
    )

    if search_button:

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
                        query.strip(),
                        language=answer_language,
                    )

                    st.markdown(
                        "### 🤖 MUSA Answer"
                    )

                    if answer:

                        st.markdown(
                            answer
                        )

                    else:

                        st.warning(
                            "MUSA could not generate "
                            "an answer."
                        )

                    # -------------------------------------------------
                    # Sources
                    # -------------------------------------------------

                    if citations:

                        st.markdown("---")

                        st.markdown(
                            "### 📚 Sources"
                        )

                        for index, doc in enumerate(
                            citations,
                            start=1,
                        ):

                            title = (
                                getattr(
                                    doc,
                                    "title",
                                    None,
                                )
                                or "Untitled"
                            )

                            url = (
                                getattr(
                                    doc,
                                    "url",
                                    None,
                                )
                                or ""
                            )

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

                    else:

                        st.caption(
                            "No source citations were returned."
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
        "MUSA respects robots.txt for normal websites "
        "and uses supported source adapters where available."
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


# =========================================================
# FOOTER
# =========================================================

st.markdown("---")

st.caption(
    "MUSA AI Search Engine"
)