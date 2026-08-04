"""Abstract protocol interface for the Device Service layer to depend on.

Per the Dependency Inversion Principle, higher layers (services, transaction
manager) should depend on this abstraction rather than the concrete
`RDME120Protocol` implementation. This also makes it possible to introduce
alternative protocol implementations (e.g. Art-Net RDM) without changing any
service-layer code.
"""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from ..packets.rdm import RDMResponse
from ..packets.types import PID, UID, TransactionNumber
from .response_correlator import ResponseCorrelator

if TYPE_CHECKING:
    from ..transaction.allocator import TransactionNumberAllocator


@runtime_checkable
class RdmProtocol(Protocol):
    """Structural interface implemented by RDM protocol classes (e.g. RDME120Protocol)."""

    @property
    def source_uid(self) -> UID:
        """Return the controller UID used as the source of requests."""
        ...

    @property
    def correlator(self) -> ResponseCorrelator:
        """Return the response correlator owned by the protocol."""
        ...

    @property
    def allocator(self) -> "TransactionNumberAllocator":
        """Return the protocol's transaction-number allocator."""
        ...

    async def start(self) -> None:
        """Start protocol background processing."""
        ...

    async def stop(self) -> None:
        """Stop protocol background processing and release its resources."""
        ...

    async def send_get_command(
        self,
        destination_uid: UID,
        pid: PID,
        transaction_number: TransactionNumber,
        data: bytes = b"",
        sub_device: int = 0,
        timeout: float = 1.0,
    ) -> RDMResponse:
        """Send a GET command and wait for its correlated response."""
        ...

    async def send_set_command(
        self,
        destination_uid: UID,
        pid: PID,
        transaction_number: TransactionNumber,
        data: bytes,
        sub_device: int = 0,
        timeout: float = 1.0,
    ) -> RDMResponse:
        """Send a SET command and wait for its correlated response."""
        ...

    async def send_discovery_command(
        self,
        destination_uid: UID,
        pid: PID,
        transaction_number: TransactionNumber,
        data: bytes = b"",
        timeout: float = 1.0,
    ) -> RDMResponse | None:
        """Send a discovery command.

        Returns:
            The decoded response, or ``None`` when no unique responder was
            detected.
        """
        ...
