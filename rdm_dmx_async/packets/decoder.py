"""
RDM packet decoder.

Parses RDM response packets from wire format bytes.
"""

import logging
import struct

from .rdm import RDMResponse
from .types import (
    PID,
    CommandClass,
    ResponseType,
    StartCode,
    TransactionNumber,
    uid_from_bytes,
)


class PacketDecodeError(Exception):
    """Raised when packet decoding fails"""

    pass


class PacketDecoder:
    """
    Decodes RDM responses from wire format.

    Thread-safe and stateless - can be shared.
    """

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)

    def decode_rdm_response(self, data: bytes) -> RDMResponse | None:
        """
        Decode RDM response packet.

        Returns None if packet is not valid RDM response.
        Raises PacketDecodeError for malformed packets.
        """
        if len(data) < 26:  # Minimum RDM packet size (24-byte header + 2-byte checksum, PDL=0)
            return None

        # Check start code
        if data[0] != StartCode.RDM:
            return None

        # Check sub-start code
        if data[1] != 0x01:
            self._logger.warning(f"Invalid sub-start code: {data[1]:#x}")
            return None

        try:
            # Parse header
            destination_uid = uid_from_bytes(data[3:9])
            source_uid = uid_from_bytes(data[9:15])
            transaction_number = TransactionNumber(data[15])
            response_type = ResponseType(data[16])
            message_count = data[17]
            sub_device = struct.unpack(">H", data[18:20])[0]
            command_class = CommandClass(data[20])
            pid = PID(struct.unpack(">H", data[21:23])[0])
            pdl = data[23]

            # Extract parameter data
            param_data = data[24 : 24 + pdl]

            # Extract checksum
            checksum_offset = 24 + pdl
            if len(data) < checksum_offset + 2:
                raise PacketDecodeError("Packet too short for checksum")

            received_checksum = struct.unpack(">H", data[checksum_offset : checksum_offset + 2])[0]

            # Validate checksum
            calculated_checksum = self._calculate_checksum(data[:checksum_offset])
            checksum_valid = received_checksum == calculated_checksum

            if not checksum_valid:
                self._logger.warning(
                    f"Checksum mismatch: received={received_checksum:#x}, "
                    f"calculated={calculated_checksum:#x}"
                )

            # Build response object
            return RDMResponse(
                source_uid=source_uid,
                destination_uid=destination_uid,
                transaction_number=transaction_number,
                response_type=response_type,
                message_count=message_count,
                sub_device=sub_device,
                command_class=command_class,
                pid=pid,
                data=param_data,
                checksum_valid=checksum_valid,
            )

        except (struct.error, ValueError, IndexError) as e:
            raise PacketDecodeError(f"Failed to decode RDM response: {e}") from e

    @staticmethod
    def _calculate_checksum(data: bytes) -> int:
        """Calculate RDM checksum"""
        return sum(data) & 0xFFFF
