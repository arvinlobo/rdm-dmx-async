"""DEVICE_LABEL PID - GET/SET device label string."""

from typing import TYPE_CHECKING

from ...domain.parameters import StandardPID

if TYPE_CHECKING:
    from ..rdm_device import RdmDevice


class DeviceLabelAPI:
    """API for DEVICE_LABEL PID (0x0082) GET/SET operations."""

    def __init__(self, device: "RdmDevice"):
        self._device = device

    async def get(self, use_cache: bool = True) -> str:
        """
        Get device label string with optional caching.

        Args:
            use_cache: Whether to use cached value

        Returns:
            Device label string
        """
        return await self._device.get_string_parameter(
            StandardPID.DEVICE_LABEL, use_cache=use_cache
        )

    async def set(self, label: str) -> bool:
        """
        Set device label string.

        Args:
            label: New device label (max 32 characters)

        Returns:
            True if successful
        """
        data = label.encode("utf-8")[:32]  # RDM E1.20 max label length

        success = await self._device.execute_set(
            pid=StandardPID.DEVICE_LABEL.value,
            data=data,
        )

        if success:
            self._device.state.device_label = label
            self._device.clear_cache(StandardPID.DEVICE_LABEL.value)

        return success
