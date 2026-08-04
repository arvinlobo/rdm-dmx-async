"""Tests for `RdmDevice.supports_pid` / `get_api_support_details` PID coverage logic."""

from unittest.mock import MagicMock

from rdm_dmx_async.domain.parameters import StandardPID
from rdm_dmx_async.services.rdm_device import RdmDevice

UID_VALUE = 0x454E00000001


def _make_device() -> RdmDevice:
    return RdmDevice(UID_VALUE, MagicMock())


def test_supports_pid_optimistic_before_capabilities_checked():
    device = _make_device()
    assert device.supports_pid(StandardPID.DMX_START_ADDRESS) is True
    assert device.supports_pid(StandardPID.LAMP_HOURS) is True


def test_supports_pid_mandatory_pid_always_true_even_if_absent():
    device = _make_device()
    device._supported_pids = {StandardPID.DEVICE_LABEL}  # noqa: SLF001 - test setup
    device._capabilities_checked = True  # noqa: SLF001 - test setup

    # DMX_START_ADDRESS and IDENTIFY_DEVICE are mandatory per E1.20 and may be
    # omitted from GET_SUPPORTED_PARAMETERS - must never be reported unsupported.
    assert device.supports_pid(StandardPID.DMX_START_ADDRESS) is True
    assert device.supports_pid(StandardPID.IDENTIFY_DEVICE) is True
    # A genuinely-absent, non-mandatory PID is still correctly unsupported.
    assert device.supports_pid(StandardPID.LAMP_HOURS) is False


def test_get_api_support_details_mandatory_pid_not_counted_missing():
    device = _make_device()
    device._supported_pids = {  # noqa: SLF001 - test setup
        StandardPID.DMX_PERSONALITY,
        StandardPID.DMX_PERSONALITY_DESCRIPTION,
    }
    device._capabilities_checked = True  # noqa: SLF001 - test setup

    details = device.get_api_support_details()

    dmx_config = details["dmx_config"]
    assert dmx_config["supported"] is True
    assert dmx_config["coverage"] == 1.0
    assert StandardPID.DMX_START_ADDRESS.value not in dmx_config["missing_pids"]
