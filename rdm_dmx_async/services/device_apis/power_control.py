"""Power control PIDs - power state GET/SET."""

import struct
from typing import TYPE_CHECKING

from ...domain.parameters import StandardPID

if TYPE_CHECKING:
    from ..rdm_device import RdmDevice


class PowerControlAPI:
    """API for power control PIDs - POWER_STATE."""

    def __init__(self, device: "RdmDevice"):
        self._device = device

    async def get_state(self, use_cache: bool = True) -> int | None:
        """
        Get device power state.

        Args:
            use_cache: Whether to use cached value

        Returns:
            Power state value or None
        """
        pid_value = StandardPID.POWER_STATE.value

        if use_cache:
            cached = self._device.cache_get(pid_value)
            if cached is not None:
                return cached

        response_data = await self._device.execute_get(pid=pid_value)

        if response_data and len(response_data) >= 1:
            state = response_data[0]
            if use_cache:
                self._device.cache_set(pid_value, state)
            return state
        return None

    async def set_state(self, state: int) -> bool:
        """
        Set device power state.

        Args:
            state: Power state to set (e.g., 0=off, 1=on, 2=standby)

        Returns:
            True if successful
        """
        data = struct.pack("B", state)
        success = await self._device.execute_set(
            pid=StandardPID.POWER_STATE.value,
            data=data,
        )
        if success:
            self._device.clear_cache(StandardPID.POWER_STATE.value)
        return success
