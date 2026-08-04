"""Manchester encoding/decoding for RDM DISC_UNIQUE_BRANCH discovery responses.

Per ANSI E1.20, DISC_UNIQUE_BRANCH responses are Manchester-encoded rather than
framed as standard RDM packets, so they require dedicated decoding logic
distinct from the normal RDM packet decoder.
"""

import logging

logger = logging.getLogger(__name__)

# Per ANSI E1.20, a responder may send 0-7 bytes of 0xFE preamble before the
# 0xAA start byte - purpose-built widgets (Enttec) normalize this to a fixed
# 7-byte preamble, but a raw wire capture (e.g. a bare manual-break interface)
# may see fewer.
_MAX_PREAMBLE_BYTES = 7
_MANCHESTER_DATA_LEN = 16  # 6 UID bytes + 2 checksum bytes, each Manchester-doubled


def find_discovery_frame_length(buffer: bytes) -> int:
    """
    Determine the total length of a DISC_UNIQUE_BRANCH response at the front
    of `buffer` (0-7 bytes of 0xFE preamble + 0xAA + 16 Manchester bytes).

    Returns:
        Total frame length, or 0 if `buffer` doesn't start with a discovery
        response or the frame hasn't fully arrived yet.
    """
    preamble_len = 0
    while (
        preamble_len < len(buffer)
        and preamble_len < _MAX_PREAMBLE_BYTES
        and buffer[preamble_len] == 0xFE
    ):
        preamble_len += 1

    if preamble_len == 0:
        return 0

    aa_index = preamble_len
    if aa_index >= len(buffer):
        return 0  # preamble seen, but 0xAA hasn't arrived yet
    if buffer[aa_index] != 0xAA:
        return 0

    total = aa_index + 1 + _MANCHESTER_DATA_LEN
    return total if len(buffer) >= total else 0


class ManchesterDiscoveryDecoder:
    """Decodes Manchester-encoded DISC_UNIQUE_BRANCH discovery responses."""

    def decode(self, data: bytes) -> bytes | None:
        """
        Decode Manchester-encoded discovery response to extract UID.

        Format: 0-7 bytes of 0xFE (preamble) + 0xAA + Manchester(UID + Checksum)
        Manchester encoding: each data byte is encoded as two bytes where
        bitwise AND of the pair recovers the original byte.

        Args:
            data: Raw Manchester-encoded bytes from device (one complete frame)

        Returns:
            6-byte UID if valid, None if collision or invalid
        """
        logger.info(
            "[MANCHESTER] Decoding %d bytes: %s", len(data), " ".join(f"{b:02X}" for b in data)
        )

        frame_len = find_discovery_frame_length(data)
        if frame_len == 0 or frame_len != len(data):
            logger.info(
                "[MANCHESTER] Invalid/incomplete frame: %d bytes (parsed length %d)",
                len(data),
                frame_len,
            )
            return None

        preamble_len = frame_len - 1 - _MANCHESTER_DATA_LEN

        # Manchester data starts right after the 0xAA start byte
        manchester_data = data[preamble_len + 1 :]
        logger.info(
            "[MANCHESTER] Manchester data: %s", " ".join(f"{b:02X}" for b in manchester_data)
        )

        if len(manchester_data) < 16:
            logger.info("[MANCHESTER] Insufficient Manchester data: %d bytes", len(manchester_data))
            return None

        # Decode 6 UID bytes (12 Manchester bytes) + 2 checksum bytes (4 Manchester bytes)
        decoded = []
        for i in range(0, 16, 2):
            decoded_byte = manchester_data[i] & manchester_data[i + 1]
            decoded.append(decoded_byte)

        logger.info(
            "[MANCHESTER] Decoded %d bytes: %s", len(decoded), " ".join(f"{b:02X}" for b in decoded)
        )

        if len(decoded) < 6:
            logger.info("[MANCHESTER] Insufficient decoded data")
            return None

        # First 6 bytes are UID
        uid = bytes(decoded[0:6])
        logger.info("[MANCHESTER] Successfully decoded UID: %s", uid.hex().upper())

        # TODO: Validate checksum (decoded[6:8]) if needed

        return uid
