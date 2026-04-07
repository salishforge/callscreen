"""Message templates package."""

from callscreen.messaging.templates.call_notification import render_call_notification
from callscreen.messaging.templates.urgent_alert import render_urgent_alert
from callscreen.messaging.templates.voicemail_notification import render_voicemail_notification

__all__ = [
    "render_call_notification",
    "render_urgent_alert",
    "render_voicemail_notification",
]
