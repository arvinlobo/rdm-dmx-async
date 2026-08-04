"""
RDM packet structures.

Immutable dataclasses for type-safe RDM packet representation.
"""

from dataclasses import dataclass

from .types import PID, UID, CommandClass, NAKReason, ResponseType, TransactionNumber


@dataclass(frozen=True)
class RDMRequest:
    """
    Immutable RDM request packet.

    All fields are validated at construction time.
    """

    destination_uid: UID
    source_uid: UID
    transaction_number: TransactionNumber
    port_address: int
    sub_device: int
    command_class: CommandClass
    pid: PID
    data: bytes = b""

    def __post_init__(self):
        """Validate fields after initialization"""
        if not (0 <= int(self.transaction_number) <= 255):
            raise ValueError(f"Transaction number must be 0-255, got {self.transaction_number}")

        if not (0 <= self.sub_device <= 0x0FFF):
            raise ValueError(f"Sub-device must be 0-4095, got {self.sub_device}")

        if len(self.data) > 231:
            raise ValueError(f"Data too long ({len(self.data)} bytes, max 231)")

    @property
    def message_length(self) -> int:
        """Calculate message length (SC to checksum, exclusive)"""
        return 24 + len(self.data)


@dataclass(frozen=True)
class RDMResponse:
    """
    Immutable RDM response packet.

    Represents a parsed response from a device.
    """

    source_uid: UID
    destination_uid: UID
    transaction_number: TransactionNumber
    response_type: ResponseType
    message_count: int
    sub_device: int
    command_class: CommandClass
    pid: PID
    data: bytes
    checksum_valid: bool

    @property
    def is_ack(self) -> bool:
        """Return whether this response is an ACK."""
        return self.response_type == ResponseType.ACK

    @property
    def is_nak(self) -> bool:
        """Return whether this response is a negative acknowledgement."""
        return self.response_type == ResponseType.NAK

    @property
    def is_ack_timer(self) -> bool:
        """Return whether the responder requested an ACK_TIMER delay."""
        return self.response_type == ResponseType.ACK_TIMER

    @property
    def nak_reason(self) -> NAKReason | None:
        """Get NAK reason code if this is a NAK response"""
        if self.is_nak and len(self.data) >= 2:
            reason_code = int.from_bytes(self.data[0:2], byteorder="big")
            try:
                return NAKReason(reason_code)
            except ValueError:
                return None
        return None

    @property
    def ack_timer_value(self) -> int | None:
        """Get estimated response time in ms if this is an ACK_TIMER"""
        if self.is_ack_timer and len(self.data) >= 2:
            return int.from_bytes(self.data[0:2], byteorder="big") * 100
        return None


@dataclass
class RDMDiscoveryResponse:
    """Discovery response (different format than standard RDM)"""

    uid: UID
    checksum_valid: bool
