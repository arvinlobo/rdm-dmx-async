"""DMX operational modes - startup mode, output response time, capture preset."""

import struct
from typing import TYPE_CHECKING

from ...domain.parameters import StandardPID

if TYPE_CHECKING:
    from ..rdm_device import RdmDevice


class DmxModesAPI:
    """API for DMX operational modes - E1.37-1 PIDs and CAPTURE_PRESET."""

    def __init__(self, device: "RdmDevice"):
        self._device = device

    async def get_dmx_startup_mode(self, use_cache: bool = True) -> int | None:
        """
        Get DMX startup mode (E1.37-1 PID).

        Args:
            use_cache: Whether to use cached value

        Returns:
            Startup mode value or None
        """
        pid_value = StandardPID.DMX_STARTUP_MODE.value

        if use_cache:
            cached = self._device.cache_get(pid_value)
            if cached is not None:
                return cached

        response_data = await self._device.execute_get(pid=pid_value)

        if response_data and len(response_data) >= 2:
            mode = struct.unpack(">H", bytes(response_data[:2]))[0]
            if use_cache:
                self._device.cache_set(pid_value, mode)
            return mode
        return None

    async def set_dmx_startup_mode(self, mode: int) -> bool:
        """Set the E1.37-1 DMX startup mode."""
        data = struct.pack(">H", mode)
        success = await self._device.execute_set(
            pid=StandardPID.DMX_STARTUP_MODE.value,
            data=data,
        )
        if success:
            self._device.clear_cache(StandardPID.DMX_STARTUP_MODE.value)
        return success

    async def get_output_response_time(self, use_cache: bool = True) -> int | None:
        """Return the output response-time setting, or ``None`` on failure."""
        pid_value = StandardPID.OUTPUT_RESPONSE_TIME.value

        if use_cache:
            cached = self._device.cache_get(pid_value)
            if cached is not None:
                return cached

        response_data = await self._device.execute_get(pid=pid_value)

        if response_data and len(response_data) >= 1:
            value = response_data[0]
            if use_cache:
                self._device.cache_set(pid_value, value)
            return value
        return None

    async def set_output_response_time(self, value: int) -> bool:
        """Set the one-byte output response-time value."""
        data = struct.pack("B", value)
        success = await self._device.execute_set(
            pid=StandardPID.OUTPUT_RESPONSE_TIME.value,
            data=data,
        )
        if success:
            self._device.clear_cache(StandardPID.OUTPUT_RESPONSE_TIME.value)
        return success

    async def capture_preset(self, mode: int) -> bool:
        """Capture the current output using the specified preset mode."""
        data = struct.pack(">H", mode)
        return await self._device.execute_set(
            pid=StandardPID.CAPTURE_PRESET.value,
            data=data,
        )

    async def get_dmx_block_address(self, use_cache: bool = True) -> tuple | None:
        """
        Get DMX block address and footprint.

        Args:
            use_cache: Whether to use cached value

        Returns:
            Tuple of (total_sub_devices, footprint, start_address) or None
        """
        pid_value = StandardPID.DMX_BLOCK_ADDRESS.value

        if use_cache:
            cached = self._device.cache_get(pid_value)
            if cached is not None:
                return cached

        response_data = await self._device.execute_get(pid=pid_value)

        if response_data and len(response_data) >= 6:
            total_sub_devices = struct.unpack(">H", bytes(response_data[:2]))[0]
            footprint = struct.unpack(">H", bytes(response_data[2:4]))[0]
            start_address = struct.unpack(">H", bytes(response_data[4:6]))[0]
            result = (total_sub_devices, footprint, start_address)
            if use_cache:
                self._device.cache_set(pid_value, result)
            return result
        return None

    async def set_dmx_block_address(self, start_address: int) -> bool:
        """
        Set DMX block start address.

        Args:
            start_address: DMX start address (1-512)

        Returns:
            True if successful
        """
        if not (1 <= start_address <= 512):
            self._device.logger.error("Invalid DMX block address: %d", start_address)
            return False

        data = struct.pack(">H", start_address)
        success = await self._device.execute_set(
            pid=StandardPID.DMX_BLOCK_ADDRESS.value,
            data=data,
        )
        if success:
            self._device.clear_cache(StandardPID.DMX_BLOCK_ADDRESS.value)
        return success

    async def get_dmx_fail_mode(self, use_cache: bool = True) -> tuple | None:
        """
        Get DMX fail mode settings.

        Args:
            use_cache: Whether to use cached value

        Returns:
            Tuple of (scene, loss_of_signal_delay, hold_time, fail_mode_level) or None
        """
        pid_value = StandardPID.DMX_FAIL_MODE.value

        if use_cache:
            cached = self._device.cache_get(pid_value)
            if cached is not None:
                return cached

        response_data = await self._device.execute_get(pid=pid_value)

        if response_data and len(response_data) >= 7:
            scene = struct.unpack(">H", bytes(response_data[:2]))[0]
            loss_of_signal_delay = struct.unpack(">H", bytes(response_data[2:4]))[0]
            hold_time = struct.unpack(">H", bytes(response_data[4:6]))[0]
            fail_mode_level = response_data[6]
            result = (scene, loss_of_signal_delay, hold_time, fail_mode_level)
            if use_cache:
                self._device.cache_set(pid_value, result)
            return result
        return None

    async def set_dmx_fail_mode(
        self, scene: int, loss_of_signal_delay: int, hold_time: int, fail_mode_level: int
    ) -> bool:
        """
        Set DMX fail mode settings.

        Args:
            scene: Scene number
            loss_of_signal_delay: Delay in seconds before activating fail mode
            hold_time: Hold time in seconds
            fail_mode_level: Fail mode level (0-255)

        Returns:
            True if successful
        """
        data = struct.pack(">HHHB", scene, loss_of_signal_delay, hold_time, fail_mode_level)
        success = await self._device.execute_set(
            pid=StandardPID.DMX_FAIL_MODE.value,
            data=data,
        )
        if success:
            self._device.clear_cache(StandardPID.DMX_FAIL_MODE.value)
        return success
