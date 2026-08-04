"""
Adapter for Enttec USB Pro and USB Pro Mk2 interfaces.
"""

import logging
from enum import IntEnum

from serial import EIGHTBITS, PARITY_NONE, STOPBITS_TWO

from ..interface_adapter import InterfaceAdapter, InterfaceType, SerialConfig

logger = logging.getLogger(__name__)


class EnttecMessageType(IntEnum):
    """
    Enttec USB Pro message types (API v1.44).

    See ENTTEC DMX USB PRO API documentation for details.
    """

    REPROGRAM_FIRMWARE = 1  # Request firmware reprogramming
    PROGRAM_FLASH_PAGE = 2  # Program firmware flash page
    GET_WIDGET_PARAMS = 3  # Get widget parameters
    SET_WIDGET_PARAMS = 4  # Set widget parameters
    RECEIVED_DMX_PACKET = 5  # Received DMX or RDM packet
    OUTPUT_ONLY_SEND_DMX = 6  # Send DMX packet (output only mode)
    SEND_RDM_PACKET = 7  # Send RDM packet (regular RDM requests)
    RECEIVE_DMX_ON_CHANGE = 8  # Configure receive on change mode
    RECEIVED_DMX_CHANGE_OF_STATE = 9  # Received DMX change of state
    GET_WIDGET_SERIAL_NUMBER = 10  # Get widget serial number
    SEND_RDM_DISCOVERY = 11  # Send RDM Discovery Request (DISC_UNIQUE_BRANCH)


