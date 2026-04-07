"""Tests for the Twilio Media Stream WebSocket handler."""

import base64
import json

import pytest
from starlette.testclient import TestClient

from callscreen.voice.session import VoiceSessionManager, get_session_manager


def _make_app():
    """Create a minimal FastAPI app with only the WS router for testing."""
    from fastapi import FastAPI

    from callscreen.api.ws.media_stream import ws_router

    app = FastAPI()
    app.include_router(ws_router)
    return app


class TestMediaStreamWebSocket:
    def setup_method(self):
        # Reset the global session manager so tests are isolated
        import callscreen.voice.session as sess_mod

        sess_mod._session_manager = VoiceSessionManager()
        self.app = _make_app()
        self.client = TestClient(self.app)

    @pytest.mark.unit
    def test_connected_event(self):
        """The handler should accept the connection and process connected events."""
        with self.client.websocket_connect("/ws/media-stream/CA_TEST_1") as ws:
            ws.send_text(json.dumps({"event": "connected", "protocol": "Call"}))
            # Send stop to cleanly exit
            ws.send_text(json.dumps({"event": "stop"}))

    @pytest.mark.unit
    def test_start_event_extracts_stream_sid(self):
        """The handler should extract streamSid from a start event."""
        mgr = get_session_manager()

        with self.client.websocket_connect("/ws/media-stream/CA_TEST_2") as ws:
            ws.send_text(
                json.dumps(
                    {
                        "event": "start",
                        "start": {
                            "streamSid": "MZ_STREAM_123",
                            "callSid": "CA_TEST_2",
                            "accountSid": "AC_TEST",
                        },
                    }
                )
            )
            ws.send_text(json.dumps({"event": "stop"}))

        # After stop + cleanup, session should have been ended
        assert mgr.get_session("CA_TEST_2") is None

    @pytest.mark.unit
    def test_media_event_decodes_audio(self):
        """The handler should decode base64 audio from media events."""
        mgr = get_session_manager()

        audio_bytes = b"\x80\x7f\x00\xff"
        b64_payload = base64.b64encode(audio_bytes).decode("ascii")

        with self.client.websocket_connect("/ws/media-stream/CA_TEST_3") as ws:
            ws.send_text(
                json.dumps(
                    {
                        "event": "start",
                        "start": {
                            "streamSid": "MZ_STREAM_456",
                            "callSid": "CA_TEST_3",
                        },
                    }
                )
            )
            ws.send_text(
                json.dumps(
                    {
                        "event": "media",
                        "media": {
                            "payload": b64_payload,
                        },
                    }
                )
            )
            ws.send_text(json.dumps({"event": "stop"}))

        # Session cleaned up after stop
        assert mgr.get_session("CA_TEST_3") is None

    @pytest.mark.unit
    def test_stop_event_ends_session(self):
        """The stop event should trigger session cleanup."""
        mgr = get_session_manager()

        with self.client.websocket_connect("/ws/media-stream/CA_TEST_4") as ws:
            ws.send_text(json.dumps({"event": "connected"}))
            ws.send_text(json.dumps({"event": "stop"}))

        assert mgr.get_session("CA_TEST_4") is None

    @pytest.mark.unit
    def test_unknown_event_ignored(self):
        """Unknown events should be silently ignored."""
        with self.client.websocket_connect("/ws/media-stream/CA_TEST_5") as ws:
            ws.send_text(json.dumps({"event": "mark", "mark": {"name": "test"}}))
            ws.send_text(json.dumps({"event": "stop"}))

    @pytest.mark.unit
    def test_multiple_media_events(self):
        """Multiple media events should all be processed."""
        mgr = get_session_manager()

        with self.client.websocket_connect("/ws/media-stream/CA_TEST_6") as ws:
            ws.send_text(
                json.dumps(
                    {
                        "event": "start",
                        "start": {
                            "streamSid": "MZ_STREAM_789",
                            "callSid": "CA_TEST_6",
                        },
                    }
                )
            )
            for i in range(5):
                payload = base64.b64encode(bytes([i] * 160)).decode("ascii")
                ws.send_text(
                    json.dumps({"event": "media", "media": {"payload": payload}})
                )
            ws.send_text(json.dumps({"event": "stop"}))

        # Session cleaned up
        assert mgr.get_session("CA_TEST_6") is None
