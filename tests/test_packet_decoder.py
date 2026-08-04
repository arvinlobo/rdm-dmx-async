"""
Unit tests for PacketDecoder (RDM response wire-format parsing).
"""

import struct

import pytest

from rdm_dmx_async.packets.decoder import PacketDecodeError, PacketDecoder
from rdm_dmx_async.packets.types import PID, UID, CommandClass, ResponseType, StartCode


def _checksum(data: bytes) -> int:
    return sum(data) & 0xFFFF


def _build_response_frame(
    destination_uid: bytes = bytes.fromhex("454E00000000"),
    source_uid: bytes = bytes.fromhex("454E00000001"),
    transaction_number: int = 5,
    response_type: int = ResponseType.ACK,
    command_class: int = CommandClass.GET_COMMAND_RESPONSE,
    pid: int = 0x1000,
    data: bytes = b"",
    corrupt_checksum: bool = False,
) -> bytes:
    body = bytearray()
    body.append(StartCode.RDM)
    body.append(0x01)
    body.append(24 + len(data))
    body.extend(destination_uid)
    body.extend(source_uid)
    body.append(transaction_number)
    body.append(response_type)
    body.append(0)  # message count
    body.extend(struct.pack(">H", 0))  # sub-device
    body.append(command_class)
    body.extend(struct.pack(">H", pid))
    body.append(len(data))
    body.extend(data)

    checksum = _checksum(bytes(body))
    if corrupt_checksum:
        checksum ^= 0xFFFF
    body.extend(struct.pack(">H", checksum))
    return bytes(body)


class TestDecodeRdmResponse:
    def test_decode_valid_ack_response(self):
        decoder = PacketDecoder()
        frame = _build_response_frame(data=b"\x01\x02")

        response = decoder.decode_rdm_response(frame)

        assert response is not None
        assert response.checksum_valid is True
        assert response.response_type == ResponseType.ACK
        assert response.command_class == CommandClass.GET_COMMAND_RESPONSE
        assert response.pid == PID(0x1000)
        assert response.data == b"\x01\x02"
        assert response.source_uid == UID(int.from_bytes(bytes.fromhex("454E00000001"), "big"))

    def test_decode_invalid_checksum_marks_response_invalid(self):
        decoder = PacketDecoder()
        frame = _build_response_frame(corrupt_checksum=True)

        response = decoder.decode_rdm_response(frame)

        assert response is not None
        assert response.checksum_valid is False

    def test_decode_too_short_returns_none(self):
        decoder = PacketDecoder()

        assert decoder.decode_rdm_response(b"\xcc\x01\x00") is None

    def test_decode_wrong_start_code_returns_none(self):
        decoder = PacketDecoder()
        frame = bytearray(_build_response_frame())
        frame[0] = 0x00

        assert decoder.decode_rdm_response(bytes(frame)) is None

    def test_decode_wrong_sub_start_code_returns_none(self):
        decoder = PacketDecoder()
        frame = bytearray(_build_response_frame())
        frame[1] = 0x02

        assert decoder.decode_rdm_response(bytes(frame)) is None

    def test_decode_invalid_response_type_raises_decode_error(self):
        decoder = PacketDecoder()
        frame = bytearray(_build_response_frame())
        frame[16] = 0xFF  # Not a valid ResponseType value

        with pytest.raises(PacketDecodeError):
            decoder.decode_rdm_response(bytes(frame))
