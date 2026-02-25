"""
Google Play Store review scraper.

Dependency: google-play-scraper
Install:    pip install google-play-scraper
"""

import logging
import time
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def _retry_with_backoff(func, *args, max_retries=3, initial_delay=1.0, **kwargs):
    """Helper to retry a function with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            if attempt == max_retries - 1:
                # Last attempt, re-raise the exception
                raise
            
            delay = initial_delay * (2 ** attempt)
            logger.warning(
                "Attempt %d/%d failed: %s. Retrying in %.1fs...",
                attempt + 1, max_retries, str(exc), delay
            )
            time.sleep(delay)
    
    return None  # Should never reach here


def _to_item(review: dict, app_id: str) -> Dict[str, Any] | None:
    """Convert a raw google-play-scraper review dict to a normalised item."""
    text = (review.get("content") or "").strip()
    if not text:
        return None
    return {
        "text": text,
        "source": "google_play",
        "app_id": app_id,
        "external_id": review.get("reviewId"),
        "rating": review.get("score"),          # 1-5
        "reviewed_at": review.get("at"),         # datetime object
    }


def scrape_reviews(
    app_id: str,
    count: int = 100,
    lang: str = "en",
    country: str = "us",
    fetch_all: bool = False,
) -> List[Dict[str, Any]]:
    """
    Fetch reviews from the Google Play Store with retry logic.

    Args:
        app_id:    Play Store app ID, e.g. "com.spotify.music"
        count:     Max reviews when fetch_all=False (default 100)
        lang:      Language code (default "en")
        country:   Country code (default "us")
        fetch_all: When True, paginate through ALL available reviews
                   (can be tens of thousands; may take several minutes).

    Returns:
        List of dicts with keys: text, source, app_id, external_id, rating, reviewed_at
    
    Raises:
        ImportError: If google-play-scraper is not installed
        Exception: If scraping fails after all retries
    """
    try:
        from google_play_scraper import reviews, reviews_all, Sort  # type: ignore
    except ImportError as exc:
        logger.error("google-play-scraper package not found")
        raise ImportError(
            "google-play-scraper is required. Install with: pip install google-play-scraper"
        ) from exc
    
    if not app_id or not app_id.strip():
        raise ValueError("app_id cannot be empty")

    try:
        if fetch_all:
            logger.info("Fetching ALL Play Store reviews for %s (this may take a while)…", app_id)
            # Use retry logic for fetching all reviews
            raw = _retry_with_backoff(
                reviews_all,
                app_id,
                lang=lang,
                country=country,
                sort=Sort.NEWEST,
            )
        else:
            logger.info("Fetching up to %d Play Store reviews for %s...", count, app_id)
            # Use retry logic for fetching reviews
            result = _retry_with_backoff(
                reviews,
                app_id,
                lang=lang,
                country=country,
                sort=Sort.NEWEST,
                count=count,
            )
            raw, _ = result

        items: List[Dict[str, Any]] = []
        for review in raw:
            item = _to_item(review, app_id)
            if item:
                items.append(item)

        logger.info("Successfully scraped %d Play Store reviews for %s", len(items), app_id)
        return items

    except Exception as exc:
        error_msg = str(exc)
        logger.error("Failed to scrape Play Store reviews for %s: %s", app_id, error_msg)
        
        # Provide helpful error messages for common issues
        if "404" in error_msg or "not found" in error_msg.lower():
            raise ValueError(
                f"App not found in Play Store: {app_id}. "
                "Please verify the app ID is correct."
            ) from exc
        elif "429" in error_msg or "rate limit" in error_msg.lower():
            raise Exception(
                f"Rate limited by Play Store for {app_id}. "
                "Please wait before trying again."
            ) from exc
        elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            raise Exception(
                f"Request timed out while scraping {app_id}. "
                "The Play Store may be experiencing issues."
            ) from exc
        else:
            # Re-raise with more context
            raise Exception(
                f"Play Store scraping failed for {app_id}: {error_msg}"
            ) from exc
