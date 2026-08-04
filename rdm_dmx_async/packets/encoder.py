"""
RDM packet encoder.

Converts RDM request objects to wire format bytes.
"""

import logging
import struct

from .rdm import RDMRequest
from .types import StartCode, uid_to_bytes


class PacketEncoder:
    """
    Encodes RDM requests into wire format.

    Thread-safe and stateless - can be shared.
    """

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)

    @staticmethod
    def encode_rdm_request(request: RDMRequest) -> bytes:
        """
        Encode RDM request to bytes.

        Format (ANSI E1.20):
        - Start Code (0xCC)
        - Sub-Start Code (0x01)
        - Message Length (24 + PDL)
        - Destination UID (6 bytes)
        - Source UID (6 bytes)
        - Transaction Number
        - Port Address / Response Type
        - Message Count
        - Sub-Device (2 bytes)
        - Command Class
        - PID (2 bytes)
        - PDL (Parameter Data Length)
        - PD (Parameter Data, 0-231 bytes)
        - Checksum (2 bytes)
        """
        # Build packet without checksum
        packet = bytearray()

        # Start codes
        packet.append(StartCode.RDM)
        packet.append(0x01)  # Sub-start code

        # Message length
        packet.append(request.message_length)

        # UIDs
        packet.extend(uid_to_bytes(request.destination_uid))
        packet.extend(uid_to_bytes(request.source_uid))

        # Transaction number
        packet.append(int(request.transaction_number))

        # Port address (for requests, response type field is 0)
        packet.append(request.port_address)

        # Message count (0 for requests)
        packet.append(0)

        # Sub-device (2 bytes, big-endian)
        packet.extend(struct.pack(">H", request.sub_device))

        # Command class
        packet.append(request.command_class)

        # PID (2 bytes, big-endian)
        packet.extend(struct.pack(">H", int(request.pid)))

        # PDL (Parameter Data Length)
        packet.append(len(request.data))

        # PD (Parameter Data)
        packet.extend(request.data)

        # Calculate and append checksum
        checksum = PacketEncoder._calculate_checksum(packet)
        packet.extend(struct.pack(">H", checksum))

        return bytes(packet)

    @staticmethod
    def _calculate_checksum(data: bytes) -> int:
        """Calculate RDM checksum (16-bit sum of all bytes)"""
        return sum(data) & 0xFFFF
