import streamlit as st
import requests
import time
import os

# ── Config ─────────────────────────────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# ── Page setup ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ShopSense AI Support",
    page_icon="🛍️",
    layout="centered"
)

# ── Styling ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Main background */
    .stApp {
        background-color: #0f1117;
    }

    /* Header */
    .ss-header {
        text-align: center;
        padding: 1.5rem 0 0.5rem 0;
    }
    .ss-header h1 {
        color: #ffffff;
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .ss-header p {
        color: #9ca3af;
        font-size: 0.95rem;
        margin: 0;
    }

    /* Status badge */
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
    }
    .status-up   { background: #14532d; color: #86efac; }
    .status-down { background: #7f1d1d; color: #fca5a5; }

    /* Chat bubbles */
    .bubble-user {
        background: #1e3a5f;
        color: #e2e8f0;
        padding: 0.85rem 1.1rem;
        border-radius: 18px 18px 4px 18px;
        margin: 0.4rem 0 0.4rem 3rem;
        font-size: 0.95rem;
        line-height: 1.5;
    }
    .bubble-ai {
        background: #1a1f2e;
        color: #e2e8f0;
        padding: 0.85rem 1.1rem;
        border-radius: 18px 18px 18px 4px;
        margin: 0.4rem 3rem 0.4rem 0;
        font-size: 0.95rem;
        line-height: 1.5;
        border: 1px solid #2d3748;
    }
    .bubble-meta {
        font-size: 0.72rem;
        color: #6b7280;
        margin: 0.1rem 0 0.6rem 0;
        padding-left: 0.3rem;
    }

    /* Source tags */
    .source-tag {
        display: inline-block;
        background: #1e293b;
        color: #7dd3fc;
        border: 1px solid #334155;
        border-radius: 6px;
        padding: 0.15rem 0.5rem;
        font-size: 0.7rem;
        margin-right: 0.3rem;
    }

    /* Confidence indicator */
    .conf-high { color: #86efac; }
    .conf-low  { color: #fca5a5; }

    /* Divider */
    .ss-divider {
        border: none;
        border-top: 1px solid #2d3748;
        margin: 1rem 0;
    }

    /* Suggestion chips */
    .chip-row {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin: 0.75rem 0;
    }

    /* Hide streamlit default elements */
    #MainMenu { visibility: hidden; }
    footer     { visibility: hidden; }
    header     { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ────────────────────────────────────────────────────────────────
def check_health() -> dict:
    try:
        resp = requests.get(f"{API_BASE_URL}/health", timeout=3)
        return resp.json()
    except Exception:
        return {"api": "down", "ollama": "down", "model": "unknown"}


def send_chat(query: str) -> dict:
    try:
        resp = requests.post(
            f"{API_BASE_URL}/chat",
            json={"query": query, "session_id": st.session_state.get("session_id", "default")},
            timeout=120
        )
        return resp.json()
    except requests.exceptions.ConnectionError:
        return {"error": "Cannot connect to ShopSense API. Is the backend running?"}
    except requests.exceptions.Timeout:
        return {"error": "Request timed out. The model is taking too long — try again."}
    except Exception as e:
        return {"error": str(e)}


def fetch_stats() -> dict:
    try:
        resp = requests.get(f"{API_BASE_URL}/logs/stats", timeout=3)
        return resp.json()
    except Exception:
        return {}


def trigger_ingest() -> str:
    try:
        resp = requests.post(f"{API_BASE_URL}/ingest", timeout=30)
        return resp.json().get("message", "Done.")
    except Exception as e:
        return f"Error: {str(e)}"


# ── Session state init ─────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

if "session_id" not in st.session_state:
    st.session_state.session_id = f"session_{int(time.time())}"


# ── Header ─────────────────────────────────────────────────────────────────
st.markdown("""
<div class="ss-header">
    <h1>🛍️ ShopSense AI</h1>
    <p>Your intelligent customer support assistant</p>
</div>
""", unsafe_allow_html=True)

# ── Health status bar ──────────────────────────────────────────────────────
health = check_health()
api_cls    = "status-up"   if health.get("api")    == "up" else "status-down"
ollama_cls = "status-up"   if health.get("ollama") == "up" else "status-down"

col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    st.markdown(f'<span class="status-badge {api_cls}">API {health.get("api","down")}</span>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<span class="status-badge {ollama_cls}">Ollama {health.get("ollama","down")}</span>', unsafe_allow_html=True)
with col3:
    st.markdown(f'<span style="color:#6b7280;font-size:0.8rem;">Model: {health.get("model","—")}</span>', unsafe_allow_html=True)

st.markdown('<hr class="ss-divider">', unsafe_allow_html=True)


# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📊 Live Stats")

    stats = fetch_stats()
    if stats:
        st.metric("Total Queries",     stats.get("total_queries", 0))
        st.metric("Confidence Rate",   f"{stats.get('confidence_rate', 0)}%")
        st.metric("Avg Response Time", f"{stats.get('avg_response_time_seconds', 0)}s")
        st.metric("Unanswered Queries",stats.get("unanswered_queries", 0))
    else:
        st.caption("No stats yet — ask something first.")

    st.markdown("---")
    st.markdown("### 🔧 Admin")

    if st.button("🔄 Re-ingest Knowledge Base"):
        with st.spinner("Ingesting..."):
            msg = trigger_ingest()
        st.success(msg)

    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()

    st.markdown("---")
    st.markdown("### 🔍 Order Lookup")
    order_id = st.text_input("Enter Order ID", placeholder="e.g. SS10002")
    if st.button("Look up"):
        if order_id.strip():
            try:
                resp = requests.get(f"{API_BASE_URL}/orders/{order_id.strip()}", timeout=10)
                if resp.status_code == 200:
                    st.json(resp.json())
                else:
                    st.error(f"Order not found: {order_id.upper()}")
            except Exception:
                st.error("Could not reach the API.")


# ── Suggestion chips ───────────────────────────────────────────────────────
if not st.session_state.messages:
    st.markdown("**Try asking:**")
    suggestions = [
        "What is the status of order SS10002?",
        "How long does a credit card refund take?",
        "Can I cancel my order after dispatch?",
        "My item arrived damaged, what do I do?",
        "What is ShopSense's return policy?",
    ]
    for suggestion in suggestions:
        if st.button(suggestion, key=f"chip_{suggestion}"):
            st.session_state.messages.append({"role": "user", "content": suggestion})
            with st.spinner("Thinking..."):
                result = send_chat(suggestion)
            st.session_state.messages.append({"role": "assistant", "content": result})
            st.rerun()


# ── Chat history ───────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(f'<div class="bubble-user">👤 {msg["content"]}</div>', unsafe_allow_html=True)

    elif msg["role"] == "assistant":
        result = msg["content"]

        if "error" in result:
            st.markdown(f'<div class="bubble-ai">⚠️ {result["error"]}</div>', unsafe_allow_html=True)
        else:
            answer   = result.get("answer", "No answer returned.")
            sources  = result.get("sources", [])
            sim      = result.get("top_similarity", 0)
            confident= result.get("confident", False)
            resp_time= result.get("response_time", 0)

            conf_cls  = "conf-high" if confident else "conf-low"
            conf_icon = "✅" if confident else "⚠️"

            # Source tags
            source_html = "".join([f'<span class="source-tag">{s}</span>' for s in sources])

            st.markdown(f'<div class="bubble-ai">🤖 {answer}</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="bubble-meta">'
                f'{source_html} &nbsp;'
                f'<span class="{conf_cls}">{conf_icon} {sim}</span> &nbsp;'
                f'<span>⏱ {resp_time}s</span>'
                f'</div>',
                unsafe_allow_html=True
            )


# ── Chat input ─────────────────────────────────────────────────────────────
st.markdown('<hr class="ss-divider">', unsafe_allow_html=True)

user_input = st.chat_input("Ask about your order, returns, or refund policy...")

if user_input and user_input.strip():
    st.session_state.messages.append({"role": "user", "content": user_input.strip()})

    with st.spinner("ShopSense AI is thinking..."):
        result = send_chat(user_input.strip())

    st.session_state.messages.append({"role": "assistant", "content": result})
    st.rerun()
