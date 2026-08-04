"""
Unit tests for ManchesterDiscoveryDecoder (RDM DISC_UNIQUE_BRANCH decoding).
"""

from rdm_dmx_async.protocols.manchester_codec import ManchesterDiscoveryDecoder


def _build_discovery_frame(uid: bytes, checksum: bytes = b"\x00\x00") -> bytes:
    """
    Build a well-formed Manchester discovery frame for the given UID.

    Each payload byte is Manchester-encoded as a pair whose bitwise AND
    recovers the original byte (matches ManchesterDiscoveryDecoder.decode()).
    """
    manchester_bytes = bytearray()
    for byte in uid + checksum:
        manchester_bytes.extend([0xFF, byte])
    return b"\xfe" * 7 + b"\xaa" + bytes(manchester_bytes)


class TestManchesterDiscoveryDecoder:
    def test_decode_valid_uid(self):
        decoder = ManchesterDiscoveryDecoder()
        uid = bytes.fromhex("123456789ABC")

        frame = _build_discovery_frame(uid)

        assert decoder.decode(frame) == uid

    def test_decode_wrong_length_returns_none(self):
        decoder = ManchesterDiscoveryDecoder()

        assert decoder.decode(b"\xfe" * 10) is None

    def test_decode_invalid_preamble_returns_none(self):
        decoder = ManchesterDiscoveryDecoder()
        frame = bytearray(_build_discovery_frame(bytes.fromhex("AABBCCDDEEFF")))
        frame[3] = 0x00  # Corrupt preamble byte

        assert decoder.decode(bytes(frame)) is None

    def test_decode_invalid_start_byte_returns_none(self):
        decoder = ManchesterDiscoveryDecoder()
        frame = bytearray(_build_discovery_frame(bytes.fromhex("AABBCCDDEEFF")))
        frame[7] = 0x55  # Should be 0xAA

        assert decoder.decode(bytes(frame)) is None

    def test_decode_collision_and_pattern(self):
        """A collision typically ANDs to a different byte than any real UID bit."""
        decoder = ManchesterDiscoveryDecoder()
        # Mismatched Manchester pair (0x0F & 0xF0 = 0x00) still decodes to a
        # concrete (if garbage) byte - the decoder has no checksum validation,
        # so it returns whatever the AND produces rather than detecting collision.
        manchester_bytes = bytes([0x0F, 0xF0] * 8)
        frame = b"\xfe" * 7 + b"\xaa" + manchester_bytes

        result = decoder.decode(frame)

        assert result == bytes([0x00] * 6)
