"""
Multi-source ingestion service for feedback system.
Handles bulk imports from CSV, email, scrapers, and other sources.
"""

import os
import imaplib
import email as email_lib
import logging
import pandas as pd
import io
from typing import List, Dict, Any, Generator
from app.services.processing import process_feedback
from app.services.alerts import handle_alert
from app.models import Feedback

logger = logging.getLogger(__name__)


async def process_csv_data(content: bytes) -> Dict[str, Any]:
    """
    Process CSV file content and create feedback entries.

    Args:
        content: Raw CSV file bytes

    Returns:
        Dictionary with processed count and errors
    """
    df = pd.read_csv(io.BytesIO(content))

    # Validate required columns
    if "text" not in df.columns:
        return {"error": "CSV must have 'text' column", "processed": 0, "errors": []}

    results = []
    errors = []

    for idx, row in df.iterrows():
        try:
            text = str(row["text"]).strip()

            if not text or text == "nan":
                errors.append(f"Row {idx + 1}: Empty text")
                continue

            # Process feedback
            sentiment, category, priority, summary = process_feedback(text)

            # Create feedback entry
            feedback = await Feedback.create(
                text=text,
                sentiment=sentiment,
                category=category,
                priority=priority,
                source="csv",
                summary=summary,
            )

            # Trigger alerts for high priority
            handle_alert(feedback)

            results.append(feedback)

        except Exception as e:
            errors.append(f"Row {idx + 1}: {str(e)}")

    return {
        "processed": len(results),
        "errors": errors[:10],  # Return first 10 errors only
        "total_errors": len(errors),
        "results": results,
    }


async def process_email_batch(emails: List[str]) -> Dict[str, Any]:
    """
    Process a batch of emails as feedback.
    Future implementation for email ingestion.

    Args:
        emails: List of email text content

    Returns:
        Dictionary with processed count and errors
    """
    results = []
    errors = []

    for idx, email_text in enumerate(emails):
        try:
            # Process feedback
            sentiment, category, priority, summary = process_feedback(email_text)

            # Create feedback entry
            feedback = await Feedback.create(
                text=email_text,
                sentiment=sentiment,
                category=category,
                priority=priority,
                source="email",
                summary=summary,
            )

            # Trigger alerts
            handle_alert(feedback)

            results.append(feedback)

        except Exception as e:
            errors.append(f"Email {idx + 1}: {str(e)}")

    return {"processed": len(results), "errors": errors, "results": results}


def fetch_emails() -> Generator[str, None, None]:
    """
    Fetch unread emails from the configured IMAP inbox.

    Required environment variables:
        EMAIL_HOST  – IMAP server hostname, e.g. "imap.gmail.com"
        EMAIL_USER  – email address / login
        EMAIL_PASS  – app password or IMAP password

    Yields:
        Plain-text body of each unseen message.
    """
    host = os.getenv("EMAIL_HOST")
    user = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASS")

    if not all([host, user, password]):
        logger.warning("Email ingestion not configured — set EMAIL_HOST, EMAIL_USER, EMAIL_PASS")
        return

    try:
        mail = imaplib.IMAP4_SSL(host)
        mail.login(user, password)
        mail.select("inbox")

        _, message_ids = mail.search(None, "UNSEEN")
        for num in message_ids[0].split():
            try:
                _, msg_data = mail.fetch(num, "(RFC822)")
                raw = msg_data[0][1]
                msg = email_lib.message_from_bytes(raw)

                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            payload = part.get_payload(decode=True)
                            if payload:
                                body = payload.decode(errors="replace")
                                break
                else:
                    payload = msg.get_payload(decode=True)
                    if payload:
                        body = payload.decode(errors="replace")

                if body.strip():
                    yield body.strip()

            except Exception as exc:
                logger.error("Error parsing email %s: %s", num, exc)

        mail.logout()

    except Exception as exc:
        logger.error("IMAP connection failed: %s", exc)


async def process_emails_from_inbox() -> Dict[str, Any]:
    """
    Fetch unread emails and process them as feedback.
    Called by the APScheduler job.
    """
    emails = list(fetch_emails())

    if emails:
        result = await process_email_batch(emails)
        logger.info("Processed %d emails from inbox", result["processed"])
        return result

    return {"processed": 0, "errors": [], "results": []}


async def ingest_scraped_items(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Ingest a batch of items produced by any scraper module.

    Each item must have at minimum: {"text": str, "source": str}
    Optional fields: "app_id", "store_country", "external_id", "rating", "reviewed_at"

    Items with a non-null external_id that already exist in the DB are skipped
    (deduplication).

    process_feedback is CPU/IO-bound (LLM call) so it is dispatched to a thread
    pool executor to avoid blocking the event loop.

    Returns:
        Dict with processed / skipped / error counts.
    """
    import asyncio
    results = []
    errors = []
    skipped = 0
    loop = asyncio.get_event_loop()

    for idx, item in enumerate(items):
        try:
            text = item.get("text", "").strip()
            if not text:
                errors.append(f"Item {idx + 1}: Empty text")
                continue

            source = item.get("source", "web_scrape")
            app_id = item.get("app_id")
            store_country = item.get("store_country")
            external_id = item.get("external_id")
            rating = item.get("rating")
            reviewed_at = item.get("reviewed_at")

            # Dedup: skip if we already have this review stored
            if external_id:
                exists = await Feedback.filter(external_id=external_id).exists()
                if exists:
                    skipped += 1
                    continue

            # Run synchronous LLM/model call in a thread so the event loop stays free
            sentiment, category, priority, summary = await loop.run_in_executor(
                None, process_feedback, text
            )

            feedback = await Feedback.create(
                text=text,
                sentiment=sentiment,
                category=category,
                priority=priority,
                source=source,
                summary=summary,
                app_id=app_id,
                store_country=store_country,
                external_id=external_id,
                rating=rating,
                reviewed_at=reviewed_at,
            )

            handle_alert(feedback)
            results.append(feedback)

        except Exception as exc:
            errors.append(f"Item {idx + 1}: {exc}")

    return {
        "processed": len(results),
        "skipped": skipped,
        "errors": errors[:10],
        "total_errors": len(errors),
    }
