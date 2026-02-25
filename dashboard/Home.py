"""
Feedback System — Home Dashboard
KPI overview with auto-refresh every 30 seconds.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import streamlit as st
from dashboard.utils.api_client import get_analytics, health

st.set_page_config(
    page_title="Feedback System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📊 AI-Powered Feedback System")
st.caption("Real-time customer feedback analysis powered by Groq LLM")

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
try:
    h = health()
    st.sidebar.success(f"API: {h.get('status', 'unknown').upper()}")
except Exception:
    st.sidebar.error("API unreachable")

# ---------------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------------
try:
    data = get_analytics()
except Exception as exc:
    st.error(f"Could not load analytics: {exc}")
    st.stop()

total = data.get("total_feedback", 0)
sent = data.get("sentiment_distribution", {})
prior = data.get("priority_distribution", {})
cat = data.get("category_distribution", {})

positive = sent.get("positive", 0)
negative = sent.get("negative", 0)
high_priority = prior.get("high", 0)
pct_positive = round(positive / total * 100, 1) if total else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Feedback", total)
col2.metric("Positive Sentiment", f"{pct_positive}%", delta=f"{positive} items")
col3.metric("Negative Feedback", negative)
col4.metric("High Priority", high_priority)

st.divider()

# ---------------------------------------------------------------------------
# Quick breakdown tables
# ---------------------------------------------------------------------------
lcol, rcol = st.columns(2)

with lcol:
    st.subheader("Sentiment Breakdown")
    if sent:
        for label, count in sorted(sent.items(), key=lambda x: -x[1]):
            pct = round(count / total * 100, 1) if total else 0
            st.progress(pct / 100, text=f"{label.capitalize()}: {count} ({pct}%)")
    else:
        st.info("No data yet.")

with rcol:
    st.subheader("Category Breakdown")
    if cat:
        for label, count in sorted(cat.items(), key=lambda x: -x[1]):
            pct = round(count / total * 100, 1) if total else 0
            st.progress(pct / 100, text=f"{label.replace('_', ' ').title()}: {count} ({pct}%)")
    else:
        st.info("No data yet.")

st.caption(f"💡 Insight: {data.get('insight', 'N/A')}")
st.divider()

# ---------------------------------------------------------------------------
# Submit feedback inline
# ---------------------------------------------------------------------------
st.subheader("Submit Feedback")
with st.form("quick_feedback"):
    text = st.text_area("Feedback text", height=100)
    submitted = st.form_submit_button("Submit")
    if submitted and text.strip():
        from dashboard.utils.api_client import post_feedback
        with st.spinner("Analysing..."):
            result = post_feedback(text.strip())
        st.success(
            f"✅ Sentiment: **{result.get('sentiment')}** | "
            f"Category: **{result.get('category')}** | "
            f"Priority: **{result.get('priority')}**"
        )
        if result.get("summary"):
            st.info(f"Summary: {result['summary']}")

# ---------------------------------------------------------------------------
# Auto-refresh
# ---------------------------------------------------------------------------
st.caption("Auto-refreshes every 30 seconds")
time.sleep(30)
st.rerun()
