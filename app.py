"""
IncidentIQ — AI-Powered DevOps Incident Commander
v3: Fixed styling, visible runbook loader, proper card layout
"""

import os
import sys
import json
import streamlit as st
import tempfile
from datetime import datetime
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from data.sample_logs import SAMPLE_LOGS

# ─────────────────────────────────────────────────
# Page Config
# ─────────────────────────────────────────────────
st.set_page_config(
    page_title="IncidentIQ",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",  # SHOW sidebar — runbook upload is critical
)

# ─────────────────────────────────────────────────
# Design System
# Dark but NOT pitch black — use #111827 (gray-900) not #0c0f16
# Enough contrast, warm feel, readable
# ─────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    /* Base — warm dark, not pure black */
    .stApp { background: #111827; }
    
    /* Hide chrome but KEEP sidebar toggle */
    #MainMenu, footer { visibility: hidden; }
    header[data-testid="stHeader"] {
        background: transparent !important;
    }
    /* Hide the decoration but keep the sidebar button functional */
    header[data-testid="stHeader"]::before {
        display: none;
    }
    
    /* ── Sidebar toggle — ALWAYS visible ── */
    button[data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"] {
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        color: #9ca3af !important;
        background: #1e2433 !important;
        border: 1px solid #374151 !important;
        border-radius: 8px !important;
    }
    
    /* ── Hero ── */
    .hero {
        text-align: center;
        padding: 1.8rem 1rem 1rem;
        max-width: 680px;
        margin: 0 auto;
    }
    .hero h1 {
        font-family: 'DM Sans', sans-serif;
        font-size: 1.8rem;
        font-weight: 700;
        color: #f1f5f9;
        margin: 0.5rem 0 0.4rem;
        letter-spacing: -0.02em;
    }
    .hero p {
        color: #9ca3af;
        font-size: 0.95rem;
        line-height: 1.5;
        margin: 0;
    }

    /* ── Text area ── */
    .stTextArea textarea {
        background: #1f2937 !important;
        color: #e5e7eb !important;
        border: 1px solid #374151 !important;
        border-radius: 8px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 13px !important;
        line-height: 1.6 !important;
    }
    .stTextArea textarea:focus {
        border-color: #4f46e5 !important;
        box-shadow: 0 0 0 1px #4f46e5 !important;
    }
    /* Kill Streamlit's default pink/magenta focus ring */
    .stTextArea div[data-baseweb="textarea"] {
        border-color: #374151 !important;
    }
    .stTextArea div[data-baseweb="textarea"]:focus-within {
        border-color: #4f46e5 !important;
        box-shadow: 0 0 0 1px #4f46e5 !important;
    }
    
    /* ── Primary button — indigo, not neon blue ── */
    .stButton > button[kind="primary"] {
        background: #4f46e5 !important;
        border: none !important;
        border-radius: 8px !important;
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        padding: 0.6rem 1.5rem !important;
        transition: background 0.2s !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: #4338ca !important;
    }

    /* ── ALL buttons — fix the white cards problem ── */
    .stButton > button {
        background: #1f2937 !important;
        color: #d1d5db !important;
        border: 1px solid #374151 !important;
        border-radius: 8px !important;
        font-family: 'DM Sans', sans-serif !important;
        font-size: 0.85rem !important;
        transition: all 0.15s !important;
    }
    .stButton > button:hover {
        background: #283548 !important;
        border-color: #6366f1 !important;
        color: #f3f4f6 !important;
    }
    /* Keep primary different */
    .stButton > button[kind="primary"] {
        color: white !important;
        border: none !important;
    }

    /* ── Scenario section header ── */
    .scenario-header {
        color: #9ca3af;
        font-size: 0.82rem;
        font-weight: 500;
        margin: 0.8rem 0 0.5rem;
        font-family: 'DM Sans', sans-serif;
    }
    
    /* ── Investigation steps ── */
    .step-card {
        background: #1f2937;
        border: 1px solid #374151;
        border-radius: 8px;
        padding: 12px 16px;
        margin: 6px 0;
        display: flex;
        align-items: center;
        gap: 10px;
        animation: slideUp 0.25s ease-out;
    }
    @keyframes slideUp {
        from { opacity: 0; transform: translateY(6px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .step-icon { font-size: 1.1rem; }
    .step-label {
        color: #e5e7eb;
        font-weight: 500;
        font-size: 0.85rem;
        font-family: 'DM Sans', sans-serif;
    }
    .step-detail {
        color: #6b7280;
        font-size: 0.75rem;
        margin-left: auto;
        font-family: 'DM Sans', sans-serif;
    }

    /* ── RCA container ── */
    .rca-box {
        background: #1f2937;
        border: 1px solid #374151;
        border-radius: 10px;
        padding: 20px 24px;
        margin: 1rem 0;
    }
    .rca-title {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 12px;
        padding-bottom: 12px;
        border-bottom: 1px solid #374151;
    }
    .rca-title h3 {
        font-family: 'DM Sans', sans-serif;
        font-size: 1.1rem;
        font-weight: 700;
        color: #f3f4f6;
        margin: 0;
    }
    .sev-badge {
        margin-left: auto;
        padding: 2px 10px;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.05em;
    }
    .sev-CRITICAL { background: #7f1d1d; color: #fca5a5; }
    .sev-HIGH { background: #78350f; color: #fde68a; }
    .sev-MEDIUM { background: #1e3a5f; color: #93c5fd; }
    .sev-LOW { background: #14532d; color: #86efac; }

    /* ── Sidebar — light enough for default widgets to work ── */
    section[data-testid="stSidebar"] {
        background: #1e2433 !important;
    }
    section[data-testid="stSidebar"] * {
        color: #c9d1d9 !important;
    }
    section[data-testid="stSidebar"] .stMarkdown h4,
    section[data-testid="stSidebar"] .stMarkdown strong {
        color: #f0f3f6 !important;
    }
    section[data-testid="stSidebar"] .stCaption p {
        color: #8b949e !important;
    }
    /* Sidebar dropdown & uploader — slight dark tint */
    section[data-testid="stSidebar"] .stSelectbox > div > div,
    section[data-testid="stSidebar"] [data-testid="stFileUploader"] {
        background: #2d333b !important;
        border-color: #444c56 !important;
        border-radius: 8px !important;
    }
    section[data-testid="stSidebar"] .stSelectbox > div > div > div {
        color: #e6edf3 !important;
    }
    /* Sidebar buttons */
    section[data-testid="stSidebar"] .stButton > button {
        background: #2d333b !important;
        color: #c9d1d9 !important;
        border: 1px solid #444c56 !important;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background: #373e47 !important;
        border-color: #6366f1 !important;
    }
    /* Sidebar dividers */
    section[data-testid="stSidebar"] hr {
        border-color: #30363d !important;
    }
    /* ── File uploader — force dark theme on ALL nested elements ── */
    section[data-testid="stSidebar"] [data-testid="stFileUploader"],
    section[data-testid="stSidebar"] [data-testid="stFileUploader"] > div,
    section[data-testid="stSidebar"] [data-testid="stFileUploader"] section,
    section[data-testid="stSidebar"] [data-testid="stFileUploader"] div {
        background-color: #2d333b !important;
        color: #8b949e !important;
        border-color: #444c56 !important;
    }
    section[data-testid="stSidebar"] [data-testid="stFileUploader"] button {
        background-color: #373e47 !important;
        color: #c9d1d9 !important;
        border: 1px solid #444c56 !important;
    }
    section[data-testid="stSidebar"] [data-testid="stFileUploader"] button:hover {
        background-color: #444c56 !important;
        border-color: #6366f1 !important;
    }
    section[data-testid="stSidebar"] [data-testid="stFileUploader"] small,
    section[data-testid="stSidebar"] [data-testid="stFileUploader"] span {
        color: #8b949e !important;
    }
    /* Round the outer container */
    section[data-testid="stSidebar"] [data-testid="stFileUploader"] > div:first-child {
        border-radius: 8px !important;
        border: 1px dashed #444c56 !important;
    }

    /* ── Status dots ── */
    .st-dot {
        display: inline-block;
        width: 7px; height: 7px;
        border-radius: 50%;
        margin-right: 6px;
        vertical-align: middle;
    }
    .st-dot-ok { background: #22c55e; }
    .st-dot-no { background: #6b7280; }
    
    /* ── Pulse animation ── */
    .pulse {
        display: inline-block;
        width: 7px; height: 7px;
        border-radius: 50%;
        background: #6366f1;
        animation: pulse-anim 1.4s infinite;
        margin-right: 8px;
        vertical-align: middle;
    }
    @keyframes pulse-anim {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.3; }
    }
    
    /* ── Reduce max width for readability ── */
    .block-container {
        max-width: 860px !important;
        padding: 1rem 2rem 2rem !important;
    }
    
    /* ── Expander styling ── */
    .streamlit-expanderHeader {
        font-family: 'DM Sans', sans-serif !important;
        background: #1f2937 !important;
        border-radius: 8px !important;
    }

    /* ── Popover (Manage docs) — dark theme ── */
    [data-testid="stPopover"] > div {
        background: #1e2433 !important;
        border: 1px solid #374151 !important;
        border-radius: 10px !important;
    }
    [data-testid="stPopover"] [data-testid="stMarkdown"],
    [data-testid="stPopover"] .stCaption p {
        color: #c9d1d9 !important;
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────
# Session State
# ─────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []
if "is_investigating" not in st.session_state:
    st.session_state.is_investigating = False
if "last_rca" not in st.session_state:
    st.session_state.last_rca = None  # stores the full RCA context for Slack etc.
if "slack_sent" not in st.session_state:
    st.session_state.slack_sent = False


# ─────────────────────────────────────────────────
# Slack send handler — runs on rerun after button click
# ─────────────────────────────────────────────────
def _send_to_slack():
    """Send the last RCA to Slack using the webhook. Returns (success, message)."""
    rca = st.session_state.get("last_rca")
    if not rca or not Config.SLACK_WEBHOOK_URL:
        return False, "No RCA data or Slack webhook not configured"
    try:
        import requests as _req
        import re as _slack_re

        _severity = rca["severity"]
        _sev_emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🔵", "LOW": "🟢"}.get(_severity, "⚪")
        _err_type = rca["error_info"].get("error_type", "Unknown")
        _final = rca["final_output"]

        _rc_match = _slack_re.search(
            r"(?:Root Cause|root cause)[:\s*]*(.{20,400})",
            _final, _slack_re.IGNORECASE | _slack_re.DOTALL,
        )
        _rc_text = _rc_match.group(1).strip()[:300] if _rc_match else "See full RCA"
        _rc_text = _slack_re.sub(r"\*+", "", _rc_text).strip()

        _payload = {
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": f"{_sev_emoji} IncidentIQ — {_severity} Incident", "emoji": True},
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Error:*\n{_err_type}"},
                        {"type": "mrkdwn", "text": f"*Severity:*\n{_severity}"},
                    ],
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Root Cause:*\n{_rc_text}"},
                },
                {"type": "divider"},
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": f"🔍 Investigated by IncidentIQ • {rca['timestamp']}"}],
                },
            ],
        }

        _resp = _req.post(Config.SLACK_WEBHOOK_URL, json=_payload, timeout=10)
        if _resp.status_code == 200:
            return True, "✓ RCA sent to Slack"
        else:
            return False, f"Slack error: {_resp.status_code} — {_resp.text[:100]}"
    except ImportError:
        return False, "Install `requests` — `pip install requests`"
    except Exception as e:
        return False, f"Slack error: {str(e)[:100]}"


# ─────────────────────────────────────────────────
# Sidebar — VISIBLE by default (runbooks are important)
# ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("#### 🔍 IncidentIQ")
    st.caption("AI Incident Commander")
    st.markdown("---")

    # Model — customer vocabulary
    st.markdown("**AI Model**")
    model_map = {
        "GPT-4o (Recommended)": "openai/gpt-4o",
        "GPT-4o Mini (Faster)": "openai/gpt-4o-mini",
        "Claude Sonnet 4.5": "anthropic/claude-sonnet-4.5",
        "Gemini 2.0 Flash": "google/gemini-2.0-flash-exp",
        "Qwen 3 235B": "qwen/qwen3-235b-a22b",
        "DeepSeek V3": "deepseek/deepseek-chat",
    }
    selected_label = st.selectbox("Model", list(model_map.keys()), index=0, label_visibility="collapsed")
    selected_model = model_map[selected_label]

    st.markdown("---")

    # Team Docs — PROMINENT, not hidden
    st.markdown("**📖 Your Team Docs**")
    st.caption("Select files, then click Upload to add them to the knowledge base")

    uploaded_files = st.file_uploader(
        "Select runbooks", type=["txt", "md", "pdf"],
        accept_multiple_files=True, label_visibility="collapsed",
    )

    # Upload button — files are only ingested when user clicks this
    if st.button("📤 Upload selected files", use_container_width=True, disabled=not uploaded_files):
        from tools.runbook_rag import ingest_document
        success_count = 0
        for uf in uploaded_files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uf.name)[1]) as tmp:
                tmp.write(uf.read())
                tmp_path = tmp.name
            try:
                result = ingest_document(tmp_path, doc_type="runbook", original_name=uf.name)
                if result["status"] == "success":
                    success_count += 1
            except Exception as e:
                st.error(f"✗ {uf.name}: {str(e)[:60]}")
            finally:
                os.unlink(tmp_path)
        if success_count:
            st.success(f"✓ {success_count} file{'s' if success_count > 1 else ''} uploaded")

    st.markdown("")

    if st.button("📂 Load demo runbooks", use_container_width=True):
        sample_dir = os.path.join(os.path.dirname(__file__), "data", "sample_runbooks")
        if os.path.exists(sample_dir):
            from tools.runbook_rag import ingest_document
            count = 0
            for fname in os.listdir(sample_dir):
                fpath = os.path.join(sample_dir, fname)
                if os.path.isfile(fpath):
                    r = ingest_document(fpath, doc_type="runbook", original_name=fname)
                    if r["status"] == "success":
                        count += 1
            st.success(f"✓ {count} runbooks loaded")

    # Show what's loaded — compact count + popover for details
    try:
        from tools.runbook_rag import get_ingested_docs, delete_document, clear_all_documents
        docs = get_ingested_docs()
        if docs:
            _doc_count = len(docs)
            _dc1, _dc2 = st.columns([3, 2])
            with _dc1:
                st.markdown(
                    f'<span style="color:#9ca3af;font-size:0.82rem;">'
                    f'📄 {_doc_count} doc{"s" if _doc_count != 1 else ""} loaded</span>',
                    unsafe_allow_html=True,
                )
            with _dc2:
                with st.popover("Manage", use_container_width=True):
                    st.markdown(
                        '<span style="color:#d1d5db;font-size:0.85rem;font-weight:600;">'
                        'Uploaded Documents</span>',
                        unsafe_allow_html=True,
                    )
                    for d in sorted(docs):
                        _pc1, _pc2 = st.columns([5, 1])
                        with _pc1:
                            st.caption(f"📄 {d}")
                        with _pc2:
                            if st.button("✕", key=f"del_{d}", help=f"Remove {d}"):
                                delete_document(d)
                                st.rerun()
                    st.markdown("")
                    if st.button("🗑 Clear all", use_container_width=True, key="clear_all_docs"):
                        clear_all_documents()
                        st.success("✓ Cleared")
                        st.rerun()
    except Exception:
        pass

    st.markdown("---")

    # Incident Memory management — compact count + Manage popover
    # Mirrors the Team Docs pattern for visual consistency.
    _incident_memory_placeholder = st.empty()
    _incident_detail_placeholder = st.empty()

    def _render_incident_memory_sidebar():
        """Render the incident memory section (called initially and after store)."""
        try:
            from tools.incident_memory import get_incident_history, clear_incident_memory
            _incidents = get_incident_history(limit=100)
            _inc_count = len(_incidents)
            if _inc_count > 0:
                with _incident_memory_placeholder.container():
                    _mc1, _mc2 = st.columns([3, 2])
                    with _mc1:
                        st.markdown(
                            f'<span style="color:#9ca3af;font-size:0.82rem;">'
                            f'🧠 {_inc_count} incident{"s" if _inc_count != 1 else ""} stored</span>',
                            unsafe_allow_html=True,
                        )
                    with _mc2:
                        with st.popover("Manage", use_container_width=True):
                            st.markdown(
                                '<span style="color:#d1d5db;font-size:0.85rem;font-weight:600;">'
                                'Incident Memory</span>',
                                unsafe_allow_html=True,
                            )
                            for _inc in _incidents:
                                _iid = _inc["id"][:8]
                                _etype = _inc.get("error_type", "Unknown")[:30]
                                _sev = _inc.get("severity", "?")
                                _ts = _inc.get("timestamp", "")[:16].replace("T", " ")
                                _rc = _inc.get("root_cause", "")[:80]
                                # Severity color dot
                                _sev_color = {
                                    "CRITICAL": "#ef4444", "HIGH": "#f59e0b",
                                    "MEDIUM": "#3b82f6", "LOW": "#22c55e",
                                }.get(_sev, "#6b7280")
                                st.markdown(
                                    f'<div style="padding:6px 0;border-bottom:1px solid #30363d;">'
                                    f'<span style="font-family:\'JetBrains Mono\',monospace;font-size:0.72rem;color:#8b949e;">'
                                    f'`{_iid}`</span> &nbsp;'
                                    f'<span style="background:{_sev_color}22;color:{_sev_color};'
                                    f'padding:1px 6px;border-radius:3px;font-size:0.68rem;font-weight:600;">'
                                    f'{_sev}</span><br>'
                                    f'<span style="color:#d1d5db;font-size:0.78rem;">{_etype}</span><br>'
                                    f'<span style="color:#6b7280;font-size:0.7rem;">{_ts}</span>'
                                    f'</div>',
                                    unsafe_allow_html=True,
                                )
                            st.markdown("")
                            if st.button("🗑 Clear all", use_container_width=True, key="clear_inc_mem"):
                                clear_incident_memory()
                                st.success("✓ Cleared")
                                st.rerun()
                _incident_detail_placeholder.empty()
            else:
                _incident_memory_placeholder.empty()
                _incident_detail_placeholder.empty()
        except Exception:
            pass

    _render_incident_memory_sidebar()

    st.markdown("---")

    # Connections
    st.markdown("**Connections**")
    for name, ok in Config.validate().items():
        friendly = {"OpenRouter LLM": "AI Engine", "Tavily Search": "Web Search",
                     "Serper Search": "StackOverflow", "LangSmith Tracing": "Tracing",
                     "Slack": "Slack"}.get(name, name)
        dot = "st-dot-ok" if ok else "st-dot-no"
        st.markdown(f'<span class="st-dot {dot}"></span> {friendly}', unsafe_allow_html=True)

    st.markdown("---")

    # History
    if st.session_state.history:
        st.markdown("**Recent (this session)**")
        for h in reversed(st.session_state.history[-5:]):
            sev = h.get("severity", "?")
            st.caption(f"[{sev}] {h.get('error_type', '?')[:25]} — {h.get('timestamp', '')}")



    # Deploy help
    with st.expander("🌐 Share via public URL"):
        st.code("# brew install cloudflared\n# Cloudflare Tunnel\ncloudflared tunnel --url http://localhost:8501\n\n# Or ngrok\nngrok http 8501", language="bash")

    st.markdown("---")
    st.caption("LangGraph • ChromaDB • Tavily • LangSmith • Slack")


# ─────────────────────────────────────────────────
# MAIN — Hero
# ─────────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <h1>🔍 What happened in production?</h1>
    <p>Paste your error log. Get root cause analysis, fix commands,<br>and matching runbook sections — in seconds.</p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────
# Input + Controls
# ─────────────────────────────────────────────────

# Clear flag — must be checked BEFORE the widget renders
if st.session_state.get("clear_input", False):
    st.session_state["clear_input"] = False
    st.session_state["log_input"] = ""

# Sample scenario flag — must be checked BEFORE the widget renders
if st.session_state.get("_load_scenario", None):
    st.session_state["log_input"] = st.session_state["_load_scenario"]
    st.session_state["_load_scenario"] = None

log_input = st.text_area(
    "Error log",
    height=180,
    placeholder="Paste your error log, stack trace, or describe the incident...",
    label_visibility="collapsed",
    key="log_input",
)

# Action row: Investigate + Clear — equal width, centered
col_pad_l, col_btn_inv, col_btn_clr, col_pad_r = st.columns([1.5, 1, 1, 1.5])
with col_btn_inv:
    btn_text = "⏳ Investigating..." if st.session_state.is_investigating else "🔍 Investigate"
    investigate = st.button(btn_text, type="primary", use_container_width=True, disabled=not log_input)
with col_btn_clr:
    if st.button("🗑 Clear", use_container_width=True):
        st.session_state["clear_input"] = True
        st.session_state.last_rca = None
        st.session_state.slack_sent = False
        st.rerun()

# ─────────────────────────────────────────────────
# Sample Scenarios — always visible, collapsible
# ─────────────────────────────────────────────────
SCENARIOS = {
    "🐍 Python — DB Connection Pool Exhaustion": "🐍  DB Pool Exhaustion — PaymentService",
    "☕ Java — NullPointerException in Auth": "☕  NullPointer — AuthService",
    "🟢 Node.js — Memory Leak in API Gateway": "🟢  OOMKilled — API Gateway",
    "🔵 Go — Goroutine Deadlock": "🔵  Deadlock — OrderService",
}

with st.expander("📦 Sample scenarios", expanded=not log_input):
    cols = st.columns(2)
    for i, (key, label) in enumerate(SCENARIOS.items()):
        with cols[i % 2]:
            if st.button(label, key=f"s{i}", use_container_width=True):
                st.session_state["_load_scenario"] = SAMPLE_LOGS[key]
                st.rerun()



# ─────────────────────────────────────────────────
# Investigation
# ─────────────────────────────────────────────────
if investigate and log_input:
    if not Config.is_ready():
        st.error("Add your **OpenRouter API key** to the `.env` file. See sidebar for connection status.")
    else:
        st.session_state.is_investigating = True
        st.markdown("---")

        status = st.empty()
        status.markdown(
            '<span class="pulse"></span> <span style="color:#a5b4fc;font-weight:500;font-size:0.9rem;">Investigating...</span>',
            unsafe_allow_html=True,
        )

        steps_area = st.container()

        TOOLS_UI = {
            "analyze_log": ("🔬", "Parsing error log"),
            "search_runbooks": ("📖", "Searching team docs"),
            "find_similar_incidents": ("🔄", "Checking past incidents"),
            "search_web": ("🌐", "Searching the web"),
            "search_stackoverflow": ("📚", "Searching Stack Overflow"),
        }

        try:
            from agent import stream_investigation
            final_output = ""
            tool_log = []
            step_n = 0

            for event in stream_investigation(log_text=log_input, model_name=selected_model, thread_id=str(uuid.uuid4())):
                etype = event.get("event_type", "")
                if etype == "tool_call":
                    step_n += 1
                    tname = event.get("tool_name", "")
                    icon, label = TOOLS_UI.get(tname, ("🔧", tname))
                    with steps_area:
                        st.markdown(
                            f'<div class="step-card">'
                            f'<span class="step-icon">{icon}</span>'
                            f'<span class="step-label">Step {step_n}: {label}</span>'
                            f'<span class="step-detail">✓</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    tool_log.append(event)
                elif etype == "tool_result":
                    tname = event.get("tool_name", "")
                    content = event.get("content", "")
                    with steps_area:
                        icon, label = TOOLS_UI.get(tname, ("🔧", tname))
                        with st.expander(f"↳ {label} — details", expanded=False):
                            try:
                                st.json(json.loads(content))
                            except Exception:
                                st.code(content[:500], language="text")
                elif etype == "agent_output":
                    final_output = event.get("content", "")

            # Done
            status.markdown(
                f'<span style="color:#86efac;">✓</span> '
                f'<span style="color:#86efac;font-weight:500;font-size:0.9rem;">Done</span> '
                f'<span style="color:#6b7280;font-size:0.82rem;">— {step_n} steps</span>',
                unsafe_allow_html=True,
            )

            st.markdown("---")

            # Severity
            from tools.log_analyzer import detect_severity, extract_error_info, detect_language
            severity = detect_severity(log_input)
            language = detect_language(log_input)
            error_info = extract_error_info(log_input, language)

            st.markdown(
                f'<div class="rca-box"><div class="rca-title">'
                f'<span style="font-size:1.2rem;">📊</span>'
                f'<h3>Root Cause Analysis</h3>'
                f'<span class="sev-badge sev-{severity}">{severity}</span>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

            st.markdown(final_output)

            # ── Save RCA context to session state ──
            # This persists across Streamlit reruns so actions like
            # "Send to Slack" can access the data after a button click.
            st.session_state.last_rca = {
                "final_output": final_output,
                "severity": severity,
                "error_info": error_info,
                "log_input": log_input,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }

            # Save to session history
            st.session_state.history.append({
                "timestamp": datetime.now().strftime("%H:%M"),
                "error_type": error_info.get("error_type", "Unknown"),
                "severity": severity,
            })

            if Config.LANGCHAIN_API_KEY:
                _langsmith_project_id = os.getenv("LANGCHAIN_PROJECT_ID", "")
                _org_id = os.getenv("LANGCHAIN_ORG_ID", "")
                if _org_id and _langsmith_project_id:
                    langsmith_url = (
                        "https://smith.langchain.com/o/" + _org_id
                        + "/projects/p/" + _langsmith_project_id
                        + "?timeModel=%7B%22duration%22%3A%221d%22%7D"
                    )
                elif _org_id:
                    langsmith_url = "https://smith.langchain.com/o/" + _org_id + "/projects/" + Config.LANGCHAIN_PROJECT + "/runs"
                else:
                    langsmith_url = "https://smith.langchain.com/projects/"
                st.info("🔗 [View traces in LangSmith](" + langsmith_url + ")")

            # ── Send to Slack ──
            if Config.SLACK_WEBHOOK_URL and final_output:
                _slack_col1, _slack_col2 = st.columns([1, 4])
                with _slack_col1:
                    def _on_slack_click():
                        ok, msg = _send_to_slack()
                        st.session_state.slack_sent = msg
                    st.button("💬 Send to Slack", use_container_width=True,
                              key="slack_send_btn", on_click=_on_slack_click)
                # Show result from a previous click (persists in session state)
                if st.session_state.slack_sent:
                    _msg = st.session_state.slack_sent
                    if _msg.startswith("✓"):
                        st.success(_msg)
                    else:
                        st.error(_msg)
                    st.session_state.slack_sent = False

            # ── Past Similar Incidents — search BEFORE storing current ──
            try:
                from tools.incident_memory import find_similar_incidents as _find_similar
                import json as _json
                # Always use raw user input as search query. It works for both cases:
                # - Structured logs: the raw text contains the error type, stack trace,
                #   service names — richer than extracted error_type alone
                # - Natural language: "I am getting OOM in my service" is the best
                #   possible semantic search query as-is
                _search_query = log_input[:500]
                _sim_result = _json.loads(_find_similar.invoke(_search_query))
                _similar_list = _sim_result.get("similar_incidents", [])
                if _similar_list:
                    _count_label = f"📋 Past Similar Incidents ({len(_similar_list)})"
                    with st.expander(_count_label, expanded=False):
                        for _inc in _similar_list:
                            _inc_id = _inc.get("incident_id", "?")
                            _err = _inc.get("error_type", "Unknown")[:40]
                            _sev = _inc.get("severity", "?")
                            _ts = _inc.get("timestamp", "")[:16].replace("T", " ")
                            _rc = _inc.get("root_cause", "N/A")
                            _resolution = _inc.get("resolution", "")
                            _score = _inc.get("similarity_score", 0)
                            _score_pct = f"{_score * 100:.0f}%" if _score else "—"
                            if _score and _score >= 0.8:
                                _score_color = "#22c55e"
                            elif _score and _score >= 0.5:
                                _score_color = "#eab308"
                            else:
                                _score_color = "#6b7280"
                            st.markdown(
                                f'**`{_inc_id}`** &nbsp;|&nbsp; `{_sev}` &nbsp;|&nbsp; {_err} '
                                f'&nbsp;&nbsp;<span style="background:{_score_color}22;color:{_score_color};'
                                f'padding:1px 8px;border-radius:4px;font-size:0.75rem;font-weight:600;">'
                                f'Similarity: {_score_pct}</span>  \n'
                                f"🕒 {_ts}  \n"
                                f"**Root Cause:** {_rc}  \n"
                                + (f"**Resolution:** {_resolution}" if _resolution else ""),
                                unsafe_allow_html=True,
                            )
                            st.divider()
            except Exception:
                pass

            # ── Store current incident AFTER showing past ones ──
            try:
                from tools.incident_memory import store_incident
                import re as _re

                def _extract_section(text, *headings):
                    """Extract content under a markdown heading from RCA text."""
                    for heading in headings:
                        pattern = rf"(?:#+\s*)?{_re.escape(heading)}[:\s]*([^\n#]{{10,500}})"
                        m = _re.search(pattern, text, _re.IGNORECASE | _re.DOTALL)
                        if m:
                            val = m.group(1).strip()
                            val = _re.split(r"\n#+\s", val)[0].strip()
                            if val and val.lower() not in ("see rca", "n/a", ""):
                                return val[:400]
                    return ""

                extracted_rc = (
                    _extract_section(final_output, "Root Cause", "root cause")
                    or error_info.get("error_type", "Unknown")
                )
                extracted_res = (
                    _extract_section(final_output, "Immediate Fix", "Short-term", "Remediation")
                    or "See full RCA"
                )

                _store_result = store_incident(
                    error_type=error_info.get("error_type", "Unknown"),
                    error_message=error_info.get("error_message", "")[:500],
                    severity=severity, language=language, services=[],
                    root_cause=extracted_rc,
                    resolution=extracted_res,
                    raw_log=log_input[:2000], full_rca=final_output,
                )

                # Refresh sidebar incident memory count in real-time
                _store_status = _store_result.get("status", "")
                if _store_status in ("stored", "updated"):
                    _render_incident_memory_sidebar()
                    st.sidebar.success(f"✓ Incident `{_store_result.get('incident_id', '')}` saved to memory")
            except Exception:
                pass

        except Exception as e:
            status.empty()
            st.error(f"Failed: {str(e)}")
            st.exception(e)
        finally:
            st.session_state.is_investigating = False

# ─────────────────────────────────────────────────
# Re-render last RCA from session state (survives reruns)
# This shows the RCA + Slack button even after a button
# click triggers a Streamlit rerun.
# ─────────────────────────────────────────────────
elif st.session_state.last_rca and not st.session_state.is_investigating:
    _rca = st.session_state.last_rca
    _sev = _rca["severity"]
    _final = _rca["final_output"]
    _einfo = _rca["error_info"]

    st.markdown("---")
    st.markdown(
        f'<div class="rca-box"><div class="rca-title">'
        f'<span style="font-size:1.2rem;">📊</span>'
        f'<h3>Root Cause Analysis</h3>'
        f'<span class="sev-badge sev-{_sev}">{_sev}</span>'
        f'</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(_final)

    # Slack button
    if Config.SLACK_WEBHOOK_URL:
        _sc1, _sc2 = st.columns([1, 4])
        with _sc1:
            def _on_slack_click_restore():
                ok, msg = _send_to_slack()
                st.session_state.slack_sent = msg
            st.button("💬 Send to Slack", use_container_width=True,
                      key="slack_send_restore", on_click=_on_slack_click_restore)
        if st.session_state.slack_sent:
            _msg = st.session_state.slack_sent
            if _msg.startswith("✓"):
                st.success(_msg)
            else:
                st.error(_msg)
            st.session_state.slack_sent = False

# ─────────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────────
st.markdown("")
with st.expander("How it works"):
    st.markdown("""
**IncidentIQ** investigates incidents like a senior engineer:

**1. Parse** — Detects language, error type, severity, affected services from your log.

**2. Search internally** — Checks uploaded runbooks using semantic search (not keywords).

**3. Research externally** — Searches Stack Overflow, GitHub, official docs for solutions.

**4. Synthesize** — Combines evidence into a structured RCA with root cause, fix commands, and prevention steps.

Each investigation is saved so the system recognizes recurring issues over time.
""")
