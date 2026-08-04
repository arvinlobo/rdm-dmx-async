"""Manchester encoding/decoding for RDM DISC_UNIQUE_BRANCH discovery responses.

Per ANSI E1.20, DISC_UNIQUE_BRANCH responses are Manchester-encoded rather than
framed as standard RDM packets, so they require dedicated decoding logic
distinct from the normal RDM packet decoder.
"""

import logging

logger = logging.getLogger(__name__)


class ManchesterDiscoveryDecoder:
    """Decodes Manchester-encoded DISC_UNIQUE_BRANCH discovery responses."""

    def decode(self, data: bytes) -> bytes | None:
        """
        Decode Manchester-encoded discovery response to extract UID.

        Format: 7*0xFE (preamble) + Manchester(UID + UID + Checksum)
        Manchester encoding: each data byte is encoded as two bytes where
        bitwise AND of the pair recovers the original byte.

        Args:
            data: Raw Manchester-encoded bytes from device (24 bytes total)

        Returns:
            6-byte UID if valid, None if collision or invalid
        """
        logger.info(
            "[MANCHESTER] Decoding %d bytes: %s", len(data), " ".join(f"{b:02X}" for b in data)
        )

        # Verify preamble: 7x 0xFE followed by 0xAA
        if len(data) != 24:
            logger.info("[MANCHESTER] Invalid length: %d bytes (expected 24)", len(data))
            return None

        if data[0:7] != b"\xfe" * 7:
            logger.info("[MANCHESTER] Invalid preamble")
            return None

        if data[7] != 0xAA:
            logger.info("[MANCHESTER] Invalid start byte: 0x%02X (expected 0xAA)", data[7])
            return None

        # Manchester data starts at byte 8, continues for 16 bytes
        # Decode by AND'ing each pair of bytes
        manchester_data = data[8:]
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
