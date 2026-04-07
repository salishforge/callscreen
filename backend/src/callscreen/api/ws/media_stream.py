"""Twilio Media Stream WebSocket handler.

Handles the bidirectional WebSocket connection for Twilio's Media Streams,
receiving caller audio and optionally sending TTS audio back.

Protocol events:
  - connected: WebSocket established
  - start: Stream metadata (streamSid, callSid)
  - media: Base64-encoded audio chunks
  - stop: Stream ended
"""

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from callscreen.voice.audio.converter import base64_audio_chunk, decode_audio_chunk
from callscreen.voice.session import get_session_manager

logger = logging.getLogger("callscreen.api.ws.media_stream")

ws_router = APIRouter()


@ws_router.websocket("/ws/media-stream/{call_sid}")
async def media_stream_handler(websocket: WebSocket, call_sid: str) -> None:
    """Handle a Twilio Media Stream WebSocket connection.

    Args:
        websocket: The WebSocket connection.
        call_sid: The Twilio Call SID from the URL path.
    """
    await websocket.accept()
    logger.info("WebSocket accepted for call_sid=%s", call_sid)

    session_mgr = get_session_manager()
    session = session_mgr.get_session(call_sid)
    stream_sid: str | None = None

    if session is None:
        session = session_mgr.create_session(call_sid)

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                message = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                logger.warning("Received non-JSON message on call_sid=%s", call_sid)
                continue

            event = message.get("event")

            if event == "connected":
                logger.info(
                    "Twilio media stream connected for call_sid=%s", call_sid
                )

            elif event == "start":
                start_data = message.get("start", {})
                stream_sid = start_data.get("streamSid")
                msg_call_sid = start_data.get("callSid", call_sid)
                if session is not None:
                    session.stream_sid = stream_sid
                logger.info(
                    "Stream started: streamSid=%s callSid=%s",
                    stream_sid,
                    msg_call_sid,
                )

            elif event == "media":
                media_data = message.get("media", {})
                payload_b64 = media_data.get("payload", "")
                if payload_b64:
                    audio_bytes = decode_audio_chunk(payload_b64)
                    # Feed to STT if available
                    if session and session.stt_provider:
                        # Audio would be fed through the streaming pipeline.
                        # Actual integration happens in the voice session orchestrator.
                        pass
                    # Store raw chunk count for diagnostics
                    if session:
                        session.transcript_parts.append(f"chunk:{len(audio_bytes)}")

            elif event == "stop":
                logger.info(
                    "Stream stopped: streamSid=%s call_sid=%s",
                    stream_sid,
                    call_sid,
                )
                break

            else:
                logger.debug(
                    "Unknown event '%s' on call_sid=%s", event, call_sid
                )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for call_sid=%s", call_sid)
    except Exception:
        logger.exception("Error in media stream handler for call_sid=%s", call_sid)
    finally:
        session_mgr.end_session(call_sid)
        logger.info("Cleaned up session for call_sid=%s", call_sid)


async def send_audio_to_stream(
    websocket: WebSocket, stream_sid: str, audio_data: bytes
) -> None:
    """Send audio data back to Twilio over the media stream.

    Encodes the audio as base64 and wraps it in the Twilio media message format.

    Args:
        websocket: The active WebSocket connection.
        stream_sid: The Twilio Stream SID.
        audio_data: Raw mulaw audio bytes to send.
    """
    if not audio_data:
        return

    message = {
        "event": "media",
        "streamSid": stream_sid,
        "media": {
            "payload": base64_audio_chunk(audio_data),
        },
    }
    await websocket.send_text(json.dumps(message))
