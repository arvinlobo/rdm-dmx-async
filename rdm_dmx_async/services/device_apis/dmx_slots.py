"""DMX slot information PIDs - SLOT_INFO, SLOT_DESCRIPTION, and DEFAULT_SLOT_VALUE."""

import struct
from typing import TYPE_CHECKING

from ...domain.parameters import StandardPID

if TYPE_CHECKING:
    from ..rdm_device import RdmDevice


class DmxSlotsAPI:
    """API for DMX slot information - SLOT_INFO, SLOT_DESCRIPTION, and DEFAULT_SLOT_VALUE."""

    def __init__(self, device: "RdmDevice"):
        self._device = device

    async def get_slot_info(self) -> list[int] | None:
        """
        Get slot information for all DMX slots.

        Returns:
            Raw slot info data or None if failed
        """
        response_data = await self._device.execute_get(pid=StandardPID.SLOT_INFO.value)
        return list(response_data) if response_data else None

    async def get_slot_description(self, slot_offset: int) -> tuple[int, str]:
        """
        Get description for a specific DMX slot.

        Args:
            slot_offset: Slot offset within personality footprint (0-based)

        Returns:
            Tuple of (slot_id, description_string)
        """
        data = struct.pack(">H", slot_offset)
        response_data = await self._device.execute_get(
            pid=StandardPID.SLOT_DESCRIPTION.value,
            data=data,
        )

        if response_data and len(response_data) >= 3:
            slot_id = struct.unpack(">H", bytes(response_data[:2]))[0]
            description = response_data[2:].decode("utf-8", errors="ignore").strip("\x00")
            return slot_id, description

        return slot_offset, ""

    async def get_all_slot_descriptions(self) -> list[str]:
        """
        Get descriptions for all slots in current personality.

        Returns:
            List of slot descriptions
        """
        footprint = self._device.state.dmx_footprint
        if footprint == 0:
            self._device.logger.warning("Footprint is 0, cannot get slot descriptions")
            return []

        descriptions = []
        for slot_offset in range(footprint):
            _, description = await self.get_slot_description(slot_offset)
            descriptions.append(description)

        return descriptions

    async def get_default_slot_values(self) -> list[tuple[int, int]] | None:
        """
        Get power-on default values for DMX slots.

        Returns:
            List of (slot_id, default_value) tuples, or None if failed
        """
        response_data = await self._device.execute_get(pid=StandardPID.DEFAULT_SLOT_VALUE.value)

        if response_data is None:
            return None

        defaults = []
        for i in range(0, len(response_data), 3):
            if i + 3 <= len(response_data):
                slot_id = struct.unpack(">H", bytes(response_data[i : i + 2]))[0]
                default_value = response_data[i + 2]
                defaults.append((slot_id, default_value))
        return defaults
