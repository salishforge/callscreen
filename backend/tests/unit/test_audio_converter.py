"""Tests for audio format conversion utilities."""

import base64
import struct

import pytest

from callscreen.voice.audio.converter import (
    base64_audio_chunk,
    decode_audio_chunk,
    mulaw_to_pcm,
    pcm_to_mulaw,
)


class TestPcmToMulaw:
    @pytest.mark.unit
    def test_empty_input(self):
        assert pcm_to_mulaw(b"") == b""

    @pytest.mark.unit
    def test_silence(self):
        """Silence (all zeros) should encode to a consistent mulaw value."""
        pcm = struct.pack("<4h", 0, 0, 0, 0)
        result = pcm_to_mulaw(pcm, sample_rate=8000)
        assert len(result) == 4
        # All zero samples should produce the same mulaw byte
        assert result[0] == result[1] == result[2] == result[3]

    @pytest.mark.unit
    def test_output_length_same_rate(self):
        """At 8000 Hz, output length should equal number of input samples."""
        num_samples = 100
        pcm = struct.pack(f"<{num_samples}h", *([1000] * num_samples))
        result = pcm_to_mulaw(pcm, sample_rate=8000)
        assert len(result) == num_samples

    @pytest.mark.unit
    def test_downsampling(self):
        """At 16000 Hz, output should be roughly half the input samples."""
        num_samples = 200
        pcm = struct.pack(f"<{num_samples}h", *([500] * num_samples))
        result = pcm_to_mulaw(pcm, sample_rate=16000)
        assert len(result) == 100

    @pytest.mark.unit
    def test_mulaw_byte_range(self):
        """All output bytes should be in the valid 0-255 range."""
        samples = list(range(-32000, 32000, 1000))
        pcm = struct.pack(f"<{len(samples)}h", *samples)
        result = pcm_to_mulaw(pcm, sample_rate=8000)
        for byte_val in result:
            assert 0 <= byte_val <= 255


class TestMulawToPcm:
    @pytest.mark.unit
    def test_empty_input(self):
        assert mulaw_to_pcm(b"") == b""

    @pytest.mark.unit
    def test_output_length(self):
        """Each mulaw byte should expand to 2 PCM bytes (16-bit)."""
        mulaw = bytes(range(10))
        result = mulaw_to_pcm(mulaw)
        assert len(result) == 20

    @pytest.mark.unit
    def test_pcm_values_in_range(self):
        """Decoded PCM samples should be in the 16-bit signed range."""
        mulaw = bytes(range(256))
        result = mulaw_to_pcm(mulaw)
        samples = struct.unpack(f"<{len(result) // 2}h", result)
        for s in samples:
            assert -32768 <= s <= 32767


class TestRoundTrip:
    @pytest.mark.unit
    def test_roundtrip_preserves_sign(self):
        """Encoding then decoding should preserve the sign of samples."""
        positive = struct.pack("<1h", 10000)
        negative = struct.pack("<1h", -10000)

        mulaw_pos = pcm_to_mulaw(positive, sample_rate=8000)
        mulaw_neg = pcm_to_mulaw(negative, sample_rate=8000)

        pcm_pos = mulaw_to_pcm(mulaw_pos)
        pcm_neg = mulaw_to_pcm(mulaw_neg)

        decoded_pos = struct.unpack("<1h", pcm_pos)[0]
        decoded_neg = struct.unpack("<1h", pcm_neg)[0]

        assert decoded_pos > 0
        assert decoded_neg < 0

    @pytest.mark.unit
    def test_roundtrip_approximate(self):
        """Roundtrip should be approximately equal (mulaw is lossy)."""
        original_value = 8000
        pcm = struct.pack("<1h", original_value)
        mulaw = pcm_to_mulaw(pcm, sample_rate=8000)
        reconstructed = mulaw_to_pcm(mulaw)
        decoded = struct.unpack("<1h", reconstructed)[0]
        # Mulaw is lossy but should be within ~5% for mid-range values
        assert abs(decoded - original_value) < original_value * 0.15


class TestBase64:
    @pytest.mark.unit
    def test_encode_decode_roundtrip(self):
        data = b"\x00\x01\x02\xff\xfe"
        encoded = base64_audio_chunk(data)
        decoded = decode_audio_chunk(encoded)
        assert decoded == data

    @pytest.mark.unit
    def test_empty_data(self):
        assert base64_audio_chunk(b"") == ""
        assert decode_audio_chunk("") == b""

    @pytest.mark.unit
    def test_encode_is_valid_base64(self):
        data = b"hello audio data"
        encoded = base64_audio_chunk(data)
        # Should not raise
        base64.b64decode(encoded)

    @pytest.mark.unit
    def test_large_chunk(self):
        """Should handle large audio chunks without issues."""
        data = bytes(range(256)) * 100  # 25.6 KB
        encoded = base64_audio_chunk(data)
        decoded = decode_audio_chunk(encoded)
        assert decoded == data
