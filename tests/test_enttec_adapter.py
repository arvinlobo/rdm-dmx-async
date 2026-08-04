"""
End-to-End Integration Tests for Enttec Adapter (rdm_dmx_async Refactored Code)

This module provides comprehensive integration tests for the refactored
rdm_dmx_async Enttec adapter implementation. Tests cover:
- Enttec packet framing (DMX and RDM)
- Packet parsing and validation
- Frame length detection
- Serial configuration
- Edge cases and error handling

Tests the new adapter pattern architecture in rdm_dmx_async.
"""

import pytest

from rdm_dmx_async.domain.parameters import StandardPID
from rdm_dmx_async.packets.encoder import PacketEncoder
from rdm_dmx_async.packets.rdm import RDMRequest
from rdm_dmx_async.packets.types import UID, CommandClass, TransactionNumber
from rdm_dmx_async.transport.adapters import EnttecAdapter, EnttecMessageType
from rdm_dmx_async.transport.interface_adapter import InterfaceType, SerialConfig

# ==================== Helper Functions ====================


def parse_enttec_frame(data: bytes) -> tuple[int, bytes]:
    """
    Parse an Enttec frame and extract label and data.

    Returns:
        Tuple of (label, data)
    """
    if len(data) < 5:
        return (0, b"")

    if data[0] != 0x7E or data[-1] != 0xE7:
        return (0, b"")

    label = data[1]
    data_len = data[2] | (data[3] << 8)
    frame_data = data[4 : 4 + data_len]

    return (label, frame_data)


# ==================== Enttec Adapter Tests ====================


class TestEnttecAdapterFraming:
    """Test Enttec adapter packet framing."""

    def test_adapter_initialization(self):
        """Test creating an Enttec adapter."""
        adapter = EnttecAdapter("COM1", use_mk2_protocol=False)

        assert adapter.interface_type == InterfaceType.ENTTEC_USB_PRO
        assert adapter.serial_config.port == "COM1"
        assert adapter.serial_config.baudrate == 250000  # DMX512-A standard
        assert adapter.serial_config.stopbits == 2  # Enttec uses 2 stop bits

    def test_frame_dmx_output(self):
        """Test framing DMX output data."""
        adapter = EnttecAdapter("COM1")
        dmx_data = bytes([0xFF, 0x7F, 0x00, 0x80, 0x40])

        framed = adapter.frame_dmx_output(dmx_data, port=1)

        # Parse frame
        label, data = parse_enttec_frame(framed)

        assert label == EnttecMessageType.OUTPUT_ONLY_SEND_DMX
        # Data includes start code (0x00) prepended to dmx_data
        assert data == bytes([0x00]) + dmx_data
        assert framed[0] == 0x7E  # START
        assert framed[-1] == 0xE7  # END

    def test_frame_rdm_request(self):
        """Test framing RDM request data."""
        adapter = EnttecAdapter("COM1")

        # Create a sample RDM packet
        rdm_data = bytes(
            [
                0xCC,
                0x01,  # Start codes
                0x18,  # Message length
                0xFF,
                0xFF,
                0xFF,
                0xFF,
                0xFF,
                0xFF,  # Dest UID (broadcast)
                0x12,
                0x34,
                0x00,
                0x00,
                0x00,
                0x01,  # Source UID
                0x00,  # Transaction number
                0x00,  # Port ID
                0x00,  # Message count
                0x00,
                0x00,  # Sub-device
                0x20,  # Command class (GET)
                0x00,
                0xE0,  # PID (IDENTIFY_DEVICE)
                0x00,  # PDL
                0x00,
                0x00,  # Checksum placeholder
            ]
        )

        framed = adapter.frame_rdm_request(rdm_data, port=1)

        # Parse frame
        label, data = parse_enttec_frame(framed)

        assert label == EnttecMessageType.SEND_RDM_PACKET
        assert data == rdm_data

    def test_frame_rdm_discovery_request(self):
        """Test framing RDM discovery request."""
        adapter = EnttecAdapter("COM1")

        # Create a sample RDM discovery packet
        discovery_data = bytes([0xCC, 0x01] + [0x00] * 22)

        framed = adapter.frame_rdm_discovery_request(discovery_data, port=1)

        # Parse frame
        label, data = parse_enttec_frame(framed)

        assert label == EnttecMessageType.SEND_RDM_DISCOVERY
        assert data == discovery_data

    def test_find_frame_length_complete_frame(self):
        """Test finding frame length for complete Enttec frame."""
        adapter = EnttecAdapter("COM1")

        # Build a complete frame
        dmx_data = bytes([0xFF, 0x7F, 0x00])
        framed = adapter.frame_dmx_output(dmx_data)

        length = adapter.find_frame_length(framed)

        assert length == len(framed)
        # Header(5) + start code(1) + dmx_data(3) + END(1)
        assert length == 5 + len(dmx_data) + 1

    def test_find_frame_length_incomplete_frame(self):
        """Test finding frame length for incomplete frame."""
        adapter = EnttecAdapter("COM1")

        # Incomplete frame (just header)
        incomplete = bytes([0x7E, 0x06, 0x03, 0x00])

        length = adapter.find_frame_length(incomplete)

        # Should return 0 because frame is incomplete
        assert length == 0

    def test_find_frame_length_invalid_start(self):
        """Test finding frame length with invalid start byte."""
        adapter = EnttecAdapter("COM1")

        invalid = bytes([0xFF, 0x06, 0x03, 0x00, 0xFF, 0x7F, 0x00, 0xE7])

        length = adapter.find_frame_length(invalid)

        assert length == 0


