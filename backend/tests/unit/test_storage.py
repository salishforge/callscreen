"""Tests for S3 recording storage service."""

from unittest.mock import MagicMock, patch
from io import BytesIO

import pytest

from callscreen.core.storage import (
    upload_recording,
    download_recording,
    delete_recording,
    list_recordings,
    _ext_from_mime,
)


@pytest.fixture(autouse=True)
def reset_s3_client():
    """Reset the module-level S3 client singleton."""
    import callscreen.core.storage as mod
    mod._client = None
    yield
    mod._client = None


@pytest.fixture
def mock_s3():
    """Mock boto3 S3 client."""
    mock_client = MagicMock()
    mock_client.head_bucket.return_value = {}
    with patch("callscreen.core.storage._get_s3_client", return_value=mock_client):
        yield mock_client


class TestUploadRecording:
    def test_upload_returns_key(self, mock_s3):
        key = upload_recording("CA123abc", b"audio-data", encrypt=False)
        assert key.startswith("recordings/CA123abc/")
        assert key.endswith(".wav")
        mock_s3.put_object.assert_called_once()

    def test_upload_encrypted_uses_enc_extension(self, mock_s3):
        key = upload_recording("CA123abc", b"audio-data", encrypt=True)
        assert key.endswith(".enc")

    def test_upload_encrypted_sets_metadata(self, mock_s3):
        upload_recording("CA123abc", b"test-audio", encrypt=True)
        call_kwargs = mock_s3.put_object.call_args[1]
        assert call_kwargs["Metadata"]["encrypted"] == "true"
        assert "checksum-sha256-pre-encrypt" in call_kwargs["Metadata"]
        assert call_kwargs["ContentType"] == "application/octet-stream"

    def test_upload_unencrypted_preserves_content_type(self, mock_s3):
        upload_recording("CA123abc", b"test", content_type="audio/mpeg", encrypt=False)
        call_kwargs = mock_s3.put_object.call_args[1]
        assert call_kwargs["ContentType"] == "audio/mpeg"

    def test_upload_creates_bucket_if_missing(self, mock_s3):
        from botocore.exceptions import ClientError
        mock_s3.head_bucket.side_effect = ClientError(
            {"Error": {"Code": "404"}}, "HeadBucket"
        )
        upload_recording("CA456", b"data", encrypt=False)
        mock_s3.create_bucket.assert_called_once()


class TestDownloadRecording:
    def test_download_returns_data_and_type(self, mock_s3):
        mock_s3.get_object.return_value = {
            "Body": BytesIO(b"raw-audio"),
            "ContentType": "audio/wav",
            "Metadata": {"encrypted": "false", "original-content-type": "audio/wav"},
        }
        data, ct = download_recording("recordings/CA123/file.wav", decrypt=False)
        assert data == b"raw-audio"
        assert ct == "audio/wav"

    def test_download_encrypted_file_decrypts(self, mock_s3):
        from callscreen.db.encryption import encrypt_field
        original = "test-audio-content"
        encrypted = encrypt_field(original)
        mock_s3.get_object.return_value = {
            "Body": BytesIO(encrypted.encode("latin-1")),
            "ContentType": "application/octet-stream",
            "Metadata": {"encrypted": "true", "original-content-type": "audio/wav"},
        }
        data, ct = download_recording("recordings/CA123/file.enc", decrypt=True)
        assert data.decode("latin-1") == original
        assert ct == "audio/wav"


class TestDeleteRecording:
    def test_delete_returns_true_on_success(self, mock_s3):
        result = delete_recording("recordings/CA123/file.wav")
        assert result is True
        mock_s3.delete_object.assert_called_once()

    def test_delete_returns_false_on_error(self, mock_s3):
        from botocore.exceptions import ClientError
        mock_s3.delete_object.side_effect = ClientError(
            {"Error": {"Code": "500"}}, "DeleteObject"
        )
        result = delete_recording("recordings/CA123/file.wav")
        assert result is False


class TestListRecordings:
    def test_list_returns_keys(self, mock_s3):
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "recordings/CA123/a.wav"},
                {"Key": "recordings/CA123/b.wav"},
            ]
        }
        keys = list_recordings("CA123")
        assert len(keys) == 2
        assert "recordings/CA123/a.wav" in keys

    def test_list_returns_empty_for_no_results(self, mock_s3):
        mock_s3.list_objects_v2.return_value = {}
        keys = list_recordings("CA999")
        assert keys == []


class TestExtFromMime:
    def test_wav(self):
        assert _ext_from_mime("audio/wav") == "wav"

    def test_mp3(self):
        assert _ext_from_mime("audio/mpeg") == "mp3"

    def test_unknown_defaults_to_bin(self):
        assert _ext_from_mime("application/octet-stream") == "bin"
