"""
Thin httpx wrapper — all dashboard pages call the FastAPI backend via this module.
API_BASE is read from the environment (default: http://localhost:8000).
"""

import os
import httpx

API_BASE = os.getenv("API_BASE", "http://localhost:8000").rstrip("/")

_client = httpx.Client(base_url=API_BASE, timeout=30)


def get_analytics() -> dict:
    return _client.get("/analytics").json()


def get_feedback(
    category: str = "",
    sentiment: str = "",
    priority: str = "",
    source: str = "",
) -> list:
    params = {k: v for k, v in {
        "category": category,
        "sentiment": sentiment,
        "priority": priority,
        "source": source,
    }.items() if v}
    return _client.get("/feedback", params=params).json()


def post_feedback(text: str, source: str = "streamlit") -> dict:
    return _client.post("/feedback", json={"text": text, "source": source}).json()


def upload_csv(file_bytes: bytes, filename: str) -> dict:
    return _client.post(
        "/upload",
        files={"file": (filename, file_bytes, "text/csv")},
    ).json()


def get_trends() -> dict:
    return _client.get("/trends").json()


def get_sources_status() -> dict:
    return _client.get("/sources/status").json()


def trigger_scrape(payload: dict) -> dict:
    return _client.post("/sources/scrape", json=payload).json()


def get_scraper_configs() -> list:
    return _client.get("/sources/configs").json()


def create_scraper_config(payload: dict) -> dict:
    return _client.post("/sources/configs", json=payload).json()


def delete_scraper_config(config_id: int) -> dict:
    return _client.delete(f"/sources/configs/{config_id}").json()


def toggle_scraper_config(config_id: int) -> dict:
    return _client.patch(f"/sources/configs/{config_id}/toggle").json()


def download_report(start_date: str = "", end_date: str = "") -> bytes:
    params = {}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    response = _client.get("/reports/generate", params=params)
    response.raise_for_status()
    return response.content


def health() -> dict:
    return _client.get("/health").json()
