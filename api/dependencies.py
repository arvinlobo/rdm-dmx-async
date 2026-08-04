"""FastAPI dependency providers for accessing the shared NetworkManager."""

from fastapi import HTTPException, Request

from rdm_dmx_async.application.network_manager import NetworkManager
from rdm_dmx_async.packets.types import UID
from rdm_dmx_async.services.rdm_device import RdmDevice


def get_network_manager(request: Request) -> NetworkManager:
    """Return the app-wide NetworkManager, or 409 if not connected yet."""
    manager: NetworkManager | None = getattr(request.app.state, "network_manager", None)
    if manager is None or not manager.is_active:
        raise HTTPException(
            status_code=409, detail="Not connected. Call POST /network/connect first."
        )
    return manager


def parse_uid(uid_hex: str) -> UID:
    """Parse a hex UID path parameter (e.g. "454e00000001") into a UID."""
    try:
        return UID(int(uid_hex, 16))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid UID: {uid_hex!r}") from exc


def get_device(uid: str, request: Request) -> RdmDevice:
    """Return the discovered device matching the hex UID path parameter, or 404."""
    manager = get_network_manager(request)
    device = manager.devices.get_device(parse_uid(uid))
    if device is None:
        raise HTTPException(status_code=404, detail=f"Device {uid} not found. Run discovery first.")
    return device
