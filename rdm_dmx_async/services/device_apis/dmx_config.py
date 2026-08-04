"""DMX configuration PIDs - start address, personality, and personality description GET/SET."""

import struct
from typing import TYPE_CHECKING

from ...domain.parameters import StandardPID

if TYPE_CHECKING:
    from ..rdm_device import RdmDevice


class DmxConfigAPI:
    """API for DMX configuration PIDs - start address, personality, and personality description."""

    def __init__(self, device: "RdmDevice"):
        self._device = device

    async def set_start_address(self, address: int) -> bool:
        """
        Set DMX start address.

        Args:
            address: DMX start address (1-512)

        Returns:
            True if successful
        """
        if not (1 <= address <= 512):
            self._device.logger.error("Invalid DMX address: %s", address)
            return False

        data = struct.pack(">H", address)
        success = await self._device.execute_set(
            pid=StandardPID.DMX_START_ADDRESS.value,
            data=data,
        )

        if success:
            self._device.state.dmx_start_address = address
            self._device.clear_cache(StandardPID.DMX_START_ADDRESS.value)

        return success

    async def get_personality(self, use_cache: bool = True) -> tuple | None:
        """Return the current personality and available personality count.

        Returns:
            A ``(current, count)`` tuple, or ``None`` when the device does not
            return a valid value.
        """
        pid_value = StandardPID.DMX_PERSONALITY.value

        if use_cache:
            cached = self._device.cache_get(pid_value)
            if cached is not None:
                return cached

        response_data = await self._device.execute_get(pid=pid_value)

        if response_data and len(response_data) >= 2:
            current = response_data[0]
            count = response_data[1]
            value = (current, count)

            self._device.state.dmx_personality = current
            self._device.state.dmx_personality_count = count

            if use_cache:
                self._device.cache_set(pid_value, value)
            return value
        return None

    async def set_personality(self, personality: int) -> bool:
        """Set the active DMX personality.

        Returns:
            ``False`` when ``personality`` is less than one or the SET fails.
        """
        if personality < 1:
            self._device.logger.error("Invalid personality: %s", personality)
            return False

        data = struct.pack("B", personality)
        success = await self._device.execute_set(
            pid=StandardPID.DMX_PERSONALITY.value,
            data=data,
        )

        if success:
            self._device.state.dmx_personality = personality
            self._device.clear_cache(StandardPID.DMX_PERSONALITY.value)
            self._device.clear_cache(StandardPID.DEVICE_INFO.value)

        return success

    async def get_personality_description(self, personality: int) -> dict | None:
        """
        Get name and DMX footprint for a specific personality.

        Args:
            personality: Personality index to query (1-based)

        Returns:
            Dictionary with 'personality', 'footprint', and 'description', or None
        """
        data = struct.pack("B", personality)
        response_data = await self._device.execute_get(
            pid=StandardPID.DMX_PERSONALITY_DESCRIPTION.value,
            data=data,
        )

        if response_data and len(response_data) >= 3:
            queried_personality = response_data[0]
            footprint = struct.unpack(">H", bytes(response_data[1:3]))[0]
            description = response_data[3:].decode("utf-8", errors="ignore").strip("\x00")
            return {
                "personality": queried_personality,
                "footprint": footprint,
                "description": description,
            }
        return None
