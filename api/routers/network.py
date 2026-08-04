"""Network lifecycle endpoints: list ports, connect, disconnect, status."""

from fastapi import APIRouter, HTTPException, Request

from rdm_dmx_async.application.network_manager import NetworkConfig, NetworkManager
from rdm_dmx_async.transport.interface_adapter import InterfaceType
from rdm_dmx_async.utils import list_available_ports

from ..dependencies import get_network_manager
from ..schemas import ConnectRequest, OkResponse, PortListResponse, StatusResponse

router = APIRouter(prefix="/network", tags=["network"])


@router.get("/ports", response_model=PortListResponse)
def get_ports() -> PortListResponse:
    return PortListResponse(ports=list_available_ports())


@router.get("/status", response_model=StatusResponse)
def get_status(request: Request) -> StatusResponse:
    manager: NetworkManager | None = getattr(request.app.state, "network_manager", None)
    if manager is None or not manager.is_active:
        return StatusResponse(connected=False)
    return StatusResponse(
        connected=True,
        port=manager.config.port,
        device_count=len(manager.devices.get_all_devices()),
    )


@router.post("/connect", response_model=StatusResponse)
async def connect(request: Request, body: ConnectRequest = ConnectRequest()) -> StatusResponse:
    existing: NetworkManager | None = getattr(request.app.state, "network_manager", None)
    if existing is not None and existing.is_active:
        raise HTTPException(
            status_code=409, detail="Already connected. Call POST /network/disconnect first."
        )

    try:
        interface_type = InterfaceType[body.interface_type]
    except KeyError as exc:
        raise HTTPException(
            status_code=400, detail=f"Unknown interface_type: {body.interface_type!r}"
        ) from exc

    config = NetworkConfig(port=body.port, interface_type=interface_type)
    manager = NetworkManager(config)
    await manager.start()
    request.app.state.network_manager = manager

    return StatusResponse(connected=True, port=manager.config.port, device_count=0)


@router.post("/disconnect", response_model=OkResponse)
async def disconnect(request: Request) -> OkResponse:
    manager = get_network_manager(request)
    await manager.stop()
    request.app.state.network_manager = None
    return OkResponse()
