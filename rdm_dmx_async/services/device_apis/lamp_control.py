"""Lamp control PIDs - hours, strikes, state, on mode."""

import struct
from typing import TYPE_CHECKING

from ...domain.parameters import StandardPID

if TYPE_CHECKING:
    from ..rdm_device import RdmDevice


class LampControlAPI:
    """API for lamp control PIDs - LAMP_HOURS, LAMP_STRIKES, LAMP_STATE, LAMP_ON_MODE."""

    def __init__(self, device: "RdmDevice"):
        self._device = device

    async def get_hours(self, use_cache: bool = True) -> int | None:
        """
        Get lamp operating hours.

        Args:
            use_cache: Whether to use cached value

        Returns:
            Hours or None
        """
        pid_value = StandardPID.LAMP_HOURS.value

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
        """
        Set lamp operating hours.

        Args:
            hours: Lamp hours to set

        Returns:
            True if successful
        """
        data = struct.pack(">I", hours)
        success = await self._device.execute_set(
            pid=StandardPID.LAMP_HOURS.value,
            data=data,
        )
        if success:
            self._device.clear_cache(StandardPID.LAMP_HOURS.value)
        return success

    async def get_strikes(self, use_cache: bool = True) -> int | None:
        """
        Get lamp strikes count.

        Args:
            use_cache: Whether to use cached value

        Returns:
            Strikes count or None
        """
        pid_value = StandardPID.LAMP_STRIKES.value

        if use_cache:
            cached = self._device.cache_get(pid_value)
            if cached is not None:
                return cached

        response_data = await self._device.execute_get(pid=pid_value)

        if response_data and len(response_data) >= 4:
            strikes = struct.unpack(">I", bytes(response_data[:4]))[0]
            if use_cache:
                self._device.cache_set(pid_value, strikes)
            return strikes
        return None

    async def set_strikes(self, strikes: int) -> bool:
        """
        Set lamp strikes count.

        Args:
            strikes: Lamp strikes to set

        Returns:
            True if successful
        """
        data = struct.pack(">I", strikes)
        success = await self._device.execute_set(
            pid=StandardPID.LAMP_STRIKES.value,
            data=data,
        )
        if success:
            self._device.clear_cache(StandardPID.LAMP_STRIKES.value)
        return success

    async def get_state(self, use_cache: bool = True) -> int | None:
        """
        Get lamp state.

        Args:
            use_cache: Whether to use cached value

        Returns:
            Lamp state value or None
        """
        pid_value = StandardPID.LAMP_STATE.value

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
        Set lamp state.

        Args:
            state: Lamp state to set

        Returns:
            True if successful
        """
        data = struct.pack("B", state)
        success = await self._device.execute_set(
            pid=StandardPID.LAMP_STATE.value,
            data=data,
        )
        if success:
            self._device.clear_cache(StandardPID.LAMP_STATE.value)
        return success

    async def get_on_mode(self, use_cache: bool = True) -> int | None:
        """
        Get lamp on mode.

        Args:
            use_cache: Whether to use cached value

        Returns:
            Lamp on mode or None
        """
        pid_value = StandardPID.LAMP_ON_MODE.value

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

    async def set_on_mode(self, mode: int) -> bool:
        """
        Set lamp on mode.

        Args:
            mode: Lamp on mode to set

        Returns:
            True if successful
        """
        data = struct.pack("B", mode)
        success = await self._device.execute_set(
            pid=StandardPID.LAMP_ON_MODE.value,
            data=data,
        )
        if success:
            self._device.clear_cache(StandardPID.LAMP_ON_MODE.value)
        return success
