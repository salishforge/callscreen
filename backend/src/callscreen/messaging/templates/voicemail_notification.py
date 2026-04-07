"""Voicemail notification message template."""

from html import escape


def render_voicemail_notification(
    caller_name: str,
    caller_number: str,
    summary: str,
    duration: int,
    audio_url: str = "",
    timestamp: str = "",
) -> dict[str, str]:
    """Render a voicemail notification across text, HTML, and subject.

    Args:
        caller_name: Display name of the caller.
        caller_number: Phone number of the caller.
        summary: AI-generated voicemail transcript/summary.
        duration: Voicemail duration in seconds.
        audio_url: URL to listen to the recording.
        timestamp: Human-readable timestamp.

    Returns:
        Dict with 'subject', 'text', and 'html' keys.
    """
    minutes, seconds = divmod(duration, 60)
    duration_str = f"{minutes}m {seconds}s" if minutes else f"{seconds}s"

    subject = f"Voicemail from {caller_name} ({duration_str})"

    text = (
        f"New Voicemail\n"
        f"{'=' * 30}\n"
        f"From: {caller_name} ({caller_number})\n"
        f"Duration: {duration_str}\n"
        f"\nSummary:\n{summary}\n"
    )
    if audio_url:
        text += f"\nListen: {audio_url}\n"
    if timestamp:
        text += f"\nReceived: {timestamp}\n"

    safe_name = escape(caller_name)
    safe_number = escape(caller_number)
    safe_summary = escape(summary)
    safe_audio = escape(audio_url)
    safe_timestamp = escape(timestamp)

    html = (
        "<div style='font-family:sans-serif;max-width:600px;margin:auto;'>"
        "<h2 style='color:#2c3e50;'>New Voicemail</h2>"
        f"<p><strong>From:</strong> {safe_name} ({safe_number})</p>"
        f"<p><strong>Duration:</strong> {duration_str}</p>"
        f"<div style='background:#f8f9fa;padding:12px;border-radius:6px;margin:12px 0;'>"
        f"<p style='margin:0;'><strong>Summary:</strong></p>"
        f"<p style='margin:4px 0;'>{safe_summary}</p>"
        f"</div>"
    )
    if audio_url:
        html += (
            f"<p><a href='{safe_audio}' style='color:#3498db;'>"
            f"Listen to Voicemail</a></p>"
        )
    if timestamp:
        html += f"<p style='color:#7f8c8d;font-size:0.9em;'>Received: {safe_timestamp}</p>"
    html += "</div>"

    return {"subject": subject, "text": text, "html": html}
