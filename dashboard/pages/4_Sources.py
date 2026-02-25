"""
Sources — Scraper configuration and manual scrape trigger.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
from dashboard.utils.api_client import (
    get_sources_status,
    get_scraper_configs,
    create_scraper_config,
    delete_scraper_config,
    toggle_scraper_config,
    trigger_scrape,
)

st.set_page_config(page_title="Sources", layout="wide")
st.title("🔌 Data Sources")

# ---------------------------------------------------------------------------
# Scheduler status
# ---------------------------------------------------------------------------
try:
    status = get_sources_status()
except Exception as exc:
    st.error(f"API error: {exc}")
    st.stop()

enabled = status.get("enabled", False)
jobs = status.get("jobs", {})

if enabled:
    st.success("✅ Scheduler is running")
else:
    st.warning("⏸️ Scheduler is disabled. Set `SCHEDULER_ENABLED=true` in `.env` and restart the server.")

if jobs:
    st.subheader("Active Jobs")
    import pandas as pd
    jobs_df = pd.DataFrame([{"Job": name, **info} for name, info in jobs.items()])
    st.dataframe(jobs_df, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Saved scraper configurations
# ---------------------------------------------------------------------------
st.subheader("⚙️ Saved Scraper Configs")
st.caption("These run automatically on the configured interval when the scheduler is enabled.")

try:
    configs = get_scraper_configs()
except Exception as exc:
    st.error(f"Could not load configs: {exc}")
    configs = []

if configs:
    for c in configs:
        label = c.get("label") or c.get("app_id") or c.get("app_name") or f"Config {c['id']}"
        badge = "🟢" if c["enabled"] else "⚫"
        col1, col2, col3, col4 = st.columns([4, 2, 1, 1])
        with col1:
            st.markdown(
                f"{badge} **{label}** &nbsp; `{c['source_type']}` · "
                f"`{c.get('app_id') or c.get('app_name', '')}` · "
                f"every **{c['interval_hours']}h** · {c['count']} reviews · country `{c['country']}`"
            )
            if c.get("last_run_at"):
                st.caption(f"Last run: {c['last_run_at']}  ({c.get('last_run_count', 0)} items)")
        with col2:
            toggle_label = "Disable" if c["enabled"] else "Enable"
            if st.button(toggle_label, key=f"toggle_{c['id']}"):
                toggle_scraper_config(c["id"])
                st.rerun()
        with col3:
            if st.button("🗑️", key=f"del_{c['id']}", help="Delete this config"):
                delete_scraper_config(c["id"])
                st.rerun()
        with col4:
            if st.button("▶ Run now", key=f"run_{c['id']}"):
                payload = {
                    "source_type": c["source_type"],
                    "app_id": c.get("app_id"),
                    "app_name": c.get("app_name"),
                    "country": c.get("country", "us"),
                    "count": c.get("count", 50),
                }
                result = trigger_scrape(payload)
                if result.get("status") == "scrape_queued":
                    st.toast(f"✅ Queued: {label}")
                else:
                    st.error(f"Unexpected: {result}")
else:
    st.info("No saved configs yet. Add one below.")

st.divider()

# ---------------------------------------------------------------------------
# Add new scraper config
# ---------------------------------------------------------------------------
st.subheader("➕ Add Scraper Config")

with st.form("add_config_form", clear_on_submit=True):
    col_a, col_b = st.columns(2)
    with col_a:
        source_type = st.selectbox("Source type", ["google_play", "app_store"])
        label = st.text_input("Label (optional)", placeholder="My App – Play Store")
    with col_b:
        interval_hours = st.number_input("Scrape every N hours", min_value=1, max_value=168, value=6)
        count = st.slider("Reviews per run", 10, 200, 50)

    if source_type == "google_play":
        app_id = st.text_input("Play Store App ID *", placeholder="com.spotify.music")
        app_name = None
        country = st.text_input("Country code", value="us")
    else:
        app_name = st.text_input("App Store app name (slug) *", placeholder="spotify")
        app_id = st.text_input("Numeric App Store ID *", placeholder="324684580")
        country = st.text_input("Country code", value="us")

    submitted = st.form_submit_button("💾 Save Config")

if submitted:
    if source_type == "google_play" and not app_id:
        st.error("Play Store App ID is required.")
    elif source_type == "app_store" and (not app_id or not app_name):
        st.error("App Store requires both app name and numeric ID.")
    else:
        payload = {
            "source_type": source_type,
            "app_id": app_id or None,
            "app_name": app_name or None,
            "country": country or "us",
            "count": count,
            "interval_hours": int(interval_hours),
            "label": label or None,
        }
        result = create_scraper_config(payload)
        if result.get("status") == "created":
            st.success(f"✅ Config saved (id={result['id']}). Scheduler registered the job.")
            st.rerun()
        else:
            st.error(f"Unexpected response: {result}")

st.divider()

# ---------------------------------------------------------------------------
# One-off manual scrape
# ---------------------------------------------------------------------------
st.subheader("🚀 One-off Manual Scrape")
st.caption("Runs immediately in the background — does not create a saved config.")

source_type_manual = st.selectbox("Source type ", ["google_play", "app_store", "web"], key="manual_src")

manual_payload: dict = {"source_type": source_type_manual}

if source_type_manual == "google_play":
    manual_payload["app_id"] = st.text_input("Play Store App ID ", placeholder="com.spotify.music", key="m_pid")
    col_cnt, col_all = st.columns([2, 1])
    with col_all:
        fetch_all = st.checkbox(
            "Fetch ALL historical reviews",
            value=False,
            key="m_fetch_all",
            help="Uses reviews_all() to paginate through every available review. "
                 "Can return tens of thousands; may take several minutes.",
        )
    with col_cnt:
        if not fetch_all:
            manual_payload["count"] = st.slider("Number of reviews ", 10, 500, 50, key="m_cnt")
        else:
            st.info("Will fetch every available review (ignores the count slider).")
            manual_payload["count"] = 500
    manual_payload["fetch_all"] = fetch_all
    manual_payload["country"] = st.text_input("Country code ", value="us", key="m_cntry")

elif source_type_manual == "app_store":
    manual_payload["app_name"] = st.text_input("App name (slug) ", placeholder="spotify", key="m_aname")
    manual_payload["app_id"] = st.text_input("Numeric App ID ", placeholder="324684580", key="m_aid")
    manual_payload["country"] = st.text_input("Country code ", value="us", key="m_acntry")
    manual_payload["count"] = st.slider("Number of reviews ", 10, 200, 50, key="m_acnt")

elif source_type_manual == "web":
    manual_payload["url"] = st.text_input("URL to scrape", placeholder="https://example.com/reviews")
    manual_payload["css_selector"] = st.text_input("CSS selector", value="p", placeholder=".review-text")

if st.button("▶ Run Scrape Now"):
    with st.spinner("Queuing..."):
        result = trigger_scrape(manual_payload)
    if result.get("status") == "scrape_queued":
        st.success(f"✅ Scrape queued for **{source_type_manual}**. Results will appear in the Feedback Browser shortly.")
    else:
        st.error(f"Unexpected response: {result}")

st.divider()
st.caption(
    "Scheduler requires `SCHEDULER_ENABLED=true` in `.env`. "
    "Saved configs register jobs automatically — no restart needed after adding/removing configs."
)

# ---------------------------------------------------------------------------
# Scheduler status
# ---------------------------------------------------------------------------
try:
    status = get_sources_status()
except Exception as exc:
    st.error(f"API error: {exc}")
    st.stop()

enabled = status.get("enabled", False)
jobs = status.get("jobs", {})

if enabled:
    st.success("✅ Scheduler is running")
else:
    st.warning("⏸️ Scheduler is disabled. Set SCHEDULER_ENABLED=true and configure source env vars to activate.")

if jobs:
    st.subheader("Configured Jobs")
    import pandas as pd
    jobs_df = pd.DataFrame([
        {"Job": name, **info} for name, info in jobs.items()
    ])
    st.dataframe(jobs_df, use_container_width=True)
else:
    st.info("No automated scraping jobs configured.")

st.divider()

# ---------------------------------------------------------------------------
# Manual scrape trigger
# ---------------------------------------------------------------------------
st.subheader("Manual Scrape")

source_type = st.selectbox("Source type", ["google_play", "app_store", "web"])

payload = {"source_type": source_type}

if source_type == "google_play":
    payload["app_id"] = st.text_input("Play Store App ID", placeholder="com.spotify.music")
    payload["count"] = st.slider("Number of reviews", 10, 200, 50)
    payload["country"] = st.text_input("Country code", value="us")

elif source_type == "app_store":
    payload["app_name"] = st.text_input("App name (slug)", placeholder="spotify")
    payload["app_id"] = st.text_input("Numeric App ID", placeholder="324684580")
    payload["country"] = st.text_input("Country code", value="us")
    payload["count"] = st.slider("Number of reviews", 10, 200, 50)

elif source_type == "web":
    payload["url"] = st.text_input("URL to scrape", placeholder="https://example.com/reviews")
    payload["css_selector"] = st.text_input("CSS selector", value="p", placeholder=".review-text")

if st.button("🚀 Trigger Scrape"):
    with st.spinner("Queuing scrape job..."):
        result = trigger_scrape(payload)
    if result.get("status") == "scrape_queued":
        st.success(f"✅ Scrape queued for **{source_type}**. Results will appear in the Feedback Browser shortly.")
    else:
        st.error(f"Unexpected response: {result}")

st.divider()
st.caption(
    "To enable automated scraping, set these environment variables:\n\n"
    "- `SCHEDULER_ENABLED=true`\n"
    "- `PLAY_STORE_APP_ID=com.yourapp` + `PLAY_STORE_SCRAPE_HOURS=6`\n"
    "- `APP_STORE_APP_NAME=yourapp` + `APP_STORE_APP_ID=123456` + `APP_STORE_SCRAPE_HOURS=6`\n"
    "- `EMAIL_HOST`, `EMAIL_USER`, `EMAIL_PASS` + `EMAIL_POLL_MINUTES=30`"
)
