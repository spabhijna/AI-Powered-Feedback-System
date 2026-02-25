"""
Generic web scraper using httpx + BeautifulSoup4.

Dependency: beautifulsoup4, httpx
Install:    pip install beautifulsoup4 httpx
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def scrape_url(
    url: str,
    css_selector: str = "p",
    source_label: str = "web_scrape",
    min_length: int = 20,
    headers: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """
    Scrape text content from a URL using a CSS selector.

    Args:
        url:          Target URL to scrape
        css_selector: CSS selector that identifies review/feedback elements
                      e.g. ".review-text", "p.comment", "li.feedback"
        source_label: Value stored in the `source` DB field (default "web_scrape")
        min_length:   Ignore elements with fewer characters (default 20)
        headers:      Optional custom HTTP headers (e.g. User-Agent)

    Returns:
        List of dicts: [{"text": str, "source": str}, ...]
    """
    try:
        import httpx
        from bs4 import BeautifulSoup  # type: ignore
    except ImportError:
        raise ImportError("httpx and beautifulsoup4 are required: pip install httpx beautifulsoup4")

    default_headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; FeedbackBot/1.0; "
            "+https://github.com/feedback-system)"
        )
    }
    if headers:
        default_headers.update(headers)

    response = httpx.get(url, headers=default_headers, follow_redirects=True, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    elements = soup.select(css_selector)

    items: List[Dict[str, Any]] = []
    for el in elements:
        text = el.get_text(separator=" ", strip=True)
        if len(text) >= min_length:
            items.append({"text": text, "source": source_label})

    logger.info("Scraped %d items from %s using selector '%s'", len(items), url, css_selector)
    return items


def scrape_multiple(
    configs: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Scrape multiple URLs using a list of config dicts.

    Each config dict should have the same keys as `scrape_url` parameters:
        url, css_selector, source_label (optional), min_length (optional)

    Returns:
        Flat list of all scraped items.
    """
    all_items: List[Dict[str, Any]] = []
    for cfg in configs:
        try:
            items = scrape_url(**cfg)
            all_items.extend(items)
        except Exception as exc:
            logger.error("Failed to scrape %s: %s", cfg.get("url"), exc)
    return all_items
