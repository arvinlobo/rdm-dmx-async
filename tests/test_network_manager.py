"""
Unit tests for NetworkManager's DMX send path, using a fake transport.

Regression safety net for the AsyncTransport.send_dmx_frame() abstraction:
NetworkManager must delegate DMX framing/sending to the transport instead of
reaching into transport-specific internals (e.g. `.adapter`, `bypass_framing`).
"""

import pytest

from rdm_dmx_async.application.network_manager import NetworkConfig, NetworkManager
from rdm_dmx_async.scheduling.dmx_scheduler import DmxFrameScheduler


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
