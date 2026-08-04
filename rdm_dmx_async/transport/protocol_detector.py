"""Protocol detection for RDM packets."""

import logging


class RdmProtocolDetector:
    """Detects RDM packet types for protocol-specific handling."""

    DISC_UNIQUE_BRANCH_PID = 0x0001
    DISC_MUTE_PID = 0x0002
    DISC_UN_MUTE_PID = 0x0003
    PID_OFFSET = 21
    PID_SIZE = 2

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)

    def is_discovery_packet(self, data: bytes) -> bool:
        """
        Check if RDM packet is a discovery request.

        Args:
            data: Raw RDM packet bytes

        Returns:
            True if discovery packet (DISC_UNIQUE_BRANCH, DISC_MUTE, or DISC_UN_MUTE)
        """
        if len(data) < self.PID_OFFSET + self.PID_SIZE:
            self._logger.debug(f"[PID_CHECK] Packet too short: {len(data)} bytes")
            return False

        pid = (data[self.PID_OFFSET] << 8) | data[self.PID_OFFSET + 1]
        is_disc = pid in (
            self.DISC_UNIQUE_BRANCH_PID,
            self.DISC_MUTE_PID,
            self.DISC_UN_MUTE_PID,
        )
        self._logger.debug(f"[PID_CHECK] PID=0x{pid:04X}, is_discovery={is_disc}")
        return is_disc
