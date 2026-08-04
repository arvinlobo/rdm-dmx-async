"""Device discovery and per-device control endpoints."""

from fastapi import APIRouter, Depends

from rdm_dmx_async.services.rdm_device import RdmDevice

from ..dependencies import get_device, get_network_manager
from ..schemas import (
    DeviceLabelUpdate,
    DeviceSummary,
    DiscoverRequest,
    DiscoverResponse,
    IdentifyRequest,
    OkResponse,
    StartAddressUpdate,
)

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("/discover", response_model=DiscoverResponse)
async def discover(body: DiscoverRequest, manager=Depends(get_network_manager)) -> DiscoverResponse:
    manager.config.discovery_timeout = body.timeout
    devices = await manager.discover_devices()
    return DiscoverResponse(
        devices=[DeviceSummary.from_device_state(f"{d.uid:012X}", d.state) for d in devices]
    )


@router.get("", response_model=DiscoverResponse)
def list_devices(manager=Depends(get_network_manager)) -> DiscoverResponse:
    devices = manager.devices.get_all_devices()
    return DiscoverResponse(
        devices=[DeviceSummary.from_device_state(f"{d.uid:012X}", d.state) for d in devices]
    )


@router.get("/{uid}", response_model=DeviceSummary)
def get_device_detail(device: RdmDevice = Depends(get_device)) -> DeviceSummary:
    return DeviceSummary.from_device_state(f"{device.uid:012X}", device.state)


@router.put("/{uid}/label", response_model=OkResponse)
async def set_label(body: DeviceLabelUpdate, device: RdmDevice = Depends(get_device)) -> OkResponse:
    success = await device.device_label.set(body.label)
    return OkResponse(success=success)


@router.put("/{uid}/start-address", response_model=OkResponse)
async def set_start_address(
    body: StartAddressUpdate, device: RdmDevice = Depends(get_device)
) -> OkResponse:
    success = await device.dmx_config.set_start_address(body.address)
    return OkResponse(success=success)


@router.post("/{uid}/identify", response_model=OkResponse)
async def identify(body: IdentifyRequest, device: RdmDevice = Depends(get_device)) -> OkResponse:
    success = await device.control.identify(body.enable)
    return OkResponse(success=success)
