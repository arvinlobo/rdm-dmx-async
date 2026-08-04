"""Unit tests for `GenericSerialAdapter` (transport/adapters/generic_serial.py)."""

import pytest

from rdm_dmx_async.transport.adapters.generic_serial import FramingMode, GenericSerialAdapter
from rdm_dmx_async.transport.interface_adapter import InterfaceType


class TestGenericSerialAdapterConfig:
    def test_defaults(self):
        adapter = GenericSerialAdapter("COM4")

        assert adapter.interface_type == InterfaceType.GENERIC_SERIAL
        assert adapter.serial_config.port == "COM4"
        assert adapter.serial_config.baudrate == 9600

    def test_custom_baudrate(self):
        adapter = GenericSerialAdapter("COM4", baudrate=115200)

        assert adapter.serial_config.baudrate == 115200

    def test_frame_dmx_output_always_raises(self):
        adapter = GenericSerialAdapter("COM4")

        with pytest.raises(NotImplementedError):
            adapter.frame_dmx_output(bytes([0xFF, 0x00]))


class TestRawFraming:
    def test_frame_rdm_request_is_passthrough(self):
        adapter = GenericSerialAdapter("COM4", framing=FramingMode.RAW)
        data = b"\x01\x02\x03"

        assert adapter.frame_rdm_request(data) == data

    def test_find_frame_length_consumes_everything(self):
        adapter = GenericSerialAdapter("COM4", framing=FramingMode.RAW)

        assert adapter.find_frame_length(b"\x01\x02\x03") == 3

    def test_parse_rdm_response_returns_all_data(self):
        adapter = GenericSerialAdapter("COM4", framing=FramingMode.RAW)

        assert adapter.parse_rdm_response(b"\x01\x02") == b"\x01\x02"

    def test_parse_rdm_response_empty_returns_none(self):
        adapter = GenericSerialAdapter("COM4", framing=FramingMode.RAW)

        assert adapter.parse_rdm_response(b"") is None


class TestLineBasedFraming:
    def test_frame_rdm_request_appends_newline_if_missing(self):
        adapter = GenericSerialAdapter("COM4", framing=FramingMode.LINE_BASED)

        assert adapter.frame_rdm_request(b"hello") == b"hello\n"

    def test_frame_rdm_request_does_not_duplicate_newline(self):
        adapter = GenericSerialAdapter("COM4", framing=FramingMode.LINE_BASED)

        assert adapter.frame_rdm_request(b"hello\n") == b"hello\n"

    def test_find_frame_length_locates_delimiter(self):
        adapter = GenericSerialAdapter("COM4", framing=FramingMode.LINE_BASED)

        assert adapter.find_frame_length(b"hello\nworld") == len(b"hello\n")

    def test_find_frame_length_no_delimiter_returns_zero(self):
        adapter = GenericSerialAdapter("COM4", framing=FramingMode.LINE_BASED)

        assert adapter.find_frame_length(b"hello") == 0

    def test_parse_rdm_response_includes_delimiter(self):
        adapter = GenericSerialAdapter("COM4", framing=FramingMode.LINE_BASED)

        assert adapter.parse_rdm_response(b"hello\nworld") == b"hello\n"

    def test_parse_rdm_response_no_delimiter_returns_none(self):
        adapter = GenericSerialAdapter("COM4", framing=FramingMode.LINE_BASED)

        assert adapter.parse_rdm_response(b"hello") is None


class TestLengthPrefixFraming:
    def test_frame_rdm_request_prepends_length_byte(self):
        adapter = GenericSerialAdapter("COM4", framing=FramingMode.LENGTH_PREFIX)

        assert adapter.frame_rdm_request(b"abc") == bytes([3]) + b"abc"

    def test_frame_rdm_request_rejects_oversized_data(self):
        adapter = GenericSerialAdapter("COM4", framing=FramingMode.LENGTH_PREFIX)

        with pytest.raises(ValueError):
            adapter.frame_rdm_request(bytes(256))

    def test_find_frame_length_complete_frame(self):
        adapter = GenericSerialAdapter("COM4", framing=FramingMode.LENGTH_PREFIX)
        buffer = bytes([3]) + b"abc"

        assert adapter.find_frame_length(buffer) == 4

    def test_find_frame_length_incomplete_frame_returns_zero(self):
        adapter = GenericSerialAdapter("COM4", framing=FramingMode.LENGTH_PREFIX)
        buffer = bytes([3]) + b"a"  # declares 3 bytes but only 1 has arrived

        assert adapter.find_frame_length(buffer) == 0

    def test_find_frame_length_empty_buffer_returns_zero(self):
        adapter = GenericSerialAdapter("COM4", framing=FramingMode.LENGTH_PREFIX)

        assert adapter.find_frame_length(b"") == 0

    def test_parse_rdm_response_strips_length_byte(self):
        adapter = GenericSerialAdapter("COM4", framing=FramingMode.LENGTH_PREFIX)
        buffer = bytes([3]) + b"abc"

        assert adapter.parse_rdm_response(buffer) == b"abc"

    def test_parse_rdm_response_incomplete_returns_none(self):
        adapter = GenericSerialAdapter("COM4", framing=FramingMode.LENGTH_PREFIX)

        assert adapter.parse_rdm_response(bytes([3]) + b"a") is None


class TestDelimiterFraming:
    def test_frame_rdm_request_appends_custom_delimiter(self):
        adapter = GenericSerialAdapter("COM4", framing=FramingMode.DELIMITER, delimiter=b"\x00")

        assert adapter.frame_rdm_request(b"abc") == b"abc\x00"

    def test_find_frame_length_locates_custom_delimiter(self):
        adapter = GenericSerialAdapter("COM4", framing=FramingMode.DELIMITER, delimiter=b"\x00")

        assert adapter.find_frame_length(b"abc\x00def") == 4

    def test_parse_rdm_response_excludes_delimiter(self):
        adapter = GenericSerialAdapter("COM4", framing=FramingMode.DELIMITER, delimiter=b"\x00")

        assert adapter.parse_rdm_response(b"abc\x00def") == b"abc"

    def test_parse_rdm_response_no_delimiter_returns_none(self):
        adapter = GenericSerialAdapter("COM4", framing=FramingMode.DELIMITER, delimiter=b"\x00")

        assert adapter.parse_rdm_response(b"abc") is None
