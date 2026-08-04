"""
rdm_dmx_async - Modern async-first library for RDM and DMX protocols

This library provides a clean, type-safe, and performant implementation of:
- RDM (Remote Device Management) E1.20 protocol
- DMX512-A protocol

Key features:
- Native async/await throughout (no thread pools)
- Full type hints for type safety
- Layered architecture with clear separation of concerns
- Comprehensive error handling
- High performance with efficient concurrency
"""

__version__ = "1.0.0-alpha"
__author__ = "Arvin Lobo"

# Core types
# Application layer
from .application.network_manager import NetworkConfig, NetworkManager

# Domain layer
from .domain.parameters import BROADCAST_UID, StandardPID
from .packets.decoder import PacketDecodeError, PacketDecoder
from .packets.encoder import PacketEncoder

# Packet structures
from .packets.rdm import RDMDiscoveryResponse, RDMRequest, RDMResponse
from .packets.types import (
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

# Protocol layer
from .protocols.rdm_e120 import ProtocolTimeoutError, RDME120Protocol
from .protocols.rdm_validator import RdmValidator, ValidationError
from .protocols.response_correlator import ResponseCorrelator

# Scheduling layer
from .scheduling import (
    DmxFrameScheduler,
    RdmRequestWindow,
)

# Service layer
from .services import (
    CachedParameter,
    DeviceRepository,
    DeviceState,
    DiscoveryService,
    RdmDevice,
)

# Transaction layer
from .transaction import (
    AGGRESSIVE_RETRY_POLICY,
    NO_RETRY_POLICY,
    STANDARD_POLICY,
    AsyncTransaction,
    RetryPolicy,
    TransactionNumberAllocator,
    TransactionResult,
    TransactionState,
)
from .transport.adapters import DMXKingAdapter, EnttecAdapter
from .transport.base import AsyncTransport
from .transport.interface_adapter import InterfaceAdapter, InterfaceType, SerialConfig

# Transport layer
from .transport.serial_transport import AsyncSerialTransport

# Utilities
from .utils import (
    find_enttec_port,
    get_enttec_serial_uid,
    get_enttec_widget_params,
    list_available_ports,
)

__all__ = [
    # Version
    "__version__",
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
    "PacketEncoder",
    "PacketDecoder",
    "PacketDecodeError",
    # Transport
    "AsyncTransport",
    "AsyncSerialTransport",
    "SerialConfig",
    "InterfaceAdapter",
    "InterfaceType",
    "EnttecAdapter",
    "DMXKingAdapter",
    # Protocols
    "RDME120Protocol",
    "ProtocolTimeoutError",
    "ResponseCorrelator",
    "RdmValidator",
    "ValidationError",
    # Scheduling
    "DmxFrameScheduler",
    "RdmRequestWindow",
    # Transaction
    "AsyncTransaction",
    "TransactionNumberAllocator",
    "RetryPolicy",
    "STANDARD_POLICY",
    "NO_RETRY_POLICY",
    "AGGRESSIVE_RETRY_POLICY",
    "TransactionResult",
    "TransactionState",
    # Domain
    "StandardPID",
    "BROADCAST_UID",
    # Services
    "RdmDevice",
    "DeviceState",
    "CachedParameter",
    "DeviceRepository",
    "DiscoveryService",
    # Application
    "NetworkManager",
    "NetworkConfig",
    # Utilities
    "get_enttec_serial_uid",
    "get_enttec_widget_params",
    "list_available_ports",
    "find_enttec_port",
]
