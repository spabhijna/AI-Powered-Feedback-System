"""
Feedback Browser — filterable, searchable table with priority color coding and CSV export.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
from dashboard.utils.api_client import get_feedback, upload_csv

st.set_page_config(page_title="Feedback Browser", layout="wide")
st.title("🗂️ Feedback Browser")

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Filters")
    f_sentiment = st.selectbox("Sentiment", ["", "positive", "negative", "neutral"])
    f_category = st.selectbox(
        "Category",
        ["", "billing", "technical", "performance", "general", "feature_request"],
    )
    f_priority = st.selectbox("Priority", ["", "high", "moderate", "low"])
    f_source = st.selectbox(
        "Source",
        ["", "web", "api", "csv", "email", "google_play", "app_store", "web_scrape", "streamlit"],
    )
    search_text = st.text_input("Search text", placeholder="keyword...")

    st.divider()
    st.header("CSV Upload")
    uploaded = st.file_uploader("Upload CSV (needs 'text' column)", type=["csv"])
    if uploaded and st.button("Process CSV"):
        with st.spinner("Processing..."):
            result = upload_csv(uploaded.read(), uploaded.name)
        st.success(f"Processed {result.get('processed', 0)} items")
        if result.get("errors"):
            st.warning(f"{result.get('total_errors')} errors")

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
try:
    items = get_feedback(
        category=f_category,
        sentiment=f_sentiment,
        priority=f_priority,
        source=f_source,
    )
except Exception as exc:
    st.error(f"API error: {exc}")
    st.stop()

df = pd.DataFrame(items)

if df.empty:
    st.info("No feedback matches the selected filters.")
    st.stop()

df["created_at"] = pd.to_datetime(df["created_at"], utc=True).dt.strftime("%Y-%m-%d %H:%M")

# Text search
if search_text:
    df = df[df["text"].str.contains(search_text, case=False, na=False)]

st.caption(f"{len(df)} items")

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
col_exp, _ = st.columns([1, 4])
with col_exp:
    csv_bytes = df.to_csv(index=False).encode()
    st.download_button("⬇️ Export CSV", csv_bytes, "feedback_export.csv", "text/csv")

st.divider()

# ---------------------------------------------------------------------------
# Priority-coloured cards (paginated)
# ---------------------------------------------------------------------------
PAGE_SIZE = 15

if "fb_page" not in st.session_state:
    st.session_state.fb_page = 0

total_pages = max(1, (len(df) - 1) // PAGE_SIZE + 1)
page = st.session_state.fb_page
start = page * PAGE_SIZE
end = start + PAGE_SIZE
page_df = df.iloc[start:end]

PRIORITY_COLOR = {"high": "#e74c3c", "moderate": "#f39c12", "low": "#2ecc71"}
SENTIMENT_COLOR = {"positive": "#2ecc71", "negative": "#e74c3c", "neutral": "#95a5a6"}

for _, row in page_df.iterrows():
    border_color = PRIORITY_COLOR.get(row.get("priority", "low"), "#ccc")
    sent_color = SENTIMENT_COLOR.get(row.get("sentiment", "neutral"), "#ccc")
    with st.container():
        st.markdown(
            f"""
            <div style="border-left: 5px solid {border_color}; padding: 8px 12px;
                        background: #f8f9fa; border-radius: 4px; margin-bottom: 8px;">
                <small style="color:#888;">{row.get('created_at','')} &bull;
                    <b>{row.get('source','')}</b> &bull;
                    ID #{row.get('id','')}</small><br>
                <span>{row.get('text','')[:300]}</span><br>
                <span style="background:{sent_color};color:#fff;padding:2px 6px;
                    border-radius:3px;font-size:12px;">{row.get('sentiment','')}</span>&nbsp;
                <span style="background:#3498db;color:#fff;padding:2px 6px;
                    border-radius:3px;font-size:12px;">{row.get('category','')}</span>&nbsp;
                <span style="background:{border_color};color:#fff;padding:2px 6px;
                    border-radius:3px;font-size:12px;">{row.get('priority','')}</span>
                {'<br><i style="color:#555;font-size:12px;">'+str(row["summary"])+'</i>' if row.get("summary") else ''}
            </div>
            """,
            unsafe_allow_html=True,
        )

# Pagination controls
pcol1, pcol2, pcol3 = st.columns([1, 2, 1])
with pcol1:
    if st.button("← Prev") and page > 0:
        st.session_state.fb_page -= 1
        st.rerun()
with pcol2:
    st.caption(f"Page {page + 1} of {total_pages}")
with pcol3:
    if st.button("Next →") and page < total_pages - 1:
        st.session_state.fb_page += 1
        st.rerun()
