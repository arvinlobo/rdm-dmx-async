"""Position configuration PIDs - pan/tilt invert and swap."""

import struct
from typing import TYPE_CHECKING

from ...domain.parameters import StandardPID

if TYPE_CHECKING:
    from ..rdm_device import RdmDevice


class PositionConfigAPI:
    """API for position configuration PIDs - PAN_INVERT, TILT_INVERT, PAN_TILT_SWAP."""

    def __init__(self, device: "RdmDevice"):
        self._device = device

    async def get_pan_invert(self, use_cache: bool = True) -> int | None:
        """
        Get pan invert setting.

        Args:
            use_cache: Whether to use cached value

        Returns:
            Invert setting or None
        """
        pid_value = StandardPID.PAN_INVERT.value

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

    async def set_pan_invert(self, invert: int) -> bool:
        """
        Set pan invert setting.

        Args:
            invert: 0 for normal, 1 for inverted

        Returns:
            True if successful
        """
        data = struct.pack("B", invert)
        success = await self._device.execute_set(
            pid=StandardPID.PAN_INVERT.value,
            data=data,
        )
        if success:
            self._device.clear_cache(StandardPID.PAN_INVERT.value)
        return success

    async def get_tilt_invert(self, use_cache: bool = True) -> int | None:
        """
        Get tilt invert setting.

        Args:
            use_cache: Whether to use cached value

        Returns:
            Invert setting or None
        """
        pid_value = StandardPID.TILT_INVERT.value

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

    async def set_tilt_invert(self, invert: int) -> bool:
        """
        Set tilt invert setting.

        Args:
            invert: 0 for normal, 1 for inverted

        Returns:
            True if successful
        """
        data = struct.pack("B", invert)
        success = await self._device.execute_set(
            pid=StandardPID.TILT_INVERT.value,
            data=data,
        )
        if success:
            self._device.clear_cache(StandardPID.TILT_INVERT.value)
        return success

    async def get_pan_tilt_swap(self, use_cache: bool = True) -> int | None:
        """
        Get pan/tilt swap setting.

        Args:
            use_cache: Whether to use cached value

        Returns:
            Swap setting or None
        """
        pid_value = StandardPID.PAN_TILT_SWAP.value

        if use_cache:
            cached = self._device.cache_get(pid_value)
            if cached is not None:
                return cached

        response_data = await self._device.execute_get(pid=pid_value)

        if response_data and len(response_data) >= 1:
            swap = response_data[0]
            if use_cache:
                self._device.cache_set(pid_value, swap)
            return swap
        return None

    async def set_pan_tilt_swap(self, swap: int) -> bool:
        """
        Set pan/tilt swap setting.

        Args:
            swap: 0 for normal, 1 for swapped

        Returns:
            True if successful
        """
        data = struct.pack("B", swap)
        success = await self._device.execute_set(
            pid=StandardPID.PAN_TILT_SWAP.value,
            data=data,
        )
        if success:
            self._device.clear_cache(StandardPID.PAN_TILT_SWAP.value)
        return success

    async def get_real_time_clock(self, use_cache: bool = True) -> int | None:
        """
        Get real-time clock value.

        Args:
            use_cache: Whether to use cached value

        Returns:
            RTC timestamp or None
        """
        pid_value = StandardPID.REAL_TIME_CLOCK.value

        if use_cache:
            cached = self._device.cache_get(pid_value)
            if cached is not None:
                return cached

        response_data = await self._device.execute_get(pid=pid_value)

        if response_data and len(response_data) >= 7:
            # Year, Month, Day, Hour, Minute, Second (7 bytes)
            year = struct.unpack(">H", bytes(response_data[:2]))[0]
            month, day, hour, minute, second = response_data[2:7]
            # Return as timestamp or dict
            if use_cache:
                self._device.cache_set(pid_value, (year, month, day, hour, minute, second))
            return (year, month, day, hour, minute, second)
        return None

    async def set_real_time_clock(
        self, year: int, month: int, day: int, hour: int, minute: int, second: int
    ) -> bool:
        """
        Set real-time clock value.

        Args:
            year: Year (e.g., 2026)
            month: Month (1-12)
            day: Day (1-31)
            hour: Hour (0-23)
            minute: Minute (0-59)
            second: Second (0-59)

        Returns:
            True if successful
        """
        data = struct.pack(">HBBBBB", year, month, day, hour, minute, second)
        success = await self._device.execute_set(
            pid=StandardPID.REAL_TIME_CLOCK.value,
            data=data,
        )
        if success:
            self._device.clear_cache(StandardPID.REAL_TIME_CLOCK.value)
        return success
