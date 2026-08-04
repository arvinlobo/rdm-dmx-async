"""
End-to-end tests for the real serial transport stack (AsyncSerialTransport +
EnttecAdapter, USB DMX PRO variant) against a mocked serial port.

Unlike test_rdm_e120_protocol_e2e.py (which fakes out the AsyncTransport
Protocol entirely, skipping adapter framing/parsing), these tests patch
`serial.Serial` with a byte-level fake that behaves like a real Enttec USB
DMX PRO widget: it receives Enttec-framed bytes over "the wire", and replies
with Enttec-framed bytes, exercising the adapter's real framing/parsing code
and AsyncSerialTransport's background RX/TX loops and frame buffering.
"""

import struct
import threading

import pytest

import rdm_dmx_async.transport.serial_transport as serial_transport_module
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
from rdm_dmx_async.transport.adapters.enttec import EnttecAdapter, EnttecMessageType
from rdm_dmx_async.transport.serial_transport import AsyncSerialTransport

CONTROLLER_UID = UID(0x454E00000000)
DEVICE_UID = UID(0x454E00000001)


class FakeEnttecSerial:
    """Byte-level stand-in for `serial.Serial` simulating an Enttec USB DMX PRO widget."""

    START = 0x7E
    END = 0xE7

    def __init__(self, **_kwargs):
        # _kwargs accepted for signature compatibility with serial.Serial(...)
        self.is_open = True
        self._inbox = bytearray()
        self._outbox = bytearray()
        # Set by tests: callable(label: int, data: bytes) -> None
        self.on_frame = None

    def reset_input_buffer(self) -> None:
        pass

    def reset_output_buffer(self) -> None:
        pass

    def write(self, data: bytes) -> int:
        self._inbox.extend(data)
        self._drain()
        return len(data)

    def read(self, size: int) -> bytes:
        if not self._outbox:
            return b""
        chunk = bytes(self._outbox[:size])
        del self._outbox[:size]
        return chunk

    def close(self) -> None:
        self.is_open = False

    def queue_response(self, label: int, data: bytes) -> None:
        """Queue a widget->host frame, as if real hardware had sent it."""
        frame = bytearray([self.START, label])
        frame.extend(struct.pack("<H", len(data)))
        frame.extend(data)
        frame.append(self.END)
        self._outbox.extend(frame)

    def _drain(self) -> None:
        """Parse complete Enttec frames out of the write buffer and dispatch them."""
        while len(self._inbox) >= 5:
            if self._inbox[0] != self.START:
                del self._inbox[0]
                continue

            data_len = self._inbox[2] | (self._inbox[3] << 8)
            frame_len = 5 + data_len
            if len(self._inbox) < frame_len:
                break
            if self._inbox[frame_len - 1] != self.END:
                del self._inbox[0]
                continue

            label = self._inbox[1]
            data = bytes(self._inbox[4 : 4 + data_len])
            del self._inbox[:frame_len]

            if self.on_frame:
                self.on_frame(label, data)


@pytest.fixture
def fake_serial_instances(monkeypatch):
    """Patch `serial.Serial` so AsyncSerialTransport talks to fake hardware."""
    instances: list[FakeEnttecSerial] = []

    def _factory(**kwargs):
        fake = FakeEnttecSerial(**kwargs)
        instances.append(fake)
        return fake

    monkeypatch.setattr(serial_transport_module.serial, "Serial", _factory)
    return instances


def _checksum(data: bytes) -> int:
    return sum(data) & 0xFFFF


