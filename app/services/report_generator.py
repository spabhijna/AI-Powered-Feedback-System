"""
PDF Report Generator using reportlab + matplotlib.

Generates a 4-section PDF:
  Page 1 – Cover (title, date range, generation timestamp, Groq executive summary)
  Page 2 – Analytics summary table (sentiment / category / priority counts)
  Page 3 – Embedded charts (sentiment line, category bar rendered via matplotlib)
  Page 4+ – Full feedback list with priority-colour left rule

Usage:
    from app.services.report_generator import generate_report
    pdf_bytes = generate_report(start_date, end_date)   # sync, run in executor
"""

import io
import asyncio
import logging
from collections import Counter
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
PRIORITY_COLORS = {
    "high":     (0.91, 0.30, 0.24),   # red
    "moderate": (0.95, 0.61, 0.07),   # amber
    "low":      (0.18, 0.80, 0.44),   # green
}
SENTIMENT_COLORS = {
    "positive": (0.18, 0.80, 0.44),
    "negative": (0.91, 0.30, 0.24),
    "neutral":  (0.58, 0.65, 0.65),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_feedback_sync(start: datetime, end: datetime) -> list:
    """Synchronously fetch feedback from DB (called from thread executor)."""
    return asyncio.run(_fetch_feedback_async(start, end))


async def _fetch_feedback_async(start: datetime, end: datetime) -> list:
    from app.models import Feedback
    return await Feedback.filter(
        created_at__gte=start,
        created_at__lte=end,
    ).order_by("created_at")


def _build_charts_image(feedbacks: list) -> bytes:
    """Render two Matplotlib charts and return a PNG byte buffer."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from collections import Counter

    sentiments = [f.sentiment for f in feedbacks]
    categories = [f.category for f in feedbacks]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

    # Sentiment pie
    sent_counts = Counter(sentiments)
    labels = list(sent_counts.keys())
    values = list(sent_counts.values())
    colors = [
        [int(c * 255) / 255 for c in SENTIMENT_COLORS.get(lbl, (0.5, 0.5, 0.5))]
        for lbl in labels
    ]
    ax1.pie(values, labels=[lbl.capitalize() for lbl in labels], colors=colors, autopct="%1.1f%%")
    ax1.set_title("Sentiment Distribution")

    # Category bar
    cat_counts = Counter(categories)
    ax2.bar(
        [c.replace("_", " ").title() for c in cat_counts.keys()],
        cat_counts.values(),
        color="#3498db",
    )
    ax2.set_title("Category Distribution")
    ax2.tick_params(axis="x", rotation=30)

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _executive_summary(sentiments: Counter, categories: Counter, priorities: Counter, total: int) -> str:
    """Generate an executive summary — tries Groq, falls back to template."""
    try:
        from app.services import llm_service
        if llm_service.is_available():
            import os
            from groq import Groq  # type: ignore
            client = Groq(api_key=os.getenv("GROQ_API_KEY"))
            prompt = (
                f"Write a 2-3 sentence executive summary for a customer feedback report. "
                f"Total: {total} items. "
                f"Sentiment: {dict(sentiments)}. "
                f"Categories: {dict(categories)}. "
                f"Priorities: {dict(priorities)}."
            )
            resp = client.chat.completions.create(
                model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.3,
            )
            return resp.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning("Groq summary failed: %s", exc)

    # Template fallback
    top_cat = categories.most_common(1)[0][0] if categories else "N/A"
    pct_neg = round(sentiments.get("negative", 0) / total * 100, 1) if total else 0
    return (
        f"This report covers {total} feedback items. "
        f"The most reported category is '{top_cat}'. "
        f"{pct_neg}% of feedback carries a negative sentiment — monitor for emerging issues."
    )


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_report(start: datetime, end: datetime) -> bytes:
    """
    Generate a complete PDF report for the given date range.

    Args:
        start: Start datetime (UTC)
        end:   End datetime (UTC)

    Returns:
        Raw PDF bytes.
    """
    from reportlab.lib.pagesizes import A4  # type: ignore
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle  # type: ignore
    from reportlab.lib.units import cm  # type: ignore
    from reportlab.lib import colors  # type: ignore
    from reportlab.platypus import (  # type: ignore
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        Image as RLImage, PageBreak, HRFlowable,
    )
    from reportlab.lib.enums import TA_CENTER  # type: ignore

    feedbacks = asyncio.run(_fetch_feedback_async(start, end))

    sentiments = Counter(f.sentiment for f in feedbacks)
    categories = Counter(f.category for f in feedbacks)
    priorities = Counter(f.priority for f in feedbacks)
    sources = Counter(f.source for f in feedbacks)
    total = len(feedbacks)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("CentreTitle", parent=styles["Title"], alignment=TA_CENTER, spaceAfter=12))
    styles.add(ParagraphStyle("SmallBody", parent=styles["Normal"], fontSize=9, leading=13))
    styles.add(ParagraphStyle("Caption", parent=styles["Normal"], fontSize=8, textColor=colors.grey))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2 * cm,
    )

    story = []

    # ------------------------------------------------------------------
    # Page 1 — Cover
    # ------------------------------------------------------------------
    story.append(Spacer(1, 3 * cm))
    story.append(Paragraph("AI-Powered Feedback System", styles["CentreTitle"]))
    story.append(Paragraph("Analytics Report", styles["CentreTitle"]))
    story.append(Spacer(1, 1 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#3498db")))
    story.append(Spacer(1, 0.5 * cm))

    meta = [
        ["Date Range:", f"{start.strftime('%Y-%m-%d')} — {end.strftime('%Y-%m-%d')}"],
        ["Generated At:", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")],
        ["Total Feedback Items:", str(total)],
    ]
    t = Table(meta, colWidths=[5 * cm, 10 * cm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f0f4f8")]),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#ddd")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 1 * cm))

    summary_text = _executive_summary(sentiments, categories, priorities, total)
    story.append(Paragraph("<b>Executive Summary</b>", styles["Heading2"]))
    story.append(Paragraph(summary_text, styles["SmallBody"]))

    story.append(PageBreak())

    # ------------------------------------------------------------------
    # Page 2 — Analytics Summary Table
    # ------------------------------------------------------------------
    story.append(Paragraph("Analytics Summary", styles["Heading1"]))
    story.append(Spacer(1, 0.4 * cm))

    def _dist_table(title: str, counter: Counter) -> None:
        story.append(Paragraph(title, styles["Heading2"]))
        rows = [["Label", "Count", "Percentage"]]
        for label, count in counter.most_common():
            pct = f"{count / total * 100:.1f}%" if total else "0%"
            rows.append([label.replace("_", " ").title(), str(count), pct])
        tbl = Table(rows, colWidths=[7 * cm, 4 * cm, 4 * cm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3498db")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4f8")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#ddd")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 0.4 * cm))

    _dist_table("Sentiment", sentiments)
    _dist_table("Category", categories)
    _dist_table("Priority", priorities)
    _dist_table("Source", sources)

    story.append(PageBreak())

    # ------------------------------------------------------------------
    # Page 3 — Charts
    # ------------------------------------------------------------------
    story.append(Paragraph("Charts", styles["Heading1"]))
    story.append(Spacer(1, 0.4 * cm))

    if feedbacks:
        try:
            chart_png = _build_charts_image(feedbacks)
            img_buf = io.BytesIO(chart_png)
            img = RLImage(img_buf, width=16 * cm, height=5.5 * cm)
            story.append(img)
        except Exception as exc:
            logger.warning("Chart generation failed: %s", exc)
            story.append(Paragraph(f"Charts unavailable: {exc}", styles["SmallBody"]))
    else:
        story.append(Paragraph("No data available for charts.", styles["SmallBody"]))

    story.append(PageBreak())

    # ------------------------------------------------------------------
    # Page 4 — Feedback List
    # ------------------------------------------------------------------
    story.append(Paragraph("Feedback List", styles["Heading1"]))
    story.append(Spacer(1, 0.4 * cm))

    for fb in feedbacks:
        priority = getattr(fb, "priority", "low")
        rgb = PRIORITY_COLORS.get(priority, (0.5, 0.5, 0.5))
        border_color = colors.Color(*rgb)

        header_text = (
            f"<font color='grey' size='8'>"
            f"#{fb.id} &bull; {fb.created_at.strftime('%Y-%m-%d %H:%M')} &bull; "
            f"{fb.source} &bull; {fb.category.replace('_', ' ').title()} &bull; "
            f"{fb.sentiment.capitalize()} &bull; <b>{fb.priority.upper()}</b>"
            f"</font>"
        )
        body_text = fb.text[:400] + ("…" if len(fb.text) > 400 else "")

        inner = [
            Paragraph(header_text, styles["Caption"]),
            Paragraph(body_text, styles["SmallBody"]),
        ]
        if getattr(fb, "summary", None):
            inner.append(Paragraph(f"<i>{fb.summary}</i>", styles["Caption"]))

        row_table = Table(
            [[inner]],
            colWidths=[15 * cm],
        )
        row_table.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LINEBEFORE", (0, 0), (0, -1), 4, border_color),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f9fafb")),
        ]))
        story.append(row_table)
        story.append(Spacer(1, 0.15 * cm))

    doc.build(story)
    buf.seek(0)
    return buf.read()
