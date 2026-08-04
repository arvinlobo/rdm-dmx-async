"""
Concrete hardware interface adapters, one module per hardware vendor/protocol.

Each adapter implements the `InterfaceAdapter` abstraction defined in
`transport.interface_adapter`. Splitting adapters into their own modules keeps
each hardware-specific implementation independently readable/testable and
means adding a new interface never requires touching an existing adapter's
file (Open/Closed Principle).
"""

from .dmxking import DMXKingAdapter
from .enttec import EnttecAdapter, EnttecMessageType
from .generic_serial import FramingMode, GenericSerialAdapter

__all__ = [
    "EnttecAdapter",
    "EnttecMessageType",
    "DMXKingAdapter",
    "GenericSerialAdapter",
    "FramingMode",
]
