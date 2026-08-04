"""Validates RDM packets according to ANSI E1.20/E1.37 standards."""

import logging

from ..packets.rdm import RDMRequest, RDMResponse
from ..packets.types import PID, UID, CommandClass, ResponseType


class ValidationError(Exception):
    """Raised when RDM validation fails."""


class RdmValidator:
    """Validates RDM packets according to ANSI E1.20 and E1.37-1 standards."""

    # Constants from E1.20
    MAX_PDL = 231  # Maximum parameter data length
    MIN_MESSAGE_LENGTH = 24  # Minimum RDM message length
    MAX_SUB_DEVICE = 0x0FFF  # Maximum sub-device number (4095)
    BROADCAST_UID = UID(0xFFFFFFFFFFFF)
    BROADCAST_SUB_DEVICE = 0xFFFF

    # Maps a request command class to the command class its response must use.
    _EXPECTED_RESPONSE_COMMAND_CLASS = {
        CommandClass.DISCOVERY_COMMAND: CommandClass.DISCOVERY_COMMAND_RESPONSE,
        CommandClass.GET_COMMAND: CommandClass.GET_COMMAND_RESPONSE,
        CommandClass.SET_COMMAND: CommandClass.SET_COMMAND_RESPONSE,
    }

    def __init__(self, strict_mode: bool = False):
        self._strict_mode = strict_mode
        self._logger = logging.getLogger(self.__class__.__name__)

    def validate_request(self, request: RDMRequest) -> tuple[bool, str | None]:
        """Validate an outgoing request.

        Returns:
            A pair containing the validity flag and an error message when invalid.
        """
        # Validate UIDs
        if not self._is_valid_uid(request.destination_uid):
            return False, f"Invalid destination UID: {request.destination_uid:012X}"

        if not self._is_valid_uid(request.source_uid):
            return False, f"Invalid source UID: {request.source_uid:012X}"

        # Validate sub-device
        if (
            request.sub_device > self.MAX_SUB_DEVICE
            and request.sub_device != self.BROADCAST_SUB_DEVICE
        ):
            return False, f"Invalid sub-device: {request.sub_device}"

        # Validate command class
        if request.command_class not in (
            CommandClass.GET_COMMAND,
            CommandClass.SET_COMMAND,
            CommandClass.DISCOVERY_COMMAND,
        ):
            return False, f"Invalid command class: {request.command_class}"

        # Validate data length
        if len(request.data) > self.MAX_PDL:
            return False, f"Data too long: {len(request.data)} > {self.MAX_PDL}"

        # Validate PID
        if not self._is_valid_pid(request.pid):
            return False, f"Invalid PID: {request.pid:#06x}"

        # Broadcast-specific validation
        if request.destination_uid == self.BROADCAST_UID:
            if request.command_class == CommandClass.GET_COMMAND:
                return False, "GET command cannot be broadcast"

        return True, None

    def validate_response(self, response: RDMResponse) -> tuple[bool, str | None]:
        """Validate an incoming response independently of its request.

        Returns:
            A pair containing the validity flag and an error message when invalid.
        """
        # Validate UIDs
        if not self._is_valid_uid(response.source_uid):
            return False, f"Invalid source UID: {response.source_uid:012X}"

        if not self._is_valid_uid(response.destination_uid):
            return False, f"Invalid destination UID: {response.destination_uid:012X}"

        # Validate sub-device
        if (
            response.sub_device > self.MAX_SUB_DEVICE
            and response.sub_device != self.BROADCAST_SUB_DEVICE
        ):
            return False, f"Invalid sub-device: {response.sub_device}"

        # Validate response type
        if response.response_type not in (
            ResponseType.ACK,
            ResponseType.NAK,
            ResponseType.ACK_TIMER,
            ResponseType.ACK_OVERFLOW,
        ):
            return False, f"Invalid response type: {response.response_type}"

        # Validate data length
        if len(response.data) > self.MAX_PDL:
            return False, f"Data too long: {len(response.data)} > {self.MAX_PDL}"

        # Validate message count
        if response.message_count > 255:
            return False, f"Invalid message count: {response.message_count}"

        # Checksum validation
        if self._strict_mode and not response.checksum_valid:
            return False, "Checksum validation failed"

        return True, None

    def validate_request_response_match(
        self, request: RDMRequest, response: RDMResponse
    ) -> tuple[bool, str | None]:
        """Verify that a response corresponds to a specific request.

        Returns:
            A pair containing the match flag and an error message on mismatch.
        """
        # Transaction number must match
        if request.transaction_number != response.transaction_number:
            return False, (
                f"Transaction number mismatch: "
                f"request={request.transaction_number}, "
                f"response={response.transaction_number}"
            )

        # Source UID in response must match destination UID in request
        if response.source_uid != request.destination_uid:
            return False, (
                f"UID mismatch: request dest={request.destination_uid:012X}, "
                f"response src={response.source_uid:012X}"
            )

        # Destination UID in response must match source UID in request
        if response.destination_uid != request.source_uid:
            return False, (
                f"UID mismatch: request src={request.source_uid:012X}, "
                f"response dest={response.destination_uid:012X}"
            )

        # PID must match (except for queued messages)
        if request.pid != response.pid:
            # Allow QUEUED_MESSAGE responses
            if response.pid != PID(0x0020):  # QUEUED_MESSAGE
                return False, (
                    f"PID mismatch: request={request.pid:#06x}, response={response.pid:#06x}"
                )

        # Command class validation: a response's command class must be the
        # corresponding *_RESPONSE class for the request's command class
        # (e.g. GET_COMMAND -> GET_COMMAND_RESPONSE), per ANSI E1.20.
        expected_command_class = self._EXPECTED_RESPONSE_COMMAND_CLASS.get(request.command_class)
        if response.command_class != expected_command_class:
            return False, (
                f"Command class mismatch: request={request.command_class}, "
                f"response={response.command_class}"
            )

        return True, None

    def _is_valid_uid(self, uid: UID) -> bool:
        uid_val = int(uid)
        # UID must be 48 bits
        if uid_val < 0 or uid_val > 0xFFFFFFFFFFFF:
            return False

        # Manufacturer ID (upper 16 bits) cannot be 0 unless it's broadcast
        if uid_val != 0xFFFFFFFFFFFF:
            manufacturer_id = uid_val >> 32
            if manufacturer_id == 0:
                return False

        return True

    def _is_valid_pid(self, pid: PID) -> bool:
        pid_val = int(pid)
        # PID must be 16 bits
        return 0 <= pid_val <= 0xFFFF

    def validate_and_log(self, request: RDMRequest) -> bool:
        """Validate a request and log its validation error, if any."""
        is_valid, error = self.validate_request(request)

        if not is_valid:
            self._logger.error(f"Request validation failed: {error}")

        return is_valid
