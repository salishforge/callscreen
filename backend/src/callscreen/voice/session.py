"""Voice session manager for active call screening sessions.

Maintains an in-memory registry of active sessions, linking each call_sid
to its STT stream, TTS engine, and conversation context.
"""

import logging
import time
from dataclasses import dataclass, field

from callscreen.voice.stt.base import STTProvider
from callscreen.voice.tts.base import TTSProvider

logger = logging.getLogger("callscreen.voice.session")


@dataclass
class VoiceSession:
    """State for a single active voice screening session."""

    call_sid: str
    stream_sid: str | None = None
    stt_provider: STTProvider | None = None
    tts_provider: TTSProvider | None = None
    created_at: float = field(default_factory=time.time)
    transcript_parts: list[str] = field(default_factory=list)
    is_active: bool = True


class VoiceSessionManager:
    """In-memory manager for active voice screening sessions.

    Thread-safe for asyncio (single-threaded event loop).
    """

    def __init__(self) -> None:
        self._sessions: dict[str, VoiceSession] = {}

    def create_session(
        self,
        call_sid: str,
        *,
        stt_provider: STTProvider | None = None,
        tts_provider: TTSProvider | None = None,
    ) -> VoiceSession:
        """Create and register a new voice session.

        If a session already exists for this call_sid, it is replaced.

        Args:
            call_sid: Twilio Call SID.
            stt_provider: Optional STT provider instance.
            tts_provider: Optional TTS provider instance.

        Returns:
            The newly created VoiceSession.
        """
        session = VoiceSession(
            call_sid=call_sid,
            stt_provider=stt_provider,
            tts_provider=tts_provider,
        )
        self._sessions[call_sid] = session
        logger.info("Voice session created for call_sid=%s", call_sid)
        return session

    def get_session(self, call_sid: str) -> VoiceSession | None:
        """Retrieve an active session by call_sid.

        Returns None if no active session exists.
        """
        session = self._sessions.get(call_sid)
        if session is not None and not session.is_active:
            return None
        return session

    def end_session(self, call_sid: str) -> bool:
        """End and remove a session.

        Returns True if a session was found and ended, False otherwise.
        """
        session = self._sessions.pop(call_sid, None)
        if session is None:
            logger.debug("No session to end for call_sid=%s", call_sid)
            return False

        session.is_active = False
        logger.info("Voice session ended for call_sid=%s", call_sid)
        return True

    def active_session_count(self) -> int:
        """Return the number of currently active sessions."""
        return len(self._sessions)

    def list_sessions(self) -> list[VoiceSession]:
        """Return a list of all active sessions."""
        return list(self._sessions.values())


# Module-level singleton instance
_session_manager: VoiceSessionManager | None = None


def get_session_manager() -> VoiceSessionManager:
    """Get or create the global VoiceSessionManager singleton."""
    global _session_manager
    if _session_manager is None:
        _session_manager = VoiceSessionManager()
    return _session_manager
