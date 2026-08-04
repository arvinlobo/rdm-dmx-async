"""Device maintenance PIDs - device hours and power cycles GET/SET."""

import struct
from typing import TYPE_CHECKING

from ...domain.parameters import StandardPID

if TYPE_CHECKING:
    from ..rdm_device import RdmDevice


class DeviceMaintenanceAPI:
    """API for device maintenance PIDs - DEVICE_HOURS and DEVICE_POWER_CYCLES."""

    def __init__(self, device: "RdmDevice"):
        self._device = device

    async def get_hours(self, use_cache: bool = True) -> int | None:
        """
        Get device operating hours.

        Args:
            use_cache: Whether to use cached value

        Returns:
            Hours or None
        """
        pid_value = StandardPID.DEVICE_HOURS.value

        if use_cache:
            cached = self._device.cache_get(pid_value)
            if cached is not None:
                return cached

        response_data = await self._device.execute_get(pid=pid_value)

        if response_data and len(response_data) >= 4:
            hours = struct.unpack(">I", bytes(response_data[:4]))[0]
            if use_cache:
                self._device.cache_set(pid_value, hours)
            return hours
        return None

    async def set_hours(self, hours: int) -> bool:
        """Set the device's accumulated operating hours."""
        data = struct.pack(">I", hours)
        success = await self._device.execute_set(
            pid=StandardPID.DEVICE_HOURS.value,
            data=data,
        )
        if success:
            self._device.clear_cache(StandardPID.DEVICE_HOURS.value)
        return success

    async def get_power_cycles(self, use_cache: bool = True) -> int | None:
        """
        Get device power cycles count.

        Args:
            use_cache: Whether to use cached value

        Returns:
            Power cycles or None
        """
        pid_value = StandardPID.DEVICE_POWER_CYCLES.value

        if use_cache:
            cached = self._device.cache_get(pid_value)
            if cached is not None:
                return cached

        response_data = await self._device.execute_get(pid=pid_value)

        if response_data and len(response_data) >= 4:
            cycles = struct.unpack(">I", bytes(response_data[:4]))[0]
            if use_cache:
                self._device.cache_set(pid_value, cycles)
            return cycles
        return None

    async def set_power_cycles(self, cycles: int) -> bool:
        """
        Set device power cycles count.

        Args:
            cycles: Power cycles to set

        Returns:
            True if successful
        """
        data = struct.pack(">I", cycles)
        success = await self._device.execute_set(
            pid=StandardPID.DEVICE_POWER_CYCLES.value,
            data=data,
        )
        if success:
            self._device.clear_cache(StandardPID.DEVICE_POWER_CYCLES.value)
        return success