class TestEnttecAdapterParsing:
    """Test Enttec adapter response parsing."""

    def test_parse_rdm_response_valid(self):
        """Test parsing valid RDM response."""
        adapter = EnttecAdapter("COM1", use_mk2_protocol=False)

        # Build RDM response frame
        rdm_response = bytes(
            [
                0xCC,
                0x01,  # Start codes
                0x18,  # Message length
                0x12,
                0x34,
                0x00,
                0x00,
                0x00,
                0x01,  # Source UID
                0xFF,
                0xFF,
                0xFF,
                0xFF,
                0xFF,
                0xFF,  # Dest UID
                0x00,  # Transaction number
                0x00,  # Response type
                0x00,  # Message count
                0x00,
                0x00,  # Sub-device
                0x21,  # Command class (GET_RESPONSE)
                0x00,
                0xE0,  # PID
                0x00,  # PDL
                0x00,
                0x00,  # Checksum
            ]
        )

        # Frame it (original USB Pro format: status + RDM data)
        status = 0x00  # No error
        frame_data = bytes([status]) + rdm_response
        framed = (
            bytes([0x7E, EnttecMessageType.RECEIVED_DMX_PACKET])
            + bytes([len(frame_data) & 0xFF, (len(frame_data) >> 8) & 0xFF])
            + frame_data
            + bytes([0xE7])
        )

        parsed = adapter.parse_rdm_response(framed)

        assert parsed is not None
        assert parsed == rdm_response

    def test_parse_rdm_response_invalid_frame(self):
        """Test parsing invalid frame returns None."""
        adapter = EnttecAdapter("COM1")

        invalid = bytes([0xFF, 0x00, 0x00, 0x00])

        parsed = adapter.parse_rdm_response(invalid)

        assert parsed is None

    def test_parse_rdm_response_wrong_label(self):
        """Test parsing frame with wrong label returns None."""
        adapter = EnttecAdapter("COM1")

        # Frame with GET_WIDGET_PARAMS label instead of RECEIVED_DMX_PACKET
        wrong_label = bytes(
            [0x7E, EnttecMessageType.GET_WIDGET_PARAMS, 0x02, 0x00, 0x00, 0x00, 0xE7]
        )

        parsed = adapter.parse_rdm_response(wrong_label)

        assert parsed is None


