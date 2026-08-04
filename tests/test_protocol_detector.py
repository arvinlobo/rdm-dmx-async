"""Unit tests for `RdmProtocolDetector` (transport/protocol_detector.py)."""

from rdm_dmx_async.transport.protocol_detector import RdmProtocolDetector


def _packet_with_pid(pid: int, total_len: int = 24) -> bytes:
    """Build a minimal fake RDM packet with `pid` at the fixed PID offset."""
    data = bytearray(total_len)
    data[RdmProtocolDetector.PID_OFFSET] = (pid >> 8) & 0xFF
    data[RdmProtocolDetector.PID_OFFSET + 1] = pid & 0xFF
    return bytes(data)


class TestIsDiscoveryPacket:
    def test_disc_unique_branch_is_discovery(self):
        detector = RdmProtocolDetector()
        packet = _packet_with_pid(RdmProtocolDetector.DISC_UNIQUE_BRANCH_PID)

        assert detector.is_discovery_packet(packet) is True

    def test_disc_mute_is_discovery(self):
        detector = RdmProtocolDetector()
        packet = _packet_with_pid(RdmProtocolDetector.DISC_MUTE_PID)

        assert detector.is_discovery_packet(packet) is True

    def test_disc_un_mute_is_discovery(self):
        detector = RdmProtocolDetector()
        packet = _packet_with_pid(RdmProtocolDetector.DISC_UN_MUTE_PID)

        assert detector.is_discovery_packet(packet) is True

    def test_non_discovery_pid_returns_false(self):
        detector = RdmProtocolDetector()
        packet = _packet_with_pid(0x0060)  # DEVICE_INFO - a regular GET, not discovery

        assert detector.is_discovery_packet(packet) is False

    def test_packet_shorter_than_pid_offset_returns_false(self):
        detector = RdmProtocolDetector()
        packet = bytes(RdmProtocolDetector.PID_OFFSET)  # one byte short of the PID field

        assert detector.is_discovery_packet(packet) is False

    def test_empty_packet_returns_false(self):
        detector = RdmProtocolDetector()

        assert detector.is_discovery_packet(b"") is False

    def test_pid_read_at_exact_offset_not_off_by_one(self):
        """A PID value placed one byte before/after the real offset must not
        be misread as a discovery PID."""
        detector = RdmProtocolDetector()
        data = bytearray(24)
        # DISC_UNIQUE_BRANCH bytes shifted one position early - the real
        # PID_OFFSET bytes remain zero, which is not a discovery PID.
        data[RdmProtocolDetector.PID_OFFSET - 1] = 0x00
        data[RdmProtocolDetector.PID_OFFSET] = 0x00
        data[RdmProtocolDetector.PID_OFFSET + 1] = 0x00

        assert detector.is_discovery_packet(bytes(data)) is False
