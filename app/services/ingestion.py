"""
Multi-source ingestion service for feedback system.
Handles bulk imports from CSV, email, and other sources.
"""

import pandas as pd
import io
from typing import List, Dict, Any
from app.services.processing import process_feedback
from app.services.alerts import handle_alert
from app.models import Feedback


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
            sentiment, category, priority = process_feedback(text)

            # Create feedback entry
            feedback = await Feedback.create(
                text=text,
                sentiment=sentiment,
                category=category,
                priority=priority,
                source="csv",
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
            sentiment, category, priority = process_feedback(email_text)

            # Create feedback entry
            feedback = await Feedback.create(
                text=email_text,
                sentiment=sentiment,
                category=category,
                priority=priority,
                source="email",
            )

            # Trigger alerts
            handle_alert(feedback)

            results.append(feedback)

        except Exception as e:
            errors.append(f"Email {idx + 1}: {str(e)}")

    return {"processed": len(results), "errors": errors, "results": results}


def fetch_emails():
    """
    Fetch unread emails from configured inbox.
    Stub for future implementation.

    Returns:
        Generator yielding email text content
    """
    # TODO: Implement IMAP email fetching
    # import imaplib
    # import email
    #
    # mail = imaplib.IMAP4_SSL("imap.gmail.com")
    # mail.login("email", "app_password")
    # mail.select("inbox")
    #
    # _, messages = mail.search(None, "UNSEEN")
    # for num in messages[0].split():
    #     _, msg_data = mail.fetch(num, "(RFC822)")
    #     msg = email.message_from_bytes(msg_data[0][1])
    #     text = msg.get_payload()
    #     yield text

    return []


async def process_emails_from_inbox():
    """
    Check inbox and process new emails as feedback.
    Stub for scheduled job implementation.
    """
    emails = list(fetch_emails())

    if emails:
        result = await process_email_batch(emails)
        print(f"📧 Processed {result['processed']} emails from inbox")
        return result

    return {"processed": 0, "errors": []}
