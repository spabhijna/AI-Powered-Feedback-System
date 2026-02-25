"""
Trends — Time-series sentiment analysis with Z-score anomaly markers.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from dashboard.utils.api_client import get_trends, get_feedback

st.set_page_config(page_title="Trends", layout="wide")
st.title("📉 Trends & Anomaly Detection")

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
try:
    trends = get_trends()
    all_feedback = get_feedback()
except Exception as exc:
    st.error(f"API error: {exc}")
    st.stop()

# ---------------------------------------------------------------------------
# Alerts banner
# ---------------------------------------------------------------------------
alerts = trends.get("alerts", [])
if alerts:
    for alert in alerts:
        sev = alert.get("severity", "moderate")
        if sev == "high":
            st.error(f"🚨 {alert.get('message')}")
        else:
            st.warning(f"⚠️ {alert.get('message')}")
else:
    st.success("✅ No active alerts — feedback levels are normal")

st.divider()

# Trend analysis metrics (Phase 6 fields)
col1, col2, col3 = st.columns(3)
slope = trends.get("sentiment_slope")
anomaly_dates = trends.get("anomaly_dates", [])

col1.metric("7-day Total", trends.get("total_feedback", 0))
col2.metric(
    "Sentiment Trend",
    "Improving ↑" if slope and slope > 0 else ("Worsening ↓" if slope and slope < 0 else "Stable →"),
    delta=f"slope {slope:.4f}" if slope is not None else None,
)
col3.metric("Anomaly Days Detected", len(anomaly_dates))

st.divider()

# ---------------------------------------------------------------------------
# Daily time-series chart
# ---------------------------------------------------------------------------
df = pd.DataFrame(all_feedback)
if df.empty:
    st.info("No feedback data yet.")
    st.stop()

df["created_at"] = pd.to_datetime(df["created_at"], utc=True)
df["date"] = df["created_at"].dt.date

# Build daily counts per sentiment
pivot = df.groupby(["date", "sentiment"]).size().unstack(fill_value=0).reset_index()

fig = go.Figure()
color_map = {"positive": "#2ecc71", "negative": "#e74c3c", "neutral": "#95a5a6"}

for col in [c for c in pivot.columns if c != "date"]:
    fig.add_trace(go.Scatter(
        x=pivot["date"],
        y=pivot[col],
        mode="lines+markers",
        name=col.capitalize(),
        line=dict(color=color_map.get(col, "#aaa")),
    ))

# Overlay anomaly markers on the negative line if present
if anomaly_dates and "negative" in pivot.columns:
    anomaly_df = pivot[pivot["date"].astype(str).isin(anomaly_dates)]
    fig.add_trace(go.Scatter(
        x=anomaly_df["date"],
        y=anomaly_df.get("negative", []),
        mode="markers",
        name="Anomaly",
        marker=dict(color="red", size=12, symbol="x"),
    ))

fig.update_layout(title="Daily Sentiment Volume", xaxis_title="Date", yaxis_title="Count")
st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Rolling average (if available)
# ---------------------------------------------------------------------------
rolling = trends.get("rolling_average")
if rolling:
    st.subheader("7-Day Rolling Average (Negative)")
    roll_df = pd.DataFrame(rolling.items(), columns=["date", "avg"]) if isinstance(rolling, dict) else pd.DataFrame(rolling)
    fig2 = go.Figure(go.Scatter(x=roll_df.iloc[:, 0], y=roll_df.iloc[:, 1], mode="lines", fill="tozeroy"))
    fig2.update_layout(xaxis_title="Date", yaxis_title="Rolling Avg")
    st.plotly_chart(fig2, use_container_width=True)

# ---------------------------------------------------------------------------
# Category shifts
# ---------------------------------------------------------------------------
cat_shifts = trends.get("category_shifts")
if cat_shifts:
    st.subheader("Category Shifts (vs. prior 7 days)")
    st.dataframe(pd.DataFrame(cat_shifts), use_container_width=True)

st.divider()
st.subheader("7-Day Distribution Summary")
c1, c2 = st.columns(2)
c1.json(trends.get("sentiment_distribution", {}))
c2.json(trends.get("category_distribution", {}))
