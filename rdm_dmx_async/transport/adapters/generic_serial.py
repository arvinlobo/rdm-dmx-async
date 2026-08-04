"""
Generic serial adapter for simple, serial devices.
"""

from enum import StrEnum

from ..interface_adapter import InterfaceAdapter, InterfaceType, SerialConfig


class FramingMode(StrEnum):
    """Framing modes for generic serial adapter"""

    LINE_BASED = "line_based"  # Newline-terminated (\n or \r\n)
    LENGTH_PREFIX = "length_prefix"  # First byte = length
    DELIMITER = "delimiter"  # Custom delimiter byte
    RAW = "raw"  # Pass-through, no framing


class GenericSerialAdapter(InterfaceAdapter):
    """
    Generic serial adapter for simple serial devices.

    Supports common serial framing patterns:
    - LINE_BASED: Newline-terminated messages (default)
    - LENGTH_PREFIX: First byte indicates message length
    - DELIMITER: Custom delimiter byte
    - RAW: No framing, pass-through mode

    Example:
        # Line-based (Arduino, text protocols)
        adapter = GenericSerialAdapter("COM4", baudrate=115200, framing=FramingMode.LINE_BASED)

        # Length-prefixed (binary protocols)
        adapter = GenericSerialAdapter("COM5", framing=FramingMode.LENGTH_PREFIX)

        # Custom delimiter
        adapter = GenericSerialAdapter(
            "COM6",
            baudrate=19200,
            framing=FramingMode.DELIMITER,
            delimiter=b'\x00'  # Null-terminated
        )
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 9600,
        framing: FramingMode = FramingMode.LINE_BASED,
        delimiter: bytes = b"\n",
        max_frame_size: int = 1024,
    ):
        """
        Initialize generic serial adapter.

        Args:
            port: COM port (e.g., "COM3" on Windows, "/dev/ttyUSB0" on Linux)
            baudrate: Baud rate (default: 9600)
            framing: Framing mode (line, length-prefix, delimiter, raw)
            delimiter: Delimiter byte(s) for DELIMITER or LINE_BASED mode
            max_frame_size: Maximum frame size in bytes
        """
        self._port = port
        self._baudrate = baudrate
        self._framing = framing
        self._delimiter = delimiter
        self._max_frame_size = max_frame_size

    @property
    def serial_config(self) -> SerialConfig:
        """
        Get serial configuration for generic devices.

        Common presets:
        - 9600 baud (default): Most Arduino/embedded devices
        - 115200 baud: High-speed Arduino, modern devices
        - 19200/38400 baud: Industrial devices
        """
        return SerialConfig(port=self._port, baudrate=self._baudrate)

    @property
    def interface_type(self) -> InterfaceType:
        """Return the generic serial interface identifier."""
        return InterfaceType.GENERIC_SERIAL

    def frame_rdm_request(self, rdm_data: bytes, port: int = 1) -> bytes:
        """
        Frame data for transmission.

        Args:
            rdm_data: Data to frame
            port: Ignored for generic serial

        Returns:
            Framed data ready for transmission
        """
        if self._framing == FramingMode.RAW:
            return rdm_data

        elif self._framing == FramingMode.LINE_BASED:
            # Add newline if not present
            if not rdm_data.endswith(self._delimiter):
                return rdm_data + self._delimiter
            return rdm_data

        elif self._framing == FramingMode.LENGTH_PREFIX:
            # Prepend length byte
            length = len(rdm_data)
            if length > 255:
                raise ValueError(f"Data too long for length-prefix mode: {length} bytes")
            return bytes([length]) + rdm_data

        elif self._framing == FramingMode.DELIMITER:
            # Add delimiter if not present
            if not rdm_data.endswith(self._delimiter):
                return rdm_data + self._delimiter
            return rdm_data

        return rdm_data

    def frame_rdm_discovery_request(self, rdm_data: bytes, port: int = 1) -> bytes:
        """Same as regular request for generic serial"""
        return self.frame_rdm_request(rdm_data, port)

    def parse_rdm_response(self, raw_data: bytes) -> bytes | None:
        """
        Parse response from raw data.

        Args:
            raw_data: Raw bytes from serial port

        Returns:
            Extracted message, or None if incomplete
        """
        if self._framing == FramingMode.RAW:
            # Return all data as-is
            return raw_data if raw_data else None

        elif self._framing == FramingMode.LINE_BASED:
            # Check for delimiter
            if self._delimiter in raw_data:
                # Return data up to and including delimiter
                idx = raw_data.index(self._delimiter)
                return raw_data[: idx + len(self._delimiter)]
            return None

        elif self._framing == FramingMode.LENGTH_PREFIX:
            # Need at least 1 byte for length
            if len(raw_data) < 1:
                return None

            length = raw_data[0]
            total_len = 1 + length  # Length byte + data

            if len(raw_data) >= total_len:
                return raw_data[1:total_len]  # Return data without length byte
            return None

        elif self._framing == FramingMode.DELIMITER:
            # Check for delimiter
            if self._delimiter in raw_data:
                idx = raw_data.index(self._delimiter)
                return raw_data[:idx]  # Return data without delimiter
            return None

        return None

    def find_frame_length(self, buffer: bytes) -> int:
        """
        Determine frame length in buffer.

        Args:
            buffer: Byte buffer potentially containing a frame

        Returns:
            Number of bytes in the frame, or 0 if cannot determine
        """
        if self._framing == FramingMode.RAW:
            # Consume all available data
            return len(buffer)

        elif self._framing == FramingMode.LINE_BASED:
            # Find delimiter
            if self._delimiter in buffer:
                idx = buffer.index(self._delimiter)
                return idx + len(self._delimiter)
            return 0

        elif self._framing == FramingMode.LENGTH_PREFIX:
            if len(buffer) < 1:
                return 0

            length = buffer[0]
            total_len = 1 + length

            if len(buffer) >= total_len:
                return total_len
            return 0

        elif self._framing == FramingMode.DELIMITER:
            if self._delimiter in buffer:
                idx = buffer.index(self._delimiter)
                return idx + len(self._delimiter)
            return 0

        return 0

    def frame_dmx_output(self, dmx_data: bytes, port: int = 1) -> bytes:
        """
        Frame DMX output data using configured framing mode.

        Note: GenericSerialAdapter is not intended for DMX output.
        This method exists to satisfy the interface, but should not be used
        for actual DMX512 transmission. Use EnttecAdapter instead.

        Args:
            dmx_data: DMX channel values
            port: Ignored for generic serial

        Returns:
            Framed data using configured framing mode

        Raises:
            NotImplementedError: This adapter is not suitable for DMX output
        """
        raise NotImplementedError(
            "GenericSerialAdapter is not suitable for DMX512 output. "
            "Use EnttecAdapter or DMXKingAdapter for DMX transmission."
        )
