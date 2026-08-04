"""
Utility functions for RDM communication.
"""

import asyncio
import logging

import serial

from .packets.types import UID, uid_from_bytes
from .transport.adapters import EnttecAdapter
from .transport.interface_adapter import InterfaceAdapter

logger = logging.getLogger(__name__)

# Retrying writes/reads on the SAME open handle does not help - real-world
# testing showed 3 attempts on one handle all failing, then a brand new
# port open (close + reopen) succeeding immediately. So each attempt below
# does a full close/reopen cycle, with a settle delay after each open to
# let the widget's USB-serial chip recover from the DTR/RTS reset triggered
# by opening the port.
_PORT_SETTLE_SECONDS = 0.3
_WIDGET_QUERY_ATTEMPTS = 4
_REOPEN_BACKOFF_SECONDS = 0.5


def _query_widget_serial_once(
    port: str, baudrate: int, timeout: float, adapter: InterfaceAdapter
) -> bytes | None:
    """Open the port once, request the widget serial number, and return the raw response."""
    ser = serial.Serial(port=port, baudrate=baudrate, timeout=timeout)
    try:
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        request = adapter.get_widget_serial_request()
        ser.write(request)
        logger.debug(f"Sent Enttec serial request: {request.hex(' ')}")

        return ser.read(100)  # Read up to 100 bytes
    finally:
        ser.close()


async def get_enttec_serial_uid(
    port: str, baudrate: int = 250000, timeout: float = 1.0, adapter: InterfaceAdapter | None = None
) -> UID | None:
    """
    Query Enttec device for its serial number and construct UID.

    Args:
        port: Serial port (e.g., "COM3")
        baudrate: Baud rate (default 250000)
        timeout: Timeout in seconds
        adapter: Interface adapter (creates default Enttec adapter if None)

    Returns:
        UID constructed from Enttec manufacturer ID (0x454E) + serial number,
        or None if failed

    Example:
        uid = await get_enttec_serial_uid("COM3")
        # Returns UID like 0x454E02192718
    """
    if adapter is None:
        adapter = EnttecAdapter(port)

    for attempt in range(1, _WIDGET_QUERY_ATTEMPTS + 1):
        try:
            await asyncio.sleep(_PORT_SETTLE_SECONDS)
            response = await asyncio.to_thread(
                _query_widget_serial_once, port, baudrate, timeout, adapter
            )

            if not response:
                logger.warning(
                    f"No response from Enttec on {port} (attempt {attempt}/"
                    f"{_WIDGET_QUERY_ATTEMPTS})"
                )
                await asyncio.sleep(_REOPEN_BACKOFF_SECONDS)
                continue

            logger.debug(f"Received: {response.hex(' ')}")

            serial_bytes = adapter.parse_widget_serial_response(response)

            if serial_bytes and len(serial_bytes) == 4:
                # Enttec serial is little-endian, reverse for UID
                serial_bytes_reversed = bytes(reversed(serial_bytes))
                # Enttec UID = 0x454E (manufacturer) + serial (MSB first)
                uid_bytes = bytes([0x45, 0x4E]) + serial_bytes_reversed
                uid = uid_from_bytes(uid_bytes)
                logger.info(
                    f"Enttec serial UID: {uid:012X} (serial bytes: {serial_bytes.hex(' ')})"
                )
                return uid

            logger.warning(f"Invalid serial number response from Enttec (attempt {attempt})")
            await asyncio.sleep(_REOPEN_BACKOFF_SECONDS)

        except Exception as e:
            logger.error(f"Failed to get Enttec serial number (attempt {attempt}): {e}")
            await asyncio.sleep(_REOPEN_BACKOFF_SECONDS)

    logger.error(f"No response from Enttec on {port} after {_WIDGET_QUERY_ATTEMPTS} attempts")
    return None


async def get_enttec_widget_params(
    port: str, baudrate: int = 250000, timeout: float = 1.0, adapter: InterfaceAdapter | None = None
) -> dict | None:
    """
    Query Enttec widget parameters (firmware version, DMX settings).

    Args:
        port: Serial port
        baudrate: Baud rate
        timeout: Timeout in seconds
        adapter: Interface adapter (creates default Enttec adapter if None)

    Returns:
        Dictionary with widget parameters or None if failed:
        {
            'firmware_version': str,          # e.g., "2.4"
            'firmware_version_lsb': int,      # LSB of firmware version
            'firmware_version_msb': int,      # MSB of firmware version
            'dmx_break_time': int,            # in 10.67μs units
            'dmx_mab_time': int,              # in 10.67μs units
            'dmx_refresh_rate': int           # Hz (0=fastest)
        }
    """
    if adapter is None:
        adapter = EnttecAdapter(port)

    try:
        # Use raw serial communication for Enttec commands
        ser = serial.Serial(port=port, baudrate=baudrate, timeout=timeout)

        try:
            # Flush buffers
            ser.reset_input_buffer()
            ser.reset_output_buffer()

            # Request widget parameters using adapter
            request = adapter.get_widget_params_request()

            ser.write(request)
            logger.debug(f"Sent Enttec params request: {request.hex(' ')}")

            # Read response with timeout
            response = ser.read(100)  # Read up to 100 bytes

            if not response:
                logger.error(f"No response from Enttec on {port}")
                return None

            logger.debug(f"Received: {response.hex(' ')}")

            # Parse response using adapter
            params = adapter.parse_widget_params_response(response)

            if params:
                logger.info(
                    f"Enttec widget: FW {params['firmware_version']}, "
                    f"Break={params['dmx_break_time']}×10.67μs, "
                    f"MAB={params['dmx_mab_time']}×10.67μs, "
                    f"Rate={params['dmx_refresh_rate']}Hz"
                )
                return params

            logger.error("Invalid widget parameters response from Enttec")
            return None

        finally:
            ser.close()

    except Exception as e:
        logger.error(f"Failed to get widget parameters: {e}")
        return None


def list_available_ports() -> list[str]:
    """
    List available serial ports on the system.

    Returns:
        List of port names (e.g., ["COM3", "COM4"])
    """
    try:
        import serial.tools.list_ports

        ports = [port.device for port in serial.tools.list_ports.comports()]
        return ports
    except ImportError:
        logger.warning("pyserial not installed, cannot list ports")
        return []


def find_enttec_port() -> str | None:
    """
    Automatically find the first available ENTTEC device.

    Returns:
        Port name (e.g., "COM3") or None if not found

    Example:
        port = find_enttec_port()
        if port:
            print(f"Found ENTTEC on {port}")
    """
    try:
        import serial.tools.list_ports

        ports = serial.tools.list_ports.comports()

        for port in ports:
            # Check for ENTTEC vendor ID (0x0403 for FTDI-based Enttec devices)
            # and product ID (0x6001 for ENTTEC USB PRO)
            if port.vid == 0x0403:
                logger.info("Found ENTTEC device on %s", port.device)
                return port.device

        logger.warning("No ENTTEC devices found")
        return None

    except ImportError:
        logger.warning("pyserial not installed, cannot find ENTTEC port")
        return None
