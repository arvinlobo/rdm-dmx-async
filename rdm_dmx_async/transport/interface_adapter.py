"""
Interface adapter abstraction for different hardware interfaces.

This module provides the adapter pattern to support multiple hardware
interfaces (Enttec, DMXKing, etc.) without changing the core
transport or protocol layers.

Concrete adapter implementations live under `transport.adapters` (one module
per hardware vendor/protocol) so that adding new hardware never requires
touching this file or any other adapter.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum

from serial import EIGHTBITS, PARITY_NONE, STOPBITS_ONE


@dataclass
class SerialConfig:
    """
    Generic serial port configuration.

    Defaults are common for most serial devices (9600 baud, 8N1).
    Use adapter-specific factory methods for protocol requirements.
    """

    port: str  # COM port (e.g., "COM3" on Windows, "/dev/ttyUSB0" on Linux)
    baudrate: int = 9600  # Common default for generic serial
    bytesize: int = EIGHTBITS
    parity: str = PARITY_NONE
    stopbits: int = STOPBITS_ONE  # Standard for most serial devices
    timeout: float = 0.1
    write_timeout: float = 1.0
    buffer_size: int = 1024
    queue_maxsize: int = 100


class InterfaceType(StrEnum):
    """Supported hardware interface types"""

    ENTTEC_USB_PRO = "enttec_usb_pro"
    DMXKING_ULTRA_DMX = "dmxking_ultra_dmx"
    GENERIC_SERIAL = "generic_serial"
    BARE_USB_RS485 = "bare_usb_rs485"
    CUSTOM = "custom"


class InterfaceAdapter(ABC):
    """
    Abstract base class for hardware interface adapters.

    Each hardware interface (Enttec, DMXKing, etc.) has its own protocol
    for framing RDM packets. This adapter pattern allows the transport
    layer to remain generic while supporting multiple interfaces.

    Responsibilities:
    - Frame RDM data in hardware-specific format
    - Parse responses from hardware-specific format
    - Handle hardware-specific message types and quirks
    """

    @property
    @abstractmethod
    def interface_type(self) -> InterfaceType:
        """Return the interface type this adapter supports"""
        pass

    @property
    @abstractmethod
    def serial_config(self) -> SerialConfig:
        """Return serial configuration for this adapter"""
        pass

    @property
    def requires_manual_break(self) -> bool:
        """
        Whether the transport must manually toggle the UART break condition
        before writing each frame.

        Purpose-built widgets (Enttec, DMXKing) generate the DMX BREAK/MAB
        signal in their own firmware, so this is False for them. Bare
        USB-RS485 dongles with no onboard framing rely on
        the host toggling `Serial.break_condition` to produce the BREAK
        signal on the wire - see `AsyncSerialTransport._tx_loop`.
        """
        return False

    @abstractmethod
    def frame_rdm_request(self, rdm_data: bytes, port: int = 1) -> bytes:
        """
        Frame RDM data for transmission through this interface.

        Args:
            rdm_data: Raw RDM packet bytes (already encoded)
            port: Physical port number (for multi-port interfaces)

        Returns:
            Framed bytes ready to send to hardware
        """
        pass

    @abstractmethod
    def frame_rdm_discovery_request(self, rdm_data: bytes, port: int = 1) -> bytes:
        """
        Frame RDM Discovery Request for transmission.

        Some interfaces (like ENTTEC USB Pro with RDM firmware) use a different
        message type for discovery requests vs regular RDM requests.

        Args:
            rdm_data: Raw RDM discovery packet bytes (DISC_UNIQUE_BRANCH)
            port: Physical port number (for multi-port interfaces)

        Returns:
            Framed bytes ready to send to hardware
        """
        pass

    @abstractmethod
    def parse_rdm_response(self, raw_data: bytes) -> bytes | None:
        """
        Parse RDM response from hardware-specific format.

        Args:
            raw_data: Raw bytes received from hardware

        Returns:
            Extracted RDM packet bytes, or None if not an RDM response
        """
        pass

    @abstractmethod
    def find_frame_length(self, buffer: bytes) -> int:
        """
        Determine frame length in buffer for this hardware's protocol.

        Args:
            buffer: Byte buffer potentially containing a frame

        Returns:
            Number of bytes in the frame, or 0 if cannot determine
        """
        pass

    @abstractmethod
    def frame_dmx_output(self, dmx_data: bytes, port: int = 1) -> bytes:
        """
        Frame DMX512 output data for transmission.

        Args:
            dmx_data: DMX universe data (up to 512 channels, values 0-255)
            port: Physical port number (for multi-port interfaces)

        Returns:
            Framed bytes ready to send to hardware
        """
        pass
