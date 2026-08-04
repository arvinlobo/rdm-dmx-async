"""RDM E1.20 protocol implementation."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from ..packets.decoder import PacketDecodeError, PacketDecoder
from ..packets.encoder import PacketEncoder
from ..packets.rdm import RDMRequest, RDMResponse
from ..packets.types import PID, UID, CommandClass, ResponseType, TransactionNumber
from ..scheduling.dmx_scheduler import DmxFrameScheduler
from ..transport.base import AsyncTransport
from .manchester_codec import ManchesterDiscoveryDecoder
from .rdm_validator import RdmValidator
from .response_correlator import ResponseCorrelator

if TYPE_CHECKING:
    from ..transaction.allocator import TransactionNumberAllocator


class ProtocolTimeoutError(Exception):
    """Raised when protocol operation times out."""


class RDME120Protocol:
    """RDM E1.20 protocol implementation."""

    _CONTROLLER_PORT_ID = 1
    _SERIAL_DESTINATION = ""

    def __init__(
        self,
        transport: AsyncTransport,
        source_uid: UID,
        *,
        encoder: PacketEncoder | None = None,
        decoder: PacketDecoder | None = None,
        correlator: ResponseCorrelator | None = None,
        validator: RdmValidator | None = None,
        allocator: "TransactionNumberAllocator",
        validate_requests: bool = True,
        dmx_scheduler: DmxFrameScheduler | None = None,
        wire_lock: asyncio.Lock | None = None,
    ):
        self._transport = transport
        self._source_uid = source_uid
        self._encoder = encoder or PacketEncoder()
        self._decoder = decoder or PacketDecoder()
        self._correlator = correlator or ResponseCorrelator()
        self._validator = validator or RdmValidator()
        self._allocator = allocator
        self._manchester_decoder = ManchesterDiscoveryDecoder()
        self._validate_requests = validate_requests
        self._dmx_scheduler = dmx_scheduler
        self._logger = logging.getLogger(self.__class__.__name__)

        # State management
        self._receive_task: asyncio.Task | None = None
        self._running = False

        # Discovery queue for Manchester-encoded responses (bypasses correlator)
        self._discovery_queue: asyncio.Queue = asyncio.Queue()

        # RDM is half-duplex - only one request may be outstanding on the wire
        # at a time. Without this, concurrent callers (e.g. the API's
        # capability dashboard fetching many modules at once) interleave
        # sends, which real responders can't handle and which produces
        # garbled/misattributed responses and cascading timeouts. DMX output
        # shares the same physical wire, so callers that also transmit DMX
        # frames (e.g. NetworkManager's scheduler) must acquire this same
        # lock instance - pass it in via `wire_lock` instead of letting each
        # side create its own.
        self._wire_lock = wire_lock or asyncio.Lock()

    @property
    def source_uid(self) -> UID:
        """Return the controller UID placed in outgoing RDM requests."""
        return self._source_uid

    @property
    def wire_lock(self) -> asyncio.Lock:
        """Return the lock serializing all access to the shared half-duplex wire."""
        return self._wire_lock

    @property
    def correlator(self) -> ResponseCorrelator:
        """Return the correlator used to match responses to requests."""
        return self._correlator

    @property
    def allocator(self) -> "TransactionNumberAllocator":
        """Return the allocator used to issue transaction numbers."""
        return self._allocator

    @asynccontextmanager
    async def _dmx_paused(self, timeout: float):
        """Pause the attached DMX scheduler for the duration of an RDM wire op.

        No-op if no scheduler is attached. Resumes DMX immediately once the
        wrapped operation finishes, even on error/timeout/cancellation - it
        only pauses for up to `timeout` seconds as a safety bound.
        """
        pause_task: asyncio.Task | None = None
        if self._dmx_scheduler:
            pause_task = asyncio.create_task(self._dmx_scheduler.pause_for_rdm(timeout * 1000))
        try:
            yield
        finally:
            if pause_task and not pause_task.done():
                pause_task.cancel()

    async def start(self) -> None:
        """Start response correlation and the transport receive loop."""
        if self._running:
            return

        self._running = True

        # Start correlator
        await self._correlator.start()

        # Start receive loop
        self._receive_task = asyncio.create_task(self._receive_loop())

        self._logger.info("RDM protocol started")

    async def stop(self) -> None:
        """Stop background protocol tasks.

        Calling this method when the protocol is already stopped is safe.
        """
        if not self._running:
            return

        self._running = False

        # Cancel receive task
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        # Stop correlator
        await self._correlator.stop()

        self._logger.info("RDM protocol stopped")

    async def send_get_command(
        self,
        destination_uid: UID,
        pid: PID,
        transaction_number: TransactionNumber,
        data: bytes = b"",
        sub_device: int = 0,
        timeout: float = 1.0,
    ) -> RDMResponse:
        """Send an E1.20 GET command and await its response.

        Raises:
            ValueError: If request validation is enabled and the request is invalid.
            ProtocolTimeoutError: If no correlated response arrives before ``timeout``.
        """
        request = RDMRequest(
            destination_uid=destination_uid,
            source_uid=self._source_uid,
            transaction_number=transaction_number,
            port_address=self._CONTROLLER_PORT_ID,
            sub_device=sub_device,
            command_class=CommandClass.GET_COMMAND,
            pid=pid,
            data=data,
        )

        return await self._send_and_receive(request, timeout)

    async def send_set_command(
        self,
        destination_uid: UID,
        pid: PID,
        transaction_number: TransactionNumber,
        data: bytes,
        sub_device: int = 0,
        timeout: float = 1.0,
    ) -> RDMResponse:
        """Send an E1.20 SET command and await its response.

        Raises:
            ValueError: If request validation is enabled and the request is invalid.
            ProtocolTimeoutError: If no correlated response arrives before ``timeout``.
        """
        request = RDMRequest(
            destination_uid=destination_uid,
            source_uid=self._source_uid,
            transaction_number=transaction_number,
            port_address=self._CONTROLLER_PORT_ID,
            sub_device=sub_device,
            command_class=CommandClass.SET_COMMAND,
            pid=pid,
            data=data,
        )

        return await self._send_and_receive(request, timeout)

    async def send_discovery_command(
        self,
        destination_uid: UID,
        pid: PID,
        transaction_number: TransactionNumber,
        data: bytes = b"",
        timeout: float = 1.0,
    ) -> RDMResponse | None:
        """
        Send RDM discovery command (DISC_UNIQUE_BRANCH, DISC_MUTE, etc.).

        Only DISC_UNIQUE_BRANCH (0x0001) returns Manchester-encoded responses.
        DISC_MUTE (0x0002) and DISC_UN_MUTE (0x0003) return standard RDM packets.

        Args:
            destination_uid: Target UID (typically BROADCAST)
            pid: Parameter ID (DISC_UNIQUE_BRANCH, DISC_MUTE, etc.)
            transaction_number: Transaction number
            data: Parameter data (e.g., UID bounds for DUB)
            timeout: Response timeout

        Returns:
            RDMResponse with decoded UID, or None if a collision was detected
            (data was received but could not be Manchester-decoded)

        Raises:
            ProtocolTimeoutError: If no response was received at all within
                `timeout` (distinct from a collision - callers must treat
                these two cases differently, e.g. during binary-search
                discovery an empty branch must terminate, not split further)
        """
        request = RDMRequest(
            destination_uid=destination_uid,
            source_uid=self._source_uid,
            transaction_number=transaction_number,
            port_address=self._CONTROLLER_PORT_ID,
            sub_device=0,
            command_class=CommandClass.DISCOVERY_COMMAND,
            pid=pid,
            data=data,
        )

        # Check if this is DISC_UNIQUE_BRANCH (Manchester-encoded response)
        # PID 0x0001 = DISC_UNIQUE_BRANCH uses discovery queue
        # PID 0x0002 = DISC_MUTE uses correlator
        # PID 0x0003 = DISC_UN_MUTE uses correlator
        DISC_UNIQUE_BRANCH_PID = 0x0001

        if pid == DISC_UNIQUE_BRANCH_PID:
            # DISC_UNIQUE_BRANCH: Manchester-encoded response, use discovery queue
            packet_bytes = self._encoder.encode_rdm_request(request)

            try:
                async with self._wire_lock, self._dmx_paused(timeout):
                    await self._transport.send(packet_bytes, self._SERIAL_DESTINATION)

                    self._logger.debug("[DUB] Waiting for Manchester response...")
                    response_data = await asyncio.wait_for(self._discovery_queue.get(), timeout)

                # Decode Manchester to UID
                uid = self._manchester_decoder.decode(response_data)

                if uid:
                    # Valid UID decoded
                    uid_int = UID(int.from_bytes(uid, "big"))
                    self._logger.info("[DUB] Decoded UID: %s", uid.hex().upper())
                    return RDMResponse(
                        source_uid=uid_int,
                        destination_uid=self._source_uid,
                        transaction_number=transaction_number,
                        response_type=ResponseType.ACK,
                        message_count=0,
                        sub_device=0,
                        command_class=CommandClass.DISCOVERY_COMMAND_RESPONSE,
                        pid=pid,
                        data=b"",
                        checksum_valid=True,
                    )
                else:
                    # Collision (invalid Manchester decode)
                    self._logger.debug("[DUB] Collision detected")
                    return None

            except TimeoutError as exc:
                # True no-response: distinct from a collision, must not be
                # swallowed to None or callers can't tell "empty branch" from
                # "collision" (see discovery_service.discover_unique_branch)
                self._logger.debug("[DUB] Timeout - no response")
                raise ProtocolTimeoutError(
                    f"No discovery response for TXN {transaction_number} within {timeout}s"
                ) from exc
        else:
            # DISC_MUTE/DISC_UN_MUTE: Standard RDM response, use correlator
            return await self._send_and_receive(request, timeout)

    async def _send_and_receive(self, request: RDMRequest, timeout: float) -> RDMResponse:

        # Validate request if enabled
        if self._validate_requests:
            is_valid, error = self._validator.validate_request(request)
            if not is_valid:
                raise ValueError(f"Invalid RDM request: {error}")

        # Encode packet
        packet_bytes = self._encoder.encode_rdm_request(request)

        # Register handler with correlator
        future = self._correlator.register_handler(request.transaction_number)

        try:
            async with self._wire_lock, self._dmx_paused(timeout):
                # Send packet
                await self._transport.send(packet_bytes, self._SERIAL_DESTINATION)

                self._logger.debug(
                    f"[TX_RDM] Sent {request.command_class.name} "
                    f"TXN={request.transaction_number} "
                    f"PID={request.pid:#x} to UID={request.destination_uid:012X}"
                )

                # Wait for response
                response = await asyncio.wait_for(future, timeout=timeout)

            # Validate response matches request
            is_valid, error = self._validator.validate_request_response_match(request, response)
            if not is_valid:
                self._logger.warning(f"Response validation warning: {error}")

            self._logger.debug(
                f"[TX_RDM] Received response TXN={response.transaction_number} "
                f"type={response.response_type.name} (elapsed: {timeout:.2f}s max)"
            )

            return response

        except TimeoutError as exc:
            # Unregister handler on timeout
            self._correlator.unregister_handler(request.transaction_number)
            raise ProtocolTimeoutError(
                f"No response for TXN {request.transaction_number} within {timeout}s"
            ) from exc
        except Exception:
            # Unregister handler on error
            self._correlator.unregister_handler(request.transaction_number)
            raise

    async def _receive_loop(self) -> None:
        self._logger.debug("Receive loop started")

        try:
            while self._running:
                try:
                    # Receive packet with timeout
                    data, _ = await self._transport.receive(timeout=0.1)

                    self._logger.debug(
                        "[RX_LOOP] Received %d bytes: %s",
                        len(data),
                        " ".join(f"{b:02X}" for b in data[:12]),
                    )

                    # Check if this is Manchester-encoded discovery response
                    # Discovery responses start with preamble: 0xFE (0-7 bytes,
                    # widget/interface dependent) - never the start of a normal
                    # RDM response (0xCC), so a single leading 0xFE is enough
                    # to route it to the discovery queue.
                    if data[:1] == b"\xfe":
                        # Route Manchester data to discovery queue (bypass correlator)
                        await self._discovery_queue.put(data)
                        self._logger.debug(
                            "[DISCOVERY] Routed Manchester response to discovery queue"
                        )
                        continue

                    # Decode normal RDM packet
                    response = self._decoder.decode_rdm_response(data)

                    if response is None:
                        self._logger.debug("[RX_LOOP] Failed to decode response")
                        continue  # Not a valid RDM response

                    self._logger.debug(
                        f"[RX_RDM] Decoded response TXN={response.transaction_number} "
                        f"from UID={response.source_uid:012X} type={response.response_type.name} PID={response.pid:#x}"
                    )

                    # Validate response
                    is_valid, error = self._validator.validate_response(response)
                    if not is_valid:
                        self._logger.error("Invalid response received: %s", error)
                        continue

                    # Correlate with handler
                    correlated = self._correlator.correlate_response(response)

                    if not correlated:
                        self._logger.debug(
                            "Unsolicited response TXN=%d", response.transaction_number
                        )

                except TimeoutError:
                    continue  # Normal timeout, check if still running
                except PacketDecodeError as e:
                    self._logger.error("Failed to decode packet: %s", e)
                except Exception as e:
                    self._logger.error("Error in receive loop: %s", e, exc_info=True)

        except asyncio.CancelledError:
            self._logger.debug("Receive loop cancelled")
        finally:
            self._logger.debug("Receive loop stopped")

    @classmethod
    def create(cls, transport: AsyncTransport) -> "RDME120Protocol":
        """Create protocol with default source UID (454e:00000000)."""
        # Default source UID (can be configured)
        from ..packets.types import uid_from_string
        from ..transaction.allocator import TransactionNumberAllocator

        default_source_uid = uid_from_string("454e:00000000")
        return cls(transport, default_source_uid, allocator=TransactionNumberAllocator())
