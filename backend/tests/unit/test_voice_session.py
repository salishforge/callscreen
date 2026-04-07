"""Tests for VoiceSessionManager lifecycle."""

import pytest

from callscreen.voice.session import VoiceSession, VoiceSessionManager


class TestVoiceSessionManager:
    def setup_method(self):
        self.mgr = VoiceSessionManager()

    @pytest.mark.unit
    def test_create_session(self):
        session = self.mgr.create_session("CA123")
        assert session.call_sid == "CA123"
        assert session.is_active is True
        assert session.stream_sid is None

    @pytest.mark.unit
    def test_get_session(self):
        self.mgr.create_session("CA123")
        session = self.mgr.get_session("CA123")
        assert session is not None
        assert session.call_sid == "CA123"

    @pytest.mark.unit
    def test_get_nonexistent_session_returns_none(self):
        assert self.mgr.get_session("CA_NONEXISTENT") is None

    @pytest.mark.unit
    def test_end_session(self):
        self.mgr.create_session("CA123")
        ended = self.mgr.end_session("CA123")
        assert ended is True
        assert self.mgr.get_session("CA123") is None

    @pytest.mark.unit
    def test_end_nonexistent_session_returns_false(self):
        assert self.mgr.end_session("CA_NONEXISTENT") is False

    @pytest.mark.unit
    def test_create_replaces_existing(self):
        s1 = self.mgr.create_session("CA123")
        s2 = self.mgr.create_session("CA123")
        assert s1 is not s2
        assert self.mgr.get_session("CA123") is s2

    @pytest.mark.unit
    def test_active_session_count(self):
        assert self.mgr.active_session_count() == 0
        self.mgr.create_session("CA1")
        self.mgr.create_session("CA2")
        assert self.mgr.active_session_count() == 2
        self.mgr.end_session("CA1")
        assert self.mgr.active_session_count() == 1

    @pytest.mark.unit
    def test_session_stores_transcript_parts(self):
        session = self.mgr.create_session("CA123")
        session.transcript_parts.append("hello")
        session.transcript_parts.append("world")
        retrieved = self.mgr.get_session("CA123")
        assert retrieved is not None
        assert retrieved.transcript_parts == ["hello", "world"]
