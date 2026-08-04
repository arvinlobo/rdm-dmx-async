"""
End-to-end tests for RDME120Protocol using an in-memory fake transport.

These exercise the full send path (encode -> transport.send) and receive
path (transport.receive -> decode -> validate -> correlate) together,
without needing real serial hardware.
"""

import asyncio
import struct

import pytest

from rdm_dmx_async.domain.parameters import StandardPID
from rdm_dmx_async.packets.types import (
    PID,
    UID,
    CommandClass,
    ResponseType,
    StartCode,
    TransactionNumber,
)
from rdm_dmx_async.protocols.rdm_e120 import ProtocolTimeoutError, RDME120Protocol
from rdm_dmx_async.transaction.allocator import TransactionNumberAllocator

CONTROLLER_UID = UID(0x454E00000000)
DEVICE_UID = UID(0x454E00000001)


class FakeTransport:
    """Minimal in-memory stand-in for AsyncTransport."""

    def __init__(self):
        self.sent: list[tuple[bytes, str]] = []
        self._rx_queue: asyncio.Queue = asyncio.Queue()
        self.is_connected = True

    async def connect(self) -> None:
        self.is_connected = True

    async def disconnect(self) -> None:
        self.is_connected = False

    async def send(self, data: bytes, destination: str) -> None:
        self.sent.append((data, destination))

    async def receive(self, timeout=None):
        try:
            return await asyncio.wait_for(self._rx_queue.get(), timeout)
        except TimeoutError as exc:
            raise TimeoutError() from exc

    def queue_incoming(self, data: bytes, source: str = "") -> None:
        self._rx_queue.put_nowait((data, source))


def _checksum(data: bytes) -> int:
    return sum(data) & 0xFFFF


def _build_ack_response(
    transaction_number: int,
    pid: int,
    command_class: int,
    data: bytes = b"",
) -> bytes:
    body = bytearray()
    body.append(StartCode.RDM)
    body.append(0x01)
    body.append(24 + len(data))
    body.extend(int(CONTROLLER_UID).to_bytes(6, "big"))  # destination = controller
    body.extend(int(DEVICE_UID).to_bytes(6, "big"))  # source = responding device
    body.append(transaction_number)
    body.append(ResponseType.ACK)
    body.append(0)  # message count
    body.extend(struct.pack(">H", 0))  # sub-device
    body.append(command_class)
    body.extend(struct.pack(">H", pid))
    body.append(len(data))
    body.extend(data)
    body.extend(struct.pack(">H", _checksum(bytes(body))))
    return bytes(body)


def _encode_manchester_byte(value: int) -> int:
    encoded = 0
    for bit in range(8):
        b = (value >> (7 - bit)) & 1
        code = 0b10 if b else 0b01
        encoded |= code << (14 - bit * 2)
    return encoded


def _build_dub_response(uid: bytes) -> bytes:
    manchester = bytearray()
    for byte in uid + b"\x00\x00":  # UID + placeholder checksum (uncredited by codec)
        manchester.extend([0xFF, byte])
    return b"\xfe" * 7 + b"\xaa" + bytes(manchester)


@pytest.mark.asyncio
class TestRDME120ProtocolEndToEnd:
    async def test_get_command_success_round_trip(self):
        transport = FakeTransport()
        protocol = RDME120Protocol(
            transport, source_uid=CONTROLLER_UID, allocator=TransactionNumberAllocator()
        )
        await protocol.start()
        try:
            txn = TransactionNumber(7)

            async def responder():
                # Wait for the request to be sent, then reply with a matching ACK.
                while not transport.sent:
                    await asyncio.sleep(0)
                response = _build_ack_response(
                    transaction_number=int(txn),
                    pid=0x1000,
                    command_class=CommandClass.GET_COMMAND_RESPONSE,
                    data=b"\x2a",
                )
                transport.queue_incoming(response)

            asyncio.create_task(responder())

            response = await protocol.send_get_command(
                destination_uid=DEVICE_UID,
                pid=PID(0x1000),
                transaction_number=txn,
                timeout=1.0,
            )

            assert response.source_uid == DEVICE_UID
            assert response.is_ack
            assert response.data == b"\x2a"
            assert len(transport.sent) == 1
        finally:
            await protocol.stop()

    async def test_get_command_timeout_raises(self):
        transport = FakeTransport()
        protocol = RDME120Protocol(
            transport, source_uid=CONTROLLER_UID, allocator=TransactionNumberAllocator()
        )
        await protocol.start()
        try:
            with pytest.raises(ProtocolTimeoutError):
                await protocol.send_get_command(
                    destination_uid=DEVICE_UID,
                    pid=PID(0x1000),
                    transaction_number=TransactionNumber(1),
                    timeout=0.1,
                )
        finally:
            await protocol.stop()

    async def test_discovery_unique_branch_decodes_uid(self):
        transport = FakeTransport()
        protocol = RDME120Protocol(
            transport, source_uid=CONTROLLER_UID, allocator=TransactionNumberAllocator()
        )
        await protocol.start()
        try:

            async def responder():
                while not transport.sent:
                    await asyncio.sleep(0)
                transport.queue_incoming(_build_dub_response(int(DEVICE_UID).to_bytes(6, "big")))

            asyncio.create_task(responder())

            response = await protocol.send_discovery_command(
                destination_uid=UID(0xFFFFFFFFFFFF),
                pid=PID(StandardPID.DISC_UNIQUE_BRANCH),
                transaction_number=TransactionNumber(1),
                timeout=1.0,
            )

            assert response is not None
            assert response.source_uid == DEVICE_UID
        finally:
            await protocol.stop()

    async def test_discovery_unique_branch_no_response_raises_timeout(self):
        transport = FakeTransport()
        protocol = RDME120Protocol(
            transport, source_uid=CONTROLLER_UID, allocator=TransactionNumberAllocator()
        )
        await protocol.start()
        try:
            with pytest.raises(ProtocolTimeoutError):
                await protocol.send_discovery_command(
                    destination_uid=UID(0xFFFFFFFFFFFF),
                    pid=PID(StandardPID.DISC_UNIQUE_BRANCH),
                    transaction_number=TransactionNumber(1),
                    timeout=0.1,
                )
        finally:
            await protocol.stop()
