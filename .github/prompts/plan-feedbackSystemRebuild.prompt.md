# Plan: Feedback System — Full Rebuild in 6 Phases

The system has a working FastAPI + SQLite core with real ML pipelines, but the rejected features (external scraping, Streamlit, PDF reports, real trend detection) are absent. The plan fixes existing bugs first, then adds each missing capability in dependency order. Groq API replaces the heavy local transformer models (DistilBERT 268 MB + BART 1.6 GB) for speed and efficiency. Streamlit replaces the HTML/JS frontend as a second Docker service.

---

## Phase 1 — Foundation & Bug Fixes

Fix all broken or misleading code before extending anything.

**Steps**
1. **Schema bug** — add `source: str = "web"` field to `FeedbackCreate` in `app/schemas.py` so the `POST /feedback` route stops crashing on `data.source`
2. **Blocking inference** — wrap `process_feedback()` call in `app/api/routes.py` with `asyncio.get_event_loop().run_in_executor(None, ...)` so ML inference doesn't block the async event loop
3. **CSV ingestion duplication** — delete the inline loop in `app/api/routes.py` `/upload` handler; call the existing `process_email_batch`-style function from `app/services/ingestion.py` instead
4. **Missing category** — add `"feature_request"` to `CATEGORIES` in `app/services/category_model.py`; update the `Feedback` model's `CharField(50)` in `app/models.py`
5. **Dependency cleanup** — remove unused `textblob` from `pyproject.toml`; move `ruff` to `[project.optional-dependencies]` dev group
6. **Test skeleton** — create `tests/` directory with `test_routes.py` and `test_processing.py` using `pytest` + `httpx.AsyncClient`; cover the POST `/feedback` and `/analytics` endpoints at minimum

**Verification** — `pytest tests/` passes; `POST /feedback` with a source field returns 200; ML inference doesn't block `/health` checks under load

---

## Phase 2 — Groq LLM Integration

Replace the two heavy local models (~1.8 GB total) with Groq API calls. Groq runs `llama-3.3-70b-versatile` inference in <500 ms, compared to the current 3–5 s blocking calls.

**Steps**
1. Add `groq` to `pyproject.toml` dependencies (`groq>=0.9.0`)
2. Add `GROQ_API_KEY` and `GROQ_MODEL` env vars to `docker-compose.yml` and document in `README.md`
3. Create `app/services/llm_service.py` — a single `analyze_feedback(text: str) -> dict` function that calls Groq with a structured prompt and returns `{sentiment, sentiment_confidence, category, category_confidence, summary}` in one API call (JSON mode)
4. Update `app/services/processing.py` — replace the three separate calls to `analyze_sentiment_detailed()` and `categorize_detailed()` with a single call to `llm_service.analyze_feedback()`; keep the existing priority scoring in `app/services/priority.py`
5. Add `LOCAL_FALLBACK=true` env var — if Groq is unavailable, fall back to existing DistilBERT/BART pipeline so the system degrades gracefully
6. Expose `summary` field: add `summary: Optional[str]` to `Feedback` model and schema; store the one-line Groq-generated summary alongside each item

**Verification** — `POST /feedback` completes in <1 s; response includes `summary` field; fallback path still works

---

## Phase 3 — Multi-Source Integration & Web Scraping

Implement real external ingestion: Google Play, App Store, and generic URL scraping using BeautifulSoup.

**Steps**
1. Add dependencies to `pyproject.toml`: `google-play-scraper>=1.2.7`, `app-store-scraper>=0.3.5`, `beautifulsoup4>=4.12`, `httpx>=0.27`, `apscheduler>=3.10`
2. Create `app/services/scrapers/` package with three modules:
   - `play_store.py` — wraps `google_play_scraper.reviews()`, takes `app_id` + `count` params, returns list of `{text, source="google_play"}`
   - `app_store.py` — wraps `app_store_scraper.AppStore`, takes `app_id` + `country`, returns list of `{text, source="app_store"}`
   - `web_scraper.py` — uses `httpx` + `BeautifulSoup`; accepts a CSS selector config dict; returns list of `{text, source="web_scrape"}`
3. Implement `fetch_emails()` in `app/services/ingestion.py` using Python `imaplib` and `email` stdlib; reads `EMAIL_HOST`, `EMAIL_USER`, `EMAIL_PASS` from env
4. Create `app/services/scheduler.py` — APScheduler `BackgroundScheduler` with configurable cron jobs per source; started at FastAPI `lifespan` startup in `app/main.py`
5. Add new routes to `app/api/routes.py`:
   - `POST /sources/scrape` — trigger manual scrape `{source_type, app_id, count}`
   - `GET /sources/status` — show configured scrapers + last run time + items fetched
6. Add `app_id`, `store_country` columns to `Feedback` model (optional, nullable) for traceability

**Verification** — `POST /sources/scrape` with a real Play Store app ID returns ingested feedback; scheduler logs show automated runs; BeautifulSoup selector config successfully extracts text from a sample URL

---

## Phase 4 — Streamlit Dashboard (replaces HTML/JS)

Build a multi-page Streamlit app as a second Docker service. The `static/` frontend is retired.

