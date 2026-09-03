import streamlit as st
import sys
from pathlib import Path

# Fix for Streamlit Cloud: Add the 'src' directory to sys.path
# This allows the app to find the 'musa' package
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

from musa.engine import MusaEngine

# Page Config
st.set_page_config(
    page_title="MUSA | AI Search Engine",
    page_icon="🔍",
    layout="wide"
)

# Custom CSS for a cleaner look
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #ff4b4b;
        color: white;
    }
    .source-card {
        padding: 10px;
        border-radius: 10px;
        border: 1px solid #ddd;
        margin-bottom: 10px;
        background-color: white;
    }
    </style>
    """, unsafe_allow_html=True)

# Initialize Engine in session state
if "engine" not in st.session_state:
    st.session_state.engine = MusaEngine()

engine = st.session_state.engine

# Sidebar
with st.sidebar:
    st.title("⚙️ MUSA Control")
    st.markdown("---")

    st.subheader("Index Stats")
    stats = engine.get_stats()
    st.metric("Total Documents", stats["document_count"])

    st.markdown("---")
    if st.button("🗑️ Clear Index"):
        engine.clear_index()
        st.rerun()

    st.markdown("---")
    st.markdown("### 🛠️ Technical Stack")
    st.caption("• FAISS Vector Index")
    st.caption("• Hybrid RRF Ranking")
    st.caption("• Async Crawler Pool")
    st.caption("• Claude-3-5-Sonnet RAG")

# Main UI
st.title("🔍 MUSA AI Search")
st.markdown("The AI-powered search engine that reads websites in real-time.")

tab1, tab2 = st.tabs(["💬 Ask MUSA", "🌐 Index Website"])

# --- TAB 1: ASK ---
with tab1:
    query = st.text_input("What would you like to know?", placeholder="Ask anything about your indexed sites...")

    if query:
        with st.spinner("Reading documents and thinking..."):
            answer, citations = engine.ask(query)

            if answer:
                st.markdown("### 🤖 MUSA AI Answer")
                st.markdown(answer)

                if citations:
                    st.markdown("---")
                    st.markdown("#### 📚 Sources")
                    for i, doc in enumerate(citations, 1):
                        st.markdown(f"""
                        <div class="source-card">
                            <strong>{i}. {doc.title}</strong><br>
                            <a href="{doc.url}" target="_blank">{doc.url}</a>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.warning("MUSA couldn't find enough relevant information to answer that question. Try indexing more pages!")

# --- TAB 2: INDEX ---
with tab2:
    st.subheader("Add Knowledge")
    col1, col2 = st.columns([3, 1])

    with col1:
        url = st.text_input("Website URL", placeholder="https://example.com")
    with col2:
        pages = st.number_input("Max Pages", min_value=1, max_value=100, value=10)

    if st.button("Start Crawling"):
        if not url:
            st.error("Please enter a URL first!")
        else:
            with st.status(f"Crawling {url}...", expanded=True) as status:
                st.write("Initializing Async Worker Pool...")
                try:
                    count = engine.crawl(url, max_pages=pages)
                    st.write(f"Successfully indexed {count} total documents.")
                    status.update(label="Crawling Complete!", state="complete", expanded=False)
                except Exception as e:
                    st.error(f"An error occurred: {e}")
                    status.update(label="Crawling Failed", state="error")
            st.rerun()