class TestEnttecPacketSizes:
    """Test various packet sizes and edge cases."""

    def test_minimum_dmx_data(self):
        """Test framing minimum DMX data (1 byte)."""
        adapter = EnttecAdapter("COM1")

        framed = adapter.frame_dmx_output(bytes([0xFF]))

        label, data = parse_enttec_frame(framed)
        assert label == EnttecMessageType.OUTPUT_ONLY_SEND_DMX
        # Data includes start code (0x00) + 1 byte
        assert data == bytes([0x00, 0xFF])

    def test_maximum_dmx_packet(self):
        """Test framing maximum size DMX packet (512 channels)."""
        adapter = EnttecAdapter("COM1")

        dmx_data = bytes(range(256)) + bytes(range(256))  # 512 bytes

        framed = adapter.frame_dmx_output(dmx_data)

        label, data = parse_enttec_frame(framed)
        assert label == EnttecMessageType.OUTPUT_ONLY_SEND_DMX
        # Data includes start code (0x00) + 512 bytes
        assert data == bytes([0x00]) + dmx_data
        assert len(data) == 513

    def test_packet_with_special_bytes(self):
        """Test DMX data containing START/END bytes."""
        adapter = EnttecAdapter("COM1")

        # DMX data that includes bytes matching START and END markers
        dmx_data = bytes([0x7E, 0xE7, 0xFF, 0x00, 0x7E, 0xE7])

        framed = adapter.frame_dmx_output(dmx_data)

        # Parse and verify data is preserved
        label, data = parse_enttec_frame(framed)
        # Data includes start code (0x00) + dmx_data
        assert data == bytes([0x00]) + dmx_data


class TestEnttecMk2Differences:
    """Test USB Pro Mk2 specific behavior."""

    def test_mk2_adapter_initialization(self):
        """Test creating Mk2 adapter."""
        adapter = EnttecAdapter("COM1", use_mk2_protocol=True)

        assert adapter.interface_type == InterfaceType.ENTTEC_USB_PRO_MK2

    def test_mk2_uses_same_dmx_framing(self):
        """Test that Mk2 uses same DMX framing as original USB Pro."""
        adapter = EnttecAdapter("COM1", use_mk2_protocol=True)

        dmx_data = bytes([0xFF, 0x00, 0x00])

        # Frame for port 1
        framed = adapter.frame_dmx_output(dmx_data, port=1)

        label, data = parse_enttec_frame(framed)

        # Mk2 uses same format: start code + DMX data (no port byte for type 6)
        assert label == EnttecMessageType.OUTPUT_ONLY_SEND_DMX
        assert data == bytes([0x00]) + dmx_data


class TestSerialConfiguration:
    """Test serial port configuration."""

    def test_enttec_serial_config(self):
        """Test Enttec serial configuration."""
        adapter = EnttecAdapter("COM3")
        config = adapter.serial_config

        assert config.port == "COM3"
        assert config.baudrate == 250000  # DMX512-A standard
        assert config.stopbits == 2  # Enttec uses 2 stop bits
        assert config.timeout > 0

    def test_custom_serial_config(self):
        """Test creating custom serial config."""
        config = SerialConfig(port="/dev/ttyUSB0", baudrate=115200, timeout=0.5)

        assert config.port == "/dev/ttyUSB0"
        assert config.baudrate == 115200
        assert config.timeout == 0.5


