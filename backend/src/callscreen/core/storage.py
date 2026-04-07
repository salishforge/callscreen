"""S3-compatible object storage for recordings and audio files.

Uses MinIO in self-hosted deployments, or any S3-compatible provider.
All recordings are encrypted before upload using AES-256-GCM.
"""

import hashlib
import logging
from datetime import datetime, timezone
from io import BytesIO

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from callscreen.config import get_settings
from callscreen.db.encryption import encrypt_field, decrypt_field

logger = logging.getLogger(__name__)

_client = None


def _get_s3_client():
    """Lazy-initialize the S3 client."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            config=BotoConfig(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )
    return _client


def _ensure_bucket(bucket: str) -> None:
    """Create bucket if it doesn't exist."""
    client = _get_s3_client()
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError:
        try:
            client.create_bucket(Bucket=bucket)
            logger.info("Created S3 bucket: %s", bucket)
        except ClientError as e:
            logger.error("Failed to create bucket %s: %s", bucket, e)
            raise


def upload_recording(
    call_sid: str,
    audio_data: bytes,
    content_type: str = "audio/wav",
    encrypt: bool = True,
) -> str:
    """Upload an audio recording to S3.

    Args:
        call_sid: Twilio call SID (used as key prefix)
        audio_data: Raw audio bytes
        content_type: MIME type of the audio
        encrypt: Whether to encrypt before upload (default True)

    Returns:
        S3 object reference key (e.g., "recordings/CA123.../2026-04-07T00:00:00Z.enc")
    """
    settings = get_settings()
    bucket = settings.s3_bucket_recordings
    _ensure_bucket(bucket)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ext = "enc" if encrypt else _ext_from_mime(content_type)
    key = f"recordings/{call_sid}/{timestamp}.{ext}"

    data_to_upload = audio_data
    metadata = {
        "call-sid": call_sid,
        "original-content-type": content_type,
        "uploaded-at": timestamp,
        "encrypted": str(encrypt).lower(),
    }

    if encrypt:
        # Encrypt the audio data using AES-256-GCM
        data_to_upload = encrypt_field(audio_data.decode("latin-1")).encode("latin-1")
        metadata["checksum-sha256-pre-encrypt"] = hashlib.sha256(audio_data).hexdigest()
        content_type = "application/octet-stream"

    client = _get_s3_client()
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=BytesIO(data_to_upload),
        ContentType=content_type,
        Metadata=metadata,
    )

    logger.info("Uploaded recording: bucket=%s key=%s size=%d encrypted=%s",
                bucket, key, len(audio_data), encrypt)
    return key


def download_recording(key: str, decrypt: bool = True) -> tuple[bytes, str]:
    """Download a recording from S3.

    Args:
        key: S3 object key
        decrypt: Whether to decrypt after download

    Returns:
        Tuple of (audio_bytes, content_type)
    """
    settings = get_settings()
    bucket = settings.s3_bucket_recordings
    client = _get_s3_client()

    response = client.get_object(Bucket=bucket, Key=key)
    data = response["Body"].read()
    metadata = response.get("Metadata", {})
    is_encrypted = metadata.get("encrypted", "false") == "true"
    original_content_type = metadata.get("original-content-type", "audio/wav")

    if decrypt and is_encrypted:
        decrypted_str = decrypt_field(data.decode("latin-1"))
        data = decrypted_str.encode("latin-1")

    content_type = original_content_type if decrypt else response["ContentType"]
    logger.info("Downloaded recording: key=%s size=%d", key, len(data))
    return data, content_type


def delete_recording(key: str) -> bool:
    """Delete a recording from S3.

    Returns True if deleted successfully.
    """
    settings = get_settings()
    bucket = settings.s3_bucket_recordings
    client = _get_s3_client()

    try:
        client.delete_object(Bucket=bucket, Key=key)
        logger.info("Deleted recording: key=%s", key)
        return True
    except ClientError as e:
        logger.error("Failed to delete %s: %s", key, e)
        return False


def list_recordings(call_sid: str) -> list[str]:
    """List all recordings for a given call SID."""
    settings = get_settings()
    bucket = settings.s3_bucket_recordings
    client = _get_s3_client()

    prefix = f"recordings/{call_sid}/"
    try:
        response = client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        return [obj["Key"] for obj in response.get("Contents", [])]
    except ClientError as e:
        logger.error("Failed to list recordings for %s: %s", call_sid, e)
        return []


def generate_presigned_url(key: str, expires_in: int = 3600) -> str:
    """Generate a presigned URL for temporary audio access.

    Args:
        key: S3 object key
        expires_in: URL expiry in seconds (default 1 hour)

    Returns:
        Presigned URL string
    """
    settings = get_settings()
    bucket = settings.s3_bucket_recordings
    client = _get_s3_client()

    url = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )
    return url


def _ext_from_mime(content_type: str) -> str:
    """Map MIME type to file extension."""
    mapping = {
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/ogg": "ogg",
        "audio/webm": "webm",
        "audio/x-mulaw": "ulaw",
    }
    return mapping.get(content_type, "bin")
