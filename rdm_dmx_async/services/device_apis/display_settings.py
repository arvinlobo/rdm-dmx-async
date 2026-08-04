"""Display settings PIDs - invert and level."""

import struct
from typing import TYPE_CHECKING

from ...domain.parameters import StandardPID

if TYPE_CHECKING:
    from ..rdm_device import RdmDevice


class DisplaySettingsAPI:
    """API for display settings PIDs - DISPLAY_INVERT and DISPLAY_LEVEL."""

    def __init__(self, device: "RdmDevice"):
        self._device = device

    async def get_invert(self, use_cache: bool = True) -> int | None:
        """
        Get display invert setting.

        Args:
            use_cache: Whether to use cached value

        Returns:
            Invert setting or None
        """
        pid_value = StandardPID.DISPLAY_INVERT.value

        if use_cache:
            cached = self._device.cache_get(pid_value)
            if cached is not None:
                return cached

        response_data = await self._device.execute_get(pid=pid_value)

        if response_data and len(response_data) >= 1:
            invert = response_data[0]
            if use_cache:
                self._device.cache_set(pid_value, invert)
            return invert
        return None

    async def set_invert(self, invert: int) -> bool:
        """
        Set display invert setting.

        Args:
            invert: 0 for normal, 1 for inverted

        Returns:
            True if successful
        """
        data = struct.pack("B", invert)
        success = await self._device.execute_set(
            pid=StandardPID.DISPLAY_INVERT.value,
            data=data,
        )
        if success:
            self._device.clear_cache(StandardPID.DISPLAY_INVERT.value)
        return success

    async def get_level(self, use_cache: bool = True) -> int | None:
        """
        Get display level (brightness).

        Args:
            use_cache: Whether to use cached value

        Returns:
            Display level or None
        """
        pid_value = StandardPID.DISPLAY_LEVEL.value

        if use_cache:
            cached = self._device.cache_get(pid_value)
            if cached is not None:
                return cached

        response_data = await self._device.execute_get(pid=pid_value)

        if response_data and len(response_data) >= 1:
            level = response_data[0]
            if use_cache:
                self._device.cache_set(pid_value, level)
            return level
        return None

    async def set_level(self, level: int) -> bool:
        """
        Set display level (brightness).

        Args:
            level: Display brightness level

        Returns:
            True if successful
        """
        data = struct.pack("B", level)
        success = await self._device.execute_set(
            pid=StandardPID.DISPLAY_LEVEL.value,
            data=data,
        )
        if success:
            self._device.clear_cache(StandardPID.DISPLAY_LEVEL.value)
        return success
