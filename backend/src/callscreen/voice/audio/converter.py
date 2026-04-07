"""Audio format conversion utilities.

Implements ITU-T G.711 mu-law codec for Twilio compatibility.
Does NOT use the audioop module (removed in Python 3.13).

The encode/decode tables are built once at import time using the standard
G.711 mu-law algorithm so that encode -> decode roundtrips are consistent.
"""

import base64
import struct

# ---------------------------------------------------------------------------
# ITU-T G.711 mu-law constants
# ---------------------------------------------------------------------------

_MULAW_BIAS = 0x84  # 132
_MULAW_CLIP = 32635  # 0x7F7B — max magnitude before bias overflow


# ---------------------------------------------------------------------------
# Build encode table: signed 16-bit PCM -> 8-bit mu-law
# ---------------------------------------------------------------------------

def _encode_one(pcm_sample: int) -> int:
    """Encode a single signed 16-bit PCM sample to a mu-law byte.

    Uses the standard ITU-T G.711 algorithm: bias, then find the segment
    by iteratively shifting the biased value right until it fits in one bit.
    """
    # Determine sign bit
    if pcm_sample < 0:
        sign = 0x80
        pcm_sample = -pcm_sample
    else:
        sign = 0

    # Clip
    if pcm_sample > _MULAW_CLIP:
        pcm_sample = _MULAW_CLIP

    # Add bias
    pcm_sample += _MULAW_BIAS

    # Find segment (exponent) by counting how many shifts biased >> 7 needs
    exponent = 0
    shifted = pcm_sample >> 7
    while shifted > 1 and exponent < 7:
        shifted >>= 1
        exponent += 1

    # Extract mantissa (top 4 bits within the segment)
    mantissa = (pcm_sample >> (exponent + 3)) & 0x0F

    # Compose byte, then invert all bits
    mulaw_byte = ~(sign | (exponent << 4) | mantissa) & 0xFF
    return mulaw_byte


def _build_encode_table() -> bytes:
    """Pre-compute encode for every possible signed 16-bit value.

    Index by (sample + 32768) so that -32768 maps to index 0.
    """
    table = bytearray(65536)
    for i in range(65536):
        sample = i - 32768  # convert unsigned index to signed
        table[i] = _encode_one(sample)
    return bytes(table)


_ENCODE_TABLE: bytes = _build_encode_table()


# ---------------------------------------------------------------------------
# Build decode table: 8-bit mu-law -> signed 16-bit PCM
# ---------------------------------------------------------------------------

def _build_decode_table() -> tuple[int, ...]:
    """Pre-compute decode for every mu-law byte (0-255)."""
    table: list[int] = []
    for mu_byte in range(256):
        # Complement
        val = ~mu_byte & 0xFF
        sign = val & 0x80
        exponent = (val >> 4) & 0x07
        mantissa = val & 0x0F

        # Reconstruct magnitude: place mantissa bits and add half-step
        sample = ((2 * mantissa + 33) << (exponent + 2)) - _MULAW_BIAS

        if sign:
            sample = -sample

        # Clamp
        sample = max(-32768, min(32767, sample))
        table.append(sample)
    return tuple(table)


_DECODE_TABLE: tuple[int, ...] = _build_decode_table()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def pcm_to_mulaw(pcm_data: bytes, sample_rate: int = 16000) -> bytes:
    """Convert 16-bit signed little-endian PCM audio to mu-law encoded bytes.

    If the input sample_rate is not 8000 Hz, simple decimation is applied
    to downsample to 8000 Hz (Twilio's expected rate).

    Args:
        pcm_data: Raw PCM bytes (16-bit signed LE, mono).
        sample_rate: Sample rate of the input PCM data.

    Returns:
        Mu-law encoded bytes at 8000 Hz.
    """
    if not pcm_data:
        return b""

    # Parse 16-bit LE samples
    num_samples = len(pcm_data) // 2
    samples = struct.unpack(f"<{num_samples}h", pcm_data[: num_samples * 2])

    # Downsample via decimation when needed
    if sample_rate != 8000 and sample_rate > 0:
        ratio = sample_rate / 8000
        samples = tuple(
            samples[int(i * ratio)]
            for i in range(int(num_samples / ratio))
            if int(i * ratio) < num_samples
        )

    # Look up each sample in the pre-built table
    result = bytearray(len(samples))
    for i, s in enumerate(samples):
        result[i] = _ENCODE_TABLE[s + 32768]

    return bytes(result)


def mulaw_to_pcm(mulaw_data: bytes) -> bytes:
    """Convert mu-law encoded bytes to 16-bit signed little-endian PCM at 8000 Hz.

    Args:
        mulaw_data: Mu-law encoded audio bytes.

    Returns:
        Raw PCM bytes (16-bit signed LE, mono, 8000 Hz).
    """
    if not mulaw_data:
        return b""

    num_samples = len(mulaw_data)
    result = bytearray(num_samples * 2)

    for i in range(num_samples):
        sample = _DECODE_TABLE[mulaw_data[i]]
        struct.pack_into("<h", result, i * 2, sample)

    return bytes(result)


def base64_audio_chunk(data: bytes) -> str:
    """Base64-encode an audio chunk for WebSocket transmission.

    Args:
        data: Raw audio bytes.

    Returns:
        Base64-encoded string.
    """
    return base64.b64encode(data).decode("ascii")


def decode_audio_chunk(b64_data: str) -> bytes:
    """Decode a base64-encoded audio chunk from a WebSocket frame.

    Args:
        b64_data: Base64-encoded string.

    Returns:
        Raw audio bytes.
    """
    return base64.b64decode(b64_data)
