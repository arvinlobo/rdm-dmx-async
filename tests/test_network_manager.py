"""
Unit tests for NetworkManager's DMX send path, using a fake transport.

Regression safety net for the AsyncTransport.send_dmx_frame() abstraction:
NetworkManager must delegate DMX framing/sending to the transport instead of
reaching into transport-specific internals (e.g. `.adapter`, `bypass_framing`).
"""

from unittest import mock

import pytest

from rdm_dmx_async.application.network_manager import NetworkConfig, NetworkManager
from rdm_dmx_async.packets.types import UID
from rdm_dmx_async.scheduling.dmx_scheduler import DmxFrameScheduler
from rdm_dmx_async.transport.interface_adapter import InterfaceType


class FakeTransport:
    """Minimal stand-in for AsyncTransport, recording send_dmx_frame() calls."""

    def __init__(self):
        self.is_connected = True
        self.sent_frames: list[tuple[bytes, int]] = []

    async def connect(self) -> None:
        self.is_connected = True

    async def disconnect(self) -> None:
        self.is_connected = False

    async def send(self, data: bytes, destination: str) -> None:
        raise AssertionError("NetworkManager should use send_dmx_frame(), not raw send()")

    async def send_dmx_frame(self, dmx_data: bytes, port: int = 1) -> None:
        self.sent_frames.append((bytes(dmx_data), port))

    async def receive(self, timeout: float | None = None) -> tuple[bytes, str]:
        raise NotImplementedError


def _make_manager_with_fake_transport() -> tuple[NetworkManager, FakeTransport]:
    """Build a NetworkManager wired to a FakeTransport, bypassing real hardware I/O."""
    manager = NetworkManager(NetworkConfig())
    transport = FakeTransport()
    manager._transport = transport
    manager._scheduler = DmxFrameScheduler(send_callback=manager._send_scheduled_frame)
    manager._active = True
    return manager, transport


@pytest.mark.asyncio
class TestNetworkManagerSendDmx:
    async def test_send_dmx_delegates_to_transport_send_dmx_frame(self):
        manager, transport = _make_manager_with_fake_transport()
        try:
            dmx_data = bytes([1, 2, 3, 4])
            await manager.send_dmx(dmx_data, port=2)

            assert transport.sent_frames == [(dmx_data, 2)]
        finally:
            await manager._scheduler.stop()

    async def test_send_dmx_defaults_to_port_1(self):
        manager, transport = _make_manager_with_fake_transport()
        try:
            dmx_data = bytes([9, 9, 9])
            await manager.send_dmx(dmx_data)

            assert transport.sent_frames == [(dmx_data, 1)]
        finally:
            await manager._scheduler.stop()

    async def test_send_dmx_raises_when_not_active(self):
        manager = NetworkManager(NetworkConfig())

        with pytest.raises(RuntimeError):
            await manager.send_dmx(bytes([1, 2, 3]))

    async def test_scheduled_frame_callback_delegates_to_transport_send_dmx_frame(self):
        manager, transport = _make_manager_with_fake_transport()
        try:
            await manager._send_scheduled_frame(bytes(512))

            assert transport.sent_frames == [(bytes(512), 1)]
        finally:
            await manager._scheduler.stop()


class _FakeAdapter:
    """Minimal stand-in for InterfaceAdapter, just enough for start()'s UID resolution."""

    def __init__(self, interface_type: InterfaceType):
        self.interface_type = interface_type


@pytest.mark.asyncio
class TestNetworkManagerControllerUidResolution:
    """`start()`'s controller-UID resolution must be generic: an explicitly
    configured `NetworkConfig.controller_uid` always wins, and only interface
    types that can query their own UID (currently Enttec) get a hardware
    fallback - anything else without a configured UID must fail clearly."""

    async def test_bare_usb_rs485_without_controller_uid_raises(self):
        manager = NetworkManager(
            NetworkConfig(port="COM7", interface_type=InterfaceType.BARE_USB_RS485)
        )
        with (
            mock.patch.object(manager._port_detector, "resolve_port", return_value="COM7"),
            mock.patch.object(
                manager, "_create_adapter", return_value=_FakeAdapter(InterfaceType.BARE_USB_RS485)
            ),
        ):
            with pytest.raises(ValueError, match="controller_uid"):
                await manager.start()

    async def test_bare_usb_rs485_uses_configured_controller_uid(self):
        controller_uid = UID(0xAABBCCDDEEFF)
        manager = NetworkManager(
            NetworkConfig(
                port="COM7",
                interface_type=InterfaceType.BARE_USB_RS485,
                controller_uid=controller_uid,
            )
        )
        transport_instance = mock.MagicMock(connect=mock.AsyncMock())
        protocol_instance = mock.MagicMock(start=mock.AsyncMock())

        with (
            mock.patch.object(manager._port_detector, "resolve_port", return_value="COM7"),
            mock.patch.object(
                manager, "_create_adapter", return_value=_FakeAdapter(InterfaceType.BARE_USB_RS485)
            ),
            mock.patch(
                "rdm_dmx_async.application.network_manager.AsyncSerialTransport",
                return_value=transport_instance,
            ),
            mock.patch(
                "rdm_dmx_async.application.network_manager.RDME120Protocol",
                return_value=protocol_instance,
            ) as mock_protocol_cls,
            mock.patch("rdm_dmx_async.application.network_manager.DeviceRepository"),
            mock.patch("rdm_dmx_async.application.network_manager.DiscoveryService"),
        ):
            await manager.start()

        assert mock_protocol_cls.call_args.args[1] == controller_uid
        assert manager.is_active is True

    async def test_configured_controller_uid_skips_enttec_query(self):
        controller_uid = UID(0xAABBCCDDEEFF)
        manager = NetworkManager(
            NetworkConfig(
                port="COM7",
                interface_type=InterfaceType.ENTTEC_USB_PRO,
                controller_uid=controller_uid,
            )
        )
        transport_instance = mock.MagicMock(connect=mock.AsyncMock())
        protocol_instance = mock.MagicMock(start=mock.AsyncMock())

        with (
            mock.patch.object(manager._port_detector, "resolve_port", return_value="COM7"),
            mock.patch.object(
                manager,
                "_create_adapter",
                return_value=_FakeAdapter(InterfaceType.ENTTEC_USB_PRO),
            ),
            mock.patch(
                "rdm_dmx_async.application.network_manager.get_enttec_serial_uid"
            ) as mock_get_uid,
            mock.patch(
                "rdm_dmx_async.application.network_manager.AsyncSerialTransport",
                return_value=transport_instance,
            ),
            mock.patch(
                "rdm_dmx_async.application.network_manager.RDME120Protocol",
                return_value=protocol_instance,
            ) as mock_protocol_cls,
            mock.patch("rdm_dmx_async.application.network_manager.DeviceRepository"),
            mock.patch("rdm_dmx_async.application.network_manager.DiscoveryService"),
        ):
            await manager.start()

        mock_get_uid.assert_not_called()
        assert mock_protocol_cls.call_args.args[1] == controller_uid
