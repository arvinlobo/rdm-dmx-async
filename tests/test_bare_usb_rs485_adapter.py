"""Unit tests for `BareUsbRs485Adapter` (transport/adapters/bare_usb_rs485.py)."""

from serial import EIGHTBITS, PARITY_NONE, STOPBITS_TWO

from rdm_dmx_async.transport.adapters import BareUsbRs485Adapter
from rdm_dmx_async.transport.interface_adapter import InterfaceType


class TestManualBreakAdapterConfig:
    def test_adapter_initialization(self):
        adapter = BareUsbRs485Adapter("COM7")

        assert adapter.interface_type == InterfaceType.BARE_USB_RS485
        assert adapter.requires_manual_break is True

    def test_serial_config_is_dmx512a_8n2(self):
        adapter = BareUsbRs485Adapter("COM7")

        config = adapter.serial_config

        assert config.port == "COM7"
        assert config.baudrate == 250000
        assert config.bytesize == EIGHTBITS
        assert config.parity == PARITY_NONE
        assert config.stopbits == STOPBITS_TWO


class TestManualBreakAdapterFraming:
    def test_frame_rdm_request_is_passthrough(self):
        adapter = BareUsbRs485Adapter("COM7")
        rdm_data = bytes([0xCC, 0x01, 0x18, 0xAA, 0xBB])

        assert adapter.frame_rdm_request(rdm_data) == rdm_data

    def test_frame_rdm_discovery_request_is_passthrough(self):
        adapter = BareUsbRs485Adapter("COM7")
        rdm_data = bytes([0xCC, 0x01, 0x18, 0xAA, 0xBB])

        assert adapter.frame_rdm_discovery_request(rdm_data) == rdm_data

    def test_frame_dmx_output_prepends_start_code(self):
        adapter = BareUsbRs485Adapter("COM7")
        dmx_data = bytes([0xFF, 0x7F, 0x00])

        framed = adapter.frame_dmx_output(dmx_data)

        assert framed == bytes([0x00]) + dmx_data


class TestManualBreakAdapterFindFrameLength:
    def test_empty_buffer_returns_zero(self):
        adapter = BareUsbRs485Adapter("COM7")

        assert adapter.find_frame_length(b"") == 0

    def test_unrecognized_leading_byte_returns_zero(self):
        adapter = BareUsbRs485Adapter("COM7")

        assert adapter.find_frame_length(bytes([0x11, 0x22, 0x33])) == 0

    def test_rdm_frame_too_short_to_read_length_field(self):
        adapter = BareUsbRs485Adapter("COM7")

        assert adapter.find_frame_length(bytes([0xCC, 0x01])) == 0

    def test_rdm_frame_length_from_message_length_field(self):
        adapter = BareUsbRs485Adapter("COM7")
        message_length = 24
        total = message_length + 2  # message bytes + 2 checksum bytes
        # Message-Length field (byte[2]) counts start code through last
        # parameter data byte; total frame adds 2 checksum bytes.
        buffer = bytes([0xCC, 0x01, message_length]) + bytes(total - 3)

        assert adapter.find_frame_length(buffer) == total

    def test_rdm_frame_incomplete_returns_zero(self):
        adapter = BareUsbRs485Adapter("COM7")
        message_length = 24
        # Declares a 26-byte frame but only 10 bytes have arrived so far.
        buffer = bytes([0xCC, 0x01, message_length]) + bytes(7)

        assert adapter.find_frame_length(buffer) == 0

    def test_bare_start_byte_without_fe_preamble_is_unrecognized(self):
        # find_discovery_frame_length requires at least one 0xFE preamble
        # byte, so a bare 0xAA start (no preamble) falls through as unrecognized.
        adapter = BareUsbRs485Adapter("COM7")
        buffer = bytes([0xAA]) + bytes(16)

        assert adapter.find_frame_length(buffer) == 0

    def test_discovery_frame_with_preamble(self):
        adapter = BareUsbRs485Adapter("COM7")
        buffer = bytes([0xFE, 0xFE, 0xAA]) + bytes(16)

        assert adapter.find_frame_length(buffer) == 19

    def test_discovery_frame_incomplete_returns_zero(self):
        adapter = BareUsbRs485Adapter("COM7")
        buffer = bytes([0xFE, 0xAA]) + bytes(5)  # fewer than 16 Manchester bytes

        assert adapter.find_frame_length(buffer) == 0


class TestManualBreakAdapterParseRdmResponse:
    def test_extracts_exactly_one_frame(self):
        adapter = BareUsbRs485Adapter("COM7")
        message_length = 24
        total = message_length + 2
        frame = bytes([0xCC, 0x01, message_length]) + bytes(total - 3)
        buffer = frame + bytes([0xCC, 0x01, 0x05])  # leading bytes of a second frame

        parsed = adapter.parse_rdm_response(buffer)

        assert parsed == frame

    def test_incomplete_frame_returns_none(self):
        adapter = BareUsbRs485Adapter("COM7")

        assert adapter.parse_rdm_response(bytes([0xCC, 0x01])) is None

    def test_unrecognized_data_returns_none(self):
        adapter = BareUsbRs485Adapter("COM7")

        assert adapter.parse_rdm_response(bytes([0x11, 0x22])) is None
