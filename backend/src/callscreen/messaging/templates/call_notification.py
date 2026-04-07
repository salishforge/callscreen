"""Call notification message template."""

from html import escape


def render_call_notification(
    caller_name: str,
    caller_number: str,
    intent: str,
    trust_score: float,
    summary: str = "",
    timestamp: str = "",
) -> dict[str, str]:
    """Render a call notification across text, HTML, and subject.

    Args:
        caller_name: Display name of the caller.
        caller_number: Phone number of the caller.
        intent: Detected caller intent.
        trust_score: Numeric trust score (0.0 - 1.0).
        summary: AI-generated call summary.
        timestamp: Human-readable timestamp of the call.

    Returns:
        Dict with 'subject', 'text', and 'html' keys.
    """
    trust_pct = int(trust_score * 100)

    subject = f"Call from {caller_name} ({caller_number})"

    text = (
        f"Incoming Call Notification\n"
        f"{'=' * 30}\n"
        f"Caller: {caller_name}\n"
        f"Number: {caller_number}\n"
        f"Intent: {intent}\n"
        f"Trust Score: {trust_pct}%\n"
    )
    if summary:
        text += f"\nSummary: {summary}\n"
    if timestamp:
        text += f"\nTime: {timestamp}\n"

    safe_name = escape(caller_name)
    safe_number = escape(caller_number)
    safe_intent = escape(intent)
    safe_summary = escape(summary)
    safe_timestamp = escape(timestamp)

    html = (
        "<div style='font-family:sans-serif;max-width:600px;margin:auto;'>"
        "<h2 style='color:#2c3e50;'>Incoming Call Notification</h2>"
        f"<p><strong>Caller:</strong> {safe_name}</p>"
        f"<p><strong>Number:</strong> {safe_number}</p>"
        f"<p><strong>Intent:</strong> {safe_intent}</p>"
        f"<p><strong>Trust Score:</strong> {trust_pct}%</p>"
    )
    if summary:
        html += f"<p><strong>Summary:</strong> {safe_summary}</p>"
    if timestamp:
        html += f"<p style='color:#7f8c8d;font-size:0.9em;'>Time: {safe_timestamp}</p>"
    html += "</div>"

    return {"subject": subject, "text": text, "html": html}
