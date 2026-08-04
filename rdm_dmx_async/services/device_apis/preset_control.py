"""Preset control PIDs - playback, status, and merge mode."""

import struct
from typing import TYPE_CHECKING

from ...domain.parameters import StandardPID

if TYPE_CHECKING:
    from ..rdm_device import RdmDevice


class PresetControlAPI:
    """API for preset control PIDs - PRESET_PLAYBACK, PRESET_STATUS, PRESET_MERGEMODE."""

    def __init__(self, device: "RdmDevice"):
        self._device = device

    async def get_playback(self, use_cache: bool = True) -> tuple | None:
        """
        Get preset playback settings.

        Args:
            use_cache: Whether to use cached value

        Returns:
            Tuple of (mode, level) or None
        """
        pid_value = StandardPID.PRESET_PLAYBACK.value

        if use_cache:
            cached = self._device.cache_get(pid_value)
            if cached is not None:
                return cached

        response_data = await self._device.execute_get(pid=pid_value)

        if response_data and len(response_data) >= 3:
            mode = struct.unpack(">H", bytes(response_data[:2]))[0]
            level = response_data[2]
            result = (mode, level)
            if use_cache:
                self._device.cache_set(pid_value, result)
            return result
        return None

    async def set_playback(self, mode: int, level: int) -> bool:
        """
        Set preset playback settings.

        Args:
            mode: Preset mode (scene number)
            level: Preset level (0-255)

        Returns:
            True if successful
        """
        data = struct.pack(">HB", mode, level)
        success = await self._device.execute_set(
            pid=StandardPID.PRESET_PLAYBACK.value,
            data=data,
        )
        if success:
            self._device.clear_cache(StandardPID.PRESET_PLAYBACK.value)
        return success

    async def get_status(self, use_cache: bool = True) -> dict | None:
        """
        Get preset status.

        Args:
            use_cache: Whether to use cached value

        Returns:
            Dictionary with scene, up_fade, down_fade, wait_time or None
        """
        pid_value = StandardPID.PRESET_STATUS.value

        if use_cache:
            cached = self._device.cache_get(pid_value)
            if cached is not None:
                return cached

        response_data = await self._device.execute_get(pid=pid_value)

        if response_data and len(response_data) >= 8:
            scene = struct.unpack(">H", bytes(response_data[:2]))[0]
            up_fade = struct.unpack(">H", bytes(response_data[2:4]))[0]
            down_fade = struct.unpack(">H", bytes(response_data[4:6]))[0]
            wait_time = struct.unpack(">H", bytes(response_data[6:8]))[0]
            result = {
                "scene": scene,
                "up_fade": up_fade,
                "down_fade": down_fade,
                "wait_time": wait_time,
            }
            if use_cache:
                self._device.cache_set(pid_value, result)
            return result
        return None

    async def get_merge_mode(self, use_cache: bool = True) -> int | None:
        """
        Get preset merge mode.

        Args:
            use_cache: Whether to use cached value

        Returns:
            Merge mode value or None
        """
        pid_value = StandardPID.PRESET_MERGEMODE.value

        if use_cache:
            cached = self._device.cache_get(pid_value)
            if cached is not None:
                return cached

        response_data = await self._device.execute_get(pid=pid_value)

        if response_data and len(response_data) >= 1:
            mode = response_data[0]
            if use_cache:
                self._device.cache_set(pid_value, mode)
            return mode
        return None

    async def set_merge_mode(self, mode: int) -> bool:
        """
        Set preset merge mode.

        Args:
            mode: Merge mode to set

        Returns:
            True if successful
        """
        data = struct.pack("B", mode)
        success = await self._device.execute_set(
            pid=StandardPID.PRESET_MERGEMODE.value,
            data=data,
        )
        if success:
            self._device.clear_cache(StandardPID.PRESET_MERGEMODE.value)
        return success
