"""
Unit tests for RdmValidator (ANSI E1.20 request/response validation rules).
"""

from rdm_dmx_async.packets.rdm import RDMRequest, RDMResponse
from rdm_dmx_async.packets.types import PID, UID, CommandClass, ResponseType, TransactionNumber
from rdm_dmx_async.protocols.rdm_validator import RdmValidator

DEVICE_UID = UID(0x454E00000001)
CONTROLLER_UID = UID(0x454E00000000)
BROADCAST_UID = UID(0xFFFFFFFFFFFF)


def _request(**overrides) -> RDMRequest:
    fields = {
        "destination_uid": DEVICE_UID,
        "source_uid": CONTROLLER_UID,
        "transaction_number": TransactionNumber(1),
        "port_address": 0,
        "sub_device": 0,
        "command_class": CommandClass.GET_COMMAND,
        "pid": PID(0x1000),
        "data": b"",
    }
    fields.update(overrides)
    return RDMRequest(**fields)


def _response(**overrides) -> RDMResponse:
    fields = {
        "source_uid": DEVICE_UID,
        "destination_uid": CONTROLLER_UID,
        "transaction_number": TransactionNumber(1),
        "response_type": ResponseType.ACK,
        "message_count": 0,
        "sub_device": 0,
        "command_class": CommandClass.GET_COMMAND_RESPONSE,
        "pid": PID(0x1000),
        "data": b"",
        "checksum_valid": True,
    }
    fields.update(overrides)
    return RDMResponse(**fields)


class TestValidateRequest:
    def test_valid_get_request(self):
        validator = RdmValidator()
        is_valid, error = validator.validate_request(_request())
        assert is_valid is True
        assert error is None

    def test_invalid_source_uid_zero_manufacturer(self):
        validator = RdmValidator()
        is_valid, error = validator.validate_request(_request(source_uid=UID(0x000000000001)))
        assert is_valid is False
        assert "source UID" in error

    def test_get_command_cannot_be_broadcast(self):
        validator = RdmValidator()
        is_valid, error = validator.validate_request(_request(destination_uid=BROADCAST_UID))
        assert is_valid is False
        assert "broadcast" in error.lower()

    def test_data_too_long_rejected(self):
        validator = RdmValidator()
        # RDMRequest itself enforces this at construction time; bypass via
        # object.__setattr__ so we can exercise the validator's own check.
        request = _request()
        object.__setattr__(request, "data", b"\x00" * 232)

        is_valid, error = validator.validate_request(request)
        assert is_valid is False
        assert "too long" in error.lower()

    def test_invalid_sub_device_rejected(self):
        validator = RdmValidator()
        request = _request()
        object.__setattr__(request, "sub_device", 0x1000)

        is_valid, error = validator.validate_request(request)
        assert is_valid is False
        assert "sub-device" in error.lower()

    def test_broadcast_sub_device_allowed(self):
        validator = RdmValidator()
        request = _request()
        object.__setattr__(request, "sub_device", 0xFFFF)

        is_valid, _ = validator.validate_request(request)
        assert is_valid is True


class TestValidateResponse:
    def test_valid_ack_response(self):
        validator = RdmValidator()
        is_valid, error = validator.validate_response(_response())
        assert is_valid is True
        assert error is None

    def test_invalid_response_type_rejected(self):
        validator = RdmValidator(strict_mode=False)
        response = _response()
        # Bypass frozen dataclass validation to inject a bad response_type.
        object.__setattr__(response, "response_type", 99)
        is_valid, error = validator.validate_response(response)
        assert is_valid is False
        assert "response type" in error.lower()

    def test_strict_mode_rejects_bad_checksum(self):
        validator = RdmValidator(strict_mode=True)
        is_valid, error = validator.validate_response(_response(checksum_valid=False))
        assert is_valid is False
        assert "checksum" in error.lower()

    def test_non_strict_mode_allows_bad_checksum(self):
        validator = RdmValidator(strict_mode=False)
        is_valid, _ = validator.validate_response(_response(checksum_valid=False))
        assert is_valid is True


class TestValidateRequestResponseMatch:
    def test_matching_get_request_and_response(self):
        validator = RdmValidator()
        request = _request(command_class=CommandClass.GET_COMMAND)
        response = _response(command_class=CommandClass.GET_COMMAND_RESPONSE)

        is_valid, error = validator.validate_request_response_match(request, response)

        assert is_valid is True
        assert error is None

    def test_matching_set_request_and_response(self):
        validator = RdmValidator()
        request = _request(command_class=CommandClass.SET_COMMAND)
        response = _response(command_class=CommandClass.SET_COMMAND_RESPONSE)

        is_valid, error = validator.validate_request_response_match(request, response)

        assert is_valid is True
        assert error is None

    def test_transaction_number_mismatch(self):
        validator = RdmValidator()
        request = _request(transaction_number=TransactionNumber(1))
        response = _response(transaction_number=TransactionNumber(2))

        is_valid, error = validator.validate_request_response_match(request, response)

        assert is_valid is False
        assert "Transaction number mismatch" in error

    def test_uid_mismatch(self):
        validator = RdmValidator()
        request = _request()
        response = _response(source_uid=UID(0x454E00000099))

        is_valid, error = validator.validate_request_response_match(request, response)

        assert is_valid is False
        assert "UID mismatch" in error

    def test_command_class_mismatch_detected(self):
        validator = RdmValidator()
        request = _request(command_class=CommandClass.GET_COMMAND)
        # A SET_COMMAND_RESPONSE can never legitimately answer a GET request.
        response = _response(command_class=CommandClass.SET_COMMAND_RESPONSE)

        is_valid, error = validator.validate_request_response_match(request, response)

        assert is_valid is False
        assert "Command class mismatch" in error

    def test_queued_message_pid_allowed_on_mismatch(self):
        validator = RdmValidator()
        request = _request(pid=PID(0x1000))
        response = _response(pid=PID(0x0020))  # QUEUED_MESSAGE

        is_valid, error = validator.validate_request_response_match(request, response)

        assert is_valid is True
        assert error is None