class TestRDMPacketEncoding:
    """Test RDM packet encoding for use with Enttec adapter."""

    def test_encode_simple_rdm_request(self):
        """Test encoding a simple RDM GET request."""
        encoder = PacketEncoder()

        request = RDMRequest(
            destination_uid=UID(0xFFFFFFFFFFFF),  # Broadcast
            source_uid=UID(0x123400000001),
            transaction_number=TransactionNumber(1),
            port_address=1,
            sub_device=0,
            command_class=CommandClass.GET_COMMAND,
            pid=StandardPID.to_pid(StandardPID.DEVICE_INFO),
            data=b"",
        )

        encoded = encoder.encode_rdm_request(request)

        # Verify RDM packet structure
        assert encoded[0] == 0xCC  # RDM start code
        assert encoded[1] == 0x01  # Sub-start code
        assert len(encoded) >= 24  # Minimum RDM packet size

    def test_encode_rdm_with_enttec_framing(self):
        """Test encoding RDM and framing for Enttec."""
        encoder = PacketEncoder()
        adapter = EnttecAdapter("COM1")

        request = RDMRequest(
            destination_uid=UID(0xFFFFFFFFFFFF),
            source_uid=UID(0x123400000001),
            transaction_number=TransactionNumber(1),
            port_address=1,
            sub_device=0,
            command_class=CommandClass.SET_COMMAND,
            pid=StandardPID.to_pid(StandardPID.IDENTIFY_DEVICE),
            data=bytes([0x01]),  # Turn on identify
        )

        # Encode RDM packet
        rdm_packet = encoder.encode_rdm_request(request)

        # Frame for Enttec
        framed = adapter.frame_rdm_request(rdm_packet)

        # Verify framing
        label, data = parse_enttec_frame(framed)
        assert label == EnttecMessageType.SEND_RDM_PACKET
        assert data == rdm_packet


class TestEnttecMessageTypes:
    """Test different Enttec message types."""

    def test_all_message_type_values(self):
        """Verify all Enttec message type enum values."""
        assert EnttecMessageType.GET_WIDGET_PARAMS == 3
        assert EnttecMessageType.OUTPUT_ONLY_SEND_DMX == 6
        assert EnttecMessageType.SEND_RDM_PACKET == 7
        assert EnttecMessageType.SEND_RDM_DISCOVERY == 11

    def test_message_type_in_framed_packet(self):
        """Test that message types are correctly embedded in frames."""
        adapter = EnttecAdapter("COM1")

        test_cases = [
            (adapter.frame_dmx_output(b"\xff\x00\x00"), EnttecMessageType.OUTPUT_ONLY_SEND_DMX),
            (adapter.frame_rdm_request(b"\xcc" + b"\x00" * 23), EnttecMessageType.SEND_RDM_PACKET),
            (
                adapter.frame_rdm_discovery_request(b"\xcc" + b"\x00" * 23),
                EnttecMessageType.SEND_RDM_DISCOVERY,
            ),
        ]

        for framed, expected_type in test_cases:
            label, _ = parse_enttec_frame(framed)
            assert label == expected_type


