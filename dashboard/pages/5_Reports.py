"""
Reports — PDF report generation and download.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
from datetime import datetime, timedelta, timezone
from dashboard.utils.api_client import download_report

st.set_page_config(page_title="Reports", layout="wide")
st.title("📄 PDF Reports")

st.markdown(
    "Generate a downloadable PDF analytics report containing:\n"
    "- Cover page with date range and timestamp\n"
    "- Analytics summary table (sentiment, category, priority counts)\n"
    "- Embedded trend charts (sentiment line, category bar)\n"
    "- Full feedback list with priority colour coding\n"
    "- Groq-generated executive summary"
)
st.divider()

# ---------------------------------------------------------------------------
# Date range picker
# ---------------------------------------------------------------------------
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input(
        "From date",
        value=datetime.now(timezone.utc).date() - timedelta(days=30),
    )
with col2:
    end_date = st.date_input(
        "To date",
        value=datetime.now(timezone.utc).date(),
    )

if start_date > end_date:
    st.error("Start date must be before end date.")
    st.stop()

# ---------------------------------------------------------------------------
# Generate & download
# ---------------------------------------------------------------------------
if st.button("📥 Generate PDF Report"):
    with st.spinner("Generating report — this may take a few seconds..."):
        try:
            pdf_bytes = download_report(
                start_date=str(start_date),
                end_date=str(end_date),
            )
            st.success("✅ Report ready!")
            filename = f"feedback_report_{start_date}_{end_date}.pdf"
            st.download_button(
                label="⬇️ Download PDF",
                data=pdf_bytes,
                file_name=filename,
                mime="application/pdf",
            )
        except Exception as exc:
            st.error(f"Failed to generate report: {exc}")
