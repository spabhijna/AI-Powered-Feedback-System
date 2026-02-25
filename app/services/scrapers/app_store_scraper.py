"""
Apple App Store review scraper.

Dependency: app-store-scraper
Install:    pip install app-store-scraper
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def scrape_reviews(app_name: str, app_id: str, country: str = "us", count: int = 100) -> List[Dict[str, Any]]:
    """
    Fetch recent reviews from the Apple App Store.

    Args:
        app_name: Human-readable app name (slug), e.g. "spotify"
        app_id:   Numeric App Store ID as a string, e.g. "324684580"
        country:  Two-letter country code (default "us")
        count:    Maximum number of reviews to fetch (default 100)

    Returns:
        List of dicts: [{"text": str, "source": "app_store", "app_id": str}, ...]
    """
    try:
        from app_store_scraper import AppStore  # type: ignore
    except ImportError:
        raise ImportError("app-store-scraper is required: pip install app-store-scraper")

    store = AppStore(country=country, app_name=app_name, app_id=app_id)
    store.review(how_many=count)

    items: List[Dict[str, Any]] = []
    for review in store.reviews:
        text = (review.get("review") or "").strip()
        if text:
            items.append({"text": text, "source": "app_store", "app_id": app_id})

    logger.info("Scraped %d App Store reviews for %s", len(items), app_name)
    return items
