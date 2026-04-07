"""Tests for the recording processing flow."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from callscreen.core.recording import process_twilio_recording


def _fake_call_record(call_sid: str = "CA_rec_test"):
    """Create a fake CallRecord-like object."""
    record = MagicMock()
    record.call_sid = call_sid
    record.recording_ref = None
    record.transcript = None
    record.ai_summary = None
    return record


class TestProcessTwilioRecording:
    """Tests for the main recording processing pipeline."""

    @pytest.mark.asyncio
    async def test_downloads_encrypts_and_uploads(self):
        """Happy path: download from Twilio, upload to S3, return key."""
        mock_response = MagicMock()
        mock_response.content = b"fake-audio-data"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = _fake_call_record("CA_rec_001")
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        with (
            patch("callscreen.core.recording.httpx.AsyncClient", return_value=mock_client),
            patch(
                "callscreen.core.recording.upload_recording",
                return_value="recordings/CA_rec_001/20260407T000000Z.enc",
            ) as mock_upload,
            patch(
                "callscreen.core.recording._transcribe_and_summarize",
                new_callable=AsyncMock,
            ),
        ):
            key = await process_twilio_recording(
                call_sid="CA_rec_001",
                recording_url="https://api.twilio.com/recordings/RE123",
                recording_sid="RE123",
                db=mock_db,
            )

        assert key == "recordings/CA_rec_001/20260407T000000Z.enc"
        mock_upload.assert_called_once_with(
            call_sid="CA_rec_001",
            audio_data=b"fake-audio-data",
            content_type="audio/wav",
            encrypt=True,
        )

    @pytest.mark.asyncio
    async def test_updates_call_record_in_database(self):
        """The CallRecord.recording_ref should be updated after upload."""
        mock_response = MagicMock()
        mock_response.content = b"audio"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        call_record = _fake_call_record("CA_rec_002")
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = call_record
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        with (
            patch("callscreen.core.recording.httpx.AsyncClient", return_value=mock_client),
            patch(
                "callscreen.core.recording.upload_recording",
                return_value="recordings/CA_rec_002/file.enc",
            ),
            patch(
                "callscreen.core.recording._transcribe_and_summarize",
                new_callable=AsyncMock,
            ),
        ):
            await process_twilio_recording(
                call_sid="CA_rec_002",
                recording_url="https://api.twilio.com/recordings/RE456",
                recording_sid="RE456",
                db=mock_db,
            )

        assert call_record.recording_ref == "recordings/CA_rec_002/file.enc"
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_raises_on_download_failure(self):
        """HTTP errors from Twilio should propagate as exceptions."""
        error_response = MagicMock()
        error_response.status_code = 404
        error_response.request = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=MagicMock())
        mock_client.get.return_value.raise_for_status.side_effect = (
            httpx.HTTPStatusError("Not found", request=MagicMock(), response=error_response)
        )
        mock_client.get.return_value.content = b""
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_db = AsyncMock()

        with (
            patch("callscreen.core.recording.httpx.AsyncClient", return_value=mock_client),
            pytest.raises(httpx.HTTPStatusError),
        ):
            await process_twilio_recording(
                call_sid="CA_rec_003",
                recording_url="https://api.twilio.com/recordings/RE_bad",
                recording_sid="RE_bad",
                db=mock_db,
            )

    @pytest.mark.asyncio
    async def test_raises_on_upload_failure(self):
        """S3 upload errors should propagate."""
        mock_response = MagicMock()
        mock_response.content = b"audio"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_db = AsyncMock()

        with (
            patch("callscreen.core.recording.httpx.AsyncClient", return_value=mock_client),
            patch(
                "callscreen.core.recording.upload_recording",
                side_effect=Exception("S3 is down"),
            ),
            pytest.raises(Exception, match="S3 is down"),
        ):
            await process_twilio_recording(
                call_sid="CA_rec_004",
                recording_url="https://api.twilio.com/recordings/RE789",
                recording_sid="RE789",
                db=mock_db,
            )

    @pytest.mark.asyncio
    async def test_db_failure_does_not_lose_recording(self):
        """DB update failure should not re-raise (recording is safe in S3)."""
        mock_response = MagicMock()
        mock_response.content = b"audio"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=Exception("DB connection lost"))

        with (
            patch("callscreen.core.recording.httpx.AsyncClient", return_value=mock_client),
            patch(
                "callscreen.core.recording.upload_recording",
                return_value="recordings/CA_rec_005/file.enc",
            ),
            patch(
                "callscreen.core.recording._transcribe_and_summarize",
                new_callable=AsyncMock,
            ),
        ):
            # Should NOT raise despite DB failure
            key = await process_twilio_recording(
                call_sid="CA_rec_005",
                recording_url="https://api.twilio.com/recordings/RE_db_fail",
                recording_sid="RE_db_fail",
                db=mock_db,
            )

        assert key == "recordings/CA_rec_005/file.enc"

    @pytest.mark.asyncio
    async def test_appends_wav_extension_to_download_url(self):
        """The download URL should have .wav appended."""
        mock_response = MagicMock()
        mock_response.content = b"audio"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with (
            patch("callscreen.core.recording.httpx.AsyncClient", return_value=mock_client),
            patch(
                "callscreen.core.recording.upload_recording",
                return_value="recordings/CA_rec_006/file.enc",
            ),
            patch(
                "callscreen.core.recording._transcribe_and_summarize",
                new_callable=AsyncMock,
            ),
        ):
            await process_twilio_recording(
                call_sid="CA_rec_006",
                recording_url="https://api.twilio.com/recordings/RE_wav",
                recording_sid="RE_wav",
                db=mock_db,
            )

        # Verify the .wav extension was appended
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "https://api.twilio.com/recordings/RE_wav.wav"
