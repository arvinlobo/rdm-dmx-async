"""DMX output endpoint."""

from fastapi import APIRouter, Depends

from rdm_dmx_async.application.network_manager import NetworkManager

from ..dependencies import get_network_manager
from ..schemas import DmxSendRequest, OkResponse

router = APIRouter(prefix="/dmx", tags=["dmx"])


@router.post("/send", response_model=OkResponse)
async def send_dmx(
    body: DmxSendRequest, manager: NetworkManager = Depends(get_network_manager)
) -> OkResponse:
    await manager.send_dmx(bytes(body.channels), port=body.port, repeat=body.repeat)
    return OkResponse()
