"""Tests for the top-level `api/` FastAPI application.

Exercises the API's own logic (routing, validation, dependency wiring) using
mocked NetworkManager/RdmDevice objects via FastAPI dependency overrides -
no real hardware or protocol stack is involved.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.dependencies import get_device
from rdm_dmx_async.services.rdm_device import DeviceState

DEVICE_UID_HEX = "454E00000001"


def _make_manager() -> MagicMock:
    # stop() is awaited unconditionally during app shutdown, so it must be an AsyncMock.
    manager = MagicMock(is_active=True)
    manager.stop = AsyncMock()
    return manager


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
    device.device_label.set = AsyncMock(return_value=True)
    device.dmx_config.set_start_address = AsyncMock(return_value=True)
    device.control.identify = AsyncMock(return_value=True)
    return device


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def test_ports_lists_available_ports(client, monkeypatch):
    monkeypatch.setattr("api.routers.network.list_available_ports", lambda: ["COM3", "COM5"])
    response = client.get("/network/ports")
    assert response.status_code == 200
    assert response.json() == {"ports": ["COM3", "COM5"]}


def test_status_when_not_connected(client):
    response = client.get("/network/status")
    assert response.status_code == 200
    assert response.json() == {"connected": False, "port": None, "device_count": 0}


def test_connect_rejects_unknown_interface_type(client):
    response = client.post("/network/connect", json={"interface_type": "NOT_A_REAL_INTERFACE"})
    assert response.status_code == 400


def test_connect_with_no_body_auto_detects_port(client, monkeypatch):
    manager = _make_manager()
    manager.config = MagicMock(port="COM5")
    manager.start = AsyncMock()
    monkeypatch.setattr("api.routers.network.NetworkManager", lambda config: manager)

    response = client.post("/network/connect")

    assert response.status_code == 200
    assert response.json() == {"connected": True, "port": "COM5", "device_count": 0}
    manager.start.assert_awaited_once()


def test_devices_requires_connection(client):
    response = client.get("/devices")
    assert response.status_code == 409


def test_dmx_send_requires_connection(client):
    response = client.post("/dmx/send", json={"channels": [255, 0, 128]})
    assert response.status_code == 409


def test_dmx_send_rejects_out_of_range_channel_value(app, client):
    app.state.network_manager = _make_manager()
    response = client.post("/dmx/send", json={"channels": [256]})
    assert response.status_code == 422


def test_dmx_send_forwards_channels_to_manager(app, client):
    manager = _make_manager()
    manager.send_dmx = AsyncMock()
    app.state.network_manager = manager
    response = client.post("/dmx/send", json={"channels": [255, 0, 128], "port": 2})
    assert response.status_code == 200
    assert response.json() == {"success": True}
    manager.send_dmx.assert_awaited_once_with(bytes([255, 0, 128]), port=2)


def test_list_devices(app, client):
    device = _make_device()
    manager = _make_manager()
    manager.devices.get_all_devices.return_value = [device]
    app.state.network_manager = manager
    response = client.get("/devices")
    assert response.status_code == 200
    body = response.json()["devices"]
    assert body == [
        {
            "uid": DEVICE_UID_HEX,
            "manufacturer": "Acme",
            "device_label": "Fixture 1",
            "model": "Widget",
            "dmx_start_address": 1,
            "dmx_personality": 1,
            "dmx_footprint": 4,
        }
    ]


def test_discover_devices(app, client):
    device = _make_device()
    manager = _make_manager()
    manager.discover_devices = AsyncMock(return_value=[device])
    app.state.network_manager = manager
    response = client.post("/devices/discover", json={"timeout": 2.5})
    assert response.status_code == 200
    assert manager.config.discovery_timeout == 2.5
    assert len(response.json()["devices"]) == 1


def test_get_device_detail(app, client):
    device = _make_device()
    app.dependency_overrides[get_device] = lambda: device
    response = client.get(f"/devices/{DEVICE_UID_HEX}")
    assert response.status_code == 200
    assert response.json()["uid"] == DEVICE_UID_HEX


def test_get_device_detail_not_found(app, client):
    manager = _make_manager()
    manager.devices.get_device.return_value = None
    app.state.network_manager = manager
    response = client.get(f"/devices/{DEVICE_UID_HEX}")
    assert response.status_code == 404


def test_get_device_detail_rejects_invalid_uid(app, client):
    app.state.network_manager = _make_manager()
    response = client.get("/devices/not-hex")
    assert response.status_code == 400


def test_set_device_label(app, client):
    device = _make_device()
    app.dependency_overrides[get_device] = lambda: device
    try:
        response = client.put(f"/devices/{DEVICE_UID_HEX}/label", json={"label": "New Label"})
        assert response.status_code == 200
        assert response.json() == {"success": True}
        device.device_label.set.assert_awaited_once_with("New Label")
    finally:
        app.dependency_overrides.clear()


def test_set_start_address(app, client):
    device = _make_device()
    app.dependency_overrides[get_device] = lambda: device
    try:
        response = client.put(f"/devices/{DEVICE_UID_HEX}/start-address", json={"address": 5})
        assert response.status_code == 200
        device.dmx_config.set_start_address.assert_awaited_once_with(5)
    finally:
        app.dependency_overrides.clear()


def test_set_start_address_rejects_out_of_range(app, client):
    app.dependency_overrides[get_device] = lambda: _make_device()
    response = client.put(f"/devices/{DEVICE_UID_HEX}/start-address", json={"address": 999})
    assert response.status_code == 422


def test_identify(app, client):
    device = _make_device()
    app.dependency_overrides[get_device] = lambda: device
    try:
        response = client.post(f"/devices/{DEVICE_UID_HEX}/identify", json={"enable": True})
        assert response.status_code == 200
        device.control.identify.assert_awaited_once_with(True)
    finally:
        app.dependency_overrides.clear()
