"""Tests for the generic, reflection-based `/devices/{uid}/...` capability endpoints.

These endpoints introspect a device's API module objects via `inspect`, so the
mocked device here uses plain classes with real `async def` methods (not
MagicMock auto-attributes) to exercise genuine signature introspection.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.dependencies import get_device
from rdm_dmx_async.services.rdm_device import DeviceState

DEVICE_UID_HEX = "454E00000001"


class FakeDeviceLabel:
    async def get(self, use_cache: bool = True) -> str:
        return "Fixture 1"

    async def set(self, label: str) -> bool:
        return True


class FakeLamp:
    async def get_hours(self, use_cache: bool = True) -> int:
        return 120

    async def set_hours(self, hours: int) -> bool:
        return True

    async def get_state(self, use_cache: bool = True) -> int:
        raise RuntimeError("device unresponsive")


class FakeDmxConfig:
    async def get_personality(self, use_cache: bool = True) -> tuple:
        return (2, 3)

    async def get_personality_description(self, personality: int) -> dict:
        return {
            "personality": personality,
            "footprint": personality * 4,
            "description": f"Mode {personality}",
        }

    async def set_personality(self, personality: int) -> bool:
        return True

    async def set_start_address(self, address: int) -> bool:
        return True


class FakeSensors:
    async def get_value(self, sensor_number: int) -> dict:
        return {
            "sensor_number": sensor_number,
            "present_value": 2500,
            "lowest": 2000,
            "highest": 3000,
            "recorded": 2500,
        }

    async def record(self, sensor_number: int = 0xFF) -> bool:
        return True


class FakeSensorDefinitions:
    async def get_all_sensor_definitions(self, use_cache: bool = True) -> list:
        return [
            {
                "sensor_number": 0,
                "type": 0,
                "unit": 1,
                "prefix": 2,
                "range_min": -3500,
                "range_max": 19000,
                "normal_min": -3500,
                "normal_max": 8500,
                "supports_recording": 0,
                "description": "Driver Temperature",
            }
        ]


def _make_device() -> MagicMock:
    device = MagicMock()
    device.uid = int(DEVICE_UID_HEX, 16)
    device.state = DeviceState(
        uid=device.uid,
        manufacturer="Acme",
        device_label="Fixture 1",
        model="Widget",
        dmx_start_address=1,
        dmx_personality=1,
        dmx_footprint=4,
    )
    device.device_label = FakeDeviceLabel()
    device.lamp = FakeLamp()
    device.dmx_config = FakeDmxConfig()
    device.sensors = FakeSensors()
    device.sensor_definitions = FakeSensorDefinitions()
    device.supports_pid = MagicMock(return_value=True)
    device.check_capabilities = None  # set per-test as AsyncMock when needed
    return device


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def _override(app, device) -> None:
    app.dependency_overrides[get_device] = lambda: device


def test_get_capabilities(app, client):
    from unittest.mock import AsyncMock

    device = _make_device()
    device.check_capabilities = AsyncMock(return_value=True)
    device.get_api_support_details = MagicMock(
        return_value={
            "device_label": {
                "supported": True,
                "pids": [0x0082],
                "supported_pids": [0x0082],
                "missing_pids": [],
                "coverage": 1.0,
            }
        }
    )
    _override(app, device)
    try:
        response = client.get(f"/devices/{DEVICE_UID_HEX}/capabilities")
        assert response.status_code == 200
        body = response.json()
        assert body["modules"]["device_label"]["supported"] is True
        assert body["modules"]["device_label"]["coverage"] == 1.0
        device.check_capabilities.assert_awaited_once()
    finally:
        app.dependency_overrides.clear()


def test_get_module_schema_unknown_module(app, client):
    device = _make_device()
    _override(app, device)
    try:
        response = client.get(f"/devices/{DEVICE_UID_HEX}/modules/not_a_module/schema")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_get_module_schema_lists_methods_and_params(app, client):
    device = _make_device()
    _override(app, device)
    try:
        response = client.get(f"/devices/{DEVICE_UID_HEX}/modules/lamp/schema")
        assert response.status_code == 200
        body = response.json()
        assert body["module"] == "lamp"
        methods_by_name = {m["name"]: m for m in body["methods"]}
        assert methods_by_name["get_hours"]["is_getter"] is True
        assert methods_by_name["get_hours"]["supported"] is True
        assert methods_by_name["get_hours"]["params"] == [
            {
                "name": "use_cache",
                "kind": "bool",
                "required": False,
                "default": True,
                "min": None,
                "max": None,
            }
        ]
        assert methods_by_name["set_hours"]["is_getter"] is False
        assert methods_by_name["set_hours"]["params"] == [
            {
                "name": "hours",
                "kind": "int",
                "required": True,
                "default": None,
                "min": 0,
                "max": 999_999,
            }
        ]
    finally:
        app.dependency_overrides.clear()


def test_get_module_state_calls_zero_arg_getters(app, client):
    device = _make_device()
    _override(app, device)
    try:
        response = client.get(f"/devices/{DEVICE_UID_HEX}/modules/device_label/state")
        assert response.status_code == 200
        assert response.json() == {"get": "Fixture 1"}
    finally:
        app.dependency_overrides.clear()


def test_get_module_state_swallows_getter_errors(app, client):
    device = _make_device()
    _override(app, device)
    try:
        response = client.get(f"/devices/{DEVICE_UID_HEX}/modules/lamp/state")
        assert response.status_code == 200
        body = response.json()
        assert body["get_hours"] == 120
        assert body["get_state"] is None
    finally:
        app.dependency_overrides.clear()


def test_call_module_method_setter(app, client):
    device = _make_device()
    _override(app, device)
    try:
        response = client.post(
            f"/devices/{DEVICE_UID_HEX}/modules/lamp/set_hours", json={"args": [200]}
        )
        assert response.status_code == 200
        assert response.json() == {"result": True}
    finally:
        app.dependency_overrides.clear()


def test_call_module_method_unknown_method(app, client):
    device = _make_device()
    _override(app, device)
    try:
        response = client.post(
            f"/devices/{DEVICE_UID_HEX}/modules/lamp/not_a_method", json={"args": []}
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_call_module_method_rejects_private_method(app, client):
    device = _make_device()
    _override(app, device)
    try:
        response = client.post(
            f"/devices/{DEVICE_UID_HEX}/modules/lamp/__init__", json={"args": []}
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_call_module_method_wrong_arg_count_returns_422(app, client):
    device = _make_device()
    _override(app, device)
    try:
        response = client.post(
            f"/devices/{DEVICE_UID_HEX}/modules/lamp/set_hours", json={"args": [1, 2, 3]}
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_get_module_schema_flags_unsupported_method(app, client):
    device = _make_device()
    device.supports_pid = MagicMock(side_effect=lambda pid: pid != 0x0401)  # LAMP_HOURS
    _override(app, device)
    try:
        response = client.get(f"/devices/{DEVICE_UID_HEX}/modules/lamp/schema")
        assert response.status_code == 200
        methods_by_name = {m["name"]: m for m in response.json()["methods"]}
        assert methods_by_name["get_hours"]["supported"] is False
        assert methods_by_name["set_hours"]["supported"] is False
    finally:
        app.dependency_overrides.clear()


def test_get_module_schema_start_address_range_is_1_to_512(app, client):
    device = _make_device()
    _override(app, device)
    try:
        response = client.get(f"/devices/{DEVICE_UID_HEX}/modules/dmx_config/schema")
        assert response.status_code == 200
        methods_by_name = {m["name"]: m for m in response.json()["methods"]}
        address_param = methods_by_name["set_start_address"]["params"][0]
        assert address_param == {
            "name": "address",
            "kind": "int",
            "required": True,
            "default": None,
            "min": 1,
            "max": 512,
        }

        personality_param = methods_by_name["set_personality"]["params"][0]
        assert personality_param["kind"] == "enum"
    finally:
        app.dependency_overrides.clear()


def test_get_personalities(app, client):
    device = _make_device()
    _override(app, device)
    try:
        response = client.get(f"/devices/{DEVICE_UID_HEX}/modules/dmx_config/personalities")
        assert response.status_code == 200
        body = response.json()
        assert body["current"] == 2
        assert body["options"] == [
            {"personality": 1, "footprint": 4, "description": "Mode 1"},
            {"personality": 2, "footprint": 8, "description": "Mode 2"},
            {"personality": 3, "footprint": 12, "description": "Mode 3"},
        ]
    finally:
        app.dependency_overrides.clear()


def test_get_sensor_readings(app, client):
    device = _make_device()
    _override(app, device)
    try:
        response = client.get(f"/devices/{DEVICE_UID_HEX}/modules/sensors/readings")
        assert response.status_code == 200
        body = response.json()
        assert body["sensors"] == [
            {
                "sensor_number": 0,
                "description": "Driver Temperature",
                "unit": 1,
                "prefix": 2,
                "present_value": 2500,
                "lowest": 2000,
                "highest": 3000,
                "recorded": 2500,
                "range_min": -3500,
                "range_max": 19000,
                "normal_min": -3500,
                "normal_max": 8500,
                "supports_recording": False,
            }
        ]
    finally:
        app.dependency_overrides.clear()
