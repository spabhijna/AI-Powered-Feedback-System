"""
Analytics — Sentiment, Category, Priority distribution charts with date filtering.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import plotly.express as px
import pandas as pd
from datetime import datetime, timedelta, timezone
from dashboard.utils.api_client import get_analytics, get_feedback

st.set_page_config(page_title="Analytics", layout="wide")
st.title("📈 Analytics")

# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Filters")
    days_back = st.slider("Show last N days", 1, 90, 30)
    refresh = st.button("🔄 Refresh")

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
try:
    analytics = get_analytics()
    all_feedback = get_feedback()
except Exception as exc:
    st.error(f"API error: {exc}")
    st.stop()

df = pd.DataFrame(all_feedback)

if df.empty:
    st.info("No feedback yet. Submit some via the Home page.")
    st.stop()

df["created_at"] = pd.to_datetime(df["created_at"], utc=True)
cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
df = df[df["created_at"] >= cutoff]

st.caption(f"Showing {len(df)} feedback items from the last {days_back} days")
st.divider()

# ---------------------------------------------------------------------------
# Charts row 1: Sentiment + Category
# ---------------------------------------------------------------------------
c1, c2 = st.columns(2)

with c1:
    st.subheader("Sentiment Distribution")
    sent_counts = df["sentiment"].value_counts().reset_index()
    sent_counts.columns = ["Sentiment", "Count"]
    fig = px.pie(
        sent_counts,
        names="Sentiment",
        values="Count",
        color="Sentiment",
        color_discrete_map={"positive": "#2ecc71", "negative": "#e74c3c", "neutral": "#95a5a6"},
    )
    st.plotly_chart(fig, use_container_width=True)

with c2:
    st.subheader("Category Distribution")
    cat_counts = df["category"].value_counts().reset_index()
    cat_counts.columns = ["Category", "Count"]
    fig2 = px.bar(
        cat_counts,
        x="Category",
        y="Count",
        color="Category",
        text_auto=True,
    )
    fig2.update_layout(showlegend=False)
    st.plotly_chart(fig2, use_container_width=True)

# ---------------------------------------------------------------------------
# Charts row 2: Priority + Source
# ---------------------------------------------------------------------------
c3, c4 = st.columns(2)

with c3:
    st.subheader("Priority Distribution")
    pri_counts = df["priority"].value_counts().reset_index()
    pri_counts.columns = ["Priority", "Count"]
    fig3 = px.pie(
        pri_counts,
        names="Priority",
        values="Count",
        color="Priority",
        color_discrete_map={"high": "#e74c3c", "moderate": "#f39c12", "low": "#2ecc71"},
        hole=0.4,
    )
    st.plotly_chart(fig3, use_container_width=True)

with c4:
    st.subheader("Source Distribution")
    src_counts = df["source"].value_counts().reset_index()
    src_counts.columns = ["Source", "Count"]
    fig4 = px.bar(src_counts, x="Source", y="Count", text_auto=True, color="Source")
    fig4.update_layout(showlegend=False)
    st.plotly_chart(fig4, use_container_width=True)

# ---------------------------------------------------------------------------
# Daily trend line
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Daily Feedback Volume")
df["date"] = df["created_at"].dt.date
daily = df.groupby(["date", "sentiment"]).size().reset_index(name="count")
fig5 = px.line(
    daily,
    x="date",
    y="count",
    color="sentiment",
    color_discrete_map={"positive": "#2ecc71", "negative": "#e74c3c", "neutral": "#95a5a6"},
    markers=True,
)
st.plotly_chart(fig5, use_container_width=True)
