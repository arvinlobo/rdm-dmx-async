"""Tests for SensorDefinitionsAPI/SensorsAPI prefix scaling (ANSI E1.20 Table A-14)."""

import struct
from unittest.mock import AsyncMock, MagicMock

import pytest

from rdm_dmx_async.services.device_apis.sensor_definitions import SensorDefinitionsAPI
from rdm_dmx_async.services.device_apis.sensors import SensorsAPI


def _definition_bytes(
    sensor_number: int = 0,
    sensor_type: int = 0,
    unit: int = 1,
    prefix: int = 0,
    range_min: int = 0,
    range_max: int = 100,
    normal_min: int = 0,
    normal_max: int = 100,
    supports_recording: int = 0,
    description: bytes = b"Temp",
) -> bytes:
    return (
        struct.pack("BBBB", sensor_number, sensor_type, unit, prefix)
        + struct.pack(">hhhh", range_min, range_max, normal_min, normal_max)
        + struct.pack("B", supports_recording)
        + description
    )


def _value_bytes(
    sensor_number: int = 0, present: int = 0, lowest: int = 0, highest: int = 0, recorded: int = 0
) -> bytes:
    return struct.pack(">Bhhhh", sensor_number, present, lowest, highest, recorded)


def _make_device(sensor_count: int = 1) -> MagicMock:
    device = MagicMock()
    device.state.sensor_count = sensor_count
    device.execute_get = AsyncMock()
    return device


@pytest.mark.asyncio
class TestSensorDefinitionsScaling:
    """Range/normal fields must scale by the definition's own PREFIX field,
    per ANSI E1.20 - not a fixed divisor."""

    async def test_no_prefix_returns_raw_ints(self):
        device = _make_device()
        device.execute_get.return_value = _definition_bytes(
            prefix=0x00, range_min=-3500, range_max=19000
        )
        api = SensorDefinitionsAPI(device)

        definition = await api.get_sensor_definition(0)

        assert definition["prefix"] == 0x00
        assert definition["range_min"] == -3500
        assert definition["range_max"] == 19000

    async def test_centi_prefix_scales_by_ten_to_minus_two(self):
        device = _make_device()
        device.execute_get.return_value = _definition_bytes(
            prefix=0x02, range_min=-3500, range_max=19000
        )
        api = SensorDefinitionsAPI(device)

        definition = await api.get_sensor_definition(0)

        assert definition["range_min"] == pytest.approx(-35.0)
        assert definition["range_max"] == pytest.approx(190.0)

    async def test_micro_prefix_scales_by_ten_to_minus_six_not_minus_four(self):
        """MICRO is 0x04 on the wire - a naive `10**prefix` shortcut would give
        10^-4 instead of the correct 10^-6."""
        device = _make_device()
        device.execute_get.return_value = _definition_bytes(
            prefix=0x04, range_min=100, range_max=200
        )
        api = SensorDefinitionsAPI(device)

        definition = await api.get_sensor_definition(0)

        assert definition["range_min"] == pytest.approx(0.0001)
        assert definition["range_max"] == pytest.approx(0.0002)

    async def test_kilo_prefix_scales_up(self):
        """KILO is 0x13 on the wire (the table jumps from YOCTO=0x0A to
        DECA=0x11), not the naive 0x03 (which is MILLI)."""
        device = _make_device()
        device.execute_get.return_value = _definition_bytes(prefix=0x13, range_min=1, range_max=2)
        api = SensorDefinitionsAPI(device)

        definition = await api.get_sensor_definition(0)

        assert definition["range_min"] == pytest.approx(1000.0)
        assert definition["range_max"] == pytest.approx(2000.0)

    async def test_unknown_prefix_is_identity_scaling(self):
        device = _make_device()
        device.execute_get.return_value = _definition_bytes(prefix=0x7F, range_min=42, range_max=99)
        api = SensorDefinitionsAPI(device)

        definition = await api.get_sensor_definition(0)

        assert definition["range_min"] == 42
        assert definition["range_max"] == 99


@pytest.mark.asyncio
class TestGetCachedDefinition:
    async def test_returns_none_before_bulk_load(self):
        device = _make_device()
        api = SensorDefinitionsAPI(device)

        assert api.get_cached_definition(0) is None

    async def test_returns_definition_after_bulk_load(self):
        device = _make_device(sensor_count=1)
        device.execute_get.return_value = _definition_bytes(sensor_number=0, prefix=0x02)
        api = SensorDefinitionsAPI(device)

        await api.get_all_sensor_definitions()

        cached = api.get_cached_definition(0)
        assert cached is not None
        assert cached["prefix"] == 0x02

    async def test_invalidate_cache_clears_lookup(self):
        device = _make_device(sensor_count=1)
        device.execute_get.return_value = _definition_bytes(sensor_number=0)
        api = SensorDefinitionsAPI(device)
        await api.get_all_sensor_definitions()

        api.invalidate_cache()

        assert api.get_cached_definition(0) is None


@pytest.mark.asyncio
class TestSensorsValueScaling:
    """SENSOR_VALUE readings scale by the same prefix as the sensor's
    definition, when that definition is already cached."""

    async def test_returns_raw_when_definition_not_cached(self):
        device = _make_device()
        device.sensor_definitions = SensorDefinitionsAPI(device)  # empty cache
        device.execute_get.return_value = _value_bytes(
            present=2500, lowest=2000, highest=3000, recorded=2500
        )
        api = SensorsAPI(device)

        value = await api.get_value(0)

        assert value["present_value"] == 2500
        assert value["lowest"] == 2000
        assert value["highest"] == 3000
        assert value["recorded"] == 2500

    async def test_scales_by_cached_definition_prefix(self):
        device = _make_device()
        device.sensor_definitions = SensorDefinitionsAPI(device)
        device.execute_get.return_value = _definition_bytes(sensor_number=0, prefix=0x02)
        await device.sensor_definitions.get_all_sensor_definitions()

        device.execute_get.return_value = _value_bytes(
            present=2500, lowest=2000, highest=3000, recorded=2500
        )
        api = SensorsAPI(device)

        value = await api.get_value(0)

        assert value["present_value"] == pytest.approx(25.0)
        assert value["lowest"] == pytest.approx(20.0)
        assert value["highest"] == pytest.approx(30.0)
        assert value["recorded"] == pytest.approx(25.0)