class TestEdgeCasesAndErrors:
    """Test edge cases and error conditions."""

    def test_find_frame_length_buffer_too_small(self):
        """Test frame length detection with very small buffer."""
        adapter = EnttecAdapter("COM1")

        tiny_buffer = bytes([0x7E])

        length = adapter.find_frame_length(tiny_buffer)
        assert length == 0

    def test_parse_truncated_frame(self):
        """Test parsing a truncated frame."""
        adapter = EnttecAdapter("COM1")

        truncated = bytes([0x7E, 0x05, 0x04, 0x00, 0x00])  # Missing data and END

        parsed = adapter.parse_rdm_response(truncated)
        assert parsed is None

    def test_parse_frame_with_error_status(self):
        """Test parsing RDM response with error status."""
        adapter = EnttecAdapter("COM1", use_mk2_protocol=False)

        rdm_data = bytes([0xCC] + [0x00] * 23)
        status = 0x01  # Error status

        frame_data = bytes([status]) + rdm_data
        framed = (
            bytes([0x7E, EnttecMessageType.RECEIVED_DMX_PACKET])
            + bytes([len(frame_data) & 0xFF, (len(frame_data) >> 8) & 0xFF])
            + frame_data
            + bytes([0xE7])
        )

        parsed = adapter.parse_rdm_response(framed)

        # Should still parse (status byte is stripped)
        assert parsed == rdm_data


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_dmx_output_sequence(self):
        """Test a sequence of DMX output frames."""
        adapter = EnttecAdapter("COM1")

        # Simulate fading animation
        frames = []
        for intensity in [0, 64, 128, 192, 255]:
            dmx_data = bytes([intensity, 0, 0])
            framed = adapter.frame_dmx_output(dmx_data)
            frames.append(framed)

        # Verify all frames are valid
        for framed in frames:
            label, data = parse_enttec_frame(framed)
            assert label == EnttecMessageType.OUTPUT_ONLY_SEND_DMX
            # Data includes start code (0x00) + 3 DMX bytes
            assert len(data) == 4

    def test_rdm_discovery_then_get_workflow(self):
        """Test RDM discovery followed by GET request."""
        adapter = EnttecAdapter("COM1")
        encoder = PacketEncoder()

        # Step 1: Discovery request
        discovery_data = bytes([0xCC, 0x01] + [0x00] * 22)
        discovery_frame = adapter.frame_rdm_discovery_request(discovery_data)

        label, _ = parse_enttec_frame(discovery_frame)
        assert label == EnttecMessageType.SEND_RDM_DISCOVERY

        # Step 2: GET request to discovered device
        request = RDMRequest(
            destination_uid=UID(0x123400000001),
            source_uid=UID(0xABCD00000001),
            transaction_number=TransactionNumber(2),
            port_address=1,
            sub_device=0,
            command_class=CommandClass.GET_COMMAND,
            pid=StandardPID.to_pid(StandardPID.DEVICE_INFO),
            data=b"",
        )

        rdm_packet = encoder.encode_rdm_request(request)
        get_frame = adapter.frame_rdm_request(rdm_packet)

        label, _ = parse_enttec_frame(get_frame)
        assert label == EnttecMessageType.SEND_RDM_PACKET