def _build_ack_response_rdm(
    transaction_number: int, pid: int, command_class: int, data: bytes = b""
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


def _build_dub_manchester_frame(uid: bytes) -> bytes:
    manchester = bytearray()
    for byte in uid + b"\x00\x00":  # UID + placeholder checksum
        manchester.extend([0xFF, byte])
    return b"\xfe" * 7 + b"\xaa" + bytes(manchester)


@pytest.mark.asyncio
class TestEnttecUsbProSerialTransportEndToEnd:
    """
    Real transport stack (AsyncSerialTransport + EnttecAdapter, non-Mk2 USB
    DMX PRO framing) driven against a fake serial port standing in for hardware.
    """

    async def test_get_command_success_round_trip(self, fake_serial_instances):
        adapter = EnttecAdapter("COM_FAKE", use_mk2_protocol=False)
        transport = AsyncSerialTransport(adapter)

        async with transport:
            fake = fake_serial_instances[0]
            txn = TransactionNumber(7)

            def respond(label: int, _data: bytes) -> None:
                if label != EnttecMessageType.SEND_RDM_PACKET:
                    return
                response_rdm = _build_ack_response_rdm(
                    transaction_number=int(txn),
                    pid=0x1000,
                    command_class=CommandClass.GET_COMMAND_RESPONSE,
                    data=b"\x2a",
                )
                # Original (non-Mk2) USB Pro format: status byte + RDM data
                fake.queue_response(EnttecMessageType.RECEIVED_DMX_PACKET, b"\x00" + response_rdm)

            fake.on_frame = respond

            protocol = RDME120Protocol(
                transport, source_uid=CONTROLLER_UID, allocator=TransactionNumberAllocator()
            )
            await protocol.start()
            try:
                response = await protocol.send_get_command(
                    destination_uid=DEVICE_UID,
                    pid=PID(0x1000),
                    transaction_number=txn,
                    timeout=2.0,
                )

                assert response.source_uid == DEVICE_UID
                assert response.is_ack
                assert response.data == b"\x2a"
            finally:
                await protocol.stop()

    async def test_get_command_timeout_raises(self, fake_serial_instances):
        adapter = EnttecAdapter("COM_FAKE", use_mk2_protocol=False)
        transport = AsyncSerialTransport(adapter)

        async with transport:
            # No on_frame handler set - fake hardware never replies.
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
                        timeout=0.2,
                    )
            finally:
                await protocol.stop()

    async def test_discovery_unique_branch_decodes_uid(self, fake_serial_instances):
        adapter = EnttecAdapter("COM_FAKE", use_mk2_protocol=False)
        transport = AsyncSerialTransport(adapter)

        async with transport:
            fake = fake_serial_instances[0]

            def respond(label: int, _data: bytes) -> None:
                if label != EnttecMessageType.SEND_RDM_DISCOVERY:
                    return
                dub_frame = _build_dub_manchester_frame(int(DEVICE_UID).to_bytes(6, "big"))
                # Discovery responses use the original status+data format on both variants.
                fake.queue_response(EnttecMessageType.RECEIVED_DMX_PACKET, b"\x00" + dub_frame)

            fake.on_frame = respond

            protocol = RDME120Protocol(
                transport, source_uid=CONTROLLER_UID, allocator=TransactionNumberAllocator()
            )
            await protocol.start()
            try:
                response = await protocol.send_discovery_command(
                    destination_uid=UID(0xFFFFFFFFFFFF),
                    pid=PID(StandardPID.DISC_UNIQUE_BRANCH),
                    transaction_number=TransactionNumber(1),
                    timeout=2.0,
                )

                assert response is not None
                assert response.source_uid == DEVICE_UID
            finally:
                await protocol.stop()

    async def test_response_split_across_multiple_reads_is_still_parsed(
        self, fake_serial_instances
    ):
        """Simulates the response frame trickling in over two separate
        serial reads (e.g. slow UART pacing), rather than arriving whole in
        a single read - the real-world "middle bytes arrive later" case."""
        adapter = EnttecAdapter("COM_FAKE", use_mk2_protocol=False)
        transport = AsyncSerialTransport(adapter)

        async with transport:
            fake = fake_serial_instances[0]
            txn = TransactionNumber(9)

            def respond(label: int, _data: bytes) -> None:
                if label != EnttecMessageType.SEND_RDM_PACKET:
                    return
                response_rdm = _build_ack_response_rdm(
                    transaction_number=int(txn),
                    pid=0x1000,
                    command_class=CommandClass.GET_COMMAND_RESPONSE,
                    data=b"\x2a",
                )
                full_frame_data = b"\x00" + response_rdm
                # Queue the frame as two Enttec messages' worth of raw bytes,
                # but only expose the first half to read() right away - the
                # rest is appended to the fake's outbox after a short delay,
                # forcing AsyncSerialTransport/FrameBuffer to assemble the
                # frame across two separate RX loop iterations.
                response_label = EnttecMessageType.RECEIVED_DMX_PACKET
                frame = bytearray([fake.START, response_label])
                frame.extend(struct.pack("<H", len(full_frame_data)))
                frame.extend(full_frame_data)
                frame.append(fake.END)
                midpoint = len(frame) // 2
                fake._outbox.extend(frame[:midpoint])

                # respond() runs inside AsyncSerialTransport's TX executor
                # thread (via run_in_executor), not the event loop, so a
                # plain background timer thread delivers the rest instead
                # of scheduling an asyncio task from the wrong thread.
                threading.Timer(0.05, lambda: fake._outbox.extend(frame[midpoint:])).start()

            fake.on_frame = respond

            protocol = RDME120Protocol(
                transport, source_uid=CONTROLLER_UID, allocator=TransactionNumberAllocator()
            )
            await protocol.start()
            try:
                response = await protocol.send_get_command(
                    destination_uid=DEVICE_UID,
                    pid=PID(0x1000),
                    transaction_number=txn,
                    timeout=2.0,
                )

                assert response.source_uid == DEVICE_UID
                assert response.is_ack
                assert response.data == b"\x2a"
            finally:
                await protocol.stop()

    async def test_transport_receive_times_out_with_no_response(self, fake_serial_instances):
        """Exercises AsyncSerialTransport.receive()'s own timeout directly,
        independent of the higher ProtocolTimeoutError layer."""
        adapter = EnttecAdapter("COM_FAKE", use_mk2_protocol=False)
        transport = AsyncSerialTransport(adapter)

        async with transport:
            with pytest.raises(TimeoutError):
                await transport.receive(timeout=0.1)

    async def test_transport_receive_returns_once_data_arrives_within_timeout(
        self, fake_serial_instances
    ):
        adapter = EnttecAdapter("COM_FAKE", use_mk2_protocol=False)
        transport = AsyncSerialTransport(adapter)

        async with transport:
            fake = fake_serial_instances[0]
            response_rdm = _build_ack_response_rdm(
                transaction_number=1,
                pid=0x1000,
                command_class=CommandClass.GET_COMMAND_RESPONSE,
                data=b"\x2a",
            )
            fake.queue_response(EnttecMessageType.RECEIVED_DMX_PACKET, b"\x00" + response_rdm)

            data, _source = await transport.receive(timeout=1.0)

            assert response_rdm in data