class EnttecAdapter(InterfaceAdapter):
    """
    Adapter for Enttec USB Pro and USB Pro Mk2 interfaces.

    Protocol (API v1.44):
    - START: 0x7E
    - Label: 1 byte (message type)
    - Data Length: 2 bytes (LSB first, max 600)
    - Data: N bytes
    - END: 0xE7

    Firmware Versions:
    - Version 1 (MSB=1): Normal DMX firmware (no RDM support)
    - Version 2 (MSB=2): RDM firmware (controller/responder)
    - Version 3 (MSB=3): RDM Sniffer firmware

    Key differences:
    - USB Pro (RDM fw): Uses label 7 for regular RDM, label 11 for discovery
    - USB Pro Mk2: Uses label 7 for all RDM, responds with label 5 (includes port byte)

    For received packets (label 5):
    - First byte is status: 0=valid, nonzero=error (bit 0=queue overflow, bit 1=overrun)
    - Following bytes are DMX/RDM data (start code + data)
    """

    START_OF_MESSAGE = 0x7E
    END_OF_MESSAGE = 0xE7

    def __init__(self, port: str, use_mk2_protocol: bool = True):
        """
        Initialize Enttec adapter.

        Args:
            port: COM port (e.g., "COM3" on Windows, "/dev/ttyUSB0" on Linux)
            use_mk2_protocol: True for USB Pro Mk2, False for original USB Pro
        """
        self._port = port
        self._use_mk2 = use_mk2_protocol
        self._logger = logger

    @property
    def serial_config(self) -> SerialConfig:
        """
        Get serial configuration for DMX/RDM communication.

        DMX512-A requires: 250000 baud, 8 data bits, no parity, 2 stop bits (8N2)
        """
        return SerialConfig(
            port=self._port,
            baudrate=250000,
            bytesize=EIGHTBITS,
            parity=PARITY_NONE,
            stopbits=STOPBITS_TWO,
        )

    @property
    def interface_type(self) -> InterfaceType:
        """Return the ENTTEC USB Pro variant configured for this adapter."""
        return InterfaceType.ENTTEC_USB_PRO_MK2 if self._use_mk2 else InterfaceType.ENTTEC_USB_PRO

    def frame_rdm_request(self, rdm_data: bytes, port: int = 1) -> bytes:
        """
        Frame regular RDM request (not discovery).

        Both USB Pro and Mk2 use message type 7 for regular RDM.
        Mk2 does not include port byte; original USB Pro may support it.
        """
        # Message type 7 for regular RDM requests
        message_type = EnttecMessageType.SEND_RDM_PACKET

        # Both use same format for type 7 (no port byte in data)
        data = rdm_data

        framed = self._frame_message(message_type, data)

        self._logger.debug(
            f"[ENTTEC_FRAME_RDM] Type={message_type}, "
            f"RDM_len={len(rdm_data)}, Frame_len={len(framed)}"
        )
        return framed

    def frame_rdm_discovery_request(self, rdm_data: bytes, port: int = 1) -> bytes:
        """
        Frame RDM Discovery Request (DISC_UNIQUE_BRANCH, DISC_MUTE, DISC_UN_MUTE).

        Both USB Pro (RDM firmware) and USB Pro Mk2 use message type 11
        specifically for discovery requests to receive the special discovery
        response format (which has no break).
        """
        # ALWAYS use label 11 for discovery packets
        message_type = EnttecMessageType.SEND_RDM_DISCOVERY
        data = rdm_data
        framed = self._frame_message(message_type, data)

        self._logger.debug(
            f"[ENTTEC_FRAME_DISC] Type={message_type}, "
            f"RDM_len={len(rdm_data)}, Frame_len={len(framed)}"
        )
        return framed

    def parse_rdm_response(self, raw_data: bytes) -> bytes | None:
        """
        Parse RDM response from Enttec format.

        Both USB Pro and Mk2 return message type 5 (RECEIVED_DMX_PACKET) for RDM responses.
        Format of message type 5:
        - Byte 0: Status (0=valid, nonzero=error)
        - Bytes 1+: DMX/RDM data (start code + payload)

        For Mk2, there may be an additional port byte before status.
        """
        self._logger.info(f"[PARSE_CALL] Called with {len(raw_data)} bytes")

        if len(raw_data) < 5:  # START + LABEL + LEN(2) + END
            self._logger.info("[PARSE_CALL] Too short")
            return None

        if raw_data[0] != self.START_OF_MESSAGE:
            self._logger.info(f"[PARSE_CALL] Bad start: 0x{raw_data[0]:02X}")
            return None

        message_type = raw_data[1]
        data_len = raw_data[2] | (raw_data[3] << 8)

        # Check if we have enough bytes for this frame
        frame_len = 5 + data_len  # START + LABEL + LEN(2) + DATA + END
        if len(raw_data) < frame_len:
            self._logger.info(
                f"[PARSE_CALL] Incomplete frame: need {frame_len}, have {len(raw_data)}"
            )
            return None

        # Check END marker at correct position
        if raw_data[frame_len - 1] != self.END_OF_MESSAGE:
            self._logger.info(
                f"[PARSE_CALL] Bad end at position {frame_len - 1}: 0x{raw_data[frame_len - 1]:02X}"
            )
            return None

        self._logger.info(f"[PARSE_CALL] message_type=0x{message_type:02X}, data_len={data_len}")
        data_len = raw_data[2] | (raw_data[3] << 8)
        data = raw_data[4 : 4 + data_len]

        # Message type 5: Received DMX Packet (used for RDM responses)
        if message_type == EnttecMessageType.RECEIVED_DMX_PACKET:
            if len(data) < 2:  # Need at least status + start code
                return None

            # Check if this is a discovery response (Manchester-encoded collision data)
            # Discovery responses start with preamble: 0xFE 0xFE 0xFE...
            # They use original format (status+data) even on Mk2
            is_discovery_response = len(data) >= 4 and data[1:4] == b"\xfe\xfe\xfe"

            # Check if this is a standard RDM response (starts with 0x00 0xCC pattern)
            # MUTE/UNMUTE responses use original format: status(0x00) + RDM(0xCC...)
            # This is NOT Mk2 format (which would be port + status + RDM)
            is_standard_rdm = len(data) >= 2 and data[0] == 0x00 and data[1] == 0xCC

            # Check if this looks like Mk2 format (port byte + status + data)
            # or original format (status + data)
            if (
                self._use_mk2
                and len(data) > 2
                and not is_discovery_response
                and not is_standard_rdm
            ):
                # Mk2: First byte is port, second is status
                port_byte = data[0]
                status_byte = data[1]
                rdm_data = data[2:]

                if status_byte != 0:
                    self._logger.warning(
                        f"[ENTTEC_PARSE] RX error status: 0x{status_byte:02X} "
                        f"(overflow={bool(status_byte & 0x01)}, "
                        f"overrun={bool(status_byte & 0x02)})"
                    )

                self._logger.debug(
                    f"[ENTTEC_PARSE] Type=5 (Mk2), Port={port_byte}, "
                    f"Status={status_byte}, RDM_len={len(rdm_data)}"
                )
                self._logger.info(
                    f"[ENTTEC_PARSE] Returning RDM data: {' '.join(f'{b:02X}' for b in rdm_data)}"
                )
                return rdm_data
            else:
                # Original USB Pro OR discovery response: First byte is status
                status_byte = data[0]
                rdm_data = data[1:]

                if status_byte != 0:
                    self._logger.warning(f"[ENTTEC_PARSE] RX error status: 0x{status_byte:02X}")

                parse_type = "Discovery" if is_discovery_response else "Original"
                self._logger.debug(
                    f"[ENTTEC_PARSE] Type=5 ({parse_type}), "
                    f"Status={status_byte}, RDM_len={len(rdm_data)}"
                )
                self._logger.info(
                    f"[ENTTEC_PARSE] Returning RDM data: {' '.join(f'{b:02X}' for b in rdm_data)}"
                )
                return rdm_data
        else:
            # Log unrecognized message types for debugging
            self._logger.debug(
                f"[ENTTEC_PARSE] Unhandled message type: {message_type} "
                f"(hex 0x{message_type:02X}), data_len={data_len}"
            )

        return None

    def frame_dmx_output(self, dmx_data: bytes, port: int = 1) -> bytes:
        """
        Frame DMX512 output data (message type 6).

        Enttec USB Pro uses message type 6 (OUTPUT_ONLY_SEND_DMX) to send
        DMX data to the output. Data format:
        - Byte 0: Start code (0x00 for standard DMX)
        - Bytes 1-512: DMX channel values

        Args:
            dmx_data: DMX channel values (1-512 bytes, values 0-255)
            port: Physical port number (for multi-port interfaces)

        Returns:
            Framed bytes ready to send to hardware
        """
        # Validate DMX data length
        if len(dmx_data) < 1 or len(dmx_data) > 512:
            raise ValueError(f"DMX data must be 1-512 bytes, got {len(dmx_data)}")

        # Message type 6 for DMX output
        message_type = EnttecMessageType.OUTPUT_ONLY_SEND_DMX

        # Format: start code (0x00) + DMX data
        data = bytes([0x00]) + dmx_data

        framed = self._frame_message(message_type, data)

        self._logger.debug(
            f"[ENTTEC_FRAME_DMX] Type={message_type}, "
            f"Channels={len(dmx_data)}, Frame_len={len(framed)}"
        )
        return framed

    def find_frame_length(self, buffer: bytes) -> int:
        """
        Determine Enttec frame length in buffer.

        Enttec frame structure:
        START(1) + LABEL(1) + LEN_LSB(1) + LEN_MSB(1) + DATA(len) + END(1)

        Returns:
            Number of bytes in the complete frame, or 0 if cannot determine
        """
        if len(buffer) < 5:
            return 0

        if buffer[0] == self.START_OF_MESSAGE:
            data_len = buffer[2] | (buffer[3] << 8)
            frame_len = 5 + data_len  # START + LABEL + LEN(2) + DATA + END

            if len(buffer) >= frame_len and buffer[frame_len - 1] == self.END_OF_MESSAGE:
                return frame_len

        return 0

    def get_widget_params_request(self) -> bytes:
        """
        Create request to get widget parameters (label=3).

        Request format:
        - Data: 2 bytes (LSB, MSB) for user config size (usually 0x00 0x00)
        """
        # Request with 0 user config size
        data = bytes([0x00, 0x00])
        return self._frame_message(EnttecMessageType.GET_WIDGET_PARAMS, data)

    def parse_widget_params_response(self, raw_data: bytes) -> dict | None:
        """
        Parse widget parameters response (label=3).

        Response format:
        - Byte 0: Firmware version LSB
        - Byte 1: Firmware version MSB
        - Byte 2: DMX break time (10.67μs units, range 9-127)
        - Byte 3: DMX MAB time (10.67μs units, range 1-127)
        - Byte 4: DMX rate (packets/sec, range 1-40, or 0=fastest)
        - Bytes 5+: User config data (if any)
        """
        if len(raw_data) < 5:
            return None

        if raw_data[0] != self.START_OF_MESSAGE or raw_data[-1] != self.END_OF_MESSAGE:
            return None

        message_type = raw_data[1]
        if message_type != EnttecMessageType.GET_WIDGET_PARAMS:
            return None

        data_len = raw_data[2] | (raw_data[3] << 8)
        data = raw_data[4 : 4 + data_len]

        if len(data) >= 5:
            fw_lsb = data[0]
            fw_msb = data[1]
            dmx_break = data[2]
            dmx_mab = data[3]
            dmx_rate = data[4]

            return {
                "firmware_version_lsb": fw_lsb,
                "firmware_version_msb": fw_msb,
                "firmware_version": f"{fw_msb}.{fw_lsb}",
                "dmx_break_time": dmx_break,  # units of 10.67μs
                "dmx_mab_time": dmx_mab,  # units of 10.67μs
                "dmx_refresh_rate": dmx_rate,  # packets/sec
            }

        return None

    def get_widget_serial_request(self) -> bytes:
        """
        Create request to get widget serial number (label=10).

        Request has no data.
        """
        return self._frame_message(EnttecMessageType.GET_WIDGET_SERIAL_NUMBER, b"")

    def parse_widget_serial_response(self, raw_data: bytes) -> bytes | None:
        """
        Parse widget serial number response (label=10).

        Response format:
        - 4 bytes: BCD serial number (LSB at lowest address)
        - On old widgets: 0xFFFFFFFF if not programmed

        Returns:
            4-byte serial number (little-endian), or None if invalid
        """
        if len(raw_data) < 5:
            return None

        if raw_data[0] != self.START_OF_MESSAGE or raw_data[-1] != self.END_OF_MESSAGE:
            return None

        message_type = raw_data[1]
        if message_type != EnttecMessageType.GET_WIDGET_SERIAL_NUMBER:
            return None

        data_len = raw_data[2] | (raw_data[3] << 8)
        data = raw_data[4 : 4 + data_len]

        if len(data) == 4:
            # Check for unprogrammed serial
            if data == b"\xff\xff\xff\xff":
                self._logger.warning("Widget serial number not programmed")
                return None

            return data  # Return 4 bytes as-is (little-endian)

        return None

    def _frame_message(self, message_type: EnttecMessageType, data: bytes) -> bytes:
        """
        Frame a message in Enttec format.

        Format: START + LABEL + LEN_LSB + LEN_MSB + DATA + END

        Args:
            message_type: Message type (label)
            data: Data bytes (max 600 bytes)

        Returns:
            Complete framed message
        """
        data_len = len(data)
        if data_len > 600:
            raise ValueError(f"Data length {data_len} exceeds max 600 bytes")

        data_len_lsb = data_len & 0xFF
        data_len_msb = (data_len >> 8) & 0xFF

        return (
            bytes([self.START_OF_MESSAGE, message_type, data_len_lsb, data_len_msb])
            + data
            + bytes([self.END_OF_MESSAGE])
        )
