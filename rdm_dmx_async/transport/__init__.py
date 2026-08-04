"""
Transport layer - handles low-level communication

Provides abstract interfaces and concrete implementations for:
- Serial transport (for direct RDM via Enttec, DMXKing, etc.)
- Interface adapters (support multiple hardware types)
"""

from .adapters import (
    BareUsbRs485Adapter,
    DMXKingAdapter,
    EnttecAdapter,
    EnttecMessageType,
    FramingMode,
    GenericSerialAdapter,
)
from .base import AsyncTransport, ConnectionFailedError, NotConnectedError, TransportError
from .interface_adapter import InterfaceAdapter, InterfaceType, SerialConfig
from .serial_transport import AsyncSerialTransport

__all__ = [
    "AsyncTransport",
    "TransportError",
    "NotConnectedError",
    "ConnectionFailedError",
    "AsyncSerialTransport",
    "SerialConfig",
    "InterfaceAdapter",
    "InterfaceType",
    "EnttecAdapter",
    "DMXKingAdapter",
    "GenericSerialAdapter",
    "FramingMode",
    "EnttecMessageType",
    "BareUsbRs485Adapter",
]
