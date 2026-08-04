"""Device control PIDs - identify, reset, factory defaults."""

from typing import TYPE_CHECKING

from ...domain.parameters import StandardPID

if TYPE_CHECKING:
    from ..rdm_device import RdmDevice


class DeviceControlAPI:
    """API for device control PIDs - IDENTIFY_DEVICE, RESET_DEVICE, FACTORY_DEFAULTS."""

    def __init__(self, device: "RdmDevice"):
        self._device = device

    async def identify(self, enable: bool = True) -> bool:
        """
        Enable/disable device identify mode (blinking light).

        Args:
            enable: True to enable, False to disable

        Returns:
            True if successful
        """
        data = b"\x01" if enable else b"\x00"
        return await self._device.execute_set(
            pid=StandardPID.IDENTIFY_DEVICE.value,
            data=data,
        )

    async def reset(self, warm_reset: bool = True) -> bool:
        """Reset the device and clear cached parameters on success.

        Args:
            warm_reset: Use a warm reset when true, otherwise a cold reset.
        """
        reset_flag = b"\x01" if warm_reset else b"\xff"
        success = await self._device.execute_set(
            pid=StandardPID.RESET_DEVICE.value,
            data=reset_flag,
        )
        if success:
            self._device.clear_cache()
        return success

    async def factory_defaults(self) -> bool:
        """Restore factory defaults and clear cached parameters on success."""
        success = await self._device.execute_set(
            pid=StandardPID.FACTORY_DEFAULTS.value,
            data=b"",
        )
        if success:
            self._device.clear_cache()
        return success