class TestEndToEndWorkflows:
    """Comprehensive end-to-end workflow tests."""

    def test_complete_rdm_discovery_workflow(self):
        """Test complete RDM discovery workflow: DUB -> MUTE -> GET."""
        adapter = EnttecAdapter("COM1")
        encoder = PacketEncoder()

        # Step 1: Discovery Unique Branch (DUB)
        dub_request = RDMRequest(
            destination_uid=UID(0xFFFFFFFFFFFF),  # Broadcast
            source_uid=UID(0x454E00000001),  # Controller UID
            transaction_number=TransactionNumber(1),
            port_address=1,
            sub_device=0,
            command_class=CommandClass.DISCOVERY_COMMAND,
            pid=StandardPID.to_pid(StandardPID.DISC_UNIQUE_BRANCH),
            data=bytes([0x00] * 12),  # Lower and upper bounds
        )

        dub_packet = encoder.encode_rdm_request(dub_request)
        dub_frame = adapter.frame_rdm_discovery_request(dub_packet)

        label, _ = parse_enttec_frame(dub_frame)
        assert label == EnttecMessageType.SEND_RDM_DISCOVERY

        # Step 2: MUTE discovered device
        discovered_uid = UID(0x123400000042)
        mute_request = RDMRequest(
            destination_uid=discovered_uid,
            source_uid=UID(0x454E00000001),
            transaction_number=TransactionNumber(2),
            port_address=1,
            sub_device=0,
            command_class=CommandClass.DISCOVERY_COMMAND,
            pid=StandardPID.to_pid(StandardPID.DISC_MUTE),
            data=b"",
        )

        mute_packet = encoder.encode_rdm_request(mute_request)
        mute_frame = adapter.frame_rdm_request(mute_packet)

        label, _ = parse_enttec_frame(mute_frame)
        assert label == EnttecMessageType.SEND_RDM_PACKET

        # Step 3: GET DEVICE_INFO from muted device
        info_request = RDMRequest(
            destination_uid=discovered_uid,
            source_uid=UID(0x454E00000001),
            transaction_number=TransactionNumber(3),
            port_address=1,
            sub_device=0,
            command_class=CommandClass.GET_COMMAND,
            pid=StandardPID.to_pid(StandardPID.DEVICE_INFO),
            data=b"",
        )

        info_packet = encoder.encode_rdm_request(info_request)
        info_frame = adapter.frame_rdm_request(info_packet)

        label, data = parse_enttec_frame(info_frame)
        assert label == EnttecMessageType.SEND_RDM_PACKET
        assert data[0] == 0xCC  # RDM start code

    def test_rdm_set_then_get_workflow(self):
        """Test SET parameter followed by GET to verify change."""
        adapter = EnttecAdapter("COM1")
        encoder = PacketEncoder()
        device_uid = UID(0x123400000042)
        controller_uid = UID(0x454E00000001)

        # Step 1: SET IDENTIFY_DEVICE (turn on identify LED)
        set_request = RDMRequest(
            destination_uid=device_uid,
            source_uid=controller_uid,
            transaction_number=TransactionNumber(1),
            port_address=1,
            sub_device=0,
            command_class=CommandClass.SET_COMMAND,
            pid=StandardPID.to_pid(StandardPID.IDENTIFY_DEVICE),
            data=bytes([0x01]),  # Turn on
        )

        set_packet = encoder.encode_rdm_request(set_request)
        set_frame = adapter.frame_rdm_request(set_packet)

        label, data = parse_enttec_frame(set_frame)
        assert label == EnttecMessageType.SEND_RDM_PACKET
        assert data == set_packet

        # Step 2: GET IDENTIFY_DEVICE to verify
        get_request = RDMRequest(
            destination_uid=device_uid,
            source_uid=controller_uid,
            transaction_number=TransactionNumber(2),
            port_address=1,
            sub_device=0,
            command_class=CommandClass.GET_COMMAND,
            pid=StandardPID.to_pid(StandardPID.IDENTIFY_DEVICE),
            data=b"",
        )

        get_packet = encoder.encode_rdm_request(get_request)
        get_frame = adapter.frame_rdm_request(get_packet)

        label, data = parse_enttec_frame(get_frame)
        assert label == EnttecMessageType.SEND_RDM_PACKET
        assert data == get_packet

    def test_dmx_output_continuous_streaming(self):
        """Test continuous DMX output for lighting control."""
        adapter = EnttecAdapter("COM1")

        # Simulate smooth RGB fade over 10 steps
        frames = []
        for step in range(10):
            # RGB crossfade: R fades down, G fades up, B stays mid
            r = 255 - (step * 25)
            g = step * 25
            b = 128
            dmx_data = bytes([r, g, b])

            framed = adapter.frame_dmx_output(dmx_data)
            frames.append(framed)

            # Verify each frame
            label, data = parse_enttec_frame(framed)
            assert label == EnttecMessageType.OUTPUT_ONLY_SEND_DMX
            assert len(data) == 4  # Start code + 3 channels
            assert data[0] == 0x00  # DMX start code

        # Verify we generated all frames
        assert len(frames) == 10

    def test_multi_universe_dmx_output(self):
        """Test DMX output for multiple universes (Mk2 scenario)."""
        adapter = EnttecAdapter("COM1", use_mk2_protocol=True)

        # Port 1: Red universe
        port1_dmx = bytes([0xFF, 0x00, 0x00] * 8)  # 24 channels
        frame1 = adapter.frame_dmx_output(port1_dmx, port=1)

        # Port 2: Green universe
        port2_dmx = bytes([0x00, 0xFF, 0x00] * 8)
        frame2 = adapter.frame_dmx_output(port2_dmx, port=2)

        # Verify both frames are valid and independent
        label1, data1 = parse_enttec_frame(frame1)
        label2, data2 = parse_enttec_frame(frame2)

        assert label1 == EnttecMessageType.OUTPUT_ONLY_SEND_DMX
        assert label2 == EnttecMessageType.OUTPUT_ONLY_SEND_DMX

        # Verify data is different
        assert data1 != data2

    def test_rdm_with_dmx_interleaving(self):
        """Test alternating between DMX output and RDM communication."""
        adapter = EnttecAdapter("COM1")
        encoder = PacketEncoder()

        # Step 1: Start DMX output
        dmx_data = bytes([0xFF, 0xFF, 0xFF])
        dmx_frame = adapter.frame_dmx_output(dmx_data)
        label, _ = parse_enttec_frame(dmx_frame)
        assert label == EnttecMessageType.OUTPUT_ONLY_SEND_DMX

        # Step 2: Send RDM query (DMX stops during RDM)
        rdm_request = RDMRequest(
            destination_uid=UID(0x123400000042),
            source_uid=UID(0x454E00000001),
            transaction_number=TransactionNumber(1),
            port_address=1,
            sub_device=0,
            command_class=CommandClass.GET_COMMAND,
            pid=StandardPID.to_pid(StandardPID.DMX_START_ADDRESS),
            data=b"",
        )

        rdm_packet = encoder.encode_rdm_request(rdm_request)
        rdm_frame = adapter.frame_rdm_request(rdm_packet)
        label, _ = parse_enttec_frame(rdm_frame)
        assert label == EnttecMessageType.SEND_RDM_PACKET

        # Step 3: Resume DMX output
        dmx_frame2 = adapter.frame_dmx_output(dmx_data)
        label, _ = parse_enttec_frame(dmx_frame2)
        assert label == EnttecMessageType.OUTPUT_ONLY_SEND_DMX

    def test_widget_params_get_workflow(self):
        """Test getting widget parameters."""
        adapter = EnttecAdapter("COM1")

        # Get widget parameters request
        params_request = adapter.get_widget_params_request()

        # Verify frame structure
        label, data = parse_enttec_frame(params_request)
        assert label == EnttecMessageType.GET_WIDGET_PARAMS
        assert len(data) == 2  # User config size bytes

    def test_widget_serial_get_workflow(self):
        """Test getting widget serial number."""
        adapter = EnttecAdapter("COM1")

        # Get serial number request
        serial_request = adapter.get_widget_serial_request()

        # Verify frame structure
        label, data = parse_enttec_frame(serial_request)
        assert label == EnttecMessageType.GET_WIDGET_SERIAL_NUMBER
        assert len(data) == 0  # No data in request

    def test_encode_decode_roundtrip(self):
        """Test full encode-frame-parse roundtrip."""
        adapter = EnttecAdapter("COM1", use_mk2_protocol=False)
        encoder = PacketEncoder()

        # Create RDM request
        request = RDMRequest(
            destination_uid=UID(0x123400000042),
            source_uid=UID(0x454E00000001),
            transaction_number=TransactionNumber(5),
            port_address=1,
            sub_device=0,
            command_class=CommandClass.GET_COMMAND,
            pid=StandardPID.to_pid(StandardPID.DEVICE_LABEL),
            data=b"",
        )

        # Encode to RDM packet
        rdm_packet = encoder.encode_rdm_request(request)
        assert rdm_packet[0] == 0xCC  # RDM start code

        # Frame for Enttec
        enttec_frame = adapter.frame_rdm_request(rdm_packet)
        assert enttec_frame[0] == 0x7E  # Enttec START
        assert enttec_frame[-1] == 0xE7  # Enttec END

        # Simulate response (device echoes request structure)
        response_rdm = rdm_packet  # Simplified: use same packet as response
        status = 0x00
        response_data = bytes([status]) + response_rdm

        response_frame = (
            bytes([0x7E, EnttecMessageType.RECEIVED_DMX_PACKET])
            + bytes([len(response_data) & 0xFF, (len(response_data) >> 8) & 0xFF])
            + response_data
            + bytes([0xE7])
        )

        # Parse response
        parsed_rdm = adapter.parse_rdm_response(response_frame)
        assert parsed_rdm is not None
        assert parsed_rdm[0] == 0xCC  # RDM start code

    def test_large_dmx_universe_512_channels(self):
        """Test full 512-channel DMX universe."""
        adapter = EnttecAdapter("COM1")

        # Create full 512-channel universe
        # Pattern: alternating high/low
        dmx_data = bytes([0xFF if i % 2 == 0 else 0x00 for i in range(512)])

        framed = adapter.frame_dmx_output(dmx_data)

        # Verify frame
        label, data = parse_enttec_frame(framed)
        assert label == EnttecMessageType.OUTPUT_ONLY_SEND_DMX
        assert len(data) == 513  # Start code + 512 channels
        assert data[0] == 0x00  # DMX start code
        assert data[1:] == dmx_data  # Verify all channels preserved

    def test_rdm_broadcast_then_unicast(self):
        """Test RDM broadcast followed by targeted unicast."""
        adapter = EnttecAdapter("COM1")
        encoder = PacketEncoder()
        controller_uid = UID(0x454E00000001)

        # Step 1: Broadcast UNMUTE to all devices
        unmute_broadcast = RDMRequest(
            destination_uid=UID(0xFFFFFFFFFFFF),  # Broadcast
            source_uid=controller_uid,
            transaction_number=TransactionNumber(1),
            port_address=1,
            sub_device=0,
            command_class=CommandClass.DISCOVERY_COMMAND,
            pid=StandardPID.to_pid(StandardPID.DISC_UN_MUTE),
            data=b"",
        )

        broadcast_packet = encoder.encode_rdm_request(unmute_broadcast)
        broadcast_frame = adapter.frame_rdm_request(broadcast_packet)

        label, _ = parse_enttec_frame(broadcast_frame)
        assert label == EnttecMessageType.SEND_RDM_PACKET

        # Step 2: Unicast GET to specific device
        device_uid = UID(0x123400000042)
        get_request = RDMRequest(
            destination_uid=device_uid,
            source_uid=controller_uid,
            transaction_number=TransactionNumber(2),
            port_address=1,
            sub_device=0,
            command_class=CommandClass.GET_COMMAND,
            pid=StandardPID.to_pid(StandardPID.SOFTWARE_VERSION_LABEL),
            data=b"",
        )

        unicast_packet = encoder.encode_rdm_request(get_request)
        unicast_frame = adapter.frame_rdm_request(unicast_packet)

        label, data = parse_enttec_frame(unicast_frame)
        assert label == EnttecMessageType.SEND_RDM_PACKET

        # Verify UID is unicast not broadcast
        dest_uid_bytes = data[4:10]  # UID location in RDM packet
        assert dest_uid_bytes != bytes([0xFF] * 6)

    def test_multiple_rdm_parameters_sequence(self):
        """Test querying multiple RDM parameters in sequence."""
        adapter = EnttecAdapter("COM1")
        encoder = PacketEncoder()
        device_uid = UID(0x123400000042)
        controller_uid = UID(0x454E00000001)

        # Query multiple parameters
        pids_to_query = [
            StandardPID.DEVICE_INFO,
            StandardPID.DEVICE_LABEL,
            StandardPID.DMX_START_ADDRESS,
            StandardPID.DMX_PERSONALITY,
            StandardPID.SOFTWARE_VERSION_LABEL,
        ]

        for i, pid in enumerate(pids_to_query):
            request = RDMRequest(
                destination_uid=device_uid,
                source_uid=controller_uid,
                transaction_number=TransactionNumber(i + 1),
                port_address=1,
                sub_device=0,
                command_class=CommandClass.GET_COMMAND,
                pid=StandardPID.to_pid(pid),
                data=b"",
            )

            packet = encoder.encode_rdm_request(request)
            frame = adapter.frame_rdm_request(packet)

            label, data = parse_enttec_frame(frame)
            assert label == EnttecMessageType.SEND_RDM_PACKET
            assert data[0] == 0xCC  # RDM start code

            # Verify transaction number increments (index 15 in RDM packet)
            # RDM structure: SC(0), SSC(1), MsgLen(2), DestUID(3-8), SrcUID(9-14), TN(15)
            assert data[15] == i + 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
