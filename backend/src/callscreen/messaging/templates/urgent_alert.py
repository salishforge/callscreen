"""Urgent alert message template."""

from html import escape


def render_urgent_alert(
    caller_name: str,
    caller_number: str,
    reason: str,
    summary: str = "",
    timestamp: str = "",
) -> dict[str, str]:
    """Render an urgent alert across text, HTML, and subject.

    Args:
        caller_name: Display name of the caller.
        caller_number: Phone number of the caller.
        reason: Why this alert is flagged as urgent.
        summary: Optional call summary.
        timestamp: Human-readable timestamp.

    Returns:
        Dict with 'subject', 'text', and 'html' keys.
    """
    subject = f"URGENT: Call from {caller_name} - {reason}"

    text = (
        f"URGENT ALERT\n"
        f"{'=' * 30}\n"
        f"Caller: {caller_name}\n"
        f"Number: {caller_number}\n"
        f"Reason: {reason}\n"
    )
    if summary:
        text += f"\nSummary: {summary}\n"
    if timestamp:
        text += f"\nTime: {timestamp}\n"
    text += "\nThis message requires immediate attention.\n"

    safe_name = escape(caller_name)
    safe_number = escape(caller_number)
    safe_reason = escape(reason)
    safe_summary = escape(summary)
    safe_timestamp = escape(timestamp)

    html = (
        "<div style='font-family:sans-serif;max-width:600px;margin:auto;"
        "border:2px solid #e74c3c;border-radius:8px;padding:16px;'>"
        "<h2 style='color:#e74c3c;'>URGENT ALERT</h2>"
        f"<p><strong>Caller:</strong> {safe_name}</p>"
        f"<p><strong>Number:</strong> {safe_number}</p>"
        f"<p><strong>Reason:</strong> {safe_reason}</p>"
    )
    if summary:
        html += f"<p><strong>Summary:</strong> {safe_summary}</p>"
    if timestamp:
        html += f"<p style='color:#7f8c8d;font-size:0.9em;'>Time: {safe_timestamp}</p>"
    html += (
        "<p style='color:#e74c3c;font-weight:bold;'>"
        "This message requires immediate attention.</p>"
        "</div>"
    )

    return {"subject": subject, "text": text, "html": html}