**Steps**
1. Add `streamlit>=1.35`, `plotly>=5.22`, `pandas>=2.0` to `pyproject.toml`
2. Create `dashboard/` directory at project root with:
   - `Home.py` — KPI cards (total feedback, avg sentiment, high-priority count), auto-refresh every 30 s via `st.rerun()`
   - `pages/1_Analytics.py` — Plotly pie/bar charts for sentiment, category, priority distributions; date range filter
   - `pages/2_Feedback_Browser.py` — filterable/searchable table with priority color coding; export button
   - `pages/3_Trends.py` — time-series line chart of daily sentiment counts; anomaly markers (from Phase 6)
   - `pages/4_Sources.py` — scraper status table; manual scrape trigger button via `POST /sources/scrape`
   - `pages/5_Reports.py` — PDF report configuration form; download button hitting `GET /reports/generate`
   - `utils/api_client.py` — thin wrapper around `httpx` → all Streamlit pages call the FastAPI backend; `API_BASE` from env
3. Create `dashboard/requirements.txt` pinning Streamlit deps separately from the API for clean Docker layering
4. Add `dashboard` service to `docker-compose.yml`: `streamlit run dashboard/Home.py --server.port 8501 --server.address 0.0.0.0`; depends on `feedback_app`; expose port 8501
5. Remove (or archive) `static/` directory; remove `StaticFiles` mount from `app/main.py`

**Verification** — `docker-compose up` serves FastAPI on :8000 and Streamlit on :8501; all pages load without error; feedback submitted via Streamlit form appears in the feedback browser

---

## Phase 5 — PDF Report Generation

Add a `/reports/generate` endpoint that returns a downloadable PDF using `reportlab`.

**Steps**
1. Add `reportlab>=4.2`, `matplotlib>=3.9` to `pyproject.toml`
2. Create `app/services/report_generator.py`:
   - `generate_report(start_date, end_date) -> bytes` — generates and returns a PDF byte string
   - **Page 1:** Cover page with title, date range, generation timestamp
   - **Page 2:** Analytics summary table (sentiment counts, category breakdown, priority breakdown) using `reportlab` `Table`
   - **Page 3:** Charts page — render Matplotlib figure to a PNG buffer; embed in PDF using `reportlab` `Image`; include sentiment trend line chart and category bar chart
   - **Page 4:** Full feedback list with priority-coloured left rule, text, category badge, sentiment label, timestamp
   - Groq-generated executive summary paragraph at the top (call `llm_service` with aggregated stats)
3. Add route `GET /reports/generate` in `app/api/routes.py` accepting `?start_date=&end_date=` query params; returns `StreamingResponse(content, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=feedback_report.pdf"})`
4. Wire the Streamlit `pages/5_Reports.py` (Phase 4) download button to this endpoint

**Verification** — `GET /reports/generate` returns a valid PDF; opening it shows all 4 sections with charts; Streamlit download button saves the file

---

## Phase 6 — Advanced Trend Detection

Replace the hardcoded "count > 50" spike detection with proper time-series analysis.

**Steps**
1. Create `app/services/trend_analysis.py` with:
   - `compute_rolling_average(df, window=7)` — 7-day rolling mean of daily negative feedback counts using pandas
   - `detect_anomalies_zscore(series, threshold=2.0)` — marks days where Z-score > threshold as anomalies
   - `compute_sentiment_trend(df)` — returns slope of linear regression over last 30 days (positive = improving, negative = worsening); uses `numpy.polyfit`
   - `detect_category_shift(df, lookback=14)` — compares category distribution in last 7 days vs 7–14 days ago; flags categories with >20% relative increase
2. Update `GET /trends` route in `app/api/routes.py` to return enriched response: `{daily_counts, rolling_average, anomaly_dates, sentiment_slope, category_shifts, spike_alerts}` — remove hardcoded thresholds
3. Update `app/services/alerts.py` to fire alerts based on Z-score anomalies and negative `sentiment_slope`, not raw count thresholds; structure alerts as `{type, severity, message, triggered_at}` and persist them to a new `Alert` Tortoise model
4. Wire anomaly markers to Streamlit `pages/3_Trends.py` (Phase 4) — overlay red dots on trend line chart where `anomaly_dates` match

**Verification** — `GET /trends` response includes `sentiment_slope` and `anomaly_dates`; injecting 100 negative records triggers a Z-score anomaly; trend chart in Streamlit shows markers on anomaly days

---

## Cross-Phase Verification
- `docker-compose up --build` brings up both API (:8000) and Streamlit (:8501)
- Full round-trip: scrape Play Store → ingest → Groq analysis → appears in Streamlit browser → trend chart updates → PDF report downloads with the new data
- `pytest tests/` covers all new services with mocked Groq + scraper calls

## Decisions
- **Groq API over local transformers** — eliminates 1.8 GB model weight download, reduces latency from ~4 s to <1 s
- **Streamlit replaces HTML/JS** — directly satisfies rejection criterion and adds real interactivity without custom JS
- **`reportlab` over `weasyprint`** — no system Chromium/wkhtmltopdf dependency — pure Python, simpler Docker image
- **APScheduler over Celery** — lower ops overhead for a single-container deployment; can swap to Celery + Redis later
