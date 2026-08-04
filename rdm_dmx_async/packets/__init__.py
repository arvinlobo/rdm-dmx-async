"""
Packet layer - RDM and DMX packet encoding/decoding

Provides:
- Type-safe packet structures
- Encoding/decoding utilities
- Validation
"""

from .decoder import PacketDecodeError, PacketDecoder
from .encoder import PacketEncoder
from .rdm import RDMDiscoveryResponse, RDMRequest, RDMResponse
from .types import (
    PID,
    UID,
    CommandClass,
    NAKReason,
    ResponseType,
    TransactionNumber,
    uid_from_bytes,
    uid_from_string,
    uid_to_bytes,
    uid_to_string,
)

__all__ = [
    # Types
    "UID",
    "PID",
    "TransactionNumber",
    "CommandClass",
    "ResponseType",
    "NAKReason",
    "uid_from_bytes",
    "uid_to_bytes",
    "uid_from_string",
    "uid_to_string",
    # Packets
    "RDMRequest",
    "RDMResponse",
    "RDMDiscoveryResponse",
    # Encoder/Decoder
    "PacketEncoder",
    "PacketDecoder",
    "PacketDecodeError",
]
